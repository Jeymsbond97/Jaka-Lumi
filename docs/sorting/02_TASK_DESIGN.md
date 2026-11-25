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
| Lift, waist, base | lift 0 (lowest), waist at the front, base parked; only the arm moves | the table is nearest the hand and the torso camera sees nearest to Lumi |
| Table | the owner's 75 cm table; top about −258 mm (arm base taken as 1.008 m above the floor at lift 0, from the cups' table at −403 mm at lift 75; to be measured by touching the table) | on the 68 cm table the part the torso camera sees and the part the hand reaches overlap in a strip only ~10 cm deep |
| Tray | wooden tray 28 × 19 × 2.5 cm (outer), centre (30, 470) mm, long side across | the torso camera sees the table from y ≈ 400 mm on; the hand reaches with its fingers straight down up to y ≈ 500 mm and tilted up to 45° further out |
| Balls | foam golf practice balls, 42.5 mm, 8 g, red and yellow, 6 in the tray, 90 mm apart across and 75 mm forward | room for the fingers beside each ball |
| Boxes | two open boxes 26 × 18 × 8 cm without lids, short side facing the tray, 5 cm from it: centres (−250, 470) and (310, 470) mm | the ball may be dropped with the hand pointing any way (owner): over both boxes the arm reaches easily |
| Light | normal office light; trials also with the blinds open and closed | — |

The box positions are fixed and written in `data/sort_layout.json` on the Thor. A later version can find the boxes
with the camera.

**Hand at the ball:** fingers as straight down as the arm allows there, at most 45° from vertical. The owner's
free-drive recording (2026-11-25, fingers within 9° of vertical 90 % of the time) covered x −26 … 35 cm, y 32 … 56 cm
at 13 … 24 cm below the arm base without the arm getting stuck, which matches the simulated reach.

**Cameras:** the torso camera finds the balls. The head camera cannot: at its lowest pitch (−5°) it looks only ~8°
below the horizontal and sees no part of the table within 80 cm of Lumi.

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
