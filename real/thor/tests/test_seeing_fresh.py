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
    hands = {s: {"position_mm": None, "distance_m": 0.8, "object": None} for s in ("left", "right")}
    if w.get("hand"):
        hands[w["hand"]]["object"] = {"name": w["thing"], "colour": w["colour"], "position_mm": None,
                                      "distance_m": 0.8, "width_mm": None}
    return {"distance_m": 1.0, "bearing_deg": 0.0, "where": "in front of me", "position_mm": None, "camera": "head",
            "facing": True, "gesture": None, "raised": w.get("raised", []), "pointing": None, "hands": hands,
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
scene.ask_vlm_hand = lambda evidence, lang="en", frames=None, side=None: None
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
    seeing._last.update(thing=None, name=None, kind=None, asked=None, parts=[], held=None, unsure=0.0, at=0.0)
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

# a question naming a hand is about that hand only, the person's own left / right (live 2026-10-23 15:34: "what about
# left hand?" with a laptop in the right and the left raised empty -> "I see a black laptop in your right hand" thrice)
LEFT_UP = r"^Your left hand is up and I don't see anything in it\.$"
world.update(START, hand="right", thing="laptop", colour="black", raised=["left"])
dialogue([("What is my hand?", None, r"black laptop in your right hand"),
          ("What about left hand?", None, LEFT_UP),
          ("What is it in my left hand?", None, LEFT_UP),
          ("What about the left one?", None, LEFT_UP),
          ("and the other hand?", None, r"^In your right hand I see a black laptop"),
          ("and this one?", None, LEFT_UP),
          ("really?", None, r"looked again.*left hand is up"),
          ("What about Inna's left hand?", {"raised": []}, r"^I don't see anything in your left hand"),
          ("What's in my right hand?", None, r"^In your right hand I see a black laptop"),
          ("No, it's my left hand.", None, r"laptop in your right hand, but I may be wrong")])   # a claim stays a claim
world.update(raised=["left"])
dialogue([("내 손에 뭐 있어?", None, r"오른손에 .*노트북"),
          ("왼손은?", None, r"^왼손을 들고 계신데"),
          ("다른 손은?", None, r"^오른손에 .*노트북"),
          ("그럼 왼손에는 뭐 있어?", None, r"^왼손을 들고 계신데"),
          ("What about 왼손?", None, r"^왼손을 들고 계신데"),                   # mixed
          ("what about the other one?", None, r"^In your right hand I see a black laptop"),
          ("그럼 left hand는?", None, r"^왼손을 들고 계신데")])
world.update(raised=[])

# nothing in the hand any more, or nobody there
world.update(START)
dialogue([("what am I holding?", None, r"left hand"),
          ("and now?", {"hand": None}, r"don't see anything in your hands"),
          ("it's in my right hand", None, r"don't see anything in your hands"),
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

# "what's in my hand" in every wording goes to the cameras (2026-10-23: "What is in my right hand?" went to the LLM)
for said in ("What is in my right hand?", "What's in my left hand?", "what is in my hand", "what's in my hand?",
             "What is my hand?", "what am I holding", "What do I have in my hand?", "what is on my hand",
             "Lumi, what's in my hand?", "내 손에 뭐 있어?", "내 오른손에 뭐 있어?", "제 왼손에 뭐 있어요?", "내가 뭐 들고 있어?",
             "내 손에 든 거 뭐야?"):
    assert next((k for k, rx in seeing.KINDS if rx.search(said)), None) == "holding", said

# a barge-in that is the echo of Lumi's own answer (sound match ~0.5, bent words) is not a new question
from audio import mouth
mouth.recent_speech = lambda s=30.0: "Let me check. It is overcast in Seoul today with temperatures between 7 and 19 degrees."
assert lumi.Lumi.own_echo("So today, with temperature, it's been", share=lumi.ECHO_LIKELY_SHARE)
assert lumi.Lumi.own_echo("The school is over.", share=lumi.ECHO_LIKELY_SHARE)
assert not lumi.Lumi.own_echo("What about Busan?", share=lumi.ECHO_LIKELY_SHARE)
assert not lumi.Lumi.own_echo("Look it up.", share=lumi.ECHO_LIKELY_SHARE)

# "what am I holding" tries hard before giving up: fresh looks until two agree, the colour steady across questions,
# then the close look (gemma4 on the hand picture), then a request for a hint and a new look after it (2026-10-23 live:
# a phone found only sometimes, a laptop "I can't tell" 4-5 times, a yellow cup "white" then "yellow")
def person(right=None, something=None):
    """A person in front whose right hand holds `right` ((name, colour, score) or None)."""
    obj = right and {"name": right[0], "colour": right[1], "score": right[2], "position_mm": None, "distance_m": 0.8,
                     "width_mm": None}
    hand = {"position_mm": None, "distance_m": 0.8, "object": obj, "something": something or {"colour": None, "share": 0}}
    return {"hands": {"right": hand, "left": {**hand, "object": None, "something": {"colour": None, "share": 0}}},
            "raised": [], "posture": None}


def held(views, said="what am I holding?", vlm=None, hint=None):
    """The answer when the first look sees views[0] and each new look (more()) the next; also the close look's words
    and what Lumi said before it."""
    views, spoken, asked_vlm = list(views), [], []
    scene.person_in_front = lambda frames: frames[0]["p"]
    scene.ask_vlm_hand = lambda evidence, lang="en", frames=None, side=None: asked_vlm.append(evidence) or vlm
    more = lambda: [{"p": views.pop(0)}] if views else None
    got = seeing._held_answer([{"p": views.pop(0)}], "en", None, more, spoken.append, hint)
    return got, spoken, asked_vlm


seeing._last.update(held=None, unsure=0.0)
PHONE = ("cell phone", "black", 0.22)                                    # a weak box: true only when two looks agree
got, spoken, _ = held([person(PHONE), person(PHONE)])
assert got == "You're holding a black cell phone in your right hand." and not spoken, got
got, spoken, ev = held([person(PHONE), person(), person()], vlm="UNSURE")
assert spoken == ["Let me look closely."] and "cell phone (score 0.22" in ev[0], (spoken, ev)
assert got == "It might be a black cell phone in your right hand, but I'm not sure. Could you turn it toward me, or " \
              "tell me what it is?", got
got, _, _ = held([person(), person(), person()], hint="phone", vlm=None)
assert got == "I still can't make it out well, so I'll take your word: it's a phone.", got
got, _, _ = held([person(("cell phone", "black", 0.5))], hint="phone")
assert got.startswith("Yes, now I see it: a black cell phone"), got
LAPTOP = ("laptop", "grey", 0.6)
got, spoken, _ = held([person(), person(), person(LAPTOP)])               # found on the third look: no close look
assert got == "You're holding a grey laptop in your right hand." and not spoken, got
got, spoken, ev = held([person(something={"colour": "green", "share": 0.6})] * 3, vlm="You're holding a green ball.")
assert got == "You're holding a green ball." and "something green" in ev[0], (got, ev)
got, _, _ = held([person(something={"colour": "green", "share": 0.6})] * 3, vlm=None)
assert got.startswith("I see something green in your right hand, but I can't tell what it is. Could you turn"), got
got, spoken, _ = held([person()] * 3)                                    # depth at the hands, nothing there
assert got == "I don't see anything in your hands." and not spoken, got

seeing._last.update(held=None)                                           # the colour stays steady ...
assert held([person(("cup", "yellow", 0.8))])[0].endswith("a yellow cup in your right hand.")
assert held([person(("cup", "white", 0.8)), person(("cup", "yellow", 0.8))])[0].endswith("a yellow cup in your right hand.")
assert held([person(("cup", "white", 0.8)), person(("cup", "orange", 0.8)), person(("cup", "yellow", 0.8))])[0] \
    .endswith("a yellow cup in your right hand.")
assert held([person(("cup", "white", 0.8)), person(("cup", "white", 0.8))])[0].endswith("a white cup in your right hand.")
seeing._last["held"]["at"] -= seeing.STEADY_S + 1                       # ... for STEADY_S, then a new look decides
assert held([person(("cup", "yellow", 0.8))])[0].endswith("a yellow cup in your right hand.")
                                                                         # the model is told the same colour
assert seeing._steady({"name": "cup", "colour": "white"})["colour"] == "yellow"

for said, want in (("it's my wallet", "wallet"), ("이거 지갑이야", "지갑"), ("no, it's a phone", "phone"),
                   ("it's my right hand", None), ("okay", None), ("제가 서 있나요 앉아 있나요?", None)):
    assert seeing._hint(said) == want, (said, seeing._hint(said))

print("seeing fresh ok")
