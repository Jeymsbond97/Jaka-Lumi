# Lumi on the Jetson Thor

This folder (`~/Dev/lumi-wave`) is the software of our JAKA Lumi robot and runs on the robot's Jetson Thor. It also holds the project's documentation, so work can continue from here. The owner develops on a Mac, where the git repository lives (GitHub `Jeymsbond97/Jaka-Lumi`, folder `real/thor/`). This folder is a deployed copy: the code at the top level, the documentation in `docs/` and `tools/`, refreshed from the Mac with `tools/thor_sync/sync.sh`. This folder is also a git repository of its own (`.gitignore` keeps the local-only files below out); the owner pushes it with their own account to Gitea `james/lumi` (backend-dev.podosee.com).

## Where we are (2026-10-23, morning)

Milestone: **pick and place by voice** ("Lumi, find the red cup, take it and put it here"), plan in [docs/15_PICK_AND_PLACE.md](docs/15_PICK_AND_PLACE.md), stages P0–P9; fetch tasks in [docs/16_FETCH_TASKS.md](docs/16_FETCH_TASKS.md); missions in [docs/17_MISSIONS.md](docs/17_MISSIONS.md).

| Area | State |
|---|---|
| **NOW (2026-10-23, 11:15)** | Another Claude session (the "lead", started 2026-10-22 18:04 from the office PC over LAN) runs 6 agents until **12:40**, then code freeze 12:45 and a **live voice test at 13:00**. Who does what and which files: docs/WORK_PLAN.md section "Now: midday 2026-10-23". **A second session (e.g. from home over Tailscale) only reads and reports until the lead says the agents are done: do not edit those files, do not commit, do not restart lumi-api.** Battery was 1 % at 09:40 (charger gave nothing overnight), 9 % at 11:00, charging at dock2 |
| **Night 2026-10-22/23** | Big offline test with agents: final blind exam (r5, unseen) **80 % right, 1.9 % unasked motions**; rules act only on a direct order (`brain.direct_order`), intent bank fast lane, blocked-way commands (`assistant/detour.py`), any map names, seeing from a fresh look, early transcription + own-voice filter, why / really / unknowns. Nav guard off (it blocked docking). Drives / follow need no enabled arm (arm power on). All in docs/WORK_PLAN.md "Big night test: results". **None of it live yet; `lumi-api` not restarted since 19:10** |
| **lumi-api** | Restarted 2026-10-21 18:31 with all of the day's code (reply speed, re-id, follow fix, Greeter = in place / Patrol = base + waist, dashboard hand controls only when idle or paused, arm pose graph, any marker name, Korean city weather, back-channels, songs, tests never write logs). Voice, follow and the switches not live-tested after this restart |
| Arm, live 2026-10-21 | Slow first, owner at the STOP: from a free-drive pose to `look` by two checked moves; taught `wave_out`, `wave_start`, `wave` (= `wave_start` with J3 −14.7°). Wave = look → wave_out → wave_start, 2 swings back to back, stays at `wave_start`; down wave_start → wave_out → look. Moves one at a time (`SETTLE_S` 0.3 s, `JOINT_ACCEL_FACTOR` 1.5, route 40 °/s, `ARRIVE_SPEED` "normal" into `wave_start`); software STOP empties the controller queue. Down 7.8 s, up 10.8 s, swings 7.0 s |
| Gitea | `james/lumi` (private): clean snapshots only, pushed with `tools/gitea_push.sh` after each finished piece (tests first); the work log, plans, results and CLAUDE.md stay on the Thor |
| LLM | `gemma4:26b` (benchmark 2026-10-19, logs/llm_bench.md); Qwen models removed; `gemma4:e4b` kept for colleagues |
| Conversation | Checks on gemma4:26b (2026-10-20): company 362/368 + 60/62, conversation 1205/1241, dialogue subset 329/343 turns (70/80), `--all` 1791/1904 turns (385/479; was 1760, 355); details in docs/WORK_PLAN.md |
| Gripper / picks | Zimmer GEP2013IO-05-B; finger sizes in `docs/gripper/`, AI_1 → gap (docs/10 §2.1); widths 61–92 mm (camera width + 8). Live 2026-10-19: white tumbler and red cup picked and put back; steel cups / bowl unstable (shiny), paper cups crushed |
| Arm, reach, fetch | P2–P5 done and live (docs/15, docs/16); P6 / P7 / P9 live for pick, put back, drive holding in `look`; put on a named thing, far table, give with Release written, not live |
| Cameras | Both at 5000M. Torso calibrated (3.3 mm). Head calibrated at any head pose (`vision/head_cam.py`, 6.0 mm) |
| Written, not live | 2026-10-20 evening (after the owner's live place test): one search for pick and place (`fetch._look_around`: ahead with both cameras, waist + head to each side, one base turn, the other lift end), a table / thing seen is gone to at once, table heights from level depth only (`skills.flat_top`), named things exact first else the closest surface (said aloud), "X or Y" / misspellings / "the lower one", fixed pauses removed (ROADMAP Next 0-3). Earlier 2026-10-20: lift limit 105 mm, dashboard head yaw ±180, `held_object` (Lumi names what it holds). Head camera finds and `head_hits` in fetch; waist-corrected base shift (measure-axis −95.5° at waist −20.3°); missions with wait steps and spoken marker names (docs/17, WORK_PLAN); conversation fixes |
| Docks | `home` = marker `Home`; `dock2` at (0.967, 8.412) has a charger; robot charging there |
| **Next** | (00) Restart `lumi-api` (base idle) and live-test the night's work: stop words, give while holding, "look behind", blocked way + "try again", "how old are you?", own voice with the clip mic (`ECHO_MIN`), shirt colour "really?". (0) "Follow me" live: robot off the charger, Greeter + Patrol on, arm at `look` and enabled, stand beside it (ROADMAP 0a-1); then voice tests with Greeter only on the charger (in-place commands; base / waist refused) and with Patrol. (1) Arm: look → carry → give → carry → look live, slow first; a safer `tuck` (look → tuck refused, 175 mm from the head); measure the head to replace `HEAD_CLEAR_MM` 250 (estimate); maybe S-curve (`set_motion_planner`) with the owner in Cobo π. (2) Conference: new map with new marker names (the code reads any name), Wi-Fi profile (phone hotspot first). (3) Older items: placing / search (ROADMAP 0-3), thin cups, collision limits in Cobo π. Read docs/WORK_PLAN.md for the conference work |

Untested live: the voice-assistant changes of 2026-10-13 (🟡 in [docs/14_VOICE_ASSISTANT.md](docs/14_VOICE_ASSISTANT.md)), Korean gripper commands, the own-voice filter and the 15 s voice session. The full Next list is in [docs/ROADMAP.md](docs/ROADMAP.md).

Running: the user systemd service `lumi-api` (API, dashboard, camera service, whisper, embeddings, LLM). Greeter / Patrol stay off after a reboot on purpose. Tunable values (speeds, distances, thresholds) with file and line: [docs/TUNING.md](docs/TUNING.md).

**Work in progress (missions, conversation, conference): [docs/WORK_PLAN.md](docs/WORK_PLAN.md)** — done, running, next.

When the owner asks "where are we?", answer from this section and ROADMAP: what was finished last, what is untested, the next step. Then offer to start it.

## Start here

1. [docs/ROADMAP.md](docs/ROADMAP.md): current state, the **Next** list, the log.
2. [docs/15_PICK_AND_PLACE.md](docs/15_PICK_AND_PLACE.md): design, stages, calibration results (§8).
3. [docs/10_GRIPPER.md](docs/10_GRIPPER.md): gripper hardware, signals, test log, payload. All tool I/O on **PNP**; DO_1 close, DO_2 open (never both on); AI_1 finger position (~160 open, 4100–4200 closed empty, ~3500 on a cup's wide part); DI_1 sensor below the gripper (1 = something under it; never set by a held object).
4. [docs/14_VOICE_ASSISTANT.md](docs/14_VOICE_ASSISTANT.md): how Lumi must behave in conversations.
5. [README.md](README.md): architecture of the code in this folder, how to run and deploy.

In the docs, `real/thor/<path>` means `<path>` in this folder (for example `real/thor/robot/gripper.py`). The MuJoCo simulation mentioned in places is only in the Mac repository; it is not needed here.

## Facts learned the hard way

- **Arm pose angles**: `get_data` → `actual_position` = [x, y, z mm, rx, ry, rz deg] of the flange (tool 0) in the arm base frame; the angles are fixed X-Y-Z roll-pitch-yaw, **R = Rz·Ry·Rx** (proved by the calibration: 4 mm against 97 mm for the other order). `vision/calib.py` `rpy_matrix()` / `flange_pose()` do this.
- `get_data` now and then returns a reply without the arm state or the connection closes: catch it and poll again.
- **OpenCV 5.0 here has no `cv2.calibrateHandEye`**; `vision/calib.py` has its own AX = XB solver + least-squares refinement.
- Camera service (`vision/camview.py`): full-size frames are `/dev/shm/lumi_raw_<cam>.jpg` (1280×720), colour intrinsics `/dev/shm/lumi_intr_<cam>.json` (`camview.intrinsics(name)`). Torso: fx 608.3, fy 608.4, cx 636.9, cy 363.2. After `vision/camview.py --stop` / `--start` the torso camera may not be found while it re-enumerates (`camera 'torso' not found`): wait a few seconds and start the service again.
- The hub in the head was USB 2 and the head camera dropped out when the speaker played; the owner replaced it with a USB 3 hub on 2026-10-15 (camera at 5 Gb/s, colour and colour + depth without a dropout while speaking at 60 %). Camera roles: the head camera (depth only when linked at USB 3, checked in sysfs) watches people while Lumi stands; the torso camera watches the path while driving and does objects, pick, calibration; either replaces the other while it gives no detections (`assistant/lumi.py` `Vision.pick`). An extension cable once dropped the head link to USB 2 (480M): check the speed with `/sys/bus/usb/devices/*/speed` after any cable work.
- **Temporary lift limit 0–105 mm** (2026-10-20): the head camera's cable is too short, a higher lift pulls it out. One constant, `robot/head.py` `LIFT_MAX_MM` (the `moveto` clamp, `fetch.LIFT_RANGE` / `LIFT_TRIES`, dashboard jog follow it); back to 250 when the longer cable is in.
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
- **A head camera opened at USB 2 stays colour-only**: after cable work bringing it to 5000M, restart the camera service (`vision/camview.py --stop`, `--start`) to get head depth.
- **The gripper close cannot be stopped half way**: DO_1 off at AI_1 2730 still ended at 4190. Paper cups are squeezed flat and then read "empty".
- **DI_1 looks below the gripper**, not between the fingers: it is never set by a held object.
- **The camera's width of a cup reads ~8 mm under** the width the fingers meet (`skills.SEEN_UNDER_MM`, `grip_width`).
- **Shiny metal cups give unstable depth**: width 61–74 mm and position jumping up to 17 mm between frames; one was knocked over by a finger.
- **A table's height is its level top, never the median of all depth there**: white chairs' backs and seats next to a round table pulled the median 60–110 mm low (one table read −324 … −555 mm, 2026-10-20); `skills.flat_top` keeps only level depth patches and the biggest group.
- **`skills.py pick` and `put_down` run from the CLI are separate processes**: `_held` (grasp turn, height) is lost between them.
- **Queued joint moves back to back (no wait) shake the whole robot** at every via-point and reversal: the route stops and settles at each pose; only the wave swings run queued.
- **The controller runs long joint moves far slower than commanded**: J1 60° at 25–40 °/s took 7–8 s.
- **`stop_program` empties the controller's motion queue** (checked live: the next queued move did not run).
- **The taught grasp point is the hooks' belly centre**; the finger tips are 28 mm further along the tool axis (owner's free-drive pose on a 66 mm can, `data/grasp_tips_teach.json`). The tips grasp (61–72 mm) missed twice live even with that offset (2026-10-22): it is off (`skills.MIN_WIDTH` 72); objects 72–92 mm go into the belly from above.
- **Cobo π programs (`hand_shaking.jks`, `arm_reach.jks`) run from wherever the arm is**: started from `look`, the wave went through the head (2026-10-21). Never start a stored program without a checked route from a known pose.

## Documentation

| Path | Content |
|---|---|
| `docs/00`–`13` | Real-robot reference: hardware, network, body (lift / waist / head), arm, base, cameras, audio, Thor, gripper, safety, sources, facts to verify |
| `docs/14`, `docs/15`, `docs/16`, `docs/ROADMAP.md` | Assistant requirements, pick-and-place plan and results, fetch tasks, status |
| `docs/gripper/` | Finger shape and inner gaps open / closed (tape, photos); AI_1 → gap in `robot/gripper.py` |
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
- The repo is pushed to Gitea `james/lumi` (private) by the owner's account; only finished work is pushed.
- **Changes made here must reach the Mac repository.** The Mac session pulls this folder when the owner says "yangila" there (it diffs, copies, commits and pushes). So keep files here tidy and complete; mention at the end of a session which files changed. Runtime files (`data/camera_extrinsics.json`, `data/calib_samples/`, `data/doa_*`, `data/volume.txt`, `data/speech_speed.txt`, `logs/`, `models/`, `whisper.cpp/`, `.venv`, `.venv-songs`, `.venv-cover`, `data/songs/mine/`, `tests/data/scene_carrying_jacket_*`, `tests/data/scene_white_shirt_*` (test frames with people)) stay local and are not copied. `data/songs/mine/` holds the owner's licensed songs and everything made from them (instrumental, vocals, lyrics, renders): never copy it, and never put their lyrics into code, docs, tests or knowledge files.

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
