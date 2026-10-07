"""Speaking: text -> speech (Supertonic-3, English and Korean, on the robot) -> USB speaker.

    python mouth.py "Hello, I am Lumi."
    python mouth.py "안녕하세요, 저는 루미예요."

Long answers are split into sentences: the next sentence is synthesised while the current one plays,
so Lumi starts talking after the first sentence is ready (about 1 s).
"""
import pathlib
import queue
import re
import subprocess
import sys
import threading
import time

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
DEVICE = "plughw:CARD=Device,DEV=0"          # "USB Audio Device"
VOICE = "F1"                                  # F1-F5 female, M1-M5 male
STEPS = 5                                     # quality/speed: 4 fast ... 8 best
SPEED = 1.05

_tts = None
_style = None


def _load():
    global _tts, _style
    if _tts is None:
        from supertonic import TTS
        _tts = TTS(model="supertonic-3", model_dir=HERE / "models/supertonic3", auto_download=False,
                   intra_op_num_threads=8)
        _style = _tts.get_voice_style(VOICE)
    return _tts


def lang_of(text):
    return "ko" if re.search(r"[가-힣]", text) else "en"


def sentences(text):
    parts = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    return [p for p in parts if p]


def _play(wav, rate, abort=None):
    """Play; returns False if aborted."""
    pcm = (np.clip(wav, -1, 1) * 32767).astype(np.int16).tobytes()
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


def say(text, lang=None, abort=None):
    """Speak text and return when finished (or when abort() becomes True)."""
    tts = _load()
    lang = lang or lang_of(text)
    rate = tts.sample_rate
    q = queue.Queue()                           # unbounded: the synth thread always finishes

    def synth():
        for s in sentences(text):
            wav, _ = tts.synthesize(s, voice_style=_style, lang=lang, total_steps=STEPS, speed=SPEED)
            q.put(np.asarray(wav).reshape(-1))
        q.put(None)

    threading.Thread(target=synth, daemon=True).start()
    while (wav := q.get()) is not None:
        if not _play(wav, rate, abort):
            break


def warm_up():
    """Load the model and run it once so the first real sentence is fast."""
    tts = _load()
    tts.synthesize("Hi.", voice_style=_style, lang="en", total_steps=2)


if __name__ == "__main__":
    say(" ".join(sys.argv[1:]) or "Hello, I am Lumi Robot Assistant. How can I help you?")
