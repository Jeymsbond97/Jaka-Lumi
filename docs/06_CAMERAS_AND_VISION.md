# 06. Cameras and vision

Two Orbbec Gemini 2 L RGB-D cameras (head and torso) connect to **our** computer over USB 3.0. The base camera belongs to the AGV and is only used by its navigation. Specs: [01_HARDWARE.md](01_HARDWARE.md#4-cameras).

| # | Camera | Mounted on | Moves with |
|---|---|---|---|
| 1 | Head camera (Gemini 2 L) | head, `link_4` | head yaw and pitch, waist, lift |
| 2 | Torso camera (Gemini 2 L) | under the handle on the column, `link_2` | waist, lift (same link as the arm base) |
| 3 | Base camera (AGV 3D sensor) | base front | the base; not accessible to us |

---

## 1. Connect and check

1. USB 3.0 cable from the computer to the base's USB 3.0 port for "head/torso cameras and voice module". USB 3.0 is required.
2. Linux: `lsusb` must show the cameras as `2bc5:0673 Orbbec 3D Technology International, Inc Orbbec(R) Gemini 2 L(TM)` (one line per camera).
3. In a VM (VMware): accept "Connect to virtual machine" for each "Orbbec Gemini 2 L" device; plug before starting the VM/container.
4. In Docker: pass `--device=/dev/bus/usb:/dev/bus/usb` (and `--privileged` or the udev rules), as in the vendor compose files.

### OrbbecViewer (quick visual check)

1. Download from https://github.com/orbbec/OrbbecSDK/releases (v1.10.8 used in the vendor doc):
   - Windows: `OrbbecSDK_v1.10.8_win64.exe` (SDK + viewer) or `OrbbecViewer_v1.10.8_..._win_x64_release.zip`
   - Ubuntu x64: `OrbbecSDK_v1.10.8_amd64.deb`
   - Jetson / ARM64: `OrbbecSDK_v1.10.8_arm64.deb`
   - macOS (Apple Silicon): `OrbbecViewer_v1.10.8_..._macos_arm64_release.zip`
   - Install guide: https://github.com/orbbec/OrbbecSDK/blob/main/doc/tutorial/English/Installation_guidance.md ; viewer manual: `OrbbecSDK/doc/OrbbecViewer/English/OrbbecViewer.md`
2. Start OrbbecViewer: the device list shows "Orbbec Gemini 2 L SN:<serial> USB3.0".
3. Turn on Color, Depth, IR, IMU, point cloud. The vendor screenshot (`private/images/camera-03-orbbecviewer-streams.png`) shows all four streams and the IMU at about 199 fps.
4. Write down each camera's **serial number** (also printed next to the QR label on the camera) and which one is head / torso (cover one lens to tell).

---

## 2. Python (pyorbbecsdk)

Install: https://github.com/orbbec/pyorbbecsdk (build or wheel). On Linux install the udev rules once:

```bash
sudo bash ./scripts/install_udev_rules.sh
sudo udevadm control --reload-rules && sudo udevadm trigger
export PYTHONPATH=$PYTHONPATH:$(pwd)/install/lib/
python3 examples/depth_viewer.py          # test
```

Read colour + depth from a camera chosen by serial:

```python
import numpy as np
from pyorbbecsdk import Context, Pipeline, Config, OBSensorType, OBAlignMode, OBFormat

def open_camera(serial=None):
    devices = Context().query_devices()
    for i in range(devices.get_count()):
        dev = devices.get_device_by_index(i)
        if serial is None or dev.get_device_info().get_serial_number() == serial:
            return Pipeline(dev)
    raise RuntimeError(f"camera {serial} not found")

pipe = open_camera("AY8V743....")            # our head camera serial
cfg = Config()
cfg.enable_stream(pipe.get_stream_profile_list(OBSensorType.COLOR_SENSOR).get_default_video_stream_profile())
cfg.enable_stream(pipe.get_stream_profile_list(OBSensorType.DEPTH_SENSOR).get_default_video_stream_profile())
cfg.set_align_mode(OBAlignMode.SW_MODE)      # depth aligned to colour (HW_MODE also possible on Gemini 2 L)
pipe.enable_frame_sync()
pipe.start(cfg)
frames = pipe.wait_for_frames(1000)
depth = frames.get_depth_frame()
if depth.get_format() == OBFormat.Y16:
    h, w = depth.get_height(), depth.get_width()
    depth_mm = np.frombuffer(depth.get_data(), np.uint16).reshape(h, w) * depth.get_depth_scale()
color = frames.get_color_frame()             # convert with frame_to_bgr_image() from the Orbbec examples (utils.py)
pipe.stop()
```

Vendor wrappers to reuse: `orbbecCamera.py` (`Camera(serial_number=...)`, `getColorImage()`, `getColorDepthData()` with depth clipped to 20–10 000 mm and a temporal filter), `multi_camera_manager.py` (several cameras by serial), `cam_diagnose_devices.py` / `diagnose_devices.py` (USB troubleshooting). All in jaka-robot-demos `dev/jamie` (LUMI_DEMO-v1 and v3) and JAKA_Lumi `main` (`LUMI_DEMO_BMW/LumiAgent/OrbbecSDK/`).

Linux V4L2 path (used by the NanoOWL demo): the cameras also appear as `/dev/video*` (`--camera 4 --resolution 1280x800`).

### ROS 2

`OrbbecSDK_ROS2` (in JAKA_Lumi `LumiCode` branch `Lumi_Teleoperation/src/OrbbecSDK_ROS2`, SDK 1.10.16 libraries for x64 / arm64): `gemini2L.launch.py`, `multi_camera.launch.py`, and the vendor's `multi_gemini2L_synced_sn_template.launch.py` (put each camera's serial in it, then `colcon build`). Config: `config/gemini2L_params.yaml`.

---

## 3. Intrinsics and extrinsics

Gemini 2 L colour at 1280 × 720 (vendor calibrations of their robots; recalibrate ours):

| Camera / file | fx | fy | cx | cy | Distortion k1 k2 p1 p2 k3 |
|---|---|---|---|---|---|
| Torso ("hand") camera, `CalibParams-lumi-hand.json` | 609.91 | 609.62 | 638.99 | 365.77 | −0.00962, −0.04825, 0.00200, 0.00015, 0.07460 |
| Head camera, `CalibParams-head0717.json` | 610.45 | 610.56 | 638.65 | 389.06 | −0.02081, 0.01850, 0.00138, 0.00023, −0.00596 |

These give a horizontal FoV of about 92.7° and a vertical FoV of about **61°** at 1280 × 720 (spec: H 94° / V 68° at 1280 × 800).

The same files contain the camera → arm-base transform (eye-to-hand calibration):

| File | Translation (mm) |
|---|---|
| torso `CalibParams-lumi-hand.json` | (5.8, 217.8, −33.4) |
| head `CalibParams-head0717.json` | (81.9, 96.3, 345.8), valid only for the head pose used during calibration |

The torso camera and the arm both sit on the waist link, so its calibration stays valid when the waist or lift moves. The head camera moves relative to the arm (head yaw/pitch), so its calibration only holds at one head pose unless the head joints are added to the transform chain (use the URDF + `Camera3_Link`).

Mount poses from the sensors URDF: see [01_HARDWARE.md](01_HARDWARE.md#7-kinematic-model-files).

### Pixel → 3D → arm base

From `utilfs/tools.py`:

```
x_n = (u - cx) / fx,   y_n = (v - cy) / fy
P_camera = depth_mm * [x_n, y_n, 1]
P_base   = R_camera_to_base @ P_camera + T_camera_to_base
```

If the depth at the pixel is 0, the vendor code searches nearby pixels (`generatorNearPoints`, interval / times from the config).

---

## 4. Hand-eye calibration (vendor procedure)

Files: `AutoCalibProccess.py`, `utilfs/handToEyeCalibration.py`, `visualValidCalib.py`, docs `AutoCalibProccess_使用说明.md`, `标定.md`.

- Eye-to-hand: the camera is fixed (torso), the chessboard is held by the arm.
- Board: **8 × 11 inner corners, 10 mm squares** (`boardRowNums`, `boardCowNums`, `boardLength` in `conf/userCmdControl.json`).
- Run `python AutoCalibProccess.py`: press **k** to save an image + the arm TCP pose (only kept when corners are found), collect 15–20 poses with different positions and angles, press **p** to compute, **q** to quit.
- Inside: `cv2.calibrateCamera` → `cv2.solvePnP` per image → `cv2.calibrateHandEye`; quality = position RMS error.
- Output: `conf/{project}_CalibParams.json` (+ images and `{project}_robotTcpPos.txt`).
- Check: `python visualValidCalib.py`, click a pixel, it prints the point in the arm base frame; touch it with the arm slowly.

---

## 5. Vision demos (vendor)

All in https://github.com/JAKARobotics/jaka-robot-demos/tree/dev/jamie (also copies in JAKA_Lumi `main` / `feat_ros`).

| Demo | What it does | Platform | Detector |
|---|---|---|---|
| LUMI_DEMO-v1 | Fixed-station pick: detect object + target, pick, place | x86_64 PC | Alibaba Qwen-VL (DashScope API) |
| LUMI_DEMO-v2 | Multi-station: AGV marker per station, body + arm home per station, pick/place | x86_64 PC | Qwen-VL |
| LUMI_DEMO-v3 | Voice wake-up ("lumi") + NanoOWL zero-shot detection + QR scan + AGV + arm (medicine picking) | Jetson Orin (ARM64), Docker | NanoOWL (OWL-ViT, TensorRT) / Qwen-VL |
| BMW vending demo | Voice agent sells drinks: fixed joint-space picks | Linux PC | — |

### v1 / v2 setup

```bash
pip install -r requirements.txt              # opencv-python, numpy, matplotlib, dashscope, ...
export DASHSCOPE_API_KEY="..."               # https://dashscope.console.aliyun.com/apiKey
export LD_LIBRARY_PATH=/path/to/JAKA_SDK_LINUX:$LD_LIBRARY_PATH
python AutoCalibProccess.py                  # once, or reuse the provided torso calibration
python visualDetect_ali.py                   # v1 (add --auto, --camera-sn SN, --list-cameras in v2)
python multi_station_demo.py                 # v2
```

`conf/userCmdControl.json` (v1): `cameraParams` (align SW, sync, image path), `objects.moveObjects` (e.g. "yellow doll") and `objects.putObject` ("box"), `robotParams.basePose` (start joints, rad), `relativeUpMotionHeight` (mm), offsets X/Y/Z/Zput (mm), `calibrateParams` (robot IP, board), `genNearPointParams`. v2 adds `operationMode` (`both` / `grasp_only` / `put_only` / `grasp_priority`), `systemConfig` (robot, AGV, body URLs), `extAxisLimits`, `stations` (name, AGV marker, arm home, body home, mode).

Vendor prompt to the VLM (translated): "Please box the N kinds of objects A and B in the image." Reply: JSON list of `{"label": ..., "bbox_2d": [x1, y1, x2, y2]}`. Then: box centre → depth → `pixel_to_world` → IK → pick.

### v3 (Jetson, Docker)

- Compose: image `lumi-demo-owl:v5audio`, `runtime: nvidia`, `network_mode: host`, `privileged: true`, devices `/dev/snd`, `/dev/bus/usb` (v3 compose also `/dev/video*`, `/dev/media*`, udev rules), volume `./lumi_nanoowl:/opt/nanoowl`, `DISPLAY` for GUI.
- Run: `./docker-compose-linux-aarch64 up --no-recreate -d`, then inside: `export LD_LIBRARY_PATH=/opt/nanoowl/JAKA_SDK_ARM:$LD_LIBRARY_PATH`, `python3 start_voice_wakeup_system.py --mode full` (or `owl`, `test`).
- Detector: `python3 lumi_demo_owl.py /opt/nanoowl/data/owl_image_encoder_patch32.engine --camera-sn <SN...>` (web UI on port 7860), or `lumi_demo_ali.py --camera-sn <SN>`.
- Known fix: `FileExistsError: /root/.cache/clip` → `rm /root/.cache/clip && mkdir -p /root/.cache/clip`.
- Config `conf/voice_wakeup_config.json`: wake word, AGV IP/port and marker names, camera serials for QR scan and detection, robot IP.

---

## 6. Plan for our work

1. List the cameras and record serial → role.
2. Grab colour + depth from both; measure intrinsics (`pipeline` profile intrinsics or OpenCV calibration).
3. Calibrate the torso camera to the arm base (vendor procedure).
4. Head camera: compute its pose from the URDF chain (`link_4` → `Camera3_Link`) with the body joint angles from `/api/extaxis/status`, verify against the torso camera on a common target.
5. Person / face detection on the head camera for "look at the speaker" ([07_VOICE_AND_AUDIO.md](07_VOICE_AND_AUDIO.md)).
