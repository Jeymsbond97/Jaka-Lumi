"""Lumi voice assistant: greets every visitor, talks with them and obeys voice commands.

    python lumi.py                 # full: camera, greetings, conversation, commands
    python lumi.py --no-camera     # no camera: press Enter to start a conversation (desk testing)
    python lumi.py --no-arm --no-drive     # no waving, no base driving
    python lumi.py --patrol aisle_a,aisle_b   # walk between markers; stop for people in the way, talk, go on

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
"""
import argparse
import collections
import itertools
import math
import os
import threading
import time

import agv
import arm
import ears
import head
import mouth
import speak
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
HEAD_SIGN = 1.0                    # +image angle -> +head yaw. VERIFY on the robot
LOOK = {"left": (40, None), "right": (-40, None), "center": (0, 0), "up": (None, 0), "down": (None, 20)}
# ^ yaw/pitch in degrees for "look" commands. VERIFY the signs: +yaw = robot's left?, +pitch = down?
PROMPT = {"en": "How can I help you?", "ko": "무엇을 도와드릴까요?"}
PATH_HALF_WIDTH = 0.4              # m to each side of the robot's centre line; on patrol only people in this
                                   # corridor are greeted (not people sitting at desks beside the aisle)
PATROL_WAIT_S = 8.0                # s; on patrol, after the greeting or the last answer, wait this long for speech
LOW_BATTERY, RESUME_BATTERY = 5, 60    # %
PAUSE_AT_END = 3.0                 # s to wait at each patrol point


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


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
        from person import PersonDetector
        self.det = PersonDetector(camera)
        self.tracks = []
        self.lock = threading.Lock()
        self.arm_watch = False

    def run(self):
        while True:
            color, people = self.det.read()
            if color is None:
                continue
            now = time.time()
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

    def nearest_greeted(self):
        with self.lock:
            here = [t for t in self.tracks if t.greeted and t.distance <= STAY_MAX]
        return min(here, key=lambda t: t.distance, default=None)


class Patrol:
    """Drive between markers in a loop; pause for people; go home to charge when the battery is low."""

    def __init__(self, route):
        self.route, self.i = route, 0
        self.mode = "patrol"             # patrol | going_home | charging
        self.moving = False              # a move that we started is running
        self.wait_until = 0.0
        self.last_poll = 0.0

    def pause(self):
        if self.moving:
            log("patrol paused")
            safe(agv.cancel)
            self.moving = False

    def tick(self):
        """Call often while nobody is being talked to; polls the base once a second."""
        now = time.time()
        if now - self.last_poll < 1.0:
            return
        self.last_poll = now
        st = safe(agv.status, default=None)
        if not st:
            return
        battery, ms = st.get("power_percent", 100), st.get("move_status")

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
                self.i = (self.i + 1) % len(self.route)
                self.wait_until = now + PAUSE_AT_END
            else:
                log(f"patrol move {ms} - retry in 5 s")
                self.wait_until = now + 5
            return
        if ms == "running" or now < self.wait_until:      # a voice "go to" is still driving, or waiting
            return
        ok, msg = safe(agv.go, self.route[self.i], default=(False, "error"))
        if ok:
            self.moving = True
            log(f"patrol -> {self.route[self.i]}")
        else:
            log(f"patrol cannot go to {self.route[self.i]}: {msg}")
            self.wait_until = now + 5


class Lumi:
    def __init__(self, args):
        self.a = args
        self.brain = Brain()
        self.markers = agv.markers()
        self.current = None              # the track we are talking with
        self.lang = "en"
        self.patrol = None
        if args.patrol:
            route = args.patrol.split(",")
            unknown = [m for m in route if m not in self.markers]
            if unknown:
                raise SystemExit(f"unknown markers {unknown}; markers on the map: {self.markers}")
            self.patrol = Patrol(route)
        if args.no_camera:
            self.vision = None
        elif args.patrol:
            self.vision = Vision(args.camera, PATROL_NEAR_MAX, PATH_HALF_WIDTH)
        else:
            self.vision = Vision(args.camera)
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
        if self.a.no_arm:
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
        elif action == "go_to" and not self.a.no_drive:
            log(f"drive to {target}: {safe(agv.go, target)}")

    # ---------- interrupts ----------
    def interrupted(self):
        """Stop listening/speaking: the person left, or a new person is waiting to be greeted."""
        if not self.vision:
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
        speak.play("sounds/hello.wav", wait=True)

    def talk_turn(self):
        """Listen once; answer if something was said. Returns True if the visitor spoke."""
        text = ears.listen(wait_s=4.0, on_start=lambda: log("  hearing speech"), abort=self.interrupted)
        if not text or self.interrupted():
            return False
        self.lang = mouth.lang_of(text)
        log(f"visitor #{self.current.id if self.current else '-'}: {text}")
        t = time.time()
        out = self.brain.respond(text, self.markers)
        log(f"lumi ({time.time() - t:.1f} s): {out['say']}  [{out['action']} {out['target']}]")
        if out["action"] not in ("none", "end"):
            self.act(out["action"], out["target"])
        mouth.say(out["say"], abort=self.interrupted)
        if out["action"] in ("end", "go_to") and self.current:
            self.current = None          # stay quiet with this person until a new visit
        return True

    def run_camera(self):
        self.last_activity, self.prompts = time.time(), 0
        while True:
            try:
                self.step()
            except Exception as e:                     # never stop the robot program on one error
                log(f"error: {e!r}")
                time.sleep(1)

    def step(self):
        """One pass of the camera behaviour (see the module docstring)."""
        new = self.vision.to_greet()
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
            if self.patrol:
                self.patrol.tick()
            time.sleep(0.1)
            return

        if self.patrol and time.time() - self.last_activity > PATROL_WAIT_S:
            log(f"no answer for {PATROL_WAIT_S:.0f} s - continue patrol")
            self.current = None
            self.turn_head(0, 0)
            return

        if self.talk_turn():
            self.last_activity, self.prompts = time.time(), 0
        elif (not self.interrupted() and time.time() - self.last_activity > PROMPT_S and self.prompts < MAX_PROMPTS):
            log(f"silent for {PROMPT_S:.0f} s - prompt")
            mouth.say(PROMPT[self.lang], abort=self.interrupted)
            self.last_activity, self.prompts = time.time(), self.prompts + 1

    def run_desk(self):
        while True:
            input("\nPress Enter to start a conversation (Ctrl+C to quit)...")
            self.brain.reset()
            self.current = None
            if self.wave():
                time.sleep(AUDIO_DELAY)
            speak.play("sounds/hello.wav", wait=True)
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
        ears.ensure_stt_server()
        mouth.warm_up()
        if self.vision:
            self.vision.start()
        log("ready")
        self.run_camera() if self.vision else self.run_desk()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-camera", action="store_true")
    ap.add_argument("--no-arm", action="store_true")
    ap.add_argument("--no-drive", action="store_true")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--patrol", help="comma-separated markers to drive between, e.g. aisle_a,aisle_b")
    try:
        Lumi(ap.parse_args()).run()
    except KeyboardInterrupt:
        print("\nbye")
        os._exit(0)          # leave at once; the camera thread would otherwise abort noisily
