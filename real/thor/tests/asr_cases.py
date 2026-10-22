"""Spoken cases for the speech-to-text check (tests/asr_check.py): what a person says, and how it sounds.

A case: {"text": the words as Lumi should read them, "say": [(lang, words), ...] the pieces the TTS speaks (a mixed
sentence is English and Korean pieces one after the other), "lang": "en" | "ko" | "mix", "kind": "command" |
"question" | "short" | "wake"}. The text is what the routing is judged against; "say" is how people say it
("피쓰리로 가 줘" for "p3로 가 줘", "p five" for "p5").
"""
import random

R = random.Random(11)          # the same cases every run
CASES = []


def add(kind, lang, text, *say):
    """say: (lang, words) pieces; none given: the text itself in the case's language."""
    CASES.append({"kind": kind, "lang": lang, "text": text,
                  "say": list(say) or [("ko" if lang == "ko" else "en", text)]})


EN_NUM = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
KO_EN_NUM = ["원", "투", "쓰리", "포", "파이브", "식스", "세븐", "에잇", "나인", "텐"]
SINO = ["일", "이", "삼", "사", "오", "육", "칠", "팔", "구", "십"]

# ---- English: going to places
for n in R.sample(range(1, 11), 6):
    w = EN_NUM[n - 1]
    add("command", "en", f"Go to p{n}.", ("en", f"Go to p {w}."))
    add("command", "en", f"Lumi, go to point {w}.")
    add("command", "en", f"Please drive to p{n}.", ("en", f"Please drive to p {w}."))
for t in ["Head over to the final point.", "Go to the exit, please.", "Lumi, take me to the final point.",
          "Go back home.", "Go to your charger.", "Go to dock two.", "Drive to aisle a.", "Go to aisle b, please.",
          "Can you go to p seven?", "Lumi, could you go to point three?", "Go home and charge.",
          "Move to point ten.", "Take me to the exit."]:
    add("command", "en", t)
# ---- English: coming, following, stopping
for t in ["Come here.", "Come over here, please.", "Lumi, come to me.", "Come closer.", "Follow me.",
          "Walk with me.", "Stop following me.", "Stop.", "Wait.", "Stop right there.", "Hold on.", "That's enough.",
          "Stay here.", "Lumi, stop.", "Come back.", "Go back where you were.", "Be quiet.", "Please be quiet for a while."]:
    add("command", "en", t)
# ---- English: head, base, lift
for t in ["Look left.", "Look to your right.", "Look up.", "Look down a bit.", "Look behind you.", "Look at me.",
          "Look straight ahead.", "Turn your head thirty degrees to the left.", "Turn left.", "Turn right.",
          "Turn around.", "Turn right ninety degrees.", "Turn left forty five degrees.", "Move forward one meter.",
          "Back up twenty centimeters.", "Move back half a meter.", "Go forward two meters.",
          "Move left fifty centimeters.", "Move back a little.", "Go forward a tiny bit.", "Raise yourself.",
          "Lower yourself a bit.", "Go a bit faster.", "Slow down.", "Move back ten centimeters.",
          "Come forward thirty centimeters."]:
    add("command", "en", t)
# ---- English: hand and objects
for t in ["Open your hand.", "Close your hand.", "Wave your hand.", "Wave at me.", "Fold your arm.",
          "Pick up the red cup.", "Pick up the white cup.", "Bring me the bottle.", "Bring me a cup, please.",
          "Give me the cup.", "Hand it over.", "Put it down here.", "Put the cup on the table.", "Take this.",
          "Take the cup from my hand.", "Find the red cup and bring it to me.", "Grab the bottle.",
          "Let go of the cup.", "Put it back.", "Can you hold this for me?"]:
    add("command", "en", t)
# ---- English: voice, songs, missions
for t in ["Speak louder.", "Talk a bit slower.", "Speak quieter, please.", "I can't hear you.", "Sing a song.",
          "Can you sing for me?", "Go to p three, wait ten seconds, then come back.",
          "Go to the final point and then go home.", "Go to p five, then p two, then come back here."]:
    add("command", "en", t.replace("p three", "p3").replace("p five", "p5").replace("p two", "p2"), ("en", t))
# ---- English: questions
for t in ["What's your name?", "Who made you?", "What is Cutshion?", "Tell me about Cutshion company.",
          "Where is Cutshion located?", "How many people work at Cutshion?", "How old are you?",
          "What can you do?", "What's the weather like today?", "Is it going to rain tomorrow?", "What time is it?",
          "What's the date today?", "Can you see me?", "What am I holding?", "What color is my shirt?",
          "What color are my pants?", "How many people are here?", "Do you see a cup?", "What do you see?",
          "Is there a bottle on the table?", "How far is the cup?", "What's behind you?", "Are you a robot?",
          "How much do you weigh?", "How fast can you drive?", "How long does your battery last?",
          "What's the dollar exchange rate?", "Who is the president of Korea?", "Can you tell me a joke?",
          "Where is the restroom?", "Do you speak Korean?", "What does Cutshion make?", "Can you pick things up?",
          "How tall are you?", "What is in my hand?", "Am I wearing glasses?"]:
    add("question", "en", t)
# ---- English: short answers, wake words
for t in ["Yes.", "No.", "Okay.", "Thank you.", "Thanks, bye.", "Got it.", "Really?", "I see.", "Sure.",
          "No, thanks.", "Good job.", "See you later.", "That's all, thank you.", "Okay, bye."]:
    add("short", "en", t)
for t in ["Lumi.", "Hi Lumi.", "Hey Lumi.", "Hello Lumi.", "Hi.", "Lumi, are you there?", "Hey Lumi, how are you?"]:
    add("wake", "en", t)

# ---- Korean: going to places
for n in R.sample(range(1, 11), 6):
    add("command", "ko", f"p{n}로 가 줘.", ("ko", f"피{KO_EN_NUM[n - 1]}로 가 줘."))
    add("command", "ko", f"포인트 {SINO[n - 1]}으로 가.", ("ko", f"포인트 {SINO[n - 1]}으로 가."))
for n in R.sample(range(1, 10), 3):
    add("command", "ko", f"{SINO[n - 1]} 번 포인트로 가 줘.")
for t in ["파이널 포인트로 가 줘.", "홈으로 가.", "충전하러 가.", "도크 투로 가.", "엑시트로 가 줘.", "집으로 돌아가.",
          "루미야, 파이널로 가.", "피텐으로 가 줄래?", "포인트 파이브로 이동해."]:
    add("command", "ko", t)
# ---- Korean: coming, following, stopping
for t in ["이리 와.", "이쪽으로 와 줘.", "루미야 이리 와.", "가까이 와.", "나 따라와.", "따라와 줘.", "따라오지 마.",
          "멈춰.", "그만.", "기다려.", "거기 있어.", "잠깐만.", "조용히 해.", "돌아와.", "원래 자리로 돌아가."]:
    add("command", "ko", t)
# ---- Korean: head, base, lift
for t in ["왼쪽 봐.", "오른쪽 봐.", "위를 봐.", "아래 봐.", "뒤 봐.", "나 봐.", "정면 봐.", "고개 들어.", "고개 숙여.",
          "앞으로 일 미터 가.", "뒤로 이십 센티 가.", "반 미터 뒤로 가.", "왼쪽으로 돌아.", "오른쪽으로 구십 도 돌아.",
          "뒤로 돌아.", "키 좀 높여.", "몸 좀 낮춰.", "살짝 뒤로 가.", "조금 앞으로 와.", "더 빨리 가.", "천천히 가.",
          "앞으로 삼십 센티 가."]:
    add("command", "ko", t)
# ---- Korean: hand and objects
for t in ["손 펴.", "손 쥐어.", "손 흔들어 줘.", "손 인사 해 줘.", "빨간 컵 집어 줘.", "흰 컵 집어.", "컵 좀 갖다 줘.",
          "물병 가져와.", "컵 좀 주세요.", "이거 받아.", "테이블에 놔 줘.", "여기 내려놔.", "컵 테이블에 올려 줘.",
          "빨간 컵 찾아서 가져와.", "병 잡아.", "컵 내려놔.", "그거 나 줘.", "이것 좀 들고 있어."]:
    add("command", "ko", t)
# ---- Korean: voice, songs, missions
for t in ["크게 말해 줘.", "천천히 말해.", "소리 좀 줄여.", "안 들려.", "노래 불러 줘.", "노래 하나 해 줄래?",
          "파이널 갔다가 홈으로 와."]:
    add("command", "ko", t)
add("command", "ko", "p3 갔다가 십 초 기다리고 돌아와.", ("ko", "피쓰리 갔다가 십 초 기다리고 돌아와."))
# ---- Korean: questions
for t in ["이름이 뭐야?", "누가 만들었어?", "컷션이 뭐야?", "컷션 회사에 대해 알려 줘.", "컷션은 어디에 있어?",
          "몇 살이야?", "뭘 할 수 있어?", "오늘 날씨 어때?", "내일 비 와?", "지금 몇 시야?", "오늘 며칠이야?",
          "나 보여?", "내가 뭘 들고 있어?", "내 옷 무슨 색이야?", "여기 사람 몇 명 있어?", "컵 보여?", "뭐가 보여?",
          "테이블 위에 뭐 있어?", "컵 얼마나 멀리 있어?", "너 로봇이야?", "무게가 얼마나 돼?", "배터리 얼마나 가?",
          "달러 환율 알려 줘.", "농담 하나 해 줘.", "화장실 어디예요?", "영어 할 줄 알아?", "물건 집을 수 있어?",
          "키가 몇이야?", "내 손에 뭐 있어?", "나 안경 썼어?"]:
    add("question", "ko", t)
# ---- Korean: short answers, wake words
for t in ["네.", "아니요.", "응.", "고마워요.", "감사합니다.", "알겠어요.", "그래요?", "아 그렇구나.", "됐어요, 고마워요.",
          "안녕히 계세요.", "수고하세요.", "잘했어요.", "좋아요."]:
    add("short", "ko", t)
for t in ["루미야.", "안녕 루미야.", "루미야, 안녕.", "루미야 거기 있어?", "안녕하세요."]:
    add("wake", "ko", t)

# ---- Mixed: English pieces inside Korean and the reverse
for t, say in [("Lumi, 이리 와.", [("en", "Lumi,"), ("ko", "이리 와.")]),
               ("루미야, come here.", [("ko", "루미야,"), ("en", "come here.")]),
               ("Lumi, 나 따라와.", [("en", "Lumi,"), ("ko", "나 따라와.")]),
               ("루미야, follow me.", [("ko", "루미야,"), ("en", "follow me.")]),
               ("Lumi, 멈춰.", [("en", "Lumi,"), ("ko", "멈춰.")]),
               ("루미야, stop.", [("ko", "루미야,"), ("en", "stop.")]),
               ("p3로 가 줘.", [("en", "p three"), ("ko", "로 가 줘.")]),
               ("p5로 가.", [("en", "p five"), ("ko", "로 가.")]),
               ("final point로 가 줘.", [("en", "final point"), ("ko", "로 가 줘.")]),
               ("home으로 가.", [("en", "home"), ("ko", "으로 가.")]),
               ("dock two로 가.", [("en", "dock two"), ("ko", "로 가.")]),
               ("Lumi, 왼쪽 봐.", [("en", "Lumi,"), ("ko", "왼쪽 봐.")]),
               ("루미야, look left.", [("ko", "루미야,"), ("en", "look left.")]),
               ("Lumi, 손 흔들어 줘.", [("en", "Lumi,"), ("ko", "손 흔들어 줘.")]),
               ("루미야, open your hand.", [("ko", "루미야,"), ("en", "open your hand.")]),
               ("cup 좀 가져와.", [("en", "cup"), ("ko", "좀 가져와.")]),
               ("red cup 집어 줘.", [("en", "red cup"), ("ko", "집어 줘.")]),
               ("Lumi, 오늘 날씨 어때?", [("en", "Lumi,"), ("ko", "오늘 날씨 어때?")]),
               ("루미야, what's your name?", [("ko", "루미야,"), ("en", "what's your name?")]),
               ("Cutshion이 뭐야?", [("en", "Cutshion"), ("ko", "이 뭐야?")]),
               ("Okay, 고마워요.", [("en", "Okay,"), ("ko", "고마워요.")]),
               ("네, thank you.", [("ko", "네,"), ("en", "thank you.")]),
               ("Lumi, 뒤로 이십 센티 가.", [("en", "Lumi,"), ("ko", "뒤로 이십 센티 가.")]),
               ("루미야, move back one meter.", [("ko", "루미야,"), ("en", "move back one meter.")]),
               ("Lumi, 노래 불러 줘.", [("en", "Lumi,"), ("ko", "노래 불러 줘.")]),
               ("루미야, sing a song.", [("ko", "루미야,"), ("en", "sing a song.")])]:
    add("command" if "?" not in t else "question", "mix", t, *say)
