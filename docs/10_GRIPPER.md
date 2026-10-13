# 10. Gripper

A Zimmer electric parallel gripper has been mounted on the arm flange since 2026-10-13. It is driven by the two digital outputs of the arm's tool connector and reports its finger position on an analog input. An optical sensor on one finger tells whether something is in front of the fingers.

Everything in sections 1–5 was measured on our robot. Section 6 lists the vendor's other gripper options for reference.

---

## 1. Hardware

| Part | What it is |
|---|---|
| Gripper | Zimmer (zimmer-group.com) electric two-finger parallel gripper, probably GEP2000 series (the exact model is still to read from the label). Rotary switch "Funct" 1–4 on the housing; green LED = powered |
| Fingers | Long stainless-steel fingers with curved tips, about 15 cm, made for cups and glasses |
| Finger sensor | Small optical (photoelectric) sensor with a yellow/black housing, mounted on one finger and looking forward. The red light is its emitter and is always on. The indicator LED on its back turns red when something is in front of it and blue when nothing is |
| Cable | Gripper and sensor are both wired to the arm's M8 tool connector (TIO), see [04_ARM.md §8](04_ARM.md#8-tool-io-connector-m8-8-pin-tio-v3) |

The rotary switch selects the gripper's operating function. Its exact meaning (grip force or mode) is in the Zimmer manual for the model; it was left at the position it was delivered in.

---

## 2. Signals

| Signal | Direction | Meaning | Values measured |
|---|---|---|---|
| **DO_1** | controller → gripper | **Close** | 1 = close |
| **DO_2** | controller → gripper | **Open** | 1 = open |
| **AI_1** | gripper → controller | **Finger position** (analog, 0–10 V, read as 0–4096) | ~160 open · 4100–4200 closed on nothing · ~3500 closed on a cup's wide part · in between while moving |
| **DI_1** | sensor → controller | **Object in front of the fingers** | 1 = object, 0 = nothing |
| DI_2 | | not connected | always 0 |
| AI_2 | | not connected | constant ~489 (floating input) |

**All tool I/O must be set to PNP.** In Cobo π → I/O → Tool(S), open the ⋮ menu of each DI / DO and choose PNP. With the factory setting NPN the gripper does not move and the sensor is not read.

### PNP and NPN

Both describe how a digital signal is switched:

- **PNP** ("sourcing"): the signal wire is connected to **+24 V** when the signal is on. Common on European equipment (Zimmer, Sick, Festo).
- **NPN** ("sinking"): the signal wire is connected to **0 V (ground)** when the signal is on. Common on Japanese and Chinese equipment.

Both ends of a signal have to use the same type. If one side expects PNP and the other sends NPN, nothing is read.

### Behaviour

- One stroke (open → closed or back) takes about **1 s**.
- **The fingers stay where they are when both outputs are off.** The gripper does not need a signal to keep holding.
- **Never switch both outputs on at the same time.** That commands open and close together. Always switch the other output off first.
- A closed gripper holding nothing reads 4100–4200 on AI_1, with about ±50 noise. When it closes on an object, the fingers stop earlier and AI_1 stays lower. In the cup test, the wide part of a cup stopped the fingers at ~3500.
- A small or soft object gives no reliable reading. A thin plastic cup gripped at its narrow end gave way, and the fingers closed fully (~4150) as if nothing were there.

---

## 3. Test log (2026-10-13)

The controller's `get_data` was polled every 0.3 s while the outputs were switched by hand in Cobo π.

| Test | Result |
|---|---|
| DO_1 / DO_2 with NPN | Outputs switched, gripper did not move |
| DO_1 / DO_2 with PNP | Gripper closes on DO_1 and opens on DO_2, 7 of 7 times |
| Hand in front of the sensor, inputs PNP | DI_1 = 1 while the hand is there, 0 when it is gone; more than 10 times, with the gripper open and closed |
| Hand between the fingers (touching) | Nothing changes: the fingers have no touch sensing |
| Close on a cup, wide part | AI_1 stopped at 3480–3560 (empty: 4090–4200) |
| Close on a cup, narrow part (3 times) | AI_1 4100–4200: the cup gave way, reads like empty |

---

## 4. Software

`real/thor/gripper.py` drives the gripper through the arm controller's TCP command port (192.168.10.90:10001, JSON, no SDK):

```bash
python gripper.py            # {'closed': ..., 'holding': ..., 'object_in_front': ..., 'ai': [...], 'do': [...], 'di': [...]}
python gripper.py open
python gripper.py close
```

```python
import gripper
gripper.state()["object_in_front"]   # DI_1
gripper.close()                      # DO_2 off, DO_1 on, wait ~1.5 s, return state()
gripper.state()["holding"]           # closed and AI_1 below EMPTY_AI (3900)
gripper.open_()
```

| Constant | Value | Meaning |
|---|---|---|
| `CLOSE_DO`, `OPEN_DO` | 0, 1 | DO_1, DO_2 (0-based index) |
| `CLOSED_AI` | 2000 | AI_1 above this = closed |
| `EMPTY_AI` | 3900 | closed and above this = nothing between the fingers |
| `SENSOR_DI` | 0 | DI_1 |
| `MOVE_S` | 1.5 | s to wait for a stroke |

The raw command is `{"cmdName": "set_digital_output", "type": 1, "index": <0|1>, "value": <0|1>}` (type 1 = tool I/O). The state comes from `get_data` (`tio_dout`, `tio_din`, `tio_ain`).

`open` / `close` in `gripper.py` have not been run yet: so far the outputs were only switched from Cobo π. The first run should be watched, with nobody's hands near the fingers.

---

## 5. Still to do

| Item | Why |
|---|---|
| Read the model number from the label and download its manual | Stroke, grip force, the "Funct" switch, the meaning of the AI_1 output |
| Weigh the gripper and fingers, set **payload** and **TCP** in Cobo π | The arm's collision detection and dynamics need the real tool mass. TCP = the point between the fingertips |
| Calibrate AI_1 against finger opening in mm | So that the vision system can check whether an object fits (see [15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md)) |
| Teach the finger sensor's range | It decides when the gripper is close enough to an object to close |

---

## 6. Other gripper options on Lumi (vendor material)

JAKA's education kit uses a **DH Robotics DH-PGEA-50** with 3D-printed fingers, driven over **Modbus RTU (RS485)**. The tool connector's DO pins can be switched to RS485 channel 1 for this (Cobo π → I/O → Tool → DO_1 → "Reuse as RS485 channel 1"). Settings in the vendor code: slave 1, 115200 baud, 8N1. Registers: `0x0100` initialise, `0x0101` force %, `0x0103` target position (0 closed … 1000 open), `0x0200` init state, `0x0201` grip state, `0x0202` position. The vendor demos also use a USB-RS485 adapter on the host (`/dev/DH_hand`) and DH AG-95 grippers through `pyDHgripper`. Sources: jaka-robot-demos `LUMI_DEMO-v3/.../dh_gripper.py`, JAKA_Lumi `LUMI_DEMO_BMW/LumiAgent/utilfs/python_open_gripper.py` (see [12_SOURCES.md](12_SOURCES.md)).

Arm-side limits for any gripper:

| Item | Value |
|---|---|
| Flange | ISO 9409-1, pitch circle 50 mm, 4 × M6, Ø6 H7 pin hole |
| Payload | 2 kg in total (gripper + object), less with a larger centre-of-mass offset |
| Tool power | 24 V or 12 V, 1 A continuous, 2 A peak |
| Tool DO | 2 × ≤ 1 A, NPN / PNP / push-pull |
| Tool AI | 2 × 0–10 V |
