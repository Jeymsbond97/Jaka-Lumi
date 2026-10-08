"""Lumi robot API: HTTP endpoints for the base, head, arm, voice and the lumi.py assistant, with Swagger at /docs.

    python api.py                 # http://<thor>:8100/docs  (robot network: http://192.168.10.240:8100/docs)

Started at boot by a crontab @reboot line (see README.md), so nothing has to be run by hand.
While the assistant (lumi.py) is running it owns the robot: motion and speech endpoints answer 409.
/status, /agv/markers and the log always work.
"""
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV_PY = HERE / ".venv" / "bin" / "python"
if VENV_PY.exists() and Path(sys.prefix).resolve() != (HERE / ".venv").resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve())] + sys.argv[1:])

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

import agv
import arm
import head

PORT = 8100
LUMI_LOG = HERE / "lumi.log"                 # written by lumi.py itself
CONSOLE_LOG = HERE / "lumi_console.log"      # lumi.py stdout/stderr when started from here (tracebacks)

app = FastAPI(title="Lumi robot API", version="0.1.0",
              description="Base (AGV), head, arm, voice and the greeter/patrol assistant of our JAKA Lumi. "
                          "Motion endpoints really move the robot.")
_brain = None
_voice_lock = threading.Lock()


# ---------- helpers ----------
def assistant_pids():
    """PIDs of running lumi.py processes (started from here or from a terminal)."""
    out = subprocess.run(["pgrep", "-f", f"{HERE}/lumi.py|python3? lumi.py"], capture_output=True, text=True).stdout
    return [int(p) for p in out.split() if int(p) != os.getpid()]


def robot_free():
    if assistant_pids():
        raise HTTPException(409, "The assistant (lumi.py) is running and owns the robot. POST /assistant/stop first.")


def tail(path, n):
    try:
        return path.read_text(errors="replace").splitlines()[-n:]
    except FileNotFoundError:
        return []


def part(fn):
    """Run one status read; an unreachable device gives {"error": ...} instead of failing the whole call."""
    try:
        return fn()
    except Exception as e:
        return {"error": str(e)}


# ---------- request bodies ----------
class GoBody(BaseModel):
    marker: str = Field(examples=["aisle_a"], description='Marker name; "home" = the charging dock')


class HeadBody(BaseModel):
    yaw: float = Field(0, ge=-60, le=60, description="deg, clamped to +-60")
    pitch: float | None = Field(None, ge=-5, le=35, description="deg; empty = keep the current pitch")


class BodyBody(BaseModel):
    lift_mm: float | None = Field(None, ge=0, le=300, examples=[150], description="lifting column, 0 = lowest")
    waist_deg: float | None = Field(None, ge=-140, le=140, description="waist rotation")
    head_yaw_deg: float | None = Field(None, ge=-60, le=60)
    head_pitch_deg: float | None = Field(None, ge=-5, le=35)
    speed: float = Field(15, ge=1, le=50, description="speed ratio %, slow by default")


class SayBody(BaseModel):
    text: str = Field(examples=["안녕하세요, 저는 루미예요."], description="English or Korean (Hangul = Korean)")


class AskBody(BaseModel):
    question: str = Field(examples=["What can you do?"])
    speak: bool = Field(True, description="also say the answer on the robot's speaker")


class StartBody(BaseModel):
    patrol: str | None = Field(None, examples=["p1,p2,p3,p4,p5,p6,p7,p8,final,p9,p10,home"],
                               description="markers to drive through; empty = stay at the current place")
    once: bool = Field(True, description="drive the route once (true) or loop it forever (false)")
    pause: float = Field(1.0, ge=0, le=60, description="seconds to wait at each marker")
    no_arm: bool = False
    no_drive: bool = False


# ---------- status ----------
@app.get("/status", tags=["status"], summary="Battery, position, base / head / arm state, assistant")
def status():
    def base():
        s = agv.status()
        return {k: s.get(k) for k in ("power_percent", "charge_state", "current_pose", "move_status", "move_target",
                                       "running_status", "error_code", "estop_state", "is_paused")}

    def body():
        return dict(zip(["lift_mm", "waist_deg", "head_yaw_deg", "head_pitch_deg"],
                        (round(p, 2) for p in head.status())))

    def arm_state():
        r = arm.cmd("get_robot_state")
        return {"power": bool(r.get("power")), "enable": bool(r.get("enable")), "program": arm.program_state()}

    return {"base": part(base), "body": part(body), "arm": part(arm_state),
            "assistant": {"running": bool(assistant_pids()), "pids": assistant_pids()}}


# ---------- base ----------
@app.get("/agv/markers", tags=["base"], summary="Markers on the current map")
def markers():
    return {"markers": agv.markers()}


@app.post("/agv/go", tags=["base"], summary="Drive to a marker (returns at once; watch /status move_status)")
def go(body: GoBody):
    robot_free()
    names = agv.markers()
    if body.marker not in names:
        raise HTTPException(400, f"unknown marker {body.marker!r}; markers: {names}")
    ok, msg = agv.go(body.marker)
    if not ok:
        raise HTTPException(502, f"AGV refused: {msg}")
    return {"ok": True, "marker": body.marker}


@app.post("/agv/cancel", tags=["base"], summary="Stop the current drive")
def cancel():
    return {"status": agv.cancel()}


# ---------- head / arm ----------
@app.post("/head/turn", tags=["body"], summary="Turn the head (slow); waits until the move ends")
def head_turn(body: HeadBody):
    robot_free()
    head.turn(body.yaw, body.pitch)
    return {"body": dict(zip(["lift_mm", "waist_deg", "head_yaw_deg", "head_pitch_deg"],
                             (round(p, 2) for p in head.status())))}


@app.post("/body/move", tags=["body"], summary="Lift / waist / head (slow); empty fields keep their value")
def body_move(body: BodyBody):
    robot_free()
    cur = head.status()
    target = [cur[i] if v is None else v
              for i, v in enumerate((body.lift_mm, body.waist_deg, body.head_yaw_deg, body.head_pitch_deg))]
    reply = head._call("moveto", {"pos": target, "vel": body.speed, "acc": 20}, timeout=60)
    return {"reply": reply, "body": dict(zip(["lift_mm", "waist_deg", "head_yaw_deg", "head_pitch_deg"],
                                             (round(p, 2) for p in head.status())))}


@app.post("/arm/wave", tags=["arm"], summary="Wave (Cobo π program hand_shaking.jks); returns at once")
def arm_wave():
    robot_free()
    if not arm.ready():
        raise HTTPException(409, "arm not ready: power/enable off, or a program is running")
    arm.start()
    return {"ok": True, "program": arm.WAVE}


@app.post("/arm/stop", tags=["arm"], summary="Stop the running arm program")
def arm_stop():
    return arm.stop()


# ---------- voice ----------
@app.post("/say", tags=["voice"], summary="Lumi says the text on its speaker; returns when finished")
def say(body: SayBody):
    robot_free()
    import mouth
    with _voice_lock:
        t = time.time()
        mouth.say(body.text)
    return {"ok": True, "seconds": round(time.time() - t, 1)}


@app.post("/ask", tags=["voice"], summary="Ask Lumi a question (knowledge base + LLM), optionally spoken")
def ask(body: AskBody):
    global _brain
    if body.speak:
        robot_free()
    from brain import Brain
    _brain = _brain or Brain()
    t = time.time()
    reply, hits = _brain.answer(body.question)
    took = round(time.time() - t, 1)
    if body.speak:
        import mouth
        with _voice_lock:
            mouth.say(reply)
    return {"answer": reply, "llm_seconds": took, "sources": [src for _, src, _ in hits]}


# ---------- assistant (lumi.py) ----------
@app.post("/assistant/start", tags=["assistant"], summary="Start lumi.py (greeter + conversation, optional patrol)")
def assistant_start(body: StartBody):
    if assistant_pids():
        raise HTTPException(409, "already running")
    args = [str(VENV_PY), str(HERE / "lumi.py")]
    if body.patrol:
        names = agv.markers()
        unknown = [m for m in body.patrol.split(",") if m not in names]
        if unknown:
            raise HTTPException(400, f"unknown markers {unknown}; markers: {names}")
        args += ["--patrol", body.patrol, "--pause", str(body.pause)] + ["--once"] * body.once
    args += ["--no-arm"] * body.no_arm + ["--no-drive"] * body.no_drive
    log = open(CONSOLE_LOG, "a")
    log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start: {' '.join(args[1:])}\n")
    log.flush()
    p = subprocess.Popen(args, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         start_new_session=True)
    return {"ok": True, "pid": p.pid, "args": args[2:]}


@app.post("/assistant/stop", tags=["assistant"], summary="Stop lumi.py and the base")
def assistant_stop():
    pids = assistant_pids()
    for pid in pids:
        os.kill(pid, signal.SIGINT)                  # lumi.py exits at once on Ctrl+C
    time.sleep(1.0)
    for pid in assistant_pids():
        os.kill(pid, signal.SIGKILL)
    part(agv.cancel)                                 # a patrol drive would otherwise go on to its marker
    part(arm.stop)
    return {"stopped": pids}


@app.get("/assistant/log", tags=["assistant"], summary="Last lines of lumi.log (and errors from the console)")
def assistant_log(lines: int = 50):
    return {"lumi_log": tail(LUMI_LOG, lines), "console": tail(CONSOLE_LOG, 15)}


@app.get("/health", tags=["status"])
def health():
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
