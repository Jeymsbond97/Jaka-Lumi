"""Self-check of who Lumi listens to while following (only the followed person; anyone's stop word stops the base),
no robot, no audio: python tests/test_follow_listen.py"""
import threading
import time

from assistant import lumi
from tasks import follow

done, heard = [], []
follow.running = lambda: run["on"]
follow.followed_angle = lambda: run["angle"]
follow.stop = lambda: done.append("follow stop")
lumi.doa.load_calib = lambda: {"fitted": True}
lumi.doa.estimate = lambda mics, cal: (mics, 0.5, None)      # the fake mics carry the voice angle (head frame)
lumi.mouth.say = lambda text, **k: done.append(("say", text))
lumi.mouth.recent_speech = lambda s=30.0: ""
lumi.ears.understood = lambda *a: True
run = {"on": True, "angle": 20.0}


class U:                                       # one utterance from the head array
    def __init__(self, deg):
        self.mics, self.seconds, self.source, self.during_speech = deg, 1.2, "array", False


class Track:
    def __init__(self, tid, angle):
        self.id, self.angle, self.person, self.greeted = tid, angle, None, False


class Vision:                                  # someone at -60 deg besides the followed person
    def __init__(self):
        self.stranger = Track(31, -60.0)

    def only_person(self):
        return None

    def near_angle(self, a, max_diff=25.0):
        return self.stranger if abs(a + 60.0) <= max_diff else None

    def present(self, t):
        return True

    def to_greet(self):
        return None


def fresh(said, deg, yaw=10.0):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.markers, L.lang, L.current, L.mission_hold, L.asked_go_on = ["home"], "en", None, None, False
    L.pending_text, L.closing_pending, L.voice_until, L.vision = None, None, time.time() + 15, Vision()
    L.patrol, L.chain_stop, L.sorry_at = None, threading.Event(), 0.0
    L.warm_llm = lambda: None
    L.det_yaw = lambda: yaw
    L.turn_head = lambda *a: done.append(("head", a))
    L.answer = lambda text: heard.append(text)
    L.fetch_say = lambda en, ko: done.append(("say", en))
    L.keep_listening = lambda: None
    L.act = lambda action, target: done.append(("act", action))
    lumi.ears.listen = lambda **k: (said, U(deg))
    done.clear()
    heard.clear()
    return L


# the followed person (at +20 deg, head yaw +10, voice +10 in the head frame) asks while walking: answered, following on
for q in ("What's the weather like today?", "How far am I from you?", "Can you see me?", "오늘 날씨 어때?"):
    L = fresh(q, 10.0)
    assert L.talk_turn() and heard == [q] and "follow stop" not in done, (q, heard, done)
    assert not any(d[0] == "head" for d in done if isinstance(d, tuple)), done
# a little off (the sound direction is not exact) is still them; far off is not
L = fresh("How far am I from you?", 35.0)                 # 25 deg off
assert L.talk_turn() and heard, heard
# a stranger at -60 deg asks / commands: not acted on, one short line, the head not turned, no new current
for i, q in enumerate(("What time is it?", "Lumi, come to me", "Follow me", "Hi Lumi")):
    L = fresh(q, -70.0)
    L.sorry_at = 0.0 if i == 0 else time.time()
    assert L.talk_turn() and heard == [] and "follow stop" not in done, (q, heard, done)
    assert L.current is None and not any(d[0] == "head" for d in done if isinstance(d, tuple)), done
    says = [d for d in done if isinstance(d, tuple) and d[0] == "say"]
    assert says == ([("say", "Sorry, I'm following someone right now.")] if i == 0 else []), (q, says)
L = fresh("지금 몇 시야?", -70.0)
assert L.talk_turn() and done == [("say", "지금은 다른 분을 따라가는 중이에요.")], done
# unsure (not calibrated, or the followed person not seen): only the followed person's words count, so dropped
lumi.doa.load_calib = lambda: {"fitted": False}
L = fresh("How far am I from you?", 10.0)
assert L.talk_turn() and heard == [], heard
lumi.doa.load_calib = lambda: {"fitted": True}
run["angle"] = None
L = fresh("How far am I from you?", 10.0)
assert L.talk_turn() and heard == [], heard
run["angle"] = 20.0
# the followed person says stop: it goes to answer(), whose follow_stop ends following
L = fresh("stop", 10.0)
assert L.talk_turn() and heard == ["stop"], heard
assert L.follow_stop("stop") and "follow stop" in done, done
# a stranger says stop: the base stops (safety), following ends
for word in ("stop", "Stop it!", "멈춰", "wait"):
    L = fresh(word, -70.0)
    assert L.talk_turn() and "follow stop" in done and ("act", "stop") in done and heard == [], (word, done)
# not following: today's rule, anyone is heard and looked at
run["on"] = False
L = fresh("What time is it?", -70.0)
assert L.talk_turn() and heard == ["What time is it?"] and L.current is L.vision.stranger, (heard, L.current)
print("follow listen ok")
