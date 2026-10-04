# 10. Gripper

**Status: no gripper is mounted yet.** This page collects everything the vendor material says about grippers on Lumi, so that one can be chosen, wired and programmed later. When a gripper is installed, fill in section 6.

---

## 1. What JAKA uses on Lumi

| Gripper | Where it appears | Interface used |
|---|---|---|
| **DH-PGEA-50** (DH Robotics, electric parallel gripper) + 3D-printed fingers | JAKA education kit hardware list (web doc 3.6.2, `private/images/gripper-01-vendor-hardware-list.png`), selection manual `DH_PGEA选型手册250628_中文版_V255.pdf`, finger model `教育夹指.stl`, finger shell STEP files (in the Feishu doc) | Modbus RTU over RS485 |
| DH gripper on `/dev/DH_hand` | BMW vending demo (`LUMI_DEMO_BMW/LumiAgent/utilfs/python_open_gripper.py`) | USB-RS485 adapter on the host PC, Modbus RTU |
| DH gripper on the tool connector | LUMI_DEMO-v3 `dh_gripper.py`, `jaka_integrated.py` (`gripper_init/open/close`) | Arm tool I/O (TIO) RS485 channel, Modbus RTU through the JAKA SDK |
| DH **AG-95** (two units) | VR teleop `k1_robot/control_gripper.py` (`pyDHgripper.AG95` on `/dev/ttyUSB0`, `/dev/ttyUSB1`) | USB serial; ROS topics `<name>/set_pos` (0…1 → 0…1000), `/set_force`, `/set_vel`, `/current_pos` |
| Digital-output gripper | `utilfs/jaka.py grab_action()` (`set_digital_output(1, 0/1, …)`) | Tool DO1/DO2 |

Brochure options: 3-finger or 5-finger dexterous hands, electric grippers, soft grippers (contact JAKA sales).

---

## 2. Mechanical and electrical limits (arm side)

| Item | Value |
|---|---|
| Flange | ISO 9409-1, pitch circle 50 mm, 4 × M6 (15.3 Nm, grade ≥ 12.9), Ø6 H7 locating pin hole (45° clockwise from +Xm) |
| Max flange torque | 14 Nm |
| Arm payload | 2 kg in total (gripper + object), less at a larger centre-of-mass offset (payload chart in the Lumi manual 5.8.1) |
| Tool power (TIO pin 1) | 24 V or 12 V, 1 A continuous, 2 A peak |
| Tool DO | 2 × ≤ 1 A (NPN / PNP / push-pull) |
| Tool RS485 | channel 1 on DO1/DO2 (A+/B−, high speed, Modbus RTU, up to 230400 baud); channel 2 on AIN1/AIN2 (low speed) |
| Connector | M8 8-pin, pinout in [04_ARM.md](04_ARM.md#8-tool-io-connector-m8-8-pin-tio-v3) |

**Controller 3.2 does not support TIO RS485 yet** (web doc 3.3.5.3). On 3.2, connect an RS485 gripper through a USB-RS485 adapter to the host computer instead.

---

## 3. DH Modbus RTU commands (from vendor code)

Settings: slave ID 1, 115200 baud, 8 data bits, no parity, 1 stop bit. Function `0x06` write register, `0x03` read register; CRC16 Modbus (poly 0xA001, low byte first).

| Register | Access | Meaning | Values |
|---|---|---|---|
| `0x0100` | write | Initialise (home) | `0x0001` (TIO demo) or `0x00A5` (BMW demo) |
| `0x0101` | write | Force | % (e.g. `0x001E` = 30 %) |
| `0x0103` | write | Target position | 0…1000 (‰ of stroke). In the vendor code 0 = closed, 1000 = fully open |
| `0x0200` | read | Initialisation state | 1 = done |
| `0x0201` | read | Grip state | 0 = moving; non-zero = stopped / object held |
| `0x0202` | read | Current position | 0…1000 |

Frames used (without CRC unless shown): init `01 06 01 00 00 01`; close `01 06 01 03 00 00`; open `01 06 01 03 01 F4` (500) or `03 E8` (1000); force 30 % `01 06 01 01 00 1E`; read grip state `01 03 02 01 00 01`.

### 3.1 Through a USB-RS485 adapter (BMW demo)

```python
import serial, time

def crc16(data: bytes) -> bytes:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return bytes([crc & 0xFF, crc >> 8])

def write_reg(ser, addr, value, slave=1):
    frame = bytes([slave, 0x06, addr >> 8, addr & 0xFF, value >> 8, value & 0xFF])
    ser.write(frame + crc16(frame)); return ser.read(8)

with serial.Serial("/dev/ttyUSB0", 115200, bytesize=8, parity="N", stopbits=1, timeout=0.2) as ser:
    write_reg(ser, 0x0100, 0x0001); time.sleep(2)    # initialise
    write_reg(ser, 0x0103, 1000);   time.sleep(1)    # open
    write_reg(ser, 0x0103, 0)                        # close
```

(The vendor names the port `/dev/DH_hand` with a udev rule; `pip install pyserial`.)

### 3.2 Through the arm's tool connector (LUMI_DEMO-v3, controller 1.7)

```python
import time, jkrc
robot = jkrc.RC("192.168.10.90"); robot.login(); robot.power_on()
robot.disable_robot()                    # TIO settings need the arm disabled
robot.set_tio_vout_param(1, 0)           # tool power on, 24 V
robot.set_tio_pin_mode(2, 1)             # pin mode as in the vendor code (check against the gripper wiring)
robot.set_rs485_chn_mode(1, 0)           # channel 1 = Modbus RTU
robot.set_rs485_chn_comm({'chn_id': 1, 'slave_id': 1, 'baudrate': 115200,
                          'databit': 8, 'stopbit': 1, 'parity': 78})   # 78 = 'N' no parity
robot.enable_robot(); time.sleep(1)
robot.send_tio_rs_command(1, bytearray.fromhex("01 06 01 00 00 01"))   # initialise
time.sleep(2)
robot.send_tio_rs_command(1, bytearray.fromhex("01 06 01 03 00 00"))   # close
time.sleep(2)
robot.send_tio_rs_command(1, bytearray.fromhex("01 06 01 03 01 F4"))   # open to 500
```

The same can be configured in Cobo π / JAKA App: I/O → Tool → DO_1 → "Reuse as RS485 channel 1" → RS485 configuration: Modbus RTU, baud, data/stop bits, parity, slave ID; optional "semaphores" to read registers.

### 3.3 Digital-output gripper

```python
robot.set_digital_output(1, 0, 1)   # IO_TOOL, DO1 = 1  → close
robot.set_digital_output(1, 0, 0)   # DO1 = 0           → open
```

---

## 4. Installation checklist (when a gripper arrives)

1. **Choose**: payload of gripper + heaviest object ≤ 2 kg at the expected offset; stroke fits the objects; 24 V supply current within 1 A continuous (or use an external supply).
2. **Mount**: adapter plate for ISO 9409 50 mm / M6; align the pin hole.
3. **Wire**: to the M8 tool connector (RS485 on pins 4/5 or 6/7, 24 V pin 1, GND pin 8), or to a USB-RS485 adapter on the host.
4. **Configure** in Cobo π / JAKA App: payload (mass, centre of mass), TCP (tool centre between the fingers), tool I/O mode, collision sensitivity.
5. **Test** open/close with the commands above at low force.
6. **Code**: open / close / set position (and pick / place) functions in our robot library.
7. **Document** below.

---

## 5. Links

| What | Where |
|---|---|
| DH Robotics PGEA product page ("夹爪适配: DH-PGEA-50") | Linked in the Feishu doc 3.6.2.2 (login required); DH Robotics website |
| DH-PGEA selection manual (Chinese, V255) | Feishu doc attachment |
| 3D-printed finger STL and shell STEP | Feishu doc attachments |
| `pyDHgripper` (AG95 class) | used by the vendor teleop code |
| Vendor gripper code | jaka-robot-demos `dev/jamie`: `LUMI_DEMO-v3/.../dh_gripper.py`, `jaka_utilfs/jaka_integrated.py`; JAKA_Lumi `main`: `LUMI_DEMO_BMW/LumiAgent/utilfs/python_open_gripper.py`; `LumiCode`: `Lumi_Teleoperation/src/k1_robot/k1_robot/control_gripper.py` |

---

## 6. Our gripper (fill in)

| Item | Value |
|---|---|
| Model | |
| Mass, centre of mass (mm from flange) | |
| TCP offset (x, y, z, rx, ry, rz) | |
| Stroke, force range | |
| Interface and wiring | |
| Port / channel, baud, slave ID | |
| Open / close commands | |
| Date installed, notes | |
