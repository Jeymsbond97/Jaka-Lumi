"""Listening: record one utterance from the head microphone array and turn it into text.

    python ears.py            # listen once, print what was said (English or Korean)

Microphone: AIUI-USB-MC gives 8 channels at 16 kHz; channels 0-5 are the six mics (6-7 are silent).
They are averaged. A simple energy detector finds where speech starts and ends.
Speech-to-text: whisper.cpp (GPU) server with large-v3-turbo on 127.0.0.1:8096, started when needed.
Never listen while Lumi itself is speaking: the speaker is ~25x louder than a voice in the mics.
"""
import io
import json
import pathlib
import subprocess
import time
import urllib.request
import uuid
import wave

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
MIC = "hw:CARD=AIUIUSBMC"
RATE, CHANNELS, MIC_CHANNELS = 16000, 8, slice(0, 6)
FRAME = 480                      # 30 ms
STT_URL = "http://127.0.0.1:8096"
WHISPER_SERVER = HERE / "whisper.cpp/build/bin/whisper-server"
WHISPER_MODEL = HERE / "models/ggml-large-v3-turbo-q5_0.bin"

START_FACTOR = 3.0               # speech = louder than START_FACTOR x background noise
MIN_LEVEL = 400                  # ... and at least this RMS
START_FRAMES = 4                 # 120 ms of speech to start
END_SILENCE = 0.9                # s of silence that ends the utterance
MAX_UTTERANCE = 12.0             # s


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
    """Wait up to wait_s for speech, record until silence. Returns int16 mono audio or None.
    abort: optional function checked every 30 ms; when it returns True, stop and return None."""
    proc = subprocess.Popen(["arecord", "-q", "-D", MIC, "-f", "S16_LE", "-r", str(RATE), "-c", str(CHANNELS),
                             "-t", "raw"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    nbytes = FRAME * CHANNELS * 2
    noise, frames, voiced, silent = [], [], 0, 0
    t0 = time.time()
    started = False
    try:
        while True:
            raw = proc.stdout.read(nbytes)
            if len(raw) < nbytes or (abort and abort()):
                return None
            x = np.frombuffer(raw, np.int16).reshape(-1, CHANNELS)[:, MIC_CHANNELS].mean(1).astype(np.int16)
            level = float(np.sqrt(np.mean(x.astype(np.float32) ** 2)))
            if not started:
                if len(noise) < 15:                       # first 0.45 s: measure background noise
                    noise.append(level)
                    continue
                threshold = max(MIN_LEVEL, START_FACTOR * float(np.median(noise)))
                frames = (frames + [x])[-10:]             # keep 300 ms before the start
                voiced = voiced + 1 if level > threshold else 0
                if voiced >= START_FRAMES:
                    started, silent = True, 0
                    t_start = time.time()
                    if on_start:
                        on_start()
                elif time.time() - t0 > wait_s:
                    return None
                else:
                    noise = (noise + [level])[-100:]      # follow slow changes in background noise
            else:
                frames.append(x)
                silent = silent + 1 if level < threshold * 0.7 else 0
                if silent * FRAME / RATE >= END_SILENCE or time.time() - t_start > MAX_UTTERANCE:
                    return np.concatenate(frames)
    finally:
        proc.kill()


def transcribe(audio):
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
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"a.wav\"\r\n"
            f"Content-Type: audio/wav\r\n\r\n").encode() + buf.getvalue() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{STT_URL}/inference", body,
                                 {"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        text = json.loads(r.read()).get("text", "").strip()
    # whisper writes things like "[BLANK_AUDIO]" or "(music)" for non-speech
    return "" if (text.startswith("[") or text.startswith("(")) else text


def listen(wait_s=8.0, on_start=None, abort=None):
    """Record one utterance and transcribe it. Returns text or None (nobody spoke, or aborted)."""
    audio = record(wait_s, on_start, abort)
    if audio is None or len(audio) < RATE * 0.4:
        return None
    return transcribe(audio) or None


if __name__ == "__main__":
    ensure_stt_server()
    print("Say something (English or Korean)...")
    t = time.time()
    audio = record(10, on_start=lambda: print("  (hearing you)"))
    if audio is None:
        print("nothing heard")
    else:
        t = time.time()
        print(f"you said: {transcribe(audio)!r}   ({len(audio) / RATE:.1f} s audio, STT {time.time() - t:.2f} s)")
