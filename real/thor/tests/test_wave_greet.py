"""Self-check of the wave greeting (tasks/wave_greet.py) with a fake arm, head, waist and speech, no robot, and of the
waving detector (vision/waving.py) on the recordings of vision/wave_record.py when they are here (tests/data/waves,
local only: people in the pictures): python tests/test_wave_greet.py"""
import json
from pathlib import Path
import time

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from manipulation import arm_route, wave
from robot import head, motion
from tasks import fetch, wave_greet as g
from vision import waving

done = []                                           # what the robot did, in order
arm = {"at": "look"}
waver = {"w": None}                                 # (bearing, distance, look, face) of the person waving now
A, B = [1.0, 0.0, 1.0, 0.0], [0.0, 1.0, 0.0, 1.0]   # clothes signatures (vision/reid.py) of two people


def W(bearing, look=A):
    return (bearing, 2.0, look, None)
plan_error = {"e": None}
POSES = {"look": [0.0] * 6, "wave_out": [1.0] * 6, "wave_start": [2.0] * 6, "wave": [3.0] * 6}


def plan():
    if plan_error["e"]:
        raise plan_error["e"]
    return ([("wave_out", POSES["wave_out"]), ("wave_start", POSES["wave_start"])] if arm["at"] == "look" else [],
            [])


def move_path(moves, wait=True, queued=False):
    if moves[-1][0] == POSES["wave_start"] and len(moves) == 2 and queued:
        done.append("swing")
    else:
        done.append(f"up {moves[-1][1]}")
        arm["at"] = "wave_start"


def route_move(seq, speed=None, holding=False):
    done.append(f"down {speed}")
    arm["at"] = "look"


wave.plan = plan
motion.poses = lambda: dict(POSES)
motion.move_path = move_path
arm_route.where = lambda now=None: arm["at"]
arm_route.plan = lambda target, holding=False, leaf=False, now=None: [("wave_out", None), ("look", None)]
arm_route.move = route_move
head.status = lambda: [0.0, 0.0, 0.0, 10.0]
head.moveto = lambda pos, **k: done.append(f"head {pos[2]:+.0f}" + (" rest" if pos[3] == head.HEAD_REST_PITCH else "")
                                           + (" timeout" if k.get("timeout") != g.HEAD_TIMEOUT_S else ""))
fetch._waist_turn = lambda: 0.0
fetch._waist_to = lambda rel, in_place=False, look=None: done.append(f"waist {rel:+.0f} look {look}") or True
g._head_yaw = lambda: 0.0
g._too_close = lambda: False
g._waver = lambda: waver["w"]
said = []
g._say = lambda lines, lang: said.append(lines[0][lang])
switch = {"on": True, "free": True}
g._on, g._free = (lambda: switch["on"]), (lambda: switch["free"])
g._off = lambda: switch.update(on=False)
g._bg = lambda fn, *args: fn(*args)                # the background parts run at once here
queue = {"n": 0}                                    # moves the fake controller has queued
g.arm.cmd = lambda name, **k: {"queue": queue["n"]} if name == "get_motion_state" else {}
motion._wait = lambda *a, **k: done.append("settle")


def run(t0, t1, dt=0.5):
    t = t0
    while t <= t1:
        try:
            g.step(t)
        except Exception as e:                      # as _run
            g._stopped(e)
        t += dt


def fresh():
    done.clear()
    said.clear()
    arm["at"] = "look"
    g._st.update(up=False, last_wave=0.0, next_joke=0.0, free_at=0.0, refused_until=0.0, waist_out=False, follow_at=0.0, swing_at=0.0, swing_end=0.0)
    g._met.known.clear()
    switch.update(on=True, free=True)
    plan_error["e"] = None


# someone waves 30 deg on the left at 2 m: head to them, a greeting, arm up at the route speed, one swing, waist to them
fresh()
waver["w"] = W(30.0)
run(100.0, 100.0)
assert done == ["head +30", "up route", "swing", "waist +30 look 30.0"], done
assert len(said) == 1 and said[0] in sum(g.wave_lines.INTRO, ()), said        # someone new: Lumi introduces itself
assert g.busy()

# they keep waving: swings, and a joke after JOKE_AFTER_S, then not again before JOKE_EVERY_S
done.clear()
said.clear()
run(100.5, 100.0 + g.JOKE_AFTER_S + 1)
assert done.count("swing") >= g.JOKE_AFTER_S / g.SWING_S - 1 and "up route" not in done, done  # one per SWING_S
assert len(said) == 1 and said[0] in sum(g.wave_lines.LONG, ()), said

# they move to the other side while waving: the waist turns to them again between swings, not more often than
# FOLLOW_EVERY_S
done.clear()
waver["w"] = W(-40.0)
g._st["follow_at"] = 0.0                            # (the fake waver stays at +30 after each turn: turned again so far)
run(111.5, 111.5 + g.FOLLOW_EVERY_S - 0.5)
assert done[:2] == ["settle", "waist -40 look -40.0"] and done.count("waist -40 look -40.0") == 1, done  # swings end first
waver["w"] = W(30.0)

# never more than one swing queued ahead, even if the controller's queue always read empty
g._st["swing_end"], g._st["swing_at"] = 0.0, 0.0
done.clear()
for _ in range(10):
    g._swing_on(1000.0)
assert done.count("swing") == 1, done
g._st["swing_end"] -= g.SWING_S                     # it ended: the next is sent
g._swing_on(1000.0)
assert done.count("swing") == 2, done
g._st["swing_end"] = 0.0

# they stop: the hand stays up, no swings; waving again: swings again, no new greeting within NEW_WAVE_S
waver["w"] = None
done.clear()
run(112.0, 115.0)
assert done == [], done
waver["w"] = W(30.0)
said.clear()
run(115.5, 116.0)
assert done.count("swing") == 1 and said == [], (done, said)

# nobody waves for HOLD_S: arm down slowly, waist to the front, head to rest; not before
waver["w"] = None
done.clear()
run(116.5, 116.0 + g.HOLD_S - 1)
assert done == [], done
run(116.0 + g.HOLD_S + 0.5, 116.0 + g.HOLD_S + 0.5)
assert done == ["waist +0 look None", "down normal", "head +0 rest"], done
assert not g.busy() and arm["at"] == "look"

# the waist's way back is blocked: the arm still goes down; the waist is tried again every REFUSED_S while nobody waves
fresh()
waver["w"] = W(30.0)
run(150.0, 150.0)
waver["w"] = None
blocked = {"n": 1}
fetch._waist_to = lambda rel, in_place=False, look=None: done.append(f"waist {rel:+.0f}") or (
    blocked.update(n=blocked["n"] - 1) or False if blocked["n"] > 0 else True)
done.clear()
run(150.5 + g.HOLD_S, 150.5 + g.HOLD_S + g.REFUSED_S * 2.5)
assert done[:3] == ["waist +0", "down normal", "head +0 rest"] and done[3:] == ["waist +0"], done
fetch._waist_to = lambda rel, in_place=False, look=None: done.append(f"waist {rel:+.0f} look {look}") or True

# beside a wall the full waist turn is blocked: it turns as far as its sweep is clear, the head on the person
fresh()
waver["w"] = W(-66.0)
fetch._waist_to = lambda rel, in_place=False, look=None: done.append(f"waist {rel:+.0f} look {look}") or abs(rel) < 40
run(160.0, 160.0)
assert done[-3:] == ["waist -66 look -66.0", "waist -50 look -66.0", "waist -33 look -66.0"], done
fetch._waist_to = lambda rel, in_place=False, look=None: done.append(f"waist {rel:+.0f} look {look}") or True

# a wave nearly in front: only the head turns, the waist stays
fresh()
waver["w"] = W(5.0)
run(200.0, 200.0)
assert done == ["up route", "swing"], done                     # the head looks there already (within HEAD_MIN_DEG)

# the switch is turned off with the hand up: down at once
switch["on"] = False
done.clear()
run(200.5, 200.5)
assert done[:2] == ["waist +0 look None", "down normal"], done

# the arm stops (STOP, a person too close) during a swing: switched off, nothing moves after it
fresh()
waver["w"] = W(0.0)
run(300.0, 300.0)


def stopped(*a, **k):
    raise motion.MotionError("stopped")


motion.move_path = stopped
run(300.5, 300.5)
assert switch["on"] is False and not g.busy() and said[-1] in ("I stopped my arm.", "팔을 멈췄어요."), said
motion.move_path = move_path
done.clear()
run(301.0, 310.0)
assert done == [], done

# the arm refused (off, busy, something held): nothing moves, tried again after REFUSED_S only
fresh()
plan_error["e"] = wave.WaveError(*wave.OFF)
run(400.0, 400.0 + g.REFUSED_S - 1)
assert done == [] and switch["on"], done
plan_error["e"] = None
run(400.0 + g.REFUSED_S + 0.5, 400.0 + g.REFUSED_S + 0.5)
assert "up route" in done, done

# the assistant or a task has the robot: nothing moves
fresh()
switch["free"] = False
run(500.0, 505.0)
assert done == [] and not g.busy(), done

# a drive starts (lumi.waist_home) with the hand up mid-swing: the swings end, then the arm down before the drive
fresh()
waver["w"] = W(0.0)
run(550.0, 550.0)
g._st["swing_end"] = 1e12                           # a swing still queued
switch["free"] = False
run(550.5, 550.5)                                   # the drive took the robot: the wave greeting lets go
done.clear()
g._rest = lambda: 86.0                              # on the charger the waist rests turned; a drive still wants the front
g.lower()
assert done == ["settle", "waist +0 look None", "down normal", "head +0 rest"] and arm["at"] == "look", done
arm["at"] = "wave_start"                            # nobody waves any more on the charger: down to the waist's rest there
done.clear()
g._down()
assert done[:2] == ["waist +86 look None", "down normal"], done
g._rest = lambda: 0.0
done.clear()
g.lower()                                           # the hand is down: nothing moves
assert done == [], done

# nothing asked for a while on the charger (_idle): the hand goes up and stays up, no words; 2 swings every
# IDLE_WAVE_EVERY_S while nobody talks; a call stops them (the hand still up); a drive brings it down (lower); someone
# waving is greeted as always
fresh()
waver["w"] = None
g._idle, g._rest_arm = (lambda: True), (lambda: "look")
g._someone_within = lambda m: True                      # someone right by the arm: no idle wave, tried again later
g._st["idle_at"] = 0.0
run(690.0, 690.0)
assert done == [], done
g._someone_within = lambda m: False
arm["at"] = "rest"                                      # the arm still on its way to look on the charger: not yet
g._st["idle_at"] = 0.0
run(691.0, 691.0)
assert done == [], done
arm["at"] = "look"
g._st["idle_at"] = 700.0                                # the last idle wave
run(700.0, 700.0 + g.IDLE_WAVE_EVERY_S - 1)
assert done == [] and said == [], done                  # not before IDLE_WAVE_EVERY_S
run(700.0 + g.IDLE_WAVE_EVERY_S + 0.5, 700.0 + g.IDLE_WAVE_EVERY_S + 0.5)
assert done == ["up route"] + ["swing"] * g.IDLE_SWINGS and said == [] and g._st["up"] and g._st["held"], (done, said)
done.clear()
t = 700.0 + g.IDLE_WAVE_EVERY_S + 1
run(t, t + g.IDLE_WAVE_EVERY_S - 2)
assert done == [], done                                 # up, still, until the next swings
run(t + g.IDLE_WAVE_EVERY_S, t + g.IDLE_WAVE_EVERY_S + 200)
assert done.count("swing") >= 2 * 9 and "down normal" not in done and "up route" not in done, done   # never down
talk = {"on": True}                                     # someone talks to Lumi: no swings, the hand stays up, still
g._idle = lambda: not talk["on"]
done.clear()
run(1000.0, 1100.0)
assert done == [] and g._st["up"], done
talk["on"] = False                                      # quiet again: the swings go on
run(1101.0, 1102.0)
assert done == ["swing"] * g.IDLE_SWINGS, done
done.clear()
g.lower()                                               # a drive: down to the front first
assert "down normal" in done and not g._st["up"] and not g._st["held"], done
done.clear()                                            # the hand left up (its way down did not run): swings from there
arm["at"], g._st["idle_at"] = "wave_start", 0.0
run(1200.0, 1200.0)
assert done == ["swing"] * g.IDLE_SWINGS and g._st["held"], done
g.lower()
g._idle = lambda: True
done.clear()
said.clear()                                            # someone waves back during an idle wave: greeted as always,
real_waver, g._waver = g._waver, (lambda: W(20.0))      # the hand stays up and swings on
arm["at"], g._st["idle_at"], g._st["up"] = "look", 0.0, False
run(760.0, 760.0)
assert "up route" in done and "down normal" not in done and g._st["up"], done
run(760.5, 762.0)
assert said and said[0] in sum(g.wave_lines.INTRO + g.wave_lines.GREET, ()) and done.count("swing") >= 1, (done, said)
g._waver = real_waver
g._st["up"] = g._st["held"] = False
done.clear()
g._idle = lambda: False                                 # someone talks to Lumi, or off the charger: no idle waves
run(800.0, 900.0)
assert done == [], done
g._idle, g._rest_arm = (lambda: False), g.arm_route.rest_pose

# Lumi introduces itself once per person: the same person waving again (after NEW_WAVE_S) gets a hello, someone
# else an introduction, and the first person too once they were out of view for GONE_S
fresh()
waver["w"] = W(0.0)
run(600.0, 600.0)
waver["w"] = None
run(600.5, 600.0 + g.NEW_WAVE_S + 1)
waver["w"] = W(0.0)
run(607.0, 607.0)
waver["w"] = None
run(607.5, 607.0 + g.NEW_WAVE_S + 1)
waver["w"] = W(0.0, B)
run(614.0, 614.0)
assert [l in sum(g.wave_lines.INTRO, ()) for l in said] == [True, False, True], said
assert said[1] in sum(g.wave_lines.GREET, ()), said
for k in g._met.known:
    k.last_seen -= g.GONE_S + 1                     # both left the view
waver["w"] = None
run(614.5, 614.0 + g.NEW_WAVE_S + 1)
waver["w"] = W(0.0)
run(621.0, 621.0)
assert said[-1] in sum(g.wave_lines.INTRO, ()), said

# a loop patrol's wave for people passing: only with the hand up, someone within PASSER_M, nobody by the arm
near = {"m": None}
waver["w"] = None
g._someone_within = lambda m: near["m"] is not None and near["m"] < m
g._nearest = lambda m: 20.0 if near["m"] is not None and near["m"] < m else None
saved, arm["at"] = arm["at"], "wave_start"
done.clear()
assert not g.passer_wave() and not done              # nobody there
near["m"] = 0.5
assert not g.passer_wave() and not done              # someone right by the arm
near["m"] = 2.0
assert g.passer_wave() and done.count("swing") == g.IDLE_SWINGS
time.sleep(0.2)                                      # the head turns in the background
assert "head +20" in done and done[-1] == "head +0"  # to them, then ahead again for the drive
arm["at"], near["m"] = "look", 2.0
assert not g.passer_wave()                           # the hand is not up
arm["at"] = saved
done.clear()

# a hand at the head (scratching, a phone at the ear) is not a raised hand; the same hand held out to the side is
import numpy as np                                  # noqa: E402
import cv2                                          # noqa: E402
kp = np.zeros((17, 3))
for name, xy in (("nose", (640, 200)), ("left_eye", (650, 190)), ("right_eye", (630, 190)), ("left_shoulder", (700, 320)),
                 ("right_shoulder", (580, 320)), ("right_elbow", (560, 260)), ("right_wrist", (600, 210))):
    kp[g.pose.K[name]] = (*xy, 1.0)
assert waving._hand(kp) is None                     # palm at (620, 185): beside the eye
kp[g.pose.K["right_wrist"]] = (480, 200, 1.0)
kp[g.pose.K["right_elbow"]] = (520, 280, 1.0)
assert waving._hand(kp) is not None                 # palm at (460, 160): out to the side

# the detector on the recordings: every wave found, nothing else ever counts as waving
DATA = Path(__file__).parent / "data" / "waves"
if DATA.exists():
    for f in sorted(p for p in DATA.iterdir() if p.is_dir()):
        r = waving.run_recording(f)
        seen = [any(w) for _, w in r]
        if f.name.startswith("no_"):
            assert not any(seen), f.name
        else:
            first = next(t - r[0][0] for (t, _), s in zip(r, seen) if s)
            assert first < 2.0, (f.name, first)                # found within 2 s
            if f.name != "pause_2m":                           # (it stops waving half way)
                assert sum(seen) > 0.75 * len(seen), (f.name, sum(seen), len(seen))
    for name in ("right_3m", "left_3m"):                       # the same waves shrunk to 10 m: still found
        w, n, hit, k = waving.Watcher(), 0, 0, 3 / 10
        for line in open(DATA / f"{name}.jsonl"):
            d = json.loads(line)
            g = cv2.imread(str(DATA / name / f"{d['n']:04d}.jpg"), cv2.IMREAD_GRAYSCALE)
            far = np.full_like(g, 128)
            small = cv2.resize(g, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            far[:small.shape[0], :small.shape[1]] = small
            n += 1
            hit += any(v for _, v in w.update(d["t"], far, [{**p, "kp": np.array(p["kp"]) * [k, k, 1]}
                                                            for p in d["people"]]))
        assert hit > 0.75 * n, (name, hit, n)
    r = waving.run_recording(DATA / "pause_2m")                # stopped at ~6 s: no longer waving 2.5 s later
    assert not any(any(w) for t, w in r if t - r[0][0] > 8.5)
else:
    print("(no recordings here: detector not checked)")

print("wave greeting: ok")
