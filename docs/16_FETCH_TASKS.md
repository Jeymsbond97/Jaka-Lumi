# 16. Fetch tasks: bring an object from one place to another

A person tells Lumi what to fetch, from where and to where, in the dashboard (Command) or by voice. Lumi drives
there, finds the object with the torso camera, moves the base a little if the object is out of reach, picks it up,
carries it to the destination and holds it, or puts it on the table there. This is stage A + B of the fetch
work in [15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md); approaching far objects, lift / waist and obstacle-aware reach
(stage C) and other place spots (D) come later.

Status: written and tested without the robot (`tests/test_fetch.py`, `tests/test_fetch_intents.py`); not yet run live. Poses `look`, `carry` and `give` are taught; the base-axis angle is measured (−95.5° at waist −20.3°, `data/fetch_calib.json`). Table height at the destination is taken as the pick table's height (the camera service does not share depth yet). Tracked in [ROADMAP.md](ROADMAP.md).

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
4. Look (`_search`): `skills.find(object, colour)` at the lift it has; not found → "Let me look around": turn on
   the spot by 30° (`SEARCH_TURN_DEG`, arm in `look`, the lift stays) and look again, 11 times (all the way round);
   still not → the same whole turn at lift 0 mm, then at 105 mm (`LIFT_TRIES` = `LIFT_RANGE`, down first, then up;
   0–105 mm for now: the head camera cable, docs/03). The first turn
   goes towards the side where the base's lidar sees more things the map does not have (`first_side`: 3 angles ×
   3 distances each side, `/api/map/distance_probe` live < 0.3 m where the map is free for 0.5 m: tables, chairs,
   boxes; ~2 s), all later turns the same way. The torso detector looks at the whole frame and again at three crops
   (`vision/person.py` `ZOOM`: the pick zone and the left / right of the band where far table tops are seen, about
   2.7× bigger; ~50 ms each), so cups 1–3 m away are found too. YOLOv8n scores some cups very low (the white
   tumbler 1.4 m away: 0.03–0.25 over 8 frames, 2026-10-16): cup boxes are kept from 0.05 (`person.WEAK_SCORE`), but a
   box under 0.35 counts only when depth measures a whole cup-sized thing there (`objects.sized_like`: width 40–110,
   height 50–250 mm), and `find` still wants it in 5 of 8 frames at the same place. Never turns
   while charging (then only the lifts). Nothing anywhere → "I looked all around, but I can't see the cup", task failed. With "From: Here" (`"here"`) this is
   the whole search; with a marker / point it is done after driving there.
   With the head camera calibrated (`data/camera_extrinsics_head.json` with its axes, and measure-axis done) the
   search uses the head first (`_look_around`): the torso camera looks; then the head looks ahead and every 60° to one
   side up to 180° (`HEAD_SCAN_STEP_DEG`, `HEAD_SCAN_MAX_DEG`, pitch −5° where it is calibrated), the side with more
   unmapped things first (`first_side`), then to the other side (far things); then the waist turns 60° and 120° to
   each side and the torso camera looks (`WAIST_SCAN_DEG`: near, low tables); then the base turns half round in 3
   checked turns (`BASE_HALF_STEPS`) and head and waist look again; then the lift goes to its other end of
   `LIFT_TRIES` (0 or 105 mm: down when it is above the middle, up when below) and all of it again. Still nothing:
   the base moves (`SEARCH_MOVES`): turn 90° to the busier side and drive up to 0.5 m closer to its things, then back
   off 0.3 m to see more; after each the head and waist look at both lifts. Every move goes through the checked
   helpers (waist to the front, arm-sweep check, `line_hits` and `_straight_clear` for straight drives). On the
   charger only the head, the waist and the lifts. Each head yaw is read
   `HEAD_READS` times, a thing counts when seen twice within `HEAD_SAME_MM`. Found by the head: the base turns to face
   it and drives straight (at most `HEAD_DRIVE_MAX_M` 3 m, checked like a reach), then the torso camera finds it.
   Without the head calibration it is the 30° base-turning search above. Written 2026-10-19, not yet run live.
4b. Table height: the depth surface on rings 80 / 110 mm around the object (`skills.table_near`). The lift is set to bring it as near the
   proven −403 mm as 0–105 mm allows (250 with the longer head camera cable) (`lift_for`; table 10 cm higher → lift 10 cm up, slow) and Lumi looks again. Any
   surface that ends between −560 and −30 mm in the arm frame is worked on (`SURFACE_Z`, from the grasp IK: a table
   top +300 … −200 mm from ours at lift 0 reachable, −250 partly, −300 (a chair seat) not at all); lower ones (floor,
   low seats) are never fitted. The torso
   camera sits on the same link as the arm base, so the lift does not change the camera calibration (checked: lift
   75 → 150 mm moved a cup x +2, y −2, top −76 mm). Every drive is at lift 75 mm. At a put-down the same is done with
   the table in front (`fetch.table_ahead`), and the object goes down at that table's height.
5. Reach (`_reach`): the pick plan must pass IK. If not, the base moves so the object comes to `PICK_ZONE_CENTRE`
   (−100, 580) mm, then Lumi looks again (lost: the whole search of step 4), fits the lift and plans again; at most
   `APPROACH_TRIES` 5 moves, never on the charger. One move (`_approach`, geometry in `approach_move` / `side_pose`):
   - Way in at most 0.6 m (`STRAIGHT_MAX_M`): turn on the spot to face it (navigation), then straight with
     `joy_control` at 0.05 m/s (forward when it is too far, backwards when too near). Before the drive the line is
     checked every 5 cm with the base's `/api/map/distance_probe` (lidar + map): the drive ends where the base
     (half width 0.255 m + 0.05 m) would get closer to an obstacle (`agv.clearance`). Navigation alone does not go
     near a table: it keeps its own margin and answered "succeeded" without moving (2026-10-16).
   - Longer, or the straight way blocked: navigation (it plans round obstacles) to a stand-off point 0.4 m
     (`STANDOFF_M`) back from the pose that reaches it, facing the object, from the direct side first, then from
     ±45°, ±90°, ±135°, 180° around it (`APPROACH_SIDES`, each side once per task); the next move drives straight in.
   - The arm base's position in the base frame is not known from a drawing: it starts at (0, 0) and is learned from
     the object seen before and after a move that turned the base ≥ 15° (`arm_offset`), kept in
     `data/fetch_calib.json` (`arm_xy_in_base_m`); the look after every move corrects the rest.
   After every move the object is looked for again: YOLO first; else it is remembered on the map (`remember`,
   `expected`: its map position from the base pose, the arm yaw and offset; its top and table moved by the lift
   change) and looked for with depth only where it should be (`skills.locate`: a 90 mm grid around it, points
   above half its height). Depth only tells whether it is still there; a pick always needs a YOLO box measured with
   depth (a depth-only position was 45 mm off on 2026-10-16 and the gripper knocked the cup over). Depth sees only
   table there → "It is not where I saw it", the whole search. Otherwise back off 0.15 m, turn 20° each way, looking
   again after each; still no YOLO box but depth sees it → "please move it a little", the task ends; nothing seen
   at all → the whole search. The arm base offset is the median of the last 9 measurements (`OFFSET_SAMPLES`).
   An object's width is only trusted within 250 mm of the pick zone (`WIDTH_NEAR_MM`: the tumbler measured 85–88 mm at
   1.14 m, 76–81 mm up close): a too wide / too narrow one further away is approached and measured again.
   Still out of reach → "I can't reach it, please move it closer to me", look every 2 s for 30 s, go on when it is
   reachable, else task failed.
6. Pick (`skills.reachable_pick`): the taught grasp turned about the vertical every 15° all the way round
   (`GRASP_YAWS`, nearest the taught one first; the cup stays upright at every one), each with two IK seeds: `ready`'s
   arm configuration and the same with the wrist flipped (J4 + 180, −J5, J6 + 180). The first that works: a joint
   move from `look` to 10 cm above the cup (no joint more than 200°), checked with `kine_forward` at 11 points to
   never take the gripper more than 2 cm below both ends (`PATH_SAG_MM`), straight down and up passing IK, and the
   straight line from above to `carry` with the cup passing too (`fetch._carry_ok`: IK at 20 points, ≤ 25° per
   joint between two, lean ≤ 15°), so a pick never ends where the cup can't be carried. Measured with the
   controller's IK (2026-10-16, top −340 mm): grasps exist only for y ≤ ~700 mm, 1–4 options per spot, about 1 s to
   plan. The turn is kept and the cup is put down turned the same way.
7. Up, then straight to `carry` (`_line_holding`: the straight move is IK-checked at 20 points and the cup's lean at each must stay within `MAX_TILT_DEG`; measured 2.5° from four pick spots, against 36° for a joint move), then straight to `look` (5.9° lean). A turned grasp can't go straight to `look` (a joint jumps 30–80° on the way, IK 2026-10-16), so `carry` is passed through. No `ready`.
8. Drive to the destination in `look`; the gripper's holding signal is read every second, a drop stops the base
   ("I dropped it"). Not in `carry`: there the hand is ~0.3 m before the base's front and 23 cm lower than in
   `look`; every drive in `carry` stalled (p6 and home on 2026-10-15, p9 on 2026-10-16: the base only edged, and
   `distance_probe` showed a live obstacle 0.5 m ahead in an aisle that is free on the map), while the owner's drives
   from the AGV test tool with the arm in `look` went. Likely the base's front 3D camera sees the hand; not proven.
9. Finish:
   - `hold`: stay in `look`, status `holding`; wait for "give" or "place".
   - `place`: in `look` (in `carry` the held cup covers the torso camera's view of the table), the same search as
     step 4 (the arm stays in `look` while the base turns), at each try (`_place_here`, `place_spots`): the pick spot itself when the
     base has not moved since the pick (2 cm, 2°); then free spots of a grid (x −260…−60, y 640…740 mm) where the
     torso depth camera sees table at the pick table's height, every one checked at its centre and 8 points 50 mm
     around it (`skills.on_table`; the camera service writes `/dev/shm/lumi_depth_torso.npy`). The camera sees a
     table at −403 mm only from y ≈ 640 mm, a lower one further (−414: ≈ 655, −457: ≈ 690); a ring point on the near
     side below the view is checked 25 mm from the centre instead. Free: 110 mm from every thing seen standing on the
     table; a box no higher than the table is the table itself under another name (a round white table read "sink"
     and "chair"). No spot →
     "I can't see a free place on the table". Then straight to above the spot, put down, back to `look`.
     Nothing is put down unless the table in front is measured right then (`table_ahead`: at least 4 grid points
     at table height); the height the object was picked from is never taken instead (2026-10-16 the cup was put
     down at p9 on nothing).
     No spot in reach but a table seen further away (`far_table`: depth surface on a grid x −700…500, y 720…1600 mm
     at a height some lift can work at, the point nearest (−160, 670) mm whose 50 mm ring is all table; every table
     point is tried, the nearest ones lie on a round table's edge): the base brings that point to (−160, 670) mm
     (`PLACE_GOAL`) the same way as for a pick (step 5, up to 5 moves), then the grid again.
     A table lower than the proven one at lift 0 logs "table at −457 mm: the lift stays at 0 mm (its end)"; one the
     lift is right for, without "(its end)".
9a. "Put it on the orange chair" (`brain.place_on`, `fetch._put_on`): the named thing (table words, chair, stool,
    sofa, or any class the cameras name: "the white sink"; a colour if said, grey / gray, purple, pink too) is searched
    like an object, its flat top measured with depth; within reach of the lift it is approached and the object put
    on it (spots around its centre, then place grid spots within 0.4 m of it at its top's height), else Lumi says
    how much lower / higher it is than a table. The cameras label furniture badly (one white table was "white chair"
    to one camera, "white sink" to the other): when no thing of the named class is in view but one of the named colour
    is, under any class but small round things, with a flat top at a workable height, that one is used. "The grey
    table" with no such thing in view: any table in view, as for "put it on the table". The dialog reads it back with
    the held object: "Put the white cup on the grey table." With an empty hand a place command is refused at once.
    A thing's colour can be taught (`POST /objects/teach {"name": "chair", "colour": "yellow"}`: the nearest one
    seen, kept by its map place in `data/known_things.json`); within 0.5 m of that place it has that colour from
    any side (`colour_of`), since a colour read from the box changes with the view.
    Before every turn on the spot the arm's sweep is checked against lidar + map (`turn_hits`, 0.10 m), with the
    torso depth camera at the arm's real height (`depth_hits`; the arm's own parts within 120 mm do not count), and
    then with the head camera turned 60° to the side of the turn (`head_hits`, `HEAD_SIDE_DEG`, pitch −5°; the torso
    camera sees only ahead, the arm sweeps to the side); the head goes back to where it was. Without the head
    calibration only the first two decide. `head_hits` not yet run live.
9b. What is in the hand is checked at every command (fetch, place, give, carry; `fetch._in_hand`): the torso depth
    camera looks at the cup's axis 30–70 mm below the grasp point, projected from the arm's joints
    (`skills.hand_sees`: depth within 60 mm of it = an object, more than 250 mm behind = empty); only when it
    can't tell, AI_1. Live: an empty hand reads "empty"; a held cup gave no depth ("unknown", too near the camera),
    so a held object is decided by AI_1. A fetch always opens the gripper first and stops if it stays closed.
10. Carry to another place (while holding): the dashboard's To (From is hidden while holding) or "bring it to p1"
    → `look`, drive with the drop watch, keep holding (`fetch.carry_to`, `POST /tasks/carry`). A command that names a
    place and a finish ("go to p5 and put it on the table", "give it to me at p9"; the place from the text, else the
    dialog's To) drives there first, then puts it down (step 9) or gives it (step 11) (`carry_to(dest, then)`,
    `POST /tasks/carry {"dest", "then": "place" | "give"}`). "put it on the table" alone puts it down where Lumi
    stands. A command while holding is never a new fetch: the object stays in the hand until it is put down or given.
    What is held is remembered: a pick (also a mission's pick step) or a named receive stores `held_object`
    (`{"object", "colour"}`) in the state file, kept across tasks and an API restart and cleared whenever `holding`
    goes false (put down, given, dropped, hand opened). `fetch.held_name()` says it ("I'm holding the white cup",
    "Put the white cup on the table near me."); "something" only when the hand was taken over without a pick.
11. Give (while holding): `look` → `give` straight (IK-checked), say "Here you go. Hold it and say thank you.", open
    only on "thank you" (voice) or Release (dashboard Command dialog, `POST /tasks/release`), then `look`. Nobody
    releases within `GIVE_WAIT_S` 30 s: "I'll keep holding it", back to `look`, still `holding` (it is never dropped).
    A pull can't be felt: with the cup in the closed gripper AI_1's median stayed 2780–2870 during gentle pulls (only
    its noise grew, sd 20 → 50–75), and the fingers settling after the move changed it by 192.

Base move geometry: the object's position in the arm base frame is turned into the base frame by the angle between
the two frames (`arm_yaw_in_base_deg`) plus the arm base's offset (`arm_xy_in_base_m`, step 5). That angle is measured once on the robot with `tasks/fetch.py measure-axis [object]`: the arm stands at
`look` (or `ready`) with a few objects in the torso camera's view; the base drives 10 cm straight forward with `/api/joy_control`
at 0.05 m/s (`AXIS_SPEED`; not navigation, which can turn in place while the arm is over the table). Every object seen
steady before and after (matched by class) is used; the yaw is fitted as an exact rigid motion that includes the
base's own turn during the drive (1.14° on the first 10 cm run). The base always drives back, also after an error. At
`ready` the gripper covers the right part of the torso view, so objects there can disappear after the move. Result (2026-10-14, arm at `look`): the base
drove 0.100 m forward, −0.003 m sideways and turned −1.25°; cup (−235, 1000) → (−261, 894) mm and chair (−862, 1280) →
(−900, 1155) mm in the arm base frame. Fit with both: arm yaw in the base frame −86.2° (replaced 2026-10-19, below). Single objects give −88.0° (cup), −85.0° (chair) and −89.2° (bowl, an earlier run): spread
about ±2°, about 1 cm on a 30 cm shift. The arm and both cameras sit on the waist and turn with it, so the waist angle
of the run is kept too (`waist_deg`), and the arm yaw and the arm offset in the base frame are corrected by the waist
turn since then (`fetch._waist_turn`; the waist axis is taken at the base centre, not measured). Run again
2026-10-19 at waist −20.31° with two cups: −96.4, −94.9, −95.5°, kept **−95.5°** (median); objects are paired before /
after one to one, nearest first (`_pairs`; a run that paired both cups with one gave −136.4°). Results:
[15 §8](15_PICK_AND_PLACE.md). The waist-corrected base shift is not yet run live. The drive back ended 3.5 mm from the start with −1.6° heading drift in total
(straight `joy_control` drives turn about 1° per 10 cm). Without `data/fetch_calib.json`, step 5 does not move the
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
the white cup, where should I put it first?" (`held_name()`).

## 5. Dashboard

A **Command** button next to Settings opens a dialog in the middle of the screen (a click outside or Esc closes it):

While holding, the command is read by the rules only (fast): the object named is the held one, a marker
named anywhere is where to bring it (else To), "give" / "put it on the table" what to do there, "bring it to
p2" a carry; a new fetch ("take the bottle from p2") is refused with the held object's name. Below the read
sentence, selects correct it: Object, Colour and At the end (hold / put on the table) for a fetch, At the end
(hold / put on the table / give) for a carry. Start / Go / Give / Place starts it at once.

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
| `state() -> dict` | `{"status", "step", "task", "holding", "held_object", "log", "since"}`, read from `/dev/shm/lumi_task.json` so any process sees it |

`say(en, ko)` is a callback for spoken progress (the assistant passes one that speaks in the current language).
Status values: `idle`, `running`, `holding`, `done`, `failed`, `stopped`.

API (`api/server.py`): `POST /tasks/parse` (typed text → task / give / place, sentence, problems), `POST /tasks/fetch` (a task), `POST /tasks/describe` (sentence + problems), `POST /tasks/give`,
`POST /tasks/place`, `POST /tasks/stop`, `GET /tasks/state`. While the assistant runs, start / give / place are
forwarded to it (`/dev/shm/lumi_cmd.json`, commands `fetch`, `fetch_give`, `fetch_place`, `fetch_stop`) because it owns
the robot; stop also stops the base and arm directly.

## 7. Tests

Without the robot: `tests/test_fetch.py` (task validation, read-back, approach geometry (turn + straight, sides, arm offset), the step order with fake
drivers, stop at every step), `tests/test_fetch_intents.py` (EN / KO commands, unknown words, corrections,
confirmation answers). On the robot, with the owner at the STOP: empty cup first, slow, one step at a time.
