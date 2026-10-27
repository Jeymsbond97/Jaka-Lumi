"""Spoken answers about what Lumi sees, from vision/scene.py: "do you see the red apple?", "how far is it?", "what's on
the table?", "how many people are here?", "what am I holding?", "what colour is my shirt?", "is my hand raised?",
"am I wearing glasses?" (the slow VLM), "am I sitting or standing?", English and Korean.

    answer(text, lang, frames=None, slow_line=None) -> spoken sentence, or None when the words are not such a question
    facts() -> one line of what the cameras see now, for the conversation model; facts_for(text) only when the words
    are about seeing

    python assistant/seeing.py "do you see a cup?"          # answer from the cameras now
    python assistant/seeing.py --load tests/data/scene_white_shirt_near "what colour is my shirt?"

Only what the detections give is said; anything else is "I can't tell". "What am I holding?" tries harder first: fresh
looks until two agree (a weak detector box counts then), the same thing's colour kept steady for STEADY_S, then a close
look by gemma4 at the hand picture with the measured facts ("Let me look closely."), and when still unsure what it seems
to be and a request for a hint, looked at again with the hint. Nothing here moves the head.
Every answer comes from frames taken after the words (scene.snapshot(since=...)), also a follow-up right after one
("really?", "and now?", "다시 봐": the same question again) and a correction ("it's white", "오른손이야"), which is
checked against the camera and agreed with only when the camera sees it so.
"""
import re
import sys
import threading
import time
from collections import Counter
from pathlib import Path

from assistant import brain
from vision import objects, pose, scene

ROOT = Path(__file__).resolve().parents[1]      # the project folder
NEAR_SAY = 6                     # at most this many kinds of things named in "what do you see"
DESCRIBE_SCORE = 0.3             # weaker boxes (depth-checked cups) count for "do you see a cup", not in the list
THREAD_S = 60.0                  # s; this long after a seeing answer the conversation model gets a new look too
CLAIM_WORDS = 14                 # words; a correction is short: "no, it's my right hand", "아니야 흰색이야"
BIG = {"dining table", "chair", "couch", "bed", "refrigerator", "sink", "oven", "tv", "toilet", "bench"}   # not "on a table"

COLOURS = {"white": "white", "red": "red", "blue": "blue", "green": "green", "yellow": "yellow", "black": "black",
           "orange": "orange", "grey": "grey", "gray": "grey", "purple": "purple", "pink": "pink",
           "brown": "brown", "light blue": "light blue", "sky blue": "light blue", "pale blue": "light blue",
           "흰": "white", "하얀": "white", "빨간": "red", "파란": "blue", "초록": "green", "노란": "yellow", "검은": "black",
           "까만": "black", "주황": "orange", "회색": "grey", "보라": "purple", "분홍": "pink", "핑크": "pink",
           "하양": "white", "빨강": "red", "파랑": "blue", "노랑": "yellow", "검정": "black", "까망": "black", "갈색": "brown", "하늘": "light blue",
           "브라운": "brown", "beige": "beige", "베이지": "beige"}   # "brown", "beige" are only said by people: the camera
                                 # names browns orange
COLOUR_KO = {"white": "흰색", "red": "빨간색", "blue": "파란색", "green": "초록색", "yellow": "노란색", "black": "검은색",
             "orange": "주황색", "grey": "회색", "purple": "보라색", "pink": "분홍색", "brown": "갈색", "light blue": "하늘색", "beige": "베이지색"}
SYNONYMS = {"mug": "cup", "glass": "cup", "tumbler": "cup", "coffee": "cup", "phone": "cell phone", "mobile": "cell phone",
            "smartphone": "cell phone", "plant": "potted plant", "flower": "potted plant", "table": "dining table",
            "desk": "dining table", "monitor": "tv", "screen": "tv", "television": "tv", "computer": "laptop",
            "notebook": "laptop", "bag": "handbag", "ball": "sports ball", "sofa": "couch", "people": "person",
            "man": "person", "woman": "person", "someone": "person", "anyone": "person", "somebody": "person",
            "anybody": "person", "fridge": "refrigerator", "doughnut": "donut", "glasses": "wine glass"}
KO = {"person": "사람", "bicycle": "자전거", "car": "자동차", "motorcycle": "오토바이", "airplane": "비행기", "bus": "버스",
      "train": "기차", "truck": "트럭", "boat": "보트", "traffic light": "신호등", "fire hydrant": "소화전",
      "stop sign": "정지 표지판", "parking meter": "주차 미터기", "bench": "벤치", "bird": "새", "cat": "고양이", "dog": "개",
      "horse": "말", "sheep": "양", "cow": "소", "elephant": "코끼리", "bear": "곰", "zebra": "얼룩말", "giraffe": "기린",
      "backpack": "백팩", "umbrella": "우산", "handbag": "가방", "tie": "넥타이", "suitcase": "여행 가방",
      "frisbee": "원반", "skis": "스키", "snowboard": "스노보드", "sports ball": "공", "kite": "연", "baseball bat": "야구 방망이",
      "baseball glove": "야구 글러브", "skateboard": "스케이트보드", "surfboard": "서핑보드", "tennis racket": "테니스 라켓",
      "bottle": "병", "wine glass": "와인잔", "cup": "컵", "fork": "포크", "knife": "칼", "spoon": "숟가락", "bowl": "그릇",
      "banana": "바나나", "apple": "사과", "sandwich": "샌드위치", "orange": "오렌지", "broccoli": "브로콜리",
      "carrot": "당근", "hot dog": "핫도그", "pizza": "피자", "donut": "도넛", "cake": "케이크", "chair": "의자",
      "couch": "소파", "potted plant": "화분", "bed": "침대", "dining table": "테이블", "toilet": "변기", "tv": "모니터",
      "laptop": "노트북", "mouse": "마우스", "remote": "리모컨", "keyboard": "키보드", "cell phone": "휴대폰",
      "microwave": "전자레인지", "oven": "오븐", "toaster": "토스터", "sink": "싱크대", "refrigerator": "냉장고",
      "book": "책", "clock": "시계", "vase": "꽃병", "scissors": "가위", "teddy bear": "곰 인형", "hair drier": "드라이기",
      "toothbrush": "칫솔"}
KO_WORDS = {**{v: k for k, v in KO.items()}, "폰": "cell phone", "핸드폰": "cell phone", "전화": "cell phone",
            "잔": "cup", "머그": "cup", "식물": "potted plant", "꽃": "potted plant", "책상": "dining table",
            "식탁": "dining table", "배낭": "backpack", "컴퓨터": "laptop", "티비": "tv", "가방": "handbag", "물병": "bottle",
            "탁자": "dining table"}

KO_CANON = ((r"있습니까|있나요|있냐|있니|있노|있는교|있심니꺼|있습니꺼|있는가|있나(?=\s*\?|$)", "있어"),
            (r"보입니까|보이나요|보이냐|보이니|보이노|보이는교|보이십니까|보이세요|보이시나요|보이시죠|보이죠|보이는가|보입니꺼|보이나(?=\s*\?|$)", "보여"),
            (r"하는\s*중이(?:게|야|에요|예요|냐|니|노|지)?|하고\s*있게", "하고 있"), (r"어데|어디메", "어디"),
            (r"참말로|참말|레알", "진짜"), (r"무엇을", "뭘"), (r"무엇이", "뭐가"), (r"무엇", "뭐"), (r"뭣", "뭐"),
            (r"입니까|인가요|이냐|이니|이노|인교|입니꺼", "이야"), (r"(미터|명|개)고(?=\s*\?)", r"\1야"),
            (r"아닙니다|아입니다|아이다", "아니야"), (r"(?<=[가-힣])입니다", "이야"), (r"말씀해", "말해"),
            (r"(?<![가-힣])내(?=하고|랑)", "나"), (r"(?<![가-힣])니(?=하고|랑)", "너"), (r"(?:나|저)하고\s*(?:너|루미)하고", "나하고"),
            (r"(?<![가-힣])함(?=\s)", "한번"), (r"^(\W*(?:\S+\s+)?)(그럼|그러면|근데|그리고)(?=[가-힣])", r"\1\2 "), (r"려어(?=놨|놓)", "려"), (r"(?<=[\s가-힣])(?:보십시오|보세요|봐요|보이소|봐라|봐\s*주세요|봐\s*줘)", "봐"))
EN_IN_KO = ((r"\bwhat\s*(?:colou?r|색)", "무슨 색"), (r"\bcolou?rs?\b", "색"), (r"\bwhich side\b", "어느 쪽"),
            (r"\b(?:you\s+)?see\b", "보여"), (r"\bhow far\b", "얼마나 떨어져"), (r"\bdistance\b", "거리"),
            (r"\bnow\b", "지금"), (r"\breally\b", "진짜"), (r"\bholding\b|\bhold\b", "들고"), (r"\bhow many\b", "몇"),
            (r"\bpeoples?\b", "사람"), (r"\bpocket\b", "주머니"), (r"\bfingers?\b", "손가락"), (r"\bwhat\b", "뭐"),
            (r"\bmy\b", "내"), (r"\bme\b", "나"), (r"\bshirt\b", "셔츠"), (r"\b(?:pants|trousers)\b", "바지"),
            (r"\bleft hand\b", "왼손"), (r"\bright hand\b", "오른손"), (r"\bhand\b", "손"), (r"\bwearing\b|\bwear\b", "입고"), (r"\b(?:outfit|clothes)\b", "옷"),
            *((rf"\b{c}\b", COLOUR_KO[v]) for c, v in COLOURS.items() if c.isascii()),
            (r"\bsunglasses\b", "선글라스"), (r"\bglasses\b", "안경"), (r"\b(?:hats?|caps?|beanie)\b", "모자"),
            (r"\b(?:shoulder )?bags?\b|\bhandbag\b", "가방"), (r"\bbackpack\b", "백팩"), (r"\bhair\b", "머리"),
            *((rf"\b{re.escape(n)}(?:e?s)?\b", KO[SYNONYMS.get(n, n)]) for n in sorted(set(KO) | set(SYNONYMS), key=len, reverse=True)
              if SYNONYMS.get(n, n) in KO and SYNONYMS.get(n, n) != "person" and n != "glasses"))
EN_IN_KO = tuple((rx.replace(r"\b", r"(?<![A-Za-z])", 1).replace(r"\b", r"(?![A-Za-z])"), to) for rx, to in EN_IN_KO)
                                 # an English word glued to a Korean particle ("outfit이야") is still a word
KO_IN_EN = ((r"색깔?|컬러", "colour"), (r"상의|윗옷", "top"), (r"바지", "trousers"), (r"(?<![가-힣])(?:나|저)(?![가-힣])", "me"),
            (r"(?<![가-힣])(?:내|제)(?![가-힣])", "my"), (r"손가락", "fingers"), (r"주머니", "pocket"), (r"사람", "people"),
            (r"오른손", "right hand"), (r"왼손", "left hand"), (r"신발", "shoes"), (r"셔츠", "shirt"), (r"보여", "see"))
EN_CANON = ((r"\bpeoples\b", "people"), (r"\b(is|are) dare\b", r"\1 there"), (r"\bready,? (?:set|steady),? go\b\W*", ""), (r"\bu\b", "you"), (r"\bda\b", "the"), (r"\bwhat (?:do )?i hold\b", "what am I holding"),
            (r"\bwhat i am (wearing|holding|doing)\b", r"what am I \1"), (r"\bwhat (?:clothes )?(?:do )?i wear(?:ing)?\b", "what am I wearing"),
            (r"\bwhat you see\b", "what do you see"), (r"\b(?:would|will) you be able to see\b|\bare you able to see\b", "can you see"),
            (r"^\W*(?:a |an |the )?(?!(?:do|does|can|could|would|will|did|i|you|and|so|what|which|how)\b)([a-z]+(?: [a-z]+)?) "
             r"(?:do )?you (?:can )?see\b", r"do you see a \1"), (r"^\W*(?:(?:robot|lumi)\W+)?you (?:can )?see\b", "do you see"),
            (r"\bcolou?r is what\b", "what colour is it"), (r"\b(?:how )?(?:me far|far me)\b(?: how much)?", "how far am I"),
            (r"\bthis hand\b", "my hand"),
            (r"^\W*(?:in )?my (left |right )?hand,? (?:something,? )?what(?: is)?\b", r"what is in my \1hand"),
            (r"^\W*(left|right) hand,? what(?: is)?\b", r"what is in my \1 hand"),
            (r"^\W*(?:the |a )?([a-z]+(?: [a-z]+)?) is (?:here|there)\s*\?", r"is there a \1 here?"),
            (r"[,.!]\s*(?:go|come on|quick(?:ly)?)\W*$", ""),
            (r"^\W*(?:(?:lumi|robot)\W+)?(?:my )?hands? (?:up|raised),? me\s*\?", "is my hand up?"),
            (r"^\W*(glasses|sunglasses|hat|cap|mask|bag|backpack),? (?:on )?me,?(?: yes or no)?\s*\?", r"am I wearing \1?"), (r"\bhow much (?:persons?|people|peoples)\b", "how many people"),
            (r"^\W*(?:the |my |a )?(?!(?:you|it|that|this|he|she|they|i)\b)([a-z]+(?: (?!is\b)[a-z]+)?) (?:is )?where\b", r"where is the \1"),
            (r"^\W*on the (table|desk),? what (?:things |stuff )?(?:are|is)(?: there)?\b", r"what is on the \1"), (r"\bis either of my hands\b", "is my hand"),
            (r"^\W*my (\w+(?: \w+)?) (" + "|".join(c for c in COLOURS if c.isascii()) + r"),? (?:yes|right|correct|no)\s*\?",
             r"is my \1 \2?"))


def canons(t):
    """canon(t), then the mixed sentence read both ways (English words as Korean, Korean words as English): the
    readers take the first that asks something."""
    t = canon(t)
    if not (re.search(r"[가-힣]", t) and re.search(r"[A-Za-z]", t)):
        return [t]
    ko, en = len(re.findall(r"[가-힣]+", t)), len(re.findall(r"[A-Za-z]+", t))
    a, b = _swap(t, EN_IN_KO), _swap(t, KO_IN_EN)
    return [a, t, b] if ko >= en else [b, t, a]           # "빨간 apple 보여?" -> "빨간 사과 보여?" first


def _swap(t, rules):
    for rx, to in rules:
        t = re.sub(rx, to, t, flags=re.I)
    return t


_PIECE = r"\bhair\b|\bsunglasses\b|\bglasses\b|\bhats?\b|\bcaps?\b|\bmask\b|\bbag\b|\bbackpack\b|\bshirt\b|\bt-shirt\b|" \
         r"\btop\b|\bjacket\b|\bpants\b|\btrousers\b|\bjeans\b|\bshoes\b|\bskirt\b|\bshorts\b|" \
         r"머리|안경|선글라스|모자|마스크|가방|백팩|티셔츠|셔츠|상의|윗옷|웃옷|바지|청바지|하의|치마|신발|재킷|자켓"
SELF_FIX = re.compile(r"(?:\.{2,}|[,!?.]|\s)\s*(?:아\s+)?(?:아니(?:요|야)?|아냐|아뇨|no+|nope|sorry|wait|i mean|uh+|um+|er+|"
                      r"or rather)\b[\s,!.]*(?:(?:i mean|sorry|i meant)\b[\s,]*)?(?P<rest>[^?]*?)(?:,?\s*i mean)?\W*$", re.I)


def self_fixed(t):
    """A thing named again after "no" / "아 아니" / "sorry, I mean" in the same question: the question about that one
    ("do you see an umbrella... no, a teddy bear?" -> "do you see a teddy bear?"); else t."""
    m = SELF_FIX.search(t)
    if not m or not m.group("rest"):
        return t
    rest, head = m.group("rest"), t[:m.start()]
    piece = re.match(rf"(?:(?:a|an|the|my|내|제)\s+)?(?P<w>{_PIECE})", rest, re.I)
    if piece:                                              # "what colour is my hat, uh, my hair?", "가방, 아니 모자 썼어?"
        old = list(re.finditer(_PIECE, head, re.I))
        if old:
            o = old[-1]
            return head[:o.start()] + piece.group("w") + head[o.end():] + rest[piece.end():] + \
                ("?" if t.rstrip().endswith("?") else "")
    new = re.fullmatch(r"(?:(?:a|an|the|my)\s+)?" + _THING_EN, rest, re.I) or \
        re.fullmatch(_THING_KO + r"(?:이|가|요|야|이야|이요)?", rest)
    if not new or not _name(new.group("obj")):
        return t
    old = list(re.finditer(_THING_EN, head, re.I)) or list(re.finditer(_THING_KO, head))
    if not old:
        return t
    o = old[-1]
    said = re.sub(r"^(?:the|a|an|my)\s+", "", new.group(0), flags=re.I)
    return head[:o.start()] + said + head[o.end():].rstrip(" ?.!,") + "?"


def canon(t):
    """A question in one plain form for the readers: Korean dialect and speech levels as 반말 ("사과 있냐?", "가방 어데
    있노?", "보이십니까?"), English words in a Korean sentence as Korean ("바지 what color야?" -> "바지 무슨 색야?") and
    Korean words in an English one as English ("What 색 is my 상의?"), non-native English as plain ("me far how
    much?", "what clothes I wear?", "backpack is here?")."""
    t = re.sub(r"\S*[—–]\s*", "", t)                     # a stutter: "있— 있어요", "O— Oh"
    t = re.sub(r"\s*(?:\.{2,}|…)\s*$", "?", t)              # trailing dots for a question mark
    t = self_fixed(t)
    for rx, to in KO_CANON:
        t = re.sub(rx, to, t)
    t = GLUED_COLOUR.sub(r"\1 ", t)
    t = re.sub(r"(?<![가-힣])(제|내)(?=머리|바지|옷|윗옷|셔츠|티셔츠|신발|모자|안경|가방|손|자세)", r"\1 ", t)   # "제머리색 뭐예요?"                        # "분홍색바나나 보여?" -> "분홍색 바나나 보여?"
    if not re.search(r"[가-힣]", t):
        for rx, to in EN_CANON:
            t = re.sub(rx, to, t, flags=re.I)
    return t


class _Any:
    """Several patterns asked as one: .search gives the first match (each has its own col / obj groups)."""
    def __init__(self, *rxs):
        self.rxs = rxs

    def search(self, t):
        return next((m for rx in self.rxs if (m := rx.search(t))), None)


_EN_NAMES = sorted(set(objects.COCO) | set(SYNONYMS), key=len, reverse=True)
_THING_EN = r"(?:(?P<col>" + "|".join(c for c in COLOURS if c.isascii()) + r")\s+)?(?<![a-z])(?P<obj>" + \
    "|".join(re.escape(n) for n in _EN_NAMES) + r")(?:e?s)?(?![a-z])"
_THING_KO = r"(?:(?P<col>" + "|".join(c for c in COLOURS if not c.isascii()) + r")\w*\s*)?(?<![가-힣])(?<!몇 )(?P<obj>" + \
    "|".join(sorted(KO_WORDS, key=len, reverse=True)) + r")(?=[\s?.,!~]|$|[은는이가을를도의에랑와과요야]|까지|하고)"
                                 # a whole word: not 연 (kite) in 연구소, 개 (dog) in "몇 개"
GLUED_COLOUR = re.compile(r"((?:" + "|".join(c for c in COLOURS if not c.isascii()) + r")색)(?=(?:" +
                          "|".join(sorted(KO_WORDS, key=len, reverse=True)) + r"))")

SEE_ME = re.compile(r"^\W*(?:wait,?\s*)?you see me\b|" r"(?<![가-힣])(?:나|저)\s*(?:를|가)?\s*잘\s*보여|" r"\b(do|can) you see me\b|\bam i (visible|in (your )?view)\b|(?<![가-힣])(나|저)(를|)? ?보여|(?<![가-힣])(나|저) ?보이|(?:내가|제가)\s*보여", re.I)
SEE_THING = re.compile(r"(?<!what )\b(?:do|can|could) you (?:still )?(?:see|spot|notice)\b.*?\b(?:a|an|the|any|some|my)?\s*" + _THING_EN, re.I)
THERE_IS = re.compile(r"\b(?:is|are) there (?:still )?(?:a|an|any|some)\s+" + _THING_EN +
                      r"(?! (?:open|close|nearby|near here|around here))", re.I)
STILL_THERE = re.compile(r"\bis (?:the|my|that|your|this) " + _THING_EN + r" still (?:there|here|on|in)\b", re.I)
SEE_THING_KO = re.compile(_THING_KO + r"(?:이|가|은|는|을|를|도)?\s*(?:(?:(?:아직도?|지금도?|still)\s*)?(?:보여|보이|찾을\s*수\s*있)|아직도?\s*있|"
                          r"(?:(?:저기|여기|거기|앞에)\s*)?있(?:어|나|니|습|잖|는데)|"
                          r"(?:\s*(?:치웠|갖다\s*놨|올려\s*놨|놨|뒀)\S*\W+(?:\S+\s+)?(?:아직\s*|이제\s*)?(?:보여|보이|있)))")
                                 # "사과 아직 보여요?", "컵이 아직 있습니까?", "바나나가 있어요?", "컵 치웠어요. 아직 보여요?"
SEE_MORE = _Any(re.compile(r"(?:^\W*(?:\w+\W+)?any|\bthere(?:'s| is))\s+(?:(?:a|an|some)\s+)?" + _THING_EN + r"(?:\s+(?:around|here|in front|right there))", re.I),
            re.compile(r"\bi (?:can )?see (?:a|an|the)\s+" + _THING_EN, re.I),
            re.compile(r"\bis (?:a|an|the) " + _THING_EN + r" (?:somewhere )?(?:near|around|here)", re.I),
            re.compile(r"\b(?:can|could) you find\s+(?:a|an|the|any|my)\s+" + _THING_EN + r"\s+(?:here|around)", re.I),
            re.compile(r"\b(?:looking for|brought|put|took|moved|got|have)\s+(?:a|an|the|my|this|that)\s+" + _THING_EN +
                       r"\b.*\b(?:see (?:it|one|them)|still there|is it there)\b", re.I),
            re.compile(r"(?<![a-z])" + _THING_EN + r"\s*(?:이|가|는|도)?\s*(?:(?:아직|still)\s*)?(?:보여|보이|있어|있나|있니|있잖|있는데|"
                       r"see\s*(?:돼|되|가능))", re.I))
                                 # "any apple around here?", "I brought a cup. see it?", "bottle 보여?", "여기 banana 있나?"
WHERE_THING = _Any(re.compile(r"\bwhere(?:'s| is| are| did you see| exactly is)\s+(?:exactly\s+)?(?:the|my|a|an)\s+" + _THING_EN, re.I),
               re.compile(r"\bwhich side(?: is)? (?:the|my) " + _THING_EN, re.I),
               re.compile(r"\bis (?:the|my) " + _THING_EN + r" (?:on|to) (?:your|the|my) (?:left|right)\b", re.I),
               re.compile(r"(?<![a-z])" + _THING_EN + r"\s*(?:은|는|이|가)?\s*(?:left|right|왼쪽|오른쪽)(?:야|이야|에)", re.I),
               re.compile(_THING_KO + r"\s*(?:는|은|이|가)?\s*(?:어디|위치|어느\s*(?:쪽|side)|왼쪽이야|오른쪽이야)"),
               re.compile(r"(?<![a-z])" + _THING_EN + r"\s*(?:은|는)?\s*(?:어디|위치|어느\s*(?:쪽|side))", re.I))
                                 # "where exactly is the banana?", "노트북은 왼쪽이야 오른쪽이야?", "laptop 어느 side에 있어?"
HOW_FAR = re.compile(r"\bhow far\b|\bhow (?:near|close)\b|\bwhat(?:'s| is) the distance\b|\bhow many (?:meters|metres)\b|"
                     r"\bam i close\b|\bdistance\s*(?:얼마|몇)|\bdistance (?:to|from)\b|몇\s*(?:미터|meter|m\b)|떨어져\s*있|"
                     r"우리\s*사이|얼마나 ?(?:멀|떨어|가까)|거리가?|(?:거기|그거|저거|걔)까지\s*얼마나",
                     re.I)
HOW_FAR_THING = re.compile(r"\b(?:how far|how (?:near|close)|how many (?:meters|metres)|distance (?:to|from)).*?\b(?:the|that|this|a|an)\s+" + _THING_EN, re.I)
FAR_THING = _Any(HOW_FAR_THING, re.compile(r"(?<![a-z])" + _THING_EN + r"\s*(?:까지|이랑|랑)?\s*(?:distance|거리)", re.I),
             re.compile(_THING_KO + r"\S*\s*(?:까지|이랑|랑|와|하고)?\s*(?:의\s*)?(?:거리|얼마나\s*(?:멀|떨어)|몇\s*(?:미터|meter))"))
WHAT_SEE = re.compile(r"\bwhat (?:do|can) you see\b|\bwhat(?:'s| is| are)? (?:there )?in front of you\b|"
                      r"\bwhat(?:'s| is) (?:(?:still|now) )?(?:on|at) the (?:table|desk|테이블)|\bwhat(?:'s| is) (?:around|near) you\b|"
                      r"\bdescribe what you see\b|\bwhat are you (?:looking at|seeing)\b|\btell me what you see\b|"
                      r"\bwhat (?:things|stuff|objects)? ?(?:is |are )?(?:there |lying |sitting )?on the (?:table|desk)\b|"
                      r"\bwhat(?:'s| is) (?:lying|sitting|there) on the (?:table|desk)\b|\banything on the (?:table|desk)\b|"
                      r"\btell me what you (?:can )?see\b|\bwhat (?:things|objects|stuff) (?:are|is) (?:there )?in front of you\b|"
                      r"뭐가 ?보여|무엇이 ?보여|뭐 ?보여|뭐가 ?보이|뭐 ?보이|앞에 ?(?:뭐|무엇)|"
                      r"(?:테이블|탁자|책상|table) ?(?:위에|에|위)? ?(?:things\s*)?(?:뭐|무엇|있는 ?거)|"
                      r"뭘 ?보고 ?있", re.I)
BEHIND = re.compile(r"뒤쪽에\s*(?:뭐|무엇|누가|누구)|" r"\bwhat(?:'s| is) behind you\b|^(?!.*\b(?:look|turn|check|peek|glance)\b).*\bbehind you\b.*\?|"   # not "can you look
                    r"뒤에 ?(?:뭐|무엇|누가|누구)", re.I)   # "뒤에 뭐 있는지 봐 줘" too: the cameras answer it
SIDE_Q = re.compile(r"\bwhat(?:'s| is| do you see| can you see)? (?:there )?(?:on|to|at) (?:your|the) (?P<e>left|right)(?: side)?\s*\?|"
                    r"\b(?:can|do) you see (?:what(?:'s| is)|anything|anyone|something) (?:on|to|at) (?:your|the) (?P<e2>left|right)\b|"
                    r"(?<![가-힣])(?P<k>왼|오른)쪽에\s*(?:뭐|무엇|뭔가|누가|누구)\S*\s*(?:있|보여|보이)"
                    r"(?!.*(?:봐|보세요|봐\s*줘|봐\s*주세요|보십시오|봐라)\W*$)", re.I)
                                 # "can you see what's on your right?", "왼쪽에 뭐 있어?": the cameras now (a question,
                                 # not "peek / glance to your right": the look rule, brain)                                             # behind you?" (a head turn)
HOW_MANY = re.compile(r"\bhow many (?:people|persons|visitors|humans|folks|guys)\b|\bhow many of us\b|몇 ?(?:명|사람)|몇\s*분이?나?\s*(?:보여|있)|"
                      r"몇\s*분\s*(?:이\s*)?계|\bcount (?:the )?(?:people|persons|heads|us)\b|사람\s*(?:count|how many)|"
                      r"\bare we (?:\w+ )?(?:or|two|three|four)\b.*\bhow many\b|"
                      r"^\W*(?:(?:and|so|okay)\W+)?(?:(?:지금|이제|now)\s*(?:은|는)?\s*how many|how many(?: do you see| are there)? now)\W*$|"
                      r"\bhow many(?: (?:people|of us))?(?: do you see| are there| (?:are )?(?:here|left))? now\b",
                      re.I)   # "How many now?", "someone left. How many now?"
NOT_IN_VIEW = re.compile(r"\b(?:work|works|working|employ\w*|staff|company|companies|campy|firm|cutshion|country|city|"
                         r"live|lives|living|world|team|office|branch|developers?|engineers?|built|made|came|visited|talked|met)\b|"
                         r"직원|회사|쿳션|일하|일해|근무|나라|국가|도시|살아|사는|인구|팀|지사|만든|만들|개발자|엔지니어|왔었|다녀갔|만났|얘기했|이야기했",
                         re.I)   # "how many people work at Cutshion?": the company, not the cameras
HOLDING = re.compile(r"\bi (?:just )?picked (?:something|it|this|that|one) up\b.*\bwhat\b|"
                     r"(?:뭐|뭘|무엇을?|뭔가|하나)\s*(?:집었|주웠|잡았)\S*\W*(?:\S+\s+)?(?:뭐|뭔|무엇|what)|"
                     r"(?<![가-힣])손(?:에는|엔|에)\s*(?:뭐|뭘|무엇)(?:가|이)?\s*(?:들었|있|쥐|잡)|" r"\bi'?m holding (?:an? |the |my )?(?:\w+ )?\w+,? (?:right|correct|yes)\s*\?|" r"^\W*(?:\S+\s+)?(?:이거|이건|이게|이기|이것)\s*\S+\s*맞(?:죠|지|제|아|나요|습니까|나)|" r"(?:사람|분|person|친구)\S*\s*(?:은|는)?\s*(?:지금\s*)?(?:손에\s*)?(?:뭐|뭘|무엇을?)\s*(?:들었|들고|holding|쥐고)|" r"\bwhat (?:thing )?(?:do )?i hold\b|" r"\bwhat(?:'s| is| am| do)? (?:i|is (?:in|on) my (?:left |right |other )?hands?|(?:in|on) my (?:left |right |other )?hands?)\b.*?\b(?:holding|carrying|have)\b|"
                     r"\bwhat(?:'s| is)(?: it| this| that)? (?:in|on|with) my (?:left |right |other )?hands?\b|\bwhat(?:'s| is) my (?:left |right |other )?hands?\?|\bwhat (?:do )?i have (?:in|on) my (?:left |right |other )?hands?\b|\bam i holding\b|"
                     r"\bis there (?:something|anything) in my hand\b|\bwhat is this\b(?=.*\bhand\b)|\bwhat am i hold in\b|\banything (?:in|on) my (?:left |right |other )?hands?\b|"
                     r"\bwhat\b.{0,25}\b(?:i'?m|i am) (?:holding|carrying)\b|\bwhat(?:'ve| have| do) i (?:got|have)\b(?! to)|"
                     r"\bwhat(?:'s| is) this(?: thing)?\W*$|\bwhat i(?:'ve| have) got\b|hold\s*했\S*\W+.*뭐|"
                     r"(?<!루미 )(?<!네 )손에\s*(?:뭐|뭘|든|있는).{0,15}(?:보여|보이|알아|맞혀|\bwhat is it\b)|"   # Lumi's hand: status
                     r"(?:my\s*hand|(?:내|제)\s*(?:오른|왼)?손)\s*에?\s*(?:든|있는|뭐|뭔|무엇)|(?:내|제)\s*(?:오른|왼)?손\b.*(?:뭐|뭘)\s*들고\s*있|\bi(?:'ve| have) got something\b.*\bwhat\b|"
                     r"(?:내가|제가)\s*(?:hold|들고|잡고|쥐고)\s*(?:하고\s*)?있는\s*(?:거|게|것)|손에\s*(?:something|뭔가|무언가)|"
                     r"^\W*(?:\S+\W+){0,3}(?:이거|이건|이게)\s*(?:뭐|뭔|무엇|what)|"
                     r"(?:내가|제가|나|저)\s*(?:지금\s*)?(?:뭐|뭘|무엇을?)\s*(?:들고|잡고|쥐고|holding)|(?:내|제)\s*(?:오른|왼)?(?:손|hand)에\s*(?:뭐|뭔|무엇|든|있)|"
                     r"(?:내가|제가)\s*(?:든|들고\s*있는|쥐고\s*있는)\s*(?:거|게|것)|(?:뭐|뭘)\s*들고\s*있\S*\s*(?:내가|제가)|"
                     r"(?:내가|제가)\s*(?:지금\s*)?손에\s*(?:뭐|뭘)\s*(?:들고|쥐고|잡고)|"
                     r"(?<!루미 )(?<!네 )(?<!니 )(?<!너 )(?<![가-힣])(?:왼|오른)?손(?:에는|엔|에)\s*(?:뭐|뭘|무엇)\s*(?:들었|있|쥐|잡)|"
                     r"(?:내|제)\s*(?:왼|오른)?손\S*\s*(?:\S+\s+){0,2}(?:있|들)\S*\s*맞|"
                     r"\b(?:see|is there|there'?s) (?:a |an |the )?(?:\w+ )?\w+ in my (?:left |right )?hand\b", re.I)   # "제가 들고 있는 거 뭐예요?"
                                 # "뭐 들고 있어?" without "내가" asks about Lumi's own hand (lumi.status_question)
WHICH_HAND = re.compile(r"\b(?:which|what) hand(?![a-z])|무슨\s*손|오른손\S*\s*(?:아니면\s*)?왼손\S*\s*\?|\bleft or (?:my |the )?right\b|\bwhich of my hands\b|어느\s*(?:쪽\s*)?(?:손|hand)|손\s*어느\s*쪽|"
                        r"왼손\S*\s*(?:아니면\s*)?오른손\S*\s*\?|left\S*\s*right\S*\s*\?", re.I)   # held first, else raised
_UPPER = r"short|t-? ?shirts?|te[ea] ?shirts?|shirts?|tops?|jackets?|sweaters?|sweatshirts?|hoodies?|jumpers?|blouses?|coats?"
_LOWER = r"pants|trousers?|jeans?|genes|skirts?|shorts|slacks|leggings|bottoms"   # "genes", "jean": heard for jeans
_FEET = r"shoes?|sneakers?|trainers|boots?|sandals?|slippers?|socks?|feet|foot"
_UPPER_KO = r"티셔츠|셔츠|셔쯔|상의|윗옷|웃옷|윗도리|웃도리|겉옷|재킷|자켓|후드티|맨투맨|니트|스웨터|코트"
_LOWER_KO = r"청 ?바지|청바진|반바지|바지|하의|치마|스커트"
_FEET_KO = r"운동화|신발|구두"
_ITEM = rf"(?:{_UPPER}|{_LOWER}|{_FEET}|clothes|clothing|outfit)"
_ITEM_KO = rf"(?:{_UPPER_KO}|{_LOWER_KO}|{_FEET_KO}|옷)"
PARTS = (("upper", rf"\b(?:{_UPPER}|upper half)\b|{_UPPER_KO}"),
         ("lower", rf"\b(?:{_LOWER}|bottom half|lower half|legs?|down below)\b|{_LOWER_KO}|아래(?:쪽)?|밑|다리"),
         ("feet", rf"\b(?:{_FEET})\b|{_FEET_KO}|신었|신고 있|신은"))
SHIRT = re.compile(rf"(?:위|아래|밑)(?:에|쪽)?\s*(?:입은|신은)\s*(?:거|것|옷)\S*\s*(?:무슨\s*)?(?:색|컬러)|" rf"(?:{_ITEM_KO})\S*\s*(?:type|종류|타입)|" rf"\bcolou?rs?\b.{{0,30}}?\b(?:my|the|his|her|their|this)\s+(?:[\w']+\s+)?{_ITEM}\b|"
                   rf"\bcolou?r\s*(?:내|제)\s*(?:{_ITEM_KO})|"
                   rf"\bcolou?r(?:'s| is)? (?:the |my )?(?:bottom|top|lower|upper) half\b|"
                   rf"\b(?:{_UPPER}|{_LOWER})\b\s*(?:은|는|이|가)?\s*(?:(?:무슨|어떤|뭔)\s*)?(?:색|컬러|colou?r)|"
                   rf"\bput on (?:a |an )?(?:\w+ )?{_ITEM}\b.{{0,25}}\bcolou?r|{_ITEM}\W+what colou?r|\bmy\s+(?:\w+\s+)?{_ITEM}(?:'s)?\s+colou?r|"
                   rf"\b(?:is|are) my\s+(?:\w+\s+)?{_ITEM}\s+(?:" + "|".join(c for c in COLOURS if c.isascii()) + r")\b|"
                   rf"\bmy\s+(?:\w+\s+)?{_ITEM}\s+(?:is|are|looks?)\s+(?:" + "|".join(c for c in COLOURS if c.isascii()) + r")\b|"
                   r"\bwhat\b.{0,25}?\b(?:am i|i'?m|do i|did i)\s+(?:wear(?:ing)?|have on|got on)\b|"
                   r"\bwhat(?:'s| is| are)? (?:she|he|they|my friend|the (?:other|second) (?:person|guy|man|woman)|"
                   r"the (?:person|man|woman|guy|lady) next to me) wearing\b|"
                   r"\bwhat(?:'s| is| are)? (?:the )?(?:person|man|woman|guy|lady|kid|one) (?:standing |sitting )?(?:on|to|at) (?:your|the|my) (?:left|right) wearing\b|"
                   r"\bwhat colou?r (?:is|are) (?:she|he|they|my friend|the (?:other|second|person|man|woman|guy|lady)\b.{0,15}) wearing\b|"
                   r"\b(?:i (?:changed|switched)|changed (?:my )?(?:clothes|shirt|top))\b.{0,25}\bcolou?r|"
                   r"(?:위|아래|밑)(?:쪽)?\s*(?:은|는)?\s*무슨\s*색|"
                   r"\bwhat(?:'s| is| are)? on my (?:feet|foot)\b|\bdescribe my (?:clothes|clothing|outfit)\b|"
                   rf"{_ITEM_KO}\s*(?:은|는|이|가|의)?\s*(?:무슨|어떤|뭔|무엇|뭐)?\s*(?:색|컬러|colou?r)|무슨\s*색\s*{_ITEM_KO}|"
                   r"(?:뭐|뭘|무엇을?|무슨|어떤)\s*(?:\w+\s*)?(?:입었|입고|입은|신었|신고|신은)|"
                   r"(?:입었|벗었|바꿨|갈아입|change)\S*\W+.{0,12}(?:무슨\s*색|colou?r|컬러)|(?:나|저|내|제)\s*(?:무슨|어떤)\s*옷|"
                   rf"(?:내|제)\s*{_ITEM_KO}\S*\s*(?:{'|'.join(c for c in COLOURS if not c.isascii())})\S*\s*(?:맞|이지|지\?|죠)|\b(?:" + _UPPER + "|" + _LOWER + r")\s*(?:색|컬러)", re.I)   # 2026-10-21 live:
                                 # "What is the color of my t-shirt?", "What is it? Color my jeans." went to the LLM
SIDE_WHO = re.compile(r"\b(?:person|man|woman|guy|lady|kid|boy|girl|one|someone|people)\s+(?:standing\s+|sitting\s+)?(?:on|to|at)\s+"
                      r"(?P<o>your|the|my)\s+(?P<s>left|right)\b|\b(?:your|the)\s+(?P<s2>left|right)(?:-hand)?\s+(?:person|one)\b|"
                      r"(?P<k>왼|오른)쪽\s*(?:에\s*)?(?:있는|계신|서\s*있는|앉은|앉아\s*있는)?\s*(?:사람|분|person|애|아이|친구)", re.I)
                                 # "the person on your left", "왼쪽에 계신 분": the side as Lumi sees it ("on my left": theirs)
OTHER = re.compile(r"\b(?:friend|colleague|partner|she|he|his|her|their)\b|\bthe (?:other|second) (?:person|guy|man|woman|one)\b|"
                   r"\b(?:person|man|woman|guy|lady) (?:next to|beside|behind|with) me\b|친구|동료|옆\s*(?:에\s*)?(?:있는\s*)?(?:사람|분)|"
                   r"다른\s*(?:사람|분)|그\s*(?:사람|분)|저\s*(?:사람|분)|그분|저분", re.I)   # someone else than the person talking
FRIEND = re.compile(r"\b(?:do|can) you (?:still )?see (?:my (?:friend|colleague)|the other (?:person|guy|man|woman))\b|"
                    r"\bis (?:my (?:friend|colleague)|the other (?:person|guy|man|woman)) still (?:here|there|in view)\b|"
                    r"(?:친구|동료|그\s*사람|다른\s*(?:사람|분)|옆\s*사람)\S*\s*(?:아직도?\s*|still\s*)?(?:보여|보이|있어|있나|있습)", re.I)
DOING = re.compile(r"(?:내가|제가)\s*(?:지금\s*)?(?:뭐|뭘|무엇을?)\s*하는지|" r"\bwhat i(?:'m| am) doing\b|" r"\bwhat (?:is|are) (?:he|she|they) doing\b|" r"\b(?:on|to) (?:your|the) (?:left|right),? what (?:is|are) (?:he|she|they) doing\b|" r"(?:사람|분|person|친구)\S*\s*(?:은|는)?\s*(?:지금\s*)?(?:뭐|뭘|무엇을?)\s*(?:해|하|하고|하는)|" r"\bwhat am i doing\b|\bwhat(?:'m| am) i up to\b|(?:내가|제가|나|저)\s*(?:지금\s*)?(?:뭐|뭘|무엇을?)\s*하고\s*있|"
                   r"\bwhat(?:'s| is) (?:she|he|my friend|the (?:other )?(?:person|man|woman|guy|lady)(?: (?:on|to) (?:your|the|my) (?:left|right))?) doing\b|"
                   r"(?:사람|분|person|친구)\S*\s*(?:은|는)?\s*(?:지금\s*)?(?:뭐|뭘|무엇을?)\s*(?:하고|하세요|하시|해)", re.I)
POSTURE = re.compile(r"\bi'?m on my feet\b|\bam i on my feet\b|" r"(?:내가|제가)\s*(?:지금\s*)?(?:앉아|서)\s*(?:있|계)는지|" r"\b(?:am i|is (?:he|she|my friend))\s+(?:\w+\s+)?(?:sitting|standing|seated|"
                     r"crouching|squatting)\b|\b(?:sitting|standing|seated|crouching|squatting)\s+or\s+(?:sitting|standing|"
                     r"seated|crouching|squatting|not)\b|\bwhat(?:'s| is) my (?:posture|pose)\b|\bdo i (?:sit|stand)\b|"
                     r"(?:앉아|서|쪼그려\s*앉아)\s*(?:있|계)\S*\s*(?:아니면|or)?\s*(?:앉아|서)\s*(?:있|계)|"
                     r"(?:내가|제가|나|저)\s*(?:지금\s*)?(?:앉아|서|쪼그려\s*앉아)\s*(?:있|계)\S*\s*\?|"
                     r"(?:앉았|섰)\S*\s*(?:아니면\s*)?(?:서|앉아|섰|앉았)\S*|(?:내|제)\s*자세|"
                     r"(?:사람|분|person|친구)\S*\s*(?:지금\s*)?(?:앉아|서|쪼그려\s*앉아)\s*(?:있|계)|"
                     r"\bis (?:the )?(?:person|man|woman|guy|lady|one) (?:on|to) (?:your|the|my) (?:left|right) (?:sitting|standing|crouching)\b", re.I)   # 2026-10-23 live: "I am
                                 # standing or sitting." got "nice to meet you"
RAISED = re.compile(r"\b(?:is|are) my (?:hand|hands|arm|arms) still (?:raised|up)\b|" r"손\s*(?:을\s*)?(?:올린|든)\s*(?:거|게)\s*보여|" r"\bwhich (?:hand|arm) (?:do i have|have i got) (?:up|raised)\b|\b(?:is|are) my (?:hand|hands|arm|arms) (?:raised|up)\b|\bam i raising (?:my |a |an |any |one )?(?:hand|arm)s?\b|"
                    r"\bdid i raise my hand\b|\bwhich hand (?:did i raise|is (?:up|raised)|am i (?:raising|holding up|lifting))\b|"
                    r"\bwhich (?:hand|arm) is (?:up|raised)\b|\b(?:see|tell) (?:if|whether) (?:i'?m|i am) raising\b|"
                    r"\b(?:see|is) my (?:hand|arm)s? (?:up|raised)\b|\bhands? up or (?:not|down)\b|\bmy (?:hand|arm) is (?:up|raised)\b|"
                    r"\bi'?m raising (?:my |a )?(?:hand|arm)\b|\bi am raising\b|\b(?:is )?one of my hands (?:is )?up\b|"
                    r"(?:손|hand)\s*(?:을\s*)?(?:들었|들고\s*있|올라가|올렸|올리고\s*있|up\s*했|raise)|어떤\s*손이\s*(?:올라|들)", re.I)
POINTING = re.compile(r"\bwhat am i pointing (?:at|to)\b|\bwhere am i pointing\b|(?:내가|제가)?\s*(?:뭘|어디를?)\s*가리키", re.I)
_WHO = r"(?:am i|do i(?: have)?|have i got|i'?m|is (?:she|he|my friend|the other (?:person|guy|man|woman|one))|" \
       r"does (?:she|he|my friend) have)"
_ACCESSORY = r"glasses|eyeglasses|spectacles|sunglasses|shades|hats?|caps?|beanie|mask|face mask|bags?|backpack|handbag|" \
             r"purse|shoulder bag|watch|earrings|necklace|scarf|tie|beard|moustache|mustache"
WEARING = re.compile(r"\b(?:are )?(?:these|my) (sunglasses|glasses) visible\b|" r"\bis there an? (hat|cap|beanie|bag|mask|backpack) on me\b|" r"\b(?:do|does) (?:they|he|she) (?:carry|have|wear) (?:an? |any )?(?:\w+ )?(bag|backpack|hat|cap|glasses|sunglasses|mask)\b|" r"(안경|선글라스|모자|마스크|가방)\S*\s*(?:wearing|wear|착용)|" r"머리\s*위에\s*(?:뭐|뭔가|무엇)|" r"(?:내|제)\s*(가방|백팩|모자)\s*(?:무슨\s*)?(?:종류|type)|" rf"\b{_WHO} (?:wearing |got |have |carrying |holding )?(?:on )?(?:a |an |any |my )?(?:\w+ )?({_ACCESSORY})\b|"
                     rf"\bcolou?r\b.{{0,20}}\b(?:my|her|his) (?:\w+ )?(hats?|caps?|beanie|mask|bags?|backpack|glasses)\b|"
                     r"\bwhat(?:'s| is) on my (?:head|face)\b|\b(?:anything|something) on my head\b|\bwhat about my head\b|"
                     r"(?<![가-힣])머리에\s*(?:뭐|뭔가|무엇|아무것)|\b(?:see|notice) my (glasses|sunglasses|hat|cap|beanie|mask|bag|backpack)\b|"
                     r"(?:내|제|나|저)\s*(?:shoulder\s*)?(가방|백팩|배낭|모자|안경|선글라스|마스크)\S*\s*(?:색\S*\s*)?(?:보여|있어|있나|색)|\b(?:my|her|his) (hat|cap|bag|backpack|mask|glasses)\b.{0,12}\bcolou?r\b|"
                     r"(안경|선글라스|모자|마스크|시계|목걸이|귀걸이|넥타이|수염)\s*(?:을|를|은|는|이|가)?\s*"
                     r"(?:썼|쓰고|쓰셨|쓰신|꼈|끼고|끼셨|끼신|했|하고|하셨|있|찼|차고|기르|착용)|"
                     r"(가방|백팩|배낭)\s*(?:을|를|은|는|이|가)?\s*(?:메고|멨|매고|맸|메셨|메신|착용)|"   # not "가방 있어?" (a thing)
                     r"(모자|마스크|안경|(?:내|제)\s*가방|(?:내|제)\s*백팩)\s*(?:은|는|이|가)?\s*(?:무슨|어떤|뭔)?\s*(?:색|컬러|colou?r)",
                     re.I)                       # "am I wearing glasses?", "is she wearing a hat?", "가방 메고 있어?"
HAIR = re.compile(r"(?<![가-힣])머리\s*(?:가|는|이|도)?\s*(?:깁|짧습|길어|짧아)|" r"\b(?:my|her|his|their)\s+(?:\w+\s+)?hair\b|\bhair\s*(?:colou?r|style|length)\b|\bhairstyle\b|"
                  r"\b(?:am i|is (?:she|he)) bald\b|\bdo i have (?:\w+ )?hair\b|\bwhat (?:colou?r|kind of) hair\b|"
                  r"(?<![가-힣])머리\s*(?:카락)?\s*(?:색|컬러|colou?r|길이|스타일|모양|염색)|머리카락|헤어|대머리|"
                  r"(?<![가-힣])머리\s*(?:가|는|이|도)?\s*(?:길|짧|어때|어떤|무슨\s*색|긴\s*편|짧은\s*편)", re.I)
                                 # "what colour is my hair?", "is my hair long?", "내 머리 무슨 색이야?", "머리 길어?"
DESCRIBE_ME = re.compile(r"\bwhat do i look like\b|\bdescribe (?:me|my (?:look|looks|appearance)|her|him|my friend|"
                         r"the other (?:person|guy|man|woman))\b|\bhow (?:do|would) you describe (?:me|her|him)\b|"
                         r"\bwhat does (?:she|he|my friend) look like\b|\bhow do i look\b|"
                         r"(?:나|저|그\s*분|그\s*사람|옆\s*사람)\s*(?:은|는)?\s*(?:어떻게|어때)\s*(?:생겼|보여|보이)|"
                         r"(?:내|제)\s*(?:모습|외모|인상착의)|(?:나|저)를?\s*(?:좀\s*)?(?:묘사|설명)해|describe\s*해", re.I)
CLOSEST = re.compile(r"\bwho(?:'s| is)? (?:the )?(?:closest|nearest)\b|\bwho(?:'s| is) (?:standing )?closer\b|"
                     r"\bwhich (?:person|one of us) is (?:the )?(?:closest|nearest|closer)\b|\bwho(?:'s| is) standing (?:closest|nearest)\b|"
                     r"누가\s*(?:제일|가장|더)?\s*가까|(?:제일|가장)\s*가까운\s*(?:사람|분)\S*\s*(?:누구|어느)", re.I)
_TYPES_EN = rf"{_UPPER}|{_LOWER}|{_FEET}|dress(?:es)?|vests?|blazers?|cardigans?|polos?"
WEAR_ITEM = re.compile(rf"\b(?:i'?ve got|i have|i'?m wearing|i am wearing)\s+(?:an?\s+)?(?:\w+\s+)?(?:{_TYPES_EN})(?:\s+on)?,?\s+(?:right|correct|yes|yeah)\s*\?|" rf"^\W*(?:\w+\s+)?(?:{_TYPES_EN}),?\s+(?:i'?m|am i)\s+right\s*\?|" rf"\b(?:{_TYPES_EN})\b or (?:an? )?(?:{_TYPES_EN})\b.{{0,20}}\b(?:i'?ve got on|i(?:'m| am) wearing|on me)\b|" rf"\b(?:am i|is (?:she|he|my friend|the other (?:person|guy|man|woman)))\s+(?:wearing|in|dressed in)\s+"
                       rf"(?:a |an |any |my )?(?:[\w-]+\s+)?(?:{_TYPES_EN})\b|\bdo i have (?:a |an |any )?(?:\w+\s+)?(?:{_TYPES_EN}) on\b|"
                       rf"(?:{_UPPER_KO}|{_LOWER_KO}|{_FEET_KO}|원피스|조끼|블라우스|후드|부츠|샌들)\s*(?:을|를)?\s*"
                       r"(?:입었|입고|입으셨|입으신|신었|신고|신으셨)(?:\s*(?:있|계))?\S*\s*\??\W*$|"
                       rf"(?:{_UPPER_KO}|{_LOWER_KO}|원피스)\S*\s*(?:입었|입고|입으셨)\S*\s*(?:아니면\s*|or\s*)?"
                       rf"(?:{_UPPER_KO}|{_LOWER_KO}|원피스)\S*\s*(?:입었|입고|입으셨)", re.I)   # "청바지 입었어 치마 입었어?"
                                 # "am I wearing a jacket?", "is she in jeans?", "청바지 입었어?"
PATTERN_Q = re.compile(r"\bis this (?:\w+ )?(?:shirt|top|t-shirt|jacket|sweater|hoodie) (?:striped|checked|plain|printed|dotted|patterned)\b|" rf"\b(?:my|her|his)\s+(?:\w+\s+)?(?:{_UPPER}|{_LOWER}|clothes)\b.{{0,30}}\b(?:striped|stripes|stripy|checked|"
                       r"checkered|plaid|patterns?|patterned|plain|printed|dotted|polka)\b|"
                       rf"\b(?:pattern|print|stripes|logo)\b.{{0,15}}\b(?:on|of) (?:my|her|his)\b|"
                       rf"(?:{_UPPER_KO}|{_LOWER_KO}|옷)\S*\s*(?:에\s*)?(?:무슨\s*|어떤\s*)?(?:무늬|줄무늬|체크|프린트|그림|로고)", re.I)
                                 # "is my shirt striped?", "셔츠에 무늬 있어?": the VLM's look

FAR_ME = re.compile(r"\bhow far (?:from you )?(?:am i|are you from me|away am i)\b|(?:제가|내가)\s*(?:서\s*)?있는\s*(?:곳|데|자리)\S*\s*(?:몇\s*미터|얼마나)|(?:나|저)(?:랑|와|하고|는|한테서)?\s*얼마나|"
                    r"\bam i close\b|\bdistance between us\b|\bhow many (?:meters|metres) (?:away )?am i\b|"
                    r"(?:나|저)(?:랑|와|하고)\s*(?:의\s*)?(?:거리|distance)|우리\s*사이|"
                    r"(?:나|저|제가|내가)(?:랑|와|하고|는)?\s*(?:몇\s*(?:미터|meter)|.{0,8}떨어져\s*있)", re.I)
IT = re.compile(r"\b(?:it|that|this|they|them)\b|그거|그게|그건|저거|저게|저건|걔|거기", re.I)
ORDER = re.compile(r"\b(?:take|bring|pick|grab|get|put|place|give|fetch|carry|go|come|move|turn|look)\b|(?<!\bmy )(?<!\byour )\bhands?\b(?! (?:raised|up|down)\b)(?=\s+(?:me|it|this|that|the|her|him|them|over)\b)|"
                   r"가져|집어|잡아|놓아|놔|주고|(?<!말해 )(?<!알려 )(?<!말해)(?<!알려)줘|갖다(?!\s*놨)|가 ?줘|와 ?줘|돌아", re.I)
DONE = re.compile(r"\bi(?:'ve| have)? (?:just )?(?:put|brought|moved|took|got)\b", re.I)   # "I just put a cup there": done
HEAD = re.compile(r"\blook\b|\beyes on me\b|\bhead\b|(?:왼쪽|오른쪽|정면|이쪽|저쪽|위|아래|나|저|side|쪽)\s*(?:좀\s*)?(?:봐|look)|"
                  r"고개|\blook\s*해", re.I)              # a head turn between keeps the question: "look up", "and now?"
PRAISE = re.compile(r"^\W*(?:\w+\W+){0,3}?(?:nice|neat|cool|wow|great|amazing|impressive|smart|awesome|good eyes|"
                    r"잘\s*보|똑똑|신기|대박|멋지|멋있|좋네)[^?]*$", re.I)   # "nice, you have good eyes": the thread goes on
FAR_BARE = re.compile(r"^\W*(?:(?:and|so|then)\W+)?how (?:far|near|close)(?: away)?\W*$|"
                      r"^\W*(?:그럼\s*)?(?:얼마나\s*(?:멀|떨어|가까)\S*|거리는요?)\W*$", re.I)   # "how far?" right after a see answer
FOLLOW_EN = re.compile(r"^\W*(?:(?:and|so|then|ok(?:ay)?|well|but|no|sorry|oh|also|actually|wait|uh+|um+|er)\W+)*"
                       r"(?:i\s+mean[t]?\W+|(?:what|how)\s+about\s+|not (?:the |my |that |this )?\w+(?: one)?\W+)?"
                       r"(?:(?:my|the|a|an|that|this|those|these)\s+)?(?P<x>.+?)[\s?.!,]*$", re.I)
FOLLOW_KO = re.compile(r"^\W*(?:(?:그럼|그러면|그리고|근데|아니요|아니|아뇨)[\s,]*)*(?:\S+(?:\s*거)?\s*말고[\s,]*)?"
                       r"(?:(?:내|제|그|저|이)\s+)?(?P<x>.+?)\s*(?:(?:은|는|도)요?|말(?:이야|이에요|이요|요|고요)|요)?[\s?.!]*$")
BYE = re.compile(r"\b(?:bye|goodbye|see you|see ya|later)\b|안녕|잘 ?(?:가|있어)", re.I)   # ends the thread
ABOUT_LUMI = re.compile(r"(?:루미|너|니가|네가|당신)(?:는|은|가|도|의)\s|(?<![가-힣])(?:너|니가|네가|당신)\s|루미\s+머리|^\W*넌|"
                        r"\bare you\b|\byou(?:'re| are) wearing\b", re.I)   # "루미 바지 무슨 색이야?": a call (Lumi wears none)
VOCATIVE = re.compile(r"(?:루미|로봇|\blumi|\brobot|\bloomy|\brumi)\s*(?:(?:쌤|선생님|선배님?|프로|선수|님|아저씨|양반|친구|군|양|짱|사장님|"
                      r"착하지|야|아)(?![가-힣])|씨)|"
                      r"(?:루미|로봇)\s*[,!]|(?:^|(?<=[\s,]))(?:친구|동료)(?:야|아|님)?\s*[,!]", re.I)
                                 # "루미 씨, ...", "로봇 친구", "동료, 제 바지 ...": a call, not whom it is about
FIRST_PERSON = re.compile(r"(?<![가-힣])(?:제가|내가|저는|나는|제|내|나|저(?!\s*(?:사람|분|쪽|기|거)))(?![가-힣])|"
                          r"\b(?:i|me|my|mine|i'?m)\b", re.I)


def _about_lumi(t):
    """"루미는 무슨 옷 입었어?", "루미 머리 무슨 색이야?": about Lumi; "루미 씨, 제 바지 무슨 색이에요?": about the speaker."""
    u = VOCATIVE.sub(" ", t)
    return bool(ABOUT_LUMI.search(u)) and not FIRST_PERSON.search(u)
ONE = re.compile(r"(?P<col>" + "|".join(COLOURS) + r")\w*\s*(?:ones?|거|것|걸)?", re.I)   # "the blue one", "파란 거"
UP_ASKED = re.compile(r"\bup\b|\braised?\b|\braising\b|올라|올렸|손\s*(?:을\s*)?들(?:고|었)", re.I)
HELD_ASKED = re.compile(r"\bhold|\bhave it\b|\bin my\b|\bit\b|\b(?:that|this) in\b|들고|쥐고|잡고|있(?:어|습|나|니)|들었게", re.I)
SEE_KINDS = ("see", "there", "still", "see_ko", "see_more", "where", "far", "it")
TAIL = re.compile(r"(?:[\s,]+(?:too|then|also|exactly|again|please|dear|sir|ma'?am|lumi|robot|what colou?rs?(?: (?:are|is) (?:they|it))?))+\W*$|"
                  r"(?:도|은|는)?\s*(?:정확히\s*)?(?:무슨\s*)?(?:색깔?|컬러|colou?r)\s*(?:은|는|이야|이에요|이에요)?\W*$|"
                  r"도\s*(?:보여|보이|있어|있나)\S*\W*$|(?:은|는)?\s*(?:어때|어떻|어떤가)\S*\W*$",
                  re.I)   # words after a follow-up's noun that ask nothing new
WHERE_ON_ME = (("lower", r"(?:down )?below|(?:the )?bottom(?: half)?|(?:on )?(?:the )?lower (?:half|part)|밑(?:에|쪽)?\w?|아래(?:쪽)?(?:에)?\w?"),
               ("upper", r"(?:up )?above|(?:the )?top half|위(?:쪽)?(?:에)?\w?"),
               ("feet", r"on my feet|발(?:에)?\w?"))     # "how about below?" after a clothes answer: the trousers
IT_WHERE = re.compile(r"^\W*(?:(?:and|so|then|ok(?:ay)?)\W+)*(?:where(?: is (?:it|that))?(?: exactly)?|which side|"
                      r"(?:is it )?on (?:the|your) (?:left|right)(?: or (?:the |your )?(?:left|right))?)\W*$|어디(?:에)?\s*있|어느\s*쪽",
                      re.I)
IT_COLOUR = re.compile(r"\bwhat colou?r is (?:it|that)\b|^\W*(?:그거|그건|저거)?\s*무슨\s*색", re.I)
IT_SIZE = re.compile(r"\b(?:is it|is that|how) (?:big|large|small|tall|high|wide)\b|^\W*(?:그거|저거)?\s*(?:커|작아|크기)", re.I)
IT_COUNT = re.compile(r"^\W*(?:how many(?: \w+)?|any (?:others|more)|몇\s*개\S*)\W*$", re.I)
_LEAD = r"^\W*(?:(?:and|so|but|okay|ok|well|then|hmm+|uh+|um+|oh|no|wait)\W+)*"
AGAIN = re.compile(r"\band now\s*\??\s*$|" + _LEAD + r"(?:(?:what|how) about |(?:where(?:'s| is)? (?:it|that|they)|which hand(?: is it)?|"
                   r"what(?:'s| is)? (?:it|that)|is it|right|just|look|check) )?(?:now|know)\b(?:,? lumi)?"
                   r"(?:\W+anything (?:new|else|different))?\W*$|\bone more time\b|"   # "and now?" ("and know?")
                   r"\b(?:look|check|see)\b.{0,15}\b(?:again|one more time)\b|\btake another look\b|"
                   r"\blook (?:closer|carefully|properly)\b|^\W*again\W*$|"
                   r"\bare you (?:sure|shore|certain|positive)\b|^\W*(?:\w+\W+){0,2}(?:really|seriously|for real)\W*$|"
                   r"^\W*(?:you(?:'re)?\s+)?(?:sure|positive|certain)\S{0,2}\s*\?|"
                   r"\bis (?:it|that|this) (?:really|right|true|correct|so)\b|\breally\b.{0,25}\?|"
                   r"^\W*(?:(?:그럼|근데|아니)\s*)?(?:(?:진짜|정말)\S{0,2}\s*)?(?:진짜|정말|확실|맞아|맞나|맞습니까|틀림없)\S{0,4}\s*\?|"
                   r"^\W*(?:진짜|정말)\S{0,3}\W*$|지금은|이제는|\bnow\s*(?:은|는)|^\W*(?:그럼\s*)?(?:지금|이제)\s*\??\W*$|"
                   r"(?:지금|이제)\S{0,2}\s*(?:어때|어떻|어떤가)|(?:지금|이제|now)\S{0,2}\s+(?:손에\s*)?(?:뭐|뭘|무엇을?)\s*(?:들고|쥐고|있)|"
                   r"\bdouble[- ]?check\b|^\W*(?:(?:and|okay|ok|so)\W+)*(?:what about |how about )?this time\W*$|"
                   r"\bwhat now\b|^\W*now what\b|\bsure about (?:that|it)\b|\bis that (?:right|so|true|correct)\b|"
                   r"이번엔|이번에는|^\W*그래요?\s*\?|\bagain\s*(?:봐|보)|sure\s*해|really\s*맞|"
                   r"다시\s*(?:한\s*번\s*|한번\s*)?(?:봐|보|확인|check|체크|look)|자세히\s*(?:다시\s*)?봐|잘\s*봐|또\s*봐", re.I)
                                 # a new look at the same question: "are you sure?", "다시 한번 확인해 줄래요?"
LOOK_SAID = re.compile(r"\blook\b(?=\s*(?:[,.!]|$))", re.I)   # "Lumi, look, what am I holding?": not a head turn
PUT_ON = re.compile(r"\bi(?:'ve| have)? (?:just )?(?:put on|took off|taken off)\b", re.I)   # clothes, not an order
LIKED = re.compile(r"\bfavou?rite\b|\b(?:like|love)\b|좋아하", re.I)   # "is white your favourite colour?": not a check
NOT_A_HAND = re.compile(r"\b(?:that'?s|that is|you'?re|you are|all|is that|is it) right\b|\bright (?:now|away|here|there)\b|"
                        r",\s*right\W*$",   # "you see the phone in my hand, right?": a tag, not the right hand
                        re.I)
HAND_SAID = re.compile(r"(?P<n>\bnot (?:in )?(?:the |my |your )?|\bisn'?t (?:in )?(?:the |my |your )?)?\b(?P<s>left|right)\b"
                       r"(?=\s*(?:hand|one|side)(?![a-z])|\W*$)|(?P<k>왼|오른)\s*(?:손|쪽|편)\S{0,3}(?P<kn>\s*아니)?", re.I)
HAND_ASKED = re.compile(r"\b(?:what|how) about\b|^\W*and\b|\bwhat\b.*\b(?:in|on)\b|\?\s*$|"
                        r"(?:손|쪽|거)\S{0,2}(?:은|는|엔)\s*\??\W*$|뭐|뭘|무엇|뭔", re.I)
                                 # "what about the left hand?", "왼손은?": a question about that hand, not "it's my left hand"
OTHER_HAND = re.compile(r"\bother (?:hand|one)\b|\bthis (?:one|hand)\b|다른\s*(?:손|쪽)|반대\S{0,2}\s*손|이쪽\s*손|^\W*이\s*손|"
                        r"^\W*(?:그럼\s*)?이건\s*\?", re.I)   # "and the other one?", "this one?" after a hand answer
COLOUR_SAID = re.compile(r"(?P<n>\bnot (?:\w+ ){0,2}|n't (?:\w+ ){0,2})?\b(?P<c>" + "|".join(c for c in COLOURS if c.isascii()) +
                         r")(?![a-z])|(?P<k>" + "|".join(c for c in COLOURS if not c.isascii()) + r")\w*(?P<kn>\s*아니)?", re.I)
_last = {"thing": None,          # the thing seen last: "how far is it?"
         "name": None,           # the kind of thing asked about last: "and the blue one?"
         "kind": None,           # the kind of the question just answered: "what about my jeans?" after the shirt
         "asked": None,          # (kind, words) of that question: "really?", "and now?" ask it again
         "hand": None,           # the hand the last "what's in my hand" answer was about: "and the other one?"
         "parts": [],            # [(part, word, colour)] said in the clothes answer: "it's white" is about these
         "held": None,           # {name, colour, at} of the held thing said last: its colour stays steady
         "unsure": 0.0,          # time.time() Lumi last asked "could you tell me what it is?"
         "at": 0.0}              # time.time() of the last seeing answer


def _follow_up(t, last):
    """"what about my jeans?", "and the apple?", "신발은?" right after a seeing answer of kind `last`:
    (kind, the words to answer), else (None, t). Only a clothes word or a thing name may follow the lead-in."""
    t = TAIL.sub("", t) or t                               # "jeans too?", "바지는 정확히 무슨 색?", "신발도 보여?"
    for rx in (FOLLOW_EN, FOLLOW_KO):
        m = rx.match(t)
        x = m.group("x") if m else ""
        if last:                                           # "바지는?" after any seeing answer
            for part, said in WHERE_ON_ME:                 # "and below?", "그럼 아래는?"
                if re.fullmatch(said, x, re.I):
                    return "shirt", NOUN[part][rx is FOLLOW_KO]
            if re.fullmatch(rf"(?:\w+\s+)?{_ITEM}|{_ITEM_KO}", x, re.I):
                return "shirt", x
            if WEARING.search(f"am i wearing {x}") or WEARING.search(f"{x} 썼"):
                return "wearing", f"am I wearing {x}?" if rx is FOLLOW_EN else f"{x} 썼어?"   # "and my glasses?"
        if re.fullmatch(r"coffee|커피", x, re.I):
            return None, t                                 # "what about coffee?" after a cup: a drink, not the cup
        th = last in SEE_KINDS and (re.fullmatch(_THING_EN, x, re.I) or re.fullmatch(_THING_KO, x))
        one = last in SEE_KINDS and _last["name"] and ONE.fullmatch(x)
        if th and _name(th.group("obj")) or one:
            name, colour = _thing(th) if th else (_last["name"], COLOURS[one.group("col").lower()])
            w = f"{colour} {name}" if colour else name
            return ("far", f"how far is the {w}?") if last == "far" else ("see", f"do you see a {w}?")
    return None, t


BAGS = ("handbag", "backpack", "suitcase")   # "가방", "bag": any of these


def _sees(name, colour, frames):
    """scene.sees, with "bag" standing for every kind of bag the detector names."""
    for n in (BAGS if name == "handbag" else (name,)):
        hits = scene.sees(n, colour, frames)
        if hits:
            return hits
    return []


def _name(word):
    w = word.lower()
    return SYNONYMS.get(w) or KO_WORDS.get(w) or (w if w in objects.COCO else None)


def _thing(m):
    return _name(m.group("obj")), COLOURS.get((m.group("col") or "").lower())


def _j(word, after_consonant, after_vowel):
    """Korean particle after a word: 사과 + 가, 컵 + 이."""
    c = word[-1:]
    final = "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 != 0
    return word + (after_consonant if final else after_vowel)


def _ko_name(name):
    return KO.get(name, name)


def _n(n):
    return ("no", "one", "two", "three", "four", "five", "six")[n] if n <= 6 else str(n)


def _a(name, colour=None):
    w = f"{colour} {name}" if colour else name
    return ("an " if w[0] in "aeiou" else "a ") + w


def _m(d, lang):
    if d is None:
        return ""
    return (f" about {_metres(d)} away" if d >= 1 else f" about {round(d * 100, -1):.0f} centimetres away") \
        if lang == "en" else (f" {_d(d)}미터쯤 떨어진" if d >= 1 else f" {round(d * 100, -1):.0f}센티미터쯤 떨어진")


def _d(d):
    """2.0 -> "2", 1.46 -> "1.5": metres as said aloud."""
    return f"{d:.1f}".removesuffix(".0")


def _metres(d):
    return f"{_d(d)} metre" + ("" if _d(d) == "1" else "s")


def _where_ko(w):
    return {"on my left": "왼쪽", "on my right": "오른쪽", "in front of me": "앞"}.get(w, "")


def _say(en, ko, lang):
    return en if lang == "en" else ko


EMPTY_HANDS = ("I don't see anything in your hands{}.", "{}손에 든 게 없어 보여요.")
NO_CAMERA = ("My cameras aren't giving me a picture right now, so I can't tell.", "지금은 카메라 화면이 없어서 잘 모르겠어요.")
LOOKS = 3                        # fresh looks at most at the hands before the close look (each 0.1-1 s)
SURE = 0.35                      # a held thing seen once with this detector score is trusted (person.OBJECT_SCORE);
                                 # a weaker one when two looks agree
STEADY_S = 30.0                  # s; the same kind of thing asked about again this soon keeps its colour unless two
                                 # new looks agree on another (a yellow cup read white, then yellow, 2026-10-23)
HINT_S = 60.0                    # s; after "could you tell me what it is?" this long, the next words are the hint
SAVE_DIR = ROOT / "logs" / "seeing"   # the frames of each live "what am I holding" (to measure misses later)
SAVE_KEEP = 40                   # ... the newest this many questions kept
HINT = re.compile(r"^\W*(?:(?:no|nope|well|ok(?:ay)?|so|oh|it'?s|it is|this is|that'?s|i'?m holding|i have|they'?re)\W+)+"
                  r"(?:(?:a|an|my|the|some|just)\s+)?(?P<x>[a-z][a-z -]{1,30}?)\W*$|"
                  r"^\W*(?:이거|이건|그거|그건|제가\s*든\s*(?:건|거)|아니\S*)?\s*(?P<k>[가-힣A-Za-z ]{1,15}?)\s*"
                  r"(?:이야|야|예요|이에요|에요|입니다|이요|요)\W*$", re.I)   # "it's my wallet", "이거 지갑이야"
UNSURE_SAID = re.compile(r"UNSURE|can'?t tell|not sure|모르겠|알 수 없|확실하지", re.I)   # the close look gave up
TURNED = re.compile(r"\bturn(?:ed)?\b|\bhow about (?:now|this)\b|\bcan you see (?:it|now)\b|돌렸|이제\s*보여|보여\s*\?", re.I)


def _seen_answer(name, colour, frames, lang):
    _last["name"] = name
    if name == "person":
        n = len(scene.people(frames))
        return _say(f"Yes, I see {_n(n)} {'person' if n == 1 else 'people'}." if n else "No, I don't see anyone right now.",
                    f"네, 사람 {n}명이 보여요." if n else "아니요, 지금은 아무도 안 보여요.", lang)
    hits = _sees(name, colour, frames)
    if colour and hits and not any(h["colour"] == colour for h in hits):
        hits = []                                          # a grey chair asked as white: said as seen, not agreed
    if hits:
        t = hits[0]
        _last["thing"] = t
        more = len(hits) - 1
        en = f"Yes, I see {_a(name, colour)}{_m(t['distance_m'], 'en')} {t['where']}."
        ko = f"네, {_where_ko(t['where'])}{_m(t['distance_m'], 'ko')} 곳에 {COLOUR_KO.get(colour, '') + ' ' if colour else ''}" \
             f"{_j(_ko_name(name), '이', '가')} 보여요."
        if more:
            en += f" I see {more} more."
            ko += f" {more}개 더 보여요."
        return _say(en, ko, lang)
    other = _sees(name, None, frames) if colour else []
    if other:
        t = other[0]
        _last["thing"] = t
        c = t["colour"]
        return _say(f"I don't see {_a(name, colour)}, but I see {_a(name, c)}{_m(t['distance_m'], 'en')} {t['where']}.",
                    f"{COLOUR_KO.get(colour, colour)} {_j(_ko_name(name), '은', '는')} 안 보이지만, {COLOUR_KO.get(c, '')} "
                    f"{_j(_ko_name(name), '이', '가')} {_where_ko(t['where'])}에 보여요.", lang)
    _last["thing"] = None
    return _say(f"No, I don't see {_a(name, colour)} right now.",
                f"아니요, 지금은 {COLOUR_KO.get(colour, '') + ' ' if colour else ''}{_j(_ko_name(name), '이', '가')} 안 보여요.", lang)


def _listing(frames, lang, small_only=False):
    seen = [t for t in scene.things(frames) if (t["score"] or 0) >= DESCRIBE_SCORE and not (small_only and t["name"] in BIG)]
    names = []
    for t in seen:
        if t["name"] not in names:
            names.append(t["name"])
    names = names[:NEAR_SAY]
    if not names:
        return None
    if lang == "en":
        words = [_a(n) for n in names]
        return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
    return ", ".join(_ko_name(n) for n in names)


def describe(frames, lang):
    n = len(scene.people(frames))
    things = _listing(frames, lang)
    if lang == "en":
        parts = ([f"{_n(n)} {'person' if n == 1 else 'people'}"] if n else []) + ([things] if things else [])
        return ("I see " + " and ".join(parts) + ".") if parts else "I don't see anything I can name right now."
    parts = ([f"사람 {n}명"] if n else []) + ([things] if things else [])
    return (_j(", ".join(parts), "이", "가") + " 보여요.") if parts else "지금은 제가 알아볼 수 있는 게 안 보여요."


def _it_answer(t, frames, lang):
    """Where, what colour, how big, how many: about the thing seen just before (_last["thing"])."""
    th = _last["thing"]
    name = th["name"]
    if IT_COUNT.search(t):
        n = len(_sees(name, None, frames))
        return _say(f"I see {_n(n)} {name}{'' if n == 1 else 's'}.", f"{_ko_name(name)} {n}개가 보여요.", lang)
    if IT_COLOUR.search(t):
        c = th["colour"]
        return _say(f"The {name} looks {c}." if c else f"I can't tell the colour of the {name}.",
                    f"{_j(_ko_name(name), '은', '는')} {COLOUR_KO.get(c, c)}으로 보여요." if c else "색은 잘 모르겠어요.", lang)
    if IT_SIZE.search(t):
        return _say(f"I can't measure its size, but the {name} is{_m(th['distance_m'], 'en')} {th['where']}.",
                    f"크기는 잴 수 없지만, {_j(_ko_name(name), '은', '는')} {_where_ko(th['where'])}에 있어요.", lang)
    return _say(f"The {name} is {th['where']}{',' + _m(th['distance_m'], 'en') if th['distance_m'] else ''}.",
                f"{_j(_ko_name(name), '은', '는')} {_where_ko(th['where'])}{_m(th['distance_m'], 'ko')} 곳에 있어요."
                if th['distance_m'] else f"{_j(_ko_name(name), '은', '는')} {_where_ko(th['where'])}에 있어요.", lang)


KO_SIDE = {"left": "왼", "right": "오른"}


def _from(p, side=None):
    """The thing in that hand (None: right first, then left) of a person_in_front, with "hand", or None."""
    for s in ((side,) if side else ("right", "left")):
        h = p["hands"].get(s)
        if h and h.get("object"):
            return {**h["object"], "hand": s}
    return None


def _vote(got):
    """The thing several looks agree on: {name, colour, hand, score, sure, doubt} or None. sure: one look with a
    detector score >= SURE or two looks; the colour is the one most looks gave, the colour said before for the same
    kind of thing (STEADY_S) unless two looks now agree on another; doubt: the newest look disagrees with that."""
    if not got:
        return None
    names = Counter(x["name"] for x in got)
    best = max(names, key=lambda n: (names[n], max(x.get("score", 1.0) for x in got if x["name"] == n)))
    mine = [x for x in got if x["name"] == best]
    cols = Counter(x["colour"] for x in mine if x["colour"])
    colour = max(cols, key=lambda c: (cols[c], max(i for i, x in enumerate(mine) if x["colour"] == c)), default=None)
    mem = _last["held"]
    doubt = False
    if mem and mem["name"] == best and time.time() - mem["at"] < STEADY_S and mem["colour"] and colour != mem["colour"] \
            and cols[colour] < 2:
        colour, doubt = mem["colour"], True               # one look against the colour said seconds ago: look again
    score = max(x.get("score", 1.0) for x in mine)
    return {**mine[-1], "colour": colour, "score": score, "sure": score >= SURE or len(mine) >= 2, "doubt": doubt}


def _held_look(frames, p, side, more):
    """Up to LOOKS fresh looks (more(): new frames, None in tests with saved frames) until the looks agree on a thing.
    (sure thing or None, weak guess or None, the last frames, the person in them)."""
    got = []
    for i in range(LOOKS):
        if i:
            nxt = more() if more else None
            q = scene.person_in_front(nxt) if nxt else None
            if q is None:
                break
            frames, p = nxt, q
        o = _from(p, side)
        if o:
            got.append(o)
        pick = _vote(got)
        if pick and pick["sure"] and not pick["doubt"]:
            break
    pick = _vote(got)
    if pick and pick["sure"]:
        return pick, None, frames, p
    return None, pick, frames, p


def _save(frames):
    """The frames of a live question to logs/seeing/ (the newest SAVE_KEEP kept), in the background."""
    def run():
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            scene.save(str(SAVE_DIR / time.strftime("%Y%m%d_%H%M%S")), frames)
            old = sorted(SAVE_DIR.glob("*.json"))[:-2 * SAVE_KEEP]
            for j in old:
                for x in SAVE_DIR.glob(j.stem + ".*"):
                    x.unlink()
        except Exception as e:
            print(f"seeing: frames not saved ({e})", flush=True)
    threading.Thread(target=run, daemon=True).start()


def _held_answer(frames, lang, side=None, more=None, slow_line=None, hint=None):
    """What the person holds; side ("left" / "right", the person's own): only what is in that hand. Tries hard
    before giving up: fresh looks until two agree (_held_look), then gemma4 on the picture of the hand with what the
    cameras measured; still unsure: what it seems to be and a request for a hint (hint: the words they gave)."""
    p = scene.person_in_front(frames)
    if p is None:
        return _say("I can't see you well enough to tell. Could you step in front of me?",
                    "잘 안 보여서 모르겠어요. 제 앞으로 와 주시겠어요?", lang)
    if side:
        _last["hand"] = side                               # "and the other one?" next
    o, weak, frames, p = _held_look(frames, p, side, more)
    if more and all("color" in f for f in frames):         # live frames (tests fake them)
        _save(frames)
    if o:
        return _held_said(o, lang, side, hint)
    sides = (side,) if side else ("left", "right")
    seen = {s: p["hands"][s] for s in sides if p["hands"].get(s)}
    blobs = {s: h["something"]["colour"] for s, h in seen.items() if (h.get("something") or {}).get("colour")}
    k = KO_SIDE.get(side, "")
    if not seen and not weak:
        return _say(f"I can't see your {side + ' hand' if side else 'hands'} well enough to tell.",
                    f"{k}손이 잘 안 보여서 모르겠어요.", lang)
    if not weak and not blobs and all(h.get("distance_m") is not None for h in seen.values()) and not hint:
        if side and side in p["raised"]:                   # depth at the wrist and nothing but the hand there
            return _say(f"Your {side} hand is up and I don't see anything in it.",
                        f"{k}손을 들고 계신데, 그 손에는 든 게 안 보여요.", lang)
        _last["held"] = None
        return _say(f"I don't see anything in your {side} hand." if side else EMPTY_HANDS[0].format(""),
                    f"{k}손에는 든 게 없어 보여요." if side else EMPTY_HANDS[1].format(""), lang)
    lk = _looks(p, frames, lang, None, more, wait=False)    # the person's looks of seconds ago name the thing
    got = lk and not hint and next(((s, lk[f"{s}_hand"]) for s in sides if lk.get(f"{s}_hand")), None)
    if got:
        s, w = got
        return _say(f"It looks like {_a(w)} in your {s} hand.", f"{KO_SIDE[s]}손에 {_j(_ko_thing(w), '이', '가')} 있는 것 같아요.", lang)
    evidence = "; ".join(
        ([f"the object detector's best guess is a {weak['name']} (score {weak['score']:.2f}, unsure)"] if weak else
         ["the object detector knows no class for it"]) +
        [f"in their {s} hand something {c}" for s, c in blobs.items()] +
        ([f"about {weak['width_mm'] // 10:.0f} cm wide"] if weak and weak.get("width_mm") else []) +
        ([f"they say it is {_a(hint)}"] if hint else []))
    if slow_line:
        slow_line(_say("Let me look closely.", "자세히 볼게요.", lang))
    said = scene.ask_vlm_hand(evidence, lang, frames, side)
    print(f"seeing: close look ({evidence}) -> {said}", flush=True)
    if said and not UNSURE_SAID.search(said):
        _last["unsure"], _last["held"] = 0.0, None
        return said
    if hint:
        _last["unsure"] = 0.0
        return _say(f"I still can't make it out well, so I'll take your word: it's {_a(hint)}.",
                    f"아직 잘 안 보이지만, {hint}(이)라고 믿을게요.", lang)
    _last["unsure"] = time.time()
    s, c = next(iter(blobs.items()), ((weak or {}).get("hand") or side, None))
    where = f" in your {s} hand" if s else ""
    if weak:
        en = f"It might be {_a(weak['name'], weak['colour'])}{where}, but I'm not sure."
        ko = f"{KO_SIDE.get(s, '')}손에 든 게 {_ko_name(weak['name'])}인 것 같은데 확실하지 않아요."
    elif c:
        en, ko = f"I see something {c}{where}, but I can't tell what it is.", \
            f"{KO_SIDE.get(s, '')}손에 {COLOUR_KO.get(c, c)} 뭔가가 보이는데, 뭔지는 모르겠어요."
    else:
        en, ko = f"I can't make out what's{where or ' in your hand'}.", "손에 든 게 뭔지 잘 안 보여요."
    return _say(en + " Could you turn it toward me, or tell me what it is?",
                ko + " 저한테 보이게 돌려 주시거나, 뭔지 말씀해 주시겠어요?", lang)


def _held_said(o, lang, side=None, hint=None):
    """The sentence for a thing seen in a hand (the hand asked about first), remembered so its colour stays steady."""
    _last["hand"], _last["unsure"] = o["hand"], 0.0
    _last["held"] = {"name": o["name"], "colour": o["colour"], "at": time.time()}
    h, k = o["hand"], KO_SIDE[o["hand"]]
    col_ko = COLOUR_KO[o["colour"]] + " " if o["colour"] in COLOUR_KO else ""
    named = hint and (_said_thing(hint) or _name(hint.split()[-1]))
    if named and named != o["name"]:
        return _say(f"To my camera it looks like {_a(o['name'], o['colour'])}, not {_a(named)}, but I may be wrong.",
                    f"제 카메라에는 {_j(_ko_name(named), '이', '가')} 아니라 {col_ko}{_ko_name(o['name'])}(으)로 보여요. "
                    f"틀릴 수도 있어요.", lang)
    if hint:
        return _say(f"Yes, now I see it: {_a(o['name'], o['colour'])} in your {h} hand.",
                    f"네, 이제 보여요. {k}손에 {col_ko}{_j(_ko_name(o['name']), '이', '가')} 있어요.", lang)
    if side:
        return _say(f"In your {side} hand I see {_a(o['name'], o['colour'])}.",
                    f"{k}손에 {col_ko}{_j(_ko_name(o['name']), '이', '가')} 보여요.", lang)
    return _say(f"You're holding {_a(o['name'], o['colour'])} in your {h} hand.",
                f"{k}손에 {col_ko}{_j(_ko_name(o['name']), '을', '를')} 들고 계세요.", lang)


def _steady(o):
    """A thing in a hand (object_in_hand) with the colour said for it seconds ago (STEADY_S), for other answers."""
    mem = _last["held"]
    if o and mem and mem["name"] == o["name"] and time.time() - mem["at"] < STEADY_S:
        return {**o, "colour": mem["colour"]}
    return o


def _hint(t):
    """The thing named after "could you tell me what it is?": "it's my wallet", "이거 지갑이야" -> "my wallet" / "지갑",
    else None."""
    m = "?" not in t and HINT.match(t.strip())
    x = m and (m.group("x") or m.group("k") or "").strip()
    if not x or re.fullmatch(r"(?:it|this|that|right|left|okay|ok|sure|yes|no|here|now|hand|네|아니|맞아|여기|이거|그거)",
                             x, re.I) or _side(t):
        return None
    return x


def _asked_hand(t):
    """The hand a question is about: "what's in my left hand?", "왼손은?", "and the other one?" (not the one just told)."""
    return _side(t) or (OTHER_HAND.search(t) and {"left": "right", "right": "left"}.get(_last["hand"])) or None


def _empty_hands(lang, now=False):
    """Nothing the detector knows in the hands: said plainly, with what it can't see (a watch has no class)."""
    return _say(EMPTY_HANDS[0].format(" now" if now else ""), EMPTY_HANDS[1].format("지금은 " if now else ""), lang)


NOUN = {"upper": ("top", "상의"), "lower": ("trousers", "바지"), "feet": ("shoes", "신발")}
GENERIC = re.compile(r"tops?|bottoms?|bottom half|lower half|upper half|legs?|down below|clothes|outfit|상의|하의|아래(?:쪽)?|밑|"
                     r"다리|윗옷|웃옷|옷", re.I)          # words for a piece that name no kind


def _clothes_answer(p, text, lang, looks=None):
    """The colour of each piece asked about (all three for "what am I wearing?"), in the asker's own word ("your
    jeans look blue"), else the kind the VLM's looks give ("a white t-shirt"); a piece out of the picture is said to
    be out of view, never guessed (the looks' colour when the camera can't measure it)."""
    asked = []                                             # (start, part, noun) in the order said
    for part, rx in PARTS:
        m = re.search(rx, text, re.I)
        if m:
            w = m.group(0).lower()
            if bool(re.match(r"[a-z]", w)) != (lang == "en") or w in ("feet", "foot") or w[0] == "신" and w != "신발":
                w = NOUN[part][lang != "en"]
            w = {"genes": "jeans", "jean": "jeans", "short": "shirt", "trouser": "trousers", "청바진": "청바지", "청 바지": "청바지"}.get(w, w)
            asked.append((m.start(), part, re.sub(r"^te[ea] ?shirt|^t ?shirt", "t-shirt", w)))
    kinds = {part: _type_of(part, looks) for part in NOUN}
    asked = [(part, (kinds[part] if lang == "en" else TYPE_KO.get(kinds[part], w)) if kinds[part] and GENERIC.fullmatch(w) else w)
             for _, part, w in sorted(asked)]              # "my bottoms" -> "your jeans" when the looks know the kind
    named = bool(asked)                                    # pieces named: each one is answered, seen or not
    asked = asked or \
        [(part, (kinds[part] if lang == "en" else TYPE_KO.get(kinds[part])) if kinds[part] else NOUN[part][lang != "en"])
         for part in NOUN]
    seen = [(part, w, p["clothes"].get(part) or
             ((looks or {}).get({"upper": "top", "lower": "bottom", "feet": "feet"}[part]) or {}).get("colour"))
            for part, w in asked]
    _last["parts"] = seen
    if len(seen) == 1:
        part, w, c = seen[0]
        if c is None:
            return _say(f"I can't see your {w} from here.", f"여기서는 {_j(w, '이', '가')} 안 보여요.", lang)
        return _say(f"Your {w} {'look' if w.endswith('s') else 'looks'} {c}.",
                    f"{_j(w, '은', '는')} {COLOUR_KO.get(c, c)}으로 보여요.", lang)
    shown = [(part, w, c) for part, w, c in seen if c]
    hidden = [w for part, w, c in seen if not c and (named or part != "feet" or not seen[1][2])]
                                 # "what am I wearing?": shoes out of view are not said alone (the head camera seldom
                                 # sees the feet); with the trousers out of view too, both are
    if not shown:
        return _say("I can't see your clothes well enough to tell.", "옷이 잘 안 보여서 모르겠어요.", lang)
    en = [f"{c} {w}" for _, w, c in shown]
    en = "You're wearing " + (("a " if shown[0][0] == "upper" and not shown[0][1].endswith("s") else "") +
                              (en[0] if len(en) == 1 else ", ".join(en[:-1]) + " and " + en[-1])) + "."
    put_on = [f"{COLOUR_KO.get(c, c)} {w}" for part, w, c in shown if part != "feet"]
    ko = (_j("에 ".join(put_on), "을", "를") + " 입고" if put_on else "") + \
         ("".join(f"{', ' if put_on else ''}{COLOUR_KO.get(c, c)} {_j(w, '을', '를')} 신고" for part, w, c in shown
                  if part == "feet")) + " 계세요."
    if hidden:
        en += f" I can't see your {' or '.join(hidden)} from here."
        ko += f" {_j('와 '.join(hidden), '은', '는')} 여기서 안 보여요."
    return _say(en, ko, lang)


POSE_SAID = {"standing": ("You're standing", "서 계시고"), "sitting": ("You're sitting", "앉아 계시고"),
             "crouching": ("You're crouching", "쪼그려 앉아 계시고")}
POSE_WORD = {"standing": r"stand|서|섰", "sitting": r"sit|seated|앉", "crouching": r"crouch|squat|쪼그"}


def _posture_answer(p, t, lang, looks=None):
    """"Am I sitting or standing?": from the knees and ankles (scene._posture), else the VLM's look; "No, ..." when
    they guessed another."""
    got = p.get("posture") or ((looks or {}).get("posture") if (looks or {}).get("posture") in POSE_SAID else None)
    if got is None:
        return _say("I can't see your legs well enough to tell whether you're sitting or standing.",
                    "다리가 잘 안 보여서 앉아 계신지 서 계신지 모르겠어요.", lang)
    asked = [k for k, rx in POSE_WORD.items() if re.search(rx, t, re.I)]
    lead = ("Yes, " if asked == [got] else "No, " if len(asked) == 1 else "", "네, " if asked == [got] else
            "아니요, " if len(asked) == 1 else "")
    ko = {"standing": "서 계세요.", "sitting": "앉아 계세요.", "crouching": "쪼그려 앉아 계세요."}[got]
    return _say(f"{lead[0]}{POSE_SAID[got][0].replace('You', 'you' if lead[0] else 'You')}.", f"{lead[1]}{ko}", lang)


ACTION_KO = (("wav", "손을 흔들고 계세요"), ("phone call|on the phone|calling", "통화하고 계세요"),
             ("phone", "휴대폰을 보고 계세요"), ("read", "뭔가 읽고 계세요"), ("drink", "뭔가 마시고 계세요"),
             ("eat", "뭔가 드시고 계세요"), ("talk", "이야기하고 계세요"), ("walk", "걷고 계세요"),
             ("photo|picture", "사진을 찍고 계세요"), ("typ", "타자를 치고 계세요"), ("writ", "뭔가 쓰고 계세요"),
             ("point", "뭔가 가리키고 계세요"), ("clap", "박수를 치고 계세요"), ("danc", "춤추고 계세요"),
             ("smil|laugh", "웃고 계세요"), ("stretch", "스트레칭하고 계세요"), ("carry", "뭔가 들고 계세요"),
             ("look", "뭔가 보고 계세요"))   # the VLM's English action said in Korean when it gave no action_ko


def _doing_answer(p, frames, lang, looks=None, own=True):
    act = (looks or {}).get("action")                       # the VLM's words: "looking at a phone"
    o = None if act else _steady(scene.object_in_hand(frames)) if own else _from(p)
    pose_en, pose_ko = POSE_SAID.get(p.get("posture") or (looks or {}).get("posture"), ("You're", "계시고"))
    en, ko = [f"{pose_en}{_m(p['distance_m'], 'en')} {p['where']}"], [f"제 {_where_ko(p['where'])}에 {pose_ko}"]
    if p["facing"] is True and not act:
        en.append("looking at me")
        ko.append("저를 보고 계시고")
    if o:
        en.append(f"holding {_a(o['name'], o['colour'])}")
        ko.append(f"{_j(_ko_name(o['name']), '을', '를')} 들고 계시고")
    if p["raised"]:
        en.append(f"with your {' and '.join(p['raised'])} hand raised")
        ko.append("손을 들고 계시고")
    elif p["pointing"]:
        en.append(f"pointing with your {p['pointing']} hand")
        ko.append("손으로 가리키고 계시고")
    if act and not (o and o["name"] in act):
        en.append(act if act.split()[0].endswith("ing") else f"and {act}")
    ko_s = " ".join(ko).rstrip("고").rstrip("시") + "세요."
    act_ko = act and ((looks or {}).get("action_ko") or next((k for w, k in ACTION_KO if re.search(w, act)), None))
    if act_ko:
        ko_s += " " + act_ko.strip().rstrip(".") + "."
    return _say(", ".join(en) + ".", ko_s, lang)


# ---------- looks: one VLM pass describes the person (clothes types, hair, glasses, hat, mask, bag, action) ----------
LOOKS_S = 10.0                   # s; a person's looks are reused this long for follow-up questions (one VLM pass)
LOOKS_WAIT_S = 16.0              # s; a question that needs the looks waits this long for the VLM (scene timeout 15 s)
LOOKS_SAME_DEG = 15.0            # deg; looks cached for a person at this bearing are theirs
NONE_WORDS = {"", "null", "none", "no", "unknown", "n/a", "not visible", "false", "nothing"}
COLOUR_KO_MORE = {"navy": "남색", "beige": "베이지색", "khaki": "카키색", "dark": "어두운 색", "gold": "금색",
                  "silver": "은색", "cream": "크림색", "blond": "금발", "dyed": "염색한 색", "dark blue": "남색",
                  "light grey": "밝은 회색", "dark grey": "짙은 회색", "multicoloured": "여러 색", "colourful": "알록달록한 색"}
TYPE_KO = {"t-shirt": "티셔츠", "shirt": "셔츠", "jacket": "재킷", "hoodie": "후드티", "sweater": "스웨터", "coat": "코트",
           "blouse": "블라우스", "dress": "원피스", "vest": "조끼", "blazer": "재킷", "cardigan": "카디건", "polo": "셔츠",
           "jeans": "청바지", "trousers": "바지", "pants": "바지", "shorts": "반바지", "skirt": "치마", "leggings": "레깅스",
           "sneakers": "운동화", "shoes": "신발", "boots": "부츠", "sandals": "샌들", "slippers": "슬리퍼",
           "cap": "모자", "hat": "모자", "beanie": "비니", "backpack": "백팩", "handbag": "핸드백", "bag": "가방",
           "shoulder bag": "숄더백", "purse": "지갑", "mask": "마스크", "face mask": "마스크", "glasses": "안경",
           "sunglasses": "선글라스"}
FAMILY = {"t-shirt": "top", "tee": "top", "shirt": "top", "blouse": "top", "polo": "top", "top": "top", "티셔츠": "top",
          "셔츠": "top", "블라우스": "top", "상의": "top",
          "jacket": "jacket", "coat": "jacket", "blazer": "jacket", "재킷": "jacket", "자켓": "jacket", "코트": "jacket",
          "hoodie": "hoodie", "sweatshirt": "hoodie", "후드": "hoodie", "후드티": "hoodie", "맨투맨": "hoodie",
          "sweater": "sweater", "jumper": "sweater", "cardigan": "sweater", "니트": "sweater", "스웨터": "sweater",
          "dress": "dress", "원피스": "dress", "vest": "vest", "조끼": "vest",
          "jeans": "trousers", "jean": "trousers", "genes": "trousers", "trousers": "trousers", "pants": "trousers",
          "slacks": "trousers", "leggings": "trousers", "청바지": "trousers", "바지": "trousers", "하의": "trousers",
          "shorts": "shorts", "반바지": "shorts", "skirt": "skirt", "치마": "skirt", "스커트": "skirt",
          "sneakers": "shoes", "trainers": "shoes", "shoes": "shoes", "boots": "shoes", "sandals": "sandals",
          "slippers": "sandals", "운동화": "shoes", "신발": "shoes", "구두": "shoes", "부츠": "shoes", "샌들": "sandals"}
                                 # what counts as the same kind of piece ("shirt" asked, a t-shirt seen: yes)
EXACT = {"jeans": ("jeans", "jean", "genes", "청바지")}   # asked by these words, only jeans is a yes
PATTERN_ASKED = re.compile(r"\b(?:striped|stripes?|stripy|checked|checkered|chequered|plaid|patterns?|patterned|plain|"
                           r"printed|prints?|dotted|dots|polka|logo)\b|무늬|줄무늬|체크(?!\s*(?:하|해|했|좀))|민무늬|프린트|그림|로고|도트|땡땡이", re.I)
PATTERN_SAID = {"plain": ("plain", "무늬가 없어"), "striped": ("striped", "줄무늬가 있어"), "checked": ("checked", "체크무늬가 있어"),
                "printed": ("printed", "프린트가 있어"), "dotted": ("dotted", "물방울무늬가 있어")}
LENGTHS = {"short": ("short", "짧아"), "medium": ("medium length", "중간 길이예요"), "long": ("long", "길어"),
           "bald": ("shaved", "거의 없어")}
HAIR_KO = {"black": "검은", "brown": "갈색", "blond": "금발", "grey": "회색", "white": "흰", "red": "붉은", "dyed": "염색한"}
LEN_ASKED = re.compile(r"\b(?:long|short|length|bald|medium)\b|길|짧|길이|대머리|단발|장발", re.I)
HAIR_COL_ASKED = re.compile(r"\bcolou?r|\b(?:black|brown|blond|blonde|grey|gray|white|red|dyed)\b|색|컬러|금발|염색", re.I)
WHO_ELSE = re.compile(r"^\W*(?:(?:and|so|then|okay|ok|what|how)\W+)*(?:about\s+)?(?:her|him|them|my friend|the other (?:one|person|guy|man|woman)|"
                      r"(?:the )?(?:person|man|woman|guy|lady) (?:next to|beside|behind) me)\W*$|"
                      r"^\W*(?:그럼\s*)?(?:그\s*(?:분|사람)|옆\s*(?:에\s*)?(?:있는\s*)?(?:분|사람)|친구|저\s*(?:분|사람)|다른\s*(?:분|사람))"
                      r"\s*(?:은|는|도)?요?\s*\??\W*$", re.I)   # "what about her?", "그 사람은?" after a question about someone
ME_AGAIN = re.compile(r"^\W*(?:(?:and|so|then|okay|ok|my turn)\W+)*(?:(?:what|how)\s+about\s+)?(?:me|mine|myself)(?:\s+too)?\W*$|"
                      r"\b(?:what|how) about (?:me|mine)\b|^\W*(?:그럼\s*)?(?:나|저|내\s*거|제\s*거|제\s*것|내\s*것)\s*(?:는|도|은)요?\s*(?:\?|$)|"
                      r"나도\s*(?:해|봐)\s*줘|저도\s*(?:해|봐)\s*주세요|(?:내|제)\s*(?:거|것)\S*\s*(?:은|는)?\s*(?:무슨\s*색|어때)", re.I)
PERSON_KINDS = ("wearing", "hair", "describe", "shirt", "wear_item", "posture", "doing", "holding", "raised")
_looks_cache = {"front": None, "other": None}     # {"at", "bearing", "looks"} per person asked about
_looks_lock = threading.Lock()
_looks_jobs = {}                                   # who -> (thread, started at)


def _flag(v):
    """glasses / hat / mask / bag: False when clearly not worn ("none", false), None when not in view (null), else
    the phrase ("black cap")."""
    if v is False or isinstance(v, str) and v.strip().lower() in ("none", "no", "false", "nothing"):
        return False
    w = _word(v)
    return None if w is None else w


PLURAL_WEAR = re.compile(r"\b(?:jeans|pants|trousers|shorts|leggings|shoes|sneakers|trainers|boots|socks|sandals|"
                         r"glasses|sunglasses|gloves)\b", re.I)


def _who(t):
    """Whom a question about a person asks about: "front" (the one talking), "other", or "left" / "right" (the person
    on that side as Lumi sees it)."""
    t = VOCATIVE.sub(" ", t)                               # "로봇 친구, 제가 뭐 하고 있어요?": the speaker
    m = SIDE_WHO.search(t)
    if m:
        side = (m.group("s") or m.group("s2") or {"왼": "left", "오른": "right"}.get(m.group("k"))).lower()
        return {"left": "right", "right": "left"}[side] if (m.group("o") or "").lower() == "my" else side
    if OTHER.search(t) or re.search(r"\b(?:they|them|their)\b", t, re.I) and not re.search(r"\b(?:i|me|my|i'?m)\b", t, re.I) \
            and not PLURAL_WEAR.search(t):                    # "the jeans, what colour are they?": they = the jeans
        return "other"
    return "front"


def _someone(frames, who):
    """The person a question is about when it is not the one talking: on that side (who "left" / "right"), else the
    nearest other one; None when nobody else is in view."""
    if who in ("left", "right"):
        try:
            front = scene.person_in_front(frames)
            for q in scene._persons(frames):
                if q.get("where") == f"on my {who}" and not (front and q.get("bearing_deg") == front.get("bearing_deg")
                                                             and q.get("distance_m") == front.get("distance_m")):
                    return scene._public(q)
        except Exception as e:                             # noqa: BLE001 - stand-in cameras without _persons
            print(f"seeing: no side look ({e})", flush=True)
    return scene.other_person(frames)


def _word(v):
    """A VLM value as a plain lower-case word or phrase, None for null / none / unknown."""
    if isinstance(v, dict):
        v = " ".join(str(x) for x in (v.get("colour") or v.get("color"),
                                      v.get("object") or v.get("type") or v.get("kind") or v.get("name"))
                     if x and str(x).lower() not in NONE_WORDS)
    if v is True:
        return "yes"
    if v is None or v is False:
        return None
    v = str(v).strip().lower().replace("gray", "grey").replace("colored", "coloured")
    return None if v in NONE_WORDS else v


def _piece(v):
    """{type, colour, pattern} from the VLM's top / bottom / feet (a dict or a phrase)."""
    if isinstance(v, dict):
        out = {k: _word(v.get(k) if k != "colour" else v.get("colour", v.get("color"))) for k in ("type", "colour", "pattern")}
        return out if any(out.values()) else None
    w = _word(v)
    if not w:
        return None
    c = next((c for c in sorted(list(COLOUR_KO) + list(COLOUR_KO_MORE), key=len, reverse=True) if w.startswith(c + " ")), None)
    return {"type": w[len(c) + 1:] if c else w, "colour": c, "pattern": None}


def norm_looks(raw):
    """The VLM's JSON (scene.ask_vlm_person) as {top, bottom, feet: {type, colour, pattern} or None, hair: {colour,
    length} or None, glasses, hat, mask, bag, left_hand, right_hand, posture, action, action_ko: a phrase or None}."""
    if not isinstance(raw, dict):
        return None
    hair = raw.get("hair")
    if isinstance(hair, dict):
        hair = {"colour": _word(hair.get("colour", hair.get("color"))), "length": _word(hair.get("length"))}
    elif _word(hair):
        w = _word(hair)
        hair = {"colour": next((c for c in HAIR_KO if c in w), None), "length": next((n for n in LENGTHS if n in w), None)}
    else:
        hair = None
    glasses = _flag(raw.get("glasses"))
    if glasses == "yes":
        glasses = "glasses"
    if _word(raw.get("sunglasses")) == "yes":
        glasses = "sunglasses"
    elif glasses is None and raw.get("sunglasses") is False:
        glasses = False
    out = {"top": _piece(raw.get("top")), "bottom": _piece(raw.get("bottom")), "feet": _piece(raw.get("feet")),
           "hair": hair if hair and any(hair.values()) else None, "glasses": glasses,
           **{k: _flag(raw.get(k)) for k in ("hat", "mask", "bag")},
           **{k: _word(raw.get(k)) for k in ("left_hand", "right_hand", "posture", "action")},
           "action_ko": raw.get("action_ko") or None}
    for k in ("hat", "mask", "bag"):
        if out[k] == "yes":
            out[k] = k
    return out


def scene_looks(person):
    """looks (norm_looks) from a blind test scene's person (tests/blind/README.md seeing format, plus the r6 fields
    hair, glasses, hat, mask, bag, action, top_type, bottom_type, pattern, shoes), for a checker's fake person_in_front:
    put it under "looks" there; None when the person has none of these fields."""
    q = person
    keys = ("hair", "hair_colour", "hair_color", "hair_length", "glasses", "sunglasses", "hat", "mask", "bag", "action",
            "top_type", "bottom_type", "bottom_kind", "pattern", "top_pattern", "shoes", "posture")
    if not any(k in q for k in keys):
        return None
    hair = q.get("hair")
    if not isinstance(hair, dict) and (q.get("hair_colour") or q.get("hair_color") or q.get("hair_length")):
        hair = {"colour": q.get("hair_colour") or q.get("hair_color"), "length": q.get("hair_length")}
    pattern = q.get("top_pattern", q.get("pattern"))
    action = {"phone": "looking at a phone"}.get(q.get("action"), q.get("action"))
    return norm_looks({"top": {"type": q.get("top_type"), "colour": q.get("top"),
                               "pattern": {"print": "printed"}.get(pattern, pattern)},
                       "bottom": {"type": q.get("bottom_type") or q.get("bottom_kind"), "colour": q.get("bottom")},
                       "feet": q.get("shoes"), "hair": hair, "glasses": q.get("glasses"),
                       "sunglasses": q.get("sunglasses"), "hat": q.get("hat") or ("none" if "hat" in q else None),
                       "mask": q.get("mask") or ("none" if q.get("mask") is False else None),
                       "bag": q.get("bag") or ("none" if "bag" in q else None), "left_hand": q.get("left_hand"), "right_hand": q.get("right_hand"),
                       "posture": q.get("posture"), "action": action, "action_ko": q.get("action_ko")})


def _live(frames, more):
    return bool(more) and bool(frames) and all("color" in f for f in frames)


def _looks_job(frames, who, bearing):
    """The VLM look at that person in the background (one per person at a time); the thread."""
    with _looks_lock:
        job = _looks_jobs.get(who)
        if job and job[0].is_alive():
            return job[0]

        def run():
            t = time.time()
            got = norm_looks(scene.ask_vlm_person(frames, other=who != "front", bearing=bearing if who != "front" else None))
            print(f"seeing: looks of the {who} person in {time.time() - t:.1f} s: {got}", flush=True)
            if got:
                _looks_cache[who] = {"at": t, "bearing": bearing, "looks": got}
        th = threading.Thread(target=run, daemon=True)
        _looks_jobs[who] = (th, time.time())
        th.start()
        return th


def _cached_looks(who, p, after=0.0):
    c = _looks_cache.get(who)
    if c and c["at"] >= max(after, time.time() - LOOKS_S) and \
            abs((c["bearing"] or 0) - (p.get("bearing_deg") or 0)) <= LOOKS_SAME_DEG:
        return c["looks"]
    return None


def _looks(p, frames, lang, slow_line=None, more=None, who="front", wait=True):
    """What the person looks like (norm_looks): the fake scene's ("looks" in p), else the VLM's from a look taken after
    _last["after"] (a "really?": a new one) or within LOOKS_S; wait: run it now (saying "Let me look." first), else
    only what is cached (and a run started in the background). None when it can't be had."""
    if "looks" in p:
        return p["looks"]
    if not _live(frames, more):
        return None
    after = _last.get("after") or 0.0
    got = _cached_looks(who, p, after)
    if got or not wait:
        if not got:
            _looks_job(frames, who, p.get("bearing_deg"))
        return got
    job = _looks_job(frames, who, p.get("bearing_deg"))
    if slow_line:
        slow_line(_say("Let me look.", "잠깐 볼게요.", lang))
    job.join(LOOKS_WAIT_S)
    return _cached_looks(who, p, after)


def prefetch(frames=None):
    """Start the VLM look at the person in front in the background (lumi may call it when a talk starts), so the first
    question about their looks is answered at once."""
    try:
        frames = scene.snapshot() if frames is None else frames
        p = scene.person_in_front(frames) if frames else None
        if p and all("color" in f for f in frames) and not _cached_looks("front", p):
            _looks_job(frames, "front", p.get("bearing_deg"))
    except Exception as e:
        print(f"seeing: no prefetch ({e})", flush=True)


def _ck(c):
    return COLOUR_KO.get(c) or COLOUR_KO_MORE.get(c) or c


def _ko_thing(phrase):
    """"black cap" -> "검은색 모자": the colour and the kind in Korean when known, else the words as they are."""
    if not phrase:
        return ""
    c = next((c for c in sorted(list(COLOUR_KO) + list(COLOUR_KO_MORE), key=len, reverse=True)
              if phrase.startswith(c + " ")), None)
    rest = phrase[len(c) + 1:] if c else phrase
    noun = TYPE_KO.get(rest) or next((v for k, v in TYPE_KO.items() if rest.endswith(k)), None) or KO.get(rest) or rest
    return f"{_ck(c)} {noun}" if c else noun


def _them(said, lang):
    """A "you" sentence about the person in front turned to another person: "Your shirt" -> "Their shirt"."""
    if lang != "en":
        return said if said.startswith(("네", "아니", "그분", "지금은")) else "그분은 " + said
    said = re.sub(r"\byou're\b", "they're", re.sub(r"\bYou're\b", "They're", said))
    said = re.sub(r"\bYou are\b", "They are", re.sub(r"\byou are\b", "they are", said))
    said = re.sub(r"\byou have\b", "they have", re.sub(r"\bYou have\b", "They have", said))
    said = re.sub(r"\bon you\b", "on them", said)
    return re.sub(r"\b([Yy])our\b", lambda m: "Their" if m.group(1) == "Y" else "their", said)


ACCESSORY_OF = (("glasses", r"glass|spectacle|shades|안경|선글라스"), ("hat", r"hat|cap|beanie|head|모자|머리에|머리\s*위"),
                ("mask", r"mask|face|마스크"), ("bag", r"bag|backpack|purse|가방|백팩|배낭"))
ACC_KO = {"glasses": ("안경을", "쓰고"), "hat": ("모자를", "쓰고"), "mask": ("마스크를", "쓰고"), "bag": ("가방을", "메고")}


def _wearing_answer(t, p, frames, lang, slow_line, more, who):
    """Glasses, a hat, a mask, a bag: from the looks; other things (a watch, earrings) the VLM is asked as before."""
    m = WEARING.search(t)
    item = next((g for g in (m.groups() if m else ()) if g), t)
    acc = next((k for k, rx in ACCESSORY_OF if re.search(rx, item, re.I)), None)
    looks = _looks(p, frames, lang, slow_line, more, who) if acc else None
    if looks is None:                                      # live, the looks timed out: no second slow look
        if acc and _live(frames, more):
            return _say("I can't see that well enough to tell.", "그건 잘 안 보여서 모르겠어요.", lang)
        if slow_line and not acc:
            slow_line(_say("Let me look.", "잠깐 볼게요.", lang))
        said = scene.ask_vlm(t, lang, frames)
        return said or _say("I can't see that well enough to tell.", "그건 잘 안 보여서 모르겠어요.", lang)
    v = looks.get(acc)
    if v is None:                                          # not in view (the face, the shoulders): never guessed
        part = {"glasses": ("face", "얼굴이"), "hat": ("head", "머리가"), "mask": ("face", "얼굴이"),
                "bag": ("shoulders", "어깨가")}[acc]
        return _say(f"I can't see your {part[0]} well enough to tell.", f"{part[1]} 잘 안 보여서 모르겠어요.", lang)
    sun = bool(re.search(r"sun|shades|선글라스", item, re.I))
    if acc == "glasses":
        if v and (not sun or v == "sunglasses"):
            return _say(f"Yes, you're wearing {v}.", f"네, {'선글라스를' if v == 'sunglasses' else '안경을'} 쓰고 계세요.", lang)
        if v:                                              # glasses asked as sunglasses
            return _say("You're wearing glasses, not sunglasses.", "선글라스가 아니라 안경을 쓰고 계세요.", lang)
        return _say(f"No, you're not wearing {'sunglasses' if sun else 'glasses'}.",
                    f"아니요, {'선글라스는' if sun else '안경은'} 안 쓰고 계세요.", lang)
    obj, verb = ACC_KO[acc]
    if v and re.search(r"colou?r|색|컬러", t, re.I):          # "what colour is my cap?"
        return _say(f"It's {_a(v)}." if v != acc else f"I can't tell the colour of your {acc}.",
                    f"{_ko_thing(v)}예요." if v != acc else "색은 잘 모르겠어요.", lang)
    if v:
        en_v = {"bag": "have", "hat": "are wearing", "mask": "are wearing"}[acc]
        noun = v if v != acc else ("a " + acc)
        noun = noun if noun.startswith(("a ", "an ")) or noun.endswith("s") else _a(noun)
        ko = _ko_thing(v)
        return _say(f"Yes, you {en_v} {noun}.", f"네, {_j(ko, '을', '를') if ko else obj} {verb} 계세요.", lang)
    word = {"glasses": "glasses", "hat": "a hat", "mask": "a mask", "bag": "a bag"}[acc]
    return _say(f"No, you don't have {word} on." if acc != "bag" else "No, you don't have a bag.",
                f"아니요, {_j(obj[:-1], '은', '는')} 안 {verb} 계세요.", lang)


def _hair_answer(t, looks, lang):
    h = (looks or {}).get("hair")
    if not h:
        return _say("I can't see your hair well enough to tell.", "머리가 잘 안 보여서 모르겠어요.", lang)
    col, ln = h.get("colour"), h.get("length")
    ask_len, ask_col = bool(LEN_ASKED.search(t)), bool(HAIR_COL_ASKED.search(t))
    lead_en = lead_ko = ""
    said_len = next((n for n in LENGTHS if re.search(n, t, re.I)), None) or \
        ("long" if re.search(r"길|장발", t) else "short" if re.search(r"짧|단발", t) else None)
    said_col = next((c for c in HAIR_KO if re.search(rf"\b{c}", t, re.I)), None) or ("blond" if "금발" in t else None)
    if said_len and ln and not ask_col:
        lead_en, lead_ko = ("Yes, ", "네, ") if said_len == ln else ("No, ", "아니요, ")
    elif said_col and col and not ask_len:
        lead_en, lead_ko = ("Yes, ", "네, ") if said_col == col else ("No, ", "아니요, ")
    if ask_len and not ask_col or col is None:
        if ln is None:
            return _say("I can't tell how long your hair is from here.", "머리 길이는 여기서 잘 모르겠어요.", lang)
        return _say(f"{lead_en}{'your' if lead_en else 'Your'} hair looks {LENGTHS[ln][0]}.",
                    f"{lead_ko}머리가 {LENGTHS[ln][1]} 보여요." if ln != "medium" else f"{lead_ko}중간 길이 머리로 보여요.", lang)
    if ask_col and not ask_len or ln is None:
        return _say(f"{lead_en}{'your' if lead_en else 'Your'} hair looks {col}.",
                    f"{lead_ko}{HAIR_KO.get(col, col)} 머리로 보여요." if col != "blond" else f"{lead_ko}금발로 보여요.", lang)
    return _say(f"{lead_en}{'your' if lead_en else 'Your'} hair looks {LENGTHS[ln][0]} and {col}.",
                f"{lead_ko}{HAIR_KO.get(col, col)} 머리이고 {LENGTHS[ln][1]} 보여요.", lang)


def _type_of(part, looks):
    piece = (looks or {}).get({"upper": "top", "lower": "bottom", "feet": "feet"}[part])
    return piece and piece.get("type")


def _wear_item_answer(t, p, frames, lang, slow_line, more, who):
    """"Am I wearing a jacket?", "is she in jeans?", "청바지 입었어?": the kind of piece from the looks, its colour from the
    camera (the looks' colour when the camera can't measure it)."""
    asked = [(m.start(), part, m.group(0).lower()) for part, rx in PARTS for m in [re.search(rx, t, re.I)] if m]
    extra = re.search(r"\b(dress(?:es)?|vests?|blazers?|cardigans?|polos?)\b|원피스|조끼|블라우스|후드|부츠|샌들", t, re.I)
    if extra:
        w = extra.group(0).lower().rstrip("s") if extra.group(0).isascii() else extra.group(0)
        asked.append((extra.start(), "feet" if w in ("부츠", "샌들") else "upper", w))
    if not asked:
        return None
    _, part, word = min(asked)
    word = re.sub(r"^te[ea] ?shirts?|^t ?shirts?", "t-shirt", word).rstrip("?")
    word = word[:-1] if word.endswith("s") and word not in ("jeans", "trousers", "pants", "shorts", "slacks", "leggings",
                                                              "glasses", "dress", "genes") else word
    said_c = next((COLOURS[(m.group("c") or m.group("k")).lower()] for m in COLOUR_SAID.finditer(t)
                   if not (m.group("n") or m.group("kn"))), None)        # "am I wearing a blue hoodie?"
    looks = _looks(p, frames, lang, slow_line, more, who)
    kind = _type_of(part, looks)
    piece = (looks or {}).get({"upper": "top", "lower": "bottom", "feet": "feet"}[part]) or {}
    c = p["clothes"].get(part) or piece.get("colour")
    if kind is None:
        if c is None:
            return _say(f"I can't see your {word} well enough to tell.", f"{_j(TYPE_KO.get(word, word), '이', '가')} 잘 안 보여서 모르겠어요.", lang)
        noun = NOUN[part]
        return _say(f"I can see your {noun[0]} {'look' if noun[0].endswith('s') else 'looks'} {c}, but I can't tell if it's {_a(word) if not word.endswith('s') else word}.",
                    f"{_j(noun[1], '은', '는')} {_ck(c)}으로 보이는데, {TYPE_KO.get(word, word)}인지는 잘 모르겠어요.", lang)
    fam = FAMILY.get(word, word)
    same = FAMILY.get(kind, kind) == fam or fam == "top" and FAMILY.get(kind) in ("top",) or \
        (word in EXACT["jeans"] and kind == "jeans") or (fam == "trousers" and word not in EXACT["jeans"] and FAMILY.get(kind) == "trousers")
    if word in EXACT["jeans"] and kind != "jeans":
        same = False
    if said_c and c and said_c != c:
        same = False
    what_en = f"{c + ' ' if c else ''}{kind}"
    what_en = what_en if kind.endswith("s") and kind not in ("dress",) else _a(what_en)
    what_ko = f"{_ck(c) + ' ' if c else ''}{TYPE_KO.get(kind, kind)}"
    verb_ko = "신고" if part == "feet" else "입고"
    if same:
        return _say(f"Yes, you're wearing {what_en}.", f"네, {_j(what_ko, '을', '를')} {verb_ko} 계세요.", lang)
    return _say(f"No, you're wearing {what_en}.", f"아니요, {_j(what_ko, '을', '를')} {verb_ko} 계세요.", lang)


def _pattern_answer(p, looks, lang):
    top = (looks or {}).get("top") or {}
    pat = top.get("pattern")
    w = top.get("type") or "top"
    if not pat:
        return _say("I can't make out the pattern from here.", "무늬는 여기서 잘 안 보여요.", lang)
    en, ko = PATTERN_SAID.get(pat, (pat, f"{pat} 무늬가 있어"))
    return _say(f"Your {w} looks {en}.", f"{_j(TYPE_KO.get(w, '상의'), '은', '는')} {ko} 보여요.", lang)


def _describe_me(p, frames, lang, slow_line, more, who):
    """"What do I look like?": clothes (kinds from the looks, colours from the camera), hair, glasses, hat, posture."""
    looks = _looks(p, frames, lang, slow_line, more, who) or {}
    en, ko = [], []
    worn = []
    for part, key in (("upper", "top"), ("lower", "bottom"), ("feet", "feet")):
        piece = looks.get(key) or {}
        c = p["clothes"].get(part) or piece.get("colour")
        kind = piece.get("type") or (NOUN[part][lang != "en"] if c else None)
        if kind:
            worn.append((part, c, kind))
    if worn:
        ws = [f"{c + ' ' if c else ''}{k}" for _, c, k in worn]
        ws[0] = ws[0] if worn[0][2].endswith("s") else _a(ws[0])
        en.append("you're wearing " + (ws[0] if len(ws) == 1 else ", ".join(ws[:-1]) + " and " + ws[-1]))
        ko.append(" ".join(f"{_ck(c) + ' ' if c else ''}{TYPE_KO.get(k, k)}" for _, c, k in worn) + " 차림이시고")
    h = looks.get("hair")
    if h and (h.get("colour") or h.get("length")):
        en.append(f"you have {' '.join(x for x in (LENGTHS.get(h.get('length'), ('',))[0], h.get('colour')) if x)} hair")
        ko.append(f"{HAIR_KO.get(h.get('colour'), '')} 머리".strip() + "이시고")
    if looks.get("glasses"):
        en.append(f"you're wearing {looks['glasses']}")
        ko.append("안경을 쓰셨고" if looks["glasses"] != "sunglasses" else "선글라스를 쓰셨고")
    if looks.get("hat"):
        en.append(f"you have {_a(looks['hat'])} on")
        ko.append(f"{_j(_ko_thing(looks['hat']), '을', '를')} 쓰셨고")
    if looks.get("bag"):
        en.append(f"you have {_a(looks['bag'])}")
        ko.append(f"{_j(_ko_thing(looks['bag']), '을', '를')} 메셨고")
    pose_ = p.get("posture") or looks.get("posture")
    if pose_ in POSE_SAID:
        en.append(f"you're {pose_}")
        ko.append(POSE_SAID[pose_][1])
    act = looks.get("action")
    act_ko = act and (looks.get("action_ko") or next((k for w, k in ACTION_KO if re.search(w, act)), None))
    if act:
        en.append(f"you're {act}" if act.split()[0].endswith("ing") else act)
    if not en:
        return _say("I can't see you well enough to describe you. Could you step in front of me?",
                    "잘 안 보여서 설명하기 어려워요. 제 앞으로 와 주시겠어요?", lang)
    s_en = ", ".join(en[:-1]) + (" and " if len(en) > 1 else "") + en[-1]
    s_ko = (" ".join(ko).rstrip("고").rstrip("시").rstrip("셨") + "세요.") if ko else ""
    if act_ko:
        s_ko = (s_ko + " " + act_ko.strip().rstrip(".") + ".").strip()
    return _say(s_en[0].upper() + s_en[1:] + ".", s_ko or "잘 안 보여서 설명하기 어려워요.", lang)


def _closest_answer(frames, lang):
    """"Who is closest to you?": the person in front (taken as the speaker) or someone else nearer, with where they are."""
    p, q = scene.person_in_front(frames), scene.other_person(frames)
    if p is None and q is None:
        n = len(scene.people(frames))
        return _say("I don't see anyone near me right now." if not n else "I see someone, but I can't tell how far they are.",
                    "지금은 가까이에 아무도 안 보여요." if not n else "사람은 보이는데 거리는 잘 모르겠어요.", lang)
    if p and (q is None or (q["distance_m"] or 99) >= (p["distance_m"] or 99)):
        return _say(f"You are, about {_metres(p['distance_m'])} from me." if p["distance_m"] else "You are the closest.",
                    f"손님이 제일 가까워요. 저한테서 {_d(p['distance_m'])}미터쯤 떨어져 계세요." if p["distance_m"] else
                    "손님이 제일 가까워요.", lang)
    top = q["clothes"].get("upper")
    return _say(f"The person {q['where']}{' in ' + _a(top) + ' top' if top else ''} is closest, about {_metres(q['distance_m'])} away.",
                f"제 {_where_ko(q['where'])}에 계신{' ' + _ck(top) + ' 상의를 입은' if top else ''} 분이 제일 가까워요. "
                f"{_d(q['distance_m'])}미터쯤 떨어져 계세요.", lang)


UP_ASKED = re.compile(r"\bup\b|\braised?\b|\braising\b|올라|올렸|손\s*(?:을\s*)?들(?:고|었)", re.I)
HELD_ASKED = re.compile(r"\bhold|\bhave it\b|\bin my\b|\bit\b|\b(?:that|this) in\b|들고|쥐고|잡고|있(?:어|습|나|니)|들었게", re.I)


CANT = re.compile(r"\b(?:how many|count|guess)\b.{0,25}\bfingers?\b|\bfingers?\b.{0,15}(?:\bhow many\b|몇)|"
                  r"손가락\S*\s*(?:몇|how many)|(?:\bhow many\b|몇)\s*(?:개\s*)?손가락|"
                  r"\b(?:in|inside) (?:my|her|his) (?:\w+ )?pockets?\b|\bpockets?\b.{0,10}\bwhat\b|"
                  r"주머니\S*\s*(?:안에|속에|에)?\s*(?:뭐|뭘|무엇|무슨|what)", re.I)   # fingers, a pocket: the cameras can't
KINDS = (("cant", CANT), ("wearing", WEARING), ("hair", HAIR), ("describe", DESCRIBE_ME), ("closest", CLOSEST), ("holding", HOLDING), ("shirt", SHIRT),
         ("wear_item", WEAR_ITEM), ("shirt", PATTERN_Q), ("raised", RAISED), ("where", WHERE_THING), ("hand", WHICH_HAND),
         ("pointing", POINTING), ("posture", POSTURE), ("doing", DOING), ("friend", FRIEND), ("see_me", SEE_ME), ("how_many", HOW_MANY), ("behind", BEHIND), ("side", SIDE_Q),
         ("far", HOW_FAR), ("see", SEE_THING), ("there", THERE_IS), ("still", STILL_THERE), ("see_ko", SEE_THING_KO),
         ("see_more", SEE_MORE), ("what_see", WHAT_SEE))


def answer(text, lang="en", frames=None, slow_line=None):
    """The spoken answer when `text` asks about what Lumi sees, else None. frames: scene.load(...) for tests.
    slow_line(sentence): said before a slow VLM look ("Let me look.")."""
    ways = canons(text.strip())
    asked_at = time.time()                                 # the answer comes from frames taken after this
    last = _last["kind"]
    more = (lambda: scene.snapshot(since=time.time())) if frames is None else None   # new looks (saved frames: none)
    own, t = next(((k, w) for w in ways for k, rx in KINDS if rx.search(w)), (None, canon(text.strip())))
                                 # a whole question of its own is answered as asked, in the first form that asks it
    if own is None:                                        # "안경을 벗었습니다. 지금은 어떻습니까?": asked anew
        own, t = _changed(t, last) or (None, t)
    if own is None:                                        # "저 사람 윗옷은?", "그 사람 glasses는?", "the one on your left?"
        own, t = next((g for w in ways if (g := _piece_of_someone(w))), (None, t))
    if own is None and len(ways) > 1 and last:             # a mixed follow-up: "진짜 really?", "지금은 now?"
        t = next((w for w in ways if AGAIN.search(w) or _follow_up(w, last)[0]), t)
    if last and _last["asked"] and own is None:
        got = _check(t, lang, frames, asked_at, slow_line, more)   # "really?", "and now?", "it's white": a new look
        if got:
            _last["at"] = time.time()
            return got
    if brain.is_backchannel(t) and not BYE.search(t):      # "nice!" between keeps the thread: "and my jeans?"
        return None
    if last and own is None and (HEAD.search(t) or PRAISE.search(t)):
        return None                                        # "look up" / "nice!" between: "and now?" still asks again
    _last["kind"], _last["prev"] = None, last              # a follow-up goes only with the turn right before
    if own != "describe" and ORDER.search(DONE.sub(" ", LOOK_SAID.sub(" ", re.sub(r"(?:좀\s*)?봐\s*(?:줘|주세요|주십시오|줄래)" if own else "^$", " ", t)))) \
            and not PUT_ON.search(t):
        return None                                        # "find the red cup and bring it": a fetch, not a question
    kind = own
    if kind == "posture" and (FAR_ME.search(t) or HOW_FAR.search(t)):
        kind = "far"                                       # "how far am I standing?": the distance
    if kind in ("shirt", "wearing", "hair", "describe", "wear_item") and _about_lumi(t):
        return None                                        # "루미는 무슨 옷 입었어?": about Lumi, not the visitor
    _last["after"] = 0.0                                   # a new question: looks of the last LOOKS_S do
    if kind in PERSON_KINDS:
        _last["who"] = _who(t)
    elif kind is None and last in PERSON_KINDS and _last["asked"] and (WHO_ELSE.search(t) or ME_AGAIN.search(t)):
        kind, t = last, _last["asked"][1]                  # "what about her?", "그 사람은?", "and me?": the same question
        _last["who"] = "other" if WHO_ELSE.search(text) else "front"
    if kind is None and last in SEE_KINDS and _last["thing"] and not _about_lumi(t) and \
            (IT_WHERE.search(t) or IT_COLOUR.search(t) or IT_SIZE.search(t) or IT_COUNT.search(t)):
        kind = "it"                                        # "where is it?", "무슨 색이야?" about the thing just seen
    if kind is None and last:
        kind, t = _follow_up(t, last)
    if kind is None or kind == "how_many" and NOT_IN_VIEW.search(t) and not NOW_END.search(t) or \
            kind == "where" and _thing(WHERE_THING.search(t))[0] in BIG:
        return None                                        # "where is the toilet?": the way there, not the cameras
    if kind == "far" and not (FAR_THING.search(t) or SEE_THING_KO.search(t)):
        if FAR_ME.search(t):
            kind = "far_me"
        elif _last["thing"] is None or last not in SEE_KINDS or re.search(r"\bit\s+(?:to|from)\b", t, re.I) or \
                not (IT.search(t) or FAR_BARE.match(t)):
            return None                                    # "how far is Seoul?": not about the cameras
    from assistant import quick_answers
    if not last and quick_answers.kind_of(text):
        return None                                        # "머리에 컴퓨터 있어?", "Is it safe to stand next to you?": a fact
    _last["kind"], _last["asked"], _last["at"] = kind, (kind, t), time.time()
    frames = _look(frames, asked_at)
    if not frames:
        return _say(*NO_CAMERA, lang)
    said = _reply(kind, t, frames, lang, slow_line, more)
    _last["state"] = _state(frames)                        # "and now?" next: what changed besides the question
    if _live(frames, more) and kind in PERSON_KINDS + ("see_me", "how_many", "closest", "friend"):
        threading.Thread(target=prefetch, args=(frames,), daemon=True).start()   # the next question about them: at once
    return said


CHANGED = re.compile(r"\bput (?:\w+ )?\w+ on\b|\boff\b|\bsit\b|\bstand\b|다른\s*(?:거|것|걸)\s*들었|벗었|벗어|썼어요|썼습니다|썼어(?=\s*[.,!])|꼈|앉았|일어섰|일어났|내렸|내려놨|옮겼|바꿨|놨|놓았|\btook (?:it |them |my \w+ )?off\b|"
                     r"\bput (?:on|down|it down|them on)\b|\b(?:sat|stood) (?:down|up)\b|\bswitched\b|\bmoved\b|\bchanged\b|"
                     r"\blowered\b|\bremoved\b|\b(?:is|are) (?:gone|off)\b|'s (?:gone|off)\b|\bnow\b|지금|이제", re.I)
CHANGE_KINDS = ((r"선글라스|sunglasses", "wearing", "am I wearing sunglasses?", "선글라스 썼어?"),
                (r"안경|glasses", "wearing", "am I wearing glasses?", "안경 썼어?"),
                (r"모자|\bhat\b|\bcap\b|beanie|\bhead\b|머리에", "wearing", "am I wearing a hat?", "모자 썼어?"),
                (r"가방|백팩|\bbag\b|backpack", "wearing", "do I have a bag?", "가방 메고 있어?"),
                (r"앉았|앉아|일어섰|일어났|\bsat\b|\bstood\b|sitting|standing|\bsit\b|\bstand\b", "posture", "am I sitting or standing?",
                 "내가 앉아 있어 서 있어?"),
                (r"(?:손|hand)\S*\s*(?:을\s*)?(?:내렸|내려|올렸|들었)|\bhands? (?:down|up)\b|lowered|raised", "raised",
                 "is my hand raised?", "손 들었어?"),
                (r"다른\s*손|다른\s*(?:거|것|걸)|옮겼|switched|other hand|put (?:it )?down|내려놨|내려놓|놓았|놨|picked up|something else", "holding", "what am I holding?",
                 "내가 뭘 들고 있어?"),
                (r"재킷|자켓|jacket|겉옷|coat|hoodie|sweater", "shirt", "what colour is my top?", "상의 무슨 색이야?"))


def _piece_of_someone(t):
    """A piece of another person named without a question word ("저 사람 윗옷은?", "혹시 그분 상의는요?", "그 사람
    glasses는?"): (kind, the question in full) or None."""
    if not (SIDE_WHO.search(t) or re.search(r"(?:저|그|옆)\s*(?:사람|분)|그분|\b(?:her|his|their)\b", t, re.I)):
        return None
    if re.search(r"머리|\bhair\b", t, re.I):
        return "hair", t + (" 무슨 색이야?" if re.search(r"[가-힣]", t) else " what colour?")
    if re.search(r"안경|선글라스|모자|마스크|가방|백팩|\b(?:glasses|hat|cap|mask|bag|backpack)\b", t, re.I):
        return "wearing", t
    if re.search(rf"{_ITEM_KO}|\b(?:{_ITEM})\b", t, re.I):
        return "shirt", t + (" 무슨 색이야?" if re.search(r"[가-힣]", t) else " what colour?")
    return None


def _changed(t, last):
    """"I took my glasses off, now?", "모자를 벗었습니다. 지금은 쓰고 있습니까?", "앉았어요, 지금은?": the question about
    what they say changed, asked anew: (kind, words) or None."""
    if not (CHANGED.search(t) and (AGAIN.search(t) or "?" in t or re.search(r"어때|어떻|보여|보이|\bnow\W*$|\bwhich one\b", t, re.I))):
        return None
    for rx, kind, en, ko in CHANGE_KINDS:
        if re.search(rx, t, re.I):
            return kind, ko if re.search(r"[가-힣]", t) else en
    return None


def _look(frames, since):
    """The frames given (tests), else the cameras' frames taken after `since` (the question), never older ones."""
    return scene.snapshot(since=since) if frames is None else frames


def _side(t):
    """The hand a correction names: "it's in my right hand", "not right, the left", "왼손이야" -> "left" / "right"."""
    said, denied = [], set()
    for m in HAND_SAID.finditer(NOT_A_HAND.sub(" ", t)):
        s = (m.group("s") or {"왼": "left", "오른": "right"}[m.group("k")]).lower()
        (denied.add(s) if m.group("n") or m.group("kn") else said.append(s))
    if said:
        return said[-1]
    return {"left": "right", "right": "left"}[denied.pop()] if len(denied) == 1 else None


def _colours(t):
    """(colour said, colours denied) in a correction: "no, it's not blue, it's white" -> ("white", {"blue"}). A colour
    before a noun asks about that thing ("what about my blue jeans?")."""
    said, denied = [], set()
    if LIKED.search(t):
        return None, denied
    for m in COLOUR_SAID.finditer(t):
        if re.match(rf"\s+(?:(?:{_ITEM})\b|{_THING_EN})", t[m.end():], re.I):
            continue
        c = COLOURS[(m.group("c") or m.group("k")).lower()]
        (denied.add(c) if m.group("n") or m.group("kn") else said.append(c))
    return (said[-1] if said else None), denied - set(said[-1:])


NUMBER = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5,
          "여섯": 6, "혼자": 1, "둘": 2, "셋": 3, "넷": 4}
COUNT_SAID = re.compile(r"\b(?P<e>one|two|three|four|five|six|\d)\b(?=.{0,12}\b(?:people|persons|of us|here)(?![a-z]))|"
                        r"\bwe(?:'re| are) (?P<w>one|two|three|four|five|six|\d)\b|(?P<s>한|두|세|네|다섯|여섯)\s*사람|"
                        r"\bi count (?P<c>one|two|three|four|five|six|\d)\b|(?P<k>한|두|세|네|다섯|여섯|\d)\s*(?:명|분)|"
                        r"(?P<b>혼자|둘|셋|넷)(?:이야|이에요|입니다|이요|야|요)?\W*$", re.I)


WRONG = re.compile(r"^\W*(?:no|nope|wrong|but|you'?re wrong|that'?s wrong|not (?:true|right)|아니|아닌데|틀렸)\b", re.I)
                                 # "wrong, it's a watch": looked at again even when the word names nothing known


def _said_count(t):
    """The number of people a correction names: "no, there are four of us", "아니야, 세명이야" -> 4 / 3."""
    m = COUNT_SAID.search(t)
    w = m and next(g for g in m.groups() if g)
    return w and (int(w) if w.isdigit() else NUMBER[w.lower()])


def _said_thing(t):
    """The thing a correction names: "nope, this is a book", "아닌데, 이거 오렌지야" -> "book" / "orange"."""
    m = re.search(_THING_EN, t, re.I) or re.search(_THING_KO, t)
    return m and _name(m.group("obj"))


PALE = objects.LIGHT | {"light blue"}   # a white shirt under a cool office light may read light blue


def _verdict(c, said, denied, en, ko, verb, lang, before=None):
    """A colour the person said (or denied) against the colour the camera sees now: agree only when it agrees.
    before: the colour said in the answer before."""
    if c is None:
        return _say(f"I can't see {en} well enough right now.", f"지금은 {_j(ko, '이', '가')} 잘 안 보여요.", lang)
    k = COLOUR_KO.get(c, c)
    if said == c or said and c == f"light {said}" or said is None and c not in denied:
        lead = ("Yes, " if said else "You're right, looking again ", "네, " if said else "맞아요, 다시 보니 ")
        return _say(f"{lead[0]}{en} {verb} {c}.", f"{lead[1]}{_j(ko, '은', '는')} {k}으로 보여요.", lang)
    if said and {said, c} <= PALE:                         # white in shade reads grey: both may be true
        return _say(f"To my camera {en} {verb} {c}; in this light it may well be {said}.",
                    f"제 카메라에는 {k}으로 보이는데, 이 조명에서는 {COLOUR_KO.get(said, said)}일 수도 있어요.", lang)
    if c != before:                                        # the new look sees otherwise than the answer before
        return _say(f"Looking again, {en} {verb} {c}" + (f", not {said}." if said else "."),
                    f"다시 보니 {_j(ko, '은', '는')} {k}으로 보여요.", lang)
    return _say(f"My camera still sees {en} as {c}, but I may be wrong; the light can change colours.",
                f"제 카메라에는 아직 {_j(ko, '이', '가')} {k}으로 보여요. 조명 때문에 틀릴 수도 있어요.", lang)


def _check(t, lang, frames, since, slow_line, more=None):
    """A follow-up right after a seeing answer, from a new look: "really?", "and now?", "look again", "다시 봐" ask the
    same question again; "it's white", "no, it's in my right hand", "아니야 흰색이야" are checked against the camera
    (agreed only when it sees so, else what it sees and that it may be wrong). None: not such a follow-up."""
    kind, asked = _last["asked"]
    again = AGAIN.search(t)
    short = len(t.split()) <= CLAIM_WORDS and \
        not ((ORDER.search(re.sub(r"\W+look\W*$", "", t)) or HEAD.search(t)) and not again)   # "put it in my right hand"; "..., look"
    hand = _side(t) if short and kind in ("holding", "hand", "raised") else None
    side = _asked_hand(t) if short and kind in ("holding", "hand") and HAND_ASKED.search(t) else None
    if side:                                               # "what about the left hand?": that hand, from a new look
        _last["kind"], _last["asked"] = "holding", ("holding", f"what is in my {side} hand?")
        frames = _look(frames, since)
        return _held_answer(frames, lang, side, more, slow_line) if frames else _say(*NO_CAMERA, lang)
    hint = _hint(t) if kind == "holding" and time.time() - _last["unsure"] < HINT_S else None
    if hint or kind == "holding" and _last["unsure"] and TURNED.search(t):   # after "could you tell me what it is?"
        frames = _look(frames, since)
        _last["kind"] = kind
        return _held_answer(frames, lang, _asked_hand(asked), more, slow_line, hint) if frames else _say(*NO_CAMERA, lang)
    said, denied = _colours(t) if short and kind in ("shirt", "holding", "hand") else (None, set())
    named = _said_thing(t) if short and kind in ("holding", "hand") and not hand else None
    count = _said_count(t) if short and kind == "how_many" else None
    again = again or WRONG.search(t) and short and len(t.split()) > 1 and _follow_up(t, kind)[0] is None
    if not (hand or said or denied or again or named or count):
        return None
    frames = _look(frames, since)
    _last["kind"] = kind                                   # the thread goes on: "and now?" again
    _last["after"] = since                                 # looks (glasses, hair ...) from a new VLM look too
    if not frames:
        return _say(*NO_CAMERA, lang)
    if count:                                              # "no, there are four of us": counted again
        n = len(scene.people(frames))
        if n == count:
            return _say(f"Yes, I see {_n(n)} {'person' if n == 1 else 'people'}.", f"네, {n}명이 보여요.", lang)
        return _say(f"I count {_n(n)} {'person' if n == 1 else 'people'} in view now, not {count}; someone may be out of "
                    f"my view.", f"제 카메라에는 지금 {n}명이 보여요. 화면 밖에 계신 분이 있을 수도 있어요.", lang)
    if not (hand or said or denied or named):
        old, _last["state"] = _last.get("state"), _state(frames)
        got = _reply(kind, asked, frames, lang, slow_line, more)
        moved = _changes(old, _last["state"], kind, lang) if NOW_ASKED.search(t) else ""
        return got and _say("I looked again. ", "다시 봤어요. ", lang) + got + moved
    p = scene.person_in_front(frames)
    if p is None:
        return _say("I can't see you well enough to tell. Could you step in front of me?",
                    "잘 안 보여서 모르겠어요. 제 앞으로 와 주시겠어요?", lang)
    if kind == "shirt":
        parts = [(part, w) for part, w, _ in _last["parts"]] or [("upper", NOUN["upper"][lang != "en"])]
        named = [part for part, rx in PARTS if re.search(rx, t, re.I)]   # "my pants are black"
        part, w = next(((a, w) for a, w in parts if a in named), None) or \
            ((named[0], NOUN[named[0]][lang != "en"]) if named else None) or \
            next(((a, w) for a, w, c in _last["parts"] if c in denied), parts[0])
        before = next((c for a, _, c in _last["parts"] if a == part), None)
        c = p["clothes"].get(part)
        _last["parts"] = [(a, x, c if a == part else y) for a, x, y in _last["parts"]]   # "still" next time
        if bool(re.match(r"[a-z]", w)) != (lang == "en"):
            w = NOUN[part][lang != "en"]
        return _verdict(c, said, denied, f"your {w}", w, "look" if w.endswith("s") else "looks", lang, before)
    side = {"left": "왼", "right": "오른"}
    if kind == "raised":                                   # "it's my left hand" after "is my hand up?"
        up = p["raised"]
        if hand in up:
            return _say(f"Yes, your {hand} hand is up.", f"네, {side[hand]}손을 들고 계세요.", lang)
        if up:
            return _say(f"I see your {up[0]} hand up, but I may be wrong.",
                        f"제 카메라에는 {side[up[0]]}손을 드신 걸로 보여요. 틀릴 수도 있어요.", lang)
        return _say("I don't see a hand raised now.", "지금은 손을 들고 계시지 않아요.", lang)
    o = scene.object_in_hand(frames)
    if hand:
        inn = ((p["hands"].get(hand) or {}).get("object"))
        o = {**inn, "hand": hand} if inn else o
        if o is None:
            if scene.person_holds(None, frames) is False:
                return _empty_hands(lang, now=True)
            return _say("I can't see your hands well enough to tell.", "손이 잘 안 보여서 모르겠어요.", lang)
        thing = (_a(o["name"], o["colour"]), _ko_name(o["name"]))
        if o["hand"] == hand:
            return _say(f"Yes, I see {thing[0]} in your {hand} hand.",
                        f"네, {side[hand]}손에 {_j(thing[1], '이', '가')} 보여요.", lang)
        return _say(f"I see {thing[0]} in your {o['hand']} hand, but I may be wrong.",
                    f"제 카메라에는 {side[o['hand']]}손에 {_j(thing[1], '이', '가')} 보여요. 틀릴 수도 있어요.", lang)
    if o is None:
        if named and any(((h or {}).get("something") or {}).get("colour") for h in p["hands"].values()):
            return _held_answer(frames, lang, None, more, slow_line, hint=named)   # "no, it's a bottle": a close look
        return _empty_hands(lang, now=True)
    if named:                                              # "nope, this is a book": checked, not agreed
        if o["name"] == named:
            return _say(f"Yes, I see {_a(o['name'], o['colour'])} in your hand.",
                        f"네, 손에 {_j(_ko_name(o['name']), '이', '가')} 보여요.", lang)
        return _say(f"To my camera it looks like {_a(o['name'])}, not {_a(named)}, but I may be wrong.",
                    f"제 카메라에는 {_j(_ko_name(named), '이', '가')} 아니라 {_ko_name(o['name'])}(으)로 보여요. 틀릴 수도 있어요.", lang)
    return _verdict(o["colour"], said, denied, f"the {o['name']}", _ko_name(o["name"]), "looks", lang)


NOW_END = re.compile(r"\bhow many\b[^.?!]{0,25}\bnow\W*$", re.I)   # "my friend just came. How many now?": the view
NOW_ASKED = re.compile(r"\bnow\b|\bknow\b|\bthis time\b|지금|이제|이번", re.I)   # "and now?": a change is news too
SKIP = {"posture": ("posture",), "holding": ("held",), "hand": ("held", "raised"), "raised": ("raised",),
        "wearing": ("glasses", "hat", "bag"), "how_many": ("n",), "doing": ("posture", "held", "raised")}
                                 # the fields the question itself answers: not said again as a change


def _state(frames):
    """What "and now?" compares: the person in front's posture, held things, raised hands, glasses / hat / bag (from
    looks already had, never a new VLM look) and the number of people; None when nobody is in front."""
    try:
        p = scene.person_in_front(frames)
        if p is None:
            return None
        lk = (p.get("looks") if "looks" in p else _cached_looks("front", p)) or {}
        held = {s: h["object"]["name"] for s, h in p["hands"].items() if h and h.get("object")}
        return {"posture": p.get("posture") or (lk.get("posture") if lk.get("posture") in POSE_SAID else None),
                "held": held if all(p["hands"].values()) or held else None, "raised": tuple(p["raised"]),
                **{k: lk.get(k) for k in ("glasses", "hat", "bag")}, "n": len(scene.people(frames))}
    except Exception as e:                                 # noqa: BLE001 - stand-in cameras
        print(f"seeing: no state ({e})", flush=True)
        return None


def _changes(old, new, kind, lang):
    """" And now you're sitting.": what changed on the person in front since the answer before, beside what was asked
    again ("" when nothing did or either look is missing)."""
    if not old or not new:
        return ""
    en, ko = [], []
    skip = SKIP.get(kind, ())
    a, b = old["posture"], new["posture"]
    if "posture" not in skip and a and b and a != b:
        en.append(f"now you're {b}")
        ko.append({"standing": "지금은 서 계세요", "sitting": "지금은 앉아 계세요", "crouching": "지금은 쪼그려 앉아 계세요"}[b])
    a, b = old["held"], new["held"]
    if "held" not in skip and a is not None and b is not None and a != b:
        for s, x in b.items():
            if a.get(s) != x:
                en.append(f"now you're holding {_a(x)} in your {s} hand")
                ko.append(f"지금은 {KO_SIDE[s]}손에 {_j(_ko_name(x), '을', '를')} 들고 계세요")
        for x in set(a.values()) - set(b.values()):
            en.append(f"you're not holding the {x} any more")
            ko.append(f"이제 {_j(_ko_name(x), '은', '는')} 안 들고 계세요")
    a, b = old["raised"], new["raised"]
    if "raised" not in skip and a != b:
        en.append(f"your {' and '.join(b)} hand is up now" if b else "your hand is down now")
        ko.append(f"지금은 {'·'.join(KO_SIDE[x] + '손' for x in b)}을 들고 계세요" if b else "지금은 손을 내리셨어요")
    for k, on_en, on_ko, off_ko in (("glasses", "glasses", "안경을 쓰고 계세요", "안경을 벗으셨어요"),
                                    ("hat", "a hat on", "모자를 쓰고 계세요", "모자를 벗으셨어요"),
                                    ("bag", "a bag", "가방을 메고 계세요", "가방을 내려놓으셨어요")):
        a, b = old[k], new[k]
        if k in skip or a is None or b is None or bool(a) == bool(b):
            continue
        en.append(f"now you have {on_en}" if b else f"you've taken your {'glasses' if k == 'glasses' else k} off")
        ko.append(f"지금은 {on_ko}" if b else off_ko)
    if "n" not in skip and old["n"] != new["n"]:
        en.append(f"I see {_n(new['n'])} {'person' if new['n'] == 1 else 'people'} now")
        ko.append(f"지금은 {new['n']}명이 보여요")
    if not en:
        return ""
    return _say(" And " + ", and ".join(en) + ".", " 그리고 " + ". ".join(ko) + ".", lang)


def _reply(kind, t, frames, lang, slow_line=None, more=None):
    """The answer to a question of this kind (answer() read it) from these frames."""
    if kind == "behind":
        return _say("My cameras look forward, so I can't see what's behind me. " + describe(frames, "en"),
                    "제 카메라는 앞만 보여서 뒤는 볼 수 없어요. " + describe(frames, "ko"), lang)
    if kind == "side":                                     # "what's on your right?": what the cameras see there
        m = SIDE_Q.search(t)
        side = (m.group("e") or m.group("e2") or {"왼": "left", "오른": "right"}[m.group("k")]).lower()
        there = f"on my {side}"
        n = sum(1 for q in scene.people(frames) if scene.where(q["bearing_deg"]) == there)
        names = []
        for h in scene.things(frames):
            if h["where"] == there and (h["score"] or 0) >= DESCRIBE_SCORE and h["name"] not in names:
                names.append(h["name"])
        names = names[:NEAR_SAY]
        en = ([f"{_n(n)} {'person' if n == 1 else 'people'}"] if n else []) + [_a(x) for x in names]
        ko = ([f"사람 {n}명"] if n else []) + [_ko_name(x) for x in names]
        k = {"left": "왼쪽", "right": "오른쪽"}[side]
        if not en:
            return _say(f"I don't see anything I can name on my {side} right now.",
                        f"지금 제 {k}에는 제가 알아볼 수 있는 게 안 보여요.", lang)
        return _say(f"On my {side} I see " + (en[0] if len(en) == 1 else ", ".join(en[:-1]) + " and " + en[-1]) + ".",
                    f"제 {k}에 {_j(', '.join(ko), '이', '가')} 보여요.", lang)
    if kind == "what_see":
        if re.search(r"table|desk|테이블|탁자|책상", t, re.I):
            things = _listing(frames, lang, small_only=True)
            return _say(f"On the table I see {things}." if things else "I don't see anything on the table I can name.",
                        f"테이블 위에 {_j(things, '이', '가')} 보여요." if things else "테이블 위에 제가 알아볼 수 있는 건 없어요.", lang)
        return describe(frames, lang)
    if kind == "how_many":
        n = len(scene.people(frames))
        return _say(f"I see {_n(n)} {'person' if n == 1 else 'people'} right now." if n else "I don't see anyone right now.",
                    f"지금 {n}명이 보여요." if n else "지금은 아무도 안 보여요.", lang)
    if kind in ("see", "there", "still", "see_ko", "see_more", "where"):
        m = {"see": SEE_THING, "there": THERE_IS, "still": STILL_THERE, "see_ko": SEE_THING_KO, "see_more": SEE_MORE,
             "where": WHERE_THING}[kind].search(t)
        name, colour = _thing(m)
        if name is None:
            return None
        return _seen_answer(name, colour, frames, lang)
    if kind == "it":
        return _it_answer(t, frames, lang)
    if kind == "far":
        m = FAR_THING.search(t) or SEE_THING_KO.search(t)
        if m:
            name, colour = _thing(m)
            _last["name"] = name
            hits = _sees(name, colour, frames)
            if not hits:
                return _say(f"I don't see {_a(name, colour)} right now.", f"지금은 {_j(_ko_name(name), '이', '가')} 안 보여요.", lang)
            _last["thing"] = hits[0]
        name = _last["thing"]["name"]
        again = [h for h in _sees(name, None, frames) if h["camera"] == _last["thing"]["camera"]] or [_last["thing"]]
        d = min(again, key=lambda h: abs((h["bearing_deg"] or 0) - (_last["thing"]["bearing_deg"] or 0)))["distance_m"]
        if d is None:
            return _say("I can't measure how far it is.", "거리는 잴 수 없어요.", lang)
        return _say(f"The {name} is about {_metres(d)} from me.", f"{_j(_ko_name(name), '은', '는')} 저한테서 {_d(d)}미터쯤 떨어져 있어요.", lang)
    if kind == "holding" and _last.get("who", "front") != "front":   # "왼쪽에 계신 분 손에 뭐 있어요?"
        q = _someone(frames, _last["who"])
        if q is None:
            return _say("I only see you right now.", "지금은 한 분만 보여요.", lang)
        o = _from(q)
        if o:
            return _say(f"They're holding {_a(o['name'], o['colour'])} in their {o['hand']} hand.",
                        f"그분은 {KO_SIDE[o['hand']]}손에 {_j(_ko_name(o['name']), '을', '를')} 들고 계세요.", lang)
        if not any(q["hands"].values()):
            return _say("I can't see their hands well enough to tell.", "그분 손이 잘 안 보여서 모르겠어요.", lang)
        return _say("I don't see anything in their hands.", "그분 손에는 든 게 없어 보여요.", lang)
    if kind == "holding":
        return _held_answer(frames, lang, _asked_hand(t), more, slow_line)
    if kind == "closest":
        return _closest_answer(frames, lang)
    if kind == "cant":
        if re.search(r"pocket|주머니", t, re.I):
            return _say("I can't see inside your pocket.", "주머니 안은 안 보여서 알 수 없어요.", lang)
        return _say("I can't count fingers with my cameras; I see the hand, not each finger.",
                    "제 카메라로는 손가락 개수까지는 알 수 없어요.", lang)
    p = scene.person_in_front(frames)
    if kind in ("wearing", "hair", "describe", "wear_item") and p is not None:
        if _last.get("who", "front") != "front":           # "is she wearing glasses?", "what about her?"
            q = _someone(frames, _last["who"])
            if q is None:
                return _say("I only see you right now.", "지금은 한 분만 보여요.", lang)
            return _them(_person_reply(kind, t, q, frames, lang, slow_line, more, _last["who"]), lang)
        return _person_reply(kind, t, p, frames, lang, slow_line, more, "front")
    if kind == "friend":                                   # "do you still see my friend?": anyone besides them
        n = len(scene.people(frames)) - (p is not None)
        if n > 0:
            return _say(f"Yes, I see {_n(n)} other {'person' if n == 1 else 'people'} besides you.",
                        f"네, 다른 사람 {n}명이 더 보여요.", lang)
        return _say("No, I only see you now." if p else "No, I don't see anyone right now.",
                    "아니요, 지금은 한 분만 보여요." if p else "아니요, 지금은 아무도 안 보여요.", lang)
    if kind == "shirt" and (OTHER.search(VOCATIVE.sub(" ", t)) or _last.get("who", "front") != "front"):   # "what is my friend wearing?", "옆 사람 셔츠는 무슨 색이에요?"
        q = _someone(frames, _last.get("who") if _last.get("who", "front") != "front" else "other")
        if q is None:
            return _say("I only see you right now.", "지금은 한 분만 보여요.", lang)
        return _them(_clothes_answer(q, t, lang, _looks(q, frames, lang, None, more, _last.get("who") or "other", wait=False)), lang)
    if kind == "see_me":
        if p is None and not scene.people(frames):
            return _say("No, I can't see you right now.", "아니요, 지금은 안 보여요.", lang)
        d = p["distance_m"] if p else None
        return _say(f"Yes, I can see you{_m(d, 'en')}.", f"네, 보여요.{' ' + f'{_d(d)}미터쯤 앞에 계세요.' if d else ''}", lang)
    if p is None:
        return _say("I can't see you well enough to tell. Could you step in front of me?",
                    "잘 안 보여서 모르겠어요. 제 앞으로 와 주시겠어요?", lang)
    if kind == "far_me":
        if p["distance_m"] is None:
            return _say("I can't measure how far you are.", "거리는 잴 수 없어요.", lang)
        return _say(f"You're about {_metres(p['distance_m'])} from me.", f"저한테서 {_d(p['distance_m'])}미터쯤 떨어져 계세요.", lang)
    looks = _looks(p, frames, lang, None, more, wait=False)   # only what is cached: never slower for these
    if kind == "shirt":
        if PATTERN_ASKED.search(t):                        # "is my shirt striped?": the VLM's look
            return _pattern_answer(p, _looks(p, frames, lang, slow_line, more), lang)
        return _clothes_answer(p, t, lang, looks)
    if kind == "hand":                                     # "which hand?": the one holding something, else one raised
        up = UP_ASKED.search(t) or _last.get("prev") == "raised" and not HELD_ASKED.search(t)
                                                           # "left or right, which one's up?"; "which hand?" after "is my hand up?"
        if not up and (HELD_ASKED.search(t) or scene.object_in_hand(frames) or not p["raised"]):
            return _held_answer(frames, lang, None, more, slow_line)
        kind = "raised"
        _last["kind"], _last["asked"] = kind, (kind, t)      # "and now?" asks about the raised hand again
    if kind == "raised":
        if p["raised"]:
            return _say(f"Yes, your {' and '.join(p['raised'])} hand is up.",
                        "네, " + " ".join({"left": "왼손", "right": "오른손"}[s] for s in p["raised"]) + "을 들고 계세요.", lang)
        if not any(p["hands"].values()):
            return _say("I can't see your hands well enough to tell.", "손이 잘 안 보여서 모르겠어요.", lang)
        return _say("No, your hands are down.", "아니요, 지금은 손을 안 들고 계세요.", lang)
    if kind == "pointing":
        if not p["pointing"]:
            return _say("I don't see you pointing.", "가리키고 계신 게 안 보여요.", lang)
        target = scene.pointing_target(frames)
        near = None
        if target:
            near = min((h for h in scene.things(frames) if h["position_mm"] and None not in h["position_mm"][:2]),
                       key=lambda h: sum((a - b) ** 2 for a, b in zip(h["position_mm"][:2], target["position_mm"][:2])),
                       default=None)
            if near and sum((a - b) ** 2 for a, b in zip(near["position_mm"][:2], target["position_mm"][:2])) > 300 ** 2:
                near = None
        side = {"left": "your left", "right": "your right"}[p["pointing"]]
        if near:
            return _say(f"You're pointing at {_a(near['name'], near['colour'])}, I think.",
                        f"{_j(_ko_name(near['name']), '을', '를')} 가리키시는 것 같아요.", lang)
        return _say(f"You're pointing with {side} hand, but I can't tell at what.",
                    "손으로 가리키시는 건 보이는데, 무엇인지는 모르겠어요.", lang)
    if kind in ("doing", "posture") and _last.get("who", "front") != "front":   # "what about her?" after "what am I doing?"
        q = _someone(frames, _last["who"])
        if q is None:
            return _say("I only see you right now.", "지금은 한 분만 보여요.", lang)
        lk = _looks(q, frames, lang, None, more, _last["who"], wait=False)
        return _them(_doing_answer(q, frames, lang, lk, own=False) if kind == "doing" else _posture_answer(q, t, lang, lk), lang)
    if kind == "doing":
        return _doing_answer(p, frames, lang, looks)
    if kind == "posture":
        return _posture_answer(p, t, lang, looks)
    return None


def _person_reply(kind, t, p, frames, lang, slow_line, more, who):
    """Glasses / hat / mask / bag, hair, "what do I look like", "am I wearing a jacket?" about person p."""
    if kind == "wearing":
        return _wearing_answer(t, p, frames, lang, slow_line, more, who)
    if kind == "hair":
        return _hair_answer(t, _looks(p, frames, lang, slow_line, more, who), lang)
    if kind == "describe":
        return _describe_me(p, frames, lang, slow_line, more, who)
    return _wear_item_answer(t, p, frames, lang, slow_line, more, who) or _clothes_answer(p, t, lang)


RECHECK_S = 30.0                 # s; a one-word "really?" this soon after a seeing answer is a new look, also said
                                 # while Lumi still talks


def recheck(text):
    """"Really?", "진짜?", "Now?" right after a seeing answer: worth interrupting Lumi for (a new look), though one word."""
    return bool(_last["kind"] and time.time() - _last["at"] < RECHECK_S and AGAIN.search(text.strip()))


ABOUT_VIEW = re.compile(r"\b(?:see|seeing|look(?:ing)? at|camera|cameras|in front of you|around you|holding|wearing|"
                        r"colou?r)\b|보여|보이|보고|카메라|들고|입고|무슨 색", re.I)


def warm_up():
    """Load the pose and object models now, so the first question is answered in ~0.1 s, not ~1 s; the close look's
    model in the background."""
    try:
        pose.load()
        scene._box_net()
        threading.Thread(target=scene.warm_vlm_hand, daemon=True).start()   # the close look's model, ~12 s
    except Exception as e:
        print(f"seeing: models not loaded ({e})", flush=True)


def facts_for(text):
    """" " + facts() for words about what Lumi sees that answer() did not take, and for anything said soon after a
    seeing answer, else "" (the model then answers from what the cameras see now, not from what it said before)."""
    recent = time.time() - _last["at"] < THREAD_S
    return " " + facts() if ABOUT_VIEW.search(text) or recent else ""


def _looks_line(p):
    """" They have short black hair, glasses, ..." from the person's looks of the last LOOKS_S (no new VLM look)."""
    lk = p.get("looks") if "looks" in p else _cached_looks("front", p)
    if not lk:
        return ""
    bits = []
    h = lk.get("hair") or {}
    if h.get("colour") or h.get("length"):
        bits.append(f"{' '.join(x for x in (h.get('length'), h.get('colour')) if x)} hair")
    for k, none in (("glasses", "no glasses"), ("hat", "no hat"), ("bag", "no bag")):
        if lk.get(k):
            bits.append(lk[k] if k != "hat" else f"{lk[k]} on the head")
        elif lk.get(k) is False:
            bits.append(none)
    return ((" They have " + ", ".join(bits) + ".") if bits else "") + \
        (f" They are {lk['action']}." if lk.get("action") else "")


def facts(frames=None):
    """One line of what the cameras see now, for the conversation model's prompt ("" when nothing / no camera)."""
    try:
        frames = _look(frames, time.time())
        if not frames:
            return ""
        line = describe(frames, "en")
        p = scene.person_in_front(frames)
        if p:
            o = _steady(scene.object_in_hand(frames))
            line += f" The person in front is{_m(p['distance_m'], 'en')}" + \
                (f", {p['posture']}" if p.get("posture") else "") + \
                (", wearing " + ", ".join(f"{c} {NOUN[k][0]}" for k, c in p["clothes"].items() if c)
                 if any(p["clothes"].values()) else "") + \
                (f", holding {_a(o['name'], o['colour'])}" if o else "") + "." + _looks_line(p)
        return "Your cameras see now (a new look; it replaces anything said about them before): " + line
    except Exception as e:
        print(f"seeing: no facts ({e})", flush=True)
        return ""


if __name__ == "__main__":
    args = sys.argv[1:]
    fr = None
    if args and args[0] == "--load":
        fr, args = scene.load(args[1]), args[2:]
    for q in args:
        lang = "ko" if re.search(r"[가-힣]", q) else "en"
        print(f"{q} -> {answer(q, lang, fr, slow_line=print)}")
