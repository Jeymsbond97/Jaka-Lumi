# Tuning values

Every value here is a constant at the top of its file, with a comment on what it means. Change it there, then restart what uses it (top-level README, "Deploying a change"): `systemctl --user restart lumi-api` for the API and fetch (first check that `curl -s localhost:8100/status` → `base.move_status` is not `running`), `.venv/bin/python vision/camview.py --stop` and `--start` for the detector. "Estimate" marks a value not taken from a measurement or a datasheet.

## Arm speed

| File | Name | Default | What it does |
|---|---|---|---|
| `robot/motion.py` | `JOINT_SPEED` | slow 10, normal 25, route 40 °/s | Joint move speeds. "normal" / "route" are the dashboard's Arm pose card "Normal" / "Fast". route: estimate |
| `robot/motion.py` | `LINEAR_SPEED` | slow 20, normal 50 mm/s | Straight move speeds |
| `robot/motion.py` | `ACCEL_FACTOR` | 3.0 | Straight moves: acceleration = speed × this per second |
| `robot/motion.py` | `JOINT_ACCEL_FACTOR` | 1.5 | Joint moves: acceleration = speed × this per second (route 60 °/s², normal 37.5, slow 15). Lower = softer start and stop, longer moves. Estimate |
| `manipulation/arm_route.py` | `SPEED` | "route" | Joint moves along the pose graph (to `look`, `carry`, `give`, `ready`, `wave_out`, `wave_start`, `wave`) with an empty hand; the wave's way up |
| `manipulation/arm_route.py` | `HOLD_SPEED` | "slow" | The same with something in the hand |
| `manipulation/skills.py` | `EMPTY_SPEED` | "normal" | Arm with nothing in the hand: the joint move from `look` to above a cup |
| `manipulation/skills.py` | `HOLDING_SPEED` | "slow" | With an object in the hand, and the last 10 cm down onto an object and up from it |
| `manipulation/skills.py` | `ABOVE_MM` | 100 mm | Height above the grasp from where the arm goes straight down (slow) |
| `manipulation/skills.py` | `MAX_TILT_DEG` | 15° | How far a held cup may lean on any move (`tasks/fetch.py` uses the same) |
| `manipulation/wave.py` | `SWINGS` | 2 | The wave: times `wave_start` → `wave` → `wave_start` (the two taught poses, J3 −2.5° ↔ −17.2°) |
| `manipulation/wave.py` | `SWING_SPEED` | "normal" | `motion.JOINT_SPEED` of the swings. The swings are queued back to back (no stop between them); the way up goes as `arm_route.goto`, with a stop at each pose |
| `manipulation/wave.py` | `ARRIVE_SPEED` | "normal" | The way up's last move, `wave_out` → `wave_start` (J1 60°); "slow" for a softer arrival |
| `robot/motion.py` | `SLOW_DEG_S`, `EXTRA_S` | 5 °/s, 10 s | The longest a joint move may take: its largest joint travel at this slow rate (or 3× the planned time if longer), plus `EXTRA_S`; then the arm is stopped. Long moves run at 4.3–7 °/s whatever speed is asked |
| `robot/motion.py` | `STILL_S` | 2 s | An arm standing this long short of its target has stopped short: stopped, nothing more sent |
| `robot/motion.py` | `SETTLE_S` | 0.3 s | After each arrival (inpos, joints within 0.3°) the arm stands this long before the next move of a route or wave. Estimate |
| `manipulation/arm_route.py` | `HEAD_CLEAR_MM` | 250 mm | The gripper (flange, grasp point, finger tips) keeps this from the head's turning centre (`head_cam.head_centre()`) on every pose-graph move, the wave and straight moves with an object. The head camera is 102 mm from that centre; `look` keeps 327 mm. Estimate (head size not measured) |
| `manipulation/arm_route.py` | `EDGES` | give–carry, carry–look, look–wave_out, wave_out–wave_start, wave_start–wave, look–ready | The only joint moves between named poses |
| `manipulation/arm_route.py` | `JOIN_DEG` | 20° | An arm at no pose (free drive, stopped half way) joins the graph by one checked joint move only when every joint is this close to a pose; else it does not move and asks to be brought near `look` |
| `manipulation/arm_route.py` | `AT_POSE_DEG`, `EXACT_DEG` | 3°, 1° | At a pose for programs and `check` / further than 1° from the nearest pose a route first goes to it |
| `api/dashboard.html` | `MAP_POLL_MS` | 20000 ms | The dashboard reads the map's markers again this often (markers added on the base, a map switched) |

## Lift and base

| File | Name | Default | What it does |
|---|---|---|---|
| `tasks/fetch.py` | `SURFACE_Z` | −560 … −30 mm | Arm-frame heights (after the lift) of surfaces the arm picks from / puts on; outside: refused (floor, low seats) |
| `tasks/fetch.py` | `LIFT_VEL` | 20 % | Lift speed in fetch |
| `robot/head.py` | `LIFT_MAX_MM` | 105 mm | Highest lift anything moves to, limited by the head camera cable (250 with a longer cable); `fetch.LIFT_RANGE`, `LIFT_TRIES` and the dashboard jog follow it |
| `tasks/fetch.py` | `LIFT_DRIVE_MM` | 75 mm | Lift height for every drive and at every task's end |
| `tasks/fetch.py` | `AXIS_SPEED` | 0.05 m/s | Straight drives with `joy_control` (the last part of a reach, measure-axis) |
| `tasks/fetch.py` | `STRAIGHT_MAX_M` | 0.6 m | A reach needing a longer drive than this goes by navigation; shorter ones turn on the spot and drive straight |
| `tasks/fetch.py` | `STANDOFF_M` | 0.4 m | Navigation stops this far back from the pose that reaches the object, facing it; the rest is a straight drive (navigation does not go near a table) |
| `tasks/fetch.py` | `BASE_HALF_M`, `CLEAR_M` | 0.255 + 0.05 m | A straight drive is checked every 5 cm (lidar + map, `/api/map/distance_probe`) and ends where the base centre would come closer than their sum to an obstacle. The lidar sees table legs, not always a table top's edge |
| `tasks/fetch.py` | `SELF_MM` | 120 mm | Depth this near the arm's own points is the arm itself in the camera's view (turn check) |
| `tasks/fetch.py` | `ARM_CLEAR_M`, `SWEEP_STEP_DEG` | 0.10 m, 10° | Before turning on the spot: flange, grasp point and finger tips must stay this far from anything the lidar / map shows, checked every this many degrees |
| `robot/nav_guard.py` | `MARGIN_M`, `LOOKAHEAD_M`, `STEP_M`, `TURN_AHEAD_S` | 0.10 m, 0.30 m, 0.15 m, 0.5 s | While navigation drives (go to, missions, fetch legs, come here, dock): flange, grasp point and finger tips are checked at the base's pose, turned on at its turn rate for `TURN_AHEAD_S`, and every `STEP_M` along the planned path up to `LOOKAHEAD_M`; an arm point nearer than `MARGIN_M` to anything the lidar / map shows (and nearer than now) cancels the move. Estimates |
| `robot/nav_guard.py` | `CLEAR_S`, `BLOCK_S` | 1 s, 10 s | The same goal is sent again after the way has been clear this long; blocked this long in all: "I stopped: my arm would hit something on the way" |
| `tasks/fetch.py` | `STUCK_S`, `STUCK_M` | 30 s, 0.1 m | A navigation drive that has not moved this far in this time is cancelled |
| `assistant/lumi.py` | `FOLLOW_VOICE_DEG`, `FOLLOW_SORRY_S` | 35°, 20 s | While following, a voice this near the followed person's angle is theirs (estimate); the "I'm following someone" line at most this often |
| `tasks/follow.py` | `FOLLOW_GAP_M`, `NEAR_STOP_M` | 1.0 m, 0.8 m | "Follow me": camera distance kept to the person (nearer: no forward); nearer than `NEAR_STOP_M` no turn either. Estimate |
| `tasks/follow.py` | `FOLLOW_MAX_MS`, `SPEED_GAIN` | 0.5 m/s, 0.8 /s | Follow speed cap (joy_control's own clamp, [05_AGV_BASE.md](05_AGV_BASE.md)); speed = their walking speed + this per m beyond the gap |
| `tasks/follow.py` | `ACCEL_MS2`, `DECEL_MS2` | 0.5, 0.8 m/s² | Speeding up / slowing down limits; never faster than lets the base stop at the gap with `DECEL_MS2` after `REACT_S`. Estimates |
| `tasks/follow.py` | `REACT_S` | 0.3 s | From the person stopping to the base braking (frame, track, tick, command); with `DECEL_MS2` it sets the follow distance while walking (~1.3 m at 0.5 m/s). Estimate |
| `tasks/follow.py` | `TURN_GAIN`, `TURN_MAX_RS`, `TURN_ACCEL_RS2`, `TURN_DEAD_DEG`, `TURN_ONLY_DEG` | 1.5, 0.6 rad/s, 2.0 rad/s², 5°, 35° | Turning toward the person: gain, cap, change limit, no turn within, no forward beyond (turn first) |
| `tasks/follow.py` | `STALE_S`, `COAST_S`, `LOST_S` | 0.4 s, 1.0 s, 3 s | A sighting older than `STALE_S` is not new; unseen, the base drives on toward where they should be for `COAST_S`, then slows; "I lost you" after `LOST_S` |
| `tasks/follow.py` | `VEL_TAU_S`, `WALK_MAX_MS` | 0.5 s, 2 m/s | Walking-velocity filter time constant; faster estimates are noise |
| `tasks/follow.py` | `JUMP_M`, `GATE_GROW_MS`, `SWITCH_M`, `RELOCK_LOOK` | 0.5 m, 0.7 m/s, 0.15 m, 0.6 | Keeping the person: a sighting further than `JUMP_M` (+ `GATE_GROW_MS` per s unseen) from where they should be is someone else; another track must be `SWITCH_M` nearer to be taken; clothes `reid.same` below `RELOCK_LOOK` never taken. Estimates |
| `tasks/follow.py` | `HEAD_YAW_MAX`, `HEAD_PITCH`, `HEAD_STEP_DEG`, `HEAD_LEAD_S`, `HEAD_VEL` | 180°, 10°, 3°, 0.3 s, 50 % | Head on the person while following: yaw limit (the body API range; right behind it keeps the side it came from), fixed pitch, smallest move, sent where they will be this much later, speed |
| `tasks/follow.py` | `BRAKE_S`, `BLOCKED_END_S` | 0.5 s, 5 s | Each command is checked where the base (`BASE_HALF_M + CLEAR_M`) and the arm (`ARM_CLEAR_M`) would be this much later; blocked this long: "Something is in my way" |
| `tasks/follow.py` | `TICK_S`, `LOG_S` | 0.1 s, 1 s | Command rate (steady); `follow: v … w … driven … person … head … tick` line (driven = the base's real speed from its pose) in `logs/lumi_console.log` |
| `assistant/lumi.py` | `MATCH_DEG_PER_M` | 10 °/m | Person tracking: each m of distance difference counts as this many degrees when a detection is given to a track. Estimate |
| `vision/person.py` | `HEAD_POLL_S` | 0.1 s | Head yaw read this often by the camera service (a person's angle is off by the head's turn in this time) |
| AGV panel `:9001` | navigation speed | AGV setting | Speed of drives to markers and points; an AGV setting, changed only by the owner |

## Search and reach

| File | Name | Default | What it does |
|---|---|---|---|
| `tasks/fetch.py` | `VIEW_STEPS` | 60°, 120°, 180° | Search: after ahead, both cameras look this far to the busier side step by step, then to the other side |
| `tasks/fetch.py` | `WAIST_SCAN_MAX` | 120° | The waist turns up to this in the search (body limit ±140° absolute), the head turns the rest |
| `tasks/fetch.py` | `SEARCH_BASE_DEG` | 180°, 90° | Then the base turns towards the busier side, the first of these whose sweep is clear, and all again |
| `tasks/fetch.py` | `LIFT_TRIES` | 0, 105 mm (`LIFT_RANGE`) | Nothing found: all of it again at the other end |
| `tasks/fetch.py` | `APPROACH_TRIES` | 5 | Base moves to bring an object into reach before asking the person |
| `tasks/fetch.py` | `PROGRESS_MM` | 40 mm | A base move that brought the object less than this nearer its goal (odometry) did nothing: that way is not tried again from there |
| `tasks/fetch.py` | `GOAL_SHIFTS_MM` | 0, −120, +120 mm | The straight way in aims the object at the pick zone, then this far to either side of it (a small turn and in) |
| `tasks/fetch.py` | `APPROACH_SIDES` | 0, ±45, ±90, ±135, 180° | Then navigation to each of these sides of the object, once; a side where the base can't stand near enough is skipped |
| `manipulation/skills.py` | `COMFORT_R_MM` | 710 mm | A cup further than this from the arm base (where the waist can bring it) is brought nearer by the base first when it can. Estimate |
| `manipulation/skills.py` | `TRUSTED_YAW_DEG` | 15° | Grasp turns up to this are tried first; larger ones only when the base can't bring the cup nearer |
| `tasks/fetch.py` | `KEPT_MM`, `TORSO_HALF_DEG` | 150 mm, 30° | After a base move the object is the one seen this near where its map place says; the waist turns the torso camera to it when it is further than this off the view |
| `tasks/fetch.py` | `GOAL_OUT_MM`, `VIEW_MARGIN_PX` | 0–200 mm in 20 mm steps, 10 px | The base brings a cup further out than the pick zone when the torso camera would not see its middle there (a low table); "in view" is this far inside the image |
| `tasks/fetch.py` | `NEAR_GAP_M`, `NEAR_BACK_M` | 0.15 m, 0.3 m | Nothing seen ahead and something this near the base: back off this much and look again before the whole search |
| `tasks/fetch.py` | `FAR_SPOTS` | 4 | Spots of a table seen further away tried from where the base stands before going closer |
| `tasks/fetch.py` | `WAIST_REACH_STEPS` | 0, ±15, ±30° | A pick out of reach: waist turns tried around the one bringing the object to the pick zone's bearing, before a base move |
| `tasks/fetch.py` | `WAIST_FOUND_MM` | 80 mm | After that waist turn the object must be seen this near where it should be |
| `manipulation/skills.py` | `IK_SEEDS` | ready, look, carry, give | Taught poses whose arm configurations (and wrist flips) seed the pick / place IK |
| `tasks/fetch.py` | `PICK_ZONE_CENTRE` | (−100, 580) mm | Where a base move brings an object (arm base frame) |
| `tasks/fetch.py` | `LOST_BACK_M`, `LOST_TURN_DEG` | 0.15 m, 20° | An object lost after a base move: back off, turn each way, look again |
| `tasks/fetch.py` | `WIDTH_NEAR_MM` | 250 mm | A width further than this from the pick zone does not refuse a pick (far widths read ~8 mm too wide); measured again up close |
| `manipulation/skills.py` | `MIN_WIDTH`, `MAX_WIDTH` | 72, 92 mm | Object widths the gripper takes (belly open 96, closed 70; tips open 88 / close to 59; [10_GRIPPER.md](10_GRIPPER.md)). `MIN_WIDTH` 61 enables the finger-tip grasp (61–72 mm) |
| `manipulation/skills.py` | `BELLY_MIN_MM` | 72 mm | Thinner objects are held between the finger tips (the belly closes only to 70 mm) |
| `manipulation/skills.py` | `TIPS_OFFSET` (`data/grasp_tips_teach.json` `tips_offset_flange`) | [−0.4, −4.6, 28.2] mm | Finger-tip grasp: the object's axis goes this far from the hooks' belly centre (flange frame, level, turned with the grasp); taught |
| `manipulation/skills.py` | `TIP_CLEAR_MM`, `ROUND_BITE_MM` | 10, 10 mm | Round things (apple, orange, ball): the finger tips (`TIP_MM` 60, estimate) stay this far above the table; the grasp point at least this far below the top, else refused. Estimates |
| `manipulation/skills.py` | `BELOW_SHOULDER_MM` | 80 mm | Bottles: the grasp point this far below where the body begins; the hand's lowest part (`TIP_MM` below) must stay `TIP_CLEAR_MM` above the table under it (`table_near`, else the bottle's lowest point seen) |
| `vision/objects.py` | `SLICE_MM`, `BODY_PCT`, `BODY_FRACTION` | 10 mm, 75, 0.9 | A bottle's width profile (`objects.body`): slices this thick; its body as wide as this percentile of the slices; the body begins at the first slice from the top this much as wide |
| `manipulation/skills.py` | `GRASPS` | cup upright; apple, orange, sports ball round; the rest refused | Which classes are picked and how |
| `tasks/fetch.py` | `PICK_TRIES` | 2 | A missed / slipped pick is tried this often |
| `manipulation/skills.py` | `SEEN_UNDER_MM` | 8 mm | Added to the camera's width to get the width the fingers meet (`grip_width`), which the limits above are compared with |
| `tasks/fetch.py` | `HEAD_READS`, `HEAD_SAME_MM` | 4, 120 mm | Head camera frames read per view; a thing counts when seen at least twice within this distance |
| `tasks/fetch.py` | `HEAD_SIDE_DEG` | 60° | Head yaw towards the side of a turn on the spot, for the arm-sweep check (`head_hits`) |
| `tasks/fetch.py` | `HEAD_LOW_PITCH` | −5° | Head pitch for the search and `head_hits` (its lowest, where the head camera is calibrated) |
| `manipulation/skills.py` | `FRAME_LAG_S`, `FRESH_WAIT_S` | 0.15 s, 2 s | After a lift / waist / head / base move, depth and detections come from the first frame written this long after it (no fixed wait); give up after the second |
| `tasks/fetch.py` | `COAST_S` | 0.3 s | Frames after a straight `joy_control` drive are taken from this long after the stop. Estimate |
| `tasks/fetch.py` | `DRIVE_POLL_S`, `DRIVE_START_S` | 0.2 s, 3 s | Base status reads while driving; a drive not seen "running" counts as over after the second (at once when it reports "succeeded" at the goal pose) |
| `tasks/fetch.py` | `GIVE_WAIT_S` | 30 s | Giving: no "thank you" / Release by then, keep holding it |

## Missions

| File | Name | Default | What it does |
|---|---|---|---|
| `assistant/steps.py` | `MOVE_MAX_M` | 3.0 m | Longest single `move` in a mission; longer is refused before it starts |
| `tasks/fetch.py` | `MOVE_SPEED` | 0.10 m/s | Speed of a mission `move` (straight, joy_control). Estimate |
| `tasks/fetch.py` | `SHORT_MOVE_M` | 0.10 m | A shorter `move` goes at `AXIS_SPEED` |
| `tasks/fetch.py` | `SPEED_STEP`, `SPEED_MIN`, `SPEED_MAX` | 0.2, 0.4, 1.6 | "Faster" / "slower" by voice: step and limits as parts of the normal speed (moves `MOVE_SPEED` × it). Estimates |
| `tasks/fetch.py` | `NAV_SPEED_MPS`, `NAV_TURN_RADS` | 0.3 m/s, 0.3 rad/s | Navigation's own limits (`/api/get_params`) = normal; voice only lowers the linear one (`/api/set_params`) |
| `assistant/driving.py` | `MOVE_MAX_M`, `MOVE_MIN_M` | 3 m, 0.01 m | Longest / shortest drive by voice; outside is refused with the limit |
| `assistant/driving.py` | `TINY_M`, `SPAN_M`, `STEP_M`, `LITTLE_M`, `DEFAULT_M` | 0.05, 0.2, 0.5, 0.5, 1 m | "A tiny bit" / 살짝, 한 뼘, one step, "a little" / 조금, no amount said. Estimates |
| `tasks/fetch.py` | `RECEIVE_WAIT_S` | 30 s | `receive`: nothing put in the hand by then, the mission fails with the hand open |
| `assistant/steps.py` | `WAIT_SHORT_S` | 10 s | "wait a moment", "잠깐 기다렸다가": how long a short wait is |
| `assistant/steps.py` | `WAIT_MAX_S` | 30 min | Longest wait step (and receive wait); longer is refused before it starts |
| `assistant/steps.py` | `WAIT_GIVE_S` | 5 min | "wait until someone gives you the cup": the hand is held out this long, then the mission fails there |
| `assistant/steps.py` | `WAIT_ORDER_S` | 5 min | "do what they tell you": no instruction by then, the mission goes on with its rest |
| `tasks/fetch.py` | `RECEIVE_REACH_MM`, `RECEIVE_SHORT_MM`, `RECEIVE_MIN_MM` | 150, 100, 20 mm | "Take this from my hand" and "reach out to me": the hand moves at most this far from `give` towards the thing in the hand (or their hand), stops this far before it, leaves out a shorter move. Estimates |
| `tasks/fetch.py` | `REACH_BODY_MM` | 300 mm | "Reach out to me" with no hand of theirs seen: the hand stops this far before the person's body. Estimate |
| `assistant/lumi.py` | `REACH_FRONT_DEG` | 20° | "Reach out to me": a person further to the side is turned to first with the waist (Patrol) or asked to stand in front (Greeter). Estimate |
| `assistant/lumi.py` | `REACH_HOLD_S` | 30 s | The hand stays held out this long after a reach without "thanks" / "okay", then the arm folds back to `look`. Estimate |
| `tasks/fetch.py` | `POINT_STEPS_MM` | 0, ±50, ±100 mm | "Put it here" with pointing: spot grid around the pointed point |
| `tasks/fetch.py` | `RECEIVE_DI_S` | 0.5 s | `receive`: the finger sensor (DI_1) must see something this long before Lumi asks the person to let go (the hand closes on their "okay") |
| `tasks/fetch.py` | `MOVE_SEGMENT_M` | 0.25 m | A mission `move` is driven in pieces this long; the way of the base and the arm is checked again before each (also what the base rolls on meanwhile, `JOY_HOLD_S` 0.5 s); the base does not stop between pieces |
| `tasks/fetch.py` | `MOVED_MIN_PART`, `MOVED_CHECK_M` | 0.5, 0.1 m | A move whose base pose went less than this part of the distance driven by time stops and says the wheels did not move (checked from 0.1 m on). Estimate |

## Placing

| File | Name | Default | What it does |
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

| File | Name | Default | What it does |
|---|---|---|---|
| `vision/person.py` | `OBJECT_SCORE` | 0.35 | Lowest YOLO score for an object |
| `vision/person.py` | `WEAK_SCORE` | cup 0.05 | Lower score for cups, kept only when depth measures a cup-sized thing (`vision/objects.py` `WEAK`) |
| `vision/objects.py` | `WEAK` | cup: width 40–110, height 50–250 mm | Size a weak cup box must have |
| `vision/reid.py` | `FACE_SAME`, `SAME` | 0.30, 0.90 | Same person: face cosine (a track's first faces against the person's mean face) at least this; without both faces, clothes likeness at least this. Typical on the head camera: the same person 0.51–0.74 face, 0.48–0.97 clothes; other people ≤ 0.08 face, up to 0.86 clothes |
| `assistant/lumi.py` | `FACE_FRAMES`, `FACE_WAIT_S` | 3, 1.0 s | Faces seen on a new track before Lumi decides who it is and greets; without them it waits at most this long after `HOLD_S`, then the clothes decide |
| `vision/reid.py` | `FACE_MAX_M`, `FACE_SCORE` | 2.0 m, 0.85 | Faces are looked for only this close, and kept from this detector score (turned faces are not) |
| `vision/reid.py` | `FORGET_S` | 600 s | Someone not seen this long is new again: the full greeting |
| `assistant/lumi.py` | `RECENT_S` | 150 s | Back within this while the talk was open: Lumi listens on without a word; later, or after a goodbye: "Welcome back! How can I help you?" |
| `vision/person.py` | `ZOOM` | 3 torso crops | Parts of the frame looked at a second time, bigger |
| `vision/scene.py` | `HAND_CROPS_PX`, `HELD_SCORE` | 320, 640 px; 0.2 | Squares around each hand the detector looks at again; handheld classes count there from this score |
| `assistant/seeing.py` | `LOOKS`, `SURE`, `STEADY_S` | 3, 0.35, 30 s | "What am I holding": fresh looks at most; a held box this sure counts from one look (weaker: two looks agree); the same thing keeps its colour this long unless two looks agree on another |
| `vision/scene.py` | `COLOUR_CORE`, `WB_V_PCT`, `WB_MAX_S`, `WB_GAIN` | 0.6; 90, 100; 0.8–1.25 | A held thing's colour from this middle part of its box; white balance from the scene's brightest pale pixels, gains limited |
| `vision/scene.py` | `PALM`, `BLOB_MM`, `BLOB_SHARE` | 0.6 / 0.35 forearm, 100 mm, 0.25 | Something without a class in a hand: not-skin pixels past the wrist at its depth over this share (estimates) |
| `vision/scene.py` | `SIT_THIGH`, `STAND_THIGH`, `CROUCH_THIGH`, `CROUCH_DROP` | 0.45, 0.6, 0.1, 0.8 | Posture: knee below hip / ankle below hip as parts of the torso length (estimates) |
| `vision/scene.py` | `VLM_HAND_MODEL`, `VLM_HAND_WIDTH`, `VLM_HAND_TIMEOUT_S` | gemma4:e4b, 320 px, 12 s | The model, picture width and wait for the close look at a hand (26b took 18–33 s per picture, e4b 2–13 s) |
| `manipulation/skills.py` | `MIN_SEEN` | 5 of 8 frames | An object must be seen this often at the same place |
| `manipulation/skills.py` | `HAND_PROBE_MM`, `HAND_NEAR_MM`, `HAND_FAR_MM` | 30/50/70, 60, 250 mm | In-hand check by depth (`hand_sees`) |

## Voice

| File | Name | Default | What it does |
|---|---|---|---|
| `assistant/voice_words.py` | `VOLUME_STEP` | 10 % | One "speak louder" / "quieter" step of the speaker mixer (`data/volume.txt`, also songs) |
| `assistant/voice_words.py` | `VOLUME_MIN`, `VOLUME_MAX` | 30 %, 90 % | Limits for the voice commands (the dashboard may set any value; "louder" never lowers it) |
| `assistant/voice_words.py` | `SPEED_STEP` | 0.1 | One "speak slower" / "faster" step of the Supertonic speed (`data/speech_speed.txt`) |
| `audio/mouth.py` | `SPEED`, `SPEED_MIN`, `SPEED_MAX` | 0.92, 0.72, 1.2 | Speaking speed without a stored value, and the limits (Supertonic takes 0.7–2.0) |
| `audio/mouth.py` | `SPLIT_WORDS` | 8 words | TTS on the CPU only (GPU engines not loaded): a first sentence this long is said in two parts, cut after its first comma (3 words in or later), so the voice starts ~1 s sooner. On the GPU a sentence is said whole |
| `audio/mouth.py` | `STEPS` | 4 | Supertonic synthesis steps (quality / speed). On the GPU a step takes a few ms, on the CPU 0.1–0.27 s |
| `audio/mouth.py` | `NOISE_SEED` | 7 | The fixed noise every sentence starts from (one voice for every sentence; another seed is a slightly different voice) |
| `audio/mouth.py` | `ECHO_MIN`, `ECHO_TOP_DB`, `ECHO_MIN_FRAMES`, `ECHO_LAG_S`, `ECHO_KEEP_S` | 0.6, 15 dB, 12, −0.3…1.0 s, 30 s | Lumi's own voice in the clip mic: a clip-mic utterance whose spectrogram (16 bands, its frames within `ECHO_TOP_DB` of its loudest, at least `ECHO_MIN_FRAMES`) correlates at least `ECHO_MIN` with what the speaker played `ECHO_LAG_S` earlier is dropped before whisper (`mouth.own_voice`; check: `tests/echo_check.py`). Estimate |
| `audio/tts_gpu.py` | `MAX_LEN` | 640 | Longest text / latent (~44 s of speech) the TensorRT engines take; longer goes to the CPU. A change needs `tts_gpu.py build` |
| `audio/ears.py` | `WHISPER_MODEL` | `ggml-large-v3-turbo.bin` (f16) | Speech-to-text model; takes effect when the whisper-server is started again (check: `tests/asr_check.py`) |
| `audio/ears.py` | `PROMPT`, `LANG_PROMPT` | "Hi Lumi. Hey Lumi. 루미야."; one per language | Whisper's prompt (spells the name); `LANG_PROMPT` when asked again in one language |
| `audio/ears.py` | `MIN_LOGPROB` | −1.0 | Below this average log-probability Lumi asks to say it again |
| `audio/ears.py` | `KO_BONUS`, `ODD_KO_BONUS` | 0.3, 0.3 | How much more a Hangul transcription counts when whisper named another language / wrote English with a word no dictionary has |
| `audio/ears.py` | `VAD_P`, `MIN_SPEECH_S` | 0.3, 0.1 s | A sound needs this many seconds of 32 ms frames Silero calls speech (probability above `VAD_P`), else it is music or noise and never reaches whisper. Higher drops more music but also short words ("네.", "Stop." are 0.3–0.4 s) |
| `audio/ears.py` | `SPEECH_PER_SYLLABLE` | 0.05 s | A text needs this much speech per syllable, else it came from music |
| `audio/ears.py` | `NOT_SAID` | no word, a leading "-", 자막 / 시청해 주셔서 / thanks for watching | Whisper's subtitle texts for music, dropped |
| `audio/ears.py` | `BEAM_SIZE` | 0 (greedy) | Whisper beam search |
| `audio/sing.py` | `BANK_SIM`, `BANK_MARGIN` | 0.80, 0.05 | Song bank (`assistant/song_bank.py`): words this similar (bge-m3) to a wording that asks for a song / the songs, and this much closer than to any wording of another kind, sing / list at once without the LLM. Lower catches more and risks wrong songs |
| `audio/sing.py` | `BANK_MIN_WORDS` | 3 | The song bank reads only words with a song / music word and at least this many words |
| `audio/ears.py` | `MERGE_WAIT_S` | 1.5 s | A sentence cut off by a pause (it ends on "let's", "can you", "and", "저기" …: `CUT_OFF`) waits this long for the rest, heard as one sentence (`mic.END_SILENCE` is 0.6 s) |
| `audio/mic.py` | `EARLY_QUIET_S`, `EARLY_MIN_S`, `EARLY_MAX_S` | 0.3 s, 0.4 s, 4.0 s | After this much quiet inside an utterance (0.4–4 s long so far) whisper starts on it; the result is used when the utterance ends with no new speech. Longer utterances are talk with pauses, where each early run delays the last |
| `audio/ears.py` | `SAME_WORDS` | 0.8 | Korean-tagged text in Latin letters asked again in English is taken as English when the two readings' letters match this much (difflib ratio) |
| `audio/ears.py` | `STOCK`, `REPEAT` | 감사합니다, thank you, hey, hi, bye (not 네 / yes); a 2+ word phrase three times | Dropped: stock words written for a sound whisper took for another language; whisper repeating itself |
| `audio/sing.py` | `FILLER`, `FILLER_KO`, `VERB_KO` | word lists | Words around a song request that are never a title; any other word where a title goes ("sing ___", "___ 노래", "by ___") is a song Lumi doesn't have: said so, its own offered |
| `assistant/llm_direct.py` | `KEEP_EVERY_S` | 60 s | How often Ollama is told to keep the model loaded (it doesn't see the direct requests) |

## Web answers

| File | Name | Default | What it does |
|---|---|---|---|
| `assistant/web.py` | `SEARCH_WAIT_S` | 2.0 s | All sources get this long together (Naver, Wikipedia ~0.7 s, Google News 0.4–1.6 s); a slower one is left out |
| `assistant/web.py` | `PAGE_CHARS`, `BLOCK_CHARS`, `WIKI_CHARS` | 1500, 600, 500 chars | Text of the search page, of one part of it, of the Wikipedia summary given to the LLM; Korean is ~1 token a char and the runner reads ~1300 tokens/s |
| `assistant/web.py` | `NEWS_ITEMS` | 3 | Headlines given, only for questions about what changes (`NEWSY`) |
| `assistant/web.py` | `SEARCH_TTL`, `WEATHER_TTL` | 600 s | A search / weather answer is reused this long |
| `assistant/web.py` | `WEATHER_DAYS` | 7 | Days of forecast given with the weather ("tomorrow", "모레", "this weekend") |
| `assistant/web.py` | `TOWN` | 50000 people | A smaller geocoded place is not taken for a "how far" distance (often a namesake) |
