"""manipulation/sort.py without the robot: which balls are taken, the plan reaches them with the offline kinematics,
a run sorts them and counts, refusals before anything moves. Run: .venv/bin/python tests/test_sort.py"""
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
                                                   ("yellow", "yellow")], got   # nearest the arm base first
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

# a run: three sortable balls, each picked and let go once; the blue one stays; counts on the state
left = [ball(0, 440, "red"), ball(60, 500, "yellow"), ball(-60, 450, "red"), ball(90, 480, "blue")]
moves = []
skills.look = lambda *a, **k: list(left)
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
    if holding["v"] and left and left[0]["colour"] != "blue":
        left.pop(0)                                       # a held ball let go: it went into its box
    holding["v"] = False
    moves.append("open")
    return {"ai": [150.0], "holding": False}
gripper.close, gripper.open_ = close, open_
gripper.state = lambda: {"ai": [2500.0 if holding["v"] else 150.0], "holding": holding["v"]}
out = sort.run()
assert out == {"done": 3, "failed": 0}, out
assert moves.count("close") == 3 and moves.count("home") == 3, moves
assert sort.state["left"] == 0 and sort.state["current"] is None

# a ball missed three times in a row stops the run
left[:] = [ball(0, 440, "red")]
gripper.close = lambda: {"ai": [4150.0], "holding": False}
try:
    sort.run()
    raise AssertionError("went on after three misses")
except skills.SkillError as e:
    assert "3 balls in a row" in e.args[0], e.args
assert sort.state["failed"] == 3

print("test_sort: ok")
