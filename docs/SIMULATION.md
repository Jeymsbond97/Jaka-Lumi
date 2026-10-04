# JAKA Lumi: MuJoCo simulation reference

What the simulation contains, how it is built, which numbers come from the real robot and which are guesses, and what still differs from the hardware. The real robot is described in the other documents in this folder, starting with [00_START_HERE.md](00_START_HERE.md).

State as of 2026-10-04 (commit `4b0dd23`).

---

## 1. Purpose

- Develop and test control code (body, arm, base, cameras, gestures, later LLM + vision) without the hardware.
- Keep the same method names and units as the real interfaces, so a `LumiReal` class with the same methods can replace `LumiSim` and the code above it does not change.

```
LLM / vision / scripts ──> LumiAPI methods ──┬─> LumiSim   (MuJoCo, this repo)
                                             └─> LumiReal  (body HTTP + jkrc + AGV TCP + Orbbec), to be written
```

---

## 2. Running it

Python environment: the existing venv at `/Users/tokhirbek/Documents/PROJECTS/RobotSimulation/venv` (MuJoCo 3.14). The system `python3` has no MuJoCo. Requirements: `mujoco>=3.14`, `numpy>=2.0`, `opencv-python>=4.10`.

```bash
source /Users/tokhirbek/Documents/PROJECTS/RobotSimulation/venv/bin/activate
python demo.py               # headless: prints the checks, writes pictures to media/
mjpython demo.py --viewer    # window; on macOS the viewer needs mjpython
```

Interactive use:

```bash
mjpython
>>> from lumi_api import LumiSim
>>> robot = LumiSim(viewer=True)
>>> robot.body_moveto([100, 30, 0, 20])
```

`python lumi_api.py` on its own does nothing: it is a library. `scene.xml` can also be dropped onto the MuJoCo app to move every actuator with sliders.

---

## 3. Files

| File | Contents |
|---|---|
| `lumi.xml` | Robot model: bodies, joints, actuators, collision shapes, cameras, gripper attachment |
| `scene.xml` | Includes `lumi.xml`; floor, lights, table, two cubes, a can, a movable mannequin |
| `lumi_api.py` | `LumiSim` class |
| `demo.py` | Headless check of body, pick and place, base, waving |
| `lumi_description/` | Official URDF `jaka_lumi.urdf` and STL meshes (JAKA_Lumi repo, Apache-2.0) |
| `robotiq_2f85/` | Robotiq 2F-85 gripper model (MuJoCo Menagerie) |
| `assets/`, `tools/make_decals.py` | "JAKA" arm labels (texture and curved meshes); rebuild with `python3 tools/make_decals.py` (needs Pillow) |
| `media/` | Pictures written by `demo.py` |
| `PLAN.md` | Plan and daily log (Uzbek) |

---

## 4. Model (`lumi.xml`)

### Global settings

- `compiler angle="radian" autolimits="true"`, meshes from `lumi_description/meshes`.
- `option timestep="0.002" integrator="implicitfast" cone="elliptic" impratio="10"`.
- Kinematics and masses come from the URDF. Motors, collision shapes, cameras and the gripper were added by hand.
- `gravcomp="1"` on the column, head and arm bodies (the real controllers hold their own weight).
- The robot's front is the **−y** side of `base_link`. The root body is turned 90°, so in the world the robot faces **+x**.

### Kinematic tree

```
root (freejoint)
└── base_link
    ├── wheel_r (w_r), wheel_l (w_l)          drive wheels, axis z of the wheel frame
    ├── 4 caster spheres                      frictionless, in place of the casters
    └── link_1 (l_1, slide)                   lift, pos (0, 0, 0.565)
        └── link_2 (l_2, hinge)               waist, pos (0, 0, 0.0745)
            ├── torso_cam                     camera under the handle
            ├── link_3 (l_3, hinge)           head yaw, pos (0, 0, 0.3465)
            │   └── link_4 (l_4, hinge)       head pitch, pos (0, 0, 0.052)
            │       └── head_cam
            └── link_a1 (l_a1) ... link_a6 (l_a6)   arm, link_a1 at (−0.104, 0, 0.069)
                └── flange site → Robotiq 2F-85 (attach, prefix g_), g_pinch site between the fingers
```

### Joints and actuators

| Joint | Type | Range in model | Actuator | Type | Gain | Force limit |
|---|---|---|---|---|---|---|
| `w_l`, `w_r` | hinge | free | `wheel_l`, `wheel_r` | velocity, ctrl −12…12 rad/s (≈ ±1 m/s) | kv 200 | ±60 |
| `l_1` lift | slide | 0–0.3 m | `lift` | position | kp 40000, dampratio 1 | ±2000 N |
| `l_2` waist | hinge | ±2.4435 rad (±140°) | `waist` | position | kp 2000 | ±200 Nm |
| `l_3` head yaw | hinge | ±3.1415 rad | `head_yaw` | position | kp 100 | ±20 Nm |
| `l_4` head pitch | hinge | −0.0872…0.6108 rad (−5…35°) | `head_pitch` | position | kp 100 | ±20 Nm |
| `l_a1` | hinge | ±6.2831 rad | `a1` | position (class `arm_big`) | kp 1500 | ±60 Nm |
| `l_a2` | hinge | ±2.1816 rad | `a2` | `arm_big` | kp 1500 | ±60 Nm |
| `l_a3` | hinge | ±2.2689 rad | `a3` | `arm_big` | kp 1500 | ±60 Nm |
| `l_a4` | hinge | ±6.2831 rad | `a4` | position (class `arm_small`) | kp 400 | ±20 Nm |
| `l_a5` | hinge | ±2.0943 rad | `a5` | `arm_small` | kp 400 | ±20 Nm |
| `l_a6` | hinge | ±6.2831 rad | `a6` | `arm_small` | kp 400 | ±20 Nm |
| gripper | | | `g_fingers_actuator` | from `2f85.xml`, 0 = open, 255 = closed | | |

13 actuators plus the gripper. Joint defaults: armature 0.1, damping 1 (lift damping 200, waist 5; wheels armature 0.05, damping 0.1).

Lift and waist ranges follow the Lumi SDK doc (0–300 mm, ±140°), not the URDF (0.4 m, ±160°). Arm ranges match the Mini 2 spec (±360, 125, 130, 360, 120, 360°).

**All gains and force limits are estimates.** They are not in the URDF and must be tuned against measured motion of the real robot.

### Cameras

| Camera | Body | Position in body | fovy |
|---|---|---|---|
| `head_cam` | `link_4` | (−0.043, −0.07, 0) | 58° |
| `torso_cam` | `link_2` | (0.158, −0.019, 0.023) | 58° |

Both were placed by eye from a photo of the real robot (`Jaka_lumi.jpg`), at the centre of the black camera windows. The real values are known now (see section 8).

### Scene (`scene.xml`)

| Body | Position (world) | Notes |
|---|---|---|
| `table` | (0.7, 0, 0) | Top at 0.75 m |
| `red_cube` | (0.5, −0.15, 0.775) | 4 × 6 × 4 cm, 60 g, freejoint |
| `blue_cube` | (0.52, 0.15, 0.775) | freejoint |
| `green_can` | (0.58, 0, 0.81) | freejoint |
| `person` | (0.7, −0.85, 0), facing the robot | Mocap mannequin with eyes and nose, beside the table on the arm side |

---

## 5. `LumiSim` API (`lumi_api.py`)

Robot frame for every Cartesian method: origin on the floor under the wheel axle, **x forward, y left, z up, metres**.

| Method | Arguments and units | Real channel it stands in for |
|---|---|---|
| `LumiSim(scene=SCENE, viewer=False)` | Opens the model; arm starts at `ARM_HOME` | |
| `body_moveto(pos, vel=100)` | `[lift mm, waist deg, head yaw deg, head pitch deg]`, `vel` 0.1–100 %. Out-of-range raises `ValueError`. Blocking | Body HTTP `/api/extaxis/moveto` |
| `body_status()` | → `[lift mm, waist deg, head yaw deg, head pitch deg]` | Body HTTP `/api/extaxis/status` (`pos` fields) |
| `arm_joint_move(joints_deg, vel=100)` | Six angles in degrees. Out-of-range raises. Blocking | `jkrc.joint_move` (which takes **radians**) |
| `arm_joints()` | → six angles in degrees | `jkrc.get_joint_position` (radians) |
| `tcp_position()` | → point between the fingers, robot frame, m | `jkrc.get_tcp_position` (mm, arm base frame) |
| `solve_ik(xyz, approach=(0,0,-1), use_waist=True, restarts=40, keep=6)` | → `(waist deg, six arm deg)` | `jkrc.kine_inverse` (arm only, no waist) |
| `arm_move_to(xyz, approach, use_waist=True, vel=100)` | IK, then waist move (head counter-turns to keep looking the same way), then arm move | |
| `arm_move_line(xyz, approach, vel=40)` | Straight line in 2 cm steps, waist fixed | `jkrc.linear_move` |
| `gripper(closed)` | Robotiq open / close | Gripper (none on the real robot yet) |
| `pick(xyz, clearance=0.10)`, `place(xyz, clearance=0.10)` | Top-down grasp and release | |
| `drive(linear, angular, seconds)` | m/s, rad/s (+ = left), then stop | AGV `/api/joy_control` |
| `base_pose()` | → `(x, y, heading deg)` in the world | AGV `current_pose` (map frame, rad) |
| `get_image(camera="head_cam", width=640, height=480, depth=False)` | RGB `uint8`, or depth in **metres** | Orbbec colour / depth (depth in **mm**) |
| `wave(times=3)` | Raise arm, swing wrist (a5 ± 25°), back to home | |
| `set_person(x, y)` | Sim only: move the mannequin; far away (4, 3) = nobody | |
| `object_position(name)` | Sim only: ground-truth position in the robot frame | |
| `step(seconds)` | Sim only: advance physics, sync the viewer every 8 steps | |
| `robot_to_world(xyz)`, `world_to_robot(xyz)` | Frame conversion | |

### Constants

| Name | Value | Origin |
|---|---|---|
| `WHEEL_RADIUS` | 0.084 m | From `wheel_l.STL` |
| `WHEEL_TRACK` | 0.3586 m | From the URDF |
| `AXLE_HEIGHT` | 0.084 m | Wheel axle above the floor |
| `BODY_SPEED` | `[100 mm/s, 60 °/s, 90 °/s, 60 °/s]` at `vel=100` | **Estimate**, measure on the robot |
| `ARM_SPEED` | 90 °/s at `vel=100` | **Estimate** |
| `JOINT_MARGIN` | 15° | IK keeps every joint this far inside its limit (the real controller stops at soft limits) |
| `ARM_HOME` | `[178, -91, 77, 28, 89, 135]` deg | Ready pose on the right side, elbow up, gripper forward and down |
| `ARM_WAVE` | `[206, -95, 39, 65, 52, 136]` deg | Hand above the head; every joint within 40° of `ARM_HOME` |
| `GRIPPER_OPEN`, `GRIPPER_CLOSED` | 0, 255 | Robotiq actuator range |

`ARM_HOME` and `ARM_WAVE` are in URDF joint space. They have not been compared with SDK joint space (the vendor's factory pose is `[0, 120, -120, 0, -90, 0]` in SDK space), so do not send them to the real arm before the joint mapping is checked.

### How moves work

- `_ramp` moves actuator setpoints linearly at a constant speed (units per second), in 20 ms steps, then waits `settle` seconds (0.4 s by default). This mimics a blocking robot move.
- IK: damped least squares (λ = 1e-3, step clip 0.2 rad, up to 200 iterations) on a scratch `MjData`, so the simulation is not disturbed. Position tolerance 1 mm, approach-axis tolerance 0.01. The waist is part of the IK unless `use_waist=False`. First try from the current pose, then from random poses (seeded, so results repeat). Solutions with any upper-body part colliding with the robot or the fixed world (penetration > 2 mm) are rejected; loose objects are ignored. For a1, a4, a6 (±360°) the turn nearest the current angle is used. Up to `keep` solutions are collected and the one closest to the current pose wins.
- Rotation around the approach axis is left free.
- The arm is short and mounted on the right side, so points in front need a waist turn; top-down grasps reach about 0.6 m in front of the wheel axle.

---

## 6. Verified behaviour (`demo.py`)

| Check | Result |
|---|---|
| Lift 150 mm, head pitch 30° | 149.7 mm, 30.0° |
| Pick the red cube | Lifted to 0.869 m (table top 0.75 m) |
| Place it 12 cm to the right | 3 mm from the goal |
| Back up 0.4 m, turn left 90° | 0.40 m, 89.2° |
| Person walks up, robot waves | Runs; head camera sees the person |
| Arm motion quality (after the 2026-10-02 fix) | Smallest joint margin during the demo 28°, largest single-move joint turn 38° (was 133–166°) |

---

## 7. What is real and what is estimated

| Matches the real robot | Estimated or simplified |
|---|---|
| Link geometry, joint axes, masses (URDF) | Actuator gains and force limits |
| Arm joint ranges (Mini 2 spec) | Body and arm joint speeds |
| Body API units and argument order | Camera positions and field of view |
| Lift 0–300 mm, waist ±140°, head ranges (SDK doc) | Gravity compensation instead of real controllers |
| Wheel radius and track | Casters are frictionless spheres; collisions are boxes and cylinders |
| | Gripper (Robotiq 2F-85; the real robot has none yet) |
| | No lidar, no base camera, no microphones |

---

## 8. Updates to make from the real robot documents

Collected from the official documentation (details in [01_HARDWARE.md](01_HARDWARE.md), [04_ARM.md](04_ARM.md), [05_AGV_BASE.md](05_AGV_BASE.md), [06_CAMERAS_AND_VISION.md](06_CAMERAS_AND_VISION.md)):

| Item | Sim now | Real data | Action |
|---|---|---|---|
| Camera FoV | `fovy="58"` | Gemini 2 L colour 1280 × 720: fy ≈ 610 → vertical FoV ≈ **61°** (H ≈ 93°); spec H 94° / V 68° at 1280 × 800 | Set `fovy="61"` and render at 1280 × 720 for real-like images |
| Head camera pose | (−0.043, −0.07, 0) in `link_4` | `Camera3_Link` (−0.0552, −0.0665, −0.001), rpy (−1.5708, −1.5708, 0) in `link_4` | Move the camera; confirm the optical axis |
| Torso camera pose | (0.158, −0.019, 0.023) in `link_2` | `Camera2_Link` (0.1257, 0.011, 0.0287), rpy (0, 0, 0) in `link_2` | Move the camera; confirm the optical axis |
| Base camera | none | `Camera1_Link` (0.003, −0.191, −0.120), rpy (−0.663, 0, 3.1416) in `base_link`; FoV H 58.4° × V 45.5°, 0.35–2 m | Optional: add it |
| Lidar | none | `Radar_Link` (0, −0.126, −0.085) in `base_link`; 240°, 0.02–10 m, 30 Hz | Optional: rangefinder fan for person tracking tests |
| Base speed limits | wheels ±12 rad/s (≈ ±1 m/s) | `joy_control` ±0.5 m/s, ±1.0 rad/s; each command lasts 0.5 s | Clamp `drive()` to these limits |
| Base behaviour | `drive()` runs for `seconds` then stops | Real base needs a command at > 2 Hz | `LumiReal.drive()` must resend every ~0.1 s |
| Body move | `body_moveto(pos, vel)` | Real API also has `acc` (1–100) | Add an optional `acc` argument |
| Body status | positions only | Real `/status` has `pos`, `vel`, `toq`, `enable`, `error`, `ecode` per joint | Return more fields if needed |
| Body speeds | `BODY_SPEED` guess | Not documented | Measure |
| Arm units | degrees | SDK uses radians and mm | `LumiReal` converts |
| Arm joint mapping | URDF joint space | Vendor ROS arm server sends URDF angles to `servo_j` unchanged; a real Cobo π joint/TCP pair matches our FK reach within 1 mm ([04_ARM.md §4](04_ARM.md#4-joint-space-urdf--sdk-high-confidence)) | Treat as identical; still jog each joint +5° once on the robot |
| Arm model | comment says MiniCobo | Cobo π reports `MiniCobo2` = JAKA Mini 2 (2 kg payload) | Fix the comment in `lumi.xml` |
| Gripper | Robotiq 2F-85 (~0.9 kg) | None installed; JAKA's Lumi kit uses a DH-PGEA-50 ([10_GRIPPER.md](10_GRIPPER.md)) | Keep for sim tests; replace when a gripper is chosen |
| Camera intrinsics | ideal pinhole | Vendor calibrations: torso fx/fy ≈ 610, cx 639, cy 366; head fx/fy ≈ 610, cx 639, cy 389 (1280 × 720) ([06](06_CAMERAS_AND_VISION.md#3-intrinsics-and-extrinsics)) | Optional: render at 1280 × 720 with fovy 61° |
| People | mocap mannequin | AGV `human_detection` gives person positions (x forward, y left) | A sim version of `human_positions()` can read the mannequin pose |
| Sound direction | none | 6-mic array, 360°, ±15° | A sim version can return the mannequin's bearing plus ±15° noise |

---

## 9. Plan to swap in the real robot

1. Write `lumi_real.py` with a `LumiReal` class that has the same methods as `LumiSim`:
   - `body_moveto`, `body_status` → HTTP `/api/extaxis/...` (same units; add enable and reset at start).
   - `arm_joint_move`, `arm_joints`, `tcp_position`, `arm_move_line` → `jkrc` (degrees ↔ radians, metres ↔ mm, robot frame ↔ arm base frame, after the joint mapping is verified).
   - `drive`, `base_pose` → AGV `joy_control` at 10 Hz, `robot_status`.
   - `get_image` → Orbbec (depth mm → m).
   - IK: keep our MuJoCo IK for the waist + arm choice and check the result with `jkrc.kine_forward`, or use `jkrc.kine_inverse` for the arm only.
2. Simulation-only methods (`set_person`, `object_position`, `step`) are not part of `LumiReal`.
3. Add methods both backends implement for the new behaviours: `human_positions()`, `sound_direction()`, `head_look_at(bearing_deg)`.
4. Test each method on the real robot at low speed against the sim.

---

## 10. Learning material

- Whole project guide (Uzbek): https://claude.ai/artifact/2FQCeYgSrXRYYWwNWhCPmX
- `scene.xml` line by line (Uzbek): https://claude.ai/artifact/7QaR4iTLaGR7TVwWb5Lgdx
