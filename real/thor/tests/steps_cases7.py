"""Missions (docs/17), seventh round (2026-10-21 night): three or four steps said in one breath, English, Korean and
mixed, on the conference map (CONF: start, end, init, final, middle, table_front, stage, booth_2, home, dock2), with
then / and / after that / 그리고 / 다음에 / -고 / -서, fillers ("먼저", "그다음", "I'd like you to"), waits, named
people, "갔다 와" / "다녀와". Same notation as tests/test_steps.py; "?" = some words must stay unread (nothing runs).

FIXED: said with a correction inside ("go to start, no, end, then come back"): brain.self_correct first, then read.
READ_BACK: the sentence Lumi says before starting (steps.describe), English and Korean.
"""
CONF = ["home", "start", "end", "init", "final", "middle", "table_front", "stage", "booth_2", "dock2"]

CASES = {
    # ---- the owner's examples, on this map ----
    "take the cup, go to booth two, give it to James and come back": "pick cup | go booth_2 | give James | go here",
    "먼저 스테이지 가서 컵 가져오고 그다음 여기로 와서 줘": "go stage | pick cup | go here | give",
    "take the cup, go to the stage, give it to the person there and come back here": "pick cup | go stage | give | go here",
    # ---- English: then / and / after that ----
    "pick up the cup, then go to the end, then give it to Sarah": "pick cup | go end | give Sarah",
    "grab the apple and take it to table front and put it on the table": "pick apple | go table_front | place dining table",
    "go to booth two, pick up the cup, and bring it back to me": "go booth_2 | pick cup | go here | give",
    "go to the stage, wait 10 seconds, then come back": "go stage | wait 10 | go here",
    "go to start, after that go to middle, after that go to end": "go start | go middle | go end",
    "first go to start, then go to the middle, and finally come back here": "go start | go middle | go here",
    "go to the stage and wait there for 2 minutes, then go to booth two and come back": "go stage | wait 120 | go booth_2 | go here",
    "take the cup to the stage, put it on the table and come back": "pick cup | go stage | place dining table | go here",
    "could you take the cup to the stage and then come back here please": "pick cup | go stage | go here",
    "I'd like you to take the cup, go to the end and hand it to Sarah": "pick cup | go end | give Sarah",
    "I want you to go to the stage, say hello everyone, and come back": "go stage | say hello everyone | go here",
    "go to init, turn around and come back": "go init | turn 180 | go here",
    "turn left, go forward one meter, turn right and go forward half a meter": "turn 90 | move forward 1 | turn -90 | move forward 0.5",
    "go forward 1 meter then turn around then go forward 1 meter": "move forward 1 | turn 180 | move forward 1",
    "go to booth 2, wait until someone gives you a cup, then bring it here": "go booth_2 | receive cup wait | go here",
    "go to the stage and do what they tell you": "go stage | wait order",
    "go to table front, ask them for the cup, then bring it to the stage": "go table_front | receive cup | go stage",
    "take the cup from start to end and give it to Mr. Kim": "go start | pick cup | go end | give Mr. Kim",
    "pick up the red cup, go to the final point, and hold it": "pick red cup | go final | hold",
    "go to the middle, then booth two, then the stage": "go middle | go booth_2 | go stage",
    "go to start, middle and end": "go start | go middle | go end",
    "go to the stage, after 30 seconds go to end": "go stage | wait 30 | go end",
    "wait 5 seconds then go to the stage and come back": "wait 5 | go stage | go here",
    "bring the cup to James at the stage": "pick cup | go stage | give James",
    "take this cup to Anna, she is at booth two": "go booth_2 | give Anna",
    "go to the end and stay there": "go end | wait",
    "go to the stage, wait there, then go home": "go stage | wait | go home",
    "Lumi, go to start and then come back, thanks": "go start | go here",
    "um, take the cup, uh, go to the stage and give it to them": "pick cup | go stage | give",
    "please go to the stage, after that come back and give it to me": "go stage | go here | give",
    "go to the stage, then come back and turn left": "go stage | go here | turn 90",
    "go to the stage once you're there say welcome and then come back": "go stage | say welcome | go here",
    "go to booth 2 and tell them the demo starts at 3, then go to the stage": "go booth_2 | say the demo starts at 3 | go stage",
    "take the cup and bring it to one of start, middle or end": "pick cup | go start,middle,end",
    "head to table front, then make your way to the stage and come back": "go table_front | go stage | go here",
    "navigate to the stage and then return here": "go stage | go here",
    # ---- Korean: -고 / -서 / 그리고 / 다음에, every speech level ----
    "스테이지 가서 컵 가져오고 여기로 와": "go stage | pick cup | go here",
    "컵 집고 스테이지로 가서 제임스한테 줘": "pick cup | go stage | give 제임스",
    "컵 가지고 스테이지 가서 김 대리님께 드려": "pick cup | go stage | give 김 대리님",
    "스타트로 가서 10초 기다렸다가 엔드로 가": "go start | wait 10 | go end",
    "부스 투에서 병 집어서 테이블 프론트로 가져가": "go booth_2 | pick bottle | go table_front",
    "스테이지 가서 안녕하세요라고 말하고 돌아와": "go stage | say 안녕하세요 | go here",
    "스테이지 갔다 와": "go stage | go here",
    "부스 투 다녀와 줄래?": "go booth_2 | go here",
    "스테이지 갔다가 엔드로 가 줘": "go stage | go end",
    "앞으로 1미터 가고 왼쪽으로 돌고 다시 1미터 가": "move forward 1 | turn 90 | move forward 1",
    "먼저 미들로 가고 그다음 엔드로 가 주세요": "go middle | go end",
    "스타트로 가고 그리고 미들로 가고 마지막으로 엔드로 가": "go start | go middle | go end",
    "컵 들고 스테이지로 가서 테이블에 놔 줘": "pick cup | go stage | place dining table",
    "컵 잡고 엔드로 가서 사라한테 주고 돌아와": "pick cup | go end | give 사라 | go here",
    "부스 투에 가서 누가 컵 주면 받아서 여기로 가져와": "go booth_2 | receive cup wait | go here",
    "스테이지에 가서 2분 기다리고 돌아오세요": "go stage | wait 120 | go here",
    "엔드로 가서 거기서 기다려": "go end | wait",
    "스테이지 가서 거기 있는 사람이 시키는 거 해": "go stage | wait order",
    "테이블 프론트에 가서 컵 받아서 스테이지로 가져가": "go table_front | receive cup | go stage",
    "스타트 갔다가 다시 돌아와 줄래요?": "go start | go here",
    "컵을 집어서 파이널로 가 주시고 거기 계신 분께 드리세요": "pick cup | go final | give",
    "사과 들고 미들로 가서 들고 있어": "pick apple | go middle | hold",
    "뒤로 돌아서 앞으로 2미터 가고 오른쪽으로 돌아": "turn 180 | move forward 2 | turn -90",
    "5초 있다가 스테이지로 가": "wait 5 | go stage",
    "스테이지로 가서 이 분 기다렸다가 돌아와": "go stage | wait 120 | go here",
    "이닛으로 가서 뒤로 돌고 와": "go init | turn 180 | go here",
    # ---- mixed ----
    "take the cup 하고 스테이지로 가서 줘": "pick cup | go stage | give",
    "스테이지 가서 pick up the cup 하고 돌아와": "go stage | pick cup | go here",
    "go to 스테이지, wait 10 seconds, 그리고 돌아와": "go stage | wait 10 | go here",
    "컵 take해서 booth 2로 가져가": "pick cup | go booth_2",
    "go to 부스 투 and then come back": "go booth_2 | go here",
    # ---- must not run: unread or not on the map ----
    "go to the stage and wave": "?",
    "go to the stage and follow me": "?",
    "pick up the cup and lift yourself up": "?",
    "go to booth two and look left": "?",
    "go to the stage and dance": "?",
    "go to the kitchen, then come back": "?",
    "take the cup to p3 and come back": "?",                         # p3 is not on this map
    "go to booth, then come back": "?",                               # which booth? never guessed
    "go to the stage for a while and come back": "?",                 # how long? never guessed
    "스테이지 가서 춤추고 와": "?",
    "부엌에 가서 컵 가져와": "?",
    "go to the stage and give it to him": "?",                        # nothing in the hand before: refused by check
}

# second round: Korean "-고 나서" / "-ㄴ 다음에", a gift with the object in between, no commas (whisper), ordinals,
# "after you get to ...", "hang around", "wait for my call", "come right back"
CASES.update({
    "스테이지에 가고 나서 엔드로 가": "go stage | go end",
    "스테이지에 간 다음에 엔드로 가 줘": "go stage | go end",
    "컵을 집은 다음에 스테이지로 가": "pick cup | go stage",
    "컵 집고 나서 스테이지로 가져가": "pick cup | go stage",
    "스테이지에 갔다가 부스 투로 가서 컵 받아 와": "go stage | go booth_2 | receive cup | go here",
    "스테이지로 가서 10초만 기다렸다가 돌아와": "go stage | wait 10 | go here",
    "스테이지 가서 잠깐 기다렸다가 와": "go stage | wait 10 | go here",
    "스테이지까지 가서 사라 씨한테 컵 전해 줘": "go stage | give 사라",
    "엔드로 가서 거기 있는 분한테 이거 드리고 와": "go end | give | go here",
    "부스 투에 있는 제임스한테 이 컵 갖다줘": "pick cup | go booth_2 | give 제임스",
    "go to the stage then wait ten secs then come back": "go stage | wait 10 | go here",
    "go to the stage, hang around for 10 seconds, then come back": "go stage | wait 10 | go here",
    "go to start, then to middle, then back here": "go start | go middle | go here",
    "take the cup over to booth two and come right back": "pick cup | go booth_2 | go here",
    "bring the cup over to the stage and leave it on the table": "pick cup | go stage | place dining table",
    "go grab the cup, bring it to the stage": "pick cup | go stage",
    "go to the stage and get me the cup": "go stage | pick cup | go here | give",
    "after you get to the stage, wait 5 seconds and come back": "go stage | wait 5 | go here",
    "when you get to the stage, say hello": "go stage | say hello",
    "go to stage wait 10 seconds come back": "go stage | wait 10 | go here",
    "first take the cup, second go to the stage, third give it to Sarah": "pick cup | go stage | give Sarah",
    "take the cup and go to booth two, then wait there until someone takes it": "pick cup | go booth_2 | give",
    "go to the stage and give the cup to whoever is there": "go stage | give",
    "go to the stage and hand the cup to the first person you see": "go stage | give",
    "go to booth two and wait for my call": "go booth_2 | wait",
    "booth 2 가서 컵 가져오고 스테이지로 가": "go booth_2 | pick cup | go stage",
    "go to 엔드 and 컵 가져와": "go end | pick cup | go here",
})

# third round: "not booth two", a message to a named person, people and places in any order
CASES.update({
    "take the cup to the stage, not booth two": "pick cup | go stage",
    "스테이지 말고 부스 투로 가서 컵 줘": "go booth_2 | pick cup | go here | give",
    "go to the stage and tell Sarah the meeting is at 3": "go stage | say the meeting is at 3",
    "go to Sarah at the stage and give her the cup": "go stage | give Sarah",
    "Sarah is at booth two, bring her the cup": "pick cup | go booth_2 | give Sarah",
    "사라는 부스 투에 있어, 컵 갖다줘": "pick cup | go booth_2 | give 사라",
    "컵을 사라한테 갖다 줘, 사라는 부스 투에 있어": "pick cup | go booth_2 | give 사라",
    "go to the stage, and if nobody is there, come back": "?",       # no conditions in a task: asked
    "go to the stage, wait a few minutes, then come back": "?",      # how long? never guessed
    "스테이지 가서 몇 분 기다렸다가 와": "?",
    "go to the stage, wait 30 seconds, go to booth two, wait 30 seconds, then come back":
        "go stage | wait 30 | go booth_2 | wait 30 | go here",
    "can you go to booth 2 and ask for a cup and bring it to me": "go booth_2 | receive cup | go here | give",
    "turn around, take the cup and give it to me": "turn 180 | pick cup | give",
    "take the cup and put it on the chair at the stage": "pick cup | go stage | place chair",
})

# fourth round: 하십시오체 / 해요체 with -시- ("가셔서", "받으시고", "기다리신 후에"), "거기서 기다려" (no stop),
# "who is at", "from the table there", "at the stage"
CASES.update({
    "컵을 들고 스테이지로 가신 다음에 테이블에 올려 주세요": "pick cup | go stage | place dining table",
    "스테이지에 가셔서 10초 기다리신 후에 돌아오세요": "go stage | wait 10 | go here",
    "부스 투에 가셔서 컵을 받으시고 여기로 가져와 주십시오": "go booth_2 | receive cup | go here",
    "먼저 컵을 집으시고 엔드로 가셔서 사라 씨께 드리세요": "pick cup | go end | give 사라",
    "스테이지로 가서 컵 가져오고, 그 다음에 부스 투로 가서 제임스한테 줘": "go stage | pick cup | go booth_2 | give 제임스",
    "컵 집어서 스테이지로 가져가서 테이블에 놓고 돌아와": "pick cup | go stage | place dining table | go here",
    "스테이지 갔다가 부스 투 갔다가 돌아와": "go stage | go booth_2 | go here",
    "앞으로 1미터 갔다가 다시 돌아와": "move forward 1 | go here",
    "오른쪽으로 돌고 앞으로 50센티 가고 컵 집어": "turn -90 | move forward 0.5 | pick cup",
    "스테이지로 가서 30초 있다가 엔드로 가서 기다려": "go stage | wait 30 | go end | wait",
    "야 스테이지 가서 컵 좀 가져와 봐": "go stage | pick cup | go here",
    "스테이지 가서 거기서 기다려": "go stage | wait",
    "스테이지 가서 기다리다가 누가 컵 주면 받아서 와": "go stage | receive cup wait | go here",
    "go to the stage, take a cup from the table there and bring it to booth two": "go stage | pick cup | go booth_2",
    "go pick up the cup at the stage and bring it to me": "go stage | pick cup | go here | give",
    "take the cup and bring it to Sarah, who is at booth two": "pick cup | go booth_2 | give Sarah",
    "go to the stage and wait there until I tell you to come back": "go stage | wait",
    "go ahead to the stage and come back": "go stage | go here",
    "take the cup, roll on over to the end, and let Sarah have it": "pick cup | go end | give Sarah",
    "pick up the cup, go forward half a meter, turn right, go forward one meter and put it on the table":
        "pick cup | move forward 0.5 | turn -90 | move forward 1 | place dining table",
})

# said with a correction inside: brain.self_correct reads it first (lumi.answer)
# ---- 2026-10-22: a full turn (two checked half turns), put it back after a pick, look / lift / wave are no steps ----
CASES.update({
    "한 바퀴 돌고 스테이지로 가": "turn 360 | go stage",
    "spin around and then go to the stage": "turn 360 | go stage",
    "go to booth two and turn all the way around": "go booth_2 | turn 360",
    "스테이지 가서 오른쪽으로 한 바퀴 돌아 줘": "go stage | turn -360",
    "go to the end, spin around, then come back": "go end | turn 360 | go here",
    "take the cup and put it back": "pick cup | place",
    "pick up the red cup and put it back down": "pick red cup | place",
    "컵 집었다가 제자리에 놔": "pick cup | place",
    "컵 집고 제자리에 다시 놔 줘": "pick cup | place",
    "take the cup, go to the stage and put it back": "?",
    "let's go stage point and go booth two point": "go stage | go booth_2",
    "first the stage, then the end": "go stage | go end",
    "go to the start point then the end point": "go start | go end",
    "스테이지 포인트 갔다가 엔드 포인트로 가": "go stage | go end",
    "먼저 미들 가고 그다음 파이널로 가": "go middle | go final",
    "look at me and wave": "?",
    "웨이브 하고 나 봐": "?",
    "나 보고 손 흔들어": "?",
    "lift yourself up and wave": "?",
    "go to the stage and spin around the table": "?",
})

FIXED = {
    "take the cup, go to start, no, end, and give it to James": "pick cup | go end | give James",
    "go to start, sorry, I mean the stage, then come back": "go stage | go here",
    "go to the stage, wait 10 seconds, no, 20 seconds, then come back": "go stage | wait 20 | go here",
    "컵 들고 스타트로 가, 아니 엔드로 가서 줘": "pick cup | go end | give",
    "pick up the cup, no, the apple, and bring it to the stage": "pick apple | go stage",
}

# the read-back (steps.describe) for a few of them
READ_BACK = {
    "turn 360 | go stage": ("Turn all the way around, then go to stage.", "한 바퀴 돌고 stage 위치로 갈게요."),
    "go stage | turn -360": ("Go to stage, then turn all the way around to the right.",
                             "stage 위치로 가고 오른쪽으로 한 바퀴 돌게요."),
    "pick cup | place": ("Take the cup, then put it down.", "컵을 집고 테이블에 놓을게요."),
    "pick cup | give": ("Take the cup, then hand it over.", "컵을 집고 건네줄게요."),     # "컵 가져다 줘"
    "pick cup | go booth_2 | give James | go here":
        ("Take the cup, go to booth 2, hand it to James, then come back here.",
         "컵을 집고 booth 2 위치로 가고 James에게 건네주고 여기로 돌아올게요."),
    "go stage | pick cup | go here | give":
        ("Go to stage, take the cup, come back here, then hand it over.",
         "stage 위치로 가고 컵을 집고 여기로 돌아오고 건네줄게요."),
    "go table_front | wait 30 | go home":
        ("Go to table front, wait 30 seconds, then go to my dock.",
         "table front 위치로 가고 30초 기다리고 충전소로 갈게요."),
}

# for the LLM pass (tests/steps_llm_check.py): wordings the rules leave a part of, with what must come out ("?":
# nothing may be kept; every value must be written in the words, steps.read checks that)
LLM = {
    "grab the cup, then zip over to booth two and pass it to whoever is standing there": "pick cup | go booth_2 | give",
    "snag the apple, scoot over to the stage, and drop it on the table": "pick apple | go stage | place dining table",
    "take the cup, roll on over to the end, and let Sarah have it": "pick cup | go end | give Sarah",
    "head to the stage, hang tight for 20 seconds, then make your way back here": "go stage | wait 20 | go here",
    "컵 챙겨서 스테이지 쪽으로 슝 가서 거기 계신 분께 건네 드려": "pick cup | go stage | give",
    "스테이지 가서 한 20초 쉬었다가 돌아와": "go stage | wait 20 | go here",
    "take the cup to the stage and juggle it": "?",
    "go to the stage and then go to the kitchen": "?",
    "take the cup, go to booth seven and give it to Sarah": "?",
    "컵 들고 스테이지 가서 춤추고 와": "?",
}
