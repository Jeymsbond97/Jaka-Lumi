"""Lumi robot API: HTTP endpoints for the base, head, arm, voice and the lumi.py assistant, with Swagger at /docs.

    python api/server.py                 # http://<thor>:8100/docs  (robot network: http://192.168.10.240:8100/docs)
                                  # live cameras: http://192.168.10.240:8100/view

Started at boot by a crontab @reboot line (see README.md), so nothing has to be run by hand.
While the assistant (lumi.py) is running it owns the robot: motion and speech endpoints answer 409.
/status, /agv/markers and the log always work.
"""
import json
import math
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # the project folder
VENV_PY = ROOT / ".venv" / "bin" / "python"
if VENV_PY.exists() and Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve())] + sys.argv[1:])

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

from robot import agv
from robot import arm
from vision import camview
from robot import gripper
from robot import motion
from vision import objects
from robot import head
from manipulation import arm_route
from manipulation import skills
from manipulation import wave
from api.control import jogger

PORT = 8100
LUMI_LOG = ROOT / "logs" / "lumi.log"                 # written by lumi.py itself
CONSOLE_LOG = ROOT / "logs" / "lumi_console.log"      # lumi.py stdout/stderr when started from here (tracebacks)
API_LOG = ROOT / "logs" / "api.log"                   # this server's output (lumi-api.service): tasks, arm, errors
ERROR_RE = re.compile(r"\b(error|failed|stuck|refused|cannot|traceback|stopped)\b|E-stop pressed|not answering",
                      re.I)                          # whole words only

app = FastAPI(title="Lumi robot API", version="0.1.0",
              description="Base (AGV), head, arm, voice and the greeter/patrol assistant of our Lumi. "
                          "Motion endpoints really move the robot.")
_brain = None
_voice_lock = threading.Lock()
CAMERA_NAMES = ("head", "torso")
DASHBOARD = ROOT / "api" / "dashboard.html"


# ---------- helpers ----------
def assistant_pids():
    """PIDs of running lumi.py processes (started from here or from a terminal)."""
    out = subprocess.run(["pgrep", "-f", "assistant/lumi[.]py"], capture_output=True, text=True).stdout
    return [int(p) for p in out.split() if int(p) != os.getpid()]


# ---------- the assistant's live modes and commands (see lumi.py) ----------
MODES_FILE = Path("/dev/shm/lumi_modes.json")
CMD_FILE = Path("/dev/shm/lumi_cmd.json")
CALIB_FILE = Path("/dev/shm/lumi_calib.json")
DEFAULT_MODES = {"greeter": False, "patrol": False, "wave": True, "drive": True}


def read_modes():
    try:
        return {**DEFAULT_MODES, **json.loads(MODES_FILE.read_text())}
    except (FileNotFoundError, ValueError):
        return dict(DEFAULT_MODES)


def send_to_assistant(cmd, **args):
    """lumi.py runs and owns the robot: it drives (and stops for people with patrol mode on)."""
    tmp = CMD_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({"id": time.time_ns(), "time": time.time(), "cmd": cmd, **args}))
    os.replace(tmp, CMD_FILE)


def start_assistant(no_arm=False, no_drive=False):
    if assistant_pids():
        return None
    args = [str(VENV_PY), str(ROOT / "assistant" / "lumi.py")] + ["--no-arm"] * no_arm + ["--no-drive"] * no_drive
    log = open(CONSOLE_LOG, "a")
    log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start: {' '.join(args[1:])}\n")
    log.flush()
    return subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            start_new_session=True).pid


BUSY_FILE = Path("/dev/shm/lumi_busy.json")    # written by lumi.py: {"busy": skill | follow | drive | wave | null}
BUSY_MSG = "Busy with a task. Pause or stop it first."
_waving = threading.Event()                     # /arm/wave runs here
_posing = threading.Event()                     # /arm/pose runs here


def running_now():
    """What the robot is doing now (a task or mission, a skill, following, a wave, a drive), None when idle. A
    paused task does not count."""
    from tasks import fetch
    lumi = assistant_pids()
    st = fetch.state()
    if st.get("status") in ("running", "waiting") and not st.get("paused") and (lumi or fetch._busy()):
        return "task"                           # (lumi or _busy: the file of a runner that died does not count)
    if _skill["thread"] and _skill["thread"].is_alive():
        return "skill"
    if _route.thread and _route.thread.is_alive():
        return "route"
    if _waving.is_set():
        return "wave"
    if _posing.is_set():
        return "arm"
    if lumi:
        try:
            what = json.loads(BUSY_FILE.read_text()).get("busy")
            if what:
                return what
        except (FileNotFoundError, ValueError):
            pass
    try:                                        # a drive to a marker / point / dock, by anyone
        if agv.request("/api/robot_status", timeout=0.5)["results"].get("move_status") == "running":
            return "drive"
    except Exception:
        pass
    return None


def robot_free(manual=False):
    """manual: a hand control on the dashboard (jog, lift, waist, head, arm buttons and poses, gripper): refused while
    something runs (running_now), allowed when idle or paused, Greeter / Patrol on or off. Anything else is refused
    while the assistant runs (it owns the robot). STOP never asks here."""
    if manual:
        if running_now():
            raise HTTPException(409, BUSY_MSG)
    elif assistant_pids():
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


# A hung or switched-off controller (2026-10-15) made /status take ~20 s: every arm read waits for ARP to give up
# and is retried. The reads now run side by side and /status answers within this time with "no reply" for the rest.
STATUS_DEADLINE_S = 2.5
_status_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="status")
_status_reads = {}                  # part name -> its read, reused while it is still running (no pile-up of threads)
_status_lock = threading.Lock()


def parts(**fns):
    """Run status reads in parallel; one that has not answered within STATUS_DEADLINE_S reads as {"error": ...}."""
    with _status_lock:
        for name, fn in fns.items():
            f = _status_reads.get(name)
            if f is None or f.done():
                _status_reads[name] = _status_pool.submit(part, fn)
        futures = {name: _status_reads[name] for name in fns}
    done, _ = wait(futures.values(), timeout=STATUS_DEADLINE_S)
    return {name: f.result() if f in done else {"error": f"no reply within {STATUS_DEADLINE_S} s"}
            for name, f in futures.items()}


# ---------- request bodies ----------
class GoBody(BaseModel):
    marker: str = Field(examples=["aisle_a"], description='Marker name; "home" = the charging dock')


class HeadBody(BaseModel):
    yaw: float = Field(0, ge=-180, le=180, description="deg")
    pitch: float | None = Field(None, ge=-5, le=35, description="deg; empty = keep the current pitch")


class BodyBody(BaseModel):
    lift_mm: float | None = Field(None, ge=0, le=head.LIFT_MAX_MM, examples=[75], description="lifting column, 0 = lowest")
    waist_deg: float | None = Field(None, ge=-140, le=140, description="waist rotation")
    head_yaw_deg: float | None = Field(None, ge=-180, le=180)
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

    return {**parts(base=base, body=body, arm=arm_state),
            "assistant": {"running": bool(assistant_pids()), "pids": assistant_pids()}}


# ---------- base ----------
@app.get("/agv/markers", tags=["base"], summary="Markers on the current map")
def markers():
    return {"markers": agv.markers()}


def fetch_head_ahead():
    from tasks import fetch
    fetch.head_ahead()                            # drives look ahead, wherever the head was turned


@app.post("/agv/go", tags=["base"], summary="Drive to a marker (returns at once; watch /status move_status)")
def go(body: GoBody):
    _route.stop()
    names = agv.markers()
    if body.marker not in names:
        raise HTTPException(400, f"unknown marker {body.marker!r}; markers: {names}")
    if assistant_pids():
        send_to_assistant("go", marker=body.marker)
        return {"ok": True, "marker": body.marker, "by": "assistant"}
    part(fetch_head_ahead)
    ok, msg = agv.go(body.marker)
    if not ok:
        raise HTTPException(502, f"AGV refused: {msg}")
    return {"ok": True, "marker": body.marker}


# ---------- several markers in a row ----------
class RouteBody(BaseModel):
    markers: list[str] = Field(examples=[["p1", "p3", "home"]], min_length=1)
    pause: float = Field(1.0, ge=0, le=60, description="seconds to wait at each marker")


class RouteRunner:
    """Drives marker after marker when the assistant is not running (it does this itself when it runs)."""

    def __init__(self):
        self.thread, self.stop_flag, self.state = None, threading.Event(), {}

    def start(self, markers, pause):
        self.stop()
        self.stop_flag = threading.Event()
        self.state = {"route": markers, "index": 0, "status": "starting"}
        self.thread = threading.Thread(target=self._run, args=(markers, pause, self.stop_flag), daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_flag.set()

    def _run(self, markers, pause, stop):
        for i, m in enumerate(markers):
            if stop.is_set():
                break
            self.state.update(index=i, status=f"driving to {m}")
            ok, msg = agv.go(m)
            if not ok:
                self.state["status"] = f"{m}: AGV refused ({msg})"
                return
            time.sleep(1.0)
            while not stop.is_set():
                ms = (part(agv.status) or {}).get("move_status")
                if ms != "running":
                    break
                time.sleep(0.5)
            if stop.is_set():
                break
            if ms != "succeeded":
                self.state["status"] = f"{m}: {ms}"
                return
            stop.wait(pause)
        self.state["status"] = "cancelled" if stop.is_set() else "done"


_route = RouteRunner()


@app.post("/agv/route", tags=["base"], summary="Drive through several markers in order (once)")
def go_route(body: RouteBody):
    names = agv.markers()
    unknown = [m for m in body.markers if m not in names]
    if unknown:
        raise HTTPException(400, f"unknown markers {unknown}; markers: {names}")
    if assistant_pids():
        send_to_assistant("route", markers=body.markers, pause=body.pause)
        return {"ok": True, "route": body.markers, "by": "assistant"}
    _route.start(body.markers, body.pause)
    return {"ok": True, "route": body.markers, "by": "api"}


@app.get("/agv/route", tags=["base"], summary="Progress of the last route driven by the API")
def route_state():
    return _route.state

@app.post("/agv/cancel", tags=["base"], summary="Stop the current drive")
def cancel():
    _route.stop()
    if assistant_pids():
        send_to_assistant("cancel")
    return {"status": agv.cancel()}


# ---------- head / arm ----------
@app.post("/head/turn", tags=["body"], summary="Turn the head (slow); waits until the move ends")
def head_turn(body: HeadBody):
    robot_free(manual=True)
    lift, waist, _, pitch = head.status()
    head.moveto([lift, waist, body.yaw, pitch if body.pitch is None else body.pitch])   # +-180, not head.turn's YAW_LIMIT
    return {"body": dict(zip(["lift_mm", "waist_deg", "head_yaw_deg", "head_pitch_deg"],
                             (round(p, 2) for p in head.status())))}


@app.post("/body/move", tags=["body"], summary="Lift / waist / head (slow); empty fields keep their value")
def body_move(body: BodyBody):
    robot_free(manual=True)
    cur = head.status()
    target = [cur[i] if v is None else v
              for i, v in enumerate((body.lift_mm, body.waist_deg, body.head_yaw_deg, body.head_pitch_deg))]
    reply = head.moveto(target, body.speed, 20, timeout=60)
    return {"reply": reply, "body": dict(zip(["lift_mm", "waist_deg", "head_yaw_deg", "head_pitch_deg"],
                                             (round(p, 2) for p in head.status())))}


@app.post("/arm/wave", tags=["arm"], summary="Wave, checked first (manipulation/wave.py): look -> wave_out -> "
                                            "wave_start, the swings, stays at wave_start")
def arm_wave():
    robot_free(manual=True)
    _waving.set()
    try:
        wave.wave()
    except wave.WaveError as e:
        raise HTTPException(409, e.args[0])
    except motion.MotionError as e:
        raise HTTPException(409, str(e))
    finally:
        _waving.clear()
    return {"ok": True}


@app.post("/arm/stop", tags=["arm"], summary="Stop the running arm program, motion or skill")
def arm_stop():
    return skills.cancel()


# ---------- voice ----------
@app.post("/say", tags=["voice"], summary="Lumi says the text on its speaker; returns when finished")
def say(body: SayBody):
    robot_free()
    from audio import mouth
    with _voice_lock:
        t = time.time()
        mouth.say(body.text)
    return {"ok": True, "seconds": round(time.time() - t, 1)}


@app.post("/ask", tags=["voice"], summary="Ask Lumi a question (knowledge base + LLM), optionally spoken")
def ask(body: AskBody):
    global _brain
    if body.speak:
        robot_free()
    from assistant.brain import Brain
    _brain = _brain or Brain()
    t = time.time()
    reply, hits = _brain.answer(body.question)
    took = round(time.time() - t, 1)
    if body.speak:
        from audio import mouth
        with _voice_lock:
            mouth.say(reply)
    return {"answer": reply, "llm_seconds": took, "sources": [src for _, src, _ in hits]}


# ---------- assistant (lumi.py) ----------
@app.post("/assistant/start", tags=["assistant"], summary="Start lumi.py (greeter + conversation, optional patrol)")
def assistant_start(body: StartBody):
    if assistant_pids():
        raise HTTPException(409, "already running")
    args = [str(VENV_PY), str(ROOT / "assistant" / "lumi.py")]
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
    p = subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
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


@app.get("/logs/robot", tags=["assistant"], summary="Last lines of this server's log (fetch tasks, arm, base, errors "
         "and tracebacks) and the errors among the last 400")
def robot_log(lines: int = 50):
    recent = tail(API_LOG, 400)
    return {"lines": [l[:300] for l in recent[-lines:]], "errors": [l[:200] for l in recent if ERROR_RE.search(l)][-15:]}


# ---------- live cameras and the dashboard ----------
class ViewSettings(BaseModel):
    box_color: str | None = Field(None, pattern=r"^#[0-9a-fA-F]{6}$", examples=["#22c55e"])
    thickness: int | None = Field(None, ge=1, le=6)
    boxes: bool | None = None
    labels: bool | None = None


def _camera_name(name):
    if name not in CAMERA_NAMES:
        raise HTTPException(404, f"camera must be one of {CAMERA_NAMES}")
    return name


@app.get("/", include_in_schema=False)
@app.get("/view", tags=["cameras"], summary="Dashboard: both cameras live + robot controls (open in a browser)",
         response_class=HTMLResponse)
def view():
    return DASHBOARD.read_text()


@app.get("/camera/{name}.mjpg", tags=["cameras"], summary="Live MJPEG stream of one camera (head / torso)")
def camera_stream(name: str):
    name = _camera_name(name)

    def frames():
        last = 0.0
        while True:
            camview.want(name)                           # full speed while someone watches
            path = camview.frame_path(name)
            try:
                mtime = path.stat().st_mtime
                if mtime != last:
                    last = mtime
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + path.read_bytes() + b"\r\n"
            except FileNotFoundError:
                pass
            time.sleep(0.05)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/camera/stream", tags=["cameras"],
         summary="Live video of both cameras in ONE connection: camera JPEGs at full rate + detections")
def camera_stream_all(max_fps: float = 15.0):
    """Binary records: 1 byte camera (0 head, 1 torso), 1 byte kind (0 JPEG, 1 detections JSON),
    4 bytes length (big endian), payload. The dashboard draws the boxes itself, so the video is not slowed
    down by person detection."""
    import struct
    names = list(CAMERA_NAMES)
    camview.ensure_running()

    def records():
        seen, last_want, gap = {}, 0.0, 1.0 / max(1.0, max_fps)
        sent = {n: 0.0 for n in names}
        while True:
            now = time.time()
            if now - last_want > 1.0:
                last_want = now
                for n in names:
                    camview.want(n)
            for i, n in enumerate(names):
                for kind, path in ((0, camview.raw_path(n)), (1, camview.det_path(n))):
                    try:
                        m = path.stat().st_mtime
                    except FileNotFoundError:
                        continue
                    if seen.get((n, kind)) == m or (kind == 0 and now - sent[n] < gap):
                        continue
                    seen[(n, kind)] = m
                    data = path.read_bytes()
                    if kind == 1:                        # only what the dashboard draws
                        try:
                            d = json.loads(data)
                            data = json.dumps({"w": d["width"], "h": d["height"], "people": [
                                {k: p.get(k) for k in ("box", "distance_m", "angle_deg", "focus", "near")}
                                for p in d["people"]], "objects": [
                                {k: o.get(k) for k in ("box", "name", "colour", "width_mm", "position_mm")}
                                for o in d.get("objects", [])]}).encode()
                        except (ValueError, KeyError):
                            continue
                    else:
                        sent[n] = now
                    yield struct.pack(">BBI", i, kind, len(data)) + data
            time.sleep(0.01)

    return StreamingResponse(records(), media_type="application/octet-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.get("/camera/{name}/latest.jpg", tags=["cameras"], summary="Latest picture right away (the dashboard polls this)")
def camera_latest(name: str):
    name = _camera_name(name)
    camview.want(name)                                   # full speed while someone watches
    camview.ensure_running()
    try:
        return Response(camview.frame_path(name).read_bytes(), media_type="image/jpeg",
                        headers={"Cache-Control": "no-store"})
    except FileNotFoundError:
        raise HTTPException(404, "no picture yet")


@app.get("/camera/{name}.jpg", tags=["cameras"], summary="Latest picture of one camera")
def camera_snapshot(name: str):
    name = _camera_name(name)
    camview.ensure_running()
    for _ in range(50):                                  # up to 5 s for a fresh picture
        camview.want(name)
        age = camview.picture_age(name)
        if age is not None and age < camview.FRESH_S:
            return Response(camview.frame_path(name).read_bytes(), media_type="image/jpeg")
        time.sleep(0.1)
    raise HTTPException(503, _camera_error(name) or "no picture from this camera yet")


@app.get("/camera/{name}/info", tags=["cameras"], summary="Who has the camera and the people it sees")
def camera_info(name: str):
    name = _camera_name(name)
    try:
        info = json.loads(camview.info_path(name).read_text())
    except (FileNotFoundError, ValueError):
        info = {"time": 0, "source": None, "people": []}
    info["age_s"] = round(time.time() - info["time"], 1) if info["time"] else None
    info["error"] = _camera_error(name)
    return info


def _camera_error(name):
    if not camview.service_pid():
        return "camera service not running"
    st = camview.status().get("cameras", {}).get(name)
    return None if st in (None, "ok") else st


@app.get("/view/settings", tags=["cameras"], summary="How person boxes are drawn")
def view_settings():
    return camview.settings()


@app.post("/view/settings", tags=["cameras"], summary="Change box colour / thickness, show boxes / labels")
def view_settings_set(body: ViewSettings):
    return camview.save_settings(body.model_dump())


class VolumeBody(BaseModel):
    percent: int = Field(55, ge=0, le=100)


@app.get("/volume", tags=["voice"], summary="Speaker volume (%)")
def volume_get():
    from audio import mouth
    return {"percent": mouth.volume()}


@app.post("/volume", tags=["voice"], summary="Set the speaker volume (%); kept for every program")
def volume_set(body: VolumeBody):
    from audio import mouth
    mouth.set_volume(body.percent)
    return {"percent": mouth.volume()}

@app.post("/stop", tags=["status"], summary="STOP everything: base drive, arm program and the assistant")
def stop_all():
    jogger.stop()
    _route.stop()
    task = part(_fetch_stop)                         # first, so the runner starts nothing new
    stopped = assistant_stop()
    return {"assistant": stopped["stopped"], "agv": part(agv.cancel), "arm": part(skills.cancel), "task": task}


def _fetch_stop():
    from tasks import fetch
    return fetch.stop()

# ---------- hold-to-move, map, arm (dashboard) ----------
AGV_WEB = "http://192.168.10.10:9001"


class JogBody(BaseModel):
    axis: str = Field(examples=["head_yaw"], description="base_drive, base_turn, lift, waist, head_yaw, head_pitch, j1..j6")
    direction: int = Field(1, description="+1 or -1")
    speed: float = Field(0.5, ge=0.05, le=1.0, description="0..1 of the axis' top speed")


class PointBody(BaseModel):
    x: float
    y: float
    theta: float = Field(0.0, description="rad, map frame")


class MapBody(BaseModel):
    map_name: str
    floor: int = 1


class OnBody(BaseModel):
    on: bool


class ProgramBody(BaseModel):
    program: str = Field(examples=["arm_reach.jks"])


@app.post("/jog", tags=["control"], summary="Hold-to-move: call every ~150 ms while a button is held")
def jog(body: JogBody):
    robot_free(manual=True)
    try:
        jogger.hold(body.axis, body.direction, body.speed)
    except ValueError as e:
        raise HTTPException(400, str(e))
    err, jogger.last_error = jogger.last_error, None       # report each error once, not on every call
    return {"ok": True, "error": err}


@app.post("/jog/stop", tags=["control"], summary="Stop every hold-to-move axis now")
def jog_stop():
    jogger.stop()
    return {"ok": True}


@app.get("/map/info", tags=["map"], summary="Current map, its geometry, the markers with poses and all maps")
def map_info():
    cur = agv.request("/api/map/get_current_map")["results"]
    marks = agv.request("/api/markers/query_list")["results"]
    maps = agv.request("/api/map/list")["results"]
    markers = [{"name": n, "type": m.get("key"), "x": m["pose"]["position"]["x"], "y": m["pose"]["position"]["y"],
                "theta": 2 * math.atan2(m["pose"]["orientation"]["z"], m["pose"]["orientation"]["w"])}
               for n, m in marks.items() if m.get("floor", 1) == cur["floor"]]
    return {"map_name": cur["map_name"], "floor": cur["floor"], **cur["info"], "markers": markers,
            "main_dock": agv.dock_marker(),          # "home"; further docks (dock2) keep their names
            "maps": [{"name": n, "floors": f} for n, f in sorted(maps.items())]}


@app.get("/map/image", tags=["map"], summary="Map picture (PNG) from the base; default the current map")
def map_image(map_name: str | None = None, floor: int | None = None):
    if map_name is None:
        cur = agv.request("/api/map/get_current_map")["results"]
        map_name, floor = cur["map_name"], cur["floor"]
    url = f"{AGV_WEB}/maps/{urllib.request.quote(map_name)}/{floor or 1}/map.png"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return Response(r.read(), media_type="image/png", headers={"Cache-Control": "max-age=60"})
    except Exception as e:
        raise HTTPException(502, f"map picture not available: {e}")


@app.post("/map/switch", tags=["map"], summary="Use another map (the base service restarts; relocalise after)")
def map_switch(body: MapBody):
    robot_free()
    try:
        r = agv.request(f"/api/map/set_current_map?map_name={body.map_name}&floor={body.floor}", timeout=10)
    except Exception as e:                       # the base restarts and may not answer
        r = {"note": f"no reply ({e}); the base is restarting"}
    return {"ok": True, "reply": r}


@app.post("/agv/go_point", tags=["base"], summary="Drive to a point on the map (x, y in m, theta in rad)")
def go_point(body: PointBody):
    if assistant_pids():
        send_to_assistant("go_point", point=[body.x, body.y, body.theta])
        return {"ok": True, "by": "assistant"}
    part(fetch_head_ahead)
    ok, msg = agv.go_point(body.x, body.y, body.theta)
    if not ok:
        raise HTTPException(502, f"AGV refused: {msg}")
    return {"ok": True}


@app.get("/arm/state", tags=["arm"], summary="Joints (deg), TCP (mm, deg), power, enable, program")
def arm_state():
    d = arm.cmd("get_data")
    st = arm.cmd("get_robot_state")
    return {"joints": [round(v, 2) for v in d.get("joint_actual_position", [])],
            "tcp": [round(v, 1) for v in d.get("actual_position", [])],
            "power": bool(st.get("power")), "enable": bool(st.get("enable")),
            "program": arm.program_state(), "loaded": arm.cmd("get_loaded_program").get("programName")}


@app.post("/arm/power", tags=["arm"], summary="Arm power on / off")
def arm_power(body: OnBody):
    robot_free(manual=True)
    return arm.cmd("power_on" if body.on else "power_off")


@app.post("/arm/enable", tags=["arm"], summary="Arm servo enable / disable")
def arm_enable(body: OnBody):
    robot_free(manual=True)
    return arm.cmd("enable_robot" if body.on else "disable_robot")


@app.post("/arm/run", tags=["arm"], summary="Run a Cobo π program (.jks) once, only from look; returns at once")
def arm_run(body: ProgramBody):
    robot_free(manual=True)
    if not arm.ready():
        raise HTTPException(409, "arm not ready: power/enable off, or a program is running")
    try:
        arm_route.start_program(body.program)
    except arm_route.RouteError as e:
        raise HTTPException(409, e.args[0])
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "program": body.program}


class PoseBody(BaseModel):
    name: str = Field(examples=["look"], description="a pose of the pose graph (manipulation/arm_route.py)")
    speed: str = Field(arm_route.SPEED, description="slow / normal / route (empty hand; holding: always slow)")


class LineBody(BaseModel):
    dx: float = 0.0
    dy: float = 0.0
    dz: float = Field(0.0, examples=[30.0], description="mm, arm base frame (z up); orientation is kept")
    speed: str = "slow"


class NameBody(BaseModel):
    name: str = Field(examples=["ready"])


def _motion(fn, *args, **kw):
    robot_free(manual=True)
    try:
        return {"ok": True, "joints": fn(*args, **kw)}
    except motion.MotionError as e:
        raise HTTPException(409, str(e))


@app.get("/arm/poses", tags=["arm"], summary="The taught poses of the pose graph (deg)")
def arm_poses():
    return arm_route.graph()


@app.post("/arm/pose", tags=["arm"], summary="Go to a named pose along the pose graph (every joint move checked first; "
                                            "returns when there)")
def arm_pose(body: PoseBody):
    if body.speed not in motion.JOINT_SPEED:
        raise HTTPException(400, f"speed: {', '.join(motion.JOINT_SPEED)}")
    if body.name not in arm_route.graph():
        raise HTTPException(404, f"no pose {body.name}")
    robot_free(manual=True)
    _posing.set()
    try:
        return {"ok": True, "route": arm_route.goto(body.name, gripper.state()["holding"], speed=body.speed),
                "joints": motion.joints()}
    except arm_route.RouteError as e:
        raise HTTPException(409, e.args[0])
    except motion.MotionError as e:
        raise HTTPException(409, str(e))
    finally:
        _posing.clear()


@app.post("/arm/line", tags=["arm"], summary="Straight TCP move by dx / dy / dz mm (IK-checked first)")
def arm_line(body: LineBody):
    if body.speed not in motion.LINEAR_SPEED:
        raise HTTPException(400, f"speed: {', '.join(motion.LINEAR_SPEED)}")
    return _motion(motion.move_linear, delta=[body.dx, body.dy, body.dz], speed=body.speed)


@app.post("/arm/teach", tags=["arm"], summary="Save the arm's current joints as a named pose")
def arm_teach(body: NameBody):
    return _motion(motion.teach, body.name)


@app.get("/objects", tags=["objects"],
         summary="Objects the torso camera sees: class, colour, centre / top / width / height in the arm base frame (mm)")
def objects_seen():
    camview.want(objects.CAMERA)
    return objects.latest()


@app.get("/gripper/state", tags=["gripper"], summary="Open / closed / holding, finger sensor, raw tool I/O")
def gripper_state():
    return gripper.state()


@app.post("/gripper/open", tags=["gripper"], summary="Open the gripper; returns the state after the stroke (~1.5 s)")
def gripper_open():
    robot_free(manual=True)
    return gripper.open_()


@app.post("/gripper/close", tags=["gripper"], summary="Close the gripper (keep hands away); returns the state after")
def gripper_close():
    robot_free(manual=True)
    return gripper.close()


# ---------- skills: pick and place (manipulation/skills.py) ----------
class ObjectBody(BaseModel):
    object: str = Field("cup", description="COCO class name the camera sees, e.g. cup, bottle")
    colour: str | None = Field(None, examples=["white"], description="only an object of this colour")


class MoveBody(ObjectBody):
    x: float | None = Field(None, description="place spot, mm in the arm base frame; empty = a free spot nearby")
    y: float | None = None


class PlaceBody(BaseModel):
    back: bool = Field(False, description="where it was picked; otherwise a free spot nearby")
    x: float | None = Field(None, description="or this spot, mm in the arm base frame")
    y: float | None = None


_skill = {"thread": None, "state": {"status": "idle"}}


def _run_skill(name, fn, *args, **kw):
    """Run a skill in the background (it takes up to a minute); /skills/state shows how it goes, STOP ends it."""
    robot_free(manual=True)
    if _skill["thread"] and _skill["thread"].is_alive():
        raise HTTPException(409, f"{_skill['state']['skill']} is still running")
    st = _skill["state"] = {"skill": name, "status": "running", "since": time.time()}

    def run():
        try:
            st.update(status="done", result=fn(*args, **kw))
        except skills.SkillError as e:
            st.update(status="refused", reason=e.args[0])
        except motion.MotionError as e:
            st.update(status="stopped", reason=str(e))
        except Exception as e:
            st.update(status="failed", reason=repr(e))
        st["took_s"] = round(time.time() - st["since"], 1)
    _skill["thread"] = threading.Thread(target=run, daemon=True)
    _skill["thread"].start()
    return {"ok": True, "skill": name}


@app.post("/skills/plan", tags=["skills"], summary="Dry run of moving an object: what is seen, the place spot, "
          "every waypoint with IK joints. Nothing moves")
def skill_plan(body: MoveBody):
    seen = skills.look()
    try:
        obj = skills.find(body.object, body.colour, seen)
        xy, rows = skills.plan_move(obj, (body.x, body.y) if body.x is not None else None, seen)
    except skills.SkillError as e:
        return {"ok": False, "reason": str(e), "seen": seen}
    return {"ok": True, "object": obj, "place": xy, "seen": seen,
            "waypoints": [{"name": n, "flange": [round(v, 1) for v in pose], "joints": [round(v, 1) for v in j]}
                          for n, pose, j, _ in rows]}


@app.post("/skills/move", tags=["skills"], summary="Pick the object up and put it at x, y or a free spot nearby; "
          "returns at once, watch /skills/state")
def skill_move(body: MoveBody):
    to = (body.x, body.y) if body.x is not None and body.y is not None else None
    return _run_skill("move", skills.move_object, body.object, body.colour, to)


@app.post("/skills/pick", tags=["skills"], summary="Pick the object up and hold it 3 cm above the table; returns at once")
def skill_pick(body: ObjectBody):
    return _run_skill("pick", skills.pick, body.object, body.colour)


@app.post("/skills/place", tags=["skills"], summary="Put down what /skills/pick holds; returns at once")
def skill_place(body: PlaceBody):
    if body.x is not None and body.y is not None:
        return _run_skill("place", skills.place, body.x, body.y)
    return _run_skill("place", skills.put_down, body.back)


@app.get("/skills/state", tags=["skills"], summary="The last skill: running / done / refused / stopped, reason, log")
def skill_state():
    return {**_skill["state"], "log": list(skills.LOG)[-12:]}


# ---------- fetch tasks: bring an object from one place to another (tasks/fetch.py, docs/16) ----------
class TaskBody(BaseModel):
    object: str = Field(examples=["apple"], description="cup, bottle, apple, orange, banana")
    colour: str | None = Field(None, examples=["red"], description="only an object of this colour; empty = any")
    source: str | dict = Field("here", examples=[{"marker": "p1"}],
                               description='"here", {"marker": name} or {"x", "y" m, "theta" rad} in the map frame')
    dest: str | dict = Field(examples=[{"marker": "home"}], description="same forms as source")
    finish: str = Field("hold", examples=["hold"], description="hold (wait for give / place) or place on the table")
    prefer: str | None = Field(None, examples=["small"], description="which of several: small, big, near, far, left, right")


SWITCHES_OFF = "Switch on Greeter or Patrol first."
BASE_OFF = "I can't drive or turn my waist right now. Switch on Patrol for that."   # lumi.BASE_OFF_SAY, as by voice


def _switches(base):
    """Every task the dashboard starts obeys the switches as voice does: nothing with both off, the base or the waist
    (`base`: a drive or a turn in it) only with Patrol on; with Greeter only a task stays in place (fetch.stay_put).
    STOP, pause, jog and the manual buttons are not asked here."""
    m = read_modes()
    if not (m["greeter"] or m["patrol"]):
        raise HTTPException(409, SWITCHES_OFF)
    if base and not m["patrol"]:
        raise HTTPException(409, BASE_OFF)
    from tasks import fetch
    fetch.stay_put = not m["patrol"]


def _drives(steps):
    from assistant import lumi
    return bool({s.get("do") for s in steps} & lumi.DRIVE_STEPS)


def _plan_drives(r):
    """A /tasks/parse result drives or turns the base / waist."""
    a, task = r.get("action"), r.get("task") or {}
    return a == "carry" or a == "steps" and _drives(r["steps"]) or r.get("base", False) or \
        a == "fetch" and any(task.get(k) not in (None, "here") for k in ("source", "dest"))


def _fetch_call(name, cmd, *args, **fields):
    """start / give / place: the assistant does it while it runs (it owns the robot), else the runner here."""
    from tasks import fetch
    if assistant_pids():
        send_to_assistant(cmd, **fields)
        return {"ok": True, "by": "assistant"}
    try:
        getattr(fetch, name)(*args)
    except fetch.FetchError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "by": "api"}


def _task_problems(task):
    """fetch.validate plus: a map point must be a place the base can stand on."""
    from tasks import fetch
    from robot import nav
    problems = fetch.validate(task, agv.markers())
    for key, what in (("source", "take it from"), ("dest", "bring it to")):
        p = task.get(key)
        if isinstance(p, dict) and "x" in p and not part(lambda: nav.reachable(p["x"], p["y"])) is True:
            problems.append(f"I can't drive to the point chosen to {what}: pick a free spot on the map.")
    return problems


@app.post("/tasks/describe", tags=["tasks"], summary="The task as a sentence and what is wrong with it. Nothing moves")
def task_describe(body: TaskBody):
    from tasks import fetch
    task = body.model_dump()
    return {"sentence": fetch.describe(task, "en"), "problems": _task_problems(task)}


class ParseBody(BaseModel):
    text: str = Field(examples=["bring the red apple from p1 to home"], description="the command in English or Korean")
    source: str | dict | None = Field(None, description="from the dialog, used when the text names no place to take it from")
    dest: str | dict | None = Field(None, description="from the dialog, used when the text names no place to bring it to")
    llm: bool = Field(False, description="words the rules leave are read by the LLM as by voice (Enter in the dialog; "
                                         "not while typing)")


def _talk(sentence, problems=(), kind="talk"):
    """What voice would only answer (a question, talk, a refusal): shown, nothing to start."""
    return {"action": None, "task": None, "talk": kind, "sentence": sentence, "problems": list(problems), "read_by": "rules"}


def _answer(text, sentence, kind="talk", read_by="rules"):
    """What voice answers out loud (a question, seeing, the status, a song, a voice setting, "more" / "again" with
    the assistant's own last command): Start hands the words to the assistant, as if heard (/tasks/command)."""
    return {"action": "command", "text": text, "talk": kind, "sentence": sentence, "problems": [], "read_by": read_by}


def _rule_steps(rule):
    """A keyword command that the mission runner does the same way as voice: its steps, else None (look, lift, wave,
    come, follow, quiet need the assistant: /tasks/command)."""
    a, t = rule
    d, _, n = (t or "").partition(" ")
    if a == "go_to":
        return [{"do": "go", "to": t}]
    if a == "move" and d in ("forward", "back", "left", "right"):
        return [{"do": "move", "dir": d, "m": float(n or 1)}]
    if a == "turn":
        return [{"do": "turn", "deg": 180.0 if d == "around" else (1 if d == "left" else -1) * float(n or 90)}]
    if a == "arm":
        return [{"do": "arm", "pose": t}]
    if a == "pick":
        w = t.split()
        return [{"do": "pick", "object": w[-1], "colour": w[0] if len(w) > 1 else None}]
    return None


def _said(kind, words, what):
    from assistant import brain, steps
    if kind == "steps":
        return steps.describe(what).rstrip(".")
    if kind == "talk":
        return f"answer \u201c{words}\u201d"
    a, t = what
    return {"look": f"look {t}", "lift": f"lift {t}", "wave": "wave", "come": "come to you", "come_back": "go back",
            "follow": "follow you", "go_to": f"go to {brain.place_said(t)}", "arm": f"arm {t}",
            "quiet": "be quiet", "waist": f"turn my waist {t}"}.get(a, f"{a} {t}".strip())


@app.post("/tasks/parse", tags=["tasks"], summary="A typed command (English or Korean) read exactly as by voice "
          "(lumi.route): a mission, a fetch, a command or chain for the assistant, or what Lumi would only answer. "
          "Nothing moves")
def task_parse(body: ParseBody):
    from assistant import brain, driving, lumi, seeing, steps
    from tasks import fetch
    markers = agv.markers()
    text = body.text.strip()
    lang = "ko" if brain.HANGUL.search(text) else "en"
    held = bool(fetch.check_hand())                   # the camera sees the hand; a stale "holding" is forgotten
    if not text:
        return _held_parse(body, markers) if held else _talk("–")
    if lumi.FOREIGN_SCRIPT.search(text):
        return _talk("–", ["Please write the command in English or Korean."])
    from assistant import voice_words
    voice = voice_words.read(text, "")                # Lumi.voice_setting comes first, as by voice
    if voice:
        return _answer(text, {("volume", 1): "Speak louder.", ("volume", -1): "Speak quieter.",
                              ("speed", 1): "Speak faster.", ("speed", -1): "Speak slower."}.get(voice, "Voice setting."),
                       "voice")
    fixed = brain.self_correct(text, markers)         # "go to start, no, end": as by voice (lumi.answer)
    if not fixed:
        return _talk("–", ["Which one did you mean? Please write it again." if fixed is None else "Taken back: nothing to do."])
    body = body.model_copy(update={"text": fixed})
    drive = driving.read(brain._norm(fixed), None, False)       # lumi.drive_words: speed, a distance asked or refused
    if drive == ("ask", ""):                          # "more", "again", "한 번 더": the assistant's last command
        return _answer(fixed, "Again.", "again")
    if drive and drive[0] in ("refuse", "ask"):
        d, _, n = drive[1].partition(" ")
        return _talk(driving.say_refused(d, float(n), "en") if drive[0] == "refuse" else driving.say_ask(drive[1], "en"))
    if drive and drive[0] == "speed":
        return {"action": "command", "text": fixed, "sentence": "Faster." if drive[1] > 0 else "Slower.", "problems": [],
                "read_by": "rules"}
    if lumi.NAME_ONLY.match(fixed):
        return _talk("Yes?")
    seen = lambda x: "seeing" if seeing.answer(x, frames=[]) else None   # no camera here: whether it is one
    kind, data = lumi.route(fixed, markers, brain.Brain(), held, seen=seen)
    if kind == "stop":
        return {"action": "command", "text": fixed, "sentence": "Stop.", "problems": [], "read_by": "rules"}
    if kind == "detour":                              # after a blocked drive (assistant/detour.py): the assistant does it
        from assistant import detour
        return {"action": "command", "text": fixed, "sentence": detour.SAY[data][0], "problems": [], "read_by": "rules",
                "base": True}
    if kind == "chain":
        base = any(k == "steps" and _drives(x) or k == "quick" and x[0] in lumi.BASE_ACTIONS for k, _, x in data)
        return {"action": "command", "text": fixed, "parts": [[k, w] for k, w, _ in data], "problems": [], "read_by": "rules",
                "base": base,
                "sentence": ", then ".join(_said(*p) for p in data).capitalize() + "."}
    if kind == "hand":
        (hand, _) = data
        if hand[0] == "receive" and not held:
            got = [{"do": "receive", "object": hand[1], "from_hand": True}]
            return {"action": "steps", "steps": got, "lang": lang, "sender": None, "read_by": "rules", **_steps_said(got, markers)}
        if hand[0] in ("give", "place"):              # voice's reading of the hand (brain.hand_request), not a second one
            return _held_parse(body, markers, hand[0]) if held else _talk("–", ["My hand is empty, I'm not holding anything."])
        return _talk(hand[1][0] if hand[0] == "refuse" else "–", kind="refuse")
    if kind == "mission":
        got, unread, by = data
        if unread:
            problem = brain.place_problem(" ".join(unread), markers)    # "go to p12", "go to booth" (two)
            return _talk("–", [problem[0] if problem else f"I didn't understand: {', '.join(unread)}"])
        return {"action": "steps", "steps": got, "lang": lang, "sender": steps.sender(fixed), "read_by": by,
                **_steps_said(got, markers)}
    if not held and (lumi.empty_hand_request(fixed) or kind is None and brain.place_on(fixed) and
                     not brain._mentions(fixed, markers).get("object")):   # as by voice: "put it on the table" with
                                                                            # nothing held (the LLM reads a place)
        return _talk("–", ["My hand is empty, I'm not holding anything."])
    if kind == "quick" and data[0] == "fetch":
        return _fetch_parse(body, markers)
    if kind == "quick" and data[0] == "put":
        return _held_parse(body, markers, "place") if held else _talk("–", ["My hand is empty, I'm not holding anything."])
    if kind == "quick" and data[0] in ("weather", "search"):
        return _answer(fixed, "Look it up and answer.", "lookup")
    if kind == "quick":
        if held and data[0] == "go_to":
            return _held_parse(body, markers)                 # holding: a carry there
        got = _rule_steps(data)
        prefer = data[0] == "pick" and got and brain.pick_prefer(fixed)[0]
        if prefer:
            got[0]["prefer"] = prefer                 # "왼쪽 컵 집어", "the smaller cup": which of several (fetch picks it)
        if got:
            return {"action": "steps", "steps": got, "lang": lang, "sender": None, "read_by": "rules",
                    **_steps_said(got, markers)}
        return {"action": "command", "text": fixed, "sentence": _said("quick", fixed, data).capitalize() + ".",
                "problems": [], "read_by": "rules", "base": data[0] in lumi.BASE_ACTIONS, "rule": list(data)}
    problem = brain.place_problem(fixed, markers)
    if problem:                                       # quick_command says it: "I don't have a place called p12"
        return _talk(problem[0], kind="refuse")
    if held and kind is None and brain.held_carry(fixed, markers) and not brain.ARM_TALK.search(fixed) and \
            not brain.to_someone_else(fixed):         # "p5로 가져가": a carry there. Nothing else the rules left is done
        return _held_parse(body, markers)            # with the hand here: as by voice, the LLM reads it (no motion)
    if kind is None and body.llm:                     # the rules leave it: the LLM, one call, as by voice
        gen = brain.Brain().respond_stream(fixed, markers)
        head = next(gen)
        first = next(gen, "") or ""
        gen.close()
        rule = (head["action"], head["target"])
        if rule[0] == "fetch" and brain._mentions(fixed, markers).get("object"):
            return _fetch_parse(body, markers)
        got = _rule_steps(rule) if rule[0] in ("go_to", "move", "turn", "arm", "pick") else None
        if got:
            return {"action": "steps", "steps": got, "lang": lang, "sender": None, "read_by": "llm",
                    **_steps_said(got, markers)}
        if rule[0] in ("look", "lift", "wave", "come", "follow", "come_back", "quiet"):
            return {"action": "command", "text": fixed, "sentence": first or "–", "problems": [], "read_by": "llm",
                    "base": rule[0] in lumi.BASE_ACTIONS}
        return _answer(fixed, first or "Answer.", "talk", "llm")
    return _answer(fixed, {"seeing": "Say what I see.", "status": "Say what I'm doing.", "end": "Say goodbye.",
                           "sing": "Sing.", "correction": "Correct the last command."}.get(kind, "Answer."), kind or "talk")


def _fetch_parse(body, markers):
    """A fetch really read (an object named): the dialog's object / colour / place / finish choices."""
    from assistant import brain
    from tasks import fetch
    if fetch.check_hand():
        return _held_parse(body, markers)
    if not brain._mentions(body.text, markers).get("object"):   # no object named: never a fetch (nor an LLM guess)
        return _talk("–", [f"I didn't understand: {body.text.strip()}"])
    fields, read_by = brain.fetch_from_text(body.text, markers)
    task = {"object": fields.get("object"), "colour": fields.get("colour"),
            "source": fields.get("source") or body.source or "here", "dest": fields.get("dest") or body.dest,
            "finish": fields.get("finish", "hold"), **({"prefer": fields["prefer"]} if fields.get("prefer") else {})}
    problems = [] if task["object"] else ["Which object? I know cup, bottle, apple, orange and banana."]
    problems += [x for x in _task_problems(task) if x not in problems]
    if read_by == "other":                       # not English or Korean: nothing else is worth saying
        problems = ["Please write the command in English or Korean."]
    return {"action": "fetch", "task": task, "sentence": fetch.describe(task, "en"), "problems": problems,
            "read_by": read_by, "from_text": sorted(fields), "choices": _choices()}


class CommandBody(BaseModel):
    text: str = Field(description="a command /tasks/parse read as action \"command\"")


@app.post("/tasks/command", tags=["tasks"], summary="Do a typed command the way voice does it (the assistant hears "
          "it): look, lift, wave, come, follow, several parts in a row")
def task_command(body: CommandBody):
    r = task_parse(ParseBody(text=body.text))         # read again here (rules), never the client's word for it
    if r.get("sentence") == "Stop." and not assistant_pids():
        return task_stop()                            # "stop" never reads the switches
    if r.get("sentence") != "Stop.":
        _switches(_plan_drives(r))
    if not assistant_pids():
        raise HTTPException(409, SWITCHES_OFF)
    send_to_assistant("heard", text=body.text)
    return {"ok": True, "by": "assistant"}


def _steps_said(got, markers):
    from assistant import steps
    from tasks import fetch
    problems = steps.check(got, bool(fetch.state().get("holding")), markers)   # read only: the runner may be in
    try:                                                                         # the assistant's process
        sentence = steps.describe(got)
    except (KeyError, TypeError, IndexError, AttributeError):
        sentence = "–"
    return {"sentence": sentence, "problems": problems}


class StepsBody(BaseModel):
    steps: list[dict] = Field(examples=[[{"do": "pick", "object": "cup", "colour": None},
                                         {"do": "move", "dir": "right", "m": 1.0}, {"do": "place", "on": None}]],
                              description="the steps as /tasks/parse read them (docs/17)")
    lang: str = Field("en", description="language Lumi speaks in while running it: en or ko")
    sender: str | None = Field(None, description="who sends it (from /tasks/parse): may change or cancel it on the way")


@app.post("/tasks/steps/describe", tags=["tasks"], summary="Steps as a sentence and what is wrong with them. Nothing moves")
def steps_describe(body: StepsBody):
    return _steps_said(body.steps, agv.markers())


@app.post("/tasks/steps", tags=["tasks"], summary="Start a mission: the steps in order; returns at once, watch /tasks/state")
def steps_run(body: StepsBody):
    _switches(_drives(body.steps))
    if assistant_pids():
        send_to_assistant("fetch_steps", steps=body.steps, sender=body.sender)
        return {"ok": True, "by": "assistant"}
    from audio import mouth
    from tasks import fetch
    try:
        fetch.run_steps(body.steps, say=lambda en, ko: mouth.say(ko if body.lang == "ko" else en), sender=body.sender)
    except fetch.FetchError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "by": "api"}


def _choices():
    """What the dialog may change by hand after reading a command."""
    from tasks import fetch
    return {"object": list(fetch.PICKABLE), "colour": list(fetch.COLOURS), "finish": list(fetch.FINISH),
            "then": [t for t in fetch.THEN if t]}


def _held_parse(body, markers, said=None):
    """A command while something is held: what to do with it, read by the rules only (fast; the object named in it is
    the held one, so "give me the cup" is a give, not a new fetch). A marker named anywhere in the text is where to
    bring it, else the dialog's To; then put it on a table, hand it over or keep holding it. said: what voice's reader
    (lumi.route: the hand, the put rule) already made of the words, "give" or "place"."""
    from assistant import brain, steps
    from tasks import fetch
    held, text = fetch.held_name(), brain.give_clause(body.text)   # not where the person it is for goes
    m, t = brain._mentions(text, markers), brain._norm(text)
    if isinstance(m.get("source"), dict) and not brain.held_command(text):     # "take the bottle from p2": a new fetch
        return {"action": None, "task": None, "sentence": "–", "problems": [
            f"I'm holding {held}: give it to you, put it on a table, or say where to bring it first."]}
    named = [brain._as_place(brain._resolve(x, markers)) for x in re.finditer(brain._place_re(markers), t)]
    named = [p for p in named if isinstance(p, dict)]
    dest = named[0] if named else (body.dest if body.dest not in (None, "here") else None)
    on = brain.place_on(text)                         # "on the orange chair": what to put it on
    then = said or ("place" if on else brain.held_command(text) or ("place" if m.get("finish") == "place" else None))
    if then == "give" and named and not re.search(r"\b(give|hand)\b|줘|주세요|건네", t):
        then = None                                   # "bring it to p2" is a carry, not a hand-over
    table = "dining table" if re.search(r"\bdin+(?:n|i)?ing\b|\bdinner table\b", t) else "table"   # as it was said
    which = {"low": "lower", "high": "higher", "small": "smaller", "big": "bigger", "far": "farther"}.get(
        (on or {}).get("prefer"))                     # "the lower one": which of several
    on_words = " ".join(w for w in (which, on.get("colour"), " or ".join(n.replace("dining table", table) for n in
                                                                    [on["name"]] + on.get("alts", []))) if w) if on else "table"
    side = steps._side(t) if then == "place" else None  # "왼쪽 테이블에 놔", "put it on the right side": the mission's
    if dest is None and side:                         # place step turns to that side first (fetch.place does not)
        got = [{"do": "place", "on": {"name": "dining table", "colour": None, **(on or {}), "side": side}}]
        return {"action": "steps", "steps": got, "lang": "ko" if brain.HANGUL.search(text) else "en", "sender": None,
                "read_by": "rules", **_steps_said(got, markers)}
    if dest is None:
        if then:
            return {"action": then, "task": {"on": on}, "problems": [], "choices": _choices(),
                    "sentence": f"Hand {held} to you." if then == "give" else
                    f"Put {held} on the {on_words}." if on else f"Put {held} on the table near me."}
        return {"action": None, "task": None, "sentence": "–", "problems": [
            f"I'm holding {held}: say give it to me, put it on the table, or where to bring it."]}
    problems = _task_problems({"dest": dest, "object": "cup", "finish": "hold"})   # only the dest can be wrong
    return {"action": "carry", "task": {"dest": dest, "then": then, "on": on}, "problems": problems,
            "choices": _choices(), "sentence": fetch.carry_sentence(dest, then).replace("Bring it", f"Bring {held}", 1)
            .replace("on the table there", f"on the {on_words} there")}


@app.post("/tasks/fetch", tags=["tasks"], summary="Start a fetch: drive, pick, carry, hold or place; returns at once, "
          "watch /tasks/state")
def task_fetch(body: TaskBody):
    from tasks import fetch
    task = body.model_dump()
    problems = _task_problems(task)
    if problems:
        raise HTTPException(400, "; ".join(problems))
    _switches(any(task.get(k) not in (None, "here") for k in ("source", "dest")))   # from / to a place drives
    return _fetch_call("start", "fetch", task, task=task)


@app.post("/tasks/give", tags=["tasks"], summary="Hand the held object to the person in front")
def task_give():
    _switches(False)
    return _fetch_call("give", "fetch_give")


class TaskPlaceBody(BaseModel):
    on: dict | None = Field(None, examples=[{"name": "chair", "colour": "orange"}],
                            description="put it on this instead of a table: camera class and colour (or null)")


@app.post("/tasks/place", tags=["tasks"], summary="Put the held object on the table in front")
def task_place(body: TaskPlaceBody | None = None):
    on = body.on if body else None
    _switches(False)
    return _fetch_call("place", "fetch_place", None, on, on=on)


@app.post("/tasks/release", tags=["tasks"], summary="While giving: the person holds it, open the gripper")
def task_release():
    if assistant_pids():
        send_to_assistant("fetch_release")
        return {"ok": True, "by": "assistant"}
    from tasks import fetch
    fetch.release_now()
    return {"ok": True, "by": "api"}


class CarryBody(BaseModel):
    dest: dict = Field(examples=[{"marker": "p1"}], description='{"marker": name} or {"x", "y", "theta"} (map)')
    then: str | None = Field(None, description='there: null = keep holding it, "place" = on a table, "give" = hand it over')
    on: dict | None = Field(None, description='put it on this instead of a table: {"name": camera class, "colour"}')


@app.post("/tasks/carry", tags=["tasks"], summary="Bring the held object to a place, then keep holding it, put it on "
          "a table there or hand it over")
def task_carry(body: CarryBody):
    _switches(True)
    return _fetch_call("carry_to", "fetch_carry", body.dest, body.then, None, body.on, dest=body.dest, then=body.then,
                       on=body.on)


@app.post("/tasks/pause", tags=["tasks"], summary="Halt the task where it is (the base stops); /tasks/resume goes on")
def task_pause():
    from tasks import fetch
    if assistant_pids():
        send_to_assistant("fetch_pause")
        return {"ok": True, "by": "assistant"}
    return {"ok": fetch.pause(), "by": "api"}


@app.post("/tasks/resume", tags=["tasks"], summary="Go on with a paused task")
def task_resume():
    from tasks import fetch
    if assistant_pids():
        send_to_assistant("fetch_resume")
        return {"ok": True, "by": "assistant"}
    fetch.resume()
    return {"ok": True, "by": "api"}


@app.post("/tasks/stop", tags=["tasks"], summary="Stop the fetch task, the base and the arm")
def task_stop():
    if assistant_pids():
        send_to_assistant("fetch_stop")
    return {"task": part(_fetch_stop), "agv": part(agv.cancel), "arm": part(skills.cancel)}


class TeachBody(BaseModel):
    name: str = Field(examples=["chair"], description="camera class of the thing (chair, couch, dining table, ...)")
    colour: str = Field(examples=["yellow"], description="the colour to call it from now on")


@app.post("/objects/teach", tags=["objects"], summary="The nearest thing of this class seen now is this colour, from now "
          "on and from any side (kept by its place on the map)")
def objects_teach(body: TeachBody):
    from tasks import fetch
    if body.colour not in fetch.COLOURS:
        raise HTTPException(400, f"colour: {', '.join(fetch.COLOURS)}")
    try:
        o, w = fetch.teach_thing(body.name, body.colour)
    except fetch.FetchError as e:
        raise HTTPException(409, str(e))
    return {"name": body.name, "colour": body.colour, "seen_at_mm": [round(o["x"]), round(o["y"])],
            "camera_said": o.get("colour"), "map": [round(float(v), 3) for v in w]}


@app.get("/tasks/state", tags=["tasks"], summary="The fetch task: status, step, task, holding, log")
def task_state():
    from tasks import fetch
    return fetch.state()


class ModesBody(BaseModel):
    greeter: bool | None = Field(None, description="standing: greet people who come close, talk, wake word")
    patrol: bool | None = Field(None, description="driving anywhere: stop for people in the way, talk, drive on")
    wave: bool | None = Field(None, description="wave when asked")
    drive: bool | None = Field(None, description='allow "come here" and voice "go to"')


@app.get("/assistant/modes", tags=["assistant"], summary="Greeter / patrol / wave / drive switches")
def modes_get():
    return {**read_modes(), "running": bool(assistant_pids())}


@app.post("/assistant/modes", tags=["assistant"],
          summary="Switch greeter / patrol (lumi.py starts when one is on and stops when both are off)")
def modes_set(body: ModesBody):
    m = {**read_modes(), **{k: v for k, v in body.model_dump().items() if v is not None}}
    tmp = MODES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(m))
    os.replace(tmp, MODES_FILE)
    calibrating = _calib_active()
    if (m["greeter"] or m["patrol"]) and not assistant_pids():
        start_assistant()
    elif not (m["greeter"] or m["patrol"]) and assistant_pids() and not calibrating:
        assistant_stop()
    return {**m, "running": bool(assistant_pids())}


def _calib_active():
    try:
        c = json.loads(CALIB_FILE.read_text())
        return c.get("state") == "collecting" and c.get("until", 0) > time.time()
    except (FileNotFoundError, ValueError):
        return False


@app.get("/assistant/status", tags=["assistant"], summary="Is the assistant running, stuck, failing? (Settings > Logs)")
def assistant_status():
    pids = assistant_pids()
    lines = tail(LUMI_LOG, 400)
    errors = [l for l in lines if re.search(r"\b(error|failed|stuck|refused|cannot|traceback)\b", l, re.I)]
    # (whole words only: "median_error_deg" in a calibration line is not an error)
    last = lines[-1] if lines else ""
    age = None
    if pids:
        try:
            age = round(time.time() - LUMI_LOG.stat().st_mtime, 1)
        except FileNotFoundError:
            pass
    started = None
    if pids:
        try:
            started = round(time.time() - Path(f"/proc/{pids[0]}").stat().st_mtime)
        except FileNotFoundError:
            pass
    stuck = any("MAIN LOOP STUCK" in l for l in lines[-30:])
    return {"running": bool(pids), "pids": pids, "uptime_s": started, "log_age_s": age, "stuck": stuck,
            "modes": read_modes(), "cameras": camview.status().get("cameras"), "camera_service": camview.service_pid(),
            "errors": errors[-15:], "last_line": last, "console_tail": tail(CONSOLE_LOG, 25)}


class CalibBody(BaseModel):
    on: bool = True


@app.post("/doa/calibrate", tags=["voice"], summary="Start / stop a 2-minute calibration of the voice direction")
def doa_calibrate(body: CalibBody):
    if body.on and not assistant_pids():
        start_assistant()
        time.sleep(1.0)
    CALIB_FILE.write_text(json.dumps({"state": "starting" if body.on else "stopped", "samples": 0,
                                      "until": time.time() + 120 if body.on else 0, "time": time.time()}))
    send_to_assistant("calibrate", on=body.on)
    return {"ok": True}


@app.get("/doa/status", tags=["voice"], summary="Calibration progress and the current calibration")
def doa_status():
    from audio import doa
    try:
        prog = json.loads(CALIB_FILE.read_text())
    except (FileNotFoundError, ValueError):
        prog = {"state": "idle", "samples": 0}
    return {"progress": prog, "calibration": doa.load_calib()}


@app.post("/doa/reset", tags=["voice"], summary="Forget the voice-direction calibration and its samples")
def doa_reset():
    from audio import doa
    for f in (doa.CALIB, doa.SAMPLES):
        f.unlink(missing_ok=True)
    return {"ok": True}

def _supervise():
    """Keep lumi.py running while greeter or patrol is switched on (it can crash or be killed);
    wait longer after each quick failure so a broken start does not loop."""
    wait, last_start = 5.0, 0.0
    while True:
        time.sleep(5.0)
        try:
            m = read_modes()
            if not (m["greeter"] or m["patrol"]) or assistant_pids() or time.time() - last_start < wait:
                if assistant_pids() and time.time() - last_start > 120:
                    wait = 5.0                                   # it has been running fine: reset the back-off
                continue
            with open(CONSOLE_LOG, "a") as f:
                f.write(f"\n{time.strftime('%H:%M:%S')} supervisor: greeter/patrol is on but lumi.py is not running - starting it\n")
            start_assistant()
            last_start, wait = time.time(), min(wait * 2, 120.0)
        except Exception:
            pass


threading.Thread(target=_supervise, daemon=True).start()

@app.get("/health", tags=["status"])
def health():
    return {"ok": True}


def start_services():
    """Speech to text, knowledge search and the LLM, loaded now so the assistant and /ask answer at once."""
    from assistant import brain, knowledge
    from audio import ears
    for name, start in (("whisper", ears.ensure_stt_server), ("embeddings", knowledge.ensure_embed_server),
                        ("llm", brain.warm_up)):
        try:
            start()
            print(f"{time.strftime('%H:%M:%S')} {name} ready", flush=True)
        except Exception as e:                           # the API keeps working without it
            print(f"{time.strftime('%H:%M:%S')} {name} failed: {e}", flush=True)


def _drive_log():
    """Every drive of the base in this log (robot/drive_log.py): start, on the way, standing still, the end."""
    from robot import drive_log
    drive_log.watch(lambda line: print(f"{time.strftime('%H:%M:%S')} {line}", flush=True))


if __name__ == "__main__":
    camview.ensure_running()                             # the camera service owns both cameras
    threading.Thread(target=start_services, daemon=True).start()
    threading.Thread(target=_drive_log, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
