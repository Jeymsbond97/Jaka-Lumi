# 14. Voice assistant: required behaviour

How Lumi must behave when it talks with people. The requirements come from the product owner. Each one is marked with how it is implemented (`real/thor/assistant/lumi.py`, `assistant/brain.py`, `audio/ears.py`, `audio/mic.py`) and whether it has been tested on the robot. Change the code to match this page, not the other way round. When a requirement changes, update this page first.

Status: ✅ tested on the robot · 🟡 implemented, not yet tested live · ⬜ not implemented

---

## 1. Languages

| Requirement | Implementation | Status |
|---|---|---|
| Understand and answer **English and Korean** | whisper.cpp (`large-v3-turbo`, auto language) → Ollama `gemma4:e4b` → Supertonic TTS (voice F1) | ✅ |
| **Answer in the language the person just used**, switching at once (EN ↔ KO) | `ears.last_stt["language"]` → `brain.FORCED_LANG` → system prompt names the answer language | 🟡 |
| Other languages are not answered | only `english` / `korean` count as understood | ✅ |

## 2. Waking and finding the caller

| Requirement | Implementation | Status |
|---|---|---|
| Wake words: **"Lumi", "Hi", "Hi Lumi", "Hey Lumi"** (Korean "루미야") from anywhere, also 3–4 m away and from behind | `WAKE`, `HELLO_ONLY` in `lumi.py`; wireless clip mic (DJI Mic Mini) when connected, else the head mic array | ✅ (near), 🟡 (3–4 m) |
| Find **who** called: the voice direction (6-mic array, SRP-PHAT, self-calibrating) matched to a person in the camera | `doa.py`, `find_caller()` | ✅ |
| Caller **outside the camera view**: the head camera turns the head first (sees ±102°: 42° + head ±60°); farther, turn the base toward the voice, then look for the person | `CAMERA_HALF_FOV` 42°, `head.YAW_LIMIT`, `agv.turn_by` | 🟡 |
| Reply to a bare wake word: "Yes? How can I help?" | `WAKE_REPLY` | 🟡 |
| A command spoken together with the wake word ("Hi Lumi, come here") is done at once | `check_wake()` | ✅ |

## 3. Answering

| Requirement | Implementation | Status |
|---|---|---|
| **Answer only what was asked**: no self-introduction, no extra offers | system prompt in `brain.py` | 🟡 |
| Short spoken answers, 1–3 sentences | system prompt; streamed sentence by sentence (first words ~2 s after the question) | ✅ |
| Follow-ups ("tell me more", "why?") continue the same topic | history of 4 turns, `FOLLOW_UP` | ✅ |
| **Unclear or garbled speech → ask to repeat** ("Sorry, what did you say?"), never guess | `ears.understood()`: language EN/KO, average log-probability ≥ −1.0, and the text must be written in the detected language; LLM action `unclear` | 🟡 |
| Facts it does not know (news, people, prices, events) → say "let me check", look them up, answer | `web.search`: Wikipedia + Google News RSS, query written by the LLM | ✅ |
| Weather → current weather for Seoul (or a named place) | `web.weather` (open-meteo), refreshed in the background every ~9 min so the answer is immediate | 🟡 |
| Date and time | `web.now_text()` in the prompt | ✅ |
| Natural small talk ("how are you?") | system prompt | ✅ |
| Sing a short song on request | action `sing` | ✅ |

## 4. Ending a conversation

| Requirement | Implementation | Status |
|---|---|---|
| Closing words (**"okay", "thanks", "I got you", "thanks so much", "good"**) followed by ~3 s of silence → goodbye | `brain.is_closing`, `CLOSING_WAIT_S` | 🟡 |
| Explicit goodbyes ("bye", "see you", "that's all") → goodbye at once | `FAREWELL_WORDS` | 🟡 |
| **The goodbye fits the conversation and varies**; no fixed phrase | `Brain.farewell(text, lang)` (LLM, one short sentence) | 🟡 |
| Silence after an answer ends the conversation | voice session `VOICE_SESSION_S` 15 s; on patrol `PATROL_WAIT_S` 8 s | ✅ |
| "Be quiet" → no greetings for 10 min (the wake word still works) | action `quiet`, `QUIET_S` | ✅ |

## 5. Interrupting Lumi (barge-in)

| Requirement | Implementation | Status |
|---|---|---|
| While Lumi speaks, "stop", "okay", "thanks", "got it" stop the speech | clip mic keeps listening while Lumi talks (`mic.BARGE_IN`), `barge_in()` | ✅ |
| A new question interrupts the answer and is answered | `pending_text` | ✅ |
| Lumi's own voice must not count as an interruption | ignored when ≥ 60 % of the words match what Lumi said in the last 30 s, or when the text is unclear (log-probability < −0.6 or in the wrong script) | 🟡 |

Keep the clip mic's transmitter on the visitor, not on the robot: taped near the head it hears the speaker and interrupts Lumi.

## 6. Motion commands by voice

| Command | Action | Status |
|---|---|---|
| "Come here", "come to me", "이리 와" | drive to a free spot ~1 m in front of the caller (`nav.py`), stop at 1.1 m | ✅ |
| "Go to p2", "go home", "go to the charger" | drive to a map marker | ✅ |
| "Look left / right / up / down / at me" | head | ✅ |
| "Turn left / right / around" | base turns 90° / 180° (or a spoken angle) | 🟡 |
| "Move forward / back / left / right N metres" | short base move, at most 3 m | 🟡 |
| "Reach out your hand" / "fold your arm" | Cobo π program `arm_reach.jks` (to record) / tuck pose | 🟡 / ⬜ |
| "Wave" | Cobo π program `hand_shaking.jks` | ✅ |
| "Open your hand" / "close your hand", "grab it", "let go", 손을 펴 / 잡아 | gripper open / close, confirmed aloud | 🟡 |
| "Stop" | base, arm, a running pick / place (`skills.cancel`) and speech stop | ✅ (skills 🟡) |
| "Pick up the (white) cup", "take the bottle", 컵 잡아 | `skills.pick`: find, IK-check, pick, hold 3 cm above the table; "I've got it" or the reason it cannot | 🟡 |
| "Move the cup", 컵 옮겨 | `skills.move_object`: pick and put on a free spot nearby, back to `ready` | 🟡 |
| "Put it down" / "put it back", 내려놔 / 제자리에 놔 | `skills.put_down`: a free spot near where it was picked / the same spot | 🟡 |
| "Bring me the apple from p1", "take the cup from p2 to home and put it on the table", "p1에서 사과 가져와" | fetch task ([16_FETCH_TASKS.md](16_FETCH_TASKS.md)): strict parse (unknown words are asked about), read-back, yes or 5 s silence starts, a correction changes one field and is read back, "cancel" ends | 🟡 |
| While holding: "give it to me" / "bring it to me" / 줘, "put it on the table" / 테이블에 놔, "thank you" while handing over | give (needs pose `give`), place, open the hand | 🟡 |
| "Put it here" (where the person points) | needs the person's position on the table, P7 in [15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md) | ⬜ |

Simple commands are matched by rules (`brain.INTENTS`) and done without waiting for the LLM; everything else goes through the LLM's `ACTION:` line.

Pick and place run in the background (up to a minute) while Lumi keeps listening, so "stop" works during them; no wave is started meanwhile. Objects are the camera classes cup, bottle, apple, orange, banana (spoken "mug", "glass" mean cup). A colour in the request must match the colour the camera measures, which changes with the light (a white cup can read "grey"): without a colour the nearest such object is taken. Reasons are spoken in English; in Korean Lumi says only that it cannot do it now.

## 7. Greeting and driving

| Requirement | Implementation | Status |
|---|---|---|
| **Greeter mode** (standing): a person who stays 0.5–1.2 m in front for 0.7 s is greeted once (head turns, wave, "Hi, I'm Lumi…") | `NEAR_MIN/MAX`, `HOLD_S` | ✅ |
| After 12 s of silence ask "How can I help you?" (at most twice) | `PROMPT_S`, `MAX_PROMPTS` | ✅ |
| Person leaves → stop talking; comes back → greeted again | `LOST_S` 2 s | ✅ |
| **Patrol mode** (driving): only a person in the path (±0.4 m) closer than 1 m stops the robot | `PATH_HALF_WIDTH`, `PATROL_NEAR_MAX` | ✅ |
| **While driving, stop only for a wake word.** Stop, turn to the caller, talk; afterwards continue the conversation without the wake word | `check_wake()` → `patrol.pause()` | 🟡 |
| After the conversation (goodbye, closing words + silence, or silence) **continue the same route** | `end_conversation()` → `patrol.wait_until` | 🟡 |
| A drive that does not move for 20 s is cancelled and Lumi says so | `STUCK_DRIVE_S` | ✅ |
| Below 5 % battery drive home, continue at 60 % | `LOW_BATTERY`, `RESUME_BATTERY` | ✅ |

Cameras: standing (greeter, conversation) the **head camera** watches people, driving (patrol, go to, come here) the **torso camera** watches the path; a camera without detections for `CAMERA_FRESH_S` 2.5 s is replaced by the other until it is back; while the arm waves, a person too close in either camera stops it. `--camera head|torso` pins one. 🟡 not yet run live.

Modes are switched live from the dashboard (`/assistant/modes`): **greeter**, **patrol**, **wave** (wave when greeting), **drive** (allow "come here" / "go to").

## 8. Tuning values

| Value | Where | Now |
|---|---|---|
| Speech start threshold | `mic.START_FACTOR`, `MIN_LEVEL`, `MIN_LEVEL_CLIP` | 1.8 × noise, 250 / 300 RMS |
| End of utterance | `mic.END_SILENCE` | 0.6 s |
| Clear-speech threshold | `ears.MIN_LOGPROB` / `lumi.BARGE_IN_LOGPROB` | −1.0 / −0.6 |
| Own-voice window | `mouth.recent_speech` | 30 s |
| Speaker volume | `volume.txt`, dashboard | 55 % |
| LLM | `brain.MODEL` | `gemma4:e4b` via Ollama, kept loaded |

## 9. Open items

- Live test of everything marked 🟡 (language switching, unclear-speech handling, wake word while driving and resuming, varied goodbyes, turn / move commands).
- Better general answers: a search API key (Brave Search, Tavily) or the Claude API with web search. Owner to decide.
