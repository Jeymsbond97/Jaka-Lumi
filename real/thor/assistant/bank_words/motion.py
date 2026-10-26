"""Head, lift and base wordings for the intent bank (assistant/intent_bank.py): look, lift, turn, move, go_to, come,
follow, come_back, and the "no" kind for words that sound like them but ask nothing.

The bank only picks the kind; the slot (which way, how far, which place) is read from the words by intent_bank._slot,
so every wording here says its way with the plain words that reader knows. Amounts are written the way the bank
compares them (intent_bank.core): "90 degrees", "1 meter"; a marker as <place>.

Lists are built from parts (verbs x ways x endings) and cut to a fixed, spread subset (_pick), so a new verb or
ending reaches every way without writing each sentence out.
"""
import zlib


def _pick(texts, keep):
    """A fixed subset of about `keep` (0..1) of `texts`, spread over them (the same every run), without repeats."""
    out = []
    for t in dict.fromkeys(texts):
        if keep >= 1 or zlib.crc32(t.encode()) % 1000 < keep * 1000:
            out.append(t)
    return out


def _x(*parts):
    """Every join of one choice from each part (a part is a list of strings), spaces tidied."""
    out = [""]
    for p in parts:
        out = [f"{a} {b}" for a in out for b in p]
    return [" ".join(t.split()) for t in out]


EN_FRAMES = ["{}", "{} please", "please {}", "can you {}", "could you {} please", "would you {}", "will you {}",
             "i want you to {}", "i need you to {}", "{} for me", "go ahead and {}", "lumi, {}", "hey lumi, {}",
             "{} now", "can you {} for me", "would you mind if you {}", "just {}", "{} real quick", "{}, okay?",
             "yo, {}", "{} pls", "you {}"]


def _en(bases, keep, hand=()):
    """A share of the built `bases`, a smaller share of them in EN_FRAMES, and every `hand` written wording."""
    return list(hand) + _pick(bases, max(keep * 4, 0.25)) + _pick([f.format(b) for b in list(bases) + list(hand)
                                                                    for f in EN_FRAMES[1:]], keep)


# ---------------- look: the head ----------------
_EN_LOOK_VERB = ["look", "glance", "peek", "take a look", "have a look", "turn your head", "move your head",
                 "swing your head", "point your head", "turn your eyes", "cast your eyes", "check"]
_EN_LOOK_WAY = {d: [f"{d}", f"to the {d}", f"to your {d}", f"at the {d}", f"at the {d} side", f"over to the {d}",
                    f"toward the {d}", f"towards your {d}", f"the {d} side", f"over {d}", f"{d} side"]
                for d in ("left", "right")}
_EN_LOOK_WAY["up"] = ["up", "upward", "upwards", "up high", "up at the ceiling", "at the ceiling", "at the sky",
                      "up there", "higher"]
_EN_LOOK_WAY["down"] = ["down", "downward", "downwards", "down low", "at the floor", "at the ground", "at your feet",
                        "down at the floor", "lower"]
_EN_LOOK = [f"{v} {w}" for v in _EN_LOOK_VERB for ws in _EN_LOOK_WAY.values() for w in ws
            if not (v == "check" and w in ("up", "down", "higher", "lower"))]
_EN_LOOK += [f"{s} the {d} side" for s in ("see", "check out", "watch", "scan", "eye") for d in ("left", "right")]
_EN_LOOK += [f"{v} {w}" for v in ("look", "glance", "turn your head", "face", "eyes")
             for w in ("straight", "straight ahead", "ahead", "forward", "front", "to the front", "at the front",
                       "front again", "forward again", "to the center", "back to the middle", "back to center")]
_EN_LOOK += [f"{v} {w}" for v in ("look", "glance", "turn your head", "eyes", "look over")
             for w in ("at me", "this way", "over here", "my way", "toward me", "towards me", "at my face",
                       "at us", "here")]
_EN_LOOK_HAND = ["eyes on me", "eyes over here", "eyes front", "eyes up", "eyes down", "eyes left", "eyes right",
             "chin up", "chin down", "head up", "head down", "head left", "head right", "nose up", "look alive, eyes up",
             "look left a bit more", "look right a little more", "look further left", "look further right",
             "look a little higher", "look a little lower", "look up a tad", "look down a touch",
             "look 90 degrees to the left", "look 90 degrees right", "turn your head 90 degrees to the left",
             "turn your head 90 degrees right", "look left 90 degrees", "look up 90 degrees", "tilt your head up",
             "tilt your head down", "tilt up a bit", "tilt down a little", "tip your head up", "tip your head back",
             "bow your head", "nod down", "drop your head", "raise your chin", "lower your gaze", "raise your gaze",
             "lift your eyes", "lift your head up", "put your head down", "put your head up", "look lefft", "look rite",
             "look leff", "look rigt", "look dawn", "look upp", "luk left", "luk right", "luk up", "luk down",
             "look at mee", "look at mi", "lok left", "lok right", "look write side", "look left side",
             "look right side", "look up side", "look down side", "you look left", "you look right", "you look up",
             "you look down", "you look me", "robot look left", "robot look up", "look to left", "look to right",
             "look on the left", "look on the right", "look in the left", "look at left", "look at right",
             "look at up", "look at down", "look the front", "look at front", "see the front", "see left", "see right",
             "see up", "see down", "watch the left", "watch the right"]
_KO_LOOK_WAY = ["왼쪽", "오른쪽", "왼편", "오른편", "좌측", "우측", "위", "위쪽", "아래", "아래쪽", "밑", "천장", "바닥",
                "땅", "하늘", "정면", "앞", "나", "저", "날", "절", "여기", "이쪽", "레프트", "라이트"]
_KO_PART = {"나": ["", "를", "좀"], "저": ["", "를", "좀"], "날": [""], "절": [""], "여기": ["", "좀"], "이쪽": ["", "을", "으로"]}
_KO_LOOK_VERB = ["봐", "봐 줘", "봐 봐", "봐요", "봐 주세요", "봐 줄래", "봐 줄래요", "봐 주실래요", "봐 주시겠어요",
                 "보세요", "보십시오", "보시오", "보시게", "보거라", "봐라", "보자", "볼래", "볼래요", "봐 주십시오",
                 "쳐다봐", "쳐다봐 줘", "쳐다보세요", "쳐다봐 주세요", "쳐다보십시오", "쳐다볼래", "바라봐", "바라봐 줘",
                 "바라보세요", "바라봐 주세요", "바라보십시오", "봐 보이소", "보이소", "봐 주라", "봐 줘요", "봐줘",
                 "봐주세요", "쳐다봐줘", "보셈", "봐바", "바바", "봐 주면 좋겠어", "봐 주시면 좋겠어요", "봐 주시기 바랍니다",
                 "look", "look 해", "look 해 줘", "좀 봐", "좀 봐 줘", "좀 봐 주세요", "한번 봐", "한번 봐 줘", "한번 보세요"]
_KO_LOOK = []
for _w in _KO_LOOK_WAY:
    _side = _w[-1] in "쪽편측"
    for _p in _KO_PART.get(_w, ["", "을" if _w[-1] in "쪽편측면앞밑땅장닥늘" else "를"] + ([] if _side else ["쪽", "쪽을"]) +
                           ["으로" if _w[-1] in "쪽편측면앞밑땅장닥늘" else "로"]):
        for _v in _KO_LOOK_VERB:
            _KO_LOOK.append(f"{_w}{_p} {_v}")
_KO_LOOK += [f"{h} {w}" for h in ("고개", "고개를", "고개 좀", "머리", "머리를", "얼굴", "얼굴을", "시선", "시선을", "눈")
             for w in ("왼쪽으로 돌려", "오른쪽으로 돌려", "왼쪽으로 돌려 줘", "오른쪽으로 돌려 주세요", "들어", "들어 줘", "들어 봐",
                       "들어 주세요", "드세요", "드십시오", "숙여", "숙여 줘", "숙여 봐", "숙여 주세요", "숙이세요", "숙이십시오",
                       "올려", "올려 줘", "올려 주세요", "내려", "내려 줘", "내려 주세요", "위로", "아래로", "위로 들어",
                       "아래로 내려", "정면으로", "정면으로 돌려", "앞으로 돌려 줘", "원위치", "원위치 해 줘", "원래대로 해 줘",
                       "똑바로 해", "똑바로 해 주세요", "왼쪽으로 돌려 주십시오", "오른쪽으로 돌려 봐", "up", "down", "left",
                       "right", "up 해 줘", "down 해 줘", "좌측으로 돌려", "우측으로 돌려")]
_KO_LOOK += [f"{w} {v}" for w in ("왼쪽 좀", "오른쪽 좀", "위쪽 좀", "아래쪽 좀", "왼쪽으로 좀", "오른쪽으로 좀", "왼쪽 더",
                                  "오른쪽 더", "위 더", "아래 더", "좀 더 왼쪽", "좀 더 오른쪽", "조금 더 위", "조금 더 아래",
                                  "살짝 왼쪽", "살짝 오른쪽", "살짝 위", "살짝 아래", "왼쪽으로 90 degrees", "오른쪽으로 90 degrees",
                                  "위로 90 degrees", "아래로 90 degrees")
             for v in ("봐", "봐 줘", "봐 주세요", "쳐다봐", "보세요", "보십시오")]
_KO_LOOK += [f"{a} {b}" for a in ("시선", "시선 좀", "눈", "눈길", "고개") for b in ("돌려", "돌려 줘", "돌려 주세요", "딴 데로 돌려",
                                                                                  "다른 데로 돌려 줘", "피해 줘")] + \
    [f"{a} {b}" for a in ("딴 데", "다른 데", "딴 곳", "다른 곳", "다른 쪽", "딴 데를", "다른 곳을") for b in ("봐", "봐 줘", "봐 주세요", "보세요", "쳐다봐")]
_MIX_LOOK = [f"{a} {b}" for a in ("left", "right", "up", "down", "front", "왼쪽", "오른쪽", "위", "아래", "정면", "나", "여기")
             for b in ("봐", "봐 줘", "봐 주세요", "look", "look 해", "look 해 줘", "쳐다봐", "보세요", "좀 봐", "look please")] + \
    [f"look {a}" for a in ("왼쪽", "오른쪽", "위", "아래", "정면", "나", "여기", "위로", "아래로", "왼쪽으로", "오른쪽으로")] + \
    [f"고개 {a}" for a in ("left", "right", "up", "down", "left 해 줘", "right 해 줘", "up 해", "down 해", "turn 해 줘")] + \
    ["eyes 여기", "eyes on 나", "head up 해 줘", "head down 해 줘", "레프트 봐", "라이트 봐", "레프트 쪽 봐", "라이트 쪽 봐 줘",
     "업 봐", "다운 봐", "룩 레프트", "룩 라이트", "룩 업", "룩 다운", "룩 앳 미", "look at 나", "look at 저", "나 좀 look"]

# ---------------- lift: Lumi's own height ----------------
_EN_LIFT = _x(["raise yourself", "lift yourself", "raise yourself up", "lift yourself up", "raise your body",
               "lift your body", "raise your torso", "lift your torso", "get taller", "grow taller", "make yourself taller",
               "stand taller", "stretch up", "go up", "move up", "rise up", "come up", "get higher", "go higher",
               "raise your height", "increase your height", "make you taller", "lift up", "elevate yourself",
               "lower yourself", "lower yourself down", "lower your body", "lower your torso", "get shorter",
               "get smaller", "make yourself shorter", "make yourself smaller", "shrink", "shrink down", "go down",
               "move down", "come down", "sink down", "get lower", "go lower", "lower your height",
               "decrease your height", "make you shorter", "lift down", "squat down", "crouch down", "drop down"],
              ["", "a bit", "a little", "a little bit", "slightly", "1 meter", "by 1 meter", "some more", "a tad",
               "all the way", "a notch"])
_KO_LIFT = _x(["", "좀", "조금", "살짝", "1 meter", "1 meter만", "조금만", "좀 더", "더", "약간", "끝까지"],
              ["키", "키를", "몸", "몸을", "높이", "높이를", "리프트", "리프트를", "상체", "상체를", "몸통", "몸통을", "키 좀",
               "몸 좀", "자세", "자세를"],
              ["올려", "올려 줘", "올려 주세요", "올려 줄래", "올려 주실래요", "올리세요", "올리십시오", "올려 주십시오",
               "높여", "높여 줘", "높여 주세요", "높이세요", "높여 주십시오", "키워", "키워 줘", "키워 주세요",
               "내려", "내려 줘", "내려 주세요", "내리세요", "내려 주십시오", "낮춰", "낮춰 줘", "낮춰 주세요",
               "낮추세요", "낮춰 주십시오", "낮추십시오", "줄여", "줄여 줘", "줄여 주세요", "up", "down", "up 해 줘",
               "down 해 줘", "업", "다운", "올려 보이소", "내려 보이소", "낮춰 봐", "높여 봐"])
_KO_LIFT += _x(["", "좀", "조금", "살짝", "더", "좀 더", "조금만"],
               ["커져", "커져 봐", "커져 줘", "커지세요", "커져 주세요", "커지십시오", "작아져", "작아져 봐", "작아져 줘",
                "작아지세요", "작아져 주세요", "작아지십시오", "높아져", "높아져 봐", "낮아져", "낮아져 봐", "낮아져 주세요",
                "위로 올라가", "위로 올라가 줘", "위로 올라가 주세요", "아래로 내려가", "아래로 내려가 줘", "아래로 내려가 주세요",
                "올라가 봐", "내려가 봐", "몸 위로", "몸 아래로", "키 크게", "키 작게", "키 높게", "키 낮게", "쭉 올라가",
                "쭉 내려가"])
_MIX_LIFT = [f"{a} {b}" for a in ("body", "lift", "height", "키", "몸", "리프트", "몸을", "키를")
             for b in ("up", "down", "올려", "내려", "up 해 줘", "down 해 줘", "올려 줘", "내려 줘", "높여", "낮춰",
                       "좀 up", "좀 down", "up please", "down please")] + \
    ["you make body high", "you make body low", "you body up", "you body down", "body go up", "body go down",
     "make tall", "make short", "you be tall", "you be short", "taller 해 줘", "shorter 해 줘", "키 taller",
     "lift up 해 줘", "lift down 해 줘", "리프트 업", "리프트 다운", "몸 업", "몸 다운", "키 업", "키 다운"]

# ---------------- turn: the base on the spot ----------------
_EN_TURN = _x(["turn", "rotate", "spin", "pivot", "swivel", "turn yourself", "turn your body", "rotate yourself",
               "rotate your body", "spin yourself", "make a turn", "do a turn", "swing", "turn your whole body"],
              ["left", "right", "to the left", "to the right", "to your left", "to your right", "leftward",
               "rightward", "towards the left", "towards the right"],
              ["", "90 degrees", "by 90 degrees", "a bit", "a little"])
_EN_TURN += _x(["turn", "rotate", "spin", "pivot", "turn yourself", "rotate yourself"],
               ["90 degrees left", "90 degrees right", "90 degrees to the left", "90 degrees to the right",
                "90 degrees to your left", "90 degrees to your right", "left 90 degrees", "right 90 degrees"])
_EN_TURN_HAND = ["turn around", "turn yourself around", "turn back around", "spin around", "spin round", "about face",
             "do an about face", "do a u-turn", "make a u-turn", "u-turn", "face the other way", "face the opposite way",
             "turn the other way", "turn to face the other way", "turn your back", "rotate 90 degrees", "spin 90 degrees",
             "do a 180", "do a ninety to the left", "do a ninety to the right", "hang a left", "hang a right",
             "take a left", "take a right", "make a left", "make a right", "left turn", "right turn", "turn lef",
             "turn rite", "tern left", "tern right", "trun left", "trun right", "you turn left", "you turn right",
             "robot turn left", "body turn left", "body turn right", "spin all the way around", "do a full circle",
             "do a full spin", "spin a full circle", "turn all the way around", "do a 360", "turn 360 degrees",
             "face left", "face right", "face to the left", "face to the right", "face your left", "face your right",
             "face left, robot", "face right please", "turn and face left", "turn and face right",
             "turn your body to face right", "turn to face the left"]
_KO_TURN = _x(["왼쪽으로", "오른쪽으로", "좌측으로", "우측으로", "왼편으로", "오른편으로", "왼쪽으로 90 degrees",
               "오른쪽으로 90 degrees", "왼쪽으로 좀", "오른쪽으로 좀", "왼쪽으로 살짝", "오른쪽으로 살짝", "왼쪽", "오른쪽",
               "90 degrees 왼쪽으로", "90 degrees 오른쪽으로"],
              ["돌아", "돌아 줘", "돌아 봐", "돌아요", "돌아 주세요", "돌아 줄래", "돌아 주실래요", "도세요", "도십시오",
               "돌아 주십시오", "회전해", "회전해 줘", "회전해 주세요", "회전하세요", "회전하십시오", "회전", "몸 돌려",
               "몸 돌려 줘", "몸을 돌려 주세요", "몸을 돌리십시오", "방향 바꿔", "방향 바꿔 줘", "방향을 바꿔 주세요",
               "방향 바꾸세요", "방향 틀어", "방향 틀어 줘", "틀어", "틀어 줘", "꺾어", "꺾어 줘", "돌아 보이소", "돌아라",
               "돌아서", "돌아서 줘", "turn", "turn 해", "turn 해 줘", "턴", "턴 해 줘", "돌아조", "도라"])
_KO_TURN += ["뒤로 돌아", "뒤로 돌아 줘", "뒤로 돌아 주세요", "뒤로 도세요", "뒤로 도십시오", "뒤돌아", "뒤돌아 줘",
             "뒤돌아 주세요", "뒤돌아서", "돌아서", "돌아서 주세요", "반대로 돌아", "반대쪽으로 돌아", "반대 방향으로 돌아 줘",
             "반대쪽으로 방향 바꿔", "유턴", "유턴해", "유턴 해 줘", "유턴하세요", "한 바퀴 돌아", "한 바퀴 돌아 줘",
             "한 바퀴 돌아 주세요", "제자리에서 한 바퀴 돌아", "빙글 돌아", "한 바퀴 빙 돌아", "좌회전", "우회전", "좌회전해",
             "우회전해", "좌회전 해 주세요", "우회전 해 주세요", "턴 레프트", "턴 라이트", "레프트로 돌아", "라이트로 돌아",
             "left로 돌아", "right로 돌아", "left 턴", "right 턴", "turn left 해 줘", "turn right 해 줘"]

# ---------------- move: a short straight drive ----------------
_EN_MOVE = _x(["move", "go", "drive", "roll", "step", "scoot", "shift", "slide", "inch", "get", "come", "head"],
              ["forward", "forwards", "ahead", "back", "backward", "backwards", "to the left", "to the right",
               "to your left", "to your right", "left", "right", "straight ahead"],
              ["", "a bit", "a little", "a little bit", "1 meter", "by 1 meter", "a few steps", "one step", "two steps",
               "a tiny bit", "slightly"])
_EN_MOVE = [t for t in _EN_MOVE if t not in ("go ahead", "go straight ahead", "head forward") and not t.startswith(("come left", "come right", "come to the", "come to your", "head left",
                                                     "head right", "get left", "get right", "head back", "get back",
                                                     "go back", "come back", "head to the", "head to your"))]
_EN_MOVE += _x(["move", "go", "drive", "roll"], ["1 meter forward", "1 meter back", "1 meter backward",
                                                 "1 meter to the left", "1 meter to the right", "1 meter ahead",
                                                 "1 meter left", "1 meter right"])
_EN_MOVE_HAND = ["back up", "back up a bit", "back up a little", "back up 1 meter", "back off a bit", "reverse a bit",
             "reverse 1 meter", "step back a little", "take a step back", "take a step forward", "take two steps back",
             "take one step to the left", "take one step to the right", "scooch over to the left", "scooch to the right",
             "move over to the left a bit", "move over to the right a bit", "give me some room, back up",
             "make some room, move back", "you move forward", "you go back 1 meter", "you move left", "robot go forward",
             "go straight a bit", "go straight 1 meter", "move straight ahead 1 meter", "move fwd", "move forword",
             "moov back", "bak up", "go bakwards", "mov left", "mov right"]
_KO_MOVE = _x(["앞으로", "뒤로", "왼쪽으로", "오른쪽으로", "좌측으로", "우측으로", "앞쪽으로", "뒤쪽으로"],
              ["", "좀", "조금", "조금만", "살짝", "1 meter", "1 meter만", "한 걸음", "두 걸음", "반 걸음", "한 발짝",
               "약간", "쪼끔"],
              ["가", "가 줘", "가 봐", "가요", "가 주세요", "가세요", "가십시오", "가 주십시오", "가 줄래", "가 주실래요",
               "이동해", "이동해 줘", "이동해 주세요", "이동하세요", "이동하십시오", "이동해 주십시오", "움직여",
               "움직여 줘", "움직여 주세요", "움직이세요", "와", "와 줘", "와 주세요", "가라", "가 보이소", "가이소",
               "go", "go 해", "move", "move 해 줘", "가조", "가 쥬"])
_KO_MOVE += _x(["뒤로", "좀", "조금", "뒤로 좀", "뒤로 조금", "뒤로 1 meter"],
               ["물러나", "물러나 줘", "물러나 주세요", "물러서", "물러서 주세요", "물러나십시오", "빠져", "빠져 줘",
                "빠져 주세요", "후진해", "후진해 줘", "후진해 주세요", "후진하십시오", "비켜", "비켜 줘", "비켜 주세요"])
_KO_MOVE += _x(["왼쪽으로", "오른쪽으로", "옆으로"], ["비켜", "비켜 줘", "비켜 주세요", "비키세요", "비켜 주십시오"])
_KO_MOVE = [t for t in _KO_MOVE if not t.startswith("옆으로")]
_MIX_MOVE = [f"{a} {b}" for a in ("forward로", "back으로", "left로", "right로", "forward", "back", "앞으로", "뒤로",
                                  "왼쪽으로", "오른쪽으로")
             for b in ("가", "가 줘", "이동", "이동해 줘", "move", "move 해", "go", "go 해 줘", "1 meter 가", "좀 가")] + \
    ["back 해", "back 해 줘", "back up 해 줘", "후진 please", "앞으로 move please", "move forward 해 줘",
     "move back 해 줘", "move left 해 줘", "move right 해 줘", "포워드", "포워드로 가", "백으로 가", "백 해 줘"]

# ---------------- go_to: a marker on the map ----------------
_EN_GO = _x(["go", "head", "drive", "move", "walk", "roll", "get", "make your way", "proceed", "travel", "hurry",
             "navigate", "go on over", "head on over", "get yourself", "take yourself", "run", "go straight", "zip"],
            ["to <place>", "over to <place>", "on to <place>", "to <place> now", "to <place> right now",
             "to <place> please", "to <place> for me", "to <place> real quick", "back to <place>"])
_EN_GO += _x(["<place>"], ["please", "now", "go", "go now", "let's go", "lumi", "right now", "next", "is where you go",
                           "is your next stop", "go there", "head there", "move there"])
_EN_GO_HAND = ["to <place> please", "to <place>, now", "off to <place>", "off you go to <place>", "next stop, <place>",
           "your next stop is <place>", "can you get to <place>", "could you head to <place>", "would you go to <place>",
           "please head to <place> now", "i need you at <place> now", "go to <place>. right now, not later",
           "go to <place>, right now", "go to <place> immediately", "go to <place> asap", "go to <place> quick",
           "go to <place>, yes, now", "go to the <place>", "go to <place> point", "go to point <place>",
           "go to marker <place>", "drive to the <place> marker", "you go <place>", "you go to <place>",
           "robot go <place>", "go <place> please", "go too <place>", "go two <place>", "goto <place>",
           "go to da <place>", "go <place> now", "move to <place> spot", "please you go <place>", "you <place> go",
           "<place> go please", "<place> you go", "go stand at <place>", "go wait at <place>", "go and stay at <place>",
           "go to <place> and wait there", "can you take me to <place>", "show me the way to <place>",
           "guide me to <place>", "lead me to <place>", "lead the way to <place>", "take me to <place> please"]
_KO_GO = _x(["<place>로", "<place>으로", "<place>에", "<place>까지", "<place> 쪽으로", "<place> 앞으로", "<place>",
             "<place>로 좀", "<place>까지 좀", "<place>로 얼른", "<place>로 빨리", "<place>로 지금", "<place>로 당장"],
            ["가", "가 줘", "가 봐", "가요", "가 주세요", "가세요", "가십시오", "가 주십시오", "가 줄래", "가 줄래요",
             "가 주실래요", "가 주시겠어요", "가 주시겠습니까", "가 줄 수 있어", "가 줄 수 있어요", "가 주실 수 있나요",
             "이동해", "이동해 줘", "이동해 주세요", "이동하세요", "이동하십시오", "이동해 주십시오", "이동", "이동 부탁해",
             "이동 부탁드려요", "이동 부탁드립니다", "가 주라", "가라", "가거라", "가자", "갑시다", "가시죠", "가 보이소",
             "가이소", "가 보소", "가 보랑께", "가 봐라", "가 주면 좋겠어", "가 주시면 좋겠어요", "가 주시면 감사하겠습니다",
             "가 줬으면 좋겠어", "출발", "출발해", "출발해 줘", "출발하세요", "출발하십시오", "go", "go 해", "go 해 줘",
             "move", "move 해 줘", "고", "고고", "가조", "가 쥬", "가셈", "가 줘요", "가 주쇼", "가 주이소"])
_KO_GO = [t for t in _KO_GO if not (t.startswith("<place> ") and t.split(" ", 1)[1] in ("고", "move"))]
_KO_GO += ["<place>로 안내해 줘", "<place>로 안내해 주세요", "<place>까지 안내해 주십시오", "<place>로 데려다 줘",
           "<place>로 나 데려다 줘", "<place>로 저 데려다 주세요", "<place>로 가자고", "<place>로 가라고", "<place> 가야 돼",
           "<place>로 가야 해", "<place>로 가야 돼요", "<place>로 가 볼까", "<place>로 가 볼래", "<place> 쪽으로 가 볼래요",
           "지금 <place>로 가", "당장 <place>로 가", "얼른 <place>로 가 줘", "빨리 <place>로 이동해", "루미 <place>로 가",
           "<place>로 이동 바랍니다", "<place>로 가 주시기 바랍니다", "<place>로 가 주셨으면 해요", "<place>까지 가 볼래",
           "<place>로 가 주라 마", "<place>로 퍼뜩 가", "<place>로 언능 가", "<place>로 싸게 가", "<place>로 가랑께"]

# ---------------- come / follow / come_back ----------------
_EN_COME = _en(["come here", "come over here", "come to me", "come closer", "come over", "come this way",
                "get over here", "come on over", "come on over here", "come near me", "come up to me", "come by me",
                "come towards me", "approach me", "move closer to me", "roll over here", "drive over to me",
                "come to where i am", "come to my side", "come stand by me", "come a bit closer", "come right here",
                "come to me now", "over here", "come over to me", "come here to me", "come here quickly"], 0.35)
_KO_COME = _x(["이리", "이리로", "일로", "일루", "여기로", "여기", "이쪽으로", "나한테", "저한테", "제게", "내 쪽으로",
               "제 쪽으로", "내 옆으로", "제 옆으로", "가까이", "좀 더 가까이", "이리 좀", "여기로 좀", "이쪽으로 좀",
               "가까이 좀", "여기까지"],
              ["와", "와 줘", "와 봐", "와요", "와 주세요", "오세요", "오십시오", "와 주십시오", "와 줄래", "와 줄래요",
               "와 주실래요", "와 주시겠어요", "와라", "오너라", "와 보이소", "오이소", "온나", "와 주라", "와 봐요",
               "와 줘요", "오셈", "와조", "come", "come 해", "와 please"])
_EN_FOLLOW = _en(["follow me", "come with me", "come along with me", "walk with me", "tag along", "tag along with me",
                  "stay with me", "keep up with me", "stick with me", "stay behind me", "walk behind me",
                  "follow behind me", "follow my lead", "keep following me", "follow me around", "go where i go",
                  "come after me", "follow us", "come with us", "walk alongside me", "stay close to me",
                  "keep close behind me", "shadow me", "follow along", "follow me this way", "follow me over there",
                  "accompany me", "escort me"], 0.4)
_KO_FOLLOW = _x(["", "나", "날", "나를", "저", "저를", "절", "우리", "뒤에서", "천천히", "잘", "계속", "얼른", "나 좀",
                 "저 좀", "제 뒤를"],
                ["따라와", "따라와 줘", "따라와 봐", "따라와요", "따라와 주세요", "따라오세요", "따라오십시오",
                 "따라와 주십시오", "따라올래", "따라올래요", "따라와 주실래요", "따라와 주시겠어요", "따라와라",
                 "따라오너라", "따라온나", "따라오이소", "따라오소", "따라와 보이소", "따라다녀", "따라다녀 줘",
                 "따라다니세요", "쫓아와", "쫓아와 줘", "follow 해", "follow 해 줘", "팔로우 해", "팔로우 해 줘",
                 "따라와조", "따라 와", "따라 오세요"])
_KO_FOLLOW += _x(["", "나랑", "저랑", "저와", "나하고", "우리"],
                 ["같이 가자", "같이 가", "같이 가요", "같이 가 줘", "같이 가 주세요", "같이 가시죠", "같이 걸어",
                  "같이 걸어요", "같이 걸어가자", "함께 가자", "함께 가요", "함께 가시죠", "함께 걸어요"])
_EN_BACK = _en(["come back", "come back to your spot", "go back to where you were", "go back to your spot",
                "return to your spot", "return to where you were", "return to your starting point",
                "go back to the start", "go back to where you started", "head back to where you were",
                "back to where you were", "back to your spot", "go back where you came from", "return to your place",
                "get back to your spot", "go back to your old spot", "come back to where you started"], 0.4)
_KO_BACK = _x(["", "다시", "원래 자리로", "제자리로", "아까 그 자리로", "아까 있던 데로", "처음 자리로", "원래 있던 곳으로",
               "원래 위치로", "출발한 곳으로", "있던 자리로"],
              ["돌아와", "돌아와 줘", "돌아와 봐", "돌아와요", "돌아와 주세요", "돌아오세요", "돌아오십시오",
               "돌아와 주십시오", "돌아가", "돌아가 줘", "돌아가 주세요", "돌아가세요", "돌아가십시오", "복귀해",
               "복귀해 주세요", "복귀하십시오", "돌아온나", "돌아오이소", "come back 해 줘", "도라와"])
_KO_BACK = [t for t in _KO_BACK if not (t.startswith("다시 돌아가") or t in ("돌아가", "돌아가 줘", "돌아가 주세요",
                                                                             "돌아가세요", "돌아가십시오"))]

# ---------------- no: sounds like a motion, asks for none ----------------
_NO = [
    # looks / seeing / talk about looks
    "you look tired", "you look great today", "you look cute", "you look happy", "looks good to me", "that looks nice",
    "the booth on the left looks nice", "it looks like rain", "look who's here", "look, it's not a big deal",
    "look, i'm just saying hi", "i'm looking forward to the talk", "i looked everywhere", "i'll look it up later",
    "look it up later", "look before you leap", "look both ways before crossing", "he looks down on robots",
    "she turned her head left", "my mom is on the left", "the restroom is on the right", "the exit is up ahead",
    "what's on your left?", "what's on your right?", "can you see what's on your right?", "what do you see on the left?",
    "what's above you?", "what's behind you?", "where are you looking?", "why are you looking at me?",
    "did you just look at me?", "how far can your head turn?", "can your head turn all the way around?",
    "can you turn your head?", "how high can you go?", "how tall are you?", "how tall can you get?",
    "how far can you drive?", "how fast can you move?", "can you move?", "do you have wheels?", "can you walk?",
    "왼쪽에 뭐 있어?", "오른쪽에 뭐가 보여?", "오른쪽에 뭐 있는지 보여?", "위에 뭐 있어?", "뒤에 뭐 있어?", "뭐 보고 있어?",
    "어디 보고 있어?", "왜 나 쳐다봐?", "고개 몇 도까지 돌아가?", "고개 얼마나 돌아가?", "키가 몇이야?", "키 커 보인다",
    "너 키 크다", "몸 괜찮아?", "높이가 얼마야?", "얼마나 빨리 움직여?", "바퀴 있어?", "걸을 수 있어?", "오늘 멋져 보여",
    "피곤해 보여", "이 부스 괜찮아 보이네", "화장실은 오른쪽에 있어요", "출구는 왼쪽이에요", "엄마 이거 봐", "여기 봐 봐 엄마",
    # someone else, later, past, quoting
    "kids, look at the robot", "mina, look up, there's a balloon", "he said look left and you'll see the booth",
    "so when i say now, look left", "look left later, when the guests arrive", "after the speech, look at the audience",
    "i turned left at the corner", "turn left at the corner to find the restroom", "go straight and turn right for the exit",
    "we went back home", "back in my day", "i'll be back", "i'm going to the stage later", "i'll go to the booth later",
    "where is the stage?", "is the stage far?", "how do i get to the stage?", "which way is the exit?",
    "저 왼쪽으로 갈게요", "제가 뒤로 좀 갈게요", "제가 거기로 갈게요", "음, 저 포토 존으로 갈게요", "우리 이제 집에 가자",
    "나 먼저 갈게", "이따가 갈게", "다음에 또 올게", "화장실 어디예요?", "무대는 어디야?", "출구까지 멀어?",
    "어떻게 가요?", "모퉁이에서 왼쪽으로 도세요", "직진하다가 오른쪽으로 꺾으면 돼요", "엘리베이터 타고 올라가세요",
    # other senses of the verbs
    "take the lift to the second floor", "where's the lift?", "lift는 어디 있어요?", "엘리베이터 어디야?",
    "turn the music up", "turn up the volume", "turn down the music", "turn it down", "turn off the light",
    "follow the signs", "follow up later", "i follow you on instagram", "follow us on instagram",
    "come on!", "come on, really?", "oh come on", "come back later", "come again?", "how come?",
    "move on to the next topic", "let's move on", "i'm moving to busan next month", "that movie moved me",
    "go ahead and tell me", "go on, tell me more", "how's it going?", "what's going on?", "the show must go on",
    "stand up for yourself", "cheer up", "hurry up and answer", "turn the page", "it's your turn", "whose turn is it?",
    "go around", "go around it", "go round", "walk around", "look around", "go around the booth", "돌아다녀", "둘러봐",
    "go ahead", "go ahead, tell me", "go ahead and ask", "go ahead, i'm listening", "go on then",
    "음악 좀 올려 줘", "볼륨 올려", "소리 키워", "소리 좀 줄여", "목소리 키워 줘", "불 꺼 줘", "인스타 팔로우 해 주세요",
    "다음 주제로 넘어가자", "부산으로 이사 가요", "이야기 계속해", "잘 지내?", "무슨 일이야?", "네 차례야",
    # ability and conditions
    "can you look up?", "are you able to look up at the ceiling?", "is it possible for you to turn around?",
    "do you know how to follow people?", "can you follow people?", "can you come to me if i call?",
    "if i call you, come here", "when i wave, come to me", "when the show starts, go to the stage",
    "after lunch go to the booth", "if someone comes, look at them", "고개 돌릴 수 있어?", "따라올 수 있어?",
    "부르면 와 줄 수 있어?", "나중에 무대로 가", "이따가 나 봐", "신호 주면 위 봐", "근데 나중에 왼쪽 봐",
    "쇼 시작하면 무대로 가", "밥 먹고 나서 부스로 가",
    # the person's own body, reported speech
    "can you lift me up?", "lift me up", "pick me up", "carry me", "can you carry me?", "lift my bag", "나 들어 올려 줘",
    "나 안아 줘", "나 업어 줘", "저 좀 들어 주세요", "루미가 <place>로 간대", "<place>로 간대", "<place>로 간다고 했어",
    "루미가 <place>로 간다고 했어요", "로봇이 <place>로 간대요", "lumi is going to <place>", "lumi said it's going to <place>",
    "the robot is going to <place>", "he's going to <place>", "they went to <place>",
    "로봇이 따라온대", "루미가 우리 따라온대", "루미가 돌아온대", "the robot will follow us", "lumi is coming back",
]

INTENT = {
    "look": _en(_EN_LOOK, 0.05, _EN_LOOK_HAND) + _pick(_KO_LOOK, 0.1) + _MIX_LOOK,
    "lift": _en(_EN_LIFT, 0.04) + _pick(_KO_LIFT, 0.1) + _MIX_LIFT,
    "turn": _en(_EN_TURN, 0.04, _EN_TURN_HAND) + _pick(_KO_TURN, 0.5),
    "move": _en(_EN_MOVE, 0.02, _EN_MOVE_HAND) + _pick(_KO_MOVE, 0.06) + _MIX_MOVE,
    "go_to": _en(_EN_GO, 0.06, _EN_GO_HAND) + _pick(_KO_GO, 0.15),
    "come": _EN_COME + _pick(_KO_COME, 0.3),
    "follow": _EN_FOLLOW + _pick(_KO_FOLLOW, 0.3),
    "come_back": _EN_BACK + _pick(_KO_BACK, 0.5),
    "no": _NO,
}

if __name__ == "__main__":
    for k, v in INTENT.items():
        print(f"{k:10} {len(v)}")
    print("total", sum(map(len, INTENT.values())))
