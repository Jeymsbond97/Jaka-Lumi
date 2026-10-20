"""Make Lumi sing the best part of a song the owner provided (data/songs/mine/, local only, never copied to the Mac):
the singer's own vocal turned into Lumi's voice (audio/cover.py), over the song's instrumental.

    .venv-songs/bin/python audio/separate.py data/songs/mine/<NAME>.mp3     # 1. vocals / instrumental (Demucs)
    .venv-cover/bin/python audio/cover.py <NAME>                             # 2. the vocal in Lumi's voice
    .venv/bin/python audio/sing_mine.py <NAME> --title "..." --title-ko "..." --names "a,b"   # 3. this

3 does: words and their times from the separated vocal (whisper.cpp), the part to sing (~40-60 s where the
most-repeated lines, the singing and the loudness are; or --start/--end seconds), the beats of the instrumental for
the head moves, and the mix: Lumi's vocal at the singer's level with a little room reverb over the instrumental.
Writes data/songs/mine/<NAME>.wav (the part) + .json (audio/sing.py plays them) and <NAME>/full_lumi.wav (the
whole song, to check). Lyrics only ever go into data/songs/mine/.
"""
import argparse
import difflib
import json
import pathlib
import re
import subprocess

import numpy as np
import soundfile as sf

from audio import sing_render as R

ROOT = pathlib.Path(__file__).resolve().parents[1]
MINE = ROOT / "data" / "songs" / "mine"
WHISPER_CLI = ROOT / "whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL = ROOT / "models/ggml-large-v3-turbo-q5_0.bin"
SR = R.SR
PART_S = (40.0, 60.0)           # s, length of the part sung
PART_BEST_S = 50.0              # s, preferred length
PAUSE_S = 0.2                   # s of a quiet vocal between two sung phrases
PHRASE_LEVEL = 0.3              # vocal RMS below this part of its loud level counts as quiet (separated vocals
                                # keep some reverb and bleed, so not much lower)
MAX_PHRASE_S = 12.0             # s; a longer phrase is split at its quietest moment
CHUNK_S = 28.0                  # s, longest piece of vocal given to whisper at once
SAME_LINE = 0.7                 # difflib ratio: two lines are the same line (a repeat)
HOP = 441                       # samples (10 ms) for pitch and energy frames
FRAME = 2048                    # samples, pitch window
VOCAL_F0 = (70.0, 1000.0)       # Hz, singer pitch range searched
VOICED_R = 0.6                  # normalised autocorrelation above this = a sung (voiced) frame
VOICE_GAIN = 1.0                # Lumi's vocal level relative to the singer's in the record (1 = the same balance)
FADE_IN_S, FADE_OUT_S = 0.3, 2.5
BPM_RANGE = (70.0, 180.0)
BEAT_TIGHTNESS = 100.0          # DP beat tracker: how strongly beats keep the tempo
ENERGY_RANGE = (0.3, 0.8)        # instrumental loudness (part of the song's loud level) mapped to energy 0 .. 1
BEAT_MIN = 0.6                  # a beat closer than this part of the usual beat to the last one is a tracking hiccup


# ---------- analysis ----------
def mono(x):
    return x.mean(1) if x.ndim == 2 else x


def frames(x, size, hop):
    n = 1 + max(0, (len(x) - size) // hop)
    idx = np.arange(size)[None, :] + hop * np.arange(n)[:, None]
    return x[idx]


def rms(x, hop=HOP):
    return np.sqrt((frames(x, hop * 2, hop) ** 2).mean(1) + 1e-12)


def pitch_contour(v):
    """Per 10 ms: f0 in Hz (0 = unvoiced) of a separated vocal; octave jumps of single frames removed."""
    lo, hi = int(SR / VOCAL_F0[1]), int(SR / VOCAL_F0[0])
    f = frames(np.pad(v, (FRAME // 2, FRAME)), FRAME, HOP)
    e = np.sqrt((f ** 2).mean(1))
    spec = np.fft.rfft(f * np.hanning(FRAME), 2 * FRAME)
    ac = np.fft.irfft(np.abs(spec) ** 2)[:, :hi + 1]
    ac /= ac[:, :1] + 1e-12
    lag = lo + np.argmax(ac[:, lo:hi], 1)
    best = ac[np.arange(len(ac)), lag]
    # prefer the shortest lag that is nearly as good (the true period, not a multiple)
    for div in (3, 2):
        sub = np.round(lag / div).astype(int)
        ok = (sub >= lo) & (ac[np.arange(len(ac)), np.clip(sub, 0, hi)] > 0.9 * best)
        lag = np.where(ok, sub, lag)
    f0 = np.where((best > VOICED_R) & (e > 0.1 * np.percentile(e, 95)), SR / lag, 0.0)
    st = np.where(f0 > 0, 12 * np.log2(np.maximum(f0, 1) / 440), np.nan)
    med = st.copy()
    for i in range(2, len(st) - 2):                    # median of 5 frames
        w = st[i - 2:i + 3]
        w = w[~np.isnan(w)]
        med[i] = np.median(w) if len(w) >= 3 and not np.isnan(st[i]) else np.nan
    return np.where(np.isnan(med), 0.0, 440 * 2 ** (med / 12))


def onset_envelope(x):
    """Spectral flux per 10 ms frame (log magnitude, positive changes)."""
    f = frames(x, 2048, HOP)
    mag = np.log1p(100 * np.abs(np.fft.rfft(f * np.hanning(2048), axis=1)))
    flux = np.maximum(0, np.diff(mag, axis=0)).sum(1)
    flux = np.concatenate([[0], flux])
    flux -= np.convolve(flux, np.ones(50) / 50, "same")         # local mean removed
    return np.maximum(flux, 0)


def beats(x):
    """(bpm, beat times s) of the instrumental: tempo from the onset autocorrelation, beats by dynamic
    programming (Ellis 2007)."""
    env = onset_envelope(x)
    fps = SR / HOP
    lags = np.arange(int(fps * 60 / BPM_RANGE[1]), int(fps * 60 / BPM_RANGE[0]) + 1)
    ac = np.array([np.dot(env[:-l], env[l:]) for l in lags])
    prior = np.exp(-0.5 * (np.log2(60 * fps / lags / 120.0) / 0.9) ** 2)   # a mild preference for ~120 bpm
    period = lags[np.argmax(ac * prior)]
    score = env.copy()
    back = np.full(len(env), -1)
    span = np.arange(-2 * period, -period // 2)
    cost = -BEAT_TIGHTNESS * np.log(-span / period) ** 2
    for i in range(2 * period, len(env)):
        c = score[i + span] + cost
        k = np.argmax(c)
        score[i] += c[k]
        back[i] = i + span[k]
    i = len(env) - period + np.argmax(score[-period:])
    out = []
    while i >= 0:
        out.append(i)
        i = back[i]
    return 60 * fps / period, np.array(out[::-1]) / fps


def phrases(v):
    """[(t0, t1)] sung phrases of the separated vocal: parts between pauses of PAUSE_S."""
    e = rms(v)
    on = e > PHRASE_LEVEL * np.percentile(e, 95)
    out, start, quiet = [], None, 0
    for i, o in enumerate(on):
        if o:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * 0.01 >= PAUSE_S:
                out.append((start / 100, (i - quiet + 1) / 100))
                start, quiet = None, 0
    if start is not None:
        out.append((start / 100, len(on) / 100))
    out = [(a, b) for a, b in out if b - a >= 0.3]
    done = []
    while out:
        a, b = out.pop(0)
        if b - a <= MAX_PHRASE_S:
            done.append((a, b))
            continue
        lo, hi = int((a + (b - a) / 4) * 100), int((b - (b - a) / 4) * 100)
        cut = (lo + int(np.argmin(np.convolve(e[lo:hi], np.ones(15) / 15, "same")))) / 100
        out[:0] = [(a, cut), (cut, b)]
    return done


def whisper_words(v, folder, lang):
    """[(t0, t1, word)] of the separated vocal. whisper.cpp (one word per segment, DTW timestamps) on chunks of
    whole phrases up to CHUNK_S: on a whole song at once it skips parts and drifts."""
    chunks, cur = [], None
    for a, b in phrases(v):
        if cur and b - cur[0] <= CHUNK_S:
            cur = (cur[0], b)
        else:
            if cur:
                chunks.append(cur)
            cur = (a, b)
    chunks += [cur] if cur else []
    words = []
    tmp = folder / "chunk.wav"
    for a, b in chunks:
        a0 = max(0.0, a - 0.3)
        sf.write(tmp, v[int(a0 * SR):int((b + 0.3) * SR)], SR)
        subprocess.run(["sox", str(tmp), "-r", "16000", "-c", "1", "-b", "16", str(tmp.with_name("chunk16.wav"))],
                       check=True)
        subprocess.run([str(WHISPER_CLI), "-m", str(WHISPER_MODEL), "-f", str(tmp.with_name("chunk16.wav")), "-l", lang,
                        "-ml", "1", "-sow", "-mc", "0", "-dtw", "large.v3.turbo", "-oj", "-of", str(folder / "chunk"),
                        "-np"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        words += [(t0 + a0, t1 + a0, w) for t0, t1, w in read_words(folder / "chunk.json") if t0 + a0 < b + 0.2]
    (folder / "words.json").write_text(json.dumps(words, ensure_ascii=False))
    for f in ("chunk.wav", "chunk16.wav", "chunk.json"):
        (folder / f).unlink(missing_ok=True)
    return words


def read_words(path):
    """whisper.cpp's JSON with one word per segment. A Korean character can be split over two segments (its UTF-8
    bytes): such segments are joined."""
    segs = json.loads(path.read_bytes().decode("utf-8", "surrogateescape"))["transcription"]
    words, buf, t0 = [], b"", None
    for s in segs:
        if not buf:
            t0 = s["offsets"]["from"] / 1000
        buf += s["text"].encode("utf-8", "surrogateescape")
        try:
            w = buf.decode("utf-8").strip()
        except UnicodeDecodeError:
            continue
        buf = b""
        if w and not re.fullmatch(r"[\W_]*|\[.*\]|\(.*\)", w):
            words.append((t0, s["offsets"]["to"] / 1000, w))
    return words


def pick_part(words, phr, mr, vocal_f0):
    """(start s, end s): a part PART_S long, starting and ending with a sung phrase, where repeated lines (the
    chorus), singing and a loud instrumental are."""
    texts = [re.sub(r"\W", "", "".join(w for t, _, w in words if a - 0.2 <= t < b)).lower() for a, b in phr]
    rep = np.array([sum(len(a) > 3 and difflib.SequenceMatcher(None, a, b).ratio() > SAME_LINE
                        for j, b in enumerate(texts) if j != i) for i, a in enumerate(texts)], float)
    loud = rms(mr)
    loud /= np.percentile(loud, 95)
    voiced = vocal_f0 > 0
    best, part = -1.0, (phr[0][0], phr[0][0] + PART_BEST_S)
    for i in range(len(phr)):
        for j in range(i, len(phr)):
            t0, t1 = phr[i][0], phr[j][1]
            if t1 - t0 > PART_S[1]:
                break
            if t1 - t0 < PART_S[0]:
                continue
            f0, f1 = int(t0 * 100), int(t1 * 100)
            score = (1 + rep[i:j + 1].mean()) * (0.5 + voiced[f0:f1].mean()) * (0.5 + loud[f0:f1].mean()) \
                * (1 + 0.3 * min(rep[i], 2)) * np.exp(-abs(t1 - t0 - PART_BEST_S) / 30)   # begins with a repeated line
            if score > best:
                best, part = score, (t0, t1)
    return part


# ---------- mix ----------
def beat_info(beat_times, mr, v, t_start, t_end):
    """[[s from the part's start, energy 0..1, accent 0..1, a sung phrase starts]] per beat of the part, for the
    head moves of audio/sing.py: energy = the instrumental's loudness over half a second against the whole
    song's (ENERGY_RANGE), accent = its strongest
    onset within 60 ms of the beat, phrase = a vocal phrase begins before the next beat."""
    loud = rms(mono(mr))
    onset = onset_envelope(mono(mr))
    bt = beat_times[(beat_times >= t_start) & (beat_times < t_end - 0.5)]
    if not len(bt):
        return []
    period = np.median(np.diff(bt)) if len(bt) > 1 else 0.5
    keep = [bt[0]]
    for t in bt[1:]:
        if t - keep[-1] > BEAT_MIN * period:
            keep.append(t)
    bt = np.array(keep)
    energy = np.array([loud[int(t * 100):int(t * 100) + 50].mean() for t in bt]) / np.percentile(loud, 95)
    energy = np.clip((energy - ENERGY_RANGE[0]) / (ENERGY_RANGE[1] - ENERGY_RANGE[0]), 0, 1)
    accent = np.array([onset[max(0, int(t * 100) - 6):int(t * 100) + 7].max() for t in bt])
    accent = np.clip(accent / (np.percentile(accent, 90) + 1e-9), 0, 1)
    starts = np.array([a for a, _ in phrases(v)])
    phrase = [bool(((starts >= t - 0.1) & (starts < t + period - 0.1)).any()) for t in bt]
    return [[round(float(t - t_start), 3), round(float(e), 2), round(float(a), 2), ph]
            for t, e, a, ph in zip(bt, energy, accent, phrase)]


def active_rms(x, ref):
    """RMS of x over the frames where it sounds (above 10 % of ref's loud level)."""
    e = rms(x)
    on = e > 0.1 * np.percentile(rms(ref), 95)
    return float(np.sqrt((e[on] ** 2).mean())) if on.any() else 1e-9


def make(name, title, title_ko, names, lang, start=None, end=None):
    folder = MINE / name
    vocals, sr = sf.read(folder / "vocals.wav", dtype="float32", always_2d=True)
    mr, _ = sf.read(folder / "mr.wav", dtype="float32", always_2d=True)
    lumi, sr_l = sf.read(folder / "vocal_lumi.wav", dtype="float32", always_2d=True)
    assert sr == SR and sr_l == SR, (sr, sr_l)
    v, lumi = mono(vocals), mono(lumi)
    f0 = pitch_contour(v)
    words_file = folder / "words.json"
    words = [tuple(w) for w in json.loads(words_file.read_text())] if words_file.exists() else \
        whisper_words(v, folder, lang)
    phr = phrases(v)
    bpm, bt = beats(mono(mr))
    if start is None:
        start, end = pick_part(words, phr, mono(mr), f0)
    bar = 4 * 60 / bpm
    before = bt[bt <= start - 0.2]
    t_start = float(before[-1] if len(before) and start - before[-1] < bar + 0.3 else max(0.0, start - 0.5))
    if start - t_start < bar * 0.75 and len(before) > 4:   # a bar of music before Lumi starts
        t_start = float(bt[max(0, len(before) - 5)])
    t_end = min(len(mr) / SR, end + 1.5)
    n = min(len(lumi), len(mr))
    voice = np.zeros(len(mr), np.float32)
    voice[:n] = lumi[:n] * VOICE_GAIN * active_rms(v, v) / active_rms(lumi, v)
    full = R.reverb(voice)[:, None] + mr
    full *= 0.9 / np.abs(full).max()
    sf.write(folder / "full_lumi.wav", full.astype(np.float32), SR, subtype="PCM_16")
    part = full[int(t_start * SR):int(t_end * SR)].copy()
    fi, fo = int(FADE_IN_S * SR), int(FADE_OUT_S * SR)
    part[:fi] *= np.linspace(0, 1, fi)[:, None]
    part[-fo:] *= np.linspace(1, 0, fo)[:, None]
    sf.write(MINE / f"{name}.wav", part.astype(np.float32), SR, subtype="PCM_16")
    lyrics = " ".join(w for a, _, w in words if start - 0.05 <= a < end)
    song = {"title": title, "title_ko": title_ko, "lang": lang, "names": names,
            "source": "owner's file; company holds the performance licence; local only",
            "part_s": [round(t_start, 2), round(t_end, 2)], "bpm": round(bpm, 1),
            "lyrics": lyrics, "beats": beat_info(bt, mr, v, t_start, t_end)}
    (MINE / f"{name}.json").write_text(json.dumps(song, ensure_ascii=False, indent=1))
    print(f"{MINE / name}.wav  part {t_start:.1f}-{t_end:.1f} s ({t_end - t_start:.0f} s), {bpm:.0f} bpm; "
          f"{folder / 'full_lumi.wav'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--title", required=True)
    ap.add_argument("--title-ko", required=True)
    ap.add_argument("--names", required=True, help="comma-separated words it is asked by")
    ap.add_argument("--lang", default="ko")
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    a = ap.parse_args()
    make(a.name, a.title, a.title_ko, [n.strip().lower() for n in a.names.split(",")], a.lang, a.start, a.end)
