"""Questions about Lumi for assistant/quick_answers.py: more wordings of its kinds (QUICK), a few new kinds with
their answers (QUICK_KINDS) and more "no" wordings (things that sound alike but are not about Lumi itself).
English, Korean (반말 / 해요체 / 하십시오체, dialect, Konglish, whisper slips) and mixed. Every answer is a fact of
knowledge/lumi_about_en.md; keep them in step.
"""


def _ko(stems, ends):
    """Every stem with every ending: _ko(["이름이 뭐"], ["야", "예요"]) -> ["이름이 뭐야", "이름이 뭐예요"]."""
    return [s + e for s in stems for e in ends]


QUICK = {
    "name": [
        "what's your name again", "could you tell me your name", "what name do you go by", "what do people call you",
        "what are you named", "what is ur name", "whats your name robot", "robot what is your name", "your name is",
        "name?", "what's the name of this robot", "what's this robot called", "what is this robot called",
        "what do we call you", "how should i call you", "what should we call you", "do you have a name robot",
        "have you got a name", "tell me your name please", "can i know your name", "may i ask your name",
        "what's ur name", "wats ur name", "what your name", "what's you name", "what is you name", "whats yor name",
        "what's your nam", "lumi is that your name", "is your name lumi", "are you lumi", "is this lumi",
        "your name please robot", "hey robot what's your name", "name of the robot",
        "니 이름", "네 이름", "너 이름", "너의 이름은", "너 이름은 뭐야", "니 이름은 뭐니",
        "이름이 뭐니", "이름이 뭐냐", "이름이 뭐임", "이름이 뭐여", "이름 뭐임", "이름 머야", "이름 모야", "이름 뭐예요",
        "이름이 뭐에요", "이름이 무엇입니까", "이름이 무엇인가요", "이름이 어떻게 되세요", "이름이 어떻게 되니", "이름이 어떻게 돼",
        "이름이 어떻게 되십니까", "존함이 어떻게 되세요", "이름 좀 알려 줘", "이름 좀 알려 주세요", "이름 알려 줄래", "이름 말해 줘",
        "이름 말해 주세요", "이름 좀 가르쳐 줘", "이름을 알려 주시겠어요", "이름이 있어", "이름 있니", "이름이 있나요",
        "로봇 이름이 뭐야", "로봇 이름이 뭐예요", "이 로봇 이름 뭐야", "로봇아 이름이 뭐야", "로봇 이름 알려 주세요",
        "얘 이름이 뭐야", "얘는 이름이 뭐예요", "쟤 이름이 뭐야", "이 친구 이름이 뭐예요", "이 아이 이름은 뭐예요",
        "뭐라고 불러", "뭐라고 불러야 돼", "뭐라고 부르면 될까요", "어떻게 부르면 돼요", "널 뭐라고 부르면 돼",
        "이름이 뭐라꼬", "이름이 뭐꼬", "니 이름 뭐꼬", "이름이 뭐시여", "이름이 뭣이여", "이름이 뭐래요", "이름이 뭐라고요",
        "이름이 뭐라고", "니 이름이 뭐고", "니 이름 뭐라카노", "이름이 뭐당가", "이름이 뭐요",
        "루미가 네 이름이야", "네 이름이 루미야", "너 루미야", "루미 맞아요", "니가 루미야",
        "what's your 이름", "your name이 뭐야", "너 name이 뭐야", "네임이 뭐예요", "니 네임 뭐야", "name 알려 줘",
        "이름 what", "what is 너의 이름",
    ],
    "name_meaning": [
        "what does the name lumi mean", "why lumi", "why are you named lumi", "why is your name lumi",
        "where does your name come from", "how did you get your name", "who gave you your name", "who named you",
        "what's the meaning of lumi", "what is the meaning behind your name", "is lumi a word", "does lumi mean anything",
        "lumi means what", "what does lumi stand for", "where did the name lumi come from", "why did they call you lumi",
        "루미 뜻이 뭐예요", "루미는 무슨 뜻이야", "루미가 무슨 의미예요", "루미 의미가 뭐야", "이름 뜻이 뭐야", "이름 뜻이 뭐예요",
        "이름에 무슨 뜻이 있어요", "이름이 무슨 의미예요", "왜 루미라고 지었어요", "왜 이름이 루미야", "루미라는 이름은 왜 지었어요",
        "이름은 누가 지었어", "이름은 누가 지어 줬어요", "이름 누가 지어 줬어", "루미는 무슨 말이에요", "루미 어디서 나온 이름이야",
        "루미가 뭔 뜻이고", "루미 뜻이 뭐꼬", "루미 meaning이 뭐야", "lumi 무슨 뜻이야", "루미 무슨 뜻",
    ],
    "who": [
        "who are you exactly", "who are you robot", "and who are you", "tell me who you are", "say who you are",
        "can you introduce yourself", "could you introduce yourself", "please introduce yourself", "introduce yourself please",
        "introduce yourself to us", "give us an introduction", "tell us about yourself", "say something about yourself",
        "what are you supposed to be", "what kind of machine are you", "what type of robot are you", "what sort of robot are you",
        "what kind of robot is this", "what's this machine", "what is this machine", "what robot is this", "who is this",
        "what is this robot for", "what is your purpose", "what's your role here", "what is your role", "why are you here",
        "what's your job here", "who r you", "who are yu", "who ar you", "hu are you", "who are you lumi",
        "누구니", "누구세요", "누구십니까", "누구신가요", "너는 누구야", "넌 누구야", "당신 누구예요", "넌 뭐니", "너는 뭐야",
        "너 정체가 뭐야", "정체가 뭐예요", "넌 정체가 뭐니", "무슨 로봇이에요", "무슨 로봇이야", "어떤 로봇이야", "어떤 로봇입니까",
        "이 로봇 뭐야", "이 로봇은 뭐예요", "이건 무슨 로봇이에요", "이 로봇은 무슨 로봇이에요", "이거 무슨 로봇이야", "얘는 뭐야",
        "얘 뭐예요", "얘는 무슨 로봇이에요", "로봇이 뭐 하는 거예요", "넌 뭐 하는 로봇이니", "넌 여기서 뭐 해", "여기서 뭐 하는 거야",
        "자기소개", "자기소개 해 주세요", "자기소개 좀 해 줘", "자기소개 부탁해요", "자기소개 부탁합니다", "자기소개 해 주실래요",
        "자기소개 해 줄래", "소개 좀 해 주세요", "너 소개 좀 해 줘", "너에 대해 알려 줘", "너에 대해 말해 줘", "본인 소개 해 주세요",
        "자기 소개 좀 해 보세요", "니 소개 좀 해 봐라", "니는 누고", "누꼬", "니 뭐꼬", "너 뭐여", "너 누구여", "뉘시오",
        "who are you 루미", "너 who야", "self introduction 해 줘", "자기소개 please", "introduce 해 줘", "너 뭐 하는 robot이야",
    ],
    "age": [
        "how old are you lumi", "what age are you", "how old r you", "how old are u", "how old ru", "hao old are you",
        "how ole are you", "how old are you now", "how old are you robot", "how old is the robot", "what's the robot's age",
        "how many years have you been around", "how long have you existed", "when were you created", "when were you first made",
        "when did you come out", "when were you manufactured", "what year were you made", "what year were you born",
        "are you a new robot", "are you a new model", "you're how old",
        "age?", "how young are you",
        "몇 살", "몇 살이니", "몇 살이냐", "몇 살임", "몇 살이에요", "몇 살이세요", "몇 살입니까", "몇 살인가요", "몇 살이야 너",
        "너 몇 살이니", "너는 몇 살이야", "니 몇 살이야", "네 나이가 몇이야", "나이가 몇이에요", "나이가 어떻게 되니", "나이가 어떻게 돼",
        "나이 어떻게 되세요", "나이가 몇 살이에요", "나이 몇이야", "나이 알려 줘", "나이가 궁금해요", "올해 몇 살이야", "올해 몇 살이에요",
        "태어난 지 얼마나 됐어", "태어난 지 얼마나 됐어요", "언제 태어났어요", "언제 태어났니",
        "만들어진 지 얼마나 됐어", "만들어진 지 얼마나 됐어요", "만든 지 몇 년 됐어요", "언제 만들어졌니", "언제 만들어졌습니까",
        "몇 년생이야", "몇 년생이에요", "몇 년 됐어", "몇 년 된 로봇이에요", "이 로봇 몇 년 됐어요", "로봇 나이가 몇이에요",
        "멫 살이고", "몇 살이고", "몇 살이여", "몇 살이당가", "몇 살이유", "몇 살이오", "니 몇 살이가", "나이가 우째 되노",
        "how old 이야", "너 몇 years old야", "age 몇이야", "몇 살 how old", "너 나이 how many",
    ],
    "maker": [
        "who made this robot", "who built this robot", "who created this robot", "who developed this robot",
        "who's your developer", "who is your developer", "who are your developers", "who's your manufacturer",
        "who manufactured you", "who makes you", "who produced you", "who invented you", "who is your creator",
        "who's behind you", "which company developed you", "which company created you", "what company created you",
        "what company developed you", "which company are you from", "what company do you belong to", "made by which company",
        "where were you made", "where were you built", "where were you developed", "where are you made", "where did you come from",
        "who made u", "who mad u", "who maid you", "hoo made you", "who build you", "who maked you", "who made ya",
        "누가 만들었니", "누가 만들었냐", "누가 만들었습니까", "누가 만든 거야", "누가 만든 거예요", "누가 만든 로봇이에요",
        "누가 너를 만들었어", "누가 너를 만들었어요", "너는 누가 만들었니", "넌 누가 만들었어", "누가 개발했어", "누가 개발했니",
        "누가 개발했습니까", "누가 개발한 로봇이에요", "개발자가 누구야", "개발자가 누구예요", "개발사가 어디예요", "개발사가 어디야",
        "제조사가 어디야", "제조사는 어디예요", "제조사가 어디입니까", "만든 회사가 어디야", "만든 회사가 어디예요", "만든 회사 어디",
        "어느 회사 거야", "어느 회사 거예요", "어디 회사 거야", "어디 회사 거예요", "어디 제품이야", "어디 제품이에요", "어디 꺼야",
        "어느 회사 제품이에요", "어느 회사에서 개발했어요", "어디서 개발했어", "어디서 개발했어요", "어디서 만든 거야", "어디서 만들었니",
        "어디서 만들어졌어요", "너 어느 회사 소속이에요", "넌 어디 소속이니", "어디 소속이에요", "누구 거야", "주인이 누구야",
        "누가 만들었노", "누가 맹글었어", "누가 만들었드나", "누가 만들었당가", "누가 만들었슈", "누가 만들었소", "누가 맹근 거여",
        "누가 만들었는교", "어데서 만들었노", "어데 회사고",
        "who made 너", "who developed 너", "누가 만들었어 who", "maker가 누구야", "제조사 who", "누가 develop 했어",
        "어느 company야", "company 어디야", "너 어느 company에서 만들었어", "made in 어디야",
    ],
    "height": [
        "how tall are you lumi", "how tall r you", "how tall are u", "how tal are you", "hou tall are you", "what is your height",
        "what's your height in cm", "what is your height in centimeters", "how many centimeters tall are you",
        "how many cm are you", "how high is this robot", "how tall is the robot", "what's the robot's height",
        "how big are you", "are you tall", "how tall do you get", "what's your size", "how tall exactly are you",
        "키 몇", "키 몇이야", "키 몇이니", "키 몇이에요", "키가 몇이니", "키가 몇이세요", "키가 몇입니까",
        "키가 얼마나 되니", "키가 어떻게 돼", "키가 어떻게 돼요", "키가 어떻게 되세요", "키 몇 센티야", "키 몇 센티니", "키가 몇 센티예요",
        "키가 몇 센티미터예요", "키가 몇 cm예요", "키 몇 cm야", "몇 센티야", "몇 센티예요", "키 얼마나 돼", "키 얼마나 돼요",
        "키가 얼마나 커", "키가 얼마나 커요", "신장이 몇이에요", "너 키가 몇이야", "니 키 몇이고", "니 키가 얼마고", "키가 우째 되노",
        "키 몇이여", "키가 몇이당가", "로봇 키가 몇이야", "이 로봇 키는 몇이에요", "키 알려 줘", "키 알려 주세요",
        "how tall 이야", "키 how tall", "your height 몇이야", "너 height가 얼마야", "키 몇 centi야",
    ],
    "weight": [
        "how heavy are you lumi", "what do you weigh", "how much do you weight", "how many kilos are you",
        "how many kg do you weigh", "how many kilograms do you weigh", "what's your weight in kg", "how heavy is the robot",
        "how much does this robot weigh", "how much does the robot weigh", "how heavy r you", "are you very heavy",
        "몸무게 몇이야", "몸무게가 몇이에요", "몸무게 얼마나 돼요", "몸무게가 어떻게 되세요", "무게가 몇이야",
        "무게가 몇이에요", "무게 몇 킬로예요", "몇 킬로그램이에요", "몇 kg이에요", "몇 키로야", "몇 키로나 나가", "무게 얼마나 나가",
        "무게가 얼마나 나가요", "너 무거워", "무거워요", "많이 무거워요", "무게가 어떻게 돼요", "이 로봇 무게가 몇이에요",
        "로봇 무게 몇 킬로예요", "몇 키로고", "무게가 우째 되노", "몇 키로여", "your weight 몇이야", "너 몇 kg이야", "weight가 얼마야",
    ],
    "battery_life": [
        "how long does the battery last", "how long does your battery last on a charge", "how many hours can you run",
        "how many hours can you work", "how long can you operate", "how long can you keep going", "how long do you run for",
        "what's your battery life like", "what is your battery life", "how long is your battery life", "battery life",
        "how long can you stay on", "how long can you run without charging", "how long until you need charging",
        "how long until your battery dies", "how long do your batteries last", "how many hours on one charge",
        "how long can you last", "how long can you work for", "does your battery last long",
        "배터리 몇 시간 가요", "배터리 몇 시간 쓸 수 있어", "배터리 몇 시간 써요", "배터리가 얼마나 가요", "배터리가 얼마나 오래 가요",
        "배터리 얼마나 오래 가", "배터리 지속 시간이 몇 시간이에요", "배터리 몇 시간 버텨요", "한 번 충전으로 얼마나 가요",
        "한 번 충전으로 몇 시간 가", "충전하면 몇 시간 가", "충전하면 얼마나 써요", "완충하면 몇 시간 가요", "완충하면 얼마나 가",
        "몇 시간 동안 움직일 수 있어요", "몇 시간 동안 일할 수 있어", "몇 시간 일해요", "하루 종일 일할 수 있어요", "얼마나 오래 일할 수 있어요",
        "배터리 몇 시간이에요", "배터리 사용 시간이 얼마예요", "배터리 몇 시간 가노", "배터리 얼마나 가노", "배터리 몇 시간 가유",
        "battery 몇 시간 가", "배터리 life가 얼마야", "battery 얼마나 가요", "배터리 how long",
    ],
    "languages": [
        "which languages can you speak", "what languages do you know", "do you know english", "do you know korean",
        "do you know chinese", "can you understand korean", "can you understand chinese", "can you understand spanish",
        "do you speak spanish", "do you speak french", "do you speak german", "can you speak russian", "do you speak uzbek",
        "can you talk in korean", "can you talk in english", "speak english", "english ok", "do you understand korean",
        "is english okay", "can i talk to you in english", "can i speak korean to you", "what languages can you understand",
        "how many languages can you speak", "are you multilingual", "can you speak japanese",
        "영어 할 수 있어", "영어 할 수 있어요", "영어 할 줄 아세요", "영어 돼", "영어 돼요", "영어 가능해요", "영어 알아들어",
        "영어도 할 줄 알아", "한국어 알아", "한국어 알아들어요", "한국말 할 줄 알아", "한국말 잘해요", "중국어 돼", "중국어 할 줄 알아",
        "일본어 돼요", "일본어 할 줄 아세요", "스페인어 할 수 있어요", "러시아어 해요", "몇 개 국어 할 수 있어", "몇 개 국어 가능해요",
        "몇 개 언어 할 수 있어요", "무슨 말 할 줄 알아", "무슨 언어로 말해요", "어떤 언어로 말할 수 있어요", "어떤 말을 알아들어요",
        "외국어 해요", "외국어 할 수 있어요", "다른 나라 말도 해요", "영어로 말해도 돼요", "영어로 해도 알아들어", "영어 할 줄 아나",
        "영어 하나", "영어 할 줄 아노", "영어 되나", "영어 할 줄 아는교",
        "can you speak 한국어", "do you speak 한국말", "english 돼", "english 할 수 있어요", "korean 할 줄 알아", "japanese 할 줄 알아",
        "영어 speak 할 수 있어", "korean 돼요",
    ],
    "chatgpt": [
        "are you based on chatgpt", "are you built on chatgpt", "do you run on chatgpt", "do you run on gpt",
        "is chatgpt inside you", "are you openai", "do you use openai", "are you made by openai", "are you gpt",
        "are you gpt 4", "is this gpt", "are you connected to chatgpt",
        "is your brain chatgpt", "chatgpt?", "are you like chatgpt",
        "너 지피티야", "지피티야", "챗지피티예요", "챗GPT예요", "챗GPT야", "챗GPT 기반이야", "챗지피티 기반이에요", "GPT 써요",
        "지피티 써", "오픈AI 거야", "오픈AI 써요", "챗GPT랑 연결돼 있어요",
        "너 chatgpt야", "chatgpt 써요", "gpt야 너", "너 openai야",
    ],
    "model": [
        "what ai model are you using", "what ai model do you use", "which ai model are you", "which llm do you use",
        "what llm are you", "what language model runs you", "what language model do you use", "what is your ai",
        "which ai do you use", "what ai runs you", "what software is your brain", "what model are you", "what model runs you",
        "which ai are you based on", "what ai is inside you", "what large language model do you use", "are you gemma",
        "do you use gemma", "what powers your answers", "what's your language model",
        "어떤 AI 모델 써", "어떤 AI 써요", "무슨 AI야", "너 무슨 AI야", "무슨 AI 모델이에요", "무슨 언어 모델이야", "언어 모델 뭐 써요",
        "인공지능 모델이 뭐예요", "인공지능은 뭐 써요", "어떤 인공지능이에요", "무슨 인공지능 써", "LLM 뭐 써요", "엘엘엠 뭐 써",
        "어떤 모델이야", "무슨 모델 써", "젬마 써요", "두뇌가 뭐예요", "무슨 AI 쓰노",
        "what ai model 써", "ai model 뭐야", "어떤 llm 써", "무슨 ai model이야", "너 model이 뭐야", "너 brain이 뭐야",
    ],
    "robot": [
        "are you a real robot", "are you human or robot", "are you a human", "are you human or machine", "are you a living thing",
        "are you a living being", "is someone inside you", "is there a human inside", "is a person controlling you",
        "is someone remote controlling you", "who is controlling you", "is somebody driving you", "can you feel emotions",
        "can you feel anything", "do you feel things", "do you feel pain", "do you have a heart", "do you have a soul",
        "are you sentient", "are you self aware", "are you artificial intelligence", "are you an ai robot", "are you just a machine",
        "are you a computer", "are you a toy", "are you real or fake", "r u a robot", "are u human", "are you a person or a robot",
        "너 사람이니", "사람이에요", "사람이세요", "사람이야 로봇이야", "로봇이야 사람이야", "진짜 로봇이야", "진짜 로봇이니",
        "너 진짜 로봇이야", "로봇 맞아", "로봇 맞아요", "로봇이니", "로봇입니까", "살아 있어요", "살아 있니", "살아 있는 거야",
        "생명체야", "생물이에요", "안에 사람이 있어", "사람이 안에 있어요", "누가 조종하는 거야", "누가 조종하고 있어요", "원격 조종이에요",
        "누가 움직이는 거예요", "감정이 있니", "감정을 느껴", "감정 느껴요", "기분을 느껴요", "아픔을 느껴요", "마음이 있어요",
        "영혼이 있어", "의식이 있니", "너 AI야", "AI예요", "인공지능이에요", "인공지능 로봇이야", "기계야", "너 기계니", "장난감이야",
        "사람이가", "사람이가 로봇이가", "로봇이가", "살아 있나", "니 사람이가", "사람이여", "감정 있나",
        "너 robot이야", "너 human이야", "are you 사람", "너 진짜 robot이야", "feelings 있어", "emotion 있어요", "너 real robot이야",
    ],
    "speed": [
        "how fast can you drive", "how quickly can you move", "what is your maximum speed", "what's your speed limit",
        "how fast do you drive", "how fast can you run", "how fast can you roll", "what speed do you go", "are you fast",
        "how fast r u", "how fast are u", "how many meters per second can you go", "how many km per hour can you go",
        "얼마나 빨리 달려", "얼마나 빨리 움직여요", "얼마나 빨라", "얼마나 빠르니", "속도가 얼마나 돼요", "속도는 얼마예요", "속도 몇이야",
        "최고 속도가 얼마예요", "최대 속도는 몇이에요", "제일 빠르면 얼마나 가요", "빨리 갈 수 있어요", "빨라요", "시속 몇 킬로예요",
        "초속 몇 미터예요", "얼마나 빨리 가노", "속도 얼마나 나오노", "your speed 얼마야", "너 max speed가 몇이야", "speed 얼마나 돼요",
    ],
    "hello": [
        "hello there", "hi lumi", "hey lumi", "hello hello", "hi hi", "hey hey", "heya", "hey robot", "hi robot",
        "good morning lumi", "good evening lumi", "good afternoon lumi", "morning", "evening", "greetings", "hello everyone",
        "nice to meet you lumi", "pleased to meet you", "glad to meet you", "hellooo", "hii", "heyy", "hullo", "hello?",
        "안녕 루미", "안녕 루미야", "루미 안녕", "안녕", "안녕하세요 루미", "안녕하세요 루미 씨", "안녕하신가요", "안녕하십니까 루미",
        "하이 루미야", "하이루", "하이요", "헬로 루미", "헬로우", "방가방가", "반갑다", "반갑습니다", "반가워 루미", "만나서 반가워",
        "처음 뵙겠습니다 루미", "좋은 아침", "좋은 아침이야", "좋은 아침입니다", "좋은 저녁이에요", "굿모닝", "굿모닝 루미", "안냥",
        "안녕하쇼", "안녕하능교", "안녕하셨어요", "어서 와", "여어", "hello 루미", "hi 루미야", "루미 hi", "안녕 hello",
    ],
    "how_are_you": [
        "how are you lumi", "how are you doing today", "how's your day", "how's your day going", "how is your day",
        "are you doing well", "are you doing ok", "you okay", "you alright", "how do you feel today", "how are things",
        "how have you been lumi", "what's up lumi", "how you doing", "how r u", "how are u", "hows it going",
        "잘 지냈어", "잘 지냈니", "잘 지냈습니까", "잘 지내요", "잘 지내니", "잘 있었어", "잘 있었어요", "오늘 어때", "오늘 어때요",
        "오늘 하루 어때요", "오늘 기분이 어때", "기분이 어때", "기분 좋아", "기분 어때요", "컨디션 어때", "컨디션 어때요", "괜찮니",
        "별일 없어", "요즘 어떻게 지내", "요즘 어때요", "잘 지내고 있어요", "오늘 컨디션 괜찮아요", "잘 지냈나", "잘 있었나",
        "how are you 루미", "컨디션 how", "how are you 오늘", "기분 how",
    ],
    "no": [
        # weight, height, age, maker, speed of other things: the LLM or a lookup
        "how heavy is the ice cream robot", "how heavy is the candy ball robot", "how much does the barista robot weigh",
        "how tall is the ice cream robot", "how big is the ice cream robot", "how fast is the ice cream robot",
        "how fast is the candy ball robot", "how tall is the eiffel tower", "how tall is lotte tower", "how old is taylor swift",
        "how old is the president", "how old is the ceo", "who made the iphone", "who invented the telephone",
        "who made jaka robots", "what is jaka", "who made your camera", "who made your computer", "who made your wheels",
        "how heavy is your gripper", "how heavy is your head", "how fast is your arm", "how old is your arm",
        "how fast can a car go", "how heavy is an elephant", "how tall is son heung-min", "what's the name of this event",
        "what's the name of this building", "what is the name of the ceo", "what's the name of the company",
        "아이스크림 로봇 무게가 얼마예요", "아이스크림 로봇 얼마나 빨라요", "캔디볼 로봇 몇 초 걸려요", "에펠탑 높이가 얼마야",
        "손흥민 키가 몇이야", "손흥민 몇 살이야", "아이폰 누가 만들었어", "대표 나이가 몇이에요", "대표님 이름이 뭐예요",
        "이 건물 이름이 뭐예요", "이 행사 이름 뭐야", "회사 이름이 뭐예요", "카메라 누가 만들었어",
        # the visitor about themselves
        "what's my name", "do you know my name", "guess my name", "how old do you think i am", "guess how old i am",
        "how tall do you think i am", "내 이름 뭐게", "내 이름 알아", "내가 몇 살 같아", "나 몇 살로 보여", "제 이름 아세요",
        # questions that are not facts of Lumi
        "what is your favorite color", "what's your favourite food", "do you like music", "do you like me",
        "are you tired", "are you hungry", "are you happy", "are you bored", "are you sleepy", "do you sleep",
        "where are we", "where am i", "where is the toilet", "what do you think about ai", "will robots take over the world",
        "좋아하는 색이 뭐야", "좋아하는 음식 뭐예요", "음악 좋아해", "피곤해", "배고파", "행복해", "심심해", "잠 자", "여기 어디야",
        "화장실 어디예요", "로봇이 세상을 지배할까", "battery level", "your battery level", "how much battery do you have",
        "배터리 얼마나 남았어", "배터리 몇 프로야",
        "emergency stop", "stop now", "stop", "멈춰", "그만",
        # what Lumi is doing now (status), what it can do (abilities), slow speed, charging time: not these kinds
        "what are you doing", "what are you doing now", "what are you doing robot", "what are you up to", "지금 뭐 해",
        "뭐 하고 있어", "지금 뭐 하는 중이에요", "로봇아 지금 뭐 해", "뭐 할 줄 알아", "뭘 할 줄 아니", "뭐 할 수 있어요",
        "how slow can you drive", "how slow can you go", "what's your slowest speed", "가장 느리게 가면 얼마야", "얼마나 천천히 갈 수 있어",
        "완충하는 데 얼마나 걸려", "완충까지 몇 시간이에요", "how long does a full charge take", "how long to fully charge",
        # a request and a question together: the rules or the LLM
        "컵 주고 이름 알려 줘", "이리 오고 이름 말해 줘", "손 흔들고 이름 알려 주세요", "give me the cup and tell me your name",
        "come here and tell me how old you are", "따라오고 나이 알려 줘",
        # the birthday is not known (the age is)
        "when is your birthday", "when's your birthday", "what's your birthday", "what day were you born", "생일이 언제야",
        "생일이 언제예요", "생일 언제야", "너 birthday 언제야", "생일이 며칠이에요",
        # a greeting with a question after it: the question decides
        "안녕 루미 상 받은 거 있어", "안녕하세요 화장실 어디예요", "안녕 루미 날씨 어때",
        "안녕 오늘 뭐 해",
        # not known: the battery's lifetime in years, being another company's robot
        "battery 수명 몇 년이에요", "배터리 수명이 몇 년이에요", "배터리 몇 년 써요", "배터리 교체 주기가 어떻게 돼요",
        "how many years does the battery last", "when does the battery need replacing", "너 자카 로봇이야", "자카 거야",
        "jaka에서 만들었어", "are you a jaka robot", "are you made by jaka", "너 중국 회사 로봇 맞지", "hello where is the toilet", "hi what's the weather",
        "hello can you help me", "안녕하세요 질문 있어요", "hi i have a question",
    ],
}

# new kinds: (wordings, {"en": [answers], "ko": [answers]})
QUICK_KINDS = {
    "internet": ([
        "do you use the internet", "are you connected to the internet", "are you online", "do you need the internet",
        "do you use the cloud", "are you using the cloud", "do you need the cloud", "do you work without internet",
        "can you work offline", "can you go on the internet", "can you search the internet", "can you look things up online",
        "인터넷 써요", "인터넷 연결돼 있어", "인터넷 돼요", "인터넷 없이도 돼요", "인터넷 검색할 수 있어요", "인터넷에 연결돼 있어요",
        "클라우드 써요", "클라우드로 돌아가요", "클라우드 연결돼 있어", "오프라인으로도 돼요", "cloud 써요", "internet 돼요",
        "인터넷으로 찾아볼 수 있어", "온라인이야",
    ], {"en": ["I think on my own computer, without the cloud. I use the internet only to look up the weather, the news and other facts.",
               "My language model runs on the robot itself. The internet I use only for lookups: the weather, news and facts from Wikipedia and Google News."],
        "ko": ["저는 클라우드 없이 제 컴퓨터에서 생각해요. 인터넷은 날씨, 뉴스, 그 밖의 정보를 찾아볼 때만 써요.",
               "제 언어 모델은 로봇 안에서 돌아가요. 인터넷은 날씨나 뉴스, 위키백과 같은 정보를 찾을 때만 써요."]}),
    "country": ([
        "what country are you from", "which country are you from", "which country made you", "what country made you",
        "are you from korea", "are you korean", "are you a korean robot", "are you made in korea", "were you made in korea",
        "are you from china", "are you chinese", "are you a chinese robot", "are you made in china", "are you japanese",
        "are you american", "is this robot korean", "where is this robot from", "what nationality are you",
        "어느 나라에서 왔어", "어느 나라에서 왔어요", "어느 나라 로봇이야", "어느 나라 로봇이에요", "어느 나라에서 만들었어요",
        "어느 나라 거예요", "어느 나라 제품이에요", "한국 로봇이야", "한국 로봇이에요", "한국에서 만들었어요", "국산이에요", "국산 로봇이야",
        "중국 로봇이야", "중국 로봇이에요", "중국산이에요", "중국에서 만들었어요", "일본 로봇이에요", "미국 로봇이야", "국적이 어디예요",
        "너 한국인이야", "메이드 인 코리아예요", "made in korea야", "너 korean robot이야", "너 어느 나라 robot이야", "중국 꺼야",
    ], {"en": ["I'm from Korea: Cutshion Company in Seoul developed me.",
               "I'm a Korean robot. Cutshion Company, a robot company in Seoul, developed me."],
        "ko": ["저는 한국에서 왔어요. 서울에 있는 쿳션이 저를 개발했어요.",
               "저는 한국 로봇이에요. 서울의 로봇 회사 쿳션이 개발했어요."]}),
    "computer": ([
        "what computer do you use", "what computer do you have", "what's your computer", "what computer runs you",
        "what hardware do you run on", "what processor do you have", "what chip do you use", "what gpu do you have",
        "which computer is inside you", "what is your cpu", "do you use nvidia", "are you running on a jetson",
        "what's inside you", "what kind of computer are you", "how powerful is your computer", "how much memory do you have",
        "무슨 컴퓨터 써요", "어떤 컴퓨터 써", "컴퓨터 뭐 써요", "컴퓨터가 뭐예요", "어떤 컴퓨터가 들어 있어요", "무슨 칩 써요",
        "GPU 뭐 써요", "그래픽카드 뭐야", "프로세서가 뭐예요", "엔비디아 써요", "젯슨이에요", "안에 뭐가 들어 있어요",
        "메모리 얼마예요", "컴퓨터 성능이 어때요", "무슨 하드웨어로 돌아가요", "너 computer 뭐 써", "무슨 gpu야", "hardware 뭐 써요",
    ], {"en": ["My computer is an NVIDIA Jetson AGX Thor, with a Blackwell graphics processor, 14 cores and 122 GB of memory.",
               "An NVIDIA Jetson AGX Thor with 122 GB of memory. It runs my speech recognition, my language model and my cameras, all on the robot."],
        "ko": ["제 컴퓨터는 엔비디아 젯슨 AGX 토르예요. 블랙웰 그래픽 프로세서, 코어 14개, 메모리 122GB가 있어요.",
               "엔비디아 젯슨 AGX 토르예요. 메모리는 122GB이고, 음성 인식, 언어 모델, 카메라를 모두 로봇 안에서 돌려요."]}),
    "dof": ([
        "how many joints do you have", "how many degrees of freedom do you have", "how many dof do you have",
        "how many axes do you have", "how many motors do you have", "how many joints does your arm have",
        "how many axes does your arm have", "how many parts can you move",
        "관절이 몇 개야", "관절이 몇 개예요", "자유도가 몇이에요", "몇 자유도예요", "몇 축이에요", "팔이 몇 축이야", "팔 관절 몇 개예요",
        "모터가 몇 개예요", "몸에서 움직이는 데가 어디예요", "너 dof 몇이야", "joint 몇 개야", "몇 축 로봇이에요",
    ], {"en": ["I have 12 degrees of freedom: the lift, the waist, two head joints, six arm joints and two drive wheels.",
               "Twelve in all: my arm has six joints, my head two, then my waist, my lift and my two wheels."],
        "ko": ["자유도는 모두 12개예요. 리프트, 허리, 머리 관절 두 개, 팔 관절 여섯 개, 바퀴 두 개예요.",
               "모두 12축이에요. 팔이 6축, 머리가 2축이고, 허리, 리프트, 바퀴 두 개가 있어요."]}),
    "estop": ([
        "where is your emergency stop", "where's your emergency stop button", "where is the stop button", "how do i stop you",
        "how can i stop you in an emergency", "do you have an emergency stop", "is there an emergency button",
        "what if something goes wrong how do i stop you", "where is the red button", "how do we stop the robot",
        "비상 정지 버튼 어디 있어요", "비상 정지 버튼이 어디야", "비상 버튼 어디 있어", "정지 버튼이 어디예요", "빨간 버튼 어디 있어요",
        "어떻게 멈춰요", "위험할 때 어떻게 멈춰", "비상시에 어떻게 세워요", "비상 정지 있어요", "emergency stop 어디 있어요",
        "e-stop 버튼 어디야", "비상 스톱 어디예요",
    ], {"en": ["There are red emergency stop buttons on my body and in my base. Pressing one stops my arm and my lift at once.",
               "Press one of my red emergency stop buttons, on my body or in my base: my arm and lift stop at once. You can also just say \"stop\"."],
        "ko": ["제 몸과 베이스에 빨간 비상 정지 버튼이 있어요. 누르면 팔과 리프트가 바로 멈춰요.",
               "몸이나 베이스에 있는 빨간 비상 정지 버튼을 누르시면 팔과 리프트가 바로 멈춰요. \"멈춰\"라고 말씀하셔도 돼요."]}),
}

# slips, dialect and short forms heard in the blind rounds (the same meanings, other words)
_MORE = {
    "name": [
        "wat is ur naem", "whats yer name", "what's yer name", "you name what", "your name what", "what name do they give you",
        "what name did they give you", "got a name", "got a name buddy", "what are they calling you", "name pls",
        "이름이 뭐라 카노", "이름이 뭐라카노", "이름 머라 카노", "니 이름 뭐라꼬", "이름이 뭐임 너", "이름이 뭐지", "얘 이름이 뭐지",
        "이름 뭐니 너", "이림이 뭐야", "일므이 뭐야", "이름이 머예요", "너 name 뭐야", "your name 알려 줘",
    ],
    "who": [
        "you are what thing", "what thing are you", "what's your deal what are you", "so what are you", "what are you anyway",
        "넌 머야", "너 머야", "넌 머니", "너는 머임", "이건 뭐 하는 로봇이여", "뭐 하는 애니", "넌 무슨 로봇이고",
    ],
    "age": [
        "how old r u robot", "how many years old r u", "are you a baby robot", "are you a young robot",
        "몇쌀이야", "몇 쌀이야", "멷 살이야", "몇 살 잡수셨어요", "연세가 어떻게 되십니까", "춘추가 어떻게 되세요", "나이가 몇 살이고",
        "몇 살인데", "나이 좀 알려 줘", "너 나이 몇", "how old 너는",
    ],
    "maker": [
        "who made you robot", "who built you robot", "what company built you", "what company made you robot", "which firm built you", "너 어느 회사 거니", "너 어느 회사 로봇이야", "너 어디 회사 로봇이에요", "어느 회사 로봇이십니까", "니 어느 회사 기고", "who's the maker of this robot", "which company makes you",
        "어디서 만든 로봇입니까", "어디서 만든 로봇이에요", "어디서 만든 로봇이야", "이거 어디 회사 기고", "어데 회사 로봇이고",
        "이거 누가 만들었노", "이 로봇 누가 만든 거예요", "어느 회사가 만들었어", "어디 거야 이 로봇", "who made 이 로봇",
    ],
    "height": [
        "키가 몃이야", "키가 몇이예요", "키 몇 쎈치야", "키 몇 센치야", "키 몇 센치예요", "높이가 얼마예요", "높이가 몇이에요",
        "로봇 높이가 어떻게 돼요", "키 몇 미터야", "몇 미터예요 키가", "how high r you", "what's your height robot",
    ],
    "weight": [
        "몇 키로나 나가노", "몇 키로 나가", "몇 킬로나 나가요", "무게 머야", "무게가 머예요", "무게 얼마야 너", "중량이 얼마예요",
        "몇 kg 나가요", "how heavy r u", "how many kilos do you weigh", "what's your weight robot",
    ],
    "speed": [
        "how fast are you robot", "how fast do you go", "how quick are you", "얼마나 빨리 다녀", "빠르기가 어때요", "속도 머야",
        "몇 키로로 가요", "시속 몇이야",
    ],
    "battery_life": [
        "does your battery run out quickly", "how long do you keep going", "how long can you keep going on one charge",
        "충전하면 얼마나 씁니까", "충전하면 얼마나 써", "사용 시간이 어떻게 돼요", "사용 시간이 얼마예요", "연속으로 얼마나 움직일 수 있어요",
        "연속 사용 시간이 얼마예요", "한 번 충전에 몇 시간이나 버팁니까", "한 번 충전에 몇 시간 버텨요", "너 battery 얼마나 가",
        "배터리 얼마나 가요 하루 종일 가요", "배터리 다 닳으려면 얼마나 걸려", "배터리 얼마나 오래 써요",
    ],
    "languages": [
        "can i talk to you in german", "can i speak to you in japanese", "do you understand every language",
        "한국어 알아들어요", "한국말 알아들어", "한국어 알아듣니", "영어 돼요 너", "영어 되나", "사투리도 알아듣나", "사투리 알아들어요",
        "외국말도 알아들어", "중국말 할 줄 아나",
    ],
    "model": [
        "do you use gemini", "are you gemini", "do you use llama", "are you claude", "is your ai from google",
        "AI 뭐 들어 있어", "어떤 AI가 들어 있어요", "대화는 어떤 AI가 해", "대화는 무슨 AI로 해요", "무슨 AI로 대답해요",
        "AI 뭐 써", "어떤 AI 들어가 있어",
    ],
    "robot": [
        "do you get sad", "do you get angry", "do you get lonely", "you have feeling", "you have feelings", "do you dream",
        "can you dream", "꿈 꿔", "꿈 꿔요", "꿈을 꿔", "로봇도 감정이 있어요", "로봇도 감정 있어", "슬퍼할 줄 알아", "화낼 줄 알아",
        "외로움 느껴", "너 살아 있어", "살아 있는 거 맞아", "생각할 줄 알아",
    ],
    "no": [
        "요즘 무슨 일 있어", "요즘 경제가 어때요", "요즘 경제 어때", "경기가 어때요", "요즘 뉴스 뭐 있어",
        "how heavy can you lift", "can i lift you", "내가 너 들 수 있어", "are you taller than me", "are you taller than my dad",
        "could you beat me in a race", "나랑 달리기 하면 누가 이겨", "who is faster you or me",
        "로봇은 어디서 만들어요", "로봇은 어디서 만들어", "where are the robots made", "where is the factory", "공장이 어디예요",
        "쿳션 공장 어디 있어요", "where does cutshion build its robots",
    ],
}
for _k, _v in _MORE.items():
    QUICK.setdefault(_k, []).extend(_v)

QUICK_KINDS["used_where"] = ([
    "where are you used", "where can you be used", "where do you work", "what places are you made for",
    "what were you made for", "what were you built for", "who are you made for", "where would you be useful",
    "어디에 쓰여요", "어디서 쓰는 로봇이에요", "어떤 데서 쓰라고 만들었어", "어디에 쓰려고 만들었어요", "어디서 일해요",
    "어떤 곳에서 써요", "무슨 용도로 만들었어요", "용도가 뭐예요", "어디에 쓸 수 있어", "너 용도가 뭐야", "어디서 쓰는 거야",
], {"en": ["I'm made for shops, hotels, schools, labs and exhibitions.",
           "Places like shops, hotels, schools, research labs and exhibitions, where I greet, guide and help people."],
    "ko": ["저는 상점, 호텔, 학교, 연구실, 전시회에서 쓸 수 있게 만들어졌어요.",
           "상점, 호텔, 학교, 연구실, 전시회 같은 곳에서 사람들을 맞이하고 안내하고 도와요."]})

QUICK_KINDS["stt"] = ([
    "how do you understand speech", "how do you understand what i say", "what speech recognition do you use",
    "what do you use for speech recognition", "how do you hear words", "what turns my voice into text",
    "do you use whisper", "what's your speech to text", "how do you recognise speech",
    "말 알아듣는 건 뭘로 해요", "말은 어떻게 알아들어요", "음성 인식 뭐 써요", "음성 인식은 뭘로 해", "음성 인식 엔진이 뭐예요",
    "말을 어떻게 알아듣니", "목소리를 어떻게 글로 바꿔요", "위스퍼 써요", "speech recognition 뭐 써요", "STT 뭐 써",
], {"en": ["I turn speech into text with Whisper, the large-v3-turbo model, running on my own computer.",
           "With Whisper: it runs right here on my NVIDIA computer and writes down what you say."],
    "ko": ["말소리는 위스퍼(Whisper) large-v3-turbo 모델로 글자로 바꿔요. 제 컴퓨터에서 직접 돌아가요.",
           "위스퍼라는 음성 인식 모델로 알아들어요. 제 엔비디아 컴퓨터에서 돌아가요."]})
QUICK_KINDS["reply_time"] = ([
    "how fast do you answer", "how quickly can you respond", "how quickly do you reply", "how long do you take to answer",
    "how fast do you respond to a question", "how long until you answer", "what's your response time",
    "얼마나 빨리 대답해요", "대답하는 데 얼마나 걸려요", "대답 속도가 어때요", "답하는 데 몇 초 걸려", "반응 속도가 얼마예요",
    "말하면 얼마 만에 대답해요", "response time 얼마야",
], {"en": ["My first words come about two seconds after a question.",
           "About two seconds: that's when my first words come after you ask."],
    "ko": ["질문하시고 약 2초 뒤에 첫마디가 나와요.", "대답은 질문 후 약 2초 안에 시작해요."]})
QUICK["no"] += [
    "몇 센티 오차예요", "오차가 몇 센티야", "위치 오차가 얼마예요", "how accurate is your position", "how precise is your map position",
    "how accurate is your arm", "팔 정확도가 얼마예요", "반복 정밀도가 얼마예요", "what's your repeatability",
]
QUICK_KINDS["tts"] = ([
    "what text to speech do you use", "what text-to-speech do you use", "what's your tts", "how do you speak",
    "how do you make your voice", "what voice engine do you use", "where does your voice come from", "what makes your voice",
    "목소리는 뭘로 내요", "음성 합성 뭐 써요", "TTS 뭐 써", "목소리 어떻게 만들어요", "말소리는 어떻게 내요", "너 목소리 뭐야",
], {"en": ["I speak with a text-to-speech engine called Supertonic, through my speaker.",
           "My voice comes from Supertonic, a text-to-speech engine running on my own computer."],
    "ko": ["슈퍼토닉(Supertonic)이라는 TTS로 목소리를 내요.", "제 목소리는 슈퍼토닉이라는 음성 합성 엔진으로 만들어요."]})
QUICK_KINDS["mics"] = ([
    "how do you hear me", "what do you hear with", "how many microphones do you have", "do you have microphones",
    "where are your microphones", "how far can you hear", "can you tell where a voice comes from",
    "소리는 무엇으로 들으십니까", "소리는 뭘로 들어요", "마이크 몇 개예요", "마이크 있어요", "마이크가 어디 있어", "얼마나 멀리서 들려요",
    "귀가 어디야", "어떻게 들어요", "소리 어떻게 들어",
], {"en": ["I hear with a ring of six microphones in my head, from about 3 to 5 metres away, and I can tell where a voice comes from.",
           "Six microphones in my head: they hear people 3 to 5 metres away and tell me which direction a voice comes from."],
    "ko": ["머리에 있는 마이크 6개로 들어요. 3에서 5미터 거리까지 듣고, 목소리가 어느 쪽에서 오는지도 알 수 있어요.",
           "머리에 마이크가 6개 있어요. 3~5미터 떨어진 목소리를 듣고 방향도 알아요."]})
QUICK["no"] += ["can you hear me", "do you hear me", "들려", "내 말 들려요", "제 말 들리세요", "hello can you hear me",
                "are you listening", "듣고 있어"]
QUICK["no"] += [
    # orders that sound like these questions: the rules or the LLM, never a fact
    "키 줄여 줘", "키 다운 해 줘", "키 업 해 줘", "키를 올려 보시오", "키 좀 높여 줘", "키 올려", "키 내려", "키 낮춰 줘", "키 키워 줘",
    "robot stretch up tall", "robot more tall please", "grow taller", "get taller", "be shorter", "stretch up",
    "몸 올려요 로봇", "몸 내려요 로봇", "몸 올려", "몸 내려", "손 좀 내밀어 주세요", "손 내밀어", "손 줘",
    "hey robot wave like a person", "wave like a human", "hello robot follow follow", "hi lumi follow me", "hello lumi come here",
    "안녕 루미 이리 와", "루미야 루미야 그만해요", "그만해요", "그만해", "기분이 다운됐어", "나 기분 안 좋아",
    "how much longer will you wait", "how long are you waiting", "how long will you wait", "what's the job", "what's your task now",
    "introduce yourself then turn to your left", "자기소개하고 왼쪽 봐", "고개 숙이고 이름 알려 줘", "오른쪽 보고 나이 말해 줘",
]
# "노래 부를 줄 알아요?": an ability question, answered; the song comes on "yes" / "불러 줘" (brain.DO_IT, SING_ASK).
# A request ("노래 불러 줘", "can you sing?", "노래 부를 수 있어?") is audio/sing.asked's and never reaches this kind.
_SING_KO = [s + e for s in ["노래 부를 줄 ", "노래 할 줄 ", "노래할 줄 ", "노래도 할 줄 ", "노래도 부를 줄 ", "너 노래 할 줄 ", "루미 노래 부를 줄 ",
                             "노래 하실 줄 ", "노래 부르실 줄 ", "혹시 노래 부를 줄 "]
            for e in ["알아", "알아요", "아니", "아세요", "아십니까", "압니까", "아나", "아나요", "알아유", "아노", "알지", "알죠"]]
QUICK_KINDS["can_sing"] = (_SING_KO + [
    "do you know how to sing", "are you able to sing", "is singing something you can do", "do you sing", "can robots like you sing",
    "do you know how to sing songs", "are you able to sing at all", "is lumi able to sing", "do you know any singing",
    "노래 부를 줄은 알아", "노래는 할 줄 알아요", "노래 부르는 거 할 줄 알아", "singing 할 줄 알아", "sing 할 줄 알아요",
], {"en": ["Yes, I can sing! I have a few songs of my own. Shall I sing one for you?",
           "I can! I know some songs of my own. Want to hear one?"],
    "ko": ["네, 노래할 수 있어요! 제 노래가 몇 곡 있어요. 한 곡 불러 드릴까요?",
           "할 줄 알아요! 제 노래가 있는데, 한 곡 들어 보실래요?"]})
QUICK["no"] += ["노래 불러 줘", "노래 불러 줄래", "노래 한 곡 불러 주세요", "sing a song", "sing me a song", "sing for me",
                "노래 좋아해", "노래 잘해", "do you like singing", "what songs can you sing", "무슨 노래 할 줄 알아", "부를 줄 아는 노래 뭐야",
                "춤 출 줄 알아", "요리할 줄 알아", "수영할 줄 알아", "거짓말 할 줄 알아", "can you cook", "do you know how to swim"]
# whose robot Lumi is ("너 어느 회사 거야?", "어디 회사 거예요?"): the maker, not the company's place (co_hq) or what it does (co_what)
QUICK["maker"] = QUICK.get("maker", []) + [
    s + e for s in ["너 어느 회사 거", "어느 회사 거", "어디 회사 거", "너 어디 회사 거", "루미 어디 회사 거", "이 로봇 어느 회사 거", "이 로봇 어디 회사 거",
                    "어느 회사 제품", "어디 제품", "어느 회사 로봇", "너 어디 제품", "어디서 나온 로봇"]
    for e in ["야", "예요", "에요", "니", "입니까", "인가요", "고", "여", "냐", "임", "이야", "이에요"]] + [
    "who designed and built you", "who built and designed you", "who made and programmed you", "what company built you",
    "which company built you", "what company created you", "which company designed you", "whose robot are you",
    "whose robot is this", "which brand are you", "what brand is this robot",
]
QUICK["who"] = QUICK.get("who", []) + ["tell me about you", "tell me something about you", "tell me a bit about you", "what do you do",
    "what do you do exactly", "what is it you do", "what's your job here", "what's your role", "너에 대해 알려 줘", "너에 대해 말해 줘",
    "너에 대해 알려 주세요", "루미에 대해 알려 주세요", "당신에 대해 소개해 주세요"]
QUICK["height"] = QUICK.get("height", []) + ["how tall is this thing", "how tall is this machine", "how tall is the robot", "how high is lumi",
    "이거 키가 얼마야", "이 기계 키 몇이에요"]
QUICK["name_meaning"] = QUICK.get("name_meaning", []) + [
    s + e for s in ["루미 무슨 뜻", "루미가 무슨 뜻", "루미는 무슨 뜻", "루미라는 이름 무슨 뜻", "루미 뜻", "루미란 이름은 무슨 뜻"]
    for e in ["이에요", "이야", "이니", "입니까", "이고", "이여", "인가요", "이죠"]] + [
    "why is your name lumi", "why are you named lumi", "what does the name lumi mean", "why the name lumi",
    "왜 루미라고 불러", "왜 이름이 루미야", "왜 루미예요", "왜 루미라고 지었어요"]
