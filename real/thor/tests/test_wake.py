"""Self-check of when Lumi speaks (owner's rules and live test 2026-10-23 16:30-17:10, logs/lumi.log): only when
called (wake word or a wave), never to someone who only stands there or walks past, never during a task; a talk
goes on without the wake word until it ends, then a call is needed again; an answer is never cut to greet someone,
the call is answered after it; "I am standing or sitting" is no name. Fake mic, camera, speech; nothing reaches the
robot: python tests/test_wake.py"""
import threading
import time
import types

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import brain as brain_mod
from assistant import lumi
from tasks import fetch, follow

done = []
lumi.agv.cancel = lambda: done.append("agv cancel")
lumi.agv.status = lambda: {"move_status": "idle"}
lumi.agv.turn_by = lambda a: done.append("TURN")
lumi.skills.cancel = lambda: done.append("skills cancel")
lumi.motion.stop = lambda: done.append("arm stop")
follow.running = lambda: False
fetch.state = lambda: {"status": "idle"}
lumi.mouth.say = lambda text, **k: done.append(("say", text))
lumi.mouth.own_voice = lambda u: False
lumi.mouth.recent_speech = lambda s: ""
lumi.mouth.last_echo = 0.0
lumi.doa.load_calib = lambda: {"fitted": False}
lumi.doa.estimate = lambda mics, cal, ref=None: (0.0, 0.0, 0.0)
lumi.ears.heard_lang = lambda lang: lang
lumi.ears.transcribe = lambda mono: mono
lumi.ears.understood = lambda lp: True
lumi.time.sleep = lambda s: None
lumi.waist_turned = lambda: 0.0                    # the waist at the front (it reads the body)
lumi.waist_home = lambda why, fold=False: True
M = ["home", "dock2"]


class U:                                           # one utterance from audio/mic.py
    def __init__(self, text, seconds=0.8, during_speech=False):
        self.mono, self.mics, self.seconds, self.during_speech, self.source = text, None, seconds, during_speech, "clip"


class Mic:
    def __init__(self, *utts):
        self.q = list(utts)

    def next(self, timeout):
        return self.q.pop(0) if self.q else None


class Track:
    def __init__(self, id, angle=0.0, distance=1.0):
        self.id, self.angle, self.distance, self.greeted, self.person = id, angle, distance, False, None


class Vision:                                      # people in the greeting zone, nobody waving unless `up` says so
    def __init__(self, *tracks):
        self.tracks, self.camera, self.pinned = list(tracks), "head", True
        self.det = types.SimpleNamespace(focus_angle=None)

    def to_greet(self):
        return next((t for t in self.tracks if not t.greeted), None)

    def near_angle(self, a, d=lumi.SPEAKER_MATCH_DEG):
        return min((t for t in self.tracks if abs(t.angle - a) <= d), key=lambda t: abs(t.angle - a), default=None)

    def present(self, t):
        return t in self.tracks

    def know(self, t):
        return types.SimpleNamespace(talking=False), None

    def only_person(self):
        return self.tracks[0] if len(self.tracks) == 1 else None

    def anyone_near(self):
        return bool(self.tracks)

    def nearest_greeted(self):
        return next((t for t in self.tracks if t.greeted), None)


up = []                                            # bearings of raised hands the fake pose net sees
lumi.hands_up = lambda frames: list(up)
import vision.scene as scene                       # noqa: E402
scene.snapshot = lambda cams: []


class Brain:
    history = []

    def reset(self):
        done.append("<reset>")


def fresh(*tracks, utts=()):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.markers, L.lang, L.current, L.pending_text, L.patrol = M, "en", None, None, None
    L.vision, L.mic, L.brain, L.chain_stop = Vision(*tracks), Mic(*utts), Brain(), threading.Event()
    L.modes = types.SimpleNamespace(greeter=True, patrol=False, drive=True, refresh=lambda: None)
    L.voice_until = L.quiet_until = L.calib_until = 0.0
    L.last_activity, L.closing_pending, L._yaw, L._yaw_time = time.time(), None, 0.0, time.time()
    L.skill_thread, L.prompts = None, 0
    L.poll_commands = L.mission_wait = L.say_stuck = lambda: None
    L.publish_busy = lambda what: None
    L.turn_head = lambda *a, **k: done.append("head")
    L.answer = lambda text: done.append(("answer", text))
    L.fetch_say = lambda en, ko: done.append(("say", en))
    L.mission_running = lambda: False
    L.mission_hold = None
    L.warm_llm = lambda: None
    L.who_spoke = lambda u, text=None: done.append("who spoke")
    lumi.ears.listen = lambda **k: (None, None)
    done.clear()
    up.clear()
    return L


said = lambda: [d[1] for d in done if isinstance(d, tuple) and d[0] == "say"]   # noqa: E731

# ---- the calls that wake Lumi (EN + KO + whisper slips) and what does not ----
for call in ("Lumi.", "Hi Lumi.", "Hi.", "Hello Lumi!", "Hello.", "Hey Lumi", "How are you?", "Hi, how are you?",
             "루미야.", "루미.", "안녕.", "안녕하세요.", "하이.", "하이 루미!", "Hi, Loomi.", "Hello, Rumi.", "Hai.",
             "Lummy?", "누미야", "안녕하십니까.", "Wake up.", "Wake up, Lumi!", "Hey Lumi.", "Lumi, wake up.",
             "헤이 루미", "루미야 일어나", "루미 일어나세요.", "일어나세요.", "깨어나 루미야"):
    L = fresh()
    L.mic = Mic(U(call))
    assert L.check_wake(), call
    assert lumi.call_only(call), call
for heard in ("Let's make music.", "What is that?", "We make it.", "Let's.", "It looks fun.", "Okay.", ""):
    L = fresh()
    L.mic = Mic(U(heard))
    assert not L.check_wake(), heard                   # 16:57:00, 17:05:03 live: "(no wake word)"
assert not lumi.call_only("Lumi, what time is it?") and not lumi.call_only("루미야 노래 불러줘")
for call in ("Lumi.", "Lumi?", "Hey, Lumi!", "루미야.", "루미야?", "루미!", "헤이 루미", "하이 루미야", "누미야"):   # in a talk:
    assert lumi.NAME_ONLY.match(call), call                                    # "Yes?" / "네?" at once, no LLM
for heard in ("How are you?", "Hi.", "안녕하세요.", "루미야 노래 불러줘", "Lumi, wake up."):
    assert not lumi.NAME_ONLY.match(heard), heard
assert not lumi.WAKE.search("I wake up at 7 every day") and not lumi.WAKE.search("일어나서 밥 먹었어")   # no call
L = fresh()                                            # "How are you?" is answered, not "Yes? How can I help?"
L.mic = Mic(U("How are you?"))
L.check_wake()
assert ("answer", "How are you?") in done and lumi.WAKE_REPLY["en"] not in said(), done
L = fresh()                                            # "Hi Lumi, go home": done at once
L.mic = Mic(U("Hi Lumi, go home."))
L.check_wake()
assert ("answer", "go home") in done, done

# ---- someone who only stands in front (16:45:07 "see #11 ... greeted", 17:05:08 "GREET person #23"): no word ----
a = Track(23, -28, 0.87)
L = fresh(a)
for _ in range(10):
    L.step()
assert said() == [] and L.current is None and not a.greeted, done

# ---- a wave (a hand up, facing Lumi, two looks in a row): greeted ----
L = fresh(a := Track(23, -28, 0.87))
up.append(-30.0)
for _ in range(3):
    L.step()
    L.wave_checked = 0.0                               # the next look at once (no real time passes here)
assert lumi.GREETING in said() and L.current is a, done
L = fresh(a := Track(5, 0))                            # one frame with a hand up: not yet
up.append(0.0)
assert L.waver() is None
up.clear()
L.wave_checked = 0.0
assert L.waver() is None
L = fresh(a := Track(5, 40), Track(6, -40))            # the other person's hand: not this one
up.append(-40.0)
L.vision.tracks[1].greeted = True
for _ in range(3):
    L.step()
    L.wave_checked = 0.0
assert said() == [], done

# ---- never during a task or a drive, even for a wave ----
for busy in ("skill", "drive"):
    L = fresh(a := Track(7, 0))
    up.append(0.0)
    L.doing = lambda b=busy: b
    if busy == "drive":
        L.traveling = lambda: True
        L.patrol = types.SimpleNamespace(mode="patrol", moving=True, tick=lambda: None, pause=lambda: None)
    for _ in range(3):
        L.step()
        L.wave_checked = 0.0
    assert lumi.GREETING not in said(), (busy, done)

# ---- talking with #23, a newcomer stands in the zone: the answer is not cut (interrupted() stays False) ----
a, b = Track(23, -28), Track(26, 55)
L = fresh(a, b)
a.greeted, L.current = True, a
assert not L.interrupted() and not L.speak_abort.__self__.interrupted()

# ---- 17:05:24 "루미야." while Lumi answered "Give me.": the answer went on, the call answered after it ----
for call in ("루미야.", "Hi Lumi.", "안녕하세요.", "Hello, Lumi!"):
    L = fresh(a := Track(23, 0))
    a.greeted, L.current = True, a
    L.mic = Mic(U(call, during_speech=True))
    assert L.barge_in() is False, call                 # the sentence is not cut
    assert L.pending_text == call
    assert L.talk_turn() and ("answer", call) in done and "who spoke" in done, (call, done)   # turned to them
L = fresh(a := Track(23, 0))                           # a real question from the visitor still interrupts
a.greeted, L.current = True, a
L.mic = Mic(U("Lumi, what is in my hand?", during_speech=True))
assert L.barge_in() is True
L = fresh(a := Track(23, 0))                           # and a stop word from anyone stops at once
a.greeted, L.current = True, a
L.act = lambda action, target: done.append(("act", action))
L.mic = Mic(U("Stop.", during_speech=True))
assert L.barge_in() is True and ("act", "stop") in done

# ---- the talk goes on without the wake word; silence ends it quietly; then a call is needed again ----
L = fresh(a := Track(14, 60))
a.greeted, L.current = True, a
lumi.ears.listen = lambda **k: ("What is behind me?", None)
L.follow_filter = lambda text, u: False
L.step()
assert ("answer", "What is behind me?") in done        # no wake word needed in an open talk
lumi.ears.listen = lambda **k: (None, None)
L.last_activity = time.time() - lumi.TALK_IDLE_S - 1
done.clear()
L.step()
assert L.current is None and said() == [], done        # over, no goodbye into the silence
L.mic = Mic(U("What is that?"))
L.step()
assert not any(d[0] == "answer" for d in done if isinstance(d, tuple)), done   # needs "Lumi" again
assert L.vision.to_greet() is None                     # still in view, not greeted again by standing there
L.mic = Mic(U("루미야, 뭐 보여?"))
L.step()
assert ("answer", "뭐 보여") in done, done

# the person talked with, still tracked but past STAY_MAX (come here took a far one): gone, never "seen again" as
# itself (that looped ~33000 times a s, the assistant went deaf, 2026-10-28 18:06)
L = fresh(a := Track(10, 186.0, 4.7))
a.greeted, L.current = True, a
L.vision.present = lambda t: t in L.vision.tracks and t.distance <= lumi.STAY_MAX
L.vision.nearest_greeted = lambda: None
lumi.ears.listen = lambda **k: (None, None)
L.step()
assert L.current is None, L.current

L = fresh()                                            # a talk started by voice ends the same way
L.voice_until = time.time() - 1
L.brain.history = [("hi", "hello")]
L.end_conversation = lambda text=None, quiet=False: done.append(("end", quiet))
L.check_wake = lambda: False
L.step()
assert ("end", True) in done, done

# ---- 16:46:41 "I am standing or sitting." -> "It is nice to meet you.": no name in it ----
for text in ("I am standing or sitting.", "Am I sitting or standing?", "It looks like a phone.", "It looks iPhone.",
             "I'm sitting.", "I am standing here."):
    assert lumi.claimed_name(text) is None, text
assert lumi.claimed_name("I'm James.") == "james"
assert "only when they clearly tell you their name" in brain_mod.SYSTEM

# the head rests looking down (lowest pitch): every "head back" sends HEAD_REST_PITCH, never pitch 0
src = open(lumi.__file__).read()
assert "turn_head(0, 0)" not in src and "head.HEAD_REST_PITCH" in src
assert lumi.LOOK["center"] == (0, lumi.head.HEAD_REST_PITCH) and lumi.head.HEAD_REST_PITCH == lumi.head.PITCH_RANGE[0]

# a look asked for is held: automatic head moves wait until LOOK_HOLD_S of silence, a goodbye or a stop word
moves = []
real_status, real_turn = lumi.head.status, lumi.head.turn
lumi.head.status = lambda: [50.0, 0.0, 0.0, 20.0]
lumi.head.turn = lambda yaw, pitch=None, **k: moves.append((yaw, pitch))
H = lumi.Lumi.__new__(lumi.Lumi)
H.looked_at, H.last_activity = time.time(), time.time()             # "look up" just now
H.turn_head(30.0)                                                   # toward a speaker: waits
H.turn_head(0, lumi.head.HEAD_REST_PITCH)                           # back to rest: waits
H.looked_at = H.last_activity = time.time() - lumi.LOOK_HOLD_S + 1  # still inside the hold
H.turn_head(0, lumi.head.HEAD_REST_PITCH)
time.sleep(0.2)
assert moves == [] and H.look_held(), moves
H.turn_head(10.0, 10, force=True)                                   # an order still moves it
H.looked_at = H.last_activity = time.time() - lumi.LOOK_HOLD_S - 1  # 35 s of silence: rest
H.turn_head(0, lumi.head.HEAD_REST_PITCH)
time.sleep(0.2)
assert moves == [(10.0, 10), (0, lumi.head.HEAD_REST_PITCH)] and not H.look_held(), moves
moves.clear()
H.looked_at = H.last_activity = time.time()
H.head_rest()                                                       # "be quiet" ends the hold
time.sleep(0.2)
assert moves == [(0, lumi.head.HEAD_REST_PITCH)] and H.looked_at == 0.0, moves
lumi.head.status, lumi.head.turn = real_status, real_turn

# the head stays toward the person while the conversation goes on; it rests only when the conversation is over
fetch.stop = lambda: done.append("fetch stop")
L = fresh(a := Track(31, 40))
a.greeted, L.current, L.looked_at = True, a, time.time()
L.act = lambda action, target: done.append(("act", action))
L.stop_all("Stop.")                                    # stopping a song or an answer mid-talk
assert ("act", "stop") in done and "head" not in done and L.looked_at == 0.0, done
L = fresh(a := Track(32, 40))
a.greeted, L.current = True, a
L.vision.tracks.clear()                                # out of the frame, nobody else greeted
L.step()
assert L.current is None and L.voice_until > time.time() and "head" not in done, done
L.step()                                               # the voice session goes on: still no rest
assert "head" not in done, done
L.voice_until = time.time() - 1                        # the session ends by silence, nobody in view
L.check_wake = lambda: False
L.step()
assert "head" in done and L.voice_until == 0.0, done   # end_conversation: yaw 0, rest pitch

# the conversation ends (silence, goodbye, "be quiet"): the waist comes back to the front too, Greeter or Patrol;
# a held look keeps both (the waist waits like the head)
homed, back = [], threading.Event()
real_home, real_turned = lumi.waist_home, lumi.waist_turned
lumi.waist_home = lambda why, fold=False: homed.append(why) or back.set() or True
for patrol in (False, True):
    L = fresh(a := Track(33, 40))
    a.greeted, L.current, L.modes.patrol = True, a, patrol
    L.traveling = lambda: False
    homed.clear(), back.clear()
    L.end_conversation(None, quiet=True)
    assert back.wait(2) and "head" in done and L.current is None and homed, (patrol, done, homed)
    homed.clear(), back.clear()
    L.head_rest()                                      # "be quiet"
    assert back.wait(2) and homed
L.looked_at = L.last_activity = time.time()            # "look up" just now, then silence ends the talk
homed.clear(), back.clear()
L.end_conversation(None, quiet=True)
assert not back.wait(0.3) and not homed

# someone else takes over (on the right, Lumi turned left for the first one): the waist back to the front, then the
# head to the new person (their angle from the waist's old place + the turn taken back); not turned: the head only
lumi.doa.load_calib = lambda: {"fitted": True}
lumi.doa.clip_ref = lambda u: None
lumi.doa.estimate = lambda mics, cal, ref=None: (-50.0, 0.9, 0.0)
for turned, homes, want in ((30.0, True, -20.0), (30.0, False, -50.0), (0.0, True, -50.0)):
    L = fresh(a := Track(40, 40), b := Track(41, -50))
    a.greeted, L.current = True, a
    heads, back = [], threading.Event()
    L.turn_head = lambda yaw=None, *r, **k: heads.append(yaw) or back.set()
    lumi.waist_turned = lambda w=turned: w
    lumi.waist_home = lambda why, ok=homes, fold=False: homed.append(why) or ok
    homed.clear()
    lumi.Lumi.who_spoke(L, U("Lumi, stop.", seconds=1.0))
    assert back.wait(2) and L.current is b and heads == [lumi.HEAD_SIGN * want], (turned, homes, heads)
    assert bool(homed) == bool(turned), (turned, homed)
lumi.waist_home, lumi.waist_turned = real_home, real_turned
lumi.doa.load_calib = lambda: {"fitted": False}
lumi.doa.estimate = lambda mics, cal, ref=None: (0.0, 0.0, 0.0)

print("ok: wake words, waves, no greeting to passers-by or during tasks, answers never cut, names")
