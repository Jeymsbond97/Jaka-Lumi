# 17 Missions: commands of several steps

A mission is one command, typed in the dashboard's Command dialog or spoken, that Lumi turns into a list of steps,
reads back, and runs after a yes. Examples:

- "take the cup, go forward 0.5 m, then right 1 m and put it on the table"
- "take the cup, go to final, give it and say: Anvar says hello"
- "go to p9, ask them for the cup, then bring it to p1"
- "bring it to p3, p5 or p7" (one of them, chosen at random when the mission starts; only "or", "one of", "중" make a
  choice: "go to p1 and p2" is two drives)
- "put it on the white table on your left"
- "go to p2, wait 2 minutes, then come back home", "go to p9 and wait until someone gives you a cup, then bring it to
  p1", "go to p6 and do what they tell you", "p3에 가서 기다려"
- "컵을 들고 앞으로 0.5미터 가서 오른쪽으로 1미터 가고 테이블에 놔"

Commands are English or Korean only. A part Lumi can't read is never guessed: it says which part it did not
understand ("I didn't understand: dance") and nothing runs. Conversation (questions, date, weather, greeting) stays
as it is (docs/14); a single move / turn / arm command by voice keeps its fast path without a read-back. A plain fetch
("bring me the apple from p1") still goes the fetch way (docs/16).

## 1. Steps

| Step | Fields | Done by (`tasks/fetch.py`) |
|---|---|---|
| `go` | `to`: a marker, `"here"` (where the command was given), or a list (one of them at random) | `_drive_to` |
| `move` | `dir`: forward / back / left / right, `m` (`MOVE_MIN_M` … `MOVE_MAX_M`) | `_move`: left / right = `_turn(±90)` (arm sweep checked) then forward; at `LIFT_DRIVE_MM`, in `MOVE_SEGMENT_M` pieces at `MOVE_SPEED`, before each piece the base's way (`_straight_clear`) and the arm's (`line_hits`) checked again with the live lidar, a held object checked after it; stopped short = the mission fails with the reason. On the charger: forward allowed (the way is checked), back refused |
| `turn` | `deg` (+ left), ±360 all the way round | `_turn` (arm sweep checked; not on the charger); 360°: two half turns, each checked (a 360° goal is the start pose to the base) |
| `pick` | `object`, `colour` | `_pick_here` (the look / reach / pick part of a fetch) |
| `receive` | `object`, `from_hand` (optional) | `_receive`: arm to `give`, hand open, "Please put the cup in my hand, let go, and say okay."; the hand closes **only on that word** ("okay", "done", "thank you", "됐어", or Release in the dashboard), never while fingers may be in it. DI_1 (below the gripper, docs/10) seeing something for `RECEIVE_DI_S` only makes Lumi say "Let go of it, then say okay." After the close AI_1 must say holding; closed on nothing: hand open, "My hand closed on nothing, there was nothing to take.", failed. Nothing put in, or no okay, within `RECEIVE_WAIT_S`: back to look, hand open, failed. `from_hand` ("take this from my hand"): `scene.person_holds()` False → "I don't see anything in your hand.", nothing moves (can't tell: goes on); then from `give` the open hand moves straight towards `scene.object_in_hand()` at give's height, at most `RECEIVE_REACH_MM`, stopping `RECEIVE_SHORT_MM` before it (IK-checked; not seen: stays at give). Not live |
| `say` | `text` (the command's own words) | spoken as written |
| `place` | `on`: null or {`name` (camera class), `colour`, `side`, optional `alts` ("the table or chair"), `prefer` ("the lower one")} | a `side`: turn 90° that way first (checked); a named thing, a table with a colour or "which one": `_put_on` (exactly that thing first, else the surface seen that comes closest to what was said, said aloud; docs/16 9a); else `_put_down` (any free table spot). One search, then straight to what was seen |
| `give` | `person` (optional: "bring it to James at p6", "p6에 있는 제임스한테 갖다줘"; who it is for, see §4) | `_give` (opens on "thank you" / Release; nobody takes it = failed, still holding) |
| `hold` | – | nothing: the mission ends holding |
| `arm` | reach / fold / open / close | reach = the `give` pose, fold = `look`, open / close = gripper |
| `wait` | `s`: seconds | `_wait`: waits there ("waiting at p3"); time someone talks to Lumi (pause) does not count; "go on" ends it early |
| `wait` | `s`: null | at the end of a mission ("go to p3 and stay there"): the mission ends there, status `waiting` (step "waiting at p3"); any new command or Stop is taken as usual. In the middle ("go to the exit, wait there, then go home"): waits until someone says "go on" / "you can go" (`fetch.proceed`), or Stop. No time limit |
| `wait` | `s`, `until: "instruction"` | waits there for the person at the place to say what to do (§4), at most `s` (`WAIT_ORDER_S` when no time is said); their command is read back, a spoken yes, done there ("here" in it = that place), then the rest of the mission. Nobody: "Nobody told me what to do, I'll go on." and the rest of the mission |
| `receive` | `object`, `wait_s` | "wait until someone gives you a cup": the receive above with the hand held out up to `wait_s` (`WAIT_GIVE_S` when no time is said) instead of `RECEIVE_WAIT_S`; "okay" counts only after DI_1 saw something (talk around it during a long wait must not close the hand). Nobody: hand back to look, open, "Nobody gave me the cup.", the mission fails there (it does not drive on or back: the rest needs the cup) |

Checked before anything moves (`steps.check`): `pick` / `receive` need an empty hand, `place` / `give` a full one,
`arm` reach / fold an empty one, `arm open` is refused while holding (it would fall: "put it down" or "hand it
over" instead); every field is validated (the dashboard sends the steps back as JSON); every marker must be on the map; a `move` over `MOVE_MAX_M` is refused; a wait over `WAIT_MAX_S` (30 min) is refused ("I wait at most 30 minutes."); a
`pick` / `receive` of a thing the fingers can't take is refused with its reason (`skills.refusal`: "The bottle is too
narrow at the top for my fingers ..."). **Something
handed over (`receive`) can't be put down on a table yet**: where it sits in the fingers is not measured, so the
height to let go at is not known; it can be handed over, carried and held.

## 2. Reading a command (`assistant/steps.py`)

1. **Messages first.** A `say` text is cut out of the command as written (case, numbers, names): after "say",
   "tell them (that)", "announce" up to a closing quote, or up to "and / then / ," followed by a step verb;
   Korean "…라고 말해 / 전해".
2. **Rules.** The rest is split into clauses (", then", "and", "after that", ". ", "그리고", Korean verbs in -고 / -서 /
   -다가) and each clause must be read whole as one step; filler ("please", "Lumi", "um", "thank you", "좀",
   "-주세요") is dropped. Numbers as words, "half a meter", "1 and a half", "50 cm", "반 미터" become metres.
   Marker names and numbers are read by `assistant/wording.py`, the same reader the keyword rules and the LLM check
   use: "피쓰리", "피 삼", "포인트 쓰리", "삼 번 포인트", "point three", "P.3", "피3" = p3; "파이널" = final; "도크 투" =
   dock2; "엑시트" = exit; "일 미터", "1미터 50센치", "영점오 미터", "오십 센치", "사십오 도"; mixed ("go to 피쓰리",
   "point 3에서 컵 가져와", "take the cup 하고 p3로 가서 줘"). Not clearly a marker ("피로", "PE로", "피자"): unread.
3. **LLM** (`brain.MODEL`, Ollama structured JSON) only when the rules leave a clause of a command of two or more
   clauses unread and what they did read is clearly a mission (a mission-only step, or not a plain fetch / carry);
   else the command goes the old way ("go to p1 and dance": the conversation answers it). Never when the
   command has a negation ("don't", "not", "말고", "대신"). The rule-read steps must be in its answer, in order; a
   turn's side and angle, a move's direction word and number (not inside "p1" or "1.5"), and how often a number is
   used are checked. Its answer is kept only if every value in it is written in the command: markers, numbers, objects,
   colours, sides, the words to say, and the verb of give / place / receive / hold. One step that fails this and the
   whole reading is dropped (the person is asked again). Non-English / non-Korean text: "other", nothing is taken.
4. **Waiting.** Times are read by `wording.durations` ("30 seconds", "2 mins", "half an hour", "1분 30초", "오 분", "한
   시간"; "이 분한테 줘" / "두 분께" are people). "Wait a moment / a second / a bit", "잠깐 / 잠시 / 조금" = `WAIT_SHORT_S`
   (10 s); "a while", "a few minutes", "몇 분", "한참", "이따가" are never guessed: unread, Lumi asks. "After 5 minutes go to
   p1", "5분 뒤에 p1로 가" = a wait, then the drive; "wait at p3", "p3에서 기다려" = a drive there, then the wait. A bare
   "wait" / "기다려" is a step only after another step ("go to p3 and wait"); alone, as a question ("can you wait?",
   "기다려 줄래?") or as a word to get attention ("wait, go to p2", "잠깐만, …") it is not one, and a command of waits
   only ("wait here", "hold on a second") is talk, not a mission. "Wait there and do what they tell you" is one
   instruction wait; "wait for someone to give you the cup" / "누가 컵 주면 받아서" a receive with `wait_s`.
4a. **The hand.** "Take this from me", "take the cup from me", "hold this", "이거 받아", "드릴게요" (the same words as
   `brain.hand_request`) are a `receive` with `from_hand`; "pass me the cup", "can I have the apple?", "컵 좀 줘" as the
   first clause are a `pick` then a `give` (from the table in front, then over). "..., then hold it" after another step
   stays a `hold`. Said alone, these go the quick way in `lumi.hand_command` (docs/14), not as a mission, except "pass
   me the cup" (two steps, read back).
5. **Named people.** "bring it to James at p6", "…to James, he is at p6", "James is at p6, take it to him",
   "p6에 있는 제임스한테 갖다줘": a drive there and a give to James. A name with no place ("give it to James") is
   asked about, unless Lumi drives somewhere first in the same command. Who sends it ("Anvar asks you to…", "from
   Lisa", "안바르가 보내는 거야") is not a step; it is kept with the mission (`steps.sender`). Names are kept as
   written ("Mr. Park", "김 부장님"; 씨 and a final 이 are taken off Korean names). People and places in any order:
   "go to Sarah at the stage and give her the cup", "Sarah is at booth two, bring her the cup", "bring it to Sarah,
   who is at booth two", "사라는 부스 투에 있어, 컵 갖다줘", "컵을 사라한테 갖다 줘, 사라는 부스 투에 있어"; "tell Sarah
   the meeting is at 3" is a `say`.
5a. **Said as people say it.** Before the reading (in `lumi.answer`, `brain.self_correct`): a correction inside the
   sentence is applied ("take the cup, go to start, no, end, and give it to James", "스타트로 가, 아니 엔드로 가서 줘",
   "wait 10 seconds, no, 20 seconds"); "..., never mind" / "아니 됐어" takes the command back ("Okay.", nothing
   moves); a correction that can't be read for sure is asked ("Sorry, which one did you mean?"). Fillers anywhere
   ("go to, uh, the stage"), "먼저 / 그다음 / 마지막으로", "I'd like you to", ordinals ("first ..., second ..."), Korean
   -고 나서 / -ㄴ 다음에 / -ㄴ 후에 and the honorific -시- ("가셔서", "받으시고", "기다리신 후에"), "갔다 와" / "다녀와" (there and
   back), "after you get to the stage, ...", and a clause whisper wrote without commas ("go to stage wait 10 seconds
   come back": split at the step verbs, every piece must read). "..., not booth two" is no drive there.
   "거기서 기다려" is a wait there, not "거기 서" (stop). A part that is a command but no step ("go to the stage and
   wave", "... and follow me", "... and dance", "... and tell ..." not read) is never done half: "Sorry, I can't do
   that as part of a task: wave. Please ask me one thing at a time." / "I didn't understand: ..." — when the
   sentence is no chain (5b).
5b. **A chain of commands, questions and talk** (`assistant/chain.py`, `lumi.chain_run`; owner 2026-10-22): a
   sentence cut at and / then / 그리고 / -고 / -서 whose parts are each a run of steps, a keyword command (look,
   lift, wave, arm, come, follow, go, turn, move, pick, put) or a question ("look at me and wave", "put it down
   and wave", "웨이브 하고 나 봐", "go to p5 and tell me the weather", "고개 들고 몇 시야?", "go to the stage and
   dance" -> it drives, then says it can't dance) is done part by part in the order said, each started when the
   one before is over (trip, mission, pick, wave, head and lift still). Steps next to each other run as one
   mission (no read-back; a whole sentence of steps is still a mission with its read-back). A part that can't be
   done says why (Patrol off, arm off, holding, unknown place) and the rest goes on; after a mission part that
   failed, the parts that drive or need the hand are not done and Lumi says so ("So I didn't do this part:
   come back."); in-place parts and answers still are. Follow only as the last part. "Stop" or new words end the
   chain. Not a chain: one command, "turn around and look" (the head), "come here, I need help", talk only.
   "Take the cup and put it back" / "컵 집었다가 제자리에 놔" is pick + place here (put back where it was picked);
   after a drive "put it back" is asked. "한 바퀴 돌아" / "spin around" in a mission is a turn of 360°. The
   dashboard's Command box (`/tasks/parse`) applies the same `brain.self_correct` first. The box reads every sentence
   exactly as voice (both on `lumi.route`, `tests/test_command_box.py`): a mission, a fetch (only with an object named),
   a command or chain done by the assistant as if heard (`/tasks/command`), or what voice would only answer (shown,
   nothing to start); the LLM only on Enter, for words the rules leave, as by voice. "X point" / "X 포인트" after any marker
   name is that marker ("let's go exit point and go p9 point", "first X then Y"); the Command box never reads a
   fetch when the text names no object.
6. **Read back.** Voice: "Take the cup, turn right and drive 1 m, then put it on the table. Is that right?" (marker
   names said with spaces: "go to booth 2", "table front"); only a
   spoken yes starts it (silence: "Should I do it? Please say yes or no.", three times, then cancelled), anything
   else cancels it ("Please say the whole command again."). Dashboard: the steps are
   listed, ✕ drops one (read again by `/tasks/steps/describe`), Start runs it.

API: `/tasks/parse` returns `action: "steps"` with `steps`, `sentence`, `problems`, `lang`; `POST /tasks/steps
{steps, lang}` starts it (the assistant runs it while it is on, else the API, speaking with the robot's voice).

"Stop" anywhere in what is said ("stop, where are you going?") stops the runner, the base, the arm and a trip first.

## 3. Questions about what Lumi is doing

"What are you doing", "where are you going", "what are you holding", "뭐 해", "어디 가" are answered from the task
state and the trip (`lumi.now_doing`), never by the LLM; while a wait step runs (state `waiting`: at, for, end):
"I'm waiting at p3, 25 seconds left." / "… until someone tells me to go on." / "… for an instruction." / "… for
someone to give me the cup." / after a final stay "I'm waiting at p3."; other phrasings reach the LLM with the same facts in its
prompt ("What you are doing now: …").

## 4. People on the way (`assistant/lumi.py` `mission_talk`)

While a mission runs, Lumi keeps listening. What is said **to it** halts the mission (`fetch.pause`: the base stops
at once, an arm move in progress ends first; `fetch.resume` goes on where it was: the rest of a turn, the same
goal, the rest of a move, all checked again). Said to it = the wake word, "stop" / "wait" / "excuse me" / "robot",
a question about what it is doing, a request, a name, or anything within 20 s of talking with it; other talk
around it is ignored.

| Someone says | Lumi |
|---|---|
| a stop word, anyone, running or halted: "stop", "stop it", "okay, stop it", "enough", "그만", "그만해", "멈춰", "정지" | stops everything and **ends** the mission at once (`lumi.stop_order` / `ENOUGH` -> `stop_all`): "Okay, I stopped." It never goes on after a stop word |
| "Hi Lumi", "wait", "excuse me" | halts, "Hi, I'm Lumi. I stopped for you. How can I help you?" |
| a question ("what are you doing", "who made you", "what is in my hand", "내 손에 뭐 있어?") | answered as usual (status from the task, seeing questions from the camera), then "Can I go on with my task?" |
| "go on", "continue", "you can go", "계속해", "계속 가", yes to "can I go on" | goes on with the mission. Nothing else lets a halted mission go on: not a goodbye, not "okay", not silence |
| nothing for 15 s | "Can I go on with my task?" once; it stays halted |
| "watch out", "my hand", "멈춰!", "위험해" | safety stop: stays halted until "go on" / "continue" / "계속 가" |
| a new command from anyone ("follow me", "come to me", "take me to p2", "give me that", a song), running or halted | the mission ends (`fetch.end`) with "Okay, I've stopped my task." and the command is done as usual (`lumi.end_run`; the same for a fetch run, a new mission, follow, a song). Something held stays held. "Cancel it" alone: "Okay, I've cancelled my task." |
| "I'm James" (James is who it is for) | "Hi James, this is for you. Here you go." and hands it over there (the rest of the mission is replaced by the give) |
| "I'm James, put it on my desk at p3 instead", "I'm at p5 now, bring it there", "I don't need it, cancel it" | the person it is for, or the sender named in the mission ("Anvar asks you…", "안바르가 보내는 거야"), may change or cancel it; a change Lumi can't read: "Sorry, what should I…? Should I give it to you here?" |
| "I'm Tom, give it to me" (it is for James) | a new command as any other: the mission ends, it is given to Tom |

**Waiting for an instruction** ("go to p6 and do what they tell you"): while that wait runs, anything said is to Lumi,
and the person there may give **one** command: read with `steps.read` (English / Korean only, LLM pass as usual),
read back, an explicit spoken yes, `steps.check` with the rest of the mission, then done there
(`lumi.instruction` -> `fetch.instruct`). It can't ask for another instruction wait. This is the only case where
someone gives Lumi a task that becomes part of the mission; at every other wait (a time, "until go on", a receive)
a new command ends the mission as above. "Go on" / "you can go" ends any wait step. While receiving or giving on a
mission, "okay" / "thank you" closes / opens the hand even when nobody spoke to Lumi before.

A name is the person's word only: anyone can say "I'm James". A name said in Korean is not matched to one written in
English in the mission (제임스 ≠ James). Who speaks makes no difference to a stop word or a new command (tracks of
the same person change: #10, #21, #24, #27 in one test). The dashboard's Stop always works; its Cancel (drive) also
ends a running or halted mission.

## 5. Checks

- `tests/test_steps.py`: 946 commands (66 written with the reader, 349 + 377 + 163 written blind from this page by
  another agent, `tests/steps_cases.py`, `steps_cases2.py`, `steps_cases3.py` (named people, senders); 40 % Korean,
  170 must be refused) read right, plus
  `check`, `describe`, `is_mission` and the LLM pass with a fake model.
- `tests/test_fetch.py`: missions run with fake base / arm / gripper (order of calls, receive by DI_1, timeout,
  blocked move, refused before moving). `tests/test_fetch_wait.py`: wait steps (stay at the end, until go on, a time
  with a pause, an instruction taken / refused / none, receive with a waiting time, stop).
  `tests/test_mission_wait.py`: what Lumi does with words during a wait and the status answers.
- Waits: `tests/steps_cases6.py` (written blind by an agent from the wait spec: 329 commands, ~48 % Korean, 50 must
  stay unread, 9 too long, 25 near misses that must not be a mission), in `tests/test_steps.py`: 2035 / 2035.
- Three or four steps in one breath on the conference map: `tests/steps_cases7.py` (EN / KO / mixed, every speech
  level, corrections inside, read-backs), in `tests/test_steps.py`; `tests/test_mission_route.py`: the same through
  `lumi.read_mission` (a mission, the plain fetch, or asked: never half done) and the Greeter-only rule.
- `tests/test_task_switches.py`: missions, fetches, carry, give, place and commands started from the dashboard with
  both switches off (refused), Greeter only (in place only) and Patrol (all); "stop" always.
- `tests/voice_check.py`: every command spoken by Lumi's TTS, heard by the robot's whisper, read again; the
  reading must equal the typed one (logs/voice_check.log). Round 1: 440 / 600; the misses are mostly marker names
  in Korean ("p3로" heard "피세로") and "1미터" heard "2m" (the read-back and the spoken yes catch these). Round 3
  (2026-10-19, Korean markers and numbers spoken as people say them, `tests/steps_cases5.py` added): 889 / 1065. A whisper
  prompt listing the markers made it worse (it wrote "p3" for other markers) and is not used.
- `tests/test_mission_talk.py`, `tests/interrupt_check.py`: what Lumi does with things said on the way (160
  scenarios, 301 turns written by another agent, `tests/interrupt_cases.py`): 290 / 301 as written; the rest are
  the voice "cancel" by the person who started it, a change that adds a message ("tell Tom happy birthday when you
  give it"), "take it back to Anvar" (Anvar's place is not kept).

## 6. Values

`MOVE_MIN_M` 0.1 m, `MOVE_MAX_M` 3.0 m, `TURN_MAX_DEG` 360°, `WAIT_SHORT_S` 10 s, `WAIT_MAX_S` 30 min,
`WAIT_GIVE_S` 5 min, `WAIT_ORDER_S` 5 min (`assistant/steps.py`), `WAIT_POLL_S` 0.05 s, `MOVE_SPEED` 0.10 m/s,
`MOVE_SEGMENT_M` 0.25 m, `RECEIVE_WAIT_S` 30 s, `RECEIVE_DI_S` 0.5 s (`tasks/fetch.py`). Estimates, to be tuned live (docs/TUNING.md).

## 7. A blocked drive (`assistant/detour.py`, `tasks/fetch.py` `detour`)

A drive that gets nowhere (a trip, a task's or a mission's drive: no progress for `STUCK_S`, or the base reports
`failed`) is said ("Sorry, I can't find a way to p3. Something may be blocking the path.") and kept for
`FRESH_S` 300 s in `/dev/shm/lumi_stuck.json`: its goal, the steps from that drive on, where the trip started. While
it is kept, these words (voice or the Command box, both through `lumi.route`) mean:

| Said | Lumi |
|---|---|
| "try again", "again", "keep going", "다시 해 봐", "한 번 더", "계속 가" | the same drive again, then the rest |
| "back up a little and try again", "뒤로 갔다가 다시 가" | straight back `BACKUP_M` 0.3 m (the checked move), then again |
| "go around it", "find a way", "try another way", "다른 길로 가 봐", "돌아서 가", "길 찾아서 와" | first to a free point beside the way (`VIA_AHEAD_M` 0.5 m along, `VIA_SIDE_M` 0.8 / 1.2 m to a side, `VIA_CLEAR_M` 0.6 m room by `agv.clearance`), then the goal |
| "go back", "come back", "원래 자리로 돌아가", "돌아와" | back to where the trip started |

Words the rules don't read go to the LLM with the block in "what you are doing now" (lumi.now_doing); it may answer
`ACTION: detour retry|around|backup|back` (brain.ACTIONS_STREAM). Each runs as a mission (STOP, pause and questions work as on one), says what it does in one line, and says plainly
when it still can't ("Sorry, I still can't get through. I can go back if you like."). Without a kept block the
words keep their usual meaning ("go back" = 1 m back, "try again" = the LLM). Another place named, "come back here",
"go back a bit", a no or a question are never a detour. The base's API has no call to clear its costmap: a retry
sends the same goal again. Straight moves ("move forward 2 m") stopped by something are not kept (they say how far
they got; "again" repeats them).
