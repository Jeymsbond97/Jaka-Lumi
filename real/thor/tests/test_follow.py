"""Self-check of "follow me" (tasks/follow.py, the hooks in assistant/lumi.py, brain.intent) with a fake base and
fake person tracks, no robot, no network: python tests/test_follow.py"""
import math
import re
import tempfile
import threading
import time
import types
from pathlib import Path

import numpy as np

from assistant import brain, lumi
from robot import agv, head, motion
from tasks import fetch, follow

lumi.LOG_FILE = "/dev/null"                         # keep the assistant's real log clean
tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"           # never the real /dev/shm file
follow.TICK_S = 0.02
follow.FOLLOW_MAX_MS = 0.5                       # the walks below are checked at the full clamp (joy_control 0.5)
M = ["home", "p1", "p3"]


def forbid(*a, **k):
    raise AssertionError("a test reached the robot")


fetch.motion.go = fetch.skills._ask = motion._ready = forbid
fetch._charging = lambda: False
fetch._at_pose = lambda name: True                  # the arm is in look already
fetch._pose = lambda name, speed=None: None
fetch._waist_front = lambda: None
fetch.head_ahead = lambda: None
fetch.arm_yaw = lambda: -86.0
ARM = [np.array([0.44, 0.0]), np.array([0.52, 0.0]), np.array([0.60, 0.0])]   # flange, grasp point, tips (m)
fetch.arm_points = lambda: ARM


class Body:
    """The body API behind robot/head.py: [lift, waist, yaw, pitch]; a moveto takes MOVE_S; overlaps are counted."""
    MOVE_S = 0.05

    def __init__(self):
        self.pos, self.moves, self.busy, self.overlaps = [50.0, 0.0, 0.0, 0.0], [], 0, 0
        self.lock = threading.Lock()
        head._call = self.call

    def call(self, path, body=None, timeout=2):
        if path == "status":
            return [{"enable": True, "pos": p} for p in self.pos]
        if path != "moveto":
            forbid()
        with self.lock:
            self.busy += 1
            self.overlaps += self.busy > 1
        time.sleep(self.MOVE_S)
        with self.lock:
            self.busy -= 1
            self.pos = list(body["pos"])
            self.moves.append((time.time(), threading.current_thread().name, *self.pos))
        return {"code": 0}


body = Body()
HALF_FOV = 47.0                                     # deg; the head camera's half view (vision/person.py COLOR_HFOV / 2)


class World:
    """The base drives by the joy commands it gets (each lasts 0.5 s); a person walks; obstacles are points."""

    def __init__(self, person=(3.0, 0.0), walk=(0.0, 0.0), walk_s=0.0, obstacles=(), path=None, fov=False):
        self.x = self.y = self.th = 0.0
        self.v = self.w = 0.0
        self.t = self.t_cmd = self.t0 = time.time()
        self.person, self.walk, self.walk_s, self.obstacles = np.array(person, float), np.array(walk), walk_s, obstacles
        self.hidden = False
        self.path, self.fov = path, fov             # path(t): the person's (x, y); fov: seen only by the head camera
        self.cmds, self.dist = [], []
        self.lock = threading.Lock()
        agv.request = self.request
        agv.pose = self.pose
        agv.clearance = self.clearance

    def _move(self):
        now = time.time()
        dt = max(0.0, min(now, self.t_cmd + 0.5) - self.t)  # a command lasts 0.5 s
        self.x += self.v * math.cos(self.th) * dt
        self.y += self.v * math.sin(self.th) * dt
        self.th += self.w * dt
        self.t = now

    def request(self, cmd):
        m = re.match(r"/api/joy_control\?linear_velocity=(-?[\d.]+)&angular_velocity=(-?[\d.]+)$", cmd)
        if not m:
            forbid()
        with self.lock:
            self._move()
            self.v, self.w = float(m.group(1)), float(m.group(2))
            self.t_cmd = time.time()
            self.cmds.append((self.t_cmd, self.v, self.w))
        return {"status": "OK"}

    def pose(self):
        with self.lock:
            self._move()
            return self.x, self.y, self.th

    def clearance(self, x, y):
        return min((math.hypot(x - ox, y - oy) for ox, oy in self.obstacles), default=float("inf"))

    def person_at(self):
        if self.path:
            return np.array(self.path(time.time() - self.t0))
        return self.person + self.walk * min(time.time() - self.t0, self.walk_s)

    def see(self):
        """What lumi.Vision.follow_view gives: (distance, angle deg + left, age s, look)."""
        if self.hidden:
            return None
        d, a = self.sight(self.person_at())
        self.dist.append(d)
        if self.fov and abs(a - body.pos[2]) > HALF_FOV:
            return None
        return d, a, 0.0, self.look

    look = None

    def sight(self, p):
        """(distance, angle deg + left) of the map point p from the base now."""
        x, y, th = self.pose()
        a = (math.degrees(math.atan2(p[1] - y, p[0] - x) - th) + 180) % 360 - 180
        return math.hypot(p[0] - x, p[1] - y), a


said = []


def say(en, ko):
    said.append(en)


def wait_end(s=3.0):
    t = time.time()
    while follow.running() and time.time() - t < s:
        time.sleep(0.01)
    return not follow.running()


# follows a person walking away, at most FOLLOW_MAX_MS, never inside the gap, turns toward them
MAX_MS, follow.FOLLOW_MAX_MS = follow.FOLLOW_MAX_MS, 0.4                              # a lower cap: reached and kept
w = World(person=(2.2, 0.4), walk=(0.3, 0.05), walk_s=2.0)
follow.start(w.see, say)
time.sleep(6.0)
assert follow.running()
assert follow.stop() and wait_end(0.5)
vs, ws = [c[1] for c in w.cmds], [c[2] for c in w.cmds]
assert max(vs) <= follow.FOLLOW_MAX_MS + 1e-9 and max(vs) > 0.85 * follow.FOLLOW_MAX_MS, max(vs)          # capped, and it got there
assert max(abs(x) for x in ws) <= follow.TURN_MAX_RS + 1e-9
assert min(vs) >= 0.0                                                               # never backwards
assert min(w.dist) >= follow.FOLLOW_GAP_M, min(w.dist)                              # never closer than the gap
assert w.dist[-1] < follow.FOLLOW_GAP_M + 0.15, w.dist[-1]                          # caught up and stands
assert w.y > 0.1 and abs(w.see()[1]) < follow.TURN_DEAD_DEG + 1.0, (w.y, w.see())  # turned toward them
assert w.cmds[-1][1:] == (0.0, 0.0)
print(f"follow: ok (drove {w.x:.2f}, {w.y:.2f} m, top {max(vs):.2f} m/s, nearest {min(w.dist):.2f} m)")
follow.FOLLOW_MAX_MS = MAX_MS

# closer than NEAR_STOP_M: stands still (no forward, no turn)
w = World(person=(0.6, 0.3))
follow.start(w.see, say)
time.sleep(0.5)
follow.stop()
assert wait_end(0.5) and all(c[1:] == (0.0, 0.0) for c in w.cmds) and abs(w.x) < 1e-9
print("too close: stands still")

# every stop word ends it at once (lumi.follow_stop, as answer() calls it); then "follow me" starts again
L = lumi.Lumi.__new__(lumi.Lumi)
stops = []
L.stop_all = lambda: stops.append(1)
STOP = ["stop", "Stop!", "enough", "that's enough", "wait", "wait, Lumi", "stay here", "you can stop", "hold on",
        "don't follow me", "stop following me", "멈춰", "그만", "그만해", "거기 있어", "기다려", "여기 있어", "스톱", "정지", "서"]
for word in STOP:
    w = World(person=(3.0, 0.0))
    follow.start(w.see, say)
    time.sleep(0.15)
    assert follow.running(), word
    t_stop = time.time()
    assert L.follow_stop(word), word
    assert wait_end(0.3), word
    assert w.cmds[-1][1:] == (0.0, 0.0) and all(c[1:] == (0.0, 0.0) for c in w.cmds if c[0] >= t_stop), word
    assert stops and stops.pop() == 1
for text in ("follow me", "go on", "keep going", "stay with me", "this way", "faster", "어디 가?"):
    assert not follow.stop_word(text), text
assert not L.follow_stop("stop")                                                    # not following: the old paths
print(f"stop words: {len(STOP)} ok")

# restarts on "follow me" again, also while following (the old loop ends first)
w = World(person=(3.0, 0.0))
follow.start(w.see, say)
time.sleep(0.2)
first = follow._thread
follow.start(w.see, say)
assert not first.is_alive() and follow.running()
time.sleep(0.3)
assert any(c[1] > 0 for c in w.cmds)
follow.stop()
assert wait_end(0.5)
print("restart: ok")

# lost: no sighting -> drives on toward where they were for COAST_S, slows to 0, after LOST_S "I lost you"
said.clear()
w = World(person=(3.0, 0.0))
follow.start(w.see, say)
time.sleep(0.3)
w.hidden, t_lost = True, time.time()
assert wait_end(follow.LOST_S + 1.0)
assert said == [follow.LOST[0]], said
after = [c[1] for c in w.cmds if c[0] > t_lost + follow.COAST_S + 0.05]
assert w.cmds[-1][1:] == (0.0, 0.0) and after and all(b <= a + 1e-9 for a, b in zip(after, after[1:])), after
t_still = t_lost + follow.COAST_S + follow.FOLLOW_MAX_MS / follow.DECEL_MS2 + 0.1
assert all(c[1:] == (0.0, 0.0) for c in w.cmds if c[0] > t_still)
print("lost: ok")

# a stale sighting stands still, then counts as lost
said.clear()
w = World(person=(3.0, 0.0))
t_old = time.time() - follow.STALE_S - 0.1
follow.start(lambda: (3.0, 0.0, time.time() - t_old, None), say)
assert wait_end(follow.LOST_S + 1.0) and said == [follow.LOST[0]] and all(c[1:] == (0.0, 0.0) for c in w.cmds)
print("stale: ok")

# something in the way: stops before the arm or the base gets there
said.clear()
w = World(person=(3.0, 0.0), obstacles=[(1.5, 0.0)])
follow.start(w.see, say)
assert wait_end(4.0 + follow.BLOCKED_END_S)
assert said == ["Something is in my way, so I stopped."], said
assert 0.3 < w.x and w.x + ARM[-1][0] < 1.5 - 0.05 and w.cmds[-1][1:] == (0.0, 0.0), w.x
print(f"obstacle: stopped at {w.x:.2f} m (finger tips {1.5 - w.x - ARM[-1][0]:.2f} m before it)")

# on the charger: refused, said, the base never driven
said.clear()
fetch._charging = lambda: True
w = World()
follow.start(w.see, say)
assert wait_end(1.0) and said and "charger" in said[0] and all(c[1:] == (0.0, 0.0) for c in w.cmds)
fetch._charging = lambda: False
print("charger: refused")

# the arm switched off: follows with the arm still, in look or not; powered off (joints 0): refused, never driven
def arm_off():
    raise motion.MotionError("arm is not powered / enabled")


motion._ready = arm_off
assert follow.ready() is None
said.clear()
w = World(person=(3.0, 0.0))
follow.start(w.see, say)
time.sleep(0.4)
assert follow.running() and any(c[1] > 0 for c in w.cmds)
follow.stop()
assert wait_end(0.5)
fetch._at_pose = lambda name: False
real_joints, fetch.skills._joints = fetch.skills._joints, lambda: [5.0] * 6
assert follow.ready() is None
fetch.skills._joints = lambda: [0.0] * 6
assert follow.ready() == fetch.ARM_UNSEEN
said.clear()
w = World()
follow.start(w.see, say)
assert wait_end(1.0) and said == [fetch.ARM_UNSEEN[0]] and all(c[1:] == (0.0, 0.0) for c in w.cmds), said
fetch.skills._joints = real_joints
motion._ready = lambda: (_ for _ in ()).throw(motion.MotionError("a Cobo π program is running"))
assert follow.ready() == follow.ARM_BUSY
fetch._at_pose = lambda name: (_ for _ in ()).throw(ConnectionError("no answer"))
assert follow.ready() == follow.NO_ARM
fetch._at_pose, motion._ready = (lambda name: True), forbid
print("arm off: follows, powered off refuses")

# any other failure in prepare: said, the base at 0, the head free again, the thread ends
said.clear()
fetch._waist_front = lambda: 1 / 0
w = World()
follow.start(w.see, say)
assert wait_end(1.0) and said and "went wrong" in said[0] and w.cmds and w.cmds[-1][1:] == (0.0, 0.0), said
assert head.owners == ()
fetch._waist_front = lambda: None
print("failure in prepare: said, stopped")

# the person walks around to behind (radius 2 m, 0 -> 150 deg in 6 s), seen by the head camera only: the head turns
# first, the base after, the head comes back toward 0; head moves one at a time, toward the person
said.clear()
body.moves.clear()
R = 2.0
w = World(path=lambda t: (R * math.cos(math.radians(min(t, 6.0) * 25)), R * math.sin(math.radians(min(t, 6.0) * 25))),
          fov=True)
follow.start(w.see, say)
time.sleep(9.0)
assert follow.running() and not said, said
follow.stop()
assert wait_end(0.5)
yaws = [m[4] for m in body.moves if m[1] == "follow head"]
assert body.overlaps == 0 and len(yaws) >= 3, (body.overlaps, len(yaws))
assert max(yaws) > 20.0 and min(yaws) >= -follow.HEAD_STEP_DEG, yaws                                  # left, toward them
assert abs(yaws[-1]) < 15.0, yaws[-1]                                                                      # back toward 0
assert math.degrees(w.th) > 120.0 and all(m[5] == follow.HEAD_PITCH for m in body.moves), math.degrees(w.th)
print(f"walk behind: head up to {max(yaws):.0f} deg, base turned {math.degrees(w.th):.0f} deg, {len(yaws)} head moves")

# live 2026-10-21: "follow me" from a person at 0.54 m, -80 deg, the head turned to them; prepare() turned the head
# ahead, they were out of its view, the track was dropped: "lost" before a single move. The head must stay on them.
said.clear()
fetch.head_ahead = lambda: head.moveto([*head.status()[:2], *fetch.HEAD_AHEAD])   # as the real one: the body moves
body.pos[2] = -75.0                                                                 # lumi turned the head to them
w = World(path=lambda t: (math.cos(math.radians(-75)) * (0.6 + 0.4 * min(t, 4.0)),
                          math.sin(math.radians(-75)) * (0.6 + 0.4 * min(t, 4.0))), fov=True)
follow.start(w.see, say)
time.sleep(6.0)
assert follow.running() and not said, said
follow.stop()
assert wait_end(0.5)
assert any(c[2] < 0 for c in w.cmds) and math.degrees(w.th) < -30.0, math.degrees(w.th)     # turned toward them
fetch.head_ahead, body.pos[2] = (lambda: None), 0.0
print(f"follow me from aside: kept in view, base turned {math.degrees(w.th):.0f} deg")

# while following only follow moves the head (lumi's turn_head, sing are skipped)
w = World(person=(3.0, 0.0))
follow.start(w.see, say)
time.sleep(0.2)
n = len(body.moves)
assert head.moveto([50, 0, -60, 0]) is None and len(body.moves) == n
follow.stop()
assert wait_end(0.5) and head.owners == ()
print("head owned while following")

# re-lock: the track is lost but a person appears at about the same place -> followed on; somewhere else -> lost
said.clear()
w, gone, fresh = World(person=(3.0, 0.0)), [False], []
follow.start(lambda: None if gone[0] else w.see(), say, people=lambda: fresh)
time.sleep(0.3)
gone[0] = True                                                                      # the track id is dropped
time.sleep(0.5)
fresh.append((w.see, 3.0, 8.0, 0.0, None))                                                # a new track where they were
t_new = time.time()
time.sleep(follow.LOST_S + 0.5)
assert follow.running() and not said, said
assert any(c[0] > t_new and c[1] > 0 for c in w.cmds)
follow.stop()
assert wait_end(0.5)
said.clear()
w = World(person=(3.0, 0.0))
fresh = [(lambda: (3.0, 80.0, 0.0, None), 3.0, 80.0, 0.0, None)]
follow.start(lambda: None if w.hidden else w.see(), say, people=lambda: fresh)
time.sleep(0.3)
w.hidden = True
assert wait_end(follow.LOST_S + 1.0) and said == [follow.LOST[0]], said
print("re-lock: ok")


def missing(world, every=1.0, gap=0.5):
    """world.see as Vision gives it with frames missed: for `gap` s of every `every` s the last sighting gets older."""
    last = [None, 0.0]

    def see():
        t = time.time() - world.t0
        if t % every < every - gap or last[0] is None:
            last[:] = [world.see(), time.time()]
            return last[0]
        d, a, _, look = last[0]
        return d, a, time.time() - last[1], look
    return see


def steady(cmds, t_from, t_to):
    """Forward speeds sent between t_from and t_to (s after the start) and the biggest change from one to the next."""
    t0 = cmds[0][0]
    vs = [c[1] for c in cmds if t_from <= c[0] - t0 <= t_to]
    return vs, max((abs(b - a) for a, b in zip(vs, vs[1:])), default=0.0)


step = max(follow.ACCEL_MS2, follow.DECEL_MS2) * follow.TICK_S + 1e-6

# walks away at 0.45 m/s with half the frames missed: drives on smoothly (no stop-and-go), keeps up
said.clear()
w = World(person=(2.0, 0.0), walk=(0.45, 0.0), walk_s=6.0)
follow.start(missing(w), say)
time.sleep(6.0)
assert follow.running() and not said, said
follow.stop()
assert wait_end(0.5)
vs, jump = steady(w.cmds, 1.5, 5.8)
assert min(vs) > 0.2 and jump <= step, (min(vs), jump)                               # never stopped, smooth
assert w.dist[-1] < 2.0 + 0.2, w.dist[-1]                                            # did not fall behind
print(f"walk away, frames missed: {min(vs):.2f}-{max(vs):.2f} m/s, gap {w.dist[-1]:.2f} m")

# walks faster than the base (1.2 m/s for 2 s), then stops: full speed, never lost, slows smoothly, stops at the gap
said.clear()
w = World(person=(1.5, 0.0), walk=(1.2, 0.0), walk_s=2.0)
follow.start(w.see, say)
time.sleep(9.0)
assert follow.running() and not said, said
follow.stop()
assert wait_end(0.5)
vs, jump = steady(w.cmds, 0.0, 9.0)
assert max(vs) >= follow.FOLLOW_MAX_MS - 1e-6 and jump <= step + 0.03, (max(vs), jump)   # the last cm/s at the gap: 0
assert min(w.dist) >= follow.FOLLOW_GAP_M - 0.02 and w.dist[-1] < follow.FOLLOW_GAP_M + 0.2, (min(w.dist), w.dist[-1])
print(f"faster than the base, then stops: top {max(vs):.2f} m/s, nearest {min(w.dist):.2f} m, stood at {w.dist[-1]:.2f} m")

# walks a curve (a quarter circle of 2.5 m to the left at 0.4 m/s): turns with them, stays close behind
said.clear()
R = 2.5
w = World(path=lambda t: (R * math.sin(min(t, 9.0) * 0.16), R - R * math.cos(min(t, 9.0) * 0.16) + 0.0 * t))
w.path0 = w.path
w.path = lambda t: (1.5 + w.path0(t)[0], w.path0(t)[1])
follow.start(w.see, say)
time.sleep(11.0)
assert follow.running() and not said, said
follow.stop()
assert wait_end(0.5)
assert math.degrees(w.th) > 45.0 and w.dist[-1] < follow.FOLLOW_GAP_M + 0.3, (math.degrees(w.th), w.dist[-1])
print(f"curve: base turned {math.degrees(w.th):.0f} deg, gap {w.dist[-1]:.2f} m")

# another person crosses between: the followed track jumps onto them (Vision matched them), the followed person gets a
# fresh track: the jump is not taken, Lumi re-locks onto the right one and follows them on
said.clear()
A = lambda t: (2.0 + 0.3 * min(t, 6.0), 0.0)                                       # the followed person
B = lambda t: (1.7, 1.5 - 1.0 * t)                                                  # crosses in front, 1 m/s
w = World(path=A)
stolen = 1.2                                                                        # s; from here the track is B's


def followed():
    t = time.time() - w.t0
    if t < stolen:
        return w.see()
    return (*w.sight(B(t)), 0.0, None)


def everyone():
    t = time.time() - w.t0
    a = (lambda: w.see()) if t >= stolen + 0.1 else None                            # A's new track, a frame later
    return [(followed, *followed())] + ([(a, *a())] if a else [])


follow.start(followed, say, people=everyone)
time.sleep(6.0)
assert follow.running() and not said, said
follow.stop()
assert wait_end(0.5)
t_end = time.time() - w.t0
assert abs(w.y) < 0.15 and w.dist[-1] < follow.FOLLOW_GAP_M + 0.4, (w.y, w.dist[-1])                  # followed A
assert math.hypot(*(np.array(B(t_end)) - (w.x, w.y))) > 2.0
print(f"another person crossing: stayed with them (y {w.y:+.2f} m, gap {w.dist[-1]:.2f} m)")

# re-lock by clothes: someone where the person should be, in clearly other clothes, is not taken
n = len(lumi.reid.PARTS) * (lumi.reid.H_BINS * lumi.reid.S_BINS + lumi.reid.V_BINS) // len(lumi.reid.PARTS)
red, blue = np.zeros(2 * n), np.zeros(2 * n)
red[[0, n]], blue[[20, n + 20]] = 1.0, 1.0
p = follow.Person()
p.seen(np.array([3.0, 0.0]), time.time())
cand = [(lambda: None, 3.0, 2.0, 0.0, list(blue))]
gone = lambda: None
assert follow._pick(gone, None, lambda: cand, p, (0.0, 0.0, 0.0), list(red), time.time()) == (gone, None)
assert follow._pick(gone, None, lambda: cand, p, (0.0, 0.0, 0.0), list(blue), time.time())[1][:2] == (3.0, 2.0)
assert follow._pick(gone, None, lambda: cand, p, (0.0, 0.0, 0.0), None, time.time())[1] is not None
print("re-lock by clothes: ok")

# walks slowly (0.2 m/s): the base goes as slowly, ~1 m behind, no stop-and-go
said.clear()
w = World(person=(1.5, 0.0), walk=(0.2, 0.0), walk_s=10.0)
follow.start(w.see, say)
time.sleep(8.0)
assert follow.running() and not said, said
follow.stop()
assert wait_end(0.5)
vs, jump = steady(w.cmds, 4.0, 7.8)
assert 0.12 < min(vs) and max(vs) < 0.3 and jump <= step, (min(vs), max(vs), jump)
assert abs(w.dist[-1] - follow.FOLLOW_GAP_M) < 0.25, w.dist[-1]
print(f"slow walk: {min(vs):.2f}-{max(vs):.2f} m/s, gap {w.dist[-1]:.2f} m")

# walks past the robot's side to behind it (1.2 m/s, 1.0 m to the left), head camera only: the head stays on them
# past 90 deg, the base turns on the spot toward them (sweep checked) and follows again; never "lost"
said.clear()
body.moves.clear()
turn_max, follow.TURN_MAX_RS = follow.TURN_MAX_RS, 0.25                                 # a base slower than the head
w = World(path=lambda t: (2.0 - 1.4 * min(t, 3.0), 1.0), fov=True)
follow.start(w.see, say)
time.sleep(14.0)
follow.TURN_MAX_RS = turn_max
assert follow.running() and not said, said
follow.stop()
assert wait_end(0.5)
yaws = [m[4] for m in body.moves if m[1] == "follow head"]
assert max(yaws) > 90.0 and all(abs(y) <= 180.0 for y in yaws), yaws                    # past the side
assert all(abs(b - a) < 90.0 for a, b in zip(yaws, yaws[1:])), yaws                     # never swung round
assert math.degrees(w.th) > 120.0 and w.dist[-1] < follow.FOLLOW_GAP_M + 0.4, (math.degrees(w.th), w.dist[-1])
print(f"past the side to behind: head up to {max(yaws):.0f} deg, base turned {math.degrees(w.th):.0f} deg, "
      f"gap {w.dist[-1]:.2f} m")

# right behind: the angle flips between +179 and -179; the head and the base keep one side
said.clear()
body.moves.clear()
flip = [0]


def behind():
    flip[0] += 1
    return 2.0, 179.0 if flip[0] % 2 else -179.0, 0.0, None


follow.start(behind, say)
time.sleep(0.6)
follow.stop()
assert wait_end(0.5)
yaws = [m[4] for m in body.moves if m[1] == "follow head"]
assert yaws and all(y > 0 for y in yaws[1:]), yaws
print("right behind: one side")

# lumi: act("stop") ends following; follow_me locks onto the person talking, refuses when it must
lumi.agv.cancel = lumi.skills.cancel = lumi.arm.stop = lambda: None
w = World(person=(3.0, 0.0))
follow.start(w.see, say)
time.sleep(0.1)
L.act("stop", "")
assert wait_end(0.3)

spoken, started = [], []
lumi.mouth.say = lambda text, **k: spoken.append(text)
real_start = follow.start
follow.start = lambda see, say=None, people=None: started.append(see)
track = types.SimpleNamespace(id=7, distance=1.8, angle=10.0, greeted=False, history=[1.7], last_seen=time.time(),
                              look=None)
L.lang, L.voice_angle, L.voice_trusted = "en", 0.0, False
L.modes = types.SimpleNamespace(drive=True, patrol=True)
L.skill_busy = lambda: False
L.keep_listening = lambda: None
L.fetch_say = lambda en, ko: spoken.append(en)
L.vision = lumi.Vision.__new__(lumi.Vision)
L.vision.tracks, L.vision.lock = [track], threading.Lock()
L.current = track
L.find_caller = lambda angle, trusted: None
L.follow_me()
assert started and "follow you" in spoken[-1], spoken
d, a, age, look = started[-1]()
assert (d, a) == (1.7, 10.0) and age < 1.0                                          # the nearer of median / newest
L.vision.tracks = []
assert started[-1]() is None                                                        # track gone: lost
L.current, started[:] = None, []
L.follow_me()
assert not started and "can't see you" in spoken[-1]
L.find_caller = lambda angle, trusted: track                                       # where the voice came from
L.follow_me()
assert started and L.current is track
started.clear()
L.modes.drive = False
L.follow_me()
assert not started and "switched off" in spoken[-1]
L.modes.drive, L.skill_busy = True, lambda: True
L.follow_me()
assert not started and "on a task" in spoken[-1]
L.skill_busy, real_ready = (lambda: False), follow.ready
follow.ready = lambda: fetch.ARM_UNSEEN                                              # checked before "Okay"
L.follow_me()
assert not started and spoken[-1] == fetch.ARM_UNSEEN[0] and not any("follow you" in x for x in spoken[-1:])
follow.ready = real_ready
follow.start = real_start
print("lumi hooks: ok")

# the keyword rules: any wording EN / KO is "follow", talk about following is not
FOLLOW = ["follow me", "Follow me, please.", "Lumi, follow me", "hey lumi follow me", "can you follow me?",
          "please follow me", "follow me to p3", "come with me", "Come with me please", "walk with me",
          "come along", "따라와", "따라와 줘", "나 따라와", "같이 가자", "루미야 따라와", "저 따라오세요",
          "저 좀 따라와 주시겠어요?", "나랑 같이 가자", "같이 가요"]
NOT = ["follow me on instagram", "You should follow me on Instagram!", "I follow you", "I follow you on twitter",
       "do you follow me?", "did you follow me?", "don't follow me", "따라오지 마", "how do you follow people?",
       "I'm following the news", "come here", "come to me", "p3로 같이 가자"]
for text in FOLLOW:
    assert brain.intent(text, M) == ("follow", ""), (text, brain.intent(text, M))
    assert lumi.read_mission(text, M) is None, text                                  # not a mission of steps
for text in NOT:
    assert (brain.intent(text, M) or ("",))[0] != "follow", (text, brain.intent(text, M))
assert brain.intent("stop following me", M) == ("stop", "")
for text, want in (("can you tag along?", "follow"), ("I follow you on twitter", "none"),
                   ("I like walking", "none"), ("follow me", "follow")):
    got = brain.Brain._action("ACTION: follow -", text, M)["action"]                 # the LLM's line, checked
    assert got == want, (text, got)
print(f"intents: {len(FOLLOW)} follow, {len(NOT)} not")

# quick_command answers "follow me" at once
called = []
L.follow_me = lambda: called.append(1)
L.mission_running = lambda: False
L.brain, L.markers = types.SimpleNamespace(history=[]), M
assert L.quick_command("follow me") and called
# the speed law (live 2026-10-23: capped at 0.3 m/s the base fell 4 m behind a person walking 0.6-0.75 m/s)
def settle(d, walk, v=0.0, n=60):
    for _ in range(n):
        v = follow.speeds(d, 0.0, v, 0.0, walk, dt=0.1)[0]
    return v


assert follow.FOLLOW_MAX_MS == 0.5                                        # joy_control's own clamp (docs/05)
assert settle(1.8, 0.7) == follow.FOLLOW_MAX_MS                            # far behind a walker: full speed
assert abs(settle(1.5, 0.0) - 0.4) < 1e-6                                  # standing 0.5 m beyond the gap: gentle
assert settle(1.1, 0.0) < 0.1 and settle(1.0, 0.5) == 0.0                  # near the gap: slow; at it: none
assert settle(1.3, -0.4, v=0.4) == 0.0                                     # coming back toward the base: slows
vs = [settle(1.0 + r, 0.3) for r in (0.1, 0.3, 0.6, 1.0)]
assert vs == sorted(vs) and vs[-1] == follow.FOLLOW_MAX_MS, vs             # faster the further behind
v, prev = 0.0, []                                                          # speeds up and eases back gradually
for d in [3.0] * 20 + [1.2] * 20:
    prev.append(v)
    v = follow.speeds(d, 0.0, v, 0.0, 0.0, dt=0.1)[0]
steps = [b - a for a, b in zip(prev, prev[1:])]
assert max(steps) <= follow.ACCEL_MS2 * 0.1 + 1e-9 and min(steps) >= -follow.DECEL_MS2 * 0.1 - 1e-9, steps

# never into the person: they walk at 0.5 m/s and stop dead; the base sees them REACT_S late (walking estimate
# filtered as Person does) and must still stand before NEAR_STOP_M
gap, v, walk, t, seen = follow.FOLLOW_GAP_M + 0.1, 0.0, 0.0, 0.0, []
for k in range(300):                                                      # 0.1 s ticks
    t = k * 0.1
    pw = 0.5 if t < 15.0 else 0.0
    seen.append((gap, pw))
    lag = seen[max(0, len(seen) - 1 - round(follow.REACT_S / 0.1))]
    walk += (lag[1] - walk) * 0.1 / (follow.VEL_TAU_S + 0.1)
    v = follow.speeds(lag[0], 0.0, v, 0.0, walk, dt=0.1)[0]
    gap += (pw - v) * 0.1
    assert gap > follow.NEAR_STOP_M, (t, gap, v)
    if 10.0 < t < 15.0:
        assert v > 0.45, (t, v)                                            # keeps up with a 0.5 m/s walk
assert v == 0.0 and gap < follow.FOLLOW_GAP_M + 0.2, (v, gap)

print("all follow checks passed")
