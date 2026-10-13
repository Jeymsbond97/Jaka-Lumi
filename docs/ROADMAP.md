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
| Arm | Cobo π programs over TCP 10001 (`hand_shaking.jks`), relative joint jogging, tuck pose |
| Gripper | Zimmer gripper mounted and tested (PNP, DO_1 close / DO_2 open, AI_1 position, DI_1 finger sensor), see [10_GRIPPER.md](10_GRIPPER.md). open / close run from code; API `/gripper/*`, dashboard buttons; voice command written, not tested live |
| Internet | Thor's own Wi-Fi to the company network (`CUTSHION_5G`); the robot LAN has none |

Uncommitted / untested work from 2026-10-13: caller detection outside the camera view, motion commands (turn / move / arm), "answer only what was asked", unclear-speech handling, wake-word-only stops while driving with route resume, varied goodbyes, weather cache, own-voice filter for interruptions.

---

## Next

1. **Live test** of the 2026-10-13 voice changes (all 🟡 items in [14_VOICE_ASSISTANT.md](14_VOICE_ASSISTANT.md)).
2. **Pick and place, stage P0**: live test of the voice "open / close your hand" (code, API and dashboard done) ([15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md)).
3. **P3 camera calibration done**: 30 samples up to 48 cm, median 3.3 mm, max 7.5 mm ([15 §8](15_PICK_AND_PLACE.md#8-camera-calibration-p3-results)). Optional: `calib.py check` live, and a check at another waist / lift position.
4. Then P4 (objects) and P2 (arm motion from code), P1 measurements, P5–P9.
5. Glass door: the base stood "running" at the door (x −1.03, y 0.92) without a free path past the no-go line. Open both leaves or shorten the line in the AGV panel (:9001), move `p1` to the middle of the doorway.
6. Record `arm_tuck.jks` / `arm_reach.jks` in Cobo π. Tuck before every drive (the arm hit a door frame once).
7. Decide on a search API key or the Claude API for general questions.

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
| 2026-10-13 | Voice behaviour reworked (section 7 of the voice doc); weather cache; own-voice filter. Zimmer gripper mounted and measured (PNP, DO_1 / DO_2, AI_1, DI_1); `gripper.py`. Repository reorganised (`sim/`, docs in English, onboarding for the Thor). Pick-and-place plan written. P0: gripper opened / closed from the Thor, `/gripper/state|open|close` in the API, dashboard buttons, voice intents (not tested live). Payload set in Cobo π (1.0 kg estimate). P3: ArUco marker on the gripper body, `calib.py` (collects still poses with the marker in view, own AX = XB solver because OpenCV 5 has no `calibrateHandEye`), calibration median 3.3 mm (30 samples). |
