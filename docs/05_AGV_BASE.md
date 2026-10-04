# 05. Mobile base (AGV)

The base drives and navigates on its own (lidar SLAM). We use it two ways: the **web monitor** for mapping, markers and manual driving, and the **TCP API** from code. Specs are in [01_HARDWARE.md](01_HARDWARE.md#3-mobile-base-agv).

---

## 1. Power

1. First start: switch the main power switch underneath (next to the rear right caster) to **I** ("pull" it on).
2. Hold the power button on the base: two short beeps, purple LED, release after the third, long beep; green flashing while booting; **white** when ready.
3. Off: hold the button, seven short beeps, release on the eighth, long beep. Or "shutdown" in the web monitor, or `/api/shutdown`.
4. Main switch to **O** if the robot stands for more than 30 days.

While the base is off but charging, its Wi-Fi may be visible, but nothing answers until it is switched on.

---

## 2. Web monitor (`http://192.168.10.10:9001`)

Use Chrome. Screenshots: `private/images/agv-*.png`.

**Status bar (top left):** map name / floor, battery %, soft E-stop and hard E-stop state, move state (`idle`, `running`, ...), target marker, chassis serial number, software version.

**Top menu:** floor selector, track (keep the robot centred), laser, ultrasonic, infrared, 4g, **position correction**, **add marker** (at current position / at a chosen location), add line (no-go line), add zone, add route (beta), **control** (drive with the keyboard), measure, global path, particle cloud, log, other, **soft E-stop**.

**Bottom menu:** network, restart software, power off and restart, shutdown, update & diagnose, **map management**, configuration, sensor status, test tools, elevator tools, map tools, deployment-detection, robot-3d.

### 2.1 Prepare the area (web doc 3.4.1)

- Close the area with hard boards; avoid reflective material; boards must be at lidar height (inside the scan range).
- Make it a closed polygon (a rectangle is best).

### 2.2 Create a map

1. Bottom menu → **map management** → tab **Map Creating**.
2. Enter **Map Name** (e.g. `office_0301`) and **floor** (e.g. `1`) → **Create Map**.
3. Choose the map size: **small map** (< 3600 m²), **middle map** (3600–10 000 m²), **big map** (> 10 000 m²). Tabs "v1 scanning / v2 scanning" are at the top (v2 used in the company test).
4. The map builder opens (port 8809). Drive the base by hand with the keyboard: **i** forward, **k** back, **j** turn left, **l** turn right. Keep about 0.5 m from the walls, steady speed (≤ 0.5 m/s; slider at the top, 0.7 used), turn 360° in each corner to help feature matching. ("start" on the right runs an automatic scan; manual driving is recommended.)
5. Watch "optimizing progress"; press **Save** when done. A page `192.168.10.10:8809/map-build/map.html?hotelid=<map>&floor=1&map_type=v2` opens (buttons "continue scan" / "rescan"); close it.

### 2.3 Use the map

1. Map management → **Switch Map** → choose the map name and floor → **Apply** (the page `192.168.10.10:9001/robot-map-config.html`).
2. Close map management and check the new map on the main page.

### 2.4 Position correction (relocalise)

When the robot icon on the map is not where the robot really is (for example after switching maps, after pushing it while off, or after starting away from the dock):

1. Top menu → **position correction**.
2. Click at the robot's real position on the map and drag in the direction it faces.
3. A dialog appears. Black lines = walls from the map; red = what the lidar sees now; purple = the copy you are moving.
4. Move the purple copy onto the black lines with the buttons or keys: **i** up, **k** down, **j** left, **l** right, **u** rotate clockwise, **o** rotate counter-clockwise. Then **OK**.

It is enough to be within about 20 cm and 5°; the base refines the rest. If the robot is on its dock and a dock marker exists, it snaps to the dock marker automatically.

### 2.5 Add markers (named goals)

1. Drive to the place: top menu **control** on, keys **i / k / j / l**, then **control** off.
2. Top menu **add marker → insert marker at current position** (or "at specified location": click and drag for the heading).
3. In **edit marker**: **Marker type** and **Marker name** (≤ 50 characters), optional icon → **Save**.

Marker types:

| Type | Name | Attributes | Use |
|---|---|---|---|
| 0 | Normal point | — | Go to this pose, nothing else |
| 3 | Lift outside | lift module number | Wait for and call the lift here |
| 4 | Lift inside | lift module number | Position inside the lift (same relative position on every floor) |
| 7 | Gate / door | ID, distance, one-way | Gate or automatic door control point; arrow at 90° to the passage |
| 8 | Lift waiting point | lift number | Needed with several lifts and robots |
| 11 | Charging dock | dock number, charging-pile type | Where the dock really stands; number from the dock's label |
| 20 | Narrow-area waiting point | — | Wait outside a narrow area |
| 76 | Slow-down point | ratio, distance, one-way | Slow down near slopes or thresholds (default ±50 cm) |

Example dock marker: type `11` → the name is filled in automatically (`charge_point_1F_<dock number>`), num = dock number, "common charging pile" → Save. Markers on the map are shown as `name[type][num]`. Every name must be unique (also across floors).

### 2.6 Drive and navigate from the web page

- **control** mode: keys **i j k l**, or click a point on the map to drive there.
- Navigation test: right-click a target on the map; the base plans a green path and drives.
- One marker: show it ("display point") and send the move. Several markers: **test tools** → choose markers, repeat count → run.

---

## 3. TCP API

### Protocol

- TCP client to **`192.168.10.10:31001`** (or the base's LAN IP when it joined another Wi-Fi via the API). Socket, not serial.
- Commands are URL-like strings; replies are JSON.
- Add `uuid=<anything>` to a command and the reply carries it back.
- Reply `type`: `response` (to your command), `callback` (data you subscribed to), `notification` (events pushed to all clients).
- Reply `status`: `OK`, `INVALID_REQUEST`, `REQUEST_DENIED`, `UNKNOWN_ERROR`, `GOAL_CAN_NOT_BE_REACHED`; reason in `error_message`.

```python
import json, socket, uuid

AGV = ("192.168.10.10", 31001)

def agv(command, timeout=5.0):
    """Send one command, return its response (skips callbacks/notifications on the same socket)."""
    tag = uuid.uuid4().hex
    command += ("&" if "?" in command else "?") + f"uuid={tag}"
    buf = ""
    with socket.create_connection(AGV, timeout=timeout) as sock:
        sock.sendall(command.encode())
        dec = json.JSONDecoder()
        while True:
            buf += sock.recv(65536).decode()
            while buf.strip():
                try:
                    msg, end = dec.raw_decode(buf.lstrip())
                except json.JSONDecodeError:
                    break                                   # partial message, read more
                buf = buf.lstrip()[end:]
                if msg.get("type") == "response" and msg.get("uuid") == tag:
                    return msg

print(agv("/api/robot_status"))
```

### Direct velocity control: `/api/joy_control` (our own trajectories)

```
/api/joy_control?linear_velocity=0.2&angular_velocity=0.5
```

| Parameter | Unit | Range | Sign |
|---|---|---|---|
| `linear_velocity` | m/s | −0.5…0.5 (clamped) | + forward |
| `angular_velocity` | rad/s | −1.0…1.0 (clamped) | + turn left (counter-clockwise) |

- **One command lasts 0.5 s**, then the base stops. Send at > 2 Hz (10 Hz recommended) for continuous motion.
- Overrides navigation (`/api/move`).
- Vendor keyboard example: every 0.1 s, v = 0.5 m/s, w = 0.3 rad/s.

```python
import time
def drive(v, w, seconds, rate=10):
    t_end = time.time() + seconds
    while time.time() < t_end:
        agv(f"/api/joy_control?angular_velocity={w}&linear_velocity={v}")
        time.sleep(1 / rate)
```

### Navigation

| Command | Parameters | Notes |
|---|---|---|
| `/api/move?marker=NAME` | `marker`, or `location=x,y,theta` (map frame, m, rad); optional `max_continuous_retries` (30), `distance_tolerance` (m), `theta_tolerance` (official PDF: degrees; company translation: radians, **verify**), `angle_offset` (rad, −3.14…3.14), `yaw_goal_reverse_allowed` (1/0), `occupied_tolerance` (m) | Plans a path and avoids obstacles. Returns `task_id`. Rejected while another move is `running` |
| `/api/move?markers=m1,m2,m3&count=-1&distance_tolerance=1.0` | ≥ 2 markers, count (−1 forever; default 1), tolerance ≥ 0.5 m (default 0.5), `max_continuous_retries` (default 5) | Patrol; a failed point is skipped and the patrol continues; stop it with `/api/move/cancel` |
| `/api/move/cancel` | — | Stop the task and stay |
| `/api/get_planned_path` | — | Points of the current global path |
| `/api/make_plan?start_x=..&start_y=..&start_floor=..&goal_x=..&goal_y=..&goal_floor=..` | | Path length between two points |

Wait for a move to finish (vendor pattern): poll `/api/robot_status` every 0.1–0.5 s until `results.move_status == "succeeded"` (or `failed` / `canceled`).

### State

| Command | Returns |
|---|---|
| `/api/robot_status` | `move_target`, `move_status` (`idle` / `running` / `succeeded` / `failed` / `canceled`), `running_status` (e.g. `leave_charging_pile`, `dock_to_charging_pile`, lift states), `move_retry_times`, `charge_state`, `soft_estop_state`, `hard_estop_state`, `estop_state`, `power_percent`, `current_pose {x, y, theta}` (m, rad), `current_floor`, `chargepile_id`, `error_code`. Poll at 1–2 Hz |
| `/api/robot_info` | `product_id` |
| `/api/get_power_status` | `battery_capacity` %, `battery_current` (A, + charging), `battery_voltage`, `charge_voltage`, `charger_connected_notice`, `head_current` |
| `/api/diagnosis/get_result` | Self-test: sensor board, motor boards, radio, power, depth camera, laser, IMU, CAN, internet |
| `/api/software/get_version` | Software version (`check_for_update`, `update`, `restart` also exist) |

### Real-time streams: `/api/request_data?topic=...&frequency=Hz`

| Topic | Default | Data |
|---|---|---|
| `robot_status` | 2 Hz | as `/api/robot_status` |
| `human_detection` | 1 Hz | `"legtrack N": {"position": {x, y}, "velocity": {x, y}}` in the robot frame (x ahead, right-handed, so y left). **Needs the leg-tracking module configured and enabled** |
| `robot_velocity` | 1 Hz | `linear` (m/s, + forward), `angular` (rad/s, + left) |

Keep the socket open to receive the callbacks.

### Markers

| Command | Notes |
|---|---|
| `/api/markers/insert?name=N&type=0&num=1` | At the current pose. Custom types > 1000 |
| `/api/markers/insert_by_pose?name=N&x=..&y=..&theta=..&floor=..` | At given coordinates |
| `/api/markers/query_list`, `/api/markers/query_brief`, `/api/markers/count` | List |
| `/api/markers/delete?name=N` | Delete |
| `/api/position_adjust?marker=N`, `/api/position_adjust_by_pose?x=..&y=..&theta=..` | Relocalise (only after drift) |

### Settings and other

| Command | Notes |
|---|---|
| `/api/set_params?max_speed_linear=0.3&max_speed_angular=0.5` | 0.1–1.0 m/s, 0.5–3.5 rad/s; reset at restart; always answers `OK`, confirm with `/api/get_params` |
| `/api/estop?flag=true` / `false` | Software E-stop (motors free, base can be pushed). Separate from the hardware E-stop; neither releases the other; reset to false at restart |
| `/api/map/list`, `/api/map/get_current_map` (resolution, width, height, origin), `/api/map/set_current_map?map_name=..&floor=..`, `/api/map/list_info` | Maps (setting a map restarts the base service) |
| `/api/map/accessible_point_query?x=..&y=..`, `/api/map/distance_probe?x=..&y=..` | Nearest reachable point; distance to obstacles |
| `/api/LED/set_color?r=..&g=..&b=..` (0–100), `/api/LED/set_luminance?value=..` | Base LED strip |
| `/api/shutdown?reboot=false&delay=0` | Off after 10 s |
| `/api/wifi/list`, `/api/wifi/connect`, `/api/wifi/get_active_connection`, `/api/wifi/info`, `/api/wifi/detail_list` | Base Wi-Fi |
| `/api/lift_status` | Only while riding a lift |

**Notifications** (pushed; do not use for flow control): full code list in [3.2](#32-further-details-from-the-agv-api-manual).


### 3.1 Captured on our robot

Real replies from our base (move, cancel, estop, the full `robot_status` with extra fields, `query_list`), the markers on our map, and the company's streaming client: [private/AGV_ON_OUR_ROBOT.md](private/AGV_ON_OUR_ROBOT.md) (local only). In short: on our base `task_id` comes inside `results`, and `robot_status` has extra fields (`chassis_lift_state`, `collision_state`, `hall_state`, `hand_charge`, `hard_estop_abolish_state`, `is_paused`, `extraData`, `outTaskId`, `target_floor`, `task_id`, `ts`).

### 3.2 Further details from the AGV API manual

Source: `AGV API手册.pdf` (69 pages, Chinese; document v1.8.8 of 2022-03-18; the copy in this project root is byte-identical to the one in the JAKA_Lumi repo). Our base runs software 0.10.351.1D, which is newer than the manual, so some fields differ (see 3.1 and the private notes).

**Protocol notes**

- Replies are JSON; fields at the same level have no fixed order, parse them with a JSON parser.
- Socket is recommended; a serial link is also possible but can corrupt data.
- Old address format: since v1.4.0 the `http://192.168.10.10:8808` prefix was dropped from the commands, and the manual says the original format "can still be used", i.e. `http://192.168.10.10:8808/api/robot_status` over HTTP. **Verify** on our base before relying on it.
- `error_code` in `robot_status`: hexadecimal string of 8 bytes; anything other than `"00000000"` means a fault.

**`running_status` values** (`move_status` in brackets): `idle` (idle/succeeded/failed/canceled), `leave_charging_pile`, `dock_to_charging_pile`, `leave_container`, `dock_to_container`, `leave_cabin`, `dock_to_cabin`, `goto_lift`, `wait_lift_unlock`, `wait_lift_outside`, `enter_lift`, `avoid_lift`, `take_lift`, `exit_lift`, `back_to_lift` (all running), `running` (any other running state). Do not cancel a move during `enter_lift`, `avoid_lift`, `take_lift`, `exit_lift`.

**`/api/robot_info`** → `{"results": {"product_id": "WATER-xxxx-xxxxx"}}` (base serial; software ≥ 0.6.3.3).

**Markers**

| Command | Parameters | Reply |
|---|---|---|
| `/api/markers/insert` | `name` (no special characters), `type` (int, default 0), `num` (int, default 1) | marker at the current pose and floor. Examples: `?name=205_room`, `?name=charge_dock_2&type=11` |
| `/api/markers/insert_by_pose` | `name` (an existing name is updated), `x`, `y` (map, float), `theta` (float, −π…π), `floor` (int ≠ 0, default current floor), `type` (default 0), `num` (default 1) | `?name=205_room&x=-0.1&y=1.0&theta=0.0&floor=2&type=0` |
| `/api/markers/query_list` | `floor` (optional; all floors otherwise) | `results` = `{name: {"floor", "pose": {"orientation": {x, y, z, w}, "position": {x, y, z}}, "key": type, "marker_name"}}`; `null` if there are no markers. Our robot also returns `avatar` (icon) |
| `/api/markers/count` | — | `{"results": {"count": 10}}` |
| `/api/markers/query_brief` | — | `{"results": {"meeting_room": "0-1", ...}}` = `"type-floor"` per name |
| `/api/markers/delete` | `name` | `OK`; unknown name → `status: "INVALID_REQUEST"`, `error_message: "Marker Not Found"` |

Marker types usable through the API: `0` normal, `1` front desk, `3` lift outside, `4` lift inside, `7` gate, `11` charging dock; other types should be created in the web monitor. Custom types must be > 1000.

Quaternion → `theta` (from the manual):

```python
import math
def quat_to_theta(z, w):
    theta = 2 * math.atan2(z, w)
    if math.pi < theta <= 2 * math.pi:
        theta -= 2 * math.pi
    elif -2 * math.pi <= theta < -math.pi:
        theta += 2 * math.pi
    return theta
```

**Wi-Fi of the base**

| Command | Parameters | Reply |
|---|---|---|
| `/api/wifi/list` | — | `{"SSID1": 50, ...}` (SSID → signal strength) |
| `/api/wifi/connect` | `SSID`, `password` (optional if connected before) | joins / switches the environment Wi-Fi |
| `/api/wifi/get_active_connection` | — | current SSID, `""` if none |
| `/api/wifi/info` | — | `{"IPaddr": "...", "HWaddr": "..."}` (IP from the environment Wi-Fi) |
| `/api/wifi/detail_list` | — | per SSID: `SSID`, `SIGNAL`, `ACTIVE`, `FREQ` (e.g. "2462 MHz"), `SECURITY` (e.g. "WPA2", empty = open) |

After joining another Wi-Fi, the API is also reachable at that IP (port 31001).

**Other replies**

- `/api/software/get_version` → `{"results": "x.x.x"}`.
- `/api/map/set_current_map?map_name=<name>&floor=<n>` (`hotel_id` is the deprecated name of `map_name`); the base service restarts, so a reply may not arrive.

**Notifications (`"type": "notification"`)**: fields `code` (stable ID), `description` (English), `level` (`info` / `warning` / `error`), `data` (extra info, e.g. `{"target": "room_205"}`; task-end notifications carry the distance driven). Poll `robot_status` for decisions; notifications can be lost.

| Group | Codes |
|---|---|
| Move task | `01001` started, `01002` finished, `01003` failed, `01004` canceled, `01005` retried, `01006` robot may be trapped (help needed), `01007` no available path (then `01003`) |
| Charging dock | `01010` leaving dock, `01011` left, `01012` failed to leave, `01013` leave retry; `01020` docking started, `01021` docked, `01022` docking failed, `01023` docking data invalid, `01024` no docking feature found, `01025` no power signal, `01026` no infrared signal, `01027` docking timeout |
| Container / cabin | `01028` wrong cabin ID, `01029` lateral mode failed, `01050–01053` leave container, `01060–01062` dock to container, `01070–01073` leave cabin, `01080–01082` dock to cabin |
| Gate / door, narrow area | `01030` door control started, `01031` finished, `01032` door control timeout (released); `01033` waiting for a narrow area, `01034` narrow area free |
| Patrol | `01101` started, `01102` finished, `01103` failed (last point failed), `01104` canceled |
| Path / traffic | `01200` traffic busy, `01201` trapped in an unknown (grey) area, `01202` trapped near an obstacle, `01203` global planning failed (about every 5 s while stuck), `01204` local planning failed, `01210` no-entry sign detected, zero velocity |
| Lift | `04000–04002` go to lift, `04010–04013` call lift (`04013` > 3 min), `04020–04023` ride (`04023` > 3 min), `04030–04033` enter (`04033` not enough space, next lift), `04040–04041` avoid lift, `04050–04052` exit, `04060–04062` back to lift, `04070–04071` wait for unlock |
| State | `02000` power off, `02001` charging on, `02002` charging off, `02003` E-stop on, `02004` E-stop off, `02005` attitude correction triggered (robot may have been moved), `02006` software shutting down, `02010` robot may be lost (`probability`; can be a false alarm) |
| Abnormal | `03001` foreign object in the lidar slot |

---

## 4. Environment rules (chassis manual)

- Indoors, flat floor, no drops over 1.5 cm, thresholds under 1.8 cm, slopes within 8°.
- Lidar blind spots: obstacles lower than about 23 cm (8 cm with a downward camera on the upper body), reflective, black or transparent objects, objects under 2 cm.
- Map drift: carpets over 0.5 cm, wet floors, large empty halls, often-moved furniture, fast driving over bumps, pushing the base while on, starting away from the dock.
- Draw no-go lines around areas the robot must not enter (0.5 m from danger), slow-down zones at slopes, drop zones at stairs.
- Dock against a wall, 0.5 m free each side, ≥ 1.5 m between docks, fixed in place.

---

## 5. First-session base tests

1. Web monitor: map loaded? position correct? battery? E-stops off?
2. API read-only: `robot_status`, `get_power_status`, `software/get_version`, `map/get_current_map`, `markers/query_brief`, `diagnosis/get_result`.
3. In a clear area: `joy_control` 0.1 m/s for 2 s at 10 Hz, then 0.3 rad/s for 2 s. Compare `robot_velocity` and `current_pose`.
4. Try the soft E-stop on and off.
5. Subscribe to `human_detection`, walk around the robot, log positions (tells us whether leg tracking is enabled).
6. Create a marker, `/api/move?marker=...`, poll until `succeeded`.
