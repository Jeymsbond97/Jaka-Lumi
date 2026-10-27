"""More arm and hand wordings for the intent bank (night 5, beyond assistant/bank_words/arm.py): new verbs, frames
and keywords for every arm / hand capability, side words for pick and put ("왼쪽에 있는 컵 집어", "put it down to your
right": the bank keeps them pick / put, the side itself is the rules' or the LLM's), Korean at every level (반말,
해요체, 하십시오체, 하게체, honorific, dialect, Konglish, slips), and hard negatives for "no" (questions about the arm,
remarks, applause and hand gestures Lumi has none of, past, other people's hands).

Endings are written plainly once per stem: the bank stores Korean as wording.ko_plain reads it, so "주십시오" and
"주세요" become one wording; what grows the bank is new verbs and frames, not more endings.
"""
from assistant.bank_words.arm import _ko, _en, ASK_SHORT

# speech levels the ASK lists of arm.py do not have (하게체, 하오체, honorific, more dialect, slips)
LEVELS = ["", " 줘", " 주세요", " 주십시오", " 주시게", " 주시오", " 주쇼", " 주이소", " 줘유", " 주랑께", " 주라", " 줘라",
          " 봐", " 보래이", " 봐라잉", " 보소", " 봐유", " 주시지요", " 주시죠", " 주실 수 있으세요?", " 주시겠어요?",
          " 줄래", " 줄래요?", " 줘요", " 조", " 쥬", " 도", " 주실래요?"]
SHORT = ["", " 줘", " 주세요", " 주십시오", " 주시게", " 주쇼", " 줘유", " 봐", " 보래이"]

# ---------- wave (every handshake form: the owner's meaning) ----------
WAVE = [
    "give me a shake", "let's shake on it", "shake on it", "how about a shake", "can we shake hands",
    "let's do a handshake", "handshake time", "time for a handshake", "a handshake, robot", "shake hands, robot",
    "shake my hand, friend", "let me shake your hand", "i'd like to shake your hand", "i want to shake your hand",
    "i want to shake hands with you", "i'd like a handshake", "shake hands with my son", "shake hands with grandma",
    "shake hands with our guest", "shake hands with the kids", "go ahead and shake my hand", "come on, shake my hand",
    "wave hi to my son", "wave bye to grandma", "wave them goodbye", "wave so long", "wave farewell",
    "say bye-bye with your hand", "say bye bye with your arm", "flap your hand", "waggle your hand",
    "wiggle your hand hello", "do the waving thing", "do the hand wave", "hand hello", "give the camera a wave",
    "say hi to the camera with your hand", "wave to the nice lady", "wave at my kid", "wave at the baby",
    "wave at my little sister", "wave to my brother", "show the kids your wave", "do your little wave",
    "wave us goodbye", "wave them hello", "give my mom a wave", "give the kids a wave", "a little wave for the kids",
    "one big wave for us", "wave like you mean it", "wave really big", "wave slowly", "wave nicely",
    "you make wave", "do wave hand please", "wave hand to me robot", "hand wave for me", "make hand shake with me",
    "make handshake with me please", "you and me handshake", "handshake with me", "shake hand me please",
    "please hand shake", "robot hand shake", "robot, wave wave", "wave wave robot", "robot robot wave",
    "say bye bye robot, wave", "bye bye wave robot", "hello wave robot", "gimme a wave", "throw me a wave",
    "toss us a wave", "give us a little wave", "wave at your fans", "wave to your fans",
    "would you be so kind as to wave", "would you kindly shake my hand", "would you kindly wave to us",
    "be so kind as to wave", "i would appreciate a wave", "a wave would be lovely", "please greet us with your hand",
    "greet my mother with a wave", "greet the guests with a wave", "welcome them with a wave",
    "wave to welcome them", "wave to say goodbye", "wave to say hello",
    *_en(["wave to my kids", "give me a shake", "shake on it", "wave them goodbye", "wave so long"]),
    # Korean, every level
    *_ko(["손 살랑살랑 흔들어", "손 흔들흔들 해", "손 좌우로 흔들어", "손 들어서 흔들어", "손 번쩍 들어 흔들어",
          "손으로 빠이빠이 해", "손으로 작별 인사 해", "손 흔들어서 배웅해", "손 흔들어 배웅해", "손 흔들어 환영해",
          "손 흔들어서 반겨", "손 흔들어 반겨", "손 흔들며 인사해", "손 흔들어 안녕 해", "반갑게 손 흔들어",
          "크게 손 흔들어", "손 크게 한번 흔들어", "손 천천히 흔들어", "나한테 손 흔들어", "저한테 손 흔들어",
          "우리 애한테 손 흔들어", "손녀한테 손 흔들어", "손자한테 손 흔들어", "엄마한테 손 흔들어", "아빠한테 손 흔들어",
          "카메라에 손 흔들어", "사진 찍을 때처럼 손 흔들어", "악수 한번 해", "나랑 악수 한번 해", "악수로 인사해",
          "핸드셰이크 해", "쉐이크 핸즈 해", "웨이빙 해", "핸드 웨이브 해", "바이 바이 해", "굿바이 손 흔들어",
          "하이 손 흔들어"], LEVELS),
    "손 흔드시게", "손 흔드시오", "손 흔드십시오", "손 흔드세요", "손 흔드셔요", "손 좀 흔드시지요", "손 흔들어 주시지요",
    "악수 한번 하시지요", "악수 한번 하시죠", "악수 청합니다", "악수 부탁드립니다", "악수 부탁해요", "악수 좀 부탁해",
    "악수 한번 합시다", "악수 한번 하세", "악수 하세나", "악수나 하세", "악수하시게", "악수 하시오",
    "할아버지께 손 흔들어 드려", "할머니께 손 흔들어 드리세요", "선생님께 손 흔들어 드려요", "어르신께 손 흔들어 드리십시오",
    "손님들께 손 흔들어 드리세요", "어르신께 손으로 인사드려", "손님께 손으로 인사드리세요", "할머니랑 악수해 드려",
    "할아버지랑 악수 한번 해 드려요", "선생님이랑 악수하세요", "회장님께 악수 청해 드리세요",
    "악수 하입시더", "악수 하자이", "악수 하장께", "악수 하드라고", "악수 하자 마", "악수 해 보이소", "악수 하쇼",
    "손 쪼까 흔들어 봐", "손 흔들어 주소마", "손 흔들어 보래이", "손 흔들어 봐라잉", "손 흔드쇼", "손 흔드소",
    "핸즈 쉐이크", "쉐이크 핸즈", "쉐이크 핸즈 플리즈", "웨이브 플리즈", "핸드 웨이브", "핸드 웨이브 플리즈",
    "웨이빙 플리즈", "바이바이 플리즈", "하이 해 줘 손으로", "손으로 하이 해", "shake hands 해 주세요",
    "wave 좀 해 주세요", "손 wave 해 주세요", "handshake 좀 해요", "악수 please", "please 악수",
    "손 흔드러 조", "손 흔들러 줘", "손흔들어", "손흔들어줘", "손흔들어주세요", "악수해조", "악쑤 해 줘", "악수 해쥬",
    "악수하쟝", "악수 해 주라", "악수하자구", "악수하자고", "손 흔들어 쥬세요", "손 흔드러 주세여", "손 흔들어 주세여",
    "자 악수", "자, 악수하자", "그럼 악수하자", "반가워, 악수", "반갑습니다 악수 한번 하시죠", "만나서 반가워요 악수해요",
    "잘 가 손 흔들어", "안녕 손 흔들어 줘", "빠빠이 손 흔들어", "바이바이 손 흔들어 줘",
]

# ---------- arm_reach: hold the arm out ("give me your hand", "손 줘", "손 내밀어") ----------
ARM_REACH = [
    "give us your hand", "put out your hand", "put out your arm", "reach your hand to me", "reach me your hand",
    "extend your hand to me", "extend your arm out", "extend your arm toward me", "hold your arm straight out",
    "arm straight forward", "hand forward please", "can i get your hand", "let's see that hand", "bring your hand out",
    "your arm, stretch it out", "out with your hand", "your hand, give it here", "your hand, hold it out",
    "stretch your arm toward me", "stretch your hand to me", "reach your arm toward me", "reach your arm forward",
    "arm out to me please", "arm toward me", "hand toward me", "reach over to me", "reach over here",
    "hold out a hand", "hold a hand out", "offer a hand", "give me your paw", "give paw", "paw please",
    "robot gimme hand", "give hand robot", "you give hand me", "hand give me", "your hand give me please",
    "please you reach hand", "reach hand please", "you reach out please", "make arm long", "make your arm long",
    "long arm", "big reach", "reach far", "reach as far as you can", "stretch as far as you can",
    "would you be so kind as to give me your hand", "would you kindly hold out your hand",
    "may i have your hand, please", "i'd like to hold your hand", "let me hold your hand", "let me see your arm out",
    *_en(["give me your paw", "put out your hand", "extend your hand to me", "reach your hand to me"]),
    *_ko(["손 뻗쳐", "팔 뻗쳐", "손 앞으로 쭉", "팔 앞으로 쭉 뻗어", "팔 쭉 내밀어", "손 이리 내", "손 내 봐", "손 좀 내",
          "손 내어", "팔 내어", "손 쭉 뻗어", "팔 쭉 빼", "팔 앞으로 빼", "손 앞으로 빼", "팔 길게 내밀어", "팔 멀리 뻗어",
          "나한테 팔 내밀어", "저한테 팔 뻗어", "이쪽으로 팔 뻗어", "나 쪽으로 손 뻗어", "내 쪽으로 손 내밀어",
          "제 쪽으로 팔 뻗어", "손 줘 봐", "핸드 아웃 해", "암 아웃 해", "리치 아웃 해", "팔 익스텐드 해",
          "팔 스트레치 해", "리치 해"], LEVELS),
    "손 내미시게", "팔 뻗으시게", "손 내미시오", "팔 뻗으시오", "손 내미십시오", "팔 뻗으십시오", "손 내미세요",
    "팔 뻗으세요", "손 내밀어 주시지요", "손 좀 내어 주시겠어요?", "손 내주세요", "손 내줘", "손 내줄래?",
    "손 좀 내 주시겠습니까?", "할머니께 손 내밀어 드려", "어르신께 팔 뻗어 드리세요", "선생님께 손 내밀어 드리세요",
    "손님께 손 내밀어 드려요", "손 내밀어 보래이", "손 쫌 내 봐라", "팔 뻗어 보랑께", "손 내밀어 주쇼", "손 내미소",
    "팔 뻗어 봐라잉", "손 내밀어 보소", "팔 쫌 뻗어 보이소", "손 쪼까 내밀어 봐", "핸드 아웃", "암 아웃", "리치 아웃",
    "핸드 플리즈", "hand 좀 줘 봐", "손 out 해", "arm 좀 뻗어 줘", "팔 쭉 reach 해", "손내밀어", "손내밀어줘",
    "팔뻗어", "팔뻗어줘", "손 내미러 줘", "팔 뻐더 봐", "손 내미러", "팔 뻗어 쥬", "손 내밀어 쥬세요", "손 쥬", "손 조",
    "손 주쇼", "손 주시게", "손 주시오", "손 좀 주시지요", "손 이리 주시게", "손 이리 내 봐", "자 손", "자, 손 줘",
    "루미 손", "루미야 손 좀", "손 한번 줘 봐", "손 한 번만 줘", "팔 한번 뻗어 봐", "팔 한 번만 뻗어 줘",
]

# ---------- arm_fold: the arm back to its look pose ----------
ARM_FOLD = [
    "arm back to normal", "back to your normal pose", "reset arm position",
    "go back to resting position", "rest position", "arm to rest", "arm to rest position",
    "put your arm back where it was", "pull in your arm", "bring your arm in close", "fold it up", "fold up",
    "fold back", "retract", "retract it", "retract your hand", "pack your arm away", "stow your arm", "stow the arm",
    "park your arm", "arm in please", "arm away please", "that's enough, arm back", "ok thanks, you can retract",
    "withdraw your arm", "withdraw your hand", "take your hand away", "put that arm away", "arm back, robot", "arm back to look", "back to look", "look pose please",
    "arm to the look pose", "you arm back please", "put arm in", "put arm down", "arm back now",
    "all done, arm back", "we're done, fold your arm", "done shaking, arm back", "okay you can retract your arm",
    "bring it back in", "bring your hand back", "pull your hand in", "draw your hand back", "arm back to start",
    "arm to start position", "starting position, arm", "neutral position", "arm neutral", "arm to neutral",
    "fold your arm away", "fold the arm in", "tuck your arm back in", "tuck the arm away",
    "would you kindly put your arm down", "would you be so kind as to fold your arm",
    *_en(["retract your arm", "stow your arm", "pull in your arm", "put your arm back where it was",
          "bring your hand back"]),
    *_ko(["팔 원래 자세로 해", "팔 기본 자세로 돌려", "팔 원상복구 해", "팔 원상태로 해", "팔 정위치 해", "팔 제자리에 둬",
          "팔 다시 원래대로 해", "팔 집어넣어", "손 집어넣어", "팔 거둬들여", "팔 당겨", "팔 안으로 넣어", "팔 몸쪽으로 붙여",
          "팔 붙여", "팔 회수해", "팔 복귀해", "팔 원위치 복귀해", "팔 정리해", "팔 다시 접어 놔", "팔 거둬 들여",
          "손 다시 가져가", "손 거둬들여", "팔 리셋 해", "팔 폴드 해", "팔 룩 포즈로 해",
          "팔 리트랙트 해", "팔 안쪽으로 접어", "팔 몸에 붙여"], SHORT),
    "손 거두세요", "손 거두시오", "팔 거두시게", "팔 접으시게", "팔 접으시오", "팔 거두어 주십시오", "팔 거두어 주세요",
    "팔 접어 주시지요", "팔 내리시게", "팔 내리시오", "손 거두시게", "팔 원위치 하십시오", "팔 원위치 해 주시죠",
    "팔 접어라 마", "팔 접어 보래이", "팔 쫌 접으소", "팔 접어 주쇼", "팔 거둬 부러", "팔 접어 주랑께", "팔 접으쇼",
    "팔 거둬유", "팔 쪼까 접어 봐", "암 폴드", "팔 폴드", "팔 리셋", "arm reset 해", "arm reset 해 줘",
    "팔 룩 포즈로", "룩 포즈로 팔 접어", "팔 리트랙트", "retract 해 줘", "팔 retract 해",
    "팔접어", "팔접어줘", "팔 저버 줘", "팔 거더 줘", "팔 너어", "팔 너어 줘", "팔 접어 쥬", "팔 접어 주세여", "팔내려",
    "팔 원위치요", "팔 원위치 좀", "됐어, 팔 접어", "다 됐어 팔 거둬", "악수 끝, 팔 접어", "수고했어 팔 접어",
    "고마워요 이제 팔 접으세요", "감사합니다 이제 팔 거두셔도 됩니다", "이제 손 거둬도 돼", "이제 팔 넣어",
]

# ---------- arm_open / arm_close: the gripper ----------
ARM_OPEN = [
    "open your gripper wide", "open the fingers", "fingers apart", "spread the gripper", "open the claw", "unclamp",
    "unclamp your gripper", "release the gripper", "gripper open please", "open up your gripper", "open your pincers",
    "open hand please robot", "hand open you", "you open finger", "open finger", "open fingers please",
    "open your hand all the way", "open the hand wide", "spread your hand", "spread your hand out", "palm open",
    "relax your grip", "open the grip",
    *_en(["open your gripper wide", "unclamp your gripper", "spread your hand", "open your pincers"]),
    *_ko(["손가락 벌려", "그리퍼 벌려", "집게 펴", "손 쫙 벌려", "손 열어 봐", "손 오픈 해", "그리퍼 오픈 해", "손 펼쳐",
          "손바닥 펼쳐", "손가락 쫙 펴", "손 활짝 열어", "그리퍼 활짝 열어", "집게 활짝 벌려", "손가락 벌려 봐",
          "손 쫙 펼쳐"], SHORT),
    "손 펴시게", "손 펴시오", "손 펴 보래이", "손 펴 주쇼", "손 펴 봐유", "손펴", "손펴줘", "손 벌려 주십시오",
    "그리퍼 여시게", "그리퍼 여십시오", "손 여세요", "손 펴 주시지요", "핸드 오픈", "핸드 오픈 해 줘", "그리퍼 오픈 플리즈",
    "open 해 줘 그리퍼", "gripper 열어", "hand open 해 줘", "손 펴 쥬", "손가락 펴 조",
]
ARM_CLOSE = [
    "close your pincers", "clamp your gripper", "close the claw", "fingers together", "pinch your fingers",
    "pinch your fingers together", "shut the gripper", "close up your hand", "squeeze your hand", "make a fist please",
    "fist please", "close fingers", "you close finger", "hand close you", "close the hand all the way",
    "close the fingers", "curl your fingers", "ball your hand", "make a fist for me",
    *_en(["close your pincers", "clamp your gripper", "fingers together"]),
    *_ko(["손가락 모아", "그리퍼 오므려", "집게 쥐어", "손 닫아 봐", "손 클로즈 해", "그리퍼 클로즈 해", "손 꽉 오므려",
          "손가락 오므려 봐", "그리퍼 꽉 닫아", "집게 꽉 닫아", "주먹 쥐어 봐"], SHORT),
    "주먹 쥐시게", "주먹 쥐시오", "손 쥐어 보래이", "손 오므려 봐유", "손쥐어", "주먹쥐어", "그리퍼닫아", "그리퍼 닫으십시오",
    "손 닫으세요", "주먹 쥐어 주시지요", "핸드 클로즈", "핸드 클로즈 해 줘", "그리퍼 클로즈 플리즈", "close 해 줘 그리퍼",
    "gripper 닫아", "hand close 해 줘", "주먹 쥐어 쥬", "손 오므려 조",
]

# ---------- pick: an object; the side words keep it a pick (the bank's quick pick takes no side: rules / LLM) ----------
SIDE_EN = ["on your left", "on your right", "to your left", "to your right", "on the left", "on the right",
           "on the left side", "on the right side", "next to you", "beside you", "at your side", "in front of you",
           "right in front of you", "over on the right", "over on the left", "on your left side", "on your right side"]
SIDE_KO = ["왼쪽에 있는", "오른쪽에 있는", "왼쪽", "오른쪽", "왼편에 있는", "오른편", "옆에 있는", "네 왼쪽에 있는",
           "너 오른쪽에 있는", "앞에 있는", "바로 앞에 있는", "좌측", "우측", "왼쪽 테이블 위", "오른쪽 테이블에 있는",
           "왼쪽 옆에 있는", "오른쪽 옆에 있는", "니 왼쪽에 있는"]
PICK = [
    *[f"pick up the <obj> {s}" for s in SIDE_EN], *[f"grab the <obj> {s}" for s in SIDE_EN[:8]],
    *[f"take the <obj> {s}" for s in SIDE_EN[4:10]],
    "the <obj> on your right, pick it up", "the <obj> on your left, grab it", "get the <obj> on the left side",
    "grab the left <obj>", "pick the right <obj>", "take the left one", "grab the one on the right",
    "pick up the one on your left", "pick up the one to your right", "turn and pick up the <obj> on your left",
    "pluck the <obj>", "scoop up the <obj>", "take hold of <obj>", "get a grip on the <obj>", "grab hold of the <obj>",
    "snatch up the <obj>", "lift up that <obj>", "pick up the <obj>, would you", "robot take <obj>", "get <obj>",
    "<obj>, pick up", "you get <obj>", "you lift <obj> please", "pick <obj> please", "grab <obj> please",
    "would you kindly pick up the <obj>", "would you be so kind as to pick up the <obj>",
    *_en(["pick up the <obj> on your left", "grab the <obj> on your right", "pick up the <obj> next to you"]),
    *_ko([f"{s} <obj> {v}" for s in SIDE_KO for v in ("집어", "잡아")], ["", " 줘", " 주세요", " 주십시오", " 봐"]),
    *_ko(["<obj> 잡아 들어", "<obj> 집어 들어", "<obj> 꽉 잡아", "<obj> 집어 봐", "<obj> 집어 올려 봐",
          "<obj> 픽업 해", "<obj> 들어 올려 봐", "<obj> 그랩 해", "<obj> 테이크 해", "<obj> 쥐어 봐", "그 <obj> 잡아",
          "저기 있는 <obj> 집어", "탁자 위에 <obj> 집어", "책상 위에 <obj> 집어", "<obj> 하나만 집어"], LEVELS),
    "<obj> 집으시게", "<obj> 잡으시오", "<obj> 집으시오", "<obj> 잡으시게", "<obj> 집어 주시지요", "<obj> 집어 보래이",
    "<obj> 쫌 집어 봐라", "<obj> 집어 주쇼", "<obj> 집어 봐라잉", "<obj> 잡아 보소", "<obj> 그랩", "<obj> 픽 업",
    "<obj> 테이크", "<obj>집어", "<obj>집어줘", "<obj> 지버 줘", "<obj> 자바", "<obj> 자바 줘", "<obj> 집어 쥬",
]

# ---------- fetch: bring an object to the person ----------
FETCH = [
    "bring the <obj> over", "bring the <obj> over here", "fetch me that <obj>", "bring the <obj> back to me",
    "could you bring me that <obj>", "carry the <obj> over to me", "deliver me the <obj>", "bring <obj> please",
    "<obj>, bring it here", "the <obj>, bring it to me", "fetch <obj> please", "bring cup", "get me <obj>",
    "bring me <obj> please", "you bring me <obj>", "please bring <obj> to me", "bring <obj> to me please",
    "would you kindly bring me the <obj>", "would you be so kind as to fetch the <obj>",
    "go fetch me the <obj>", "fetch the <obj> for me", "bring the <obj> to me, please", "bring that <obj> here",
    *_en(["bring the <obj> over here", "fetch me that <obj>", "bring the <obj> back to me"]),
    *_ko(["<obj> 갖고 와", "<obj> 챙겨 와", "<obj> 챙겨다", "<obj> 이리 가져와", "<obj> 여기로 갖고 와", "<obj> 좀 챙겨 와",
          "<obj> 가지고 와", "나한테 <obj> 갖고 와", "저한테 <obj> 챙겨 와", "<obj> 갖다 와"], SHORT),
    "<obj> 가지고 오시게", "<obj> 가져오시오", "<obj> 가져오십시오", "<obj> 가져오세요", "<obj> 가 온나", "<obj> 가져 온나",
    "<obj> 갖다 주쇼", "<obj> 가져와 부러", "<obj> 갖고 와유", "<obj> 가져와유", "<obj> 브링 해 줘", "<obj> 가져와줘",
    "<obj>가져와", "<obj> 가져와 주시지요", "<obj> 좀 갖다 주시게", "<obj> 가저와 줘", "<obj> 갖고 와 쥬",
]

# ---------- the hand's (not acted on by the bank; kept apart from the motions): put, give, receive ----------
PUT = [
    "put it down to your right", "put it down to your left", "put it down on your left", "put it down on your right",
    "set it on the left side", "set it on the right side", "place it to the right", "place it to the left",
    "put the <obj> down on the right side", "put the <obj> down on the left side", "put it on the table to your left",
    "put it on the table to your right", "drop it off on the right", "set the <obj> down", "lay it down",
    "lay it on the table", "rest it on the table", "leave it here", "leave it on the table", "put it there",
    "put it back where you found it", "put it down beside you", "put it next to you", "put it down gently",
    "set it down slowly", "place the <obj> on <place>", "put the <obj> at <place>", "drop the <obj> off at <place>",
    "put it on the left table", "put it on the right table", "put it down on the table on your right",
    "release it on the table", "put down the <obj>", "put the <obj> back", "set down the <obj> please",
    "you put down please", "put down please", "you put it table", "cup down please", "put cup on table",
    *_ko(["왼쪽에 내려놔", "오른쪽에 내려놔", "오른쪽 테이블에 내려놔", "왼쪽 테이블에 놔", "왼편에 놔", "옆에 내려놔",
          "네 오른쪽에 내려놔", "좌측에 내려놔", "우측에 놔", "여기 놔", "거기 놔", "저기 내려놔", "<place>에 내려놔",
          "<place>에 놔", "<place> 테이블에 갖다 놔", "<obj> 내려놔", "<obj> 테이블에 놔", "제자리에 갖다 놔",
          "원래 자리에 둬", "살짝 내려놔", "천천히 내려놔", "테이블 위에 살며시 놔", "오른쪽 옆에 놔", "왼쪽 옆에 둬"],
        ["", " 줘", " 주세요", " 주십시오", " 주시게"]),
    "내려놓으십시오", "내려놓으시게", "내려놓으시오", "내려놔 주쇼", "내려놔 보래이", "내려놔 부러", "내려놔유", "내려놓으소",
    "풋 다운 해", "put down 해 줘", "테이블에 put 해", "내려놔 쥬", "내려나 조", "그거 놓으세요", "놓으십시오",
]
GIVE = [
    "hand it here", "pass it over", "pass it here", "give it back", "give it over", "over here, give it",
    "i'll take it", "i'll take it from you", "let me take it", "let me take that", "hand it on over", "pass that to me",
    "give that to me now", "give it to me please", "give me the thing", "give it, please", "hand it",
    "you give me please", "give me now", "now give me",
    "그거 나 줘", "이리 내", "이리 내놔", "내놔", "그거 내놔", "그거 이리 넘겨", "건네 줘", "넘겨 줘", "저한테 넘겨 주세요",
    "저 주십시오", "나한테 줘", "제게 주시겠어요?", "그거 받을게", "제가 받겠습니다", "주라", "줘 봐라", "그거 주소",
    "이리 주이소", "그거 주쇼", "이리 도", "그거 나 도", "줘유", "기브 미", "give 해 줘", "그거 이리 주시게",
    "저에게 건네 주십시오", "할머니 드려", "할머니께 드리세요", "선생님께 드려", "이리 주시지요",
]
RECEIVE = [
    "here, take this", "hold this for me", "take this <obj> from me", "here's the <obj>", "this is for you, take it",
    "can you take this", "would you hold this", "grab this", "hold onto this", "keep this", "take my <obj>",
    "i'm giving you this", "please hold my <obj>", "here, hold it",
    "이거 받아 주세요", "이거 들어 줘", "이거 좀 들고 있어 줘", "이거 잡아", "이거 잡아 줘", "이거 받으세요", "이거 받으십시오",
    "이거 받으시게", "이거 받아라", "이거 받아 주이소", "받아유", "이것 좀 쥐고 있어", 
    "이 <obj> 좀 들고 있어", "이거 너 가져", "이거 너 줄게", "이거 테이크 해", "이거 홀드 해 줘", "자, 받아", "옜다 받아",
]

# ---------- no: about the arm and hand, past, other people, gestures Lumi has none of ----------
NO = [
    "did you just wave", "you waved at me earlier", "why did you wave", "why are you waving", "can your arm reach the shelf",
    "how far can your arm reach", "your arm reached the cup", "you reached out nicely", "no need to wave",
    "you don't have to shake my hand", "my grandma likes it when robots wave", "the robot in the video waved",
    "i'd rather not shake hands", "i don't shake hands", "no handshake please", "is your hand open",
    "is your gripper closed", "why is your hand open", "your fingers are open", "your hand is closed",
    "you dropped the cup", "you picked it up yesterday", "you picked the wrong cup", "that cup is heavy",
    "what can you pick up", "who taught you to wave", "where did you learn to shake hands",
    "the cup on your left is mine", "the cup on the right is empty", "there's a cup on your left",
    "is there a cup on your right", "my cup is on the left", "i put the cup down", "i picked up the cup",
    "she took the cup", "he gave me the cup", "someone left a cup on the table", "pick up the pace",
    "pick up where we left off", "put up with it", "put your hands together for lumi", "give it up for lumi",
    "give a hand to our guests", "let's give him a big hand", "hands up", "hands off", "keep your hands to yourself",
    "hold your horses", "fold the paper", "fold the towel", "reach your goals", "shake it off", "shake the bottle",
    "shake your head", "shake a leg", "wave the flag", "clap your hands", "give me a thumbs up", "do a peace sign",
    "make a heart with your hands", "arm wrestle me", "do push ups", "high five me", "fist bump me", "pinky promise",
    "the gripper looks strong", "your gripper is cool", "nice reach", "good grab", "nice pick", "you put it down well",
    "손 흔들었어?", "아까 손 흔들었잖아", "왜 손 흔들어?", "손 흔드는 거 봤어요", "악수는 됐어", "악수 안 할래", "악수 안 해도 돼",
    "팔 뻗는 거 무섭다", "팔이 어디까지 닿아?", "팔 얼마나 뻗을 수 있어?", "팔 길이가 몇이야?", "손 열려 있어?",
    "그리퍼 닫혀 있네", "손가락이 몇 개야?", "컵 떨어뜨렸어", "아까 컵 집었잖아", "컵 잘 집네", "왼쪽에 컵 있어",
    "오른쪽에 있는 컵 내 거야", "왼쪽 컵 비었어", "오른쪽에 컵 있나?", "컵 누가 놨어?", "컵 내가 내려놨어", "엄마가 컵 가져왔어",
    "박수 쳐 줘", "손뼉 쳐 줘", "박수 쳐", "엄지 척 해 줘", "손가락 하트 해 줘", "손하트 해 줘", "브이 해 줘", "팔씨름 하자",
    "팔 굽혀 펴기 해 봐", "컵 씻어 줘", "손 흔드는 거 처음 봐", "악수하는 로봇이네", "팔이 참 기네요", "손이 크시네요",
    "아까 악수했잖아", "악수 벌써 했어", "팔 접는 소리 났어", "손 내미는 거 귀엽다", "할머니가 손 흔드셨어",
    "손 흔들어 주시던데요", "악수는 나중에 하자", "악수는 다음에 해요", "손 흔드는 건 언제 배웠어?", "컵 집는 거 어려워?",
    "컵 몇 개나 들어?", "그 컵 무거워?", "왼쪽에 있는 컵 뭐야?", "오른쪽 컵 무슨 색이야?", "왼손잡이야?", "오른손잡이야?",
]


# ---------- more frames and endings: "what I need is for you to …", "-주게나", "-주세유", "-주시길 바랍니다" ----------
FRAMES2 = ["what i need is for you to {}", "the plan is, you {}", "i said {}", "all i ask is that you {}", "time to {}",
           "go on and {}", "{} if you would", "{}, would you", "{}, yeah", "your job now is to {}", "next, {}",
           "{} right now", "{} quickly", "{} slowly", "{} for us", "{} one time", "you gotta {}", "you should {} now",
           "hello lumi, {}", "excuse me robot, {}", "mister robot, {}", "lumi, buddy, {}", "{}, my friend"]
KO_END2 = [" 주게나", " 주세유", " 주시길 바랍니다", " 주셨으면 합니다", " 주시면 고맙겠습니다", " 주면 안 될까요?",
           " 주실 수 있을까요?", " 줄 수 있겠니?", " 주겠니?", " 주겠나?", " 주시겠나?", " 주셔", " 줘 봐 응", " 주실래예",
           " 주이소 마", " 줘 볼래?", " 주라 응", " 줘 얼른", " 줘 빨리요", " 주실 수 있나요?"]


def _en2(cores):
    return [f.format(c) for c in cores for f in FRAMES2]


WAVE += _en2(["wave", "wave hello", "shake my hand", "do a little wave", "give us a wave", "shake hands with me"]) + \
    _ko(["손 흔들어", "팔 흔들어", "악수해", "손 인사 해", "손 흔들어서 인사해", "바이바이 해"], KO_END2) + [
    "you and me shake hand", "me and you, handshake", "let us shake hands", "a handshake for me please",
    "i'd love a wave from you", "how about you wave hello", "show everyone your wave", "wave hi, lumi",
    "say hi to my mom with a wave", "it's goodbye time, wave", "wave goodbye to me", "wave to me once",
    "손 흔드세유", "손 흔들어 주시길 바랍니다", "wave 해 주시길 바랍니다", "웨이브 해 주시길 바랍니다", "악수 부탁드려요",
    "악수해 주시면 고맙겠습니다", "인사 손으로 해 주게나", "우리 악수나 하자", "그럼 악수 한번 할까", "악수 한번 할래?"]
ARM_REACH += _en2(["give me your hand", "hold out your hand", "reach out your arm", "stretch out your arm",
                "put your hand out"]) + _ko(["손 줘", "손 내밀어", "팔 뻗어", "손 앞으로 내밀어", "팔 앞으로 뻗어"], KO_END2) + [
    "your hand, give me", "hand, give me", "your hand to me", "your arm to me, please", "me your hand please",
    "give your hand to me now", "i'd like your hand", "hand over here", "arm over here please", "손 한번 주시게",
    "손 한번 주게나", "손 좀 주세유", "손 줘 봐유", "팔 쭉 뻗어 주세유"]
ARM_FOLD += _en2(["fold your arm", "put your arm back", "pull your arm back in", "tuck your arm away", "lower your arm",
               "bring your arm home"]) + _ko(["팔 접어", "팔 거둬", "손 내려", "팔 안으로 거둬", "팔 원위치 해"], KO_END2) + [
    "bring your hadn home", "put arm back where it was", "you can put arm back where it was", "arm back where it was",
    "put your arm where it was", "arm back to where it was", "fold you're arm", "fold your arms", "put your arms down",
    "arms back", "arms in", "팔 안으로 거둬 줘", "팔을 안으로 거둬", "손 이제 내려 줘", "팔 이제 거둬 주게나", "암 백", "암 백 해 줘",
    "arm back 해 줘", "팔 백 해 줘"]
ARM_OPEN += _en2(["open your hand", "release your grip", "open your fingers", "open the gripper"]) + \
    _ko(["손가락 펴", "손 펴", "그리퍼 열어", "손 벌려"], KO_END2) + [
    "let go of your grip", "loosen your fingers", "fingers open please", "open hand now", "손가락 펴 주게",
    "손가락펴줘", "손가락 쫙 펴 주세유"]
ARM_CLOSE += _en2(["close your hand", "grip with your fingers", "make a fist", "close the gripper"]) + \
    _ko(["주먹 쥐어", "손 쥐어", "그리퍼 닫아", "손가락 오므려"], KO_END2) + [
    "grip with your fingers", "grip your fingers", "grip tight", "close your grip", "tighten your fingers",
    "주먹 꽉 쥐어 주시겠습니까", "손 꽉 쥐어 주세유", "주먹쥐어줘"]
PICK += _en2(["pick up the <obj>", "grab the <obj>", "take the <obj>"]) + \
    _ko(["<obj> 집어", "<obj> 잡아", "<obj> 들어"], KO_END2) + [
    "peek up the <obj>", "<obj> 잡아 주게나", "<obj> 집어 주세유", "<obj> 들어 올려 주시길 바랍니다", "the <obj>, grab it",
    "<obj>, take it", "that <obj> there, pick it up", "pick that <obj> up for me", "grab me that <obj>"]
FETCH += _en2(["bring me the <obj>", "fetch the <obj>"]) + _ko(["<obj> 가져와", "<obj> 갖다"], KO_END2)
NO += [
    "she asked you to wave hi to me yesterday", "my grandson told you to shake hands", "you waved to her before",
    "will you wave at the party tomorrow", "never grab that apple without asking", "don't ever pick up my phone",
    "can robots wave", "do robots shake hands", "the robot shook my hand", "you shook my hand earlier",
    "your hand is so cold when we shake", "i'm waving at you", "i'm shaking your hand now", "i'll wave back",
    "look, i'm reaching out", "my arm is tired", "my hand is full", "my fingers are cold", "open your mind",
    "close your eyes", "open your mouth", "close the curtains", "reach for the stars", "hold my beer",
    "grab a seat", "take a seat", "get a grip", "get a grip on yourself", "pick a side", "take my word for it",
    "give me your word", "give me your opinion", "give me your number", "lend me your ears", "fold your hands and pray",
    "shake things up", "wave of the future", "hand me down clothes", "put your feet up", "put it on my account",
    "아까 손자가 악수하라고 했어", "손 흔들라고 누가 그랬어?", "어제 손 흔들어 줬잖아", "내일 행사 때 손 흔들 거야?",
    "손 흔드는 로봇 처음 봐요", "로봇이랑 악수했어요", "손 시려워", "손가락이 아파요", "팔이 아파서 못 들겠어",
    "눈 감아", "입 벌려", "커튼 닫아", "마음 열어", "자리에 앉아", "정신 차려", "손 들어 질문 있어요", "손 씻으러 가자",
    "의자 들어 줄래?", "가방 들어 줘", "백팩 집어 줘", "의자 잡아 줘", "책상 옮겨 줘", "pick up my backpack",
    "grab that chair for me", "lift the table", "carry my bag", "hold the door",
]


# ---------- put and pick from any side, give while holding, receive ----------
SIDES_KO = ["왼쪽", "오른쪽", "왼편", "오른편", "좌측", "우측", "왼쪽 옆", "오른쪽 옆", "니 왼쪽", "네 오른쪽", "옆", "앞",
            "바로 옆", "왼쪽 테이블", "오른쪽 테이블", "왼쪽 탁자", "오른쪽 책상"]
SIDES_EN = ["to your left", "to your right", "on your left", "on your right", "on the left side", "on the right side",
            "to the left", "to the right", "beside you", "next to you", "at your left", "at your right",
            "on the table to your left", "on the table to your right", "on the left table", "on the right table",
            "over on your left", "over to the right", "by your side", "on your left-hand side", "on your right-hand side"]
PUT_END = ["", " 줘", " 주세요", " 주십시오", " 주시게", " 주세유", " 주이소", " 줘유", " 주게나", " 주시길 바랍니다", " 주쇼", " 봐"]
PUT += [f"put it down {s}" for s in SIDES_EN] + [f"set it down {s}" for s in SIDES_EN[:10]] + \
    [f"place the <obj> {s}" for s in SIDES_EN[:8]] + [f"put the <obj> {s}" for s in SIDES_EN[8:16]] + \
    [f"leave it {s}" for s in SIDES_EN[:6]] + [f"drop it {s}" for s in SIDES_EN[:4]] + \
    _ko([f"{s}에 내려놔" for s in SIDES_KO] + [f"{s}에 놔" for s in SIDES_KO[:10]] + [f"{s}에 둬" for s in SIDES_KO[:6]] +
        [f"그거 {s}에 내려놔" for s in SIDES_KO[:6]] + [f"<obj> {s}에 놔" for s in SIDES_KO[:6]] +
        [f"{s}에 내려놓아" for s in SIDES_KO[:4]], PUT_END) + [
    "왼쪽에다 내려놔", "오른쪽에다 놔 줘", "왼쪽에다가 놔", "오른쪽에다가 내려놓으세요", "레프트에 놔", "라이트 쪽에 내려놔",
    "왼쪽 사이드에 놔", "오른쪽 사이드에 내려놔 줘", "put it 왼쪽에", "오른쪽에 put down 해", "왼쪽에 내려나", "오른쪽에 내려 나 줘",
    "put it down at your left side", "on the right, put it down", "left side, put it down", "put down left side please",
    "you put left side", "put cup right side", "the right side, set it there", "over there on the left, put it down",
]
PICK += [f"pick up the <obj> {s}" for s in SIDES_EN[8:]] + [f"take the <obj> {s}" for s in SIDES_EN[:4]] + \
    [f"grab the <obj> sitting {s}" for s in SIDES_EN[:4]] + \
    _ko([f"{s}에 있는 <obj> {v}" for s in SIDES_KO for v in ("집어", "잡아", "들어")], ["", " 줘", " 주세요", " 주십시오", " 주게나", " 주세유"]) + [
    "왼쪽 거 집어", "오른쪽 거 잡아 줘", "왼쪽 것 좀 집어 주세요", "오른쪽에 있는 거 집어", "레프트 컵 집어", "라이트 쪽 <obj> 잡아",
    "the <obj> at your left, take it", "the left <obj>, grab it", "the one on your right, pick it up",
]
GIVE += _ko(["그거 줘", "이리 줘", "나 줘", "저 줘", "그거 이리 건네", "그거 넘겨", "그 <obj> 줘", "들고 있는 거 줘",
            "손에 든 거 줘", "그거 나한테 줘"], ["", " 봐", "요", " 주세유", " 주게나", " 주시길 바랍니다"]) + [
    "give me what you're holding", "give me the thing you're holding", "hand me what you have", "pass me what you got",
    "what you have, give me", "the <obj>, give it to me", "give it me", "give me", "gimme", "gimme it", "hand over",
    "그거 주시게", "그거 주게나", "주세유", "그거 주셔", "줘 봐 응", "그거 건네주세요", "손에 든 거 이리 줘요", "그거 저 줘요",
]
RECEIVE += [
    "here, this is yours", "take this from me please", "this one you hold", "now you here, take this",
    "hold onto this for me", "take it, it's for you", "here, grab this from me", "i'm handing it to you", "keep it for me",
    "이거 받아 주게나", "이거 받아 주세유", "이거 가지고 있어", "이거 들고 계세요", "이거 쥐고 있어 줘", "이것 좀 맡아 줘",
    "이거 맡아 주세요", "자 이거", "옛다", "받으세유", "받아 주시길 바랍니다",
    "이거 받게", "이거 받게나", "이 <obj> 받게", "<obj> 받게", "이 <obj> 받으시게", "이거 받으시오", "이거 받으소", "이거 받아 두게",
]
NO += [
    "왼쪽에 놔둔 컵 누구 거야?", "오른쪽에 둔 거 뭐야?", "왼쪽에 내려놨어?", "오른쪽에 놓을까?", "왼쪽에 놓으면 돼?",
    "어디에 내려놓을까?", "왼쪽이 좋아 오른쪽이 좋아?", "왼쪽 컵 예쁘다", "오른쪽에 있는 컵 누구 거예요?",
    "did you put it on the left?", "should i put it on the right?", "the cup on the left is broken",
    "put it on the left or the right?", "which side should i put it on", "the left one is mine", "i put it on your left",
    "my cup is on your right", "is the cup on the left full?", "you put it down on the left yesterday",
    "왼쪽에 컵 있어?", "오른쪽에 뭐 있어?", "옆에 컵 있네", "앞에 컵 있다",
]


# ---------- dialects (제주, 경상, 전라, 충청), 하오체 / 하게체, honorific receivers, glued slips ----------

DIALECT = [" 줍서", " 주십서", " 도고", " 도가", " 주이소 예", " 주이소마", " 주씨요", " 주쇼 잉", " 줘 잉", " 주랑께요",
           " 주셔유", " 주시유", " 줘 봐유", " 봐 도고", " 주라 마", " 주소 마", " 주게 자네", " 주시구려", " 주구려",
           " 주오", " 주시오 그려", " 주시게나", " 주겠는가?", " 주시겠는가?"]
DIALECT_CORES = [   # (list, stems)
    (WAVE, ["손 흔들어", "악수해", "손 인사 해", "팔 흔들어", "손 흔들어서 인사해"]),
    (ARM_REACH, ["손 내밀어", "팔 뻗어", "손 이리 내밀어", "손 줘"]),
    (ARM_FOLD, ["팔 접어", "팔 거둬", "손 내려", "팔 넣어"]),
    (ARM_OPEN, ["손 펴", "손가락 펴", "그리퍼 열어"]),
    (ARM_CLOSE, ["주먹 쥐어", "손 쥐어", "그리퍼 닫아"]),
    (PICK, ["<obj> 집어", "<obj> 잡아", "<obj> 들어"]),
    (FETCH, ["<obj> 가져다", "<obj> 갖다"]),
]
for _list, _stems in DIALECT_CORES:
    _list += _ko(_stems, DIALECT)
WAVE += [
    "손 흔들어 주시구려", "악수 한번 하시구려", "악수나 한번 하세", "자네 악수 한번 하세", "악수 한번 합세", "손 한번 흔드시오",
    "할머님께 손 한번 흔들어 드리시게", "어르신들께 손 흔들어 드리십시오", "아버님께 악수 청해 보세요", "교수님께 손 흔들어 드려라",
    "손 흔들어 줍서", "손 흔들어 도고", "악수 하입시더 예", "악수 하자 잉", "악수 혀 봐유", "악수 하드래요",
    "손흔들어줘요", "손흔들어봐", "손 흔들어줘", "악수하자요", "악수해요루미", "손흔드러", "손 흔드러 줘요", "악수 해 조요",
    "웨이브해줘", "웨이브해주세요", "쉐이크핸드해줘", "핸드쉐이크해줘", "wave해줘", "wave해주세요", "악수해줄래",
    "wave to grandpa please", "say hi to grandpa with your hand", "wave at mommy", "wave at daddy", "wave to teacher",
    "wave to the teacher please", "go on wave to mister kim", "wave hi to everybody here", "wave to all of us",
    "handshake me please robot", "you shake hand with my father", "please you give me handshake", "shake hand with me ok",
    "shake hands ok", "wave ok", "wave okay?", "you can wave please", "wave for me robot friend",
]
ARM_REACH += [
    "손 좀 내밀어 주시구려", "손 한번 내미시오", "팔 한번 뻗어 보시게나", "자네 손 좀 내밀어 보게", "손 내밀어 줍서", "손 도고",
    "손 이리 도고", "손 내밀어 도고", "팔 뻗어 보래이 마", "손 줘 잉", "손 줘 봐유", "손 이리 주셔유",
    "손내밀어봐", "손줘봐", "손좀줘", "팔뻗어봐", "손 내밀어줘요", "손 쭉내밀어", "팔쭉뻗어줘", "핸드줘", "핸드 내밀어줘",
    "reach out to grandma", "hold your hand out to my son", "give your hand to my daughter", "reach out to the kid",
    "give grandpa your hand", "hold out your hand to the lady", "you give hand to my mom", "hand to grandma please",
]
ARM_FOLD += [
    "팔 거두시구려", "팔 접으시구려", "팔 좀 거두시게나", "자네 팔 좀 접게", "팔 접어 줍서", "팔 접어 도고", "팔 거둬 잉",
    "팔 접어 주셔유", "팔 넣어 도고", "팔접어줘요", "팔거둬", "팔거둬줘", "팔넣어줘", "손내려줘", "팔 내려줘요", "팔 접어줘요",
    "arm back please robot friend", "ok arm in now", "put your arm back now please", "arm back in place",
]
ARM_OPEN += ["손 펴 주시구려", "손 좀 펴 보시게나", "손 펴 줍서", "손 펴 도고", "손펴줘요", "손가락펴", "손가락펴줘요",
                       "그리퍼열어", "그리퍼열어줘"]
ARM_CLOSE += ["주먹 쥐어 주시구려", "손 좀 쥐어 보시게나", "주먹 쥐어 줍서", "주먹 쥐어 도고", "주먹쥐어줘요", "손쥐어줘",
                        "그리퍼닫아줘", "손 꽉쥐어"]
PICK += ["<obj> 집어 주시구려", "<obj> 좀 집어 보시게나", "<obj> 집어 줍서", "<obj> 집어 도고", "<obj>집어줘요",
                   "<obj>잡아줘", "<obj>들어줘", "<obj> 집어줘", "<obj> 잡아줘요", "<obj>좀집어줘"]
FETCH += ["<obj> 가져다 주시구려", "<obj> 좀 가져오시게나", "<obj> 가져다 줍서", "<obj> 갖다 도고", "<obj> 가 온나 마",
                    "<obj>가져다줘요", "<obj>갖다줘", "<obj>좀가져와", "<obj> 가져와줘요"]
NO += [
    "손 흔들어 주면 사탕 줄게", "if you wave i'll clap", "손 흔들면 사진 찍어 줄게", "악수하면 친구 하는 거야", "악수하자고 했잖아",
    "손 흔들어 달라고 했는데 안 했어", "손 흔들어 준 거 고마워", "악수해 줘서 고마워요", "thanks for the wave", "thanks for shaking my hand",
    "that was a good handshake", "i liked your wave", "your wave was too slow", "can you wave faster next time",
    "팔 접는 게 왜 이렇게 느려?", "손 펴는 거 신기하다", "주먹 쥐는 거 귀엽네", "컵 집는 거 다시 보고 싶다",
    "민수야 컵 가져와",
]


# ---------- English depth: indirect, kids, elderly, non-native, slang ----------
WAVE += [
    "it would make her day if you waved", "a wave would make his day",
    "say goodbye to us with a wave", "wave us farewell", "give us a goodbye wave", "a goodbye wave please",
    "wavey wave for the baby", "robot wave hi hi", "do the bye bye", "do bye bye with your hand", "bye bye hand please",
    "hand bye bye", "hand hello please", "hello hand please", "you do hand hello", "make bye bye", "make the wave",
    "wave it", "wave it up", "wave that hand", "wave that arm", "wave that thing", "flap that hand at me",
    "yo wave at me", "yo, shake my hand", "bro, shake hands", "dude, wave", "come shake hands", "c'mon, shake",
    "lemme shake your hand", "lemme get a wave", "gimme a handshake real quick", "quick wave", "quick handshake",
    "if it's no trouble, a wave", "would you mind giving us a wave", "could you do me a wave", "would it be possible to wave",
    "please, a handshake", "kindly greet us by waving", "please greet my grandmother with a wave",
    "you wave hand hello for grandma", "you make handshake grandma", "please doing wave", "doing handshake please",
    "you waving please", "waving please", "waving hand please", "shaking hand please",
]
ARM_REACH += [
    "can the baby touch your hand, hold it out",
    "hold it out so she can touch it", "hold your hand out so we can see it", "put your hand out for the photo",
    "stick your hand out for the picture", "hand out for the photo please", "reach out so i can touch your hand",
    "let her touch your hand", "your hand, let me touch it", "touch hands with me", "high hand please",
    "robot hand out", "robot hand to me", "you hand to me", "hand me hand", "stretch stretch", "arm long long",
    "make arm go out", "arm go out", "arm go forward please", "hand go forward", "yo, hand out", "c'mon, gimme your hand",
    "if it's no trouble, hold out your hand", "would it be possible to extend your arm", "kindly extend your hand",
    "please extend your hand towards me", "please, your hand",
]
ARM_FOLD += [
    "you can stop holding your arm out", "you don't need your arm out anymore, fold it", "no more arm out, fold it",
    "enough with the arm, put it away", "we're done with the arm", "done, arm back", "finished, put your arm away",
    "the photo is done, arm down", "photo's done, you can lower your arm", "arm go back", "arm come back",
    "hand come back", "hand go back", "make arm small", "arm small please", "yo, arm in", "c'mon, put your arm away",
    "if it's no trouble, fold your arm", "would it be possible to lower your arm", "kindly retract your arm",
    "please return your arm to its resting position", "please put your arm back to rest",
    "bring your hand home", "bring your hand home now", "would you please bring your hand home", "hand home please",
    "bring your hand back home", "bring the hand home", "bring your hands home",
]
ARM_OPEN += [
    "open your hand for the photo", "show us your open hand", "open open hand", "hand open open", "make hand open",
    "make the fingers open", "yo, open your hand", "if it's no trouble, open your hand", "kindly open the gripper",
    "would it be possible to open your gripper",
]
ARM_CLOSE += [
    "close your hand for the photo", "make your hand closed", "close close hand", "hand close close", "make hand close",
    "make the fingers close", "yo, close your hand", "if it's no trouble, close your hand", "kindly close the gripper",
    "would it be possible to close your gripper",
]
PICK += [
    "pick up the <obj> for the kids",
    "show the kids, pick up the <obj>", "pick up the <obj> so we can see", "robot pick <obj>", "<obj> pick robot",
    "you <obj> pick up", "<obj> you grab please", "yo, grab the <obj>", "c'mon, pick up the <obj>",
    "if it's no trouble, pick up the <obj>", "kindly lift the <obj>", "would it be possible to pick up the <obj>",
    "please take hold of the <obj>",
]
FETCH += [
    "my son wants the <obj>, bring it", "bring the <obj> to my son", "grandma needs the <obj>, fetch it", "robot bring <obj>",
    "<obj> bring robot", "you <obj> bring me", "yo, bring me the <obj>", "c'mon, fetch the <obj>",
    "if it's no trouble, bring me the <obj>", "kindly fetch the <obj>", "would it be possible to bring me the <obj>",
]
NO += [
    "my son waved at you", "the kids want to wave at you", "my daughter wants to shake your hand later",
    "can my son shake your hand", "can i touch your hand", "may i shake your hand", "should i wave back",
    "is it ok if i wave", "wave if you can hear me", "if you can hear me, wave", "wave when i say go",
    "don't wave yet", "not yet, don't reach out", "wait, don't pick it up yet", "you don't need to fold your arm",
    "no need to open your hand", "your hand doesn't need to close", "i don't want the cup", "i don't need the bottle",
    "the photo was great, thanks", "nice wave, thank you", "great handshake, thanks", "that handshake was firm",
    "wave hello to my friend on the phone, no wait, never mind", "pick it up? no, leave it",
]

INTENT = {"wave": WAVE, "arm_reach": ARM_REACH, "arm_fold": ARM_FOLD, "arm_open": ARM_OPEN, "arm_close": ARM_CLOSE,
          "pick": PICK, "fetch": FETCH, "put": PUT, "give": GIVE, "receive": RECEIVE, "no": NO}
