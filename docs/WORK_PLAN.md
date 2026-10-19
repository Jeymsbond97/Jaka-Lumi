# Work plan: missions, conversation, conference (started 2026-10-16)

The owner takes Lumi to a conference: mostly voice. Goals: any command of several steps (typed in the Command
dialog or spoken) is read right and done; people met on the way are answered and their tasks refused (unless they
are who the task is for); conversation answers exactly what is asked, varied, from facts, English and Korean (Korean
replies always polite); Lumi is presented as developed by Cutshion Company (쿳션), 2 years old.

Update this file when a part is done. A new session: read this, then docs/17_MISSIONS.md, then ROADMAP.

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
greeting" = quiet, "나 이제 집에 가" = goodbye, "손주가" is not 주가, notes FAQ (EN + KO). Round-3 LLM checks started
14:xx (logs/*_run.log, logs/recheck3_done at the end); then `tests/dialogue_check.py --all`.

## Marker names and numbers as said (2026-10-19)

Cause of "피쓰리로 가 줘" / "파이널로 가" answered but not driven: markers were read in two places with different
code (steps `_KO_P`, brain `POINT_KO` / `_norm`), and brain's check of the LLM's place (`named_place`) and its
keyword rule (`go_point`, English only) knew no Korean spellings. Now one reader, `assistant/wording.py`
(`norm` = numbers then markers), used by `brain._norm` (so intent, fetch, `named_place`) and `steps._norm` (so the
mission reader and the LLM check, which now calls `named_place`). It reads p1–p12 said as "p3", "P.3", "p 3",
"point three", "피쓰리", "피스리", "피 삼", "포인트 쓰리", "삼 번 / 3번 / 세 번 포인트", "피3", mixed ("go to 피쓰리",
"point 3에서"); final, dock2, exit, PInit, Wp, home in Korean; whisper forms (piece 6, 피트로 = p2, PO = p5, 도크트로,
Docky2); numbers: 일 / 한 미터, 영점오, 오십 센치, 1미터 50센치, 일 미터 반, point five meters, 사십오 도, "05 meters".
Not clearly a marker ("피로", "PE로", "피자", "피오나", "이번에", "팔도") stays unread. Also: `go_point` reads
"p3로 가 줘" (only when that is all that is said), "go to dock two" no longer goes home, "go to a meeting room" is not
marker a; steps: "from p3 to p5", "p5 앞에", "까지 / 쪽으로", "final이나 exit", "ask for the bottle", "컵 받아 와",
"p6에 있는 제임스한테 컵 갖다줘", "컵 take해서", "turn left 하고", "go home and charge", "충전하러 가"; a lone
"go back" is unread (back where? or backwards?).
Tests: `tests/steps_cases5.py` written blind by an agent (549 cases, 41 % Korean, 24 % mixed, 84 must be refused;
136 keyword-rule cases), `tests/test_places.py` (normaliser, intents, named_place). test_steps 1707/1707 (new cases
1664/1701 with the first version of the reader), test_places 136/136, test_fetch, test_fetch_intents, test_intents,
test_mission_talk ok, interrupt_check 288/301 (as before). voice_check now says Korean markers and numbers the way
people do ("피쓰리로", "피삼으로", "일 미터"; Lumi's TTS reads "p3" / "1미터" in Korean badly) and includes the new
cases: 889/1065 (old cases 538/600, was 440/600; new 351/465). Runs differ by ~10 (the TTS is not repeatable). What
still fails: mixed-language sentences (the TTS speaks one language per sentence), whisper's guesses that are not one
marker ("피사로" heard for p3 and p4, "PE" for p1 and p2, "픽으로" for p9, "PeeFree"), "2m" heard for "1미터" spoken
by the TTS as digits. Files: assistant/wording.py (new), assistant/steps.py, assistant/brain.py (marker code only),
tests/steps_cases5.py (new), tests/test_places.py (new), tests/test_steps.py, tests/voice_check.py, docs/14, docs/17.

## Wait steps in missions (2026-10-19)

Missions read and run waits (docs/17 §1, §2.4, §4): stay ("go to p3 and stay there", "p3에 가서 기다려": the mission
ends there, status `waiting`; in the middle, "go to the exit, wait there, then go home", it waits for "go on"), a time
("wait 30 seconds then go to p5", "p3에서 5분 기다렸다가 p1로 가", "잠깐 기다렸다가" = `WAIT_SHORT_S` 10 s, over
`WAIT_MAX_S` 30 min refused, "a while" / "몇 분" unread), until someone gives it (receive with `wait_s`, `WAIT_GIVE_S`
5 min, nobody: fails there, hand open), an instruction from the person at the place ("do what they tell you", "거기
있는 사람이 시키는 거 해": one command, read back, spoken yes, checked with the rest; `WAIT_ORDER_S` 5 min, nobody: the
rest of the mission). Times: `wording.durations` (mission reader only). Status answers say where, for what, how long.
"Go on" ends any wait (`fetch.proceed`); "okay" / "thank you" while receiving / giving on a mission now reach the
hand even when nobody spoke to Lumi before (they were ignored as "not to me"). Lone waits ("wait here", "hold on a
second", "can you wait?") are not a task. Changed expectations: "wait for someone to give you the cup" is now a
receive with the long wait (4 cases), "go to the exit, wait there, then go home" reads.
Tests: `tests/steps_cases6.py` (blind, 329), test_steps 1707 -> 2035 / 2035, `tests/test_fetch_wait.py` (runner, fakes
only), `tests/test_mission_wait.py` (lumi hooks, status), test_fetch, test_places, test_fetch_intents, test_intents,
test_mission_talk ok, interrupt_check 288 / 301 (as before). Not live yet. No dashboard "go on" button (voice or Stop).

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

## Files changed in this work (for the Mac sync, "yangila")

assistant/steps.py (new), assistant/talk_examples.py (new), assistant/interrupt_examples.py (new),
assistant/company_examples.py (new, agent), assistant/brain.py, assistant/lumi.py, assistant/fetch_dialog.py,
assistant/knowledge.py, assistant/web.py, tasks/fetch.py, api/server.py, api/dashboard.html,
knowledge/lumi_about_en.md, knowledge/cutshion_en.md (new, agent),
tests/test_steps.py, tests/steps_cases*.py (new), tests/test_fetch.py, tests/test_fetch_intents.py,
tests/test_mission_talk.py (new), tests/interrupt_cases.py (new), tests/interrupt_check.py (new),
tests/voice_check.py (new), tests/llm_bench.py, tests/status_cases.py, tests/conversation_cases.py,
tests/conversation_check.py, tests/dialogues.py, tests/dialogue_check.py, tests/company_cases.py,
tests/company_check.py (new, agents), assistant/company_examples.py, tests/conversation_cases_more.py, tests/company_cases_more.py, tests/dialogues_more_a.py, tests/dialogues_more_b.py (new, agents), docs/14, docs/17_MISSIONS.md (new), docs/WORK_PLAN.md (this), docs/14, docs/TUNING.md,
docs/ROADMAP.md, README.md, CLAUDE.md, assistant/wording.py (new), tests/steps_cases5.py (new), tests/test_places.py (new), tests/steps_cases6.py (new), tests/test_fetch_wait.py (new),
tests/test_mission_wait.py (new), docs/TUNING.md. Not synced: logs/, models, knowledge/index.npz.
