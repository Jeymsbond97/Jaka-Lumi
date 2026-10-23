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
