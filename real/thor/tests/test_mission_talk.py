"""Self-check of what Lumi does when people talk to it on a mission (docs/17 §6), no robot, no audio:
python tests/test_mission_talk.py"""
import time

from assistant import lumi
from tasks import fetch

M = ["home", "final", "dock2"] + [f"p{i}" for i in range(1, 11)]
MISSION = [{"do": "pick", "object": "cup", "colour": None}, {"do": "go", "to": "p6"}, {"do": "give", "person": "James"}]
done = []
run = {"paused": False}
fetch.state = lambda: {"status": "running", "task": {"steps": MISSION}, "holding": True}
fetch.pause = lambda: (done.append("pause"), run.update(paused=True), True)[-1]
fetch.paused = lambda: run["paused"]
fetch.resume = lambda: (done.append("resume"), run.update(paused=False))
fetch.stop = lambda: done.append("stop")
fetch.replace = lambda steps, say=None: done.append(("replace", steps))
lumi.brain_mod.intent.__globals__  # the real rules


def fresh():
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.markers, L.lang, L.current, L.mission_hold, L.asked_go_on = M, "en", None, None, False
    L.last_activity, L.said = time.time(), []
    L.fetch_say = lambda en, ko: L.said.append(en)
    L.keep_listening = lambda: None
    done.clear()
    run["paused"] = False
    return L


def talk(L, text):
    return L.mission_talk(text), (L.said[-1] if L.said else "")


L = fresh()
assert talk(L, "the weather is nice today")[0] and not done and not L.said          # not to me: ignored, drives on
L = fresh()
ok, said = talk(L, "Hi Lumi!")
assert ok and done == ["pause"] and "How can I help you" in said, (done, said)
ok, said = talk(L, "go to p3")                                                        # a stranger's task: refused
assert ok and "doing a task for someone" in said and not any(isinstance(d, tuple) for d in done), said
ok, said = talk(L, "what are you doing?")                                              # a question: answered as usual
assert not ok
ok, said = talk(L, "okay, you can go")
assert ok and done[-1] == "resume" and L.mission_hold is None, done
L = fresh()
ok, said = talk(L, "Lumi, I'm James, give it to me")                                  # the person it is for
assert ok and done[-1] == ("replace", [{"do": "give", "person": "James"}]) and "James" in said, (done, said)
L = fresh()
ok, said = talk(L, "Lumi, I'm Tom, give it to me")
assert ok and "this is for James" in said and not any(isinstance(d, tuple) for d in done), (done, said)
L = fresh()
ok, said = talk(L, "Hey Lumi, I'm James. Take it to p3 and put it on the table")
assert ok and done[-1] == ("replace", [{"do": "go", "to": "p3"}, {"do": "place", "on": {"name": "dining table",
                                                                                        "colour": None, "side": None}}]), done
L = fresh()
ok, said = talk(L, "Lumi, I'm James, I don't need it, cancel it")
assert ok and done[-1] == "stop", done
L = fresh()
ok, said = talk(L, "watch out!")                                                      # safety: never goes on by itself
assert ok and L.mission_hold == "safety" and "Tell me when I can go on" in said
L.last_activity -= 100
L.mission_wait(); L.mission_wait()
assert "resume" not in done, done
ok, said = talk(L, "you can go now")
assert done[-1] == "resume"
L = fresh()
talk(L, "Lumi, wait")                                                                 # halted for a talk, then silence
L.last_activity -= 100
L.mission_wait()
assert L.said[-1] == "Can I go on with my task?" and "resume" not in done
L.last_activity -= 100
L.mission_wait()
assert done[-1] == "resume", done
L = fresh()
talk(L, "Lumi, stop")
ok, said = talk(L, "can you take me to p2?")
assert "doing a task for someone" in said, said
L = fresh()
ok, said = talk(L, "루미야, 제가 제임스예요")            # 제임스 is not matched to "James" (another script): nothing given
assert not any(isinstance(d, tuple) for d in done) and "this is for James" not in said, (done, said)
print("mission talk ok")
