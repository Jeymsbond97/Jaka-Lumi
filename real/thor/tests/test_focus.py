"""Self-check of the focus on one person (live 2026-10-27 19:22-19:28): once someone calls, gives an order or says
"look at me", the head stays on them as they move; a newcomer (even waving) is not greeted or looked at; someone else
takes over only with a call, a stop word or an order said from their direction. Fake vision, head, base and mic;
nothing reaches the robot: python tests/test_focus.py"""
import threading
import time
import types

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import lumi

M = ["home", "dock2"] + [f"p{i}" for i in range(1, 11)]
S = lumi.HEAD_SIGN
moves, said, base = [], [], {"move_status": "idle"}
lumi.head.status = lambda: [0.0, 0.0, 0.0, 20.0]
lumi.head.turn = lambda yaw, pitch=None, **k: moves.append(round(yaw))
lumi.mouth.say = lambda text, **k: said.append(text)
lumi.LOOK_ME_SETTLE_S = 0.0
up = []                                             # bearings of raised hands the fake pose net sees
lumi.hands_up = lambda frames: list(up)
import vision.scene as scene                        # noqa: E402
scene.snapshot = lambda cams: []


class Track:
    def __init__(self, id, angle, distance=1.2):
        self.id, self.angle, self.distance, self.greeted, self.person = id, angle, distance, False, None


class Vision:
    camera, pinned = "head", True

    def __init__(self, *tracks):
        self.tracks = list(tracks)
        self.det = types.SimpleNamespace(focus_angle=None)

    def near_angle(self, a, d=lumi.SPEAKER_MATCH_DEG):
        return min((t for t in self.tracks if abs(t.angle - a) <= d), key=lambda t: abs(t.angle - a), default=None)

    def present(self, t):
        return t in self.tracks

    visible = present

    def anyone(self):
        return bool(self.tracks)

    def only_seen(self):
        return self.tracks[0] if len(self.tracks) == 1 else None

    def to_greet(self):
        return next((t for t in self.tracks if not t.greeted), None)

    def only_person(self):                          # as lumi.Vision: within 3 m
        near = [t for t in self.tracks if t.distance <= 3.0]
        return near[0] if len(near) == 1 else None

    def nearest_greeted(self):
        return next((t for t in self.tracks if t.greeted), None)

    def seen(self):
        return [(t.angle, t.distance) for t in self.tracks]

    def head_person(self, angle, since):
        return None

    def know(self, t):
        return types.SimpleNamespace(talking=False), None


def fresh(*tracks):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.markers, L.lang, L.current, L.pending_text, L.patrol = M, "en", None, None, None
    L.vision, L.mic = Vision(*tracks), types.SimpleNamespace(next=lambda timeout: None)
    L.modes = types.SimpleNamespace(greeter=True, patrol=True, drive=True, refresh=lambda: None)
    L.voice_until = L.quiet_until = L.calib_until = 0.0
    L.last_activity, L.closing_pending, L._yaw, L._yaw_time = time.time(), None, 0.0, time.time() + 1e6
    L.skill_thread, L.prompts, L.wave_checked = None, 0, 0.0
    L.poll_commands = L.say_stuck = lambda: None
    L.reach_done = lambda: False
    L.publish_busy = lambda what: None
    L.talk_turn = lambda: False
    L.brain = types.SimpleNamespace(reset=lambda: None, history=[])
    moves.clear(), said.clear(), up.clear()
    return L


def settle():
    time.sleep(0.2)                                 # turn_head moves the head in a thread


# ---- talking with #1 (right), #2 walks in on the left and waves: no greeting, the head stays on #1 as they move ----
L = fresh(a := Track(1, 30.0))
a.greeted, L.current = True, a
L.vision.tracks.append(b := Track(2, -40.0))
up.append(-40.0)
for _ in range(3):
    L.step()
    L.wave_checked = 0.0
assert lumi.GREETING not in said and L.current is a and not b.greeted, said
a.angle = 45.0
L.focus_step()
settle()
assert moves == [S * 45], moves                     # the head follows #1, never #2
moves.clear()
L._yaw = S * 45
L.focus_step()                                      # still on them: no move
settle()
assert moves == [], moves

# ---- the voice near #2: plain words keep the focus on #1; "stop", "Lumi" or an order hand it to #2 ----
lumi.doa.load_calib = lambda: {"fitted": True}
lumi.doa.clip_ref = lambda u: None
lumi.doa.estimate = lambda mics, cal, ref=None: (-40.0, 0.9, 0.0)
lumi.waist_turned = lambda: 0.0
from tasks import fetch as _fetch                    # noqa: E402
_fetch._waist_to = lambda rel, in_place=False, look=None: True   # "look at me" past the head turns the waist
lumi.waist_home = lambda why: True
lumi.agv.turn_by = lambda rad: None                  # "look at me" past the head with Patrol turns the base
lumi.agv.status = lambda: {"move_status": "succeeded"}
U = types.SimpleNamespace(mics=None, seconds=1.0, source="clip")
for text, takes in (("The weather is nice today.", False), ("Stop.", True), ("Lumi, over here.", True),
                    ("Go to p3.", True), ("I like your colour.", False)):
    L = fresh(a := Track(1, 30.0), b := Track(2, -40.0))
    a.greeted, L.current = True, a
    L.who_spoke(U, text)
    settle()
    assert (L.current is b) == takes and (moves == [S * -40] if takes else moves == []), (text, L.current.id, moves)

# ---- "look at me" (19:24:16): focus on the person found; a newcomer does not take the head; the head follows the
# looked-at person over the held look, also when their track gets a new id (#5 -> #7) ----
L = fresh(a := Track(5, -19.0, 1.15))
L.voice_angle, L.voice_trusted = -62.0, True
L.looked_at = time.time()                           # act("look", "me") holds the look
L.look_at_speaker()
assert L.current is a and L.look_me is a and a.greeted, (L.current, getattr(L, "look_me", None))
L.vision.tracks.append(b := Track(6, 40.0))
up.append(40.0)
moves.clear()
for _ in range(3):
    L.step()
    L.wave_checked = 0.0
assert lumi.GREETING not in said and L.current is a, said
L._yaw = S * -19
a.angle = -35.0                                     # they step aside
L.focus_step()
settle()
assert L.look_held() and moves == [S * -35], moves  # over the held look: it was them
L.vision.tracks.remove(a)
L.vision.tracks.append(a2 := Track(7, -33.0, 1.15))
L.step()
assert L.current is a2 and L.look_me is a2, L.current.id
# a "look left" hold is not a person: the head stays where asked
L.look_me, L._yaw = None, S * 60
moves.clear()
L.focus_step()
settle()
assert moves == [], moves

# ---- "come here" with the look held: the head stays on the caller while the base drives ----
lumi.agv.cancel = lambda: None
lumi.agv.status = lambda: dict(base)
lumi.agv.pose = lambda: (0.0, 0.0, 0.0)
lumi.agv.go_point = lambda *a: (True, "")
lumi.agv.turn_by = lambda a: (_ for _ in ()).throw(AssertionError("the base turned away from the caller"))
lumi.nav.person_on_map = lambda *a: (3.0, 0.0)
lumi.nav.approach = lambda *a: (2.0, 0.0, 0.0)
lumi.waist_home = lambda why: True
L = fresh(a := Track(5, -19.0, 2.5), Track(8, 30.0, 2.4))
L.current, L.look_me, L.looked_at = a, a, time.time()
L.voice_angle, L.voice_trusted = -107.0, True       # the voice read far off (19:24:22): the focus wins
base["move_status"] = "running"
threading.Timer(1.5, lambda: base.update(move_status="succeeded")).start()
L.come_to(L.current, say=True)
settle()
assert moves and set(moves) == {S * -19}, moves

# ---- "come here" to the one person seen 4.7 m away, the voice unsure: drives to them (live 2026-10-28 17:42: "do you
# see me?" yes, "come here" said "I can't see you": present() ends at STAY_MAX, only_person() at 3 m) ----
goals = []
lumi.agv.go_point = lambda *a: goals.append(a) or (True, "")
L = fresh(Track(13, 187.0, 4.7))
L.current, L.voice_angle, L.voice_trusted = None, 244.0, False
base["move_status"] = "running"
threading.Timer(1.0, lambda: base.update(move_status="succeeded")).start()
L.come_to(L.current, say=True)
settle()
assert goals == [(2.0, 0.0, 0.0)] and L.current is not None and L.current.id == 13, (goals, L.current)
lumi.agv.go_point = lambda *a: (True, "")

# ---- after turning to the voice: the person nearest its side, not the nearest one far off it ----
heads = []
lumi.time.sleep, real_sleep = (lambda s: None), lumi.time.sleep
L = fresh(Track(9, -50.0, 0.8), Track(10, 38.0, 2.5))
L.vision.near_angle = lambda a, d=lumi.SPEAKER_MATCH_DEG: None
L.vision.seen = lambda: [(-50.0, 0.8), (38.0, 2.5)]
L.det_yaw = lambda: 0.0
L.turn_head = lambda yaw=None, pitch=None, force=False: heads.append((round(yaw), force))
L.find_caller(50.0, True)
lumi.time.sleep = real_sleep
assert heads == [(S * 50, True), (S * 38, True)], heads
# ---- who gave the order (speaker_track): never the wrong one of several people ----
owner, other = Track(20, 60.0, 4.0), Track(21, 0.0, 2.0)
L = fresh(owner, other)                              # the owner far behind the head's turn, someone else near ahead:
L._yaw = S * 60.0                                    # the head looks at the owner ("look at me" left it there)
L.voice_trusted = False
assert L.speaker_track() is owner and not said
L = fresh(owner, other)
L.voice_trusted, L.voice_angle = True, 2.0           # a sure voice wins over the look
assert L.speaker_track() is other
L = fresh(owner, other)                              # the voice unsure, the head between them, nobody talked with:
L.voice_trusted, L.voice_angle, L._yaw = False, 5.0, S * 30.0   # asked to raise a hand, the one who does is taken
up.append(60.0)
assert L.speaker_track() is owner and said == [lumi.RAISE_HAND_SAY[0]], said
up.clear()
L = fresh(owner, other)                              # nobody raises a hand: nobody is taken, it says so
L.voice_trusted, L._yaw, real_raise, lumi.RAISE_HAND_S = False, S * 30.0, lumi.RAISE_HAND_S, 0.3
assert L.speaker_track() is None and said == [lumi.RAISE_HAND_SAY[0], lumi.WHO_ASKED_SAY[0]], said
goals = []                                           # ... and "come here" then drives nowhere, no "can't see you"
lumi.agv.go_point = lambda *a: goals.append(a) or (True, "")
L = fresh(owner, other)
L.voice_trusted, L._yaw = False, S * 30.0
L.come_to(None)
assert not goals and said == [lumi.RAISE_HAND_SAY[0], lumi.WHO_ASKED_SAY[0]], said
lumi.RAISE_HAND_S, lumi.agv.go_point = real_raise, (lambda *a: (True, ""))
print("focus ok")
