"""Record people's keypoints from the head camera while Lumi reads out what to do: the waves (and the non-waves) the
wave greeting is tuned and tested on. Moves nothing; Lumi only speaks (POST /say).

    python vision/wave_record.py [first_step]     # writes tests/data/waves/<label>.jsonl and <label>/<n>.jpg

One line per frame: {t, n, people: [{box, kp (17 x [x, y, conf]), dist_m}]}; frame n at half size (640 x 360), for the
hand's own motion (the keypoints have no fingers: a wave from the wrist hardly moves the wrist keypoint). People in
the pictures: tests/data/waves/ stays local (.gitignore).
"""
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from vision import camview, pose

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "data" / "waves"
CAM = "head"
READY_S = 5                  # from the instruction to "Go": time to walk to the distance

# (label, what Lumi says, seconds recorded)
STEPS = [
    ("right_1m", "Stand one metre in front of me. Wave with your right hand.", 8),
    ("left_1m", "Now wave with your left hand.", 8),
    ("right_2m", "Step back to two metres. Wave with your right hand.", 8),
    ("left_2m", "Now your left hand.", 8),
    ("right_3m", "Step back to three metres. Wave with your right hand.", 8),
    ("left_3m", "Now your left hand.", 8),
    ("slow_2m", "Come to two metres. Wave slowly.", 8),
    ("fast_2m", "Now wave fast.", 8),
    ("pause_2m", "Wave, stop for three seconds when I say pause, then wave again.", 12),
    ("edge_left", "Go to the far left of my view and wave.", 8),
    ("edge_right", "Now the far right of my view, and wave.", 8),
    ("walk_wave", "Walk past me from one side to the other, waving.", 10),
    ("no_raised", "Two metres in front of me. Hold one hand up, still, like asking a question.", 6),
    ("no_scratch", "Scratch your head.", 6),
    ("no_phone", "Hold a phone to your ear and talk.", 6),
    ("no_point", "Point at something, then at another thing.", 6),
    ("no_glasses", "Touch your face or fix your hair.", 6),
    ("no_walk", "Walk past me from one side to the other, swinging your arms, no wave.", 10),
    ("no_still", "Just stand still.", 6),
]


def say(text):
    req = urllib.request.Request("http://localhost:8100/say", json.dumps({"text": text}).encode(),
                                 {"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except OSError as e:
        print(f"say failed ({e}): {text}", flush=True)


def dist_m(depth, kp):
    """Median head-camera depth around the shoulders' middle, m; None without depth."""
    ls, rs = pose.seen(kp, "left_shoulder"), pose.seen(kp, "right_shoulder")
    if depth is None or not (ls and rs):
        return None
    x, y = int((ls[0] + rs[0]) / 2), int((ls[1] + rs[1]) / 2)
    patch = depth[max(0, y - 6):y + 7, max(0, x - 6):x + 7]
    v = patch[patch > 0]
    return round(float(np.median(v)) / 1000, 2) if v.size >= 5 else None


def record(label, seconds, pause_at=None):
    raw = camview.raw_path(CAM)
    last, n = 0.0, 0
    (OUT / label).mkdir(exist_ok=True)
    t_end = time.time() + seconds
    with open(OUT / f"{label}.jsonl", "w") as f:
        while time.time() < t_end:
            camview.want(CAM)
            if pause_at and time.time() > t_end - seconds + pause_at:     # spoken aside, the frames keep coming
                threading.Thread(target=lambda: (say("Pause."), time.sleep(3), say("Wave again.")), daemon=True).start()
                pause_at = None
            try:
                m = raw.stat().st_mtime
            except FileNotFoundError:
                m = last
            if m == last:
                time.sleep(0.01)
                continue
            last = m
            img = cv2.imread(str(raw))
            if img is None:
                continue
            depth = camview.depth(CAM)
            people = [{"box": p["box"], "kp": np.round(p["kp"].astype(float), 1).tolist(), "dist_m": dist_m(depth, p["kp"])}
                      for p in pose.detect(img)]
            f.write(json.dumps({"t": round(m, 3), "n": n, "people": people}) + "\n")
            cv2.imwrite(str(OUT / label / f"{n:04d}.jpg"), cv2.resize(img, (640, 360)), [cv2.IMWRITE_JPEG_QUALITY, 90])
            n += 1
    print(f"{label}: {n} frames, {n / seconds:.1f} per s", flush=True)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    pose.load()
    first = sys.argv[1] if len(sys.argv) > 1 else STEPS[0][0]
    steps = STEPS[[s[0] for s in STEPS].index(first):]
    say("Let's record waves. Do what I say after I say go.")
    for label, text, seconds in steps:
        print(f"-- {label}", flush=True)
        say(text)
        time.sleep(READY_S)
        say("Go.")
        record(label, seconds, pause_at=4 if label == "pause_2m" else None)
        say("Stop.")
        time.sleep(1)
    say("All done, thank you.")
