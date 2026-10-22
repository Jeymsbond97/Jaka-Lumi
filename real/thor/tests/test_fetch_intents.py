"""Self-check of the voice side of fetch tasks (docs/16 §4), no robot, no audio: python tests/test_fetch_intents.py"""
import time

from assistant import brain, fetch_dialog

M = ["p1", "p2", "p3", "home", "final"]
P1, P2, HOME = {"marker": "p1"}, {"marker": "p2"}, {"marker": "home"}


def task(obj, src, dest, finish="hold", colour=None):
    return {"object": obj, "colour": colour, "source": src, "dest": dest, "finish": finish}


PARSE = {
    "bring me the apple from p1": (task("apple", P1, "here"), []),
    "take the cup from p2 to home": (task("cup", P2, HOME), []),
    "get the bottle from point 3 and put it on the table": (task("bottle", {"marker": "p3"}, None, "place"), ["dest"]),
    "fetch the red cup": (task("cup", "here", None, colour="red"), ["dest"]),
    "bring the orange cup from point one to me": (task("cup", P1, "here", colour="orange"), []),
    "p1에서 사과 가져와": (task("apple", P1, "here"), []),
    "포인트 1에서 바나나 가져와": (task("banana", P1, "here"), []),
    "컵을 p2에서 home으로 가져다 놔": (task("cup", P2, HOME, "place"), []),
    "bring me the ap from p1": (task(None, P1, "here"), ["object"]),           # half-heard: asked, not guessed
    "bring me the thing": (task(None, "here", "here"), ["object"]),
    "take the cup from p9 to home": (task("cup", None, HOME), ["place"]),      # p9 is not on the map
    "take the banana from the kitchen to p1": (task("banana", None, P1), ["place"]),
    "apple from p1 to here hold": (task("apple", P1, "here"), []),               # the LLM's ACTION line
    "cup from p2 to home place": (task("cup", P2, HOME, "place"), []),
}
for text, want in PARSE.items():
    got = brain.parse_fetch(text, M)
    assert got == want, (text, got, want)

for text in ("bring me the apple from p1", "take the cup from p2 to home", "p1에서 사과 가져와", "fetch the red cup"):
    assert brain.intent(text, M)[0] == "fetch", text
assert brain.intent("take the cup please", M) == ("pick", "cup")
assert brain.intent("move the cup", M) == ("move_object", "cup")
assert brain.intent("take me to p1", M) is None

base = task("apple", P1, "here")
CORRECT = {
    "no, from p2": ({"source": P2}, ["source"]),
    "not the apple, the cup": ({"object": "cup"}, ["object"]),
    "사과 말고 컵": ({"object": "cup"}, ["object"]),
    "to p3": ({"dest": {"marker": "p3"}}, ["dest"]),
    "put it on the table": ({"finish": "place"}, ["finish"]),
    "what": ({}, []),
}
for text, (fields, changed) in CORRECT.items():
    got, ch = brain.parse_correction(text, base, M)
    assert got == {**base, **fields} and ch == changed, (text, got, ch)
assert brain.parse_correction("just hold it", {**base, "finish": "place"}, M) == (base, ["finish"])
assert brain.parse_correction("p2", base, M, field="source")[0]["source"] == P2   # a bare answer to "from where?"

ANSWERS = {"yes": "yes", "okay": "yes", "yes please": "yes", "네": "yes", "응": "yes", "맞아": "yes",
           "no": "no", "아니": "no", "아니요": "no", "no, from p2": "correction", "not the apple, the cup": "correction",
           "cancel": "cancel", "never mind": "cancel", "취소": "cancel", "": None}
for text, want in ANSWERS.items():
    assert brain.confirm_answer(text) == want, (text, brain.confirm_answer(text))


def dialog(t, answers):
    """Run the dialog with fake ears / mouth / runner; returns (result, started task, what Lumi said)."""
    said, started, answers = [], [], list(answers)
    out = fetch_dialog.run(t, M, lambda s: answers.pop(0) if answers else (None, True), lambda en, ko: said.append(en),
                           lambda t, lang: f"take the {t['object']}.", started.append)
    return out, started, said


assert dialog(base, [("yes", True)])[:2] == ("started", [base])
assert dialog(base, [])[:2] == ("started", [base])                                   # silence = yes
out, started, said = dialog(base, [("no, from p2", True), ("okay", True)])
assert out == "started" and started == [{**base, "source": P2}] and len(said) == 2
out, started, said = dialog(base, [("no", True), ("not the apple, the cup", True), ("yes", True)])
assert out == "started" and started[0]["object"] == "cup" and said[1] == "What should I change?"
assert dialog(base, [("cancel", True)])[:2] == ("cancelled", [])
assert dialog(base, [("no", True)])[:2] == ("cancelled", [])                          # no, then silence
out, started, said = dialog(base, [("mumble", False), ("yes", True)])
assert out == "started" and said[1] == "Sorry, I didn't catch that."
out, started, said = dialog(task(None, P1, "here"), [("the banana", True), ("yes", True)])
assert out == "started" and started[0]["object"] == "banana" and said[0].startswith("Which object?")
out, started, said = dialog(task("cup", "here", None), [("p2", True), ("yes", True)])
assert started == [task("cup", "here", P2)] and said[0].startswith("Where should I bring it?")
assert dialog(task(None, P1, "here"), [])[:2] == ("cancelled", [])                    # a question, then silence

# typed commands: the model's answer is kept only where it names known words; a marker must be in the text
import json as _json
from assistant import brain as _b
_b._chat = lambda msgs, fmt=None: _json.dumps({"language": "en", "object": "apple", "colour": "red", "source": "PInit",
                                                "dest": "home", "finish": "place"})
fields, how = _b.fetch_from_text("bring me the ap", ["home", "PInit"])
assert how == "llm" and fields == {"finish": "place"}, fields       # "ap" is not "apple", places not said: dropped
fields, _ = _b.fetch_from_text("take the reddish appl from PInit over to home and set it down", ["home", "PInit"])
assert fields == {"source": {"marker": "PInit"}, "dest": {"marker": "home"}, "finish": "place"}, fields   # no guessing
fields, _ = _b.fetch_from_text("please carry over that red apple thing, PInit to home, set it down", ["home", "PInit"])
assert fields["object"] == "apple" and fields["colour"] == "red", fields      # words written in the text pass
_b._chat = lambda msgs, fmt=None: _json.dumps({"language": "other", "object": "apple", "source": "p1"})
assert _b.fetch_from_text("qizil olmani p1 dan olib kel", ["p1"]) == ({}, "other")   # English / Korean only
_b._chat = lambda msgs, fmt=None: _json.dumps({"object": "apple"})                  # no language: not trusted
assert _b.fetch_from_text("принеси яблоко", [])[1] == "other"
_b._chat = lambda msgs, fmt=None: _json.dumps({"language": "other", "object": "apple"})
assert _b.fetch_from_text("그거 가져와", [])[1] == "llm"                                # Hangul is Korean whatever it says
_b._chat = lambda msgs, fmt=None: _json.dumps({"language": "en", "object": "thing", "colour": "pink", "finish": "hold"})
assert _b.fetch_from_text("something nice", [])[0] == {"finish": "hold"}            # unknown words never pass
assert _b.fetch_from_text("bring the white cup from p2", ["p2"])[1] == "rules"
for text, want in {"give it to me": "give", "hand it over": "give", "put it on the table": "place",
                   "테이블에 놔": "place", "줘": "give", "hello": None, "menga ber": None, "shu yerga qo'y": None}.items():
    assert _b.held_command(text) == want, (text, _b.held_command(text))
t, _ = brain.parse_fetch("could you go to p1 and fetch the bottle", ["p1", "home"])
assert t["source"] == {"marker": "p1"} and t["object"] == "bottle", t           # where it goes first is the source
# ---------- mission read-back (docs/17): yes / silence starts, anything else cancels ----------
from assistant import steps as steps_mod
mission = [{"do": "pick", "object": "cup", "colour": None}, {"do": "move", "dir": "left", "m": 1.0}]
for answers, want in (([("yes", True)], "started"), ([(None, True)], "cancelled"), ([(None, True), ("yes", True)], "started"),
                      ([("no", True)], "cancelled"),
                      ([("hmm", False), ("네", True)], "started"), ([("cancel", True)], "cancelled"),
                      ([("go to p3 instead", True)], "cancelled")):
    heard, spoken, started = list(answers), [], []
    got = fetch_dialog.run_steps(mission, lambda s: heard.pop(0) if heard else (None, True),
                                 lambda en, ko: spoken.append(en), steps_mod.describe, started.append)
    assert got == want and bool(started) == (want == "started"), (answers, got, spoken)
    assert spoken[0] == "Take the cup, then turn left and drive 1 m. Is that right?", spoken
for text in ("yes", "Yes, you're right. Let's go.", "yes you are right", "that's right", "correct", "let's go", "do that",
             "go ahead", "okay do it", "yes, let's go, do that", "Yes. Yes.", "네", "맞아", "그래 가자", "좋아 해줘"):   # 2026-10-21
    heard, started = [(text, True)], []
    assert fetch_dialog.run_steps(mission, lambda s: heard.pop(0) if heard else (None, True), lambda en, ko: None,
                                  steps_mod.describe, started.append) == "started" and started, text
for text in ("no", "wait", "cancel", "no, let's go", "아니요", "잠깐만", "stop"):
    heard, started = [(text, True)], []
    assert fetch_dialog.run_steps(mission, lambda s: heard.pop(0) if heard else (None, True), lambda en, ko: None,
                                  steps_mod.describe, started.append) == "cancelled" and not started, text
# the answer is checked for Lumi's own voice against the question only: "Yes?" (the wake reply) 20 s before is not it
from audio import mouth as _mouth
_mouth._recent[:] = [(time.time() - 20, "Yes?"), (time.time() - 4, "Go to p10, wait 30 seconds, then come back here."),
                     (time.time() - 1, "Is that right?")]
from assistant.lumi import ANSWER_ECHO_S, Lumi as _Lumi
assert not _Lumi.own_echo("Yes. Yes.", ANSWER_ECHO_S) and _Lumi.own_echo("Yes. Yes.")
assert _Lumi.own_echo("Is that right?", ANSWER_ECHO_S)
_mouth._recent.clear()
# ---------- questions about what Lumi is doing: answered from the state, not by the LLM ----------
from assistant.lumi import STATUS_Q
for text in ("what are you doing?", "Lumi, where are you going?", "What are you holding", "what's in your hand",
             "뭐 해?", "뭐 하고 있어?", "어디 가?", "어디로 가고 있어?", "손에 뭐 들고 있어?"):
    assert STATUS_Q.search(text), text
for text in ("what can you do", "what is your name", "뭐 해줄 수 있어?", "p3로 가", "go to p3", "how are you doing today"):
    assert not STATUS_Q.search(text), text
# ---------- the end of a talk: a real closing (ends now), "okay" / "thank you" / "네" alone (ends after silence), or
# understanding / a check ("I see", "그렇구나", "really?"): answered, the talk goes on (lumi.talk_fate) ----------
from assistant.lumi import talk_fate as _fate

for t in ("see you next time", "bye", "okay, bye", "good night", "I have to go", "nice talking to you", "take care",
          "thank you for your time", "thanks, that's all", "that's it, thank you", "Okay, thank you. Bye.",
          "다음에 봬요", "들어가세요", "수고하세요", "안녕히 계세요", "이만 갈게요", "됐어요 고마워요", "네 감사합니다 안녕히 계세요",
          "go on", "good job", "well done", "가 보세요", "잘했어요", "수고했어요", "okay thanks bye bye", "고마워요, 다음에 봐요"):
    assert _fate(t) == "end", (t, _fate(t))
for t in ("okay", "Okay.", "thanks", "thank you", "Thank you.", "thanks a lot", "got it, thanks", "alright", "good",
          "okay, good", "고마워요", "감사합니다", "네 감사합니다", "알았어, 고마워", "오케이", "그래요", "네", "네.", "좋아", "땡큐",
          "오케이 땡큐", "okay 감사합니다", "Thanks, Lumi."):
    assert _fate(t) == "wait", (t, _fate(t))
for t in ("I see", "I see.", "got it", "I got you", "okay I see", "okay, I understand", "makes sense", "That makes sense.",
          "understood", "아 그렇구나", "그렇구나", "그렇군요", "알겠어요", "네 알겠습니다", "아하", "아, 그랬구나", "Uh huh.",
          "oh 그렇구나", "아 I see", "Okay, 알겠어요", "아 네",
          "I see?", "really?", "Really? I see.", "is that so?", "is that true?", "그래요?", "정말?", "그런가요?", "그렇구나?",
          "thanks, what time is it?", "okay, and where is p3?", "what is your name", "네 근데 몇 살이에요?",
          "good morning Lumi", "is this good for kids?", "I see a robot, what is it?", "좋아하는 음식 있어요?"):
    assert _fate(t) == "talk", (t, _fate(t))
for t in ("I see", "got it", "그렇구나", "알겠어요", "Uh huh.", "I see?", "그런가요?", "정말?", "is that so?", "oh 그렇구나"):
    assert _b.is_backchannel(t), t                      # asks nothing new: never looked up, never an action
for t in ("I see a robot, what is it?", "알겠어요 p3로 가요", "really go to p3", "그래요 그럼 p3로 가 주세요"):
    assert not _b.is_backchannel(t), t
print("fetch intents ok")

# ---------- which of several to pick: "the smaller cup", "왼쪽 컵" -> task["prefer"] (fetch._rank) ----------
from assistant import steps
from tasks import fetch
PREFER = {"take the smaller cup to p1": "small", "bring me the big cup": "big", "take the cup on the left to p1": "left",
          "get the red cup on the right side to p1": "right", "bring me the nearest cup": "near",
          "take the far one to p1": "far", "bring me the largest red cup": "big",
          "작은 컵 가져와": "small", "큰 컵 가져와": "big", "왼쪽 컵 가져와": "left", "오른쪽에 있는 컵 가져와": "right",
          "가까운 컵 가져와": "near", "제일 먼 컵 가져와": "far", "왼쪽에 있는 빨간 컵 가져와": "left",
          "bring me the cup": None, "go right 1 m and take the cup": None, "먼저 컵 가져와": None,
          "take the cup and put it on the smaller one": None, "take the cup and put it on the left table": None}
for text, want in PREFER.items():
    got, _ = brain.parse_fetch(text, M)
    assert got.get("prefer") == want, (text, got)
assert brain.parse_fetch("왼쪽에 있는 빨간 컵 가져와", M)[0]["colour"] == "red"
assert brain.parse_correction("no, the smaller one", task("cup", "here", "here"), M)[1] == ["prefer"]
SAID = {("small", "en"): "Take the smaller cup from here, bring it here and hold it.",
        ("left", "en"): "Take the cup on the left from here, bring it here and hold it.",
        ("far", "en"): "Take the farthest cup from here, bring it here and hold it.",
        ("small", "ko"): "여기에서 작은 컵을 가져와서 여기로 가져와서 들고 있을게요.",
        ("right", "ko"): "여기에서 오른쪽 컵을 가져와서 여기로 가져와서 들고 있을게요."}
for (prefer, lang), want in SAID.items():
    assert fetch.describe({**task("cup", "here", "here"), "prefer": prefer}, lang) == want, (prefer, lang)
# a mission's pick step carries it too, and its sentence says it
MISSION = {"take the smaller cup, go to p1 and put it on the table": ("small", "Take the smaller cup, go to p1"),
           "take the cup on the left, go to p2 and hand it over": ("left", "Take the cup on the left, go to p2"),
           "작은 컵 집고 p1으로 가서 테이블에 놔": ("small", None), "왼쪽 컵 집고 p2로 가서 건네줘": ("left", None)}
for text, (want, said) in MISSION.items():
    got, unread, _ = steps.read(text, M, llm=False)
    assert not unread and got[0]["do"] == "pick" and got[0].get("prefer") == want, (text, got, unread)
    assert said is None or steps.describe(got).startswith(said), steps.describe(got)
    assert said or steps.describe(got, "ko").startswith({"small": "작은 컵을", "left": "왼쪽 컵을"}[want]), steps.describe(got, "ko")
print("fetch prefer ok")
