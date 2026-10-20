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
tests/test_mission_wait.py (new), docs/TUNING.md. Not synced: logs/, models, knowledge/index.npz.
