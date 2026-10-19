"""Find people in front of the robot: Orbbec colour + depth, YOLOv8s on the GPU (TensorRT engine) or, when that is not
available, YOLOv8n on the CPU (ONNX, OpenCV DNN). Both have the 80 COCO classes; only the speed and accuracy differ.

    python vision/person.py                # head camera, print the people seen (distance, angle) for 20 s
    python vision/person.py torso --save   # torso camera, also save person_view.jpg with boxes every second

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

from vision import camview
from robot import head

ROOT = pathlib.Path(__file__).resolve().parents[1]      # the project folder
MODEL = ROOT / "models" / "yolov8n.onnx"              # fallback: OpenCV DNN on the CPU
ENGINE = ROOT / "models" / "yolov8s.engine"           # TensorRT engine built from yolov8s.onnx on this Thor (640, FP32)
COLOR_HFOV = 94.0            # deg, Gemini 2 L colour camera
SIZE = 640                   # YOLO input size
MIN_SCORE = 0.5
OBJECT_SCORE = 0.35          # other COCO classes (cups, bottles...) are kept for objects.py above this ...
WEAK_SCORE = {41: 0.05}      # ... and cups from this: a white tumbler 1.4 m away scored 0.03-0.25 (2026-10-16); objects.py
                             # keeps such a weak box only when depth measures a cup-sized thing there (objects.WEAK)
# Full-size px (x1, y1, x2, y2) looked at a second time, bigger (about 2.7x the whole-frame pass): the pick zone of the
# torso camera (a cup on a box there scored 0.15 in the whole frame and 0.73 in this crop, 2026-10-15), and the left
# and right of the band where table tops further away are seen (cups 1-3 m away were missed, 2026-10-16). ~45-50 ms
# each on the CPU.
ZOOM = {"torso": [(400, 300, 880, 720), (0, 180, 560, 600), (720, 180, 1280, 600)]}
ZOOM_EDGE_PX = 3             # a zoom box touching a crop side inside the frame is cut by it: not used
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


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter or 1)


class CvNet:
    """YOLO on the CPU through OpenCV DNN (the fallback)."""
    name = "OpenCV DNN on the CPU (yolov8n)"

    def __init__(self):
        self.net = cv2.dnn.readNetFromONNX(str(MODEL))

    def forward(self, blob):
        self.net.setInput(blob)
        return self.net.forward()


class TrtNet:
    """YOLO on the GPU through TensorRT: the engine file is deserialized once, input and output stay in GPU memory."""
    name = "TensorRT on the GPU (yolov8s)"

    def __init__(self, path=None):
        import tensorrt as trt
        from cuda.bindings import runtime as cr
        self.cr = cr
        path = path or ENGINE
        self.engine = trt.Runtime(trt.Logger(trt.Logger.ERROR)).deserialize_cuda_engine(open(path, "rb").read())
        if self.engine is None:
            raise RuntimeError(f"cannot load {path}")
        self.ctx = self.engine.create_execution_context()
        self.inp, self.out = (self.engine.get_tensor_name(i) for i in range(2))
        self.out_shape = (1, 84, 8400)                # YOLOv8 at 640: 84 values (box + 80 classes) x 8400 anchors
        self.in_bytes = 1 * 3 * SIZE * SIZE * 4
        self.out_bytes = int(np.prod(self.out_shape)) * 4
        self.d_in, self.d_out = self._malloc(self.in_bytes), self._malloc(self.out_bytes)
        self.ctx.set_tensor_address(self.inp, int(self.d_in))
        self.ctx.set_tensor_address(self.out, int(self.d_out))
        self.stream = self._malloc_stream()
        self.host_out = np.empty(self.out_shape, np.float32)

    def _check(self, r):
        """cuda-python returns (error, value) or just the error."""
        if isinstance(r, tuple):
            err, val = r[0], (r[1] if len(r) > 1 else None)
        else:
            err, val = r, None
        if err != self.cr.cudaError_t.cudaSuccess:
            raise RuntimeError(f"CUDA error {err}")
        return val

    def _malloc(self, nbytes):
        return self._check(self.cr.cudaMalloc(nbytes))

    def _malloc_stream(self):
        return self._check(self.cr.cudaStreamCreate())

    def forward(self, blob):
        """blob: (1, 3, 640, 640) float32, as cv2.dnn.blobFromImage makes it. Returns (1, 84, 8400)."""
        x = np.ascontiguousarray(blob, np.float32)
        cr = self.cr
        self._check(cr.cudaMemcpyAsync(self.d_in, x.ctypes.data, self.in_bytes,
                                       cr.cudaMemcpyKind.cudaMemcpyHostToDevice, self.stream))
        self.ctx.execute_async_v3(int(self.stream))
        self._check(cr.cudaMemcpyAsync(self.host_out.ctypes.data, self.d_out, self.out_bytes,
                                       cr.cudaMemcpyKind.cudaMemcpyDeviceToHost, self.stream))
        self._check(cr.cudaStreamSynchronize(self.stream))
        return self.host_out


def load_net():
    """The GPU detector when its engine loads, else the CPU one (the robot keeps working, only slower)."""
    try:
        return TrtNet()
    except Exception as e:                  # no engine file, no GPU, no TensorRT: say why, then use the fallback
        print(f"person: TensorRT not used ({e}); YOLOv8n on the CPU", flush=True)
        return CvNet()


class PersonDetector:
    def __init__(self, camera="head", head_sign=1.0, depth=True):
        self.camera, self.use_depth = camera, depth
        self.distance_hint = None                   # optional f(angle_deg) -> metres from another camera
        self._open()
        self.last_frame = time.time()
        self.reopens, self.reboots, self.last_reopen = 0, 0, 0.0
        self.head_sign, self.head_yaw = head_sign, 0.0
        self.head_pose = None                       # [lift, waist, yaw, pitch] last read (head camera only)
        self.focus_angle = None                     # set by lumi.py: the person it talks to is drawn red
        self.bad_jpeg = 0                           # colour frames dropped because they arrived incomplete
        self.running = True
        self.objects, self.depth = [], None         # last frame: non-person boxes and aligned depth (objects.py)
        if self.name == "head":                     # the head camera turns with the head
            threading.Thread(target=self._follow_head, daemon=True).start()
        self.align = AlignFilter(align_to_stream=OBStreamType.COLOR_STREAM)   # depth pixels -> colour pixels
        self.net = load_net()
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
        for attempt in range(OPEN_TRIES):           # the live view in api/server.py may still be letting it go
            try:
                self.pipeline, self.serial, self.name = open_camera(self.camera)
                config = Config()
                self.color_profile = _profile(self.pipeline, OBSensorType.COLOR_SENSOR, COLOR_MODE)
                config.enable_stream(self.color_profile)
                if self.use_depth:
                    config.enable_stream(_profile(self.pipeline, OBSensorType.DEPTH_SENSOR, DEPTH_MODE))
                self.pipeline.start(config)
                return
            except Exception:
                if attempt == OPEN_TRIES - 1:
                    raise
                time.sleep(1.0)

    def intrinsics(self):
        """Colour camera matrix and distortion of the open mode (factory calibration), as a JSON-ready dict."""
        i, d = self.color_profile.get_intrinsic(), self.color_profile.get_distortion()
        return {"width": i.width, "height": i.height, "fx": i.fx, "fy": i.fy, "cx": i.cx, "cy": i.cy,
                "dist": [d.k1, d.k2, d.p1, d.p2, d.k3, d.k4, d.k5, d.k6]}       # OpenCV order

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
                self.head_pose = head.status()
                self.head_yaw = self.head_pose[2]
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
        """YOLOv8 boxes: list of (x1, y1, x2, y2, score, COCO class id); class 0 is a person."""
        h, w = color.shape[:2]
        scale = SIZE / max(h, w)
        canvas = np.zeros((SIZE, SIZE, 3), np.uint8)              # letterbox, keep aspect ratio
        canvas[:int(h * scale), :int(w * scale)] = cv2.resize(color, (int(w * scale), int(h * scale)))
        out = self.net.forward(cv2.dnn.blobFromImage(canvas, 1 / 255.0, (SIZE, SIZE), swapRB=True))[0].T
                                                                   # (8400, 84): cx, cy, w, h, 80 class scores
        cls = out[:, 4:].argmax(axis=1)
        scores = out[np.arange(len(out)), 4 + cls]
        floor = np.array([WEAK_SCORE.get(int(c), OBJECT_SCORE) for c in cls])
        keep = scores > np.where(cls == 0, MIN_SCORE, floor)
        if not keep.any():
            return []
        cls = cls[keep]
        cx, cy, bw, bh = (out[keep, i] / scale for i in range(4))
        boxes = np.stack([cx - bw / 2, cy - bh / 2, bw, bh], axis=1)
        idx = cv2.dnn.NMSBoxes(boxes.tolist(), scores[keep].tolist(), min(WEAK_SCORE.values()), 0.45)
        result = []
        for i in np.array(idx).flatten():
            x, y, bw_, bh_ = boxes[i]
            result.append((max(0, int(x)), max(0, int(y)), min(w - 1, int(x + bw_)), min(h - 1, int(y + bh_)),
                           float(scores[keep][i]), int(cls[i])))
        return result

    def _zoomed(self, color, have):
        """Non-person boxes found in the ZOOM crops (full-frame px) that the whole frame and earlier crops missed."""
        h, w = color.shape[:2]
        out = []
        for zx1, zy1, zx2, zy2 in ZOOM[self.name]:
            for x1, y1, x2, y2, score, cls in self._detect(color[zy1:zy2, zx1:zx2]):
                cut = (zx1 > 0 and x1 < ZOOM_EDGE_PX) or (zy1 > 0 and y1 < ZOOM_EDGE_PX) \
                    or (zx2 < w and x2 > zx2 - zx1 - 1 - ZOOM_EDGE_PX) or (zy2 < h and y2 > zy2 - zy1 - 1 - ZOOM_EDGE_PX)
                if cls == 0 or cut:
                    continue
                box = (x1 + zx1, y1 + zy1, x2 + zx1, y2 + zy1)
                if not any(b[5] == cls and _iou(box, b[:4]) > 0.3 for b in have + out):
                    out.append((*box, score, cls))
        return out

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
        people, self.objects = [], []
        self.depth = depth                          # aligned depth (mm) of this frame, for objects.py
        boxes = self._detect(color)
        for x1, y1, x2, y2, score, cls in boxes:
            if cls != 0:
                self.objects.append((x1, y1, x2, y2, score, cls))
                continue
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
        camview.publish(self.name, color, people, source=pathlib.Path(sys.argv[0]).name)   # for /view in api/server.py
        if self.name in ZOOM:
            self.objects += self._zoomed(color, self.objects)
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
                cv2.imwrite(str(ROOT / "logs" / "person_view.jpg"), draw(color, people))
                last_save = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        det.close()
