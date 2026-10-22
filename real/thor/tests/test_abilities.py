""""What can you do?" (assistant/abilities.py and lumi.answer()'s routing): which words ask it, the short overview,
the rest on "tell me more" / "yes" right after. No robot, no speaker, no LLM. python tests/test_abilities.py"""
import types

from assistant import abilities as ab
from assistant import lumi
from audio import mouth

ASKED = {"What can you do?": True, "what can you do": True, "Lumi, what can you do for me?": True,
         "what are your abilities": True, "what are you capable of?": True, "what do you do?": True,
         "what else can you do?": True, "뭐 할 수 있어?": True, "뭘 할 수 있어요?": True, "넌 무슨 일을 해?": True,
         "어떤 일을 할 수 있어요?": True, "할 수 있는 게 뭐야?": True, "무슨 기능이 있어?": True, "루미는 뭐 하는 로봇이야?": True,
         "Lumi, 뭐 할 수 있어?": True,
         "what can you do with your arm?": False, "팔로 뭘 할 수 있어?": False, "can you do a dance?": False,
         "what are you doing?": False, "지금 뭐 해?": False, "what can I do?": False, "뭐 할까?": False,
         "what can't you do?": False, "what time is it": False, "노래 할 수 있어?": False, "sing a song": False}
wrong = {t: want for t, want in ASKED.items() if ab.asked(t) != want}
assert not wrong, wrong
for lang in ("en", "ko"):                                # 2-3 spoken sentences, then the rest
    assert 2 <= len(mouth.sentences(ab.SHORT[lang])) <= 3, ab.SHORT[lang]
    assert len(ab.LONG[lang]) > len(ab.SHORT[lang])
assert all(w in ab.SHORT["en"] for w in ("talk", "internet", "pick things up", "places", "follow", "wave", "sing"))
assert all(w in ab.LONG["en"] for w in ("wearing or holding", "from your hand", "follow me", "Arirang"))
assert not any(w in ab.LONG["en"] + ab.SHORT["en"] for w in ("table", "behind", "charge", "mission"))
assert not any(w in ab.LONG["ko"] + ab.SHORT["ko"] for w in ("테이블", "뒤를", "충전", "미션"))

SHORT = ab.SHORT_MARK + "\n..."
for t in ["tell me more", "yes", "sure", "okay", "what else?", "네", "더 알려 줘", "자세히 알려 주세요", "그리고요?"]:
    assert ab.answer(t, "en", SHORT)[0] == "long", t
    assert ab.answer(t, "en", "ACTION: none -\nHi") is None, t       # not after another answer
for t in ["go to p3", "no thanks", "아니요", "sing a song"]:
    assert ab.answer(t, "en", SHORT) is None, t
assert ab.answer("또 뭐 할 수 있어?", "ko")[0] == "long"

# lumi.answer(): the overview by rule (before talk_fate, so "yes" after "Shall I tell you more?" is answered)
said = []
lumi.LOG_FILE = "/dev/null"
mouth.say = lambda text, lang=None, abort=None: said.append(text)
lumi.ears.understood = lambda *a: True
lumi.ears.last_stt = {"language": "english", "logprob": -0.1}
L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.current, L.closing_pending = "en", None, None
L.brain = types.SimpleNamespace(history=[])
L.follow_stop = lambda text: False
L.keep_listening = lambda: None
L.speak_abort = lambda: False
L.drive_words = lambda text: (_ for _ in ()).throw(AssertionError(f"drive words got {text!r}"))
L.answer("What can you do?")
assert said[-1] == ab.SHORT["en"], said
L.answer("yes")
assert said[-1] == ab.LONG["en"], said
lumi.ears.last_stt = {"language": "korean", "logprob": -0.1}
L.answer("넌 무슨 일을 해?")
assert said[-1] == ab.SHORT["ko"], said
L.answer("네")
assert said[-1] == ab.LONG["ko"], said
print("abilities ok")
