"""Self-check of singing (audio/sing.py and its wiring in assistant/lumi.py): which words ask for a song, which song
is chosen, head targets inside the limits, stop at once, switch to another song, the head back where it was.
No robot, no speaker: the head, the player and the microphone are fakes. python tests/test_songs.py"""
import threading
import time
import types

import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from audio import sing
from assistant import lumi

SONGS = sing.songs()
if not SONGS:                                        # the owner's songs are only on the robot
    print("songs: none here (data/songs/mine is local to the robot), skipped")
    raise SystemExit
B, F, D, L_ = "ATEEZ_BAD", "BIGBANG_FANTASTIC_BABY", "MEOMUREU_DREAMED_ADULT", "RESCENE_LOVE_ATTACK"
assert set(SONGS) == {B, F, D, L_}, SONGS.keys()     # Lumi sings only the owner's songs

ASKED = {"sing a song": True, "Lumi, sing me a song please": True, "sing Fantastic Baby": True, "sing Yesterday": True,
         "can you sing a song?": True, "sing another song": True, "노래 불러 줘": True, "노래 한 곡 해 줘": True,
         "러브 어택 불러 줘": True, "판타스틱 베이비 불러 줄래?": True, "다른 노래": True, "노래해 줘": True,
         "play some music": True, "sing a Korean song": True, "Let it go 불러 줘": True,
         "can you sing?": True, "노래 할 수 있어요?": True, "sing song": True, "sing music": True, "play music": True,
         "Can you sing song?": True, "let's say song": True, "노래해": True, "음악 틀어 줘": True, "노래 하나 해 줘": True,
         "노래 하나 불러 줘": True, "아무 노래나 불러 줘": True, "put on some music": True, "다음 곡": True,
         "노래 듣고 싶어": True, "루미야 sing a song 해 줘": True, "play a song": True,
         "do you like singing?": False, "what's your favourite song?": False, "what music do you like?": False,
         "좋아하는 노래 있어요?": False, "노래 잘해?": False, "사람 좀 불러 줘": False, "택시 불러 줘": False, "go to p3": False,
         "happy birthday, Lumi": False, "stop": False, "I like this music": False, "노래방 가자": False,
         "누가 이 노래 불렀어?": False, "what songs can you sing?": False, "another one": False, "그거 말고": False,
         "can I sing?": False, "내가 노래 불러도 돼?": False, "sing later when the guests come": False,
         "손님 오면 그때 노래해 줘": False, "I can't sing at all": False}
wrong = {t: w for t, w in ASKED.items() if sing.asked(t) != w}
assert not wrong, wrong
ASKED2 = {"노래 싱 해 줘": True, "송 하나 불러 줘": True, "노래하나불러줘요": True, "노래 한 자락 해 줘": True, "배드 불러 주라": True,
          "Love Attack 부르시게": True, "I'd love to hear Love Attack": True, "에이티즈 거 한 곡": True, "give us a song": True,
          "제가 노래해도 돼요?": False, "노래 불러도 돼요?": False, "I feel bad, please": False, "택시 좀 불러 주세요": False,
          "my daughter loves love attack": False}
wrong = {t: w for t, w in ASKED2.items() if sing.asked(t) != w}
assert not wrong, wrong
assert sing.asked("웅 불러 줘~", "한 곡 불러 드릴까요?") and sing.asked("앵콜!", "ACTION: sing " + F) and sing.list_asked("송 리스트 알려 줘")
for t in ["죄송한데요, 노래 하나 불러 주시겠어요?", "실례지만다른노래불러주시길부탁드립니다", "보소, 에이티즈 노래 쪼까 불러 줘", "sing anothre song",
          "you sing song pleaase", "다른 노래 퍼뜩 불러 주이소"]:
    assert sing.choose(t) in SONGS, t                # openers, dialect, slips and words written together are no title
assert sing.choose("트로트한곡불러줘") is None and sing.choose("죄송하지만 아리랑 불러 주세요") is None
assert sing.choose("루미야 자 다음은 꿈꾸던 어른이 되었나요 불러 줘") == D

CHOSEN = {"sing Fantastic Baby": F, "판타스틱 베이비 불러 줘": F, "sing a BIGBANG song": F, "sing something by Big Bang": F,
          "러브어택 틀어 줘": L_, "리센느 노래 해 줘": L_, "sing a teez song": B, "sing BAD by ATEEZ": B,
          "꿈꾸던 어른이 되었나요 불러 줘": D, "sing Did I Become the Adult I Dreamed Of": D,
          "sing yesterday": None, "sing dynamite by BTS": None, "애국가 불러 줘": None, "아리랑 불러 줘": None,
          "sing happy birthday": None, "생일 축하 노래 불러 줘": None, "sing Bad Guy by Billie Eilish": None,
          "sing ATEEZ Wonderland": None, "빅뱅 거짓말 불러 줘": None, "sing Bang Bang Bang by BIGBANG": None,
          "아이유 노래 불러 줘": None, "BTS 노래 sing 해 줘": None, "sing a Christmas song": None, "sing a lullaby": None,
          "Let it go 불러 줄래?": None, "sing an English song": None, "트로트 한 곡 불러 줘": None,
          "I feel bad, sing Love Attack": L_}           # "bad" is a song name only as a whole word
for text, want in CHOSEN.items():
    assert sing.choose(text, "ko" if any('가' <= ch <= '힣' for ch in text) else "en") == want, (text, sing.choose(text, "en"), want)
for _ in range(30):                                  # unnamed: one of ours, not the last
    for t in ["노래 불러 줘", "sing a song", "신나는 노래 불러 줘", "sing something fun", "sing pls", "우리 아이한테 노래 불러 줄래요?",
              "sing for everyone", "뭐든 좋으니까 노래 해 줘", "sing a Korean song"]:
        assert sing.choose(t, "en") in SONGS, t
    assert sing.choose("sing another song", "en", last=F) != F
    assert sing.choose("다른 노래", "ko", last=L_) != L_
    assert sing.choose("sing it again", "en", last=D) == D
    assert sing.choose("한 번 더 불러 줘", "ko", last=L_) == L_
LISTED = ["what songs can you sing?", "which songs do you know?", "what songs do you know", "무슨 노래 알아?",
          "어떤 노래 부를 수 있어?", "아는 노래 뭐 있어?", "노래 목록 알려 줘", "what can you sing?"]
assert all(sing.list_asked(t) and not sing.asked(t) for t in LISTED), [t for t in LISTED if not sing.list_asked(t)]
assert not any(sing.list_asked(t) for t in ["sing a song", "어떤 노래든 불러 줘", "what's your favourite song?", "go to p3"])
assert all(SONGS[sid]["title"] in sing.list_reply("en") for sid in SONGS) and "어떤 노래" in sing.list_reply("ko")
assert all(SONGS[sid]["title_ko"] in sing.list_reply("ko") for sid in SONGS)
AFTER = f"ACTION: sing {L_}"                         # right after a song: a short word switches or repeats it
for t in ["another one", "next", "next one", "a different one", "something else", "not this one", "다른 거",
          "다음 거", "그거 말고", "딴 거", "one more"]:
    assert sing.asked(t, AFTER) and not sing.asked(t), t
    assert all(sing.choose(t, "en", L_) not in (None, L_) for _ in range(10)), t
assert sing.asked("그 노래 말고 다른 거 불러 줘") and sing.choose("그 노래 말고 다른 거 불러 줘", "ko", L_) != L_
for t in ["again", "한 번 더", "다시"]:
    assert sing.asked(t, AFTER) and sing.choose(t, "en", L_) == L_, t
for t in ["that was bad", "go to p3", "thank you", "what time is it"]:
    assert not sing.asked(t, AFTER), t
assert sing.asked("Love Attack", "ACTION: none songs\n...") and sing.asked("판타스틱 베이비", "ACTION: none songs\n...")
assert not sing.asked("Love Attack") and not sing.asked("go to p3", "ACTION: none songs\n...")
for _ in range(20):                                  # a song we don't have: said kindly, ours offered
    en, ko = sing.unknown_reply("en"), sing.unknown_reply("ko")
    assert all(SONGS[sid]["title"] in en and SONGS[sid]["title_ko"] in ko for sid in SONGS), (en, ko)
    assert "{" not in en + ko and "네 곡" in ko or "이렇게" not in ko, ko
assert len({sing.unknown_reply("en") for _ in range(40)}) > 2   # not the same words every time
# the song bank never reads a cut-off start or words without a song word (no embedding needed: refused first)
for t in ["Let's", "can you", "please", "루미야 저기", "let's go", "Lumi, can you", "follow me", "what time is it"]:
    assert sing.bank_read(t) is None, t
from assistant import brain                          # a reply promising a move the action line did not: asked
for t, want in [("Okay, I'll follow you!", "motion"), ("네, 따라갈게요!", "motion"), ("I'm coming!", "motion"),
                ("Okay! I'll sing a song for you.", "sing"), ("I'll wave!", "wave"), ("I'll look into it.", None),
                ("I'll give you an example.", None), ("알려 드릴게요.", None), ("I can follow you if you like.", None)]:
    assert brain.promised(t) == want, (t, brain.promised(t))
assert all(sing.stop_words(t) for t in ["stop", "Lumi stop", "멈춰", "그만", "그만해", "enough", "스톱"])
assert not any(sing.stop_words(t) for t in ["sing another song", "다른 노래", "what time is it"])

for sid, song in SONGS.items():                      # head moves like a singer's, inside the owner's limits
    beat_times = np.array([b[0] for b in sing.song_beats(song)])
    for seed in range(5):
        targets = sing.head_targets(song, seed=seed)
        assert len(targets) >= 8, sid
        assert all(abs(y) <= sing.YAW_SWAY and sing.PITCH_RANGE[0] <= p <= sing.PITCH_RANGE[1] for _, y, p, _ in targets), (sid, targets)
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
assert sing.sing(B, None, player(2.5), head, fake_load)        # finished
sing._head_thread.join(2)
assert len(head.moves) >= 3, head.moves                                  # to 0 / 0, moved with the song ...
assert head.moves[0] == [120.0, 5.0, 0.0, 0.0], head.moves[0]
assert head.moves[-1] == [120.0, 5.0, 0.0, 0.0], head.moves[-1]           # ... and back to 0 / 0
assert all(abs(m[2]) <= sing.YAW_SWAY and sing.PITCH_RANGE[0] <= m[3] <= sing.PITCH_RANGE[1] for m in head.moves), head.moves

head = FakeHead()
t0 = time.time()
stop_at = t0 + 0.3
assert not sing.sing(F, lambda: time.time() > stop_at, player(30), head, fake_load)   # stopped
assert time.time() - stop_at < 0.1, time.time() - stop_at                # at once
sing._head_thread.join(2)
assert head.moves and head.moves[-1] == [120.0, 5.0, 0.0, 0.0], head.moves

for centre in (-40.0, 55.0, -90.0):                  # the owner on a side: the dance around them, inside the limits
    head = FakeHead()
    assert sing.sing(B, None, player(2.5), head, fake_load, centre_yaw=centre)
    sing._head_thread.join(2)
    c = max(-sing.YAW_LIMIT, min(sing.YAW_LIMIT, centre))
    assert head.moves[0][2] == c and head.moves[-1][2] == c, (centre, head.moves)   # turns there and stays there
    assert all(abs(m[2] - c) <= sing.YAW_SWAY and abs(m[2]) <= sing.YAW_LIMIT for m in head.moves), (centre, head.moves)
    assert c == -sing.YAW_LIMIT or len({m[2] for m in head.moves}) > 2, head.moves   # still dances (at the limit: one side)
assert all(abs(sing.around(c, y)) <= sing.YAW_LIMIT for c in range(-90, 91, 5) for y in range(-40, 41, 2))
assert sing.around(0.0, 33.0) == 33.0                # the default: as before

played = []                                          # a stereo file reaches the one-channel speaker as mono
assert sing.sing(D, None, lambda wav, rate, abort: played.append(wav.ndim) or True, FakeHead(),
                 lambda path: (np.zeros((4410, 2), np.float32), 44100))
assert played == [1], played
sing._head_thread.join(2)

# lumi.py: "stop" while singing ends the song; "sing another song" ends it and sings a different one
real_sing = sing.sing
heard = []                                           # what the fake clip mic hears, one utterance per poll
sung = []


centres = []


def fake_sing(sid, abort=None, centre_yaw=0.0):
    sung.append(sid)
    centres.append(centre_yaw)
    return real_sing(sid, abort, player(5), FakeHead(), fake_load, centre_yaw)


lumi.sing.sing = fake_sing
lumi.LOG_FILE = "/dev/null"                      # keep the assistant's log clean
lumi.ears.transcribe = lambda mono: heard.pop(0) if heard else ""
lumi.ears.understood = lambda *a: True
L = lumi.Lumi.__new__(lumi.Lumi)
L.markers = ["home", "p1"]                           # never the base's marker list
L.lang, L.current, L.vision, L.last_song, L.pending_text, L.voice_until = "en", None, None, None, None, 0.0
L.skill_thread, L.mission_hold = None, None
L.brain = types.SimpleNamespace(history=[])
L.fetch_status = lambda: None
L.mission_running = lambda: False
L.det_yaw = lambda: -40.0                            # nobody tracked: the head already faces the voice
utterance = types.SimpleNamespace(during_speech=True, seconds=1.0, mono=None)
L.mic = types.SimpleNamespace(next=lambda wait: utterance if heard else None)

t0 = time.time()
threading.Timer(0.3, lambda: heard.append("stop")).start()
L.sing_song("sing Love Attack")
assert sung == [L_] and time.time() - t0 < 1.0 and L.pending_text is None, (sung, time.time() - t0)
assert centres == [-40.0], centres                   # the dance stays toward the listener

threading.Timer(0.3, lambda: heard.append("sing another song")).start()
L.sing_song("sing a song")
assert L.pending_text == "sing another song", L.pending_text
first, L.pending_text = sung[-1], None
threading.Timer(0.3, lambda: heard.append("멈춰")).start()
L.sing_song("sing another song")
assert sung[-1] != first and L.pending_text is None, sung

threading.Timer(0.3, lambda: heard.append("thank you")).start()   # whisper's guess on music: ignored
L.interrupted = lambda: True        # the dancing head lost the listener ("person left"): the song goes on (2026-10-23)
t0 = time.time()
L.sing_song("sing Fantastic Baby")
assert time.time() - t0 > 4.5 and L.pending_text is None

# words over a song that are no new request leave it going (logs/lumi.log 2026-10-27, logs/heard): whisper's words
# from the music (0.26 s of speech for "Last hole."), a single word, the request said again while it starts
lumi.ears.last_stt = {"speech_s": 0.26}
threading.Timer(0.3, lambda: heard.append("Last hole.")).start()
t0 = time.time()
L.sing_song("Let's make music.")
assert time.time() - t0 > 4.5 and L.pending_text is None
lumi.ears.last_stt = {}
ign = sing.ignored_over_song
assert ign("Last hole.", "Let's make music.", 3.0, 0.26) and ign("Let's make music.", "Let's make music.", 2.0, 0.99)
assert ign("Okay.", "sing a song", 3.0, 0.5) and ign("Lumi.", "sing a song", 3.0, None)
assert ign("sing a song", "Let's make music.", 40.0, 1.0) and ign("노래 불러 줘", "sing a song", 40.0, 1.0)
assert ign("Let's make music.", "Let's make music.", 40.0, 0.99) is None             # long after: asked for real
for words, speech in (("Let's change music.", 1.28), ("Let's change the music.", 1.2), ("another song", 0.6),
                      ("다른 노래", 0.6), ("바꿔", 0.3), ("sing Fantastic Baby", 0.9), ("What time is it?", 0.9),
                      ("Lumi, go to p3", 0.8), ("Let's make music.", None)):
    assert ign(words, "Let's make music.", 2.0 if words != "Let's make music." else 30.0, speech) is None, words

# lumi.answer(): "again" right after a song is the song (not the drive words), "Can you sing song?" tagged Korean
# by whisper is still sung, "what songs can you sing?" lists them
said = []
lumi.mouth.say = lambda text, lang=None, abort=None: said.append(text)
lumi.ears.last_stt = {"language": "english", "logprob": -0.1}
L.closing_pending = None
L.follow_stop = lambda text: False
L.keep_listening = lambda: None
L.speak_abort = lambda: False
L.drive_words = lambda text: (_ for _ in ()).throw(AssertionError(f"drive words got {text!r}"))
L.skill_busy = lambda: False
L.sing_song = lambda text: sung.append(("sing", text))
L.brain.history = [("sing Love Attack", f"ACTION: sing {L_}")]
L.answer("again")
assert sung[-1] == ("sing", "again"), sung
L.answer("그거 말고")
assert sung[-1] == ("sing", "그거 말고"), sung
L.brain.history = []
L.answer("what songs can you sing?")
assert "Which one would you like?" in said[-1] and L.brain.history[-1][1].startswith("ACTION: none songs"), said
# live 2026-10-23: after the list a title or a place in it starts that song, never an LLM "Okay, I'll play it"
for words in ("Let's put the first one.", "Fantastic Baby.", "아무거나", "두 번째 거 불러 줘", "the last one"):
    L.answer(words)
    assert sung[-1] == ("sing", words), (words, sung)
    L.brain.history = L.brain.history[:-1] + [("what songs can you sing?", "ACTION: none songs\n" + said[-1])]
listed = "ACTION: none songs\nI can sing ..."
assert sing.picked("Let's put the first one.", listed) == B and sing.picked("Fantastic Baby.", listed) == F
assert sing.picked("두 번째 거", listed) == F and sing.picked("세 번째", listed) == D and sing.picked("the last one", listed) == L_
assert sing.picked("마지막 거", listed) == L_ and sing.picked("판타스틱", listed) == F and sing.picked("아무거나", listed) in SONGS
assert sing.picked("first one", "ACTION: none -\nOkay.") is None and sing.picked("go to p3", listed) is None
assert sing.picked("don't sing the first one", listed) is None
assert sing.asked("Let's change music.") and sing.choose("Let's change music.", last=B) not in (None, B)   # not "not ours"
assert sing.asked("노래 바꿔 줘") and sing.choose("노래 바꿔 줘", last=B) not in (None, B)
assert lumi.brain_mod.promised("Okay, I'll play it.") == "sing" and lumi.brain_mod.promised("판타스틱 베이비 틀어 드릴게요.") == "sing"
assert lumi.mouth.sentences("我会唱歌。 Okay! 好的") == ["Okay!"] and lumi.mouth.sentences("你好") == []
lumi.ears.understood = lambda *a: False              # English words tagged 'korean' (logs/lumi.log 2026-10-21 11:30)
lumi.ears.heard_clearly = lambda *a: True
lumi.ears.last_stt = {"language": "korean", "logprob": -0.08}
passed = []                                          # past the "say it again" gate, in English; stop there
L.drive_words = lambda text: passed.append(text) or True
L.answer("Can you sing song?")
assert L.lang == "en" and passed == ["Can you sing song?"] and not said[-1].startswith("죄송"), (L.lang, passed, said)
L.answer("I'll see you next time.")                  # whisper's English for noise: still asked again
assert passed == ["Can you sing song?"] and said[-1].startswith("죄송"), said
assert lumi.own_command("Can you sing song?") and not lumi.own_command("I'll see you next time.")
lumi.sing.sing = real_sing
print("songs ok")
