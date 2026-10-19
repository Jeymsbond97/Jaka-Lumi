"""What Lumi decides for each thing people say to it on a mission (tests/interrupt_cases.py), through the real
assistant/lumi.py mission_talk() with a fake runner: no robot, no audio, no LLM (questions it leaves to the
LLM count as "answer"). python tests/interrupt_check.py  ->  logs/interrupt_check.log"""
import re
import time
from pathlib import Path

from assistant import lumi, steps
from tasks import fetch
from tests.interrupt_cases import SCENARIOS
from tests.test_steps import short

ROOT = Path(__file__).resolve().parents[1]
M = ["home", "PInit", "Wp", "a", "b", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]
done, run, task = [], {"paused": False}, {"steps": []}
fetch.state = lambda: {"status": "running", "task": task, "holding": True}
fetch.pause = lambda: (done.append("pause"), run.update(paused=True), True)[-1]
fetch.paused = lambda: run["paused"]
fetch.resume = lambda: (done.append("resume"), run.update(paused=False))
fetch.stop = lambda: done.append("stop")
fetch.replace = lambda s, say=None: done.append(("replace", s))


def decide(L, text):
    """What happened for one thing said: (decision, what Lumi said)."""
    n_done, n_said = len(done), len(L.said)
    if text == "":                                        # nobody answered "Can I go on?"
        L.last_activity -= 100
        L.mission_wait()
        L.last_activity -= 100
        L.mission_wait()
        handled = True
    else:
        handled = L.mission_talk(text)
        if not handled:                                   # answered as a question; then "may I go on?" (talk_turn)
            if L.mission_hold == "safety":                # still halted; a goodbye does not let it go on
                return ("safety_stop" if lumi.DONE_TALK.search(text) else "answer"), ""
            if L.mission_hold == "talk":
                L.asked_go_on = True
            return "answer", ""
    new, said = done[n_done:], " ".join(L.said[n_said:])
    if any(isinstance(d, tuple) for d in new):
        rep = next(d for d in new if isinstance(d, tuple))[1]
        return ("give_here" if [s["do"] for s in rep] == ["give"] else "change_task"), rep
    if "stop" in new:
        return "cancel", said
    if "resume" in new:
        return "resume", said
    if L.mission_hold == "safety":
        return "safety_stop", said
    if re.search(r"doing a task for someone|this is for|이건 .*가져가는|다른 분의 일|끝나면", said):
        return "refuse_redirect", said
    if re.search(r"How can I help|무엇을 도와|I stopped for you|didn't understand", said):
        return "halt_talk", said
    if not new and not said:
        return "ignored", said
    return "other", said


def main():
    bad, total, t0 = [], 0, time.time()
    for sc in SCENARIOS:
        task["steps"], unread, _ = steps.read(sc["mission"], M, llm=False)
        task["sender"] = steps.sender(sc["mission"])
        L = lumi.Lumi.__new__(lumi.Lumi)
        L.markers, L.lang, L.current, L.mission_hold, L.asked_go_on = M, "en", None, None, False
        L.lang = "ko" if re.search(r"[가-힣]", sc["mission"]) else "en"
        L.last_activity, L.said = time.time(), []
        L.fetch_say = lambda en, ko, L=L: L.said.append(en if L.lang == "en" else ko)
        L.keep_listening = lambda: None
        done.clear()
        run["paused"] = False
        for t in sc["turns"]:
            total += 1
            if t["expect"] == "ask_language":              # the recogniser's language check answers it, not this
                continue
            got, said = decide(L, t["say"])
            want = t["expect"]
            ok = got == want or (want, got) in {("halt_talk", "answer"), ("answer", "halt_talk")}
            if want == "change_task" and t.get("new_steps") == "?":   # a change Lumi can't read: it asks
                ok = got in ("halt_talk", "other")
            elif ok and want == "change_task" and "new_steps" in t:
                ok = said == [short(x.strip()) for x in t["new_steps"].split(" | ")]
            if not ok:
                bad.append(f"{sc['mission']!r} [{t['who']}] {t['say']!r}\n  want {want} {t.get('new_steps', '')}\n"
                           f"  got  {got} {said}")
    (ROOT / "logs" / "interrupt_check.log").write_text("\n".join(bad) + "\n")
    print(f"{total - len(bad)}/{total} turns right ({time.time() - t0:.1f} s); failures in logs/interrupt_check.log")


if __name__ == "__main__":
    main()
