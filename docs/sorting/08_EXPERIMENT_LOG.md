# 08 Experiment log

Every measurement, training run and real trial session is recorded here, newest at the bottom of its table. The
raw files live next to the code (`rl/sorting/runs/`, `rl/sorting/sysid/`, Thor `logs/sort/`); this page holds the
numbers and the conclusions.

---

## 1. Naming

| Thing | Name | Example |
|---|---|---|
| Training run | `<date>_<phase>_<short change>_s<seed>` | `2026-12-03_teacher_lift-reward-2x_s1` |
| Sysid session | `<date>_sysid_<what>` | `2026-11-28_sysid_modeB-steps` |
| Real session | `<date>_real_<step>` | `2026-12-15_real_one-ball-anywhere` |

A run record says: git commit, machine, config file, what changed from the previous run and why, the result, and
what was decided because of it.

---

## 2. Metrics

| Metric | Definition |
|---|---|
| Success | ball at rest inside the target box, gripper open, within 15 s |
| Drop rate | ball left the hand outside the target box |
| Wrong box | ball at rest in the other box |
| Missed grasp | close ended without the ball (AI_1 near shut-on-nothing) |
| Unsafe stop | a safety check refused a step |
| Time to success | from episode start to success, successful episodes only |
| Smoothness | mean action-rate cost per episode |
| Real-to-sim gap | MuJoCo success − real success, same ball positions |

Success rates are given with the number of trials and a 95 % interval (Wilson), e.g. "41 / 50 = 82 % (69–90 %)".

---

## 3. Measurements

| Date | Session | Result | Used for |
|---|---|---|---|
| | | | |

## 4. Training runs

| Run | Change | Isaac Lab success (randomised) | MuJoCo success | Decision |
|---|---|---|---|---|
| | | | | |

## 5. Ablations

| Variant | Isaac Lab | MuJoCo | Real (if tried) |
|---|---|---|---|
| Full method | | | |
| No domain randomisation | | | |
| No sensor model | | | |
| No teacher (direct PPO on robot observations) | | | |

## 6. Real trial sessions

| Session | Policy run | Trials | Success | Failures by cause | Notes |
|---|---|---|---|---|---|
| | | | | | |

---

## 7. Portfolio checklist

What a robotics learning team asks about, and where this project answers it:

| Topic | Evidence |
|---|---|
| Simulation and environment design | Isaac Lab environment, MuJoCo twin, robot and gripper models ([03](03_SIMULATION.md)) |
| RL formulation | observations, actions, reward, curriculum ([04](04_RL.md)) |
| Domain randomisation from measured ranges | sysid data and the ranges table |
| Privileged teacher and student distillation | phase 5 runs and the ablation |
| Sim-to-sim and sim-to-real gap, measured | sections 4–6 above |
| Deployment on an embedded computer | ONNX policy on the Jetson Thor, timing logs |
| Safety in a real system | envelope, STOP, refusal logs ([05](05_SIM_TO_REAL.md) §4) |
| Engineering | tests, reproducible runs, seeds, this log |
