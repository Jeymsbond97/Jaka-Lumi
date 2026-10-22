"""Self-check of the pose graph (manipulation/arm_route.py) with a fake arm and toy kinematics (no robot):
python tests/test_arm_route.py"""
import tempfile
from pathlib import Path

import numpy as np

from manipulation import arm_route, skills
from robot import arm, gripper, motion
from tasks import fetch
from vision import head_cam

fetch.STATE_FILE = Path(tempfile.mkdtemp()) / "lumi_task.json"     # never the real /dev/shm file
POSES = {"look": [0.0] * 6, "carry": [20.0, 0, 0, 0, 0, 0], "give": [40.0, 0, 0, 0, 0, 0],
         "wave_start": [0.0, -20, 0, 0, 0, 0], "wave": [0.0, -20, 20, 0, 0, 0], "ready": [0.0, 0, -20, 0, 0, 0],
         "tuck": [-20.0, 0, 0, 0, 0, 0]}
FAR = np.array([0.0, 0.0, 5000.0])                                  # the head far away: nothing near it
head = {"centre": FAR}
motion.poses = lambda: dict(POSES)
head_cam.head_centre = lambda: head["centre"]
gripper.state = lambda: {"holding": False, "ai": [160]}
arm_route.log = fetch.log = lambda *a: None


class FakeArm:
    """Joints in deg; toy forward kinematics: flange at 30 mm per degree of J1 / J2 / J3, never turned."""

    def __init__(self, joints):
        self.j, self.sent, self.programs = list(joints), [], []

    def __call__(self, name, **a):
        if name == "get_robot_state":
            return {"power": 1, "enable": 1, "errorCode": "0"}
        if name == "get_program_state":
            return {"programState": "idle", "errorCode": "0"}
        if name == "get_joint_pos":
            return {"joint_pos": list(self.j), "errorCode": "0"}
        if name == "kine_forward":
            j = a["jointPosition"]
            return {"cartPosition": [30 * j[0], 30 * j[1], 30 * j[2]] + list(skills.GRASP_RPY), "errorCode": "0"}
        if name == "get_data":
            return {"joint_actual_position": list(self.j), "inpos": True}
        if name == "joint_move":
            self.sent.append(list(a["jointPosition"]))
            self.j = list(a["jointPosition"])
            return {"errorCode": "0"}
        if name in ("get_loaded_program", "load_program", "play_program"):
            self.programs.append(name)
            return {"errorCode": "0", "programName": ""}
        raise AssertionError(f"unexpected arm command {name}")


def use(j):
    arm.cmd = FakeArm(j)
    return arm.cmd


def refused(reason, fn, *a, **k):
    try:
        fn(*a, **k)
    except arm_route.RouteError as e:
        assert e.args == reason, e.args
        return
    raise AssertionError(f"moved, expected {reason}")


edges = {frozenset(e) for e in arm_route.EDGES}

# ---------- every pair of poses: along the graph's edges, one joint move each ----------
for a in POSES:
    for b in POSES:
        fake = use(POSES[a])
        route = arm_route.goto(b)
        assert [a] + route == arm_route._path(a, b, POSES) and fake.sent == [POSES[n] for n in route], (a, b, route)
        assert all(frozenset(p) in edges for p in zip([a] + route, route)), (a, b, route)
        assert arm_route.where(fake.j) == b
use(POSES["give"])
assert arm_route.goto("look") == ["carry", "look"]                  # after giving: give -> carry -> look
assert arm_route.goto("give") == ["carry", "give"]                  # to give: look -> carry -> give
use(POSES["wave"])
assert arm_route.goto("tuck") == ["wave_start", "look", "tuck"]     # fold: through look

# ---------- after a wave the arm stays up; the next pick goes wave -> wave_start -> look first ----------
fake = use(POSES["wave"])
skills._prepare()
assert fake.sent == [POSES["wave_start"], POSES["look"]], fake.sent
fake = use(POSES["wave"])
fetch._pose("look")
assert fake.sent == [POSES["wave_start"], POSES["look"]], fake.sent

# ---------- an unknown pose near a known one: a checked joint move to it, then on ----------
near = [3.0, 2.0, -4.0, 5.0, 0.0, 0.0]                              # 5 deg from look (free drive)
assert arm_route.where(near) is None
fake = use(near)
assert arm_route.goto("carry") == ["look", "carry"] and fake.sent == [POSES["look"], POSES["carry"]], fake.sent
fake = use([20.5, 0, 0, 0, 0, 0])                                   # within EXACT_DEG of carry: straight on
assert arm_route.goto("give") == ["give"]

# ---------- far from every pose, or a move that passes the head: refused, nothing sent ----------
fake = use([60.0, 60.0, 0, 0, 0, 0])
refused(arm_route.UNKNOWN, arm_route.goto, "look")
try:
    fetch._pose("look")
    raise AssertionError("fetch moved from an unknown pose")
except fetch.FetchError as e:
    assert e.args == arm_route.UNKNOWN
assert fake.sent == []
fake = use([60.0, 60.0, 0, 0, 0, 0])                                # a task's own way back from the table: straight
assert arm_route.goto("look", leaf=True) == ["look"]
head["centre"] = np.array([300.0, 0.0, 0.0])                         # on the way look -> carry (flange x 0 -> 600)
for start in (POSES["look"], near, POSES["give"]):
    fake = use(start)
    refused(arm_route.NEAR_HEAD, arm_route.goto, "give" if start != POSES["give"] else "look")
    assert fake.sent == [], fake.sent
fake = use(POSES["look"])
assert arm_route.goto("wave") == ["wave_start", "wave"]              # another edge: clear of it
head["centre"] = None                                               # the head not measured: nothing moves
refused(arm_route.UNSURE, arm_route.goto, "look")
head["centre"] = FAR
POSES["give"] = [40.0, 0, 0, 0, 125.0, 0]                           # beyond J5's limit
fake = use(POSES["look"])
refused(arm_route.BLOCKED, arm_route.goto, "give")
assert fake.sent == []
POSES["give"] = [40.0, 0, 0, 0, 0, 0]
del POSES["wave_start"]
refused(arm_route.NOT_TAUGHT, arm_route.goto, "wave")               # no way to wave without wave_start
refused(arm_route.NOT_TAUGHT, arm_route.goto, "nowhere")
POSES["wave_start"] = [0.0, -20, 0, 0, 0, 0]

# ---------- Cobo π programs only from look; hand_shaking never ----------
fake = use(POSES["carry"])
refused(arm_route.NOT_AT_LOOK, arm_route.start_program, "arm_reach.jks")
fake = use(near)
refused(arm_route.NOT_AT_LOOK, arm_route.start_program, "arm_reach.jks")
fake = use(POSES["look"])
refused(arm_route.RETIRED, arm_route.start_program, "hand_shaking.jks")
assert fake.programs == []
arm_route.start_program("arm_reach.jks")
assert "play_program" in fake.programs
print("arm route ok")
