# 03 Simulation

Two simulators, one scene. Isaac Lab trains the policy; MuJoCo replays the same policy to check it does not depend
on one engine's quirks. Both are built from the same robot description and the same numbers ([01](01_HARDWARE_FACTS.md)).

---

## 1. Engines

| | Isaac Lab | MuJoCo |
|---|---|---|
| Role | training (PPO, thousands of parallel scenes) | sim-to-sim check, debugging, quick visual runs on the Mac |
| Version | Isaac Lab 3.0, Newton physics on NVIDIA Warp (default install, Isaac Sim not required for headless training) | MuJoCo ≥ 3.14 (`sim/requirements.txt`) |
| Runs on | NVIDIA GPU, Linux: cloud x86 RTX machine, or the Thor if Isaac Lab runs there | Mac (CPU) and the Thor |
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
| Ball | sphere, measured diameter and mass, rubber-like contact | diameter ±1.5 mm, mass ±20 %, friction 0.6–1.2, restitution 0.1–0.5, start position anywhere on the plate |
| Boxes | thin-walled open boxes at the layout positions | position ±15 mm, wall height ±5 mm |
| Obstacles | column, head, lift link as fixed bodies | none |

One ball is "the" ball of the episode; 0–3 other balls lie on the plate as obstacles so the policy learns not to
knock them off.

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
