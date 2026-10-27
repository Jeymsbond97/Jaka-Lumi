"""Dev eval of quick answers on wordings written apart from the bank. python qa_eval.py"""
import sys
sys.path.insert(0, __file__.rsplit("/tests/", 1)[0])
from assistant import quick_answers as qa

POS = {
 "name": ["Hey, what is your name?", "Could you tell me your name?", "What name do you go by?", "Robot, what's ur name",
          "and your name is?", "Do you have a name, robot?", "너는 이름이 뭐니?", "이름 좀 알려 주세요", "이름이 뭐라고요?",
          "니 이름이 뭐고", "이름이 어떻게 되십니까?", "자네 이름은?", "얘 이름 뭐야?", "what's your 이름?", "네 이름은 뭐야",
          "What do I call you?", "your name please", "이름 뭐야?", "님 이름이 뭐예요", "로봇아 이름이 뭐야"],
 "age": ["How old are you, Lumi?", "What age are you?", "How many years have you been around?", "When were you created?",
         "Lumi, how old r you?", "너 나이가 어떻게 돼?", "몇 살이니?", "나이 몇이에요?", "올해 몇 살이야?", "몇 살이십니까?",
         "언제 만들어졌니?", "태어난 지 얼마나 됐어요?", "몇 년 됐어요 너?", "니 나이 몇이고", "how old is the robot?", "your age is?",
         "만들어진 지 몇 년 됐어요?", "너 몇살이야"],
 "maker": ["Who made this robot?", "Who's your developer?", "Which company developed you?", "Who manufactured you?",
           "what company built you?", "Who designed and built you?", "Where were you made?", "who is your manufacturer",
           "누가 너를 만들었니?", "누가 만들었습니까?", "만든 회사가 어디예요?", "어디서 개발했어요?", "제조사가 어디야?",
           "너 어느 회사 거야?", "누가 개발했니", "어디 회사 거예요?", "개발사가 어디예요", "who made u", "너 누가 만들었어?",
           "어디 제품이에요?"],
 "who": ["What are you?", "Tell me about you.", "Please introduce yourself.", "Who exactly are you?", "So who are you?",
         "What kind of robot is this?", "What is this thing?", "Can you introduce yourself?", "너는 누구니?", "당신은 누구십니까?",
         "자기소개 부탁해요", "너 정체가 뭐야?", "넌 뭐니?", "소개 좀 해 봐", "어떤 로봇이야?", "이 로봇 뭐야?", "자기소개 해 봐",
         "who are u", "넌 뭐 하는 로봇이야?", "what do you do?"],
 "height": ["How tall are you, Lumi?", "What is your height in cm?", "How tall is this thing?", "how many centimeters tall are you",
            "너 키가 얼마야?", "키 몇 센티야?", "키가 어떻게 돼요?", "키가 몇 센티미터예요?", "신장이 얼마예요?", "키 얼마나 돼?",
            "니 키 몇이고", "how tall r you", "키가 몇이니?"],
 "weight": ["How heavy are you, Lumi?", "What do you weigh?", "How many kilos are you?", "how many kg do you weigh",
            "너 무게가 얼마야?", "몸무게 몇이에요?", "몇 킬로그램이에요?", "무게 얼마나 나가요?", "너 무거워?", "체중이 얼마예요?"],
 "battery_life": ["How long does your battery last on a charge?", "How many hours can you run?", "How long can you operate?",
                  "What's your battery life like?", "How long until you need charging?", "배터리 몇 시간 쓸 수 있어?",
                  "한 번 충전으로 얼마나 가요?", "배터리 지속 시간이 얼마예요?", "충전하면 몇 시간 가?", "몇 시간 동안 움직일 수 있어요?",
                  "배터리가 얼마나 오래 가요?", "배터리 몇 시간 버텨?"],
 "languages": ["Which languages can you speak?", "Do you speak English?", "Can you talk in Korean?", "Can you speak Japanese?",
               "Do you know Chinese?", "What languages do you know?", "Can you understand Spanish?", "영어 할 수 있어요?",
               "한국어 알아?", "일본어 할 줄 아세요?", "몇 개 언어 할 수 있어?", "무슨 말 할 줄 알아?", "중국어 돼?", "영어 돼요?",
               "speak english?", "can you speak 한국어?"],
 "chatgpt": ["Are you ChatGPT?", "Is this ChatGPT inside?", "Do you run on GPT?", "Are you based on ChatGPT?",
             "너 지피티야?", "챗GPT예요?", "챗지피티 기반이야?", "are you like chatgpt?", "Do you use OpenAI?"],
 "model": ["What AI model are you using?", "Which LLM do you use?", "What language model runs you?", "What is your AI?",
           "어떤 AI 모델 써?", "무슨 언어 모델이야?", "인공지능 모델이 뭐예요?", "너 무슨 AI야?", "what ai model 써?", "which ai are you based on"],
 "robot": ["Are you a real robot?", "Are you alive?", "Are you a human?", "Is someone inside you?", "Do you have feelings?",
           "Can you feel emotions?", "Are you human or robot?", "너 사람이야?", "너 진짜 로봇이야?", "살아 있어요?", "감정을 느껴?",
           "누가 조종하는 거야?", "사람이 안에 있어?", "너 기계야?", "are you an AI?", "너 AI야?"],
 "speed": ["How fast can you drive?", "What's your top speed?", "How quickly can you move?", "What is your maximum speed?",
           "너 얼마나 빨리 달려?", "속도가 얼마나 돼요?", "최대 속도가 얼마예요?", "얼마나 빨라?", "how fast r u"],
 "hello": ["Hello there!", "Hi Lumi!", "Hey Lumi", "Good morning, Lumi", "Hello, robot", "Hey hey", "안녕 루미",
           "안녕하세요 루미", "하이 루미야", "안녕?", "방가방가", "반갑습니다", "헬로 루미", "hello 루미", "좋은 아침", "Greetings"],
 "how_are_you": ["How are you?", "How are you doing today?", "How's your day going?", "Are you doing well?", "You okay?",
                 "잘 지냈어?", "오늘 어때요?", "잘 지내요?", "기분이 어때?", "컨디션 어때?", "how are you 루미", "how's it going, lumi"],
 "name_meaning": ["What does Lumi mean?", "Why is your name Lumi?", "Where does your name come from?", "루미 무슨 뜻이에요?",
                  "왜 루미라고 불러?", "이름 뜻이 뭐야?"],
}
NEG = ["can you see me?", "what am I wearing?", "how old do I look?", "what colour is my bag?", "come here please",
       "follow me", "wave at me", "sing something", "go to the stage", "tell me a joke", "what can you do?",
       "how much can you lift?", "how long does it take to charge?", "how much battery is left?",
       "how many employees work there?", "what's the weather today?",
       "thanks", "thank you so much", "goodbye", "okay", "why?", "really?", "and you?", "how old?", "what's my name?",
       "how tall am I?", "who made your arm?", "who made the barista robot?", "how much do you cost?", "얼마예요?",
       "나 몇 살로 보여?", "내 이름 뭐게?", "이리 와", "따라와", "노래해 줘", "날씨 어때?", "고마워", "잘 가",
       "왜?", "진짜?", "넌?", "충전 얼마나 걸려?", "배터리 몇 퍼센트야?",
       "뭐 할 수 있어?", "몇 킬로까지 들어?", "how tall is the eiffel tower?", "how old is taylor swift?", "who made the iphone?",
       "what's the name of this event?", "what is jaka?", "who made jaka robots?",
       "what is your favorite color?", "do you like music?", "where am I?", "where are we?",
       "what is your battery level?", "are you tired?", "are you hungry?", "what languages does cutshion use?",
       "how tall is your arm?", "what's my age?", "이 행사 이름 뭐야?", "여기 어디야?",
       "how far can you see?", "do you know my name?", "where's the toilet?", "what do you think about AI?"]

POS.update({
 "size": ["How wide is Lumi?", "What are your dimensions, robot?", "너 폭이 몇이야?", "크기가 어떻게 되십니까?", "가로세로 몇 센티예요?",
          "how much space do you take up?", "로봇 사이즈 좀 알려 주세요", "너비가 몇이고?"],
 "payload": ["What is your payload capacity?", "Max payload of the arm?", "가반하중은 얼마나 되나요?", "최대 몇 킬로까지 집으세요?",
             "how heavy a thing can your gripper pick?", "가반하중 몇 키로고?"],
 "arm": ["What sort of arm is that?", "Which robot arm do you use?", "팔은 무슨 모델이에요?", "팔 길이가 몇 센티야?", "how far is your reach?",
         "팔이 어디까지 닿습니까?", "팔 하나밖에 없어?"],
 "gripper": ["What kind of gripper is on you?", "How many fingers have you got?", "그리퍼는 무슨 제품이에요?", "손가락이 몇 개니?",
             "집게는 뭐 써?"],
 "lidar": ["Is there a lidar on you?", "How far can the lidar measure?", "라이다 달려 있니?", "라이다 있으십니까?", "레이저 스캐너 있어?"],
 "sensors": ["Which sensors are on this robot?", "What sensors do you use?", "센서 어떤 게 달려 있어요?", "무슨 센서 있니?", "센서 몇 개 달렸노?"],
 "stairs": ["Can you go up the stairs?", "Are you able to climb stairs?", "계단도 올라가니?", "계단 오르실 수 있습니까?", "턱 넘을 수 있나?",
            "can you climb a ramp?"],
 "turn_range": ["How far does your head rotate?", "Can you spin your head all the way around?", "고개 얼마나 돌아가니?", "허리는 몇 도 돌아가요?",
                "머리 360도 돌릴 수 있어?"],
 "grow": ["Can you become taller?", "What is your max height?", "키 늘릴 수 있어요?", "최대 몇 센티까지 커져?", "키 높이 조절되나요?"],
 "charging": ["How do you recharge yourself?", "Do you charge on your own?", "충전은 어떻게 하세요?", "혼자 충전하러 가요?",
              "배터리 떨어지면 어떡해요?"],
 "battery_spec": ["What type of battery do you use?", "How many volts?", "배터리 종류 뭐야?", "배터리 용량이 몇이에요?"],
 "navigation": ["How do you find the way?", "Do you drive by yourself?", "자율주행 되니?", "길은 어떻게 찾으세요?", "지도 가지고 있어?",
                "are you self-driving?"],
 "obstacles": ["How do you not bump into people?", "Do you avoid obstacles?", "장애물은 어떻게 피하니?", "사람한테 안 부딪혀요?"],
 "dance": ["Are you able to dance?", "Can you walk around?", "춤 출 수 있니?", "걸어 다닐 수 있어요?", "do you have any legs?", "날 수 있니?"],
 "doors": ["Are you able to open a door?", "문 여실 수 있어요?", "문 열 줄 아니?"],
 "software": ["What language is your software in?", "Is your code Python?", "프로그램 무슨 언어로 짰어요?", "소프트웨어 뭘로 만들었어?"],
 "detector": ["What model detects objects?", "Do you run YOLO?", "물체 인식 모델 뭐야?", "사람 인식은 어떻게 하세요?"],
 "teach": ["Can people teach you new skills?", "Are you able to learn?", "새로운 거 배울 수 있어요?", "가르치면 배우니?"],
 "touch": ["Is it OK to touch the robot?", "Can children touch you?", "만져 봐도 돼요?", "만져도 되니?"],
 "accuracy": ["How precise is your arm?", "What is your precision?", "정밀도가 얼마나 돼요?", "오차가 얼마나 나?"],
 "pick_what": ["What can you pick?", "Which objects can you grab?", "뭐 집을 수 있어요?", "바닥에서 주울 수 있니?"],
 "operator": ["Who is in charge of you here?", "Who operates this robot?", "누가 관리하세요?", "담당자 누구야?"],
})
NEG += ["turn your head left", "tilt your head down", "고개 돌려", "허리 오른쪽으로 돌려", "go to the charger", "충전하러 가자",
        "dance please", "춤 한번 춰 봐", "open the door for me", "문 좀 열어 주세요", "pick up the red cup", "빨간 컵 집어 줘",
        "how wide is the hallway", "복도 폭이 얼마예요", "where are the stairs", "엘리베이터 어디 있어요", "who's the staff here?",
        "how do I charge my phone?", "핸드폰 충전 어디서 해요?", "does the barista robot have a lidar?", "바리스타 로봇 팔 몇 축이에요?",
        "do you like to dance?", "춤 좋아해?", "lift your arm", "팔 들어", "reach out your hand", "손 내밀어 줘"]

POS.update({
 "co_what": ["What's Cutshion?", "Tell me about Cutshion Company.", "쿳션은 무슨 회사예요?", "쿳션이 뭐 하는 회사니?", "쿳션 뭐 하는 데고?"],
 "co_founded": ["How old is Cutshion?", "When did Cutshion start?", "쿳션 몇 년 됐어?", "쿳션은 언제 설립되었습니까?", "회사 언제 만들어졌어요?"],
 "co_ceo": ["Who is the CEO of Cutshion?", "Who founded Cutshion?", "쿳션 대표가 누구야?", "쿳션 대표님 성함이 어떻게 되십니까?", "사장님 누구예요?"],
 "co_hq": ["Where is Cutshion located?", "Cutshion address?", "쿳션 어디에 있어요?", "쿳션 본사 위치가 어떻게 돼요?", "회사 주소 좀 알려 주세요"],
 "co_contact": ["How can I reach Cutshion?", "Cutshion's phone number please", "쿳션 전화번호 알려 줘", "쿳션 연락처가 어떻게 되나요?",
                "쿳션 이메일 주소 뭐예요?"],
 "co_products": ["What robots does Cutshion make?", "Which products does Cutshion sell?", "쿳션 무슨 로봇 만들어요?", "쿳션 제품 뭐가 있나요?"],
 "co_awards": ["Has Cutshion won awards?", "쿳션 상 받은 적 있어요?", "쿳션 수상 경력 알려 주세요"],
 "co_unknown": ["How many employees does Cutshion have?", "직원 몇 명이에요?", "쿳션 매출 얼마예요?", "Is Cutshion hiring?", "쿳션 직원 수가 몇 명이에요?"],
 "co_icecream": ["How heavy is the ice cream robot?", "How fast is the ice cream robot?", "아이스크림 로봇은 뭐예요?", "Tell me about the ice cream robot"],
 "co_barista": ["What does the barista robot do?", "바리스타 로봇 뭐 하는 거예요?", "커피 로봇 설명해 주세요"],
 "co_candyball": ["What's the candy ball robot?", "캔디볼 로봇이 뭐야?"],
 "co_pionoid": ["What is Pionoid?", "피오노이드가 뭐예요?"],
 "price": ["Is Lumi for sale?", "가격이 어떻게 되나요?", "이 로봇 가격 좀 알려 주세요", "Can I rent this robot?", "렌탈 가능해요?"],
})
NEG += ["does the barista robot have a lidar?", "make me a latte", "라떼 한 잔 만들어 줘", "where's the coffee robot?", "바리스타 로봇 어디 있어?",
        "what is samsung?", "who is the CEO of Google?", "애플 대표가 누구야?", "커피 얼마예요?", "this cushion is comfy"]
POS.update({   # night 4, round 2
 "paper_cup": ["can you grab a paper cup?", "Could you hold a paper coffee cup?", "종이컵도 집으실 수 있나요?", "종이컵 잡을 수 있겠나?",
               "종이컵은 잡을 수 있습니까?"],
 "arm_weight": ["How much does the arm itself weigh?", "팔 무게는 얼마나 됩니까?", "팔이 몇 kg이에요?", "팔 무게 얼마고?"],
 "short_move": ["How far do you go when I say move forward?", "앞으로 가 하면 최대 몇 미터까지 가요?", "직진 최대 거리가 몇 미터입니까?"],
 "llm_runtime": ["What runs Gemma for you?", "Is your model served with Ollama?", "언어 모델 돌리는 프로그램이 뭐예요?"],
})
NEG += ["move forward 4 meters", "앞으로 5미터 가 줘", "grab the paper cup", "종이컵 좀 집어 주세요", "how old is the mayor?",
        "사장님 연세가 어떻게 되세요?", "who leads samsung?"]

POS.update({   # night 5: openers, asides, Konglish, 하게체, run-together words, guesses
 "safety": ["Is it safe to stand next to you?", "아이들 옆에 있어도 안전합니까?", "너 위험하지 않아?", "are you dangerous for kids?"],
 "cameras": ["How many cameras do you have?", "카메라 뭐 쓰세요?", "what camera model do you use?", "카메라 몇 대 있어요?"],
 "faces": ["Do you do face recognition?", "얼굴 알아볼 수 있어요?", "can you remember faces?"],
 "mics": ["How many microphones do you have?", "마이크 몇 개 있어요?", "how far away can you hear?"],
 "tts": ["What text to speech do you use?", "목소리는 뭘로 내세요?", "너 목소리 진짜 사람이야?"],
 "stt": ["Which speech recognition do you use?", "음성 인식 뭐 쓰십니까?", "말은 어떻게 알아들으세요?"],
})
POS["age"] += ["궁금한 게, 브로, 너 몇 살이야?", "루미 군, 너 몇 살인가?", "에이지가 몇이야?", "you're about five, right?"]
POS["height"] += ["농사일에 쓸라 카는데, 로봇아, 키가 몇이에요?", "하이트가 얼마야?", "키 how much?", "너 2미터지?"]
POS["maker"] += ["메이커가 어디야?", "LG가 만들었지?", "아야 루미, 어느 회사가 너를 만들었는교?"]
POS["battery_life"] += ["배터리 수명 얼마나 되는가?", "battery life 얼마야?", "하루 종일 가나?"]
NEG += ["내일 며칠이야?", "어제 무슨 요일이었어?", "what's the date tomorrow?", "what day was yesterday?", "크리스마스가 무슨 요일이야?",
        "what day is christmas this year?", "다음 주 금요일이 며칠이야?", "몇 시에 문 닫아요?", "what time does the store close?",
        "how tall is namsan tower?", "롯데타워 높이가 얼마야?", "BTS 나이가 어떻게 돼?", "how old is the president?", "how heavy is an elephant?",
        "코끼리 무게가 얼마야?", "how fast is a cheetah?", "치타 얼마나 빨라?", "핸드폰 배터리 얼마나 가요?", "how long does a phone battery last?",
        "who made the iphone?", "who invented robots?", "브라질은 무슨 언어 써?", "what language do they speak in Brazil?",
        "what's your mom's name?", "너네 엄마 이름 뭐야?", "what's my name?", "내 나이 맞혀 봐", "몇 살로 보여요?",
        "오픈AI 대표 누구야?", "환율 얼마야?", "1달러 얼마야?", "what does JAKA stand for?", "자카 로봇 몇 대 팔렸어?",
        "follow me, how tall are you?", "이리 와. 몇 살이야?", "take the cup, then tell me the time", "손 흔들고 몇 시인지 알려 줘",
        "what's your name? where's the toilet?", "how are you and what time is it?", "언제?", "how do you know?", "really? how old?",
        "그거 몇 킬로야?", "that one, how heavy?", "저 로봇 이름 뭐야?", "옆에 로봇은 몇 살이야?", "what's the name of that robot?"]


# night 5, rounds 6-7: new phrasings written apart from the bank (every Korean level), and new "no" risks
POS_a = {
 "name": ["I didn't catch your name, what was it?", "Sorry, your name again?", "Got a name, little guy?", "What should I call you, robot?",
          "니 이름이 뭐였더라?", "이름이 뭐라 그랬지?", "이름을 여쭤봐도 될까요?", "로봇님 존함이 어떻게 되십니까?", "이름 뭐라카노?",
          "이름이 뭐시여?", "너 이름 뭐냐고", "네임 좀 알려 주세요", "what's ur name lol", "이름 있으세요?"],
 "age": ["How long ago were you built?", "Are you old or new?", "When's your birthday?", "how many years old is lumi",
         "너 태어난 지 얼마나 됐어?", "몇 살이나 먹었니?", "연식이 어떻게 돼요?", "나이 좀 물어봐도 돼요?", "니 몇 살이고?",
         "몇 살이당가?", "올해로 몇 살 되셨어요?", "your age, please?"],
 "maker": ["Who's behind you, which company?", "Who built this robot?", "What company are you from?", "Who created you?",
           "누가 널 만든 거야?", "어디서 만든 로봇이에요?", "제작사가 어디죠?", "만든 곳이 어디예요?", "누가 맹글었노?", "어디 제품인교?",
           "who's your creator?", "너 누구 작품이야?"],
 "height": ["How tall do you stand?", "What's your height exactly?", "Are you taller than a person?", "키가 어느 정도 돼요?",
            "몇 센티나 돼?", "키가 몇 센치야?", "신장이 어떻게 되십니까?", "키 얼마나 되노?", "키가 몇이여?", "how tall r u lumi"],
 "weight": ["How much do you weigh exactly?", "Are you heavy?", "What's your weight in kilograms?", "무게가 어느 정도 돼요?",
            "몇 키로 나가?", "몸무게 몇 키로예요?", "중량이 얼마입니까?", "무게 우째 되노?", "얼마나 무거워요?", "how heavy is lumi"],
 "battery_life": ["How long can you run before charging?", "How many hours does a full battery give you?", "What's your runtime on battery?",
                  "충전 한 번에 몇 시간 일해요?", "배터리 몇 시간 버텨요?", "한 번 충전하면 하루 종일 가요?", "배터리가 몇 시간이나 갑니까?",
                  "배터리 오래가노?", "배터리 지속 시간이 어떻게 되세요?"],
 "languages": ["What languages do you understand?", "Do you understand Korean?", "Can I talk to you in Japanese?", "Do you speak French?",
               "한국어로 말해도 돼?", "영어도 알아들어요?", "일본어 돼요?", "몇 개 언어 하세요?", "중국말 할 줄 아나?", "외국어 할 수 있습니까?"],
 "chatgpt": ["Is this ChatGPT talking?", "Are you powered by OpenAI?", "Do you use GPT-4?", "챗GPT로 대답하는 거야?", "너 GPT 기반이야?",
             "오픈AI 거 써요?"],
 "model": ["What brain do you use to talk?", "Which AI answers me?", "What's the name of your language model?", "너 무슨 모델로 대답해?",
           "어떤 인공지능으로 말해요?", "언어 모델 이름이 뭐예요?", "LLM 뭐 쓰세요?"],
 "robot": ["Are you a person in a costume?", "Is there a human inside?", "Do you have a soul?", "Can you feel pain?", "너 사람이니 로봇이니?",
           "안에 사람 들어 있어요?", "감정이 있으세요?", "아픈 거 느껴?", "너 기계 맞아?", "are you conscious?"],
 "speed": ["How fast do you drive?", "What's your top speed in km/h?", "Can you go quickly?", "속도가 얼마나 나와요?", "최고 속력이 얼마예요?",
           "얼마나 빨리 움직여?", "빠르게 갈 수 있어요?", "속도 우째 되노?"],
 "time_now": ["Do you know what time it is?", "What's the time please?", "Time check?", "지금 몇 시예요?", "몇 시쯤 됐어요?", "시간 좀 알려 주시겠어요?",
              "지금 몇 시나 됐노?", "현재 시각 알려 줘"],
 "date_today": ["What's today's date?", "What day is it today?", "Which day of the week is today?", "오늘 날짜 좀 알려 주세요", "오늘 무슨 요일이에요?",
                "오늘이 며칠이죠?", "오늘 몇 월 며칠이고?", "today date?"],
 "hello": ["Hi there, Lumi!", "Good afternoon!", "Hey robot!", "안녕하십니까!", "하이~", "반가워 루미!"],
 "how_are_you": ["How's your day been?", "Are you having a good day?", "오늘 기분 좋아?", "잘 지내셨어요?", "컨디션 괜찮아?"],
}
NEG_a = ["Can you see my hand?", "What's on the table?", "Where did my friend go?", "How old is my son?", "What am I holding?",
       "Come with me please", "Turn to the left", "Bring me the cup", "Sing me a song", "Tell me a story",
       "What's the weather tomorrow?", "Who won the game yesterday?", "What's the capital of France?", "How tall is BTS Jungkook?",
       "How old is the CEO?", "When does the exhibition close?", "What time does the bus come?", "Where is the restroom?",
       "내 손 보여?", "책상 위에 뭐 있어?", "우리 아들 몇 살로 보여?", "왼쪽으로 돌아", "컵 가져와", "노래 불러 줘", "이야기 해 줘",
       "내일 날씨 어때?", "어제 경기 누가 이겼어?", "프랑스 수도가 어디야?", "대표님 나이가 어떻게 돼요?", "전시회 몇 시에 끝나요?",
       "버스 몇 시에 와요?", "화장실 어디예요?", "고마워", "잘 가", "그래서?", "진짜야?", "왜?", "알았어", "음...", "그럼 이건?",
       "이 컵 무게 얼마야?", "how heavy is this cup?", "how tall is the table?", "책상 높이 얼마야?", "이거 몇 살짜리 장난감이야?",
       "how old is this building?", "what's your favorite food?", "좋아하는 음식 뭐야?", "do you love me?", "나 좋아해?"]
POS_b = {
    "co_what": ["쿳션은 어떤 회사입니까?", "쿳션 뭐 하는 회사여?", "Tell me a bit about Cutshion", "쿳션이 뭐 하는 곳이에요?"],
 "co_founded": ["When was your company set up?", "쿳션은 몇 년도에 생겼어요?", "회사 설립이 언제입니까?", "쿳션 창업한 지 얼마나 됐어?"],
 "co_ceo": ["Who runs Cutshion?", "쿳션 사장님이 누구세요?", "쿳션 대표님 이름이 뭐예요?", "Who's the boss of Cutshion?"],
 "co_hq": ["Where is Cutshion's office?", "쿳션 사무실이 어디 있어요?", "회사가 어디에 있습니까?", "쿳션 본사가 어디고?"],
 "co_contact": ["How do I contact Cutshion?", "쿳션 이메일이 뭐예요?", "회사 전화번호 좀 알려 주세요", "쿳션에 연락하려면 어떻게 해요?"],
 "safety": ["Is it safe for my kids to be near you?", "로봇 옆에 있어도 위험하지 않나요?", "너 위험한 로봇이야?", "Can you hurt someone?"],
 "cameras": ["How many cameras are on you?", "카메라가 몇 개 달려 있어요?", "What camera do you have in your head?", "카메라 어떤 거 쓰세요?"],
 "mics": ["Do you have a microphone?", "마이크가 몇 개 있어요?", "How far away can you hear people?", "멀리서도 들려요?"],
 "stt": ["How do you understand my words?", "말을 어떻게 알아들어요?", "음성 인식 뭐 써요?", "Do you use Whisper?"],
 "tts": ["How do you make your voice?", "목소리는 어떻게 내세요?", "What speech synthesis do you use?", "TTS 뭐 씁니까?"],
 "internet": ["Are you connected to the internet?", "인터넷 연결돼 있어요?", "Can you work without wifi?", "와이파이 써?"],
 "computer": ["What computer is inside you?", "안에 무슨 컴퓨터 들어 있어요?", "Do you use an NVIDIA chip?", "컴퓨터 사양이 어떻게 돼요?"],
 "stairs": ["Can you climb stairs?", "계단 올라갈 수 있어요?", "Can you go over a step?", "턱 넘을 수 있어?"],
 "doors": ["Can you open a door?", "문 열 수 있어요?", "문 열 줄 아니?"],
 "lidar": ["Do you have a lidar?", "라이다 있어요?", "How far does your lidar see?"],
 "gripper": ["What gripper do you have?", "그리퍼 뭐 써요?", "How many fingers do you have?", "손가락 몇 개야?"],
 "payload": ["How much can your arm carry?", "팔 가반하중이 얼마예요?", "What's your payload?"],
 "dance": ["Can you dance?", "춤출 수 있어요?", "Can you walk?", "걸을 수 있어?"],
 "touch": ["Can I touch you?", "만져 봐도 돼요?", "Is it okay to touch the robot?"],
}
NEG_b = ["Where can I buy a robot like you?", "쿳션 주식 살 수 있어요?", "Is Cutshion's CEO married?", "대표님 몇 살이에요?",
       "Can you open the window?", "문 좀 열어 줘", "Climb the stairs now", "계단으로 가", "Dance for me!", "춤 춰 봐", "Touch my hand",
       "내 손 만져 봐", "Show me your camera", "카메라 보여 줘", "Turn on the internet", "와이파이 비밀번호 뭐야?", "What's the wifi password?",
       "Pick up the bottle", "병 집어 줘", "How heavy is this bottle?", "이 병 몇 킬로야?", "Is the floor safe?", "여기 안전해?"]
for _p in (POS_a, POS_b):
    for _k, _t in _p.items():
        POS.setdefault(_k, []).extend(_t)
NEG += NEG_a + NEG_b


def run():
    ok = bad = miss = 0
    lines = []
    for kind, texts in POS.items():
        for t in texts:
            got = qa.kind_of(t)
            if got == kind:
                ok += 1
            elif got is None:
                miss += 1; lines.append(f"miss {kind:12} {t!r} guard={qa.guarded(t)}")
            else:
                bad += 1; lines.append(f"WRONG {kind:12} {t!r} -> {got}")
    nok = 0
    for t in NEG:
        got = qa.kind_of(t)
        if got is None:
            nok += 1
        else:
            bad += 1; lines.append(f"WRONG no           {t!r} -> {got}")
    n = sum(map(len, POS.values()))
    print("\n".join(lines))
    print(f"pos {ok}/{n} ({miss} missed), neg {nok}/{len(NEG)}, wrong {bad}")

run()
