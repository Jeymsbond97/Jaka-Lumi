"""Head camera -> arm base transform at any head yaw / pitch.

calib.py --camera head gives the camera pose at one head pose (yaw 0, pitch -5, saved as "body" in
camera_extrinsics_head.json). The head turns about a vertical yaw axis and a horizontal pitch axis; both are measured
here in the arm base frame: the arm holds the gripper marker still, the head moves through small steps, and the
marker poses the camera sees give each axis. The lift and the waist carry the arm and the head together, so they
do not change the transform.

    python vision/head_cam.py measure yaw     # arm still with the marker in view; the head turns -30..0 deg
    python vision/head_cam.py measure pitch   # marker in the upper part of the view; the head tilts -5..+4 deg
    python vision/head_cam.py fit             # axes from both measurements -> camera_extrinsics_head.json
    python vision/head_cam.py check           # live: marker from the head camera vs from the arm, at the head pose now

Measured 2026-10-19: yaw -30..0 deg and pitch -5..+4 deg, the model within 11 mm / 1.4 deg of every pose seen.
Larger turns (yaw > 0, pitch > 4) are extrapolated.
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from robot import arm, head

ROOT = Path(__file__).resolve().parents[1]      # the project folder
RESULT = ROOT / "data" / "camera_extrinsics_head.json"
MEASURED = {"yaw": ROOT / "data" / "head_axes_yaw.json", "pitch": ROOT / "data" / "head_axes_pitch.json"}
STEPS = {"yaw": [(y, -5) for y in (0, -10, -20, -30, -10, 0)],     # (yaw, pitch) deg; the marker must stay in view
         "pitch": [(0, p) for p in (-5, -2, 1, 4, -5)] + [(-20, p) for p in (-5, -1, 3, -5)] + [(0, -5)]}
SETTLE_S = 1.5                  # s after a head move before the frames are read
FRAMES = 6                      # marker poses averaged per head pose
MIN_TURN_DEG = 2.0              # head poses closer than this to the reference give no axis direction

_cache = {"mtime": None, "data": None}


def _load():
    try:
        m = RESULT.stat().st_mtime
    except FileNotFoundError:
        return None
    if m != _cache["mtime"]:
        _cache["mtime"], _cache["data"] = m, json.loads(RESULT.read_text())
    return _cache["data"]


def _rot(axis, deg):
    return cv2.Rodrigues(np.asarray(axis, float) / np.linalg.norm(axis) * np.radians(deg))[0]


def base_from_head(yaw, pitch):
    """4x4 head camera -> arm base transform at head (yaw, pitch) deg, or None before calib.py and fit have run."""
    d = _load()
    if d is None or "pitch_axis" not in d:
        return None
    X = np.array(d["T_base_cam"])
    ref_yaw, ref_pitch = d["body"][2], d["body"][3]
    yp, yu = np.array(d["yaw_axis"]["point"]), np.array(d["yaw_axis"]["dir"])
    pp, pu = np.array(d["pitch_axis"]["point"]), np.array(d["pitch_axis"]["dir"])   # as at the reference yaw
    Rp, Ry = _rot(pu, pitch - ref_pitch), _rot(yu, yaw - ref_yaw)
    out = np.eye(4)
    out[:3, :3] = Ry @ Rp @ X[:3, :3]
    out[:3, 3] = yp + Ry @ (pp + Rp @ (X[:3, 3] - pp) - yp)
    return out


def head_centre():
    """The head's turning centre (mm, arm base frame): midway between the closest points of the yaw and the pitch
    axis (27 mm apart in the 2026-10-19 fit). Fixed at any head pose and lift; None before fit has run."""
    d = _load()
    if d is None or "pitch_axis" not in d:
        return None
    p, u = np.array(d["yaw_axis"]["point"]), np.array(d["yaw_axis"]["dir"])
    q, v = np.array(d["pitch_axis"]["point"]), np.array(d["pitch_axis"]["dir"])
    w, b = p - q, u @ v
    den = (u @ u) * (v @ v) - b * b
    s, t = (b * (v @ w) - (v @ v) * (u @ w)) / den, ((u @ u) * (v @ w) - b * (u @ w)) / den
    return (p + s * u + q + t * v) / 2


def base_from_head_now():
    """base_from_head at the head pose the body reports now (None when unknown)."""
    _, _, yaw, pitch = head.status()
    return base_from_head(yaw, pitch)


# ---------- measuring ----------
def _flange():
    for _ in range(10):                          # get_data now and then answers without the arm state
        try:
            return arm.cmd("get_data")["actual_position"]
        except (KeyError, OSError, ValueError):
            time.sleep(0.2)
    raise RuntimeError("no arm state")


def _orthonormal(R):
    U, _, Vt = np.linalg.svd(R)
    return U @ Vt


def measure(which):
    """Move the head through STEPS[which] (slowly, lift and waist stay) and save the marker pose at each."""
    from vision import calib
    calib.CAMERA = "head"
    K, dist, _ = calib.camera_model()
    lift, waist, yaw0, pitch0 = head.status()
    start, rows = _flange(), []
    for yaw, pitch in STEPS[which]:
        head.moveto([lift, waist, yaw, pitch], vel=20, acc=20)
        time.sleep(SETTLE_S)
        seen = []
        for _ in range(FRAMES):
            T, _ = calib.find_marker(calib.latest_image(), K, dist)
            if T is not None:
                seen.append(T)
            time.sleep(0.15)
        moved = float(np.linalg.norm(np.subtract(_flange()[:3], start[:3])))
        if moved > 1.0:
            sys.exit(f"the arm moved {moved:.1f} mm: keep it still and start again")
        T = None
        if seen:
            T = np.mean(seen, axis=0)
            T[:3, :3] = _orthonormal(T[:3, :3])
        rows.append({"body": head.status(), "T_cam_marker": None if T is None else T.tolist()})
        print(f"yaw {yaw:4.0f} pitch {pitch:4.0f}: marker {'not seen' if T is None else T[:3, 3].round(0)}",
              flush=True)
    head.moveto([lift, waist, yaw0, pitch0], vel=20, acc=20)
    MEASURED[which].write_text(json.dumps(rows))
    print(f"saved {MEASURED[which].name}")


def _camera_poses(rows, X0, ref):
    """(yaw, pitch, camera pose in the arm frame) of every row, through the marker that stays put."""
    rows = [r for r in rows if r["T_cam_marker"]]
    at_ref = [r for r in rows if abs(r["body"][2] - ref[0]) < 0.5 and abs(r["body"][3] - ref[1]) < 0.5]
    if not at_ref:
        sys.exit("no row at the calibration's head pose: measure again")
    M = X0 @ np.array(at_ref[0]["T_cam_marker"])                      # the marker in the arm frame
    return [(r["body"][2], r["body"][3], M @ np.linalg.inv(np.array(r["T_cam_marker"]))) for r in rows]


def _axis(poses, X0, sign_of):
    """(point, unit direction) of the rotation taking X0 to each pose; the direction turned so that a positive
    angle (sign_of(pose) > 0) is a positive rotation."""
    A, b, dirs = [], [], []
    for p in poses:
        R = p[2][:3, :3] @ X0[:3, :3].T
        A.append(np.eye(3) - R)                   # rotation about a line through c: t' - c = R (t - c)
        b.append(p[2][:3, 3] - R @ X0[:3, 3])
        rv = cv2.Rodrigues(R)[0].ravel()
        if np.degrees(np.linalg.norm(rv)) >= MIN_TURN_DEG:
            dirs.append(rv / np.linalg.norm(rv) * np.sign(sign_of(p)))
    point = np.linalg.lstsq(np.vstack(A), np.concatenate(b), rcond=None)[0]
    u = np.mean(dirs, axis=0)
    return point, u / np.linalg.norm(u)


def fit():
    d = json.loads(RESULT.read_text())
    X0, ref = np.array(d["T_base_cam"]), (d["body"][2], d["body"][3])
    yaw_rows = [p for p in _camera_poses(json.loads(MEASURED["yaw"].read_text()), X0, ref)
                if abs(p[1] - ref[1]) < 0.5]
    pitch_rows = [p for p in _camera_poses(json.loads(MEASURED["pitch"].read_text()), X0, ref)
                  if abs(p[0] - ref[0]) < 0.5]
    yp, yu = _axis(yaw_rows, X0, lambda p: p[0] - ref[0])
    pp, pu = _axis(pitch_rows, X0, lambda p: p[1] - ref[1])
    d["yaw_axis"] = {"point": yp.round(1).tolist(), "dir": yu.round(4).tolist()}
    d["pitch_axis"] = {"point": pp.round(1).tolist(), "dir": pu.round(4).tolist()}
    d["axes_time"] = time.strftime("%Y-%m-%d %H:%M")
    RESULT.write_text(json.dumps(d, indent=1))
    print(f"yaw axis through {yp.round(1)} along {yu.round(3)}; pitch axis through {pp.round(1)} along {pu.round(3)}")
    worst = 0.0
    for yaw, pitch, X in _camera_poses(json.loads(MEASURED["yaw"].read_text()), X0, ref) + \
            _camera_poses(json.loads(MEASURED["pitch"].read_text()), X0, ref):
        P = base_from_head(yaw, pitch)
        e = float(np.linalg.norm(P[:3, 3] - X[:3, 3]))
        a = float(np.degrees(np.linalg.norm(cv2.Rodrigues(P[:3, :3] @ X[:3, :3].T)[0])))
        worst = max(worst, e)
        print(f"  yaw {yaw:6.1f} pitch {pitch:5.1f}: camera {e:4.1f} mm, {a:4.2f} deg off")
    print(f"saved {RESULT.name}; worst {worst:.1f} mm")


def check():
    from vision import calib
    calib.CAMERA = "head"
    K, dist, _ = calib.camera_model()
    d = _load()
    order, T_flange_marker = d["euler"], np.array(d["T_flange_marker"])
    print("marker from the head camera vs from the arm, at the head pose now (Ctrl+C to stop)")
    try:
        while True:
            T, _ = calib.find_marker(calib.latest_image(), K, dist)
            expected = (calib.flange_pose(_flange(), order) @ T_flange_marker)[:3, 3]
            if T is None:
                print("  marker not in view", flush=True)
            else:
                seen = (base_from_head_now() @ T)[:3, 3]
                print(f"  head {head.status()[2:]}  camera {seen.round(0)}  arm {expected.round(0)}  difference "
                      f"{np.linalg.norm(seen - expected):.1f} mm", flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    what = sys.argv[1:2]
    if what == ["measure"] and sys.argv[2:3] in (["yaw"], ["pitch"]):
        measure(sys.argv[2])
    elif what == ["fit"]:
        fit()
    elif what == ["check"]:
        check()
    else:
        print(__doc__)
