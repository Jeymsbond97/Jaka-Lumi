# 00. Start here

The path from zero to working on the real Lumi: what the robot is, what to install, how to power it on and connect, the first slow motions, and where each part is documented. Passwords are not in these docs; ask the project owner.

---

## 0. The robot and its control channels

Lumi is a JAKA mobile manipulator: mobile base, lift, waist, 2-joint head, 6-joint arm with a gripper, two RGB-D cameras and a microphone array ([01_HARDWARE.md](01_HARDWARE.md)).

| Channel | Controls | Address |
|---|---|---|
| Body HTTP API | lift, waist, head yaw, head pitch | `http://192.168.10.90:5000/api/extaxis/...` |
| Arm controller | 6-joint arm, tool I/O (gripper) | `192.168.10.90` (JAKA SDK `jkrc`, or JSON commands on TCP port 10001) |
| AGV TCP API | base driving, navigation, people detection | `192.168.10.10:31001` |
| USB 3.0 (to the onboard computer) | head and torso cameras, microphone array | — |

---

## 1. Read first

1. [11_SAFETY.md](11_SAFETY.md): stop devices and operating rules.
2. [01_HARDWARE.md](01_HARDWARE.md): what is on the robot.
3. [02_NETWORK_AND_ACCESS.md](02_NETWORK_AND_ACCESS.md): addresses and how to connect.

---

## 2. Prepare your computer

| Need | macOS (Apple Silicon) | Ubuntu 22.04 / Jetson |
|---|---|---|
| Python 3.10+ with `requests`, `numpy`, `opencv-python`, `pyserial`, `pyaudio` | `pip install requests numpy opencv-python pyserial pyaudio` (pyaudio needs `brew install portaudio`) | `pip install ...`, `sudo apt install portaudio19-dev` |
| JAKA SDK `jkrc` (arm) | no macOS build: use Docker Desktop with an `arm64v8/python:3.10` container and the `aarch64-linux-gnu` files ([04_ARM.md](04_ARM.md)) | native: `x86_64-linux-gnu` or `aarch64-linux-gnu` files + `LD_LIBRARY_PATH` |
| Orbbec camera tools | OrbbecViewer macOS arm64 build | OrbbecSDK `.deb` (amd64 / arm64) + pyorbbecsdk ([06_CAMERAS_AND_VISION.md](06_CAMERAS_AND_VISION.md)) |
| Browser | Chrome | Chrome |
| JAKA App 1.7.2 (optional) | iPad / Android tablet / Windows PC | Windows PC / tablet |

Download the SDK:

```bash
curl -L -o jaka_sdk.zip "https://www.jaka.com/prod-api/common/download/resource?resource=%2Fprofile%2Fupload%2F2025%2F04%2F25%2F20250425134342A024.zip"
unzip jaka_sdk.zip && tar -xf "SDK V2.2.7.7z"      # macOS tar (bsdtar) reads .7z; on Linux use 7z x
ls "SDK V2.2.7/Linux/python3/"                     # aarch64-linux-gnu, x86_64-linux-gnu, i686-linux-gnu
```

Keep the SDK binaries out of git (they are large).

---

## 3. Power on and off

1. Robot on a flat floor, free space around, E-stop on the column released, manual charging cable unplugged.
2. **Base:** main switch underneath (next to the rear right caster) to **I**. Hold the power button: two short beeps → release after the third, long beep. LED flashes green, then **white** = ready.
3. Wait about **5 minutes** for the controller and the onboard computer to start.
4. **Arm:** in Cobo π (`https://192.168.10.90`) or the JAKA App: **Power** → ring light blue → **Enable** → green.
5. **Body:** open `http://192.168.10.90:5000` → Reset → Enable (or through the API, [03_BODY_LIFT_WAIST_HEAD.md](03_BODY_LIFT_WAIST_HEAD.md)).

Power off in reverse: body Disable → arm Disable → arm Power off → hold the base button (seven short beeps, release on the eighth) → main switch to O if the robot is stored for more than 30 days.

---

## 4. Connect

1. Join the robot Wi-Fi `Lumi<serial>` **or** plug a cable into the base's RJ45 port.
2. Your IP must be `192.168.10.x`. If it is `10.5.5.x`, set a static address such as `192.168.10.150/24`, gateway `192.168.10.9` ([02 §2](02_NETWORK_AND_ACCESS.md#fix-a-1055x-address)).
3. Check:

```bash
ping -c 2 192.168.10.90
ping -c 2 192.168.10.10
curl -s http://192.168.10.90:5000/api/extaxis/status
```

4. Web pages: `https://192.168.10.90` (Cobo π, log in as Administrator), `http://192.168.10.90:5000` (body), `http://192.168.10.10:9001` (AGV).

---

## 4a. The onboard computer

The cameras and the microphone array are USB devices: they work only on the computer plugged into the base's USB 3.0 port. On Lumi this is the onboard **Jetson AGX Thor** ([08_NVIDIA_THOR.md](08_NVIDIA_THOR.md)), which runs the robot software. Body, arm and base are network devices and can be reached from any computer on the robot network.

```
Laptop ──Wi-Fi "Lumi<serial>"──> robot network 192.168.10.x
   │                                  ├─ 192.168.10.90  arm + body controller (MiniCab)
   │                                  ├─ 192.168.10.10  AGV base computer
   └──SSH──> onboard computer (Thor) ─┘
                 └─USB 3.0─> head camera, torso camera, microphone array
```

Neither `192.168.10.90` (arm controller) nor `192.168.10.10` (AGV navigation PC) runs user code; the onboard computer does.

1. Find the onboard computer's IP: router page `http://192.168.10.79` → connected devices, or `nmap -sn 192.168.10.0/24`.
2. `ssh <user>@<ip>`.
3. Check the USB devices: `lsusb | grep -i -E "2bc5|orbbec"` (two Gemini 2 L) and `arecord -l` (AIUI-USB-MC).
4. Edit code remotely (VS Code Remote-SSH), or keep it in git and pull / rsync it there.
5. Camera images on a laptop: OrbbecViewer over X11 forwarding (`ssh -X`), or frames published over the network (ROS 2 `OrbbecSDK_ROS2`, or an HTTP / MJPEG server).

The software that runs on the onboard computer is described in [../README.md](../README.md).

---

## 5. Read-only checks

| Part | Check | Doc |
|---|---|---|
| Arm | Cobo π: controller version, arm model (`MiniCobo2`), joint limits, joint speed limits, mounting, payload | [04_ARM.md](04_ARM.md) |
| Arm SDK | `login()` (or `login(1)`), `get_sdk_version()`, `get_robot_status_simple()`, `get_joint_position()` | [04_ARM.md](04_ARM.md) |
| Body | `GET /sysinfo`, `GET /status` | [03 §2](03_BODY_LIFT_WAIST_HEAD.md#2-http-api) |
| Base | web monitor: map, position, battery, E-stops; API `robot_status`, `get_power_status`, `software/get_version`, `markers/query_brief` | [05_AGV_BASE.md](05_AGV_BASE.md) |
| Cameras | `lsusb` / OrbbecViewer: two Gemini 2 L, serial numbers, head / torso | [06_CAMERAS_AND_VISION.md](06_CAMERAS_AND_VISION.md) |
| Microphone | `AIUI-USB-MC` in the audio device list; record 5 s | [07_VOICE_AND_AUDIO.md](07_VOICE_AND_AUDIO.md) |

---

## 6. First motions (slow)

1. **Body** ([03 §5](03_BODY_LIFT_WAIST_HEAD.md#5-bring-up-sequence)): enable, `moveto` with `vel=10`: head pitch 0→20→0, head yaw ±30, waist ±20, lift 0→50→0.
2. **Arm** ([04_ARM.md](04_ARM.md)): collision level 1; each joint +5° and back at 0.2 rad/s; then the factory pose `[0, 120, -120, 0, -90, 0]°`.
3. **Base** ([05_AGV_BASE.md](05_AGV_BASE.md)): open area, `joy_control` 0.1 m/s for 2 s at 10 Hz, 0.3 rad/s turn; soft E-stop.

---

## 7. Development areas

| Area | Approach | Docs |
|---|---|---|
| Arm trajectories | `joint_move` sequences → `servo_j` streaming (8 ms) where the controller supports servo mode → MoveIt 2 through the vendor ROS servers | [04_ARM.md](04_ARM.md), [09_ROS2_TELEOP_AND_SIM.md](09_ROS2_TELEOP_AND_SIM.md) |
| Base | `joy_control` at 10 Hz (v, w) → markers + `/api/move` navigation | [05_AGV_BASE.md](05_AGV_BASE.md) |
| Cameras / vision | pyorbbecsdk colour + depth, intrinsics, hand-eye calibration | [06_CAMERAS_AND_VISION.md](06_CAMERAS_AND_VISION.md) |
| Sound direction | mic array direction output → head / waist turn; AGV `human_detection` as a second source | [07_VOICE_AND_AUDIO.md](07_VOICE_AND_AUDIO.md) |
| Onboard computer | Jetson AGX Thor setup, Docker, voice services | [08_NVIDIA_THOR.md](08_NVIDIA_THOR.md) |
| Gripper | tool I/O signals, gripper control | [10_GRIPPER.md](10_GRIPPER.md) |
| Tunable values | speeds, distances, thresholds with file and line | [TUNING.md](TUNING.md) |

---

## 8. Coordinate frames and units

| Interface | Units | Frame |
|---|---|---|
| Body HTTP API | mm, degrees | joint space |
| Arm SDK joints | rad | SDK joint space = URDF `l_a1…l_a6` |
| Arm SDK Cartesian | mm, rad (RX, RY, RZ) | arm base / user frame; TCP = active tool (default flange centre). Cobo π shows degrees and a "World" frame that includes the mounting angle |
| AGV `joy_control` | m/s, rad/s | base: + forward, + left turn |
| AGV poses, markers | m, rad | map frame made during mapping |
| AGV `human_detection` | m | robot: x ahead, right-handed (y left) |
| Camera depth | mm (after `depth_scale`) | camera optical frame |
| URDF | m, rad | robot front = −y of `base_link`; arm base on the waist link at (−0.104, 0, 0.069) |

---

## 9. Documentation map

| Doc | Content |
|---|---|
| [README.md](README.md) | index |
| [01_HARDWARE.md](01_HARDWARE.md) | specs of every part, connectors, lights, model files |
| [02_NETWORK_AND_ACCESS.md](02_NETWORK_AND_ACCESS.md) | network map, addresses, static IP, apps and tools |
| [03_BODY_LIFT_WAIST_HEAD.md](03_BODY_LIFT_WAIST_HEAD.md) | body web page, HTTP API, Cobo π external axes, ROS node |
| [04_ARM.md](04_ARM.md) | Cobo π, controller versions, Python SDK, joint space, trajectories, settings, tool I/O |
| [05_AGV_BASE.md](05_AGV_BASE.md) | web monitor (mapping, markers, correction) and TCP API |
| [06_CAMERAS_AND_VISION.md](06_CAMERAS_AND_VISION.md) | Orbbec tools, Python, intrinsics, hand-eye calibration |
| [07_VOICE_AND_AUDIO.md](07_VOICE_AND_AUDIO.md) | mic array, recording, sound direction |
| [08_NVIDIA_THOR.md](08_NVIDIA_THOR.md) | Jetson Thor setup, Docker, voice services |
| [09_ROS2_TELEOP_AND_SIM.md](09_ROS2_TELEOP_AND_SIM.md) | ROS 2 / MoveIt / Isaac Sim, VR teleop, ACT |
| [10_GRIPPER.md](10_GRIPPER.md) | gripper hardware, signals, control |
| [11_SAFETY.md](11_SAFETY.md) | stop devices and rules |
| [12_SOURCES.md](12_SOURCES.md) | sources and download links |
| [TUNING.md](TUNING.md) | tunable values |
