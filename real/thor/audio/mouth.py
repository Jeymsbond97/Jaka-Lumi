"""Speaking: text -> speech (Supertonic-3, English and Korean, on the robot's GPU: audio/tts_gpu.py) -> USB speaker.

    python audio/mouth.py "Hello, I am Lumi."
    python audio/mouth.py "안녕하세요, 저는 루미예요."

Long answers are split into sentences: the next sentence is synthesised while the current one plays,
so Lumi starts talking after the first sentence is ready (about 1 s). say_stream() takes sentences while
they are still being written by the LLM, so speech starts before the whole answer exists.
Fixed phrases (greetings) are synthesised once and kept (CACHED), so they play at once.
While Lumi talks the microphone is muted (mic.speaking), so it never hears itself. The clip mic keeps listening (for
"stop"): what the speaker played is kept for ECHO_KEEP_S, and own_voice() tells Lumi's voice in a clip-mic utterance
from a visitor's by comparing the two sounds at the same time (echo()).
"""
import collections
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
SPEED_MIN, SPEED_MAX = 0.72, 1.2              # what "speak slower / faster" may set (Supertonic takes 0.7 to 2.0)
SPLIT_WORDS = 8                               # TTS on the CPU only: a first sentence this long is said in two parts,
                                              # cut after its first comma (first part ~0.7 s instead of ~1.8 s); on
                                              # the GPU a whole sentence takes 0.07-0.2 s and is said in one piece
VOLUME = 55                                   # % of the USB speaker mixer (100 % disturbed people in the office)
CACHED = ["Hi, I'm Lumi, the assistant robot. How can I help you?", "안녕하세요, 저는 루미예요. 무엇을 도와드릴까요?",
          "Yes?", "네?", "Okay, I'm coming.", "네, 갈게요.", "I'm right here.",
          "Sorry, I can't get closer from here.", "How can I help you?", "무엇을 도와드릴까요?",
          "Let me check.", "확인해 볼게요.", "Okay, I'll be quiet.", "네, 조용히 할게요.",
          "Sorry, I'm not connected to the internet right now, so I can't look that up.",
          "Yes? How can I help?", "네? 무엇을 도와드릴까요?",
          "Welcome back! How can I help you?", "다시 오셨네요, 무엇을 도와드릴까요?", "Okay, I'm going to my charging dock.", "네, 충전소로 갈게요.",
          "Sorry, driving is switched off."] + [f"Okay, I'm going to p{i}." for i in range(1, 11)]

_tts = None
_style = None
_gpu = False                                  # synthesis on the GPU (audio/tts_gpu.py engines loaded)
_cache = {}
_volume_set = False
_recent = []                                  # (time, sentence) Lumi said lately: to tell its own echo from a visitor
ECHO_KEEP_S = 30.0                            # s of played sound kept to recognise Lumi's own voice in the clip mic
ECHO_LAG_S = (-0.3, 1.0)                      # s the clip mic may hear the speaker later than _play started it (ALSA
                                              # and the wireless link's buffers; < 0: the two clocks' read-out times)
ECHO_MIN = 0.6                                # spectrogram correlation from which a clip-mic sound is Lumi's own voice
                                              # (tests/echo_check.py, made: own voice 0.67 and more, a visitor talking
                                              # over Lumi 0.39 at most; the owner's real clips against Lumi's lines at
                                              # any time: 1.8 % reach 0.6, 4.7 % 0.55); an estimate until checked live
ECHO_TOP_DB = 15                              # frames compared: those within this of the sound's loudest
ECHO_MIN_FRAMES = 12                          # ... at least this many (10 ms each), else no judgement
_played = collections.deque()                 # [t_start, t_end, float32 16 kHz audio] of what the speaker played
last_echo = None                              # echo() of the last own_voice() call (lumi.py logs it)
last_voice = 0.0                              # time.time() when the last say_stream() began to play (lumi.py logs it)


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


SPEED_FILE = ROOT / "data" / "speech_speed.txt"        # set by voice ("speak slower", assistant/voice_words.py)


def speed():
    try:
        return max(SPEED_MIN, min(SPEED_MAX, float(SPEED_FILE.read_text().strip())))
    except (FileNotFoundError, ValueError):
        return SPEED


def set_speed(value):
    """Store the speaking speed; the cached fixed phrases were made at the old one, so they are made when said."""
    SPEED_FILE.write_text(f"{max(SPEED_MIN, min(SPEED_MAX, value)):.2f}")
    _cache.clear()


def _set_volume():
    global _volume_set
    if not _volume_set:
        set_volume()
        _volume_set = True


def _load():
    global _tts, _style, _gpu
    _set_volume()
    if _tts is None:
        from supertonic import TTS
        from audio import tts_gpu
        _tts = TTS(model="supertonic-3", model_dir=ROOT / "models/supertonic3", auto_download=False,
                   intra_op_num_threads=8)
        _style = _tts.get_voice_style(VOICE)
        try:
            tts_gpu.use(_tts.model)
            _gpu = True
        except Exception as e:                # no engine file, no GPU, no TensorRT: the CPU, 5-10x slower
            print(f"mouth: TTS on the CPU ({e})", flush=True)
    return _tts


def lang_of(text):
    return "ko" if re.search(r"[가-힣]", text) else "en"


def sentences(text):
    parts = re.split(r"(?<=[.!?。！？])\s+", text.strip())
    return [p for p in parts if p]


def first_parts(sentence):
    """TTS on the CPU: a long first sentence cut after its first comma (3 words in or later), so the voice starts
    sooner."""
    m = re.search(r"[,;]\s", sentence)
    if _gpu or len(sentence.split()) < SPLIT_WORDS or not m or len(sentence[:m.start()].split()) < 3:
        return [sentence]
    return [sentence[:m.start() + 1], sentence[m.end():]]


_play_lock = threading.Lock()                # one sentence at a time (a skill's result is spoken from another thread)


def _play(wav, rate, abort=None):
    """Play; returns False if aborted."""
    wav = np.clip(np.asarray(wav, np.float32).reshape(-1), -1, 1)
    pcm = (wav * 32767).astype(np.int16).tobytes()
    with _play_lock:
        mic.speaking(True)
        now = time.time()
        entry = [now, now + len(wav) / rate, np.interp(np.arange(0, len(wav), rate / mic.RATE), np.arange(len(wav)),
                                                       wav).astype(np.float32)]
        _played.append(entry)
        while _played and _played[0][1] < now - ECHO_KEEP_S:
            _played.popleft()
        try:
            done = _play_pcm(pcm, rate, abort)
            if not done:
                entry[1] = time.time()            # cut short: nothing played after this
            return done
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


def _bands(x):
    """Log energy in 16 bands (200-4000 Hz) every 10 ms: frames x 16."""
    n = (len(x) - 400) // 160 + 1
    if n < 1:
        return np.zeros((0, 16), np.float32)
    frames = x[np.arange(400)[None, :] + 160 * np.arange(n)[:, None]] * np.hanning(400)
    spec = np.abs(np.fft.rfft(frames, 512)) ** 2                 # 31.25 Hz per bin
    edges = np.geomspace(200, 4000, 17) / 31.25
    e = np.stack([spec[:, int(a):max(int(a) + 1, int(b))].sum(1) for a, b in zip(edges[:-1], edges[1:])], 1)
    return np.log(e + 1e-4 * e.max() + 1e-12)


def echo(audio, t_end):
    """How much a microphone sound (int16 mono 16 kHz, recorded until t_end, time.time()) is Lumi's own voice: the
    best correlation of its spectrogram with that of what the speaker played then (lags ECHO_LAG_S), over the mic's
    loud frames (ECHO_TOP_DB of its loudest); None when nothing was played then or the sound is too short. A visitor
    talking over Lumi, or saying Lumi's words after it, scores low."""
    rate, (lo, hi) = mic.RATE, ECHO_LAG_S
    t0 = t_end - len(audio) / rate - hi                 # the reference: what played from t0 on
    ref = np.zeros(len(audio) + int((hi - lo) * rate), np.float32)
    for start, end, wav in list(_played):
        a = int((start - t0) * rate)                    # the sentence's first sample in ref
        b = min(len(ref), a + min(len(wav), int((end - start) * rate)))
        if b > max(a, 0):
            ref[max(a, 0):b] = wav[max(0, -a):b - a]
    if not ref.any():
        return None
    m, r = _bands(np.asarray(audio, np.float32) / 32768.0), _bands(ref)
    level = m.mean(1)
    loud = level > level.max() - ECHO_TOP_DB / 10 * np.log(10)
    if loud.sum() < ECHO_MIN_FRAMES:
        return None
    m = m[loud] - m[loud].mean(0)
    best = 0.0
    for k in range(0, len(r) - len(loud) + 1, 2):       # 20 ms steps over the lag window
        seg = r[k:k + len(loud)][loud]
        seg = seg - seg.mean(0)
        den = np.sqrt((seg ** 2).sum() * (m ** 2).sum())
        if den > 0:
            best = max(best, float((seg * m).sum() / den))
    return best


def own_voice(u):
    """A clip-mic utterance (mic.Utterance) that is Lumi's own voice from its speaker (echo() >= ECHO_MIN)."""
    global last_echo
    if getattr(u, "source", "") != "clip" or getattr(u, "mono", None) is None:
        return False
    last_echo = echo(u.mono, u.t_end)
    return last_echo is not None and last_echo >= ECHO_MIN


def _synth(text, lang):
    if text in _cache:
        return _cache[text]
    wav, _ = _tts.synthesize(text, voice_style=_style, lang=lang, total_steps=STEPS, speed=speed())
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
                    for part in [s] if spoken else first_parts(s):
                        spoken.append(part)
                        q.put((part, _synth(part, lang or lang_of(part))))
        finally:
            q.put(None)

    global last_voice
    threading.Thread(target=synth, daemon=True).start()
    first = True
    while (item := q.get()) is not None:
        text, wav = item
        if first:
            last_voice, first = time.time(), False
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
