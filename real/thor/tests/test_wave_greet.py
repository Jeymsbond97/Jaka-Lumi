"""Self-check of the wave greeting (tasks/wave_greet.py) with a fake arm, head, waist and speech, no robot, and of the
waving detector (vision/waving.py) on the recordings of vision/wave_record.py when they are here (tests/data/waves,
local only: people in the pictures): python tests/test_wave_greet.py"""
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from manipulation import arm_route, wave
from robot import head, motion
from tasks import fetch, wave_greet as g
from vision import waving

done = []                                           # what the robot did, in order
arm = {"at": "look"}
waver = {"w": None}                                 # (bearing, distance) of the person waving now
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
    g._st.update(up=False, last_wave=0.0, next_joke=0.0, free_at=0.0, refused_until=0.0, waist_out=False, follow_at=0.0)
    switch.update(on=True, free=True)
    plan_error["e"] = None


# someone waves 30 deg on the left at 2 m: head to them, a greeting, arm up at the route speed, one swing, waist to them
fresh()
waver["w"] = (30.0, 2.0)
run(100.0, 100.0)
assert done == ["head +30", "up route", "swing", "waist +30 look 30.0"], done
assert len(said) == 1 and said[0] in sum(g.wave_lines.GREET, ()), said
assert g.busy()

# they keep waving: swings, and a joke after JOKE_AFTER_S, then not again before JOKE_EVERY_S
done.clear()
said.clear()
run(100.5, 100.0 + g.JOKE_AFTER_S + 1)
assert done.count("swing") >= 10 and "up route" not in done, done
assert len(said) == 1 and said[0] in sum(g.wave_lines.LONG, ()), said

# they move to the other side while waving: the waist turns to them again between swings, not more often than
# FOLLOW_EVERY_S
done.clear()
waver["w"] = (-40.0, 2.0)
g._st["follow_at"] = 0.0                            # (the fake waver stays at +30 after each turn: turned again so far)
run(111.5, 111.5 + g.FOLLOW_EVERY_S - 0.5)
assert done[0] == "waist -40 look -40.0" and done.count("waist -40 look -40.0") == 1, done
waver["w"] = (30.0, 2.0)

# they stop: the hand stays up, no swings; waving again: swings again, no new greeting within NEW_WAVE_S
waver["w"] = None
done.clear()
run(112.0, 115.0)
assert done == [], done
waver["w"] = (30.0, 2.0)
said.clear()
run(115.5, 116.0)
assert done.count("swing") == 2 and said == [], (done, said)

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
waver["w"] = (30.0, 2.0)
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
waver["w"] = (-66.0, 2.0)
fetch._waist_to = lambda rel, in_place=False, look=None: done.append(f"waist {rel:+.0f} look {look}") or abs(rel) < 40
run(160.0, 160.0)
assert done[-3:] == ["waist -66 look -66.0", "waist -50 look -66.0", "waist -33 look -66.0"], done
fetch._waist_to = lambda rel, in_place=False, look=None: done.append(f"waist {rel:+.0f} look {look}") or True

# a wave nearly in front: only the head turns, the waist stays
fresh()
waver["w"] = (5.0, 1.5)
run(200.0, 200.0)
assert done == ["up route", "swing"], done                     # the head looks there already (within HEAD_MIN_DEG)

# the switch is turned off with the hand up: down at once
switch["on"] = False
done.clear()
run(200.5, 200.5)
assert done[:2] == ["waist +0 look None", "down normal"], done

# the arm stops (STOP, a person too close) during a swing: switched off, nothing moves after it
fresh()
waver["w"] = (0.0, 2.0)
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

# a hand at the head (scratching, a phone at the ear) is not a raised hand; the same hand held out to the side is
import numpy as np                                  # noqa: E402
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
    r = waving.run_recording(DATA / "pause_2m")                # stopped at ~6 s: no longer waving 2.5 s later
    assert not any(any(w) for t, w in r if t - r[0][0] > 8.5)
else:
    print("(no recordings here: detector not checked)")

print("wave greeting: ok")
