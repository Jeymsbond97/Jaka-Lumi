"""Hold-to-move ("jog") control for the app and the dashboard: base, head, waist, lift, arm joints and the hand.

The page sends POST /jog about every 150 ms while a button is held; each call keeps that axis moving
for HOLD_S more. When the calls stop (button released, page closed, network gone) the axis stops by
itself:
- base: /api/joy_control, each command lasts 0.5 s on the AGV anyway
- arm joints and the hand (tcp_x / tcp_y / tcp_z): one long move per hold (no step pauses), stopped with
  stop_program the moment the hold ends. A move covers at most ARM_SEG_S / ARM_SEG_DEG (TCP_SEG_MM): if the
  controller drops the stop for a moment the arm still ends there; a longer hold starts the next one right away.
- head / waist / lift: the body controller cannot stop a moveto (docs/08), so these stay steps, sized to
  about BODY_SEG_S each from the speed measured on the last steps and sent back to back (no settle wait between
  two of our own steps). A release ends at most one step later.
The arm's speeds follow the owner's arm speed % (motion.speed_percent, the app's slider), as every arm move does.
"""
import threading
import time


def log(*a):
    print(time.strftime("%H:%M:%S"), "jog:", *a, flush=True)

from robot import agv
from robot import arm
from robot import head
from robot import motion

HOLD_S = 0.35                # s an axis keeps moving after the last /jog call

# axis: (index in the body status, first step, low limit, high limit)
BODY_AXES = {"lift": (0, 10.0, 0.0, head.LIFT_MAX_MM), "waist": (1, 3.0, -90.0, 90.0),
             "head_yaw": (2, 3.0, -180.0, 180.0), "head_pitch": (3, 2.0, -5.0, 35.0)}
BODY_SEG_S = 0.4             # s one body step should take (sized from the measured speed)
BODY_STEP_RANGE = (0.5, 8.0)  # x the first step: the smallest and largest step
BODY_ACC = 80                # acceleration ratio % of a body step (was 60: shorter ramps, smaller dips between steps)
ARM_AXES = {f"j{i}": i - 1 for i in range(1, 7)}
TCP_AXES = {"tcp_x": 0, "tcp_y": 1, "tcp_z": 2}
ARM_SPEED = 20.0             # deg/s at speed 1 and arm speed 100 %
ARM_SEG_S, ARM_SEG_DEG = 2.0, 30.0   # one arm-joint move: at most this long and this far
TCP_SPEED = 40.0             # mm/s at speed 1 and arm speed 100 %
TCP_SEG_S, TCP_SEG_MM = 2.0, 60.0    # one hand move: at most this long and this far
TCP_TRY_MM = (1.0, 0.5, 0.25, 0.1)   # x the planned length, tried in turn when IK refuses the longer one
ARM_RETRY_S = 1.0            # s a hold keeps trying while the controller has closed its connection (~0.5 s drops)
NEXT_EARLY_S = 0.1           # s before a move should end that the next one of a long hold is sent
BASE_V = 0.3                 # m/s at speed 100 %
BASE_W = 0.6                 # rad/s at speed 100 %

HAND_AXES = {**{a: ("joint", i) for a, i in ARM_AXES.items()}, **{a: ("tcp", i) for a, i in TCP_AXES.items()}}


def arm_deg_s(speed):
    return min(motion.JOINT_MAX_DEG_S, ARM_SPEED * speed * motion.speed_percent() / 100)


def tcp_mm_s(speed):
    return min(motion.LINEAR_MAX_MM_S, TCP_SPEED * speed * motion.speed_percent() / 100)


def joint_target(now, index, direction, deg_s):
    """Where one joint move of a hold goes: ARM_SEG_S / ARM_SEG_DEG on, kept inside the joint's limit.
    None at the limit."""
    lim = motion.LIMITS[index] - motion.LIMIT_MARGIN
    t = list(now)
    t[index] = max(-lim, min(lim, now[index] + direction * min(ARM_SEG_DEG, deg_s * ARM_SEG_S)))
    return t if abs(t[index] - now[index]) > 0.2 else None


def body_step(first, rate):
    """One body step for `rate` units/s measured (None: not yet), BODY_SEG_S long, within BODY_STEP_RANGE."""
    lo, hi = (first * k for k in BODY_STEP_RANGE)
    return first if not rate else max(lo, min(hi, rate * BODY_SEG_S))


class Jogger:
    def __init__(self):
        self.lock = threading.Lock()
        self.cmd = {}                         # axis -> (direction, speed 0..1, deadline)
        self.threads = {}
        self.last_error = None
        self.body_rate = {}                   # (axis, vel) -> units/s measured on the last steps

    def hold(self, axis, direction, speed=0.5):
        if axis not in BODY_AXES and axis not in HAND_AXES and axis not in ("base_drive", "base_turn"):
            raise ValueError(f"unknown axis {axis}")
        group = "base" if axis.startswith("base") else "arm" if axis in HAND_AXES else "body"
        with self.lock:
            if group == "base":               # drive and turn may be held together
                self.cmd = {a: c for a, c in self.cmd.items() if a.startswith("base")}
            else:                             # one body / arm axis at a time
                self.cmd = {a: c for a, c in self.cmd.items() if not (a in BODY_AXES or a in HAND_AXES)}
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
        last = None                           # (axis, target) of the step just ended: the next starts there
        while True:
            active = self._active(BODY_AXES)
            if not active:
                return
            axis, (direction, speed, _) = next(iter(active.items()))
            index, first, low, high = BODY_AXES[axis]
            vel = 20 + 60 * speed
            try:
                pos = head.status()
                if last and last[0] == axis and abs(pos[index] - last[1]) < 1.0:
                    pos[index] = last[1]      # read a hair short of the step's end: go on from where it was sent
                step = body_step(first, self.body_rate.get((axis, vel)))
                target = max(low, min(high, pos[index] + direction * step))
                if abs(target - pos[index]) < 0.05:          # at the limit
                    last = None
                    time.sleep(0.1)
                    continue
                start, pos[index] = pos[index], target
                t0 = time.time()
                head.moveto(pos, vel, BODY_ACC, timeout=10, settle=not (last and last[0] == axis))
                dt = time.time() - t0
                if dt > 0.05:
                    rate = abs(target - start) / dt
                    old = self.body_rate.get((axis, vel))
                    self.body_rate[(axis, vel)] = rate if old is None else (old + rate) / 2
                last = (axis, target)
            except Exception as e:
                self.last_error = f"{axis}: {e}"
                last = None
                time.sleep(0.3)

    def _halt_arm(self):
        log("arm hold ended: stop")
        try:
            arm.cmd("stop_program")
        except Exception as e:
            self.last_error = f"arm stop: {e}"
            log(f"arm stop failed: {e!r}")

    def _start_arm(self, axis, direction, speed):
        """Send one move of a hold; returns when it should end (time), None when it cannot go on (a limit)."""
        kind, index = HAND_AXES[axis]
        motion._ready()
        if kind == "joint":
            deg_s = arm_deg_s(speed)
            now = motion.joints()
            target = joint_target(now, index, direction, deg_s)
            if target is None:
                return None
            moved = max(abs(a - b) for a, b in zip(target, now))
            r = arm.cmd("joint_move", relFlag=0, jointPosition=target, speed=deg_s, accel=deg_s * 3)
            if r.get("errorCode") != "0":
                raise motion.MotionError(r.get("errorMsg") or str(r))
            return time.time() + moved / deg_s + 1 / 3
        mm_s = tcp_mm_s(speed)
        length = min(TCP_SEG_MM, mm_s * TCP_SEG_S)
        err = None
        for k in TCP_TRY_MM:
            delta = [0.0, 0.0, 0.0]
            delta[index] = direction * length * k
            try:
                motion.move_linear(delta=delta, wait=False, mm_s=mm_s)
                return time.time() + length * k / mm_s + 1 / 3
            except motion.MotionError as e:
                err = e
        raise err

    def _start_arm_retry(self, *want):
        """_start_arm, tried again while the controller has its connection closed (ARM_RETRY_S at most): usually the drop
        came before a move went out, or (rarely) one went out without a reply: then a second one is queued behind
        it, at most one more segment, and the release's stop_program empties the queue either way."""
        end = time.time() + ARM_RETRY_S
        while True:
            try:
                return self._start_arm(*want)
            except (ConnectionError, OSError):
                if time.time() > end or not self._active(HAND_AXES):
                    raise
                time.sleep(0.15)

    def _run_arm(self):
        moving, ends = None, 0.0              # (axis, direction, speed) of the move running now
        try:
            while True:
                active = self._active(HAND_AXES)
                if active:
                    axis, (direction, speed, _) = next(iter(active.items()))
                    want = (axis, direction, speed)
                else:
                    want = None
                if moving and want != moving:
                    self._halt_arm()          # released, or another axis / direction / speed
                    moving = None
                if want is None:
                    return
                if moving is None or time.time() >= ends - NEXT_EARLY_S:
                    try:
                        end = self._start_arm_retry(*want)
                    except Exception as e:
                        self.last_error = f"{want[0]}: {e}"
                        log(f"{want[0]} {want[1]:+d} refused: {e!r}")
                        moving = None
                        time.sleep(0.3)
                        continue
                    if end is None:           # at the joint's limit: nothing sent
                        log(f"{want[0]} {want[1]:+d}: at its limit")
                        moving = None
                        time.sleep(0.1)
                        continue
                    log(f"{want[0]} {want[1]:+d} speed {want[2]:.2f}: move sent, {end - time.time():.1f} s")
                    moving, ends = want, end
                time.sleep(0.03)
        finally:
            if moving:
                self._halt_arm()


jogger = Jogger()
