"""Self-check: with only Wave and/or Welcome on, Lumi only waves (owner, 2026-11-16): no talk, no wake word, the wave
greeting says nothing; with Greeter or Patrol on it talks as before. Fake state, no robot:
python tests/test_quiet_modes.py"""
import sys
import types

import no_robot                                     # noqa: F401  any connection to the robot fails the test

from assistant import lumi
from tasks import wave_greet

M = lambda **kw: types.SimpleNamespace(**{"greeter": False, "patrol": False, "wave_greet": False, "welcome": False, **kw})
assert not lumi.talk_allowed(M(wave_greet=True, welcome=True))
assert lumi.talk_allowed(M(greeter=True, wave_greet=True))
assert lumi.talk_allowed(M(patrol=True))
assert not lumi.talk_allowed(M())

# the wave greeting's lines: silent while talk is not allowed
said = []
from audio import mouth  # noqa: E402
mouth.say = lambda text: said.append(text)          # never the real speaker
wave_greet._bg = lambda fn, *a: fn(*a)               # run in this thread
wave_greet._talk = lambda: False
wave_greet._say([("hello", "안녕")], 0)
assert said == [], said
wave_greet._talk = lambda: True
wave_greet._say([("hello", "안녕")], 0)
assert said == ["hello"], said

print("ok: quiet modes")
