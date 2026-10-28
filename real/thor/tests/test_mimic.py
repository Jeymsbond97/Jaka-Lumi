"""Self-check of tasks/mimic.py without the robot or camera: face angles and the playback plan."""
import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from tasks import mimic
from vision import pose


def face(nose_x, nose_y=100):
    kp = np.zeros((17, 3))
    for n, (x, y) in {"nose": (nose_x, nose_y), "left_eye": (110, 90), "right_eye": (90, 90),
                      "left_ear": (125, 95), "right_ear": (75, 95)}.items():
        kp[pose.K[n]] = (x, y, 0.9)
    return kp


straight, turned = mimic._face(face(100)), mimic._face(face(107))
assert abs(straight[0]) < 1e-6 and turned[0] > 20
assert mimic._face(face(100, 80))[1] > straight[1]               # nose higher: looking up
assert mimic._face(np.zeros((17, 3))) is None

samples = [[t / 10, 30.0 if t >= 10 else 0.0, mimic.PITCH_ZERO] for t in range(30)]
p = mimic.plan(samples, lambda dy, dp: 1.0)
assert len(p) == 1 and p[0][1] == 30.0 and abs(p[0][2] - mimic.PITCH_ZERO) >= 0.5 * 30 - 1e-6 and abs(p[0][0] - 1.0) < 1e-6, p   # one diagonal move, when due
shake = [[t / 10, 20.0 * (-1) ** t, mimic.PITCH_ZERO] for t in range(20)]
p = mimic.plan(shake, lambda dy, dp: 0.5)
assert all(b[0] - a[0] >= 0.5 for a, b in zip(p, p[1:]))        # never two moves at once
print("mimic ok")
