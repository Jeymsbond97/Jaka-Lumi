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
tests/test_mission_wait.py (new), docs/TUNING.md, audio/tts_gpu.py (new), audio/mouth.py, assistant/llm_direct.py, tests/test_mouth.py, tests/command_cases2.py (new), tests/steps_cases7.py (new), tests/test_mission_route.py (new), tests/steps_llm_check.py (new), tests/command_cases3.py (new), tests/steps_cases8.py (new), assistant/driving.py, tests/test_driving.py, tests/command_check.py, tests/command_cases.py, audio/ears.py, assistant/wording.py, tests/asr_check.py, tests/asr_cases.py, tests/asr_cases2.py, tests/asr_cases3.py, tests/test_ears.py (new), README.md, assistant/seeing.py, assistant/talk_examples.py, tests/dialogues_prag_en.py (new), tests/dialogues_prag_ko.py (new), tests/followup_cases_more.py (new), tests/followup_cases.py, tests/dialogue_check.py, docs/14_VOICE_ASSISTANT.md, tests/closing_cases.py (new), tests/closing_check.py (new), tests/test_web.py, tests/web_check.py, tests/web_cases2.py, tests/conversation_check.py, tests/test_fetch_intents.py, tests/test_followup.py. Not synced: logs/, models (now also `models/ggml-large-v3-turbo.bin`), knowledge/index.npz.
