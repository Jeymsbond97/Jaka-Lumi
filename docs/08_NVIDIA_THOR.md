# 08. NVIDIA Jetson AGX Thor

Main AI computer for Lumi: runs large models (e.g. a voice assistant), vision and our control code. IP, user and password: [private/ACCESS.md](private/ACCESS.md#nvidia-jetson-agx-thor-company-main-computer-for-lumi-ai).

---

## 1. What it is

| Item | Value |
|---|---|
| Model | NVIDIA Jetson AGX Thor Developer Kit |
| Compute | 2070 TOPS (INT8), Blackwell GPU (1.57 GHz), 72-core Arm v9 CPU (2.6 GHz) |
| Memory | up to 128 GB unified |
| Storage | PCIe 5.0 NVMe + UFS 4.0 |
| Power | 30–120 W (configurable) |
| Latest JetPack (NVIDIA, 2026-08) | JetPack 7.2.1, Jetson Linux r39.2.1 |
| Ports | 2 × USB-C (power/data), USB-A, HDMI/DisplayPort, Ethernet, Debug-USB behind the lid |

Why Thor: JAKA's table ([01_HARDWARE.md](01_HARDWARE.md#6-main-ai-computer-options)) puts large multimodal models (≥ 30B, VLA, ACT, LLM + vision) on the AGX Thor. The voice assistant needs about 80 GB of GPU memory.

---

## 2. Connect

SSH from a computer on the same network as the Thor: `ssh <user>@<thor-ip>`, port 22 (use `ssh -X` for GUI programs such as OrbbecViewer or RViz). When the Thor is mounted on the robot it is on the robot network (`192.168.10.x`); find its address on the router page `http://192.168.10.79` (connected devices) or with `nmap -sn 192.168.10.0/24`. Our addresses and login: [private/THOR_COMPANY_SETUP.md](private/THOR_COMPANY_SETUP.md) and [private/ACCESS.md](private/ACCESS.md) (local only).

---

## 3. Install the OS (only if it must be re-flashed)

NVIDIA quick start: https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/quick_start.html

You need: a PC with 25 GB free, a USB stick ≥ 16 GB, a monitor + keyboard (or a USB-C cable for headless setup).

1. Download the installer ISO (e.g. `jetsoninstaller-r39.2.1-...-arm64.iso`) from NVIDIA Developer Downloads.
2. Write it with **Balena Etcher** (https://etcher.balena.io). Copying the file to the stick does not work.
3. Plug the stick into the Thor (USB-A or USB-C), connect the bundled USB-C power supply, press the power button (left button on the side).
4. Boot from USB: Enter (or wait); accept the **QSPI capsule update** with **Y** (do not skip); installation to NVMe takes about 10 minutes, then it reboots.
5. **Remove the USB stick** right away.
6. First-boot wizard (oem-config): keyboard, licence, network, time zone, user name and password, hostname. Headless: connect the USB-C cable to a PC, open a serial terminal, press Tab then Enter.
7. Notes: use the bundled power supply; avoid KVM switches; display issues in headless mode on factory UEFI 38.0.0 (see NVIDIA's workaround); devices reinstalled with a pre-7.2 ISO may need UEFI changes.
8. Then install JetPack components and CUDA (NVIDIA pages "JetPack SDK Setup", "CUDA Setup").

---

## 4. Docker on the Thor

If `docker compose` does not work on a fresh system, reinstall Docker with NVIDIA's procedure (https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_docker.html):

```bash
sudo apt-get update
sudo apt install -y nvidia-container curl
curl https://get.docker.com | sh && sudo systemctl --now enable docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl daemon-reload && sudo systemctl restart docker

# make nvidia the default runtime
sudo apt install -y jq
sudo jq '. + {"default-runtime": "nvidia"}' /etc/docker/daemon.json | sudo tee /etc/docker/daemon.json.tmp \
  && sudo mv /etc/docker/daemon.json.tmp /etc/docker/daemon.json

# run docker without sudo
sudo usermod -aG docker $USER && newgrp docker && sudo systemctl restart docker

# check: compose and GPU
docker compose version
docker run --rm -it nvcr.io/nvidia/pytorch:25.08-py3 python3 -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

`/etc/docker/daemon.json` should contain `"runtimes": {"nvidia": {"path": "nvidia-container-runtime", "args": []}}` and `"default-runtime": "nvidia"`.

---

## 5. Company voice services on the Thor

Installation and layout of the company's voice-assistant containers: [private/THOR_COMPANY_SETUP.md](private/THOR_COMPANY_SETUP.md) (local only).

---

## 6. Using the Thor for our robot work

- The JAKA SDK has an `aarch64-linux-gnu` build, so `jkrc` runs natively on the Thor (Ubuntu 24.04, Python 3.12: check that `jkrc.so` loads; otherwise use a Python 3.10 container).
- Orbbec SDK has arm64 `.deb` packages and the vendor's Jetson Docker setup for cameras ([06](06_CAMERAS_AND_VISION.md#v3-jetson-docker)).
- Mind the GPU memory: the voice model takes about 80 GB; leave room for vision models.
- Keep our code in this repo and mount it into a container (`-v $PWD:/work`), like the vendor compose files do.

Measured on our Thor (`lumi-thor`, JetPack R38.4, CUDA 13.0, driver 580):

- 14 CPU cores (aarch64), 122 GB memory shared by CPU and GPU.
- On the GPU: Ollama (`gemma4:e4b` 8B Q4 at ~50 tokens/s, ~4 GB; `qwen3-vl:8b` takes 44 GB at its default 262k
  context), whisper.cpp (built with CUDA), the bge-m3 embedding server, and the camera service's YOLO.
- `onnxruntime-gpu` 1.31 (pip) installs and lists the CUDA provider, but its kernels do not run on this GPU
  ("no kernel image is available for execution on the device"). TensorRT 11.4 from pip (`tensorrt-cu13`, with
  `cuda-python`) works: YOLOv8n 4 ms, YOLOv8s 2.5–4 ms per 640 frame, against ~45 ms for YOLOv8n on the CPU with OpenCV
  DNN. TensorRT 11 has no FP16 builder flag (networks are strongly typed). An engine only runs with the TensorRT
  version and GPU it was built with.
- The camera service used ~8.4 cores with YOLO on the CPU, ~1 core with it on the GPU.

## Local files and models (not in git)

| Path | What | How it is made |
|---|---|---|
| `logs/` | all log files and debug pictures | written at run time |
| `data/camera_extrinsics*.json`, `data/calib_samples*/`, `data/doa_*`, `data/volume.txt`, `data/speech_speed.txt` | calibrations and settings of this robot | `vision/calib.py`, `audio/doa.py`, the dashboard |
| `.venv/` | Python 3.12 venv with `site-packages/lumi_wave.pth` (the path of this folder): numpy, opencv-python-headless, pyorbbecsdk2, fastapi, uvicorn, supertonic, soundfile, tensorrt-cu13, cuda-python | |
| `models/yolov8s.onnx`, `models/yolov8s.engine` | GPU detector. The engine only runs on the TensorRT version and GPU it was built with: rebuild after a JetPack or TensorRT change | `YOLO("yolov8s.pt").export(format="onnx", imgsz=640, opset=17)`; `vision/yolo_engine.py models/yolov8s.onnx models/yolov8s.engine` (~100 s) |
| `models/yolov8n.onnx` | CPU fallback detector | `YOLO("yolov8n.pt").export(format="onnx", imgsz=640, opset=12, simplify=True)` |
| `models/yolo11s-pose.onnx`, `.engine` | pose keypoints for `vision/pose.py` | ultralytics export, then `vision/yolo_engine.py` |
| `models/face_detection_yunet_2023mar.onnx`, `models/face_recognition_sface_2021dec.onnx` | face detector and embedding for `vision/reid.py` (without them only clothes are used) | github.com/opencv/opencv_zoo |
| `models/ggml-large-v3-turbo.bin` | whisper model (f16; `ggml-large-v3-turbo-q5_0.bin` is still used by `audio/sing_mine.py`) | Hugging Face `ggerganov/whisper.cpp` |
| `models/supertonic3/` | TTS model | Hugging Face `Supertone/supertonic-3` |
| `models/supertonic3_vector_estimator.engine`, `models/supertonic3_vocoder.engine` | the TTS's two slow parts on the GPU (`audio/tts_gpu.py`; without them the CPU, 5–10x slower). Bound to this TensorRT and GPU: rebuild after a JetPack or TensorRT change | `.venv/bin/python audio/tts_gpu.py build` (~3 min), then `check` |
| `whisper.cpp/` | v1.9.5, built with CUDA | `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=110 -DCMAKE_BUILD_TYPE=Release && cmake --build build -j 12 --target whisper-server whisper-cli` |
| `~/models/bge-m3-Q8_0.gguf` | embedding model for the knowledge base | Hugging Face |
| `knowledge/index.npz` | knowledge vectors | `assistant/knowledge.py build` |
| Ollama `gemma4:26b` | LLM | `ollama pull gemma4:26b` |
| `docs/private/` | company-internal notes (access, vendor manuals, screenshots) | kept off git |

The Orbbec cameras need the udev rule `SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"` in `/etc/udev/rules.d/99-orbbec.rules`.

---


## Operational pitfalls

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

Every value meant to be tuned by hand, with its file: [TUNING.md](TUNING.md).
