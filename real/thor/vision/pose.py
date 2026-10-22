"""Body keypoints of the people in a colour frame: YOLO11s-pose on the GPU (TensorRT engine), 17 COCO keypoints.

    python vision/pose.py [picture.jpg]     # keypoints of the people in a picture (default: the head camera now)

The engine is built on this Thor from the ONNX file (exported with ultralytics, imgsz 640):
    .venv/bin/python vision/yolo_engine.py models/yolo11s-pose.onnx models/yolo11s-pose.engine
Without the engine (other TensorRT, no GPU) load() returns None and callers say they can't tell.
Left / right are the person's own (their left hand is on the image's right when they face the camera).
"""
import sys
import threading
from pathlib import Path

import cv2
import numpy as np

from vision import person

ROOT = Path(__file__).resolve().parents[1]      # the project folder
ENGINE = ROOT / "models" / "yolo11s-pose.engine"
SIZE = person.SIZE           # 640, the model input
MIN_SCORE = 0.4              # person box score
KP_SEEN = 0.5                # keypoint confidence above this counts as seen
NAMES = ("nose", "left_eye", "right_eye", "left_ear", "right_ear", "left_shoulder", "right_shoulder", "left_elbow",
         "right_elbow", "left_wrist", "right_wrist", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle",
         "right_ankle")
K = {n: i for i, n in enumerate(NAMES)}

_net = {"net": None, "tried": False}
_lock = threading.Lock()


def load():
    """The TensorRT pose net, loaded once; None when it can't be loaded (says why once)."""
    with _lock:
        if not _net["tried"]:
            _net["tried"] = True
            try:
                _net["net"] = person.TrtNet(ENGINE)
            except Exception as e:
                print(f"pose: engine not loaded ({e})", flush=True)
        return _net["net"]


def detect(color):
    """[{box (x1, y1, x2, y2), score, kp: (17, 3) array of x, y px and confidence}] largest first; [] without the net."""
    net = load()
    if net is None:
        return []
    h, w = color.shape[:2]
    scale = SIZE / max(h, w)
    canvas = np.zeros((SIZE, SIZE, 3), np.uint8)                  # letterbox, as person._detect
    canvas[:int(h * scale), :int(w * scale)] = cv2.resize(color, (int(w * scale), int(h * scale)))
    with _lock:                                                   # one CUDA stream and output buffer per net
        out = net.forward(cv2.dnn.blobFromImage(canvas, 1 / 255.0, (SIZE, SIZE), swapRB=True))[0].T.copy()
    out = out[out[:, 4] > MIN_SCORE]                              # (N, 56): cx, cy, w, h, score, 17 x (x, y, conf)
    if not len(out):
        return []
    out[:, :4] /= scale
    boxes = np.stack([out[:, 0] - out[:, 2] / 2, out[:, 1] - out[:, 3] / 2, out[:, 2], out[:, 3]], axis=1)
    keep = np.array(cv2.dnn.NMSBoxes(boxes.tolist(), out[:, 4].tolist(), MIN_SCORE, 0.45)).flatten()
    people = []
    for i in keep:
        x, y, bw, bh = boxes[i]
        kp = out[i, 5:].reshape(17, 3).copy()
        kp[:, :2] /= scale
        people.append({"box": (max(0, int(x)), max(0, int(y)), min(w - 1, int(x + bw)), min(h - 1, int(y + bh))),
                       "score": round(float(out[i, 4]), 2), "kp": kp})
    people.sort(key=lambda p: -(p["box"][2] - p["box"][0]) * (p["box"][3] - p["box"][1]))
    return people


def seen(kp, name):
    """(x, y) of a keypoint when it is seen, else None."""
    x, y, c = kp[K[name]]
    return (float(x), float(y)) if c > KP_SEEN else None


if __name__ == "__main__":
    import time
    img = cv2.imread(sys.argv[1] if len(sys.argv) > 1 else "/dev/shm/lumi_raw_head.jpg")
    detect(img)
    t = time.time()
    people = detect(img)
    print(f"{len(people)} people, {1000 * (time.time() - t):.0f} ms")
    for p in people:
        print(p["box"], p["score"], {n: tuple(int(v) for v in seen(p["kp"], n)) for n in NAMES if seen(p["kp"], n)})
