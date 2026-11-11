"""Readings fixed on 2026-11-02: Korean casual / rude / formal / suggestion forms, steps said with "-ㄴ 다음에", polite noun
requests, a said distance with 비켜, stop forms, and English paraphrases, doubts and remarks. Rules only (the bank's
embeddings are read as by every check). No robot.

    .venv/bin/python tests/test_night6_words.py
"""
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import lumi, quick_answers as qa
from audio import sing
from tests import command_check
from assistant import brain
from tests.blind.maps import MAPS

MARKS = MAPS["office"]
B = brain.Brain()

READS = [
    ("야, p3로 가", "action:go_to p3"), ("야 손 흔들어", "action:wave"), ("야 팔 접어라", "action:arm fold"),
    ("민수야 이리 와", None), ("얘 이리 와", None),
    ("p3로 갑시다", "action:go_to p3"), ("왼쪽으로 돕시다", "action:turn left 90"), ("악수합시다", "action:wave"),
    ("노래 합시다", "sing"), ("노래 하십시오", "sing"), ("당장 노래 불러", "sing"),
    ("p5로 이동 부탁드립니다", "action:go_to p5"), ("저 따라다녀 주세요", "action:follow"),
    ("야 뒤로 50센티 비켜", "action:move back 0.5"), ("비켜", "action:move back 1"),
    ("p3로 이동한 다음에 손 흔들어 주시겠어요?", "chain:steps+wave"), ("회의 끝난 다음에 p3로 가", None),
    ("do you shake your hand", "action:wave"), ("can you shake your hand", "action:wave"),
    ("can you even turn left?", None), ("my son wants to fold your arm", None), ("can you turn left?", "action:turn left 90"),
    ("lift your head now", "action:look up"), ("go get the cup for me", "action:fetch go get the cup for me"),
    ("you go front one meter", "action:move forward 1"), ("bow your head", "action:look down"),
    ("rotate one eighty", "action:turn around 180"), ("turn left 180 degrees", "action:turn left 180"),
    ("앞으로 1미터 전진해 봐", "action:move forward 1"), ("좌회전 해 봐", "action:turn left 90"), ("p3로 움직여 봐", "action:go_to p3"),
    ("고개를 드세요", "action:look up"), ("빨리 돌아와", "action:come_back"), ("노래 부릅시다", "sing"), ("왼쪽 봐", "action:look left"),
    ("왼쪽으로 돌아봐", "action:look left"), ("번거로우시겠지만 왼쪽을 돌아보시겠어요?", "action:look left"),
    ("left로육십degreesturn해봐", None), ("mind folding your arm?", "action:arm fold"), ("how about singing a song?", "sing"),
]
STOPS = ["동작 멈춰 줄 수 있어?", "거기 서 도", "거기 서 봐라", "루미 씨, 동작 멈춰 주시겠어요?", "거기 서 주세요, 부탁드립니다",
         "could you stop it?", "would you be so kind as to stop?", "please cut it out", "freeze ok?", "you can stop?",
         "움직이지 말아 주세요", "움직이지 말아 줄래?", "꼼짝 마", "가만 있어 봐", "멈춥시다", "거기 서라 빨리",
         "I'd like you to cut it out", "could you stay still?", "you can stop the robot?", "hey, cut it out would ya"]
NOT_STOPS = ["거기 서 있는 사람 누구야?", "동작 멈추는 법 알아?", "can you stop the music?", "the bus stop is there",
             "waiting for it to freeze", "I want to stop by the cafe", "가만히 있으면 돼요?", "그거 그만하자고 했잖아",
             "you can stop worrying", "please don't stop talking"]
QUICK = [("이름 대 봐", "name"), ("나이 대 봐", "age"), ("이름을 말씀해 주십시오", "name"), ("야 너 몇 살이냐", "age"),
         ("카메라 어디 달려 있어?", "cameras"), ("how old r u", "age"), ("can u sing tho?", "can_sing"),
         ("Is it safe for my kids to be near you?", "safety"), ("How do I stop you in an emergency?", "estop"),
         ("how old?", None), ("what's my name?", None)]

bad = []
for text, want in READS:
    got = command_check.rules(text, "idle", MARKS, B)
    if got != want:
        bad.append(f"{text!r}: got {got}, want {want}")
bad += [f"no stop: {t!r}" for t in STOPS if not lumi.stop_order(t, ())]
bad += [f"stop: {t!r}" for t in NOT_STOPS if lumi.stop_order(t, ())]
bad += [f"quick {t!r}: got {qa.kind_of(t)}, want {w}" for t, w in QUICK if qa.kind_of(t) != w]
bad += [f"song: {t!r}" for t in ("my son wants to sing a song", "he told me to sing a song") if sing.asked(t)]
assert not bad, "\n".join(bad)
print(f"night 6 words ok ({len(READS) + len(STOPS) + len(NOT_STOPS) + len(QUICK)} cases)")
