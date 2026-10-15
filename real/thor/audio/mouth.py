"""Speaking: text -> speech (Supertonic-3, English and Korean, on the robot) -> USB speaker.

    python audio/mouth.py "Hello, I am Lumi."
    python audio/mouth.py "안녕하세요, 저는 루미예요."

Long answers are split into sentences: the next sentence is synthesised while the current one plays,
so Lumi starts talking after the first sentence is ready (about 1 s). say_stream() takes sentences while
they are still being written by the LLM, so speech starts before the whole answer exists.
Fixed phrases (greetings) are synthesised once and kept (CACHED), so they play at once.
While Lumi talks the microphone is muted (mic.speaking), so it never hears itself.
"""
import pathlib
import queue
import re
import subprocess
import sys
import threading
import time

import numpy as np

from audio import mic

ROOT = pathlib.Path(__file__).resolve().parents[1]      # the project folder
DEVICE = "plughw:CARD=Device,DEV=0"          # "USB Audio Device"
VOICE = "F1"                                  # F1-F5 female, M1-M5 male
STEPS = 4                                     # quality/speed: 4 fast ... 8 best
SPEED = 0.92                                  # < 1 = slower; 1.05 sounded rushed
VOLUME = 55                                   # % of the USB speaker mixer (100 % disturbed people in the office)
CACHED = ["Hi, I'm Lumi, the assistant robot. How can I help you?", "안녕하세요, 저는 루미예요. 무엇을 도와드릴까요?",
          "Yes?", "네?", "Okay, I'm coming.", "네, 갈게요.", "I'm right here.",
          "Sorry, I can't get closer from here.", "How can I help you?", "무엇을 도와드릴까요?",
          "Let me check.", "확인해 볼게요.", "Okay, I'll be quiet.", "네, 조용히 할게요.",
          "Sorry, I'm not connected to the internet right now, so I can't look that up.",
          "Yes? How can I help?", "네? 무엇을 도와드릴까요?", "Okay, I'm going to my charging dock.", "네, 충전소로 갈게요.",
          "Sorry, driving is switched off."] + [f"Okay, I'm going to p{i}." for i in range(1, 11)]

_tts = None
_style = None
_cache = {}
_volume_set = False
_recent = []                                  # (time, sentence) Lumi said lately: to tell its own echo from a visitor


def recent_speech(seconds=30.0):
    """What Lumi said in the last seconds (lumi.py ignores its own voice picked up by the clip mic).
    Long sentences take 15 s and more to say, so the window is long."""
    now = time.time()
    return " ".join(t for when, t in _recent if now - when < seconds)


VOLUME_FILE = ROOT / "data" / "volume.txt"             # set from the dashboard (api/server.py /volume); overrides VOLUME


def volume():
    try:
        return max(0, min(100, int(VOLUME_FILE.read_text().strip())))
    except (FileNotFoundError, ValueError):
        return VOLUME


def set_volume(percent=None):
    """Apply (and with percent: store) the speaker volume."""
    if percent is not None:
        VOLUME_FILE.write_text(str(int(max(0, min(100, percent)))))
    subprocess.run(["amixer", "-q", "-c", "Device", "sset", "Speaker", f"{volume()}%"], check=False)


def _set_volume():
    global _volume_set
    if not _volume_set:
        set_volume()
        _volume_set = True


def _load():
    global _tts, _style
    _set_volume()
    if _tts is None:
        from supertonic import TTS
        _tts = TTS(model="supertonic-3", model_dir=ROOT / "models/supertonic3", auto_download=False,
                   intra_op_num_threads=8)
        _style = _tts.get_voice_style(VOICE)
    return _tts


def lang_of(text):
    return "ko" if re.search(r"[가-힣]", text) else "en"


def sentences(text):
    parts = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    return [p for p in parts if p]


_play_lock = threading.Lock()                # one sentence at a time (a skill's result is spoken from another thread)


def _play(wav, rate, abort=None):
    """Play; returns False if aborted."""
    pcm = (np.clip(wav, -1, 1) * 32767).astype(np.int16).tobytes()
    with _play_lock:
        mic.speaking(True)
        try:
            return _play_pcm(pcm, rate, abort)
        finally:
            mic.speaking(False)


def _play_pcm(pcm, rate, abort):
    p = subprocess.Popen(["aplay", "-q", "-D", DEVICE, "-f", "S16_LE", "-r", str(rate), "-c", "1", "-t", "raw"],
                         stdin=subprocess.PIPE)
    def feed():
        try:
            p.stdin.write(pcm)
            p.stdin.close()
        except (BrokenPipeError, ValueError):     # aplay was killed (abort)
            pass
    threading.Thread(target=feed, daemon=True).start()
    while p.poll() is None:
        if abort and abort():
            p.kill()
            return False
        time.sleep(0.05)
    return True


def _synth(text, lang):
    if text in _cache:
        return _cache[text]
    wav, _ = _tts.synthesize(text, voice_style=_style, lang=lang, total_steps=STEPS, speed=SPEED)
    return np.asarray(wav).reshape(-1)


def say_stream(pieces, lang=None, abort=None):
    """Speak text that arrives in pieces (e.g. sentences from a streaming LLM); returns the full text.
    Synthesis of the next sentence runs while the current one plays."""
    tts = _load()
    rate = tts.sample_rate
    q = queue.Queue()                           # unbounded: the synth thread always finishes
    spoken = []

    def synth():
        try:
            for piece in pieces:
                for s in sentences(piece):
                    spoken.append(s)
                    q.put((s, _synth(s, lang or lang_of(s))))
        finally:
            q.put(None)

    threading.Thread(target=synth, daemon=True).start()
    while (item := q.get()) is not None:
        text, wav = item
        _recent.append((time.time(), text))
        del _recent[:-12]
        if not _play(wav, rate, abort):
            break
    return " ".join(spoken)


def say(text, lang=None, abort=None):
    """Speak text and return when finished (or when abort() becomes True)."""
    say_stream([text], lang, abort)


def warm_up():
    """Load the model, run it once so the first real sentence is fast, and prepare the fixed phrases."""
    tts = _load()
    tts.synthesize("Hi.", voice_style=_style, lang="en", total_steps=2)
    for text in CACHED:
        _cache[text] = _synth(text, lang_of(text))


if __name__ == "__main__":
    say(" ".join(sys.argv[1:]) or "Hello, I am Lumi Robot Assistant. How can I help you?")
