"""Self-check of vision/pointing.py with synthetic keypoints and depth, no camera, no robot: python tests/test_pointing.py"""
import math

import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from robot import agv
from tasks import fetch
from vision import pointing, pose, scene


def forbid(*a, **k):
    raise AssertionError("a test reached the robot")


agv.request = agv.go_point = agv.go = agv.cancel = forbid

# --- the words ---
THERE = ["go there", "Go there.", "Lumi, go over there please", "come to where I'm pointing", "go where i am pointing",
         "move that way", "head over there", "저기로 가", "저쪽으로 가 줘", "저기 가", "거기로 가세요", "제가 가리키는 곳으로 가 주세요",
         "루미야 저기로 가", "저기로 go", "go 저기", "there로 가", "저쪽으로 이동해"]
HERE = ["come here", "Come over here.", "여기로 와", "여기 와", "이쪽으로 와 줘", "here로 와", "come 여기"]
NONE = ["put it there", "go to p3", "go there and come back", "저기 뭐 있어?", "what is there", "여기가 어디야",
        "go to the kitchen over there and wave", "there you go", "저기요"]
for t in THERE:
    assert pointing.asked(t) == "there", t
for t in HERE:
    assert pointing.asked(t) == "here", t
for t in NONE:
    assert pointing.asked(t) is None, t

# --- the floor line ---
assert pointing.floor_spot((0, 0, 0), (100, 0, 10), -1400) is None                 # up: never meets the floor
assert pointing.floor_spot((0, 0, 0), (100, 0, -2), -1400) is None                 # almost level: too flat
p = pointing.floor_spot((0, 0, 0), (300, 0, -300), -1400)                           # 45 deg down
assert np.allclose(p, (1400, 0, -1400)), p

# --- a whole frame: camera 1.4 m over the floor looking ahead, base frame x forward, y left, z up ---
W, H = 1280, 720
INTR = {"fx": 600.0, "fy": 600.0, "cx": 640.0, "cy": 360.0, "dist": [0, 0, 0, 0, 0]}
T = np.eye(4)
T[:3, :3] = [[0, 0, 1], [-1, 0, 0], [0, -1, 0]]                                    # camera (x right, y down, z ahead)
FLOOR = -1400.0                                                                    # base z of the floor


def frame(points):
    """A frame whose depth has each base-frame point at its pixel; keypoints {name: point}."""
    depth = np.zeros((H, W), np.uint16)
    kp = np.zeros((17, 3), np.float32)
    Ri = T[:3, :3].T
    for name, P in points.items():
        c = Ri @ (np.asarray(P, float) - T[:3, 3])
        u, v = INTR["fx"] * c[0] / c[2] + INTR["cx"], INTR["fy"] * c[1] / c[2] + INTR["cy"]
        assert 10 < u < W - 10 and 10 < v < H - 10, (name, u, v)
        depth[int(v) - 7:int(v) + 8, int(u) - 7:int(u) + 8] = int(round(c[2]))
        kp[pose.K[name]] = (u, v, 0.9)
    return {"camera": "head", "depth": depth, "intr": INTR, "T": T}, kp


def run(points, pointing_side="right"):
    f, kp = frame(points)
    scene._front = lambda frames: {"pointing": pointing_side, "_f": f, "_kp": kp}
    return pointing.spot([f])


SH = np.array([2500.0, -200.0, FLOOR + 1400])          # the person 2.5 m ahead, right shoulder 1.4 m up
ANK = {"left_ankle": (2500, 100, FLOOR + 80), "right_ankle": (2500, -100, FLOOR + 80)}
d = np.array([-0.5, 0.6, -0.5]) / np.linalg.norm([-0.5, 0.6, -0.5])   # towards the robot's front left, down
pts = {"right_shoulder": SH, "right_wrist": SH + 600 * d, **ANK}
want = SH + (FLOOR - SH[2]) / d[2] * d
r = run(pts)
assert not r["clamped"] and np.hypot(*np.subtract(r["position_mm"][:2], want[:2])) < 40, (r, want)
assert abs(r["position_mm"][2] - FLOOR) < 5, r

assert run(pts, None) == {"why": "not_pointing"}
assert run({k: v for k, v in pts.items() if "ankle" not in k}) == {"why": "no_feet"}
assert run({**pts, "right_wrist": SH + 600 * np.array([0, 0.8, 0.6])}) == {"why": "up"}
scene._front = lambda frames: None
assert pointing.spot([]) == {"why": "nobody"}

d_far = np.array([1.0, 0, -0.12]) / np.linalg.norm([1.0, 0, -0.12])   # away from the robot, shallow: 11+ m
r = run({**pts, "right_wrist": SH + 600 * d_far})
assert r["clamped"] and abs(r["distance_m"] - pointing.MAX_M) < 0.01, r

d_near = np.array([-1.0, 0.05, -0.62])                                  # at the robot's own feet
assert run({**pts, "right_wrist": SH + 600 * d_near / np.linalg.norm(d_near)}) == {"why": "near"}

# --- map pose and room there (fake base) ---
fetch.map_xy = lambda o: np.array([1.0 + o["x"] / 1000, 2.0 + o["y"] / 1000])
agv.pose = lambda: (1.0, 2.0, 0.0)
agv.clearance = lambda x, y: 1.0
scene._front = lambda frames: None
assert pointing.target([]) == {"why": "nobody"}
f, kp = frame(pts)
scene._front = lambda frames: {"pointing": "right", "_f": f, "_kp": kp}
r = pointing.target([f])
x, y, th = r["map"]
assert abs(x - (1 + want[0] / 1000)) < 0.05 and abs(y - (2 + want[1] / 1000)) < 0.05, r
assert abs(th - math.atan2(y - 2.0, x - 1.0)) < 1e-3, r
agv.clearance = lambda x, y: 0.2
assert pointing.target([f])["why"] == "blocked"
fetch.map_xy = lambda o: None
assert pointing.target([f]) == {"why": "no_map"}
for k, (en, ko) in pointing.SAY.items():
    assert en and ko, k

print("pointing: all checks passed")
