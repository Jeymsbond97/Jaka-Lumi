# 11. Safety

Rules for working with the real Lumi, collected from the Lumi manual, the Mini hardware manual, the JAKA App manual, the chassis manual and the vendor web doc. Read before the first power-on.

---

## 1. Stop devices

| Device | What it does | How to release |
|---|---|---|
| Red E-stop button on the column | Cuts arm power, stops the lift column; the base becomes free to push | Turn to release; then power on and enable the arm again. After release the base can no longer be pushed |
| E-stop on the chassis | Stops the base (LED flashes) | Release the button |
| AGV software E-stop | `/api/estop?flag=true` or "soft E-stop" in the web monitor: base motors free | `flag=false`; independent of the hardware E-stop |
| Body Stop | `POST /api/extaxis/stop` or "Stop" on `http://192.168.10.90:5000` | Reset, enable |
| Arm abort | `robot.motion_abort()`; Cobo π stop | — |

Stop categories (IEC 60204-1): Cat. 0 = power cut at once; Cat. 1 = controlled stop, then power off (E-stop button); Cat. 2 = stop on the path, stays enabled (safety functions, protective stop). The joint brakes tolerate only a limited number of emergency stops: do not use the E-stop as a normal stop.

## 2. Before the first start (Lumi manual 6.8)

- Robot standing on a flat floor, nothing within the arm's reach (580 mm + gripper) and the base's path.
- E-stop tested and within reach of the operator.
- Move slowly beyond the planned workspace and joint limits once to confirm that limits stop the robot.
- Check for drops (stairs, steps) and tipping risks; the base must not reach them.
- First tests at low speed.
- Hot surfaces: keep flammable or heat-sensitive things away from the controller and motors.

## 3. Rules for our tests

1. One person watches the robot with a hand near the E-stop; the code has a stop key ready (`motion_abort()`, body `stop`, AGV `estop`).
2. Low speeds first: arm 0.2–0.5 rad/s (joint) or ≤ 50 mm/s (linear); body `vel` 10–20; base ≤ 0.2 m/s and ≤ 0.3 rad/s.
3. Collision sensitivity: level 1 (25 N) near people (`robot.set_collision_level(1)`).
4. **App safety zones do not work in SDK mode**: our code checks reach, workspace and joint limits before every move, and keeps a margin from the joint limits (the controller stops with a soft-limit error at the limit).
5. Set the payload and mounting in Cobo π before arm motion; wrong payload causes false collisions or drift.
6. `set_network_exception_handle(100, 2)`: the arm aborts if our SDK connection drops.
7. Prefer joint moves near wrist singularities; avoid large orientation changes with linear moves.
8. Keep the cycle time ≥ 80 % slower than the fastest possible cycle (reducer life).
9. The lidar does not see low (< ~23 cm), black, reflective or transparent objects: watch the base.
10. Do not push the base while it is on and not in E-stop; do not lift the wheels; do not drive with the manual charging cable plugged in.
11. Power order: base on → arm power → enable; reverse to stop. Never cut cabinet power while the arm is powered or enabled; wait 5–10 s after shutdown.
12. Teleoperation: be ready before pressing the side button; if the robot shakes, press the E-stop.

## 4. Safety facts (arm)

- Safety system: EN ISO 10218-1, ISO 13849-1 PL d Cat. 3; 27 safety functions in 8 groups.
- During a running program: ≈ 1° deviation between commanded and measured joint position → stop and program end; ≈ 3.6° → stop and disable.
- Stop time / distance charts (Lumi manual Appendix 1): graph axes up to about 250 ms and 80 mm for joints 1–2 at full speed and reach.
- The arm is a collaborative robot but is not meant to work on people; any task that touches a person needs a separate risk assessment (ISO/TS 15066).
