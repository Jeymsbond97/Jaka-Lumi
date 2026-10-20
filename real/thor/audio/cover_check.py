"""Judge a converted vocal (Lumi's voice cover) against the singer's original, without listening. Offline tool for
the render venv (.venv-cover: resemblyzer); prints numbers only, never lyrics.

    .venv-cover/bin/python audio/cover_check.py data/songs/mine/<NAME>/vocals.wav <converted.wav> [start end]

(a) words: whisper (the running server) on both, cut the same way at the singer's phrases, the similarity of the
    two transcripts, and how many characters
    each gave; (b) voice: speaker-embedding similarity of the converted vocal to Lumi (data/songs/mine/lumi_voice)
    and to the original singer; (c) melody: correlation and median difference of the two pitch contours;
    (d) clipping and silent gaps where the singer sings.
"""
import difflib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf

from audio import sing_mine as M

ROOT = pathlib.Path(__file__).resolve().parents[1]
LUMI = ROOT / "data" / "songs" / "mine" / "lumi_voice"
STT_URL = "http://127.0.0.1:8096/inference"
PIECE_S = 25                    # s per whisper request
GAP_S = 0.3                     # s; a silent stretch this long where the singer sings is a gap
SINGING = 0.5                   # the singer sings where the vocal is above this part of its loud level (lower is
                                # mostly the reverb tail of a phrase, which the converted vocal rightly leaves out)


def load(path, sr=44100):
    x, r = sf.read(path, dtype="float32", always_2d=True)
    x = x.mean(1)
    if r != sr:
        x = np.interp(np.arange(int(len(x) * sr / r)) * r / sr, np.arange(len(x)), x).astype(np.float32)
    return x


def pieces(x, sr=44100):
    """[(start, end) samples]: the singer's phrases joined into pieces up to PIECE_S, so whisper hears whole lines
    (fixed 25 s cuts split words, and whisper drops parts of a long song)."""
    out = []
    for a, b in M.phrases(x):
        if out and b - out[-1][0] / sr <= PIECE_S:
            out[-1] = (out[-1][0], int(b * sr))
        else:
            out.append((int(max(0.0, a - 0.2) * sr), int(b * sr)))
    return out


def transcript(x, cuts, sr=44100):
    out = []
    with tempfile.TemporaryDirectory() as d:
        for a, b in cuts:
            p = pathlib.Path(d) / "p.wav"
            sf.write(p, x[a:b + int(0.3 * sr)], sr)
            subprocess.run(["sox", str(p), "-r", "16000", "-c", "1", "-b", "16", str(p.with_name("p16.wav"))],
                           check=True, stderr=subprocess.DEVNULL)
            r = subprocess.run(["curl", "-s", "-F", f"file=@{p.with_name('p16.wav')}", "-F", "response_format=json",
                                "-F", "language=ko", STT_URL], capture_output=True, text=True).stdout
            out.append(json.loads(r).get("text", ""))
    return re.sub(r"\W", "", " ".join(out)).lower()


def embed(enc, x, sr=44100):
    from resemblyzer import preprocess_wav
    return enc.embed_utterance(preprocess_wav(x, source_sr=sr))


def check(orig_path, conv_path, start=None, end=None):
    from resemblyzer import VoiceEncoder
    sr = 44100
    o, c = load(orig_path), load(conv_path)
    n = min(len(o), len(c))
    o, c = o[:n], c[:n]
    if start is not None:
        o, c = o[int(start * sr):int(end * sr)], c[int(start * sr):int(end * sr)]
    cuts = pieces(o)                                   # the same cuts for both
    to, tc = transcript(o, cuts), transcript(c, cuts)
    words = difflib.SequenceMatcher(None, to, tc).ratio()
    enc = VoiceEncoder("cpu")
    lumi = np.mean([embed(enc, load(p)) for p in sorted(LUMI.glob("line_*.wav"))], 0)
    e_c, e_o = embed(enc, c), embed(enc, o)
    cos = lambda a, b: float(np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b))
    f_o, f_c = M.pitch_contour(o), M.pitch_contour(c)
    m = min(len(f_o), len(f_c))
    both = (f_o[:m] > 0) & (f_c[:m] > 0)
    so, sc = 12 * np.log2(f_o[:m][both] / 440), 12 * np.log2(f_c[:m][both] / 440)
    diff = sc - so
    octave = round(float(np.median(diff)) / 12) * 12            # a whole-octave shift is allowed
    e_orig = M.rms(o) > SINGING * np.percentile(M.rms(o), 95)
    e_conv = M.rms(c) > 0.02 * np.percentile(M.rms(o), 95)
    gap, longest = 0, 0
    for so_on, sc_on in zip(e_orig, e_conv):
        gap = gap + 1 if so_on and not sc_on else 0
        longest = max(longest, gap)
    res = {"words_similarity": round(words, 2), "chars_original": len(to), "chars_converted": len(tc),
           "voice_sim_to_lumi": round(cos(e_c, lumi), 3), "voice_sim_to_singer": round(cos(e_c, e_o), 3),
           "singer_sim_to_lumi": round(cos(e_o, lumi), 3),
           "pitch_corr": round(float(np.corrcoef(so, sc)[0, 1]), 3), "pitch_octave_shift": octave,
           "pitch_median_err_cents": round(float(np.median(np.abs(diff - octave))) * 100),
           "pitch_within_50_cents": round(float((np.abs(diff - octave) < 0.5).mean()), 2),
           "pitch_frames_both_voiced": round(float(both.mean()), 2),
           "clipped_samples": int((np.abs(c) >= 0.999).sum()), "longest_gap_s": round(longest * 0.01, 2),
           "gaps_over_limit": longest * 0.01 >= GAP_S}
    print(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    a = sys.argv[1:]
    check(a[0], a[1], *(float(x) for x in a[2:4])) if len(a) >= 4 else check(a[0], a[1])
