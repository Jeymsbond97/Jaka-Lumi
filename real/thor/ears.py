"""Listening: one utterance from the head microphone array (via mic.py) turned into text.

    python ears.py            # listen once, print what was said (English or Korean)

Recording, speech detection and "do not listen while Lumi talks" are in mic.py (one always-on recording that
lumi.py also uses for the wake word). Speech-to-text: whisper.cpp (GPU) server with large-v3-turbo on
127.0.0.1:8096, started when needed.
"""
import io
import json
import pathlib
import subprocess
import time
import urllib.request
import uuid
import wave

import mic

HERE = pathlib.Path(__file__).resolve().parent
RATE = mic.RATE
STT_URL = "http://127.0.0.1:8096"
WHISPER_SERVER = HERE / "whisper.cpp/build/bin/whisper-server"
WHISPER_MODEL = HERE / "models/ggml-large-v3-turbo-q5_0.bin"
PROMPT = "Hi Lumi. Hey Lumi. 루미야."   # helps whisper spell the robot's name
last = {}                        # levels of the last listen() call, for the log: noise, threshold, peak


def ensure_stt_server():
    try:
        urllib.request.urlopen(f"{STT_URL}/", timeout=1)
        return
    except OSError:
        pass
    log = open(HERE / "whisper_server.log", "a")
    subprocess.Popen([str(WHISPER_SERVER), "-m", str(WHISPER_MODEL), "--host", "127.0.0.1", "--port", "8096",
                      "-l", "auto", "-nt"], stdout=log, stderr=log, start_new_session=True)
    for _ in range(120):
        time.sleep(0.5)
        try:
            urllib.request.urlopen(f"{STT_URL}/", timeout=1)
            return
        except OSError:
            pass
    raise RuntimeError("whisper-server did not start, see whisper_server.log")


def record(wait_s=8.0, on_start=None, abort=None):
    """Wait up to wait_s for speech to start, then until it ends. Returns a mic.Utterance or None.
    abort: optional function checked every 30 ms; when it returns True, stop and return None."""
    m = mic.get()
    m.clear()                                    # only speech that starts from now on
    t0, started = time.time(), False
    try:
        while True:
            if abort and abort():
                return None
            u = m.next(0.03)
            if u is not None and u.t_end > t0:
                return u
            if m.in_speech and not started:
                started = True
                if on_start:
                    on_start()
            if not m.in_speech and not started and time.time() - t0 > wait_s:
                return None
    finally:
        last.update(noise=round(m.noise), threshold=round(m.threshold))


def transcribe(audio, prompt=PROMPT):
    """int16 mono 16 kHz -> text (empty string if nothing understood)."""
    ensure_stt_server()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(audio.tobytes())
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"response_format\"\r\n\r\njson\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"prompt\"\r\n\r\n{prompt}\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{STT_URL}/inference", body,
                                 {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = json.loads(r.read()).get("text", "").strip()
    # whisper writes things like "[BLANK_AUDIO]" or "(music)" for non-speech
    return "" if (text.startswith("[") or text.startswith("(")) else text


def listen(wait_s=8.0, on_start=None, abort=None, full=False):
    """Record one utterance and transcribe it. Returns text or None (nobody spoke, or aborted).
    full=True: returns (text, mic.Utterance) instead, for the sound direction."""
    u = record(wait_s, on_start, abort)
    if u is not None:
        last["peak"] = round(u.peak)
    if u is None or u.seconds < 0.4:
        return (None, u) if full else None
    text = transcribe(u.mono) or None
    return (text, u) if full else text


if __name__ == "__main__":
    ensure_stt_server()
    print("Say something (English or Korean)...")
    u = record(10, on_start=lambda: print("  (hearing you)"))
    if u is None:
        print("nothing heard")
    else:
        t = time.time()
        print(f"you said: {transcribe(u.mono)!r}   ({u.seconds:.1f} s audio, STT {time.time() - t:.2f} s)")
