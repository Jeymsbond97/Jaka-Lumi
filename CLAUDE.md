# Working on this project

Notes for anyone (person or coding assistant) picking up work on this repository, on the Mac or directly on the robot's Jetson Thor.

## What this is

A JAKA Lumi mobile manipulator in our office, made into an autonomous assistant. It greets and talks with visitors in English and Korean, drives where it is told and, next, fetches objects by voice.

- `real/thor/`: the software that runs on the robot's Jetson Thor. Start with its [README](real/thor/README.md).
- `docs/`: real-robot reference (00–13), voice-assistant requirements (14), pick-and-place plan (15), [ROADMAP.md](docs/ROADMAP.md) (status, next steps, log).
- `sim/`: MuJoCo model of the robot; used as the planning model for arm motion.
- `tools/`: laptop-side scripts for the base and arm (`robot_check.py` is read-only); `tools/thor_sync/` copies code and docs to the Thor (its `CLAUDE.md` becomes the Thor's).

**Where to resume:** the "Next" list in [docs/ROADMAP.md](docs/ROADMAP.md). How the assistant must behave is in [docs/14_VOICE_ASSISTANT.md](docs/14_VOICE_ASSISTANT.md); keep the code and that page in step.

## Machines and addresses

| Device | Address | Access |
|---|---|---|
| Jetson Thor | 192.168.10.240 | user `cutshion`; `real/thor/` is deployed to `~/Dev/lumi-wave` together with the docs (`tools/thor_sync/sync.sh`) |
| Arm / body controller | 192.168.10.90 | Cobo π `https://192.168.10.90`, body API `:5000`, arm JSON `:10001` |
| AGV base | 192.168.10.10 | API `:31001`, panel `:9001` |
| Robot API + dashboard | 192.168.10.240:8100 | `/docs`, `/view` |

Robot Wi-Fi `Lumi10000013-5G` (a laptop needs a manual IP such as 192.168.10.200/24). Passwords are **not** in this repository; they are in `docs/private/` on the owner's Mac (git-ignored, the repository is public).

## Working with the owner

- The owner writes in Uzbek. **Answer in Uzbek**, short and clear.
- **Everything in the repository is English**: code, comments, docs, commit messages. Write like an experienced engineer: plain, specific, no filler, nothing that reads as generated text.
- Code style: small single-purpose modules, constants at the top with a comment saying what they mean and why, no speculative abstractions. Match the surrounding code.
- **Commit and push only when asked.** Never commit `gripper_pictures/` or anything from `docs/private/`.
- `docs/00–13` hold measured or vendor-documented real-robot facts only; simulation values stay in `docs/SIMULATION.md`.
- When a test on the robot is needed, say exactly what the owner should do and what to report back. Watch logs or I/O yourself while they do it.

## Safety (always)

- **Ask before moving anything** (base, lift, waist, head, arm, gripper) unless the owner asked for that motion. People work next to the robot.
- **Do not restart the assistant (`assistant/lumi.py`) or the API (`api/server.py`, service `lumi-api`) while the base drives**: check `GET /status` → `base.move_status` first. Stopping the assistant cancels the drive.
- Do not change controller, AGV or network settings without the owner's go-ahead. Match Wi-Fi profile names exactly (a too-broad match once deleted a profile).
- Colleagues' projects on the Thor (`~/Dev/lumi_edu`, `lumi-vision`, `lumi_voice_app`, `jaka-lumi-docs`, `lumi-doctor`, docs on :3080) are not ours. Do not touch them.
- `pkill -f` / `pgrep -f` patterns can match your own shell's command line. Kill by PID.

## On the Thor

- The Thor has no git checkout: `~/Dev/lumi-wave` is the code from `real/thor/` plus `docs/` (including `docs/private/`), `tools/` and its own `CLAUDE.md`. Changes made on the Thor must be copied back here.
- Run Python with `~/Dev/lumi-wave/.venv/bin/python` (system Python lacks OpenCV).
- Logs are in `~/Dev/lumi-wave/logs/`; `lumi.log` is the assistant, `api.log` the API.
- After editing a module, restart only what uses it (see "Deploying a change" in the Thor README).
- The Thor reaches the internet through its own Wi-Fi.
