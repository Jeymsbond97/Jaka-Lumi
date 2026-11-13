# Work plan: missions, conversation, conference

The owner takes Lumi to a conference: mostly voice. Goals: any command of several steps (typed in the Command
dialog or spoken) is read right and done; people met on the way are answered and their tasks refused (unless they
are who the task is for); conversation answers exactly what is asked, varied, from facts, English and Korean (Korean
replies always polite); Lumi is presented as developed by Cutshion Company (쿳션), 2 years old.

Update this file when a part is done. A new session: read this, then docs/17_MISSIONS.md, then ROADMAP.

## Next session starts here (written 2026-11-13 evening)

Done on 2026-11-13 (with the Lumi app work): `/body/enable` and `body.enabled` in `/status` (deployed to the Thor and
running); the waist counted from the real front (`robot/head.py` `WAIST_FRONT_DEG` −20.4, `data/fetch_calib.json`
`waist_deg` converted to +0.09) **written in this repo but NOT on the Thor yet**; base switched to map
`cutshion_708_B_block` and marker `Home` set to the docked pose (docs/05 §2.3); charging stuck after the E-stop, fixed by a
base power cycle (docs/01). Lumi was left on its dock, waist at −20.4° on the controller (the real front).

1. Deploy and restart lumi-api (from the Mac):
   `cd ~/Documents/PROJECTS/JakaLumi_simulation/real/thor && scp robot/head.py cutshion@192.168.0.250:Dev/lumi-wave/robot/head.py && scp data/fetch_calib.json cutshion@192.168.0.250:Dev/lumi-wave/data/fetch_calib.json && ssh cutshion@192.168.0.250 'systemctl --user restart lumi-api'`
2. Check: `/status` `body.waist_deg` about 0 with the torso facing the base's front. If the front looks off, change only
   `WAIST_FRONT_DEG` (try −20 / −21) and deploy again. Then `/body/move {"waist_deg": 0}` must keep it at the front.
3. Run the self-checks on the Thor (they need its venv): `for t in tests/test_*.py; do .venv/bin/python "$t" || echo "FAILED $t"; done`,
   first `test_fetch.py`, `test_fetch_head_aim.py`, `test_follow.py`, `test_look_me.py`, `test_come_give.py`.
4. Open question: was the waist's front at −20 on the controller before too? Logs show it resting at −20 on earlier
   days and the fetch calibration was measured at −20.31, so probably yes; a pick after the deploy will tell
   (fetch uses the converted `waist_deg`).
5. Lumi app (separate repo, Gitea `Jaka_Lumi/Lumi-App`): live test of the BODY and ARM chips, and the 3D waist and head
   pitch against the real robot.

## Night 6 (2026-11-01 23:30 → 11-02 07:00): Korean first, then English — ENDED
Owner: grow Korean understanding (banks, quick answers, LLM) at every register — 반말 / casual-rude 명령조 / 해요 /
하십시오 / honorific / suggestion (가자, 갑시다) — with many sentences of the same meaning per command; then English the same;
never worse than now; 6 local commits (last ~07:00), tests until 05:00; no Gitea push (owner pushes).
Checks: tests/ko_levels_check.py (+ PARA paraphrases, rude, suggest), tests/ko_questions_check.py, tests/ko_held_check.py
(held-out sentences; before tree = scratchpad/before6), tests/en_paraphrase_check.py, bank_check --stress.
- 23:50 baseline Korean (8379 forms): rude 64/288 missed, paraphrases 5–26 % missed; questions 244/286.
- 01:25 commit 1 (9c148c1): bare "야" is a call to Lumi (얘 / names stay someone else); bank_words/ko_more.py (other
  verbs, orders, rude endings; bank 64k -> 73k, read 28 ms); ko_questions.py + "X 대 봐" as a question; stop forms with
  동작 / 거기 서 + polite / dialect endings; -ㅂ시다 suggestions; 노래 하십시오 / 뽑으세요; "do you shake your hand" = wave.
  Korean forms missed 249 -> 195 (of 8314), questions 263/268, bank stress wrong 27 -> 28 (+1 head-at-limit state case).
- 02:15 commit 2 (3597b31): Korean "-ㄴ 다음에" steps (Lumi's own step only; "회의 끝난 다음에" stays a condition),
  "이동 부탁드립니다" noun requests, 비켜 with a distance ("뒤로 50센티 비켜" was 1 m), 따라다녀 no longer "several",
  exact Korean quick wordings; English: bank_words/en_more.py, polite / "kind as to" / "you can" stops, "X now" orders
  no longer a seeing question, "is it safe for my kids…" / "how do I stop you…" answered. Korean forms missed 523 ->
  76 of 8411 (wrong 9 -> 5: stop said in the past, kept), held Korean 85 -> 96 of 106, questions 288/295, qa_eval wrong 0.
- 02:38 commit 3 (6cb9e1d): English stops in any frame (STOP_CORE), quick answers (EN_SLANG "how old r u",
  en_questions.py, "is it safe for my kids…"), Korean stay-still stops (꼼짝 마, 가만 있어, 움직이지 말아 주세요, 멈춥시다).
- 02:52 Gitea push 1 (5bfabd6, commits 1–3; owner asked at 02:50 for spread pushes, last near 07:00).
- 03:44 commit 4 (86921aa) + Gitea push 2 (4887ea9): Korean try-forms (전진해 봐, 좌회전 해 봐, 움직여 봐, 고개를 드세요, 빨리
  돌아와, 노래 부릅시다), English -ing / "how about" frames, "how about singing", more Korean questions. Bank stress 28 wrong
  (27 + 1 state case), right 24684 -> 25004; all tests pass.
- 09:22 commit 5 (40b1d6d) + Gitea push 3: "팔 접는 법 알아?" / "-는 방법 아세요?" are questions, not orders. All checks and bank stress (28 wrong, unchanged) passed. Commit 6 not made: the session ran out of context after 04:35; pushes 02:52, 03:44, 09:22.

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
- **Follow**: the head alone tracks the person, aimed where they will be when the head move ends (the base's turn
  and drive counted, `HEAD_LEAD_S`..`HEAD_LEAD_MAX_S`); the base turns and drives; the waist never turns further out,
  it only unwinds toward the front as the base comes round (a waist turned at the start). `TURN_MAX_RS` 0.6 (0.3 halves
  the gaze error in the simulation: the owner's call). Not live yet.
- **Put down after a voice pick**: base, waist and lift as they picked and the hand within `fetch.BACK_DOWN_MM` of
  the pick spot: straight back down there, no arm to `look` first. Not live yet.
- **Give from any pose**: by the checked route to `give_pre`, a stop, then the last move to `give` at `GIVE_SPEED`
  (`arm_route.py`); `give_pre` / `give` to be taught by the owner (`robot/motion.py teach give_pre`, then `give`).
  Speech plays while the arm moves (wave / handshake, open / close). "Give me your hand": the waist turns toward the
  person in `fetch.WAIST_STEP_DEG` moves while the arm goes to give, the head on the person, the whole sweep checked
  first (`fetch._give_turning`). Not live yet.
- **A stopped pick**: the next pick first backs out the way it came (`skills.back_out`); stopped after closing, the
  cup counts as held (put down works, also straight back at the pick spot).
- **No "Come when called" switch**: with Greeter or Patrol on every voice command works (Greeter alone never drives).
- **Follow turns** (not live): the head at the body API's maximum (`follow.HEAD_VEL` 100, ~40 °/s); the base turns
  up to joy_control's 1.0 rad/s (`TURN_MAX_RS`), slowed while the head falls behind the person (`FOCUS_*`). Turning
  round the other way (one side blocked) the head swings through the front to meet them, the torso camera watches
  meanwhile. Blocked both ways on the spot: a short straight move (≤ `SHIFT_MAX_M` 0.4 m, checked) and the turn from
  there; no such spot: "My arm can't turn here".
- **Tests**: every test imports the `tests/no_robot.py` guard (a test reaching the robot fails).

## Left half done (do first)
- Nothing half done: `main` = Gitea (2026-10-30 evening). `data/fetch_calib.json` (arm place, measured by the robot)
  and `data/hover_readings.json` stay local. An old `git stash` (`stash@{0}`, wave files of the other session, already
  committed newer) can be dropped once that session agrees.

## Open problems (latest live test 2026-10-30; logs `logs/lumi.log`, `logs/lumi_console.log`)
- **Exhibition (map `expo1`)**: markers `home` (dock, type 11, num 1, docks and charges), `p1`, `p2`, `p3`, `p4`,
  `final`. The office map `cutshion_708_B_block` is unchanged (Switch Map to go back). Open:
  - **Head USB**: the mic board (`AIUIUSBMC`) is not enumerated (Lumi hears nothing, mic noise 0), the head camera is
    at 480M (no depth, drop-outs, people read 20-30 m away). Owner to reseat the head hub cables; then check the mic,
    `/sys/bus/usb/devices/*/speed`, restart the camera service.
  - **Wheels slip on the carpet over metal strips**: the pose jumps (once to a map corner). On the dock:
    `/api/position_adjust?marker=home`. Owner to draw no-go lines / zones over the strips; more lidar features
    (continue scan); ask the base vendor about laser-only odometry.
  - **Café table ~74 cm** (top at arm z ~-255 mm, floor ~-995, lift 0 since `LIFT_MAX_MM` 0): inside `SURFACE_Z`, but
    ~15 cm higher than every proven pick; `fetch.table_ahead` did not find it from the edge (camera too flat over
    it). Next: a cup on it, `skills.py plan cup`, then `hover` (Greeter / Patrol / Wave greeting off).
  - **Dashboard stop now ends follow** (`fetch_stop` → `follow.stop`): not live yet; toggle Greeter / Patrol to load it.
  - `data/known_things.json` holds the office's yellow chair: back up and empty it while on `expo1` (owner: later).
  - Owner question left open: should spoken drive orders work with Greeter only (Patrol off)?
- **Gripper AI_1 read open while the fingers stayed shut** at a put-down (20:15: "opening", AI_1 90, the cup came back
  up). Owner test waiting: dashboard Close / Open 3 times with nothing inside, the owner says what the fingers did, the
  log has AI_1 each time. If AI_1 lies, check the gripper cable / Cobo π tool I/O. Code now: a cup that comes back up
  is put down again with what the put-down knew (`skills.released`, `fetch.RELEASED_KEEP_S`); still missing: a camera
  check after every release that the cup stayed on the table.
- **A cup put into the hand** (open, close by voice) can be given but not put on a table (no height known).
- **Answers via the LLM are slow** (median 2.7 s, worst 5-11 s, mostly on misheard sentences); not measured further.
  `gemma4:26b` is loaded with a 262144 context: measure whether a smaller context is faster.
- **Search half turn**: `fetch.SEARCH_BASE_DEG` 180: the base picks its own way round for a half turn. 170 broke
  `tests/test_fetch.py` (second place run); find why before changing it.
- **Arm speed** (long joint moves ~7 deg/s): waiting for the owner's Cobo π "Robot limit" / "Joint limit" photos.

## Voice direction
- The head mic board read front and back mirrored (since ~2026-10-27, cause not known; not the USB cable).
  Recalibrated 2026-10-30 from 60 camera samples: `data/doa_calib.json` sign +1, offset 140, radius 0.035, median
  error 27.5 deg (52 % within 30, 77 % within 60). Old: `data/doa_bad_2026-10-30/`, `data/doa_run_2026-10-30/`.
- Room noise limits it (~25 deg whatever the calibration). Offline next: speech-only frames (Silero VAD) and noise
  subtraction for the direction, checked against the camera angles in the logs and `logs/doa_dump`.
- Head moves: the body controller drops a move sent while another runs and never answers it; `head.moveto` now waits
  until the positions stand still (`head.STILL_S`), `head.turn` waits at most `TURN_TIMEOUT_S` (measured live: turns
  of 30 deg 1.4 s, 110 -> 0 deg 4 s).

## Live test list (owner at the STOP; restart lumi-api, toggle Patrol)
0. Today's, not live yet (2026-10-30): "Lumi" / "look at me" from every side, also behind (head sweeps +-110,
   waist to the front first, body turns to an unsure voice, the voice read in front taken as behind); the head on
   whoever talks; a held-out empty hand folds on the next words; "give me your hand" with the head on the person;
   follow from beside the charger wall (other way round, a short move off the wall, `follow.TURN_MAX_RS` 1.0: start
   0.3-0.5 near people); "close your hand" on a narrow cup, "you are holding the cup" (arm to carry and back);
   narrow cup pick (lift 30 mm, the camera decides); put down from a remembered table; head aim during pick / put;
   "let's go charging"; words after Lumi's own voice kept.
1. Top grasp from several spots and turns ("take the cup"), then put down / bring to p3; widen `TRUSTED_YAW_DEG` 15 -> 30
   after clean picks at +-30.
2. Holding: a drive to a marker / come here brings the arm to `look` first.
3. "Give me the cup" from 2 m: comes to the speaker, then hands over; "open your hand" / "thank you" releases.
4. "Come here and give me" / "이리 와서 줘".
5. "Look at me" with a person in front (repeat it: no side flips), and from behind with nobody in view.
6. Side grasp with a cup wider than 97 mm at the top.
7. Body contact limits taught by free drive (3-4 poses beside the body).
8. Wave greeting (dashboard switch; with Greeter / Patrol off and on): collision limits first; wave from 1.5 / 3 / 6 / 10 m, front and
   sides; with Patrol on: a drive asked while the hand is up brings it down first; stop, wave again; wave 20 s; walk away (down after 60 s); non-waves must not start it. Offline: every
   recorded wave found within 0.5-1.9 s, no non-wave ever (`tests/test_wave_greet.py`, recordings local).
9. A cup about as wide as the closed fingers (the white cup seen 76 mm): "take the cup" closes fully, lifts 30 mm and
   the camera decides (log "fully shut on a narrow one", then "it is gone from the table: held" or "I missed it.");
   also a miss: once the fingers have shut, the owner holds the cup's foot on the table so the lift leaves it there:
   "I missed it" and a second try. A cup knocked over or out of view at its place is taken as held (not caught).

## Next
0. **New gripper fingers**: gaps measured (docs/gripper/README.md: belly 9.4 / 6.8 cm, tips 8.7 / 6.3, neck 5.7 /
   3.0); grasp point from 3 free-drive side grasps by the owner (`data/grasp_side_teach.json`, agree within 1 mm;
   the belly 43.5 mm nearer the flange than the old fingers' point), then 1 mm left after the first auto side grasp
   brushed the cup with the right finger. The arm's pick reach is ~4 cm shorter with it. Left: the top grasp live
   with the new point; `grasp_tips_teach.json` (old fingers); arm speed (the owner's "Robot limit" / "Joint limit"
   screens, joint speed now 50), then look -> give timed live.
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
   5. **Side grasp**: picked live and put back once (84 mm rim, 142 mm tall cup at 60 mm up, the side decision and
      the height given by hand in that run). Next: "take the cup" through the assistant with the code's own choice
      (top over `MAX_WIDTH` 81 → side, height nearest 0.42 of the cup's height that fits), at the cup spots it can
      reach (nearer than ~640 mm in front, or to the right); a short (~7 cm) cup; a cup wide all the way down: "too
      wide for my hand, also lower down".
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
