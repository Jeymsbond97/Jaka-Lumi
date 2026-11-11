"""Wave back at people who wave at Lumi: the dashboard switch "Wave greeting", with or without Greeter / Patrol. It
runs in the process that owns the robot: the API's (api/server.py) while the assistant is off, the assistant's
(assistant/lumi.py) while it runs. There it waits while a drive, task, skill or conversation has the robot; a drive
or turn brings a raised hand down first (lower()).

Someone waving within GREET_M of either camera (vision/waving.py; the head camera may look elsewhere): the head turns to them and the arm goes up at
once (manipulation/wave.py checks and plans the way, look -> wave_out -> wave_start, at the route speed), Lumi says a
greeting (tasks/wave_lines.py; it introduces itself once to a person, until they leave the cameras' view: vision/reid.py
face, else clothes), swings once even when they stopped meanwhile, then turns the waist to face them (fetch._waist_to,
its sweep checked; the head stays on them). It swings back to back while they wave (one swing always queued behind
the running one, no stop between), stops when they stop and keeps the hand up; waving again swings again. A long wave gets a joke now and then. Nobody waving for HOLD_S: the arm
goes down slowly to look, the waist to the front, the head to rest.

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
GREET_M = 3.0                # m; people waving further away are not answered
HOLD_S = 40.0                # s the hand stays up after the last wave seen, then down to look (owner: 60 too long)
GONE_S = 10.0                # s a greeted person may be out of both cameras' view and still be known (no new intro)
SWING_POLL_S = 0.2           # s between looks at the controller's queue while swinging
SWING_S = 1.5                # s one swing takes (measured 1.5-1.6 at "swing"); with the queue reading, at most one swing
SWING_LEAD_S = 0.5           # is queued ahead: the next is sent only when the ones sent end within this
FRESH_S = 0.5                # s a waving person seen counts as waving now
NEW_WAVE_S = 5.0             # s without any waving after which a wave is greeted anew (a new greeting line)
JOKE_AFTER_S = 10.0          # s of waving before the first joke ...
JOKE_EVERY_S = 12.0          # ... and between jokes
WAIST_MIN_DEG = 10.0         # deg; a person nearer the front than this: only the head turns
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
IDLE_SWINGS = 3              # swings of such a wave
IDLE_CLEAR_M = 1.0           # m; nobody this near in either camera when such a wave starts (one coming closer while the
                             # arm goes up still stops it: _too_close); estimate
RAISE_WAIT_S = 10.0          # s a drive waits for someone right by the arm to step back before the hand goes up
                             # (else it drives in look); estimate
IDLE_RETRY_S = 1.0          # s between two asks whether Lumi is idle (it asks the base whether it charges)
CLOSE_FRESH_S = 1.5          # s a camera service detection counts for the too-close check

_seen = {c: {"t": 0.0, "wavers": []} for c in CAMERAS}   # wavers: [(bearing deg from the waist's front, + left;
                                                          # distance m)] in that camera, nearest first
_met = reid.People()                 # people greeted (introduced to), forgotten GONE_S after they leave the view
_met_lock = threading.Lock()
_busy = threading.Event()            # the arm is up or moving for a greeting
_speaking = threading.Lock()
_on = _free = _off = None            # set by start()
_rest = lambda: 0.0                  # waist angle (deg from the front) the waist goes back to; set by start()
_rest_arm = arm_route.rest_pose      # the pose the arm goes down to; set by start()
_idle = lambda: False                # nothing asked of Lumi for a while (on the charger): a wave now and then; set by start()


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
        wavers, now = [], time.time()
        for p, is_waving in watcher.update(m, gray, pose.detect(img)):
            ls, rs = pose.seen(p["kp"], "left_shoulder"), pose.seen(p["kp"], "right_shoulder")
            if not (ls and rs):
                continue
            at = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
            d = _dist(depth, at)
            look = reid.look(img, p["box"])
            face = reid.face(img, p["box"]) if is_waving and d is not None and d <= reid.FACE_MAX_M else None
            with _met_lock:                          # someone greeted, still in view: stays known
                known = _known(look, face, now)
                if known:
                    known.seen(look, face, now)
            if is_waving and d is not None and d <= GREET_M:
                wavers.append((yaw - math.degrees(math.atan((at[0] - intr["cx"]) / intr["fx"])), d, look, face))
        _seen[cam].update(t=time.time(), wavers=sorted(wavers, key=lambda w: w[1]))


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
    """One line of `lines` in language 0 (English) / 1 (Korean), in the background; skipped while Lumi speaks."""
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
    return True


def _settle():
    """Let the queued swings end at START before the waist turns or the arm goes down."""
    start = motion.poses()[wave.START]
    motion._wait(lambda d: max(abs(a - b) for a, b in zip(d["joint_actual_position"],
                                                          motion.nearest(start, d["joint_actual_position"]))) <
                 motion.AT_JOINT_DEG, 10.0, queued=True)


def _face(bearing):
    """Waist turned to the person (they face each other), the head staying on them; only the head when they are
    nearly in front. A turn whose sweep is not clear is tried part of the way (WAIST_PARTS); the head covers the
    rest."""
    from tasks import fetch
    fetch._stop.clear()                  # no task runs: an old stop must not end this turn
    for part in WAIST_PARTS:
        if abs(bearing * part) < WAIST_MIN_DEG:
            break
        if fetch._waist_to(fetch._waist_turn() + bearing * part, in_place=True, look=bearing):
            return
    _head_to(bearing)


def _greet(w, lang):
    """Head to them, a greeting, the arm up, one swing, the waist to them. False when the arm is refused."""
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
    _swing()                             # once, even if they stopped while the arm went up
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
    log("nothing asked for a while: the hand up for the passers-by")
    _busy.set()
    try:
        if route:
            _up(route)
        _st.update(up=True, held=True, held_at=0.0)
        _idle_swings()
    finally:
        _busy.clear()
    return True


def _idle_swings():
    """IDLE_SWINGS swings of the held hand; someone waving back (greeted as always, step) or talking to Lumi (the hand
    stays up, still) ends them."""
    for _ in range(IDLE_SWINGS):
        if _waver():
            log("idle wave: someone waves back")
            _st["last_wave"] = 0.0
            return
        if not (_free() and _idle()):
            log("idle wave: someone talks to me, the hand stays up")
            return
        _swing()


def raise_for_drive():
    """With the switch on, the empty arm drives with the hand up at START (owner, 2026-11-07): the way up (wave.plan)
    unless it is up already. A stop or a failure switches the greeting off (_stopped) and raises. True when it is up."""
    if _on is None or not _on():
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


def passer_wave():
    """A drive with the hand up (lumi.Patrol, the base stopped): the head to the one waving, else the nearest person
    within GREET_M, and IDLE_SWINGS swings, waited for, then the head ahead again; none when nobody is within GREET_M
    or someone is within IDLE_CLEAR_M of the arm. A stop or a failure switches the greeting off (_stopped) and
    raises. True when it swung."""
    w = _waver()
    bearing = w[0] if w else _nearest(GREET_M)
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
    except Exception as e:
        _stopped(e)
        raise
    finally:
        _busy.clear()
        _turn_head(0.0)                  # the drive goes on looking ahead
    return True


def _down(waist=None, arm_to=None):
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
            arm_route.move(arm_route.plan(arm_to or _rest_arm()), DOWN_SPEED)
        _turn_head(0.0, head.HEAD_REST_PITCH)
        log("arm down" if at in arm_route.WAVE_POSES or at in (_rest_arm(), arm_to) else f"arm left where it is ({at or 'between poses'})")
    finally:
        _busy.clear()


_st = {"up": False, "last_wave": 0.0, "lang": 0, "next_joke": 0.0, "free": False, "free_at": 0.0, "refused_until": 0.0,
       "waist_out": False, "follow_at": 0.0, "swing_at": 0.0,
       "swing_end": 0.0, "idle_at": 0.0, "held": False, "held_at": 0.0}   # held: the hand kept up on the charger
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
    if w:
        st["last_wave"] = now
    if not st["up"]:
        if w and now > st["refused_until"]:
            st["up"] = _greet(w, st["lang"])
            if not st["up"]:
                st["refused_until"] = now + REFUSED_S
        elif not w and now > st["refused_until"] and now - max(st["idle_at"], st["last_wave"]) > IDLE_WAVE_EVERY_S:
            if not _idle():
                st["idle_at"] = now - IDLE_WAVE_EVERY_S + IDLE_RETRY_S   # asked again in IDLE_RETRY_S, not every step
            elif not _idle_wave():
                st["refused_until"] = now + REFUSED_S
            else:
                st["idle_at"] = now              # its swings IDLE_WAVE_EVERY_S apart
        elif not w and st["waist_out"] and now > st["refused_until"]:
            from tasks import fetch
            fetch._stop.clear()
            st["waist_out"] = not fetch._waist_to(_rest(), in_place=True)
            st["refused_until"] = now + REFUSED_S
    elif w:
        if new:
            _say(_greeting(w), st["lang"])
        elif now > st["next_joke"]:
            _say(wave_lines.LONG, st["lang"])
            st["next_joke"] = now + JOKE_EVERY_S
        if abs(w[0]) > WAIST_FOLLOW_DEG and now > st["follow_at"]:
            st["follow_at"] = now + FOLLOW_EVERY_S
            _settle()
            _face(w[0])                  # they moved: the waist turns to them again, between two swings
        else:
            _head_to(w[0])
        if now > st["swing_at"]:
            st["swing_at"] = now + SWING_POLL_S
            if not _swing_on(now):
                st["up"] = False         # someone moved the arm: the next wave starts from where it is
    elif st["held"]:                     # held up on the charger: swings now and then while nobody talks to Lumi
        if now - st["idle_at"] > IDLE_WAVE_EVERY_S and now - st["held_at"] > IDLE_RETRY_S:
            st["held_at"] = now
            if _idle():
                if arm_route.where() in (wave.START, wave.SWING):
                    _busy.set()
                    try:
                        _idle_swings()
                    finally:
                        _busy.clear()
                    st["idle_at"] = now
                else:                    # an order moved the arm meanwhile: not held any more
                    st["up"] = st["held"] = False
    elif now - st["last_wave"] > HOLD_S:
        _down()
        st["up"] = False


def _stopped(e):
    """A stop or a failure of the arm: switched off, it never goes on by itself."""
    log(f"stopped ({e!r}) - switched off")
    _busy.clear()
    _st["up"] = False
    _off()
    _say([("I stopped my arm.", "팔을 멈췄어요.")], _st["lang"])


def _run():
    try:                                 # the hand left up (an API restart mid-wave): it comes down after HOLD_S
        if arm_route.where() in (wave.START, wave.SWING):
            _st.update(up=True, last_wave=time.time())
    except Exception as e:
        log(f"arm not read at start: {e!r}")
    while True:
        time.sleep(0.05)
        try:
            step(time.time())
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


def lower(wait_s=10.0):
    """A drive or a turn takes the robot (lumi.waist_home): the way up and the queued swings end, then a hand left in
    a wave pose comes down to look, the waist to the front. Never driven with the hand up. Nothing when the greeting
    does not run in this process (start() not called)."""
    if _on is None:
        return
    _quiet(wait_s)
    _st["up"] = arm_route.where() in arm_route.WAVE_POSES
    if _st["up"]:
        from tasks import fetch
        _down(0.0, fetch.drive_arm())    # a drive follows: the waist to the front, the arm to its drive pose
    _st["up"] = _st["held"] = False


def start(on, free, off, free_every=FREE_EVERY_S, rest=None, rest_arm=None, idle=None):
    """`on()`: the switch is on; `free()`: nothing else has the robot (asked every `free_every` s); `off()`: turn the
    switch off; `rest()`: the waist's angle when the hand is down (the front unless given); `rest_arm()`: the arm's
    pose then (arm_route.rest_pose unless given); `idle()`: nothing asked for a while, a wave every IDLE_WAVE_EVERY_S
    (never unless given)."""
    global _on, _free, _off, FREE_EVERY_S, _rest, _rest_arm, _idle
    _on, _free, _off, FREE_EVERY_S = on, free, off, free_every
    _rest, _rest_arm, _idle = rest or _rest, rest_arm or _rest_arm, idle or _idle
    for cam in CAMERAS:
        threading.Thread(target=_watch, args=(cam,), daemon=True).start()
    threading.Thread(target=_run, daemon=True).start()
