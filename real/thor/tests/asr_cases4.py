"""Music in the room, for tests/asr_check.py --cases 4 (2026-10-22: soft music, nobody speaking, became "-끝-" -> goodbye):
music only (kind "noise": right is no wake word and no motion, nothing said), and speech over soft music (the speech
cases' own judgement). The music is made here: piano-like chords, bass, a melody and a hi-hat in four tempos, or
an excerpt of Lumi's public domain songs (data/songs/<id>.wav, sung words over chords; never data/songs/mine).

A case's "music" is "synth:<seed>:<seconds>" or "song:<id>:<start s>:<seconds>"; "music_db" is how far the speech is
above the music (rms).
"""
import pathlib
import random
import wave

import numpy as np

from tests.asr_cases import CASES as SPOKEN

RATE = 16000
SONGS = pathlib.Path(__file__).resolve().parents[1] / "data" / "songs"
MUSIC_DB = 6.0                  # speech this much louder than the music (soft background music at a booth)
CASES = []


def synth(seed, seconds):
    """Instrumental music: a I-V-vi-IV progression, decaying piano-like notes with harmonics, a bass, a melody
    and a hi-hat on the beat. float32, peak 1."""
    rng = np.random.default_rng(seed)
    bpm = [72, 96, 118, 140][seed % 4]
    beat = 60.0 / bpm
    root = 48 + seed % 7                                          # MIDI note of the key
    chords = [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)]
    n = int(seconds * RATE)
    out = np.zeros(n + 4 * RATE)                                  # room for the last bar past the end

    def note(midi, start, dur, gain, harmonics=4):
        f = 440.0 * 2 ** ((midi - 69) / 12)
        t = np.arange(int(dur * RATE)) / RATE
        tone = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.5 for k in range(1, harmonics + 1))
        i = int(start * RATE)
        if i >= len(out):
            return
        seg = tone * np.exp(-3.0 * t / dur) * gain
        out[i:i + len(seg)] += seg[:len(out) - i]

    t, bar = 0.0, 0
    while t < seconds:
        ch = chords[bar % 4]
        for k in ch:
            note(root + 12 + k, t, 4 * beat, 0.25)
        note(root - 12 + ch[0], t, 2 * beat, 0.5, 2)
        note(root - 12 + ch[0], t + 2 * beat, 2 * beat, 0.5, 2)
        for b in range(4):
            note(root + 24 + ch[rng.integers(0, 3)] + rng.choice([0, 12]), t + b * beat, beat, 0.2)
            i = int((t + b * beat) * RATE)
            hat = rng.standard_normal(int(0.03 * RATE)) * np.exp(-np.arange(int(0.03 * RATE)) / 80) * 0.15
            out[i:i + len(hat)] += hat[:len(out) - i]
        t, bar = t + 4 * beat, bar + 1
    out = out[:n]
    return (out / (np.abs(out).max() + 1e-9)).astype(np.float32)


def song(sid, start, seconds):
    """An excerpt of data/songs/<sid>.wav at 16 kHz, peak 1."""
    with wave.open(str(SONGS / f"{sid}.wav")) as w:
        rate = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    x = x[int(start * rate):int((start + seconds) * rate)]
    x = np.interp(np.arange(0, len(x), rate / RATE), np.arange(len(x)), x)
    return (x / (np.abs(x).max() + 1e-9)).astype(np.float32)


def music(spec, seconds=None):
    """The case's music; `seconds` (under speech: the speech's length) instead of the spec's."""
    kind, *a = spec.split(":")
    if kind == "synth":
        return synth(int(a[0]), seconds or float(a[1]))
    return song(a[0], float(a[1]), seconds or float(a[2]))


for k in range(16):
    CASES.append({"kind": "noise", "lang": "none", "text": f"(music {k})", "say": [],
                  "music": f"synth:{k}:{[1.5, 2.5, 4.0, 6.0][k % 4]}"})
for sid in ["arirang", "happy_birthday", "row_row", "three_bears", "twinkle"]:
    for start in (2.0, 14.0):
        CASES.append({"kind": "noise", "lang": "none", "text": f"({sid} at {start:.0f} s)", "say": [],
                      "music": f"song:{sid}:{start}:3.0"})
R = random.Random(4)
for i, c in enumerate(R.sample(SPOKEN, 40)):
    CASES.append({**c, "music": f"synth:{100 + i}:1.0", "music_db": MUSIC_DB})
for i, (lang, t) in enumerate([("en", "Sing a song."), ("en", "Let's do some music."), ("en", "Lumi, stop."),
                               ("en", "Hi Lumi."), ("ko", "노래 불러 줘."), ("ko", "음악 틀어 줘."), ("ko", "루미야."),
                               ("ko", "멈춰.")]):
    kind = "wake" if "Lumi." in t or t == "루미야." else "command"
    CASES.append({"kind": kind, "lang": lang, "text": t, "say": [(lang, t)], "music": f"synth:{200 + i}:1.0",
                  "music_db": MUSIC_DB})
