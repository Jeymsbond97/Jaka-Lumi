"""Self-check: questions about a person's looks (glasses, hat, mask, bag, hair, the kind and pattern of clothes, what
they do, who is closest, "what about her?") answered at once from the looks (seeing.norm_looks / scene_looks) and
the measured colours, EN and KO; "really?" asks for a new look; the VLM's JSON normalised; questions about Lumi left
alone. Fake people, no robot, no VLM.  python tests/test_seeing_people.py
"""
import re

from assistant import seeing
from vision import scene

ME = {"top": "red", "bottom": "black", "top_type": "hoodie", "bottom_type": "jeans", "hair": "long brown",
      "glasses": True, "hat": "black cap", "mask": False, "bag": "blue backpack", "action": "looking at a phone",
      "pattern": "striped"}
HER = {"top": "blue", "hair": "short black", "glasses": False, "hat": None, "action": "waving"}


def person(bearing, dist, clothes, looks):
    return {"camera": "head", "box": [0, 0, 1, 1], "distance_m": dist, "bearing_deg": bearing, "position_mm": None,
            "facing": True, "raised": [], "pointing": None, "gesture": None, "posture": "standing",
            "clothes": clothes, "hands": {"left": {"object": None, "distance_m": dist},
                                          "right": {"object": None, "distance_m": dist}},
            "seen": 17, "where": scene.where(bearing), "looks": looks}


world = {"people": []}
scene._persons = lambda frames=None: world["people"]
scene.people = lambda frames=None: [{"distance_m": p["distance_m"], "bearing_deg": p["bearing_deg"], "camera": "head"}
                                    for p in sorted(world["people"], key=lambda p: p["distance_m"])]
scene.things = lambda frames=None: []
scene.ask_vlm = lambda *a, **k: None
scene.ask_vlm_person = lambda *a, **k: (_ for _ in ()).throw(AssertionError("the VLM asked in a test"))
FRAMES = [{"camera": "head"}]


def setup(me=ME, her=HER, her_nearer=False):
    world["people"] = [person(0.0, 1.0, {"upper": me.get("top"), "lower": me.get("bottom"), "feet": None},
                              seeing.scene_looks(me))]
    if her:
        world["people"].append(person(30.0, 0.8 if her_nearer else 2.0, {"upper": her.get("top"), "lower": None,
                                                                          "feet": None}, seeing.scene_looks(her)))


def ask(text):
    lang = "ko" if re.search(r"[가-힣]", text) else "en"
    return seeing.answer(text, lang, FRAMES)


CASES = [   # (question, regex the answer must match; None: not a seeing question)
    ("am I wearing glasses?", r"^Yes, you're wearing glasses"),
    ("do I have sunglasses on?", r"glasses, not sunglasses"),
    ("Lumi, am I wearing a hat?", r"^Yes.*black cap"),
    ("what colour is my cap?", r"black cap"),
    ("do I have a bag?", r"^Yes.*blue backpack"),
    ("am I wearing a mask?", r"^No, I don't see a mask"),
    ("what colour is my hair?", r"hair looks brown"),
    ("is my hair short?", r"^No, your hair looks long"),
    ("is my hair long?", r"^Yes, your hair looks long"),
    ("describe me", r"red hoodie.*black jeans.*long brown hair.*glasses"),
    ("what do I look like?", r"red hoodie"),
    ("who is closest to you?", r"^You are, about 1 metre"),
    ("am I wearing a jacket?", r"^No, you're wearing a red hoodie"),
    ("am I wearing a hoodie?", r"^Yes, you're wearing a red hoodie"),
    ("am I wearing jeans?", r"^Yes, you're wearing black jeans"),
    ("am I wearing a blue hoodie?", r"^No, you're wearing a red hoodie"),
    ("is my shirt striped?", r"hoodie looks striped"),
    ("what am I wearing?", r"red hoodie and black jeans"),
    ("what am I doing?", r"looking at a phone"),
    ("is she wearing glasses?", r"^No, they're not wearing glasses"),
    ("what colour is her hair?", r"^Their hair looks black"),
    ("안경 썼어?", r"^네, 안경을 쓰고"),
    ("안경 쓰셨나요?", r"^네, 안경을"),
    ("모자 쓰고 있어요?", r"검은색 모자를 쓰고"),
    ("가방 메고 있습니까?", r"파란색 백팩을 메고"),
    ("마스크 썼어?", r"^아니요, 마스크는 안 보여요"),
    ("내 머리 무슨 색이야?", r"갈색 머리"),
    ("머리 길어?", r"^네, 머리가 길어"),
    ("제 머리 짧아요?", r"^아니요, 머리가 길어"),
    ("나 어떻게 생겼어?", r"빨간색 후드티.*갈색 머리"),
    ("누가 제일 가까워?", r"손님이 제일 가까워요"),
    ("청바지 입었어?", r"^네, 검은색 청바지를 입고"),
    ("자켓 입고 있어요?", r"^아니요, 빨간색 후드티를 입고"),
    ("내가 뭐 입었어?", r"빨간색 후드티에 검은색 청바지"),
    ("내가 지금 뭐 하고 있어?", r"휴대폰을 보고 계세요"),
    ("그분 머리 무슨 색이에요?", r"검은 머리"),
    ("셔츠에 무늬 있어?", r"줄무늬"),
    ("루미 머리 무슨 색이야?", None),
    ("are you wearing glasses?", None),
    ("what colour is your hair?", None),
    ("머리 돌려", None),
    ("I need a new hat", None),
]

setup()
bad = 0
for q, want in CASES:
    seeing._last.update(kind=None, asked=None)
    got = ask(q)
    ok = got is None if want is None else bool(got and re.search(want, got))
    if not ok:
        bad += 1
        print(f"FAIL {q!r} -> {got!r} (want {want!r})")

# follow-ups: "what about her?" / "그 사람은?" ask the same about the other person; "and me?" back
seeing._last.update(kind=None, asked=None)
assert re.search(r"^Yes, you're wearing glasses", ask("am I wearing glasses?"))
assert re.search(r"^No, they're not wearing glasses", ask("what about her?")), seeing._last
assert re.search(r"^Yes, you're wearing glasses", ask("and me?"))
seeing._last.update(kind=None, asked=None)
assert re.search(r"갈색 머리", ask("내 머리 무슨 색이야?"))
assert re.search(r"^그분은 검은 머리", ask("그 사람은?"))
seeing._last.update(kind=None, asked=None)
assert re.search(r"looking at a phone", ask("what am I doing?"))
assert re.search(r"^They're standing.*waving", ask("what about her?"))

# someone else nearer than the speaker
setup(her_nearer=True)
seeing._last.update(kind=None, asked=None)
assert re.search(r"person on my left in a blue top is closest", ask("who is closest?"))

# "really?" after a looks answer: a new look (the scene changed: the glasses are off now)
setup()
seeing._last.update(kind=None, asked=None)
assert ask("am I wearing glasses?").startswith("Yes")
setup(me={**ME, "glasses": False})
assert re.search(r"I looked again\. No, you're not wearing glasses", ask("are you sure?"))

# a face not in view: no guess; a scene's hat / bag None means none (tests/blind/r6 format)
setup(me={**ME, "glasses": None, "hat": None, "bag": {"kind": "handbag", "colour": "red"}})
seeing._last.update(kind=None, asked=None)
assert re.search(r"can't see your face", ask("am I wearing glasses?"))
assert re.search(r"^No, I don't see a hat", ask("am I wearing a hat?"))
assert re.search(r"red handbag", ask("do I have a bag?"))
assert re.search(r"빨간색 핸드백", ask("가방 메고 있어요?"))

# no looks (an older test scene): plain "can't tell", never a guess; the clothes colours still answered
world["people"] = [person(0.0, 1.0, {"upper": "white", "lower": None, "feet": None}, None)]
for p in world["people"]:
    del p["looks"]
seeing._last.update(kind=None, asked=None)
assert re.search(r"can't see", ask("am I wearing a hat?"))
assert re.search(r"can't see your hair", ask("what colour is my hair?"))
assert re.search(r"top looks white, but I can't tell if it's a jacket", ask("am I wearing a jacket?"))

# the VLM's JSON in its several shapes
n = seeing.norm_looks({"top": {"type": "T-shirt", "color": "Gray", "pattern": "plain"}, "bottom": "dark blue jeans",
                       "hair": {"colour": "black", "length": "short"}, "glasses": False, "sunglasses": True,
                       "hat": "null", "mask": "none", "bag": {"object": "backpack", "colour": "black"},
                       "left_hand": {"object": "cup", "colour": "yellow"}, "right_hand": None, "posture": "standing",
                       "action": "Waving"})
assert n["top"] == {"type": "t-shirt", "colour": "grey", "pattern": "plain"}, n["top"]
assert n["bottom"] == {"type": "jeans", "colour": "dark blue", "pattern": None}, n["bottom"]
assert n["glasses"] == "sunglasses" and n["hat"] is None and n["mask"] is False   # null: not in view; "none": none
assert n["bag"] == "black backpack" and n["left_hand"] == "yellow cup" and n["action"] == "waving"
assert seeing.norm_looks("not json") is None
assert seeing.scene_looks({"id": "A", "top": "red"}) is None   # an older scene: no looks fields

assert not bad, f"{bad} failed"
print(f"seeing people ok ({len(CASES)} questions)")
