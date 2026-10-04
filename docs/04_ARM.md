# 04. Arm: JAKA Mini 2

How to control the 6-joint arm: the web/app UIs, the Python SDK (`jkrc`), units, joint space, trajectories, safety settings and the tool connector. Hardware specs are in [01_HARDWARE.md](01_HARDWARE.md#2-arm-jaka-mini-2).

---

## 1. Ways to control the arm

| Tool | Use it for | How |
|---|---|---|
| **Cobo π** (web) | Power on/off, enable, jog, check joint/TCP values, safety settings, external axes, programs | Browser → `https://192.168.10.90` → English → select robot → Administrator login ([private/ACCESS.md](private/ACCESS.md)) |
| **JAKA App 1.7.2** (Zu App) | Same, older UI; required for some settings on 1.7 controllers | https://www.jaka.com/download, join the robot Wi-Fi, connect |
| **Python SDK `jkrc`** | Our code: moves, trajectories, state | Section 3 |
| **ROS 2** (`jaka_lumi_minicobo_arm_server`) | MoveIt 2 trajectories | [09_ROS2_TELEOP_AND_SIM.md](09_ROS2_TELEOP_AND_SIM.md) |

Cobo π top bar (from `private/images/arm-02-cobopi-manual-extaxis-jog-notes.png`): Home (首页), Programming (编程), Manual (手动), I/O panel, Settings (设置), Apps (应用); "Real robot" (真机) / simulation switch; checksum; **Power** (电源) and **Enable** (使能) switches on the right; 3PE indicator. The Manual page shows the 3D model, TCP X/Y/Z (mm) and RX/RY/RZ (deg) in the chosen frame ("World frame", "flange centre"), joint dials J1…J6 with a step selector and speed %.

### Power-on order

1. Base main switch on, base power button (see [00_START_HERE.md](00_START_HERE.md)). The robot controller and the arm need about **5 minutes** to be ready after power-on (company voice-assistant notes).
2. In Cobo π or the App: **Power** on → ring light blue → **Enable** → ring light green.
3. Power off in the reverse order: disable → power off. Never cut cabinet power while the arm is powered or enabled; wait 5–10 s after the cabinet shuts down before cutting power.

---

## 2. Controller versions: 1.7 vs 3.2

The JAKA web doc (3.3.5.3, `arm-02-…`) lists differences that change how code must be written:

| | Controller 1.7 (e.g. 1.7.1-46-X64-minicab) | Controller 3.2 |
|---|---|---|
| SDK login | `login()` | `login(1)` (gRPC) |
| Tool TIO RS485 communication | supported | not yet |
| Servo mode (`servo_j`, `servo_p`) | supported | not yet |
| VR teleoperation (vendor) | supported | not supported |
| Cobo π | from 1.7.1 | yes |
| SDK v2.2.7 | needs controller ≥ 1_7_2_28 | — |

**First thing to check on our robot:** the controller version (Cobo π → About / settings, or JAKA App → About). The vendor code itself is mixed: the BMW demo calls `login(1)`, the ROS arm server calls `login_in(ip, true)` (gRPC) and then uses `servo_j`, the pick demo calls `login()`. Try `login()` first; if it fails, `login(1)`.

SDK compatibility (SDK 2.2.7 release notes): SDK 2.2.7 for controllers **1_7_2_28 and newer**; for 1_7_0_x and 1_5_x use SDK 2.1.11 or older.

---

## 3. Python SDK (`jkrc`)

### Get it

| Source | Contents |
|---|---|
| JAKA SDK v2.2.7 zip ([download](https://www.jaka.com/prod-api/common/download/resource?resource=%2Fprofile%2Fupload%2F2025%2F04%2F25%2F20250425134342A024.zip), 63 MB, contains `SDK V2.2.7.7z`) | `Linux/python3/{x86_64,aarch64,i686}-linux-gnu/{jkrc.so,libjakaAPI.so}`, Windows `jkrc.pyd`, C/C++ headers (`JAKAZuRobot.h` documents every function), release notes |
| JAKA_Lumi repo `main` | `JAKA_Lumi_Demo_Case/compose/JAKA_SDK_LINUX_X86`, `JAKA_SDK_LINUX_ARM`, `JAKA_SDK_WINDOWS` |
| jaka-robot-demos `dev/jamie` | `LUMI_DEMO-v1/JAKA_SDK_LINUX/jkrc.pyi` (type stubs with Python signatures) |
| JAKA_Lumi `LumiCode` | `Lumi_Training/JAKASDK/JAKA PythonSDK.pdf` (Python SDK manual v2.1.9, Chinese, 74 pages) |

**No macOS build.** On an Apple Silicon Mac run it in an arm64 Linux container and use the `aarch64-linux-gnu` files:

```bash
# on the Mac (Docker Desktop), from this repo
docker run -it --rm --network host -v "$PWD":/work -w /work arm64v8/python:3.10 bash
# inside the container
export LD_LIBRARY_PATH=/work/jaka_sdk/aarch64:$LD_LIBRARY_PATH   # folder with jkrc.so + libjakaAPI.so
python3 -c "import sys; sys.path.insert(0,'/work/jaka_sdk/aarch64'); import jkrc; print(jkrc)"
```

(Docker Desktop's `--network host` needs Docker Desktop 4.34+ with host networking enabled; otherwise the container still reaches `192.168.10.90` through NAT, which is enough for the SDK client.) On the Jetson (aarch64 Ubuntu) and on Linux PCs it runs natively.

On Linux:

```bash
export LD_LIBRARY_PATH=/path/to/JAKA_SDK_LINUX:$LD_LIBRARY_PATH
python3 -c "import jkrc"
```

### Return values and units

Every call returns a tuple; `ret[0] == 0` is success, data is in `ret[1]`.

| Quantity | Unit |
|---|---|
| Joint angles | **rad** |
| Joint speed / acceleration | rad/s, rad/s² |
| Cartesian position | **mm** |
| Cartesian orientation | rad (RX, RY, RZ). Cobo π displays degrees |
| Linear speed / acceleration | mm/s, mm/s² |
| Payload | kg, centroid mm |
| Servo period | `step_num × 8 ms` |

`move_mode`: `0` ABS, `1` INCR, `2` CONTINUE. `coord_type`: `0` base/user, `1` joint, `2` tool.

### Signatures (from `jkrc.pyi` and the Python manual)

```python
robot = jkrc.RC("192.168.10.90")
robot.login()                       # 1.7 controller; on 3.2 use robot.login(1)  (stub name: log_in(use_grpc=0))
robot.logout()
robot.power_on(); robot.power_off(); robot.shut_down()
robot.enable_robot(); robot.disable_robot()

robot.joint_move(joint_pos, move_mode, is_block, speed)                       # rad, rad/s
robot.joint_move_extend(joint_pos, move_mode, is_block, speed, acc, tol)
robot.linear_move(end_pos, move_mode, is_block, speed)                        # [x,y,z mm, rx,ry,rz rad], mm/s
robot.linear_move_extend(end_pos, move_mode, is_block, speed, acc, tol)
robot.linear_move_extend_ori(end_pos, move_mode, is_block, speed, acc, tol, ori_vel=pi, ori_acc=4*pi)
robot.circular_move(end_pos, mid_pos, move_mode, is_block, speed, acc, tol)
robot.jog(aj_num, move_mode, coord_type, jog_vel, pos_cmd=0); robot.jog_stop(jnum)
robot.motion_abort()

robot.servo_move_enable(True/False); robot.is_in_servomove()
robot.servo_j(joint_pos, move_mode, step_num)                                 # period = step_num * 8 ms
robot.servo_p(end_pos, move_mode, step_num)
robot.servo_move_use_none_filter()
robot.servo_move_use_joint_LPF(cutoff_hz)
robot.servo_move_use_joint_NLF(max_vr, max_ar, max_jr)
robot.servo_move_use_carte_NLF(max_vp, max_ap, max_jp, max_vr, max_ar, max_jr)
robot.edg_init(en, edg_stat_ip); robot.edg_servo_j(...); robot.edg_servo_p(...)

robot.get_joint_position()          # (0, (j1..j6)) rad, commanded
robot.get_actual_joint_position()
robot.get_tcp_position()            # (0, (x,y,z mm, rx,ry,rz rad))
robot.get_actual_tcp_position()
robot.get_robot_status()            # (0, list) see below
robot.kine_forward(joint_pos); robot.kine_inverse(ref_joint_pos, cartesian_pose)

robot.get_digital_input(type, index); robot.set_digital_output(type, index, value)
robot.get_analog_input(type, index);  robot.set_analog_output(type, index, value)
robot.get_tool_id(); robot.set_tool_id(id); robot.set_tool_data(id, tcp, name)
robot.set_payload(...); robot.set_collision_level(level); robot.collision_recover(); robot.clear_error()
robot.drag_mode_enable(bool); robot.is_in_drag_mode()
robot.program_load(name); robot.program_run(); robot.program_pause(); robot.program_resume(); robot.program_abort()
robot.get_sdk_version(); robot.get_last_error(); robot.set_error_handler(func)
```

### `get_robot_status()` list (Python manual 4.4.1)

| Index | Field | Index | Field |
|---|---|---|---|
| 0 | errcode (0 = OK) | 13 | ain (cabinet analog in) |
| 1 | inpos (motion reached) | 14 | tio_dout |
| 2 | powered_on | 15 | tio_din |
| 3 | enabled | 16 | tio_ain |
| 4 | rapidrate | 17 | extio |
| 5 | protective_stop (collision) | **18** | **cart_position** (TCP pose) |
| 6 | drag_status | **19** | **joint_position** |
| 7 | on_soft_limit | 20 | robot_monitor_data (temperatures, voltages, currents per joint) |
| 8 | current_user_id | 21 | torq_sensor_monitor_data |
| 9 | current_tool_id | 22 | is_socket_connect |
| 10 | dout (cabinet) | 23 | emergency_stop |
| 11 | din (cabinet) | 24 | tio_key (`[0]` FREE, `[1]` POINT, `[2]` light button) |
| 12 | aout (cabinet) | | |

Status data refreshes every 4 ms by default.

### Minimal session

```python
import math, jkrc

robot = jkrc.RC("192.168.10.90")
ret = robot.login()
if ret[0] != 0:
    ret = robot.login(1)                     # controller 3.2
assert ret[0] == 0, ret
robot.power_on()                             # ~8 s
robot.enable_robot()                         # ~4 s
robot.set_collision_level(1)                 # 25 N, most sensitive
robot.set_network_exception_handle(100, 2)   # abort motion if the SDK link drops for 100 ms

print("joints (deg):", [round(math.degrees(a), 2) for a in robot.get_joint_position()[1]])
print("tcp:", robot.get_tcp_position()[1])

# one joint, +5 degrees, slowly, relative move
robot.joint_move([0, 0, 0, 0, 0, math.radians(5)], 1, True, 0.2)

robot.disable_robot()
robot.power_off()
robot.logout()
```

Vendor speed habits: `joint_move(..., speed=vel/180*3.14)` with `vel=90` (deg/s) in the pick demo; ROS uses 1.0 rad/s for the teleop home. One vendor wrapper (`jaka_integrated.py rob_moveto`) passes "45" straight into a rad/s argument; do not copy that. Start at 0.2–0.5 rad/s.

---

## 4. Joint space: URDF = SDK (high confidence)

1. The vendor's ROS arm server (`feat_ros/jaka_lumi_minicobo_arm_server`) takes MoveIt trajectories for `l_a1…l_a6` from the URDF and sends the positions to `servo_j` **unchanged**; it publishes `get_joint_position()` as `l_a1…l_a6` unchanged. So the vendor treats URDF joint angles and SDK joint angles as the same numbers.
2. Check with real data: Cobo π on a real Lumi showed joints `[165.559, -35.513, -81.900, -13.096, -30.818, -58.021]°` with the flange at `(121.985, -126.405, 377.039) mm` (`private/images/arm-02-…`). Forward kinematics of the official URDF (`jaka_lumi.urdf`, identical in JAKA_Lumi `feat_ros`) with these angles puts the flange **415.1 mm** from the arm base; the real distance is **416.0 mm**. The angle between the TCP vector and the flange axis agrees within about 4° (Cobo π's "World" frame includes the mounting angle, so the xyz components themselves are not comparable).
3. Still do the +5° per joint test (section 9) before sending URDF-computed angles (e.g. from MoveIt or our own IK) to the robot.

Known poses (degrees, SDK = URDF joint space):

| Pose | J1…J6 | Source |
|---|---|---|
| Factory initial position ("手臂出厂初始位置") | `[0, 120, -120, 0, -90, 0]` | BMW demo |
| Pick demo home / pick / place | `[0, 110, -100, 0, -80, -50]`, `[0, 110, -100, 0, 0, -50]`, `[0, 110, -100, 0, -10, -50]` | JAKA_Lumi `feat_demo/body_head/2_moveto.py` |
| Teleop "E demo vertical" default | `[18.24, -80.54, -49.54, -16.99, -78.43, 0]` (rad `[0.3183, -1.4058, -0.8646, -0.2966, -1.3689, 0]`) | LumiCode `teleoperation_control_lumi.py` |
| Vision demo start pose | rad `[1.780, -0.532, -1.075, -0.554, -1.192, 1.244]` | LUMI_DEMO-v1 config |
| Seen in Cobo π | `[165.559, -35.513, -81.900, -13.096, -30.818, -58.021]` | Notion screenshot |
| MoveIt SRDF `pose_1` | `[0, 0, -90, 0, -90, 0]` | `jaka_lumi.srdf` |

---

## 5. Trajectories

| Method | When | Notes |
|---|---|---|
| `joint_move` (blocking) | Point-to-point, safest | Controller plans the profile. `set_motion_planner(0)` T-curve (speed first) or `1` S-curve (smooth first) |
| `linear_move` | Straight TCP line (approach/retreat) | Avoid near wrist singularities; prefer joint moves when orientation changes a lot |
| `circular_move` | Arcs | |
| `servo_j` streaming | Our own trajectories (sampled at 8 ms × n), tracking, MoveIt | Needs servo mode (controller 1.7; **3.2 not yet**). Send the next point immediately; set a filter first |
| ROS 2 `FollowJointTrajectory` | Plan in MoveIt, execute on the robot | Arm server: servo_j with `step_num = dt / 0.008`, filter `servo_move_use_joint_LPF(0.5)` |

Servo-mode recipe (as in the vendor ROS server and teleop):

```python
robot.servo_move_enable(False)
robot.servo_move_use_joint_LPF(0.5)          # or servo_move_use_joint_NLF(60, 60, 60) as in teleop
robot.servo_move_enable(True)
for q in trajectory_rad:                     # one point every 8 ms * step_num
    robot.servo_j(q, 0, 1)                   # absolute, 8 ms
robot.servo_move_enable(False)
```

Teleop also uses Cartesian servo: `servo_move_use_carte_NLF(500, 250, 250, 500, 250, 250)` and `servo_p(pose, 0, step_num)`.

---

## 6. Function reference (C++ header, SDK 2.2.7)

Names are the same in Python.

| Group | Functions |
|---|---|
| Connection, power | `login_in`/`login`, `login_out`/`logout`, `power_on`, `power_off`, `shut_down`, `enable_robot`, `disable_robot`, `get_sdk_version`, `get_controller_ip`, `set_network_exception_handle(ms, 0 keep / 1 pause / 2 abort)`, `set_debug_mode`, `set_SDK_filepath`, `set_errorcode_file_path`, `get_last_error` |
| State | `get_robot_status`, `get_robot_status_simple` (errcode, errmsg, powered_on, enabled), `get_robot_state` (estoped, poweredOn, servoEnabled), `get_joint_position`, `get_actual_joint_position`, `get_tcp_position`, `get_actual_tcp_position`, `get_motion_status`, `is_in_pos`, `is_in_estop`, `is_on_limit`, `is_in_collision`, `get_dh_param`, `get_installation_angle`, `set_installation_angle(x, z)` |
| Motion | `joint_move(pos, mode, block, speed, acc=3.5, tol=0)`, `linear_move(pos, mode, block, speed, accel=500, tol=0, ori_vel=3.14, ori_acc=12.56)`, `circular_move`, `jog`, `jog_stop`, `motion_abort`, `set_rapidrate(0..1)`, `set_motion_planner(-1/0/1)`, `kine_forward`, `kine_inverse` (nearest to the reference joints, error −4 if none), rotation conversions |
| Servo | `servo_move_enable`, `is_in_servomove`, `servo_j`, `servo_p`, filters (`none`, `joint_LPF`, `joint_NLF`, `carte_NLF`, `joint_MMF`, `speed_foresight`), EDG (`edg_init`, `edg_servo_j`, `edg_servo_p`, `edg_get_stat`) |
| Frames, tool, payload | `set_tool_data`, `set_tool_id`, `get_tool_data`, `get_tool_id`, `set_user_frame_data`, `set_user_frame_id`, `set_payload(mass kg, centroid mm)`, `get_payload` |
| Safety, drag | `set_collision_level` (0 off, 1 25 N, 2 50 N, 3 75 N, 4 100 N, 5 125 N), `collision_recover`, `clear_error`, `drag_mode_enable`, `is_in_drag_mode`, `set_motion_limit_warning_range` |
| I/O | `set_digital_output(type, index, value)`, `get_digital_input`, analog in/out, multi-channel variants; types `0` cabinet, `1` tool, `2` extend, `3` relay, `4` Modbus slave, `5` PROFINET, `6` EtherNet/IP |
| Tool RS485 (grippers) | `set_tio_vout_param(enable, 0=24V/1=12V)`, `set_tio_pin_mode`, `set_rs485_chn_comm`, `set_rs485_chn_mode`, `send_tio_rs_command`, `add_tio_rs_signal`, `get_rs485_signal_info` |
| Other | trajectory recording, controller programs, user variables, FTP, force-torque sensor and force control |

### Error codes

| Code | Meaning | Code | Meaning |
|---|---|---|---|
| 0 | success | −16 | FK error |
| 2 | call error / not supported by controller | −20 | protective stop |
| −1 | invalid handle (not logged in) | −21 | emergency stop |
| −3 | connection failed | −22 | on soft limit |
| −4 | no IK solution | −40 / −41 / −42 | linear / joint / arc move error |
| −5 | E-stop pressed | −50 | blocking wait timeout |
| −6 | not powered | −51…−56 | power on/off, enable/disable, user frame, tool timeouts |
| −7 | not enabled | −57 / −58 | EDG init failed / EDG running |
| −8 | not in servo mode | −60 / −61 | IO / operation timeout |
| −9 | must disable first | −9997 / −9998 / −9999 | not implemented / deprecated / obsolete |
| −10 | program running | | |
| −12 | motion abnormal | | |

Full list: https://www.jaka.com/docs/en/guide/errinfo.html

---

## 7. Settings in Cobo π / JAKA App that matter

- **Mounting** (Settings → Operation → Mounting): the arm is mounted on the side of the column. Check the 3D model in the UI matches the real arm before moving. The "World" frame shown in the UI includes this mounting angle.
- **Payload** (Settings → Operation → Payload): mass and centre of mass of whatever is on the flange. Wrong values cause false collisions or drift in drag mode.
- **TCP** (Settings → Operation → TCP, 15 slots): default tool = flange centre (+Z out of the flange, −Y toward the TIO connector).
- **Collision**: force / momentum / TCP speed / power limits; rebound 0–3°. While a program runs, ~1° joint deviation stops the robot, ~3.6° stops and disables it.
- **Joint limits** (Safety → Joint Limit): soft limits and speed limit per joint, within the factory range.
- **Safety zones are NOT active in SDK control mode** (only while a UI program runs). Our code must check its own workspace.
- **Real / Simulation** switch: hardware-in-the-loop simulation on the real controller (arm must be off and disabled to switch). Useful for dry runs.
- **Freedrive limit**: TCP speed in drag mode 50–1500 mm/s.
- **Initial orientation**: user-defined safe pose (Home button).
- **Brake voltage**: required with an external power supply (MiniCab).
- Monitoring page: per-joint current, voltage, temperature, torque as % of alarm thresholds.

---

## 8. Tool I/O connector (M8, 8-pin, TIO V3)

| Pin | Signal | Wire | Notes |
|---|---|---|---|
| 1 | +24 V | red | 24 V / 12 V selectable or off; 1 A continuous, 2 A peak |
| 2 | DI1 | blue | NPN / PNP |
| 3 | DI2 | green | NPN / PNP |
| 4 | DO1 / RS485-1 A+ | yellow | NPN / PNP / push-pull, ≤ 1 A |
| 5 | DO2 / RS485-1 B− | pink | NPN / PNP / push-pull, ≤ 1 A |
| 6 | AIN1 / RS485-2 A+ | brown | 0–10 V (reads 0–4096; idle ≈ 400–800) |
| 7 | AIN2 / RS485-2 B− | white | 0–10 V |
| 8 | GND | gray | |

RS485 channel 1 (on the DO pins, high speed): Modbus RTU grippers, JAKA torque sensor; baud up to 230400, 8/9 data bits, 1/2 stop bits, odd/even/none parity. Channel 2 (on the AI pins): low speed. Gripper wiring and commands: [10_GRIPPER.md](10_GRIPPER.md).

---

## 9. First-session arm tests

1. Cobo π: note controller version, arm model, joint limits and joint speed limits, mounting, payload.
2. SDK: `login` (or `login(1)`), `get_sdk_version`, `get_robot_status_simple`, `get_joint_position`, `get_dh_param` (compare with the URDF).
3. Collision level 1, payload = no tool.
4. For each joint: `joint_move` INCR +5° at 0.2 rad/s, read `get_joint_position`, check that the joint turned in the positive direction of its URDF axis (and as Cobo π's 3D view shows); move back −5°.
5. Go to the factory pose `[0, 120, -120, 0, -90, 0]°` slowly; compare the arm shape with Cobo π's 3D view and with the URDF at the same angles (e.g. in RViz: `ros2 launch jaka_lumi_description lumi_description.launch.py`).
6. Only then run your own poses and short trajectories; servo mode only if the controller supports it.
