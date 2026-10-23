"""Lumi's own voice in the clip mic (audio/mouth.py echo()): what the speaker played against what the mic heard.

    .venv/bin/python tests/echo_check.py           # made cases, and the real clips in logs/asr_real/ when there

Made cases: Lumi's lines (TTS voice F1) through a room as the clip mic hears the speaker (echo, noise, 0-0.8 s late,
the utterance a part of the sentence) must score >= mouth.ECHO_MIN; a visitor (other voices) close to the clip mic
while Lumi talks in the background (12-20 dB lower), also saying Lumi's own words, must score below it. Real: the
owner's clips against Lumi's lines (low), and the clips that were Lumi's own voice live (2026-10-22 18:25, 18:49)
against the line Lumi said then. The TTS samples differ each time it is made (a made line against itself made
again: 0.4-0.6 instead of 0.8), so the real own-voice scores here are lower than live, where mouth keeps the samples
it played: only the made cases decide ECHO_MIN; the live log's "own voice" lines show the real scores.
"""
import wave
from pathlib import Path

import numpy as np

from audio import mouth
from tests.asr_check import synth, room

ROOT = Path(__file__).resolve().parents[1]
RATE = 16000
LINES = ["I can see you through my cameras and sensors to make sure I navigate around you safely.",
         "Your right hand is still empty.", "Okay, I'm looking to the left.",
         "It is mainly clear right now with a temperature of 23 degrees, but you should be prepared for rain later.",
         "네, 충전소로 갈게요. 잠시만 기다려 주세요.", "저는 커피를 직접 만들 수는 없지만, 커피 바까지 안내해 드릴 수 있어요."]
VISITOR = [("en", "Stop, please stop."), ("en", "Can you see me?"), ("en", "What is in my hand?"),
           ("ko", "잠깐만, 그만해."), ("ko", "루미야, 이리 와."), ("en", "Let's follow me.")]
ARM = "My arm is in a position I don't know, so I won't move it."
OWN_REAL = {"1022/182501": ARM,                                           # heard "I am dumb, so I won't move it."
            "1022/182504": "Please bring it near its look pose by hand.",  # "It's bringing your insulin to the hand."
            "1022/182519": ARM,                                           # "I won't move it."
            "184903": "Your right hand is still empty."}                  # "It's still empty." (logs/heard)
NEAR_SPEAKER = dict(rt60=0.35, snr=20, peak=0.2, babble=False)   # the speaker ~1 m from the clip mic


def lumi(text, speed=0.92):
    return synth([("ko" if any("가" <= ch <= "힣" for ch in text) else "en", text)], "F1", speed)


def score(mic, played, lag):
    """echo() with `played` started `lag` s before the mic heard it, the mic's audio ending now."""
    mouth._played.clear()
    end = 1000.0
    start_mic = end - len(mic) / RATE
    mouth._played.append([start_mic - lag, start_mic - lag + len(played) / RATE, played.astype(np.float32)])
    return mouth.echo(mic, end)


def made():
    rng = np.random.default_rng(3)
    own, other = [], []
    for i, text in enumerate(LINES):
        x = lumi(text)
        for k in range(4):
            lag = rng.uniform(0.0, 0.8)
            a = int(rng.uniform(0, 0.5) * len(x))
            part = x[a:a + int(rng.uniform(1.2, 4.0) * RATE)]             # the part the mic cut as one utterance
            heard = room(part, NEAR_SPEAKER, rng)
            # the mic hears part (from sample a) lag s after it played: played started (a/RATE + lag) s before
            own.append(score(heard, x, a / RATE + lag - 0.3))            # room() puts 0.3 s before it
            assert score(heard, x, a / RATE + len(x) / RATE + 2) is None   # said after Lumi stopped: not judged
            lang, words = VISITOR[(i + k) % len(VISITOR)]
            v = synth([(lang, words)], ["M2", "F3", "M4", "F5"][k], 1.0)
            for same in (False, True):
                if same:                                                  # the visitor says Lumi's own words
                    v = synth([("ko" if any("가" <= ch <= "힣" for ch in text) else "en", text)], "M3", 1.0)[:len(part)]
                bg = room(part[:len(v)], NEAR_SPEAKER, rng).astype(np.float32)
                db = rng.uniform(12, 20)
                n = min(len(v), len(bg))
                vv, bg = v[:n] * 32767 * 0.3, bg[:n]
                mix = vv + bg * np.sqrt(np.mean(vv ** 2) / (np.mean(bg ** 2) + 1e-9)) / 10 ** (db / 20)
                mix = np.concatenate([np.zeros(int(0.3 * RATE)), mix, np.zeros(int(0.3 * RATE))])
                other.append(score(mix.astype(np.int16), x, a / RATE + lag - 0.3))
    return own, other


def clip(name):
    f = ROOT / "logs" / "asr_real" / f"{name}.wav"
    f = f if f.exists() else ROOT / "logs" / "heard" / f"{name}.wav"
    if not f.exists():
        return None
    with wave.open(str(f)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16)


def best(mic, played):
    """The best echo() over every lag (the real clips' play times are not known): harder for the visitor clips."""
    return max(score(mic, played, lag) or 0.0 for lag in np.arange(-len(mic) / RATE, len(played) / RATE, 1.0))


def real():
    from tests.asr_live import REAL
    own = {n: best(clip(n), lumi(t)) for n, t in OWN_REAL.items() if clip(n) is not None}
    visitor = {n: max(best(clip("1022/" + n), lumi(t)) for t in set(OWN_REAL.values()) | {LINES[0]})
               for n, said in REAL.items() if said and clip("1022/" + n) is not None}
    return own, visitor


if __name__ == "__main__":
    own, other = made()
    print(f"made: own voice {len(own)}: min {min(own):.2f}, median {np.median(own):.2f}; "
          f"visitor over Lumi {len(other)}: max {max(other):.2f}, median {np.median(other):.2f}")
    print(f"  own below {mouth.ECHO_MIN}: {sum(s < mouth.ECHO_MIN for s in own)}, visitor at or above: "
          f"{sum(s >= mouth.ECHO_MIN for s in other)}")
    assert min(own) >= mouth.ECHO_MIN > max(other)
    own_r, vis_r = real()
    if own_r:
        print("real own voice:", {k: round(v, 2) for k, v in own_r.items()})
        print(f"real visitor clips {len(vis_r)}: max {max(vis_r.values()):.2f}, at or above {mouth.ECHO_MIN}: "
              f"{[k for k, v in vis_r.items() if v >= mouth.ECHO_MIN]}")
