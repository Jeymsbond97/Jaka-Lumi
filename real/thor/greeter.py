"""Greeter: when a person stands in front of Lumi, turn the head to them, say hello and wave.

    python greeter.py --dry-run          # camera + detection only, prints what it WOULD do (nothing moves)
    python greeter.py --no-arm           # head + voice, no arm
    python greeter.py                    # everything
    options: --camera 0

Trigger: the nearest person is between NEAR_MIN and NEAR_MAX metres for HOLD_S seconds.
Wave, voice and head turn start together (voice delayed by AUDIO_DELAY to match the arm's start-up).
Safety: the arm only starts when nobody is closer than TOO_CLOSE, and is stopped if someone comes closer.
After a greeting it waits COOLDOWN_S; when nobody has been near for RETURN_S, the head goes back to 0.
"""
import argparse
import threading
import time

import arm
import head
import speak
from person import PersonDetector

NEAR_MIN, NEAR_MAX = 0.5, 1.2      # m, greeting zone: someone who walks up to about 1 m
TOO_CLOSE = 0.45                   # m, the wave is stopped if anyone comes this close
HOLD_S = 0.7                       # s the person must stay in the zone
AUDIO_DELAY = 0.3                  # s after play_program before the voice starts (arm start-up lag); tune
COOLDOWN_S = 15.0                  # s between greetings
RETURN_S = 5.0                     # s without anyone near before the head returns to 0
HEAD_SIGN = 1.0                    # +angle (person on the image's left) -> +head yaw. VERIFY on the robot


class Greeter:
    def __init__(self, dry_run, use_arm, use_head):
        self.dry, self.use_arm, self.use_head = dry_run, use_arm, use_head
        self.head_busy = False
        self.arm_running = False
        self.head_turned = False

    def log(self, msg):
        print(time.strftime("%H:%M:%S"), msg, flush=True)

    def turn_head(self, yaw):
        """Move the head in a background thread so the camera loop keeps running."""
        if not self.use_head or self.head_busy:
            return
        self.log(f"head -> {yaw:+.0f} deg" + ("  (dry run)" if self.dry else ""))
        if self.dry:
            return
        self.head_busy = True

        def run():
            try:
                head.turn(yaw)
            except Exception as e:
                self.log(f"head error: {e}")
            finally:
                self.head_busy = False
        threading.Thread(target=run, daemon=True).start()

    def greet(self, person):
        """Start the wave, the voice and the head turn together."""
        self.log(f"GREET person at {person['distance_m']} m, {person['angle_deg']:+.0f} deg"
                 + ("  (dry run: nothing moves or plays)" if self.dry else ""))
        delay = 0.0
        if self.use_arm and not self.dry:
            if arm.ready():
                arm.start()                       # returns at once; the arm starts moving shortly after
                self.arm_running = True
                delay = AUDIO_DELAY
            else:
                self.log("arm not ready (power/enable off or a program is running) - no wave")
        if not self.dry:
            threading.Timer(delay, speak.play, args=("sounds/hello.wav",)).start()
        self.turn_head(HEAD_SIGN * person["angle_deg"])
        self.head_turned = True

    def run(self, camera):
        det = PersonDetector(camera)
        self.log(f"camera {camera} (SN {det.serial}) running. Zone {NEAR_MIN}-{NEAR_MAX} m. Ctrl+C to stop.")
        in_zone_since, last_greet, last_near = None, 0.0, 0.0
        try:
            while True:
                color, people = det.read()
                if color is None:
                    continue
                now = time.time()
                known = [p for p in people if p["distance_m"] is not None]
                nearest = known[0] if known else None
                d = nearest["distance_m"] if nearest else None

                # safety: stop the wave if someone gets too close
                if self.arm_running:
                    if d is not None and d < TOO_CLOSE:
                        self.log(f"person at {d} m - STOP arm")
                        arm.stop()
                        self.arm_running = False
                    elif arm.program_state() == "idle":
                        self.arm_running = False
                        self.log("wave finished")

                if d is not None and d < NEAR_MAX + 0.5:
                    last_near = now

                in_zone = d is not None and NEAR_MIN <= d <= NEAR_MAX
                in_zone_since = (in_zone_since or now) if in_zone else None
                ready = (in_zone_since and now - in_zone_since >= HOLD_S and now - last_greet >= COOLDOWN_S
                         and not self.arm_running)
                if ready:                          # in_zone already means d >= NEAR_MIN > TOO_CLOSE
                    self.greet(nearest)
                    last_greet = now
                    in_zone_since = None

                if self.head_turned and now - last_near > RETURN_S and not self.arm_running:
                    self.turn_head(0.0)
                    self.head_turned = False
        except KeyboardInterrupt:
            self.log("stopping")
        finally:
            if self.arm_running and not self.dry:
                arm.stop()
            det.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="nothing moves, nothing plays")
    ap.add_argument("--no-arm", action="store_true")
    ap.add_argument("--no-head", action="store_true")
    ap.add_argument("--camera", type=int, default=0)
    a = ap.parse_args()
    Greeter(a.dry_run, not a.no_arm, not a.no_head).run(a.camera)
