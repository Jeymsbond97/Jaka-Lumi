"""Follow a person with the base: "follow me" ... "stop" (lumi.py follow_me).

The person is a track of the assistant's Vision; `see()` gives (distance m, angle deg + left, age s) or None once the
track is gone, `people()` [(see, distance, angle, age)] of everyone in view: a track lost is swapped for a fresh one
where the person was last (re-lock). The head turns toward the person (only this task moves the body meanwhile:
head.owners), the base turns after it, so they stay in view when they walk to the side or behind. The base is driven with joy_control (one command lasts 0.5 s: a stuck loop stops the base by itself),
the arm in look and the waist at the front as for every fetch drive. Every command is checked first: where the base
and the arm would be BRAKE_S later must be clear (lidar + map, agv.clearance).

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

FOLLOW_GAP_M = 1.0          # m; keep this far from the person (camera distance); nearer: stand still
FOLLOW_MAX_MS = 0.15        # m/s; forward speed cap (estimate, tune live)
SPEED_GAIN = 0.8            # m/s per m the person is further than FOLLOW_GAP_M
ACCEL_MS2 = 0.4             # m/s^2; speeding up at most this fast (slowing down at once)
TURN_GAIN = 1.0             # rad/s per rad the person is off to the side
TURN_MAX_RS = 0.5           # rad/s; turn speed cap (joy_control takes up to 1.0)
TURN_DEAD_DEG = 5.0         # deg; the person this near the middle: no turn
TURN_ONLY_DEG = 30.0        # deg; the person further aside: turn on the spot first, no forward
STALE_S = 0.5               # s; a sighting older than this: stand still and wait for a new one
LOST_S = 2.0                # s without a sighting -> "I lost you" (lumi.Vision drops a track after its own LOST_S, 2 s)
BRAKE_S = 0.5               # s; the base and the arm must be clear where this command would take them by then
ARM_CLEAR_M = fetch.ARM_CLEAR_M                    # m; arm points kept this far from anything the lidar / map shows
BASE_CLEAR_M = fetch.BASE_HALF_M + fetch.CLEAR_M   # m; base centre kept this far, unless it gets further away
TICK_S = 0.1                # s between commands (joy_control wants > 2 Hz)
JOIN_S = 2.0                # s a new "follow me" waits for the old loop to end
RELOCK_DEG = 25.0           # deg; a fresh track this near the lost person's last angle is taken as them (estimate)
RELOCK_M = 0.8              # m; ... and this near their last distance (estimate)
HEAD_YAW_MAX = 90.0         # deg; the head turns toward the person up to this far (+ left; body API allows 180)
HEAD_PITCH = 10.0           # deg; head pitch while following, a little up toward a standing person (as "look at me")
HEAD_STEP_DEG = 5.0         # deg; a new head move only when the person is this far from where the head was sent
HEAD_VEL = 50               # speed ratio %; the head is at its full speed from 50 (audio/sing.py, measured)
HEAD_TIMEOUT_S = 5          # s; one head move (90 deg at ~40 deg/s takes ~2.5 s)

CHARGER = ("I'm on the charger, I can't follow you from here.", "충전 중이라 따라갈 수 없어요.")
ARM_OFF = ("My arm is switched off, so I can't drive safely. Please enable it.",
           "팔이 꺼져 있어서 안전하게 이동할 수 없어요. 팔을 켜 주세요.")
ARM_BUSY = ("A program is running on my arm, so I can't follow you.", "팔에서 프로그램이 실행 중이라 따라갈 수 없어요.")
LOST = ("I lost you, so I stopped. Stand in front of me and say follow me again.",
        "놓쳐서 멈췄어요. 제 앞에 서서 다시 따라오라고 말해 주세요.")
NO_ARM = ("My arm is not answering, so I can't drive safely.", "팔이 응답하지 않아서 안전하게 이동할 수 없어요.")

_stop = threading.Event()
_send = threading.Lock()    # a command and the stop never cross: after stop() no drive command goes out
_thread = None


STOP_WORDS = re.compile(r"\b(stop|halt|freeze|enough|wait|hold on|stay(?! with)|don'?t (move|follow)|no more|"
                        r"that'?s (enough|far enough|it))\b|멈춰|그만|정지|스톱|거기 ?(있어|서|계세요|있으세요)|기다려|"
                        r"여기 ?(있어|서)|따라오지 ?마|됐어|^\s*서[\s,!.]*$", re.I)   # end following (only while it runs)


def stop_word(text):
    """A word that ends following ("stop", "wait", "that's enough", "거기 있어", "기다려")."""
    return bool(STOP_WORDS.search(text or ""))


def running():
    return _thread is not None and _thread.is_alive()


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


def speeds(distance, angle_deg, v_last, dt=TICK_S):
    """(v m/s, w rad/s) toward a person `distance` m away at `angle_deg` (+ left); never forward inside the gap."""
    if distance <= FOLLOW_GAP_M:
        return 0.0, 0.0                                 # close enough: stand still (no turn: the arm sweeps)
    a = math.radians(angle_deg)
    w = 0.0 if abs(angle_deg) < TURN_DEAD_DEG else max(-TURN_MAX_RS, min(TURN_MAX_RS, TURN_GAIN * a))
    v = 0.0 if abs(angle_deg) > TURN_ONLY_DEG else min(FOLLOW_MAX_MS, SPEED_GAIN * (distance - FOLLOW_GAP_M),
                                                       v_last + ACCEL_MS2 * dt)
    return max(0.0, v), w


def blocked(v, w, arm_pts):
    """True when the base or the arm would come too close to something within BRAKE_S at (v, w)."""
    x, y, th = agv.pose()
    th2 = th + w * BRAKE_S
    x2, y2 = x + v * BRAKE_S * math.cos(th), y + v * BRAKE_S * math.sin(th)
    if v > 0:
        ahead = agv.clearance(x2, y2)
        if ahead < BASE_CLEAR_M and ahead < agv.clearance(x, y):
            fetch.log(f"follow: an obstacle {ahead:.2f} m from the base's way")
            return True
    c, s = math.cos(th2), math.sin(th2)
    for p in arm_pts:
        px, py = x2 + c * p[0] - s * p[1], y2 + s * p[0] + c * p[1]
        if agv.clearance(px, py) < ARM_CLEAR_M:
            fetch.log(f"follow: my arm would hit something at ({px:.2f}, {py:.2f})")
            return True
    return False


def ready():
    """Why following can't start now as (en, ko), None when it can. The arm must be able to go to look, or be there
    already: then it may stay switched off (it does not move while following)."""
    if fetch._charging():
        return CHARGER
    try:
        if fetch._at_pose(fetch._look()):
            return None
        motion._ready()
    except motion.MotionError as e:
        fetch.log(f"follow: the arm can't go to look: {e}")
        return ARM_BUSY if "program" in str(e) else ARM_OFF
    except Exception as e:                               # the controller does not answer
        fetch.log(f"follow: the arm does not answer: {e!r}")
        return NO_ARM
    return None


def prepare():
    """Arm to look, waist to the front (as before every fetch drive). The head stays where it is: it is on the person
    already (the track is seen), and ahead they may be out of view (lost at once, 2026-10-21). Returns the arm's points (m, base
    frame) that stick out past the base, [] when the arm's place on the base is not measured. FetchError when it
    must not drive."""
    why = ready()
    if why:
        raise fetch.FetchError(*why)
    fetch._stop.clear()                                  # a stop said earlier must not end this one
    fetch._pose(fetch._look())
    fetch._waist_front()
    if fetch.arm_yaw() is None:
        fetch.log("follow: the arm's place on the base is not measured: only the base is checked")
        return []
    return [np.asarray(p, float) for p in fetch.arm_points()]


def _relock(people, last):
    """The see() of the fresh track nearest to where the followed person was last (distance, angle), None when
    nobody is near. ponytail: by position only, appearance (reid) would tell two people apart."""
    d0, a0 = last
    near = [(abs(a - a0), see) for see, d, a, age in people()
            if age < STALE_S and abs(a - a0) <= RELOCK_DEG and abs(d - d0) <= RELOCK_M]
    return min(near, key=lambda n: n[0], default=(0, None))[1]


def _head_follow(target, done, lift, waist):
    """Turn the head to target[0] (yaw, pitch) whenever it is HEAD_STEP_DEG from where it was sent last. One moveto
    at a time, from this thread only: overlapping calls hang the body API."""
    sent = None
    while not done.is_set():
        t = target[0]
        if t is None or sent is not None and max(abs(t[0] - sent[0]), abs(t[1] - sent[1])) < HEAD_STEP_DEG:
            done.wait(TICK_S)
            continue
        try:
            head.moveto([lift, waist, *t], vel=HEAD_VEL, acc=HEAD_VEL, timeout=HEAD_TIMEOUT_S)
            sent = t
        except (ConnectionError, OSError, ValueError, KeyError) as e:
            fetch.log(f"follow: head error {e!r}")
            done.wait(1.0)


def _run(see, say, people):
    """The loop: until stop(), lost, or something in the way. Any failure ends with the base at 0 and a reason said."""
    v, turning = 0.0, False
    done, target = threading.Event(), [None]
    head.owners = (threading.current_thread(),)
    try:
        arm_pts = prepare()
        lift, waist = head.status()[:2]
        head_thread = threading.Thread(target=_head_follow, args=(target, done, lift, waist), daemon=True,
                                       name="follow head")
        head.owners += (head_thread,)
        head_thread.start()
        seen_t, last = time.time(), None
        while not _stop.is_set():
            got = see()
            now = time.time()
            if (got is None or got[2] >= STALE_S) and last and people:
                new = _relock(people, last)
                if new is not None:
                    fetch.log(f"follow: re-locked onto the person at {last[1]:+.0f} deg")
                    see, got = new, new()
            if got is not None and got[2] < STALE_S:
                seen_t, last = now - got[2], got[:2]
                cmd = speeds(got[0], got[1], v)
                target[0] = (max(-HEAD_YAW_MAX, min(HEAD_YAW_MAX, got[1])), HEAD_PITCH)
            else:                                        # stale or gone (Vision drops a track unseen for 2 s)
                if now - seen_t >= LOST_S:
                    fetch.log("follow: lost the person")
                    fetch._say(say, *LOST)
                    return
                cmd = (0.0, 0.0)
            spot = cmd[0] == 0.0 and cmd[1] != 0.0      # a turn on the spot (the person aside or behind)
            if spot and not turning:
                hit = fetch.turn_hits(got[1])            # the arm's whole sweep toward them
                if hit is not None:
                    fetch.log(f"follow: turning {got[1]:+.0f} deg my arm would hit something at "
                              f"({hit[0]:.2f}, {hit[1]:.2f})")
                    fetch._say(say, "My arm can't turn here, something is in its way.",
                               "팔이 부딪힐 수 있어서 돌 수 없어요.")
                    return
            turning = spot
            if cmd != (0.0, 0.0) and blocked(*cmd, arm_pts):
                fetch._say(say, "Something is in my way, so I stopped.", "앞이 막혀서 멈췄어요.")
                return
            with _send:
                if _stop.is_set():
                    return
                _joy(*cmd)
            v = cmd[0]
            _stop.wait(TICK_S)
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
    fetch.log("follow: start")
    _thread = threading.Thread(target=_run, args=(see, say, people), daemon=True, name="follow")
    _thread.start()
