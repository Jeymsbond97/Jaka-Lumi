"""Self-check of "look at me": the cameras first (head or torso camera), the voice only chooses among the people seen;
nobody seen -> the head looks around, then a sure voice from behind turns the body. No robot: python tests/test_look_me.py"""
import math

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import lumi

turns, pitches = [], []
lumi.head.turn = lambda yaw, pitch=None: (turns.append(round(yaw)), pitches.append(pitch))
lumi.LOOK_ME_SETTLE_S = 0.0


class Vision:
    def __init__(self, before, after=None):
        self.views = [before, before if after is None else after]

    def seen(self):
        return self.views.pop(0) if len(self.views) > 1 else self.views[0]

    def present(self, t):
        return False

    def head_person(self, angle, since):
        return None

    def near_angle(self, a, max_diff=25.0):
        return None


def look(seen, voice=None, after=None, gaze=0.0):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.vision, L.current = Vision(seen, after), None
    L.voice_angle, L.voice_trusted = (voice or 0.0), voice is not None
    L.det_yaw = lambda: gaze
    turns.clear()
    L.look_at_speaker()
    return list(turns)


# someone on Lumi's right, seen only by the torso camera, no voice direction: the head turns right to them
assert look([(-33.0, 0.78)]) == [-33], turns
# the voice agrees with a person seen: that person, not the nearer one elsewhere
assert look([(-33.0, 1.2), (40.0, 0.6)], voice=-20.0) == [-33], turns
# someone in view, the voice elsewhere: the person seen (the voice read people in front as behind, 2026-10-29)
assert look([(40.0, 0.6)], voice=-55.0) == [40], turns
assert look([(-33.0, 0.78)], voice=50.0) == [-33], turns
# the owner's report: person in front at -22, repeat "look at me" with the voice read at +128 / -122 / +120 behind:
# the head stays on them every time, the base never turns
for v in (128.0, -122.0, 120.0, -120.0):
    assert look([(-22.0, 1.3)], voice=v) == [-22], (v, turns)
# several seen, none at the voice: the one nearest where the head looks, not one on the voice's side
assert look([(-30.0, 1.0), (35.0, 1.0)], voice=150.0, gaze=-25.0) == [-30], turns
# nobody seen: the head looks to the voice's side first, finds the person there
assert look([], voice=-55.0, after=[(-50.0, 0.9)]) == [-60, -50], turns
# nobody seen on that side either: the other side, then back where it looked when nobody is anywhere
assert look([], voice=-55.0) == [-60, 60, 0], turns
# nobody seen, no voice: looks around and back
assert look([], gaze=10.0) == [60, -60, 10], turns

# "Lumi" with the voice read on the left, nobody there: the head turns there, then to the person seen, else back
heads = []
lumi.time.sleep = lambda s: None


class Head(Vision):
    camera = "head"

    def near_angle(self, a, max_diff=25.0):
        return None


for seen, want in (([(-33.0, 0.8)], [50, -33]), ([], [50, 5])):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.vision, L.current = Head(seen), None
    L.det_yaw = lambda: 5.0
    L.turn_head = lambda yaw=None, pitch=None, force=False: heads.append(round(yaw))
    heads.clear()
    assert L.find_caller(50.0, True) is None and heads == want, heads

# a call with the voice read behind (+150) while someone stands in view at -22: no base turn, the head finds them
base = []
lumi.agv.turn_by = lambda rad: base.append(rad)
lumi.waist_turned = lambda: 0.0
L = lumi.Lumi.__new__(lumi.Lumi)
L.vision, L.current = Head([(-22.0, 1.3)]), None
L.modes = type("M", (), {"patrol": True})()
L.det_yaw = lambda: 0.0
L.turn_head = lambda yaw=None, pitch=None, force=False: heads.append(round(yaw))
heads.clear()
L.find_caller(150.0, True)
assert base == [] and heads == [60, -22], (base, heads)

# the pitch follows the person in the head camera (torso camera intrinsics, near the head camera's)
FY, CY, H = 608.4, 363.2, 720
far = lumi.look_me_pitch
assert far([600, 250, 700, 600], H, 0.0, FY, CY) is None                  # far, all of them in view: stays level
# sitting, close: head low, legs cut: down 30 deg, cut to the head's range
assert far([600, 400, 800, 720], H, 0.0, FY, CY) == lumi.head.PITCH_RANGE[0]
p = far([600, 400, 800, 720], H, 30.0, FY, CY)
assert -2 < p < 2, p
assert far([500, 0, 900, 720], H, 0.0, FY, CY) == lumi.LOOK_ME_UP_STEP     # tall, close: head cut, up a step
assert far([500, 0, 900, 720], H, 35.0, FY, CY) is None                   # already at the top of the range
assert far([600, 60, 800, 720], H, 5.0, FY, CY) is None                   # head already near the top


class Camera(Vision):
    """Head camera frames after each turn: the box top moves by the pitch change (fy px per radian)."""
    def __init__(self, top, bottom=720):
        super().__init__([(-30.0, 1.0)])
        self.top, self.bottom, self.pitch = top, bottom, 0.0

    def head_person(self, angle, since):
        if pitches:
            shift = FY * (math.tan(math.radians(pitches[-1] - self.pitch)))
            self.top, self.pitch = self.top + shift, pitches[-1]
        return {"box": [500, max(0, self.top), 900, self.bottom], "height": H, "pitch": self.pitch, "fy": FY, "cy": CY}


def look_pitch(cam):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.vision, L.current, L.voice_angle, L.voice_trusted = cam, None, 0.0, False
    L.det_yaw = lambda: 0.0
    turns.clear(), pitches.clear()
    L.look_at_speaker()
    return [round(p) for p in pitches]


assert look_pitch(Camera(250, 600)) == [0], pitches                      # far: level, no correction
assert look_pitch(Camera(300)) == [0, -5], pitches                       # sitting close: down, to the lowest pitch
assert look_pitch(Camera(100)) == [0, -3], pitches                       # standing close, legs cut: head to the top
p = look_pitch(Camera(-150))                                              # tall close: up until the head shows
assert p[0] == 0 and p[-1] > 10 and len(p) <= 1 + lumi.LOOK_ME_TRIES, p
assert set(turns) == {-30}, turns                                         # the yaw stays on them
print("look me: ok")

# "look at me" from behind with Patrol off: the waist turns in place toward the voice, the head looks on from there
from tasks import fetch
waist = {"at": 0.0, "calls": []}
lumi.waist_turned = lambda: waist["at"]


def fake_waist_to(rel, in_place=False, look=None):
    waist["calls"].append((round(rel), in_place, look))
    waist["at"] = rel
    return True


fetch._waist_to = fake_waist_to
L = lumi.Lumi.__new__(lumi.Lumi)
L.vision, L.current = Vision([]), None
L.voice_angle, L.voice_trusted = 170.0, True
L.det_yaw = lambda: 0.0
L.modes = type("M", (), {"patrol": False})()
turns.clear()
L.look_at_speaker()
assert waist["calls"] == [(120, True, 170.0)], waist
assert turns == [60, -60, 50, 0], turns            # looked around first; 170 - 120 left for the head; nobody: back
assert not L.voice_trusted and L.voice_at == 0.0   # a direction measured before the turn is never used again
print("look me behind: ok")
