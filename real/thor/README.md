# Lumi greeter and voice assistant (runs on the Jetson Thor)

When a person stands 0.5–1.2 m in front of the robot, Lumi waves (Cobo π program `hand_shaking.jks`), says "Hello, I am Lumi Robot Assistant. How can I help you?" and turns its head to them. `lumi.py` then listens and answers in English or Korean from its knowledge base, and obeys voice commands (go to a marker, go home, look left/right/up/down, wave, stop).

| File | What it does | Talks to |
|---|---|---|
| `camera_test.py` | Lists the Orbbec cameras, grabs colour + depth, saves `color_<id>.jpg` | cameras (USB) |
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
| `greeter.py` | Puts it together; `--dry-run`, `--no-arm`, `--no-head`, `--camera N` | all of the above |
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
python person.py 0 --save        # detection only, 20 s, person_view.jpg
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
- `lumi.py` logs `camera ok: N fps` every 30 s and reopens the camera after 3 s without frames.
- Restarting the API over SSH: `pkill -f "bin/python api.py"` also matches the SSH shell's own command line if it contains that text; start it in a separate SSH call.
- The camera is mounted on the waist link, the head yaw is relative to the waist, so the image angle is used directly as head yaw while the waist stays still.
- Detection runs at about 14 fps on the Thor CPU.
