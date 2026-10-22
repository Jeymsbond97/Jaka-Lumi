"""Self-check of the speaking volume and speed by voice (assistant/voice_words.py and lumi.answer()'s routing to it):
EN / KO / mixed, the drive speed kept apart, "again" right after, the limits. No speaker: the mixer and the speed
file are fakes. python tests/test_voice_words.py"""
import pathlib
import tempfile
import types

from assistant import lumi
from assistant import voice_words as vw
from audio import mouth

UP, DOWN, SLOWER, FASTER = ("volume", 1), ("volume", -1), ("speed", -1), ("speed", 1)
CASES = {"speak louder": UP, "a bit louder": UP, "louder please": UP, "I can't hear you": UP, "I cannot hear you, Lumi": UP,
         "I didn't catch that, louder": UP, "speak up": UP, "turn the volume up": UP, "can you speak louder?": UP,
         "you're too quiet": UP, "더 크게 말해": UP, "크게 말해 줘": UP, "안 들려": UP, "잘 안 들려요": UP,
         "소리 좀 키워 줘": UP, "목소리가 너무 작아요": UP, "루미야 좀 더 크게": UP, "louder 해 줘": UP, "speak 크게": UP,
         "speak quieter": DOWN, "too loud": DOWN, "lower your voice": DOWN, "softer please": DOWN, "turn it down": DOWN,
         "소리 좀 줄여": DOWN, "너무 시끄러워": DOWN, "작게 말해": DOWN, "목소리 좀 낮춰 주세요": DOWN, "you're so loud": DOWN,
         "speak slower": SLOWER, "talk more slowly please": SLOWER, "you talk too fast": SLOWER, "천천히 말해": SLOWER,
         "좀 천천히 말해 주세요": SLOWER, "말이 너무 빨라요": SLOWER, "speak 천천히": SLOWER,
         "talk faster": FASTER, "speak a bit quicker": FASTER, "빨리 말해": FASTER, "말이 너무 느려": FASTER,
         # not the voice: the drive speed, other commands, plain talk
         "go faster": None, "drive slower": None, "a bit faster": None, "slow down": None, "천천히 가": None,
         "빨리 가 줘": None, "너무 빨라": None, "크게 돌아": None, "turn left": None, "be quiet": None, "조용히 해": None,
         "say it again": None, "what did you say?": None, "speak Korean": None, "말해 줘": None, "천천히 와": None,
         "sing a song": None, "what can you do?": None, "follow me slowly": None}
wrong = {t: (vw.read(t), want) for t, want in CASES.items() if vw.read(t) != want}
assert not wrong, wrong
assert vw.read("조금 더", "ACTION: voice volume +1\nIs this better?") == UP
assert vw.read("a bit more", "ACTION: voice speed -1\nOkay") == SLOWER
assert vw.read("again", "ACTION: voice volume -1\nOkay") == DOWN
assert vw.read("한 번 더", "ACTION: voice volume +1\n...") == UP
assert vw.read("조금 더", "ACTION: speed 1\n...") is None and vw.read("again", "ACTION: none -\nHi") is None

# one step, inside the limits; never the real mixer
level = {"v": 60}
mouth.volume = lambda: level["v"]
mouth.set_volume = lambda p=None: level.update(v=p)
mouth.SPEED_FILE = pathlib.Path(tempfile.mkdtemp()) / "speech_speed.txt"
assert vw.apply("volume", 1) == "Is this better?" and level["v"] == 70
assert vw.apply("volume", -1, "ko").startswith("네") and level["v"] == 60
level["v"] = vw.VOLUME_MAX
assert vw.apply("volume", 1) == "This is as loud as I can speak." and level["v"] == vw.VOLUME_MAX
level["v"] = 95                                      # set higher on the dashboard: "louder" never lowers it
assert "loud as I can" in vw.apply("volume", 1) and level["v"] == 95
level["v"] = vw.VOLUME_MIN
assert "quiet as I can" in vw.apply("volume", -1) and level["v"] == vw.VOLUME_MIN
assert mouth.speed() == mouth.SPEED
vw.apply("speed", -1)
assert abs(mouth.speed() - (mouth.SPEED - vw.SPEED_STEP)) < 1e-6, mouth.speed()
for _ in range(10):
    vw.apply("speed", -1)
assert mouth.speed() == mouth.SPEED_MIN and "any slower" in vw.apply("speed", -1)
for _ in range(10):
    vw.apply("speed", 1)
assert mouth.speed() == mouth.SPEED_MAX and "더 빨리는" in vw.apply("speed", 1, "ko")

# lumi.answer(): the voice words come before the drive words ("again" after "louder" is the voice)
said = []
lumi.LOG_FILE = "/dev/null"
mouth.say = lambda text, lang=None, abort=None: said.append(text)
lumi.ears.understood = lambda *a: True
lumi.ears.last_stt = {"language": "english", "logprob": -0.1}
L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.current, L.closing_pending = "en", None, None
L.brain = types.SimpleNamespace(history=[])
L.follow_stop = lambda text: False
L.keep_listening = lambda: None
L.speak_abort = lambda: False
L.drive_words = lambda text: (_ for _ in ()).throw(AssertionError(f"drive words got {text!r}"))
level["v"] = 50
L.answer("speak louder please")
assert level["v"] == 60 and said[-1] == "Is this better?", (level, said)
L.answer("a bit more")
assert level["v"] == 70 and L.brain.history[-1][1].startswith("ACTION: voice volume +1"), L.brain.history
lumi.ears.last_stt = {"language": "korean", "logprob": -0.1}
L.answer("너무 시끄러워")
assert level["v"] == 60 and said[-1].startswith("네"), said
mouth.SPEED_FILE.unlink()
L.answer("천천히 말해 주세요")
assert mouth.speed() < mouth.SPEED and "천천히" in said[-1], said
print("voice words ok")
