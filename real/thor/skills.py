"""Pick and place with the torso camera, the arm and the gripper: find an object, plan every pose, check it with
the controller's IK, then move. Nothing moves unless the whole plan (pick and place) passes.

The grasp is the one taught in grasp_teach.json: the flange orientation with the fingers around a cup, and the
point between the fingers where the cup's axis sits 4 cm below the rim. Down from 10 cm above, close, lift.

    python skills.py plan [cup] [--to X Y]     # dry run: object, place spot, every waypoint with IK joints
    python skills.py pick cup                  # pick it up and hold it 3 cm above the table
    python skills.py move cup [--to X Y]       # pick it up and put it down at X Y (mm, base frame) or a free spot

Ctrl+C or any motion error stops the arm; the gripper keeps its state.
"""
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

import arm
import calib
import camview
import gripper
import motion
import objects

HERE = Path(__file__).resolve().parent
TEACH = json.loads((HERE / "grasp_teach.json").read_text())
GRASP_RPY = TEACH["flange"][3:]                  # deg, flange orientation with the fingers around a cup
GRASP_OFFSET = np.array(TEACH["tcp_offset_flange"])   # mm, cup axis 4 cm below the rim, in the flange frame
BELOW_RIM_MM = 40.0                              # grasp this far below the object's top
ABOVE_MM = 100.0                                 # approach / retreat height over the grasp pose
LIFT_MM = 30.0                                   # first lift after closing, then check the grip again
PLACE_EXTRA_MM = 3.0                             # put down this much higher than it was picked (same table)
MIN_WIDTH, MAX_WIDTH = 45.0, 84.0                # mm; fingertip entry is 88 mm, the fingers close to ~62
FRAMES = 8                                       # camera frames looked at by find()
FRAME_GAP_S = 0.2                                # s between them
MIN_SEEN = 5                                     # an object must be in this many frames, at the same place
CLUSTER_MM = 40.0                                # detections closer than this (x, y) are the same object
SPREAD_MM = 20.0                                 # a detection further than this from the median -> unstable
IGNORE = {"dining table"}                        # classes that are never objects to pick or avoid
FREE_MM = 110.0                                  # a place spot keeps this distance from other objects' centres
PLACE_X = (-240.0, -100.0)                       # mm; place spots stay in this zone (picks proven to work there)
PLACE_Y = (560.0, 630.0)
SPOT_DX = (-60, -90, -120, 60, 90, 120)          # mm; candidate offsets from the pick point, tried in this order
SPOT_DY = (0, -20, -40, 20)
RETRIES = 4                                      # the controller now and then answers with nothing: ask again
RETRY_S = 0.2
OPEN_AI = gripper.CLOSED_AI                      # AI_1 below this after opening = released

_held = {}                                       # what pick() holds: {"top_mm"} for place()


class SkillError(RuntimeError):
    """A plain spoken-style reason why the skill cannot go on."""


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------- seeing ----------
def look(frames=FRAMES):
    """Detections over several frames, grouped by position: [{name, colour, x, y, top_mm, width_mm, seen, spread}]
    with medians of the detections that agree with the majority name. Raises when the camera is not live."""
    camview.want(objects.CAMERA)
    groups, live = [], 0
    for i in range(frames):
        d = objects.latest()
        if d["age_s"] is not None and d["age_s"] < objects.STALE_S:
            live += 1
            for o in d["objects"]:
                if o["name"] in IGNORE or not o.get("position_mm"):
                    continue
                x, y = o["position_mm"][:2]
                g = next((g for g in groups if np.hypot(x - g[0]["x"], y - g[0]["y"]) < CLUSTER_MM), None)
                row = {"name": o["name"], "colour": o.get("colour"), "x": x, "y": y, "top_mm": o.get("top_mm"),
                       "width_mm": o.get("width_mm")}
                if g:
                    g.append(row)
                else:
                    groups.append([row])
        if i < frames - 1:
            time.sleep(FRAME_GAP_S)
    if live < frames // 2:
        raise SkillError("My camera isn't working right now.")
    out = []
    for g in groups:
        name = statistics.mode(r["name"] for r in g)
        rows = [r for r in g if r["name"] == name]
        med = {k: statistics.median(r[k] for r in rows if r[k] is not None) if any(r[k] is not None for r in rows)
               else None for k in ("x", "y", "top_mm", "width_mm")}
        spread = max(np.hypot(r["x"] - med["x"], r["y"] - med["y"]) for r in rows)
        out.append({"name": name, "colour": statistics.mode(r["colour"] for r in rows), **med, "seen": len(rows),
                    "spread": round(float(spread), 1)})
    return sorted(out, key=lambda o: np.hypot(o["x"], o["y"]))


def find(name="cup", colour=None, seen=None):
    """The nearest stable `name` (of `colour`) the torso camera sees, from look() (or `seen`, its result)."""
    seen = look() if seen is None else seen
    what = f"{colour + ' ' if colour else ''}{name}"
    hits = [o for o in seen if o["name"] == name and (colour is None or o["colour"] == colour)]
    if not hits:
        raise SkillError(f"I can't see a {what}.")
    steady = [o for o in hits if o["seen"] >= MIN_SEEN and o["spread"] <= SPREAD_MM and o["top_mm"] is not None]
    if not steady:
        raise SkillError(f"I'm not sure where the {what} is, it keeps changing.")
    return steady[0]


# ---------- geometry ----------
def flange_for(x, y, z):
    """Flange pose that puts the taught grasp point at (x, y, z) mm with the taught orientation."""
    R = calib.rpy_matrix(*GRASP_RPY)
    f = np.array([x, y, z]) - R @ GRASP_OFFSET
    return [float(v) for v in f] + list(GRASP_RPY)


def up(pose, dz):
    return [pose[0], pose[1], pose[2] + dz] + list(pose[3:])


def plan_pick(obj):
    """Waypoints [(name, flange pose)] to pick `obj` (a find() result). Refuses objects of the wrong width."""
    w = obj.get("width_mm")
    if w is None or w > MAX_WIDTH:
        raise SkillError(f"The {obj['name']} is too big for my hand.")
    if w < MIN_WIDTH:
        raise SkillError(f"The {obj['name']} is too small for me to hold.")
    grasp = flange_for(obj["x"], obj["y"], obj["top_mm"] - BELOW_RIM_MM)
    return [("above", up(grasp, ABOVE_MM)), ("grasp", grasp), ("lift", up(grasp, LIFT_MM))]


def plan_place(x, y, top_mm, start=None):
    """Waypoints to put down what was picked with its top at `top_mm`, centred at (x, y). `start`: the flange
    pose it is held at now (adds the lift to carry height there)."""
    down = up(flange_for(x, y, top_mm - BELOW_RIM_MM), PLACE_EXTRA_MM)
    steps = [("carry", [start[0], start[1], down[2] - PLACE_EXTRA_MM + ABOVE_MM] + list(start[3:]))] if start else []
    return steps + [("above place", up(down, ABOVE_MM)), ("place", down), ("release up", up(down, ABOVE_MM))]


def spots(pick_xy, others):
    """Candidate place spots (x, y) near the pick point, inside the place zone, FREE_MM from every other object."""
    out = []
    for dx in SPOT_DX:
        for dy in SPOT_DY:
            x, y = pick_xy[0] + dx, pick_xy[1] + dy
            if not (PLACE_X[0] <= x <= PLACE_X[1] and PLACE_Y[0] <= y <= PLACE_Y[1]):
                continue
            if all(np.hypot(x - o["x"], y - o["y"]) >= FREE_MM for o in others):
                out.append((x, y))
    return out


# ---------- checking with the controller ----------
def _ask(name, **args):
    """arm.cmd with retries for empty answers / dropped connections."""
    for _ in range(RETRIES):
        try:
            r = arm.cmd(name, **args)
        except (ConnectionError, OSError):
            r = {}
        if "errorCode" in r and not (name == "kine_inverse" and r["errorCode"] == "0" and "jointPosition" not in r):
            return r                     # ("0" without the joints happens too: ask again)
        time.sleep(RETRY_S)
    raise SkillError("The arm controller is not answering.")


def _joints():
    for _ in range(RETRIES):
        try:
            return motion.joints()
        except (motion.MotionError, ConnectionError, OSError):
            time.sleep(RETRY_S)
    raise SkillError("The arm controller is not answering.")


def ik_chain(waypoints, start_joints):
    """IK for each waypoint, each from the previous answer. Rows [name, pose, joints, error]; stops at the first
    error (error None = passed)."""
    rows, ref = [], list(start_joints)
    for name, pose in waypoints:
        r = _ask("kine_inverse", jointPosition=ref, cartPosition=list(pose))
        if r["errorCode"] != "0":
            rows.append([name, pose, None, "no IK solution"])
            return rows
        j = r["jointPosition"]
        err = None
        try:
            motion.check(j)
        except motion.MotionError as e:
            err = str(e)
        flips = [f"J{i + 1} turns {j[i] - ref[i]:+.0f} deg" for i in motion.FULL_TURN if abs(j[i] - ref[i]) > motion.MAX_FLIP]
        err = err or (flips[0] if flips else None)
        rows.append([name, pose, j, err])
        if err:
            return rows
        ref = j
    return rows


def ready_joints():
    """`ready` as move_joints will reach it from here (J1 / J4 / J6 nearest the current angles)."""
    return motion.nearest(motion.poses()["ready"], _joints())


def checked(waypoints, start_joints):
    rows = ik_chain(waypoints, start_joints)
    if rows[-1][3]:
        log(f"plan refused at {rows[-1][0]}: {rows[-1][3]}")
        raise SkillError("I can't reach it safely.")
    return rows


def plan_move(obj, to=None, seen=()):
    """Full pick + place plan from `ready`: (place (x, y), IK rows). `to` None = first free spot that passes IK."""
    pick = plan_pick(obj)
    start = ready_joints()
    if to is not None:
        tries = [tuple(to)]
    else:
        others = [o for o in seen if np.hypot(o["x"] - obj["x"], o["y"] - obj["y"]) >= CLUSTER_MM]
        tries = spots((obj["x"], obj["y"]), others)
        if not tries:
            raise SkillError("I can't find a free place to put it.")
    last = None
    for xy in tries:
        rows = ik_chain(pick + plan_place(*xy, obj["top_mm"], start=pick[-1][1]), start)
        if not rows[-1][3]:
            return xy, rows
        last = (xy, rows)
        log(f"spot ({xy[0]:.0f}, {xy[1]:.0f}) refused at {rows[-1][0]}: {rows[-1][3]}")
    if to is not None:
        raise SkillError("I can't reach that place safely.")
    raise SkillError("I can't find a free place I can reach.")


# ---------- moving ----------
def _prepare():
    if gripper.state()["ai"][0] > OPEN_AI:
        log("opening the gripper")
        gripper.open_()
    if max(abs(a - b) for a, b in zip(_joints(), ready_joints())) > 1.0:
        log("going to ready")
        motion.go("ready")


def _line(name, pose):
    log(f"{name}: to ({pose[0]:.0f}, {pose[1]:.0f}, {pose[2]:.0f})")
    motion.move_linear(target=pose, speed="slow")


def _give_up(reason):
    """Open, back up 100 mm, ready, raise. Only used while the object is at (or just above) the table."""
    log(f"{reason}: opening, backing up")
    gripper.open_()
    motion.move_linear(delta=[0, 0, ABOVE_MM], speed="slow")
    motion.go("ready")
    raise SkillError(reason)


def _do_pick(obj, waypoints):
    above, grasp, lift = (p for _, p in waypoints)
    _prepare()
    _line("above", above)
    _line("grasp", grasp)
    log("closing")
    s = gripper.close()
    log(f"AI_1 {s['ai'][0]:.0f} holding {s['holding']} finger sensor {s['object_in_front']}")
    if not s["holding"]:
        _give_up("I missed it.")
    _line("lift", lift)
    s = gripper.state()
    log(f"AI_1 {s['ai'][0]:.0f} holding {s['holding']}")
    if not s["holding"]:
        _line("slipped, back down", grasp)
        _give_up("It slipped out of my hand.")
    _held["top_mm"] = obj["top_mm"]


def _do_place(waypoints):
    for name, pose in waypoints[:-1]:
        _line(name, pose)
    log("opening")
    s = gripper.open_()
    log(f"AI_1 {s['ai'][0]:.0f}")
    if s["ai"][0] > OPEN_AI:
        raise SkillError("My hand did not open.")           # stay put: lifting now would drag the object
    _held.clear()
    _line(*waypoints[-1])
    log("going to ready")
    motion.go("ready")


def _guarded(fn, *a):
    """Run a motion sequence; on a motion error or Ctrl+C stop the arm and re-raise."""
    try:
        return fn(*a)
    except (motion.MotionError, KeyboardInterrupt, ConnectionError, OSError):
        motion.stop()
        log("stopped")
        raise


def pick(name="cup", colour=None):
    """Find, plan, pick up and hold `name` 3 cm above the table."""
    obj = find(name, colour)
    log(f"found {obj['colour']} {obj['name']} at ({obj['x']:.0f}, {obj['y']:.0f}) top {obj['top_mm']:.0f} "
        f"width {obj['width_mm']:.0f}")
    waypoints = plan_pick(obj)
    checked(waypoints, ready_joints())
    _guarded(_do_pick, obj, waypoints)
    log("holding it")
    return obj


def place(x, y):
    """Put down what pick() holds at (x, y), then go to ready."""
    if "top_mm" not in _held:
        raise SkillError("I'm not holding anything I picked.")
    waypoints = plan_place(x, y, _held["top_mm"], start=motion.tcp())
    checked(waypoints, _joints())
    _guarded(_do_place, waypoints)


def move_object(name="cup", colour=None, to=None):
    """Pick `name` up and put it at `to` (x, y) or at a free spot. Everything is planned before anything moves."""
    seen = look()
    obj = find(name, colour, seen)
    log(f"found {obj['colour']} {obj['name']} at ({obj['x']:.0f}, {obj['y']:.0f}) top {obj['top_mm']:.0f}")
    xy, rows = plan_move(obj, to, seen)
    log(f"placing at ({xy[0]:.0f}, {xy[1]:.0f}); plan of {len(rows)} waypoints passed")
    waypoints = [(r[0], r[1]) for r in rows]
    _guarded(_do_pick, obj, waypoints[:3])
    _guarded(_do_place, waypoints[3:])
    log("done")
    return xy


def _dry_run(name, to):
    seen = look()
    for o in seen:
        log(f"seen {o['colour']} {o['name']} at ({o['x']:.0f}, {o['y']:.0f}) top {o['top_mm']} "
            f"width {o['width_mm']} in {o['seen']}/{FRAMES} frames, spread {o['spread']} mm")
    obj = find(name, None, seen)
    log(f"picking {obj['colour']} {obj['name']} at ({obj['x']:.0f}, {obj['y']:.0f}) top {obj['top_mm']:.0f}")
    try:
        xy, rows = plan_move(obj, to, seen)
        log(f"place spot ({xy[0]:.0f}, {xy[1]:.0f})")
    except SkillError as e:
        log(f"no plan: {e}")
        return
    for n, pose, j, err in rows:
        print(f"  {n:12s} flange {[round(v, 1) for v in pose[:3]]}  joints {[round(v, 1) for v in j]}  "
              f"{'FAIL ' + err if err else 'ok'}")


if __name__ == "__main__":
    a = sys.argv[1:]
    to = None
    if "--to" in a:
        i = a.index("--to")
        to, a = (float(a[i + 1]), float(a[i + 2])), a[:i] + a[i + 3:]
    try:
        if a[:1] == ["plan"]:
            _dry_run(a[1] if len(a) > 1 else "cup", to)
        elif a[:1] == ["pick"]:
            pick(a[1] if len(a) > 1 else "cup")
        elif a[:1] == ["move"]:
            move_object(a[1] if len(a) > 1 else "cup", to=to)
        else:
            sys.exit(__doc__)
    except SkillError as e:
        sys.exit(f"refused: {e}")
    except motion.MotionError as e:
        sys.exit(f"motion failed: {e}")
    except KeyboardInterrupt:
        sys.exit("stopped")
