"""Lumi robot API: HTTP endpoints for the base, head, arm, voice and the lumi.py assistant, with Swagger at /docs.

    python api.py                 # http://<thor>:8100/docs  (robot network: http://192.168.10.240:8100/docs)
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
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV_PY = HERE / ".venv" / "bin" / "python"
if VENV_PY.exists() and Path(sys.prefix).resolve() != (HERE / ".venv").resolve():
    os.execv(str(VENV_PY), [str(VENV_PY), str(Path(__file__).resolve())] + sys.argv[1:])

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

import agv
import arm
import camview
import gripper
import motion
import objects
import head
from control import jogger

PORT = 8100
LUMI_LOG = HERE / "lumi.log"                 # written by lumi.py itself
CONSOLE_LOG = HERE / "lumi_console.log"      # lumi.py stdout/stderr when started from here (tracebacks)

app = FastAPI(title="Lumi robot API", version="0.1.0",
              description="Base (AGV), head, arm, voice and the greeter/patrol assistant of our JAKA Lumi. "
                          "Motion endpoints really move the robot.")
_brain = None
_voice_lock = threading.Lock()
CAMERA_NAMES = ("head", "torso")
DASHBOARD = HERE / "dashboard.html"


# ---------- helpers ----------
def assistant_pids():
    """PIDs of running lumi.py processes (started from here or from a terminal)."""
    out = subprocess.run(["pgrep", "-f", f"{HERE}/lumi.py|python3? lumi.py"], capture_output=True, text=True).stdout
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
    args = [str(VENV_PY), str(HERE / "lumi.py")] + ["--no-arm"] * no_arm + ["--no-drive"] * no_drive
    log = open(CONSOLE_LOG, "a")
    log.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start: {' '.join(args[1:])}\n")
    log.flush()
    return subprocess.Popen(args, cwd=HERE, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            start_new_session=True).pid


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
    _route.stop()
    names = agv.markers()
    if body.marker not in names:
        raise HTTPException(400, f"unknown marker {body.marker!r}; markers: {names}")
    if assistant_pids():
        send_to_assistant("go", marker=body.marker)
        return {"ok": True, "marker": body.marker, "by": "assistant"}
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
    return motion.stop()


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
    import mouth
    return {"percent": mouth.volume()}


@app.post("/volume", tags=["voice"], summary="Set the speaker volume (%); kept for every program")
def volume_set(body: VolumeBody):
    import mouth
    mouth.set_volume(body.percent)
    return {"percent": mouth.volume()}

@app.post("/stop", tags=["status"], summary="STOP everything: base drive, arm program and the assistant")
def stop_all():
    jogger.stop()
    _route.stop()
    stopped = assistant_stop()
    return {"assistant": stopped["stopped"], "agv": part(agv.cancel), "arm": part(motion.stop)}

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
    program: str = Field(examples=["hand_shaking.jks"])


@app.post("/jog", tags=["control"], summary="Hold-to-move: call every ~150 ms while a button is held")
def jog(body: JogBody):
    robot_free()
    try:
        jogger.hold(body.axis, body.direction, body.speed)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "error": jogger.last_error}


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
    r = agv.request(f"/api/move?location={body.x:.3f},{body.y:.3f},{body.theta:.3f}")
    if r.get("status") != "OK":
        raise HTTPException(502, f"AGV refused: {r.get('error_message') or r}")
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
    robot_free()
    return arm.cmd("power_on" if body.on else "power_off")


@app.post("/arm/enable", tags=["arm"], summary="Arm servo enable / disable")
def arm_enable(body: OnBody):
    robot_free()
    return arm.cmd("enable_robot" if body.on else "disable_robot")


@app.post("/arm/run", tags=["arm"], summary="Run a Cobo π program (.jks) once; returns at once")
def arm_run(body: ProgramBody):
    robot_free()
    if not arm.ready():
        raise HTTPException(409, "arm not ready: power/enable off, or a program is running")
    try:
        arm.start(body.program)
    except RuntimeError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "program": body.program}


@app.post("/arm/tuck", tags=["arm"], summary="Fold the arm beside the column (slow), e.g. before driving")
def arm_tuck():
    return arm_pose(PoseBody(name="tuck", wait=False))


class PoseBody(BaseModel):
    name: str = Field(examples=["ready"], description="tuck or a pose taught with /arm/teach")
    speed: str = Field("slow", description="slow / normal")
    wait: bool = Field(True, description="return when the arm is there (STOP ends the wait)")


class LineBody(BaseModel):
    dx: float = 0.0
    dy: float = 0.0
    dz: float = Field(0.0, examples=[30.0], description="mm, arm base frame (z up); orientation is kept")
    speed: str = "slow"


class NameBody(BaseModel):
    name: str = Field(examples=["ready"])


def _motion(fn, *args, **kw):
    robot_free()
    try:
        return {"ok": True, "joints": fn(*args, **kw)}
    except motion.MotionError as e:
        raise HTTPException(409, str(e))


@app.get("/arm/poses", tags=["arm"], summary="Named arm poses (deg): tuck + taught ones")
def arm_poses():
    return motion.poses()


@app.post("/arm/pose", tags=["arm"], summary="Move to a named pose (checked joint move, slow by default)")
def arm_pose(body: PoseBody):
    if body.speed not in motion.JOINT_SPEED:
        raise HTTPException(400, f"speed: {', '.join(motion.JOINT_SPEED)}")
    return _motion(motion.go, body.name, body.speed, body.wait)


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
    robot_free()
    return gripper.open_()


@app.post("/gripper/close", tags=["gripper"], summary="Close the gripper (keep hands away); returns the state after")
def gripper_close():
    robot_free()
    return gripper.close()


class ModesBody(BaseModel):
    greeter: bool | None = Field(None, description="standing: greet people who come close, talk, wake word")
    patrol: bool | None = Field(None, description="driving anywhere: stop for people in the way, talk, drive on")
    wave: bool | None = Field(None, description="wave when greeting")
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
    import doa
    try:
        prog = json.loads(CALIB_FILE.read_text())
    except (FileNotFoundError, ValueError):
        prog = {"state": "idle", "samples": 0}
    return {"progress": prog, "calibration": doa.load_calib()}


@app.post("/doa/reset", tags=["voice"], summary="Forget the voice-direction calibration and its samples")
def doa_reset():
    import doa
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


if __name__ == "__main__":
    camview.ensure_running()                             # the camera service owns both cameras
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
