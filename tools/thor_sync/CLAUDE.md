# Lumi on the Jetson Thor

This folder (`~/Dev/lumi-wave`) is the software of our JAKA Lumi robot and runs on the robot's Jetson Thor. It also holds the project's documentation, so work can continue from here. The owner develops on a Mac, where the git repository lives (GitHub `Jeymsbond97/Jaka-Lumi`, folder `real/thor/`). This folder is a deployed copy: the code at the top level, the documentation in `docs/` and `tools/`, refreshed from the Mac with `tools/thor_sync/sync.sh`. There is no git here.

## Where we are (2026-10-13 evening)

Milestone: **pick and place by voice** ("Lumi, find the red cup, take it and put it here"), plan in [docs/15_PICK_AND_PLACE.md](docs/15_PICK_AND_PLACE.md), stages P0–P9.

| Stage | State |
|---|---|
| P0 gripper from voice / API / dashboard | Done in code (`gripper.py`, `/gripper/state|open|close`, dashboard Arm tab, voice "open / close your hand", "grab it", "let go"). Open / close run from code. **Voice not yet tested live** |
| P1 gripper measurements | Model **Zimmer GEP2013IO-05-B** (13 mm per jaw, 90–360 N, force switch on 1). **Payload set in Cobo π**: slot `zimmer_gripper`, 1.0 kg, centre of mass (30, 0, 80) mm, an estimate (auto identification refuses on a side-mounted arm). Still open: weigh the tool, AI_1 → mm table, minimum holdable width |
| P2 arm motion from code | Not started. The TCP (fingertip point) is to be kept in our code, not in Cobo π |
| P3 camera calibration | **Done.** ArUco marker (DICT_4X4_50 id 0, 50 mm) on the gripper body's flat black face. `calib.py`: 30 samples, 2 left out, **median 3.3 mm, max 7.5 mm**. Result in `camera_extrinsics.json` (this folder) |
| **P4 objects** | **Next.** `objects.py`: torso camera finds cup / apple / bottle (YOLO COCO classes + colour), position (mm, arm base frame via `camera_extrinsics.json`), height, width; `/objects` API and a dashboard overlay. The arm does not move in this stage |
| P5–P9 | Reach planning, pick, place / give, voice, fetch with driving |

The voice-assistant changes of 2026-10-13 (🟡 in [docs/14_VOICE_ASSISTANT.md](docs/14_VOICE_ASSISTANT.md)) are also still to be tested live. The full Next list is in [docs/ROADMAP.md](docs/ROADMAP.md).

When the owner asks "where are we?", answer from this section and ROADMAP: what was finished last, what is untested, the next step. Then offer to start it.

## Start here

1. [docs/ROADMAP.md](docs/ROADMAP.md): current state, the **Next** list, the log.
2. [docs/15_PICK_AND_PLACE.md](docs/15_PICK_AND_PLACE.md): design, stages, calibration results (§8).
3. [docs/10_GRIPPER.md](docs/10_GRIPPER.md): gripper hardware, signals, test log, payload. All tool I/O on **PNP**; DO_1 close, DO_2 open (never both on); AI_1 finger position (~160 open, 4100–4200 closed empty, ~3500 on a cup's wide part); DI_1 finger sensor (1 = object in front).
4. [docs/14_VOICE_ASSISTANT.md](docs/14_VOICE_ASSISTANT.md): how Lumi must behave in conversations.
5. [README.md](README.md): architecture of the code in this folder, how to run and deploy.

In the docs, `real/thor/<file>` means `<file>` in this folder. The MuJoCo simulation mentioned in places is only in the Mac repository; it is not needed here.

## Facts learned the hard way

- **Arm pose angles**: `get_data` → `actual_position` = [x, y, z mm, rx, ry, rz deg] of the flange (tool 0) in the arm base frame; the angles are fixed X-Y-Z roll-pitch-yaw, **R = Rz·Ry·Rx** (proved by the calibration: 4 mm against 97 mm for the other order). `calib.rpy_matrix()` / `calib.flange_pose()` do this.
- `get_data` now and then returns a reply without the arm state or the connection closes: catch it and poll again.
- **OpenCV 5.0 here has no `cv2.calibrateHandEye`**; `calib.py` has its own AX = XB solver + least-squares refinement.
- Camera service: full-size frames are `/dev/shm/lumi_raw_<cam>.jpg` (1280×720), colour intrinsics `/dev/shm/lumi_intr_<cam>.json` (`camview.intrinsics(name)`). Torso: fx 608.3, fy 608.4, cx 636.9, cy 363.2. After `camview.py --stop` / `--start` the torso camera may not be found while it re-enumerates (`camera 'torso' not found`): wait a few seconds and start the service again.
- The head camera drops out when the speaker plays (USB 2 hub in the head): the torso camera is the one for behaviour and objects.
- Collision limits in Cobo π are still the loose defaults; tighten them before the arm works near people (with the owner).

## Documentation

| Path | Content |
|---|---|
| `docs/00`–`13` | Real-robot reference: hardware, network, body (lift / waist / head), arm, base, cameras, audio, Thor, gripper, safety, sources, facts to verify |
| `docs/14`, `docs/15`, `docs/ROADMAP.md` | Assistant requirements, pick-and-place plan and results, status |
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
- **Changes made here must reach the Mac repository.** The Mac session pulls this folder when the owner says "yangila" there (it diffs, copies, commits and pushes). So keep files here tidy and complete; mention at the end of a session which files changed. Runtime files (`camera_extrinsics.json`, `calib_samples/`, `doa_calib.json`, `volume.txt`, logs, models, `.venv`) stay local and are not copied.

## Safety (always)

- **Ask before moving anything** (base, lift, waist, head, arm, gripper) unless the owner asked for that motion. People work next to the robot; no hands near the gripper fingers when code closes it. First run of any new arm motion: slow, watched, owner at the STOP.
- **Do not restart `lumi.py` or `api.py` while the base drives.** Check `curl -s localhost:8100/status` → `base.move_status` first. Stopping the assistant cancels the drive.
- Do not change controller, AGV or network settings without the owner's go-ahead (Mounting Orientation in Cobo π must stay as it is: the arm is side-mounted, Y 90°). Match Wi-Fi profile names exactly.
- `pkill -f` / `pgrep -f` can match your own shell's command line (also through `bash -c`): find the PID with `ps -eo pid,args | grep "[n]ame"` and kill that.
- Colleagues' projects on this Thor are not ours (`~/Dev/lumi_edu`, `lumi-vision`, `lumi_voice_app`, `jaka-lumi-docs`, `lumi-doctor`, `~/Dev/docs`, services on :8000, :8001, :8090, :3080). Do not touch them. `~/Dev/CLAUDE.md` is a colleague's general guideline file.

## Running things here

- Python: `.venv/bin/python` (the system Python has no OpenCV).
- Logs: `lumi.log` (assistant), `lumi_console.log`, `api.log`, `camview.log`, `whisper_server.log`, `calib_collect*.log`.
- Calibration: `calib.py collect` (move the arm by hand, Lumi says "Saved, N"), `calib.py solve`, `calib.py check` (live difference in mm), `calib.py clear`.
- After editing a module, restart only what uses it ("Deploying a change" in [README.md](README.md)).
- The vendor SDK `jkrc.so` on this machine is x86-only; the arm is driven through the controller's JSON port (`arm.py`, `gripper.py`).
