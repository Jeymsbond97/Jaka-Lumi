# Lumi

Software for our **JAKA Lumi** robot. It runs on the NVIDIA Jetson AGX Thor mounted on the robot and makes Lumi an office assistant: it talks with people in English and Korean, drives where it is told, and picks up and puts back a cup by voice.

**Contents:** [About the robot](#about-the-robot) · [Getting started](#getting-started) · [Hardware](#hardware) · [Folder layout](#folder-layout) · [Run](#run) · [Deploying a change](#deploying-a-change) · [Not in git](#not-in-git-local-on-the-thor) · [Pitfalls](#pitfalls) · [Documentation](#documentation)

---

## About the robot

The JAKA Lumi is a **mobile manipulator**: a robot arm on a body that drives, sold by JAKA as an "embodied AI platform". From the floor up:

- a **mobile base** (AGV) with two drive wheels, a lidar and its own navigation computer: it keeps a map of the office, drives to named places (markers) on it and charges itself on a dock;
- a **lifting column** that raises the upper body, and a **waist** that turns it left and right;
- a **head** that turns and nods, with a camera, a microphone array and a speaker in it;
- a **6-joint arm** (JAKA Mini 2) on the side of the column, with a **Zimmer electric gripper** and long steel fingers made for cups;
- a second camera on the **torso**, looking at the table in front of the arm;
- the **Jetson AGX Thor** computer, which runs everything in this repository: speech recognition, the language model, the voice, camera detection and the control of every part.

Each part has its own controller on the robot's network; this software talks to all of them directly (no ROS, no vendor SDK). Numbers and models: [Hardware](#hardware).

### What Lumi can do

- **Talk in English and Korean.** Wake it by name ("Lumi", "Hi Lumi", "루미야") from anywhere; it finds who called by voice direction and camera and answers in English or Korean. Follow-up questions keep the topic, and it can be interrupted while it speaks.
- **Answer questions**, from its own knowledge and from the internet: date and time, weather, Wikipedia, news.
- **Greet people.** In Greeter mode it greets a person who stops in front of it and asks how it can help.
- **Go to places.** "Come here" brings it to about 1 m in front of the caller; "go to p2", "go home", "go to table front" to any marker on the active map, its names said in English, Korean or mixed. In Patrol mode it drives its round and stops only for a person in its path. It goes to the charger on low battery.
- **Pick up a cup and put it back.** It finds the cup with the torso camera, plans the grasp, picks it, can drive holding it, and puts it back where it was.
- **Stop on "stop" / "멈춰"**: the base, the arm and its own speech.

---

## Getting started

### 1. Connect to the robot

All of Lumi's parts share one network, the **robot LAN** (`192.168.10.x`). It has no internet; the Thor reaches the internet over its own Wi-Fi to the office network.

- **Wi-Fi**: join the robot's own Wi-Fi `Lumi<serial>` (2.4 GHz) or `Lumi<serial>-5G`; the serial is on the robot's name plate. Password: **ask the robot's owner**.
- **Cable**: plug into the gigabit RJ45 port on the back of the base.
- Your computer must get a `192.168.10.x` address. If it gets `10.5.5.x`, set one by hand as described in [docs/02 §2](../../docs/02_NETWORK_AND_ACCESS.md).
- Check: `ping 192.168.10.240` (the Thor), then open the dashboard below.
- **SSH to the Thor**: `ssh <user>@192.168.10.240`. User name and password: **ask the robot's owner**.

### 2. Pages and services

| What | Address | For |
|---|---|---|
| **Dashboard** | http://192.168.10.240:8100/view | Everyday use: cameras, map (markers added on the base show within 20 s), arm poses and Wave, Greeter / Patrol, STOP |
| **Robot API** (Swagger) | http://192.168.10.240:8100/docs | Every endpoint of this software with "Try it out": status, base, body, arm, gripper, skills, tasks, cameras, assistant |
| API health | http://192.168.10.240:8100/health | `{"ok": true}` while the API runs |
| Camera picture | http://192.168.10.240:8100/camera/torso.jpg (or `head.jpg`) | Latest frame of one camera; `/camera/<name>.mjpg` is a live stream |
| **Cobo π** (arm controller) | https://192.168.10.90 | Arm power, enable, jog, safety settings, tool I/O, programs. Accept the self-signed certificate. Login: **ask the robot's owner** |
| Body page and API | http://192.168.10.90:5000 | Lift, waist, head: enable / disable / reset / stop, joint table; the API is under `/api/extaxis/` ([docs/03](../../docs/03_BODY_LIFT_WAIST_HEAD.md)) |
| Arm JSON port | `192.168.10.90:10001` (TCP) | The arm controller's command port, used by `robot/arm.py` and `robot/gripper.py` |
| **Base panel** (AGV) | http://192.168.10.10:9001 | Map, markers, no-go lines, manual driving, soft E-stop, battery. Use Chrome. The map builder opens on port 8809 |
| Base API | `192.168.10.10:31001` (TCP) | The base's command port, used by `robot/agv.py` ([docs/05](../../docs/05_AGV_BASE.md)) |

Used only by the API, on the Thor itself: whisper speech-to-text `:8096`, the embedding server `:8095`, Ollama `:11434`. Other services on the Thor (`:8000`, `:8001`, `:8090`, `:3080`) belong to colleagues.

### 3. Switch Lumi on

Open the dashboard, http://192.168.10.240:8100/view. Both switches are off after every reboot.

- **Greeter**: Lumi stays in place and talks with people. Stand in front of it or call it by name ("Lumi", "Hi Lumi", "루미야"), then ask in English or Korean. A wireless clip mic on the person hears far better than the head microphones at a distance.
- **Patrol**: Lumi also drives and uses the arm: everything that moves.
- **■ STOP** in the top bar stops the base, the arm, the body and the assistant at once.

### 4. Safety

- **Ask before moving anything** (base, lift, waist, head, arm, gripper). People work next to the robot.
- Someone stands at a **stop** while anything new runs: the red **E-stop on the column** (cuts arm power, stops the lift), the dashboard **■ STOP**, or "stop" / "멈춰". The first run of any new arm motion is slow and watched.
- **No hands near the gripper fingers** when it may close: it closes with 90 N or more and cannot be stopped half way.
- The arm sticks out past the base (about 0.44 m from its centre in `look`) and the base's navigation does not know it: keep the arm's sweep and the base's path clear. The lidar does not see glass or low, black or shiny things.
- **Never restart the API or the assistant while the base drives**: check `curl -s localhost:8100/status` → `base.move_status` first. Stopping the assistant cancels the drive.
- Do not change controller, base or network settings without the owner (the arm's mounting in Cobo π must stay as it is: the arm is side-mounted). The arm's collision limits are still the loose defaults: no arm work close to people.
- Do not push the base while it is on; do not drive with the manual charging cable plugged in.

Full rules: [docs/11_SAFETY.md](../../docs/11_SAFETY.md).

### 5. For developers

The code runs on the Thor (it needs the robot's hardware); the self-checks also run on any Linux machine with the venv. Repository URL and access: ask the robot's owner.

```bash
git clone <repo-url> ~/Dev/lumi-wave
cd ~/Dev/lumi-wave

# Python 3.12 venv, with this folder on its path (modules import each other by folder)
uv venv --python 3.12 .venv
uv pip install --python .venv numpy opencv-python-headless pyorbbecsdk2 fastapi uvicorn supertonic soundfile
uv pip install --python .venv tensorrt-cu13 cuda-python      # GPU detection, on the Thor
echo "$PWD" > .venv/lib/python3.12/site-packages/lumi_wave.pth

for t in tests/test_*.py; do .venv/bin/python $t || echo "FAILED: $t"; done   # self-checks, nothing moves

systemctl --user restart lumi-api                     # after a change; check the base is not driving first
tail -f logs/api.log logs/lumi.log                    # robot log, assistant log
```

Models, whisper.cpp and calibration files are local to the Thor: [Not in git](#not-in-git-local-on-the-thor). What to restart after a change: [Deploying a change](#deploying-a-change).

---

## Hardware

Lumi is 510 × 510 mm on the floor, 1460–1860 mm tall (with the lift), 95.6 kg, with 12 degrees of freedom: 2 drive wheels, lift, waist, head yaw and pitch, 6 arm joints. Full specifications and sources: [docs/01_HARDWARE.md](../../docs/01_HARDWARE.md).

| Part | What it is | Key facts | How we reach it | Doc |
|---|---|---|---|---|
| **Base (AGV)** | Differential-drive base with its own navigation computer, lidar SLAM | 2 × 160 W hub motors; 0.6 m/s default, 1.2 m/s max (joystick command ±0.5 m/s, ±1.0 rad/s); turning radius 307 mm; needs a 700 mm passage. 24 V 45 Ah Li-ion, about 10 h; contact charging on a dock | TCP API of the base, over the robot LAN | [05](../../docs/05_AGV_BASE.md) |
| Base sensors | Used by the base's own navigation | 2D lidar 0.02–10 m, 240°, 30 Hz; front 3D camera 0.35–2 m; 5 ultrasonic sensors 0.03–0.55 m; 6-axis IMU; infrared; bumper. The lidar does not see glass | Base API (map, distance probe) | [05](../../docs/05_AGV_BASE.md) |
| **Body** | Lifting column, waist turn, head yaw, head pitch | Lift 0–400 mm in hardware, 0–300 mm in the API; **our code holds it at 0–105 mm** (the head camera's cable is too short). Waist ±160° hardware, ±140° API. Head yaw ±180° (about 6 s per 90°), pitch −5…+35° | HTTP API on the arm controller | [03](../../docs/03_BODY_LIFT_WAIST_HEAD.md) |
| **Arm** | JAKA Mini 2, 6 joints, mounted on the side of the column | Payload 2 kg, reach 580 mm, repeatability ±0.1 mm, 9.9 kg, max tool speed 1 m/s, 48 V. Controller (MiniCab) inside the base, web UI Cobo π. In the `look` pose the hand is ~0.44 m from the base centre, past the base edge | JSON port of the arm controller | [04](../../docs/04_ARM.md) |
| **Gripper** | Zimmer GEP2013IO-05-B electric parallel gripper with long steel cup fingers | 13 mm stroke per jaw, 90–360 N in four levels (set to level 1), ~0.54 kg, ~1 s per stroke. Inner gap open → closed: tips 88 → 59 mm, round hook 96 → 70 mm. Software grips 61–92 mm wide objects | Arm tool I/O (all PNP): DO_1 close, DO_2 open (never both), AI_1 finger position, DI_1 optical sensor looking below the gripper | [10](../../docs/10_GRIPPER.md), [gripper/](../../docs/gripper/README.md) |
| **Head camera** | Orbbec Gemini 2 L RGB-D, front of the head | Colour used at 1280 × 720, depth 0.02–10 m (brochure 0.2–10 m), colour FoV 94° × 68°. Turns with the head; watches people while Lumi stands. Calibrated to the arm at any head pose: median 6.0 mm | USB 3, through a USB 3 hub in the head shared with the microphones and speaker | [06](../../docs/06_CAMERAS_AND_VISION.md) |
| **Torso camera** | Orbbec Gemini 2 L RGB-D, under the handle on the column | Same link as the arm base, so its calibration holds at any lift and waist angle: median 3.3 mm. Sees objects for picking, the table, the path while driving | USB 3 | [06](../../docs/06_CAMERAS_AND_VISION.md) |
| **Microphones** | iFlytek AIUI XF-USB-MC ring array in the head; optional DJI Mic Mini wireless clip mic | Array: 8 channels at 16 kHz (6 mics), SNR > 70 dB, 3–5 m. Voice direction is computed by our code (SRP-PHAT). The clip mic is used automatically when its receiver is plugged in and hears 5–10× better at 4–5 m | USB audio | [07](../../docs/07_VOICE_AND_AUDIO.md) |
| **Speaker** | USB speaker in the head ("USB Audio Device") | Volume 55 % in the office; set from the dashboard or by voice | USB audio | [07](../../docs/07_VOICE_AND_AUDIO.md) |
| **Computer** | NVIDIA Jetson AGX Thor Developer Kit | Blackwell GPU, 2070 TOPS (INT8) by spec; measured 14 CPU cores and 122 GB memory shared by CPU and GPU; JetPack R38.4, CUDA 13.0. Runs the LLM, speech, detection and all control | Ethernet to the robot LAN; its own Wi-Fi for the internet (the robot LAN has none) | [08](../../docs/08_NVIDIA_THOR.md) |

Safety: E-stop buttons on the column and in the base; the arm's collision limits in Cobo π are still the factory defaults. Read [docs/11_SAFETY.md](../../docs/11_SAFETY.md) before moving anything.

---

## Folder layout

```
lumi-wave/                      run with the venv: .venv/bin/python <folder>/<module>.py
├── api/                        robot API (FastAPI :8100, Swagger /docs) and the dashboard (/view)
├── assistant/                  the voice assistant: main loop (lumi.py), answers (brain.py), knowledge, web lookups
├── audio/                      microphones, speech to text, text to speech, voice direction
├── vision/                     camera service (the only camera owner), detection, objects in mm, calibration
├── robot/                      one driver per piece of hardware: base, body, arm, gripper; checked arm motion
├── manipulation/               pick and place skills, the arm's pose graph, the wave
├── tasks/                      whole jobs made of skills, driving and talking
├── tests/                      self-checks without the robot
├── data/                       taught and calibrated values
├── knowledge/                  texts Lumi answers from
├── logs/                       every log file and debug picture
├── docs/, tools/               documentation; scripts run from a laptop
└── lumi-api.service            starts the API at boot (systemd user service)
```

Modules import each other by folder (`from robot import arm`, `from vision import camview`). The venv has `lumi_wave.pth` in its `site-packages` with the path of this folder, so any module runs directly from any directory: `.venv/bin/python robot/gripper.py`.

---

## Run

Always with the venv (the system Python has no OpenCV):

```bash
cd ~/Dev/lumi-wave
.venv/bin/python api/server.py                  # normally started at boot
.venv/bin/python assistant/lumi.py              # assistant in the terminal (switch the dashboard's Greeter/Patrol off first)
.venv/bin/python assistant/lumi.py --no-camera --no-drive
.venv/bin/python assistant/brain.py --act       # type questions, see answers and actions
.venv/bin/python audio/ears.py                  # speak, see the text
.venv/bin/python audio/mouth.py "Hello"         # Lumi says it
.venv/bin/python robot/gripper.py               # gripper state
.venv/bin/python robot/motion.py                # joints, TCP, named poses
.venv/bin/python vision/objects.py --watch      # what the torso camera sees, in mm
.venv/bin/python manipulation/skills.py plan cup   # dry run of a pick and place (nothing moves)
.venv/bin/python manipulation/arm_route.py check   # the arm's route to look along the pose graph (nothing moves)
.venv/bin/python assistant/web.py weather Seoul
.venv/bin/python assistant/knowledge.py build   # after changing knowledge/
.venv/bin/python vision/camview.py --stop       # free the cameras for camera_test / camera_fps
```

At boot the user service `lumi-api` ([lumi-api.service](lumi-api.service), installed in `~/.config/systemd/user/`, linger on, so no login is needed) starts `api/server.py` 20 s after boot and restarts it 5 s after it dies. Restarting the API does not stop the camera service, whisper or a running assistant. The assistant runs only while Greeter or Patrol is switched on in the dashboard; both are off after a reboot on purpose.

```bash
systemctl --user status lumi-api       # running? since when?
systemctl --user restart lumi-api      # after changing api/, robot/, manipulation/ or tasks/
systemctl --user stop lumi-api         # stays stopped until start or the next boot
```

Logs are in `logs/`: `lumi.log` (assistant), `lumi_console.log` (its stderr), `api.log`, `camview.log`, `whisper_server.log`, `embed_server.log`. The dashboard's Settings → Logs shows the robot log or the assistant log, latest errors on top.

---

## Deploying a change

1. Check that the robot is not driving: `curl -s localhost:8100/status` → `base.move_status` must not be `running`. **Restarting the assistant cancels a drive in progress.**
2. Edit, then `.venv/bin/python -m py_compile <file>`.
3. Restart what uses the file:
   - `assistant/`, `audio/` → switch Greeter/Patrol off and on in the dashboard (the API restarts the assistant);
   - `api/` → `systemctl --user restart lumi-api`;
   - `vision/camview.py`, `person.py`, `objects.py` → `vision/camview.py --stop`, then `--serve`;
   - `robot/`, `manipulation/`, `tasks/` are used by all of them: restart the API, and the assistant if it runs.
4. Watch `logs/lumi.log` / Settings → Logs.

---

## Not in git (local on the Thor)

| Path | What | How it is made |
|---|---|---|
| `logs/` | all log files and debug pictures | written at run time |
| `data/camera_extrinsics*.json`, `data/calib_samples*/`, `data/doa_*`, `data/volume.txt`, `data/speech_speed.txt` | calibrations and settings of this robot | `vision/calib.py`, `audio/doa.py`, the dashboard |
| `.venv/` | Python 3.12 venv with `site-packages/lumi_wave.pth` (the path of this folder): numpy, opencv-python-headless, pyorbbecsdk2, fastapi, uvicorn, supertonic, soundfile, tensorrt-cu13, cuda-python | |
| `models/yolov8s.onnx`, `models/yolov8s.engine` | GPU detector. The engine only runs on the TensorRT version and GPU it was built with: rebuild after a JetPack or TensorRT change | `YOLO("yolov8s.pt").export(format="onnx", imgsz=640, opset=17)`; `vision/yolo_engine.py models/yolov8s.onnx models/yolov8s.engine` (~100 s) |
| `models/yolov8n.onnx` | CPU fallback detector | `YOLO("yolov8n.pt").export(format="onnx", imgsz=640, opset=12, simplify=True)` |
| `models/yolo11s-pose.onnx`, `.engine` | pose keypoints for `vision/pose.py` | ultralytics export, then `vision/yolo_engine.py` |
| `models/face_detection_yunet_2023mar.onnx`, `models/face_recognition_sface_2021dec.onnx` | face detector and embedding for `vision/reid.py` (without them only clothes are used) | github.com/opencv/opencv_zoo |
| `models/ggml-large-v3-turbo-q5_0.bin` | whisper model | Hugging Face `ggerganov/whisper.cpp` |
| `models/supertonic3/` | TTS model | Hugging Face `Supertone/supertonic-3` |
| `whisper.cpp/` | v1.9.5, built with CUDA | `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=110 -DCMAKE_BUILD_TYPE=Release && cmake --build build -j 12 --target whisper-server whisper-cli` |
| `~/models/bge-m3-Q8_0.gguf` | embedding model for the knowledge base | Hugging Face |
| `knowledge/index.npz` | knowledge vectors | `assistant/knowledge.py build` |
| Ollama `gemma4:26b` | LLM | `ollama pull gemma4:26b` |
| `docs/private/` | company-internal notes (access, vendor manuals, screenshots) | kept off git |

The Orbbec cameras need the udev rule `SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"` in `/etc/udev/rules.d/99-orbbec.rules`.

---

## Pitfalls

- **Never open the cameras from a second program** while the camera service runs. After `vision/camview.py --stop` / `--start` the torso camera may not be found for a few seconds while it re-enumerates: wait and start again.
- **Check the USB speed after any cable work** (`/sys/bus/usb/devices/*/speed` must say 5000 for the cameras). A head camera opened at USB 2 stays colour-only until the camera service is restarted.
- **Never call `tasks/fetch.py` functions from a second process while the API runs**: its log writes that process's empty state over `/dev/shm/lumi_task.json`, and the held object is forgotten.
- After a controller power cycle the body axes are disabled and every move times out; `robot/head.py` enables them. All tool I/O must be PNP in Cobo π, or the gripper does not move.
- The base drives into a table's margin and reports "succeeded" without moving; the last part of a reach is a straight checked drive. Drives with the arm in `carry` stall (the base's 3D camera sees the hand): drive in `look`.
- The base's planning API does not check real paths, so `robot/nav.py` uses the map image. Closed glass doors need a no-go line in the base's web panel.
- The body API's `/stop` does not stop a `moveto`, so hold-to-move uses small steps.
- `pkill -f` / `pgrep -f` also match your own shell's command line: find the PID with `ps -eo pid,args | grep "[n]ame"` and kill that.
- Headless Chrome screenshots of the dashboard: do not use `--timeout` (it freezes the page's JavaScript).
- Other projects and services on this Thor belong to colleagues (`~/Dev/lumi_edu`, `lumi-vision`, `lumi_voice_app`, services on :8000, :8001, :8090, :3080). Do not touch them.

Every value meant to be tuned by hand, with its file: [docs/TUNING.md](../../docs/TUNING.md).

---

## Documentation

| Document | Content |
|---|---|
| [00 Start here](../../docs/00_START_HERE.md) | From zero to developing on the robot: install, power on, connect, first tests |
| [01 Hardware](../../docs/01_HARDWARE.md) | Every specification, connectors, lights, model files |
| [02 Network and access](../../docs/02_NETWORK_AND_ACCESS.md) | Connecting a computer; web pages, apps |
| [03 Body: lift, waist, head](../../docs/03_BODY_LIFT_WAIST_HEAD.md) | The four body joints, their API and ranges |
| [04 Arm](../../docs/04_ARM.md) | Cobo π, SDK, units, settings, tool connector |
| [05 Mobile base](../../docs/05_AGV_BASE.md) | Mapping, markers, driving, navigation API |
| [06 Cameras and vision](../../docs/06_CAMERAS_AND_VISION.md) | Orbbec cameras, intrinsics, calibration, scene understanding |
| [07 Voice and audio](../../docs/07_VOICE_AND_AUDIO.md) | Microphone array, speaker, voice direction |
| [08 Jetson Thor](../../docs/08_NVIDIA_THOR.md) | The AI computer, setup, what runs on its GPU |
| [09 ROS 2, teleop, simulators](../../docs/09_ROS2_TELEOP_AND_SIM.md) | Vendor ROS 2, MoveIt 2, Isaac Sim, VR teleoperation |
| [10 Gripper](../../docs/10_GRIPPER.md) | The Zimmer gripper: signals, PNP, measurements |
| [Gripper fingers](../../docs/gripper/README.md) | Finger shape and measured gaps, photos |
| [11 Safety](../../docs/11_SAFETY.md) | Stop buttons and rules; read before any motion |
| [12 Sources](../../docs/12_SOURCES.md) | Where each fact came from; downloads |
| [Tuning](../../docs/TUNING.md) | Speeds, distances, thresholds with their file |
| [docs/README.md](../../docs/README.md) | Index of the reference docs |

Company-internal notes (access, vendor manuals, screenshots) are kept off git.
