"""Self-check of distances and speed by voice (assistant/driving.py, brain.intent's moves, fetch's straight move and
speed) with a fake base, no robot: python tests/test_driving.py"""
import tempfile
import threading
import time
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import brain, driving
from manipulation import skills
from tasks import fetch

fetch.head_ahead = lambda: None                    # never the real head
M = ["home", "p9"]
read = lambda text, last=None, talking=False: driving.read(brain._norm(text), last, talking)

# ---------- exact amounts: digits, words, units, Korean, mixed, whisper's slips ----------
EXACT = {
    "Let's come back to 20 cm.": "back 0.2", "come back 20 cm": "back 0.2", "go forward 30 cm": "forward 0.3",
    "move back 5 centimeters": "back 0.05", "move back 5 centimetres": "back 0.05", "go back 1 cm": "back 0.01",
    "move back 10 mm": "back 0.01", "move back 250 millimeters": "back 0.25", "go back 1 meter": "back 1",
    "move forward one point five meters": "forward 1.5", "move back fifteen centimetres": "back 0.15",
    "back up two hundred millimetres": "back 0.2", "go back twenty five centimeters": "back 0.25",
    "move back half a meter": "back 0.5", "reverse half a metre": "back 0.5", "move left 40 cm": "left 0.4",
    "go right 1 meter": "right 1", "Let's bake 20 cm.": "back 0.2", "big 30 centimeters": "back 0.3",
    "go back 2 metals": "back 2", "Let's bake one metal.": "back 1", "Big one meter.": "back 1",
    "20센티 뒤로": "back 0.2", "20센티 뒤로 가 줘": "back 0.2", "앞으로 반 미터": "forward 0.5", "앞으로 반 미터 가": "forward 0.5",
    "이십 센티 뒤로 가": "back 0.2", "일 미터 앞으로 가": "forward 1", "뒤로 오십 센치만 가 줘": "back 0.5",
    "루미야 뒤로 삼십 센티 가": "back 0.3", "뒤로 백 센티 가": "back 1", "뒤로 10 cm 가": "back 0.1", "back 20센티": "back 0.2",
    "왼쪽으로 50센티 가": "left 0.5", "1미터 50센치 뒤로 가": "back 1.5", "뒤로 2미터 가 줘": "back 2",
}
VAGUE = {   # a fixed estimate (driving.TINY_M, SPAN_M, STEP_M, LITTLE_M), read back with "about"
    "back up a tiny bit": "back 0.05", "a hair to the left": "left 0.05", "inch forward": "forward 0.05",
    "scoot back just a touch": "back 0.05", "move back a few centimetres": "back 0.05", "살짝 뒤로": "back 0.05",
    "살짝만 앞으로 가 줘": "forward 0.05", "한 뼘 앞으로": "forward 0.2", "반 걸음 뒤로": "back 0.25",
    "한 걸음 뒤로 가": "back 0.5", "두 걸음 앞으로": "forward 1", "two steps back": "back 1",
    "take a step forward": "forward 0.5", "half a step back": "back 0.25", "go back a little": "back 0.5",
    "뒤로 조금 가 줘": "back 0.5", "scooch back a bit": "back 0.5",
}
for text, want in {**EXACT, **VAGUE}.items():
    got = read(text)
    assert got == ("move", want, text in EXACT), (text, got)
    assert brain.intent(text, M) == ("move", want), (text, brain.intent(text, M))

# ---------- not understood: asked; too far / too short: refused with the limit; never a default ----------
for text in ["move back 20", "go back a couple of meters", "move back a few steps", "move forward 2 feet",
             "go back several metres", "뒤로 20 가"]:
    assert read(text)[0] == "ask" and brain.intent(text, M) is None, (text, read(text))
for text in ["move back 5 meters", "go forward 2 km", "drive back three miles", "뒤로 5미터 가", "앞으로 천 미터 가",
             "move back 1 mm", "go back 3.5 m", "앞으로 삼 킬로미터 가"]:
    assert read(text)[0] == "refuse" and brain.intent(text, M) is None, (text, read(text))
assert read("go back 3 m") == ("move", "back 3", True) and read("go back 3 km") == ("refuse", "back 3000")
assert driving.say_refused("back", 5) == "Sorry, I can only drive up to 3 metres at a time."
assert driving.say_ask("back") .startswith("How far should I go back?")

# ---------- places, the head, objects, talk: what they are ----------
assert brain.intent("come back here", M) == ("come", "") and read("come back here") is None
assert brain.intent("come back to p9", M) == ("go_to", "p9") and read("come back to p9") is None
assert brain.intent("come back p9", M) == ("go_to", "p9")
assert brain.intent("look left a bit", M) == ("look", "left small") and read("look left a bit") is None
assert brain.intent("move the cup to the left", M)[0] == "move_object"
for text in ["go right ahead", "I live a few metres to the left", "I'll be right back", "that's right", "go back home",
             "turn right", "you were right", "컵을 살짝 왼쪽으로"]:
    got = brain.intent(text, M)
    assert read(text) is None and (got is None or got[0] != "move"), (text, got, read(text))

# ---------- speed: whole sentences, EN / KO / mixed ----------
FASTER = ["go a bit faster", "faster", "speed up", "a little faster please", "can you pick up the pace", "even faster",
          "way too slow", "hurry up Lumi", "you're too slow", "faster!", "빨리", "더 빨리", "좀 더 빨리 가 줘", "너무 느려",
          "속도 좀 높여", "faster 좀"]
SLOWER = ["slower", "slow down", "a bit slower", "too fast", "not so fast", "ease off", "slow it down a notch",
          "Lumi, slow down please", "go slower", "천천히", "더 천천히", "속도 줄여", "너무 빨라", "좀 천천히 가 줄래요",
          "천천히 가세요", "go slower 좀"]
for text in FASTER:
    assert read(text) == ("speed", 1), (text, read(text))
for text in SLOWER:
    assert read(text) == ("speed", -1), (text, read(text))
for text in ["how fast can you go?", "빨리 와", "I'm a slow reader", "slow and steady wins the race", "take it easy",
             "the internet is slow today", "go back 20 cm"]:
    assert driving.speed(brain._norm(text)) == 0, text

# ---------- "more" / "again" right after a move or a speed change; with nothing before: asked ----------
moved = driving.last_command([("go back 20 cm", "ACTION: move back 0.2")])
sped = driving.last_command([("faster", "ACTION: speed 1\nOkay, a bit faster.")])
slowed = driving.last_command([("천천히", "ACTION: speed -1\n네.")])
assert moved == ("move", "back 0.2", True) and sped == ("speed", 1) and slowed == ("speed", -1)
for text in ["again", "a bit more", "more", "same again", "one more time", "once more", "한 번 더", "조금 더", "더", "똑같이 해"]:
    assert read(text, moved) == moved, (text, read(text, moved))
    assert read(text, sped) == ("speed", 1) and read(text, slowed) == ("speed", -1), text
    assert read(text) == ("ask", "") and read(text, None, talking=True) is None, text   # after talk: the conversation's
assert read("less", sped) == ("speed", -1) and read("less", moved) is None
assert read("just a few centimetres more", moved) == ("move", "back 0.05", False)
assert read("10센티 더", moved) == ("move", "back 0.1", True) and read("20 cm more", moved) == ("move", "back 0.2", True)
assert read("a hair to the left", moved) == ("move", "left 0.05", False)          # its own direction
assert driving.last_command([("hi", "ACTION: none -\nHello!")]) is None and driving.talking([("hi", "ACTION: none -\nHi")])
assert not driving.talking([]) and not driving.talking([("go back 20 cm", "ACTION: move back 0.2")])

# ---------- what Lumi says ----------
assert driving.say_move("back", 0.2, True) == "Okay, moving back 20 centimetres."
assert driving.say_move("back", 0.05, False) == "Okay, moving back about 5 centimetres."
assert driving.say_move("forward", 1.5, True, "ko") == "네, 앞으로 1.5미터 갈게요."
assert driving.say_move("back", 0.01, True) == "Okay, moving back 1 centimetre."

# ---------- the speed: steps, limits, navigation never above its own speed ----------
tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"                                    # never the real /dev/shm file
sent = []
real_request = fetch.agv.request
fetch.agv.request = lambda cmd, timeout=3.0: sent.append(cmd) or {}
f = 1.0
for _ in range(10):
    f = fetch.set_speed(f + fetch.SPEED_STEP)
assert f == fetch.SPEED_MAX and not sent, sent                               # faster: navigation stays at its own
for _ in range(10):
    f = fetch.set_speed(f - fetch.SPEED_STEP)
assert f == fetch.SPEED_MIN and sent[-1].startswith(f"/api/set_params?max_speed_linear={fetch.NAV_SPEED_MPS * 0.4:g}")
assert all(float(c.split("=")[1].split("&")[0]) <= fetch.NAV_SPEED_MPS for c in sent)
f = fetch.set_speed(1.0)
assert sent[-1].startswith(f"/api/set_params?max_speed_linear={fetch.NAV_SPEED_MPS:g}") and f == 1.0
sent.clear()                                         # every navigation move sends the speed first: the base forgets it
real_status = fetch.agv.status                       # at its restart (0.3 m/s of its own, 2026-10-28)
fetch.agv.status = lambda: {"move_status": "idle"}
fetch.agv.request = lambda cmd, timeout=3.0: sent.append(cmd) or {"status": "FAIL"}
fetch.agv.go("p1")
assert sent == [f"/api/set_params?max_speed_linear={fetch.NAV_SPEED_MPS:g}&max_speed_angular={fetch.NAV_TURN_RADS:g}",
                "/api/move?marker=p1"], sent
fetch.agv.status = real_status
fetch.agv.request = lambda cmd, timeout=3.0: sent.append(cmd) or {}
assert driving.say_speed(1, 1.2, True) == "Okay, a bit faster: 120 percent of my normal speed."
assert driving.say_speed(1, fetch.SPEED_MAX, False) == "I'm already at my top speed."

# ---------- a 1 cm move is driven, and the last joy_control command lasts only the time left ----------
# a fake base (heading 0): its x follows the joy_control speed, each command for JOY_HOLD_S; no wheels: it stays
base = {"x": 0.0, "v": 0.0, "t": time.time(), "wheels": True}


def roll():
    now = time.time()
    dt, base["t"] = now - base["t"], now
    if base["wheels"]:
        base["x"] += base["v"] * min(dt, fetch.JOY_HOLD_S)
    if dt > fetch.JOY_HOLD_S:
        base["v"] = 0.0


def joy_request(cmd, timeout=3.0):
    if "joy_control" in cmd:
        roll()
        base["v"] = float(cmd.split("linear_velocity=")[1].split("&")[0])
        joy.append((time.time(), cmd))
    return {}


fetch.agv.pose = lambda: (roll(), (base["x"], 0.0, 0.0))[1]
fetch.agv.clearance = lambda x, y: 5.0
fetch._waist_front = lambda: None
real_moved, skills.moved = skills.moved, lambda after=0.0: None
joy = []
fetch.agv.request = joy_request
for dist in (0.01, 0.03, 0.07, 0.37):
    joy.clear()
    t0 = time.time()
    got = fetch._straight_clear(-dist, lambda: fetch.AXIS_SPEED)
    secs = joy[-1][0] - t0                                                   # until the stop command
    assert abs(got - dist) < 1e-6, (dist, got)
    assert abs(secs - dist / fetch.AXIS_SPEED) < 0.05, (dist, secs)        # no extra 0.1 s at the end
    assert joy[-1][1].endswith("linear_velocity=0&angular_velocity=0") and "-0.050" in joy[0][1], joy
# the speed read again while driving: a change applies to the move running now
joy.clear()
speeds = iter([0.1] * 3 + [0.2] * 100)
fetch._straight(0.05, lambda: next(speeds))
assert any("0.100" in c for _, c in joy) and any("0.200" in c for _, c in joy), joy

# _move: pieces down to the last centimetre, short moves at AXIS_SPEED, longer ones at MOVE_SPEED x speed_factor
fetch._pose, fetch._look, fetch._lift_to, fetch.line_hits = (lambda *a, **k: None), (lambda: "look"), \
    (lambda mm: None), (lambda d: None)
fetch._charging = lambda: False
for m, v in ((0.01, "-0.050"), (0.3, "-0.120")):
    joy.clear()
    fetch.speed_factor = 1.2
    fetch._move("back", m, holding=False)
    vel = {c.split("linear_velocity=")[1].split("&")[0] for _, c in joy} - {"0"}
    assert vel == {v}, (m, vel)
fetch.speed_factor = 1.0

# _move rolls on between its pieces (no stop-and-go), the time spent checking counted as driven: 0.8 m is 0.8 m
STOP = "linear_velocity=0&angular_velocity=0"
fetch.MOVE_SPEED = 0.5
real_line_hits = fetch.line_hits
fetch.line_hits = lambda d: time.sleep(0.15)                                  # a slow check of the arm's way
joy.clear()
x0 = base["x"]
fetch._move("back", 0.8, holding=False)
time.sleep(fetch.JOY_HOLD_S + 0.05)
roll()
stops = [k for k, (_, c) in enumerate(joy) if c.endswith(STOP)]
assert stops == [len(joy) - 1], stops                                         # one stop: at the end
assert abs((x0 - base["x"]) - 0.8) < 0.03, x0 - base["x"]
assert fetch._rolling["v"] == 0.0

# the base does not follow the commands (2026-10-23: a follow loop sent its own): said, stopped, never "done"
base["wheels"] = False
joy.clear()
try:
    fetch._move("back", 1.0, holding=False)
    raise AssertionError("a move the base did not drive ended as done")
except fetch.FetchError as e:
    assert "did not move" in e.args[0] and "0.00 m of 1" in e.args[0], e.args
assert joy[-1][1].endswith(STOP) and fetch._rolling["v"] == 0.0, joy[-3:]
base["wheels"] = True

# something steps into the way after the first piece: stops at once (also while rolling), says how far it got
clear_at = {"x": base["x"] - 0.3}
fetch.agv.clearance = lambda x, y: 5.0 if x > clear_at["x"] else 0.1
joy.clear()
try:
    fetch._move("back", 1.0, holding=False)
    raise AssertionError("drove into an obstacle")
except fetch.FetchError as e:
    assert "in my way" in e.args[0], e.args
time.sleep(fetch.JOY_HOLD_S + 0.05)
assert base["x"] > clear_at["x"] and joy[-1][1].endswith(STOP), (base, clear_at)   # stopped before it
fetch.agv.clearance = lambda x, y: 5.0
fetch.line_hits = real_line_hits
fetch.agv.request, skills.moved = real_request, real_moved

# a task (a move by voice) ends a follow that runs first: two joy_control senders must never fight
from tasks import follow
follow._stop.clear()
follow._thread = threading.Thread(target=follow._stop.wait, daemon=True)
follow._thread.start()
follow._joy = lambda v, w: None
fetch._launch(lambda: None)
assert not follow.running() and follow._stop.is_set()
fetch._thread.join(1.0)
# "again" / "a bit more" right after a turn (2026-10-21)
_turn = driving.last_command([("turn left", "ACTION: turn left 90")])
assert _turn == ("turn", "left 90"), _turn
for _t, _want in {"again": ("turn", "left 90"), "한 번 더": ("turn", "left 90"), "one more time": ("turn", "left 90"),
                  "a bit more": ("turn", "left 15"), "조금 더": ("turn", "left 15")}.items():
    assert driving.read(brain._norm(_t), _turn) == _want, (_t, driving.read(brain._norm(_t), _turn))
assert driving.read("a bit more", ("turn", "around 180")) == ("ask", "")
print("driving: all self-checks passed")
