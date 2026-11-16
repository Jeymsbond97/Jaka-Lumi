"""Wave back at people who wave at Lumi: the dashboard switch "Wave greeting", with or without Greeter / Patrol. It
runs in the process that owns the robot: the API's (api/server.py) while the assistant is off, the assistant's
(assistant/lumi.py) while it runs. There it waits while a drive, task, skill or conversation has the robot; a drive
or turn brings a raised hand down first (lower()).

Someone waving GREET_MIN_M .. GREET_M from either camera (vision/waving.py; the head camera may look elsewhere): the head turns to them and the arm goes up at
once (manipulation/wave.py checks and plans the way, look -> wave_out -> wave_start, at the route speed), Lumi says a
greeting (tasks/wave_lines.py; it introduces itself once to a person, until they leave the cameras' view: vision/reid.py
face, else clothes), swings once even when they stopped meanwhile, then turns the waist to face them (fetch._waist_to,
its sweep checked; the head stays on them). It swings back to back while they wave (one swing always queued behind
the running one, no stop between), stops when they stop and keeps the hand up; waving again swings again. A long wave gets a joke now and then. Nobody waving for HOLD_S: the waist
back to its rest (the front unless start() says otherwise), the hand stays up (held, the idle swings now and then); only the switch turned off,
a drive or an order for the arm brings it down.

Any stop or failure of the arm (STOP, a person too close while the arm goes up, a refused move) switches the greeting
off: it never moves again by itself after a stop.
"""
import json
import math
import random
import threading
import time

import cv2
import numpy as np

from manipulation import arm_route, wave
from robot import head, motion
from tasks import wave_lines
from robot import arm
from vision import camview, pose, reid, waving

CAMERAS = ("head", "torso")   # both watched: the head may look away while the person is in the torso camera's view
GREET_MIN_M, GREET_M = 1.0, 5.0   # m; people waving nearer or further away are not answered (owner)
PASSER_MIN_M, PASSER_M = 0.8, 6.0   # m; a drive with Wave on stops for people passing this near (passer_wave), each
                             # person once, and only when nobody is within IDLE_CLEAR_M (owner, 2026-11-16)
SHOULDER_M = 0.36            # m between the shoulder keypoints: a waver's distance from their width in the image when
                             # depth has none there (far, or a colour-only camera); estimate (recordings 0.32-0.40)
HOLD_S = 15.0                # s the waist stays on the last one who waved, then back to its rest, the hand kept up and
                             # the idle swings at once (owner: every 15 s on the charger, also among many people)
GONE_S = 10.0                # s a greeted person may be out of both cameras' view and still be known (no new intro)
SWING_POLL_S = 0.2           # s between looks at the controller's queue while swinging
SWING_S = 1.5                # s one swing takes (measured 1.5-1.6 at "swing"); with the queue reading, at most one swing
SWING_LEAD_S = 0.5           # is queued ahead: the next is sent only when the ones sent end within this
FRESH_S = 0.5                # s a waving person seen counts as waving now
NEW_WAVE_S = 5.0             # s without any waving after which a wave is greeted anew (a new greeting line)
JOKE_AFTER_S = 10.0          # s of waving before the first joke ...
JOKE_EVERY_S = 12.0          # ... and between jokes
WAIST_MIN_DEG = 10.0         # deg; a person nearer the front than this: only the head turns
WAIST_MAX_DEG = 30.0         # deg from the front the waist turns to a waving person at most, the head covers the rest
                             # (owner: it faces the front, a little toward them is fine); estimate
WAIST_FOLLOW_DEG = 20.0      # deg the waving person may move off the waist's front before it turns to them again ...
FOLLOW_EVERY_S = 3.0         # ... at most this often (between swings)
WAIST_PARTS = (1.0, 0.75, 0.5, 0.25)   # a blocked waist turn is tried again this much of the way (beside a wall)
HEAD_MIN_DEG = 8.0           # deg the person may move off the head's direction before the head follows
DOWN_SPEED = "normal"        # motion.JOINT_SPEED of the way down (owner: 2x the first "slow")
SWING_SPEED = "swing"        # motion.JOINT_SPEED of the swings, 60 deg/s at 4x the usual acceleration (owner: faster;
                             # wave.SWING_SPEED of an asked wave is "quick")
FREE_EVERY_S = 1.0           # s between checks that nothing else runs (it asks the AGV)
REFUSED_S = 30.0             # s before trying again after the arm was refused (off, busy, holding something) and
                             # between tries to bring a blocked waist back to the front
HEAD_TIMEOUT_S = 5.0         # s a head move may take; the body API now and then never answers a moveto, and the call
                             # holds the body lock all that time (the waist turn waited 30 s behind it)
IDLE_WAVE_EVERY_S = 15.0     # s between two waves while nothing is asked of Lumi on the charger (owner: now and then for
                             # the passers-by; estimate), from the end of the last one (or anyone's last wave)
IDLE_SWINGS = 3              # swings of such a wave (also keep alive and a wave at someone new)
KEEP_QUIET_S = 30.0          # s without a wave before keep alive (owner, 2026-11-16): on the way Lumi stops and waves;
                             # at home (Welcome) it waves every IDLE_WAVE_EVERY_S until someone comes or waves
GREET_SWINGS = 3             # swings at least for someone who starts waving, more while they go on (owner: one too few)
IDLE_CLEAR_M = 0.8           # m; nobody this near in either camera when such a wave starts (one coming closer while the
                             # arm goes up still stops it: _too_close); owner 2026-11-16 (was 1.0): the hand is already
                             # up in wave_start before drives and waves, so it does not sweep into someone in front
RAISE_WAIT_S = 10.0          # s a drive waits for someone right by the arm to step back before the hand goes up
                             # (else it drives in look); estimate
IDLE_RETRY_S = 1.0          # s between two asks whether Lumi is idle (it asks the base whether it charges)
CLOSE_FRESH_S = 1.5          # s a camera service detection counts for the too-close check
LINK_RETRY_S = 3.0           # s before trying again when the arm controller or the base did not answer (the controller
                             # now and then closes the connection, the base refuses while it loads a map): not a stop

_seen = {c: {"t": 0.0, "wavers": []} for c in CAMERAS}   # wavers: [(bearing deg from the waist's front, + left;
                                                          # distance m)] in that camera, nearest first
_met = reid.People()                 # people greeted (introduced to), forgotten GONE_S after they leave the view
_passed = reid.People()              # people a drive already stopped and waved at (each once), forgotten the same way
_drive_wave = threading.Lock()       # held while a drive's swings run (passer_wave, keep_alive_wave): no new drive then
_met_lock = threading.Lock()
_busy = threading.Event()            # the arm is up or moving for a greeting
_speaking = threading.Lock()
_on = _free = _off = None            # set by start()
_rest = lambda: 0.0                  # waist angle (deg from the front) the waist goes back to; set by start()
_rest_arm = arm_route.rest_pose      # the pose the arm goes down to; set by start()
_idle = lambda: False                # nothing asked of Lumi for a while (on the charger): a wave now and then; set by start()
_talk = lambda: True                 # the greeting may speak (Greeter or Patrol on); only waves when not; set by start()
_welcome = lambda: False             # Welcome is on: the hand goes up to wave_start and stays; set by start()
_home = lambda: False                # Welcome, on the charger, nobody talked to: waves at someone new; set by start()
_drive_on = None                     # the hand rides up on drives only with this on (Wave; Welcome alone: down);
                                     # _on when not set by start()


def log(*a):
    print(time.strftime("%H:%M:%S"), "wave greeting:", *a, flush=True)


def busy():
    return _busy.is_set()


# ---------- seeing ----------
def _head_yaw(cam="head"):
    """Yaw (deg) of a camera from the waist's front at its newest frame: the head's yaw for the head camera, 0 for the
    torso camera (it looks along the waist)."""
    try:
        return float(json.loads(camview.det_path(cam).read_text()).get("head_yaw") or 0.0)
    except (FileNotFoundError, ValueError):
        return 0.0


def _dist(depth, at):
    """Median depth (m) around a pixel, None without depth there."""
    if depth is None:
        return None
    x, y = int(at[0]), int(at[1])
    patch = depth[max(0, y - 6):y + 7, max(0, x - 6):x + 7]
    v = patch[patch > 0]
    return float(np.median(v)) / 1000 if v.size >= 5 else None


def _watch(cam):
    """Every frame of camera `cam` while the switch is on: who waves, where (_seen[cam])."""
    watcher, last, intr = waving.Watcher(), 0.0, None
    while True:
        if not _on():
            watcher, intr = waving.Watcher(), None
            time.sleep(0.5)
            continue
        camview.want(cam)
        try:
            m = camview.raw_path(cam).stat().st_mtime
        except FileNotFoundError:
            time.sleep(0.2)
            continue
        if m == last:
            time.sleep(0.01)
            continue
        last = m
        img = cv2.imread(str(camview.raw_path(cam)))
        intr = intr or camview.intrinsics(cam)
        if img is None or intr is None:
            continue
        depth, yaw = camview.depth(cam), _head_yaw(cam)
        gray = cv2.cvtColor(cv2.resize(img, None, fx=waving.SCALE, fy=waving.SCALE), cv2.COLOR_BGR2GRAY)
        wavers, people, now = [], [], time.time()
        for p, is_waving in watcher.update(m, gray, pose.detect(img)):
            ls, rs = pose.seen(p["kp"], "left_shoulder"), pose.seen(p["kp"], "right_shoulder")
            if not (ls and rs):
                continue
            at = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
            d = _dist(depth, at) or intr["fx"] * SHOULDER_M / max(1.0, math.hypot(ls[0] - rs[0], ls[1] - rs[1]))
            look = reid.look(img, p["box"])
            face = reid.face(img, p["box"]) if is_waving and d is not None and d <= reid.FACE_MAX_M else None
            with _met_lock:                          # someone greeted, still in view: stays known
                known = _known(look, face, now)
                if known:
                    known.seen(look, face, now)
            bearing = yaw - math.degrees(math.atan((at[0] - intr["cx"]) / intr["fx"]))
            if d is not None:
                people.append((bearing, d, look, None))
                with _met_lock:                      # someone already waved at, still in view: stays known
                    _passed.known = [k for k in _passed.known if now - k.last_seen < GONE_S]
                    known = _passed.recall(look, None, now)
                    if known:
                        known.seen(look, None, now)
            if is_waving and d is not None and GREET_MIN_M <= d <= GREET_M:
                wavers.append((bearing, d, look, face))
        _seen[cam].update(t=time.time(), wavers=sorted(wavers, key=lambda w: w[1]),
                          people=sorted(people, key=lambda w: w[1]))


def _known(look, face, now):
    """The greeted person this is (call with _met_lock held), None for someone new or gone longer than GONE_S."""
    _met.known = [k for k in _met.known if now - k.last_seen < GONE_S]
    return _met.recall(look, face, now)


def _greeting(w):
    """The lines to greet waver `w` with: an introduction for someone new (they are remembered), else a hello."""
    now = time.time()
    with _met_lock:
        if _known(w[2], w[3], now):
            return wave_lines.GREET
        _met.add(w[2], w[3], now)
    return wave_lines.INTRO


def _waver():
    """(bearing, distance, look, face) of the nearest person waving now in either camera, None when nobody waves."""
    now = [w for s in _seen.values() if time.time() - s["t"] < FRESH_S for w in s["wavers"]]
    return min(now, key=lambda w: w[1], default=None)


def _too_close():
    """A person really close in either camera (the assistant's rule, lumi.too_close)."""
    from assistant.lumi import too_close
    for cam in ("head", "torso"):
        try:
            d = json.loads(camview.det_path(cam).read_text())
        except (FileNotFoundError, ValueError):
            continue
        if time.time() - d["time"] < CLOSE_FRESH_S and \
                too_close([p for p in d["people"] if p.get("distance_m") is not None], d["height"]):
            return True
    return False


def _someone_within(m):
    """A person within `m` metres in either camera's fresh detections."""
    for cam in ("head", "torso"):
        try:
            d = json.loads(camview.det_path(cam).read_text())
        except (FileNotFoundError, ValueError):
            continue
        if time.time() - d["time"] < CLOSE_FRESH_S and \
                any(p.get("distance_m") is not None and p["distance_m"] < m for p in d["people"]):
            return True
    return False


# ---------- moving and talking ----------
def _bg(fn, *args):
    threading.Thread(target=fn, args=args, daemon=True).start()


def _say(lines, lang):
    """One line of `lines` in language 0 (English) / 1 (Korean), in the background; skipped while Lumi speaks and
    when talk is not allowed (only Wave / Welcome on: Lumi only waves, owner 2026-11-16)."""
    if not _talk():
        return

    def run():
        if not _speaking.acquire(blocking=False):
            return
        try:
            from audio import mouth
            mouth.say(random.choice(lines)[lang])
        except Exception as e:
            log(f"say failed: {e!r}")
        finally:
            _speaking.release()
    _bg(run)


def _turn_head(yaw, pitch=None):
    """head.turn with HEAD_TIMEOUT_S; a move that times out is logged (the head finishes it anyway)."""
    try:
        lift, waist, _, now_pitch = head.status()
        yaw = max(-head.YAW_LIMIT, min(head.YAW_LIMIT, yaw))
        head.moveto([lift, waist, yaw, now_pitch if pitch is None else pitch], timeout=HEAD_TIMEOUT_S)
    except Exception as e:
        log(f"head move: {e!r}")


def _head_to(bearing):
    """The head to a bearing from the waist's front, in the background, unless it looks there already."""
    if abs(bearing - _head_yaw()) > HEAD_MIN_DEG:
        _bg(_turn_head, bearing)


def _up(route):
    """The way up (wave.plan) at the route speed, the last move at ARRIVE_SPEED; the arm stops when a person comes
    really close meanwhile (motion.MotionError)."""
    if not route:
        return
    done = threading.Event()

    def guard():
        while not done.wait(0.1):
            if _too_close():
                log("a person is too close - STOP arm")
                motion.stop()
                return
    threading.Thread(target=guard, daemon=True).start()
    t0 = time.time()
    try:
        motion.move_path([(j, arm_route.SPEED) for _, j in route[:-1]] + [(route[-1][1], wave.ARRIVE_SPEED)])
    finally:
        done.set()
    log(f"arm up after {time.time() - t0:.1f} s")


def _swing():
    """One swing, START -> SWING -> START, waited for."""
    p, t0 = motion.poses(), time.time()
    motion.move_path([(p[wave.SWING], SWING_SPEED), (p[wave.START], SWING_SPEED)], queued=True)
    _st["any_wave"] = time.time()        # keep alive counts from the last swing of any kind
    log(f"swing {time.time() - t0:.1f} s")


def _pending():
    """Moves the controller has still to run (its queue), 9 when it does not say."""
    r = arm.cmd("get_motion_state")
    return r.get("queue", 9) if "queue" in r else 9


def _swing_on(now):
    """Keep the swings going back to back: one more swing is queued while the running one has at most its last move
    left. Not waited for, so a STOP or a protective stop is looked for here (motion._wait does it for waited moves).
    False when the arm is not at the wave any more (someone moved it)."""
    if motion._stopped.is_set():
        raise motion.MotionError("stopped")
    d = arm.cmd("get_data")
    if d.get("protective_stop") or d.get("emergency_stop"):
        raise motion.MotionError("the controller stopped the arm (protective / emergency stop)")
    if _st["swing_end"] - now > SWING_LEAD_S:    # the swings sent still run longer than that: never pile up
        return True
    n = _pending()
    if n > 1:
        return True
    if n == 0 and arm_route.where() not in (wave.START, wave.SWING):
        return False
    p = motion.poses()
    motion.move_path([(p[wave.SWING], SWING_SPEED), (p[wave.START], SWING_SPEED)], wait=False, queued=True)
    _st["swing_end"] = max(now, _st["swing_end"]) + SWING_S
    _st["owed"] = max(0, _st["owed"] - 1)
    return True


def _settle():
    """Let the queued swings end at START before the waist turns or the arm goes down."""
    start = motion.poses()[wave.START]
    motion._wait(lambda d: max(abs(a - b) for a, b in zip(d["joint_actual_position"],
                                                          motion.nearest(start, d["joint_actual_position"]))) <
                 motion.AT_JOINT_DEG, 10.0, queued=True)


def _face(bearing):
    """Waist turned to the person (they face each other), the head staying on them; only the head when they are
    nearly in front. The waist stays within WAIST_MAX_DEG of the front; a turn whose sweep is not clear is tried part
    of the way (WAIST_PARTS); the head covers the rest."""
    from tasks import fetch
    fetch._stop.clear()                  # no task runs: an old stop must not end this turn
    tried = set()
    for part in WAIST_PARTS:
        if abs(bearing * part) < WAIST_MIN_DEG:
            break
        want = round(max(-WAIST_MAX_DEG, min(WAIST_MAX_DEG, fetch._waist_turn() + bearing * part)), 1)
        if want in tried:                # cut to WAIST_MAX_DEG like a longer part before it
            continue
        tried.add(want)
        if fetch._waist_to(want, in_place=True, look=bearing):
            return
    _head_to(bearing)


def _greet(w, lang):
    """Head to them, a greeting, the arm up, GREET_SWINGS swings, the waist to them. False when the arm is refused."""
    bearing = w[0]
    try:
        route, _ = wave.plan()
    except Exception as e:               # refused (arm off, busy, holding) or the controller did not answer
        log(f"not waving: {e.args[0] if isinstance(e, wave.WaveError) else repr(e)}")
        return False
    log(f"someone waves at {bearing:+.0f} deg: arm up")
    _busy.set()
    _head_to(bearing)
    _say(_greeting(w), lang)
    _up(route)
    for _ in range(GREET_SWINGS):        # even if they stopped while the arm went up
        _swing()
    w = _waver()
    _face(w[0] if w else bearing)
    return True


def _idle_wave():
    """Nobody asks anything (on the charger, _idle): the hand goes up and stays up (owner, 2026-11-04: "held"), the
    waist where it is, no words; it swings IDLE_SWINGS times now and then (step) so passers-by see Lumi is on. A drive
    or an order for the arm takes it down (lower, a task), the switch turned off too. False when the arm is refused."""
    at = arm_route.where()
    if _someone_within(IDLE_CLEAR_M) or at not in (_rest_arm(), wave.START, wave.SWING):
        return True                          # someone near the arm, or the arm still on its way to rest: next time
    route = None                             # the hand already up (a wave's way down did not run): it swings from there
    if at == _rest_arm():
        try:
            route, _ = wave.plan()
        except Exception as e:
            log(f"no idle wave: {e.args[0] if isinstance(e, wave.WaveError) else repr(e)}")
            return False
    log("Welcome: the hand up to wave_start, held")
    _busy.set()
    try:
        if route:
            _up(route)
        _st.update(up=True, held=True, held_at=0.0)
    finally:
        _busy.clear()
    return True


def _held_swings(bearing, allowed):
    """The held hand: the head to `bearing` and IDLE_SWINGS swings while `allowed()` (_idle_swings ends them for a
    waver or a talk)."""
    _busy.set()
    _head_to(bearing)
    try:
        _idle_swings(allowed)
    finally:
        _busy.clear()


def _nearest_any(now=None):
    """Bearing of the nearest person either camera sees at any distance (also far beyond PASSER_M), else None."""
    now = time.time() if now is None else now
    seen = [p for cam in CAMERAS if now - _seen[cam]["t"] < CLOSE_FRESH_S for p in _seen[cam].get("people", [])]
    if seen:
        return min(seen, key=lambda p: p[1])[0]
    return _nearest(1e9)


def note_quiet_start(now=None):
    """A trip starts: keep alive counts KEEP_QUIET_S from here (not from a wave long ago)."""
    _st["any_wave"] = time.time() if now is None else now


def keep_alive_due(now=None):
    """On the way (lumi.Patrol, Wave on): KEEP_QUIET_S without a swing of any kind, nobody by the arm."""
    now = time.time() if now is None else now
    return now - _st["any_wave"] >= KEEP_QUIET_S and not _someone_within(IDLE_CLEAR_M)


def answer_waver(speed=None):
    """A drive in look stopped for someone waving (Greeter / Patrol with Wave, lumi.Patrol): the hand up (wave.plan,
    refused while holding something), the head to them, swings while they wave (GREET_SWINGS at least), the head ahead
    and the hand down to the drive pose at `speed`. A stop or a failure switches the waving off and raises. True when
    it swung."""
    with _drive_wave:
        w = _waver()
        if _on is None or not _on() or not w or _someone_within(IDLE_CLEAR_M):
            return False
        from tasks import fetch
        raised = arm_route.where() not in (wave.START, wave.SWING)
        _busy.set()
        try:
            if raised:
                try:
                    route, _ = wave.plan()
                except wave.WaveError as e:
                    log(f"no answer to a wave: {e.args[0]}")
                    return False
                _up(route)
            _head_to(w[0])
            n = 0
            while n < GREET_SWINGS or (_waver() and n < 4 * GREET_SWINGS):
                if _someone_within(IDLE_CLEAR_M):
                    break
                _swing()
                n += 1
        except Exception as e:
            _stopped(e)
            raise
        finally:
            _busy.clear()
            _turn_head(0.0)
        if raised:
            _down(0.0, fetch.drive_arm(), speed)
        return True


def keep_alive_wave():
    """See _keep_alive_wave; the next drive waits for it (_drive_wave)."""
    with _drive_wave:
        return _keep_alive_wave()


def _keep_alive_wave():
    """A drive with the hand up stopped for keep alive (the base stopped): the head toward the nearest person at any
    distance, else ahead, IDLE_SWINGS swings, the head ahead again. A stop or a failure switches the greeting off and
    raises. True when it swung."""
    if _on is None or not _on() or _someone_within(IDLE_CLEAR_M) or arm_route.where() not in (wave.START, wave.SWING):
        return False
    b = _nearest_any()
    b = 0.0 if b is None else b
    log(f"keep alive: nobody waved at for {KEEP_QUIET_S:.0f} s, a wave toward {b:+.0f} deg")
    _busy.set()
    _head_to(b)
    try:
        for _ in range(IDLE_SWINGS):
            if _someone_within(IDLE_CLEAR_M):
                break
            _swing()
    except Exception as e:
        _stopped(e)
        raise
    finally:
        _busy.clear()
        _turn_head(0.0)
    return True


def _idle_swings(allowed=None):
    """IDLE_SWINGS swings of the held hand; someone waving back (greeted as always, step) or talking to Lumi (the hand
    stays up, still) ends them."""
    for _ in range(IDLE_SWINGS):
        if _waver():
            log("idle wave: someone waves back")
            _st["last_wave"] = 0.0
            return
        if not (_free() and (allowed or _idle)()):
            log("idle wave: someone talks to me, the hand stays up")
            return
        if _someone_within(IDLE_CLEAR_M) or not _on():
            log("idle wave: someone by the arm, or switched off: no more swings")
            return
        _swing()


def raise_for_drive():
    """With the switch on, the empty arm drives with the hand up at START (owner, 2026-11-07): the way up (wave.plan)
    unless it is up already. A stop or a failure switches the greeting off (_stopped) and raises. True when it is up.
    Only with Wave on (_drive_on): Welcome alone drives with the hand down (owner, 2026-11-16)."""
    on = _drive_on or _on
    if on is None or not on():
        return False
    if arm_route.where() in arm_route.WAVE_POSES:
        return True
    end = time.time() + RAISE_WAIT_S             # someone right by the arm (the one who sent Lumi): they step back
    while _too_close() and time.time() < end:    # first, else the guard stops the way up and the greeting is off
        time.sleep(0.2)
    if _too_close():
        log("a drive: someone right by me, the hand stays down")
        return False
    route, _ = wave.plan()
    log("a drive: the hand up")
    _busy.set()
    try:
        _up(route)
    except Exception as e:
        _stopped(e)
        raise
    finally:
        _busy.clear()
    return True


def _nearest(m):
    """Bearing (deg from the waist's front, + left) of the nearest person within `m` metres in either camera's fresh
    detections, None when there is none."""
    near = []
    for cam in ("head", "torso"):
        try:
            d = json.loads(camview.det_path(cam).read_text())
        except (FileNotFoundError, ValueError):
            continue
        if time.time() - d["time"] < CLOSE_FRESH_S:
            near += [(p["distance_m"], p["angle_deg"]) for p in d["people"]
                     if p.get("distance_m") is not None and p["distance_m"] < m]
    return min(near)[1] if near else None


def _in_range(now):
    """Everyone either camera sees now PASSER_MIN_M..PASSER_M away: [(bearing, distance, look, face)], nearest first."""
    out = []
    for cam in CAMERAS:
        s = _seen[cam]
        if now - s["t"] < CLOSE_FRESH_S:
            out += [p for p in s.get("people", []) if PASSER_MIN_M <= p[1] <= PASSER_M]
    return sorted(out, key=lambda p: p[1])


def _new_passer(now=None):
    """The nearest person in range not waved at yet (each once until they were out of view GONE_S), else None."""
    now = time.time() if now is None else now
    with _met_lock:
        _passed.known = [k for k in _passed.known if now - k.last_seen < GONE_S]
        return next((p for p in _in_range(now) if _passed.recall(p[2], p[3], now) is None), None)


def _mark_passed(now=None):
    """Everyone in range now has been waved at (they saw the wave): no stop for them again while in view."""
    now = time.time() if now is None else now
    with _met_lock:
        for p in _in_range(now):
            known = _passed.recall(p[2], p[3], now)
            if known:
                known.seen(p[2], p[3], now)
            else:
                _passed.add(p[2], p[3], now)


def drive_wave_busy():
    """A drive's swings run (lumi.Patrol waits with the next drive until they end)."""
    return _drive_wave.locked()


def passer_due():
    """Someone new passing to wave at (_new_passer), nobody within IDLE_CLEAR_M (lumi.Patrol stops for it)."""
    return _new_passer() is not None and not _someone_within(IDLE_CLEAR_M)


def passer_wave():
    """See _passer_wave; the next drive waits for it (_drive_wave)."""
    with _drive_wave:
        return _passer_wave()


def _passer_wave():
    """A drive with the hand up (lumi.Patrol, the base stopped): the head to the one waving, else the nearest person
    within PASSER_M, and IDLE_SWINGS swings, waited for, then the head ahead again; none when nobody is within PASSER_M
    or someone is within IDLE_CLEAR_M of the arm. A stop or a failure switches the greeting off (_stopped) and
    raises. True when it swung."""
    w = _waver()
    p = None if w else _new_passer()
    bearing = w[0] if w else p[0] if p else None
    if _on is None or not _on() or bearing is None or _someone_within(IDLE_CLEAR_M) or \
            arm_route.where() not in (wave.START, wave.SWING):
        return False
    log(f"{'someone waves' if w else 'people passing'} at {bearing:+.0f} deg: a wave")
    _busy.set()
    _head_to(bearing)
    try:
        for _ in range(IDLE_SWINGS):
            if _someone_within(IDLE_CLEAR_M):
                break
            _swing()
        _mark_passed()                   # each person once
    except Exception as e:
        _stopped(e)
        raise
    finally:
        _busy.clear()
        _turn_head(0.0)                  # the drive goes on looking ahead
    return True


def _rest_waist():
    """The waist back to _rest() with the hand kept up (its sweep checked, fetch._waist_to); the swings end first."""
    from tasks import fetch
    _busy.set()
    try:
        if arm_route.where() is None:
            _settle()
        fetch._stop.clear()
        _st["waist_out"] = not fetch._waist_to(_rest(), in_place=True)
    finally:
        _busy.clear()


def _down(waist=None, arm_to=None, speed=None):
    """Waist to its rest (`waist` deg from the front, else _rest()) first, the way it came with the hand up (in `look`
    the arm sticks out further and the same turn back can be blocked), then the arm slowly down (_rest_arm) and the
    head to rest."""
    from tasks import fetch
    _busy.set()
    try:
        if arm_route.where() is None:
            _settle()                    # mid-swing: the queued swings end first
        fetch._stop.clear()
        _st["waist_out"] = not fetch._waist_to(_rest() if waist is None else waist, in_place=True)
        at = arm_route.where()
        if at in arm_route.WAVE_POSES:
            arm_route.move(arm_route.plan(arm_to or _rest_arm()), speed or DOWN_SPEED)
        _turn_head(0.0, head.HEAD_REST_PITCH)
        log("arm down" if at in arm_route.WAVE_POSES or at in (_rest_arm(), arm_to) else f"arm left where it is ({at or 'between poses'})")
    finally:
        _busy.clear()


_st = {"up": False, "last_wave": 0.0, "lang": 0, "next_joke": 0.0, "free": False, "free_at": 0.0, "refused_until": 0.0,
       "waist_out": False, "follow_at": 0.0, "swing_at": 0.0,
       "swing_end": 0.0, "idle_at": 0.0, "held": False, "held_at": 0.0, "owed": 0, "people_wave": 0.0, "any_wave": 0.0,
       "raise_at": 0.0}   # held: the hand kept up on the charger
                                                                          # (_idle_wave)                     # swing_end: when the swings sent so far should be done                    # waist_out: the way back to the front was blocked, tried again later


def step(now):
    """One look at what to do now (_run calls it every 50 ms)."""
    st = _st
    if not _on():
        if st["up"]:
            _down()
        st["up"] = st["held"] = False
        return
    if now - st["free_at"] > FREE_EVERY_S:
        st["free"], st["free_at"] = _free(), now
    if not st["free"]:                   # the assistant or a task has the robot: it takes the arm from here
        st["up"] = st["held"] = False
        _busy.clear()
        return
    w = _waver()
    new = bool(w) and now - st["last_wave"] > NEW_WAVE_S
    if new:
        st["lang"], st["next_joke"] = random.randrange(2), now + JOKE_AFTER_S
        st["owed"] = GREET_SWINGS        # the hand up already: this many swings even if they stop sooner
    if w:
        st["last_wave"] = now
        st["held"] = False               # facing them now: after HOLD_S the waist goes back to its rest (held again)
    if not st["up"]:
        if w and now > st["refused_until"]:
            st["up"] = _greet(w, st["lang"])
            st["owed"] = 0               # _greet swung them
            if not st["up"]:
                st["refused_until"] = now + REFUSED_S
        elif not w and now > st["refused_until"] and now - st["raise_at"] >= IDLE_RETRY_S and _welcome():
            st["raise_at"] = now                 # Welcome: the hand up at once, whatever the pose (owner, 2026-11-16)
            if not _idle_wave():
                st["refused_until"] = now + REFUSED_S
        elif not w and st["waist_out"] and now > st["refused_until"]:
            from tasks import fetch
            fetch._stop.clear()
            st["waist_out"] = not fetch._waist_to(_rest(), in_place=True)
            st["refused_until"] = now + REFUSED_S
    elif w or st["owed"] > 0:            # they stopped: the swings owed still run
        if w and new:
            _say(_greeting(w), st["lang"])
        elif w and now > st["next_joke"]:
            _say(wave_lines.LONG, st["lang"])
            st["next_joke"] = now + JOKE_EVERY_S
        if w and abs(w[0]) > WAIST_FOLLOW_DEG and now > st["follow_at"]:
            st["follow_at"] = now + FOLLOW_EVERY_S
            _settle()
            _face(w[0])                  # they moved: the waist turns to them again, between two swings
        elif w:
            _head_to(w[0])
        if now > st["swing_at"]:
            st["swing_at"] = now + SWING_POLL_S
            if not _swing_on(now):
                st["up"] = False         # someone moved the arm: the next wave starts from where it is
    elif st["held"]:                     # held up (Welcome): someone new at home, keep alive on the charger
        if now - st["held_at"] >= IDLE_RETRY_S:
            st["held_at"] = now
            if arm_route.where() not in (wave.START, wave.SWING):
                st["up"] = st["held"] = False    # an order moved the arm meanwhile (Welcome raises it again)
            elif _home() and not _someone_within(IDLE_CLEAR_M) and (p := _new_passer()) is not None:
                log(f"Welcome: someone new at {p[0]:+.0f} deg, {p[1]:.1f} m: a wave")
                _held_swings(p[0], _home)
                _mark_passed()
                st["people_wave"] = st["idle_at"] = now
            elif _idle() and now - max(st["last_wave"], st["people_wave"]) >= KEEP_QUIET_S and \
                    now - st["idle_at"] >= IDLE_WAVE_EVERY_S and not _someone_within(IDLE_CLEAR_M):
                b = _nearest_any()
                log(f"keep alive at home: a wave toward {0.0 if b is None else b:+.0f} deg")
                _held_swings(0.0 if b is None else b, _idle)
                st["idle_at"] = now
    elif now - st["last_wave"] > HOLD_S:           # nobody waves: the hand stays up (owner), the waist to its rest
        _rest_waist()
        st["held"], st["idle_at"], st["held_at"] = True, now - IDLE_WAVE_EVERY_S, 0.0   # swings due at once


def _stopped(e):
    """A stop or a failure of the arm: switched off, it never goes on by itself."""
    log(f"stopped ({e!r}) - switched off")
    _busy.clear()
    _st["up"] = False
    _off()
    _say([("I stopped my arm.", "팔을 멈췄어요.")], _st["lang"])


def _run():
    try:                                 # the hand left up (an API restart mid-wave): held after HOLD_S
        if arm_route.where() in (wave.START, wave.SWING):
            _st.update(up=True, last_wave=time.time())
    except Exception as e:
        log(f"arm not read at start: {e!r}")
    while True:
        time.sleep(0.05)
        _tick(time.time())


def _tick(now):
    """One step; a stop or a failure of the arm switches the greeting off, no answer from a device does not."""
    try:
        step(now)
    except OSError as e:                 # ConnectionError too: the switch stays on
        log(f"no answer ({e!r}), trying again in {LINK_RETRY_S:.0f} s")
        _busy.clear()
        time.sleep(LINK_RETRY_S)
    except Exception as e:
        _stopped(e)


def up():
    """The hand is up for a greeting (or was, when someone else took the robot meanwhile)."""
    return _st["up"]


def _quiet(wait_s):
    """The way up and the swings sent without waiting end first (at most `wait_s` for the way up)."""
    end = time.time() + wait_s
    while _busy.is_set() and time.time() < end:
        time.sleep(0.05)
    if _st["swing_end"] > time.time() - SWING_S:
        _settle()
        _st["swing_end"] = 0.0


def front_hand_up(wait_s=10.0):
    """Before a drive with the switch on and the hand up (lumi.waist_home): the swings end and the waist turns to the
    front with the hand kept up, as _down turns it (owner, 2026-11-07: not down and up again). True when it did."""
    if _on is None or not _on():
        return False
    _quiet(wait_s)
    if arm_route.where() not in arm_route.WAVE_POSES:
        return False
    from tasks import fetch
    fetch._stop.clear()
    return fetch._waist_to(0.0, in_place=True)


def lower(wait_s=10.0, speed=None):
    """A drive or a turn takes the robot (lumi.waist_home): the way up and the queued swings end, then a hand left in
    a wave pose comes down to look, the waist to the front. Never driven with the hand up. Nothing when the greeting
    does not run in this process (start() not called)."""
    if _on is None:
        return
    _quiet(wait_s)
    _st["up"] = arm_route.where() in arm_route.WAVE_POSES
    if _st["up"]:
        from tasks import fetch
        _down(0.0, fetch.drive_arm(), speed)   # a drive follows: the waist to the front, the arm to its drive pose
    _st["up"] = _st["held"] = False


def start(on, free, off, free_every=FREE_EVERY_S, rest=None, rest_arm=None, idle=None, talk=None, welcome=None,
          home=None, drive_on=None):
    """`on()`: the switch is on; `free()`: nothing else has the robot (asked every `free_every` s); `off()`: turn the
    switch off; `rest()`: the waist's angle when the hand is down (the front unless given); `rest_arm()`: the arm's
    pose then (arm_route.rest_pose unless given); `idle()`: nothing asked for a while, a wave every IDLE_WAVE_EVERY_S
    (never unless given); `talk()`: the greeting may speak (always unless given); `welcome()`: the hand up and held;
    `home()`: wave at someone new (both never unless given); `drive_on()`: the hand up on drives (`on` unless given)."""
    global _on, _free, _off, FREE_EVERY_S, _rest, _rest_arm, _idle, _talk, _welcome, _home
    global _drive_on
    _welcome, _home, _drive_on = welcome or _welcome, home or _home, drive_on or _drive_on
    _on, _free, _off, FREE_EVERY_S = on, free, off, free_every
    _rest, _rest_arm, _idle, _talk = rest or _rest, rest_arm or _rest_arm, idle or _idle, talk or _talk
    for cam in CAMERAS:
        threading.Thread(target=_watch, args=(cam,), daemon=True).start()
    threading.Thread(target=_run, daemon=True).start()
