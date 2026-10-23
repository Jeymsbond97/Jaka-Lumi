"""What Lumi heard live (logs/lumi.log, logs/lumi_console.log 2026-10-21 and 10-22) against what was said, judged
from the context (the turns before and after, Lumi's own lines, the owner's usual wording). The owner speaks English
with a Korean / Uzbek accent: "Let's go P9.", "Look at the back side.", "What is my hand?".

    .venv/bin/python tests/asr_live.py            # text check: the heard text, as Lumi reads it, routes as the said one
    .venv/bin/python tests/asr_live.py --real     # also the real clips in logs/asr_real/ through whisper (local only)
    .venv/bin/python tests/asr_live.py --real --port 8099   # a whisper-server already running there

LIVE: (heard, whisper's language, said). said "" = not said to Lumi (noise, music, people talking to each other,
Lumi's own voice): right is no wake word and no motion. Language "korean" on Latin letters is understood() refusing
it ("say it again"): those need ears' retry and are checked by tests/test_ears.py, here they only count.
REAL: the clip (logs/asr_real/<day>/<HHMMSS>.wav, the robot's logs/heard kept) -> said, "" or None (not judged).
"""
import difflib
import re
import sys
import wave
from pathlib import Path

import numpy as np

from assistant import brain, lumi
from audio import ears
from tests.asr_check import MARKERS, plain, route

ROOT = Path(__file__).resolve().parents[1]
TEXT_CLOSE = 0.6             # difflib ratio of the words for a question (LLM) to count as heard; the said texts
                             # here are judged, not exact, so looser than tests/asr_check.py

LIVE = [
    # 2026-10-21
    ("What's your name?", "english", "What's your name?"),
    ("What is your hand? What is it in my hand?", "english", "What is in my hand?"),
    ("What is my hand?", "english", "What is in my hand?"),
    ("Look at it again.", "english", "Look at it again."),
    ("Lumi.", "english", "Lumi."),
    ("루미야.", "korean", "루미야."),
    ("*sad*", "english", ""), ("*Clap*", "english", ""), ("Hmm.", "english", ""), ("Um.", "english", ""),
    ("Hi Lumi.", "english", "Hi Lumi."),
    ("오늘 난시가 어때요?", "korean", "오늘 날씨가 어때요?"),
    ("What is your name?", "english", "What is your name?"),
    ("Lumi. Lumi.", "korean", "Lumi. Lumi."),
    ("You got it.", "korean", "You got it."),
    ("Can you hear this?", "english", "Can you hear this?"),
    ("Go to pit 9.", "english", "Go to P9."),
    ("Let's go. Final point.", "english", "Let's go final point."),
    ("Lumi, come to me.", "english", "Lumi, come to me."),
    ("Let's go to home.", "english", "Let's go home."),
    ("Lumi. Stop it.", "english", "Lumi, stop it."),
    ("Let's go P10.", "english", "Let's go P10."),
    ("Stop it.", "english", "Stop it."),
    ("Let's take it.", "english", "Let's take it."),
    ("Let's bake one meter.", "english", "Let's back one meter."),
    ("Come back P9.", "english", "Come back to P9."),
    ("Let's come to P9.", "english", "Let's come to P9."),
    ("Let's go P9.", "english", "Let's go P9."),
    ("Let's go back.", "english", "Let's go back."),
    ("Stop, stop.", "english", "Stop, stop."),
    ("Big one meter.", "english", "Back one meter."),
    ("Let's bake one metal.", "english", "Let's back one meter."),
    ("Let's come to me.", "english", "Let's come to me."),
    ("Let's come to P9 point.", "english", "Let's come to P9 point."),
    ("Stop Lumi.", "english", "Stop, Lumi."),
    ("What is the color of my t-shirt?", "english", "What is the color of my t-shirt?"),
    ("Can you give me information about the coaching company?", "english",
     "Can you give me information about the Cutshion company?"),
    ("How many people work in a coaching company?", "english", "How many people work in Cutshion company?"),
    ("Lumi. Lumi. Let's go pick five point.", "english", "Lumi, let's go P5 point."),
    ("Let's go P5.", "english", "Let's go P5."),
    ("Let's go P10 point and wait 30 seconds then come back here again.", "english",
     "Let's go P10 point and wait 30 seconds then come back here again."),
    ("Wait.", "korean", "Wait."),
    ("What would you like to do?", "korean", "What would you like to do?"),
    ("Let's copy 10 point.", "english", "Let's go P10 point."),
    ("Let's go P5 point.", "english", "Let's go P5 point."),
    ("Keep going.", "english", "Keep going."),
    ("Lumi stopped.", "english", "Lumi, stop."),
    ("Can you see me?", "english", "Can you see me?"),
    ("What is the color of my shirt?", "english", "What is the color of my shirt?"),
    ("Let's go 9 point.", "english", "Let's go P9 point."),
    ("Can you sing song?", "korean", "Can you sing a song?"),
    ("Let's say song.", "korean", "Let's sing a song."),
    ("Look at me.", "english", "Look at me."),
    ("Look at left side.", "english", "Look at the left side."),
    ("Lumi, can you see me?", "english", "Lumi, can you see me?"),
    ("Let's follow me.", "english", "Let's follow me."),
    ("Let's go back one meter.", "english", "Let's go back one meter."),
    ("Let's come back to 20 cm.", "english", "Let's come back 20 cm."),
    ("What is the color of my pants?", "english", "What is the color of my pants?"),
    ("What is the hand of my hand?", "english", "What is in my hand?"),
    ("What is it? My hand.", "english", "What is in my hand?"),
    ("Lumi, look at the back.", "english", "Lumi, look at the back."),
    ("Look at the back side.", "english", "Look at the back side."),
    ("Look at back side.", "english", "Look at the back side."),
    ("Look at behind.", "english", "Look behind."),
    ("Look at behind side.", "english", "Look at the back side."),
    ("Look at big side.", "english", "Look at the back side."),
    ("Say it again. Look at the big side.", "english", "Look at the back side."),
    ("Look at the right side.", "english", "Look at the right side."),
    ("Look at the left side.", "english", "Look at the left side."),
    ("식사하고 오세요. 네. 맛있게 드세요.", "korean", ""),
    ("Follow me.", "english", "Follow me."),
    ("Good job.", "english", "Good job."),
    ("Oh, hey.", "english", ""), ("Uh.", "english", ""), ("I love you.", "english", ""), ("Yeah.", "english", ""),
    ("Chinat, shut up, bravo.", "english", ""), ("그럼 무슨 세일까?", "korean", ""), ("네.", "korean", ""),
    ("Leo.", "english", ""), ("감사합니다.", "korean", ""), ("Uh huh.", "english", ""), ("Wow.", "english", ""),
    ("Bye.", "english", ""),
    # 2026-10-22
    ("-끝-", "korean", ""), ("-", "korean", ""), ("자막 제공 및 자막 제공 및 광고를 포함하고 있습니다.", "korean", ""),
    ("시청해주셔서 감사합니다.", "korean", ""), ("아멘", "korean", ""), ("ТРЕВОЖНАЯ МУЗЫКА", "korean", ""),
    ("오늘 날씨가 어때요?", "korean", "오늘 날씨가 어때요?"),
    ("서울에서 7시 후에 날씨 어때요?", "korean", "서울에서 7시 후에 날씨 어때요?"),
    ("What kind of stuff you can do?", "english", "What kind of stuff can you do?"),
    ("Start with one.", "english", "Start with one."),
    ("Who created you?", "english", "Who created you?"),
    ("How old are you?", "english", "How old are you?"),
    ("호월달요.", "korean", "How old are you?"),
    ("호화 다리.", "korean", "How old are you?"),
    ("호월달의 요", "korean", "How old are you?"),
    ("호월 대휴.", "korean", "How old are you?"),
    ("호valde arıyor.", "korean", "How old are you?"),
    ("호val도 알아요.", "korean", "How old are you?"),
    ("Hovalt arıyor.", "english", "How old are you?"),
    ("What kind of company? What kind of company Kutsche? Let's talk about Kutsche and Company.", "english",
     "What kind of company? What kind of company Cutshion? Let's talk about Cutshion company."),
    ("Let's talk more about Cutshion company.", "english", "Let's talk more about Cutshion company."),
    ("Where is it located? Kuchung company.", "english", "Where is it located? Cutshion company."),
    ("Let's talk more about the Kuching Company.", "english", "Let's talk more about the Cutshion company."),
    ("How can I contact with the company?", "english", "How can I contact the company?"),
    ("Let's change the music.", "english", "Let's change the music."),
    ("Can you look at behind side?", "english", "Can you look at the back side?"),
    ("A bit more.", "english", "A bit more."),
    ("Look at left side a bit more.", "english", "Look at the left side a bit more."),
    ("More again.", "english", "More again."),
    ("Can you follow me?", "english", "Can you follow me?"),
    ("Okay, let's fall lonely.", "english", "Okay, let's follow me."),
    ("Кам туне.", "korean", "Come to me."),
    ("Let's come back.", "english", "Let's come back."),
    ("Stop.", "english", "Stop."),
    ("Come to me.", "english", "Come to me."),
    ("Let's come back one meter.", "english", "Let's come back one meter."),
    ("Let's look at the left side.", "english", "Let's look at the left side."),
    ("Okay, stop it.", "english", "Okay, stop it."),
    ("What is it my hand?", "english", "What is in my hand?"),
    ("What is that my hand?", "english", "What is in my hand?"),
    ("Let's fall of Him.", "english", "Let's follow me."),
    ("Okay, let's come here.", "english", "Okay, let's come here."),
    ("3 düşüme.", "korean", None),
    ("Okay, let's go P9.", "english", "Okay, let's go P9."),
    ("What about my watch?", "english", "What about my watch?"),
    ("Is that blue?", "english", "Is that blue?"),
    ("No, it's my right hand.", "english", "No, it's my right hand."),
    ("Do you know my name?", "english", "Do you know my name?"),
    ("이름은 뭐예요?", "korean", "이름은 뭐예요?"),
    ("Where is my left hand?", "english", "Where is my left hand?"),
    ("Can you look at the right side?", "english", "Can you look at the right side?"),
    ("Let's go back. P5.", "english", None),          # "go back to P5" or "go back, P5": Lumi should ask
    ("No, let's go P5.", "english", "No, let's go P5."),
    ("It's the right hand.", "english", "It's the right hand."),
    ("Is it white?", "english", "Is it white?"),
    ("What is it?", "korean", "What is it?"),
    ("Let's come to P5 point.", "english", "Let's come to P5 point."),
    ("Let's count to p5.", "english", "Let's come to P5."),
    ("Modern communication.", "english", ""),
    ("네, 수고하셨습니다.", "korean", ""),
    ("It's bringing your insulin to the hand.", "english", ""),   # Lumi's "Please bring it near its look pose by hand."
    ("Look at the big side.", "english", "Look at the back side."),
    ("Mm.", "english", ""), ("하고 있어요?", "korean", ""),
    ("James가 이거 계정으로 어카운트를 했었고, 그 다음에 K-PASK 등록을 했어요.", "korean", ""),
    ("What are you looking at?", "english", ""), ("Keep it safe. Yeah, you on?", "english", ""),
]

REAL = {   # logs/asr_real/1022: the last 50 utterances of 2026-10-22 (17:51-18:44), listened to through the log
    "175142": "Lumi.", "175150": "Look at the left side.", "175156": "More again.", "175220": "Let's come to P5 point.",
    "175232": "Let's come to P5.", "175247": "Let's come to P5.", "175249": "", "175346": "", "175348": "",
    "175355": "", "175402": "", "175407": "", "175409": "", "175414": "", "182444": "", "182447": "", "182501": "",
    "182504": "", "182515": "", "182519": "", "182757": "", "182819": "", "182836": "", "183458": "", "183502": "",
    "183510": "Lumi.", "183519": "Can you see me?", "183527": "So let's follow me.", "183536": "Let's follow me.",
    "183549": "Look at the back side.", "183605": "Look at the back side.", "183734": "", "183739": "", "183921": "",
    "183923": "", "183945": "", "183955": "", "184000": "", "184404": "", "184429": "Lumi.",
    "184439": "Look at the left side.", "184447": "A bit more.", "184456": "One more.", "184459": "One more.",
}   # not judged: 175201, 175210, 175212, 175214 (unclear what was said), 182813 (someone's "네 감사합니다"), 184451


def judge(heard, said, b):
    """right / wrong (why)."""
    if said == "":
        if heard and (lumi.WAKE.search(heard) or lumi.HELLO_ONLY.match(heard)):
            return "wake word"
        got = route(heard, b) if heard else "llm"
        return got if re.match(r"action|receive|give|place|stop|mission|sing", got) else ""
    if not heard:
        return "nothing heard"
    if re.fullmatch(r"\W*(?:lumi|루미야?)\W*(?:(?:lumi|루미야?)\W*)?", said, re.I):
        return "" if lumi.WAKE.search(heard) else "no wake word"
    want, got = route(said, b), route(heard, b)
    if want != got:
        return f"{got} (want {want})"
    r = difflib.SequenceMatcher(None, " ".join(plain(said)), " ".join(plain(heard))).ratio()
    return f"text {r:.2f}" if want == "llm" and r < TEXT_CLOSE else ""


def text_check():
    b, bad, n, lang = brain.Brain(), [], 0, 0
    for heard, tag, said in LIVE:
        if said is None:
            continue
        if tag == "korean" and not re.search(r"[가-힣]", heard) and said and ears.names(heard) == heard:
            lang += 1                                        # left to ears' retry (tests/test_ears.py)
            continue
        n += 1
        why = judge(ears.names(heard), said, b)
        if why:
            bad.append(f"  {heard!r} -> {ears.names(heard)!r}: {why}   (said {said!r})")
    print(f"live texts: {n - len(bad)} of {n} read as said ({lang} more tagged Korean in Latin letters: ears' retry)")
    print("\n".join(bad))
    return len(bad)


def real_check(args):
    from tests import asr_check
    if "--port" in args:
        asr_check.STT_PORT = int(args[args.index("--port") + 1])
    asr_check.start_server()
    b, bad, n = brain.Brain(), [], 0
    for clip, said in sorted(REAL.items()):
        f = ROOT / "logs" / "asr_real" / "1022" / f"{clip}.wav"
        if not f.exists():
            continue
        with wave.open(str(f)) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        heard = ears.transcribe(audio)
        if not ears.understood() and not (heard and ears.heard_clearly() and lumi.own_command(heard, "")):
            heard = heard if said == "" else ""          # Lumi would ask again: lost
        n += 1
        why = judge(heard, said, b)
        if why:
            bad.append(f"  {clip} {heard!r}: {why}   (said {said!r})")
    print(f"real clips: {n - len(bad)} of {n} right")
    print("\n".join(bad))
    return len(bad)


if __name__ == "__main__":
    wrong = text_check()
    if "--real" in sys.argv:
        wrong += real_check(sys.argv[1:])
    sys.exit(1 if wrong else 0)
