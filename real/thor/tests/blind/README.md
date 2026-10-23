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
