"""Render the songs in data/songs/ once: Lumi's TTS voice sung to the melody over a backing track made here.

    python audio/sing_render.py              # every song
    python audio/sing_render.py arirang      # one song

Each syllable is spoken by the TTS (Supertonic-3, the same voice as every answer), its pitch is set to the note
and its vowel stretched to the note's length with a pitch-synchronous overlap-add (TD-PSOLA, written below: no
pyworld / librosa on this Thor). The backing (bass + chords, a soft piano-like tone) is synthesised from the
song's chord list. Voice and backing are mixed into data/songs/<id>.wav, which audio/sing.py plays.
Nothing here is downloaded: the melodies and chords are written in the song files (public domain songs).
"""
import json
import pathlib
import sys

import numpy as np
import soundfile as sf

ROOT = pathlib.Path(__file__).resolve().parents[1]
SONGS = ROOT / "data" / "songs"
SR = 44100                      # Hz, the TTS sample rate
TARGET_MEAN_HZ = 240.0          # songs are transposed so their average note is near this (voice F1 speaks at ~175 Hz)
F0_RANGE = (110.0, 400.0)       # Hz, pitch search range for the speaking voice
HOP = 220                       # samples (5 ms) between pitch frames
WIN = 1323                      # samples (30 ms) pitch analysis window
VOICED_R = 0.5                  # normalised autocorrelation above this = voiced frame
UNVOICED_P = SR // 200          # samples; grain spacing in unvoiced parts
ONSET_MAX_S = 0.12              # s; a syllable's leading consonant is sung before the beat by up to this
GLIDE_S = 0.03                  # s; pitch moves between notes with this time constant
VIBRATO = (5.5, 0.25, 0.3)      # Hz, semitones depth, s from a note's start before the vibrato grows
NOTE_FILL = 0.92                # part of a note's length the syllable lasts (a short breath between notes)
VOICE_GAIN, BACKING_GAIN = 0.8, 0.22
REVERB_S, REVERB_MIX = 0.9, 0.12
NOTE_NAMES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
CHORDS = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10)}


# ---------- song file ----------
def midi(name):
    """'F#4' -> 66"""
    n = NOTE_NAMES[name[0]] + name[1:-1].count("#") - name[1:-1].count("b")
    return 12 * (int(name[-1]) + 1) + n


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def notes(song):
    """[(start beat, beats, midi or None, syllable)] from 'syl:NOTE:beats' tokens ('-:r:1' rest, '~' slur);
    the melody is played song['repeat'] times."""
    out, beat = [], 0.0
    tokens = [t for t in song["melody"].split() if t != "|"]
    for _ in range(song.get("repeat", 1)):
        for tok in tokens:
            syl, note, beats = tok.split(":")
            beats = float(beats)
            out.append((beat, beats, None if note == "r" else midi(note), syl))
            beat += beats
    return out


def transpose(song):
    """Semitones that bring the song's average note to TARGET_MEAN_HZ (or the file's own 'transpose')."""
    if "transpose" in song:
        return song["transpose"]
    ms = [m for _, _, m, _ in notes(song) if m is not None]
    return round(12 * np.log2(TARGET_MEAN_HZ / hz(np.mean(ms))))


def chord_notes(name):
    """'F#m7' -> (root pitch class, intervals)"""
    root = NOTE_NAMES[name[0]]
    rest = name[1:]
    if rest[:1] in ("#", "b"):
        root += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return root % 12, CHORDS[rest]


# ---------- voice: pitch analysis and PSOLA ----------
def trim(x, level=0.02):
    e = np.sqrt(np.convolve(x ** 2, np.ones(441) / 441, "same"))
    on = np.nonzero(e > level * max(e.max(), 1e-9) / 0.3)[0]
    return x[max(0, on[0] - 220):on[-1] + 220] if len(on) else x


def f0_track(x):
    """Per HOP frame: period in samples (0 = unvoiced)."""
    lo, hi = int(SR / F0_RANGE[1]), int(SR / F0_RANGE[0])
    rms_all = np.sqrt((x ** 2).mean())
    periods = []
    for i in range(0, max(1, len(x) - WIN), HOP):
        f = x[i:i + WIN]
        if len(f) < WIN or np.sqrt((f ** 2).mean()) < 0.3 * rms_all:
            periods.append(0)
            continue
        spec = np.fft.rfft(f * np.hanning(WIN), 4096)
        ac = np.fft.irfft(np.abs(spec) ** 2)[:hi + 1]
        ac /= ac[0] + 1e-12
        best = lo + np.argmax(ac[lo:hi])
        periods.append(best if ac[best] > VOICED_R else 0)
    p = np.array(periods, float)
    sm = p.copy()                                    # median of 5 frames removes single octave jumps
    for i in range(2, len(p) - 2):
        win = p[i - 2:i + 3]
        sm[i] = np.median(win) if np.count_nonzero(win) >= 3 else 0
    return sm


def pitch_marks(x, per):
    """Analysis marks [(sample, period)]: one per pitch period on voiced parts, every UNVOICED_P elsewhere."""
    marks, t = [], 0
    sign = 1 if x.max() >= -x.min() else -1
    while t < len(x):
        p = per[min(len(per) - 1, t // HOP)]
        if p:
            p = int(p)
            a, b = max(0, t - p // 3), min(len(x), t + p // 3 + 1)
            t = a + int(np.argmax(sign * x[a:b])) if b > a else t
            marks.append((t, p))
            t += p
        else:
            marks.append((t, UNVOICED_P))
            t += UNVOICED_P
    return marks


def voiced_span(per):
    v = np.nonzero(per)[0]
    return (v[0] * HOP, v[-1] * HOP + WIN) if len(v) else (0, 0)


def sing_syllable(x, pitches, dur):
    """x (a spoken syllable) sung for dur seconds on pitches [(seconds, Hz)] (one note, or a slur over several).
    Returns (audio, onset seconds: the consonant before the vowel, to be placed before the beat)."""
    per = f0_track(x)
    va, vb = voiced_span(per)
    if vb <= va:                                     # nothing voiced (a whispered syllable): just fit the length
        va, vb = 0, len(x)
    va, vb = min(va, len(x)), min(vb, len(x))
    n_out = int(dur * SR)
    onset = min(va, int(ONSET_MAX_S * SR))
    head, tail = va, len(x) - vb                     # consonants before / after the vowel keep their speed
    body_out = n_out + onset - head - tail
    if body_out < 0.3 * (vb - va):                   # too short a note: squeeze everything evenly
        scale = (n_out + onset) / len(x)
        def src(t):
            return t / scale
    else:
        def src(t):
            if t < head:
                return t
            if t < head + body_out:
                return va + (t - head) * (vb - va) / body_out
            return vb + (t - head - body_out)
    total = n_out + onset
    # target pitch along the output: notes in order, smoothed (glide) with a vibrato that grows into long notes
    f0 = np.zeros(total)
    ends = head + (np.cumsum([sec for sec, _ in pitches]) * SR).astype(int)
    starts = [head] + list(ends[:-1])
    for i in range(len(pitches)):
        f0[0 if i == 0 else starts[i]:total if i == len(pitches) - 1 else ends[i]] = pitches[i][1]
    alpha = 1 - np.exp(-1 / (GLIDE_S * SR))
    log_f = np.log(f0)
    sm = np.empty_like(log_f)
    acc = log_f[0]
    for i in range(0, total, 64):                    # smoothing in blocks of 64 samples is plenty
        acc += (log_f[i] - acc) * (1 - (1 - alpha) ** 64)
        sm[i:i + 64] = acc
    t = np.arange(total) / SR
    note_start = np.zeros(total)
    for a in starts:
        note_start[a:] = a / SR
    since = np.clip(t - note_start - VIBRATO[2], 0, None)
    vib = VIBRATO[1] * np.minimum(1, since / 0.3) * np.sin(2 * np.pi * VIBRATO[0] * t)
    target = np.exp(sm) * 2 ** (vib / 12)
    # TD-PSOLA: grains two input periods long, placed at the target period
    marks = pitch_marks(x, per)
    pos = np.array([m for m, _ in marks])
    y, w = np.zeros(total + 2 * SR // 50), np.zeros(total + 2 * SR // 50)
    out = 0
    while out < total:
        s = src(out)
        k = int(np.argmin(np.abs(pos - s)))
        m, p = marks[k]
        voiced = va <= s < vb and p != UNVOICED_P
        win = np.hanning(2 * p + 1)
        a, b = m - p, m + p + 1
        grain = np.zeros(2 * p + 1)
        ga, gb = max(0, a), min(len(x), b)
        grain[ga - a:gb - a] = x[ga:gb]
        oa = out - p
        lo = max(0, oa)
        hi = min(len(y), oa + 2 * p + 1)
        if hi > lo:
            y[lo:hi] += (grain * win)[lo - oa:hi - oa]
            w[lo:hi] += win[lo - oa:hi - oa]
        out += max(20, int(SR / target[min(out, total - 1)])) if voiced else p
    y = y[:total] / np.maximum(w[:total], 0.5)
    fade = int(0.01 * SR)
    fade = min(fade, len(y) // 4)                    # a very short syllable (fast rap) gets shorter fades
    y[:fade] *= np.linspace(0, 1, fade)
    y[len(y) - fade * 3:] *= np.linspace(1, 0, fade * 3)
    return y, onset / SR


def segments(song, shift):
    """Sung syllables [(start s, seconds, syllable, [(seconds, Hz)])]: a syllable and the slurs ('~') after it."""
    spb = 60.0 / song["bpm"]
    intro = song.get("intro_bars", 1) * song["meter"] * spb
    out = []
    for beat, beats, m, syl in notes(song):
        sec = beats * spb
        if m is None:
            continue
        if syl == "~" and out:
            out[-1][1] += sec
            out[-1][3].append((sec, hz(m + shift)))
        else:
            out.append([intro + beat * spb, sec, syl, [(sec, hz(m + shift))]])
    return out


def render_voice(song, shift, n):
    from audio import mouth
    tts = mouth._load()
    assert tts.sample_rate == SR, tts.sample_rate
    lang = song["lang"]
    spoken = {}
    y = np.zeros(n)
    for start, sec, syl, pitches in segments(song, shift):
        if syl not in spoken:
            spoken[syl] = trim(np.asarray(mouth._synth(syl, lang), float))
        dur = sec * NOTE_FILL if sec > 0.3 else sec * 0.97
        v, onset = sing_syllable(spoken[syl], pitches, dur)
        a = max(0, int((start - onset) * SR))
        b = min(n, a + len(v))
        y[a:b] += v[:b - a]
    return y


# ---------- backing ----------
def tone(f, sec, bright=1.0, decay=2.5):
    """A soft plucked / piano-like note."""
    t = np.arange(int(sec * SR)) / SR
    y = sum(np.sin(2 * np.pi * f * k * t) * bright ** (k - 1) / k ** 1.6 * np.exp(-t * decay * (1 + 0.5 * k))
            for k in range(1, 7))
    y *= np.minimum(1, t / 0.006)
    return y


def render_backing(song, shift, n):
    """Bass on the bar's first beat (and the middle in 4/4 and 6/8), the chord on the other beats; one chord per
    bar, or 'C,G' for two."""
    spb = 60.0 / song["bpm"]
    meter = song["meter"]
    bars = song["chords"].split() * song.get("repeat", 1)
    bars = [bars[0]] * song.get("intro_bars", 1) + bars + [bars[-1]]     # count-in bar and a last ringing bar
    strong = {3: (0,), 4: (0, 2), 6: (0, 3)}[meter]
    y = np.zeros(n)
    for i, bar in enumerate(bars):
        parts = bar.split(",")
        for beat in range(meter):
            name = parts[min(len(parts) - 1, beat * len(parts) // meter)]
            root, iv = chord_notes(name)
            t = (i * meter + beat) * spb
            a = int(t * SR)
            last = i == len(bars) - 1
            if last and beat:
                break
            ring = meter * spb if last else spb * 1.2
            f = hz(36 + (root + shift) % 12)                 # bass, C2..B2
            bass = 0.9 * tone(f, ring * 1.5, 0.4, 1.5) + 0.3 * tone(f * 2, ring * 1.5, 0.3, 2.0)
            chord = sum(tone(hz(55 + (root + shift + k - 7) % 12), ring, 0.6, 3.0) for k in iv) * 0.45   # G3..F#4
            if last:
                v = bass[:len(chord)] + chord
            else:
                v = bass if beat in strong else chord
            b = min(n, a + len(v))
            y[a:b] += v[:b - a]
    return y


def reverb(x):
    """Convolution with a short decaying noise tail (a small room)."""
    rng = np.random.default_rng(1)
    t = np.arange(int(REVERB_S * SR)) / SR
    ir = rng.standard_normal(len(t)) * np.exp(-t * 6.9 / REVERB_S)
    ir[:int(0.02 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum())
    size = 1 << int(np.ceil(np.log2(len(x) + len(ir))))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[:len(x)]
    return x + REVERB_MIX * wet


def length_s(song):
    beats = sum(b for _, b, _, _ in notes(song))
    return (song.get("intro_bars", 1) * song["meter"] + beats + song["meter"]) * 60.0 / song["bpm"] + 1.0


def render(song_id):
    song = json.loads((SONGS / f"{song_id}.json").read_text())
    shift = transpose(song)
    n = int(length_s(song) * SR)
    voice = render_voice(song, shift, n)
    backing = render_backing(song, shift, n)
    voice *= VOICE_GAIN / max(np.abs(voice).max(), 1e-9)
    backing *= BACKING_GAIN / max(np.abs(backing).max(), 1e-9)
    mix = reverb(voice + backing)
    mix *= 0.9 / np.abs(mix).max()
    path = SONGS / f"{song_id}.wav"
    sf.write(path, mix.astype(np.float32), SR, subtype="PCM_16")
    print(f"{path}  {len(mix) / SR:.1f} s, transposed {shift:+d}")
    return path


if __name__ == "__main__":
    ids = sys.argv[1:] or sorted(p.stem for p in SONGS.glob("*.json"))
    for i in ids:
        render(i)
