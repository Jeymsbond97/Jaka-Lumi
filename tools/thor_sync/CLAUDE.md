# Lumi on the Jetson Thor

This folder (`~/Dev/lumi-wave`) is the software of our JAKA Lumi robot and runs on the robot's Jetson Thor. It also holds the project's documentation, so work can continue from here. The owner develops on a Mac, where the git repository lives (GitHub `Jeymsbond97/Jaka-Lumi`, folder `real/thor/`). This folder is a deployed copy: the code at the top level, the documentation in `docs/` and `tools/`, refreshed from the Mac with `tools/thor_sync/sync.sh`. There is no git here.

## Start here

1. [docs/ROADMAP.md](docs/ROADMAP.md): current state, the **Next** list, the log. Resume from "Next".
2. [docs/15_PICK_AND_PLACE.md](docs/15_PICK_AND_PLACE.md): the current milestone, picking and placing objects by voice. Stage **P0** (gripper from voice, API and dashboard) is next.
3. [docs/10_GRIPPER.md](docs/10_GRIPPER.md): the mounted Zimmer gripper. All tool I/O on PNP; DO_1 close, DO_2 open; AI_1 finger position (~160 open, 4100–4200 closed empty, lower when holding); DI_1 finger sensor. `gripper.py` is written; its open/close have not been run from code yet.
4. [docs/14_VOICE_ASSISTANT.md](docs/14_VOICE_ASSISTANT.md): how Lumi must behave in conversations. Items marked 🟡 are implemented but not yet tested live.
5. [README.md](README.md): architecture of the code in this folder, how to run and deploy.

When the owner asks "where are we?", answer from those files: what was finished last, what is untested, and what the next step is. Then offer to start it.

In the docs, `real/thor/<file>` means `<file>` in this folder. The MuJoCo simulation mentioned in places is only in the Mac repository; it is not needed here.

## Documentation

| Path | Content |
|---|---|
| `docs/00`–`13` | Real-robot reference: hardware, network, body (lift / waist / head), arm, base, cameras, audio, Thor, gripper, safety, sources, facts to verify |
| `docs/14`, `docs/15`, `docs/ROADMAP.md` | Assistant requirements, pick-and-place plan, status |
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

- The owner writes in Uzbek. **Answer in Uzbek**, short and clear.
- **Code, comments and docs are English**, written plainly like an experienced engineer, nothing that reads as generated text. Small single-purpose modules, constants at the top with a comment on what they mean. Match the surrounding code.
- Changes made here must reach the Mac repository too. At the end of a session, list the files changed here so the owner can copy them back (or commit them on the Mac). Update `docs/ROADMAP.md` (tick, Next, log line) and `docs/14` when behaviour changes.
- When a test on the robot is needed, say exactly what the owner should do and what to report. Watch the logs or I/O yourself while they do it (for example poll the arm controller's `get_data` for `tio_din` / `tio_dout` / `tio_ain`).
- `docs/00–13` hold measured or vendor-documented facts only.

## Safety (always)

- **Ask before moving anything** (base, lift, waist, head, arm, gripper) unless the owner asked for that motion. People work next to the robot; no hands near the gripper fingers when code closes it.
- **Do not restart `lumi.py` or `api.py` while the base drives.** Check `curl -s localhost:8100/status` → `base.move_status` first. Stopping the assistant cancels the drive.
- Do not change controller, AGV or network settings without the owner's go-ahead. Match Wi-Fi profile names exactly.
- `pkill -f` / `pgrep -f` can match your own shell's command line: kill by PID.
- Colleagues' projects on this Thor are not ours (`~/Dev/lumi_edu`, `lumi-vision`, `lumi_voice_app`, `jaka-lumi-docs`, `lumi-doctor`, `~/Dev/docs`, services on :8000, :8001, :8090, :3080). Do not touch them. `~/Dev/CLAUDE.md` is a colleague's general guideline file.

## Running things here

- Python: `.venv/bin/python` (the system Python has no OpenCV).
- Logs: `lumi.log` (assistant), `lumi_console.log`, `api.log`, `camview.log`, `whisper_server.log`.
- After editing a module, restart only what uses it ("Deploying a change" in [README.md](README.md)).
- The vendor SDK `jkrc.so` on this machine is x86-only; the arm is driven through the controller's JSON port (`arm.py`, `gripper.py`).
