"""The first quick-answer kinds (name, age, maker, height, weight, battery, languages, AI model ...) asked at every
Korean speech level and in many English frames (assistant/quick_answers.py). Same meanings as the kinds' own
wordings in assistant/quick_answers.py and questions.py: no new facts, no new answers.

Korean: each kind's stems ("몸무게가 ", "몇 킬로") with the ending family of their last word, with or without a
subject (너, 루미, 이 로봇, 로봇님 ...). Levels: 반말, 해요체, 하십시오체, honorific (-세요 / -십니까 / -시나요),
friendly (-냐, -지), dialect (-노, -고, -여, -유, -교), short written forms (-임). English: frames with "you" and with
"lumi" / "this robot", plus Konglish mixes.
"""

KO_WHO = ["", "너 ", "니 ", "루미 ", "이 로봇 ", "로봇님 "]

# ending families: the question word or verb the stem ends on
WHAT = ["뭐야", "뭐예요", "뭐에요", "뭐니", "뭐냐", "뭡니까", "뭔가요", "뭐죠", "뭐고", "뭐여", "뭐임", "뭐예유", "뭔교", "뭔데", "뭐세요"]
MUCH = ["얼마야", "얼마예요", "얼마니", "얼마냐", "얼맙니까", "얼마입니까", "얼마인가요", "얼마죠", "얼마고", "얼마여", "얼마임", "얼마예유",
        "얼만교", "얼만데", "얼마세요"]
MANY = ["몇이야", "몇이에요", "몇이니", "몇이냐", "몇입니까", "몇인가요", "몇이죠", "몇이고", "몇이여", "몇임", "몇이에유", "몇인교", "몇인데",
        "몇이세요"]
HOW = ["어떻게 돼", "어떻게 돼요", "어떻게 되니", "어떻게 되냐", "어떻게 되나요", "어떻게 되세요", "어떻게 되십니까", "어떻게 됩니까",
       "어떻게 되시나요", "어떻게 되노", "우째 되노", "어떻게 돼유", "어떻게 되는데", "어떻게 되죠"]
COP = ["야", "예요", "니", "냐", "입니까", "인가요", "죠", "고", "여", "임", "예유", "인교", "인데", "세요"]   # after a vowel noun
COP_C = ["이야", "이에요", "이니", "이냐", "입니까", "인가요", "이죠", "이고", "이여", "임", "이에유", "인교", "인데", "이세요"]   # after a consonant
HAVE = ["있어", "있어요", "있니", "있냐", "있나요", "있습니까", "있으세요", "있으십니까", "있으신가요", "있나", "있노", "있어유", "있음", "있지"]
ABLE = ["수 있어", "수 있어요", "수 있니", "수 있냐", "수 있나요", "수 있습니까", "수 있으세요", "수 있으십니까", "수 있으신가요", "수 있나",
        "수 있노", "수 있어유", "수 있음", "줄 알아", "줄 알아요", "줄 아니", "줄 아세요", "줄 아십니까", "줄 압니까", "줄 아노"]


def ko(stems, ends, who=KO_WHO):
    return [w + s + e for w in who for s in stems for e in ends]


def en(frames, subjects=("you",)):
    return [f.format(s=s) for f in frames for s in subjects]


IT = ("lumi", "this robot", "the robot", "this thing")   # "how heavy is {s}"
YOU_IS = [("you", "are"), ("lumi", "is"), ("this robot", "is"), ("the robot", "is")]


def en_be(frames):
    """Frames with {s} and {be}: "how heavy {be} {s}" -> "how heavy are you", "how heavy is lumi"."""
    return [f.format(s=s, be=b) for f in frames for s, b in YOU_IS]


QUICK = {
    "name": ko(["이름이 ", "이름 ", "네임이 "], WHAT) + ko(["이름이 ", "성함이 "], HOW) +
            ko(["뭐라고 부르면 "], ["돼", "돼요", "되니", "되냐", "되나요", "됩니까", "될까요", "되노", "되겠습니까"], ["", "너 ", "로봇님 "]) +
            ["what's your name", "what is your name", "may i ask your name", "could you tell me your name", "your name please",
             "what's lumi's name", "what is this robot's name"] +
            ["what name do you go by", "what should we call you", "how should i call you", "what's the robot called", "what is this robot called",
             "is there a name for you", "what are you named", "your 이름 뭐야", "name이 뭐예요", "네 name 뭐야", "이름 what", "what's ur name"],
    "age": ko(["몇 살", "나이가 몇 살", "올해 몇 살"], COP_C) + ko(["나이가 ", "연세가 ", "연식이 "], HOW) +
           ko(["나이 ", "나이가 "], MANY) +
           ko(["언제 만들어졌", "언제 태어났", "만들어진 지 얼마나 됐", "태어난 지 얼마나 됐"],
              ["어", "어요", "니", "냐", "습니까", "나요", "어유", "노", "음", "지", "으세요", "으십니까"]) +
           en_be(["how old {be} {s}", "what age {be} {s}", "how many years old {be} {s}", "when {be} {s} made", "when {be} {s} built",
                  "when {be} {s} born"]) +
           ["how long have you existed", "how long have you been around", "what year were you made", "how old r u 루미", "너 age 몇이야"],
    "maker": ko(["누가 만들었", "누가 개발했", "누가 제작했"], ["어", "어요", "니", "냐", "습니까", "나요", "어유", "노", "음", "지", "으세요", "으십니까", "죠"]) +
             ko(["만든 사람이 누구", "만든 회사가 어디", "제조사가 어디", "개발사가 어디", "제작사가 어디"], COP) +
             ko(["어느 회사에서 만들었", "어디서 만들었", "어디서 개발했"], ["어", "어요", "니", "냐", "습니까", "나요", "노", "어유", "으세요"]) +
             en(["who made {s}", "who built {s}", "who created {s}", "who developed {s}", "which company made {s}", "who designed {s}",
                 "who manufactures {s}", "which company is behind {s}", "who is {s} made by"], ("you", "lumi", "this robot")) +
             ["who's behind you", "who are your makers", "누가 만들었어 you", "who made 너", "maker가 누구야", "제조사 where"],
    "height": ko(["키가 ", "키 ", "신장이 ", "높이가 "], MANY + MUCH) + ko(["키가 ", "신장이 "], HOW) +
              ko(["키 몇 센티", "키가 몇 센티미터", "몇 센티"], COP) +
              en_be(["how tall {be} {s}", "how high {be} {s}", "how many centimeters tall {be} {s}", "how many cm {be} {s}"]) +
              en(["what's {s} height", "what is {s} height", "{s} height?"], ["your", "lumi's", "the robot's"]) +
              ["너 height 몇이야", "키 몇 cm야"],
    "weight": ko(["몸무게가 ", "몸무게 ", "무게가 ", "무게 ", "체중이 "], MUCH + MANY) + ko(["무게가 ", "몸무게가 ", "체중이 "], HOW) +
              ko(["몇 킬로", "몇 키로", "몇 킬로그램", "몇 kg"], COP) +
              ko(["얼마나 무거"], ["워", "워요", "워유", "운가요", "우세요", "워?", "웁니까", "우십니까"], ["", "너 ", "루미 ", "이 로봇 "]) +
              ko(["무게 얼마나 나가"], ["", "요", "니", "나요", "세요", "십니까", "노", "유", "냐"], ["", "너 ", "루미 ", "이 로봇 "]) +
              en_be(["how heavy {be} {s}", "how many kilos {be} {s}", "how many kg {be} {s}", "how many pounds {be} {s}"]) +
              en(["how much do {s} weigh", "what do {s} weigh"], ["you"]) +
              en(["how much does {s} weigh", "what does {s} weigh", "what's the weight of {s}"], ("lumi", "this robot", "the robot")) +
              ["너 weight 얼마야", "몸무게 how much", "weight가 몇이에요", "몇 kg이에요 you"],
    "speed": ko(["속도가 ", "최고 속도가 ", "최대 속도가 ", "속력이 "], MUCH + MANY) + ko(["속도가 "], HOW) +
             ko(["얼마나 빨리 가", "얼마나 빨리 달려", "얼마나 빨리 움직여", "얼마나 빨라"], ["", "요", "니?", "유", "노", "요?"]) +
             ko(["얼마나 빨리 갈 ", "얼마나 빨리 달릴 "], ABLE[:13]) +
             en_be(["how fast {be} {s}", "how quick {be} {s}"]) +
             en(["how fast can {s} go", "how fast can {s} drive", "how fast can {s} move"], ("you", "lumi", "this robot")) +
             en(["what's {s} top speed", "what is {s} maximum speed", "what's {s} max speed"], ("your", "lumi's", "this robot's")) +
             ["max speed?", "top speed?", "speed 얼마야", "너 speed 몇이야", "how fast 가요", "최고 speed가 몇이에요"],
    "battery_life": ko(["배터리 얼마나 가", "배터리 얼마나 오래 가", "배터리 몇 시간 가", "한 번 충전하면 얼마나 가", "충전하면 몇 시간 가"],
                       ["", "요", "니", "냐", "나요", "요?", "노", "유", "죠"]) +
                    ko(["몇 시간 동안 일할 ", "몇 시간 움직일 ", "충전 없이 얼마나 일할 "], ABLE[:13]) +
                    ko(["배터리 지속 시간이 ", "배터리 사용 시간이 ", "배터리 수명이 하루에 "], MUCH + HOW[:8]) +
                    ["how long does your battery last", "how long can you run on one charge", "how many hours can you work",
                     "how long can you go without charging", "what's your battery life", "how long does lumi's battery last",
                     "how many hours can this robot run"] +
                    ["how long do you last", "how long until your battery runs out", "battery 몇 시간 가요", "battery life 얼마예요",
                     "배터리 how long 가", "한 번 charge하면 얼마나 가요"],
    "languages": ko(["영어 할 ", "한국어 할 ", "중국어 할 ", "일본어 할 ", "영어로 말할 ", "다른 언어 할 "], ABLE) +
                 ko(["무슨 언어 할 ", "몇 개 언어 할 ", "어떤 말 할 "], ["수 있어", "수 있어요", "수 있니", "수 있습니까", "수 있으세요", "줄 알아",
                                                              "줄 아세요", "줄 아십니까", "줄 아노"]) +
                 ko(["영어 ", "한국어 ", "중국어 ", "일본어 ", "스페인어 "], ["돼", "돼요", "되니", "되냐", "되나요", "됩니까", "되세요", "되노", "돼유"]) +
                 ko(["영어 ", "한국어 ", "일본어 "], ["알아", "알아요", "아니", "아세요", "아십니까", "압니까", "아나", "아노", "알아유", "하세요", "하십니까", "하시나요"]) +
                 [f.format(l=l) for f in ["can you speak {l}", "do you speak {l}", "do you understand {l}", "can you talk in {l}",
                                          "can we talk in {l}", "{l} okay?", "do you know {l}"]
                  for l in ["english", "korean", "chinese", "japanese", "spanish", "french", "german"]] +
                 ["english 돼요", "korean 할 줄 알아", "can you speak 영어", "한국말 할 줄 알아", "한국말 잘해요", "what languages 할 수 있어"],
    "model": ko(["무슨 AI ", "어떤 AI ", "어떤 모델 ", "무슨 언어 모델 ", "인공지능 ", "무슨 LLM "], ["써", "써요", "쓰니", "쓰냐", "쓰세요", "쓰십니까",
                                                                                 "씁니까", "쓰나요", "쓰노", "써유", "씀"]) +
             ko(["AI 모델이 ", "언어 모델이 ", "인공지능 모델이 ", "두뇌가 "], WHAT) +
             ["what ai do you use", "what model do you run", "which llm do you use", "what ai is your brain", "which ai model powers you",
              "what language model do you use"] +
             ["what model runs lumi", "what's inside your brain", "which ai is this robot using", "ai model 뭐 써요", "what ai 써",
              "llm 뭐야", "너 brain이 뭐야"],
    "chatgpt": ko(["챗GPT ", "챗지피티 ", "GPT ", "지피티 ", "오픈AI "], ["써", "써요", "쓰니", "쓰냐", "쓰세요", "쓰십니까", "씁니까", "쓰나요", "쓰노", "써유",
                                                         "기반이야", "기반이에요", "기반입니까", "기반이세요"]) +
               ko(["챗GPT", "챗지피티", "GPT"], COP, ["너 ", "루미 ", "이거 "]) +
               ["are you chatgpt inside", "is chatgpt running you", "do you run on chatgpt", "are you powered by gpt", "is this openai",
                "are you an openai robot", "do you use gpt-4", "chatgpt 써요", "너 gpt야"],
    "robot": ko(["사람", "진짜 로봇", "로봇", "인공지능"], COP_C, ["너 ", "루미 ", "당신 ", "이거 "]) + ko(["기계"], COP, ["너 ", "루미 ", "당신 ", "이거 "]) +
             ko(["살아 있", "감정 있", "마음 있", "느낌 있"], ["어", "어요", "니", "냐", "나요", "습니까", "으세요", "으십니까", "나", "노", "어유", "지"]) +
             ko(["누가 조종하는 ", "사람이 조종하는 ", "누가 원격으로 움직이는 "], ["거야", "거예요", "거니", "거냐", "겁니까", "건가요", "거죠", "기가", "거여"], ["", "너 ", "이 로봇 "]) +
             en_be(["{be} {s} a real robot", "{be} {s} a person", "{be} {s} alive", "{be} {s} human", "{be} {s} remote controlled"]) +
             ["is a person controlling you", "is somebody steering you", "are you real or fake", "do you feel anything", "너 real robot이야",
              "사람 inside 있어"],
    "how_are_you": ko(["잘 지냈", "잘 지내", "괜찮"], ["어", "어요", "니", "냐", "나요", "습니까", "으세요", "으십니까", "어유", "노", "지", "죠"], ["너 ", "루미 ", "로봇님 "]) +
                   ko(["기분 ", "기분이 ", "컨디션 ", "컨디션이 ", "오늘 기분 "], ["어때", "어때요", "어떠니", "어떠냐", "어떻습니까", "어떠세요", "어떠신가요",
                                                                   "어떻노", "어뗘", "어때유", "좋으세요"], ["", "너 ", "루미 "]) +
                   ["how are you today", "how are you feeling", "how's your day", "how's your day been", "how are things", "you doing okay",
                    "how you doing", "are you doing ok today", "how r u", "how are u", "how are you 루미야", "오늘 how are you"],
    "touch": ko(["만져도 ", "만져 봐도 "], ["돼", "돼요", "되니", "되냐", "되나요", "됩니까", "될까요", "되노", "돼유", "되죠"], ["", "로봇 ", "루미 ", "이 로봇 ", "너 "]) +
             ["is it alright to touch you", "can people touch the robot", "are kids allowed to touch you", "can my kid touch you",
              "is touching allowed", "touch 해도 돼요", "만져도 okay"],
    "country": ko(["어느 나라 ", "어디 나라 "], ["로봇이야", "로봇이에요", "로봇이니", "로봇입니까", "로봇인가요", "거야", "거예요", "제품이에요", "출신이야", "출신이에요",
                                           "출신입니까", "출신이세요"], ["", "너 ", "루미 ", "이 로봇 "]) +
               ko(["한국 로봇", "한국에서 만든 로봇", "국산", "중국 로봇"], COP_C, ["너 ", "루미 ", "이 로봇 "]) +
               ["made in korea?", "which country is this robot from", "korea에서 만들었어요"],
}
QUICK["no"] = [
    # the same words about other things or the visitor, and orders: not these kinds
    "내 이름이 뭐야", "제 이름이 뭐예요", "내 나이가 몇 살이야", "제 키가 몇이에요", "내 몸무게가 얼마야", "제 몸무게 몇 킬로예요",
    "엄마 이름이 뭐예요", "이 컵 무게가 얼마예요", "이 컵 몇 킬로야", "테이블 높이가 얼마예요", "책상 높이 몇이야", "자동차 속도가 얼마야",
    "핸드폰 배터리 얼마나 가요", "내 폰 배터리 몇 시간 가", "배터리 몇 퍼센트 남았어", "배터리 얼마나 남았어요", "충전 얼마나 걸려요",
    "속도 줄여", "속도 높여 줘", "천천히 가", "빨리 가", "더 빨리 와", "키 높여", "키 낮춰 줘", "영어로 말해 줘", "한국어로 대답해 주세요",
    "영어로 바꿔", "한국말로 해", "speak english please", "talk in korean", "answer in english", "switch to korean",
    "how fast is the ice cream robot", "how heavy is the cup", "how tall is the table", "how old is cutshion", "who made the barista robot",
    "what's my name", "how old am i", "how tall am i", "how heavy am i", "how are you so tall", "how are you so fast",
    "슬퍼", "나 기분 안 좋아", "기분 좋다", "나 오늘 기분 최고야", "how am i doing", "how was my day",
]

# night 4, round 2: the question said inside a polite frame ("키가 얼마인지 알려 주시겠어요?", "몇 살인지 여쭤봐도 될까요?"),
# 하게체 ("키가 얼마인가?", "누가 만들었는가?"), and broken English / slips ("what is name of you", "you how heavy?")
TOLD = ["알려 줘", "알려 줄래", "알려 주세요", "알려 주실래요", "알려 주시겠어요", "알려 주시겠습니까", "알려 주십시오", "여쭤봐도 될까요",
        "여쭤봐도 되겠습니까", "물어봐도 돼요", "말해 줄 수 있어", "말씀해 주시겠어요"]
for _kind, _stems, _hage, _en in [
    ("height", ["키가 얼마인지 ", "키가 몇 센티인지 ", "키가 얼마나 되는지 ", "키 몇인지 "], ["키가 얼마인가", "키가 얼마나 되는가", "키 몇인가"],
     ["you how tall", "how tall you are", "your height how much", "height of you", "you tall how much", "how tal are you", "how tall r you"]),
    ("weight", ["무게가 얼마인지 ", "몸무게가 얼마인지 ", "무게가 얼마나 되는지 ", "몸무게 얼마나 나가는지 "],
     ["무게가 얼마인가", "몸무게가 얼마나 되는가", "무게 얼마나 나가는가"],
     ["you how heavy", "how heavy you are", "your weight how much", "weight of you", "how heavi are you", "how hevy are you", "you weigh how much"]),
    ("age", ["몇 살인지 ", "나이가 몇 살인지 ", "나이가 어떻게 되는지 ", "나이가 어떻게 되시는지 "], ["몇 살인가", "나이가 몇인가", "나이가 몇 살인가"],
     ["you how old", "how old you are", "your age how much", "age of you", "you age is", "how ol are you", "what your age"]),
    ("name", ["이름이 뭔지 ", "이름이 무엇인지 ", "이름이 어떻게 되는지 ", "성함이 어떻게 되시는지 "], ["이름이 무엇인가", "이름이 뭔가", "자네 이름이 뭔가"],
     ["name of you", "you name what", "what name you", "your name is what", "what is you name?", "wat is your name", "you name is"]),
    ("maker", ["누가 만들었는지 ", "어느 회사가 만들었는지 ", "어느 회사에서 만드셨는지 ", "어디서 만들었는지 "], ["누가 만들었는가", "어느 회사가 만들었는가"],
     ["who make you", "you made by who", "you made by which company", "which company make you", "who maked you", "company of you which",
      "where you come from which company"]),
    ("speed", ["속도가 얼마나 되는지 ", "최고 속도가 얼마인지 ", "얼마나 빨리 가는지 "], ["속도가 얼마인가", "최고 속도가 얼마나 되는가"],
     ["you how fast", "how fast you go", "your speed how much", "speed of you", "how fsat are you", "how fast u move", "max speed of you"]),
    ("battery_life", ["배터리가 얼마나 가는지 ", "한 번 충전하면 얼마나 쓰는지 ", "사용 시간이 얼마인지 ", "배터리 몇 시간 가는지 "],
     ["배터리가 얼마나 가는가", "한 번 충전하면 얼마나 쓰는가"],
     ["battery how long", "your battery how long", "how long battery", "how many hour you run", "how long you run one charge", "batery how long"]),
    ("languages", ["무슨 언어를 하는지 ", "말할 수 있는 언어가 뭔지 ", "어떤 언어를 할 수 있는지 "], ["무슨 언어를 하는가", "할 수 있는 언어가 뭔가"],
     ["you speak which language", "what language you speak", "language of you", "you can english", "which languages u speak"]),
    ("model", ["무슨 AI 쓰는지 ", "어떤 인공지능이 들어 있는지 ", "AI 모델이 뭔지 "], ["무슨 AI를 쓰는가", "인공지능이 뭔가", "어떤 AI가 들어 있는가"],
     ["you use which ai", "your ai is what", "what ai you use", "ai of you", "which ai inside you"]),
    ("time_now", ["지금 몇 시인지 "], ["지금 몇 시인가", "몇 시인가"], ["now time what", "what time now", "time now?", "what time it is now"]),
    ("date_today", ["오늘 며칠인지 ", "오늘 날짜가 며칠인지 "], ["오늘 며칠인가", "오늘 날짜가 며칠인가"], ["today date what", "what date today", "date today?"]),
    ("date_today", ["오늘 무슨 요일인지 ", "오늘 요일이 뭔지 "], ["오늘 무슨 요일인가", "오늘 요일이 뭔가"], ["today what day", "what day today", "today which day"]),
]:
    QUICK.setdefault(_kind, []).extend([w + s + t for w in ["", "너 "] for s in _stems for t in TOLD] + _hage +
                                       ["너 " + h for h in _hage if not h.startswith("자네")] + _en)
QUICK["languages"] += ["랭귀지 뭐 할 수 있어요", "랭귀지 몇 개 해", "language 뭐 할 수 있어", "랭귀지 뭐 해요", "무슨 랭귀지 해요", "랭귀지 뭐 하노"]
QUICK.setdefault("computer", []).extend([
    "which chip is your brain", "what chip do you have", "what chip runs you", "which processor do you have", "what's the chip inside you",
    "두뇌 컴퓨터 뭐야", "두뇌 컴퓨터가 뭐예요", "너 두뇌 컴퓨터 뭔데", "무슨 칩 써요", "칩 뭐 들어 있어", "프로세서 뭐예요", "머리에 무슨 컴퓨터 있어요",
    "두뇌 칩이 뭐입니까", "컴퓨터 뭐 들어갔노"])
QUICK.setdefault("co_founded", []).extend([
    "company made which year", "company founded which year", "your company start which year", "회사 몇 년도에 생겼어", "회사 언제 생겼어요",
    "회사 설립 연도가 언제예요", "회사 몇 년에 세웠습니까"])
QUICK["battery_life"] += ["how long does a full charge last", "how long does one charge last", "how long do you last on a charge",
                          "how long does your battery last", "완충하면 얼마나 가", "완충하면 몇 시간 가요", "완충하면 얼마나 버팁니까"]
QUICK["robot"] += [w + e for w in ["누가 조종해", "누가 조종하노", "누가 움직여", "사람이 조종해"] for e in ["", "요", "유", "?"]][:12] + \
                  ["누가 조종합니까", "누가 조종하세요", "is someone driving you", "who is controlling you right now"]
QUICK.setdefault("arm_weight", []).extend(["팔 무게가 몇 킬로예요", "팔 무게 몇 kg이야", "팔 무게가 몇 kg입니까", "팔은 몇 kg 나가요", "how heavy is the arm",
                                          "how heavy is this arm", "how much does that arm weigh"])
QUICK.setdefault("co_hq", []).extend(["쿳션 회사 어디 있어", "쿳션 회사 어디 있노", "쿳션 회사 어디에 있어요", "쿳션 회사 위치가 어디예요",
                                      "where is cutshion located", "where's the company located"])
QUICK.setdefault("price", []).extend(["가격이 얼마야", "가격이 얼마예요", "가격이 얼맙니까", "가격이 얼마입니까", "가격 얼마노", "가격이 얼마여",
                                      "로봇 가격 얼마예요", "이거 가격 얼마야"])
QUICK["speed"] += ["빨리 달릴 수 있어", "빨리 달릴 수 있어요", "빨리 갈 수 있어", "빨리 갈 수 있습니까", "얼마나 빨리 달려", "can you go fast",
                   "can you drive fast", "are you fast", "can you run fast"]
QUICK.setdefault("obstacles", []).extend([
    "팔이 사람 치면 어떡해요", "팔에 사람이 맞으면 어떻게 돼요", "팔이 부딪히면 어떻게 돼", "what if your arm hits someone", "will your arm hit me",
    "is it safe to stand next to you", "are you safe around kids", "옆에 서 있어도 안전해",
    "가까이 가도 안전합니까", "애들 옆에 둬도 괜찮아요"])
