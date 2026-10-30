"""Follow a person with the base: "follow me" ... "stop" (lumi.py follow_me).

The person is a track of the assistant's Vision: `see()` gives (distance m, angle deg + left, age s, clothes signature)
or None once the track is gone, `people()` [(see, distance, angle, age, look)] of everyone in view. Every sighting is
put on the map (base pose + distance, angle) with a smoothed walking velocity, so between sightings the base drives
toward where the person is now, not where they were seen (no stop-and-go when frames are missed). A sighting far from
that place is someone else (a passer-by who took the track over); a lost track is swapped for a fresh one near that
place whose clothes are not clearly different (re-lock). The head turns toward the person in its own thread (only
this task moves the body meanwhile: head.owners), straight on them (up to +-180 on the waist), sent where they will be
seen from where the base will be when the move ends; the base turns toward them at the same time. The waist never
turns further out: following starts with it where it is (turned toward the person after "look behind") and it unwinds
as the base comes round (unwind). Nothing waits for another. The base is driven with joy_control every TICK_S (one
command lasts 0.5 s: a stuck loop stops the base by itself), the arm in look; forward only with the person near ahead
and the waist near the front. Every command is checked first: where the base and the arm would be BRAKE_S later must be clear
(lidar + map, agv.clearance); when not, the base stands, and after BLOCKED_END_S it gives up.

    stop()   from any thread: the event is set and the base is sent 0 at once
"""
import math
import re
import threading
import time
import traceback

import numpy as np

from robot import agv, head, motion
from tasks import fetch
from vision import reid

FOLLOW_GAP_M = 1.0          # m; keep this far from the person (camera distance); nearer: no forward
NEAR_STOP_M = 0.8           # m; nearer than this no turn either: the arm would swing close to them (estimate)
FOLLOW_MAX_MS = 0.5         # m/s; forward cap = joy_control's own clamp (docs/05). At 0.3 a person walking 0.6-0.75 m/s
                            # got 4 m ahead (2026-10-23 15:06): the cap, not the gain, was the lag
SPEED_GAIN = 0.8            # m/s per m the person is further than FOLLOW_GAP_M, on top of their walking speed (signed:
                            # coming back toward the base slows it). A standing person: 0.4 m/s 0.5 m beyond the gap
REACT_S = 0.3               # s; from a person stopping to the base braking (frame, track, tick, command); the speed is
                            # kept low enough to stop at the gap after this plus braking at DECEL_MS2 (estimate)
ACCEL_MS2 = 0.5             # m/s^2; speeding up at most this fast (estimate, tune live)
DECEL_MS2 = 0.8             # m/s^2; slowing down this fast, and never faster than lets it stop at the gap (estimate)
TURN_GAIN = 1.5             # rad/s per rad the person is off to the side
TURN_MAX_RS = 0.6           # rad/s; turn speed cap (joy_control takes up to 1.0; the arm tips sweep 0.6 m out)
TURN_ACCEL_RS2 = 2.0        # rad/s^2; turn speed changes at most this fast (estimate)
TURN_DEAD_DEG = 5.0         # deg; the person this near the middle: no turn
TURN_ONLY_DEG = 35.0        # deg; the person further aside: turn on the spot first, no forward
STALE_S = 0.4               # s; a sighting older than this is not new (Vision gives one per head camera frame, 15/s)
COAST_S = 1.0               # s after the last sighting the base drives on toward where they should be; then it slows
LOST_S = 3.0                # s without a sighting -> "I lost you" (lumi.Vision drops a track after its own LOST_S, 2 s)
VEL_TAU_S = 0.5             # s; time constant of the walking velocity filter (depth jumps a few cm per frame)
WALK_MAX_MS = 2.0           # m/s; a faster walking estimate is noise
JUMP_M = 0.5                # m; a sighting this far from where the person should be is someone else (estimate) ...
GATE_GROW_MS = 0.7          # ... plus this much per s unseen (they may have turned): re-lock radius (estimate)
SWITCH_M = 0.15             # m; another track must be this much nearer to where they should be to be taken (estimate)
RELOCK_LOOK = 0.6           # reid.same below this: clearly other clothes, not taken (same person 0.66-0.91, reid.py)
BRAKE_S = 0.5               # s; the base and the arm must be clear where this command would take them by then
BLOCKED_END_S = 5.0         # s standing in front of an obstacle before giving up
ARM_CLEAR_M = fetch.ARM_CLEAR_M                    # m; arm points kept this far from anything the lidar / map shows
BASE_CLEAR_M = fetch.BASE_HALF_M + fetch.CLEAR_M   # m; base centre kept this far, unless it gets further away
TICK_S = 0.1                # s between commands, steady (joy_control wants > 2 Hz; a tick takes ~10-30 ms)
LOG_S = 1.0                 # s between "follow: v ... " lines (what the next live run is read from)
JOIN_S = 2.0                # s a new "follow me" waits for the old loop to end
BEHIND_DEG = 180.0          # deg; the person's angle from the base is kept within +-this (right behind: one side)
HEAD_REL_MAX = 30.0         # deg; a turned waist unwinds until the person is this far from the base heading, the
                            # head looks for the rest (it never turns further out while following, unwind())
WAIST_FOLLOW_MAX = 90.0     # deg from the front; a waist turned further unwinds to this first (estimate)
WAIST_STEP_DEG = 8.0        # deg; one body move turns the waist at most this far, so every move is short (~0.4 s) and
                            # the head's next correction is not held back; the waist keeps on in the next move
WAIST_FOLLOW_VEL = 50       # speed ratio % of a move that turns the waist (the head in it too). The waist's deg/s at
                            # this ratio is not measured; estimate ~40 deg/s as the head's (audio/sing.py), about the
                            # base's own TURN_MAX_RS turn that sweeps the arm the same way. Lower it if the arm swings
                            # too hard (fetch.WAIST_VEL 20 is the search's long turns)
WAIST_DRIVE_DEG = 15.0      # deg; the base drives forward only with the waist this near the front: navigation does not
                            # know the arm, blocked() checks it turned (estimate)
WAIST_RETRY_S = 1.0         # s; a waist turn found blocked is not tried again for this long (each try probes the map)
HEAD_PITCH = 10.0           # deg; head pitch while following, a little up toward a standing person (as "look at me")
HEAD_STEP_DEG = 3.0         # deg; a new head move only when the target is this far from where the head was sent
HEAD_LEAD_S = 0.3           # s; the head is sent where the person will be, seen from where the base will be, this
HEAD_LEAD_MAX_S = 1.5       # much later at least, or as long as the last head move took (live 0.5-1.3 s), at most this:
                            # the base turning 0.6 rad/s goes 35-45 deg round in one move, which left the head off them
HEAD_VEL = 50               # speed ratio %; the head is at its full speed from 50 (audio/sing.py, measured)
HEAD_TIMEOUT_S = 5          # s; one head move (90 deg at ~40 deg/s takes ~2.5 s)

CHARGER = ("I'm on the charger, I can't follow you from here.", "충전 중이라 따라갈 수 없어요.")
ARM_BUSY = ("A program is running on my arm, so I can't follow you.", "팔에서 프로그램이 실행 중이라 따라갈 수 없어요.")
LOST = ("I lost you, so I stopped. Stand in front of me and say follow me again.",
        "놓쳐서 멈췄어요. 제 앞에 서서 다시 따라오라고 말해 주세요.")
NO_ARM = ("My arm is not answering, so I can't drive safely.", "팔이 응답하지 않아서 안전하게 이동할 수 없어요.")

_stop = threading.Event()
_send = threading.Lock()    # a command and the stop never cross: after stop() no drive command goes out
_thread = None
_followed = [None]          # (waist-frame angle deg, time) of the last sighting of the person followed now
SEEN_MAX_S = 1.5            # s; an older sighting does not tell where they are (lumi decides who speaks from it)


STOP_WORDS = re.compile(r"\b(stop|halt|freeze|enough|wait|hold on|stay(?! with)|don'?t (move|follow)|no more|"
                        r"that'?s (enough|far enough|it))\b|멈춰|그만|정지|스톱|스탑|거기 ?(있어|서|계세요|있으세요)|기다려|"
                        r"여기 ?(있어|서)|따라오지 ?마|됐어|^\s*서[\s,!.]*$", re.I)   # end following (only while it runs)


def stop_word(text):
    """A word that ends following ("stop", "wait", "that's enough", "거기 있어", "기다려")."""
    return bool(STOP_WORDS.search(text or ""))


def running():
    return _thread is not None and _thread.is_alive()


def followed_angle():
    """Waist-frame angle (deg, + left) of the person being followed, seen within SEEN_MAX_S; None if not following
    or not seen."""
    got = _followed[0]
    return got[0] if running() and got and time.time() - got[1] <= SEEN_MAX_S else None


def _joy(v, w):
    agv.request(f"/api/joy_control?linear_velocity={v:.3f}&angular_velocity={w:.3f}")


def stop():
    """End following at once: the base gets 0 now. True when it was following."""
    was = running()
    with _send:
        _stop.set()
        try:
            _joy(0.0, 0.0)
        except (ConnectionError, OSError) as e:
            fetch.log(f"follow: stop command failed: {e}")
    return was


def speeds(distance, angle_deg, v_last, w_last=0.0, walk=0.0, go=True, dt=TICK_S):
    """(v m/s, w rad/s) toward a person `distance` m away at `angle_deg` (+ left), walking `walk` m/s away (- toward
    the base): their speed plus SPEED_GAIN per m beyond the gap, never faster than lets the base stop at the gap,
    changed smoothly (ACCEL_MS2 / DECEL_MS2).
    Never forward inside the gap; nothing at all inside NEAR_STOP_M. go=False: only slow down (and turn)."""
    if distance < NEAR_STOP_M:
        return 0.0, 0.0
    a = math.radians(angle_deg)
    w_want = 0.0 if abs(angle_deg) < TURN_DEAD_DEG else max(-TURN_MAX_RS, min(TURN_MAX_RS, TURN_GAIN * a))
    w = w_last + max(-TURN_ACCEL_RS2 * dt, min(TURN_ACCEL_RS2 * dt, w_want - w_last))
    room = distance - FOLLOW_GAP_M
    if room <= 0:
        return 0.0, w                                   # at the gap: no forward now
    v_want = 0.0 if not go or abs(angle_deg) > TURN_ONLY_DEG else \
        min(FOLLOW_MAX_MS, walk + SPEED_GAIN * room, _brake_speed(room))
    v = min(v_last + ACCEL_MS2 * dt, max(v_last - DECEL_MS2 * dt, v_want))
    return max(0.0, v), w


def _brake_speed(room):
    """Fastest speed (m/s) from which the base still stops within `room` m: REACT_S at it, then DECEL_MS2 braking."""
    dr = DECEL_MS2 * REACT_S
    return math.sqrt(dr * dr + 2 * DECEL_MS2 * room) - dr


def blocked(v, w, arm_pts, pose=None):
    """Why the base or the arm would come too close to something within BRAKE_S at (v, w), None when clear."""
    x, y, th = pose or agv.pose()
    th2 = th + w * BRAKE_S
    x2, y2 = x + v * BRAKE_S * math.cos(th), y + v * BRAKE_S * math.sin(th)
    if v > 0:
        ahead = agv.clearance(x2, y2)
        if ahead < BASE_CLEAR_M and ahead < agv.clearance(x, y):
            return f"an obstacle {ahead:.2f} m from the base's way"
    c, s = math.cos(th2), math.sin(th2)
    c0, s0 = math.cos(th), math.sin(th)
    for p in arm_pts:
        px, py = x2 + c * p[0] - s * p[1], y2 + s * p[0] + c * p[1]
        near = agv.clearance(px, py)
        # as the base's: only coming nearer counts (beside a wall, driving along it stopped the follow, 2026-10-28)
        if near < ARM_CLEAR_M and near < agv.clearance(x + c0 * p[0] - s0 * p[1], y + s0 * p[0] + c0 * p[1]):
            return f"my arm would hit something at ({px:.2f}, {py:.2f})"
    return None


def ready():
    """Why following can't start now as (en, ko), None when it can. The arm goes to look; switched off (not powered /
    enabled) it stays where it is (it does not move while following, its points are checked), unless it reads all
    joints 0 (powered off: where it is is not known)."""
    if fetch._charging():
        return CHARGER
    try:
        if fetch._at_pose(fetch._look()):
            return None
        motion._ready()
    except motion.MotionError as e:
        if "program" in str(e):
            fetch.log(f"follow: the arm can't go to look: {e}")
            return ARM_BUSY
        if not any(fetch.skills._joints()):
            fetch.log("follow: the arm is powered off, where it is is not known")
            return fetch.ARM_UNSEEN
        fetch.log("follow: the arm is switched off: it stays where it is")
    except Exception as e:                               # the controller does not answer
        fetch.log(f"follow: the arm does not answer: {e!r}")
        return NO_ARM
    return None


def prepare():
    """Arm to look. The waist and the head stay where they are: they are on the person already (the track is seen),
    and ahead they may be out of view (lost at once). Returns the arm's points (m, base frame) that stick out past the
    base, [] when the arm's place on the base is not measured. FetchError when it must not drive."""
    why = ready()
    if why:
        raise fetch.FetchError(*why)
    fetch._stop.clear()                                  # a stop said earlier must not end this one
    fetch._drive_pose()
    if fetch.arm_yaw() is None:
        fetch.log("follow: the arm's place on the base is not measured: only the base is checked")
        return []
    return [np.asarray(p, float) for p in fetch.arm_points()]


def _to_map(pose, d, a):
    """Map point (x, y) of a sighting d m away at a deg (+ left) from the base at pose (the camera ~ the base centre)."""
    x, y, th = pose
    return np.array([x + d * math.cos(th + math.radians(a)), y + d * math.sin(th + math.radians(a))])


def _seen_from(pose, turned):
    """The base pose turned by the waist's turn (deg): sightings are waist-frame angles (lumi.Vision), _to_map them
    from this."""
    return pose[0], pose[1], pose[2] + math.radians(turned)


def _rel(pose, p):
    """(distance m, angle deg + left) of the map point p from the base at pose."""
    x, y, th = pose
    a = math.degrees(math.atan2(p[1] - y, p[0] - x) - th)
    return math.hypot(p[0] - x, p[1] - y), (a + 180.0) % 360.0 - 180.0


class Person:
    """Where the followed person is on the map: the last sighting (p, t) and a smoothed walking velocity."""

    def __init__(self):
        self.p, self.t, self.vel = None, None, np.zeros(2)

    def seen(self, p, t):
        if self.p is not None:
            if t <= self.t + 1e-3:
                return                                   # the same sighting read again
            k = (t - self.t) / (VEL_TAU_S + t - self.t)
            vel = (1 - k) * self.vel + k * (p - self.p) / (t - self.t)
            speed = float(np.linalg.norm(vel))
            self.vel = vel if speed <= WALK_MAX_MS else vel * WALK_MAX_MS / speed
        self.p, self.t = p, t

    def at(self, t):
        """Where they should be at t (the walk is carried on for COAST_S at most)."""
        return self.p + self.vel * min(max(t - self.t, 0.0), COAST_S)


def _fresh(got):
    return got is not None and got[2] < STALE_S


def _pick(see, got, people, person, pose, sig, now):
    """(see, sighting) of the followed person this tick: of their own track's sighting and every fresh one in view the
    nearest to where they should be, within JUMP_M (growing while unseen) and not in clearly other clothes. A track
    taken over by a passer-by jumps away from that place, the person's own new track is near it. Their own track is
    kept unless another is SWITCH_M nearer (the same track also comes in people()). Sighting None: none."""
    cands = [(see, got)] if _fresh(got) else []
    cands += [(s, tuple(g)) for s, *g in (people() if people else ()) if _fresh(g)]
    if person.p is None:                                 # nothing to compare with yet: their own track
        return see, (got if _fresh(got) else None)
    gate = JUMP_M + GATE_GROW_MS * min(max(now - person.t - STALE_S, 0.0), LOST_S)
    best = (float("inf"), see, None)
    for s, g in cands:
        e = float(np.linalg.norm(_to_map(pose, *g[:2]) - person.at(now - g[2])))
        if e > gate or sig is not None and g[3] is not None and reid.same(sig, g[3]) < RELOCK_LOOK:
            continue
        e -= SWITCH_M if s is see else 0.0
        if e < best[0]:
            best = (e, s, g)
    return best[1:]


def waist_for(b):
    """Waist turn (deg from the front, + left) for a person b deg from the base heading: what is past HEAD_REL_MAX,
    up to WAIST_FOLLOW_MAX. 0 when they are near ahead, so it unwinds as the base turns to them."""
    return max(-WAIST_FOLLOW_MAX, min(WAIST_FOLLOW_MAX, math.copysign(max(0.0, abs(b) - HEAD_REL_MAX), b)))


def unwind(w, b):
    """Where the waist, turned w deg, goes for a person b deg from the base heading: toward waist_for(b), but only
    back toward the front, never further out. Turning out made every move a slow waist move and, with the base turning
    the same way, left the head 40-70 deg off the person (live 2026-10-29, lost): the head alone follows them, the
    base turns, and the waist unwinds as the base comes round (the head's turn back gets smaller, not bigger)."""
    goal = waist_for(b)
    return 0.0 if goal * w <= 0.0 else math.copysign(min(abs(goal), abs(w)), w)


def _head_follow(target, done, lift, front, w, waist_free, stats):
    """Turn the head to the person at target[0] (deg from the base heading, pitch), the waist back toward the front
    with it. Every move sends the head straight to them (up to +-BEHIND_DEG on the waist, never held back) and the waist
    at most WAIST_STEP_DEG toward unwind() in the same move, so a turned waist comes back move after move while the base
    turns and the head stays on the person all along. Every waist step is checked along the arm's sweep (fetch.turn_hits);
    blocked, or waist_free False (arm not in look, its place not measured): the waist stays and the head alone turns.
    `front`: the waist's reading at the front, `w`: its turn from there now. One moveto at a time, from this thread
    only: overlapping calls hang the body API. The drive loop never waits for it."""
    sent, retry = None, 0.0                               # (head yaw, pitch) sent last
    while not done.is_set():
        t = target[0]
        if t is None:
            done.wait(TICK_S / 2)
            continue
        b, pitch = t
        want = unwind(w, b) - w if waist_free and time.time() >= retry else 0.0
        step = max(-WAIST_STEP_DEG, min(WAIST_STEP_DEG, want))
        if abs(step) < HEAD_STEP_DEG and (waist_for(b) != 0.0 or abs(step) < 0.5):
            step = 0.0                                    # small steps only for the last bit to the front
        yaw = max(-BEHIND_DEG, min(BEHIND_DEG, b - w - step))
        off = float("inf") if sent is None else max(abs(yaw - sent[0]), abs(pitch - sent[1]))
        if step == 0.0 and off < HEAD_STEP_DEG:
            done.wait(TICK_S / 2)
            continue
        if step:
            try:
                hit = fetch.turn_hits(step)
            except (ConnectionError, OSError, ValueError, KeyError) as e:   # not checked: not turned
                fetch.log(f"follow: the waist's sweep can't be checked: {e!r}")
                hit = ()
            if hit is not None:
                if hit:
                    fetch.log(f"follow: waist stays at {w:+.0f} deg, turning {step:+.0f} my arm would hit something "
                              f"at ({hit[0]:.2f}, {hit[1]:.2f}); the head turns alone")
                retry = time.time() + WAIST_RETRY_S
                continue                                  # at once again: the head alone
        vel = min(HEAD_VEL, WAIST_FOLLOW_VEL) if step else HEAD_VEL
        try:
            t0 = time.time()
            head.moveto([lift, front + w + step, yaw, pitch], vel=vel, acc=vel, timeout=HEAD_TIMEOUT_S)
            w += step
            sent, stats["head"], stats["head_ms"] = (yaw, pitch), yaw, round(1000 * (time.time() - t0))
        except (ConnectionError, OSError, ValueError, KeyError) as e:
            fetch.log(f"follow: head error {e!r}")
            done.wait(1.0)


def _run(see, say, people):
    """The loop: until stop(), lost, or something in the way. Any failure ends with the base at 0 and a reason said."""
    v = w = 0.0
    done, target, stats = threading.Event(), [None], {"head": None, "head_ms": None}
    head.owners = (threading.current_thread(),)
    person, head_thread, front = Person(), None, None
    try:
        got = see()                                      # where they are now (waist-frame angle)
        sig = got[3] if got else None
        if _fresh(got):
            person.seen(_to_map(_seen_from(agv.pose(), fetch._waist_turn()), *got[:2]), time.time() - got[2])
        arm_pts = prepare()
        agv.set_max_speed(FOLLOW_MAX_MS, TURN_MAX_RS)          # joy_control is capped by it too (the next
        lift, waist, yaw = head.status()[:3]                   # navigation move sends its own again)
        turned = fetch._waist_turn()
        front, gaze = waist - turned, turned + yaw        # the waist's reading at the front; where the head looks
        waist_free = bool(arm_pts)                        # its sweep can be checked ...
        if waist_free:
            try:
                waist_free = fetch._at_pose(fetch._look())   # ... and the arm is folded in look
            except Exception as e:
                waist_free = False
                fetch.log(f"follow: the arm's pose can't be read: {e!r}")
            if not waist_free:
                fetch.log("follow: my arm is not in look: the waist stays, the head turns alone")
        if not waist_free and abs(turned) >= WAIST_DRIVE_DEG:   # it would never drive: the waist to the front, the
            look = got[1] if _fresh(got) else None             # head kept on them (fetch._waist_to checks the sweep)
            if not fetch._waist_to(0.0, in_place=True, look=look):
                raise fetch.FetchError("My arm can't turn back to the front: something is in its way.",
                                       "팔을 앞으로 돌릴 수 없어요. 뭔가 막고 있어요.")
            lift, waist, yaw = head.status()[:3]
            turned = waist - front
            gaze = turned + yaw
        head_thread = threading.Thread(target=_head_follow, args=(target, done, lift, front, turned, waist_free, stats),
                                       daemon=True, name="follow head")
        head.owners += (head_thread,)
        head_thread.start()
        start_t = next_t = time.time()                   # lost counts from here: prepare() takes a few seconds
        turning, blocked_t, hold_v, log_t, odd_t, log_pose = False, None, 0.0, 0.0, 0.0, agv.pose()
        while not _stop.is_set():
            now = time.time()
            pose = agv.pose()
            try:
                turned = head.status()[1] - front
            except (ConnectionError, OSError, KeyError):
                pass                                     # the last reading: the body API may be busy
            seen_from = _seen_from(pose, turned)
            mine, was = see(), see
            see, got = _pick(see, mine, people, person, seen_from, sig, now)
            if see is not was:
                fetch.log(f"follow: re-locked onto the person at {got[0]:.2f} m {got[1]:+.0f} deg")
            elif got is None and _fresh(mine) and now - odd_t > LOG_S:
                odd_t = now
                fetch.log(f"follow: a sighting at {mine[0]:.2f} m {mine[1]:+.0f} deg is not them (someone else)")
            if _fresh(got):
                _followed[0] = (got[1], now - got[2])
                p = _to_map(seen_from, *got[:2])
                person.seen(p, now - got[2])
                near = [float(np.linalg.norm(_to_map(seen_from, *o[1:3]) - p)) for o in people() if _fresh(o[1:])] \
                    if people else [0.0]
                if got[3] is not None and all(e > JUMP_M or e < 0.05 for e in near):   # alone (or themselves):
                    sig = reid.blend(sig, got[3])                                          # these clothes are theirs
            if now - max(person.t or 0.0, start_t) >= LOST_S:
                fetch.log("follow: lost the person")
                fetch._say(say, *LOST)
                return
            if person.p is None:                         # not seen yet (only before the first sighting)
                cmd, d, a, walk = (0.0, 0.0), 0.0, 0.0, 0.0
            else:
                # angles from the base heading, taken on from the last target, not -180..180: right behind, +179
                # and -179 are the same place, the head and waist must not swing round, the base not turn the other way
                ref = target[0][0] if target[0] else gaze
                d, a = _rel(pose, person.at(now))
                a = ref + (a - ref + 180.0) % 360.0 - 180.0
                lead = max(HEAD_LEAD_S, min((stats["head_ms"] or 0) / 1000.0, HEAD_LEAD_MAX_S))
                then = (pose[0] + v * lead * math.cos(pose[2]), pose[1] + v * lead * math.sin(pose[2]),
                        pose[2] + w * lead)                  # the base when the head gets there (v, w: this command)
                yaw = _rel(then, person.at(now + lead))[1]
                yaw = ref + (yaw - ref + 180.0) % 360.0 - 180.0
                target[0] = (max(-BEHIND_DEG, min(BEHIND_DEG, yaw)), HEAD_PITCH)
                walk = float(person.vel @ np.array([math.cos(pose[2]), math.sin(pose[2])]))
                go = now - person.t <= COAST_S and abs(turned) < WAIST_DRIVE_DEG   # forward with the waist ahead
                cmd = speeds(d, a, v, w, walk, go=go, dt=TICK_S)
            spot = cmd[0] == 0.0 and cmd[1] != 0.0      # a turn on the spot (the person aside or behind)
            if spot and not turning:
                hit = fetch.turn_hits(a - turned)        # the arm's whole sweep toward them (it is turned already)
                if hit is not None:
                    fetch.log(f"follow: turning {a:+.0f} deg my arm would hit something at "
                              f"({hit[0]:.2f}, {hit[1]:.2f})")
                    fetch._say(say, "My arm can't turn here, something is in its way.",
                               "팔이 부딪힐 수 있어서 돌 수 없어요.")
                    return
            turning = spot
            # stopped by something: on again only when the speed it was stopped at is clear (no creeping up to it)
            pts = [fetch._rot(turned) @ p for p in arm_pts]   # the arm turned with the waist
            why = cmd != (0.0, 0.0) and blocked(max(cmd[0], hold_v) if cmd[0] else 0.0, cmd[1], pts, pose)
            if why:
                if blocked_t is None:
                    fetch.log(f"follow: standing, {why}")
                blocked_t, hold_v, cmd = blocked_t or now, max(hold_v, cmd[0]), (0.0, 0.0)
                if now - blocked_t >= BLOCKED_END_S:
                    fetch._say(say, "Something is in my way, so I stopped.", "앞이 막혀서 멈췄어요.")
                    return
            elif cmd != (0.0, 0.0):
                blocked_t, hold_v = None, 0.0
            with _send:
                if _stop.is_set():
                    return
                _joy(*cmd)
            v, w = cmd
            if now - log_t >= LOG_S:             # driven: what the base really did since the last line (pose)
                driven = math.hypot(pose[0] - log_pose[0], pose[1] - log_pose[1]) / max(now - log_t, 1e-3)
                log_t, log_pose = now, pose
                fetch.log(f"follow: v {v:.2f} w {w:+.2f} driven {driven:.2f} m/s | person {d:.2f} m {a:+.0f} deg, seen "
                          f"{now - (person.t or now):.2f} s ago, walking {walk:+.2f} m/s | waist {turned:+.0f} head "
                          f"{stats['head'] or 0:+.0f} deg ({stats['head_ms']} ms) | tick {1000 * (time.time() - now):.0f} ms")
            next_t = max(next_t + TICK_S, time.time())   # a steady rate; a slow tick is not caught up
            _stop.wait(next_t - time.time())
    except fetch.Stopped:
        pass
    except fetch.FetchError as e:
        fetch.log(f"follow: {e}")
        fetch._say(say, e.args[0], e.args[1] if len(e.args) > 1 else "죄송해요, 따라갈 수 없어요.")
    except (ConnectionError, OSError) as e:
        fetch.log(f"follow: base error {e}")
        fetch._say(say, "Sorry, I can't drive right now.", "죄송해요, 지금은 이동할 수 없어요.")
    except Exception as e:                               # never die silently after "Okay, I'll follow you"
        fetch.log(f"follow: failed: {e!r}")
        traceback.print_exc()
        fetch._say(say, "Sorry, something went wrong, so I stopped following.",
                   "죄송해요, 문제가 생겨서 따라가기를 멈췄어요.")
    finally:
        done.set()
        with _send:
            try:
                _joy(0.0, 0.0)
            except (ConnectionError, OSError):
                pass                                   # one command lasts 0.5 s: the base stops anyway
        if head_thread is not None:                    # the head back to rest (ahead, looking down), the waist to
            head_thread.join(HEAD_TIMEOUT_S)           # the front, once its own move has ended: overlapping movetos
            try:                                       # hang the body API
                lift, waist = head.status()[:2]
                back = front - waist
                if abs(back) >= 1.0 and fetch.turn_hits(back) is not None:
                    fetch.log(f"follow: the waist stays at {-back:+.0f} deg: my arm would hit something going back")
                    back = 0.0
                vel = fetch.WAIST_VEL if abs(back) >= 1.0 else HEAD_VEL
                head.moveto([lift, waist + back, 0.0, head.HEAD_REST_PITCH], vel=vel, acc=vel,
                            timeout=60 if abs(back) >= 1.0 else HEAD_TIMEOUT_S)
            except (ConnectionError, OSError, ValueError, KeyError) as e:
                fetch.log(f"follow: head error {e!r}")
        head.owners = ()
        fetch.log("follow: ended")


def start(see, say=None, people=None):
    """Follow the person `see()` reports, in the background; a follow running already is ended first. Call ready()
    before saying yes."""
    global _thread
    if running():
        stop()
        _thread.join(JOIN_S)
    _stop.clear()
    _followed[0] = None
    fetch.log("follow: start")
    _thread = threading.Thread(target=_run, args=(see, say, people), daemon=True, name="follow")
    _thread.start()
