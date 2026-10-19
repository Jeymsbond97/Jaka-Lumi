# Tuning values

Every value here is a constant at the top of its file, with a comment on what it means. Change it there, then restart
what uses it (README "Deploying a change"): `systemctl --user restart lumi-api` for the API and fetch (check
`curl -s localhost:8100/status` → `base.move_status` is not `running` first), `.venv/bin/python vision/camview.py --stop`
and `--start` for the detector. Line numbers are those of 2026-10-16; search the name if they moved.

## Arm speed

| File:line | Name | Now | What it does |
|---|---|---|---|
| `robot/motion.py:29` | `JOINT_SPEED` | slow 10, normal 25 °/s | Joint move speeds. "normal" is also the dashboard's Arm pose card "Normal" |
| `robot/motion.py:30` | `LINEAR_SPEED` | slow 20, normal 50 mm/s | Straight move speeds |
| `robot/motion.py:31` | `ACCEL_FACTOR` | 3.0 | Acceleration = speed × this per second |
| `manipulation/skills.py:40` | `EMPTY_SPEED` | "normal" | Arm with nothing in the hand: to `look`, home, the joint move to above a cup |
| `manipulation/skills.py:42` | `HOLDING_SPEED` | "slow" | With an object in the hand, and the last 10 cm down onto an object and up from it |
| `manipulation/skills.py:50` | `ABOVE_MM` | 100 mm | Height above the grasp from where the arm goes straight down (slow) |
| `tasks/fetch.py:41` | `MAX_TILT_DEG` | 15° | How far a held cup may lean on any move |

## Lift and base

| File:line | Name | Now | What it does |
|---|---|---|---|
| `tasks/fetch.py` | `SURFACE_Z` | −560 … −30 mm | Arm-frame heights (after the lift) of surfaces the arm picks from / puts on; outside: refused (floor, low seats) |
| `tasks/fetch.py:64` | `LIFT_VEL` | 20 % | Lift speed in fetch |
| `tasks/fetch.py:62` | `LIFT_DRIVE_MM` | 75 mm | Lift height for every drive and at every task's end |
| `tasks/fetch.py:96` | `AXIS_SPEED` | 0.05 m/s | Straight drives with `joy_control` (the last part of a reach, measure-axis) |
| `tasks/fetch.py:71` | `STRAIGHT_MAX_M` | 0.6 m | A reach needing a longer drive than this goes by navigation; shorter ones turn on the spot and drive straight |
| `tasks/fetch.py:72` | `STANDOFF_M` | 0.4 m | Navigation stops this far back from the pose that reaches the object, facing it; the rest is a straight drive (navigation does not go near a table) |
| `tasks/fetch.py:75–76` | `BASE_HALF_M`, `CLEAR_M` | 0.255 + 0.05 m | A straight drive is checked every 5 cm (lidar + map, `/api/map/distance_probe`) and ends where the base centre would come closer than their sum to an obstacle. The lidar sees table legs, maybe not a table top's edge: keep `CLEAR_M` |
| `tasks/fetch.py` | `SELF_MM` | 120 mm | Depth this near the arm's own points is the arm itself in the camera's view (turn check) |
| `tasks/fetch.py` | `ARM_CLEAR_M`, `SWEEP_STEP_DEG` | 0.10 m, 10° | Before turning on the spot: flange, grasp point and finger tips must stay this far from anything the lidar / map shows, checked every this many degrees |
| `tasks/fetch.py:90–91` | `STUCK_S`, `STUCK_M` | 30 s, 0.1 m | A navigation drive that has not moved this far in this time is cancelled |
| AGV panel `:9001` | navigation speed | AGV setting | Speed of drives to markers and points; an AGV setting, change only with the owner |

## Search and reach

| File:line | Name | Now | What it does |
|---|---|---|---|
| `tasks/fetch.py:65–66` | `SEARCH_TURN_DEG`, `SEARCH_TURNS` | 30°, 11 | Search: look, turn on the spot, look again, all the way round |
| `tasks/fetch.py:67` | `LIFT_TRIES` | 0, 250 mm | Nothing found: the same whole turn at these lifts |
| `tasks/fetch.py:70` | `APPROACH_TRIES` | 5 | Base moves to bring an object into reach before asking the person |
| `tasks/fetch.py:49` | `PICK_ZONE_CENTRE` | (−100, 580) mm | Where a base move brings an object (arm base frame) |
| `tasks/fetch.py:83–84` | `LOST_BACK_M`, `LOST_TURN_DEG` | 0.15 m, 20° | An object lost after a base move: back off, turn each way, look again |
| `tasks/fetch.py` | `WIDTH_NEAR_MM` | 250 mm | A width further than this from the pick zone does not refuse a pick (far widths read ~8 mm too wide); measured again up close |
| `manipulation/skills.py:53` | `MIN_WIDTH`, `MAX_WIDTH` | 45, 84 mm | Object widths the gripper takes |
| `tasks/fetch.py:98` | `GIVE_WAIT_S` | 30 s | Giving: no "thank you" / Release by then, keep holding it |

## Missions (docs/17)

| File | Name | Now | What it does |
|---|---|---|---|
| `assistant/steps.py` | `MOVE_MAX_M` | 3.0 m | Longest single `move` in a mission; longer is refused before it starts |
| `tasks/fetch.py` | `MOVE_SPEED` | 0.10 m/s | Speed of a mission `move` (straight, joy_control); estimate |
| `tasks/fetch.py` | `RECEIVE_WAIT_S` | 30 s | `receive`: nothing put in the hand by then, the mission fails with the hand open |
| `assistant/steps.py` | `WAIT_SHORT_S` | 10 s | "wait a moment", "잠깐 기다렸다가": how long a short wait is |
| `assistant/steps.py` | `WAIT_MAX_S` | 30 min | Longest wait step (and receive wait); longer is refused before it starts |
| `assistant/steps.py` | `WAIT_GIVE_S` | 5 min | "wait until someone gives you the cup": the hand is held out this long, then the mission fails there |
| `assistant/steps.py` | `WAIT_ORDER_S` | 5 min | "do what they tell you": no instruction by then, the mission goes on with its rest |
| `tasks/fetch.py` | `RECEIVE_DI_S` | 0.5 s | `receive`: the finger sensor (DI_1) must see something this long before Lumi asks the person to let go (the hand closes on their "okay") |
| `tasks/fetch.py` | `MOVE_SEGMENT_M` | 0.25 m | A mission `move` is driven in pieces this long; the way of the base and the arm is checked again before each |

## Detection

| File:line | Name | Now | What it does |
|---|---|---|---|
| `vision/person.py:34` | `OBJECT_SCORE` | 0.35 | Lowest YOLO score for an object |
| `vision/person.py:35` | `WEAK_SCORE` | cup 0.05 | Lower score for cups, kept only when depth measures a cup-sized thing (`vision/objects.py` `WEAK`) |
| `vision/objects.py:37` | `WEAK` | cup: width 40–110, height 50–250 mm | Size a weak cup box must have |
| `vision/person.py:41` | `ZOOM` | 3 torso crops | Parts of the frame looked at a second time, bigger |
| `manipulation/skills.py:56` | `MIN_SEEN` | 5 of 8 frames | An object must be seen this often at the same place |
| `manipulation/skills.py` | `HAND_PROBE_MM`, `HAND_NEAR_MM`, `HAND_FAR_MM` | 30/50/70, 60, 250 mm | In-hand check by depth (`hand_sees`) |
