"""Sound direction (direction of arrival) from the six mics of the head array, SRP-PHAT.

For each candidate direction the expected time differences between the mics of a ring are compared with the
measured cross-spectra (PHAT-weighted); the direction with the most energy wins.

Geometry (to calibrate, kept in doa_calib.json): six mics on a ring of `radius`; mic k sits at
offset + sign * k * 60 deg. Angles are in the head frame: 0 = where the head looks, + = to the robot's left
(same sign as head yaw). Robot (waist) angle = head yaw + this angle.

Calibration needs people at known angles. lumi.py collects them on its own: while it talks with a person
the head camera sees, each utterance of that person is a sample (camera angle = truth). After MIN_SAMPLES
samples spread over at least SPREAD_DEG it fits sign / offset / radius and writes doa_calib.json, unless the fit is
worse than the saved one. With the clip mic a sample is weighted by the clip voice like estimate(), and is skipped
when that voice is not found in the array audio.
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
CLIP_MAX_LAG_S = 0.3             # s searched for the clip mic's voice in the head array audio (radio delay + buffers;
                                 # the array window is cut by the clip's own times, so they differ by tens of ms)
USE_CLIP_REF = False             # weight the direction by the clip mic's voice; off: the plain array estimate
CLIP_MIN_SCORE = 8.0            # clip voice found in the array: correlation peak over its spread (unrelated audio ~4-5)
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


def _spectra(x):
    """Band spectra of 50 % overlapping windows: (t, F, channels)."""
    win = np.hanning(NFFT).astype(np.float32)
    frames = np.stack([x[i:i + NFFT] * win[:, None] for i in range(0, len(x) - NFFT, HOP)])   # (t, NFFT, ch)
    return np.fft.rfft(frames, axis=1)[:, _band, :]


def clip_lag(mics, ref):
    """Where the clip mic's voice sits in the head array audio: (lag, score). Clip sample k is array sample k + lag;
    score = GCC-PHAT peak (clip against the array's mean, speech band) over the spread of the correlation."""
    a, c = mics.astype(np.float32).mean(1), np.asarray(ref, np.float32)
    n = 1 << int(np.ceil(np.log2(len(a) + len(c))))
    f = np.fft.rfftfreq(n, 1 / RATE)
    x = np.fft.rfft(a, n) * np.conj(np.fft.rfft(c, n))
    x = np.where((f >= BAND[0]) & (f <= BAND[1]), x / (np.abs(x) + 1e-9), 0)
    cc = np.fft.irfft(x, n)
    m = int(CLIP_MAX_LAG_S * RATE)
    cc = np.concatenate([cc[-m:], cc[:m + 1]])                     # lags -m .. +m
    k = int(np.argmax(cc))
    return k - m, float(cc[k] / (cc.std() + 1e-12))


def cross_spectra(mics, ref=None):
    """Average PHAT-normalised cross-spectra of all mic pairs: (15, n_band) complex, or None if too short.

    ref: the clip mic's audio of the same utterance (worn by the person talking to Lumi). The array then hears that
    person faintly under louder room sound, so the louder-frames rule picks the room. Instead the clip is lined up
    with the array (clip_lag) and each time-frequency bin is weighted by the clip's power there: bins where the wearer
    talks count, the room in between and in other frequencies does not (a fixed share of the strongest bins worked
    too, but the right share changed with how loud the room was). When the clip voice is not found in the array the
    plain estimate is made (the louder frames), as without a clip."""
    x = mics.astype(np.float32)
    if len(x) < NFFT:
        return None
    spec = _spectra(x)                                                                         # (t, F, 6)
    lag, score = clip_lag(x, ref) if ref is not None and len(ref) else (0, 0.0)
    if score < CLIP_MIN_SCORE:
        energy = (np.abs(spec) ** 2).sum((1, 2))
        w = (energy >= np.percentile(energy, 50))[:, None] * np.ones(spec.shape[1])   # the louder half of the frames:
    else:                                                                             # the voice, not pauses
        c = np.zeros(len(x), np.float32)                                   # the clip at the array's sample times
        src = np.asarray(ref, np.float32)[max(0, -lag):]
        c[max(0, lag):max(0, lag) + len(src)] = src[:len(x) - max(0, lag)]
        p = np.abs(_spectra(c[:, None])[:, :, 0]) ** 2                     # (t, F) clip power
        w = p / (p.max() + 1e-12)
    g = np.stack([(spec[:, :, i] * np.conj(spec[:, :, j])) for i, j in PAIRS])                # (15, t, F)
    g = g / (np.abs(g) + 1e-9)
    return (g * w[None]).sum(1) / w.sum(0).max()           # weighted mean over the frames: (15, F); a frequency
                                                            # where the clip voice is weak counts little


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


def clip_ref(u):
    """The clip mic's audio of an utterance cut from it (its wearer's voice is the one to find), else None. Off
    (USE_CLIP_REF): live, the clip-weighted direction came out at confidence 0.03-0.07, too weak to trust."""
    return u.mono if USE_CLIP_REF and getattr(u, "source", None) == "clip" else None


def clip_found(mics, ref):
    """Is the clip mic's voice clearly in the head array audio (then the estimate is its wearer's direction)?"""
    if ref is None or mics is None or len(mics) < NFFT or not len(ref):
        return False
    return clip_lag(mics, ref)[1] >= CLIP_MIN_SCORE


def clip_note(mics, ref):
    """For the log: how clearly the clip voice was found in the array audio, "" without a clip."""
    if ref is None or mics is None or len(mics) < NFFT or not len(ref):
        return ""
    lag, score = clip_lag(mics, ref)
    if score < CLIP_MIN_SCORE:
        return f", clip not found (score {score:.1f})"
    return f", clip score {score:.0f} at {lag * 1000 / RATE:+.0f} ms"


def estimate(mics, calib=None, ref=None):
    """(angle deg in the head frame, confidence 0..1, raw angle with the default geometry). ref: see cross_spectra."""
    calib = calib or load_calib()
    g = cross_spectra(mics, ref)
    if g is None:
        return 0.0, 0.0, 0.0
    p = _power(g, calib)
    best = int(np.argmax(p))
    conf = float((p[best] - np.median(p)) / (np.abs(p).max() + 1e-9))
    raw = float(GRID[int(np.argmax(_power(g, {"radius": 0.04, "offset": 0.0, "sign": 1})))])
    return float(GRID[best]), max(0.0, min(1.0, conf)), raw


# ---------- calibration ----------
def add_sample(mics, true_deg, ref=None):
    """Store one utterance with its true head-frame angle; refit when there are enough. Returns the new calib, or None
    (too few samples, or the refit explains the samples worse than the saved calibration did: that one is kept).
    ref: the clip mic's audio (clip_ref): the sample is the wearer's voice as estimate() hears it; an utterance whose
    clip voice is not found in the array audio is no sample (the array heard the room, not the wearer)."""
    if ref is not None and len(ref) and len(mics) >= NFFT and clip_lag(mics, ref)[1] < CLIP_MIN_SCORE:
        return None
    g = cross_spectra(mics, ref)
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
        return fit(np.array(gs), np.array(ts), keep_better=True)
    return None


def fit(gs, ts, keep_better=False):
    """Grid search sign / offset / radius that best explains the samples; saves doa_calib.json. keep_better: only when
    its median error is no worse than the saved calibration's (else None, the saved one stays)."""
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
    if keep_better:
        try:
            if round(score, 1) > float(json.loads(CALIB.read_text())["median_error_deg"]):
                return None
        except (FileNotFoundError, ValueError, KeyError):
            pass
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
