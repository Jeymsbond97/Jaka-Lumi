"""Self-check of whisper's number / unit slips read right in a move (assistant/wording.py number_slips), and words
that must stay as they are. python tests/test_number_slips.py"""
from assistant import wording

CASES = {
    "앞으로 1.m가": "앞으로 1점 몇 m가",                      # 1.5미터 with the 5 lost: asked, never 1 m
    "앞으로 1미가": "앞으로 1 m 가",
    "1m50cm 뒤로 가.": "1.5 m 뒤로 가.",
    "move back 30 centuries.": "move back 0.3 m.",
    "왼쪽으로 30세트 가죠?": "왼쪽으로 0.3 m 가죠?",
    "뒤로 40센터만 가주세요.": "뒤로 0.4 m만 가주세요.",
    "you go forward 50 cent letter please.": "you go forward 0.5 m please.",
    "left. 30cm가.": "left 0.3 m가.",
    "go forward two years.": "go forward 2 m.",
    "go back one and a half years.": "go back 1.5 m.",
    "go forward. forward to me.": "go forward. forward 2 m.",
    "move to p3 weight p8": "move to p3, wait, p8",
    # not a move or not a slip: kept
    "come forward to me.": "come forward to me.",
    "go back to me.": "go back to me.",
    "i gave 50 cents.": "i gave 50 cents.",
    "the weight is 5 kg": "the weight is 5 kg",
    "커피 바 센터": "커피 바 센터",
    "move 1.5 m forward": "move 1.5 m forward",
}
wrong = {t: (wording.norm(t), want) for t, want in CASES.items() if wording.norm(t) != want}
assert not wrong, wrong
print("number slips ok")
