# Lumi greeter and voice assistant (runs on the Jetson Thor)

When a person stands 0.5–1.2 m in front of the robot, Lumi waves (Cobo π program `hand_shaking.jks`), says "Hello, I am Lumi Robot Assistant. How can I help you?" and turns its head to them. `lumi.py` then listens and answers in English or Korean from its knowledge base, and obeys voice commands (go to a marker, go home, look left/right/up/down, wave, stop).

| File | What it does | Talks to |
|---|---|---|
| `camera_test.py` | Lists the Orbbec cameras, grabs colour + depth, saves `color_<id>.jpg` | cameras (USB) |
| `camview.py` | Camera service: owns both cameras, detects people, shares results and pictures (`RemoteDetector`) | cameras |
| `control.py` | Hold-to-move for the dashboard: base (`joy_control`), head / waist / lift (small `moveto` steps), arm joints (relative `joint_move`) | base, body, arm |
| `mic.py` | Always-on microphone (8 ch, mics 0–5), cut into utterances; muted while Lumi speaks | mic |
| `doa.py` | Sound direction from the 6-mic ring (SRP-PHAT); calibrates itself from the camera (`doa_calib.json`), or `python doa.py --calibrate` | mic |
| `nav.py` | Where to drive to reach a person: free spot ~1 m in front of them, reachable on the map | base |
| `dashboard.html` | The web dashboard served by `api.py` at `/view` | — |
| `camera_fps.py` | Streams colour + depth from one camera and counts full frames (USB 2 vs USB 3 check) | cameras (USB) |
| `person.py` | YOLOv8n (ONNX, OpenCV DNN, CPU) finds people; depth aligned to colour gives the distance, the box position gives the angle | cameras |
| `speak.py` | Plays a WAV on the robot's USB speaker (`aplay`) | speaker (USB) |
| `head.py` | Head yaw/pitch through the body HTTP API, other joints unchanged, slow | `192.168.10.90:5000` |
| `arm.py` | Loads/starts/stops a Cobo π program over the controller's TCP port 10001 (no SDK) | `192.168.10.90:10001` |
| `knowledge.py` | Knowledge base (RAG): `knowledge/**/*.md|txt` → ~500-character chunks → bge-m3 vectors (llama.cpp `llama-server` on 127.0.0.1:8095, started when needed) → `knowledge/index.npz`; `build`, `search` | `~/models/bge-m3-Q8_0.gguf` |
| `brain.py` | Answers: best chunks + question → Ollama `gemma4:e4b`, short spoken-style reply in the question's language (English/Korean), keeps the last 4 turns | Ollama 127.0.0.1:11434 |
| `knowledge/lumi_about_en.md` | Visitor-facing facts about Lumi (English) | |
| `knowledge/jaka_zh/` | Not in git: 13 JAKA product/company texts (Chinese) copied from JAKA's voice service `DataDoc/` (exhibition-only files left out) | |
| `ears.py` | Listening: AIUI mic (8 ch, 0–5 = mics) → energy speech detector → whisper.cpp server (GPU, large-v3-turbo, 127.0.0.1:8096) → text. ~0.5 s per utterance | mic (USB) |
| `mouth.py` | Speaking: Supertonic-3 TTS (English/Korean, voice F1) sentence by sentence → USB speaker | speaker (USB) |
| `agv.py` | Base: status, markers (dock = "home"), go to marker, cancel | `192.168.10.10:31001` |
| `brain.py` `respond()` | Same RAG + gemma4, JSON output `{action, target, say}`; actions go_to / look / wave / stop / end / none | |
| `lumi.py` | **Voice assistant**: camera → greet (wave + voice + head) → listen → answer / act → … until goodbye, silence or the visitor leaves. `--no-camera`, `--no-arm`, `--no-drive` | all |
| `api.py` | **Robot API + Swagger** on :8100 (`/docs`): status, markers, drive, head, wave, say, ask, start/stop `lumi.py`, log. Starts at boot (crontab `@reboot`) | all |
| `greeter.py` | Puts it together; `--dry-run`, `--no-arm`, `--no-head`, `--camera head|torso` | all of the above |
| `sounds/hello.wav` | Made on a Mac: `say -v Samantha -r 165 -o hello.aiff "Hello, I am Lumi Robot Assistant. How can I help you?"` + `afconvert -f WAVE -d LEI16@22050 -c 1` | |
| `models/yolov8n.onnx` | Not in git. Made on a Mac: `pip install ultralytics onnx onnxslim`, `YOLO("yolov8n.pt").export(format="onnx", imgsz=640, opset=12, simplify=True)` | |

## Setup on the Thor (done 2026-10-07)

The Thor's internet was too slow, so packages were downloaded on the Mac and copied:

```bash
# Mac
python3 -m pip download --only-binary=:all: --python-version 3.12 --implementation cp \
  --platform manylinux_2_28_aarch64 --platform manylinux_2_27_aarch64 \
  --platform manylinux2014_aarch64 --platform manylinux_2_17_aarch64 \
  -d thor_pkgs pip pyorbbecsdk2 opencv-python-headless numpy
curl -o thor_pkgs/get-pip.py https://bootstrap.pypa.io/get-pip.py
scp -r thor_pkgs <user>@<thor>:~/
scp real/thor/*.py <user>@<thor>:~/Dev/lumi-wave/   # plus sounds/ and models/

# Thor
cd ~/Dev/lumi-wave
python3 -m venv --without-pip .venv && source .venv/bin/activate
python ~/thor_pkgs/get-pip.py --no-index --find-links ~/thor_pkgs
pip install --no-index --find-links ~/thor_pkgs numpy opencv-python-headless
pip install --no-index --find-links ~/thor_pkgs --no-deps pyorbbecsdk2
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"' | sudo tee /etc/udev/rules.d/99-orbbec.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## Run

```bash
cd ~/Dev/lumi-wave && source .venv/bin/activate
python person.py head --save     # detection only, 20 s, person_view.jpg (or: torso)
python greeter.py --dry-run      # nothing moves
python greeter.py --no-arm       # head + voice
python greeter.py                # head + voice + wave
python knowledge.py build        # after adding/changing files in knowledge/
python brain.py                  # type questions, Lumi answers from the knowledge base
python brain.py --act            # also shows the action it would take
python ears.py                   # say something, see the text
python mouth.py "Hello"          # Lumi says it
python lumi.py --no-camera --no-drive   # voice assistant, Enter starts a conversation
python lumi.py                   # full assistant
python lumi.py --patrol a,b      # assistant + drive between markers in a loop
python lumi.py --patrol p1,p2,p3,p4,p5,p6,p7,p8,final,p9,p10,home --once --pause 1   # drive a route once, end on the dock
```

Always run with the venv (`source .venv/bin/activate` or `.venv/bin/python`); the system `python` has no cv2.
Patrol: only people in the robot's path (0.4 m to each side) closer than 1.0 m stop it; people sitting beside the aisle are ignored (`see` log marks them `side`). With no answer for 8 s the patrol goes on. Below 5 % battery Lumi drives to the dock (`home`) and patrols again from 60 % (`LOW_BATTERY`, `RESUME_BATTERY` in `lumi.py`).

Voice setup (2026-10-07, all downloaded on the Mac and copied): wheels `supertonic faster-whisper soundfile` (into `~/voice_pkgs`), model `models/supertonic3/` (Supertone/supertonic-3, 385 MB), `models/whisper-small/` (faster-whisper, CPU fallback, ~4 s — too slow), `models/ggml-large-v3-turbo-q5_0.bin` (574 MB) and `whisper.cpp/` v1.9.5 built on the Thor:
`cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=110 -DCMAKE_BUILD_TYPE=Release && cmake --build build -j 12 --target whisper-server whisper-cli` (PATH must include /usr/local/cuda/bin).
The Thor gives this user 14 CPU cores (`nproc`), so speech models run on the GPU where possible.

## Robot API (api.py)

Open `http://192.168.10.240:8100/docs` from a computer on the robot Wi-Fi and use "Try it out".
- `GET /status`, `GET /agv/markers`, `GET /assistant/log` only read.
- `POST /agv/go`, `/head/turn`, `/arm/wave`, `/say`, `/ask` move or speak. While `lumi.py` runs they answer 409; stop it with `POST /assistant/stop`.
- `POST /assistant/start` `{"patrol": "p1,...,home", "once": true, "pause": 1}` starts the assistant without a terminal; its errors go to `lumi_console.log`.
- Autostart: crontab line `@reboot sleep 20 && cd /home/cutshion/Dev/lumi-wave && .venv/bin/python api.py >> api.log 2>&1` (`crontab -e` to remove). Manual start: `setsid nohup .venv/bin/python api.py >> api.log 2>&1 &`.
- Packages: `fastapi uvicorn` wheels downloaded on the Mac (`pip download ... --platform manylinux2014_aarch64`) and installed offline.
- Only on the local networks; not exposed through the Cloudflare tunnel.

## Notes

- Camera 0 = SN CPA9B520037 (USB 3). Camera 1 = SN CPA9B52007A is on a USB 2 extension and drops out; it needs a USB 3 cable.
- `HEAD_SIGN` in `greeter.py` / `lumi.py` and `LOOK` in `lumi.py`: whether +head yaw is the robot's left and +pitch is down. Not verified yet; check with `python head.py 10` and `python head.py 0 10`.
- Navigation needs a map of the room the robot is in. Map `cutshion_708_B_block` (extended 2026-10-08 with "continue scan" to the corridor and a second room): dock marker `Home` (type 11; `home` in code finds any type-11 marker), aisle `a`, `b`, route `p1`–`p10`, `final`.
- Glass doors are invisible to the lidar: draw a no-go line (panel "add line") over closed glass leaves. One open leaf leaves ~0.7 m, too narrow for the 0.54 m base (+ the arm); open both leaves.
- `/api/make_plan` returns the straight-line distance, not a real path check: test a route by driving it.
- The arm sticks out ~11 cm to the right of the base (hit a door frame). Planned: Cobo π program `arm_tuck.jks` (sim suggestion J1 178, J2 -88, J3 -12, J4 -16, J5 -14, J6 -123, ~5 cm left out) run before every drive.
- `lumi.py` logs `camera ok (head): N fps` every 30 s and reopens the camera after 3 s without frames.
- Restarting the API over SSH: `pkill -f "bin/python api.py"` also matches the SSH shell's own command line if it contains that text; start it in a separate SSH call.
- **Dashboard:** http://192.168.10.240:8100/view (`dashboard.html`): both cameras (person boxes; the person Lumi talks to in red), live map with the robot and markers (click a marker / a point to drive, scroll to zoom), hold-to-move base / head (keys W A S D), destinations, wave / fold arm / say / ask / volume, assistant start/stop; ⚙ Settings: box colour, lift / waist, arm joints J1–J6 (hold − / +), power / enable, programs, maps (switch), patrol route, logs. STOP button = `POST /stop`. Hold-to-move is `control.py` (`POST /jog` every 150 ms; small steps, so releasing stops within one step).
- **Camera service (`camview.py --serve`):** the only program that opens the Orbbec cameras (two programs opening them make the SDK reset the devices: the head camera then disconnected every ~2.5 s). Started by `api.py` at boot and by `lumi.py` / `greeter.py` if needed; it detects people on both cameras and writes `/dev/shm/lumi_det_<name>.json` (read by `camview.RemoteDetector`, same `read()` as `PersonDetector`) and `/dev/shm/lumi_cam_<name>.jpg` (dashboard). `python camview.py --stop` frees the cameras for `camera_fps.py` / `camera_test.py` and keeps it off until `--start`.
- **Head camera without depth:** its depth stream + the speaker playing (same USB 2 hub in the head) make the camera disconnect (5 disconnects for 3 greetings; colour only: 0). The head camera runs colour only; a person's distance comes from the torso camera's depth at the same angle (within 8°), else from the box size.
- **Voice:** wake word "Hi / Hey Lumi" (whisper on each short utterance), the voice direction picks who spoke, "come here" drives to the person (`nav.py`); replies are streamed (first sentence ~2 s after the question). Speaker volume: `volume.txt` / dashboard (default 55 %, 100 % disturbed the office).
- Two Gemini 2 L cameras: **head** (SN CPA9B52007A) and **torso** (SN CPA9B520037, on the waist link). Choose them by name (`--camera head|torso`), not by index: the index order changes when USB cables are moved. Default: head.
- The head camera sits behind a USB 2.0 hub inside the head (GenesysLogic 05e3:0610, shared with the AIUI mic and the speaker), so it always runs at 480M whatever cable is used. Its default depth mode is then 1280x800 at 10 fps with broken framesets; `person.py` asks for 1280x720 MJPG colour + 640x400 depth at 15 fps, which gives clean frames on USB 2 (~15 fps detection, the CPU YOLO limit anyway). Check with `python camera_fps.py <index>` and `cat /sys/bus/usb/devices/*/speed`.
- Person angles are relative to the waist: for the head camera `person.py` adds the current head yaw (read every 0.2 s), so tracks do not jump when the head turns and the head command stays absolute. This needs `HEAD_SIGN` to be right (still to verify).
- Detection runs at about 14 fps on the Thor CPU.
