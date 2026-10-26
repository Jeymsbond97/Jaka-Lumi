# 06. Cameras and vision

Two Orbbec Gemini 2 L RGB-D cameras (head and torso) connect to the Jetson Thor over USB 3.0. The base camera belongs to the AGV and is used only by its navigation. Camera specifications: [01_HARDWARE.md](01_HARDWARE.md).

| # | Camera | Mounted on | Moves with |
|---|---|---|---|
| 1 | Head camera (Gemini 2 L) | head, `link_4` | head yaw and pitch, waist, lift |
| 2 | Torso camera (Gemini 2 L) | under the handle on the column, `link_2` | waist, lift (same link as the arm base) |
| 3 | Base camera (AGV 3D sensor) | base front | the base; not accessible |

Roles: the head camera watches people while Lumi stands; the torso camera watches the path while driving and is used for objects, picking and calibration. Either camera stands in for the other while it gives no detections (`assistant/lumi.py` `Vision.pick`).

---

## 1. Connect and check

1. USB 3.0 cable from the computer to the base's USB 3.0 port for "head/torso cameras and voice module". USB 3.0 is required: depth runs only on a 5000M link. Check with `cat /sys/bus/usb/devices/*/speed` (5000 for both cameras).
2. Linux: `lsusb` shows each camera as `2bc5:0673 Orbbec 3D Technology International, Inc Orbbec(R) Gemini 2 L(TM)`.
3. udev rule (once): `SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"` in `/etc/udev/rules.d/99-orbbec.rules`.
4. In a VM (VMware): accept "Connect to virtual machine" for each "Orbbec Gemini 2 L" device; plug in before starting the VM or container.
5. In Docker: pass `--device=/dev/bus/usb:/dev/bus/usb` (and `--privileged` or the udev rules), as in the vendor compose files.

### OrbbecViewer

1. Download from https://github.com/orbbec/OrbbecSDK/releases (v1.10.8 in the vendor doc):
   - Windows: `OrbbecSDK_v1.10.8_win64.exe` (SDK + viewer) or `OrbbecViewer_v1.10.8_..._win_x64_release.zip`
   - Ubuntu x64: `OrbbecSDK_v1.10.8_amd64.deb`
   - Jetson / ARM64: `OrbbecSDK_v1.10.8_arm64.deb`
   - macOS (Apple Silicon): `OrbbecViewer_v1.10.8_..._macos_arm64_release.zip`
   - Install guide: https://github.com/orbbec/OrbbecSDK/blob/main/doc/tutorial/English/Installation_guidance.md ; viewer manual: `OrbbecSDK/doc/OrbbecViewer/English/OrbbecViewer.md`
2. The device list shows "Orbbec Gemini 2 L SN:<serial> USB3.0".
3. Streams: Color, Depth, IR, IMU (about 199 fps), point cloud.
4. Each camera's serial number is also printed next to the QR label on the camera; cover one lens to tell head from torso.

The camera service (§3) must be stopped before any other program opens the cameras.

---

## 2. Python (pyorbbecsdk)

Lumi uses `pyorbbecsdk2` from pip (in `.venv`). Source and examples: https://github.com/orbbec/pyorbbecsdk. Built from source on Linux:

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

pipe = open_camera("<serial>")
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

Vendor wrappers: `orbbecCamera.py` (`Camera(serial_number=...)`, `getColorImage()`, `getColorDepthData()` with depth clipped to 20–10 000 mm and a temporal filter), `multi_camera_manager.py` (several cameras by serial), `cam_diagnose_devices.py` / `diagnose_devices.py` (USB diagnostics). All in jaka-robot-demos `dev/jamie` (LUMI_DEMO-v1 and v3) and JAKA_Lumi `main` (`LUMI_DEMO_BMW/LumiAgent/OrbbecSDK/`).

Linux V4L2: the cameras also appear as `/dev/video*` (the NanoOWL demo uses `--camera 4 --resolution 1280x800`).

### ROS 2

`OrbbecSDK_ROS2` (JAKA_Lumi branch `LumiCode`, `Lumi_Teleoperation/src/OrbbecSDK_ROS2`, SDK 1.10.16 libraries for x64 / arm64): `gemini2L.launch.py`, `multi_camera.launch.py`, and the vendor's `multi_gemini2L_synced_sn_template.launch.py` (put each camera's serial in it, then `colcon build`). Config: `config/gemini2L_params.yaml`.

---

## 3. Camera service (`vision/camview.py`)

The camera service is the only program that opens the Orbbec cameras; everything else reads its output. Two programs opening the cameras at once make the SDK reset the devices.

```bash
.venv/bin/python vision/camview.py --serve    # started by api/server.py at boot
.venv/bin/python vision/camview.py --stop     # free the cameras; stays off until --serve or --start
.venv/bin/python vision/camview.py --start
```

Output in `/dev/shm`, per camera (`<cam>` = `head` or `torso`):

| File | Content |
|---|---|
| `lumi_raw_<cam>.jpg` | full-size colour frame (1280 × 720), every frame |
| `lumi_intr_<cam>.json` | colour intrinsics of the running mode (`camview.intrinsics(name)`) |
| `lumi_det_<cam>.json` | detections of every frame: people with boxes, frame size, head yaw; torso also objects measured by `vision/objects.py` |
| `lumi_cam_<cam>.jpg` / `.json` | picture with boxes and people, for the dashboard |
| `lumi_focus_<cam>.json` | written by clients: the person drawn as focus |

Programs that need people use `RemoteDetector` (same `read()` as `person.PersonDetector`). With no reader, detection drops to 1 frame per second.

Operation:

- After `--stop` / `--start` the torso camera may be missing for a few seconds while it re-enumerates (`camera 'torso' not found`): wait and start again.
- A camera opened on a USB 2 link stays colour-only. After cable work, check the link speed (5000) and restart the service to get depth.

Detector: YOLOv8s on the GPU (TensorRT engine `models/yolov8s.engine`), 4–13 ms per frame; CPU fallback YOLOv8n (OpenCV DNN), about 50 ms. The engine is bound to the TensorRT version and GPU it was built on; `person.load_net()` falls back to the CPU and prints why. Building the models: [08_NVIDIA_THOR.md](08_NVIDIA_THOR.md#7-models-and-local-files).

---

## 4. Intrinsics and extrinsics

### Vendor calibrations

Gemini 2 L colour at 1280 × 720, from the vendor's calibrations of their own robots:

| Camera / file | fx | fy | cx | cy | Distortion k1 k2 p1 p2 k3 |
|---|---|---|---|---|---|
| Torso ("hand") camera, `CalibParams-lumi-hand.json` | 609.91 | 609.62 | 638.99 | 365.77 | −0.00962, −0.04825, 0.00200, 0.00015, 0.07460 |
| Head camera, `CalibParams-head0717.json` | 610.45 | 610.56 | 638.65 | 389.06 | −0.02081, 0.01850, 0.00138, 0.00023, −0.00596 |

These give a horizontal FoV of about 92.7° and a vertical FoV of about **61°** at 1280 × 720 (spec: H 94° / V 68° at 1280 × 800).

The same files contain the camera → arm-base transform (eye-to-hand):

| File | Translation (mm) |
|---|---|
| torso `CalibParams-lumi-hand.json` | (5.8, 217.8, −33.4) |
| head `CalibParams-head0717.json` | (81.9, 96.3, 345.8), valid only at the head pose used for that calibration |

The torso camera and the arm both sit on the waist link, so the torso calibration holds at any waist or lift position. The head camera moves relative to the arm (head yaw / pitch), so its transform needs the head joints in the chain.

Mount poses from the sensors URDF: [01_HARDWARE.md](01_HARDWARE.md).

### This robot

| | Torso camera | Head camera |
|---|---|---|
| Colour intrinsics, 1280 × 720 (factory, from `/dev/shm/lumi_intr_<cam>.json`) | fx 608.3, fy 608.4, cx 636.9, cy 363.2 | fx 607.0, fy 607.2, cx 639.1, cy 365.6 |
| Camera → arm base | `data/camera_extrinsics.json` | `data/camera_extrinsics_head.json` (with the body pose it holds for) |
| Hand-eye accuracy (median) | 3.3 mm | 6.0 mm (max 14.2 mm) |

Head camera transform (`vision/head_cam.py`):

- Reference body pose: lift 0, waist −20.3°, head yaw 0°, pitch −5°. Camera at (−114.1, 68.7, 402.6) mm in the arm base frame.
- Head axes in the arm base frame: yaw axis through (−83.1, −26.5, −142.1) mm, direction (−0.017, −0.014, 1.000); pitch axis through (33.2, 6.4, 355.7) mm, direction (0.995, 0.099, −0.005).
- Valid range: yaw −30…0°, pitch −5…+4° (model within 11 mm / 1.4°). Outside it the model is extrapolated.
- `python vision/head_cam.py measure yaw|pitch` measures an axis (the arm holds the marker still while the head turns); `fit` computes both axes into `data/camera_extrinsics_head.json`.

### Calibration tool (`vision/calib.py`)

Eye-to-hand with an ArUco marker on the gripper. Pose angles follow `get_data` `actual_position`: fixed X-Y-Z roll-pitch-yaw, R = Rz·Ry·Rx (`calib.rpy_matrix()`, `flange_pose()`). OpenCV 5.0 on the Thor has no `cv2.calibrateHandEye`; `calib.py` has its own AX = XB solver with least-squares refinement.

| Command | Does |
|---|---|
| `calib.py collect` | the arm is moved by hand; each still pose with the marker in view is saved (Lumi says "Saved, N") |
| `calib.py solve` | computes the camera → arm-base transform |
| `calib.py check` | live difference in mm between camera and arm |
| `calib.py clear` | deletes the samples |

`--camera head` works on the head camera (samples in `data/calib_samples_head/`); the torso samples are in `data/calib_samples/`.

### Pixel → 3D → arm base

```
x_n = (u - cx) / fx,   y_n = (v - cy) / fy
P_camera = depth_mm * [x_n, y_n, 1]
P_base   = R_camera_to_base @ P_camera + T_camera_to_base
```

If the depth at a pixel is 0, the vendor code (`utilfs/tools.py`, `generatorNearPoints`) searches nearby pixels.

---

## 5. Vendor hand-eye calibration

Files: `AutoCalibProccess.py`, `utilfs/handToEyeCalibration.py`, `visualValidCalib.py`, docs `AutoCalibProccess_使用说明.md`, `标定.md`.

- Eye-to-hand: the camera is fixed (torso), the chessboard is held by the arm.
- Board: **8 × 11 inner corners, 10 mm squares** (`boardRowNums`, `boardCowNums`, `boardLength` in `conf/userCmdControl.json`).
- `python AutoCalibProccess.py`: **k** saves an image + the arm TCP pose (kept only when corners are found); collect 15–20 poses with different positions and angles; **p** computes, **q** quits.
- Inside: `cv2.calibrateCamera` → `cv2.solvePnP` per image → `cv2.calibrateHandEye`; quality = position RMS error.
- Output: `conf/{project}_CalibParams.json` (+ images and `{project}_robotTcpPos.txt`).
- Check: `python visualValidCalib.py`, click a pixel, it prints the point in the arm base frame.

---

## 6. Vendor vision demos

All in https://github.com/JAKARobotics/jaka-robot-demos/tree/dev/jamie (copies in JAKA_Lumi `main` / `feat_ros`).

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
- `FileExistsError: /root/.cache/clip` → `rm /root/.cache/clip && mkdir -p /root/.cache/clip`.
- Config `conf/voice_wakeup_config.json`: wake word, AGV IP/port and marker names, camera serials for QR scan and detection, robot IP.

---

## 7. Scene understanding (`vision/scene.py`)

What the cameras see, as facts for the conversation and the skills. It reads the camera service's files (raw JPEG, aligned depth, people and objects with arm-frame positions from `vision/objects.py`) and runs a pose model on the raw frame.

| Function | Gives |
|---|---|
| `sees(name, colour)` | things of a COCO class / colour in either camera: distance, bearing, "on my left / right / in front of me", `position_mm` (arm base frame); a thing seen by both cameras is reported once |
| `people()` | everyone in view, both cameras merged (the two cameras see a near person ~atan(0.25 m / d) apart) |
| `person_in_front()` | the nearest person within 3 m: distance, bearing, chest `position_mm`, facing, gesture (`hand_raised` / `pointing`), shirt and trousers colour, `hands: {left, right: {position_mm, object}}` |
| `object_in_hand()`, `person_holds(name)` | what is in a hand: `{name, colour, hand, position_mm, distance_m, width_mm}`; True / False / None (can't tell) |
| `pointing_target()` | first depth point along shoulder → wrist past the hand, `position_mm` |
| `ask_vlm(question)` | one sentence from `gemma4:26b` on the picture of the person (glasses, hat...) |

- **Pose**: YOLO11s-pose, 17 COCO keypoints, TensorRT engine `models/yolo11s-pose.engine` (`vision/pose.py`), 16–19 ms per 1280 × 720 frame on the GPU.
- **In the hand**: the frame's object boxes plus a second YOLOv8s pass on a 320 px square around each hand (wrist + 0.35 × forearm). A box counts when it is a handheld class, within the hand region, and its depth is within 0.35 m of the wrist's. Without usable depth the box centre must be on the hand.
- **Depth timing**: depth is written every 0.5 s, people and the JPEG every frame. When the depth at a person differs from the camera service's distance by more than 0.4 m, that frame's depth is not used (positions None, no "empty hand" claim).
- **Own body**: the robot's own body appears at the bottom edge of the head camera and the top edge of the torso camera (arm, held object). Boxes touching that edge nearer than 0.8 m (or unmeasured) are ignored.
- **Speed**: `person_in_front()` 50–60 ms with the models loaded (first call ~0.8 s; `seeing.warm_up()` loads them when the assistant starts). `snapshot()` 20 ms.
- **VLM**: `gemma4:26b` with a 448 px picture, about 5 s on an idle GPU, longer while other LLM work runs. Used only for what detections can't answer; time limit 12 s, then "I can't tell".
- **Test frames**: `tests/data/scene_*`; `python vision/scene.py --save tests/data/<name>` saves the current frames. Check: `tests/test_scene.py`.
