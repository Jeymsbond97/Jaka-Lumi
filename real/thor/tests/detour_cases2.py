"""A second set of words said right after a blocked drive (assistant/detour.py), written fresh as whole classes a
visitor would use: the way is clear now + go, permission to go, route / reroute / the long way, asking Lumi to look
for a way, pointing out a gap or a side, backing up first, going back; English, Korean in every politeness level
(반말, 해요, 하십시오, 주세요, 줄래, with 좀 / 한번), mixed, whisper slips. Values: what is asked ("retry", "around",
"backup", "back"), a tuple of what may be read ("any": any of the four but "back"), or None (not a detour).
The blocked goal is p3 (tests/detour_cases.M)."""

ANY = ("retry", "around", "backup")

CASES = {
    # ---- the way is clear now, go ----
    "it's clear now, you can go": "retry", "the path is clear, go ahead": "retry", "the way is free now": ANY,
    "nothing's in the way anymore, go": "retry", "I moved the box, go": "retry", "we moved out of your way, go on": "retry",
    "the chair is gone, try now": "retry", "the person moved, carry on": "retry", "okay it's open now, go": "retry",
    "all clear, go": "retry", "coast is clear": ANY, "you're good to go": "retry", "you're clear": ANY,
    "the obstacle is gone": ANY, "I cleared the way for you": ANY, "the door is open now, go through": "retry",
    "길 비웠어, 가": "retry", "이제 길 열렸어 가 봐": "retry", "치웠으니까 가도 돼": "retry", "이제 막힌 거 없어, 가": "retry",
    "장애물 치웠어요, 다시 가 보세요": "retry", "의자 치웠어 이제 가": "retry", "사람 비켰어요, 가세요": "retry",
    "이제 지나갈 수 있어": ANY, "길 뚫렸어": ANY, "이제 괜찮아, 가 봐": "retry", "다 치웠습니다. 출발하십시오": "retry",
    "box 치웠어 go": "retry", "이제 clear 해, 가": "retry", "path clear 됐어 다시 가": "retry",
    # ---- permission ----
    "you can go now": "retry", "go ahead": "retry", "you may go": "retry", "off you go": "retry", "go for it": "retry",
    "it's fine, go": "retry", "proceed": "retry", "please proceed": "retry", "move along": "retry", "get going": "retry",
    "이제 가도 돼": "retry", "가도 돼요": "retry", "가세요": "retry", "가 봐": "retry", "출발해": "retry", "출발해 주세요": "retry",
    "이제 가 주세요": "retry", "그냥 가": "retry", "가던 길 가": "retry", "가던 데로 계속 가 줄래?": "retry",
    "진행해 주십시오": "retry", "다시 출발": "retry", "고고": "retry", "ㄱㄱ": "retry", "이제 go 해도 돼": "retry",
    # ---- route, reroute, the long way ----
    "reroute": "around", "re-route please": "around", "recalculate your route": "around", "plan a new route": "around",
    "find a new path": "around", "take the long way": "around", "go the long way round": "around",
    "use the other aisle": "around", "go through the other side": "around", "take the next aisle": "around",
    "try the route on the right": "around", "pick another route": "around", "change your route": "around",
    "경로 바꿔": "around", "경로 다시 짜 봐": "around", "다른 경로로 가 주세요": "around", "멀리 돌아서 가": "around",
    "돌아가는 길로 가": "around", "다른 통로로 가": "around", "옆 통로로 가 봐": "around", "반대쪽으로 돌아가 봐": "around",
    "route 바꿔서 가": "around", "reroute 해 줘": "around", "다른 path 찾아": "around", "우회로로 가": "around",
    # ---- look for a way ----
    "look for a way": "around", "look for another way": "around", "can you find a way through?": "around",
    "search for a path": "around", "see if there's another way": "around", "figure out a way": "around",
    "work out how to get there": "around", "find some way to get there": "around", "find your own way": "around",
    "길 좀 찾아 봐": "around", "길 한번 찾아 봐": "around", "다른 길 좀 찾아 줄래?": "around", "갈 수 있는 길 찾아 봐": "around",
    "길을 찾아 주세요": "around", "다른 길을 찾아 주십시오": "around", "길 좀 알아서 찾아 가": "around",
    "어떻게든 가 봐": ANY, "알아서 가 봐": ANY, "방법 좀 찾아 봐": "around", "길 찾아 줘": "around",
    "find a 길": "around", "길 search 해 봐": "around", "way 좀 찾아 봐": "around",
    # ---- a gap or a side ----
    "there's room on the right": "around", "there's space on the left": "around", "go by the right": "around",
    "squeeze through on the left": "around", "there's a gap over there": "around", "pass on the left side": "around",
    "keep to the right and go": "around", "go along the wall": "around", "use the gap by the wall": "around",
    "you can fit through on the right": "around", "go left of it": "around", "go to the right of the table": "around",
    "오른쪽으로 공간 있어": "around", "왼쪽으로 지나가": "around", "왼쪽에 틈 있어, 그쪽으로 가": "around",
    "오른쪽으로 비켜서 가 봐": "around", "벽 쪽으로 붙어서 가": "around", "옆으로 지나가 봐": "around",
    "오른쪽 옆으로 돌아서 가": "around", "왼쪽 공간으로 가 주세요": "around", "right side로 가 봐": "around",
    # ---- back up first ----
    "back up and go again": "backup", "reverse a little, then go": "backup", "back off a bit then try": "backup",
    "move back first, then try again": "backup", "take a step back and try": "backup", "back up some and retry": "backup",
    "뒤로 좀 갔다가 다시 해 봐": "backup", "조금 물러났다가 가": "backup", "한 발 뒤로 갔다가 다시": "backup",
    "후진 좀 하고 다시 가 봐": "backup", "뒤로 물러서서 다시 가 주세요": "backup", "back 좀 하고 다시": "backup",
    # ---- again, many ways ----
    "give it another shot": "retry", "try one more time": "retry", "try it once more please": "retry",
    "have one more go": "retry", "let's try that again": "retry", "do it again": "retry", "try again, lumi": "retry",
    "maybe try again?": "retry", "how about trying again?": "retry", "would you try again for me": "retry",
    "please try once again": "retry", "again please": "retry", "tryagain": "retry", "try agian": "retry",
    "한번 더 가 봐": "retry", "한 번만 더 시도해 줘": "retry", "다시 가 주세요": "retry", "다시 해 주실래요?": "retry",
    "재도전": "retry", "다시 도전해 봐": "retry", "다시 한 번 가 볼래?": "retry", "다시 시도하십시오": "retry",
    "또 해 볼래?": "retry", "다시 트라이": "retry", "one more 해 봐": "retry", "다시 retry": "retry",
    # ---- go back ----
    "head back to where you started": "back", "return to your starting point": "back", "go back to the start": "back",
    "just come back": "back", "come back, it's okay": "back", "give up and come back": "back",
    "forget about it, come back": "back", "return please": "back", "go back where you were standing": "back",
    "원래 자리로 와": "back", "돌아오세요": "back", "그냥 돌아와 줘": "back", "포기하고 돌아와": "back",
    "출발했던 데로 돌아가": "back", "원래 있던 데로 돌아가 주세요": "back", "제자리로 가": "back",
    "그냥 back 해": "back", "return 해 줘": "back",
    # found by the LLM probe (scratchpad, 2026-10-22): kept here so the rules hold them
    "forget p3, just come back to where you started": "back", "p3 잊어버리고 원래 자리로 돌아와": "back",
    "사람들 이제 다 지나갔어": ANY, "이제 됐어, 움직여": "retry", "we pushed the trolley aside, so off you trot": "retry",
    "maybe sneak by along the window": ANY, "그 사이로 빠져나가 봐": "around", "어디 다른 데로 해서 가 봐": "around",
    "navigate past the cart": "around", "slip through the gap next to the cart": "around",
    # ---- not a detour ----
    "go to p8": None, "p8로 가": None, "go home": None, "홈으로 가": None, "충전하러 가": None, "go to the stage": None,
    "come here": None, "이리 와": None, "come to me": None, "follow me": None, "stop": None, "멈춰": None,
    "stay there": None, "거기 있어": None, "wait there": None, "거기서 기다려": None, "don't move": None,
    "what's in your way?": None, "why did you stop?": None, "왜 멈췄어?": None, "is something blocking you?": None,
    "뭐가 막고 있어?": None, "are you stuck?": None, "can you see what's blocking you?": None,
    "don't go around it": None, "don't try again, just stay": None, "다시 가지 마": None, "돌아가지 말고 거기 있어": None,
    "tell me again": None, "say it again": None, "다시 말해 줄래?": None, "one more time, what did you say?": None,
    "go back 30 centimeters": None, "back up a little": None, "move back a bit": None, "조금 뒤로 가": None,
    "turn left": None, "turn around": None, "look right": None, "오른쪽 봐": None, "wave": None,
    "hello": None, "thanks": None, "고마워": None, "what time is it?": None, "what's your name?": None,
}

PREFIX_EN = ["Lumi, ", "okay ", "um ", "hey Lumi, "]
PREFIX_KO = ["루미야, ", "그럼 ", "음 ", "자, "]
