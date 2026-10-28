"""Self-check of stop words heard while Lumi moves, replaying the owner's live test of 2026-10-23 15:02-15:21
(logs/lumi_console.log): "Stop." on a drive to a marker went on ("heard 'Stop.' (no wake word)"), "Stop, 루미."
only paused the drive and turned the base toward the voice, a one-word "Stop." / "멈춰." while Lumi talked was not a
stop. Fake mic, speech-to-text and base; nothing reaches the robot: python tests/test_stop_live.py"""
import threading
import time

from assistant import lumi
from tasks import fetch, follow

M = ["home", "dock2"] + [f"p{i}" for i in range(1, 11)]
done = []
base = {"move_status": "idle"}

# the robot: every call that could move or stop something is recorded, never sent
lumi.agv.cancel = lambda: done.append("agv cancel")
lumi.agv.status = lambda: dict(base)
lumi.agv.turn_by = lambda a: done.append("TURN")              # find_caller's turn toward the voice
lumi.agv.go_point = lambda *a: done.append("GO") or (True, "")
lumi.skills.cancel = lambda: done.append("skills cancel")
lumi.motion.stop = lambda: done.append("arm stop")
follow.stop = lambda: done.append("follow stop")
fetch.stop = lambda: done.append("fetch stop")
fetch.state = lambda: {"status": "idle"}
lumi.waist_home = lambda why: True                # the waist at the front before a drive (it reads the body and arm)
lumi.waist_turned = lambda: 0.0
lumi.mouth.say = lambda text, **k: done.append(("say", text))
lumi.mouth.own_voice = lambda u: False
lumi.mouth.recent_speech = lambda s: ""
lumi.doa.load_calib = lambda: {"fitted": False}
lumi.doa.estimate = lambda mics, cal, ref=None: (0.0, 0.0, 0.0)
lumi.ears.heard_lang = lambda lang: lang


class U:                                           # one utterance from audio/mic.py
    def __init__(self, text, seconds=0.8, during_speech=False):
        self.mono, self.mics, self.seconds, self.during_speech, self.source = text, None, seconds, during_speech, "clip"


lumi.ears.transcribe = lambda mono: mono           # the fake utterance carries what whisper heard


class Mic:
    def __init__(self, *utts):
        self.q = list(utts)

    def next(self, timeout):
        return self.q.pop(0) if self.q else None


class Brain:
    def reset(self):
        pass


def fresh(*utts, trip=True):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.markers, L.lang, L.current, L.vision, L.pending_text = M, "en", None, None, None
    L.mic, L.brain, L.chain_stop = Mic(*utts), Brain(), threading.Event()
    L.patrol = lumi.Patrol(["p5"], once=True) if trip else None
    if trip:
        L.patrol.moving = True
    L.voice_until = L.quiet_until = 0.0
    L.last_activity, L.closing_pending, L._yaw, L._yaw_time = time.time(), None, 0.0, time.time()
    L.fetch_say = lambda en, ko: done.append(("say", en))
    L.answer = lambda text: done.append(("answer", text))
    done.clear()
    base["move_status"] = "running" if trip else "idle"
    return L


def stopped(L):
    return "agv cancel" in done and "arm stop" in done and L.patrol is None and ("say", "Okay, I stopped.") in done


# 15:10:13 "Let's go P5." -> patrol -> p5; then "Stop looming." / "Stop." / "Stop it." (no wake word): drove on
for heard in ("Stop looming.", "Stop.", "Stop it.", "멈춰.", "스톱!", "그만.", "Stop, stop."):
    L = fresh(U(heard))
    assert L.check_wake() and stopped(L), (heard, done)

# 15:21:23 "Stop, 루미." on a drive: only "drive paused", then a base turn toward the voice and "drive on" later
L = fresh(U("Stop, 루미."))
assert L.check_wake() and stopped(L) and "TURN" not in done and "GO" not in done, done

# said while Lumi talks on the trip (clip mic, during_speech): a stop word still stops; other words are left alone
L = fresh(U("Stop.", during_speech=True))
assert L.check_wake() and stopped(L), done
L = fresh(U("Lumi, go home.", during_speech=True))
assert not L.check_wake() and "agv cancel" not in done, done

# a drive the dashboard or the base started (no trip of the assistant's own) is stopped too
L = fresh(U("Stop."), trip=False)
base["move_status"] = "running"
assert L.check_wake() and "agv cancel" in done, done

# nothing moves: "stop it" between visitors is not answered; "Hi Lumi" on a drive still pauses and talks
L = fresh(U("Stop it."), trip=False)
assert not L.check_wake() and not done, done
L = fresh(U("Hi Lumi."))
assert L.check_wake() and "agv cancel" in done and L.patrol is not None and ("say", "Okay, I stopped.") not in done, done
L = fresh(U("It stopped."))
assert not L.check_wake() and "agv cancel" not in done, done

# one-word stop while Lumi talks (barge-in): "Stop." was a closing word (talk ended, the drive went on), "멈춰." ignored
lumi.ears.understood = lambda *a: True
for heard in ("Stop.", "멈춰.", "스탑", "Stop it."):
    L = fresh(U(heard, during_speech=True))
    assert L.barge_in() and "agv cancel" in done and "arm stop" in done and L.pending_text == heard, (heard, done)
    assert lumi.route(heard, M, L.brain)[0] == "stop", heard          # answered next: stop_all
L = fresh(U("I see.", during_speech=True))
lumi.brain_mod.is_backchannel = lambda t: True
L.barge_in()
assert "agv cancel" not in done, done


# "come here": the main loop waits on the drive; "stop" from anyone ends it, other words are answered after it
class Track:
    id, distance, angle = 5, 3.0, 0.0


class Vision:
    present = lambda self, t: True


lumi.agv.pose = lambda: (0.0, 0.0, 0.0)
lumi.head.status = lambda: [0, 0, 0, 0]
lumi.nav.person_on_map = lambda *a: (3.0, 0.0)
lumi.nav.approach = lambda *a: (2.0, 0.0, 0.0)
L = fresh(U("Stop!"), trip=False)
L.vision, L.modes, L.turn_head = Vision(), type("Modes", (), {"drive": True})(), lambda *a, **k: None
base["move_status"] = "running"
t = time.time()
L.come_to(Track())
assert stopped(L) and time.time() - t < 3, done
L = fresh(U("What is your name?"), trip=False)
L.vision, L.modes, L.turn_head = Vision(), type("Modes", (), {"drive": True})(), lambda *a, **k: None
base["move_status"] = "running"
threading.Timer(1.0, lambda: base.update(move_status="succeeded")).start()
L.come_to(Track())
assert "agv cancel" not in done and L.pending_text == "What is your name?", done

# right after Lumi said "Okay, I stopped.", "Stop." is no echo of it (own_echo counts "stop" in "stopped")
lumi.mouth.recent_speech = lambda s: "Okay, I stopped. Let's go to p5."
L = fresh(U("Stop."), trip=False)
L.vision, L.modes, L.turn_head = Vision(), type("Modes", (), {"drive": True})(), lambda *a, **k: None
base["move_status"] = "running"
L.come_to(Track())
assert stopped(L), done
head_u = U("Stop.")
head_u.source = "head"
lumi.ears.listen = lambda **k: ("Stop.", head_u)
L = fresh(trip=False)
L.warm_llm, L.interrupted, L.who_spoke, L.mission_hold = lambda: None, lambda: False, lambda u, text=None: None, None
L.follow_filter = lambda text, u: False
assert L.talk_turn() and ("answer", "Stop.") in done, done

# a stop word passes every echo filter: mouth.own_voice, own_echo, the ECHO_LIKELY gate (barge-in, talk_turn, check_wake)
lumi.mouth.own_voice = lambda u: True
lumi.mouth.last_echo = 0.9
for heard in ("Stop.", "멈춰.", "Stop it."):
    L = fresh(U(heard, during_speech=True))
    assert L.barge_in() and "agv cancel" in done and L.pending_text == heard, (heard, done)
    L = fresh(U(heard, during_speech=True))
    assert L.check_wake() and stopped(L), (heard, done)
L = fresh(trip=False)
L.warm_llm, L.interrupted, L.who_spoke, L.mission_hold = lambda: None, lambda: False, lambda u, text=None: None, None
L.follow_filter = lambda text, u: False
assert L.talk_turn() and ("answer", "Stop.") in done, done
L = fresh(U("Okay, I'm going to p5.", during_speech=True))           # Lumi's own sentence: still ignored
assert not L.barge_in() and "agv cancel" not in done, done
lumi.mouth.own_voice, lumi.mouth.last_echo = (lambda u: False), 0.0
lumi.mouth.recent_speech = lambda s: ""

# whisper's slips of the stop words, and talk about stopping that orders nothing
for t in ("스탑.", "Stob.", "Stopp!", "Lumi stopped.", "멈추세요.", "Stop looming.", "Stop, 루미."):
    assert lumi.stop_order(t, M), t
for t in ("It stopped.", "The bus stop is there.", "Don't stop.", "계속 가.", "Why did you stopped?", "My laptop freezes."):
    assert not lumi.stop_order(t, M), t
assert follow.stop_word("스탑")

print("ok")
