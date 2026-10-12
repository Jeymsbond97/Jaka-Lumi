"""Camera stability test on the Thor: stream colour + depth from one camera and count full frames.

    python camera_fps.py head            # head camera, 30 s, the modes person.py / lumi.py use
    python camera_fps.py torso 60        # torso camera, 60 s
    python camera_fps.py head --default  # the camera's own default modes (the old, broken USB 2 case)

The camera is chosen by name (head / torso), serial number or index, like person.py.
A healthy camera gives the asked fps (15 in person.py's modes) with almost no missed frames.
Ctrl+C stops early and prints the result so far.
"""
import sys
import time

from pyorbbecsdk import Config, OBSensorType

import person

import camview

if camview.service_pid():
    sys.exit("The camera service (camview.py) has the cameras. Stop it first: python camview.py --stop (and --start afterwards) "
             "(api.py / lumi.py start it again when needed).")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
camera = args[0] if args else "head"
seconds = float(args[1]) if len(args) > 1 else 30
default = "--default" in sys.argv

pipeline, serial, name = person.open_camera(camera)
config = Config()
for sensor, mode in ((OBSensorType.COLOR_SENSOR, person.COLOR_MODE), (OBSensorType.DEPTH_SENSOR, person.DEPTH_MODE)):
    profiles = pipeline.get_stream_profile_list(sensor)
    p = profiles.get_default_video_stream_profile() if default else person._profile(pipeline, sensor, mode)
    config.enable_stream(p)
    print(f"  {sensor}: {p.get_width()}x{p.get_height()} {str(p.get_format()).split('.')[-1]} @ {p.get_fps()} fps")
print(f"{name} camera  SN {serial}, {seconds:.0f} s" + ("  (default modes)" if default else ""))
pipeline.start(config)

full = missed = 0
start = last = time.time()
try:
    while time.time() - start < seconds:
        frames = pipeline.wait_for_frames(1000)
        if frames is None or frames.get_color_frame() is None or frames.get_depth_frame() is None:
            missed += 1
        else:
            full += 1
        if time.time() - last >= 5:                   # progress every 5 s
            last = time.time()
            print(f"  {last - start:4.0f} s: {full / (last - start):5.1f} fps, missed {missed}")
except KeyboardInterrupt:                             # Ctrl+C: stop early and still print the result
    pass
finally:
    pipeline.stop()

elapsed = time.time() - start
print(f"{name} camera: {full / elapsed:.1f} fps, {missed} missed in {elapsed:.0f} s")
