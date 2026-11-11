"""A fully shut hand is looked at before it is called empty. Live 2026-10-30 18:26-18:30: "give me your hand", "open
your hand", the owner put a cup between the fingers, "close your hand" (AI_1 4143: the cup narrower than the belly's
closed gap, AI_1 read as on nothing), then "put the cup on the table" and "you are holding the cup" were answered
"my hand is empty". Replayed with fakes: the close counts the cup the camera saw between the open fingers, an order
that needs the hand takes a shut hand to carry and lets the torso camera decide, and a close on nothing (or the
person's hand seen after the close, 2026-10-23) stays empty. No robot.

    .venv/bin/python tests/test_hand_check.py
"""
import tempfile
import time
import types
from pathlib import Path

import no_robot                                  # noqa: F401  any connection to the robot fails the test
from assistant import lumi
from tasks import fetch

fetch.STATE_FILE = Path(tempfile.mkdtemp()) / "lumi_task.json"
OPEN = {"ai": [160.0, 489.0], "closed": False, "holding": False}
SHUT = {"ai": [4143.0, 489.0], "closed": True, "holding": False}       # the live close of 18:27:03
grip, eye, arm, moves, put = dict(OPEN), {"sees": "object"}, {"pose": "give"}, [], []
fetch.gripper.state = lambda: dict(grip)
fetch.gripper.close = lambda: grip.update(SHUT) or dict(grip)
fetch.skills.hand_sees = lambda: eye["sees"]
fetch.motion.poses = lambda: {"look": [0] * 6, "carry": [1] * 6, "give": [2] * 6}
fetch._at_pose = lambda name: arm["pose"] == name
fetch.arm_route.goto = lambda target, holding=False, **kw: moves.append((target, holding)) or arm.update(pose=target)
fetch._scene = lambda fn, *a: None                      # the owner's hand was gone: no name for it
fetch._put_down = lambda say, on=None: put.append(on)
fetch._lift_to = fetch.head_ahead = lambda *a, **k: None
L = lumi.Lumi.__new__(lumi.Lumi)
L.fetch_status = lambda: fetch.state().get("status")
B = types.SimpleNamespace(history=[])


def reset(sees, pose="give"):
    fetch._set(status="idle", step="", holding=False)
    fetch.skills._held.clear()
    fetch._last_held.clear()
    grip.clear(), grip.update(OPEN)
    eye["sees"], arm["pose"] = sees, pose
    moves.clear(), put.clear()


def routed(text):
    return lumi.route(text, ["home", "p1"], B, lambda: L.held_now(look=True))


# ---------- the cup put between the open fingers, then "close your hand" ----------
reset("object")
assert L.arm_pose("close")                                       # the camera saw it between the open fingers
assert fetch.state()["holding"] and fetch.held_name() == "something", fetch.state()
assert fetch.check_hand() and not moves                          # "go to look position": still held, nothing moved
arm["pose"] = "look"
assert fetch.check_hand() and fetch.state()["holding"]
kind, data = routed("Put the cup on the table.")                 # an order that needs the hand: looked at from carry
assert kind == "hand" and data[0][0] == "place" and data[1] is True, (kind, data)
assert moves == [("carry", True)], moves                         # slowly, as with a cup in the hand
fetch.place()
fetch._thread.join(2)
assert put == [{"name": "dining table", "colour": None}] or put == [None], put   # it went on to put it down
for t in ["You are holding the cup.", "You are holding cup.", "Look at your hand. You have a cup.", "손에 컵 있잖아"]:
    assert lumi.HAND_FULL_SAID.search(t), t
for t in ["are you holding anything?", "you are holding me back", "give me your hand", "what's in your hand"]:
    assert not lumi.HAND_FULL_SAID.search(t), t

# ---------- the cup taken out of the shut hand: the camera at carry sees it empty ----------
eye["sees"] = "empty"
assert not fetch.look_at_hand() and not fetch.state()["holding"]

# ---------- "close your hand" on nothing: empty; told "you are holding a cup": looked at, still empty ----------
reset("empty")
assert L.arm_pose("close") and not fetch.state()["holding"]
assert not fetch.check_hand() and not moves
assert routed("Put the cup on the table.")[0] != "hand" and moves == [("carry", True)]   # looked at, then empty
try:
    fetch.place()
    raise AssertionError("put down with an empty hand")
except fetch.FetchError as e:
    assert "empty" in e.args[0], e.args
assert not L.held_now(look=True)

# ---------- shut, the state forgot it, the person insists: the camera at carry finds it ----------
reset("object", pose="look")
grip.update(SHUT)
assert not fetch.check_hand() and not moves                      # from look nothing is seen there: shut = empty
assert L.held_now(look=True) and moves == [("carry", True)] and fetch.state()["holding"]
arm["pose"] = "look"                                             # still held away from carry (the next words' check)
assert fetch.check_hand() and fetch.state()["holding"]

# ---------- 2026-10-23: closed on nothing, the person's hand by the held-out fingers after the close ----------
reset("unknown")
L.arm_pose("close")
eye["sees"] = "object"
fetch._set(holding=True, status="holding")                       # a stale "holding" (no close on a seen thing)
assert not fetch.check_hand() and not fetch.state()["holding"]

# ---------- AI_1 stopped on something: held, whatever the camera says ----------
reset("empty")
grip.update(ai=[3500.0, 489.0], closed=True, holding=True)
assert fetch.check_hand() and not moves
print("hand check ok (narrow cup closed on, looked at from carry, closed on nothing, the 2026-10-23 case)")
