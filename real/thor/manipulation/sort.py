"""Colour sorting (docs/sorting): the balls on the tray, one at a time, into the box of their colour.

The scripted version: the torso camera finds the balls and reads their colour (skills.look), the arm controller's
inverse kinematics plans every pose and the existing checks guard every move (joint limits, joint flips, head
clearance), as for the cup picks. The learned policy replaces only `_sort_one`'s motion later; the checks, the
camera, the state and STOP stay.

What it needs on the robot, both written once with the owner at the robot:
- data/sort_layout.json: where the tray and the two boxes stand (tray centre and size, box centres and rim height,
  mm in the arm base frame) and which colour goes in which box. `python manipulation/sort.py layout` writes it from
  the hand's grasp point held over each place in free drive.
- data/grasp_ball_teach.json: the ball grasp with the straight fingers (the flange pose with a ball centred between
  the pads, and that ball's centre). `python manipulation/sort.py teach` writes it.

    python manipulation/sort.py plan       # dry run: balls seen, their boxes, every waypoint with IK joints; nothing moves
    python manipulation/sort.py teach      # the ball grasp (free drive), see above
    python manipulation/sort.py layout     # the tray and boxes (free drive), see above
    python manipulation/sort.py run        # sort everything on the tray (the API's POST /skills/sort does this)

Ctrl+C, skills.cancel() (STOP in the API) or any motion error stops the arm; the gripper keeps its state.
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from manipulation import skills
from robot import gripper
from robot import motion
from vision import calib

ROOT = Path(__file__).resolve().parents[1]
LAYOUT_FILE = ROOT / "data" / "sort_layout.json"
TEACH_FILE = ROOT / "data" / "grasp_ball_teach.json"

BALL_CLASS = "sports ball"          # the COCO class the detector gives a ball
BALL_R_MM = 21.25                   # foam golf practice ball, 42.5 mm (docs/sorting/02)
ABOVE_MM = 90.0                     # approach and retreat height over the ball's centre
DROP_ABOVE_RIM_MM = 45.0            # the grasp point this far over a box's rim when the ball is let go
YAWS = (0, 30, -30, 60, -60, 90, -90, 120, -120, 150, -150, 180)   # deg; the taught grasp turned about the vertical
MAX_TILT_DEG = 45.0                 # deg; the fingers may lean this far from the taught (straight down) grasp at a ball
TILTS = (0.0, 15.0, 30.0, 45.0)     # ... tried in this order, each towards 8 directions
MAX_FAILS = 3                       # balls missed or dropped in a row: stop
MAX_BALLS = 12                      # a run never picks more than this (a ball seen again and again is not looped on)
TRAY_MARGIN_MM = 10.0               # a ball counts as on the tray within its outline grown by this

state = {"done": 0, "failed": 0, "left": None, "current": None}   # shown by /skills/state while sorting


# ---------- what was taught ----------
def layout():
    if not LAYOUT_FILE.exists():
        raise skills.SkillError("The boxes aren't set up.")
    return json.loads(LAYOUT_FILE.read_text())


def grasp():
    """(R, offset): the taught ball grasp's flange orientation and the ball centre in the flange frame (mm)."""
    if not TEACH_FILE.exists():
        raise skills.SkillError("I haven't learned how to hold a ball yet.")
    t = json.loads(TEACH_FILE.read_text())
    f = t["flange"]
    R = calib.rpy_matrix(*f[3:])
    return R, R.T @ (np.array(t["ball"]) - np.array(f[:3]))


def _rot(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "z":
        return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
    return np.array([[1.0, 0, 0], [0, c, -s], [0, s, c]])        # x


def flange_at(p, R):
    """Flange pose [x, y, z, rx, ry, rz] that puts the taught ball centre at `p` (mm) with flange orientation `R`."""
    _, offset = grasp()
    f = np.array(p, float) - R @ offset
    return [float(v) for v in f] + skills.rpy_of(R)


def hands(max_tilt=MAX_TILT_DEG):
    """Flange orientations for a ball: the taught one (fingers straight down) turned about the vertical, then leaning
    up to `max_tilt` deg towards 8 directions. Straightest first."""
    R0, _ = grasp()
    for tilt in TILTS:
        if tilt > max_tilt:
            break
        for lean in ((0,) if tilt == 0 else range(0, 360, 45)):
            L = _rot("z", lean) @ _rot("x", tilt) @ _rot("z", -lean)   # lean the hand `tilt` deg towards `lean`
            for yaw in YAWS:
                yield L @ _rot("z", yaw) @ R0


# ---------- seeing ----------
def on_tray(o, lay):
    (cx, cy), (w, h) = lay["tray"]["centre"], lay["tray"]["size"]
    return abs(o["x"] - cx) <= w / 2 + TRAY_MARGIN_MM and abs(o["y"] - cy) <= h / 2 + TRAY_MARGIN_MM


def balls(lay, seen=None):
    """Steady balls on the tray, nearest the arm first: [{x, y, z (centre), colour, box}]; box None for a colour that
    has no box."""
    seen = skills.look() if seen is None else seen
    out = []
    for o in seen:
        if o["name"] != BALL_CLASS and BALL_CLASS not in o.get("names", ()):
            continue
        if o["seen"] < skills.MIN_SEEN or o["spread"] > skills.SPREAD_MM or o["top_mm"] is None or not on_tray(o, lay):
            continue
        out.append({"x": o["x"], "y": o["y"], "z": o["top_mm"] - BALL_R_MM, "colour": o["colour"],
                    "box": lay["colours"].get(o["colour"])})
    return sorted(out, key=lambda b: np.hypot(b["x"], b["y"]))


# ---------- planning ----------
def plan_ball(ball, lay, start):
    """Waypoints and joints for one ball: [(name, flange pose)], the joints at "above" (a joint move from `start`).
    Above the ball, straight down to it, straight back up (one hand orientation), then the drop over its box (any
    orientation the arm reaches). None when nothing passes the checks."""
    box = lay["boxes"][ball["box"]]
    p = np.array([ball["x"], ball["y"], ball["z"]])
    drop = np.array([box["centre"][0], box["centre"][1], box["rim_mm"] + DROP_ABOVE_RIM_MM])
    for R in hands():
        g = flange_at(p, R)
        a = skills.up(g, ABOVE_MM)
        for ja in skills.above_joints(a, start):
            if not skills.move_ok(start, ja):
                continue
            rows = skills.ik_chain([("above", a), ("grasp", g), ("lift", a)], ja)
            if rows[-1][3]:
                continue
            for Rd in hands(max_tilt=90.0):                   # the drop: the arm may hold the ball any way
                d = flange_at(drop, Rd)
                jd = skills._solve(d, rows[-1][2], rows[-1][2])
                if jd is not None and skills.move_ok(rows[-1][2], jd):
                    return [("above", a), ("grasp", g), ("lift", a), ("drop", d)], ja, jd
    return None


# ---------- moving ----------
def _sort_one(ball, plan):
    """Pick the ball and let it go over its box. Raises SkillError when it was missed or dropped (the arm is then back
    up at "above" and open)."""
    way = dict(plan[0])
    ja, jd = plan[1], plan[2]
    skills._go_on()
    skills.log(f"{ball['colour']} ball at ({ball['x']:.0f}, {ball['y']:.0f}): to the {ball['box']} box")
    motion.move_joints(ja, skills.EMPTY_SPEED)
    skills._line("grasp", way["grasp"])
    skills._go_on()
    s = gripper.close()
    skills.log(f"closed: AI_1 {s['ai'][0]:.0f} holding {s['holding']}")
    if not s["holding"]:
        gripper.open_()
        skills._line("up", way["above"])
        raise skills.SkillError("I missed the ball.")
    skills._line("lift", way["lift"])
    if not gripper.state()["holding"]:
        gripper.open_()
        raise skills.SkillError("The ball slipped out of my hand.")
    skills._go_on()
    motion.move_joints(jd, skills.HOLDING_SPEED)
    s = gripper.open_()
    skills.log(f"let go over the {ball['box']} box: AI_1 {s['ai'][0]:.0f}")
    if s["ai"][0] > skills.OPEN_AI:
        raise skills.SkillError("My hand did not open.")


def run():
    """Sort every steady ball on the tray. Returns {done, failed}; refuses before anything moves when the tray, the
    boxes or the ball grasp are not set up, or no ball is seen."""
    skills._cancel.clear()
    lay = layout()
    grasp()
    state.update(done=0, failed=0, left=None, current=None)
    skills._prepare()                                       # open, back out of a stopped pick, home (look)
    fails = 0
    for _ in range(MAX_BALLS):
        skills._go_on()
        seen = balls(lay)
        sortable = [b for b in seen if b["box"]]
        state["left"] = len(sortable)
        for b in seen:
            if not b["box"]:
                skills.log(f"a {b['colour']} ball: no box for that colour, left on the tray")
        if not sortable:
            break
        start = skills._joints()
        ball, plan = next(((b, p) for b in sortable for p in [plan_ball(b, lay, start)] if p), (None, None))
        if ball is None:
            raise skills.SkillError("I can't reach the balls that are left safely.")
        state["current"] = {"colour": ball["colour"], "box": ball["box"]}
        try:
            skills._guarded(_sort_one, ball, plan)
            state["done"] += 1
            fails = 0
        except skills.SkillError as e:
            if e.args and e.args[0] == "Stopped.":
                raise
            state["failed"] += 1
            fails += 1
            skills.log(f"{e.args[0]} ({fails} in a row)")
            if fails >= MAX_FAILS:
                raise skills.SkillError(f"I missed {fails} balls in a row, so I stopped.")
        skills._back_home()
    state.update(current=None, left=0)
    if state["done"] == 0 and state["failed"] == 0:
        raise skills.SkillError("I don't see any balls on the tray.")
    skills.log(f"sorted {state['done']}, missed {state['failed']}")
    return {"done": state["done"], "failed": state["failed"]}


# ---------- teaching (owner at the robot, free drive) ----------
def teach():
    """The ball grasp: a ball on the table, seen by the camera from `look`; then the owner free-drives the fingers
    around it (pads centred on the ball, fingers straight down) and presses Enter: the flange pose is read."""
    seen = [o for o in skills.look() if o["name"] == BALL_CLASS and o["top_mm"] is not None]
    if not seen:
        sys.exit("no ball seen: put one on the table in front of Lumi, arm at look")
    b = seen[0]
    ball = [b["x"], b["y"], b["top_mm"] - BALL_R_MM]
    print(f"ball at ({ball[0]:.0f}, {ball[1]:.0f}, {ball[2]:.0f}) mm. Free-drive the fingers around it, pads centred, "
          "fingers straight down, then press Enter (the gripper is not closed).")
    input()
    f = motion.tcp()
    TEACH_FILE.write_text(json.dumps({"flange": [round(v, 2) for v in f], "ball": [round(v, 1) for v in ball],
                                      "time": time.strftime("%Y-%m-%d %H:%M")}, indent=1))
    print(f"saved {TEACH_FILE.relative_to(ROOT)}")


def teach_layout():
    """The tray and the boxes: the owner holds the taught grasp point over each place in free drive, Enter each time."""
    _, offset = grasp()

    def point(what):
        input(f"hold the grasp point over {what}, then press Enter ")
        f = motion.tcp()
        return calib.rpy_matrix(*f[3:]) @ offset + np.array(f[:3])

    corners = [point(f"tray corner {i + 1} of 4 (on its rim)") for i in range(4)]
    xs, ys = [c[0] for c in corners], [c[1] for c in corners]
    boxes = {}
    for colour in ("red", "yellow"):
        c = point(f"the middle of the {colour} box, level with its rim")
        boxes[colour] = {"centre": [round(float(c[0]), 1), round(float(c[1]), 1)], "rim_mm": round(float(c[2]), 1)}
    LAYOUT_FILE.write_text(json.dumps({
        "tray": {"centre": [round(float(np.mean(xs)), 1), round(float(np.mean(ys)), 1)],
                 "size": [round(float(max(xs) - min(xs)), 1), round(float(max(ys) - min(ys)), 1)]},
        "boxes": boxes, "colours": {"red": "red", "yellow": "yellow", "orange": "red"},
        "time": time.strftime("%Y-%m-%d %H:%M")}, indent=1))
    print(f"saved {LAYOUT_FILE.relative_to(ROOT)}")


def dry_run():
    lay = layout()
    start = skills._joints()
    seen = balls(lay)
    print(f"{len(seen)} balls on the tray")
    for b in seen:
        p = plan_ball(b, lay, start) if b["box"] else None
        print(f"  {b['colour']} at ({b['x']:.0f}, {b['y']:.0f}, {b['z']:.0f}) -> {b['box'] or 'no box'}: "
              + ("reachable" if p else "NOT reachable" if b["box"] else "left"))
        for name, pose in (p[0] if p else []):
            print(f"     {name:6s} flange ({pose[0]:.0f}, {pose[1]:.0f}, {pose[2]:.0f})")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "plan"
    {"plan": dry_run, "teach": teach, "layout": teach_layout, "run": lambda: print(run())}[cmd]()
