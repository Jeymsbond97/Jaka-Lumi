"""Hold-to-move ("jog") control for the dashboard: base, head, waist, lift and arm joints.

The page sends POST /jog about every 150 ms while a button is held; each call keeps that axis moving
for HOLD_S more. When the calls stop (button released, page closed, network gone) the axis stops by
itself within one small step. Nothing here runs a long motion that has to be cancelled:
- base: /api/joy_control, each command lasts 0.5 s on the AGV anyway
- head / waist / lift: short moveto steps (the body /stop call does not stop a moveto)
- arm: short relative joint_move steps over TCP 10001
"""
import threading
import time

from robot import agv
from robot import arm
from robot import head

HOLD_S = 0.35                # s an axis keeps moving after the last /jog call

# axis: (index in the body status, step per move, low limit, high limit)
BODY_AXES = {"lift": (0, 10.0, 0.0, head.LIFT_MAX_MM), "waist": (1, 3.0, -90.0, 90.0),
             "head_yaw": (2, 3.0, -180.0, 180.0), "head_pitch": (3, 2.0, -5.0, 35.0)}
ARM_AXES = {f"j{i}": i - 1 for i in range(1, 7)}
ARM_STEP = 2.0               # deg per step
ARM_SPEED = 20.0             # deg/s at speed 100 %
BASE_V = 0.3                 # m/s at speed 100 %
BASE_W = 0.6                 # rad/s at speed 100 %


class Jogger:
    def __init__(self):
        self.lock = threading.Lock()
        self.cmd = {}                         # axis -> (direction, speed 0..1, deadline)
        self.threads = {}
        self.last_error = None

    def hold(self, axis, direction, speed=0.5):
        if axis not in BODY_AXES and axis not in ARM_AXES and axis not in ("base_drive", "base_turn"):
            raise ValueError(f"unknown axis {axis}")
        group = "base" if axis.startswith("base") else "arm" if axis in ARM_AXES else "body"
        with self.lock:
            if group == "base":               # drive and turn may be held together
                self.cmd = {a: c for a, c in self.cmd.items() if a.startswith("base")}
            else:                             # one body / arm axis at a time
                self.cmd = {a: c for a, c in self.cmd.items() if not (a in BODY_AXES or a in ARM_AXES)}
            self.cmd[axis] = (1 if direction > 0 else -1, max(0.05, min(1.0, speed)), time.time() + HOLD_S)
            t = self.threads.get(group)
            if t is None or not t.is_alive():
                t = threading.Thread(target=getattr(self, f"_run_{group}"), daemon=True)
                self.threads[group] = t
                t.start()

    def stop(self):
        with self.lock:
            self.cmd = {}
        try:
            agv.request("/api/joy_control?linear_velocity=0&angular_velocity=0")
        except Exception:
            pass

    def _active(self, axes):
        now = time.time()
        with self.lock:
            return {a: c for a, c in self.cmd.items() if a in axes and c[2] > now}

    def _run_base(self):
        while True:
            active = self._active(("base_drive", "base_turn"))
            if not active:
                return
            v = active.get("base_drive", (0, 0, 0))
            w = active.get("base_turn", (0, 0, 0))
            try:
                agv.request(f"/api/joy_control?linear_velocity={v[0] * v[1] * BASE_V:.3f}"
                            f"&angular_velocity={w[0] * w[1] * BASE_W:.3f}", timeout=1.0)
            except Exception as e:
                self.last_error = f"base: {e}"
            time.sleep(0.1)

    def _run_body(self):
        while True:
            active = self._active(BODY_AXES)
            if not active:
                return
            axis, (direction, speed, _) = next(iter(active.items()))
            index, step, low, high = BODY_AXES[axis]
            try:
                pos = head.status()
                target = max(low, min(high, pos[index] + direction * step))
                if abs(target - pos[index]) < 0.05:          # at the limit
                    time.sleep(0.1)
                    continue
                pos[index] = target
                head.moveto(pos, 20 + 60 * speed, 60, timeout=10)
            except Exception as e:
                self.last_error = f"{axis}: {e}"
                time.sleep(0.3)

    def _run_arm(self):
        while True:
            active = self._active(ARM_AXES)
            if not active:
                return
            axis, (direction, speed, _) = next(iter(active.items()))
            delta = [0.0] * 6
            delta[ARM_AXES[axis]] = direction * ARM_STEP
            deg_s = ARM_SPEED * speed
            try:
                r = arm.cmd("joint_move", relFlag=1, jointPosition=delta, speed=deg_s, accel=deg_s * 3)
                if r.get("errorCode") != "0":
                    self.last_error = f"{axis}: {r.get('errorMsg') or r}"
                    time.sleep(0.3)
                    continue
            except Exception as e:
                self.last_error = f"{axis}: {e}"
                time.sleep(0.3)
                continue
            time.sleep(ARM_STEP / deg_s + 0.05)                 # let this step finish before the next


jogger = Jogger()
