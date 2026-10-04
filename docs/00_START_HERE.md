# 00. Start here: from zero to developing on the real Lumi

A step-by-step path for anyone who picks up this project: what the project is, what to install, how to power on and connect to the robot, how to test each part, and where to start writing code. Each step links to the detailed document.

Passwords and company-internal addresses are in [private/ACCESS.md](private/ACCESS.md). That folder is local only (not on GitHub); ask the project owner for a copy if it is missing.

---

## 0. What this project is

- **Goal:** control the real JAKA Lumi (mobile base + lift + waist + head + 6-joint arm + two RGB-D cameras + mic array) from our own code; first trajectories and sensors, then "turn toward the person who speaks", then grasping once a gripper is mounted, then LLM + vision control.
- **The robot has three control channels** (plus USB for sensors):

| Channel | What | Address |
|---|---|---|
| Body HTTP API | lift, waist, head yaw, head pitch | `http://192.168.10.90:5000/api/extaxis/...` |
| JAKA SDK `jkrc` | 6-joint arm | `192.168.10.90` |
| AGV TCP API | base driving, navigation, people detection | `192.168.10.10:31001` |
| USB 3.0 (to our computer) | head + torso cameras, microphone array | — |

---

## 1. Read first (30 minutes)

1. [11_SAFETY.md](11_SAFETY.md): stop buttons and test rules.
2. [01_HARDWARE.md](01_HARDWARE.md): what is on the robot.
3. [02_NETWORK_AND_ACCESS.md](02_NETWORK_AND_ACCESS.md): addresses and how to connect.

---

## 2. Prepare your computer

| Need | macOS (Apple Silicon) | Ubuntu 22.04 / Jetson |
|---|---|---|
| Python 3.10+ with `requests`, `numpy`, `opencv-python`, `pyserial`, `pyaudio` | `pip install requests numpy opencv-python pyserial pyaudio` (pyaudio needs `brew install portaudio`) | `pip install ...`, `sudo apt install portaudio19-dev` |
| JAKA SDK `jkrc` (arm) | **no macOS build**: use Docker Desktop with an `arm64v8/python:3.10` container and the `aarch64-linux-gnu` files ([04 §3](04_ARM.md#get-it)) | native: `x86_64-linux-gnu` or `aarch64-linux-gnu` files + `LD_LIBRARY_PATH` |
| Orbbec camera tools | OrbbecViewer macOS arm64 build; pyorbbecsdk on macOS: verify | OrbbecSDK `.deb` (amd64 / arm64) + pyorbbecsdk ([06](06_CAMERAS_AND_VISION.md)) |
| Browser | Chrome | Chrome |
| JAKA App 1.7.2 (optional) | iPad / Android tablet / Windows PC | Windows PC / tablet |

Download the SDK once:

```bash
curl -L -o jaka_sdk.zip "https://www.jaka.com/prod-api/common/download/resource?resource=%2Fprofile%2Fupload%2F2025%2F04%2F25%2F20250425134342A024.zip"
unzip jaka_sdk.zip && tar -xf "SDK V2.2.7.7z"      # macOS tar (bsdtar) reads .7z; on Linux use 7z x
ls "SDK V2.2.7/Linux/python3/"                     # aarch64-linux-gnu, x86_64-linux-gnu, i686-linux-gnu
```

Keep SDK binaries out of git (they are large); put them in a local `jaka_sdk/` folder and add it to `.gitignore` if needed.

---

## 3. Power on the robot

1. Check: robot on a flat floor, free space around, E-stop on the column released, manual charging cable unplugged.
2. **Base:** main switch underneath (next to the rear right caster) to **I**. Hold the power button: two short beeps → release after the third, long beep. LED flashes green, then **white** = ready.
3. Wait about **5 minutes** for the controller (and, if fitted, the Jetson services) to start.
4. **Arm:** in Cobo π (`https://192.168.10.90`) or the JAKA App: **Power** → ring light blue → **Enable** → green.
5. **Body:** open `http://192.168.10.90:5000` → Reset → Enable (or by API, step 6).

Power off in reverse: body Disable → arm Disable → arm Power off → hold the base button (seven short beeps, release on the eighth) → main switch to O if stored > 30 days.

---

## 4. Connect

1. Join the robot Wi-Fi `Lumi<serial>` (password: [private/ACCESS.md](private/ACCESS.md)) **or** plug a cable into the base's RJ45 port.
2. Your IP must be `192.168.10.x`. If it is `10.5.5.x`, set a static address like `192.168.10.150/24`, gateway `192.168.10.9` ([02 §2](02_NETWORK_AND_ACCESS.md#fix-a-1055x-address)).
3. For cameras and microphone: USB 3.0 cable from your computer to the base.
4. Check:

```bash
ping -c 2 192.168.10.90
ping -c 2 192.168.10.10
curl -s http://192.168.10.90:5000/api/extaxis/status
```

5. Open the three web pages: `https://192.168.10.90` (Cobo π, log in as Administrator), `http://192.168.10.90:5000` (body), `http://192.168.10.10:9001` (AGV).

---

## 4a. Working through the robot's onboard computer

The cameras and the microphone array are USB devices: they work only on the computer that is plugged into the base's USB 3.0 port. On Lumi this is the **onboard computer** (most likely the company's Jetson Thor, powered by the robot and cabled to that port), not your laptop. Body, arm and base are network devices and can be driven from any computer on the robot network, including your Mac.

```
Your Mac ──Wi-Fi "Lumi<serial>"──> robot network 192.168.10.x
   │                                  ├─ 192.168.10.90  arm + body controller (MiniCab)  ← from the Mac directly
   │                                  ├─ 192.168.10.10  AGV base computer                 ← from the Mac directly
   └──SSH──> onboard computer (Thor) ─┘
                 └─USB 3.0 (always plugged)─> head camera, torso camera, microphone array
```

Neither `192.168.10.90` (arm controller) nor `192.168.10.10` (AGV navigation PC) is meant for our code; the onboard computer is.

1. Find the onboard computer's IP ([13 §5](13_TO_VERIFY_ON_ROBOT.md#5-thor-on-the-robot-network)): router page `http://192.168.10.79` → connected devices, or `nmap -sn 192.168.10.0/24` from the Mac.
2. `ssh <user>@<ip>` (credentials in [private/ACCESS.md](private/ACCESS.md)).
3. Check the USB devices are there: `lsusb | grep -i -E "2bc5|orbbec"` (two Gemini 2 L) and `arecord -l` (AIUI-USB-MC).
4. Write code from the Mac with VS Code **Remote-SSH** (code lives and runs on the onboard computer), or keep it in this repo and `git pull` / `rsync` it there.
5. To see camera images on the Mac: run OrbbecViewer on the onboard computer with X11 forwarding (`ssh -X`), or publish frames over the network (ROS 2 topics with `OrbbecSDK_ROS2`, or a small HTTP/MJPEG server) and view them on the Mac.
6. Plug the Mac into the base USB port only if no onboard computer is connected there.

---

## 5. Look before moving (read-only checks)

Write the results into section 9 ("Robot facts").

| Part | Check | Doc |
|---|---|---|
| Arm | Cobo π: controller version (1.7 or 3.2 changes the SDK login and servo support), arm model, joint limits, joint speed limits, mounting, payload | [04 §2, §7](04_ARM.md#2-controller-versions-17-vs-32) |
| Arm SDK | `login()` (or `login(1)`), `get_sdk_version()`, `get_robot_status_simple()`, `get_joint_position()` | [04 §3](04_ARM.md#minimal-session) |
| Body | `GET /sysinfo`, `GET /status` | [03 §2](03_BODY_LIFT_WAIST_HEAD.md#2-http-api) |
| Base | web monitor: map, position, battery, E-stops; API `robot_status`, `get_power_status`, `software/get_version`, `markers/query_brief` | [05](05_AGV_BASE.md) |
| Cameras | `lsusb` / OrbbecViewer: two Gemini 2 L, serial numbers, which is head / torso | [06 §1](06_CAMERAS_AND_VISION.md#1-connect-and-check) |
| Microphone | `AIUI-USB-MC` in the audio device list; record 5 s | [07 §2](07_VOICE_AND_AUDIO.md#2-recording-audio) |

---

## 6. First motions (slow)

1. **Body** ([03 §5](03_BODY_LIFT_WAIST_HEAD.md#5-test-sequence-for-the-first-session)): enable, `moveto` with `vel=10`: head pitch 0→20→0, head yaw ±30, waist ±20, lift 0→50→0. Time each move, write down each joint's positive direction.
2. **Arm** ([04 §9](04_ARM.md#9-first-session-arm-tests)): collision level 1; each joint +5° and back at 0.2 rad/s, compare the direction with the joint axes of the official URDF and Cobo π's 3D view; then the factory pose `[0, 120, -120, 0, -90, 0]°`.
3. **Base** ([05 §5](05_AGV_BASE.md#5-first-session-base-tests)): open area, `joy_control` 0.1 m/s for 2 s at 10 Hz, 0.3 rad/s turn; soft E-stop test.

---

## 7. Development tracks

| Track | Start with | Docs |
|---|---|---|
| Arm trajectories | `joint_move` sequences → `servo_j` streaming (8 ms) with a filter (if the controller supports servo mode) → MoveIt 2 via the vendor ROS servers | [04 §5](04_ARM.md#5-trajectories), [09](09_ROS2_TELEOP_AND_SIM.md) |
| Base trajectories | `joy_control` at 10 Hz (v, w) → markers + `/api/move` navigation | [05 §3](05_AGV_BASE.md#3-tcp-api) |
| Cameras / vision | pyorbbecsdk colour + depth, intrinsics, torso hand-eye calibration, vendor Qwen-VL / NanoOWL demos | [06](06_CAMERAS_AND_VISION.md) |
| Look at the speaker | find the mic array's direction output, calibrate it, turn head/waist; refine with head camera; AGV `human_detection` as a second source | [07 §3](07_VOICE_AND_AUDIO.md#3-sound-direction-for-look-at-the-speaker) |
| Voice assistant (company) | Jetson Thor containers, web app | [08](08_NVIDIA_THOR.md), [private/COMPANY_VOICE_ASSISTANT.md](private/COMPANY_VOICE_ASSISTANT.md) |
| Grasping | after a gripper is mounted: wiring, Modbus commands, payload/TCP, gripper control code | [10](10_GRIPPER.md) |
| Robot control library | one Python class over the three channels (body HTTP, arm SDK, AGV TCP) + cameras | [03](03_BODY_LIFT_WAIST_HEAD.md), [04](04_ARM.md), [05](05_AGV_BASE.md), [06](06_CAMERAS_AND_VISION.md) |

---

## 8. Coordinate frames and units

| Interface | Units | Frame |
|---|---|---|
| Body HTTP API | mm, degrees | joint space |
| Arm SDK joints | rad | SDK joint space = URDF `l_a1…l_a6` (high confidence, [04 §4](04_ARM.md#4-joint-space-urdf--sdk-high-confidence)) |
| Arm SDK Cartesian | mm, rad (RX, RY, RZ) | arm base / user frame; TCP = active tool (default flange centre). Cobo π shows degrees and a "World" frame that includes the mounting angle |
| AGV `joy_control` | m/s, rad/s | base: + forward, + left turn |
| AGV poses, markers | m, rad | map frame made during mapping |
| AGV `human_detection` | m | robot: x ahead, right-handed (y left) |
| Camera depth | mm (after `depth_scale`) | camera optical frame |
| URDF | m, rad | robot front = −y of `base_link`; arm base on the waist link at (−0.104, 0, 0.069) |

---

## 9. Robot facts (fill in on the robot)

Procedures for finding each value: [13_TO_VERIFY_ON_ROBOT.md](13_TO_VERIFY_ON_ROBOT.md).

| Fact | Value | Date |
|---|---|---|
| Arm controller version | | |
| SDK login that works (`login()` / `login(1)`) | | |
| Servo mode supported? | | |
| Arm model shown by Cobo π | MiniCobo2 (Mini 2) | |
| Body firmware (`/sysinfo`) | | |
| Lift range accepted by the API | | |
| Head pitch sign (+ = down?) | | |
| Body speeds at vel=100 (lift mm/s, waist/head deg/s) | | |
| Arm joint speed limits | | |
| AGV software version, map, dock marker | see private/ACCESS.md (values from company screenshots) | |
| Leg tracking (`human_detection`) enabled? | | |
| Head camera serial / torso camera serial | | |
| Mic array: serial device? channels? direction output? | | |
| SDK joint directions match the URDF axes (+5° test)? | | |

---

## 10. Documentation map

| Doc | Content |
|---|---|
| [README.md](README.md) | index |
| [01_HARDWARE.md](01_HARDWARE.md) | specs of every part, connectors, lights, model files |
| [02_NETWORK_AND_ACCESS.md](02_NETWORK_AND_ACCESS.md) | network map, addresses, static IP, apps and tools |
| [03_BODY_LIFT_WAIST_HEAD.md](03_BODY_LIFT_WAIST_HEAD.md) | body web page, HTTP API, Cobo π external axes, ROS node |
| [04_ARM.md](04_ARM.md) | Cobo π, controller versions, Python SDK, joint space, trajectories, settings, tool I/O |
| [05_AGV_BASE.md](05_AGV_BASE.md) | web monitor (mapping, markers, correction) and TCP API |
| [06_CAMERAS_AND_VISION.md](06_CAMERAS_AND_VISION.md) | Orbbec tools, Python, intrinsics, hand-eye calibration, vision demos |
| [07_VOICE_AND_AUDIO.md](07_VOICE_AND_AUDIO.md) | mic array, recording, sound direction, voice assistant |
| [08_NVIDIA_THOR.md](08_NVIDIA_THOR.md) | Jetson Thor setup, Docker, voice services |
| [09_ROS2_TELEOP_AND_SIM.md](09_ROS2_TELEOP_AND_SIM.md) | ROS 2 / MoveIt / Isaac Sim, VR teleop, ACT |
| [10_GRIPPER.md](10_GRIPPER.md) | gripper options, wiring, Modbus commands, install checklist |
| [11_SAFETY.md](11_SAFETY.md) | stop devices and rules |
| [12_SOURCES.md](12_SOURCES.md) | every source and download link |
| [13_TO_VERIFY_ON_ROBOT.md](13_TO_VERIFY_ON_ROBOT.md) | unknown facts and how to find them |
| [private/ACCESS.md](private/ACCESS.md) | passwords, internal IPs, NAS (local only) |
