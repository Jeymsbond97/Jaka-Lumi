"""Self-check: every task the dashboard starts (Command box: mission, fetch, carry, give, place, a command for the
assistant) obeys the Greeter / Patrol switches as voice does (api/server.py _switches): both off nothing, Greeter
only in place (no base, no waist), Patrol everything; "stop" always. Fake switches, fake runner, nothing reaches the
robot: python tests/test_task_switches.py"""
import json
import tempfile
from pathlib import Path

from fastapi import HTTPException

from api import server
from tasks import fetch


def forbid(*a, **k):
    raise AssertionError("a test reached the robot")


M = ["home", "p1", "p3"]
tmp = Path(tempfile.mkdtemp())
server.MODES_FILE = tmp / "lumi_modes.json"          # never the real /dev/shm files
fetch.STATE_FILE = tmp / "lumi_task.json"
server.agv.request = server.agv.cancel = server.skills.cancel = server.arm.cmd = forbid
server.agv.markers = lambda: M
fetch.check_hand = lambda: False
fetch.log = lambda *a: None
done = []
server.send_to_assistant = lambda cmd, **a: done.append(cmd)
for name in ("start", "run_steps", "carry_to", "give", "place"):          # the runner in the API process
    setattr(fetch, name, lambda *a, _n=name, **k: done.append(_n))
running = [12345]
server.assistant_pids = lambda: list(running)

PLACE = [{"do": "pick", "object": "cup", "colour": None}, {"do": "arm", "pose": "open"}]
DRIVE = [{"do": "go", "to": "p3"}, {"do": "pick", "object": "cup", "colour": None}]
TASKS = {   # name: (start it, drives or turns the base / waist)
    "mission in place": (lambda: server.steps_run(server.StepsBody(steps=PLACE)), False),
    "mission driving": (lambda: server.steps_run(server.StepsBody(steps=DRIVE)), True),
    "mission turning": (lambda: server.steps_run(server.StepsBody(steps=[{"do": "turn", "deg": 90.0}])), True),
    "fetch here": (lambda: server.task_fetch(server.TaskBody(object="cup", dest="here")), False),
    "fetch from p1": (lambda: server.task_fetch(server.TaskBody(object="cup", source={"marker": "p1"}, dest="here")),
                      True),
    "fetch to p3": (lambda: server.task_fetch(server.TaskBody(object="cup", dest={"marker": "p3"})), True),
    "carry": (lambda: server.task_carry(server.CarryBody(dest={"marker": "p3"})), True),
    "give": (server.task_give, False),
    "place": (lambda: server.task_place(None), False),
    "command look": (lambda: server.task_command(server.CommandBody(text="look left")), False),
    "command lift": (lambda: server.task_command(server.CommandBody(text="lift up")), False),
    "command follow": (lambda: server.task_command(server.CommandBody(text="follow me")), True),
    "command come": (lambda: server.task_command(server.CommandBody(text="이리 와")), True),
    "command chain": (lambda: server.task_command(server.CommandBody(text="look at me and come here")), True),
    "command go": (lambda: server.task_command(server.CommandBody(text="go to p3")), True),   # steps sent as text
}


def start(fn):
    done.clear()
    try:
        fn()
    except HTTPException as e:
        assert e.status_code == 409 and not done, (e.detail, done)
        return e.detail
    assert done, "accepted but nothing started"
    return None


for greeter, patrol in ((False, False), (True, False), (False, True), (True, True)):
    server.MODES_FILE.write_text(json.dumps({"greeter": greeter, "patrol": patrol}))
    for assistant in (True, False):
        running[:] = [12345] if assistant else []
        for name, (fn, base) in TASKS.items():
            if name.startswith("command") and not assistant:
                continue                                     # a command is done by the assistant only
            got = start(fn)
            want = server.SWITCHES_OFF if not (greeter or patrol) else server.BASE_OFF if base and not patrol else None
            assert got == want, (name, greeter, patrol, assistant, got)
            if got is None:
                assert fetch.stay_put == (not patrol), (name, fetch.stay_put)

# "stop" typed with both off still stops (never the switches)
server.MODES_FILE.write_text(json.dumps({"greeter": False, "patrol": False}))
running[:] = []
stopped = []
server._fetch_stop = lambda: stopped.append("task")
server.agv.cancel = lambda: stopped.append("base")
server.skills.cancel = lambda: stopped.append("arm")
server.task_command(server.CommandBody(text="stop"))
assert stopped == ["task", "base", "arm"], stopped
print("task switches ok")
