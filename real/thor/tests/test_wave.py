"""Self-check of the wave (manipulation/wave.py) and that a greeting never moves the arm, with a fake arm, base, gripper
and camera (no robot): python tests/test_wave.py"""
import tempfile
import threading
import types
from pathlib import Path

import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import lumi
from manipulation import arm_route, skills, wave
from robot import agv, arm, gripper, motion
from tasks import fetch
from vision import head_cam

fetch.STATE_FILE = Path(tempfile.mkdtemp()) / "lumi_task.json"     # never the real /dev/shm file
lumi.BUSY_FILE = str(fetch.STATE_FILE.parent / "lumi_busy.json")       # nor the real busy file
LOOK = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
POSES = {"look": LOOK, "wave_out": [-50.0, 0.0, 0.0, 0.0, 0.0, 0.0], "wave_start": [-50.0, 0.0, 60.0, 0.0, 0.0, 0.0],
         "wave": [-50.0, 0.0, 60.0, 0.0, 21.7, 0.0]}
HEAD = np.array([-100.0, -200.0, 700.0])                               # mm, the head's turning centre in the toy arm
motion.poses = lambda: dict(POSES)
head_cam.head_centre = lambda: HEAD
skills.hand_sees = lambda: "unknown"                                # the camera can't tell: AI_1 decides
hand = {"holding": False}
gripper.state = lambda: {"holding": hand["holding"]}
base = {"move_status": "idle"}
agv.status = lambda: dict(base)
wave.log = arm_route.log = lambda *a: None
fetch._waist_turn = lambda: 0.0                                    # the waist at the front (never the body)
motion.SETTLE_S = 0.01                                              # quick here (tests/test_arm_route.py checks it)


class FakeArm:
    """Joints in deg; toy forward kinematics: flange at 10 mm per degree of J1 / J2 / J3, never turned."""

    def __init__(self, joints, enable=True):
        self.j, self.enable, self.sent = list(joints), enable, []

    def __call__(self, name, **a):
        if name == "get_robot_state":
            return {"power": 1, "enable": self.enable, "errorCode": "0"}
        if name == "get_program_state":
            return {"programState": "idle", "errorCode": "0"}
        if name == "get_joint_pos":
            return {"joint_pos": list(self.j), "errorCode": "0"}
        if name == "kine_forward":
            j = a["jointPosition"]
            return {"cartPosition": [10 * j[0], 10 * j[1], 10 * j[2], 0.0, 0.0, 0.0], "errorCode": "0"}
        if name == "get_data":
            return {"joint_actual_position": list(self.j), "inpos": True}
        if name == "get_motion_state":
            return {"queue": 0, "active_queue": 0, "errorCode": "0"}
        if name == "joint_move":
            self.sent.append(list(a["jointPosition"]))
            self.j = list(a["jointPosition"])
            return {"errorCode": "0"}
        raise AssertionError(f"unexpected arm command {name}")


def use(fake):
    arm.cmd = fake
    return fake


def refused(reason):
    try:
        wave.wave()
    except wave.WaveError as e:
        assert e.args == reason, e.args
        return
    raise AssertionError(f"waved, expected {reason}")


# ---------- from look: up through wave_out, 2 swings, the arm stays at wave_start; every move clear of the head ------
a = use(FakeArm(LOOK))
started, up = [], []
wave.wave(on_start=lambda: started.append(len(a.sent)), on_up=lambda: up.append(len(a.sent)))
assert started == [0]                                               # said before the first move
assert up == [2]                                                    # at wave_start, before the swings (person stop off)
top, swing = POSES["wave_start"], POSES["wave"]
assert wave.SWINGS == 2
assert a.sent == [POSES["wave_out"], top] + [swing, top] * wave.SWINGS, a.sent
for j0, j1 in zip([LOOK] + a.sent, a.sent):
    assert arm_route.profile(j0, j1, HEAD)[0] >= arm_route.HEAD_CLEAR_MM, (j0, j1)
assert arm_route.profile(LOOK, top, HEAD)[0] < arm_route.HEAD_CLEAR_MM     # straight up from look would pass the head
assert {"look", "wave_start"} not in [set(e) for e in arm_route.EDGES]       # so there is no such edge
a.sent.clear()
wave.wave()                                                         # asked again while up: only the swings
assert a.sent == [swing, top] * wave.SWINGS, a.sent
a.sent.clear()
a.j = list(swing)                                                   # stopped at wave: back to wave_start, then swings
wave.wave()
assert a.sent == [top] + [swing, top] * wave.SWINGS, a.sent
names = []                                                          # the way up as goto, move by move; then the swings
arm.cmd = lambda name, **k: (names.append((name, k.get("speed"), "tol" in k)), a(name, **k))[1]   # as goto
a.j = list(LOOK)
wave.wave()
sent = [e for e in names if e[0] in ("joint_move", "get_data")]
route, swing_s = motion.JOINT_SPEED[arm_route.SPEED], motion.JOINT_SPEED[wave.SWING_SPEED]
arrive = motion.JOINT_SPEED[wave.ARRIVE_SPEED]                      # into wave_start at the route speed too
assert arrive == route and wave.ARRIVE_SPEED == "route"
assert sent == [("joint_move", route, False), ("get_data", None, False), ("joint_move", arrive, False),
                ("get_data", None, False)] + \
    [("joint_move", swing_s, False)] * 2 * wave.SWINGS + [("get_data", None, False)], sent      # swings back to back
assert wave.SWING_SPEED == "quick"
arm.cmd = a
a.j = list(top)
a.sent.clear()
assert arm_route.goto("look") == ["wave_out", "look"]               # the way down
assert a.sent == [POSES["wave_out"], LOOK], a.sent

# ---------- a taught pose whose way passes the head: refused before anything moves ----------
POSES["wave_out"] = [-15.0, 0.0, 40.0, 0.0, 0.0, 0.0]
a = use(FakeArm(LOOK))
refused(wave.NEAR_HEAD)
assert a.sent == []
POSES["wave_out"] = [-50.0, 0.0, 0.0, 0.0, 0.0, 0.0]

# ---------- holding something: refused (task state, or AI_1 when the camera can't tell) ----------
a = use(FakeArm(LOOK))
fetch.STATE_FILE.write_text('{"status": "idle", "holding": true, "held_object": "cup"}')
refused(wave.HOLDING)
fetch.STATE_FILE.unlink()
hand["holding"] = True
refused(wave.HOLDING)
hand["holding"] = False
skills.hand_sees = lambda: "object"
refused(wave.HOLDING)
skills.hand_sees = lambda: "unknown"
assert a.sent == []

# ---------- from carry (empty hand): the least joint travel checked; straight to wave_start passes the head ----------
POSES["carry"] = [30.0, 0.0, 0.0, 0.0, 0.0, 0.0]
a = use(FakeArm(POSES["carry"]))
wave.wave()
assert a.sent[:3] == [POSES["wave_out"], top, swing], a.sent
assert arm_route.profile(POSES["carry"], top, HEAD)[0] < arm_route.HEAD_CLEAR_MM
del POSES["carry"]

# ---------- an unknown start (after free drive: the wrist the other way round): joins by a checked move; power ----------
a = use(FakeArm([-249.1, -90.9, -29.1, 14.6, -83.8, -33.0]))
wave.wave()
assert a.sent[0][1:3] == LOOK[1:3] and swing in a.sent, a.sent
use(FakeArm(LOOK, enable=False))
refused(wave.OFF)
base["move_status"] = "running"
use(FakeArm(LOOK))
refused(wave.DRIVING)
base["move_status"] = "idle"
fetch.STATE_FILE.write_text('{"status": "running", "holding": false}')
refused(wave.BUSY)
fetch.STATE_FILE.unlink()
del POSES["wave"]
refused(wave.NOT_TAUGHT)
POSES["wave"] = swing
del POSES["wave_out"]
refused(wave.NEAR_HEAD)                                              # the ways left (look -> wave -> ...) pass the head
POSES["wave_out"] = [-50.0, 0.0, 0.0, 0.0, 0.0, 0.0]
assert arm.cmd.sent == []                                            # nothing sent for any refusal

# ---------- the assistant: a greeting sends no arm command; a wave asked while holding is refused aloud ----------
calls = []
arm.cmd = lambda name, **a: calls.append(name) or {}
said = []
lumi.mouth = types.SimpleNamespace(say=lambda text, **k: said.append(text))
lumi.log = lambda msg: None
v = lumi.Vision.__new__(lumi.Vision)
v.know = lambda track: (types.SimpleNamespace(talking=False), None)
L = lumi.Lumi.__new__(lumi.Lumi)
L.vision, L.current, L.lang, L.voice_until = v, None, "en", 0.0
L.brain = types.SimpleNamespace(reset=lambda: None)
L.turn_head = lambda *a: None
L.modes = types.SimpleNamespace(wave=True)
L.skill_thread = None
L.mission_running = lambda: False
track = types.SimpleNamespace(id=1, distance=0.8, angle=-20.0, greeted=False)
L.greet(track)
for th in threading.enumerate():                                    # a wave started beside the greeting would show
    if th is not threading.main_thread():
        th.join(10)
assert track.greeted and said == [lumi.GREETING] and calls == [], calls
fetch.STATE_FILE.write_text('{"status": "idle", "holding": true}')
hand["holding"] = True                                              # the hand checked again: really held
said.clear()
assert L.wave(("Okay!", "네!")) is False and said == [wave.HOLDING[0]]
L.lang = "ko"
said.clear()
assert L.wave() is False and said == [wave.HOLDING[1]]
said.clear()
assert L.wave(quiet=True) is False and said == []                    # a goodbye wave refused: no words about it
hand["holding"] = False                                             # a stale "holding", the hand empty (2026-10-23
real_wave, wave.wave = wave.wave, lambda on_start=None, on_up=None: None  # 17:43): checked again, not refused for holding
said.clear()
assert L.wave() is True and said == [] and not fetch.state()["holding"], said
held, go = threading.Event(), threading.Event()                    # the same request twice (16:21, typed): one wave
wave.wave = lambda on_start=None, on_up=None: (held.set(), go.wait(10))
first = threading.Thread(target=L.wave)
first.start()
held.wait(10)
assert L.wave() is False                                            # asked again while it waves: refused, no second
go.set()
first.join()
assert L.wave() is True                                             # ... and the next one after it ended runs
wave.wave = real_wave
fetch.STATE_FILE.unlink()

# ---------- the arm moves while the words are said, never after them (wave, open / close) ----------
gate, order = threading.Event(), []


def slow_say(text, **k):                                            # speech that ends only when the test says so
    order.append(("say", text))
    gate.wait(30)


lumi.mouth = types.SimpleNamespace(say=slow_say)
L.lang = "en"
wave.wave = lambda on_start=None, on_up=None: (on_start(), order.append("move"))
done = []
th = threading.Thread(target=lambda: done.append(L.wave(("Okay!", "네!"))))
th.start()
th.join(10)
assert done == [True] and "move" in order, (done, order)            # waved with the words still being said
gate.set()
wave.wave = real_wave
gate.clear(), order.clear()
L.arm_pose = lambda target: order.append("gripper") or True
L.base_off = lambda *a, **k: False
L.arm_off = lambda: False
L.brain = types.SimpleNamespace(history=[])
th = threading.Thread(target=L.quick_command, args=("open your hand", ("arm", "open")))
th.start()
th.join(1)
assert "gripper" in order and th.is_alive(), order                  # the gripper started while the words go on
gate.set()
th.join(5)
del L.arm_pose, L.base_off, L.arm_off
lumi.mouth = types.SimpleNamespace(say=lambda text, **k: said.append(text))

# ---------- "bye bye" to the person in view: a (quiet) wave beside the goodbye; else only the goodbye ----------
waves = []
L.wave = lambda **k: waves.append(k)
L.brain = types.SimpleNamespace(reset=lambda: None, farewell=lambda text, lang: "Bye!")
L.speak_abort, L.mission_hold, L.closing_pending = None, None, None
L.traveling = lambda: False
v.present = lambda t: True
for text, current, wanted in (("bye bye", track, 1), ("바이바이", track, 1), ("Bay bay, Lumi", track, 1), ("잘 가", track, 1),
                              ("bye bye", None, 0), ("thank you, bye", track, 0), ("안녕히 계세요", track, 0)):
    waves.clear()
    L.current = current
    L.end_conversation(text)
    for th in threading.enumerate():
        if th is not threading.main_thread():
            th.join(5)
    assert len(waves) == wanted and all(w == {"quiet": True} for w in waves), (text, waves)
v.present = lambda t: False                                         # said while walking out of view: no wave
waves.clear()
L.current = track
L.end_conversation("bye bye")
assert waves == []
assert calls == [], calls
print("wave ok")
