# 16. Fetch tasks: bring an object from one place to another

A person tells Lumi what to fetch, from where and to where, in the dashboard (Command) or by voice. Lumi drives
there, finds the object with the torso camera, moves the base a little if the object is out of reach, picks it up,
carries it to the destination and holds it, or puts it on the table there. This is stage A + B of the fetch
work in [15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md); approaching far objects, lift / waist and obstacle-aware reach
(stage C) and other place spots (D) come later.

Status: written and tested without the robot (`tests/test_fetch.py`, `tests/test_fetch_intents.py`); not yet run live. Poses `look`, `carry` and `give` are taught; the base-axis angle is measured (−86.2°, `data/fetch_calib.json`). Table height at the destination is taken as the pick table's height (the camera service does not share depth yet). Tracked in [ROADMAP.md](ROADMAP.md).

---

## 1. The task

```
{"object": "apple",            # cup | bottle | apple | orange | banana (camera classes)
 "colour": null,               # optional, must match the colour the camera measures
 "source": "here" | {"marker": "p1"} | {"x": 1.2, "y": -0.4, "theta": 1.57},
 "dest":   {"marker": "home"} | {"x": ..., "y": ..., "theta": ...} | "here",
 "finish": "hold" | "place"}
```

`x, y` are metres and `theta` radians in the map frame (the base's own frame, like `/agv/go_point`). `"here"` is
where the robot stands when the task is given. The dashboard and the voice build the same task and hand it to the
same runner.

## 2. Arm poses

| Pose | When | Taught |
|---|---|---|
| `tuck` | parking only; fetch does not use it | built in (`robot/motion.py`) |
| `ready` | not moved to by fetch; its arm configuration is the IK seed every pick is planned in | `data/arm_poses.json` |
| `look` | **the empty-hand pose**: driving, looking, start and end of every pick, end of a task. Taught 2026-10-15 by the owner: joints [−250.55, −75.65, −49.42, 194.23, 62.06, 143.5], gripper at the top of the torso view (table and cups fully visible), grasp point z +50 mm (≈ 45 cm above the table), inside the base outline. Not taught → `ready` (`LOOK_POSE`, `skills.HOME_POSE`) | `data/arm_poses.json` |
| `carry` | every drive with an object: close to the body, inside the base outline, gripper upright, the torso camera's left two thirds clear (2.5° tilt; at most 13.1° on the way from `ready`) | `data/arm_poses.json` |
| `give` | handing an object to a person: arm forward (cup centre about (−147, 635, −89) mm in the arm base frame; 4.8° tilt, at most 9.1° on the way from `ready`) | `data/arm_poses.json` |

With an object in the hand every move between poses is a straight one (`moveL`), checked first: IK at 10 points
along the line, and the cup axis at each must stay within `MAX_TILT_DEG` (15°) of vertical. A joint move from a pick
to `carry` tilted the cup up to 36°; the straight move 2.5°. A small joint move then sets the pose's exact joints
(tilt-checked at 11 points with `kine_forward`).

## 3. Steps of a fetch

1. Prepare: empty hand → open the gripper, `look`.
2. Drive to the source (marker: `agv.go`; map point: `agv.go_point`; `here`: no drive); wait until the base has stopped.
3. The arm stays in `look`. Every move between named poses is checked first with `kine_forward`: the grasp point must stay above `MIN_POSE_Z` (−220 mm, table top ≈ −400) or above where it starts; otherwise the task fails before the arm moves.
4. Look (`_search`): `skills.find(object, colour)` at this lift; not found → at the other lifts of `LIFT_TRIES`
   (75, 250, 0 mm); still not → "Let me look around": turn on the spot by 30° (`SEARCH_TURN_DEG`, arm in `look`, lift
   75 mm) and look at lift 75 and 250 mm, up to 11 times (all the way round). Never turns while charging. Nothing
   anywhere → "I looked all around, but I can't see the cup", task failed. With "From: Here" (`"here"`) this is
   the whole search; with a marker / point it is done after driving there.
4b. Table height: the depth surface on rings 80 / 110 mm around the object (`skills.table_near`). When it is more
   than 2 cm (`LIFT_TOL_MM`) from the proven −403 mm, the lift moves by the difference (table 10 cm higher → lift 10 cm
   up, within 0–250 mm, slow) and Lumi looks again; a surface more than 15 cm off (floor, wall) is never fitted. The torso
   camera sits on the same link as the arm base, so the lift does not change the camera calibration (checked: lift
   75 → 150 mm moved a cup x +2, y −2, top −76 mm). Every drive is at lift 75 mm. At a put-down the same is done with
   the table in front (`fetch.table_ahead`), and the object goes down at that table's height.
5. Reach: the pick plan must pass IK. If not, compute the base shift that brings the object to the middle of the
   proven pick zone, shift the base (at most `MAX_SHIFT_M` 0.30 m per try, slow), `look`, look again;
   at most `SHIFT_TRIES` 3 tries. Still out of reach → "I can't reach it, please move it closer to me", look every
   2 s for 30 s, go on when it is reachable, else task failed.
6. Pick (`skills.reachable_pick`): the taught grasp turned about the vertical by 0, ±10, ±20, ±30, ±45, ±60° (`GRASP_YAWS`, the cup stays upright), the first that works: a joint move from `look` to 10 cm above the cup in `ready`'s arm configuration, checked with `kine_forward` at 11 points to never take the gripper more than 2 cm below both ends (`PATH_SAG_MM`), then straight down, close, straight up. The turn is kept and the cup is put down turned the same way.
7. Up, then straight to `carry` (`_line_holding`: the straight move is IK-checked at 10 points and the cup's lean at each must stay within `MAX_TILT_DEG`; measured 2.5° from four pick spots, against 36° for a joint move). No `ready`.
8. Drive to the destination in `carry`; the gripper's holding signal is read every second, a drop stops the base
   ("I dropped it").
9. Finish:
   - `hold`: stay in `carry`, status `holding`; wait for "give" or "place".
   - `place`: straight from `carry` to `look` with the object (5.9° lean; in `carry` the held cup covers the
     torso camera's view of the table), then the same search as step 4, at each try (`_place_here`, `place_spots`): the pick spot itself when the
     base has not moved since the pick (2 cm, 2°); then free spots of a grid (x −260…−60, y 640…700 mm) where the
     torso depth camera sees table at the pick table's height, every one checked at its centre and 8 points 50 mm
     around it (`skills.on_table`; the camera service writes `/dev/shm/lumi_depth_torso.npy`). At table height
     the camera sees only y ≥ ~640 mm, nearer spots can't be checked and are never used after a drive. No spot →
     "I can't see a free place on the table". Then straight from `carry` to above the spot (2.3° lean), put down, back to `look`.
10. Carry to another place (while holding): the dashboard's To (From is hidden while holding) or "bring it to p1"
    → `carry`, drive with the drop watch, keep holding (`fetch.carry_to`, `POST /tasks/carry`).
11. Give (while holding): `carry` → `give` straight (4.8° lean), say "Here you go. Hold it and say thank you.", open
    only on "thank you" (voice) or Release (dashboard Command dialog, `POST /tasks/release`), then `look`. Nobody
    releases within `GIVE_WAIT_S` 30 s: "I'll keep holding it", back to `carry`, still `holding` (it is never dropped).
    A pull can't be felt: with the cup in the closed gripper AI_1's median stayed 2780–2870 during gentle pulls (only
    its noise grew, sd 20 → 50–75), and the fingers settling after the move changed it by 192.

Base shift geometry: the object's position in the arm base frame and the pick zone centre give an offset in the arm
base frame; the base moves by that offset (towards the object), turned into the base frame by the angle between the two
frames (`ARM_YAW_IN_BASE_DEG`). That angle is measured once on the robot with `tasks/fetch.py measure-axis [object]`: the arm stands at
`look` (or `ready`) with a few objects in the torso camera's view; the base drives 10 cm straight forward with `/api/joy_control`
at 0.05 m/s (`AXIS_SPEED`; not navigation, which can turn in place while the arm is over the table). Every object seen
steady before and after (matched by class) is used; the yaw is fitted as an exact rigid motion that includes the
base's own turn during the drive (1.14° on the first 10 cm run). The base always drives back, also after an error. At
`ready` the gripper covers the right part of the torso view, so objects there can disappear after the move. Result (2026-10-14, arm at `look`): the base
drove 0.100 m forward, −0.003 m sideways and turned −1.25°; cup (−235, 1000) → (−261, 894) mm and chair (−862, 1280) →
(−900, 1155) mm in the arm base frame. Fit with both: arm yaw in the base frame **−86.2°**, saved in
`data/fetch_calib.json`. Single objects give −88.0° (cup), −85.0° (chair) and −89.2° (bowl, an earlier run): spread
about ±2°, about 1 cm on a 30 cm shift. The drive back ended 3.5 mm from the start with −1.6° heading drift in total
(straight `joy_control` drives turn about 1° per 10 cm). Without `data/fetch_calib.json`, step 5 does not shift the
base and goes straight to asking the person.

STOP (dashboard, `/stop`, `/arm/stop`, `/tasks/stop`, voice "stop"): base and arm stop at once, the gripper keeps its
state, the task becomes `stopped` and does nothing more until a new task.

## 4. Voice

Works while the assistant runs (Greeter or Patrol on). Rules first (`assistant/brain.py`), the LLM fills the task
only when the rules do not understand. Nothing is guessed: every field must match a known word (objects above and
their Korean names, the map's marker names, "here" / "me"); an unknown or half-heard word is asked about ("Which
object? I know cup, bottle, apple, orange and banana."). A missing destination is asked for; a missing source is
`here`. Low recognition confidence → "Sorry, I didn't catch that".

Lumi reads the task back ("I understood: take the apple from p1, bring it to home and hold it. Is that right?") and
listens 5 s:

| Answer | Then |
|---|---|
| yes / okay / 네 / 응 / 맞아 | start |
| silence | start |
| no / 아니 alone | "What should I change?" |
| a correction ("no, from p2", "not the apple, the cup", "put it on the table") | change only that field, read back again (at most 3 times) |
| cancel / never mind / 취소 | "Okay, cancelled." |

While a task runs: "stop" stops it; short progress is spoken ("Going to p1", "I've got it", "I'm here"). While
holding: "give it to me" / "줘" → give; "put it on the table" / "테이블에 놔" → place; a new fetch → "I'm holding
something, where should I put it first?".

## 5. Dashboard

A **Command** button next to Settings opens a dialog in the middle of the screen (a click outside or Esc closes it):

- **Command**: one text box ("Write command"), English or Korean only ("bring the red apple from p1 to home",
  "p1에서 흰 컵 가져와"). `POST /tasks/parse` reads it: the rules first, else the LLM, which may only answer with
  known words; a marker it names must be written in the text. Text with Hangul is Korean; otherwise the LLM also
  says the language, and anything not English or Korean gets the problem "Please write the command in English or
  Korean." and nothing is taken from it. The task is shown as a sentence and starts only with Start (a short
  confirm: the sentence, then "Start?"), so the person checks what was understood. Problems are shown in red.
- **From / To**: here / marker / a point on the map, used when the text names no place (places in the text win).
  The map zooms (wheel, + / −) and pans (drag); a click sets the point, a drag from the point sets the heading; the
  chosen point is shown as "x 1.23 · y -0.40 · 90°". A point the base cannot stand on (not free, or not connected
  to where the robot is: `nav.reachable`) is refused.
- After a fetch Lumi holds the object; the same box takes "give it to me" / "put it on the table" (also "줘",
  "테이블에 놔"), and Start does it. By voice the same works while the assistant runs.
- While the dialog is open: status, step and the last three log lines of the task; keyboard driving is off.

## 6. Interfaces

`tasks/fetch.py` (one runner, used in-process by the API and by the assistant):

| Function | Does |
|---|---|
| `validate(task, markers) -> list[str]` | problems in plain words, empty when the task can run |
| `describe(task, lang="en") -> str` | the read-back sentence (en / ko) |
| `start(task, say=None)` | start in a background thread; `FetchError` when busy, holding something or invalid |
| `give(say=None)`, `place(say=None)` | finish a `holding` task |
| `stop()` | stop everything the runner does (base, arm, waiting) |
| `state() -> dict` | `{"status", "step", "task", "holding", "log", "since"}`, read from `/dev/shm/lumi_task.json` so any process sees it |

`say(en, ko)` is a callback for spoken progress (the assistant passes one that speaks in the current language).
Status values: `idle`, `running`, `holding`, `done`, `failed`, `stopped`.

API (`api/server.py`): `POST /tasks/parse` (typed text → task / give / place, sentence, problems), `POST /tasks/fetch` (a task), `POST /tasks/describe` (sentence + problems), `POST /tasks/give`,
`POST /tasks/place`, `POST /tasks/stop`, `GET /tasks/state`. While the assistant runs, start / give / place are
forwarded to it (`/dev/shm/lumi_cmd.json`, commands `fetch`, `fetch_give`, `fetch_place`, `fetch_stop`) because it owns
the robot; stop also stops the base and arm directly.

## 7. Tests

Without the robot: `tests/test_fetch.py` (task validation, read-back, base-shift geometry, the step order with fake
drivers, stop at every step), `tests/test_fetch_intents.py` (EN / KO commands, unknown words, corrections,
confirmation answers). On the robot, with the owner at the STOP: empty cup first, slow, one step at a time.
