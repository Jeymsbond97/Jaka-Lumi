"""Self-check of the skills.py geometry, no robot: python tests/test_skills.py"""
import numpy as np

from vision import calib
from manipulation import skills

cup = {"name": "cup", "colour": "white", "x": -126.5, "y": 613.0, "top_mm": -261.0, "width_mm": 76.0}
R = calib.rpy_matrix(*skills.GRASP_RPY)
g = np.array([cup["x"], cup["y"], cup["top_mm"] - 40])

(n1, above), (n2, grasp), (n3, lift) = skills.plan_pick(cup)
assert np.allclose(grasp[:3], g - R @ skills.GRASP_OFFSET) and grasp[3:] == list(skills.GRASP_RPY)
assert np.allclose(np.array(grasp[:3]) + R @ skills.GRASP_OFFSET, g)       # the fingers' point is on the cup axis
assert np.allclose(np.subtract(above[:3], grasp[:3]), [0, 0, 100])
assert np.allclose(np.subtract(lift[:3], grasp[:3]), [0, 0, 30])

steps = dict(skills.plan_place(-200, 600, cup["top_mm"], start=lift))
assert np.isclose(steps["place"][2], grasp[2] + 3)                         # same table, 3 mm higher
assert np.isclose(steps["carry"][2], above[2]) and steps["carry"][:2] == lift[:2]
assert np.allclose(np.array(steps["place"][:3]) + R @ skills.GRASP_OFFSET, [-200, 600, g[2] + 3])

for yaw in (-30, 45):                                                      # a turned grasp: same point, cup upright
    t = skills.plan_pick(cup, yaw)[1][1]
    Rt = calib.rpy_matrix(*t[3:])
    assert np.allclose(np.array(t[:3]) + Rt @ skills.GRASP_OFFSET, g)
    assert np.allclose(Rt @ R.T @ [0, 0, 1], [0, 0, 1]) and np.isclose(skills.yaw_of(t), yaw)
    p = dict(skills.plan_place(-200, 600, cup["top_mm"], yaw=yaw))["place"]
    assert np.allclose(np.array(p[:3]) + calib.rpy_matrix(*p[3:]) @ skills.GRASP_OFFSET, [-200, 600, g[2] + 3])

for bad in (88, 30, 50):                      # seen widths: +SEEN_UNDER_MM over 92, under 61
    try:
        skills.plan_pick({**cup, "width_mm": bad})
        raise AssertionError(f"width {bad} accepted")
    except skills.SkillError:
        pass

# ---------- the object table: what the cup fingers take, and why not ----------
for name in ("cup", "apple", "orange", "sports ball"):
    assert skills.refusal(name) is None, name
for name, word in (("bottle", "narrow"), ("wine glass", "break"), ("banana", "thin"), ("cell phone", "thin"),
                   ("book", "flat"), ("bowl", "shallow"), ("sandwich", "soft"), ("laptop", "big")):
    en, ko = skills.refusal(name)
    assert word in en and name in en and ko, (name, en, ko)
assert skills.refusal("bottle")[1] == "병은 윗부분이 좁아서 제 손가락으로 잡을 수 없어요."           # 은 after a final consonant
assert skills.refusal("banana")[1].startswith("바나나는 ")
assert "giraffe" in skills.refusal("giraffe")[0]                                       # not in the table at all
assert all(n in skills.objects.COCO for n in skills.GRASPS), [n for n in skills.GRASPS if n not in skills.objects.COCO]
try:                                                                                   # refused before any geometry
    skills.plan_pick({**cup, "name": "bottle"})
    raise AssertionError("a bottle planned")
except skills.SkillError as e:
    assert e.args == skills.refusal("bottle")
# a cup: the proven grasp, 40 mm below its top, whatever its height
assert skills.grasp_height(cup) == cup["top_mm"] - skills.BELOW_RIM_MM
assert skills.grasp_height({**cup, "height_mm": 80.0}) == cup["top_mm"] - skills.BELOW_RIM_MM
# a round thing: at its equator when the tips clear the table there, else raised until they do
ball = {"name": "orange", "colour": "orange", "x": -126.5, "y": 613.0, "top_mm": -250.0, "width_mm": 150.0 - 8,
        "height_mm": 150.0}                                                 # (too wide for the hand, geometry only)
assert skills.grasp_height(ball) == -325.0                                 # equator 75 mm up, tips 65 mm up
apple = {**ball, "name": "apple", "width_mm": 76.0, "height_mm": 80.0}
z = skills.grasp_height(apple)
bottom = apple["top_mm"] - 80.0
assert z - skills.TIP_MM >= bottom + skills.TIP_CLEAR_MM - 1e-9 and z > bottom + 40.0, z     # raised over the equator
assert np.isclose(skills.grasp_height({**apple, "height_mm": None}), skills.grasp_height({**apple, "height_mm": 84.0}))
try:                                                                        # too low: the tips would hit the table
    skills.grasp_height({**apple, "height_mm": 60.0})
    raise AssertionError("a 60 mm high apple planned")
except skills.SkillError as e:
    assert "too low" in e.args[0]
(_, a_above), (_, a_grasp), _ = skills.plan_pick(apple)
assert np.allclose(np.array(a_grasp[:3]) + R @ skills.GRASP_OFFSET, [apple["x"], apple["y"], z])
# put down where it was held: the grasp point as far under its top as at the pick (below), not the cup's 40 mm
p = dict(skills.plan_place(-200, 600, apple["top_mm"], below=apple["top_mm"] - z))["place"]
assert np.allclose(np.array(p[:3]) + R @ skills.GRASP_OFFSET, [-200, 600, z + 3])
skills._held.update(below=apple["top_mm"] - z)
assert np.allclose(dict(skills.plan_place(-200, 600, apple["top_mm"]))["place"], p)
skills._held.clear()
assert np.allclose(dict(skills.plan_place(-200, 600, cup["top_mm"]))["place"][:3], np.array(grasp[:3]) + [-200 - cup["x"], 600 - cup["y"], 3])


free = skills.spots((cup["x"], cup["y"]), [])
assert free and all(np.hypot(x - cup["x"], y - cup["y"]) >= 60 for x, y in free)
near = {"x": free[0][0], "y": free[0][1]}                                  # something standing on the first spot
assert free[0] not in skills.spots((cup["x"], cup["y"]), [near])

moved = []                                                                 # after cancel() no move may start
skills.motion.stop = lambda: None
skills.motion.move_linear = lambda **kw: moved.append(kw)
skills.cancel()
try:
    skills._line("grasp", grasp)
    raise AssertionError("moved after cancel")
except skills.SkillError:
    assert not moved
try:
    skills.put_down()
    raise AssertionError("put down without holding anything")
except skills.SkillError:
    pass
sag = lambda name, **a: {"errorCode": "0",                                # z dips 250 mm in the middle of J1 0 -> 10
                         "cartPosition": [0, 0, -10 * a["jointPosition"][0] * (10 - a["jointPosition"][0])] + list(skills.GRASP_RPY)}
skills._ask = sag
assert not skills.joint_move_ok([0] * 6, [10, 0, 0, 0, 0, 0])
assert skills.joint_move_ok([5, 0, 0, 0, 0, 0], [10, 0, 0, 0, 0, 0])              # rising from the low point is fine
assert skills.joint_move_ok([0] * 6, [0] * 6)

# grasp options: only the flipped wrist reaches (seed J5 < 0), and only at turns of 45 deg or more; `accept` can refuse
READY = [-284.35, -75.43, -52.45, -136.99, 26.46, -278.46]
skills.motion.poses = lambda: {"ready": READY}
def ik(name, **a):
    if name == "kine_forward":
        return {"errorCode": "0", "cartPosition": [0, 0, 0] + list(skills.GRASP_RPY)}
    flipped, turn = a["jointPosition"][4] < 0, abs(skills.yaw_of(a["cartPosition"]))
    if flipped and turn >= 44:
        return {"errorCode": "0", "jointPosition": list(a["jointPosition"])}
    return {"errorCode": "1"}
skills._ask = ik
start = READY
plan = skills.reachable_pick(cup, start)
assert plan and plan[1][4] < 0 and abs(round(skills.yaw_of(plan[0][1][1]))) == 45, plan       # nearest turn first
plan = skills.reachable_pick(cup, start, accept=lambda wp, ja: abs(skills.yaw_of(wp[1][1])) > 100)
assert plan and abs(round(skills.yaw_of(plan[0][1][1]))) == 105, plan
assert skills.reachable_pick(cup, start, accept=lambda wp, ja: False) is None
# hand_sees: depth right at the cup's axis = object, far behind it = empty, nothing seen = unknown
skills.objects.base_from_camera = lambda: np.eye(4)                      # camera at the arm base origin
skills._ask = lambda name, **a: {"errorCode": "0", "cartPosition": [0.0, 500.0, 0.0] + list(skills.GRASP_RPY)}
skills._joints = lambda: [0.0] * 6
for depth_extra, want in ((0.0, "object"), (2000.0, "empty")):
    skills.surface_points = lambda pts, guess_z=-400.0, e=depth_extra: [tuple(np.array(p) * (1 + e / np.linalg.norm(p)))
                                                                        for p in pts]
    assert skills.hand_sees() == want, want
skills.surface_points = lambda pts, guess_z=-400.0: [None] * len(pts)
assert skills.hand_sees() == "unknown"
assert len(skills.GRASP_YAWS) == 24 and set(skills.GRASP_YAWS) == set(range(-165, 181, 15))
print("skills ok")

# ---------- the fingers point straight down in the grasp (the tips: TIP_MM along them, below the grasp point)
assert abs(np.linalg.norm(skills.FINGER_DIR) - 1.0) < 1e-9 and \
    (calib.rpy_matrix(*skills.GRASP_RPY) @ skills.FINGER_DIR)[2] < -0.99
# a cup thinner than the belly closes to is held between the tips: the arm stops TIPS_GRASP_MM higher
thin = {**cup, "width_mm": 58.0}                                            # 66 mm at the fingers
g_belly, g_tips = skills.plan_pick(cup)[1][1], skills.plan_pick(thin)[1][1]
assert abs(g_tips[2] - g_belly[2] - skills.TIPS_GRASP_MM) < 1.0 and np.allclose(g_tips[:2], g_belly[:2], atol=1.0)
skills._held.update(tips=True)
d = skills.plan_place(-200, 600, thin["top_mm"])[1][1]                         # put down held the same way
assert abs(d[2] - skills.plan_place(-200, 600, thin["top_mm"], tips=False)[1][1][2] - skills.TIPS_GRASP_MM) < 1.0
skills._held.clear()

# ---------- frames after a move: wait for one written after it ended, never longer than FRESH_WAIT_S ----------
import tempfile
import time
from pathlib import Path
f = Path(tempfile.mkdtemp()) / "lumi_depth_torso.npy"
f.write_bytes(b"x")
skills.moved_at.clear()
t0 = time.time()
assert skills.fresh(f, "torso") is not None and time.time() - t0 < 0.05        # no move since: at once
skills.FRESH_WAIT_S = 0.3
skills.moved("torso")
t0 = time.time()
skills.fresh(f, "torso")                                                         # older than the move: waits, gives up
assert 0.25 < time.time() - t0 < 0.5
import threading
threading.Timer(0.2, lambda: f.write_bytes(b"y")).start()                        # a new frame comes: taken at once
skills.moved("torso")
skills.FRESH_WAIT_S = 2.0
t0 = time.time()
skills.fresh(f, "torso")
assert 0.15 < time.time() - t0 < 0.6, time.time() - t0
skills.moved_at.clear()

# ---------- the table's height: the biggest group of level points, not the median of everything ----------
real_flat = skills.flat_points
table = [(x, 700.0, -400.0 + (x % 7)) for x in range(0, 300, 20)]              # 15 level points of a table
seat = [(x, 900.0, -600.0) for x in range(0, 200, 20)]                          # 10 of a chair seat
skills.flat_points = lambda pts, guess_z=-400.0, camera="torso", T=None: (table + seat + [None] * 30)[:len(pts)]
z, group = skills.flat_top([(0, 0)] * 55, (-700.0, 0.0))
assert abs(z + 397) < 4 and len(group) == 15, (z, len(group))
assert skills.flat_top([(0, 0)] * 55, (-700.0, -500.0))[0] == -600.0           # the band leaves only the seat
assert skills.flat_top([(0, 0)] * 3, (-700.0, 0.0)) is None                      # too few points
skills.flat_points = real_flat
print("skills fresh / flat ok")

# ---------- a pick stores what put down needs: the table under the object, also when its bottom was not in view ------
skills._prepare = lambda: None
skills._cancel.clear()                                                          # cancel() above
skills.motion.move_joints = lambda j, speed=None: None
skills.gripper.close = lambda: {"ai": [3500.0], "holding": True, "object_in_front": False}
skills.gripper.state = lambda: {"ai": [3500.0], "holding": True}
skills.table_near = lambda obj: -395.0                                          # the ring of table around it
skills._held.clear()
skills._do_pick(cup, skills.plan_pick(cup), READY)                              # no height_mm (live 2026-10-20 15:39)
assert skills._held["table"] == -395.0 and skills._held["top_mm"] == cup["top_mm"], skills._held
skills._do_pick({**cup, "height_mm": 120.0}, skills.plan_pick(cup), READY)      # its own bottom seen: that one
assert skills._held["table"] == cup["top_mm"] - 120.0 and skills._held["below"] == skills.BELOW_RIM_MM
skills._do_pick(apple, skills.plan_pick(apple), READY)                          # a round one: held higher up on it
assert np.isclose(skills._held["below"], apple["top_mm"] - skills.grasp_height(apple)) and skills._held["table"] == apple["top_mm"] - 80.0
# put down (voice "put it down"): the held turn reaches no spot -> up to carry height, then another turn and wrist
def ik_place(name, **a):
    if name == "kine_forward":
        return {"errorCode": "0", "cartPosition": [0.0, 0.0, 0.0] + list(skills.GRASP_RPY)}
    p = a["cartPosition"]
    if p[2] > -100.0 or a["jointPosition"][4] < 0 and abs(skills.yaw_of(p)) >= 44:   # up high, or turned and flipped
        return {"errorCode": "0", "jointPosition": list(a["jointPosition"])}
    return {"errorCode": "1"}


skills._ask, skills._joints = ik_place, lambda: list(READY)
skills.motion.tcp = lambda: skills.flange_for(cup["x"], cup["y"], cup["top_mm"] - 10.0)
lines_, turned = [], []
skills._line = lambda name, pose: lines_.append(name)
skills.place_turned = lambda way, ja: turned.append((way, ja))
assert skills.place(-200.0, 600.0) == (-200.0, 600.0)
assert lines_ == ["carry"] and turned[0][1][4] < 0 and abs(round(skills.yaw_of(turned[0][0][1][1]))) == 45, turned
skills._held.clear()
print("skills pick stores ok")
