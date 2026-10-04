# JAKA Lumi documentation

Everything needed to connect to, test and develop on the real JAKA Lumi. Documents 00–12 contain real-robot information only; the MuJoCo simulation is described separately in SIMULATION.md. Start with **[00_START_HERE.md](00_START_HERE.md)**.

| # | Document | Read it when |
|---|---|---|
| 00 | [Start here](00_START_HERE.md) | First time: install, power on, connect, first tests, where to start coding |
| 01 | [Hardware](01_HARDWARE.md) | You need a spec, a connector, a light code, a model file |
| 02 | [Network and access](02_NETWORK_AND_ACCESS.md) | Connecting a computer; addresses, ports, web pages, apps |
| 03 | [Body: lift, waist, head](03_BODY_LIFT_WAIST_HEAD.md) | Moving the four body joints |
| 04 | [Arm](04_ARM.md) | Cobo π, Python SDK, joint space, trajectories, settings |
| 05 | [Mobile base (AGV)](05_AGV_BASE.md) | Mapping, markers, driving, navigation, people detection |
| 06 | [Cameras and vision](06_CAMERAS_AND_VISION.md) | Orbbec cameras, calibration, vision demos |
| 07 | [Voice and audio](07_VOICE_AND_AUDIO.md) | Microphone, sound direction, voice assistant |
| 08 | [NVIDIA Jetson Thor](08_NVIDIA_THOR.md) | The AI computer, Docker, voice services |
| 09 | [ROS 2, teleop, learning, simulators](09_ROS2_TELEOP_AND_SIM.md) | MoveIt 2, Isaac Sim, VR teleoperation, ACT |
| 10 | [Gripper](10_GRIPPER.md) | Choosing, wiring and programming a gripper (none mounted yet) |
| 11 | [Safety](11_SAFETY.md) | Before any motion |
| 12 | [Sources and downloads](12_SOURCES.md) | Where each fact came from; download links |
| 13 | [To verify on the robot](13_TO_VERIFY_ON_ROBOT.md) | First session: unknown facts and how to find each one |
| — | [Simulation](SIMULATION.md) | Our MuJoCo model and `LumiSim` API |
| — | [private/](private/) | **Local only, git-ignored:** `ACCESS.md` (passwords, IPs, NAS), `THOR_COMPANY_SETUP.md`, `COMPANY_VOICE_ASSISTANT.md`, `AGV_ON_OUR_ROBOT.md` (real replies, our markers), `NOTION_STRUCTURE.md`, `AGV API手册.pdf`, `images/` (78 screenshots) |

The `private/` folder is excluded from git because this repository is public. Keep a copy of it on the team NAS.
