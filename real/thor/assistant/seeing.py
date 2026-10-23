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

NEAR_SAY = 4                     # at most this many kinds of things named in "what do you see"
DESCRIBE_SCORE = 0.3             # weaker boxes (depth-checked cups) count for "do you see a cup", not in the list
THREAD_S = 60.0                  # s; this long after a seeing answer the conversation model gets a new look too
CLAIM_WORDS = 14                 # words; a correction is short: "no, it's my right hand", "아니야 흰색이야"
BIG = {"dining table", "chair", "couch", "bed", "refrigerator", "sink", "oven", "tv", "toilet", "bench"}   # not "on a table"

COLOURS = {"white": "white", "red": "red", "blue": "blue", "green": "green", "yellow": "yellow", "black": "black",
           "orange": "orange", "grey": "grey", "gray": "grey", "purple": "purple", "pink": "pink",
           "brown": "brown",
           "흰": "white", "하얀": "white", "빨간": "red", "파란": "blue", "초록": "green", "노란": "yellow", "검은": "black",
           "까만": "black", "주황": "orange", "회색": "grey", "보라": "purple", "분홍": "pink", "핑크": "pink",
           "하양": "white", "빨강": "red", "파랑": "blue", "노랑": "yellow", "검정": "black", "까망": "black", "갈색": "brown",
           "브라운": "brown"}   # "brown" is only said by people: the camera names browns orange
COLOUR_KO = {"white": "흰색", "red": "빨간색", "blue": "파란색", "green": "초록색", "yellow": "노란색", "black": "검은색",
             "orange": "주황색", "grey": "회색", "purple": "보라색", "pink": "분홍색", "brown": "갈색"}
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
      "backpack": "배낭", "umbrella": "우산", "handbag": "가방", "tie": "넥타이", "suitcase": "여행 가방",
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
            "식탁": "dining table", "컴퓨터": "laptop", "티비": "tv", "가방": "handbag"}

_EN_NAMES = sorted(set(objects.COCO) | set(SYNONYMS), key=len, reverse=True)
_THING_EN = r"(?:(?P<col>" + "|".join(c for c in COLOURS if c.isascii()) + r")\s+)?(?P<obj>" + \
    "|".join(re.escape(n) for n in _EN_NAMES) + r")(?:e?s)?\b"
_THING_KO = r"(?:(?P<col>" + "|".join(c for c in COLOURS if not c.isascii()) + r")\w*\s*)?(?P<obj>" + \
    "|".join(sorted(KO_WORDS, key=len, reverse=True)) + r")"

SEE_ME = re.compile(r"\b(do|can) you see me\b|\bam i (visible|in (your )?view)\b|(나|저)(를|)? ?보여|(나|저) ?보이", re.I)
SEE_THING = re.compile(r"(?<!what )\b(?:do|can|could) you (?:still )?(?:see|spot|notice)\b.*?\b(?:a|an|the|any|some|my)?\s*" + _THING_EN, re.I)
THERE_IS = re.compile(r"\b(?:is|are) there (?:still )?(?:a|an|any|some)\s+" + _THING_EN +
                      r"(?! (?:open|close|nearby|near here|around here))", re.I)
STILL_THERE = re.compile(r"\bis (?:the|my|that|your|this) " + _THING_EN + r" still (?:there|here|on|in)\b", re.I)
SEE_THING_KO = re.compile(_THING_KO + r"(?:이|가|은|는|을|를|도)?\s*(?:(?:(?:아직도?|지금도?|still)\s*)?(?:보여|보이)|아직도?\s*있)")
                                 # "사과 아직 보여요?", "컵이 아직 있습니까?"
HOW_FAR = re.compile(r"\bhow far\b|\bhow (?:near|close)\b|\bwhat(?:'s| is) the distance\b|얼마나 ?(?:멀|떨어|가까)|거리가?|(?:거기|그거|저거|걔)까지\s*얼마나",
                     re.I)
HOW_FAR_THING = re.compile(r"\b(?:how far|how (?:near|close)).*?\b(?:the|that|this|a|an)\s+" + _THING_EN, re.I)
WHAT_SEE = re.compile(r"\bwhat (?:do|can) you see\b|\bwhat(?:'s| is| are)? (?:there )?in front of you\b|"
                      r"\bwhat(?:'s| is) (?:(?:still|now) )?(?:on|at) the (?:table|desk|테이블)|\bwhat(?:'s| is) (?:around|near) you\b|"
                      r"\bdescribe what you see\b|\bwhat are you (?:looking at|seeing)\b|\btell me what you see\b|"
                      r"뭐가 ?보여|무엇이 ?보여|뭐 ?보여|뭐가 ?보이|앞에 ?(?:뭐|무엇)|(?:테이블|table) ?(?:위에|에|위) ?(?:뭐|무엇)|"
                      r"뭘 ?보고 ?있", re.I)
BEHIND = re.compile(r"\bwhat(?:'s| is) behind you\b|^(?!.*\b(?:look|turn|check)\b).*\bbehind you\b.*\?|"   # not "can you look
                    r"뒤에 ?(?:뭐|무엇|누가|누구)", re.I)                                             # behind you?" (a head turn)
HOW_MANY = re.compile(r"\bhow many (?:people|persons|visitors|humans)\b|\bhow many of us\b|몇 ?(?:명|사람)|"
                      r"^\W*(?:(?:and|so|okay)\W+)?(?:(?:지금|이제|now)\s*(?:은|는)?\s*how many|how many(?: do you see| are there)? now)\W*$",
                      re.I)   # "How many now?"
NOT_IN_VIEW = re.compile(r"\b(?:work|works|working|employ\w*|staff|company|companies|campy|firm|cutshion|country|city|"
                         r"live|lives|living|world|team|office|branch|developers?|engineers?|built|made)\b|"
                         r"직원|회사|쿳션|일하|일해|근무|나라|국가|도시|살아|사는|인구|팀|지사|만든|만들|개발자|엔지니어",
                         re.I)   # "how many people work at Cutshion?": the company, not the cameras
HOLDING = re.compile(r"\bwhat(?:'s| is| am| do)? (?:i|is in my hands?|in my hands?)\b.*?\b(?:holding|carrying|have)\b|"
                     r"\bwhat(?:'s| is)(?: it| this| that)? in my hands?\b|\bwhat(?:'s| is) my hands?\?|\bwhat (?:do )?i have in my hands?\b|\bam i holding\b|"
                     r"\bis there (?:something|anything) in my hand\b|\bwhat is this\b(?=.*\bhand\b)|\bwhat am i hold in\b|\banything in my hands?\b|"
                     r"(?:내가|제가|나|저)\s*(?:뭐|뭘|무엇을?)\s*(?:들고|잡고|쥐고|holding)|(?:내|제)\s*(?:손|hand)에\s*(?:뭐|뭔|무엇|든|있)|"
                     r"(?:내가|제가)\s*(?:든|들고\s*있는|쥐고\s*있는)\s*(?:거|게|것)", re.I)   # "제가 들고 있는 거 뭐예요?"
                                 # "뭐 들고 있어?" without "내가" asks about Lumi's own hand (lumi.status_question)
WHICH_HAND = re.compile(r"\b(?:which|what) hand(?![a-z])|\bleft or right\b|어느\s*(?:쪽\s*)?(?:손|hand)|손\s*어느\s*쪽|"
                        r"왼손\S*\s*(?:아니면\s*)?오른손\S*\s*\?|left\S*\s*right\S*\s*\?", re.I)   # held first, else raised
_UPPER = r"short|t-? ?shirts?|te[ea] ?shirts?|shirts?|tops?|jackets?|sweaters?|sweatshirts?|hoodies?|jumpers?|blouses?|coats?"
_LOWER = r"pants|trousers?|jeans?|genes|skirts?|shorts|slacks|leggings|bottoms"   # "genes", "jean": heard for jeans
_FEET = r"shoes?|sneakers?|trainers|boots?|sandals?|slippers?|socks?|feet|foot"
_UPPER_KO = r"티셔츠|셔츠|셔쯔|상의|윗옷|겉옷|재킷|자켓|후드티|맨투맨|니트|스웨터|코트"
_LOWER_KO = r"청 ?바지|청바진|반바지|바지|하의|치마|스커트"
_FEET_KO = r"운동화|신발|구두"
_ITEM = rf"(?:{_UPPER}|{_LOWER}|{_FEET}|clothes|clothing|outfit)"
_ITEM_KO = rf"(?:{_UPPER_KO}|{_LOWER_KO}|{_FEET_KO}|옷)"
PARTS = (("upper", rf"\b(?:{_UPPER})\b|{_UPPER_KO}"), ("lower", rf"\b(?:{_LOWER})\b|{_LOWER_KO}|아래(?:쪽)?|밑"),
         ("feet", rf"\b(?:{_FEET})\b|{_FEET_KO}|신었|신고 있|신은"))
SHIRT = re.compile(rf"\bcolou?rs?\b.{{0,30}}?\b(?:my|the|his|her|their)\s+(?:\w+\s+)?{_ITEM}\b|{_ITEM}\W+what colou?r|\bmy\s+(?:\w+\s+)?{_ITEM}(?:'s)?\s+colou?r|"
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
                   r"(?:입었|벗었|바꿨|갈아입)\S*\W+.{0,12}(?:무슨\s*색|colou?r|컬러)|\b(?:" + _UPPER + "|" + _LOWER + r")\s*(?:색|컬러)", re.I)   # 2026-10-21 live:
                                 # "What is the color of my t-shirt?", "What is it? Color my jeans." went to the LLM
OTHER = re.compile(r"\b(?:friend|colleague|partner|she|he|his|her|their)\b|\bthe (?:other|second) (?:person|guy|man|woman|one)\b|"
                   r"\b(?:person|man|woman|guy|lady) (?:next to|beside|behind|with) me\b|친구|동료|옆\s*(?:에\s*)?(?:있는\s*)?(?:사람|분)|"
                   r"다른\s*(?:사람|분)|그\s*(?:사람|분)", re.I)   # someone else than the person talking
FRIEND = re.compile(r"\b(?:do|can) you (?:still )?see (?:my (?:friend|colleague)|the other (?:person|guy|man|woman))\b|"
                    r"\bis (?:my (?:friend|colleague)|the other (?:person|guy|man|woman)) still (?:here|there|in view)\b|"
                    r"(?:친구|동료|그\s*사람|다른\s*(?:사람|분)|옆\s*사람)\S*\s*(?:아직도?\s*|still\s*)?(?:보여|보이|있어|있나|있습)", re.I)
DOING = re.compile(r"\bwhat am i doing\b|\bwhat(?:'m| am) i up to\b|(?:내가|제가|나|저)\s*(?:지금\s*)?(?:뭐|뭘|무엇을?)\s*하고\s*있", re.I)
RAISED = re.compile(r"\b(?:is|are) my (?:hand|hands|arm|arms) (?:raised|up)\b|\bam i raising (?:my )?(?:hand|arm)\b|"
                    r"\bdid i raise my hand\b|\bwhich hand (?:did i raise|is (?:up|raised)|am i (?:raising|holding up|lifting))\b|"
                    r"(?:내가|제가)?\s*손\s*(?:을\s*)?들었", re.I)
POINTING = re.compile(r"\bwhat am i pointing (?:at|to)\b|\bwhere am i pointing\b|(?:내가|제가)?\s*(?:뭘|어디를?)\s*가리키", re.I)
WEARING = re.compile(r"\b(?:am i|do i have|i'?m) (?:wearing |got )?(?:a |an |any )?(glasses|sunglasses|hat|cap|mask|"
                     r"watch|earrings|necklace|scarf|tie|beard|moustache|mustache)\b|"
                     r"(안경|선글라스|모자|마스크|시계|목걸이|귀걸이|넥타이|수염)\s*(?:을|를)?\s*(?:썼|쓰고|꼈|끼고|했|하고|있|찼|차고|기르)",
                     re.I)

FAR_ME = re.compile(r"\bhow far (?:am i|are you from me|away am i)\b|(?:나|저)(?:랑|와|하고|는|한테서)?\s*얼마나", re.I)
IT = re.compile(r"\b(?:it|that|this|they|them)\b|그거|그게|그건|저거|저게|저건|걔|거기", re.I)
ORDER = re.compile(r"\b(?:take|bring|pick|grab|get|put|place|give|fetch|carry|go|come|move|turn|look)\b|(?<!\bmy )(?<!\byour )\bhands?\b(?! (?:raised|up|down)\b)(?=\s+(?:me|it|this|that|the|her|him|them|over)\b)|"
                   r"가져|집어|잡아|놓아|놔|줘|갖다|가 ?줘|와 ?줘|돌아", re.I)
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
SEE_KINDS = ("see", "there", "still", "see_ko", "far", "it")
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
                   r"what(?:'s| is)? (?:it|that)|is it|right|just) )?(?:now|know)\b(?:,? lumi)?"
                   r"(?:\W+anything (?:new|else|different))?\W*$|\bone more time\b|"   # "and now?" ("and know?")
                   r"\b(?:look|check|see)\b.{0,15}\b(?:again|one more time)\b|\btake another look\b|"
                   r"\blook (?:closer|carefully|properly)\b|^\W*again\W*$|"
                   r"\bare you (?:sure|shore|certain|positive)\b|^\W*(?:\w+\W+){0,2}(?:really|seriously|for real)\W*$|"
                   r"^\W*(?:you(?:'re)?\s+)?(?:sure|positive|certain)\S{0,2}\s*\?|"
                   r"\bis (?:it|that|this) (?:really|right|true|correct|so)\b|\breally\b.{0,25}\?|"
                   r"^\W*(?:(?:그럼|근데|아니)\s*)?(?:(?:진짜|정말)\S{0,2}\s*)?(?:진짜|정말|확실|맞아|맞나|맞습니까|틀림없)\S{0,4}\s*\?|"
                   r"^\W*(?:진짜|정말)\S{0,3}\W*$|지금은|이제는|\bnow\s*(?:은|는)|^\W*(?:그럼\s*)?(?:지금|이제)\s*\??\W*$|"
                   r"(?:지금|이제)\S{0,2}\s*(?:어때|어떻|어떤가)|^\W*(?:지금|이제|now)\s+(?:손에\s*)?(?:뭐|뭘|무엇을?)\s*(?:들고|쥐고|있)|"
                   r"다시\s*(?:한\s*번\s*|한번\s*)?(?:봐|보|확인|check|체크)|자세히\s*(?:다시\s*)?봐|잘\s*봐|또\s*봐", re.I)
                                 # a new look at the same question: "are you sure?", "다시 한번 확인해 줄래요?"
PUT_ON = re.compile(r"\bi(?:'ve| have)? (?:just )?(?:put on|took off|taken off)\b", re.I)   # clothes, not an order
LIKED = re.compile(r"\bfavou?rite\b|\b(?:like|love)\b|좋아하", re.I)   # "is white your favourite colour?": not a check
NOT_A_HAND = re.compile(r"\b(?:that'?s|that is|you'?re|you are|all|is that|is it) right\b|\bright (?:now|away|here|there)\b",
                        re.I)
HAND_SAID = re.compile(r"(?P<n>\bnot (?:in )?(?:the |my |your )?|\bisn'?t (?:in )?(?:the |my |your )?)?\b(?P<s>left|right)\b"
                       r"(?=\s*(?:hand|one|side)(?![a-z])|\W*$)|(?P<k>왼|오른)\s*(?:손|쪽|편)\S{0,3}(?P<kn>\s*아니)?", re.I)
COLOUR_SAID = re.compile(r"(?P<n>\bnot (?:\w+ ){0,2}|n't (?:\w+ ){0,2})?\b(?P<c>" + "|".join(c for c in COLOURS if c.isascii()) +
                         r")\b|(?P<k>" + "|".join(c for c in COLOURS if not c.isascii()) + r")\w*(?P<kn>\s*아니)?", re.I)
_last = {"thing": None,          # the thing seen last: "how far is it?"
         "name": None,           # the kind of thing asked about last: "and the blue one?"
         "kind": None,           # the kind of the question just answered: "what about my jeans?" after the shirt
         "asked": None,          # (kind, words) of that question: "really?", "and now?" ask it again
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
    return (f" about {d:.1f} metres away" if d >= 1 else f" about {round(d * 100, -1):.0f} centimetres away") \
        if lang == "en" else (f" {d:.1f}미터쯤 떨어진" if d >= 1 else f" {round(d * 100, -1):.0f}센티미터쯤 떨어진")


def _where_ko(w):
    return {"on my left": "왼쪽", "on my right": "오른쪽", "in front of me": "앞"}.get(w, "")


def _say(en, ko, lang):
    return en if lang == "en" else ko


NO_CAMERA = ("My cameras aren't giving me a picture right now, so I can't tell.", "지금은 카메라 화면이 없어서 잘 모르겠어요.")


def _seen_answer(name, colour, frames, lang):
    _last["name"] = name
    if name == "person":
        n = len(scene.people(frames))
        return _say(f"Yes, I see {_n(n)} {'person' if n == 1 else 'people'}." if n else "No, I don't see anyone right now.",
                    f"네, 사람 {n}명이 보여요." if n else "아니요, 지금은 아무도 안 보여요.", lang)
    hits = scene.sees(name, colour, frames)
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
    other = scene.sees(name, None, frames) if colour else []
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
        n = len(scene.sees(name, None, frames))
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


def _held_answer(frames, lang):
    p = scene.person_in_front(frames)
    if p is None:
        return _say("I can't see you well enough to tell. Could you step in front of me?",
                    "잘 안 보여서 모르겠어요. 제 앞으로 와 주시겠어요?", lang)
    o = scene.object_in_hand(frames)
    if o:
        hand = {"left": ("left", "왼"), "right": ("right", "오른")}[o["hand"]]
        return _say(f"You're holding {_a(o['name'], o['colour'])} in your {hand[0]} hand.",
                    f"{hand[1]}손에 {COLOUR_KO[o['colour']] + ' ' if o['colour'] in COLOUR_KO else ''}"
                    f"{_j(_ko_name(o['name']), '을', '를')} 들고 계세요.", lang)
    if scene.person_holds(None, frames) is False:
        return _say("I don't see anything I can recognise in your hands.", "손에 제가 알아볼 수 있는 건 없어요.", lang)
    return _say("I can't see your hands well enough to tell.", "손이 잘 안 보여서 모르겠어요.", lang)


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


KINDS = (("wearing", WEARING), ("holding", HOLDING), ("shirt", SHIRT), ("raised", RAISED), ("hand", WHICH_HAND),
         ("pointing", POINTING), ("doing", DOING), ("friend", FRIEND), ("see_me", SEE_ME), ("how_many", HOW_MANY), ("behind", BEHIND),
         ("far", HOW_FAR), ("see", SEE_THING), ("there", THERE_IS), ("still", STILL_THERE), ("see_ko", SEE_THING_KO),
         ("what_see", WHAT_SEE))


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
    _last["kind"] = None                                   # a follow-up goes only with the turn right before
    if ORDER.search(t) and not PUT_ON.search(t):
        return None                                        # "find the red cup and bring it": a fetch, not a question
    kind = own
    if kind == "shirt" and ABOUT_LUMI.search(t):
        return None                                        # "루미는 무슨 옷 입었어?": about Lumi, not the visitor
    if kind is None and last in SEE_KINDS and _last["thing"] and not ABOUT_LUMI.search(t) and \
            (IT_WHERE.search(t) or IT_COLOUR.search(t) or IT_SIZE.search(t) or IT_COUNT.search(t)):
        kind = "it"                                        # "where is it?", "무슨 색이야?" about the thing just seen
    if kind is None and last:
        kind, t = _follow_up(t, last)
    if kind is None or kind == "how_many" and NOT_IN_VIEW.search(t):
        return None
    if kind == "far" and not (HOW_FAR_THING.search(t) or SEE_THING_KO.search(t)):
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


def _verdict(c, said, denied, en, ko, verb, lang, before=None):
    """A colour the person said (or denied) against the colour the camera sees now: agree only when it agrees.
    before: the colour said in the answer before."""
    if c is None:
        return _say(f"I can't see {en} well enough right now.", f"지금은 {_j(ko, '이', '가')} 잘 안 보여요.", lang)
    k = COLOUR_KO.get(c, c)
    if said == c or said is None and c not in denied:
        lead = ("Yes, " if said else "You're right, looking again ", "네, " if said else "맞아요, 다시 보니 ")
        return _say(f"{lead[0]}{en} {verb} {c}.", f"{lead[1]}{_j(ko, '은', '는')} {k}으로 보여요.", lang)
    if said and {said, c} <= objects.LIGHT:                # white in shade reads grey: both may be true
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
        not (ORDER.search(re.sub(r"\W+look\W*$", "", t)) and not again)   # "put it in my right hand"; "..., look"
    hand = _side(t) if short and kind in ("holding", "hand", "raised") else None
    said, denied = _colours(t) if short and kind in ("shirt", "holding", "hand") else (None, set())
    if not (hand or said or denied or again):
        return None
    frames = _look(frames, since)
    _last["kind"] = kind                                   # the thread goes on: "and now?" again
    if not frames:
        return _say(*NO_CAMERA, lang)
    if not (hand or said or denied):
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
                return _say("I don't see anything I can recognise in your hands now.", "지금은 손에 제가 알아볼 수 있는 건 없어요.", lang)
            return _say("I can't see your hands well enough to tell.", "손이 잘 안 보여서 모르겠어요.", lang)
        thing = (_a(o["name"], o["colour"]), _ko_name(o["name"]))
        if o["hand"] == hand:
            return _say(f"Yes, I see {thing[0]} in your {hand} hand.",
                        f"네, {side[hand]}손에 {_j(thing[1], '이', '가')} 보여요.", lang)
        return _say(f"I see {thing[0]} in your {o['hand']} hand, but I may be wrong.",
                    f"제 카메라에는 {side[o['hand']]}손에 {_j(thing[1], '이', '가')} 보여요. 틀릴 수도 있어요.", lang)
    if o is None:
        return _say("I don't see anything I can recognise in your hands now.", "지금은 손에 제가 알아볼 수 있는 건 없어요.", lang)
    return _verdict(o["colour"], said, denied, f"the {o['name']}", _ko_name(o["name"]), "looks", lang)


def _reply(kind, t, frames, lang, slow_line=None):
    """The answer to a question of this kind (answer() read it) from these frames."""
    if kind == "behind":
        return _say("My cameras look forward, so I can't see what's behind me. " + describe(frames, "en"),
                    "제 카메라는 앞만 보여서 뒤는 볼 수 없어요. " + describe(frames, "ko"), lang)
    if kind == "what_see":
        if re.search(r"table|desk|테이블", t, re.I):
            things = _listing(frames, lang, small_only=True)
            return _say(f"On the table I see {things}." if things else "I don't see anything on the table I can name.",
                        f"테이블 위에 {_j(things, '이', '가')} 보여요." if things else "테이블 위에 제가 알아볼 수 있는 건 없어요.", lang)
        return describe(frames, lang)
    if kind == "how_many":
        n = len(scene.people(frames))
        return _say(f"I see {_n(n)} {'person' if n == 1 else 'people'} right now." if n else "I don't see anyone right now.",
                    f"지금 {n}명이 보여요." if n else "지금은 아무도 안 보여요.", lang)
    if kind in ("see", "there", "still", "see_ko"):
        m = {"see": SEE_THING, "there": THERE_IS, "still": STILL_THERE, "see_ko": SEE_THING_KO}[kind].search(t)
        name, colour = _thing(m)
        if name is None:
            return None
        return _seen_answer(name, colour, frames, lang)
    if kind == "it":
        return _it_answer(t, frames, lang)
    if kind == "far":
        m = HOW_FAR_THING.search(t) or SEE_THING_KO.search(t)
        if m:
            name, colour = _thing(m)
            _last["name"] = name
            hits = scene.sees(name, colour, frames)
            if not hits:
                return _say(f"I don't see {_a(name, colour)} right now.", f"지금은 {_j(_ko_name(name), '이', '가')} 안 보여요.", lang)
            _last["thing"] = hits[0]
        name = _last["thing"]["name"]
        again = [h for h in scene.sees(name, None, frames) if h["camera"] == _last["thing"]["camera"]] or [_last["thing"]]
        d = min(again, key=lambda h: abs((h["bearing_deg"] or 0) - (_last["thing"]["bearing_deg"] or 0)))["distance_m"]
        if d is None:
            return _say("I can't measure how far it is.", "거리는 잴 수 없어요.", lang)
        return _say(f"The {name} is about {d:.1f} metres from me.", f"{_j(_ko_name(name), '은', '는')} 저한테서 {d:.1f}미터쯤 떨어져 있어요.", lang)
    if kind == "holding":
        return _held_answer(frames, lang)
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
        return _say(f"Yes, I can see you{_m(d, 'en')}.", f"네, 보여요.{' ' + f'{d:.1f}미터쯤 앞에 계세요.' if d else ''}", lang)
    if p is None:
        return _say("I can't see you well enough to tell. Could you step in front of me?",
                    "잘 안 보여서 모르겠어요. 제 앞으로 와 주시겠어요?", lang)
    if kind == "far_me":
        if p["distance_m"] is None:
            return _say("I can't measure how far you are.", "거리는 잴 수 없어요.", lang)
        return _say(f"You're about {p['distance_m']:.1f} metres from me.", f"저한테서 {p['distance_m']:.1f}미터쯤 떨어져 계세요.", lang)
    if kind == "shirt":
        return _clothes_answer(p, t, lang)
    if kind == "hand":                                     # "which hand?": the one holding something, else one raised
        if scene.object_in_hand(frames) or not p["raised"]:
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
