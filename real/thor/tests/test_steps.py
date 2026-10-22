"""Self-check of reading missions (docs/17), no robot, no LLM: python tests/test_steps.py

Each case: command -> the steps it must give, written short:
  go p1 | go p3,p5,p7 (one of them) | go here | move left 1 | turn -90 | pick white cup | receive cup |
  say <text> | place | place white dining table left | give | hold | arm reach |
  wait (no time: stay / until go on) | wait 30 | wait order [600] (an instruction there) | receive cup wait [120]
"?" as the steps: some words must stay unread (Lumi asks again, nothing runs)."""
from assistant import steps

M = ["home", "PInit", "Wp", "a", "b", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]


def short(s):
    """'move left 1' -> {"do": "move", "dir": "left", "m": 1.0} (the notation above)."""
    w = s.split()
    do = w[0]
    if do == "go":
        to = w[1].split(",")
        return {"do": "go", "to": to if len(to) > 1 else to[0]}
    if do == "move":
        return {"do": "move", "dir": w[1], "m": float(w[2])}
    if do == "turn":
        return {"do": "turn", "deg": float(w[1])}
    if do == "pick":
        return {"do": "pick", "object": w[-1], "colour": w[1] if len(w) == 3 else None}
    if do == "receive":
        out = {"do": "receive", "object": w[1] if len(w) > 1 and w[1] != "wait" else None}
        if "wait" in w:
            out["wait_s"] = float(w[-1]) if w[-1] != "wait" else steps.WAIT_GIVE_S
        return out
    if do == "wait":
        if len(w) > 1 and w[1] == "order":
            return {"do": "wait", "s": float(w[2]) if len(w) > 2 else steps.WAIT_ORDER_S, "until": "instruction"}
        return {"do": "wait", "s": float(w[1]) if len(w) > 1 else None}
    if do == "say":
        return {"do": "say", "text": s[4:]}
    if do == "place":
        if len(w) == 1:
            return {"do": "place", "on": None}
        side = w[-1] if w[-1] in ("left", "right") else None
        rest = w[1:-1] if side else w[1:]
        colour = rest[0] if rest[0] in steps.brain.COLOURS.values() and len(rest) > 1 else None
        name = " ".join(rest[1:] if colour else rest)
        return {"do": "place", "on": {"name": name, "colour": colour, "side": side}}
    if do == "arm":
        return {"do": "arm", "pose": w[1]}
    if do == "give" and len(w) > 1:
        return {"do": "give", "person": s[5:]}
    return {"do": do}


CASES = {
    # ---- the owner's examples ----
    "take the cup, go forward 0.5 m, then right 1 m and put it on the table":
        "pick cup | move forward 0.5 | move right 1 | place dining table",
    "go forward 0.5 meters, then go right 1 meter and put the cup on the table":
        "move forward 0.5 | move right 1 | place dining table",
    "take the cup and go left 1 meter and look for the table and put it there":
        "pick cup | move left 1 | place dining table",
    "take the cup, go to final, give it and say Anvar says hello":
        "pick cup | go final | give | say Anvar says hello",
    "take the cup, go to the final point, give it to them and tell them: Anvar says hello to you":
        "pick cup | go final | give | say Anvar says hello to you",
    "go to p9, ask them for the cup, then bring it to p1":
        "go p9 | receive cup | go p1",
    "go to p9 and tell the people: please give me the cup, I have to bring it to p1. Then take the cup from them and bring it to p1":
        "go p9 | say please give me the cup, I have to bring it to p1 | receive cup | go p1",
    "bring it to p3, p5 or p7": "go p3,p5,p7",
    "take it to one of p3, p5 and p7 and put it on the table": "go p3,p5,p7 | place dining table",
    "bring it to a random one of p2, p4": "go p2,p4",
    "put it on the white table on your left": "place white dining table left",
    "put it on the table on your right": "place dining table right",
    "put the cup on the white table to the left": "place white dining table left",
    "go to p10, then go left 1 meter and put it on the table": "go p10 | move left 1 | place dining table",
    "go to p10, then go left one meter and give it to the person": "go p10 | move left 1 | give",
    # 2026-10-21, said by voice: "let's", "P10 point", "10p point", "p ten"
    "Let's go P10 point and wait 30 seconds then come back here again.": "go p10 | wait 30 | go here",
    "let's go to 10p point then wait 30 seconds and come back here again": "go p10 | wait 30 | go here",
    "go to p ten, wait 30 seconds and come back here": "go p10 | wait 30 | go here",
    "go to point 10 and let's back 1 meter": "go p10 | move back 1",
    # ---- moves and turns ----
    "go forward 1 meter and put it on the table": "move forward 1 | place dining table",
    "move back half a meter and give it to me": "move back 0.5 | give",
    "go back 50 cm, turn left and put it down": "move back 0.5 | turn 90 | place",
    "turn right, go 2 meters and put it on the table": "turn -90 | move forward 2 | place dining table",
    "turn around and give it to me": "turn 180 | give",
    "turn left 45 degrees, then put it on the table": "turn 45 | place dining table",
    "go 1 metre to the right and put the cup on the table": "move right 1 | place dining table",
    "drive forward two meters then turn right and hold it": "move forward 2 | turn -90 | hold",
    "go one meter forward and one meter left and put it on the stool": "move forward 1 | move left 1 | place chair",
    "move forward 1.5 m, then put it on the yellow chair": "move forward 1.5 | place yellow chair",
    "go forward a meter and then give it to me": "move forward 1 | give",
    # ---- picks, places, gives ----
    "pick up the red cup and go to p2 and put it on the table": "pick red cup | go p2 | place dining table",
    "take the bottle from p2 and bring it to p5 and put it on the table, then go home":
        "go p2 | pick bottle | go p5 | place dining table | go home",
    "grab the white cup, turn around, go forward 1 m and put it on the table":
        "pick white cup | turn 180 | move forward 1 | place dining table",
    "take the cup, go to p4 and give it to the person there": "pick cup | go p4 | give",
    "take the cup, go to p4, give it and come back here": "pick cup | go p4 | give | go here",
    "take the cup, go to p4, give it and go back home": "pick cup | go p4 | give | go home",
    "bring it to p2 and put it on the orange chair": "go p2 | place orange chair",
    "go to p6 and put it on the sofa": "go p6 | place couch",
    "bring it back to me": "go here | give",
    "take the apple, go to final and say here is your apple, then give it":
        "pick apple | go final | say here is your apple | give",
    # ---- receive ----
    "go to p9, take the cup from the person and bring it to p1": "go p9 | receive cup | go p1",
    "go to p3 and get the bottle from them, then come back and give it to me":
        "go p3 | receive bottle | go here | give",
    "wait for someone to give you the cup, then put it on the table": "receive cup wait | place dining table",
    "receive the cup and bring it to final": "receive cup | go final",
    "go to exit, ask someone to hand you the cup, then bring it here and put it on the table":
        "go exit | receive cup | go here | place dining table",
    # ---- say ----
    "go to p2 and say hello everyone": "go p2 | say hello everyone",
    "go to p2 and tell them lunch is ready": "go p2 | say lunch is ready",
    "go to p5, say: the meeting starts in five minutes, then come back home":
        "go p5 | say the meeting starts in five minutes | go home",
    'go to final and say "welcome to JAKA"': "go final | say welcome to JAKA",
    "go to p7 and tell everyone that Kim is waiting at the entrance":
        "go p7 | say Kim is waiting at the entrance",
    # ---- arm ----
    "reach out your arm, then open your hand": "arm reach | arm open",
    "go to p1 and wave": "?",                                      # wave is not a mission step: asked again
    # ---- Korean ----
    "컵을 들고 앞으로 0.5미터 가서 오른쪽으로 1미터 가고 테이블에 놔":
        "pick cup | move forward 0.5 | move right 1 | place dining table",
    "컵 잡고 p9로 가서 줘": "pick cup | go p9 | give",
    "p9로 가서 컵을 받아서 p1으로 가져가": "go p9 | receive cup | go p1",
    "왼쪽에 있는 흰 테이블에 놔": "place white dining table left",
    "오른쪽 테이블에 놔": "place dining table right",
    "p3, p5, p7 중에 아무데나 가져가": "go p3,p5,p7",
    "p10으로 가서 왼쪽으로 1미터 가고 테이블에 놔": "go p10 | move left 1 | place dining table",
    "뒤로 1미터 가서 줘": "move back 1 | give",
    "final로 가서 안녕하세요라고 말해": "go final | say 안녕하세요",
    "final로 가서 컵 주고 김 대리님이 안부 전한다고 전해": "go final | give | say 김 대리님이 안부 전한다",
    "오른쪽으로 돌고 앞으로 2미터 가서 노란 의자에 놔": "turn -90 | move forward 2 | place yellow chair",
    "컵 들고 집으로 가": "pick cup | go home",
    # ---- must not run: unread words ----
    "take the cup and dance": "?",
    "go to the kitchen and put it on the table": "?",              # kitchen is not on the map
    "go to p12 and give it": "?",
    "olmani ol va p1 ga bor": "?",                                 # not English or Korean
    "take the ap and go to p1": "?",                               # half-heard object: never guessed
    "go left and put it on the table": "?",                        # how far? not guessed
}

from tests.steps_cases import CASES as BLIND        # written from docs/17 only, without reading steps.py
from tests.steps_cases2 import CASES as BLIND2      # the same, a second round (speech-recogniser forms, polite Korean)
from tests.steps_cases3 import CASES as BLIND3      # the same, third round: a named person to give it to, a sender
from tests.steps_cases4 import CASES as BLIND4      # the same in every Korean speech level (반말, -요, -습니다)
from tests.steps_cases5 import CASES as BLIND5      # marker names and numbers as said: 피쓰리, 포인트 삼, 일 미터, mixed
from tests import steps_cases6                      # waiting: stay, a time, until someone gives it, an instruction
CASES = {**CASES, **BLIND, **BLIND2, **BLIND3, **BLIND4, **BLIND5, **steps_cases6.CASES}
failed = []
for text, want in CASES.items():
    got, unread = steps.rules(text, M)
    if want == "?":                                  # not understood, or understood and refused: nothing runs
        ok = bool(unread) or bool(steps.check(got, False, M))
    else:
        ok = not unread and got == [short(s.strip()) for s in want.split(" | ")]
    if not ok:
        failed.append((text, want, got, unread))
for text, want, got, unread in failed:
    print(f"FAIL {text!r}\n  want {want}\n  got  {got}\n  unread {unread}")
print(f"{len(CASES) - len(failed)}/{len(CASES)} read right")
# waits: too long is read but refused; an interjection or a question is not a mission
for text in steps_cases6.TOO_LONG:
    got, unread = steps.rules(text, M)
    if unread or not steps.check(got, False, M):
        failed.append((text, "refused", got, unread))
for text in steps_cases6.NOT_MISSION:
    got, unread = steps.rules(text, M)
    if not unread and steps.is_mission(got):
        failed.append((text, "not a mission", got, unread))
for text, want, got, unread in failed:
    if want in ("refused", "not a mission"):
        print(f"FAIL {text!r}: must be {want}, got {got} unread {unread}")
assert not failed

# ---- missions vs the old fetch / carry ----
for text, mission in {"bring me the apple from p1": False, "take the cup from p2 to home": False,
                      "give it to me": False, "go to p5 and put it on the table": False,
                      "take the cup, go left 1 meter and put it on the table": True,
                      "bring it to p3, p5 or p7": True, "go to p2 and say hi": True}.items():
    got, unread = steps.rules(text, M)
    assert steps.is_mission(got) == mission, (text, got)

# ---- checks before a mission starts ----
S = lambda w: [short(x.strip()) for x in w.split(" | ")]
assert steps.check(S("pick cup | go p1 | place"), False, M) == []
assert steps.check(S("go p1 | give"), False, M)                    # nothing in the hand
assert steps.check(S("pick cup | go p1"), True, M)                 # the hand is full already
assert steps.check(S("go p1 | place"), True, M) == []
assert steps.check(S("receive cup | give"), False, M) == []
assert steps.check(S("move forward 4"), False, M)                   # longer than MOVE_MAX_M
assert steps.check(S("go p3,p99"), False, M)                        # not on the map
assert steps.check(S("pick cup | arm fold"), False, M)              # not with a cup in the hand
assert steps.check(S("arm open"), False, M) == []

# ---- read-back ----
s = S("pick cup | move forward 0.5 | move right 1 | place dining table")
assert steps.describe(s, "en") == ("Take the cup, drive 0.5 m forward, turn right and drive 1 m, "
                                   "then put it on the table."), steps.describe(s, "en")
assert steps.describe(S("go p3,p5,p7 | hold"), "en") == "Go to one of p3, p5 or p7, then hold it."
assert steps.describe(S("go final | give | say Anvar says hello"), "en") == \
    'Go to final, hand it over, then say "Anvar says hello".'
assert steps.describe(s, "ko")
print("steps ok")

# ---- the LLM pass (faked): kept only when every value is written in the command ----
fake = {}
steps._ollama = lambda messages, fmt: fake["lang"] if fmt == "json" else fake["steps"]
fake["lang"] = {"language": "English"}
cmd = "grab the bottle and then kindly zip over to p4, after that put it onto the white table"
fake["steps"] = {"steps": [{"do": "pick", "object": "bottle"}, {"do": "go", "to": ["p4"]},
                           {"do": "place", "on": {"name": "dining table", "colour": "white"}}]}
got, unread, by = steps.read(cmd, M)
assert by == "llm" and not unread and got == S("pick bottle | go p4 | place white dining table"), (got, unread, by)
for bad in ([{"do": "go", "to": ["p5"]}],                                   # a marker not in the command
            [{"do": "pick", "object": "orange"}],                           # an object not in the command
            [{"do": "move", "dir": "forward", "m": 2}],                     # a number not in the command
            [{"do": "say", "text": "welcome to JAKA"}],                     # words not in the command
            [{"do": "give"}],                                                # give not said
            [{"do": "unknown"}]):
    fake["steps"] = {"steps": bad}
    got, unread, by = steps.read(cmd, M)
    assert by == "rules" and unread, (bad, got, unread, by)
fake["lang"] = {"language": "Uzbek"}
assert steps.read("kubokni ol, keyin p4 ga bor", M)[2] == "other"
steps._ollama = lambda messages, fmt: (_ for _ in ()).throw(AssertionError("LLM asked for a one-clause command"))
assert steps.read("bring me the apple from p1", M)[2] == "rules"
assert steps.read("take the cup, go left 1 meter and put it on the table", M)[2] == "rules"
print("steps llm ok")

# ---- the LLM checks the review asked for ----
def llm_says(cmd, steps_):
    global fake
    fake = {"lang": {"language": "English"}, "steps": {"steps": steps_}}
    steps._ollama = lambda messages, fmt: fake["lang"] if fmt == "json" else fake["steps"]
    return steps.read(cmd, M)
assert llm_says("please kindly turn left and then roll forward 1 m, finally hold it",
                [{"do": "turn", "deg": -90}, {"do": "move", "dir": "forward", "m": 1}, {"do": "hold"}])[2] == "rules"
assert llm_says("kindly turn left 45 degrees and then roll forward 1 m, finally hold it",
                [{"do": "turn", "deg": 90}, {"do": "move", "dir": "forward", "m": 1}, {"do": "hold"}])[2] == "rules"
assert llm_says("kindly back up 1 m and then spin around, finally hold it",
                [{"do": "move", "dir": "forward", "m": 1}, {"do": "turn", "deg": 180}, {"do": "hold"}])[2] == "rules"
assert llm_says("go to p1, then roll back 1.5 m and wiggle", [{"do": "go", "to": ["p1"]},
                {"do": "move", "dir": "back", "m": 1}])[2] == "rules"                    # "1" is not in "p1" / "1.5"
assert llm_says("kindly roll forward 1 m and then wiggle", [{"do": "move", "dir": "forward", "m": 1},
                {"do": "move", "dir": "forward", "m": 1}])[2] == "rules"                 # said once, driven twice
assert llm_says("don't take the cup, just roll over to p1", [{"do": "go", "to": ["p1"]}])[2] == "rules"
assert llm_says("take the cup and then zip over to p1", [{"do": "go", "to": ["p1"]}])[2] == "rules"  # pick left out
got = llm_says("take the cup and then zip over to p1", [{"do": "pick", "object": "cup"}, {"do": "go", "to": ["p1"]}])
assert got[2] == "llm" and got[0] == S("pick cup | go p1"), got

# ---- lists: only "or" / one of / 중 is a choice; "and" is both, in turn ----
assert steps.rules("go to p1 and p2", M)[0] == S("go p1 | go p2")
assert steps.rules("take the cup and go to p1, p2", M)[0] == S("pick cup | go p1 | go p2")

# ---- checks of what may come from the dashboard as JSON ----
for bad in ([{"do": "fly"}], [{"do": "go", "to": []}], [{"do": "move", "dir": "up", "m": 1}], [{"do": "turn", "deg": 720}],
            [{"do": "arm", "pose": "wave"}], [{"do": "pick", "object": "phone"}], [{"do": "move", "dir": "forward"}],
            [{"do": "move", "dir": "forward", "m": 0.005}], ["go p1"], []):
    assert steps.check(bad, False, M), bad
assert steps.check(S("pick cup | go p1 | arm open"), False, M)            # it would fall
print("steps review ok")

# ---- waits: checks, read-back, the LLM's wait checked against the words ----
assert steps.check(S("go p3 | wait"), False, M) == [] and steps.check(S("wait 1800 | go p1"), False, M) == []
assert steps.check(S("wait 1801"), False, M) and steps.check(S("receive cup wait 3600"), False, M)
assert steps.check(S("go p6 | wait order"), True, M) == []
for bad in ([{"do": "wait", "s": "ten"}], [{"do": "wait", "s": None, "until": "instruction"}], [{"do": "wait", "s": 0}],
            [{"do": "wait", "s": 5, "until": "dance"}], [{"do": "receive", "object": "cup", "wait_s": None}]):
    assert steps.check(bad, False, M), bad
assert steps.describe(S("go p3 | wait"), "en") == "Go to p3, then stay there."
assert steps.describe(S("go exit | wait | go home"), "en") == \
    "Go to exit, wait there until I'm told to go on, then go to my dock."
assert steps.describe(S("wait 90 | go p5"), "en") == "Wait 1 minute 30 seconds, then go to p5."
assert steps.describe(S("go p6 | wait order"), "en") == "Go to p6, then wait there for an instruction (up to 5 minutes)."
assert steps.describe(S("go p9 | receive cup wait | go p1"), "en") == \
    "Go to p9, wait for someone to give me the cup (up to 5 minutes), then go to p1."
assert steps.describe(S("go p3 | wait"), "ko") == "p3 위치로 가고 거기서 기다릴게요."
assert steps.describe(S("wait 300 | go p1"), "ko") == "5분 기다리고 p1 위치로 갈게요."
assert not steps.is_mission(S("wait 30")) and steps.is_mission(S("go p3 | wait"))
assert llm_says("go to p2, then chill there for 2 minutes and wiggle", [{"do": "go", "to": ["p2"]},
                {"do": "wait", "s": 120}])[0] == S("go p2 | wait 120")
assert llm_says("go to p2, then chill there for 2 minutes and wiggle", [{"do": "go", "to": ["p2"]},
                {"do": "wait", "s": 60}])[2] == "rules"                                  # 60 s is not said
assert llm_says("go to p2, then chill there and wiggle", [{"do": "go", "to": ["p2"]},
                {"do": "wait", "s": None}])[2] == "rules"                                # no wait word
assert llm_says("go to p2, then chill there and do whatever the visitors tell you", [{"do": "go", "to": ["p2"]},
                {"do": "wait", "s": None, "until": "instruction"}])[0] == S("go p2 | wait order")
print("steps wait ok")

# ---- three or four steps in one breath on the conference map (tests/steps_cases7.py) ----
from assistant import brain
from tests import steps_cases7 as c7
failed = []
for text, want in list(c7.CASES.items()) + [(brain.self_correct(t, c7.CONF), w) for t, w in c7.FIXED.items()]:
    got, unread = steps.rules(text, c7.CONF)
    if want == "?":
        ok = bool(unread) or bool(steps.check(got, False, c7.CONF))
    else:
        ok = not unread and got == [short(x.strip()) for x in want.split(" | ")]
    if not ok:
        failed.append(text)
        print(f"FAIL {text!r}\n  want {want}\n  got  {got}\n  unread {unread}")
for want, (en, ko) in c7.READ_BACK.items():
    s_ = [short(x.strip()) for x in want.split(" | ")]
    for lang, said in (("en", en), ("ko", ko)):
        if steps.describe(s_, lang) != said:
            failed.append(want)
            print(f"FAIL read-back {lang} {want!r}\n  want {said}\n  got  {steps.describe(s_, lang)}")
print(f"{len(c7.CASES) + len(c7.FIXED) - sum(1 for f in failed if f in c7.CASES or f in c7.FIXED.values())}/"
      f"{len(c7.CASES) + len(c7.FIXED)} read right on the conference map")
assert not failed
print("steps conference ok")
