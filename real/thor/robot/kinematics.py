"""Offline arm kinematics: forward and inverse, fitted to the controller's own answers, so reach planning can be
checked without the robot (tests, dry runs over many cup positions). The robot itself always plans with the
controller's kine_inverse / kine_forward (manipulation/skills.py); this only stands in for them offline.

The model is the vendor URDF's arm chain (l_a1 ... l_a6) with every joint's fixed frame and zero corrected by a
least-squares fit to the calibration samples (joints + the flange pose the controller reported). Held-out samples
and the taught grasps agree within 0.2 mm and 0.05 deg.

    python robot/kinematics.py fit     # refit data/arm_kinematics.json from data/calib_samples*/ (no robot needed)
    python robot/kinematics.py         # the fit's error on every sample
"""
import glob
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]      # the project folder
MODEL_FILE = ROOT / "data" / "arm_kinematics.json"
SAMPLES = ("data/calib_samples/*.json", "data/calib_samples_head/*.json")
URDF_JOINTS = (((0, 0, 0), (3.1416, 1.5708, 0)),                   # jaka_lumi.urdf l_a1 ... l_a6: origin xyz (m), rpy
               ((0, -0.0165, 0.156), (1.5708, -1.5708, 0)),
               ((0.21, 0, -0.029), (0, 0, 0)),
               ((0.1303, 0, 0.0185), (-1.5708, 0, -1.5708)),
               ((0, -0.01805, 0.0802), (1.5708, 1.5708, 0)),
               ((-0.1233, 0, 0.01805), (1.5708, 0, -1.5708)))
IK_ITERS = 30                                    # Newton steps at most (a reachable pose took at most 19)
IK_TOL_MM, IK_TOL_RAD = 0.01, 1e-5               # converged when the pose is this close
IK_STEP_DEG = 20.0                               # no joint turns more than this in one step (keeps the seed's branch)


def _rpy(r, p, y):
    """R = Rz(y) Ry(p) Rx(r) (URDF and the controller's convention), radians."""
    cr, sr, cp, sp, cy, sy = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(y), math.sin(y)
    return np.array([[cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
                     [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
                     [-sp, cp * sr, cp * cr]])


def _frame(xyz, rpy):
    A = np.eye(4)
    A[:3, :3], A[:3, 3] = _rpy(*rpy), xyz
    return A


def _frames(p):
    """(base, [joint frames], [zero offsets rad]) of a parameter vector: base xyz rpy, then per joint dxyz drpy dq."""
    joints = [_frame(np.array(xyz) * 1000.0 + p[6 + 7 * i:9 + 7 * i], np.array(rpy) + p[9 + 7 * i:12 + 7 * i])
              for i, (xyz, rpy) in enumerate(URDF_JOINTS)]
    return _frame(p[:3], p[3:6]), joints, [p[12 + 7 * i] for i in range(6)]


_model = None


def _load():
    global _model
    if _model is None:
        d = json.loads(MODEL_FILE.read_text())
        _model = (np.array(d["base"]), [np.array(f) for f in d["joints"]], d["offsets_rad"])
    return _model


def chain(joints, model=None):
    """[4x4] of the arm base, then the frame of each joint after its turn (mm); the last one is the flange."""
    base, frames, offsets = model or _load()
    T, out = base, [base]
    for F, q, off in zip(frames, joints, offsets):
        T = T @ F
        a = math.radians(q) + off
        c, s = math.cos(a), math.sin(a)
        T = T.copy()
        T[:, :2] = np.stack([c * T[:, 0] + s * T[:, 1], c * T[:, 1] - s * T[:, 0]], axis=1)   # T @ Rz(a)
        out.append(T)
    return out


def fk(joints, model=None):
    """Flange 4x4 (mm) in the arm base frame, as the controller's kine_forward gives it."""
    return chain(joints, model)[-1]


def pose(joints):
    """[x, y, z mm, rx, ry, rz deg] of the flange (R = Rz Ry Rx, like the controller)."""
    T = fk(joints)
    R = T[:3, :3]
    return [float(v) for v in T[:3, 3]] + [math.degrees(math.atan2(R[2, 1], R[2, 2])),
                                           math.degrees(math.asin(max(-1.0, min(1.0, -R[2, 0])))),
                                           math.degrees(math.atan2(R[1, 0], R[0, 0]))]


def _rotvec(R):
    """Rotation vector (rad) of a rotation matrix."""
    a = math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2)))
    if a < 1e-9:
        return np.zeros(3)
    v = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]])
    if math.pi - a < 1e-6:                       # half a turn: the axis from the symmetric part
        w = np.sqrt(np.maximum((np.diag(R) + 1) / 2, 0))
        return a * w
    return a * v / (2 * math.sin(a))


def ik(target, seed):
    """Joints (deg) putting the flange at `target` [x, y, z, rx, ry, rz], found from `seed` by Newton steps (so the
    answer is the solution of the seed's arm configuration, like the controller's nearest-to-reference answer);
    None when it does not converge (out of reach). Joint limits are not checked here (motion.check does)."""
    goal = _frame(target[:3], [math.radians(v) for v in target[3:]])
    q = np.array(seed, float)
    for _ in range(IK_ITERS):
        frames = chain(q)
        T = frames[-1]
        e = np.concatenate([goal[:3, 3] - T[:3, 3], T[:3, :3] @ _rotvec(T[:3, :3].T @ goal[:3, :3])])
        if np.linalg.norm(e[:3]) < IK_TOL_MM and np.linalg.norm(e[3:]) < IK_TOL_RAD:
            return [float(v) for v in (q + 180.0) % 360.0 - 180.0]   # the same pose; within +-180 like a fresh answer
        F = np.array(frames[1:7])
        Z, O = F[:, :3, 2], F[:, :3, 3]                                  # each joint's axis and origin
        d = T[:3, 3] - O
        J = np.vstack([np.array([Z[:, 1] * d[:, 2] - Z[:, 2] * d[:, 1], Z[:, 2] * d[:, 0] - Z[:, 0] * d[:, 2],
                                 Z[:, 0] * d[:, 1] - Z[:, 1] * d[:, 0]]), Z.T])   # axis x (flange - origin), axis
        e[3:] *= 100.0                           # 1 rad weighs as 100 mm
        J[3:] *= 100.0
        dq = np.degrees(np.linalg.lstsq(J, e, rcond=None)[0])
        q = q + dq * min(1.0, IK_STEP_DEG / max(np.abs(dq).max(), 1e-9))
    return None


def ask(name, **args):
    """Offline stand-in for skills._ask: kine_forward / kine_inverse answers shaped like the controller's."""
    if name == "kine_forward":
        return {"errorCode": "0", "cartPosition": pose(args["jointPosition"])}
    if name == "kine_inverse":
        j = ik(args["cartPosition"], args["jointPosition"])
        return {"errorCode": "-4"} if j is None else {"errorCode": "0", "jointPosition": j}
    raise ValueError(f"offline kinematics has no {name}")


# ---------- fitting ----------
def _samples():
    out = []
    for pattern in SAMPLES:
        for f in sorted(glob.glob(str(ROOT / pattern))):
            s = json.loads(Path(f).read_text())
            out.append((s["joints"], np.array(s["flange"], float)))
    return out


def _residual(p, samples):
    model = _frames(p)
    r = []
    for j, F in samples:
        T = fk(j, model)
        r += list(T[:3, 3] - F[:3, 3]) + list(100.0 * (T[:3, :3] - F[:3, :3]).ravel())
    return np.array(r)


def fit(iters=60):
    """Levenberg-Marquardt fit of the corrections to the samples; writes MODEL_FILE. The base starts from a rigid
    fit of the plain URDF's flange positions."""
    samples = _samples()
    p = np.zeros(6 + 7 * 6)
    P = np.array([fk(j, _frames(p))[:3, 3] for j, _ in samples])
    X = np.array([F[:3, 3] for _, F in samples])
    U, _, Vt = np.linalg.svd((P - P.mean(0)).T @ (X - X.mean(0)))
    R = Vt.T @ np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))]) @ U.T
    p[:3] = X.mean(0) - R @ P.mean(0)
    p[3:6] = [math.atan2(R[2, 1], R[2, 2]), math.asin(-R[2, 0]), math.atan2(R[1, 0], R[0, 0])]
    lam = 1e-2
    for _ in range(iters):
        r0 = _residual(p, samples)
        J = np.stack([(_residual(p + d, samples) - r0) / 1e-4 for d in np.eye(len(p)) * 1e-4], axis=1)
        A = J.T @ J
        step = np.linalg.solve(A + lam * np.eye(len(p)) + 1e-3 * np.diag(np.diag(A)), -J.T @ r0)
        if np.sum(_residual(p + step, samples) ** 2) < np.sum(r0 ** 2):
            p, lam = p + step, lam * 0.5
        else:
            lam *= 10
    base, frames, offsets = _frames(p)
    MODEL_FILE.write_text(json.dumps({"note": "robot/kinematics.py fit: URDF arm chain corrected to the controller",
                                      "base": base.tolist(), "joints": [f.tolist() for f in frames],
                                      "offsets_rad": [float(v) for v in offsets]}, indent=1))
    global _model
    _model = None


def errors():
    """(largest mm, largest deg) between the model and every sample."""
    mm, deg = [], []
    for j, F in _samples():
        T = fk(j)
        mm.append(float(np.linalg.norm(T[:3, 3] - F[:3, 3])))
        deg.append(math.degrees(math.acos(min(1.0, (np.trace(T[:3, :3].T @ F[:3, :3]) - 1) / 2))))
    return max(mm), max(deg)


if __name__ == "__main__":
    if sys.argv[1:] == ["fit"]:
        fit()
    print("largest error: %.2f mm, %.3f deg" % errors())
