"""Self-check of stop words, questions and new commands on a running or paused mission, replaying the owner's live
test of 2026-10-22 16:56-16:59 (logs/lumi_console.log) in order; fake mission runner, nothing reaches the robot:
python tests/test_mission_stop.py"""
import json
import os
import tempfile
import threading
import time

from assistant import lumi
from tasks import fetch

M = ["home", "dock2"] + [f"p{i}" for i in range(1, 11)]
BACK = [{"do": "move", "dir": "back", "m": 1.0}]
DELIVERY = [{"do": "pick", "object": "cup", "colour": None}, {"do": "go", "to": "p6"}, {"do": "give", "person": "James"}]
done, run = [], {"status": "running", "paused": False, "steps": BACK}


def _stop():
    done.append("stop")
    run["status"] = "stopped"


fetch.state = lambda: {"status": run["status"], "task": {"steps": run["steps"]}, "holding": False}
fetch.pause = lambda: (done.append("pause"), run.update(paused=True), True)[-1] if run["status"] == "running" else False
fetch.paused = lambda: run["paused"]
fetch.resume = lambda: (done.append("resume"), run.update(paused=False))
fetch.stop = _stop
fetch.end = lambda timeout=5.0: (done.append("end"), run.update(status="stopped"))
fetch.replace = lambda steps, say=None: done.append(("replace", steps))
fetch.proceed = lambda: done.append("proceed")
lumi.agv.cancel = lambda: done.append("agv cancel")
lumi.mouth.say = lambda text, **k: done.append(("say", text))


class Track:                                       # a vision track: the id changes, the re-id person stays
    def __init__(self, tid, person):
        self.id, self.person = tid, person


OWNER, OTHER = object(), object()                  # reid.Person stand-ins: who it is makes no difference


def fresh(steps=BACK, paused=False, hold=None, current=None):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.markers, L.lang, L.current, L.mission_hold, L.asked_go_on = M, "en", current, hold, False
    L.patrol, L.chain_stop = None, threading.Event()
    L.last_activity, L.said = time.time(), []
    L.fetch_say = lambda en, ko: L.said.append(en)
    L.keep_listening = lambda: None
    L.act = lambda action, target: done.append(("act", action))       # stop_all's motion stop: not to the robot
    done.clear()
    run.update(status="running", paused=paused, steps=steps)
    return L


def halted(L):                                     # the mission paused for a talk, as at 16:56:07 on the old code
    run["paused"], L.mission_hold = True, "talk"
    return L


# 16:56:07 "Stop it." while the 1 m drive back runs: stopped and ended at once, not paused
L = fresh(current=Track(21, OWNER))
assert L.mission_talk("Stop it.") and "stop" in done and "pause" not in done, done
assert run["status"] == "stopped" and L.mission_hold is None and L.said[-1] == "Okay, I stopped.", (run, L.said)
for word in ("stop", "Okay, stop it.", "enough", "that's enough", "그만", "멈춰", "정지", "그만해"):   # running or paused
    for p in (False, True):
        L = fresh(paused=p, hold="talk" if p else None)
        assert L.mission_talk(word) and "stop" in done and "resume" not in done, (word, p, done)
        assert not L.mission_running(), word
# no mission (a fetch, follow, a song, the arm): the same words are a stop order (route -> stop_all, fetch.stop)
for word in ("Stop it.", "Okay, stop it.", "stop", "그만", "멈춰", "정지"):
    assert lumi.stop_order(word, M), word
# 16:56:52 "What is my hand?" (same person #21) on the paused mission: a question, answered as usual
for q in ("What is my hand?", "What is it my hand?", "내 손에 뭐 있어?"):
    L = halted(fresh(current=Track(21, OWNER)))
    assert L.mission_talk(q) is False and not any("doing a task" in s for s in L.said), (q, L.said)
    assert "stop" not in done and "end" not in done, (q, done)
# 16:57:02 "Okay, stop it." after "Can I go on with my task?": ended, never "going on"
L = halted(fresh(current=Track(21, OWNER)))
L.asked_go_on = True
assert L.mission_talk("Okay, stop it.") and "stop" in done and "resume" not in done, done
# 16:57:09 "Okay." on a paused mission: not a go-on
L = halted(fresh(current=Track(21, OWNER)))
L.mission_talk("Okay.")
assert "resume" not in done, done
# only an explicit go-on resumes it
for go in ("go on", "continue", "계속해"):
    L = halted(fresh())
    assert L.mission_talk(go) and done[-1] == "resume", (go, done)
# silence while paused: asked once, never goes on by itself (16:59:36 "no answer - going on with the mission")
L = halted(fresh())
for _ in range(3):
    L.last_activity -= 100
    L.mission_wait()
assert "resume" not in done and L.said.count("Can I go on with my task?") == 1, (done, L.said)
# 16:58:25 / 16:58:41 "Let's follow me." from #27 (the owner again, a new track): the paused mission is ended
# with one line, the command then taken as usual
L = halted(fresh(current=Track(27, OWNER)))
assert L.mission_talk("Let's follow me.") is False and "end" in done, done
assert L.said == ["Okay, I've stopped my task."] and not L.mission_running(), L.said
# 16:58:59 "Come to me." by voice only (nobody in view) on a paused mission: also taken
L = halted(fresh(current=None))
assert L.mission_talk("Come to me.") is False and "end" in done, done
# the same person on a new track while it runs: taken
L = fresh(current=Track(24, OWNER))
assert L.mission_talk("Lumi, come to me") is False and "end" in done, done
# anyone else, while it runs or paused, also on a delivery for James: the task ends with one line, the command is done
for steps_, p in ((BACK, False), (BACK, True), (DELIVERY, False), (DELIVERY, True)):
    L = fresh(steps_, current=Track(30, OTHER))
    if p:
        halted(L)
    assert L.mission_talk("Lumi, take me to p2") is False and "end" in done, (steps_, p, done)
    assert L.said == ["Okay, I've stopped my task."] and not any("doing a task" in x for x in L.said), L.said
# 16:59:07 dashboard cancel on the paused mission: it ends (it went on again at 16:59:39)
L = halted(fresh())
L.cmd_id = 0
fd, lumi.CMD_FILE = tempfile.mkstemp(suffix=".json")
with os.fdopen(fd, "w") as f:
    json.dump({"id": 1, "time": time.time(), "cmd": "cancel"}, f)
L.poll_commands()
os.remove(lumi.CMD_FILE)
assert "stop" in done and run["status"] == "stopped" and L.mission_hold is None, done


# 16:56:38 "One more." right after "look left": further left; also "a bit more", "더", after a lift
class Brain:
    def __init__(self, last):
        self.history = [("before", last)]


looked = []
for said, last, want in (("One more.", "ACTION: look left\nOkay, I am looking to the left.", ("look", "left small")),
                         ("a bit more", "ACTION: look right\nOkay.", ("look", "right small")),
                         ("조금 더", "ACTION: look up\n네.", ("look", "up small")),
                         ("one more", "ACTION: look left small", ("look", "left small")),
                         ("again", "ACTION: lift up\nOkay.", ("lift", "up small"))):
    for paused in (False, True):
        if paused and want[0] == "lift":
            continue                               # the lift is not moved on a mission
        L = halted(fresh()) if paused else fresh()
        if not paused:
            run["status"] = "idle"
        L.brain = Brain(last)
        L.look = lambda target: looked.append(("look", target))
        L.lift = lambda target: looked.append(("lift", target)) and False
        looked.clear()
        assert L.drive_words(said) and looked == [want], (said, paused, looked)
print("mission stop ok")
