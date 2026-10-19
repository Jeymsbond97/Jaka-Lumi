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
| `turn` | `deg` (+ left) | `_turn` (arm sweep checked; not on the charger) |
| `pick` | `object`, `colour` | `_pick_here` (the look / reach / pick part of a fetch) |
| `receive` | `object` | `_receive`: arm to `give`, hand open, "Please put the cup in my hand."; when DI_1 has seen something for `RECEIVE_DI_S`: "Let go of it, then say okay." and the hand closes **only on that word** ("okay", "done", "thank you", "됐어", or Release in the dashboard), never while fingers may be in it; then AI_1 must say holding. Nothing put in, or no okay, within `RECEIVE_WAIT_S`: back to look, hand open, failed |
| `say` | `text` (the command's own words) | spoken as written |
| `place` | `on`: null or {`name` (camera class), `colour`, `side`} | a `side`: turn 90° that way first (checked); a named thing or a table with a colour: `_put_on` (that thing, found by class and colour); else `_put_down` (any free table spot) |
| `give` | `person` (optional: "bring it to James at p6", "p6에 있는 제임스한테 갖다줘"; who it is for, see §4) | `_give` (opens on "thank you" / Release; nobody takes it = failed, still holding) |
| `hold` | – | nothing: the mission ends holding |
| `arm` | reach / fold / open / close | reach = the `give` pose, fold = `tuck`, open / close = gripper |
| `wait` | `s`: seconds | `_wait`: waits there ("waiting at p3"); time someone talks to Lumi (pause) does not count; "go on" ends it early |
| `wait` | `s`: null | at the end of a mission ("go to p3 and stay there"): the mission ends there, status `waiting` (step "waiting at p3"); any new command or Stop is taken as usual. In the middle ("go to the exit, wait there, then go home"): waits until someone says "go on" / "you can go" (`fetch.proceed`), or Stop. No time limit |
| `wait` | `s`, `until: "instruction"` | waits there for the person at the place to say what to do (§4), at most `s` (`WAIT_ORDER_S` when no time is said); their command is read back, a spoken yes, done there ("here" in it = that place), then the rest of the mission. Nobody: "Nobody told me what to do, I'll go on." and the rest of the mission |
| `receive` | `object`, `wait_s` | "wait until someone gives you a cup": the receive above with the hand held out up to `wait_s` (`WAIT_GIVE_S` when no time is said) instead of `RECEIVE_WAIT_S`. Nobody: hand back to look, open, "Nobody gave me the cup.", the mission fails there (it does not drive on or back: the rest needs the cup) |

Checked before anything moves (`steps.check`): `pick` / `receive` need an empty hand, `place` / `give` a full one,
`arm` reach / fold an empty one, `arm open` is refused while holding (it would fall: "put it down" or "hand it
over" instead); every field is validated (the dashboard sends the steps back as JSON); every marker must be on the map; a `move` over `MOVE_MAX_M` is refused; a wait over `WAIT_MAX_S` (30 min) is refused ("I wait at most 30 minutes."). **Something
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
5. **Named people.** "bring it to James at p6", "…to James, he is at p6", "James is at p6, take it to him",
   "p6에 있는 제임스한테 갖다줘": a drive there and a give to James. A name with no place ("give it to James") is
   asked about, unless Lumi drives somewhere first in the same command. Who sends it ("Anvar asks you to…", "from
   Lisa", "안바르가 보내는 거야") is not a step; it is kept with the mission (`steps.sender`). Names are kept as
   written ("Mr. Park", "김 부장님"; 씨 and a final 이 are taken off Korean names).
6. **Read back.** Voice: "Take the cup, turn right and drive 1 m, then put it on the table. Is that right?"; only a
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
| "Hi Lumi", "stop", "wait" | halts, "Hi, I'm Lumi. I stopped for you. How can I help you?" |
| a question ("what are you doing", "who made you") | answers (status from the task), then "Can I go on with my task?" |
| "go on", "you can go", yes to "can I go on", a goodbye, "never mind" | goes on with the mission |
| nothing for 15 s | "Can I go on with my task?"; nothing for 15 s more: goes on |
| "watch out", "stop!", "STOP STOP", "my hand", "멈춰!", "위험해" | safety stop: stays halted until "go on" / "continue" / "계속 가" (a goodbye or silence does not let it go) |
| another task, "come with me", "give me that", "take me to p2", asking again | refuses: "Sorry, I'm doing a task for someone: … I can help you when I've finished."; any motion the LLM or the quick rules would start is blocked while a mission runs |
| "I'm James" (James is who it is for) | "Hi James, this is for you. Here you go." and hands it over there (the rest of the mission is replaced by the give) |
| "I'm James, put it on my desk at p3 instead", "I'm at p5 now, bring it there", "I don't need it, cancel it" | the person it is for, or the sender named in the mission ("Anvar asks you…", "안바르가 보내는 거야"), may change or cancel it; a change Lumi can't read: "Sorry, what should I…? Should I give it to you here?" |
| "I'm Tom, give it to me" (it is for James) | "Sorry, this is for James, I have to bring it to them." |

**Waiting for an instruction** ("go to p6 and do what they tell you"): while that wait runs, anything said is to Lumi,
and the person there may give **one** command: read with `steps.read` (English / Korean only, LLM pass as usual),
read back, an explicit spoken yes, `steps.check` with the rest of the mission, then done there
(`lumi.instruction` -> `fetch.instruct`). It can't ask for another instruction wait. This is the only case where
someone not named in the mission gives Lumi a task on the way; at every other wait (a time, "until go on", a receive)
another person's task is refused as above. "Go on" / "you can go" ends any wait step. While receiving or giving on a
mission, "okay" / "thank you" closes / opens the hand even when nobody spoke to Lumi before.

A name is the person's word only: anyone can say "I'm James". A name said in Korean is not matched to one written in
English in the mission (제임스 ≠ James). The person who started the mission is not known by voice: a voice "cancel"
from someone not named in the mission is refused; the dashboard's Stop always works.

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
`WAIT_GIVE_S` 5 min, `WAIT_ORDER_S` 5 min (`assistant/steps.py`), `WAIT_POLL_S` 0.2 s, `MOVE_SPEED` 0.10 m/s,
`MOVE_SEGMENT_M` 0.25 m, `RECEIVE_WAIT_S` 30 s, `RECEIVE_DI_S` 0.5 s (`tasks/fetch.py`). Estimates, to be tuned live (docs/TUNING.md).
