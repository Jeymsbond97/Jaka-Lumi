"""Camera service: the ONLY program that opens the Orbbec cameras; everyone else reads its results.

Two programs opening Orbbec cameras at the same time make the SDK reset the devices: the head camera then
disconnects every ~2.5 s (seen 2026-10-12). So one service owns both cameras:

    python camview.py --serve     # started by api.py at boot (and by lumi.py / greeter.py if it is not running)
    python camview.py --stop      # free the cameras, e.g. for camera_fps.py / camera_test.py; it stays off
                                  # (nothing restarts it) until `python camview.py --serve` or --start

For each camera it runs person detection (person.py) and writes to /dev/shm:
- lumi_cam_<name>.jpg / .json   picture with boxes (PUBLISH_HZ) + people, for the dashboard (api.py /view)
- lumi_det_<name>.json          every detection frame: people with boxes, frame size, head yaw (RemoteDetector)
Programs that need people (lumi.py, greeter.py) use RemoteDetector, which has the same read() as
person.PersonDetector. They tell the service whom to draw red (focus) through lumi_focus_<name>.json.
Nobody reading for IDLE_S (no viewer, no lumi.py): detection drops to 1 frame a second.
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
VENV_PY = HERE / ".venv" / "bin" / "python"
SHM = Path("/dev/shm")
PID_FILE = SHM / "lumi_camd.pid"
STATUS_FILE = SHM / "lumi_camd.json"
OFF_FILE = SHM / "lumi_camd.off"          # written by --stop: do not restart the service automatically
SETTINGS = SHM / "lumi_view_settings.json"
CAMERAS = ("head", "torso")
PUBLISH_HZ = 5.0
VIEW_WIDTH = 640             # px, pictures are scaled down to this width
FRESH_S = 1.5                # s; a newer picture counts as live
IDLE_S = 30.0                # s without any reader -> slow detection (1 per second)
DEFAULTS = {"box_color": "#22c55e", "thickness": 2, "boxes": True, "labels": True}
FOCUS_COLOR = (68, 68, 239)  # BGR red: the person Lumi talks to
HEAD_DEPTH = False           # head depth stream + the speaker playing (same USB 2 hub) = camera disconnects
FOCUS_FRESH_S = 3.0          # s; an older focus file (lumi.py gone) is ignored
MATCH_DEG = 8.0              # a torso-camera person within this angle gives the head person's distance

_last = {}
_settings = {"time": 0.0, "value": dict(DEFAULTS)}


def frame_path(name):
    return SHM / f"lumi_cam_{name}.jpg"


def info_path(name):
    return SHM / f"lumi_cam_{name}.json"


def det_path(name):
    return SHM / f"lumi_det_{name}.json"


def focus_path(name):
    return SHM / f"lumi_focus_{name}.json"


def want_path(name):
    return SHM / f"lumi_cam_{name}.want"


def _write(path, data):
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)                         # atomic: a reader never sees half a file


def want(name):
    """A reader (dashboard, lumi.py) is interested in this camera: keep full speed."""
    try:
        want_path(name).touch()
    except OSError:
        pass


# ---------- drawing settings (dashboard) ----------
def settings():
    now = time.time()
    if now - _settings["time"] > 1.0:
        _settings["time"] = now
        try:
            _settings["value"] = {**DEFAULTS, **json.loads(SETTINGS.read_text())}
        except (FileNotFoundError, ValueError):
            _settings["value"] = dict(DEFAULTS)
    return _settings["value"]


def save_settings(new):
    _settings["time"] = 0.0
    value = {**settings(), **{k: v for k, v in new.items() if k in DEFAULTS and v is not None}}
    _write(SETTINGS, json.dumps(value).encode())
    _settings["time"] = 0.0
    return value


def _bgr(hex_color):
    h = hex_color.lstrip("#")
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        r, g, b = 34, 197, 94
    return b, g, r


def publish(name, color, people=(), source="camview.py"):
    """Picture with person boxes for the dashboard (called by PersonDetector.read for every frame)."""
    now = time.time()
    if now - _last.get(name, 0) < 1 / PUBLISH_HZ:
        return
    _last[name] = now
    s = settings()
    scale = VIEW_WIDTH / color.shape[1]
    img = cv2.resize(color, (VIEW_WIDTH, int(color.shape[0] * scale)))
    box_color, thick = _bgr(s["box_color"]), max(1, min(6, int(s["thickness"])))
    for p in people:
        x1, y1, x2, y2 = (int(v * scale) for v in p["box"])
        col = FOCUS_COLOR if p.get("focus") or p.get("near") else box_color
        if s["boxes"]:
            cv2.rectangle(img, (x1, y1), (x2, y2), col, thick + (1 if col == FOCUS_COLOR else 0))
        if s["labels"]:
            text = ("TALKING  " if p.get("focus") else "") + f"{p['distance_m']} m  {p['angle_deg']:+.0f} deg"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            ty = max(th + 6, y1)
            cv2.rectangle(img, (x1, ty - th - 6), (x1 + tw + 6, ty), col, -1)
            cv2.putText(img, text, (x1 + 3, ty - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 1, cv2.LINE_AA)
    ok, jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 75])
    if not ok:
        return
    _write(frame_path(name), jpg.tobytes())
    _write(info_path(name), json.dumps({"time": now, "source": source, "people": [
        {**{k: p[k] for k in ("distance_m", "angle_deg", "score")}, "focus": bool(p.get("focus")),
         "near": bool(p.get("near"))}
        for p in people]}).encode())


def picture_age(name):
    try:
        return time.time() - frame_path(name).stat().st_mtime
    except FileNotFoundError:
        return None


def status():
    try:
        return json.loads(STATUS_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return {}


# ---------- the service ----------
def service_pid():
    try:
        pid = int(PID_FILE.read_text())
        os.kill(pid, 0)
        if "camview.py" in Path(f"/proc/{pid}/cmdline").read_bytes().decode(errors="replace"):
            return pid
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        pass
    return None


_start_lock = threading.Lock()


def ensure_running():
    """Start the camera service if it is not running (safe to call often)."""
    with _start_lock:
        if service_pid() or OFF_FILE.exists():
            return
        subprocess.Popen([str(VENV_PY), str(HERE / "camview.py"), "--serve"], cwd=HERE, stdin=subprocess.DEVNULL,
                         stdout=open(HERE / "camview.log", "a"), stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(30):                       # wait until it has written its pid
            time.sleep(0.1)
            if service_pid():
                return


def stop_service():
    OFF_FILE.touch()
    pid = service_pid()
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(1.5)
            if service_pid():
                os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return pid


def _serve():
    OFF_FILE.unlink(missing_ok=True)
    if service_pid():
        sys.exit("camera service already running")
    PID_FILE.write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, lambda *_: os._exit(0))   # exit at once: pipeline.stop() can hang
    cv2.setNumThreads(8)                          # two YOLOs share these (the Thor has 14 cores)
    from person import PersonDetector
    state = {name: "starting" for name in CAMERAS}

    def write_status():
        _write(STATUS_FILE, json.dumps({"pid": os.getpid(), "cameras": state, "time": time.time()}).encode())

    latest = {}                                   # name -> (time, people): the torso's depth helps the head

    def torso_distance(angle):
        """Distance of the torso camera's person at about this angle (both angles are waist-frame)."""
        t, people = latest.get("torso", (0, []))
        if time.time() - t > 0.5:
            return None
        near = [p for p in people if p["distance_m"] and abs(p["angle_deg"] - angle) < MATCH_DEG]
        return min(near, key=lambda p: abs(p["angle_deg"] - angle))["distance_m"] if near else None

    def run(name):
        det = None
        last_focus_read, focus_mtime = 0.0, None
        while True:
            if det is None:
                try:
                    # head camera without depth: depth + the speaker on the head's USB 2 hub make it disconnect
                    det = PersonDetector(name, head_sign=1.0, depth=(name != "head" or HEAD_DEPTH))
                    if name == "head" and not HEAD_DEPTH:
                        det.distance_hint = torso_distance
                    state[name] = "ok"
                except Exception as e:
                    state[name] = f"cannot open: {e}"
                    write_status()
                    time.sleep(5)
                    continue
                write_status()
            now = time.time()
            if now - last_focus_read > 0.2:       # whom lumi.py talks to (drawn red)
                last_focus_read = now
                try:
                    st = focus_path(name).stat()
                    if now - st.st_mtime > FOCUS_FRESH_S:        # lumi.py stopped (or crashed): nobody to draw red
                        det.focus_angle = None
                    elif st.st_mtime != focus_mtime:
                        focus_mtime = st.st_mtime
                        det.focus_angle = json.loads(focus_path(name).read_text()).get("angle")
                except (FileNotFoundError, ValueError):
                    det.focus_angle = None
            try:
                color, people = det.read()
            except Exception as e:
                state[name] = f"error: {e}"
                write_status()
                time.sleep(1)
                continue
            if color is not None:
                latest[name] = (time.time(), people)
                _write(det_path(name), json.dumps({
                    "time": time.time(), "serial": det.serial, "height": color.shape[0], "width": color.shape[1],
                    "head_yaw": det.head_yaw, "bad_jpeg": det.bad_jpeg, "reopens": det.reopens,
                    "people": people}).encode())
            try:
                idle = time.time() - want_path(name).stat().st_mtime > IDLE_S
            except FileNotFoundError:
                idle = True
            if idle:
                time.sleep(1.0)

    for name in CAMERAS:
        threading.Thread(target=run, args=(name,), daemon=True).start()
        time.sleep(2.0)                           # open the cameras one after the other
    while True:
        time.sleep(5)
        write_status()


class RemoteDetector:
    """Reads the camera service's detections; same use as person.PersonDetector (read(), name, head_yaw...)."""

    def __init__(self, camera="head", head_sign=1.0):
        if camera not in CAMERAS:
            raise ValueError(f"camera must be one of {CAMERAS} (the camera service owns them)")
        self.name, self.head_sign = camera, head_sign
        self.serial, self.head_yaw, self.bad_jpeg, self.reopens = "?", 0.0, 0, 0
        self._last_time, self._last_want = 0.0, 0.0
        self._focus, self._focus_written = None, 0.0
        ensure_running()

    @property
    def focus_angle(self):
        return self._focus

    @focus_angle.setter
    def focus_angle(self, angle):
        angle = None if angle is None else round(float(angle), 1)
        if angle != self._focus or time.time() - self._focus_written > 1.0:   # heartbeat: see FOCUS_FRESH_S
            self._focus, self._focus_written = angle, time.time()
            _write(focus_path(self.name), json.dumps({"angle": angle}).encode())

    def read(self, timeout=0.3):
        """(frame stand-in with .shape, people) for a new detection frame, or (None, []) if none came."""
        now = time.time()
        if now - self._last_want > 1.0:
            self._last_want = now
            want(self.name)
            if not service_pid():
                ensure_running()
        end = now + timeout
        while time.time() < end:
            try:
                if det_path(self.name).stat().st_mtime > self._last_time:
                    d = json.loads(det_path(self.name).read_text())
                    if d["time"] > self._last_time:
                        self._last_time = d["time"]
                        self.serial, self.head_yaw = d["serial"], d["head_yaw"]
                        self.bad_jpeg, self.reopens = d["bad_jpeg"], d["reopens"]
                        return np.empty((d["height"], 0), np.uint8), d["people"]
            except (FileNotFoundError, ValueError, KeyError):
                pass
            time.sleep(0.01)
        return None, []

    def close(self):
        self.focus_angle = None


if __name__ == "__main__":
    if "--serve" in sys.argv:
        _serve()
    elif "--stop" in sys.argv:
        print(("stopped" if stop_service() else "not running") + "; it stays off until: python camview.py --start")
    elif "--start" in sys.argv:
        OFF_FILE.unlink(missing_ok=True)
        ensure_running()
        print({"pid": service_pid()})
    else:
        print({"pid": service_pid(), **status()})
