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

wrong = {text: (brain.intent(text, []), want) for text, want in CASES.items() if brain.intent(text, []) != want}
assert not wrong, wrong
print("intents ok")
