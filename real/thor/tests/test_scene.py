"""Self-check of vision/scene.py and assistant/seeing.py on saved camera frames (tests/data/scene_*) and synthetic
keypoints: python tests/test_scene.py. Uses the GPU pose model; never the robot, the camera service or the VLM."""
import time
from pathlib import Path

import numpy as np

from assistant import seeing
from vision import pose, scene

DATA = Path(__file__).resolve().parent / "data"
scene.ask_vlm = lambda q, lang="en", frames=None: "VLM"          # the slow model is not asked in tests
scene.snapshot = None                                              # and the live cameras are never read


def fx(name):
    return scene.load(str(DATA / f"scene_{name}"))


def say(text, frames, lang="en"):
    return seeing.answer(text, lang, frames)


# ---------- a room without people (2026-10-20, kitchen corner) ----------
f = fx("empty_room")
assert scene.person_in_front(f) is None and scene.people(f) == []
assert scene.person_holds(None, f) is None and scene.object_in_hand(f) is None
assert scene.sees("potted plant", None, f), scene.things(f)
assert not any(t["distance_m"] is not None and t["distance_m"] < scene.SELF_M for t in scene.things(f)), \
    "the robot's own shoulder (head camera, frame bottom) is not a thing it sees"
assert say("how many people are here?", f) == "I don't see anyone right now."
assert say("do you see the red apple?", f) == "No, I don't see a red apple right now."
assert say("빨간 사과 보여?", f, "ko") == "아니요, 지금은 빨간색 사과가 안 보여요."
assert say("what am I holding?", f).startswith("I can't see you")
assert say("do you see a plant?", f).startswith("Yes, I see a potted plant")
assert "metres from me" in say("how far is it?", f)
assert say("what is behind you?", f).startswith("My cameras look forward")
assert say("what do you see?", f).startswith("I see a ")

# ---------- one man in a white shirt close in front, looking down at the robot ----------
f = fx("white_shirt_near")
p = scene.person_in_front(f)
assert p and p["distance_m"] < 1.0 and p["clothes"]["upper"] == "white" and p["where"] == "in front of me", p
assert len(scene.people(f)) == 1, "the head and the torso camera see the same man"
assert say("how many people are here?", f) == "I see one person right now."
assert say("how many people can you see?", f) == "I see one person right now."
for q in ("How many people work at Cutshion company?", "How many people work at cutshion campy?",   # 2026-10-21 live
          "How many people work there?", "How many people work in a coaching company?", "how many employees do you have?",
          "how many people live in Korea?", "직원이 몇 명이에요?", "쿳션에는 몇 명이 일해요?"):
    assert say(q, f, "ko" if q[0] > "z" else "en") is None, q   # the company / the world: knowledge or the LLM
assert say("what colour is my shirt?", f) == "Your shirt looks white."
assert say("What is the color of my t-shirt?", f) == "Your t-shirt looks white."            # 2026-10-21 live: the LLM
assert say("내 티셔츠 무슨 색이야?", f, "ko") == "티셔츠는 흰색으로 보여요."
assert say("what colour are my trousers?", f) == "I can't see your trousers from here."     # head camera, close up
assert say("바지 색깔?", f, "ko") == "여기서는 바지가 안 보여요."
assert say("what's on my feet?", f) == "I can't see your shoes from here."
assert say("신발 뭐 신었어?", f, "ko") == "여기서는 신발이 안 보여요."
assert say("what am I wearing?", f) == "You're wearing a white top. I can't see your trousers or shoes from here."
assert say("내 옷 무슨 색이야?", f, "ko") == "흰색 상의를 입고 계세요. 바지와 신발은 여기서 안 보여요."
assert scene.object_in_hand(f) is None, "a fire extinguisher behind his hand is not in it"
assert say("can you see me?", f).startswith("Yes, I can see you")

# ---------- a man walking away to the right with a jacket over his arm (white shirt, jeans) ----------
f = fx("carrying_jacket")
p = scene.person_in_front(f)
assert p and p["where"] == "on my right" and p["facing"] is False, p
assert p["clothes"] == {"upper": "white", "lower": "blue", "feet": None}, p["clothes"]    # ankle below the frame
assert say("What is it? Color my jeans.", f) == "Your jeans look blue."                    # 2026-10-21 live
assert say("내가 뭐 입고 있어?", f, "ko") == "흰색 상의에 파란색 바지를 입고 계세요. 신발은 여기서 안 보여요."
assert scene.person_holds(None, f) is not True, "no detected thing in his hands: never claim one"

# ---------- a man with his back to the torso camera, a clear plastic cup in his hand (not detectable) ----------
f = fx("holding_cup_back")
p = scene.person_in_front(f)
assert p and p["clothes"]["upper"] == "blue" and p["pointing"] is None and p["facing"] is False, p
assert scene.object_in_hand(f) is None and scene.person_holds("cup", f) is None    # depth stale: can't tell
assert say("what am I wearing?", f) == "You're wearing a blue top and black trousers. I can't see your shoes from here."
                                         # the trousers are near black (V ~48): no hue there (2026-10-22 live: "blue")

# ---------- a white shirt against a bright window: the pixels read grey (V 107), the face darker still (V 70) ----------
f = fx("white_shirt_backlit")
assert scene.person_in_front(f)["clothes"] == {"upper": "white", "lower": None, "feet": None}
assert say("What is the color of my shirt?", f) == "Your shirt looks white."               # 2026-10-21 live: "grey"

# ---------- clothes words that are not questions about them ----------
for q in ("what are you wearing?", "what should I wear today?", "뭐 입을까?", "I like my shoes", "do you like my shirt?"):
    assert seeing.SHIRT.search(q) is None, q

# ---------- gestures from synthetic keypoints (x, y px, confidence) ----------
def kp(**pts):
    k = np.zeros((17, 3), np.float32)
    for n, (x, y) in pts.items():
        k[pose.K[n]] = (x, y, 0.9)
    return k


body = dict(left_shoulder=(700, 300), right_shoulder=(580, 300), left_hip=(690, 600), right_hip=(590, 600),
            nose=(640, 220), left_eye=(655, 205), right_eye=(625, 205))
raised = kp(**body, right_elbow=(560, 220), right_wrist=(560, 120), left_elbow=(720, 450), left_wrist=(725, 580))
assert scene._gesture(raised) == (["right"], None) and scene._facing(raised) is True
points = kp(**body, left_elbow=(820, 310), left_wrist=(950, 320), right_elbow=(570, 450), right_wrist=(570, 580))
assert scene._gesture(points) == ([], "left")
hangs = kp(**body, left_elbow=(780, 420), left_wrist=(860, 540))              # arm held out low, a bag in it
assert scene._gesture(hangs) == ([], None)
back = kp(left_shoulder=(580, 300), right_shoulder=(700, 300))
assert scene._facing(back) is False

# ---------- what is in a hand: synthetic frame, depth 1.0 m at the person, 2.5 m behind ----------
img = np.full((720, 1280, 3), 200, np.uint8)
depth = np.full((720, 1280), 2500, np.uint16)
depth[100:700, 500:900] = 1000
intr = {"fx": 608.0, "fy": 608.0, "cx": 640.0, "cy": 360.0, "dist": [0.0] * 8}
frame = {"camera": "torso", "color": img, "depth": depth, "people": [], "head_yaw": 0.0, "intr": intr, "T": np.eye(4),
         "objects": [{"name": "cup", "score": 0.8, "box": (850, 560, 900, 640)},          # at the right hand, 1.0 m
                     {"name": "bottle", "score": 0.8, "box": (520, 600, 560, 690)}]}     # by the left hand, but 2.5 m
img[560:640, 850:900] = (30, 30, 200)                                                     # a red cup
depth[600:700, 520:560] = 2500
k = kp(**body, left_elbow=(860, 450), left_wrist=(870, 560), right_elbow=(560, 450), right_wrist=(550, 560))
held = {s: scene._held(frame, k, s, 600) for s in ("left", "right")}
assert held["left"]["object"]["name"] == "cup" and held["left"]["object"]["colour"] == "red", held
assert held["right"]["object"] is None, "a bottle 1.5 m behind the hand is not in it"
assert held["left"]["position_mm"] is not None and abs(held["left"]["distance_m"] - 1.0) < 0.05

# ---------- shirt, trousers and shoes of a whole body: synthetic frame, keypoints of a person 2.5 m away ----------
img = np.full((720, 1280, 3), 150, np.uint8)                                            # grey floor and wall
img[200:470, 580:700] = (40, 40, 200)                                                   # red t-shirt
img[470:640, 590:690] = (20, 20, 20)                                                    # black trousers
img[640:690, 585:695] = (235, 235, 235)                                                 # white shoes
img[150:190, 620:660] = (120, 150, 190)                                                 # the face
frame = {"camera": "torso", "color": img, "depth": None}
whole = kp(nose=(640, 170), left_eye=(648, 165), left_shoulder=(690, 210), right_shoulder=(590, 210),
           left_hip=(670, 470), right_hip=(610, 470), left_knee=(665, 560), right_knee=(615, 560),
           left_ankle=(665, 635), right_ankle=(615, 635))
assert scene._clothes(frame, whole, None) == {"upper": "red", "lower": "black", "feet": "white"}
cut = whole.copy()
cut[pose.K["left_ankle"], 1] = cut[pose.K["right_ankle"], 1] = 700                     # shoes past the frame edge
assert scene._clothes(frame, cut, None)["feet"] is None
p = {"clothes": scene._clothes(frame, whole, None)}
assert seeing._clothes_answer(p, "what am I wearing?", "en") == "You're wearing a red top, black trousers and white shoes."
assert seeing._clothes_answer(p, "what colour are my shoes?", "en") == "Your shoes look white."
assert seeing._clothes_answer(p, "신발 뭐 신었어?", "ko") == "신발은 흰색으로 보여요."
assert seeing._clothes_answer(p, "내가 뭐 입고 있어?", "ko") == "빨간색 상의에 검은색 바지를 입고, 흰색 신발을 신고 계세요."

# ---------- words that are not about the cameras ----------
f = fx("empty_room")
for text in ("how far is Seoul?", "what time is it?", "is there a cafe nearby?", "what are you doing?",
             "지금 뭐 해?", "what are you holding?", "tell me about Cutshion", "look left"):
    assert say(text, f) is None, text
assert say("am I wearing glasses?", f).startswith("I can't see you")
assert say("am I wearing glasses?", fx("white_shirt_near")) == "VLM"

# ---------- speed: the facts in well under a second once the models are loaded ----------
f = fx("white_shirt_near")
t = time.time()
for _ in range(5):
    scene.person_in_front(f)
ms = (time.time() - t) / 5 * 1000
print(f"person_in_front {ms:.0f} ms")
assert ms < 300, ms
print("scene ok")
