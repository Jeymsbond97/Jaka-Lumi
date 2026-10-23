"""Self-check: every seeing answer, follow-up ("really?", "and now?", "다시 봐") and correction ("it's white",
"no, it's in my right hand", "아니야 흰색이야") is answered from a new look taken after the words, never from what was
said before; a correction is agreed with only when the camera sees it so. Fake cameras whose world changes between
turns; no robot, no LLM.  python tests/test_seeing_fresh.py
"""
import json
import re
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

from assistant import brain, lumi, seeing
from vision import camview, objects, scene

MARKS = ["home", "dock2", "p1", "p2", "p3", "p4", "p5"]
world = {}                       # what is in front of the fake cameras now; the test changes it between turns
looks = []                       # (since, frame number) of every snapshot asked for


def snapshot(cameras=scene.CAMERAS, since=None):
    assert since is not None and since <= time.time(), "a look must be taken after the question"
    looks.append((since, len(looks)))
    return [{"camera": "head", "n": len(looks)}]


def _now(frames):
    assert frames[0]["n"] == len(looks), "answered from an older look"
    return world


def person_in_front(frames=None):
    w = _now(frames)
    if not w.get("person", True):
        return None
    hands = {s: {"position_mm": None, "object": None} for s in ("left", "right")}
    if w.get("hand"):
        hands[w["hand"]]["object"] = {"name": w["thing"], "colour": w["colour"], "position_mm": None,
                                      "distance_m": 0.8, "width_mm": None}
    return {"distance_m": 1.0, "bearing_deg": 0.0, "where": "in front of me", "position_mm": None, "camera": "head",
            "facing": True, "gesture": None, "raised": [], "pointing": None, "hands": hands,
            "clothes": {"upper": w.get("upper"), "lower": w.get("lower"), "feet": None}}


def object_in_hand(frames=None):
    w = _now(frames)
    if not w.get("hand"):
        return None
    return {"name": w["thing"], "colour": w["colour"], "hand": w["hand"], "position_mm": None, "distance_m": 0.8,
            "width_mm": None}


real_snapshot = scene.snapshot
scene.snapshot = snapshot
scene.person_in_front = person_in_front
scene.object_in_hand = object_in_hand
scene.person_holds = lambda obj=None, frames=None: bool(_now(frames).get("hand"))
scene.people = lambda frames=None: [{}] if _now(frames).get("person", True) else []
scene.ask_vlm = lambda q, lang="en", frames=None: "VLM"
scene.things = lambda frames=None: []


def lang_of(text):
    return "ko" if re.search(r"[가-힣]", text) else "en"


def say(text):
    """What lumi.answer() does with the words: lumi.route with seeing.answer first; "llm" when it goes on to the model."""
    b = brain.Brain()
    kind, data = lumi.route(text, MARKS, b, seen=lambda x: seeing.answer(x, lang_of(x)))
    return data if kind == "seeing" else "llm"


def dialogue(turns):
    """turns: (words, world change before them or None, regex the answer must match; "llm": not a seeing answer)."""
    seeing._last.update(thing=None, name=None, kind=None, asked=None, parts=[], at=0.0)
    for words, change, want in turns:
        if change:
            world.update(change)
        n = len(looks)
        t = time.time()
        got = say(words)
        if want == "llm":
            assert got == "llm", f"{words!r} -> {got!r} (want the conversation model)"
            continue
        assert got != "llm" and re.search(want, got, re.I), f"{words!r} -> {got!r} (want {want!r})"
        assert len(looks) > n and looks[-1][0] >= t, f"{words!r}: answered without a new look"


START = {"person": True, "hand": "left", "thing": "cell phone", "colour": "grey", "upper": "white", "lower": "black"}

# the owner's live dialogues of 2026-10-22
world.update(START)
dialogue([("What is my hand?", None, r"grey cell phone in your left hand"),
          ("What about now?", {"hand": "right"}, r"looked again.*right hand"),
          ("and now?", {"hand": "left"}, r"looked again.*left hand"),
          ("Right now.", {"hand": "right"}, r"right hand"),
          ("No, it's my left hand.", None, r"^I see .* in your right hand, but I may be wrong"),
          ("It's in the right.", None, r"^Yes, I see a grey cell phone in your right hand"),
          ("Look at the again. It's not right hand. It's the left hand.", {"hand": "left"}, r"^Yes, .*left hand"),
          ("So, where is it now?", {"hand": "right"}, r"right hand"),
          ("Left hand.", None, r"right hand, but I may be wrong")])

world.update(START)
dialogue([("What is the color of my t-shirt?", {"upper": "blue"}, r"t-shirt looks blue"),
          ("Is it really blue?", {"upper": "white"}, r"^Looking again, your t-shirt looks white, not blue"),
          ("really?", None, r"looked again.*white"),
          ("are you sure?", {"upper": "blue"}, r"looked again.*blue"),
          ("No, it's white.", None, r"still sees your t-shirt as blue, but I may be wrong"),
          ("it's white", {"upper": "white"}, r"^Yes, your t-shirt looks white"),
          ("It's grey.", None, r"looks white; in this light it may well be grey"),
          ("look again", {"upper": "blue"}, r"looked again.*blue")])

world.update(START)
dialogue([("Okay, what's the color of my pants?", {"lower": "blue"}, r"pants look blue"),
          ("Is that blue?", {"lower": "black"}, r"^Looking again, your pants look black, not blue"),
          ("No, it's not blue.", None, r"^You're right, .*pants look black"),
          ("What is the color of the pants?", None, r"pants look black"),
          ("what about my blue jeans?", None, r"jeans look black"),
          ("is white your favourite colour?", None, "llm")])

world.update(START)
dialogue([("내 티셔츠 무슨 색이야?", {"upper": "blue"}, r"티셔츠는 파란색"),
          ("아니야 흰색이야", None, r"파란색으로 보여요. 조명 때문에 틀릴 수도"),
          ("다시 봐", {"upper": "white"}, r"다시 봤어요.*흰색"),
          ("진짜?", None, r"다시 봤어요.*흰색"),
          ("흰색 맞지?", None, r"^네, .*흰색"),
          ("내 손에 뭐 있어?", None, r"왼손에 .*휴대폰"),
          ("지금은?", {"hand": "right"}, r"다시 봤어요.*오른손"),
          ("이제는?", {"hand": "left"}, r"다시 봤어요.*왼손"),
          ("오른손이야", None, r"왼손에 휴대폰이 보여요. 틀릴 수도"),
          ("오른손 아니고 왼손이야", None, r"^네, 왼손에"),
          ("What about now?", {"hand": "right"}, r"looked again.*right hand"),     # mixed: the answer in their language
          ("그럼 지금은?", {"hand": "left"}, r"다시 봤어요.*왼손")])

world.update(START)
dialogue([("Can you see me?", {"person": False}, r"can't see you"),
          ("What about now?", {"person": True}, r"looked again.*yes, i can see you"),
          ("Lumi, look at the left side.", None, "llm")])                     # a head turn, not a seeing follow-up

# nothing in the hand any more, or nobody there
world.update(START)
dialogue([("what am I holding?", None, r"left hand"),
          ("and now?", {"hand": None}, r"don't see anything I can recognise in your hands"),
          ("it's in my right hand", None, r"don't see anything I can recognise in your hands"),
          ("what about now?", {"person": False}, r"can't see you")])

# no follow-up without a seeing answer just before; an order is never a correction
world.update(START)
dialogue([("what time is it now?", None, "llm"), ("really?", None, "llm")])
dialogue([("what am I holding?", None, r"left hand"), ("put it in my right hand", None, "llm")])

# the conversation model gets a new look too right after a seeing answer
seeing._last["at"] = time.time()
n = len(looks)
assert seeing.facts_for("tell me a joke").startswith(" Your cameras see now") and len(looks) == n + 1
seeing._last["at"] = 0.0
assert seeing.facts_for("tell me a joke") == ""

# one word while Lumi still talks: a barge-in only right after a seeing answer (lumi.barge_in)
seeing._last.update(kind=None, at=0.0)
assert not seeing.recheck("Really?")
seeing._last.update(kind="shirt", at=time.time())
assert all(seeing.recheck(w) for w in ("Really?", "진짜?", "Now?", "정말?", "지금은?", "are you sure?"))
assert not any(seeing.recheck(w) for w in ("yes", "okay", "thanks", "what time is it?"))
seeing._last.update(at=time.time() - seeing.RECHECK_S - 1)
assert not seeing.recheck("Really?")

# colour naming: the hand's skin is not the held thing's colour; near-black has no hue (black trousers read "blue")
SKIN = (110, 140, 200)                                             # BGR of a face / hand
hsv = cv2.cvtColor(np.uint8([[SKIN]]), cv2.COLOR_BGR2HSV)[0, 0]
skin = (float(hsv[0]), float(hsv[1]))
phone_in_hand = np.array([SKIN] * 40 + [(128, 128, 128)] * 60, np.uint8)
assert objects.colour_name(phone_in_hand) != "grey" and scene._thing_colour(phone_in_hand, skin) == "grey"
assert scene._thing_colour(np.array([(0, 120, 255)] * 80 + [SKIN] * 20, np.uint8), skin) == "orange"   # an orange thing
assert objects.colour_name(np.array([(48, 36, 30)] * 100, np.uint8)) == "black"                   # V 48, S 96
assert objects.colour_name(np.array([(90, 50, 35)] * 100, np.uint8)) == "blue"                    # jeans, V 90

# scene.snapshot(since): a detection made before the question is not "now", one after it is (files faked)
tmp = Path(tempfile.mkdtemp())
cv2.imwrite(str(tmp / "raw.jpg"), np.zeros((8, 8, 3), np.uint8))
camview.want = lambda c: None
camview.raw_path = lambda c: tmp / "raw.jpg"
camview.det_path = lambda c: tmp / f"det_{c}.json"
camview.depth = lambda c, max_age=None: None
camview.intrinsics = lambda c: None
scene._transform = lambda c, d: None
scene.SINCE_WAIT_S = 0.3
asked = time.time()
(tmp / "det_head.json").write_text(json.dumps({"time": asked - 0.5, "people": [], "objects": []}))
assert real_snapshot(("head",), since=asked) == []
assert len(real_snapshot(("head",))) == 1                         # without `since`: anything under FRESH_S
(tmp / "det_head.json").write_text(json.dumps({"time": time.time(), "people": [], "objects": []}))
assert len(real_snapshot(("head",), since=asked)) == 1

print("seeing fresh ok")
