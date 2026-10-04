# 01. Hardware

What the JAKA Lumi is made of, with every specification found in the official material. Sources are listed in [12_SOURCES.md](12_SOURCES.md). Screenshots mentioned as `private/images/...` are local only.

Values marked **verify** disagree between sources or are undocumented.

---

## 1. The robot at a glance

Lumi is a wheeled mobile manipulator ("embodied AI platform"): an AGV base, a lifting column, a waist joint, a 2-joint head, a 6-joint arm on the side of the column, two RGB-D cameras and a microphone array.

| Part | What it is | Controlled through | Detail doc |
|---|---|---|---|
| Mobile base (AGV) | Differential-drive base with 2D lidar SLAM ("WATER" platform) | TCP commands to `192.168.10.10:31001`; web UI `:9001` | [05_AGV_BASE.md](05_AGV_BASE.md) |
| Lift, waist, head (4 joints) | Lifting column, waist turn, head yaw, head pitch | HTTP `192.168.10.90:5000/api/extaxis/...`; also external axes in Cobo π | [03_BODY_LIFT_WAIST_HEAD.md](03_BODY_LIFT_WAIST_HEAD.md) |
| Arm (6 joints) | JAKA Mini 2 ("MiniCobo2") with a MiniCab controller inside the base | JAKA SDK `jkrc`; Cobo π web UI `https://192.168.10.90`; JAKA App | [04_ARM.md](04_ARM.md) |
| Head and torso cameras | Orbbec Gemini 2 L RGB-D (+ IMU) | USB 3.0 to the host computer | [06_CAMERAS_AND_VISION.md](06_CAMERAS_AND_VISION.md) |
| Base camera, lidar, ultrasonics, IMU, bumper | Built into the AGV, used by its navigation | AGV API | [05_AGV_BASE.md](05_AGV_BASE.md) |
| Voice module | iFlytek AIUI XF-USB-MC, 6-mic ring array | USB audio to the host computer | [07_VOICE_AND_AUDIO.md](07_VOICE_AND_AUDIO.md) |
| Main AI computer (optional, separate) | Jetson Orin NX / AGX Orin / AGX Thor; the company uses an AGX Thor | Ethernet / Wi-Fi to the robot network | [08_NVIDIA_THOR.md](08_NVIDIA_THOR.md) |
| Gripper | **None mounted yet** | Tool I/O (RS485) or USB serial | [10_GRIPPER.md](10_GRIPPER.md) |

Camera positions on the robot (`private/images/camera-02-demo-download-camera-positions.png`): **1** head (front of the head), **2** torso (under the handle on the column), **3** base front (the AGV's own camera).

### Whole robot

| Item | Value | Source |
|---|---|---|
| Size (W × D × H) | 510 × 510 × 1460–1860 mm (height changes with the lift) | Lumi manual 5.1.1, brochure |
| Weight | 95.6 kg | Brochure |
| Degrees of freedom | 12 = lift 1 + waist 1 + head 2 + arm 6 + 2 drive wheels | Lumi manual 5.1.1 |
| Power | 800 W (manual) / 1500 W (brochure) **verify** | |
| Arm and controller supply | 48 V DC; base battery 24 V | Lumi manual, AGV spec |
| Arm payload | 2 kg | Lumi manual, brochure, web doc 3.3.5 |
| Lift range | 0–400 mm (hardware); 0–300 mm (body API doc) **verify** | see [03](03_BODY_LIFT_WAIST_HEAD.md#joint-ranges) |
| Waist | ±160° (hardware); ±140° (body API doc) | |
| Head yaw (neck) | ±180° | |
| Head pitch | −5…+35° | |
| End-effector options (vendor) | 3-finger or 5-finger dexterous hands, electric grippers, soft grippers | Brochure |
| Simulation support (vendor claim) | "natively compatible with MuJoCo and NVIDIA Isaac Sim" | Brochure |

---

## 2. Arm: JAKA Mini 2

From the Lumi manual 5.1.2, Mini hardware manual 3.3 and web doc 3.3.5.

| Item | Value |
|---|---|
| Model | JAKA Mini 2. Cobo π names it `MiniCobo2` on our robot. (The teleop hardware list says "MiniCobo"; MiniCobo is the 1 kg / 24 V sibling. Our robot reports MiniCobo**2**, i.e. the Mini 2.) |
| Payload | 2 kg |
| Weight | 9.9 kg |
| Reach | 580 mm |
| Repeatability | ±0.1 mm |
| Max tool speed | 1 m/s |
| Rated power | 180 W |
| Supply | 48 V DC; under-voltage protection at ≤ 30 V |
| Communication | TCP/IP, Modbus TCP, Modbus RTU, PROFINET, EtherNet/IP |
| Tool I/O | 2 DI, 2 DO, 2 AI, 24 V supply, M8 8-pin connector (pinout in [04_ARM.md](04_ARM.md#8-tool-io-connector-m8-8-pin-tio-v3)) |
| Base diameter | 124 mm |
| IP rating | IP40 |
| Mounting | Any angle; on Lumi it hangs on the side of the column (on the waist link) |
| Max load on the arm base | Fx/Fy 120 N, Fz 140 N, Mx/My 100 Nm, Mz 90 Nm (not all at once) |
| Max flange torque | 14 Nm |
| Flange | ISO 9409-1, pitch circle 50 mm, 4 × M6 (15.3 Nm, screws grade ≥ 12.9), 1 × Ø6 H7 locating pin hole rotated 45° clockwise from +Xm |
| Flange buttons | FREE (hand-guiding / drag), POINT (record a point in the app) |
| Ring light at the arm base | blue = powered not enabled, green = enabled, red = fault / protective stop, yellow = drag mode, yellow fast flashing = paused / single step |

| Joint | Range | URDF joint | URDF limit (rad) |
|---|---|---|---|
| J1 | ±360° | `l_a1` | ±6.2831 |
| J2 | ±125° | `l_a2` | ±2.1816 |
| J3 | ±130° | `l_a3` | ±2.2689 |
| J4 | ±360° | `l_a4` | ±6.2831 |
| J5 | ±120° | `l_a5` | ±2.0943 |
| J6 | ±360° | `l_a6` | ±6.2831 |

### Arm controller: MiniCab

| Item | Value |
|---|---|
| Location | Inside the AGV base |
| Size / weight | 180 × 46.6 × 128 mm, 1.1 kg |
| Supply | 48 V DC (Mini 2) |
| I/O | 7 configurable channels (NPN, triggered by 0 V) |
| Network | Wi-Fi (DHCP only) and two LAN ports: LAN1 fixed at `10.5.5.x`, LAN2 configurable (cannot be set to `10.5.5.x`) |
| Wi-Fi reset | Hold the button next to the antenna for > 10 s (gateway goes back to factory settings) |
| Brake voltage | Must be set in the app when an external power supply is used (robot powered off and disabled) |
| Controller software (seen in vendor docs) | 1.7.1-46-X64-minicab for teleoperation; newer robots ship controller 3.2 with Cobo π. See [04_ARM.md](04_ARM.md#2-controller-versions-17-vs-32) |
| Absolute limits | logic/power supply −0.3…40 V absolute; recommended 40–56 V (48 V typical); average current 3.75 A, peak 12.5 A |
| Typical power | off 1 W, on 12 W, with arm power up to 30 W |

### Safety system (arm)

EN ISO 10218-1, ISO 13849-1 PL d Cat. 3, 27 safety functions in 8 groups: emergency stop, protective stop, motion state, manual mode, speed monitoring, torque and power limits, collision protection, position monitoring. Stop categories: Cat. 0 (power cut), Cat. 1 (controlled stop, then power off; E-stop button), Cat. 2 (stops on path, stays enabled; safety functions). Details in [11_SAFETY.md](11_SAFETY.md) and [04_ARM.md](04_ARM.md).

---

## 3. Mobile base (AGV)

From the AGV spec sheet, Lumi manual 5.1.4 and the chassis manual.

| Item | Value |
|---|---|
| Size | 510 × 510 × 280 mm |
| Weight | 50 kg |
| Payload | 60 kg rated, 80 kg max on flat floor |
| Drive | Differential, 2 × 160 W hub servo motors |
| Wheels | 2 drive, 4 casters, 1 auxiliary; swing-arm active suspension |
| Turning radius | 307 mm |
| Ground clearance | 25 mm |
| Speed | 0.6 m/s default, 1.2 m/s max (API joystick command limited to ±0.5 m/s, ±1.0 rad/s) |
| Repeatability | ±5 cm |
| Obstacles | Step 15 mm, slope 8°, gap 30 mm; needs a 700 mm wide passage |
| Battery | 24 V (21–29.4 V), 45 Ah Li-ion; about 10 h with ≤ 50 kg load (spec sheet: 45 h idle, 25 h empty driving, 13 h with 60 kg) |
| Battery life | 1000 full cycles to ≥ 75 % |
| Charging dock | 100–240 V AC in, 29.4 V 6 A out |
| Computer | Intel J1900 quad core, Linux (navigation only; not for user code) |
| Mapping | 50 000 m² per map, 80 000 m² max operating area |
| Upper-body recommendations (chassis manual) | total height ≤ 110 cm, centre of mass ≤ 50 cm above ground for full climbing ability; mount through 9 × M5 holes, max 10 mm screw depth |

### Sensors in the base

| Sensor | Specification |
|---|---|
| 2D lidar | 0.02–10 m, 240°, ±20 mm, 10 mm resolution, 30 Hz, IP65 |
| 3D camera (front, looks forward/up) | 0.35–2 m, FoV H 58.4° × V 45.5° |
| Ultrasonic | 5 units, 0.03–0.55 m, ≈ 3 cm accuracy, < 15° cone |
| IMU | 6-axis |
| Infrared | 1 m, ±2–6° |
| Bumper | triggers at 5–7 mm travel, > 20 N |

### Connectors on the back of the base

From the Lumi manual 6.5, the quick manual, web doc 3.2 and the chassis ports docx.

| Connector | Purpose |
|---|---|
| USB 3.0 (1) | **Head camera, torso camera and voice module.** Plug the host computer in here |
| Gigabit Ethernet (RJ45, "upper computer") | Host computer. Fixed `192.168.10.x` network (robot at `192.168.10.90`) |
| USB 3.0 (2) | MiniCab control cabinet inside the base |
| External RJ45 | Extra network port |
| Charging contacts | Contact charging on the dock (LED breathes while charging) |
| 48 V manual charging socket | Behind a magnetic cover on the right side; remove the cable before driving (tasks fail while it is plugged) |
| 48 V and 24 V aviation sockets | Upper-body power |
| Main power switch | Underneath, next to the rear right caster. Off from the factory; "pull" it on at first start |
| Contact power switch | Hidden underneath |
| E-stop | Built into the chassis; another red E-stop button is on the column |

### Lights and buttons

| Base LED strip | Meaning |
|---|---|
| Green flashing | Power on, computer booting |
| White steady | Booted, normal |
| White / blue-white breathing | Charging (also while off and charging) |
| White / blue-white flashing | E-stop pressed |

| Charging dock light | Meaning |
|---|---|
| Green | Dock powered, not charging, or charging with battery ≥ 90 % |
| Red | Charging, battery < 90 % |

Power button: hold → two short beeps (LED purple) → release after the third, long beep (LED flashes green while booting). Off: hold → seven short beeps → release on the eighth, long beep.

**E-stop (red button on the column):** cuts arm power and stops the lift column; the base becomes free to push by hand. After releasing the E-stop the base cannot be pushed any more. (Web doc 3.3.3.4, `private/images/setup-01-wifi-wired-control-estop.png`.)

---

## 4. Cameras

| Item | Value |
|---|---|
| Model | Orbbec Gemini 2 L (head and torso), USB VID:PID `2bc5:0673` |
| Depth range | 0.02–10 m (brochure: 0.2–10 m) |
| Depth FoV | H 91° / V 66° / D 101° ± 3° |
| Depth resolution | 1280 × 800 @ 30 fps, 640 × 400 @ 60 fps |
| Colour FoV | H 94° / V 68° / D 104° ± 3° |
| Colour resolution | 1280 × 800 @ 30 fps, 1280 × 720 @ 60 fps |
| Other streams | IR, IMU (accelerometer + gyroscope, ~200 Hz in OrbbecViewer) |
| Interface | USB 3.0 (required; USB 2.0 is not enough) |

Calibrated intrinsics, mount poses and software: [06_CAMERAS_AND_VISION.md](06_CAMERAS_AND_VISION.md).

---

## 5. Voice module

| Item | Value |
|---|---|
| Model | iFlytek AIUI XF-USB-MC (shows up as the audio device `AIUI-USB-MC`) |
| Microphones | 6-mic ring array in the head |
| SNR | > 70 dB |
| Wake-up / recognition distance | 3–5 m (more with an external mic) |
| Sound localisation | 4 mics 180°, 6 mics 360°, ±15° |
| OS support | Windows, Linux, Android |

Use: [07_VOICE_AND_AUDIO.md](07_VOICE_AND_AUDIO.md).

---

## 6. Main AI computer options

JAKA's recommendation (web doc 3.0, `private/images/web-03-main-controller-comparison.png`):

| | No extra controller | Jetson Orin NX | Jetson AGX Orin | Jetson AGX Thor |
|---|---|---|---|---|
| Class | — | light, 70 TOPS | high, 275 TOPS | flagship, 2070 TOPS |
| Use when | No vision or voice; control body, arm, base only; wireless remote control | Body control only, or ≤ 2 × 1080p @ 15 fps light AI | Vision and voice needed, LLM ≤ 7B or VLA ≤ 13B, 4–8 × 1080p @ 30 fps | Large multimodal models (≥ 30B VLA, ACT, LLM + vision), 8K, multi-robot |
| Typical tasks | Trajectory teaching, body + base control, AGV transport, simple palletising | Same | Vision-guided assembly, barcode + OCR, voice picking, online quality check | Voice interaction, ACT 30 Hz end-to-end, complex semantic segmentation, LLM trajectory generation |
| Measured (vendor) | — | YOLOv5n 640×480 25 FPS; Whisper-Tiny 0.8× real time | YOLOv8x 640×640 8 ch 30 FPS; Whisper-Small 1.2× RT; LLaMA-7B INT4 18 tok/s | ACT 512×512 2 cameras 30 Hz; LLaMA-30B INT4 28 tok/s; 8K AV1 60 FPS |
| CPU | — | 6/8-core Cortex-A78AE | 12-core Cortex-A78AE 2.2 GHz | 72-core Arm v9 (Grace-Next) 2.6 GHz |
| GPU | — | 1024-core Ampere | 2048-core Ampere 1.3 GHz | Blackwell 1.57 GHz |
| Memory | — | 8 / 16 GB LPDDR5 | 32 / 64 GB LPDDR5 | up to 128 GB |
| Power | — | 10–25 W | 15–60 W | 30–120 W |

Our robot setup uses a **Jetson AGX Thor**: [08_NVIDIA_THOR.md](08_NVIDIA_THOR.md).

The vendor's education kit (`private/images/gripper-01-vendor-hardware-list.png`) lists: JAKA Mini2 arm, lift + voice module, **DH-PGEA-50** gripper with 3D-printed fingers, lidar base, 3D camera, optional 16" monitor, **Jetson AGX Orin** main controller.

---

## 7. Kinematic model files

| File | Where |
|---|---|
| URDF (same kinematics in all copies) | this repo `lumi_description/urdf/jaka_lumi.urdf`; JAKA_Lumi `feat_ros` branch `jaka_lumi_ros/src/jaka_lumi_description/urdf/jaka_lumi.urdf` (checked: identical joints, origins and limits) |
| URDF with cameras, lidar and casters | JAKA_Lumi `main`: `02. .../JAKA-Lumi-sensors-v3/urdf/JAKA-Lumi-sensors-v3.urdf` |
| USD for Isaac Sim | `feat_ros`: `jaka_lumi_description/urdf/jaka_lumi/*.usd` |
| MoveIt 2 config | `feat_ros`: `jaka_lumi_moveit_config/` |
| STEP model (65 MB) and 2D drawing | JAKA_Lumi `main`: `02. .../Lumi Models [模型说明]/` |

Sensor mount poses from the sensors URDF (in `base_link`, whose front is −y):

| Link | Parent | xyz (m) | rpy (rad) |
|---|---|---|---|
| `Camera3_Link` (head camera) | `link_4` | (−0.0552, −0.0665, −0.001) | (−1.5708, −1.5708, 0) |
| `Camera2_Link` (torso camera) | `link_2` | (0.1257, 0.011, 0.0287) | (0, 0, 0) |
| `Camera1_Link` (base camera) | `base_link` | (0.003, −0.191, −0.120) | (−0.663, 0, 3.1416) |
| `Radar_Link` (lidar) | `base_link` | (0, −0.126, −0.085) | (0, 0, 0) |
