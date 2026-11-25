# 06 Integration

How sorting is started, watched and stopped, using the same skill machinery as Move object.

---

## 1. Robot side (Thor, lumi-api)

| Endpoint | Body | Answer |
|---|---|---|
| `POST /skills/sort` | `{}` (version 1: everything on the plate) | 200 started; 409 another skill runs; 400 with the reason when a check fails |
| `GET /skills/state` | — | existing: `status` (running / done / refused / stopped / failed), `reason`, `took_s`, last log lines; sorting adds `sort: {done, left, failed, current: {colour, box}}` |
| `GET /sort/layout`, `POST /sort/layout` | box positions, plate centre | read and set `data/sort_layout.json` (later: from the app) |

Checks before starting (reason words in English and Korean, like the other skills):

| Check | Refusal |
|---|---|
| arm enabled | "Switch on the arm first." |
| gripper fitted (`gripper.FITTED`) and hand empty (AI_1) | "My hand isn't empty." |
| no other skill or task | existing busy answer |
| layout file present | "The boxes aren't set up." |
| policy file matches the control mode | "The sorting program doesn't match this arm." |

Code:

| File | Contents |
|---|---|
| `manipulation/sort.py` | the run loop of [02](02_TASK_DESIGN.md) §2, failure counting, speech lines |
| `policies/sort/` | `policy.onnx`, `config.json` (mode, rates, scaling, run id), `obs.py` |
| `robot/servo.py` | only for mode A: enable, stream joint targets, disable, with the existing checks |
| `api/server.py` | the endpoints above, registered like `/skills/move` |
| `tests/test_sort.py` | observation parity with simulation, refusals, STOP mid-episode (arm faked) |

The voice assistant can start it later with "sort the balls" / "공 정리해" through the intent bank; not in
version 1.

---

## 2. App side (Lumi app)

| Change | Where |
|---|---|
| SORT tile in COMMANDS → ARM & OBJECTS, needs arm on and hand empty | `src/app/(robot)/commands.tsx` (`TILES.arm`), icon in `src/ui/CommandIcon.tsx` |
| Request `POST /skills/sort`, marked as a skill so the status line follows `/skills/state` | `src/lib/commands.ts` (`sortRequest`) |
| Status line: "Sorting: 2 of 4", then "Done", or the robot's reason | existing skill status handling; counts from `sort` in `/skills/state` |
| Texts in English and Korean | `src/lib/i18n.tsx` (`cmdSort`, `cmdSortHint`, `cmdAskSort`, counts) |
| Asks first (it moves the arm) | `ConfirmDialog`, like Move object |
| Docs | `docs/COMMANDS.md` row for Sort |

STOP on every screen already stops skills; no new stop path.

---

## 3. Deploy steps

1. Export the student policy (`rl/sorting/export.py`) → `policy.onnx`, `config.json`, `obs.py`, run id.
2. Put them in `policies/sort/` in lumi-wave on the Thor and commit there.
3. Run `tests/test_sort.py` on the Thor.
4. Restart lumi-api only when the base is not driving (`GET /status` → `base.move_status`).
5. Dry run ([05](05_SIM_TO_REAL.md) §5 step 1) with the owner at the robot.
