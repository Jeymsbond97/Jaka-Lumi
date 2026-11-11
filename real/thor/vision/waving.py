"""Who is waving: a raised hand that moves side to side, back and forth, from the head camera.

The pose keypoints have no fingers, and a wave from the wrist hardly moves the wrist keypoint (a few px), so the hand
itself is measured: the sideways optical flow in a box over the palm (past the wrist, along the forearm), frame to
frame. A wave is that flow changing direction MIN_FLIPS times within WINDOW_S with the hand above the shoulder. A
hand held up still, a scratch, a phone, pointing or arms swinging while walking give no flips.

    python vision/waving.py tests/data/waves/right_2m     # a recording of vision/wave_record.py, frame by frame

Frames are taken at half size (640 x 360, as recorded); keypoints are full size (1280 x 720, pose.detect).
"""
import sys
from pathlib import Path

import cv2
import numpy as np

from vision import pose

SCALE = 0.5                  # flow frame size / pose frame size
WINDOW_S = 2.0               # s of flow looked at ...
MIN_FLIPS = 2                # ... that has to change direction this often (a slow wave: one swing ~1 s)
FLOW_PX = 1.0                # px per frame (half size) of sideways hand flow that counts as a swing
MIN_MOVING = 20              # flow pixels in the hand box needed to measure the hand at all
PALM = 0.5                   # the palm's centre: this much of the forearm past the wrist
BOX = 0.6                    # half the hand box's side, in forearm lengths
MIN_BOX_PX = 8               # ... at least (half size)
TRACK_PX = 120               # px (full size); a person's shoulder centre moves less than this between frames
LOST_S = 1.0                 # s a person may be unseen before their history is dropped


def _hand(kp):
    """(centre (x, y) half size, half side px) of the higher raised hand, None when no hand is above its shoulder."""
    best = None
    for side in ("left", "right"):
        w, e, s = (pose.seen(kp, f"{side}_{j}") for j in ("wrist", "elbow", "shoulder"))
        if not (w and e and s) or w[1] >= s[1]:
            continue
        fx, fy = w[0] - e[0], w[1] - e[1]
        c = ((w[0] + PALM * fx) * SCALE, (w[1] + PALM * fy) * SCALE)
        r = max(MIN_BOX_PX, BOX * np.hypot(fx, fy) * SCALE)
        if best is None or c[1] < best[0][1]:
            best = (c, r)
    return best


def _flow_x(prev, gray, hand):
    """Median sideways flow (px) of the moving pixels in the hand box, 0 when too little moves there."""
    (cx, cy), r = hand
    x0, y0, x1, y1 = int(max(0, cx - r)), int(max(0, cy - r)), int(cx + r), int(cy + r)
    a, b = prev[y0:y1, x0:x1], gray[y0:y1, x0:x1]
    if min(a.shape) < 8:
        return 0.0
    fx = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 2, 9, 3, 5, 1.1, 0)[..., 0]
    moving = np.abs(fx) > FLOW_PX / 2
    return float(np.median(fx[moving])) if moving.sum() >= MIN_MOVING else 0.0


def _flips(flows):
    s = np.sign([f for f in flows if abs(f) > FLOW_PX])
    return int((np.diff(s) != 0).sum()) if len(s) > 1 else 0


class Watcher:
    """Feed it every frame (update); it keeps a short flow history per person."""

    def __init__(self):
        self.prev = None
        self.tracks = []         # {"at": (x, y) shoulder centre full size, "seen": t, "flows": [(t, flow)]}

    def update(self, t, gray, people):
        """`gray`: the frame at half size, grey; `people`: pose.detect of the full-size frame. Returns
        [(person, waving)] for every person seen, in that order."""
        out = []
        for p in people:
            ls, rs = pose.seen(p["kp"], "left_shoulder"), pose.seen(p["kp"], "right_shoulder")
            if not (ls and rs):
                out.append((p, False))
                continue
            at = ((ls[0] + rs[0]) / 2, (ls[1] + rs[1]) / 2)
            tr = min(self.tracks, key=lambda k: np.hypot(k["at"][0] - at[0], k["at"][1] - at[1]), default=None)
            if tr is None or np.hypot(tr["at"][0] - at[0], tr["at"][1] - at[1]) > TRACK_PX or tr["seen"] == t:
                tr = {"flows": []}
                self.tracks.append(tr)
            tr["at"], tr["seen"] = at, t
            hand = _hand(p["kp"])
            f = _flow_x(self.prev, gray, hand) if hand and self.prev is not None else 0.0
            tr["flows"] = [(ft, v) for ft, v in tr["flows"] if t - ft <= WINDOW_S] + [(t, f)]
            out.append((p, hand is not None and _flips([v for _, v in tr["flows"]]) >= MIN_FLIPS))
        self.tracks = [k for k in self.tracks if t - k["seen"] <= LOST_S]
        self.prev = gray
        return out


def run_recording(folder):
    """[(t, [waving per person])] of a vision/wave_record.py recording."""
    import json
    folder = Path(folder)
    w, out = Watcher(), []
    for line in open(folder.with_suffix(".jsonl")):
        d = json.loads(line)
        gray = cv2.imread(str(folder / f"{d['n']:04d}.jpg"), cv2.IMREAD_GRAYSCALE)
        people = [{**p, "kp": np.array(p["kp"])} for p in d["people"]]
        out.append((d["t"], [v for _, v in w.update(d["t"], gray, people)]))
    return out


if __name__ == "__main__":
    for t, waving in run_recording(sys.argv[1]):
        print(f"{t:.2f}", waving)
