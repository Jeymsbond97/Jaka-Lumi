"""Self-check of objects.measure on a synthetic cup: python tests/test_objects.py"""
import numpy as np

from vision import objects

# camera looking along base +y, base z up (like the real torso camera), 600 mm from a cup of r 40 mm, h 100 mm
T = np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float)
INTR = {"fx": 600.0, "fy": 600.0, "cx": 320.0, "cy": 240.0, "dist": [0.0] * 8}
R, H, D = 40.0, 100.0, 600.0

v, u = np.mgrid[0:480, 0:640]
x, y = (u - 320) / 600, (v - 240) / 600              # ray direction (x, y, 1) in the camera frame
depth = np.full((480, 640), 1500.0)                  # wall behind
a = x * x + 1
b = -2 * D
c = D * D - R * R
disc = b * b - 4 * a * c
hit = disc > 0
z = np.where(hit, (-b - np.sqrt(np.where(hit, disc, 0))) / (2 * a), 0)
cup = hit & (np.abs(y * z) < H / 2)
depth[cup] = z[cup]
color = np.zeros((480, 640, 3), np.uint8)
color[cup] = (30, 30, 200)                            # red in BGR
vs, us = np.nonzero(cup)
box = (us.min() - 5, vs.min() - 5, us.max() + 5, vs.max() + 5)

m = objects.measure(color, depth, box, INTR, T, round_=True)
print(m)
assert m["colour"] == "red"
cx, cy, cz = m["position_mm"]
assert abs(cx) < 5 and abs(cy - D) < 10 and abs(cz) < 5, m
assert abs(m["width_mm"] - 2 * R) < 8, m
assert abs(m["height_mm"] - H) < 12, m
print("objects ok")
