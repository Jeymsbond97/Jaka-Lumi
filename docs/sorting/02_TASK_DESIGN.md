# 02 Task design

What Lumi does when SORT is pressed, which part is learned and which part is plain code.

---

## 1. The scene

```
            Lumi (column, arm on its side)
                    │
   ┌────────────────┼────────────────┐  table, top at the proven pick height
   │  [ RED box ]   ( plate )   [ BLUE box ]
   │                 o  o
   │                 o  o
   └─────────────────────────────────┘
```

| Item | Value | Status |
|---|---|---|
| Table | the office table used for the proven picks: top at −403 mm in the arm base frame at lift 75 mm | measured ([01](01_HARDWARE_FACTS.md) §1) |
| Lift, waist, base | lift 75 mm, waist at the front (0°), base parked; nothing but the arm moves in a trial | fixed by this design |
| Plate | white, shallow, centred on the proven pick centre (−100, 580) mm | position to confirm, plate size to measure |
| Balls | golf practice rubber balls (Coupang item 9233082559); 2–4 per trial, 2 colours to start | **diameter, mass, colours to measure** |
| Boxes | open boxes, one per colour, left and right of the plate inside the arm's comfort radius (710 mm) and clear of the head | **size and positions to choose**, then fixed with tape marks |
| Light | normal office light; trials also run with the blinds open and closed | — |

Box positions are fixed in the arm base frame and written in `data/sort_layout.json` on the Thor. A later version
can find the boxes with the camera; the first one does not.

### Choosing the balls

- Two colours with far-apart hues and good saturation: **red and blue** first (the colour rule separates them
  with wide margins: red hue < 8 or ≥ 170, blue 85–130). Green or yellow is the third colour.
- Avoid white, grey and black balls at first: the colour rule calls anything with low saturation white, grey or
  black, and the plate is white.
- Matte rubber is good for depth (shiny objects jump up to 17 mm).

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

The policy starts with the hand above the plate (the `look` pose or a fixed "ready above plate" pose, chosen in
phase 2) and the gripper open. It is given:

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
lines live with the skill. Exact wording is set in phase 6 ([06](06_INTEGRATION.md)).
