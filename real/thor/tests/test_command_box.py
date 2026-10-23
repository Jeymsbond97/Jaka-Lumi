"""The dashboard's Command box (/tasks/parse) reads a sentence exactly as voice does (Lumi.answer, both on
lumi.route): the same plan for the same words, English and Korean. No robot, no LLM (rules only on both sides):
python tests/test_command_box.py"""
import types

from assistant import brain, lumi
from tasks import fetch

M = ["home", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]
SENTENCES = [
    # the owner's examples
    "let's go exit point and go p9 point", "Let's go P5 (point).", "go to p5 and tell me the weather",
    "look at me and wave", "웨이브 하고 나 봐", "고개 들고 몇 시야?", "exit 갔다가 p9로 가", "first p1 then p2",
    "take the cup, go to p5, give it to Sarah and come back", "go to p10, then go left 1 meter and give it to the person",
    "go to p9, ask them for the cup, then bring it to p1", "컵 집고 p3로 가서 테이블에 놔",
    "Let's go P10 point and wait 30 seconds then come back here again.",
    # corrections
    "go to p1, no, p2", "go to p1, never mind", "앞으로 1미터, 아니 2미터 가",
    # one command
    "turn left", "한 바퀴 돌아", "move back 1 meter", "앞으로 1미터 가", "come here", "이리 와", "follow me", "look left",
    "lift yourself up", "wave", "손 흔들어", "stop", "멈춰", "p3로 가 줘", "spin around", "pick up the red cup", "빨간 컵 집어",
    "take this from me", "이거 받아", "open your hand", "bring me the cup from p1", "p3에서 컵 가져와",
    # talk, questions, refusals
    "what time is it?", "오늘 날씨 어때?", "hello", "what's your name?", "go to p12", "dance", "go to p5 and dance",
    "루미야 너 월급 받아?",
]

# ---------- voice: Lumi.answer with every handler recorded, nothing moves, no LLM ----------
got_voice = []


class LLMReached(Exception):
    pass


def rec(*item):
    got_voice.append(item)
    return True


def steps_of(rule):                                   # what the mission runner does for a keyword command
    a, t = rule
    d, _, n = t.partition(" ")
    return {"go_to": lambda: [{"do": "go", "to": t}],
            "move": lambda: [{"do": "move", "dir": d, "m": float(n or 1)}],
            "turn": lambda: [{"do": "turn", "deg": 180.0 if d == "around" else (1 if d == "left" else -1) * float(n or 90)}],
            "arm": lambda: [{"do": "arm", "pose": t}],
            "pick": lambda: [{"do": "pick", "object": t.split()[-1], "colour": t.split()[0] if " " in t else None}],
            }.get(a, lambda: None)()


def quick(text):
    rule = brain.intent(text, M)
    if not rule or rule[0] not in lumi.QUICK_RULES:
        return False
    if rule[0] == "fetch":
        return rec("fetch")
    if rule[0] in ("weather", "search"):
        return rec("talk")
    s = steps_of(rule)
    return rec("steps", s) if s else rec("command", rule[0])


def hand(text):
    h = brain.hand_request(text, False, L.brain, M)
    if h and h[0] == "receive":
        return rec("steps", [{"do": "receive", "object": h[1], "from_hand": True}])
    return rec("talk")


fetch.check_hand = lambda: False
lumi.log = fetch.log = lambda *a: None
lumi.mouth = types.SimpleNamespace(say=lambda *a, **k: None, lang_of=lambda t: "ko" if brain.HANGUL.search(t) else "en",
                                recent_speech=lambda s=30.0: "")
lumi.ears = types.SimpleNamespace(heard_lang=lambda x: x, last_stt={}, understood=lambda: True, heard_clearly=lambda: True)
real_seeing = lumi.seeing.answer
lumi.seeing.answer = lambda t, lang="en", frames=None, slow_line=None: real_seeing(t, lang, frames=[])   # no camera
L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.markers, L.current, L.patrol = "en", M, None, None
L.now_doing = lambda: ("", "")
for name in ("follow_stop", "voice_setting", "fixed_answer", "drive_words", "mission_running", "chain_busy", "fetch_voice"):
    setattr(L, name, lambda *a, **k: False)
L.fetch_status = lambda: None
L.keep_listening = lambda: None
L.fetch_say = lambda *a: None
L.stop_all = lambda: rec("stop")
L.chain_request = lambda text, plan=None: rec("chain", [[k, w] for k, w, _ in plan])
L.mission_request = lambda text, read=None: rec("talk") if read[1] else rec("steps", read[0])
L.hand_command = hand
L.quick_command = quick
L.end_conversation = lambda *a: rec("talk")
L.sing_song = lambda *a: rec("talk")


def voice(text):
    got_voice.clear()
    L.brain = brain.Brain()
    L.brain.respond_stream = lambda *a, **k: (_ for _ in ()).throw(LLMReached())
    try:
        L.answer(text)
    except LLMReached:
        rec("talk")
    return got_voice[0] if got_voice else ("talk",)


# ---------- the box ----------
from api import server
server.agv.markers = lambda: M


def box(text):
    r = server.task_parse(server.ParseBody(text=text))
    a = r["action"]
    if a == "steps":
        return ("steps", r["steps"])
    if a == "command":
        return ("chain", r["parts"]) if "parts" in r else ("stop",) if r["sentence"] == "Stop." else \
            ("command", brain.intent(r["text"], M)[0])
    if a == "fetch":
        return ("fetch",)
    return ("talk",)


bad = []
for t in SENTENCES:
    v, b = voice(t), box(t)
    if "-v" in __import__("sys").argv:
        print(t, "->", v)
    if v != b:
        bad.append(t)
        print(f"DIFFERENT {t!r}\n  voice {v}\n  box   {b}")
print(f"{len(SENTENCES) - len(bad)}/{len(SENTENCES)} the same by voice and in the Command box")
assert not bad
print("command box ok")
