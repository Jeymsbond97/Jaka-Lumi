"""Sounds and words where Lumi must say nothing (tests/blind/train/silence_noise.py): music, TV, captions, coughs,
laughter, visitors talking to each other, Lumi's own voice heard back, a word in an empty room. No audio, no LLM:
each heard text goes the text path of a turn as it is in audio/ears.transcribe (speech seconds, subtitle texts) and
assistant/lumi.py (no talk open: only a wake word starts one; a talk open: own echo, noise words, else an answer).

    .venv/bin/python tests/silence_check.py        # prints the cases Lumi would answer although it must say nothing
    .venv/bin/python tests/silence_check.py r2     # round 2's train set (tests/blind/r2/train/silence_noise.py)
"""
import importlib
import re
import sys

from assistant import brain, lumi
from audio import ears


def fate(case):
    """"dropped", "ignored" or "speaks" for one case."""
    text, ctx = case["heard"].strip(), case["ctx"]
    s = ctx.get("speech_s")
    if not text or s is not None and s < ears.MIN_SPEECH_S:
        return "dropped"                                   # Silero VAD: whisper is not asked
    if ears.NOT_SAID.search(text) or text.startswith(("[", "(", "*")) or \
            s is not None and s < ears.SPEECH_PER_SYLLABLE * ears.syllables(text):
        return "dropped"
    if ctx["session"] != "open":                           # nobody talking with Lumi (a goodbye ends the talk)
        return "speaks" if lumi.WAKE.search(text) or lumi.HELLO_ONLY.match(text) else "ignored"
    said = set(re.findall(r"\w+", (ctx.get("lumi_said") or "").lower()))
    words = re.findall(r"\w+", text.lower())
    if ctx.get("from_lumi_speaker") and words and sum(w in said for w in words) / len(words) >= 0.6:
        return "ignored"                                   # Lumi.own_echo
    if lumi.NOISE_WORDS.fullmatch(text) or brain.to_someone_else(text):
        return "ignored"
    return "speaks"


def main(CASES):
    bad = [(c, fate(c)) for c in CASES if c["expect"] == "nothing" and fate(c) == "speaks"]
    for c, f in bad:
        print(f"SPEAKS  {c['kind']:15s} {c['ctx']['session']:10s} {c['heard']!r}")
    n = sum(c["expect"] == "nothing" for c in CASES)
    print(f"{n - len(bad)}/{n} silent as they must be")


if __name__ == "__main__":
    rnd = "r2." if "r2" in sys.argv[1:] else ""
    main(importlib.import_module(f"tests.blind.{rnd}train.silence_noise").CASES)
