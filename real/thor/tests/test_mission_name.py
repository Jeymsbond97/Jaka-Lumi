"""Self-check of the owner's live test of 2026-10-27 (logs/lumi.log 10:45-11:19), no robot, no audio, no LLM:
python tests/test_mission_name.py
1. While a mission picks / places / carries, only words with Lumi's name halt it ("Lumi, wait", "루미 멈춰"); talk
   around it ("네, 안녕하세요.", "Very nice.", "Okay.") neither halts nor resumes it. Stop words and safety words from
   anyone still stop at once. "Lumi, keep going" / "루미 계속해" after a stop does the rest of the job.
2. "Lumi stop, not the apple, take the cup": stopped, then the new order is done. Holding after a stop: put it back /
   on the table / down again, at every speech level, English and Korean.
3. The dashboard's Command box: "come to me" reads back as "Come to me." and, typed, comes to the person in view."""
import re
import threading
import time

re._MAXCACHE = 100000

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import lumi
from tasks import fetch

M = ["home", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]
TAKE = [{"do": "pick", "object": "cup", "colour": None}]                       # the dashboard's "Take the cup"
DELIVERY = TAKE + [{"do": "go", "to": "p6"}, {"do": "give", "person": "James"}]
done = []
run = {"status": "running", "paused": False, "steps": TAKE, "log": [], "holding": False, "since": time.time()}


def _stop():
    done.append("stop")
    run.update(status="stopped", since=time.time())


fetch.state = lambda: {"status": run["status"], "task": {"steps": run["steps"], "sender": None}, "log": run["log"],
                       "holding": run["holding"], "since": run["since"]}
fetch.pause = lambda: (done.append("pause"), run.update(paused=True), True)[-1] if run["status"] == "running" else False
fetch.paused = lambda: run["paused"]
fetch.resume = lambda: (done.append("resume"), run.update(paused=False))
fetch.stop = _stop
fetch.end = lambda timeout=5.0: (done.append("end"), run.update(status="stopped"))
fetch.replace = lambda steps, say=None: done.append(("replace", steps))
fetch.proceed = lambda: done.append("proceed")
fetch.run_steps = lambda steps, say=None, sender=None: done.append(("run", steps))
fetch.check_hand = lambda: run["holding"]
fetch.held_name = lambda lang="en": "the cup" if lang == "en" else "컵"
lumi.agv.cancel = lambda: done.append("agv cancel")
lumi.mouth.say = lambda text, **k: done.append(("say", text))


class Track:
    def __init__(self, tid):
        self.id, self.person, self.angle, self.distance, self.greeted = tid, None, -9.0, 2.35, False


class Brain:
    history = []


def fresh(steps=TAKE, current=None, holding=False, log=()):
    L = lumi.Lumi.__new__(lumi.Lumi)
    L.markers, L.lang, L.current, L.mission_hold, L.asked_go_on = M, "en", current, None, False
    L.patrol, L.chain_stop, L.brain, L.pending_text = None, threading.Event(), Brain(), None
    L.last_activity, L.said = time.time(), []
    L.fetch_say = lambda en, ko: L.said.append(en)
    L.keep_listening = lambda: None
    L.act = lambda action, target: done.append(("act", action))
    L.head_rest = lambda: None
    done.clear()
    run.update(status="running", paused=False, steps=steps, log=list(log), holding=holding, since=time.time())
    return L


bad = []


def check(ok, what):
    if not ok:
        bad.append(what)
        print("WRONG", what)


# ---------- 1. talk around Lumi on a pick: never halts it, never resumes it ----------
for current in (None, Track(97)):
    L = fresh(current=current)
    L.last_talk = time.time()                               # someone talked a moment ago (10:56:01 "네.")
    for said in ("네, 안녕하세요.", "네.", "Very nice.", "Okay.", "네, 네, 네, 네, 네.", "hello", "hi there", "excuse me",
                 "sorry", "what are you doing?", "그렇죠.", "I'm Tom.", "the robot is slow", "로봇 신기하다", "hey"):
        L.mission_talk(said)
        check(not done and not L.said, f"plain talk {said!r} halted or answered: {done} {L.said}")
    for said in ("come to me", "give me that", "go to p3"):    # an order without the name: not to Lumi on a job
        L.mission_talk(said)
        check("end" not in done and "pause" not in done, f"{said!r} without the name ended the job: {done}")
# said to Lumi by name: halts it
for said in ("Lumi, wait", "Hi Lumi!", "루미야 잠깐", "루미야, 뭐 해?", "Lumi, what are you doing?", "hey Lumi"):
    L = fresh()
    L.mission_talk(said)
    check(done[:1] == ["pause"], f"{said!r} did not halt it: {done}")
# stop and safety words from anyone, with or without the name: at once, as before
for said in ("stop", "Stop it.", "멈춰", "그만", "Lumi, stop", "루미 멈춰", "stop Lumi"):
    L = fresh()
    check(L.mission_talk(said) and "stop" in done, f"{said!r} did not stop it: {done}")
for said in ("watch out!", "아파", "my hand!", "위험해"):
    L = fresh()
    check(L.mission_talk(said) and "pause" in done and L.mission_hold == "safety", f"{said!r} no safety halt: {done}")
# halted by name, then "Lumi, keep going" at every level: goes on
GO_EN = ["Lumi, keep going", "Lumi, go on", "Lumi, continue", "Lumi, carry on", "okay Lumi, you can go on",
         "Lumi, keep going please", "Lumi, resume", "Lumi, finish the job"]
GO_KO = ["루미 계속해", "루미야 계속해", "루미야 계속해요", "루미야 계속하세요", "루미야 계속하십시오", "루미야 계속해 줘",
         "루미야 계속해 주세요", "루미 계속 진행해", "루미야 하던 거 계속해", "루미야 마저 해", "루미야 마저 하세요"]
for said in GO_EN + GO_KO:
    L = fresh()
    L.mission_talk("Lumi, wait")
    check(L.mission_talk(said) and done[-1] == "resume", f"{said!r} did not go on: {done}")

# ---------- 1b. "Lumi, stop", then "Lumi, keep going": the rest of the job is done ----------
for said in GO_EN + GO_KO:
    for steps_, log_, holding, want in ((TAKE, ["10:46:01 step 1/1: {'do': 'pick'}"], False, TAKE),
                                        (DELIVERY, ["step 1/3: pick", "step 2/3: go"], True, DELIVERY[1:]),
                                        (DELIVERY, ["step 1/3: pick"], True,                  # held: lifted, then on
                                         [{"do": "carry"}] + DELIVERY[1:]),
                                        (DELIVERY, ["step 1/3: pick"], False, DELIVERY)):
        L = fresh(steps_, holding=holding, log=log_)
        L.mission_talk("Lumi, stop")
        check(not L.mission_running() and L.resume_stopped(said) and done[-1] == ("run", want),
              f"stop, then {said!r} ({log_[-1]}, holding {holding}): {done[-1]} not {want}")
L = fresh(TAKE, holding=True, log=["step 1/1: pick"])         # "take the cup" stopped with the cup in the hand
L.mission_talk("Lumi, stop")
check(L.resume_stopped("Lumi, keep going") and done[-1] == ("run", [{"do": "carry"}])
      and "the cup" in L.said[-1], f"held, nothing left: lifted to look, then asked: {done} {L.said}")
for said in ("keep going", "계속해", "Lumi, keep going?", "did you keep going, Lumi?"):   # no name, or a question
    L = fresh(DELIVERY, log=["step 1/3: pick"])
    L.mission_talk("stop")
    check(not L.resume_stopped(said), f"{said!r} after a stop restarted the job")
L = fresh(log=["step 1/1: pick"])                                 # long after the stop: not taken
L.mission_talk("Lumi, stop")
L.stopped_mission = L.stopped_mission[:2] + (time.time() - lumi.RESUME_S - 1,)
check(not L.resume_stopped("Lumi, keep going"), "keep going long after the stop restarted the job")

# ---------- 2. a stop with a new order after it: stopped, then the new order ----------
for said, want in (("Lumi stop, not the apple, take the cup", ("pick", "cup")),
                   ("Lumi, stop. Take the cup instead.", ("pick", "cup")),
                   ("루미 멈춰, 사과 말고 컵 집어", ("pick", "cup")),
                   ("루미야 멈춰 그거 말고 컵 집어 주세요", ("pick", "cup")),
                   ("stop Lumi, put it back", ("put", "back")),
                   ("루미 멈춰, 제자리에 놔", ("put", "back"))):
    L = fresh(log=["step 1/1: pick"])
    check(L.mission_talk(said) and "stop" in done and "end" in done and L.pending_text, f"{said!r}: {done} {L.pending_text!r}")
    got = lumi.route(L.pending_text or "", M, Brain(), holding=False, chain_ok=False)
    check(got == ("quick", want), f"{said!r}: then {L.pending_text!r} read {got}, not {want}")
    check(L.stopped_mission is None, f"{said!r}: the old job is still kept to go on with")
for said in ("Stop it.", "Lumi, stop!", "stop, stop", "루미야 멈춰 주세요", "stop, where are you going?",
             "Lumi, stop, you're going to hit the table", "stop, don't take the cup"):   # nothing to do after it
    L = fresh()
    L.mission_talk(said)
    check(not L.pending_text, f"{said!r}: {L.pending_text!r} taken as an order after the stop")

# holding after a stop: put it back / on the table / down again, every level, English and Korean
EN_LEVELS = ["{x}", "please {x}", "{x}, please", "can you {x}?", "could you {x}?", "would you {x}?", "will you {x}?",
             "could you please {x}?", "I need you to {x}", "hey Lumi, {x}", "Lumi, {x} now", "go ahead and {x}", "kindly {x}",
             "if you don't mind, {x}", "do me a favor and {x}", "{x} pls", "Lumi could you {x}"]


def ko_levels(v, h):
    return [v, f"{v} 줘", f"{v}요", f"{v} 주세요", f"{h}세요", f"{h}십시오", f"{v} 주십시오", f"{v} 주시겠어요?",
            f"{v} 주시겠습니까?", f"{v} 줄래?", f"{v} 주실래요?", f"{v} 주게", f"{v} 주이소", f"{v} 도", f"{v} 주라",
            f"{v} 주시면 감사하겠습니다", f"{v} 주면 안 될까요?", f"{v} 주실 수 있나요?", f"{v}줘", f"{v} 줘 봐", f"{v} 주시오"]


def put_down(text):
    kind, data = lumi.route(text, M, Brain(), holding=True, chain_ok=False)
    return kind == "quick" and data[:2] == ("put", "back") or kind == "hand" and data[0][0] == "place"


HELD = [f.format(x=x) for x in ("put it back", "put it on the table", "put it down again", "put it down") for f in EN_LEVELS]
HELD += [w.format(f) for w, v, h in (("제자리에 {}", "놔", "놓으"), ("다시 {}", "놔", "놓으"), ("테이블에 {}", "놔", "놓으"),
                                     ("다시 {}", "내려놔", "내려놓으"), ("원래 자리에 {}", "갖다 놔", "갖다 놓으"))
         for f in ko_levels(v, h)]
for text in HELD:
    check(put_down(text), f"holding: {text!r} does not put it down")
check(lumi.route("take the apple", M, Brain(), holding=False, chain_ok=False) == ("quick", ("pick", "apple")),
      "then another thing is not taken")

# ---------- 3. the Command box: "come to me" ----------
from api import server
server.agv.markers = lambda: M
for text, want in (("come to me", "Come to me."), ("이리 와", "Come to me."), ("follow me", "Follow me.")):
    got = server.task_parse(server.ParseBody(text=text))
    check(got["sentence"] == want and got["action"] == "command", f"box {text!r}: {got['sentence']!r}")
# typed: no voice this turn, so the person in view is the one (11:18:02: a stale voice direction, nobody found)
came = []
L = fresh()
run.update(status="idle", steps=[])
L.voice_angle, L.voice_trusted, L.current = 60.0, True, None    # the last voice, long ago, from the side


class Vision:
    camera = "head"
    tracks = [Track(97)]
    lock = threading.Lock()

    def present(self, t):
        return t in self.tracks

    def near_angle(self, angle, max_diff=20):
        return next((t for t in self.tracks if abs(t.angle - angle) <= max_diff), None)

    def only_person(self):
        return self.tracks[0]


L.vision = Vision()
L.turn_head = lambda yaw: None
L.come_to = lambda track, say=False: came.append(track if track is not None else L.find_caller(L.voice_angle, L.voice_trusted))
L.answer = lambda text: L.come_to(L.current, say=True)
L.typed("come to me")
check(came and came[0] is not None and came[0].id == 97, f"typed come to me: came to {came}")
check(lumi.ears.understood(), "typed words taken as not understood (11:22:46 'look at front': 'say it again')")

L = fresh()                                                       # typed in the box on a job: to Lumi
L.answer = lambda text: L.mission_talk(text)
L.typed("come to me")
check("end" in done, f"typed 'come to me' on a job was ignored: {done}")

if bad:
    raise SystemExit(f"{len(bad)} wrong")
print(f"mission name ok ({len(HELD)} held commands)")
