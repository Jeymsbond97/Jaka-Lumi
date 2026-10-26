"""The live sequence of 2026-10-23 15:21-15:23, replayed with fakes: "give me a hand" / handshake words with an empty
hand are arm reach (the rules, not the LLM's "I can't shake hands"), and a reach whose body move hangs ends at once on
STOP, so the next "give me your hand" starts instead of "I'm busy with another task". No robot.

    .venv/bin/python tests/test_reach_live.py
"""
import tempfile
import threading
import time
from pathlib import Path

from assistant import brain
from tasks import fetch

MARKERS = ["home", "p1"]
REACH = ["Let's give me a hand.", "Let's give me your hand.", "Give me your hand.", "give me a hand", "손 줘",
         "손 내밀어", "루미야 손 줘", "Lumi, 손 줘", "hand 줘", "손 좀 줘", "shake hands with me", "let's shake hands",
         "shake my hand", "give me a handshake", "악수하자", "악수해 줘", "나랑 악수할래?"]
NOT_REACH = ["give me a hand with this", "can you lend me a hand?", "give me a hand to lift this", "I shook hands with him",
             "don't shake hands", "악수하지 마", "어제 악수했어", "the handshake was nice", "give me a break"]

bad = [(t, brain.intent(t, MARKERS)) for t in REACH if brain.intent(t, MARKERS) != ("arm", "reach")]
bad += [(t, brain.intent(t, MARKERS)) for t in NOT_REACH if brain.intent(t, MARKERS) == ("arm", "reach")]
bad += [(t, "held rule") for t in REACH if brain.hand_request(t, False, None, MARKERS)]   # empty hand: never a give
assert not bad, bad

# ---------- the stuck reach: the body API does not answer a head move ----------
tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"
hung = threading.Event()                         # never set: the body API's moveto hangs
fetch.head.moveto = lambda pos, **kw: hung.wait(30)
fetch.head.status = lambda: [0.0, 0.0, -22.0, 0.0]
fetch.camview.want = lambda name: None
fetch.skills.cancel = fetch.agv.cancel = lambda: None
fetch.motion.poses = lambda: {"give": [0] * 6, "look": [0] * 6}
fetch.head_ahead = lambda: None
moved = []
fetch._turn = lambda deg, **kw: (fetch._head_to(-30.0, 0.0), True)[1]   # the turn's head check (head_hits) hangs
fetch._pose = lambda name: moved.append(name)
fetch._person_point = lambda: ((0.0, 600.0, 0.0), 100.0)
fetch._reach_to_hand = lambda *a: moved.append("hand")

fetch.reach(-22.7)
time.sleep(0.3)
assert fetch._busy() and fetch.state()["status"] == "running"
try:
    fetch.reach(-22.0)                            # said again while it really runs: busy is right
    raise AssertionError("a second reach started")
except fetch.FetchError as e:
    assert "busy" in e.args[0]
t = time.time()
fetch.end()                                       # "stop" / a new command
assert time.time() - t < 1.0 and not fetch._busy(), "stop waited for the hung body call"
assert fetch.state()["status"] == "stopped" and moved == []

hung.set()                                        # the body answers again
fetch.reach(0.0)                                  # the next "give me your hand": starts, not "busy"
fetch._thread.join(2)
assert moved == ["give", "hand"] and fetch.state()["status"] == "done", (moved, fetch.state()["status"])
print(f"reach live ok ({len(REACH) + len(NOT_REACH)} wordings, stop during a hung body move)")
