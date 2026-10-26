"""Self-check of several commands in one sentence (assistant/chain.py, lumi.chain_run), no robot, no LLM:
python tests/test_chain.py"""
import re
import threading
import types

from assistant import chain, lumi
from tasks import fetch

M = ["home", "p1", "p5", "p9", "stage", "booth_2"]
CANT = lumi.NOT_A_STEP

# ---------- the plan: kinds in the order said; None = not a chain (one command, a mission, talk) ----------
WANT = {
    "look at me and wave": ["quick look", "quick wave"],
    "Lumi, look at me and wave please": ["quick look", "quick wave"],
    "wave and look at me": ["quick wave", "quick look"],
    "웨이브 하고 나 봐": ["quick wave", "quick look"],
    "나 보고 손 흔들어": ["quick look", "quick wave"],
    "고개 들고 몇 시야?": ["quick look", "talk"],
    "go to p5 and tell me the weather": ["steps", "talk"],
    "스테이지 가서 날씨 알려 줘": ["steps", "talk"],
    "put it down and wave": ["steps", "quick wave"],
    "go to the stage and dance": ["steps", "talk"],
    "come here and wave": ["quick come", "quick wave"],
    "go to the stage and follow me": ["steps", "quick follow"],
    "take the cup and put it back": None,                  # all steps: a mission, read back first
    "go to p5 and wave, then come back": ["steps", "quick wave", "quick come_back"],
    "follow me and go to the stage": None,                 # following never ends: only as the last part
    "come here, I need help": None,
    "what's the weather in Seoul and Busan?": None,
    "could you turn around and look?": None,               # the head looks behind
    "look at me": None,
}
bad = []
for t, w in WANT.items():
    got = chain.plan(t, M, CANT)
    short = got and [f"{k} {x[0]}" if k == "quick" else k for k, _, x in got]
    if short != w:
        bad.append(t)
        print(f"FAIL {t!r}: {got}")
assert not bad
print("chain plan ok")

# ---------- the run: each part in turn; a failed mission part skips what drives or needs the hand, not the rest ----
done, said = [], []
fake = types.SimpleNamespace(
    chain_stop=threading.Event(), markers=M, modes=types.SimpleNamespace(patrol=True, drive=True),
    quick_command=lambda w, rule=None: done.append(("quick", w)), answer=lambda w, part=False: done.append(("talk", w)),
    fetch_say=lambda en, ko: said.append(en), chain_wait=lambda: None, base_off=lambda *a, **k: False,
    stay=lambda: None)
fetch.check_hand = lambda: False
runs = []
fetch.run_steps = lambda s, say=None, sender=None: runs.append(s)
fetch.state = lambda: {"status": "failed" if runs and runs[-1][0].get("to") == "p5" else "done"}
lumi.log = lambda *a: None
lumi.Lumi.chain_run(fake, chain.plan("go to p5 and wave, then come back", M, CANT))
assert runs == [[{"do": "go", "to": "p5"}]] and done == [("quick", "wave")], (runs, done)
assert said == ["So I didn't do this part: come back."], said      # never dropped silently
done.clear(), runs.clear()
lumi.Lumi.chain_run(fake, chain.plan("go to the stage and tell me the weather", M, CANT))
assert runs == [[{"do": "go", "to": "stage"}]] and done == [("talk", "tell me the weather")], (runs, done)
done.clear(), runs.clear()
fake.chain_stop.set()                                        # "stop" or new words: nothing more is done
lumi.Lumi.chain_run(fake, chain.plan("look at me and wave", M, CANT))
assert not done
print("chain run ok")
