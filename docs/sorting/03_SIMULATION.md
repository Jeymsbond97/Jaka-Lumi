# 03 Simulation

Two simulators, one scene. Isaac Lab trains the policy; MuJoCo replays the same policy to check it does not depend
on one engine's quirks. Both are built from the same robot description and the same numbers ([01](01_HARDWARE_FACTS.md)).

---

## 0. What exists (MuJoCo, `sim/sorting/`)

| File | Contents |
|---|---|
| `build.py` | writes `sorting.xml`: the scene in the arm controller's base frame (m, z up). Arm joints from the fitted kinematics (`data/arm_kinematics.json`), so a joint's qpos is the controller's angle; JAKA's MiniCobo meshes placed with the Lumi app's link chain (within 1.3 mm of the fitted links); torso, lift, head and base from the vendor URDF at lift 0; the torso camera from its hand-eye calibration; the Zimmer with the straight fingers (jaws coupled, 13 mm stroke, 90 N); table, tray, two boxes, six balls. The Zimmer hangs off the flange across its axis and the fingers run out along it, as on the robot (checked against the owner's photo of the `look` pose; a flange pose read from the robot lands within a millimetre in the simulation) |
| `app_look.py` | the look: the Lumi app's own 3D model (`assets/lumi_app.glb`, the uncompressed export of Lumi-app `tools/lumi-model`) cut into one mesh per link and colour, in that link's frame: white shell, black trim and visor, red bands, green shoulder ring, JAKA lettering, the cutshion logo, the cameras and the base lamp. The meshes are made once into `assets/app_cache/` (not in git) and need `trimesh` and `pillow` (`requirements.txt`) |
| `check.py` | the simulated flange against the controller's own flange pose in the 60 calibration samples: **median 0.02 mm, max 0.03 mm, 0.008°**; pictures from three cameras |
| `scripted_demo.py` | a scripted sort (inverse kinematics and waypoints, no learning): the fingers as straight down as reachable (at most 45°) at each ball, straight up, then a straight line at carrying height to the box and a drop with the hand any way: **6 of 6 balls in their boxes, 51 s** (about 8.5 s a ball at the robot's normal joint speed). The baseline the learned policy is compared with |
| `policy_play.py` | the sim-to-sim check: a policy trained in Isaac Lab (its ONNX and JSON from `rl/sorting/export_policy.py`) run in this scene with exactly its training observations, the same IK and the binary Zimmer; one ball, the easiest, per episode in any of the layouts, or `--sort-all` (six balls one after another, `--video`). The student version adds the same camera model and its memory. Prints the success with its 95 % interval, by layout and by ball count |

### Isaac Lab (`rl/sorting/`, run in the Isaac Lab environment on the Thor)

| File | Contents |
|---|---|
| `scene_from_mjcf.py` | reads the MuJoCo scene: the robot alone as MJCF (with visual copies of the Zimmer's and fingers' collision boxes) converted once to USD by Isaac Lab's MJCF importer; every fixed box of the table, tray and boxes; the balls |
| `sort_env_cfg.py` | the task's configuration: the scene (robot, table, tray, boxes, six balls: three red, three yellow), Newton physics with the MuJoCo-Warp solver at 200 Hz, the policy at 10 Hz, actuator gains, reward weights, curriculum |
| `sort_env.py` | the task: observations, the grasp-point action through a damped least squares IK (grasp point first, the fingers as straight down as the arm allows, any way while the ball is held), the binary Zimmer stroke, rewards, success and drop, the ball layouts and stage at each reset, the easiest ball and the hand's turn as `manipulation/sort.py` chooses them |
| `layouts.py` | where the balls lie: scattered, row, heap, touching pairs, spread (GPU, all environments at once) |
| `check.py` | a scripted controller on the same observations, to check that the task can be done before training; `--record` writes a clip |
| `export_policy.py` | a checkpoint as ONNX (with its observation normaliser) and a JSON of everything needed to use it elsewhere: observation layout, step size, IK weights, start pose, scene numbers, the camera model for the student |
| `train.py` | PPO training with rsl_rl (`agents/rsl_rl_ppo_cfg.py`); TensorBoard curves and checkpoints under `logs/rsl_rl/lumi_sort/` |
| `record_policy.py`, `record_milestones.sh`, `tb_export.py` | clips of a checkpoint (one table close up or a grid of scenes), recorded at set iterations while training runs, and the curves as a figure and CSV |

The balls roll with a little rolling resistance (a ball pushed at 0.2 m/s rolls ~16 mm and stops, close to Newton) and the
tray, the boxes and the table have stiff contacts (wood): without them a nudged ball crept on for seconds and a ball
pressed from above sank through the 4 mm tray floor.

Still guesses in the model: the fingers' direction around the flange and the grasp point (to be taught with a
ball), the finger mass, joint motor gains, the table's height in the arm frame (to be touched), the box positions on
the real table.

## 1. Engines

| | Isaac Lab | MuJoCo |
|---|---|---|
| Role | training (PPO, thousands of parallel scenes) | sim-to-sim check, debugging, quick visual runs on the Mac |
| Version | Isaac Lab 3.0, Newton physics on NVIDIA Warp (default install, Isaac Sim not required for headless training) | MuJoCo ≥ 3.14 (`sim/requirements.txt`) |
| Runs on | the Jetson Thor's GPU (Isaac Lab in its own environment, `~/isaaclab-spike`) | Mac (CPU) and the Thor |
| Robot from | URDF `sim/lumi_description/jaka_lumi.urdf` (arm chain only) + gripper model | `sim/lumi.xml` (already built from the same URDF) |
| Code | `rl/sorting/` | `sim/sorting/` |

Only the arm, the gripper and the scene are simulated. The column below the arm base, lift, waist and head are
fixed collision bodies at the trial pose (lift 75 mm, waist 0°, head straight), because they must be avoided but
do not move.

---

## 2. Robot model

| Part | How | Check |
|---|---|---|
| Arm links and joints | URDF geometry and masses; joint limits with the code's 5° margin | joint angles from the fitted kinematics (`data/arm_kinematics.json`) give the same hand pose in sim within 1 mm at 20 random poses |
| Arm control | joint position targets with stiff gains: the policy's hand move goes through IK to joint targets, like on the robot | step responses match the measured ones (measured on the robot): lag and overshoot |
| Speed limits | 60 °/s per joint cap, linear speed cap of the trial speed; acceleration as measured | same cap numbers as `robot/motion.py` |
| Gripper body | box with the Zimmer's outer size and 0.54 kg + fingers | from 10_GRIPPER.md |
| Fingers | two straight boxes, the new fingers' length and width, friction from the material | open and closed tip gap equal the measured ones within 0.5 mm |
| Gripper motion | **binary**: a close or open command starts a full stroke of ~1 s that cannot be stopped; a new command during a stroke waits for it to end | stroke time from 20 measured strokes; randomised ±20 % |
| Grip | finger force from the switch level (~90 N, capped low in sim to keep contacts stable) | a held ball survives a 0.5 g shake in sim, as on the robot |
| Gripper signals | AI_1 modelled from the finger gap (linear between ~140 open and ~4160 shut, ball gives a value in between) | readings on a held ball match the measured AI_1 |

### Robot description work

The URDF in `sim/lumi_description/` has the arm; the current MuJoCo model hangs a Robotiq 2F-85 on it as a stand-in.
Both simulators need the Zimmer with the new fingers instead. Steps:

1. Measure the new fingers ([01](01_HARDWARE_FACTS.md) §2).
2. Write the gripper as its own small URDF / MJCF (`zimmer_gep2013_straight`), attached at the flange with the
   measured offset.
3. Isaac Lab imports URDF through its asset importer. If the Newton-only install cannot import URDF directly, a USD
   is made once on a machine with Isaac Sim and the generated file is kept in the repo.

---

## 3. Scene

| Item | Simulated as | Randomised (training) |
|---|---|---|
| Table | box, top at the measured height | height ±10 mm, friction 0.4–1.0 |
| Plate | shallow dish mesh or a flat disc with a low rim | position ±30 mm, rim height ±3 mm |
| Ball | sphere, measured diameter and mass, rubber-like contact | diameter ±1.5 mm, mass ±20 %, friction 0.6–1.2, restitution 0.1–0.5, position: see the layouts below |
| Boxes | thin-walled open boxes at the layout positions | position ±15 mm, wall height ±5 mm |
| Obstacles | column, head, lift link as fixed bodies | none |

One ball is "the" ball of the episode; 0–5 other balls lie on the tray with it (the six balls are three red and three
yellow, as the real ones), in one of these layouts, chosen at
random each episode:

| Layout | How it is made |
|---|---|
| Scattered | balls dropped from 5–15 cm at random points over the tray and left to roll to rest, as when they are tipped in |
| Row | 2–6 balls touching in a straight or bent line, any direction |
| Heap | 3–6 balls packed together, the target anywhere in it (middle or edge) |
| Touching pairs | the target touching one or two balls |
| Spread | balls apart with room between them |

The target is the ball the run would take next (the easiest one, [02](02_TASK_DESIGN.md) §2), and the hand's turn is
chosen by the same rule, so training sees exactly the cases the robot meets. Pushing a neighbour aside is allowed;
pushing one off the tray is not.

---

## 4. Sensors

The policy never sees simulator truth directly in the student version ([04](04_RL.md) §8). The sensor model copies
what the robot's vision gives:

| Signal | Model |
|---|---|
| Ball position | true position + fixed bias per episode (up to 10 mm, from the measured error) + noise per reading (σ 3–5 mm) |
| Update rate | new reading every 0.5 s (the skills' depth rate), with 0.1–0.3 s delay |
| Occlusion | no new reading while the hand is above the ball or the ball is in the hand: the last reading is held and a "fresh" flag goes to 0 |
| Dropouts | 5 % of readings missing |
| Hand position | from joint angles through the fitted kinematics: small noise (σ 1 mm) |
| Gripper | state open / closing / closed / opening and the AI_1 value with noise |

A rendered camera image is not needed for version 1. It comes in only with the vision extension ([04](04_RL.md) §9).

---

## 5. Physics settings

| Setting | Start value | Note |
|---|---|---|
| Physics step | 2 ms (MuJoCo now uses 2 ms) | small balls need small steps; check that a held ball does not jitter |
| Policy step | matches the real control rate measured on the robot (mode A 10–20 Hz, mode B 2–4 Hz) | [04](04_RL.md) §3 |
| Contacts | elliptic friction cones, soft contact on the ball | tune until grasp, roll and drop look like the real ball in a filmed test |
| Gravity compensation | on for the arm (as in `sim/lumi.xml`) | the real controller compensates |

---

## 6. Matching the real robot

These numbers in the simulation come from measurements on the robot ([05](05_SIM_TO_REAL.md) §1):

- arm step response (lag, overshoot, settle time) at the trial speed, for each control mode;
- gripper stroke time and AI_1 on a held ball;
- ball diameter, mass, bounce (drop from 10 cm on the table, film it), roll friction (roll down a known slope);
- camera position error on the ball and its delay.

Known differences that stay ([../SIMULATION.md](../SIMULATION.md) §known differences) are written down with their
expected effect, not hidden.
