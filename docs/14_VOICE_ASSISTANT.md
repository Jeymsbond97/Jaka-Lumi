# 14. Voice assistant: required behaviour

How Lumi must behave when it talks with people. The requirements come from the product owner. Each one is marked with how it is implemented (`real/thor/assistant/lumi.py`, `assistant/brain.py`, `audio/ears.py`, `audio/mic.py`) and whether it has been tested on the robot. Change the code to match this page, not the other way round. When a requirement changes, update this page first.

Status: ✅ tested on the robot · 🟡 implemented, not yet tested live · ⬜ not implemented

---

## 1. Languages

| Requirement | Implementation | Status |
|---|---|---|
| Understand and answer **English and Korean** | whisper.cpp (`large-v3-turbo`, auto language) → Ollama `gemma4:26b` → Supertonic TTS (voice F1) | ✅ |
| **Answer in the language the person just used**, switching at once (EN ↔ KO) | `ears.last_stt["language"]` → `brain.FORCED_LANG` → system prompt names the answer language | 🟡 |
| "English로 말해 줄래요?", "영어로 자기소개 해 봐", "talk in Korean": answered in the language asked for; in English the company is always "Cutshion" | `brain.reply_language`, `brain.spoken` | 🟡 |
| Other languages are not answered | only `english` / `korean` count as understood | ✅ |
| Another language in Latin letters typed or misheard as text ("menga suv ber") → "Sorry, I only understand English and Korean." | `brain.other_latin_language` (one short LLM call on an unclear action) | 🟡 |

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
| Never "How can I help you?" / "무엇을 도와드릴까요?" tacked on after an answer | system prompt; such a sentence after the first one is dropped (`brain.HELP_OFFER`) | 🟡 |
| Short spoken answers, 1–3 sentences | system prompt; streamed sentence by sentence (first words ~2 s after the question) | ✅ |
| Follow-ups ("tell me more", "why?", "can they see in the dark?") continue the same topic | history of 4 turns; `Brain.topic()` joins a short follow-up or one with "it / they / 그거" to the previous question for the notes, the examples and the lookup decision | ✅ |
| **Unclear or garbled speech → ask to repeat** ("Sorry, what did you say?"), never guess | `ears.understood()`: language EN/KO, average log-probability ≥ −1.0, and the text must be written in the detected language; LLM action `unclear` | 🟡 |
| Facts it does not know (news, people, prices, events) → say "let me check", look them up, answer | `web.search`: Wikipedia + Google News RSS, query written by the LLM | ✅ |
| Never looked up online: Lumi itself, Cutshion, this event or building (schedule, booths, restrooms, tickets, opening hours): the notes say it, else "I don't have that information" and a staff member | `lumi.not_online`, `lumi.look_up_unsure` | 🟡 |
| "Hand it over", "테이블에 놔" with nothing in the hand → "I'm not holding anything right now." | `lumi.empty_hand_request` | 🟡 |
| The LLM never drives to a place the words do not name ("take me to the meeting room" is not p1) | `brain.named_place` | 🟡 |
| Weather → current weather for Seoul (or a named place) | `web.weather` (open-meteo), refreshed in the background every ~9 min so the answer is immediate | 🟡 |
| Date and time | `brain.now_line()` in the prompt (English and Korean form) | ✅ |
| Facts about Lumi and Cutshion said exactly, also in short follow-ups ("No, I meant the arm.", "How long on a charge?"); what the notes do not have (in the dark, ROS, charge time) is "not sure" | fact sheet and "not known" line in the system prompt, from knowledge/*.md | 🟡 |
| Sing / wave only when asked ("Prove it." after a joke is a joke, "Hello Lumi!" is not a wave); "and down?" after a look looks down; "How old is he?" after a lookup is looked up | `Brain._after`, `WAVE_ASK`, `SING_ASK` | 🟡 |
| Natural small talk ("how are you?") | system prompt | ✅ |
| Sing a short song on request, with music and head moves (§6, Singing) | `audio/sing.py`, `sing_song()` | 🟡 |

Lumi is presented as developed by Cutshion Company, 2 years old. With each question the LLM gets the few closest
of 620+ example exchanges (`assistant/talk_examples.py`, English and Korean, by topic) as a guide to tone and to
vary its wording ("Nice to meet you! How can I help you today?" every time was boring); on a mission also examples of
answers to people met on the way (`assistant/interrupt_examples.py`).

## 4. Ending a conversation

| Requirement | Implementation | Status |
|---|---|---|
| Acknowledgements (**"okay", "got it", "I got you", "alright", "okay, I understand", "알겠어요", "네 알겠습니다", "오케이", "그래요", "네", "좋아요"**) followed by ~3 s of silence → goodbye; more words after them go on with the talk | `brain.is_closing`, `CLOSING_WAIT_S` | 🟡 |
| Goodbyes and thanks (**"thanks", "thank you", "bye", "see you next time", "that's all", "good night", "I have to go", "nice talking to you", "take care", "고마워요", "감사합니다", "다음에 봬요", "들어가세요", "수고하세요", "안녕히 계세요", "이만 갈게요", "빠이빠이", "바이", "땡큐", "간다~", "잘 있게"**) → goodbye at once, unless a question comes with them ("thanks, what time is it?") | `FAREWELL_WORDS` (`answer()`), checked in `tests/test_fetch_intents.py` | 🟡 |
| Said on their own (**"go on", "I see", "good", "good job", "well done", "got it, thanks", "가 보세요", "잘했어요", "좋아", "수고했어요", "그렇구나"**) → goodbye at once; inside a sentence they don't end it ("good morning", "I see a robot, what is it?") | `FAREWELL_ONLY` | 🟡 |
| **The goodbye fits the conversation and varies**; no fixed phrase, never a greeting ("안녕!" at the end is bye) | `Brain.farewell(text, lang)` (LLM, one short sentence, 3 random goodbye examples as ideas, not one of the last `FAREWELL_RECENT` 8 goodbyes) | 🟡 |
| Silence after an answer ends the conversation (the person may just walk away) | voice session `VOICE_SESSION_S` 15 s; someone in view: "How can I help you?" after `PROMPT_S` 12 s, at most `MAX_PROMPTS` 2; the person leaves the camera's view: talk over; on patrol `PATROL_WAIT_S` 8 s, then it drives on | ✅ |
| On a mission (docs/17 §4): a goodbye or a thanks goes on with the task; silence: "Can I go on with my task?" after 15 s, goes on after 15 s more (never after a safety stop) | `lumi.mission_talk`, `TALK_ASK_S` | 🟡 |
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
| "p3로 가 줘", "피쓰리로 가", "포인트 삼으로", "삼 번 포인트로", "point three", "파이널로 가", "도크 투로 가" | the same: marker names said in English, in Korean or mixed, and as whisper writes them, are read by `assistant/wording.py` (one reader for the keyword rules, missions and the check of the LLM's place); a word that is not clearly a marker ("피로 가", "PE로") is not driven | 🟡 |
| "Look left / right / up / down / at me" | head | ✅ |
| "Turn your head 30 degrees right", "look down a bit", "고개 들어 / 숙여", "고개 살짝 왼쪽으로", "정면 봐" | head to a number of degrees or a small step (`brain.head_target`, `head_goal`); a number past the range is cut and said ("I can turn my head up to 180 degrees each way"; commanded looks use the full ±180°, `head.YAW_LIMIT` ±60° is for following people) | 🟡 |
| "Raise yourself", "lower yourself a bit", "키 좀 높여", "몸 5센티만 내려" | lift up / down / small step / mm, slowly, 0–105 mm for now (`brain.lift_target`, `lift_goal`, `lumi.lift`) | 🟡 |
| "Turn left / right / around" | base turns 90° / 180° (or a spoken angle) | 🟡 |
| "Move forward / back / left / right N metres" | short base move, at most 3 m | 🟡 |
| "Reach out your hand" / "fold your arm" | Cobo π program `arm_reach.jks` (to record) / tuck pose | 🟡 / ⬜ |
| "Wave", "can you shake your hand?", "손 흔들어 줘", "손 인사 해 줘" | Cobo π program `hand_shaking.jks`; done at once by the keyword rule | ✅ |
| "Open your hand" / "close your hand", "grab it", "let go", 손을 펴 / 잡아 | gripper open / close, confirmed aloud | 🟡 |
| "Stop" | base, arm, a running pick / place (`skills.cancel`) and speech stop | ✅ (skills 🟡) |
| "Pick up the (white) cup", "take the bottle", 컵 잡아 | `skills.pick`: find, IK-check, pick, hold 3 cm above the table; "I've got it" or the reason it cannot | 🟡 |
| "Move the cup", 컵 옮겨 | `skills.move_object`: pick and put on a free spot nearby, back to `ready` | 🟡 |
| "Put it down" / "put it back", 내려놔 / 제자리에 놔 | `skills.put_down`: a free spot near where it was picked / the same spot | 🟡 |
| "Bring me the apple from p1", "take the cup from p2 to home and put it on the table", "p1에서 사과 가져와" | fetch task ([16_FETCH_TASKS.md](16_FETCH_TASKS.md)): strict parse (unknown words are asked about), read-back, yes or 5 s silence starts, a correction changes one field and is read back, "cancel" ends | 🟡 |
| While holding: "give it to me" / "bring it to me" / 줘, "put it on the table" / 테이블에 놔, "thank you" while handing over | give (needs pose `give`), place, open the hand | 🟡 |
| Several steps in one command: "take the cup, go left 1 m and put it on the table", "go to final, give it and say Anvar says hello", "go to p9, ask them for the cup, then bring it to p1", 컵 들고 p9로 가서 줘 | mission ([17_MISSIONS.md](17_MISSIONS.md)): read by rules (the LLM only for what they leave, every value checked against the words), read back, yes or silence starts, anything else cancels; a part not understood is named and nothing runs | 🟡 |
| "What are you doing", "where are you going", "what are you holding", 뭐 해, 어디 가 | answered from the task state and the trip (`now_doing`), never guessed; during a mission's wait: "I'm waiting at p3, 25 seconds left" / "… for an instruction" / "… for someone to give me the cup" / "… until someone tells me to go on" (docs/17 §3) | 🟡 |
| "Put it here" (where the person points) | needs the person's position on the table, P7 in [15_PICK_AND_PLACE.md](15_PICK_AND_PLACE.md) | ⬜ |

Simple commands are matched by rules (`brain.INTENTS`) and done without waiting for the LLM; everything else goes through the LLM's `ACTION:` line, which lists every ability with its parameters and limits (`brain.ACTIONS_STREAM`) and maps any wording to one of them ("Eyes on me, please." → look me, "한 바퀴 빙 돌아 봐" → turn around); code checks the action and its values (`Brain._action`). What the body can't do (jump, dance, fly, stairs, doors) is answered plainly. Body commands in any wording are checked by `tests/dialogue_check.py --commands`.

Pick and place run in the background (up to a minute) while Lumi keeps listening, so "stop" works during them; no wave is started meanwhile. Objects are the camera classes cup, bottle, apple, orange, banana (spoken "mug", "glass" mean cup). A colour in the request must match the colour the camera measures, which changes with the light (a white cup can read "grey"): without a colour the nearest such object is taken. Reasons are spoken in English; in Korean Lumi says only that it cannot do it now.

### Singing

| Requirement | Implementation | Status |
|---|---|---|
| "Sing a song", "sing Arirang", "can you sing for her?", "노래 불러 줘", "아리랑 불러 줘", "a Korean song" → Lumi sings about a minute over a backing track in its own voice | `sing.asked()` before the quick rules; also the LLM's action `sing` ("can you sing?" … "yes"); `sing.choose()`: a named song, else any song (one in the language asked for: "a Korean song") | 🟡 |
| Songs: Happy Birthday, Twinkle Twinkle Little Star, Row Row Row Your Boat (EN), 아리랑, 곰 세 마리 (KO); public domain, melodies and chords written in `data/songs/<id>.json`, nothing downloaded | `audio/sing_render.py` renders `data/songs/<id>.wav` once | 🟡 |
| The owner's songs (Fantastic Baby / 판타스틱 베이비, Love Attack / 러브 어택, 꿈꾸던 어른이 되었나요, BAD / 배드; licensed by the company, files local only in `data/songs/mine/`): an "AI cover": the original singer's vocal (words, melody, timing, feeling) turned into Lumi's voice, over the song's own instrumental, the best 40–60 s (most-repeated lines, singing, loudness); the instrumental's beats and loudness drive the head moves | `audio/separate.py` (Demucs), `audio/cover.py` (Seed-VC 44.1 kHz pitch model fine-tuned on Lumi's TTS voice), `audio/sing_mine.py` (part, beats, mix), `audio/cover_check.py` | 🟡 |
| "Sing a song" with no title: any song, not the one just sung | `sing.choose()` | 🟡 |
| A song we don't have ("sing Yesterday", "애국가 불러 줘") → "Sorry, I don't know that song yet. I can sing …" | `sing.unknown_reply()` | 🟡 |
| The head moves like a person singing, following the music. It turns to yaw 0 / pitch 0 first and dances around it: in energetic parts a small diagonal bob (4–8°) on every beat there is time for, alternating sides, at vel 100; on a bar's accent (onset) or where a sung phrase starts a quick 15–25° sweep across with a dip; calm parts sway slower (vel 70, 50 in the calmest). Each move is called so it lands ON its beat, with the owner's measured head timing (starts 0.2 s after the call, ~40°/s, a small move arrives 0.5 s and returns 0.6 s after the call); the next call is sent only after the last returned (overlapping moveto calls hang the body API). Yaw and pitch change on every move, never along the last move's line. Yaw ±25°, pitch 0–15°; never the lift, waist or arm; back to yaw 0 / pitch 0 when the song ends or stops | `sing.head_targets()`, `reach_time()`, `move_time()`; beats, energy, accents and phrases from `sing_mine.beat_info()` (owner's songs) or the melody | 🟡 |
| "Stop", "멈춰", "그만" while singing → music, voice and head stop at once (head back) | `song_abort()`: the clip mic keeps listening, as for barge-in (§5) | 🟡 |
| "Sing another song", "다른 노래" → a different song; "sing it again", "한 번 더" → the same one; any other request ends the song and is answered | `pending_text`, `last_song` | 🟡 |
| Not while a task or a mission runs (the head and speaker are the task's) | `skill_busy()`, `mission_running()` | 🟡 |

The voice: every syllable of the lyrics is spoken by the TTS (voice F1, the same as every answer; English syllables written the way the TTS says them right, "Twin kle"), its pitch is set to the note and its vowel stretched to the note's length by TD-PSOLA (pitch-synchronous overlap-add), with a short glide between notes and a light vibrato on long notes; the consonant before the vowel starts just before the beat. The backing is bass and chords in a soft piano-like tone, synthesised from the chord list, with a small room reverb. Songs are transposed so their average note is near 240 Hz (the voice speaks at about 175 Hz). After changing a song file: `.venv/bin/python audio/sing_render.py <id>`. With only the head microphone (no clip mic) Lumi cannot hear "stop" while it sings, as while it speaks.

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
| LLM | `brain.MODEL` | `gemma4:26b` via Ollama, kept loaded |

## 9. Open items

- Live test of everything marked 🟡 (language switching, unclear-speech handling, wake word while driving and resuming, varied goodbyes, turn / move commands).
- Better general answers: a search API key (Brave Search, Tavily) or the Claude API with web search. Owner to decide.
