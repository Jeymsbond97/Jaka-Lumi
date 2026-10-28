"""Self-check of the sound direction with the clip mic as reference (audio/doa.py): a voice from one side plus a
louder noise from another, made for the six-mic ring of the calibration geometry. With the clip audio (the voice,
reaching the robot later over the radio) the direction is the voice's; audio without that voice gives the plain estimate;
head-array utterances (no reference) are estimated as before. No hardware: python tests/test_doa_clip.py"""
import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from audio import doa

CAL = {"radius": 0.045, "offset": 30.0, "sign": -1}
RATE = doa.RATE
rng = np.random.default_rng(1)


def voice(seconds):
    """Speech-like: harmonics of a gliding pitch, in syllables (4 per second) with pauses."""
    t = np.arange(int(seconds * RATE)) / RATE
    f0 = 140 + 30 * np.sin(2 * np.pi * 0.7 * t)
    phase = 2 * np.pi * np.cumsum(f0) / RATE
    x = sum(np.sin(k * phase) / k for k in range(1, 20))
    return x * np.clip(np.sin(2 * np.pi * 2 * t), 0, None) ** 2


def at_ring(x, deg):
    """The six mics' signals of a far source at deg (head frame), by fractional delays in the spectrum."""
    th, phi = np.radians(deg), np.radians(CAL["offset"] + CAL["sign"] * 60.0 * np.arange(6))
    tau = -CAL["radius"] * np.cos(th - phi) / doa.SOUND
    f = np.fft.rfftfreq(len(x), 1 / RATE)
    X = np.fft.rfft(x)
    return np.stack([np.fft.irfft(X * np.exp(-2j * np.pi * f * d), len(x)) for d in tau], 1)


def rms(x):
    return float(np.sqrt(np.mean(x ** 2)))


def scene(voice_deg, noise_deg, noise_over_voice, seconds=2.5):
    v = voice(seconds)
    n = rng.standard_normal(len(v))
    n *= noise_over_voice * rms(v) / rms(n)
    mics = at_ring(v, voice_deg) + at_ring(n, noise_deg) + 0.02 * rms(v) * rng.standard_normal((len(v), 6))
    return (mics * 3000 / rms(mics)).astype(np.int16), v


def clip_of(v, delay_ms):
    """What the clip mic gives: the voice, close and clean, delayed by the radio (array sample k = clip k - delay)."""
    c = np.roll(v, int(delay_ms * RATE / 1000)) + 0.01 * rms(v) * rng.standard_normal(len(v))
    return (c * 3000 / rms(c)).astype(np.int16)


def off(a, b):
    return abs((a - b + 180) % 360 - 180)


fails = []
for voice_deg, noise_deg in [(-60, 170), (-30, 180), (-90, 150), (45, -120), (0, 120)]:
    mics, v = scene(voice_deg, noise_deg, 2.0)            # the noise twice as loud as the voice at the head
    for delay_ms in (0, 40, -25):
        ang, conf, _ = doa.estimate(mics, CAL, clip_of(v, delay_ms))
        print(f"voice {voice_deg:+4d}, noise {noise_deg:+4d}, clip delay {delay_ms:+3d} ms: "
              f"{ang:+5.0f} deg (confidence {conf:.2f})")
        if off(ang, voice_deg) > 10 or conf < 0.12:
            fails.append((voice_deg, noise_deg, delay_ms, ang, conf))
    ang, conf, _ = doa.estimate(mics, CAL)
    print(f"  without the clip: {ang:+5.0f} deg (confidence {conf:.2f})")
    assert off(ang, voice_deg) > 30, "the scene must be hard without the clip (else the test proves nothing)"
assert not fails, fails

# the clip wearer's voice is not found in the array audio: the plain estimate, as without the clip
mics, _ = scene(-60, 170, 0.5)
other = clip_of(voice(2.5)[::-1].copy(), 0)
assert doa.clip_lag(mics, other)[1] < doa.CLIP_MIN_SCORE
assert doa.estimate(mics, CAL, other) == doa.estimate(mics, CAL)
assert "clip not found" in doa.clip_note(mics, other)
mics, v = scene(-60, 170, 2.0)
assert "clip score" in doa.clip_note(mics, clip_of(v, 40))
assert doa.clip_note(mics, None) == ""
print(f"clip voice not in the array: plain estimate {doa.estimate(mics, CAL, other)[0]:+.0f} deg")

# head-array utterances: no reference, the voice alone is found as before
mics, _ = scene(-60, 170, 0.1)
ang, conf, _ = doa.estimate(mics, CAL)
assert off(ang, -60) <= 10 and conf > 0.12, (ang, conf)
assert doa.clip_ref(type("U", (), {"source": "head", "mono": "x"})) is None
doa.USE_CLIP_REF = True
assert doa.clip_ref(type("U", (), {"source": "clip", "mono": "x"})) == "x"

# calibration samples (add_sample) in a temporary folder: with the clip the wearer's voice is learnt under louder room
# noise; a clip voice not in the array is no sample; a refit worse than the saved calibration does not replace it
import json, pathlib, tempfile
tmp = pathlib.Path(tempfile.mkdtemp())
doa.CALIB, doa.SAMPLES = tmp / "calib.json", tmp / "samples.npz"
mics, _ = scene(-60, 170, 0.5)
assert doa.add_sample(mics, -60, other) is None and not doa.SAMPLES.exists()
c = None
for deg in (-40, -20, 0, 20, 40, 10):
    mics, v = scene(deg, 170, 2.0)
    c = doa.add_sample(mics, deg, clip_of(v, 40))
assert c and (c["sign"], c["offset"]) == (CAL["sign"], CAL["offset"]) and c["median_error_deg"] <= 4, c
doa.CALIB.write_text(json.dumps({**c, "median_error_deg": -1.0}))  # a saved fit no new one can beat
mics, _ = scene(30, 170, 2.0)
assert doa.add_sample(mics, 30) is None and json.loads(doa.CALIB.read_text())["median_error_deg"] == -1.0
assert len(np.load(doa.SAMPLES)["t"]) == 7                       # the sample itself is kept
print("ok")
