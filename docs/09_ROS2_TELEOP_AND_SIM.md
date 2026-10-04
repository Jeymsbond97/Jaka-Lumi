# 09. ROS 2, teleoperation, learning and simulators

Vendor software beyond the plain APIs: the ROS 2 workspace with MoveIt 2 and Isaac Sim, VR teleoperation, ACT imitation learning. Our own MuJoCo simulation is documented separately in [SIMULATION.md](SIMULATION.md).

---

## 1. ROS 2 workspace `jaka_lumi_ros` (MoveIt 2, Isaac Sim)

Source: JAKA_Lumi repo, branch **`feat_ros`**, folder `jaka_lumi_ros/` (ROS 2 **Humble**, Ubuntu 22.04).

```bash
git clone -b feat_ros https://github.com/JAKARobotics/JAKA_Lumi.git     # large repo; or sparse-checkout jaka_lumi_ros
cd JAKA_Lumi/jaka_lumi_ros
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash
```

| Package | Role |
|---|---|
| `jaka_lumi_body_node` | Topics/services for the body over HTTP (`/joint_states`, `/lumi_body/enable|move|stop|reset|read_status`), details in [03](03_BODY_LIFT_WAIST_HEAD.md#4-ros-2) |
| `jaka_lumi_body_server` | `FollowJointTrajectory` action server for the body; publishes the TF root (start it first) |
| `jaka_lumi_minicobo_arm_server` | `FollowJointTrajectory` action server for the arm via JAKA SDK (`servo_j`, 8 ms steps, joint LPF 0.5); parameter `ip` (default `192.168.10.90`); powers on and enables the arm at start; publishes `/joint_states` `l_a1…l_a6` |
| `jaka_lumi_description` | URDF, meshes, USD files, RViz config |
| `jaka_lumi_moveit_config` | MoveIt 2: groups `jaka_lumi_body` (l_1…l_4), `jaka_lumi_minicobo_arm` (l_a1…l_a6), `jaka_lumi_full_robot`; default velocity/acceleration scaling 0.1; max joint velocity 1.57 rad/s; states `zero`, `pose_1` |
| `jaka_lumi_isaacsim` | Launch Isaac Sim with the Lumi USD; topics `/isaac_joint_states`, `/isaac_joint_commands` |

Run on the real robot:

```bash
ros2 launch jaka_lumi_body_server lumi_body_server.launch.py                       # always first
ros2 launch jaka_lumi_minicobo_arm_server lumi_minicobo_arm_server.launch.py ip:=192.168.10.90
ros2 launch jaka_lumi_moveit_config demo.launch.py                                 # RViz + MoveIt 2
```

Body only: body server + `demo.launch.py`. Standalone body node: `ros2 launch jaka_lumi_body_node lumi_body_node.launch.py`.

Controllers (only one owner per joint):

```bash
ros2 control switch_controllers --activate jaka_lumi_full_robot_controller \
  --deactivate jaka_lumi_body_controller jaka_lumi_minicobo_arm_controller --strict
ros2 control switch_controllers --activate jaka_lumi_body_controller jaka_lumi_minicobo_arm_controller \
  --deactivate jaka_lumi_full_robot_controller --strict
```

Simulation modes (replace MoveIt's `launches.py` with the one in `jaka_lumi_ros`; find it with `find /opt/ros/humble/ -name launches.py`):

```bash
ros2 launch jaka_lumi_moveit_config demo.launch.py use_rviz_sim:=true          # fake controllers
ros2 launch jaka_lumi_isaacsim run_lumi_isaacsim.launch.py                      # Isaac Sim 4.5 + Lumi USD
ros2 launch jaka_lumi_moveit_config demo.launch.py use_isaac_sim:=true
```

Isaac Sim install: https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/install_workstation.html. If it segfaults: `rm -rf ~/.nvidia-omniverse/logs ~/.nvidia-omniverse/config`; test without ROS: `cd jaka_lumi_isaacsim/scripts && ./python.sh isaacsim_moveit.py`; fallback: `ros2 launch jaka_lumi_isaacsim run_isaacsim.launch.py`, then File → Open `jaka_lumi_description/urdf/jaka_lumi/jaka_lumi_moveit.usd`, Play.

Servo mode note: the arm server needs servo mode, which controller 3.2 does not support yet ([04](04_ARM.md#2-controller-versions-17-vs-32)).

---

## 2. VR teleoperation (PICO 4)

Sources: JAKA web doc 3.2.3 (`private/images/teleop-*.png`), teleop quick-start docx, JAKA_Lumi branch **`LumiCode`** (`Lumi_Teleoperation/`), Google Drive links in `03. JAKA Lumi Related Software/Teleoperation and training code.md`.

**Only controller 1.7 (1.7.1-46-X64-minicab) is supported; controller 3.2 is not.**

| Part | Form | Role |
|---|---|---|
| VR sender | Android app on the PICO 4 (Ultra) | Sends controller poses and buttons |
| VR receiver | Docker container on an Ubuntu PC (ROS 2 Humble) | Converts them into robot Cartesian targets |
| Robot controller side | same container | Cartesian servo (`servo_p`) to the arm |

Network: VR headset and PC on the same Wi-Fi (Lumi's own Wi-Fi recommended, 5 GHz for low latency); PC also reaches the robot.

### PICO setup

1. On the headset: Control Center → Settings → About → tap the software version several times → Developer options → **USB debugging** on.
2. On the PC: install PICO Developer Center (https://developer-cn.picoxr.com/resources/#pdc). PICO docs: https://developer-cn.picoxr.com/document/unity/set-up-the-development-environment/
3. USB-cable the headset to the PC, unzip `controlData_*.zip`, copy the APK to *PICO 4 Ultra → internal shared storage → Download*.
4. In the headset: File manager → Installation packages → install. It appears under Library → **Unknown sources** (apps seen: `controllers_data_250220`, `robotB612`, `imgVR_250220`; use the one with the yellow smiley icon).
5. Open it, enter: **PC IP** (`ifconfig` on the PC, e.g. `192.168.10.35`), **PC port** (doc default 8018; the Lumi launch file uses **9852**; they must match), **send period** 0.01 s (60 Hz) → **LOGIN**. Move the controllers and check the virtual hands follow; if laggy, check both are on the same Wi-Fi.

### PC setup

```bash
# Docker (or the fishros helper: wget http://fishros.com/install -O fishros && . fishros)
docker load -i jaka_images_lumi_v1.0.tar.gz          # image jaka_images:lumi_V1.0 (≈ 37 GB on disk); from a JAKA engineer
docker images -a
# plug grippers / cameras first (cameras USB 3.0, grippers USB 2.0); ls /dev/ttyUSB* ; lsusb
docker run -it --name lumi_yao --net=host --ipc=host --pid=host \
  --device=/dev/bus/usb:/dev/bus/usb --device=/dev/usb:/dev/usb \
  -v /home/$USER/data:/home/data -v /dev/shm:/dev/shm \
  -d jaka_images:lumi_V1.0
# (add --device=/dev/ttyUSB0 --device=/dev/ttyUSB1 for grippers)

docker start lumi_yao
docker exec -it lumi_yao bash
vim ~/Lumi_Teleoperation/src/vr_data_pub/launch/teleoperation_system_lumi.launch.py   # set robot_ip (and server_port)
colcon build && source ~/.bashrc
ros2 launch vr_data_pub teleoperation_system_lumi.launch.py      # terminal 1: communication + robot init (power on, enable)
ros2 run vr_data_pub teleoperation_control_lumi                  # terminal 2: control state machine
```

In the vendor launch file: `vr_data_pub` (socket server, `server_port: 9852`), `vr_data_distributer`, `k1_robot/robot_interface` (namespace `/right_arm`, `robot_ip`, `robot_running_mode`: `teleop` / `act` / `test`), `vr_robot_pose_converter_lumi_servo_p`.

### Controller buttons

| Button | Action |
|---|---|
| Either side (grip) button | Start controlling the arm (be ready: the arm follows immediately) |
| B | Pause and return to the default pose; **disabled by default** (enable and set the home in `move_to_default_pose` of `teleoperation_control_lumi.py`). Lumi default: rad `[0.3183, -1.4058, -0.8646, -0.2966, -1.3689, 0]` |
| Y | Stop control and exit; rerun `ros2 run vr_data_pub teleoperation_control_lumi` to resume |
| X | Start recording data (data collection mode) |
| A | Save the recorded episode and stop recording |

Data collection: put the camera serials into `OrbbecSDK_ROS2/orbbec_camera/launch/multi_gemini2L_synced_sn_template.launch.py`, `colcon build`, `ros2 launch orbbec_camera multi_gemini2L_synced_sn_template.launch.py`, then `ros2 run vr_data_pub collect_data_xy` (Lumi version: `aloha_data_prepare_lumi.py`).

Safety: physical E-stop within reach; move slowly at first; if the robot shakes, press the E-stop; if communication drops, check the Wi-Fi. Troubleshooting: Docker fails to start → `sudo chmod 666 /dev/ttyUSB*`.

VM setup (from the docx): two network adapters, one bridged to the wired port (robot, `10.5.5.x` in the docx), one bridged to Wi-Fi (headset); if networking fails, swap `ens33` / `ens37`.

---

## 3. Imitation learning (ACT, Mobile ALOHA)

- Code: JAKA_Lumi `LumiCode` branch `Lumi_Training/` (fork of the ACT / Mobile ALOHA repo: `imitate_episodes.py`, `policy.py`, `detr/`, `constants.py`), Google Drive link in the repo.
- Install (docx "Docker ACT"): Docker + NVIDIA Container Toolkit; image `actimages:V1.0` (environment only, mount the code) or V1.1 (code in `/ACT`); compose:

```yaml
services:
  act:
    image: actimages:V1.0
    container_name: act
    volumes: ["../ACT:/ACT", "/dev/shm:/dev/shm"]
    network_mode: host
    command: /bin/bash -c "sleep infinity"
    runtime: nvidia
    environment: [NVIDIA_VISIBLE_DEVICES=all]
```

- `docker compose -f docker-compose.act.yml up -d`, enter the container, set `DATA_DIR` and the camera names in `/ACT/constants.py` (same names as in the dataset; example cameras `front_cam`, `right_cam`, action dim 7, chunk 25), create a checkpoint folder, comment out wandb in `train.py`, run `train.py`.
- ACT tuning tips: train long (≥ 5000 epochs on real data); jerky policies improve with more training.
- `Lumi_Training/JAKASDK/` scripts are for a 7-DOF dual-arm robot (K1): useful only as examples of SDK ↔ MuJoCo transforms.

---

## 4. Simulators summary

| Simulator | Where | Status |
|---|---|---|
| RViz fake controllers | `jaka_lumi_moveit_config use_rviz_sim:=true` | vendor |
| Isaac Sim 4.5 | `jaka_lumi_isaacsim` | vendor |
| Cobo π / JAKA App simulation switch | controller hardware-in-the-loop | arm only |
| JAKASim virtual machine | "About the Development" on jaka.com, used with the App's offline connection | arm only |
