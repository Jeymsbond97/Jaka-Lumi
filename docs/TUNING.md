# Tuning values

Every value here is a constant at the top of its file, with a comment on what it means. Change it there, then restart
what uses it (README "Deploying a change"): `systemctl --user restart lumi-api` for the API and fetch (check
`curl -s localhost:8100/status` → `base.move_status` is not `running` first), `.venv/bin/python vision/camview.py --stop`
and `--start` for the detector. Line numbers may move; search the name.

## Arm speed

| File:line | Name | Now | What it does |
|---|---|---|---|
| `robot/motion.py:29` | `JOINT_SPEED` | slow 10, normal 25, route 40 °/s | Joint move speeds. "normal" / "route" are also the dashboard's Arm pose card "Normal" / "Fast". **route 40 is an estimate**, not run live yet |
| `robot/motion.py:30` | `JOINT_ACCEL` | slow 30, normal 75, route 200 °/s² | Joint move acceleration per speed (vendor: under 720). **route 200 is an estimate** |
| `robot/motion.py:31` | `LINEAR_SPEED` | slow 20, normal 50 mm/s | Straight move speeds |
| `robot/motion.py:32` | `ACCEL_FACTOR` | 3.0 | Straight moves: acceleration = speed × this per second |
| `manipulation/arm_route.py` | `SPEED` | "route" | Joint moves along the pose graph (to `look`, `carry`, `give`, `tuck`, `wave_out`, `wave_start`, `wave`) with an empty hand, all sent at once; the wave's way up |
| `manipulation/arm_route.py` | `HOLD_SPEED` | "slow" | The same with something in the hand: one move at a time, each to a full stop |
| `manipulation/arm_route.py` | `TOL` | 10 | **Estimate**: the controller's transition radius (`joint_move` `tol`, no unit in the vendor doc) at each via-point of an empty-hand route (wave_out on the wave's way up and down): the arm blends through instead of stopping. The corner cut (half of each move next to it) is checked. 0 = a full stop at each via-point, still with no pause |
| `manipulation/skills.py:40` | `EMPTY_SPEED` | "normal" | Arm with nothing in the hand: the joint move from `look` to above a cup |
| `manipulation/skills.py:42` | `HOLDING_SPEED` | "slow" | With an object in the hand, and the last 10 cm down onto an object and up from it |
| `manipulation/skills.py:50` | `ABOVE_MM` | 100 mm | Height above the grasp from where the arm goes straight down (slow) |
| `tasks/fetch.py:41` | `MAX_TILT_DEG` | 15° | How far a held cup may lean on any move |
| `manipulation/wave.py` | `SWINGS` | 2 | The wave: times `wave_start` → `wave` → `wave_start` (the two taught poses, J3 −2.5° ↔ −17.2°) |
| `manipulation/wave.py` | `SWING_SPEED` | "normal" | `motion.JOINT_SPEED` of the swings, all queued (the owner liked 25 °/s); the way up goes as `arm_route.goto` |
| `robot/motion.py` | `SLOW_DEG_S`, `EXTRA_S` | 5 °/s, 10 s | The longest a joint move may take: the largest joint travel summed over the queued moves at this slow rate (or 3× the planned time if longer), plus `EXTRA_S`; then the arm is stopped. Measured: long moves ran 4.3–7 °/s whatever the speed asked |
| `robot/motion.py` | `STILL_S` | 2 s | An arm standing this long, not at the end and the controller's queue not empty, has stopped short: stopped, the rest of the queue dropped |
| `manipulation/arm_route.py` | `HEAD_CLEAR_MM` | 250 mm | **Estimate**: the gripper (flange, grasp point, finger tips) keeps this from the head's turning centre (`head_cam.head_centre()`) on every pose-graph move, the wave and straight moves with an object; the head camera is 102 mm from it, the head's size is not measured (`look` keeps 327 mm; look → tuck passes at 175 mm and is refused) |
| `manipulation/arm_route.py` | `EDGES` | give–carry, carry–look, look–wave_out, wave_out–wave_start, wave_start–wave, look–ready, look–tuck | The only joint moves between named poses |
| `manipulation/arm_route.py` | `JOIN_DEG` | 20° | An arm at no pose (free drive, stopped half way) joins the graph by one checked joint move only when every joint is this close to a pose; else it does not move and asks to be brought near `look` |
| `manipulation/arm_route.py` | `AT_POSE_DEG`, `EXACT_DEG` | 3°, 1° | At a pose for programs and `check` / further than 1° from the nearest pose a route first goes to it |

## Lift and base

| File:line | Name | Now | What it does |
|---|---|---|---|
| `tasks/fetch.py` | `SURFACE_Z` | −560 … −30 mm | Arm-frame heights (after the lift) of surfaces the arm picks from / puts on; outside: refused (floor, low seats) |
| `tasks/fetch.py:64` | `LIFT_VEL` | 20 % | Lift speed in fetch |
| `robot/head.py` | `LIFT_MAX_MM` | 105 mm | **Temporary**: highest lift anything moves to (the head camera cable is too short). Set back to 250 when the longer cable is in; `fetch.LIFT_RANGE`, `LIFT_TRIES` and the dashboard jog follow it |
| `tasks/fetch.py:62` | `LIFT_DRIVE_MM` | 75 mm | Lift height for every drive and at every task's end |
| `tasks/fetch.py:96` | `AXIS_SPEED` | 0.05 m/s | Straight drives with `joy_control` (the last part of a reach, measure-axis) |
| `tasks/fetch.py:71` | `STRAIGHT_MAX_M` | 0.6 m | A reach needing a longer drive than this goes by navigation; shorter ones turn on the spot and drive straight |
| `tasks/fetch.py:72` | `STANDOFF_M` | 0.4 m | Navigation stops this far back from the pose that reaches the object, facing it; the rest is a straight drive (navigation does not go near a table) |
| `tasks/fetch.py:75–76` | `BASE_HALF_M`, `CLEAR_M` | 0.255 + 0.05 m | A straight drive is checked every 5 cm (lidar + map, `/api/map/distance_probe`) and ends where the base centre would come closer than their sum to an obstacle. The lidar sees table legs, maybe not a table top's edge: keep `CLEAR_M` |
| `tasks/fetch.py` | `SELF_MM` | 120 mm | Depth this near the arm's own points is the arm itself in the camera's view (turn check) |
| `tasks/fetch.py` | `ARM_CLEAR_M`, `SWEEP_STEP_DEG` | 0.10 m, 10° | Before turning on the spot: flange, grasp point and finger tips must stay this far from anything the lidar / map shows, checked every this many degrees |
| `tasks/fetch.py:90–91` | `STUCK_S`, `STUCK_M` | 30 s, 0.1 m | A navigation drive that has not moved this far in this time is cancelled |
| `tasks/follow.py` | `FOLLOW_GAP_M` | 1.0 m | "Follow me": camera distance kept to the person; nearer, the base stands still |
| `tasks/follow.py` | `FOLLOW_MAX_MS`, `SPEED_GAIN`, `ACCEL_MS2` | 0.15 m/s, 0.8 /s, 0.4 m/s² | Follow speed cap (estimate), m/s per m beyond the gap, speed-up limit |
| `tasks/follow.py` | `TURN_GAIN`, `TURN_MAX_RS`, `TURN_DEAD_DEG`, `TURN_ONLY_DEG` | 1.0, 0.5 rad/s, 5°, 30° | Turning toward the person: gain, cap, no turn within, no forward beyond (turn first) |
| `tasks/follow.py` | `STALE_S`, `LOST_S` | 0.5 s, 2 s | No fresh sighting: stand still; none for this long: "I lost you" |
| `tasks/follow.py` | `RELOCK_DEG`, `RELOCK_M` | 25°, 0.8 m | A lost track is swapped for a fresh one this near the person's last angle and distance (estimates) |
| `tasks/follow.py` | `HEAD_YAW_MAX`, `HEAD_PITCH`, `HEAD_STEP_DEG`, `HEAD_VEL` | 90°, 10°, 5°, 50 % | Head turned toward the person while following: yaw limit, fixed pitch, smallest move, speed |
| `tasks/follow.py` | `BRAKE_S` | 0.5 s | Each follow command is checked where the base (`BASE_HALF_M + CLEAR_M`) and the arm (`ARM_CLEAR_M`) would be this much later |
| AGV panel `:9001` | navigation speed | AGV setting | Speed of drives to markers and points; an AGV setting, change only with the owner |

## Search and reach

| File:line | Name | Now | What it does |
|---|---|---|---|
| `tasks/fetch.py` | `VIEW_STEPS` | 60°, 120°, 180° | Search: after ahead, both cameras look this far to the busier side step by step, then to the other side |
| `tasks/fetch.py` | `WAIST_SCAN_MAX` | 120° | The waist turns up to this in the search (body limit ±140° absolute), the head turns the rest |
| `tasks/fetch.py` | `SEARCH_BASE_DEG` | 180°, 90° | Then the base turns towards the busier side, the first of these whose sweep is clear, and all again |
| `tasks/fetch.py` | `LIFT_TRIES` | 0, 105 mm (`LIFT_RANGE`) | Nothing found: all of it again at the other end |
| `tasks/fetch.py:70` | `APPROACH_TRIES` | 5 | Base moves to bring an object into reach before asking the person |
| `tasks/fetch.py:49` | `PICK_ZONE_CENTRE` | (−100, 580) mm | Where a base move brings an object (arm base frame) |
| `tasks/fetch.py:83–84` | `LOST_BACK_M`, `LOST_TURN_DEG` | 0.15 m, 20° | An object lost after a base move: back off, turn each way, look again |
| `tasks/fetch.py` | `WIDTH_NEAR_MM` | 250 mm | A width further than this from the pick zone does not refuse a pick (far widths read ~8 mm too wide); measured again up close |
| `manipulation/skills.py` | `MIN_WIDTH`, `MAX_WIDTH` | 61, 92 mm | Object widths the gripper takes (belly open 96, tips open 88 / close to 59; docs/gripper) |
| `manipulation/skills.py` | `BELLY_MIN_MM` | 72 mm | Thinner objects are held between the finger tips (the belly closes only to 70 mm) |
| `manipulation/skills.py` | `TIPS_GRASP_MM` | 0 mm | For those the arm stops this much higher (25 was too high: the tips closed above the cup) |
| `manipulation/skills.py` | `TIP_CLEAR_MM`, `ROUND_BITE_MM` | 10, 10 mm | Round things (apple, orange, ball): the finger tips (`TIP_MM` 60, not measured) stay this far above the table; the grasp point at least this far below the top, else refused. Estimates |
| `manipulation/skills.py` | `GRASPS` | cup upright; apple, orange, sports ball round; the rest refused | Which classes are picked and how |
| `tasks/fetch.py` | `PICK_TRIES` | 2 | A missed / slipped pick is tried this often |
| `manipulation/skills.py` | `SEEN_UNDER_MM` | 8 mm | Added to the camera's width to get the width the fingers meet (`grip_width`), which the limits above are compared with |
| `tasks/fetch.py` | `HEAD_READS`, `HEAD_SAME_MM` | 4, 120 mm | Head camera frames read per view; a thing counts when seen at least twice within this distance |
| `tasks/fetch.py` | `HEAD_SIDE_DEG` | 60° | Head yaw towards the side of a turn on the spot, for the arm-sweep check (`head_hits`) |
| `tasks/fetch.py` | `HEAD_LOW_PITCH` | −5° | Head pitch for the search and `head_hits` (its lowest, where the head camera is calibrated) |
| `manipulation/skills.py` | `FRAME_LAG_S`, `FRESH_WAIT_S` | 0.15 s, 2 s | After a lift / waist / head / base move, depth and detections come from the first frame written this long after it (no fixed wait); give up after the second |
| `tasks/fetch.py` | `COAST_S` | 0.3 s | Frames after a straight `joy_control` drive are taken from this long after the stop (estimate) |
| `tasks/fetch.py` | `DRIVE_POLL_S`, `DRIVE_START_S` | 0.2 s, 3 s | Base status reads while driving; a drive not seen "running" counts as over after the second (at once when it reports "succeeded" at the goal pose) |
| `tasks/fetch.py:98` | `GIVE_WAIT_S` | 30 s | Giving: no "thank you" / Release by then, keep holding it |

## Missions

| File | Name | Now | What it does |
|---|---|---|---|
| `assistant/steps.py` | `MOVE_MAX_M` | 3.0 m | Longest single `move` in a mission; longer is refused before it starts |
| `tasks/fetch.py` | `MOVE_SPEED` | 0.10 m/s | Speed of a mission `move` (straight, joy_control); estimate |
| `tasks/fetch.py` | `SHORT_MOVE_M` | 0.10 m | A shorter `move` goes at `AXIS_SPEED` (measured exact at 10 cm) |
| `tasks/fetch.py` | `SPEED_STEP`, `SPEED_MIN`, `SPEED_MAX` | 0.2, 0.4, 1.6 | "Faster" / "slower" by voice: step and limits as parts of the normal speed (moves `MOVE_SPEED` × it; estimate) |
| `tasks/fetch.py` | `NAV_SPEED_MPS`, `NAV_TURN_RADS` | 0.3 m/s, 0.3 rad/s | Navigation's own limits (`/api/get_params`) = normal; voice only lowers the linear one (`/api/set_params`) |
| `assistant/driving.py` | `MOVE_MAX_M`, `MOVE_MIN_M` | 3 m, 0.01 m | Longest / shortest drive by voice; outside is refused with the limit |
| `assistant/driving.py` | `TINY_M`, `SPAN_M`, `STEP_M`, `LITTLE_M`, `DEFAULT_M` | 0.05, 0.2, 0.5, 0.5, 1 m | "A tiny bit" / 살짝, 한 뼘, one step, "a little" / 조금, no amount said; estimates |
| `tasks/fetch.py` | `RECEIVE_WAIT_S` | 30 s | `receive`: nothing put in the hand by then, the mission fails with the hand open |
| `assistant/steps.py` | `WAIT_SHORT_S` | 10 s | "wait a moment", "잠깐 기다렸다가": how long a short wait is |
| `assistant/steps.py` | `WAIT_MAX_S` | 30 min | Longest wait step (and receive wait); longer is refused before it starts |
| `assistant/steps.py` | `WAIT_GIVE_S` | 5 min | "wait until someone gives you the cup": the hand is held out this long, then the mission fails there |
| `assistant/steps.py` | `WAIT_ORDER_S` | 5 min | "do what they tell you": no instruction by then, the mission goes on with its rest |
| `tasks/fetch.py` | `RECEIVE_REACH_MM`, `RECEIVE_SHORT_MM`, `RECEIVE_MIN_MM` | 150, 100, 20 mm | "Take this from my hand": the open hand moves at most this far from `give` towards the thing in the hand, stops this far before it, leaves out a shorter move. Estimates |
| `tasks/fetch.py` | `POINT_STEPS_MM` | 0, ±50, ±100 mm | "Put it here" with pointing: spot grid around the pointed point |
| `tasks/fetch.py` | `RECEIVE_DI_S` | 0.5 s | `receive`: the finger sensor (DI_1) must see something this long before Lumi asks the person to let go (the hand closes on their "okay") |
| `tasks/fetch.py` | `MOVE_SEGMENT_M` | 0.25 m | A mission `move` is driven in pieces this long; the way of the base and the arm is checked again before each |

## Placing

| File | Name | Now | What it does |
|---|---|---|---|
| `tasks/fetch.py` | `PLACE_GRID_X`, `PLACE_GRID_Y` | x −260…−60 step 40, y 640…740 mm | Place spots tried in front (after the pick spot); IK refuses the ones out of reach |
| `tasks/fetch.py` | `PLACE_GOAL` | (−160, 670) mm | Where the base brings a table spot seen further away |
| `tasks/fetch.py` | `FAR_R_MM`, `FAR_HALF_DEG`, `FAR_IN_MM` | 0.6–3 m, ±45°, 150 mm | A table further away: level tops looked for on sight lines this far, within this of where the camera looks; the base goes to the point this far in from its nearest edge |
| `tasks/fetch.py` | `TOP_NEAR_MM` | 1500 mm | A named thing's top measured further away is not trusted: the base goes closer first |
| `tasks/fetch.py` | `FURNITURE` | table, chair, couch, bench, bed, sink, toilet, desk | Classes the cameras mix up: a named piece of furniture matches any of them in its colour |
| `manipulation/skills.py` | `FLAT_DEG`, `FLAT_PATCH`, `TABLE_MIN_POINTS` | 12°, 7 × 7 px 3 px apart, 6 | A table height: the depth around a sight line must lie on a plane leaning less than this; at least this many such points within `TABLE_TOL_MM` |
| `tasks/fetch.py` | `NEAR_THING_MM` | 400 mm | Place grid spots this near a named thing ("the white sink"), at its top's height, count as on it |
| `manipulation/skills.py` | `TABLE_RING_MM`, `TABLE_TOL_MM` | 50 mm, 25 mm | A place spot must be table at its centre and 8 points this far around, within this of the table height |
| `manipulation/skills.py` | `TABLE_NEAR_RING_MM` | 25 mm | A near-side ring point below the camera's view is checked this far from the centre instead |
| `manipulation/skills.py` | `FREE_MM` | 110 mm | A place spot keeps this far from things standing on the table |

## Detection

| File:line | Name | Now | What it does |
|---|---|---|---|
| `vision/person.py:34` | `OBJECT_SCORE` | 0.35 | Lowest YOLO score for an object |
| `vision/person.py:35` | `WEAK_SCORE` | cup 0.05 | Lower score for cups, kept only when depth measures a cup-sized thing (`vision/objects.py` `WEAK`) |
| `vision/objects.py:37` | `WEAK` | cup: width 40–110, height 50–250 mm | Size a weak cup box must have |
| `vision/reid.py` | `FACE_SAME`, `SAME` | 0.30, 0.90 | Same person: face cosine (a track's first faces against the person's mean face) at least this; without both faces, clothes likeness at least this. Measured on the head camera: one person back 0.51–0.74 face, 0.48–0.97 clothes; other people ≤ 0.08 face, up to 0.86 clothes |
| `assistant/lumi.py` | `FACE_FRAMES`, `FACE_WAIT_S` | 3, 1.0 s | Faces seen on a new track before Lumi decides who it is and greets; without them it waits at most this long after `HOLD_S`, then the clothes decide |
| `vision/reid.py` | `FACE_MAX_M`, `FACE_SCORE` | 2.0 m, 0.85 | Faces are looked for only this close, and kept from this detector score (turned faces are not) |
| `vision/reid.py` | `FORGET_S` | 600 s | Someone not seen this long is new again: the full greeting |
| `assistant/lumi.py` | `RECENT_S` | 150 s | Back within this while the talk was open: Lumi listens on without a word; later, or after a goodbye: "Welcome back! How can I help you?" |
| `vision/person.py:41` | `ZOOM` | 3 torso crops | Parts of the frame looked at a second time, bigger |
| `manipulation/skills.py:56` | `MIN_SEEN` | 5 of 8 frames | An object must be seen this often at the same place |
| `manipulation/skills.py` | `HAND_PROBE_MM`, `HAND_NEAR_MM`, `HAND_FAR_MM` | 30/50/70, 60, 250 mm | In-hand check by depth (`hand_sees`) |

## Voice

| File:line | Name | Now | What it does |
|---|---|---|---|
| `assistant/voice_words.py` | `VOLUME_STEP` | 10 % | One "speak louder" / "quieter" step of the speaker mixer (`data/volume.txt`, also songs) |
| `assistant/voice_words.py` | `VOLUME_MIN`, `VOLUME_MAX` | 30 %, 90 % | Limits for the voice commands (the dashboard may set any value; "louder" never lowers it) |
| `assistant/voice_words.py` | `SPEED_STEP` | 0.1 | One "speak slower" / "faster" step of the Supertonic speed (`data/speech_speed.txt`) |
| `audio/mouth.py` | `SPEED`, `SPEED_MIN`, `SPEED_MAX` | 0.92, 0.72, 1.2 | Speaking speed without a stored value, and the limits (Supertonic takes 0.7–2.0) |
| `audio/mouth.py` | `SPLIT_WORDS` | 8 words | A first sentence this long is said in two parts, cut after its first comma (3 words in or later): the voice starts ~1 s sooner |
| `assistant/llm_direct.py` | `KEEP_EVERY_S` | 60 s | How often Ollama is told to keep the model loaded (it doesn't see the direct requests) |
