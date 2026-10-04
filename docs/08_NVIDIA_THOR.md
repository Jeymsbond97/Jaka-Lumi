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

SSH from a computer on the same network as the Thor: `ssh <user>@<thor-ip>`, port 22 (use `ssh -X` for GUI programs such as OrbbecViewer or RViz). When the Thor is mounted on the robot it is on the robot network (`192.168.10.x`); find its address as in [13 §5](13_TO_VERIFY_ON_ROBOT.md#5-thor-on-the-robot-network). Our addresses and login: [private/THOR_COMPANY_SETUP.md](private/THOR_COMPANY_SETUP.md) and [private/ACCESS.md](private/ACCESS.md) (local only).

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
