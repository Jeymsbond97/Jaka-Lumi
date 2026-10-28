# Roadmap and status

Where the project stands and what comes next. Keep it current: replace numbers with the latest, remove what is done
from Next. No dates, no history of how it got here.

**Goal:** the JAKA Lumi in our office works as an autonomous assistant. It greets and talks with visitors (English /
Korean), drives where it is told and fetches objects by voice.

---

## Current state

| Area | State |
|---|---|
| Onboard software | Runs on the Jetson Thor: API + dashboard on :8100, camera service, whisper, embeddings, LLM `gemma4:26b`, voice assistant supervised by the API (user service `lumi-api`). Code in `api/`, `assistant/`, `audio/`, `vision/`, `robot/`, `manipulation/`, `tasks/`, `tests/`, values in `data/`, logs in `logs/` |
| Dashboard | `http://192.168.10.240:8100/view`: live cameras with person boxes, live map, click-to-drive, routes, hold-to-move base / head / lift / waist / arm (hand controls only when idle or paused), Arm pose dropdown, Command dialog, notifications for every error, Greeter / Patrol switches, logs, volume, STOP |
| Understanding commands | Intent bank (fast lane, no LLM) 64246 wordings EN + KO: 27 wrong of 109990. Commands right 88–93 % at every speech level (English 88–89 %, Korean 88–93 %, Konglish / mixed 87 %); typed = spoken except 30 of 19393; 127 stop forms stop; rules act only on a direct order |
| Conversation | Quick answers 2280 / 2284, none wrong. With the LLM: commands 78–89 %, dialogue turns 62–80 %, unasked motions ≤ 3 %; things the arm can't do 82 %. Weakest: Konglish, very short orders, "again / more", memory of earlier days. Requirements and status: [14_VOICE_ASSISTANT.md](14_VOICE_ASSISTANT.md) |
| Attention and voice direction | The person who calls, commands or says "look at me" is the focus; the head stays on them (also during come here, reach and give) and goes back to 0 with the waist at the conversation's end. "Look at me" / "I'm on your right / behind you": voice direction first (head array, `audio/doa.py`), then both cameras; behind: waist (Greeter) or base (Patrol). Stop words heard while Lumi talks or sings. **Not live** ([WORK_PLAN.md](WORK_PLAN.md)) |
| Base | Map `cutshion_708_B_block`: docks `home` (marker `Home`), `dock2`, `charge`; markers `a`, `b`, `p1`–`p10`, `final` (any marker name is read). Stuck drives cancelled; a move that went nowhere is never repeated. "Follow me" (`tasks/follow.py`: head first, waist follows, base turns and unwinds them; not live), distances and speed by voice (`assistant/driving.py`) |
| Arm | Named poses `look`, `carry`, `give`, `ready`, `wave_out`, `wave_start`, `wave`, changed along the pose graph (empty hand: shortest checked route over the taught poses; holding: the fixed chain, never wave poses), every move checked first, one at a time (`manipulation/arm_route.py`); look / carry / ready by voice (not live); wave live; STOP empties the controller queue |
| Pick and place | Offline sweep (1500 pick + 500 place scenes): picks 93 %, every side 92–93 %, cups next to Lumi 94 %, grasps turned > 15° 4; places 79 % (standard tables 95–99 %, tables below −420 mm at lift 0 22 %). Cups 72–92 mm into the hooks' belly. Live: straight picks and put back of a tumbler and a red cup; the rest **not live** ([15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md)) |
| Fetch and missions | `tasks/fetch.py`: search with both cameras, waist and head, reach by waist / base, carry in `look`, put on a seen or named table, give / hold / receive. One command of several steps typed or spoken (`assistant/steps.py`). [16_FETCH_TASKS.md](16_FETCH_TASKS.md), [17_MISSIONS.md](17_MISSIONS.md) |
| Gripper | Zimmer GEP2013IO-05-B (PNP, DO_1 close / DO_2 open, AI_1 → gap, DI_1 below the gripper), [10_GRIPPER.md](10_GRIPPER.md). Steel cups unstable (shiny), paper cups crushed |
| Cameras | Both at USB 3 (5000M). Torso calibrated to the arm (3.3 mm); head calibrated at any head pose (6.0 mm) |
| Lift | Held to 0–105 mm until the longer head camera cable is in (`robot/head.py` `LIFT_MAX_MM`) |
| Internet | Thor's own Wi-Fi (`CUTSHION_5G`); the robot LAN has none |

---

## Next

1. **Pick and place live** (owner at the STOP, slow): the four scenes and the hover check in
   [WORK_PLAN.md](WORK_PLAN.md) "Next". After the hover check: corrected grasp offset, then `TRUSTED_YAW_DEG` 15 → 30 / 45.
2. **Attention and voice live** (WORK_PLAN "Next" 3): look at me from the right / behind (Greeter → waist, Patrol →
   base); wake from out of view with the clip mic; focus during come here; give from `wave_start` (`arm_route.py
   check give`, then `goto give`) with the head on the person; take the cup where only a waist turn reaches; arm poses
   by voice; songs and stop mid-song; stop mid-long-answer; follow me with the waist (`TURN_MAX_RS` 0.3 first);
   conversation end → waist and head to 0.
3. **Voice live**: give while holding, blocked way + "try again", own voice with the clip mic (`ECHO_MIN`); Greeter
   only on the charger, then with Patrol; knowing people again; reply speed (~1 s to the voice); the 🟡 items of docs/14.
4. **"Follow me" live**: off the charger, Greeter + Patrol on, arm at `look`; straight, stop ~1 m away, beside the robot,
   out of view, a chair in the way.
5. **Missions live**: from the Command dialog, then by voice; receive from a hand; distances by voice (measure 1–20 cm).
6. **Arm**: look → carry → give → carry → look live, slow first; "fold your arm"; a safer `tuck`; measure the head to
   replace `HEAD_CLEAR_MM` 250 (estimate); S-curve only with the owner.
7. **Placing**: puts beside Lumi with a waist turn; a table seen from further away kept in the map (low tables);
   place search nearest spots first.
8. **Conference**: new map with new marker names, Wi-Fi profile (phone hotspot first).
9. **Hardware**: longer head camera cable (lift back to 250 mm); thin / soft cups (gripper force level or other
   fingers); `MAX_WIDTH` 92 vs 88 (measure the hooks' neck); collision limits in Cobo π before work near people;
   weigh the tool for the payload; glass door no-go line; hand-over sensing (AI_1 can't feel a pull).
10. **Conversation**: memory of earlier days, Konglish, very short orders, "again / more".
11. **Code**: dashboard drives (`api/server.py`) bring the waist to 0 first; tests stop writing into `logs/lumi.log`;
    fix `tests/interrupt_check.py` (its fake Lumi has no `patrol`).
