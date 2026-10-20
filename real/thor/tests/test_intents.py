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
    # base
    "go back 1 m": ("move", "back 1"), "go back one metre": ("move", "back 1"), "move forward a little": ("move", "forward 0.5"),
    "step back please": ("move", "back 1"), "come forward two meters": ("move", "forward 2"), "move left half a meter": ("move", "left 0.5"),
    "뒤로 1미터 가": ("move", "back 1"), "앞으로 2미터 가 줘": ("move", "forward 2"), "조금 앞으로 와": ("move", "forward 0.5"),
    "오른쪽으로 1미터 이동해": ("move", "right 1"), "turn around": ("turn", "around 180"), "turn left": ("turn", "left 90"),
    "turn right 45 degrees": ("turn", "right 45"), "오른쪽으로 돌아": ("turn", "right 90"), "뒤로 돌아": ("turn", "around 180"),
    "왼쪽으로 돌아 줘": ("turn", "left 90"),
    "앞으로 조금만 와 봐": ("move", "forward 0.5"), "뒤로 1미터만 가": ("move", "back 1"),
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

wrong = {text: (brain.intent(text, []), want) for text, want in CASES.items() if brain.intent(text, []) != want}
assert not wrong, wrong

# head and lift goals are cut to the ranges; "small" moves from where it is
assert brain.head_goal("right 90", 0, 0) == (-90.0, 0, None)          # commanded looks: the body's full yaw range
assert brain.head_goal("right 200", 0, 0) == (-180.0, 0, "yaw")
assert brain.head_goal("up 50", 0, 0) == (0, 35.0, "pitch")
assert brain.head_goal("left small", 10, 0) == (25.0, 0, None)
assert brain.head_goal("down", 20, 10) == (20, -5, None)
assert brain.lift_goal("up 50", 80) == (105.0, True)
assert brain.lift_goal("down small", 50) == (20.0, False)
assert brain.lift_goal("up", 0) == (105.0, False)
print("intents ok")
