"""Checked arm motion over the controller's TCP command port (10001, JSON, no SDK): named poses, joint moves,
straight-line TCP moves, stop.

Every move is checked before it is sent: joint limits with a margin, and for linear moves an IK solution
(the controller's kine_inverse) that does not swing J1 / J4 / J6 around. Moves wait until the arm is there,
and return early with an error when STOP was pressed or the controller stopped the arm.

    python motion.py                     # joints, TCP, named poses
    python motion.py go tuck [normal]    # move to a named pose (slow by default)
    python motion.py teach ready         # save the arm's current joints as a named pose (move it in Cobo π first)
    python motion.py line 0 0 30         # straight TCP move by dx dy dz mm (base frame), slow
    python motion.py stop

Poses taught with `teach` are kept in arm_poses.json next to this file.
"""
import json
import sys
import threading
import time
from pathlib import Path

import arm

HERE = Path(__file__).resolve().parent
POSES_FILE = HERE / "arm_poses.json"
TUCK = [179.3, -88.6, -13.9, -15.8, -14.5, -121.3]   # deg, arm folded beside the column (fits doorways)
LIMITS = [360, 125, 130, 360, 120, 360]              # deg, ± factory range per joint (docs/01_HARDWARE.md)
LIMIT_MARGIN = 5.0                                   # deg kept away from every limit
JOINT_SPEED = {"slow": 10.0, "normal": 25.0}         # deg/s
LINEAR_SPEED = {"slow": 20.0, "normal": 50.0}        # mm/s
ACCEL_FACTOR = 3.0                                   # accel = speed x this (per s)
MAX_FLIP = 90.0                                      # deg; an IK answer turning J1 / J4 / J6 more than this is refused
MAX_TRAVEL = 200.0                                   # deg; a joint move turning any joint further is refused
FULL_TURN = (0, 3, 5)                                # J1, J4, J6: ±360 joints; a target and target ± 360 are the same pose
AT_JOINT_DEG = 0.3                                   # arrived when every joint is this close ...
AT_TCP_MM = 1.0                                      # ... or the TCP this close (linear moves)
POLL_S = 0.1
EXTRA_S = 10.0                                       # s allowed on top of 3x the planned move time
STILL_S = 2.0                                        # s without joint motion (and not there) -> the move ended short
STILL_DEG = 0.05                                     # joint change that counts as motion
BLIND_S = 1.0                                        # s without a valid state reply while moving -> stop the arm

_stopped = threading.Event()                         # set by stop(): a waiting move gives up


class MotionError(RuntimeError):
    pass


def _read(name, key):
    r = arm.cmd(name)
    if key not in r:
        raise MotionError(f"{name} failed: {r.get('errorMsg') or r}")
    return r[key]


def joints():
    return _read("get_joint_pos", "joint_pos")


def tcp():
    return _read("get_tcp_pos", "tcp_pos")


def poses():
    """Named poses: tuck plus everything taught."""
    try:
        taught = json.loads(POSES_FILE.read_text())
    except FileNotFoundError:
        taught = {}
    return {"tuck": TUCK, **taught}


def teach(name):
    """Save the current joints as pose `name`."""
    if name == "tuck":
        raise MotionError("tuck is fixed in motion.py")
    check(j := [round(v, 2) for v in joints()])
    taught = {k: v for k, v in poses().items() if k != "tuck"}
    taught[name] = j
    POSES_FILE.write_text(json.dumps(taught, indent=1))
    return j


def check(target):
    """Raise MotionError if a joint target is out of range (with LIMIT_MARGIN)."""
    if len(target) != 6:
        raise MotionError(f"need 6 joints, got {len(target)}")
    for i, (v, lim) in enumerate(zip(target, LIMITS)):
        if abs(v) > lim - LIMIT_MARGIN:
            raise MotionError(f"J{i + 1} {v:.1f} deg is beyond ±{lim - LIMIT_MARGIN:.0f}")


def _ready():
    st = arm.cmd("get_robot_state")
    if not (st.get("power") and st.get("enable")):
        raise MotionError("arm is not powered / enabled")
    if arm.program_state() != "idle":
        raise MotionError("a Cobo π program is running")


def _wait(arrived, planned_s):
    """Wait while the arm moves. Big joint moves run slower than speed / travel suggests (measured: 157 deg
    of J6 at 10 deg/s took well over 21 s), so the limit is generous; a move that stops short is caught by
    STILL_S instead."""
    t0 = last_move = last_seen = time.time()
    last = None
    while time.time() - t0 < 3 * planned_s + EXTRA_S:
        if _stopped.is_set():
            raise MotionError("stopped")
        try:
            d = arm.cmd("get_data")
        except (ConnectionError, OSError):
            d = {}
        if "joint_actual_position" not in d:     # the controller now and then answers a poll with nothing
            if time.time() - last_seen > BLIND_S:
                stop()
                raise MotionError("lost the arm state while moving - stopped")
            time.sleep(POLL_S)
            continue
        last_seen = time.time()
        if d.get("protective_stop") or d.get("emergency_stop"):
            raise MotionError("the controller stopped the arm (protective / emergency stop)")
        if d.get("inpos") and arrived(d):
            return d
        j = d["joint_actual_position"]
        if last is None or max(abs(a - b) for a, b in zip(j, last)) > STILL_DEG:
            last, last_move = j, time.time()
        elif time.time() - last_move > STILL_S and time.time() - t0 > STILL_S + 1:
            raise MotionError("the arm stopped before the target")
        time.sleep(POLL_S)
    stop()
    raise MotionError(f"not there after {time.time() - t0:.0f} s - stopped")


def nearest(target, start):
    """For the ±360 joints use target or target ± 360, whichever is closest to where the joint is now:
    the same pose, without spinning the arm a full turn around the column."""
    out = list(target)
    for i in FULL_TURN:
        lim = LIMITS[i] - LIMIT_MARGIN
        options = [v for v in (target[i] - 360, target[i], target[i] + 360) if abs(v) <= lim]
        out[i] = min(options, key=lambda v: abs(v - start[i]))
    return out


def move_joints(target, speed="slow", wait=True):
    """Joint move to absolute angles (deg). Returns the joints reached (or the target if wait=False)."""
    check(target)
    _ready()
    deg_s = JOINT_SPEED[speed]
    start = joints()
    target = nearest(target, start)
    for i, (a, b) in enumerate(zip(target, start)):
        if abs(a - b) > MAX_TRAVEL:
            raise MotionError(f"J{i + 1} would turn {a - b:+.0f} deg - refused")
    travel = max(abs(a - b) for a, b in zip(target, start))
    _stopped.clear()
    r = arm.cmd("joint_move", relFlag=0, jointPosition=list(target), speed=deg_s, accel=deg_s * ACCEL_FACTOR)
    if r.get("errorCode") != "0":
        raise MotionError(f"joint_move refused: {r.get('errorMsg') or r}")
    if not wait:
        return list(target)
    d = _wait(lambda d: max(abs(a - b) for a, b in zip(d["joint_actual_position"], target)) < AT_JOINT_DEG,
              travel / deg_s)
    return d["joint_actual_position"]


def go(name, speed="slow", wait=True):
    p = poses()
    if name not in p:
        raise MotionError(f"no pose {name!r} (known: {', '.join(p)})")
    return move_joints(p[name], speed, wait)


def move_linear(target=None, delta=None, speed="slow", wait=True):
    """Straight TCP move to `target` [x, y, z mm, rx, ry, rz deg] or by `delta` (dx, dy, dz mm), base frame.
    The end pose is checked with the controller's IK first."""
    now_j, now_p = joints(), tcp()
    if target is None:
        target = [now_p[i] + (delta[i] if i < len(delta) else 0.0) for i in range(3)] + list(now_p[3:])
    for _ in range(3):          # the controller now and then answers "0" without the joints: ask again
        ik = arm.cmd("kine_inverse", jointPosition=now_j, cartPosition=list(target))
        if "jointPosition" in ik or ik.get("errorCode") not in ("0", None):
            break
        time.sleep(0.2)
    if "jointPosition" not in ik:
        raise MotionError(f"no IK solution for {[round(v, 1) for v in target]}: {ik.get('errorMsg') or ik}")
    end_j = ik["jointPosition"]
    check(end_j)
    for i in (0, 3, 5):
        if abs(end_j[i] - now_j[i]) > MAX_FLIP:
            raise MotionError(f"J{i + 1} would turn {end_j[i] - now_j[i]:+.0f} deg - refused")
    _ready()
    mm_s = LINEAR_SPEED[speed]
    dist = sum((a - b) ** 2 for a, b in zip(target[:3], now_p[:3])) ** 0.5
    _stopped.clear()
    r = arm.cmd("moveL", relFlag=0, cartPosition=list(target), speed=mm_s, accel=mm_s * ACCEL_FACTOR)
    if r.get("errorCode") != "0":
        raise MotionError(f"moveL refused: {r.get('errorMsg') or r}")
    if not wait:
        return list(target)
    d = _wait(lambda d: sum((a - b) ** 2 for a, b in zip(d["actual_position"][:3], target[:3])) ** 0.5 < AT_TCP_MM,
              dist / mm_s)
    return d["actual_position"]


def stop():
    """Stop any arm motion (also a running Cobo π program)."""
    _stopped.set()
    for _ in range(2):          # the controller stops the arm but sometimes closes the connection without a reply
        try:
            return arm.cmd("stop_program")
        except ConnectionError:
            pass
    return {"sent": True, "reply": None}


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if not a:
            print("joints", [round(v, 2) for v in joints()])
            print("tcp   ", [round(v, 1) for v in tcp()])
            for k, v in poses().items():
                print(f"pose {k:8s}", v)
        elif a[0] == "go":
            print(go(a[1], a[2] if len(a) > 2 else "slow"))
        elif a[0] == "teach":
            print(a[1], teach(a[1]))
        elif a[0] == "line":
            print(move_linear(delta=[float(v) for v in a[1:4]]))
        elif a[0] == "stop":
            print(stop())
        else:
            sys.exit(__doc__)
    except KeyboardInterrupt:
        print(stop())
    except MotionError as e:
        sys.exit(f"refused / failed: {e}")
