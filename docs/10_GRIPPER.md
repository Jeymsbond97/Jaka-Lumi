# 10. Gripper

A Zimmer electric parallel gripper is mounted on the arm flange. It is driven by the two digital outputs of the arm's tool connector and reports its finger position on an analog input. An optical sensor on one finger mount detects objects below the gripper.

---

## 1. Hardware

| Part | Description |
|---|---|
| Gripper | **Zimmer GEP2013IO-05-B**: electric 2-jaw parallel gripper, digital I/O version. GEP2013 family datasheet: **13 mm stroke per jaw**, **gripping force 90–360 N** in four levels, **mass about 0.54 kg** without fingers. Rotary switch "Funct" 1–4 selects the force level (4 = 360 N); set to **1**. Green LED = powered |
| Fingers | Long stainless-steel fingers with curved tips on L-shaped brackets, for cups and glasses. Fingertips about 265 mm from the flange face; the fingers sit beside the flange axis, not on it (about 8 cm off, estimate) |
| Finger sensor | **MISUMI** optical (photoelectric) sensor, yellow/black housing, on the side of one finger mount. It sees what is **below the gripper**, not an object between the fingers. The red light is its emitter and is always on; the indicator LED on its back is red when something is in front of it, blue when nothing is |
| Cable | Gripper and sensor are wired to the arm's M8 tool connector (TIO), see [04_ARM.md §8](04_ARM.md#8-tool-io-connector-m8-8-pin-tio-v3) |

Even force level 1 (~90 N) is far more than a plastic cup needs: the software must not close on objects that cannot take it (`manipulation/skills.py` refuses objects of the wrong width).

### Finger geometry

Each finger is a straight thin shank below its mount block, then a C-shaped hook that bends out and curves back in to an inward tip. Inner gap between the fingers:

| Where | Open | Closed |
|---|---|---|
| Tips (entry gap) | 88 mm | 59 mm |
| Belly: widest point inside the hook | 96 mm | 70 mm |
| Neck: narrowest point where the hook meets the shank | 73 mm | 47 mm |
| Shank: the straight part, same gap along its length | 66 mm | 39 mm |

Along the fingers, from the bottom face of the Zimmer body (±5 mm): shank starts ~100 mm, hook starts ~150 mm, tips ~200 mm.

A round object narrower than 70 mm is not squeezed by the belly. An 82 mm cup passes the 88 mm entry with only ~3 mm per side: approach on the centre line.

**Grasp point** (where a cup's axis sits between the fingers, 4 cm below the rim): **(106.4, −86.5, 230.5) mm in the flange frame** (268 mm from the flange, 137 mm off its axis), stored in `data/grasp_teach.json` with the flange pose.

---

## 2. Signals

**All tool I/O must be set to PNP** (Cobo π → I/O → Tool(S), ⋮ menu of each DI / DO → PNP). With the factory setting NPN the gripper does not move and the sensor is not read.

| Signal | Direction | Meaning | Values |
|---|---|---|---|
| **DO_1** | controller → gripper | **Close** | 1 = close |
| **DO_2** | controller → gripper | **Open** | 1 = open |
| **AI_1** | gripper → controller | **Finger position** (0–10 V, read as 0–4096) | 100–160 open · 4100–4200 closed on nothing (noise ±50) · in between while moving or holding |
| **DI_1** | sensor → controller | **Something below the gripper** | 1 = object, 0 = nothing; never set by an object held between the fingers |
| DI_2 | | not connected | always 0 |
| AI_2 | | not connected | ~489 (floating input) |

### AI_1 and the finger gap

The gap is linear in AI_1 between fully open and closed on nothing; `gripper.gap_mm(ai, where)` gives the width at the tips, belly, neck or shank, and `state()["gap_mm"]` is the belly gap. Plastic cups give a little, so their gap reads somewhat under their real diameter. The value right after closing overshoots: read it about 1 s after the close.

### Behaviour

- One stroke (open → closed or back) takes about **1 s**.
- **The fingers stay where they are when both outputs are off.** No signal is needed to keep holding.
- **Never switch both outputs on at the same time** (open and close together). Switch the other output off first.
- Closing on an object stops the fingers early and AI_1 stays lower (a cup's wide part: about 3500).
- Small or soft objects give no reliable reading: a thin plastic cup gripped at its narrow end gives way and reads like empty (~4150). Paper cups are squeezed flat and then read as empty.
- **A close cannot be stopped half way**: switching DO_1 off during the stroke does not stop the fingers. A gentler close from software is not possible with these outputs.
- The fingers have no touch sensing, and a pull on a held object does not change AI_1 beyond the settling noise: the gripper cannot detect a hand-over.

### PNP and NPN

- **PNP** ("sourcing"): the signal wire is connected to **+24 V** when the signal is on. Common on European equipment (Zimmer, Sick, Festo).
- **NPN** ("sinking"): the signal wire is connected to **0 V (ground)** when the signal is on. Common on Japanese and Chinese equipment.

Both ends of a signal must use the same type; otherwise nothing is read.

---

## 3. Software

`robot/gripper.py` drives the gripper through the arm controller's JSON command port (192.168.10.90:10001, no SDK):

```bash
python robot/gripper.py     # {'closed': ..., 'holding': ..., 'object_in_front': ..., 'ai': [...], 'do': [...], 'di': [...]}
python robot/gripper.py open
python robot/gripper.py close
```

```python
from robot import gripper
gripper.state()["object_in_front"]   # DI_1
gripper.close()                      # DO_2 off, DO_1 on, wait MOVE_S, return state()
gripper.state()["holding"]           # closed and AI_1 below EMPTY_AI
gripper.open_()
```

| Constant | Value | Meaning |
|---|---|---|
| `CLOSE_DO`, `OPEN_DO` | 0, 1 | DO_1, DO_2 (0-based index) |
| `CLOSED_AI` | 400 | AI_1 above this = closed |
| `EMPTY_AI` | 3900 | closed and above this = nothing between the fingers |
| `GAP_MM` | see §1 | inner gap (open, closed) at tips, belly, neck, shank |
| `SENSOR_DI` | 0 | DI_1 |
| `MOVE_S` | 1.5 | s to wait for a stroke |

Raw command: `{"cmdName": "set_digital_output", "type": 1, "index": <0|1>, "value": <0|1>}` (type 1 = tool I/O). The state comes from `get_data` (`tio_dout`, `tio_din`, `tio_ain`).

The API exposes `GET /gripper/state`, `POST /gripper/open`, `POST /gripper/close` (open / close are refused with 409 while a task runs); the dashboard Arm tab has Open / Close buttons and the live state. During a hand-over Lumi opens only on "thank you" or the dashboard's Release.

---

## 4. Payload and TCP

Settings → Payload, slot **`zimmer_gripper`**, selected as the active payload:

| Field | Value | Basis |
|---|---|---|
| Load | **1.000 kg** | estimate: gripper 0.54 kg (datasheet) + steel fingers and brackets |
| Centre of mass | **X 30, Y 0, Z 80 mm** | estimate: fingers on the +X side of the flange, heavy body close to the flange |

"One-click Auto Identification" is not available: it returns error `0x0F0088` "Payload identification only be supported in floor-mounting", and the Lumi arm is side-mounted (Mounting Orientation Y 90°, do not change it). The payload is entered by hand.

The TCP offset is kept in the Lumi code (camera calibration and the grasp point), not in Cobo π.

The collision limits are at the loose defaults (force 100 %, TCP speed 5000 mm/s, momentum 10 kg·m/s, power 600 W, stop distance 4000 mm). Tighten them before the arm works near people, in small steps, checking that normal motions still pass.

---

## 5. Other gripper options on Lumi (vendor material)

JAKA's education kit uses a **DH Robotics DH-PGEA-50** with 3D-printed fingers, driven over **Modbus RTU (RS485)**. The tool connector's DO pins can be switched to RS485 channel 1 for this (Cobo π → I/O → Tool → DO_1 → "Reuse as RS485 channel 1"). Vendor settings: slave 1, 115200 baud, 8N1. Registers: `0x0100` initialise, `0x0101` force %, `0x0103` target position (0 closed … 1000 open), `0x0200` init state, `0x0201` grip state, `0x0202` position. The vendor demos also use a USB-RS485 adapter on the host (`/dev/DH_hand`) and DH AG-95 grippers through `pyDHgripper`. Sources: jaka-robot-demos `LUMI_DEMO-v3/.../dh_gripper.py`, JAKA_Lumi `LUMI_DEMO_BMW/LumiAgent/utilfs/python_open_gripper.py` (see [12_SOURCES.md](12_SOURCES.md)).

Arm-side limits for any gripper:

| Item | Value |
|---|---|
| Flange | ISO 9409-1, pitch circle 50 mm, 4 × M6, Ø6 H7 pin hole |
| Payload | 2 kg in total (gripper + object), less with a larger centre-of-mass offset |
| Tool power | 24 V or 12 V, 1 A continuous, 2 A peak |
| Tool DO | 2 × ≤ 1 A, NPN / PNP / push-pull |
| Tool AI | 2 × 0–10 V |
