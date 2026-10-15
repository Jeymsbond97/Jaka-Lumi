# Lumi onboard software (Jetson Thor)

Everything that runs on the robot's NVIDIA Jetson Thor (`192.168.10.240`). It covers the robot API with Swagger and the web dashboard, the camera service with person detection, and the voice assistant (`assistant/lumi.py`), which greets visitors, talks with them in English and Korean and drives where it is told. It also holds the device drivers for the base, body, arm and gripper.

On the Thor this folder is `~/Dev/lumi-wave`, with the real-robot documentation copied next to the code (`docs/`, `tools/`, `CLAUDE.md`). `tools/thor_sync/sync.sh` on the Mac refreshes it.

---

## Folder layout

```
lumi-wave/                      run with the venv: .venv/bin/python <folder>/<module>.py
├── api/                        robot API and dashboard
│   ├── server.py               FastAPI :8100, Swagger /docs, dashboard /view, supervisor of the assistant
│   ├── control.py              hold-to-move for the dashboard
│   └── dashboard.html          the single-page dashboard
├── assistant/                  the voice assistant
│   ├── lumi.py                 main loop: tracking, greeting, conversation, commands, patrol, wake word
│   ├── brain.py                answers (knowledge + gemma4), actions, rule-based intents
│   ├── knowledge.py            knowledge base (RAG) over knowledge/
│   └── web.py                  date / time, weather, Wikipedia, news
├── audio/                      microphones and speaker
│   ├── mic.py                  always-on recording, utterances, barge-in
│   ├── ears.py                 speech to text (whisper.cpp)
│   ├── mouth.py                text to speech (Supertonic)
│   └── doa.py                  direction of the voice
├── vision/                     cameras
│   ├── camview.py              camera service (the only camera owner), RemoteDetector
│   ├── person.py               YOLOv8n people (and objects) per frame
│   ├── objects.py              objects in mm in the arm base frame
│   ├── calib.py                torso camera → arm base calibration
│   └── camera_test.py, camera_fps.py   diagnostics
├── robot/                      drivers for the hardware
│   ├── agv.py, nav.py          base: drive, markers; where to stop in front of a person
│   ├── head.py                 head yaw / pitch through the body API
│   ├── arm.py                  arm controller JSON commands
│   ├── motion.py               checked arm motion: named poses, joint and straight moves
│   └── gripper.py              Zimmer gripper
├── manipulation/
│   └── skills.py               pick / place / move an object
├── tasks/
│   └── fetch.py                fetch tasks: drive, find, pick, carry, hold / place / give (docs/16)
├── tests/                      self-checks without the robot
├── data/                       taught and calibrated values (see Shared state)
├── knowledge/                  texts Lumi answers from
├── logs/                       every log file
├── docs/, tools/               documentation; laptop scripts
├── lumi-api.service            starts the API at boot (systemd user service)
└── models/, whisper.cpp/, .venv/   local only (see Not in git)
```

Modules import each other by folder (`from robot import arm`, `from vision import camview`). The venv has `lumi_wave.pth` in its `site-packages` with the path of this folder, so any module runs directly, from any directory: `.venv/bin/python robot/gripper.py`.

---

## Architecture

```
                         browser / Swagger  http://192.168.10.240:8100/view  /docs
                                     │
 systemd lumi-api ──> api/server.py (FastAPI :8100) ───────── supervises ──> assistant/lumi.py
                       │   │   │                                             │   │   │   │
       /dev/shm/lumi_det_*.json, lumi_cam_*.jpg  <── vision/camview.py       │   │   │   └ brain.py ── Ollama gemma4 :11434
                       │   │                       (only camera owner,       │   │   │       ├ knowledge.py ── bge-m3 :8095
                       │   │                        person.py YOLOv8n)       │   │   │       └ web.py ── internet (Wi-Fi)
                       │   └ api/control.py (hold-to-move)                   │   │   └ audio/mouth.py ── Supertonic TTS ── speaker
                       │                                                     │   └ audio/ears.py ── whisper.cpp :8096
                       │                                                     │       └ audio/mic.py (head array + clip mic) ── doa.py
                       └──────── robot/: agv · head · arm · motion · gripper · nav ──┘
                                       │         │         │         │
                                AGV .10:31001  body .90:5000  arm controller .90:10001
```

- **`api/server.py`** is the entry point. It starts at boot, starts the camera service, whisper (:8096) and the embedding server (:8095), loads the LLM, and runs `assistant/lumi.py` while the Greeter or Patrol switch is on (restarting it if it dies). Commands from the dashboard (go, route, cancel, calibrate) are forwarded to the assistant while it runs (`/dev/shm/lumi_cmd.json`), so it can stop for people on the way; otherwise the API drives itself.
- **`vision/camview.py --serve`** is the **only** program that opens the Orbbec cameras (two openers make the SDK reset the devices). It runs detection on both cameras and shares the results through `/dev/shm`; everybody else uses `camview.RemoteDetector`.
- **`assistant/lumi.py`** is the assistant: tracks people, greets, listens, answers, obeys commands. Its behaviour is specified in [docs/14_VOICE_ASSISTANT.md](../../docs/14_VOICE_ASSISTANT.md).
- Modules talk to the hardware directly over the robot LAN; no ROS, no vendor SDK on the Thor (the shipped `jkrc.so` is x86-only).

### Shared state

| Path | Written by | Read by | Content |
|---|---|---|---|
| `/dev/shm/lumi_modes.json` | api | lumi | `greeter`, `patrol`, `wave`, `drive` switches |
| `/dev/shm/lumi_cmd.json` | api | lumi | dashboard command `{id, cmd: go | go_point | cancel | calibrate}` |
| `/dev/shm/lumi_det_<cam>.json` | camview | lumi, api | people per frame (box, distance, angle) |
| `/dev/shm/lumi_cam_<cam>.jpg/.json` | camview | api | latest picture for the dashboard |
| `/dev/shm/lumi_focus_<cam>.json` | lumi | camview | person drawn red (the one Lumi talks to) |
| `/dev/shm/lumi_raw_<cam>.jpg`, `lumi_intr_<cam>.json` | camview | calib, objects | full-size camera JPEG; colour intrinsics |
| `/dev/shm/lumi_task.json` | tasks/fetch (API or assistant) | api, assistant, dashboard | fetch task state, also what is held |
| `data/fetch_calib.json` | `tasks/fetch.py measure-axis` | tasks/fetch | angle between the arm base frame and the base (local) |
| `data/volume.txt` | api `/volume` | mouth | speaker volume % |
| `data/doa_calib.json`, `data/doa_samples.npz` | doa | doa | voice-direction calibration |
| `data/mic_source.txt` (optional) | you | mic | `auto` / `head` / `clip` |
| `data/proxy.txt` (optional) | you | web | HTTP proxy for internet lookups |
| `data/camera_extrinsics.json`, `data/calib_samples/` | calib | objects, skills | camera pose in the arm base frame; calibration samples (local, not in git) |
| `data/arm_poses.json` | motion `teach` | motion | taught joint poses (in git) |
| `data/grasp_teach.json` | taught by hand | skills | flange orientation and finger point around a cup (in git) |

---

## Modules

| Module | Job | Hardware / service |
|---|---|---|
| `api/server.py` | Robot API + Swagger (`/docs`), dashboard (`/view`), camera streams, supervisor of the assistant | all |
| `api/dashboard.html` | The single-page dashboard served at `/view` | |
| `api/control.py` | Hold-to-move for the dashboard: base `joy_control`, head / waist / lift steps, arm relative joint moves | base, body, arm |
| `assistant/lumi.py` | Voice assistant: tracking, greeting, conversation, commands, patrol, wake word | all |
| `assistant/brain.py` | Answers: knowledge search + Ollama `gemma4:e4b`, streamed, with an `ACTION:` line; rule-based intents | Ollama :11434 |
| `assistant/knowledge.py` | Knowledge base (RAG): `knowledge/**/*.md` → bge-m3 vectors → `knowledge/index.npz` | llama-server :8095 |
| `assistant/web.py` | Date / time, weather (open-meteo, cached), Wikipedia + Google News lookups | internet |
| `audio/mic.py` | Always-on microphone: head array (8 ch) and wireless clip mic, cut into utterances, barge-in | AIUI mic, DJI Mic Mini |
| `audio/ears.py` | Speech to text: whisper.cpp server (GPU, `large-v3-turbo`), language and confidence | whisper :8096 |
| `audio/mouth.py` | Text to speech: Supertonic-3 (EN / KO, voice F1), sentence by sentence, cache | USB speaker |
| `audio/doa.py` | Voice direction from the 6-mic ring (SRP-PHAT), self-calibrating from the camera | |
| `vision/camview.py` | Camera service: owns both cameras, detection, `/dev/shm` results, `RemoteDetector` | Orbbec (USB) |
| `vision/person.py` | YOLOv8n (ONNX, OpenCV DNN) person detection; distance from depth, angle from the box | |
| `vision/objects.py` | Objects in the torso camera (YOLO COCO classes): colour, centre / top / width / height in the arm base frame from depth + `data/camera_extrinsics.json`; called by the camera service, served as `/objects` | camera service |
| `vision/calib.py` | Torso camera → arm base calibration with the ArUco marker on the gripper (`collect`, `solve`, `check`), see [docs/15_PICK_AND_PLACE.md §8](../../docs/15_PICK_AND_PLACE.md) | camera service, arm controller |
| `vision/camera_test.py`, `camera_fps.py` | Diagnostics: list cameras and save a frame (to `logs/`); count full frames per second (USB 2 vs 3) | stop the camera service first |
| `robot/agv.py` | Base: status, markers, go to marker / point, turn, cancel | AGV `192.168.10.10:31001` |
| `robot/nav.py` | Where to stop in front of a person: free, reachable spot on the map | AGV map |
| `robot/head.py` | Head yaw / pitch through the body API | `192.168.10.90:5000` |
| `robot/arm.py` | Arm controller JSON commands (read-only ones retried), Cobo π programs (load / play / stop) | `192.168.10.90:10001` |
| `robot/motion.py` | Checked arm motion: named poses (`tuck`, taught `ready` in `data/arm_poses.json`), joint moves with limits and ±360° unwrapping, IK-checked straight moves, stop | arm controller `kine_inverse`, `joint_move`, `moveL` |
| `robot/gripper.py` | Zimmer gripper: open / close / state (DO_1, DO_2, AI_1, DI_1), see [docs/10_GRIPPER.md](../../docs/10_GRIPPER.md) | tool I/O via the arm controller |
| `manipulation/skills.py` | Pick and place: `plan` (dry run with IK for every waypoint), `pick`, `put_down` (back or a free spot), `move` an object to a spot or a free place; `cancel()` stops a running skill for good; the grasp taught in `data/grasp_teach.json`; refuses objects of the wrong width and unreachable plans with a spoken-style reason. Called by the CLI, the API (`/skills/*`, in the background) and the assistant (voice) | motion, gripper, objects |
| `tasks/fetch.py` | Fetch tasks ([docs/16_FETCH_TASKS.md](../../docs/16_FETCH_TASKS.md)): drive to the source, find, shift the base if out of reach, pick, `carry`, drive to the destination, hold / place / give; state in `/dev/shm/lumi_task.json`; run by the API or the assistant | base, arm, gripper, camera service |
| `assistant/fetch_dialog.py` | Voice fetch: ask what is missing, read the task back, start on yes or silence, take corrections | |
| `tests/test_*.py` | Self-checks without the robot: objects, skills, intents, fetch runner, fetch voice parsing and dialog, camera choice | |
| `knowledge/` | `lumi_about_en.md` (visitor facts, in git); `jaka_zh/` and `index.npz` are local | |

---

## Run

Always with the venv (the system Python has no OpenCV):

```bash
cd ~/Dev/lumi-wave
.venv/bin/python api/server.py                  # normally started at boot
.venv/bin/python assistant/lumi.py              # assistant in the terminal (stop the dashboard's Greeter/Patrol first)
.venv/bin/python assistant/lumi.py --no-camera --no-drive
.venv/bin/python assistant/brain.py --act       # type questions, see answers and actions
.venv/bin/python audio/ears.py                  # speak, see the text
.venv/bin/python audio/mouth.py "Hello"         # Lumi says it
.venv/bin/python robot/gripper.py               # gripper state
.venv/bin/python robot/motion.py                # joints, TCP, named poses; robot.motion go ready
.venv/bin/python vision/objects.py --watch      # what the torso camera sees, in mm
.venv/bin/python manipulation/skills.py plan cup   # dry run of a pick and place (nothing moves)
.venv/bin/python assistant/web.py weather Seoul
.venv/bin/python assistant/knowledge.py build   # after changing knowledge/
.venv/bin/python vision/camview.py --stop       # free the cameras for camera_test / camera_fps
for t in tests/test_*.py; do .venv/bin/python $t; done
```

Boot: the user service `lumi-api` ([lumi-api.service](lumi-api.service), installed in `~/.config/systemd/user/`, linger on, so no login is needed) starts `api/server.py` 20 s after boot and restarts it 5 s after it dies. Restarting the API does not stop the camera service, whisper or a running assistant.

```bash
systemctl --user status lumi-api       # running? since when?
systemctl --user restart lumi-api      # after changing api/, robot/ or manipulation/
systemctl --user stop lumi-api         # stays stopped until start or the next boot
```

Logs are in `logs/`: `lumi.log` (assistant), `lumi_console.log` (its stderr), `api.log`, `camview.log`, `whisper_server.log`, `embed_server.log`. The dashboard's Settings → Logs shows the assistant log and highlights real errors.

---

## Deploying a change

1. Check that the robot is not driving: `curl -s localhost:8100/status` → `base.move_status` must not be `running`. **Restarting the assistant cancels a drive in progress.**
2. Edit, then `.venv/bin/python -m py_compile <file>`.
3. Restart what uses the file: `assistant/`, `audio/` modules → switch Greeter/Patrol off and on in the dashboard (the API restarts the assistant); `api/` → `systemctl --user restart lumi-api`; `vision/camview.py`, `vision/person.py`, `vision/objects.py` → `vision/camview.py --stop` then `--serve`. `robot/` and `manipulation/` are used by all of them: restart the API, and the assistant if it runs.
4. Watch `logs/lumi.log` / Settings → Logs.

---

## Not in git (local on the Thor)

| Path | What | How it was made |
|---|---|---|
| `logs/` | all log files | written at run time |
| `data/camera_extrinsics.json`, `data/calib_samples/`, `data/doa_*`, `data/volume.txt` | calibrations and settings of this robot | `vision/calib.py`, `audio/doa.py`, the dashboard |
| `.venv/` | Python 3.12 venv (plus `site-packages/lumi_wave.pth`, one line: the path of this folder): numpy, opencv-python-headless, pyorbbecsdk2, fastapi, uvicorn, supertonic, soundfile | wheels downloaded on a Mac and installed offline (the Thor's internet was too slow at the time) |
| `models/yolov8n.onnx` | person / object detector | `YOLO("yolov8n.pt").export(format="onnx", imgsz=640, opset=12, simplify=True)` |
| `models/ggml-large-v3-turbo-q5_0.bin` | whisper model | Hugging Face `ggerganov/whisper.cpp` |
| `models/supertonic3/` | TTS model | Hugging Face `Supertone/supertonic-3` |
| `whisper.cpp/` | v1.9.5, built with CUDA | `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=110 -DCMAKE_BUILD_TYPE=Release && cmake --build build -j 12 --target whisper-server whisper-cli` |
| `~/models/bge-m3-Q8_0.gguf` | embedding model for the knowledge base | Hugging Face |
| `knowledge/jaka_zh/` | 13 JAKA product texts (Chinese) from JAKA's voice service | vendor |
| Ollama `gemma4:e4b` | LLM | `ollama pull gemma4:e4b` |

Orbbec cameras need the udev rule `SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"` in `/etc/udev/rules.d/99-orbbec.rules`.

---

## Hardware notes

- **Cameras**: two Gemini 2 L. **Torso** (SN CPA9B520037, USB 3, colour + depth): objects, pick and place, calibration, and people while the base drives (it always looks forward). **Head** (SN CPA9B52007A) sits behind a hub inside the head, shared with the mic array and the speaker. The hub was USB 2 and the camera reset while the speaker played; it was replaced by a USB 3 hub on 2026-10-15 (camera at 5 Gb/s, colour stream steady while speaking). Colour + depth on the head camera also hold while the speaker plays (`vision/camera_fps.py head`: 14.9 fps, no frame lost after the start). The camera service opens the head camera with depth when it is linked at USB 3 speed and colour only at USB 2 (`DEPTH_MIN_MBPS`, distance then from the torso camera). The head camera watches people while Lumi stands (it turns with the head); `assistant/lumi.py` falls back to the other camera while one gives no detections. Choose cameras by name (`head` / `torso`), never by index.
- **Microphones**: head array AIUI-USB-MC (8 ch at 16 kHz, mics 0–5). A DJI Mic Mini receiver in a USB-A port (through a USB-C→A adapter; the Thor's USB-C ports are device-mode) is used automatically when present. It is 5–10× louder at 4–5 m. Keep its transmitter on the visitor, not on the robot.
- **Speaker** volume 55 % (100 % is too loud for the office).
- **Internet** comes from the Thor's own Wi-Fi (`wlP1p1s0` → company network, route metric 600). The robot LAN (`enP2p1s0`, gateway 192.168.10.9) has none.
- **Base**: `/api/make_plan` and `accessible_point_query` do not check real paths; `nav.py` uses the map image instead. The lidar does not see glass: closed glass doors need a no-go line in the AGV panel.
- **Body**: `/stop` does not stop a `moveto`, so hold-to-move uses small steps.

---

## Pitfalls

- `pkill -f <pattern>` / `pgrep -f` over SSH also match the SSH command line that contains the pattern and kill your own shell. Look up the PID first, or build the pattern from pieces.
- Never open the cameras from a second program while `camview.py --serve` runs.
- Headless Chrome screenshots of the dashboard: do not use `--timeout` (it freezes the page's JavaScript).
- Other projects on this Thor belong to colleagues (`~/Dev/lumi_edu` :8000/:8090, `lumi-vision-api` :8001, docs :3080). Do not touch them.
