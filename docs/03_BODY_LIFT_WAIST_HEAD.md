# 03. Body: lift, waist, head

The four "external axes" (lifting column, waist, head yaw, head pitch). There are three ways to drive them: the web page, the HTTP API, and the external-axis panel in Cobo π. ROS 2 nodes wrap the HTTP API.

Units everywhere: **mm** for the lift, **degrees** for the others.

---

## Joint ranges

| Index | Joint | HTTP API range (Lumi SDK doc) | Hardware (Lumi manual, brochure) | URDF |
|---|---|---|---|---|
| 0 / joint 1 | Lift | 0–300 mm | 0–400 mm | `l_1` 0–0.4 m |
| 1 / joint 2 | Waist rotation | −140…+140° | ±160° | `l_2` ±2.7925 rad |
| 2 / joint 3 | Head yaw (neck) | −180…+180° | ±180° | `l_3` ±3.1415 rad |
| 3 / joint 4 | Head pitch | −5…+35° | −5…35° | `l_4` −0.0872…0.6108 rad |

Observation: the vendor's web-UI screenshot (`private/images/body-01-extaxis-web-ui.png`) shows joint 0 at **355** (mm), above the documented 300, with the waist at −140, head yaw 175 and pitch 34. So the API may accept more than 300 mm on some firmware. Stay within 0–300 mm until we have read the robot's own limit. The vendor demo config limits the lift to 0–200 mm.

Head pitch sign: not documented. **Verify** on the robot with a +10° move (which way does the head tilt?).

---

## 1. Web page

Open `http://192.168.10.90:5000` → **ExtAxis**.

| Button | Chinese label in vendor docs | Action |
|---|---|---|
| Enable | 上使能 | Enable all 4 joints |
| Disable | 下使能 | Disable |
| Reset | 复位 | Clear joint errors |
| Stop | 急停 | Emergency stop of the axes |

Below: the **Joint State** table (Joint, Enable, Error, Error Code, Position, Velocity, Torque) and a **Joint State Chart**. Side menu: HOME, ExtAxis, Upgrade (firmware upload). When the arm side reports an external-axis error, the reset is still done on this page (web doc 3.3.5).

---

## 2. HTTP API

Base URL: `http://192.168.10.90:5000/api/extaxis` (old documents: `http://10.5.5.100:5000/...`). JSON bodies, `Content-Type: application/json`.

| Method | Path | Body | Purpose |
|---|---|---|---|
| GET | `/sysinfo` | — | Version and serial number |
| POST | `/reset` | `{}` | Clear joint errors |
| POST | `/enable` | `{"enable": 1}` / `{"enable": 0}` | Enable / disable all 4 joints |
| POST | `/moveto` | `{"pos": [lift_mm, waist_deg, head_yaw_deg, head_pitch_deg], "vel": 100, "acc": 100}` | Move all 4 joints. **Blocks** until the motion ends or fails |
| POST | `/stop` | `{}` | Stop the current motion (used by the vendor ROS node; not in the written doc) |
| GET | `/status` | — | Array of 4 joint objects |

`moveto` fields:

| Field | Meaning | Range |
|---|---|---|
| `pos` | Target `[lift, waist, head yaw, head pitch]` | Out-of-range values return an error |
| `vel` | Speed ratio (%) | 0.1–100, clamped |
| `acc` | Acceleration ratio (%) | 1–100, clamped |

Rules: enable first; every call sends all four values, so read `/status` and keep the joints you don't want to move at their current value.

`/status` returns one object per joint: `id`, `pos` (mm or deg), `vel`, `toq` (torque), `enable`, `error`, `ecode`.

Responses seen (web doc 3.3.4, `private/images/body-02-curl-enable-moveto.png`):

```json
{"message": "Axis enabled successfully", "status": 0}
{"message": "Axis move successfully", "status": 0}
```

`status` 0 = success; the vendor code treats `-1` as failure.

### curl

macOS / Linux:

```bash
curl -s http://192.168.10.90:5000/api/extaxis/sysinfo
curl -s -X POST http://192.168.10.90:5000/api/extaxis/reset  -H "Content-Type: application/json" -d '{}'
curl -s -X POST http://192.168.10.90:5000/api/extaxis/enable -H "Content-Type: application/json" -d '{"enable": 1}'
curl -s http://192.168.10.90:5000/api/extaxis/status
curl -s -X POST http://192.168.10.90:5000/api/extaxis/moveto -H "Content-Type: application/json" \
     -d '{"pos": [5, 0, 0, 0], "vel": 20, "acc": 20}'
curl -s -X POST http://192.168.10.90:5000/api/extaxis/enable -H "Content-Type: application/json" -d '{"enable": 0}'
```

Windows `cmd` (as in the vendor screenshot; `^` continues the line, inner quotes escaped):

```
curl -X POST http://192.168.10.90:5000/api/extaxis/moveto ^
  -H "Content-Type: application/json" ^
  -d "{\"pos\": [5, 0, 0, 0], \"vel\": 100, \"acc\": 100}"
```

### Python

```python
import requests

BODY = "http://192.168.10.90:5000/api/extaxis"

def body_status():
    joints = requests.get(f"{BODY}/status", timeout=2).json()
    return [j["pos"] for j in joints]                 # [lift mm, waist, head yaw, head pitch]

def body_enable(retries=5):
    """Vendor pattern: reset, enable, check, repeat."""
    for _ in range(retries):
        requests.post(f"{BODY}/reset", json={}, timeout=2)
        requests.post(f"{BODY}/enable", json={"enable": 1}, timeout=2)
        if all(j["enable"] for j in requests.get(f"{BODY}/status", timeout=2).json()):
            return True
    return False

def body_moveto(lift=None, waist=None, head_yaw=None, head_pitch=None, vel=20, acc=20):
    current = body_status()
    target = [v if v is not None else c for v, c in zip((lift, waist, head_yaw, head_pitch), current)]
    r = requests.post(f"{BODY}/moveto", json={"pos": target, "vel": vel, "acc": acc}, timeout=120)
    r.raise_for_status()                              # returns when the move is finished
    return r.json()

def body_stop():
    requests.post(f"{BODY}/stop", json={}, timeout=2)
```

Notes from the vendor code:

- Enabling can need retries (`jaka_integrated.py` tries 5 times).
- `moveto` blocks for the whole motion, so give it a long HTTP timeout. A vendor comment says it "often gets no response": treat a timeout as "unknown", then read `/status`.
- The vendor ROS node considers a move done when the lift is within 1 mm and the other joints within 1° of the target.

### Speeds

Not documented. Measure them at `vel=100` and `vel=20` (time a full lift stroke and a 90° waist turn) and record them in [00_START_HERE.md §9](00_START_HERE.md#9-robot-facts-fill-in-on-the-robot).

---

## 3. Cobo π external axes

On controllers with Cobo π the body joints are also registered as external axes of the arm controller (`private/images/arm-01-specs-cobopi-extaxis-settings.png`, `arm-02-cobopi-manual-extaxis-jog-notes.png`):

1. `https://192.168.10.90` → log in.
2. **Settings (设置) → Hardware & communication → External axis settings (外部轴设置)**: four axes of type "positioner" (变位机): 汇川升降 (Inovance lift), 腰 (waist), 脖子 (neck = head yaw), 头 (head = pitch), each with an enable switch.
3. **Manual (手动) → External axis jog (外部轴调节)**: choose the axis, see the current position, type a target and press "Move to target" (移动至目标点), or hold − / +. Speed slider at the bottom.

The newer JAKA SDK (2.3.x, in the LumiCode branch `robohub`) has `ext_power_on`, `ext_enable_on`, `ext_jog_to(axis, pos, vel, acc)` for these axes; the vendor body node used axis 1 = head left/right, 2 = head up/down, 3 = waist left/right, 4 = waist up/down (lift) with ±10 / ±3 clamps. This path is optional; the HTTP API is the documented one.

---

## 4. ROS 2

From the JAKA_Lumi `feat_ros` branch (`jaka_lumi_ros`, ROS 2 Humble, C++ with libcurl, IP hard-coded to 192.168.10.90):

**`jaka_lumi_body_node`** (`ros2 launch jaka_lumi_body_node lumi_body_node.launch.py`)

| Interface | Type | Notes |
|---|---|---|
| `/joint_states` | topic `sensor_msgs/JointState` | `l_1` in metres, others in radians (converted from the API's mm/deg) |
| `/lumi_body/enable` | `std_srvs/SetBool` | |
| `/lumi_body/move` | `jaka_lumi_body_node/MoveService`: `float64[4] target` (mm, deg, deg, deg) → `bool success` | |
| `/lumi_body/stop` | `std_srvs/Empty` | calls `/api/extaxis/stop` |
| `/lumi_body/reset` | `std_srvs/Empty` | |
| `/lumi_body/read_status` | `ReadStatusService` → `float64[4] position` | |

**`jaka_lumi_body_server`**: `FollowJointTrajectory` action server for MoveIt 2 (it also publishes the root of the TF tree, so start it before the arm server). See [09_ROS2_TELEOP_AND_SIM.md](09_ROS2_TELEOP_AND_SIM.md).

---

## 5. Test sequence for the first session

1. Read only: `GET /sysinfo`, `GET /status`. Write down firmware version and positions.
2. `reset`, `enable`, then `status` until all `enable` are true.
3. `moveto` with `vel=10`: head pitch 0 → 20 → 0; head yaw 0 → 30 → −30 → 0; waist 0 → 20 → −20 → 0; lift 0 → 50 → 0. Time each move.
4. Write down the positive direction of each joint (lift up/down, waist and head yaw left/right, pitch up/down) and the measured times.
5. `enable 0` at the end.
