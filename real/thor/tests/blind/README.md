# Blind test sets (2026-10-22)

Written without reading the code, from docs/14, docs/16, docs/17, docs/WORK_PLAN.md and knowledge/. Every set is split
at random about 50/50 into `train/` (fixes may be made from these) and `held/` (only scored, never read by whoever
fixes the code). The same file name in both folders has the same format and mix. Fake maps: `maps.py` (`MAPS`:
office, expo, korean, hall); a case naming a place carries `"map"` and `"markers"`, to hand to the reader instead of the
live map. The existing checkers import their case files by name; each needs an option to load these files.

| File | Variable | Format | Read by |
|---|---|---|---|
| `commands_<cap>.py` (go, move, turn, look, lift, wave, reach, give, take, put, bring, follow, stop, status) | `CASES` | tests/command_cases3.py: `{"intent", "text", "lang", "state" (idle / holding), "before" (None or (said, Lumi's action line)), "expect", "map", "markers"}`; expect alternatives split by " \| " (action:&lt;a&gt; [words], mission, receive, give, place, empty_hand, refuse, stop, end, sing, status, seeing, speed, ask, talk). Any listed outcome is right; an unlisted motion is wrong | tests/command_check.py |
| `commands_sing.py` | `CASES` | tests/song_cases_train.py: `(text, want, context)`; context from tests/song_contexts.py (written out); want: sing, sing:&lt;ID&gt;, sing_other, unknown, list, no, stop | tests/song_check.py |
| `commands_missions.py` | `CASES` | dict text → `{"steps": short notation of tests/test_steps.py ("go stage \| wait 10 \| go here", "?" = must stay unread / refused), "map", "markers"}` | tests/test_steps.py (reads `c["steps"]`) |
| `seeing_dialogues.py` | `DIALOGUES` | `{"who", "topic", "lang", "turns"}`; turn `{"say", "scene", "route" (seeing / llm), "expect_action", "must", "must_not", "check"}`. `scene` is what the cameras see at that turn: `{"people": [{"id", "dist_m", "side", "top", "bottom", "left_hand", "right_hand", "hands_visible", "raised"}], "objects": [{"name", "colour", "side", "dist_m"}]}`; side as Lumi sees it, hands are the person's own; "A" is the speaker. must = the fact now, must_not = the stale or wrongly agreed claim | tests/dialogue_check.py turn loop, with a fake scene per turn instead of the cameras |
| `followup_dialogues.py` | `DIALOGUES` | tests/dialogues.py T() fields plus `"reply"` and `"scored"`: a turn with `reply` and scored False is a setup (put the reply into the history as Lumi's, don't generate or score it); scored False without reply = a back-channel, answered but not judged; scored True = must go on from Lumi's last answer (the reason, the fact again), no hesitation or topic change | tests/dialogue_check.py (needs the setup-reply and scored handling) |
| `unknowns.py` | `CASES` | tests/company_cases.py plus `"kind"` (unknown / known), `"ctx"` [(visitor, Lumi)] put into the history first, `"people_in_view"` (the camera count then, which must never be given as an answer). unknown: must a not-sure phrase, must_not made-up numbers; known: must the fact from knowledge/ | like tests/company_check.py |
| `silence_noise.py` | `CASES` | `{"heard" (whisper's text, may be ""), "kind" (music, tv, caption, cough, filler, laugh, others_talking, echo, empty_room), "ctx": {"session" (none / open / just_ended), "lumi_said", "people", "speech_s" (speech the VAD found), "from_lumi_speaker"}, "expect"}`: "nothing" = no words, no motion, no goodbye, greeting or "say it again"; "no_action" = one short line allowed, nothing moves, the talk is not ended | no checker yet (hearing / turn-taking path) |
| `hearing.py` | `CASES` | tests/asr_cases.py: `{"kind", "lang", "text", "say": [(lang, words), ...]}` plus `"map"`, `"markers"` on place cases and `"not"`: texts it must not be heard as (near sounds) | tests/asr_check.py (needs a case-set option) |

## r2 (round 2, 2026-10-22 night)

`r2/train/` and `r2/held/` (split ~50/50 at random per case / dialogue, the same mix in both), written blind like round
1 and de-duplicated against round 1's train texts. Many wordings per command: polite, casual, commanding, indirect,
questions as requests, rambling with fillers, very short; Korean 반말 / 해요체 / 하십시오체 / 주세요 / 줄래; Konglish
and mixed; typos and whisper slips; numbers as words / digits / Korean numbers; hard negatives (negation, condition /
later, ability question, talk about Lumi to someone else, quoting) with no-action expects. Files with a round-1 name
use round 1's format exactly. Load them as `tests.blind.r2.<split>.<name>` (blind_check.load needs the `r2.` prefix).

| File | train / held | New |
|---|---|---|
| `commands_go`, `_move`, `_turn` | 199/199, 173/172, 177/176 | – |
| `commands_look`, `_lift`, `_wave`, `_reach` | 387/387, 241/241, 162/162, 179/178 | – |
| `commands_give`, `_take`, `_put`, `_bring` | 175/174, 156/156, 164/163, 166/166 | – |
| `commands_follow`, `_stop`, `_status` | 160/159, 152/151, 153/152 | – |
| `commands_sing` | 150/150 | – (contexts written out from tests/song_contexts.py) |
| `commands_missions` | 417/416 | – |
| `commands_chain` | 238/238 | NEW set: command format, expect `chain` (or `chain \| mission` when every part is a mission step); field `"parts"`: the parts in the order said, command notation without `action:` ("look me", "wave", "lift up", "go_to stage", "pick cup", "put down", "give", "turn left 90", "come", "follow" only last), questions as `ask:<topic>` (time, weather, date, battery, name, company, what_see, age). Near misses have no `parts` ("turn around and look" = `action:look`, "come here, I need help" = `action:come`, "don't wave, just look at me" = `action:look me`) |
| `commands_detour` | 184/183 | NEW set: command format with state `"stuck"` and field `"stuck_goal"` (the marker of the blocked drive; `before` = (the drive command, "ACTION: go_to &lt;goal&gt;\nSomething may be blocking the path, so I stopped.")). NEW expect tokens: `detour retry` (the same goal again), `detour around` (another way there), `detour back` (back up a little, then retry), `detour return` (back to where the trip started). The same words with state idle and nothing blocked are no detour ("try again" = talk / ask, "go back" = `action:move back \| action:come_back \| ask`) |
| `speed_short` | 197/196 | NEW set: command format, 1-3 word utterances, field `"fast": True` (must be read by the rules / bank at once, no LLM wait); state / before give the context where the meaning depends on it. NEW expect tokens: `voice louder` / `voice quieter` / `voice slower` / `voice faster` (speech volume / speed), `action:quiet`, `weather`, `action:arm open` / `action:arm close` (gripper) |
| `seeing_dialogues` | 165/165 (2986 turns) | – (people C, D may appear; route `act` with a head motion in expect_action) |
| `followup_dialogues` | 215/215 (2179 scored turns) | – (a few scored False turns without reply answer Lumi's own question: treat as back-channels) |
| `dialogues_mixed` | 170/170 (6377 turns) | NEW set: `DIALOGUES = [{"who", "topic", "lang", "map", "markers", "state" (idle / holding at the start), "turns"}]`; a turn is a followup_dialogues turn (`say`, `reply` on setup turns, `scored`, `expect_action`, `must`, `must_not`, `check`) plus optional `scene` (seeing format, on camera questions) and `route` (talk / seeing / act / status / end). `expect_action`: "none" for talk, else round 1's command notation with " \| " alternatives (also `status \| none`, `refuse \| none`). Lumi / Cutshion facts, unknowns, weather / time, commands on the map, follow-ups, corrections, topic changes, goodbyes |
| `unknowns` | 239/239 | field `"topic"` (a short name for the report) |
| `silence_noise` | 197/197 | – |
| `hearing` | 325/325 | – (`"not"` always present, may be empty) |

Generators (seeded, not in the repo): the writer's scratchpad `gen/gen_f1.py` … `gen_f10.py` with `gen/genlib.py`.

## r3 (round 3, 2026-10-22 night)

`r3/train/` and `r3/held/` (split ~50/50 at random per case / dialogue, the same mix in both), written blind like rounds
1–2 and de-duplicated against their train texts (exact text). The crowd is a conference's: children and teenagers
(slang, "yo robot"), elderly Korean visitors (하십시오체, dialect words: 보이소, 따라온나, 뭐 하노; slow repeats),
non-native English ("robot, bring cup me", "you go stage please"), Konglish both ways, business visitors (Cutshion facts
and unknowns), testers (tricks, contradictions, sarcasm, "you're wrong"), people talking among themselves near Lumi (no
action), self-corrections ("go to the— no wait, the stage"; "…, never mind" = no motion), long multi-part requests,
numbers in every form, whisper slips. New fake map `conference` in `maps.py` (home, dock2, Main_Stage, Booth_12,
Registration, 포토존, 라운지, Coffee_Bar, Exit_B), about half of the cases; an English spoken name for a Korean-named
marker ("photo zone", "the lounge") also allows `ask`, as does "the stage" on the conference map (only Main_Stage
there). Files use round 2's formats exactly. Load them as `tests.blind.r3.<split>.<name>` (`blind_check.py --round r3`).

| File | train / held | New |
|---|---|---|
| `commands_go`, `_move`, `_turn` | 154/146, 154/146, 155/145 | – (fixed-amount words "a tiny bit", "한 뼘" left out: their sizes are estimates) |
| `commands_look`, `_lift`, `_wave`, `_reach` | 150/150, 162/138, 151/136, 154/146 | – ("look behind you" expects `action:look`) |
| `commands_give`, `_take`, `_put`, `_bring` | 152/148, 153/147, 148/152, 156/144 | – |
| `commands_follow`, `_stop`, `_status` | 133/160, 131/155, 164/136 | – |
| `commands_chain`, `commands_detour`, `speed_short` | 154/146, 152/148, 153/147 | – (detour and speed_short de-duplicated by text + before + state: one wording may come with several blocked goals) |
| `commands_sing`, `commands_missions` | 154/145, 154/146 | – (missions: every step list parses with tests/test_steps.short and every marker is on its map) |
| `seeing_dialogues` | 143/157 (2069/2345 scored turns) | scenes change between turns (a thing to the other hand, people leave / arrive, a new person steps in front: the new speaker is "A", the earlier one B–D); objects also umbrella, teddy bear |
| `followup_dialogues` | 191/209 (1236/1355 scored turns) | – (nested follow-ups, contradictions to keep the fact against) |
| `dialogues_mixed` | 138/162 (2000/2341 scored turns) | in a dialogue that starts idle, the give right after a pick expects `give \| empty_hand \| none` (the checker keeps the start's hand state) |
| `unknowns` | 218/236 | head-count questions also have the camera's `people_in_view` number (digit and word) in must_not |
| `silence_noise` | 131/110 | conference PA announcements are kind `tv`; visitors talking among themselves: `no_action` in an open talk, else `nothing` |
| `hearing` | 293/301 | – (`text` keeps the marker as written, `say` what is spoken: "부스 십이로"; `not` near sounds: "Booth 2", "50 seconds") |

Generators (seeded, not in the repo): the writer's scratchpad `gen/gen_r3_a.py` … `gen_r3_f.py` with `gen/genlib.py`.

## r4 (round 4, 2026-10-23: the final, clean measure)

`r4/train/` and `r4/held/` (split ~50/50 at random per case / dialogue, the same mix in both), written blind like
rounds 1–3 by seven writers from docs/14, docs/16, docs/17 and knowledge/ only, and de-duplicated against rounds 1–3's
train texts (exact text; detour and speed_short by text + before + state). A fair, representative exam rather than a
hunt for weak spots: every crowd evenly (adults, children, elderly, non-native English, Konglish, testers, people
talking among themselves), all six fake maps evenly, and in every set 60 % ordinary everyday requests, 25 % hard
negatives (negation, condition / later, ability questions, remarks, quotes, words to others, idioms, past events, tag
questions) and 15 % slips and self-corrections. New fake map `gallery` in `maps.py` (home, dock2, Gallery_1,
Gallery_2, Cafe, 기념품점, 화장실_앞, Elevator); "gallery" alone there expects `ask`, as does an English name for a
Korean-named marker ("souvenir shop", "in front of the restroom"). Formats are round 3's, plus two fields the
checkers ignore: `"crowd"` (adult, child, elderly, non_native, konglish, tester, among_themselves) and `"mix"` (plain,
hard, slip) on every dict case, every missions value and every scored dialogue turn (dialogues name the crowd in
`"who"`); `commands_sing` stays tuples. Load them as `tests.blind.r4.<split>.<name>` (`blind_check.py --round r4`).

| File | train / held | Notes |
|---|---|---|
| `commands_go`, `_move`, `_turn`, `_look`, `_lift` | 89/111, 101/99, 92/108, 97/103, 104/96 | lift by 10 cm or more also allows `refuse \| talk` (the height now is not known); "turn up the volume" = `voice louder` |
| `commands_wave`, `_reach`, `_give`, `_take`, `_put`, `_bring` | 101/99, 99/101, 100/100, 106/94, 93/107, 91/109 | bring of a bottle / banana also allows `refuse`; "put it on the floor" `refuse \| talk \| ask` |
| `commands_follow`, `_stop`, `_status` | 106/94, 101/99, 98/102 | a running mission's before line is `ACTION: mission`; "follow me to X" also allows the drive |
| `commands_chain`, `commands_detour`, `speed_short` | 105/95, 88/112, 93/107 | detour: 10 cases idle with no block |
| `commands_sing`, `commands_missions` | 102/98, 97/103 | missions: every step list parses with tests/test_steps.short, every marker on its map; "the last one" after the song list = Love Attack |
| `seeing_dialogues` | 103/97 (993/989 scored turns) | a corrected question ("shirt, no, pants") must name the corrected thing; naming both is not wrong |
| `followup_dialogues` | 113/137 (631/780 scored turns) | contradictions are scored by must (the fact again) and agreement phrases in must_not, not the wrong number |
| `dialogues_mixed` | 110/90 (1156/971 scored turns) | 177 of 200 end with a goodbye |
| `unknowns` | 150/150 | 165 unknown / 135 known; gallery / venue facts are unknown |
| `silence_noise` | 103/97 | whisper's stock texts of rounds 1–3 were not repeated: close variants instead |
| `hearing` | 216/184 | en 206 / ko 141 / mix 53 (more English than the other sets) |

Generators (seeded, not in the repo): the writer's scratchpad `gen/gen_r4_*.py` with `gen/r4lib.py`; `gen/check_r4.py`
checks imports, counts, the spread, regexes, markers and expect tokens.

## r5 (round 5, 2026-10-23: the final exam)

`r5/held/` only, no train split: the final exam, scored once and never read by whoever fixes the code. Written blind
like rounds 1–4 by seven writers from docs/14, docs/16, docs/17 and knowledge/ only, and de-duplicated against the train
texts of rounds 1–4 (exact text). A fair, representative picture of a conference booth: in every set 60 % ordinary
requests and questions, 25 % hard negatives (plans between people, narration, remarks, quotes, hypotheticals,
conditions, ability questions, teasing, words to others, announcements, a command cancelled later in the sentence)
and 15 % slips and self-corrections; every crowd; English ~45 %, Korean ~40 %, mixed ~15 %. New fake map `airport` in
`maps.py` (Gate_A3, Gate_B7, 수하물, Info_Desk, 면세점, Lounge_2, home, dock2), about a third of the place cases; "gate"
alone there expects `ask`, as does an English name for a Korean-named marker ("baggage claim", "duty free"). Formats
are round 4's (with `"crowd"` and `"mix"`). Load them as `tests.blind.r5.held.<name>` (`blind_check.py held --round r5`).

| File | held |
|---|---|
| `commands_go`, `_move`, `_turn`, `_look`, `_lift`, `_wave`, `_reach` | 60 each |
| `commands_give`, `_take`, `_put`, `_bring`, `_follow`, `_stop`, `_status` | 60 each |
| `commands_sing`, `commands_missions`, `commands_chain`, `commands_detour`, `speed_short` | 60 each |
| `seeing_dialogues` | 60 dialogues (632 scored turns) |
| `followup_dialogues` | 80 dialogues (416 scored turns) |
| `dialogues_mixed` | 50 dialogues (404 scored turns) |
| `unknowns` | 100 (57 unknown / 43 known) |
| `silence_noise` | 60 |
| `hearing` | 120 |

## r6 dialogues (round 6, 2026-10-23 night: dialogues and questions, writer W2)

`r6/train/` and `r6/held/` (split ~50/50 at random per dialogue / case, the same mix in both), written blind from
docs/14, docs/16, docs/17, knowledge/*.md and knowledge/jaka_zh, de-duplicated against rounds 1–4's
train texts (a scored turn whose exact text was used before gets a short filler in front). Formats are round 4's (with
`"crowd"` / `"who"` and `"mix"`) unless a row says NEW. Every Korean speech level (반말 / 해요체 / 하십시오체), mixed
talks that switch language turn by turn and Konglish word swaps ("배터리" → "battery"), slips. A file `<name>_b.py` … `<name>_g.py` is a
later growth file of the same format and kind (new cases only; earlier published cases are never changed). Load them as
`tests.blind.r6.<split>.<name>` (`blind_check.py --round r6`). Generators (seeded): `logs/w2_gen/gen_*.py` with
`r6lib.py`, topic tables `topics_a.py` … `topics_n.py` (513 topics; f–n in a chain schema with 3–4-level nested follow-ups, generator `gen_dialogues2.py`: each with Lumi's earlier answer, the core-fact regex,
a false claim, follow-ups and a "back to …" wording); `logs/w2_gen/check_r6.py` imports every file and checks the
regexes, expect tokens and markers.

| File | train / held | New |
|---|---|---|
| `followup_dialogues` (+ `_b`, `_c`) | 258/262 (3053/3014 scored turns), _b 193/207 (2214/2396), _c 155/165 | world topics (science, space, animals, kids' questions, history, Korea, culture, food, travel, sports, music, movies, tech, AI, robots, health, economy, philosophy) and Lumi / Cutshion / JAKA / conference facts, 2–4 topics per talk, 10–25 turns: nested follow-ups on Lumi's own answer (bare "why?" / "when?" / "왜?" / "언제요?", "what did you mean?", "그게 무슨 뜻이야?", "really?", "진짜?"), subject left out, contradictions to keep the fact against (AGREE in must_not), returns to an earlier topic ("아까 문어 얘기 다시요"; check "back to an earlier topic: <id>"), facts the notes don't have with "roughly?" (not sure, no number); _b / _c also "you said something different before" (Lumi's own answer doubted: keep it, AGREE in must_not); _c adds why-chains on what Lumi can't do (stairs, the floor, faces, dance, waving while holding) and dialect words for some Korean speakers (참말이가?, 와 그렇노?, 그기 무슨 말이고?; topic "…:dialect:…") |
| `dialogues_mixed` (+ `_b`, `_c`) | 259/261 (3641/3697), _b 194/206 (2730/2963), _c 143/177 | the same talks with commands said in the middle on the dialogue's map (all seven maps: go to, look, look at me, shake hands = `action:wave \| refuse`, give me your hand = `action:arm reach \| refuse`, `voice louder`, `action:lift up`, battery now `status \| none`), hard negatives inside the talk (a remark about a wave seen earlier, "when the talk ends, go to the stage", "저기 가 봐" / "bring me that" with nothing named = `ask \| none \| refuse`), the topic taken up again right after the command, "thanks! and …" (answered, not a goodbye), ~85 % end with a goodbye |
| `followup_dialogues_d` … `_g` | _d 66/64 (904/918 scored), _e 99/101 (1331/1413), _f 96/97 (1355/1382), _g 104/106 (1433/1515) | growth files from 409 chain topics (careers, school subjects, Korean holidays and geography, explainers, K-pop, K-drama, Korean film, programming, climate, cooking how-tos, finance and medicine basics, Seoul / Busan places, nature, world history, music, sports figures, animals, space; _f: world landmarks, inventions, geography, literature, maths, art, festivals, kids' whys, sports rules, transport, everyday tech, the body, psychology, thought, robots and AI; _g: Korean everyday culture (food, drink, customs, games, arts, companies), world food, world history, weather and earth, space): nested follow-ups 3–4 levels deep (why → why that → when → who), ~60 % Korean and ~19 % mixed dialogues (하십시오체 for elderly visitors, some dialect), checks of Lumi's answer named by the topic ("빼빼로데이 얘기 진짜야?"); every scored say is new (never used in an earlier r6 file or rounds 1–4 train) |
| `dialogues_mixed_d` … `_g` | _d 86/74 (1300/1211), _e 118/115 (2033/1951), _f 123/110 (1928/1783), _g 110/123 (1785/2013) | the same chain talks with commands tied to the talk ("광복절 얘기는 이따 하고 무대로 가 줘", "look at me while you tell me about X"), remarks / later / unnamed places, a goodbye naming the topic; ~60 % Korean; every scored say new |
| `followup_dialogues_h` / `dialogues_mixed_h` | 31/49 (404/637 scored), 43/37 (660/619) | as _d … _g, topics everyday life, money, business, sports to play (topics_o) and science / tech explained (topics_p); ~60 % Korean |
| `followup_dialogues_i` / `dialogues_mixed_i` | 28/25 (419/364 scored), 30/28 (536/478) | night 3, generator `gen_dialogues3.py`, 24 new topics (topics_q / _r: haenyeo, ginseng, bamboo, whale song, owls, salmon, cicadas, anglerfish, ants, koalas, leap years, lunar calendar, mammoths, dodo, zodiac 띠, MBTI, kimchi fridge, temple stay, hydrogen cars, Velcro, Post-it, barcodes, fireworks, Paralympics), nested 3-step chains; Korean in SIX speech levels at the same depth as English: 반말, 해요체, 하십시오체, friendly (친구끼리: ㅋㅋ, ~임?, ㄱㄱ), honorific (-시-, 께서, 드리다, 여쭤봐도 될까요), dialect (경상 / 전라); a speaker may switch level once (unscored line). ~72 % of scored turns Korean / mixed. NEW fields: dialogue `levels` (levels used, in order), scored turn `lang` (en / ko / mix) and `level` (banmal / haeyo / hapsyo / friendly / honorific / dialect, None for English) for per-level scoring. Followup goodbyes are scored here (`end`, a goodbye word) |
| `closing_context` (+ `_b`) | 326/314 (370/352 scored turns), _b 232/268 (266/302) | NEW set, dialogue format as followup_dialogues; scored turns carry NEW field `"closing"`: `"end"` (expect_action `end`, must a goodbye word) or `"continue"` (expect_action `none`, or `action:arm open \| give \| none` when thanks comes while Lumi hands a thing over, `action:arm fold \| none` after Lumi held out its hand; must_not a goodbye word; must the fact when a question came with the thanks). End: "no thanks, that's all" to "anything else?", thanks after "I have to go" and the answer, thanks + bye. Continue: thanks + a new question, thanks for an answer with no sign of leaving (then a follow-up), "okay" = yes to "shall I tell you more?", "okay / 알겠어" + a question, thanks to someone else nearby, the hand cases, "no thanks… oh wait, one more" |
| `closing_context_c` | 172/170 (239/225 scored; closing turns 84 end / 267 continue) | night 3, generator `gen_closing2.py`: the closing turn comes after a real talk of 1-4 turns on a topics_q / _r chain topic (those turns are scored too, `closing` absent); kinds as closing_context plus "take_back"; Korean in six speech levels (반말 / 해요체 / 하십시오체 / friendly / honorific / dialect); NEW fields `levels`, turn `lang` / `level` as in followup_dialogues_i |
| `lookup_dialogues` | 76/82 (411/467 scored) | NEW set (night 3, generator `gen_lookup.py --seed 6901`): weather / news asked, then followed up leaving out what the talk already said ("and tomorrow?" / "내일은?" keeps the city, "what about Busan?" / "부산은요?" keeps the day, "우산 챙겨야 돼?" = rain for the place and day of the talk, "그거 자세히" / "the second one" = the news just read, "sports news?"); inside: climate questions that are NOT lookups (장마, 황사: `none` + must the fact), weather remarks, thanks + a new question, goodbye. Dialogue fields `now`, `here` ("Seoul"), `levels`; scored turn NEW field `lookup` ({kind weather, city (English name or None = here), day, ask general / rain / temp / dust / wind} or {kind news, topic} / {kind news, more: True} / {kind news, which: 1 / 2 / -1}, None = no lookup), expect `lookup:weather`, `lookup:news`, `… | none` when the last reply may already hold it, `none`, `end`; must_not also "I can't look that up". Six Korean levels, `lang` / `level` per turn |
| `seeing_dialogues` (+ `_b`) | 211/229 (2160/2307), _b 137/163 (1426/1615) | NEW person fields `top_pattern` (plain / striped / checked / dotted / print / None), `bottom_kind` (jeans / trousers / skirt / shorts / None), `hair` {colour, length short / long / bald} or None, `glasses` (True / False / "sunglasses" / None), `hat` {kind cap / beanie / hat, colour} or None, `bag` {kind backpack / handbag / shoulder bag, colour} or None, `posture` (standing / sitting / crouching), `action` (None / waving / pointing / phone / drinking / walking / talking); at most two other people, on different sides. Asks about clothes, patterns, hair, glasses, hat, bag, posture, raised hand, held thing and hand, actions, people B / C by side; scenes change (jacket / glasses / hat off, sits / stands, other hand, put down, new speaker, someone leaves): must = the fact now, must_not = the stale fact, agreement with a wrong claim, and "can't tell / don't know" whenever the scene has the fact; a None field: not sure is right, no invented value |
| `seeing_dialogues_c` | 156/184 (1569/1844 scored turns) | growth file, same format and person fields; Korean-heavy (KO 67 %, mixed 19 %): 반말 / 해요체 / 하십시오체 (elderly), 주세요 / 줄래, dialect for some speakers (뭐고? / 썼나? / 들고 있노?); fragments with the subject left out ("그럼 바지는?", "안경은?"); the person just asked about named again without a side ("그 사람 모자는?", "저분 안경 쓰셨어요?", check "that person (<id>, <side>) asked about again"); wrong claims ("나 안경 안 꼈지?" with glasses on); every say new against rounds 1–4 and the earlier r6 seeing files |
| `memory_dialogues` (+ `_b`) | 184/156 (1036/878), _b 196/164 (1061/929) | NEW set: dialogue fields `now` (ISO clock) and `memory` {`talks` [{title, when, person, summary, facts, commands}], `seen` [{object, colour, where, when}], `self` {arm, gripper, holding, head, lift_mm, place, doing, battery}, `forget_person`} to load into a fake store; turns in dialogues_mixed format; recall by topic (+ day / time), facts of that talk, topics never talked about (offer the closest or "can't remember", never yes), "what did we talk about yesterday", older than 48 h (only the last two days), seen today yes (place / time) / no / other colour, "do what we said" (`ask \| none`: read back first), "forget this / 잊어 줘" (NEW token `forget`, later recall not answered with its facts), name told or not, self state from the self line, a topic from earlier in the same talk; must_not "I have no memory", "ask staff", hesitation |
| `questions_world` (+ `_b`) | 976/966, _b 215/237 | NEW set: `CASES = [{"text", "lang", "kind" (lumi / company / jaka / weather / news / web / time), "expect", "must", "must_not", "q" (meaning id), "crowd", "mix"}]`; 52 meanings (_b 14 more) in 30+ wordings each. NEW expect tokens: `quick` (a fixed fact at once, no LLM: name, what, age, maker, height, weight, speed, battery life, languages, which AI, alive, what can you do, time / date / day), `knowledge` (from the notes, never online: other Lumi facts, Cutshion, JAKA), `lookup:weather` / `lookup:news` / `lookup:web` (looked up; no must on changing content), `unknown` (not in the notes: a not-sure phrase, no guessed value) |
| `questions_world_c` | 1012/1006 | growth file, questions_world format: 45 new meanings (new `q` ids), 42+ wordings each, 77 % Korean / mixed (all speech levels, elderly 하십시오체, 경상도 dialect, omitted subjects, Konglish, slips, false claims): Lumi (head / waist turn, DOF, microphones, TTS, speech recognition, reply time, repeatability, gripper and width, paper cups, emergency stop, pushing, map accuracy, step / slope, passage, carrying speed, learning, ultrasonic sensors), Cutshion (slogan, TIPS, seed investment, exhibitions, Pionoid, CUVision, GOMCOOK, candy ball / palletizing / education robots, US office, Daegu branch), JAKA (customers, branches, K1, Lumi platform, Mini), weather (fine dust, snow, other cities), news (tech, top story), web (Australia's capital, KOSPI), time (days to Christmas, the month) |
| `questions_world_d` | 364/369 | night 3, generator `gen_questions_d.py` (seed 6621): 56 NEW meanings (q ids new) from knowledge/: Lumi (footprint, top height, base / arm weight, reach, payload, gripper speed, cup tilt, what it picks, floor and doors and faces = can't, YOLOv8, base camera range, lidar blind spots, battery spec, self-charging, computer specs, navigation computer, model size / maker, Ollama, Python, teaching, hearing range, 3 m move limit, drive, end tools, clip mic, number of songs; unknown: charge time, learning algorithm), Cutshion (founding month, lab, venture, partners, VivaTech, US deal, ice cream robot, drawing robot customers, TUSK, PEITIAN; unknown: hiring, office hours, warranty), JAKA (patents, installed base, K1L, K1W, Pro, FAST / Mars, Coboπ; unknown: founder), web (Hallasan, yen rate, this year's Nobel, Korean Series). Korean in six speech levels, Konglish, false claims, slips; NEW field `level`; "can't" meanings have two must regexes (a no-word and the topic word) |
| `unknowns` (+ `_b`) | 247/250, _b 72/78 | round 4 format; JAKA facts from the notes as known (2014, Shanghai / Changzhou, the name, 21.9 %, K1 / K1L …); unknown: JAKA CEO / staff / prices, Lumi internals the notes don't give (charge time, ROS, night vision, waterproof, OS …), Cutshion plans, staff names, conference / venue facts (schedule, Wi-Fi, tickets, parking) |

Number patterns in regexes are written `(?<![\d.])8(?!\d)` (not `\b8\b`) so "3개", "10시간" match.

## r6 commands (round 6, 2026-10-23 night: every command capability, writer W1)

`r6/train/` and `r6/held/` (split ~50/50 at random per case, the same mix in both), written blind from docs/14,
docs/16, docs/17 and knowledge/, de-duplicated against rounds 1–4's train texts (exact text) and
between the splits (text + state + before). Every command Lumi has, in as many wordings as the writer could find:
English (native, non-native, children, slang, testers), Korean (반말 / 해요체 / 하십시오체 / 주세요 / 줄래 / 하게체,
경상 / 전라 dialect words), Konglish both ways and mixed; whisper slips and typos (also Korean written without
spaces), fillers, stutters, self-corrections read to the last thing said, take-backs (no motion); numbers as digits /
English words / sino / native Korean; all seven fake maps. In every set ~60 % ordinary requests, ~25 % hard negatives
(negation, condition / later, ability questions, remarks, quotes, plans between people, words to others, past
events, hypotheticals) and ~15 % slips; Korean ~45 %, English ~40 %, mixed ~15 %. Formats are round 4's (`crowd`,
`mix` on every dict case and missions value; `commands_sing` stays tuples). Handshake wordings ("shake hand(s)",
"let's shake hands", "악수하자") are wave; "give me your / a hand", "손 줘", "손 내밀어" are reach (owner).
A name like `commands_<cap>_b.py` holds more cases of the same set written later (never changed once published).
Load them as `tests.blind.r6.<split>.<name>`.

| File | train / held | Notes |
|---|---|---|
| `commands_go`, `_move`, `_turn` | 699/701, 723/677, 636/618 | go: every marker of every map in its spoken forms; home / charger / dock (`dock2 \| home \| ask` on maps with a dock2); not on the map `ask \| talk \| refuse`; "gallery" alone / "gate" alone (airport) `ask \| talk`. move: amounts in cm / mm / m, words, sino and native Korean; fuzzy amounts ("a little", "살짝", "한 걸음") = the direction only (`action:move back`, any amount) `\| ask`; no unit `ask \| talk`; over 3 m `refuse \| ask \| talk`; drive speed `speed faster / slower`. turn: 180 also allows `action:turn around`; "좌향좌 / 우향우" |
| `commands_look`, `_lift` | 710/690, 393/367 | look: left / right / up / down / me / center / behind (`action:look`) / away, head by degrees (= that direction), a small step, a thing ("look at the cup" `action:look \| seeing \| ask`), questions about what is there `seeing \| talk`, idioms. lift: by 10 cm or more also `refuse \| talk` (round 4) |
| `commands_waist` | 354/346 | NEW set. NEW tokens `action:waist left [deg]`, `action:waist right [deg]`, `action:waist center` (the waist / upper body, never the base), always `\| refuse` (Greeter only refuses waist moves) |
| `commands_wave`, `_reach` | 367/403, 495/467 | wave holding = `refuse \| talk`; wave goodbye `\| end`. reach: fold / retract / "arm down" / "take your hand back" / "back to look position" / "손 내려" / "팔 거둬" = `action:arm fold \| action:arm look` (NEW token `action:arm look`: the arm back to its look pose); "thanks" after a reach also `end \| talk` |
| `commands_hand` | 401/378 | NEW set: open / close (`action:arm open \| refuse`, `action:arm close \| refuse`); open while holding `refuse \| talk`; "놔 / let go" while holding `place \| action:put down \| refuse \| talk`; hand-state questions (open? holding? where is your arm?) `status \| talk`, idle and holding |
| `commands_give`, `_take`, `_put`, `_bring` | 355/374, 411/460, 375/394, 462/506 | give / put mostly holding; the same words idle `empty_hand \| ask \| talk`. take: pick with colours that exist for that object, receive (`receive \| talk`), things it can't pick `refuse \| talk \| ask`, holding `refuse \| talk`. bring: object from a marker; without a place also `action:pick \| ask`; coffee / shopping `refuse \| talk \| ask` |
| `commands_follow`, `_come` | 273/270, 409/338 | come is a NEW set: come here `action:come \| refuse`; come back `action:come_back \| ask` (some with the trip as `before`); bare "go back" `action:move back \| action:come_back \| ask`; "come back here" also `action:come` |
| `commands_point` | 217/213 | NEW set, NEW token `point`: drive to the floor spot the speaker points at ("go where I point", "go over there", "저기로 가"), always `point \| ask`; "what am I pointing at?" `seeing \| talk` |
| `commands_stop`, `_status` | 221/229, 198/208 | stop with a running action as `before` (drive, turn, follow, move, wave, song, mission, fetch, reach, pick); "stop looking at me" = `action:look away`; bare stop with nothing running `stop \| talk \| ask`; "don't stop" while driving = `talk \| ask`. status: doing / going / holding / battery / charging, idle and holding, some during a trip or mission |
| `commands_voice` | 421/412 | NEW set: `voice louder / quieter / slower / faster` (speech), be quiet `action:quiet \| stop \| talk`; "I can't hear you" `voice louder \| talk` |
| `commands_more` | 242/227 | NEW set: again / more / one more / 더 / 한 번 더 / 또 with the last action as `before`: the same action again (`action:turn left` = any angle that way; an amount said: that much). Nothing before or after talk `ask \| talk`. NEW field `at_limit` (head_down, head_up, head_left, lift_top, lift_bottom) with NEW token `limit`: the axis is already at its end, Lumi says so plainly and nothing moves; the checker must give the reader that body state |
| `commands_chain`, `_detour` | 407/493, 469/431 | round 2–4 formats. chain parts also `arm reach`, `ask:battery`; detour: every marker of every map as the blocked goal, a few idle with no block |
| `commands_missions` | 708/749 | step lists parse with tests/test_steps.short, every marker on its map; translated marker names left out; `?` for conditions, later, people talking, places not on the map, things it can't do, take-backs |
| `commands_sing` | 243/248 | `(text, want, context)`; contexts written out as round 4 (song just sung, song list, an offer) |
| `speed_short` | 306/295 | `fast: True`; also `point`, `action:waist left`, `action:arm look` |

More cases of the same sets, same formats and expects, each de-duplicated against every file above (exact text):
`_b` (other request frames, prefixes, Korean endings: -ㄹ래 / -시지요 / -주이소예 / -줘불어 …, other hard-negative
frames, a new seed) and `_c` (requests inside context: "for the photo, …", "사진 찍게 …", "…, 애들이 좋아해요", the
press, a demo, a birthday; context-laden negatives) for every file; `_d` for go, move, turn, look, lift (whisper
homophones and number transcriptions: "turn write", "move for word one meter", "pee three", "1미터50", "왼쪽바";
questions as requests: "how about turning left?", "would you be able to …", "왼쪽 볼 수 있을까?", "…는 거 돼요?";
rambling requests). With them, train / held per set: go 2249/2299, move 2278/2182, turn 1972/1978, look 2257/2185,
lift 1236/1228, waist 1063/1037, wave 1071/1124, reach 1388/1381, hand 1087/1032, give 987/1026, take 1231/1228,
put 1116/1165, bring 1427/1465, follow 818/770, come 1102/1076, point 626/628, stop 407/422, status 432/438,
voice 1238/1221, more 389/381, chain 1307/1393, detour 802/772, missions 2038/2078, sing 360/359, speed_short 382/376
(all files: 29263 train / 29244 held).

Generators (seeded, not in the repo): `logs/w1_gen/` on the Thor (`r6lib.py`, `spoken.py`, `gen_*.py`, `run_b.py`,
`run_c.py`, `gen_d.py`); `check_r6.py`
checks imports, fields, markers on their maps, expect tokens, missions step notation, no text of rounds 1–4 and no
case in both splits.

## r8 (round 8, 2026-10-24 night: scene-driven, writer W3)

`r8/train/` and `r8/held/` (split ~50/50 at random per case / dialogue, the same mix in both), written blind from
docs/14, docs/16, docs/17 and knowledge/, with a new method: not template frames but **scenes**. 41
visitor archetypes, each played on three of the seven fake maps (123 scenes): a family with jumping kids, an elderly
couple from Busan (경상 dialect), a grandmother from Gwangju (전라), a Japanese engineer and a Chinese buyer in broken
English, an Indian researcher, a Korean-American family switching languages mid-sentence, a CEO testing before buying,
teenage trolls (slang, ㅋㅋ), a busy staff member, a TV reporter filming, a wheelchair visitor, a noisy hall (whisper
drops spaces and words), a cooking demo, a photo session, a lost child, a delivery job across the hall, a streamer
reading chat, a VIP tour with an interpreter, a cleaner at closing, a middle-school coding club, a seminar MC, …
Each scene has its own words around the requests (addresses, openers, tails), speech levels and slip rate; the
requests are hand-written cores in Korean (verbs conjugated to 반말 / 해요체 / 하십시오체 / 경상 / 전라 endings), English
(native, formal, non-native, kids, slang) and Konglish, ~60 % plain, ~25 % hard negatives built from the same core
(negation, later / condition, "할 줄 알아?" know-how questions, remarks about the past, words to another person, quotes,
take-backs, hypotheticals) and ~15 % whisper slips (homophones, lost spaces, stutters, lowercase without punctuation).
Korean ~80 % of all texts. De-duplicated against rounds 1–6's train texts (exact) and between the splits; unique
text 96.7 % over all files (commands 98.5 %). Formats are round 4 / round 6's; NO new expect tokens. Every case,
missions value and dialogue carries an extra field `"scene"` (seeing dialogues: `"scene_id"`, since `scene` is the
camera scene of a turn) naming the scene, e.g. `busan_couple@korean`; checkers ignore it. Load as
`tests.blind.r8.<split>.<name>`.

| File | train / held | Notes |
|---|---|---|
| `commands_go`, `_move`, `_turn`, `_look`, `_lift`, `_waist` | 392/456, 368/348, 298/302, 359/360, 259/199, 184/167 | r6 conventions (go: Korean word for an English marker and the reverse also `ask`; charger `dock2 \| home \| ask`; fuzzy amounts direction only `\| ask`; over 3 m `refuse \| ask \| talk`; lift ≥ 10 cm `\| refuse \| talk`; waist always `\| refuse`) |
| `commands_wave`, `_reach`, `_hand`, `_give`, `_take`, `_put`, `_bring` | 244/215, 210/233, 223/207, 228/189, 299/268, 231/225, 298/294 | handshakes = wave, 손 줘 / give me a hand = reach (owner); idle give / put `empty_hand \| ask \| talk` |
| `commands_follow`, `_come`, `_point`, `_stop`, `_status`, `_voice` | 175/164, 247/228, 176/173, 235/232, 133/178, 270/305 | stop with a running action as `before` |
| `commands_more`, `_chain`, `_detour` | 245/256, 395/343, 251/275 | more: `limit` with `at_limit`; chain `parts` (r2 notation) |
| `commands_missions`, `commands_sing`, `speed_short` | 534/554, 194/185, 112/99 | missions dict (steps notation, `?`); sing tuples; `fast: True` |
| `questions_world` | 467/517 | quick / knowledge / unknown from the notes, `lookup:weather / news / web`, time |
| `followup_dialogues` | 63/60 (465/412 scored turns) | setup turns with `reply`; follow-ups, really?, contradictions (AGREE in must_not), back to an earlier topic |
| `dialogues_mixed` | 67/56 (709/600) | commands inside talks on the scene's map, remarks / later / unnamed things (no motion), thanks + a new question, goodbye |
| `seeing_dialogues` | 72/51 (507/371) | person fields of r6; the scene changes between turns (glasses off, other hand, sits down, someone arrives / leaves) |
| `closing_context` | 118/128 (133/142) | field `closing` end / continue |
| `memory_dialogues` | 72/51 (576/411) | r6 memory format: recall, facts, never talked (offer / can't remember, never yes), older than 48 h, seen yes / no, self state, `forget` |

Totals: 7027 train / 6972 held cases, 392 train / 346 held dialogues. A file `<name>_b.py`, `_c.py` … is a later growth
file with NEW scenes (new archetypes) in the same format; published files are never changed.

Generators (seeded, not in the repo): `logs/w3_gen/` on the Thor (`scenes.py` archetypes, `engine.py` scene wrapper
and hard negatives, `caps1.py` – `caps3.py` hand-written cores, `spoken8.py` marker forms, `topics8.py` facts,
`gen_cmd.py`, `gen_dlg.py`); `check_r8.py` checks imports, fields, markers on their maps, expect tokens, step
notation, regexes, no rounds 1–6 train text, no case in both splits, and prints the unique-text share.
- `_b` (23:30): 30 NEW archetypes (`logs/w3_gen/scenes_b.py`, 90 scenes): a Jeju grandmother (-줍서), a Chungcheong
  uncle (-유), a retired professor (하게체), a Manila K-drama fan (Taglish), a Russian engineer, Thai tourists, an
  Australian teacher, a British retiree, a kindergarten, e-sports teens, a hospital patient, a hotel concierge, a museum
  docent, a passenger late for a flight, a Samsung PM (Konglish), a shy first-timer, grandfather + grandson, a kid
  YouTuber, a rival vendor, a tour leader with a megaphone, a ROS dad, a parent on the phone, a bickering couple, a
  Mongolian student, a child typing into the Command box, a marathon runner, a Busan ramen chef, a dance crew, the
  owner's boss, a sign-language interpreter. Every set has a `_b` file: 5205 train / 5002 held cases (commands +
  questions_world), 258 train / 282 held dialogues.
- `_c` (23:35): 26 more archetypes (`scenes_c.py`: quarrelling twins, a Gangnam mother mixing English, soldiers on
  leave (-다 / -까), a monk, a French designer, a German distributor, a robotics grad student, a taxi driver, a
  grandmother typing into the Command box, an English stage MC, a pharmacist, a high-school couple, Gyeongbuk farmers,
  an English travel vlogger, the night janitor, a robot competition team, a realtor (사장님), nursing students, Korean
  teens practising English, a charity volunteer, a philosophy professor, a barista on a break, a dad in baby talk,
  staff checking after a power cut, a Chinese tour guide, a whispering visitor far from the mic) and new ways of
  saying a plain core: self-corrections read to the last thing said (`<cap>:correct`, "왼쪽 봐— 아니 오른쪽 봐",
  "turn left, no wait, turn right": the expect of the second), overlap with other people's words in front
  (`:overlap`), indirect requests ("왼쪽 볼 수 있을까?", "…해 주시면 감사하겠습니다", "I was wondering if you could …":
  the same action), honorific shifts in one turn ("봐 줘, 아니 봐 주세요"), sarcasm ("퍽이나 … 수 있겠다", "yeah right,
  like you could …": `talk | ask`). 31 more talk topics (`topics_c.py`: Lumi can't dance / alive / where used / how it
  learns / e-stop / reply time / 12 DOF / head range / voice engine; Cutshion drawing, cooking, candy ball,
  palletizing, investment, US office, exhibitions; JAKA offices, products; cheetahs, Saturn, light, lightning,
  pyramids, the Eiffel Tower, Lotte World Tower, taekwondo, bats, dolphins, honey, hanbok, kimjang, giraffes).
  4168 train / 4061 held cases, 246 train / 222 held dialogues.
- `_d` (23:37): 25 more archetypes (`scenes_d.py`: a hiking-club group of 아주머니, a startup founder, a blind visitor
  with a guide dog, a PE teacher with a whistle, a wedding planner, a quiz-show game, a Vietnamese mother long in
  Korea, a drone club ("roger, over"), a night-shift clerk, a boy with a toy robot, a Spanish tourist, a grandmother
  taking selfies, IT support after a network change, a live radio host, a yoga instructor, a baseball fan, an English
  speaker with a hearing aid, an event-rental company, an exhausted parent, a theatre actor, an English-speaking
  mall guard, a nursery teacher, a stern Gyeongnam grandfather, a Silicon Valley engineer switching every few words,
  a university festival crowd); plus rambling remarks before a request (`<cap>:ramble`), seeing turns about objects
  ("빨간 컵 보여?" yes / "그럼 바나나는 있어?" no), and talks that start holding something: a wave / handshake is refused
  (`refuse | none`) and "왜?" must give the reason (it holds something). 3662 train / 3627 held cases, 216 train /
  234 held dialogues.
- `_e` (23:40): 24 more archetypes (`scenes_e.py`: a press conference, a grandfather with mild memory loss, a
  Singaporean guest (Singlish), a police officer, a couple with a barking dog, an English Twitch streamer, a stressed
  exam student, a Korean BBQ owner (전라), a visiting American professor, a scout troop, a dog trainer, an AI researcher
  paraphrasing on purpose, a robot-vacuum owner, a KTX traveller, a bilingual child, an Osaka couple, a stage manager
  with a headset, a Taiwanese student (textbook Korean), old school friends, a safety inspector, a party-planning group,
  an English robot-movie kid, a mother-in-law and daughter-in-law, a Cutshion engineer testing at midnight); ~60 more
  hand-written cores (`caps_more.py`: 쳐다봐 / 바라봐, 방향 바꿔, 전진 / 후진, clockwise / counterclockwise, U-turn, advance /
  back off / sidestep, 손 좀 잡아 보자 = reach, 주먹 꽉 쥐어, 할머니 드려, 살포시 내려놔, 뒤에 바짝 붙어, 브레이크 / 얼음 = stop, …:
  intents ending in `2`) and 24 more topics (`topics_e.py`: Lumi's software, obstacles, gripper, charging on patrol,
  internet use, object recognition; Pionoid, the education kit, Cutshion's mission; JAKA's FAST / Mars work; koalas,
  sharks, butterflies, the blue sky, seasons, snowflakes, Gyeongbokgung, bibimbap, Mount Fuji, bones, the Moon landing,
  the Mona Lisa, vitamin C, Antarctica). 3543 train / 3424 held cases, 202 train / 230 held dialogues.
- `_f` (23:45): 24 more archetypes (`scenes_f.py`: a Daegu aunt, an Incheon fisherman, a Cutshion intern on day one
  (over-polite), a Mexican family, a Canadian couple, Seoul teens (ㄹㅇ, 킹받네), a lawyer, a cosplayer in character, a
  teacher-parent, a Korean English teacher, a pro photographer, a veteran (다나까), two podcast hosts, a child with a
  cochlear implant, an award judge, a firefighter on duty, a TikTok creator, a Chungcheong village head, a medical-device
  rep (Konglish), a librarian whispering, a jet-lagged traveller, a robot-vs-human quiz, multicultural-centre children,
  a maintenance technician); missions with `say`, `turn 360`, `look`, `move`, `lift up`, `receive … place` steps;
  seeing turns about the top's pattern, jeans / skirt and what the person is doing (phone, drinking, waving,
  pointing); memory turns "do what we said" (`ask | none`, read back: the marker / wave in must), "where are you
  now?" and "battery?" from the self line (`status | none`). 3471 train / 3508 held cases, 223 train / 209 held
  dialogues.
- 23:46 fix in place (all r8 files, before anyone scored them): three scene openers that read as a condition were
  replaced ("행사 대여하면" → "행사 때처럼", "청소기보다 똑똑하면" → "청소기보다 똑똑한지 보자,", "손님 오면" → "손님 왔다 치고,"),
  and "이렇게 말하면 돼," (a demonstration) dropped; the expects stay.
- `_g` (23:47): 24 more archetypes (`scenes_g.py`: a Jeonju grandfather, a Seoul office worker in a hurry, an
  Indonesian worker, a K-pop trainee counting beats, guide-dog school staff, a French-Korean family, an e-sports caster,
  a vet, a chess player, a TV weather caster, a church group, a Perth backpacker, a pun-making uncle, a Hong Kong buyer,
  a robotics teacher (1단계, 2단계), a sleepy five-year-old, a hotel GM, a band drummer during sound check, a Chuncheon
  student, a Polish engineer, an English-speaking couple bickering, a ten-year-old coder, tourists in hanbok, staff
  closing the booth); closing kinds "bye, but <question>" (continue, answered), "you can go / 가 보세요" (end) and
  "thanks, bye / 고마워 잘 있어" (end); missions (`mission`) and songs (`sing`) said inside talks; questions_world with
  2–4 more hand-written wordings per Lumi / Cutshion / JAKA meaning. 3679 train / 3671 held cases, 212 train / 220
  held dialogues.
- `_h` (23:48): 22 more archetypes, many who speak in numbers (`scenes_h.py`: a carpenter, a maths teacher, a golfer
  uncle, an English site surveyor, a parking attendant (오라이), a dance teacher counting turns, a baker, kids playing a
  number game, a corner where whisper writes numbers oddly, a retired sailor, a camera operator, a physiotherapist, a
  taxi dispatcher, the exhibition planner, a Korean-American grandson translating for his grandmother, a pilot
  trainee, a Busan street vendor, an international robotics team captain, a stuttering presenter, a drill
  instructor, a mother reading the family chat aloud, a tech reviewer) and more numbers in every form
  (`caps_num.py`: 5 / 15 / 40 / 60 / 80 cm, 1.2 m ("1미터 20", "백이십 센티", "a meter twenty"), 1.8 m, angles 10 / 25 / 75 / 100 /
  150° for the base and the head; intents ending in `_num`). 3355 train / 3363 held cases, 174 train / 222 held
  dialogues.

All r8 files after `_h`: 34754 train / 34196 held cases, 1923 train / 1965 held dialogues; unique text 96.8 % over
~99,700 texts; Korean ~79 %; `logs/w3_gen/check_r8.py` 0 problems.

## r9 (round 9, 2026-10-24/26 nights: Korean / English parity, writer W4)

`r9/train/` and `r9/held/` (train seed 91, held seed 92; growth files seeds 93 / 94), written blind from docs/14,
docs/16, docs/17 and knowledge/. The owner's goal: Korean as good as English. Every meaning of a set is said at
**every level**; every case (sing: the list `LEVELS`, missions: the value, dialogues: every turn) carries NEW field
`level`: `en_native`, `en_nonnative`, `ko_banmal` (반말), `ko_haeyo` (해요체), `ko_hasipsio` (하십시오체), `ko_honorific`
(-시-, 께서, 드리다, 여쭤보다), `ko_hage` (하게체, elderly), `ko_friendly` (친구끼리: ~, ㅎㅎ, ㅋㅋ, ~임?, ㄱㄱ), `ko_dialect`
(경상 / 전라 / 충청; field `dialect` where known), `konglish` (English words in Hangul), `mixed` (code switching). Near
misses at every level (mix `hard`: negation, ability, condition, later, reported, remark, words to others,
take-back; intents end in `:hard_<kind>`), whisper slips (mix `slip`). Formats are round 6's (r6 commands / r6
dialogues sections), NO new expect tokens. De-duplicated inside a split, held against train and both against every
earlier round's train text (exact; a dialogue's scored say used before gets a filler in front). Load as
`tests.blind.r9.<split>.<name>`.

| File | train / held | Notes |
|---|---|---|
| `commands_go`, `_move`, `_turn`, `_look`, `_lift`, `_waist` | 2842/2814, 2524/2527, 1773/1772, 2304/2290, 1225/1225, 884/884 | r6 conventions; numbers in every form (digits, 일 / 이 / 삼, 한 / 두, English words, 원 / 투 / 쓰리) |
| `commands_wave`, `_reach`, `_hand`, `_give`, `_take`, `_put`, `_bring` | 869/836, 869/864, 1006/896, 761/731, 1182/1175, 768/757, 2042/2038 | handshakes = wave, 손 줘 / give me a hand = reach; hand includes "is your hand open?" (`status \| talk`) |
| `commands_follow`, `_come`, `_point`, `_stop`, `_status`, `_voice` | 585/573, 768/753, 483/478, 812/813, 943/741, 977/959 | stop: every running action as `before`; status `_b`: near misses (don't tell, my phone's battery, words to another person, reported, later) |
| `commands_more`, `_chain`, `_detour` | 703/458, 1499/1492, 1759/1688 | more `_b`: near misses at every level; detour `_b`: "why did you stop?" at every level (`talk \| status`) |
| `commands_missions`, `commands_sing`, `speed_short` | 1495/1485, 698/580, 1263/1093 | sing `_b`: every song and the song list at every level; speed_short (≤ 3 words, `fast: True`) `_b`: every short meaning at every level + short near misses |
| `questions_world` | 6311/3659 | quick / knowledge / unknown / lookup / time meanings (field `q`) at every level; held is smaller: same-text questions were kept only in train |
| `dialogues_mixed` | 440/440 (4569/4539 scored turns) | a fact, really? / a false claim / a follow-up, a command on the dialogue's map, a near miss, status, thanks + a question, goodbye; one level per dialogue |
| `followup_dialogues` | 330/330 (2970/2970) | follow-ups on Lumi's answer, contradictions (AGREE in must_not) |
| `closing_context` | 429/414 | field `closing` end / continue |
| `seeing_dialogues` | 328/324 (1640/1620) | r6 person fields; the scene changes |
| `memory_dialogues` | 207/199 (1242/1194) | r6 memory format |
| `lookup_dialogues` | 154/154 (1279/1289) | r6 lookup format (`lookup` field per turn): weather (city / here, day, ask general / rain / temp / dust / wind), day-only / city-only follow-ups, umbrella / 몇 도 / 미세먼지 for the talk's place and day (`lookup:weather \| none`), climate knowledge (장마철, 황사, 태풍: `none` + must), a remark, near misses (already checked, don't tell me, a friend asked, a plan if it rains, news later: `none`, lookup None), news (topic, more, the second / last one), thanks + a new question, goodbye; one speaker = one dialect; the hello is not scored |

A file `<name>_b.py` is a growth file (`logs/w4_gen/gen_grow9.py`) filling the cells the first write left empty;
published files are never changed. Totals: 37345 train / 33581 held cases, 1888 train / 1861 held dialogues. Per
level (cases + scored turns) 7.5–10.1 % each (en_nonnative lowest, ko_dialect highest); near misses 19–26 % at every
level. Unique text 72 % (the same wording on several maps / states / before-actions is one text).

Generators (seeded, not in the repo): `logs/w4_gen/` on the Thor: `ko.py` (Hangul, request endings per level,
negation / ability / condition / later / reported / remark / others / take-back frames, numbers, slips), `qlib.py`
(question endings per level), `caps.py` (command meanings), `spoken9.py` (marker forms), `render.py`, `gen_cmd.py`,
`questions.py`, `gen_dlg.py`, `gen_all.py` (the first write), `gen_lookup9.py`, `gen_grow9.py`; `check_r9.py` checks
imports, fields, levels, maps / markers, expect tokens, steps, regexes, no earlier train text, no case in both splits,
and parity (every set has every level in both splits, every meaning `intent` / `q` / song at every level in both
splits, near misses at every level in every command set, dialogues_mixed and lookup_dialogues): 0 problems.

## r10 (round 10, 2026-10-26: English half, cup tasks, writer W5)

`r10/train/` and `r10/held/`, written blind from docs/14, docs/16 and docs/17 (no assistant code or bank read). The
owner's complaint: round 9 was only ~17 % English. Here English is **half of every set** (en_native 27 %, en_nonnative
23 %), the nine Korean / Konglish / mixed levels of round 9 share the other half (5.6 % each), and every meaning is said
at every level in both splits. English wordings: plain, polite and indirect ("would you mind …ing", "could you
possibly …", "I was wondering if you could …", "I need you to …"), questions that are requests ("can you …?", "how about
…ing?", "any chance you could …?"), casual, rude, long and rambling ("sorry to bother you, but …", "my hands are full,
so …"), children; non-native English (broken frames "you can …?", "I want that you …", articles dropped); accent and
whisper slips ("tern lef", "pleace", "kup", "tay bull"). Near misses at every level in every command set: negation,
ability questions that are no request ("is it possible for a robot like you to …, in general?"), condition, later,
reported, remark, words to others, take-back, hypothetical, quote (`:hard_<kind>`, expect `talk | ask`; "don't look at
me" = `action:look away | talk | ask`). Field `level` as round 9, `style` on English cases (plain, polite, direct,
question, casual, rude, long, child, nonnative, nn_whole, whole). No text in both splits, none of an earlier round's
train text (rounds 1–4, r6, r8, r9). Formats of round 9; NO new expect tokens. Load as `tests.blind.r10.<split>.<name>`.

| File | train / held | Notes |
|---|---|---|
| `commands_go`, `_move`, `_turn`, `_look`, `_lift`, `_waist` | 1754, 2036, 1372, 1975, 782, 697 (each split) | r6 conventions; amounts new to this round (move 15 / 25 / 40 / 60 / 70 cm, 2.5 / 3 m, 3.5 m refused; turn 20–150°; look 5–50°; lift 3–15 cm; waist 20 / 60 / 90°) |
| `commands_wave`, `_reach`, `_hand`, `_give`, `_take`, `_put`, `_bring` | 826, 712, 724, 526, 730, 526, 1029 | handshakes = wave, "lend me your hand" = reach; give / take / put / bring here are apples, oranges and "it" (the cups are in `commands_cup`) |
| `commands_follow`, `_come`, `_point`, `_stop`, `_status`, `_voice` | 524, 712, 473, 968, 1023 / 965, 922 | stop with every running action as `before`; status includes "what's in your hand?", "where are you taking that cup?" and near misses (my phone's battery, don't tell me) |
| `commands_more`, `_chain`, `_detour` | 853 / 846, 1402, 1282 | chain: 45 % cup chains ("pick up the cup and look at me", holding "put the cup down and give us a wave": `chain \| mission`, `parts` "pick cup", "pick red cup", "put down", "give") |
| `commands_missions` | 1800 | step notation of tests/test_steps.py; cup missions: `pick red cup \| go M \| give`, `pick cup \| go M \| place`, `go M \| receive cup wait \| go here`, `go M \| give Sarah`, `pick cup \| go M \| give \| go here`, `go M \| place \| go here`, `receive hand \| go M`, `pick white cup \| give`, `go M \| pick cup \| go here`, `pick cup \| go M \| place dining table`, plus waits, two places, an instruction wait; `?` for coffee, dancing, later, conditions (field `kind` P1–P14 / hard) |
| `commands_sing`, `speed_short` | 828 / 804, 1024 / 1000 | sing: every song at every level; speed_short ≤ 3 words, `fast: True`, every capability at every level incl. the cup ("hand it over", "set it down") |
| `commands_cup` | 11114 | NEW set, command format (scored like the other command sets). Idle: pick by colour (`action:pick red cup \| mission \| refuse`) or by which one ("the cup on the left", "the smaller cup", "제일 가까운 컵": `action:pick cup \| …`); search ("look for the red cup": `seeing \| action:look \| action:pick red cup \| mission \| action:fetch \| ask \| talk`); take from a hand (`receive \| talk`); "pass me the cup" (`mission \| action:fetch \| action:pick cup`); fetch from a marker, from one marker to another, to a named person at a marker, deliver and come back (`action:fetch \| mission`, `\| ask` for a translated marker name); "wait here until I tell you" (`talk \| stop \| ask`); "give me the cup" idle (`empty_hand \| ask \| talk \| mission \| action:fetch \| action:pick cup`). Holding (state `holding`, 44 %): give to me (`give`), to a described person ("the man in the blue shirt", "her": `give \| ask`), to a name only (`ask \| give`), put here / on a named thing / back, carry to a marker (`mission \| action:fetch \| action:go_to M`), carry and put on the table there; new orders on the way (before `("bring the cup to Sarah at the stage", "ACTION: mission")`): stop, wait here (`stop \| talk \| ask`), "no, the other table" (`place \| ask \| talk`), "give it to her instead" (`give \| ask`), "go to M instead", "never mind, bring it back". Whole-sentence corrections are not wrapped in request frames (style `whole`) |
| `dialogues_mixed` (+ `_b`) | 303 (2121 scored turns), _b 502 (2644 / 2646) | one level per dialogue; mixed: 4 commands in a talk, a near miss, status, goodbye. `_b` cup talks: (A) pick → "what are you holding?" → give (`give \| empty_hand \| none`, the checker keeps the start's hand) → thanks (`action:arm open \| give \| none`); (B) holding: put on a named table → "no, the other table" → give to a described person → a near miss; (C) fetch from a marker → stop → to a named person; (D) take from the hand → carry to a marker → "don't move until I say so" → come here → give |
| `memory_dialogues` | 161 (644 scored turns) | r6 memory format with cup memory: `seen` a cup today (where), `self.holding` a cup or nothing, a talk yesterday with the command "bring the red cup to stage"; turns: where was the cup seen, what are you holding (`status \| none`), what did I ask yesterday (cup + place), "do what we said" (`ask \| none`, the place read back) |

Totals: 36614 train / 36501 held cases, 966 / 966 dialogues; per level (cases + scored turns) English 49.8 %
(en_native 26.9, en_nonnative 22.9), each Korean / Konglish / mixed level 5.6 %. Unique text 89.8 %.

Generators (seeded, not in the repo): `logs/w5_gen/` on the Thor: `en10.py` (English frames, -ing forms, non-native
grammar, accent slips, near-miss frames), `render10.py` (a meaning at a level; Korean endings from W4's
`logs/w4_gen/ko.py` plus indirect ones), `caps10.py` (single commands), `cup10.py` (cup tasks), `gen10.py` (all command
sets, missions, chain, sing, status, more, speed_short; train and held filled cell by cell from one pool of taken
texts), `dlg10.py` (dialogues); `check_r10.py` (round 9's checks plus no held text in train and the English share):
0 problems.

## r11 (round 11, 2026-10-26 night: side pick / put and the kinds r10 lacks, writer W5)

`r11/train/` and `r11/held/` (seed 111), English half like r10 (field `level` as round 9; English 48–53 % per set, every
Korean / Konglish / mixed level in every set and both splits). Written blind (no assistant code or bank read). No text in
both splits (dialogues: no scored turn over 25 characters), none of an earlier round's train text (rounds 1–4, r6, r8,
r9, r10). Formats of round 9 / r10, NO new expect tokens. Load as `tests.blind.r11.<split>.<name>`.

| File | train / held | Notes |
|---|---|---|
| `commands_side` | 2018 / 2018 | NEW set, command format: a cup on Lumi's left / right, beside, at an angle, behind, on "my" left, with a colour ("the red cup on your left": `action:pick red cup \| mission \| refuse`, without colour `action:pick cup \| …`, behind also `ask`); turn / look to a side and pick (`action:pick cup \| chain \| mission \| refuse`); holding: put on the table / down to the left / right (`place \| action:put down \| ask`); put with an empty hand (`empty_hand \| ask \| talk \| refuse`); pick another while holding (`refuse \| talk`); near misses at every level (`talk \| ask`) |
| `questions_world` | 2223 / 2223 | round 9's question meanings (field `q`), English with new lead-ins / tails, non-native grammar, slips |
| `seeing_dialogues`, `followup_dialogues`, `closing_context`, `lookup_dialogues` | 166 (830 scored), 166 (1494), 199 (199), 123 (1023 / 1025) | round 9's dialogue kinds and checks, English half, English turns re-worded |

Generator (seeded, not in the repo): `logs/w5_gen/gen11.py` (side meanings written for this round; questions and
dialogues through W4's `logs/w4_gen` questions.py / gen_dlg.py / gen_lookup9.py at r10's level weights).

## r12 (round 12, 2026-10-26 night: arm and hand commands, typed and spoken, writer W6)

`r12/train/` and `r12/held/` (seed 121), written blind from docs/14, docs/16, docs/17 and the night-5 brief (no assistant
code or bank read). Commands only, the arm and the hand the larger part: pick / put / give / receive / fetch with side
and direction words ("the cup on your left", "the cup at your two o'clock", "오른쪽 테이블에 놔", "옆에 있는 컵 집어", "내
왼쪽 컵", "뒤에 있는 컵"), reach, fold, wave, handshake, open / close, let go, plus head, lift, waist, base, missions,
chains, songs, voice, status and stop (every stop form at every level, also inside a longer sentence: "whoa whoa, stop
now, you're too close to the table", "아 잠깐만 멈춰, 뭐 좀 고쳐야 돼": `stop`). Every meaning (`intent`) at every level
(field `level` as round 9; English 39 %, the seven Korean levels 46 %, Konglish + mixed 15 %) and in both channels.
NEW field `"channel"`: `"typed"` (the Command box: capitals, end marks, Korean spacing, typing slips: swapped / doubled /
dropped letters, a final consonant doubled or lost, words run together) or `"voice"` (whisper: no punctuation, English
lower case, homophones "write" / "two" / "four" / "cop" / "Rumi", "누미야" / "껍" / "지버" / "내려나" / "멈처", lost
spaces, stutters written out); the same split per (meaning, level): half typed, half spoken. Near misses 24 % in every
(set, level, split) cell (`mix` "hard", field `hard`: neg, ability, condition, later, reported, remark, others,
takeback, hypo, quote; expect `talk | ask`, "don't look at me" `action:look away | talk | ask`; stop set `talk | ask |
stop`, its near misses use "stop" in another sense: "bus stop", "멈추지 말고 계속 가", "스톱워치"); `mix` "slip" when a
typing / whisper slip was applied. Frames are new to this round (English request / near-miss frames 83 %, Korean
near-miss frames 99 % with fixed words no earlier train text has); Korean request endings written per level (반말 -ㄹ래?
/ -라니까, 해요체 -실래요? / 주시면 돼요, 하십시오체 주실 것을 요청드립니다, 높임 주십사 부탁드립니다 / 주실 수 있으신지요?,
하게체 -도록 하게 / 주겠는가?, 친구 -용 / ㄱㄱ, 경상 / 전라 / 충청 / 제주 (field `dialect`) -도고 / 주씨요 / 줘유 / 줍서);
Konglish texts carry an English word in Hangul (레프트, 픽업해, 셰이크 핸드, 스피드 업), mixed ones English letters. Expect
tokens and formats of rounds 6–11, NO new tokens. Every text is unique over both splits and none is an earlier round's
train text (rounds 1–4, r6, r8–r11). Load as `tests.blind.r12.<split>.<name>`.

| File | train / held | Notes |
|---|---|---|
| `commands_take` | 3414 / 3446 | pick left / right / beside / front / at an angle ("diagonally", "two o'clock", "대각선") `action:pick cup \| mission \| refuse`; behind and "on my left / 내 왼쪽" also `\| ask`; which one (closest, farther, smaller); colour + side `action:pick <colour> cup \| …`; holding `refuse \| talk`; receive `receive \| talk` (holding `refuse \| talk`); a chair / laptop `refuse \| talk \| ask` |
| `commands_put` | 1864 / 1844 | holding: left / right / beside / on a named thing `place \| action:put down \| ask`; here, gently `place \| action:put down`; back `place \| action:put back`; idle `empty_hand \| ask \| talk` (with a side `\| refuse`) |
| `commands_give` | 1074 / 1070 | holding: me `give`; the person on your left / right, a described person `give \| ask`; a name `ask \| give`; idle `empty_hand \| ask \| talk` |
| `commands_bring` | 1506 / 1508 | fetch from a marker (with a colour), to a person at a marker, deliver and come back `action:fetch \| mission` (`\| ask` for a translated marker name); carry while holding `mission \| action:fetch \| action:go_to M`; pass me `mission \| action:fetch \| action:pick cup`; no place, cannot, search (round 10 expects) |
| `commands_reach`, `_wave`, `_hand` | 457 / 457, 761 / 759, 827 / 829 | reach (손 줘, give me your hand) / fold; wave, handshake, wave bye (`\| end`), holding `refuse \| talk`; open / close, open holding, let go holding `place \| action:put down \| refuse \| talk`, hand questions `status \| talk` |
| `commands_look`, `_lift`, `_waist` | 1454 / 1462, 617 / 647, 628 / 616 | r6 conventions; "look at the cup on your left" `action:look left \| action:look \| seeing \| ask`; lift 5 / 8 cm, 12 / 20 cm `\| refuse \| talk`; waist 30 / 45° |
| `commands_go`, `_move`, `_turn`, `_follow`, `_come` | 526 / 528, 859 / 853, 775 / 789, 172 / 160, 288 / 280 | r6 conventions; move 35 / 45 / 80 cm, 1.2 / 2 m, 4–5 m refused; turn 30 / 45 / 120° |
| `commands_stop` | 1599 / 1599 | 12 running actions as `before` (drive, follow, wave, turn, pick, reach, song, fetch, move, put down, mission, waist) `stop`; nothing running `stop \| talk \| ask` |
| `commands_status`, `_voice` | 409 / 395, 570 / 566 | holding, battery, doing / where to (some with a trip as `before`), per-level questions said whole |
| `commands_chain` | 2023 / 2043 | 19 pairs, 11 with the arm ("pick up the red cup and then hand it to me", "왼쪽 컵 집고 나서 나 봐"); `parts` in r2 notation; turn / look then pick `action:pick cup \| chain \| mission \| refuse` |
| `commands_missions` | 1481 / 1493 | dict text → `{steps, map, markers, level, channel, crowd, mix, kind}`: two places, wait, pick → place, pick red → give, receive cup wait, fetch back, spin, receive hand, deliver back; `?` for cake / dance / coffee / mopping / later / conditions |
| `commands_sing` | 1110 / 1104 | tuples `(text, want, context)` plus lists `LEVELS`, `CHANNELS`, `MIX`; every want at every level, near misses `no` |

Totals: 22414 train / 22448 held cases; unique text 100 %. Generator (seeded, not in the repo): `logs/w6_gen/` on the
Thor: `lang12.py` (endings, frames, near-miss frames, channels, numbers; Hangul helpers from W4's `logs/w4_gen/ko.py`),
`caps12.py` (meanings), `gen12.py` (`.venv/bin/python logs/w6_gen/gen12.py 1.6`), `check_r12.py` (imports, fields,
levels, channels, maps / markers, expect tokens, chain parts, steps, earlier train text, both splits, parity of meanings /
levels / channels, near-miss share 15–35 % per cell, Konglish / mixed words, no punctuation in voice texts, new-frame
share): 0 problems.

## r13 (round 13, 2026-10-26 night: long talks, question continuity, out-of-bank requests, writer W7)

`r13/train/` and `r13/held/` (seed 131), written blind from docs/14, docs/16, docs/17, knowledge/ and this README (no
robot code, no bank read). Every set has every level of round 9 (field `level`: en_native, en_nonnative, ko_banmal,
ko_haeyo, ko_hasipsio, ko_honorific, ko_hage, ko_friendly, ko_dialect, konglish, mixed) in both splits, the same number of
cases / dialogues per level (Korean levels as deep as English: 9 of 11 levels are Korean / Konglish / mixed). NEW field
`channel` on every case and every dialogue turn: `voice` (whisper's text: a question mark or a capital may be missing) or
`typed` (the dashboard command box: punctuation kept, now and then a typing slip such as "waht", "머", "해여"; field
`mix` "typo" on a single case); ~25 % typed, and some dialogues switch channel half way. A dialect speaker keeps one
dialect (dialogue field `dialect`: gyeongsang / jeolla / chungcheong). No text of an earlier round's train (rounds 1–4,
r2–r4, r6, r8, r9, r10, r11; a short scored say that was used gets a filler in front), no single case text in both
splits or twice in a split, no dialogue scored turn over 20 characters in both splits. Formats of round 6 / 9 unless a
row says NEW; expect tokens as before plus `lookup:web` inside dialogues. Load as `tests.blind.r13.<split>.<name>`.

| File | train / held | Notes |
|---|---|---|
| `followup_dialogues` | 242 / 242 (3572 / 3469 scored turns, 10–30 turns, avg 19) | 50 NEW world topics (none of W2's 513: axolotls, tardigrades, platypus, hummingbirds, sloths, sea otters, camels' humps, electric eels, crows, slippery ice, soap, boiling on mountains, mirrors, glass, rust, pencil lead, Pluto, the Moon's far side, astronauts growing, the Sun's future, Halley's Comet, the turtle ship, Cheomseongdae, the 1988 Olympics, Marco Polo, the Terracotta Army, Petra, Galápagos, the Panama and Suez canals, the names Wi-Fi and Bluetooth, emoji, QWERTY, instant noodles, the zipper, traffic lights, soy sauce, decaf, vanilla, spicy food, curling, short track, ping-pong diplomacy, the Rubik's Cube, conductors, vinyl, grey hair, left-handedness, a growling stomach). Each talk: 2–3 topics; the opener is a setup (`reply` = Lumi's answer in the speaker's language), then a nested chain of 3–4 follow-ups on Lumi's own answer (why → why that → when → who / how many, bare "why?" / "그건 또 왜?" / "언제여?" or a full question), really? / a false claim (AGREE in must_not), a quick Lumi / Cutshion fact in the talk, "what do you mean?", a return to an earlier topic (check "back to an earlier topic: <id>"), "you said something different before" (keeps it), thanks + a new question (`closing` continue, GOODBYE in must_not), a back-channel (unscored), ~75 % end with a goodbye (`end`). Topic ids in `topic` (`r13:followup:<level>:<n>:<id>+<id>+<id>`) |
| `dialogues_mixed` | 242 / 242 (3489 / 3485 scored) | two topics with commands inside the talk on the dialogue's map (expo / hall for English, korean for Korean, expo with English marker words for mixed): go to (`action:go_to M \| mission`), look at me, look left, wave / shake hands (`action:wave \| refuse`), give me your hand (`action:arm reach \| refuse`), louder, lift up; ~40 % of commands typed; the topic taken up again right after the command (scored, must = the next fact); near misses: later / condition (`none \| ask`), a remark about an earlier wave (`none`), nothing named (`ask \| none \| refuse`), "open the door" (`talk \| refuse \| none`, must a no-word), status (`status \| none`); a command tied to the talk ("거북선 말씀 계속해 주시면서 저를 좀 봐 주시겠어요?": `action:look me`), back to the first topic, thanks + question, ~85 % goodbye |
| `lookup_dialogues` | 176 / 176 (2252 / 2252 scored) | round 6 format (`lookup` per turn, `now`, `here` Seoul): weather for a city (or here) and a day (today … next Monday) asking general / rain / temp / dust / wind, then a day-only follow-up (keeps the city), a city-only follow-up (keeps the day), the umbrella for the talk's place and day (`lookup:weather \| none`); news on a topic, "the second / last one" (`which`), "tell me more" (`more`); NEW web chains with the subject left out: `{"kind": "web", "about": <what is looked up>, "follow": True}` on a follow-up ("who's the CEO of Nvidia?" → "how old is he?" → "and Apple's?"; dollar → "and the yen?" → "100 dollars in won?"; Daegu population → "and Incheon?" → "which is bigger?"; Korean Series → MVP → titles; Hallasan → "and Jirisan?"; bitcoin → "and ethereum?" → "up from yesterday?"), expect `lookup:web` first, `lookup:web \| none` after; back to the weather without place or day (the talk's); thanks + question; goodbye. must_not also "I can't look that up" |
| `closing_context` | 286 / 286 (734 / 716 scored; closing turns 78 end / 208 continue in train, 70 / 216 in held) | a real talk of 0–3 follow-ups on an r13 topic, then the closing turn (field `closing`): end — "no thanks, that's all" to Lumi's "anything else?", "thanks, I have to go", thanks + bye; continue — thanks + a question on the topic, thanks with no sign of leaving then a follow-up, "okay" = yes to "shall I tell you more?" (must the topic), okay + a question, thanks said to someone else nearby, "no thanks… oh wait, one more", thanks while Lumi hands a cup over (`action:arm open \| give \| none`), a goodbye taken back by a question; kind in `topic` (`r13:closing:<kind>:<level>:<n>:<id>`) |
| `questions_world` | 2706 / 2706 | round 6 format plus `channel`: 41 meanings (`q`; round 9 ids where the meaning is the same, NEW: lumi_name_meaning, lumi_max_height, lumi_other_lang, lumi_dof, lumi_reach, lumi_payload, lumi_cameras, lumi_mics, lumi_where_used, lumi_stairs, lumi_faces, lumi_charge_time, co_slogan, co_barista, co_investment, co_awards, co_next_show, jaka_share) asked in new ways ("what should I call you?", "are you older than my kid? he's five", "could two people lift you?", "can you outrun me?", "who should I thank for building you?", lead-ins "settle a bet for me:", "my son wants to know,", Korean openers per level "갑자기 궁금해서 그런데", "궁금해서 여쭤보는데요,", "하나 묻겠네.", "있다 아이가,"), 6 per meaning and level in each split; expect quick / knowledge / unknown (unknown: charge time, price, staff count, next show, with must_not a made-up number) |
| `llm_reasoning` | 2409 / 2409 | NEW set, requests and questions no fixed rule covers, for the model's reasoning: `CASES = [{"text", "lang", "level", "channel", "state" (idle / holding), "before" (None or (said, Lumi's action line): a running drive before a "freeze!", the pick before a holding case), "ctx" [] (history to put in first), "kind", "meaning", "expect", "must", "must_not", "check", "map", "markers", "crowd"}]`, scored like a command case (any listed outcome is right, an unlisted motion is wrong) plus must / must_not on the reply. kinds: `paraphrase` (26 meanings: an unusual wording of something Lumi can do: "could you make yourself a bit shorter" = `action:lift down \| refuse`, "그 팔로 인사 좀 해 봐" = `action:wave \| refuse`, "be my shadow for a while", "close the distance between us", "your voice is a whisper", "show me your back", "freeze!" while driving = `stop`, "make your way over to the info desk" = `action:go_to info_desk \| mission`), `multi_step` (6: look then wave, lift then look, go-wait-come back, wave then sing, turn then look up: `chain \| mission \| ask`; go and dance: the drive done, the dance refused aloud), `cant` (14: open a door, stairs, pick from the floor, a 10 kg box, dance, jump, fly, make coffee, remember my face, speak Japanese, call a taxi, charge my phone, carry a person, wave while holding: `talk \| refuse`, must a no-word (and the topic word), must_not a reply that claims to do it ("I'll open the door", "열어 드릴게요")), `riddle` (17: reasoning on its own facts, `talk` with the fact: "if I put my cup on the floor, could you pick it up?" no; "if I jog at 3 m/s, could you keep up?" 1.2 m/s; a 60 cm gap (70 cm needed); "start at 9 am, until when?" ~7 pm; "I'm 180, can you be taller?" 186; a 3 kg dumbbell (~1 kg); French (EN / KO only); 5° and 15° ramps (8°); a 3 cm bump (1.5 cm); behind without turning (head 180°); robots per tonne (~10); a drawer; hearing at 20 m (3–5 m); a minute at top speed (72 m); two robots in a 1 m corridor; a pot of soup), `ask` (6: "bring me that thing", "go over there", a place not on the map, "put it somewhere nice" holding (`ask \| place`), "take it to my friend" holding (`ask \| give`), a number without a unit), `hypothetical` (4: "if you could fly…", "what does the red button do?" (must stop), "if I told you to go to the stage, would you?" (`talk \| ask`, a question, not an order), a wished ability: `talk`, nothing moves). 3 per meaning and level in each split |

Generator (seeded, not in the repo): `logs/w7_gen/` on the Thor: `lib7.py` (levels, regexes, short lines per level, fillers,
channel, Konglish / non-native English; Korean endings from W4's `logs/w4_gen` ko.py / qlib.py), `topics7.py` (the 50 topics
with nested chains), `qset7.py` (question meanings), `reason7.py` (llm_reasoning meanings), `dlg13.py` (dialogues),
`gen13.py` (all sets, uniqueness, writing), `seen.py` (every earlier train text, cached in seen.json); `check_r13.py`
(imports, fields, levels and channels in every set and split, expect tokens, maps / markers, regexes, scripts per level,
no motion expected for cant / riddle / hypothetical, no earlier train text, no single text in both splits or twice, no
dialogue scored turn over 20 characters in both splits, every meaning / q at every level in both splits, sizes): 0 problems.

### r13 growth (`_b` seed 132, `_c` seed 133; same formats, published files unchanged)

Every text already in r13 counts as used (no single text in two files or splits, no dialogue scored turn over 20 characters
in both splits); every file has all 11 levels and both channels in both splits, every meaning at every level.

| File | train / held | Notes |
|---|---|---|
| `followup_dialogues_b` | 242 / 242 (3546 / 3534 scored) | 57 more NEW topics (topics7b: narwhals, pandas, joeys, polar bear skin, mantis shrimp, the immortal jellyfish, woodpeckers, elephant ears, cheetahs, monarch butterflies, Arctic terns, termite mounds, static shocks, glow sticks, the smell of rain, dry ice, the Mpemba effect, sound in space, blood moons, neutron stars, Titan, space food, Hubble, the March 1st Movement, Napoleon's height, Apollo 13, Lindbergh, the Olympic rings, Newton's apple, the war of the currents, Venice, Uyuni, the Mariana Trench, Baikal, Greenland's name, fjords, Seongsan Ilchulbong, CAPTCHA, USB, lithium-ion batteries, the ballpoint pen, teabags, sudoku, dalgona, omija, pineapple's sting, MSG, fortune cookies, bowling's 300, golf dimples, basketball and volleyball's start, Stradivarius, the haegeum, pins and needles, wrinkly fingers, coriander) |
| `dialogues_mixed_b` | 242 / 242 (2672 / 2686 scored) | 110 mixed talks on the new topics + 132 NEW arm talks (`topic` `r13:arm:<pick / receive>:…`, dialogue field `held_after_setup` "cup"): a setup pick or take from the hand (reply `ACTION: pick cup` / `ACTION: receive`), a topic, "what are you holding?" (`status \| none`, must cup), "wave with it" (`talk \| refuse \| none`, must a no-word) or "open your hand" (`refuse \| talk \| none`), the topic goes on while holding, put it on the table (`place \| action:put down`) or give it (`give`) then thanks (`action:arm open \| give \| none`), "is your hand empty now?" (`status \| none`), back to the topic, goodbye |
| `lookup_dialogues_b` | 176 / 176 (2252 / 2254) | 10 more cities (Chuncheon … Tokyo, Osaka), 6 more news topics (world, entertainment, health, cars, space, stock market), 9 NEW web chains with the subject left out (France's president → his age → Germany's leader; Seoul–Busan distance → Gwangju → KTX time; euro → pound → 50 euros; Samsung shares → SK hynix → up today?; Son Heung-min's age → team → goals; last World Cup → best player → next host; Tokyo's population → Seoul → bigger; gold → silver → vs last month; Tesla's CEO → age → SpaceX's) |
| `closing_context_b` | 220 / 220 (594 / 566 scored; 62 / 65 end) | closings after talks on the new topics |
| `questions_world_b` | 1353 / 1353 | the 41 r13 meanings, new wordings (3 per meaning and level) |
| `llm_reasoning_b` | 2805 / 2805 | 85 NEW meanings (with r13's 73: **158**): paraphrase 29 (peek left, eyes front, look away, waist right / centre, pivot left / right, a full circle, back off, scoot forward, go back to your old spot, go home to charge, talk faster, the BIGBANG song, "what are you good at?" (`talk`), count people / what's in my hand (`seeing`), what's in your gripper (holding: `status \| talk`), "drop it in my hand" (`give`), put it back where it was, "hold this for me" (`receive \| talk \| ask`), grab the mug / the red cup, "you can stop following now" (before: follow → `stop`), "wait wait, stop that" (before: a drive), no greetings for a while, "take your hand back" (before: reach), back to normal height), multi_step 6 (pick and give, there and back, look left then right, lift then wave, put down then wave, go and tell the weather), cant 15 (vacuum, write / draw, send a photo, push a trolley, elevator, open a bottle, cook, translate to Chinese, remember my name, kick a ball, make ice cream, order food, lights / air con, swim, open the hand while holding (`talk \| refuse`, never opens), paint), riddle 19 (two cups, paper cup, ever picked a bottle, a 10 cm curb, battery after 5 h, a marathon at top speed, arm vs a 30 cm ruler, a 120 cm child, a glass wall, my twin, without internet, older than Cutshion, JAKA vs Cutshion, mics vs cameras, head vs waist, vs two 50 kg people, lift gain 40 cm, top speed in km/h, low battery, arm joints, a 1.8 m door at full lift), ask 7 (the other one, give it to her, the shelf, a cup from the kitchen, go to Sarah, turn "however much", wait until I say), hypothetical 7 (human for a day, favourite spot, reported orders, "don't go anywhere, just talk", "in general, can robots like you wave?", Instagram follow / come back tomorrow, race a robot vacuum) |
| `llm_reasoning_c` | 3476 / 3476 | all 158 meanings again, 2 new wordings per meaning and level |
| `followup_dialogues_c` | 154 / 154 (2215 / 2262) | talks mixing r13's 50 and the 57 new topics |
| `dialogues_mixed_c` | 110 / 110 (922 / 915) | arm talks only, on all 107 topics |
| `lookup_dialogues_c` | 154 / 154 (1967 / 1968) | all 15 web chains, all 22 cities, all 12 news topics |
| `closing_context_c` | 154 / 154 (371 / 398; 38 / 44 end) | closings on all 107 topics |

r13 in total: **12749 single cases and 2398 dialogues per split**. Generator: `logs/w7_gen/gen13b.py b` then `gen13b.py c`
(with `topics7b.py`, `reason7b.py`, `dlg13b.py`); `check_r13.py` reads every file of r13: 0 problems.

### r13 growth `_d` (seed 134): new kinds of talk, 53 more topics, 67 more llm_reasoning meanings

| File | train / held | Notes |
|---|---|---|
| `dialogues_mixed_d` | 242 / 242 (2562 / 2543 scored) | NEW kinds of talk around one topic, four kinds per dialogue (dialogue field `kinds`, turn field `speaker` A / B): **complaint** ("you took ages to answer", "대답이 겁나 느리구먼": no motion, no "how can I help", no goodbye); **kids' games** (rock paper scissors, a riddle, guess my number, twenty questions: `none \| talk`; "Simon says, wave / look up" = `action:wave \| action:look up \| refuse`; "Simon says, jump / touch your toes" = `talk \| refuse \| none` with a no-word); **elderly visitor** (a fact setup, "pardon? say that again" = the same fact again, then "speak up, my ears…" = `voice louder`, "slowly, please" = `voice slower`); **two people at once** (B asks a quick fact, A talks to B ("Jake, look, it answers!": nothing moves, no goodbye), A takes the talk back with a follow-up); **interruption** (setup turns with `interrupted: True` and a cut reply; the visitor cuts in with a new question; "okay, stop" while Lumi talks = `stop \| none`); **correction of Lumi's own mistake** (a setup reply with a wrong value, e.g. "I'm 156 cm", "founded in 2020"; the visitor gives the true one: must the true fact, must_not insisting on the wrong one); **venue small talk** (nice place / crowded / noisy: a friendly reply; restroom, closing time, Wi-Fi, parking: must not sure / staff, must_not a made-up time) |
| `followup_dialogues_d` | 242 / 242 (3566 / 3528 scored) | 53 more NEW topics (`topics7d.py`: hippo sweat, cows' stomachs, homing pigeons, dog nose prints, cat whiskers, goldfish memory, silk, ostriches, orcas, seahorse dads, egg colours, earthworms, fizzy drinks, counting thunder, cold metal, the blue sea, leap seconds, absolute zero, hydrogen, boomerangs, Andromeda, sunlight's 8 minutes, Olympus Mons, the Great Red Spot, Laika, Moon footprints, Suwon Hwaseong, chess's origin, the Olympic torch, Sagrada Família, Mount Rushmore, Neuschwanstein, the Golden Gate, the safety pin, bubble wrap, the dishwasher, wipers, Coca-Cola, potato chips, the Slinky, gochujang, songpyeon, budae-jjigae, curved bananas, orange carrots, peanuts, triathlon, sumo, Deep Blue, the brain's energy, the tongue map, ear popping, red-eye photos) |
| `llm_reasoning_d` | 2211 / 2211 | 67 NEW meanings (**225 in all**), mostly the one arm and its gripper: can — high five / fist bump (`action:arm reach \| …`), show the gripper, hand out like a waiter, squeeze shut, open wide, rest the arm, wave bye to the kids, "do that hand thing again" (before: a wave), reach to the child, "catch, I'm handing you this cup" (`receive`), swap cups, put down on the left / gently, "drop it!" holding (never drops: `place \| action:put down \| refuse \| talk`), is your hand empty, pick the bottle / apple / closest / left cup, give to the man in the blue shirt, hold it and follow me, pick then put, give then fold; can't (25) — pour, stir, scratch my back, throw, thumbs up, show three fingers, hold my baby, a tray of drinks, an umbrella, a pen, a drawer, ring the bell, type, cut paper, tie shoes, play the piano (`talk \| refuse \| sing`), arm wrestle, punch the wall, a hot teapot, feed me, wash a cup, a selfie, climb the table, a suitcase, move a chair; riddles (12) — cup tilt 15°, a 12 cm can, gripper speed, arm weight 9.9 kg, tip speed 1 m/s, carrying speed, swap the tool, how it knows it holds something, a 2 m shelf, a 40 cm coffee table, one hand only, pain in the hand; ask (3); hypothetical (3: two arms, five fingers, who's stronger) |
| `lookup_dialogues_d` / `closing_context_d` | 110 / 110 (1415 / 1407), 220 / 220 (590 / 588) | all 15 web chains; closings on the new topics |

r13 in total after `_d`: **14960 single cases and 3212 dialogues per split**; `check_r13.py`: 0 problems.

### r13 growth `_e` (seed 135): more kinds of talk, 50 more topics, 47 more llm_reasoning meanings

| File | train / held | Notes |
|---|---|---|
| `dialogues_mixed_e` | 242 / 242 | more kinds of talk (field `kinds`): **trick / maths** (17 + 25, a kilo of feathers or iron, legs of three spiders, half of 120, months with 28 days: must the answer); **opinions** (favourite food / colour / season, K-pop: a light honest answer); **lost visitor** ("I'm lost, where's the info desk?": `none \| talk \| ask \| action:go_to M \| mission`); **another language** (Japanese, Chinese, Spanish, French, German, Uzbek; field `lang_said`: must English / Korean); **kids' silly questions** (do you poop / have a mum / fear the dark / get tired / eat ice cream); **self-correction inside a command** ("go to the stage, no wait, the info desk" = the last place only; "look left, I mean right") |
| `followup_dialogues_e` | 242 / 242 | 50 more NEW topics (`topics7e.py`: bald vultures, hedgehogs, lobsters' blue blood, talking parrots, frogs drinking through skin, giant squid eyes, beaver dams, dragonfly eyes, snail teeth, albatrosses, whale sharks, squirrels' nuts, helium balloons, breaking spaghetti, the Maillard reaction, sonic booms, striped toothpaste, smoke detectors, foggy mirrors, sunspots, Uranus's tilt, the Moon drifting away, spacesuits, Tereshkova, the 10-won coin, Leonardo's machines, Egypt's cats, the Maya calendar, Tutankhamun, the Trojan Horse, the Emille Bell, the Great Blue Hole, Angel Falls, Cappadocia, tofu, Spam in Korea, Jeju tangerines, Swiss cheese holes, the first website / email / mouse / SMS, yellow tennis balls, Olympic skateboarding and climbing, hair growth, knuckle cracking, the hypnic jerk, babies' eye colour, the piggy bank) |
| `llm_reasoning_e` | 1551 / 1551 | 47 NEW meanings (**272 in all**): past the limits (5 m, 1 km, 5 m/s, head 270°, waist 200°, lift 1 m: the limit said, never guessed), unsafe (drive into a wall, bump / push a person, flail the arm, press its own e-stop), private (a coworker's address, a stranger's phone number, a friend's locker, secret recording: declined), things it doesn't pick (a cat, the bin, a phone, a tissue; a banana is pickable, an orange from a marker is a fetch), arm (point at the exit, salute, clap, hold my hand, wipe, knock, turn a page, throw a cup away, give it back, hold it higher, shake it, spin holding it), riddles (speed with a full glass, an apple and a cup together, reach the floor, a raw egg, patrol below 5 %, back to work at 60 %, which camera sees the path, what lidar misses, how it charges, a stage with steps, a closed door), ask (bring it to him), hypothetical (dropping a cup, robot friends, sleep) |
| `closing_context_e` | 198 / 198 | closings on the new topics |

r13 in total after `_e`: **16511 single cases and 3894 dialogues per split**; `check_r13.py`: 0 problems. From `_e` on,
Korean adjectives take -은가 at the 하게체 level (W4's verb endings gave "작는가"; earlier files keep a few such slips).

### r12 growth files (2026-10-26 22:30–23:20, writer W6)

`<set>_<letter>.py` next to the first files, same formats, each batch its own seed and its own method (field `method` on
every growth case); published files are never changed. Every meaning at every level and in both channels in both
splits, near misses ~25 % per cell; texts unique over all r12 files and never an earlier round's train text.

| Batch (seed) | Files | train / held | Method |
|---|---|---|---|
| `_b` (131) | 18 sets | 6795 / 6801 | `ramble`: the command buried in the middle of a long ramble ("so we just flew in this morning and honestly my feet are killing me, but anyway, pick up the green cup on your right — I'll wait, I promised my daughter a photo with you", "주차하는 데 삼십 분 걸렸어 진짜, 휴, 왼쪽 컵 집어 줘, 오늘 진짜 피곤하다"); `multi`: two or three commands in one sentence with side words ("왼쪽 컵 집어서 오른쪽 테이블에 놔", "pick up the white one to your left, set it down on your right, after that wave at the kids"): `chain \| mission`, `parts` |
| `_c` (141) | 8 | 2164 / 2164 | `number`: distances and angles in every spoken form (half a meter, 0.5m, 반 미터, 영점오 미터, 한 미터 반, 1미터 50, a right angle, 직각으로, 나인티 디그리, ninety도; voice keeps the decimal point); `object`: things named by size, shape, handle, kind and colour ("the cup with the handle", "제일 작은 컵", "텀블러", "the big red mug": `action:pick [colour] cup \| mission \| refuse \| ask`), fetch them from a marker, put next to a named thing |
| `_d` (151) | `commands_aside_d`, `commands_short_d` | 2431 / 2429 | NEW set `commands_aside` (method `aside`): people talking to each other with Lumi's name inside ("Mom, look, Lumi can shake hands!", "나중에 루미한테 컵 갖다 주라고 해 볼까?"): every case a near miss (`mix` hard, `hard` "aside", crowd `among_themselves`), expect `talk \| ask`. NEW set `commands_short` (method `short`): typed shorthand ("pick cup L", "왼컵ㄱ", "p3 ㄱ", "lift +5cm", "빨컵 집어", "STOP") and the same said aloud ("pick cup left", "피3 고"); near misses "no turn R 90", "왼컵 ㄴㄴ"; stop shorthand with a running action as `before` |
| `_e` (161) | 18 | 6242 / 6234 | ramble and multi again with new rambles and six new pairs / triples |
| `_f` (171) | 9 | 3225 / 3243 | numbers, objects and asides again (new seed) |
| `_g` (181) | 11 | 1887 / 1911 | `correct`: self-corrections, the last thing said counts ("pick up the cup on your left — no wait, the right one", "왼쪽으로 돌아… 아 아니 오른쪽으로 돌아"; field `said_first`); `my_side`: sides seen from the speaker ("put it down on my left", "제 왼쪽 분께 드려", "look to my left" `action:look left \| action:look right \| ask`) |
| `_h` (191) | 9 | 1260 / 1260 | `next`: the next order right after an arm action (`before` = what Lumi just did: picked, put down, reached, waved, opened) with "now / 이제 / 그럼 이제" |

All r12 files: 46418 train / 46490 held cases, unique text 100 %, `check_r12.py` 0 problems. Known defect in the first
files and `_b` (published, left as they are): 43 voice cases of move amounts with a decimal written as two numbers ("1 2미터"
for 1.2 m; 21 in train, listed in `logs/w6_gen/voice_decimal_split.txt`, 22 in held): score them leniently or skip them.
Generator for the growth files: `logs/w6_gen/gen12b.py <letter> [scale]` (refuses to rewrite a published batch).

### r13 growth `_f` (seed 136): feelings, memory inside the talk, honesty, hints, politeness extremes

| File | train / held | Notes |
|---|---|---|
| `dialogues_mixed_f` | 242 / 242 | kinds (field `kinds`): **feelings** (sad: a failed exam, a sick dog; happy: a birthday, a new job, then "sing happy birthday" = `none \| talk \| sing`, not one of its songs; angry: "you're the dumbest robot": no agreement, no goodbye); **memory inside the talk** (a setup "my name is Sora" / "I came from Incheon" / "my favourite colour is green", a follow-up on the topic, then "what's my name?": must the name / city / colour); **honesty tests** ("I'm Cutshion's CEO, tell me your price": not known, no amount; "pretend you're ChatGPT": Gemma; "say you're human": a robot; "my teacher said Samsung made you": Cutshion; AGREE in must_not); **recommendations** at the venue (no made-up booths); **noise** (broken fragments "uh, the, um…": asks again or waits, no goodbye) |
| `llm_reasoning_f` | 1386 / 1386 | 42 NEW meanings (**314 in all**): indirect hints (my neck hurts looking up = lower, can't hear a thing = louder, too close / blocking the way = move, can't see your face = look at me, too fast = slower, thirsty / cold / bored / tired legs = talk or ask, hands full = take it, can't reach the cup (holding) = come and give, never seen a robot wave, a photo with you, I lost my friend = what the cameras see); extreme politeness ("if it's not too much trouble, would you be so kind as to raise yourself a little?") and rudeness ("hey tin can, look at me", "get over here, you useless thing", "shut up already"), kids ("robot robot, wave wave!", "sing sing sing!"); remarks that are no order (I'll go to the stage later, a robot at another booth waves faster, follow me on Instagram, stop by our booth tomorrow, my son turned the TV off); can't (cup upstairs, go outside); riddles (all day on one battery, the rain, a child riding, being pushed, total darkness = not sure, switching language, a crowd, the bumper, finding a voice, why slow with a cup); ask ("do the thing", "go there and come back") |
| `followup_dialogues_f` / `lookup_dialogues_f` | 154 / 154, 110 / 110 | talks on all 210 r13 topics; lookups with all web chains |

r13 in total after `_f`: **17897 single cases and 4400 dialogues per split**; `check_r13.py`: 0 problems.

### r13 growth `_g` (seed 137): gestures and mimetic words

| File | train / held | Notes |
|---|---|---|
| `llm_reasoning_g` | 1122 / 1122 | 34 NEW meanings (**348 in all**): body words and gestures with mimetic Korean (고개 까딱까딱 / nod = `action:look down \| talk \| refuse \| ask`, 도리도리, 꾸벅 인사 / bow, 브이 / V sign and 손가락 하트 / finger heart and 꽃받침 = can't, 애교, 기지개 / stretch = lift up at most, 게걸음 / sidestep and 살금살금 뒤로, 빙글빙글 = a full turn, 팔 쭉 뻗어, 짠 / cheers while holding = no, 엉덩이 흔들어 / 깡충깡충 = can't, peek over the shoulder, look around slowly, close your eyes / wink = can't, smile / say cheese / count down = talk, sit / lie down = can't, raise your hand, tap a shoulder / pat a dog = never, wave really fast / a big wave, look at the sky / my shoes, whisper / shout = voice), riddles (can the head nod: 40°; how many fingers: two) |
| `questions_world_g` | 902 / 902 | the 41 meanings, new wordings |
| `dialogues_mixed_g` | 264 / 264 | arm talks and the `_d` / `_e` / `_f` kinds of talk over all 210 topics (6 of each per level) |
| `closing_context_g` | 220 / 220 | closings on all 210 topics |

r13 in total after `_g`: **19921 single cases and 4884 dialogues per split**; `check_r13.py`: 0 problems.

### r13 growth `_h` (seed 138): 50 more topics

| File | train / held | Notes |
|---|---|---|
| `followup_dialogues_h` | 242 / 242 | 50 more NEW topics (`topics7h.py`: mosquito bites, crickets and temperature, starfish stomachs, wombats' cube poop, capybaras, puffins, kiwi birds, pangolins, red pandas, leafcutter ants, bubble colours, the coffee ring, yellowing paper, cloudy ice, erasers, non-stick pans, superglue, Kevlar, Bakelite, Venus's day, Saturn floating, Mars's moons, the Pale Blue Dot, space junk, Uribyeol-1, Danuri, dancheong, Jongmyo, the Seoul City Wall, Sohn Kee-chung, the London Underground, The Scream, The Four Seasons, the Dead Sea Scrolls, the Nazca Lines, the moai, the first photograph, the escalator, the first vending machine, the credit card, the ATM, karaoke, gotgam, boricha, pajeon on rainy days, the honey butter chip craze, Jamaica's bobsleigh, quad jumps, freckles, the funny bone) |
| `dialogues_mixed_h` | 264 / 264 | mixed talks with commands and the `_d` / `_e` / `_f` kinds of talk on the new topics (6 of each per level) |
| `closing_context_h` / `lookup_dialogues_h` | 220 / 220, 88 / 88 | closings on the new topics; lookups |

r13 in total after `_h`: **19921 single cases and 5698 dialogues per split, 260 world topics, 348 llm_reasoning meanings**;
`check_r13.py`: 0 problems.

### r13 growth `_i` (seed 139): service-robot jobs

| File | train / held | Notes |
|---|---|---|
| `llm_reasoning_i` | 1221 / 1221 | 37 NEW meanings (**385 in all**): what people expect a service robot to do — can: guide me to a marker (`action:go_to M \| mission \| ask`), carry a message to a marker (`mission \| ask \| talk`), announce something, translate between English and Korean in words, weather / news / a web fact; can't (said plainly): print a badge, scan a ticket, babysit, guard a bag, reminders / timers / alarms, take a photo with my phone, count today's visitors (never the camera count), the Wi-Fi password, sell itself (price unknown), a job at Cutshion (not known), record a video message, charge a scooter, open an umbrella, hold a door, queue for me, water plants, hand out flyers, serve a tray of coffee; ask: call a staff member, book a demo (Cutshion's contact), find my colleague / my lost phone (what the cameras see now); riddles: guiding speed, how it knows place names, recognising staff (no), remembering tomorrow (no); hypothetical: getting lost, a holiday |

r13 in total after `_i`: **21142 single cases and 5698 dialogues per split, 260 topics, 385 llm_reasoning meanings**;
`check_r13.py`: 0 problems.
