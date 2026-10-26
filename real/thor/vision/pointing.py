"""Where on the floor the person in front points ("go there", "저기로 가"): the shoulder -> wrist line of their
pointing arm (YOLO11s-pose keypoints + depth, scene.py) met with the floor, as a map point the base can drive to.

    asked(text) -> "there" | "here" | None       the words of a go-to-the-pointed-spot request
    spot(frames) -> {"position_mm", "distance_m", "clamped"} or {"why"}    arm base frame, nothing else read
    target(frames=None) -> spot + {"map": (x, y, theta)} or {"why"}       map pose, the spot checked for room

    python vision/pointing.py      # the spot pointed at now (nothing moves)

The floor height comes from the person's own ankles (they stand on it), so no camera height has to be known.
Accuracy (estimates, not measured live): depth at the shoulder and the wrist is good to ~2 % at 2 m, which tilts the
line by a few degrees; a spot 3 m from the person can be ~0.5 m off, nearer spots less. Pointing almost level moves
the spot most. Honest by design: when the arm, the feet or the depth is not seen, it says why; no spot is guessed.
"""
import json
import math
import re
import sys

import numpy as np

from vision import pose, scene

MAX_M = 5.0              # m from the robot; a spot further away is brought in towards the robot (safe max, estimate)
NEAR_M = 0.5             # m; a spot this near the robot needs no drive
MIN_DOWN_DEG = 5.0       # deg the arm must point below level; flatter, the line meets the floor too far or never
ANKLE_MM = 80.0          # mm; ankle keypoint above the floor (estimate: an adult's ankle bone, shoes on)
FEET_SAME_MM = 150.0     # mm; two ankles further apart in height than this are not both on the floor (a step)

SAY = {   # why -> (en, ko)
    "nobody": ("I can't see you. Please stand in front of me and point.", "안 보여요. 제 앞에 서서 가리켜 주세요."),
    "not_pointing": ("I don't see you pointing. Point with your arm straight to the spot, please.",
                     "가리키는 팔이 안 보여요. 팔을 쭉 펴서 그곳을 가리켜 주세요."),
    "no_depth": ("I see your arm, but I can't measure it. Please come a bit closer.",
                 "팔은 보이는데 거리를 잴 수 없어요. 조금 더 가까이 와 주세요."),
    "no_feet": ("I can't see your feet, so I can't tell where the floor is. Please step back a little.",
                "발이 안 보여서 바닥을 알 수 없어요. 조금 뒤로 물러나 주세요."),
    "up": ("You're pointing too high, not at the floor. Point down at the spot, please.",
           "너무 높이 가리키고 있어요. 바닥의 그곳을 가리켜 주세요."),
    "near": ("That's right here.", "바로 여기예요."),
    "no_map": ("I can't place that spot on my map yet.", "그곳을 아직 지도에 표시할 수 없어요."),
    "blocked": ("Something is in the way at that spot. Please point somewhere else.",
                "그곳에는 장애물이 있어요. 다른 곳을 가리켜 주세요."),
}

_GO_EN = r"(?:go|come|move|drive|walk|head|get)(?: over)?"
_THERE_EN = (r"(?:over )?there|that way|over that way|to that (?:spot|place|point)|"
             r"(?:to )?where i(?:'m| am) pointing(?: (?:at|to))?|to the (?:spot|place) i(?:'m| am) pointing (?:at|to)")
_HERE_EN = r"(?:over )?here|this way"
_THERE_KO = r"저기|저쪽|저곳|거기|그쪽|(?:제가|내가) 가리키는 (?:곳|데|쪽)"
_HERE_KO = r"여기|이쪽|이곳"
_GO_KO = r"(?:가|와|와봐|가봐|이동해|가 ?줘|와 ?줘|가 ?봐|와 ?봐|가세요|오세요|가 ?주세요|와 ?주세요|이동해 ?줘)(?:요)?"
_LEAD = r"^(?:(?:hey |hi |ok(?:ay)? )?lumi[,!]?\s*|루미[야아]?[,!]?\s*)?(?:please |can you |could you |now |)?"
_END = r"(?:,? please)?\s*[.!?]*$"
_ASK = [(re.compile(_LEAD + _GO_EN + rf" (?:{w}){_END}", re.I), k) for w, k in ((_THERE_EN, "there"), (_HERE_EN, "here"))] + \
       [(re.compile(_LEAD + rf"(?:{w})\s*(?:으로|로)?\s*{_GO_KO}{_END}"), k) for w, k in ((_THERE_KO, "there"), (_HERE_KO, "here"))] + \
       [(re.compile(_LEAD + rf"(?:{w})\s*(?:으로|로)?\s*{_GO_EN}{_END}", re.I), k)          # mixed: "저기로 go", "there로 가"
        for w, k in ((_THERE_KO + "|there", "there"), (_HERE_KO + "|here", "here"))] + \
       [(re.compile(_LEAD + rf"(?:there|that way)\s*(?:으로|로)?\s*{_GO_KO}{_END}", re.I), "there"),
        (re.compile(_LEAD + rf"(?:here|this way)\s*(?:으로|로)?\s*{_GO_KO}{_END}", re.I), "here"),
        (re.compile(_LEAD + _GO_EN + rf"\s*(?:{_THERE_KO}){_END}", re.I), "there"),
        (re.compile(_LEAD + _GO_EN + rf"\s*(?:{_HERE_KO}){_END}", re.I), "here")]


def asked(text):
    """"there" for "go there" / "저기로 가" / "come to where I'm pointing", "here" for "come here" / "여기로 와",
    None for anything else (a longer sentence, a place by name, "put it there")."""
    t = re.sub(r"\s+", " ", text.strip().lower().replace("’", "'"))
    return next((k for r, k in _ASK if r.match(t)), None)


def floor_spot(shoulder, wrist, floor_z):
    """Where the shoulder -> wrist line (mm, z up) meets the floor at floor_z: the point (mm), or None when the line
    points less than MIN_DOWN_DEG below level."""
    a, b = np.asarray(shoulder, float), np.asarray(wrist, float)
    d = b - a
    n = np.linalg.norm(d)
    if n < 1 or d[2] / n > -math.sin(math.radians(MIN_DOWN_DEG)):
        return None
    return b + (floor_z - b[2]) / d[2] * d


def _point(f, kp, name, pct=50):
    xy = pose.seen(kp, name)
    return None if xy is None else scene._to_base(f, *xy, scene._depth_at(f, *xy, pct=pct))


def spot(frames):
    """The floor spot the person in front points at, arm base frame: {"position_mm", "distance_m" (from the robot),
    "clamped"} or {"why": a SAY key}."""
    p = scene._front(frames)
    if p is None:
        return {"why": "nobody"}
    s = p["pointing"]
    if not s:
        return {"why": "not_pointing"}
    f, kp = p["_f"], p["_kp"]
    sh, wr = _point(f, kp, f"{s}_shoulder"), _point(f, kp, f"{s}_wrist", scene.WRIST_PCT)
    if sh is None or wr is None:
        return {"why": "no_depth"}
    feet = [q[2] for q in (_point(f, kp, n, scene.WRIST_PCT) for n in ("left_ankle", "right_ankle")) if q is not None]
    if not feet or max(feet) - min(feet) > FEET_SAME_MM:
        return {"why": "no_feet"}
    hit = floor_spot(sh, wr, min(feet) - ANKLE_MM)
    if hit is None:
        return {"why": "up"}
    xy = hit[:2]            # ponytail: distance from the arm base origin, not the base centre (~0.1 m apart)
    dist = float(np.hypot(*xy)) / 1000
    clamped = dist > MAX_M
    if clamped:             # brought in towards the robot along the same bearing
        xy, dist = xy * MAX_M / dist, MAX_M
    if dist < NEAR_M:
        return {"why": "near"}
    return {"position_mm": [round(float(v)) for v in (*xy, hit[2])], "distance_m": round(dist, 2), "clamped": clamped}


def target(frames=None):
    """spot() of the cameras now as a map pose to drive to: + {"map": (x, y, theta)}, theta facing from the robot to
    the spot; {"why"} when there is none, or the base would not fit there (the sensors or the map, agv.clearance)."""
    from robot import agv
    from tasks import fetch
    out = spot(scene.snapshot() if frames is None else frames)
    if "why" in out:
        return out
    w = fetch.map_xy({"x": out["position_mm"][0], "y": out["position_mm"][1]})
    if w is None:
        return {"why": "no_map"}
    x, y, _ = agv.pose()
    mx, my = float(w[0]), float(w[1])
    if agv.clearance(mx, my) < fetch.BASE_HALF_M + fetch.CLEAR_M:
        return {"why": "blocked", **out}
    return {**out, "map": (round(mx, 3), round(my, 3), round(math.atan2(my - y, mx - x), 3))}


if __name__ == "__main__":
    print(json.dumps(target(scene.load(sys.argv[1]) if len(sys.argv) > 1 else None)))
