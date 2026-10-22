"""Sounds that are not said to Lumi, for tests/asr_check.py --cases 3: room noise only, people talking in the room,
"uh" / "wow" / laughs. Right is whatever Lumi does not act on: no wake word, no motion, nothing it would answer
as a question to it (kind "noise"; say [] is noise only).
"""
CASES = []


def add(lang, text, *say):
    CASES.append({"kind": "noise", "lang": lang, "text": text, "say": list(say)})


for k in range(12):
    add("none", f"(room noise {k})")
for t in ["Uh.", "Um.", "Hmm.", "Wow.", "Oh.", "Ah.", "Ha ha ha.", "Mm-hmm.", "Oops.", "Whoa.", "Huh?", "Yeah, yeah."]:
    add("en", t, ("en", t))
for t in ["음.", "어.", "아.", "와.", "헐.", "흠.", "오.", "하하하."]:
    add("ko", t, ("ko", t))
for t in ["I think the meeting is at three.", "Did you send the file?", "Let's get some coffee later.",
          "The printer on the second floor is broken again.", "She said the demo went well.",
          "Can you pass me that pen?", "We should leave in ten minutes.", "Where did you park your car?"]:
    add("en", t, ("en", t))
for t in ["회의 몇 시에 해요?", "점심 뭐 먹을까?", "그 파일 보냈어요?", "오늘 너무 피곤하다.", "커피 마시러 갈래?",
          "이거 내일까지 해야 돼요.", "주차 어디에 했어?", "아까 그 사람 누구야?"]:
    add("ko", t, ("ko", t))
