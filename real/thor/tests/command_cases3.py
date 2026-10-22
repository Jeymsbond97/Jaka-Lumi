"""Third command set (2026-10-21 night), written blind from docs/14 (§4, §6) and docs/17 only: single spoken commands
and near misses on the conference map, English, Korean (반말, 해요체, 하십시오체) and mixed, as people say them at a
booth: fillers, hedges ("could you maybe", "I was wondering if", "~해 줄 수 있어요?", "~해 주실래요?"), negations,
conditions and later times (no motion), corrections inside the sentence, things the body can't do, questions about
abilities, remarks that only look like commands, and whisper's slips. Same notation as tests/command_cases2.py; the
intent names start with "blind:". A question back ("ask" / "talk") is accepted wherever the words are unclear; a wrong
motion never is.
"""
CONF = ["home", "start", "end", "init", "final", "middle", "table_front", "stage", "booth_2", "dock2"]
CASES = []


def add(intent, text, expect, state="idle", before=None):   # before: (what was said, Lumi's action line)
    lang = "ko" if any("가" <= ch <= "힣" for ch in text) else "en"
    CASES.append({"intent": "blind:" + intent, "text": text, "lang": lang, "state": state, "before": before,
                  "expect": expect, "markers": CONF})


def each(intent, templates, fills, expect, state="idle", before=None):
    for tpl in templates:
        for word, val in fills:
            add(intent, tpl.format(o=word), expect.format(o=val), state, before)


GO = "action:go_to {o} | mission"
NO_MOVE = "talk | ask"
CANT = "refuse | talk"

# ---------- go to a marker: English ----------
each("go", ["I was wondering if you could go to {o}", "could you go over to {o} real quick?",
            "hey Lumi, {o}, please. Go there.", "so, uh, can you head to {o}?", "would you mind going to {o}?"],
     [("the stage", "stage"), ("booth two", "booth_2"), ("table front", "table_front"), ("the middle", "middle"),
      ("the start", "start"), ("the end point", "end"), ("init", "init"), ("final", "final")], GO)  # 40
add("go", "go home", GO.format(o="home"))
add("go", "Lumi, go back home please", GO.format(o="home"))
add("go", "go to dock two", GO.format(o="dock2"))
add("go", "go to dock 2", GO.format(o="dock2"))
add("go", "drive over to booth 2", GO.format(o="booth_2"))
add("go", "go to booth number two", GO.format(o="booth_2"))
add("go", "take yourself to the table front", GO.format(o="table_front"))
add("go", "go to the front of the table", "action:go_to table_front | mission | ask")
add("go", "go to the charger", "action:go_to dock2 | action:go_to home | ask")
add("go", "go charge yourself", "action:go_to dock2 | action:go_to home | ask | talk")
add("go", "go to the starting point", "action:go_to start | ask")
add("go", "go to the end", GO.format(o="end"))
# whisper's slips: one letter off after "to"
add("go_whisper", "go to the stagee", GO.format(o="stage"))
add("go_whisper", "go to the stag", GO.format(o="stage"))
add("go_whisper", "go to boot two", "action:go_to booth_2 | ask")
add("go_whisper", "go to booth to", "action:go_to booth_2 | ask")
add("go_whisper", "go to the midle", GO.format(o="middle"))
add("go_whisper", "go to finale", "action:go_to final | ask")
add("go_whisper", "go to in it", "action:go_to init | ask")
add("go_whisper", "go to table fronts", "action:go_to table_front | ask")
# not on this map
add("go_unknown", "go to the kitchen", "refuse | talk | ask")
add("go_unknown", "go to p3", "refuse | talk | ask")
add("go_unknown", "go to booth three", "refuse | talk | ask")
add("go_unknown", "go to the exit", "refuse | talk | ask")
add("go_unknown", "부스 쓰리로 가", "refuse | talk | ask")
add("go_unknown", "주방으로 가", "refuse | talk | ask")

# ---------- go to a marker: Korean, every speech level ----------
each("go_ko", ["{o}로 가", "{o}로 가요", "{o}로 가 주세요", "{o}로 가십시오", "{o}로 가 주실래요?",
               "{o}로 가 줄 수 있어요?", "음 {o}로 좀 가 줄래?"],
     [("스테이지", "stage"), ("부스 투", "booth_2"), ("테이블 프론트", "table_front"), ("엔드", "end")], GO)  # 28
add("go_ko", "스타트로 이동해 주십시오", GO.format(o="start"))
add("go_ko", "미들로 가 봐", GO.format(o="middle"))
add("go_ko", "파이널로 가 주세요", GO.format(o="final"))
add("go_ko", "이닛으로 가", GO.format(o="init"))
add("go_ko", "홈으로 가요", GO.format(o="home"))
add("go_ko", "집에 가", "action:go_to home | ask")
add("go_ko", "도크 투로 가 주세요", GO.format(o="dock2"))
add("go_ko", "충전하러 가", "action:go_to dock2 | action:go_to home | ask | talk")
add("go_ko", "부스 2번으로 가 줘", GO.format(o="booth_2"))

# ---------- go: mixed ----------
add("go_mixed", "stage로 가 줘", GO.format(o="stage"))
add("go_mixed", "booth two로 가 주세요", GO.format(o="booth_2"))
add("go_mixed", "table front로 이동", GO.format(o="table_front"))
add("go_mixed", "go to 스테이지", GO.format(o="stage"))
add("go_mixed", "please 엔드로 가", GO.format(o="end"))
add("go_mixed", "Lumi, middle 쪽으로 가 볼래?", GO.format(o="middle"))
add("go_mixed", "home으로 돌아가", GO.format(o="home"))

# ---------- corrections inside the sentence ----------
add("correct", "go to start, no, end", GO.format(o="end"))
add("correct", "go to the stage, sorry, I mean booth two", GO.format(o="booth_2"))
add("correct", "go to booth two, uh no wait, table front", GO.format(o="table_front"))
add("correct", "go to the middle, actually no, the final point", GO.format(o="final"))
add("correct", "스타트로 가, 아니 엔드로", GO.format(o="end"))
add("correct", "스테이지로 가요, 아 아니다, 부스 투로 가요", GO.format(o="booth_2"))
add("correct", "미들로, 아니 테이블 프론트로 가 주세요", GO.format(o="table_front"))
add("correct", "turn left, I mean right", "action:turn right 90")
add("correct", "왼쪽으로 돌아, 아니 오른쪽", "action:turn right 90")
add("correct", "move forward 1 meter, no, 2 meters", "action:move forward 2")
add("correct", "앞으로 1미터, 아니 50센티 가", "action:move forward 0.5")
add("correct", "pick up the cup, no, the apple", "action:pick apple")
add("correct", "사과 집어, 아니 오렌지", "action:pick orange")
add("correct", "look left, no, right", "action:look right")
add("correct_back", "go to the stage, never mind", NO_MOVE)
add("correct_back", "스테이지로 가, 아니 됐어", NO_MOVE)
add("correct_back", "turn around, actually forget it", NO_MOVE)
add("correct_back", "follow me, oh never mind", NO_MOVE)
add("correct_unclear", "go to the stage, no, the kitchen", NO_MOVE)
add("correct_unclear", "부스 투로 가, 아니 화장실로", NO_MOVE)
add("correct_talk", "I like apples, no, I love them", "talk")

# ---------- negations: no motion ----------
add("neg", "don't go to the stage", NO_MOVE)
add("neg", "please don't follow me", NO_MOVE)
add("neg", "don't turn around", NO_MOVE)
add("neg", "you don't need to come here", NO_MOVE)
add("neg", "don't pick up the cup", NO_MOVE)
add("neg", "no need to wave", NO_MOVE)
add("neg", "스테이지로 가지 마", NO_MOVE)
add("neg", "따라오지 마세요", NO_MOVE)
add("neg", "컵 집지 마", NO_MOVE)
add("neg", "이리 오지 마십시오", NO_MOVE)
add("neg", "don't move forward", NO_MOVE + " | stop")   # a stop is never harmful
add("neg", "손 흔들지 마", NO_MOVE)

# ---------- conditions and later times: no motion ----------
add("cond", "when I say go, go to the stage", NO_MOVE)
add("cond", "after the talk ends, go to start", NO_MOVE)
add("cond", "go there tomorrow", NO_MOVE)
add("cond", "if someone calls you, come here", NO_MOVE)
add("cond", "in an hour, go to booth two", NO_MOVE)
add("cond", "later, could you follow me around?", NO_MOVE)
add("cond", "before we close tonight go to the charger", NO_MOVE)
add("cond", "내가 가라고 하면 스테이지로 가", NO_MOVE)
add("cond", "발표 끝나면 엔드로 가 주세요", NO_MOVE)
add("cond", "내일 부스 투로 가", NO_MOVE)
add("cond", "이따가 따라와", NO_MOVE)
add("cond", "손님 오시면 손 흔들어 주세요", NO_MOVE)

# ---------- come ----------
add("come", "come here", "action:come")
add("come", "come to me please", "action:come")
add("come", "could you come over here?", "action:come")
add("come", "hey, come closer", "action:come | ask")
add("come", "come hear", "action:come")
add("come", "come back here", "action:come")
add("come", "이리 와", "action:come")
add("come", "이리 와 주세요", "action:come")
add("come", "이쪽으로 오십시오", "action:come")
add("come", "여기로 와 줄래요?", "action:come")
add("come", "이리 돌아와", "action:come")
add("come", "come here 해 줘", "action:come")
add("come_not", "can I come closer?", "talk")
add("come_not", "come on, that's so funny", "talk")
add("come_not", "my friend will come here soon", "talk")

# ---------- come back ----------
add("come_back", "come back", "action:come_back | ask")
add("come_back", "return", "action:come_back | ask")
add("come_back", "go back where you were", "action:come_back | ask")
add("come_back", "돌아와", "action:come_back | ask")
add("come_back", "원래 자리로 돌아가", "action:come_back | ask")
add("come_back", "원래 있던 데로 돌아가 주세요", "action:come_back | ask")
add("come_back", "come back to the stage", GO.format(o="stage"))
add("come_back", "스테이지로 돌아와", GO.format(o="stage"))
add("come_back", "come back 20 cm", "action:move back 0.2")
add("come_back", "go back", "action:move back 1")
add("come_back_not", "I'll come back later", "talk")
add("come_back_not", "come back tomorrow, we'll be here", "talk")
add("come_back_not", "she will come back", "talk")
add("come_back_not", "이따 다시 올게요", "talk")

# ---------- follow ----------
add("follow", "follow me", "action:follow | refuse")
add("follow", "could you maybe follow me?", "action:follow | refuse")
add("follow", "come with me", "action:follow | refuse")
add("follow", "walk with me", "action:follow | refuse")
add("follow", "follow mi", "action:follow | refuse | ask")
add("follow", "따라와", "action:follow | refuse")
add("follow", "나 따라와", "action:follow | refuse")
add("follow", "저 따라오세요", "action:follow | refuse")
add("follow", "같이 가자", "action:follow | refuse")
add("follow", "저를 따라오십시오", "action:follow | refuse")
add("follow", "follow me 해 줘", "action:follow | refuse")
add("follow_not", "follow me on Instagram", "talk")
add("follow_not", "I follow you", "talk")
add("follow_not", "did you follow me?", "talk")
add("follow_not", "제 말 따라와요?", "talk")
add("follow_not", "can you follow what I'm saying?", "talk")

# ---------- short moves ----------
add("move", "move forward one meter", "action:move forward 1")
add("move", "back up two hundred millimetres", "action:move back 0.2")
add("move", "move back 5 centimeters", "action:move back 0.05")
add("move", "go left half a meter", "action:move left 0.5")
add("move", "could you move to the right 1.5 meters?", "action:move right 1.5")
add("move", "let's bake 20 cm", "action:move back 0.2")
add("move", "big one meter", "action:move back 1 | ask")
add("move", "forward one metal", "action:move forward 1 | ask")
add("move", "20센티 뒤로", "action:move back 0.2")
add("move", "앞으로 반 미터", "action:move forward 0.5")
add("move", "이십 센티 뒤로 가", "action:move back 0.2")
add("move", "왼쪽으로 1미터 가 주세요", "action:move left 1")
add("move", "오른쪽으로 삼십 센치 이동하십시오", "action:move right 0.3")
add("move", "앞으로 일 미터 가 줄 수 있어요?", "action:move forward 1")
add("move", "move forward 1미터", "action:move forward 1")
add("move", "back up a tiny bit", "action:move back 0.05")
add("move", "inch forward", "action:move forward 0.05 | ask")
add("move", "a hair to the left", "action:move left 0.05")
add("move", "two steps back", "action:move back 1")
add("move", "go back a little", "action:move back 0.5")
add("move", "살짝 뒤로", "action:move back 0.05")
add("move", "한 뼘 앞으로", "action:move forward 0.2")
add("move", "반 걸음 뒤로 가 주세요", "action:move back 0.25 | ask")
add("move_ask", "move back 20", "ask")
add("move_ask", "move forward a couple of metres", "ask")
add("move_ask", "앞으로 조금만 더 가 볼래요 한 스무", "ask | action:move forward 0.5")
add("move_refuse", "move forward 5 meters", "refuse")
add("move_refuse", "go back one kilometer", "refuse")
add("move_refuse", "앞으로 10미터 가", "refuse")
add("move_refuse", "move left half a millimetre", "refuse")

# ---------- turns ----------
add("turn", "turn left", "action:turn left 90")
add("turn", "turn right please", "action:turn right 90")
add("turn", "turn 45 degrees to the left", "action:turn left 45")
add("turn", "can you turn right thirty degrees?", "action:turn right 30")
add("turn", "turn around", "action:turn around")
add("turn", "뒤로 돌아", "action:turn around")
add("turn", "왼쪽으로 돌아", "action:turn left 90")
add("turn", "오른쪽으로 돌아 주세요", "action:turn right 90")
add("turn", "오른쪽으로 사십오 도 도십시오", "action:turn right 45")
add("turn", "turn left 해 줘", "action:turn left 90")
add("turn", "한 바퀴 빙 돌아 봐", "action:turn 360 | ask")   # all the way round: two half turns
add("turn_not", "it's your turn to talk", "talk")
add("turn_not", "turn left at the corner and you'll find the restroom", "talk")

# ---------- look (head) ----------
add("look", "look left", "action:look left")
add("look", "look to your right", "action:look right")
add("look", "look up", "action:look up")
add("look", "could you look down a bit?", "action:look down")
add("look", "look at me", "action:look me")
add("look", "eyes on me, please", "action:look me")
add("look", "고개 들어", "action:look up")
add("look", "고개 숙여 주세요", "action:look down")
add("look", "고개 살짝 왼쪽으로", "action:look left")
add("look", "정면 봐", "action:look center | action:look me")
add("look", "저 봐 주실래요?", "action:look me")
add("look", "turn your head 30 degrees right", "action:look right | action:look right 30")
add("look", "look right 해 봐", "action:look right")
add("look_not", "what's behind you?", "seeing | talk")
add("look_not", "뒤에 뭐 있어?", "seeing | talk")
add("look_not", "look at this booth, isn't it nice?", "talk")
add("look_not", "you look great today", "talk")

# ---------- lift ----------
add("lift", "raise yourself", "action:lift up")
add("lift", "lower yourself a bit", "action:lift down")
add("lift", "could you get a little taller?", "action:lift up")
add("lift", "키 좀 높여", "action:lift up")
add("lift", "몸 5센티만 내려", "action:lift down")
add("lift", "몸 좀 낮춰 주세요", "action:lift down")
add("lift", "lift 올려 줘", "action:lift up")
add("lift_not", "can you lift a car?", "talk | refuse")

# ---------- wave ----------
add("wave", "wave", "action:wave | refuse")
add("wave", "wave your hand", "action:wave | refuse")
add("wave", "can you shake your hand?", "action:wave | refuse")
add("wave", "give us a wave!", "action:wave | refuse")
add("wave", "손 흔들어 줘", "action:wave | refuse")
add("wave", "손 인사 해 주세요", "action:wave | refuse")
add("wave", "안녕 하고 손 흔들어", "action:wave | refuse")
add("wave", "wave 해 줄래?", "action:wave | refuse")
add("wave", "wave your hand", "refuse | action:wave", state="holding")   # wave() refuses aloud
add("wave", "손 흔들어 주실래요?", "refuse | action:wave", state="holding")
add("wave_not", "I saw you wave", "talk")
add("wave_not", "the wave was nice", "talk")
add("wave_not", "아까 손 흔드는 거 귀여웠어요", "talk")
add("wave_q", "can you wave?", "action:wave | refuse | talk")

# ---------- bye-bye ----------
add("bye", "bye bye", "end | action:wave")
add("bye", "bay bay", "end | action:wave")
add("bye", "바이바이", "end | action:wave")
add("bye", "빠이빠이", "end | action:wave")
add("bye", "잘 가", "end | action:wave")
add("bye", "okay, bye", "end | action:wave")
add("bye", "안녕히 계세요", "end | action:wave")
add("bye", "bye bye", "end", state="holding")

# ---------- pick ----------
add("pick", "pick up the cup", "action:pick cup")
add("pick", "could you grab that mug for me?", "action:pick cup")
add("pick", "take the glass", "action:pick cup")
add("pick", "pick up the apple", "action:pick apple")
add("pick", "I was wondering if you could pick up the orange", "action:pick orange")
add("pick", "pick up the white cup", "action:pick cup")
add("pick", "컵 잡아", "action:pick cup")
add("pick", "사과 집어 주세요", "action:pick apple")
add("pick", "오렌지 좀 들어 줄 수 있어요?", "action:pick orange")
add("pick", "컵을 집어 주십시오", "action:pick cup")
add("pick", "cup pick up 해 줘", "action:pick cup")
add("pick", "빨간 컵 pick up", "action:pick cup")
add("pick_refuse", "pick up the bottle", "refuse | action:pick bottle | talk")
add("pick_refuse", "take the banana", "refuse | action:pick banana | talk")
add("pick_refuse", "병 집어", "refuse | action:pick bottle | talk")
add("pick_refuse", "바나나 잡아 주세요", "refuse | action:pick banana | talk")
add("pick_refuse", "pick up the laptop", "refuse | talk | ask")
add("pick_full", "pick up the cup", "refuse | talk | action:pick", state="holding")   # the task refuses a full hand
add("pick_not", "I'll pick up my cup later", "talk")
add("pick_not", "do you like apples?", "talk")
add("move_object", "move the cup", "action:move_object cup | action:pick cup | mission")

# ---------- put / place (holding) ----------
add("place", "put it down", "place", state="holding")
add("place", "put it back", "place | action:put back", state="holding")
add("place", "put it on the table", "place", state="holding")
add("place", "could you set it down over there?", "place", state="holding")
add("place", "drop it here", "place", state="holding")
add("place", "내려놔", "place", state="holding")
add("place", "제자리에 놔 주세요", "place | action:put back", state="holding")
add("place", "테이블에 놔", "place", state="holding")
add("place", "책상 위에 올려놓으십시오", "place", state="holding")
add("place", "put it on the lower one", "place | ask", state="holding")
add("place", "table 위에 put it", "place", state="holding")
add("place_empty", "put it down", "empty_hand")
add("place_empty", "테이블에 놔 주세요", "empty_hand")

# ---------- give (holding) ----------
add("give", "give it to me", "give", state="holding")
add("give", "bring it to me", "give | action:fetch", state="holding")
add("give", "pass it over", "give", state="holding")
add("give", "hand it to her", "give", state="holding")
add("give", "I'll take it", "give", state="holding")
add("give", "줘", "give", state="holding")
add("give", "이리 줘", "give", state="holding")
add("give", "저 주세요", "give", state="holding")
add("give", "저 사람한테 줘", "give", state="holding")
add("give", "give it to me 해 줘", "give", state="holding")
add("give_empty", "give it to me", "empty_hand")
add("give_empty", "이리 줘", "empty_hand")

# ---------- receive (take from the person's hand) ----------
add("receive", "take this from my hand", "receive")
add("receive", "hold this", "receive")
add("receive", "here you go", "receive | talk")
add("receive", "I'll give you this cup", "receive")
add("receive", "can you take this apple from me?", "receive")
add("receive", "이거 받아", "receive")
add("receive", "드릴게요", "receive | talk")
add("receive", "내 손에 있는 거 가져가", "receive")
add("receive", "이 컵 받아 주실래요?", "receive")
add("receive", "this 받아 줘", "receive")

# ---------- hand open / close ----------
add("hand", "open your hand", "action:arm open")
add("hand", "close your hand", "action:arm close")
add("hand", "손을 펴", "action:arm open")
add("hand", "손 좀 펴 주세요", "action:arm open")
add("hand", "손 오므려", "action:arm close | ask")
add("hand", "could you open your gripper?", "action:arm open")
add("hand", "open your hand", "refuse", state="holding")
add("hand", "손 펴", "refuse", state="holding")
add("hand", "let go", "give | place | refuse", state="holding")

# ---------- fetch ----------
add("fetch", "bring me the apple from the stage", "action:fetch | mission")
add("fetch", "could you get me a cup from booth two?", "action:fetch | mission")
add("fetch", "go get the orange from table front", "action:fetch | mission")
add("fetch", "엔드에서 컵 가져와", "action:fetch | mission")
add("fetch", "스테이지에서 사과 가져다주세요", "action:fetch | mission")
add("fetch", "부스 투에서 컵 좀 가져와 주실래요?", "action:fetch | mission")
add("fetch", "bring the cup from start to table front", "action:fetch | mission")
add("fetch", "pass me the cup", "mission | action:fetch")
add("fetch", "can I have the apple?", "mission | action:fetch")
add("fetch", "컵 좀 줘", "mission | action:fetch")
add("fetch", "bring me a bottle from the stage", "action:fetch | mission")   # bottles by their body since 2026-10-22
add("fetch_unknown", "bring me a cup from the kitchen", "refuse | talk | ask | action:fetch")   # parse_fetch asks
add("fetch_not", "I brought my own cup", "talk")

# ---------- stop ----------
add("stop", "stop", "stop")
add("stop", "stop stop stop", "stop")
add("stop", "that's enough", "stop | talk")
add("stop", "멈춰", "stop")
add("stop", "그만", "stop")
add("stop", "그만하세요", "stop")
add("stop", "정지하십시오", "stop")
add("stop", "stop, where are you going?", "stop")
add("stop", "wait", "stop | talk")
add("stop", "기다려", "stop | talk")
add("stop", "거기 서", "stop")
add("stop_not", "I can't stop laughing", "talk")
add("stop_not", "the bus stop is outside", "talk")
add("stop_not", "거기서 기다려", "stop | talk")

# ---------- speed ----------
add("speed", "a bit faster", "speed faster")
add("speed", "can you pick up the pace?", "speed faster")
add("speed", "way too slow", "speed faster")
add("speed", "더 빨리", "speed faster")
add("speed", "너무 느려요", "speed faster")
add("speed", "slow down", "speed slower")
add("speed", "not so fast", "speed slower")
add("speed", "ease off a little", "speed slower")
add("speed", "천천히", "speed slower")
add("speed", "속도 줄여 주세요", "speed slower")
add("speed", "좀 천천히 가 줄래요?", "speed slower")
add("speed", "speed 좀 올려", "speed faster")
add("speed_not", "you are so fast at answering", "talk")

# ---------- again, with the turn before ----------
add("again", "again", "action:turn left 90", before=("turn left", "ACTION: turn left 90"))
add("again", "one more time", "action:move forward 1", before=("move forward one meter", "ACTION: move forward 1"))
add("again", "a bit more", "action:turn left 15", before=("turn left", "ACTION: turn left 90"))
add("again", "조금 더", "action:turn right 15", before=("오른쪽으로 돌아", "ACTION: turn right 90"))
add("again", "한 번 더", "action:move back 0.2", before=("20센티 뒤로", "ACTION: move back 0.2"))
add("again", "10센티 더", "action:move forward 0.1", before=("앞으로 50센티", "ACTION: move forward 0.5"))
add("again", "just a few centimetres more", "action:move forward 0.05 | ask", before=("move forward half a meter", "ACTION: move forward 0.5"))
add("again", "same again", "speed faster", before=("a bit faster", "ACTION: speed 1"))
add("again", "less", "speed slower", before=("a bit faster", "ACTION: speed 1"))
add("again", "more", "speed slower", before=("slow down", "ACTION: speed -1"))
add("again_none", "again", "ask | talk")
add("again_none", "한 번 더", "ask | talk")
add("again_talk", "more", "talk", before=("tell me about JAKA", "ACTION: none -\nJAKA makes robot arms."))

# ---------- missions in one command ----------
add("mission", "take the cup, go to booth two and give it to James", "mission")
add("mission", "go to the stage, wait 10 seconds and come back", "mission")
add("mission", "컵 들고 스테이지로 가서 줘", "mission")
add("mission", "스타트 갔다 와", "mission")
add("mission", "pick up the apple then go to the end and put it on the table", "mission | action:fetch")
add("mission", "부스 투에 가서 컵 받아서 테이블 프론트로 가 주세요", "mission")
add("mission_part", "go to the stage and wave", "chain")
add("mission_part", "go to the stage and dance", "chain")
add("mission_part", "스테이지 가서 춤춰", "chain")

# ---------- things the body can't do ----------
add("cant", "jump", CANT)
add("cant", "can you dance for us?", CANT)
add("cant", "fly up to the ceiling", CANT)
add("cant", "go up the stairs", CANT)
add("cant", "open the door for me", CANT)
add("cant", "점프해 봐", CANT)
add("cant", "춤 좀 춰 주세요", CANT)
add("cant", "계단 올라가 주십시오", CANT)

# ---------- questions about abilities: no motion ----------
add("ability", "what can you do?", "talk")
add("ability", "are you able to follow people?", "talk")
add("ability", "how far can you drive?", "talk")
add("ability", "can you pick up a bottle?", "talk | refuse")
add("ability", "how fast can you go?", "talk")
add("ability", "뭐 할 수 있어요?", "talk")
add("ability", "물건 집을 수 있어?", "talk")
add("ability", "사람 따라다닐 수 있나요?", "talk")
add("ability", "can you go to the stage?", GO.format(o="stage"))
add("ability", "스테이지로 가 줄 수 있어요?", GO.format(o="stage"))

# ---------- seeing, status, conversation ----------
add("seeing", "what do you see?", "seeing")
add("seeing", "지금 뭐 보여?", "seeing")
add("status", "what are you doing?", "status")
add("status", "where are you going?", "status")
add("status", "what are you holding?", "status", state="holding")
add("status", "뭐 해?", "status")
add("status", "어디 가?", "status")
add("talk", "I see", "talk")
add("talk", "아 그렇구나", "talk")
add("talk", "okay", "talk | end")
add("talk", "thank you", "talk | end")
add("end", "thanks, that's all", "end")
add("end", "수고하세요", "end")
add("end", "see you", "end | action:wave")
add("talk", "good morning, Lumi", "talk")
add("talk", "go on", "end | talk")
