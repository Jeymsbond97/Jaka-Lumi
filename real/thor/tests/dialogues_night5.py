"""Night-5 talks of T1 (own cases, not a blind set): unclear fragments. Words cut off by the speech recogniser
("지금 몇...", "Can you"), odd noun phrases ("서울의 지구.", "Seoul's district."), statements that mean nothing to Lumi
("저는 오후 6시 반이에요.") and filler get "sorry, again?" / "다시 한 번 말씀해 주시겠어요?" (or, inside a talk, a reply about
that talk), never an unrelated fact about Lumi (its microphones, lidar, cameras, maker). English and Korean at every
level (반말 / 해요체 / 하십시오체 / friendly / honorific / dialect), mixed; the date and time from the clock.

    .venv/bin/python tests/dialogues_night5.py [only]   # -> logs/t1n5/night5_check.json
"""
import sys

from tests.dialogues import T, D
from tests.dialogues_world import N, NK, OFFER, RUDE

F, FK = [OFFER], [OFFER, RUDE]     # a fragment's reply: asking again is right here (N / NK forbid it)

AGAIN = (r"didn't catch|did not catch|didn't quite|say (?:it|that) again|could you repeat|repeat that|one more time|"
         r"what do you mean|what did you mean|못 알아|다시 (?:한 ?번 )?말씀|다시 말씀|무슨 말씀|무슨 뜻|다시 한 ?번|잘 못 들|"
         r"잘 모르겠|이해하지 못|무엇을 말씀|어떤 (?:뜻|의미|말씀|점)|말씀해 주|궁금하신|not sure what|not sure which|"
         r"explain|tell me more|which one|어느 which .* you mean|do you mean|you mean\b")
SELF = (r"microphone|\bmics?\b|lidar|laser|scanner|camera|ultrasonic|bumper|JAKA|Cutshion|made me|developed me|"
        r"robot assistant|my (?:arm|head|gripper|battery|wheels)|마이크|라이다|레이저|스캐너|카메라|초음파|범퍼|자카|쿳션|"
        r"만들었|만든 |개발한|로봇 비서|제 (?:팔|머리|고개|그리퍼|배터리|바퀴)")
TIME = r"\d+ ?(?:시|:\d\d)|\b(?:am|pm|a\.m\.|p\.m\.)|오전|오후|o'clock"
DATE = r"\d+ ?월 ?\d+ ?일|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b"
Q = "unclear | none"            # asking again may come as unclear or as none with the words of asking again

DIALOGUES_NIGHT5 = [
    D("visitor", "fragment_ko_start", "ko",
      T("지금 몇...", Q, must=[AGAIN], no=FK + [SELF], check="잘린 말: 다시 말해 달라고 함, 자기 소개 아님"),
      T("서울의 지구.", Q, must=[AGAIN], no=FK + [SELF], check="뜻이 불분명: 다시 말해 달라고 함, 검색 아님"),
      T("저는 오후 6시 반이에요.", Q, must=[AGAIN + "|6시 반|여섯 시 반"], no=FK + [SELF],
        check="뜻이 불분명한 말: 무슨 뜻인지 묻거나 짧게 받음; 라이다 / 카메라 얘기 아님"),
      T("고마워요, 갈게요.", "end")),
    D("visitor", "fragment_ko_after_time", "ko",
      T("지금 몇 시예요?", must=[TIME], no=NK, check="시계의 시각"),
      T("지금 몇...", Q + " | none", must=[AGAIN + "|" + TIME], no=FK + [SELF], check="잘린 말: 시각을 다시 말하거나 다시 묻기"),
      T("몇이요? 지금은 몇이요?", must=[TIME], no=FK + [SELF], check="시각"),
      T("오늘 며칠이에요?", must=[DATE], no=NK, check="오늘 날짜 (시계)"),
      T("네 고마워요.", "-")),
    D("visitor", "fragment_en_start", "en",
      T("Can you", Q, must=[AGAIN], no=F + [SELF], check="cut off: asks again, no self-description"),
      T("Seoul's district.", Q, must=[AGAIN], no=F + [SELF], check="unclear phrase: asks again"),
      T("A-Q-N. Nunn.", Q, must=[AGAIN], no=F + [SELF], check="nonsense: asks again"),
      T("I'm half past six.", Q, must=[AGAIN + "|six|6:30"], no=F + [SELF], check="unclear statement: asks what they mean"),
      T("Okay, bye.", "end")),
    D("visitor", "fragment_en_time", "en",
      T("What is the time?", must=[TIME], no=N, check="the clock's time"),
      T("And what's the...", Q + " | none", must=[AGAIN + "|" + DATE + "|" + TIME], no=F + [SELF],
        check="cut off: asks again (or the date / time)"),
      T("What's the date today?", must=[DATE], no=N, check="today's date from the clock"),
      T("the uh the", Q, must=[AGAIN], no=F + [SELF], check="filler: asks again"),
      T("Thanks, that's all.", "end")),
    D("student", "fragment_ko_banmal", "ko",
      T("야 그 저기 그거...", Q, must=[AGAIN], no=FK + [SELF], check="filler: 다시 말해 달라고 함"),
      T("어 그러니까 그 몇 개...", Q, must=[AGAIN], no=FK + [SELF], check="잘린 말"),
      T("부산의 바다.", Q, must=[AGAIN], no=FK + [SELF], check="뜻이 불분명"),
      T("됐어, 갈게.", "end")),
    D("office worker", "fragment_ko_hasipsio", "ko",
      T("실례지만 혹시 그...", Q, must=[AGAIN], no=FK + [SELF], check="잘린 말"),
      T("그러니까 제가 여쭤보고 싶은 것은...", Q, must=[AGAIN], no=FK + [SELF], check="잘린 말"),
      T("저는 3층입니다.", Q + " | none", must=[AGAIN + "|3층"], no=FK + [SELF], check="문맥 없는 말: 짧게 받거나 다시 묻기"),
      T("수고하십시오.", "end")),
    D("grandmother", "fragment_ko_honorific_dialect", "ko",
      T("아이고 그 뭐시냐...", Q, must=[AGAIN], no=FK + [SELF], check="사투리 filler"),
      T("거시기 그 머꼬...", Q, must=[AGAIN], no=FK + [SELF], check="사투리 filler"),
      T("할머니께서 그 저...", Q, must=[AGAIN], no=FK + [SELF], check="높임말 잘린 말"),
      T("고맙데이, 가께.", "end")),
    D("parent", "fragment_mixed", "ko",
      T("지금 time이 몇...", Q + " | none", must=[AGAIN + "|" + TIME], no=FK + [SELF], check="잘린 말: 시각 또는 다시 묻기"),
      T("그 robot의 그...", Q, must=[AGAIN], no=FK + [SELF], check="잘린 말"),
      T("Seoul 그 district.", Q, must=[AGAIN], no=FK + [SELF], check="뜻이 불분명"),
      T("오케이 땡큐, 바이.", "end")),
]


def main(only=None):
    """Each talk through tests/dialogue_check.run_turn (lumi.answer()'s order) and dialogue_check.problems; no judge
    (followup_check would count asking again as a fault, and here it is the right answer)."""
    import json
    from tests import dialogue_check as dc
    from tests.conversation_check import markers
    marks, rows = markers(), []
    for i, d in enumerate(DIALOGUES_NIGHT5, 1):
        if only and only not in d["topic"]:
            continue
        b = brain.Brain()
        for j, turn in enumerate(d["turns"], 1):
            lang = dc.turn_lang(turn)
            r, reply, first, _ = dc.run_turn(b, turn["say"], lang, marks)
            probs = dc.problems(turn, lang, r, reply, first is not None) if turn["expect_action"] != "-" else None
            rows.append({"topic": d["topic"], "turn": j, "say": turn["say"], "got": r, "reply": reply, "problems": probs})
            print(f"{'-   ' if probs is None else 'OK  ' if not probs else 'FAIL'} {d['topic']} t{j} {turn['say']!r} -> [{r}] {reply[:110]!r} {probs}",
                  flush=True)
    scored = [r for r in rows if r["problems"] is not None]
    ok = sum(not r["problems"] for r in scored)
    print(f"right {ok}/{len(scored)} turns")
    out = dc.ROOT / "logs" / "t1n5" / "night5_check.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    from assistant import brain
    main(sys.argv[1] if len(sys.argv) > 1 else None)
