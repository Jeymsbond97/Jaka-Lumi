# 01 Hardware facts for sorting

Every number the simulation or the policy depends on, with where it comes from. "M" is this repository, "T" is
`~/Dev/lumi-wave` on the Thor. Anything marked **to measure** is not known yet; until it is measured, the code uses a guess and says so.

---

## 1. Arm

| Item | Value | Source |
|---|---|---|
| Model | JAKA Mini 2 ("MiniCobo2" in Cobo π), 6 DOF | M docs/01_HARDWARE.md:49-56 |
| Payload, reach, mass | 2 kg, 580 mm, 9.9 kg | 01_HARDWARE.md:49-56 |
| Repeatability | ±0.1 mm | 01_HARDWARE.md |
| Joint limits | J1, J4, J6 ±360°; J2 ±125°; J3 ±130°; J5 ±120°. Code keeps 5° margin | 01_HARDWARE.md:68-75; T robot/motion.py:26-27 |
| Joint speed used as the cap | 60 °/s ("Cobo π joint speed limit"); not a vendor spec | T robot/motion.py:56 |
| Speeds in use | joint 20 / 50 / 60 °/s; linear 40 / 100 mm/s; acceleration 1.5× (joint), 3.0× (linear) | T robot/motion.py:28-32 |
| `speed_percent` | 10–150 %, capped at 60 °/s and 150 mm/s (`data/arm_speed.json`) | T robot/motion.py:53-92 |
| Real speed on long moves | slower than commanded: J1 60° at 25–40 °/s takes 7–8 s; long moves 4.3–7 °/s | 04_ARM.md:330; TUNING.md:23 |
| Command path | JSON over TCP `192.168.10.90:10001`, one connection per command, no SDK | T robot/arm.py:12, 41-53 |
| Commands used | `joint_move` (absolute), `moveL`; one at a time, each waits until settled (queued moves shake) | T robot/motion.py:261, 311; 04_ARM.md:328 |
| Connection drops | the controller closes every connection for ~0.5 s every few seconds; retries 5× from 0.2 s doubling (~3 s) | T robot/arm.py:13-22; TUNING.md:34 |
| Other port quirks | replies sometimes belong to another command; `stop_program` may close without reply; no `motion_abort` | 04_ARM.md:319-326 |
| Kinematics | fitted offline, match the controller within 0.2 mm / 0.05° (`data/arm_kinematics.json`) | T robot/kinematics.py:6-7 |
| Servo mode | `servo_j` / `servo_p`, period = step_num × 8 ms; filters none / joint LPF / joint NLF / Cartesian NLF / MMF. Documented as supported on controller 1.7, **not yet on 3.2**. Not used by any code. `jkrc` on the Thor is x86-only | 04_ARM.md:35, 86, 109-114, 211-238; 08_NVIDIA_THOR.md:92 |
| **To measure** | controller version; whether servo mode is accepted over the JSON port; command-to-motion latency; tracking lag at 5–20 Hz targets; how a short `moveL` (10–30 mm) behaves when sent every 0.2–0.5 s | on the robot |

### Mount and frames

| Item | Value | Source |
|---|---|---|
| Mount | on the side of the column, on the waist link, mounting orientation Y 90° | 04_ARM.md:268; 01_HARDWARE.md:61 |
| URDF chain | lift link z 0.565 m in `base_link`, waist +0.0745 m, arm base `link_a1` at (−0.104, 0, 0.069) m on `link_2` | SIMULATION.md:80-86 |
| Lift / waist | lift 0–400 mm hardware, held to 0–105 mm in software; waist ±160° hardware, ±140° API | 01_HARDWARE.md:34-35; ROADMAP.md |
| Table top in arm base frame | −403 mm at lift 75 mm for the proven picks; usable band −560 … −30 mm | T tasks/fetch.py:97-98 |
| Proven zones | pick centre (−100, 580) mm; place x −240…−100, y 560…630 mm; comfort radius 710 mm | T tasks/fetch.py:63; manipulation/skills.py:96-97, 188 |
| Frames | arm base (mm, flange RPY deg, R = Rz·Ry·Rx); robot base (m): arm yaw −95.5°, arm at (0.074, −0.085) m; map (m, rad) | 04_ARM.md:319; T data/fetch_calib.json; tasks/fetch.py:10 |
| Clearances | `HEAD_CLEAR_MM` 245 (lowered from 250 on 2026-11-23), `LINK_HEAD_CLEAR_MM` 220 | TUNING.md:26-30; T Thor main 20171de |

For sorting the lift, waist and base stay still during a trial: the scene is fixed in the arm base frame.

---

## 2. Gripper

| Item | Value | Source |
|---|---|---|
| Model | Zimmer GEP2013IO-05-B | 10_GRIPPER.md:11 |
| Stroke | 13 mm per jaw (26 mm change of the gap) | 10_GRIPPER.md:11 |
| Grip force | 90–360 N, switch at level 1 (~90 N) | 10_GRIPPER.md:11 |
| Mass | ~0.54 kg without fingers; 1.0 kg payload entered in Cobo π, CoM (30, 0, 80) mm (estimate) | 10_GRIPPER.md:11, 108-113 |
| Signals | DO_1 close, DO_2 open, never both on; AI_1 finger position (~140 open, ~4160 shut on nothing); DI_1 optical sensor below the gripper | 10_GRIPPER.md:41-48; T robot/gripper.py:24-31 |
| Timing | a stroke ~1 s; code waits 1.5 s | T robot/gripper.py:6-7 |
| Behaviour | a close cannot be stopped half way; no touch sensing; a held object shows only in AI_1 | T robot/gripper.py:6-12; 10_GRIPPER.md:61 |
| Fitted | `FITTED = False` today (gripper off the flange since 2026-11-10) | T robot/gripper.py:22 |
| Fingers (since 2026-11-25) | straight printed fingers with rubber pads on the steel mount blocks: inner gap 61 mm open / 35 mm closed, outer 76 / 50 mm, 7.5 mm thick; flange to arm lower edge ~170 mm, arms ~180 mm long, pads ~50 mm at the tips (photo readings ±5 mm) | docs/gripper/README.md, owner's measurements |
| Previous fingers (C-hooks) | gap open / closed: tips 100 / 73, belly 102 / 77, neck 57 / 30, shank 66 / 39 mm; hold 6–9 cm objects only | T robot/gripper.py:33; manipulation/skills.py:152 |
| **To measure** | grasp point in the flange frame (free-drive onto a ball at the pad centres, read the flange pose); finger mass; AI_1 closed on a ball and on nothing | on the robot |

The 26 mm stroke decides the ball. With these fingers the 42.5 mm foam golf ball gets 9.25 mm clearance on each
side when open (enough for the camera's ~1 cm error) and is squeezed 7.5 mm when closed.

---

## 3. Torso camera and vision

| Item | Value | Source |
|---|---|---|
| Camera | Orbbec Gemini 2 L | 01_HARDWARE.md:175 |
| In use | colour 1280×720 MJPG 15 fps, depth 640×400 Y16 15 fps; depth written for skills every 0.5 s | T vision/person.py:47-48; vision/camview.py:49 |
| Intrinsics (1280×720) | fx 608.3, fy 608.4, cx 636.9, cy 363.2 | 06_CAMERAS_AND_VISION.md:149 |
| Hand-eye | eye-to-hand, ArUco on the gripper, 28 samples, median 3.3 mm, max 7.5 mm; camera at (−257.7, 13.7, −41.4) mm in the arm base frame; `data/camera_extrinsics.json` | 15_PICK_AND_PLACE.md:223-226 |
| Mount | camera and arm share `link_2`: calibration holds at any lift and waist | 06_CAMERAS_AND_VISION.md:141 |
| Detector | YOLOv8s TensorRT, 640 input, 2.5–4 ms per frame, COCO classes incl. `sports ball`, score ≥ 0.35; output in `/dev/shm/lumi_det_torso.json` | T vision/person.py:29-35; 08_NVIDIA_THOR.md:102 |
| 3D position | depth pixels in the box within ±60 mm of the median, deprojected, moved to the arm frame; round objects get a fixed (+19, −4) mm correction | T vision/objects.py:36, 104-153 |
| Colour | HSV; S ≥ 50 and V ≥ 60 kept; under 25 % kept → white / black / grey by V; else hue histogram (red wraps), argmax. Bounds red < 8, orange < 20, yellow < 33, green < 85, blue < 130, purple < 155, pink < 170 | T vision/objects.py:62-101 |
| Steady check | 8 frames 0.2 s apart, seen in ≥ 5, within 20 mm of the median | T manipulation/skills.py:89-93 |
| Position error | target ±1 cm; widths read ~8 mm small; shiny objects jump up to 17 mm | 15_PICK_AND_PLACE.md §9, 180, 274 |
| **To measure** | detection rate of the chosen balls as `sports ball` on the plate and in the hand; colour reading for each ball colour under office light; position error on a ball at 5 plate positions (ruler); latency from a ball moving to `position_mm` changing | on the robot |

The camera cannot see a ball inside the closed fingers reliably, and the arm hides the plate while it is above it.
The policy must not depend on a fresh ball position after the grasp ([04](04_RL.md) §2).

---

## 4. Jetson Thor

| Item | Value | Source |
|---|---|---|
| Software | L4T R38.4 (JetPack 7), CUDA 13.0, driver 580.00 | `nvidia-smi`, `/etc/nv_tegra_release`, 2026-11-24 |
| Hardware | Thor GPU (Blackwell), 122 GiB unified memory (74 GiB free at the check), 14 cores, 3.2 TB free disk | `free -g`, `df -h`, 08_NVIDIA_THOR.md:26-27 |
| Python | `~/Dev/lumi-wave/.venv`, Python 3.12.3, numpy 2.5.3 | venv check |
| Inference | onnxruntime 1.30.0 (CPU provider only; the CUDA provider fails on this GPU), TensorRT 11.4 | 08_NVIDIA_THOR.md:100-101 |
| Not installed | torch, mujoco (GPU torch only in the nvcr PyTorch container) | 08_NVIDIA_THOR.md:76 |
| Shared GPU | LLM, whisper and ~80 GB of voice services run on it | 08_NVIDIA_THOR.md:86-87 |
| Isaac Lab 3.0 needs | Linux aarch64 is listed (DGX Spark named, Jetson not); Python 3.12; CUDA 13; driver ≥ 580.65.06; Isaac Sim optional (Newton physics on Warp, headless without RTX) | docs.nvidia.com/isaaclab/isaac-lab/installation, read 2026-11-24 |
| Isaac Sim | not supported on Jetson Thor (needs RT cores) | docs.isaacsim.omniverse.nvidia.com 5.1 requirements; DesignSpark Thor article |

The Thor's driver (580.00) is below the documented minimum and Jetson is not listed: training on the Thor is a
thing to try; the other place is a cloud x86 machine with an RTX GPU.

---

## 5. Safety facts

| Item | Value | Source |
|---|---|---|
| Speeds to start with | joint 0.2–0.5 rad/s, linear ≤ 50 mm/s, collision level 1 (25 N) near people | 11_SAFETY.md:31-32 |
| Safety zones | Cobo π zones do not apply to port control: the code checks every move itself | 11_SAFETY.md:33; 04_ARM.md:273 |
| Collision limits | still at loose defaults (100 % force, 5000 mm/s TCP) | 10_GRIPPER.md:119 |
| STOP | `POST /stop`, `/arm/stop`, `/tasks/stop`; skills stop through `skills.cancel()` → `motion.stop()` (JSON `stop_program`) | T api/server.py:585, 844; manipulation/skills.py:1173-1180 |
| Watchdogs | no valid controller reply for 3 s → stop (`BLIND_S`); still 2 s short of target → ended short (`STILL_S`) | T robot/motion.py:45-47 |
| People | an operator at the E-stop for every arm test; cycle ≥ 80 % slower than the fastest | 11_SAFETY.md:30, 37 |
