# Work plan: missions, conversation, conference

The owner takes Lumi to a conference: mostly voice. Goals: any command of several steps (typed in the Command
dialog or spoken) is read right and done; people met on the way are answered and their tasks refused (unless they
are who the task is for); conversation answers exactly what is asked, varied, from facts, English and Korean (Korean
replies always polite); Lumi is presented as developed by Cutshion Company (쿳션), 2 years old.

Update this file when a part is done. A new session: read this, then docs/17_MISSIONS.md, then ROADMAP.

## Where it stands (2026-10-27)

All of it is checked offline (no robot); none of the pick / place changes and none of the attention / voice direction
changes below are live yet.

### Understanding commands and questions
- **Intent bank** (fast lane, read without the LLM): **64246 wordings**, English and Korean. Stress check over
  109990 sentences: 27 wrong (0.02 %), none from new wordings; the 27 are body state (axis at its end) or map
  (charge vs home).
- **Commands right per speech level** (rules, 19393 cases): English 88–89 %; Korean 반말 90 %, 해요 93 %, 하십시오
  92 %, 높임 90 %, 하게 88 %, 친구 92 %, 사투리 91 %; Konglish 87 %, mixed 87 %. English = Korean.
- **Typed = spoken**: the Command box and voice read the same in all but 30 of 19393 cases.
- **Stop**: 127 stop forms stop, also with a call or a polite ending around them.
- **Quick answers** (answered at once, no LLM): 2280 of 2284 questions that want one; wrong quick answers 0.
- **With the LLM** (blind sets): commands 78–89 %, dialogue turns 62–80 %, unasked motions ≤ 3 %; reasoning about
  things the arm can't do 82 %. Weakest: Konglish, very short orders, "again / more", memory of earlier days.

### Pick and place (offline sweep: 1500 pick + 500 place scenes)
| | |
|---|---|
| Picks, cups 72–92 mm | **93 %**, every side 92–93 % (left, right, ahead, beside) |
| Cups right next to Lumi (0–450 mm) | 94 % |
| Grasps turned more than 15° | 4 (live misses came from these) |
| Same base move repeated after one that went nowhere | 0 |
| Places | **79 %** (tables at standard height 95–99 %; tables lower than −420 mm at lift 0: 22 %, physical) |
| Cups put down off a table edge | 0 |

What is left is physical: cups under 72 mm (refused), grips over 88 mm (the hooks' neck), low tables at lift 0.

A voice pick ("take the cup") tries grasp turns 0…−15° only (`TRUSTED_YAW_DEG`; +15° missed twice live), then turns
the waist in place, then the base (Patrol), else asks to move the cup closer (`fetch.pick_here`).

### Attention, voice direction, body (offline only)
- **Look at me**: person from both cameras (`Vision.seen`); voice direction first, then the camera. Past the head's
  reach (behind): Patrol turns the base (`look_toward`), Patrol off turns the waist in place (`turn_body_to`, up to
  `LOOK_WAIST_MAX` 120°). Head pitch follows the person's box in the head camera (`LOOK_ME_*`; the −5…35° pitch range
  limits sitting people). A sure voice direction counts for `VOICE_KEEP_S` 20 s. "I'm on your right / left / behind
  you" (EN / KO) looks that way. Wake with nobody at the voice: nearest seen person, else head back.
- **Focus**: whoever calls, commands or says "look at me" is the focus; `keep_focus` keeps the head on them
  (`FOCUS_*`), also during come here. No greeting newcomers while focused; another person takes over only with a call,
  stop word or order.
- **Voice direction** (`audio/doa.py`): the plain head-array estimate, trusted from `DOA_MIN_CONF` 0.12. The clip
  mic as reference (`USE_CLIP_REF`) is off: live it gave confidences 0.03–0.07. Plain confidences were also low
  (0.07–0.15) late on 2026-10-27: check live; if they stay under 0.12, calibrate again. Auto-calibration uses the clip reference and never saves a worse
  refit; calibration offset 30, 13.6°. WAKE and turn log lines show direction / confidence / clip score; opt-in dump
  `data/doa_dump_on` → `logs/doa_dump/`.
- **Head and waist**: the head stays on the person through a conversation (also after stop); at its end head and
  waist go to 0; the waist goes to 0 before any drive or base turn; a new speaker: waist back, head to them.
- **Reach / give**: Greeter turns only the waist (never the base); the head stays on the person. Empty hand: shortest
  checked route over the taught poses (`wave_start` → `give` directly); holding: the old chain, never wave poses
  (`arm_route.py` `STOP_DEG`, `NO_EDGES`).
- **Arm poses by voice**: look / carry / ready and position words, EN / KO (`brain.ARM_POSE`).
- **Songs**: dance centred on the person; the request said again, stray words and the song's own sound don't stop it
  (`sing.REPEAT_S`, `sing.SPEECH_PER_SYLLABLE`); stop / change requests do.
- **Stop while Lumi talks or sings**: the clip stream is checked every 0.7 s for stop words (`mic.PEEK_*`); Lumi's own
  words don't trigger it.
- **Follow**: head, waist and base move at once, none waits: the head goes straight to the person (±180°), the waist
  turns toward them up to `WAIST_STEP_DEG` 8° per body move at `WAIST_FOLLOW_VEL` 50 % (estimate, watch the arm's
  swing), the base turns at once and drives when the person is within `TURN_ONLY_DEG` 35° and the waist within
  `WAIST_DRIVE_DEG` 15°; waist / head unwind to 0. Follow starts with the waist where it is.
- **Tests**: every test imports the `tests/no_robot.py` guard (a test reaching the robot fails).

## Left half done (do first)
- `api/server.py` (supervisor started only in `__main__`, see below) is edited but **not committed**: run all
  `tests/test_*.py`, commit ("Improve service supervision"), then `tools/gitea_push.sh` (start it detached with
  `setsid … &`: a plain background run was killed twice). Everything else of 2026-10-28 is on Gitea.
- `data/fetch_calib.json` (arm place measured 2026-10-27) and `data/hover_readings.json` (old fingers) stay
  uncommitted until the new gripper is measured.

## Open problems from the live test (fix these first; logs: `logs/lumi.log`, `logs/lumi_console.log`, times 2026-10-28)
- **"Look at me" does not work from 2 m and more** (clip mic worn). The owner: it worked until Friday 2026-10-23, also
  from 5-6 m. Facts: wake direction confidence median 0.20 (85 calls before 2026-10-27) -> 0.07-0.13 since Tuesday
  ~17:30; `DOA_MIN_CONF` 0.12; unsure directions were off by up to 90 deg (person at +187, read +244 / +94 / +106);
  one "sure" 0.24 read +166 with the owner in front (19:13:36). The direction code and calibration did not change
  (`doa.USE_CLIP_REF` False, `data/doa_calib.json` offset 30 = the 2026-10-23 one). `logs/doa_dump/*.npz` (16:38-16:39,
  record more with `touch data/doa_dump_on`, `rm` to stop): the clip voice is barely in the head array (score
  3.5-5.4, unrelated audio ~4-5), aligned within 0.05 s when found. Not found yet: what changed physically or in the
  head array audio since Tuesday (ask the owner about the head mic board; compare a Friday utterance if any is kept).
  Possible fix to discuss: when the voice is unsure, the head sweeps -60 / 0 / +60 with the head camera to find them.
- **Dashboard "go dock2" did not move** from (-5.29, 10.33) beside the charger (accepted, never moved, STUCK after 20 s);
  from (-4.87, 10.24) it drove at once. Not the speed: `get_params` reads angular 0.5 (the base keeps its minimum).
  A stuck drive now logs the base's `running_status` and planned path (`logs/api.log`, robot/drive_log.py): try it
  again from beside the charger and read that line. If the path is empty there, a short straight drive off the wall
  before the navigation move.
- **Arm speed**: long joint moves ~7 deg/s (look -> give 8.8 s) although 40 deg/s is asked; `traj_rapidrate` is 1.0.
  Cobo π joint speed limit raised 40 -> 50 by the owner; waiting for photos of "Robot limit" / "Joint limit" (likely
  a TCP speed limit). Then time look -> give live and raise `motion.JOINT_SPEED`.
- **Not live yet** (pushed 2026-10-28): who gave the order (`Lumi.speaker_track`: sure voice, the one talked with, the
  one the head looks at, the only one seen, else "raise your hand"); come here / reach to a far person; follow turning
  0.6 rad/s with the base's cap raised; follow arm check counts only nearer points; `motion.BLIND_S` 3 s; the arm
  folded to look before a drive (`waist_home(fold=True)`); "What did you say?" repeats the last answer; "Yes?" / "네?"
  to the name mid-talk; drive speed 0.5 m/s (`fetch.NAV_SPEED_MPS`, sent before every move).
  Also: "go back 1 m" beside something (the arm check counts only points coming nearer, `fetch.line_hits`, and logs
  the point's clearance now / after); "charger" / "charging station" / 충전 go to the marker `charge` when the map
  has one (else `home`).

## Next
0. **New gripper fingers first** (fitted; gaps measured, docs/gripper/README.md: belly 9.4 / 6.8 cm, tips 8.9 / 6.3,
   neck 5.7 / 3.0). Before any pick: `robot/gripper.py` `GAP_MM`, `skills.MIN_WIDTH` / `MAX_WIDTH` / `BELLY_MIN_MM`
   from them; AI_1 open / closed empty / on a cup read live; the lowest point below the grasp point (`TIP_MM`); the
   grasp pose taught again by hand on a cup (`data/grasp_teach.json`, `grasp_tips_teach.json`); then the hover check
   (old `data/hover_readings.json` was for the old fingers). Arm speed: the owner's "Robot limit" / "Joint limit"
   screens (joint speed now 50), then look -> give timed live.
1. **Live test** (owner at the STOP, slow). Before: Patrol on, robot off the charger, arm enabled at `look`, waist at
   the front, lift 0, base idle; one white 80–85 mm tumbler, upright. Watch logs/api.log. After each step: where the
   fingers landed and whether the base did anything twice. Stop at the first wrong motion.
   1. Cup at about (−100, 600), "Take the cup", then "put it down": no base move, no turn, named ("Put the white
      cup …"), put back.
   2. Cup ~75 cm ahead (−100, 740): "closer first", one straight drive, a no-turn pick near (−100, 580); if the base
      is blocked, no second identical move.
   3. Cup beside, right (+260, 720): waist or base turn brings it in front, grasp turned at most 15°.
   4. Holding, base ~0.3 m back from the table: "put it down", "put it on the white table": put down without
      repeating a move or turning away, or "This table is too low for me right now".
2. **Hover check** of the grasp point (Greeter / Patrol off; nothing touches the cup). Grey 85 mm cup at
   (−100, 600): `.venv/bin/python manipulation/skills.py hover cup 0`, then `-30`, `-45`: the arm stops with the open
   hooks 6 cm over the rim; the owner reads dx (+ = Lumi's right) / dy (+ = away) of the hooks' centre from the rim's
   centre, photo from above. Then `skills.py offset 0 DX DY -30 DX DY -45 DX DY` (prints the corrected offset, writes
   nothing); then `hover cup -30` at (+260, 700). Readings so far in data/hover_readings.json: 0° dx +2, dy +4
   (cup at (−126, 619)); left: −30°, −45°, then (+260, 700). With the corrected offset `TRUSTED_YAW_DEG` can go from 15 to 30 /
   45 after a live pick at each.
3. **Attention and voice live** (owner at the STOP, slow; Greeter / Patrol toggled off and on first so the assistant
   loads the new code):
   1. "Look at me" from the right and from behind: Greeter only → waist turns; Patrol → base turns.
   2. Wake from out of view with the clip mic: the head finds the caller.
   3. Focus during "come here": the head stays on the caller.
   4. Give from `wave_start`: `manipulation/arm_route.py check give` first, then `goto give`; the head stays on the
      person during the give.
   5. "Take the cup" where only a waist turn reaches it.
   6. Arm poses by voice (look / carry / ready).
   7. A song, then stop mid-song; stop in the middle of a long answer.
   8. Follow me with the waist (`TURN_MAX_RS` 0.3 for the first run).
   9. Conversation end: waist and head back to 0.

## Owner decisions waiting
- Place translation aliases (출구 → exit, 무대 → stage) are removed (rule: never translate a word into a place): confirm.
- "Just hold it" while holding = stop?
- Receive-wait notation (docs/17).
- "Who is the CEO?" quick answer; which JAKA questions get quick answers.
- `MAX_WIDTH` 92 vs 88 mm: measure the hooks' neck distance from the belly centre.
- "Go to p5 and dance".
- Command box talk history (needs the assistant to share its last turns).

## Left (not started)
- Puts beside Lumi with a waist turn (as picks do), and a table seen from further away kept in the map so a low table
  can be used after driving in.
- Place search: try the spots nearest the goal first, stop after ~8 refused in a row (slow on low tables).
- Conversation: memory of earlier days ("what did I ask yesterday"), Konglish, very short orders, "again / more".
- Conference: new map with new marker names, Wi-Fi profile (phone hotspot first).
- Dashboard drives (`api/server.py`) don't bring the waist to 0 first.
- Tests still write into `logs/lumi.log`; `tests/interrupt_check.py` is broken (its fake Lumi has no `patrol`).
