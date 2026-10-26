"""Head / lift / base wordings and limits, without the robot (head.status / moveto faked, nothing moves).

    .venv/bin/python tests/test_motion_words.py
"""
import types

from assistant import brain, lumi
from robot import head

# ---------- at an axis end: said plainly, nothing moves (HANDOFF 16.2) ----------
lo, hi = brain.HEAD_PITCH
assert brain.head_goal("down", 0, lo)[2] == "down"
assert brain.head_goal("down", 0, lo - 0.003)[2] == "down"          # the pitch reads -5.003 at its stop
assert brain.head_goal("down small", 0, lo)[2] == "down"            # "more" after "look down"
assert brain.head_goal("up small", 0, hi)[2] == "up"
assert brain.head_goal("left small", brain.HEAD_YAW[1], 0)[2] == "left"
assert brain.head_goal("right", -brain.HEAD_YAW[1], 0)[2] == "right"
assert brain.head_goal("down", 0, lo + 2)[2] is None                # the last two degrees still move
assert brain.head_goal("center", 0, lo)[2] is None
assert brain.head_goal("up 50", 0, 0)[2] == "pitch"                 # a number past the range: the range said
assert brain.lift_goal("down", 0) == (0.0, "down")
assert brain.lift_goal("down small", 0.4) == (0.0, "down")
assert brain.lift_goal("up small", 105, 105) == (105, "up")
assert brain.lift_goal("up 50", 80) == (105.0, True)
assert brain.lift_goal("down small", 10) == (0.0, False)
for k in ("left", "right", "up", "down", "lift_up", "lift_down", "lift", "yaw", "pitch"):
    en, ko = lumi.LIMIT_SAY[k]
    assert en and ko and "okay" not in en.lower()

# Lumi.look / Lumi.lift with a fake body: at the end nothing is sent and the LIMIT_SAY key comes back
moved = []
real = head.status, head.moveto
fake = types.SimpleNamespace(looked_at=0)
try:
    head.moveto = lambda *a, **k: moved.append(a)
    head.status = lambda: [0.0, 0.0, 0.0, lo]
    assert lumi.Lumi.look(fake, "down") == "down" and lumi.Lumi.look(fake, "down small") == "down"
    assert lumi.Lumi.lift(fake, "down") == "lift_down" and lumi.Lumi.lift(fake, "down small") == "lift_down"
    head.status = lambda: [head.LIFT_MAX_MM, 0.0, 0.0, hi]
    assert lumi.Lumi.look(fake, "up small") == "up" and lumi.Lumi.lift(fake, "up") == "lift_up"
    assert not moved, moved
finally:
    head.status, head.moveto = real

# ---------- stop: a sentence that only says stop, also after calls and tags; not talk about stopping ----------
from assistant import chain, driving
OFFICE = ["p1", "p2", "p3", "home", "exit", "dock2"]
for t in ("hi Lumi, stop, okay?", "enough already", "that's enough", "stahp", "루미야, 그만해 줄래?", "멈쳐", "고마 서라",
          "stay here", "거기 그대로 있어", "stop", "멈춰", "루미야 그만해", "Lumi, stop moving"):
    assert lumi.stop_order(t, OFFICE), t
for t in ("stop-motion videos are fun", "I wish time would stop", "회사 그만뒀어", "민수야 그만해", "엄마 그만 찍어",
          "we should stop for coffee", "Jake, stop touching the robot!", "when people come, you stop",
          "yo why'd you freeze lol", "is there a bus stop near here?"):
    assert not lumi.stop_order(t, OFFICE), t

# ---------- chains: parts read by the bank / Korean -고 forms; no chain from talk about the past or a relative ----------
def kinds(t, mk=OFFICE):
    p = chain.plan(t, mk, lumi.NOT_A_STEP)
    return [(k, w[0] if k == "quick" else None) for k, _, w in p] if p else None
assert kinds("고개 숙이고 몸 좀 내려") == [("quick", "look"), ("quick", "lift")]
assert kinds("나 쳐다보고 follow me") == [("quick", "look"), ("quick", "follow")]
assert kinds("I want you to tell me how old you are, and wave hello") == [("talk", None), ("quick", "wave")]
assert kinds("you go home and also what time is it") == [("quick", "go_to"), ("talk", None)]
assert kinds("왼쪽으로 도시고 손 인사 해 주세요.") == [("quick", "turn"), ("quick", "wave")]
for t in ("go ahead and turn right, okay?", "Hey, can you look over to the right, where the door is?",
          "so you got shorter, didn't you?", "You went to gate 1 earlier, right?", "go dock two you, yes?",
          "come here, I need help"):
    assert kinds(t) is None, t

# ---------- driving: a bare way right after a look, "again" forms after a move / turn ----------
look, turn, move = ("look", "right small"), ("turn", "right 90"), ("move", "forward 1", True)
assert driving.read(brain._norm("왼쪽"), look) == ("look", "left")
assert driving.read(brain._norm("Down a little."), look) == ("look", "down small")
assert driving.read(brain._norm("왼쪽"), None) is None                      # no look before: not a head move
for t in ("다시", "한 번만 더.", "또 해!", "루미, 한번 더!"):
    assert driving.read(brain._norm(t), turn) == turn, t
assert driving.read(brain._norm("again again!"), move) == move
assert driving.talking([("sing", "ACTION: sing x")]) and not driving.talking([("t", "ACTION: turn left 90")])

# ---------- places said other ways (place_words) ----------
EXPO = ["home", "dock2", "booth_A", "booth_B", "booth_3", "entrance", "stage", "coffee_corner", "info_desk"]
CONF = ["home", "dock2", "Main_Stage", "Booth_12", "Registration", "포토존", "라운지", "Coffee_Bar", "Exit_B"]
KOREAN = ["home", "커피코너", "부스3", "입구", "무대", "안내데스크", "휴게실", "회의실"]
for t, mk, want in (("Go to booth bee.", EXPO, "booth_B"), ("에이 부스로 가 줘", EXPO, "booth_A"),
                    ("인포 대스크로 가 줘", EXPO, "info_desk"), ("레지스트레이션으로 가 줘", CONF, "Registration"),
                    ("부스 십이로 가 줘", CONF, "Booth_12"), ("출구 B로 가 봐", CONF, "Exit_B"),
                    ("삼 번 부스로 가", KOREAN, "부스3"), ("go to the information desk", KOREAN, "안내데스크"),
                    ("roll over to the coffee corner", KOREAN, "커피코너"), ("Would you mind heading to dock 2?", EXPO, "dock2")):
    assert [m for m in mk if brain.named_place(t, m, mk)] == [want], (t, want)
assert not [m for m in EXPO if brain.named_place("go to the booth", m, EXPO)]       # which booth: asked
assert brain.intent("go to the stage... wait, not the stage, the entrance", KOREAN) is None

# ---------- "go where I point" in many wordings (vision/pointing.asked); not a place, a negation, later ----------
from vision import pointing
for t in ("저기로 가", "저쪽으로 가 주십시오", "내 손가락 방향으로 가 줘", "루미야 저기 저쪽으로 가 줘 봐", "go there 해 줘",
          "could you go to where my finger points?", "hmm, how about you drive to where I'm pointing?",
          "please go stand over there", "저기 가서 서 있어 줄래? 응?", "robot, go over there, will ya?"):
    assert pointing.asked(t) == "there", t
for t in ("저쪽으로 가지 마", "don't go to where my finger points", "go there tomorrow", "오 분 있다가 저리로 가",
          "p3로 가", "go to the stage", "저기 가면 화장실 있어요"):
    assert pointing.asked(t) != "there", t
assert brain.intent("hey, please you move over there", OFFICE) is None          # not the 1 m back-off

print("motion words ok")
