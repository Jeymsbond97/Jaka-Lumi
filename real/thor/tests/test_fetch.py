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
fetch.LOG_LINES = 1000                              # whole runs in the state log
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

# ---------- approach geometry ----------
def seen_from(pose, world, yaw, t):
    """Where an object at map point `world` appears (mm, arm frame) from base pose `pose`."""
    b = fetch._rot(-math.degrees(pose[2])) @ np.subtract(world, pose[:2])
    return fetch._rot(-yaw) @ (b - t) * 1000


goal = np.array(fetch.PICK_ZONE_CENTRE)
for yaw in (-86.2, 0.0, 30.0):
    for t in (np.zeros(2), np.array([0.12, -0.05])):
        for obj in ((-489.0, 998.0), (-160.0, 600.0), (300.0, 900.0), (-900.0, 300.0), (50.0, 420.0)):
            move = fetch.approach_move(obj, yaw, t)                            # turn on the spot, then straight
            if move is None:                                                   # too near the turning centre
                assert obj[1] < 500, (yaw, t, obj)
                continue
            turn, s = move
            p0 = (1.0, -2.0, 0.4)
            world = np.array(p0[:2]) + fetch._rot(math.degrees(p0[2])) @ fetch.to_base(obj, yaw, t)
            th = p0[2] + math.radians(turn)
            p1 = (p0[0] + s * math.cos(th), p0[1] + s * math.sin(th), th)
            assert np.allclose(seen_from(p1, world, yaw, t), goal, atol=1e-6), (yaw, t, obj, seen_from(p1, world, yaw, t))
            for side in (0, 90, -135):                                           # in from any side by navigation
                h = th + math.radians(side)
                sx, sy, sh = fetch.side_pose(world, h, yaw, t)
                p2 = (sx + fetch.STANDOFF_M * math.cos(sh), sy + fetch.STANDOFF_M * math.sin(sh), sh)
                assert np.allclose(seen_from(p2, world, yaw, t), goal, atol=1e-6)
        # the arm base's offset comes back from one object seen before and after a turn and a drive
        world, pa, pb = np.array([2.0, 1.0]), (1.0, 0.5, 0.3), (1.2, 0.4, 0.9)
        got = fetch.arm_offset((pa, seen_from(pa, world, yaw, t)), (pb, seen_from(pb, world, yaw, t)), yaw)
        assert np.allclose(got, t, atol=1e-9), (got, t)
# the arm offset kept is the median of the measurements: one bad one (a depth-only position) does not spoil it
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
world, pa, pb = np.array([2.0, 1.0]), (1.0, 0.5, 0.3), (1.2, 0.4, 0.9)
for t in ([0.11, -0.09], [0.12, -0.10], [0.005, -0.12]):
    t = np.array(t)
    fetch._learn_offset((pa, seen_from(pa, world, -86.2, t)), (pb, seen_from(pb, world, -86.2, t)), -86.2)
assert np.allclose(fetch.arm_xy(), [0.11, -0.10], atol=1e-3), fetch.arm_xy()
fetch.CALIB_FILE.unlink()
assert fetch.approach_move((-100.0, 0.0), -86.2, np.zeros(2)) is None         # right at the turning centre: back off
assert abs(fetch.approach_move((-300.0, 900.0), -86.2, np.zeros(2))[1]) > 0.2

# measure-axis sees the object move by -base_move (in the arm frame) and gets the yaw back
for yaw in (0.0, 90.0, -135.0, 30.0):
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


def fake_reachable(obj, start=None, accept=None):
    calls.append(("ik",))
    return (skills.plan_pick(obj), [0.0] * 6) if reach["ok"] else None


fetch.agv.markers = lambda: MARKERS
fetch.agv.pose = lambda: base["pose"]
fetch.agv.status = fake_status
fetch.agv.go = lambda m: (calls.append(("go", m)), (True, "OK"))[1]
fetch.agv.go_point = lambda x, y, th: (calls.append(("go_point", round(x, 3), round(y, 3))), (True, "OK"))[1]
fetch.agv.cancel = lambda: calls.append(("cancel",))
fetch.agv.clearance = lambda x, y: room["clear"](x, y)
fetch.agv.request = lambda cmd, **kw: (calls.append(("joy", cmd.split("linear_velocity=")[1].split("&")[0]))
                                       if "joy_control" in cmd else None, {})[1]
room = {"clear": lambda x, y: 1.0, "probe": lambda x, y: (float("inf"), float("inf"))}
fetch.agv.probe = lambda x, y: room["probe"](x, y)
fetch.AXIS_SPEED, fetch.COAST_S = 100.0, 0.0
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
fetch.gripper.open_ = lambda: (calls.append(("open",)), hand.update(holding=False, closed=False), fetch.gripper.state())[-1]
skills.find = lambda name, colour=None, seen=None: (calls.append(("find", name)), found["obj"])[1] if found["obj"] \
    else (_ for _ in ()).throw(skills.SkillError("I can't see a thing."))
skills.reachable_pick = fake_reachable
skills.look = lambda frames=None: []


def fake_pick(obj, wp, ja):
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
surface = {"z": -403.0}                     # what the fake depth camera sees: the proven table
skills.surface_heights = lambda pts, guess_z=-400.0: [surface["z"]] * len(pts)
skills.surface_points = lambda pts, guess_z=-400.0: [None] * len(pts)          # never the live depth file
eye = {"hand": "unknown"}                                                 # what skills.hand_sees() says
skills.hand_sees = lambda: eye["hand"]
where = {"how": "unseen"}                                                 # what skills.locate finds by depth
skills.locate = lambda xy, top, table, width, radius=None: \
    (where["how"], {"x": xy[0], "y": xy[1], "top_mm": top, "width_mm": width} if where["how"] == "here" else None)
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
moved = [l.split(" ", 1)[1] for l in st["log"] if "(straight)" in l]
assert moved[-2:] == ["arm to carry (straight)", "arm to look (straight)"], moved     # then look to drive
try:
    fetch.give()
    raise AssertionError("gave without a taught give pose")
except fetch.FetchError:
    pass
st = run(fetch.place)
assert st["status"] == "done" and not st["holding"] and ("place",) in calls and poses()[-1] == "look", (st, calls)

# ---------- arm speed: empty hand faster, with the object slow ----------
speeds = []
real_go = fetch.motion.go
fetch.motion.go = lambda name, speed="slow", *a, **k: (speeds.append((name, speed)), calls.append(("pose", name)))
fetch._pose("look")
fetch.motion.poses = lambda: {"tuck": [0] * 6, "ready": [0] * 6, "carry": [0] * 6, "look": [0] * 6}
tilt["rpy"] = up_rpy
fetch._pose_holding("carry")
assert speeds == [("look", skills.EMPTY_SPEED), ("carry", skills.HOLDING_SPEED)], speeds
assert skills.EMPTY_SPEED != skills.HOLDING_SPEED
fetch.motion.go = real_go

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
st = run(fetch.place)                                    # only floor in view: never put down, search all round
assert st["status"] == "failed" and ("place",) not in calls and st["holding"], st["log"][-3:]
surface["z"] = -303.0
st = run(fetch.place)                                                        # done: back to the usual lift
assert st["status"] == "done" and body["lift"] == 75.0, (st, body)
surface["z"] = -1060.0
body["lift"], found["obj"] = 175.0, None                                      # raised and nothing in view ...
found_after = {"n": 0}
real_find = skills.find
def find_low(name, colour=None, seen=None):
    found_after["n"] += 1
    if body["lift"] > 75.0:
        raise skills.SkillError("I can't see a thing.")
    return CUP
skills.find = find_low
reset()
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
lifts = [c[1] for c in calls if c[0] == "lift"]
turns = [c for c in calls if c[0] == "go_point"]
assert st["status"] == "holding" and lifts[0] == 0.0 and len(turns) == fetch.SEARCH_TURNS, (st, calls)  # ... a whole
assert calls.index(("lift", 0.0)) > max(i for i, c in enumerate(calls) if c[0] == "go_point")  # turn high, then low
skills.find = real_find
surface["z"] = -403.0
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
# ... and put it on the table there: drive first, then put down (never before the drive)
st = run(fetch.carry_to, {"marker": "home"}, "place")
names = [c[0] for c in calls]
assert st["status"] == "done" and not st["holding"] and names.index("go") < names.index("place"), (st, calls)
assert [c for c in calls if c[0] == "go"] == [("go", "home")]
try:
    fetch.carry_to({"marker": "p1"}, "throw")
    raise AssertionError("unknown finish accepted")
except fetch.FetchError:
    pass
fetch._set(holding=False, status="idle")

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
assert len(turns) == 3 * fetch.SEARCH_TURNS and not any(c[0] == "pick" for c in calls), calls  # whole turn per lift
assert [c[1] for c in calls if c[0] == "lift"][:2] == [0.0, 250.0], calls                  # here, down, up
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
first, last = names.index("go_point"), len(names) - 1 - names[::-1].index("go_point")
assert "line" not in names[first:last + 1], names                       # turns with the cup in look: no arm moves
# ---------- put down: a table seen further away, the base goes closer, then a spot in reach ----------
reset()
hand.update(holding=True, closed=True)
fetch._set(holding=True, status="holding")
skills._held.update(top_mm=-260.0, x=-150.0, y=600.0, base=None, table=-403.0)
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
surface["z"] = -400.0
skills.on_table = lambda spots, table: [p for p in spots if p[1] >= 760][:1] if not any(c[0] == "joy" for c in calls) \
    else [p for p in spots if p[1] <= 700][:1]
st = run(fetch.place)
skills.on_table, surface["z"] = real_on_table, -403.0
names = [c[0] for c in calls]
assert st["status"] == "done" and "joy" in names and names.index("joy") < names.index("place"), st["log"]
assert any("further away" in l for l in st["log"]) and not any(c[0] == "go" for c in calls), st["log"]

# ---------- out of reach, base axis not measured: no shift, ask, then failed ----------
reset()
reach["ok"] = False
st = run(fetch.start, ok)
assert st["status"] == "failed" and not any(c[0] == "go_point" for c in calls), calls
assert any("move it closer" in l for l in st["log"]) and poses()[-1] == "look"

# ---------- out of reach with the axis measured: turn and drive straight in, APPROACH_TRIES times, then ask ----------
reset()
reach["ok"] = False
far_cup = {**CUP, "x": -489.0, "y": 998.0}
found["obj"] = far_cup
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
moves = [l for l in st["log"] if "moving to reach it" in l]
assert st["status"] == "failed" and len(moves) == fetch.APPROACH_TRIES, st["log"]
assert sum(c[0] == "go_point" for c in calls) == fetch.APPROACH_TRIES                  # a turn to face it each time
assert any(c[0] == "joy" and float(c[1]) > 0 for c in calls), calls                     # then straight forward
# reachable after the first move: picked
reset()
found["obj"] = far_cup
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
reach["ok"] = False
skills.find = lambda name, colour=None, seen=None: (reach.update(ok=any(c[0] == "joy" for c in calls)), far_cup)[1]
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
skills.find = real_find
assert st["status"] == "holding" and ("pick", "apple") in calls, st["log"]
fetch._set(holding=False, status="idle")
# the straight way is blocked (an obstacle next to the base on the way): navigation round to a side, one side a try
reset()
found["obj"], reach["ok"] = far_cup, False
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
room["clear"] = lambda x, y: 0.1 if math.hypot(x, y) > 0.01 else 0.2
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
room["clear"] = lambda x, y: 1.0
rounds = [l for l in st["log"] if "driving round" in l]
assert st["status"] == "failed" and len(rounds) == fetch.APPROACH_TRIES and not any(c[0] == "joy" for c in calls), st["log"]
assert len({l.split("from ")[-1] for l in rounds}) == fetch.APPROACH_TRIES              # every time another side
found["obj"] = CUP

# ---------- the state still says holding, but the hand is open (someone took it): a new fetch starts ----------
reset()
fetch._set(holding=True, status="holding")
hand.update(holding=False, closed=False)
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
assert st["status"] == "holding" and ("pick", "apple") in calls, st["log"]        # started, not refused
fetch._set(holding=True, status="holding")
hand.update(holding=True, closed=True)                               # really holding: refused as before
try:
    fetch.start(ok)
    raise AssertionError("started while holding")
except fetch.FetchError:
    pass
fetch._set(holding=False, status="idle")
hand.update(holding=False, closed=False)
# the camera sees an empty hand while AI_1 still says holding (the fingers shut on nothing): believed, fetch starts
reset()
fetch._set(holding=True, status="holding")
hand.update(holding=True, closed=True)
eye["hand"] = "empty"
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
assert st["status"] == "holding" and ("open",) in calls, st["log"]           # started, and opened the hand first
# ... and place / give with an empty hand are refused, the state forgets it
fetch._set(holding=True, status="holding")
for fn in (fetch.place, fetch.give):
    try:
        fn()
        raise AssertionError("put down / gave with an empty hand")
    except fetch.FetchError as e:
        assert "empty" in str(e) or "learned" in str(e), e
assert not fetch.state()["holding"]
eye["hand"] = "object"                                                    # the camera sees it, AI_1 says nothing
hand.update(holding=False, closed=False)
try:
    fetch.start(ok)
    raise AssertionError("started with something in the hand")
except fetch.FetchError:
    pass
assert fetch.check_hand() and fetch.state()["holding"]                  # the dialog takes it over
eye["hand"] = "empty"
assert not fetch.check_hand() and not fetch.state()["holding"]           # ... and forgets it when it is gone
eye["hand"] = "unknown"
fetch._set(holding=False, status="idle")
hand.update(holding=False, closed=False)

# ---------- too wide from far away: go closer and measure again; too wide up close: refused ----------
real_reach = skills.reachable_pick
def width_check(obj, start=None, accept=None):
    calls.append(("ik",))
    skills.plan_pick(obj)                                                  # raises when too wide
    return (skills.plan_pick(obj), [0.0] * 6) if obj["y"] < 700 else None
skills.reachable_pick = width_check
reset()
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
wide_far = {**CUP, "name": "cup", "x": -69.0, "y": 1142.0, "width_mm": 88.0}
wide_near = {**wide_far, "x": -100.0, "y": 600.0, "width_mm": 79.0}
skills.find = lambda name, colour=None, seen=None: wide_near if any(c[0] == "joy" for c in calls) else wide_far
st = run(fetch.start, {**ok, "object": "cup", "source": "here", "dest": "here"})
assert st["status"] == "holding" and any("measure it again up close" in l for l in st["log"]), st["log"]
fetch._set(holding=False, status="idle")
hand.update(holding=False, closed=False)
reset()
skills.find = lambda name, colour=None, seen=None: {**wide_near, "width_mm": 95.0}
st = run(fetch.start, {**ok, "object": "cup", "source": "here", "dest": "here"})
assert st["status"] == "failed" and "too big" in st["log"][-1], st["log"]
skills.find, skills.reachable_pick = real_find, real_reach
skills.reachable_pick = fake_reachable

# ---------- put it on a named thing: an orange chair too low for the arm -> said why; one at table height -> on it ----
reset()
hand.update(holding=True, closed=True)
fetch._set(holding=True, status="holding")
skills._held.update(top_mm=-260.0, x=-150.0, y=600.0, base=None, table=-403.0)
chair = {"name": "chair", "colour": "orange", "x": -120.0, "y": 640.0, "top_mm": -150.0, "seen": 8, "spread": 1.0}
real_look = skills.look
skills.look = lambda frames=None: [chair, {**chair, "colour": "black", "x": 300.0}]
surface["z"] = -703.0                                                      # a seat 30 cm below a table
st = run(fetch.place, None, {"name": "chair", "colour": "orange"})
assert st["status"] == "failed" and "lower than a table" in st["log"][-1] and st["holding"], st["log"][-3:]
assert ("place",) not in calls
surface["z"] = -403.0                                                      # a stool as high as a table
skills.on_table = lambda spots, table: list(spots)[:1]
st = run(fetch.place, None, {"name": "chair", "colour": "orange"})
assert st["status"] == "done" and ("place",) in calls, st["log"][-4:]
skills.look, skills.on_table = real_look, real_on_table
fetch._set(holding=False, status="idle")
hand.update(holding=False, closed=False)

# ---------- which heights the arm can work at: a lift for each, none for a floor or a low seat ----------
body["lift"] = 75.0
assert fetch.lift_for(-403.0) == 75.0                     # the proven table: the lift stays
assert fetch.lift_for(-303.0) == 175.0                    # 10 cm higher: lift up by as much
assert fetch.lift_for(-603.0) == 0.0                      # 20 cm lower: lift down to 0, reachable there (IK map)
assert fetch.lift_for(-703.0) is None and fetch.lift_for(-1060.0) is None    # a seat 30 cm lower, the floor

# ---------- a turn that would take the arm into something is not made ----------
reset()
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
room["clear"] = lambda x, y: 0.05 if math.hypot(x, y) > 0.2 else 1.0    # free at the base centre, a wall around it
calls.clear()
assert fetch._turn(30) is False and not any(c[0] == "go_point" for c in calls), calls
room["clear"] = lambda x, y: 1.0
assert fetch._turn(30) is True and any(c[0] == "go_point" for c in calls)
assert fetch.turn_hits(90) is None
# the torso camera sees something where the arm will be (a table top's edge the lidar misses): no turn
real_points, real_extr = skills.surface_points, skills.objects.base_from_camera
skills.objects.base_from_camera = lambda: np.eye(4)
skills.surface_points = lambda pts, guess_z=-400.0: [tuple(p) for p in pts]          # depth right at each point
calls.clear()
assert fetch._turn(30) is False and not any(c[0] == "go_point" for c in calls)
skills.surface_points = lambda pts, guess_z=-400.0: [tuple(np.array(p) * 3) for p in pts]   # only far behind them
assert fetch.depth_hits(30) is None
skills.surface_points, skills.objects.base_from_camera = real_points, real_extr
fetch.CALIB_FILE.unlink()

# ---------- first search turn: towards the side with things the map does not have ----------
room["probe"] = lambda x, y: (0.05, 2.0) if y < 0 else (float("inf"), 2.0)     # base at (0, 0, 0): right is y < 0
assert fetch.first_side() == -1
room["probe"] = lambda x, y: (0.05, 2.0) if y > 0 else (float("inf"), 2.0)
assert fetch.first_side() == 1
room["probe"] = lambda x, y: (0.05, 0.05)                                       # walls on the map: no preference
assert fetch.first_side() == 1
room["probe"] = lambda x, y: (float("inf"), float("inf"))

# ---------- lost after a base move: YOLO misses it, depth finds it where it should be -> picked, no search ----------
def lose_after_move(name, colour=None, seen=None):
    if any(c[0] == "joy" for c in calls):
        raise skills.SkillError("I can't see a thing.")
    return far_cup
reach_after = lambda obj, start=None, accept=None: (calls.append(("ik",)), (skills.plan_pick(obj), [0.0] * 6)
                                                     if any(c[0] == "joy" for c in calls) else None)[1]
for how, want in (("here", "failed"), ("gone", "failed")):
    reset()
    fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
    skills.find, skills.reachable_pick, where["how"] = lose_after_move, reach_after, how
    st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
    turns = [l for l in st["log"] if "look further" in l]
    if how == "here":     # depth sees it, YOLO never: never picked from the depth-only place, ask, no turning round
        assert st["status"] == "failed" and ("pick", "apple") not in calls and not turns, st["log"]
        assert "move it a little" in st["log"][-1], st["log"][-1]
    else:                 # gone from where it was: the whole search, then "can't see"
        assert st["status"] == "failed" and "not where I saw" not in st["log"][-1] and len(turns) >= fetch.SEARCH_TURNS, st["log"]
    fetch._set(holding=False, status="idle")
# not seen by depth either (out of view): back off, turn both ways, then the whole search
reset()
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
skills.find, where["how"] = lose_after_move, "unseen"
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
assert any("find it again" in l for l in st["log"]) and any(c[0] == "joy" and float(c[1]) < 0 for c in calls), st["log"]
skills.find, skills.reachable_pick, where["how"] = real_find, fake_reachable, "unseen"
fetch._set(holding=False, status="idle")

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
