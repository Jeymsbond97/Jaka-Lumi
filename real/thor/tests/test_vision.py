"""Self-check of the camera choice in lumi.Vision (head standing, torso driving, fallback), no robot:
python tests/test_vision.py"""
from assistant import lumi

v = lumi.Vision.__new__(lumi.Vision)           # no camera service needed: only pick() is checked
CASES = [   # (preferred, cameras giving detections) -> camera used
    ("head", {"head", "torso"}, "head"),
    ("head", {"torso"}, "torso"),               # head down: torso until it is back
    ("torso", {"head", "torso"}, "torso"),
    ("torso", {"head"}, "head"),
    ("head", set(), "head"),                    # nothing yet (service starting): keep the preferred one
]
for prefer, up, expected in CASES:
    v.prefer = prefer
    lumi.Vision.alive = staticmethod(lambda name, up=up: name in up)
    got = v.pick()
    assert got == expected, (prefer, up, got)

close = {"box": [0, 0, 100, 700], "distance_m": 0.4}
far = {"box": [0, 0, 100, 700], "distance_m": 0.8}
small = {"box": [0, 0, 100, 300], "distance_m": 0.4}     # the arm in front of a person: depth small, box not
assert lumi.too_close([close, far, small], 720) == [close]

# ---------- zoom pass: boxes from the crop are moved to full-frame px; cut ones and repeats are dropped ----------
import numpy as np
from vision import person
d = person.PersonDetector.__new__(person.PersonDetector)
d.name = "torso"
zx1, zy1, zx2, zy2 = person.ZOOM["torso"][0]
real_zoom = person.ZOOM["torso"]
person.ZOOM["torso"] = [real_zoom[0]]
d._detect = lambda crop: [(250, 150, 330, 300, 0.7, 41),                 # a cup inside the crop
                          (0, 100, 50, 200, 0.6, 41),                    # touches the crop's left side: cut
                          (100, 100, 200, 300, 0.8, 0),                  # a person: not an object
                          (10, 10, 60, 60, 0.5, 39)]                     # a bottle the whole frame found too
have = [(zx1 + 12, zy1 + 11, zx1 + 61, zy1 + 59, 0.6, 39)]
got = d._zoomed(np.zeros((720, 1280, 3), np.uint8), have)
assert got == [(250 + zx1, 150 + zy1, 330 + zx1, 300 + zy1, 0.7, 41)], got
# the left crop starts at the frame's edge: a box there is not cut; the same cup in two crops counts once
person.ZOOM["torso"] = [(0, 180, 560, 600), (0, 180, 560, 600)]
d._detect = lambda crop: [(0, 100, 40, 160, 0.5, 41)]
got = d._zoomed(np.zeros((720, 1280, 3), np.uint8), [])
assert got == [(0, 280, 40, 340, 0.5, 41)], got
person.ZOOM["torso"] = real_zoom

# the GPU detector is used when its engine loads; without the engine file the CPU one takes over
import pathlib
real_engine = person.ENGINE
person.ENGINE = pathlib.Path("/nonexistent/yolov8s.engine")
assert isinstance(person.load_net(), person.CvNet)
person.ENGINE = real_engine
assert person.load_net().name.startswith("TensorRT"), person.load_net().name
print("ok: camera choice and too-close check")
