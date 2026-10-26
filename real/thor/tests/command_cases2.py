"""Second command set (2026-10-21 night): every ability in wordings the first set (tests/command_cases.py) does not
have: polite / casual / 반말 / 존댓말, indirect ("could you maybe ...", "I'd like you to ...", "~해 줄래?", "~할 수 있어?"),
negation ("don't go to the stage", "가지 마"), conditions ("when I say go ..."), corrections inside the sentence
("go to start, no, end", "컵 집어, 아니 병"), fillers, code-mixing, the conference map's marker names (start, end, init,
final, middle, table_front, booth_2, stage) and whisper's slips. Same notation as tests/command_cases.py; every case
carries the map it is said on ("markers"). The intent names start with "new:" so the report keeps both sets apart.
Forbidden motions are what "wrong" counts: any motion that is not one of the expected alternatives.
"""
import random

R = random.Random(21)
CONF = ["home", "start", "end", "init", "final", "middle", "table_front", "stage", "booth_2", "dock2"]
CASES = []


def add(intent, text, expect, state="idle", before=None):
    lang = "ko" if any("가" <= ch <= "힣" for ch in text) else "en"
    CASES.append({"intent": "new:" + intent, "text": text, "lang": lang, "state": state, "before": before,
                  "expect": expect, "markers": CONF})


def ro(word):
    """The Korean 'to' particle after a word: 스테이지로, 이닛으로, 테이블 프론트로."""
    c = word[-1]
    if not "가" <= c <= "힣":
        return word + "로"
    final = (ord(c) - 0xAC00) % 28
    return word + ("으로" if final and final != 8 else "로")


def each(intent, templates, fills, expect, state="idle", before=None):
    for tpl in templates:
        for word, val in fills:
            add(intent, tpl.format(o=word, ro=ro(word) if word else ""), expect.format(o=val), state, before)


PLACES_EN = [("the stage", "stage"), ("booth two", "booth_2"), ("table front", "table_front"), ("the start", "start"),
             ("the end", "end"), ("init", "init"), ("the final point", "final"), ("the middle", "middle")]
PLACES_KO = [("스테이지", "stage"), ("부스 투", "booth_2"), ("테이블 프론트", "table_front"), ("스타트", "start"),
             ("엔드", "end"), ("미들", "middle"), ("파이널", "final"), ("이닛", "init")]
PAIRS_EN = [("the start", "the end", "end"), ("the stage", "booth two", "booth_2"), ("the middle", "table front", "table_front"),
            ("booth two", "the stage", "stage"), ("init", "the final point", "final")]
PAIRS_KO = [("스타트", "엔드", "end"), ("스테이지", "부스 투", "booth_2"), ("미들", "테이블 프론트", "table_front"),
            ("부스 투", "스테이지", "stage"), ("이닛", "파이널", "final")]

# ---------- go to a marker ----------
each("go", ["go to {o}", "could you maybe go to {o}?", "I'd like you to go to {o}", "head over to {o}, please",
            "please make your way to {o}", "can you drive to {o}", "let's go to {o}", "navigate to {o}",
            "off you go to {o}", "proceed to {o}", "um, go to, uh, {o}", "Lumi, would you go to {o} for me?",
            "why don't you go to {o}", "I want you to go to {o} now"], PLACES_EN, "action:go_to {o} | mission")
each("go", ["{ro} 가", "{ro} 가 줘", "{ro} 가 줄래?", "{ro} 가 주실래요?", "{ro} 이동해 주세요", "{o}까지 가 줘", "{o} 가",
            "{o} 쪽으로 가 봐", "{ro} 가 주시겠어요?", "{ro} 가십시오", "{ro} 가 줄 수 있어요?", "루미야, {ro} 좀 가 줘",
            "음 {ro} 가 줘요"], PLACES_KO, "action:go_to {o} | mission")
each("go", ["go to {o} 해 줘", "{o}로 go"], [("stage", "stage"), ("booth 2", "booth_2")], "action:go_to {o} | mission | talk")
# not a drive now: negation, a question about the place, a condition for later
each("go_not", ["don't go to {o}", "please don't go to {o}", "you don't need to go to {o}", "never go to {o} alone",
                "how far is {o}?", "where is {o}?", "have you been to {o} today?", "how long does it take to go to {o}?",
                "is {o} on your map?", "when I say go, go to {o}", "after the talk ends, go to {o}",
                "I'm going to {o}", "my friend is at {o}"], PLACES_EN[:5], "talk | ask | stop | end")
each("go_not", ["{ro} 가지 마", "{ro} 가지 마세요", "{o}에는 가지 마", "{o} 어디예요?", "{o}까지 얼마나 걸려요?",
                "{o}에 가 봤어?", "제가 {o}에 갈게요", "내가 가라고 하면 {ro} 가", "제 친구가 {o}에 있어요"],
     PLACES_KO[:5], "talk | ask | stop | end")          # "제가 스테이지에 갈게요": may be a goodbye
# corrections inside the sentence: the last place said; the first one is never driven to
for a, b, v in PAIRS_EN:
    for tpl in ["go to {a}, no, {b}", "go to {a}, sorry, I mean {b}", "go to {a}, actually, {b}", "go to {a}, wait, no, {b}",
                "go to {a}. No wait, go to {b}", "go to {a}, oops, {b}", "drive to {a}, I mean {b}, please"]:
        add("correct", tpl.format(a=a, b=b), f"action:go_to {v} | mission")
for a, b, v in PAIRS_KO:
    for tpl in ["{ra} 가, 아니 {rb}", "{ra} 가, 아니 {rb} 가 줘", "{ra} 가 줘. 아 아니, {rb}", "{ra}, 아니다 {rb} 가 줘"]:
        add("correct", tpl.format(ra=ro(a), rb=ro(b)), f"action:go_to {v} | mission")
for t in ["go to the stage, never mind", "go to the stage, no, forget it", "go to booth two, actually never mind",
          "come here, never mind", "turn left, no, never mind", "pick up the cup, no, forget it",
          "스테이지로 가, 아니 됐어", "이리 와, 아니야 됐어", "왼쪽으로 돌아, 아니 됐어요", "컵 집어, 아니 취소"]:
    add("correct", t, "talk")
for t, want in [("move forward 1 meter, no, 2 meters", "action:move forward 2"),
                ("move back 50 centimeters, sorry, 30 centimeters", "action:move back 0.3"),
                ("go back 1 meter, no, forward", "action:move forward 1"),
                ("turn left, no, right", "action:turn right"), ("turn left, I mean right", "action:turn right"),
                ("turn right 45 degrees, no, 30", "action:turn right 30"),
                ("look left, no, right", "action:look right"), ("look up, sorry, down", "action:look down"),
                ("pick up the cup, no, the bottle", "action:pick bottle | mission"),
                ("grab the apple, I mean the banana", "action:pick banana | mission"),
                ("pick up the cup, no, the red one", "action:pick red cup | mission"),
                ("go to the stage, no, pick up the cup", "action:pick cup | mission"),
                ("go to the stage, no, the kitchen", "ask | talk"), ("go to the stage, no, dance", "ask | talk"),
                ("앞으로 1미터, 아니 2미터 가", "action:move forward 2"), ("뒤로 1미터, 아니 50센티만 가 줘", "action:move back 0.5"),
                ("왼쪽으로 돌아, 아니 오른쪽", "action:turn right"), ("왼쪽 봐, 아니 오른쪽", "action:look right"),
                ("컵 집어, 아니 병", "action:pick bottle | mission"), ("사과 집어 줘, 아니 바나나", "action:pick banana | mission"),
                ("go to 스테이지, 아니 부스 투", "action:go_to booth_2 | mission")]:
    add("correct", t, want)

# ---------- come, come back, follow ----------
for t in ["come here", "come over here, please", "could you come here for a sec?", "come to me", "come closer",
          "get over here", "come this way", "Lumi, I need you over here, come here", "can you come over to me?",
          "이리 와", "이리 와 줄래?", "이쪽으로 와 주세요", "가까이 와", "여기로 와 봐", "나한테 와", "저한테 와 주실래요?",
          "루미야 이리 와 줘", "come here 해 줘"]:
    add("come", t, "action:come")
for t in ["don't come here", "please don't come closer", "오지 마", "가까이 오지 마세요", "I'll come to you", "can I come closer?",
          "come here often?", "제가 갈게요"]:
    add("come_not", t, "talk | stop | action:move back | end")
for t in ["come back", "come back please", "return to where you were", "go back to your spot", "could you go back where you were?",
          "come back to where you started", "돌아와", "다시 돌아와 줘", "원래 자리로 돌아가", "아까 있던 데로 돌아가 줘",
          "제자리로 돌아와 주세요"]:
    add("come_back", t, "action:come_back | mission")
for t in ["I'll come back later", "come back tomorrow", "she will come back soon", "나중에 다시 올게요", "내일 다시 와"]:
    add("come_back_not", t, "talk | end")
for t in ["follow me", "follow me please", "can you follow me?", "come with me", "walk with me", "keep following me",
          "come along", "Lumi, follow me to the booth", "따라와", "따라와 줄래?", "나 따라와", "저 따라오세요", "같이 가자",
          "저랑 같이 가요", "follow me 해 줘"]:
    add("follow", t, "action:follow")
for t in ["don't follow me", "따라오지 마", "follow me on instagram", "did you follow what I said?", "I follow you on youtube",
          "do you follow me?", "제 말 따라와요?"]:
    add("follow_not", t, "talk | stop")
add("follow_not", "stop following me", "stop")
add("follow_not", "그만 따라와", "stop")

# ---------- short moves, turns ----------
for t, want in [("move forward 1 meter", "action:move forward 1"), ("could you go forward half a meter?", "action:move forward 0.5"),
                ("back up 30 centimeters please", "action:move back 0.3"), ("I'd like you to move back 1 meter", "action:move back 1"),
                ("scoot back a little", "action:move back"), ("move 2 meters ahead", "action:move forward 2"),
                ("go left 1 meter", "action:move left 1"), ("move to the right 50 cm", "action:move right 0.5"),
                ("앞으로 1미터 가 줘", "action:move forward 1"), ("뒤로 50센티만 가", "action:move back 0.5"),
                ("왼쪽으로 1미터 이동해 줄래요?", "action:move left 1"), ("뒤로 좀 물러나 주세요", "action:move back"),
                ("앞으로 조금만 와", "action:move forward"), ("한 걸음 앞으로", "action:move forward 0.5"),
                ("move back 20 cm, no, 10 cm", "action:move back 0.1"),
                ("move back", "action:move back"), ("move forward 4 meters", "refuse"), ("앞으로 10미터 가", "refuse"),
                ("move back twenty", "ask")]:
    add("move", t, want)
for t, want in [("turn left", "action:turn left 90"), ("turn to the right please", "action:turn right"),
                ("turn around", "action:turn around"), ("could you turn left 30 degrees?", "action:turn left 30"),
                ("turn right 45 degrees", "action:turn right 45"), ("왼쪽으로 돌아", "action:turn left 90"),
                ("오른쪽으로 돌아 줘", "action:turn right 90"), ("뒤로 돌아", "action:turn around"),
                ("왼쪽으로 45도 돌아 주세요", "action:turn left 45"), ("한 바퀴 돌아 봐", "action:turn 360"),
                ("turn left 하고", "action:turn left | talk")]:
    add("turn", t, want)
for t in ["don't turn", "돌지 마", "turn off the light", "turn up the volume", "it's your turn", "turn the page"]:
    add("turn_not", t, "talk | stop")
TURNED = ("turn left", "ACTION: turn left 90")
for t, want in [("again", "action:turn left 90"), ("한 번 더", "action:turn left 90"), ("one more time", "action:turn left 90"),
                ("a bit more", "action:turn left 15"), ("조금 더", "action:turn left 15")]:
    add("again", t, want, before=TURNED)
MOVED = ("move forward 1 meter", "ACTION: move forward 1")
for t, want in [("again", "action:move forward 1"), ("do it again", "action:move forward 1"), ("same again please", "action:move forward 1"),
                ("한 번 더", "action:move forward 1"), ("10센티 더", "action:move forward 0.1")]:
    add("again", t, want, before=MOVED)
for t in ["again", "do that again", "한 번 더 해 줘"]:
    add("again", t, "ask")                                    # nothing before it: "more of what?"

# ---------- look, lift ----------
for t, want in [("look left", "action:look left"), ("look to your right", "action:look right"), ("look up", "action:look up"),
                ("look down at the table", "action:look down"), ("look at me", "action:look me"),
                ("could you look at me please?", "action:look me"), ("look straight ahead", "action:look center"),
                ("turn your head left", "action:look left"), ("look behind you", "action:look"),
                ("왼쪽 봐", "action:look left"), ("위를 봐", "action:look up"), ("나 봐", "action:look me"),
                ("고개 숙여", "action:look down"), ("정면 봐 줘", "action:look center"), ("고개 오른쪽으로 돌려 줄래?", "action:look right"),
                ("look away", "action:look away"), ("stop staring at me", "action:look away"),
                ("look up the weather", "weather | search | talk"), ("look at that!", "talk | action:look"),
                ("I'm looking for the toilet", "talk"), ("look what I have", "talk | seeing | action:look")]:
    add("look", t, want)
for t, want in [("raise yourself", "action:lift up"), ("lift yourself up a bit", "action:lift up"),
                ("lower yourself", "action:lift down"), ("could you get a little lower?", "action:lift down | talk"),
                ("키 좀 높여 줘", "action:lift up"), ("몸 좀 낮춰", "action:lift down"), ("몸 5센티만 올려", "action:lift up"),
                ("lift the cup", "action:pick cup | mission"), ("lift my spirits", "talk")]:
    add("lift", t, want)

# ---------- wave, bye-bye ----------
for t in ["wave", "wave at them", "wave your hand", "wave hello", "give them a wave", "can you wave?", "wave to the camera",
          "say hi with your hand", "손 흔들어", "손 흔들어 줄래?", "손 인사 해 줘", "손 좀 흔들어 주세요", "애들한테 손 흔들어 줘",
          "wave 해 줘", "손 wave 해 봐"]:
    add("wave", t, "action:wave")
for t in ["do you know how to wave?", "손 흔들 줄 알아?", "I saw you wave yesterday", "the wave was nice",
          "a new wave of visitors is coming"]:
    add("wave_not", t, "talk")
for t in ["bye bye", "bye-bye!", "바이바이", "빠이빠이", "잘 가", "okay, bye!", "see you, Lumi"]:
    add("bye", t, "end")

# ---------- pick, put, give, receive, the hand ----------
for t, want in [("would you mind picking up the cup?", "action:pick cup | mission"),
                ("I'd like you to grab the bottle", "action:pick bottle | mission"),
                ("could you maybe take the apple?", "action:pick apple | mission"),
                ("pick the banana up for me, would you?", "action:pick banana | mission"),
                ("go ahead and pick up the red cup", "action:pick red cup | mission"),
                ("컵 좀 집어 줄래?", "action:pick cup | mission"), ("사과 좀 들어 줄 수 있어요?", "action:pick apple | mission"),
                ("빨간 컵 잡아 주세요", "action:pick red cup | mission"), ("병 좀 집어 줘요", "action:pick bottle | mission"),
                ("pick up the 컵", "action:pick cup | mission"), ("cup 집어", "action:pick cup | mission"),
                ("don't pick up the cup", "talk"), ("컵 집지 마", "talk"), ("can you pick up a cup?", "talk"),
                ("how do you pick up cups?", "talk"), ("I picked up a cup today", "talk")]:
    add("pick", t, want)
for t, want in [("put it down please", "place"), ("set it down", "place"), ("place it on the table", "place"),
                ("테이블에 내려놔 줘", "place"), ("여기 내려놓아 주세요", "place"), ("put it down, no, give it to me", "give"),
                ("hand it over", "give"), ("give it to me please", "give"), ("I'll take it", "give"), ("can I have it?", "give"),
                ("이리 줘", "give"), ("저 주세요", "give"), ("그거 저한테 건네 주실래요?", "give"),
                ("don't drop it", "talk"), ("떨어뜨리지 마", "talk"), ("open your hand", "refuse")]:
    add("held", t, want, state="holding")
for t, want in [("here, take this", "receive"), ("can you hold this for me?", "receive"), ("이거 받아 줄래요?", "receive"),
                ("이거 좀 들고 있어 줘", "receive"), ("I have a cup for you, take it", "receive cup"),
                ("open your hand", "action:arm open"), ("open the gripper please", "action:arm open"), ("손 펴 줘", "action:arm open"),
                ("close your fingers", "action:arm close"), ("손 오므려", "action:arm close"), ("don't open your hand", "talk"),
                ("give it to me", "empty_hand | talk"), ("put it down", "empty_hand | talk")]:
    add("hand", t, want)

# ---------- fetch, missions on this map ----------
for t in ["bring me the cup from the stage", "get the bottle from booth two", "could you fetch the apple from table front?",
          "go to the stage and bring me the apple", "스테이지에서 컵 가져와", "부스 투에서 사과 가져다 줘",
          "엔드에 있는 병 가져와 줄래?", "fetch the banana from the end for me"]:
    add("fetch", t, "action:fetch | mission | refuse")             # a bottle or banana: the reason why not
for t in ["take the cup to booth two and come back", "go to the stage, wait 10 seconds, then come back",
          "스테이지 갔다 와", "부스 투 다녀와 줄래?", "먼저 스테이지 가서 컵 가져오고 그다음 여기로 와서 줘",
          "go to start, then middle, then end", "pick up the cup, go to the end and give it to Sarah"]:
    add("mission", t, "mission | action:fetch")
for t in ["go to the stage and wave", "go to the stage and follow me", "pick up the cup and lift yourself up",
          "go to booth two and look left", "스테이지 가서 손 흔들어"]:
    add("mission_part", t, "chain")                 # each part in turn (lumi.chain_run), never half done

# ---------- stop, speed ----------
for t in ["stop", "stop it", "stop right now", "halt", "freeze", "stop, stop!", "wait, stop", "Lumi stop", "멈춰", "그만", "정지",
          "스톱", "멈춰 주세요", "거기 서", "stop 해"]:
    add("stop", t, "stop")
for t in ["how do I stop you?", "where is your stop button?", "멈추는 방법이 뭐예요?"]:
    add("stop_not", t, "talk")
add("stop_not", "bus stop", "talk | stop")                   # a stop is never a harmful motion
add("stop_not", "don't stop talking", "talk | stop")
for t, want in [("go faster", "speed faster"), ("speed up a little", "speed faster"), ("can you go quicker?", "speed faster"),
                ("slow down", "speed slower"), ("not so fast please", "speed slower"), ("더 빨리 가", "speed faster"),
                ("천천히 가 줘", "speed slower"), ("속도 좀 줄여 주세요", "speed slower"), ("you're too fast", "speed slower"),
                ("speak slower", "talk"), ("천천히 말해 줘", "talk"), ("you speak too fast", "talk")]:
    add("speed", t, want)
# ---------- every Korean speech level, slang and whisper's spellings (second round) ----------
for t, want, st in [
        ("스테이지로 가십시오", "action:go_to stage", "idle"), ("스테이지로 가시겠어요?", "action:go_to stage", "idle"),
        ("스테이지로 가 줄 수 있니?", "action:go_to stage", "idle"), ("스테이지로 좀 가 봐요", "action:go_to stage", "idle"),
        ("스테이지로 가자", "action:go_to stage", "idle"), ("스테이지로 가 볼까?", "action:go_to stage | talk", "idle"),
        ("스테이지로 가면 안 돼?", "action:go_to stage | talk", "idle"), ("스테이지로 가야 해", "action:go_to stage", "idle"),
        ("스테이지로 가 줬으면 좋겠어", "action:go_to stage", "idle"), ("스테이지 가 주라", "action:go_to stage", "idle"),
        ("스테이지로 가 주시면 감사하겠습니다", "action:go_to stage | talk | end", "idle"),
        ("이리 오세요", "action:come", "idle"), ("이리 와 주시겠어요?", "action:come", "idle"), ("이리 좀 와 볼래?", "action:come", "idle"),
        ("여기로 와 주실 수 있나요?", "action:come", "idle"), ("따라오세요", "action:follow", "idle"),
        ("따라와 주시겠어요?", "action:follow", "idle"), ("저를 따라와 주세요", "action:follow", "idle"),
        ("앞으로 오십 센티 가 주세요", "action:move forward 0.5", "idle"), ("뒤로 조금만 물러나 주실래요?", "action:move back", "idle"),
        ("왼쪽으로 돌아 주십시오", "action:turn left", "idle"), ("고개를 왼쪽으로 돌려 주세요", "action:look left", "idle"),
        ("위를 봐 주실래요?", "action:look up", "idle"), ("손을 흔들어 주시겠어요?", "action:wave", "idle"),
        ("손 좀 흔들어 줄 수 있어?", "action:wave", "idle"), ("컵을 집어 주시겠습니까?", "action:pick cup | mission", "idle"),
        ("컵 좀 집어 주실 수 있나요?", "action:pick cup | mission", "idle"), ("그 컵 좀 집어 줘 봐", "action:pick cup | mission", "idle"),
        ("멈춰 주세요", "stop", "idle"), ("그만하세요", "stop", "idle"), ("천천히 가 주세요", "speed slower", "idle"),
        ("좀 더 빨리 가 줄래요?", "speed faster", "idle"),
        ("그거 저 주세요", "give", "holding"), ("테이블에 놓아 주시겠어요?", "place", "holding"), ("저한테 주실래요?", "give", "holding"),
        ("gimme a wave", "action:wave", "idle"), ("yo come here", "action:come", "idle"), ("c'mon follow me", "action:follow", "idle"),
        ("go 2 the stage", "action:go_to stage", "idle"), ("goto the stage", "action:go_to stage", "idle"),
        ("go too the stage", "action:go_to stage", "idle"), ("go to the stag", "action:go_to stage", "idle"),
        ("go to stage pls", "action:go_to stage", "idle"), ("plz come here", "action:come", "idle"), ("come hear", "action:come", "idle"),
        ("move forward a metre and a half", "action:move forward 1.5", "idle"), ("turn lefft", "action:turn left | talk | ask", "idle"),
        ("look write", "action:look right | talk | ask", "idle"), ("lemme see you wave", "action:wave | talk | end", "idle")]:
    add("levels", t, want, st)
for t, want in [("go ahead to the stage", "action:go_to stage"), ("you may go to booth two", "action:go_to booth_2"),
                ("feel free to go to the stage", "action:go_to stage"), ("time to go to the stage", "action:go_to stage"),
                ("I was wondering if you could go to the stage", "action:go_to stage"),
                ("would it be possible for you to go to the stage?", "action:go_to stage | talk"),
                ("is it okay if you go to the stage?", "action:go_to stage | talk"), ("mind going to the stage?", "action:go_to stage | talk"),
                ("stop and come back", "stop"), ("wait, don't go there", "talk | stop"), ("no no no, stop", "stop"),
                ("스테이지 가서 거기서 기다려", "mission"), ("거기 서!", "stop"), ("거기 서", "stop"),
                ("look at the stage", "talk | ask | action:look"), ("face the stage", "talk | ask | action:look | action:turn")]:
    add("levels", t, want)
# "can you ...?" asks it done (owner, 2026-10-20); "do you know how / can you X people" asks whether it can
for t, want in [("can you raise yourself?", "action:lift up"), ("could you get a bit taller", "action:lift up"),
                ("can you look to the left?", "action:look left"), ("could you turn around please", "action:turn around"),
                ("can you move back a little?", "action:move back"), ("can you stop?", "stop"), ("멈출 수 있어?", "stop"),
                ("Lumi, could you stop please?", "stop"), ("can you close your hand?", "action:arm close"),
                ("왼쪽으로 돌아 줄 수 있어요?", "action:turn left"), ("이리 와 줄 수 있어요?", "action:come"),
                ("turn left, would you?", "action:turn left"), ("turn around for me, will you?", "action:turn around"),
                ("do you know how to follow people?", "talk"), ("can you follow people?", "talk | action:follow"),
                ("do you turn left?", "talk"), ("can you stop talking?", "talk | action:quiet"),
                ("can you pick that up?", "talk | ask"), ("how about turning left", "talk | action:turn left"),
                ("would you mind looking at me?", "talk | action:look me")]:
    add("levels", t, want)
# ---------- leftovers of the second night (2026-10-22) ----------
for t in ["look at me and wave", "look at me, then wave", "wave and look at me", "lift yourself up and wave",
          "웨이브 하고 나 봐", "나 보고 손 흔들어", "손 흔들고 나 봐 줘", "키 높이고 손 흔들어", "look at me and 손 흔들어",
          "Lumi, look at me and wave please"]:
    add("mission_part", t, "chain")                 # two commands: both, in the order said
for t in ["put it down and wave", "내려놓고 손 흔들어", "give it to me and wave"]:
    add("mission_part", t, "chain", state="holding")
# a sentence of commands, questions and talk: each part in the order said (owner, 2026-10-22)
for t in ["go to the stage and tell me the weather", "go to booth two and tell me what time it is",
          "look at me and tell me a joke", "wave and then tell me your name", "고개 들고 몇 시야?",
          "스테이지 가서 날씨 알려 줘", "나 보고 오늘 날씨 어때?", "look up and what time is it?",
          "turn left and wave", "왼쪽으로 돌고 손 흔들어", "lift yourself up, then look at me", "come here and wave",
          "고개 들고 손 흔들어", "go to the stage and dance", "come here and tell me the time",
          "go to the stage and follow me", "wave and go to the stage"]:
    add("chain", t, "chain")
for t in ["what's the weather in Seoul and Busan?", "come here, I need help", "I like the stage and the music",
          "tell me about Cutshion and its products", "how far is the stage and how long does it take?",
          "turn around and look", "do you wave and dance?", "나 보고 싶었어", "follow me and go to the stage"]:
    add("chain_not", t, "talk | ask | action:look | action:come | action:follow | action:fetch | weather | search")
for t in ["spin around", "turn all the way around", "do a 360", "turn 360 degrees", "한 바퀴 돌아", "한 바퀴 돌아 줘",
          "제자리에서 한 바퀴 돌아 주세요", "360도 돌아", "빙글빙글 돌아", "Lumi, spin around please", "can you spin around?"]:
    add("turn", t, "action:turn 360")                # two checked half turns (tasks/fetch.py _do_step)
for t, want in [("오른쪽으로 한 바퀴 돌아", "action:turn right 360"), ("spin around to the right", "action:turn right 360"),
                ("turn around", "action:turn around 180"), ("뒤로 돌아", "action:turn around 180")]:
    add("turn", t, want)
for t in ["공원 한 바퀴 돌았어", "the earth spins around the sun", "how do you spin around?", "can I spin around?",
          "어제 한 바퀴 돌았어요"]:
    add("turn_not", t, "talk")
for t in ["take the cup and put it back", "pick up the red cup and put it back", "컵 집었다가 제자리에 놔",
          "grab the apple and put it back down"]:
    add("mission", t, "mission")                     # picked here, put back here
for t in ["루미야 너 월급 받아?", "너 월급 받아?", "월급 받아요?", "너 전화 받아?", "칭찬 많이 받아?"]:
    add("talk", t, "talk")                           # about Lumi, nothing is handed over
for t in ["컵 가져다 줘", "컵 좀 가져다 주세요", "컵 갖다 줘", "빨간 컵 가져다 줄래?"]:
    add("fetch", t, "mission | action:fetch")        # picked from the table in front, handed over
for t, want in [("Let's go P5 (point).", "action:go_to p5"), ("Let's go P9.", "action:go_to p9"),
                ("lets go p3", "action:go_to p3"), ("let's go p10 point", "action:go_to p10"),
                ("let's go eat", "talk")]:
    CASES.append({"intent": "new:go", "text": t, "lang": "en", "state": "idle", "before": None, "expect": want,
                  "markers": ["home", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]})   # the owner's map
for t in ["let's go exit point and go p9 point", "go to exit then p9", "first exit then p9", "exit 갔다가 p9로 가",
          "exit 포인트 갔다가 p9 포인트로 가", "먼저 final 가고 그다음 p2로 가", "let's go final point and go p9 point"]:
    CASES.append({"intent": "new:mission", "text": t, "lang": "ko" if any("가" <= ch <= "힣" for ch in t) else "en",
                  "state": "idle", "before": None, "expect": "mission",
                  "markers": ["home", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]})   # the owner's map
R.shuffle(CASES)                                     # the report lists them by intent; the order only spreads the LLM's load
