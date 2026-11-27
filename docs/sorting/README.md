# Colour sorting with reinforcement learning

Lumi picks small rubber balls from a plate and drops each one into the box of its colour, started by one button
in the Lumi app. The arm motion is a policy trained with reinforcement learning in simulation (Isaac Lab), checked
in a second simulator (MuJoCo) and run on the robot's Jetson Thor. The point of the project is the full
sim-to-real pipeline, not only the demo.

Reference video of the target behaviour: `Lumi_Color_Sorting_Demo.mp4` (owner's desktop, 30 s render): red ball to
the red box, blue ball to the blue box, arm back to rest.

---

## Documents

| # | Document | Contents |
|---|---|---|
| 01 | [Hardware facts](01_HARDWARE_FACTS.md) | Everything measured on the robot that the simulation and the policy depend on, with its source, and what is still to be measured |
| 02 | [Task design](02_TASK_DESIGN.md) | The scene, the balls and boxes, what the policy does and what plain code does around it |
| 03 | [Simulation](03_SIMULATION.md) | The Isaac Lab environment, the MuJoCo twin, the gripper model, physics and sensor models |
| 04 | [Reinforcement learning](04_RL.md) | Observations, actions, rewards, resets, curriculum, randomisation, PPO, teacher and student |
| 05 | [Sim to real](05_SIM_TO_REAL.md) | System identification, sim-to-sim check, running the policy on the Thor, safety envelope, real tests |
| 06 | [Integration](06_INTEGRATION.md) | The robot skill (`/skills/sort`), its state, the app's SORT button, STOP |

---

## Goal and success criteria

| Criterion | Target |
|---|---|
| Real robot, one ball on the plate | ≥ 80 % of balls end in the right box over 50 trials |
| Real robot, full plate (4 balls, 2 colours) | ≥ 70 % of plates fully sorted over 20 plates, no ball dropped outside a box |
| Simulation (Isaac Lab, randomised) | ≥ 95 % over 4096 episodes |
| Sim-to-sim (same policy in MuJoCo) | ≥ 85 %; the gap to Isaac Lab is reported |
| Safety | No contact with the head, the column or the table edge in any real trial; STOP ends a trial within 0.5 s |
| Cycle | One ball in ≤ 20 s at the speed used for the trials (the vendor rule keeps it ≥ 80 % slower than the fastest) |

The real success rates are what the project is judged by. Simulation numbers alone mean nothing without them.

---

## How it fits together

```
 Lumi app: SORT button
        │  POST /skills/sort
        ▼
 lumi-api (Thor) ── skill thread ── manipulation/sort.py
        │                              │
        │   vision (existing)          │  until STOP, easiest ball first:
        │   YOLOv8s "sports ball"      │    target box = colour rule
        │   + colour_name + depth  ───►│    policy loop (ONNX, CPU)
        │   → ball position, colour    │      obs → action (Δ hand position, open / close)
        │                              │      → IK → arm command (servo or short moveL)
        │                              │      → gripper DO_1 / DO_2
        ▼                              ▼
 GET /skills/state  ◄── status, ball count, reason
```

- **Decision** (which ball, which box) is plain code: the camera's colour reading picks the box. It is not learned.
- **Motion** (reach, grasp, lift, carry, release) is the learned policy. It is goal-conditioned: it is given the
  ball's position and the target box's position and does one ball per episode.
- **Training** happens in Isaac Lab with thousands of parallel scenes; the policy is exported to ONNX and runs on
  the Thor's CPU (a small network, well under 1 ms per step).

---

## Decisions taken

| Decision | Why |
|---|---|
| Learn the motion, not the colour rule | Sorting by colour is one line of code; the hard and transferable part is the grasp and place. This split is how manipulation stacks are built in industry |
| Policy acts on the ball's 3D position, not on raw pixels (first version) | The existing detector and depth give the position to about 1 cm. A pixel policy needs rendered training images and a much harder sim-to-real step; it is a later extension ([04](04_RL.md) §9) |
| Action = hand position change + open / close, hand pointing down, fixed yaw | A ball has no orientation, so yaw adds nothing. Three numbers plus one switch are far easier to transfer than six joint targets |
| Isaac Lab 3.0 for training, MuJoCo for the cross-check | Isaac Lab is what humanoid teams use; a second engine catches policies that only exploit one simulator's contact model. MuJoCo is already set up in `sim/` |
| Keep the Zimmer gripper with new straight fingers | Same signals and code as today ([10_GRIPPER.md](../10_GRIPPER.md)); only the finger geometry changes. Binary open / close is modelled exactly as it behaves (§ [03](03_SIMULATION.md)) |
| One button in the existing app, no separate app | Owner's requirement |

---

## Where the code lives

Everything is in lumi-wave on the Thor (`~/Dev/lumi-wave`), the project the Lumi app talks to.

| What | Where |
|---|---|
| Training environment, configs, export scripts | `rl/sorting/` (new) |
| MuJoCo sorting scene | `sim/sorting/`, run with `.venv-sim` (`MUJOCO_GL=egl` for pictures) |
| Robot skill and policy runtime | `manipulation/sort.py`, `policies/sort/` |
| App button | Lumi app, COMMANDS → ARM & OBJECTS |
| Run records and plots | `rl/sorting/runs/` (large files kept off git) |
