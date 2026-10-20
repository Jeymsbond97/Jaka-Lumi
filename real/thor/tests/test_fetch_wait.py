"""Self-check of a mission's wait steps (tasks/fetch.py `_wait`, `proceed`, `instruct`, receive with a waiting time)
with fake base, arm and gripper (no robot, no network): python tests/test_fetch_wait.py"""
import tempfile
import threading
import time
from pathlib import Path

from manipulation import skills
from tasks import fetch

tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"           # never the real /dev/shm file
fetch.CALIB_FILE = tmp / "fetch_calib.json"         # never the robot's measured values (waist at the front)
fetch.LOG_LINES = 1000
fetch.WAIT_POLL_S = fetch.GIVE_POLL_S = 0.01
fetch.RECEIVE_DI_S = 0.05
MARKERS = ["p1", "p3", "p6", "exit", "home"]

calls, said = [], []
hand = {"holding": False, "front": False}
fetch.agv.markers = lambda: MARKERS
fetch.agv.pose = lambda: (0.0, 0.0, 0.0)
fetch.agv.go = lambda m: (calls.append(("go", m)), (True, "OK"))[1]
fetch.agv.go_point = lambda x, y, th: (calls.append(("go_point",)), (True, "OK"))[1]
fetch.agv.cancel = lambda: calls.append(("cancel",))
fetch._wait_drive = lambda watch_holding=False, again=None, goal=None: None
fetch._lift_to = lambda mm: None
fetch._pose = lambda name, speed=None: calls.append(("pose", name))
fetch._line_holding = lambda name: calls.append(("line", name))
fetch._in_hand = lambda: hand["holding"]
fetch.motion.poses = lambda: {"look": [0] * 6, "give": [0] * 6, "tuck": [0] * 6}
fetch.gripper.state = lambda: {"holding": hand["holding"], "closed": hand["holding"], "object_in_front": hand["front"]}
fetch.gripper.open_ = lambda: (calls.append(("open",)), hand.update(holding=False), fetch.gripper.state())[-1]
fetch.gripper.close = lambda wait=True: (calls.append(("close",)), hand.update(holding=hand["front"]),
                                         fetch.gripper.state())[-1]
skills.surface_points = lambda pts, guess_z=-400.0, **kw: [None] * len(pts)    # never the live depth file
skills.hand_sees = lambda: "unknown"
fetch.head_cam.base_from_head = lambda yaw, pitch: None                        # no head camera checks
fetch.objects.latest = lambda camera="torso": {"age_s": None, "objects": [], "head_pose": None}
fetch.camview.want = lambda name: None
fetch.head.moveto = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("real head / lift move in a test"))
fetch.head.status = lambda: [75.0, -15.0, 0.0, 0.0]
skills.arm.cmd = lambda *a, **kw: (_ for _ in ()).throw(AssertionError(f"real arm command in a test: {a}"))
say = lambda en, ko: said.append(en)
P = lambda **k: k


def start(steps):
    calls.clear()
    said.clear()
    hand.update(holding=False, front=False)
    fetch._state.update(status="idle", holding=False, step="")
    fetch.run_steps(steps, say)


def end():
    fetch._thread.join(5)
    assert not fetch._thread.is_alive()
    return fetch.state()


def until(cond, s=2.0):
    t0 = time.time()
    while not cond():
        assert time.time() - t0 < s, "timed out"
        time.sleep(0.01)


drives = lambda: [c[1] for c in calls if c[0] == "go"]

# ---------- "go to p3 and stay there": the mission ends there, waiting (new commands are taken as usual) ----------
start([P(do="go", to="p3"), P(do="wait", s=None)])
st = end()
assert st["status"] == "waiting" and st["step"] == "waiting at p3" and st["waiting"]["for"] == "stay", st
assert drives() == ["p3"] and said[-1] == "I'll wait here.", (calls, said)
start([P(do="go", to="p1")])                                                 # a new command after it: as usual
assert end()["status"] == "done" and not fetch.state()["waiting"]

# ---------- "go to the exit, wait there, then go home": waits until "go on" ----------
start([P(do="go", to="exit"), P(do="wait", s=None), P(do="go", to="home")])
until(lambda: (fetch.state().get("waiting") or {}).get("for") == "go on")
time.sleep(0.1)
assert drives() == ["exit"] and fetch.state()["step"] == "waiting at exit", calls
fetch.proceed()
st = end()
assert st["status"] == "done" and drives() == ["exit", "home"] and not st["waiting"], (st, calls)

# ---------- a time: waited, someone talking pauses the clock ----------
t0 = time.time()
start([P(do="wait", s=0.3), P(do="go", to="p1")])
st = end()
assert time.time() - t0 >= 0.3 and drives() == ["p1"] and st["status"] == "done", (st, calls)
t0 = time.time()
start([P(do="go", to="p3"), P(do="wait", s=0.3), P(do="go", to="p1")])
until(lambda: fetch.state().get("waiting"))
assert fetch.state()["waiting"]["at"] == "p3" and fetch.state()["waiting"]["end"] > time.time()
fetch.pause()
time.sleep(0.4)
assert drives() == ["p3"], calls                                              # paused: the time does not run out
fetch.resume()
st = end()
assert time.time() - t0 >= 0.65 and drives() == ["p3", "p1"], (time.time() - t0, calls)
start([P(do="wait", s=5.0), P(do="go", to="p1")])                             # "go on" ends a timed wait too
until(lambda: fetch.state().get("waiting"))
fetch.proceed()
assert end()["status"] == "done" and drives() == ["p1"]

# ---------- an instruction from the person at the place: read there, done there, then the rest ----------
try:
    fetch.instruct([P(do="go", to="p1")])
    raise AssertionError("an instruction taken while not waiting for one")
except fetch.FetchError:
    pass
start([P(do="go", to="p6"), P(do="wait", s=2.0, until="instruction"), P(do="go", to="home")])
until(lambda: (fetch.state().get("waiting") or {}).get("for") == "instruction")
assert said[-1] == "I'll wait here. Tell me what I should do.", said
for bad in ([P(do="give")],                                                   # nothing in the hand
            [P(do="go", to="p1"), P(do="wait", s=60.0, until="instruction")],  # another person's wait: no
            [P(do="go", to="p9")]):                                           # not on the map
    try:
        fetch.instruct(bad)
        raise AssertionError(f"instruction taken: {bad}")
    except fetch.FetchError:
        pass
fetch.instruct([P(do="go", to="p1"), P(do="say", text="hello from p6"), P(do="go", to="here")])
st = end()
assert st["status"] == "done" and drives() == ["p6", "p1", "p6", "home"], (st, calls)    # "here" = p6 for them
assert "hello from p6" in said and [s["do"] for s in st["task"]["steps"]] == ["go", "wait", "go", "say", "go", "go"]
start([P(do="go", to="p6"), P(do="wait", s=0.2, until="instruction"), P(do="go", to="home")])
st = end()                                                                     # nobody: said, then the rest
assert st["status"] == "done" and drives() == ["p6", "home"] and "Nobody told me what to do, I'll go on." in said

# ---------- "wait until someone gives you a cup": the hand held out longer; nobody: failed there, hand open ----------
start([P(do="go", to="p3"), P(do="receive", object="cup", wait_s=0.3), P(do="go", to="p1")])
until(lambda: (fetch.state().get("waiting") or {}).get("for") == "person")
assert fetch.state()["waiting"]["object"] == "cup" and fetch.state()["waiting"]["at"] == "p3"
st = end()
assert st["status"] == "failed" and drives() == ["p3"] and ("close",) not in calls and not st["waiting"], (st, calls)
assert said[-1] == "Nobody gave me the cup." and ("pose", "look") in calls, said
fetch.RECEIVE_WAIT_S = 0.2                                                     # a plain receive would give up
start([P(do="go", to="p3"), P(do="receive", object="cup", wait_s=5.0), P(do="go", to="p1")])
until(lambda: fetch.state().get("waiting"))
time.sleep(0.4)                                                                # longer than RECEIVE_WAIT_S would allow
hand["front"] = True
until(lambda: fetch.state()["step"] == "receiving: waiting for okay")
fetch.release_now()
st = end()
assert st["status"] == "holding" and st["holding"] and drives() == ["p3", "p1"], (st, calls)
fetch.RECEIVE_WAIT_S = 30.0

# ---------- stop while waiting ----------
start([P(do="go", to="exit"), P(do="wait", s=None), P(do="go", to="home")])
until(lambda: fetch.state().get("waiting"))
fetch.stop()
assert end()["status"] == "stopped" and drives() == ["exit"]
print("fetch wait ok")
