"""Lumi voice assistant: greets every visitor, talks with them and obeys voice commands.

    python assistant/lumi.py                 # full: camera, greetings, conversation, commands
    python assistant/lumi.py --no-camera     # no camera: press Enter to start a conversation (desk testing)
    python assistant/lumi.py --no-arm --no-drive     # no waving, no base driving
    python assistant/lumi.py --patrol a,b    # walk between markers in a loop; stop for people in the way, talk, go on
    python assistant/lumi.py --patrol p1,p2,final,p10,home --once --pause 0.5   # drive the route once, end at the dock

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
- Cameras: standing, the head camera watches people (it turns with the head toward them); driving, the torso
  camera watches the path (it always looks forward). A camera that gives no detections is replaced by the other
  one until it is back. While the arm waves, people too close are watched in both cameras. --camera pins one.
- Sound direction calibrates itself: while Lumi talks with the only person in view, their camera angle is the
  truth for each utterance (doa.add_sample); after enough samples doa_calib.json is written.
- Replies are streamed: Lumi starts speaking after the LLM's first sentence.

Modes (switched live from the dashboard through /dev/shm/lumi_modes.json, see api/server.py /assistant/modes):
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))      # the project folder
VENV = os.path.join(ROOT, ".venv")
VENV_PY = os.path.join(VENV, "bin", "python")
if os.path.exists(VENV_PY) and os.path.realpath(sys.prefix) != os.path.realpath(VENV):
    os.execv(VENV_PY, [VENV_PY, os.path.abspath(__file__)] + sys.argv[1:])

import re

from robot import agv
from robot import arm
from assistant import brain as brain_mod
from vision import camview
from audio import doa
from robot import gripper
from audio import ears
from robot import head
from audio import mic
from robot import motion
from audio import mouth
from robot import nav
from manipulation import skills
from assistant import web
from assistant import fetch_dialog
from assistant.brain import Brain

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
WAKE_REPLY = {"en": "Yes? How can I help?", "ko": "네? 무엇을 도와드릴까요?"}
NAME_ONLY = re.compile(r"^\s*(hi |hey |hello )?(lumi|loomi|rumi|루미)[\s,.!?]*$", re.I)
FETCH_STOP = re.compile(r"\b(stop|halt)\b|멈춰|그만|정지|스톱", re.I)
FETCH_GIVE = re.compile(r"\bgive (it|that|this|the \w+)( to me)?\b|\bhand (it )?(over|to me)\b|줘|주세요|건네", re.I)
FETCH_PLACE = re.compile(r"\b(put|place|set) (it|that|this|the \w+) (down|on the table)\b|테이블에 ?(놔|놓|둬)|내려 ?(놔|놓)", re.I)
FETCH_BRING_IT = re.compile(r"\bbring (it|that|this)\b|가져와|가져다 ?줘|갖다 ?줘", re.I)   # no object named
FETCH_THANKS = re.compile(r"\bthank|\bthanks\b|고마워|감사", re.I)
FAREWELL_WORDS = re.compile(r"\b(thanks?|thank you|bye|goodbye|see you|that'?s all|good night)\b|고마워|감사|안녕히|잘 ?가|다음에", re.I)
HELLO_ONLY = re.compile(r"^\s*(hi|hey|hello|hiya)( there)?[\s,.!]*$|^\s*(안녕|안녕하세요)[\s.!]*$", re.I)
CAMERA_HALF_FOV = 42.0             # deg; half the camera's view (+ the head's YAW_LIMIT for the head camera)
WAKE_MAX_S = 6.0                   # s; longer utterances are not checked for the wake word
BARGE_IN_LOGPROB = -0.6            # an interruption must be heard more clearly than a normal answer (-1.0)
CLOSING_WAIT_S = 3.0               # s of silence after "okay" / "got it" before Lumi says goodbye
VOICE_SESSION_S = 15.0             # s a conversation started by voice (nobody in view) waits for the next words
SPEAKER_MATCH_DEG = 25.0           # a voice direction belongs to the visible person within this angle
DOA_MIN_CONF = 0.12                # below this the sound direction is not trusted
COME_STOP = 1.1                    # m; driving to a person stops when the camera sees them this close
COME_TIMEOUT = 60.0                # s
MAX_MOVE_M = 3.0                   # m; "move forward N metres" is limited to this
ARM_REACH_PROGRAM = "arm_reach.jks"   # Cobo π program for "reach out your hand" (to be recorded on the robot)
STUCK_DRIVE_S = 20.0               # s "running" without moving -> the drive is cancelled and Lumi says so
MODES_FILE = "/dev/shm/lumi_modes.json"   # written by api/server.py: {"greeter", "patrol", "wave", "drive"}
CMD_FILE = "/dev/shm/lumi_cmd.json"       # written by api/server.py: {"id", "cmd": go | go_point | cancel | calibrate
                                          # | fetch | fetch_give | fetch_place | fetch_stop | fetch_carry | fetch_release}
CALIB_FILE = "/dev/shm/lumi_calib.json"   # progress of a calibration session, for the dashboard
CALIB_S = 120.0                    # s a calibration session lasts
CALIB_NEAR = 2.0                   # m; the speaker for a calibration sample is the nearest person within this
CALIB_ALONE_DEG = 30.0             # ... with nobody else within this angle (closer than 4 m)
QUIET_S = 600.0                    # s Lumi greets nobody after "be quiet" (the wake word still works)
STUCK_S = 90.0                     # s without a main-loop pass -> stacks of all threads into the log
GREETING = "Hi, I'm Lumi, the assistant robot. How can I help you?"   # same voice as every other answer
PROMPT = {"en": "How can I help you?", "ko": "무엇을 도와드릴까요?"}
PATH_HALF_WIDTH = 0.4              # m to each side of the robot's centre line; on patrol only people in this
                                   # corridor are greeted (not people sitting at desks beside the aisle)
CAMERA_STALL_S = 3.0               # s without a camera frame -> reopen the camera
CAMERA_FRESH_S = 2.5               # s; a camera whose last detection is older counts as down (idle rate is 1/s)
HEALTH_S = 30.0                    # s between "camera ok" lines in the log
PATROL_WAIT_S = 8.0                # s; on patrol, after the greeting or the last answer, wait this long for speech
LOW_BATTERY, RESUME_BATTERY = 5, 60    # %
PAUSE_AT_END = 3.0                 # s to wait at each patrol point


LOG_FILE = os.path.join(ROOT, "logs", "lumi.log")


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


def too_close(people, frame_h):
    """People really closer than TOO_CLOSE: small depth AND a box that fills the frame."""
    return [p for p in people if p["distance_m"] < TOO_CLOSE and (p["box"][3] - p["box"][1]) > CLOSE_BOX * frame_h]


class Vision(threading.Thread):
    """Person detection + simple tracking (nearest match by angle and distance)."""

    def __init__(self, camera=None, near_max=NEAR_MAX, corridor=None):
        super().__init__(daemon=True)
        self.near_max, self.corridor = near_max, corridor     # corridor: half width in m, None = everyone
        self.last_report = 0.0
        self.pinned = camera                      # None: Lumi.step sets self.prefer (head standing, torso driving)
        self.prefer = camera or "head"
        self.camera = self.pick()
        self.det = camview.RemoteDetector(self.camera, HEAD_SIGN)   # the camera service owns the cameras
        self.tracks = []
        self.lock = threading.Lock()
        self.arm_watch = False

    @staticmethod
    def alive(name):
        try:
            return time.time() - camview.det_path(name).stat().st_mtime < CAMERA_FRESH_S
        except FileNotFoundError:
            return False

    def pick(self):
        """The preferred camera, or the other one while the preferred gives no detections."""
        other = "torso" if self.prefer == "head" else "head"
        return other if not self.alive(self.prefer) and self.alive(other) else self.prefer

    def use(self, name):
        """Read people from this camera from now on (tracks are kept: both give waist-frame angles)."""
        focus = self.det.focus_angle
        self.det.close()
        self.det = camview.RemoteDetector(name, HEAD_SIGN)
        self.det.focus_angle = focus
        self.camera = name

    def run(self):
        last_frame = last_health = last_pick = time.time()
        frames = 0
        while True:
            if time.time() - last_pick > 1.0:
                last_pick = time.time()
                want = self.pick()
                if want != self.camera:
                    log(f"camera: {self.camera} -> {want}" + ("" if want == self.prefer else f" ({self.prefer} gives no detections)"))
                    self.use(want)
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
            close = too_close(people, color.shape[0])
            if self.arm_watch and not close and self.camera != "torso":   # the torso camera looks at the arm's side
                close = self.torso_close()
            if self.arm_watch and close:
                log(f"person at {close[0]['distance_m']} m - STOP arm")
                safe(arm.stop)
                self.arm_watch = False

    @staticmethod
    def torso_close():
        camview.want("torso")                     # full detection rate while the arm moves
        try:
            d = json.loads(camview.det_path("torso").read_text())
        except (FileNotFoundError, ValueError):
            return []
        if time.time() - d["time"] > 1.5:
            return []
        return too_close([p for p in d["people"] if p["distance_m"] is not None], d["height"])

    def reopen(self):
        try:
            self.det.close()
        except Exception:
            pass
        try:
            self.use(self.pick())
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
        self.progress = None             # (pose, time) of the last movement, to notice a stuck drive
        self.stuck = None                # target of a drive that could not get anywhere (Lumi says so)
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
                pose = st.get("current_pose") or {}
                xy = (pose.get("x", 0.0), pose.get("y", 0.0), pose.get("theta", 0.0))
                if self.progress is None or math.hypot(xy[0] - self.progress[0][0], xy[1] - self.progress[0][1]) > 0.05 \
                        or abs(xy[2] - self.progress[0][2]) > 0.1:
                    self.progress = (xy, now)                   # it moves
                elif now - self.progress[1] > STUCK_DRIVE_S:   # "running" but standing still: no way through
                    target = self.route[self.i]
                    log(f"drive to {target} STUCK: the base has not moved for {STUCK_DRIVE_S:.0f} s "
                        f"(no free path? glass door, people, no-go line) - cancelled")
                    safe(agv.cancel)
                    self.moving, self.progress = False, None
                    self.stuck = target
                    if self.once:
                        self.mode = "done"
                    else:
                        self.i = (self.i + 1) % len(self.route)
                        self.wait_until = now + 5
                return
            self.moving, self.progress = False, None
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
        self.quiet_until = 0.0           # after "be quiet": no greetings until then
        self._yaw, self._yaw_time = 0.0, 0.0
        self.pending_text = None         # a question the visitor asked while Lumi was talking (barge-in)
        self.voice_angle, self.voice_trusted = 0.0, False   # where the last caller's voice came from
        self.closing_pending = None      # time of a weak closing word ("okay", "got it"): silence after it ends the talk
        self.lang = "en"
        self.skill_thread = None         # pick / put / move_object running in the background
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
        if not self.modes.wave or self.skill_busy():     # never wave while a skill moves the arm
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
        if action == "look" and target == "me":
            angle = self.current.angle if self.current else self.voice_angle
            self.turn_head(HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, angle)), 10)
        elif action == "look" and target in LOOK:
            self.turn_head(*LOOK[target])
        elif action == "wave":
            threading.Thread(target=self.wave, daemon=True).start()   # while the reply is spoken
        elif action == "stop":
            safe(agv.cancel)
            safe(skills.cancel)
            safe(arm.stop)
        elif action == "go_to":
            if self.modes.drive:
                self.start_trip(target)
            else:
                log("  driving by voice is switched off (dashboard: Come when called)")
        elif action in ("move", "turn"):
            self.move_by(action, target)
        elif action == "arm":
            self.arm_pose(target)
        elif action in ("pick", "put", "move_object"):
            self.object_task(action, target, confirm=False)          # the LLM's words already confirmed it
        elif action == "fetch":                                      # parse the person's own words, never the LLM's
            self.fetch_request(getattr(self, "heard", "") or target)  # wording ("ap" must not become "apple")
        elif action in ("give", "place"):
            if self.fetch_status() == "holding":
                self.fetch_finish(action)

    def move_by(self, action, target):
        """'move forward 1' / 'move left 0.5' / 'turn around 180' / 'turn left 90', relative to where Lumi stands.
        Driven as a normal base move to a map point, so obstacles are avoided. Returns False if not possible."""
        if not self.modes.drive:
            log("  driving by voice is switched off (dashboard: Come when called)")
            return False
        parts = (target or "").split()
        direction = parts[0] if parts else "forward"
        try:
            amount = float(parts[1]) if len(parts) > 1 else (1.0 if action == "move" else 90.0)
        except ValueError:
            amount = 1.0 if action == "move" else 90.0
        pose = safe(agv.pose)
        if pose is None:
            return False
        x, y, th = pose
        if action == "turn":
            turn = math.radians({"left": 1, "right": -1}.get(direction, 1) * (180.0 if direction == "around" else amount))
            goal = (x, y, (th + turn + math.pi) % (2 * math.pi) - math.pi)
        else:
            amount = max(0.1, min(MAX_MOVE_M, amount))
            side = {"forward": 0.0, "back": math.pi, "left": math.pi / 2, "right": -math.pi / 2}.get(direction, 0.0)
            goal = (x + amount * math.cos(th + side), y + amount * math.sin(th + side), th)
        log(f"  {action} {direction} {amount:g} -> map ({goal[0]:.2f}, {goal[1]:.2f}, {math.degrees(goal[2]):.0f} deg)")
        self.start_trip(goal)
        return True

    def skill_busy(self):
        return (self.skill_thread is not None and self.skill_thread.is_alive()) or self.fetch_status() in ("running", "holding")

    # ---------- fetch tasks (tasks/fetch.py, docs/16) ----------
    @staticmethod
    def fetch_status():
        try:
            from tasks import fetch
            st = fetch.state()
        except Exception:                              # no runner yet, or its state file is being written
            return None
        # a stopped / failed task can still have the object in the hand: give / place must still work
        return "holding" if st.get("holding") and st.get("status") != "running" else st.get("status")

    def fetch_finish(self, how, on=None):
        """Give / place what the hand holds; a refusal ("I haven't learned how to hand things over yet") is spoken."""
        from tasks import fetch
        try:
            if how == "give":
                fetch.give(say=self.fetch_say)
            else:
                fetch.place(say=self.fetch_say, on=on)
        except fetch.FetchError as e:
            log(f"  fetch {how} refused: {e}")
            self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")

    def fetch_say(self, en, ko):
        """Spoken progress of the runner, in the language of the conversation."""
        mouth.say(en if self.lang == "en" else ko)

    def fetch_start(self, task):
        """Start a task; "here" becomes the robot's map pose now, so it does not move with the robot."""
        from tasks import fetch
        pose = safe(agv.pose)
        task = dict(task)
        for k in ("source", "dest"):
            if task.get(k) == "here" and pose:
                task[k] = dict(zip(("x", "y", "theta"), pose))
        log(f"  fetch start: {task}")
        try:
            fetch.start(task, say=self.fetch_say)
        except fetch.FetchError as e:
            log(f"  fetch refused: {e}")
            self.fetch_say(str(e), "죄송해요, 지금은 할 수 없어요.")
        self.keep_listening()

    def hear(self, wait_s):
        """One answer in a dialog: (text or None, understood)."""
        text = ears.listen(wait_s=wait_s, on_start=lambda: log("  hearing speech"))
        if not text or self.own_echo(text):
            return None, True
        ok = ears.understood()
        log(f"  answer: {text!r} [{ears.last_stt.get('language')}, confidence {ears.last_stt.get('logprob')}]")
        if ok:
            self.lang = ears.heard_lang(self.lang)
        return text, ok

    def fetch_request(self, text):
        """A fetch said by voice: parse strictly, ask what is missing, read back, start on yes or silence."""
        if not self.modes.drive:
            self.fetch_say("Sorry, driving is switched off.", "죄송해요, 지금은 이동할 수 없어요.")
            return
        status = self.fetch_status()
        if status == "holding":
            self.fetch_say("I'm holding something, where should I put it first?", "뭔가 들고 있어요. 먼저 어디에 둘까요?")
            return
        if status == "running":
            self.fetch_say("I'm still doing a task. Say stop to cancel it.", "아직 일하는 중이에요. 멈추려면 멈춰라고 하세요.")
            return
        from tasks import fetch
        task, problems = brain_mod.parse_fetch(text, self.markers)
        log(f"  fetch parsed: {task} problems {problems}")
        result = fetch_dialog.run(task, self.markers, self.hear, self.fetch_say, fetch.describe, self.fetch_start)
        log(f"  fetch dialog: {result}")
        self.keep_listening()

    def fetch_voice(self, text):
        """While a task runs or holds: stop / give / place / "thank you" while giving. True if handled."""
        status = self.fetch_status()
        if status not in ("running", "holding"):
            return False
        from tasks import fetch
        if FETCH_STOP.search(text):
            log("  fetch: stop by voice")
            safe(fetch.stop)
            self.act("stop", "")
            self.fetch_say("Okay, I stopped.", "네, 멈췄어요.")
        elif FETCH_THANKS.search(text) and fetch.state().get("step") == "giving":
            safe(fetch.release_now)                    # the person has taken it
        elif status == "holding" and not any(w in text.lower() for w in brain_mod.OBJECTS) and \
                (FETCH_GIVE.search(text) or FETCH_BRING_IT.search(text)):
            self.fetch_finish("give")                  # "bring it to me" while holding = hand it over
        elif (brain_mod.intent(text, self.markers) or ("",))[0] == "fetch":
            return False                               # a new fetch: fetch_request() answers it
        elif status == "holding" and FETCH_PLACE.search(text):
            self.fetch_finish("place")
        else:
            return False
        self.keep_listening()
        return True

    def object_task(self, action, target, confirm=True):
        """'pick white cup' / 'move_object cup' / 'put back|down' by voice. The skill runs in the background (up
        to a minute) while Lumi keeps listening, so "stop" ends it; the result or the reason is spoken."""
        en = self.lang == "en"
        if self.skill_busy():
            mouth.say("I'm still busy with my arm." if en else "아직 팔로 하는 일이 있어요.")
            return
        if action == "put":
            back = target == "back"
            said = ("Okay, putting it back.", "네, 제자리에 놓을게요.") if back else ("Okay, putting it down.", "네, 내려놓을게요.")
            done = ("Done.", "다 했어요.")
            run = lambda: skills.put_down(back=back)
        else:
            words = (target or "").lower().split()           # the LLM may write "the white cup"
            colour = next((brain_mod.COLOURS[w] for w in words if w in brain_mod.COLOURS and w != words[-1]), None)
            name = next((brain_mod.OBJECTS[w] for w in reversed(words) if w in brain_mod.OBJECTS), "cup")
            target = f"{colour} {name}" if colour else name
            if action == "pick":
                said, done = (f"Okay, I'll pick up the {target}.", "네, 집어 볼게요."), ("I've got it.", "잡았어요.")
                run = lambda: skills.pick(name, colour)
            else:
                said, done = (f"Okay, I'll move the {target}.", "네, 옮겨 볼게요."), ("Done.", "다 옮겼어요.")
                run = lambda: skills.move_object(name, colour)
        if confirm:
            mouth.say(said[0] if en else said[1])

        def work():
            try:
                run()
                mouth.say(done[0] if en else done[1])
            except skills.SkillError as e:
                log(f"  {action} {target}: {e}")
                mouth.say(str(e) if en else "죄송해요, 지금은 할 수 없어요.")
            except (motion.MotionError, ConnectionError, OSError) as e:
                log(f"  {action} {target} stopped: {e}")
                mouth.say("I stopped my arm." if en else "팔을 멈췄어요.")
        self.skill_thread = threading.Thread(target=work, daemon=True)
        self.skill_thread.start()
        self.keep_listening()

    def arm_pose(self, target):
        """'reach': the Cobo π program ARM_REACH_PROGRAM (record it once); 'fold': the folded drive pose;
        'open' / 'close': the gripper."""
        if target in ("open", "close"):
            st = safe(gripper.open_ if target == "open" else gripper.close)
            log(f"  gripper {target}: {st}")
            return st is not None
        if target == "fold":
            return safe(lambda: motion.go("tuck", wait=False)) is not None
        try:
            arm.start(ARM_REACH_PROGRAM)
            return True
        except Exception as e:
            log(f"  arm reach: {e} (record {ARM_REACH_PROGRAM} in Cobo pi)")
            return False

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
        log(f"dashboard: {cmd} {d.get('marker') or d.get('point') or d.get('markers') or ''}")
        if cmd == "go":
            self.start_trip(d["marker"])
        elif cmd == "go_point":
            self.start_trip(tuple(d["point"]))
        elif cmd == "route":
            self.start_trip(d["markers"], d.get("pause", 1.0))
        elif cmd == "cancel":
            if self.patrol:
                self.patrol.pause()
                self.patrol = None
            safe(agv.cancel)
        elif cmd in ("fetch", "fetch_give", "fetch_place", "fetch_stop", "fetch_carry", "fetch_release"):
            from tasks import fetch                      # dashboard tasks are confirmed there: no read-back
            if cmd == "fetch":
                try:
                    fetch.start(d["task"], say=self.fetch_say)
                except fetch.FetchError as e:
                    log(f"  fetch refused: {e}")
            elif cmd == "fetch_stop":
                safe(fetch.stop)
            elif cmd == "fetch_release":
                safe(fetch.release_now)
            elif cmd == "fetch_carry":
                try:
                    fetch.carry_to(d["dest"], d.get("then"), say=self.fetch_say, on=d.get("on"))
                except fetch.FetchError as e:
                    log(f"  carry refused: {e}")
            else:
                self.fetch_finish(cmd[6:], d.get("on"))
        elif cmd == "calibrate":
            self.calib_until = time.time() + CALIB_S if d.get("on", True) else 0.0
            self.calib_n = 0
            self.write_calib("collecting" if self.calib_until else "stopped")

    def start_trip(self, target, pause_s=0.0):
        """Drive to a marker, a map point or a list of markers in order; with patrol mode on, people in the
        way are greeted on the way."""
        if self.patrol:
            self.patrol.pause()
        self.patrol = Patrol(list(target) if isinstance(target, list) else [target], once=True, pause_s=pause_s)
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

    # ---------- interrupting Lumi while it talks (clip mic only) ----------
    def speak_abort(self):
        """Stop talking: the person left, someone new arrived, or the visitor interrupted ("stop", a new question)."""
        return self.interrupted() or self.barge_in()

    def barge_in(self):
        u = self.mic.next(0.0)
        if u is None:
            return False
        if not getattr(u, "during_speech", False) or u.seconds < 0.25:
            return False
        text = (ears.transcribe(u.mono) or "").strip()
        if not text or self.own_echo(text):
            return False
        if not ears.understood(BARGE_IN_LOGPROB):        # unclear while Lumi talks = mostly Lumi's own voice
            log(f"  ignored while talking (unclear): {text!r}")
            return False
        if brain_mod.is_closing(text):
            log(f"  interrupted: {text!r} - stop talking, listen")
            return True
        if len(text.split()) >= 2 or brain_mod.WAKE_WORD_RE.search(text):
            log(f"  interrupted by a new question: {text!r}")
            self.pending_text = text
            return True
        return False

    @staticmethod
    def own_echo(text):
        """The clip mic also hears Lumi: ignore what overlaps with what it just said."""
        said = set(re.findall(r"\w+", mouth.recent_speech().lower()))
        words = re.findall(r"\w+", text.lower())
        return bool(words) and sum(w in said for w in words) / len(words) >= 0.6

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
        threading.Thread(target=self.wave, daemon=True).start()   # wave and talk at the same time
        mouth.say(GREETING)                              # cached at start: plays at once

    def talk_turn(self):
        """Listen once; answer if something was said. Returns True if the visitor spoke."""
        if self.pending_text:                              # asked while Lumi was talking
            text, self.pending_text = self.pending_text, None
            self.answer(text)
            return True
        text, u = ears.listen(wait_s=4.0, on_start=lambda: log("  hearing speech"), abort=self.interrupted, full=True)
        if text and self.own_echo(text):                   # the clip mic heard Lumi's own greeting / reply
            log(f"  ignored own voice: {text!r}")
            text = None
        if not text and self.closing_pending and time.time() - self.closing_pending > CLOSING_WAIT_S:
            log("  silence after a closing word - conversation over")
            self.end_conversation("okay")
            return False
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
        """Current head yaw (deg), read from the body every 0.3 s (the torso camera does not know it)."""
        now = time.time()
        if now - self._yaw_time > 0.3:
            st = safe(head.status)
            if st:
                self._yaw, self._yaw_time = st[2], now
        return self._yaw

    def look_up(self, text, action, target, t0=None):
        """Weather or web facts -> short spoken answer (interruptible)."""
        en = self.lang == "en"
        mouth.say("Let me check." if en else "확인해 볼게요.")
        facts = web.weather(target) if action == "weather" else web.search(target)
        log(f"  {action} {target!r}: {(facts or 'NO INTERNET')[:120]}")
        if facts is None:
            mouth.say("Sorry, I'm not connected to the internet right now, so I can't look that up."
                      if en else "죄송해요, 지금은 인터넷에 연결되어 있지 않아서 찾아볼 수 없어요.")
        else:
            said = mouth.say_stream(self.brain.respond_from(text, facts), abort=self.speak_abort)
            log(f"lumi ({time.time() - (t0 or time.time()):.1f} s): {said}")
        if self.current is None:
            self.voice_until = time.time() + VOICE_SESSION_S

    def keep_listening(self):
        if self.current is None:
            self.voice_until = time.time() + VOICE_SESSION_S
        self.last_activity = time.time()

    def end_conversation(self, text=None):
        """Say a goodbye that fits the conversation, forget it, and drive on if Lumi was on the way."""
        bye = self.brain.farewell(text, self.lang)
        log(f"  goodbye: {bye}")
        mouth.say(bye, abort=self.speak_abort)
        self.current, self.voice_until, self.closing_pending = None, 0.0, None
        self.brain.reset()
        self.turn_head(0, 0)
        if self.traveling():
            log("  conversation over - driving on")
            self.patrol.wait_until = time.time() + 0.5

    def quick_command(self, text):
        """A command the keyword rules recognise for sure: confirm with a ready phrase and act, no LLM wait."""
        rule = brain_mod.intent(text, self.markers)
        if not rule or rule[0] not in ("go_to", "come", "quiet", "weather", "search", "move", "turn", "arm", "pick", "put",
                                       "move_object", "fetch"):
            return False
        action, target = rule
        en = self.lang == "en"
        log(f"  action {action} {target} (keyword rule)")
        if action in ("weather", "search"):                    # look it up at once, one LLM call for the answer
            self.look_up(text, action, target if action == "weather" else self.brain.search_query(target))
            return True
        self.brain.history.append((text, f"ACTION: {action} {target or '-'}"))
        if action == "quiet":
            mouth.say("Okay, I'll be quiet." if en else "네, 조용히 할게요.")
            self.quiet_until = time.time() + QUIET_S
            self.current, self.voice_until = None, 0.0
            self.turn_head(0, 0)
            return True
        if action in ("pick", "put", "move_object"):
            self.object_task(action, target)
            return True
        if action == "fetch":
            self.fetch_request(target)
            return True
        if not self.modes.drive:
            mouth.say("Sorry, driving is switched off." if en else "죄송해요, 지금은 이동할 수 없어요.")
            return True
        if action == "come":
            mouth.say("Okay, I'm coming." if en else "네, 갈게요.")
            self.come_to(self.current)
            return True
        if action in ("move", "turn"):
            d, n = (target.split() + ["", ""])[:2]
            if action == "turn":
                say_en = "Okay, turning around." if d == "around" else f"Okay, turning {d}."
                say_ko = "네, 뒤로 돌게요." if d == "around" else ("네, 왼쪽으로 돌게요." if d == "left" else "네, 오른쪽으로 돌게요.")
            else:
                say_en = f"Okay, moving {d} {n} metre{'s' if n not in ('1', '0.5') else ''}." if d != "back" \
                    else f"Okay, moving back {n} metre{'s' if n not in ('1', '0.5') else ''}."
                say_ko = {"forward": "앞으로", "back": "뒤로", "left": "왼쪽으로", "right": "오른쪽으로"}.get(d, "") + f" {n}미터 갈게요."
            if self.move_by(action, target):
                mouth.say(say_en if en else say_ko)
            return True
        if action == "arm":
            done = {"open": ("Okay, opening my hand.", "네, 손을 펼게요."), "close": ("Okay, closing my hand.", "네, 손을 쥘게요.")}
            if target in done:
                mouth.say(done[target][0] if en else done[target][1])
            if self.arm_pose(target):
                if target not in done:
                    mouth.say("Here you go." if en else "여기요.")
            else:
                mouth.say("Sorry, I haven't learned that arm movement yet." if en else "죄송해요, 그 팔 동작은 아직 못 배웠어요.")
            return True
        self.start_trip(target)                           # go_to: start driving, then say so
        name = "my charging dock" if target == "home" else target
        mouth.say(f"Okay, I'm going to {name}." if en else ("네, 충전소로 갈게요." if target == "home" else f"네, {target}로 갈게요."))
        self.current, self.voice_until = None, 0.0
        return True

    def answer(self, text):
        """Stream the LLM reply: act on the action line, speak sentence by sentence.
        Clear commands (go home, go to p1, come here, be quiet...) are done at once without the LLM."""
        self.lang = ears.heard_lang(mouth.lang_of(text))   # answer in the language just spoken
        brain_mod.FORCED_LANG["lang"] = self.lang
        self.heard = text                                  # what the person said, for a fetch the LLM recognised
        log(f"visitor #{self.current.id if self.current else 'voice'}: {text}  "
            f"[{ears.last_stt.get('language')}, confidence {ears.last_stt.get('logprob')}]")
        t = time.time()
        self.closing_pending = None
        if not ears.understood():                          # garbled or another language: ask, do not guess
            log("  not understood - asking again")
            mouth.say("Sorry, I didn't catch that. Could you say it again?" if self.lang == "en"
                      else "죄송해요, 잘 못 들었어요. 다시 말씀해 주시겠어요?")
            self.keep_listening()
            return
        if NAME_ONLY.match(text):                           # just "Lumi?": they want attention
            mouth.say("Yes?" if self.lang == "en" else "네?")
            self.keep_listening()
            return
        if self.fetch_voice(text):                         # before the closing words: "thank you" while giving
            return
        if brain_mod.is_closing(text):
            if FAREWELL_WORDS.search(text):                # "thanks", "bye", "see you": say goodbye, end the talk
                self.end_conversation(text)
            else:                                          # "okay", "got it": wait; silence after it ends the talk
                log("  closing word - waiting a moment")
                self.closing_pending = time.time()
                self.keep_listening()
            return
        if self.quick_command(text):
            log(f"  done at once ({time.time() - t:.1f} s)")
            return
        if self.brain.is_lookup_follow_up(text):           # "tell me more" about something looked up just now
            self.look_up(text, "search", self.brain.search_query(text), t)
            return
        gen = self.brain.respond_stream(text, self.markers)
        head_ = next(gen)
        log(f"  action {head_['action']} {head_['target']} ({time.time() - t:.1f} s)")
        if head_["action"] == "come":
            gen.close()
            mouth.say("Okay, I'm coming." if self.lang == "en" else "네, 갈게요.")
            self.come_to(self.current)
            return
        if head_["action"] in ("weather", "search"):
            gen.close()
            target = head_["target"] if head_["action"] == "weather" else self.brain.search_query(head_["target"])
            self.look_up(text, head_["action"], target, t)
            return
        if head_["action"] == "quiet":
            gen.close()
            mouth.say("Okay, I'll be quiet." if self.lang == "en" else "네, 조용히 할게요.")
            log(f"  quiet for {QUIET_S / 60:.0f} min (no greetings; \"Hi Lumi\" still works)")
            self.quiet_until = time.time() + QUIET_S
            self.current, self.voice_until = None, 0.0
            self.turn_head(0, 0)
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
        first = next(gen, None)
        if first and brain_mod.UNSURE.search(first) and head_["action"] in ("none", "sing"):
            gen.close()                                    # the model does not know: look it up instead
            log(f"  not sure ({first[:60]!r}) - looking it up")
            self.look_up(text, "search", self.brain.search_terms(text), t)
            return
        said = mouth.say_stream(itertools.chain([first] if first else [], timed()), abort=self.speak_abort)
        log(f"lumi ({time.time() - t:.1f} s): {said}")
        if head_["action"] in ("end", "go_to"):
            self.current, self.voice_until = None, 0.0     # stay quiet with this person until a new visit
        elif self.current is None:
            self.voice_until = time.time() + VOICE_SESSION_S

    # ---------- wake word ----------
    def check_wake(self):
        """Idle or driving: is someone calling "Lumi" / "Hi Lumi" / "Hey Lumi" (or just "Hi" / "Hey")? Handles it."""
        u = self.mic.next(0.0)
        if u is None or not (0.3 <= u.seconds <= WAKE_MAX_S) or getattr(u, "during_speech", False):
            return False
        text = ears.transcribe(u.mono)
        m = WAKE.search(text or "")
        if not m and HELLO_ONLY.match(text or ""):          # a plain "Hi!" / "Hey" said on its own
            m = HELLO_ONLY.match(text)
        if not m:
            if text:
                log(f"  heard {text!r} (no wake word)")
            return False
        rest = text[m.end():].strip(" ,.!?")
        lang = ears.heard_lang("ko" if re.search(r"[가-힣]", text) else "en")
        self.lang = lang
        cal = doa.load_calib()
        ang, conf, raw = doa.estimate(u.mics, cal)
        trusted = cal["fitted"] and conf >= DOA_MIN_CONF
        robot_angle = HEAD_SIGN * self.det_yaw() + ang
        self.voice_angle, self.voice_trusted = robot_angle, trusted
        log(f"WAKE {text!r}: voice at {robot_angle:+.0f} deg (confidence {conf:.2f}, "
            f"{'calibrated' if cal['fitted'] else 'NOT calibrated'})")
        if self.traveling():                                  # someone calls while driving: stop for them
            log("  called while driving - stop and talk, then drive on")
            self.patrol.pause()
        self.quiet_until = 0.0
        self.brain.reset()
        self.closing_pending = None
        command = rest if len(rest) > 2 else ""
        target = self.find_caller(robot_angle, trusted)
        if target is not None:
            target.greeted = True
            self.current = target
            self.turn_head(HEAD_SIGN * target.angle)
        if not command:                                       # just "Hi Lumi": a short answer, then listen
            mouth.say(WAKE_REPLY[lang])
        self.voice_until = time.time() + VOICE_SESSION_S
        self.last_activity, self.prompts = time.time(), 0
        if command:                                           # "Hi Lumi, go home": do it at once, no greeting
            self.answer(command)
        return True

    def find_caller(self, robot_angle, trusted):
        """The visible person who called (voice direction + camera). If the voice comes from outside what the
        camera can see (the head camera also by turning the head), turn the base toward it first, then look for
        the person in front."""
        if not self.vision:
            return None
        if not trusted:
            return self.vision.only_person() or self.vision.near_angle(0.0, 30)
        t = self.vision.near_angle(robot_angle, SPEAKER_MATCH_DEG)
        if t is not None:
            return t
        view = CAMERA_HALF_FOV + (head.YAW_LIMIT if self.vision.camera == "head" else 0.0)
        if abs(robot_angle) > view and self.modes.drive:
            log(f"  caller outside the camera ({robot_angle:+.0f} deg): turning toward the voice")
            self.turn_head(0)
            safe(agv.turn_by, math.radians(robot_angle))
            t0 = time.time()
            time.sleep(0.6)
            while time.time() - t0 < 8 and (safe(agv.status, default={}) or {}).get("move_status") == "running":
                time.sleep(0.2)
            time.sleep(0.8)                                   # let detection catch up
            self.voice_angle = 0.0
            return self.vision.near_angle(0.0, 35) or self.vision.only_person()
        self.turn_head(HEAD_SIGN * max(-head.YAW_LIMIT, min(head.YAW_LIMIT, robot_angle)))
        if self.vision.camera == "head":                      # the camera turned with the head: look again
            time.sleep(1.5)
            return self.vision.near_angle(robot_angle)
        return None

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
            track = self.find_caller(self.voice_angle, self.voice_trusted)   # look where the voice came from
            if track is None:
                mouth.say("I can't see you. Could you wave or step in front of me?" if self.lang == "en"
                          else "보이지 않아요. 손을 흔들거나 제 앞으로 와 주시겠어요?")
                return
            self.current = track
            track.greeted = True
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
        if not self.vision.pinned:                         # driving: the path ahead; standing: the people
            self.vision.prefer = "torso" if moving else "head"
        if time.time() < self.calib_until:
            self.vision.det.focus_angle = None
            self.calibrate_step()
            return
        if self.calib_until:
            self.calib_until = 0.0
            self.write_calib("finished")
        greet_now = (self.modes.patrol if moving else self.modes.greeter) and time.time() > self.quiet_until
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
                # often still there, out of the frame (beside the arm): keep listening without the wake word
                # for a while, like a conversation started by voice
                self.turn_head(0, 0)
                self.voice_until = time.time() + VOICE_SESSION_S
            self.last_activity, self.prompts = time.time(), 0
            return

        if self.current is None:
            if self.fetch_status() in ("running", "holding"):   # keep listening for stop / give / place / thanks
                self.voice_until = max(self.voice_until, time.time() + VOICE_SESSION_S)
            if time.time() < self.voice_until:            # talking with someone we only heard
                if self.talk_turn():
                    self.voice_until = max(self.voice_until, time.time() + VOICE_SESSION_S)
                return
            if self.voice_until:
                log("voice conversation over (silence)")
                self.end_conversation(None)
            if self.check_wake():                          # "Hi Lumi" works in every mode
                return
            if self.patrol:
                self.patrol.tick()
                if self.patrol and self.patrol.stuck:
                    target, self.patrol.stuck = self.patrol.stuck, None
                    name = "my charging dock" if target == "home" else target
                    mouth.say(f"Sorry, I can't find a way to {name}. Something may be blocking the path.")
            time.sleep(0.05)
            return

        if self.traveling() and time.time() - self.last_activity > PATROL_WAIT_S:
            log(f"no answer for {PATROL_WAIT_S:.0f} s - goodbye, drive on")
            self.end_conversation(None)
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
        web.keep_weather_fresh()
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
    # torso camera by default: the head camera shares a USB 2 hub with the speaker and drops out while Lumi talks
    ap.add_argument("--camera", default=None, choices=camview.CAMERAS,
                    help="pin one camera (default: head standing, torso driving)")
    ap.add_argument("--patrol", help="comma-separated markers to drive between, e.g. a,b")
    ap.add_argument("--once", action="store_true", help="drive the --patrol route once instead of looping")
    ap.add_argument("--pause", type=float, default=PAUSE_AT_END, help="seconds to wait at each marker")
    try:
        Lumi(ap.parse_args()).run()
    except KeyboardInterrupt:
        print("\nbye")
        os._exit(0)          # leave at once; the camera thread would otherwise abort noisily
