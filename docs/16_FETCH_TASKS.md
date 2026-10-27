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
{"object": "apple",            # cup | apple | orange | sports ball (skills.GRASPS; others refused with the reason)
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
4. Look (`_look_around`, the one search for picking and placing): (a) ahead with both cameras: the torso camera
   sees near, low things (tables, what stands on them), the head camera (pitch −5°, where it is calibrated) far, high
   ones; not found → "Let me look around"; (b) the waist and the head turn together to the side where the base's
   lidar sees more things the map does not have (`first_side`: 3 angles × 3 distances each side,
   `/api/map/distance_probe` live < 0.3 m where the map is free for 0.5 m) step by step: both cameras look 60°, 120°
   and 180° that way (`VIEW_STEPS`; the waist, which carries the arm, the torso camera and the head, up to 120°
   (`WAIST_SCAN_MAX`, cut to the body's ±140° absolute), the head the rest), then the same to the other side; every
   waist turn is checked like a base turn (`_sweep_blocked`); a blocked one is left out and the head turns further
   instead; (c) only then the base turns 180° towards that side (90° when 180° is not clear; checked, never on the
   charger) and all of it again; (d) the lift to the other end of `LIFT_TRIES` (0 or 105 mm: down when it is above
   the middle) and (a)–(c) again. The waist and head stay where the thing was seen; nothing → the waist back to the
   front. Without the head calibration the head is left out; without the arm's yaw the waist is. The torso detector
   looks at the whole frame and again at three crops (`vision/person.py` `ZOOM`, ~2.7× bigger), so cups 1–3 m away are
   found too; cup boxes under 0.35 count only when depth measures a cup-sized thing (`objects.sized_like`), and `find`
   wants it in 5 of 8 frames at the same place. The head camera's detections (in the arm frame through `head_cam`)
   count when seen twice within `HEAD_SAME_MM` in `HEAD_READS` fresh frames; it only shows where to go: the base
   brings that place to the pick zone (`_go_to`: its map place is kept while the waist turns to the front, then
   `_approach`, step 5) and the search looks ahead again, where the torso camera finds it. Nothing anywhere → "I
   looked all around, but I can't see the cup", task failed. Of several of the object, the said colour, else the
   nearest, or the one the command says (`task["prefer"]`, `_rank`): small / big (camera width), near / far, left /
   right (the robot's: arm frame x, +x is its right). Read from the words by `brain.pick_prefer` for typed
   (`/tasks/parse`), spoken and mission pick steps: "the smaller cup", "the big cup", "the cup on the left", "the
   nearest cup", "the far one", "작은 컵", "큰 컵", "왼쪽(에 있는) 컵", "가까운 컵", "제일 먼 컵"; the read-back says it
   ("Take the smaller cup from here, …", "Take the cup on the left …", "여기에서 작은 컵을 …"). The said
   colour nowhere in the whole search, but the same object in another colour was seen: the base goes to the nearest
   such one and Lumi says "I couldn't see a blue cup, so I'm taking the white one." Written 2026-10-20, not yet run
   live.
   Frames are never read from before a move ended: after a lift, waist, head or base move, depth and detections are
   read from the first frame the camera service writes 0.15 s after it (`skills.moved` / `fresh`; depth comes every
   0.5 s) instead of a fixed wait.
4b. Table height: the depth surface on rings 80 / 110 mm around the object (`skills.table_near`). The lift is set to bring it as near the
   proven −403 mm as 0–105 mm allows (250 with the longer head camera cable) (`lift_for`; table 10 cm higher → lift 10 cm up, slow) and Lumi looks again. Any
   surface that ends between −560 and −30 mm in the arm frame is worked on (`SURFACE_Z`, from the grasp IK: a table
   top +300 … −200 mm from ours at lift 0 reachable, −250 partly, −300 (a chair seat) not at all); lower ones (floor,
   low seats) are never fitted. The torso
   camera sits on the same link as the arm base, so the lift does not change the camera calibration (checked: lift
   75 → 150 mm moved a cup x +2, y −2, top −76 mm). Every drive to a place is at lift 75 mm; the short base moves of a reach or a search keep the lift. At a put-down the same is done with
   the table in front (`fetch.table_ahead`), and the object goes down at that table's height.
5. Reach (`_reach`): the pick plan must pass IK. If not, the waist turns first (`_waist_reach`): it carries the arm
   round the column, so a cup beside Lumi is reached as one ahead is. The turn that brings the cup to
   `PICK_ZONE_CENTRE`'s bearing about the column (the head's turning centre), and `WAIST_REACH_STEPS` around it, are
   planned where the cup will be seen (`turned`); the first that passes turns the waist (its sweep checked, Patrol
   on), the camera looks again (the cup within `WAIST_FOUND_MM` of where it should be) and the pick is planned from
   that look. Then, if still out of reach, the base moves so the object comes to `PICK_ZONE_CENTRE`
   (−100, 580) mm, then Lumi looks again (lost: the whole search of step 4), fits the lift and plans again; at most
   `APPROACH_TRIES` 8 moves, never on the charger. One move (`_approach`, geometry in `approach_move` / `side_pose`):
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
   Comfort and order (night 5): a cup that would stay further than `skills.COMFORT_R_MM` (710 mm) from the arm base
   even after the waist brought it round (`at_edge`) is brought in by the base first while it can; grasp turns up to
   `skills.TRUSTED_YAW_DEG` (15°) first, larger turns only when the base can't help. The base goal is
   `pick_goal`: the pick zone, or up to 200 mm further out when the torso camera would not see the cup's middle
   there (a low table at lift 0). Every move is measured by odometry (`PROGRESS_MM` 40): a way that brought the cup
   no nearer is not tried again from there; the ways are: straight in, a small turn and in (`GOAL_SHIFTS_MM`, not
   when flush at something), navigation to each side once (a side where the base can't stand near enough is skipped
   without driving; a goal that left the base where it was counts as nothing). After every attempt, also a failed
   one, the cup is looked for where its map place says it is now (`_see_again` / `_kept`, the waist turning the torso
   camera to it, `KEPT_MM` 150): a plan never uses a spot from before a move. No way left: picked from where it
   stands when the arm reaches it (any grasp turn), else "I can't get closer to it, something is in my way. Please
   move it closer to me". Nothing seen ahead with something right at the base: back off 0.3 m and look again before
   the whole search. Tested offline in `tests/test_fetch_ways.py` with the live positions of 2026-10-26.
   Still out of reach → "I can't reach it, please move it closer to me", look every 2 s for 30 s, go on when it is
   reachable, else task failed.
6. Pick (`skills.reachable_pick`): the taught grasp turned about the vertical every 15° all the way round
   (`GRASP_YAWS`, nearest the taught one first; the cup stays upright at every one), each with the IK seeded from
   every `IK_SEEDS` pose (`ready`, `look`, `carry`, `give`) and the same with the wrist flipped (J4 + 180, −J5,
   J6 + 180); J1 / J4 / J6 answers are taken nearest the arm's angles (± 360° is the same pose) before the joint
   limits are checked. The first that works: a joint move from `look` to 10 cm above the cup (no joint more than
   200°), checked with `kine_forward` at 21 points like every pose-graph move (`skills.move_ok` =
   `arm_route.move_problem`: the gripper `HEAD_CLEAR_MM` from the head, never more than 2 cm below both ends,
   `PATH_SAG_MM`), straight down and up passing IK, and the
   straight line from above to `carry` with the cup passing too (`fetch._carry_ok`: IK at 20 points, ≤ 25° per
   joint between two, lean ≤ 15°), so a pick never ends where the cup can't be carried. Measured with the
   controller's IK at waist 0 with these checks: by the distance of the cup from the column and its bearing (+ left
   of ahead): 400 mm −15…+75°, 600 mm −15…+30°, 800 mm −30…−15°, nothing past 850 mm (offline kinematics,
   `robot/kinematics.py`, every 15°; cup top −260 mm at lift 75). The waist turn brings any bearing into that
   sector. A refused plan takes ~2 s offline. Put down tries the held turn first (straight from `look`); when that reaches no spot, every turn and wrist
   like the pick (step 9). The pick stores the table under the object (`_held["table"]`: from the cup's own bottom,
   else the ring of table around it, `skills.table_near`) and the lift, so put down knows the cup's height.
6a. Several of the object and no "which one" said: when the chosen one is out of reach (or measured the wrong size
   near), the others seen steadily here are tried, nearest first (`_other_here`), before the base moves. A pick that
   missed or slipped (the hand opened, the arm back at `look`) is looked for and tried once more (`PICK_TRIES`).
7. Up, then straight to `carry` (`_line_holding`: the straight move is IK-checked at 20 points and the cup's lean at each must stay within `MAX_TILT_DEG`; measured 2.5° from four pick spots, against 36° for a joint move), then straight to `look` (5.9° lean). A turned grasp can't go straight to `look` (a joint jumps 30–80° on the way, IK 2026-10-16), so `carry` is passed through. No `ready`.
8. Drive to the destination in `look`; the gripper's holding signal is read every second, a drop stops the base
   ("I dropped it"). Not in `carry`: there the hand is ~0.3 m before the base's front and 23 cm lower than in
   `look`; every drive in `carry` stalled (p6 and home on 2026-10-15, p9 on 2026-10-16: the base only edged, and
   `distance_probe` showed a live obstacle 0.5 m ahead in an aisle that is free on the map), while the owner's drives
   from the AGV test tool with the arm in `look` went. Likely the base's front 3D camera sees the hand; not proven.
9. Finish:
   - `hold`: stay in `look`, status `holding`; wait for "give" or "place".
   - `place`: in `look` (in `carry` the held cup covers the torso camera's view of the table), the search of step 4
     with, at every view (`_place_view`): the table in front (`table_ahead`) → the pick spot itself when the base has
     not moved since the pick (2 cm, 2°); then free spots of a grid (x −260…−60, y 640…740 mm) where the torso depth
     camera sees table at that height, every one checked at its centre and 8 points 50 mm around it
     (`skills.on_table`); a ring point on the near side below the view is checked 25 mm from the centre instead. Free:
     110 mm from every thing seen standing on the table; a box no higher than the table is the table itself under
     another name. Then straight to above the spot with the held grasp turn; when that line or the way down fails
     IK, the same spot with every grasp turn and wrist (`skills.place_options`: `GRASP_YAWS`, the held turn first, both
     IK seeds; a joint move from `look` to above it that keeps the gripper up (`PATH_SAG_MM`) and the cup within
     `MAX_TILT_DEG`, then straight down and up). An upright cup turned about its own axis stands the same, so any turn
     will do. Spots in order, nearest the pick zone centre first; put down, back to `look`. Live 2026-10-20 17:59 every
     spot failed IK with the held turn (0°) on a table measured right (−385 mm). The cup's top there: its height over
     the pick table (`_top_on`); that table not measured: as high as it was picked, moved by the lift since. Nothing
     is put down unless the table in front is measured right then.
     Table heights are the level top only (`skills.flat_top`): each sight line's depth patch (7 × 7 pixels) must lie on
     a plane leaning < 12° (`FLAT_DEG`), and the height is the median of the largest group within 25 mm, at least 6
     points (`TABLE_MIN_POINTS`). Live 2026-10-20 the median of every sight line read one round white table at −324 …
     −555 mm (chair backs and seats beside it, its edge); the level top alone reads −386 mm from the same frame
     (`tests/data/depth_torso_2026-10-20.npz`).
     No spot in reach but a table seen by either camera (`far_table`: level tops on sight lines 0.6–3 m away, ±45° of
     where the torso camera, else the head camera, looks): the base goes to it at once (`_go_to`, `PLACE_GOAL`
     (−160, 670) mm, the point 150 mm in from its nearest edge, `FAR_IN_MM`), then it looks ahead again, going closer
     up to 5 times; no second whole search. Before going, the spots of that table the arm reaches from here are tried
     (`_place_far`: its level points within 850 mm, comfortable ones first, `on_table`, IK; `FAR_SPOTS` 4): live
     2026-10-26 18:53 the near part of the table in front was hidden at lift 0 ("no table in view") and the base,
     stopped at the table, "drove" +0.13 m six times. The drives are measured as for the pick (step 5).
     "Put it on the table" with a big top (`BIG_TOPS`: table, desk, bed): its YOLO box centre moves with the view
     ((22, 623), then (-349, 647) for one table, 18:55), so it is never aimed at: the top is measured by the grid /
     the far table, spots are the grid near `PLACE_GOAL` first, then the far table's points.
     A table lower than the proven one at lift 0 logs "table at −457 mm: the lift stays at 0 mm (its end)".
9a. "Put it on the orange chair" (`brain.place_on`, `fetch._put_on`): the named thing (table words, chair, stool,
    sofa, or any class the cameras name; typed misspellings "dinning", "tabel"; "the table or chair" / "테이블이나
    의자": either counts, `alts`; a colour if said; which of several: lower / higher / smaller / bigger / nearer /
    farther, "the lower one", "낮은 / 높은 / 작은 / 큰 / 가까운 / 먼", `prefer`) is looked for with one search (step 4).
    First exactly what was said: its class among every label any frame gave the thing there (`skills.look` `names`:
    one white table was "chair", "sink" and "dining table" from frame to frame), its colour, a level top the arm can
    work at (`_top_of`: `flat_top` on a 100 mm disc; trusted within 1.5 m, `TOP_NEAR_MM`, else the base goes closer
    first); of several, the one `prefer` says (`_rank`), else the nearest; or one the head camera sees. Found: the
    base goes to it, the lift is fitted and the object put on it (spots around its centre, then place grid spots
    within 0.4 m of it at its top's height). Seen but out of the lift's reach: "The top of the orange chair is 30 cm
    lower than a table". Not seen: every surface the arm could use that was seen during the search (the table in
    front, a table further away, furniture with a level top; kept by map place with the label, colour, size and
    height the camera saw there, `_usable`) is ranked by what was said: its colour first, then its kind (furniture
    for furniture, `FURNITURE`), then `prefer`, else the nearest; the base goes to the best, puts it there and says
    "I couldn't find the black table, so I put the grey cup on the black chair here." Nothing usable: "I looked all
    around, but I can't see the white table, and no other table I could put it on." The dialog reads it back as
    understood: "Put the grey cup on the white dining table or chair.", "Put the grey cup on the lower table." With
    an empty hand a place command is refused at once. A thing's colour can be taught (`POST /objects/teach`,
    `data/known_things.json`); within 0.5 m of that place it has that colour from any side (`colour_of`).
    Every navigation drive (`agv.go` / `go_point`, also turns and the dashboard's go / route) is watched by
    `robot/nav_guard.py`: the arm's points along the planned path 0.30 m ahead; one that would come within 0.10 m of
    an obstacle cancels the move, the same goal goes again when the way is clear 1 s, after 10 s blocked the task
    fails with "I stopped: my arm would hit something on the way."
    Before every turn on the spot the arm's sweep is checked against lidar + map (`turn_hits`, 0.10 m), with the
    torso depth camera at the arm's real height (`depth_hits`; the arm's own parts within 120 mm do not count), and
    then with the head camera turned 60° to the side of the turn (`head_hits`, `HEAD_SIDE_DEG`, pitch −5°; the torso
    camera sees only ahead, the arm sweeps to the side); the head stays there (the next look or drive turns it). Without the head
    calibration only the first two decide. `head_hits` not yet run live.
9b. What is in the hand is checked at every command (fetch, place, give, carry; `fetch._in_hand`): the torso depth
    camera looks at the cup's axis 30–70 mm below the grasp point, projected from the arm's joints
    (`skills.hand_sees`: depth within 60 mm of it = an object, more than 250 mm behind = empty); only when it
    can't tell, AI_1. Live: an empty hand reads "empty"; a held cup gave no depth ("unknown", too near the camera),
    so a held object is decided by AI_1. A fetch always opens the gripper first and stops if it stays closed.
9c. "Put it here / there" with a pointing hand (`on` = `{"pointed": true}`, `_put_pointed`): the point from
    `vision/scene.py` `pointing_target()` (arm frame); a level table top around it (`flat_top`), the lift fitted, free
    spots on a grid around it (`POINT_STEPS_MM`, nearest first, `FREE_MM` from things on it); out of reach: the base
    brings the point to `PLACE_GOAL` and looks again. Nothing pointed at: "Where should I put it? Please point at the
    place and tell me again.", still holding. Not live.
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
object? I can pick up cup, apple, orange and sports ball."); a known thing the fingers can't take is refused with
its reason ("The bottle is too narrow at the top for my fingers…", [15 §10](15_PICK_AND_PLACE.md)). A missing destination is asked for; a missing source is
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
- **From / To** are always shown (From hidden while holding); what to take and its colour are written in the text.
  A typed fetch shows the places it names in them.
- Every Start obeys the Greeter / Patrol switches as voice does (`api/server.py` `_switches`): both off "Switch on
  Greeter or Patrol first."; a drive, a base or waist turn only with Patrol on; with Greeter only in place.
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
