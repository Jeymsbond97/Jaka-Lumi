"""Korean speech levels against English: the same request said at every level must be read as the same action.

For each capability one English request (and its polite English forms) and one Korean verb phrase; the Korean forms
are made from the verb's stem at each level (반말, friendly, 해요체, 하십시오체, 하게체, honorific, question-form
requests, dialect, whisper slips). Every form must give the English base's reading (lumi.answer()'s rules, as
tests/command_check.rules). The same phrase as a past remark, an ability question, a negation, a later time or a
condition must give no motion.

    .venv/bin/python tests/ko_levels_check.py            # -> logs/ko_levels.md, a table by level and the misses
    .venv/bin/python tests/ko_levels_check.py wave turn  # only these capabilities
"""
import collections
import pathlib
import sys

from assistant import brain, voice_words
from tests import command_check
from tests.blind.maps import MAPS

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARKS = MAPS["office"]

# name: (English request, Korean words before the verb, verb stem, its 아/어 form, Konglish / mixed forms)
CAPS = {
    "go_to":    ("go to p3", "p3로", "가", "가", ["p3로 고 해 줘", "go to p3 해 주세요"]),
    "home":     ("go home", "홈으로", "가", "가", ["홈으로 무브 해 줘"]),
    "forward":  ("move forward one meter", "앞으로 1미터", "가", "가", ["포워드로 1미터 가 줘"]),
    "back":     ("move back half a meter", "뒤로 50센티", "가", "가", ["백으로 50센티 가 주세요"]),
    "turn":     ("turn left", "왼쪽으로", "돌", "돌아", ["레프트로 턴 해 줘", "왼쪽으로 turn 해 주세요"]),
    "turn45":   ("turn right 45 degrees", "오른쪽으로 45도", "돌", "돌아", ["라이트로 45도 턴 해요"]),
    "look":     ("look left", "왼쪽", "보", "봐", ["왼쪽 룩 해 줘"]),
    "look_up":  ("look up", "위를", "보", "봐", ["업 봐 줘"]),
    "head_up":  ("raise your head", "고개", "들", "들어", ["헤드 업 해 줘"]),
    "head_dn":  ("lower your head", "고개", "숙이", "숙여", ["고개 다운 해 줘"]),
    "wave":     ("wave", "손", "흔들", "흔들어", ["웨이브 해 줘", "wave 해 주세요"]),
    "shake":    ("let's shake hands", "악수", "하", "해", ["셰이크 핸드 해 줘"]),
    "reach":    ("give me your hand", "손", "내밀", "내밀어", []),
    "follow":   ("follow me", "저를", "따라오", "따라와", ["팔로우 미 해 줘", "follow me 해 주세요"]),
    "come":     ("come here", "이리", "오", "와", ["컴 히어 해 줘"]),
    "stop":     ("stop", "", "멈추", "멈춰", ["스탑 해 주세요"]),
    "fetch":    ("bring me the cup", "컵", "가져오", "가져와", []),
    "pick":     ("pick up the cup", "컵", "집", "집어", ["컵 픽업 해 줘"]),
    "fold":     ("fold your arm", "팔", "접", "접어", []),
    "sing":     ("sing a song", "노래", "부르", "불러", ["노래 싱 해 줘"]),
    "louder":   ("speak louder", "더 크게", "말하", "말해", []),
    "slower":   ("speak slower", "좀 천천히", "말하", "말해", []),
    "quieter":  ("speak more quietly", "좀 작게", "말하", "말해", []),
    "look_dn":  ("look down", "아래를", "보", "봐", ["다운 봐 줘", "look down 해 주세요"]),
    "look_me":  ("look at me", "저를", "보", "봐", ["룩 앳 미 해 줘"]),
    "around":   ("turn around", "뒤로", "돌", "돌아", ["유턴 해 줘", "turn around 해 주세요"]),
    "come_back": ("come back", "", "돌아오", "돌아와", ["컴백 해 줘"]),
    "waist":    ("turn your waist left", "허리를 왼쪽으로", "돌리", "돌려", ["웨이스트 레프트로 돌려 줘"]),
    "body_up":  ("raise your body", "몸을", "올리", "올려", ["리프트 업 해 줘", "바디 업 해 줘"]),
    "open":     ("open your hand", "손", "펴", "펴", ["핸드 오픈 해 줘"]),
    "put":      ("put the cup down", "컵 내려", "놓", "놔", []),
    "charge":   ("go charge", "충전하러", "가", "가", ["차지하러 가 줘"]),
}
# other sentences of the same meaning: (words before the verb, verb stem, its 아/어 form), each said at every level
PARA = {
    "go_to":    [("p3로", "이동하", "이동해"), ("p3까지", "가", "가"), ("p3 쪽으로", "가", "가"), ("p3로", "움직이", "움직여")],
    "home":     [("홈으로", "돌아가", "돌아가"), ("홈 위치로", "가", "가")],
    "forward":  [("앞으로 1미터", "이동하", "이동해"), ("1미터 앞으로", "가", "가"), ("앞으로 1미터", "전진하", "전진해"),
                 ("1미터만 앞으로", "가", "가")],
    "back":     [("뒤로 50센티", "물러나", "물러나"), ("50센티 뒤로", "가", "가"), ("뒤로 50센티", "후진하", "후진해"),
                 ("50센티만 뒤로", "빠지", "빠져")],
    "turn":     [("왼쪽으로", "회전하", "회전해"), ("몸을 왼쪽으로", "돌리", "돌려"), ("왼편으로", "돌", "돌아"),
                 ("좌회전", "하", "해")],
    "turn45":   [("오른쪽으로 45도", "회전하", "회전해"), ("45도 오른쪽으로", "돌", "돌아")],
    "look":     [("왼쪽을", "보", "봐"), ("왼쪽", "쳐다보", "쳐다봐"), ("고개를 왼쪽으로", "돌리", "돌려")],
    "look_up":  [("위쪽을", "보", "봐"), ("위를", "쳐다보", "쳐다봐"), ("천장을", "보", "봐")],
    "head_up":  [("고개를", "들", "들어"), ("머리", "들", "들어"), ("고개를 위로", "올리", "올려")],
    "head_dn":  [("고개를", "숙이", "숙여"), ("머리를", "숙이", "숙여"), ("고개를 아래로", "내리", "내려")],
    "wave":     [("손을", "흔들", "흔들어"), ("손 한번", "흔들", "흔들어"), ("팔을", "흔들", "흔들어"),
                 ("손 흔들어서 인사", "하", "해")],
    "shake":    [("저랑 악수", "하", "해"), ("악수 한번", "하", "해"), ("나랑 악수", "하", "해")],
    "reach":    [("손을", "내밀", "내밀어"), ("팔을", "뻗", "뻗어"), ("손을 앞으로", "내밀", "내밀어")],
    "follow":   [("나를", "따라오", "따라와"), ("저", "따라다니", "따라다녀"), ("제 뒤를", "따라오", "따라와"),
                 ("날", "쫓아오", "쫓아와")],
    "come":     [("여기로", "오", "와"), ("이쪽으로", "오", "와"), ("나한테", "오", "와"), ("가까이", "오", "와"),
                 ("이리", "다가오", "다가와")],
    "stop":     [("거기", "서", "서"), ("동작", "멈추", "멈춰"), ("", "정지하", "정지해")],
    "fetch":    [("컵 좀", "가져오", "가져와"), ("컵", "갖고 오", "갖고 와"), ("저한테 컵", "가져오", "가져와"),
                 ("컵", "챙겨 오", "챙겨 와")],
    "pick":     [("컵을", "잡", "잡아"), ("컵을", "집어 들", "집어 들어"), ("컵", "픽업하", "픽업해")],
    "fold":     [("팔을", "접", "접어"), ("팔을", "거두", "거둬"), ("팔을 몸 쪽으로", "접", "접어")],
    "sing":     [("노래 한 곡", "부르", "불러"), ("노래", "하", "해"), ("노래 한 곡", "뽑", "뽑아")],
    "look_me":  [("나를", "보", "봐"), ("저 좀", "보", "봐"), ("여기를", "보", "봐"), ("저를", "쳐다보", "쳐다봐")],
    "around":   [("반 바퀴", "돌", "돌아"), ("180도", "돌", "돌아")],
    "come_back": [("원래 자리로", "돌아오", "돌아와"), ("다시", "돌아오", "돌아와")],
    "waist":    [("허리를 왼쪽으로", "틀", "틀어"), ("허리 왼쪽으로", "돌리", "돌려")],
    "body_up":  [("몸을", "높이", "높여"), ("키를", "높이", "높여"), ("몸을 위로", "올리", "올려")],
    "open":     [("손을", "펴", "펴"), ("손을", "벌리", "벌려"), ("집게를", "열", "열어"), ("그리퍼", "열", "열어")],
    "put":      [("컵", "내려놓", "내려놔"), ("컵을 테이블에", "놓", "놔"), ("컵", "내려 두", "내려 둬")],
    "charge":   [("충전기로", "가", "가"), ("충전하러", "이동하", "이동해")],
}
EN_FORMS = ["{}", "please {}", "{}, please", "could you {}?", "can you {} for me?", "would you {}, please?",
            "I'd like you to {}", "I'd love it if you could {}", "{}, if you don't mind", "lumi, {}",
            "it would be great if you could {}"]
# English forms where the verb must be first ("would you mind ...ing" is not made: no gerunds here)


def _j(c):
    n = ord(c) - 0xAC00
    return (n // 588, n // 28 % 21, n % 28) if 0 <= n < 11172 else None


def _with_final(c, final):
    l, v, _ = _j(c)
    return chr(0xAC00 + (l * 21 + v) * 28 + final)


def hon(stem):
    """The stem before an honorific -시- ending: 돌 -> 도, 집 -> 집으, 가 -> 가."""
    j = _j(stem[-1])
    if j[2] == 8:                                         # ㄹ drops: 도세요, 흔드세요
        return stem[:-1] + _with_final(stem[-1], 0)
    return stem + "으" if j[2] else stem


def ul(stem):
    """The stem's 관형형 before 수 / 줄: 가 -> 갈, 돌 -> 돌, 집 -> 집을."""
    j = _j(stem[-1])
    if j[2] == 8:
        return stem
    return stem + "을" if j[2] else stem[:-1] + _with_final(stem[-1], 8)


def past(a):
    """The past of the 아/어 form: 돌아 -> 돌았, 가 -> 갔, 해 -> 했."""
    return a[:-1] + _with_final(a[-1], 20)


def sida(stem):
    """The 하십시오체 suggestion: 가 -> 갑시다, 돌 -> 돕시다, 집 -> 집읍시다."""
    j = _j(stem[-1])
    if j[2] == 8:                                         # ㄹ drops: 돕시다, 흔듭시다
        return stem[:-1] + _with_final(stem[-1], 17) + "시다"
    return stem + "읍시다" if j[2] else stem[:-1] + _with_final(stem[-1], 17) + "시다"


def levels(pre, stem, a):
    """{level: [Korean forms]} for one verb phrase."""
    p = (pre + " ") if pre else ""
    h = hon(stem)
    return {
        "반말": [f"{p}{a}", f"{p}{a} 줘", f"{p}{a} 줄래?", f"{p}{a} 줄 수 있어?", f"{p}좀 {a} 줘"],
        "friendly": [f"{p}{a} 봐", f"{p}한번 {a} 봐", f"{p}{a} 줘 봐", f"{p}{a} 줘라", f"{p}{a} 줘~", f"루미야 {p}{a} 줘"],
        "해요": [f"{p}{a}요", f"{p}{a} 주세요", f"{p}{a} 줄래요?", f"{p}{a} 줄 수 있어요?", f"{p}좀 {a} 주세요"],
        "하십시오": [f"{p}{h}십시오", f"{p}{a} 주십시오", f"{p}{a} 주시겠습니까?", f"{p}{a} 주시기 바랍니다",
                    f"{p}{a} 주실 수 있습니까?"],
        "하게": [f"{p}{a} 주게", f"{p}{a} 주시게"],
        "honorific": [f"{p}{h}세요", f"{p}{a} 주시겠어요?", f"{p}{a} 주실 수 있으신가요?", f"{p}{a} 주셨으면 해요",
                      f"{p}{a} 주시면 감사하겠습니다", f"{p}{a} 주시길 부탁드립니다", f"{p}{a} 주세요, 부탁드립니다",
                      f"루미 씨, {p}{a} 주시겠어요?"],
        "question": [f"{p}{a} 주면 안 돼?", f"{p}{a} 주면 안 될까요?", f"{p}{a} 주실래요?", f"{p}{ul(stem)} 수 있으세요?",
                     f"{p}{a} 줄 수 있을까요?"],
        "dialect": [f"{p}{a} 도", f"{p}{a} 주이소", f"{p}{a} 주랑께", f"{p}{a} 줘유", f"{p}{a} 줍서", f"{p}{a}라 마"],
        "slip": [f"{p}{a}줘", f"{p}{a} 주세여", f"{p}{a}조", f"{(pre + a).replace(' ', '')} 줘"],
        "suggest": [f"{p}{stem}자", f"{p}{sida(stem)}", f"자, {p}{stem}자"],
        "rude": [f"야, {p}{a}", f"야 {p}{a}라", f"빨리 {p}{a}", f"{p}{a}라 빨리", f"당장 {p}{a}", f"{p}{a}라고",
                 f"{p}{a} 봐라", f"얼른 {p}{a} 줘", f"야 루미, {p}{a}"],
    }


def not_now(pre, stem, a):
    """The same phrase with no order now: a past, an ability question, a negation, a later time, a condition."""
    p = (pre + " ") if pre else ""
    return [f"아까 {p}{past(a)}어요", f"어제 {p}{past(a)}잖아", f"{p}{ul(stem)} 줄 알아요?", f"{p}{stem}지 마세요",
            f"{p}{stem}지 마", f"이따가 {p}{a} 주세요", f"제가 손 들면 {p}{a} 주세요", f"{p}{a} 주면 어떻게 돼요?",
            f"우리 애가 {p}{past(a)}어요", f"{p}{hon(stem) if _j(stem[-1])[2] == 8 else stem}는 거 봤어요"]


def read(text):
    """The reading lumi.answer()'s rules give (None: left to the LLM)."""
    voice = voice_words.read(text, "")
    if voice:
        return f"voice {voice[0]} {voice[1]:+d}"
    return command_check.rules(text, "idle", MARKS, brain.Brain())


def same(want, got):
    return got == want or got is not None and want is not None and command_check.ok(want, got) == "right"


SUGGEST_FOR = {"go_to", "home", "forward", "back", "turn", "turn45", "wave", "shake", "sing", "around", "charge", "look", "look_up",
               "look_dn"}    # "p3로 가자", "악수합시다": a suggestion is an order only where Lumi does it with the visitor


def check(names=None, para=True):
    """rows: (capability, level, text, reading, want, verdict) with verdict right / missed / wrong / motion."""
    rows = []
    for name, (en, pre, stem, a, mixed) in CAPS.items():
        if names and name not in names:
            continue
        want = read(en)
        forms = {"en": [f.format(en) for f in EN_FORMS], **levels(pre, stem, a), "konglish": mixed}
        for pp, ps, pa in PARA.get(name, []) if para else []:
            for level, texts in levels(pp, ps, pa).items():
                forms["para_" + level] = forms.get("para_" + level, []) + texts
        if name not in SUGGEST_FOR:
            forms = {k: v for k, v in forms.items() if not k.endswith("suggest")}
        for level, texts in forms.items():
            for t in texts:
                got = read(t)
                rows.append((name, level, t, got, want, "right" if same(want, got) else
                             "missed" if got is None or got.split()[0] in command_check.NO_MOTION else "wrong"))
        for t in not_now(pre, stem, a) + [t for pp, ps, pa in (PARA.get(name, []) if para else []) for t in not_now(pp, ps, pa)]:
            got = read(t)
            moves = got is not None and got.split()[0] not in command_check.NO_MOTION and \
                not (got == "action:look away" and "지 마" in t)   # "저를 보지 마세요": looking away is asked
            rows.append((name, "not_now", t, got, "no motion", "right" if not moves else
                         "wrong" if got in ("stop", "sing") else "motion"))   # a stop or a song moves nothing
    return rows


def report(rows):
    by = collections.defaultdict(collections.Counter)
    for name, level, *_, v in rows:
        by[level][v] += 1
    lines = ["# Korean speech levels against English (tests/ko_levels_check.py)", "",
             "| level | right | missed | wrong | motion | total |", "|---|---|---|---|---|---|"]
    for level, c in by.items():
        lines.append(f"| {level} | {c['right']} | {c['missed']} | {c['wrong']} | {c['motion']} | {sum(c.values())} |")
    tot = collections.Counter(v for *_, v in rows)
    lines += [f"| all | {tot['right']} | {tot['missed']} | {tot['wrong']} | {tot['motion']} | {len(rows)} |", "",
              "## Not right", ""]
    lines += [f"- {name} [{level}] {t!r} -> {got} (want {want})" for name, level, t, got, want, v in rows if v != "right"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    out = report(check(set(sys.argv[1:]) or None))
    (ROOT / "logs" / "ko_levels.md").write_text(out)
    print(out[:out.index("## Not right")])
