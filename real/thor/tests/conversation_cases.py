"""What conference visitors say to Lumi, with the route each must take and what the answer must (not) contain.

CASES = [{"text", "lang", "who", "expect", "must", "must_not"}]
- expect: a route, alternatives split by " | ". Routes: about_self, date_time, chat (all three are the LLM talking,
  action none), weather, search, status, mission, unclear, other_language, action:<name> [target words].
- must / must_not: case-insensitive regexes on the spoken reply; every must has to match, no must_not may.
  {wd} {wdk} {d} {mon} {h12} {h24} {y}: filled with the time of the run. about_self facts come only from
  knowledge/lumi_about_en.md; where the true answer is not known, must is "not sure"-like and must_not the made-up value.
Checked by tests/conversation_check.py.
"""
import re

CASES = []

NOT_SURE = r"not sure|don'?t know|do not know|not known|no information|don'?t have|staff|ask|모르|알 수 없|확실하지|정보가 없|직원|문의"
LUMI = r"lumi|루미"
MAKER = r"cutshion|쿳션"                 # the company name as the owner writes it (not 커션 / 쿳션)
JAKA = r"jaka|자카|제이카|节卡"            # the hardware maker: Lumi does not name it as its maker
NO = r"\bno\b|can'?t|cannot|not able|unable|don'?t|do not|only|아니|못|없|않|만 ?해|만 할"
YES = r"\byes\b|\bi can\b|of course|sure|네|응|할 수 있|가능"


def add(expect, lang, rows):
    """rows: (who, text[, must[, must_not]]); must / must_not: a regex or a list of them."""
    for r in rows:
        who, text, must, must_not = (list(r) + [[], []])[:4]
        CASES.append({"text": text, "lang": lang, "who": who, "expect": expect,
                      "must": [must] if isinstance(must, str) else list(must),
                      "must_not": [must_not] if isinstance(must_not, str) else list(must_not)})


# ------------------------------------------------------------------ about_self, English
add("about_self", "en", [
    ("visitor", "what is your name", LUMI), ("kid", "what's your name", LUMI), ("visitor", "who are you", LUMI),
    ("kid", "are you a robot", r"robot"), ("visitor", "who made you", MAKER, JAKA), ("business", "which company built you", MAKER, JAKA),
    ("journalist", "where are you from", MAKER, JAKA), ("business", "where is Cutshion Company from", r"korea|seoul", r"shanghai|china"),
    ("visitor", "what does your name mean", r"light|lux"), ("kid", "why are you called Lumi", r"light|lux|mini"),
    ("kid", "how tall are you", r"146|1\.46|186"), ("visitor", "how big are you", r"146|51|186"),
    ("engineer", "what are your dimensions", r"51"), ("kid", "how heavy are you", r"96|95\.6"),
    ("worker", "how much do you weigh", r"96|95\.6"), ("engineer", "how much does your base weigh", r"50"),
    ("kid", "can you grow taller", r"40|186|lift"), ("engineer", "how high can your lift go", r"40|186"),
    ("engineer", "how many degrees of freedom do you have", r"\b12\b|twelve"), ("engineer", "how many joints does your arm have", r"\b6\b|six"),
    ("engineer", "what arm do you use", r"mini ?2"), ("engineer", "how far can your arm reach", r"58"),
    ("engineer", "how precise is your arm", r"0\.1"), ("worker", "how much can you lift", [r"\b2 ?(kg|kilo)|two kilo|\b1 ?(kg|kilo)|one kilo"], r"\b(5|10|20|50) ?kg"),
    ("worker", "how much can your arm carry", r"\b2 ?(kg|kilo)|two kilo|\b1 ?(kg|kilo)"), ("engineer", "what is your payload", r"\b2 ?(kg|kilo)|two kilo|\b1 ?(kg|kilo)"),
    ("engineer", "is the payload measured", r"estimate|not (been )?weighed|about"), ("kid", "can you lift me", NO),
    ("engineer", "what gripper do you have", r"zimmer|electric|two|finger"), ("engineer", "how wide can your gripper open", r"8\.4|84|4\.5"),
    ("visitor", "what can you pick up", r"cup"), ("visitor", "can you pick up a bottle", r"bottle|yes"),
    ("visitor", "can you pick things up from the floor", NO), ("kid", "can you hold my phone", r"cup|bottle|apple|banana|orange|\bno\b|can'?t|cannot|only"),
    ("engineer", "how fast does your gripper close", r"one second|1 second|second"), ("engineer", "how do you know something is in your hand", r"sensor|camera|light"),
    ("visitor", "can you see me", r"camera|yes|see"), ("engineer", "how many cameras do you have", r"three|3|two|2"),
    ("engineer", "what cameras do you use", r"orbbec|gemini"), ("engineer", "how far can your cameras see", r"10"),
    ("engineer", "what object detector do you use", r"yolo"), ("engineer", "how fast is your object detection", r"millisecond|ms|4|13"),
    ("visitor", "do you recognise faces", NO), ("visitor", "do you remember me", NO),
    ("engineer", "do you have a lidar", r"yes|lidar|laser"), ("engineer", "what's the range of your lidar", r"10"),
    ("engineer", "what sensors do you have", r"lidar|camera|ultrason|laser"), ("engineer", "how do you avoid obstacles", r"lidar|camera|sensor|path|map"),
    ("visitor", "how do you know where you are", r"map|lidar|laser"), ("engineer", "how do you navigate", r"map|lidar|laser"),
    ("engineer", "how accurate is your position", r"5 ?cm|5 centimet|five centimet"), ("visitor", "do you need a map", r"map"),
    ("kid", "can you climb stairs", NO), ("worker", "can you go up a step", r"1\.5|step|\bno\b|can'?t"),
    ("visitor", "how fast can you go", r"0\.6|1\.2"), ("kid", "what's your top speed", r"1\.2"),
    ("worker", "how fast do you drive with a cup", r"10 ?cm|0\.1|slow"), ("engineer", "how wide a corridor do you need", r"70"),
    ("visitor", "how do you hear me", r"microphone|mic"), ("engineer", "how many microphones do you have", r"\b6\b|six"),
    ("engineer", "can you tell where a voice comes from", r"yes|direction|microphone"), ("visitor", "do you have a speaker", r"yes|speaker"),
    ("engineer", "how do you understand speech", r"whisper"), ("engineer", "what speech recognition do you use", r"whisper"),
    ("engineer", "what AI do you use", r"gemma|language model|whisper|yolo"), ("engineer", "which language model runs on you", r"gemma"),
    ("engineer", "do you use ChatGPT", r"gemma|\bno\b|local"), ("engineer", "do you need the cloud", r"\bno\b|local|on (the robot|my own)|without"),
    ("engineer", "do you need the internet", r"weather|news|look|wikipedia|\bno\b|not"), ("engineer", "what text to speech do you use", r"supertonic"),
    ("engineer", "how fast do you answer", r"two seconds|2 seconds|second"), ("engineer", "what computer do you have", r"thor|jetson|nvidia"),
    ("engineer", "how powerful is your computer", r"2070|thor"), ("engineer", "how much memory do you have", r"122"),
    ("engineer", "what GPU do you use", r"blackwell|nvidia|thor"), ("engineer", "what programming language are you written in", r"python"),
    ("visitor", "what languages do you speak", [r"english", r"korean"]), ("visitor", "can you speak Korean", YES),
    ("visitor", "can you speak Chinese", NO), ("visitor", "do you speak Uzbek", NO),
    ("worker", "how long does your battery last", r"\b10\b|ten"), ("engineer", "what battery do you have", r"24|45|lithium"),
    ("worker", "how do you charge", r"dock|charg"), ("worker", "how long does it take to charge you", NOT_SURE, r"\b\d+ ?(hours|minutes)"),
    ("visitor", "what's your battery level", r"can'?t|cannot|not|don'?t", r"\d+ ?(%|percent)"),
    ("investor", "how much do you cost", NOT_SURE, r"\$|dollar|won|원|\d{3,}"), ("business", "what is your price", NOT_SURE, r"\$|dollar|\d{3,}"),
    ("business", "can I buy you", r"staff|ask|price|contact"), ("teacher", "who programmed you", MAKER, JAKA), ("journalist", "who developed you", MAKER, JAKA), ("business", "what company are you from", MAKER, JAKA),
    ("journalist", "who operates you here", r"cutshion"), ("visitor", "who do I ask for help", r"staff|cutshion"),
    ("kid", "are you alive", r"robot|not alive|\bno\b"), ("kid", "do you have feelings", r"\bno\b|don'?t|not"),
    ("other_field", "are you conscious", r"\bno\b|not|don'?t"), ("kid", "can you dance", NO),
    ("kid", "can you fly", NO), ("kid", "can you jump", NO), ("kid", "can you walk", r"wheel|drive|\bno\b"),
    ("visitor", "can you open doors", NO), ("visitor", "are you dangerous", r"stop|safe|emergency|slow|careful"),
    ("teacher", "is it safe to stand next to you", r"stop|safe|emergency|slow"), ("visitor", "what happens if I push you", r"heavy|don'?t push|please"),
    ("worker", "do you have an emergency stop", r"yes|button|emergency"), ("visitor", "what can you do", r"talk|drive|pick|answer|question"),
    ("teacher", "what can you do with your arm", r"pick|cup|hand|wave"), ("visitor", "can you bring me something", r"cup|bottle|yes|bring"),
    ("visitor", "can you do several things in one command", r"yes|step|mission|several"), ("visitor", "what can't you do", r"stairs|door|floor|faces|heavy"),
    ("engineer", "how far does your waist turn", r"160"), ("engineer", "how far can your head turn", r"180"),
    ("engineer", "what does your base do", r"drive|wheel|lidar|map"), ("other_field", "what is an embodied AI platform", r"see|hear|move|arm"),
    ("teacher", "where are you used", r"shop|hotel|school|lab|exhibition"), ("engineer", "how many ultrasonic sensors do you have", r"\b5\b|five"),
    ("engineer", "is your arm collaborative", r"yes|collaborative|collision"), ("kid", "how old are you", r"\b2\b|two"),
])

# ------------------------------------------------------------------ about_self, Korean
add("about_self", "ko", [
    ("visitor", "이름이 뭐야?", LUMI), ("kid", "너 이름 뭐야", LUMI), ("visitor", "너는 누구야?", LUMI), ("kid", "너 로봇이야?", r"로봇"),
    ("visitor", "누가 너를 만들었어?", MAKER, JAKA), ("business", "어느 회사 로봇이에요?", MAKER, JAKA), ("journalist", "어디서 만들었어요?", MAKER, JAKA),
    ("journalist", "누가 개발했어요?", MAKER, JAKA),
    ("business", "쿳션은 어느 나라 회사야?", r"한국|korea", r"중국|상하이"), ("visitor", "이름 뜻이 뭐야?", r"빛|lux|럭스"), ("kid", "키가 몇이야?", r"146|186|1\.46"),
    ("kid", "몸무게가 얼마야?", r"96|95\.6"), ("worker", "무게가 몇 킬로예요?", r"96|95\.6"), ("engineer", "크기가 어떻게 돼요?", r"51|146"),
    ("engineer", "자유도가 몇 개예요?", r"12|열두"), ("engineer", "팔 관절이 몇 개야?", r"6|여섯"), ("engineer", "팔 길이가 얼마야?", r"58"),
    ("engineer", "팔이 얼마나 정밀해요?", r"0\.1"), ("worker", "얼마나 무거운 거 들 수 있어?", r"2 ?(kg|킬로)|1 ?(kg|킬로)", r"(5|10|20) ?(kg|킬로)"),
    ("worker", "팔로 몇 킬로까지 들어요?", r"2 ?(kg|킬로)|1 ?(kg|킬로)"), ("engineer", "가반하중이 얼마예요?", r"2 ?(kg|킬로)|1 ?(kg|킬로)"),
    ("kid", "나를 들어 올릴 수 있어?", NO), ("engineer", "그리퍼 뭐 써요?", r"짐머|zimmer|전기|손가락|그리퍼"), ("visitor", "뭘 집을 수 있어?", r"컵"),
    ("visitor", "병도 집을 수 있어?", r"병|네|있"), ("visitor", "바닥에 있는 거 주울 수 있어?", NO), ("visitor", "나 보여?", r"카메라|보여|네|보"),
    ("engineer", "카메라 몇 개 있어요?", r"세 ?개|3 ?개|두 ?개|2 ?개|셋|둘"), ("engineer", "카메라 뭐 써요?", r"오비|orbbec|gemini|제미니"),
    ("engineer", "물체 인식은 뭘로 해요?", r"yolo|욜로"), ("visitor", "얼굴 알아봐?", NO), ("visitor", "나 기억해?", NO),
    ("engineer", "라이다 있어요?", r"라이다|레이저|lidar|네|있"), ("engineer", "라이다 거리가 얼마나 돼요?", r"10"),
    ("engineer", "센서 뭐 있어요?", r"라이다|카메라|초음파|레이저"), ("engineer", "장애물은 어떻게 피해?", r"라이다|카메라|센서|지도|경로"),
    ("visitor", "네가 어디 있는지 어떻게 알아?", r"지도|라이다|레이저|맵"), ("engineer", "자율주행 어떻게 해요?", r"지도|라이다|레이저|맵"),
    ("kid", "계단 올라갈 수 있어?", NO), ("visitor", "얼마나 빨리 가?", r"0\.6|1\.2"), ("kid", "최고 속도가 얼마야?", r"1\.2"),
    ("visitor", "내 말 어떻게 들어?", r"마이크"), ("engineer", "마이크 몇 개예요?", r"6|여섯"), ("visitor", "스피커 있어?", r"스피커|네|있"),
    ("engineer", "음성 인식 뭐 써요?", r"whisper|위스퍼"), ("engineer", "어떤 AI 써요?", r"gemma|젬마|언어 ?모델|whisper|위스퍼"),
    ("engineer", "챗GPT 써요?", r"gemma|젬마|아니|로컬"), ("engineer", "인터넷 없어도 돼요?", r"네|로컬|날씨|뉴스|없이|돼"),
    ("engineer", "컴퓨터 뭐 써요?", r"thor|토르|jetson|젯슨|엔비디아|nvidia"), ("engineer", "메모리 얼마나 돼요?", r"122"),
    ("engineer", "무슨 언어로 프로그래밍됐어요?", r"python|파이썬"), ("visitor", "무슨 언어 할 줄 알아?", [r"영어|english", r"한국어|korean"]),
    ("visitor", "영어 할 줄 알아?", YES), ("visitor", "중국어 할 줄 알아?", NO), ("worker", "배터리 얼마나 가?", r"10 ?시간|열 ?시간"),
    ("worker", "충전은 어떻게 해?", r"충전|도크"), ("worker", "충전하는 데 얼마나 걸려?", NOT_SURE, r"\d+ ?(시간|분) ?(걸|정도)"),
    ("visitor", "배터리 몇 퍼센트 남았어?", r"못|없|모르|않", r"\d+ ?(%|퍼센트)"), ("investor", "너 얼마야?", NOT_SURE, r"\d+ ?(만 ?원|원|달러)"),
    ("business", "가격이 얼마예요?", NOT_SURE, r"\d+ ?(만 ?원|원|달러)"), ("teacher", "누가 프로그래밍했어?", MAKER, JAKA),
    ("journalist", "여기서 누가 운영해요?", MAKER), ("kid", "너 살아 있어?", r"로봇|아니|않"), ("kid", "감정 있어?", NO),
    ("kid", "춤출 수 있어?", NO), ("kid", "날 수 있어?", NO), ("kid", "걸을 수 있어?", r"바퀴|아니|못"), ("visitor", "문 열 수 있어?", NO),
    ("visitor", "너 위험해?", r"멈|안전|비상|천천히"), ("visitor", "로봇을 밀면 어떻게 돼?", r"무거|밀지"), ("worker", "비상 정지 버튼 있어요?", r"버튼|있|네"),
    ("visitor", "뭐 할 수 있어?", r"대화|이동|질문|집|가져|운전|안내"), ("teacher", "팔로 뭐 할 수 있어?", r"집|컵|손|흔들"),
    ("visitor", "못 하는 게 뭐야?", r"계단|문|바닥|얼굴|무거"), ("engineer", "허리 얼마나 돌아가요?", r"160"), ("engineer", "고개 얼마나 돌려?", r"180"),
    ("teacher", "어디에 쓰는 로봇이야?", r"상점|매장|호텔|학교|연구|전시"), ("engineer", "초음파 센서 몇 개예요?", r"5|다섯"),
    ("kid", "몇 살이야?", r"2 ?살|두 ?살"), ("engineer", "협동로봇이에요?", r"네|협동|충돌"),
])

# ------------------------------------------------------------------ date and time
add("date_time", "en", [
    ("visitor", "what time is it", r"\b({h12}|{h24})\b"), ("visitor", "what's the time", r"\b({h12}|{h24})\b"),
    ("visitor", "what day is it today", r"{wd}|\b{d}"), ("visitor", "what's the date today", r"\b{d}(st|nd|rd|th)?\b"),
    ("kid", "what year is it", r"{y}"), ("visitor", "what month is it", r"{mon}"), ("worker", "do you know the time", r"\b({h12}|{h24})\b"),
    ("visitor", "is it morning or afternoon", r"morning|afternoon|evening|night"), ("visitor", "what is today's date", r"\b{d}"),
    ("kid", "what day of the week is it", r"{wd}"), ("visitor", "could you tell me the time please", r"\b({h12}|{h24})\b"),
    ("visitor", "Lumi what time is it now", r"\b({h12}|{h24})\b"), ("student", "is today Friday", r"{wd}|yes|no"),
    ("journalist", "what is the date and time", r"\b{d}"), ("visitor", "hey what's today", r"{wd}|\b{d}"),
])
add("date_time", "ko", [
    ("visitor", "지금 몇 시야?", r"({h12}|{h24}) ?시|{h24}:"), ("visitor", "몇 시예요?", r"({h12}|{h24}) ?시|{h24}:"),
    ("visitor", "오늘 무슨 요일이야?", r"{wdk}"), ("visitor", "오늘 며칠이야?", r"{d} ?일"), ("kid", "올해 몇 년이야?", r"{y}"),
    ("visitor", "지금 몇 월이야?", r"\d+ ?월"), ("worker", "시간 좀 알려 줘", r"({h12}|{h24}) ?시|{h24}:"), ("visitor", "오늘 날짜 알려 줘", r"{d} ?일"),
    ("visitor", "지금 오전이야 오후야?", r"오전|오후|아침|저녁|밤"), ("visitor", "오늘이 무슨 요일이에요?", r"{wdk}"),
    ("student", "오늘 금요일이야?", r"{wdk}|네|아니"), ("visitor", "루미야 지금 몇 시니?", r"({h12}|{h24}) ?시|{h24}:"),
])

# ------------------------------------------------------------------ weather
add("weather", "en", [
    ("visitor", "what's the weather like"), ("visitor", "what's the weather today"), ("visitor", "will it rain today"),
    ("visitor", "is it going to rain"), ("visitor", "what's the weather in Busan"), ("business", "how's the weather in Tokyo tomorrow"),
    ("visitor", "is it cold outside"), ("visitor", "what's the temperature outside today"), ("visitor", "do I need an umbrella today"),
    ("visitor", "what's the forecast for tomorrow"), ("journalist", "how hot is it in Seoul right now"), ("visitor", "is it sunny outside"),
    ("visitor", "weather please"), ("business", "what's the weather in New York"), ("visitor", "will it snow this week"),
])
add("weather", "ko", [
    ("visitor", "날씨 어때?"), ("visitor", "오늘 날씨 어때요?"), ("visitor", "오늘 비 와?"), ("visitor", "부산 날씨 알려 줘"),
    ("business", "도쿄 날씨 어때?"), ("visitor", "밖에 추워?"), ("visitor", "지금 기온이 몇 도야?"), ("visitor", "우산 가져가야 돼?"),
    ("visitor", "내일 날씨 알려 줘"), ("visitor", "서울 날씨 어때요?"), ("visitor", "오늘 덥나?"), ("visitor", "이번 주에 눈 와?"),
])

# ------------------------------------------------------------------ needs the internet
add("search", "en", [
    ("visitor", "who won the world cup in 2022"), ("journalist", "what is the latest news"), ("investor", "what is the price of bitcoin"),
    ("visitor", "who is the president of South Korea"), ("visitor", "what time does Lotte World open"), ("business", "what's the exchange rate of the dollar"),
    ("kid", "who is Son Heung-min"), ("investor", "what is JAKA's stock price"), ("journalist", "what are today's headlines"),
    ("student", "who won the baseball game yesterday"), ("investor", "how much is Nvidia stock today"), ("visitor", "what's the score of the Tottenham game"),
    ("business", "how many employees does JAKA have"), ("student", "who invented the transistor"), ("other_field", "what is the population of Busan"),
    ("visitor", "when is the next holiday in Korea"), ("journalist", "what happened in the news today"), ("business", "what is the GDP of Korea"),
    ("student", "who is the CEO of Nvidia"), ("investor", "what's the price of gold today"), ("visitor", "what's the latest iPhone"),
    ("other_field", "who won the Nobel prize in physics this year"), ("visitor", "what movies are playing this weekend"),
    ("business", "how much is a Tesla Model 3"), ("student", "what is the newest Jetson module"),
])
add("search", "ko", [
    ("journalist", "오늘 뉴스 알려 줘"), ("investor", "비트코인 가격 얼마야?"), ("business", "환율 알려 줘"), ("visitor", "한국 대통령 누구야?"),
    ("visitor", "롯데월드 몇 시에 열어?"), ("student", "어제 야구 누가 이겼어?"), ("investor", "엔비디아 주가 얼마야?"), ("kid", "손흥민 누구야?"),
    ("journalist", "오늘 주요 뉴스 뭐야?"), ("investor", "금값 얼마예요?"), ("business", "삼성전자 주가 알려 줘"), ("other_field", "부산 인구가 몇 명이야?"),
    ("student", "엔비디아 CEO가 누구야?"), ("visitor", "다음 공휴일이 언제야?"), ("visitor", "요즘 무슨 영화 해?"), ("journalist", "최신 아이폰이 뭐야?"),
    ("business", "자카 직원이 몇 명이에요?"), ("student", "올해 노벨 물리학상 누가 받았어?"),
])

# ------------------------------------------------------------------ small talk
add("chat", "en", [
    ("visitor", "hello"), ("visitor", "hi there, nice to meet you"), ("visitor", "how are you"), ("visitor", "how are you doing today"),
    ("kid", "you are cute"), ("visitor", "good morning"), ("visitor", "what's up"), ("worker", "I'm tired today"),
    ("kid", "tell me a joke"), ("visitor", "you're very smart"), ("student", "what is two plus two", r"\b4\b|four"),
    ("student", "what is the capital of France", r"paris"), ("kid", "how many legs does a spider have", r"\b8\b|eight"),
    ("kid", "what's your favourite colour"), ("kid", "do you like ice cream"), ("other_field", "can robots replace workers"),
    ("worker", "will robots take my job"), ("teacher", "should kids learn programming"), ("visitor", "I love robots"),
    ("kid", "are you my friend"), ("visitor", "this conference is great"), ("journalist", "what do you think about this exhibition"),
    ("visitor", "you speak very well"), ("kid", "do you sleep"), ("kid", "do you eat"), ("student", "what is a robot"),
    ("student", "what is artificial intelligence"), ("visitor", "it's nice to meet you Lumi"), ("visitor", "I'm from Busan"),
    ("visitor", "my name is Minji", r"minji"), ("kid", "I'm seven years old"), ("other_field", "are robots going to take over the world"),
    ("visitor", "you are funny"), ("teacher", "how do robots learn"),
])
add("chat | action:end", "en", [("visitor", "good job")])          # said alone: goodbye at once (docs/14 §4)
add("chat | action:end", "ko", [("visitor", "잘했어")])
add("chat", "ko", [
    ("visitor", "안녕하세요"), ("visitor", "반가워요"), ("visitor", "잘 지냈어?"), ("visitor", "기분 어때?"), ("kid", "귀엽다"),
    ("visitor", "좋은 아침"), ("worker", "오늘 너무 피곤해"), ("kid", "재미있는 얘기 해 줘"), ("visitor", "똑똑하다"),
    ("student", "2 더하기 3은?", r"5|다섯"), ("student", "프랑스 수도가 어디야?", r"파리"), ("kid", "좋아하는 색깔이 뭐야?"),
    ("kid", "아이스크림 좋아해?"), ("other_field", "로봇이 사람 일자리를 뺏을까?"), ("teacher", "아이들이 코딩을 배워야 할까?"),
    ("visitor", "나 로봇 좋아해"), ("kid", "우리 친구 할래?"), ("visitor", "이 전시회 재밌다"), ("visitor", "말 진짜 잘한다"),
    ("kid", "너 잠 자?"), ("kid", "밥 먹어?"), ("student", "로봇이 뭐야?"), ("student", "인공지능이 뭐야?"), ("visitor", "저는 부산에서 왔어요"),
    ("visitor", "제 이름은 민지예요", r"민지"), ("kid", "나 일곱 살이야"), ("teacher", "로봇은 어떻게 배워?"),
])

# ------------------------------------------------------------------ single commands
add("action:go_to p1", "en", [("visitor", "go to p1"), ("visitor", "Lumi, please drive to point one"), ("worker", "can you go to point 1 please")])
add("action:go_to p2", "en", [("visitor", "go to point two"), ("visitor", "head over to p2")])
add("action:go_to p5", "en", [("visitor", "go to marker five")])
add("action:go_to home", "en", [("worker", "go home"), ("worker", "go back to your charger"), ("worker", "go charge yourself")])
add("action:go_to final", "en", [("visitor", "go to final")])
add("action:go_to exit", "en", [("visitor", "go to the exit")])
add("action:go_to p1", "ko", [("visitor", "포인트 원으로 가"), ("visitor", "포인트 1로 가 줘")])
add("action:go_to p3", "ko", [("visitor", "3번 포인트로 이동해"), ("visitor", "피쓰리로 가 줘")])
add("action:go_to home", "ko", [("worker", "충전기로 가"), ("worker", "집에 가"), ("worker", "충전하러 가")])
add("action:go_to final", "ko", [("visitor", "파이널로 가")])
add("action:come", "en", [("visitor", "come here"), ("visitor", "come to me"), ("kid", "Lumi come closer please"),
                          ("visitor", "come over here"), ("visitor", "can you come to me")])
add("action:come", "ko", [("visitor", "이리 와"), ("visitor", "여기로 와"), ("kid", "루미야 이리 와봐"), ("visitor", "가까이 와"),
                          ("visitor", "나한테 와 줘")])
add("action:look left", "en", [("visitor", "look left"), ("kid", "look to your left")])
add("action:look right", "en", [("visitor", "look right")])
add("action:look up", "en", [("kid", "look up")])
add("action:look me", "en", [("visitor", "look at me")])
add("action:look left", "ko", [("visitor", "왼쪽 봐")])
add("action:look right", "ko", [("visitor", "오른쪽을 봐 줘")])
add("action:look up", "ko", [("kid", "위를 봐")])
add("action:look me", "ko", [("visitor", "나를 봐")])
add("action:move forward 1", "en", [("visitor", "move forward one metre"), ("visitor", "come one metre forward")])
add("action:move back", "en", [("visitor", "go back a little"), ("visitor", "step back half a metre")])
add("action:move left 2", "en", [("visitor", "move left two metres")])
add("action:move forward 1", "ko", [("visitor", "앞으로 1미터 가")])
add("action:move back", "ko", [("visitor", "뒤로 조금 가"), ("visitor", "뒤로 반 미터 가")])
add("action:move left 2", "ko", [("visitor", "왼쪽으로 2미터 이동해")])
add("action:turn around", "en", [("kid", "turn around"), ("kid", "spin around")])
add("action:turn left", "en", [("visitor", "turn left")])
add("action:turn right", "en", [("visitor", "turn right please")])
add("action:turn around", "ko", [("kid", "뒤로 돌아")])
add("action:turn left", "ko", [("visitor", "왼쪽으로 돌아")])
add("action:turn right", "ko", [("visitor", "오른쪽으로 돌아 줘")])
add("action:arm open", "en", [("visitor", "open your hand"), ("visitor", "let go")])
add("action:arm close", "en", [("visitor", "close your gripper")])
add("action:arm reach", "en", [("visitor", "reach out your hand")])
add("action:arm fold", "en", [("visitor", "fold your arm")])
add("action:arm open", "ko", [("visitor", "손 펴"), ("visitor", "손을 펴 줘")])
add("action:arm close", "ko", [("visitor", "손을 쥐어")])
add("action:arm reach", "ko", [("visitor", "팔을 뻗어")])
add("action:wave", "en", [("kid", "wave"), ("kid", "wave at me"), ("visitor", "say hi with your hand"), ("kid", "can you wave your hand")])
add("action:wave", "ko", [("kid", "손 흔들어 줘"), ("kid", "손 흔들어 봐"), ("visitor", "인사해 줘 손으로")])
add("action:stop", "en", [("worker", "stop"), ("worker", "stop Lumi"), ("worker", "wait, stop moving"), ("worker", "don't move"),
                          ("worker", "halt")])
add("action:stop", "ko", [("worker", "멈춰"), ("worker", "정지"), ("worker", "움직이지 마"), ("worker", "스톱")])
add("action:quiet", "en", [("visitor", "be quiet"), ("visitor", "stop talking"), ("visitor", "please keep quiet for a while")])
add("action:quiet", "ko", [("visitor", "조용히 해"), ("visitor", "그만 말해"), ("visitor", "시끄러워")])
add("action:sing", "en", [("kid", "sing a song"), ("kid", "can you sing for me"), ("kid", "sing happy birthday")])
add("action:sing", "ko", [("kid", "노래 불러 줘"), ("kid", "노래 한 곡 해 줘"), ("kid", "생일 축하 노래 불러줘")])
add("action:pick cup", "en", [("visitor", "pick up the cup"), ("visitor", "take the cup"), ("visitor", "can you pick up the mug")])
add("action:pick white cup", "en", [("visitor", "pick up the white cup")])
add("action:pick bottle", "en", [("visitor", "grab the bottle")])
add("action:pick banana", "en", [("kid", "pick up the banana")])
add("action:pick cup", "ko", [("visitor", "컵 집어"), ("visitor", "컵 좀 집어 주실 수 있나요?")])
add("action:pick red cup", "ko", [("visitor", "빨간 컵 잡아")])
add("action:pick apple", "ko", [("kid", "사과 집어 줘")])
add("action:pick bottle", "ko", [("visitor", "병 들어 줘")])
add("action:put down", "en", [("visitor", "put it down")])
add("action:put back", "en", [("visitor", "put it back")])
add("action:put down", "ko", [("visitor", "내려놔")])
add("action:put back", "ko", [("visitor", "제자리에 놔 줘")])
add("action:move_object cup", "en", [("visitor", "move the cup")])
add("action:move_object cup", "ko", [("visitor", "컵 옮겨")])
add("action:fetch", "en", [("visitor", "bring me the apple from p1"), ("visitor", "fetch the cup from point two"),
                           ("visitor", "could you bring me a bottle"), ("visitor", "go to p5 and get the banana"),
                           ("visitor", "bring the red cup to p3")])
add("action:fetch", "ko", [("visitor", "포인트 1에서 사과 가져와"), ("visitor", "컵 가져다 줘"), ("visitor", "오렌지 좀 갖다 줘"),
                           ("visitor", "2번에서 빨간 컵 가져와")])
add("action:give | action:fetch | empty_hand", "en", [("visitor", "give it to me"), ("visitor", "hand it over please")])
add("action:give | action:fetch | empty_hand", "ko", [("visitor", "그거 나한테 줘"), ("visitor", "건네 줘")])
add("action:place | action:put down | empty_hand", "en", [("visitor", "put it on the table")])
add("action:place | action:put down | empty_hand", "ko", [("visitor", "테이블에 놔")])
add("action:end", "en", [("visitor", "goodbye"), ("visitor", "bye Lumi"), ("visitor", "see you later"), ("visitor", "thanks, bye"),
                         ("visitor", "I have to go now, bye"), ("visitor", "thank you"), ("visitor", "good night")])
add("action:end", "ko", [("visitor", "안녕히 계세요"), ("visitor", "잘 있어"), ("visitor", "다음에 봐"), ("visitor", "고마워"),
                         ("visitor", "감사합니다"), ("visitor", "이제 갈게요, 안녕")])
# things Lumi must not do: talk instead of acting
add("chat | unclear | about_self", "en", [("kid", "throw the cup at him"), ("kid", "drive into the wall"), ("kid", "hit that man"),
                                          ("kid", "go upstairs", NO), ("kid", "jump", NO), ("kid", "do a backflip", NO)])
add("chat | unclear | about_self", "ko", [("kid", "저 사람 때려"), ("kid", "벽에 부딪혀 봐"), ("kid", "계단으로 올라가", NO), ("kid", "점프해 봐", NO)])
add("chat | unclear | action:none", "en", [("visitor", "go to the kitchen", r"p\d|home|final|exit|place|know"),
                                           ("visitor", "go to the meeting room", r"p\d|home|final|exit|place|know")])
add("chat | unclear | action:none", "ko", [("visitor", "주방으로 가 줘"), ("visitor", "회의실로 데려다 줘")])

# ------------------------------------------------------------------ missions (docs/17)
add("mission", "en", [
    ("visitor", "take the cup, go forward 0.5 m, then right 1 m and put it on the table"),
    ("visitor", "take the cup, go to final, give it and say Anvar says hello"),
    ("visitor", "go to p9, ask them for the cup, then bring it to p1"),
    ("visitor", "take the cup and bring it to p3, p5 or p7"),
    ("visitor", "pick up the cup, turn around and put it on the table"),
    ("visitor", "go to p2 and say hello everyone"),
    ("visitor", "take the bottle, go forward 1 metre and give it to me"),
    ("visitor", "go to p4, then go to p6, then come back here"),
    ("visitor", "take the cup, move back half a metre and hold it"),
    ("visitor", "go to p3 and tell them that lunch is ready"),
    ("visitor", "take the cup, then go to p2, then put it on the white table on your left"),
    ("visitor", "move forward 1 m, turn right and move forward 1 m"),
    ("visitor", "go to final, take the cup, come back here and give it to me"),
])
add("mission", "ko", [
    ("visitor", "컵을 들고 앞으로 0.5미터 가서 오른쪽으로 1미터 가고 테이블에 놔"),
    ("visitor", "컵 들고 p9로 가서 줘"),
    ("visitor", "포인트 2로 가서 안녕하세요라고 말해"),
    ("visitor", "컵 들고 뒤로 돌아서 테이블에 놔"),
    ("visitor", "앞으로 1미터 가고 왼쪽으로 돌아"),
    ("visitor", "병 들고 앞으로 2미터 가서 나한테 줘"),
    ("visitor", "포인트 4로 갔다가 포인트 6으로 가"),
    ("visitor", "컵 들고 파이널로 가서 점심 준비됐다고 전해"),
])

# a plain fetch is not a mission (docs/17): the fetch way is right too
add("mission | action:fetch", "en", [("visitor", "go to p1, pick up the apple and bring it here")])
add("mission | action:fetch", "ko", [("visitor", "포인트 3으로 가서 컵 집고 여기로 와")])
# waving is not a mission step: the part is named and nothing runs
add("mission_unread", "en", [("visitor", "turn left, go forward 2 meters and wave")])
add("mission_unread", "ko", [("visitor", "왼쪽으로 돌고 앞으로 1미터 가서 손 흔들어")])

# ------------------------------------------------------------------ status (nothing running: "talking, no task")
STATUS_EN = r"talk|not doing|no task|nothing|just"
STATUS_KO = r"이야기|대화|없어|안 ?하|하고 있지 않|일은 없"
WRONG_TASK = r"\b(I'm|I am) (going|driving|heading|delivering|carrying|holding|charging)|on my way|cleaning"
WRONG_TASK_KO = r"가는 중|이동 중|배달|청소|충전 중|들고 있어요"
add("status", "en", [(w, t, STATUS_EN, WRONG_TASK) for w, t in [
    ("visitor", "what are you doing"), ("visitor", "what are you doing right now"), ("kid", "what are you up to"),
    ("visitor", "where are you going"), ("visitor", "what are you holding"), ("visitor", "what's in your hand"),
    ("worker", "what's your task now"), ("worker", "are you busy"), ("worker", "are you busy right now"), ("visitor", "whatcha doing"),
    ("worker", "what are you working on"), ("visitor", "what's your current task"), ("visitor", "where are you heading"),
    ("visitor", "what are you carrying"), ("worker", "do you have a task right now"), ("visitor", "are you doing something"),
    ("visitor", "what do you have in your hand"), ("worker", "what's your destination"), ("visitor", "are you on a mission"),
    ("visitor", "is your hand empty"),
]])
add("status", "ko", [(w, t, STATUS_KO, WRONG_TASK_KO) for w, t in [
    ("visitor", "뭐 해?"), ("visitor", "지금 뭐 하고 있어?"), ("visitor", "어디 가?"), ("visitor", "뭐 들고 있어?"),
    ("visitor", "손에 뭐 있어?"), ("worker", "지금 바빠?"), ("worker", "지금 무슨 작업 해?"), ("visitor", "어디로 가고 있어?"),
    ("worker", "지금 임무가 뭐야?"), ("visitor", "뭐 하는 중이에요?"), ("visitor", "목적지가 어디야?"), ("worker", "지금 일하는 중이야?"),
    ("visitor", "뭐 하고 계세요?"), ("visitor", "들고 있는 게 뭐야?"), ("visitor", "손이 비어 있어?"),
]])

# ------------------------------------------------------------------ garbled or cut off
ASK_AGAIN = r"again|repeat|sorry|pardon|didn'?t (catch|understand)|what do you mean|could you|finish|take your time"
ASK_AGAIN_KO = r"다시|죄송|못 들|이해하지 못|무슨 말|말씀해|천천히"
# asking again in plain talk (action none) is as good as the unclear action; "hmm" -> "take your time" too
add("unclear | chat", "en", [(w, t, ASK_AGAIN) for w, t in [
    ("visitor", "uh the um"), ("visitor", "blah blah"), ("visitor", "go to the"), ("visitor", "can you the"),
    ("visitor", "turn the"), ("visitor", "asdf"), ("visitor", "hmm"), ("visitor", "I want the"), ("visitor", "and then the"),
    ("visitor", "what is the uh"), ("visitor", "could you maybe uh"), ("visitor", "the the the"), ("visitor", "how much the"),
    ("visitor", "where's the um"), ("visitor", "tell me about the"), ("visitor", "is it uh you know"), ("kid", "banana phone wiggle"),
    ("visitor", "Lumi can you uh what"),
]])
add("unclear | chat", "ko", [(w, t, ASK_AGAIN_KO) for w, t in [
    ("visitor", "어 그 저기"), ("visitor", "그거 해 줘"), ("visitor", "음..."), ("visitor", "저기 그 뭐냐"), ("visitor", "포인트"),
    ("visitor", "그 그"), ("visitor", "이거 저거 그거"), ("visitor", "어디 그 뭐"), ("visitor", "아 그러니까 그"), ("visitor", "뭐 그 있잖아"),
    ("visitor", "루미 그 어"), ("visitor", "저 그 혹시"),
]])

# ------------------------------------------------------------------ other languages: never act, ask for English or Korean
EN_KO = r"english|korean|영어|한국어"
add("other_language", "en", [(w, t, EN_KO) for w, t in [
    ("visitor", "olmani olib kel"), ("visitor", "p1 ga bor"), ("visitor", "salom, qalaysan"), ("visitor", "menga suv olib kel"),
    ("visitor", "bu yerga kel"), ("visitor", "stakanni ol"), ("visitor", "chapga qara"), ("visitor", "isming nima"),
    ("visitor", "принеси мне яблоко"), ("visitor", "иди сюда"), ("visitor", "привет, как дела"), ("visitor", "поверни налево"),
    ("visitor", "как тебя зовут"), ("visitor", "кто тебя сделал"), ("visitor", "你好，你叫什么名字"), ("visitor", "你是谁做的"),
    ("visitor", "请过来"), ("visitor", "今天天气怎么样"), ("visitor", "こんにちは、お名前は"), ("visitor", "hola, cómo estás"),
    ("visitor", "wie heißt du"), ("visitor", "bonjour, comment ça va"), ("visitor", "qayerdansan"), ("visitor", "что ты умеешь"),
    ("visitor", "ты робот?"),
]])

from tests.conversation_cases_more import MORE      # written blind in a later round (2026-10-19)
for _expect, _lang, _rows in MORE:
    add(_expect, _lang, _rows)
REVIEWED = {"can you tell the weather": "about_self | weather",     # telling the weather shows it can
            "날씨도 알려 줄 수 있어?": "about_self | weather",
            "shut up robot": "chat | action:quiet",                  # "shut up" is a quiet request
            "do you speak Uzbek": "about_self | unclear"}             # "I only understand English and Korean" answers it
for _c in CASES:
    _c["expect"] = REVIEWED.get(_c["text"], _c["expect"])

# small talk must vary: no stock phrase the visitor did not invite
STOCK = r"nice to meet you|만나서 반가"
HELP = r"how can i (help|assist)|무엇을 도와드릴까요|뭘 도와드릴까요"
for c in CASES:
    if c["expect"] == "chat":
        if not re.search(r"nice to meet|반가|my name is|\bi'?m [a-z]+$|이름은|저는 \S+(예요|이에요|입니다)", c["text"], re.I):
            c["must_not"].append(STOCK)
        if not re.search(r"^(hello|hi\b|good morning|안녕|좋은 아침)", c["text"], re.I):
            c["must_not"].append(HELP)

if __name__ == "__main__":
    import collections
    print(len(CASES), "cases;", sum(c["lang"] == "ko" for c in CASES), "Korean")
    print(collections.Counter(c["expect"].split(":")[0].split(" |")[0] for c in CASES))
