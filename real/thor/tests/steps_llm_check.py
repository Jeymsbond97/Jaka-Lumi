"""The mission reader's LLM pass (steps.read, brain.MODEL through Ollama) on wordings the rules leave a part of
(tests/steps_cases7.py LLM): what it kept must be exactly the steps written there, and nothing for "?".
Uses the shared LLM: run it alone. python tests/steps_llm_check.py"""
import time

from assistant import steps
from tests import steps_cases7 as c7

real = steps._ollama
from tests.test_steps import short          # noqa: E402 - runs the offline checks, which fake the LLM
steps._ollama = real

right, t0 = 0, time.time()
for text, want in c7.LLM.items():
    got, unread, by = steps.read(text, c7.CONF)
    ok = (bool(unread) or bool(steps.check(got, False, c7.CONF))) if want == "?" else \
        not unread and got == [short(x.strip()) for x in want.split(" | ")]
    right += ok
    print(f"{'ok  ' if ok else 'FAIL'} [{by}] {text!r}\n     want {want}\n     got  {got} unread {unread}", flush=True)
print(f"{right}/{len(c7.LLM)} right ({time.time() - t0:.0f} s)")
