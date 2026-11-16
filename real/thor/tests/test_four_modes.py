"""Self-check of the four switches (owner, 2026-11-16): Greeter, Patrol, Wave (wave_greet) and Welcome each work on
their own, so lumi.py runs while any of them is on and stops when all four are off; the assistant reads all four.
Fake state, no robot: python tests/test_four_modes.py"""
import json
import tempfile
import types
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test

from api import server
from assistant import lumi

tmp = Path(tempfile.mkdtemp())
server.MODES_FILE = tmp / "lumi_modes.json"         # never the real /dev/shm file
lumi.MODES_FILE = str(server.MODES_FILE)

# the file keeps all four; an old file without welcome reads it as off
server.MODES_FILE.write_text(json.dumps({"greeter": False, "patrol": False, "wave_greet": True}))
assert server.read_modes() == {"greeter": False, "patrol": False, "wave_greet": True, "welcome": False}, server.read_modes()

# who starts and stops lumi.py
running, calls = [], []
server.assistant_pids = lambda: list(running)
server.start_assistant = lambda *a, **k: (calls.append("start"), running.append(1))
server.assistant_stop = lambda *a, **k: (calls.append("stop"), running.clear())
server._calib_active = lambda: False
server.agv.status = lambda: {"charge_state": True, "move_status": "idle"}   # on the charger (Welcome)
server._bg = lambda fn: fn()                        # the stop after the hand is down runs at once here
server.arm_route.where = lambda: "look"             # the hand is down
server.MODES_FILE.write_text(json.dumps({}))


def switch(**kw):
    return server.modes_set(server.ModesBody(**kw))


for only in ("greeter", "patrol", "wave_greet", "welcome"):
    calls.clear()
    r = switch(**{only: True})
    assert calls == ["start"] and r["running"] and r[only], (only, calls, r)
    calls.clear()
    r = switch(**{only: False})
    assert calls == ["stop"] and not r["running"], (only, calls, r)

# Welcome on, then Wave on and Welcome off: lumi.py keeps running
switch(welcome=True)
calls.clear()
switch(wave_greet=True)
switch(welcome=False)
assert calls == [] and running, calls
switch(wave_greet=False)
assert calls == ["stop"], calls

assert server.any_on({"greeter": False, "patrol": False, "wave_greet": False, "welcome": True})
assert not server.any_on(dict(server.DEFAULT_MODES))

# the assistant reads the four switches live
server.MODES_FILE.write_text(json.dumps({"greeter": False, "patrol": False, "wave_greet": True, "welcome": True}))
m = lumi.Modes(types.SimpleNamespace(patrol=False, no_arm=False))
assert (m.greeter, m.patrol, m.wave_greet, m.welcome) == (False, False, True, True), vars(m)
assert lumi.waving_on() and lumi.wave_greet_on()
server.MODES_FILE.write_text(json.dumps({"greeter": True, "patrol": False, "wave_greet": False, "welcome": True}))
assert lumi.waving_on() and not lumi.wave_greet_on() and lumi.welcome_on()
server.MODES_FILE.write_text(json.dumps({"greeter": True}))
assert not lumi.waving_on() and not lumi.welcome_on()

print("ok: four switches")
