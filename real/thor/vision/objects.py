"""Objects on the table in front of the torso camera: class, colour, 3D position and size in the arm base frame.

The camera service (camview.py) runs YOLOv8n once per frame for people and objects alike; for the torso
camera it calls measure_all() with the non-person boxes and the aligned depth, and puts the result into
lumi_det_torso.json ("objects"). api/server.py serves it as GET /objects, the dashboard draws the boxes.

    python vision/objects.py              # print what the torso camera sees now (camera service must be running)
    python vision/objects.py --watch      # every second, until Ctrl+C

Positions are in the arm base frame (mm, z up) through camera_extrinsics.json (calib.py). The calibration was
made at one lift / waist position; other positions are not verified yet (docs/15 section 8).
Only the front of an object is visible, so for round things (cups, bottles, fruit) the centre is the visible
surface pushed back by half the width along the line of sight.
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from vision import camview

ROOT = Path(__file__).resolve().parents[1]      # the project folder
EXTRINSICS = ROOT / "data" / "camera_extrinsics.json"
CAMERA = "torso"
FG_MM = 60.0                 # depth band around the object's centre depth that counts as the object
MIN_POINTS = 40              # fewer valid depth pixels than this -> no 3D for that box
MAX_POINTS = 4000            # depth pixels used per object (random subset)
MID_BAND = (0.3, 0.7)        # width is measured on this height band of the object (the table edge stays out)
EDGE_PCT = (1, 99)          # percentiles taken as the object's edges (robust to stray depth pixels)
MIN_SATURATION = 50          # HSV S below this is white / grey / black
DARK_V = 60                  # HSV V below this has no hue the camera can tell (black trousers: V ~48, S ~95, read
                             # "blue"; blue jeans V ~90, 2026-10-22)
ROUND_FIX_MM = (13.9, -3.1)  # mm (x, y), arm frame, added to a round thing's centre: the camera read cup centres this
                             # far off, mean of three spots 7-11 cm apart (hover readings, 2026-10-27; +-4 mm between them)
EDGE_PX = 4                  # a box this close to the bottom of the frame is cut off: height and centre z unknown
STALE_S = 1.5                # s; an older detection file means the camera service is not live
SURE_SCORE = 0.35            # a box scoring less (person.WEAK_SCORE) is kept only when depth measures this size there:
WEAK = {"cup": ((40, 110), (50, 250))}   # name -> (width, height) mm ranges
WIDEST = {"cup": 100}        # mm; a box measured wider is something else: a white plant pot read "cup" at 110 mm
                             # (2026-10-20); the widest cup the gripper takes reads ~84

SLICE_MM = 10.0              # body(): a bottle's width is measured in height slices this thick
SLICE_MIN_POINTS = 20        # ... a slice with fewer depth points is left out
BODY_PCT = 75                # ... its body is as wide as this percentile of the slices' widths (the neck and the cap
                             # are the narrow minority; the table's edge in the bottom slice the wide one)
BODY_FRACTION = 0.9          # ... and begins at the first slice from the top this much as wide (a 66 mm spray can,
                             # 2026-10-22: cap 43-53, body 58-63 seen)

COCO = ("person bicycle car motorcycle airplane bus train truck boat traffic_light fire_hydrant stop_sign "
        "parking_meter bench bird cat dog horse sheep cow elephant bear zebra giraffe backpack umbrella handbag tie "
        "suitcase frisbee skis snowboard sports_ball kite baseball_bat baseball_glove skateboard surfboard "
        "tennis_racket bottle wine_glass cup fork knife spoon bowl banana apple sandwich orange broccoli carrot "
        "hot_dog pizza donut cake chair couch potted_plant bed dining_table toilet tv laptop mouse remote keyboard "
        "cell_phone microwave oven toaster sink refrigerator book clock vase scissors teddy_bear hair_drier "
        "toothbrush").split()
COCO = [c.replace("_", " ") for c in COCO]
ROUND = {"cup", "bottle", "wine glass", "bowl", "apple", "orange", "banana", "vase", "sports ball", "donut"}
# OpenCV hue 0-180 -> colour name, upper bounds
HUES = ((8, "red"), (20, "orange"), (33, "yellow"), (85, "green"), (130, "blue"), (155, "purple"), (170, "pink"),
        (181, "red"))

_extr = {"mtime": None, "T": None}


def base_from_camera():
    """4x4 camera -> arm base transform from calib.py, or None (re-read when the file changes)."""
    try:
        m = EXTRINSICS.stat().st_mtime
    except FileNotFoundError:
        return None
    if m != _extr["mtime"]:
        _extr["mtime"], _extr["T"] = m, np.array(json.loads(EXTRINSICS.read_text())["T_base_cam"])
    return _extr["T"]


LIGHT = {"white", "grey"}     # the same white cup reads "grey" in shade or from the head camera (2026-10-20)


def same_colour(asked, seen):
    """True when a thing seen as `seen` counts as the colour `asked` (None: any colour)."""
    return asked is None or asked == seen or {asked, seen} <= LIGHT


def colour_name(bgr_pixels):
    """Dominant colour of an (N, 3) BGR pixel array."""
    if len(bgr_pixels) == 0:
        return None
    hsv = cv2.cvtColor(bgr_pixels.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    vivid = hsv[(hsv[:, 1] >= MIN_SATURATION) & (hsv[:, 2] >= DARK_V)]
    if len(vivid) < 0.25 * len(hsv):
        v = np.median(hsv[:, 2])
        return "white" if v > 170 else "black" if v < DARK_V else "grey"
    hist = np.bincount(vivid[:, 0], minlength=181)
    hist[:8] += hist[170:].sum()                      # red wraps around 0
    hist[170:] = 0
    h = int(np.argmax(np.convolve(hist, np.ones(7), "same")))
    return next(name for top, name in HUES if h < top)


def points(depth, box, intr, T):
    """The depth pixels of the thing in `box` (within FG_MM of its core's depth): (core depth mm, their mask in the
    box, (3, N) points mm in the arm base frame or None when too few / no calibration); (None, None, None) when the
    box's core has too little depth."""
    x1, y1, x2, y2 = box
    d = depth[y1:y2, x1:x2]
    h, w = d.shape
    core = d[h // 4:3 * h // 4, w // 4:3 * w // 4]
    core = core[core > 0]
    if core.size < MIN_POINTS:
        return None, None, None
    dc = float(np.median(core))
    mask = (d > 0) & (np.abs(d - dc) < FG_MM)
    vs, us = np.nonzero(mask)
    if len(vs) < MIN_POINTS or T is None or intr is None:
        return dc, mask, None
    if len(vs) > MAX_POINTS:
        pick = np.random.default_rng(0).choice(len(vs), MAX_POINTS, replace=False)
        vs, us = vs[pick], us[pick]
    z = d[vs, us].astype(np.float64)
    K = np.array([[intr["fx"], 0, intr["cx"]], [0, intr["fy"], intr["cy"]], [0, 0, 1]])
    px = np.stack([us + x1, vs + y1], axis=1).astype(np.float64).reshape(-1, 1, 2)
    n = cv2.undistortPoints(px, K, np.array(intr["dist"])).reshape(-1, 2)
    return dc, mask, T[:3, :3] @ np.stack([n[:, 0] * z, n[:, 1] * z, z]) + T[:3, 3:4]


def measure(color, depth, box, intr, T, round_=False):
    """3D facts of one box: colour, distance (m), centre, top, width, height (mm, arm base frame)."""
    x1, y1, x2, y2 = box
    out = {"colour": colour_name(color[y1:y2, x1:x2].reshape(-1, 3)), "distance_m": None, "position_mm": None,
           "top_mm": None, "width_mm": None, "height_mm": None}
    dc, mask, P = points(depth, box, intr, T)
    if dc is None:
        return out
    out["colour"] = colour_name(color[y1:y2, x1:x2][mask])
    out["distance_m"] = round(dc / 1000, 3)
    if P is None:
        return out
    bottom, top = np.percentile(P[2], EDGE_PCT)
    band = (P[2] > bottom + MID_BAND[0] * (top - bottom)) & (P[2] < bottom + MID_BAND[1] * (top - bottom))
    mid = P[:, band] if band.sum() >= MIN_POINTS // 2 else P
    surface = np.median(mid, axis=1)
    sight = surface[:2] - T[:2, 3]                    # horizontal line of sight from the camera
    sight /= np.linalg.norm(sight) or 1.0
    across = mid[:2].T @ np.array([-sight[1], sight[0]])
    width = float(np.subtract(*np.percentile(across, EDGE_PCT[::-1])))
    centre = np.array([*surface[:2], (top + bottom) / 2])
    if round_:                                        # the camera sees the front; the centre is behind it
        centre[:2] += sight * width / 2 + np.array(ROUND_FIX_MM)
    out.update(position_mm=[round(float(v)) for v in centre], top_mm=round(float(top)), width_mm=round(width),
               height_mm=round(float(top - bottom)))
    return out


def profile(depth, box, intr, T):
    """(slices, lowest z seen) of the upright thing in `box`: slices [(top z of the slice, width)] from the top down,
    SLICE_MM thick, mm in the arm base frame, seen widths (as width_mm); None when not measured."""
    P = points(depth, box, intr, T)[2]
    if P is None:
        return None
    sight = np.median(P[:2], axis=1) - T[:2, 3]
    sight /= np.linalg.norm(sight) or 1.0
    across = P[:2].T @ np.array([-sight[1], sight[0]])
    low, top = np.percentile(P[2], EDGE_PCT)
    slices = []
    for z in np.arange(top, low, -SLICE_MM):
        a = across[(P[2] <= z) & (P[2] > z - SLICE_MM)]
        if len(a) >= SLICE_MIN_POINTS:
            slices.append((float(z), float(np.subtract(*np.percentile(a, EDGE_PCT[::-1])))))
    return (slices, float(low)) if slices else None


def body(depth, box, intr, T):
    """Width profile of an upright bottle in `box` (profile()): {"shoulder_mm": where its body begins (the top of the
    first slice from the top down at least BODY_FRACTION as wide as the body), "body_mm": the body's width (median of
    the slices below that), "low_mm": its lowest point seen}, mm in the arm base frame; None when not measured. Seen
    widths, as width_mm."""
    p = profile(depth, box, intr, T)
    if p is None:
        return None
    slices, low = p
    wide = BODY_FRACTION * np.percentile([w for _, w in slices], BODY_PCT)
    i = next(i for i, (_, w) in enumerate(slices) if w >= wide)
    return {"shoulder_mm": round(slices[i][0]), "body_mm": round(float(np.median([w for _, w in slices[i:]]))),
            "low_mm": round(float(low))}


def measure_all(color, depth, boxes, intr=None, T=None):
    """[{name, score, box, colour, distance_m, position_mm, top_mm, width_mm, height_mm}] for YOLO boxes
    (x1, y1, x2, y2, score, coco_class) of one frame, nearest first. "cut": the object's bottom is below the
    frame, so height_mm and position_mm z are None (top_mm, x, y and width still hold). intr / T default to the
    torso camera's."""
    if intr is None:
        intr = camview.intrinsics(CAMERA)
    if T is None:
        T = base_from_camera()
    result = []
    for x1, y1, x2, y2, score, cls in boxes:
        o = {"name": COCO[cls], "score": round(score, 2), "box": (x1, y1, x2, y2)}
        if depth is None:
            o["colour"] = colour_name(color[y1:y2, x1:x2].reshape(-1, 3))
        else:
            o.update(measure(color, depth, (x1, y1, x2, y2), intr, T, round_=o["name"] in ROUND))
            if y2 >= color.shape[0] - EDGE_PX and o.get("height_mm") is not None:   # the bottom is out of view
                o.update(cut=True, height_mm=None)
                o["position_mm"][2] = None
        if score < SURE_SCORE and not sized_like(o):
            continue
        if (o.get("width_mm") or 0) > WIDEST.get(o["name"], float("inf")):
            continue
        result.append(o)
    result.sort(key=lambda o: o.get("distance_m") or 99)
    return result


def sized_like(o):
    """A weak box is believed only when depth measured a whole object of its class's size (WEAK)."""
    size = WEAK.get(o["name"])
    w, h = o.get("width_mm"), o.get("height_mm")
    return bool(size and w is not None and h is not None and size[0][0] <= w <= size[0][1] and size[1][0] <= h <= size[1][1])


def latest(camera=CAMERA):
    """What the camera service saw last: {"age_s", "objects"}; objects is [] when it is not live. For the head
    camera also "head_pose" [lift, waist, yaw, pitch] the positions were measured at."""
    try:
        d = json.loads(camview.det_path(camera).read_text())
    except (FileNotFoundError, ValueError):
        return {"age_s": None, "objects": []}
    age = time.time() - d.get("time", 0)
    return {"age_s": round(age, 2), "objects": d.get("objects", []) if age < STALE_S else [],
            "head_pose": d.get("head_pose")}


def _print():
    camview.want(CAMERA)
    d = latest()
    if d["age_s"] is None or d["age_s"] >= STALE_S:
        print(f"camera service not live (age {d['age_s']})")
        return
    if not d["objects"]:
        print("no objects")
    for o in d["objects"]:
        print(f"{o['name']:12s} {o.get('colour') or '?':7s} {o['score']:.2f}  dist {o.get('distance_m')} m  "
              f"centre {o.get('position_mm')} mm  width {o.get('width_mm')}  height {o.get('height_mm')}  "
              f"top z {o.get('top_mm')}")


if __name__ == "__main__":
    if "--watch" in sys.argv:
        while True:
            _print()
            print("-" * 40)
            time.sleep(1.0)
    _print()
