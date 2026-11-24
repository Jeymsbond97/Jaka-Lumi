# 05 Sim to real

How the policy gets from the simulator onto the robot and how the gap is measured and closed.

---

## 1. System identification (before training)

Each test is done with the owner at the robot, arm in free space above the table, at the trial speed. The data
goes into `rl/sorting/sysid/` and the fitted numbers into the simulation config.

| Test | How | Gives |
|---|---|---|
| Controller version and servo | read the version in Cobo π; try `servo_move_enable` and a 5 s small sine on J6 (±5°) over the JSON port with STOP ready | mode A or B ([04](04_RL.md) §3) |
| Step response, mode A | joint targets in small steps (2°, 5°) on J1, J2, J3 at 10 and 20 Hz; record joint angles at the highest rate the port gives | lag, overshoot, settle time per joint |
| Step response, mode B | `moveL` of 10, 20, 30 mm in x, y, z, sent back to back with a 0.2 s gap; record start delay and end time | time per step, which sets the policy rate |
| Connection drops | log every retry during the tests | how often a step is delayed; becomes the delay range |
| Gripper | 20 opens and 20 closes on nothing and on a ball: AI_1 trace | stroke time, AI_1 on a held ball |
| Ball | drop from 10 cm, film at 60 fps; roll down a 5° board | bounce, rolling friction |
| Camera on balls | ball at 5 marked plate positions, 20 readings each, ruler truth | bias and noise; detection rate; colour reading |

---

## 2. Sim-to-sim check (MuJoCo)

The trained student runs in the MuJoCo twin with the same observation code. A large drop in success from Isaac Lab
to MuJoCo means the policy uses something one engine does that the other does not (usually contact details).
That is fixed in simulation (more randomisation, gentler grasp reward) before the robot sees the policy.

Gate: MuJoCo success ≥ 85 % before the first real trial.

---

## 3. Running the policy on the Thor

| Part | Choice |
|---|---|
| Runtime | onnxruntime on the CPU (the policy is a small MLP or GRU: well under 1 ms); no GPU needed, so it does not compete with the LLM and whisper |
| Loop | one thread in the skill: read state → build observation → policy → checks → command; fixed period with timing logged |
| Observation code | one Python module shared word for word with the simulation's student observation (`rl/sorting/obs.py` copied to `real/thor/policies/sort/obs.py` by the export script); a test checks both give the same vector for recorded states |
| Arm command | through `robot/motion.py` (mode B) or a new small servo module (mode A) that keeps the existing checks: joint limits, head clearance, workspace box |
| Gripper | `robot/gripper.py` open / close, never both outputs on |
| Logging | every step: time, observation, action, command sent, controller reply time; one file per episode in `logs/sort/` |

The policy file, its config (control mode, rates, scaling) and the hash of the training run go together in
`policies/sort/`; the skill refuses to run a policy whose config does not match the robot's mode.

---

## 4. Safety envelope

The policy only proposes. Every step passes these before anything moves:

| Check | Limit |
|---|---|
| Workspace box | hand within the plate-and-boxes box: x, y from the layout ± 60 mm, z from table + 15 mm to table + 250 mm |
| Step size | ≤ `STEP_MM` |
| Joint limits | code limits (5° margin) |
| Head and column clearance | `HEAD_CLEAR_MM`, `LINK_HEAD_CLEAR_MM` as in the skills |
| Speed | trial speed cap, set low for the first trials (≤ 50 mm/s linear, as 11_SAFETY.md says for a start) |
| Controller silent | `BLIND_S` 3 s → stop |
| Episode time | 15 s → stop, open, back to `look` |
| STOP | app STOP, `/stop`, `/arm/stop`, `/tasks/stop` end the loop within one step and stop the arm |

A refused step ends the episode as "unsafe" and is logged; the run does not continue around it.

Before the first real trial the collision sensitivity should be raised from the loose defaults (10_GRIPPER.md:119): owner's decision.

---

## 5. Real trials

| Step | Setup | Pass to go on |
|---|---|---|
| 1 Dry run | policy runs with the gripper open and no ball; the hand follows a ball position typed in | hand stays in the workspace box, motion smooth, STOP works |
| 2 One ball, centre | one red ball at the plate centre, 10 trials | ≥ 7 of 10 in the box |
| 3 One ball, anywhere | 50 trials, ball at marked plate positions, both colours | ≥ 80 % |
| 4 Full plate | 4 balls, 2 colours, 20 plates | ≥ 70 % fully sorted, none dropped outside |
| 5 Conditions | step 3 again with blinds open / closed and a moved table (± 2 cm) | within 10 points of step 3 |

Each trial is filmed from a fixed phone position and logged. Every failure gets a
cause from a fixed list: missed grasp, slipped, dropped in carry, hit box rim, wrong box, perception (no or wrong
reading), unsafe stop, timeout, other.

---

## 6. Closing the gap

When real success is clearly below MuJoCo success, the failure causes decide the fix:

| Most failures are | Look at | Usual fix |
|---|---|---|
| Missed grasp | camera bias near the failures; finger gap | widen ball position bias range; re-check the round-object correction |
| Slipped / dropped | finger friction and force | add friction lower range; grasp lower on the ball |
| Hit box rim | box positions vs layout file | re-measure layout; widen box position randomisation |
| Jerky or late motion | step timing logs | refit lag and delay in sim; lower the policy rate |
| Unsafe stops | which check | tighten the reward's near-limit term; move the start pose |

Real-robot fine-tuning (learning on the robot itself) is not in the plan: it is slow and needs resets by hand. If
it is tried, it is a separate, documented experiment.
