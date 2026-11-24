# 07 Plan

Phases in order. A phase is closed only by its check, written as a result in [08_EXPERIMENT_LOG.md](08_EXPERIMENT_LOG.md).
"Robot" means the owner is at the robot with STOP ready; everything else is done without moving it.

| Phase | Name | Robot needed | Depends on |
|---|---|---|---|
| 0 | Hardware and measurements | yes (no arm motion) | — |
| 1 | System identification | yes | 0 |
| 2 | Simulation scene and robot model | no | 0 (numbers), 1 (numbers, later) |
| 3 | Training setup (where Isaac Lab runs) | no | — (can run beside 0–2) |
| 4 | Teacher policy | no | 2, 3 |
| 5 | Student policy and sim-to-sim | no | 4 |
| 6 | Robot skill and app button | yes for tests | 1 (mode), can start beside 4 |
| 7 | Real trials | yes | 5, 6 |
| 8 | Write-up and portfolio | no | 7 |

---

## Phase 0: Hardware and measurements

| Task | Output |
|---|---|
| Fit the Zimmer with the new straight fingers; set `FITTED = True` | gripper on the robot |
| Measure the tip gap open and closed, finger length, width, mass, material | numbers in [01](01_HARDWARE_FACTS.md) §2 |
| Teach the new grasp point (free-drive tips onto a ball, read the flange pose) | grasp point in the flange frame |
| Measure the balls: diameter, mass, colours; pick 2 colours (red, blue) | numbers in [02](02_TASK_DESIGN.md) §1 |
| Choose boxes and plate; tape the layout; measure positions with the arm (touch each corner, read the hand position) | `data/sort_layout.json` |
| AI_1 closed on a ball and on nothing, 10 each | thresholds for "holding" |

**Check:** a close on a ball held by hand gives an AI_1 clearly between open and shut-on-nothing; the open gap
clears the ball by ≥ 8 mm each side.

## Phase 1: System identification

| Task | Output |
|---|---|
| Read the controller version; test servo mode over the JSON port (5 s small motion on J6, STOP ready) | mode A or B decided |
| Step responses in the chosen mode ([05](05_SIM_TO_REAL.md) §1) | `rl/sorting/sysid/*.csv`, fitted lag and delay |
| Gripper strokes ×40 | stroke time, spread |
| Camera on balls: detection rate, colour reading, bias and noise at 5 positions | perception numbers |
| Ball bounce and roll films | contact numbers |

**Check:** a script replays the recorded commands in MuJoCo and the simulated joint angles follow the recorded
ones within the measured noise; the colour rule reads both chosen colours right in ≥ 95 % of readings.

## Phase 2: Simulation scene and robot model

| Task | Output |
|---|---|
| Gripper model with the new fingers (URDF + MJCF), attached at the measured offset | `sim/sorting/zimmer_straight.*` |
| MuJoCo sorting scene: table, plate, boxes, balls at measured values; fixed column and head bodies | `sim/sorting/scene.xml` |
| A scripted (not learned) pick and place in MuJoCo using IK, to prove the scene can be solved | `sim/sorting/scripted_demo.py`, a video |
| Same robot and scene in Isaac Lab (import route decided in phase 3) | `rl/sorting/assets/` |
| Kinematics check: fitted kinematics vs both simulators at 20 poses | ≤ 1 mm |

**Check:** the scripted pick and place sorts 4 balls in both simulators; kinematics match.

## Phase 3: Training setup

| Task | Output |
|---|---|
| Spike, half a day at most: install Isaac Lab 3.0 (Newton, no Isaac Sim) on the Thor in a separate venv or the nvcr PyTorch container; run a stock manipulation example headless for 10 minutes | works or the exact error |
| If the Thor fails: pick a cloud x86 machine with an RTX GPU (price per hour noted), install Isaac Lab there; data transfer by git + rsync | training machine ready |
| Run a stock Isaac Lab reach or lift task to completion | baseline speed: steps per second at 4096 scenes |

The Thor runs the robot (LLM, whisper, vision). Training on it only happens when nobody uses Lumi, and never during
a demo.

**Check:** a stock example trains to its documented reward on the chosen machine.

## Phase 4: Teacher policy

| Task | Output |
|---|---|
| Environment: observations, actions (mode from phase 1), rewards, resets, curriculum ([04](04_RL.md)) | `rl/sorting/env/` |
| Unit tests: reward terms, resets, gripper stroke model, workspace limits | `rl/sorting/tests/` |
| Train the teacher, 3 seeds; tune rewards one change at a time, each a logged run | runs in [08](08_EXPERIMENT_LOG.md) |

**Check:** teacher ≥ 95 % on the randomised set ([04](04_RL.md) §10).

## Phase 5: Student policy and sim-to-sim

| Task | Output |
|---|---|
| Student with robot-only observations and memory; DAgger from the teacher, then PPO fine-tune | student policy |
| Ablations: no randomisation / no sensor model / no teacher (direct PPO on student obs) | table of success rates |
| Export to ONNX; parity test: ONNX and PyTorch outputs equal for 1000 recorded inputs | `policy.onnx`, `config.json`, `obs.py` |
| Run the student in MuJoCo | MuJoCo success |

**Check:** student ≥ 90 % in Isaac Lab randomised, ≥ 85 % in MuJoCo.

## Phase 6: Robot skill and app button

| Task | Output |
|---|---|
| `manipulation/sort.py`, `policies/sort/`, endpoints, `robot/servo.py` if mode A ([06](06_INTEGRATION.md)) | Thor code |
| Tests with the arm faked: observation parity, refusals, STOP | `tests/test_sort.py` passes |
| App SORT tile, texts EN + KO, status counts | Lumi app change |

**Check:** dry run on the robot ([05](05_SIM_TO_REAL.md) §5 step 1) passes; STOP ends a run within 0.5 s.

## Phase 7: Real trials

Steps 2–5 of [05](05_SIM_TO_REAL.md) §5, with every trial filmed and logged, failures classified, fixes in
simulation and retrained when needed ([05](05_SIM_TO_REAL.md) §6).

**Check:** the success criteria in [README](README.md).

## Phase 8: Write-up and portfolio

| Task | Output |
|---|---|
| Results page: method, numbers sim vs sim vs real, ablations, failures and what fixed them | [08](08_EXPERIMENT_LOG.md) final section |
| Side-by-side video: Isaac Lab, MuJoCo, real robot, same ball positions | 60–90 s video |
| Short technical summary (one page) for the CV and interviews | PDF |
| Clean public code (no private data, no addresses, no passwords) | repository section |
