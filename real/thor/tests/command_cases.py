"""Generated commands and questions, English, Korean and mixed, with the route Lumi must take: templates x slot
fills (tests/command_check.py runs them).

A case: {"intent", "text", "lang", "state": "idle" | "holding", "before": (text, action line) or None, "expect"}.
expect: alternatives split by " | ":
    action:<a> [words]   a quick command or the LLM's action (words must be in its target): pick cup, look me
    receive [object]     take something from the person's hand (the camera checks first)
    give | place [thing] hand over / put down what is held
    empty_hand           nothing is held: "I'm not holding anything"
    refuse               a fixed refusal ("I won't open my hand while holding something")
    mission | status | stop | end | sing | search | weather | ask (a clarifying question) | talk (answer only)
Every case is right, a miss (no motion: talk / ask / unclear where a motion was wanted) or wrong (a motion that was
not asked for, or the wrong one). Nothing may be wrong.
"""
import random
import re

R = random.Random(7)           # the same cases every run

OBJ_EN = [("cup", "cup"), ("bottle", "bottle"), ("apple", "apple"), ("banana", "banana"), ("orange", "orange"),
          ("mug", "cup"), ("red cup", "red cup"), ("white cup", "white cup"), ("blue bottle", "blue bottle"),
          ("glass", "cup")]
OBJ_KO = [("컵", "cup"), ("병", "bottle"), ("사과", "apple"), ("바나나", "banana"), ("빨간 컵", "red cup"),
          ("흰 컵", "white cup"), ("파란 병", "blue bottle"), ("오렌지", "orange")]
PRE_EN = ["", "please ", "Lumi, ", "hey Lumi, ", "okay Lumi, ", "um, ", "could you ", "can you ", "would you ",
          "uh, could you please ", "Lumi, can you ", "so, ", "alright, "]
PRE_CALL = ["", "Lumi, ", "hey Lumi, ", "okay Lumi, ", "um, ", "so, ", "alright, "]   # before a question or "I ..."
POST_EN = ["", " please", " for me", ", thanks", " now", ".", "!", " real quick", " if you can"]
PRE_KO = ["", "루미야 ", "루미야, ", "저기 ", "음 ", "자, ", "혹시 "]
CASES = []


def add(intent, text, expect, lang=None, state="idle", before=None):
    lang = lang or ("ko" if any("가" <= ch <= "힣" for ch in text) else "en")
    CASES.append({"intent": intent, "text": text, "lang": lang, "state": state, "before": before, "expect": expect})


VARIANTS = 3                   # wordings (prefix / suffix) made of each template and fill


def en(intent, templates, expect, slots=None, state="idle", n=VARIANTS):
    """English: every template x slot, n times with a random prefix / suffix (the plain wording first)."""
    for tpl in templates:
        for word, val in (slots or [("", "")]):
            seen = set()
            for i in range(n):
                asking = re.match(r"(?:what|how|why|where|when|which|who|do|does|is|are|can|could|i\b|i'|my|there|here|"
                                  r"you|nice|hello)", tpl, re.I)
                p, s = ("", "") if i == 0 else (R.choice(PRE_CALL if asking else PRE_EN),
                                                "" if asking or tpl.endswith("?") else R.choice(POST_EN))
                if p.rstrip().endswith("you") and s in (".", "!"):
                    s = "?"
                text = p + tpl.format(o=word) + s
                text = text[0].upper() + text[1:] if i else text
                if text not in seen:
                    seen.add(text)
                    add(intent, text, expect.format(o=val), state=state)


def ko(intent, templates, expect, slots=None, state="idle", n=VARIANTS):
    for tpl in templates:
        for word, val in (slots or [("", "")]):
            for text in dict.fromkeys(("" if i == 0 else R.choice(PRE_KO)) + tpl.format(o=word) for i in range(n)):
                add(intent, text, expect.format(o=val), state=state)


def both(intent, templates, expect, slots=None, state="idle"):
    """English and Korean templates in one list."""
    for tpl in templates:
        (ko if any("가" <= ch <= "힣" for ch in tpl) else en)(intent, [tpl], expect, slots, state)


# ---------- pick from the table in front ----------
en("pick", ["pick up the {o}", "grab the {o}", "take the {o}", "get the {o}", "pick the {o} up", "lift the {o}",
            "pick up that {o}", "grab that {o} on the table", "pick up the {o} in front of you", "take the {o} off the table"],
   "action:pick {o} | mission", OBJ_EN)
ko("pick", ["{o} 집어", "{o} 좀 집어 줘", "{o} 잡아", "{o} 들어 봐", "{o} 집어 주세요", "{o}을 들어 줄래?", "테이블에 있는 {o} 집어",
            "{o} 좀 잡아 볼래요?"], "action:pick {o} | mission", OBJ_KO)
# pass me X: pick it, then hand it over
en("pass_me", ["pass me the {o}", "hand me the {o}", "give me the {o}", "can I have the {o}", "could I get the {o}",
               "bring me that {o} on the table"],
   "mission | action:fetch {o}", OBJ_EN[:7])
ko("pass_me", ["{o} 좀 줘", "{o} 건네 줘", "{o} 좀 주세요", "저한테 {o} 좀 주실래요?", "{o} 나한테 줘"],
   "mission | action:fetch {o}", OBJ_KO[:6])

# ---------- receive: take it from the person's hand ----------
REC_EN = ["take this", "here, take this", "take this from me", "take it from my hand", "take this from my hand",
          "hold this", "hold this for me", "can you hold this?", "here you go", "here, hold it", "grab this from me",
          "take what I'm holding", "I want to give you something", "I have something for you, take it"]
REC_EN_OBJ = ["take the {o} from my hand", "take my {o}", "take this {o} from me", "hold this {o}", "I'll give you this {o}",
              "here's the {o}, take it", "I want to give you a {o}", "take the {o} I'm holding", "I'm handing you the {o}",
              "can you take the {o} from me?", "please hold my {o} for a moment"]
REC_KO = ["이거 받아", "이거 받아 줘", "이거 좀 받아 주세요", "받아", "자, 받아", "받으세요", "드릴게요", "이거 드릴게요", "이거 가져가",
          "내 손에 있는 거 가져가", "제 손에 있는 거 가져가세요", "이거 좀 들고 있어", "이거 들고 있어 줄래요?", "이거 줄게"]
REC_KO_OBJ = ["{o} 받아", "{o} 드릴게요", "이 {o} 받아 줘", "제 손에 있는 {o} 가져가세요", "이 {o} 좀 들고 있어", "{o} 받아 줄래요?",
              "내가 {o} 줄게", "제가 {o} 드릴게요, 받아 주세요"]
OBJ_ONLY = [(w, v.split()[-1]) for w, v in OBJ_EN[:6]]
OBJ_ONLY_KO = [(w, v.split()[-1]) for w, v in OBJ_KO[:5]]
both("receive", REC_EN + REC_KO, "receive")
en("receive", REC_EN_OBJ, "receive {o}", OBJ_ONLY)
ko("receive", REC_KO_OBJ, "receive {o}", OBJ_ONLY_KO)
both("receive", REC_EN + REC_KO[:6], "receive | refuse", state="holding")
en("receive", REC_EN_OBJ, "receive | refuse", OBJ_ONLY[:3], state="holding")

# ---------- give / place what is held ----------
GIVE_EN = ["give it to me", "give me that", "hand it over", "hand it to her", "give it to him", "pass it to me",
           "give it to that person", "can I have it?", "I'll take it", "let me have it", "give it back", "hand it to me",
           "give that to my friend", "pass it over here", "give it to the lady", "okay, give it", "hand it to them"]
GIVE_KO = ["줘", "이리 줘", "그거 줘", "나 줘", "저 줘요", "저 사람한테 줘", "그 사람한테 건네 줘", "이 분께 드려", "그거 저한테 주세요",
           "이제 줘", "그거 이리 주세요", "그거 내 친구한테 줘", "건네 줘", "저 분한테 드려요"]
PLACE_EN = ["put it down", "put it here", "put it there", "set it down", "leave it here", "put it on the table",
            "put it on that table", "place it on the desk", "drop it here", "put it next to the laptop",
            "set it down over there", "just put it down", "put that on the table please", "place it here"]
PLACE_KO = ["여기 놔", "거기 놔", "내려놔", "내려 놓아 줘", "테이블에 놔", "책상 위에 올려놔", "여기 둬", "탁자에 놓아 주세요",
            "그거 내려놔", "여기에 내려 주세요", "거기 둬", "테이블 위에 놔 줘"]
both("give", GIVE_EN + GIVE_KO, "give", state="holding")
both("give", GIVE_EN + GIVE_KO, "empty_hand | ask | talk")
both("place", PLACE_EN + PLACE_KO, "place | action:put down", state="holding")
both("place", PLACE_EN + PLACE_KO, "empty_hand | ask | talk")
en("give", ["give me the {o}", "hand me the {o}", "can I have the {o}?"], "give", OBJ_ONLY[:5], state="holding")
ko("give", ["{o} 줘", "{o} 이리 주세요"], "give", OBJ_ONLY_KO[:4], state="holding")
en("place", ["put the {o} on the table", "put the {o} down"], "place | action:put down", OBJ_ONLY[:5], state="holding")
both("place", ["put it back", "put it back where it was", "제자리에 놔", "다시 제자리에 둬"], "action:put back", state="holding")

# ---------- the hand: open / close ----------
for t in ["open your hand", "open your gripper", "open your fingers", "let go", "now open it", "open your hand please",
          "손 펴", "손 벌려", "손 좀 펴 봐", "손 펴 줘", "손을 열어", "다시 손 펴", "hand open 해 줘", "손 open 해"]:
    both("hand", [t], "action:arm open")
    both("hand", [t], "refuse | place | give", state="holding")    # it would fall
for t in ["close your hand", "now close it", "close it again", "close your fingers", "close your gripper", "make a fist",
          "손 쥐어", "주먹 쥐어", "손 오므려", "다시 손 닫아", "손 쥐어 봐", "손 close 해 줘"]:
    both("hand", [t], "action:arm close")

# ---------- arm ----------
for t in ["reach out your hand", "stretch out your arm", "put your arm out", "hold out your hand", "extend your arm",
          "팔 뻗어", "팔 좀 내밀어 봐", "팔을 쭉 뻗어 줘"]:
    both("arm", [t], "action:arm reach")
for t in ["fold your arm", "put your arm down", "tuck your arm in", "put your arm away", "팔 접어", "팔 내려", "팔 거둬"]:
    both("arm", [t], "action:arm fold")

# ---------- look ----------
for t, want in [("look at me", "me"), ("look at me please", "me"), ("eyes on me", "me"), ("face me", "me"),
                ("look over here", "me | center"), ("나 봐", "me"), ("저 좀 봐 주세요", "me"), ("나를 봐", "me"),
                ("look left", "left"), ("look to your right", "right"), ("look up", "up"), ("look down", "down"),
                ("look up a bit", "up small"), ("look straight ahead", "center"), ("왼쪽 봐", "left"), ("오른쪽 좀 봐", "right"),
                ("위를 봐", "up"), ("아래 봐", "down"), ("고개 들어", "up"), ("고개 숙여", "down"), ("정면 봐", "center"),
                ("turn your head to the left", "left"), ("고개 오른쪽으로 돌려", "right"), ("look behind you", "left"),
                ("look away", "away"), ("don't look at me", "away"), ("stop looking at me", "away"),
                ("stop staring at me", "away"), ("please don't stare at me", "away"), ("쳐다보지 마", "away"),
                ("날 보지 마", "away"), ("나 보지 마세요", "away"), ("다른 데 봐", "away"), ("저 쳐다보지 마세요", "away"),
                ("look somewhere else", "away"), ("고개 돌려", "away | left | right | center | talk"),
                ("look at the back side", "left 180"), ("look at back side", "left 180"), ("look at behind", "left 180"),
                ("look at behind side", "left 180"), ("look at the backside", "left 180"), ("look back", "left 180"),
                ("look at the big side", "left 180"), ("turn your head back", "left 180"), ("turn around and look", "left 180"),
                ("look over your right shoulder", "right 180"), ("뒤 봐", "left 180"), ("뒤를 봐", "left 180"),
                ("뒤돌아 봐", "left 180"), ("뒤쪽 봐", "left 180"), ("뒤에 봐 줘", "left 180"), ("고개 뒤로 돌려", "left 180"),
                ("오른쪽 뒤 봐", "right 180"), ("back side 봐", "left 180"), ("뒤 좀 look 해 줘", "left 180"),
                ("look forward", "center"), ("look ahead", "center")]:
    alts = " | ".join("talk" if w.strip() == "talk" else f"action:look {w.strip()}" for w in want.split("|"))
    both("look", [t], alts)

# ---------- base ----------
for t, want in [("move forward one metre", "action:move forward"), ("go back a little", "action:move back"),
                ("back up please", "action:move back"), ("step back", "action:move back"), ("scoot forward", "action:move forward"),
                ("move left 2 meters", "action:move left"), ("앞으로 1미터 가", "action:move forward"),
                ("뒤로 조금 가 줘", "action:move back"), ("뒤로 물러나", "action:move back"), ("왼쪽으로 50센티 가", "action:move left"),
                ("turn around", "action:turn around"), ("turn left", "action:turn left"), ("turn right 45 degrees", "action:turn right"),
                ("spin around", "action:turn 360"), ("한 바퀴 돌아", "action:turn 360"), ("왼쪽으로 돌아", "action:turn left"),
                ("come here", "action:come"), ("come to me", "action:come"), ("come closer", "action:come"), ("이리 와", "action:come"),
                ("여기로 와 줘", "action:come"), ("come over here please", "action:come"),
                ("go to p3", "action:go_to p3"), ("go to point two", "action:go_to p2"), ("p5로 가", "action:go_to p5"),
                ("go home", "action:go_to home"), ("go charge yourself", "action:go_to home"), ("충전하러 가", "action:go_to home"),
                ("can you move?", "action:move back"), ("비켜 줄래요?", "action:move back"), ("get out of the way", "action:move back"),
                ("move forward ten meters", "talk | refuse"), ("앞으로 10미터 가", "talk | refuse"), ("go to the kitchen", "talk | ask"),
                ("go to p77", "talk | ask"), ("주방으로 가", "talk | ask"),
                ("let's back 1 meter", "action:move back 1"), ("lets back 1 meter", "action:move back 1"),     # 2026-10-21:
                ("Let's bake one meter.", "action:move back 1"), ("Big one meter.", "action:move back 1"),     # whisper's
                ("Let's bake one metal.", "action:move back 1"), ("go back 1 meter", "action:move back 1"),    # slips
                ("move back one metre", "action:move back 1"), ("back up 2 meters", "action:move back 2"),
                ("reverse half a meter", "action:move back 0.5"), ("go backwards one meter", "action:move back 1"),
                ("1미터 뒤로 가", "action:move back 1"), ("뒤로 2미터 가 줘", "action:move back 2"),
                ("1미터 후진해", "action:move back 1"), ("I'm stuck, go back one meter", "action:move back 1"),
                ("come back p9", "action:go_to p9"), ("come back here", "action:come")]:
    both("base", [t], want)

# ---------- body ----------
for t, want in [("raise yourself", "action:lift up"), ("get taller", "action:lift up"), ("lower yourself a bit", "action:lift down"),
                ("키 좀 높여", "action:lift up"), ("키 낮춰 줘", "action:lift down"), ("wave", "action:wave"),
                ("wave at me", "action:wave"), ("can you wave?", "action:wave"), ("손 흔들어 줘", "action:wave"),
                ("손 인사 해 봐", "action:wave"), ("wave goodbye to my friend", "action:wave"), ("be quiet", "action:quiet"),
                ("조용히 해", "action:quiet"), ("stop", "stop"), ("stop!", "stop"), ("freeze", "stop"), ("멈춰", "stop"),
                ("그만", "stop"), ("don't move", "stop"), ("움직이지 마", "stop")]:
    both("body", [t], want)

# ---------- fetch / missions ----------
for word, val in OBJ_EN[:5]:
    add("fetch", f"bring me the {word} from p2", f"action:fetch {val} | mission")
    add("fetch", f"go to p3 and get the {word}", f"action:fetch {val} | mission")
    add("fetch", f"could you fetch the {word} from point one for me?", f"action:fetch {val} | mission")
for word, val in OBJ_KO[:5]:
    add("fetch", f"p2에서 {word} 가져와", f"action:fetch {val} | mission")
    add("fetch", f"{word} 들고 p3로 가서 테이블에 놔", f"mission | action:fetch {val}")
for t in ["take the cup, go to p3 and give it to Mina", "pick up the bottle, turn around and give it to me",
          "go to p2, wait 10 seconds and come back", "컵 집어서 p3로 가서 줘", "pick up the apple and hand it to me",
          "take the cup and put it on the chair", "사과 집어서 나한테 줘"]:
    add("mission", t, "mission | action:fetch | refuse" if "bottle" in t else "mission | action:fetch")   # the bottle: why not

# ---------- status ----------
for t in ["what are you holding?", "what's in your hand?", "where are you going?", "what are you doing?", "뭐 하고 있어?",
          "손에 뭐 있어?", "뭐 들고 있어?", "are you holding something?", "is your hand empty?", "어디 가?", "지금 바빠?",
          "what are you up to?", "what have you got there?", "뭐 하는 중이에요?", "그거 뭐야, 손에 든 거?"]:
    both("status", [t], "status")
    both("status", [t], "status", state="holding")

# ---------- what the cameras see (assistant/seeing.py answers) ----------
for t in ["do you see a cup?", "can you see the red cup?", "is there an apple on the table?", "how far is the cup?",
          "what do you see?", "what's in front of you?", "how many people are there?", "can you see me?",
          "what am I holding?", "what's in my hand?", "is my hand raised?", "what am I pointing at?", "what am I doing?",
          "what color is my shirt?", "am I wearing glasses?", "how far am I from you?", "컵 보여?", "앞에 뭐가 있어?",
          "몇 명 보여?", "내가 뭐 들고 있어?", "내 손에 뭐 있어?", "나 보여?", "내가 뭘 가리키고 있어?", "사과 보여요?",
          "뒤에 누가 있어?", "내가 지금 뭐 하고 있어?", "what's behind you?", "뒤에 뭐 있어?", "who is behind you?"]:
    both("seeing", [t], "seeing")
for t in ["what are you holding?", "what's in your hand?", "손에 뭐 들고 있어?"]:     # Lumi's own hand: the task state
    both("seeing", [t], "status")
for t in ["How many people work at Cutshion company?", "how many people work at cutshion campy?",   # 2026-10-21: the
          "how many employees does Cutshion have?", "how many people work there?", "직원이 몇 명이에요?",  # company, from
          "쿳션에는 몇 명이 일해요?"]:                                                          # knowledge
    both("question", [t], "talk")

for t in ["I'll be back", "I'm behind you", "I'll be right back"]:                 # "back", "behind": no head turn
    both("question", [t], "talk | end")

# ---------- things it can't do: a plain answer, no motion ----------
for t in ["can you fly?", "jump", "jump for me!", "dance for me", "can you dance?", "climb the stairs", "open the door",
          "make me a coffee", "lift this table", "pick up that chair", "go upstairs", "do a backflip", "run!", "sit down",
          "날아 봐", "점프해", "춤 춰 줘", "커피 타 줘", "계단 올라가", "문 열어 줘", "이 책상 들어 봐", "앉아", "pick up my phone",
          "take my laptop", "carry me", "give me a hug", "shake hands with me", "throw the cup", "kick the ball",
          "pick me up", "날 안아 줘", "공 차 봐", "이 의자 옮겨 줘", "pick up the box", "bring me a pizza"]:
    both("cannot", [t], "talk | ask | unclear")

# ---------- questions, not orders ----------
for t in ["can you pick up a bottle?", "how do you open your hand?", "do you know how to wave?",
          "what happens if I put something in your hand?", "손 펼 수 있어요?", "how much can you lift?",
          "can you hold a cup?", "how do you know where the cup is?", "why do you look at me?", "can you turn your head?",
          "컵 집을 수 있어요?", "어떻게 물건을 잡아요?", "is it hard to pick up a cup?", "can you give things to people?",
          "do you take things from people's hands?", "what can you carry?", "how far can you move?", "can you see me?"]:
    both("question", [t], "talk | status | seeing")

# ---------- tricks: things that may not be there (the route is right; lumi checks with the camera) ----------
for t, want in [("take the apple from my hand", "receive apple"), ("take the banana I'm holding", "receive banana"),
                ("내 손에 있는 사과 가져가", "receive apple"), ("I'm giving you a bottle, take it", "receive bottle"),
                ("give me the apple you are holding", "give | empty_hand | ask | talk"),
                ("put the banana you're holding on the table", "place | empty_hand | ask | talk")]:
    add("trick", t, want)

# ---------- corrections after an action ----------
for t in ["no, the other one", "not that one", "no, not that", "아니 그거 말고", "그거 말고 다른 거", "wrong one", "no no no, the other cup",
          "아니, 그거 아니야"]:
    add("correction", t, "ask | stop | talk", before=("pick up the cup", "ACTION: pick cup"))
for t, want in [("no, the red one", "action:pick red | ask"), ("아니, 빨간 거", "action:pick red | ask"),
                ("no, the bottle", "action:pick bottle | ask"), ("not the cup, the apple", "action:pick apple | ask")]:
    add("correction", t, want, before=("pick up the cup", "ACTION: pick cup"))
for t, want in [("now close it", "action:arm close"), ("and the other way", "action:look right | ask | talk"),
                ("a bit more", "action:look left | ask | talk")]:
    add("follow_up", t, want, before=("look left" if "way" in t or "more" in t else "open your hand",
                                      "ACTION: look left" if "way" in t or "more" in t else "ACTION: arm open"))

# ---------- mixed English / Korean ----------
for t, want in [("cup 좀 pick up 해 줘", "action:pick cup | mission"), ("look at me 해 봐", "action:look me"),
                ("이거 take 해", "receive"), ("bottle 줘", "mission | action:fetch bottle"), ("left 봐", "action:look left"),
                ("wave 해 줘", "action:wave"), ("p3로 go", "action:go_to p3"), ("손 close 해", "action:arm close"),
                ("apple 집어 줘", "action:pick apple | mission"), ("come here 해", "action:come"),
                ("이거 hold 해 줘", "receive"), ("put it down 해 줘", "empty_hand | ask | talk")]:
    add("mixed", t, want)

# ---------- speech recognition slips ----------
for t, want in [("pick up the cop", "talk | ask | unclear"), ("grab the cap", "talk | ask | unclear"),
                ("Lumi luck at me", "action:look me | talk | ask | unclear"), ("give it too me", "empty_hand | talk | ask"),
                ("put it hear", "empty_hand | talk | ask"), ("loomi come hear", "action:come | talk | ask | unclear"),
                ("pic up the cup", "action:pick cup | talk | ask | unclear"), ("the cup the cup", "talk | ask | unclear"),
                ("컵 집어 줘 어", "action:pick cup | mission"), ("루미야 이리와", "action:come"), ("손펴", "action:arm open"),
                ("고개들어", "action:look up"), ("p 3으로 가", "action:go_to p3 | talk | ask"),
                ("uh take the uh the cup", "action:pick cup | mission | ask"), ("move four word", "talk | ask | unclear")]:
    add("asr", t, want)

# ---------- long, rambling ----------
for t, want in [("okay so um I was wondering if maybe you could, like, pick up the red cup for me, if that's okay",
                 "action:pick red cup | mission"),
                ("so I'm holding this apple and I'd like you to take it from me", "receive apple"),
                ("you know what, I think it would be really nice if you could look at me while we talk", "action:look me"),
                ("hey Lumi, sorry to bother you, but could you please move back a little bit, you're kind of in the way",
                 "action:move back"),
                ("루미야 내가 지금 손에 컵을 들고 있는데 이거 좀 받아 줄래", "receive cup"),
                ("음 그러니까 저기 테이블 위에 있는 빨간 컵 있잖아 그거 좀 집어 줄 수 있어", "action:pick red cup | mission"),
                ("I don't really need it anymore so could you just put it down somewhere", "place | action:put down"),
                ("Lumi, when you get a second, could you hand that to my colleague over there", "give")]:
    add("ramble", t, want, state="holding" if ("put it down somewhere" in t or "hand that" in t) else "idle")

# ---------- chat that is not a command ----------
for t in ["hello", "how are you?", "what's your name?", "nice to meet you", "you're cute", "who made you?", "안녕하세요",
          "이름이 뭐예요?", "몇 살이에요?", "I like your hand", "your arm looks strong", "is that your hand?",
          "I have an apple", "I'm holding a cup", "there's a cup on the table",
          "저 사람은 내 친구야", "사과 좋아해?", "I gave my friend a cup yesterday", "look, it's raining"]:
    both("chat", [t], "talk | status")
both("chat", ["my friend is over there"], "talk | action:look")   # looking that way is fine

# ---------- distances and speed by voice (assistant/driving.py): exact amounts, vague ones, "again", limits ----------
MOVED = ("go back 20 cm", "ACTION: move back 0.2")
SPED = ("a bit faster", "ACTION: speed 1\nOkay, a bit faster: 120 percent of my normal speed.")
SLOWED = ("천천히", "ACTION: speed -1\n네, 조금 더 천천히 갈게요. 보통 속도의 80퍼센트예요.")
TALKED = ("what's your name?", "ACTION: none -\nI'm Lumi.")
for t, want, before in [
        # exact: digits, words, units, Korean, whisper's slips ("come back to" for "come back", "bake", "metal")
        ("Let's come back to 20 cm.", "action:move back 0.2", None), ("come back 20 cm", "action:move back 0.2", None),
        ("go forward 30 cm", "action:move forward 0.3", None), ("move back 5 centimeters", "action:move back 0.05", None),
        ("move back fifteen centimetres please", "action:move back 0.15", None),
        ("could you back up two hundred millimetres", "action:move back 0.2", None),
        ("move forward one point five meters", "action:move forward 1.5", None),
        ("go back 1 cm", "action:move back 0.01", None), ("move back 10 mm", "action:move back 0.01", None),
        ("Let's bake 20 cm.", "action:move back 0.2", None), ("big 30 centimeters", "action:move back 0.3", None),
        ("go back 2 metals", "action:move back 2", None), ("move left 40 cm", "action:move left 0.4", None),
        ("20센티 뒤로", "action:move back 0.2", None), ("20센티 뒤로 가 줘", "action:move back 0.2", None),
        ("앞으로 반 미터", "action:move forward 0.5", None), ("앞으로 반 미터 가", "action:move forward 0.5", None),
        ("이십 센티 뒤로 가", "action:move back 0.2", None), ("일 미터 앞으로 가", "action:move forward 1", None),
        ("뒤로 오십 센치만 가 줘", "action:move back 0.5", None), ("루미야 뒤로 삼십 센티 가", "action:move back 0.3", None),
        ("뒤로 10 cm 가", "action:move back 0.1", None), ("back 20센티", "action:move back 0.2", None),
        # vague: a fixed estimate, read back with "about"
        ("back up a tiny bit", "action:move back 0.05", None), ("a hair to the left", "action:move left 0.05", None),
        ("inch forward", "action:move forward 0.05", None), ("scoot back just a touch", "action:move back 0.05", None),
        ("살짝 뒤로", "action:move back 0.05", None), ("살짝만 앞으로 가 줘", "action:move forward 0.05", None),
        ("한 뼘 앞으로", "action:move forward 0.2", None), ("반 걸음 뒤로", "action:move back 0.25", None),
        ("한 걸음 뒤로 가", "action:move back 0.5", None), ("two steps back", "action:move back 1", None),
        ("take a step forward", "action:move forward 0.5", None), ("go back a little", "action:move back 0.5", None),
        # not understood or too far: asked / refused with the limit, never a default
        ("move back 20", "ask", None), ("go back a couple of meters", "ask", None), ("move back a few steps", "ask", None),
        ("move forward 2 feet", "ask", None),
        ("move back 5 meters", "refuse", None), ("go forward 2 km", "refuse", None), ("drive back three miles", "refuse", None),
        ("뒤로 5미터 가", "refuse", None), ("앞으로 천 미터 가", "refuse", None), ("move back 1 mm", "refuse", None),
        # places and other things stay what they are
        ("come back here", "action:come", None), ("come back to p9", "action:go_to p9", None),
        ("come back p9", "action:go_to p9", None), ("go right ahead", "talk", None), ("look left a bit", "action:look left", None),
        ("I live a few metres to the left", "talk", None), ("I'll be right back", "talk | end", None),
        # speed
        ("go a bit faster", "speed faster", None), ("faster", "speed faster", None), ("speed up", "speed faster", None),
        ("a little faster please", "speed faster", None), ("can you pick up the pace", "speed faster", None),
        ("even faster", "speed faster", None), ("way too slow", "speed faster", None), ("hurry up Lumi", "speed faster", None),
        ("you're too slow", "speed faster", None),
        ("slower", "speed slower", None), ("slow down", "speed slower", None), ("a bit slower", "speed slower", None),
        ("too fast", "speed slower", None), ("not so fast", "speed slower", None), ("ease off", "speed slower", None),
        ("slow it down a notch", "speed slower", None), ("Lumi, slow down please", "speed slower", None),
        ("빨리", "speed faster", None), ("더 빨리", "speed faster", None), ("좀 더 빨리 가 줘", "speed faster", None),
        ("너무 느려", "speed faster", None), ("천천히", "speed slower", None), ("더 천천히", "speed slower", None),
        ("속도 줄여", "speed slower", None), ("너무 빨라", "speed slower", None), ("좀 천천히 가 줄래요", "speed slower", None),
        ("천천히 가세요", "speed slower", None), ("go slower 좀", "speed slower", None),
        # right after a move or a speed change: "more" / "again" repeat it; with nothing before: asked
        ("again", "action:move back 0.2", MOVED), ("a bit more", "action:move back 0.2", MOVED),
        ("same again", "action:move back 0.2", MOVED), ("one more time", "action:move back 0.2", MOVED),
        ("한 번 더", "action:move back 0.2", MOVED), ("조금 더", "action:move back 0.2", MOVED),
        ("just a few centimetres more", "action:move back 0.05", MOVED), ("10센티 더", "action:move back 0.1", MOVED),
        ("more", "speed faster", SPED), ("a bit more", "speed faster", SPED), ("again", "speed faster", SPED),
        ("조금 더", "speed faster", SPED), ("less", "speed slower", SPED), ("한 번 더", "speed slower", SLOWED),
        ("more", "ask", None), ("한 번 더", "ask", None), ("a bit more", "ask", None),
        ("more", "talk", TALKED)]:
    add("drive", t, want, before=before)

# ---------- slang, short and casual ----------
for t, want, st in [
        ("yo Lumi, snag that apple", "action:pick apple | mission", "idle"), ("could ya grab the orange real quick", "action:pick orange | mission", "idle"),
        ("mind passing me the cup?", "mission | action:fetch cup", "idle"), ("lemme have the cup", "mission | action:fetch cup", "idle"),
        ("gimme that", "give", "holding"), ("gimme that", "empty_hand | talk", "idle"), ("gimme", "give", "holding"),
        ("get over here", "action:come", "idle"), ("scooch back a bit", "action:move back", "idle"),
        ("back off a little", "action:move back", "idle"), ("eyes over here", "action:look me | action:look center", "idle"),
        ("quit staring", "action:look away", "idle"), ("drop that here", "place", "holding"), ("chuck it on the table", "place", "holding"),
        ("here, catch", "receive", "idle"), ("yours now, take it", "receive", "idle"), ("open up your hand", "action:arm open", "idle"),
        ("clench your fist", "action:arm close", "idle"), ("hands up!", "talk | action:arm reach | action:lift up", "idle"),
        ("야 그거 줘 봐", "give", "holding"), ("컵 좀 집어 봐라", "action:pick cup | mission", "idle"), ("이리 와 봐", "action:come", "idle"),
        ("고개 좀 왼쪽으로 돌려 봐", "action:look left", "idle"), ("손 좀 펴 봐라", "action:arm open", "idle"),
        ("그거 이리 내놔", "give", "holding"), ("자 받아라", "receive", "idle"), ("이거 맡아 줘", "receive", "idle"),
        ("그만 쳐다봐", "action:look away", "idle"), ("좀 비켜 봐", "action:move back", "idle"), ("뒤로 좀 빠져", "action:move back", "idle"),
        ("사과 하나만 줘", "mission | action:fetch apple", "idle"), ("거기다 놔", "place", "holding"), ("바닥에 내려놔", "place | talk", "holding"),
        ("손 꽉 쥐어", "action:arm close", "idle"), ("팔 쭉 펴", "action:arm reach", "idle"), ("한 바퀴 돌아 봐", "action:turn 360", "idle")]:
    add("slang", t, want, state=st)

# ---------- near misses: not a hand-over, not a correction ----------
for t, want, st, before in [("I get it", "talk", "idle", None), ("hold that thought", "talk", "idle", None),
                            ("leave it", "talk", "holding", None), ("그냥 둬", "talk", "holding", None),
                            ("no thanks", "talk | end", "idle", ("pick up the cup", "ACTION: pick cup")),
                            ("no worries", "talk | end", "idle", ("pick up the cup", "ACTION: pick cup")),
                            ("I'll take a photo of you", "talk", "idle", None), ("can I take a picture?", "talk", "idle", None),
                            ("take care", "end | talk", "idle", None), ("take your time", "talk", "idle", None),
                            ("here is fine", "talk", "idle", None), ("I'm giving a talk later", "talk", "idle", None),
                            ("give me a second", "talk", "idle", None), ("give me a minute to think", "talk", "idle", None),
                            ("hand on heart, you're great", "talk", "idle", None), ("잠깐만 기다려 줘", "talk | stop", "idle", None),
                            ("받아 적어 줘", "talk", "idle", None), ("놀라지 마", "talk", "idle", None),
                            ("And take things from me?", "talk", "idle", ("can you give things to people?", "ACTION: none -\nYes.")),
                            ("I dropped my pen on the floor. Can you get it?", "talk", "idle", None)]:
    add("near_miss", t, want, state=st, before=before)
