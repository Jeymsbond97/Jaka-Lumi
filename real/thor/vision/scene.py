"""What Lumi sees now, as facts other modules can use: things in view, the person in front, what is in their hands.

    sees(name=None, colour=None) -> [{name, colour, distance_m, bearing_deg, where, camera, position_mm, score}]
    people() -> [{distance_m, bearing_deg, camera}]   everyone in view, both cameras merged
    person_in_front() -> {distance_m, bearing_deg, where, position_mm, camera, facing, gesture, raised, pointing, posture,
                          clothes: {upper, lower, feet}, hands: {"left"|"right": {"position_mm", "distance_m", "object",
                          "something" (a thing without a class: {colour, share}), "px"}}} or None
    person_holds(object=None) -> True / False / None (None: can't tell)
    object_in_hand() -> {name, colour, hand, position_mm, distance_m, width_mm} or None
    pointing_target() -> {"position_mm", "distance_m"} or None
    ask_vlm(question, lang="en") -> one spoken sentence from gemma4 on the picture of the person, or None (slow: 3-20 s)
    ask_vlm_hand(evidence, lang="en") -> the same about what the person holds, from the picture around the hands and
                          the measured facts; "UNSURE" when it can't tell (slow: 1-30 s)
    ask_vlm_person(frames) -> {top, bottom, feet, hair, glasses, hat, mask, bag, left_hand, right_hand, posture,
                          action} of the person in front from one VLM pass on their picture, or None (slow: 2-15 s)

    python vision/scene.py                       # print all of it for the cameras now
    python vision/scene.py --save tests/data/x   # save the frames now as a test fixture (x_head.jpg/.npz/.json, ...)

Sources: the camera service's files (camview.py: raw JPEG, aligned depth, people and objects with positions measured
by objects.py), and YOLO11s-pose (pose.py) run here on the raw frame, ~20 ms. Positions are in the arm base frame (mm,
z up) as objects.py gives them; distance_m is from the camera along its view. Every function takes `frames` (from
snapshot() or load()) so tests run on saved frames; without it the cameras are read now. Nothing here moves the robot.
Honest by design: a fact the cameras do not give is None, never a guess.
"""
import base64
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from vision import camview, objects, person, pose

ROOT = Path(__file__).resolve().parents[1]      # the project folder
CAMERAS = ("head", "torso")      # the head camera watches people; the torso camera the table and the hands from below
FRESH_S = 1.5                    # s; older detections are not "now"
WAIT_S = 1.2                     # s to wait for a fresh detection when the camera service runs slow (idle: 1 per s)
SINCE_WAIT_S = 2.0               # s to wait for a detection made after the question (idle service: 1 per s, woken)
DEPTH_AGE_S = 2.0                # s; depth frames are written every 0.5 s
DEPTH_BEFORE_S = 0.5             # s; with `since`, depth written at most this long before the question (a hand that
                                 # moved while asking is measured where it is, else no depth: the colour-only checks)
FRONT_M = 3.0                    # m; the person "in front" is nearer than this
OFF_CENTRE_M = 0.5               # m; someone off to the side counts this much further when choosing who talks to Lumi
                                 # (the head turns to the speaker; a passer-by 0.1 m nearer at the side is not them)
SIDE_DEG = 15.0                  # deg; a thing further left / right than this is "on my left / right"
SAME_DEG, SAME_M = 8.0, 0.35     # two cameras' detections closer than this (angle, distance) are the same thing
CAMS_APART_M = 0.25              # m; the head and torso cameras see a near person at angles apart by about atan(this / d)
STALE_DEPTH_M = 0.4             # m; depth this far off the camera service's distance of a person is from another moment
SELF_M = 0.8                     # m; a box touching the frame edge at OWN_EDGE nearer than this (or unmeasured) is the
OWN_EDGE = {"head": "bottom", "torso": "top"}   # robot's own body (head: the shoulder; torso: the arm and the hand)
EDGE_PX = 15
SAME_MM = 200                    # ... or with arm-frame positions this close
DEPTH_R = 6                      # px; half size of the depth patch at a keypoint
HAND_REACH = 0.35                # hand centre = wrist + this x (wrist - elbow): the palm and what it holds
HAND_R = 0.5                     # hand region radius as a part of the forearm length
NO_DEPTH_R = 0.5                 # without depth the box centre must be this part of the radius from the hand
WRIST_PCT = 20                   # depth percentile at the wrist: the nearer part of the patch is the arm, not the room
HAND_DEPTH_M = 0.35              # m; an object this much further or nearer than the wrist is not in the hand
HAND_CROPS_PX = (320, 640)       # px; the detector looks again at squares this big around each hand: small things,
                                 # and a laptop or a book held up (a 320 crop cut a laptop in half)
HELD_SCORE = 0.2                 # in those crops a handheld class counts from this score (the whole frame: 0.35); a
                                 # phone held up scored 0.2-0.35 and was missed (2026-10-23). seeing.py trusts a weak
                                 # one only when two looks agree, or says it is a guess
COLOUR_CORE = 0.6                # a held thing's colour from this middle part of its box (the edges are hand and room)
WB_V_PCT, WB_MAX_S = 90, 100    # white balance: the scene's brightest pixels (this V percentile) with HSV S under
WB_GAIN = (0.8, 1.25)            # this are taken as white; per-channel gain limits (a beige wall is not grey)
PALM = (0.6, 0.35)               # something in a hand without a class: pixels around wrist + 0.6 x forearm, radius
BLOB_MM, BLOB_SHARE = 100, 0.25  # 0.35 x forearm, within this depth of the wrist and not skin, over this share
                                 # (estimates, 2026-10-23; not yet measured live)
SIT_THIGH, STAND_THIGH = 0.45, 0.6   # posture: knee below hip by under / over this part of the torso length (hip -
CROUCH_THIGH, CROUCH_DROP = 0.1, 0.8  # shoulder) is sitting / standing; crouching: hip at knee level and the ankle
                                 # under this part of the torso below the hip (estimates from body proportions)
HANDHELD = {"bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
            "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "cell phone", "remote", "mouse", "book",
            "scissors", "toothbrush", "hair drier", "sports ball", "frisbee", "umbrella", "handbag", "backpack",
            "laptop", "keyboard", "clock", "vase", "kite", "tennis racket", "baseball bat", "baseball glove"}
                                 # classes a person may hold; a "teddy bear" was an arm with a clear cup (2026-10-20)
RAISED = 0.25                    # wrist above the shoulder by this part of the torso length -> hand raised
POINT_ANGLE = 150.0              # deg; elbow straighter than this ...
POINT_LOW = 0.5                  # ... and wrist above this part of the torso (an arm hanging out with a cup is not)
POINT_REACH = 0.8                # ... and wrist this far from the shoulder (x torso length, in the picture) -> pointing
POINT_STEP_PX, POINT_RAY_MM = 4, 120   # the pointing ray is followed in px steps; a depth point this close to it is hit
POINT_MIN_MM = 250               # mm past the hand before a hit counts (not the hand itself)
CHEST = 0.5                      # the shirt colour is taken from this top part of shoulders -> hips
CLOTH_DEPTH_MM = 250             # mm; shirt pixels are this close to the chest depth (the room behind stays out)
CLOTH_MIN_PX = 60                # px; fewer clothes pixels in view than this: can't tell
THIGH = (0.1, 0.6)               # the trousers colour from this part of hip -> knee (shorts and skirts cover it too)
LEG_W = 0.35                     # thigh band width as a part of the hip keypoint distance
FOOT = (0.05, 0.35)              # the shoe: this part of the shin length past the ankle, away from the knee
FOOT_W = 0.3                     # shoe band width as a part of the shin length
SKIN_R = 6                       # px; half size of the face patch at the nose that gives the skin colour
SKIN_HUE, SKIN_SAT = 6, 50       # a held thing's pixels this close to the skin (HSV hue, saturation) are the hand
SKIN_KEEP = 0.3                  # ... unless fewer than this part of the box is left (estimates, not yet measured live)
WHITE_VS_SKIN = 1.2              # "grey" clothes this much brighter than the face are white in shade or against a
                                 # bright window (a white shirt read V 107 by a nose at 70, 2026-10-21)
PALE_S, PALE_V = 70, 150         # HSV median S under / V over: "light blue" clothes (measured 2026-10-22, the light blue
                                 # shirt in tests/data/scene_holding_cup_back: S 48, V 173; jeans S 107, V 90; white S 4-13)
VLM_MODEL = "gemma4:26b"         # multimodal; the conversation model, already loaded
VLM_URL = "http://127.0.0.1:11434/api/chat"
VLM_WIDTH = 448                  # px; the picture sent (5 s on a quiet GPU, 20+ s while other LLM work runs)
VLM_TIMEOUT_S = 12.0
VLM_PROMPT = ("You are the eyes of a service robot. Look at the picture and answer the question in one short spoken "
              "sentence in {lang}. Say only what is clearly visible. If it is not clearly visible, say that you "
              "can't tell. Question: {q}")
VLM_HAND_MODEL = "gemma4:e4b"    # the close look at a hand: gemma4:26b took 18-33 s for each new picture (measured
                                 # 2026-10-23 17:30, quiet or busy GPU alike; 1.3 s only for a picture seen before),
                                 # e4b 2-13 s once loaded (12.6 s to load; seeing.warm_up loads it). Both name
                                 # things wrongly on unclear pictures, so the answer starts "It looks like"
VLM_HAND_WIDTH = 320             # px; the hand picture sent
VLM_HAND_TIMEOUT_S = 12.0        # s; longer: Lumi says it can't make it out and asks for a hint
VLM_HAND_PROMPT = ("You are the eyes of a friendly service robot. The picture shows a person's hand close up; they "
                   "asked what they are holding. What your cameras measured: {evidence}. Answer in {lang} in one short, "
                   "natural spoken sentence to them (\"you're holding ...\"): what the thing is, its colour, and its "
                   "shape if that helps, beginning \"It looks like\" unless it is plain to see. Trust the picture over the "
                   "measurements. If the hand is clearly empty, say so. If you can't tell what it is, answer exactly "
                   "UNSURE.")
VLM_PERSON_MODEL = VLM_HAND_MODEL   # one look at the whole person: e4b 7-8 s, gemma4:26b 17 s, qwen2.5vl:7b 10 s on the
                                 # same picture with the GPU busy (measured 2026-10-23 23:00); e4b is kept loaded anyway
VLM_PERSON_WIDTH = 320           # px; the person picture sent (448 was not better, only slower)
VLM_PERSON_TIMEOUT_S = 15.0
VLM_PERSON_PROMPT = (
    "You are the eyes of a service robot. Describe the person nearest the camera as JSON with exactly these keys: "
    '"top": {"type": "t-shirt" / "shirt" / "jacket" / "hoodie" / "sweater" / "coat" / "blouse" / "dress" / "vest", '
    '"colour": one colour word, "pattern": "plain" / "striped" / "checked" / "printed" / "dotted"}, '
    '"bottom": {"type": "trousers" / "jeans" / "shorts" / "skirt", "colour": one colour word}, '
    '"feet": {"type": "sneakers" / "shoes" / "boots" / "sandals" / "slippers", "colour": one colour word}, '
    '"hair": {"colour": "black" / "brown" / "blond" / "grey" / "white" / "red" / "dyed", "length": "short" / "medium" / '
    '"long" / "bald"}, "glasses": "none" or "glasses" or "sunglasses", "hat": "none" or what it is with its colour '
    '("black cap"), "mask": "none" or the mask with its colour, "bag": "none" or the bag with its colour ("brown '
    'backpack"); for these four use null only when that part of the person is not in the picture, '
    '"left_hand": null or the thing in their own left hand with its colour, "right_hand": the same for their right '
    'hand, "posture": "standing" / "sitting" / "crouching", "action": what they are doing in a few words ("looking at '
    'a phone", "waving", "carrying a jacket"), "action_ko": the same in polite Korean ("휴대폰을 보고 계세요"). Use null for a part that is not visible. Only what is clearly visible.')

_det_lock = threading.RLock()
_det = {"net": None}


# ---------- frames ----------
def _transform(camera, d):
    if camera == "torso":
        return objects.base_from_camera()
    if d.get("head_pose"):
        from vision import head_cam
        return head_cam.base_from_head(*d["head_pose"][2:])
    return None


def snapshot(cameras=CAMERAS, since=None):
    """[{camera, color, depth (mm uint16 or None), people, objects, head_yaw, intr, T}] of the cameras now.
    since: a time.time(); only detections made after it count (a question is answered from frames taken after it
    was asked, not from the second before, while the hand still moved). A camera without one is left out."""
    for c in cameras:
        camview.want(c)                       # wakes an idle camera service to full speed
    def fresh(d):
        return d and time.time() - d["time"] < FRESH_S and (since is None or d["time"] >= since)

    def det(c):
        try:
            return json.loads(camview.det_path(c).read_text())
        except (FileNotFoundError, ValueError):
            return None
    end = time.time() + (SINCE_WAIT_S if since else WAIT_S)
    dets = {c: det(c) for c in cameras}
    while not all(fresh(d) for d in dets.values()) and time.time() < end:   # both cameras at once, not one by one
        time.sleep(0.01)
        dets = {c: d if fresh(d) else det(c) for c, d in dets.items()}
    frames = []
    for c in cameras:
        d = dets[c]
        color = cv2.imread(str(camview.raw_path(c)))
        if not fresh(d) or color is None:
            continue
        age = DEPTH_AGE_S if since is None else min(DEPTH_AGE_S, time.time() - since + DEPTH_BEFORE_S)
        frames.append({"camera": c, "color": color, "depth": camview.depth(c, age), "people": d["people"],
                       "objects": d["objects"], "head_yaw": d.get("head_yaw") or 0.0,
                       "intr": camview.intrinsics(c), "T": _transform(c, d)})
    return frames


def save(prefix, frames):
    """Frames -> <prefix>_<camera>.jpg / .npz (depth) / .json, a test fixture."""
    for f in frames:
        p = f"{prefix}_{f['camera']}"
        cv2.imwrite(p + ".jpg", f["color"], [cv2.IMWRITE_JPEG_QUALITY, 92])
        if f["depth"] is not None:
            np.savez_compressed(p + ".npz", depth=f["depth"].astype(np.uint16))
        meta = {k: f[k] for k in ("camera", "people", "objects", "head_yaw", "intr")}
        meta["T"] = None if f["T"] is None else np.asarray(f["T"]).tolist()
        Path(p + ".json").write_text(json.dumps(meta))


def load(prefix):
    """The frames save() wrote."""
    frames = []
    for c in CAMERAS:
        p = f"{prefix}_{c}"
        if not Path(p + ".json").exists():
            continue
        f = json.loads(Path(p + ".json").read_text())
        f["color"] = cv2.imread(p + ".jpg")
        f["depth"] = np.load(p + ".npz")["depth"] if Path(p + ".npz").exists() else None
        f["T"] = None if f["T"] is None else np.array(f["T"])
        frames.append(f)
    return frames


# ---------- geometry ----------
def _bearing(f, x):
    """Angle (deg) of image column x from the waist forward axis, + = robot's left (as person.py)."""
    w = f["color"].shape[1]
    return round(-(x - w / 2) / (w / 2) * (person.COLOR_HFOV / 2) + f["head_yaw"], 1)


def where(bearing):
    if bearing is None:
        return None
    return "on my left" if bearing > SIDE_DEG else "on my right" if bearing < -SIDE_DEG else "in front of me"


def _depth_at(f, x, y, r=DEPTH_R, pct=50):
    """Depth (mm) around a pixel: the median, or a lower percentile for a thin thing before the room (a wrist)."""
    d = f["depth"]
    if d is None:
        return None
    h, w = d.shape
    x, y = int(round(x)), int(round(y))
    patch = d[max(0, y - r):min(h, y + r + 1), max(0, x - r):min(w, x + r + 1)]
    v = patch[patch > 0]
    return float(np.percentile(v, pct)) if v.size >= 5 else None


def _to_base(f, x, y, z):
    """Pixel + depth (mm) -> arm base frame point (mm, numpy), or None without calibration."""
    if f["T"] is None or f["intr"] is None or z is None:
        return None
    i = f["intr"]
    K = np.array([[i["fx"], 0, i["cx"]], [0, i["fy"], i["cy"]], [0, 0, 1]])
    n = cv2.undistortPoints(np.array([[[x, y]]], np.float64), K, np.array(i["dist"])).reshape(2)
    T = np.asarray(f["T"])
    return T[:3, :3] @ np.array([n[0] * z, n[1] * z, z]) + T[:3, 3]


def _mm(p):
    return None if p is None else [round(float(v)) for v in p]


# ---------- things in view ----------
def _same(a, b):
    if a["name"] != b["name"]:
        return False
    if a.get("position_mm") and b.get("position_mm") and None not in a["position_mm"][:2] + b["position_mm"][:2]:
        return np.hypot(*np.subtract(a["position_mm"][:2], b["position_mm"][:2])) < SAME_MM
    return abs(a["bearing_deg"] - b["bearing_deg"]) < SAME_DEG and \
        abs((a["distance_m"] or 0) - (b["distance_m"] or 0)) < SAME_M


def own_body(f, o):
    """True for a box that is the robot itself: its shoulder in the head camera, its arm in the torso camera."""
    x1, y1, x2, y2 = o["box"]
    edge = OWN_EDGE[f["camera"]]
    at_edge = y2 >= f["color"].shape[0] - EDGE_PX if edge == "bottom" else y1 <= EDGE_PX
    return at_edge and (o.get("distance_m") is None or o["distance_m"] < SELF_M)


def things(frames=None):
    """Everything detected (not people), both cameras, the same thing seen twice kept once, nearest first."""
    frames = snapshot() if frames is None else frames
    out = []
    for f in frames:
        for o in f["objects"]:
            if own_body(f, o):
                continue
            t = {"name": o["name"], "colour": o.get("colour"), "distance_m": o.get("distance_m"),
                 "bearing_deg": _bearing(f, (o["box"][0] + o["box"][2]) / 2), "camera": f["camera"],
                 "position_mm": o.get("position_mm"), "score": o.get("score"), "box": o["box"]}
            t["where"] = where(t["bearing_deg"])
            twin = next((u for u in out if _same(u, t)), None)
            if twin is None:
                out.append(t)
            elif (t["score"] or 0) > (twin["score"] or 0):
                out[out.index(twin)] = t
    out.sort(key=lambda t: t["distance_m"] or 99)
    return out


def sees(name=None, colour=None, frames=None):
    """Things of this COCO class (None: any) and colour (None: any; white and grey count as one) seen now."""
    return [t for t in things(frames) if (name is None or t["name"] == name)
            and objects.same_colour(colour, t["colour"])]


def _same_deg(d):
    """Angle (deg) within which the two cameras' views of one thing d m away fall."""
    return SAME_DEG + (np.degrees(np.arctan(CAMS_APART_M / d)) if d else 0.0)


def people(frames=None):
    """Everyone in view, the two cameras merged: [{distance_m, bearing_deg, camera}] nearest first."""
    frames = snapshot() if frames is None else frames
    out = []
    for f in frames:
        for p in f["people"]:
            q = {"distance_m": p.get("distance_m"), "bearing_deg": p["angle_deg"], "camera": f["camera"]}
            if not any(abs(u["bearing_deg"] - q["bearing_deg"]) < _same_deg(u["distance_m"] or q["distance_m"]) and
                       (u["distance_m"] is None or q["distance_m"] is None or
                        abs(u["distance_m"] - q["distance_m"]) < SAME_M) for u in out):
                out.append(q)
    out.sort(key=lambda p: p["distance_m"] or 99)
    return out


# ---------- the person in front ----------
def _box_net():
    with _det_lock:
        if _det["net"] is None:
            _det["net"] = person.load_net()
        return _det["net"]


def _hand_boxes(f, cx, cy):
    """Object boxes (x1, y1, x2, y2, score, cls) found by second, zoomed looks at squares around a hand, handheld
    classes from HELD_SCORE."""
    img = f["color"]
    h, w = img.shape[:2]
    out = []
    for size in HAND_CROPS_PX:
        s = min(size, h, w) // 2
        x1, y1 = int(max(0, min(w - 2 * s, cx - s))), int(max(0, min(h - 2 * s, cy - s)))
        with _det_lock:
            boxes = person.detect_boxes(_box_net(), img[y1:y1 + 2 * s, x1:x1 + 2 * s], object_score=HELD_SCORE)
        out += [(a + x1, b + y1, c + x1, d + y1, sc, cl) for a, b, c, d, sc, cl in boxes]
    return out


def _gains(img):
    """Per-channel (B, G, R) gains that make the scene's bright, pale pixels grey: the light's colour taken out (a warm
    lamp makes a white cup cream and a cream one yellow). Limited to WB_GAIN."""
    small = img[::8, ::8].reshape(-1, 3)
    hsv = cv2.cvtColor(small.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    white = small[(hsv[:, 2] >= np.percentile(hsv[:, 2], WB_V_PCT)) & (hsv[:, 1] < WB_MAX_S)]
    if len(white) < 20:
        return np.ones(3)
    m = white.astype(np.float32).mean(axis=0) + 1
    return np.clip(m.mean() / m, *WB_GAIN)


def _balanced(f, px):
    """Pixels with the scene's light taken out (_gains, once per frame)."""
    if "_wb" not in f:
        f["_wb"] = _gains(f["color"])
    return np.clip(px.astype(np.float32) * f["_wb"], 0, 255).astype(np.uint8)


def _core(box, part=COLOUR_CORE):
    """The middle part of a box (x1, y1, x2, y2), int px."""
    x1, y1, x2, y2 = box
    dx, dy = (x2 - x1) * (1 - part) / 2, (y2 - y1) * (1 - part) / 2
    return int(x1 + dx), int(y1 + dy), int(max(x1 + dx + 1, x2 - dx)), int(max(y1 + dy + 1, y2 - dy))


def _skin_mask(px, skin):
    """True for the pixels (N, 3 BGR) of the skin colour (hue, saturation); all False without a skin reference."""
    if skin is None or len(px) == 0:
        return np.zeros(len(px), bool)
    hsv = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    dh = np.abs(hsv[:, 0] - skin[0])
    return (np.minimum(dh, 180 - dh) <= SKIN_HUE) & (np.abs(hsv[:, 1] - skin[1]) <= SKIN_SAT)


def _skin(f, kp):
    """(hue, saturation) medians of the face around the nose (HSV), or None: the hand holding a thing has this colour."""
    nose = pose.seen(kp, "nose")
    if nose is None:
        return None
    x, y = int(nose[0]), int(nose[1])
    patch = f["color"][max(0, y - SKIN_R):y + SKIN_R, max(0, x - SKIN_R):x + SKIN_R]
    if patch.size == 0:
        return None
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).reshape(-1, 3)
    return float(np.median(hsv[:, 0])), float(np.median(hsv[:, 1]))


def _thing_colour(px, skin):
    """Colour of a held thing's box pixels without the hand's skin (a grey phone in a hand read "orange", 2026-10-22);
    the box as it is when the skin leaves too little (an orange thing itself)."""
    if len(px) == 0:
        return objects.colour_name(px)
    keep = ~_skin_mask(px, skin)
    return objects.colour_name(px[keep] if keep.mean() >= SKIN_KEEP else px)


def _held(f, kp, side, body_h, skin=None):
    """{position_mm, distance_m, object, something, px, camera} for one hand, or None when the wrist is not seen.
    skin: _skin()."""
    wr, el = pose.seen(kp, f"{side}_wrist"), pose.seen(kp, f"{side}_elbow")
    if wr is None:
        return None
    if el is not None:
        fore = np.subtract(wr, el)
        cx, cy = np.add(wr, HAND_REACH * fore)
        r = max(HAND_R * float(np.hypot(*fore)), 0.04 * body_h)
    else:
        (cx, cy), r = wr, 0.08 * body_h
    z = _depth_at(f, *wr, r=2 * DEPTH_R, pct=WRIST_PCT)
    hand = {"position_mm": _mm(_to_base(f, wr[0], wr[1], z)), "distance_m": None if z is None else round(z / 1000, 2),
            "object": None}
    boxes = [(*o["box"], o.get("score") or 0, objects.COCO.index(o["name"])) for o in f["objects"]
             if not own_body(f, o)]
    best = None
    for x1, y1, x2, y2, score, cls in boxes + _hand_boxes(f, cx, cy):
        name = objects.COCO[cls]
        if name not in HANDHELD:
            continue
        gap = np.hypot(max(x1 - cx, 0, cx - x2), max(y1 - cy, 0, cy - y2))   # hand centre to the box, px
        if f["depth"] is None:                              # no depth to tell before / behind: the box must be on
            gap = np.hypot((x1 + x2) / 2 - cx, (y1 + y2) / 2 - cy) / NO_DEPTH_R   # the hand, not touch its region
        if gap > r:
            continue
        m = objects.measure(f["color"], f["depth"], (x1, y1, x2, y2), f["intr"], f["T"], round_=name in objects.ROUND) \
            if f["depth"] is not None else {"colour": objects.colour_name(f["color"][y1:y2, x1:x2].reshape(-1, 3)),
                                            "distance_m": None, "position_mm": None, "width_mm": None}
        if f["depth"] is not None and (z is None or m["distance_m"] is None or
                                       abs(m["distance_m"] - z / 1000) > HAND_DEPTH_M):
            continue                                            # behind or before the hand: not in it
        a, b, c, d = _core((x1, y1, x2, y2))                # the middle of the box, the light taken out
        m["colour"] = _thing_colour(_balanced(f, f["color"][b:d, a:c].reshape(-1, 3)), skin)
        o = {"name": name, "colour": m["colour"], "score": round(float(score), 2), "box": (x1, y1, x2, y2),
             "distance_m": m["distance_m"], "position_mm": m.get("position_mm"), "width_mm": m.get("width_mm")}
        if best is None or (gap, -score) < best[0]:
            best = ((gap, -score), o)
    hand["object"] = best[1] if best else None
    hand["px"], hand["camera"] = (float(cx), float(cy), float(r)), f["camera"]   # the other camera may fill a hand in
    hips = [p[1] for p in (pose.seen(kp, "left_hip"), pose.seen(kp, "right_hip")) if p]
    shown = not hips or wr[1] < min(hips)                  # a hand held up shows a thing; one hanging by the trousers
    hand["something"] = None if best or el is None else \
        _blob(f, wr, el, z, skin) if shown else {"colour": None, "share": 0.0}   # has them at its depth (2026-10-21)
    return hand


def _blob(f, wr, el, z, skin):
    """{colour, share}: share of the palm disc that is not skin at the hand's depth, just past the wrist, and the
    colour of it when over BLOB_SHARE (something the detector has no class for), else colour None (an empty hand).
    None: no depth to tell."""
    if f["depth"] is None or z is None:
        return None
    fore = np.subtract(wr, el)
    cx, cy = np.add(wr, PALM[0] * fore)
    r = max(6, int(PALM[1] * np.hypot(*fore)))
    h, w = f["depth"].shape
    yy, xx = np.ogrid[:h, :w]
    disc = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    near = disc & (f["depth"] > 0) & (np.abs(f["depth"].astype(np.float32) - z) < BLOB_MM)
    px = f["color"][near]
    px = px[~_skin_mask(px, skin)]
    share = len(px) / max(1, disc.sum())
    return {"colour": objects.colour_name(_balanced(f, px)) if share >= BLOB_SHARE else None,
            "share": round(float(share), 2)}


def _named(f, mask, ref_z=None, skin_v=None):
    """Colour name of the pixels in mask, or None (too few). Depth near ref_z (default: their own median) keeps the
    room out; objects.colour_name takes the main hue (a logo or a bit of floor does not move it). skin_v: the face's
    brightness (HSV V, median), which tells a white shirt in poor light from a grey one."""
    if mask.sum() < CLOTH_MIN_PX:
        return None
    px = f["color"][mask]
    if f["depth"] is not None:
        d = f["depth"][mask].astype(np.float32)
        ref = ref_z if ref_z is not None else (np.median(d[d > 0]) if (d > 0).any() else None)
        keep = (d > 0) & (np.abs(d - ref) < CLOTH_DEPTH_MM) if ref is not None else d > 0
        if keep.sum() > 50:
            px = px[keep]
    name = objects.colour_name(px)
    if name == "blue":                                         # a pale blue shirt is not the blue of jeans
        hsv = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3)
        return "light blue" if np.median(hsv[:, 1]) < PALE_S and np.median(hsv[:, 2]) > PALE_V else name
    # ponytail: one skin reference, so a light grey shirt over dark skin may read white; a second reference if so
    return "white" if name == "grey" and skin_v and np.median(px.max(axis=1)) >= WHITE_VS_SKIN * skin_v else name


def _clothes(f, kp, chest_z):
    """{upper, lower, feet}: the colour of the shirt (shoulders -> hips), the trousers (hips -> knees) and the shoes
    (past the ankles, away from the knees); None for a part not in the picture (a keypoint outside the frame is
    not seen: the pose model places ankles below the frame edge)."""
    h, w = f["color"].shape[:2]

    def at(n):
        p = pose.seen(kp, n)
        return np.array(p) if p and 0 <= p[0] < w and 0 <= p[1] < h else None

    def band(a, b, t0, t1, width):                             # mask of a thick line along a -> b, from t0 to t1
        m = np.zeros((h, w), np.uint8)
        cv2.line(m, tuple(int(v) for v in a + t0 * (b - a)), tuple(int(v) for v in a + t1 * (b - a)), 1,
                 max(4, int(width)))
        return m.astype(bool)

    out = {"upper": None, "lower": None, "feet": None}
    nose, eye = at("nose"), at("left_eye") if at("left_eye") is not None else at("right_eye")
    skin_v = None
    if nose is not None:
        r = max(4, int(0.4 * np.linalg.norm(eye - nose))) if eye is not None else 6
        x, y = int(nose[0]), int(nose[1])
        patch = f["color"][max(0, y - r):y + r, max(0, x - r):x + r]
        skin_v = float(np.median(patch.max(axis=2))) if patch.size else None
    sh, hip = [at(f"{s}_shoulder") for s in ("left", "right")], [at(f"{s}_hip") for s in ("left", "right")]
    if all(p is not None for p in sh):
        xs, y1 = [p[0] for p in sh], max(p[1] for p in sh)
        if all(p is not None for p in hip):                    # the chest: the arms hang over the belly side on
            y2 = y1 + CHEST * (min(p[1] for p in hip) - y1)
        else:
            y2 = y1 + 1.2 * abs(xs[0] - xs[1])                 # no hips in view: a shoulder width and a bit down
        inset = 0.15 * abs(xs[0] - xs[1])
        x1, x2 = int(max(0, min(xs) + inset)), int(min(w, max(xs) - inset))
        y1, y2 = int(max(0, y1 + 0.1 * (y2 - y1))), int(min(h, y2 - 0.1 * (y2 - y1)))
        if x2 - x1 >= 8 and y2 - y1 >= 8:
            m = np.zeros((h, w), bool)
            m[y1:y2, x1:x2] = True
            out["upper"] = _named(f, m, chest_z, skin_v)
    hip_w = np.linalg.norm(hip[0] - hip[1]) if all(p is not None for p in hip) else None
    legs, feet = np.zeros((h, w), bool), np.zeros((h, w), bool)
    for s, hp in zip(("left", "right"), hip):
        knee, ankle = at(f"{s}_knee"), at(f"{s}_ankle")
        if hp is not None and knee is not None:                # the thigh: trousers, shorts and skirts all cover it
            legs |= band(hp, knee, *THIGH, LEG_W * (hip_w or np.linalg.norm(knee - hp) / 2))
        if knee is not None and ankle is not None:
            end = ankle + FOOT[1] * (ankle - knee)
            if 0 <= end[0] < w and 0 <= end[1] < h:            # the whole shoe in the picture
                feet |= band(knee, ankle, 1 + FOOT[0], 1 + FOOT[1], FOOT_W * np.linalg.norm(ankle - knee))
    out["lower"] = _named(f, legs, None, skin_v) if legs.any() else None
    out["feet"] = _named(f, feet, None, skin_v) if feet.any() else None
    return out


def _angle(a, b, c):
    """Angle at b (deg) of a-b-c in the picture."""
    v1, v2 = np.subtract(a, b), np.subtract(c, b)
    cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) or 1)
    return float(np.degrees(np.arccos(np.clip(cos, -1, 1))))


def _gesture(kp):
    """(raised: [sides], pointing: side or None) from the keypoints of one picture."""
    sh = {s: pose.seen(kp, f"{s}_shoulder") for s in ("left", "right")}
    hips = [pose.seen(kp, f"{s}_hip") for s in ("left", "right")]
    known = [p for p in sh.values() if p]
    if not known:
        return [], None
    shoulder_y = np.mean([p[1] for p in known])
    if all(hips) and all(sh.values()):
        torso = abs(np.mean([p[1] for p in hips]) - shoulder_y)
    elif all(sh.values()):
        torso = 1.5 * abs(sh["left"][0] - sh["right"][0])
    else:
        torso = None
    raised, pointing = [], None
    for s in ("left", "right"):
        wr, el = pose.seen(kp, f"{s}_wrist"), pose.seen(kp, f"{s}_elbow")
        if wr is None or sh[s] is None or not torso:
            continue
        if wr[1] < sh[s][1] - RAISED * torso:
            raised.append(s)
        elif el is not None and wr[1] < shoulder_y + POINT_LOW * torso and _angle(sh[s], el, wr) > POINT_ANGLE and \
                np.hypot(*np.subtract(wr, sh[s])) > POINT_REACH * torso:
            pointing = s
    return raised, pointing


def _posture(kp):
    """"standing" / "sitting" / "crouching" from where the knees and ankles are against the torso length in the
    picture, or None (no hips or knees in view)."""
    def y(names):
        pts = [pose.seen(kp, n) for n in names]
        pts = [p[1] for p in pts if p]
        return np.mean(pts) if pts else None
    sh, hip, knee = y(("left_shoulder", "right_shoulder")), y(("left_hip", "right_hip")), y(("left_knee", "right_knee"))
    ankle = y(("left_ankle", "right_ankle"))
    if None in (sh, hip, knee) or hip - sh <= 0:
        return None
    torso = hip - sh
    thigh = (knee - hip) / torso                               # 0.8-0.9 standing; small when the thigh points at us
    if thigh > STAND_THIGH:
        return "standing"
    if thigh < CROUCH_THIGH and ankle is not None and (ankle - hip) / torso < CROUCH_DROP:
        return "crouching"
    return "sitting" if thigh < SIT_THIGH else None


def _facing(kp):
    eyes = [pose.seen(kp, n) for n in ("left_eye", "right_eye")]
    if all(eyes) and pose.seen(kp, "nose"):
        return True
    if any(eyes) or pose.seen(kp, "left_shoulder") or pose.seen(kp, "right_shoulder"):
        return False                                           # side on, or the back turned
    return None


def _describe_person(f, p):
    kp, (x1, y1, x2, y2) = p["kp"], p["box"]
    body_h = y2 - y1
    sh = [pose.seen(kp, n) for n in ("left_shoulder", "right_shoulder")]
    chest = tuple(np.mean([s for s in sh if s], axis=0)) if any(sh) else ((x1 + x2) / 2, y1 + 0.3 * body_h)
    hips = [pose.seen(kp, n) for n in ("left_hip", "right_hip")]
    if any(sh) and any(hips):                                  # a bit below the shoulders: the chest
        chest = (chest[0], chest[1] + 0.3 * (np.mean([h[1] for h in hips if h]) - chest[1]))
    z = _depth_at(f, *chest, r=3 * DEPTH_R)
    raised, pointing = _gesture(kp)
    skin = _skin(f, kp)
    hands = {s: _held(f, kp, s, body_h, skin) for s in ("left", "right")}
    out = {"camera": f["camera"], "box": p["box"], "distance_m": None if z is None else round(z / 1000, 2),
           "bearing_deg": _bearing(f, chest[0]), "position_mm": _mm(_to_base(f, chest[0], chest[1], z)),
           "facing": _facing(kp), "raised": raised, "pointing": pointing, "posture": _posture(kp),
           "gesture": "hand_raised" if raised else "pointing" if pointing else None,
           "clothes": _clothes(f, kp, z),
           "hands": hands, "seen": int((kp[:, 2] > pose.KP_SEEN).sum()), "_f": f, "_kp": kp}
    out["where"] = where(out["bearing_deg"])
    if out["distance_m"] is None:                              # no depth there: the camera service's distance
        near = [q for q in f["people"] if abs(q["angle_deg"] - out["bearing_deg"]) < SAME_DEG]
        if near:
            out["distance_m"] = near[0]["distance_m"]
    return out


def _depth_fits(f):
    """False when the depth frame is from another moment than the people found (depth is written every 0.5 s): a
    person's distance measured with the picture differs from the depth there now."""
    if f["depth"] is None:
        return False
    for p in f["people"]:
        if p.get("distance_m") and p.get("distance_src", "depth") == "depth":
            x1, y1, x2, y2 = p["box"]
            z = _depth_at(f, (x1 + x2) / 2, y1 + (y2 - y1) * 3 / 8, r=max(4, (x2 - x1) // 6))
            if z is None or abs(z / 1000 - p["distance_m"]) > STALE_DEPTH_M:
                return False
    return True


def _persons(frames):
    """Every person the pose model finds, described, nearest first (the cameras not merged)."""
    out = []
    for f in frames:
        if not f["people"]:                                    # the camera service saw nobody: skip the pose run
            continue
        if not _depth_fits(f):                                 # someone moved since the depth frame: go without it
            f = {**f, "depth": None}
        out += [_describe_person(f, p) for p in pose.detect(f["color"])]
    out.sort(key=lambda p: (p["distance_m"] or 99, -p["seen"]))
    return out


def _public(p):
    return {k: v for k, v in p.items() if not k.startswith("_")}


def speaker_key(distance_m, bearing_deg):
    """Who of the people in view is the one talking to Lumi: the nearest, someone off-centre counted further."""
    return (distance_m if distance_m is not None else 99) + (OFF_CENTRE_M if abs(bearing_deg or 0) > SIDE_DEG else 0)


def _front(frames):
    """The nearest person within FRONT_M, the other camera's view of the same person filling in the hands."""
    persons = [p for p in _persons(frames) if p["distance_m"] is None or p["distance_m"] <= FRONT_M]
    if not persons:
        return None
    persons.sort(key=lambda p: speaker_key(p["distance_m"], p["bearing_deg"]))
    me = persons[0]
    for other in persons[1:]:                                  # the same person in the other camera
        if other["camera"] == me["camera"] or abs(other["bearing_deg"] - me["bearing_deg"]) > _same_deg(me["distance_m"]):
            continue
        for s in ("left", "right"):
            mine, theirs = me["hands"][s], other["hands"][s]
            if theirs and (mine is None or (mine["object"] is None and theirs["object"] is not None)):
                me["hands"][s] = theirs
        for k in ("upper", "lower", "feet"):
            me["clothes"][k] = me["clothes"][k] or other["clothes"][k]
        if me["facing"] is None:
            me["facing"] = other["facing"]
        me["posture"] = me["posture"] or other["posture"]      # the torso camera sees the legs the head camera can't
    return me


def other_person(frames=None):
    """The nearest person in view other than the one in front (another bearing), described as person_in_front, or
    None: "what is my friend wearing?"."""
    p = _other(snapshot() if frames is None else frames)
    return _public(p) if p else None


def _other(frames):
    me = _front(frames)
    if me is None:
        return None
    for p in _persons(frames):
        if abs(p["bearing_deg"] - me["bearing_deg"]) > _same_deg(me["distance_m"]):
            return p
    return None


def person_in_front(frames=None):
    """The person nearest in front (see the module docstring), or None when nobody is within FRONT_M."""
    p = _front(snapshot() if frames is None else frames)
    return _public(p) if p else None


def object_in_hand(frames=None):
    """What the person in front holds: {name, colour, hand, position_mm, distance_m, width_mm} or None."""
    p = _front(snapshot() if frames is None else frames)
    if p is None:
        return None
    for s in ("right", "left"):
        h = p["hands"][s]
        if h and h["object"]:
            o = h["object"]
            return {"name": o["name"], "colour": o["colour"], "hand": s, "position_mm": o["position_mm"],
                    "distance_m": o["distance_m"], "width_mm": o["width_mm"], "score": o.get("score")}
    return None


def person_holds(object=None, frames=None):
    """True: a thing (of this COCO class) is in a hand. False: no such thing in the hands seen. None: can't tell
    (nobody in front, or no hand in view)."""
    p = _front(snapshot() if frames is None else frames)
    if p is None:
        return None
    hands = [h for h in p["hands"].values() if h]
    if any(h["object"] and (object is None or h["object"]["name"] == object) for h in hands):
        return True
    if any(h["object"] for h in hands):
        return False                                           # something else is in a hand
    return False if hands and all(h["distance_m"] is not None for h in hands) else None   # empty only with depth


def pointing_target(frames=None):
    """Where the person in front points: the first depth point along the shoulder -> wrist line past the hand,
    {"position_mm", "distance_m"} or None (not pointing, no depth, nothing hit in the picture)."""
    p = _front(snapshot() if frames is None else frames)
    if p is None or not p["pointing"]:
        return None
    f, kp, s = p["_f"], p["_kp"], p["pointing"]
    if f["depth"] is None:
        return None
    sh, wr = pose.seen(kp, f"{s}_shoulder"), pose.seen(kp, f"{s}_wrist")
    A, B = _to_base(f, *sh, _depth_at(f, *sh)), _to_base(f, *wr, _depth_at(f, *wr))
    if A is None or B is None or np.linalg.norm(B - A) < 1:
        return None
    ray = (B - A) / np.linalg.norm(B - A)
    step = np.subtract(wr, sh)
    step = step / (np.linalg.norm(step) or 1) * POINT_STEP_PX
    h, w = f["depth"].shape
    x, y = wr
    while 0 <= x < w and 0 <= y < h:
        x, y = x + step[0], y + step[1]
        z = f["depth"][int(min(h - 1, max(0, y))), int(min(w - 1, max(0, x)))]
        if not z:
            continue
        P = _to_base(f, x, y, float(z))
        along = np.dot(P - B, ray)
        if along > POINT_MIN_MM and np.linalg.norm(P - B - along * ray) < POINT_RAY_MM:
            return {"position_mm": _mm(P), "distance_m": round(float(z) / 1000, 2)}
    return None


# ---------- open questions: the VLM ----------
def ask_vlm(question, lang="en", frames=None):
    """One sentence about the person in front (or the whole head view when nobody is there) from gemma4 with the
    picture, or None on a timeout / error. Slow: use it only for what detections can't answer (glasses, a hat...)."""
    frames = snapshot() if frames is None else frames
    if not frames:
        return None
    return _vlm(_person_img(frames), VLM_PROMPT.format(lang="Korean" if lang == "ko" else "English", q=question))


def _person_img(frames, p=None):
    """The picture of person p (default: the one in front) with a margin, or the whole head view when nobody is there."""
    p = p or _front(frames)
    if p is not None:
        f, (x1, y1, x2, y2) = p["_f"], p["box"]
        mx, my = (x2 - x1) // 6, (y2 - y1) // 10
        return f["color"][max(0, y1 - my):y2 + my, max(0, x1 - mx):x2 + mx]
    return next((f for f in frames if f["camera"] == "head"), frames[0])["color"]


def ask_vlm_person(frames=None, other=False, bearing=None):
    """What the person in front (other: the nearest one besides them; bearing: the one seen nearest that bearing) looks
    like, from one VLM pass on their picture (VLM_PERSON_PROMPT's keys; None for what it can't see), or None: nobody
    there, a timeout or no JSON. Slow: 2-15 s."""
    frames = snapshot() if frames is None else frames
    p = (_other if other else _front)(frames) if frames else None
    if p is not None and bearing is not None:
        p = min(_persons(frames), key=lambda q: abs(q["bearing_deg"] - bearing))
    if p is None:
        return None
    said = _vlm(_person_img(frames, p), VLM_PERSON_PROMPT, width=VLM_PERSON_WIDTH, timeout=VLM_PERSON_TIMEOUT_S,
                model=VLM_PERSON_MODEL, fmt="json", tokens=200)
    try:
        got = json.loads(said or "")
    except ValueError:
        print(f"scene: VLM person look gave no JSON ({said!r})", flush=True)
        return None
    return got if isinstance(got, dict) else None


def _vlm(img, content, width=VLM_WIDTH, timeout=VLM_TIMEOUT_S, model=VLM_MODEL, fmt=None, tokens=60):
    """gemma4's words about a picture, or None on a timeout / error. fmt "json": the model must answer JSON."""
    img = cv2.resize(img, (width, max(1, int(img.shape[0] * width / img.shape[1]))))
    b64 = base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]).decode()
    body = {"model": model, "stream": False, "think": False, "keep_alive": -1,
            "options": {"temperature": 0, "num_predict": tokens},
            "messages": [{"role": "user", "images": [b64], "content": content}]}
    if fmt:
        body["format"] = fmt
    try:
        req = urllib.request.Request(VLM_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())["message"]["content"].strip() or None
    except Exception as e:
        print(f"scene: VLM gave no answer ({e})", flush=True)
        return None


def hand_crop(frames=None, side=None):
    """The picture around the hand(s) of the person in front (a square of 5 hand radii, at least 320 px), or None."""
    frames = snapshot() if frames is None else frames
    p = _front(frames)
    if p is None:
        return None
    hands = [h for s, h in p["hands"].items() if h and h.get("px") and side in (None, s)]
    if not hands:
        return None
    hands = [h for h in hands if h["camera"] == hands[0]["camera"]]
    img = next(f["color"] for f in frames if f["camera"] == hands[0]["camera"])
    xs, ys = [h["px"][0] for h in hands], [h["px"][1] for h in hands]
    half = max(160, 2.5 * max(h["px"][2] for h in hands), (max(xs) - min(xs)) / 2 + 160, (max(ys) - min(ys)) / 2 + 160)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    x1, y1 = int(max(0, cx - half)), int(max(0, cy - half))
    crop = img[y1:int(cy + half), x1:int(cx + half)]
    return crop if crop.size else None


def ask_vlm_hand(evidence, lang="en", frames=None, side=None):
    """One spoken sentence on what the person in front holds, from gemma4 with the picture around their hand(s) and
    what the cameras measured (evidence: a line of facts), or "UNSURE" / None (can't tell, timeout). Slow: 1-30 s."""
    img = hand_crop(frames, side)
    if img is None:
        return None
    return _vlm(img, VLM_HAND_PROMPT.format(lang="Korean" if lang == "ko" else "English", evidence=evidence),
                width=VLM_HAND_WIDTH, timeout=VLM_HAND_TIMEOUT_S, model=VLM_HAND_MODEL)


def warm_vlm_hand():
    """Loads the close-look model (VLM_HAND_MODEL) with a tiny picture, so the first close look is not 12 s slower."""
    _vlm(np.zeros((32, 32, 3), np.uint8), "Say OK.", width=32, timeout=60, model=VLM_HAND_MODEL)


def _print(frames):
    t = time.time()
    p = person_in_front(frames)
    print(f"person in front ({1000 * (time.time() - t):.0f} ms):", json.dumps(p, default=str))
    print("in hand:", object_in_hand(frames), " holds:", person_holds(None, frames), " points at:", pointing_target(frames))
    print("people:", people(frames))
    for o in things(frames):
        print(f"  {o['name']:12s} {o['colour'] or '?':7s} {o['distance_m']} m  {o['where']}  ({o['camera']}, {o['score']})")


if __name__ == "__main__":
    if "--save" in sys.argv:
        save(sys.argv[sys.argv.index("--save") + 1], snapshot())
    elif "--load" in sys.argv:
        _print(load(sys.argv[sys.argv.index("--load") + 1]))
    else:
        _print(snapshot())
