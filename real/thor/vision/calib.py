"""Torso camera -> arm base calibration with the ArUco marker on the gripper (eye-to-hand).

The marker (DICT_4X4_50, id 0, 50 mm black square) is stuck on the gripper body, so it moves rigidly with the
flange. For each sample we store where the arm controller says the flange is (base frame) and where the camera
sees the marker (camera frame). Two unknown fixed transforms link them: camera in the arm base frame and marker
on the flange; solve() finds both (Park & Martin's AX = XB).

    python vision/calib.py collect        # move the arm by hand (Cobo π); every still pose with the marker in view
                                   # is saved and Lumi says "Saved, N". Ctrl+C or MAX_SAMPLES to stop.
    python vision/calib.py solve          # compute camera_extrinsics.json, print the error of every sample
    python vision/calib.py check          # live: marker position from the camera vs from the arm, in mm
    python vision/calib.py clear          # forget the samples

Keep the lift and the waist where they are during a session: the camera turns with the waist and moves with
the lift, the arm base too, but samples from different body poses must not be mixed until that is verified.
"""
import json
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from robot import arm
from vision import camview

ROOT = Path(__file__).resolve().parents[1]      # the project folder
SAMPLES_DIR = ROOT / "data" / "calib_samples"
RESULT = ROOT / "data" / "camera_extrinsics.json"
CAMERA = "torso"
MARKER_ID = 0
MARKER_MM = 50.0                  # black square side, checked with a ruler on the print
STILL_S = 1.5                     # s the joints must not move before a sample is taken
STILL_DEG = 0.05                  # max joint change while "still"
MIN_MOVE_MM, MIN_TURN_DEG = 30.0, 8.0   # a new sample must differ this much from every saved one
MAX_SAMPLES = 30
OUTLIER_FACTOR, OUTLIER_MIN_MM = 3.0, 8.0   # samples off by more than this x the median (and 8 mm) are left out
POLL_S = 0.2

DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
DETECTOR = cv2.aruco.ArucoDetector(DICT, cv2.aruco.DetectorParameters())
H = MARKER_MM / 2
MARKER_POINTS = np.array([[-H, H, 0], [H, H, 0], [H, -H, 0], [-H, -H, 0]], np.float64)   # ArUco corner order


# ---------- poses ----------
EULER = ("Rz Ry Rx", "Rx Ry Rz")   # candidate orders of the controller's (rx, ry, rz); solve() keeps the better one


def rpy_matrix(rx, ry, rz, order=EULER[0]):
    """Rotation of the controller's (rx, ry, rz) in degrees. "Rz Ry Rx" = fixed X, then Y, then Z (roll-pitch-yaw)."""
    a, b, c = np.radians([rx, ry, rz])
    R = {"Rx": np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]]),
         "Ry": np.array([[math.cos(b), 0, math.sin(b)], [0, 1, 0], [-math.sin(b), 0, math.cos(b)]]),
         "Rz": np.array([[math.cos(c), -math.sin(c), 0], [math.sin(c), math.cos(c), 0], [0, 0, 1]])}
    first, second, third = (R[k] for k in order.split())
    return first @ second @ third


def matrix(R, t):
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, np.ravel(t)
    return T


def flange_pose(position, order=EULER[0]):
    """4x4 flange pose in the arm base frame (mm) from get_data's actual_position (tool 0 = flange)."""
    x, y, z, rx, ry, rz = position
    return matrix(rpy_matrix(rx, ry, rz, order), [x, y, z])


def angle_between(R1, R2):
    return math.degrees(math.acos(np.clip((np.trace(R1.T @ R2) - 1) / 2, -1, 1)))


# ---------- camera ----------
def camera_model():
    intr = camview.intrinsics(CAMERA)
    if intr is None:
        sys.exit(f"no intrinsics for the {CAMERA} camera: is the camera service running (camview.py --serve)?")
    K = np.array([[intr["fx"], 0, intr["cx"]], [0, intr["fy"], intr["cy"]], [0, 0, 1]])
    return K, np.array(intr["dist"], np.float64), (intr["width"], intr["height"])


def latest_image():
    camview.want(CAMERA)                                   # keep the service at full speed
    data = camview.raw_path(CAMERA).read_bytes()
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def find_marker(img, K, dist):
    """(4x4 marker pose in the camera frame (mm), corners) or (None, None)."""
    corners, ids, _ = DETECTOR.detectMarkers(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    if ids is None or MARKER_ID not in ids.ravel():
        return None, None
    c = corners[list(ids.ravel()).index(MARKER_ID)][0].astype(np.float64)
    ok, rvec, tvec = cv2.solvePnP(MARKER_POINTS, c, K, dist, flags=cv2.SOLVEPNP_IPPE_SQUARE)
    if not ok:
        return None, None
    return matrix(cv2.Rodrigues(rvec)[0], tvec), c


# ---------- collect ----------
def say(text):
    print(text, flush=True)
    try:
        from audio import mouth
        mouth.say(text)
    except Exception as e:
        print(f"  (cannot speak: {e})", flush=True)


def load_samples():
    return [json.loads(p.read_text()) for p in sorted(SAMPLES_DIR.glob("sample_*.json"))]


def collect():
    K, dist, size = camera_model()
    SAMPLES_DIR.mkdir(exist_ok=True)
    samples = load_samples()
    print(f"camera {CAMERA} {size[0]}x{size[1]}, {len(samples)} samples so far; move the arm, hold it still")
    joints, still_since, warned = None, time.time(), False
    try:
        while len(samples) < MAX_SAMPLES:
            time.sleep(POLL_S)
            try:
                d = arm.cmd("get_data")
                q = np.array(d["joint_actual_position"])
            except (KeyError, OSError, ValueError) as e:   # now and then a reply without the arm state
                print(f"  (arm state unavailable: {e})", flush=True)
                continue
            if joints is None or np.max(np.abs(q - joints)) > STILL_DEG:
                joints, still_since, warned = q, time.time(), False
                continue
            if time.time() - still_since < STILL_S:
                continue
            T_base_flange = flange_pose(d["actual_position"])
            near = [s for s in samples if
                    np.linalg.norm(np.array(s["flange"])[:3, 3] - T_base_flange[:3, 3]) < MIN_MOVE_MM and
                    angle_between(np.array(s["flange"])[:3, :3], T_base_flange[:3, :3]) < MIN_TURN_DEG]
            if near:
                continue                                   # same pose as a saved sample: wait for a new one
            img = latest_image()
            T_cam_marker, corners = find_marker(img, K, dist)
            if T_cam_marker is None:
                if not warned:
                    say("I can't see the marker.")
                    warned = True
                continue
            n = len(samples) + 1
            sample = {"position": d["actual_position"], "flange": T_base_flange.tolist(), "marker": T_cam_marker.tolist(), "corners": corners.tolist(),
                      "joints": q.tolist(), "time": time.time()}
            (SAMPLES_DIR / f"sample_{n:02d}.json").write_text(json.dumps(sample))
            cv2.imwrite(str(SAMPLES_DIR / f"sample_{n:02d}.jpg"), img)
            samples.append(sample)
            print(f"  #{n}: flange {T_base_flange[:3, 3].round(0)} mm, marker {T_cam_marker[2, 3]:.0f} mm "
                  f"from the camera", flush=True)
            say(f"Saved, {n}.")
    except KeyboardInterrupt:
        pass
    print(f"{len(samples)} samples in {SAMPLES_DIR}")


# ---------- solve ----------
def rotation_log(R):
    """Axis * angle (rad) of a rotation matrix."""
    return cv2.Rodrigues(R)[0].ravel()


def mean_rotation(Rs):
    U, _, Vt = np.linalg.svd(sum(Rs))
    D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))])
    return U @ D @ Vt


def solve_ax_xb(As, Bs):
    """X with A X = X B for pairs of relative motions (Park & Martin 1994): rotation from the rotation axes,
    then translation by least squares."""
    alphas = np.array([rotation_log(A[:3, :3]) for A in As])
    betas = np.array([rotation_log(B[:3, :3]) for B in Bs])
    M = betas.T @ alphas                                   # sum of beta alpha^T
    w, V = np.linalg.eigh(M.T @ M)
    R = V @ np.diag(1 / np.sqrt(w)) @ V.T @ M.T             # (M^T M)^-1/2 M^T
    C = np.vstack([A[:3, :3] - np.eye(3) for A in As])
    d = np.concatenate([R @ B[:3, 3] - A[:3, 3] for A, B in zip(As, Bs)])
    t = np.linalg.lstsq(C, d, rcond=None)[0]
    return matrix(R, t)


def refine(flange, marker, T_base_cam, T_flange_marker, iterations=50):
    """Levenberg-Marquardt on the marker centre: camera pose (6) and marker offset on the flange (3) that make
    the camera's and the arm's marker positions agree best. AX = XB weighs rotations, this weighs millimetres."""
    def unpack(p):
        return matrix(cv2.Rodrigues(p[:3])[0], p[3:6]), p[6:9]

    def residuals(p):
        X, offset = unpack(p)
        return np.concatenate([(X @ M)[:3, 3] - (F[:3, :3] @ offset + F[:3, 3]) for F, M in zip(flange, marker)])

    p = np.concatenate([rotation_log(T_base_cam[:3, :3]), T_base_cam[:3, 3], T_flange_marker[:3, 3]])
    lam = 1e-3
    r = residuals(p)
    for _ in range(iterations):
        J = np.empty((r.size, p.size))
        for k in range(p.size):                         # numeric Jacobian: radians and millimetres
            dp = np.zeros(p.size)
            dp[k] = 1e-6 if k < 3 else 1e-3
            J[:, k] = (residuals(p + dp) - r) / dp[k]
        step = np.linalg.solve(J.T @ J + lam * np.diag(np.diag(J.T @ J)), -J.T @ r)
        r_new = residuals(p + step)
        if r_new @ r_new < r @ r:
            p, r, lam = p + step, r_new, lam / 3
            if np.linalg.norm(step) < 1e-6:
                break
        else:
            lam *= 5
    X, offset = unpack(p)
    return X, matrix(T_flange_marker[:3, :3], offset)


def solve(samples, order=EULER[0]):
    """Camera pose in the arm base frame and marker pose on the flange, with the error of each sample.

    Each sample i gives F_i Y = X M_i (F flange in base, Y marker on flange, X camera in base, M marker in
    camera). For two samples: (F_j^-1 F_i) Y = Y (M_j^-1 M_i), an AX = XB problem for Y; X follows."""
    flange = [flange_pose(s["position"], order) for s in samples]
    marker = [np.array(s["marker"]) for s in samples]
    As, Bs = [], []
    for i in range(len(samples)):
        for j in range(i + 1, len(samples)):
            A = np.linalg.inv(flange[j]) @ flange[i]
            if np.degrees(np.linalg.norm(rotation_log(A[:3, :3]))) > 5:   # small turns carry no axis information
                As.append(A)
                Bs.append(np.linalg.inv(marker[j]) @ marker[i])
    if len(As) < 3:
        sys.exit("the samples hardly differ in orientation: tilt the marker differently between samples")
    T_flange_marker = solve_ax_xb(As, Bs)
    Xs = [F @ T_flange_marker @ np.linalg.inv(M) for F, M in zip(flange, marker)]
    T_base_cam = matrix(mean_rotation([X[:3, :3] for X in Xs]), np.mean([X[:3, 3] for X in Xs], axis=0))
    T_base_cam, T_flange_marker = refine(flange, marker, T_base_cam, T_flange_marker)
    errors = []
    for F, M in zip(flange, marker):
        seen = (T_base_cam @ M)[:3, 3]                     # marker centre in the base frame, from the camera
        expected = (F @ T_flange_marker)[:3, 3]           # ... from the arm
        errors.append(float(np.linalg.norm(seen - expected)))
    return T_base_cam, T_flange_marker, errors


def run_solve():
    samples = load_samples()
    if len(samples) < 6:
        sys.exit(f"only {len(samples)} samples: collect at least 6 (better 12-15) with different tilts")
    results = {order: solve(samples, order) for order in EULER}
    order = min(results, key=lambda o: np.median(results[o][2]))
    for o, r in results.items():
        print(f"  angles as {o}: median error {np.median(r[2]):.1f} mm")
    T_base_cam, T_flange_marker, errors = results[order]
    limit = max(OUTLIER_FACTOR * float(np.median(errors)), OUTLIER_MIN_MM)
    bad = [i for i, e in enumerate(errors) if e > limit]
    if bad and len(samples) - len(bad) >= 6:              # an arm still moving, a blurred or steep marker
        print(f"  left out (error > {limit:.1f} mm): samples {[i + 1 for i in bad]}")
        samples = [s for i, s in enumerate(samples) if i not in bad]
        T_base_cam, T_flange_marker, errors = solve(samples, order)
    for i, e in enumerate(errors, 1):
        print(f"  sample {i:2d}: {e:5.1f} mm")
    print(f"error: median {np.median(errors):.1f} mm, max {max(errors):.1f} mm")
    print(f"camera in the arm base frame: {T_base_cam[:3, 3].round(1)} mm")
    print(f"marker on the flange: {T_flange_marker[:3, 3].round(1)} mm")
    RESULT.write_text(json.dumps({
        "camera": CAMERA, "euler": order, "T_base_cam": T_base_cam.tolist(), "T_flange_marker": T_flange_marker.tolist(),
        "samples": len(samples), "median_error_mm": round(float(np.median(errors)), 1),
        "max_error_mm": round(max(errors), 1), "time": time.strftime("%Y-%m-%d %H:%M")}, indent=1))
    print(f"saved {RESULT.name}")


def check():
    K, dist, _ = camera_model()
    res = json.loads(RESULT.read_text())
    T_base_cam, T_flange_marker = np.array(res["T_base_cam"]), np.array(res["T_flange_marker"])
    order = res["euler"]
    print("marker seen by the camera vs where the arm puts it (Ctrl+C to stop)")
    try:
        while True:
            T_cam_marker, _ = find_marker(latest_image(), K, dist)
            expected = (flange_pose(arm.cmd("get_data")["actual_position"], order) @ T_flange_marker)[:3, 3]
            if T_cam_marker is None:
                print("  marker not in view", flush=True)
            else:
                seen = (T_base_cam @ T_cam_marker)[:3, 3]
                print(f"  camera {seen.round(0)}  arm {expected.round(0)}  difference "
                      f"{np.linalg.norm(seen - expected):.1f} mm", flush=True)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "collect":
        collect()
    elif what == "solve":
        run_solve()
    elif what == "check":
        check()
    elif what == "clear":
        for p in SAMPLES_DIR.glob("sample_*"):
            p.unlink()
        print("samples removed")
    else:
        print(__doc__)
