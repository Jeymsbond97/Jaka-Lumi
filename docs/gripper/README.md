# Gripper fingers: shape and measured sizes

Zimmer GEP2013IO-05-B parallel gripper on the arm flange (control: `robot/gripper.py`). It carries long stainless-steel fingers; this folder records their shape and inner sizes,
measured by hand with a tape on 2026-10-19.

## Photos

| File | What it shows |
|---|---|
| `gripper_open.png` | fingers fully open, seen from the front |
| `gripper_closed.png` | fingers fully closed, seen from the front |
| `gripper_length_front.png` | tape along the fingers, zero at the bottom face of the black Zimmer body |
| `gripper_length_side.png` | tape along one finger from the side, zero at the lower edge of the finger mount |
| `gripper_shank_gap_open.png` | tape across the shank (the straight thin part), fingers open: inner gap 6.6 cm |

## Shape

Each finger has three parts, from the gripper body down to the tip:

1. **Mount block**: the short, thick steel block bolted to the Zimmer jaw. When closed the two blocks touch.
2. **Shank**: a long, thin, straight flat bar. Its inner gap is the same along its whole length.
3. **Hook**: below the shank the finger bends outward and then curves back in, like the letter C.
   The two hooks together make a round opening, like a pair of tongs, sized for a cup or a can.
   The hook ends in a short inward-pointing tip.

```
        [ Zimmer body ]
         |##|    |##|      mount blocks
          ||      ||
          ||      ||       shank (straight, constant gap)
          ||      ||
         /          \      bend outward  (hook starts: "neck")
        (            )     widest point of the round opening ("belly")
         \          /
          `        `       tips (point inward)
```

## Inner distances (finger to finger, cm)

All gaps are measured between the **inner** faces of the two fingers, straight across.

| Where | Open | Closed | Stroke |
|---|---|---|---|
| Tips: the entry gap between the two tip ends | 8.8 | 5.9 | 2.9 |
| Belly: widest point inside the round opening | 9.6 | 7.0 | 2.6 |
| Neck: narrowest point where the round opening ends, at the top of the hook | 7.3 | 4.7 | 2.6 |
| Shank: the long straight thin part (same gap from top to bottom) | 6.6 | 3.9 | 2.7 |

What this means for grasping:

- An object goes in through the tips, so it must be narrower than **8.8 cm** (open) to enter.
- A round object is held in the hook. It is gripped when its diameter is between about **7.0 cm** (belly
  when closed) and **9.6 cm** (belly when open); a smaller object is not squeezed by the hook.
- The closed sizes are the gaps with nothing between the fingers: the smallest the gripper can make.

## Lengths along the fingers (approximate, read from the tape photos)

Read off the photos, so treat them as about ±0.5 cm; measure directly before relying on them.

| Point | From the bottom face of the Zimmer body (`gripper_length_front.png`) |
|---|---|
| End of the mount blocks, start of the shank | about 10 cm |
| End of the shank, start of the hook (neck) | about 15 cm |
| Finger tips | about 20 cm |

In `gripper_length_side.png` the tape starts lower, at the bottom edge of the finger mount: the hook starts
at about 11 cm and the tips are at about 17 cm on that tape.
