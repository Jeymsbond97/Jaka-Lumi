# 13. To verify on the robot

Facts that no document gives and must be found on the real robot, each with a procedure. Do them in this order on the first session (connected to the robot network, see [02](02_NETWORK_AND_ACCESS.md)). Write every result into [00_START_HERE.md §9](00_START_HERE.md#9-robot-facts-fill-in-on-the-robot) and tick it here.

| # | What | Needed for | Status |
|---|---|---|---|
| 1 | Arm controller version (1.7 or 3.2) | SDK login, servo mode, gripper RS485 | ☐ |
| 2 | Which SDK login works: `login()` or `login(1)` | every arm script | ☐ |
| 3 | Servo mode supported (`servo_j`) | smooth trajectories, MoveIt, teleop | ☐ |
| 4 | Arm joint directions (+5° test) and joint speed limits | sending computed joint angles | ☐ |
| 5 | The onboard computer: is it the Thor, its IP, are the cameras/mic plugged into it, does `jkrc` load | running all code on the robot | ☐ |
| 6 | Body joint speeds, head pitch sign, accepted limits | body motion planning | ☐ |
| 7 | Camera serial numbers: which is head, which is torso | vision code | ☐ |
| 8 | AGV leg tracking (`human_detection`) enabled? | finding people | ☐ |
| 9 | Microphone array: can we get the sound direction? | turning toward a speaker | ☐ |
| 10 | AGV `theta_tolerance` unit; old HTTP port 8808 | navigation parameters | ☐ |
| 11 | Robot Wi-Fi password still the factory default? | access | ☐ |

---

## 1. Arm controller version

**Why:** controller 1.7 and 3.2 behave differently: 1.7 uses `login()` and supports servo mode and tool RS485; 3.2 uses `login(1)` and does not support them yet ([04 §2](04_ARM.md#2-controller-versions-17-vs-32)).

**How:**

1. Browser → `https://192.168.10.90` → log in (Cobo π; password in [private/ACCESS.md](private/ACCESS.md)).
2. Look for the version: **About** (user / info icon top right) or **Settings → System → Version upgrade**. It looks like `1.7.1_46_X64` or `3.2.x`.
3. The same is shown in the JAKA App: **About → Controller version**, or in the robot list when connecting (column "version").

**Record:** full version string.

## 2. SDK login

**How** (on a computer where `jkrc` runs: Linux PC, the Thor, or a Linux Docker container):

```python
import jkrc
r = jkrc.RC("192.168.10.90")
print("login()  ->", r.login())
r.logout()
print("login(1) ->", r.login(1))
print("sdk version ->", r.get_sdk_version())
print("status ->", r.get_robot_status_simple() if hasattr(r, "get_robot_status_simple") else r.get_robot_status()[0])
r.logout()
```

`(0,)` means success. If both work, use the one that matches the controller version (1.7 → `login()`, 3.2 → `login(1)`). If both fail with −3: network problem (ping 192.168.10.90). If an older controller (1.7.0 / 1.5) fails with SDK 2.2.7, use SDK 2.1.11.

**Record:** working login call, SDK version.

## 3. Servo mode

Arm **powered and enabled**, nothing near it.

```python
r.power_on(); r.enable_robot()
print("enable servo ->", r.servo_move_enable(True))
q = r.get_joint_position()[1]
print("servo_j (no motion) ->", r.servo_j([0, 0, 0, 0, 0, 0], 1, 1))   # relative move of 0 rad
print("disable servo ->", r.servo_move_enable(False))
```

All `(0,)` → servo mode works. An error code (e.g. 2 = not supported, −8 = not in servo mode) → not supported on this controller; use `joint_move` / `linear_move` only.

**Record:** supported yes / no, error code if not.

## 4. Arm joint directions and speed limits

1. Cobo π → **Settings → Safety → Joint limit**: write down soft limits and speed limit per joint.
2. Cobo π → **Settings → Operation → Mounting** and **Payload**: write down what is set.
3. Collision level 1, then for each joint `i`:

```python
import math
d = [0]*6; d[i] = math.radians(5)
r.joint_move(d, 1, True, 0.2)      # +5°, relative, 0.2 rad/s
print(r.get_joint_position()[1])
r.joint_move([-x for x in d], 1, True, 0.2)
```

Watch which way the joint turns and compare with the joint's axis in the official URDF (`l_a<i>`, positive = counter-clockwise around its z axis) and with Cobo π's 3D view.

**Record:** per joint: limits, speed limit, direction matches yes / no.

## 5. Thor on the robot network

The robot most likely carries its own computer (probably the Thor) cabled to the base's USB 3.0 port. Check: look at the robot for a computer and its cables, then:

1. If it is not already on the robot network, connect it (Lumi Wi-Fi or the base's RJ45).
2. On the Thor (monitor + keyboard, or SSH over the office network first): `ip -4 addr` or `hostname -I` → the `192.168.10.x` address.
3. Without access to the Thor: open the robot router `http://192.168.10.79` → connected devices list; or from a laptop on the robot network: `arp -a`, or `nmap -sn 192.168.10.0/24`.
4. From your laptop: `ssh <user>@<that IP>`.
5. Check the SDK on the Thor: `python3 --version`, then

```bash
export LD_LIBRARY_PATH=/path/to/SDK/Linux/python3/aarch64-linux-gnu:$LD_LIBRARY_PATH
cd /path/to/SDK/Linux/python3/aarch64-linux-gnu && python3 -c "import jkrc; print(jkrc)"
```

If the import fails (Python version mismatch, Thor has Python 3.12), use a Python 3.10 container: `docker run -it --rm --network host -v $PWD:/work arm64v8/python:3.10 bash`.

6. On it, check that the sensors are connected: `lsusb | grep -i -E "2bc5|orbbec"` (two lines) and `arecord -l` (AIUI-USB-MC).

**Record:** onboard computer model and IP on the robot network, cameras/mic visible yes / no, `jkrc` works natively / only in a container.

## 6. Body speeds, head pitch sign, limits

Body enabled ([03](03_BODY_LIFT_WAIST_HEAD.md)). Time each move with the blocking `moveto` call:

```python
import time, requests
B = "http://192.168.10.90:5000/api/extaxis"
def status(): return [j["pos"] for j in requests.get(f"{B}/status").json()]
def move(pos, vel):
    t = time.time()
    r = requests.post(f"{B}/moveto", json={"pos": pos, "vel": vel, "acc": 100}, timeout=120)
    return round(time.time() - t, 2), r.json(), status()

print(move([0, 0, 0, 0], 20))
for vel in (20, 100):
    print("lift 0->200", vel, move([200, 0, 0, 0], vel)); move([0, 0, 0, 0], vel)
    print("waist 0->90", vel, move([0, 90, 0, 0], vel));  move([0, 0, 0, 0], vel)
    print("head yaw 0->90", vel, move([0, 0, 90, 0], vel)); move([0, 0, 0, 0], vel)
    print("pitch 0->30", vel, move([0, 0, 0, 30], vel)); move([0, 0, 0, 0], vel)
```

Speed ≈ distance / time (includes acceleration; use the longer moves). During `pitch 0->30` look at the head: does it tilt **down** or **up**? Also note which way waist +90 and head yaw +90 turn (left/right seen from behind the robot).

Limits: the API rejects targets outside its range without moving, so send just outside the documented range at low speed and read the reply: `[301, 0, 0, 0]`, `[0, 141, 0, 0]`. If it accepts 301, the hardware range (up to 400 mm) is allowed; go back to 0 and do not explore further.

**Record:** mm/s and deg/s at vel 20 and 100, pitch sign, positive directions, accepted limits.

## 7. Camera serial numbers

The cameras are not on the network: they are USB devices.

1. Plug a **USB 3.0** cable (USB-C to USB-A adapter on a Mac) from your computer into the base's USB 3.0 port marked for the cameras and voice module. If the Thor is plugged into that port, unplug it first (or do this on the Thor).
2. Start **OrbbecViewer**. The device list shows two entries like `Orbbec Gemini 2 L SN:AY8V74300xx USB3.0`. If it shows "USB2.0", change cable/port.
3. Open one camera's Color stream and cover the head camera with your hand: the stream that goes black is the head camera.
4. Linux alternative: `lsusb | grep 2bc5` and

```python
from pyorbbecsdk import Context
dl = Context().query_devices()
for i in range(dl.get_count()):
    print(dl.get_device_by_index(i).get_device_info().get_serial_number())
```

**Record:** head SN, torso SN.

## 8. AGV leg tracking

```python
import socket, time
s = socket.create_connection(("192.168.10.10", 31001), timeout=5)
s.sendall(b"/api/request_data?topic=human_detection&frequency=2")
s.settimeout(1)
t = time.time()
while time.time() - t < 20:          # walk around the robot within ~2 m during these 20 s
    try: print(s.recv(65536).decode())
    except socket.timeout: pass
```

- Reply `status: OK` and then `"type": "callback", "topic": "human_detection"` messages with `legtrack N` positions → enabled.
- `OK` but no callbacks while you walk, or an error status → not enabled (the manual says the leg-tracking module must be configured and enabled). Look in the web monitor `http://192.168.10.10:9001` → **configuration** for a person / leg detection setting; otherwise ask JAKA.

**Record:** enabled yes / no; position frame check (stand in front: x should be positive).

## 9. Microphone array direction

Connect the computer to the base USB port as in step 7 (the voice module is on the same port).

1. List devices: Linux `lsusb`, `arecord -l`, `ls /dev/ttyUSB* /dev/ttyACM*`; macOS: System Settings → Sound → Input shows `AIUI-USB-MC`, and `ls /dev/tty.usb* /dev/cu.usb*` for serial ports.
2. Does a **serial device** appear together with the audio device? If yes, open it (try 115200 baud, 8N1) and say the wake word near the robot: does a message with an angle appear?

```bash
python3 -m serial.tools.miniterm /dev/ttyACM0 115200     # or the port found above
```

3. How many **audio channels** does it offer? Linux: `arecord -D hw:<card> --dump-hw-params -d 1 /dev/null`; macOS: Audio MIDI Setup → AIUI-USB-MC → input channels. 1–2 channels = processed audio only; 6–8 channels = raw mics, so the direction can be computed by us (GCC-PHAT with the ring geometry).
4. If neither works: ask JAKA / iFlytek for the XF-USB-MC protocol (wake-up angle).
5. If an angle is available: find where 0° points and which way is positive (speak from front, left, right, back).

**Record:** serial port yes / no and messages, channel count, angle zero and direction.

## 10. AGV details

- `theta_tolerance` unit: send `/api/move?marker=home&theta_tolerance=0.1` and compare the final heading error in `current_pose.theta` with a larger value; or ask JAKA. (Manual: degrees; company translation: radians.)
- Old HTTP access: `curl -s http://192.168.10.10:8808/api/robot_status`. A JSON reply means the HTTP form works too.

**Record:** unit, HTTP yes / no.

## 11. Wi-Fi password

Join `Lumi<serial>` with the factory password from [private/ACCESS.md](private/ACCESS.md). If it is refused, the password was changed: check with the person who set up the robot, or the router page `http://192.168.10.79` (wired connection) → wireless settings.

**Record:** password works yes / no (new password only in `private/ACCESS.md`).
