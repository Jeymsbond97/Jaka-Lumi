"""Always-on microphone: one recording of the head mic array, cut into utterances.

The AIUI-USB-MC array gives 8 channels at 16 kHz: channels 0-5 are the six mics of the ring, 6-7 are silent.
A background thread reads it continuously (an ALSA device can be opened only once, so everything that
listens goes through here) and cuts the sound into utterances with an energy detector:
speech starts when the level stays above START_FACTOR x the background noise for START_FRAMES frames and
ends after END_SILENCE of quiet. Each utterance keeps all six mic channels (for the sound direction, doa.py)
and a mono mix (for speech-to-text).

While Lumi itself speaks (mouth.py calls speaking()), nothing is recorded: the speaker is ~25x louder than a
voice in the mics.

    python mic.py        # print every utterance: length, level and (if calibrated) the direction
"""
import collections
import queue
import subprocess
import threading
import time

import numpy as np

DEVICE = "hw:CARD=AIUIUSBMC"
RATE, CHANNELS, MICS = 16000, 8, slice(0, 6)
FRAME = 480                      # 30 ms
START_FACTOR = 2.5               # speech = louder than START_FACTOR x background noise
MIN_LEVEL = 400                  # ... and at least this RMS
START_FRAMES = 4                 # 120 ms of speech to start
END_SILENCE = 0.7                # s of quiet that ends an utterance
MAX_UTTERANCE = 12.0             # s
PRE_ROLL = 10                    # frames kept before the start (300 ms)
AFTER_SPEAKING = 0.4             # s still ignored after Lumi stopped talking (room echo)


class Utterance:
    def __init__(self, frames, t_start, t_end, peak):
        self.mics = np.concatenate(frames)                       # int16, (n, 6)
        self.mono = self.mics.astype(np.float32).mean(1).astype(np.int16)
        self.t_start, self.t_end, self.peak = t_start, t_end, peak

    @property
    def seconds(self):
        return len(self.mono) / RATE


class Mic(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.utterances = queue.Queue(maxsize=20)
        self.levels = collections.deque(maxlen=300)              # last 9 s of frame levels, for the noise floor
        self.in_speech = False
        self.speech_started = 0.0
        self.muted_until = 0.0
        self.speaking_now = False
        self.noise = self.threshold = 0.0
        self.error = None

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

    # ---------- the recording thread ----------
    def run(self):
        while True:
            try:
                self._record()
            except Exception as e:
                self.error = repr(e)
            time.sleep(1.0)                                      # arecord ended (device gone?): start again

    def _record(self):
        proc = subprocess.Popen(["arecord", "-q", "-D", DEVICE, "-f", "S16_LE", "-r", str(RATE), "-c", str(CHANNELS),
                                 "-t", "raw"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        nbytes = FRAME * CHANNELS * 2
        before = collections.deque(maxlen=PRE_ROLL)
        frames, voiced, silent, peak = [], 0, 0, 0.0
        try:
            while True:
                raw = proc.stdout.read(nbytes)
                if len(raw) < nbytes:
                    return
                x = np.frombuffer(raw, np.int16).reshape(-1, CHANNELS)[:, MICS]
                level = float(np.sqrt(np.mean(x.astype(np.float32).mean(1) ** 2)))
                now = time.time()
                if self.muted():                                 # Lumi is talking: drop everything
                    before.clear()
                    frames, voiced, self.in_speech = [], 0, False
                    continue
                if not self.in_speech:
                    self.levels.append(level)
                    self.noise = float(np.percentile(self.levels, 30))
                    self.threshold = max(MIN_LEVEL, START_FACTOR * self.noise)
                    before.append(x)
                    voiced = voiced + 1 if level > self.threshold else 0
                    if voiced >= START_FRAMES:
                        self.in_speech, self.speech_started = True, now
                        frames, silent, peak = list(before), 0, level
                    continue
                frames.append(x)
                peak = max(peak, level)
                silent = silent + 1 if level < self.threshold * 0.7 else 0
                if silent * FRAME / RATE >= END_SILENCE or now - self.speech_started > MAX_UTTERANCE:
                    self.in_speech = False
                    u = Utterance(frames, self.speech_started, now, peak)
                    frames, voiced = [], 0
                    before.clear()
                    try:
                        self.utterances.put_nowait(u)
                    except queue.Full:                           # nobody is reading: keep the newest
                        try:
                            self.utterances.get_nowait()
                        except queue.Empty:
                            pass
                        self.utterances.put_nowait(u)
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
    import doa
    m = get()
    print("listening... (Ctrl+C to stop)")
    try:
        while True:
            u = m.next(1.0)
            if u is None:
                continue
            ang = doa.estimate(u.mics)
            print(f"{u.seconds:4.1f} s  peak {u.peak:5.0f}  noise {m.noise:4.0f}  "
                  f"direction {ang[0]:+5.0f} deg (confidence {ang[1]:.2f}, raw {ang[2]:+.0f})")
    except KeyboardInterrupt:
        pass
