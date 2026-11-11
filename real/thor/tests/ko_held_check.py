"""A held-out Korean check (written apart from ko_levels_check.py's sentences and bank_words/ko_more.py): orders said
in sentences of their own at every register, each with the English request it means; and remarks that must not
move. Run on two trees to compare (PYTHONPATH=<tree> from inside it).

    .venv/bin/python tests/ko_held_check.py      # -> logs/ko_held.md
"""
import collections
import pathlib

from tests import ko_levels_check as kl

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (Korean, the English request it means, register)
CASES = [
    ("저 p5까지 좀 데려다줄래?", "go to p5", "반말"), ("p5 쪽으로 출발!", "go to p5", "반말"), ("p5로 가 보자", "go to p5", "suggest"),
    ("야 p5 가라고", "go to p5", "rude"), ("p5로 이동 부탁드립니다", "go to p5", "하십시오"), ("p5까지 가 주시면 좋겠어요", "go to p5", "해요"),
    ("p5 방향으로 움직여 주실래요?", "go to p5", "honorific"), ("얼른 p5로 꺼져", "go to p5", "rude"),
    ("앞으로 쭉 1미터만 가 볼래?", "move forward one meter", "반말"), ("1미터 전진하십시오", "move forward one meter", "하십시오"),
    ("앞으로 1미터 나가 봐", "move forward one meter", "반말"), ("야 1미터 앞으로 가라", "move forward one meter", "rude"),
    ("한 1미터 앞으로 와 주세요", "move forward one meter", "해요"),
    ("뒤로 50센티 빠져 줄래?", "move back half a meter", "반말"), ("50센티 후진 부탁해요", "move back half a meter", "해요"),
    ("뒤로 50센티 물러나십시오", "move back half a meter", "하십시오"), ("야 뒤로 50센티 비켜", "move back half a meter", "rude"),
    ("왼쪽으로 몸 좀 틀어 봐", "turn left", "반말"), ("좌회전 하십시오", "turn left", "하십시오"), ("왼편으로 돌아 주시겠어요?", "turn left", "honorific"),
    ("야 왼쪽으로 돌라고", "turn left", "rude"), ("왼쪽으로 한 바퀴 말고 90도만 돌아", "turn left", "반말"),
    ("오른쪽으로 45도 회전 부탁드려요", "turn right 45 degrees", "해요"), ("우측으로 45도 돌아 주십시오", "turn right 45 degrees", "하십시오"),
    ("뒤돌아 봐", "turn around", "반말"), ("반대쪽으로 돌아 서 주세요", "turn around", "해요"), ("한 바퀴 반 말고 반 바퀴만 돌아라", "turn around", "rude"),
    ("고개 위로 들어 봐", "look up", "반말"), ("위쪽 좀 쳐다보세요", "look up", "honorific"), ("천장 좀 봐라", "look up", "rude"),
    ("고개를 아래로 숙여 주십시오", "look down", "하십시오"), ("바닥 좀 봐 줄래?", "look down", "반말"),
    ("여기 나 좀 봐라", "look at me", "rude"), ("저 좀 쳐다봐 주세요", "look at me", "해요"), ("저를 바라봐 주시겠습니까?", "look at me", "하십시오"),
    ("이쪽으로 와 볼래?", "come here", "반말"), ("내 쪽으로 좀 와라", "come here", "rude"), ("가까이 와 주시겠어요?", "come here", "honorific"),
    ("이리로 좀 오십시오", "come here", "하십시오"), ("야 이리 와 봐", "come here", "rude"),
    ("나 졸졸 따라와", "follow me", "반말"), ("제 뒤를 쫓아와 주세요", "follow me", "해요"), ("저를 따라오시겠습니까?", "follow me", "하십시오"),
    ("야 나 따라붙어", "follow me", "rude"), ("나만 따라다녀 줘", "follow me", "반말"),
    ("손 들어서 흔들어 줘", "wave", "반말"), ("손 좀 흔들어 주실래요?", "wave", "honorific"), ("야 손 흔들어 봐라", "wave", "rude"),
    ("손을 흔들어 주십시오", "wave", "하십시오"), ("우리랑 악수 한번 해요", "wave", "해요"), ("악수 좀 하자", "wave", "suggest"),
    ("저랑 악수하시겠어요?", "wave", "honorific"), ("손 흔들어서 인사 좀 해 줘", "wave", "반말"),
    ("손 내밀어 줄래?", "give me your hand", "반말"), ("팔 쭉 뻗어 봐라", "give me your hand", "rude"), ("손을 내밀어 주시겠습니까?", "give me your hand", "하십시오"),
    ("팔 다시 접어", "fold your arm", "반말"), ("팔 거두십시오", "fold your arm", "하십시오"), ("팔 좀 접어 주세요", "fold your arm", "해요"),
    ("손 쫙 펴 봐", "open your hand", "반말"), ("그리퍼 좀 열어 주세요", "open your hand", "해요"), ("집게 벌려라", "open your hand", "rude"),
    ("컵 하나 들어 올려 봐", "pick up the cup", "반말"), ("컵 좀 잡아 주시겠어요?", "pick up the cup", "honorific"), ("야 컵 집어 들어", "pick up the cup", "rude"),
    ("그 컵 좀 챙겨 줘", "pick up the cup", "반말"), ("컵을 집어 주십시오", "pick up the cup", "하십시오"),
    ("컵 하나만 갖다 줄래?", "bring me the cup", "반말"), ("저한테 컵 좀 가져다주세요", "bring me the cup", "해요"),
    ("야 컵 가져와 빨리", "bring me the cup", "rude"), ("컵 하나 가져오시겠습니까?", "bring me the cup", "하십시오"),
    ("그만 좀 해", "stop", "반말"), ("거기 멈춰라", "stop", "rude"), ("동작을 멈춰 주십시오", "stop", "하십시오"), ("움직이지 마세요", "stop", "해요"),
    ("잠깐 정지해 주실래요?", "stop", "honorific"), ("야 서라고", "stop", "rude"),
    ("노래 하나 불러 봐", "sing a song", "반말"), ("노래 좀 불러 주시겠어요?", "sing a song", "honorific"), ("야 노래나 해 봐", "sing a song", "rude"),
    ("노래 한 곡 부탁드립니다", "sing a song", "하십시오"), ("노래 부르자", "sing a song", "suggest"),
    ("충전하러 가 봐", "go charge", "반말"), ("충전기 쪽으로 가 주세요", "go charge", "해요"), ("배터리 충전하러 가십시오", "go charge", "하십시오"),
    ("원래 있던 자리로 돌아와", "come back", "반말"), ("제자리로 돌아오세요", "come back", "해요"),
    ("몸 좀 올려 봐", "raise your body", "반말"), ("키 좀 높여 주세요", "raise your body", "해요"),
    ("더 크게 말해 봐", "speak louder", "반말"), ("목소리 좀 키워 주세요", "speak louder", "해요"),
]
NOT_NOW = [
    "아까 너 왼쪽으로 돌았잖아", "손 흔들 줄 알아?", "어제 로봇이 p5로 가더라", "따라오지 마세요", "이따가 노래 불러 줘",
    "엄마가 이리 오래", "우리 애가 손 흔들었어요", "컵 집지 마", "제가 신호하면 앞으로 가 주세요", "민수야 이리 와 봐",
    "고개 숙이는 거 봤어요", "p5로 가면 뭐가 있어요?", "악수하는 법 알려 줄까?", "팔 접지 마십시오", "충전하러 갔었어?",
]


def check():
    rows = []
    for t, en, level in CASES:
        want, got = kl.read(en), kl.read(t)
        rows.append(("ko", level, t, got, want, "right" if kl.same(want, got) else
                     "missed" if got is None or got.split()[0] in kl.command_check.NO_MOTION else "wrong"))
    for t in NOT_NOW:
        got = kl.read(t)
        moves = got is not None and got.split()[0] not in kl.command_check.NO_MOTION
        rows.append(("ko", "not_now", t, got, "no motion", "motion" if moves and got not in ("stop", "sing") else "right"))
    return rows


if __name__ == "__main__":
    out = kl.report(check()).replace("# Korean speech levels against English (tests/ko_levels_check.py)",
                                     "# Korean held-out orders (tests/ko_held_check.py)")
    (ROOT / "logs" / "ko_held.md").write_text(out)
    print(out)
