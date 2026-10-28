"""The owner's arm and hand meanings (2026-10-23 night) through the voice / Command box route (command_check.rules =
lumi.route without the LLM): every handshake = wave, "give me your hand" / 손 줘 = reach, "give me it" / 줘 while
holding = give; the known faults of that day; negations, later times and remarks never move. No robot.

    .venv/bin/python tests/test_arm_words.py
"""
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import brain
from tests import command_check

M = ["p1", "p2", "p3", "home", "dock2"]
CASES = [   # (text, state, route)
    ("shake hand", "idle", "action:wave"), ("shake hands", "idle", "action:wave"), ("let's shake hands", "idle", "action:wave"),
    ("can you shake hand", "idle", "action:wave"), ("shake", "idle", "action:wave"), ("wave", "idle", "action:wave"),
    ("wave your hand", "idle", "action:wave"), ("악수하자", "idle", "action:wave"), ("악수해요", "idle", "action:wave"),
    ("악수 한번 해요", "idle", "action:wave"), ("빠빠이 해 줘", "idle", "action:wave"),
    ("give me your hand", "idle", "action:arm reach"), ("give me a hand", "idle", "action:arm reach"),
    ("손 줘", "idle", "action:arm reach"), ("손 내밀어", "idle", "action:arm reach"),
    ("give me it", "holding", "give"), ("줘", "holding", "give"), ("이리 줘", "holding", "give"),
    ("줘. 빨리.", "holding", "give"), ("들고 있는 거 나 주쇼", "holding", "give"), ("제가 가져갈게요", "holding", "give"),
    ("이제 내려놔도 돼", "holding", "place"), ("루미야 이제 내려놔도 돼", "holding", "place"),
    ("팔 접어, 아니 뻗어!", "idle", "action:arm reach"), ("reach out, no wait, fold it", "idle", "action:arm fold"),
    ("손 내밀어, 아니 접어, 아니 그냥 내밀어", "idle", "action:arm reach"),
    ("take this cup", "idle", "receive cup"), ("녹색 물병 집어 줘", "idle", "action:pick green bottle"),
    ("원래 자리에 좀 갖다 놔 줘", "holding", "action:put back"),
    # no motion
    ("don't shake hands", "idle", None), ("악수하지 마", "idle", None), ("팔 접지 말라니까", "idle", None),
    ("빨간 사과 잡지 말라니까", "idle", None), ("작은 테이블에 놓지 말라니까", "holding", None),
    ("자, 악수하자... 됐다 마", "idle", None), ("arm 뻗어 해 주라... 됐어, forget it", "idle", None),
    ("쉬는 시간 끝나고 팔 쭉 뻗어", "idle", None), ("다음 주에 사과 좀 들어 줘", "idle", None),
    ("아까는 팔 원래대로 돌리는 거 안 하더라", "idle", None), ("you better not pass it over", "holding", None),
    ("watch, it's going to hand it to me", "holding", None), ("give me five!", "holding", None),
    ("don't drop it in my hand", "holding", None), ("thanks, I'll take it from here", "idle", None),
    ("김 대리 녹색 잔 좀 들어", "idle", None), ("wave 파마 어때?", "idle", None),
    ("팔 혹시 집어넣어 줄 수 있어요, 아니 어이 손 좀 내밀어 줘라", "idle", "action:arm reach"),
    # 23:30-00:00
    ("open your claw please", "holding", "refuse"), ("손을 펴 주십시오", "holding", "refuse"),
    ("그리퍼 열어 줘", "holding", "refuse"), ("you think you could give it here?", "holding", "give"),
    ("저 주면 안 돼?", "holding", "give"), ("루미야이리주세요", "holding", "give"), ("내 송에 올려 주라", "holding", "give"),
    ("있던 곳에 도로 놔 줘", "holding", "action:put back"), ("robot, return the cup!", "holding", "action:put back"),
    ("에구 손 도", "idle", "action:arm reach"), ("팔 피 주쇼", "idle", "action:arm reach"),
    ("저한테 송 주십시오", "idle", "action:arm reach"), ("루미야 기본 pose 로 해 주세요", "idle", "action:arm fold"),
    ("손 얼른 내려 줘", "idle", "action:arm fold"), ("look at me, no, just wave", "idle", "action:wave"),
    ("take the cup, sorry I mean the white bottle", "idle", "action:pick white bottle"),
    ("take the white cup, wait, the apple", "idle", "action:pick apple"),
    ("테이블에 있는 오렌지 집으시오", "idle", "action:pick orange"), ("문 열어 줘", "idle", None), ("컵 들어 있어", "idle", None),
    # 00:00-00:15
    ("있잖아 악수 한번 할까요?", "idle", "action:wave"), ("would it be possible to wave at me?", "idle", "action:wave"),
    ("손 흔들어 주면 안 돼?", "idle", "action:wave"), ("do you know how to wave?", "idle", None), ("Jake, wave to the robot", "idle", None),
    ("p2에서 green apple bring 해", "idle", "action:fetch"), ("손가락 한번 모아 봐", "idle", "action:arm close"),
    ('"give it to me" is a nice English phrase', "holding", None), ("몸 5센티만 내려 주세요", "holding", "action:lift"),
    ("테이블에 놔 줄래? 영상 찍고 있어", "holding", "place"), ("it's my birthday, put that back where you found it!", "holding", "action:put back"),
    ("Lumi buddy, any chance you could pick up the apple?", "idle", "action:pick apple"),
    # 2026-10-27: taught poses by name (look = fold)
    ("Let's take look position.", "idle", "action:arm fold"), ("Let's put your hand look position.", "idle", "action:arm fold"),
    ("let's bring your hand look position", "idle", "action:arm fold"), ("let's come your hand look position", "idle", "action:arm fold"),
    ("look position", "idle", "action:arm fold"), ("go to look", "idle", "action:arm fold"), ("hand to look", "idle", "action:arm fold"),
    ("bring your hand to look position", "idle", "action:arm fold"), ("carry position", "idle", "action:arm carry"),
    ("put your arm in carry position", "idle", "action:arm carry"), ("carry", "idle", "action:arm carry"),
    ("arm to carry", "idle", "action:arm carry"), ("ready position", "idle", "action:arm ready"),
    ("carry position", "holding", "action:arm carry"), ("룩 포지션", "idle", "action:arm fold"), ("룩 자세로", "idle", "action:arm fold"),
    ("팔 룩으로", "idle", "action:arm fold"), ("캐리 자세", "idle", "action:arm carry"), ("팔 캐리로 해 줘", "idle", "action:arm carry"),
    ("팔 원위치", "idle", "action:arm fold"), ("팔 내려", "idle", "action:arm fold"),
    ("what is the look position?", "idle", None), ("can you carry this?", "idle", None), ("I like your look position", "idle", None),
    ("캐리 자세가 뭐야?", "idle", None), ("룩 자세로 가지 마", "idle", None), ("don't go to carry position", "idle", None),
    ("put your arm in tuck position", "idle", None), ("get ready", "idle", None), ("are you ready?", "idle", None),
    ("what does carry position mean?", "idle", None), ("look at my hand", "idle", None),
]
MOVES = ("action:", "give", "place", "receive", "mission", "chain")

bad = []
for text, state, want in CASES:
    try:
        got = command_check.rules(text, state, M, brain.Brain())
    except command_check.NoLLM:
        got = None
    got = got if got not in ("llm?",) else None
    if want is None:
        if got and got.startswith(MOVES):
            bad.append((text, state, got, "no motion"))
    elif not (got or "").startswith(want):
        bad.append((text, state, got, want))
for text in ("again", "one more time please", "한 번 더", "또 해 줘"):      # right after a wave: the wave again
    b = brain.Brain()
    b.history.append(("wave", "ACTION: wave -"))
    got = command_check.rules(text, "idle", M, b)
    if got != "action:wave":
        bad.append((text, "after a wave", got, "action:wave"))
assert not bad, "\n".join(map(str, bad))
print(f"arm words ok ({len(CASES)} cases)")
