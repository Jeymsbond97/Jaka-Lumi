"""Self-check of the arm's reach planning with the offline kinematics (robot/kinematics.py), no robot:
python tests/test_reach.py

Cups the arm reaches from where Lumi stands are planned, from any grasp turn and IK seed; cups beside it are reached
by a waist turn first; cups out of reach of every waist turn still go to the base move / asking. The positions of the
live cases are from logs/api.log (2026-10-2x): the one picked, and the ones refused then."""
import math

import numpy as np

from robot import kinematics, motion
from manipulation import arm_route, skills
from tasks import fetch

# ---------- the offline kinematics: the controller's own answers ----------
mm, deg = kinematics.errors()
assert mm < 0.5 and deg < 0.1, (mm, deg)
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
                                "width_mm": 76.0, "seen": 8, "spread": 1.0}
reach = lambda o: skills.reachable_pick(o, accept=fetch._carry_ok)

plan = reach(cup(-96, 598))                                  # picked live 2026-10-2x 15:39 (J5 +20, no turn)
assert plan and abs(skills.yaw_of(plan[0][1][1])) < 1, plan
for xy in ((-171, 697), (-395, 629), (-480, 652)):          # refused live from where it stood: still out of reach
    assert reach(cup(*xy)) is None, xy                      # of the arm alone at waist 0 (base moved then)

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

for r, b in ((600, 60), (600, -60), (550, 90), (600, -100), (730, 7), (720, 25)):   # beside it and the live ones
    o = around(r, b)
    assert reach(o) is None, (r, b)                         # not from here ...
    turns = fetch.waist_for(o)
    assert turns and any(reach(fetch.turned(o, d)) for d in turns), (r, b, turns)   # ... after a waist turn
    assert abs(turns[0] - (b - math.degrees(math.atan2(-(fetch.PICK_ZONE_CENTRE[0] - C[0]),
                                                       fetch.PICK_ZONE_CENTRE[1] - C[1])))) < 1e-6
for r, b in ((1000, 0), (950, 40)):                         # too far for any waist turn: the base has to move
    o = around(r, b)
    assert all(reach(fetch.turned(o, d)) is None for d in fetch.waist_for(o)), (r, b)
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
def waist_to(rel):
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
print("reach ok")
