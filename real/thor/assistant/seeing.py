"""Spoken answers about what Lumi sees, from vision/scene.py: "do you see the red apple?", "how far is it?", "what's on
the table?", "how many people are here?", "what am I holding?", "what colour is my shirt?", "is my hand raised?",
"am I wearing glasses?" (the slow VLM), English and Korean.

    answer(text, lang, frames=None, slow_line=None) -> spoken sentence, or None when the words are not such a question
    facts() -> one line of what the cameras see now, for the conversation model; facts_for(text) only when the words
    are about seeing

    python assistant/seeing.py "do you see a cup?"          # answer from the cameras now
    python assistant/seeing.py --load tests/data/scene_white_shirt_near "what colour is my shirt?"

Only what the detections give is said; anything else is "I can't tell". Nothing here moves the head.
Every answer comes from frames taken after the words (scene.snapshot(since=...)), also a follow-up right after one
("really?", "and now?", "다시 봐": the same question again) and a correction ("it's white", "오른손이야"), which is
checked against the camera and agreed with only when the camera sees it so.
"""
import re
import sys
import time

from assistant import brain
from vision import objects, pose, scene

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
           "브라운": "brown"}   # "brown" is only said by people: the camera names browns orange
COLOUR_KO = {"white": "흰색", "red": "빨간색", "blue": "파란색", "green": "초록색", "yellow": "노란색", "black": "검은색",
             "orange": "주황색", "grey": "회색", "purple": "보라색", "pink": "분홍색", "brown": "갈색", "light blue": "하늘색"}
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

SEE_ME = re.compile(r"\b(do|can) you see me\b|\bam i (visible|in (your )?view)\b|(나|저)(를|)? ?보여|(나|저) ?보이", re.I)
SEE_THING = re.compile(r"(?<!what )\b(?:do|can|could) you (?:still )?(?:see|spot|notice)\b.*?\b(?:a|an|the|any|some|my)?\s*" + _THING_EN, re.I)
THERE_IS = re.compile(r"\b(?:is|are) there (?:still )?(?:a|an|any|some)\s+" + _THING_EN +
                      r"(?! (?:open|close|nearby|near here|around here))", re.I)
STILL_THERE = re.compile(r"\bis (?:the|my|that|your|this) " + _THING_EN + r" still (?:there|here|on|in)\b", re.I)
SEE_THING_KO = re.compile(_THING_KO + r"(?:이|가|은|는|을|를|도)?\s*(?:(?:(?:아직도?|지금도?|still)\s*)?(?:보여|보이)|아직도?\s*있|"
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
BEHIND = re.compile(r"\bwhat(?:'s| is) behind you\b|^(?!.*\b(?:look|turn|check)\b).*\bbehind you\b.*\?|"   # not "can you look
                    r"뒤에 ?(?:뭐|무엇|누가|누구)", re.I)                                             # behind you?" (a head turn)
HOW_MANY = re.compile(r"\bhow many (?:people|persons|visitors|humans|folks|guys)\b|\bhow many of us\b|몇 ?(?:명|사람)|"
                      r"몇\s*분\s*(?:이\s*)?계|\bcount (?:the )?(?:people|persons|heads|us)\b|사람\s*(?:count|how many)|"
                      r"\bare we (?:\w+ )?(?:or|two|three|four)\b.*\bhow many\b|"
                      r"^\W*(?:(?:and|so|okay)\W+)?(?:(?:지금|이제|now)\s*(?:은|는)?\s*how many|how many(?: do you see| are there)? now)\W*$",
                      re.I)   # "How many now?"
NOT_IN_VIEW = re.compile(r"\b(?:work|works|working|employ\w*|staff|company|companies|campy|firm|cutshion|country|city|"
                         r"live|lives|living|world|team|office|branch|developers?|engineers?|built|made|came|visited|talked|met)\b|"
                         r"직원|회사|쿳션|일하|일해|근무|나라|국가|도시|살아|사는|인구|팀|지사|만든|만들|개발자|엔지니어|왔었|다녀갔|만났|얘기했|이야기했",
                         re.I)   # "how many people work at Cutshion?": the company, not the cameras
HOLDING = re.compile(r"\bwhat(?:'s| is| am| do)? (?:i|is (?:in|on) my (?:left |right |other )?hands?|(?:in|on) my (?:left |right |other )?hands?)\b.*?\b(?:holding|carrying|have)\b|"
                     r"\bwhat(?:'s| is)(?: it| this| that)? (?:in|on) my (?:left |right |other )?hands?\b|\bwhat(?:'s| is) my (?:left |right |other )?hands?\?|\bwhat (?:do )?i have (?:in|on) my (?:left |right |other )?hands?\b|\bam i holding\b|"
                     r"\bis there (?:something|anything) in my hand\b|\bwhat is this\b(?=.*\bhand\b)|\bwhat am i hold in\b|\banything (?:in|on) my (?:left |right |other )?hands?\b|"
                     r"\bwhat\b.{0,25}\b(?:i'?m|i am) (?:holding|carrying)\b|\bwhat(?:'ve| have| do) i (?:got|have)\b(?! to)|"
                     r"\bwhat(?:'s| is) this(?: thing)?\W*$|\bwhat i(?:'ve| have) got\b|hold\s*했\S*\W+.*뭐|"
                     r"(?<!루미 )(?<!네 )손에\s*(?:뭐|뭘|든|있는).{0,15}(?:보여|보이|알아|맞혀|\bwhat is it\b)|"   # Lumi's hand: status
                     r"(?:my\s*hand|(?:내|제)\s*(?:오른|왼)?손)\s*에?\s*(?:든|있는|뭐|뭔|무엇)|(?:내|제)\s*(?:오른|왼)?손\b.*(?:뭐|뭘)\s*들고\s*있|\bi(?:'ve| have) got something\b.*\bwhat\b|"
                     r"(?:내가|제가)\s*(?:hold|들고|잡고|쥐고)\s*(?:하고\s*)?있는\s*(?:거|게|것)|손에\s*(?:something|뭔가|무언가)|"
                     r"^\W*(?:\S+\W+){0,3}(?:이거|이건|이게)\s*(?:뭐|뭔|무엇|what)|"
                     r"(?:내가|제가|나|저)\s*(?:지금\s*)?(?:뭐|뭘|무엇을?)\s*(?:들고|잡고|쥐고|holding)|(?:내|제)\s*(?:오른|왼)?(?:손|hand)에\s*(?:뭐|뭔|무엇|든|있)|"
                     r"(?:내가|제가)\s*(?:든|들고\s*있는|쥐고\s*있는)\s*(?:거|게|것)", re.I)   # "제가 들고 있는 거 뭐예요?"
                                 # "뭐 들고 있어?" without "내가" asks about Lumi's own hand (lumi.status_question)
WHICH_HAND = re.compile(r"\b(?:which|what) hand(?![a-z])|무슨\s*손|오른손\S*\s*(?:아니면\s*)?왼손\S*\s*\?|\bleft or (?:my |the )?right\b|\bwhich of my hands\b|어느\s*(?:쪽\s*)?(?:손|hand)|손\s*어느\s*쪽|"
                        r"왼손\S*\s*(?:아니면\s*)?오른손\S*\s*\?|left\S*\s*right\S*\s*\?", re.I)   # held first, else raised
_UPPER = r"short|t-? ?shirts?|te[ea] ?shirts?|shirts?|tops?|jackets?|sweaters?|sweatshirts?|hoodies?|jumpers?|blouses?|coats?"
_LOWER = r"pants|trousers?|jeans?|genes|skirts?|shorts|slacks|leggings|bottoms"   # "genes", "jean": heard for jeans
_FEET = r"shoes?|sneakers?|trainers|boots?|sandals?|slippers?|socks?|feet|foot"
_UPPER_KO = r"티셔츠|셔츠|셔쯔|상의|윗옷|윗도리|겉옷|재킷|자켓|후드티|맨투맨|니트|스웨터|코트"
_LOWER_KO = r"청 ?바지|청바진|반바지|바지|하의|치마|스커트"
_FEET_KO = r"운동화|신발|구두"
_ITEM = rf"(?:{_UPPER}|{_LOWER}|{_FEET}|clothes|clothing|outfit)"
_ITEM_KO = rf"(?:{_UPPER_KO}|{_LOWER_KO}|{_FEET_KO}|옷)"
PARTS = (("upper", rf"\b(?:{_UPPER}|upper half)\b|{_UPPER_KO}"),
         ("lower", rf"\b(?:{_LOWER}|bottom half|lower half)\b|{_LOWER_KO}|아래(?:쪽)?|밑"),
         ("feet", rf"\b(?:{_FEET})\b|{_FEET_KO}|신었|신고 있|신은"))
SHIRT = re.compile(rf"\bcolou?rs?\b.{{0,30}}?\b(?:my|the|his|her|their|this)\s+(?:[\w']+\s+)?{_ITEM}\b|"
                   rf"\bcolou?r\s*(?:내|제)\s*(?:{_ITEM_KO})|"
                   rf"\bcolou?r(?:'s| is)? (?:the |my )?(?:bottom|top|lower|upper) half\b|"
                   rf"\b(?:{_UPPER}|{_LOWER})\b\s*(?:은|는|이|가)?\s*(?:(?:무슨|어떤|뭔)\s*)?(?:색|컬러|colou?r)|"
                   rf"\bput on (?:a |an )?(?:\w+ )?{_ITEM}\b.{{0,25}}\bcolou?r|{_ITEM}\W+what colou?r|\bmy\s+(?:\w+\s+)?{_ITEM}(?:'s)?\s+colou?r|"
                   rf"\b(?:is|are) my\s+(?:\w+\s+)?{_ITEM}\s+(?:" + "|".join(c for c in COLOURS if c.isascii()) + r")\b|"
                   r"\bwhat\b.{0,25}?\b(?:am i|i'?m|do i|did i)\s+(?:wear(?:ing)?|have on|got on)\b|"
                   r"\bwhat(?:'s| is| are)? (?:she|he|they|my friend|the (?:other|second) (?:person|guy|man|woman)|"
                   r"the (?:person|man|woman|guy|lady) next to me) wearing\b|"
                   r"\bwhat colou?r (?:is|are) (?:she|he|they|my friend|the (?:other|second|person|man|woman|guy|lady)\b.{0,15}) wearing\b|"
                   r"\b(?:i (?:changed|switched)|changed (?:my )?(?:clothes|shirt|top))\b.{0,25}\bcolou?r|"
                   r"(?:위|아래|밑)(?:쪽)?\s*(?:은|는)?\s*무슨\s*색|"
                   r"\bwhat(?:'s| is| are)? on my (?:feet|foot)\b|\bdescribe my (?:clothes|clothing|outfit)\b|"
                   rf"{_ITEM_KO}\s*(?:은|는|이|가|의)?\s*(?:무슨|어떤|뭔|무엇|뭐)?\s*(?:색|컬러|colou?r)|무슨\s*색\s*{_ITEM_KO}|"
                   r"(?:뭐|뭘|무엇을?|무슨|어떤)\s*(?:\w+\s*)?(?:입었|입고|입은|신었|신고|신은)|"
                   r"(?:입었|벗었|바꿨|갈아입|change)\S*\W+.{0,12}(?:무슨\s*색|colou?r|컬러)|\b(?:" + _UPPER + "|" + _LOWER + r")\s*(?:색|컬러)", re.I)   # 2026-10-21 live:
                                 # "What is the color of my t-shirt?", "What is it? Color my jeans." went to the LLM
OTHER = re.compile(r"\b(?:friend|colleague|partner|she|he|his|her|their)\b|\bthe (?:other|second) (?:person|guy|man|woman|one)\b|"
                   r"\b(?:person|man|woman|guy|lady) (?:next to|beside|behind|with) me\b|친구|동료|옆\s*(?:에\s*)?(?:있는\s*)?(?:사람|분)|"
                   r"다른\s*(?:사람|분)|그\s*(?:사람|분)", re.I)   # someone else than the person talking
FRIEND = re.compile(r"\b(?:do|can) you (?:still )?see (?:my (?:friend|colleague)|the other (?:person|guy|man|woman))\b|"
                    r"\bis (?:my (?:friend|colleague)|the other (?:person|guy|man|woman)) still (?:here|there|in view)\b|"
                    r"(?:친구|동료|그\s*사람|다른\s*(?:사람|분)|옆\s*사람)\S*\s*(?:아직도?\s*|still\s*)?(?:보여|보이|있어|있나|있습)", re.I)
DOING = re.compile(r"\bwhat am i doing\b|\bwhat(?:'m| am) i up to\b|(?:내가|제가|나|저)\s*(?:지금\s*)?(?:뭐|뭘|무엇을?)\s*하고\s*있", re.I)
RAISED = re.compile(r"\bwhich (?:hand|arm) (?:do i have|have i got) (?:up|raised)\b|\b(?:is|are) my (?:hand|hands|arm|arms) (?:raised|up)\b|\bam i raising (?:my )?(?:hand|arm)\b|"
                    r"\bdid i raise my hand\b|\bwhich hand (?:did i raise|is (?:up|raised)|am i (?:raising|holding up|lifting))\b|"
                    r"\bwhich (?:hand|arm) is (?:up|raised)\b|\b(?:see|tell) (?:if|whether) (?:i'?m|i am) raising\b|"
                    r"\b(?:see|is) my (?:hand|arm)s? (?:up|raised)\b|\bhands? up or (?:not|down)\b|\bmy (?:hand|arm) is (?:up|raised)\b|"
                    r"\bi'?m raising (?:my |a )?(?:hand|arm)\b|\bi am raising\b|\b(?:is )?one of my hands (?:is )?up\b|"
                    r"(?:손|hand)\s*(?:을\s*)?(?:들었|들고\s*있|올라가|올렸|올리고\s*있|up\s*했|raise)|어떤\s*손이\s*(?:올라|들)", re.I)
POINTING = re.compile(r"\bwhat am i pointing (?:at|to)\b|\bwhere am i pointing\b|(?:내가|제가)?\s*(?:뭘|어디를?)\s*가리키", re.I)
WEARING = re.compile(r"\b(?:am i|do i have|i'?m) (?:wearing |got )?(?:a |an |any )?(glasses|sunglasses|hat|cap|mask|"
                     r"watch|earrings|necklace|scarf|tie|beard|moustache|mustache)\b|"
                     r"(안경|선글라스|모자|마스크|시계|목걸이|귀걸이|넥타이|수염)\s*(?:을|를)?\s*(?:썼|쓰고|꼈|끼고|했|하고|있|찼|차고|기르)",
                     re.I)

FAR_ME = re.compile(r"\bhow far (?:am i|are you from me|away am i)\b|(?:나|저)(?:랑|와|하고|는|한테서)?\s*얼마나|"
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
ABOUT_LUMI = re.compile(r"(?:루미|너|니가|네가|당신)(?:는|은|가|도)?\s|^\W*넌|\bare you\b|\byou(?:'re| are) wearing\b", re.I)
ONE = re.compile(r"(?P<col>" + "|".join(COLOURS) + r")\w*\s*(?:ones?|거|것|걸)?", re.I)   # "the blue one", "파란 거"
UP_ASKED = re.compile(r"\bup\b|\braised?\b|\braising\b|올라|올렸|손\s*(?:을\s*)?들(?:고|었)", re.I)
HELD_ASKED = re.compile(r"\bhold|\bhave it\b|\bin my\b|\bit\b|들고|쥐고|잡고|있(?:어|습|나|니)|들었게", re.I)
SEE_KINDS = ("see", "there", "still", "see_ko", "see_more", "where", "far", "it")
TAIL = re.compile(r"(?:[\s,]+(?:too|then|also|exactly|again|please|what colou?rs?(?: (?:are|is) (?:they|it))?))+\W*$|"
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
AGAIN = re.compile(_LEAD + r"(?:(?:what|how) about |(?:where(?:'s| is)? (?:it|that|they)|which hand(?: is it)?|"
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
NOT_A_HAND = re.compile(r"\b(?:that'?s|that is|you'?re|you are|all|is that|is it) right\b|\bright (?:now|away|here|there)\b",
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


EMPTY_HANDS = ("I don't see anything I can recognise in your hands{}. Small things like a watch, a ring or a pen "
               "I can't make out.", "{}손에 제가 알아볼 수 있는 건 없어요. 시계, 반지, 펜 같은 작은 건 제 카메라로는 알아보기 어려워요.")
NO_CAMERA = ("My cameras aren't giving me a picture right now, so I can't tell.", "지금은 카메라 화면이 없어서 잘 모르겠어요.")


def _seen_answer(name, colour, frames, lang):
    _last["name"] = name
    if name == "person":
        n = len(scene.people(frames))
        return _say(f"Yes, I see {_n(n)} {'person' if n == 1 else 'people'}." if n else "No, I don't see anyone right now.",
                    f"네, 사람 {n}명이 보여요." if n else "아니요, 지금은 아무도 안 보여요.", lang)
    hits = _sees(name, colour, frames)
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


def _held_answer(frames, lang, side=None):
    """What the person holds; side ("left" / "right", the person's own): only what is in that hand."""
    p = scene.person_in_front(frames)
    if p is None:
        return _say("I can't see you well enough to tell. Could you step in front of me?",
                    "잘 안 보여서 모르겠어요. 제 앞으로 와 주시겠어요?", lang)
    if side:
        return _hand_answer(p, side, lang)
    o = scene.object_in_hand(frames)
    if o:
        _last["hand"] = o["hand"]
        hand = {"left": ("left", "왼"), "right": ("right", "오른")}[o["hand"]]
        return _say(f"You're holding {_a(o['name'], o['colour'])} in your {hand[0]} hand.",
                    f"{hand[1]}손에 {COLOUR_KO[o['colour']] + ' ' if o['colour'] in COLOUR_KO else ''}"
                    f"{_j(_ko_name(o['name']), '을', '를')} 들고 계세요.", lang)
    if scene.person_holds(None, frames) is False:
        return _empty_hands(lang)
    return _say("I can't see your hands well enough to tell.", "손이 잘 안 보여서 모르겠어요.", lang)


def _hand_answer(p, side, lang):
    """The one hand asked about ("what about my left hand?"), never the other hand's thing: what is in it, that it is
    up with nothing seen in it, or that nothing known is in it."""
    _last["hand"] = side
    h, k = p["hands"].get(side), {"left": "왼", "right": "오른"}[side]
    o = h and h["object"]
    if o:
        return _say(f"In your {side} hand I see {_a(o['name'], o['colour'])}.",
                    f"{k}손에 {COLOUR_KO[o['colour']] + ' ' if o['colour'] in COLOUR_KO else ''}"
                    f"{_j(_ko_name(o['name']), '이', '가')} 보여요.", lang)
    if side in p["raised"]:
        return _say(f"Your {side} hand is up and I don't see anything in it.",
                    f"{k}손을 들고 계신데, 그 손에는 든 게 안 보여요.", lang)
    if h is None:
        return _say(f"I can't see your {side} hand well enough to tell.", f"{k}손이 잘 안 보여서 모르겠어요.", lang)
    return _say(f"I don't see anything I can recognise in your {side} hand.",
                f"{k}손에는 제가 알아볼 수 있는 게 안 보여요.", lang)


def _asked_hand(t):
    """The hand a question is about: "what's in my left hand?", "왼손은?", "and the other one?" (not the one just told)."""
    return _side(t) or (OTHER_HAND.search(t) and {"left": "right", "right": "left"}.get(_last["hand"])) or None


def _empty_hands(lang, now=False):
    """Nothing the detector knows in the hands: said plainly, with what it can't see (a watch has no class)."""
    return _say(EMPTY_HANDS[0].format(" now" if now else ""), EMPTY_HANDS[1].format("지금은 " if now else ""), lang)


NOUN = {"upper": ("top", "상의"), "lower": ("trousers", "바지"), "feet": ("shoes", "신발")}


def _clothes_answer(p, text, lang):
    """The colour of each piece asked about (all three for "what am I wearing?"), in the asker's own word ("your
    jeans look blue"); a piece out of the picture is said to be out of view, never guessed."""
    asked = []                                             # (part, noun) in the order said
    for part, rx in PARTS:
        m = re.search(rx, text, re.I)
        if m:
            w = m.group(0).lower()
            if bool(re.match(r"[a-z]", w)) != (lang == "en") or w in ("feet", "foot") or w[0] == "신" and w != "신발":
                w = NOUN[part][lang != "en"]
            w = {"genes": "jeans", "jean": "jeans", "short": "shirt", "trouser": "trousers", "청바진": "청바지", "청 바지": "청바지"}.get(w, w)
            asked.append((m.start(), part, re.sub(r"^te[ea] ?shirt|^t ?shirt", "t-shirt", w)))
    asked = [(part, w) for _, part, w in sorted(asked)] or [(part, NOUN[part][lang != "en"]) for part in NOUN]
    seen = [(part, w, p["clothes"].get(part)) for part, w in asked]
    _last["parts"] = seen
    if len(seen) == 1:
        part, w, c = seen[0]
        if c is None:
            return _say(f"I can't see your {w} from here.", f"여기서는 {_j(w, '이', '가')} 안 보여요.", lang)
        return _say(f"Your {w} {'look' if w.endswith('s') else 'looks'} {c}.",
                    f"{_j(w, '은', '는')} {COLOUR_KO.get(c, c)}으로 보여요.", lang)
    shown = [(part, w, c) for part, w, c in seen if c]
    hidden = [w for _, w, c in seen if not c]
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


def _doing_answer(p, frames, lang):
    o = scene.object_in_hand(frames)
    en, ko = [f"You're standing{_m(p['distance_m'], 'en')} {p['where']}"], [f"제 {_where_ko(p['where'])}에 서 계시고"]
    if p["facing"] is True:
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
    return _say(", ".join(en) + ".", " ".join(ko).rstrip("고").rstrip("시") + "세요.", lang)


UP_ASKED = re.compile(r"\bup\b|\braised?\b|\braising\b|올라|올렸|손\s*(?:을\s*)?들(?:고|었)", re.I)
HELD_ASKED = re.compile(r"\bhold|\bhave it\b|\bin my\b|\bit\b|들고|쥐고|잡고|있(?:어|습|나|니)|들었게", re.I)


KINDS = (("wearing", WEARING), ("holding", HOLDING), ("shirt", SHIRT), ("raised", RAISED), ("where", WHERE_THING), ("hand", WHICH_HAND),
         ("pointing", POINTING), ("doing", DOING), ("friend", FRIEND), ("see_me", SEE_ME), ("how_many", HOW_MANY), ("behind", BEHIND),
         ("far", HOW_FAR), ("see", SEE_THING), ("there", THERE_IS), ("still", STILL_THERE), ("see_ko", SEE_THING_KO),
         ("see_more", SEE_MORE), ("what_see", WHAT_SEE))


def answer(text, lang="en", frames=None, slow_line=None):
    """The spoken answer when `text` asks about what Lumi sees, else None. frames: scene.load(...) for tests.
    slow_line(sentence): said before a slow VLM look ("Let me look.")."""
    t = text.strip()
    asked_at = time.time()                                 # the answer comes from frames taken after this
    last = _last["kind"]
    own = next((k for k, rx in KINDS if rx.search(t)), None)   # a whole question of its own is answered as asked
    if last and _last["asked"] and own is None:
        got = _check(t, lang, frames, asked_at, slow_line)   # "really?", "and now?", "it's white": a new look
        if got:
            _last["at"] = time.time()
            return got
    if brain.is_backchannel(t) and not BYE.search(t):      # "nice!" between keeps the thread: "and my jeans?"
        return None
    if last and own is None and (HEAD.search(t) or PRAISE.search(t)):
        return None                                        # "look up" / "nice!" between: "and now?" still asks again
    _last["kind"] = None                                   # a follow-up goes only with the turn right before
    if ORDER.search(DONE.sub(" ", LOOK_SAID.sub(" ", t))) and not PUT_ON.search(t):
        return None                                        # "find the red cup and bring it": a fetch, not a question
    kind = own
    if kind == "shirt" and ABOUT_LUMI.search(t):
        return None                                        # "루미는 무슨 옷 입었어?": about Lumi, not the visitor
    if kind is None and last in SEE_KINDS and _last["thing"] and not ABOUT_LUMI.search(t) and \
            (IT_WHERE.search(t) or IT_COLOUR.search(t) or IT_SIZE.search(t) or IT_COUNT.search(t)):
        kind = "it"                                        # "where is it?", "무슨 색이야?" about the thing just seen
    if kind is None and last:
        kind, t = _follow_up(t, last)
    if kind is None or kind == "how_many" and NOT_IN_VIEW.search(t) or \
            kind == "where" and _thing(WHERE_THING.search(t))[0] in BIG:
        return None                                        # "where is the toilet?": the way there, not the cameras
    if kind == "far" and not (FAR_THING.search(t) or SEE_THING_KO.search(t)):
        if FAR_ME.search(t):
            kind = "far_me"
        elif _last["thing"] is None or last not in SEE_KINDS or re.search(r"\bit\s+(?:to|from)\b", t, re.I) or \
                not (IT.search(t) or FAR_BARE.match(t)):
            return None                                    # "how far is Seoul?": not about the cameras
    _last["kind"], _last["asked"], _last["at"] = kind, (kind, t), time.time()
    frames = _look(frames, asked_at)
    if not frames:
        return _say(*NO_CAMERA, lang)
    return _reply(kind, t, frames, lang, slow_line)


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


def _check(t, lang, frames, since, slow_line):
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
        return _held_answer(frames, lang, side) if frames else _say(*NO_CAMERA, lang)
    said, denied = _colours(t) if short and kind in ("shirt", "holding", "hand") else (None, set())
    named = _said_thing(t) if short and kind in ("holding", "hand") and not hand else None
    count = _said_count(t) if short and kind == "how_many" else None
    again = again or WRONG.search(t) and short and len(t.split()) > 1 and _follow_up(t, kind)[0] is None
    if not (hand or said or denied or again or named or count):
        return None
    frames = _look(frames, since)
    _last["kind"] = kind                                   # the thread goes on: "and now?" again
    if not frames:
        return _say(*NO_CAMERA, lang)
    if count:                                              # "no, there are four of us": counted again
        n = len(scene.people(frames))
        if n == count:
            return _say(f"Yes, I see {_n(n)} {'person' if n == 1 else 'people'}.", f"네, {n}명이 보여요.", lang)
        return _say(f"I count {_n(n)} {'person' if n == 1 else 'people'} in view now, not {count}; someone may be out of "
                    f"my view.", f"제 카메라에는 지금 {n}명이 보여요. 화면 밖에 계신 분이 있을 수도 있어요.", lang)
    if not (hand or said or denied or named):
        got = _reply(kind, asked, frames, lang, slow_line)
        return got and _say("I looked again. ", "다시 봤어요. ", lang) + got
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
        return _empty_hands(lang, now=True)
    if named:                                              # "nope, this is a book": checked, not agreed
        if o["name"] == named:
            return _say(f"Yes, I see {_a(o['name'], o['colour'])} in your hand.",
                        f"네, 손에 {_j(_ko_name(o['name']), '이', '가')} 보여요.", lang)
        return _say(f"To my camera it looks like {_a(o['name'])}, not {_a(named)}, but I may be wrong.",
                    f"제 카메라에는 {_j(_ko_name(named), '이', '가')} 아니라 {_ko_name(o['name'])}(으)로 보여요. 틀릴 수도 있어요.", lang)
    return _verdict(o["colour"], said, denied, f"the {o['name']}", _ko_name(o["name"]), "looks", lang)


def _reply(kind, t, frames, lang, slow_line=None):
    """The answer to a question of this kind (answer() read it) from these frames."""
    if kind == "behind":
        return _say("My cameras look forward, so I can't see what's behind me. " + describe(frames, "en"),
                    "제 카메라는 앞만 보여서 뒤는 볼 수 없어요. " + describe(frames, "ko"), lang)
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
    if kind == "holding":
        return _held_answer(frames, lang, _asked_hand(t))
    p = scene.person_in_front(frames)
    if kind == "friend":                                   # "do you still see my friend?": anyone besides them
        n = len(scene.people(frames)) - (p is not None)
        if n > 0:
            return _say(f"Yes, I see {_n(n)} other {'person' if n == 1 else 'people'} besides you.",
                        f"네, 다른 사람 {n}명이 더 보여요.", lang)
        return _say("No, I only see you now." if p else "No, I don't see anyone right now.",
                    "아니요, 지금은 한 분만 보여요." if p else "아니요, 지금은 아무도 안 보여요.", lang)
    if kind == "shirt" and OTHER.search(t):                # "what is my friend wearing?", "옆 사람 셔츠는 무슨 색이에요?"
        q = scene.other_person(frames)
        if q is None:
            return _say("I only see you right now.", "지금은 한 분만 보여요.", lang)
        said = _clothes_answer(q, t, lang)
        return re.sub(r"\bYou're\b", "They're", re.sub(r"\b([Yy])our\b", lambda m: "Their" if m.group(1) == "Y" else "their", said))
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
    if kind == "shirt":
        return _clothes_answer(p, t, lang)
    if kind == "hand":                                     # "which hand?": the one holding something, else one raised
        up = UP_ASKED.search(t)                            # "left or right, which one's up?"
        if not up and (HELD_ASKED.search(t) or scene.object_in_hand(frames) or not p["raised"]):
            return _held_answer(frames, lang)
        kind = "raised"
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
    if kind == "doing":
        return _doing_answer(p, frames, lang)
    if kind == "wearing":                                  # detections can't tell: ask the picture (slow)
        if slow_line:
            slow_line(_say("Let me look.", "잠깐 볼게요.", lang))
        said = scene.ask_vlm(t, lang, frames)
        return said or _say("Sorry, I can't tell.", "죄송해요, 잘 모르겠어요.", lang)
    return None


RECHECK_S = 30.0                 # s; a one-word "really?" this soon after a seeing answer is a new look, also said
                                 # while Lumi still talks


def recheck(text):
    """"Really?", "진짜?", "Now?" right after a seeing answer: worth interrupting Lumi for (a new look), though one word."""
    return bool(_last["kind"] and time.time() - _last["at"] < RECHECK_S and AGAIN.search(text.strip()))


ABOUT_VIEW = re.compile(r"\b(?:see|seeing|look(?:ing)? at|camera|cameras|in front of you|around you|holding|wearing|"
                        r"colou?r)\b|보여|보이|보고|카메라|들고|입고|무슨 색", re.I)


def warm_up():
    """Load the pose and object models now, so the first question is answered in ~0.1 s, not ~1 s."""
    try:
        pose.load()
        scene._box_net()
    except Exception as e:
        print(f"seeing: models not loaded ({e})", flush=True)


def facts_for(text):
    """" " + facts() for words about what Lumi sees that answer() did not take, and for anything said soon after a
    seeing answer, else "" (the model then answers from what the cameras see now, not from what it said before)."""
    recent = time.time() - _last["at"] < THREAD_S
    return " " + facts() if ABOUT_VIEW.search(text) or recent else ""


def facts(frames=None):
    """One line of what the cameras see now, for the conversation model's prompt ("" when nothing / no camera)."""
    try:
        frames = _look(frames, time.time())
        if not frames:
            return ""
        line = describe(frames, "en")
        p = scene.person_in_front(frames)
        if p:
            o = scene.object_in_hand(frames)
            line += f" The person in front is{_m(p['distance_m'], 'en')}" + \
                (", wearing " + ", ".join(f"{c} {NOUN[k][0]}" for k, c in p["clothes"].items() if c)
                 if any(p["clothes"].values()) else "") + \
                (f", holding {_a(o['name'], o['colour'])}" if o else "") + "."
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
