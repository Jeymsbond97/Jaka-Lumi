# Lumi on the Jetson Thor

This folder (`~/Dev/lumi-wave`) is the software of our JAKA Lumi robot and runs on the robot's Jetson Thor. It also holds the project's documentation, so work can continue from here. The owner develops on a Mac, where the git repository lives (GitHub `Jeymsbond97/Jaka-Lumi`, folder `real/thor/`). This folder is a deployed copy: the code at the top level, the documentation in `docs/` and `tools/`, refreshed from the Mac with `tools/thor_sync/sync.sh`. There is no git here.

## Where we are (2026-10-16, end of day)

Milestone: **pick and place by voice** ("Lumi, find the red cup, take it and put it here"), plan in [docs/15_PICK_AND_PLACE.md](docs/15_PICK_AND_PLACE.md), stages P0–P9; fetch tasks in [docs/16_FETCH_TASKS.md](docs/16_FETCH_TASKS.md).

| Stage | State |
|---|---|
| P0 gripper from voice / API / dashboard | **Done.** `robot/gripper.py`, `/gripper/state|open|close`, dashboard Arm tab, voice (English tested live; Korean not yet) |
| P1 gripper measurements | Model **Zimmer GEP2013IO-05-B**, payload an **estimate** (1.0 kg). AI_1 can't feel a pull on a held cup (measured, docs/10 §3). Still open: weigh the tool, AI_1 → mm, DI_1 range |
| P2 arm motion | **Done.** `robot/motion.py`. Poses: **`look`** (drive, turn, look, wait, also with an object; start / end of every pick; taught 2026-10-15), `carry` (only passed through after a pick), `give`, `ready` (only an IK seed now), `tuck`. With an object every move is a checked straight line (20 points, cup lean ≤ 15°, joint step ≤ 25°) |
| P3 camera calibration | **Done.** `data/camera_extrinsics.json`; the torso camera is on the arm's link, so it holds at any lift (checked 75 → 150 mm) |
| P4 objects | **Done.** `vision/objects.py`, `/objects`. Detector **YOLOv8s on the GPU** (TensorRT engine `models/yolov8s.engine`, ~4–13 ms; CPU YOLOv8n fallback); zoom pass on three torso crops; weak cup boxes (0.05+) kept when depth measures a cup-sized thing. Live: cup 0.71–0.78 at 0.7–0.8 m |
| P5 reach | ✅ **Live 2026-10-16**: base moves to reach (turn on the spot + checked straight drive) brought cups into reach and they were picked (also from a 13 cm foam box). Grasp every 15° round, two wrist solutions, only if the line to `carry` passes. Heights: the arm reaches table tops +300 … −250 mm from ours with the lift (`SURFACE_Z`, `lift_for`; IK-measured); lower (floor, chair seats) refused with the reason. A width measured further than 250 mm from the pick zone is not trusted (measured again up close). A pick never uses a depth-only position (`skills.locate` was 45 mm off and knocked a cup over) |
| P6 / P7 pick, place, give | 🟡 **Live**: pick and put back on table / box. Written, not yet live: put down on a named thing ("on the orange chair": `brain.place_on`, `fetch._put_on`), far-table put-down, give with Release. In-hand check: torso depth sees an **empty** hand reliably, a held cup is too near (then AI_1) |
| P8 voice | 🟡 written, voice parts not yet run live |
| P9 fetch with driving | 🟡 **Live**: picked, drove to p9 holding in `look` (drives in `carry` stalled). Dashboard Command dialog while holding reads with rules only (0.2–0.6 s): "give me cup", "go to p5 and put it on the yellow chair", "bring it to p2"; editable Object / Colour / At the end; no confirm popup |
| Safety | Before every turn on the spot the arm's sweep is checked with lidar + map (`turn_hits`) and the torso depth camera at the arm's height (`depth_hits`); live it caught a bin the lidar missed. Every base drive is logged (`robot/drive_log.py`, Settings → Logs) |
| Docks | `home` = marker `Home` (num 1); **`dock2`** (num 2) at (0.967, 8.412) where the owner put a charger on 2026-10-16; the owner will move the charger back to `Home` |
| **Next** | (1) Head camera on USB 3 (owner, 2026-10-17): check 5000M, calibrate it to the arm like the torso one, add it to the turn check (sides) and the far search. (2) Live tests of the 🟡 items above (ROADMAP Next 0). (3) Arm collision sensitivity in Cobo π with the owner. (4) Later: Qwen3 vs gemma4 on a recorded command set; qwen3-vl as a fallback detector |

Untested live: the voice-assistant changes of 2026-10-13 (🟡 in [docs/14_VOICE_ASSISTANT.md](docs/14_VOICE_ASSISTANT.md)), Korean gripper commands, the own-voice filter and the 15 s voice session. The full Next list is in [docs/ROADMAP.md](docs/ROADMAP.md).

Running: the user systemd service `lumi-api` (API, dashboard, camera service, whisper, embeddings, LLM). Greeter / Patrol stay off after a reboot on purpose. Tunable values (speeds, distances, thresholds) with file and line: [docs/TUNING.md](docs/TUNING.md).

When the owner asks "where are we?", answer from this section and ROADMAP: what was finished last, what is untested, the next step. Then offer to start it.

## Start here

1. [docs/ROADMAP.md](docs/ROADMAP.md): current state, the **Next** list, the log.
2. [docs/15_PICK_AND_PLACE.md](docs/15_PICK_AND_PLACE.md): design, stages, calibration results (§8).
3. [docs/10_GRIPPER.md](docs/10_GRIPPER.md): gripper hardware, signals, test log, payload. All tool I/O on **PNP**; DO_1 close, DO_2 open (never both on); AI_1 finger position (~160 open, 4100–4200 closed empty, ~3500 on a cup's wide part); DI_1 finger sensor (1 = object in front).
4. [docs/14_VOICE_ASSISTANT.md](docs/14_VOICE_ASSISTANT.md): how Lumi must behave in conversations.
5. [README.md](README.md): architecture of the code in this folder, how to run and deploy.

In the docs, `real/thor/<path>` means `<path>` in this folder (for example `real/thor/robot/gripper.py`). The MuJoCo simulation mentioned in places is only in the Mac repository; it is not needed here.

## Facts learned the hard way

- **Arm pose angles**: `get_data` → `actual_position` = [x, y, z mm, rx, ry, rz deg] of the flange (tool 0) in the arm base frame; the angles are fixed X-Y-Z roll-pitch-yaw, **R = Rz·Ry·Rx** (proved by the calibration: 4 mm against 97 mm for the other order). `vision/calib.py` `rpy_matrix()` / `flange_pose()` do this.
- `get_data` now and then returns a reply without the arm state or the connection closes: catch it and poll again.
- **OpenCV 5.0 here has no `cv2.calibrateHandEye`**; `vision/calib.py` has its own AX = XB solver + least-squares refinement.
- Camera service (`vision/camview.py`): full-size frames are `/dev/shm/lumi_raw_<cam>.jpg` (1280×720), colour intrinsics `/dev/shm/lumi_intr_<cam>.json` (`camview.intrinsics(name)`). Torso: fx 608.3, fy 608.4, cx 636.9, cy 363.2. After `vision/camview.py --stop` / `--start` the torso camera may not be found while it re-enumerates (`camera 'torso' not found`): wait a few seconds and start the service again.
- The hub in the head was USB 2 and the head camera dropped out when the speaker played; the owner replaced it with a USB 3 hub on 2026-10-15 (camera at 5 Gb/s, colour and colour + depth without a dropout while speaking at 60 %). Camera roles: the head camera (depth only when linked at USB 3, checked in sysfs) watches people while Lumi stands; the torso camera watches the path while driving and does objects, pick, calibration; either replaces the other while it gives no detections (`assistant/lumi.py` `Vision.pick`). An extension cable once dropped the head link to USB 2 (480M): check the speed with `/sys/bus/usb/devices/*/speed` after any cable work.
- Collision limits in Cobo π are still the loose defaults; tighten them before the arm works near people (with the owner).
- **In `carry` the held cup is right in front of the torso camera** (it covers the table): look for a place from `look` (the cup is out of the view there, 5.9° lean). At table height the torso camera sees only y ≥ ~640 mm in the arm frame; nearer spots can't be checked for table.
- **Body axes after a controller power cycle are disabled** (`/extaxis/status` `enable: false`) and every `moveto` times out; the head pitch reads −5.003° at its stop, outside −5…35°, and a `moveto` with an out-of-range value is dropped. `robot/head.py` `moveto()` enables and clamps.
- The controller sometimes answers a command with another command's reply (`get_data` to `get_joint_pos`) or `get_data` without the tool I/O: `motion._read` and `gripper.state` ask again.
- `kine_inverse` sometimes answers with 7 joint values, `kine_forward` sometimes without `cartPosition`: cut to 6 / ask again (`skills._ask`, `motion.move_linear`).
- Near J5 ≈ 0 a straight move can turn J4 and J6 ~110° against each other in small steps (the cup hardly turns); `motion.move_linear(path_checked=True)` lets a line checked in 20 steps through.
- **Drives with the arm in `carry` stalled every time** (the hand is ~0.3 m before the base front; likely the base's 3D camera sees it); the same drives with the arm in `look` went. Fetch now drives, turns and waits in `look`, also with an object.
- **AI_1 can be wrong about the hand**: a cup pulled out of the closed fingers left AI_1 at 162 ("open"). What is in the hand is decided by the torso depth camera first (`skills.hand_sees`, the cup's axis between the fingers is in view in `look`), AI_1 only when the camera can't tell (`fetch._in_hand`). The camera reliably sees an **empty** hand (the room behind); a held cup is too near for its depth ("unknown"), so then AI_1 decides.
- **The person / object detector runs on the GPU** (`models/yolov8s.engine`, TensorRT, ~4–13 ms per frame; the CPU fallback is YOLOv8n, ~50 ms). Its engine is bound to this Thor's TensorRT and GPU: after a JetPack or TensorRT change, rebuild it from `models/yolov8s.onnx`, else `person.load_net()` falls back to the CPU and prints why.
- **The arm sticks out past the base** (in `look` the flange is ~0.44 m from the base centre); navigation does not know it. Turns on the spot are checked along the arm's sweep (`fetch.turn_hits`); a chair seat is too low for the arm (IK), only surfaces near table height can be reached.
- **Navigation does not take the base near a table**: a goal inside its margin ends "succeeded" without moving. The last part of a reach is a straight `joy_control` drive checked with `agv.clearance` (`/api/map/distance_probe`).
- **Never call `tasks/fetch.py` functions from a second process while the API runs**: its `log()` writes that process's empty state over `/dev/shm/lumi_task.json` (the held cup was "forgotten" once). The runner also asks the gripper now.
- **Tests must never reach the robot**: `tests/test_fetch.py` fakes depth, the lift, `move_linear` and forbids `arm.cmd`; a test once read live depth and called the real IK.

## Documentation

| Path | Content |
|---|---|
| `docs/00`–`13` | Real-robot reference: hardware, network, body (lift / waist / head), arm, base, cameras, audio, Thor, gripper, safety, sources, facts to verify |
| `docs/14`, `docs/15`, `docs/16`, `docs/ROADMAP.md` | Assistant requirements, pick-and-place plan and results, fetch tasks, status |
| `docs/TUNING.md` | Every value the owner may change by hand (arm / lift / base speeds, approach distances, search, detection), with its file and what it does |
| `docs/private/` | **Company-internal**: `ACCESS.md` (all passwords and addresses), AGV notes and API manual, Thor and voice-assistant setup, screenshots. Never copy it anywhere public |
| `tools/` | Scripts the owner runs from a laptop: `robot_check.py` (read-only network check), `agv_teleop.py`, `agv_route.py`, `arm_program.py` |

## Addresses

| Device | Address |
|---|---|
| This Thor | 192.168.10.240 (robot LAN `enP2p1s0`); internet through its own Wi-Fi `wlP1p1s0` |
| Arm / body controller | 192.168.10.90: Cobo π `https://192.168.10.90`, body API `:5000`, arm JSON `:10001` |
| AGV base | 192.168.10.10: API `:31001`, panel `:9001` |
| Robot API + dashboard | `http://192.168.10.240:8100/docs`, `/view` (served from this folder by `api.py`) |

Passwords: `docs/private/ACCESS.md`.

## Working with the owner

- The owner writes in Uzbek. **Answer in Uzbek**, short and clear. Explain hardware steps simply and exactly (which button, which value, what to look for); the owner does the physical work and Cobo π settings and reports back with photos.
- **Code, comments and docs are English**, written plainly like an experienced engineer, nothing that reads as generated text. Small single-purpose modules, constants at the top with a comment on what they mean. Match the surrounding code.
- When a test on the robot is needed, say exactly what the owner should do and what to report. Watch the logs or I/O yourself while they do it (for example poll `get_data` for `tio_din` / `tio_dout` / `tio_ain`, or detect the ArUco marker in `/dev/shm/lumi_raw_torso.jpg`). Long-running helpers: start them with `setsid … > x.log 2>&1 < /dev/null &` and read the log.
- Never guess a physical value (mass, offset, force) into a setting: measure it, take it from a datasheet, or say it is an estimate.
- Update `docs/ROADMAP.md` (tick, Next, log line), `docs/15` and `docs/14` when work is done or behaviour changes. `docs/00–13` hold measured or vendor-documented facts only.
- Robot commands (typed or spoken) are English and Korean only. Never guess or translate a word into an object or place ("olma" is not "orange"): ask, and read the command back.
- UI looks like a finished product: short labels, no hint or explanation texts. Docs describe the project as it is, never "moved from" / "before it was".
- Poses are taught by the owner by hand; check them (limits, cup tilt along the path) and save. Arm moves only when the owner asks; the first run of a new motion slow, the owner at the STOP.
- The owner may ask for parallel agents: give each clear file ownership; agents never move the robot or restart services.
- **Changes made here must reach the Mac repository.** The Mac session pulls this folder when the owner says "yangila" there (it diffs, copies, commits and pushes). So keep files here tidy and complete; mention at the end of a session which files changed. Runtime files (`data/camera_extrinsics.json`, `data/calib_samples/`, `data/doa_*`, `data/volume.txt`, `logs/`, `models/`, `whisper.cpp/`, `.venv`) stay local and are not copied.

## Safety (always)

- **Ask before moving anything** (base, lift, waist, head, arm, gripper) unless the owner asked for that motion. People work next to the robot; no hands near the gripper fingers when code closes it. First run of any new arm motion: slow, watched, owner at the STOP.
- **Do not restart the assistant (`assistant/lumi.py`) or the API (`api/server.py`) while the base drives.** Check `curl -s localhost:8100/status` → `base.move_status` first. Stopping the assistant cancels the drive.
- Do not change controller, AGV or network settings without the owner's go-ahead (Mounting Orientation in Cobo π must stay as it is: the arm is side-mounted, Y 90°). Match Wi-Fi profile names exactly.
- `pkill -f` / `pgrep -f` can match your own shell's command line (also through `bash -c`): find the PID with `ps -eo pid,args | grep "[n]ame"` and kill that.
- Colleagues' projects on this Thor are not ours (`~/Dev/lumi_edu`, `lumi-vision`, `lumi_voice_app`, `jaka-lumi-docs`, `lumi-doctor`, `~/Dev/docs`, services on :8000, :8001, :8090, :3080). Do not touch them. `~/Dev/CLAUDE.md` is a colleague's general guideline file.

## Running things here

- Run any module directly with the venv, from any directory: `.venv/bin/python robot/gripper.py`, `vision/objects.py --watch`, `manipulation/skills.py plan cup`. The system Python has no OpenCV. Modules import each other by folder (`from robot import arm`); the venv's `site-packages/lumi_wave.pth` puts this folder on the path.
- Logs: `logs/lumi.log` (assistant), `logs/lumi_console.log`, `logs/api.log`, `logs/camview.log`, `logs/whisper_server.log`, `logs/calib_collect*.log`.
- Calibration: `vision/calib.py collect` (move the arm by hand, Lumi says "Saved, N"), `solve`, `check` (live difference in mm), `clear`.
- Self-checks: `tests/test_*.py` (objects, skills, intents, fetch, camera choice).
- After editing a module, restart only what uses it ("Deploying a change" in [README.md](README.md)). Boot: the user systemd service `lumi-api` (`lumi-api.service`) runs `api/server.py` and restarts it if it dies (`systemctl --user restart lumi-api`); the API starts the camera service, whisper, the embedding server and loads the LLM; `assistant/lumi.py` runs only while Greeter or Patrol is switched on in the dashboard (the switches are off after a reboot, on purpose).
- The vendor SDK `jkrc.so` on this machine is x86-only; the arm is driven through the controller's JSON port (`robot/arm.py`, `robot/gripper.py`).

## Where files go

The project is kept in folders by job, so anyone can find a file from its name:

| Folder | What belongs there |
|---|---|
| `api/` | the HTTP API, the dashboard and what only they use |
| `assistant/` | conversation: main loop, LLM, knowledge, internet lookups |
| `audio/` | microphones, speech to text, text to speech, voice direction |
| `vision/` | cameras, detection, measuring objects, camera calibration |
| `robot/` | one driver per piece of hardware (base, body, arm, gripper) and checked motion |
| `manipulation/` | skills built on robot + vision: pick, place, give, reach planning |
| `tasks/` | whole jobs made of skills, driving and talking: fetch |
| `tests/` | self-checks that run without the robot (`test_<module>.py`) |
| `data/` | values taught or measured on this robot (JSON, samples) |
| `logs/` | every log file and debug picture |
| `knowledge/` | texts Lumi answers from |
| `docs/`, `tools/` | documentation; scripts run from a laptop |

A new file goes into the folder whose job it shares. When none fits, open a new folder with a plain name for that job (and add it to this table and to the layout in README.md); a single file that belongs to the whole project may stay at the top level. Code writes its data to `data/` and its logs to `logs/`, never next to the code. Docs describe the layout as it is, without history of moves.
