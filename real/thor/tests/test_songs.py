"""Self-check of singing (audio/sing.py and its wiring in assistant/lumi.py): which words ask for a song, which song
is chosen, head targets inside the limits, stop at once, switch to another song, the head back where it was.
No robot, no speaker: the head, the player and the microphone are fakes. python tests/test_songs.py"""
import threading
import time
import types

import numpy as np

from audio import sing
from assistant import lumi

SONGS = sing.songs()
assert {"happy_birthday", "twinkle", "row_row", "arirang", "three_bears"} <= set(SONGS), SONGS.keys()

ASKED = {"sing a song": True, "Lumi, sing me a song please": True, "sing Arirang": True, "sing happy birthday": True,
         "can you sing a song?": True, "sing another song": True, "노래 불러 줘": True, "노래 한 곡 해 줘": True,
         "아리랑 불러 줘": True, "곰 세 마리 불러 줄래?": True, "다른 노래": True, "노래해 줘": True,
         "play some music": True, "sing a Korean song": True,
         "can you sing?": False, "do you like singing?": False, "what's your favourite song?": False,
         "좋아하는 노래 있어요?": False, "노래 할 수 있어요?": False, "사람 좀 불러 줘": False, "go to p3": False,
         "happy birthday, Lumi": False, "stop": False}
wrong = {t: w for t, w in ASKED.items() if sing.asked(t) != w}
assert not wrong, wrong

CHOSEN = {("sing Arirang", "en"): "arirang", ("아리랑 불러 줘", "ko"): "arirang", ("sing happy birthday", "en"): "happy_birthday",
          ("생일 축하 노래 불러 줘", "ko"): "happy_birthday", ("곰 세 마리 불러 줘", "ko"): "three_bears",
          ("sing twinkle twinkle little star", "en"): "twinkle", ("sing row row row your boat", "en"): "row_row",
          ("sing yesterday", "en"): None, ("sing dynamite by BTS", "en"): None, ("애국가 불러 줘", "ko"): None}
for (text, lang), want in CHOSEN.items():
    assert sing.choose(text, lang) == want, (text, sing.choose(text, lang), want)
for _ in range(30):                                  # unnamed: a song in the language asked for / spoken, not the last
    assert sing.choose("노래 불러 줘", "ko") in SONGS and sing.choose("sing a song", "en") in SONGS
    assert SONGS[sing.choose("sing a Korean song", "en")]["lang"] == "ko"
    assert sing.choose("sing another song", "en", last="twinkle") != "twinkle"
    assert sing.choose("다른 노래", "ko", last="arirang") != "arirang"
    assert SONGS[sing.choose("sing an English song", "ko")]["lang"] == "en"
    assert sing.choose("sing for everyone", "en") is not None
    assert sing.choose("sing it again", "en", last="row_row") == "row_row"
    assert sing.choose("한 번 더 불러 줘", "ko", last="arirang") == "arirang"
assert "Arirang" in sing.unknown_reply("en") and "Twinkle" in sing.unknown_reply("en")
assert "아리랑" in sing.unknown_reply("ko")
assert all(sing.stop_words(t) for t in ["stop", "Lumi stop", "멈춰", "그만", "그만해", "enough", "스톱"])
assert not any(sing.stop_words(t) for t in ["sing another song", "다른 노래", "what time is it"])

for sid, song in SONGS.items():                      # head moves like a singer's, inside the owner's limits
    beat_times = np.array([b[0] for b in sing.song_beats(song)])
    for seed in range(5):
        targets = sing.head_targets(song, seed=seed)
        assert len(targets) >= 8, sid
        assert all(abs(y) <= 25 and 0 <= p <= 15 for _, y, p, _ in targets), (sid, targets)
        assert all(50 <= v <= 100 for *_, v in targets), sid
        assert sum(v >= 70 for *_, v in targets) >= 0.5 * len(targets), sid             # lively, slow only when calm
        moves = [(targets[0][1], targets[0][2])] + [(b[1] - a[1], b[2] - a[2]) for a, b in zip(targets, targets[1:])]
        for k in range(len(targets)):
            dy, dp = moves[k]
            lands = targets[k][0] + sing.reach_time(dy, dp, targets[k][3])
            assert np.abs(beat_times - lands).min() < 0.01, (sid, k)                   # lands on a beat
            if k + 1 < len(targets):                                                   # never two calls at once
                assert targets[k + 1][0] >= targets[k][0] + sing.move_time(dy, dp, targets[k][3]), (sid, k)
        assert max(abs(dy) for dy, _ in moves) >= 15, sid                                # accents: big sweeps
        assert all(abs(dy) >= 1.4 and abs(dp) >= 0.7 for dy, dp in moves[1:]), sid      # both axes, every move
        turns = [sing._turn(a, b) for a, b in zip(moves[1:], moves[2:])]
        assert all(15 <= t <= 165 for t in turns), (sid, min(turns), max(turns))     # never on the last move's line
        ys = [round(y) for _, y, _, _ in targets]
        assert len(set(zip(ys, ys[1:], ys[2:]))) > 0.8 * (len(ys) - 2), sid          # does not loop the same way
    assert song["wav"].exists(), sid
assert sing.choose("I feel bad, sing twinkle", "en") == "twinkle"     # "bad" is a song name only as a whole word
if "BIGBANG_FANTASTIC_BABY" in SONGS:                # the owner's songs are only on the robot
    assert sing.choose("sing fantastic baby", "en") == "BIGBANG_FANTASTIC_BABY"
    assert sing.choose("판타스틱 베이비 불러 줘", "ko") == "BIGBANG_FANTASTIC_BABY"
    assert sing.asked("판타스틱 베이비 불러 줘")


class FakeHead:
    YAW_LIMIT = 60.0

    def __init__(self):
        self.moves = []

    def status(self):
        return [120.0, 5.0, 20.0, 3.0]

    def moveto(self, pos, vel=None, acc=None):
        assert pos[:2] == [120.0, 5.0], pos         # never the lift or the waist
        assert not getattr(self, "busy", False)     # never a second call while one runs
        self.busy = True
        self.moves.append(pos)
        time.sleep(0.05)
        self.busy = False


def fake_load(path):
    return np.zeros(4410, np.float32), 44100


def player(seconds):
    """A speaker that 'plays' for seconds and stops within 10 ms of abort(), like mouth._play."""
    def play(wav, rate, abort):
        t = time.time()
        while time.time() - t < seconds:
            if abort and abort():
                return False
            time.sleep(0.01)
        return True
    return play


head = FakeHead()
assert sing.sing("row_row", None, player(2.5), head, fake_load)        # finished
sing._head_thread.join(2)
assert len(head.moves) >= 3, head.moves                                  # to 0 / 0, moved with the song ...
assert head.moves[0] == [120.0, 5.0, 0.0, 0.0], head.moves[0]
assert head.moves[-1] == [120.0, 5.0, 0.0, 0.0], head.moves[-1]           # ... and back to 0 / 0
assert all(abs(m[2]) <= 25 and 0 <= m[3] <= 15 for m in head.moves), head.moves

head = FakeHead()
t0 = time.time()
stop_at = t0 + 0.3
assert not sing.sing("arirang", lambda: time.time() > stop_at, player(30), head, fake_load)   # stopped
assert time.time() - stop_at < 0.1, time.time() - stop_at                # at once
sing._head_thread.join(2)
assert head.moves and head.moves[-1] == [120.0, 5.0, 0.0, 0.0], head.moves

played = []                                          # a stereo file reaches the one-channel speaker as mono
assert sing.sing("twinkle", None, lambda wav, rate, abort: played.append(wav.ndim) or True, FakeHead(),
                 lambda path: (np.zeros((4410, 2), np.float32), 44100))
assert played == [1], played
sing._head_thread.join(2)

# lumi.py: "stop" while singing ends the song; "sing another song" ends it and sings a different one
real_sing = sing.sing
heard = []                                           # what the fake clip mic hears, one utterance per poll
sung = []


def fake_sing(sid, abort=None):
    sung.append(sid)
    return real_sing(sid, abort, player(5), FakeHead(), fake_load)


lumi.sing.sing = fake_sing
lumi.LOG_FILE = "/dev/null"                      # keep the assistant's log clean
lumi.ears.transcribe = lambda mono: heard.pop(0) if heard else ""
lumi.ears.understood = lambda *a: True
L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.current, L.vision, L.last_song, L.pending_text, L.voice_until = "en", None, None, None, None, 0.0
L.skill_thread, L.mission_hold = None, None
L.brain = types.SimpleNamespace(history=[])
L.fetch_status = lambda: None
L.mission_running = lambda: False
utterance = types.SimpleNamespace(during_speech=True, seconds=1.0, mono=None)
L.mic = types.SimpleNamespace(next=lambda wait: utterance if heard else None)

t0 = time.time()
threading.Timer(0.3, lambda: heard.append("stop")).start()
L.sing_song("sing Arirang")
assert sung == ["arirang"] and time.time() - t0 < 1.0 and L.pending_text is None, (sung, time.time() - t0)

threading.Timer(0.3, lambda: heard.append("sing another song")).start()
L.sing_song("sing a song")
assert L.pending_text == "sing another song", L.pending_text
first, L.pending_text = sung[-1], None
threading.Timer(0.3, lambda: heard.append("멈춰")).start()
L.sing_song("sing another song")
assert sung[-1] != first and L.pending_text is None, sung

threading.Timer(0.3, lambda: heard.append("thank you")).start()   # whisper's guess on music: ignored
t0 = time.time()
L.sing_song("sing twinkle twinkle")
assert time.time() - t0 > 4.5 and L.pending_text is None
lumi.sing.sing = real_sing
print("songs ok")
