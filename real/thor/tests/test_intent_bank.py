"""Self-check of the example bank (assistant/intent_bank.py): python tests/test_intent_bank.py

Needs the embedding server (assistant/knowledge.embed starts it); nothing moves. Guards first, then readings on maps
with other marker names (any map, not p1..p10), then words that must never become a motion."""
from assistant import intent_bank as ib

EXPO = ["home", "dock2", "booth_A", "booth_B", "entrance", "stage", "coffee_corner", "info_desk"]
KOREAN = ["home", "커피코너", "부스3", "입구", "무대", "안내데스크", "회의실"]

GUARDED = {
    "don't go to the stage": "negation", "무대로 가지 마": "negation", "손 흔들지 마세요": "negation",
    "go to the stage when the guests arrive": "later", "손님 오시면 손 흔들어": "later", "나중에 무대로 가": "later",
    "are you able to wave?": "ability", "손 흔들 줄 알아?": "ability", "무대로 갈 수 있어?": "ability",
    "where is the stage?": "question", "무대 어디야?": "question", "무대에 가 봤어?": "question",
    "go to the stage and wave": "several", "무대로 가서 기다려": "several", "move back 50 cm, sorry, 30 cm": "several",
    "I'll go to the stage": "self", "제가 따라갈게요": "self",
    "Jake, follow me": "someone else", "민수야 이리 와": "someone else", "음 민수야 손 흔들어 봐": "someone else",
    "okay thanks": "closing", "알겠어요": "closing",
    "hold this cup": "hand", "제 손에 있는 컵 가져가세요": "hand",
    "인스타 팔로우 해 주세요": "other sense", "따라 해 봐": "other sense", "한 번만 더 해 줘": "repeat",
}
READS = [   # (words, markers, holding, (action, target))
    ("say hi with your arm", EXPO, False, ("wave", "")),
    ("give us a wave", EXPO, False, ("wave", "")),
    ("손 인사 해 주세요", KOREAN, False, ("wave", "")),
    ("would you mind going to the coffee corner?", EXPO, False, ("go_to", "coffee_corner")),
    ("bring yourself over to the stage please", EXPO, False, ("go_to", "stage")),
    ("커피코너로 가 주세요", KOREAN, False, ("go_to", "커피코너")),
    ("안내데스크로 이동하십시오", KOREAN, False, ("go_to", "안내데스크")),
    ("무대로 go", KOREAN, False, ("go_to", "무대")),
    ("walk beside me", EXPO, False, ("follow", "")),
    ("나 쫓아와", KOREAN, False, ("follow", "")),
    ("elevate yourself", EXPO, False, ("lift", "up")),
    ("높이 좀 낮춰 주실래요?", KOREAN, False, ("lift", "down")),
    ("look rightwards", EXPO, False, ("look", "right")),
    ("천장 봐", KOREAN, False, ("look", "up")),
    ("reset your head", EXPO, False, ("look", "center")),
    ("hang a left", EXPO, False, ("turn", "left 90")),
    ("오른쪽으로 삼십 도 회전해 줘", KOREAN, False, ("turn", "right 30")),
    ("오른쪽으로 십오 도만 돌아", KOREAN, False, ("turn", "right 15")),
    ("move a quarter of a meter to your right", EXPO, False, ("move", "right 0.25")),
    ("go forward eight centimetres", EXPO, False, ("move", "forward 0.08")),
    ("앞으로 이 미터 반만 가 주십시오", KOREAN, False, ("move", "forward 2.5")),
    ("spin fifteen degrees right", EXPO, False, ("turn", "right 15")),
    ("bring me the cup from the coffee corner", EXPO, False, ("fetch", "bring me the cup from the coffee corner")),
    ("컵 저한테 가져다 주세요", KOREAN, False, ("fetch", "컵 저한테 가져다 주세요")),
    ("pull your arm back in", EXPO, False, ("arm", "fold")),
    ("snatch the blue bottle", EXPO, False, ("pick", "blue bottle")),
]
NEVER = [   # (words, markers, holding): no motion from the bank
    ("go to the kitchen", EXPO, False),             # not on this map
    ("take it to the stage", EXPO, True),           # carry what is held: the mission reader / LLM
    ("face the stage", EXPO, False),
    ("go upstairs", EXPO, False),
    ("the cup the cup", EXPO, False),
    ("give me a wave", EXPO, True),                 # a wave with a cup in the hand: the LLM says why not
    ("open your hand", EXPO, True),                 # would drop what is held
    ("put it down", EXPO, False),                   # the hand reader's
    ("컵 좀 줘", KOREAN, False),                    # pick, then give: a mission
    ("follow you", EXPO, False),
    ("turn your back to me", EXPO, False),
    ("a little lower", EXPO, False),                # the head or the lift? the LLM asks
    ("move forward to meters", EXPO, False),
    # a past event in the first person, a statement with a tag: never an order (held-out wrong motions, round 2)
    ("I walked over to the stage", EXPO, False),
    ("we went to the coffee corner earlier", EXPO, False),
    ("I turned left at the entrance", EXPO, False),
    ("I moved back a bit so you could pass", EXPO, False),
    ("무대에 갔었어", KOREAN, False),
    ("아까 왼쪽으로 돌았어요", KOREAN, False),
    ("the next stop is the stage, right?", EXPO, False),
    ("this is the end, isn't it?", EXPO, False),
    ("you go to the entrance after this, don't you?", EXPO, False),
    ("다음은 무대지?", KOREAN, False),
    ("입구로 가는 거 맞죠?", KOREAN, False),
    ("stage로 가는 거 맞지?", KOREAN, False),
    ("in five minutes go to the entrance", EXPO, False),
    ("go to the stage, oh, forget it", EXPO, False),
    ("get me a cup from the cafeteria", EXPO, False),   # not on this map: asked
    ("bring the cup to James", EXPO, False),            # to a person: a mission
    ("제임스에게 컵 가져다 줘", KOREAN, False),
    ("move forward 2 feet", EXPO, False),                # feet: asked
    ("가자 이제", KOREAN, False),
    ("would you throw the cup", EXPO, False),
    ("빨간 컵을 무대에 있는 안나한테 갖다줘", KOREAN, False),   # to a person: a mission
    ("I want the mug, the one at the entrance", EXPO, False),  # a thing at a place: fetch or ask, never a pick here
    ("take the cup to the stage", EXPO, False),
]


def main():
    for words, why in GUARDED.items():
        got = ib.guarded(ib.plain(words))
        assert got == why, (words, got, why)
    for words, markers, holding, want in READS:
        got = ib.read(words, markers, holding)
        assert got == want, (words, got, want)
    for words, markers, holding in NEVER:
        got = ib.read(words, markers, holding)
        assert got is None, (words, got)
    print("intent bank ok")


if __name__ == "__main__":
    main()
