"""Head moves copied from a person: record how someone moves their head in front of the head camera, play it back
with Lumi's head.

    python tasks/mimic.py record nod 10      # 10 s; look straight at the camera for the first second
    python tasks/mimic.py show nod           # the recorded angles, nothing moves
    python tasks/mimic.py play nod           # Lumi's head does it (moves the head)

The person's head turn and nod come from the face keypoints of the pose net (nose against the ears / eyes), relative
to the first second (looking straight). Only yaw and pitch: Lumi's head has no roll. As in a mirror: the person turns
to their left, Lumi turns to its right. The body API's moveto blocks and the head turns ~40 deg/s, so the playback
goes from one recorded pose to the one due when the last move ended: fast shakes come out smaller and slower.
"""
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from robot import head
from vision import camview, pose

ROOT = Path(__file__).resolve().parents[1]
MOVES = ROOT / "data" / "head_moves"
CAMERA = "head"
NEUTRAL_S = (0.3, 1.5)       # s of the recording the person looks straight (the zero); the first 0.3 s they settle
YAW_GAIN = 2.0               # Lumi's yaw per degree of the face turn read from the eyes (it reads low); estimate,
                             # tune live
PITCH_GAIN = 140.0           # deg per unit of nose height change / eye distance; estimate, tune live
MIRROR = True                # the person's left = Lumi's right, as in a mirror
SMOOTH = 3                   # samples in the running median (15 fps camera)
YAW_MAX = head.YAW_LIMIT     # deg
PITCH_ZERO = 12.0            # deg, Lumi's pitch for the person's straight look (room to look down to -5)
MIN_MOVE = 2.0               # deg; smaller changes are not sent
CROSS = 0.5                  # a move along one axis gets this much of its size on the other axis, the side
                             # alternating: diagonal moves, never one axis alone (owner)
VEL = 70                     # speed ratio %; the head is at full speed from ~50


def _face(kp):
    """(turn deg, nod) of a face, or None. The turn comes from where the nose sits between the eyes (ears drop out
    in a side view, which made the old ear-based turn jump); the nod is the nose height under the eyes over the eye
    distance, the eye distance corrected for the turn."""
    nose = pose.seen(kp, "nose")
    ley, rey = pose.seen(kp, "left_eye"), pose.seen(kp, "right_eye")
    if nose is None or ley is None or rey is None:
        return None
    dl, dr = abs(nose[0] - ley[0]), abs(nose[0] - rey[0])
    if dl + dr < 4:
        return None
    r = float(np.clip((dr - dl) / (dl + dr), -0.99, 0.99))     # + : the nose toward the image's right
    eyes = abs(ley[0] - rey[0]) / np.sqrt(1 - r * r) or 1.0
    return np.degrees(np.arcsin(r)), ((ley[1] + rey[1]) / 2 - nose[1]) / eyes


def record(name, seconds):
    """Samples [t s, yaw deg, pitch deg] of the biggest face for `seconds`, saved to data/head_moves/<name>.json."""
    path, last, raw = camview.raw_path(CAMERA), 0.0, []
    start = time.time()
    while time.time() - start < seconds:
        m = os.stat(path).st_mtime
        if m == last:
            time.sleep(0.01)
            continue
        last = m
        img = cv2.imread(str(path))
        people = pose.detect(img) if img is not None else []
        f = _face(people[0]["kp"]) if people else None
        if f:
            raw.append((time.time() - start, *f))
    if len(raw) < 10:
        raise SystemExit(f"saw a face in {len(raw)} frames only: stand in front of the head camera")
    out = _samples(raw)
    MOVES.mkdir(exist_ok=True)
    (MOVES / f"{name}.json").write_text(json.dumps({"samples": out, "raw": [[round(float(x), 4) for x in r] for r in raw]}))
    return out


def _samples(raw):
    """[t s, yaw deg, pitch deg] for Lumi from the face readings [t, turn deg, nod], relative to the straight look."""
    zero = [s for s in raw if NEUTRAL_S[0] <= s[0] < NEUTRAL_S[1]] or raw[:10]
    t0, n0 = np.median([s[1] for s in zero]), np.median([s[2] for s in zero])
    side = -1 if MIRROR else 1
    out = []
    for i in range(len(raw)):
        w = raw[max(0, i - SMOOTH + 1):i + 1]
        turn, nod = np.median([s[1] for s in w]), np.median([s[2] for s in w])
        out.append([round(raw[i][0], 2), round(float(np.clip(side * (turn - t0) * YAW_GAIN, -YAW_MAX, YAW_MAX)), 1),
                    round(float(np.clip(PITCH_ZERO + (nod - n0) * PITCH_GAIN, *head.PITCH_RANGE)), 1)])
    return out


def load(name):
    d = json.loads((MOVES / f"{name}.json").read_text())
    return _samples(d["raw"]) if d.get("raw") else d["samples"]       # the raw readings: today's gains


def _diagonal(cur, y, p, side):
    """The pose (y, p) moved so the step from cur changes both axes: the smaller one gets at least CROSS of the bigger,
    to `side` (+1 / -1), kept inside the limits."""
    dy, dp = y - cur[0], p - cur[1]
    if abs(dp) < CROSS * abs(dy):
        p = cur[1] + side * CROSS * abs(dy)
        if not head.PITCH_RANGE[0] <= p <= head.PITCH_RANGE[1]:
            p = cur[1] - side * CROSS * abs(dy)
    elif abs(dy) < CROSS * abs(dp):
        y = cur[0] + side * CROSS * abs(dp)
    return float(np.clip(y, -YAW_MAX, YAW_MAX)), float(np.clip(p, *head.PITCH_RANGE))


def plan(samples, move_s):
    """The poses to send: from each move's end, the pose due then. move_s(dyaw, dpitch) = s a move takes."""
    out, t, cur, i = [], 0.0, (0.0, PITCH_ZERO), 0
    rec = cur                                            # the recorded pose last sent (cur is it made diagonal)
    while i < len(samples):
        while i + 1 < len(samples) and samples[i + 1][0] <= t:
            i += 1
        _, y, p = samples[i]
        if max(abs(y - rec[0]), abs(p - rec[1])) >= MIN_MOVE:
            rec = (y, p)
            y, p = _diagonal(cur, y, p, len(out) % 2 * 2 - 1)
            out.append((t, y, p))
            t += move_s(y - cur[0], p - cur[1])
            cur = (y, p)
        elif i + 1 < len(samples):
            t = samples[i + 1][0]
        else:
            break
    return out


def play(name, head_api=head):
    from audio import sing
    lift, waist, _, _ = head_api.status()
    start = time.time()
    try:
        for due, y, p in plan(load(name), lambda dy, dp: sing.move_time(dy, dp, VEL)):
            wait = due - (time.time() - start)
            if wait > 0:
                time.sleep(wait)
            head_api.moveto([lift, waist, y, p], VEL, VEL)       # blocks: never two moves at once
    finally:
        head_api.moveto([lift, waist, 0.0, 0.0], VEL, VEL)


if __name__ == "__main__":
    what, name = sys.argv[1], sys.argv[2]
    if what == "record":
        secs = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
        print("look straight at the head camera... go")
        s = record(name, secs)
        print(f"{len(s)} samples, yaw {min(x[1] for x in s)}..{max(x[1] for x in s)}, "
              f"pitch {min(x[2] for x in s)}..{max(x[2] for x in s)}")
    elif what == "show":
        for s in load(name):
            print(*s)
    elif what == "play":
        play(name)
