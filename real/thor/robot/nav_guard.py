"""Keeps the arm off things while navigation drives (/api/move to a marker or a point). The base plans and avoids
obstacles for its own footprint only; the arm sticks out past it (in look the flange is ~0.44 m from the base
centre). agv.go() / go_point() start watch() for every navigation move. While the move runs, the arm's points
(flange, grasp point, finger tips: tasks.fetch.arm_points) are checked at the base's pose now, turned on at its turn
rate for TURN_AHEAD_S, and along the planned path up to LOOKAHEAD_M ahead. An arm point that would come nearer than
MARGIN_M to anything the lidar or the map shows (agv.clearance), and nearer than it is now, cancels the move (the base
has no pause command; cancel stops it on the spot). The same goal is sent again once that way has been clear for
CLEAR_S; blocked BLOCK_S in all, the move ends "failed" with REASON (agv.status() "guard").

While the guard holds a move, agv.status() reports it "running", so every waiter (fetch, missions, come here,
the dashboard route) waits on; agv.cancel() or a new go ends the guard.
"""
import math
import threading
import time

from robot import agv

MARGIN_M = 0.10        # m; an arm point nearer than this to an obstacle stops the drive (estimate, tune live)
LOOKAHEAD_M = 0.30     # m along the planned path checked ahead of the base: ~1 s at 0.3 m/s, its stop included (estimate)
STEP_M = 0.15          # m between the path points checked
TURN_AHEAD_S = 0.5     # s; a turning base (on the spot at a goal too) is checked this far ahead at its turn rate now
POLL_S = 0.1           # s between checks (a check is ~10 distance probes at 5-15 ms each: ~5-8 Hz in all)
PATH_EVERY_S = 1.0     # s between reads of the planned path
START_S = 3.0          # s after a move is sent in which a status other than "running" is not believed yet
CLEAR_S = 1.0          # s the way must stay clear before the goal is sent again
BLOCK_S = 10.0         # s blocked in all (per goal) -> the move ends: the drive waiters' stuck checks are 20 / 30 s
REASON = ("I stopped: my arm would hit something on the way.", "팔이 가는 길에 있는 것에 부딪힐 것 같아서 멈췄어요.")


def log(msg):
    print(time.strftime("%H:%M:%S"), "nav guard:", msg, flush=True)


def _arm():
    """The arm's points (x, y) m in the base frame, None when they can't be known (arm axis not measured, arm
    controller not answering): then navigation drives unguarded, as before."""
    try:
        from tasks import fetch            # imported here: fetch imports agv, which starts this
        return [tuple(p) for p in fetch.arm_points()] if fetch.arm_yaw() is not None else None
    except Exception as e:                 # never stop a drive because the arm could not be asked
        log(f"no arm points ({e}): unguarded")
        return None


def _world(pose, p):
    x, y, th = pose
    c, s = math.cos(th), math.sin(th)
    return x + c * p[0] - s * p[1], y + s * p[0] + c * p[1]


def ahead(pose, path, turn_rate):
    """Base poses (x, y, theta) to check: the pose turned on at turn_rate (rad/s) for TURN_AHEAD_S, then every STEP_M
    along `path` ([[x, y], ...], from its point nearest the base) up to LOOKAHEAD_M, heading along the path.
    ponytail: the base is taken to drive forward along the path; a reversing drive is checked at the turn only."""
    out = [(pose[0], pose[1], pose[2] + turn_rate * TURN_AHEAD_S)] if abs(turn_rate) > 0.05 else []
    if len(path) < 2:
        return out
    i = min(range(len(path)), key=lambda k: math.hypot(path[k][0] - pose[0], path[k][1] - pose[1]))
    want, done = STEP_M, 0.0
    for a, b in zip(path[i:], path[i + 1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if seg < 1e-6:
            continue
        th = math.atan2(b[1] - a[1], b[0] - a[0])
        while want <= min(done + seg, LOOKAHEAD_M) + 1e-9:
            f = (want - done) / seg
            out.append((a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]), th))
            want += STEP_M
        done += seg
        if done >= LOOKAHEAD_M:
            break
    return out


def hit(pose, poses, pts):
    """The map point where an arm point at one of `poses` comes nearer than MARGIN_M to an obstacle and nearer than
    it is at `pose` now (getting further from one is fine: it may start next to a table); None when clear."""
    for p in pts:
        now = agv.clearance(*_world(pose, p))
        for q in poses:
            w = _world(q, p)
            c = agv.clearance(*w)
            if c < MARGIN_M and c < now:
                return w
    return None


def watch(command, gen):
    """Guard the navigation move `command` (sent just now) until it ends or agv's guard generation moves on."""
    threading.Thread(target=_run, args=(command, gen), daemon=True, name="nav-guard").start()


def _status():
    return agv.request("/api/robot_status").get("results") or {}


def _pose(st):
    p = st.get("current_pose") or {}
    return (p["x"], p["y"], p["theta"]) if "x" in p else None


def _run(command, gen):
    pts = _arm()
    if not pts:
        return
    mine = lambda: agv._guard["gen"] == gen
    sent, path, path_t, last, rate, blocked = time.time(), [], 0.0, None, 0.0, 0.0
    while mine():
        time.sleep(POLL_S)
        try:
            st = _status()
            pose = _pose(st)
            if st.get("move_status") != "running":
                if time.time() - sent > START_S:
                    agv._guard["held"] = False
                    return                                 # arrived, failed, or cancelled by someone else
                continue
            agv._guard["held"] = False                     # going again after a hold
            if pose is None:
                continue
            now = time.time()
            if last is not None and now > last[1]:
                rate = ((pose[2] - last[0][2] + math.pi) % (2 * math.pi) - math.pi) / (now - last[1])
            last = (pose, now)
            if now - path_t > PATH_EVERY_S:
                path, path_t = agv.request("/api/get_planned_path").get("results", {}).get("path") or [], now
            w = hit(pose, ahead(pose, path, rate), pts)
        except (OSError, KeyError, TypeError, ValueError):
            continue
        if w is None or not mine():
            continue
        agv._guard["held"] = True                          # before the cancel: waiters never see "canceled"
        try:
            agv.request("/api/move/cancel")
        except OSError as e:
            log(f"cancel failed: {e}")
        log(f"stopped at ({pose[0]:.2f}, {pose[1]:.2f}): the arm would come within {MARGIN_M:.2f} m of something "
            f"at ({w[0]:.2f}, {w[1]:.2f})")
        blocked = _hold(command, gen, path, rate, pts, blocked)
        if blocked is None:
            return
        sent, last, path_t = time.time(), None, 0.0


def _hold(command, gen, path, rate, pts, blocked):
    """Wait, the base stopped, until the way it was going is clear for CLEAR_S, then send `command` again; returns
    the time blocked so far. None when the guard ends here: BLOCK_S blocked in all (the move fails with REASON), an
    E-stop, or agv moved on (cancel, a new go)."""
    t0, clear_since = time.time(), None
    while agv._guard["gen"] == gen:
        time.sleep(POLL_S)
        if blocked + time.time() - t0 > BLOCK_S:
            agv._guard.update(held=False, reason=REASON)
            log(f"blocked {BLOCK_S:.0f} s: the move ends")
            return None
        try:
            st = _status()
            if st.get("soft_estop_state") or st.get("hard_estop_state") or st.get("estop_state"):
                agv._guard.update(held=False, reason=REASON)
                log("E-stop while stopped: the move ends")
                return None
            pose = _pose(st)
            w = None if pose is None else hit(pose, ahead(pose, path, rate), pts)
        except (OSError, KeyError, TypeError, ValueError):
            continue
        if pose is None or w is not None:
            clear_since = None
            continue
        clear_since = clear_since or time.time()
        if time.time() - clear_since < CLEAR_S:
            continue
        if agv._guard["gen"] != gen:
            break
        try:
            r = agv.request(command)
        except OSError as e:
            r = {"error_message": str(e)}
        if r.get("status") != "OK":
            agv._guard.update(held=False, reason=REASON)
            log(f"could not go on ({r.get('error_message') or r.get('status')}): the move ends")
            return None
        log("the way is clear: going on")              # held until the base reports "running" (_run)
        return blocked + time.time() - t0
    return None
