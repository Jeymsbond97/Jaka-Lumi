"""manipulation/sort.py without the robot: which balls are taken and in which order, the fingers kept off touching
balls, the plan reaches them with the offline kinematics, a run sorts until STOP (balls put back later are sorted
too) and counts, refusals before anything moves. Run: .venv/bin/python tests/test_sort.py"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from manipulation import skills, sort
from robot import gripper, motion
from vision import calib

tmp = Path(tempfile.mkdtemp())
sort.LAYOUT_FILE, sort.TEACH_FILE = tmp / "layout.json", tmp / "teach.json"

# refused before anything moves when nothing is set up
for missing in ("The boxes aren't set up.", "I haven't learned how to hold a ball yet."):
    try:
        sort.run()
        raise AssertionError("run() went on without its set-up")
    except skills.SkillError as e:
        assert e.args[0] == missing, e.args
    if not sort.LAYOUT_FILE.exists():
        sort.LAYOUT_FILE.write_text(json.dumps({
            "tray": {"centre": [30.0, 470.0], "size": [280.0, 190.0]},
            "boxes": {"red": {"centre": [-250.0, 470.0], "rim_mm": -178.0},
                      "yellow": {"centre": [310.0, 470.0], "rim_mm": -178.0}},
            "colours": {"red": "red", "yellow": "yellow", "orange": "red"}}))

# a stand-in ball grasp: the fingers-down flange pose read from the robot on 2026-11-25 (free drive) and the grasp
# point the simulation uses (sim/sorting/build.py TCP, 130 mm across and 155 mm along the flange axis, turned -43.3 deg)
f = [44.7, 384.5, -18.4, 176.9, 8.0, -42.5]
R = calib.rpy_matrix(*f[3:])
a = np.radians(-43.3)
offset = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]]) @ [130.0, 0.0, 155.0]
sort.TEACH_FILE.write_text(json.dumps({"flange": f, "ball": [float(v) for v in R @ offset + np.array(f[:3])]}))
Rg, off = sort.grasp()
assert np.allclose(off, offset, atol=1e-6)
g = sort.flange_at([30.0, 470.0, -237.0], Rg)            # the taught centre lands where asked
assert np.allclose(calib.rpy_matrix(*g[3:]) @ off + g[:3], [30.0, 470.0, -237.0], atol=1e-6)
first = next(sort.hands())
assert np.allclose(first, Rg)                            # the taught (straight down) hand is tried first

# which balls count: on the tray, steady, sorted nearest first; a colour without a box is left
TABLE_TOP = -258.0
def ball(x, y, colour, seen=8, spread=3.0, name="sports ball"):
    return {"name": name, "names": [name], "x": x, "y": y, "top_mm": TABLE_TOP + 4 + 42.5, "colour": colour,
            "seen": seen, "spread": spread}
seen = [ball(60, 500, "yellow"), ball(0, 440, "red"), ball(-60, 450, "orange"), ball(90, 480, "blue"),
        ball(400, 470, "red"),                            # in the yellow box, not on the tray
        ball(30, 470, "red", seen=2),                     # not steady
        ball(-30, 500, "red", name="apple")]
lay = sort.layout()
got = sort.balls(lay, seen)
assert [(b["colour"], b["box"]) for b in got] == [("red", "red"), ("orange", "red"), ("blue", None),
                                                   ("yellow", "yellow")], got   # all free: nearest the arm base first
assert abs(got[0]["z"] - (TABLE_TOP + 4 + 21.25)) < 1e-6

# the plan reaches a ball at the tray's centre and both boxes (offline kinematics; the head check stood in)
skills.move_ok = lambda j0, j1: True
look = motion.nearest(motion.poses()["look"], motion.poses()["look"])
skills._joints = lambda: list(look)
for colour in ("red", "yellow"):
    p = sort.plan_ball({"x": 30.0, "y": 470.0, "z": TABLE_TOP + 25.25, "colour": colour, "box": colour}, lay, look)
    assert p is not None, f"no plan to the {colour} box"
    names = [n for n, _ in p[0]]
    assert names == ["above", "grasp", "lift", "drop"], names
    drop = p[0][3][1]
    centre = calib.rpy_matrix(*drop[3:]) @ off + drop[:3]
    box = lay["boxes"][colour]
    assert np.hypot(centre[0] - box["centre"][0], centre[1] - box["centre"][1]) < 1.0
    assert abs(centre[2] - (box["rim_mm"] + sort.DROP_ABOVE_RIM_MM)) < 1.0

# the jaws open square to the flange axis and to the fingers' side offset
J = sort.jaws()
assert abs(J @ [0, 0, 1]) < 1e-9 and abs(J @ [offset[0], offset[1], 0]) < 1e-6

# touching balls: the fingers come down across the pair, never onto the neighbour
A, B = {"x": 0.0, "y": 440.0}, {"x": 42.5, "y": 440.0}                  # touching, side by side across the table
u = (sort.grasp_hands(A, [B])[0] @ J)[:2]
assert abs(u[0]) < 0.6 * np.linalg.norm(u), u                           # the jaws open (mostly) along y, not into B
assert all(sort.clearance(A, R, [B]) is not None for R in sort.grasp_hands(A, [B]))
along_x = next(R for R in sort.hands() if abs((R @ J)[1]) < 0.05)        # a hand with the jaws along x
assert sort.clearance(A, along_x, [B]) is None                          # would land a finger on B: never tried

# a heap of seven touching balls: none of them has room for both fingers (every turn puts a finger against a
# neighbour, which is pushed aside), so a lone ball further from the arm goes first; the heap's balls still come,
# none is left out
heap = [ball(0, 440, "red")] + [ball(42.5 * np.cos(a), 440 + 42.5 * np.sin(a), "yellow")
                                for a in np.radians(range(0, 360, 60))]
got = sort.balls(lay, heap + [ball(100, 520, "red")])
assert got[0]["x"] == 100 and got[0]["room"] >= sort.CLEAR_MM, got[0]
assert all(b["room"] is not None and b["room"] < sort.CLEAR_MM for b in got[1:]), got
# a row of three: the end balls have room on their open side and come before the middle one
row = [ball(-42.5, 470, "red"), ball(0, 470, "yellow"), ball(42.5, 470, "red")]
got = sort.balls(lay, row)
assert all(b["room"] is not None for b in got)
assert got[-1]["x"] == 0 or got[-1]["room"] <= min(b["room"] for b in got), got

# a run goes on until STOP: three balls, then the tray is empty for a while, then two balls are put back, then one
# more; the blue one stays; STOP while waiting ends it with the counts
sort.WAIT_S = 0.001
script = {"looks": 0, "empty": 0}
later = [[ball(30, 470, "yellow"), ball(-40, 460, "red")], [ball(10, 500, "red")]]
left = [ball(0, 440, "red"), ball(60, 500, "yellow"), ball(-60, 450, "red"), ball(90, 480, "blue")]
moves = []


def look_tray(*a, **k):
    script["looks"] += 1
    if all(b["colour"] == "blue" for b in left):
        script["empty"] += 1
        if script["empty"] % 3 == 0:                                    # the owner puts balls back after a while
            if later:
                left[:0] = later.pop(0)
            else:
                skills.cancel()                                         # STOP while waiting
    return list(left)


skills.look = look_tray
skills.cancel = lambda: skills._cancel.set()
skills._prepare = lambda: moves.append("prepare")
skills._back_home = lambda: moves.append("home")
skills._line = lambda name, pose: moves.append(name)
motion.move_joints = lambda j, speed=None: moves.append("joints")
holding = {"v": False}


def close():
    holding["v"] = True
    moves.append("close")
    return {"ai": [2500.0], "holding": True}


def open_():
    if holding["v"]:
        held = next((b for b in left if b["colour"] != "blue"), None)
        if held is not None:
            left.remove(held)                                           # a held ball let go: it went into its box
    holding["v"] = False
    moves.append("open")
    return {"ai": [150.0], "holding": False}


gripper.close, gripper.open_ = close, open_
gripper.state = lambda: {"ai": [2500.0 if holding["v"] else 150.0], "holding": holding["v"]}
out = sort.run()
assert out == {"done": 6, "failed": 0, "stopped": True}, out
assert moves.count("close") == 6 and moves.count("home") == 6, moves
assert sort.state["stopped"] and sort.state["current"] is None and not sort.state["waiting"]
assert [b["colour"] for b in left] == ["blue"]

# after STOP nothing runs on its own: a new run starts clean
assert not later

# a ball missed twice is left where it lies and the run waits (it is not tried again and again); STOP ends it
left[:] = [ball(0, 440, "red")]
script.update(empty=0)
gripper.close = lambda: {"ai": [4150.0], "holding": False}


def look_missing(*a, **k):
    script["looks"] += 1
    if sort.state["failed"] >= 2:
        script["empty"] += 1
        if script["empty"] >= 3:
            skills.cancel()
    return list(left)


skills.look = look_missing
out = sort.run()
assert out == {"done": 0, "failed": 2, "stopped": True}, out

# misses in a row on different balls stop the run with an error
left[:] = [ball(0, 440, "red"), ball(90, 480, "red")]
skills.look = lambda *a, **k: list(left)
try:
    sort.run()
    raise AssertionError("went on after three misses")
except skills.SkillError as e:
    assert "3 balls in a row" in e.args[0], e.args
assert sort.state["failed"] == 3

print("test_sort: ok")
