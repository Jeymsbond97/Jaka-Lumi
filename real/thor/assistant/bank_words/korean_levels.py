"""Korean wordings at every speech level, for the kinds Lumi acts on: each kind's fronts (object with a side, place,
way, body part, who to) x its verbs x the request endings people use, 반말 to 하십시오체, honorific -시-, 하게체,
dialect, friendly and written slips.

wording.ko_plain already reads most endings as the plain 반말 one before the bank compares ("집어 주십시오",
"집으세요", "집어 주이소" -> "집어 줘"), and the bank stores its wordings the same way, so those collapse into one
wording each; they are listed so every level is covered by name. The endings ko_plain leaves as they are ("집어
주라", "집어 줘 보소", "집어 주시겠소?", "집어 주는 거 어때?", "집어줘") are embedded as said.
"""
import itertools
import zlib

# verb: (반말 form "집어", stem before -세요 / -십시오 "집으" or None); a verb whose 반말 form needs 주다 after it
# ("갖다", "가져다") is marked by a trailing "~"
VERBS = {
    "집": ("집어", "집으"), "잡": ("잡아", "잡으"), "들어올려": ("들어 올려", "들어 올리"), "쥐": ("쥐어", "쥐"),
    "픽업": ("픽업해", "픽업하"),
    "가": ("가", "가"), "이동": ("이동해", "이동하"), "움직": ("움직여", "움직이"), "와": ("와", "오"),
    "다가와": ("다가와", "다가오"), "따라와": ("따라와", "따라오"), "쫓아와": ("쫓아와", "쫓아오"),
    "따라다녀": ("따라다녀", "따라다니"), "돌아와": ("돌아와", "돌아오"), "돌아가": ("돌아가", "돌아가"),
    "복귀": ("복귀해", "복귀하"), "돌아": ("돌아", "도"), "회전": ("회전해", "회전하"), "돌아서": ("돌아서", "돌아서"),
    "봐": ("봐", "보"), "쳐다봐": ("쳐다봐", "쳐다보"), "바라봐": ("바라봐", "바라보"), "들어": ("들어", None),
    "숙여": ("숙여", "숙이"), "돌려": ("돌려", "돌리"), "올려": ("올려", "올리"), "내려": ("내려", "내리"),
    "높여": ("높여", "높이"), "낮춰": ("낮춰", "낮추"), "흔들어": ("흔들어", "흔드"), "악수": ("악수해", "악수하"),
    "인사": ("인사해", "인사하"), "내밀어": ("내밀어", "내미"), "뻗어": ("뻗어", "뻗으"), "접어": ("접어", "접으"),
    "넣어": ("넣어", "넣으"), "거둬": ("거둬", "거두"), "펴": ("펴", "펴"), "벌려": ("벌려", "벌리"), "열어": ("열어", "여"),
    "닫아": ("닫아", "닫으"), "오므려": ("오므려", "오므리"), "가져와": ("가져와", "가져오"), "갖고와": ("갖고 와", "갖고 오"),
    "챙겨와": ("챙겨 와", "챙겨 오"), "가져다": ("가져다~", None), "갖다": ("갖다~", None), "놔": ("놔", "놓으"),
    "내려놔": ("내려놔", "내려놓으"), "둬": ("둬", "두"), "올려놔": ("올려놔", "올려놓으"),
}

# endings: {a} the 반말 form, {s} the stem before -시-. Levels in order: 반말, friendly, 해요체, honorific, 하십시오체,
# 하게체, dialect (경상 / 전라 / 충청), written slips and suggestions
ENDS = [
    "{a}", "{a} 줘", "{a} 봐", "{a}라", "{a} 줄래?", "{a} 줄 수 있어?", "{a} 주라", "{a} 줘라", "{a} 봐 봐", "{a}줘", "{a}봐",
    "{a} 줄래 응?", "{a} 주지 않을래?", "{a} 줄 수 있겠어?", "{a} 주는 거 어때?",
    "{a}요", "{a} 줘요", "{a} 주세요", "{a} 봐요", "{a} 줄래요?", "{a} 주실래요?", "{a} 주시겠어요?", "{a} 주실 수 있어요?",
    "{a} 주셔요", "{a} 주셔", "{a} 주시지 않겠어요?", "{a} 주셨으면 해요", "{a} 주시면 감사하겠습니다",
    "{s}세요", "{s}시겠어요?", "{s}실래요?", "{s}시죠",
    "{a} 주십시오", "{a} 주시기 바랍니다", "{a} 주시겠습니까?", "{a} 주시길 바랍니다", "{a} 주실 수 있겠습니까?", "{s}십시오",
    "{a} 주게", "{a} 주게나", "{a} 주시게", "{a} 주시겠소?", "{a} 주시오", "{s}시오",
    "{a} 도", "{a} 주이소", "{s}이소", "{a} 줘 보소", "{a} 주소", "{a}라잉", "{a} 줘라잉", "{a} 주랑께", "{a} 줘유", "{a} 봐유",
    "{a} 주이라",
    "{a}조", "{a} 줘용", "{a} 주세여", "{a} 줘염", "{a} 주세염", "{a} 주시겠어여?", "{a} 주실래여?", "{a} 주떼여", "{a} 달라",
]


def _say(front, verb, end):
    a, s = VERBS[verb]
    aux = a.endswith("~")
    a = a.rstrip("~")
    if "{s}" in end and not s or aux and not any(w in end for w in ("{a} 주", "{a} 줘", "{a}줘", "{a} 줄", "{a} 도",
                                                                       "{a} 달라")):
        return None
    return " ".join((front + end.format(a=a, s=s or "")).split())


BASIC = ["{a}", "{a} 줘", "{a} 봐", "{a} 줄래?", "{a} 봐 봐"]   # what ko_plain turns most endings into
RAW_SHARE = 0.2         # share of fronts x verbs said with each ending ko_plain keeps as it is (each one embedded)


def _make(fronts, verbs, share=RAW_SHARE):
    """Every front x verb x ending; an ending ko_plain does not read as a BASIC one on a fixed `share` of them."""
    from assistant import wording
    out = []
    for f, v in itertools.product(fronts, verbs):
        basic = {wording.ko_plain(t) for t in (_say(f, v, e) for e in BASIC) if t}
        for e in ENDS:
            t = _say(f, v, e)
            if t and (wording.ko_plain(t) in basic or zlib.crc32(t.encode()) % 1000 < share * 1000):
                out.append(t)
    return list(dict.fromkeys(out))


_OBJ = ["<obj> ", "<obj> 좀 ", "그 <obj> ", "저 <obj> ", "이 <obj> ", "<obj> 하나 ", "저기 있는 <obj> ",
        "테이블 위에 있는 <obj> ", "테이블에 있는 <obj> "]
_SIDE = ["왼쪽에 있는 <obj> ", "오른쪽에 있는 <obj> ", "왼쪽 <obj> ", "오른쪽 <obj> ", "왼편에 있는 <obj> ",
        "오른편에 있는 <obj> ", "앞에 있는 <obj> ", "가운데 있는 <obj> ", "옆에 있는 <obj> ", "제일 가까운 <obj> ",
         "왼쪽에 놓인 <obj> ", "오른쪽에 놓인 <obj> "]
_TO = ["", "저한테 ", "나한테 ", "여기로 ", "이리 "]
_DIRS = ["앞으로 ", "뒤로 ", "왼쪽으로 ", "오른쪽으로 "]
_HOW = ["", "조금 ", "살짝 ", "약간 ", "1 meter ", "한 걸음 ", "좀 "]

INTENT = {
    "pick": _make(_OBJ, ["집", "잡", "들어올려", "픽업"]) + _make(_SIDE, ["집", "잡"], share=0.05),   # a side said:
    # the bank finds the kind, the pick reader leaves it to the rules / LLM (the quick pick takes no side)
    "fetch": _make([t + o for t in _TO for o in ["<obj> ", "그 <obj> ", "<obj> 하나 ", "<obj> 좀 "]] +
                   ["왼쪽에 있는 <obj> ", "오른쪽에 있는 <obj> ", "테이블에 있는 <obj> "],
                   ["가져와", "갖고와", "챙겨와", "가져다", "갖다"]),
    "put": _make(["<obj> ", "그거 ", "이거 ", "들고 있는 거 ", "왼쪽 테이블에 ", "오른쪽 테이블에 ", "테이블 위에 ", "여기 ",
                  "저기 ", "바닥에 ", "왼쪽에 ", "오른쪽에 ", "앞에 ", "옆 테이블에 ", "그거 왼쪽에 ", "그거 오른쪽 테이블에 "],
                 ["놔", "내려놔", "둬", "올려놔"]),
    "go_to": _make(["<place>로 ", "<place>까지 ", "<place> 쪽으로 ", "<place>에 ", "<place> 앞으로 ", "<place> 방향으로 "],
                   ["가", "이동"]),
    "come": _make(["이리 ", "여기로 ", "이쪽으로 ", "나한테 ", "저한테 ", "제 쪽으로 ", "가까이 ", "제 앞으로 ", "내 옆으로 ",
                   "제 옆으로 ", "일로 ", "좀 더 가까이 "], ["와", "다가와"]),
    "follow": _make(["", "저 ", "저를 ", "나 ", "날 ", "제 뒤를 ", "저희를 ", "우리 ", "뒤에서 ", "잘 "],
                    ["따라와", "쫓아와"]),
    "come_back": _make(["원래 자리로 ", "제자리로 ", "아까 그 자리로 ", "처음 자리로 ", "원위치로 ", "아까 있던 곳으로 ",
                        "원래 있던 데로 ", "출발한 곳으로 "], ["돌아와", "돌아가", "복귀"]),
    "move": _make([d + h for d in _DIRS for h in _HOW], ["가", "이동", "움직"]),
    "turn": _make([d + h for d in ["왼쪽으로 ", "오른쪽으로 "] for h in ["", "90 degrees ", "살짝 ", "몸 ", "조금 "]] +
                  ["뒤로 ", "몸 뒤로 "], ["돌아", "회전"]),
    "look": _make(["위 ", "위쪽 ", "아래 ", "아래쪽 ", "왼쪽 ", "오른쪽 ", "저를 ", "절 ", "여기 ", "이쪽 ", "정면 ", "천장 ",
                   "바닥 ", "제 얼굴 "], ["봐", "쳐다봐", "바라봐"]) +
            _make(["고개 ", "고개를 ", "고개 좀 ", "고개 살짝 ", "머리 "], ["들어", "숙여"]) +
            _make(["고개 왼쪽으로 ", "고개 오른쪽으로 ", "고개를 왼쪽으로 ", "고개를 오른쪽으로 "], ["돌려"]),
    "lift": _make([b + h for b in ["몸 ", "몸을 ", "키 ", "키를 ", "몸통 ", "상체 "] for h in ["", "좀 ", "조금 ", "살짝 ", "더 "]],
                  ["올려", "내려", "높여", "낮춰"]),
    "wave": _make(["손 ", "손을 ", "손 좀 ", "손 한번 ", "저한테 손 ", "우리한테 손 ", "애들한테 손 ", "손님들한테 손 ",
                   "반갑게 손 "], ["흔들어"]) +
            _make(["", "저랑 ", "나랑 ", "우리 "], ["악수"]) + _make(["손으로 ", "손 흔들어 "], ["인사"]),
    "arm_reach": _make(["손 ", "손을 ", "팔 ", "팔을 ", "손 좀 ", "팔 좀 ", "팔 앞으로 ", "손 앞으로 ", "팔 쭉 ", "저한테 손 "],
                       ["내밀어", "뻗어"]),
    "arm_fold": _make(["팔 ", "팔을 ", "팔 좀 ", "팔 다시 ", "팔 이제 "], ["접어", "넣어", "거둬", "내려"]),
    "arm_open": _make(["손 ", "손을 ", "손가락 ", "그리퍼 ", "그리퍼를 ", "집게 ", "집게를 ", "손 좀 ", "그리퍼 좀 "],
                      ["펴", "벌려", "열어"]),
    "arm_close": _make(["손 ", "손을 ", "손가락 ", "그리퍼 ", "그리퍼를 ", "집게 ", "집게를 ", "그리퍼 좀 "],
                       ["닫아", "오므려"]) + _make(["주먹 ", "주먹 꽉 ", "손 꽉 "], ["쥐"]),
}
# "손 줘" (give me your hand) has no verb of its own here: its levels written out
INTENT["arm_reach"] += [f"{w}{e}" for w in ["손 ", "손 좀 ", "손 이리 ", "저한테 손 "]
                        for e in ["줘", "줘 봐", "주세요", "줘요", "주십시오", "주실래요?", "줄래?", "주이소", "도", "줘유", "주게",
                                  "주시겠어요?", "주시겠습니까?", "주라", "줘라잉", "주소", "주랑께"]]

if __name__ == "__main__":
    for k, v in INTENT.items():
        print(f"{k:10} {len(v)}")
    print("total", sum(map(len, INTENT.values())))
