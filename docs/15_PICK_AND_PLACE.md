# 15. Pick and place by voice: design and plan

Goal: a visitor says *"Lumi, find the red cup, take it and put it here"* (or *"bring me the blue apple"*, *"open your hand"*), and the robot does it on its own. It finds the object with its camera and works out where it is, how big it is and whether the gripper can hold it. It sets lift, waist, base and arm so the object is in reach, grips it with the right width, checks that it really holds it, carries it and puts it down. If something is impossible (out of reach, too small, too big, not found), it says so instead of trying.

This page is the agreed plan. Work through the stages in order; each ends with a test on the robot. Status is tracked in [ROADMAP.md](ROADMAP.md).

---

## 1. Principles

1. **The LLM decides *what*, deterministic code decides *how*.** The language model turns speech into a task (`pick red cup`, `place here`). It may also pick one object out of several candidates in a camera image. It never produces joint angles, coordinates or speeds. Geometry, reach checks, motion and grip checks are ordinary code with fixed limits.
2. **Check before moving.** Every motion is checked against reach, joint limits and the known obstacles (column, base, table, head) before it is sent. A task that fails a check is refused with a spoken reason.
3. **Measure, then trust.** Every number the planner uses comes from a measurement on this robot: camera extrinsics, gripper opening, table height, finger-sensor range. Section 7 lists them.
4. **Slow and stoppable.** Arm speeds stay low near objects and people. The dashboard STOP and the voice "stop" interrupt any stage. The controller's collision detection stays on with the real payload set.
5. **One skill, many callers.** `pick`, `place`, `give` and `open/close` are Python functions. The voice assistant, the API (`/skills/*`, Swagger) and the dashboard all call the same ones.

---

## 2. What the robot has to work with

| Part | Fact | Source |
|---|---|---|
| Arm | JAKA Mini 2 on the right side of the column, 6 joints, **reach 580 mm**, payload 2 kg incl. gripper | [04_ARM.md](04_ARM.md), [01_HARDWARE.md](01_HARDWARE.md) |
| Lift | 0–300 mm (body API) | [03_BODY_LIFT_WAIST_HEAD.md](03_BODY_LIFT_WAIST_HEAD.md) |
| Waist | ±140° | same |
| Base | differential drive; short moves through `joy_control` / `move?location` | [05_AGV_BASE.md](05_AGV_BASE.md) |
| Torso camera | Orbbec Gemini 2 L on the waist link, colour + depth (USB 3), turns with the waist | [06_CAMERAS_AND_VISION.md](06_CAMERAS_AND_VISION.md) |
| Head camera | colour only (it resets when depth and the speaker run together) | same |
| Gripper | Zimmer, DO_1 close / DO_2 open, AI_1 finger position, DI_1 finger sensor | [10_GRIPPER.md](10_GRIPPER.md) |
| Robot model | URDF + MuJoCo model in `sim/`. Forward kinematics agrees with the real arm within ~1 mm (415.1 vs 416.0 mm) | [04_ARM.md §4](04_ARM.md#4-joint-space-urdf--sdk-high-confidence), [SIMULATION.md](SIMULATION.md) |
| Compute | Jetson Thor: YOLOv8n on CPU (~14 fps), Ollama `gemma4:e4b` (text + images), whisper.cpp on GPU | [08_NVIDIA_THOR.md](08_NVIDIA_THOR.md) |

The MuJoCo model is used as the robot's **planning model**: inverse kinematics, reach checks and collision checks run against it before a motion goes to the real arm. That is the reason the simulation was built with the real link geometry and limits.

---

## 3. Pipeline

```
speech ──> intent (LLM + rules) ──> task            "pick red cup" / "place here" / "give to me"
                                       │
camera (torso, colour+depth) ──> detect ──> choose (rules, or LLM on the image) ──> object
                                                                                     │
         object 3D: position, size, top height, shape  <── depth + camera extrinsics ┘
                                       │
         feasibility: fits the gripper? within reach (lift / waist / base)? clear of obstacles?
                                       │   no ──> say why, stop
         plan: base move → lift → waist → approach pose → grasp pose → lift-off pose   (checked in the model)
                                       │
         execute: move, open, approach, sensor sees it?, close, AI_1 says holding?, lift, still holding?
                                       │   no ──> open, back off, say why (retry once if it makes sense)
         carry (arm tucked close) ──> place / give ──> open ──> back off ──> tuck
```

### 3.1 Intent

New voice actions next to the existing ones in `brain.py` (rules first, LLM for everything else):

| Action | Examples | Result |
|---|---|---|
| `hand open` / `hand close` | "open your hand", "close the gripper", "손 펴" | gripper only |
| `pick <object>` | "take the red cup", "pick up the blue apple", "grab that bottle" | find + grasp |
| `place <where>` | "put it here", "put it on the table", "put it next to the laptop" | place what it holds |
| `give` | "give it to me", "bring it to me" | hand over to the person speaking |
| `fetch <object> [to <where>]` | "find the red cup and bring it here" | pick, then place / give |

The object description is kept as text (`red cup`, `blue apple`) plus parsed fields: class (`cup`), colour (`red`), relation (`left of the laptop`). "Here" and "me" resolve to the person who spoke (voice direction + camera, already in `lumi.py`).

### 3.2 Find the object

1. **Detect**: YOLOv8n already runs for people. Its COCO classes include `cup`, `bottle`, `wine glass`, `bowl`, `apple`, `banana`, `orange`, `cell phone`, `book` and more, so the same model gives object boxes.
2. **Colour**: the dominant HSV hue inside the box (masked by depth so that the background does not count) gives `red`, `blue`, and so on.
3. **Choose**: one match → take it. Several, or a class YOLO does not know → send the colour image with numbered boxes to `gemma4` and ask which number fits the description ("the red cup on the left"). It answers with a number, never with coordinates.
4. **Not found** → turn the waist / head to search the table area once, then say "I can't see a red cup".

If COCO classes turn out too narrow, add an open-vocabulary detector (YOLO-World or Grounding DINO, ONNX on the GPU) behind the same `detect()` interface.

### 3.3 Measure it

From the aligned depth inside the object mask:

- **3D position** of the object's centre and top, first in the camera frame, then in the arm base frame through the camera extrinsics (section 7).
- **Size**: width across the grasp direction, height above the table, footprint. **Shape class**: upright cylinder (cup, bottle, can), round (apple, ball), box, flat. The class sets the grasp: side grasp at the widest stable height for cylinders, from above or the side at the equator for round objects, top grasp for low boxes.
- **Support surface**: fit a plane to the depth points around the object: table height and its edge. Objects are only picked from a surface, not from someone's hand.

### 3.4 Feasibility checks (before any motion)

| Check | Rule | Spoken reason when it fails |
|---|---|---|
| Fits the gripper | grasp width < max finger opening − margin | "It's too big for my hand." |
| Not too small | grasp width > minimum width that gives a measurable AI_1 stop | "It's too small for me to hold." |
| Weight | estimated class weight + gripper ≤ payload | "It's too heavy for me." |
| Reach | IK solution in the model for approach, grasp and lift-off poses, with joint margins | handled by repositioning, below |
| Clearance | approach and grasp poses collide with nothing in the model (table plane as a box, column, base, head) | "I can't reach it safely." |

**Repositioning** when the object is out of reach, cheapest first:
1. **Waist** turn so that the arm side faces the object.
2. **Lift** so that the arm base height suits the object's grasp height (table top vs. low shelf).
3. **Base**: a short move toward or along the table, at most ~0.5 m, only on the map's free space, and stopping at a set distance from the table edge. Then measure again: the object position is always taken fresh after the robot moves.

### 3.5 Grasp and verify

1. Tuck → (base, lift, waist) → **open** the gripper.
2. **Approach pose**: 10 cm before the grasp pose along the approach direction. Joint move, slow.
3. **Linear move** in to the grasp pose, slower. The finger sensor (DI_1) looks below the gripper, not between the fingers, so it cannot confirm the object before the close (docs/10).
4. **Close.** Read **AI_1** after the stroke:
   - near the fully closed value → **missed** or **too small / too soft**: open, back off, report.
   - stopped where the measured object width predicts (± tolerance) → **holding**.
   - stopped far wider than expected → grabbed something else (an edge, the table): open and back off.
5. **Lift off** 3–5 cm straight up, read AI_1 and DI_1 again: still holding? Otherwise put back down and report a slip.
6. Carry with the arm close to the body. Hold low and slow while the base drives.

Grip force cannot be set from software with digital outputs. It comes from the gripper's own setting ("Funct" switch). The software side of "not too hard" is: never close on something narrower than the measured width predicts, and refuse objects classed as fragile unless the force setting is known to be safe for them.

### 3.6 Place and give

- **"Put it here" / "on the table"**: find free space on the support plane near the speaker (or next to the named object), at least the object's footprint plus a margin from other objects and the edge. Lower until the object is ~1 cm above the surface, open, back off up, tuck.
- **"Give it to me"**: turn to the person who spoke and hold the object at chest height ~40 cm in front of the robot. Open when the person takes it (a pull on the arm or the object leaving the finger sensor) or after they say "okay / got it". Then tuck.

---

## 4. Software layout

New modules in `real/thor/` (same style as the existing ones: one job each, runnable alone):

| Module | Job |
|---|---|
| `robot/gripper.py` | open / close / state (done) |
| `vision/objects.py` | (done) detect objects in the torso camera, colour, choose one (rules / LLM on the image), 3D position and size from depth |
| `vision/calib.py` | camera → arm-base extrinsics (ArUco on the gripper, still arm poses moved by hand in Cobo π, Park & Martin AX = XB), saved to `data/camera_extrinsics.json` (done, see §8) |
| `manipulation/reach.py` | planning model: loads the MuJoCo model from `sim/`, IK with joint margins, collision check, chooses lift / waist / base for a target |
| `robot/motion.py` | sends checked joint and linear moves to the arm (controller TCP 10001), slow presets, stop (done, see [04_ARM.md §10](04_ARM.md)) |
| `manipulation/skills.py` | (pick / place / move of one named object done 2026-10-13: `python manipulation/skills.py plan|pick|move cup [--to X Y]`) `pick(description)`, `place(where)`, `give()`, `fetch(...)`: the sequences above, each step logged and stoppable |

`assistant/lumi.py` gets the new actions and speaks the results. `api/server.py` gets `/gripper/*`, `/objects` (what the camera sees, with sizes), `/skills/plan|move|pick|place` and `/skills/state` (skills run in the background; STOP and `/arm/stop` end them through `skills.cancel()`), later `/skills/give`. The dashboard gets gripper buttons, an object overlay on the torso camera and a Pick and place section (Check plan, Move it, Stop).

---

## 5. Stages

Each stage ends with a test on the robot; the next starts only when it passes.

| # | Stage | Done when |
|---|---|---|
| P0 ✅ | **Gripper basics**: `gripper.py` run from the Thor; `/gripper/open|close|state` in the API; dashboard buttons; voice "open / close your hand" | The gripper opens and closes from voice and the dashboard; state shown live |
| P1 | **Gripper measurements**: model number and manual, mass → payload and TCP in Cobo π, AI_1 vs finger opening (mm) table, minimum holdable width | Opening in mm from AI_1 within ±3 mm |
| P2 ✅ | **Arm motion from code**: checked joint and linear moves (`motion.py`), tuck / ready / reach poses, speed presets, stop | Arm moves to named poses from the API and stops on STOP |
| P3 ✅ | **Camera extrinsics**: ArUco on the gripper, `calib.py` | A point seen by the camera maps to the arm base frame within ±10 mm |
| P4 ✅ | **Objects**: `objects.py` detects, colours, measures; `/objects` and a dashboard overlay | Cup / apple / bottle on a table: position ±1 cm, width ±5 mm |
| P5 🟡 | **Reach planning**: `reach.py` with the MuJoCo model, lift / waist / base choice, clearance checks. Done on the robot without the model: grasp turned about the vertical (0…±60°), lift to the table's height (measured with depth), base shift, search by turning on the spot (`skills.py`, `tasks/fetch.py`, [16](16_FETCH_TASKS.md)) | For objects on the table, the plan says reachable or not reachable and why, and agrees with the real arm in 10 test placements |
| P6 🟡 | **Pick**: `skills.pick` with sensor and AI_1 checks, failure handling. Live by fetch 2026-10-15: 4 of 4 grasps held (one from a box 12 cm higher, lift 193 mm) | 8 of 10 picks of a cup at different positions; every failure detected and reported |
| P7 🟡 | **Place and give**: free-space search, hand-over. Live 2026-10-15: put down upright on the table and on the box (seen-table spots, lift fitted); hand-over opens only on "thank you" / Release (AI_1 can't feel a pull), Release not yet run live. 2026-10-20 on a round table 1–5 cm lower than the proven one (lift at 0) no place spot was ever found after the base drove up to it: the grid's near rows were below the camera's view and the table, read "sink", counted as an obstacle; changed offline ([16](16_FETCH_TASKS.md) step 9), not yet live | Objects placed upright within ±2 cm; hand-over works with a person |
| P8 🟡 | **Voice**: intents, object choice by the LLM on the image, spoken progress and reasons. Done in code: "pick up the (colour) cup", "move the cup", "put it down / back" (rules + LLM action), API `/skills/*`, dashboard button; not yet run live. Still open: choice among several objects by the LLM, "put it here" | "Find the red cup and put it here" works end to end with two cups on the table |
| P9 🟡 | **Fetch with driving**: go to a marker, pick there, come back, give. Live 2026-10-15: drove with the cup towards p6, the base stalled on the way (cancelled), the cup stayed held | A cup is fetched from another table and handed over |

---

## 6. Safety rules for this work

- The arm moves only when the controller has the **real payload** set and collision detection is on ([11_SAFETY.md](11_SAFETY.md)).
- The first run of every new motion is at low speed, watched, with a hand on the STOP.
- Nobody's hands near the fingers when code closes the gripper.
- The base never drives with the arm reaching out. Tuck first, then drive.
- The planner refuses targets closer than a margin to the column, base, head, the table plane and the person.

---

## 7. Measurements this plan depends on

| What | How | Used by |
|---|---|---|
| Max finger opening and AI_1 → mm | close on gauge blocks / measure with a caliper at several AI_1 values | fit check, grip check |
| Minimum holdable width | close on rods of decreasing diameter | "too small" |
| Gripper + finger mass, centre of mass | scale; CAD or balance | payload, reach (2 kg limit) |
| TCP (fingertip centre) | measure from the flange | every arm target |
| Torso camera → arm base transform | `calib.py` | object position |
| Finger sensor range | move a cup toward it, note DI_1 switching distance | "close now" condition |
| Arm base position vs. lift / waist | from the URDF; verify with a few poses | reach planning |

---

## 8. Camera calibration (P3) results

Method: ArUco DICT_4X4_50 id 0, 50 mm, glued on the flat black face of the gripper body (the face with two holes). The arm is moved by hand in Cobo π; `calib.py collect` saves a sample whenever the joints are still for 1.5 s, the marker is in view and the pose differs from earlier samples (Lumi says "Saved, N"). `calib.py solve` fits camera-in-base and marker-on-flange (Park & Martin AX = XB, then Levenberg-Marquardt on the marker centre, then once more without samples off by more than 3× the median) and reports, for each sample, how far apart the marker is when seen by the camera and when placed by the arm.

Findings:
- The controller's `actual_position` angles are fixed X-Y-Z roll-pitch-yaw in degrees (R = Rz·Ry·Rx): median error 4.1 mm, against 97 mm for the other order (before refinement).
- The arm does not reach farther than ~48 cm from the camera with the marker facing it, so that is the far end of the samples. Error by distance (refined, before leaving out): 3.9 mm under 40 cm, 4.3 mm at 40–48 cm.
- Torso colour intrinsics at 1280×720 (factory): fx 608.3, fy 608.4, cx 636.9, cy 363.2, 8 distortion coefficients (rational model). Written by the camera service to `/dev/shm/lumi_intr_torso.json`.
- The camera service may start before a camera re-enumerates after `--stop`; it then reports `camera 'torso' not found`. Start it again.

| Date | Samples | Marker distance | Median / max error | Camera in arm base (mm) | Marker on flange (mm) |
|---|---|---|---|---|---|
| 2026-10-13 (first) | 20 | 215–355 mm | 4.1 / 10.9 mm | (−242.8, 4.5, −40.0) | (−16.5, 4.0, 40.4) |
| **2026-10-13 (in use)** | 30, 2 left out | 215–484 mm | **3.3 / 7.5 mm** | (−257.7, 13.7, −41.4) | (−20.0, −6.9, 44.6) |

Lift and waist were not moved during the session. The lift does not change it: lift 75 → 150 mm moved a cup x +2, y −2, top −76 mm (2026-10-15; the camera sits on the arm's link).

### Head camera (2026-10-19)

Same marker and solver, `calib.py --camera head` (samples `data/calib_samples_head/`, result
`data/camera_extrinsics_head.json`, with the body pose of the session). 30 samples at lift 0, waist −20.3°, head yaw 0°,
pitch −5°: median 6.0 mm, max 14.2 mm; live check 8–16 mm at 5 arm positions. The head's yaw and pitch axes were
then measured in the arm base frame with the arm holding the marker still (`vision/head_cam.py measure yaw|pitch`,
yaw −30…0°, pitch −5…+4°, then `fit`): the model is within 11 mm / 1.4° of every pose seen.
`head_cam.base_from_head(yaw, pitch)` gives the camera pose at any head pose (outside the measured range
extrapolated); lift and waist carry the arm and the head together. Cross-check: a potted plant seen by both cameras
came out 13 mm apart at head yaw +10°. Values: [06 §3](06_CAMERAS_AND_VISION.md).

The camera service writes head depth (`/dev/shm/lumi_depth_head.npy`) and measures head-camera objects in the arm
frame too (`objects.latest("head")`, each with the `head_pose` it was seen at); `objects.measure_all` takes the
intrinsics and the transform, `skills.surface_points` the camera and the transform.

### Base axis (measure-axis) again (2026-10-19)

Arm yaw in the base frame with `tasks/fetch.py measure-axis` at waist −20.31°, two white cups on a table: −96.4,
−94.9, −95.5° over three runs; kept −95.5° (median) in `data/fetch_calib.json` with `waist_deg` −20.31. One more run
gave −136.4°: it had paired both cups with one; `_pairs` now matches each object once, nearest first over all pairs.
A run with only a bowl (low score) gave −89.1°, not kept. The arm offset (0.114, −0.104) m from 2026-10-16 is kept.
It replaces −86.2° (2026-10-14, no waist angle recorded). Fetch corrects the yaw and the offset by the waist turn
since measure-axis (`fetch._waist_turn`; the waist axis is taken at the base centre).

## 9. Grip widths (2026-10-19)

Finger shape and inner gaps: [docs/gripper/](gripper/README.md); AI_1 → gap: [10 §2.1](10_GRIPPER.md). The camera's
width of a cup reads about 8 mm under the width the fingers meet (white tumbler: camera 72–74 mm, circumference
26.5–26.8 cm → 84–85 mm; red cup: camera 81 mm, gripper ~85 mm), so `skills.grip_width()` = camera width +
`SEEN_UNDER_MM` (8) is compared with the limits:

| Constant (`manipulation/skills.py`) | Value | Why |
|---|---|---|
| `MIN_WIDTH`, `MAX_WIDTH` | 61, 92 mm | belly opens to 96, tips close to 59; the tips open only to 88, so over 84 is the owner's call and not tried live |
| `BELLY_MIN_MM` | 72 mm | thinner is held between the tips (the belly closes only to 70) |
| `TIPS_GRASP_MM` | 0 mm | a tips grasp at the normal height; 25 mm higher left the tips at the rim and they closed on nothing |
| `TIP_MM` | 60 mm | finger tips beyond the grasp point along the fingers (`FINGER_DIR`: they point down in the grasp, not along the flange z); used by `path_heights` and `fetch.arm_points_3d` |

Picks with `skills.py pick` (owner at the STOP):

| Object | Camera width | Result |
|---|---|---|
| white tumbler | 72–74 mm (84–85 real) | picked (AI_1 2265 holding), put back |
| red cup | 81 mm (~85 by the gripper) | picked (AI_1 1764), put back |
| small steel cup / steel bowl | 61–74 mm, position spread up to 17 mm (shiny) | knocked over once by a finger, refused once ("keeps changing"), missed once |
| paper cup | 59–63 mm | missed 3 times: 25 mm higher (tips at the rim), at the normal height, then squeezed flat when taught by hand |

Shiny metal gives unstable depth (width and position jump between frames). Paper cups are crushed by the close,
which cannot be stopped half way (docs/10): they need another force setting or other fingers.
