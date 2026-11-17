"""Self-check of the safety fixes for the four modes (review of 2026-11-16): a stop switches Wave and Welcome off, so
nothing raises the arm by itself again; the swings of a drive wait for the base to stand; a new drive waits for them;
keep alive does not stop the base again and again; held swings end when someone comes close; the last switch off
lowers the hand before lumi.py stops. Fake state, no robot: python tests/test_modes_safety.py"""
import json
import tempfile
import threading
import time
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test

from api import server
from assistant import lumi
from tasks import wave_greet as g

tmp = Path(tempfile.mkdtemp())
server.MODES_FILE = tmp / "lumi_modes.json"
lumi.MODES_FILE = str(server.MODES_FILE)

# C1: an arm stop switches both Wave and Welcome off (through the API, as the dashboard does)
sent = []
real_open = lumi.urllib.request.urlopen
lumi.urllib.request.urlopen = lambda req, timeout=5: sent.append(json.loads(req.data)) or type("R", (), {"close": lambda s: None})()
lumi.wave_greet_off()
assert sent == [{"wave_greet": False, "welcome": False}], sent
lumi.urllib.request.urlopen = real_open

# C2: STOP switches Wave and Welcome off (the supervisor must not bring lumi.py back to raise the arm); Greeter and
# Patrol keep their switches as before
server.MODES_FILE.write_text(json.dumps({"greeter": True, "patrol": False, "wave_greet": True, "welcome": True}))
server.jogger.stop = server._route.stop = lambda: None
server.part = lambda fn, *a, **k: None
server.assistant_stop = lambda **k: {"stopped": []}
server.stop_all()
assert server.read_modes() == {"greeter": True, "patrol": False, "wave_greet": False, "welcome": False}, server.read_modes()
assert not server.any_on({**server.read_modes(), "greeter": False})

# I1: a drive's swings wait for the base to stand; a base that does not stop: no swings
states = iter(["running", "running", "idle"])
lumi.agv.status = lambda: {"move_status": next(states, "idle")}
assert lumi.base_stopped(timeout=2.0, every=0.01)
lumi.agv.status = lambda: {"move_status": "running"}
assert not lumi.base_stopped(timeout=0.1, every=0.01)
swung = []
real_keep, real_passer = g.keep_alive_wave, g.passer_wave
g.keep_alive_wave = lambda: swung.append("keep") or True
g.passer_wave = lambda: swung.append("passer") or True
lumi.BASE_STOP_WAIT_S = 0.1
P = lumi.Patrol(["p1", "p2"])
P.keep_alive()
P.passer_wave()
assert swung == [], swung                            # the base never stopped
lumi.agv.status = lambda: {"move_status": "idle"}
P.keep_alive()
P.passer_wave()
assert swung == ["keep", "passer"], swung

# I3: keep alive that could not swing starts the quiet count again (no stop every 2 s); keep alive waits wave_after
g.keep_alive_wave = lambda: False
g._st["any_wave"] = 0.0
P.keep_alive()
assert time.time() - g._st["any_wave"] < 5, g._st["any_wave"]
g.keep_alive_wave, g.passer_wave = real_keep, real_passer
order = []
lumi.agv.status = lambda: {"move_status": "running", "power_percent": 90}
real_on, real_due, real_waver, real_kad = lumi.wave_greet_on, g.passer_due, g._waver, g.keep_alive_due
real_only, lumi.wave_only = lumi.wave_only, (lambda: True)   # Wave alone (keep alive only then)
lumi.wave_greet_on, g.passer_due, g._waver, g.keep_alive_due = (lambda: True), (lambda: False), (lambda: False), \
    (lambda now=None: True)
P = lumi.Patrol(["p1", "p2"])
P.moving, P.hand_up, P.wave_after = True, True, time.time() + 60
P.pause = lambda: order.append("pause")
P.tick(force=True)
assert order == [], order                            # keep alive due, but a stop was just made: not yet
P.wave_after = 0.0
P.keep_alive = lambda: None
P.tick(force=True)
assert order == ["pause"], order
lumi.wave_greet_on, g.passer_due, g._waver, g.keep_alive_due = real_on, real_due, real_waver, real_kad
lumi.wave_only = real_only

# I2: a new drive waits while a drive's swings still run (the arm must be still when the base moves)
went = []
lumi.arm_route.where = lambda now=None: "look"      # never the real arm controller or base
lumi.agv.dock_marker = lambda: "home"
lumi.agv.status = lambda: {"move_status": "idle", "power_percent": 90}
lumi.agv.go = lambda m: went.append(m) or (True, "OK")
real_home, lumi.waist_home = lumi.waist_home, (lambda why, fold=False: True)
with g._drive_wave:
    assert g.drive_wave_busy()
    P = lumi.Patrol(["p3"], once=True)
    P.tick(force=True)
    assert went == [] and not P.moving, went
assert not g.drive_wave_busy()
P.tick(force=True)
assert went == ["p3"], went
lumi.waist_home = real_home

# I4: held swings (Welcome at home, keep alive) end as soon as someone is within IDLE_CLEAR_M, or the switch is off
n = []
real_swing, g._swing = g._swing, (lambda: n.append(1))
g._waver, g._free, g._on = (lambda: None), (lambda: True), (lambda: True)
near = {"n": 0}
g._someone_within = lambda m: len(n) >= 1           # someone walks up after the first swing
g._idle_swings(lambda: True)
assert len(n) == 1, n
n.clear()
g._someone_within = lambda m: False
g._on = lambda: False
g._idle_swings(lambda: True)
assert n == [], n
g._swing = real_swing

# I5: the last switch off with the hand up: lumi.py stops only once the hand is down (or after a wait)
server.MODES_FILE.write_text(json.dumps({"greeter": False, "patrol": False, "wave_greet": False, "welcome": False}))
poses, stopped = iter(["wave_start", "wave_start", "look"]), []
server.arm_route.where = lambda: next(poses, "look")
server.assistant_stop = lambda **k: stopped.append(time.time()) or {"stopped": []}
server.stop_when_lowered(wait_s=2.0, every=0.01)
assert len(stopped) == 1, stopped
server.arm_route.where = lambda: "wave_start"       # never comes down: stopped all the same after the wait
t0 = time.time()
server.stop_when_lowered(wait_s=0.2, every=0.01)
assert len(stopped) == 2 and time.time() - t0 >= 0.2, stopped

# Welcome alone drives with the hand down: only Wave raises it for a drive (owner, 2026-11-16)
import types                                         # noqa: E402
g.arm_route.where = lambda now=None: "look"
g._on, g._drive_on = (lambda: True), (lambda: False)  # Welcome on, Wave off
assert g.raise_for_drive() is False
g.arm_route.where = lambda now=None: "wave_start"
g._drive_on = lambda: True                           # Wave on: the hand up (already there)
assert g.raise_for_drive() is True
g._drive_on = None

# a blocked trip is said aloud, also with only Wave on (owner, 2026-11-16, second round)
said = []
real_say, lumi.mouth.say = lumi.mouth.say, (lambda text, **k: said.append(text))
Mo = lambda **kw: types.SimpleNamespace(**{"greeter": False, "patrol": False, "wave_greet": False, "welcome": False, **kw})
me = types.SimpleNamespace(modes=Mo(wave_greet=True), lang="en",
                           patrol=types.SimpleNamespace(stuck="p3", stuck_why=("Blocked.", "막혔어요."), once=True))
lumi.Lumi.say_stuck(me)
assert said == ["Blocked."] and me.patrol.stuck is None, said
me.modes, me.patrol.stuck, me.patrol.stuck_why = Mo(patrol=True), "p3", ("Blocked.", "막혔어요.")
lumi.Lumi.say_stuck(me)
assert said == ["Blocked.", "Blocked."], said
lumi.mouth.say = real_say


# the last switch off, then a switch on again while the hand comes down: lumi.py is not stopped after all (it was,
# and the supervisor started it again and again, 2026-11-16 16:31)
stopped.clear()
server.arm_route.where = lambda: "wave_start"
server.MODES_FILE.write_text(json.dumps({"greeter": False, "patrol": False, "wave_greet": True, "welcome": False}))
server.stop_when_lowered(wait_s=0.2, every=0.01)
assert stopped == [], stopped
server.MODES_FILE.write_text(json.dumps({"greeter": False, "patrol": False, "wave_greet": False, "welcome": False}))
server.stop_when_lowered(wait_s=0.2, every=0.01)
assert len(stopped) == 1, stopped
print("ok: no stop after a switch on again")
print("ok: modes safety")
