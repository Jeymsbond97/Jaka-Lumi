"""Come here and hand it over, the live test of 2026-10-29 19:41 replayed with fakes. "Give me a cup" with the cup in the
hand went out to a person 2 m away; "Give me here. Let's come here" was then ignored as "not to me" (the hand-over
still carried the steps of the mission before it, "move back 1 m"), and "come here" drove with the cup held out in
give. Now: the hand-over goes to the person who asked and comes to them first when they are further than
REACH_COME_M; "come here and give me" / "이리 와서 줘" comes, then hands over (empty: comes, says the hand is empty);
every drive and base turn with something held brings it to look first (fetch.drive_ready, _turn, follow). No robot.

    .venv/bin/python tests/test_come_give.py
"""
import tempfile
import types
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import brain, lumi
from tasks import fetch, follow

M = ["home", "p1", "p3", "p9"]
events, said = [], []
lumi.log = fetch.log = lambda *a: None
lumi.mouth = types.SimpleNamespace(say=lambda text, **k: said.append(text))

# ---------- the words: come, then the hand-over (EN + KO), with and without something in the hand ----------
COME_GIVE = ["come here and give me", "Come here and give it to me.", "Lumi, come here and give me", "come and give it to me",
             "Let's come here and give me.", "come over here and hand it to me", "come closer, give it to me",
             "come here and give me that", "이리 와서 줘", "루미야 이리 와서 줘", "여기 와서 주세요", "나한테 와서 그거 줘",
             "와서 줘", "이리 와서 건네 줘"]
NAMED = ["come here and give me the cup", "Come here and give me the cup.", "와서 컵 줘", "이리 와서 컵 줘",
         "come to me and give me a red cup"]
NOT = {"come here": ("quick", ("come", "")), "이리 와": ("quick", ("come", "")),
       "come here and wave": "chain", "이리 와서 손 흔들어": "chain", "come here and give me your hand": "chain",
       "don't come here and give it to me": (None, None)}
bad = []
for held in (True, False):
    for t in COME_GIVE + NAMED:
        got = lumi.route(t, M, brain.Brain(), holding=held)
        if held or t in COME_GIVE:
            ok = got == ("quick", ("come", "give"))
        else:                                       # nothing held, a thing named: come, then the pick-and-give
            ok = got[0] == "chain" and got[1][0][2] == ("come", "") and got[1][1][0] == "steps" and \
                [s["do"] for s in got[1][1][2]] == ["pick", "give"]
        if not ok:
            bad.append((held, t, got))
    for t, want in NOT.items():
        got = lumi.route(t, M, brain.Brain(), holding=held)
        if (got[0] if isinstance(want, str) else got) != want:
            bad.append((held, t, got))
assert not bad, bad

# ---------- Lumi with fakes: the person, the base, the hand ----------
lumi.arm.cmd = lambda name, **a: {"power": 1, "enable": 1}       # the arm is on (arm_off)
real_give = fetch.give
fetch.give = lambda say=None: events.append("give")
L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.markers, L.current, L.patrol, L.voice_trusted = "en", M, None, None, False
L.brain = brain.Brain()
L.modes = types.SimpleNamespace(greeter=True, patrol=True)
L.keep_listening = lambda: None
L.mission_running = lambda: False
L.skill_busy = lambda: False
L.fetch_status = lambda: "holding"
person = types.SimpleNamespace(id=5, angle=7.0, distance=1.97)  # where the live give went out from
L.vision = types.SimpleNamespace(present=lambda t: True, anyone=lambda: True)
L.speaker_track = lambda: person
come = {"to": 1.1, "result": None}


def come_to(track, say=False):
    events.append("come")
    (track or person).distance = come["to"]   # None: come_to finds the speaker itself
    return come["result"]


L.come_to = come_to
L.end_run = lambda text: events.append("end run")
hand = {"held": True}
L.held_now = lambda: hand["held"]

# the hand-over by voice goes to the person who asked: far -> comes to them first, near -> at once
for text in ["Give me a cup.", "give it to me", "hand it over", "컵 줘", "이리 줘", "나한테 주세요"]:
    for dist, patrol, want, words in ((1.97, True, ["come", "give"], []), (1.2, True, ["give"], []),
                                      (3.0, False, [], [lumi.COME_CLOSER_SAY[0]])):
        person.distance, L.modes.patrol = dist, patrol
        events.clear(), said.clear()
        assert L.hand_command(text) and events == want and said == words, (text, dist, patrol, events, said)
L.modes.patrol = True
person.distance, come["to"] = 2.5, 2.4                    # it came, but they are still too far (stepped back)
events.clear(), said.clear()
L.fetch_finish("give")
assert events == ["come"] and said == [lumi.COME_CLOSER_SAY[0]], (events, said)
person.distance, come["to"], come["result"] = 2.5, 1.1, False   # "stop" on the way: no hand-over after it
events.clear(), said.clear()
L.fetch_finish("give")
assert events == ["come"] and not said, (events, said)
come["result"] = None
person.distance = 3.0                                     # the dashboard's give: in front, as it was
events.clear()
L.fetch_finish("give", voice=False)
assert events == ["give"]
L.speaker_track = lambda: None                            # several seen, nobody raised a hand (raised_hand said so)
events.clear()
L.fetch_finish("give")
assert events == []
L.speaker_track = lambda: person

# "give me your hand" with the cup in the hand: the same hand-over, so the same come first
person.distance = 2.2
events.clear()
real_check, fetch.check_hand = fetch.check_hand, lambda: True
assert lumi.Lumi.arm_pose(L, "reach") is None and events == ["come", "give"], events
fetch.check_hand = real_check

# "come here and give me": the hand held out ends, comes, hands over; nothing held: comes, says the hand is empty
for text in COME_GIVE:
    for held, want, words in ((True, ["end run", "come", "give"], []),
                              (False, ["end run", "come"], [lumi.EMPTY_HAND_SAY["en"]])):
        hand["held"], person.distance, come["result"] = held, 2.0, None
        events.clear(), said.clear()
        assert L.quick_command(text, ("come", "give")), text
        assert events == want and said == words, (text, held, events, said)
hand["held"], come["result"] = True, False                # stopped on the way: nothing after it
events.clear(), said.clear()
L.quick_command("come here and give me", ("come", "give"))
assert events == ["end run", "come"] and not said, events
L.modes.patrol = False                                    # Greeter only: no come, said why
said.clear(), events.clear()
assert L.quick_command("이리 와서 줘", ("come", "give")) and not events and said == [lumi.BASE_OFF_SAY[0]], said
L.modes.patrol = True
fetch.give = real_give

# ---------- a hand-over is no mission: the steps of the mission before it are not carried along ----------
fetch.STATE_FILE = Path(tempfile.mkdtemp()) / "lumi_task.json"
fetch._set(status="holding", holding=True, task={"steps": [{"do": "move", "dir": "back", "m": 1.0}], "sender": None})
fetch._in_hand = lambda: True
fetch.motion.poses = lambda: {"give": [0] * 6, "look": [0] * 6}
fetch._lift_to = lambda mm: None
fetch.head_ahead = lambda: None
fetch._give = lambda say: events.append("held out") or "kept"
real_mission = lumi.Lumi.mission_running
fetch.give()
fetch._thread.join(2)
assert fetch.state()["task"] is None and not real_mission(L)
fetch._set(status="running")                              # while it is held out: still no mission (mission_talk)
assert not real_mission(L)
fetch._set(status="holding")

# ---------- every drive and turn with something held: to look first ----------
moves = []
real_pose = fetch._drive_pose
fetch._drive_pose = lambda holding=False: moves.append(holding)
fetch.stay_put = False
fetch._charging = lambda: False
fetch._waist_front = lambda: None
fetch._sweep_blocked = lambda *a, **k: True               # stops _turn after the arm (no base move in a test)
assert fetch._turn(90.0, holding=True) is False and moves == [True]   # a mission's turn after a give / carry
moves.clear()
real_ready = follow.ready
follow.ready = lambda: None
fetch.arm_yaw = lambda: None
assert follow.prepare() == [] and moves == [True]          # follow me with the cup: the held lines, holding speed
follow.ready, fetch._drive_pose = real_ready, real_pose
print(f"come give ok ({len(COME_GIVE) + len(NAMED)} wordings x held / empty, far give comes first, come and give, "
      "no stale mission, held drives to look)")
