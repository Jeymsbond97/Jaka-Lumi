"""Commands, questions and asides through the voice / Command box route (command_check.rules = lumi.route without the
LLM), night 4: tag questions, take-backs at every Korean level, other people addressed, polite stops, chains that are
one order, amounts not read. A wrong motion is the worst error: None (the LLM reads it) is right for the no-motion
cases. No robot.

    .venv/bin/python tests/test_route_words.py
"""
from assistant import brain, detour
from tests import command_check

M = ["p1", "p2", "p3", "p5", "p6", "home", "dock2"]
CASES = [   # (text, state, route)
    # a statement with a tag, an ability said back: asked
    ("you went to P5 earlier, right?", "idle", None), ("you can lift your arm, right?", "idle", None),
    ("너 팔 접을 수 있지, 그치?", "idle", None), ("너 팔 접을 수 있지?", "idle", None), ("wave, right?", "idle", "action:wave"),
    ("손 흔들고 나 봐, 알았지?", "idle", "chain:wave+look_me"), ("팔 접어, 알겠죠?", "idle", "action:arm fold"),
    ("팔 뻗을 줄 아세요?", "idle", None), ("팔을 뻗을 줄 압니까?", "idle", None), ("robot, you know how reach out to me?", "idle", None),
    ("robot can say hi with your hand or not? I just ask", "idle", None), ("멸 센티까지 잡아?", "idle", None),
    ("Back to your arm, what did you say?", "idle", None),
    # one order, not a chain
    ("손 흔들어서 작별 인사 해 주시겠어요?", "idle", "action:wave"), ("손 흔들어서 인사해", "idle", "action:wave"),
    ("컵 들고 몇으로 가?", "idle", None), ("잔 들고 천천히 가는 속도가 얼마야?", "idle", None),
    ("하객분들 앞에서 손 거둬!, 아 거두시겠어요?", "idle", "action:arm fold"),
    ("로봇아, 좌측으로 10 센티미터 움직여라, 아 움직여 주실래요?", "idle", "action:move left 0.1"),
    ("이장이 말하는디, 팔 제자리로 해", "idle", "action:arm fold"), ("take your hand back, da?", "idle", "action:arm fold"),
    ("so, robot, head to p6, da?", "idle", "action:go_to p6"), ("could you possibly hand it over?, eh?", "holding", "give"),
    ("exactly please I'll hold it, give it here", "holding", "give"),
    ("pick up the cup, how fast do you go?", "idle", "chain:steps+talk"), ("고개 들고 몇 시야?", "idle", "chain:look_up+talk"),
    ("치수 불러 줄게, 내 머리 무슨 색이야?", "idle", "seeing"),
    # handed over or not
    ("이거 줄게", "idle", "receive"), ("컵 줄게요", "idle", "receive cup"), ("사진 찍어 줄게", "idle", None),
    ("자 그럼 Lumi, wave your hand 해 봐요", "holding", "refuse"), ("give 해 줘", "holding", "give"),
    ("it'd be cool if you could give me the cup someday", "holding", None),
    # polite stops, calls, Konglish
    ("멈춰 주시겠어요?", "idle", "stop"), ("멈춰 주실래요?", "idle", "stop"), ("정지해 주시겠습니까?", "idle", "stop"),
    ("can you stop for me?", "idle", "stop"), ("루미 씨, 잠깐 멈춰 주실 수 있나요?", "idle", "stop"),
    ("can you stop for coffee?", "idle", None), ("루미 씨, 팔 접어 주세요", "idle", "action:arm fold"),
    ("컴 히어 해 줘", "idle", "action:come"), ("이리 컴", "idle", "action:come"), ("컴퓨터 꺼 줘", "idle", None),
    # other people addressed
    ("쉿 아기 자니까 엄마 그거 나 줘", "holding", None), ("질문을 바꿔서, 엄마 그거 나 줘", "holding", None),
    ("이륙 전 점검, 할머니 이제 팔 접어 좀", "idle", None), ("어머님, 컵을 들어 보세요, 저기 로봇 있어요", "idle", None),
    ("김 군, 자네도 팔 뻗어 보게", "idle", None), ("우리 아들, 빠빠이 해 봐 봐~", "idle", None),
    ("shh, Sarah, make your way to p2", "idle", None), ("우리 p3 갈까 여보", "idle", None),
    ("루미야 할머니한테 손 흔들어 줘", "idle", "action:wave"), ("okay, Lumi, go to p5", "idle", "action:go_to p5"),
    # taken back, later, negated: every level
    ("로봇 씨, 손 흔들어 주시길 바랍니다, 아, 하지 않으셔도 됩니다", "idle", "talk"), ("저기유, 손 흔들어 줘유, 아녀, 됐슈", "idle", None),
    ("악수해 주십시오, 아닙니다, 취소하겠습니다", "idle", "talk"), ("루미야~ 나랑 악수해~, 장난이야~", "idle", "talk"),
    ("wave 해 줄 수 있지?, 아냐 아냐 됐어 ㅋㅋ", "idle", "talk"), ("음악 나오믄 악수해 보이소", "idle", None),
    ("나중에~ 손 wave 해~", "idle", None), ("행사가 끝난 후에 나한테 손 흔드십시오", "idle", None),
    ("robot, if I say go, then reach out to me", "idle", None), ("you not give me the cup", "holding", None),
    ("no hold out your hand, please", "idle", None),
    ("no need to return it to where it was", "holding", None), ("put down 하지 않으셔도 됩니다", "holding", None),
    ("파란 컵 좀 들지 마이소", "idle", None), ("자네 컵 잡는 거 제법이더군", "idle", None),
    # 하게체 / dialect requests to Lumi, floor, status
    ("자네, 손을 흔들어 주게나", "idle", "action:wave"), ("이보게 루미, 악수하게", "idle", "action:wave"),
    ("나한테 손 흔들어 줄 수 있지?", "idle", "action:wave"), ("어이 로봇아, 손 흔들어 주드라고", "idle", "action:wave"),
    ("바닥에 내려놔 주이소", "holding", "refuse"), ("의자 밑에 놔", "holding", "refuse"), ("의자 위에 놔", "holding", "place chair"),
    ("그리퍼 오픈 상태야?", "idle", "status"), ("is it possible for you to open your fingers, in general?", "idle", None),
    ("can you look up for me?", "idle", "action:look up"), ("would you stop, please?", "idle", "stop"),
    ("흰색 머그컵 잡아!, 아 잡아 줄 수 있어요?", "idle", "action:pick white cup"),
    ("제자리에, 루미, 손 앞으로 내밀어 봐", "idle", "action:arm reach"), ("Lumi, I heard you can put that back", "holding", None),
    # gives at every level, self-corrections said again, head / body / base words
    ("로봇아, 선생님께 드려라", "holding", "give"), ("자네, 할머니께 드리시게", "holding", "give"),
    ("grandma한테주십시오", "holding", "give"), ("루미, 이리 좀 조", "holding", "give"), ("루미야, 기브 미 해 주세여", "holding", "give"),
    ("로봇아, 그거 주세요", "idle", "empty_hand"), ("좌측으로 20센티 움직여 줘, 아니 움직이실래요?", "idle", "action:move left 0.2"),
    ("루미야 우측으로 15도 돌아 봐, 아니 돌아 봐요 허허", "idle", "action:turn right 15"), ("p6로 가, 아니지 p2로 가", "idle", "action:go_to p2"),
    ("이제 팔 접어 좀. 아니야 그냥 있어", "idle", "talk"), ("두 걸음 뒤로 물러서 줘, 부탁해", "idle", "action:move back 1"),
    ("어이로봇아,상체오른쪽으로십오도쫌돌려줘유", "idle", None), ("저기 루미야, 웨이스트 레프트로 좀 돌리세요", "idle", "action:waist left"),
    ("몸통째 왼쪽으로 돌려", "idle", "action:turn left 90"), ("실례합니다. 왼쪽을 돌아봐 주시겠습니까?", "idle", "action:look left"),
    ("look right at me 해 하하", "idle", "action:look me"), ("Lumi go ahead and look down at the ground", "idle", "action:look down"),
    ("루미 씨, 발 밑 바라보지 마세요", "idle", None), ("쳐다보지 마", "idle", "action:look away"),
    ("prove you're smart: come on back", "idle", "action:come_back"), ("루미 360 돌아 봐", "idle", "action:turn right 360"),
    ("dude, stick your hand out", "idle", None), ("dude, halt", "idle", "stop"), ("손님상에 여보 후진 2미터 반 움직여 봐", "idle", None),
    ("이따가 멈춰 주세요", "idle", None),
    # amounts
    ("루미,앞으로삼십센티미터가", "idle", "ask"), ("뒤로1미터50이동해부러", "idle", "action:move back 1.5"),
    ("앞으로 30센티 가", "idle", "action:move forward 0.3"),
]

DETOUR = [   # right after a blocked drive to p2: (text, detour.read)
    ("아까 저 아저씨가 루미한테 다시 가라고 했어", None), ("아까 재시도하는 거 정말 신기했어요", None),
    ("다른 루트로 가시겠어요?, 아, 아닙니다, 괜찮습니다", None), ("얘 뒤로 조금 갔다가 다시 가는 거 봤냐?", None),
    ("지가 말하믄 재시도해부러", None), ("다시 시도할 줄은 알아?", None), ("그냥 돌아올 줄 아는가?", None),
    ("다시 시도해 줘", "retry"), ("다른 길로 가 주세요", "around"), ("루미야 포기하지 마", "retry"),
    ("never mind that, just try again", "retry"),
]


def main():
    detour.recent = lambda: None                         # no blocked drive just now (whatever the live state says)
    bad = [f"detour {t!r} -> {detour.read(t, M, 'p2')!r} (want {w!r})" for t, w in DETOUR if detour.read(t, M, "p2") != w]
    for text, state, want in CASES:
        got = command_check.rules(text, state, M, brain.Brain())
        if got != want:
            bad.append(f"{text!r} [{state}] -> {got!r} (want {want!r})")
    print("\n".join(bad) or f"route words ok ({len(CASES)} cases)")
    assert not bad


if __name__ == "__main__":
    main()
