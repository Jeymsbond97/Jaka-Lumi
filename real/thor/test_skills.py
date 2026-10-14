"""Self-check of the skills.py geometry, no robot: python test_skills.py"""
import numpy as np

import calib
import skills

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
print("skills ok")
