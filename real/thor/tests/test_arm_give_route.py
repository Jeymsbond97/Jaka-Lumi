"""Self-check of the routes to `give` (manipulation/arm_route.py) with the taught poses, the measured head centre and
the offline arm kinematics (robot/kinematics.py), no robot: python tests/test_arm_give_route.py"""
import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from manipulation import arm_route, skills
from robot import kinematics, motion
from vision import head_cam

POSES = {"ready": [-284.35, -75.43, -52.45, -136.99, 26.46, -278.46],      # data/arm_poses.json, 2026-10-27
         "carry": [-280.6, -86.13, -2.58, -173.3, 85.86, 119.9],
         "give": [-270.97, -86.67, -3.28, -168.9, 56.87, 128.14],
         "look": [-239.15, -88.4, -29.48, 199.97, 81.4, 158.35],
         "wave_out": [-239.15, -89.88, 0.5, -160.11, 77.47, -201.64],
         "wave_start": [-178.86, -77.26, -2.49, -175.06, 38.21, -219.73],
         "wave": [-178.86, -77.26, -17.24, -175.06, 38.37, -219.7]}
motion.poses = lambda: dict(POSES)
head_cam.head_centre = lambda: np.array([-93.0, -19.9, 356.1])      # the 2026-10-19 fit
skills._ask = kinematics.ask
arm_route.log = lambda *a: None


def names(target, now, holding=False):
    return [n for n, _ in arm_route.plan(target, holding, now=list(now))]


def moved(j, joint, deg):
    j = list(j)
    j[joint] += deg
    return j


# ---------- empty hand: the least joint travel, every move checked ----------
for s in ("wave_start", "wave"):                                    # after a wave: never in one move to give
    assert names("give", POSES[s])[-1] == "give" and len(names("give", POSES[s])) > 1
assert names("give", POSES["look"]) == ["give"]                     # 32 deg, not look -> carry -> give (71)
assert names("look", POSES["give"]) == ["look"]
assert names("look", POSES["wave_start"]) == ["wave_out", "look"]  # never look - wave_start in one move
assert names("wave_start", POSES["look"]) == ["wave_out", "wave_start"]
assert names("give", moved(POSES["carry"], 0, -8)) == ["carry", "give"]       # near carry: to carry, then on
assert names("give", moved(POSES["carry"], 0, -30)) == ["carry", "give"]      # far: the nearest pose first (join)
assert names("give", moved(POSES["look"], 1, 6)) == ["look", "give"]

# ---------- holding: only the EDGES, never a wave pose, the cup upright ----------
assert names("give", POSES["look"], holding=True) == ["carry", "give"]
assert names("look", POSES["give"], holding=True) == ["carry", "look"]
for start in (POSES["wave_start"], moved(POSES["wave_start"], 0, 5), moved(POSES["wave_out"], 2, 4)):
    try:
        route = names("give", start, holding=True)
    except arm_route.RouteError:
        continue                                                    # refused: nothing moves
    assert not set(route) & set(arm_route.WAVE_POSES), route
    prev = start
    for n in route:
        assert arm_route.move_problem(prev, motion.nearest(POSES[n], prev), head_cam.head_centre(), True) is None
        prev = POSES[n]
assert arm_route.hops(POSES["look"], "give", leaf=True, holding=True) == ["carry", "give"]   # fetch._line_holding
try:
    arm_route.plan("wave_start", holding=True, now=POSES["look"])
    raise AssertionError("went to a wave pose holding")
except arm_route.RouteError as e:
    assert e.args == arm_route.SPILL, e.args

# ---------- give_pre taught: an empty-hand way to give always ends give_pre -> give, the last move slow ----------
POSES["give_pre"] = moved(POSES["give"], 4, 20)                     # give with J5 20 deg further (a stand-in)
for start in ("look", "wave_start", "wave", "carry", "ready", "wave_out", "give_pre"):
    route = names("give", POSES[start])
    assert route[-2:] == ["give_pre", "give"] or start == "give_pre" and route == ["give"], (start, route)
    assert route.count("give") == 1, (start, route)                 # never through give on the way to give_pre
assert names("give", POSES["give"]) == []                           # there already: nothing moves
assert names("give", moved(POSES["give"], 4, 2)) == ["give"]        # at give within AT_POSE_DEG: as before
assert names("give", moved(POSES["carry"], 0, -30))[-2:] == ["give_pre", "give"]   # a join from far too
assert names("give", POSES["look"], holding=True) == ["carry", "give"]          # holding: give_pre not used
assert "give_pre" not in arm_route.graph(holding=True)
assert names("look", POSES["give"]) == ["look"]                     # other targets as before
sent = []
real_path, motion.move_path = motion.move_path, lambda moves, **k: sent.extend(moves)
arm_route.move(arm_route.plan("give", now=list(POSES["wave_start"])))
assert [s for _, s in sent][-1] == arm_route.GIVE_SPEED and \
    all(s == arm_route.SPEED for _, s in sent[:-1]), sent           # the last move, give_pre -> give, GIVE_SPEED
del POSES["give_pre"]                                                # not taught: the route and speed as before
sent.clear()
arm_route.move(arm_route.plan("give", now=list(POSES["wave_start"])))
assert all(s == arm_route.SPEED for _, s in sent), sent             # no give_pre: every move at route speed
motion.move_path = real_path
print("arm give route ok")
