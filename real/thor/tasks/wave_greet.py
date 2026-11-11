"""Wave back at people who wave at Lumi: the dashboard switch "Wave greeting". Greeter / Patrol are not needed; while
either runs the assistant owns the robot and this waits. Runs in the API process (api/server.py starts it).

Someone waving within GREET_M of either camera (vision/waving.py; the head camera may look elsewhere): the head turns to them and the arm goes up at
once (manipulation/wave.py checks and plans the way, look -> wave_out -> wave_start, at the route speed), Lumi says a
greeting (tasks/wave_lines.py), swings once even when they stopped meanwhile, then turns the waist to face them
(fetch._waist_to, its sweep checked; the head stays on them). It swings while they wave, stops when they stop and
keeps the hand up; waving again swings again. A long wave gets a joke now and then. Nobody waving for HOLD_S: the arm
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
from vision import camview, pose, waving

CAMERAS = ("head", "torso")   # both watched: the head may look away while the person is in the torso camera's view
GREET_M = 3.0                # m; people waving further away are not answered
HOLD_S = 60.0                # s the hand stays up after the last wave seen, then down to look
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
CLOSE_FRESH_S = 1.5          # s a camera service detection counts for the too-close check

_seen = {c: {"t": 0.0, "wavers": []} for c in CAMERAS}   # wavers: [(bearing deg from the waist's front, + left;
                                                          # distance m)] in that camera, nearest first
_busy = threading.Event()            # the arm is up or moving for a greeting
_speaking = threading.Lock()
_on = _free = _off = None            # set by start()


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
        wavers = []
        for p, is_waving in watcher.update(m, gray, pose.detect(img)):
            ls, rs = pose.seen(p["kp"], "left_shoulder"), pose.seen(p["kp"], "right_shoulder")
            if not (is_waving and ls and rs):
                continue
            at = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
            d = _dist(depth, at)
            if d is not None and d <= GREET_M:
                wavers.append((yaw - math.degrees(math.atan((at[0] - intr["cx"]) / intr["fx"])), d))
        _seen[cam].update(t=time.time(), wavers=sorted(wavers, key=lambda w: w[1]))


def _waver():
    """(bearing, distance) of the nearest person waving now in either camera, None when nobody waves."""
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
    """One swing, START -> SWING -> START, back to back."""
    p, t0 = motion.poses(), time.time()
    motion.move_path([(p[wave.SWING], SWING_SPEED), (p[wave.START], SWING_SPEED)], queued=True)
    log(f"swing {time.time() - t0:.1f} s")


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


def _greet(bearing, lang):
    """Head to them, a greeting, the arm up, one swing, the waist to them. False when the arm is refused."""
    try:
        route, _ = wave.plan()
    except Exception as e:               # refused (arm off, busy, holding) or the controller did not answer
        log(f"not waving: {e.args[0] if isinstance(e, wave.WaveError) else repr(e)}")
        return False
    log(f"someone waves at {bearing:+.0f} deg: arm up")
    _busy.set()
    _head_to(bearing)
    _say(wave_lines.GREET, lang)
    _up(route)
    _swing()                             # once, even if they stopped while the arm went up
    w = _waver()
    _face(w[0] if w else bearing)
    return True


def _down():
    """Waist to the front first, the way it came with the hand up (in `look` the arm sticks out further and the same
    turn back can be blocked), then the arm slowly down to look and the head to rest."""
    from tasks import fetch
    _busy.set()
    try:
        fetch._stop.clear()
        _st["waist_out"] = not fetch._waist_to(0.0, in_place=True)
        if arm_route.where() in arm_route.WAVE_POSES:
            arm_route.move(arm_route.plan(arm_route.HOME), DOWN_SPEED)
        _turn_head(0.0, head.HEAD_REST_PITCH)
        log("arm down")
    finally:
        _busy.clear()


_st = {"up": False, "last_wave": 0.0, "lang": 0, "next_joke": 0.0, "free": False, "free_at": 0.0, "refused_until": 0.0,
       "waist_out": False, "follow_at": 0.0}                    # waist_out: the way back to the front was blocked, tried again later


def step(now):
    """One look at what to do now (_run calls it every 50 ms)."""
    st = _st
    if not _on():
        if st["up"]:
            _down()
        st["up"] = False
        return
    if now - st["free_at"] > FREE_EVERY_S:
        st["free"], st["free_at"] = _free(), now
    if not st["free"]:                   # the assistant or a task has the robot: it takes the arm from here
        st["up"] = False
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
            st["up"] = _greet(w[0], st["lang"])
            if not st["up"]:
                st["refused_until"] = now + REFUSED_S
        elif not w and st["waist_out"] and now > st["refused_until"]:
            from tasks import fetch
            fetch._stop.clear()
            st["waist_out"] = not fetch._waist_to(0.0, in_place=True)
            st["refused_until"] = now + REFUSED_S
    elif w:
        if arm_route.where() not in (wave.START, wave.SWING):
            st["up"] = False             # someone moved the arm: the next wave starts from where it is
            return
        if new:
            _say(wave_lines.GREET, st["lang"])
        elif now > st["next_joke"]:
            _say(wave_lines.LONG, st["lang"])
            st["next_joke"] = now + JOKE_EVERY_S
        if abs(w[0]) > WAIST_FOLLOW_DEG and now > st["follow_at"]:
            st["follow_at"] = now + FOLLOW_EVERY_S
            _face(w[0])                  # they moved: the waist turns to them again, between two swings
        else:
            _head_to(w[0])
        _swing()
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


def start(on, free, off):
    """`on()`: the switch is on; `free()`: nothing else has the robot; `off()`: turn the switch off."""
    global _on, _free, _off
    _on, _free, _off = on, free, off
    for cam in CAMERAS:
        threading.Thread(target=_watch, args=(cam,), daemon=True).start()
    threading.Thread(target=_run, daemon=True).start()
