"""Self-check of tasks/fetch.py with fake base, arm and gripper (no robot, no network): python tests/test_fetch.py"""
import json
import math
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

from manipulation import skills
from tasks import fetch
from vision import calib

tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"           # never the real /dev/shm file
fetch.CALIB_FILE = tmp / "fetch_calib.json"
fetch.DRIVE_POLL_S = fetch.GIVE_POLL_S = 0.01
fetch.ASK_EVERY_S, fetch.ASK_WAIT_S = 0.01, 0.05
MARKERS = ["p1", "home"]

# ---------- validate / describe ----------
ok = {"object": "apple", "colour": None, "source": {"marker": "p1"}, "dest": {"marker": "home"}, "finish": "hold"}
assert fetch.validate(ok, MARKERS) == []
assert fetch.validate({**ok, "source": "here", "dest": {"x": 1.0, "y": -0.4, "theta": 1.57}}, MARKERS) == []
assert fetch.validate({**ok, "object": "laptop"}, MARKERS)
assert fetch.validate({**ok, "colour": "teal"}, MARKERS)
assert "p9" in fetch.validate({**ok, "source": {"marker": "p9"}}, MARKERS)[0]
assert fetch.validate({**ok, "dest": None}, MARKERS) == ["Where should I bring it?"]
assert fetch.validate({k: v for k, v in ok.items() if k != "dest"}, MARKERS) == ["Where should I bring it?"]
assert fetch.validate({**ok, "finish": "throw"}, MARKERS)
assert fetch.validate({k: v for k, v in ok.items() if k != "source"}, MARKERS) == []     # no source = here

assert fetch.describe(ok) == "Take the apple from p1, bring it to home and hold it."
assert fetch.describe({**ok, "source": "here", "colour": "red", "finish": "place"}) == \
    "Take the red apple from here, bring it to home and put it on the table."
assert fetch.describe({**ok, "source": {"x": 1, "y": 2, "theta": 0}, "dest": "here"}) == \
    "Take the apple from the point I was shown, bring it here and hold it."
assert fetch.describe(ok, "ko") == "p1 위치에서 사과를 가져와서 home 위치로 가져가 들고 있을게요."
assert fetch.describe({**ok, "object": "cup", "colour": "red", "finish": "place"}, "ko") == \
    "p1 위치에서 빨간 컵을 가져와서 home 위치로 가져가 테이블에 내려놓을게요."

# ---------- base shift geometry ----------
for yaw in (0.0, 90.0, -135.0, 30.0):
    for theta in (0.0, 1.2):
        obj = (fetch.PICK_ZONE_CENTRE[0] + 80, fetch.PICK_ZONE_CENTRE[1] - 120)   # 144 mm off, under MAX_SHIFT
        x, y, th = fetch.shift_target(obj, (2.0, -1.0, theta), yaw)
        move_b = fetch._rot(-math.degrees(theta)) @ [x - 2.0, y + 1.0]           # base move in the base frame
        obj_b = fetch._rot(yaw) @ (np.subtract(obj, fetch.PICK_ZONE_CENTRE) / 1000)
        after_b = obj_b - move_b                                                   # the object moves against the base
        assert np.allclose(after_b, 0) and th == theta, (yaw, theta, after_b)
        # measure-axis sees the object move by -base_move (in the arm frame) and gets the yaw back
        seen = fetch._rot(-yaw) @ (-np.array([0.1, 0.0])) * 1000
        assert abs(fetch.yaw_from_shift((0, 0), seen, (0.1, 0.0)) - yaw) < 1e-6 or abs(yaw) == 180

# yaw from several objects with a small turn on the way (the 2026-10-14 run turned 1.1 deg on a straight drive)
for yaw in (-60.0, 10.0, 95.0):
    R, mv, dth = fetch._rot(yaw), np.array([0.099, 0.001]), math.radians(1.1)
    pts = [np.array(q) for q in ((-60.0, 720.0), (175.0, 905.0), (720.0, 1950.0))]
    pairs = []
    for q in pts:                                  # exact rigid motion of the base about its own centre
        pb = R @ q
        c, s_ = math.cos(-dth), math.sin(-dth)
        pb2 = np.array([[c, -s_], [s_, c]]) @ (pb - mv * 1000)
        pairs.append((tuple(q), tuple(R.T @ pb2)))
    assert abs(fetch.yaw_from_motion(pairs, mv, dth) - yaw) < 0.5, (yaw, fetch.yaw_from_motion(pairs, mv, dth))

far = fetch.shift_target((fetch.PICK_ZONE_CENTRE[0] + 1000, fetch.PICK_ZONE_CENTRE[1]), (0, 0, 0), 0.0)
assert abs(math.hypot(far[0], far[1]) - fetch.MAX_SHIFT_M) < 1e-9                 # one shift is at most 0.30 m

# ---------- fake base, arm, gripper and camera ----------
calls = []
CUP = {"name": "apple", "colour": "red", "x": -150.0, "y": 600.0, "top_mm": -260.0, "width_mm": 70.0,
       "seen": 8, "spread": 1.0}
hand = {"holding": False, "closed": False}
base = {"pose": (0.0, 0.0, 0.0), "polls": 0, "on_poll": None}
found = {"obj": CUP}
reach = {"ok": True}


def fake_status():
    base["polls"] += 1
    if base["on_poll"]:
        base["on_poll"]()
    return {"move_status": "running" if base["polls"] % 3 else "succeeded", "charge_state": base.get("charging", False)}


def fake_reachable(obj, start=None):
    calls.append(("ik",))
    return skills.plan_pick(obj) if reach["ok"] else None


fetch.agv.markers = lambda: MARKERS
fetch.agv.pose = lambda: base["pose"]
fetch.agv.status = fake_status
fetch.agv.go = lambda m: (calls.append(("go", m)), (True, "OK"))[1]
fetch.agv.go_point = lambda x, y, th: (calls.append(("go_point", round(x, 3), round(y, 3))), (True, "OK"))[1]
fetch.agv.cancel = lambda: calls.append(("cancel",))
fetch.motion.go = lambda name, *a, **k: calls.append(("pose", name))
fetch.motion.stop = lambda: calls.append(("arm stop",))
fetch.motion.poses = lambda: {"tuck": [0] * 6, "ready": [0] * 6, "carry": [0] * 6, "look": [0] * 6}
fetch.motion.tcp = lambda: [0.0] * 3 + tilt["rpy"]                    # the flange as the fake kine_forward says
skills._joints = lambda: [0.0] * 6
skills.home_joints = lambda: [0.0] * 6
up_rpy = list(skills.GRASP_RPY)
tilt = {"rpy": up_rpy}
skills._ask = lambda name, **a: {"errorCode": "0", "cartPosition": [0, 0, 0] + tilt["rpy"]}
fetch.gripper.state = lambda: {**hand, "ai": [3500 if hand["holding"] else 160], "di": [int(hand["holding"])]}
fetch.gripper.open_ = lambda: (calls.append(("open",)), hand.update(holding=False, closed=False))
skills.find = lambda name, colour=None, seen=None: (calls.append(("find", name)), found["obj"])[1] if found["obj"] \
    else (_ for _ in ()).throw(skills.SkillError("I can't see a thing."))
skills.reachable_pick = fake_reachable
skills.look = lambda frames=None: []


def fake_pick(obj, wp):
    calls.append(("pick", obj["name"]))
    hand.update(holding=True, closed=True)
    skills._held.update(top_mm=obj["top_mm"], x=obj["x"], y=obj["y"])


def fake_place(wp):
    calls.append(("place",))
    hand.update(holding=False, closed=False)
    skills._held.clear()


skills._do_pick = fake_pick
skills._do_place = fake_place
skills._line = lambda name, pose: calls.append(("line", name))
fetch.motion.move_linear = lambda target=None, **kw: calls.append(("line", "straight"))
skills.on_table = lambda spots, table: []                                 # no live depth frames in a test
surface = {"z": None}                                                     # what the fake depth camera sees
skills.surface_heights = lambda pts, guess_z=-400.0: [surface["z"]] * len(pts)
body = {"lift": 75.0}
fetch.head.status = lambda: [body["lift"], -15.0, 0.0, 0.0]
fetch.head.moveto = lambda pos, **kw: (calls.append(("lift", pos[0])), body.update(lift=pos[0]))
skills.arm.cmd = lambda *a, **kw: (_ for _ in ()).throw(AssertionError(f"real arm command in a test: {a}"))
skills.ik_chain = lambda wp, j: [[n, p, [0] * 6, None] for n, p in wp]


def run(fn, *a):
    calls.clear()
    fn(*a)
    fetch._thread.join(5)
    assert not fetch._thread.is_alive()
    return fetch.state()


def reset():
    fetch._state.update(status="idle", holding=False, step="")
    base["polls"], base["on_poll"] = 0, None
    found["obj"], reach["ok"] = CUP, True
    hand.update(holding=False, closed=False)
    fetch.HOLD_CHECK_S = 1.0
    if fetch.CALIB_FILE.exists():
        fetch.CALIB_FILE.unlink()


poses = lambda: [c[1] for c in calls if c[0] == "pose"]

# ---------- happy fetch: hold, then place ----------
reset()
st = run(fetch.start, ok)
assert st["status"] == "holding" and st["holding"], st
names = [c[0] if c[0] != "pose" else c[1] for c in calls]
order = ["look", "go", "find", "ik", "pick", "line", "line", "go"]   # look; pick, up, straight to carry; drive
it = iter(names)
assert all(any(n == want for n in it) for want in order), names                   # these steps, in this order
assert [c for c in calls if c[0] == "go"] == [("go", "p1"), ("go", "home")]
assert names[names.index("pick"):].count("ready") == 0                             # pick -> carry, not by ready
try:
    fetch.give()
    raise AssertionError("gave without a taught give pose")
except fetch.FetchError:
    pass
st = run(fetch.place)
assert st["status"] == "done" and not st["holding"] and ("place",) in calls and poses()[-1] == "look", (st, calls)

# ---------- a drive that turns on the spot without getting anywhere is cancelled ----------
reset()
real_status = fetch.agv.status
spin = {"t": 0.0}
fetch.agv.status = lambda: (spin.update(t=spin["t"] + 0.7),
                            {"move_status": "running", "current_pose": {"x": 1.0, "y": 2.0, "theta": spin["t"] % 1}})[1]
fetch.STUCK_S, fetch.DRIVE_POLL_S = 0.3, 0.05
st = run(fetch.start, ok)
assert st["status"] == "failed" and "way there" in st["log"][-1] and ("cancel",) in calls, st
fetch.agv.status, fetch.STUCK_S, fetch.DRIVE_POLL_S = real_status, 30.0, 0.01

# ---------- a table 10 cm higher: lift up before the pick, back down before driving ----------
reset()
surface["z"], body["lift"] = -303.0, 75.0
st = run(fetch.start, ok)
lifts = [c[1] for c in calls if c[0] == "lift"]
assert st["status"] == "holding" and lifts[:2] == [175.0, 75.0], (lifts, calls)    # at p1 up for the pick, down to drive
assert calls.index(("lift", 175.0)) < next(i for i, c in enumerate(calls) if c[0] == "pick")
surface["z"] = -1060.0                                                       # the floor: never fitted
assert not fetch._fit_lift(-1060.0) and body["lift"] == 75.0
st = run(fetch.place)                                                        # done: back to the usual lift
assert st["status"] == "done" and body["lift"] == 75.0, (st, body)
body["lift"], found["obj"] = 175.0, None                                      # raised and nothing in view ...
found_after = {"n": 0}
real_find = skills.find
def find_low(name, colour=None, seen=None):
    found_after["n"] += 1
    if body["lift"] != 75.0:
        raise skills.SkillError("I can't see a thing.")
    return CUP
skills.find = find_low
reset()
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
assert st["status"] == "holding" and found_after["n"] == 2 and ("lift", 75.0) in calls, (st, calls)   # ... look low
skills.find = real_find
surface["z"] = None
fetch._set(holding=False, status="idle")

# ---------- holding: bring it somewhere else and keep holding it ----------
reset()
run(fetch.start, {**ok, "source": "here", "dest": "here"})
st = run(fetch.carry_to, {"marker": "p1"})
assert st["status"] == "holding" and st["holding"] and [c for c in calls if c[0] == "go"] == [("go", "p1")], (st, calls)
try:
    fetch.carry_to({"marker": "p9"})
    raise AssertionError("unknown place accepted")
except fetch.FetchError:
    pass
fetch._set(holding=False, status="idle")                                          # the state file too

# ---------- from here, put it on the table; progress is spoken ----------
reset()
spoken = []
st = run(fetch.start, {**ok, "source": "here", "finish": "place"}, lambda en, ko: spoken.append(en))
assert st["status"] == "done" and ("place",) in calls and [c for c in calls if c[0] == "go"] == [("go", "home")], calls
assert "I've got it." in spoken and "I'm here." in spoken, spoken

# ---------- not found: every lift here, then all the way round, failed ----------
reset()
found["obj"] = None
st = run(fetch.start, ok)
turns = [c for c in calls if c[0] == "go_point"]
assert st["status"] == "failed" and "looked all around" in st["log"][-1], (st, calls)
assert len(turns) == fetch.SEARCH_TURNS and not any(c[0] == "pick" for c in calls), calls
assert {c[1] for c in calls if c[0] == "lift"} >= {250.0, 0.0}, calls                # top and bottom lift tried
# ---------- not found on the charger: no turning ----------
reset()
found["obj"], base["charging"] = None, True
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
assert st["status"] == "failed" and not any(c[0] == "go_point" for c in calls), calls
base["charging"] = False
# ---------- found after one turn ----------
reset()
looks = {"n": 0}
real_find2 = skills.find
def find_after_turn(name, colour=None, seen=None):
    if not any(c[0] == "go_point" for c in calls):
        raise skills.SkillError("I can't see a thing.")
    return CUP
skills.find = find_after_turn
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
skills.find = real_find2
assert st["status"] == "holding" and sum(c[0] == "go_point" for c in calls) >= 1, (st, calls)
# ---------- put down: no table here, a free spot after a turn; seen from look, not from carry ----------
real_on_table = skills.on_table
skills.on_table = lambda spots, table: list(spots)[:1] if any(c[0] == "go_point" for c in calls) else []
skills._held.update(base=None)
st = run(fetch.place)
skills.on_table = real_on_table
names = [c[1] if c[0] == "pose" else c[0] for c in calls]
assert st["status"] == "done" and ("place",) in calls and names.index("go_point") < names.index("place"), (st, calls)

# ---------- out of reach, base axis not measured: no shift, ask, then failed ----------
reset()
reach["ok"] = False
st = run(fetch.start, ok)
assert st["status"] == "failed" and not any(c[0] == "go_point" for c in calls), calls
assert any("move it closer" in l for l in st["log"]) and poses()[-1] == "look"

# ---------- out of reach with the axis measured: SHIFT_TRIES shifts, then ask ----------
reset()
reach["ok"] = False
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -89.2}))
st = run(fetch.start, ok)
assert st["status"] == "failed" and sum(c[0] == "go_point" for c in calls) == fetch.SHIFT_TRIES, calls

# ---------- give: nobody takes it -> keep holding; a pull -> open ----------
fetch.motion.poses = lambda: {"tuck": [0] * 6, "ready": [0] * 6, "carry": [0] * 6, "look": [0] * 6, "give": [0] * 6}
fetch.GIVE_WAIT_S = 0.3
reset()
st = run(fetch.start, ok)
assert st["status"] == "holding", st
st = run(fetch.give)                                                       # nobody says thank you: kept
assert st["status"] == "holding" and st["holding"] and ("open",) not in calls, (st, calls)
assert calls.count(("line", "straight")) == 2 and "ready" not in poses()          # carry -> give -> carry, straight
fetch.GIVE_WAIT_S = 5.0
threading.Timer(0.2, fetch.release_now).start()                            # "thank you" / Release
st = run(fetch.give)
assert st["status"] == "done" and not st["holding"] and ("open",) in calls, (st, calls)
fetch.motion.poses = lambda: {"tuck": [0] * 6, "ready": [0] * 6, "carry": [0] * 6, "look": [0] * 6}

# ---------- another process holds it: give / place here take it over ----------
reset()
skills._held.clear()
fetch.STATE_FILE.write_text(json.dumps({"status": "holding", "step": "holding", "task": ok, "holding": True, "log": [],
                                        "since": 0, "held": {"top_mm": -260.0, "x": -150.0, "y": 600.0,
                                                             "base": [0.0, 0.0, 0.0]}}))
hand.update(holding=True, closed=True)
st = run(fetch.place)
assert st["status"] == "done" and ("place",) in calls, (st, calls)

# ---------- stop while driving ----------
reset()
base["on_poll"] = lambda: fetch.stop() if base["polls"] == 2 else None
st = run(fetch.start, ok)
assert st["status"] == "stopped", st
after = calls[calls.index(("cancel",)):]
assert not any(c[0] in ("pose", "go", "go_point", "pick", "open") for c in after), after

# ---------- dropped while driving ----------
reset()
base["on_poll"] = lambda: hand.update(holding=False) if base["polls"] == 5 else None
fetch.HOLD_CHECK_S = 0
st = run(fetch.start, ok)
assert st["status"] == "failed" and not st["holding"] and "dropped" in st["log"][-1], st
assert ("cancel",) in calls

# ---------- tilt check ----------
tilted = calib.rpy_matrix(30, 0, 0) @ calib.rpy_matrix(*up_rpy)                  # turned 30 deg about base x
ry = math.degrees(math.asin(-tilted[2, 0]))
tilt["rpy"] = [math.degrees(math.atan2(tilted[2, 1], tilted[2, 2])), ry, math.degrees(math.atan2(tilted[1, 0], tilted[0, 0]))]
assert abs(fetch.tilt_along("carry") - 30) < 0.5, fetch.tilt_along("carry")
calls.clear()
try:
    fetch._pose_holding("carry")
    raise AssertionError("tilted move accepted")
except fetch.FetchError:
    assert not calls
tilt["rpy"] = up_rpy
assert fetch.tilt_along("carry") < 1e-6

# ---------- height check: a pose move must not take the gripper down to the table ----------
z_along = {"look": -500.0}                     # flange z at the end of the move; it starts at 0
skills._ask = lambda name, **a: {"errorCode": "0", "cartPosition": [0, 0, z_along.get(name_of(a), 0.0)] + up_rpy}
name_of = lambda a: "look" if a["jointPosition"][0] > 0 else None
fetch.motion.poses = lambda: {"tuck": [0] * 6, "ready": [0] * 6, "carry": [0] * 6, "look": [10.0] + [0] * 5}
calls.clear()
try:
    fetch._pose("look")
    raise AssertionError("move down to the table accepted")
except fetch.FetchError:
    assert not calls
fetch._pose("ready")
assert calls == [("pose", "ready")], calls
# ---------- place spots: the pick spot only while the base stands where it picked ----------
seen_table = {"spots": None}
skills.on_table = lambda spots, table: (seen_table.update(spots=list(spots), table=table), [s for s in spots if s[1] >= 680])[1]
held = {"x": -160.0, "y": 600.0, "top_mm": -260.0, "table": -402.0, "base": (1.0, 2.0, 0.5)}
cup_near = {"x": -220.0, "y": 640.0, "top_mm": -340.0, "height_mm": 65.0}
tries = fetch.place_spots(held, (1.005, 2.0, 0.51), [cup_near])
assert tries[0] == (-160.0, 600.0) and all(t[1] >= 680 for t in tries[1:]), tries
assert all(np.hypot(x - cup_near["x"], y - cup_near["y"]) >= skills.FREE_MM for x, y in seen_table["spots"])
tries = fetch.place_spots(held, (1.0, 2.0, 0.5 + 0.17), [cup_near])          # turned 10 deg: the pick spot is gone
assert (-160.0, 600.0) not in tries and tries and seen_table["table"] == -402.0, tries
fetch.place_spots({**held, "table": None}, (1.0, 2.0, 0.5), [cup_near])
assert seen_table["table"] == -405.0                                          # from the other cup: -340 - 65
print("fetch ok")
