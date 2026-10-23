"""Spoken cases, set 5 (hearing round 2, 2026-10-22 night): short commands, numbers with units, and marker names
on several maps (tests/blind/maps.py), English, Korean and mixed. Format of tests/asr_cases.py plus "markers" (the
map the case is read against).

    .venv/bin/python tests/asr_check.py --cases 5 [--session]
"""
from tests.blind.maps import MAPS

CASES = []
OFFICE = MAPS["office"]


def add(lang, text, say=None, kind="command", markers=OFFICE):
    """say: the words as spoken (numbers in words), in the case's language; mixed: [(lang, words), ...]."""
    if isinstance(say, list):
        pieces = say
    else:
        pieces = [("ko" if lang == "ko" else "en", say or text)]
    CASES.append({"kind": kind, "lang": lang, "text": text, "say": pieces, "markers": markers})


# ---- short commands, said alone
for t in ["Stop.", "Stop!", "Stop it.", "Wait.", "Wait a second.", "Wave.", "Wave to me.", "Hand.", "Your hand.",
          "Come.", "Come here.", "Follow me.", "Here.", "Over here.", "Come back.", "Look back.", "Look behind you.",
          "Look up.", "Look down.", "Look left.", "Look right.", "Look at me.", "Turn left.", "Turn right.",
          "Turn around.", "Go home.", "Sing.", "Sing a song.", "Louder.", "Quieter.", "Speak slower.", "Open your hand.",
          "Close your hand.", "Give it to me.", "Take it.", "Put it down.", "Go back.", "Move forward.", "Back up.",
          "Lift up.", "Go down.", "Higher.", "Lower.", "Be quiet.", "What time is it?", "How's the weather?",
          "Battery?", "Again.", "One more time.", "A bit more.", "Okay.", "Thanks.", "Bye.", "Never mind.",
          "Hold on.", "Freeze.", "Halt.", "Enough."]:
    add("en", t, kind="short")
for t, say in [("멈춰", None), ("멈춰!", None), ("그만", None), ("그만해", None), ("정지", None), ("스톱", None),
               ("잠깐", None), ("잠깐만", None), ("손 흔들어", None), ("손 흔들어 줘", None), ("손", None), ("손 줘", None),
               ("따라와", None), ("나 따라와", None), ("이리 와", None), ("와", None), ("여기", None), ("여기로", None),
               ("돌아와", None), ("뒤 봐", None), ("뒤 돌아봐", None), ("고개 들어", None), ("고개 숙여", None),
               ("위 봐", None), ("아래 봐", None), ("왼쪽 봐", None), ("오른쪽 봐", None), ("나 봐", None),
               ("왼쪽으로 돌아", None), ("오른쪽으로 돌아", None), ("뒤로 돌아", None), ("집에 가", None),
               ("홈으로 가", None), ("노래해", None), ("노래 불러 줘", None), ("크게 말해", None), ("작게 말해", None),
               ("천천히 말해", None), ("손 펴", None), ("손 쥐어", None), ("줘", None), ("이거 받아", None),
               ("내려놔", None), ("뒤로 가", None), ("앞으로 가", None), ("올라가", None), ("내려가", None),
               ("조용히 해", None), ("몇 시야?", None), ("날씨 어때?", None), ("배터리 얼마야?", None), ("한 번 더", None),
               ("조금 더", None), ("다시", None), ("고마워", None), ("잘 가", None), ("됐어", None), ("괜찮아", None)]:
    add("ko", t, say, kind="short")

# ---- numbers with units (said in words)
EN_MOVES = [("Go forward 1 meter.", "Go forward one meter."), ("Move back half a meter.", None),
            ("Go forward 50 centimeters.", "Go forward fifty centimeters."), ("Move back 30 centimeters.", "Move back thirty centimeters."),
            ("Go forward 2 meters.", "Go forward two meters."), ("Go back 1.5 meters.", "Go back one and a half meters."),
            ("Move left 20 centimeters.", "Move left twenty centimeters."), ("Move right 1 meter.", "Move right one meter."),
            ("Turn left 30 degrees.", "Turn left thirty degrees."), ("Turn right 90 degrees.", "Turn right ninety degrees."),
            ("Turn left 45 degrees.", "Turn left forty five degrees."), ("Turn right 180 degrees.", "Turn right one hundred eighty degrees."),
            ("Turn 60 degrees to the left.", "Turn sixty degrees to the left."), ("Forward 1 meter.", "Forward one meter."),
            ("Back 50 centimeters.", "Back fifty centimeters."), ("Go 3 meters forward.", "Go three meters forward."),
            ("Lift up 5 centimeters.", "Lift up five centimeters."), ("Lower 10 centimeters.", "Lower ten centimeters.")]
for t, say in EN_MOVES:
    add("en", t, say)
KO_MOVES = [("1미터 앞으로 가", "일 미터 앞으로 가"), ("반 미터 뒤로 가", None), ("50센티 앞으로", "오십 센티 앞으로"),
            ("30센티 뒤로", "삼십 센티 뒤로"), ("2미터 앞으로 가 줘", "이 미터 앞으로 가 줘"),
            ("1미터 50센티 뒤로 가", "일 미터 오십 센티 뒤로 가"), ("왼쪽으로 20센티 가", "왼쪽으로 이십 센티 가"),
            ("오른쪽으로 1미터 가", "오른쪽으로 일 미터 가"), ("왼쪽으로 30도 돌아", "왼쪽으로 삼십 도 돌아"),
            ("오른쪽으로 90도 돌아", "오른쪽으로 구십 도 돌아"), ("45도 왼쪽으로 돌아", "사십오 도 왼쪽으로 돌아"),
            ("180도 돌아", "백팔십 도 돌아"), ("30도 오른쪽", "삼십 도 오른쪽"), ("1미터", "일 미터"),
            ("반 미터", None), ("50센티", "오십 센티"), ("30도", "삼십 도"), ("앞으로 3미터", "앞으로 삼 미터"),
            ("5센티 올려", "오 센티 올려"), ("10센티 내려", "십 센티 내려"), ("한 걸음 앞으로", None),
            ("1미터만 와", "일 미터만 와")]
for t, say in KO_MOVES:
    add("ko", t, say)
for t, say in [("1미터 forward", [("ko", "일 미터"), ("en", "forward")]),
               ("turn left 30도", [("en", "turn left"), ("ko", "삼십 도")]),
               ("50센티 back", [("ko", "오십 센티"), ("en", "back")]),
               ("go 1미터 앞으로", [("en", "go"), ("ko", "일 미터 앞으로")])]:
    add("mix", t, say)

# ---- marker names on several maps
CONF = MAPS["conference"]
for t, say in [("Go to the Main Stage.", None), ("Take me to Booth 12.", "Take me to booth twelve."),
               ("Go to Registration.", None), ("Go to the photo zone.", None), ("Go to the lounge.", None),
               ("Go to the Coffee Bar.", None), ("Go to Exit B.", None), ("Main Stage, please.", None),
               ("Booth 12.", "Booth twelve."), ("Coffee Bar.", None), ("Lumi, go to the main stage.", None),
               ("Bring me to registration.", None), ("Go home.", None), ("Go to dock 2 and charge.", "Go to dock two and charge.")]:
    add("en", t, say, markers=CONF)
for t, say in [("메인 스테이지로 가", None), ("부스 12로 가", "부스 십이로 가"), ("부스 12로 가 줘", "부스 열둘로 가 줘"),
               ("레지스트레이션으로 가", None), ("포토존으로 가", None), ("포토존 가자", None), ("라운지로 가", None),
               ("라운지로 데려다 줘", None), ("커피 바로 가", None), ("커피바로 가 줘", None), ("엑시트 비로 가", None),
               ("포토존", None), ("라운지", None), ("메인 스테이지", None), ("홈으로 가", None), ("도크 투로 가서 충전해", None)]:
    add("ko", t, say, markers=CONF)
for t, say in [("Main Stage로 가", [("en", "Main Stage"), ("ko", "로 가")]),
               ("Booth 12로 가 줘", [("en", "Booth twelve"), ("ko", "로 가 줘")]),
               ("Coffee Bar로 가", [("en", "Coffee Bar"), ("ko", "로 가")]),
               ("go to 포토존", [("en", "go to"), ("ko", "포토존")]),
               ("go to 라운지", [("en", "go to"), ("ko", "라운지")])]:
    add("mix", t, say, markers=CONF)
KOREAN_MAP = MAPS["korean"]
for t, say in [("커피코너로 가", None), ("부스3으로 가", "부스 삼으로 가"), ("입구로 가", None), ("무대로 가", None),
               ("안내데스크로 가", None), ("휴게실로 가", None), ("회의실로 가 줘", None), ("커피코너", None)]:
    add("ko", t, say, markers=KOREAN_MAP)
for t, say in [("Go to the 커피코너.", [("en", "Go to the"), ("ko", "커피코너")]),
               ("Take me to 회의실.", [("en", "Take me to"), ("ko", "회의실")])]:
    add("mix", t, say, markers=KOREAN_MAP)
EXPO, HALL = MAPS["expo"], MAPS["hall"]
for t, say, m in [("Go to booth A.", None, EXPO), ("Go to booth 3.", "Go to booth three.", EXPO),
                  ("Go to the entrance.", None, EXPO), ("Go to the info desk.", None, EXPO),
                  ("Go to the coffee corner.", None, EXPO), ("Go to gate 1.", "Go to gate one.", HALL),
                  ("Go to gate 2.", "Go to gate two.", HALL), ("Go to hall A.", None, HALL),
                  ("Go to the photo zone.", None, HALL), ("Go to the table front.", None, HALL)]:
    add("en", t, say, markers=m)
for t, say, m in [("부스 에이로 가", None, EXPO), ("부스 쓰리로 가", None, EXPO), ("인포 데스크로 가", None, EXPO),
                  ("커피 코너로 가", None, EXPO), ("게이트 원으로 가", None, HALL), ("게이트 투로 가", None, HALL),
                  ("홀 에이로 가", None, HALL), ("포토 존으로 가", None, HALL)]:
    add("ko", t, say, markers=m)
for n, ko in [(1, "일"), (3, "삼"), (5, "오"), (7, "칠"), (9, "구"), (10, "십")]:
    add("ko", f"p{n}로 가", f"피 {ko}로 가")
    add("en", f"Go to p{n}.", f"Go to p {['one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'][n - 1]}.")
for t, say in [("p3로 가 줘", "피쓰리로 가 줘"), ("p5", "피 파이브"), ("p8로", "피 에잇으로"), ("p2", "피 이")]:
    add("ko", t, say)
