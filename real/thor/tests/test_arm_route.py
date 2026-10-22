"""Self-check of the pose graph (manipulation/arm_route.py) with a fake arm and toy kinematics (no robot):
python tests/test_arm_route.py"""
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

from manipulation import arm_route, skills
from robot import arm, gripper, motion
from tasks import fetch
from vision import head_cam

fetch.STATE_FILE = Path(tempfile.mkdtemp()) / "lumi_task.json"     # never the real /dev/shm file
POSES = {"look": [0.0] * 6, "carry": [20.0, 0, 0, 0, 0, 0], "give": [40.0, 0, 0, 0, 0, 0],
         "wave_out": [0.0, -20, 0, 0, 0, 0], "wave_start": [0.0, -20, 20, 0, 0, 0],
         "wave": [0.0, -20, 20, 0, 20, 0], "ready": [0.0, 0, -20, 0, 0, 0]}
FAR = np.array([0.0, 0.0, 5000.0])                                  # the head far away: nothing near it
head = {"centre": FAR}
motion.poses = lambda: dict(POSES)
head_cam.head_centre = lambda: head["centre"]
gripper.state = lambda: {"holding": False, "ai": [160]}
arm_route.log = fetch.log = lambda *a: None
motion.SETTLE_S = 0.05                                              # quick here; the pause itself is checked below


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
        if name == "get_motion_state":
            return {"queue": 0, "active_queue": 0, "errorCode": "0"}
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
assert arm_route.goto("look") == ["wave_start", "wave_out", "look"]  # fold: down to look
assert not any("tuck" in e for e in arm_route.EDGES)
use(POSES["look"])
assert arm_route.goto("wave_start") == ["wave_out", "wave_start"]   # up: never look -> wave_start directly
assert {"look", "wave_start"} not in [set(e) for e in arm_route.EDGES]

# ---------- after a wave the arm stays at wave_start; the next pick goes down through wave_out first ----------
fake = use(POSES["wave_start"])
skills._prepare()
assert fake.sent == [POSES["wave_out"], POSES["look"]], fake.sent
fake = use(POSES["wave_start"])
fetch._pose("look")
assert fake.sent == [POSES["wave_out"], POSES["look"]], fake.sent

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
assert arm_route.goto("wave") == ["wave_out", "wave_start", "wave"]  # other edges: clear of it
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
POSES["wave_start"] = [0.0, -20, 20, 0, 0, 0]

# ---------- every move to a stop, settled, then the next: SPEED empty, HOLD_SPEED holding, old accel, no blending ----


class QueueArm(FakeArm):
    """Queues joint moves like the controller: each get_data shows the next one done; stop_program empties the queue.
    `on_move(k)` / `on_poll()` run before the k-th move / a poll. log: (command, speed, accel, keys, time)."""

    def __init__(self, joints, on_move=None, on_poll=None):
        super().__init__(joints)
        self.queue, self.log, self.on_move, self.on_poll = [], [], on_move, on_poll

    def __call__(self, name, **a):
        self.log.append((name, a.get("speed"), a.get("accel"), set(a), time.time()))
        if name == "joint_move":
            if self.on_move:
                self.on_move(len(self.sent))
            self.sent.append(list(a["jointPosition"]))
            self.queue.append(list(a["jointPosition"]))
            return {"errorCode": "0"}
        if name == "get_data":
            if self.on_poll:
                self.on_poll()
            if self.queue:
                self.j = self.queue.pop(0)
            return {"joint_actual_position": list(self.j), "inpos": getattr(self, "inpos_always", False) or not self.queue}
        if name == "stop_program":
            self.queue.clear()
            return {"errorCode": "0"}
        if name == "get_motion_state":
            return {"queue": len(self.queue), "active_queue": len(self.queue), "errorCode": "0"}
        return super().__call__(name, **a)

    def moves(self):
        return [(s, acc, keys) for n, s, acc, keys, _ in self.log if n == "joint_move"]


def order(fake):
    return [e[0] for e in fake.log if e[0] in ("joint_move", "get_data")]


fake = arm.cmd = QueueArm(POSES["look"])
assert arm_route.goto("wave_start") == ["wave_out", "wave_start"] and fake.j == POSES["wave_start"]
route = motion.JOINT_SPEED[arm_route.SPEED]
keys = {"relFlag", "jointPosition", "speed", "accel"}                              # no tol: never blended
assert fake.moves() == [(route, route * motion.JOINT_ACCEL_FACTOR, keys)] * 2, fake.moves()
assert order(fake) == ["joint_move", "get_data", "joint_move", "get_data"], order(fake)
arrived = [e for e in fake.log if e[0] == "get_data"][0][4]
second = [e for e in fake.log if e[0] == "joint_move"][1][4]
assert second - arrived >= motion.SETTLE_S * 0.9, second - arrived                 # stood at wave_out first
fake = arm.cmd = QueueArm(POSES["look"])
arm_route.goto("wave_start", holding=True)
hold = motion.JOINT_SPEED[arm_route.HOLD_SPEED]
assert order(fake) == ["joint_move", "get_data", "joint_move", "get_data"], order(fake)
assert fake.moves() == [(hold, hold * motion.JOINT_ACCEL_FACTOR, keys)] * 2 and hold < route, fake.moves()

# STOP while a move is sent, while the arm runs it, or while it stands between two: stopped, nothing more sent
fake = arm.cmd = QueueArm(POSES["look"], on_move=lambda k: k == 1 and motion.stop())
try:
    arm_route.goto("wave_start")
    raise AssertionError("went on after STOP")
except motion.MotionError as e:
    assert str(e) == "stopped"
names = [e[0] for e in fake.log]
assert names[-1] == "stop_program" and names.count("joint_move") == 2 and fake.queue == [], names
fake = arm.cmd = QueueArm(POSES["look"], on_poll=motion.stop)
try:
    arm_route.goto("wave_start")
    raise AssertionError("went on after STOP")
except motion.MotionError as e:
    assert str(e) == "stopped" and fake.queue == [] and fake.j == POSES["look"], (e, fake.j)
fake = arm.cmd = QueueArm(POSES["look"])
fake.on_poll = lambda: threading.Timer(0.1, motion.stop).start()                 # pressed just after the arrival
motion.SETTLE_S = 0.5
try:
    arm_route.goto("wave_start")
    raise AssertionError("went on after STOP")
except motion.MotionError as e:
    assert str(e) == "stopped" and fake.sent == [POSES["wave_out"]], fake.sent
motion.SETTLE_S = 0.05


# queued (the wave's swings): all sent before any poll, the wait ends only at the end with the queue empty, though
# the arm passes the last pose before (inpos there too)
a_, b_ = POSES["wave_start"], POSES["wave"]
fake = arm.cmd = QueueArm(a_)
fake.inpos_always = True
motion.move_path([(b_, "normal"), (a_, "normal"), (b_, "normal"), (a_, "normal")], queued=True)
assert order(fake)[:5] == ["joint_move"] * 4 + ["get_data"] and fake.queue == [] and fake.j == a_, order(fake)
assert order(fake).count("get_data") >= 4, order(fake)
fake = arm.cmd = QueueArm(a_, on_move=lambda k: k == 2 and motion.stop())      # STOP while they are sent
try:
    motion.move_path([(b_, "normal"), (a_, "normal"), (b_, "normal"), (a_, "normal")], queued=True)
    raise AssertionError("went on after STOP")
except motion.MotionError as e:
    names = [e_[0] for e_ in fake.log]
    assert str(e) == "stopped" and names[-1] == "stop_program" and fake.queue == [] and "get_data" not in names, names


class SlowArm(QueueArm):
    """Runs the queued moves at `deg_s` (wall clock), far below the speed asked; `stall_at`: stops there for good."""

    def __init__(self, joints, deg_s, stall_at=None):
        super().__init__(joints)
        self.deg_s, self.stall_at, self.t = deg_s, stall_at, None

    def __call__(self, name, **a):
        if name == "get_data":
            now = time.time()
            step, self.t = self.deg_s * (now - (self.t or now)), now
            if self.queue and (self.stall_at is None or max(abs(x - y) for x, y in zip(self.j, self.stall_at)) > 1e-6):
                t = self.queue[0]
                d = np.clip(np.array(t) - self.j, -step, step)
                self.j = [float(v) for v in np.array(self.j) + d]
                if self.stall_at is not None and max(abs(x - y) for x, y in zip(self.j, self.stall_at)) < step:
                    self.j = list(self.stall_at)
                if np.allclose(self.j, t):
                    self.queue.pop(0)
            return {"joint_actual_position": list(self.j), "inpos": not self.queue}
        return super().__call__(name, **a)


extra, still = motion.EXTRA_S, motion.STILL_S
motion.EXTRA_S, motion.STILL_S = 0.0, 0.5
fake = arm.cmd = SlowArm(POSES["look"], deg_s=8.0)                  # 20 deg asked at 40 deg/s: planned 0.5 s, takes 2.5
motion.move_path([(POSES["wave_out"], "route"), (POSES["wave_start"], "route")])
assert fake.j == POSES["wave_start"] and fake.queue == [], fake.j
fake = arm.cmd = SlowArm(POSES["look"], deg_s=8.0, stall_at=[0.0, -20, 5, 0, 0, 0])   # stuck on the way: stopped
try:
    motion.move_path([(POSES["wave_out"], "route"), (POSES["wave_start"], "route")])
    raise AssertionError("waited on a stalled arm")
except motion.MotionError as e:
    assert "stopped before" in str(e) and fake.queue == [] and fake.log[-1][0] == "stop_program", (e, fake.log[-1])
motion.EXTRA_S, motion.STILL_S = extra, still

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
