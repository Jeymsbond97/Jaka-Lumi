# Lumi onboard software (Jetson Thor)

Everything that runs on the robot's NVIDIA Jetson Thor (`192.168.10.240`). It covers the robot API with Swagger and the web dashboard, the camera service with person detection, and the voice assistant (`lumi.py`), which greets visitors, talks with them in English and Korean and drives where it is told. It also holds the device drivers for the base, body, arm and gripper.

On the Thor this folder is `~/Dev/JakaLumi_simulation/real/thor`; `~/Dev/lumi-wave` is a symlink to it (the boot crontab and the venv use that path).

---

## Architecture

```
                         browser / Swagger  http://192.168.10.240:8100/view  /docs
                                     │
 crontab @reboot ──> api.py (FastAPI :8100) ──────────────── supervises ──> lumi.py (voice assistant)
                       │   │   │                                             │   │   │   │
       /dev/shm/lumi_det_*.json, lumi_cam_*.jpg  <── camview.py --serve      │   │   │   └ brain.py ── Ollama gemma4 :11434
                       │   │                       (only camera owner,       │   │   │       ├ knowledge.py ── bge-m3 :8095
                       │   │                        person.py YOLOv8n)       │   │   │       └ tools.py ── web (Wi-Fi)
                       │   └ control.py (hold-to-move)                       │   │   └ mouth.py ── Supertonic TTS ── speaker
                       │                                                     │   └ ears.py ── whisper.cpp :8096
                       │                                                     │       └ mic.py (head array + clip mic) ── doa.py
                       └──────────── agv.py · head.py · arm.py · gripper.py · nav.py ────┘
                                       │         │         │         │
                                AGV .10:31001  body .90:5000  arm controller .90:10001
```

- **`api.py`** is the entry point. It starts at boot, starts the camera service and runs `lumi.py` while the Greeter or Patrol switch is on (restarting it if it dies). Commands from the dashboard (go, route, cancel, calibrate) are forwarded to `lumi.py` while it runs (`/dev/shm/lumi_cmd.json`), so the assistant can stop for people on the way; otherwise the API drives itself.
- **`camview.py --serve`** is the **only** program that opens the Orbbec cameras (two openers make the SDK reset the devices). It runs person detection on both cameras and shares the results through `/dev/shm`; everybody else uses `camview.RemoteDetector`.
- **`lumi.py`** is the assistant: tracks people, greets, listens, answers, obeys commands. Its behaviour is specified in [docs/14_VOICE_ASSISTANT.md](../../docs/14_VOICE_ASSISTANT.md).
- Modules talk to the hardware directly over the robot LAN; no ROS, no vendor SDK on the Thor (the shipped `jkrc.so` is x86-only).

### Shared state

| Path | Written by | Read by | Content |
|---|---|---|---|
| `/dev/shm/lumi_modes.json` | api.py | lumi.py | `greeter`, `patrol`, `wave`, `drive` switches |
| `/dev/shm/lumi_cmd.json` | api.py | lumi.py | dashboard command `{id, cmd: go | go_point | cancel | calibrate}` |
| `/dev/shm/lumi_det_<cam>.json` | camview.py | lumi.py, api.py | people per frame (box, distance, angle) |
| `/dev/shm/lumi_cam_<cam>.jpg/.json` | camview.py | api.py | latest picture for the dashboard |
| `/dev/shm/lumi_focus_<cam>.json` | lumi.py | camview.py | person drawn red (the one Lumi talks to) |
| `volume.txt` | api.py `/volume` | mouth.py | speaker volume % |
| `doa_calib.json`, `doa_samples.npz` | doa.py | doa.py | voice-direction calibration |
| `mic_source.txt` (optional) | you | mic.py | `auto` / `head` / `clip` |

---

## Modules

| Module | Job | Hardware / service |
|---|---|---|
| `api.py` | Robot API + Swagger (`/docs`), dashboard (`/view`), camera streams, supervisor of `lumi.py` | all |
| `dashboard.html` | The single-page dashboard served at `/view` | |
| `control.py` | Hold-to-move for the dashboard: base `joy_control`, head / waist / lift steps, arm relative joint moves | base, body, arm |
| `camview.py` | Camera service: owns both cameras, detection, `/dev/shm` results, `RemoteDetector` | Orbbec (USB) |
| `person.py` | YOLOv8n (ONNX, OpenCV DNN) person detection; distance from depth, angle from the box | |
| `lumi.py` | Voice assistant: tracking, greeting, conversation, commands, patrol, wake word | all |
| `brain.py` | Answers: knowledge search + Ollama `gemma4:e4b`, streamed, with an `ACTION:` line; rule-based intents | Ollama :11434 |
| `knowledge.py` | Knowledge base (RAG): `knowledge/**/*.md` → bge-m3 vectors → `knowledge/index.npz` | llama-server :8095 |
| `tools.py` | Date / time, weather (open-meteo, cached), Wikipedia + Google News lookups | internet |
| `ears.py` | Speech to text: whisper.cpp server (GPU, `large-v3-turbo`), language and confidence | whisper :8096 |
| `mic.py` | Always-on microphone: head array (8 ch) and wireless clip mic, cut into utterances, barge-in | AIUI mic, DJI Mic Mini |
| `doa.py` | Voice direction from the 6-mic ring (SRP-PHAT), self-calibrating from the camera | |
| `mouth.py` | Text to speech: Supertonic-3 (EN / KO, voice F1), sentence by sentence, cache | USB speaker |
| `agv.py` | Base: status, markers, go to marker / point, turn, cancel | AGV `192.168.10.10:31001` |
| `nav.py` | Where to stop in front of a person: free, reachable spot on the map | AGV map |
| `head.py` | Head yaw / pitch through the body API | `192.168.10.90:5000` |
| `arm.py` | Arm controller JSON commands, Cobo π programs (load / play / stop) | `192.168.10.90:10001` |
| `gripper.py` | Zimmer gripper: open / close / state (DO_1, DO_2, AI_1, DI_1), see [docs/10_GRIPPER.md](../../docs/10_GRIPPER.md) | tool I/O via the arm controller |
| `camera_test.py`, `camera_fps.py` | Diagnostics: list cameras and save a frame; count full frames per second (USB 2 vs 3) | stop the camera service first |
| `knowledge/` | `lumi_about_en.md` (visitor facts, in git); `jaka_zh/` and `index.npz` are local | |

---

## Run

Always use the venv (`.venv/bin/python`); the system Python has no OpenCV.

```bash
cd ~/Dev/lumi-wave
.venv/bin/python api.py                     # normally started at boot
.venv/bin/python lumi.py                    # assistant in the terminal (stop the dashboard's Greeter/Patrol first)
.venv/bin/python lumi.py --no-camera --no-drive
.venv/bin/python brain.py --act             # type questions, see answers and actions
.venv/bin/python ears.py                    # speak, see the text
.venv/bin/python mouth.py "Hello"           # Lumi says it
.venv/bin/python gripper.py                 # gripper state
.venv/bin/python tools.py weather Seoul
.venv/bin/python knowledge.py build         # after changing knowledge/
.venv/bin/python camview.py --stop          # free the cameras for camera_test.py / camera_fps.py
```

Boot: crontab `@reboot sleep 20 && cd /home/cutshion/Dev/lumi-wave && .venv/bin/python api.py >> api.log 2>&1`.
Manual restart of the API: find its PID (`pgrep -f "python api.py"`) and `kill` it, then
`setsid .venv/bin/python api.py >> api.log 2>&1 < /dev/null &`.

Logs: `lumi.log` (assistant), `lumi_console.log` (its stderr), `api.log`, `camview.log`, `whisper_server.log`, `embed_server.log`. The dashboard's Settings → Logs shows the assistant log and highlights real errors.

---

## Deploying a change

1. Check that the robot is not driving: `curl -s localhost:8100/status` → `base.move_status` must not be `running`. **Restarting `lumi.py` cancels a drive in progress.**
2. Edit, then `python -m py_compile <file>`.
3. Restart what uses the file: `lumi.py` modules → switch Greeter/Patrol off and on in the dashboard (the API restarts it); `api.py`, `control.py`, `dashboard.html` → restart the API; `camview.py`, `person.py` → `camview.py --stop` then `--serve`.
4. Watch `lumi.log` / Settings → Logs.

---

## Not in git (local on the Thor)

| Path | What | How it was made |
|---|---|---|
| `.venv/` | Python 3.12 venv: numpy, opencv-python-headless, pyorbbecsdk2, fastapi, uvicorn, supertonic, soundfile | wheels downloaded on a Mac and installed offline (the Thor's internet was too slow at the time) |
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

- **Cameras**: two Gemini 2 L. **Torso** (SN CPA9B520037, USB 3, colour + depth) is used for behaviour. **Head** (SN CPA9B52007A) sits behind a USB 2 hub inside the head, shared with the mic array and the speaker. It resets when depth streams while the speaker plays, so it runs colour only and is display-only. Choose cameras by name (`head` / `torso`), never by index.
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
