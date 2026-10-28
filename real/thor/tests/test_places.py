"""Self-check of marker names and numbers as people say them (assistant/wording.py), the keyword rules
(brain.intent) and the check of the LLM's place (brain.named_place), no robot, no LLM: python tests/test_places.py"""
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import brain, wording
from tests.steps_cases5 import INTENTS

INTENTS = {**INTENTS,       # how the quick rules work on purpose (docs/14), not a marker or a number:
           "피자 가져와": ("fetch", "피자 가져와"),     # a fetch; the fetch dialog asks which object (pizza is not one)
           "앞으로 가": ("move", "forward 1"),          # a single voice move without a number drives 1 m,
           "go forward a bit": ("move", "forward 0.5"),  # "a bit" 0.5 m
           "컵 들고 춤추면서 p2로 가": None}              # only part of it is a drive: not guessed

M = ["home", "PInit", "Wp", "a", "b", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]

NORM = {   # said -> written
    "피쓰리로 가 줘": "p3로 가 줘", "피 쓰리로 가": "p3로 가", "피스리로": "p3로", "피삼으로 가": "p3으로 가",
    "피 삼에서": "p3에서", "포인트 쓰리": "p3", "포인트 삼에서": "p3에서", "삼 번 포인트로 가": "p3로 가",
    "3번 포인트": "p3", "포인트 3번": "p3", "삼 번으로 가": "3번으로 가", "P.3": "p3", "P-3로": "p3로", "p 3": "p3",
    "피3로": "p3로", "go to 피쓰리": "go to p3", "point 3에서 컵 가져와": "p3에서 컵 가져와",
    "point three에서": "p3에서", "피파이브 앞에 있는 테이블": "p5 앞에 있는 테이블", "피오로가": "p5로가",
    "피십으로": "p10으로", "피텐": "p10", "go to point three": "go to p3", "go to p two": "go to p2",
    "go to piece 6": "go to p6", "파이널로 가": "final로 가", "파이널 포인트로": "final로", "도크 투로 가": "dock2로 가",
    "독투": "dock2", "go to dock two": "go to dock2", "dock two로": "dock2로", "엑시트로 가": "exit로 가",
    "세 번 포인트로 가": "p3로 가", "피트로 가서": "p2로 가서", "po에서": "p5에서", "p.o.로 가": "p5로 가",
    "도크트로가": "dock2로가", "go to docky2": "go to dock2", "피구나 피십중에": "p9나 p10중에",   # as whisper writes them
    "p init": "pinit", "더블유피로": "wp로", "홈으로 가": "home으로 가", "포인트 에이로 가": "point a로 가",
    # numbers
    "앞으로 일 미터 가": "앞으로 1 m 가", "한 미터": "1 m", "1미터 50센치": "1.5 m", "오십 센치": "0.5 m",
    "50센치": "0.5 m", "영점오 미터": "0.5 m", "일 미터 반": "1.5 m", "half a meter": "0.5 m",
    "one point five meters": "1.5 m", "point five meters": "0.5 m", "go forward 05 meters": "go forward 0.5 m",
    "왼쪽으로 사십오 도 돌아": "왼쪽으로 45도 돌아", "백팔십 도 돌아": "180도 돌아",
    "turn left forty five degrees": "turn left 45 degrees", "a hundred and eighty degrees": "180 degrees",
    # not a marker or a number: unchanged
    "피로 가": "피로 가", "pe로 가": "pe로 가", "피자 가져와": "피자 가져와", "피투성이": "피투성이",
    "피오나한테 줘": "피오나한테 줘", "이번에 가": "이번에 가", "커피 3잔": "커피 3잔", "팔도 뻗어": "팔도 뻗어",
    "홈페이지": "홈페이지", "one of them": "one of them",
}
bad = {t: (wording.norm(t), w) for t, w in NORM.items() if wording.norm(t) != w}
assert not bad, bad

wrong = {t: (brain.intent(t, M), w) for t, w in INTENTS.items() if brain.intent(t, M) != w}
for t, (got, want) in wrong.items():
    print(f"FAIL {t!r}: got {got}, want {want}")
print(f"{len(INTENTS) - len(wrong)}/{len(INTENTS)} intents right")

NAMED = {   # (words, the LLM's marker) -> named in the words?
    ("피쓰리로 가 줘", "p3"): True, ("파이널로 가", "final"): True, ("포인트 삼으로 가", "p3"): True,
    ("go to point three", "p3"): True, ("도크 투로 가", "dock2"): True, ("충전하러 가", "home"): True,
    ("take me to the meeting room", "p1"): False, ("take me to a meeting room", "a"): False,
    ("go to marker a", "a"): True, ("go to a", "a"): True, ("피로 가", "p1"): False, ("pe로 가", "p2"): False,
}
off = {k: v for k, v in NAMED.items() if brain.named_place(k[0], k[1], M) != v}
assert not off, off
assert not wrong

# ---- other maps' names (the whole sets on fake maps: tests/fake_maps.py) ----
from assistant import driving, steps
KO = ["home", "커피코너", "부스3", "입구", "무대", "창고", "출구"]
EXPO = ["home", "booth_A", "booth_B", "booth_3", "stage", "coffee_corner", "info_desk", "end", "a"]
SPACED = ["home", "Main Stage", "Storage", "Coffee Corner", "Back Door"]
GO = {   # (words, map) -> intent
    ("커피 코너로 가 줘", "KO"): ("go_to", "커피코너"), ("부스 삼으로 가", "KO"): ("go_to", "부스3"),
    ("go to 입구", "KO"): ("go_to", "입구"), ("출입구로 가", "KO"): None, ("도서관으로 가", "KO"): None,
    ("부스 에이로 가 줘", "EXPO"): ("go_to", "booth_A"), ("booth a로 go", "EXPO"): ("go_to", "booth_A"),
    ("인포 데스크로 가", "EXPO"): ("go_to", "info_desk"), ("come back booth 3", "EXPO"): ("go_to", "booth_3"),
    ("go to the end of the hall", "EXPO"): None, ("go a bit forward", "EXPO"): ("move", "forward 0.5"),
    ("go to the coffee corner", "SPACED"): ("go_to", "Coffee Corner"), ("go to stage", "SPACED"): None,   # asked
    ("no need to go to booth B", "EXPO"): None, ("테이블 앞으로 가", "EXPO"): None,
}
maps = {"KO": KO, "EXPO": EXPO, "SPACED": SPACED}
off = {k: brain.intent(k[0], maps[k[1]]) for k, v in GO.items() if brain.intent(k[0], maps[k[1]]) != v}
assert not off, off
assert brain.place_problem("go to stage", SPACED)[0] == "Did you mean Main Stage?"
assert driving.read(brain._norm("come back booth 3", EXPO)) is None              # a place, not "3 back"
for text, want in {"창고 가서 기다려": [{"do": "go", "to": "창고"}, {"do": "wait", "s": None}],
                   "입구나 무대 중에 아무 데나 가": [{"do": "go", "to": ["입구", "무대"]}],
                   "go to back door then main stage": [{"do": "go", "to": "Back Door"}, {"do": "go", "to": "Main Stage"}],
                   "James asked me to send this to Sara at booth B": [{"do": "go", "to": "booth_B"},
                                                                     {"do": "give", "person": "Sara"}]}.items():
    m = KO if "창고" in text or "입구" in text else SPACED if "door" in text else EXPO
    got, unread = steps.rules(text, m)
    assert got == want and not unread, (text, got, unread)
print("places ok")
