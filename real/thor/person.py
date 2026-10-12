"""Find people in front of the robot: Orbbec colour + depth, YOLOv8n (ONNX, OpenCV DNN on the CPU).

    python person.py                # head camera, print the people seen (distance, angle) for 20 s
    python person.py torso --save   # torso camera, also save person_view.jpg with boxes every second

The camera is chosen by name (head / torso), serial number or index. Names are safer: the index
order changes when USB cables are moved.

Each person: box in colour pixels, score, distance in metres (median depth inside the box centre; without
depth (depth=False, the head camera, see camview.py) a distance_hint function or the box size gives it),
angle in degrees from the robot's waist forward axis (positive = person is on the image's left side).
For the head camera the current head yaw is added, so the angle does not jump when the head turns.
"""
import pathlib
import sys
import threading
import time

import cv2
import numpy as np
from pyorbbecsdk import (AlignFilter, Config, Context, OBFormat, OBLogLevel, OBSensorType, OBStreamType,
                         Pipeline)

import camview
import head

HERE = pathlib.Path(__file__).resolve().parent
MODEL = HERE / "models" / "yolov8n.onnx"
COLOR_HFOV = 94.0            # deg, Gemini 2 L colour camera
SIZE = 640                   # YOLO input size
MIN_SCORE = 0.5
CAMERAS = {"head": "CPA9B52007A", "torso": "CPA9B520037"}   # name -> serial number
# The head camera sits behind a USB 2.0 hub inside the head (shared with the mic and speaker).
# On USB 2 the default depth mode is 1280x800 at 10 fps with many broken framesets. 15 fps colour (MJPG)
# + 640x400 depth leaves room for the mic and gives clean frames; YOLO on the CPU runs ~15 fps anyway.
COLOR_MODE = (1280, 720, OBFormat.MJPG, 15)
DEPTH_MODE = (640, 400, OBFormat.Y16, 15)
FY_720 = 610.0               # px, colour focal length at 1280x720 (JAKA calibration of the Gemini 2 L)
PERSON_H, PERSON_W = 1.70, 0.50   # m, typical person height and width for a distance from the box size
OPEN_TRIES = 5               # 1 s apart
NEAR_RED = 1.2               # m; nearest person this close is drawn red even when lumi.py is not running
STALL_S = 2.0                # s without a full frame -> reopen the camera
REBOOT_IF_STUCK_AGAIN_S = 15.0   # s; stuck again this soon after a reopen -> reboot the device
REBOOT_WAIT_S = 6.0          # s for a rebooted camera to come back on USB
MAX_REBOOTS_10MIN = 3        # more than this -> the camera rests UNSTABLE_PAUSE_S before trying again
UNSTABLE_PAUSE_S = 60.0
HEAD_POLL_S = 0.2            # s between head yaw reads (head camera only)


def _profile(pipeline, sensor, mode):
    """The wanted stream mode, or the camera's default if it does not offer it."""
    profiles = pipeline.get_stream_profile_list(sensor)
    try:
        return profiles.get_video_stream_profile(*mode)
    except Exception:
        return profiles.get_default_video_stream_profile()


_ctx = []                     # one Orbbec context per program, kept alive while its devices are used


def open_camera(camera):
    """camera = name (head / torso), serial number or index -> (Pipeline, serial, name).
    Only the camera service (camview.py) should call this: two programs opening cameras reset them."""
    if not _ctx:
        ctx = Context()
        ctx.set_logger_level(OBLogLevel.NONE)
        _ctx.append(ctx)
    devices = _ctx[0].query_devices()
    serials = [devices.get_device_serial_number_by_index(i) for i in range(devices.get_count())]
    camera = str(camera)
    wanted = CAMERAS.get(camera, camera)
    if wanted in serials:
        index = serials.index(wanted)
    elif camera.isdigit() and int(camera) < len(serials):
        index = int(camera)
    else:
        raise RuntimeError(f"camera {camera!r} not found; connected: {serials}")
    name = next((n for n, sn in CAMERAS.items() if sn == serials[index]), f"#{index}")
    return Pipeline(devices.get_device_by_index(index)), serials[index], name


def _jpeg_complete(data):
    """True if the JPEG ends with its end-of-image marker (FF D9), ignoring zero padding."""
    end = len(data)
    while end > 2 and data[end - 1] == 0:
        end -= 1
    return end > 2 and data[end - 2] == 0xFF and data[end - 1] == 0xD9


class PersonDetector:
    def __init__(self, camera="head", head_sign=1.0, depth=True):
        self.camera, self.use_depth = camera, depth
        self.distance_hint = None                   # optional f(angle_deg) -> metres from another camera
        self._open()
        self.last_frame = time.time()
        self.reopens, self.reboots, self.last_reopen = 0, 0, 0.0
        self.head_sign, self.head_yaw = head_sign, 0.0
        self.focus_angle = None                     # set by lumi.py: the person it talks to is drawn red
        self.bad_jpeg = 0                           # colour frames dropped because they arrived incomplete
        self.running = True
        if self.name == "head":                     # the head camera turns with the head
            threading.Thread(target=self._follow_head, daemon=True).start()
        self.align = AlignFilter(align_to_stream=OBStreamType.COLOR_STREAM)   # depth pixels -> colour pixels
        self.net = cv2.dnn.readNetFromONNX(str(MODEL))
        # frames are grabbed at the camera's rate in their own thread (live video: on_raw gets every JPEG);
        # read() detects people on the newest frame only, at whatever speed YOLO manages
        self.on_raw = None                          # f(name, jpeg bytes), set by the camera service
        self._latest, self._new = None, threading.Event()
        threading.Thread(target=self._grab, daemon=True).start()

    def _grab(self):
        while self.running:
            try:
                frames = self.pipeline.wait_for_frames(200)
            except Exception:
                time.sleep(0.05)
                continue
            if frames is None:
                continue
            if self.on_raw is not None:
                c = frames.get_color_frame()
                if c is not None and str(c.get_format()).endswith("MJPG"):
                    data = np.asanyarray(c.get_data())
                    if _jpeg_complete(data):
                        try:
                            self.on_raw(self.name, data.tobytes())
                        except Exception:
                            pass
            self._latest = frames
            self._new.set()

    def _open(self):
        for attempt in range(OPEN_TRIES):           # the live view in api.py may still be letting it go
            try:
                self.pipeline, self.serial, self.name = open_camera(self.camera)
                config = Config()
                config.enable_stream(_profile(self.pipeline, OBSensorType.COLOR_SENSOR, COLOR_MODE))
                if self.use_depth:
                    config.enable_stream(_profile(self.pipeline, OBSensorType.DEPTH_SENSOR, DEPTH_MODE))
                self.pipeline.start(config)
                return
            except Exception:
                if attempt == OPEN_TRIES - 1:
                    raise
                time.sleep(1.0)

    def _reopen(self):
        """The camera stopped sending. Seen on the head camera: sometimes it streams for ~1 s and then stops,
        and opening it again does not help; a device reboot does. So: reopen first; stuck again soon -> reboot."""
        now = time.time()
        reboot = now - self.last_reopen < REBOOT_IF_STUCK_AGAIN_S
        self.last_reopen = now
        old = self.pipeline
        self.reboot_times = [t for t in getattr(self, "reboot_times", []) if now - t < 600]
        if reboot and len(self.reboot_times) >= MAX_REBOOTS_10MIN:
            # it keeps failing (the head camera's USB 2 hub): rest instead of resetting the hub again and again,
            # which also disturbs the microphone and the speaker on the same hub
            print(f"{self.name} camera: unstable ({len(self.reboot_times)} reboots in 10 min) - pausing "
                  f"{UNSTABLE_PAUSE_S:.0f} s", flush=True)
            t = threading.Thread(target=old.stop, daemon=True)
            t.start()
            t.join(2.0)
            time.sleep(UNSTABLE_PAUSE_S)
            self.reboot_times = self.reboot_times[-1:]
            reboot = False
        if reboot:
            self.reboot_times.append(now)
            try:
                dev = old.get_device()
                t = threading.Thread(target=dev.reboot, daemon=True)
                t.start()
                t.join(3.0)
                print(f"{self.name} camera: stuck again - device rebooted", flush=True)
                self.reboots += 1
            except Exception as e:
                print(f"{self.name} camera: reboot failed: {e}", flush=True)
            time.sleep(REBOOT_WAIT_S)                       # the camera leaves the USB bus and comes back
        elif not self.reboot_times or self.reboot_times[-1] != now:
            t = threading.Thread(target=old.stop, daemon=True)     # stop() can hang on a stuck device
            t.start()
            t.join(2.0)
        try:
            self._open()
            self.reopens += 1
            print(f"{self.name} camera: no frames for {STALL_S:.0f} s - reopened", flush=True)
        except Exception as e:
            print(f"{self.name} camera: reopen failed: {e}", flush=True)
        self.last_frame = time.time()

    def close(self):
        self.running = False
        self.pipeline.stop()

    def _follow_head(self):
        """Keep self.head_yaw up to date (deg) so image angles can be turned into waist angles."""
        while self.running:
            try:
                self.head_yaw = head.status()[2]
            except Exception:
                pass                                # keep the last value; the body API may be busy
            time.sleep(HEAD_POLL_S)

    def _frames(self):
        """(colour BGR image, depth in mm aligned to it) or (None, None)."""
        if not self._new.wait(0.2):
            return None, None
        self._new.clear()
        frames = self._latest
        if frames is None:
            return None, None
        if not self.use_depth:
            c = frames.get_color_frame()
            return (self._decode(c), None) if c is not None else (None, None)
        frames = self.align.process(frames)
        if frames is None:
            return None, None
        frames = frames.as_frame_set()
        c, d = frames.get_color_frame(), frames.get_depth_frame()
        if c is None or d is None or len(d.get_data()) != d.get_width() * d.get_height() * 2:
            return None, None
        color = self._decode(c)
        depth = np.frombuffer(d.get_data(), dtype=np.uint16).reshape(d.get_height(), d.get_width())
        depth = depth.astype(np.float32) * d.get_depth_scale()
        if color is None or color.shape[:2] != depth.shape:
            return None, None
        return color, depth

    def _decode(self, c):
        data = np.asanyarray(c.get_data())
        if str(c.get_format()).endswith("MJPG"):
            if not _jpeg_complete(data):            # cut short on the busy USB 2 hub: skip it quietly
                self.bad_jpeg += 1
                return None
            return cv2.imdecode(data, cv2.IMREAD_COLOR)
        return cv2.cvtColor(data.reshape(c.get_height(), c.get_width(), 3), cv2.COLOR_RGB2BGR)

    def _box_distance(self, x1, y1, x2, y2, h):
        """Rough distance from the box size: height for a whole person, width if the box is cut by the frame."""
        f = FY_720 * h / 720
        if y1 > 3 and y2 < h - 3 and y2 > y1:
            return f * PERSON_H / (y2 - y1)
        return f * PERSON_W / max(1, x2 - x1)

    def _detect(self, color):
        """YOLOv8 boxes for class 0 (person): list of (x1, y1, x2, y2, score)."""
        h, w = color.shape[:2]
        scale = SIZE / max(h, w)
        canvas = np.zeros((SIZE, SIZE, 3), np.uint8)              # letterbox, keep aspect ratio
        canvas[:int(h * scale), :int(w * scale)] = cv2.resize(color, (int(w * scale), int(h * scale)))
        self.net.setInput(cv2.dnn.blobFromImage(canvas, 1 / 255.0, (SIZE, SIZE), swapRB=True))
        out = self.net.forward()[0].T                              # (8400, 84): cx, cy, w, h, 80 class scores
        scores = out[:, 4]                                         # person
        keep = scores > MIN_SCORE
        if not keep.any():
            return []
        cx, cy, bw, bh = (out[keep, i] / scale for i in range(4))
        boxes = np.stack([cx - bw / 2, cy - bh / 2, bw, bh], axis=1)
        idx = cv2.dnn.NMSBoxes(boxes.tolist(), scores[keep].tolist(), MIN_SCORE, 0.45)
        result = []
        for i in np.array(idx).flatten():
            x, y, bw_, bh_ = boxes[i]
            result.append((max(0, int(x)), max(0, int(y)), min(w - 1, int(x + bw_)), min(h - 1, int(y + bh_)),
                           float(scores[keep][i])))
        return result

    def read(self):
        """(colour image, [dict(box, score, distance_m, angle_deg)]) or (None, []) if no frame."""
        color, depth = self._frames()
        if color is None:
            if time.time() - self.last_frame > STALL_S:
                self._reopen()
            return None, []
        self.last_frame = time.time()
        w = color.shape[1]
        yaw = self.head_yaw                         # 0 for the torso camera
        people = []
        for x1, y1, x2, y2, score in self._detect(color):
            # centre part of the box (torso), ignore holes (0) in the depth image
            cx1, cx2 = x1 + (x2 - x1) // 4, x2 - (x2 - x1) // 4
            cy1, cy2 = y1 + (y2 - y1) // 4, y2 - (y2 - y1) // 2
            angle = -((x1 + x2) / 2 - w / 2) / (w / 2) * (COLOR_HFOV / 2) + self.head_sign * yaw
            src = "depth"
            if depth is not None:
                patch = depth[cy1:cy2, cx1:cx2]
                valid = patch[patch > 0]
                dist = float(np.median(valid)) / 1000 if valid.size > 50 else None
            else:
                dist = self.distance_hint(angle) if self.distance_hint else None
                src = "other camera"
                if dist is None:
                    dist, src = self._box_distance(x1, y1, x2, y2, color.shape[0]), "box size"
            people.append({"box": (x1, y1, x2, y2), "score": round(score, 2),
                           "distance_m": None if dist is None else round(dist, 2), "angle_deg": round(angle, 1),
                           "distance_src": src})
        people.sort(key=lambda p: p["distance_m"] if p["distance_m"] is not None else 99)
        if self.focus_angle is not None and people:
            f = min(people, key=lambda p: abs(p["angle_deg"] - self.focus_angle))
            if abs(f["angle_deg"] - self.focus_angle) < 12:
                f["focus"] = True
        elif people and people[0]["distance_m"] is not None and people[0]["distance_m"] <= NEAR_RED:
            people[0]["near"] = True                # the nearest person in the greeting zone (drawn red too)
        camview.publish(self.name, color, people, source=pathlib.Path(sys.argv[0]).name)   # for /view in api.py
        return color, people


def draw(color, people):
    for p in people:
        x1, y1, x2, y2 = p["box"]
        cv2.rectangle(color, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(color, f"{p['distance_m']} m  {p['angle_deg']} deg", (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    return color


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    save = "--save" in sys.argv
    if camview.service_pid():                     # the camera service has the cameras: read its results
        det = camview.RemoteDetector(args[0] if args else "head")
        save = False
    else:
        det = PersonDetector(args[0] if args else "head")
    print(f"{det.name} camera (SN {det.serial}) running; Ctrl+C to stop")
    t0, last_save, n = time.time(), 0.0, 0
    try:
        while time.time() - t0 < 20:
            color, people = det.read()
            if color is None:
                continue
            n += 1
            print(f"{n / (time.time() - t0):4.1f} fps  " +
                  (", ".join(f"{p['distance_m']} m @ {p['angle_deg']} deg ({p['score']})" for p in people)
                   or "no person"))
            if save and time.time() - last_save > 1:
                cv2.imwrite(str(HERE / "person_view.jpg"), draw(color, people))
                last_save = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        det.close()
