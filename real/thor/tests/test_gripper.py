"""Self-check of robot/gripper.py's finger gap from AI_1 (no robot): python tests/test_gripper.py"""
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from robot import gripper as g

assert g.gap_mm(g.AI_OPEN) == 102.0 and g.gap_mm(g.AI_SHUT) == 77.0        # belly, open / closed (owner)
assert g.gap_mm(50) == 102.0 and g.gap_mm(5000) == 77.0                     # readings past the ends are clamped
assert abs(g.gap_mm((g.AI_OPEN + g.AI_SHUT) / 2) - 89.5) < 0.01   # linear between
assert g.gap_mm(g.AI_SHUT, "tips") == 73.0 and g.gap_mm(g.AI_OPEN, "shank") == 66.0
assert all(hasattr(g, n) for n in ("MOVE_S", "SENSOR_DI", "READ_TRIES", "READ_GAP_S", "CLOSED_AI", "EMPTY_AI"))
print("gripper ok")
