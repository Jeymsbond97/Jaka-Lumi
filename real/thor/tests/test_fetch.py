"""Self-check of tasks/fetch.py with fake base, arm and gripper (no robot, no network): python tests/test_fetch.py"""
import json
import math
import tempfile
import threading
import time
from pathlib import Path

import numpy as np

from robot import head
assert head.LIFT_MAX_MM == 0.0   # live: the lift stays at the bottom (head camera cable); the cases below are the long cable's
head.LIFT_MAX_MM, head.AXIS_LIMITS = 105.0, ((0.0, 105.0),) + head.AXIS_LIMITS[1:]
from manipulation import skills
from tasks import fetch
from vision import calib

tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"           # never the real /dev/shm file
fetch.CALIB_FILE = tmp / "fetch_calib.json"
fetch.DRIVE_POLL_S = fetch.GIVE_POLL_S = 0.01
fetch.ASK_EVERY_S, fetch.ASK_WAIT_S = 0.01, 0.05
fetch.LOG_LINES = 1000                              # whole runs in the state log
fetch.KNOWN_FILE = tmp / "known_things.json"
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
assert fetch.describe(ok, "ko") == "p1 위치에서 사과를 가져와서 home 위치로 가져가서 들고 있을게요."
assert fetch.describe({**ok, "object": "cup", "colour": "red", "finish": "place"}, "ko") == \
    "p1 위치에서 빨간 컵을 가져와서 home 위치로 가져가서 테이블에 내려놓을게요."

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
CUP = {"name": "apple", "colour": "red", "x": -150.0, "y": 600.0, "top_mm": -260.0, "width_mm": 76.0,
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


def fake_reachable(obj, start=None, accept=None, max_yaw=None):
    calls.append(("ik",))
    return (skills.plan_pick(obj), [0.0] * 6) if reach["ok"] else None


fetch.agv.markers = lambda: MARKERS
fetch.agv.pose = lambda: base["pose"]
fetch.agv.status = fake_status
fetch.agv.go = lambda m: (calls.append(("go", m)), (True, "OK"))[1]
fetch.agv.go_point = lambda x, y, th: (calls.append(("go_point", round(x, 3), round(y, 3))), base.update(pose=(x, y, th)),
                                       (True, "OK"))[-1]                 # the fake base gets there at once
fetch.agv.cancel = lambda: calls.append(("cancel",))
fetch.agv.clearance = lambda x, y: room["clear"](x, y)
fetch.agv.request = lambda cmd, **kw: (calls.append(("joy", cmd.split("linear_velocity=")[1].split("&")[0]))
                                       if "joy_control" in cmd else None, {})[1]
room = {"clear": lambda x, y: 1.0, "probe": lambda x, y: (float("inf"), float("inf"))}
fetch.agv.probe = lambda x, y: room["probe"](x, y)
fetch.AXIS_SPEED, fetch.COAST_S = 100.0, 0.0
real_straight = fetch._straight


def moving_straight(d, speed=None, stop=True):
    """The fake base's pose follows a straight drive, unless base["stuck"] (its own obstacle stop at a table)."""
    got = real_straight(d, speed, stop)
    if not base.get("stuck"):
        x, y, th = base["pose"]
        s = math.copysign(got, d)
        base["pose"] = (x + s * math.cos(th), y + s * math.sin(th), th)
    return got


fetch._straight = moving_straight
fetch.MOVED_CHECK_M = float("inf")         # this fake base never moves its pose (the check: test_driving.py)
arm = {"j": [5.0] * 6}                                                     # the fake arm's joints: away from every pose
fetch.motion.go = lambda name, *a, **k: (calls.append(("pose", name)), arm.update(j=list(fetch.motion.poses()[name])))
fetch.motion.stop = lambda: calls.append(("arm stop",))
real_move = fetch.arm_route.move
fetch.arm_route.move = lambda seq, *a, **k: [fetch.motion.go(n) for n, _ in seq]    # by name (poses share joints here)
fetch.motion.poses = lambda: {"ready": [0] * 6, "carry": [3] * 6, "look": [0] * 6}
fetch.motion.tcp = lambda: [0.0] * 3 + tilt["rpy"]                    # the flange as the fake kine_forward says
skills._joints = lambda: arm["j"]
skills.FRESH_WAIT_S = 0.0                                                  # never wait for the live camera files
skills.home_joints = lambda: [0.0] * 6
up_rpy = list(skills.GRASP_RPY)
tilt = {"rpy": up_rpy}
skills._ask = lambda name, **a: {"errorCode": "0", "cartPosition": [0, 0, 0] + tilt["rpy"]}
fetch.gripper.state = lambda: {**hand, "ai": [3500 if hand["holding"] else 160], "di": [int(hand["holding"])]}
fetch.gripper.open_ = lambda: (calls.append(("open",)), hand.update(holding=False, closed=False), fetch.gripper.state())[-1]
def in_room(obj):
    """A fake camera's object that stays put in the room: seen where it is from the base pose now (the CALIB_FILE yaw
    must be written first; the base is at (0, 0, 0) when this is called)."""
    w = fetch.map_xy(obj)
    return lambda: {**obj, **dict(zip(("x", "y"), map(float, fetch.arm_frame(w))))}


skills.find = lambda name, colour=None, seen=None: (calls.append(("find", name)),
                                                    found["obj"]() if callable(found["obj"]) else found["obj"])[1] \
    if found["obj"] \
    else (_ for _ in ()).throw(skills.SkillError("I can't see a thing."))
skills.reachable_pick = fake_reachable
skills.look = lambda frames=None, **kw: []


def fake_pick(obj, wp, ja):
    calls.append(("pick", obj["name"]))
    arm.update(j=[5.0] * 6)
    hand.update(holding=True, closed=True)
    skills._held.update(top_mm=obj["top_mm"], x=obj["x"], y=obj["y"])


def fake_place(wp):
    calls.append(("place",))
    arm.update(j=[5.0] * 6)
    hand.update(holding=False, closed=False)
    skills._held.clear()


skills._do_pick = fake_pick
skills._do_place = fake_place
skills._line = lambda name, pose: (calls.append(("line", name)), arm.update(j=[5.0] * 6))
fetch.motion.move_linear = lambda target=None, **kw: (calls.append(("line", "straight")), arm.update(j=[9.0] * 6))
skills.on_table = lambda spots, table: []                                 # no live depth frames in a test
surface = {"z": -403.0}                     # what the fake depth camera sees: the proven table
skills.surface_heights = lambda pts, guess_z=-400.0: [surface["z"]] * len(pts)
skills.flat_points = lambda pts, guess_z=-400.0, camera="torso", T=None: [(p[0], p[1], surface["z"]) for p in pts]
skills.surface_points = lambda pts, guess_z=-400.0, **kw: [None] * len(pts)    # never the live depth file
fetch.head_cam.base_from_head = lambda yaw, pitch: None                    # head camera checks off (own test below)
fetch.objects.latest = lambda camera="torso": {"age_s": None, "objects": [], "head_pose": None}
fetch.camview.want = lambda name: None
eye = {"hand": "unknown"}                                                 # what skills.hand_sees() says
skills.hand_sees = lambda: eye["hand"]
where = {"how": "unseen"}                                                 # what skills.locate finds by depth
skills.locate = lambda xy, top, table, width, radius=None: \
    (where["how"], {"x": xy[0], "y": xy[1], "top_mm": top, "width_mm": width} if where["how"] == "here" else None)
body = {"lift": 75.0}
fetch.head.status = lambda: [body["lift"], -15.0, *fetch.HEAD_AHEAD]   # the head at rest
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
    base.update(polls=0, on_poll=None, pose=(0.0, 0.0, 0.0), stuck=False)
    arm.update(j=[5.0] * 6)
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

# ---------- arm speed along the pose graph: arm_route.SPEED with an empty hand, HOLD_SPEED holding ----------
speeds = []
real_go = fetch.motion.go
fetch.motion.go = lambda name, speed="slow", *a, **k: (speeds.append((name, speed)), calls.append(("pose", name)))
fetch.arm_route.move, fake_move = real_move, fetch.arm_route.move
fetch.motion.move_path = lambda moves, *a, **k: speeds.extend(("carry", s) for _, s in moves)
arm.update(j=[0.5] * 6)
fetch._pose("carry")
tilt["rpy"] = up_rpy
fetch._pose("carry", holding=True)
assert speeds == [("carry", "route"), ("carry", "slow")], speeds
fetch.motion.go, fetch.arm_route.move = real_go, fake_move

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

# ---------- a table 3 cm higher: lift up before the pick, back down before driving ----------
reset()
surface["z"], body["lift"] = -373.0, 75.0
st = run(fetch.start, ok)
lifts = [c[1] for c in calls if c[0] == "lift"]
assert st["status"] == "holding" and lifts[:2] == [105.0, 75.0], (lifts, calls)    # at p1 up for the pick, down to drive
assert calls.index(("lift", 105.0)) < next(i for i, c in enumerate(calls) if c[0] == "pick")
surface["z"] = -1060.0                                                       # the floor: never fitted
assert not fetch._fit_lift(-1060.0) and body["lift"] == 75.0
st = run(fetch.place)                                    # only floor in view: never put down, search all round
assert st["status"] == "failed" and ("place",) not in calls and st["holding"], st["log"][-3:]
surface["z"] = -373.0
st = run(fetch.place)                                                        # done: back to the usual lift
assert st["status"] == "done" and body["lift"] == 75.0, (st, body)
surface["z"] = -1060.0
body["lift"], found["obj"] = 105.0, None                                      # raised and nothing in view ...
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
before = calls[:calls.index(("pick", "apple"))]                         # (then the way back to where it was told)
turns = [c for c in before if c[0] == "go_point"]
assert st["status"] == "holding" and lifts[0] == 0.0 and len(turns) == 1, (st, calls)   # ... a base turn up there,
assert calls.index(("lift", 0.0)) > max(i for i, c in enumerate(before) if c[0] == "go_point")  # then the lift down
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
assert len(turns) == 2 and not any(c[0] == "pick" for c in calls), calls     # one search: a base turn at each lift
assert [c[1] for c in calls if c[0] == "lift"] == [0.0, 75.0], calls           # here (75), the other end, back to drive
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
far_held = dict(skills._held)
real_chain, real_options = skills.ik_chain, skills.place_options
far_spot = lambda n: n.startswith("to (") and float(n.split(", ")[1].split(")")[0]) > 740   # line to a spot y > 740
skills.ik_chain = lambda wp, j: [[n, p, [0] * 6, "no IK solution" if far_spot(n) else None] for n, p in wp]
skills.place_options = lambda *a: iter(())                                 # ... the arm does not reach it from here
st = run(fetch.place)
names = [c[0] for c in calls]
assert st["status"] == "done" and "joy" in names and names.index("joy") < names.index("place"), st["log"]
assert any("further away" in l for l in st["log"]) and not any(c[0] == "go" for c in calls), st["log"]
# ... the arm reaches a spot of it from here (lift 0, the near part of the table under the camera's view): put there,
# no base move (2026-10-26 18:53: "further away" right in front, the base could not get nearer)
skills.ik_chain, skills.place_options = real_chain, real_options
reset()
hand.update(holding=True, closed=True)
fetch._set(holding=True, status="holding")
skills._held.update(far_held)
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
st = run(fetch.place)
names = [c[0] for c in calls]
assert st["status"] == "done" and "joy" not in names and "place" in names, st["log"]
assert any("trying spots in reach from here" in l for l in st["log"]), st["log"]
skills.on_table, surface["z"] = real_on_table, -403.0

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
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
found["obj"], reach["ok"] = in_room(far_cup), False
room["clear"] = lambda x, y: 0.1 if math.hypot(x, y) > 0.01 else 0.2
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
room["clear"] = lambda x, y: 1.0
tries = [l for l in st["log"] if "driving round" in l or "can't get near enough" in l]   # (no room anywhere here)
drives = [l for l in tries if "driving round" in l]
assert st["status"] == "failed" and tries, st["log"]
assert len({l.split("from ")[-1] for l in drives}) == len(drives)                       # each side driven to once
assert any("asking for help: every way closer was blocked" in l for l in st["log"]), st["log"]
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
def width_check(obj, start=None, accept=None, max_yaw=None):
    calls.append(("ik",))
    skills.plan_pick(obj)                                                  # raises when too wide
    return (skills.plan_pick(obj), [0.0] * 6) if obj["y"] < 700 else None
skills.reachable_pick = width_check
reset()
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
wide_far = {**CUP, "name": "cup", "x": -69.0, "y": 1142.0, "width_mm": 98.0}
wide_near = {**wide_far, "x": -100.0, "y": 600.0, "width_mm": 79.0}
skills.find = lambda name, colour=None, seen=None: wide_near if any(c[0] == "joy" for c in calls) else wide_far
st = run(fetch.start, {**ok, "object": "cup", "source": "here", "dest": "here"})
assert st["status"] == "holding" and any("measure it again up close" in l or "closer first" in l for l in st["log"]), \
    st["log"]                                                              # (that far it is not even measured)
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
skills.look = lambda frames=None, **kw: [chair, {**chair, "colour": "black", "x": 300.0}]
surface["z"] = -703.0                                                      # a seat 30 cm below a table
st = run(fetch.place, None, {"name": "chair", "colour": "orange"})
assert st["status"] == "failed" and "lower than a table" in st["log"][-1] and st["holding"], st["log"][-3:]
assert ("place",) not in calls
surface["z"] = -403.0                                                      # a stool as high as a table
skills.on_table = lambda spots, table: list(spots)[:1]
st = run(fetch.place, None, {"name": "chair", "colour": "orange"})
assert st["status"] == "done" and ("place",) in calls, st["log"][-4:]
# "the grey table": the cameras call it a white sink (flat, table height) -> on it; nothing named in view -> any table
sink = {"name": "sink", "colour": "white", "x": -160.0, "y": 760.0, "top_mm": -400.0, "seen": 8, "spread": 1.0}
for seen in ([chair, sink], []):
    reset()
    hand.update(holding=True, closed=True)
    fetch._set(holding=True, status="holding")
    skills._held.update(top_mm=-260.0, x=-150.0, y=600.0, base=None, table=-403.0)
    skills.look = lambda frames=None, seen=seen, **kw: seen
    fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
    said = []
    st = run(fetch.place, lambda en, ko: said.append(en), {"name": "dining table", "colour": "grey"})
    assert st["status"] == "done" and ("place",) in calls, st["log"][-4:]
    this = st["log"][max(i for i, l in enumerate(st["log"]) if "placing" in l):]          # this run's lines
    instead = "white sink" if seen else "table"            # not exactly what was said: the closest (white = grey, a
    assert any(f"couldn't find the grey table, so I put it on the {instead} here" in w for w in said), said   # flat
    assert seen or not any("sink" in l for l in this), this   # furniture word), after the one whole search; else any
skills.look, skills.on_table = real_look, real_on_table
fetch._set(holding=False, status="idle")
hand.update(holding=False, closed=False)

# ---------- a taught colour sticks to the thing by its place, from any side ----------
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))
base["pose"] = (0.0, 0.0, 0.0)
stool = {"name": "chair", "colour": "grey", "x": 265.0, "y": 2390.0, "top_mm": -400.0, "seen": 8, "spread": 1.0}
real_look2 = skills.look
skills.look = lambda frames=None, **kw: [stool]
o, w = fetch.teach_thing("chair", "yellow")
assert fetch.colour_of(stool) == "yellow"
b_now = fetch._rot(-90.0) @ (np.array(w) - [1.0, 1.0])                    # the base moved to (1, 1) and turned 90 deg
arm_now = fetch._rot(86.2) @ (b_now - fetch.arm_xy()) * 1000
base["pose"] = (1.0, 1.0, math.radians(90.0))
moved = {**stool, "colour": "orange", "x": float(arm_now[0]), "y": float(arm_now[1])}
assert fetch.colour_of(moved) == "yellow", fetch.colour_of(moved)         # seen from elsewhere, read orange: still yellow
assert fetch.colour_of({**moved, "x": moved["x"] + 900.0}) == "orange"     # another chair 0.9 m away keeps its own
skills.look = real_look2
base["pose"] = (0.0, 0.0, 0.0)
fetch.CALIB_FILE.unlink()
fetch.KNOWN_FILE.unlink()

# ---------- which heights the arm can work at: a lift for each, none for a floor or a low seat ----------
body["lift"] = 75.0
assert fetch.lift_for(-403.0) == 75.0                     # the proven table: the lift stays
assert fetch.lift_for(-373.0) == 105.0                    # 3 cm higher: lift up by as much
assert fetch.lift_for(-303.0) == 105.0                    # 10 cm higher: only to the lift limit (camera cable)
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
skills.surface_points = lambda pts, guess_z=-400.0, **kw: [tuple(p) for p in pts]          # depth right at each point
calls.clear()
assert fetch._turn(30) is False and not any(c[0] == "go_point" for c in calls)
skills.surface_points = lambda pts, guess_z=-400.0, **kw: [tuple(np.array(p) * 3) for p in pts]   # only far behind them
assert fetch.depth_hits(30) is None
# only the head camera, turned to the side of the turn, sees something in the arm's way: no turn; the head stays there
heads = []
real_head_move, real_from_head, real_status = fetch.head.moveto, fetch.head_cam.base_from_head, fetch.head.status
hp = {"waist": -15.0, "yaw": 0.0, "pitch": 0.0}
fetch.head.status = lambda: [body["lift"], hp["waist"], hp["yaw"], hp["pitch"]]
def head_move(pos, **kw):
    if abs(pos[0] - body["lift"]) > 0.5:
        calls.append(("lift", pos[0]))
    if (pos[2], pos[3]) != (hp["yaw"], hp["pitch"]):
        heads.append(tuple(pos[2:]))
    body["lift"] = pos[0]
    hp.update(waist=pos[1], yaw=pos[2], pitch=pos[3])
fetch.head.moveto = head_move
fetch.head_cam.base_from_head = lambda yaw, pitch: np.eye(4)
skills.surface_points = lambda pts, guess_z=-400.0, camera="torso", T=None: \
    [tuple(p) if camera == "head" else None for p in pts]
calls.clear()
assert fetch._turn(-30) is False and not any(c[0] == "go_point" for c in calls)
assert heads == [(-fetch.HEAD_SIDE_DEG, fetch.HEAD_LOW_PITCH)], heads           # no move back: the next look turns it
skills.surface_points = lambda pts, guess_z=-400.0, **kw: [None] * len(pts)

# ---------- the search (_look_around), one for picking and placing ----------
# (a) ahead with both cameras, (b) waist and head together to the busier side step by step, then the other side,
# (c) the base turns towards that side and all again, (d) the other lift end and all again
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2, "waist_deg": -15.0}))   # the front: -15
real_blocked, real_side, real_turn, real_find_any = fetch._sweep_blocked, fetch.first_side, fetch._turn, fetch._find_any
blocked, views, base_turns = set(), [], []
fetch._sweep_blocked = lambda deg, what: round(fetch._waist_turn() + deg) in blocked          # by where it would end
fetch.first_side = lambda: -1                                                 # more unmapped things on the right
fetch._turn = lambda deg, holding=False, why="": base_turns.append((deg, body["lift"])) or deg not in blocked_turns
blocked_turns = set()
fetch._do_step({"do": "turn", "deg": -360.0}, None)          # all the way round: two checked half turns
assert [d for d, _ in base_turns] == [-180.0, -180.0], base_turns
base_turns.clear()
def seen_here(at=None):
    views.append((round(fetch._waist_turn()), round(hp["yaw"])))
    return "it" if views[-1] == at else None
body["lift"], hp["waist"], hp["yaw"] = 75.0, -15.0, 0.0
assert fetch._look_around(seen_here) is None
side = [(-60, 0), (-120, 0), (-120, -60), (60, 0), (120, 0), (120, 60)]      # the head turns the last 60 deg
assert views == [(0, 0)] + side + [(0, 0)] + side + [(0, 0)] + side + [(0, 0)] + side, views
assert base_turns == [(-180.0, 75.0), (-180.0, 0.0)], base_turns              # towards the busy side, at each lift
assert hp["waist"] == -15.0                                                   # nothing: the waist back at the front
# found at a view: the waist and the head stay where it was seen
views.clear(); base_turns.clear()
body["lift"] = 75.0
assert fetch._look_around(lambda: seen_here((120, 0))) == "it" and round(fetch._waist_turn()) == 120 and not base_turns
# a waist turn whose sweep is not clear is left out: the head turns further instead
views.clear(); hp["waist"] = -15.0
blocked = {120}
fetch._look_around(lambda: seen_here((60, 120)))
assert views[-1] == (60, 120) and (60, 60) in views, views
blocked = set()
# a half turn of the base refused: a quarter turn; on the charger: no base turn at all
views.clear(); base_turns.clear(); body["lift"] = 75.0
blocked_turns = {-180.0}
fetch._look_around(lambda: None)
assert base_turns[:2] == [(-180.0, 75.0), (-90.0, 75.0)], base_turns
blocked_turns = set()
base_turns.clear()
base["charging"] = True
fetch._look_around(lambda: None)
assert not base_turns
base["charging"] = False
# the waist never goes past the body's limit (+-140 absolute): the head turns the rest
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2, "waist_deg": -30.0}))
hp["waist"] = -30.0
assert fetch._waist_to(-120.0) and hp["waist"] == -140.0
fetch._look_at(-180.0, lambda: None)
assert hp["waist"] == -140.0 and round(hp["yaw"]) == -70, hp
hp["waist"] = -15.0
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2, "waist_deg": -15.0}))

# ---------- picking: the head camera sees the cup far away -> the base goes there, the torso camera picks it up ------
sight = {"n": 0}
def head_sees(camera="torso"):                                  # the cup to the left, seen twice at about one place
    sight["n"] += 1
    cup = {"name": "cup", "colour": "white", "position_mm": [-900.0 + sight["n"] % 2 * 20, 1700.0, -380.0]}
    return {"age_s": 0.1, "objects": [cup] if camera == "head" and round(hp["yaw"]) == 60 else [], "head_pose": None}
fetch.objects.latest = head_sees
assert fetch._head_seen(lambda o: fetch._is_task(o, {"object": "cup", "colour": "red"})) is None   # not that colour
hp["yaw"] = 60.0
got = fetch._head_seen(lambda o: fetch._is_task(o, {"object": "cup", "colour": "white"}))
assert got and got["head"] and abs(got["x"] + 890) < 1 and got["y"] == 1700.0, got
hp["yaw"] = 0.0
went = []
real_go_to = fetch._go_to
fetch._go_to = lambda thing, goal, tried, holding=False: (went.append((round(thing["x"]), goal)), calls.append(("joy", "0.05")))
fetch._find_any = lambda task, close=None: CUP if any(c[0] == "joy" for c in calls) else None
calls.clear(); views.clear()
assert fetch._see({"object": "cup", "colour": "white"}) == CUP
assert went == [(-890, fetch.PICK_ZONE_CENTRE)], went                       # once to where the head saw it
fetch._go_to = real_go_to
fetch.objects.latest = lambda camera="torso": {"age_s": None, "objects": [], "head_pose": None}

fetch._sweep_blocked, fetch.first_side, fetch._turn, fetch._find_any = real_blocked, real_side, real_turn, real_find_any
fetch.head.moveto, fetch.head_cam.base_from_head, fetch.head.status = real_head_move, real_from_head, real_status
skills.surface_points, skills.objects.base_from_camera = real_points, real_extr
fetch.CALIB_FILE.unlink()

# ---------- no waiting: a drive that has ended at its goal is over at once (a short turn may never show "running") ----
real_agv_status = fetch.agv.status
fetch.agv.status = lambda: {"move_status": "succeeded", "current_pose": {"x": 1.0, "y": 2.0, "theta": 0.5}}
t0 = time.time()
fetch._wait_drive(goal=(1.0, 2.0, 0.5))
assert time.time() - t0 < 0.5, time.time() - t0
real_start, fetch.DRIVE_START_S = fetch.DRIVE_START_S, 0.3                  # elsewhere: an old "succeeded", wait
t0 = time.time()
fetch._wait_drive(goal=(1.0, 2.0, 1.5))
assert time.time() - t0 >= 0.3
fetch.DRIVE_START_S, fetch.agv.status = real_start, real_agv_status
# ... a head move and a joy_control drive don't sleep; frames from after them are what is read next
t0 = time.time()
fetch._straight(0.01, 1.0)
assert time.time() - t0 < 0.2 and skills.moved_at["torso"] > t0, skills.moved_at

# ---------- measure-axis pairs each object once: two cups before, one after ----------
b2 = [{"name": "cup", "x": -211.5, "y": 1332.0}, {"name": "cup", "x": 9.0, "y": 1301.0}]
assert fetch._pairs(b2, [{"name": "cup", "x": 36.0, "y": 1202.0}]) == [((9.0, 1301.0), (36.0, 1202.0), "cup")]

# ---------- the waist turned since measure-axis: the arm frame turns with it about the base centre ----------
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2, "arm_xy_in_base_m": [0.1, 0.0], "waist_deg": -5.0}))
assert abs(fetch.arm_yaw() - (-96.2)) < 1e-9                                 # the fake waist reads -15
assert np.allclose(fetch.arm_xy(), [0.1 * math.cos(math.radians(-10)), 0.1 * math.sin(math.radians(-10))])
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2}))      # not recorded: as measured
assert fetch.arm_yaw() == -86.2
fetch.CALIB_FILE.unlink()

# the gripper finger between flange and grasp point is the hand itself, not something in its way
grip = [np.array([-38.0, 329.0, 146.0]), np.array([-283.0, 281.0, 50.0]), np.array([-289.0, 282.0, -9.0])]
assert fetch._near_hand([-119.0, 359.0, 61.0], grip) < fetch.SELF_MM < fetch._near_hand([-119.0, 600.0, 61.0], grip)

# ---------- never a base move with the waist turned ----------
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -86.2, "waist_deg": -15.0}))   # the front: -15
waist = {"deg": -15.0}
real_status, real_move = fetch.head.status, fetch.head.moveto
real_blocked, real_find_any = fetch._sweep_blocked, fetch._find_any
fetch.head.status = lambda: [75.0, waist["deg"], *fetch.HEAD_AHEAD]
fetch.head.moveto = lambda pos, **kw: waist.update(deg=pos[1])
fetch._sweep_blocked = lambda deg, what: round(fetch._waist_turn() + deg) in blocked          # by where it would end
waist["deg"], blocked = 45.0, {0}
try:                                                                       # the way back is blocked: no base move
    fetch._drive_to({"marker": "p1"}, None)
    raise AssertionError("drove with the waist turned")
except fetch.FetchError:
    pass
blocked.clear()
calls.clear()
fetch._drive_to({"marker": "p1"}, None)
assert waist["deg"] == -15.0 and ("go", "p1") in calls                      # the waist turned back first
fetch.head.status, fetch.head.moveto, fetch._sweep_blocked, fetch._find_any = real_status, real_move, real_blocked, real_find_any
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
        assert st["status"] == "failed" and "not where I saw" not in st["log"][-1] and len(turns) >= 2, st["log"]   # the whole search
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
fetch.motion.poses = lambda: {"ready": [0] * 6, "carry": [3] * 6, "look": [0] * 6, "give": [-6] * 6}
fetch.GIVE_WAIT_S = 0.3
reset()
st = run(fetch.start, ok)
assert st["status"] == "holding", st
calls.clear()
st = run(fetch.give)                                                       # nobody says thank you: kept
assert st["status"] == "holding" and st["holding"] and ("open",) not in calls, (st, calls)
assert calls.count(("line", "straight")) == 4 and poses() == ["carry", "give", "carry", "look"], calls   # look ->
                                                                           # carry -> give -> carry -> look, straight
fetch.GIVE_WAIT_S = 5.0
threading.Timer(0.2, fetch.release_now).start()                            # "thank you" / Release
st = run(fetch.give)
assert st["status"] == "done" and not st["holding"] and ("open",) in calls, (st, calls)
fetch.motion.poses = lambda: {"ready": [0] * 6, "carry": [3] * 6, "look": [0] * 6}

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
arm.update(j=[0.5] * 6)                                                       # at look: the route is look -> carry
calls.clear()
try:
    fetch._pose("carry", holding=True)
    raise AssertionError("tilted move accepted")
except fetch.FetchError as e:
    assert not calls and e.args == fetch.arm_route.SPILL, (calls, e.args)
tilt["rpy"] = up_rpy
fetch._pose("carry", holding=True)
assert calls == [("pose", "carry")], calls

# ---------- height check: a pose move must not take the gripper down to the table on the way ----------
skills._ask = lambda name, **a: {"errorCode": "0", "cartPosition": [0, 0, -500.0 if 0 < a["jointPosition"][0] < 10 else 0.0]
                                 + up_rpy}
fetch.motion.poses = lambda: {"look": [0] * 6, "carry": [10.0] + [0] * 5}
arm.update(j=[0.0] * 6)
calls.clear()
try:
    fetch._pose("carry")
    raise AssertionError("move down to the table accepted")
except fetch.FetchError as e:
    assert not calls and e.args == fetch.arm_route.BLOCKED, (calls, e.args)
skills._ask = lambda name, **a: {"errorCode": "0", "cartPosition": [0, 0, 0] + up_rpy}
fetch._pose("carry")
assert calls == [("pose", "carry")], calls
fetch._pose("carry")                                                          # there already: no move
assert calls == [("pose", "carry")], calls
fetch.motion.poses = lambda: {"ready": [0] * 6, "carry": [3] * 6, "look": [0] * 6}
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
# ---------- missions (docs/17): steps in order, moves checked, receive by the finger sensor ----------
fetch.motion.poses = lambda: {"ready": [0] * 6, "carry": [3] * 6, "look": [0] * 6, "give": [-6] * 6}
fetch.MOVE_SPEED, fetch.RECEIVE_DI_S, fetch.GIVE_POLL_S = 100.0, 0.05, 0.01
real_state, real_close = fetch.gripper.state, fetch.gripper.close
fetch.gripper.state = lambda: {**hand, "object_in_front": hand.get("front", False),
                               "ai": [3500 if hand["holding"] else 160], "di": [int(hand.get("front", False))]}
fetch.gripper.close = lambda wait=True: (calls.append(("close",)), hand.update(holding=hand.get("front", False),
                                                                               closed=True), fetch.gripper.state())[-1]
said = []
say = lambda en, ko: said.append(en)
P = lambda **k: k
reset()
skills._held.clear()
st = run(fetch.run_steps, [P(do="pick", object="apple", colour=None), P(do="move", dir="right", m=1.0),
                           P(do="place", on=None)], say)
names = [c[0] for c in calls]
assert st["status"] == "done" and not st["holding"], st
assert names.index("pick") < names.index("go_point") < names.index("joy") < names.index("place"), calls  # turn, drive
assert ("joy", "100.000") in calls and "Done." in said, (calls, said)
# receive: the hand held out, closes when the sensor sees something, the cup is carried on; place after it refused
reset()
hand["front"] = False
threading.Timer(0.1, lambda: hand.update(front=True)).start()
threading.Timer(0.4, fetch.release_now).start()            # the person lets go and says okay
st = run(fetch.run_steps, [P(do="go", to="p1"), P(do="receive", object="cup"), P(do="go", to="home")], say)
assert st["status"] == "holding" and st["holding"], st
assert [c for c in calls if c[0] in ("go", "close")] == [("go", "p1"), ("close",), ("go", "home")], calls
assert "give" in poses() and "Please put the cup in my hand, let go, and say okay." in said and \
    "Let go of it, then say okay." in said, said
# "okay" said at once (the sensor below the gripper never saw it): closes, AI_1 says holding
reset()
hand["front"] = False
threading.Timer(0.1, lambda: (hand.update(front=True), fetch.release_now())).start()   # fake: closing finds it
st = run(fetch.run_steps, [P(do="receive", object="cup")], say)
assert st["status"] == "holding" and ("close",) in calls, (st, calls)
fetch._set(holding=False, status="idle")
# okay, but the hand closed on nothing (a joke): opened again, said so, not holding
reset()
hand["front"] = False
said.clear()
threading.Timer(0.1, fetch.release_now).start()
st = run(fetch.run_steps, [P(do="receive", object="cup")], say)
assert st["status"] == "failed" and not st["holding"] and "nothing to take" in said[-1] and poses()[-1] == "look", \
    (st, said)
# "take this from my hand": the cameras see the hand empty -> said, nothing moves
real_scene = fetch._scene
scene = {"person_holds": False, "object_in_hand": None}
fetch._scene = lambda fn, *a: scene.get(fn)
reset()
said.clear()
st = run(fetch.run_steps, [P(do="receive", object="cup", from_hand=True)], say)
assert st["status"] == "failed" and not poses() and ("close",) not in calls and ("open",) not in calls and \
    "anything in your hand" in said[-1], (st, calls, said)
# ... the cameras see it in the hand 400 mm ahead of the give pose: the open hand reaches 150 mm towards it, then okay
scene.update(person_holds=True)
g0 = np.zeros(3) + calib.rpy_matrix(*up_rpy) @ skills.GRASP_OFFSET          # the fake flange is at the origin
scene["object_in_hand"] = {"name": "cup", "position_mm": [g0[0] + 400.0, g0[1], g0[2]]}
reach_to = []
real_line_rows = fetch._line_rows
fetch._line_rows = lambda target, label, start=None: reach_to.append((label, list(target))) or [[label, target, [0] * 6, None]]
reset()
hand["front"] = False
threading.Timer(0.1, lambda: (hand.update(front=True), fetch.release_now())).start()
st = run(fetch.run_steps, [P(do="receive", object="cup", from_hand=True)], say)
hand_moves = [t for l, t in reach_to if l == "to the hand"]
assert st["status"] == "holding" and "give" in poses() and len(hand_moves) == 1, (st, reach_to)
assert np.allclose(hand_moves[0][:3], [fetch.RECEIVE_REACH_MM, 0, 0]), hand_moves      # 150 of the 300 it could go
fetch._set(holding=False, status="idle")
# ... it is right in front of the hand already: no reach, still received; can't tell (None): received as before
scene["object_in_hand"] = {"name": "cup", "position_mm": [g0[0] + 50.0, g0[1], g0[2]]}
scene["person_holds"] = None
reach_to.clear()
reset()
threading.Timer(0.1, lambda: (hand.update(front=True), fetch.release_now())).start()
st = run(fetch.run_steps, [P(do="receive", object="cup", from_hand=True)], say)
assert st["status"] == "holding" and not [l for l, t in reach_to if l == "to the hand"], (st, reach_to)
fetch._set(holding=False, status="idle")
# "reach out to me": to give along the pose graph (via carry), then 150 mm towards their nearer seen hand
ahead = lambda mm, side=0.0: [g0[0] + mm, g0[1] + side, g0[2]]
scene["person_in_front"] = {"position_mm": ahead(900.0), "hands": {"left": {"position_mm": ahead(600.0, 100.0),
                            "distance_m": 1.1}, "right": {"position_mm": ahead(400.0), "distance_m": 0.9}}}
turns = []
real_waist_to = fetch._waist_to
fetch._waist_to = lambda deg: turns.append(deg) or deg < 90


def reached(angle=0.0):
    reach_to.clear()
    reset()
    st = run(fetch.reach, angle, say)
    return st, [t[:3] for l, t in reach_to if l == "to the hand"]


st, moves = reached()
assert st["status"] == "done" and poses() == ["carry", "give"] and not turns, (st, poses())
assert len(moves) == 1 and np.allclose(moves[0], [fetch.RECEIVE_REACH_MM, 0, 0]), moves
scene["person_in_front"]["hands"]["right"]["position_mm"] = ahead(180.0)          # stops RECEIVE_SHORT_MM before it
assert np.allclose(reached()[1][0], [80.0, 0, 0])
scene["person_in_front"]["hands"] = {"left": None, "right": {"position_mm": None, "distance_m": None}}
scene["person_in_front"]["position_mm"] = ahead(fetch.REACH_BODY_MM + 60.0)      # no hand seen: REACH_BODY_MM before
assert np.allclose(reached()[1][0], [60.0, 0, 0])                                 # the body
scene["person_in_front"]["position_mm"] = ahead(fetch.REACH_BODY_MM + 10.0)      # too short a move: left out
st, moves = reached()
assert st["status"] == "done" and poses()[-1] == "give" and not moves, (st, moves)
scene["person_in_front"] = None                                                   # nobody seen: the hand at give
st, moves = reached()
assert st["status"] == "done" and poses()[-1] == "give" and not moves, (st, moves)
st, moves = reached(40.0)                                     # to the side (Patrol): the waist turns first, by the
assert turns == [40.0 + fetch._waist_turn()] and poses()[-1] == "give", (turns, poses())   # waist's offset too
turns.clear()
said.clear()
st, moves = reached(120.0)                                    # the waist turn refused (sweep): the arm stays
assert st["status"] == "failed" and not poses() and said[-1] == fetch.TURN_TO_PERSON[0], (st, said)
turns.clear()
st, moves = reached(160.0)                                    # past the waist's limit (-15 + 160 > 140): stand in front
assert st["status"] == "failed" and not turns and not poses() and said[-1] == fetch.TURN_TO_PERSON[0], (st, turns)
fetch._waist_to = real_waist_to
fetch._line_rows, fetch._scene = real_line_rows, real_scene
hand["front"] = False
# the cup is in the hand but nobody says okay: the hand never closes (their fingers may be in it)
reset()
hand["front"], fetch.RECEIVE_WAIT_S = True, 0.3
st = run(fetch.run_steps, [P(do="receive", object="cup")], say)
assert st["status"] == "failed" and ("close",) not in calls, (st, calls)
fetch.RECEIVE_WAIT_S = 30.0
hand["front"] = False
fetch._set(holding=False, status="idle")
try:
    fetch.run_steps([P(do="receive", object="cup"), P(do="place", on=None)])
    raise AssertionError("put down something handed over (its height in the hand is not known)")
except fetch.FetchError:
    pass
# nobody puts anything in the hand: failed, the hand open
reset()
fetch.RECEIVE_WAIT_S = 0.2
st = run(fetch.run_steps, [P(do="receive", object="cup")], say)
assert st["status"] == "failed" and not st["holding"] and ("close",) not in calls and poses()[-1] == "look", (st, calls)
# a message is spoken as written; one of several markers; here = where it was given (no drive)
reset()
said.clear()
st = run(fetch.run_steps, [P(do="go", to=["p1", "home"]), P(do="say", text="Anvar says hello"), P(do="go", to="here")],
         say)
gone = [c for c in calls if c[0] in ("go", "go_point")]
assert st["status"] == "done" and len(gone) == 1 and gone[0][1] in ("p1", "home") and "Anvar says hello" in said, \
    (st, calls, said)
# a move that can't go the whole way: stopped short and said why; the held object is kept
reset()
room["clear"] = lambda x, y: 0.05 if x > 0.15 else 1.0
st = run(fetch.run_steps, [P(do="pick", object="apple", colour=None), P(do="move", dir="forward", m=1.0)], say)
assert st["status"] == "failed" and st["holding"] and "in my way" in said[-1], (st, said[-1:])
room["clear"] = lambda x, y: 1.0
fetch._set(holding=False, status="idle")
hand.update(holding=False, closed=False)
# steps that don't fit the hand are refused before anything moves
for bad in ([P(do="give")], [P(do="place", on=None)], [P(do="go", to="p9")], [P(do="move", dir="back", m=5.0)],
            [P(do="arm", pose="wave")], [P(do="turn", deg=720)]):
    calls.clear()
    try:
        fetch.run_steps(bad)
        raise AssertionError(f"started {bad}")
    except fetch.FetchError:
        assert not any(c[0] in ("go", "go_point", "joy", "pose") for c in calls), calls
# a move is driven in pieces, each checked again; back on the charger is refused
reset()
hold, fetch.JOY_HOLD_S = fetch.JOY_HOLD_S, 0.0005      # at this fake 100 m/s a real hold would roll the whole way
st = run(fetch.run_steps, [P(do="move", dir="forward", m=0.6)], say)
fetch.JOY_HOLD_S = hold
assert st["status"] == "done" and [c for c in calls if c[0] == "joy"].count(("joy", "100.000")) == 3, calls  # 0.25+0.25+0.1
fetch.agv.status = lambda: {"move_status": "succeeded", "charge_state": True}
st = run(fetch.run_steps, [P(do="move", dir="back", m=0.5)], say)
assert st["status"] == "failed" and "charger" in said[-1] and not any(c[0] == "joy" for c in calls), (st, said[-1:])
fetch.agv.status = fake_status
# "the white table on your left": turn left first, then that table by colour (not any table)
reset()
seen_things = []
fetch._put_on = lambda top, on, say_: (seen_things.append(on), fetch._set(holding=False), True)[-1]
st = run(fetch.run_steps, [P(do="pick", object="apple", colour=None),
                           P(do="place", on={"name": "dining table", "colour": "white", "side": "left"})], say)
assert st["status"] == "done" and seen_things and seen_things[0]["colour"] == "white", (st, seen_things)
assert any(c[0] == "go_point" for c in calls), calls                                   # the turn left
# someone talks to Lumi on the way: the drive halts, waits, then goes on to the same goal; a move goes the rest
reset()
base["on_poll"] = lambda: fetch.pause() if base["polls"] == 2 else None
threading.Timer(0.3, fetch.resume).start()
st = run(fetch.run_steps, [P(do="go", to="p1"), P(do="move", dir="forward", m=0.5)], say)
assert st["status"] == "done" and [c for c in calls if c[0] == "go"] == [("go", "p1"), ("go", "p1")], calls
assert ("cancel",) in calls and not fetch.paused(), calls
reset()
fetch.MOVE_SPEED = 0.5                               # 0.25 m pieces take 0.5 s: time to pause inside one
threading.Timer(0.2, fetch.pause).start()
threading.Timer(0.6, fetch.resume).start()
st = run(fetch.run_steps, [P(do="move", dir="forward", m=0.5)], say)
assert st["status"] == "done" and any("paused" in l for l in st["log"]), st
fetch.MOVE_SPEED = 100.0
# STOP while paused ends it
reset()
base["on_poll"] = lambda: fetch.pause() if base["polls"] == 2 else None
threading.Timer(0.3, fetch.stop).start()
st = run(fetch.run_steps, [P(do="go", to="p1")], say)
assert st["status"] == "stopped", st
fetch.gripper.state, fetch.gripper.close = real_state, real_close

# what Lumi holds is kept from the pick until the hand opens ("Put the white cup on the table")
fetch._set(holding=True, held_object={"object": "cup", "colour": "white"}, task={"steps": []})
assert fetch.held_name() == "the white cup"
fetch._set(task={"steps": [{"do": "go", "to": "exit"}]}, status="holding")   # another task: still held
assert fetch.held_name() == "the white cup"
fetch._state.update(holding=False, held_object=None)                        # a restarted process: from the file
fetch._adopt()
assert fetch._state["held_object"] == {"object": "cup", "colour": "white"} and fetch.held_name() == "the white cup"
fetch._set(holding=False)                                                    # put down / given / dropped
assert fetch.held_name() == "something" and fetch.state()["held_object"] is None
skills._held["what"] = {"object": "cup", "colour": "white"}                  # picked, then the state lost the name
fetch._set(holding=True)                                                     # (taken over from the hand)
assert fetch.held_name() == "the white cup"
fetch._set(holding=False)
skills._held.clear()
# one hand read said empty with the cup still in it (live 2026-10-26 18:53:00): the name and the put-down data come
# back when the hand is seen holding again, on every path (the dashboard's check, a fetch, place / give, a mission)
def forgot():
    reset()
    fetch._set(holding=True, held_object={"object": "cup", "colour": "white"}, status="holding")
    skills._held.update(top_mm=-260.0, x=-150.0, y=600.0, table=-403.0, what={"object": "cup", "colour": "white"})
    hand.update(holding=False, closed=False)
    fetch.check_hand()                                                       # the false "empty"
    assert fetch.held_name() == "something" and not skills._held
    hand.update(holding=True, closed=True)


forgot()
assert fetch.check_hand() and fetch.held_name() == "the white cup" and fetch.held_name("ko") == "흰 컵"
forgot()
try:
    fetch.start(ok)
    raise AssertionError("a fetch while holding")
except fetch.FetchError as e:
    assert e.args[0] == "I'm holding the white cup, where should I put it first?", e.args
forgot()
st = run(fetch.place)                                                        # put down needs its height: back too
assert st["status"] == "done" and ("place",) in calls, st["log"]
forgot()
named = []
real_give = fetch._give
fetch._give = lambda say: (named.append(fetch.held_name()), fetch._set(holding=False), skills._held.clear())[-1]
st = run(fetch.run_steps, [{"do": "give"}])
fetch._give = real_give
assert st["status"] == "done" and named == ["the white cup"], (st["log"], named)
fetch.held_by_skill({"object": "cup", "colour": "white"})                 # a voice pick (skills.pick, not a fetch)
assert fetch.state()["held_object"] == {"object": "cup", "colour": "white"} and fetch.state()["status"] == "holding"
assert fetch.held_name() == "the white cup" and skills._held["what"]["object"] == "cup"
fetch._set(holding=True, held_object={"object": "cup", "colour": "white"})
assert fetch.held_name("ko") == "흰 컵"
fetch._set(holding=True, held_object={"object": "bottle", "colour": None})
assert fetch.held_name("ko") == "병" and fetch.held_name() == "the bottle", fetch.held_name("ko")
fetch._set(holding=False)
assert fetch.held_name("ko") == "물건"
skills._held.clear()
hand.update(holding=False, closed=False)
fetch._set(status="idle")

# the straight line to carry ending on the other wrist branch (the same pose, pick:502) is no carry: carry_up decides
real_rows, real_up = fetch._line_rows, skills.carry_up
wp = [("above", [0.0] * 6)]
fetch._line_rows = lambda target, label, start=None: [["to carry 20", target, [3.0] * 6, None]]
skills.carry_up = lambda above, ja: None
assert fetch._carry_ok(wp, [0.0] * 6)                                       # ends at carry's own joints
fetch._line_rows = lambda target, label, start=None: [["to carry 20", target, [3.0, 3.0, 3.0, 183.0, -3.0, 183.0], None]]
assert not fetch._carry_ok(wp, [0.0] * 6)                                   # the other branch, carry_up refuses
skills.carry_up = lambda above, ja: ([0.0] * 6, [3.0] * 6)
assert fetch._carry_ok(wp, [0.0] * 6)                                       # ... or takes it by a joint move
fetch._line_rows, skills.carry_up = real_rows, real_up

# a put down gives up after PLACE_REFUSALS refused spots in a row (each costs IK time; two puts timed out, X1)
asked = []
real_opts = skills.place_options
skills.place_options = lambda x, y, top, start: (asked.append((x, y)), iter(()))[1]
fetch._line_rows = lambda target, label, start=None: (_ for _ in ()).throw(fetch.FetchError("no"))
skills._held.update(top_mm=-260.0)
assert fetch._place_at([(-100.0 - 10 * k, 640.0) for k in range(20)], -260.0) is None
assert len(asked) == fetch.PLACE_REFUSALS, asked
fetch._line_rows, skills.place_options = real_rows, real_opts
skills._held.clear()

# the lift is never asked above its limit (head camera cable, robot/head.py LIFT_MAX_MM)
assert max(fetch.LIFT_RANGE + fetch.LIFT_TRIES + (fetch.LIFT_DRIVE_MM,)) <= fetch.head.LIFT_MAX_MM == 105.0
assert fetch.head.AXIS_LIMITS[0] == (0.0, fetch.head.LIFT_MAX_MM)
body["lift"] = 75.0
assert all(fetch.lift_for(z) is None or fetch.lift_for(z) <= 105.0 for z in range(-700, 0, 10))
fetch._clear()
fetch._lift_to(250.0)
assert body["lift"] == 105.0, body
# a drive starts with the head looking ahead, wherever it was turned
moves, real_status, real_move = [], fetch.head.status, fetch.head.moveto
fetch.head.status = lambda: [75.0, -15.0, -120.0, 20.0]
fetch.head.moveto = lambda pos, **kw: moves.append(list(pos))
fetch.head_ahead()
assert moves == [[75.0, -15.0, *fetch.HEAD_AHEAD]], moves
fetch.head.status, fetch.head.moveto = real_status, real_move

# ---------- objects the fingers can't take: refused in words, before anything moves ----------
assert "break" in fetch.validate({**ok, "object": "wine glass"}, MARKERS)[0]
assert "thin" in fetch.validate({**ok, "object": "banana"}, MARKERS)[0]
assert fetch.validate({**ok, "object": "giraffe"}, MARKERS)[0].startswith("Which object? I can pick up cup, apple")
assert all(fetch.validate({**ok, "object": n}, MARKERS) == [] for n in fetch.PICKABLE)
assert fetch.describe({**ok, "object": "sports ball"}, "ko").startswith("p1 위치에서 공을")
reset()
said.clear()
try:                                         # steps.check refuses it before the mission starts (read-back included)
    st = run(fetch.run_steps, [P(do="pick", object="wine glass", colour=None)], say)
    assert st["status"] == "failed" and "break" in said[-1], (st, said)
except fetch.FetchError as e:
    assert "break" in str(e), e
assert not any(c[0] in ("pick", "go_point", "find") for c in calls), calls

# ---------- several of them: the chosen one out of reach (or the wrong size) -> another one here that is not ----------
FAR = {**CUP, "x": -150.0, "y": 600.0}
NEAR = {**CUP, "x": 60.0, "y": 560.0}
skills.look = lambda frames=None, **kw: [FAR, NEAR]
found["obj"] = FAR
skills.reachable_pick = lambda obj, start=None, accept=None, max_yaw=None: (skills.plan_pick(obj), [0.0] * 6) if obj["x"] > 0 else None
reset()
found["obj"] = FAR
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
assert st["status"] == "holding" and any("instead" in l for l in st["log"]) and not any(c[0] == "go_point" for c in calls), \
    (st["log"][-6:], calls)
fetch._set(holding=False, status="idle")
skills._held.clear()
def too_big(obj, start=None, accept=None, max_yaw=None):
    if obj["x"] < 0:
        raise skills.SkillError("The apple is too big for my hand.")
    return skills.plan_pick(obj), [0.0] * 6
skills.reachable_pick = too_big
reset()
found["obj"] = FAR
st = run(fetch.start, {**ok, "source": "here", "dest": "here"})
assert st["status"] == "holding", st["log"][-6:]
fetch._set(holding=False, status="idle")
skills._held.clear()
reset()                                                                      # "the one on the left": only that one
found["obj"] = FAR
st = run(fetch.start, {**ok, "source": "here", "dest": "here", "prefer": "left"})
assert st["status"] == "failed" and "too big" in st["log"][-1], st["log"][-3:]
skills.reachable_pick, skills.look = fake_reachable, (lambda frames=None, **kw: [])

# ---------- a miss: open, back at look, found and tried once more; a second miss fails ----------
misses = {"n": 1}
def miss_once(obj, wp, ja):
    if misses["n"]:
        misses["n"] -= 1
        raise skills.SkillError("I missed it.")
    fake_pick(obj, wp, ja)
skills._do_pick = miss_once
reset()
said.clear()
st = run(fetch.start, {**ok, "source": "here", "dest": "here"}, say)
assert st["status"] == "holding" and "I missed it. Let me try again." in said and \
    [c[0] for c in calls].count("find") >= 2, (st, said)
fetch._set(holding=False, status="idle")
skills._held.clear()
misses["n"] = 2
reset()
st = run(fetch.start, {**ok, "source": "here", "dest": "here"}, say)
assert st["status"] == "failed" and "missed" in st["log"][-1] and not st["holding"], st["log"][-3:]
skills._do_pick = fake_pick

# ---------- "put it here" with a pointing hand: the free table spot nearest the point; no point: ask ----------
real_scene, real_on_table = fetch._scene, skills.on_table
point = {"pointing_target": {"position_mm": [-120.0, 690.0, -403.0]}}
fetch._scene = lambda fn, *a: point.get(fn)
skills.on_table = lambda spots, table: list(spots)
reset()
run(fetch.start, {**ok, "source": "here", "dest": "here"})
st = run(fetch.place, None, {"pointed": True})
put = [l for l in st["log"] if "putting it down at" in l]
assert st["status"] == "done" and not st["holding"] and put and put[0].endswith("(-120, 690)"), st["log"][-5:]
reset()
run(fetch.start, {**ok, "source": "here", "dest": "here"})
point["pointing_target"] = None
st = run(fetch.place, None, {"pointed": True})
assert st["status"] == "failed" and st["holding"] and "Where should I put it?" in st["log"][-1], st["log"][-3:]
fetch._set(holding=False, status="idle")
skills._held.clear()
fetch._scene, skills.on_table = real_scene, real_on_table

print("fetch ok")
