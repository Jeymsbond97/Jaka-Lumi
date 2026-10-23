"""Early transcription check: the real clips (logs/asr_real/, local only) are played into mic.Segmenter in real time,
30 ms frames, as the microphone thread does; ears.early() starts on a pause (mic.EARLY_QUIET_S), the utterance is
transcribed when it ends. Measured: the time from the end of the utterance to the text, with and without the early
run, and whether the text is the same.

    .venv/bin/python tests/asr_early.py --port 8099    # a whisper-server already running there
"""
import statistics
import sys
import time
import wave
from pathlib import Path

import numpy as np

from audio import ears, mic

ROOT = Path(__file__).resolve().parents[1]


def utterance(audio, with_early):
    """Feed the clip as the microphone would; returns (text, seconds from the end of the utterance to the text,
    early runs started)."""
    seg = mic.Segmenter(mic.MIN_LEVEL_CLIP)
    ears._early.clear()
    n_early, t0 = 0, time.time()
    for i in range(0, len(audio) - mic.FRAME + 1, mic.FRAME):
        x = audio[i:i + mic.FRAME]
        time.sleep(max(0.0, t0 + (i + mic.FRAME) / mic.RATE - time.time()))   # real time
        done = seg.feed(x, float(np.sqrt(np.mean(x.astype(np.float32) ** 2))), time.time())
        if done:
            t_end = time.time()
            text = ears.transcribe(np.concatenate(done[0]))
            return text, time.time() - t_end, n_early
        if with_early and seg.quiet_now():
            ears.early(np.concatenate(seg.frames))
            n_early += 1
    return None, 0.0, n_early


def main(args):
    if "--port" in args:
        ears.STT_URL = f"http://127.0.0.1:{args[args.index('--port') + 1]}"
    ears.HEARD_DIR = ROOT / "logs" / "asr_check" / "heard"
    ends = int(mic.END_SILENCE * mic.RATE) + mic.FRAME
    old, new, same, n, discarded = [], [], 0, 0, 0
    for f in sorted((ROOT / "logs" / "asr_real").glob("*/*.wav")):
        with wave.open(str(f)) as w:
            audio = np.frombuffer(w.readframes(w.getnframes()), np.int16)
        audio = np.concatenate([np.zeros(mic.FRAME * 40, np.int16) + 1, audio, np.zeros(ends, np.int16)])  # floor, end
        a, ta, _ = utterance(audio, False)
        b, tb, k = utterance(audio, True)
        if a is None or b is None:
            continue
        n += 1
        old.append(ta)
        new.append(tb)
        same += a == b
        discarded += max(0, k - 1)
        if a != b:
            print(f"  {f.name}: {a!r} | early {b!r}")
    print(f"{n} clips: text the same {same}; end of speech -> text median {statistics.median(old):.2f} s -> "
          f"{statistics.median(new):.2f} s, mean {statistics.mean(old):.2f} -> {statistics.mean(new):.2f} s; "
          f"{discarded} early runs thrown away (speech went on)")


if __name__ == "__main__":
    main(sys.argv[1:])
