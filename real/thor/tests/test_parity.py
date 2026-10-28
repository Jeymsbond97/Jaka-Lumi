"""tests/parity_check.py on a few fixed sentences: typed (the Command box) and voice give the same plan, English and
Korean the same, each the one asked for. Rules only, nothing moves: python tests/test_parity.py"""
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from tests import parity_check as pc

M = ["p1", "p2", "p3", "p5", "home", "exit", "dock2"]
CASES = [  # (text, state, expect)
    ("go to p1", "idle", "action:go_to p1 | mission"), ("p1로 가 줘", "idle", "action:go_to p1 | mission"),
    ("p1으로 가십시오", "idle", "action:go_to p1 | mission"),
    ("turn left", "idle", "action:turn left"), ("왼쪽으로 돌아", "idle", "action:turn left"),
    ("stop", "idle", "stop"), ("멈춰", "idle", "stop"), ("그만해요", "idle", "stop"),
    ("wave", "idle", "action:wave"), ("손 흔들어", "idle", "action:wave"),
    ("take this from me", "idle", "receive"), ("이거 받아", "idle", "receive"),
    ("pick up the red cup", "idle", "action:pick red cup | action:fetch cup"),
    ("빨간 컵 집어", "idle", "action:pick red cup | action:fetch cup"),
    ("put it on the table", "holding", "place"), ("테이블에 놔", "holding", "place"),
    ("put it on the table", "idle", "empty_hand | talk"),
    ("what time is it?", "idle", "talk"), ("몇 시야?", "idle", "talk"),
]

assert pc.canon("action:go_to p1") == pc.canon("mission", st=[{"do": "go", "to": "p1"}]) == "steps go p1"
assert pc.canon("talk") == pc.canon("refuse") == pc.canon("llm?") == "none"
assert pc.typed_got({"action": "steps", "steps": [{"do": "turn", "deg": 90.0}]})[0] == "action:turn left 90"

bad = []
for text, state, expect in CASES:
    c = {"text": text, "state": state, "before": None, "expect": expect, "lang": "ko" if pc.brain.HANGUL.search(text)
         else "en", "markers": M, "intent": "fixed"}
    r = pc.run_case("fixed", "fixed", c, None, False)
    if not r["same"] or r["v"] not in ("right", "llm?") or r["t"] not in ("right", "llm?"):   # llm?: a question
        bad.append(r)
        print(f"BAD [{state}] {text!r}: voice {r['voice']} ({r['v']}), typed {r['typed']} ({r['t']}), want {expect}")
print(f"{len(CASES) - len(bad)}/{len(CASES)} the same typed and by voice, as asked")
assert not bad
print("parity ok")
