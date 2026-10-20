"""Split a song into vocals and accompaniment (Demucs htdemucs) for audio/sing_mine.py. Offline tool: runs only in
the separate render venv (.venv-songs, torch CPU + demucs), never in the robot's .venv.

    .venv-songs/bin/python audio/separate.py data/songs/mine/BIGBANG_FANTASTIC_BABY.mp3

Writes <folder>/<name>/vocals.wav and <folder>/<name>/mr.wav (44.1 kHz stereo) next to the song.
"""
import pathlib
import sys

import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.pretrained import get_model

MODEL = "htdemucs"              # 4 stems: drums, bass, other, vocals
THREADS = 12                    # CPU threads (the Thor has 14 cores; leave some for the robot's services)


def separate(path):
    path = pathlib.Path(path)
    out = path.with_suffix("")
    out.mkdir(exist_ok=True)
    torch.set_num_threads(THREADS)
    model = get_model(MODEL)
    model.eval()
    wav, sr = sf.read(path, dtype="float32", always_2d=True)
    assert sr == model.samplerate, (sr, model.samplerate)
    x = torch.from_numpy(wav.T.copy())
    if x.shape[0] == 1:
        x = x.repeat(2, 1)
    ref = x.mean(0)
    mean, std = ref.mean(), ref.std()
    with torch.no_grad():
        stems = apply_model(model, ((x - mean) / std)[None], shifts=1, split=True, overlap=0.25, progress=True)[0]
    stems = stems * std + mean
    names = model.sources
    vocals = stems[names.index("vocals")].numpy().T
    mr = sum(stems[i] for i, n in enumerate(names) if n != "vocals").numpy().T
    sf.write(out / "vocals.wav", np.clip(vocals, -1, 1), sr)
    sf.write(out / "mr.wav", np.clip(mr, -1, 1), sr)
    print(f"{out}/vocals.wav, mr.wav")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        separate(p)
