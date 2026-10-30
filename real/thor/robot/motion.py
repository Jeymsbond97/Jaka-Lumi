"""Checked arm motion over the controller's TCP command port (10001, JSON, no SDK): named poses, joint moves,
straight-line TCP moves, stop.

Every move is checked before it is sent: joint limits with a margin, and for linear moves an IK solution
(the controller's kine_inverse) that does not swing J1 / J4 / J6 around. Moves wait until the arm is there,
and return early with an error when STOP was pressed or the controller stopped the arm.

    python robot/motion.py                     # joints, TCP, named poses
    python manipulation/arm_route.py goto look # to a named pose: only along the pose graph, checked
    python robot/motion.py teach ready         # save the arm's current joints as a named pose (move it in Cobo π first)
    python robot/motion.py line 0 0 30         # straight TCP move by dx dy dz mm (base frame), slow
    python robot/motion.py stop

Poses taught with `teach` are kept in arm_poses.json next to this file.
"""
import json
import sys
import threading
import time
from pathlib import Path

from robot import arm

ROOT = Path(__file__).resolve().parents[1]      # the project folder
POSES_FILE = ROOT / "data" / "arm_poses.json"
LIMITS = [360, 125, 130, 360, 120, 360]              # deg, ± factory range per joint (docs/01_HARDWARE.md)
LIMIT_MARGIN = 5.0                                   # deg kept away from every limit
JOINT_SPEED = {"slow": 10.0, "normal": 25.0, "fast": 40.0, "quick": 50.0, "route": 60.0}   # deg/s; route: empty-hand pose-graph moves (the Cobo π joint speed limit, 60)
LINEAR_SPEED = {"slow": 20.0, "normal": 50.0}        # mm/s
ACCEL_FACTOR = 3.0                                   # straight moves: accel = speed x this (per s)
JOINT_ACCEL_FACTOR = 1.5                             # joint moves: accel = speed x this (per s); estimate: x 3
                                                     # stopped at each pose with a jolt that shook the robot
MAX_FLIP = 90.0                                      # deg; an IK answer turning J1 / J4 / J6 more than this is refused
MAX_TRAVEL = 200.0                                   # deg; a joint move turning any joint further is refused
FULL_TURN = (0, 3, 5)                                # J1, J4, J6: ±360 joints; a target and target ± 360 are the same pose
AT_JOINT_DEG = 0.3                                   # arrived when every joint is this close ...
AT_TCP_MM = 1.0                                      # ... or the TCP this close (linear moves)
POLL_S = 0.1
EXTRA_S = 10.0                                       # s allowed on top of the longest a move may take
SLOW_DEG_S = 5.0                                     # deg/s; long joint moves ran this slow whatever the speed asked
                                                     # (measured: 157 deg of J6 in 37 s, 60 deg of J1 in 8.5 s)
STILL_S = 2.0                                        # s without joint motion (and not there) -> the move ended short
STILL_DEG = 0.05                                     # joint change that counts as motion
BLIND_S = 3.0                                        # s without a valid state reply while moving -> stop the arm
                                                     # (the controller drops its connections ~0.5 s every few s and
                                                     # arm.cmd retries for up to ~3 s: at 1.0 a reach stopped half way)
SETTLE_S = 0.3                                       # s the arm stands at a pose before the next move (estimate;
                                                     # going straight on shook the whole robot, 2026-10-21)

_stopped = threading.Event()                         # set by stop(): a waiting move gives up


class MotionError(RuntimeError):
    pass


def _read(name, key):
    """A value read from the controller. It now and then answers with another command's reply (get_data or
    get_robot_state to get_joint_pos, 2026-10-16): ask again."""
    for _ in range(arm.RETRIES):
        r = arm.cmd(name)
        if key in r:
            return r[key]
        time.sleep(arm.RETRY_S)
    raise MotionError(f"{name} failed: {r.get('errorMsg') or r.get('cmdName') or r}")


def joints():
    return _read("get_joint_pos", "joint_pos")


def tcp():
    return _read("get_tcp_pos", "tcp_pos")


def poses():
    """Named poses: everything taught."""
    try:
        return json.loads(POSES_FILE.read_text())
    except FileNotFoundError:
        return {}


def teach(name):
    """Save the current joints as pose `name`."""
    check(j := [round(v, 2) for v in joints()])
    taught = poses()
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


def _queue_empty():
    """The controller has no motion command left to run (get_motion_state; an odd reply counts as not empty)."""
    try:
        r = arm.cmd("get_motion_state")
    except (ConnectionError, OSError):
        return False
    return r.get("queue") == 0 and r.get("active_queue", 0) == 0


def _wait(arrived, limit_s, queued=False):
    """Wait while the arm moves, at most limit_s. Big moves run far slower than the speed asked (SLOW_DEG_S), so the
    limit is generous; a move that stops short is caught by STILL_S instead. `queued`: several moves were sent at
    once, so arrived also needs the controller's queue empty (the swings pass their last pose before the end)."""
    t0 = last_move = last_seen = time.time()
    last = None
    while time.time() - t0 < limit_s:
        if _stopped.is_set():
            raise MotionError("stopped")
        try:
            d = arm.cmd("get_data")
        except (ConnectionError, OSError) as e:
            d = {"error": repr(e)}
        if "joint_actual_position" not in d:     # the controller now and then answers a poll with nothing
            if time.time() - last_seen > BLIND_S:
                stop()
                raise MotionError(f"lost the arm state while moving - stopped (last reply: {str(d)[:120]})")
            time.sleep(POLL_S)
            continue
        last_seen = time.time()
        if d.get("protective_stop") or d.get("emergency_stop"):
            raise MotionError("the controller stopped the arm (protective / emergency stop)")
        if d.get("inpos") and arrived(d) and (not queued or _queue_empty()):
            return d
        j = d["joint_actual_position"]
        if last is None or max(abs(a - b) for a, b in zip(j, last)) > STILL_DEG:
            last, last_move = j, time.time()
        elif time.time() - last_move > STILL_S and time.time() - t0 > STILL_S + 1:
            stop()                              # nothing may run on later
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
    return move_path([(target, speed)], wait)


def move_path(moves, wait=True, queued=False):
    """Joint moves [(joints, speed)], all checked before the first is sent, then one at a time: each waits until the
    arm is there (inpos, every joint within AT_JOINT_DEG) and stands SETTLE_S before the next is sent. `queued`: all
    sent at once instead, the controller runs them back to back (docs/04 §10; the wave's swings) and only the end is
    waited for. stop() ends it at any point. Returns the joints reached (wait=False: the last move is not waited for,
    its target)."""
    for t, _ in moves:
        check(t)
    _ready()
    prev, seq = joints(), []
    for t, speed in moves:
        t = nearest(t, prev)
        for i, (a, b) in enumerate(zip(t, prev)):
            if abs(a - b) > MAX_TRAVEL:
                raise MotionError(f"J{i + 1} would turn {a - b:+.0f} deg - refused")
        seq.append((t, speed, max(abs(a - b) for a, b in zip(t, prev))))
        prev = t
    _stopped.clear()
    d, limit = None, 0.0
    for k, (t, speed, deg) in enumerate(seq):
        if k and not queued and _stopped.wait(SETTLE_S):
            raise MotionError("stopped")
        deg_s = JOINT_SPEED[speed]
        r = arm.cmd("joint_move", relFlag=0, jointPosition=list(t), speed=deg_s, accel=deg_s * JOINT_ACCEL_FACTOR)
        if _stopped.is_set():               # STOP pressed while sending: stop again, after this move
            stop()
            raise MotionError("stopped")
        if r.get("errorCode") != "0":
            if queued and k:
                stop()                      # the moves already queued must not run on alone
            raise MotionError(f"joint_move refused: {r.get('errorMsg') or r}")
        last = k == len(seq) - 1
        limit += max(3 * deg / deg_s, deg / SLOW_DEG_S)
        if queued and not last:
            continue
        if not wait and last:
            return list(t)
        d = _wait(lambda d, t=t: max(abs(a - b) for a, b in zip(d["joint_actual_position"], t)) < AT_JOINT_DEG,
                  limit + EXTRA_S, queued=queued and len(seq) > 1)
        limit = 0.0
    return d["joint_actual_position"]


def go(name, speed="slow", wait=True):
    p = poses()
    if name not in p:
        raise MotionError(f"no pose {name!r} (known: {', '.join(p)})")
    return move_joints(p[name], speed, wait)


def move_linear(target=None, delta=None, speed="slow", wait=True, path_checked=False):
    """Straight TCP move to `target` [x, y, z mm, rx, ry, rz deg] or by `delta` (dx, dy, dz mm), base frame.
    The end pose is checked with the controller's IK first. `path_checked`: the caller checked the whole line in
    small steps (fetch._line_rows), so a big J1 / J4 / J6 turn over it is a real one, not another IK branch."""
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
    end_j = ik["jointPosition"][:6]      # some answers carry a 7th (external axis) value
    check(end_j)
    for i in () if path_checked else (0, 3, 5):
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
              3 * dist / mm_s + EXTRA_S)
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
