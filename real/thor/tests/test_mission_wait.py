"""Self-check of what Lumi does with words said while a mission waits (docs/17 §4: an instruction from the person at
the place, "go on", "okay" while receiving) and of the status answer; no robot, no audio:
python tests/test_mission_wait.py"""
import time

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import lumi
from assistant import steps
from tasks import fetch

steps._ollama = lambda messages, fmt: (_ for _ in ()).throw(OSError("no LLM in this test"))

M = ["home", "exit"] + [f"p{i}" for i in range(1, 11)]
MISSION = [{"do": "go", "to": "p6"}, {"do": "wait", "s": 300.0, "until": "instruction"}, {"do": "go", "to": "home"}]
done, st = [], {}
fetch.state = lambda: st
fetch.pause = lambda: (done.append("pause"), True)[-1]
fetch.paused = lambda: "pause" in done and "resume" not in done
fetch.resume = lambda: done.append("resume")
fetch.stop = lambda: done.append("stop")
fetch.end = lambda timeout=5.0: done.append("end")
fetch.proceed = lambda: done.append("proceed")
fetch.release_now = lambda: done.append("release")
fetch.instruct = lambda steps: done.append(("instruct", steps))
fetch.replace = lambda steps, say=None: done.append(("replace", steps))
fetch.held_name = lambda: "the cup"


def fresh(waiting, step="waiting at p6", answers=()):
    st.clear()
    st.update(status="running", task={"steps": MISSION}, holding=False, step=step, waiting=waiting)
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.markers, L.lang, L.current, L.mission_hold, L.asked_go_on = M, "en", None, None, False
    L.last_activity, L.said, L.patrol = time.time(), [], None
    L.fetch_say = lambda en, ko: L.said.append(en)
    L.keep_listening = lambda: None
    heard = list(answers)
    L.hear = lambda wait_s: (heard.pop(0), True) if heard else (None, True)
    done.clear()
    return L


ORDER = {"at": "p6", "for": "instruction", "end": time.time() + 200}
# the person at the place gives the instruction: read back, a spoken yes, then given to the runner
L = fresh(ORDER, answers=["yes"])
assert L.mission_talk("take the cup and bring it to p2")
assert done[-2:] == [("instruct", [{"do": "pick", "object": "cup", "colour": None}, {"do": "go", "to": "p2"}]), "resume"], done
assert "Is that right?" in L.said[0], L.said
L = fresh(ORDER, answers=["no"])                                    # no: nothing given, still waiting
assert L.mission_talk("go to p2") and not any(isinstance(d, tuple) for d in done), done
L = fresh(ORDER)                                                    # said without the wake word: still to Lumi
assert L.mission_talk("p3로 가서 안녕하세요라고 말해") and "Is that right?" in L.said[0], L.said
L = fresh(ORDER)
assert L.mission_talk("go to the kitchen and dance") and "didn't understand" in L.said[-1], L.said
L = fresh(ORDER)
assert not L.mission_talk("what are you doing?")                     # a question: answered as usual
assert L.now_doing()[0] == "I'm waiting at p6 for an instruction.", L.now_doing()
# a mission waiting for go on / a time: anyone's new task ends it with one line (then it is done); "go on" ends the wait
for w in ({"at": "exit", "for": "go on", "end": None}, {"at": "p3", "for": "time", "end": time.time() + 25}):
    L = fresh(w)
    assert L.mission_talk("Lumi, take me to p2") is False and "end" in done and "stopped my task" in L.said[-1], L.said
    L = fresh(w)
    assert L.mission_talk("okay, you can go now") and "proceed" in done and done[-1] == "resume", done
L = fresh({"at": "exit", "for": "go on", "end": None}, step="waiting at exit")
assert L.now_doing()[0] == "I'm waiting at exit until someone tells me to go on.", L.now_doing()
L = fresh({"at": "p3", "for": "time", "end": time.time() + 25.4}, step="waiting at p3")
assert L.now_doing()[0] == "I'm waiting at p3, 25 seconds left.", L.now_doing()
assert L.now_doing()[1] == "p3에서 기다리고 있어요. 25초 남았어요.", L.now_doing()
L = fresh({"at": "p9", "for": "person", "object": "cup", "end": time.time() + 200}, step="receiving")
assert L.now_doing()[0] == "I'm waiting at p9 for someone to give me the cup.", L.now_doing()
# the mission ended with "stay there": waiting, not running (a new command is taken as usual)
L = fresh({"at": "p3", "for": "stay", "end": None})
st["status"] = "waiting"
assert not L.mission_running() and L.now_doing()[0] == "I'm waiting at p3.", L.now_doing()
# receiving on a mission: "okay" closes the hand even when nobody talked to Lumi before
L = fresh(None, step="receiving: waiting for okay")
assert L.mission_talk("okay") and done == ["release"], done
L = fresh(None, step="giving")
assert L.mission_talk("thank you") and done == ["release"], done
L = fresh(None, step="driving to p6")
assert L.mission_talk("okay") and done == [], done                  # not to me: ignored
print("mission wait ok")
