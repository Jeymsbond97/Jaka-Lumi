"""Self-check of the keyword rules in brain.intent() for arm and object commands, no robot: python tests/test_intents.py"""
from assistant import brain

CASES = {
    "Lumi, pick up the white cup": ("pick", "white cup"),
    "take the cup please": ("pick", "cup"),
    "can you hold the mug": ("pick", "cup"),
    "pick up the orange": ("pick", "orange"),
    "pick up the orange cup": ("pick", "orange cup"),
    "흰 컵 잡아": ("pick", "white cup"),
    "move the cup": ("move_object", "cup"),
    "컵 옮겨": ("move_object", "cup"),
    "put it back": ("put", "back"),
    "제자리에 놔": ("put", "back"),
    "put it down": ("put", "down"),
    "put the cup on the table": ("put", "down"),
    "내려 놓아": ("put", "down"),
    "grab it": ("arm", "close"),                 # no object named: just close the hand
    "open your hand": ("arm", "open"),
    "let go": ("arm", "open"),
    "move forward 2 meters": ("move", "forward 2"),
}
CASES.update({   # any wording of the body commands, English, Korean and mixed (None: not an order)
    # wave
    "wave": ("wave", ""), "can you wave?": ("wave", ""), "can you shake your hand?": ("wave", ""),
    "wave at my friend please": ("wave", ""), "say hi with your hand": ("wave", ""), "Lumi, wave hello": ("wave", ""),
    "손 흔들어 줘": ("wave", ""), "손 좀 흔들어 봐": ("wave", ""), "손 흔들어 주세요": ("wave", ""), "손을 흔들어 봐요": ("wave", ""),
    "손 인사 해 줘": ("wave", ""), "wave 해 봐!": ("wave", ""), "루미야 손 흔들어": ("wave", ""),
    "손 인사 해 봐": ("wave", ""), "자, 손 인사 해 봐": ("wave", ""), "손인사 해 봐": ("wave", ""),   # not a parent's "인사 해"
    "손으로 인사 해 봐": ("wave", ""), "손 흔들어 인사 해 봐": ("wave", ""), "do a wave": ("wave", ""),
    "do a little wave for us": ("wave", ""),
    "shake hand": ("wave", ""), "Shake hand, Lumi": ("wave", ""), "안녕 하고 손 흔들어": ("wave", ""),
    "Do you know how to wave?": None, "don't wave": None,
    # head
    "look left": ("look", "left"), "look up": ("look", "up"), "look down a bit": ("look", "down small"),
    "could you look to the right?": ("look", "right"), "turn your head left": ("look", "left"),
    "turn your head 30 degrees to the right": ("look", "right 30"), "tilt your head up a little": ("look", "up small"),
    "lower your head": ("look", "down"), "raise your head": ("look", "up"), "look at me": ("look", "me"),
    "face me please": ("look", "me"), "look straight ahead": ("look", "center"), "Lumi, look up!": ("look", "up"),
    "고개 왼쪽으로 돌려": ("look", "left"), "고개 오른쪽으로 돌려 줘": ("look", "right"), "고개 들어": ("look", "up"),
    "고개 숙여 봐": ("look", "down"), "위를 봐": ("look", "up"), "아래 봐": ("look", "down"), "밑에 봐 줘": ("look", "down"),
    "왼쪽 봐": ("look", "left"), "오른쪽 좀 봐 주세요": ("look", "right"), "나 봐": ("look", "me"), "저를 봐 주세요": ("look", "me"),
    "정면 봐": ("look", "center"), "고개 살짝 왼쪽으로": ("look", "left small"), "고개 좀 위로 살짝 들어 봐": ("look", "up small"),
    "고개 오른쪽으로 30도 돌려": ("look", "right 30"), "turn your head left 120": ("look", "left 120"),
    "look behind you": ("look", "left 180"), "뒤를 봐": ("look", "left 180"), "뒤 돌아봐": ("look", "left 180"), "now 오른쪽 봐!": ("look", "right"),
    "look up the weather in Paris": ("weather", "Paris"),
    "부산 날씨 알려줘": ("weather", "Busan"),
    "제주도 날씨는?": ("weather", "Jeju City"),
    "도쿄 날씨 어때?": ("weather", "Tokyo"),
    "내일 날씨 어때?": ("weather", ""),
    # base
    "go back 1 m": ("move", "back 1"), "go back one metre": ("move", "back 1"), "move forward a little": ("move", "forward 0.5"),
    "step back please": ("move", "back 0.5"), "come forward two meters": ("move", "forward 2"), "move left half a meter": ("move", "left 0.5"),
    "뒤로 1미터 가": ("move", "back 1"), "앞으로 2미터 가 줘": ("move", "forward 2"), "조금 앞으로 와": ("move", "forward 0.5"),
    "오른쪽으로 1미터 이동해": ("move", "right 1"), "turn around": ("turn", "around 180"), "turn left": ("turn", "left 90"),
    "turn right 45 degrees": ("turn", "right 45"), "오른쪽으로 돌아": ("turn", "right 90"), "뒤로 돌아": ("turn", "around 180"),
    "왼쪽으로 돌아 줘": ("turn", "left 90"),
    "앞으로 조금만 와 봐": ("move", "forward 0.5"), "뒤로 1미터만 가": ("move", "back 1"),
    # straight back (lumi.move_by drives it with joy_control); whisper's slips from the clip mic, 2026-10-21
    "let's back 1 meter": ("move", "back 1"), "lets back 1 meter": ("move", "back 1"), "Lumi, let's back 1 meter": ("move", "back 1"),
    "Let's bake one meter.": ("move", "back 1"), "Big one meter.": ("move", "back 1"), "Let's bake one metal.": ("move", "back 1"),
    "go back 1 meter": ("move", "back 1"), "move back one metre": ("move", "back 1"), "go backwards 2 meters": ("move", "back 2"),
    "back up 1 meter": ("move", "back 1"), "back up one metre": ("move", "back 1"), "reverse 1 meter": ("move", "back 1"),
    "let's back two meters": ("move", "back 2"), "drive back half a meter": ("move", "back 0.5"),
    "1미터 뒤로 가": ("move", "back 1"), "2미터 뒤로 가 줘": ("move", "back 2"), "1미터 후진해": ("move", "back 1"),
    "후진해": ("move", "back 1"), "1미터 앞으로 가": ("move", "forward 1"), "go back 5 meters": None,
    "come back here": ("come", ""),
    "how do you go back?": None, "a big one meter table": None,
    # arm
    "reach out your hand": ("arm", "reach"), "stretch out your arm": ("arm", "reach"), "fold your arm": ("arm", "fold"),
    "put your arm down": ("arm", "fold"), "팔 뻗어": ("arm", "reach"), "팔 접어": ("arm", "fold"), "팔 내려": ("arm", "fold"),
    "open your hand": ("arm", "open"), "close your hand": ("arm", "close"), "손 펴": ("arm", "open"), "손 쥐어": ("arm", "close"),
    # lift
    "raise yourself": ("lift", "up"), "lift yourself up": ("lift", "up"), "lower yourself a bit": ("lift", "down small"),
    "raise yourself 5 cm": ("lift", "up 50"), "get taller": ("lift", "up"), "make yourself shorter": ("lift", "down"),
    "키 좀 높여": ("lift", "up"), "키 낮춰": ("lift", "down"), "몸 올려 봐": ("lift", "up"), "몸 좀 내려": ("lift", "down"),
    "키 10센티 높여": ("lift", "up 100"), "몸 5센티만 내려": ("lift", "down 50"), "상체 올려 줘": ("lift", "up"),
    "lift up the cup": ("pick", "cup"),
    # questions are not orders
    "how do you turn your head?": None, "can you lift a car?": None, "how high can you raise yourself?": None,
})

CASES.update({   # looking away, the hand closed again, questions after "Lumi,"
    "look away": ("look", "away"), "don't look at me": ("look", "away"), "stop staring at me": ("look", "away"),
    "쳐다보지 마": ("look", "away"), "날 보지 마": ("look", "away"), "다른 데 봐": ("look", "away"),
    "why do you look away?": None, "now close it": ("arm", "close"), "make a fist": ("arm", "close"),
    "탁자에 놓아 주세요": None, "Lumi, is it hard to pick up a cup?": None, "Please, how far can you move?": None,
})

CASES.update({   # looking behind (2026-10-21 live: "look at the back side" was not understood); questions go to seeing
    "Lumi, look at the back.": ("look", "left 180"), "Look at the back side.": ("look", "left 180"),
    "Look at back side.": ("look", "left 180"), "Look at behind.": ("look", "left 180"),
    "Look at behind side.": ("look", "left 180"), "look at the backside": ("look", "left 180"),
    "Look at big side.": ("look", "left 180"), "look back": ("look", "left 180"), "look backwards": ("look", "left 180"),
    "turn your head back": ("look", "left 180"), "turn your head around": ("look", "left 180"),
    "turn around and look": ("look", "left 180"), "could you look at the back side?": ("look", "left 180"),
    "look over your right shoulder": ("look", "right 180"), "look behind you on the right": ("look", "right 180"),
    "뒤 봐": ("look", "left 180"), "뒤돌아 봐": ("look", "left 180"), "뒤돌아봐": ("look", "left 180"),
    "뒤쪽 봐": ("look", "left 180"), "뒤에 봐 줘": ("look", "left 180"), "뒤 좀 봐 주세요": ("look", "left 180"),
    "고개 뒤로 돌려": ("look", "left 180"), "고개를 뒤쪽으로 돌려 줘": ("look", "left 180"), "오른쪽 뒤 봐": ("look", "right 180"),
    "back side 봐": ("look", "left 180"), "behind 좀 봐 줘": ("look", "left 180"), "루미야 뒤 look": ("look", "left 180"),
    "please look behind 해 줘": ("look", "left 180"),
    "look forward": ("look", "center"), "look ahead": ("look", "center"), "turn around and look at me": ("look", "me"),
    "turn around": ("turn", "around 180"), "뒤로 돌아 봐": ("turn", "around 180"), "back up 1 m": ("move", "back 1"),
    "what's behind you?": None, "who is behind you?": None, "뒤에 뭐 있어?": None, "뒤에 누가 있어?": None,
    "I'll be back": None, "I'm behind you": None, "look back at me": None, "look at the back of the box": None,
    "I'm your backside.": None, "don't look behind": None,
})

wrong = {text: (brain.intent(text, []), want) for text, want in CASES.items() if brain.intent(text, []) != want}
assert not wrong, wrong
from assistant import seeing                               # the questions are answered by the cameras, the orders turn
for text in ("what's behind you?", "who is behind you?", "뒤에 뭐 있어?", "뒤에 누가 있어?", "뒤에 뭐 있는지 봐 줘"):   # the head
    assert seeing.BEHIND.search(text), text
for text in ("can you look behind you?", "look behind you", "뒤 봐", "Look at the back side."):
    assert not seeing.BEHIND.search(text), text
assert (brain.intent("come back", []) or ("",))[0] != "look"
for text in ("Come back P9.", "go back to p9", "come back p9"):          # a place, not 1 m back (2026-10-21)
    assert brain.intent(text, ["home", "p9"]) == ("go_to", "p9"), text

# head and lift goals are cut to the ranges; "small" moves from where it is
assert brain.head_goal("right 90", 0, 0) == (-90.0, 0, None)          # commanded looks: the body's full yaw range
assert brain.head_goal("right 200", 0, 0) == (-180.0, 0, "yaw")
assert brain.head_goal("up 50", 0, 0) == (0, 35.0, "pitch")
assert brain.head_goal("left small", 10, 0) == (25.0, 0, None)
assert brain.head_goal("down", 20, 10) == (20, -5, None)
assert brain.lift_goal("up 50", 80) == (105.0, True)
assert brain.lift_goal("down small", 50) == (20.0, False)
assert brain.lift_goal("up", 0) == (105.0, False)
assert brain.head_goal("away", 20, 5) == (-40.0, 5, None) and brain.head_goal("away", -10, 0) == (50.0, 0, None)

# the hand: (text, holding) -> hand_request(); None: not a hand request (a pick, a mission, a question)
M = ["p1", "p2", "home"]
HAND = {
    ("take this from my hand", False): ("receive", None), ("take the apple from my hand", False): ("receive", "apple"),
    ("hold this", False): ("receive", None), ("here you go", False): ("receive", None),
    ("I'll give you this cup", False): ("receive", "cup"), ("이거 받아", False): ("receive", None),
    ("드릴게요", False): ("receive", None), ("내 손에 있는 거 가져가", False): ("receive", None),
    ("사과 받아 줄래요?", False): ("receive", "apple"),
    ("give it to me", True): ("give", None), ("hand it to her", True): ("give", None), ("저 사람한테 줘", True): ("give", None),
    ("give me the cup", True): ("give", None), ("I'll take it", True): ("give", None), ("이리 줘", True): ("give", None),
    ("give it to me", False): ("give", None),               # lumi says the hand is empty
    ("put it here", True): ("place", {"pointed": True}), ("여기 놔", True): ("place", {"pointed": True}),
    ("drop it here", True): ("place", {"pointed": True}), ("put it down", True): ("place", None),
    ("put it on that table", True): ("place", {"name": "dining table", "colour": None}),
    ("open your hand", True): ("refuse", brain.REFUSE_OPEN), ("손 펴", True): ("refuse", brain.REFUSE_OPEN),
    ("open your hand", False): None, ("take the cup", False): None, ("give me the cup", False): None,
    ("grab that cup on the table", False): None, ("give it to Mina", True): None, ("put it back", True): None,
    ("take it to p2 and put it on the table", True): None, ("just hold it", True): None,
    ("can you give things to people?", False): None, ("don't give it to him", True): None, ("팔 거둬", True): None,
    ("what happens if I put something in your hand?", False): None, ("I get it", False): None,
    ("hold that thought", False): None, ("leave it", True): None, ("그냥 둬", True): None, ("lay down", True): None,
}
bad = {k: (brain.hand_request(k[0], k[1], None, M), v) for k, v in HAND.items() if brain.hand_request(k[0], k[1], None, M) != v}
assert not bad, bad

# a correction right after a pick
after_pick = [("pick up the cup", "ACTION: pick cup")]
assert brain.correction("no, the other one", after_pick)[0] == "ask"
assert brain.correction("아니 그거 말고", after_pick)[0] == "ask"
assert brain.correction("no, the red one", after_pick) == ("pick", "red cup")
assert brain.correction("not the cup, the apple", after_pick) == ("pick", "apple")
assert brain.correction("no, the other one", [("hi", "ACTION: none -\nHello!")]) is None

# every class the fingers know has spoken words (a refused one gets its reason, not "which object?")
from assistant import fetch_dialog, steps
from manipulation import skills
assert set(brain.OBJECTS.values()) == set(skills.GRASPS) - {"umbrella"}, set(skills.GRASPS) ^ set(brain.OBJECTS.values())   # umbrella: a weather word
assert brain.intent("공 집어", []) == ("pick", "sports ball") and brain.intent("pick up the tennis ball", []) == ("pick", "sports ball")
assert brain.intent("take the wine glass", []) == ("pick", "wine glass")
assert not brain._mentions("공항으로 가", []) and not brain._mentions("책상 위에 놔", []).get("object")
got, _ = steps.rules("pick up the phone", [])
assert steps.check(got, False, []) == [skills.refusal("cell phone")[0]]
assert not steps.check([{"do": "pick", "object": "cup", "colour": None}, {"do": "place", "on": {"pointed": True}}], False, [])
assert steps.rules("take this from me", [])[0] == [{"do": "receive", "object": None, "from_hand": True}]
assert "sports ball" in fetch_dialog._question({"object": None}, [])[0]
assert brain.Brain._action("ACTION: pick apple", "olmani ol", []) == {"action": "none", "target": ""}   # no translating
assert brain.Brain._action("ACTION: pick white cup", "could ya snag the white cup", [])["target"] == "white cup"
# after a lookup, a short follow-up is looked up too (not answered about Lumi); "search ..." without ACTION: is a search
b = brain.Brain()
b.history, b.last_lookup = [("who built the eiffel tower?", "Gustave Eiffel's company.")], "who built the eiffel tower?"
for text in ("How tall is it?", "Where?", "몇 살이야?", "어디서 태어났어?", "누가 설계했어?"):
    assert b._after({"action": "none", "target": ""}, text)["action"] == "search", text
assert b._after({"action": "none", "target": ""}, "how tall are you?")["action"] == "none"
assert brain.Brain._action("search Chung Ju-yung death date", "정주영 언제 죽었어?", []) == \
    {"action": "search", "target": "Chung Ju-yung death date"}
from assistant import lumi                                 # a venue question only when it names no place elsewhere
assert lumi.not_online("여기 몇 시까지 해요?") and lumi.not_online("입장료 얼마예요?") and lumi.not_online("what time is the keynote?")
assert not lumi.not_online("루브르 몇 시까지 해?") and not lumi.not_online("How much are tickets for the Louvre?")
assert not lumi.not_online("롯데월드 입장료 얼마야?")
print("intents ok")
