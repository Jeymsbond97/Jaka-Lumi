"""Arm and hand wordings for the intent bank (assistant/intent_bank.py kinds): wave (every handshake form too, the
owner's meaning), arm_reach (hold the arm out: "give me your hand", "손 줘", "손 내밀어"), arm_fold (back to look),
arm_open / arm_close (the gripper), pick, fetch, and the hand's put / receive / give (the bank does not act on these
three: they keep their wordings apart from the others), plus "no": talk about the arm and hand that asks nothing.

Korean is written as stems x endings (반말 / 해요체 / 하십시오체 / 주세요 / 줄래 / dialect), English as phrases.
"""


def _ko(stems, ends):
    return [f"{s}{e}" for s in stems for e in ends]


def _en(cores):
    return [f.format(c) for c in cores for f in FRAMES]


FRAMES = ["{}", "please {}", "{} please", "could you {}", "would you please {}", "can you {}", "will you {}",
          "you think you could {}", "be a dear and {}", "do me a favour and {}", "i want you to {}", "i need you to {}",
          "i'd like you to {}", "how about you {}", "why don't you {}", "mind if i ask you to {}", "i order you to {}",
          "{} now", "{} for me", "{} real quick", "just {}", "{}, okay", "come on, {}", "you {} please", "kindly {}"]


ASK = ["", " 줘", " 봐", " 줘 봐", " 주세요", " 줘요", " 봐요", " 보세요", " 줄래?", " 줄래요?", " 주실래요?", " 주십시오",
       " 주시겠어요?", " 주시겠습니까?", " 주라", " 주게", " 보게", " 주이소", " 보이소", " 봐유", " 줘유", " 줘용", " 주세용",
       " 줄 수 있어?", " 주실 수 있어요?", " 주면 좋겠어", " 주시면 감사하겠습니다", " 주시오", " 보거라", " 주렴"]
ASK += [" 주셨으면 해요", " 주셨으면 좋겠어요", " 주면 좋겠어요", " 주시겠소", " 주소", " 도", " 주이소예", " 조", " 주랑께",
        " 주드라고", " 줘라", " 주라잉", " 줘 봐라", " 보소", " 봐라", " 줄래 응", " 주세요 제발", " 좀 해 줘"]
ASK_SHORT = ["", " 줘", " 봐", " 주세요", " 줘요", " 줄래?", " 주실래요?", " 주십시오", " 주라", " 주게", " 주이소", " 줘유"]

# ---------- wave: a wave of the hand, and every handshake wording (owner 2026-10-23: a handshake is a wave) ----------
WAVE = [
    # handshakes, English (native, non-native, kids, slang)
    "shake hand", "shake hands", "shake my hand", "shake hands with me", "let's shake hands", "let's shake hand",
    "can you shake hand", "can you shake hands with me", "could you shake my hand", "would you shake my hand",
    "will you shake hands with me", "shake", "shake shake", "shake please", "shake hand please", "shake hands please",
    "give me a handshake", "handshake please", "handshake", "do a handshake", "let's do a handshake",
    "how about a handshake", "gimme a handshake", "you shake hand me", "you shake my hand please", "robot shake hand", "shake hand with me please",
    "shaking hands please", "do shake hand", "make handshake", "hand shake please", "handshake me", "shakey shakey",
    "shake hans", "shake hend", "shaek hands", "sheik hands", "shake handz", "you hand shake hello please",
    "hand shake hello", "a handshake would be nice", "i'd love a handshake", "nice to meet you, shake hands",
    "let's shake hands, nice to meet you", # wave, English
    "wave", "wave your hand", "wave hand", "wave at me", "wave to me", "wave at us", "wave to us", "wave hello",
    "wave goodbye", "wave bye", "wave bye bye", "wave hi", "wave to the camera", "wave to the crowd",
    "wave to everybody", "wave to everyone here", "wave to my friends", "wave to my daughter", "wave to the kids",
    "wave to the audience", "wave back", "wave back at me", "wave back at us", "wave at the people", "wave a little",
    "wave your arm", "wave your arm at me", "wave your hand at us", "wave your hand hello", "do the wave",
    "do your wave", "do a little wave", "do a big wave", "a big wave please", "big wave", "little wave",
    "give a wave", "give us a wave", "give me a wave", "give them a wave", "give everyone a wave", "give a big wave",
    "give a little wave", "give a friendly wave", "send a wave", "throw a wave", "wave for us", "wave for the photo",
    "wave for the picture", "wave for my mom", "say hi with your hand", "say hello with your hand",
    "say bye with your hand", "say goodbye with your hand", "say hi with a wave", "greet us with a wave",
    "greet me with your hand", "greet them with a wave", "hello with your hand", "bye bye with your hand",
    "hand wave", "hand wave please", "a hand wave please", "do hand wave", "you wave hand", "you wave me",
    "you wave to me please", "robot wave", "robot wave hand", "robot wave me", "wave me", "wave me please",
    "wave you hand", "wave you hand please", "wave ur hand", "please wave hand", "please you wave", "plese wave",
    "plz wave", "wave plz", "wave pls", "wavey wave", "wave wave", "wave wave wave", "wayve", "wayve please",
    "weave", "weave your hand", "waive", "waive at me", "wav", "wav hand", "wave yur hand", "wabe", "wave your han",
    "would you mind waving", "would you mind waving at us", "would you mind waving to the crowd",
    "mind waving to us", "how about waving to us", "i'd love it if you waved at us", "i'd like you to wave",
    "it'd be nice if you waved", "it would be great if you waved at us", "i want you to wave", "i want to see you wave",
    "i wanna see you wave", "let me see you wave", "show me a wave", "show me your wave", "show us how you wave",
    "can i get a wave", "can we get a wave", "could we get a wave from you", "how about a wave", "a wave, please",
    "one wave please", "wave once", "wave one time", "please wave once", "start waving", "go ahead and wave",
    "go on, wave", "come on, wave", "come on, wave at us", "just wave", "only wave", "just wave at me", "you can wave now",
    "now wave", "wave now", "wave please", "please wave", "kindly wave", "could you wave", "can you wave",
    "will you wave", "would you wave", "would you wave at us please", "could you please wave", "can you please wave",
    "can you wave at me", "can you wave your hand", "could you wave your hand", "could you, uh, wave", "um, wave",
    "so, could you wave", "hi hi wave", "bye bye wave", "wave bye-bye", "wave goodbye to them",
    "wave hello to the guests", "wave to the visitors", "wave at the kids", "wave at the camera",
    # Korean wave and handshake (stems x endings)
    *_ko(["손 흔들어", "손 좀 흔들어", "손 한번 흔들어", "손 한 번 흔들어", "손 흔들어서 인사해", "손 인사 해", "손으로 인사해",
          "팔 흔들어", "바이바이 해", "빠이빠이 해", "손 흔들면서 인사해", "손을 흔들어", "손 크게 흔들어", "손 살짝 흔들어",
          "안녕 손 흔들어", "손 흔들어서 안녕 해", "손으로 안녕 해", "손으로 바이바이 해", "웨이브 해", "wave 해", "악수 해",
          "악수 한번 해", "악수 한 번 해", "나랑 악수 해", "저랑 악수 해", "악수 좀 해", "손 흔들어 인사해"], ASK),
    "악수하자", "악수해", "악수해요", "악수 한번 해요", "악수 한번 하자", "악수 하자", "우리 악수하자", "나랑 악수하자",
    "저랑 악수해요", "악수할래?", "악수할래요?", "악수하실래요?", "악수합시다", "악수하시죠", "악수하세요", "악수하십시오",
    "악수 좀 해요", "악수 한 번만 해 줘", "악수 한 번 해 주세요", "반가워 악수하자", "반가워요 악수해요", "악수 ㄱㄱ",
    "악수 고고", "악수 플리즈", "핸드셰이크 해 줘", "쉐이크 핸드", "셰이크 핸드 해 줘", "shake hand 해 줘", "handshake 해 줘",
    "악수해 주이소", "악수 한번 해 보이소", "악수하자잉", "악수해 봐유", "악쑤하자", "악수하쟈", "악수 해조",
    "손 흔들어", "흔들어 봐", "손 흔드러", "손 흔더러 줘", "손 흔들어조", "손 흔들어 쥬", "손 흔들어 주라잉", "손 흔들어 보랑께",
    "손 흔들어 주소", "손 흔들어 도", "손 쫌 흔들어 봐", "손 흔들어 주실 수 있나요?", "손 흔들어 주시면 좋겠어요",
    "빠빠이 해 줘", "빠빠이 해", "빠이빠이 해 줘요", "안녕 해 줘 손으로", "손 흔들어서 인사해 주세요",
    "카메라 보고 손 흔들어", "카메라 보고 wave", "camera 보고 wave", "사진 찍게 손 흔들어 줘", "애들한테 손 흔들어 줘",
    "할머니한테 손 흔들어 드려", "손님들한테 손 흔들어 주세요", "저희한테 손 흔들어 주세요", "우리한테 손 흔들어 줘",
    "관객들한테 손 흔들어 주세요", "손 한번 흔들어 주십시오", "손 흔들어 주시겠습니까?", "손 인사 부탁해요", "손 인사 부탁합니다",
    "웨이브 웨이브", "웨이브", "웨이브 해 봐", "웨이브 한번 해 줘", "wave 좀 해 줘", "wave 해 주세요", "hand wave 해 줘",
    "손 wave 해", "wave hand 해 줘", "hi 해 손으로", "bye 해 손으로", "손으로 hi 해 줘", "손 흔들어 please", "please 손 흔들어",
    "손 좀 흔들어 줄래", "손 흔들어 줘 빨리", "얼른 손 흔들어", "빨리 손 흔들어 봐", "손 흔들어 봐 어서",
]

# ---------- arm_reach: the arm held out to the person ("give me your hand", "손 줘", "손 내밀어") ----------
ARM_REACH = [
    "give me your hand", "give me a hand", "give me hand", "give me ur hand", "gimme your hand", "gimme a hand",
    "gimme hand", "give your hand", "give your hand to me", "give hand", "give hand please", "you give hand",
    "you give me hand", "you give me your hand please", "you can give hand", "can you give me your hand",
    "could you give me your hand", "may i have your hand", "can i have your hand", "can i see your hand, hold it out",
    "lend me your hand", "hand please", "your hand please", "your hand, please", "hand, please",
    "reach out", "reach out your hand", "reach out your arm", "reach out to me", "reach out please", "reach your arm out",
    "reach your hand out", "reach toward me", "reach towards me", "reach for me", "reach for my hand", "reach forward",
    "reach out a bit", "reach out real quick", "reach out, lumi", "reach", "reach arm", "reach your arm",
    "hold out your hand", "hold out your arm", "hold your hand out", "hold your arm out", "hold out your gripper",
    "hold it out", "hold out your hand to me", "hold your hand out to me",
    "stretch your arm", "stretch out your arm", "stretch out your hand", "stretch your arm out", "stretch out",
    "stretch your hand forward", "stretch your arm forward", "stretch arm", "extend your arm", "extend your hand",
    "extend your arm forward", "extend the arm", "extend arm", "put your hand out", "put your arm out",
    "put your hand forward", "put your arm forward", "stick your arm out", "stick your hand out", "push your arm out",
    "push your arm forward", "move your arm forward", "move your hand forward", "bring your hand forward",
    "bring your hand over to me", "bring your arm to me", "arm out", "arm out please", "arm forward", "arm to me",
    "hand out", "hand out please", "hand forward", "hand to me", "offer me your hand", "offer your hand",
    "show me your hand", "let me see your hand", "lemme see your hand", "show your hand", "show me your arm",
    "straighten your arm", "straighten your arm out", "make your arm straight", "arm straight", "long arm please",
    "i want see you reach arm", "i want to see you reach out", "show me you reach out", "can you reach out",
    "could you reach out your arm", "would you reach out your hand", "would you mind reaching out",
    "mind holding out your hand", "how about holding your hand out", "it'd be nice if you held out your hand",
    "reech out", "rich out", "reach owt", "reach aut", "rieach out", "hold owt your hand", "giv me your hand",
    "give mi your hand", "give me you hand", "gib me your hand", "hand pls", "arm out pls",
    # Korean
    *_ko(["손 내밀어", "손 좀 내밀어", "손 앞으로 내밀어", "손 쭉 내밀어", "손 뻗어", "손 좀 뻗어", "손 앞으로 뻗어",
          "팔 뻗어", "팔 좀 뻗어", "팔 쭉 뻗어", "팔 앞으로 뻗어", "팔 내밀어", "팔 좀 내밀어", "팔 앞으로 내밀어", "팔 펴",
          "팔 쭉 펴", "팔 좀 펴", "팔 앞으로 쭉 펴", "팔을 뻗어", "손을 내밀어", "손을 앞으로 내밀어", "팔 길게 뻗어",
          "손 이쪽으로 내밀어", "나한테 손 내밀어", "저한테 손 내밀어", "손 나한테 뻗어", "팔 나한테 뻗어"], ASK),
    *_ko(["손 줘", "손 좀 줘", "손 이리 줘", "나한테 손 줘", "저한테 손 줘", "손 내놔"], ["", " 봐", "요", " 봐요"]),
    "손 주세요", "손 좀 주세요", "손 이리 주세요", "저한테 손 주세요", "손 주실래요?", "손 줄래?", "손 주라", "손 주게",
    "손 주이소", "손 줘유", "손 주십시오", "손 좀 주실래요?", "손 이리", "손 내밀기", "손 내밀어 봐 어서",
    "루미야 손 줘", "로봇아 손 줘", "hand 줘", "hand 줘 봐", "hand 좀 줘", "hand 내밀어", "hand 좀 내밀어 줘", "팔 reach 해 줘", "reach out 해 줘",
    "reach out 해", "reach 해 줘", "팔 extend 해 줘", "arm 뻗어", "arm 뻗어 줘", "arm out 해 줘", "arm 펴 줘", "팔 out",
    "손 reach", "팔 reach", "give me hand 해 줘", "hand out 해 줘", "손 앞으로", "팔 앞으로", "팔 쭉", "팔 뻐더",
    "팔 버더", "팔 뻗어조", "손 내미러", "손 내밀어조", "팔 뻐더 줘", "손 내밀어 주이소", "팔 뻗어 보이소", "팔 쭉 뻗어 보게",
    "팔 좀 뻗어 봐유", "손 쫌 내밀어 봐", "손 내밀어 주랑께", "팔 뻗쳐 봐", "팔 쭉 내밀어 보거라",
    "야 봐봐, 루미야 팔 뻗어 줘", "봐봐 루미야 손 내밀어", "얘들아 봐 루미야 손 줘",
]

# ---------- arm_fold: the arm back to its look pose ----------
ARM_FOLD = [
    "fold your arm", "fold the arm", "fold arm", "fold it", "fold it back", "fold your arm back", "fold your arm up",
    "fold up your arm", "fold your arm now", "fold your arm please", "you can fold your arm", "you can fold it now",
    "put your arm down", "put the arm down", "put your arm away", "put your arm back", "put arm back",
    "put your hand down", "put your hand away", "put your hand back", "take your arm back", "take your hand back",
    "take back your arm", "take your arm away", "pull your arm back", "pull your arm in", "pull your hand back",
    "pull back your arm", "pull it back", "draw your arm back", "draw back your arm", "bring your arm back",
    "bring your arm in", "bring the arm home", "bring the arm back", "arm back", "arm back home", "arm back please",
    "arm back in", "arm in", "arm down", "arm down please", "arm home", "arm away", "arm rest", "arm go back",
    "arm back home if you don't mind", "your arm, put back", "you close arm please, put back", "close arm",
    "retract your arm", "retract the arm", "retract arm", "tuck your arm in", "tuck it in", "tuck your arm away",
    "lower your arm", "lower the arm", "lower your hand", "drop your arm", "rest your arm", "relax your arm",
    "back to your look pose", "back to look position", "look pose", "go back to your look pose", "arm to look pose",
    "return your arm", "return the arm", "reset your arm", "reset the arm", "arm to home position",
    "okay, put your arm down", "okay arm back", "thanks, arm back", "that's enough, fold your arm",
    "you can put your arm down now", "you can take your hand back", "you can lower your arm now",
    "fold your arm, it's in the way", "fold you arm", "fold yor arm", "fould your arm", "fold ur arm", "arm fold",
    "arm fold please", "arm close", "arm close please", "you fold arm", "put back arm",
    # Korean
    *_ko(["팔 접어", "팔 좀 접어", "팔 다시 접어", "팔 거둬", "팔 좀 거둬", "팔 내려", "팔 좀 내려", "팔 넣어", "팔 다시 넣어",
          "팔 원위치 해", "팔 원래대로 해", "팔 제자리로 해", "손 내려", "손 거둬", "손 접어", "손 다시 넣어", "손 넣어",
          "팔 치워", "손 치워", "팔 원래 자리로 해", "팔 원위치로 돌려", "팔 돌려놔", "팔 접고 있어"], ASK_SHORT),
    "팔 접으세요", "팔 접으십시오", "팔 거두세요", "팔 거두십시오", "팔 내리세요", "팔 내리십시오", "팔 내려놓으세요",
    "팔 원위치", "팔 원래대로", "팔 제자리로", "팔 제자리", "이제 접어", "접어", "접어 줘", "접어 주세요", "넣어", "됐어 넣어",
    "이제 팔 접어도 돼", "팔 접어도 돼", "팔 내려도 돼", "이제 팔 내려", "고마워 팔 접어", "됐어 팔 내려", "팔 쉬어", "팔 쉬어도 돼",
    "arm 접어", "arm 접어 줘", "arm 내려", "arm down 해", "팔 down", "팔 fold", "팔 fold 해 줘", "fold arm 해 줘",
    "팔 내려 please", "팔 접어조", "팔 저버", "팔 거더", "팔 내려조", "팔 접어 보이소", "팔 접어 부러", "팔 접어 봐유",
    "얘 로봇아 arm 접어 줘", "루미야, arm 접어 줘", "팔 걷어", "팔 오므려", "팔 모아", "팔 다시 가져가",
]

# ---------- arm_open / arm_close: the gripper (with nothing held: the hand reader refuses an open while holding) ----------
ARM_OPEN = [
    "open your hand", "open hand", "open the hand", "open your fingers", "open the gripper", "open your gripper",
    "open gripper", "open your claw", "open up your hand", "open up", "open your hand wide", "spread your fingers",
    "unclench your hand", "unclench", "hand open", "hand open please", "fingers open", "gripper open",
    "release your grip", "loosen your grip", "relax your fingers", "open your hand please", "please open your hand",
    "can you open your hand", "could you open your gripper", "show me an open hand", "you open hand", "opn your hand",
    "open you hand", "open ur hand",
    *_ko(["손 펴", "손 좀 펴", "손 벌려", "손 좀 벌려", "손가락 펴", "손 열어", "그리퍼 열어", "그리퍼 좀 열어", "집게 열어",
          "집게 벌려", "손 쫙 펴", "손바닥 펴", "손 활짝 펴"], ASK_SHORT),
    "손 펴세요", "손 펴십시오", "손 오픈", "그리퍼 오픈", "손 open", "hand 펴", "gripper open 해", "open 해 손", "손 펴조",
]
ARM_CLOSE = [
    "close your hand", "close hand", "close the hand", "close your fingers", "close the gripper", "close your gripper",
    "close gripper", "close your claw", "make a fist", "clench your hand", "clench your fist", "squeeze your fingers",
    "shut your hand", "hand closed", "hand close please", "fingers close", "gripper close", "close your hand please",
    "please close your hand", "can you close your hand", "could you close your gripper", "show me a fist",
    "you close hand", "clos your hand", "close you hand", "close ur hand",
    *_ko(["손 쥐어", "손 꽉 쥐어", "주먹 쥐어", "주먹 꽉 쥐어", "손 오므려", "손가락 오므려", "손 닫아", "그리퍼 닫아",
          "그리퍼 좀 닫아", "집게 닫아", "집게 오므려"], ASK_SHORT),
    "손 쥐세요", "주먹 쥐십시오", "손 클로즈", "그리퍼 클로즈", "손 close", "gripper close 해", "주먹 쥐어조",
]

# ---------- pick: an object from the table in front ----------
PICK = [
    "pick up the <obj>", "pick the <obj> up", "pick up that <obj>", "pick up a <obj>", "pick <obj> up", "pick up <obj>",
    "take the <obj>", "take that <obj>", "grab the <obj>", "grab that <obj>", "grab a <obj>", "get the <obj>",
    "lift the <obj>", "lift up the <obj>", "snag the <obj>", "nab the <obj>", "seize the <obj>",
    "go on, pick up the <obj>", "go ahead, pick up the <obj>", "now pick up the <obj>", "okay pick up the <obj>",
    "it would be great if you picked up the <obj>", "i'd be grateful if you picked up the <obj>",
    "i'd like you to pick up the <obj>", "i want you to grab the <obj>", "would you mind picking up the <obj>",
    "could you please pick up the <obj>", "can you grab the <obj> for me", "please pick up the <obj>",
    "show me you can pick up the <obj>", "let me see you pick up the <obj>", "can i see you pick up the <obj>",
    "reach for the <obj> and pick it up", "reach for the <obj>", "grab the <obj> on the table",
    "pick up the <obj> on the table", "pick the <obj> off the table", "take the <obj> off the table",
    "you take <obj>", "you pick <obj>", "you pick up <obj> please", "you grab <obj>", "you can take the <obj>",
    "you peek up the <obj>", "peek up the <obj>", "pik up the <obj>", "pick op the <obj>", "pickup the <obj>",
    "pick upp the <obj>", "grap the <obj>", "grabb the <obj>", "take da <obj>", "pick up da <obj>", "pic up the <obj>",
    *_ko(["<obj> 집어", "<obj> 좀 집어", "<obj> 하나 집어", "<obj> 들어", "<obj> 좀 들어", "<obj> 잡아", "<obj> 좀 잡아",
          "<obj> 집어 올려", "<obj> 들어 올려", "그 <obj> 집어", "저 <obj> 집어", "저기 <obj> 집어", "테이블 위에 <obj> 집어",
          "<obj> 손으로 집어", "<obj> 쥐어"], ASK_SHORT),
    "<obj> 집으세요", "<obj> 집으십시오", "<obj> 잡으세요", "<obj> 집어 볼래?", "<obj> pick 해 줘", "<obj> pick up 해",
    "<obj> 픽업 해 줘", "<obj> 픽 해 줘", "<obj> grab 해", "<obj> take 해", "<obj> 그랩 해", "grab 해 <obj>", "<obj> 집어조",
    "<obj> 지버", "<obj> 잡아조", "봐봐, 루미야 <obj> 집어 봐", "<obj> 집어 보이소", "<obj> 집어 부러", "<obj> 집어 봐유",
]

# ---------- fetch: bring an object (from a place) ----------
FETCH = [
    "bring me the <obj>", "bring the <obj> to me", "bring the <obj> here", "bring me a <obj>", "bring over the <obj>",
    "fetch the <obj>", "fetch me the <obj>", "get me the <obj>", "go get the <obj>", "go and get the <obj>",
    "go fetch the <obj>", "grab me the <obj>", "carry the <obj> to me", "deliver the <obj> to me",
    "bring me the <obj> from <place>", "get the <obj> from <place>", "fetch the <obj> from <place>",
    "go get the <obj> at <place>", "go to <place> and bring me the <obj>", "bring the <obj> from <place> to me",
    "the <obj> at <place>, bring it to me", "there's a <obj> at <place>, bring it here", "<obj> from <place>, please bring",
    "from <place> the <obj>, bring to me", "i need the <obj> from <place>", "i'd like the <obj> from <place>",
    "could you get me the <obj> from <place>", "can you bring the <obj> from <place>", "you go <place>, bring <obj> me",
    "bring <obj> me from <place>", "fech the <obj> from <place>", "brin me the <obj> from <place>",
    *_ko(["<place>에서 <obj> 가져와", "<place>에서 <obj> 좀 가져와", "<place>에서 <obj> 가져다", "<place>에 있는 <obj> 가져와",
          "<place>에서 <obj> 갖다", "<place>에서 <obj> 가지고 와", "<obj> 가져와", "<obj> 가져다", "<obj> 갖다",
          "<obj> 좀 갖다", "나한테 <obj> 가져다", "<place>에 있는 <obj> 나한테 가져다"], ASK_SHORT),
    "<place>에서 <obj> 좀 가지고 오십시오", "<place>에서 <obj> 가져오십시오", "<place>에서 <obj> 가져오세요",
    "<place>에서 <obj> 브링 해 줘", "<place>에서 <obj> bring 해 줘", "<place>에서 <obj> 가 온나", "<place>에서 <obj> 갖다 주이소",
    "<place>에 <obj> 있는데 그것 좀 갖다 줘", "<place>에 <obj> 있어, 가져와", "<place>에서 <obj> 챙겨 와",
]

# ---------- the hand's (not acted on by the bank: brain.hand_request reads them) ----------
PUT = [
    "put it down", "put it down here", "set it down", "place it down", "put it on the table", "place it on the table",
    "put the cup on the table", "you can put it down now", "put it back", "put it back where it was",
    "내려놔", "내려놔 줘", "내려놔 주세요", "이제 내려놔도 돼", "내려놓아도 돼요", "테이블에 놔", "테이블 위에 놔 주세요",
    "제자리에 놔", "원래 자리에 놔 주세요", "여기 내려놔", "내려나", "내려나 줘", "내려 놔 줘요", "놔 둬",
]
RECEIVE = [
    "take this", "take this from me", "hold this", "here, take it", "here you go", "take it from my hand",
    "can you take this off my hands", "here, you take, is for you", "i'll give you this", "catch this",
    "이거 받아", "이거 받아 줘", "이거 들고 있어", "이거 가져", "이거 잠깐 들어 줄래?", "이거 take 해 줘", "이거 hold 해 줘",
    "take this 해 줘", "제 손에 있는 거 가져가세요", "이거 드릴게요",
]
GIVE = [
    "give it to me", "give me that", "give me it", "give it", "hand it over", "hand it to me", "pass it to me",
    "could i please have the cup", "i'd appreciate it if you passed it to me", "hand the cup down to me",
    "i'll grab it from you", "let me have it", "gimme that", "give it here",
    "줘", "그거 줘", "이리 줘", "나 줘", "저 주세요", "줘 봐", "그거 저 주시면 돼요", "그거 나 주면 돼", "제가 받을게요",
    "이리 주세요", "그거 이리 줘", "줘 빨리", "빨리 줘", "얼른 줘", "그거 넘겨", "건네줘", "그거 저한테 주세요", "give me 해 줘",
]

# ---------- no: talk about the arm and hand, negations, past, remarks, someone else's hand ----------
NO = [
    "the wave was nice", "i saw you wave", "you waved so nicely", "that was a cute wave", "you wave like my grandpa",
    "my daughter waved at you", "the kids waved at you", "a big wave hit the beach", "radio waves can't hurt you",
    "there's a heat wave this week", "microwave the food", "wave pool", "new wave music", "a wave of visitors",
    "the handshake was nice", "i shook hands with him", "we shook hands yesterday", "nice handshake",
    "your hand looks strong", "your hand is cold", "is your hand a gripper", "how strong is your hand",
    "how long is your arm", "your arm is long", "your arm moves smoothly", "the arm looks cool",
    "nice arm", "cool hand", "what a nice gripper", "my hand hurts", "i hurt my arm", "wash your hands",
    "did you wash your hands", "raise your hand if you have a question", "hands up everyone", "everyone wave to the robot",
    "kids, wave to the robot", "wave back at it, mina", "can i wave at you", "can i shake your hand later",
    "give me a hand with this box", "can you lend me a hand", "i need a hand", "give me a break", "give me a second",
    "give me a minute", "give me a call", "give me a hint", "give me five minutes", "give me some space",
    "hold on", "hold on a second", "hang on", "hold that thought", "on the other hand", "hand in hand", "second hand",
    "i have my hands full", "it's out of my hands", "hands down the best", "pick a number", "pick your favourite",
    "pick a song", "take a picture", "take a break", "take care", "take your time", "take it easy", "get some rest",
    "bring it on", "fold the laundry", "the cup is red", "i like that cup", "the bottle is empty", "my cup is here",
    "손 씻었어?", "손 예쁘다", "손이 예쁘네", "손 차가워?", "손 따뜻해?", "팔 길다", "팔 진짜 길다", "팔 멋있다", "손 힘 세?",
    "아까 손 흔드는 거 봤어", "손 흔드는 거 귀엽다", "손 흔드는 로봇이네", "웨이브 멋있다", "어제 악수했어", "악수 좋았어",
    "애들이 손 흔들었어", "와 아까 로봇이 손 흔들었어", "손 흔드는 게 참 신통하네", "손 흔드는 거 좀 어색하지 않아?",
    "민수야 로봇한테 손 흔들어", "얘들아 로봇한테 손 흔들어", "지호야 손 흔들어 봐", "동생아 로봇한테 손 흔들어 봐",
    "할머니 손 흔들어 주세요 사진 찍을게요", "손 들어 보세요 여러분", "질문 있으면 손 들어", "손 들고 질문하세요",
    "손 잡고 가자", "손 시려", "손 아파", "팔 아파", "팔이 저려", "손이 모자라", "손이 많이 가", "손 좀 빌려줘",
    "일손이 부족해", "손 놓고 있어", "손 떼", "손대지 마", "만지지 마", "손 씻고 올게", "손 닦아", "팔짱 껴",
    "컵 예쁘다", "컵 몇 개 들 수 있어?", "사과 좋아해", "바나나 맛있어", "그 컵 내 거야", "물병 비었어",
    "커피 한 잔 줘", "물 한 잔 줘", "아메리카노 한 잔 주세요", "시간 좀 줘", "기회 줘", "힌트 줘", "잠깐 시간 줘",
    "문 열어 줘", "문 열어", "문 좀 열어 주세요", "창문 열어", "뚜껑 열어 줘", "병 열어 줘", "마음을 열어 봐", "문 닫아 줘",
    "창문 닫아", "뚜껑 닫아 줘", "open the door", "close the door", "open the window", "open the box", "open the bottle",
    "open the lid", "close the window", "가위바위보", "주먹 인사", "fist bump", "high five", "하이파이브",
    "전화 줘", "연락 줘", "문자 줘", "답 줘", "대답 좀 해 줘", "칭찬 좀 해 줘", "사인 해 줘", "사진 찍어 줘",
]

WAVE += _en(["wave", "wave your hand", "wave at us", "wave hello", "wave goodbye", "wave us off", "wave one more time",
             "shake hands", "shake my hand", "shake hands with me", "give us a wave", "say hi with your hand",
             "say hello with your arm", "greet us with a wave", "wave to the camera"])
ARM_REACH += _en(["reach out", "reach out your arm", "hold out your hand", "give me your hand", "give me a hand",
                  "stretch out your arm", "put your hand out", "extend your arm", "reach toward me", "hold your arm out"])
ARM_FOLD += _en(["fold your arm", "put your arm down", "pull your arm back", "take your hand back", "bring your arm back",
                 "go back to your look pose", "lower your arm", "tuck your arm in", "put your hand down"])
ARM_OPEN += _en(["open your hand", "open the gripper", "open your fingers", "spread your fingers"])
ARM_CLOSE += _en(["close your hand", "close the gripper", "close your fingers", "make a fist"])
PICK += _en(["pick up the <obj>", "grab the <obj>", "take the <obj> from the table", "lift the <obj>"])
FETCH += _en(["bring me the <obj>", "fetch the <obj>", "get me the <obj> from <place>", "go get the <obj> at <place>"])

WHO_KO = ["할머니한테", "할아버지한테", "애들한테", "아이들한테", "손님들한테", "관객들한테", "우리 딸한테", "우리 아들한테", "손주한테",
          "카메라 보고", "저기 사람들한테", "친구들한테"]
WAVE += _ko([f"{w} 손 흔들어" for w in WHO_KO] + [f"{w} 손으로 인사해" for w in WHO_KO], ASK_SHORT)
WAVE += [f"wave to {w}" for w in ("my grandma", "my grandpa", "the kids", "my son", "my daughter", "the visitors",
                                   "the people over there", "the camera", "my friends", "the audience")]
ARM_REACH += _ko(["할머니한테 손 내밀어", "애들한테 손 내밀어", "손님한테 손 내밀어", "저 사람한테 팔 뻗어", "이쪽으로 손 내밀어",
                  "손 좀 이리 내밀어", "핸드 줘", "핸드 내밀어"], ASK_SHORT)
ARM_FOLD += _ko(["팔 기본 자세로 해", "팔 기본 위치로 돌려", "손 이제 내려", "손 얼른 거둬", "팔 원래 자리로 돌려", "arm 접어",
                 "arm 내려", "hand back 해"], ASK_SHORT)

INTENT = {"wave": WAVE, "arm_reach": ARM_REACH, "arm_fold": ARM_FOLD, "arm_open": ARM_OPEN, "arm_close": ARM_CLOSE,
          "pick": PICK, "fetch": FETCH, "put": PUT, "receive": RECEIVE, "give": GIVE, "no": NO}
