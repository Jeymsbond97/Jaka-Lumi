"""A second held-out set, Korean and English, written at 02:40 on 2026-11-02 and never used for fixing: only scored
on the tree before the night (the before copy) and after it, for the morning report.

    .venv/bin/python tests/held2_check.py      # -> logs/held2.md
"""
import pathlib

from tests import ko_levels_check as kl

ROOT = pathlib.Path(__file__).resolve().parents[1]

CASES = [
    # Korean, every register
    ("p5 쪽으로 좀 가 볼래", "go to p5", "ko 반말"), ("p5로 고고", "go to p5", "ko konglish"), ("p5까지 이동하십시오", "go to p5", "ko 하십시오"),
    ("야 p5 가", "go to p5", "ko rude"), ("p5로 가 주실 수 있을까요?", "go to p5", "ko honorific"), ("p5 가자", "go to p5", "ko suggest"),
    ("앞으로 1미터만 이동해 줄래", "move forward one meter", "ko 반말"), ("1미터 앞으로 가 주십시오", "move forward one meter", "ko 하십시오"),
    ("야 1미터 앞으로 전진", "move forward one meter", "ko rude"), ("뒤로 50센티만 가 주세요", "move back half a meter", "ko 해요"),
    ("50센티 뒤로 물러나 봐", "move back half a meter", "ko 반말"), ("왼쪽으로 돌아 주시겠습니까?", "turn left", "ko 하십시오"),
    ("야 왼쪽으로 돌아", "turn left", "ko rude"), ("좌회전 해 줘", "turn left", "ko 반말"), ("오른쪽으로 45도만 돌아 주세요", "turn right 45 degrees", "ko 해요"),
    ("뒤로 돌아 봐라", "turn around", "ko rude"), ("반 바퀴 돌아 주실래요?", "turn around", "ko honorific"),
    ("위를 봐 줄래?", "look up", "ko 반말"), ("고개 좀 들어 보십시오", "look up", "ko 하십시오"), ("아래 좀 봐라", "look down", "ko rude"),
    ("고개 숙여 주세요", "look down", "ko 해요"), ("날 봐", "look at me", "ko 반말"), ("저 좀 봐 주시겠어요?", "look at me", "ko honorific"),
    ("이리 좀 와 봐", "come here", "ko 반말"), ("이리 오세요", "come here", "ko 해요"), ("야 이리 와라", "come here", "ko rude"),
    ("저를 따라와 주시겠어요?", "follow me", "ko honorific"), ("따라와라", "follow me", "ko rude"), ("나 따라오자", "follow me", "ko suggest"),
    ("손 흔들어", "wave", "ko 반말"), ("손 좀 흔드세요", "wave", "ko honorific"), ("손 흔들어 주십시오", "wave", "ko 하십시오"),
    ("악수하자", "wave", "ko suggest"), ("야 악수해", "wave", "ko rude"), ("손 줘 봐", "give me your hand", "ko 반말"),
    ("손 내밀어 주실래요?", "give me your hand", "ko honorific"), ("팔 접어 줘", "fold your arm", "ko 반말"), ("팔 접으십시오", "fold your arm", "ko 하십시오"),
    ("손 펴 봐라", "open your hand", "ko rude"), ("컵 집어 줘", "pick up the cup", "ko 반말"), ("컵 집으세요", "pick up the cup", "ko honorific"),
    ("야 컵 들어", "pick up the cup", "ko rude"), ("컵 좀 가져와 줘", "bring me the cup", "ko 반말"), ("컵 갖다주십시오", "bring me the cup", "ko 하십시오"),
    ("멈춰", "stop", "ko 반말"), ("멈추세요", "stop", "ko honorific"), ("야 그만해", "stop", "ko rude"), ("정지하십시오", "stop", "ko 하십시오"),
    ("노래 불러 줘", "sing a song", "ko 반말"), ("노래 한 곡 불러 주시겠어요?", "sing a song", "ko honorific"), ("노래 해라", "sing a song", "ko rude"),
    ("충전하러 가", "go charge", "ko 반말"), ("돌아와 주세요", "come back", "ko 해요"), ("몸 올려 줘", "raise your body", "ko 반말"),
    # English, many ways
    ("head over to p5", "go to p5", "en plain"), ("p5 please", "go to p5", "en casual"), ("would you go to p5 for me?", "go to p5", "en polite"),
    ("you move go p5", "go to p5", "en nonnative"), ("move ahead one meter", "move forward one meter", "en plain"),
    ("back up fifty centimeters please", "move back half a meter", "en polite"), ("turn left, would you?", "turn left", "en polite"),
    ("left turn please", "turn left", "en casual"), ("you turn around please", "turn around", "en nonnative"), ("turn round", "turn around", "en plain"),
    ("look upward please", "look up", "en polite"), ("look down for me", "look down", "en plain"), ("look at me please", "look at me", "en polite"),
    ("over here, come", "come here", "en casual"), ("come to me please", "come here", "en polite"), ("follow me around", "follow me", "en plain"),
    ("could you follow behind me?", "follow me", "en polite"), ("wave at the camera", "wave", "en plain"), ("shake hands with us", "wave", "en plain"),
    ("can you wave to my friend?", "wave", "en polite"), ("reach out to me", "give me your hand", "en plain"), ("fold up your arm", "fold your arm", "en plain"),
    ("open the hand please", "open your hand", "en polite"), ("grab the cup please", "pick up the cup", "en polite"),
    ("could you bring the cup here?", "bring me the cup", "en polite"), ("stop, stop", "stop", "en casual"), ("please stop moving", "stop", "en polite"),
    ("sing us a song", "sing a song", "en plain"), ("go to your charger", "go charge", "en plain"), ("talk louder please", "speak louder", "en polite"),
]
NOT_NOW = [
    "아까 손 흔들었잖아", "손 흔들 수 있어요?", "엄마가 이리 오래요", "컵 집지 마세요", "이따가 p5로 가 줘", "우리 애가 노래 불렀어요",
    "고개 숙이는 거 봤어", "팔 접는 법 알아?", "I saw it wave yesterday", "don't wave please", "can you even wave?",
    "if I clap, come to me", "my friend went to p5", "later, turn left", "he asked me to follow him",
]


def check():
    rows = []
    for t, en, level in CASES:
        want, got = kl.read(en), kl.read(t)
        rows.append(("held2", level, t, got, want, "right" if kl.same(want, got) else
                     "missed" if got is None or got.split()[0] in kl.command_check.NO_MOTION else "wrong"))
    for t in NOT_NOW:
        got = kl.read(t)
        moves = got is not None and got.split()[0] not in kl.command_check.NO_MOTION
        rows.append(("held2", "not_now", t, got, "no motion", "motion" if moves and got not in ("stop", "sing") else "right"))
    return rows


if __name__ == "__main__":
    out = kl.report(check()).replace("# Korean speech levels against English (tests/ko_levels_check.py)",
                                     "# Second held-out set, Korean and English (tests/held2_check.py)")
    (ROOT / "logs" / "held2.md").write_text(out)
    print(out[:out.index("## Not right")])
