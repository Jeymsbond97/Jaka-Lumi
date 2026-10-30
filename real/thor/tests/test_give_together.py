"""Self-check of "give me your hand" with a waist turn (tasks/fetch.py reach, _give_turning): the waist and the arm
move together (the waist command goes out before the arm route ends, the arm starts before the waist is there), the
sweep is checked with the hand at every pose of the route over the whole turn (refused when only the route's pose
would hit something), and STOP ends both. Fake body, arm and map, no robot: python tests/test_give_together.py"""
import json
import math
import tempfile
import threading
import time
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from robot import motion
from tasks import fetch

tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"
fetch.CALIB_FILE = tmp / "base_axis.json"
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": 0.0, "arm_xy_in_base_m": [0.0, 0.0], "waist_deg": 0.0}))
fetch.log = lambda *a: None

body = {"pos": [0.0, 0.0, 0.0, 0.0]}                 # lift, waist, head yaw, head pitch
events = []                                          # (time, what)
CHUNK_S = 0.15                                       # s one fake waist move takes


def moveto(pos, **kw):
    events.append((time.time(), "waist start", pos[1]))
    time.sleep(CHUNK_S)
    body["pos"] = list(pos)
    events.append((time.time(), "waist end", pos[1]))
    return {"status": 0}


fetch.head.moveto = moveto
fetch.head.status = lambda: list(body["pos"])
fetch.skills.moved = lambda *a, **k: None
fetch.skills.objects.base_from_camera = lambda: None        # no depth: the lidar / map check decides
fetch.head_cam.base_from_head = lambda yaw, pitch: None
fetch.agv.pose = lambda: (0.0, 0.0, 0.0)
fetch.motion.poses = lambda: {"give": [2.0] * 6, "give_pre": [1.0] * 6, "look": [0.0] * 6}
fetch._person_point = lambda: ((0.0, 600.0, 0.0), 100.0)
fetch._reach_to_hand = lambda *a: events.append((time.time(), "hand"))
joints = {"now": [0.0] * 6}
fetch.skills._joints = lambda: list(joints["now"])
fetch.arm_points_3d = lambda j=None: [(500.0 * math.cos(math.radians(45.0 * (joints["now"] if j is None else j)[0])),
                                       500.0 * math.sin(math.radians(45.0 * (joints["now"] if j is None else j)[0])),
                                       0.0)] * 3   # j0 0 / 1 / 2 (look, give_pre, give): the hand at 0 / 45 / 90 deg
SEQ = [("give_pre", [1.0] * 6), ("give", [2.0] * 6)]
fetch.arm_route.plan = lambda target, holding=False, leaf=False, now=None: list(SEQ)
arm_stop = threading.Event()


def arm_move(seq, speed=None, holding=False):
    events.append((time.time(), "arm start"))
    for _, j in seq:
        if arm_stop.wait(0.2):
            raise motion.MotionError("stopped")
        joints["now"] = list(j)
    events.append((time.time(), "arm end"))


fetch.arm_route.move = arm_move
fetch.skills.cancel = lambda: arm_stop.set()
fetch.agv.cancel = lambda: None
obstacle = {"at": None}
fetch.agv.clearance = lambda x, y: 0.0 if obstacle["at"] and math.dist((x, y), obstacle["at"]) < 0.05 else 1.0


def when(what):
    return [e[0] for e in events if e[1] == what]


def reset():
    events.clear()
    body["pos"] = [0.0, 0.0, 0.0, 0.0]
    joints["now"] = [0.0] * 6
    arm_stop.clear()


# ---------- clear: waist and arm together, the head stays on the person ----------
reset()
fetch.reach(30.0, look=30.0)
fetch._thread.join(10)
st = fetch.state()
assert st["status"] == "done", st
w0, arm0, arm1, w1 = when("waist start")[0], when("arm start")[0], when("arm end")[0], when("waist end")[-1]
assert w0 <= arm0 < arm1, events                     # the waist command went out first, before the arm route ended
assert arm0 < w1, events                             # the arm started before the waist got there
assert len(when("waist start")) == math.ceil(30.0 / fetch.WAIST_STEP_DEG), events
assert abs(body["pos"][1] - 30.0) < 1e-6 and abs(body["pos"][2]) < 1e-6, body   # waist 30, head yaw 30 - 30 = 0
assert events[-1][1] == "hand" and joints["now"] == [2.0] * 6

# ---------- only the give pose, turned, meets something: refused, nothing moves ----------
reset()
obstacle["at"] = (500.0 * math.cos(math.radians(120.0)) / 1000.0, 500.0 * math.sin(math.radians(120.0)) / 1000.0)
assert fetch.turn_hits(30.0) is None                 # the old check (the hand where it is now) sees nothing
fetch.reach(30.0, look=30.0)
fetch._thread.join(10)
st = fetch.state()
assert st["status"] == "failed" and not events and joints["now"] == [0.0] * 6, (st, events)
obstacle["at"] = None

# ---------- STOP while both move: the arm stops now, the waist after the move it is in ----------
reset()
fetch.reach(40.0, look=40.0)
time.sleep(0.1)
assert when("arm start") and when("waist start"), events
t = time.time()
fetch.end()
assert time.time() - t < 1.0 and not fetch._busy()
time.sleep(3 * CHUNK_S)                              # nothing more is sent after the move in progress
assert arm_stop.is_set() and not when("arm end"), events
assert len(when("waist start")) <= 2 and all(s < t + 0.05 for s in when("waist start")), events
assert fetch.state()["status"] == "stopped" and body["pos"][1] < 40.0

# ---------- no turn: only the arm (the plain route) ----------
reset()
posed = []
real_pose, fetch._pose = fetch._pose, lambda name, **k: posed.append(name)
fetch.reach(0.0)
fetch._thread.join(5)
assert posed == ["give"] and not when("waist start") and fetch.state()["status"] == "done"
fetch._pose = real_pose
print("give together ok (ordering, route sweep refusal, stop ends both, no turn)")
