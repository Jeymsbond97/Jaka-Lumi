"""Self-check of what Lumi does after a blocked drive (assistant/detour.py, tasks/fetch.detour, lumi.detour): the words
through lumi.route with and without a blocked drive kept (tests/detour_cases.py), the way round, and the runs with a
fake base (never the real one): python tests/test_detour.py"""
import json
import math
import tempfile
import time
from pathlib import Path

from assistant import brain, detour, lumi
from tasks import fetch
from tests.detour_cases import CASES, GOAL, M, PREFIX_EN, PREFIX_KO


def forbid(*a, **k):
    raise AssertionError("a test reached the robot")


refusal = lumi.skills.refusal
for mod in (lumi.agv, lumi.head, lumi.arm, lumi.gripper, lumi.motion, lumi.skills):   # nothing may reach the robot
    for name in dir(mod):
        if not name.startswith("_") and callable(getattr(mod, name)) and not isinstance(getattr(mod, name), type):
            setattr(mod, name, forbid)
lumi.skills.refusal = refusal
lumi.log = fetch.log = lambda *a: None

tmp = Path(tempfile.mkdtemp())
detour.STATE_FILE = tmp / "lumi_stuck.json"            # never the real /dev/shm files
fetch.STATE_FILE = tmp / "lumi_task.json"
fetch.DRIVE_POLL_S = 0.001
START = [1.0, 2.0, 0.0]

# ---------- the words, through lumi.route ----------
from tests.detour_cases2 import CASES as CASES2, PREFIX_EN as PREFIX2_EN, PREFIX_KO as PREFIX2_KO
cases = dict(CASES)
for text, want in CASES.items():
    for p in PREFIX_KO if brain.HANGUL.search(text) else PREFIX_EN:
        cases[p + text] = want
for text, want in CASES2.items():                       # the second set: a tuple is what may be read
    for p in [""] + (PREFIX2_KO if brain.HANGUL.search(text) else PREFIX2_EN):
        cases[p + text] = want
B = brain.Brain()
bad = []
for text, want in cases.items():
    detour.forget()
    without = lumi.route(text, M, B)
    if without[0] == "detour":
        bad.append((text, "detour without a blocked drive", without))
    detour.remember(GOAL, [{"do": "go", "to": GOAL}], START)
    got = lumi.route(text, M, B)
    if want and not (got[0] == "detour" and got[1] in (want if isinstance(want, tuple) else (want,))) or \
            not want and got != without:
        bad.append((text, want, got))
assert not bad, "\n".join(f"{t!r}: want {w}, got {g}" for t, w, g in bad)
n_cases = len(cases)

detour.remember(GOAL, [{"do": "go", "to": GOAL}], START)
assert lumi.route("try again", M, B) == ("detour", "retry")
detour.STATE_FILE.write_text(json.dumps({"goal": GOAL, "rest": [], "start": START, "tries": 0,
                                          "time": time.time() - detour.FRESH_S - 1}))
assert detour.recent() is None and lumi.route("try again", M, B)[0] != "detour"   # an old block means nothing
assert lumi.route("go back", M, B) == ("quick", ("move", "back 1"))                # the short drive back, as always

# ---------- a way round ----------
wall = lambda x, y: 0.2 if y > 0 else 2.0             # something on the left of a drive along +x
p = detour.via((0.0, 0.0, 0.0), (5.0, 0.0), wall)
assert p[1] < 0 and abs(p[0] - detour.VIA_AHEAD_M) < 1e-9, p              # to the right, ahead
assert abs(p[2] - math.atan2(-p[1], 5.0 - p[0])) < 1e-9                    # facing the goal
assert detour.via((0.0, 0.0, 0.0), (5.0, 0.0), lambda x, y: 0.3) is None   # no room anywhere
p = detour.via((0.0, 0.0, math.pi / 2), None, lambda x, y: 1.0 + x)        # goal unknown: along the heading
assert abs(p[1] - detour.VIA_AHEAD_M) < 1e-9 and p[0] > 0, p


# ---------- the runs, with a fake base ----------
class Base:
    """go / go_point start a drive; a goal in `blocked` stays "running" without moving, then the base gives up."""

    def __init__(self):
        self.at, self.blocked, self.goals, self.reads = (0.0, 0.0, 0.0), set(), [], []

    def go(self, marker):
        return self._go(marker, (5.0, 0.0, 0.0))

    def go_point(self, x, y, th):
        return self._go((round(x, 3), round(y, 3), round(th, 3)), (x, y, th))

    def _go(self, name, pose):
        self.goals.append(name)
        self.reads = ["running", "failed"] if name in self.blocked else ["running", "succeeded"]
        self.target = pose
        return True, "OK"

    def status(self):
        st = self.reads.pop(0) if self.reads else "idle"
        if st == "succeeded":
            self.at = self.target
        return {"move_status": st, "current_pose": dict(zip(("x", "y", "theta"), self.at))}


base = Base()
for name, fn in {"go": base.go, "go_point": base.go_point, "status": base.status, "cancel": lambda: "OK",
                 "pose": lambda: base.at, "markers": lambda: M, "marker_xy": lambda m: (5.0, 0.0),
                 "clearance": lambda x, y: 2.0 if y < START[1] else 0.3}.items():
    setattr(fetch.agv, name, fn)
moves, said = [], []
fetch._move = lambda d, m, holding: moves.append((d, m))
for name in ("_drive_pose", "_waist_front", "head_ahead", "_lift_to", "_line_holding"):
    setattr(fetch, name, lambda *a, **k: None)
fetch.skills.moved = lambda: None
fetch.gripper.state = lambda: {"holding": True}
fetch._in_hand = lambda: False
fetch._launch = lambda fn, *a: fn(*a)                  # in this thread: the test reads the end at once
say = lambda en, ko=None: said.append(en)

# a mission blocked on its way to p3: kept with the rest of the mission and where it started
base.at = tuple(START)
base.blocked = {"p3"}
fetch.run_steps([{"do": "go", "to": "p3"}, {"do": "say", "text": "Hi."}, {"do": "go", "to": "here"}], say=say)
st = detour.recent()
assert fetch.state()["status"] == "failed" and said[-1] == fetch.STUCK_SAY[0], (fetch.state(), said)
assert st["goal"] == "p3" and st["start"] == START and st["tries"] == 0, st
assert st["rest"] == [{"do": "go", "to": "p3"}, {"do": "say", "text": "Hi."}, {"do": "go", "to": START}], st["rest"]

# "try again" still blocked: said plainly, the block kept for the next try
fetch.detour(st["rest"], "retry", say=say, tries=1)
assert said[-1] == detour.STILL[0] and detour.recent()["tries"] == 1, said

# "back up a little and try again": the checked move back, then the same drive; the way is free now
base.blocked = set()
base.goals.clear()
fetch.detour(detour.recent()["rest"], "backup", say=say, tries=2)
assert moves == [("back", detour.BACKUP_M)] and base.goals == ["p3", tuple(START)], (moves, base.goals)
assert fetch.state()["status"] == "done" and detour.recent() is None, fetch.state()    # done: nothing kept

# "go around it": a free point to the side first (the left is full here), then the goal
base.at, base.blocked = tuple(START), {"p3"}
fetch.run_steps([{"do": "go", "to": "p3"}], say=say)
base.blocked, base.goals = set(), []
fetch.detour(detour.recent()["rest"], "around", say=say, tries=1)
via = base.goals[0]
assert len(base.goals) == 2 and base.goals[1] == "p3" and via[1] < START[1], base.goals
assert fetch.state()["status"] == "done"

# no room on either side: said, the block kept ("go back" still works)
base.at, base.blocked = tuple(START), {"p3"}
fetch.run_steps([{"do": "go", "to": "p3"}], say=say)
fetch.agv.clearance = lambda x, y: 0.3
fetch.detour(detour.recent()["rest"], "around", say=say, tries=1)
assert said[-1] == detour.NO_WAY_ROUND[0] and detour.recent(), said

# a held cup blocked on its way: the drive and what was to follow it are kept
fetch._in_hand = lambda: True
fetch._place_ok = lambda dest, markers: True
fetch.carry_to({"marker": "p3"}, "place", say=say)
assert detour.recent()["rest"] == [{"do": "go", "to": "p3"}, {"do": "place", "on": None}], detour.recent()
fetch._in_hand = lambda: False
fetch._set(holding=False)

# ---------- lumi: the trip's block kept and said, "go back" and "try again" handed to the runner ----------
said_lumi, runs = [], []
lumi.mouth.say = said_lumi.append
fetch.detour = lambda steps, how, say=None, tries=0: runs.append((steps, how, tries))


class Patrol:
    once, stuck, stuck_why, mode = True, "p3", None, "done"

    def pause(self):
        pass


class Modes:
    patrol, drive = True, True


L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.patrol, L.modes, L.heard, L.brain = "en", Patrol(), Modes(), "try again", brain.Brain()
L.keep_listening = lambda: None
fetch._task["trip_from"] = tuple(START)
detour.forget()
L.say_stuck()
assert said_lumi[-1] == "Sorry, I can't find a way to p3. Something may be blocking the path."
assert detour.recent()["rest"] == [{"do": "go", "to": "p3"}] and detour.recent()["start"] == START
L.patrol.stuck, L.lang = "p3", "ko"
L.say_stuck()
assert said_lumi[-1].startswith("죄송해요, p3(으)로 가는 길을 못 찾겠어요"), said_lumi[-1]
L.lang = "en"

assert L.detour("retry") and runs[-1] == ([{"do": "go", "to": "p3"}], "retry", 1) and said_lumi[-1] == detour.SAY["retry"][0]
assert L.detour("back") and runs[-1] == ([{"do": "go", "to": START}], "back", 0)
n = len(said_lumi)
assert L.detour("around", speak=False) and runs[-1][1] == "around" and len(said_lumi) == n   # the LLM's own words said
L.lang = "ko"
assert L.detour("around") and said_lumi[-1] == detour.SAY["around"][1]
detour.remember("p3", [{"do": "go", "to": "p3"}], None)
assert L.detour("back") and said_lumi[-1] == detour.NO_START[1] and runs[-1][1] == "around"   # no start: asked
L.modes.patrol = False                                                    # Greeter only: no drive
n = len(runs)
assert L.detour("retry") and len(runs) == n
detour.forget()
assert L.detour("retry") is False                                         # nothing blocked: not handled here
print(f"detour ok: {n_cases} wordings through route (EN, KO, mixed), with and without a blocked drive")
