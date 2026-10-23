"""What Lumi sees now, as facts other modules can use: things in view, the person in front, what is in their hands.

    sees(name=None, colour=None) -> [{name, colour, distance_m, bearing_deg, where, camera, position_mm, score}]
    people() -> [{distance_m, bearing_deg, camera}]   everyone in view, both cameras merged
    person_in_front() -> {distance_m, bearing_deg, where, position_mm, camera, facing, gesture, raised, pointing,
                          clothes: {upper, lower, feet}, hands: {"left"|"right": {"position_mm", "object"}}} or None
    person_holds(object=None) -> True / False / None (None: can't tell)
    object_in_hand() -> {name, colour, hand, position_mm, distance_m, width_mm} or None
    pointing_target() -> {"position_mm", "distance_m"} or None
    ask_vlm(question, lang="en") -> one spoken sentence from gemma4 on the picture of the person, or None (slow: 3-20 s)

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
HAND_CROP_PX = 320               # px; the detector looks again at a square this big around each hand (small things)
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
VLM_MODEL = "gemma4:26b"         # multimodal; the conversation model, already loaded
VLM_URL = "http://127.0.0.1:11434/api/chat"
VLM_WIDTH = 448                  # px; the picture sent (5 s on a quiet GPU, 20+ s while other LLM work runs)
VLM_TIMEOUT_S = 12.0
VLM_PROMPT = ("You are the eyes of a service robot. Look at the picture and answer the question in one short spoken "
              "sentence in {lang}. Say only what is clearly visible. If it is not clearly visible, say that you "
              "can't tell. Question: {q}")

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
    frames = []
    for c in cameras:
        end = time.time() + (SINCE_WAIT_S if since else WAIT_S)

        def fresh(d):
            return d and time.time() - d["time"] < FRESH_S and (since is None or d["time"] >= since)
        while True:
            try:
                d = json.loads(camview.det_path(c).read_text())
            except (FileNotFoundError, ValueError):
                d = None
            if fresh(d) or time.time() > end:
                break
            time.sleep(0.05)
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
    """Object boxes (x1, y1, x2, y2, score, cls) found by a second, zoomed look at the square around a hand."""
    img = f["color"]
    h, w = img.shape[:2]
    s = HAND_CROP_PX // 2
    x1, y1 = int(max(0, min(w - 2 * s, cx - s))), int(max(0, min(h - 2 * s, cy - s)))
    with _det_lock:
        boxes = person.detect_boxes(_box_net(), img[y1:y1 + 2 * s, x1:x1 + 2 * s])
    return [(a + x1, b + y1, c + x1, d + y1, sc, cl) for a, b, c, d, sc, cl in boxes]


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
    if skin is None or len(px) == 0:
        return objects.colour_name(px)
    hsv = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    dh = np.abs(hsv[:, 0] - skin[0])
    keep = ~((np.minimum(dh, 180 - dh) <= SKIN_HUE) & (np.abs(hsv[:, 1] - skin[1]) <= SKIN_SAT))
    return objects.colour_name(px[keep] if keep.mean() >= SKIN_KEEP else px)


def _held(f, kp, side, body_h, skin=None):
    """{position_mm, distance_m, object} for one hand, or None when the wrist is not seen. skin: _skin()."""
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
        if skin is not None:
            m["colour"] = _thing_colour(f["color"][int(y1):int(y2), int(x1):int(x2)].reshape(-1, 3), skin)
        o = {"name": name, "colour": m["colour"], "score": round(float(score), 2), "box": (x1, y1, x2, y2),
             "distance_m": m["distance_m"], "position_mm": m.get("position_mm"), "width_mm": m.get("width_mm")}
        if best is None or (gap, -score) < best[0]:
            best = ((gap, -score), o)
    hand["object"] = best[1] if best else None
    return hand


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
           "facing": _facing(kp), "raised": raised, "pointing": pointing,
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


def _front(frames):
    """The nearest person within FRONT_M, the other camera's view of the same person filling in the hands."""
    persons = [p for p in _persons(frames) if p["distance_m"] is None or p["distance_m"] <= FRONT_M]
    if not persons:
        return None
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
    return me


def other_person(frames=None):
    """The nearest person in view other than the one in front (another bearing), described as person_in_front, or
    None: "what is my friend wearing?"."""
    frames = snapshot() if frames is None else frames
    me = _front(frames)
    if me is None:
        return None
    for p in _persons(frames):
        if abs(p["bearing_deg"] - me["bearing_deg"]) > _same_deg(me["distance_m"]):
            return _public(p)
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
                    "distance_m": o["distance_m"], "width_mm": o["width_mm"]}
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
    p = _front(frames)
    if p is not None:
        f, (x1, y1, x2, y2) = p["_f"], p["box"]
        mx, my = (x2 - x1) // 6, (y2 - y1) // 10
        img = f["color"][max(0, y1 - my):y2 + my, max(0, x1 - mx):x2 + mx]
    else:
        img = next((f for f in frames if f["camera"] == "head"), frames[0])["color"]
    img = cv2.resize(img, (VLM_WIDTH, max(1, int(img.shape[0] * VLM_WIDTH / img.shape[1]))))
    b64 = base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]).decode()
    body = {"model": VLM_MODEL, "stream": False, "think": False, "keep_alive": -1,
            "options": {"temperature": 0, "num_predict": 60},
            "messages": [{"role": "user", "images": [b64],
                          "content": VLM_PROMPT.format(lang="Korean" if lang == "ko" else "English", q=question)}]}
    try:
        req = urllib.request.Request(VLM_URL, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=VLM_TIMEOUT_S) as r:
            return json.loads(r.read())["message"]["content"].strip() or None
    except Exception as e:
        print(f"scene: VLM gave no answer ({e})", flush=True)
        return None


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
