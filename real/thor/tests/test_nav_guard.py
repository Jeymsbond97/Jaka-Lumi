"""Self-check of the arm guard on navigation drives (robot/nav_guard.py, agv.go_point / status / cancel) with a fake
base that drives its planned path and fake distance probes, no robot, no network: python tests/test_nav_guard.py"""
import math
import re
import threading
import time

from robot import agv, nav_guard
from tasks import fetch

nav_guard.POLL_S = 0.01
nav_guard.CLEAR_S = 0.1
nav_guard.START_S = 0.3
nav_guard.PATH_EVERY_S = 0.05
nav_guard.BLOCK_S = 1.0
nav_guard.log = lambda msg: logs.append(msg)
ARM = [(0.30, 0.40), (0.36, 0.40), (0.42, 0.40)]   # m, base frame: flange, grasp point, tips out to the left
fetch.arm_yaw = lambda: -86.0
fetch.arm_points = lambda: ARM
fetch.skills._ask = lambda *a, **k: (_ for _ in ()).throw(AssertionError("a test reached the arm"))
logs = []


class Base:
    """Drives straight along +x at SPEED from (0, 0) to the goal while "running"; obstacles are points; a cancel
    stops it on the spot."""
    SPEED = 0.6

    def __init__(self, obstacles):
        self.obstacles = list(obstacles)
        self.x, self.status, self.t, self.goal = 0.0, "idle", time.time(), 0.0
        self.sent, self.closest = [], float("inf")
        self.lock = threading.Lock()
        agv.request = self.request

    def _drive(self):
        now = time.time()
        if self.status == "running":
            self.x = min(self.goal, self.x + self.SPEED * (now - self.t))
            if self.x >= self.goal:
                self.status = "succeeded"
        self.t = now
        for p in ARM:                                  # the arm's real distance to the obstacles
            self.closest = min([self.closest] + [math.hypot(self.x + p[0] - ox, p[1] - oy) for ox, oy in self.obstacles])

    def request(self, cmd, timeout=3.0):
        with self.lock:
            self._drive()
            if cmd == "/api/robot_status":
                return {"results": {"move_status": self.status, "current_pose": {"x": self.x, "y": 0.0, "theta": 0.0}}}
            m = re.match(r"/api/move\?location=([-\d.]+),", cmd)
            if m:
                self.sent.append(cmd)
                self.status, self.goal = "running", float(m.group(1))
                return {"status": "OK"}
            if cmd == "/api/move/cancel":
                self.status = "canceled" if self.status == "running" else self.status
                return {"status": "OK"}
            if cmd == "/api/get_planned_path":
                return {"results": {"path": [[self.x + k * 0.05, 0.0] for k in range(int((self.goal - self.x) / 0.05) + 1)]
                                    if self.status == "running" else []}}
            m = re.match(r"/api/map/distance_probe\?x=([-\d.]+)&y=([-\d.]+)$", cmd)
            if m:
                x, y = float(m.group(1)), float(m.group(2))
                d = min([math.hypot(x - ox, y - oy) for ox, oy in self.obstacles] or [-1])
                return {"results": {"env_dist": {"obstacle": d, "static": -1}}}
            raise AssertionError(f"unexpected command {cmd}")


def wait_end(limit=5.0):
    t0 = time.time()
    while time.time() - t0 < limit:
        st = agv.status()
        if st["move_status"] != "running":
            return st
        time.sleep(0.02)
    raise AssertionError("the move never ended")


# 1. A table edge 0.45 m left of the path, where the arm passes 0.05 m from it: stopped before, the table taken
#    away (a person walks off): the same goal again, arrived.
base = Base([(1.5, 0.45)])
assert agv.go_point(3.0, 0.0, 0.0) == (True, "OK")
t0 = time.time()
while not any("stopped" in m for m in logs) and time.time() - t0 < 3:
    time.sleep(0.01)
assert any("stopped" in m for m in logs), logs
time.sleep(0.2)
st = agv.status()
assert st["move_status"] == "running" and st["guard"] == "held", st          # waiters wait on
assert base.status == "canceled" and base.x < 1.5 - ARM[-1][0], base.x        # stopped before the edge
assert base.closest > nav_guard.MARGIN_M / 2, base.closest
base.obstacles.clear()
st = wait_end()
assert st["move_status"] == "succeeded" and len(base.sent) == 2 and base.x == 3.0, (st, base.sent)
assert any("going on" in m for m in logs), logs

# 2. The table stays: stopped, then after BLOCK_S the move ends "failed" with the reason (EN + KO); no new goal.
logs.clear()
base = Base([(1.5, 0.45)])
agv.go_point(3.0, 0.0, 0.0)
st = wait_end()
assert st["move_status"] == "failed" and st["guard"] == nav_guard.REASON, st
assert len(base.sent) == 1 and base.x < 1.5 - ARM[-1][0] and base.closest > nav_guard.MARGIN_M / 2, (base.sent, base.x)
assert any("blocked" in m for m in logs), logs
agv.go_point(0.0, 0.0, 0.0)                                                    # a new goal forgets the reason
assert agv.status().get("guard") is None

# 3. Starting next to a table (the arm over its edge) and driving away from it: never stopped.
logs.clear()
base = Base([(0.36, 0.45)])
base.x = 0.0
agv.go_point(1.0, 0.0, 0.0)
st = wait_end()
assert st["move_status"] == "succeeded" and not any("stopped" in m for m in logs), (st, logs)

# 4. STOP (agv.cancel) while held: the goal is never sent again.
logs.clear()
base = Base([(1.5, 0.45)])
agv.go_point(3.0, 0.0, 0.0)
t0 = time.time()
while not any("stopped" in m for m in logs) and time.time() - t0 < 3:
    time.sleep(0.01)
agv.cancel()
base.obstacles.clear()
time.sleep(0.5)
assert len(base.sent) == 1 and agv.status()["move_status"] == "canceled", base.sent

# 5. Lookahead along a bent path, and the turn rate: poses checked.
p = nav_guard.ahead((0.0, 0.0, 0.0), [[0, 0], [0.1, 0], [0.1, 0.5]], 1.0)
assert len(p) == 3 and abs(p[0][2] - nav_guard.TURN_AHEAD_S) < 1e-9, p              # turned on, then 0.15, 0.30
assert abs(p[1][0] - 0.1) < 1e-9 and abs(p[1][1] - 0.05) < 1e-9 and abs(p[2][1] - 0.2) < 1e-9, p
assert abs(p[2][2] - math.pi / 2) < 1e-9, p
print("nav guard ok")
