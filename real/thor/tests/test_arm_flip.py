"""Self-check of an arm with its wrist turned over (J4 / J6 half a turn off and J5's sign flipped against the taught
poses) while holding a cup, with the taught poses, the measured head centre and the offline arm kinematics
(tests/pick_sweep.py simulator), no robot: python tests/test_arm_flip.py

Live 2026-10-30 15:01: a voice pick ended at its lift pose with the wrist turned over; the straight move to give
ended on the same wrist branch and from there every way back was refused (arm_route UNKNOWN)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from tests import pick_sweep as ps

ps.install()
fetch, skills, motion, kin = ps.fetch, ps.skills, ps.motion, ps.kin
from manipulation import arm_route                  # noqa: E402

STUCK = [-270.5, -88.9, -12.1, -348.9, -27.3, -51.9]               # live: give's flange pose, the wrist turned over
LIFT = [-282.3, -84.7, -44.5, 114.9, -16.3, -169.2]                 # the live pick's lift pose (-10, 499, -73), turned
CENTRE = ps.HEAD_CENTRE


def lowest(j):
    return arm_route.profile(j, j, CENTRE)[1]


def check_way(start, seq):
    """Every move of a plan: no wave pose, the cup upright, clear of the head, no dip; the wrist turning back never
    takes the gripper below where it started (PATH_SAG_MM)."""
    prev, floor = list(start), lowest(start)
    for n, j in seq:
        assert n not in arm_route.WAVE_POSES, seq
        clear, ends, low, tilt = arm_route.profile(prev, j, CENTRE)
        assert tilt <= skills.MAX_TILT_DEG and clear >= arm_route.HEAD_CLEAR_MM, (n, clear, tilt)
        assert low >= (floor if n == "wrist" else ends) - skills.PATH_SAG_MM, (n, low, floor, ends)
        prev = j


assert np.allclose(kin.pose(STUCK)[:3], kin.pose(motion.poses()["give"])[:3], atol=2.0)   # the same hand, turned over

# ---------- the planner: from the live stuck pose, holding, a checked way to each pose ----------
for target in ("look", "carry", "give"):
    seq = arm_route.plan(target, holding=True, now=list(STUCK))
    assert seq and seq[0][0] == "wrist", seq                        # the wrist turns back first, where it is
    assert max(abs(a - b) for a, b in zip(seq[-1][1], motion.nearest(motion.poses()[target], seq[-1][1]))) < 0.01
    check_way(STUCK, seq)
    print(target, "from the stuck pose:", " -> ".join(n for n, _ in seq))
try:
    arm_route.plan("wave_start", holding=True, now=list(STUCK))
    raise AssertionError("a wave pose with a cup")
except arm_route.RouteError as e:
    assert e.args == arm_route.SPILL, e.args
assert arm_route.plan("look", now=list(STUCK))[-1][0] == "look"     # empty hand: a way too

# ---------- fetch's moves with the cup from the turned-over lift pose: never left turned over at a pose ----------
for target in ("give", "carry", fetch.LOOK_POSE):
    ps.setup(ps.pick_at(-104, 656, -182, height=142), 0.0)
    ps.W["hand"].update(holding=True, closed=True)
    fetch._state.update(holding=True)
    ps.W["J"] = list(LIFT)
    fetch._line_holding(target)
    assert fetch._at_pose(target), (target, [round(v, 1) for v in ps.W["J"]])
    print(target, "from the lift pose: at", target)

# ---------- the voice pick of the live scene: the turned-over grasp, then carried to look (not left at the lift) ----
ps.setup(ps.pick_at(-104, 656, -182, height=142), 0.0)
fetch.pick_here("cup")
assert any("wrist J5 -13" in l for l in ps.W["lines"]), ps.W["lines"]  # the live grasp: J4 of the other wrist near
assert ps.W["hand"]["holding"] and fetch._state["holding"]           # its limit (from look's +200) on the way up
assert fetch._at_pose(fetch.LOOK_POSE), [round(v, 1) for v in ps.W["J"]]
print("voice pick: held at look")

print("arm flip ok")
