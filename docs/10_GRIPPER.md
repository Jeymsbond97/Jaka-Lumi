# 10. Gripper

A Zimmer electric parallel gripper has been mounted on the arm flange since 2026-10-13. It is driven by the two digital outputs of the arm's tool connector and reports its finger position on an analog input. An optical sensor on one finger tells whether something is in front of the fingers.

Everything in sections 1–6 was measured or set on our robot. Section 7 lists the vendor's other gripper options for reference.

---

## 1. Hardware

| Part | What it is |
|---|---|
| Gripper | **Zimmer GEP2013IO-05-B** (label on the housing, serial 01-00061615): electric 2-jaw parallel gripper, digital I/O version. Datasheet values for the GEP2013 family: **13 mm stroke per jaw**, **gripping force 90–360 N** in four levels, **mass about 0.54 kg** without fingers. Rotary switch "Funct" 1–4 = force level (level 4 = 360 N); it is on **1**. Green LED = powered |
| Fingers | Long stainless-steel fingers with curved tips on L-shaped brackets, made for cups and glasses. Fingertips are about 265 mm from the flange face; the fingers sit beside the flange axis, not on it (about 8 cm off, estimated from photos) |
| Finger sensor | **MISUMI** optical (photoelectric) sensor, yellow/black housing, mounted on one finger and looking forward. The red light is its emitter and is always on. The indicator LED on its back turns red when something is in front of it and blue when nothing is |
| Cable | Gripper and sensor are both wired to the arm's M8 tool connector (TIO), see [04_ARM.md §8](04_ARM.md#8-tool-io-connector-m8-8-pin-tio-v3) |

The rotary switch sets the gripping force. Even level 1 (~90 N) is far more than a plastic cup needs: the software must not close on objects that cannot take it (see [15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md) §3.5).

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

### Pulling on a held cup (2026-10-15)

The arm at `give`, the white tumbler in the closed gripper, AI_1 read at 10 Hz for 45 s while the owner first did not
touch it, then pulled gently three times, then only held it.

| Phase | AI_1 median | AI_1 spread (sd) |
|---|---|---|
| Nobody touches it | 2831–2836 | 54–61 (sd 19–23) |
| Gentle pulls | 2779–2870 | 150–200 (sd 50–75) |
| Held, not pulled | 2816–2860 | 93–142 (sd 29–39) |
| The fingers settling just after a move (another run) | 2477 → 2285 within 1 s | |

A pull does not move the fingers, so AI_1 cannot tell it; the settling after a move is larger than a pull. Lumi opens
for a hand-over only on "thank you" or the dashboard's Release ([16_FETCH_TASKS.md](16_FETCH_TASKS.md)). On the four
live picks of 2026-10-15 AI_1 read 1870–2477 holding (the cup's height at the grasp point differs).

---

### Finger opening (measured with a ruler, 2026-10-13, fully open, AI_1 162)

The fingers are curved inward, so the gap is widest in the middle:

| Where | Gap |
|---|---|
| Entry at the fingertips | 88–89 mm |
| Middle (widest) | 100 mm |
| Innermost, near the brackets | 66 mm |

With 13 mm stroke per jaw, closing narrows each place by about 26 mm (middle ~74 mm), so a cup of 75–95 mm sits best in the middle of the fingers. An 82 mm cup passes the 88 mm entry with only ~3 mm per side: approach on the measured centre line.

### Grasp point (taught 2026-10-13)

The fingers were placed around a cup by hand (FREE button), the cup measured by the torso camera after lifting the arm
straight up. The point between the fingers where a cup's axis sits, 4 cm below the rim, is at **(106.4, −86.5, 230.5) mm
in the flange frame** (268 mm from the flange, 137 mm off its axis). Stored in `data/grasp_teach.json` with the flange pose.
First pick with it: the 82 mm LS metal cup moved 16 mm, the arm went 10 cm above, straight down, closed (AI_1 2189),
lifted 30 mm (AI_1 2270–2310, stable), put it back within 1 mm. The finger sensor DI_1 stayed 0 the whole time:
it does not see a cup held at this point (to check where it looks).

## 4. Software

`real/thor/robot/gripper.py` drives the gripper through the arm controller's TCP command port (192.168.10.90:10001, JSON, no SDK):

```bash
python robot/gripper.py     # {'closed': ..., 'holding': ..., 'object_in_front': ..., 'ai': [...], 'do': [...], 'di': [...]}
python robot/gripper.py open
python robot/gripper.py close
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

`open` / `close` in `gripper.py` were first run from the Thor on 2026-10-13: open read AI_1 162 with DO `[0, 1]`, close read AI_1 4116 (empty) with DO `[1, 0]`. The API exposes them as `GET /gripper/state`, `POST /gripper/open`, `POST /gripper/close` (refused with 409 while `lumi.py` runs); the dashboard has Open / Close buttons and a live state in the Arm tab.

---

## 5. Payload in Cobo π

Set 2026-10-13 in Settings → Payload, slot **`zimmer_gripper`**, selected as the active payload:

| Field | Value | Basis |
|---|---|---|
| Load | **1.000 kg** | estimate: gripper 0.54 kg (datasheet) + steel fingers and brackets |
| Centre of mass | **X 30, Y 0, Z 80 mm** | estimate from photos: fingers on the +X side of the flange, heavy body close to the flange |

"One-click Auto Identification" refuses with error `0x0F0088` "Payload identification only be supported in floor-mounting": the Lumi arm is side-mounted (Mounting Orientation Y 90°, do not change it), so the payload has to be entered by hand.

The collision limits shown with it are still the loose defaults (force 100 %, TCP speed 5000 mm/s, momentum 10 kg·m/s, power 600 W, stop distance 4000 mm). Tighten them before the arm works near people, in small steps, checking that normal motions still pass.

---

## 6. Still to do

| Item | Why |
|---|---|
| Download the GEP2013IO-05-B operating manual | Confirm stroke, force per switch level and the AI_1 output scaling |
| Weigh the complete tool (gripper, fingers, brackets, plate, sensor) and correct the payload | The payload is set from an estimate, see below |
| TCP offset | Kept in our code, not in Cobo π, and measured during the camera calibration (the fingers are off the flange axis, a tape measure is not accurate enough) |
| Calibrate AI_1 against finger opening in mm | So that the vision system can check whether an object fits (see [15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md)) |
| Teach the finger sensor's range | It decides when the gripper is close enough to an object to close |
| A hand-over signal | AI_1 cannot feel a pull (§3); a force reading or a touch sensor would let Lumi open when the person takes it |

---

## 7. Other gripper options on Lumi (vendor material)

JAKA's education kit uses a **DH Robotics DH-PGEA-50** with 3D-printed fingers, driven over **Modbus RTU (RS485)**. The tool connector's DO pins can be switched to RS485 channel 1 for this (Cobo π → I/O → Tool → DO_1 → "Reuse as RS485 channel 1"). Settings in the vendor code: slave 1, 115200 baud, 8N1. Registers: `0x0100` initialise, `0x0101` force %, `0x0103` target position (0 closed … 1000 open), `0x0200` init state, `0x0201` grip state, `0x0202` position. The vendor demos also use a USB-RS485 adapter on the host (`/dev/DH_hand`) and DH AG-95 grippers through `pyDHgripper`. Sources: jaka-robot-demos `LUMI_DEMO-v3/.../dh_gripper.py`, JAKA_Lumi `LUMI_DEMO_BMW/LumiAgent/utilfs/python_open_gripper.py` (see [12_SOURCES.md](12_SOURCES.md)).

Arm-side limits for any gripper:

| Item | Value |
|---|---|
| Flange | ISO 9409-1, pitch circle 50 mm, 4 × M6, Ø6 H7 pin hole |
| Payload | 2 kg in total (gripper + object), less with a larger centre-of-mass offset |
| Tool power | 24 V or 12 V, 1 A continuous, 2 A peak |
| Tool DO | 2 × ≤ 1 A, NPN / PNP / push-pull |
| Tool AI | 2 × 0–10 V |
