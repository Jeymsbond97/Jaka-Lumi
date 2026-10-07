"""Camera test on the Thor: list the Orbbec cameras, grab colour + depth from one, save a picture.

    python camera_test.py            # camera 0
    python camera_test.py 1          # camera 1

Prints each camera's serial number and the distance (mm) at the image centre,
and saves color_<id>.jpg next to this file. Cover a camera with your hand to see which is head / torso.
"""
import pathlib
import sys

import cv2
import numpy as np
from pyorbbecsdk import Config, Context, OBLogLevel, OBSensorType, Pipeline

cam_id = int(sys.argv[1]) if len(sys.argv) > 1 else 0

ctx = Context()                                       # keep the context alive while devices are used
ctx.set_logger_level(OBLogLevel.NONE)                 # hide SDK noise such as "Timestamp anomaly"
devices = ctx.query_devices()
print(f"{devices.get_count()} camera(s):")
for i in range(devices.get_count()):
    print(f"  [{i}] {devices.get_device_name_by_index(i)}  SN {devices.get_device_serial_number_by_index(i)}")

pipeline = Pipeline(devices.get_device_by_index(cam_id))
config = Config()
for sensor in (OBSensorType.COLOR_SENSOR, OBSensorType.DEPTH_SENSOR):
    config.enable_stream(pipeline.get_stream_profile_list(sensor).get_default_video_stream_profile())
pipeline.start(config)

color = depth_mm = None
for n in range(90):                                   # skip ~30 frames so auto exposure settles
    frames = pipeline.wait_for_frames(100)
    if frames is None:
        continue
    c, d = frames.get_color_frame(), frames.get_depth_frame()
    if c is not None:
        data = np.asanyarray(c.get_data())
        if str(c.get_format()).endswith("MJPG"):
            color = cv2.imdecode(data, cv2.IMREAD_COLOR)
        else:                                         # RGB
            color = cv2.cvtColor(data.reshape(c.get_height(), c.get_width(), 3), cv2.COLOR_RGB2BGR)
    if d is not None and len(d.get_data()) == d.get_width() * d.get_height() * 2:   # skip broken frames
        raw = np.frombuffer(d.get_data(), dtype=np.uint16).reshape(d.get_height(), d.get_width())
        depth_mm = raw.astype(np.float32) * d.get_depth_scale()
    if n >= 30 and color is not None and depth_mm is not None:
        break
pipeline.stop()

if color is None or depth_mm is None:
    sys.exit("No frames. Is another program (e.g. lumi-vision-api) using the camera?")

h, w = depth_mm.shape
centre = depth_mm[h // 2 - 20:h // 2 + 20, w // 2 - 20:w // 2 + 20]
valid = centre[centre > 0]
print(f"colour {color.shape[1]}x{color.shape[0]}, depth {w}x{h}")
print(f"distance at centre: {np.median(valid):.0f} mm" if valid.size else "distance at centre: no depth")
out = pathlib.Path(__file__).with_name(f"color_{cam_id}.jpg")
cv2.imwrite(str(out), color)
print(f"saved {out}")
