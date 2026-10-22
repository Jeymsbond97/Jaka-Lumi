"""A second set of spoken cases for tests/asr_check.py (--cases 2), kept apart from asr_cases.py so a fix made on
the first set is checked on words it has not seen: the owner's way of saying commands (logs/lumi.log 2026-10-21),
polite Korean, numbers and times, follow-ups. Same form as asr_cases.py.
"""
from tests.asr_cases import EN_NUM, KO_EN_NUM, SINO

CASES = []


def add(kind, lang, text, *say):
    CASES.append({"kind": kind, "lang": lang, "text": text,
                  "say": list(say) or [("ko" if lang == "ko" else "en", text)]})


# ---- English as the owner says it
for n in (1, 3, 5, 7, 9, 10):
    add("command", "en", f"Let's go to p{n}.", ("en", f"Let's go to p {EN_NUM[n - 1]}."))
    add("command", "en", f"Lumi, go to p{n} point.", ("en", f"Lumi, go to p {EN_NUM[n - 1]} point."))
for t in ["Let's come to me.", "Let's follow me.", "Look at the back side.", "Look at the left side.",
          "Look at the right side.", "Can you shake your hand?", "Open your hand, please.", "Let's go back one meter.",
          "Come back twenty centimeters.", "Let's go home.", "Go to the final point, please.", "Stop, stop.",
          "Okay, you can go now.", "Go to p ten and wait thirty seconds, then come back here again.",
          "Lumi, what is the color of my t-shirt?", "What about my shoes?", "What is in my hand?",
          "Can you sing a song for me?", "Who made you?", "How many people work in Cutshion company?",
          "Can you give me information about Cutshion company?", "Where is the location?", "Can you explain more?",
          "Turn left ninety degrees.", "Move forward fifty centimeters.", "Raise your head.", "Look down.",
          "Give me the red cup.", "Put the cup on the white table.", "Bring me the white cup from the table.",
          "Pick up the bottle and give it to me.", "Take the cup and go to p five.", "Wait here.",
          "What time is it now?", "What's the weather in Seoul?", "Hi Lumi, how are you today?",
          "Lumi, are you listening?", "Speak slower, please.", "A bit louder.", "Good job, Lumi."]:
    add("command" if not t.endswith("?") else "question", "en",
        t.replace("p ten", "p10").replace("p five", "p5"), ("en", t))

# ---- Korean, polite and plain
for n in (2, 4, 6, 8):
    add("command", "ko", f"p{n}로 가 주세요.", ("ko", f"피{KO_EN_NUM[n - 1]}로 가 주세요."))
    add("command", "ko", f"{SINO[n - 1]} 번 포인트로 가 주실래요?")
for t in ["이리 와 주세요.", "저 따라오세요.", "잠깐 멈춰 주세요.", "충전하러 가세요.", "파이널 포인트로 가 주세요.",
          "왼쪽 좀 봐 주세요.", "오른쪽을 봐요.", "뒤를 봐 줘.", "고개 좀 들어 봐.", "앞으로 오십 센티 가 주세요.",
          "뒤로 일 미터 가요.", "오른쪽으로 돌아 주세요.", "한 바퀴 돌아.", "손 좀 펴 주세요.", "손 오므려.",
          "빨간 컵 좀 갖다 주세요.", "흰 컵 테이블에 올려 주세요.", "물병 좀 집어 줄래요?", "이거 좀 받아 주세요.",
          "컵 여기 놔 주세요.", "노래 한 곡 불러 주세요.", "조금 더 크게 말해 주세요.", "말 좀 천천히 해 줘.",
          "피세븐 갔다가 삼십 초 기다리고 돌아와.", "홈으로 가서 충전해.", "여기서 기다려.", "그만해.", "가만히 있어."]:
    add("command", "ko", t.replace("피세븐", "p7"), ("ko", t))
for t in ["너 이름이 뭐예요?", "누가 너를 만들었어요?", "쿳션 회사는 뭐 하는 회사예요?", "쿳션 직원은 몇 명이에요?",
          "지금 몇 시예요?", "오늘 날씨 어때요?", "서울 날씨 알려 주세요.", "제가 보여요?", "제 손에 뭐가 있어요?",
          "제 셔츠 무슨 색이에요?", "여기 몇 명 있어요?", "앞에 뭐가 보여요?", "컵 어디 있어?", "너는 몇 살이에요?",
          "무엇을 할 수 있어요?", "노래 할 줄 알아요?", "한국어 잘해요?", "충전은 얼마나 걸려요?"]:
    add("question", "ko", t)
for t in ["네, 맞아요.", "아니요, 괜찮아요.", "알겠습니다.", "고맙습니다.", "잘 가요.", "다음에 봐요.", "진짜요?", "그렇구나."]:
    add("short", "ko", t)
for t in ["루미.", "루미야, 안녕?", "안녕 루미."]:
    add("wake", "ko", t)

# ---- Mixed
for t, say in [("Lumi, 홈으로 가.", [("en", "Lumi,"), ("ko", "홈으로 가.")]),
               ("루미야, go home.", [("ko", "루미야,"), ("en", "go home.")]),
               ("p7으로 가 주세요.", [("en", "p seven"), ("ko", "으로 가 주세요.")]),
               ("Lumi, 컵 좀 갖다 줘.", [("en", "Lumi,"), ("ko", "컵 좀 갖다 줘.")]),
               ("루미야, what can you do?", [("ko", "루미야,"), ("en", "what can you do?")]),
               ("Lumi, 지금 몇 시야?", [("en", "Lumi,"), ("ko", "지금 몇 시야?")]),
               ("Okay, 이제 가도 돼.", [("en", "Okay,"), ("ko", "이제 가도 돼.")]),
               ("white cup 테이블에 놔 줘.", [("en", "white cup"), ("ko", "테이블에 놔 줘.")]),
               ("Lumi, 오른쪽 봐.", [("en", "Lumi,"), ("ko", "오른쪽 봐.")]),
               ("루미야, turn around.", [("ko", "루미야,"), ("en", "turn around.")])]:
    add("command" if "?" not in t else "question", "mix", t, *say)
