"""Self-check of robot/gripper.py's finger gap from AI_1 (no robot): python tests/test_gripper.py"""
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from robot import gripper as g

assert g.gap_mm(g.AI_OPEN) == 96.0 and g.gap_mm(g.AI_SHUT) == 70.0          # belly, open / closed (tape)
assert g.gap_mm(50) == 96.0 and g.gap_mm(5000) == 70.0                      # readings past the ends are clamped
assert abs(g.gap_mm(2250) - 82.0) < 1.5                                     # the 82 mm metal cup, 2026-10-13
assert g.gap_mm(g.AI_SHUT, "tips") == 59.0 and g.gap_mm(g.AI_OPEN, "shank") == 66.0
assert all(hasattr(g, n) for n in ("MOVE_S", "SENSOR_DI", "READ_TRIES", "READ_GAP_S", "CLOSED_AI", "EMPTY_AI"))
print("gripper ok")
