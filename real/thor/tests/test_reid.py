"""Self-check of knowing people again (vision/reid.py, lumi.Vision.know, Lumi.greet after a wave), no robot, no camera:
python tests/test_reid.py"""
import types

import numpy as np

from assistant import lumi
from vision import reid

# ---------- signatures: the same clothes in other light are the same person, other clothes are not ----------
def person_img(shirt, trousers, light=1.0, w=200, h=600):
    img = np.full((720, 1280, 3), (90, 110, 100), np.uint8)               # the room
    img[100:100 + h // 2, 500:500 + w] = shirt
    img[100 + h // 2:100 + h, 500:500 + w] = trousers
    return np.clip(img * light, 0, 255).astype(np.uint8), (500, 100, 500 + w, 100 + h)

RED, NAVY, WHITE, BLACK, GREEN, BEIGE = (40, 40, 200), (90, 40, 30), (235, 235, 235), (25, 25, 25), (60, 160, 60), (150, 190, 210)
red_jeans = reid.look(*person_img(RED, NAVY))
assert reid.same(red_jeans, reid.look(*person_img(RED, NAVY, light=0.75))) >= reid.SAME
assert reid.same(red_jeans, reid.look(*person_img(RED, NAVY, w=150, h=500))) >= reid.SAME   # farther away
for other in [(WHITE, BLACK), (GREEN, NAVY), (RED, BEIGE), (BEIGE, BLACK)]:
    assert reid.same(red_jeans, reid.look(*person_img(*other))) < reid.SAME, other
assert reid.same(red_jeans, [0.0] * len(red_jeans)) == 0.0                # nothing to compare: not the same
assert len(red_jeans) == len(reid.look(np.zeros((720, 1280, 3), np.uint8), (5, 5, 6, 6)))   # tiny box: empty parts

# ---------- Lumi: greet, leave, come back ----------
clock = {"t": 1000.0}
lumi.time = types.SimpleNamespace(time=lambda: clock["t"], sleep=lambda s: None)
said = []
lumi.mouth = types.SimpleNamespace(say=lambda text, **k: said.append(text))
lumi.log = lambda msg: None

LOOK = {"red": red_jeans, "white": reid.look(*person_img(WHITE, BLACK)), "green": reid.look(*person_img(GREEN, NAVY))}
rng = np.random.default_rng(1)
FACE = {n: list(v / np.linalg.norm(v)) for n, v in (("anna", rng.normal(size=128)), ("ben", rng.normal(size=128)))}
FACE["anna_turned"] = list(np.asarray(FACE["anna"]) + rng.normal(size=128) * 0.12)     # cosine ~0.6 to "anna"


def make():
    v = lumi.Vision.__new__(lumi.Vision)
    v.tracks, v.people, v.near_max, v.corridor, v.arm_watch = [], reid.People(), lumi.NEAR_MAX, None, False
    v.lock = lumi.threading.Lock()
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.vision, L.current, L.lang, L.voice_until = v, None, "en", 0.0
    L.brain = types.SimpleNamespace(reset=lambda: said.append("<reset>"))
    L.turn_head = lambda *a: None
    L.wave = lambda: None
    return L


def see(v, people, seconds=2.0):
    """The camera sees these (look name, angle) for `seconds` at 10 fps; tracking as in Vision.run."""
    for _ in range(int(seconds * 10)):
        clock["t"] += 0.1
        now = clock["t"]
        free = list(v.tracks)
        for name, angle, *face in people:
            p = {"distance_m": 1.0, "angle_deg": angle, "look": LOOK[name], "face": FACE[face[0]] if face else None}
            best = min(free, default=None, key=lambda t: abs(t.angle - angle))
            if best and abs(best.angle - angle) < lumi.MATCH_DEG:
                best.update(p, now)
                free.remove(best)
            else:
                t = lumi.Track(p, now)
                t.update(p, now)
                v.tracks.append(t)
        v.tracks = [t for t in v.tracks if now - t.last_seen < lumi.LOST_S]


def greet_next(L):
    said.clear()
    t = L.vision.to_greet()
    assert t is not None
    L.greet(t)
    return t


def leave(L, seconds):
    """Everyone walks out of view; Lumi's step drops the current person and keeps listening by voice for a while."""
    see(L.vision, [], 3.0)
    if L.current is not None:
        L.current, L.voice_until = None, clock["t"] + lumi.VOICE_SESSION_S
    clock["t"] += seconds


def goodbye(L):
    """The person says goodbye in view (answer() / end_conversation clear the talk)."""
    L.current, L.voice_until = None, 0.0


# who it is is decided once a few faces are seen, or after FACE_WAIT_S without them
L = make()
see(L.vision, [("red", 0)], 1.0)
assert L.vision.to_greet() is None                                        # no face yet: Lumi waits
see(L.vision, [("red", 0)], lumi.FACE_WAIT_S)
assert L.vision.to_greet() is not None                                    # waited long enough: the clothes decide
L = make()
see(L.vision, [("green", 40, "ben")], 1.0)
assert L.vision.to_greet() is not None                                    # faces seen: no wait

# a new person who waves: the full greeting
L = make()
see(L.vision, [("red", 0)])
a = greet_next(L)
assert lumi.GREETING in said and L.current is a, said

# gone, back at another angle (a new track) and waves again: known, the short welcome back (a wave always answered)
goodbye(L)
leave(L, 60)
see(L.vision, [("red", -10)])
greet_next(L)
assert said == ["<reset>", lumi.WELCOME_BACK["en"]], said

# away a few minutes: welcome back too
leave(L, 160)
see(L.vision, [("red", 0)])
greet_next(L)
assert lumi.WELCOME_BACK["en"] in said, said

# away longer than FORGET_S: forgotten, the full greeting
goodbye(L)
leave(L, reid.FORGET_S + 10)
see(L.vision, [("red", 0)])
greet_next(L)
assert lumi.GREETING in said, said

# two people: each known apart, also when they come back on each other's side
L = make()
see(L.vision, [("red", 20)])
red = greet_next(L).person
see(L.vision, [("red", 20), ("white", -20)])
white = greet_next(L).person                                              # someone new arrives: greeted too
assert lumi.GREETING in said and white is not red
goodbye(L)
leave(L, 30)
see(L.vision, [("white", 20), ("red", -20)])
first = greet_next(L)
second = greet_next(L)
assert {first.person, second.person} == {red, white}, "swapped sides: still told apart"
assert all(s != lumi.GREETING for s in said)

# someone in the same clothes as a person in view now is not that person: a new person
see(L.vision, [("white", 20), ("red", -20), ("red", 60)])
twin = greet_next(L)
assert twin.person not in (red, white) and lumi.GREETING in said, said

# a new person while others are known: the full greeting
see(L.vision, [("white", 20), ("red", -20), ("red", 60), ("green", -60)])
assert greet_next(L).person not in (red, white) and lumi.GREETING in said

# no signature (an older camera service): treated as new, as before
L = make()
LOOK["none"] = None
see(L.vision, [("none", 0)])
greet_next(L)
leave(L, 30)
see(L.vision, [("none", 0)])
greet_next(L)
assert lumi.GREETING in said

# faces decide when both are seen: two people in the same white shirts are two, a changed shirt is the same face
L = make()
see(L.vision, [("white", 0, "anna")])
anna = greet_next(L).person
goodbye(L)
leave(L, 30)
see(L.vision, [("white", 0, "ben")])
assert greet_next(L).person is not anna and lumi.GREETING in said, said
goodbye(L)
leave(L, 30)
see(L.vision, [("green", 0, "anna")])                                      # took the jacket off
assert greet_next(L).person is anna and said[-1] == lumi.WELCOME_BACK["en"], said
see(L.vision, [("green", 0, "anna")], 3.0)                                # talks a while: the green is learnt
goodbye(L)
leave(L, 30)
see(L.vision, [("green", 0)])                                              # face not seen: the clothes decide
assert greet_next(L).person is anna, said
assert reid.alike(None, FACE["anna"], None, FACE["anna_turned"])          # a less clear view of the same face
f = None                                                                  # the face kept is the mean of all seen:
for e in [FACE["anna"]] * 20 + [FACE["ben"]] * 5:                          # a few poor frames last do not replace it
    f = reid.blend_face(f, e)
assert reid.alike(None, f, None, FACE["anna"])
a, o = np.asarray(FACE["anna"]), np.asarray(FACE["ben"])
o = (o - (o @ a) * a) / np.linalg.norm(o - (o @ a) * a)
at = lambda c: list(c * a + np.sqrt(1 - c * c) * o)                      # a face at this cosine to "anna"
assert reid.alike(None, at(0.32), None, FACE["anna"])                     # a weak view of the same person
assert not reid.alike(None, at(0.16), None, FACE["anna"])                # the most alike stranger measured
print("ok: re-identification and greetings")
