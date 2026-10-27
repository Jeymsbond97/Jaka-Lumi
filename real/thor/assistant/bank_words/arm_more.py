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
    "hand me that", "hand me that, thank you", "hand me that, thank you very much", "pass me that, thanks",
    "hand that over, thank you", "hand me that one please",
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


# ---------- a reason before or after the order ("…, my mom wants a picture", "리허설 중이에요, …"), train-set gaps ----------
EN_CORE = {
    "WAVE": ["wave", "say bye with your hand", "shake my hand", "wave at the kids"],
    "ARM_REACH": ["hold your hand out to me", "give me your hand", "reach out your arm"],
    "ARM_FOLD": ["put your arm down", "rest your arm", "fold your arm"],
    "ARM_OPEN": ["open your hand", "hand open"],
    "ARM_CLOSE": ["close your hand", "make a fist"],
    "PICK": ["pick up the <obj>", "pick the <obj> up"],
}
KO_CORE = {
    "WAVE": ["손 흔들어 줘", "악수해요", "손으로 인사해 줘"],
    "ARM_REACH": ["손 줘 봐", "팔 뻗어 줘", "손 내밀어 줘"],
    "ARM_FOLD": ["팔 접어 줘", "손 내려 줘"],
    "ARM_OPEN": ["손 펴 줘", "그리퍼 열어 줘"],
    "ARM_CLOSE": ["주먹 꽉 쥐어 줘", "손 쥐어 줘"],
    "PICK": ["<obj> 집어 줘", "<obj> 잡아 주세요"],
}
EN_AFTER = ["{}, my mom wants a picture", "{}, we're making a video", "{} for the photo",
            "{}, it's for a video", "{}, i'm filming"]
EN_BEFORE = ["we're filming, {}", "for the video, {}", "ok so my friend dared me, {}", "smile for the camera and {}",
             "one, two, three, {}", "3, 2, 1, {}", "let's see you {}", "i'd love to see you {}", "i want you {}"]
KO_AFTER = ["{}, 사진 찍게", "{}, 애들이 좋아해", "{}, 영상 찍고 있어", "{} 기념으로", "{}, 할머니가 보고 싶대"]
KO_BEFORE = ["리허설 중이에요, {}", "촬영 중인데 {}", "녹음 중인데, {}", "하나 둘 셋, {}", "자 이제 {}", "기념 사진 찍을게, {}"]
_REASON = {}
for k, cores in EN_CORE.items():
    _REASON[k] = [f.format(c) for c in cores for f in EN_AFTER + EN_BEFORE]
for k, cores in KO_CORE.items():
    _REASON[k] += [f.format(c) for c in cores for f in KO_AFTER + KO_BEFORE]
WAVE += _REASON["WAVE"]
ARM_REACH += _REASON["ARM_REACH"]
ARM_FOLD += _REASON["ARM_FOLD"]
ARM_OPEN += _REASON["ARM_OPEN"]
ARM_CLOSE += _REASON["ARM_CLOSE"]
PICK += _REASON["PICK"]
ARM_OPEN += ["let go", "let go now", "okay, let go", "let go of it", "release", "release now", "손 놔", "손 놓아",
                       "그리퍼 놔", "hand open 해 줄래", "손 오픈 해 줄래"]
ARM_CLOSE += ["꽉 쥐어", "꽉 쥐어 줘", "꽉 쥐어 주면 좋겠어", "주먹 꽉 쥐어 주게", "손 꽉 쥐시게"]
ARM_REACH += ["give me 손", "give me 손 해 줘", "손 give me", "your hand to me, robot", "robot, your hand to me",
                        "손 줘 봐 손", "손 손 줘", "할머니한테 손 줘 봐", "애기한테 손 줘", "손님한테 손 줘 봐요"]
WAVE += ["악수하세", "악수하세나", "에구 악수하세", "악수 한번 하세나", "let's see you wave like a queen", "wave like a king",
                   "wave like a princess", "wave like a superstar", "wave like a pro", "핸드 웨이브 해", "손 웨이브"]
ARM_FOLD += ["rest your arn", "fold your arn", "put your arn down", "back to look position please",
                       "look position please", "go back to the look position", "팔 룩 포지션"]
PICK += ["<obj> 좀 들게", "<obj> 잡게나", "<obj> 들어부러", "<obj> 집어부러", "<obj> 좀 쪼까 집어 줘",
                   "<obj> 집어 주시기 바랍니다", "<obj> 잡아 주시기 바랍니다", "<obj> 들어 주시기 바랍니다", "<obj>좀들어주시기바랍니다",
                   "you have to take the <obj>", "you must pick up the <obj>", "you are can take the <obj>",
                   "i am tourist, please lift the <obj>", "<obj> 픽업해", "<obj> 픽업해 줘요"]
FETCH += ["<obj> 브링해 줘", "<obj> 브링해", "<obj> 브링해 주시겠습니까", "<place>에서 <obj> 브링해", "<place>에서 <obj> 브링해 줘",
                   "<obj> 가져와 주시기 바랍니다", "<obj> 갖다 주시기 바랍니다", "<place>에서 <obj> 가져와 주시기 바랍니다",
                   "<place>에서 <obj> 가져와 주시기 부탁드립니다", "<place>에 있는 <obj> 갖다 주시겠어요", "<place>에서 <obj>갖다주게나",
                   "<obj> 갖다 줘 ㅎㅎ", "you bring <obj> please", "you bring <obj> from <place> please"]


# ---------- hard negatives for every capability: negation, past, ability, condition, later, remarks ----------
NEG_EN = {"wave": ("wave", "waved", "waving"), "shake hands": ("shake hands", "shook hands", "shaking hands"),
      "hold out your hand": ("hold out your hand", "held out your hand", "holding out your hand"),
      "fold your arm": ("fold your arm", "folded your arm", "folding your arm"),
      "open your hand": ("open your hand", "opened your hand", "opening your hand"),
      "close your hand": ("close your hand", "closed your hand", "closing your hand"),
      "pick up the cup": ("pick up the cup", "picked up the cup", "picking up the cup"),
      "bring me the cup": ("bring me the cup", "brought me the cup", "bringing me the cup")}
NEG_KO = {"손 흔들어": ("손 흔들", "손 흔들었", "손 흔드는", "손 흔들"), "악수해": ("악수하", "악수했", "악수하는", "악수할"),
      "손 내밀어": ("손 내밀", "손 내밀었", "손 내미는", "손 내밀"), "팔 접어": ("팔 접", "팔 접었", "팔 접는", "팔 접을"),
      "손 펴": ("손 펴", "손 폈", "손 펴는", "손 펼"), "주먹 쥐어": ("주먹 쥐", "주먹 쥐었", "주먹 쥐는", "주먹 쥘"),
      "컵 집어": ("컵 집", "컵 집었", "컵 집는", "컵 집을"), "컵 가져와": ("컵 가져오", "컵 가져왔", "컵 가져오는", "컵 가져올")}
_neg = []
for base, past, ing in NEG_EN.values():
    _neg += [f"don't {base}", f"please don't {base}", f"never {base} again", f"you don't have to {base}", f"no need to {base}",
           f"you {past} earlier", f"you {past} yesterday", f"did you {base}?", f"can you really {base}?", f"have you ever {past}?",
           f"if the guests come, {base}", f"{base} when i say so", f"{base} later", f"{base} tomorrow", f"minsu, {base}",
           f"mom, {base}", f"i saw you {base}", f"stop {ing}", f"i love {ing}", f"{ing} is fun", f"you're good at {ing}",
           f"why did you {base}?", f"who told you to {base}?", f"robots can {base}", f"i wonder if you can {base}",
           f"do you know how to {base}?", f"i'd rather you didn't {base}", f"you shouldn't {base} now", f"wait, don't {base}"]
for imp, (stem, past, adn, fut) in NEG_KO.items():
    _neg += [f"{stem}지 마", f"{stem}지 마세요", f"{stem}지 마십시오", f"{stem}지 마시게", f"{stem}지 마이소", f"{stem}지 말아 주세요",
           f"{past}어?", f"{past}잖아", f"아까 {past}어요", f"어제 {past}습니다", f"{fut} 수 있어?", f"{fut} 줄 알아?",
           f"{adn} 거 봤어", f"{adn} 거 멋있다", f"{adn} 거 신기하네요", f"{adn} 로봇이네", f"손님 오면 {imp}", f"나중에 {imp}",
           f"내일 {imp}", f"민수야 {imp}", f"엄마 {imp} 봐", f"{imp} 달라고 누가 그랬어?", f"왜 {past}어?", f"{imp} 안 해도 돼",
           f"{imp} 필요 없어", f"{imp}도 돼?", f"{adn} 게 좋아", f"{imp} 그만", f"{adn} 건 나중에 하자"]
NO += [t for t in _neg if not t.startswith(("minsu,", "mom,", "민수야", "엄마", "can you really"))]   # a name or "can you" is
# also how a real request starts: those stay with the guards (For B2)


# ---------- Korean kids / elderly / non-native / chat slang ----------
WAVE += ["로봇아 손 흔들어 흔들어", "손 흔들어 흔들어", "안녕 안녕 손 흔들어", "빠빠이 해 빠빠이", "로봇 빠이빠이", "로봇 안녕 해 손으로",
         "어이 로봇 양반 손 좀 흔들어 보게", "이 사람아 악수나 하세", "젊은이 악수 한번 하세", "로봇 양반 손 한번 흔들어 보시게",
         "손 흔들어 주세요 로봇 씨", "로봇 손 흔들어요 제발", "악수 해요 우리", "손 흔들어 주세요 부탁", "손 흔들어 ㄱㄱ", "악수 ㄱ",
         "웨이브 ㄱㄱ", "손 흔들어 ㅇㅇ", "손인사 ㄱㄱ", "악수 ㄱㄱ해", "손 흔들어줘 ㅎㅎ", "악수하자 ㅋㅋ", "손 흔들어 주세용 ㅎㅎ",
         "로봇아 우리 애한테 손 흔들어 줘라", "애기한테 빠빠이 해 줘", "우리 손주한테 손 좀 흔들어 주게"]
ARM_REACH += ["로봇 손 줘 손", "손 손 손 줘", "손 줘 손", "로봇아 손", "손 내밀어 내밀어", "젊은이 손 좀 내밀어 보게",
              "로봇 양반 손 좀 줘 보게", "이 사람아 손 좀 내밀어 보게나", "손 주세요 부탁", "로봇 씨 손 주세요", "팔 뻗어 ㄱ",
              "손 내밀어 ㅇㅇ", "손 줘 ㅎㅎ", "팔 쭉 ㄱㄱ", "우리 애가 손 잡게 손 좀 내밀어 줘", "애기 손 잡게 손 내밀어 줘"]
ARM_FOLD += ["팔 접어 접어", "팔 넣어 넣어", "로봇 팔 접어", "로봇 양반 팔 좀 접게", "이 사람아 팔 거두게", "팔 접어 주세요 부탁",
             "로봇 씨 팔 접어요", "팔 접어 ㄱㄱ", "팔 ㄴㄴ 접어", "팔 넣어 ㅇㅇ", "팔 접어줘 ㅎㅎ", "팔 원위치 ㄱ"]
ARM_OPEN += ["손 펴 펴", "로봇 손 펴", "손 펴 보게 젊은이", "손 펴 주세요 부탁", "손 펴 ㄱㄱ", "손 쫙 펴 ㅎㅎ", "그리퍼 오픈 ㄱ"]
ARM_CLOSE += ["주먹 쥐어 쥐어", "주먹 좀 쥐어 보게 젊은이", "주먹 쥐어 주세요 부탁", "주먹 ㄱㄱ", "손 꽉 ㅎㅎ",
              "그리퍼 클로즈 ㄱ"]
PICK += ["<obj> 집어 집어", "로봇 <obj> 집어", "<obj> 좀 집어 보게 젊은이", "로봇 양반 <obj> 좀 집어 주게", "<obj> 집어 주세요 부탁",
         "<obj> 잡아 ㄱㄱ", "<obj> 집어 ㅇㅇ", "<obj> 들어 봐 ㅎㅎ", "<obj> 픽 ㄱ"]
FETCH += ["<obj> 가져와 가져와", "로봇 <obj> 가져와", "<obj> 좀 가져오게 젊은이", "로봇 양반 <obj> 좀 가져다 주게", "<obj> 가져와 주세요 부탁",
          "<obj> 갖다 줘 ㄱㄱ", "<obj> 가져와 ㅇㅇ", "<obj> 갖다 줘 ㅋㅋ"]


# ---------- whisper slips from the train sets (송 = 손, 해져 = 해 줘, hend, weib, gib) and more frames ----------
SLIP_FRAMES = ["any chance you could {}", "{}, chop chop", "{}, there's a good robot", "let's have you {}", "{}, test one",
      "hey you, {}", "{}, can?", "{}, ok?"]
SLIP_CORES = {"wave": ["wave", "shake hands", "wave hello"], "arm_reach": ["hold out your hand", "reach toward me", "offer me your hand"],
        "arm_fold": ["fold your arm", "put your arm down"], "arm_open": ["open your hand"], "arm_close": ["close your hand"],
        "pick": ["pick up the <obj>", "pick the <obj> up"]}
for _k, _v in SLIP_CORES.items():
    {"wave": WAVE, "arm_reach": ARM_REACH, "arm_fold": ARM_FOLD, "arm_open": ARM_OPEN, "arm_close": ARM_CLOSE,
     "pick": PICK}[_k].extend(f.format(c) for c in _v for f in SLIP_FRAMES)
WAVE += ["gib me a shake", "pliz gib me a shake", "give me a shek", "give everyone a wave", "give everyone weib",
                   "weib please", "give weib", "wayve like a queen", "wave one more itme", "하이 웨이브 해", "하이 웨이브",
                   "나랑 악수", "나랑악수", "저랑 악수", "우리 악수", "안녕 해져 손으로", "웨이브 해져", "손 흔들어 져", "악수 해져",
                   "손 흔드러 주소", "악수 shake 해 줄래", "hello wave 해 줄래", "손 wave 한번 해 봐"]
ARM_REACH += ["송 줘", "송 이리 줘", "송 한번 줘요", "저한테 송 줘", "송 이리 주면 안 돼?", "송 내밀어", "송 좀 내밀어 줘",
                        "손 내밀어 져", "손 줘 져", "reach for me for mi", "reach for mi", "giv hand", "gib hand", "gib me hand",
                        "손!", "손 쫌 주이소", "앞으로 팔 내밀어 주실래요", "reach 해 봐"]
ARM_FOLD += ["기본 pose 로 해", "기본 포즈로 해", "기본 포즈로 돌아가", "기본 자세로 돌아가", "기본 자세", "기본 pose",
                       "팔 기본 포즈", "팔 접어 져", "손 다시 넣어 져", "팔 넣어 져", "folf your arm", "fold yuor arm", "put yor arm down"]
ARM_OPEN += ["송 좀 펴 줄래요", "송 펴", "송 펴 줘", "손 펴 져", "opeen your hand", "open yor hand", "open hend",
                       "release ㄱㄱ", "release 해", "release 해 줘", "릴리즈 해 줘"]
ARM_CLOSE += ["clench your hend", "cllose hand", "close hend", "close yor hand", "clos hend", "손 쥐어 져",
                        "주먹 쥐어 져", "손가락 쥐어", "손가락 쥐어 줘", "손가락 쥐어 주겠나", "꽉 쥐세요", "그리퍼 오므리시겠어요",
                        "집게 꽉 닫아 봐", "그리퍼 클로즈 해 줘"]
PICK += ["<obj> 픽업 해", "<obj> 픽업 해 줘", "<obj> grab 해 줄 수 있어", "take <obj> 해 주이소", "grab the <obj> 가능?",
                   "<obj> 집어 져", "<obj> 잡아 져", "<obj> 집어! 가즈아", "<obj> 들어라", "<obj> 잡아 봐요"]
NO += ["송 불러 줘", "송 하나 불러", "송 틀어 줘", "생일 송 불러 줘", "노래 송 틀어", "손 송 노래", "drop the beat", "drop the mic",
                "let it go 불러 줘", "sing let it go", "release the song", "give everyone a break", "give everyone a minute"]


# ---------- fresh negatives (new frames and slang) and arm things Lumi can't do: all "no" ----------
NEG2_EN = {"wave": ("wave", "waved", "waving"), "shake": ("shake my hand", "shook my hand", "shaking hands"),
      "reach": ("reach out", "reached out", "reaching out"), "fold": ("put your arm down", "put your arm down", "putting your arm down"),
      "open": ("open the gripper", "opened the gripper", "opening the gripper"),
      "close": ("make a fist", "made a fist", "making a fist"), "pick": ("grab the bottle", "grabbed the bottle", "grabbing the bottle"),
      "fetch": ("fetch the cup", "fetched the cup", "fetching the cup")}
_neg2 = []
for base, past, ing in NEG2_EN.values():
    _neg2 += [f"nah, don't {base}", f"bro don't {base}", f"plz don't {base}", f"u don't gotta {base}", f"no {ing} please",
               f"quit {ing}", f"enough {ing}", f"you {past} like five minutes ago", f"you already {past}",
               f"remember when you {past}?", f"lol you {past} at me", f"bet you can't {base}", f"i dare you not to {base}",
               f"would you {base} if i asked?", f"are you gonna {base}?", f"is it hard to {base}?", f"how do you {base}?",
               f"what happens if you {base}?", f"do robots like to {base}?", f"my little brother can {base} too",
               f"my robot at home can {base}", f"the other robot {past} at me", f"once the show starts, {base}",
               f"only {base} when the music stops", f"after lunch you can {base}", f"{base} in an hour",
               f"jiwoo, {base}", f"Sarah, {base}", f"kids, {base}", f"guys, {base}", f"i'm gonna {base} now", f"let me {base} first",
               f"{ing} looks easy", f"{ing} must be boring for you", f"love the way you {base}", f"you {base} so smoothly"]
NEG2_KO = {"wave": ("손 흔들", "손 흔들었", "손 흔드는", "손 흔들", "손 흔들어"), "shake": ("악수하", "악수했", "악수하는", "악수할", "악수해"),
      "reach": ("팔 뻗", "팔 뻗었", "팔 뻗는", "팔 뻗을", "팔 뻗어"), "fold": ("팔 거두", "팔 거뒀", "팔 거두는", "팔 거둘", "팔 거둬"),
      "open": ("그리퍼 열", "그리퍼 열었", "그리퍼 여는", "그리퍼 열", "그리퍼 열어"),
      "close": ("주먹 쥐", "주먹 쥐었", "주먹 쥐는", "주먹 쥘", "주먹 쥐어"), "pick": ("병 집", "병 집었", "병 집는", "병 집을", "병 집어"),
      "fetch": ("컵 갖다주", "컵 갖다줬", "컵 갖다주는", "컵 갖다줄", "컵 갖다줘")}

for stem, past, adn, fut, imp in NEG2_KO.values():
    _neg2 += [f"{stem}지 마라", f"{stem}지 마쇼", f"{stem}지 말게", f"{stem}지 마유", f"{stem}지 마 ㅋㅋ", f"{stem}지 않아도 됩니다",
               f"{stem}기 싫어", f"{stem}기 전에 물어봐", f"{past}던데?", f"{past}다며?", f"방금 {past}지?",
               f"{past}을 때 귀여웠어", f"{adn} 거 또 보고 싶다", f"{adn} 거 어떻게 배웠어?", f"{adn} 게 힘들어?", f"{adn} 로봇 처음 봐",
               f"{fut} 수 있으려나", f"{fut} 수 있다고 들었어", f"{fut} 거야?", f"{fut} 때 말해 줘", f"공연 끝나면 {stem}자",
               f"점심 먹고 {stem}자", f"한 시간 뒤에 {stem}기", f"지우야 {imp} 봐", f"얘들아 {imp} 봐", f"우리 동생도 {fut} 줄 알아",
               f"나도 {fut} 수 있어", f"{adn} 거 별로야", f"{adn} 거 대박", f"{adn} 거 ㄹㅇ 신기"]
ARM_CANT = [  # arm things Lumi can't do: nothing must move (the LLM says why)
    "arm wrestle with me", "let's arm wrestle", "팔씨름 한판 하자", "팔씨름 하실래요?", "swing your arm around fast", "팔 막 휘둘러 봐",
    "팔 빙빙 돌려 봐", "spin your arm in circles", "make a finger heart", "손가락 하트 해 주세요", "do the flower pose", "꽃받침 해 줘",
    "꽃받침 포즈 해 주세요", "make a v sign", "브이 해 줘", "브이 포즈 해 주세요", "give me a thumbs up", "엄지 척 해 주세요", "따봉 해 줘",
    "clap for us", "박수 쳐 주세요", "박수 좀 쳐 봐", "count to five on your fingers", "손가락으로 다섯까지 세 봐", "scratch my back",
    "등 좀 긁어 줘", "등 긁어 주세요", "tap my friend on the shoulder", "내 친구 어깨 좀 톡톡 쳐 줘", "take a selfie with your arm",
    "팔로 셀카 찍어 줘", "hold my umbrella", "우산 좀 들어 줘", "우산 씌워 주세요", "hold my baby", "아기 좀 안아 줘", "애기 좀 잠깐 들고 있어",
    "hold this hot pot", "뜨거운 주전자 좀 들어 줘", "stir my coffee", "커피 좀 저어 줘", "pour me some water", "물 좀 따라 줘",
    "물 따라 주세요", "wipe the table", "테이블 좀 닦아 줘", "wash my cup", "컵 좀 씻어 주세요", "cut this ribbon", "이 리본 잘라 줘",
    "tie my shoes", "신발 끈 묶어 줘", "turn the page", "책장 넘겨 줘", "type on my laptop", "노트북에 타자 쳐 줘", "write my name",
    "내 이름 써 줘", "open this bottle", "병뚜껑 따 줘", "이 병 좀 열어 주세요", "open the drawer", "서랍 열어 줘", "open my umbrella",
    "우산 펴 줘", "knock on the door", "문 두드려 줘", "press the button", "그 버튼 눌러 줘", "엘리베이터 버튼 눌러 주세요",
    "punch the wall", "벽 쳐 봐", "주먹으로 벽 쳐", "toss me the ball", "공 던져 줘", "throw it to me", "던져 줘", "kick the ball",
    "공 차 줘", "feed me", "밥 먹여 줘", "carry my suitcase", "캐리어 좀 끌어 줘", "carry this heavy box", "이 무거운 상자 들어 줘",
    "hand out these flyers", "전단지 좀 나눠 줘", "give me a tissue", "휴지 한 장 줘", "hold the door", "문 좀 잡아 줘",
    "raise the cup over your head", "컵 머리 위로 들어", "shake the cup", "컵 흔들어 봐", "clink cups with me", "건배하자 컵 부딪혀",
    "wave with the cup in your hand", "컵 든 채로 손 흔들어", "pick it up off the floor", "바닥에 있는 거 주워 줘", "바닥에 떨어진 컵 주워",
]
NO += [t for t in _neg2 if not t.startswith(("jiwoo,", "Sarah,", "kids,", "guys,", "지우야", "얘들아"))] + ARM_CANT


# ---------- very formal Korean frames, cute endings, English frames (r12 gaps); "the moment …", "can your model …" ----------
KO_END9 = [" 주십사 부탁드립니다", " 주실 것을 요청드립니다", " 주시기를 요청합니다", " 주지 않겠는가", " 주실 수 있으신지요",
           " 주실 수 있으신지요? 부탁드려요", " 줘용 응응", " 줘 응응", " 줄래 ㅎ? 응응?", " 주시기를 부탁드립니다", " 줘라 응"]
KO_DO9 = ["{}도록 하게", "{}도록 하세요", "{}도록 하십시오"]
KO_SI9 = ["{}시기 바랍니다", "{}시겠습니까", "{}시지 않겠습니까"]
SI_STEM = {"손 흔들": "손 흔드", "손 내밀": "손 내미", "팔 뻗": "팔 뻗으", "팔 접": "팔 접으", "<obj> 집": "<obj> 집으"}   # + 시
EN_FR9 = ["your mission, should you accept it: {}", "care to {}", "any time now, {}", "{} for little old me",
          "{}, would you be a star", "{}, much obliged", "on the double, {}", "{}, good good", "{} now is ok",
          "make for me {}", "lumi dear, {}", "lumi my friend, {}"]
CORES9 = {
    "WAVE": (["shake hands with me", "wave goodbye", "wave at us"], ["손 흔들어", "악수해", "잘 가라고 손 흔들어"], ["손 흔들", "악수하"]),
    "ARM_REACH": (["hold out your hand", "give me your hand"], ["손 내밀어", "팔 뻗어", "손 줘"], ["손 내밀", "팔 뻗"]),
    "ARM_FOLD": (["put your arm back", "fold your arm"], ["팔 접어", "팔 원래대로 돌려놔", "암 원래대로 돌려놔"], ["팔 접", "팔 거두"]),
    "ARM_OPEN": (["open your hand"], ["손 펴", "손 벌려"], ["손 펴"]),
    "ARM_CLOSE": (["close your hand", "make a fist"], ["손 오므려", "주먹 쥐어"], ["주먹 쥐"]),
    "PICK": (["pick up the <obj>", "get hold of the <obj>"], ["<obj> 집어", "<obj> 집어 올려", "<obj> 들어"], ["<obj> 집"]),
    "FETCH": (["bring me the <obj>"], ["<obj> 가져와", "<obj> 갖다"], ["<obj> 가져오"]),
}
for k, (en, ko, stems) in CORES9.items():
    _more = [f.format(c) for c in en for f in EN_FR9] + [c + e for c in ko for e in KO_END9] + \
        [f.format(s) for s in stems for f in KO_DO9] + [f.format(SI_STEM.get(s, s)) for s in stems for f in KO_SI9]
    {"WAVE": WAVE, "ARM_REACH": ARM_REACH, "ARM_FOLD": ARM_FOLD, "ARM_OPEN": ARM_OPEN, "ARM_CLOSE": ARM_CLOSE, "PICK": PICK,
     "FETCH": FETCH}[k].extend(_more)
NO += [
    "the moment the bell rings, bring me the cup", "the moment the music starts, wave", "the second i clap, shake my hand",
    "the minute she arrives, hold out your hand", "the instant i say go, pick up the cup", "벨 울리는 순간 컵 가져와",
    "음악 시작하는 순간 손 흔들어", "out of curiosity, can your model pick up a cup", "can your model wave",
    "can this model shake hands", "does your model have a gripper", "just curious, can your arm reach the table",
    "궁금해서 그런데 이 모델도 컵 집을 수 있어?", "이 모델은 악수도 돼?", "컵 흔들어 봐", "컵 들고 흔들어", "컵 든 채로 손 흔들어 봐",
    "hold the cup and wave", "wave the cup around", "shake the cup for me",
]


# ---------- r13 gaps: arm things said another way, and arm things Lumi can't do said like an order ----------
ARM_REACH += _ko(["손 가까이 가져와", "손 좀 가까이 가져와", "손 이쪽으로 가져와", "팔 가까이 가져와", "핸드 한 번만 내밀어",
                  "꼬마한테 핸드 내밀어", "우리 아들한테 손 뻗어"], ["", " 줘", " 주라", " 주시길 바랍니다", " 주시길 부탁드립니다", " 줘, 응?"]) + [
    "bring your hand closer", "bring your hand closer to me", "move your hand closer", "your hand a bit closer please",
    "hand closer", "reach your hand closer to me"]
ARM_FOLD += _ko(["팔 좀 쉬게 해", "팔 쉬게 해", "암 다시 접어", "손 거둬라 카이", "팔 접어라 카이", "팔 좀 쉬어"],
                ["", " 줘", " 주세요", " 주실 수 있으신가요?", " 주시게"]) + ["let your arm rest", "give your arm a rest", "rest that arm"]
ARM_OPEN += ["spread your claw", "spread your claw all the way", "open your claw all the way", "spread the claw wide",
             "claw open", "집게 활짝 펴", "집게 쫙 벌려"]
WAVE += ["give us a big wave from up high", "big wave from up high", "wave high up", "wave up high", "손 높이 들고 흔들어",
         "손 위로 높이 흔들어 줘"]
PICK += _ko(["앞에 있는 잔 들어", "그 잔 들어", "잔 집어", "잔 하나 들어"], ["", " 줄래요?", "라", " 주세요"])
NO += [
    "팔 막 휘둘러", "팔 세게 휘둘러 봐", "팔 미친 듯이 흔들어", "flail your arm", "swing your arm wildly",
    "wave your arm like crazy", "pick the bottle up off the floor", "grab the cup down there on the ground", "pick it up from the ground",
    "바닥에 있는 병 집어", "땅에 떨어진 컵 주워 줘", "바닥에서 컵 집어 줘", "손가락 세 개 펴", "손가락 두 개만 펴 봐",
    "손가락 하나 펴", "show me three fingers", "hold up two fingers", "양손에 컵 하나씩 들 수 있어?", "두 손으로 컵 들 수 있으세요?",
    "can you hold a cup in each hand?", "이 컵 2층으로 가져가 줘", "이 컵 위층으로 갖다 줘", "take this cup upstairs",
    "carry this cup to the second floor", "꾸벅 인사 해", "꾸벅 인사 해 주라", "고개 숙여 인사해", "bow to the guests",
    "hand open이야", "hand open 상태야", "손 open이야", "그리퍼 open이야", "hand close야", "손 오픈 상태야", "your hand is open now",
    "경례 해", "거수경례 해 주게나", "salute like a soldier", "손 들어 경례", "put your hand up like a student", "손 들어 질문하는 것처럼",
]


# ---------- third negative sweep: quotes, hypotheticals, wishes, permission, how-to, sarcasm, 못 / 안, -거든, tags ----------
NEG3_EN = [("wave", "waving"), ("shake hands", "shaking hands"), ("hold out your hand", "holding out your hand"),
      ("fold your arm", "folding your arm"), ("open your hand", "opening your hand"), ("close your hand", "closing your hand"),
      ("pick up the cup", "picking up the cup"), ("bring me the cup", "bringing me the cup")]
_neg3 = []
for b, ing in NEG3_EN:
    _neg3 += [f"he said '{b}'", f"she told you to {b}, didn't she", f"the sign says {b}", f"the manual says {b}",
           f"what if you {b}?", f"imagine if you could {b}", f"pretend to {b}", f"i wish you would {b}", f"i hope you {b} someday",
           f"how do i make you {b}?", f"teach me how to make you {b}",
           f"oh great, now you {b}", f"you can't even {b}",
           f"don't you dare {b}", f"next time {b}", f"{ing} again? no",
           f"no more {ing} today", f"try not {ing}", f"stop trying to {b}"]
NEG3_KO = [("손 흔들", "손 흔들어", "손 흔드는"), ("악수하", "악수해", "악수하는"), ("손 내밀", "손 내밀어", "손 내미는"),
      ("팔 접", "팔 접어", "팔 접는"), ("손 펴", "손 펴", "손 펴는"), ("주먹 쥐", "주먹 쥐어", "주먹 쥐는"),
      ("컵 집", "컵 집어", "컵 집는"), ("컵 가져오", "컵 가져와", "컵 가져오는")]
for st, imp, adn in NEG3_KO:
    _neg3 += [f"엄마가 '{imp}' 하래", f"선생님이 {imp} 보래", f"{imp} 보라고 했던가?", f"만약에 {imp} 주면 어떨까", f"{imp} 주면 좋을 텐데",
           f"{imp} 주는 날이 오겠지", f"{st}는 법 알려 줘", f"어떻게 하면 {imp} 줘?", f"{imp} 달라고 해도 돼?", f"제가 {imp} 달라고 해도 될까요?",
           f"{st}지도 못하면서", f"{st}지 못하지?", f"너 {st}지 못하잖아", f"{st}기는 무슨", f"{imp} 주긴 뭘 {imp} 줘",
           f"{st}거든 말해", f"손님 오시거든 {imp}", f"내가 신호 주면 {imp}", f"끝날 때 {imp}", f"{imp} 줄 거지?", f"{imp} 주는 거 맞지?",
           f"{st}지 마 제발", f"그만 {st}어", f"이제 {st}지 말자", f"{adn} 연습 중이야?"]
NO += _neg3


# ---------- arm-set misses after round 2: "next thing: …", "test one: …", "-해 주면 땡큐", dialect, slips ----------
WAVE += [
    "악수해 보이소", "악수해 주소", "우리 악수해 주소", "반갑게 악수 해 주쇼", "sake hands", "sake hands now", "shak hands",
    "wave, it'll be epic", "yo, wave, it'll be fun", "next thing: wave", "test one: wave", "wave 해 주면 땡큐"]
ARM_REACH += [
    "stick your arm out to me", "stick your arm out to me real quick", "your han, please", "your hand, please robot",
    "hand out 해 주면 땡큐", "손 out 해", "지금 손 out 해", "손 reach 부탁드려요", "next thing: hold out your hand",
    "test one: reach out"]
ARM_FOLD += [
    "손 이제 내러 주실래요", "손 이제 내려 주소", "팔 원래대로 돌려어 볼래요", "retract 부탁해요", "retract 해 줄래", "팔 제자리로 빨리 가져와라", "팔 제자리로 가져와",
    "팔 bakc 해 봐", "팔 백 해 봐", "next thing: fold your arm"]
ARM_OPEN += [
    "you hand open", "you hand open please", "open up! do it!", "open up, do it", "next thing: open your hand",
    "next thing: open hand", "test one: spread your fingers", "spread ur fingers", "손 open 해 봐",
    "release please 해 줘", "송가락 벌려", "송가락 벌려 주면 좋겠어", "let it go, open your hand"]
ARM_CLOSE += [
    "grip", "grip please", "grip 가능?", "grip 가자", "그리퍼 close 가자", "gripper close 해 주면 땡큐", "close hand, will ya",
    "close hand please", "손 지금 닫아 줘", "음주먹쥐어라", "주먹쥐어라", "next thing: make a fist", "test one: close your hand",
    "teacher said I can ask you: close the gripper"]

INTENT = {"wave": WAVE, "arm_reach": ARM_REACH, "arm_fold": ARM_FOLD, "arm_open": ARM_OPEN, "arm_close": ARM_CLOSE,
          "pick": PICK, "fetch": FETCH, "put": PUT, "give": GIVE, "receive": RECEIVE, "no": NO}
