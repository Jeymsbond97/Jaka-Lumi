"""Self-check of "come back" (brain.intent, steps, fetch's trip start, lumi.come_back) with a fake base, no robot:
python tests/test_come_back.py"""
import tempfile
from pathlib import Path

from assistant import brain
from assistant import lumi
from assistant import steps
from tasks import fetch

M = ["home", "p3", "p8", "p10"]

# ---------- the words ----------
CASES = {
    # a distance: a straight move back
    "come back 20 cm": ("move", "back 0.2"), "come back 1 meter": ("move", "back 1"), "20센티 뒤로 와": ("move", "back 0.2"),
    "come back a little": ("move", "back 0.5"), "Let's come back to 20 cm.": ("move", "back 0.2"),
    # a marker
    "come back to p3": ("go_to", "p3"), "return to p3": ("go_to", "p3"), "p3로 돌아와": ("go_to", "p3"),
    "p3으로 돌아와 줘": ("go_to", "p3"), "come back p3": ("go_to", "p3"),
    # the speaker
    "come back here": ("come", ""), "come back to me": ("come", ""), "이리 돌아와": ("come", ""),
    "여기로 돌아와": ("come", ""), "나한테 돌아와": ("come", ""),
    # where Lumi started
    "come back": ("come_back", ""), "Come back.": ("come_back", ""), "come back please": ("come_back", ""),
    "Lumi, come back now": ("come_back", ""), "can you come back?": ("come_back", ""), "return": ("come_back", ""),
    "go back where you were": ("come_back", ""), "go back to where you were before": ("come_back", ""),
    "return to your starting point": ("come_back", ""), "go back to your spot": ("come_back", ""),
    "돌아와": ("come_back", ""), "루미야 돌아와": ("come_back", ""), "다시 돌아와 줘": ("come_back", ""),
    "돌아와요": ("come_back", ""), "돌아가": ("come_back", ""), "원래 자리로 돌아가": ("come_back", ""),
    "원래 있던 곳으로 돌아와": ("come_back", ""), "제자리로 돌아가": ("come_back", ""), "hey lumi 돌아와": ("come_back", ""),
    # talk
    "I'll come back later": None, "come back tomorrow": None, "she will come back": None, "I'll be right back": None,
    "when will you come back?": None, "don't come back": None, "나중에 돌아올게": None, "내일 돌아와": None,
    "언니가 돌아와": None, "my friend will return soon": None, "return the cup": ("put", "back"),
    # bare "go back" stays a short drive back (docs/17 reads it as unclear in a mission)
    "go back": ("move", "back 1"),
}
bad = [(t, brain.intent(t, M), want) for t, want in CASES.items() if brain.intent(t, M) != want]
assert not bad, "\n".join(f"{t!r}: got {g}, want {w}" for t, g, w in bad)

# ---------- in a mission "come back" is where the mission started ("here") ----------
HERE = {"do": "go", "to": "here"}
for text, want in {
        "go to p10, wait 30 seconds and come back": [{"do": "go", "to": "p10"}, {"do": "wait", "s": 30.0}, HERE],
        "go to p10, wait 30 seconds and come back here": [{"do": "go", "to": "p10"}, {"do": "wait", "s": 30.0}, HERE],
        "p10에 가서 30초 기다렸다가 돌아와": [{"do": "go", "to": "p10"}, {"do": "wait", "s": 30.0}, HERE],
        "p10에 가서 30초 기다렸다가 원래 자리로 돌아와": [{"do": "go", "to": "p10"}, {"do": "wait", "s": 30.0}, HERE],
        "go to p3 and return": [{"do": "go", "to": "p3"}, HERE],
        "go to p8, then go back where you were": [{"do": "go", "to": "p8"}, HERE],
        "p3에 갔다가 돌아와": [{"do": "go", "to": "p3"}, HERE]}.items():
    got, unread, _ = steps.read(text, M, llm=False)
    assert (got, unread) == (want, []), (text, got, unread)

# ---------- the start is remembered by trips, tasks and missions, not by short moves ----------
tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"           # never the real /dev/shm file
fetch.CALIB_FILE = tmp / "fetch_calib.json"
pose = [(1.0, 2.0, 0.5)]
fetch.agv.markers = lambda: M
fetch.agv.pose = lambda: pose[0]
fetch._in_hand = lambda: False
fetch._launch = lambda *a: None                     # nothing runs: only the start is checked
fetch._busy = lambda: False

fetch.run_steps([{"do": "move", "dir": "back", "m": 0.2}])
assert fetch._task["trip_from"] is None             # "move back 20 cm" is no trip
fetch.run_steps([{"do": "go", "to": "p10"}, {"do": "wait", "s": 30.0}, HERE])
assert fetch._task["trip_from"] == fetch._task["start_pose"] == (1.0, 2.0, 0.5)
pose[0] = (3.0, 4.0, 0.0)
fetch.run_steps([{"do": "turn", "deg": 90.0}])
assert fetch._task["trip_from"] == (1.0, 2.0, 0.5)  # a turn neither
fetch.start({"object": "cup", "colour": None, "source": "here", "dest": {"marker": "p3"}, "finish": "hold"})
assert fetch._task["trip_from"] == (3.0, 4.0, 0.0)

# ---------- lumi: "go to p8" remembers, "come back" drives there, nothing remembered -> asked ----------
trips, said = [], []


class FakePatrol:
    def __init__(self, route, once=False, pause_s=0.0):
        trips.append(route[0] if len(route) == 1 else route)
        self.mode = "patrol"

    def tick(self, force=False):
        pass

    def pause(self):
        pass


lumi.Patrol = FakePatrol
lumi.mouth.say = said.append
L = lumi.Lumi.__new__(lumi.Lumi)
L.lang, L.patrol = "en", None
L.keep_listening = lambda: None

fetch._task["trip_from"] = None
assert L.come_back(speak=True) is False and said[-1] == "Come back where?" and not trips
L.lang = "ko"
L.come_back(speak=True)
assert said[-1] == "어디로 돌아갈까요?"
L.lang = "en"

pose[0] = (5.0, 6.0, 1.0)
L.start_trip("p8")                                  # "go to p8"
pose[0] = (9.0, 9.0, 0.0)                           # arrived at p8
L.start_trip((9.5, 9.0, 0.0), remember=False)       # a short move there ("move left 0.5")
assert L.come_back(speak=True) and trips[-1] == (5.0, 6.0, 1.0) and said[-1] == "Okay, I'm going back.", (trips, said)
assert fetch._task["trip_from"] == (5.0, 6.0, 1.0)  # going back is no new trip
print("come back ok")
