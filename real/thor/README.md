# Lumi

**English** · [한국어](#lumi-한국어)

Lumi is the software of a **JAKA Lumi** mobile manipulator, developed by Cutshion. It runs entirely on the NVIDIA
Jetson AGX Thor inside the robot and turns it into a conversational service robot for offices and exhibitions: it
understands spoken English and Korean, navigates the floor, perceives people and objects, and handles objects with its
arm.

---

## Capabilities

| Area | What Lumi does |
|---|---|
| **Conversation** | Natural spoken dialogue in English and Korean, including mixed speech. Context-aware follow-ups, interruptions, answers from its own knowledge base and from the web. States plainly what it does not know. |
| **Command understanding** | Single commands, chained commands and multi-step missions in free wording. Only direct requests addressed to Lumi are executed; remarks, conditions and questions are answered, not acted on. |
| **Perception** | Detects, tracks and re-identifies people; reads clothing, gestures and held objects; measures objects on a table in 3D. Every visual answer is taken from a fresh camera frame. |
| **Navigation** | Drives to named locations on any map, moves and turns by spoken distances and angles, follows a person, recovers from a blocked path on request, and docks for charging. |
| **Manipulation** | Picks up cups and bottles, carries them, puts them down on a table, and hands them to a person. Every arm motion is planned along taught, collision-checked poses. |
| **Hearing and voice** | Wake word, voice direction, own-voice rejection, noise and music filtering; natural speech output on the GPU. |

---

## Architecture

```
 microphones ──► speech recognition ──► understanding ──► tasks ──► skills ──► robot drivers ──► hardware
 cameras ─────► vision service ──────────────┘    ▲                                    (base, body, arm, gripper)
                                                  │
                         rules ─► intent bank ─► quick answers ─► LLM
```

**Understanding pipeline.** Each utterance passes through four stages, fastest first:

1. **Rules** for words with one clear meaning and for safety (stop, cancel).
2. **Intent bank**: thousands of example wordings matched by meaning with sentence embeddings (~30 ms).
3. **Quick answers**: frequent standalone questions answered from verified facts (~0.1 s).
4. **LLM** for everything else, reading the full conversation.

An action is executed only if the words form a direct order to Lumi, whichever stage produced it.

**Processes.**

| Process | Role |
|---|---|
| Robot API (`api/server.py`) | FastAPI service: REST endpoints, dashboard, task runner; supervises the other processes |
| Assistant (`assistant/lumi.py`) | Conversation loop; runs while Greeter or Patrol is enabled |
| Vision service (`vision/camview.py`) | Sole owner of the cameras; publishes frames and detections through shared memory |
| Speech recognition | whisper.cpp server on the GPU |
| Embeddings | Local embedding server for the knowledge base and the banks |
| LLM | Ollama |

The software talks to every controller directly over the robot LAN (JSON over TCP and HTTP). It uses no ROS and no
vendor SDK.

**Design principles.**

- **Layered modules.** Drivers → skills → tasks → assistant. Each layer depends only on the layers below it.
- **One driver per device.** Each piece of hardware has exactly one module that talks to it.
- **Single owner for shared resources.** Only the vision service opens the cameras; all other processes read its output.
- **Safety by construction.** Motions are checked before they start (arm path, base clearance, arm sweep). Uncertain input is asked about, never guessed.
- **Data and code apart.** Calibrations and taught values live in `data/`, logs in `logs/`. Every module is runnable and testable on its own.
- **Self-checks without hardware.** `tests/` runs the full logic against simulated devices, so nothing moves during tests.

---

## Technology

| Layer | Technology |
|---|---|
| Language | Python 3.12; HTML / JavaScript for the dashboard |
| Service | FastAPI, Uvicorn, systemd user service |
| Speech | whisper.cpp (large-v3-turbo, CUDA), Silero VAD, Supertonic TTS on TensorRT |
| Language model | Gemma 4 (26B) via Ollama, bge-m3 embeddings |
| Vision | OpenCV, YOLOv8 / YOLO11-pose on TensorRT, YuNet / SFace, Orbbec SDK (RGB-D) |
| Platform | NVIDIA Jetson AGX Thor, JetPack R38.4, CUDA 13 |

---

## Hardware

| Component | Model | Notes |
|---|---|---|
| Mobile base | Differential-drive AGV with lidar SLAM | 0.6 m/s default, 1.2 m/s max; 24 V 45 Ah, about 10 h; contact charging dock |
| Body | Lifting column, waist, head (yaw / pitch) | Controlled through the arm controller's HTTP API |
| Arm | JAKA Mini 2, 6 axes | 2 kg payload, 580 mm reach, ±0.1 mm repeatability |
| Gripper | Zimmer GEP2013IO-05-B, electric parallel | Controlled through the arm's tool I/O |
| Cameras | 2 × Orbbec Gemini 2 L (head and torso), RGB-D | Hand-eye calibrated: 3.3 mm (torso), 6.0 mm (head) |
| Audio | 6-mic ring array, head speaker, optional wireless clip mic | |
| Computer | NVIDIA Jetson AGX Thor | Runs all AI and control |

Full specifications: [docs/01_HARDWARE.md](../../docs/01_HARDWARE.md).

---

## Repository layout

```
api/            Robot API and dashboard
assistant/      Conversation, understanding pipeline, knowledge, web lookups
audio/          Microphones, speech recognition, speech output, voice direction
vision/         Camera service, detection, object measurement, calibration
robot/          Device drivers and checked motion
manipulation/   Pick, place, hand-over, arm pose graph
tasks/          Complete jobs: fetch, missions, follow
tests/          Self-checks and blind test sets
data/           Calibrations and taught values
knowledge/      Texts Lumi answers from
docs/, tools/   Documentation and operator scripts
```

---

## Access

| Service | Address |
|---|---|
| Dashboard | http://192.168.10.240:8100/view |
| Robot API (Swagger) | http://192.168.10.240:8100/docs |
| Arm controller (Cobo π) | https://192.168.10.90 |
| Body controller | http://192.168.10.90:5000 |
| Mobile base panel | http://192.168.10.10:9001 |
| Thor (SSH) | `192.168.10.240` on the robot LAN |

Credentials are kept by the project owner.

## Operating modes

The modes are set from the dashboard. Both are off after every restart.

- **Greeter.** Lumi stays in place. It greets and converses, and runs commands that need no base or waist motion.
- **Patrol.** All capabilities are enabled, including navigation and arm tasks.
- **STOP.** Stops the base, the arm, the body and the assistant at once.

## Safety

- Any new motion is first run slowly, with an operator at a stop control. Available controls: the column E-stop, the dashboard STOP, or the spoken "stop" / "멈춰".
- Keep hands away from the gripper while it can close.
- The arm extends beyond the base. Keep its working area and the driving path clear. The lidar does not detect glass.
- Restart services only while the base is idle.
- Controller, base and network settings are changed only by the project owner.

Full rules: [docs/11_SAFETY.md](../../docs/11_SAFETY.md).

---

## Development

```bash
git clone <repository> ~/Dev/lumi-wave && cd ~/Dev/lumi-wave
uv venv --python 3.12 .venv
uv pip install --python .venv numpy opencv-python-headless pyorbbecsdk2 fastapi uvicorn supertonic soundfile \
    tensorrt-cu13 cuda-python
echo "$PWD" > .venv/lib/python3.12/site-packages/lumi_wave.pth

for t in tests/test_*.py; do .venv/bin/python "$t" || echo "FAILED $t"; done   # self-checks
systemctl --user restart lumi-api                                             # deploy (base idle)
tail -f logs/api.log logs/lumi.log
```

Models, the speech engine and calibration files are installed on the robot; see [docs/08_NVIDIA_THOR.md](../../docs/08_NVIDIA_THOR.md).
Tunable parameters with their locations are listed in [docs/TUNING.md](../../docs/TUNING.md).

## Documentation

| | |
|---|---|
| [Start here](../../docs/00_START_HERE.md) | Setup and first steps |
| [Hardware](../../docs/01_HARDWARE.md) · [Network](../../docs/02_NETWORK_AND_ACCESS.md) | Specifications, connections, access |
| [Body](../../docs/03_BODY_LIFT_WAIST_HEAD.md) · [Arm](../../docs/04_ARM.md) · [Base](../../docs/05_AGV_BASE.md) · [Gripper](../../docs/10_GRIPPER.md) | Device references |
| [Cameras](../../docs/06_CAMERAS_AND_VISION.md) · [Audio](../../docs/07_VOICE_AND_AUDIO.md) · [Thor](../../docs/08_NVIDIA_THOR.md) | Perception and compute |
| [Safety](../../docs/11_SAFETY.md) · [Tuning](../../docs/TUNING.md) · [Sources](../../docs/12_SOURCES.md) | Operation and references |

---
---

# Lumi (한국어)

[English](#lumi) · **한국어**

Lumi는 쿳션(Cutshion)이 개발한 **JAKA Lumi** 모바일 매니퓰레이터용 소프트웨어입니다. 로봇에 탑재된 NVIDIA Jetson
AGX Thor에서 모든 기능이 동작하며, 로봇을 사무실과 전시장을 위한 대화형 서비스 로봇으로 만듭니다. 영어와 한국어
음성을 이해하고, 공간을 주행하며, 사람과 사물을 인식하고, 팔로 물건을 다룹니다.

---

## 주요 기능

| 영역 | 기능 |
|---|---|
| **대화** | 영어·한국어 및 혼용 음성 대화. 맥락을 이어 가는 후속 질문, 말 끊기, 자체 지식과 웹 검색 기반 답변. 모르는 내용은 모른다고 명확히 답합니다. |
| **명령 이해** | 단일 명령, 연속 명령, 여러 단계의 미션을 자유로운 표현으로 이해합니다. Lumi에게 직접 한 요청만 실행하며, 언급·조건·질문에는 행동 없이 답합니다. |
| **인식** | 사람 감지·추적·재식별, 옷·제스처·손에 든 물건 인식, 테이블 위 물체의 3D 측정. 시각 관련 답변은 항상 최신 카메라 영상을 기준으로 합니다. |
| **주행** | 어떤 지도에서든 지정 위치로 이동, 말로 지정한 거리·각도만큼 이동·회전, 사람 따라가기, 요청 시 막힌 경로 우회, 충전 도킹. |
| **조작** | 컵과 병을 집어 운반하고, 테이블에 내려놓거나 사람에게 건넵니다. 모든 팔 동작은 교시된 자세를 따라 충돌 검사 후 실행됩니다. |
| **음성 처리** | 호출어, 음원 방향 추정, 자기 목소리 제거, 소음·음악 필터링, GPU 기반 자연스러운 음성 합성. |

---

## 아키텍처

```
 마이크 ──► 음성 인식 ──► 이해 ──► 작업 ──► 스킬 ──► 로봇 드라이버 ──► 하드웨어
 카메라 ──► 비전 서비스 ────┘   ▲                       (베이스, 바디, 팔, 그리퍼)
                                │
          규칙 ─► 의도 뱅크 ─► 빠른 답변 ─► LLM
```

**이해 파이프라인.** 모든 발화는 빠른 단계부터 네 단계를 거칩니다.

1. **규칙**: 의미가 하나뿐인 표현과 안전 명령(정지, 취소).
2. **의도 뱅크**: 수천 개의 예문을 문장 임베딩으로 의미 비교(약 30 ms).
3. **빠른 답변**: 자주 묻는 단독 질문에 검증된 사실로 즉시 답변(약 0.1초).
4. **LLM**: 그 밖의 모든 발화를 전체 대화 맥락으로 처리.

어느 단계에서 나온 동작이든, Lumi에게 직접 한 명령일 때만 실행됩니다.

**프로세스.**

| 프로세스 | 역할 |
|---|---|
| 로봇 API (`api/server.py`) | FastAPI 서비스: REST 엔드포인트, 대시보드, 작업 실행, 다른 프로세스 관리 |
| 어시스턴트 (`assistant/lumi.py`) | 대화 루프. 그리터 또는 순찰 모드에서 실행 |
| 비전 서비스 (`vision/camview.py`) | 카메라를 단독으로 소유하며 영상과 감지 결과를 공유 메모리로 제공 |
| 음성 인식 | GPU 기반 whisper.cpp 서버 |
| 임베딩 | 지식 베이스와 뱅크용 로컬 임베딩 서버 |
| LLM | Ollama |

로봇 LAN을 통해 각 제어기와 직접 통신합니다(TCP·HTTP 기반 JSON). ROS와 제조사 SDK는 사용하지 않습니다.

**설계 원칙.**

- **계층 구조.** 드라이버 → 스킬 → 작업 → 어시스턴트 순서로 구성되며, 각 계층은 아래 계층에만 의존합니다.
- **장치당 하나의 드라이버.** 각 하드웨어와 통신하는 모듈은 하나뿐입니다.
- **공유 자원의 단일 소유.** 카메라는 비전 서비스만 열고, 다른 프로세스는 그 결과를 읽습니다.
- **구조적 안전.** 모든 동작은 시작 전에 검사합니다(팔 경로, 베이스 여유 공간, 팔 회전 반경). 불확실한 입력은 추측하지 않고 다시 묻습니다.
- **데이터와 코드의 분리.** 보정값과 교시값은 `data/`, 로그는 `logs/`에 둡니다. 모든 모듈은 단독으로 실행하고 시험할 수 있습니다.
- **하드웨어 없는 자체 검사.** `tests/`는 가상 장치로 전체 로직을 검증하므로, 시험 중 로봇은 움직이지 않습니다.

---

## 기술 스택

| 계층 | 기술 |
|---|---|
| 언어 | Python 3.12, 대시보드는 HTML / JavaScript |
| 서비스 | FastAPI, Uvicorn, systemd 사용자 서비스 |
| 음성 | whisper.cpp(large-v3-turbo, CUDA), Silero VAD, TensorRT 기반 Supertonic TTS |
| 언어 모델 | Ollama 기반 Gemma 4(26B), bge-m3 임베딩 |
| 비전 | OpenCV, TensorRT 기반 YOLOv8 / YOLO11-pose, YuNet / SFace, Orbbec SDK(RGB-D) |
| 플랫폼 | NVIDIA Jetson AGX Thor, JetPack R38.4, CUDA 13 |

---

## 하드웨어

| 구성 | 모델 | 비고 |
|---|---|---|
| 모바일 베이스 | 라이다 SLAM 차동 구동 AGV | 기본 0.6 m/s, 최대 1.2 m/s, 24 V 45 Ah(약 10시간), 접촉식 충전 도크 |
| 바디 | 리프트, 허리, 머리(좌우·상하) | 팔 제어기의 HTTP API로 제어 |
| 팔 | JAKA Mini 2, 6축 | 가반하중 2 kg, 도달 거리 580 mm, 반복 정밀도 ±0.1 mm |
| 그리퍼 | Zimmer GEP2013IO-05-B 전동 평행 그리퍼 | 팔의 툴 I/O로 제어 |
| 카메라 | Orbbec Gemini 2 L RGB-D 2대(머리, 몸통) | 핸드-아이 보정: 몸통 3.3 mm, 머리 6.0 mm |
| 오디오 | 6채널 링 마이크 어레이, 머리 스피커, 선택형 무선 클립 마이크 | |
| 컴퓨터 | NVIDIA Jetson AGX Thor | 모든 AI와 제어 담당 |

상세 사양: [docs/01_HARDWARE.md](../../docs/01_HARDWARE.md).

---

## 폴더 구조

```
api/            로봇 API와 대시보드
assistant/      대화, 이해 파이프라인, 지식, 웹 검색
audio/          마이크, 음성 인식, 음성 합성, 음원 방향
vision/         카메라 서비스, 감지, 물체 측정, 보정
robot/          장치 드라이버와 검증된 동작
manipulation/   집기, 놓기, 건네기, 팔 자세 그래프
tasks/          전체 작업: 가져오기, 미션, 따라가기
tests/          자체 검사와 블라인드 테스트 세트
data/           보정값과 교시값
knowledge/      답변용 지식 문서
docs/, tools/   문서와 운영 스크립트
```

---

## 접속

| 서비스 | 주소 |
|---|---|
| 대시보드 | http://192.168.10.240:8100/view |
| 로봇 API(Swagger) | http://192.168.10.240:8100/docs |
| 팔 제어기(Cobo π) | https://192.168.10.90 |
| 바디 제어기 | http://192.168.10.90:5000 |
| 모바일 베이스 패널 | http://192.168.10.10:9001 |
| Thor(SSH) | 로봇 LAN의 `192.168.10.240` |

계정 정보는 프로젝트 책임자가 관리합니다.

## 동작 모드

모드는 대시보드에서 설정하며, 재시작 후에는 항상 꺼져 있습니다.

- **그리터(Greeter).** 제자리에서 인사와 대화를 하며, 베이스나 허리 이동이 필요 없는 명령만 수행합니다.
- **순찰(Patrol).** 주행과 팔 작업을 포함한 모든 기능을 사용합니다.
- **STOP.** 베이스, 팔, 바디, 어시스턴트를 즉시 정지합니다.

## 안전

- 새로운 동작은 처음에 느리게 실행하며, 정지 수단 옆에 작업자가 대기합니다. 정지 수단은 기둥의 비상 정지 버튼, 대시보드 STOP, 음성 "멈춰" / "stop"입니다.
- 그리퍼가 닫힐 수 있을 때는 손을 가까이 두지 않습니다.
- 팔은 베이스 밖으로 나와 있으므로 작업 공간과 주행 경로를 비워 둡니다. 라이다는 유리를 감지하지 못합니다.
- 서비스 재시작은 베이스가 정지한 상태에서만 합니다.
- 제어기, 베이스, 네트워크 설정은 프로젝트 책임자만 변경합니다.

전체 규칙: [docs/11_SAFETY.md](../../docs/11_SAFETY.md).

---

## 개발

```bash
git clone <repository> ~/Dev/lumi-wave && cd ~/Dev/lumi-wave
uv venv --python 3.12 .venv
uv pip install --python .venv numpy opencv-python-headless pyorbbecsdk2 fastapi uvicorn supertonic soundfile \
    tensorrt-cu13 cuda-python
echo "$PWD" > .venv/lib/python3.12/site-packages/lumi_wave.pth

for t in tests/test_*.py; do .venv/bin/python "$t" || echo "FAILED $t"; done   # 자체 검사
systemctl --user restart lumi-api                                             # 배포(베이스 정지 상태)
tail -f logs/api.log logs/lumi.log
```

모델, 음성 엔진, 보정 파일은 로봇에 설치되어 있습니다. 자세한 내용은 [docs/08_NVIDIA_THOR.md](../../docs/08_NVIDIA_THOR.md)를 참고하십시오.
조정 가능한 파라미터와 위치는 [docs/TUNING.md](../../docs/TUNING.md)에 정리되어 있습니다.

## 문서

| | |
|---|---|
| [시작하기](../../docs/00_START_HERE.md) | 설치와 첫 단계 |
| [하드웨어](../../docs/01_HARDWARE.md) · [네트워크](../../docs/02_NETWORK_AND_ACCESS.md) | 사양, 연결, 접속 |
| [바디](../../docs/03_BODY_LIFT_WAIST_HEAD.md) · [팔](../../docs/04_ARM.md) · [베이스](../../docs/05_AGV_BASE.md) · [그리퍼](../../docs/10_GRIPPER.md) | 장치 레퍼런스 |
| [카메라](../../docs/06_CAMERAS_AND_VISION.md) · [오디오](../../docs/07_VOICE_AND_AUDIO.md) · [Thor](../../docs/08_NVIDIA_THOR.md) | 인식과 연산 |
| [안전](../../docs/11_SAFETY.md) · [튜닝](../../docs/TUNING.md) · [출처](../../docs/12_SOURCES.md) | 운영과 참고 자료 |
