# 12. Sources and downloads

Every place information came from, what it contains, and whether it was read. Collected 2026-10-04.

---

## 1. Official GitHub

### JAKARobotics/JAKA_Lumi — https://github.com/JAKARobotics/JAKA_Lumi

About 320 MB; prefer single files via `https://raw.githubusercontent.com/JAKARobotics/JAKA_Lumi/<branch>/<path>`, or Code → Download ZIP. Use the "Go to file" search (key `T`), e.g. `pick`, `API`.

| Branch | Contents | Read |
|---|---|---|
| `main` | `01.` promotional material; `02.` product manuals (Lumi manual, AGV API, chassis manual, chassis ports docx, Mini 2 manuals, JAKA App manual, Lumi SDK doc, lift-column release `lumi_release`, sensors URDF, STEP model, 2D drawing, teleop docx, ACT docx); `03.` software notes; `JAKA_Lumi_Demo_Case/` (body, AGV, compose vision demo + SDK builds); `LUMI_DEMO_BMW/` (voice vending demo, Orbbec SDK) | yes |
| `feat_ros` | `jaka_lumi_ros/` ROS 2 workspace (body node, body/arm trajectory servers, MoveIt 2, Isaac Sim, URDF/USD); `LUMI_DEMO-v2.zip` | yes |
| `LumiCode` | `Lumi_Teleoperation/` (ROS 2 VR teleop: `vr_data_pub`, `k1_robot`, `k1_msgs`, `robohub`, `OrbbecSDK_ROS2`), `Lumi_Training/` (ACT / Mobile ALOHA, JAKA Python SDK manual PDF) | yes |
| `feat_demo` | demo case with `2_moveto.py` combining AGV + body + arm | yes |
| `feat_sdk` | demo case copies | yes |
| `ggggffff-eng-patch-1/2` | patches | no |

### JAKARobotics/jaka-robot-demos (branch `dev/jamie`) — https://github.com/JAKARobotics/jaka-robot-demos/tree/dev/jamie

| Folder | Contents |
|---|---|
| `LUMI_DEMO-v1` | Fixed-station vision pick (Qwen-VL), hand-eye calibration, `JAKA_SDK_LINUX/jkrc.pyi`, usage docs (Chinese) |
| `LUMI_DEMO-v2` | Multi-station pick with AGV and body, usage doc |
| `LUMI_DEMO-v3` | Jetson Docker: NanoOWL detection, Whisper wake word, iFlytek / MeloTTS, QR scan, DH gripper over TIO, multi-camera manager, medicine-picking doc |
| `assets/LUMI_DEMO-v3.mp4` | demo video |

Link from the Notion page: `.../tree/dev/jamie/LUMI_DEMO-v1/JAKA_SDK_LINUX` ("example program download", file `LUMI_DEMO-v1.zip`).

### Third-party

| What | Link |
|---|---|
| Orbbec SDK + OrbbecViewer releases | https://github.com/orbbec/OrbbecSDK/releases |
| Orbbec install guide | https://github.com/orbbec/OrbbecSDK/blob/main/doc/tutorial/English/Installation_guidance.md |
| pyorbbecsdk | https://github.com/orbbec/pyorbbecsdk |
| Mobile ALOHA / ACT | https://mobile-aloha.github.io/ , https://github.com/tonyzhaozh/act |
| NVIDIA Jetson AGX Thor quick start | https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/quick_start.html |
| NVIDIA Thor Docker setup | https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/setup_docker.html |
| Isaac Sim 4.5 install | https://docs.isaacsim.omniverse.nvidia.com/4.5.0/installation/install_workstation.html |
| PICO developer docs / Developer Center | https://developer-cn.picoxr.com/document/unity/set-up-the-development-environment/ , https://developer-cn.picoxr.com/resources/#pdc |
| Docker install guide (Chinese, from vendor) | https://blog.csdn.net/educth/article/details/144138879 |
| Alibaba DashScope (Qwen-VL API) | https://help.aliyun.com/zh/dashscope/ , keys: https://dashscope.console.aliyun.com/apiKey |
| Balena Etcher | https://etcher.balena.io |

---

## 2. JAKA downloads and docs

| What | Link |
|---|---|
| JAKA App (1.7.2) and other software | https://www.jaka.com/download |
| JAKA SDK v2.2.7 (zip, 63 MB) | https://www.jaka.com/prod-api/common/download/resource?resource=%2Fprofile%2Fupload%2F2025%2F04%2F25%2F20250425134342A024.zip |
| JAKA document center | https://www.jaka.com/docs/en (JavaScript site) |
| Python SDK page | https://www.jaka.com/docs/en/guide/V3/SDK/python.html |
| Error codes | https://www.jaka.com/docs/en/guide/errinfo.html |
| Add-on development | https://www.jaka.com/docs/en/guide/Add-on/1.1-AboutAdd-on.html |

---

## 3. Google Drive files

| File | Link | Read |
|---|---|---|
| `Coboπ 部署与安装.pdf` (Cobo π deployment, 8 pages) | https://drive.google.com/file/d/1_clYRaAFqT8djNnPlEnCUBzQ1Gr70YsG/view | yes (summary in [02](02_NETWORK_AND_ACCESS.md#3-apps-and-tools)) |
| `JAKA Lumi用户手册-zh-V01_20250707.pdf` (Lumi user manual) | https://drive.google.com/file/d/1eb6f43HezrzEHWXtRnmWwYEk_SkrVOwD/view | yes (same as the GitHub copy) |
| `JAKA Lumi快速手册-zh-V01.pdf` (quick manual, 8 pages) | https://drive.google.com/file/d/11xu0G2LqRBy6SOnAjL18EqLV4corgPlc/view | yes |
| Teleoperation doc and code | https://drive.google.com/drive/folders/1jzkWls1307LE-g39JGgC2y2Ezdba1bqA | linked from the repo, not downloaded |
| Training code | https://drive.google.com/drive/folders/1q3Pp88Bm9qtZXiUwOfsYbNe7FlzjsSSY | linked from the repo, not downloaded |
| Pick-and-place demo code | https://drive.google.com/file/d/15eXxmp1p7NhvUwq3MysWsdD3LPofhZvr/view | linked from the repo, not downloaded |

---

## 4. Feishu (Chinese web documentation)

https://tcnhi91rrwo5.feishu.cn/wiki/Tw1KwXKAbidNxKkFQFoc5oOHn9g — **requires a Feishu login**; it could not be opened from here. A Korean translation of it (provided as screenshots), and its content (from the screenshots) is in these docs. Attachments listed there that only exist in Feishu (ask JAKA or open Feishu with an account):

| Section | Attachment | Equivalent we have |
|---|---|---|
| 3.1.3.1 | `JAKA Lumi用户手册-zh-V01_20250707.pdf`, `JAKA Lumi快速手册-zh-V01.pdf` | Drive / GitHub copies |
| 3.1.3.2 | `Coboπ 部署与安装.pdf` | Drive copy |
| 3.1.4 | `JAKA Lumi宣传单页.pdf` | GitHub `01.` promotional PDFs |
| 3.1.5 | `底盘接口说明.docx` | GitHub `新底盘接口说明.docx` |
| 3.1.6.1 | `AGV API手册.pdf`, `JAKA Lumi底盘使用手册.pdf` | GitHub copies |
| 3.1.6.2 | `lumi_release.zip` (lifting column) | GitHub `升降柱【使用说明】/lumi_release/` |
| 3.1.6.3 | `Docker下ACT学习与推理安装文档及配置说明v1.0.docx` | GitHub copy |
| 3.1.6.4 | `信捷PLC手册.pdf` (Xinje PLC manual) | none |
| 3.1.6.5 | `Lumi基于PICO+VR遥操作系统操作手册.pdf` | GitHub teleop quick-start docx + screenshots |
| 3.1.7.1 | `JAKA 控制器软件.zip` (controller software) | ask JAKA |
| 3.1.8 | `3D模型.tar`, `Lumi-model.zip`, `JAKA-Lumi-urdf.zip`, `JAKA-Lumi-2D图纸.PDF` | GitHub STEP, URDF, drawing |
| 3.1.9 | `JAKA-Lumi-sensors-v3.zip` | GitHub sensors URDF |
| 3.3 | `JAKA Lumi技术分享0123.pdf` (technical sharing) | none |
| 3.3.4.4 | `ext_demo.py` (body test script) | GitHub `body_head/2_moveto.py` |
| 3.5.3.1 | `奥比中光相机Gemini2L介绍及使用资料.pdf` (Gemini 2 L guide) | Orbbec GitHub docs |
| 3.6.2.2 | `DH_PGEA选型手册250628_中文版_V255.pdf`, `教育夹指.stl`, finger shell STEP | none |

Document version history (web doc 2.1): 1.0.0 (2025-11-11) product info + GitHub; 1.0.1 (2025-11-13) dev contest, tutorials, demo library; 1.0.2 (2025-12-05) main controller options; 1.0.3 (2026-01-12) lift test script, arm test page, camera test; 1.0.3 (2026-01-14) shipping size/weight, PICO VR teleop tutorial.

JAKA Cup Embodied-AI developer contest (web doc 3.2.2): registration from 25 July, submissions until 31 December 24:00, judging 2026-01-01…15, results 2026-01-20; up to 3 demos per person/team, reproducible code + 30 s–2 min video; code to a fork of JAKA_Lumi, video on Xiaohongshu with #JAKA具身智能#; prizes PICO 4 Pro / Quark AI glasses (all qualifying), RTX 5070 (2), RTX 5090 (1).

---

## 5. Company Notion

The company's internal Notion page "JAKA Lumi" (sections, what was captured) is described in [private/NOTION_STRUCTURE.md](private/NOTION_STRUCTURE.md) (local only). Access data and screenshots: `private/`.

---

## 6. Files read for these docs (local copies)

Downloaded to the session scratchpad and not kept in the repo: the PDFs and docx above, the SDK 2.2.7 archive (headers, release notes), `jkrc.pyi`, the Python SDK manual, ROS packages, teleop and demo code. To re-read a file, fetch it again from the links in this page.
