"""Words said right after a blocked drive (assistant/detour.py), with what they ask: "retry", "backup", "around",
"back", or None (not a detour: the words go the way they go without a blocked drive). The blocked goal is p3 on
the map M. English, Korean, mixed, and whisper slips. Run through lumi.route by tests/test_detour.py."""

M = ["home", "dock2", "p3", "p5", "p8", "p10", "stage"]
GOAL = "p3"

CASES = {
    # ---- the same goal again ----
    "try again": "retry", "Try again.": "retry", "try it again": "retry", "again": "retry", "Again!": "retry",
    "retry": "retry", "please retry": "retry", "one more time": "retry", "once more": "retry",
    "try once more": "retry", "give it another try": "retry", "give it another go": "retry",
    "give it one more shot": "retry", "have another go": "retry", "another try": "retry", "keep trying": "retry",
    "keep going": "retry", "don't give up": "retry", "don't give up, try again": "retry", "continue": "retry",
    "carry on": "retry", "go on": "retry", "resume": "retry", "try now": "retry", "try harder": "retry",
    "can you try again?": "retry", "could you try again please": "retry", "will you try once more?": "retry",
    "it's clear now, try again": "retry", "I moved it, try again": "retry", "the way is free now, go again": "retry",
    "okay try again": "retry", "go again": "retry", "drive again": "retry", "go to p3 again": "retry",
    "try going to p3 again": "retry", "go back to p3": "retry", "head back to p3 please": "retry",
    "try a gain": "retry", "tri again": "retry", "try again lumi": "retry", "re-try": "retry",
    "다시 해 봐": "retry", "다시 해": "retry", "다시": "retry", "다시 가 봐": "retry", "다시 가": "retry",
    "다시 시도해 봐": "retry", "재시도": "retry", "한 번 더 해 봐": "retry", "한번 더": "retry", "한 번 더 가 봐": "retry",
    "다시 한번 해 봐": "retry", "계속 가": "retry", "계속 해 봐": "retry", "계속 진행해": "retry", "포기하지 마": "retry",
    "포기하지 말고 다시 가 봐": "retry", "이제 치웠어, 다시 가 봐": "retry", "길 비켰어 다시 가": "retry",
    "또 가 봐": "retry", "또 해 봐": "retry", "p3로 다시 가": "retry", "p3에 다시 가 봐": "retry",
    "다시 try 해 봐": "retry", "retry 해 봐": "retry", "one more time 가 봐": "retry", "다시 go": "retry",
    "다른 길 말고 그냥 다시 해": "retry", "try again instead of going around": "retry",

    # ---- back up a little, then again ----
    "back up a little and try again": "backup", "back up and try again": "backup",
    "back up a bit and try again": "backup", "Back up a little, then try again.": "backup",
    "reverse a bit and try again": "backup", "reverse and go again": "backup", "move back a little and retry": "backup",
    "go back a bit and try again": "backup", "step back and try once more": "backup",
    "back off a little and try again": "backup", "back out and try again": "backup",
    "move backwards a bit and go again": "backup", "drive back a little then try again": "backup",
    "try again but back up first": "backup", "try again, reverse a bit first": "backup",
    "back up and give it one more time": "backup", "go back and try again": "backup",
    "뒤로 갔다가 다시 가": "backup", "뒤로 조금 갔다가 다시 가 봐": "backup", "조금 뒤로 가서 다시 해 봐": "backup",
    "뒤로 좀 물러났다가 다시 가": "backup", "물러났다가 다시 해 봐": "backup", "후진했다가 다시 가": "backup",
    "살짝 후진하고 다시 시도해": "backup", "뒤로 빠졌다가 한 번 더 가 봐": "backup", "뒤로 갔다 다시 와": "backup",
    "back up 하고 다시 가": "backup", "뒤로 갔다가 try again": "backup", "reverse 하고 다시 해 봐": "backup",

    # ---- another way ----
    "find a way": "around", "find a way there": "around", "try another way": "around", "go around it": "around",
    "go round it": "around", "go a round it": "around", "drive around it": "around", "get around it": "around",
    "take another route": "around", "take a different route": "around", "try a different path": "around",
    "find another path": "around", "find another way": "around", "use another way": "around",
    "is there another way? try it": "around", "try some other way": "around", "take the other way": "around",
    "find a way around": "around", "find your way": "around", "find a path": "around", "make a detour": "around",
    "take a detour": "around", "avoid it": "around", "avoid the chair": "around", "steer around it": "around",
    "navigate around it": "around", "go past it": "around", "squeeze past it": "around",
    "try an alternative route": "around", "find a new route": "around", "try a better way": "around",
    "can you go around it?": "around", "could you find another way please": "around",
    "try another way to p3": "around", "find a way to p3": "around", "find another way, don't give up": "around",
    "go back and try another way": "around", "can't you find another way?": "around",
    "다른 길로 가 봐": "around", "다른 길로 가": "around", "다른 길 찾아 봐": "around", "돌아서 가": "around",
    "돌아서 가 봐": "around", "옆으로 돌아서 가": "around", "길 찾아서 와": "around", "길을 찾아 봐": "around",
    "길 찾아 봐": "around", "우회해": "around", "우회해서 가": "around", "비켜서 가": "around", "피해서 가": "around",
    "피해 가 봐": "around", "다른 쪽으로 가 봐": "around", "다른 방향으로 가 봐": "around", "다른 경로로 가": "around",
    "옆으로 피해서 가 봐": "around", "옆으로 비켜서 가": "around", "다른 루트로 가 봐": "around",
    "p3까지 다른 길로 가 봐": "around", "다른 길로 돌아가": "around",
    "다른 way로 가 봐": "around", "another way로 가 봐": "around", "go around 해 봐": "around", "detour 해": "around",
    "find a way 해 봐": "around", "돌아서 가 please": "around",

    # ---- back to where the trip started ----
    "go back": "back", "Go back.": "back", "go back where you were": "back", "go back where you came from": "back",
    "go back to where you started": "back", "come back": "back", "Come back please": "back", "return": "back",
    "just return": "back", "head back": "back", "turn back": "back", "get back": "back", "drive back": "back",
    "go back to the start": "back", "back to where you were": "back",
    "okay, go back then": "back", "never mind, go back": "back", "then just go back": "back",
    "you can go back now": "back", "go back to your spot": "back", "return to where you were": "back",
    "go back where you were before": "back", "can you come back?": "back",
    "원래 자리로 돌아가": "back", "원래 자리로 돌아와": "back", "돌아와": "back", "돌아가": "back", "되돌아가": "back",
    "제자리로 돌아가": "back", "처음 자리로 돌아가": "back", "출발한 곳으로 돌아가": "back", "원래 위치로 가": "back",
    "그냥 돌아와": "back", "다시 돌아와": "back", "좀 돌아와 줘": "back", "원래 있던 곳으로 돌아가": "back",
    "go back 해": "back", "come back 해 줘": "back", "원래 자리로 go back": "back", "그냥 return 해": "back",

    # ---- not a detour ----
    "go back a bit": None, "go back 20 cm": None, "move back a little": None, "come back here": None,
    "come back to me": None, "이리 돌아와": None, "나한테 돌아와": None, "여기로 돌아와": None,
    "go to p5": None, "go back to p5": None, "go home": None, "go back home": None, "return to the charger": None,
    "p5로 가": None, "충전하러 가": None, "집으로 돌아가": None,
    "don't try again": None, "don't go back": None, "stop trying": None, "never mind": None, "forget it": None,
    "다시 하지 마": None, "돌아가지 마": None, "그만해": None, "됐어": None, "안 해도 돼": None,
    "why can't you go?": None, "what's blocking you?": None, "did you try again?": None, "have you tried another way?": None,
    "왜 못 가?": None, "다른 길로 가 봤어?": None, "뭐가 막고 있어?": None,
    "say that again": None, "can you repeat that?": None, "tell me again": None, "다시 말해 줘": None,
    "다시 한번 말씀해 주세요": None, "sing it again": None, "노래 다시 불러 줘": None,
    "return the cup": None, "hello": None, "what time is it?": None, "thank you": None, "안녕": None,
    "turn left": None, "look at me": None, "wave": None,
}

# a call or a filler before the words: the same meaning
PREFIX_EN = ["Lumi, ", "okay, ", "hey lumi ", "um, "]
PREFIX_KO = ["루미야 ", "그럼 ", "저기 "]
