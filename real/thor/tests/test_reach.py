"""Self-check of the arm's reach planning with the offline kinematics (robot/kinematics.py), no robot:
python tests/test_reach.py

Cups the arm reaches from where Lumi stands are planned, from any grasp turn and IK seed; cups beside it are reached
by a waist turn first; cups out of reach of every waist turn still go to the base move / asking. The positions of the
live cases are from logs/api.log (2026-10-2x): the one picked, and the ones refused then."""
import math

import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from robot import kinematics, motion
from manipulation import arm_route, skills
from tasks import fetch

# ---------- the offline kinematics: the controller's own answers ----------
SAMPLES = (                                                 # joints, the flange pose the controller reported (calibration
    ([87.074, -80.539, -21.134, 0.608, -113.653, -47.948],  # samples of the torso and the head camera; the samples
     [47.777, 320.575, -20.839, 86.777, 45.757, -57.042]),  # themselves stay on the Thor)
    ([69.322, -78.233, -38.969, -5.131, -100.011, -69.562],
     [6.08, 270.561, -123.566, 77.877, 51.571, -62.655]),
    ([101.531, -72.825, 6.01, 5.321, -102.275, -53.297],
     [174.924, 414.109, 93.127, 72.719, 64.842, -115.343]),
    ([-272.27, -100.091, -8.001, 234.453, 83.508, 134.594],
     [-9.389, 400.198, 107.353, 31.332, 18.372, -113.47]),
    ([-260.075, -97.103, -25.513, 228.746, 69.866, 129.55],
     [-66.288, 354.894, 170.458, 37.788, 29.511, -109.309]),
    (skills.TEACH["joints"], skills.TEACH["flange"]))       # the taught grasp
for j, p in SAMPLES:
    T = kinematics.fk(j)
    R = skills.calib.rpy_matrix(*p[3:])
    assert np.linalg.norm(T[:3, 3] - p[:3]) < 0.5 and np.degrees(np.arccos(min(1.0, (np.trace(T[:3, :3].T @ R) - 1) / 2))) < 0.1, j
HEAD = np.array([-92.97, -19.87, 356.12])                  # the head's turning centre (vision/head_cam.py fit 2026-10-19)
arm_route.head_cam.head_centre = lambda: HEAD
for name, j in motion.poses().items():                     # IK from a seed 8 deg off: the same flange pose
    p = kinematics.pose(j)
    s = kinematics.ik(p, [a + 8.0 for a in j])
    assert s is not None and np.allclose(kinematics.pose(s)[:3], p[:3], atol=0.05), name
assert kinematics.ask("kine_inverse", jointPosition=[0.0] * 6, cartPosition=[3000.0, 0, 0, 0, 0, 0])["errorCode"] != "0"

# ---------- picks from look, offline IK, every check fetch uses (carry line, head, joint limits) ----------
skills._ask = kinematics.ask
LOOK = motion.poses()["look"]
skills._joints = lambda: list(LOOK)
lines = []
fetch.log = skills.log = arm_route.log = lambda *a: lines.append(" ".join(str(x) for x in a))
cup = lambda x, y, top=-260.0: {"name": "cup", "colour": "grey", "x": float(x), "y": float(y), "top_mm": top,
                                "width_mm": 72.0, "seen": 8, "spread": 1.0}
reach = lambda o: skills.reachable_pick(o, accept=fetch._carry_ok)
trusted = lambda o: skills.reachable_pick(o, accept=fetch._carry_ok, max_yaw=skills.TRUSTED_YAW_DEG)   # fetch's first try

plan = reach(cup(-96, 598))                                  # picked live 2026-10-2x 15:39 (J5 +20, no turn): now
assert plan and round(skills.yaw_of(plan[0][1][1])) == -15, plan   # no IK at the grasp unturned there; -15 is trusted
for xy in ((-171, 697), (-395, 629), (-480, 652)):          # refused live from where it stood: still out of reach
    assert reach(cup(*xy)) is None, xy                      # of the arm alone at waist 0 (base moved then)

# 2026-10-26 18:40 at lift 0: (260, 722) top -186 was planned turned -30 deg, J5 +26 (missed live, as every turn
# over 15 deg). Offline now -30 has no IK at the grasp there: turned -45, J5 +12; within the trusted turns there is
# none from here (the waist or the base first)
plan = reach(cup(260, 722, -186))
assert plan and round(skills.yaw_of(plan[0][1][1])) == -45 and 10 < plan[1][4] < 20, plan
assert skills.reachable_pick(cup(260, 722, -186), accept=fetch._carry_ok, max_yaw=skills.TRUSTED_YAW_DEG) is None

# 17:57 / 18:45: (-104, 694) and (-99, 738) top -186: every straight line to carry refused live (a joint jumps).
# With the camera's error fixed both are past the arm's reach from here at this height (it ends near y 660 straight
# ahead): a waist turn or the base first (LIVE below)
def line_ok(w, ja):                                         # the straight line alone (fetch._carry_ok also takes carry_up)
    try:
        fetch._line_rows(kinematics.pose(motion.poses()["carry"]), "to carry", start=(w[0][1], ja))
        return True
    except fetch.FetchError:
        return False
for seen in ((-104, 694), (-99, 738)):                     # seen live before the camera's error was fixed
    xy = np.add(seen, skills.objects.ROUND_FIX_MM)
    assert skills.reachable_pick(cup(*xy, -186), accept=line_ok) is None, xy
    assert not list(skills.pick_options(cup(*xy, -186), list(LOOK), skills.TRUSTED_YAW_DEG)), xy
# just inside the trusted reach: straight up and one joint move to carry takes the cup there too (upright, clear of
# the head)
plan = skills.reachable_pick(cup(-92, 640, -186), accept=lambda w, ja: skills.carry_up(w[0][1], ja) is not None,
                             max_yaw=skills.TRUSTED_YAW_DEG)
assert plan and abs(skills.yaw_of(plan[0][1][1])) <= 15.5, plan
via, carry = skills.carry_up(plan[0][0][1], plan[1])
assert via[2] > plan[0][0][1][2] and np.allclose(kinematics.pose(carry)[:3], kinematics.pose(motion.poses()["carry"])[:3], atol=0.1)

# a held IK answer with J4 one turn round (the same pose) is not a joint-limit or flip refusal
real_ask = skills._ask
def turned_j4(name, **a):
    r = real_ask(name, **a)
    if name == "kine_inverse" and r["errorCode"] == "0":
        r["jointPosition"][3] += 360.0 if r["jointPosition"][3] < 0 else -360.0
    return r
skills._ask = turned_j4
assert reach(cup(-96, 598))
skills._ask = real_ask

# the joint move out to above the cup is checked against the head: a head on the way refuses it
real_centre = arm_route.head_cam.head_centre
start, ja = list(LOOK), plan[1]
assert skills.move_ok(start, ja)
mid = kinematics.pose([(a + b) / 2 for a, b in zip(start, motion.nearest(ja, start))])
arm_route.head_cam.head_centre = lambda: np.array(mid[:3])
assert not skills.move_ok(start, ja)
arm_route.head_cam.head_centre = lambda: None              # the head's place unknown: no move
assert not skills.move_ok(start, ja)
arm_route.head_cam.head_centre = real_centre

# ---------- waist turns: the arm reaches round the column ----------
C = arm_route.head_cam.head_centre()[:2]
body = {"waist": -20.31}                                    # the waist of measure-axis = the front
fetch.head.status = lambda: [75.0, body["waist"], 0.0, -5.0]
around = lambda r, b: cup(C[0] - r * math.sin(math.radians(b)), C[1] + r * math.cos(math.radians(b)))

o = cup(-300, 400)
t = fetch.turned(o, 30.0)                                   # turned about the column: same distance from it
assert np.isclose(np.hypot(*(np.subtract((t["x"], t["y"]), C))), np.hypot(*(np.subtract((o["x"], o["y"]), C))))
assert t["x"] > o["x"]                                      # waist left: a thing on the left comes ahead
assert np.allclose([fetch.turned(t, -30.0)[k] for k in "xy"], [o[k] for k in "xy"])

for r, b in ((600, 60), (600, -60), (550, 90), (600, -100), (660, 7), (660, 25)):   # beside it and near the edge
    # (the trusted reach round the column ends near 670 mm: the live 730 mm ones are past it)
    o = around(r, b)
    assert trusted(o) is None, (r, b)                         # not from here ...
    turns = fetch.waist_for(o)
    assert turns and any(trusted(fetch.turned(o, d)) for d in turns), (r, b, turns)   # ... after a waist turn
    assert abs(turns[0] - (b - math.degrees(math.atan2(-(fetch.PICK_ZONE_CENTRE[0] - C[0]),
                                                       fetch.PICK_ZONE_CENTRE[1] - C[1])))) < 1e-6
for r, b in ((1000, 0), (950, 40)):                         # too far for any waist turn: the base has to move
    o = around(r, b)
    assert all(trusted(fetch.turned(o, d)) is None for d in fetch.waist_for(o)), (r, b)
# the live cases of 2026-10-26 with trusted turns only: from here, after a waist turn, or the base moves (none)
LIVE = (((262, 774, -189), "base"), ((267, 763, -188), "base"), ((260, 722, -186), "base"),   # missed at -45 / -30
        ((300, 621, -191), "base"), ((-99, 738, -181), "base"),         # missed at -30 / carry line jumped at -30
        ((-141, 869, -186), "base"), ((-117, 960, -186), "base"),       # across the table / far
        ((-104, 694, -186), "waist"), ((-73, 588, -186), "here"), ((-96, 598, -260), "here"))   # carried / picked
# (the trusted reach round the column ends near 670 mm: 621 and 738, ~756 mm from it, need the base; 694 a waist turn)
for (x, y, top), how in LIVE:                               # seen before the camera's error was fixed
    o = cup(x + skills.objects.ROUND_FIX_MM[0], y + skills.objects.ROUND_FIX_MM[1], top)
    got = "here" if trusted(o) else "waist" if any(trusted(fetch.turned(o, d)) for d in fetch.waist_for(o)) else "base"
    assert got == how, ((x, y, top), got, how)
body["waist"] = 100.0                                       # the waist near its limit (140): no turn past it
assert all(body["waist"] + d <= 140.0 for d in fetch.waist_for(around(600, 80)))
body["waist"] = -20.31

# ---------- _reach: a waist turn before any base move; a cup no turn reaches still moves the base ----------
calls = []
fetch._step = lambda name, say=None, *a: calls.append(("step", name))
fetch._pose = lambda name, *a, **k: None
fetch._charging = lambda: False
fetch._other_here = lambda task, obj: None
fetch.arm_yaw = lambda: -95.5
fetch.remember = lambda obj, yaw: {}
fetch.agv.pose = lambda: (0.0, 0.0, 0.0)
def waist_to(rel, in_place=False):
    calls.append(("waist", round(rel)))
    body["waist"] = -20.31 + rel
    return True
fetch._waist_to = waist_to
scene = {"cup": None}                                       # the cup where it stands, in the arm frame at waist 0
skills.look = lambda *a, **k: [fetch.turned(scene["cup"], body["waist"] + 20.31)]
class Moved(Exception):
    pass
def approach(obj, yaw, tried, **kw):
    calls.append(("base",))
    raise Moved()
fetch._approach = approach
task = {"object": "cup", "colour": None}

scene["cup"] = around(600, 70)                              # on the left: the waist turns, no base move
got = fetch._reach(task, scene["cup"], None)
assert got and ("base",) not in calls and calls[0] == ("step", "turning my waist to reach it"), calls
assert any(c[0] == "waist" for c in calls) and got[0]["x"] == fetch.turned(scene["cup"], body["waist"] + 20.31)["x"]

calls.clear()
body["waist"] = -20.31
scene["cup"] = around(1000, 0)                              # too far: no waist turn reaches it, the base moves
try:
    fetch._reach(task, scene["cup"], None)
    raise AssertionError("no base move")
except Moved:
    pass
assert ("base",) in calls and not any(c[0] == "waist" for c in calls), calls

calls.clear()
scene["cup"] = around(600, -70)                             # the cup was moved away while the waist turned
skills.look = lambda *a, **k: []
assert fetch._waist_reach(task, scene["cup"], None) is None and any(c[0] == "waist" for c in calls)
# ---------- put down: where no joint move from look keeps the cup upright, a straight line to above the spot does
skills._held.clear()
skills._held.update(top_mm=-300.0, yaw=0.0, tips=False, below=40.0)
opts = list(skills.place_options(200.0, 500.0, -300.0, list(LOOK)))
# (one joint move there keeps the cup within MAX_TILT_DEG too: it comes first, the straight lines after it)
straight = [(w, ja) for w, ja in opts if w[0][0] == "above place (straight)"]
assert straight and all(w[0][0] in ("above place", "above place (straight)") for w, _ in opts), [w[0][0] for w, _ in opts]
way, ja = straight[0]
assert np.allclose(kinematics.pose(ja)[:3], way[0][1][:3], atol=0.05)
moved = []
real_lin, real_jm, real_place = skills.motion.move_linear, skills.motion.move_joints, skills._do_place
skills.motion.move_linear = lambda **k: moved.append(("line", k["target"]))
skills.motion.move_joints = lambda j, s: moved.append(("joints", j))
skills._do_place = lambda w: moved.append(("down",))
skills.place_turned(way, ja)
assert moved[0] == ("line", way[0][1]) and moved[1] == ("down",), moved
skills.motion.move_linear, skills.motion.move_joints, skills._do_place = real_lin, real_jm, real_place

# the live puts of 2026-10-26 18:51-18:56 (lift 0, cup top -186 on a table at -336): put down at (-43, 618) with no
# turn, as live; (-349, 647) beside it and the far table point (-213, 797) are out of reach from where it stood
skills._held.update(top_mm=-186.0, yaw=0.0, tips=False, below=40.0)
got = next(skills.place_options(-43.0, 618.0, -183.0, list(LOOK)), None)
assert got and abs(skills.yaw_of(got[0][1][1])) < 1, got
for xy in ((-349.0, 647.0), (-213.0, 797.0)):
    assert next(skills.place_options(*xy, -183.0, list(LOOK)), None) is None, xy

# ---------- the controller confirms only the chosen plan (a stand-in behind arm.cmd here) ----------
asked, shift = [], {"mm": 0.0}
def controller(name, **a):
    asked.append(name)
    r = kinematics.ask(name, **a)
    if name == "kine_forward":
        r["cartPosition"][0] += shift["mm"]
    return r
real_cmd = skills.arm.cmd
skills.arm.cmd = skills._ARM_CMD = controller
skills._ask = skills._ASK                                    # planning offline, only confirm() asks the "controller"
skills.home_joints = lambda: list(LOOK)
assert reach(cup(-96, 598)) and sorted(asked) == ["kine_forward", "kine_inverse"], asked
shift["mm"] = 5.0                                           # the controller disagrees with the offline model: no plan
assert reach(cup(-96, 598)) is None and any("the controller puts" in l for l in lines)
skills.arm.cmd = skills._ARM_CMD = real_cmd
print("reach ok")
