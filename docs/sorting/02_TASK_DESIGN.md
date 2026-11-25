# 02 Task design

What Lumi does when SORT is pressed, which part is learned and which part is plain code.

---

## 1. The scene

```
                 Lumi (column; the arm hangs on its right side)
                        │
   ┌────────────────────┼───────────────────────────────┐  table
   │            [ red box ]  ( tray, 6 balls )  [ yellow box ]
   └─────────────────────────────────────────────────────┘
```

All positions in the arm controller's base frame (x across Lumi's front, y forward, z up), at lift 0.

| Item | Value | Why |
|---|---|---|
| Lift, waist, base | lift **0** (lowest), waist at the front, base parked; only the arm moves | at lift 75 mm (the cups' pick height) the arm cannot hold its fingers straight down at a ball's centre on the table; at lift 0 the table is 75 mm nearer and it can (reach map, `sim/sorting`) |
| Table | top at −328 mm (−403 mm at lift 75 mm, measured) | 01 §1 |
| Tray | wooden tray 28 × 19 × 2.5 cm (outer), centre (150, 550) mm, long side across | inside the area the hand reaches with its fingers straight down: x 0 … 500 mm, y 300 … 650 mm. The cups' pick centre (−100, 580) is outside it |
| Balls | foam golf practice balls, 42.5 mm, 8 g, red and yellow, 6 in the tray, 90 mm apart across and 75 mm forward | the hand reaches the table with its jaws turned about 45°: the fingers need room on the diagonals too |
| Boxes | two open boxes 26 × 18 × 8 cm without lids, short side facing the tray, 5 cm from it: centres (−130, 550) and (430, 550) mm | the drop point 45 mm above the rim is reachable over both; 5 cm leaves room for a finger beside an edge ball |
| Light | normal office light; trials also with the blinds open and closed | — |

The box positions are fixed and written in `data/sort_layout.json` on the Thor. A later version can find the boxes
with the camera.

**Torso camera:** with this layout the tray sits at the bottom right edge of the torso camera's picture (computed from
its calibration: the front right corner is just outside it), and the arm covers the tray while it works over it.
The head camera, pitched down, sees the whole tray from above; which camera finds the balls is decided on the robot.

### The balls' colours

- Red and yellow: far apart for the colour rule (red hue < 8 or ≥ 170, yellow 20 … 33). Red and orange are
  neighbours (bounds 8 and 20) and are not used together.
- White balls are possible later: the tray is brown, but the colour rule calls any low-saturation pixel white, grey
  or black.

---

## 2. One SORT run

```
SORT pressed
  │
  ├─ check: arm enabled, gripper fitted, hand empty, no other skill running, layout loaded
  ├─ arm to `look` (existing pose route)
  │
  └─ loop:
       ├─ look: steady balls on the plate (existing find(): 5 of 8 frames, 20 mm spread)
       ├─ none left → arm to rest pose, status done (balls sorted: n)
       ├─ pick the nearest steady ball; box = COLOUR_TO_BOX[colour]; unknown colour → skip it, say so
       ├─ run the policy episode (below) with goal (ball position, box position)
       ├─ check: gripper open, DI_1 / AI_1 show the hand empty, ball gone from the plate
       ├─ failure (missed grasp, dropped, timeout) → open, back to `look`, count it, try the next ball
       └─ three failures in a row → stop, status failed with the reason
```

| Part | Learned or code | Why |
|---|---|---|
| Finding balls, reading colour | existing vision code | already works to ~1 cm; colour is a rule |
| Choosing the box | code (`COLOUR_TO_BOX`) | a lookup; learning it adds nothing |
| Order of balls | code: nearest first | keeps the arm's path short and predictable |
| Reach, grasp, lift, carry, release | **policy** | the motor skill; this is the RL part |
| Moving to `look` and to rest | existing pose route | already checked for head clearance |
| Success and failure checks | code | uses the gripper signals and the camera after the episode |

---

## 3. One policy episode

The policy starts with the hand above the plate (the `look` pose or a fixed "ready above plate" pose, chosen when
the scene is built) and the gripper open. It is given:

- the ball's position (from the camera, refreshed while the ball is visible);
- the target box's position (from the layout file).

It outputs, at a fixed rate, a small move of the hand (x, y, z) and open or close. The episode ends when:

| End | Condition |
|---|---|
| Success | the ball is inside the target box's opening and the gripper has opened, hand above the box |
| Dropped | the ball leaves the hand anywhere but above the target box |
| Wrong box | the ball lands in the other box (counted separately: it means the goal input was misread) |
| Timeout | 15 s (real) / the same number of policy steps in simulation |
| Unsafe | the hand leaves the allowed box (workspace limits) or a safety check refuses a target |

After every episode, success or not, the arm goes back to the start pose by the existing checked route, not by
the policy.

---

## 4. What the policy does not do

- It does not choose the ball or the box.
- It does not move the lift, waist, head or base.
- It does not turn the hand: the fingers point down and the yaw is fixed (a ball looks the same from any side).
- It does not handle a ball stuck between two others; a ball the camera does not see steadily is left for the
  next look.

These are deliberate limits for version 1. Each can be lifted later ([04](04_RL.md) §9).

---

## 5. Words the robot says and the app shows

All in English and Korean, like every other skill: "Sorting the balls.", "Red ball to the red box.", "I couldn't
pick up the blue ball.", "All sorted.". The app's texts live in `src/lib/i18n.tsx` (Lumi app rules); the robot's
lines live with the skill. The exact wording is in the skill's code ([06](06_INTEGRATION.md)).
