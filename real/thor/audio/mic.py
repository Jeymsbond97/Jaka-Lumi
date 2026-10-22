"""Always-on microphone: the head mic array (and a wireless clip mic if one is plugged in), cut into utterances.

Head array (AIUI-USB-MC): 8 channels at 16 kHz; channels 0-5 are the six mics of the ring, 6-7 are silent.
It is far from a speaker's mouth, so speech-to-text works better with a wireless clip mic (DJI Mic Mini):
when its receiver shows up as a sound card (EXTERNAL_NAMES), utterances are cut from the clip mic and their
text comes from it, while the head array keeps recording in parallel for the sound direction (doa.py): the
six-mic audio of the same time span is taken from a ring buffer. Choose with mic_source.txt: auto | head | clip.

An ALSA device can be opened only once, so everything that listens goes through here. An energy detector
cuts utterances: speech starts when the level stays above START_FACTOR x the background noise for
START_FRAMES frames and ends after END_SILENCE of quiet.
While Lumi itself speaks (mouth.py calls speaking()), the head array records nothing (the speaker is ~25x
louder than a voice there). The clip mic keeps listening (BARGE_IN): its utterances are marked during_speech, so
lumi.py can stop talking when the visitor says "stop" / "thanks" or asks something new.

    python audio/mic.py        # print every utterance: source, length, level and the direction
"""
import collections
import queue
import re
import subprocess
import threading
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]      # the project folder
SOURCE_FILE = ROOT / "data" / "mic_source.txt"
DEVICE = "hw:CARD=AIUIUSBMC"
EXTERNAL_NAMES = r"DJI|Wireless|Mic Mini|MIC MINI|RX"   # sound card names of a clip-mic receiver
RATE, CHANNELS, MICS = 16000, 8, slice(0, 6)
FRAME = 480                      # 30 ms
START_FACTOR = 1.8               # speech = louder than START_FACTOR x background noise (2.5 missed
                                 # people 4-5 m away: only 1 of 4 phrases was heard, 2026-10-12)
MIN_LEVEL = 250                  # ... and at least this RMS (head array; room noise is ~180)
MIN_LEVEL_CLIP = 300             # ... (clip mic: close to the mouth, quiet room noise)
START_FRAMES = 4                 # 120 ms of speech to start
END_LEVEL = 1.0                  # quiet = below this x the start threshold (0.7 kept room noise ~180-250 "speech")
END_SILENCE = 0.6                # s of quiet that ends an utterance
MAX_UTTERANCE = 8.0              # s (12 s: in a room with music an utterance never got quiet enough
                                 # to end, every one ran the full 12 s, 2026-10-21)
PRE_ROLL = 10                    # frames kept before the start (300 ms)
AFTER_SPEAKING = 0.4             # s still ignored after Lumi stopped talking (room echo)
BARGE_IN = True                  # clip mic: keep listening while Lumi talks (interruptions)
RING_S = 20.0                    # s of head-array audio kept for the sound direction of clip-mic utterances


class Utterance:
    def __init__(self, mics, mono, t_start, t_end, peak, source, during_speech=False):
        self.mics = mics                                         # int16 (n, 6) head array (for doa), may be empty
        self.mono = mono                                         # int16 mono (for speech-to-text)
        self.t_start, self.t_end, self.peak, self.source = t_start, t_end, peak, source
        self.during_speech = during_speech                       # recorded while Lumi was talking (clip mic only)

    @property
    def seconds(self):
        return len(self.mono) / RATE


class Segmenter:
    """Energy speech detector over 30 ms frames."""

    def __init__(self, min_level):
        self.min_level = min_level
        self.levels = collections.deque(maxlen=300)              # last 9 s of frame levels, for the noise floor
        self.before = collections.deque(maxlen=PRE_ROLL)
        self.frames, self.voiced, self.silent, self.peak = [], 0, 0, 0.0
        self.in_speech, self.started = False, 0.0
        self.noise = self.threshold = 0.0

    def reset(self):
        self.before.clear()
        self.frames, self.voiced, self.in_speech = [], 0, False

    def feed(self, frame, level, now):
        """Returns (frames, t_start, t_end, peak) when an utterance ended, else None."""
        if not self.in_speech:
            self.levels.append(level)
            self.noise = float(np.percentile(self.levels, 30))
            self.threshold = max(self.min_level, START_FACTOR * self.noise)
            self.before.append(frame)
            self.voiced = self.voiced + 1 if level > self.threshold else 0
            if self.voiced >= START_FRAMES:
                self.in_speech, self.started = True, now - (len(self.before) * FRAME / RATE)
                self.frames, self.silent, self.peak = list(self.before), 0, level
            return None
        self.frames.append(frame)
        self.peak = max(self.peak, level)
        self.silent = self.silent + 1 if level < self.threshold * END_LEVEL else 0
        if self.silent * FRAME / RATE >= END_SILENCE or now - self.started > MAX_UTTERANCE:
            out = (self.frames, self.started, now, self.peak)
            self.frames, self.voiced, self.in_speech = [], 0, False
            self.before.clear()
            return out
        return None


def find_external():
    """ALSA name of a clip-mic receiver (e.g. DJI Mic Mini RX), or None."""
    choice = SOURCE_FILE.read_text().strip().lower() if SOURCE_FILE.exists() else "auto"
    if choice == "head":
        return None
    out = subprocess.run(["arecord", "-l"], capture_output=True, text=True).stdout
    for m in re.finditer(r"card (\d+): (\S+) \[([^\]]*)\]", out):
        num, short, long_ = m.groups()
        if "AIUI" in short or "AIUI" in long_:
            continue
        if re.search(EXTERNAL_NAMES, short + " " + long_):
            return f"plughw:CARD={short},DEV=0"
    return None


class Mic(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.utterances = queue.Queue(maxsize=20)
        self.ring = collections.deque(maxlen=int(RING_S * RATE / FRAME))   # (time, (480, 6) int16)
        self.ring_lock = threading.Lock()
        self.head_seg, self.clip_seg = Segmenter(MIN_LEVEL), Segmenter(MIN_LEVEL_CLIP)
        self.external = None                                     # ALSA device of the clip mic, when found
        self.muted_until = 0.0
        self.speaking_now = False
        self.error = None

    # the active detector's state (ears.py reads these)
    @property
    def seg(self):
        return self.clip_seg if self.external else self.head_seg

    @property
    def in_speech(self):
        return self.seg.in_speech

    @property
    def noise(self):
        return self.seg.noise

    @property
    def threshold(self):
        return self.seg.threshold

    # ---------- used by mouth.py ----------
    def speaking(self, on):
        self.speaking_now = on
        if not on:
            self.muted_until = time.time() + AFTER_SPEAKING

    def muted(self):
        return self.speaking_now or time.time() < self.muted_until

    # ---------- used by listeners ----------
    def clear(self):
        while not self.utterances.empty():
            try:
                self.utterances.get_nowait()
            except queue.Empty:
                break

    def next(self, timeout):
        try:
            return self.utterances.get(timeout=timeout)
        except queue.Empty:
            return None

    def _put(self, u):
        try:
            self.utterances.put_nowait(u)
        except queue.Full:                                       # nobody is reading: keep the newest
            try:
                self.utterances.get_nowait()
            except queue.Empty:
                pass
            self.utterances.put_nowait(u)

    def head_audio(self, t_start, t_end):
        """Six-mic audio recorded between two times (from the ring buffer)."""
        with self.ring_lock:
            frames = [x for t, x in self.ring if t_start <= t <= t_end + 0.05]
        return np.concatenate(frames) if frames else np.zeros((0, 6), np.int16)

    # ---------- recording threads ----------
    def run(self):
        threading.Thread(target=self._clip_loop, daemon=True).start()
        while True:
            try:
                self._record_head()
            except Exception as e:
                self.error = repr(e)
            time.sleep(1.0)                                      # arecord ended (device gone?): start again

    def _record_head(self):
        proc = subprocess.Popen(["arecord", "-q", "-D", DEVICE, "-f", "S16_LE", "-r", str(RATE), "-c", str(CHANNELS),
                                 "-t", "raw"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        nbytes = FRAME * CHANNELS * 2
        try:
            while True:
                raw = proc.stdout.read(nbytes)
                if len(raw) < nbytes:
                    return
                x = np.frombuffer(raw, np.int16).reshape(-1, CHANNELS)[:, MICS]
                now = time.time()
                with self.ring_lock:
                    self.ring.append((now, x))
                if self.external:                                # the clip mic cuts the utterances
                    continue
                if self.muted():                                 # Lumi is talking: drop everything
                    self.head_seg.reset()
                    continue
                level = float(np.sqrt(np.mean(x.astype(np.float32).mean(1) ** 2)))
                done = self.head_seg.feed(x, level, now)
                if done:
                    frames, t0, t1, peak = done
                    mics = np.concatenate(frames)
                    self._put(Utterance(mics, mics.astype(np.float32).mean(1).astype(np.int16), t0, t1, peak, "head"))
        finally:
            proc.kill()

    def _clip_loop(self):
        """Look for a clip-mic receiver every few seconds; record from it while it is there."""
        while True:
            dev = find_external()
            if not dev:
                self.external = None
                time.sleep(5.0)
                continue
            self.external = dev
            try:
                self._record_clip(dev)
            except Exception as e:
                self.error = repr(e)
            self.external = None
            time.sleep(2.0)

    def _record_clip(self, dev):
        proc = subprocess.Popen(["arecord", "-q", "-D", dev, "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"],
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        nbytes = FRAME * 2
        talking_since = None                                     # Lumi started talking at (for during_speech)
        try:
            while True:
                raw = proc.stdout.read(nbytes)
                if len(raw) < nbytes:
                    return
                x = np.frombuffer(raw, np.int16)
                now = time.time()
                if self.muted():
                    if not BARGE_IN:
                        self.clip_seg.reset()
                        continue
                    talking_since = talking_since or now
                elif talking_since and not self.clip_seg.in_speech:
                    talking_since = None
                level = float(np.sqrt(np.mean(x.astype(np.float32) ** 2)))
                done = self.clip_seg.feed(x, level, now)
                if done:
                    frames, t0, t1, peak = done
                    during = talking_since is not None and t1 >= talking_since
                    self._put(Utterance(self.head_audio(t0, t1), np.concatenate(frames), t0, t1, peak, "clip", during))
        finally:
            proc.kill()


_mic = None
_lock = threading.Lock()


def get():
    """The shared, running microphone."""
    global _mic
    with _lock:
        if _mic is None:
            _mic = Mic()
            _mic.start()
        return _mic


def speaking(on):
    """mouth.py: Lumi starts / stops talking (no-op if nothing listens in this program)."""
    if _mic is not None:
        _mic.speaking(on)


if __name__ == "__main__":
    from audio import doa
    m = get()
    time.sleep(1.0)
    print(f"listening on {'clip mic ' + m.external if m.external else 'the head array'} ... (Ctrl+C to stop)")
    try:
        while True:
            u = m.next(1.0)
            if u is None:
                continue
            ang = doa.estimate(u.mics) if len(u.mics) else (0.0, 0.0, 0.0)
            print(f"[{u.source}] {u.seconds:4.1f} s  peak {u.peak:5.0f}  noise {m.noise:4.0f}  "
                  f"direction {ang[0]:+5.0f} deg (confidence {ang[1]:.2f})")
    except KeyboardInterrupt:
        pass
