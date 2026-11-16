"""Self-check of the owner's mode rules of 2026-11-16 (second round): the hand is up whenever Wave alone is on and always
on the charger; with Greeter or Patrol a drive goes in look, lowered slowly; with Greeter / Patrol and Wave together Lumi
only answers people who wave (stops, raises the hand, waves, lowers it, drives on), no waves at everyone, no keep alive;
a blocked drive is said aloud and the same place is tried again; Welcome only on the charger. Fake state, no robot:
python tests/test_mode_rules.py"""
import json
import tempfile
import time
import types
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from fastapi import HTTPException

from api import server
from assistant import lumi
from manipulation import arm_route, wave
from tasks import fetch, wave_greet as g

tmp = Path(tempfile.mkdtemp())
server.MODES_FILE = tmp / "lumi_modes.json"
lumi.MODES_FILE = str(server.MODES_FILE)


def modes(**kw):
    server.MODES_FILE.write_text(json.dumps({"greeter": False, "patrol": False, "wave_greet": False, "welcome": False, **kw}))


# Wave alone, or Wave with Greeter / Patrol
modes(wave_greet=True)
assert lumi.wave_only()
modes(wave_greet=True, greeter=True)
assert not lumi.wave_only()
modes(patrol=True)
assert not lumi.wave_only()

# drives: Wave alone stops for people passing and keep alive; with Patrol too only for someone waving, whose wave is
# answered with the hand raised and lowered again
order, real = [], (g.passer_due, g._waver, g.keep_alive_due)
lumi.agv.status = lambda: {"move_status": "running", "power_percent": 90}
lumi.agv.dock_marker = lambda: "home"
g.passer_due, g.keep_alive_due = (lambda: True), (lambda now=None: True)


def drive(hand_up, waving):
    g._waver = lambda: (10.0, 2.0, None, None) if waving else None
    P = lumi.Patrol(["p1", "p2"])
    P.moving, P.hand_up = True, hand_up
    P.pause = lambda: order.append("pause")
    P.passer_wave = lambda: order.append("passer")
    P.keep_alive = lambda: order.append("keep")
    P.answer_waver = lambda: order.append("answer")
    order.clear()
    P.tick(force=True)
    if P.waving:
        P.waving.join(1.0)
    return list(order)


modes(wave_greet=True)
assert drive(True, False) == ["pause", "passer"], order
modes(wave_greet=True, patrol=True)
assert drive(False, False) == [], order             # nobody waving: drives on, no waves at people, no keep alive
assert drive(False, True) == ["pause", "answer"], order
modes(patrol=True)
assert drive(False, True) == [], order              # Wave off: no waving at all
g.passer_due, g._waver, g.keep_alive_due = real

# the hand for a drive: up only with Wave alone
g._on = lambda: True
modes(wave_greet=True, greeter=True)
assert not lumi.wave_only()
g._drive_on = lumi.wave_only
g.arm_route.where = lambda now=None: "look"
assert g.raise_for_drive() is False
g._drive_on = None

# answering someone who waves on a drive: up, swings while they wave (at least GREET_SWINGS), down slowly to look
done = []
g._waver = lambda: (15.0, 2.0, None, None) if len([d for d in done if d == "swing"]) < 4 else None
g._someone_within = lambda m: False
pose = {"at": "look"}
g.arm_route.where = lambda now=None: pose["at"]
wave.plan = lambda: ([("wave_start", None)], [])
g._up = lambda route: done.append("up") or pose.update(at="wave_start")
g._swing = lambda: done.append("swing")
g._head_to = lambda b: done.append(f"head {b:+.0f}")
g._turn_head = lambda yaw, pitch=None: done.append(f"head {yaw:+.0f}")
g._down = lambda waist=None, arm_to=None, speed=None: done.append(f"down {arm_to} {speed}")
fetch.drive_arm = lambda: "look"
assert g.answer_waver(speed="slow")
assert done[:2] == ["up", "head +15"] and done.count("swing") == 4 and done[-1] == "down look slow", done
done.clear()
g._waver = lambda: None
assert not g.answer_waver(speed="slow") and done == []   # nobody waving any more: nothing

# a hand up comes down slowly before a drive with Greeter / Patrol (lower passes the speed on)
done.clear()
g._quiet = lambda wait_s: None
pose["at"] = "wave_start"
g.lower(speed="slow")
assert done == ["down look slow"], done

# on the charger the arm rests in wave_start (with or without Welcome), slowly, from look or its rest
moved = []
lumi.on_charger = lambda: True
fetch.state = lambda: {"status": "idle"}
fetch._stop.clear = lambda: None
pose["at"] = "look"
lumi.arm_route.where = lambda now=None: pose["at"]
fetch._at_pose = lambda name: name == pose["at"]
lumi.arm_route.plan = lambda target, holding=False, leaf=False, now=None: [target]
lumi.arm_route.move = lambda seq, speed=None, holding=False: moved.append((seq[-1], speed)) or pose.update(at=seq[-1])
fetch._waist_to = lambda rel, in_place=False, look=None: True
assert lumi.waist_home_rest("test")
assert moved == [(wave.START, lumi.HOME_ARM_SPEED)], moved
moved.clear()
assert lumi.waist_home_rest("again") and moved == [], moved   # already up: stays

# a blocked drive: said aloud (also with only Wave on) and the same place tried again
lumi.agv.status = lambda: {"move_status": "running", "power_percent": 90, "current_pose": {"x": 1.0, "y": 1.0, "theta": 0.0}}
for route, once, wave_on, done_after in ((["p1", "p2"], False, False, False), (["p3"], True, True, False),
                                         (["p3"], True, False, True)):
    modes(wave_greet=wave_on, patrol=not wave_on)
    P = lumi.Patrol(route, once=once)
    P.moving, P.i = True, 0
    P.progress = ((1.0, 1.0, 0.0), time.time() - lumi.STUCK_DRIVE_S - 1)
    lumi.agv.cancel = lambda: None
    P.tick(force=True)
    assert P.stuck == route[0] and P.i == 0 and (P.mode == "done") == done_after, (route, P.mode, P.i)
said = []
real_say, lumi.mouth.say = lumi.mouth.say, (lambda text, **k: said.append(text))
modes(wave_greet=True)
me = types.SimpleNamespace(modes=types.SimpleNamespace(greeter=False, patrol=False, wave_greet=True, welcome=False),
                           lang="en", patrol=types.SimpleNamespace(stuck="p3", stuck_why=None, once=False))
lumi.Lumi.say_stuck(me)
assert said and "blocking" in said[0], said
lumi.mouth.say = real_say

# Welcome only on the charger
server.assistant_pids = lambda: [1]
server.start_assistant = lambda *a, **k: None
server._calib_active = lambda: False
modes()
server.agv.status = lambda: {"charge_state": False, "move_status": "idle"}
try:
    server.modes_set(server.ModesBody(welcome=True))
    raise AssertionError("Welcome switched on off the charger")
except HTTPException as e:
    assert e.status_code == 409 and e.detail == server.WELCOME_OFF_CHARGER, e.detail
server.agv.status = lambda: {"charge_state": True, "move_status": "idle"}
assert server.modes_set(server.ModesBody(welcome=True))["welcome"]
assert server.modes_set(server.ModesBody(welcome=False))["welcome"] is False   # off is always allowed

print("ok: mode rules")
