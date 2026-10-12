"""Lumi voice assistant: greets every visitor, talks with them and obeys voice commands.

    python lumi.py                 # full: camera, greetings, conversation, commands
    python lumi.py --no-camera     # no camera: press Enter to start a conversation (desk testing)
    python lumi.py --no-arm --no-drive     # no waving, no base driving
    python lumi.py --patrol a,b    # walk between markers in a loop; stop for people in the way, talk, go on
    python lumi.py --patrol p1,p2,final,p10,home --once --pause 0.5   # drive the route once, end at the dock

Behaviour
- Every person the camera sees gets a track (an ID followed from frame to frame).
- A new person who stays in the greeting zone is greeted once: Lumi turns its head to them,
  waves and says hello. A second person who arrives is greeted the same way, then the talk goes on.
- While a greeted person stays but says nothing, Lumi does not wave again; after PROMPT_S of silence
  it asks "How can I help you?" (at most MAX_PROMPTS times).
- When the person disappears from the camera (LOST_S), listening and speaking stop at once.
  Someone who comes back later is a new visit and is greeted again.
- Voice commands (English / Korean): go to <marker>, go home, look left/right/up/down/center, wave, stop.
- Patrol (--patrol): drive marker to marker in a loop. Only a person in the robot's path (PATH_HALF_WIDTH to
  each side) closer than PATROL_NEAR_MAX makes Lumi stop and greet; people sitting beside the path are ignored.
  If the person says nothing for PATROL_WAIT_S, or the talk is over, or the person left, the patrol goes on
  (the base drives around a person who still stands in the way).
  Below LOW_BATTERY % Lumi drives home to charge and continues at RESUME_BATTERY %.
- Wake word: "Hi Lumi" / "Hey Lumi" / "루미야" from anywhere, also from far away or from behind. Lumi finds the
  direction of the voice (doa.py), turns its head (or the whole base if the voice is behind) to that person,
  answers "Hi, I'm Lumi..." and listens. Words after the wake word ("Hi Lumi, come here") are obeyed at once.
- Several people: each utterance's direction picks the visible person who spoke; the head turns to them.
- "Come here" / "come to me" / "이리 와": Lumi computes where that person stands on the map and drives to a
  free spot STOP_DIST in front of them that it can reach (nav.py), stopping early when it is COME_STOP away.
- The person Lumi talks to is drawn red in the dashboard (person.focus_angle).
- Sound direction calibrates itself: while Lumi talks with the only person in view, their camera angle is the
  truth for each utterance (doa.add_sample); after enough samples doa_calib.json is written.
- Replies are streamed: Lumi starts speaking after the LLM's first sentence.

Modes (switched live from the dashboard through /dev/shm/lumi_modes.json, see api.py /assistant/modes):
- greeter: while standing, greet people who come close, talk, listen for "Hi Lumi".
- patrol:  while driving anywhere (a marker picked on the dashboard, "go to p2", a --patrol route), stop for a
           person in the path, greet and talk, then drive on to the same destination.
- wave / drive: wave when greeting; allow "come here" and voice "go to".
The dashboard's Go / Cancel are sent to this program (/dev/shm/lumi_cmd.json) while it runs, so it can stop
for people on the way. A calibration session for the sound direction can also be started from there.
"""
import argparse
import collections
import json
import io
import traceback
import itertools
import math
import os
import subprocess
import sys
import threading
import time

# Started with the system python (no cv2 there)? Restart with the project's venv.
VENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
VENV_PY = os.path.join(VENV, "bin", "python")
if os.path.exists(VENV_PY) and os.path.realpath(sys.prefix) != os.path.realpath(VENV):
    os.execv(VENV_PY, [VENV_PY, os.path.abspath(__file__)] + sys.argv[1:])

import re

import agv
import arm
import brain as brain_mod
import camview
import doa
import ears
import head
import mic
import mouth
import nav
from brain import Brain

NEAR_MIN, NEAR_MAX = 0.5, 1.2      # m, greeting zone
PATROL_NEAR_MAX = 1.0              # m, on patrol: only people this close stop the robot
STAY_MAX = 2.5                     # m, a greeted person farther than this counts as gone
HOLD_S = 0.7                       # s in the zone before a greeting
LOST_S = 2.0                       # s not seen -> the person is gone (detections can miss a few frames)
PROMPT_S = 12.0                    # s of silence before "How can I help you?"
MAX_PROMPTS = 2
TOO_CLOSE = 0.45                   # m, a running wave is stopped
AUDIO_DELAY = 0.3                  # s between starting the wave and the greeting voice
MATCH_DEG = 12.0                   # a detection belongs to the track with the closest angle within this
OCCLUSION_DROP = 0.3               # m; while the arm moves, a sudden drop in distance is the arm in front of
                                   # the person, not the person moving: ignore it
CLOSE_BOX = 0.85                   # a person is really closer than TOO_CLOSE only if the box is this tall (frame part)
HEAD_SIGN = 1.0                    # +image angle -> +head yaw (checked: + = robot's left)
LOOK = {"left": (40, None), "right": (-40, None), "center": (0, 0), "up": (None, 20), "down": (None, -5)}
# ^ yaw/pitch in degrees for "look" commands: +yaw = left, +pitch = up (checked on the dashboard 2026-10-12)
WAKE = re.compile(r"\b(hi|hey|hello|okay|ok|hai|high)?[\s,.!]*(lumi|loomi|lumie|lumy|lummy|looney|lu-mi|rumi|roomie)\b"
                  r"|루미|누미", re.I)
WAKE_REPLY = {"en": "Hi, I'm Lumi, the assistant robot. How can I help you?", "ko": "안녕하세요, 저는 루미예요. 무엇을 도와드릴까요?"}
WAKE_MAX_S = 6.0                   # s; longer utterances are not checked for the wake word
VOICE_SESSION_S = 15.0             # s a conversation started by voice (nobody in view) waits for the next words
SPEAKER_MATCH_DEG = 25.0           # a voice direction belongs to the visible person within this angle
DOA_MIN_CONF = 0.12                # below this the sound direction is not trusted
COME_STOP = 1.1                    # m; driving to a person stops when the camera sees them this close
COME_TIMEOUT = 60.0                # s
MODES_FILE = "/dev/shm/lumi_modes.json"   # written by api.py: {"greeter", "patrol", "wave", "drive"}
CMD_FILE = "/dev/shm/lumi_cmd.json"       # written by api.py: {"id", "cmd": go | go_point | cancel | calibrate}
CALIB_FILE = "/dev/shm/lumi_calib.json"   # progress of a calibration session, for the dashboard
CALIB_S = 120.0                    # s a calibration session lasts
CALIB_NEAR = 2.0                   # m; the speaker for a calibration sample is the nearest person within this
CALIB_ALONE_DEG = 30.0             # ... with nobody else within this angle (closer than 4 m)
STUCK_S = 90.0                     # s without a main-loop pass -> stacks of all threads into the log
GREETING = "Hi, I'm Lumi, the assistant robot. How can I help you?"   # same voice as every other answer
PROMPT = {"en": "How can I help you?", "ko": "무엇을 도와드릴까요?"}
PATH_HALF_WIDTH = 0.4              # m to each side of the robot's centre line; on patrol only people in this
                                   # corridor are greeted (not people sitting at desks beside the aisle)
CAMERA_STALL_S = 3.0               # s without a camera frame -> reopen the camera
HEALTH_S = 30.0                    # s between "camera ok" lines in the log
PATROL_WAIT_S = 8.0                # s; on patrol, after the greeting or the last answer, wait this long for speech
LOW_BATTERY, RESUME_BATTERY = 5, 60    # %
PAUSE_AT_END = 3.0                 # s to wait at each patrol point


LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lumi.log")


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:          # also kept in lumi.log, to read it over SSH
            f.write(line + "\n")
    except OSError:
        pass


def safe(fn, *args, default=None):
    """Call a robot function; on a network error log it and carry on instead of crashing."""
    try:
        return fn(*args)
    except Exception as e:
        log(f"{getattr(fn, '__name__', fn)} failed: {e}")
        return default


class Track:
    _ids = itertools.count(1)

    def __init__(self, p, now):
        self.id = next(self._ids)
        self.distance, self.angle = p["distance_m"], p["angle_deg"]
        self.history = collections.deque(maxlen=7)     # recent distances, median-filtered
        self.first_seen = self.last_seen = now
        self.zone_since = None
        self.greeted = False

    def update(self, p, now, arm_moving=False, near_max=NEAR_MAX):
        self.angle, self.last_seen = p["angle_deg"], now
        d = p["distance_m"]
        if not (arm_moving and self.history and d < self.distance - OCCLUSION_DROP):
            self.history.append(d)
            self.distance = sorted(self.history)[len(self.history) // 2]
        in_zone = NEAR_MIN <= self.distance <= near_max
        self.zone_since = (self.zone_since or now) if in_zone else None


class Vision(threading.Thread):
    """Person detection + simple tracking (nearest match by angle and distance)."""

    def __init__(self, camera, near_max=NEAR_MAX, corridor=None):
        super().__init__(daemon=True)
        self.near_max, self.corridor = near_max, corridor     # corridor: half width in m, None = everyone
        self.last_report = 0.0
        self.camera = camera
        self.det = camview.RemoteDetector(camera, HEAD_SIGN)   # the camera service owns the cameras
        self.tracks = []
        self.lock = threading.Lock()
        self.arm_watch = False

    def run(self):
        last_frame = last_health = time.time()
        frames = 0
        while True:
            try:
                color, people = self.det.read()
            except Exception as e:
                log(f"camera error: {e!r}")
                color, people = None, []
            now = time.time()
            if color is None:
                if now - last_frame > CAMERA_STALL_S:         # no frames: reopen the camera
                    log(f"camera: no frames for {now - last_frame:.0f} s - reopening")
                    self.reopen()
                    last_frame = time.time()
                continue
            last_frame, frames = now, frames + 1
            if now - last_health > HEALTH_S:                  # proves the camera is alive even with nobody around
                log(f"camera ok ({self.det.name}): {frames / (now - last_health):.1f} fps, {len(people)} people in view, "
                    f"{self.det.bad_jpeg} broken frames skipped, {self.det.reopens} reopens")
                last_health, frames = now, 0
            people = [p for p in people if p["distance_m"] is not None]
            with self.lock:
                free = list(self.tracks)
                for p in sorted(people, key=lambda p: p["distance_m"]):
                    best = min(free, default=None, key=lambda t: abs(t.angle - p["angle_deg"]))
                    if best and abs(best.angle - p["angle_deg"]) < MATCH_DEG:
                        best.update(p, now, self.arm_watch, self.near_max)
                        free.remove(best)
                    else:
                        t = Track(p, now)
                        t.update(p, now, near_max=self.near_max)
                        self.tracks.append(t)
                self.tracks = [t for t in self.tracks if now - t.last_seen < LOST_S]
                if self.tracks and now - self.last_report > 3.0:      # what the camera sees, for checking on the robot
                    self.last_report = now
                    log("see " + ", ".join(f"#{t.id} {t.distance:.2f} m {t.angle:+.0f} deg" + (" greeted" if t.greeted else "")
                                           + ("" if self.in_path(t) else " side")
                                           for t in self.tracks))
            # safety: really close = small depth AND a box that fills the frame (the arm in front of a person
            # changes the depth but not the size of the person's box)
            h = color.shape[0]
            close = [p for p in people
                     if p["distance_m"] < TOO_CLOSE and (p["box"][3] - p["box"][1]) > CLOSE_BOX * h]
            if self.arm_watch and close:
                log(f"person at {close[0]['distance_m']} m - STOP arm")
                safe(arm.stop)
                self.arm_watch = False

    def reopen(self):
        try:
            self.det.close()
        except Exception:
            pass
        try:
            self.det = camview.RemoteDetector(self.camera, HEAD_SIGN)
        except Exception as e:
            log(f"camera reopen failed: {e!r}")
            time.sleep(2)

    def present(self, track):
        """Is this person still here (seen recently and not far away)?"""
        with self.lock:
            return track in self.tracks and track.distance <= STAY_MAX

    def in_path(self, t):
        return self.corridor is None or abs(t.distance * math.sin(math.radians(t.angle))) <= self.corridor

    def to_greet(self):
        """Nearest person waiting in the zone (and in the robot's path on patrol) not greeted yet."""
        now = time.time()
        with self.lock:
            ready = [t for t in self.tracks if not t.greeted and t.zone_since and now - t.zone_since >= HOLD_S
                     and self.in_path(t)]
        return min(ready, key=lambda t: t.distance, default=None)

    def near_angle(self, angle, max_diff=SPEAKER_MATCH_DEG):
        """The visible person closest to this waist-frame angle (deg), or None."""
        with self.lock:
            best = min(self.tracks, default=None, key=lambda t: abs(t.angle - angle))
        return best if best is not None and abs(best.angle - angle) <= max_diff else None

    def only_person(self):
        with self.lock:
            near = [t for t in self.tracks if t.distance <= 3.0]
        return near[0] if len(near) == 1 else None

    def nearest_greeted(self):
        with self.lock:
            here = [t for t in self.tracks if t.greeted and t.distance <= STAY_MAX]
        return min(here, key=lambda t: t.distance, default=None)


class Patrol:
    """Drive between markers in a loop (or once); pause for people; go home to charge when the battery is low."""

    def __init__(self, route, once=False, pause_s=PAUSE_AT_END):
        self.route, self.i = route, 0
        self.once, self.pause_s = once, pause_s
        self.mode = "patrol"             # patrol | going_home | charging | done
        self.moving = False              # a move that we started is running
        self.wait_until = 0.0
        self.last_poll = 0.0

    def pause(self):
        if self.moving:
            log("drive paused")
            safe(agv.cancel)
            self.moving = False

    def tick(self, force=False):
        """Call often while nobody is being talked to; polls the base once a second.
        force=True: start the first leg now, even if the base is still driving somewhere else."""
        now = time.time()
        if now - self.last_poll < 1.0 and not force:
            return
        self.last_poll = now
        st = safe(agv.status, default=None)
        if not st:
            return
        battery, ms = st.get("power_percent", 100), st.get("move_status")

        if self.mode == "done":
            return
        if self.mode == "charging":
            if battery >= RESUME_BATTERY:
                log(f"battery {battery} % - patrol again")
                self.mode = "patrol"
            return
        if self.mode == "patrol" and battery < LOW_BATTERY:
            log(f"battery {battery} % - going home to charge")
            self.pause()
            ok, msg = safe(agv.go, "home", default=(False, "error"))
            self.mode, self.moving = ("going_home", True) if ok else ("patrol", False)
            return

        if self.moving:
            if ms == "running":
                return
            self.moving = False
            if self.mode == "going_home":
                self.mode = "charging" if st.get("charge_state") else "patrol"
                log("docked, charging" if self.mode == "charging" else f"could not dock ({ms})")
                return
            if ms == "succeeded":
                log(f"patrol at {self.route[self.i]}")
                if self.once and self.i == len(self.route) - 1:
                    self.mode = "done"
                    log("route finished")
                    return
                self.i = (self.i + 1) % len(self.route)
                self.wait_until = now + self.pause_s
            else:
                log(f"patrol move {ms} - retry in 5 s")
                self.wait_until = now + 5
            return
        if (ms == "running" and not force) or now < self.wait_until:   # something else is driving, or waiting
            return
        target = self.route[self.i]
        if isinstance(target, (tuple, list)):
            ok, msg = safe(agv.go_point, *target, default=(False, "error"))
        else:
            ok, msg = safe(agv.go, target, default=(False, "error"))
        if ok:
            self.moving = True
            log(f"patrol -> {target}")
        else:
            log(f"patrol cannot go to {self.route[self.i]}: {msg}")
            self.wait_until = now + 5


class Modes:
    """Live switches from the dashboard (MODES_FILE); the command line gives the defaults."""

    def __init__(self, args):
        self.greeter, self.patrol = True, bool(args.patrol)
        self.wave, self.drive = not args.no_arm, not args.no_drive
        self._read, self._mtime = 0.0, None
        self.refresh(force=True)

    def refresh(self, force=False):
        now = time.time()
        if not force and now - self._read < 0.5:
            return
        self._read = now
        try:
            m = os.stat(MODES_FILE).st_mtime
            if m != self._mtime:
                self._mtime = m
                d = json.load(open(MODES_FILE))
                changed = {k: d[k] for k in ("greeter", "patrol", "wave", "drive") if k in d and d[k] != getattr(self, k)}
                for k, v in changed.items():
                    setattr(self, k, bool(v))
                if changed and not force:
                    log(f"modes: {changed}")
        except (FileNotFoundError, ValueError):
            pass


class Lumi:
    def __init__(self, args):
        self.a = args
        self.brain = Brain()
        self.markers = agv.markers()
        self.current = None              # the track we are talking with
        self.voice_until = 0.0           # a conversation started by voice with nobody in view lasts until then
        self.lang = "en"
        self.mic = mic.get()
        self.modes = Modes(args)
        self.cmd_id = None
        self.calib_until = 0.0
        self.calib_n = 0
        self.patrol = None
        if args.patrol:
            route = args.patrol.split(",")
            unknown = [m for m in route if m not in self.markers]
            if unknown:
                raise SystemExit(f"unknown markers {unknown}; markers on the map: {self.markers}")
            self.patrol = Patrol(route, args.once, args.pause)
        self.vision = None if args.no_camera else Vision(args.camera)
        log(f"markers: {self.markers}")

    # ---------- actions ----------
    def turn_head(self, yaw=None, pitch=None):
        def run():
            try:
                cur = head.status()
                head.turn(cur[2] if yaw is None else yaw, cur[3] if pitch is None else pitch)
            except Exception as e:
                log(f"head error: {e}")
        threading.Thread(target=run, daemon=True).start()

    def wave(self, wait_s=6.0):
        """Start the wave program; if the arm is still waving for someone else, wait for it."""
        if not self.modes.wave:
            return False
        t = time.time()
        while not safe(arm.ready, default=False) and time.time() - t < wait_s:
            time.sleep(0.2)
        if not safe(arm.ready, default=False):
            log("arm not ready (power/enable off or busy)")
            return False
        if safe(arm.start, default="failed") == "failed":
            return False
        if self.vision:
            self.vision.arm_watch = True
            threading.Thread(target=self._end_arm_watch, daemon=True).start()
        return True

    def _end_arm_watch(self):
        """Clear arm_watch when the wave program has finished."""
        time.sleep(1.0)
        while safe(arm.program_state, default="idle") != "idle":
            time.sleep(0.3)
        self.vision.arm_watch = False

    def act(self, action, target):
        log(f"action: {action} {target}")
        if action == "look" and target in LOOK:
            self.turn_head(*LOOK[target])
        elif action == "wave":
            self.wave()
        elif action == "stop":
            safe(agv.cancel)
            safe(arm.stop)
        elif action == "go_to" and self.modes.drive:
            self.start_trip(target)

    # ---------- dashboard commands, trips ----------
    def poll_commands(self):
        try:
            d = json.load(open(CMD_FILE))
        except (FileNotFoundError, ValueError):
            return
        if d.get("id") == self.cmd_id:
            return
        first = self.cmd_id is None
        self.cmd_id = d.get("id")
        if first and time.time() - d.get("time", 0) > 5:      # an old command from before this start
            return
        cmd = d.get("cmd")
        log(f"dashboard: {cmd} {d.get('marker') or d.get('point') or ''}")
        if cmd == "go":
            self.start_trip(d["marker"])
        elif cmd == "go_point":
            self.start_trip(tuple(d["point"]))
        elif cmd == "cancel":
            if self.patrol:
                self.patrol.pause()
                self.patrol = None
            safe(agv.cancel)
        elif cmd == "calibrate":
            self.calib_until = time.time() + CALIB_S if d.get("on", True) else 0.0
            self.calib_n = 0
            self.write_calib("collecting" if self.calib_until else "stopped")

    def start_trip(self, target):
        """Drive to a marker or a map point; with patrol mode on, people in the way are greeted on the way."""
        if self.patrol:
            self.patrol.pause()
        self.patrol = Patrol([target], once=True, pause_s=0.0)
        self.patrol.tick(force=True)

    def traveling(self):
        return self.patrol is not None and self.patrol.mode != "done"

    def write_calib(self, state, result=None):
        try:
            with open(CALIB_FILE, "w") as f:
                json.dump({"state": state, "samples": self.calib_n, "until": self.calib_until,
                           "result": result, "time": time.time()}, f)
        except OSError:
            pass

    def calibrate_step(self):
        """Calibration session: each utterance of the nearest person (alone in their direction) is a sample."""
        u = self.mic.next(0.2)
        if u is None or u.seconds < 0.8:
            return
        with self.vision.lock:
            near = sorted((t for t in self.vision.tracks if t.distance <= 4.0), key=lambda t: t.distance)
        if not near or near[0].distance > CALIB_NEAR:
            log("  calibration: speech heard, but nobody within 2 m")
            return
        me = near[0]
        if any(abs(t.angle - me.angle) < CALIB_ALONE_DEG for t in near[1:]):
            log("  calibration: someone else stands in the same direction - skipped")
            return
        self.calib_n += 1
        c = doa.add_sample(u.mics, me.angle - HEAD_SIGN * self.det_yaw())
        log(f"  calibration sample {self.calib_n}: person at {me.angle:+.0f} deg, {me.distance:.1f} m"
            + (f" -> calibrated {c}" if c else ""))
        self.write_calib("calibrated" if c else "collecting", c)

    # ---------- interrupts ----------
    def interrupted(self):
        """Stop listening/speaking: the person left, or a new person is waiting to be greeted."""
        if not self.vision:
            return False
        if self.current is None and time.time() < self.voice_until:
            return False
        return (self.current is not None and not self.vision.present(self.current)) or \
            self.vision.to_greet() is not None

    # ---------- behaviour ----------
    def greet(self, track):
        track.greeted = True
        self.current = track
        log(f"GREET person #{track.id} at {track.distance} m, {track.angle:+.0f} deg")
        self.turn_head(HEAD_SIGN * track.angle)
        delay = AUDIO_DELAY if self.wave() else 0.0
        time.sleep(delay)
        mouth.say(GREETING)                              # cached at start: plays at once

    def talk_turn(self):
        """Listen once; answer if something was said. Returns True if the visitor spoke."""
        text, u = ears.listen(wait_s=4.0, on_start=lambda: log("  hearing speech"), abort=self.interrupted, full=True)
        if not text or self.interrupted():
            if not self.interrupted():
                log(f"  heard nothing (mic noise {ears.last.get('noise')}, threshold {ears.last.get('threshold')}, "
                    f"loudest {ears.last.get('peak')})")
            return False
        self.who_spoke(u)
        self.answer(text)
        return True

    def who_spoke(self, u):
        """Use the sound direction: pick the visible person who spoke; meanwhile collect calibration samples."""
        if not self.vision or u is None:
            return
        yaw = self.det_yaw()
        only = self.vision.only_person()
        if only is not None and only is self.current and only.distance <= 1.6 and u.seconds >= 0.8:
            # the only person in view is the one we talk to, close by: their angle is the truth
            c = doa.add_sample(u.mics, only.angle - HEAD_SIGN * yaw)
            if c:
                log(f"sound direction calibrated: {c}")
            return
        cal = doa.load_calib()
        if not cal["fitted"]:
            return
        ang, conf, _ = doa.estimate(u.mics, cal)
        if conf < DOA_MIN_CONF:
            return
        t = self.vision.near_angle(HEAD_SIGN * yaw + ang)
        if t is not None and t is not self.current:
            log(f"  voice from {HEAD_SIGN * yaw + ang:+.0f} deg: person #{t.id} is speaking")
            t.greeted = True
            self.current = t
            self.turn_head(HEAD_SIGN * t.angle)

    def det_yaw(self):
        return self.vision.det.head_yaw if self.vision else 0.0

    def answer(self, text):
        """Stream the LLM reply: act on the action line, speak sentence by sentence."""
        self.lang = mouth.lang_of(text)
        log(f"visitor #{self.current.id if self.current else 'voice'}: {text}")
        t = time.time()
        gen = self.brain.respond_stream(text, self.markers)
        head_ = next(gen)
        log(f"  action {head_['action']} {head_['target']} ({time.time() - t:.1f} s)")
        if head_["action"] == "come":
            gen.close()
            mouth.say("Okay, I'm coming." if self.lang == "en" else "네, 갈게요.")
            self.come_to(self.current)
            return
        if head_["action"] not in ("none", "end"):
            self.act(head_["action"], head_["target"])
        first = [True]

        def timed():
            for sentence in gen:
                if first[0]:
                    log(f"  first sentence after {time.time() - t:.1f} s")
                    first[0] = False
                yield sentence
        said = mouth.say_stream(timed(), abort=self.interrupted)
        log(f"lumi ({time.time() - t:.1f} s): {said}")
        if head_["action"] in ("end", "go_to"):
            self.current, self.voice_until = None, 0.0     # stay quiet with this person until a new visit
        elif self.current is None:
            self.voice_until = time.time() + VOICE_SESSION_S

    # ---------- wake word ----------
    def check_wake(self):
        """Idle: is someone calling "Hi Lumi"? Handles it and returns True."""
        u = self.mic.next(0.0)
        if u is None or not (0.3 <= u.seconds <= WAKE_MAX_S):
            return False
        text = ears.transcribe(u.mono)
        m = WAKE.search(text or "")
        if not m:
            return False
        rest = text[m.end():].strip(" ,.!?")
        lang = "ko" if re.search(r"[가-힣]", text) else "en"
        cal = doa.load_calib()
        ang, conf, raw = doa.estimate(u.mics, cal)
        yaw = self.det_yaw()
        robot_angle = HEAD_SIGN * yaw + ang
        log(f"WAKE {text!r}: voice at {robot_angle:+.0f} deg (confidence {conf:.2f}, "
            f"{'calibrated' if cal['fitted'] else 'NOT calibrated'})")
        if self.patrol:
            self.patrol.pause()
        target = None
        if self.vision:
            if cal["fitted"] and conf >= DOA_MIN_CONF:
                target = self.vision.near_angle(robot_angle)
            if target is None and not (cal["fitted"] and conf >= DOA_MIN_CONF):
                target = self.vision.only_person()            # no trusted direction: the only person in view
        if target is not None:
            target.greeted = True
            self.current = target
            self.turn_head(HEAD_SIGN * target.angle)
        elif cal["fitted"] and conf >= DOA_MIN_CONF:
            self.look_toward(robot_angle)
        self.brain.reset()
        mouth.say(WAKE_REPLY[lang])
        self.voice_until = time.time() + VOICE_SESSION_S
        self.last_activity, self.prompts = time.time(), 0
        if target is None and self.vision:                    # we turned toward the voice: who is there now?
            time.sleep(1.0)
            self.current = self.vision.near_angle(0.0 + HEAD_SIGN * self.det_yaw(), 35) or self.vision.only_person()
            if self.current:
                self.current.greeted = True
        if rest and len(rest) > 2:
            self.answer(rest)
        return True

    def look_toward(self, robot_angle):
        """Turn the head toward a waist-frame angle; turn the base too if it is outside the head's range."""
        if abs(robot_angle) <= head.YAW_LIMIT:
            self.turn_head(HEAD_SIGN * robot_angle)
        elif self.modes.drive:
            log(f"  voice behind ({robot_angle:+.0f} deg): turning the base")
            self.turn_head(0)
            safe(agv.turn_by, math.radians(robot_angle))
            t = time.time()
            time.sleep(0.5)
            while time.time() - t < 8 and (safe(agv.status, default={}) or {}).get("move_status") == "running":
                time.sleep(0.2)

    # ---------- come here ----------
    def come_to(self, track):
        """Drive to the person (a visible track) and stop about COME_STOP in front of them."""
        if not self.modes.drive:
            mouth.say("Sorry, driving is switched off.")
            return
        if track is None or not self.vision or not self.vision.present(track):
            mouth.say("I can't see you. Please stand in front of me." if self.lang == "en"
                      else "보이지 않아요. 제 앞에 서 주세요.")
            return
        robot = safe(agv.pose)
        waist = (safe(head.status, default=[0, 0, 0, 0]) or [0, 0, 0, 0])[1]
        if robot is None:
            return
        px, py = nav.person_on_map(track.distance, track.angle, waist, robot)
        goal = safe(nav.approach, px, py, robot)
        log(f"COME to person #{track.id} at {track.distance:.2f} m {track.angle:+.0f} deg -> map ({px:.2f}, {py:.2f}),"
            f" goal {goal}")
        if goal == "close":
            mouth.say("I'm right here.")
            return
        if goal is None:
            mouth.say("Sorry, I can't get closer from here.")
            return
        ok, msg = safe(agv.go_point, *goal, default=(False, "error"))
        if not ok:
            log(f"  base refused: {msg}")
            mouth.say("Sorry, I can't get closer from here.")
            return
        t, last_look = time.time(), 0.0
        time.sleep(0.5)
        while time.time() - t < COME_TIMEOUT:
            st = safe(agv.status, default={}) or {}
            if st.get("move_status") != "running":
                log(f"  arrived ({st.get('move_status')})")
                break
            if self.vision.present(track):
                if track.distance <= COME_STOP:
                    log(f"  person #{track.id} is {track.distance:.2f} m away - stop")
                    safe(agv.cancel)
                    break
                if time.time() - last_look > 1.0:             # keep looking at them while driving
                    self.turn_head(HEAD_SIGN * track.angle)
                    last_look = time.time()
            time.sleep(0.2)
        else:
            safe(agv.cancel)
        if self.vision.present(track):
            self.turn_head(HEAD_SIGN * track.angle)
        self.last_activity = time.time()

    def run_camera(self):
        self.last_activity, self.prompts = time.time(), 0
        self.alive = time.time()
        threading.Thread(target=self.watchdog, daemon=True).start()
        while True:
            self.alive = time.time()
            try:
                self.step()
            except Exception as e:                     # never stop the robot program on one error
                log(f"error: {e!r}")
                time.sleep(1)

    def step(self):
        """One pass of the camera behaviour (see the module docstring)."""
        self.modes.refresh()
        self.poll_commands()
        if self.patrol and self.patrol.mode == "done" and not self.a.patrol:
            self.patrol = None                             # a dashboard / voice trip has arrived
        moving = self.traveling()
        # on the way only people in the path, close by; standing: everyone in the greeting zone
        self.vision.near_max, self.vision.corridor = (PATROL_NEAR_MAX, PATH_HALF_WIDTH) if moving else (NEAR_MAX, None)
        if time.time() < self.calib_until:
            self.vision.det.focus_angle = None
            self.calibrate_step()
            return
        if self.calib_until:
            self.calib_until = 0.0
            self.write_calib("finished")
        greet_now = self.modes.patrol if moving else self.modes.greeter
        candidate = self.vision.to_greet() if greet_now else None
        focus = self.current or candidate
        self.vision.det.focus_angle = focus.angle if focus else None    # drawn red in the dashboard
        new = candidate
        if new:                                            # a new visitor (first or second person)
            if self.patrol:
                self.patrol.pause()
            if self.current is None:
                self.brain.reset()
            self.greet(new)
            self.last_activity, self.prompts = time.time(), 0
            return

        if self.current and not self.vision.present(self.current):
            log(f"person #{self.current.id} left - stop talking")
            self.current = self.vision.nearest_greeted()   # someone else still here?
            if self.current:
                self.turn_head(HEAD_SIGN * self.current.angle)
            else:
                self.turn_head(0, 0)
                self.brain.reset()
            self.last_activity, self.prompts = time.time(), 0
            return

        if self.current is None:
            if time.time() < self.voice_until:            # talking with someone we only heard
                if self.talk_turn():
                    self.voice_until = max(self.voice_until, time.time() + VOICE_SESSION_S)
                return
            if self.voice_until:
                log("voice conversation over")
                self.voice_until = 0.0
                self.turn_head(0, 0)
                self.brain.reset()
            if self.modes.greeter and self.check_wake():
                return
            if not self.modes.greeter:
                self.mic.clear()                           # nobody listens: do not pile up old speech
            if self.patrol:
                self.patrol.tick()
            time.sleep(0.05)
            return

        if self.traveling() and time.time() - self.last_activity > PATROL_WAIT_S:
            log(f"no answer for {PATROL_WAIT_S:.0f} s - drive on")
            self.current = None
            self.turn_head(0, 0)
            return

        if self.talk_turn():
            self.last_activity, self.prompts = time.time(), 0
        elif (not self.interrupted() and time.time() - self.last_activity > PROMPT_S and self.prompts < MAX_PROMPTS):
            log(f"silent for {PROMPT_S:.0f} s - prompt")
            mouth.say(PROMPT[self.lang], abort=self.interrupted)
            self.last_activity, self.prompts = time.time(), self.prompts + 1

    def watchdog(self):
        """If the main loop is stuck for STUCK_S, write every thread's stack to the log (to find the cause)."""
        reported = 0.0
        while True:
            time.sleep(5)
            if time.time() - self.alive > STUCK_S and self.alive != reported:
                reported = self.alive
                buf = io.StringIO()
                frames = sys._current_frames()
                for th in threading.enumerate():
                    f = frames.get(th.ident)
                    if f is not None:
                        buf.write(f"--- thread {th.name}\n" + "".join(traceback.format_stack(f)[-6:]))
                log(f"MAIN LOOP STUCK for {time.time() - self.alive:.0f} s:\n{buf.getvalue()}")

    def run_desk(self):
        while True:
            input("\nPress Enter to start a conversation (Ctrl+C to quit)...")
            self.brain.reset()
            self.current = None
            if self.wave():
                time.sleep(AUDIO_DELAY)
            mouth.say(GREETING)
            silent = 0
            while silent < 2:
                if self.talk_turn():
                    silent = 0
                else:
                    silent += 1
                    if silent == 1:
                        mouth.say(PROMPT[self.lang])

    def run(self):
        log("loading speech models...")
        threading.Thread(target=brain_mod.warm_up, daemon=True).start()
        ears.ensure_stt_server()
        mouth.warm_up()
        cal = doa.load_calib()
        log("sound direction " + (f"calibrated ({cal})" if cal["fitted"] else "not calibrated yet: it learns while "
                                  "talking with one person in view"))
        if self.vision:
            self.vision.start()
        log("ready")
        self.run_camera() if self.vision else self.run_desk()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--no-arm", action="store_true")
    ap.add_argument("--no-drive", action="store_true")
    ap.add_argument("--camera", default="head", choices=camview.CAMERAS)
    ap.add_argument("--patrol", help="comma-separated markers to drive between, e.g. a,b")
    ap.add_argument("--once", action="store_true", help="drive the --patrol route once instead of looping")
    ap.add_argument("--pause", type=float, default=PAUSE_AT_END, help="seconds to wait at each marker")
    try:
        Lumi(ap.parse_args()).run()
    except KeyboardInterrupt:
        print("\nbye")
        os._exit(0)          # leave at once; the camera thread would otherwise abort noisily
