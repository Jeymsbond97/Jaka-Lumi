"""Sound direction (direction of arrival) from the six mics of the head array, SRP-PHAT.

For each candidate direction the expected time differences between the mics of a ring are compared with the
measured cross-spectra (PHAT-weighted); the direction with the most energy wins.

Geometry (to calibrate, kept in doa_calib.json): six mics on a ring of `radius`; mic k sits at
offset + sign * k * 60 deg. Angles are in the head frame: 0 = where the head looks, + = to the robot's left
(same sign as head yaw). Robot (waist) angle = head yaw + this angle.

Calibration needs people at known angles. lumi.py collects them on its own: while it talks with a person
the head camera sees, each utterance of that person is a sample (camera angle = truth). After MIN_SAMPLES
samples spread over at least SPREAD_DEG it fits sign / offset / radius and writes doa_calib.json.
Or by hand:

    python audio/doa.py --calibrate     # stand in front of the head camera, talk, move left / right, Ctrl+C to fit
"""
import json
import math
import pathlib
import sys
import time

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]      # the project folder
CALIB = ROOT / "data" / "doa_calib.json"
SAMPLES = ROOT / "data" / "doa_samples.npz"
RATE = 16000
SOUND = 343.0                    # m/s
NFFT, HOP = 512, 256
BAND = (300.0, 3500.0)           # Hz used
GRID = np.arange(-180, 180, 2.0)  # deg
MIN_SAMPLES, SPREAD_DEG = 6, 30.0
PAIRS = [(i, j) for i in range(6) for j in range(i + 1, 6)]

_freqs = np.fft.rfftfreq(NFFT, 1 / RATE)
_band = (_freqs >= BAND[0]) & (_freqs <= BAND[1])
_f = _freqs[_band]


def load_calib():
    try:
        c = json.loads(CALIB.read_text())
        return {"radius": float(c["radius"]), "offset": float(c["offset"]), "sign": int(c["sign"]), "fitted": True}
    except (FileNotFoundError, ValueError, KeyError):
        return {"radius": 0.04, "offset": 0.0, "sign": 1, "fitted": False}


def cross_spectra(mics):
    """Average PHAT-normalised cross-spectra of all mic pairs: (15, n_band) complex, or None if too short."""
    x = mics.astype(np.float32)
    if len(x) < NFFT:
        return None
    win = np.hanning(NFFT).astype(np.float32)
    frames = np.stack([x[i:i + NFFT] * win[:, None] for i in range(0, len(x) - NFFT, HOP)])   # (t, NFFT, 6)
    spec = np.fft.rfft(frames, axis=1)[:, _band, :]                                            # (t, F, 6)
    energy = (np.abs(spec) ** 2).sum((1, 2))
    keep = energy >= np.percentile(energy, 50)            # the louder half of the frames: the voice, not pauses
    spec = spec[keep]
    g = np.stack([(spec[:, :, i] * np.conj(spec[:, :, j])) for i, j in PAIRS])                # (15, t, F)
    g = g / (np.abs(g) + 1e-9)
    return g.mean(1)                                                                            # (15, F)


def _steering(radius, offset, sign):
    """(n_grid, 15, F) expected phase for each candidate direction."""
    th = np.radians(GRID)[:, None]
    phi = np.radians(offset + sign * 60.0 * np.arange(6))[None, :]
    tau = -radius * np.cos(th - phi) / SOUND                       # (n_grid, 6): arrival time of each mic
    d = np.stack([tau[:, i] - tau[:, j] for i, j in PAIRS], 1)     # (n_grid, 15)
    return np.exp(2j * np.pi * _f[None, None, :] * d[:, :, None])


_cache = {}


def _power(g, calib):
    key = (calib["radius"], calib["offset"], calib["sign"])
    if key not in _cache:
        _cache.clear()
        _cache[key] = _steering(*key)
    return np.real((_cache[key] * g[None]).sum((1, 2)))           # (n_grid,)


def estimate(mics, calib=None):
    """(angle deg in the head frame, confidence 0..1, raw angle with the default geometry)."""
    calib = calib or load_calib()
    g = cross_spectra(mics)
    if g is None:
        return 0.0, 0.0, 0.0
    p = _power(g, calib)
    best = int(np.argmax(p))
    conf = float((p[best] - np.median(p)) / (np.abs(p).max() + 1e-9))
    raw = float(GRID[int(np.argmax(_power(g, {"radius": 0.04, "offset": 0.0, "sign": 1})))])
    return float(GRID[best]), max(0.0, min(1.0, conf)), raw


# ---------- calibration ----------
def add_sample(mics, true_deg):
    """Store one utterance with its true head-frame angle; refit when there are enough. Returns the new calib or None."""
    g = cross_spectra(mics)
    if g is None:
        return None
    try:
        d = np.load(SAMPLES)
        gs, ts = list(d["g"]), list(d["t"])
    except (FileNotFoundError, KeyError, ValueError):
        gs, ts = [], []
    gs.append(g)
    ts.append(float(true_deg))
    gs, ts = gs[-60:], ts[-60:]
    np.savez(SAMPLES, g=np.array(gs), t=np.array(ts))
    if len(ts) >= MIN_SAMPLES and max(ts) - min(ts) >= SPREAD_DEG:
        return fit(np.array(gs), np.array(ts))
    return None


def fit(gs, ts):
    """Grid search sign / offset / radius that best explains the samples; saves doa_calib.json."""
    best = None
    for sign in (1, -1):
        for radius in (0.03, 0.035, 0.04, 0.045, 0.05):
            for offset in np.arange(0, 360, 5.0):
                c = {"radius": radius, "offset": float(offset), "sign": sign}
                err = []
                for g, t in zip(gs, ts):
                    a = GRID[int(np.argmax(_power(g, c)))]
                    err.append(abs((a - t + 180) % 360 - 180))
                score = float(np.median(err))
                if best is None or score < best[0]:
                    best = (score, c)
    score, c = best
    c["median_error_deg"] = round(score, 1)
    c["samples"] = len(ts)
    c["time"] = time.strftime("%Y-%m-%d %H:%M")
    CALIB.write_text(json.dumps(c, indent=1))
    _cache.clear()
    return c


def calibrate_by_hand():
    """Talk in front of the head camera from several places; the camera gives the true angle."""
    from audio import mic
    import threading
    from vision.camview import RemoteDetector
    det = RemoteDetector("head")
    seen = {"angle": None, "time": 0.0}

    def watch():
        while True:
            _, people = det.read()
            near = [p for p in people if p["distance_m"] and p["distance_m"] < 3.0]
            if len(near) == 1:                                # exactly one person: no doubt who talks
                seen.update(angle=near[0]["angle_deg"] - det.head_yaw * det.head_sign, time=time.time())

    threading.Thread(target=watch, daemon=True).start()
    m = mic.get()
    print("Stand 1-2 m in front of the robot, alone in the head camera's view, and talk for a few seconds.\n"
          "Then move ~1 m to the left, talk; to the right, talk. Ctrl+C when done.")
    n = 0
    try:
        while True:
            u = m.next(1.0)
            if u is None or u.seconds < 0.8:
                continue
            if time.time() - seen["time"] > 1.0:
                print("  (heard speech but no single person in view - skipped)")
                continue
            n += 1
            c = add_sample(u.mics, seen["angle"])
            print(f"  sample {n}: person at {seen['angle']:+.0f} deg, raw estimate {estimate(u.mics)[2]:+.0f} deg"
                  + (f"  -> calibrated: {c}" if c else ""))
    except KeyboardInterrupt:
        d = np.load(SAMPLES)
        if len(d["t"]) >= 3:
            print("fit:", fit(d["g"], d["t"]))


if __name__ == "__main__":
    if "--calibrate" in sys.argv:
        calibrate_by_hand()
    else:
        print(load_calib())
