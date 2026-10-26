# 08. NVIDIA Jetson AGX Thor

Main AI computer of Lumi: runs the robot software, vision models, speech and the LLM. Address and login: `docs/private/ACCESS.md` (not in git).

---

## 1. Specifications

| Item | Value |
|---|---|
| Model | NVIDIA Jetson AGX Thor Developer Kit |
| Compute | 2070 TOPS (INT8), Blackwell GPU (1.57 GHz), 72-core Arm v9 CPU (2.6 GHz) |
| Memory | up to 128 GB unified |
| Storage | PCIe 5.0 NVMe + UFS 4.0 |
| Power | 30–120 W (configurable) |
| Current JetPack release | JetPack 7.2.1, Jetson Linux r39.2.1 |
| Ports | 2 × USB-C (power/data), USB-A, HDMI/DisplayPort, Ethernet, Debug-USB behind the lid |

JAKA's computer options table ([01_HARDWARE.md](01_HARDWARE.md)) puts large multimodal models (≥ 30B, VLA, ACT, LLM + vision) on the AGX Thor.

### This unit

| Item | Value |
|---|---|
| Hostname | `lumi-thor` |
| Software | JetPack R38.4, CUDA 13.0, driver 580, Ubuntu 24.04, Python 3.12 |
| CPU / memory | 14 cores (aarch64), 122 GB shared by CPU and GPU |
| Network | robot LAN `enP2p1s0` (192.168.10.240); internet over its own Wi-Fi `wlP1p1s0` |

---

## 2. Connect

SSH from a computer on the same network: `ssh <user>@<thor-ip>`, port 22 (`ssh -X` for GUI programs such as OrbbecViewer or RViz). On the robot network (`192.168.10.x`) the Thor's address is also listed on the router page `http://192.168.10.79` (connected devices) or found with `nmap -sn 192.168.10.0/24`. Network details: [02_NETWORK_AND_ACCESS.md](02_NETWORK_AND_ACCESS.md).

---

## 3. Install the OS (re-flash)

NVIDIA quick start: https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/quick_start.html

Requirements: a PC with 25 GB free, a USB stick ≥ 16 GB, a monitor + keyboard (or a USB-C cable for headless setup).

1. Download the installer ISO (e.g. `jetsoninstaller-r39.2.1-...-arm64.iso`) from NVIDIA Developer Downloads.
2. Write it with **Balena Etcher** (https://etcher.balena.io). Copying the file to the stick does not work.
3. Plug the stick into the Thor (USB-A or USB-C), connect the bundled USB-C power supply, press the power button (left button on the side).
4. Boot from USB: Enter (or wait); accept the **QSPI capsule update** with **Y** (do not skip); installation to NVMe takes about 10 minutes, then it reboots.
5. **Remove the USB stick** right away.
6. First-boot wizard (oem-config): keyboard, licence, network, time zone, user name and password, hostname. Headless: connect the USB-C cable to a PC, open a serial terminal, press Tab then Enter.
7. Use the bundled power supply; avoid KVM switches. Factory UEFI 38.0.0 has display issues in headless mode (NVIDIA documents a workaround); devices reinstalled with a pre-7.2 ISO may need UEFI changes.
8. Then install the JetPack components and CUDA (NVIDIA pages "JetPack SDK Setup", "CUDA Setup").

---

## 4. Docker

NVIDIA's procedure (https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_docker.html), also when `docker compose` does not work on a fresh system:

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

`/etc/docker/daemon.json` contains `"runtimes": {"nvidia": {"path": "nvidia-container-runtime", "args": []}}` and `"default-runtime": "nvidia"`.

---

## 5. Software on the Thor

- **Lumi**: the user systemd service `lumi-api` runs `api/server.py` (API and dashboard on `:8100`); the API starts the camera service, whisper, the embedding server and loads the LLM. `systemctl --user restart lumi-api` restarts it. See the top-level README.
- **On the GPU**: Ollama (`gemma4:26b`, Lumi's LLM), whisper.cpp (CUDA), the bge-m3 embedding server, the camera service's YOLO, the pose model and the Supertonic TTS engines.
- **Company voice services**: containers of the company's own voice assistant; installation and layout in `docs/private/` (not in git). They need about 80 GB of GPU memory; leave room for vision models.
- **Colleagues' projects** on this Thor are separate: `~/Dev/lumi_edu`, `lumi-vision`, `lumi_voice_app`, services on :8000, :8001, :8090, :3080.

### Vendor SDKs

- The JAKA SDK has an `aarch64-linux-gnu` build of `jkrc`; check that `jkrc.so` loads under Python 3.12, otherwise use a Python 3.10 container. The `jkrc.so` installed here is x86-only; Lumi drives the arm through the controller's JSON port (`robot/arm.py`, `robot/gripper.py`).
- Orbbec SDK: arm64 `.deb` packages and the vendor's Jetson Docker setup ([06](06_CAMERAS_AND_VISION.md#v3-jetson-docker)).
- In containers, mount the code (`-v $PWD:/work`), as the vendor compose files do.

---

## 6. GPU inference

- **TensorRT** 11.4 from pip (`tensorrt-cu13`, with `cuda-python`) runs on this GPU. TensorRT 11 has no FP16 builder flag (networks are strongly typed). An engine runs only with the TensorRT version and GPU it was built with: rebuild every engine after a JetPack or TensorRT change.
- **onnxruntime-gpu** 1.31 (pip) lists the CUDA provider, but its kernels do not run on this GPU ("no kernel image is available for execution on the device"). Use TensorRT for GPU inference.
- Detector speed: YOLOv8s engine 2.5–4 ms, YOLOv8n engine 4 ms per 640 frame; YOLOv8n on the CPU (OpenCV DNN) ~45 ms. The camera service uses ~1 CPU core with the detector on the GPU, ~8.4 cores with it on the CPU.
- OpenCV 5.0 in the venv has no `cv2.calibrateHandEye` (`vision/calib.py` has its own solver). The system Python has no OpenCV: run modules with `.venv/bin/python`.

---

## 7. Models and local files

Not in git; made on the Thor.

| Path | What | How it is made |
|---|---|---|
| `.venv/` | Python 3.12 venv; `site-packages/lumi_wave.pth` puts the project folder on the path. numpy, opencv-python-headless, pyorbbecsdk2, fastapi, uvicorn, supertonic, soundfile, tensorrt-cu13, cuda-python | top-level README |
| `models/yolov8s.onnx`, `models/yolov8s.engine` | GPU detector | `YOLO("yolov8s.pt").export(format="onnx", imgsz=640, opset=17)`; `vision/yolo_engine.py models/yolov8s.onnx models/yolov8s.engine` (~100 s) |
| `models/yolov8n.onnx` | CPU fallback detector | `YOLO("yolov8n.pt").export(format="onnx", imgsz=640, opset=12, simplify=True)` |
| `models/yolo11s-pose.onnx`, `.engine` | pose keypoints for `vision/pose.py` | ultralytics 8.4 export (imgsz 640), then `vision/yolo_engine.py` |
| `models/face_detection_yunet_2023mar.onnx`, `models/face_recognition_sface_2021dec.onnx` | face detector and embedding for `vision/reid.py` (without them only clothes are used) | github.com/opencv/opencv_zoo |
| `models/ggml-large-v3-turbo.bin` | whisper model (f16); `ggml-large-v3-turbo-q5_0.bin` is used by `audio/sing_mine.py` | Hugging Face `ggerganov/whisper.cpp` |
| `models/supertonic3/` | TTS model | Hugging Face `Supertone/supertonic-3` |
| `models/supertonic3_vector_estimator.engine`, `models/supertonic3_vocoder.engine` | TTS vector estimator and vocoder on the GPU (`audio/tts_gpu.py`); without them the CPU, 5–10× slower | `.venv/bin/python audio/tts_gpu.py build`, then `check` |
| `whisper.cpp/` | v1.9.5 with CUDA | `cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=110 -DCMAKE_BUILD_TYPE=Release && cmake --build build -j 12 --target whisper-server whisper-cli` |
| `~/models/bge-m3-Q8_0.gguf` | embedding model for the knowledge base | Hugging Face |
| `knowledge/index.npz` | knowledge vectors | `assistant/knowledge.py build` |
| Ollama `gemma4:26b` | LLM | `ollama pull gemma4:26b` |
| `data/camera_extrinsics*.json`, `data/calib_samples*/`, `data/doa_*`, `data/volume.txt`, `data/speech_speed.txt` | calibrations and settings of this robot | `vision/calib.py`, `audio/doa.py`, the dashboard |
| `logs/` | log files and debug pictures | written at run time |
| `docs/private/` | company-internal notes (access, vendor manuals, screenshots) | kept off git |

The Orbbec cameras need the udev rule `SUBSYSTEM=="usb", ATTR{idVendor}=="2bc5", MODE="0666"` in `/etc/udev/rules.d/99-orbbec.rules`.

---

## 8. Operating rules

- Only the camera service opens the cameras ([06](06_CAMERAS_AND_VISION.md#3-camera-service-visioncamviewpy)). After `vision/camview.py --stop` / `--start` the torso camera may take a few seconds to re-enumerate: wait and start again.
- After any cable work, check the camera link speed (`/sys/bus/usb/devices/*/speed` = 5000); a camera opened at USB 2 stays colour-only until the camera service is restarted.
- Do not restart the API while the base drives: check `curl -s localhost:8100/status` → `base.move_status` first.
- Never call `tasks/fetch.py` functions from a second process while the API runs: its log writes that process's empty state over `/dev/shm/lumi_task.json`.
- Tests never reach the robot (`tests/test_*.py` fake the hardware).
- After a controller power cycle the body axes are disabled; `robot/head.py` `moveto()` enables them. All tool I/O must be PNP in Cobo π.
- The body API's `/stop` does not stop a `moveto`; hold-to-move uses small steps.
- Navigation does not go into a table's margin (such a goal ends "succeeded" without moving); a reach ends with a straight checked drive. Drives run with the arm in `look`, not `carry` (the base's 3D camera sees the hand in `carry` and stalls).
- The base's planning API does not check real paths; `robot/nav.py` uses the map image. Closed glass doors need a no-go line in the base's web panel.
- `pkill -f` / `pgrep -f` also match your own shell's command line: find the PID with `ps -eo pid,args | grep "[n]ame"` and kill that.
- Headless Chrome screenshots of the dashboard: do not use `--timeout` (it freezes the page's JavaScript).
- Do not touch colleagues' projects and services (§5).

Every value meant to be tuned by hand, with its file: [TUNING.md](TUNING.md).
