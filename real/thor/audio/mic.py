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
lumi.py can stop talking when the visitor says "stop" / "thanks" or asks something new. Lumi's voice in the clip mic
can keep an utterance from ending, so while Lumi talks its last PEEK_WINDOW_S are also offered every PEEK_S (peek()).

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
EARLY_QUIET_S = 0.3              # s of quiet after which speech-to-text starts on the utterance so far (on_quiet); kept
                                 # when the utterance then ends without new speech (logs/heard 2026-10-22: the 50 real
                                 # clips without their last 0.3 s gave the same commands)
EARLY_MIN_S, EARLY_MAX_S = 0.4, 4.0   # ... for an utterance this long so far: shorter ones are not transcribed, longer
                                 # ones are talk with pauses where each early run delays the last (a 6.8 s clip: 11 s)
on_quiet = None                  # function(int16 mono audio so far), set by audio/ears.py
MAX_UTTERANCE = 8.0              # s (12 s: in a room with music an utterance never got quiet enough
                                 # to end, every one ran the full 12 s, 2026-10-21)
PRE_ROLL = 10                    # frames kept before the start (300 ms)
AFTER_SPEAKING = 0.4             # s still ignored after Lumi stopped talking (room echo)
BARGE_IN = True                  # clip mic: keep listening while Lumi talks (interruptions)
PEEK_S = 0.7                     # clip mic while Lumi talks: every this many s of an utterance still going on ...
PEEK_WINDOW_S = 2.0              # ... its last this many s go to peek() (a stop word: ~0.5 s of whisper on the GPU).
                                 # Lumi's voice in the clip mic kept an utterance going to MAX_UTTERANCE: "Stop. Stop.
                                 # Stop." was heard only when a 17.9 s answer ended (logs/heard/192150.wav, 2026-10-27)
PEEK_MIN_S = 0.5                 # s an utterance needs before its first peek
RING_S = 20.0                    # s of head-array audio kept for the sound direction of clip-mic utterances
DUMP_FLAG = ROOT / "data" / "doa_dump_on"   # while this file exists each clip-mic utterance is saved with its
DUMP_DIR = ROOT / "logs" / "doa_dump"       # head-array audio (npz), to check the sound direction offline
DUMP_MARGIN_S = 1.0              # s of head-array audio saved before and after the clip's times ("wide")


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

    def quiet_now(self):
        """True once per pause inside an utterance, when it has been quiet EARLY_QUIET_S."""
        return self.in_speech and self.silent == round(EARLY_QUIET_S * RATE / FRAME) and \
            EARLY_MIN_S * RATE <= len(self.frames) * FRAME <= EARLY_MAX_S * RATE

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
        self.talking_since = None                                # Lumi started talking at (clip mic, during_speech)
        self.peeked, self.peeked_at = None, 0.0                  # see peek()
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

    def _dump(self, u):
        """Save a clip-mic utterance with the head array's audio of its time and DUMP_MARGIN_S around it."""
        DUMP_DIR.mkdir(parents=True, exist_ok=True)
        wide = self.head_audio(u.t_start - DUMP_MARGIN_S, u.t_end + DUMP_MARGIN_S)
        np.savez(DUMP_DIR / time.strftime("%H%M%S.npz"), mics=u.mics, mono=u.mono, wide=wide,
                 t_start=u.t_start, t_end=u.t_end)

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
                elif on_quiet and self.head_seg.quiet_now():
                    on_quiet(np.concatenate(self.head_seg.frames).astype(np.float32).mean(1).astype(np.int16))
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
        self.talking_since = None
        try:
            while True:
                raw = proc.stdout.read(nbytes)
                if len(raw) < nbytes:
                    return
                self._clip_frame(np.frombuffer(raw, np.int16), time.time())
        finally:
            proc.kill()

    def _clip_frame(self, x, now):
        """One 30 ms clip-mic frame (int16 mono)."""
        if self.muted():
            if not BARGE_IN:
                self.clip_seg.reset()
                return
            self.talking_since = self.talking_since or now      # Lumi started talking at (for during_speech)
        elif self.talking_since and not self.clip_seg.in_speech:
            self.talking_since = None
        level = float(np.sqrt(np.mean(x.astype(np.float32) ** 2)))
        done = self.clip_seg.feed(x, level, now)
        if done:
            frames, t0, t1, peak = done
            during = self.talking_since is not None and t1 >= self.talking_since
            u = Utterance(self.head_audio(t0, t1), np.concatenate(frames), t0, t1, peak, "clip", during)
            if DUMP_FLAG.exists():
                self._dump(u)
            self._put(u)
        elif on_quiet and self.clip_seg.quiet_now():
            on_quiet(np.concatenate(self.clip_seg.frames))
        elif self.speaking_now and self.clip_seg.in_speech and now - self.peeked_at >= PEEK_S and \
                len(self.clip_seg.frames) * FRAME >= PEEK_MIN_S * RATE:
            # Lumi's own voice in the clip mic keeps the utterance from ending: its last seconds are offered now
            mono = np.concatenate(self.clip_seg.frames[-round(PEEK_WINDOW_S * RATE / FRAME):])
            self.peeked = Utterance(np.zeros((0, 6), np.int16), mono, now - len(mono) / RATE, now,
                                    self.clip_seg.peak, "clip", True)
            self.peeked_at = now

    def peek(self):
        """The newest window of a clip-mic utterance still going on while Lumi talks (a mic.Utterance, once), or None:
        lumi.py looks for a stop word in it."""
        u, self.peeked = self.peeked, None
        return u

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
            ang = doa.estimate(u.mics, ref=doa.clip_ref(u)) if len(u.mics) else (0.0, 0.0, 0.0)
            print(f"[{u.source}] {u.seconds:4.1f} s  peak {u.peak:5.0f}  noise {m.noise:4.0f}  "
                  f"direction {ang[0]:+5.0f} deg (confidence {ang[1]:.2f}{doa.clip_note(u.mics, doa.clip_ref(u))})")
    except KeyboardInterrupt:
        pass
