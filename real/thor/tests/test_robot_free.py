"""Self-check of the dashboard's hand controls (api/server.py robot_free): refused while a task, a skill, following,
a wave or a drive runs; allowed when idle or paused, Patrol on or off; STOP always works. Fake state, no robot:
python tests/test_robot_free.py"""
import json
import tempfile
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from fastapi import HTTPException

from api import server
from tasks import fetch

tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"           # never the real /dev/shm files
server.BUSY_FILE = tmp / "lumi_busy.json"
server.MODES_FILE = tmp / "lumi_modes.json"
base = {"move_status": "idle"}
server.agv.request = lambda cmd, timeout=3.0: {"results": dict(base)}
held = []
server.jogger.hold = lambda *a: held.append(a)
server.gripper.open_ = server.gripper.close = lambda: {"ok": True}
server.assistant_pids = lambda: [12345]             # lumi.py "runs"


def task(status, paused=False):
    fetch.STATE_FILE.write_text(json.dumps({"status": status, "paused": paused}))


def refused(fn, *a):
    try:
        fn(*a)
    except HTTPException as e:
        assert e.status_code == 409 and e.detail == server.BUSY_MSG, e.detail
        return True
    return False


JOG = server.JogBody(axis="head_yaw", direction=1)
manual = (lambda: server.jog(JOG), server.gripper_open, server.gripper_close)

# idle, Patrol on: allowed
server.MODES_FILE.write_text(json.dumps({"greeter": True, "patrol": True}))
task("idle")
server.BUSY_FILE.write_text(json.dumps({"busy": None}))
assert not any(refused(f) for f in manual)
task("holding")
assert not refused(manual[0])

# a task or mission running: refused; paused: allowed
for status in ("running", "waiting"):
    task(status)
    assert all(refused(f) for f in manual), status
    task(status, paused=True)
    assert not any(refused(f) for f in manual), status

# a running file whose runner died (no lumi.py, not this process) does not lock the controls
task("running")
server.assistant_pids = lambda: []
assert not refused(manual[0])
server.assistant_pids = lambda: [12345]
task("idle")

# lumi.py follows / waves / drives / runs a skill: refused
for what in ("follow", "wave", "drive", "skill"):
    server.BUSY_FILE.write_text(json.dumps({"busy": what}))
    assert refused(manual[0]), what
server.BUSY_FILE.write_text(json.dumps({"busy": None}))

# a drive to a marker (by the API or anyone): refused; the base unreachable: not busy
base["move_status"] = "running"
assert refused(manual[0])
base["move_status"] = "succeeded"
assert not refused(manual[0])
server.agv.request = lambda *a, **k: (_ for _ in ()).throw(OSError("no route"))
assert not refused(manual[0])

# non-manual robot calls still need lumi.py stopped
try:
    server.robot_free()
    raise AssertionError("robot_free() allowed while lumi.py runs")
except HTTPException as e:
    assert e.status_code == 409 and "assistant" in e.detail

# STOP works while a task runs
task("running")
calls = []
server.jogger.stop = lambda: calls.append("jog")
server._route.stop = lambda: calls.append("route")
server._fetch_stop = lambda: calls.append("fetch")
server.assistant_stop = lambda: {"stopped": []}
server.send_to_assistant = lambda *a, **k: calls.append(a[0])
server.agv.cancel = lambda: calls.append("agv")
server.skills.cancel = lambda: calls.append("arm")
server.stop_all()
server.task_stop()
server.jog_stop()
server.arm_stop()
assert {"jog", "route", "fetch", "agv", "arm", "fetch_stop"} <= set(calls), calls
assert len(held) == 7, held                         # the jogs that were allowed reached the (fake) jogger
print("robot_free: ok")
