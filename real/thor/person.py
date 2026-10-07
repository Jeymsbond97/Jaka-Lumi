"""Find people in front of the robot: Orbbec colour + depth, YOLOv8n (ONNX, OpenCV DNN on the CPU).

    python person.py             # camera 0, print the people seen (distance, angle) for 20 s
    python person.py 0 --save    # also save person_view.jpg with boxes every second

Each person: box in colour pixels, score, distance in metres (median depth inside the box centre),
angle in degrees from the camera's optical axis (positive = person is on the image's left side).
"""
import pathlib
import sys
import time

import cv2
import numpy as np
from pyorbbecsdk import (AlignFilter, Config, Context, OBLogLevel, OBSensorType, OBStreamType,
                         Pipeline)

HERE = pathlib.Path(__file__).resolve().parent
MODEL = HERE / "models" / "yolov8n.onnx"
COLOR_HFOV = 94.0            # deg, Gemini 2 L colour camera
SIZE = 640                   # YOLO input size
MIN_SCORE = 0.5


class PersonDetector:
    def __init__(self, camera=0):
        self.ctx = Context()                        # keep alive while the device is used
        self.ctx.set_logger_level(OBLogLevel.NONE)
        devices = self.ctx.query_devices()
        self.serial = devices.get_device_serial_number_by_index(camera)
        self.pipeline = Pipeline(devices.get_device_by_index(camera))
        config = Config()
        for sensor in (OBSensorType.COLOR_SENSOR, OBSensorType.DEPTH_SENSOR):
            config.enable_stream(self.pipeline.get_stream_profile_list(sensor).get_default_video_stream_profile())
        self.pipeline.start(config)
        self.align = AlignFilter(align_to_stream=OBStreamType.COLOR_STREAM)   # depth pixels -> colour pixels
        self.net = cv2.dnn.readNetFromONNX(str(MODEL))

    def close(self):
        self.pipeline.stop()

    def _frames(self):
        """(colour BGR image, depth in mm aligned to it) or (None, None)."""
        frames = self.pipeline.wait_for_frames(200)
        if frames is None:
            return None, None
        frames = self.align.process(frames)
        if frames is None:
            return None, None
        frames = frames.as_frame_set()
        c, d = frames.get_color_frame(), frames.get_depth_frame()
        if c is None or d is None or len(d.get_data()) != d.get_width() * d.get_height() * 2:
            return None, None
        data = np.asanyarray(c.get_data())
        if str(c.get_format()).endswith("MJPG"):
            color = cv2.imdecode(data, cv2.IMREAD_COLOR)
        else:
            color = cv2.cvtColor(data.reshape(c.get_height(), c.get_width(), 3), cv2.COLOR_RGB2BGR)
        depth = np.frombuffer(d.get_data(), dtype=np.uint16).reshape(d.get_height(), d.get_width())
        depth = depth.astype(np.float32) * d.get_depth_scale()
        if color is None or color.shape[:2] != depth.shape:
            return None, None
        return color, depth

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
            return None, []
        w = color.shape[1]
        people = []
        for x1, y1, x2, y2, score in self._detect(color):
            # centre part of the box (torso), ignore holes (0) in the depth image
            cx1, cx2 = x1 + (x2 - x1) // 4, x2 - (x2 - x1) // 4
            cy1, cy2 = y1 + (y2 - y1) // 4, y2 - (y2 - y1) // 2
            patch = depth[cy1:cy2, cx1:cx2]
            valid = patch[patch > 0]
            dist = float(np.median(valid)) / 1000 if valid.size > 50 else None
            angle = -((x1 + x2) / 2 - w / 2) / (w / 2) * (COLOR_HFOV / 2)
            people.append({"box": (x1, y1, x2, y2), "score": round(score, 2),
                           "distance_m": None if dist is None else round(dist, 2), "angle_deg": round(angle, 1)})
        people.sort(key=lambda p: p["distance_m"] if p["distance_m"] is not None else 99)
        return color, people


def draw(color, people):
    for p in people:
        x1, y1, x2, y2 = p["box"]
        cv2.rectangle(color, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(color, f"{p['distance_m']} m  {p['angle_deg']} deg", (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    return color


if __name__ == "__main__":
    cam = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 0
    save = "--save" in sys.argv
    det = PersonDetector(cam)
    print(f"camera {cam} (SN {det.serial}) running; Ctrl+C to stop")
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
