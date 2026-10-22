"""Self-check of commands of several steps said by voice, the way lumi.answer() takes them (docs/17 §2, §6): the
correction inside the sentence (brain.self_correct), lumi.read_mission (a mission, the plain fetch, or asked again:
a part that is no task step is never done half), the read-back sentence, and the Greeter-only rule (a mission that
drives is refused with one line, one that stays in place runs). Fake robot; the mission reader's LLM pass faked
(it reads nothing):
python tests/test_mission_route.py"""
import types

from assistant import brain, lumi, steps
from tasks import fetch
from tests import steps_cases7 as c7

M = c7.CONF


def forbid(*a, **k):
    raise AssertionError("a test reached the robot")


refusal = lumi.skills.refusal                            # a table of what the fingers can't take, no robot
for mod in (lumi.agv, lumi.head, lumi.arm, lumi.gripper, lumi.motion, lumi.skills):   # nothing may reach the robot
    for name in dir(mod):
        if not name.startswith("_") and callable(getattr(mod, name)) and not isinstance(getattr(mod, name), type):
            setattr(mod, name, forbid)
lumi.skills.refusal = refusal
steps._ollama = lambda messages, fmt: {"language": "English"} if fmt == "json" else {"steps": [{"do": "unknown"}]}
lumi.log = fetch.log = lambda *a: None

# ---------- every mission of the conference set: read whole, or the plain fetch; "?": asked, nothing moves ----------
bad = []
for text, want in list(c7.CASES.items()) + list(c7.FIXED.items()):
    t = brain.self_correct(text, M)
    read = lumi.read_mission(t, M)
    rule = brain.intent(t, M)
    if want == "?":
        asked = read is not None and read[1]
        refused = read is not None and not read[1] and steps.check(read[0], False, M)
        if not (asked or refused or read is None and (rule is None or rule[0] == "fetch")):
            bad.append((text, read, rule))
    elif not (read and not read[1] or read is None and rule and rule[0] == "fetch"):
        bad.append((text, read, rule))
assert not bad, bad

# ---------- the corrections said by voice ----------
FIX = {"go to start, no, end": "go to end", "스타트로 가, 아니 엔드로": "end로 가", "turn left, I mean right": "turn right",
       "앞으로 1미터, 아니 2미터 가": "앞으로 2 m 가", "컵 집어, 아니 병": "병 집어", "go to the stage, never mind": "",
       "스테이지로 가, 아니 됐어": "", "go to the stage, no, the kitchen": None, "I like apples, no, I love them": None,
       "go to the stage, no rush": None, "no, go to the end": None}
for text in ("stop, no, wait", "go to start, no wait, stop", "멈춰, 아니 기다려"):   # a stop is never rewritten
    assert brain.self_correct(text, M) == text and lumi.stop_order(text, M), text
for text, want in FIX.items():
    got = brain.self_correct(text, M)
    assert got == (text if want is None and text in ("I like apples, no, I love them", "go to the stage, no rush",
                                                     "no, go to the end") else want), (text, got)

# ---------- Greeter only: a mission that drives is refused, one in place runs ----------
said, started = [], []
L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.markers, L.current = "en", M, None
L.brain = types.SimpleNamespace(history=[])
L.keep_listening = lambda: None
L.fetch_say = lambda en, ko=None: said.append(en)
L.fetch_status = lambda: None
L.modes = types.SimpleNamespace(greeter=True, patrol=False, drive=True, wave=True)
fetch.check_hand = lambda: False
lumi.fetch_dialog = types.SimpleNamespace(run_steps=lambda s, hear, say, describe, start: started.append(s) or "started")
for text in ("take the cup, go to booth two, give it to James and come back", "스테이지 갔다 와",
             "go to the stage, wait 10 seconds, then come back"):
    said.clear(), started.clear()
    assert L.mission_request(text) and said == [lumi.BASE_OFF_SAY[0]] and not started, (text, said, started)
for text in ("pick up the cup and give it to me", "컵 집어서 나한테 줘"):
    said.clear(), started.clear()
    assert L.mission_request(text) and started and not said, (text, said, started)
said.clear()
assert L.mission_request("go to the stage and wave") and said and said[0].startswith("Sorry, I can't do that as part"), said
L.modes.patrol = True
said.clear(), started.clear()
assert L.mission_request("take the cup, go to booth two, give it to James and come back") and started
assert steps.describe(started[0]) == "Take the cup, go to booth 2, hand it to James, then come back here."
print("mission route ok")
