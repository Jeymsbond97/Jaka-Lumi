# Roadmap and status

Where the project stands, what comes next, and a short log. Update it at the end of every working session: tick what was finished, move the "Next" list, add a log line.

**Goal:** the JAKA Lumi in our office works as an autonomous assistant. It greets and talks with visitors (English / Korean), drives where it is told and fetches objects by voice. The MuJoCo model built first (`sim/`) is the robot's planning model for arm motion.

---

## Current state (2026-10-13)

| Area | State |
|---|---|
| Onboard software | `real/thor/` runs on the Jetson Thor: API + dashboard on :8100, camera service, voice assistant (`lumi.py`) supervised by the API |
| Dashboard | `http://192.168.10.240:8100/view`: live cameras with person boxes, live map, click-to-drive, routes, hold-to-move base / head / lift / waist / arm, Greeter / Patrol switches, logs, volume, STOP |
| Voice | wake word, caller direction, streamed answers, web lookups, barge-in, language switching, motion commands; requirements and test status in [14_VOICE_ASSISTANT.md](14_VOICE_ASSISTANT.md) |
| Base | map `cutshion_708_B_block` with dock `Home`, `a`, `b`, `p1`–`p10`, `final`; routes from the dashboard; stuck drives cancelled after 20 s |
| Arm | `motion.py`: named poses (`tuck`, `ready`), checked joint moves, IK-checked straight moves, stop; API `/arm/pose|line|teach|poses`; Cobo π programs (`hand_shaking.jks`) |
| Pick and place | `objects.py` (cups etc. with 3D position / size, `/objects`, dashboard overlay); `skills.py move cup [--to X Y]` picks and places end to end; grasp point taught (`grasp_teach.json`) |
| Gripper | Zimmer gripper mounted and tested (PNP, DO_1 close / DO_2 open, AI_1 position, DI_1 finger sensor), see [10_GRIPPER.md](10_GRIPPER.md). open / close from code, API `/gripper/*`, dashboard, voice (English tested live) |
| Internet | Thor's own Wi-Fi to the company network (`CUTSHION_5G`); the robot LAN has none |

Uncommitted / untested work from 2026-10-13: caller detection outside the camera view, motion commands (turn / move / arm), "answer only what was asked", unclear-speech handling, wake-word-only stops while driving with route resume, varied goodbyes, weather cache, own-voice filter for interruptions.

---

## Next

Where we stopped (2026-10-13 evening): P0, P2, P3, P4 done; `skills.py move cup` picks the white cup, puts it at another spot and returns to `ready` in one command (filmed twice for the boss). Start tomorrow at item 1.

1. **Pick by API and voice** ([15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md) P8, early part): `POST /pick`, `/place`, `/move` in `api.py` calling `skills.py` (409 while `lumi.py` runs, STOP ends it); a dashboard button "Move the cup"; voice "Lumi, pick up the white cup" / "put it there" / "put it back" in `brain.py` + `lumi.py` with spoken `SkillError` reasons. Restart `api.py` after (it still runs the old `arm.py` / `motion.py`).
2. **Robustness seen today**: the controller (TCP 10001) drops connections and sometimes answers `kine_inverse` with errorCode "0" but no joints. Read-only commands are retried now (`arm.py`, `motion.py`, `skills.py`); watch `skills.py` logs for new kinds.
3. **P1 gripper measurements**: AI_1 vs finger gap (mm) table; DI_1 finger sensor saw the cup only in 1 of 4 grasps: find where it looks.
4. **P5 reach planning**: the reach zone is small (cups ~55–62 cm from the arm base, right part of the torso view, table at z ≈ −400 mm); use waist / lift / a short base move when a cup is out of reach. Check `camera_extrinsics.json` at another waist / lift position first (calibrated at lift 75 mm, waist −15°).
5. **Voice live tests**: the 🟡 items in [14_VOICE_ASSISTANT.md](14_VOICE_ASSISTANT.md), Korean gripper commands ("손을 펴", "잡아"), the own-voice filter and the 15 s voice session after a person leaves the frame (both fixed today, not yet run with `lumi.py`).
6. P6 (pick with failure handling, 8/10), P7 (place / give to a person), P9 (fetch with driving).
7. Glass door: the base stood "running" at the door (x −1.03, y 0.92) without a free path past the no-go line. Open both leaves or shorten the line in the AGV panel (:9001), move `p1` to the middle of the doorway.
8. Tuck before every drive (the arm hit a door frame once): `motion.go("tuck")` before `agv` moves in `lumi.py`.
9. Decide on a search API key or the Claude API for general questions.

---

## Stages

### Simulation (done)

- [x] MuJoCo model from the official URDF: base, wheels, lift, waist, head, 6-joint arm, gripper, head and torso cameras; real masses and limits
- [x] `LumiSim` API with the real robot's units: body, arm (IK with collision checks, linear moves), gripper, base, cameras, wave
- [x] `demo.py`: pick and place within 3 mm, base moves, waving
- [ ] Demo video in the README

### Real robot: access and basics (done)

- [x] Network: Mac on `Lumi10000013-5G`, Thor 192.168.10.240, controller .90, AGV .10; read-only check `tools/robot_check.py`
- [x] Arm controller 3.3.8 (`login(1)`); Cobo π program `hand_shaking.jks`; TCP 10001 JSON without the SDK
- [x] AGV: new map, markers, teleop and route scripts
- [x] Thor: Python venv, Orbbec SDK, whisper.cpp (CUDA), Supertonic TTS, Ollama, YOLOv8n ONNX

### Real robot: assistant (mostly done)

- [x] Person detection and tracking (YOLOv8n + depth), camera service as the only camera owner
- [x] Greeting: head turn, wave, voice; patrol mode with path rules and battery return
- [x] Knowledge base (RAG, bge-m3) + gemma4 answers, EN / KO
- [x] Robot API with Swagger (`api.py`), autostart at boot, supervisor for `lumi.py`
- [x] Dashboard with cameras, map, routes, hold-to-move control, settings, logs
- [x] Wake word, voice direction (self-calibrating), "come here", streamed replies
- [x] DJI Mic Mini clip mic (USB-A), barge-in
- [x] Internet over the Thor's Wi-Fi; weather, Wikipedia, news lookups
- [ ] Live tests of the 2026-10-13 behaviour changes
- [ ] Head camera dropouts while the speaker plays (hardware, ask JAKA)

### Real robot: manipulation (next)

- [x] Gripper mounted, wired and measured (2026-10-13)
- [ ] P0–P9 in [15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md)

### Later

- [ ] Fetch missions across rooms (go, pick, come back, give)
- [ ] Side-by-side video of the simulation and the real robot

---

## Log

| Date | What happened |
|---|---|
| 2026-09-30 | MuJoCo model, `LumiSim` API and headless demo done. |
| 2026-10-01 | Model made to look like the real robot (camera windows, lift stripe, JAKA labels); scene person moved beside the table. |
| 2026-10-02 | First look in the viewer: arm poses near joint limits fixed (IK 15° margin, nearest solution, new home pose). |
| 2026-10-04 | Real-robot documentation `docs/00–13` written from the vendor repositories, SDK, manuals and the company Notion. URDF joint space = SDK joint space confirmed. |
| 2026-10-05 | AGV API details added; checklist of facts to verify on the robot. Company-internal data moved to the git-ignored `docs/private/`. |
| 2026-10-07 | First day on the robot: network, controller version, AGV driving and a new map, `hand_shaking.jks`, Thor software (detection, greeting, RAG, gemma4, whisper.cpp, Supertonic, `lumi.py`, patrol). |
| 2026-10-08 | Robot API + Swagger, map extended to the corridor and a second room, route markers, one-time routes. Found: glass door invisible to the lidar, the arm sticks out and hit a door frame. |
| 2026-10-12 | Head camera found behind a USB 2 hub in the head; camera service; dashboard; wake word, voice direction, "come here", streamed answers; DJI clip mic; Thor internet over Wi-Fi; web lookups; stuck-drive detection. |
| 2026-10-13 | Voice behaviour reworked (section 7 of the voice doc); weather cache; own-voice filter. Zimmer gripper mounted and measured (PNP, DO_1 / DO_2, AI_1, DI_1); `gripper.py`. Repository reorganised (`sim/`, docs in English, onboarding for the Thor). Pick-and-place plan written. P0: gripper opened / closed from the Thor, `/gripper/state|open|close` in the API, dashboard buttons, voice intents (not tested live). Payload set in Cobo π (1.0 kg estimate). P3: ArUco marker on the gripper body, `calib.py` (collects still poses with the marker in view, own AX = XB solver because OpenCV 5 has no `calibrateHandEye`), calibration median 3.3 mm (30 samples). Voice gripper commands work in English. Own-voice filter now also on normal listening (Lumi answered its own "How can I help you?"); a visitor lost by the camera keeps a 15 s voice session instead of needing the wake word again. P4 code written (`objects.py`, `/objects`, overlay); first live readings: white tumbler 78 mm wide, 142 mm tall; a clear glass is not measurable (depth sees through it). P2 done: `motion.py`, `ready` pose taught, moves and stop tested. Finger gaps measured (88 / 100 / 66 mm), grasp point taught, first pick and put-back of the metal cup. `gripper.py` closed threshold 2000 → 400. `skills.py` written; first demo run stopped when the controller dropped a `kine_inverse` connection → `arm.py` now retries read-only commands; second run completed end to end. Evening: full sequence `tuck → ready → move cup → ready → tuck (normal speed)` run without a stop and filmed; `kine_inverse` "0 without joints" replies are retried. Files changed on the Thor today (copy to the Mac): new `motion.py`, `skills.py`, `objects.py`, `test_objects.py`, `test_skills.py`, `arm_poses.json`, `grasp_teach.json`; changed `arm.py`, `api.py`, `lumi.py`, `brain.py`, `gripper.py`, `person.py`, `camview.py`, `dashboard.html`, `CLAUDE.md`, `docs/04`, `docs/10`, `docs/14`, `docs/15`, `docs/ROADMAP.md`. |
