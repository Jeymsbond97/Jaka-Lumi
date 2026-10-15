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

for bad in (90, 30):
    try:
        skills.plan_pick({**cup, "width_mm": bad})
        raise AssertionError(f"width {bad} accepted")
    except skills.SkillError:
        pass

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
print("skills ok")
