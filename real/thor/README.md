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
python lumi.py --patrol aisle_a,aisle_b   # assistant + drive between markers in a loop
```

Always run with the venv (`source .venv/bin/activate` or `.venv/bin/python`); the system `python` has no cv2.
Patrol: only people in the robot's path (0.4 m to each side) closer than 1.0 m stop it; people sitting beside the aisle are ignored (`see` log marks them `side`). With no answer for 8 s the patrol goes on. Below 5 % battery Lumi drives to the dock (`home`) and patrols again from 60 % (`LOW_BATTERY`, `RESUME_BATTERY` in `lumi.py`).

Voice setup (2026-10-07, all downloaded on the Mac and copied): wheels `supertonic faster-whisper soundfile` (into `~/voice_pkgs`), model `models/supertonic3/` (Supertone/supertonic-3, 385 MB), `models/whisper-small/` (faster-whisper, CPU fallback, ~4 s — too slow), `models/ggml-large-v3-turbo-q5_0.bin` (574 MB) and `whisper.cpp/` v1.9.5 built on the Thor:
`cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=110 -DCMAKE_BUILD_TYPE=Release && cmake --build build -j 12 --target whisper-server whisper-cli` (PATH must include /usr/local/cuda/bin).
The Thor gives this user 14 CPU cores (`nproc`), so speech models run on the GPU where possible.

## Notes

- Camera 0 = SN CPA9B520037 (USB 3). Camera 1 = SN CPA9B52007A is on a USB 2 extension and drops out; it needs a USB 3 cable.
- `HEAD_SIGN` in `greeter.py` / `lumi.py` and `LOOK` in `lumi.py`: whether +head yaw is the robot's left and +pitch is down. Not verified yet; check with `python head.py 10` and `python head.py 0 10`.
- Navigation needs a map of the room the robot is in. Current map: `cutshion_708_B_block` with markers `home_dock` (type 11, the dock, called `home` in code), `aisle_a`, `aisle_b`.
- The camera is mounted on the waist link, the head yaw is relative to the waist, so the image angle is used directly as head yaw while the waist stays still.
- Detection runs at about 14 fps on the Thor CPU.
