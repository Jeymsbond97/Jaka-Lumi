"""Self-check of the arm and hand wordings of the example bank (assistant/bank_words/arm.py, arm_more.py):
python tests/test_arm_bank.py

Needs the embedding server (assistant/knowledge.embed starts it); nothing moves. Every arm / hand capability said in
new ways (English and Korean at every level) reads as that one motion or as nothing (the LLM then decides); hard
negatives (questions, remarks, past, negations, gestures Lumi has none of) and side words never become another motion."""
from assistant import intent_bank as ib

M = ["home", "dock2", "booth_A", "stage", "coffee_corner", "p3"]

READS = [   # (words, holding, (action, target))
    ("let's shake on it", False, ("wave", "")),
    ("give the kids a wave", False, ("wave", "")),
    ("손 살랑살랑 흔들어 주세요", False, ("wave", "")),
    ("악수 한번 하시지요", False, ("wave", "")),
    ("할아버지께 손 흔들어 드려", False, ("wave", "")),
    ("악수 하입시더", False, ("wave", "")),
    ("악수 한번 합시다", False, ("wave", "")),
    ("extend your hand to me", False, ("arm", "reach")),
    ("손 내미십시오", False, ("arm", "reach")),
    ("손 좀 내어 주시겠어요?", False, ("arm", "reach")),
    ("팔 쭉 내밀어 보래이", False, ("arm", "reach")),
    ("stow your arm", False, ("arm", "fold")),
    ("팔 거두어 주십시오", False, ("arm", "fold")),
    ("팔 원상복구 해 줘", False, ("arm", "fold")),
    ("open the claw", False, ("arm", "open")),
    ("그리퍼 활짝 열어 주세요", False, ("arm", "open")),
    ("clamp your gripper", False, ("arm", "close")),
    ("주먹 쥐시게", False, ("arm", "close")),
    ("scoop up the bottle", False, ("pick", "bottle")),
    ("컵 집으시게", False, ("pick", "cup")),
    ("fetch me that cup", False, ("fetch", "fetch me that cup")),
    ("컵 챙겨 와 주세요", False, ("fetch", "컵 챙겨 와 주세요")),
    ("손 흔들어 줍서", False, ("wave", "")),
    ("팔 거두시구려", False, ("arm", "fold")),
    ("손내밀어봐", False, ("arm", "reach")),
    ("your job now is to fold your arm", False, ("arm", "fold")),
]
NOT = [   # (words, holding, motions it must not be): a side word or a hand word is never a drive / turn / look
    ("pick up the cup on your left", False, ("turn", "move", "look", "go_to", "wave", "arm")),
    ("오른쪽에 있는 컵 집어 줘", False, ("turn", "move", "look", "go_to", "wave", "arm")),
    ("왼쪽 테이블에 내려놔", True, ("turn", "move", "look", "go_to", "pick")),
    ("put it down to your right", True, ("turn", "move", "look", "go_to", "pick")),
    ("p3에 내려놔 줘", True, ("go_to", "move", "turn")),
]
NEVER = [   # no motion at all from the bank
    ("your arm reached the cup", False), ("악수는 됐어", False), ("박수 쳐 줘", False), ("clap your hands", False),
    ("give me a thumbs up", False), ("손가락 하트 해 줘", False), ("put your hands together for lumi", False),
    ("the cup on your left is mine", False), ("왼쪽에 컵 있어", False), ("you picked the wrong cup", False),
    ("팔이 어디까지 닿아?", False), ("why are you waving", False), ("아까 악수했잖아", False),
    ("shake your head", False), ("pick up the pace", False), ("give it up for lumi", False),
    ("thanks for the wave", False), ("악수해 줘서 고마워요", False), ("close your eyes", False), ("의자 들어 줄래?", False),
    ("the kids want to wave at you", False), ("can my son shake your hand", False),
    ("shaking hands is fun", False), ("you folded your arm earlier", False), ("손 펴도 돼?", False),
    ("팔 접는 게 좋아", False), ("you're good at opening your hand", False),
]


def main():
    bad = []
    for words, holding, want in READS:
        got = ib.read(words, M, holding)
        if got != want:
            bad.append(f"{words!r}: {got}, want {want}")
    for words, holding, nots in NOT:
        got = ib.read(words, M, holding)
        if got and got[0] in nots:
            bad.append(f"{words!r}: {got}, must not be {nots}")
    for words, holding in NEVER:
        got = ib.read(words, M, holding)
        if got:
            bad.append(f"{words!r}: {got}, must be nothing")
    print("\n".join(bad) or f"arm bank ok: {len(READS) + len(NOT) + len(NEVER)} cases")
    return not bad


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
