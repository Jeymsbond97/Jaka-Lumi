"""Self-check of the head during a fetch (tasks/fetch.py _aim_head): once the object or the place is found the head
turns to it and stays on it while the base turns, for the pick and the put down; assistant/lumi.py does not turn
the head to people meanwhile. Fake head, base and head camera (no robot): python tests/test_fetch_head_aim.py"""
import math
import tempfile
import time
from pathlib import Path

import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from manipulation import skills
from tasks import fetch
from assistant import lumi

tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"           # never the real /dev/shm file
fetch.CALIB_FILE = tmp / "fetch_calib.json"         # arm frame = base frame, the waist at the front
fetch.CALIB_FILE.write_text('{"arm_yaw_in_base_deg": 0.0, "arm_xy_in_base_m": [0.0, 0.0], "waist_deg": 0.0}')
fetch.DRIVE_POLL_S = 0.01
fetch.HEAD_AIM_EVERY_S = 0.0

body = [0.0, 0.0, 0.0, fetch.HEAD_LOW_PITCH]        # lift, waist, head yaw, head pitch
moves = []                                          # head yaw of every body move


def moveto(pos, vel=None, acc=None, timeout=None):
    moves.append(round(pos[2]))
    body[:] = [float(p) for p in pos]


fetch.head.status = lambda: list(body)
fetch.head.moveto = moveto
fetch.camview.want = lambda name: None
skills.moved = lambda *a, **kw: None
pose = [0.0, 0.0, 0.0]                              # map x, y (m), theta (rad)
fetch.agv.pose = lambda: tuple(pose)
fetch.agv.cancel = lambda: None


def base_from_head(yaw, pitch):
    """A head camera at the arm origin: yaw 0 looks along arm +y, + yaw turns it left (counter-clockwise)."""
    s, c = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    T = np.eye(4)
    T[:3, :3] = np.array([[c, s, 0.0], [0.0, 0.0, -1.0], [-s, c, 0.0]]).T   # columns: right, down, forward
    return T


fetch.head_cam.base_from_head = base_from_head
bearing = lambda x, y: math.degrees(math.atan2(-x, y))   # + left of arm +y


def near(a, b, tol=1.0):
    return abs(a - b) <= tol


# a new run: no target, the head is lumi.py's (a person's) to turn
fetch._clear()
assert not fetch.aiming()
heads = []
lumi.head.turn = lambda yaw, pitch=None: heads.append(round(yaw))
L = lumi.Lumi.__new__(lumi.Lumi)
L.turn_head(20)
time.sleep(0.2)
assert heads == [20], heads

# the torso camera found the cup at (-300, 600) (the pick: _reach): the head turns to it
cup = {"x": -300.0, "y": 600.0, "top_mm": -250.0}
fetch._aim_head(cup)
assert fetch.aiming() and near(body[2], bearing(-300, 600)), body
# lumi.py's focus on a person, a greeting, a voice: the head stays on the cup
heads.clear()
L.turn_head(-40)
L.turn_head(0, force=True)
time.sleep(0.2)
assert heads == [], heads

# a look again (_see_again, _look_at ahead) keeps the head on the cup, not ahead of the waist
assert fetch._look_at(0.0, lambda: "seen") == "seen"
assert near(body[2], bearing(-300, 600)), body

# the base turns left to face it (+26.6 deg): the head turns back with it, staying on the cup
step = math.atan2(300, 600) / 10
polls = {"n": 0}


def status():
    polls["n"] += 1
    if polls["n"] <= 10:
        pose[2] += step
        return {"move_status": "running", "current_pose": {"x": 0.0, "y": 0.0, "theta": pose[2]}}
    return {"move_status": "succeeded", "current_pose": {"x": 0.0, "y": 0.0, "theta": pose[2]}}


fetch.agv.status = status
moves.clear()
fetch._wait_drive()
assert len(moves) >= 2 and all(b < a for a, b in zip(moves, moves[1:])), moves     # several small turns back
x, y = fetch.arm_frame(fetch._aim["world"])
assert near(bearing(x, y), 0.0) and abs(body[2]) <= fetch.HEAD_AIM_DEG, (x, y, body)

# the pick: the head turned away (head_hits checked a turn's sweep) comes back onto the cup before the arm moves
body[2] = 60.0
picked = []
skills._held.clear()
skills._guarded = lambda fn, *a: fn(*a)
skills._do_pick = lambda obj, wp, ja: picked.append(body[2])
fetch._pick({"x": x, "y": y, "top_mm": -250.0}, [], [0.0] * 6)
assert len(picked) == 1 and near(picked[0], 0.0), picked
assert not fetch.aiming()                            # in the hand: the head is free again

# the put down: the head turns to the spot before the arm goes there
placed = []
skills._held.update(yaw=0.0)
skills.plan_place = lambda x, y, top, yaw=0.0: [("above", [x, y, top + 100.0, 0, 0, 0]), ("place", [x, y, top, 0, 0, 0])]
fetch._line_rows = lambda target, label, start=None: [[label, target, [0.0] * 6, None]]
skills.ik_chain = lambda wp, j: [[n, p, [0.0] * 6, None] for n, p in wp]
fetch.motion.move_linear = lambda target=None, **kw: None
skills._do_place = lambda rows: placed.append(body[2])
fetch._pose = lambda name, holding=False, leaf=False: None
assert fetch._place_at([(-200.0, 650.0)], -320.0) is True
assert len(placed) == 1 and near(placed[0], bearing(-200, 650)), placed
assert fetch.aiming()

# the task ends (head_ahead) or a STOP: the head is lumi.py's again
fetch.head_ahead()
assert not fetch.aiming() and body[2] == 0.0, body
fetch._aim_head(cup)
fetch._stop.set()
assert not fetch.aiming()
fetch._clear()
heads.clear()
L.turn_head(-40)
time.sleep(0.2)
assert heads == [-40], heads
print("fetch head aim: ok")
