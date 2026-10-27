# Work plan: missions, conversation, conference (started 2026-10-16)

The owner takes Lumi to a conference: mostly voice. Goals: any command of several steps (typed in the Command
dialog or spoken) is read right and done; people met on the way are answered and their tasks refused (unless they
are who the task is for); conversation answers exactly what is asked, varied, from facts, English and Korean (Korean
replies always polite); Lumi is presented as developed by Cutshion Company (쿳션), 2 years old.

Update this file when a part is done. A new session: read this, then docs/17_MISSIONS.md, then ROADMAP.

## Big night test 5 (2026-10-26 21:30 → 2026-10-27 09:30) — ENDED 08:55

Started 21:25 by the owner ("ha boshla") in the night-2 / night-4 lead session (tmux `lumi`). Brief:
docs/night5/COMMON.md; status docs/night5/<id>.md. Agents: P1, P2, L1, B2, T1, W5 as below, plus X1 (offline
pick / place sweep: thousands of cup and place positions left / right / ahead, the owner's 21:20 request: reach turned
left and turned right, not only straight, for pick and for put). **A session taking over:** read the Progress lines
below, then every docs/night5/<id>.md "Left", resume each unfinished agent with docs/night5/COMMON.md.
Morning: the lead runs all tests, commits per finished piece (~07:30–09:20), pushes spaced (never on the hour),
without assistant/bank_words/english.py until B2 clears it; report to the owner at 09:30–10:00.

Progress (lead):
- 21:25 main clean at 5b11c25 (+ runtime data/fetch_calib.json), battery 90 % charging. Owner's stop-word decision
  in job 5. Agents started.
- 21:50 owner: no usage limit today — more tests, more banks, more agents. Added H1 (arm / hand wordings:
  bank_words/arm.py, arm_more.py), Q1 (quick answers: quick_answers.py, questions.py, facts.py, company.py; taken
  from B2), W6 (blind r12: commands typed + voice, EN = KO every level, arm heavy, side words), W7 (blind r13:
  dialogues, Q&A continuity, quick questions, llm_reasoning set), E1 (typed = voice and EN = KO parity checker,
  tests/parity_check.py). 12 agents. Bank builds only under `flock data/bank_build.lock`.
- Pushes (owner): 5 spaced pushes until 06:00 (23:17, 00:48, 02:26, 03:53, 05:34) and 3 until 09:30 (07:12, 08:21,
  09:17): at each the lead runs all tests, commits the finished pieces, pushes with logs/push_night5.sh (leaves out
  bank_words/english.py until B2 clears it; KEEP_ENGLISH=1 then). Then the analysed report and the live test.
- 22:30 W7 published r13 (946 dialogues + 5115 cases per split, 11 levels, typed / voice, new set llm_reasoning);
  T1 writes tests/reasoning_check.py for it; W7 grows r13 (_b / _c) until 05:00. r11–r13 git-ignored.
- 22:40 W7 grew r13 to 12749 cases + 2398 dialogues per split (158 llm_reasoning meanings, arm talks while holding);
  keeps growing (_d …) until 04:00. W6 published r12: 22414 / 22448 command cases, 100 % unique, ~54 % arm / hand,
  side words, stop set 1599 (also inside sentences), field `channel` typed / voice, every level; grows with new
  methods until 04:00. E1 now also owns tests/blind_check.py (adds --round r11–r13, report by level and channel).
- 23:15 writers done: r12 = 46418 / 46490 command cases (ramble, multi with sides, numbers, object traits, asides,
  shorthand, self-corrections, next order after an arm action; 43 voice decimal cases to skip, logs/w6_gen/
  voice_decimal_split.txt). r13 = 21142 cases + 5698 dialogues per split, 260 topics, 385 llm_reasoning meanings
  (things the arm can't do, gestures / mimetic words, indirect hints, Simon says, two speakers, interruptions).
  Fixers now work through r12 / r13 train; more writing only if the fixers run out.
- 00:21 push 1 (late: the full test run took 60 min at load ~38): main b53fabb..0af24e9 (pick / put from the side,
  quick answers, Korean / English commands + wake-up words, parity / dialogue checks) = Gitea d72eb52, without
  english.py. All tests/test_*.py passed (4 flaky under concurrent edits, passed on rerun). W5 had stopped at 21:41
  waiting on its own shells; resumed. Next pushes 02:26, 03:53, 05:34, 07:12, 08:21, 09:17.
- 00:30 P2 round done (turned grasps land off-centre: taught grasp offset error grows with the turn; trusted turns
  ≤ 15°, then waist, then base; live hover check needed before trusting more, P2.md). Sent to a put-down round.
- 02:11 push 2: main af57edb..8014313 = Gitea 3f39234 (all tests passed; test_detour flaky, passed on rerun).
- 03:40 E1 parity round 2: typed != voice in 208 cases, all in api/server.py held parse (box gives / places on
  near misses: wrong motions; "내놔" read as place; polite give only talks; chain while holding). Given to L1.
- 03:52 push 3: main 0cbeefa (side put-down checks only; the rest changed during the test run, held for push 4)
  = Gitea ac13ced; fetch / reach tests passed in a clean copy of the commit.
- 04:15 L1 round done (box KO = voice; owner's 18:40 misses; E1 held faults; 105 stop forms; place translation
  aliases 출구/무대… removed — owner to confirm). H1 round done (arm bank 43k -> 62k wordings incl. others).
  Both sent on; H1's guard list to B2, side words / backpack to L1, voice-pick held name to P1.
- 05:03 push 4: snapshot of 04:25 tested as a copy (only test_followup / test_scene fail there: local data
  missing in a copy, as on night 4), committed from the copy: main b6dfec8..fb3420e = Gitea 5d1422b.
  Pushes left: 07:12 (or earlier ~06:30), 08:21, 09:17.
- 06:10 P1 round done: X1 sweep picks 73 % -> 93 % (every sector 92–93 %), too-near cups 8 -> 84 %, turns > 15°
  206 -> 1, places 76 -> 79 % (rest: tables too low at lift 0, said before driving).
- 06:30–07:00 all agents stopped at the 5-hour session limit; resumed 07:01.
- 07:05 Q1 done: r9 want-quick 1876 -> 2280 / 2284, wrong quick answers 0; every Korean level 91–93 % = English.
- 07:09 push 5: the 06:01 snapshot had test_route_words failing ('너 팔 접을 수 있지?' -> fold, from uncommitted
  brain.py; L1 / B2 fixing), so only the quick answers + fetch.py were committed (tested on HEAD + those files):
  main ee1219b..82f6baa = Gitea 122e7de. Pushes left 08:21, 09:17.
- 07:15–08:00 final reports: T1, P2, H1, E1, X1, W5, Q1, P1 (numbers in their docs/night5/<id>.md). X1 final:
  picks 73 -> 93 %, places 76 -> 74 % (P1's early "too low"; fixed 08:10, X1 re-sweep running).
  E1: typed != voice 417 -> 30 of 19393; every Korean level 87–92 % = English 89 %. W5 held (vs 10-24):
  r6 commands 54 -> 59 %, r8 43 -> 49 % (motions 226 -> 16), r8 questions 48 -> 70 %; English still below Korean.
- 08:14 push 6: snapshot of 07:55, all tests passed (test_followup fails only in a copy): main 4eb32ec..00b6000 =
  Gitea 5754de3. Stop words with a call before them ("루미 님, 멈춰 주실 수 있겠습니까?" …) checked in the commit.
- 08:55 push 7 (last): main cf1438e = Gitea fa9c1e7, now WITH english.py (B2 final stress: 27 wrong of 109990,
  baseline 58). All tests passed. Night 5 ENDED: 7 pushes (00:21, 02:11, 03:52, 05:03, 07:09, 08:14, 08:55; one
  fewer than asked, the 23:17 one slipped to 00:21). Every agent finished; status files docs/night5/<id>.md final.
  Owner decisions waiting: place translation aliases (출구→exit, 무대→stage removed by L1), "just hold it" while
  holding = stop, receive-wait notation (docs/17 vs r6), "who is the CEO?" quick answer, JAKA quick kinds,
  MAX_WIDTH 92 vs 88 (measure the hooks' neck), live hover check before grasp turns > 15°, "go to p5 and dance",
  Command box talk history (needs the assistant to share its last turns). Next: restart lumi-api (base idle) and
  the live test, P1.md "Live test plan" (4 scenes) + P2.md hover check, slow, owner at the STOP.

Asked by the owner 2026-10-26 11:05. Starts 19:00 from a new lead session: read this section, docs/night4/COMMON.md
and every docs/night4/<id>.md "Left" / "In progress" / "For others".
- Work not finished by the day agents at 13:30 (C, A3, A4, A5, A7, W5, B1, F1, R1): listed here by the lead at 14:00,
  each agent restarted from its own "Left".
- Faults from today's live test: the owner tells them before 19:00; the lead writes them here and gives each to the
  owning agent (EN + KO, every level, new cases for each).
- Measure on r10 (W5, half English) as well as r6 / r8 / r9; English must score as well as Korean.

### START HERE (remote session, 2026-10-26 night): what Lumi must do with things, and who does what

The owner starts this from home over Tailscale with "Big night test 5 ni boshla". The lead reads this section,
"Tonight's jobs, in order" below (every live fault with its numbers), docs/night4/COMMON.md (rules: no robot, no
service restarts, no git, held-out exams closed, one owner per file, bank builds once and alone), then starts the
agents below in parallel, each with its files, its part of the faults and the goal. The lead commits per finished
piece in the morning; Gitea pushes without assistant/bank_words/english.py until B2 clears it.

**The goal for pick and place (owner, 2026-10-26 evening, in their words: "from every side, find its own way, never
stand still").** Once the owner names a thing to take and a place to put it, Lumi:
1. **Focuses on that thing and remembers it.** The thing seen once is kept with its position in the map (base
   frame from the base pose, updated by the base's odometry and the waist / head angles), not only in the camera's
   current frame. While Lumi turns, drives, turns its waist or (later) lifts, the head and the waist turn against
   the motion so the head or the torso camera keeps it in view. Coming within reach, the arm goes to the kept
   position at once (one fresh look to correct it), no new search. "I can't see it" only after the kept spot was
   looked at and is empty.
2. **Reaches from every side.** The arm tries every grasp turn and both wrists, the waist turns as far as it can
   when that brings the thing into reach (beside Lumi, left or right), and the base moves when the arm alone can't:
   nearer when the thing is at the far edge of reach (the arm almost straight knocks cups over: pick from a
   comfortable distance, near PICK_ZONE_CENTRE, the no-turn grasp first until turned grasps are proven live),
   back when it is too near, round the table to another side when the near side is blocked.
3. **Finds its own way.** A move that did not bring the thing nearer (the base stood still: an obstacle, its own
   safety stop) is never repeated; the next way is tried (a small turn and in, another side by navigation,
   further round). It asks the person only when every way was tried, and says what blocked it.
4. **Never stands still while the thing is seen.** Every refusal (no IK, carry line jumps, head clearance, base
   blocked) leads to the next attempt, not to a stop; a stop comes only from STOP / the owner, or after all
   attempts with a clear sentence.
5. **Puts down the same way, from every side.** The table seen (also further away) is a place at once when the
   arm reaches it; otherwise the base goes nearer / round as for the pick; it turns towards the table, never away
   from it; it puts down from the side it reaches best, the cup upright.
6. **Names what it holds.** "Putting the white cup down", "컵을 내려놓을게요", never "something", however it
   was picked (voice, dashboard fetch, dashboard "Take the cup" steps, received from a hand).
7. **Talks to the controller sparingly.** Plans with the offline kinematics (robot/kinematics.py, < 0.5 mm) and asks
   the controller only to confirm the chosen plan, so the controller never drops connections in the middle.
Each point gets offline tests with today's live positions (below) and fakes for base / camera / arm; nothing is
live until the owner runs it slowly with the STOP in hand.

**Agents tonight (files owned; nobody else edits them):**
- **P1 approach & search** — tasks/fetch.py (and tests/test_fetch*.py): points 1, 3, 4, 5 (base moves, way round,
  kept position and head/waist tracking, table approach, turn sign for "face the table"), the held name in fetch
  (point 6, fetch side). Faults (a), (b), (c), (d), (g), (h), (i) below.
- **P2 reach & grasp** — manipulation/skills.py, manipulation/arm_route.py, robot/kinematics.py, tests/test_reach.py,
  tests/test_skills.py: point 2 and 7 (comfort reach limit as a constant P1 reads, offline IK planning, carry line
  without refusals, why turned grasps land off-centre: fault (e), (f)); test_reach / test_skills without the
  Thor-only calibration files. P1 and P2 agree the interface in docs/night5/P1.md / P2.md before coding.
- **L1 command box = voice, KO as EN** — assistant/brain.py, assistant/steps.py, api/server.py (+ tests
  test_command_box, test_fetch_words, test_steps): the Korean 55-sentence list grown to hundreds at every speech
  level, EN the same; the held name in the dashboard's held parse (point 6, api side). Job 3 below.
- **B2 bank wrongs** — assistant/bank_words/*.py, assistant/intent_bank.py: the 9 new wrongs of the English bank,
  the stress check again (alone), job 2.
- **T1 talk** — assistant/lumi.py prompt parts, assistant/brain.py SYSTEM text only through L1 (ask L1): the wrong
  date ("October 12"), unrelated answers to fragments, job 4; A4's dialogue regression (r6 mixed_i 111 -> 92).
- **W5 measure** — tests/blind_check.py runs only: r10 first full run, r6 / r8 / r9 after the others' fixes, the
  English vs Korean table for the morning report.
Each agent writes docs/night5/<id>.md (done, numbers before -> after, left), the lead sums up in this file by 07:00.

### Tonight's jobs, in order (the owner starts the agents remotely over Tailscale)

State at 18:45: main has 7d67106 (lift held at 0) and 4c00708 (place names without "to", stood-still approach goes
round, arm reply check) plus the uncommitted 18:40 give wording / Korean place fixes (committed by the lead once the
full test run passes). Gitea has everything up to de6830e plus, at 18:54 / 19:03, 7d67106 and 4c00708 + 5b11c25 replayed without the English bank (gitea branch 1b3f456); bcbee5d (assistant/bank_words/english.py) is NOT pushed (wrongs 58 -> 65): a push of main's tree would carry it, so until it is fixed push a tree without that file.
lumi-api was restarted by the owner at ~17:50 (before 7d67106): the evening fixes are live only after the next restart.
Agents: no robot, no service restarts, no git; one file owner per file; bank builds once, alone, before any check.

1. PICK (fetch.py / skills.py owner; the live faults below): (a) a pick at the far edge of the arm's reach is not
   tried from where it stands: the base drives closer first, then picks near PICK_ZONE_CENTRE. Live 18:30: white cup
   at (262, 774) top -189, "grasp in the hooks, turned -45 deg, wrist J5 -11", above (276, 534, -10), grasp
   (276, 534, -110): the arm almost fully out, the fingers came down with the tips on the cup instead of the belly
   and knocked it over; AI_1 4084 "I missed it", then the same again at (267, 763). Add a comfort limit (distance from
   the arm base / from PICK_ZONE_CENTRE, a constant with its reason, estimate until measured live) above which the
   base moves in first when it can; a pick the base can't improve still goes as now. (b) The carry line refusal and
   the 5 identical approaches (faults below). (c) Never lose the thing while moving (owner's 18:20 item below).
   (e) Off-centre grasps at a turned grasp (owner 18:45: "not the middle, one finger end lands on top of the cup and
   knocks it over", also after coming nearer): 18:40:11 grey cup (260, 722) top -186, "in the hooks, turned -30 deg,
   wrist J5 +26", above (336, 494, -7), grasp (336, 494, -107), AI_1 4155 missed; 18:40:57 (300, 621) top -191,
   turned -30, J5 +25, grasp (376, 393, -112), missed. Every live success so far was without a turn (J5 +20, cups
   near x -100). Suspects, in order: the turned grasp (flange_for: GRASP_OFFSET rotated about the vertical; a small
   error of the taught belly point grows sideways with the turn), the torso camera's arm-frame error at x +250..300
   (side of the view), the cup's measured centre (top rim vs body). Find it offline from the numbers, then a live
   check with the owner (slow, at the STOP): the same cup at (-100, 580) with no turn, then at (+260, 700) turned,
   the owner says on which side the finger landed and by how much. Until it is found: prefer the no-turn grasp
   and a base move that brings the cup to PICK_ZONE_CENTRE over a turned grasp.
   (f) 18:45-18:46, the cup straight in front at (-99, 738) top -181: no grasp without a turn (carry line jumps
   31-32 deg), a -15 deg turn found, then "The arm controller is not answering" (18:46:17): skills._ask's 3 quick
   tries all hit closed connections (the controller drops connections under a burst of kine_inverse; 60 fast IK
   asks by hand at 18:50 closed it too). The R1 seeds x grasp turns x carry checks ask far more IK than before.
   Fix: plan with the offline kinematics (robot/kinematics.py, fitted < 0.5 mm) and ask the controller only for the
   chosen plan, or back off longer between tries. And the base should have driven in: 738 mm straight ahead is
   the far-reach case (a).
   (g) PLACE, live 18:51-18:56 (owner: picked fine near, backed up a little, "put it": "can't find a place" with
   the table right in front; moved it a little, then it placed): 18:51:49 cup (-73, 588) picked without a turn, fine.
   18:53:20 and 18:54:30 fetch_place: "table height not measured", "no table in view", "a table at -328 mm further
   away at (-213, 797): going closer", "straight +0.13 m" five times, the table never nearer (-213, 796..799 every
   time): the base did not move and the same move was repeated (the 4c00708 _straight_went check covers only
   _approach, not this table approach), then "I can't find a free place on a table around me". Same fix as the
   pick: measure the move, go round / another way, never repeat a move that did nothing. Also "no table in view"
   with the table in front at lift 0: the torso camera's table view at this lift (holding in look) must be checked
   (CLAUDE.md: at table height it sees only y >= ~640 mm); use the table seen further away as the place directly
   when the arm reaches it.
   (h) Turning away from a table it sees (owner): 18:55:05 "white table at (22, 623): turning -14 deg to face it",
   then the table at (-349, 647) (370 mm sideways for a 14 deg turn: not the same table or a wrong sign / centre),
   the spot unreachable, turned +14 back, then placed at (-43, 618). Check the sign and the turning centre of
   "turn to face it" for tables (fetch approach_move with the waist / arm offset), offline with these numbers.
   (i) Put names the thing (owner, again): after a pick, "put it down" answers "putting something" instead of
   "putting the cup down": the held name (fetch.held_name, held_object) is lost on the mission pick path
   (dashboard "Take the cup" = steps pick, 18:51:46) or in the dashboard's held parse (api/server.py _held_parse).
   Every reply about the held thing names it ("the white cup"), EN and KO ("컵을 내려놓을게요"); a test that picks by
   steps, by fetch and by voice and then asks put / give / what are you holding.
   (d) Never stop while the thing is seen: next grasp / waist / way round, ask only at the end. Offline tests with
   every live position of today.
2. B1 bank wrongs: the 9 new wrongs of the English bank (below, B1 entry), then the stress check again; when it is
   not above 58, the lead pushes bcbee5d with the night's work.
3. Command box = voice, Korean as English (below, 18:40 item): the 55-sentence Korean cup / delivery list as a test,
   grown to hundreds at every speech level, EN the same; the open misses listed there.
4. Talk faults seen live 18:30: "What is the time?" answered "Monday, October 12, 2026" (web.now_text gives
   26 October: the model's own date; find why, the date must come from now_text); fragments "지금 몇..." answered
   with the microphone ring, "저는 오후 6시 반이에요" with the lidar, "서울의 지구" with "JAKA made me": an unclear
   fragment gets "sorry, again?" or nothing, never an unrelated self-description.
5. Stop words — DECIDED by the owner (2026-10-26 21:10): safety first. "stop", "stop it" and every Korean word with
   that meaning (멈춰, 멈춰요, 멈추세요, 멈춰 주세요, 그만, 그만해, 정지, 스톱, 스탑, 서, 거기 서, 움직이지 마 …, every
   speech level and slips) stop the task wherever they come, also inside a longer sentence (a bystander's too). Keep
   that behaviour; check every Korean / English stop form is caught (tests), never weaken it.
6. Then the 13:30 left work per agent (below), r10 measured (W5), A4's dialogue regression.
7. Lead: test_reach / test_skills without the Thor-only calibration; README EN + KO for the waist reach and the lift
   hold after the live test; one push per finished piece in the morning, tests first.

Unfinished at 13:30 (details in docs/night4/<id>.md "Left" / "For others"):
- A4: r6 dialogues_mixed_i fell 111/175 (06:28) -> 92 (12:53): the model picks search more often (first search turns
  14 -> 29 on the same talks); cause not found (not A4's search line). First job tonight: diff the 06:28 prompt with
  today's on "윤초는 뭐예요?", re-run r6 (tag a4n4n6e) and the own talks. "이름은 와 그래 지었노?" after 경복궁 (KO only).
- B1: 15103 English wordings in (bank 22565 -> 42998), no Korean yet; the blind --stress before / after on r6 / r8 / r9
  (logs/bank_check_b1_*_blind.md) done 16:57: wrong 58 -> 65 of 109990 (9 new, 2 fixed), so bcbee5d is NOT pushed.
  New wrongs to fix first: "grip immediately" -> arm open; "you must straighten your waist" -> arm reach; "grip 이 좋네
  이 컵" / "can u return the cup" -> pick; "since you're here, come back" -> come; "drive over there, where I'm
  pointing" -> come; "I'd love to see you come this way" -> look me; "fly up to the ceiling" -> look up; "review time:
  guys, get me the bottle" -> fetch. Then re-run the stress check and push bcbee5d. Next: the same depth for Korean levels. intent_bank wave verb check lacks "handshake" /
  "shaking" / "goodbye"; brain.named_place reads "your spot" / "where you were" as home.
- A3: blind r9 / r8 --rules --sample re-measure (tag a3n4r3) and bank_check r8 stress, killed by the embedding jam.
  15 ko_levels misses (C's readers): waist / charge / put polite forms ("…주셨으면 해요", "…주시면 감사하겠습니다",
  "…주면 안 될까요?"), Konglish "차지하러 가 줘"; "put that cup down" (hand reader); "아까 그 자리로 돌아가 줄래?".
- C: "고개 끄덕이고 손 흔들어" (nod lost), "go grab me a cup" (only a pick), "chin up, buddy" (looks up); ko_plain dialect
  endings (드시게, -그라, -라잉, 보소); "-주시면 안 될까요?" on the LLM path; r6 motion sets measure. Song stops "그만
  하시겠습니까?", "cut the music, please" (A5's note).
- F1: route-level r8 bring / take / put / give re-measure; receive step colour; Korean names of English markers
  ("갤러리 투", "부스 십이", "비 세븐 게이트"); fetch_dialog asking where a named person is; hand reader EN / KO parity
  ("hand it to Minsu" -> LLM, "민수한테 줘" -> give), idle "그거 놔 줘" opens the arm (C).
- A5: company_check / web_check (LLM) not run; 201 r8 sing requests left to the LLM (side remark before); "배터리 수명";
  openers / remarks / stutters before questions (A3, 67 of 528 missed r9 questions); seeing takes knowledge questions.
- A7: r6 / r8 rules4 not run (one at a time); "배터리 얼만가?" (하게체) misses battery.asked; r6 d94 shared talks.
- R1: offline only; the live waist-reach test with the owner (docs/night4/R1.md plan); README EN + KO after it.
- W5: r10 not yet measured (first full run tonight); r10 has no seeing / follow-up / closing / lookup / questions_world.
- Lead: bank builds must run once, alone, before any check (the 11:05-12:11 jam); the push checks now copy the caches.
- R1 / tests: test_reach and test_skills read the Thor-only calibration (data/camera_extrinsics*.json,
  data/calib_samples*/) and fail in a clean checkout (Mac, Gitea); the push check copies them since 16:40. Make the
  tests use fixed values instead.

Faults from the live test:
- 2026-10-26 17:57, "Take the cup from here, bring it to exit and hold it" (dashboard): the cup seen at (-117, 960),
  the base drove +0.38 m to bring it to (-100, 580) but it ended at (-104, 694) (top -186); there every grasp was
  refused by _carry_ok ("straight move to carry: a joint jumps 30-34 deg"), replayed offline the same (fine at y 598 /
  640). Then a "stop by voice" from people talking nearby ("동물을 멈춰버린 거랑 안해") ended the task.
  Owner's rule: once Lumi sees the cup it keeps trying until it has it, never stands still: every grasp turn and
  wrist, the arm reaching from every side; the waist turned as far as it can when that helps; when the base fell short
  or the arm can't reach, a new base move (find a way, closer / around) and try again. Fix: when the carry line
  jumps, another carry route (via above, the pose graph, joint moves) instead of a refusal; a short base drive is
  measured again and corrected; each refusal leads to the next attempt, not to a stop; offline test with the live
  positions (-104, 694) and (-117, 960).
- 2026-10-26 18:13, the same order again: the cup at (-141, 869) across the table, every grasp refused (carry line
  jumps 28-34 deg); "moving to reach it" 3/5, 4/5, 5/5 each planned straight +0.29 m, cut to +0.15 m by "an
  obstacle 0.30 m from the way" (the table), and the cup stayed at y 869 every time: the base did not move at all and
  the same move was tried again three times; then "asking to move it closer", failed after 40 s. Fix: a move that
  did not bring the cup nearer is not repeated; go round the table to another side (navigation, APPROACH_SIDES)
  before asking; the arm's reach across a table edge (~870 mm) checked offline with the waist.
- Dashboard: the arm state flickers "idle" / "power off" while Cobo π shows the arm on (during a fetch). Likely the
  controller answering get_robot_state with another command's reply (not reproduced idle: 40 of 40 right);
  robot/arm.py now asks a read again when the reply's cmdName differs. Check after the restart.
- Owner (2026-10-26 18:40): Korean typed in the Command box must be read as clearly and rightly as by voice and as
  English. A 55-sentence Korean cup / delivery check (scratchpad ko_box.py, rules only) after the 18:40 fixes:
  still to the LLM or wrong: "컵 챙겨서 exit 가서 기다려", "컵 들고 p5 가서 기다려" (box talk, voice fetch),
  "exit에 컵 갖다 놔" (read as the cup at exit), "컵 놔", "컵 가지고 출구로 가" (출구 is not a marker name: ask, never
  map it). Make it a test (tests/test_command_box.py KO list, every speech level) and grow it to hundreds, EN the same.
- Owner (2026-10-26 18:20): the thing to pick is lost while Lumi moves to reach it. Seen in earlier live tests: a
  base turn / drive, a waist turn or a lift move takes the cup out of the camera's view, then "I can't see the cup" or
  a whole new search. Once a pick-and-place order is given, Lumi stays on that thing: it keeps where the thing is (map
  / base frame, from the last sighting, moved along with the base's odometry and the waist / head angles) and keeps it
  in view while it moves: the head (and the waist, when the base turns) turn against the motion so the head or the
  torso camera never loses it. Arriving where the arm can reach, it reaches at once to the kept position (checked
  with a fresh look), no new search; "not seen" only after the kept spot was looked at and is empty. Offline test: a
  base turn / drive / waist turn with a fake camera, the cup kept and picked without _look_around.
- Stop words inside a long sentence of bystanders ("…멈춰버린…") stop a task: owner decided 21:10 — keep it (job 5).

## Big night test 4 (2026-10-26 00:15 → 10:00) — ended (morning commits ac4211c, b547f61, b3604af at 09:49)

Night 3 stopped 2026-10-24 22:51 (weekly usage limit; reset 2026-10-25 20:00, nobody restarted it): its work stayed
uncommitted, and night 2's five commits were never pushed (logs/gitea_night3.sh waited on the old hashes). Started
again by the owner 2026-10-25 23:45 ("boshla") in the night-2 lead session.

- Pushes: logs/gitea_night4.sh (setsid, no Claude needed) pushes 9f43b70 … dce2587 at 00:37, 01:52, 03:14, 04:29,
  05:43, each tree's tests run first in a worktree (PYTHONPATH = the worktree); log logs/gitea_night4.log.
- Night 3's work: committed 23:58 as 67bbe90 (quick answers, Cutshion, weather / news), 1f35aee (seeing, memory),
  f101455 (Korean levels, long talks, the rest); all 58 tests pass (test_quick_answers updated for the company kinds).
  Pushed after night 2's by logs/gitea_night4b.sh at 06:27, 06:58, 07:36 (log logs/gitea_night4b.log).
- Team (5 agents, fewer than nights 2–3 so the weekly usage lasts to 10:00): C (commands: A1 + A2 + A6's left —
  arm / hand, head / body / base, chain, seeing-vs-command order), A3 (Korean, engine, checkers), A5 (knowledge,
  quick answers, weather / news), A7 (memory), W4 (finish r9 parity round, then r10). Brief docs/night4/COMMON.md,
  status docs/night4/<id>.md. r7 final exam: a fresh writer ~05:00 if usage allows, scored ~08:00.
- Morning: 2–3 commits of tonight's work (~08:15, ~09:05, ~09:50), pushed spaced after 07:36; report at 10:00.
- **If the limit runs out again:** the push script goes on by itself. On reset: `date`, read logs/gitea_night4.log,
  run all tests, commit what passes, start one agent per docs/night4/<id>.md "Left" with docs/night4/COMMON.md.

Progress (lead):
- 23:50 tests of the uncommitted night-3 tree; push script started. 23:58 night 3 committed (3 pieces).
- 00:05 five agents started (C, A3, A5, A7, W4); 00:20 A4 (LLM, talk, speed) added at the owner's LLM request.
- 00:15 owner: keep the agents going round after round until 10:00 (new commands / questions / dialogues each round,
  EN = KO, banks + quick answers + rules + LLM examples). Lead: when an agent ends, re-brief it with a new round;
  when W4 ends, a fresh writer makes r10 (other method), r7 final at ~05:00.
- 00:15 wake words added by the lead (assistant/lumi.py WAKE / CALL_REST, tests/test_wake.py): "wake up", "wake up
  Lumi", "Lumi, wake up", "Hey Lumi", "헤이 루미", "루미야 일어나", "일어나세요", "깨어나 루미야"; a bare "wake up" /
  "일어나" only as the whole utterance. test_wake passes. Not live (lumi-api not restarted).
- ~00:20 session usage limit (5-hour window): all six agents stopped; reset 04:50. Pushes went on by themselves:
  9f43b70 00:37, fbcc5ca 01:52, 6922f39 03:14, fa5ac04 04:29 pushed; dce2587 at 05:43, night 3 at 06:27 / 06:58 / 07:36.
- 04:52 resumed C, A3, A4 (until 09:15) and W4 (finish r9 only); A5 and A7 kept stopped so the window lasts to the
  10:00 commits and report (their state: docs/night4/A5.md, A7.md — resume them first in the next window).
- 05:20 W4 finished r9: 37345 train / 33581 held cases, 1888 / 1861 dialogues, 11 levels at 8–10 % each, near misses
  19–26 % per level, new set lookup_dialogues; check_r9 0 problems (README "## r9", docs/night4/W4.md). Its full test
  run saw test_detour / test_driving / test_korean_numbers fail mid-edit (agents working): re-check before commits.
- ~06:45 session usage limit again (agents stopped mid-run). 09:40 new session: all 60 tests pass; night 4 committed
  as b3604af (talk, quick answers, weather, songs), b547f61 (memory), ac4211c (commands, Korean levels, checkers).
  Spaced pushes by logs/gitea_night4c.sh at 10:15, 10:55, 11:35 (log logs/gitea_night4c.log).
- 09:50 resumed C, A3, A4, A5, A7 from their docs/night4/<id>.md (A5 with levels.py from its old scratchpad).
- ~10:15 the lead session closed (agents stopped mid-round, edits uncommitted). 10:20 new lead session resumed C, A3,
  A4, A5, A7 from their docs/night4/<id>.md (In progress, Left, the "For others" items addressed to each).
- 10:45 owner: English must be understood as well as Korean (r9 is 17 % English), many more wordings for every
  command (+177 is too few), cup tasks in every form (pick / put / bring / give / take from a hand / search / wait /
  deliver, orders on the way), and the arm must reach a visible reachable cup from any direction. Four more agents:
  W5 (r10 sets, half English, cup tasks), B1 (bank growth, bank_words/english.py), F1 (cup-task language: parse_fetch,
  steps.py, fetch_dialog.py, bank_words/fetch.py; taken over from C), R1 (reach from any direction: manipulation/skills.py,
  tasks/fetch.py reach parts, offline tests only).
- 11:00 owner: all agents stop by 13:30, report at 14:00; this work goes to Gitea as 5 pushes spaced until 17:00
  (e.g. 14:15, 14:55, 15:35, 16:15, 16:55), by a push script like logs/gitea_night4c.sh.
- 14:55 all 62 tests pass; committed 56cac99 (commands, cup tasks, talk), 2131e38 (quick answers, songs), da078f2
  (memory), de6830e (waist reach), bcbee5d (English bank). logs/gitea_day4.sh pushes them 15:30 … 16:55 (the bank only
  with logs/b1_ok). ac4211c was skipped at 12:00 (its worktree had no embedding cache: every test embedded the whole
  bank and timed out); the checks now copy data/intent_bank.npz and quick_answers.npz into the worktree.

## Big night test 3 (2026-10-24 18:30 → 2026-10-25 10:00) — stopped 2026-10-24 22:51 (weekly limit)

Night 2 stopped at ~01:45 (the lead's account ran out of usage): nothing was committed then. On 2026-10-24 ~18:00 a new
session (lead 3) took over: fixed the 6 tests the night-2 work broke (chain fake, come back "return the cup" = put
back, "뒤에 뭐 있는지 봐 줘" answered by the cameras, switches fake, arm self-correction, "the jeans, what colour are
they?" = the jeans, clothes out of view said again), all 58 tests pass, and committed night 2 in five pieces
(9f43b70, fbcc5ca, 6922f39, fa5ac04, dce2587; rebuilt at 22:45 so voice_words.py goes with the brain changes it needs in the
last one). Their Gitea pushes run at irregular times (owner: never on the hour, never evenly spaced), script
logs/gitea_night3.sh, log logs/gitea_night3.log.
tests/blind/r6/ and r8/ (181 MB) stay local (git-ignored); their generators are in logs/w2_gen/ and the W3 folder.

**A new session / account taking over: read this section, docs/night3/COMMON.md, then each docs/night3/<agent>.md
(Done / In progress / Left) and re-brief the unfinished agents from "Left" with the same rules.**

Owner's goal tonight (on top of night 2's): Korean as good as English at every speech level (반말, 해요체, 하십시오체,
friendly, honorific, dialect, Konglish), tested at the same depth in both languages; banks, quick answers, dialogues and
LLM examples keep growing; new test rounds again and again until 10:00; fix night 2's "For others" faults; then a
report to the owner at 10:00. HANDOFF §16.1 (body pose drop) is put off.

Team: the night-2 roles (A1–A7, W2; files as in "Big night test 2" below), plus W4 (new writer: r9, the Korean /
English parity round: every capability and question kind in both languages and every Korean level), and at ~05:00 a
fresh writer for the final exam r7 (held only, scored by the lead ~08:00).

Commits: night 2 = five pieces above (pushed by 23:00). Tonight's work = four commits 07:00–10:00 (~07:00, ~08:00,
~09:00, ~09:50), each pushed on its own (tools/gitea_push.sh), titles short and plain ("Add …", "Fix …",
"Improve …", "… tested").

**When the usage limit runs out (owner 2026-10-24 22:45: write this into the plan):** the limit hit at ~19:30 and
reset at 22:40; every agent stopped mid-round. The work so far stays in the files. On reset (this lead or any new
session / account): (1) `date`; read logs/gitea_night3.log (pushes go on by themselves: a setsid script, no Claude);
(2) resume each stopped agent with a message "continue from where you stopped" (same session) or, in a new session,
start a new agent per docs/night3/<id>.md "Left" with docs/night3/COMMON.md; (3) run all tests/test_*.py before any
commit; (4) shift the morning schedule if needed (4 commits between 07:00 and 10:00, report at 10:00); (5) add a
Progress line below. Agents keep their status file current every hour for this.
Note: tests run in a git worktree fail test_fetch, test_fetch_place, test_followup, test_scene for reasons of the
worktree (local test data / state); the main tree is the reference (58 / 58 at dce2587).

Progress (lead):
- 18:30 r6 / r8 held scored with the rules at the start (logs/blind_held_lead0.*, logs/lead_held0.log).
- ~19:30 usage limit: all agents stopped (A1–A7, W2, W4 mid-round). 22:40 reset: lead rebuilt the 5 commits, all 9
  agents resumed with "continue from where you stopped" and write their docs/night3/<id>.md first.

## Big night test 2 (2026-10-23 22:40 → 2026-10-24 01:45) — stopped (account limit), committed 2026-10-24

Started by the owner ("barchasini boshla"). Lead = the session that wrote this. **A new session / account taking over:
read this section, then each `docs/night2/<agent>.md` (done / in progress / left), then re-brief the unfinished
agents from "left" with the same rules.** Body pose drop (HANDOFF §16.1) is put off by the owner.

Owner's goal: Lumi understands **everything it can do**, said in any way with the same meaning, English, Korean
(반말 / 해요체 / 하십시오체, dialect, Konglish, whisper slips) and mixed, at once and exactly: every arm / hand,
head, body, base command, missions, music, voice settings, status; questions (Lumi, Cutshion / JAKA, weather,
news, any internet lookup); long dialogues on any world topic with nested why / when / what follow-ups; context
("thanks" = closing or not, by the talk); people seen (clothes, colours, hair, glasses, posture, actions, held
things) answered at once, not "I can't tell"; memory of the talk (HANDOFF §16.3, 48 h); faster replies; the Command
box does whatever voice does. Banks (intent bank, quick answers) grow far past thousands of wordings; aim 100 %.

Owner's meanings: "shake hand / shake hands / let's shake hands / shake / wave / wave your hand / 악수하자" = **wave**;
"give me (your / a) hand / 손 줘 / 손 내밀어" = **reach**; "give me it" while holding = **give**.

Team (each owns its files; shared big files only by small Edit hunks in its own functions; status in docs/night2/):

| id | role | owns |
|---|---|---|
| W1 | blind test writer: commands (never reads code) | tests/blind/r6/{train,held}/commands_*.py, speed_short, chain, detour, missions, sing |
| W2 | blind test writer: dialogues and questions (never reads code) | tests/blind/r6/{train,held}/ dialogues_*, followup, seeing, unknowns, questions_* |
| A1 | arm and hand language | assistant/bank_words/arm.py, brain hand reader (hand_request …), fetch_dialog.py |
| A2 | head, body, base, missions, Command box | assistant/bank_words/motion.py, driving.py, steps.py, chain.py, detour.py, api/server.py command paths |
| A3 | Korean language + fast-lane engine + checkers | assistant/bank_words/korean.py, intent_bank.py / quick_answers.py code, wording.py, voice_words.py, brain.direct_order, tests/*_check.py |
| A4 | conversation, context, reply speed | brain.py prompt / closing / follow-ups, talk_examples.py, interrupt_examples.py, action_examples.py, llm_direct.py |
| A5 | knowledge: Lumi, Cutshion, JAKA, internet, news, weather, music | assistant/bank_words/questions.py, quick answers kinds, company_examples.py, web.py, knowledge/, song_bank.py |
| A6 | seeing people and things | assistant/seeing.py, vision/scene.py ask_vlm parts |
| A7 | memory (talk, seen things, self state, 48 h) | assistant/memory.py (new), tests/test_memory.py, small hooks in lumi.py / brain.py |

Rules: no robot motion, no service restart, no git commit / stash / reset / checkout (the lead commits); never read
`tests/blind/*/held/`, `r5/`, `r7/`; EN + KO + mixed together; never guess a word into a place / object; a wrong
motion is the worst error. Measure: `tests/blind_check.py train --round r6 [sets] [--rules|--cached] [--limit N]`,
`tests/bank_check.py`; one LLM run at a time per agent (the GPU is shared). `tests/test_mission_stop.py` segfaults at
exit after "mission stop ok" also on the committed code (known, not a failure of tonight's work).

Schedule: 5 commits, pushed at different times (tools/gitea_push.sh): ~01:00, ~03:30, ~06:00, ~08:00, ~09:50.
r6 train / held from W1 / W2 by ~00:30; held scored by the lead only. ~05:00 a fresh writer makes the final exam r7
(held only); scored ~08:00 on commit 4. Results here and in HANDOFF.

**Standing order (owner, 23:10): nobody stops before 10:00.** When an agent finishes, the lead re-briefs it at once
with the next round; writers keep making NEW rounds with new methods (r8, r9, r10 … each by a fresh writer, other
crowds / scenarios / styles, never reusing earlier generators), fixers keep filling the banks, quick answers, rules
and LLM examples and fixing what each new round shows, again and again until the morning. r7 stays the final exam
(written ~05:00, scored ~08:00).

Progress (lead, updated as agents finish):
- 22:40 bank_words hook (assistant/bank_words/, per-wording embedding cache) added; banks 4013 / 495 wordings.
- 22:45 all nine agents started (wave 1, until 03:00), common brief docs/night2/COMMON.md. Battery log:
  logs/battery_night2.log (55 % charging at 21:30). Next for the lead: commit 1 at ~01:00, score r6 held when the
  writers and A3's checker are ready (~01:30), re-brief wave 2 at ~03:00 (until 10:00), r7 writer at ~05:00.
- 22:55 W2 delivered r6 dialogue / question sets (counts in tests/blind/README "## r6 dialogues"); re-briefed to grow
  until 03:00 (variety, Korean ≥55 %, 250+ topics). Owner: Lumi's price is not needed — it stays "unknown".
- 23:05 W1 finished: r6 commands 29263 train / 29244 held cases, 80 files per split (README "## r6 commands", new
  tokens waist / arm look / point / limit / more). W1 is done (its generators would leak into r7: r7 = a new writer).
- 23:50 W3 finished r8 (scene-driven, 225 visitor types × 3 maps): 34754 / 34196 cases + 1923 / 1965 dialogues
  (train / held), 96.8 % unique, ~79 % Korean, no new tokens (README "## r8"). Fixers told to use r8/train too.
  Next writer: r9 at ~02:00, adversarial, aimed at the weak classes of the r6 / r8 held scores (classes only).
- 00:00 A2 interim: NEW capability waist by voice (Lumi.waist via fetch._waist_to, sweep-checked, Patrol only;
  before, waist words drove the base turn) — **first live run slow, owner at the STOP**. Relayed A2's findings: voice
  guards (A3), point / missions scoring (A3), lift words read as put down (A1), seeing vs peek (A6).

**Where we stopped (2026-10-16, ~19:50, owner left):** every agent finished; nothing is half-done except what is
listed under "Next". `lumi-api` was NOT restarted: the robot still runs the old code. A background re-check of
conversation / company / dialogues with all fixes was started at 19:45 (`logs/recheck_all.log`; it ends with
"dialogue_check done"); start tomorrow by reading its three reports. The LLM benchmark is paused, not lost.

## Done (written and checked without the robot)

- [x] **Missions** (docs/17): `assistant/steps.py` (reader: rules, LLM pass with every value checked against the words,
  `check`, `describe`, named people, senders), `tasks/fetch.py` `run_steps` (go / move / turn / pick / receive / say /
  place / give / hold / arm), pause / resume / replace, API `/tasks/parse` + `/tasks/steps`, dashboard step list,
  voice read-back (spoken yes only). Review findings (side / colour put-down, open while holding, checked move in
  pieces, stop first, explicit yes, validation) fixed.
- [x] **Mission place / pick steps after the 2026-10-20 live test** (docs/16 step 4, 9, 9a): one search for both, a
  table or thing seen is gone to at once, table heights from level depth only, "X or Y" / misspellings / "the lower
  one", exactly what was said first, else the closest surface or object seen, said aloud; fixed pauses between
  actions removed. Offline only; live list in ROADMAP Next 0-3.
- [x] **Reading tests**: `tests/test_steps.py` 1158 / 1158 (rounds written blind by agents:
  `tests/steps_cases.py`, `steps_cases2.py`, `steps_cases3.py` named people, `steps_cases4.py` Korean speech levels).
- [x] **People on the way** (docs/17 §4): `lumi.mission_talk`; `tests/test_mission_talk.py` passes;
  `tests/interrupt_check.py` 290 / 301 on `tests/interrupt_cases.py` (the rest: voice cancel by the starter, a
  change that adds a message, "take it back to Anvar").
- [x] **Status questions** from the task state (`lumi.STATUS_Q`, `now_doing`).
- [x] **Voice path** check `tests/voice_check.py` (TTS -> whisper -> reader): 440 / 600 round 1; Korean marker
  names and "1미터" -> "2m" are the weak spots; a whisper prompt with markers made it worse (not used).
- [x] **Cutshion**: SYSTEM prompt (developed by Cutshion Company, 2 years old, never another company), vendor
  manuals (knowledge/jaka_zh) out of the index, Korean name 쿳션.
- [x] **Varied replies**: `assistant/talk_examples.py` (658 exchanges, EN / KO, all Korean replies polite);
  the 4 closest go with each question (`brain._examples`, ~14 ms); on a mission also `assistant/interrupt_examples.py`.
- [x] **Korean speech levels**: reader understands 반말 / 해요체 / 하십시오체 (240 / 240); SYSTEM rule: always answer
  politely; fixed phrases checked polite.

## Running now (agents; results go to logs/)

- [ ] **LLM choice** (`tests/llm_bench.py`, logs/llm_bench.md) — **paused 19:25, resume tomorrow with nothing else on
  the GPU.** Measured (387 utterances): gemma4:26b action 86 % (92 % with the keyword rules), answers 94 %, first
  sentence 2.4 s; gemma4:e4b (now) 79 % / 87 %, 98 %, 1.6 s; qwen3:8b / 14b answer Korean in English (ruled out);
  qwen3:30b-a3b ignores think:false (removed with ollama rm). Left: qwen3:30b-a3b-instruct-2507-q4_K_M and
  qwen3.6:35b-a3b (both downloaded), and gemma4 e4b / 26b again on the same frozen prompt:
  `.venv/bin/python tests/llm_bench.py snapshot`, then `run <model>` for the four, `latency <model>`, `report`
  (15–20 min per model). Then set `brain.MODEL` (gemma4:26b leads so far: +0.8 s, more 반말 — the polite rule now in
  SYSTEM should fix that) and `ollama rm` the unused ones (~60 GB). Applied from it already: a `stop` intent
  (stop it / stop Lumi / freeze / 멈춰 / 그만 가), more goodbye words, prompt lines (stop vs quiet, a place not on the
  map is none, fetch only with an object, short Korean commands).
- [x] **Question sets + Lumi's own facts** (`tests/conversation_cases.py` 623, `tests/status_cases.py`,
  `tests/conversation_check.py`, knowledge/lumi_about_en.md rewritten from docs 00–17: size, arm ~1 kg, cameras,
  lidar, Thor, battery ~10 h, can / can't, FAQ, Korean summary): 546 / 623 routes, 503 / 623 all right before the
  fixes. Applied: its `STATUS_Q` (264 / 267 status questions, 0 / 156 near misses), Cyrillic / Chinese / Japanese
  not acted on, no web lookup when a "not sure" is about Lumi or points to staff, SYSTEM facts about Lumi (Whisper +
  Gemma 4 on the Thor, sensors), unclear / other-language rules, negation in the keyword rules ("don't go to p1"),
  fetch before come, 커션 / 컷션 -> 쿳션 in the stream, "say hi with your hand" = wave. knowledge.py loads the index
  fully and replaces it atomically (a rebuild crashed readers).
- [x] **Cutshion company** (from cutshion.com, all pages + the site's API for history / partners / news):
  knowledge/cutshion_en.md ("Company in short" first, every robot app — barista, drawing, cooking, ice cream, candy
  ball, welding, palletizing, education kit —, CUVision / Pionoid / GOMCOOK, TUSK / PEITIAN / cobots, awards, offices
  (head office: Mullae SK V1 Center, Seoul), contact, a "Not known" list), assistant/company_examples.py (255),
  tests/company_cases.py + company_check.py: 156 / 167 questions, 16 / 21 dialogues before the fixes below. Applied:
  gemma4's byte tokens for 쿳 ("<0xEC>...") joined in `brain._stream` (TTS read garbage), SYSTEM lines (쿳션 only;
  short company answer then "what else would you like to know?"; company questions never searched online, "I don't
  have that information"; CEO questions are not about Lumi; never mention "the notes"), `lumi.COMPANY_Q`: no web
  lookup for company questions. Next: re-run `tests/company_check.py`.
- [x] **Dialogues** (`tests/dialogues.py` 230 multi-turn, `tests/dialogue_check.py`, logs/dialogue_check.md): an
  80-dialogue subset gave 255 / 350 turns (EN 78 %, KO 64 %) before the fixes. Applied: SYSTEM lines (short
  follow-ups are about the previous answer, "say it again", "in Korean?"; nothing is known about the event / venue,
  ask a staff member, never drive to a guessed place; numbers in the notes are facts; thanks / done = end, no
  "anything else?" every time), notes for a short follow-up searched with the previous question, keyword rules
  don't act on questions ("how do you pick up a cup?", "혼자 충전하러 가요?", "yes, go ahead"), weather words
  (cold outside, umbrella, 우산), goodbye words (수고하세요, 잘 있어요), "emergency stop button?" doesn't stop, no
  web lookup for a "not sure" about Lumi or the venue, farewell varied (no "You're welcome" / "Have a great day"),
  talk examples fixed to the notes (battery ~10 h, ~1 kg) plus venue "not sure" pairs. Next: re-run
  `tests/dialogue_check.py` (subset) and then `--all` (230) when the GPU is free.

## Re-check fixes (2026-10-19)

Results of 2026-10-16: dialogues 269 / 325 turns, conversation 558 / 623, company 165 / 167 + 19 / 21. Most "wrong
action" / "search(unsure)" failures were the check harness not routing like `lumi.answer()`. Fixed:
- `lumi.answer()` decisions are now functions both lumi and the checks call: `stop_order`, `status_question`,
  `says_goodbye`, `read_mission`, `not_online` (no web search for Cutshion or this event / building: `VENUE_Q`),
  `look_up_unsure` (no lookup for Lumi / company / venue questions, also for a follow-up of one).
- `brain`: `Brain.topic()` (short follow-up or "it / they / 그거" joined to the previous question for notes, examples,
  lookup decision; "tell me more" after the lidar no longer gets the company examples); "How can I help you?" after
  an answer dropped (`HELP_OFFER`); the LLM's go_to only to a place the words name (`named_place`); intent: "where's
  your emergency stop?" is not stop, "왼쪽으로 돌아" is left (was around), "can you pick up a bottle?" is a question,
  "컵 좀 집어", "go to p5 and get the banana" = fetch, more weather wordings, "포인트 원"; UNSURE no longer counts
  refusals ("unable to", "안내해 드릴 수 없") as not knowing; farewell: 3 random goodbye ideas, not one of the last 8,
  never a greeting; SYSTEM: name only when asked, Gemma by Google, the date / time from "Now it is".
- `lumi`: "nice to meet you" is not a goodbye, "그렇구나. 안녕!" / "see ya" are; a lone "say ..." is talk, not a mission.
- Examples / notes: misleading examples replaced (copied joke, "It was nice talking with you", dance, alive, drawing
  robot); venue examples; notes: Gemma by Google + 80억 parameters, lidar range, slow with a cup (spill), safety and
  where used in Korean, Cutshion a startup, candy ball speed. Index rebuilt.
- Expectations changed (clearly wrong): lone "그렇군요" / "good job" may end (docs/14 §4); fetch | mission for
  commands the plain fetch or a mission both do; "business model" answered from the notes; "가까이", "주변", "contact"
  accepted; "I'll go eat then" may end; the judge no longer fails a greeting answered with a greeting.
- Offline: test_steps 1158/1158, test_fetch, test_fetch_intents, test_intents, test_mission_talk ok,
  interrupt_check 288/301 (same as before these changes). LLM re-checks started 2026-10-19 12:30
  (logs/company_run.log, conversation_run.log, dialogue_run.log; logs/recheck2_done when all ended): read the reports,
  then `tests/dialogue_check.py --all`.

Round 2 (2026-10-19 afternoon): results after the fixes above: company 167/167 + 20/21 (was 165 + 19), conversation
583/623 all right (was 558), dialogue subset 299/325 turns (was 269). Then: new blind cases (agents):
tests/conversation_cases_more.py (618), tests/company_cases_more.py (201 questions, 41 dialogues),
tests/dialogues_more_a.py (120, English-led), tests/dialogues_more_b.py (129, Korean-led), wired into the case
files (conversation 1241 cases, company 368 + 62, dialogues 479). Fixes from them and the remaining fails: company
examples only with company talk, topic over the last two questions, Latin-letter other languages -> "I only
understand English and Korean" (`brain.other_latin_language`), "쿳션" written "Cutshion" in English replies,
repeated goodbye openings tried again, "hand it over / 테이블에 놔" with nothing held -> "I'm not holding anything"
(`lumi.empty_hand_request`), Korean questions without "you" about the robot's parts not looked up, orders not looked
up, keyword-rule search refused for company questions, COMPANY_Q narrowed ("CEO of Nvidia", "비트코인 가격" are
searched), questions not taken as moves ("at what battery level do you go back", "물컵은 가져다줄 수 있어요?",
"루미가 … 수 있어요?"), "turn left 45 degrees", no silent 3 m cap ("move forward ten metres" is talk), "stop
greeting" = quiet, "나 이제 집에 가" = goodbye, "손주가" is not 주가, notes FAQ (EN + KO).

Latest numbers, gemma4:26b (2026-10-19), on the enlarged sets: company 352 / 368 questions, 55 / 62 dialogues
(before the company retrieval fix below); conversation 1146 / 1241 all right, 1189 route right; dialogue subset
313 / 343 turns, 56 / 80 dialogues. Offline: test_steps 2035 / 2035, test_fetch, test_fetch_intents, test_intents,
test_mission_talk ok, interrupt_check 288 / 301.

Done after those runs, not measured yet: company talk gets 4 note chunks (`brain.NOTES_K_COMPANY`, partner names in
`COMPANY_TALK` / `lumi.COMPANY_Q`); the notes are also searched with the question before ("how heavy can the items
be?"); tests/company_check.py refuses a search like lumi (`lumi.not_online`); "I can't see you" is no longer a
goodbye; a stray "ACTION: ..." in a sentence or a goodbye is cut; Korean replies say 쿳션, not Cutshion.

Open (next session, in order):
1. Re-run `tests/company_check.py`, `tests/conversation_check.py`, `tests/dialogue_check.py` (subset), then
   `tests/dialogue_check.py --all` (479 dialogues; never run yet, ~6 h with 26b).
2. Facts in the notes the model still misses: Cutshion follow-ups (Sonovictus 200 from 2027, seed 500 million won,
   palletizing 20 kg, awards), Lumi's drive (two wheels, hub motors), battery (24 V, 45 Ah), arm in Korean
   ("팔은 어디 거예요?" -> Mini 2), detector (YOLO), serving (Ollama), target market.
3. Venue questions sometimes get the action unclear ("여기 몇 시까지 해요?", "When is the next demo at this
   booth?"); "Sorry, Loomy?" gets unclear instead of "Lumi".
4. "And in Korean?" / "한국어로!" do not always repeat the previous answer.
5. Expectations to review with the owner: "그럼 가 보세요" after Lumi offers to go to p3 (docs/14 says it ends the
   talk), "Can you move?" from a cleaner (Lumi moves back 1 m).

## Overnight 2026-10-19 (gemma4:26b)

Decided by the owner: (a) after Lumi talks about going somewhere ("p3로 갈 수 있어요?"), a plain "go ahead" / "yes, go" /
"그럼 가 보세요" is consent: Lumi drives there and the talk goes on (`lumi.consent_place`, `go_offered`); (b) a cleaner's
"Can you move?" / "비켜 줄래요?" = the checked 1 m back-off (`brain` rule make_way -> move back 1).
My decisions: the "not sure" -> look it up fallback is off for 26b (`lumi.UNSURE_LOOKUP`; 26b picks search itself,
11 of 11 of its not-sure answers were about Lumi / Cutshion / the venue); a move over 3 m asked of the LLM is not
driven; general knowledge (Einstein, Everest) may be answered without a lookup (two expectations widened).
Fixes: knowledge chunks smaller (320 chars, one paragraph each, the section heading and the paragraph's first words
in front) and search adds a bonus for rare question words found in a chunk (names, numbers: Sonovictus, 20 kg);
3 chunks per question, 5 for company talk; "say it again" / "and in Korean?" / "한국어로!" repeat the last answer
(`Brain.again`, `repeat`); varied "don't know" wording (SYSTEM, `lumi.not_known`); SYSTEM: a clear sentence is never
"unclear", general knowledge answered directly; status: the 3 missed questions and 4 more wordings caught, an empty
hand said ("my hand is empty"); more empty-hand requests; weather words (coat, typhoon, fog, humidity, wind); "서,
서!" = stop; lookups / weather in the checks carry no words (lumi does not say them).
Round 4 (all of the above) started 19:02: logs/company_run.log, dialogue_run.log, conversation_run.log,
logs/round4_done at the end; round 3 reports kept in logs/round3/. Round 4: company 358 / 368 + 61 / 62 (round 3: 352 + 55), dialogue subset
323 / 343 turns, 64 / 80 dialogues (313, 56), conversation 1182 / 1241 all right, 1225 route (1146, 1189); reports in
logs/round4/.
After round 4: expectation regexes that missed right answers ("잘 몰라요", "스태프", "세 대", "만 이해", "밀면 안",
parameter count 26 for gemma4:26b); notes worded with the words people ask (DOF, footprint, IMU, repeatability,
differential drive, TTS, Ollama serves; Korean FAQ: gripper Zimmer 4.5-8.4 cm, only cups tried live, camera 10 m,
position 5 cm, nothing over 1 kg); a question is never a drive ("where is your charger?" drove home:
`brain.QUESTION_START`); a go_to the words don't name says which places Lumi knows instead of "okay, going"; "look
up" / "위를 봐" = look; "그리퍼에 뭐 있어?" = status; target market / business model never searched; "say bye in
Korean" says it in Korean; SYSTEM: no search for opinions / fun facts / recommendations, nothing over 1 kg; examples
(name misheard, photo in broken English, phone / laptop can't be picked).
Round 5 (after those fixes; the index still had the old gripper text): dialogue subset 326 / 343 turns,
67 / 80 dialogues; conversation 1205 / 1241 all right, 1230 route; company 362 / 368 + 60 / 62.
`tests/dialogue_check.py --all` (479 dialogues, first full run, 20:50-23:36): 1760 / 1904 turns, 355 / 479
dialogues; report kept in logs/all1/.
After --all (index rebuilt with the 6-9 cm gripper text): the model's "unclear" on short, broken but clear words
is asked once more (`brain.has_meaning`, `UNCLEAR_RETRY`; "uh the um" stays unclear); the LLM's end needs goodbye
or thanks words ("Alright then." / "Neat." wait for silence, docs/14 §4); no stop action for a question ("how do I
stop you?"); the consent place comes from the visitor's question or Lumi's own offering question, not from an
example in an answer; "한국어로 다시 말해 줄래요?" / "한국어로 말해 주세요" repeat in Korean; Korean words asked for
are written in Hangul; "어디 가려고" = status; awards never searched; "need a jacket?" = weather; expectations: the
parameter count is 26 (gemma4:26b), "only English and Korean" counts as no; `dialogue_check.py --failed` re-runs
the dialogues that failed in the saved .json.
Confirm runs (2026-10-20 night): the 124 dialogues that failed in --all: 41 / 124 now right, 408 / 511 turns
(logs/dialogue_check_failed.md); the subset fell to 319 / 343 turns, 63 / 80 (logs/dialogue_check_subset6.md).
Cause of the drop (compared turn by turn with round 5): the new end rule wanted goodbye words and missed "Good
day", "cya", "I'll be in touch", "that's enough for now", "고맙네" (5 turns): those words added; the checks' {h24}
did not match "00:35" after midnight (3 turns): fill() accepts 00; "정보는 없어요" was not in the not-sure regex
(1 turn): added; one judge call is noise. Subset re-run (01:09): 329 / 343 turns, 70 / 80 dialogues.

Final numbers (gemma4:26b, 2026-10-20): company 362 / 368 + 60 / 62; conversation 1205 / 1241 all right (1230
route); dialogue subset 329 / 343 turns, 70 / 80 dialogues; --all 1760 / 1904 turns, 355 / 479 dialogues (before
the post---all fixes; of its 124 failed dialogues 41 are right in the --failed re-run). Next: `--all` once more.

`--all` again with all fixes (2026-10-20, ended 11:41, logs/all2/, subset report kept in
logs/dialogue_check_subset7.md): **1791 / 1904 turns, 385 / 479 dialogues** (was 1760, 355). 46 dialogues newly
right (end with no goodbye words, unclear on broken but clear words, "do you speak German?", stop for a question,
parameter count, gripper width), 16 newly wrong, 78 still wrong. Causes: missing 65 turns, wrong action 32, ignores
the question 23, Korean reply to English 5. The failing turns (113), grouped:
- Model left out a fact it has or said "not sure" (~30): base 50 kg, arm 9.9 kg, battery 24 V / 10 h, Zimmer
  gripper, awards, schools / customers, venture certificate 2023, threshold 1.5 cm, phone number.
- Model made up an answer where "not sure" is expected (~12): "sees in the dark", "Python", talks counted.
- End of talk (10, 6 of them new): Korean casual goodbyes are not ended. `brain.py` drops the LLM's end without
  `FAREWELL_TEXT` words or with any "?" in the text: "빠이빠이!", "간다~", "잘 있게", "바이", "땡큐", "벌써요? 가 볼게요.".
  `lumi.FAREWELL_WORDS` has none of them either.
- Wrong action (~17): sing after "Prove it" / "Try again" following a joke; wave for "say hello" / "hello 해 봐", no
  wave for "can you wave?"; search for "협동 로봇이 뭐예요?" / "빨간 옷 친구 봤어요?", no search for follow-ups
  ("How old is he?", "입장료 얼마예요?"); "temperature 몇 도예요?" not weather; "and down?" not look down.
- Unclear on clear words (6): "Where from?", "v 몇?", "네, 해 주세요.", "Photo? With you? Ok?".
- Language (7): "English로 말해 줘" answered in Korean; "쿳션" in Hangul inside English replies.
- Judge noise (~12): "우와" / "아 네" / "Good evening" answered briefly and counted wrong.
- Check gaps (~7): "모르겠어요", "영어랑 한국어만 할 수 있어요", "2년 전에", "세 대", the time check at 10:59.
Not fixed yet (the owner decides).

Fixes for these groups (2026-10-20 afternoon, gemma4:26b):
- Facts: a short fact sheet in `brain.SYSTEM` ("Facts you know", from knowledge/*.md only): weights (all 96 kg,
  base 50 kg, arm 9.9 kg; carries 2 kg incl. gripper, ~1 kg in the hand), arm speed, Zimmer gripper, drive, step
  1.5 cm / slope 8° / passage 70 cm, battery 24 V 45 Ah ~10 h, cameras, YOLOv8, Whisper large-v3-turbo, Gemma
  (Google) via Ollama, Cutshion (products, phone, email, lab 2023, venture certificate Dec 2023, investment, awards,
  customers, target places). A "not known" line (dark, noise, ROS, talks counted, charge time, battery now, wiping,
  prices). Rules for "who made that?" after a part, a correction after a weight question, "How much?" after an
  answer.
- Goodbyes: 빠이빠이, 바이, 땡큐, 간다~, 잘 있게 in `brain.FAREWELL_TEXT` and `lumi.FAREWELL_WORDS`; the LLM's end
  is dropped only for a "?" in the last sentence ("벌써요? 가 볼게요." ends).
- Actions: `Brain._after()` checks the action line against the turn before: sing only when a song is asked for or
  right after a song; "and down?" after a look looks down; a follow-up with he / there / 거기 / 왜 / 얼마 right after
  a lookup is looked up. Wave only for wave words (`WAVE_ASK`; "Hello Lumi!" / "hello 해 봐" is talk); a wave
  keyword rule (`INTENTS`) so "sorry. can you wave?" waves; "temperature" is weather. The sing action no longer
  writes lines (a real song plays, `audio/sing.py`); the talk examples about singing say so.
- Language: `reply_language()` answers in the language asked for ("English로 말해 줄래요?", "영어로 자기소개 해
  봐"); "English로 다시 말해 줘" repeats in English; a sentence with no other Hangul writes "Cutshion", not 쿳션.
- Date: the prompt's time line also in Korean form (`now_line()`): with the English form alone the model said
  "10월 21일" on 20 October, every time.
- Checks: `dialogue_check.py --help` (never starts a run), a list of numbers ("9,21,309"); NO accepts 모르 / 몰라 /
  "만 할"; AGE "2년"; "세 대"; "plenty"; the hour check accepts the hour of 5 min before (`HOUR_SLACK_S`);
  `conversation_check.rules_route` sends sing requests to the song like `lumi.answer()`.

Results: subset **338 / 343 turns, 75 / 80 dialogues** (was 329, 70; logs/dialogue_check_subset9.md); the 57
targeted failed dialogues of all2: 40 right in the first re-run, of the 15 still wrong after a second fix 12 right
(logs/dialogue_target_r1.md, r2). Company 363 / 368 + 60 / 62 (was 362, 60), conversation 1212 / 1241 all right
(was 1205), route 1226 (was 1230; flaky LLM routes: "멈춰, 어디 가?", "미세먼지", "기조연설 몇 시"). Still wrong:
"Photo? With you? Ok?" unclear, "Who do I call?" without the phone, "거기 입장료" refused online by
`lumi.VENUE_Q` (입장료), "모델은 어떤 거요?" without large-v3-turbo, judge noise. First sentence in the checks
~3.9 s median (was 3.1): the longer prompt is prefilled again after each judge call; with one system prompt
(live) the cached prefix makes it the same (measured 1.6–1.9 s both ways). `lumi-api` not restarted; the assistant
loads the change when Greeter is switched on again.

Body commands in any wording (2026-10-20, owner's request). Abilities the code has, with their limits: go to a
marker; come; move forward / back / left / right (≤ 3 m) and turn (degrees, around); look left / right / up / down
/ center / at me, now also degrees or a small step (head yaw ±60° in `robot/head.py YAW_LIMIT`, pitch −5…35°);
lift up / down / small step / mm (new, 0–105 mm for now, `lumi.lift`, slow); arm reach / fold, hand open / close;
wave; pick / put / move_object / fetch / give / place / receive; missions (steps.py: go, move, turn, pick, receive,
say, place, give, hold, arm, wait); sing; quiet; stop. Keyword rules take the common wordings at once (`brain.
INTENTS`: head words before the base turn, "고개 왼쪽으로 돌려" was a base turn; wave for "shake your hand" / 손
흔들어 / 손 인사; lift words; "fold your arm" / 팔 접어; "앞으로 조금만 와"); look, lift and wave are now quick
commands. Anything else goes through the LLM's ACTION line, which lists every ability with its values and limits
and says that any wording counts and that jump / dance / fly / stairs / doors are answered plainly; `_action`
checks the values. A number past a range is cut and said ("I can turn my head up to 60 degrees each way").
Objects and places are still never guessed. Checks: tests/test_intents.py +91 EN/KO/mixed cases and the head /
lift goal limits; new tests/dialogues_commands.py (10 dialogues, 42 turns, `dialogue_check.py --commands`): **42 /
42**, 23 of them by the LLM path. Subset **338 / 343, 76 / 80** (the two misses in 281 were "lower yourself" now
doing the lift, expectation updated, and "look down at me", fixed: 281 right on re-run); conversation 1215 / 1241
all right, route 1227. First-sentence times in these runs were 4.9–7.3 s median while other agents used the GPU.
Commanded looks use the body's full head yaw (`head.AXIS_LIMITS`, ±180°, also "look behind you" / 뒤를 봐) through
`head.moveto`; `head.YAW_LIMIT` (±60°) stays for following people. --commands then 44 / 44. Not done: look and lift
as mission steps (they need a step runner in tasks/fetch.py).

## Commands in any wording (night 2026-10-20, agent A)

Goal for the live test: any command or question a native English / Korean speaker says is the right action or a
short question back, never a wrong motion. Inventory of what Lumi acts on (order in `lumi.answer()`): other script ->
mission talk (on a mission) -> name only -> stop (`stop_order`) -> what the cameras see (`seeing.answer`, agent B) ->
status (`status_question`) -> **the hand (`lumi.hand_command`: `brain.correction`, `brain.hand_request`)** -> mission
(`read_mission`, steps.py: go, move, turn, pick, receive, say, place, give, hold, arm, wait) -> fetch / give / place
while holding (`fetch_voice`) -> consent to go -> empty hand -> goodbye / closing words -> song -> keyword rules
(`brain.intent`: quiet, stop, look incl. away, fetch, come, go_to, sing, wave, turn, make_way, move, put,
move_object, pick, grip open / close, arm reach / fold, lift, weather, search) -> lookup follow-up -> the LLM's
ACTION line (go_to, come, look, lift, move, turn, arm, wave, pick, put, move_object, fetch, give, place, receive,
stop, quiet, sing, weather, search, end, unclear, none), each value checked in `Brain._action`.

New: `brain.hand_request(text, holding, b=None, markers=(), whole=True)` -> `("receive", object or None)` |
`("give", None)` | `("place", None | place_on() dict | {"pointed": True})` | `("refuse", (en, ko))` | None, any
wording EN / KO / mixed, fillers and "루미야 / 혹시 / 저기" first; `lumi.receive_from_hand` (the camera first:
`scene.person_holds` False -> "I don't see an apple in your hand", nothing moves; can't tell -> "Do you have
something for me? Hold it out, please.", on only after yes / seen; then the receive step with `from_hand`);
`brain.correction` ("no, the other one" right after a pick: the arm stops, "Which one do you mean?"; "no, the red
one" picks that); look away (`HEAD_AWAY_DEG` 60°; "stop staring at me" is no stop); "pass me the cup" / "컵 좀 줘" =
pick + give mission; every class of `skills.GRASPS` has words (`brain.OBJECTS`, not umbrella / 책; 공 / 칼 only as a
word) and a pick / receive / mission of one the fingers can't take answers its reason (`skills.refusal`); "put it
here / there" = where the person points. Bugs found: the LLM's pick target was always dropped and `object_task`
then picked a cup ("pick the banana" by the LLM picked a cup); "grab the cup, thanks" ended the talk; "stop looking
at me" stopped everything; "take the cup from me" drove "here" and picked from the table; "탁자에 놓아 주세요" opened
the hand; "open your hand" while holding dropped it. LLM side: receive in the ACTION list, give / place / look away
wordings, "never promise with none", questions ("손 펼 수 있어요?", "do you know how to wave?") and "I have an
apple" / "my friend is over there" are no motion, its pick object must be a word said (no translating).
Also (agent D's list): a short follow-up right after a lookup ("Where?", "몇 살이야?", "How tall is it?") is looked
up, a bare "search ..." line is the search action, `lumi.VENUE_Q` refuses only when no place elsewhere is named
("루브르 몇 시까지 해?" is looked up).

Test set: `tests/command_cases.py` (templates x slots x fillers: 2523 cases, EN / KO / mixed, idle and holding,
questions, jokes, things it can't do, near misses, ASR slips, rambling, corrections, slang), `tests/command_check.py`
(rules only; `--llm` the rest through the real model; `--cached`). Right / missed (no motion) / wrong (a motion not
asked for), before (old code, the first 958-case version) -> after (2523 cases, logs/command_check.md):

| intent | before cases | right / missed / wrong | after cases | right / missed / wrong |
|---|---|---|---|---|
| receive (take from the hand) | 214 | 0 / 98 / 116 | 509 | 509 / 0 / 0 |
| give | 67 | 53 / 14 / 0 | 242 | 242 / 0 / 0 |
| place | 61 | 49 / 5 / 7 | 187 | 187 / 0 / 0 |
| pass me (pick + give) | 72 | 7 / 57 / 8 | 201 | 201 / 0 / 0 |
| pick | 164 | 156 / 0 / 8 | 460 | 460 / 0 / 0 |
| hand open / close | 40 | 25 / 4 / 11 | 109 | 109 / 0 / 0 |
| look (incl. away) | 55 | 37 / 2 / 16 | 101 | 100 / 1 / 0 |
| arm, base, body, fetch, mission | 126 | 124 / 0 / 2 | 234 | 234 / 0 / 0 |
| status, seeing | 30 | 30 / 0 / 0 | 166 | 166 / 0 / 0 |
| can't do, questions, chat, near misses | 73 | 71 / 0 / 2 | 222 | 221 / 1 / 0 |
| corrections, follow-ups, tricks | 21 | 13 / 4 / 4 | 21 | 21 / 0 / 0 |
| mixed, ASR slips, rambling, slang | 35 | 24 / 8 / 3 | 71 | 68 / 3 / 0 |
| **all** | **958** | **589 / 192 / 177** | **2523** | **2518 / 5 / 0** |

296 of the 2523 went to the LLM. Left (no motion, a question back): "고개 돌려" (asks which way), "uh take the uh the
cup" (unclear), "hand that to my colleague over there" (asks who), "chuck it on the table", "놀라지 마" (unclear).
Not done: "put it next to the laptop" puts it on a free spot in front (no "next to" placing); a pointed "here" only
in the quick path, not as a mission step; the dashboard Command box (`/tasks/parse`) does not use `hand_request` yet
(agent D adds it).

Checks after these changes (gemma4:26b, other agents' changes in too): dialogue subset **341 / 343 turns, 78 / 80
dialogues** (was 338, 76; logs/dialogue_check_subset_b.md), conversation **1219 / 1241** all right, route 1230 (was
1215, 1227; logs/conversation_check_b.md), company **365 / 368 + 60 / 62** (was 363 + 60), `--commands` **44 / 44**,
every `tests/test_*.py` passes (test_steps 2035 / 2035). Harness: `conversation_check.rules_route` takes the hand
route like lumi; a pick of a thing the fingers refuse counts as answered with the reason (conversation and dialogue
checks); the expectation for "pick up my laptop" accepts "too big". Files: assistant/brain.py, assistant/lumi.py
(hand_command, receive_from_hand, says_goodbye, stop_order, read_mission, object_task, VENUE_Q / OUTSIDE,
_STATUS_P, act), assistant/steps.py, assistant/wording.py, assistant/fetch_dialog.py, tests/command_cases.py (new),
tests/command_check.py (new), tests/test_intents.py, tests/test_steps.py, tests/test_fetch.py (refusal before the
mission starts), tests/conversation_check.py, tests/conversation_cases.py, tests/conversation_cases_more.py,
tests/dialogue_check.py, docs/14, docs/17, docs/WORK_PLAN.md, docs/ROADMAP.md.

## Reply speed (night 2026-10-21, latency agent)

From the end of speech to Lumi's first sound, a warm turn (measured offline today, parts one at a time; the runner
and whisper were shared with four other agents' checks, so the numbers under load are higher):

| Part | Before | Now | How |
|---|---|---|---|
| End-of-speech wait (`mic.END_SILENCE`) | 0.6 s | 0.6 s | kept: in 76 recorded utterances (logs/heard) 9 had pauses of 0.48–0.57 s inside; 0.5 s would cut ~10 % of them for 0.1 s |
| Whisper (large-v3-turbo q5_0, GPU) | 0.4–0.6 s idle, 0.9–1.6 s with the GPU busy | same | `audio_ctx` (whisper's shorter encoder window) tried: turbo writes garbage and falls back to slow retries (16 of 16 clips wrong); not used |
| Rules before the LLM (lumi.answer checks, knowledge search, examples) | ~60 ms | same | measured, small |
| Route (action line): prompt processing | ~560 tokens warm (~0.65 s); ~4700 after any other prompt (3.7–5.0 s) | ~460 tokens in both cases (~0.5 s) | `brain.warm` / `llm_direct.prefill`: before each listen the next prompt's start (system + turns kept) is sent with n_predict 0; checked token for token (/tokenize) that it is the start of the next prompt |
| First sentence (generation) | +0.15–0.4 s | same | |
| TTS of the first sentence | 0.5–1.9 s (CPU) | 0.07–0.13 s | `audio/tts_gpu.py`: vector estimator + vocoder as TensorRT engines; the sound differs from the CPU's 50–100x less than two CPU runs with other noise |
| Total, warm | ~2.6–3.1 s | ~2.0 s | |
| Total, right after a lookup / farewell / mission read-back / picture | ~5.5–7 s | ~2.0 s (when the prefill finished while the person spoke: cold prefill ~3.5 s) | |

Accuracy: the routing prompt is the same string as before (`brain.route_system`, checked equal); the prefill only
changes what is cached. TTS: same voice (spectral distance GPU-CPU 0.01–0.02 against 0.7–1.2 between two CPU runs).
`tests/test_*.py` pass except `test_followup.py` 139 / 185 ("why don't you wave?", "it would be great if you could
wave" -> llm): wave rules, not from this work. command_check / dialogue_check were not re-run here (their reports in
logs/ belong to the commands and conversation agents; nothing in the routing changed).

Not done, for the other agents:
- **ASR agent**: whisper is now the biggest part after the fixed 0.6 s wait. Ideas with numbers to check in
  `tests/asr_check.py`: (1) start transcribing when the speech has been quiet 0.3 s (`mic.Segmenter` knows it) and
  keep the result when the utterance then ends without new speech: ~0.3 s sooner; 32 of 76 utterances had an inner
  pause of 0.3 s or more, so the early run is often thrown away (whisper is busy 0.4 s for nothing then). (2) The
  f16 large-v3-turbo may be faster on the GPU than q5_0 (not downloaded). `audio_ctx`: no (above).
- **Conversation agent**: the ~460 tokens a question still costs are its notes (150–350 tokens, `NOTES_K` 3) and
  examples (120–180, `EXAMPLES_K` 4) and the time line (44): each 100 tokens fewer is ~0.1 s.
- A second Ollama slot is not needed with the prefill (and would mean restarting Ollama).
- Live check: ROADMAP Next 0a-4.

## Commands, second night (2026-10-21 night, commands agent)

New sets (not in yesterday's): `tests/command_cases2.py` (771 single commands on the conference map: every
ability in polite / casual / 반말 / 존댓말 / 하십시오체, indirect, negation, conditions, corrections inside the
sentence, fillers, code-mixing, whisper's spellings), `tests/steps_cases7.py` (148 missions of 2-5 steps EN / KO /
mixed + 5 with corrections + read-backs, 10 for the LLM pass), `tests/test_mission_route.py` (the same through
`lumi.read_mission` and the Greeter-only rule). Checks: `tests/command_check.py --new` (`--old` yesterday's set,
`--cached` re-checks saved action lines with today's `Brain._action`), `tests/steps_llm_check.py`.

| group (new set) | cases | before: rules right / missed / wrong / to LLM | after, rules + gemma4:26b: right / missed / wrong |
|---|---|---|---|
| go to a marker | 220 | 106 / 0 / 0 / 114 | 220 / 0 / 0 |
| not a drive now (negation, question, condition) | 110 | 5 / 5 / 5 / 95 | 104 / 6 / 0 |
| corrections inside the sentence | 86 | 2 / 19 / 26 / 39 | 86 / 0 / 0 |
| speech levels, slang, whisper spellings, "can you ...?" | 85 | 49 / 0 / 1 / 35 | 84 / 1 / 0 |
| come, come back, follow (+ near misses) | 66 | 42 / 0 / 3 / 21 | 66 / 0 / 0 |
| move, turn, again (+ near misses) | 49 | 35 / 6 / 0 / 8 | 49 / 0 / 0 |
| look, lift, wave, bye (+ near misses) | 58 | 47 / 0 / 5 / 6 | 58 / 0 / 0 |
| pick, held, hand, fetch | 53 | 41 / 1 / 0 / 11 | 53 / 0 / 0 |
| missions, a part that is no step | 12 | 4 / 0 / 6 / 2 | 12 / 0 / 0 |
| stop, speed (+ near misses) | 32 | 25 / 0 / 1 / 6 | 32 / 0 / 0 |
| **all (new)** | **771** | **356 / 31 / 47 / 337** | **764 / 7 / 0** (170 by the LLM) |
| yesterday's set (now 2756 cases) | 2756 | 2518 / 5 / 0 of 2523 | 2748 / 4 / 0, 4 not re-run |
| blind set (`tests/command_cases3.py`, written by an agent from docs/14 + 17 only) | 451 | first run, rules: 311 / 3 / 20 / 117 | 446 / 3 / 0 (109 by the LLM), 1 not re-run |

Missions on the conference map (`steps_cases7`, rules only): 86 / 142 before, **148 / 148** after (+ 5 / 5 with a
correction, 3 / 3 read-backs EN + KO); the blind missions (`tests/steps_cases8.py`, 121, ~30 must stay unread):
113 / 121 on the first run, **121 / 121** after (269 / 269 in test_steps with both); the LLM pass on wordings the rules leave a part of: 9 / 10 (the 10th, "let
Sarah have it", is now read by the rules); the "?" ones stay unread. Yesterday's mission sets: test_steps
2039 / 2039 unchanged, interrupt_check 288 / 301 (same).

Wrong motions found and fixed: "go to start, sorry, I mean end" drove to start; "pick up the cup, no, the bottle" /
"컵 집어, 아니 병" picked the cup; "앞으로 1미터, 아니 2미터 가" drove 1 m; "뒤로 1미터, 아니 50센티만 가 줘" drove
forward (the LLM); "테이블 프론트 앞으로 가" drove 1 m forward instead of to table_front; "먼저 스테이지 가서 컵
가져오고 그다음 여기로 와서 줘" came to the person (the come rule on a part); "go to the stage and wave / follow me /
look left", "go to the stage and tell Sarah ..." drove and dropped the rest; "take the cup to the stage, not booth
two" also drove to booth two; "after the talk ends, go to ..." / "내가 가라고 하면 ..." drove now (rules and LLM);
"I saw you wave", "the wave was nice", "a new wave of visitors" waved; "shake hands with me" waved (the LLM too);
"can I come closer?" / "come here often?" came; "제 말 따라와요?" followed; "왼쪽으로 45도 돌아" turned the head (LLM);
"스테이지 가서 거기서 기다려" was a stop ("거기 서"); from the blind set: "손 흔들지 마" waved, "손님 오시면 손 흔들어
주세요" and "my friend will come here soon" moved, "turn left at the corner and you'll find the restroom" turned; "Um, ..." / "Uh, ..." at the start was taken as a name by the
new aside rule (147 of yesterday's commands lost their rule), "뒤돌아 봐" too.

What changed: `brain.self_correct` (corrections, "never mind", a stop never rewritten, not on a mission),
`brain.unfill` (fillers inside), `brain.LATER` (conditions / later, rules and the LLM's action), `brain.STOP_ASK`
("can you stop?", "멈출 수 있어?"), go / come / follow / turn / wave / lift wordings in `brain.INTENTS`,
`hand_request` Korean endings, the action prompt (conditions, the last of a correction, handshake), `driving`
"again" / "a bit more" after a turn, `lumi.read_mission` (a part that is a command but no step is asked),
`lumi.FETCH_STOP`, `steps.py` (fillers, splits, -고 나서 / -ㄴ 다음에 / -시-, comma-less clauses, people and places in
any order, "갔다 와", "not booth two", read-back names with spaces).

Left: "how far is the stage?" / "스테이지까지 얼마나 걸려요?" go to the camera's distance answer (`seeing.HOW_FAR`,
conversation agent's file); `wording.norm` turns "to go home" into "to home" on a map with `home` ("I want you to
go home" is then no drive; ASR agent's file); "look at me and wave" / "put it down and wave" do the first part
only (look / lift / wave are no mission steps yet); "한 바퀴 돌아" turns 180° (a full 360° spin is a navigation goal
equal to the start, not driven); "booth number two", "go to booth to" (whisper) are asked; the dashboard Command box (`/tasks/parse`) does not apply
`self_correct`; "take the cup and put it back" is asked.

## Commands, leftovers of the second night (2026-10-22, commands agent)

| leftover | before | after |
|---|---|---|
| "look at me and wave", "웨이브 하고 나 봐", "나 보고 손 흔들어", "lift yourself up and wave"; holding "put it down and wave"; "go to p5 and tell me the weather", "고개 들고 몇 시야?" | the first part only (look / place), or asked | owner's decision: every part in order (`assistant/chain.py` plan, `lumi.chain_run` / `chain_wait`): steps next to each other one mission, keyword commands by `quick_command`, questions by `answer`; a refused part says why, the rest goes on; after a failed mission part the driving / hand parts are said as not done; "stop" / new words end it. `brain.hand_request` leaves "X and <command>" to it; "웨이브 해" is a wave. Self-check `tests/test_chain.py` |
| "한 바퀴 돌아", "spin around", "turn all the way around", "do a 360" | LLM, turn around 180 | rule `turn left 360` (right: "오른쪽으로 한 바퀴"); `lumi.move_by` runs it through `fetch.run_steps`, `fetch._do_step` makes two 180° turns, each arm sweep checked (one 360° goal is the start pose: navigation does nothing). In a mission: step `turn 360`, read back "turn all the way around" / "한 바퀴 돌고" |
| dashboard Command box (`/tasks/parse`) | no `self_correct` | applied first, as by voice; "never mind" → "Taken back: nothing to do.", unsure → "Which one did you mean?" |
| "take the cup and put it back", "컵 집었다가 제자리에 놔" | asked | pick + place here (fetch puts it back where the pick was, `skills._held["base"]`); after a drive still asked |
| "루미야 너 월급 받아?" | receive | talk (`brain.PAID_Q`: 월급 / 전화 / 칭찬 ... 받, "너 ... 받아?") |
| "컵 가져다 줘" | mission pick + give | checked right: the cup in front, handed over ("컵을 집고 건네줄게요."), the same as "pass me the cup"; "컵 가져와" stays the plain fetch |
| "출구로 가" (LLM: go_to exit, not said) | "이 지도에는 that라는 곳이 없어요" | "이 지도에는 출구라는 곳이 없어요 ..." (the Korean word as said, 이라는 after a final consonant: 주방이라는); English "a place called that" |
| "Let's go P5 (point).", "Let's go P9." | LLM, 1.4–4.5 s | rule go_to (let's / lets, a trailing "point"); also "스테이지로 가 줬으면 좋겠어" (the later-check took "줬으면" for a condition) |
| `command_check.py` seeing guess | "how far is the stage?" counted as seeing | `seeing.answer(text, frames=[])` itself decides (None = not seeing) |

Command check (`--cached`, rules + saved LLM lines; the ~40 cases without a saved line asked one at a time, 3 s apart):
yesterday's set 2748 → 2747 right / 5 missed, new set 762 → 844 right of 848 (77 new cases, 26 of them chains and
near misses), blind 448 → 447 / 451; all 4038 right / 11 missed / 1 wrong / 5 not run of 4055. The three that
turned ("스테이지로 가야 해" -> goodbye: the one wrong; "그만 쳐다봐", "thanks, that's all" -> talk) come from the
conversation agent's new closing words (`talk_fate`), not from this work. Missions (`test_steps`, conference map): 284 / 284 (15 new).
Old expectations "spin around" / "한 바퀴 돌아" → turn around changed to turn 360 (command_cases 1-3,
conversation_cases_more, dialogues_commands).

Live fix (13:48, Command box): "let's go exit point and go p9 point" went to the LLM (12.5 s) and came back a fetch
with no object; now `steps._go` / `_place` take "X point" / "X 포인트" / "X 지점" after any marker and "first X then Y",
and `/tasks/parse` returns "I didn't understand: ..." instead of a fetch when no object is named (no LLM). Voice reads
the same as a mission. Cases: test_steps (owner's map), steps_cases7, command_cases2, test_fetch_place.

Command box = voice (owner, 2026-10-22): `lumi.route(text, markers, brain, holding, seen, last, chain_ok)` is the
one routing both use (and `tests/command_check.rules`); `/tasks/parse` turns its result into the dialog's plan:
mission or keyword drive / turn / arm / pick -> steps (`/tasks/steps`), a fetch only with an object named, look / lift
/ wave / come / follow / stop / chains -> `action: "command"` (Start: `/tasks/command`, the assistant answers it as
heard), questions and talk -> shown, nothing to start; rules while typing, the LLM on Enter. `tests/test_command_box.py`
46 / 46 the same by voice and in the box.

Left: `conversation_cases_more.py` expects "출구로 가" → go_to exit, against the rule that a word is never translated
into a place (it is refused with the word as said); "booth number two" / "go to booth to" (whisper) still asked;
"bus stop", "look write" go to the LLM (unclear). Not live-tested: the 360° turn (Patrol on, off the charger, the arm
goes to `look` first like every task turn).

## What Lumi hears (night 2026-10-21, speech-to-text agent)

What went wrong in `logs/lumi.log` (2026-10-13 … 10-21) and the 50 clips in `logs/heard/`:

- **The prompt's "Lumi." for sounds that are no speech**: whisper wrote "Lumi." / "Hey Lumi." for claps, thuds, music,
  "はい" (13 of 15 "Lumi." in logs/heard; without the prompt they read `*clap*`, `*gunshot*`, `はい`). They woke Lumi
  or became a turn ("Lumi." [japanese] four times for "컵 좀 주세요").
- **Own-voice filter dropped the owner's words**: a clip-mic utterance that shared 60 % of its words with anything Lumi
  said in the last 30 s was dropped, also when said seconds after Lumi stopped: "Lumi." after the greeting, "Can you
  see me?" after "I can't see you", "Just follow me." (~20 times).
- **Korean tagged English or Japanese, written in Latin letters**: "나 따라와" → "Natarawa.", "돌아와" → "Torawa.";
  asked again, the old mixed prompt kept it in Latin letters; forced to English, Korean comes back translated.
- **Name and marker slips**: Cutshion → "Kutchen", "coaching company", 커션; "p3로 가 줘" → "p3로 가죠", "P3. 로가줘";
  "go to piece six", "Look last", "Doc T"; "오늘 난시가 어때요?".
- Mixed sentences lose a part ("Lumi, 이리 와" → "Lumi."); short Korean words far away stay the hardest (below).
- Not hearing faults, for the commands agent: "Let's go P5 (point)." / "Let's go P9." (the owner's usual wording) are
  heard right but go to the LLM (1.4–4.5 s) instead of a rule.

Bench: `tests/asr_check.py` makes spoken cases with the Supertonic voices (F1–F5, M1–M5, speed 0.85–1.15), puts them
in a room (near = clip mic: echo 0.15 s, 28 dB; far = head array: echo 0.5 s, 12 dB, three other people talking),
sends them through `ears.transcribe()` on its own whisper-server (port 8097 / 8098, never the live 8096), and through
Lumi's routing (`tests/command_check.rules`). Right = the same route as the written text (and for questions nearly
the same words), the spoken language, understood. Sets: `asr_cases.py` (322 × 2 rooms), `asr_cases2.py` (127 × 2,
the owner's wording and polite Korean, kept apart to check the fixes), `asr_cases3.py` (96: noise, "uh", people
talking not to Lumi; right = no wake word, no motion). Real clips: `--heard` (text only, never committed).

| Set | Before | After |
|---|---|---|
| 1, EN near / far | 148 / 113 of 161 | 149 / 114 |
| 1, KO near / far | 89 / 39 of 135 | 109 / 56 |
| 1, mixed near / far | 10 / 5 of 26 | 16 / 7 |
| 1, all | 404 of 644 (63 %) | 451 (70 %) |
| 2 (new words), EN / KO / mixed | 84 / 93 / 8 of 104 / 130 / 20 | 87 / 97 / 11 |
| 2, all | 185 of 254 (73 %) | 195 (77 %) |
| 3, not to Lumi | 82 of 96 (11 of 12 noise clips woke Lumi) | 93 (0) |
| Real clips, false "Lumi." | 5 of 50 passed | 0 (the 3 real calls kept) |
| Whisper time per call, GPU busy | q5_0 1.36 s median | f16 1.00 s |

Changes (each measured on its own; offline replays of all three transcriptions per case in
`logs/asr_check/collect*.json`):
- `lumi.talk_turn`: on the clip mic the word match counts only for an utterance recorded while Lumi talked.
- `ears`: a name-only text is checked once without the prompt (`CALL_ONLY`, `lumi_like`); retries in one language use
  `LANG_PROMPT`; another language named → Korean and English fixed, Hangul `KO_BONUS` 0.3; English with a word no
  dictionary has (`/usr/share/dict/words`) → Korean too (`ODD_KO_BONUS`); Hangul tagged English is Korean;
  "Lumi야" → 루미야; `SLIPS` (Cutshion, 쿳션, 날씨); the f16 model. Tried and left out: an English/Korean-close retry
  (0 of 898 better, two translated), always both languages for short clips (+11 of 644 for two more calls per clip),
  other prompts (none, "Lumi.", with Cutshion / p8, "…루미야, 안녕하세요.", Korean retry prompt with the name first: within ±3,
  or hallucinated), beam 5 (+3 of 254, slower).
- `wording.ASR_SLIPS` and the "piece six" rule; `lumi.WAKE` takes "Lumia".

Left: short Korean commands far away (KO far 56 of 135: "그만" → "Come on.", "나 봐" → "Naba."); mixed sentences
(23 of 52); a far wake word with people talking (7 of 12); TTS voices are not the owner's accent, so the live check
decides. **To use it**: the whisper-server keeps the q5_0 model until it is started again (stop its process once,
`ps -eo pid,args | grep "[w]hisper-server"`; the API starts it again with f16 on the next listen).
Not done: transcribing after 0.3 s of quiet (speed agent's idea): the f16 model already saves ~0.35 s.

## Web answers without OpenAI (night 2026-10-21, web agent)

Free search + gemma4:26b only (`tests/web_check.py` sets `web.openai_ready` false; the key was never read). New set
`tests/web_cases2.py`: 191 questions + 28 dialogues (56 turns), none from yesterday's: weather (Korean cities,
tomorrow, rain), news, prices / rates, sports results, people, places (hours, distances), dates / holidays,
definitions, follow-ups, and 22 that must not go online. `web_check.py new` -> logs/web_check2.md.

| Set | Before | After | Notes |
|---|---|---|---|
| New set (247 turns) | 213 / 247; answer in the fetched text 146 | **230 / 247**; in the text 157 | weather tomorrow / 모레 9 wrong before, 0 now |
| Yesterday's set (225) | 201 / 225 (yesterday's run) | 203 / 225 | first try with 1200-char pages: 197 (lost Apple 1976, "지금 대통령" from a 2024 page); 1500 chars + news first fixed it |
| Prompt tokens read per looked-up turn (one user, warm), dialogues | median 3710, 90 % 4913 | median 2354 without the warm-up, ~1500 with it (new set 1573, 90 % 2168) | ~1300 tokens/s: ~1.0–1.7 s less to the first sentence |
| Visitor's wait after a lookup | "Let me check." played, then fetch, then the LLM | the LLM starts while "Let me check." plays | ~1 s less (TTS of the phrase overlaps fetch + prompt) |
| First sentence, wall clock | 18.4 s median | 13.4 s median | **not comparable**: the runner was shared with 3–5 other agents' checks all night (a 15-token Ollama call took 30 s once); the token count above is the number to trust |

What changed (`assistant/web.py`, `brain.respond_from` / `LOOKUP_ANSWER`, `lumi.look_up`):
- Weather now and 7 days ahead, today and tomorrow named (`WEATHER_DAYS`).
- English questions about a person, share, index or team also ask Naver with the Korean word of its answer box
  ("Taylor Swift 나이", "Nvidia 주가", "KBO 순위", `web.ko_box_query`): LeBron's height, Apple's stock, Nasdaq,
  LAFC's last games came from those boxes. Not for opening hours ("Louvre 영업시간" gives Korean shops).
- "How far": straight-line distance between the named places (open-meteo geocoder, places under 50 000 people
  refused, airports fixed); "100 dollars", "1만 엔" worked out in won.
- News headlines only for questions about what changes (`NEWSY`), put before the web pages; Naver's places-nearby
  blocks and disclaimers cut; pages 1500 chars.
- `respond_from` uses the routing system prompt (cached; the next turn's routing stays cached); an action line it
  writes instead of the answer ("search New York weather") is dropped; the answer is made while "Let me check."
  plays (`Lumi._looked_up`). A coworker's salary is declined before any lookup.

Still wrong, for the owners of those parts:
- **Routing / intents**: "How many people live there?" and "Who is the CEO of OpenAI?" went to talk (none) and
  were not looked up; the LLM wrote "search ..." without "ACTION:" on talk turns ("search I'll look that up");
  "리플 지금 얼마야?" → "I don't know what 리플 is" (talk).
- **Follow-ups**: "몇 살이야?" after a Korean answer ("샘 올트먼") searches without the name (`NAMES` is English
  only); "내일 비 와?" after Jeju's weather looks up Seoul; "How much is a ticket?" after Lotte World is refused as
  a venue question (`lumi.not_online`).
- Not on the free pages: Seoul subway's last train, flight times, Changdeokgung's closing day, English opening
  hours (the Korean question gets Naver's place box).

## Reading conversation in context (night 2026-10-21, conversation agent)

The owner saw "What about my jeans?" / "what about shoes?" after a clothes question and "what about you?" answered
wrong (fixed in `seeing._follow_up` on 2026-10-21 noon, live since 18:31). New sets, written as a linguist of English
and Korean would read the turns (ellipsis, anaphora, the question turned back, topic shifts, corrections, back-channels,
confirmation questions, teasing / jokes / compliments, indirect requests against ability questions, Korean endings
-지 / -네 / -잖아 / -거든 / -더라 / -는데, honorifics, mixed EN / KO, asides to someone nearby, thanks against goodbye,
repeated questions, answers to Lumi's own questions): `tests/dialogues_prag_en.py` (114 dialogues, 365 turns),
`tests/dialogues_prag_ko.py` (119, 392), run with `tests/dialogue_check.py --pragmatics`; `tests/followup_cases_more.py`
(286 routing cases after seeing / clothes / object answers, lookups and the weather, in `tests/test_followup.py`).

Failure kinds found: (1) seeing follow-ups about the thing just seen ("where is it?", "무슨 색이야?", "몇 개야?") and
clothes fragments with words around the noun ("jeans too?", "and below?", "바지 color는?", "청바진?") fell to the LLM;
the thread outlived a goodbye or a turn between; "루미는 무슨 옷 입었어?" described the visitor; (2) words said to
someone else ("Hey Jake, come see this", "민수야 이리 와 봐", "Okay kids, say thank you") moved Lumi or ended the talk;
(3) "Yes." / "몰라" after Lumi's question called unclear; "해 봐" after "손 흔들 줄 알아?" and "doing it again" after a
wave did nothing, while "손 흔들 줄 알아?" itself waved (the history also kept the model's "wave" instead of what was
done); (4) 26b now and then writes the bare action word ("none", "search") without "ACTION:": the word was spoken
("search I'll look that up"); (5) fragments and subject-less questions read as about Lumi or a price ("얼마?" after the
investment, "how heavy can it lift?" after TUSK, "Which one?" after "my language model is local"); (6) thanks-only
("Lovely, thanks!", "고마워요~", "감사요") ended the talk, "Cheers, that's everything." did not; (7) reactions after a
lookup ("wow, that many?", "I didn't know that") and "what time is it?" after the weather were searched.

| set | before (HEAD of 2026-10-21 evening) | after |
|---|---|---|
| pragmatics, every 3rd dialogue (78 dialogues, 255 turns) | 230 turns, 58 dialogues | **247 turns, 70 dialogues** |
| follow-up routing (`test_followup.py`, 233 + 286 new) | 233/233 + 212/286 | **519/519** |
| dialogue subset (80 dialogues; a closing "Thanks." now counts as the end, lumi ends after the silence) | 341/343, 78/80 (2026-10-20) | **340/344, 76/80** (left: "Which algorithm?", "What about your cameras?" after wiping, "Photo? With you? Ok?" once unclear, one judge call on feelings) |
| company | 365/368 + 60/62 | **365/368 + 60/62** |
| conversation (all right / route right) | 1219 / 1230 (2026-10-20); 1204 / 1222 with yesterday's code on today's cases | 1203 / 1218 (the misses left: missions and fetch wordings, "look at the floor", place refusals worded without "map") |

Changes: `brain.to_someone_else` (in `intent`, `_action`, `lumi.says_goodbye`); a bare action word on the first line
is the action line; the history keeps the action done; `DO_IT` / `AGAIN` in `Brain._after`; `ABILITY_Q` "줄 알아";
`has_meaning` takes yes / no / maybe / 글쎄요 / 몰라; `Brain._fragment_hint` (a fragment of up to `FRAGMENT_WORDS`
words gets the last answer's first sentence); lookups: `REACTION`, `NOW_Q`, a company word no longer blocks a lookup
follow-up ("who's the CEO?" after Samsung); haha / ㅋㅋ / ㅇㅋ back-channels; umbrella / 우산 only as a question; more
offers dropped (`HELP_OFFER`: "궁금한 게 더 있으시면…", "feel free to ask"); SYSTEM: same-property ellipsis, they / 걔 /
거기, subject-less questions, turned-back questions on any topic, Korean endings, yes / no answers, asides, teasing,
ability against request, 반말 asked for. `seeing`: `_it_answer`, `TAIL`, `WHERE_ON_ME`, socks / bottoms / genes,
"not X, Y" / "X 말고 Y", glasses / hat after clothes, `BYE`, `ABOUT_LUMI`, "오른쪽쪽" fixed. `lumi`: cheers / "that's
everything" end, thanks-only waits (`THANKS_REST`). `talk_examples`: turned_back, aside, answer, hint_tease.
`tests/dialogue_check.py`: `--pragmatics`, a closing expected as the end passes as "chat".

Left: "And charging?" after the battery answers how it charges (the charging time is unknown); "Ha, you got the
reference?" (a film joke) misread; "오 노래?" starts a song; "루미야 너 월급 받아?" is a receive (RECEIVE_ASK 받,
commands agent); praise compared to a grandchild taken without modesty; "Which algorithm?" after an invented "learning
from demonstration" claim; "What about your cameras?" after "can I wipe you with a wet cloth?" answers about the
cameras, not wiping them; the cooking robot's places ("Where is it used?") not found in the notes; command_check's
seeing guess counts "how far is the stage?" as seeing (5 cases; `seeing.answer` itself says None).

## Leftovers of web answers and context, closings by context (2026-10-22, conversation / web agent)

| check | before | after |
|---|---|---|
| web leftovers (`tests/web_check.py` dialogues, targeted) | CEO of OpenAI talk / searched by chance, "How many people live there?" not sure, 리플 "don't know", "몇 살이야?" without the name, Jeju → Seoul rain, ticket refused | all routed right (rules; Ottawa / Canberra population, 리플 1,807원, 샘 올트먼 41, Jeju 100 % rain tomorrow, 경복궁 입장료 3,000원); English opening hours / Lotte World and Louvre tickets are still not on the free pages |
| follow-up routing (`tests/test_followup.py`) | 519 | **551 / 551** (32 new) |
| closings in context, blind set `tests/closing_cases.py` (69) | 62 / 69 | **69 / 69** |
| ... second blind set written after the change (30) | 29 / 30 | **30 / 30** |
| pragmatics, full set (233 dialogues, 757 turns; 239 / 769 with 6 new) | 722 / 757 turns, 199 / 233 dialogues | 730 / 769, 205 / 239 (code of b435e56); the 34 failed dialogues again with the later fixes: 77 / 108 turns (was 69) |
| `command_check --cached` | 0 wrong | 0 wrong (9 missed, none from this work) |

Closings (owner's principle: understood by context, not by phrase lists): `lumi.talk_fate` "end" only for goodbyes
in any context (`CLEAR_BYE`, `RELEASE`: bye, see you, I have to go, 수고하세요, 안녕히 계세요, you can go);
okay / thanks / that's it / 됐어요 / 오케이 땡큐 are "close": the LLM reads them with the turns before. Its end stands
when its words take leave (`lumi.kept_goodbye`); "You're welcome." keeps the talk open and 8 s of silence ends it.
`brain._action` no longer drops a model end for want of farewell words (only a question is no goodbye). Cost: these
words now wait for the LLM (~2 s live; 5.5 s median in the checks with the GPU shared) instead of an instant
"You're welcome." / silent wait; 59 of the 69 cases asked the LLM (40 before).

Lookups: `INTENTS` search (office holders not Cutshion's, coin prices, population), `Brain.search_query` (Korean
names `KO_NAME`, "there" after a talk answer `NAMED_BEFORE` / `CAP_WORD`, a nameless short question after a lookup),
`Brain.weather_place`, `Brain.lookup_about` + `lumi.lookup_refused` (a follow-up of a lookup is not a venue
question; Cutshion never online), `NONE_LINE` / `LOOKUP_PEEK` / `SPOKEN_TARGET` ("search ..." without ACTION).
Conversation: `SING_ECHO` / `SONG_TALK` ("오 노래?", "노래 좋아해?"), `SAME_ABOUT` / `KO_SAME_ABOUT` hint ("What about
your cameras?", "카메라는요?"), talk examples (the film reference, charging, cameras, "Okay."), knowledge: the
learning algorithm is not known, "thank you 해" is an aside, "I wonder if it's going to rain" is the weather.

Left: "Okay." after an answer still gets "You're welcome." now and then (45, 58); "이제 됐어" right after a song ends
the talk (audio/sing STOP has no 됐어); "Lumi, ask me if I want to hear a song" sings (`sing.SING` "want to hear a
song"); "Is Seoul nice?" / "Even for the weather?" looked up; "How long on a charge?" read as the charging time in
the last rerun (example fixed after it, 9b7abdb, not re-run); fragments over 4 words ("How much does it weigh?" after
the arm). Commands agent: "say hi with your arm" (no wave), "move your hand a little for me" (arm reach). The
dialogue subset and company checks were stopped for the owner's live test: tonight's big run.

## Big night test (2026-10-22, from 18:40)

Owner's goal: Lumi understands anyone (EN, KO, mixed, Konglish, whisper slips), fast and exact, and never makes
anything up. Three layers: rules only for one-meaning and safety words (stop, 멈춰, clear goodbyes); an **example
bank** matched by meaning with the embedding server (thousands of wordings per capability, places as a `<place>`
slot, guards first: negation, condition / later, ability questions, words to someone else, two-meaning closings;
motions need a high match, 0 wrong motions); the **LLM** reads the rest from the conversation. `assistant/song_bank.py`
is the prototype.

Tests: a writer that never sees the code writes new sets per capability; each set is split into **train** (fixed
from) and **held-out** (only scored, never read by the fixers). Fake maps with other marker names ("booth A",
"커피 코너", Korean names, numbers) so nothing depends on p1–p10. The old ~4000 cases stay as regression checks.

Added by the owner (live faults, 2026-10-22):
1. **What Lumi sees must be now.** Shirt colour said "blue", owner: "is it really blue?" → silence, then blue
   again; "it's white" → "sorry, white", later wrong again. Watch in the left hand → "left"; moved to the right,
   "and now?" not understood, then "left" again; "it's in the right" → "yes, right". A phone moved to the other
   hand, "what about now?" → the old hand. Every seeing answer, follow-up ("now?", "really?", "are you sure?",
   "look again") and correction is answered from a fresh look, never from what was said before; a correction is
   checked against the camera, not just agreed with. Find why the data is late (cached frames / facts, the LLM
   repeating its history).
2. **Follow-up questions about Lumi's own answer.** "Why?", "when?", "where?", "how?", "what?", "really?",
   "왜?", "진짜?", "어떻게?" right after an answer go on from it: "I can't go there" → "why?" → the reason;
   "it's white" → "really white?" → "yes, white" (after a fresh look). Answer the question that was asked, no
   hesitation, no topic change. Long dialogues (8–20 turns) of every kind, hundreds, EN + KO + mixed.
3. **Never make anything up.** "How many people work at that company?" was answered with the people in the camera.
   Company / Lumi questions without a known fact: "I don't have exact information about that." Say what is known,
   say plainly what is not.
4. **Hearing**: more work on speech-to-text and reading what was heard, hundreds of new tests (real voice paths,
   EN / KO / mixed, noise, cut-off starts, accents), whatever helps.

5. **Lumi never speaks by itself without a reason.** A goodbye ("Nice chatting with you!") came with nobody
   there and nothing said (18:27, after a Command-box mission). Fixed for the silent end (f3b016c: only after
   something was said and with someone near); the agents look for every other unprompted line (prompts, greetings
   to nobody, echoes of its own voice, noise heard as speech) and test it.

6. **Blocked way** (owner 19:05): after "I can't find a way / something is blocking", "find a way", "try again",
   "go around", "go back", "다른 길로 가 봐", "다시 해 봐", "돌아가" are done (retry, back up and retry, another
   approach, back to the trip's start). `robot/nav_guard.py` is off (`ENABLED` False, afe3c51): it stopped drives
   near the docks and in narrow places; the base's own footprint was never changed.
7. **Overnight to 09:20 2026-10-23** (owner): round after round until morning: more blind cases each round
   (hundreds of ways per command, r2, r3 ...), fixers on the train halves, held-out scored only by the lead,
   reply speed measured with every round. Ready by 09:20: numbers, commits, Gitea push, this file updated.

Agents (none moves the robot or restarts a service; each owns its files; results to logs/ and below):
writer (blind sets, train / held-out), bank (`assistant/intent_bank.py`, the bank step in `lumi.route`),
seeing (`assistant/seeing.py`, freshness, corrections), conversation (`assistant/brain.py` prompt, follow-ups,
unknowns, examples, knowledge), hearing (`audio/ears.py`, `audio/mic.py`, `assistant/wording.py`,
`assistant/voice_words.py`), maps (fake maps, place reading in `assistant/steps.py`).

### Hearing, second night (2026-10-22 night, hearing agent)

What went wrong live (lumi.log / lumi_console.log 2026-10-21 and 10-22, every "visitor" / "no wake word" line judged
against the turns around it; `tests/asr_live.py` keeps them: 150 heard texts with what was said, and the last 50
real clips in `logs/asr_real/1022/` with labels, local only):
- The owner's English: "Look at the big side" (back side; already read right), "Let's count to p5", "Let's copy 10
  point", "Let's go pick five point", "Let's fall lonely" / "Let's fall of Him" (follow me), "Lumi stopped", "What is
  it / that / the hand of my hand?" (what is in my hand), Kuching / Kuchung / Kutsche company (Cutshion), and
  "How old are you?" written as 호월달요 / 호화 다리 / Powa tari / Hovalt arıyor: 8 times, never heard right.
- English tagged Korean in Latin letters ("Wait.", "What is it?", "Can you sing song?", "You got it."):
  understood() refused it, Lumi said "say it again".
- Noise: a sound whisper took for Japanese "はい" became "감사합니다." when made Korean (18:39, five times);
  "Looney." for a real "Lumi" dropped the wake word (18:35:10).
- "It's bringing your insulin to the hand." (18:25) was Lumi's own "Please bring it near its look pose by hand."
  through the clip mic. Not fixable from the text: Lumi's words and visitors' words overlap the same (word or
  letter match, 47 own-voice catches against 116 accepted barge-ins). Needs the played audio as an echo reference
  (`audio/mouth.py` keeping what it plays, compared with the clip-mic sound): not done.

Changes (`audio/ears.py`, `audio/mic.py`, `assistant/wording.py`; checks `tests/asr_live.py`, `tests/asr_early.py`,
`tests/test_ears.py`, `tests/asr_check.py --cases <file> / --trim`, `tests/voice_check.py --port / --tag`):
- Slips after recognition: ears `SLIPS` (stop, hand, Cutshion, how old are you; the text Korean-tagged becomes
  English), wording `ASR_SLIPS` (count to p, copy / pick N point, fall lonely). Only phonetic forms seen live.
- Korean-tagged text in Latin letters is asked once in English; the same words again (`SAME_WORDS` 0.8) are taken
  as English. Also asking Korean was tried: far Korean came back as other Korean words (6 right of 37), left out.
- A sound taken for another language: the stock words a forced language writes for it (`STOCK`: 감사합니다, thank
  you, hey, hi, bye; not 네 / yes, answers to Lumi) are dropped. Whisper repeating a phrase three times (`REPEAT`) is dropped ("Look right." x3
  for "dock2로 가서 충전해" became a chain of head turns).
- `lumi_like` takes "Looney"; `CUT_OFF` also waits for the rest after whisper's own trailing "...", "," or "of",
  "at", "about" (17 such turns live, none a whole sentence).
- **Early transcription**: `mic.Segmenter.quiet_now()` after `EARLY_QUIET_S` 0.3 s of quiet inside an utterance
  (0.4–4 s long); `ears.early()` runs whisper on it in the background; `transcribe()` takes that result when the
  utterance ended with only the quiet after it (any listener: talk turns, the wake word, barge-in). A run replaced
  by a newer pause or passed over is skipped if not started.
- Tried and left out: the map's marker names in the prompt (blind train set: +2 of 82 fake-map cases, −5 of the
  others, 4 more far wake words lost; `ears.set_names` stays as a no-op for `tests/blind_check.py`).

| Check | Before | After |
|---|---|---|
| `asr_live.py` live texts read as said | 125 of 142 | 141 |
| `asr_live.py --real` (50 real clips, 44 judged) | 42 | 44 |
| blind r1 train (238 x near / far) | 283 of 476, 21 "say it again" | 290, 5 |
| blind r2 train (325 x 2) | 420 of 650, 26 | 422, 10 |
| blind r3 train (293 x 2) | 370 of 586, 7 | 375, 1 |
| blind r2 speed_short (197 short ones x 2) | 235 of 394, 18 | 237, 9 |
| `voice_check.py 300` (Lumi's voice, mission texts) | 269 of 300 | 275 |
| set 3 (noise, people not talking to Lumi) | 95 of 96 | 96 |
| set 4 (music, speech over music) | 92 of 128 | 94 |
| End of speech → text (`asr_early.py`, real clips in real time) | median 1.14 s, mean 1.12 | 0.83 s, 0.89 (49 of 50 the same text) |

Two runs of the same code differ by ~4 cases (whisper falls back to sampling on unclear audio); a case whose heard
text is the same in both runs but whose verdict changed is another agent's routing change. No former "say it again"
became a wrong motion. Live test needed: the owner's "How old are you?", "Wait.", "What is in my hand?", a call of
"Lumi" from 2–3 m, and the reply time after short commands (logs: `early` in last_stt).

### Conversation: follow-ups, unknowns, no unprompted lines (2026-10-22 night, conversation agent)

- **Follow-ups on Lumi's own answer** ("why?", "how do you know?", "really?", "fr?", "wai?", "왜요?", "진짜?", "레알?",
  "어떻게 알아?"): a line said by code (Greeter only, arm off, place not on the map, busy, nothing held, a refused lookup,
  status) now goes into the talk like the model's answers (`Lumi.answer` wraps `_answer`, `lumi.keep_said` with what
  `mouth.recent_speech` played in that turn), so "why?" has the reason. The prompt's follow-up rule (reason / source /
  "Yes, ..." with the fact again, never "say it again"), `brain.ABOUT_ANSWER` adds a hint naming the answer asked
  about and lets an "unclear" there be asked once more. Seeing follow-ups still go to `seeing.py` first (routing
  checked: no rule takes "why?", "진짜?", "and now?").
- **Unknowns**: "I don't have exact information about that." / "그건 정확한 정보가 없어요.", at most one related fact
  with no number that could pass for the answer (buying: the phone / email), no guess on "roughly?"; never a colour or
  thing not seen; "how many people work there / made you / came today / 만든 사람" never from the camera
  (`seeing.NOT_IN_VIEW`); knowledge: the next exhibition is not known (index rebuilt).
- **No unprompted lines** (logs 2026-10-22): no "How can I help you?" after silence (`MAX_PROMPTS` 0, twice live);
  no goodbye after a closing word when nobody is near or while following (17:41, 12:10); coughs ("크흠", "ahem",
  "콜록", "에취") are noise. Music captions, "-끝-" were fixed by the hearing agent (VAD, `NOT_SAID`). "루미 안녕!" before
  anything was said is hello, not goodbye (`lumi.HI_ANNYEONG` in `route`).

| Check | Before | After |
|---|---|---|
| own follow-up dialogues (`tests/followup_check.py`, 66 dialogues / 595 turns; every 3rd: 22 / 182) | - | 173 / 182, failed ones rerun after fixes: 176 (2 of the rest are harness-only: `rules_route` has no `route`) |
| blind r1 unknowns (`--unknowns 2`, 76) | - | 73, after fixes 76 / 76 |
| blind r1 follow-ups (`--blind 6`, 28 dialogues / 142 scored) | - | 124 / 142; the 14 failed dialogues rerun after the fixes: 128 / 142 |
| blind r3 follow-ups (`blind_check.py ... --round r3 --limit 25`, 149) | - | 122 / 149 (before "fr?" / "wai?" / confirm fixes) |
| blind r3 unknowns (first 25) | - | 25 / 25 |
| silence / noise, text path (`tests/silence_check.py`; r1 88, r2 178 "nothing" cases) | 87 / 88 | 88 / 88, r2 178 / 178 |
| unknowns routed to the camera (r1 152, r2 239) | 2, 1 | 0, 0 |
| `company_check` | 362 / 368 + 60 / 62 (2026-10-20) | 364 / 368 + 59 / 62 (2 of the 3 are lookups, not made by the harness) |
| `closing_check` | 65 / 69 | 65 / 69, last run 66 / 69 (first sentence median 1.2 s with the GPU free; 8-15 s while other agents' checks ran) |
| `test_followup.py` routing | 551 / 551 | 551 / 551 |

Left: the facts in knowledge the model does not use in a short follow-up (position "to within about 5 cm", "at most
3 m", the held thing could fall), song titles counted as a "Korean reply"; "can you get taller?" lifts (rules,
ability question); "왜 손은 안 되고 노래는 돼?" sings (`sing.asked`); Lumi's own voice taken as a barge-in with other
words ("The plant develops and supplies..." for "Cutshion develops and supplies...", 4 times on 2026-10-22): a
letter-overlap test caught them but also real questions, not done (needs the echo reference, hearing notes).

### Hearing, round 2 (2026-10-23 night, hearing agent)

Lumi's own voice through the clip mic ("It's bringing your insulin to the hand." was Lumi's "Please bring it near its
look pose by hand.", 18:25; "It's still empty." for "Your right hand is still empty." interrupted Lumi, 18:49):
`audio/mouth.py` keeps what the speaker played (16 kHz, `ECHO_KEEP_S` 30 s, cut short when a sentence is stopped);
`mouth.own_voice(u)` compares a clip-mic utterance with what played at the same time (`echo()`: correlation of the two
log-spectrograms, 16 bands, the mic's frames within 15 dB of its loudest, lags −0.3…1.0 s) and drops it at
`ECHO_MIN` 0.6. A visitor saying Lumi's words after Lumi stopped has nothing played to match (not judged); a visitor
talking over Lumi is dominated by their own voice at their clip mic. `lumi.py` drops it in `barge_in`, `song_abort`
(before whisper) and `talk_turn`, logged as "ignored own voice (sound match 0.xx)"; interruptions log their match too.
The word-overlap rule (`own_echo`) stays as it was. `tests/echo_check.py`: made cases (Lumi's TTS through a room,
0-0.8 s late, a part of a sentence) 0.67 and more; a visitor (other voices, also saying Lumi's words) with Lumi 12-20 dB
lower 0.39 at most; the owner's real clips against Lumi's lines at any time reach 0.6 in 1.8 % of placements. The four
real own-voice clips score 0.16-0.5 against Lumi's lines made again (the TTS samples differ each time: a made line
against itself made again drops from 0.8 to 0.4-0.6), so the real level is not known: **live test needed**.

Short commands and marker names (`tests/asr_check.py --cases 5`, new: 239 cases x near / far: 116 short commands, 44
numbers with units, 79 marker names on the office, conference, korean, expo and hall maps, EN / KO / mixed; `--memo`
keeps every whisper answer in logs/asr_check/memo.jsonl so a re-run asks only new questions). Fixed in
`wording.ASR_SLIPS` / `KO_SPOKEN`: "커피 바로" / "커피바" = Coffee_Bar on a map that has it ("bar": 바 inside a longer
name), "30센트" before a direction = 30센티, "boot (number) 12" = booth 12, "go / move write", "turn rate" = right,
"drive to .8" = point 8, "mean stage" = main stage, "1m 50cm" = 1.5 m.

| Set (train) | Before | After |
|---|---|---|
| blind r3 hearing (293 x 2) | 374 of 586, 20 wrong motions | 395, 16 |
| set 5 (239 x 2) | 263 of 478 | 268 |
| blind r1 / r2 hearing | 290 of 476 / 422 of 650 (round 1) | 290 / 415: the same heard texts, the 7 are routing changes of commit 7caf94f |
| blind r2 / r3 speed_short | 238 of 394 / 156 of 306 | the same |
| set 3 (noise, people not talking to Lumi) | 96 of 96 | 96 |
| `asr_live.py` live texts | 141 of 142 | 141 |
| `voice_check.py 300` | 275 of 300 | 279 |

Tried and left out (each measured on the r2 speed_short set, 394; noise sets checked where it mattered):
- The conversation's language for short clips (speech < 1.2 s in another language than the last clear utterance asked
  again in that language, bonus 0.3 / 5): +1 / +2; forced Korean on far short words came back as other Korean words.
- Snapping a short Korean reading to the nearest command by letters (jamo, "정기." -> 정지): +4 to +11 on the short
  sets, but on 6440 Korean texts from the test files it changed real words into motions ("가 봐" -> 나 봐, "피십으로 가"
  -> 집으로 가, "천천히 해" -> 천천히 가, "송편" -> 손 펴). Never a guess into a command: left out.
- No temperature fallback (`temperature_inc` 0): the same right on short2 / r3, set 5 −4; fewer wrong talk, more
  "say it again". Beam 5: −2, slower.
- VAD padding / a minimum length: a clip-mic utterance always holds 0.3 s before and 0.6 s quiet after the speech, and
  none of the failures was a clip too short for whisper.

Still weak: short Korean commands far away with people talking (r2 short: KO far 24 of 90), "루미야 + a short
command" where whisper writes only "루미야." (then the wake word works and the visitor says it again), mixed
sentences cut at the language change ("Booth A. Rulga Jua."). The TTS voices are not the owner's accent.

## Now: midday 2026-10-23 (written 11:15 by the lead session)

Goal: a live voice test at 13:00 (owner says move / turn / look / lift / go commands in EN and KO, then give while
holding). Code freeze 12:45: the lead runs all tests/test_*.py, commits what passes, then the owner restarts
`lumi-api` (`systemctl --user restart lumi-api`, base idle). Six agents of the lead session, each reports by 12:40:

| agent | job | files it edits |
|---|---|---|
| LLM action gate | a motion chosen by the LLM runs only if the words are a direct order (plans, negations, conditions, remarks -> words only) | brain.py `_action`, lumi.py `act` / answer action handling |
| Korean numbers | 사십오 / 마흔다섯 / 사 십오 도, 1.5미터, 반 미터, 레프트 = left, a number without a unit = ask | brain.py `_norm`, wording.py norm, driving.py, steps.py, chain.py, intent_bank said_amount; new tests/test_korean_numbers.py |
| Hearing numbers | whisper slips of numbers / units ("1.m가"), short Korean commands far away | wording.py (own function), audio/ears.py, tests/asr_* |
| Give while holding | give 55 % -> better; reach, put back / 원위치, drop it here | fetch_dialog.py, lumi `fetch_voice`, brain hand rules, api/server.py parse |
| Bank + quick answers | many more command wordings; NEW assistant/quick_answers.py: frequent standalone questions answered at once from knowledge facts (follow-ups always to the LLM) | intent_bank.py, quick_answers.py (new), one block in lumi.route |
| LLM prompt / examples | explanations and examples for the LLM: commands vs talk, amounts, give, exact answers, follow-ups | brain.py SYSTEM / ACTIONS_STREAM, talk_examples.py, company_examples.py, knowledge/ |

Order of understanding (owner's plan): rules -> bank -> quick answers -> LLM. Tonight: another big training run
(more banks, examples, blind sets). Never fix from tests/blind/r5 (final exam) — write a round 6.

## Big night test: results (2026-10-22 18:40 – 2026-10-23 07:45)

Final exam = round 5 (`tests/blind/r5/held/`, 2992 cases / scored turns, written blind at 04:10, seen by no fixer,
scored once at 06:00–07:45 on the frozen code e32e0bb, with gemma4:26b): **2414 right (80 %), 56 unasked or wrong
motions (1.9 %)**. Report: `logs/final_r5_all.md` (rules-only: `logs/final_r5_rules.md`).

| set (r5, with the LLM) | right | motion |
|---|---|---|
| 19 command sets (1140) | 945 (83 %) | 30 |
| best: take 93, wave 91, look / lift / bring / follow / stop 90, go / move / missions 88 % | | |
| weakest: give 55, speed_short 61 (the LLM answered where a fast answer was wanted), reach / put 76 % | | |
| seeing dialogues (632 turns) | 456 (72 %) | 4 |
| follow-up dialogues (416) | 376 (90 %) | 5 |
| mixed dialogues (404) | 336 (83 %) | 7 |
| unknowns (100) | 77 (most misses: airport facts sent to a web lookup the harness has no answer for) | 1 |
| silence / noise (60) | 59 | 0 |
| hearing (120 x near / far) | 165 / 240 (68 %) | 9 |

How the night went: rounds r1–r3 of blind sets (train / held-out halves) and fixers; r1–r3 held-out reached ~5
motions, but a fresh round 4 showed 74 motions / 49 % rules-only: the blacklist guards had fitted the old sets.
Rules were then changed to act only on a positive **direct order** check (`brain.direct_order`, per clause, EN / KO /
mixed request forms), every path gated (route, hand reader, Command box, detour, chain, bank): r4 held motions
74 → 29 → 10. The lead leaked held examples into briefs twice (r3, r4), so the clean number is r5's.

Done tonight (all committed on main, all 46 tests/test_*.py pass): arm-off messages and drives without an enabled
arm (ea4badf); "look behind" stays 60 s (8fb683a); no goodbye into an empty room (f3b016c); nav guard off (afe3c51);
seeing from a fresh look, corrections checked against the camera (2e68d0c + b3028ec); blocked-way commands
(assistant/detour.py); any map names; intent bank fast lane (assistant/intent_bank.py, ~20–30 ms, 0 wrong on train);
direct-order rules; hearing: early transcription (end of speech → text 1.14 → 0.83 s), live slips, own voice in the
clip mic (audio/mouth.py echo); conversation: refusals kept for "why?", unknowns never made up, no silence prompts,
do it again, look at me = the voice. First sentence on a quiet GPU ~1.7 s median.

Next (from the r5 misses; never fix from r5 itself — write a round 6):
1. The LLM still picks motions for remarks / plans the rules leave to it ("우리 X 들렀다가 Y 가자" -> go, "Don't
   look up." -> look down, conditions "점심 먹고 나서 …"): check the LLM's action against `direct_order` too.
2. Korean number words for degrees and distances ("마흔다섯 도", "사 십오 도", "다섯만") and "Korean-English" words
   (레프트 = left, not lift).
3. Give while holding (55 %), reach ("extend your arm in my direction" -> fold), put back / 원위치.
4. Seeing dialogues 72 % on r5 (training sets were 93–96 %): read logs/final_r5_all.md seeing rows by class.
5. Hearing far Korean short commands; "1.5미터" heard "1.m".
6. Live tests for everything above (ROADMAP Next).

## Next (in order)

0. Re-runs started 2026-10-16 ~19:55 with all fixes (`logs/recheck_all.log`): conversation_check, company_check,
   dialogue_check subset. Read the three logs/*.md, fix what still fails.

1. Apply the agents' fixes above; re-run `tests/test_steps.py`, `tests/test_fetch.py`, `tests/test_fetch_intents.py`,
   `tests/test_intents.py`, `tests/test_mission_talk.py`, `tests/interrupt_check.py`, then the LLM checks
   (conversation, company, dialogues) until they pass; rebuild the knowledge index
   (`.venv/bin/python assistant/knowledge.py build`).
2. Restart `lumi-api` (owner's go-ahead; check `curl -s localhost:8100/status` base.move_status is not running) so
   the new code, prompt and index are used.
3. Live, owner at the STOP (ROADMAP Next 0a): mission from the Command dialog ("take the cup, go forward 0.5 m, then
   right 1 m and put it on the table"), then by voice when the microphone and speaker are back; receive (hand held
   out, closes on "okay"); "bring it to James at p6" with James meeting it on the way; a stranger's redirect refused.
4. Voice with the real microphone: Korean marker names, "1미터"; tune `MOVE_SPEED`, `RECEIVE_DI_S`.
5. Owner to give: Cutshion facts the site does not have (team / developers, founding, anything to say at the
   conference); whether "cancel the mission" by voice should be allowed for the person who started it.
6. Later: measure where a handed-over cup sits in the fingers (so it can be put down); a message added on change
   ("tell Tom happy birthday when you give it"); keep the sender's place ("take it back to Anvar").

## 2026-10-19 robot work (head camera, gripper, base)

Not part of this plan; written up in ROADMAP (log 2026-10-19, Next 0–0c), docs/06 §3 and docs/15 §8–9 (head camera
calibration, `vision/head_cam.py`, measure-axis −95.5° at waist −20.3°, grip widths, picks), docs/16 (head search,
`head_hits`, waist correction), docs/10 and `docs/gripper/`. Not live until `lumi-api` is restarted.

## Files changed in this work (for the Mac sync, "yangila")

assistant/steps.py (new), assistant/talk_examples.py (new), assistant/interrupt_examples.py (new),
assistant/company_examples.py (new, agent), assistant/brain.py, assistant/lumi.py, assistant/fetch_dialog.py,
assistant/knowledge.py, assistant/web.py, tasks/fetch.py, api/server.py, api/dashboard.html,
knowledge/lumi_about_en.md, knowledge/cutshion_en.md (new, agent),
tests/test_steps.py, tests/steps_cases*.py (new), tests/test_fetch.py, tests/test_fetch_intents.py,
tests/test_mission_talk.py (new), tests/interrupt_cases.py (new), tests/interrupt_check.py (new),
tests/voice_check.py (new), tests/llm_bench.py, tests/status_cases.py, tests/conversation_cases.py,
tests/conversation_check.py, tests/dialogues.py, tests/dialogue_check.py, tests/company_cases.py,
tests/company_check.py (new, agents), assistant/company_examples.py, tests/conversation_cases_more.py, tests/company_cases_more.py, tests/dialogues_more_a.py, tests/dialogues_more_b.py (new, agents), tests/company_check.py, docs/14, docs/17_MISSIONS.md (new), docs/WORK_PLAN.md (this), docs/14, docs/TUNING.md,
docs/ROADMAP.md, README.md, CLAUDE.md, assistant/wording.py (new), tests/steps_cases5.py (new), tests/test_places.py (new), tests/steps_cases6.py (new), tests/test_fetch_wait.py (new),
tests/test_mission_wait.py (new), docs/TUNING.md, audio/tts_gpu.py (new), audio/mouth.py, assistant/llm_direct.py, tests/test_mouth.py, tests/command_cases2.py (new), tests/steps_cases7.py (new), tests/test_mission_route.py (new), tests/steps_llm_check.py (new), tests/command_cases3.py (new), tests/steps_cases8.py (new), assistant/driving.py, tests/test_driving.py, tests/command_check.py, tests/command_cases.py, audio/ears.py, assistant/wording.py, tests/asr_check.py, tests/asr_cases.py, tests/asr_cases2.py, tests/asr_cases3.py, tests/test_ears.py (new), README.md, assistant/seeing.py, assistant/talk_examples.py, tests/dialogues_prag_en.py (new), tests/dialogues_prag_ko.py (new), tests/followup_cases_more.py (new), tests/followup_cases.py, tests/dialogue_check.py, docs/14_VOICE_ASSISTANT.md, tests/closing_cases.py (new), tests/closing_check.py (new), tests/test_web.py, tests/web_check.py, tests/web_cases2.py, tests/conversation_check.py, tests/test_fetch_intents.py, tests/test_followup.py, tests/followup_check.py (new), tests/dialogues_followup_en.py (new), tests/dialogues_followup_ko.py (new), tests/silence_check.py (new), tests/test_command_box.py, knowledge/cutshion_en.md, assistant/seeing.py. Not synced: logs/, models (now also `models/ggml-large-v3-turbo.bin`), knowledge/index.npz.
