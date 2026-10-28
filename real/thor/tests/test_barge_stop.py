"""Self-check of a stop word said while Lumi talks or sings (live 2026-10-27 19:21, logs/lumi_console.log): Lumi's own
voice in the clip mic kept the utterance going, so "Stop. Stop. Stop." was heard only when the 17.9 s answer ended.
A fake clip-mic stream goes through the real audio/mic.py detector and assistant/lumi.py barge_in() / song_abort();
whisper is faked (it hears "Stop." where the owner's frames are). No audio device, nothing reaches the robot:
python tests/test_barge_stop.py"""
import time

import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import lumi
from audio import ears, mic, mouth
from tasks import follow

LUMI, OWNER = 2000, 3001                            # sample values: Lumi's voice from the speaker, the owner's word
STOP_AT, REACT_S, WHISPER_S = 3.0, 1.5, 0.5         # owner's "stop" s into the answer; allowed; one transcription
acts = []
follow.running = lambda: False
mouth.own_voice = lambda u: False                   # the sound match is checked in tests/test_mouth.py
lumi.mouth.recent_speech = lambda s: ""


def fake_whisper(owner_said, lumi_said):
    def quick(audio):
        text = owner_said if (np.abs(audio) == OWNER).any() else lumi_said
        ears.last_stt.clear()
        ears.last_stt.update(text=text, language="korean" if "그" in text else "english", logprob=-0.1)
        return text
    ears.quick = quick


def fresh(saying):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.markers, L.pending_text, L.mic = ["home", "charge", "dock2"], None, mic.Mic()
    L.act = lambda a, t: acts.append(a)
    L.song_request = ("sing a song", time.time())
    mouth._recent[:] = [(time.time(), saying)]
    acts.clear()
    return L


def stream(L, abort, owner=True, seconds=7.5):
    """Quiet, then Lumi talks (loud the whole time, the utterance goes on to mic.MAX_UTTERANCE) with the owner's word at STOP_AT.
    Returns s from the word to the abort (whisper's time added), or None when nothing stopped Lumi."""
    m, t0 = L.mic, 1000.0
    frame = np.full(mic.FRAME, LUMI, np.int16)
    frame[::2] *= -1
    for i in range(100):                            # 3 s of room noise: the detector learns the floor
        m._clip_frame(np.zeros(mic.FRAME, np.int16) + 50, t0 + i * 0.03)
    m.speaking(True)
    for i in range(int(seconds / 0.03)):
        t = i * 0.03
        x = frame.copy()
        if owner and STOP_AT <= t < STOP_AT + 0.4:
            x[x > 0], x[x < 0] = OWNER, -OWNER
        m._clip_frame(x, t0 + 3.0 + t)
        assert m.utterances.empty(), "Lumi's voice must keep the utterance going (the live case)"
        if abort():
            return t - STOP_AT + WHISPER_S
    return None


# the live case: a long answer, "stop" in the middle -> stopped within REACT_S, the stop handled as before
fake_whisper("Stop. Stop.", "I know home, charge, dock2.")
L = fresh("I don't have a place called that on this map. I know: home, charge, dock2.")
took = stream(L, L.barge_in)
assert took is not None and 0 < took <= REACT_S, took
assert acts == ["stop"] and L.pending_text == "Stop. Stop.", (acts, L.pending_text)

# Lumi's own answer says "stop" and the clip mic hears it: no stop
fake_whisper("", "Stop.")
L = fresh("Press the red button to stop.")
assert stream(L, L.barge_in, owner=False) is None and not acts, acts

# ... but the owner's "stop" during that answer, heard with other words, still stops
fake_whisper("Lumi, stop now.", "Stop.")
L = fresh("Press the red button to stop.")
assert stream(L, L.barge_in) is not None and acts == ["stop"], acts

# Lumi's own words without a stop word: nothing
fake_whisper("", "I know home, charge, dock2.")
L = fresh("I know home, charge, dock2.")
assert stream(L, L.barge_in, owner=False) is None and not acts, acts

# a song, "그만" -> the song ends at once (no act: song_abort only ends the song, as before)
fake_whisper("그만.", "La la la, the sun is up.")
L = fresh("La la la, the sun is up.")
took = stream(L, L.song_abort)
assert took is not None and 0 < took <= REACT_S and not acts, (took, acts)

# a song, only the music: goes on
L = fresh("La la la, the sun is up.")
assert stream(L, L.song_abort, owner=False) is None

print("barge stop ok")
