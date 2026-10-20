"""Make a training set of Lumi's voice (Supertonic-3, the voice audio/mouth.py speaks with) for the voice-conversion
model of audio/cover.py: Lumi's own example answers (assistant/talk_examples.py), Korean and English, at varied
speeds. Local only (data/songs/mine/lumi_voice/train/).

    .venv/bin/python audio/lumi_voice_set.py [count]
"""
import pathlib
import random
import sys

import numpy as np
import soundfile as sf

from assistant import talk_examples
from audio import mouth

OUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "songs" / "mine" / "lumi_voice" / "train"
COUNT = 300                     # clips, about 15 minutes
SPEEDS = (0.8, 1.05)            # TTS speed range: slower clips give long vowels


def make(count=COUNT):
    OUT.mkdir(parents=True, exist_ok=True)
    tts = mouth._load()
    rng = random.Random(7)
    replies = sorted({r for _, _, _, r in talk_examples.EXAMPLES if 10 <= len(r) <= 160})
    rng.shuffle(replies)
    total = 0.0
    for i, text in enumerate(replies[:count]):
        wav, _ = tts.synthesize(text, voice_style=mouth._style, lang=mouth.lang_of(text), total_steps=8,
                                speed=rng.uniform(*SPEEDS))
        wav = np.asarray(wav, np.float32).reshape(-1)
        sf.write(OUT / f"{i:04d}.wav", wav, tts.sample_rate)
        total += len(wav) / tts.sample_rate
    print(f"{OUT}: {min(count, len(replies))} clips, {total / 60:.1f} min")


if __name__ == "__main__":
    make(int(sys.argv[1]) if len(sys.argv) > 1 else COUNT)
