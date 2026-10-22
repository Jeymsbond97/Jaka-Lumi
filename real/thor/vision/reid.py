"""Know a person again after they leave the view for a while: the face when it is seen, else the clothes' colours.

    look(color, box) -> [floats]          clothes signature of one person in one frame
    face(color, box) -> [128 floats]|None face embedding of a near person facing the camera (YuNet + SFace, CPU)
    same(a, b) -> 0..1                    how alike two clothes signatures are (Bhattacharyya, averaged over the parts)
    People()                              whom Lumi has met: .recall(look, face, now, taken), .add(look, face, now)

The camera service adds "look" (and "face" for people within FACE_MAX_M) to every person it detects. Faces decide
when both sides have one: many people here wear white shirts, the colours alone mixed up different people (0.83 for
two people, tests/data scenes). Without a face (turned away) the clothes decide. Numbers only: no picture is kept,
and People lives in lumi.py's memory (gone on restart and after FORGET_S); the embeddings never reach the disk.

Clothes: hue-saturation histograms with a brightness histogram for the colourless pixels (white, grey, black), one of
the upper body and one of the legs, from the middle half of the box (less background).
Models (models/, from github.com/opencv/opencv_zoo): face_detection_yunet_2023mar.onnx,
face_recognition_sface_2021dec.onnx. Without them face() gives None and only the clothes are used.
"""
import pathlib
import threading

import cv2
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]      # the project folder
FACE_DET = ROOT / "models" / "face_detection_yunet_2023mar.onnx"
FACE_REC = ROOT / "models" / "face_recognition_sface_2021dec.onnx"
PARTS = ((0.18, 0.50), (0.55, 0.90))     # parts of the box height: upper body, legs
H_BINS, S_BINS, V_BINS = 12, 3, 6        # hue x saturation for coloured pixels, brightness for the colourless ones
MIN_SAT = 50                             # HSV S below this is white / grey / black (as objects.MIN_SATURATION)
MIN_PX = 200                             # px in a part; fewer: the part is left empty (all zeros)
SAME = 0.90                              # same() at least this: the same clothes. Head camera 2026-10-21: one person back
                                         # after a while 0.66-0.91 (median 0.84), different people up to 0.86 (white
                                         # shirts 0.83): colours barely tell people apart, so only a close match counts
FACE_MAX_M = 2.0                         # m; faces are looked for only on people this close (~5 + 5 ms each)
FACE_SCORE = 0.85                        # YuNet score below this: no face (turned away, cut by the frame). Head camera
                                         # 2026-10-21, one person's faces against his other visits: score 0.80-0.85
                                         # median cosine 0.36, 0.85-0.90 0.65, above 0.90 0.73
FACE_SAME = 0.30                         # SFace cosine at least this: the same face. Head camera 2026-10-21, a new
                                         # track's first 3 faces against the person's mean face: one person back
                                         # 0.51-0.74 (6 returns seen by face), 13 other people -0.04..0.08
FORGET_S = 600.0                         # s; someone not seen this long is forgotten
KEEP = 0.8                               # clothes running mean: weight of the old signature per new frame

_face_lock = threading.Lock()            # the camera service reads both cameras in two threads
_face_nets = None


def _part(hsv):
    px = hsv.reshape(-1, 3)
    if len(px) < MIN_PX:
        return np.zeros(H_BINS * S_BINS + V_BINS, np.float32)
    vivid = px[px[:, 1] >= MIN_SAT]
    dull = px[px[:, 1] < MIN_SAT]
    hs, _, _ = np.histogram2d(vivid[:, 0], vivid[:, 1], bins=(H_BINS, S_BINS), range=((0, 180), (MIN_SAT, 256)))
    v, _ = np.histogram(dull[:, 2], bins=V_BINS, range=(0, 256))
    h = np.concatenate([hs.ravel(), v]).astype(np.float32)
    return h / h.sum()


def look(color, box):
    """Clothes signature of the person in this box (x1, y1, x2, y2 colour px), a plain list for JSON."""
    x1, y1, x2, y2 = (int(v) for v in box)
    w, h = x2 - x1, y2 - y1
    cx1, cx2 = x1 + w // 4, x2 - w // 4
    hsv = cv2.cvtColor(color[y1:y2, cx1:cx2], cv2.COLOR_BGR2HSV) if cx2 > cx1 and y2 > y1 else np.zeros((0, 0, 3))
    return [round(float(x), 4) for x in np.concatenate([_part(hsv[int(a * h):int(b * h)]) for a, b in PARTS])]


def _nets():
    global _face_nets
    if _face_nets is None:
        _face_nets = (cv2.FaceDetectorYN.create(str(FACE_DET), "", (320, 320), FACE_SCORE),
                      cv2.FaceRecognizerSF.create(str(FACE_REC), "")) if FACE_DET.exists() and FACE_REC.exists() else ()
    return _face_nets


def face(color, box):
    """Face embedding (unit length) of the person in this box, None when no clear face is in its upper half."""
    x1, y1, x2, y2 = (int(v) for v in box)
    crop = color[y1:y1 + (y2 - y1) // 2, x1:x2]
    if crop.shape[0] < 40 or crop.shape[1] < 40:
        return None
    with _face_lock:
        nets = _nets()
        if not nets:
            return None
        det, rec = nets
        det.setInputSize((crop.shape[1], crop.shape[0]))
        _, faces = det.detect(crop)
        if faces is None:
            return None
        e = rec.feature(rec.alignCrop(crop, max(faces, key=lambda f: f[-1]))).ravel()
    return [round(float(x), 4) for x in e / np.linalg.norm(e)]


def same(a, b):
    """0..1; parts empty in either signature (out of the frame) are not compared. 0 when nothing can be compared."""
    a, b = np.asarray(a, np.float32), np.asarray(b, np.float32)
    n = len(a) // len(PARTS)
    scores = [float(np.sqrt(a[i:i + n] * b[i:i + n]).sum()) for i in range(0, len(a), n)
              if a[i:i + n].any() and b[i:i + n].any()]
    return sum(scores) / len(scores) if scores else 0.0


def blend(old, new):
    """Running mean of clothes signatures (a part empty in one keeps the other)."""
    if old is None:
        return list(new)
    o, n = np.asarray(old, np.float32), np.asarray(new, np.float32)
    k = len(o) // len(PARTS)
    out = o.copy()
    for i in range(0, len(o), k):
        if n[i:i + k].any():
            out[i:i + k] = KEEP * o[i:i + k] + (1 - KEEP) * n[i:i + k] if o[i:i + k].any() else n[i:i + k]
    return out.tolist()


def blend_face(old, new):
    """Sum of the face embeddings seen (its direction is their mean): a running mean kept only the last few frames,
    often a turned face as the person left, and one person back scored -0.06..0.48 against it (0.51-0.74 the sum)."""
    if new is None:
        return old
    return list(new) if old is None else (np.asarray(old) + np.asarray(new)).tolist()


def likeness(look_a, face_a, look_b, face_b):
    """(by face, score) when both faces are known, else (by clothes, score); None when nothing can be compared."""
    if face_a is not None and face_b is not None:
        a, b = np.asarray(face_a), np.asarray(face_b)
        return "face", float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
    if look_a is not None and look_b is not None:
        return "clothes", same(look_a, look_b)
    return None


def alike(look_a, face_a, look_b, face_b):
    m = likeness(look_a, face_a, look_b, face_b)
    return m is not None and m[1] >= (FACE_SAME if m[0] == "face" else SAME)


class Person:
    """Someone Lumi has greeted: signatures, when last seen, and whether the conversation with them is still open."""

    def __init__(self, look, face, now):
        self.look, self.face, self.last_seen, self.talking = look, face, now, False

    def seen(self, look, face, now):
        if look is not None:
            self.look = blend(self.look, look)
        self.face = blend_face(self.face, face)
        self.last_seen = now


class People:
    def __init__(self):
        self.known = []

    def recall(self, look, face, now, taken=()):
        """The known person (not in `taken`: others in view now) this is, or None. A face match goes first."""
        self.known = [p for p in self.known if now - p.last_seen < FORGET_S]
        hits = [(likeness(look, face, p.look, p.face), p) for p in self.known
                if p not in taken and alike(look, face, p.look, p.face)]
        return max(hits, key=lambda h: (h[0][0] == "face", h[0][1]), default=(None, None))[1]

    def add(self, look, face, now):
        p = Person(look, face, now)
        self.known.append(p)
        return p
