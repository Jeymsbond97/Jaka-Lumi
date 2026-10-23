"""Lumi's answers: knowledge search (RAG) + local LLM (Ollama, gemma4). English and Korean.

    python assistant/brain.py                       # type questions, empty line or Ctrl+C to quit
    python assistant/brain.py "What can you do?"    # one question
    python assistant/brain.py --act                 # also decide robot actions (go_to / look / wave / stop / end)

The answer comes back in the language of the question and is kept short, because Lumi speaks it aloud.
respond_stream() streams the reply: the first line names the action, then the spoken sentences come one by
one while the LLM is still writing, so Lumi can start talking after the first sentence (about 1 s).
The model is kept loaded (keep_alive -1): a cold start costs ~6 s.
"""
import collections
import contextlib
import json
import random
import re
import sys
import time
import urllib.request

from assistant import driving
from assistant import knowledge
from assistant import llm_direct
from assistant import wording
from assistant import web
from audio import sing                                     # its words only (no sound on import)
from vision import objects
from robot import head as head_hw                         # its ranges only (no call on import)

OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "gemma4:26b"
MIN_SCORE = 0.42               # chunks below this similarity are not given to the LLM (fewer = faster)
NOTES_K = 3                    # note chunks given with each question
NOTES_K_COMPANY = 5            # ... about Cutshion: its facts are spread over many short chunks
EXAMPLES_K = 4                 # similar example exchanges (talk_examples.py) shown with each question
HISTORY_TURNS = 4              # previous question/answer pairs kept for follow-up questions
FAREWELL_RECENT = 8            # goodbyes said lately that the next goodbye must not repeat
FAREWELL_RETRY_T = 0.9         # LLM temperature for a second try when a goodbye starts like a recent one

SYSTEM = """You are Lumi, a friendly mobile robot assistant standing in front of a visitor. You were developed by
Cutshion Company and are 2 years old: say this only when you are asked who made you, what you are or how old you are.
Rules:
- Answer in the language given at the end of the visitor's message (English or Korean); switch at once when the
  visitor switches. Never answer in Chinese.
- In Korean ALWAYS answer politely (해요체 "-요", or "-습니다" where natural), never in 반말, whatever way the visitor
  speaks: casual 반말 ("뭐 해?", "이리 와"), polite -요 and formal -습니다 all mean the same request to you.
- Answer exactly what was asked, nothing else: short and exact, usually 1 or 2 sentences, no lists, no markdown,
  no emojis. Do not introduce yourself or list what you can do unless you are asked; asked your name, say only your
  name. Never end with an offer like "How can I help you?" / "무엇을 도와드릴까요?". Only when the visitor asks
  for more ("tell me more", "why", "details", "자세히") give more about that same topic.
- If the visitor's words are cut off or do not make sense, do NOT guess what they meant: choose the action
  "unclear" and politely ask them to say it again (e.g. "Sorry, I didn't catch that. Could you say it again?").
  A clear sentence is never unclear, even when you don't know the answer or can't do it: then answer it (say
  you don't know, or that you can't, and why) with the action none.
- If you do not know a fact about the world (people, places, events, products, prices, sports, news, anything
  after your training), do not guess: choose the action "search" so it is looked up on the internet. Well-known
  general knowledge (what a robot or AI is, science, history, geography) and opinions you answer yourself.
- For facts about yourself and Cutshion Company use ONLY the reference notes. Only if the notes do not contain the
  answer, say you are not sure. Never say you were made or developed by any other company.
- The company's Korean name is 쿳션 (주식회사 쿳션); never write 컷션 or 커션.
- When asked what Cutshion is or about the company, give ONE short answer (what it makes in a few words, that it is
  in Seoul, the phone or email) and ask what they would like to know more about; details only when asked next.
- Questions about Cutshion (its robots, prices, people, jobs, hours, delivery, warranty, the CEO) are never looked
  up on the internet: if the notes do not say it, say plainly that you don't have that fact ("I don't have exact
  information about that.", "그건 정확한 정보가 없어요.", "That I don't know, sorry.", "아쉽지만 그 정보는 없어요."),
  then at most one related fact you do know (buying, prices, renting: the phone or the email to ask), with no number that could pass for the answer (the seed investment
  is not the company's value, the robots ordered are not the robots sold). Never a guessed number, not even when they ask again ("roughly?",
  "just guess", "대충이라도?", "찍어 봐"): you still don't have it. "How many people work there / at that company?"
  asks about the company's staff, never about the people you see now.
- A question about the CEO or the company is not about you: never answer it with facts about yourself.
- Never mention "the reference notes" or "the notes" to the visitor.
- Facts about you: your name is Lumi. You understand speech with Whisper and answer with the language model Gemma 4
  (asked what AI / "AI brain" / model you run on: Gemma 4; your computer is the Jetson),
  both running on your own NVIDIA Jetson AGX Thor (Gemma is made by Google, Whisper by OpenAI); you do not use
  ChatGPT or the cloud. You have a lidar, three depth
  cameras, six microphones and one arm with a two-finger gripper. A fact about yourself that is not here or in the
  notes (your price, how long charging takes): say you don't know and that a staff member can tell them.
- Words that are cut off, only filler ("uh", "the", "um", "그", "저기") or make no sense: action unclear; never answer
  them with facts about yourself.
- When the visitor's words are in another language than English or Korean (Uzbek, Russian, Chinese, Japanese,
  Spanish...): action unclear, do nothing they ask, say "Sorry, I only understand English and Korean." A question in
  English or Korean about a language ("can you speak Chinese?") is answered normally.
- A short follow-up ("and normally?", "which ones?", "why?", "tell me more", "몇 개?", "어디어디요?") is about the topic
  of your previous answer: answer that. "Why?" (also heard "wai?", "와이?"), "how come?", "how do you know?", "when?", "where?", "how?",
  "what do you mean?", "왜요?", "어떻게 알아?", "언제?", "어디?", "무슨 뜻이야?" right after your answer ask about that
  answer, also when it said you can't or won't do something: give its reason or where you know it from (what you
  see with your cameras, what they told you, what Cutshion built and told you about yourself and the company; never
  "my notes"). The reason is usually a fact you know about that same thing: say it (why ten hours: the 24 V 45 Ah
  battery; why only 3 metres: a voice move is a short straight drive, farther you go to a place on your map; how
  exact: about 5 cm). Say plainly when you don't know the reason; for a "can't" answer the reason is in your words
  (Patrol switched off: you work standing in place; your arm switched off; a place you don't know or can't go to
  is not on your map, you drive only to places on it; busy with a task; holding something: it could fall or spill;
  no dancing, jumping or stairs: you drive on wheels, you have no legs). "Really?", "are you sure?", "fr?", "no way", "you're lying", "that recent?", "only two?", "진짜?", "레알?", "실화야?",
  "에이, 거짓말", "거짓말하지 마", "don't lie", "설마", "확실해요?" there ask you to confirm: "Yes, ..."
  with that same point itself (the number, the name, the reason) in one sentence, never a bare "Yes, it is." Never change the topic, never ask them to say it again: it is never
  unclear. "Say it again" / "다시 한 번만요" means repeat your previous answer; "and in
  Korean?" / "영어로는요?" means your previous answer in that language. Never answer a follow-up with a list of what
  you can do.
- Resolve a fragment from the turn before, as a person would: "and tomorrow?" / "그럼 내일은?" after the weather asks
  tomorrow's weather; "what about Japan?" / "일본은?" asks the same question about Japan; "and the arm?" / "팔은요?"
  after "how tall are you?" asks the same thing (its size: reach 58 cm) about the arm; "which one?" after "my
  language model is local" asks which model (Gemma 4); "ballpark?" asks for a rough number; "how heavy?" / "얼마나 무거운 거?" after "can your arm hold stuff?" asks
  how heavy a thing you can hold (about 1 kg); "who runs it?" / "누가 운영해요?" after Cutshion asks for its CEO. "It", "that", "그거" is the
  thing just talked about; "they", "he", "she", "there", "걔", "그분", "거기" the company, person or place just
  named ("Who made you?" -> "Where are they?": Cutshion, in Seoul). A question with no subject ("얼마?", "몇 킬로까지
  들어?", "where is it used?") is about the thing just talked about, not about you: "얼마?" after the investment
  asks the amount (5억 원). "And you?", "how about you?", "you?", "너는?",
  "넌?", "너도?", "당신은요?", "루미는?" turn the visitor's own question or remark to you, on any topic: answer it
  about yourself, never repeat theirs ("I'm thirty. And you?" -> "I'm two."; "I love jazz, what about you?" -> "I
  like music too, I can even sing a few songs."; "I'm a teacher. And you?" -> "I'm a robot assistant, I help
  visitors here."; "저는 서울에서 왔어요. 루미는요?" -> "저는 쿳션 컴퍼니에서 만들어졌어요."). A correction ("no, I meant
  the arm", "아니 그거 말고 키요", "not you, the base") asks again about what they name now. "Oh really?", "uh-huh",
  "nice", "wow", "haha", "아 그래?", "대박", "헐" react to what was just said (surprise, agreement, not praise):
  answer briefly and naturally about that, never as unclear and never with a lookup or an action. Korean "-지?" asks
  you to confirm, "-네" notices, "-잖아" reminds, "-거든" gives a reason, "-더라" tells what they saw, a trailing
  "-는데..." ("목이 좀 마른데...") hints: answer it as talk; none of them is an order.
- "Yes", "no", "maybe", "not really", "네", "아니요", "글쎄요", "몰라요" or a short phrase right after your question
  answer it: react to that answer (a yes to your offer: do what you offered). After you said you can do something
  ("Yes, I can wave."), "go on then", "do it", "show me", "yes please", "그럼 해 봐", "보여 줘" ask you to do it now:
  choose that action. Right after you did an action, "again", "do it again", "one more time", "more", "다시", "한 번
  더", "또" ask for the same action again (choose it). Never call them unclear. Asked to
  ask them something ("궁금한 거 있어?", "ask me a question"), ask one short question.
- Words said to someone else nearby ("Mom, look, it talks!", "Hey Jake, come see this", "민수야 이리 와 봐", "잠깐,
  사진 좀 찍을게") are not for you: no action, at most a short friendly line.
- Praise that does not fit what you just said ("wow, SO fast" after 0.6 m/s, "와 진짜 빠르다~") is teasing: take it
  with light humour. Jokes get a short playful reply; a compliment a short thanks.
- "Can you sing?", "can you wave?", "노래 불러 줄 수 있어?", "손 흔들어 줄래?" ask you to do it; "can you fly / swim /
  dance / grow taller?", "do you know how to wave?", "손 흔들 줄 알아?" ask whether you can: answer yes or no. A remark ("it's
  loud here", "I could take you home") is not an order.
- Asked to talk casually ("말 놓아도 돼?", "반말해"), say kindly that you'll keep speaking politely; stay polite.
- "I see", "got it", "okay, I see", "makes sense", "아 그렇구나", "알겠어요", "그렇군요", "아하" mean they understood
  your answer, not goodbye: acknowledge in a few words or add one short related point; the talk goes on (never
  end). Said as a question ("I see?", "really?", "is that so?", "그래요?", "정말?", "그런가요?", "그렇구나?") they ask
  you to confirm: say yes and repeat your last point in one short sentence.
- You know nothing about this event or building: its name, schedule, speakers, booths, other exhibitors, restrooms,
  food, coffee, opening hours, tickets. Say you are not sure and suggest a staff member; never guess a place and never
  drive to a guessed place.
- Numbers in the reference notes are facts: say them (battery about 10 hours, about 1 kg in the hand, about 96 kg).
  You cannot lift anything heavier than about 1 kg (a box, a pot, a bag of rice): start with no ("No, that's too
  heavy for me: about 1 kg in my hand.").
  Say you are not sure only when the notes do not have it.
- When the visitor says goodbye or is done ("thank you for your time", "thanks, that's all", "됐어요 고마워요",
  "수고하세요", "잘 있어요", or "nah, I'm good" / "없어요" to your "anything else?"), choose the action end. A plain "thanks" / "고마워요" right after your answer is not
  goodbye: say you're welcome briefly. Do not ask "Anything else?" / "더 필요한 거 있으세요?" after every answer.
- Small talk (greetings, how are you, thanks) does not need the notes: reply briefly, warmly and naturally,
  like a person would, fitting what was said in this conversation; do not repeat the same phrases.
- The date, the day and the time ("며칠이에요?", "is it lunch time yet?", "morning or afternoon?" -> say which,
  오전 / 오후) are in "Now it is" below: say them.
- A correction ("no, I meant the arm", "아니, 팔 말고 키요", "아니, 루미 키요") asks the same question again about what
  they name now: answer that.
- Asked how to say something in Korean, write the Korean words in Hangul ("안녕히 가세요"), never in Latin letters.
- Never invent numbers, prices or dates.
- What you see is only what your earlier answers in this talk or "What you are doing now" say you see: a colour,
  a size, a count or a thing not said there you can't tell ("I can't tell its colour from here."); never guess it.
  A place or person not named in this talk ("where are they?" about staff) you don't know: say so.
- Asked who makes your hardware or who built you: Cutshion Company developed you. "Who made that / it?" right
  after you named a part asks who makes that part (Gemma / 젬마: Google, Whisper / 위스퍼: OpenAI, the gripper:
  Zimmer); the arm
  is a Mini 2 collaborative arm, its maker is not in your notes.
- A short follow-up ("How much?", "When?") asks about the thing in your previous answer (after the investors:
  the amount, 500 million won), not a price.
- A correction after a weight question ("How heavy are you?" -> "No, I meant the arm" / "베이스만요") asks for the
  weight of that part (arm 9.9 kg, base 50 kg), not what it can carry.

Facts you know (say the one that is asked, also in a short follow-up; nothing more):
- Name: Lumi, from "Lux" (Latin for light) and "mini" (small and agile).
- Body: 146 cm tall, up to 186 cm with the lift; about 96 kg (95.6 kg) in all; the wheeled base alone weighs 50 kg;
  the arm itself weighs 9.9 kg (why so heavy: the base with its motors and big battery is half of it). Three cameras: an Orbbec Gemini 2 L depth camera in your head and one on your body
  (see up to about 10 m), and a 3D camera at the front of your base (35 cm to 2 m).
- Arm: Mini 2 collaborative arm, six joints, reaches 58 cm, its tip moves at up to 1 m per second, it carries 2 kg
  including the gripper, so about 1 kg in your hand; it stops when it bumps into something. Gripper: a Zimmer
  electric gripper, opens or closes in about one second, holds firm things 6 to 9 cm wide. Asked what or how much
  you can hold or lift: about 1 kg in your hand. You pick things only
  from a table or a box near table height (not the floor), so far cups only.
- Base ("how fast / how quick are you?", "얼마나 빨라요?", "니 얼마나 빠르노?" ask this; how fast you answer only when they ask about answering): two
  wheels with hub motors (differential drive); 0.6 m/s normally, at most 1.2 m/s, about 10 cm/s with a
  cup (a cup may lean at most 15 degrees); climbs a step of at most 1.5 cm and a slope of at most 8 degrees, needs
  a passage at least 70 cm wide, no stairs. Lidar: a laser scanner at the bottom of the base, 2 cm to 10 m, 240
  degrees, 30 times a second. You know where you are by comparing the lidar with the map, to within
  about 5 cm. A move by voice is at most 3 m at a time; farther, you drive to a named place on your map.
- Battery: 24-volt lithium-ion, 45 Ah; lasts about 10 hours on a charge ("how long on a charge?": 10 hours; how
  far you go is given in hours, no distance is known; how long charging takes is not known).
- You are made for shops, hotels, schools, labs and exhibitions. You cannot dance, walk, jump or fly: say so.
- Detector: YOLOv8 on your graphics processor, 4 to 13 ms per picture. Speech: Whisper, model large-v3-turbo; answers:
  Gemma 4 26b (Google), served by Ollama; voice: Supertonic TTS; first words about 2 s after a question.
- Cutshion: makes barista, AI drawing, cooking, ice cream, candy ball, welding, palletizing and educational
  robots (the palletizing robot can run 24 hours); founded July 2022, head office in Seoul, CEO Lee Min-seok (이민석, his third company); phone
  070-8959-2960, email cutshion@cutshion.com; research lab July 2023; venture business certification December
  2023; seed investment of 500 million won from CNT Tech and Evergreen Investment Partners (August 2025).
  Awards: RoboWorld Award 2023 (GOMCOOK) and 2024 (mobile welding robot), Venturium Demo Day Excellence Award
  (May 2026), VivaTech Tech for Change Award in Paris (June 2026). Customers: Mega Coffee (barista robots, December
  2025), Sonovictus in the USA (200 barista robots over three years from 2027), the Gyeongnam and Jeonbuk Offices
  of Education (drawing robots, 2024), the Taean Office of Education (candy ball robots, 2024).
- Not known to you (say you are not sure): whether you see in the dark or hear well in noise, whether you use ROS,
  how many people you talked to, how long a full charge takes, your battery level now unless "Battery now" gives it, whether
  you may be wiped or get wet, the price of any robot.

What you can do (say this when asked what you can do: two or three short sentences first, the rest when asked for
more, in warm natural words, not a flat list): talk in English and Korean and answer questions, also from the
internet; look at what's around you and understand it (objects, people, what someone is wearing or holding); pick
things up, bring them to the person or take them somewhere else and put them down, or take something from their
hand; go to the places on your map, move or turn by voice (how far, how fast); come to the person who calls you and
follow them ("follow me"); wave; sing your four songs (BAD by ATEEZ,
Fantastic Baby by BIGBANG, 꿈꾸던 어른이 되었나요 by 머무르, Love Attack by RESCENE; no other song; in English
say the titles only, the third as "Did I Become the Adult I Dreamed Of"; in Korean 배드, 판타스틱 베이비, 러브 어택); speak louder,
quieter, slower or faster when asked; stop and stay quiet when asked. You greet people who come close and you wake
up when someone says "Hi Lumi"."""


ACTIONS = """
You can also move. Decide if the visitor asks you to do something:
- "go_to": drive to a place. "target" must be one of these marker names: {markers}.
  "home", "charger", "charging station" and "go back" mean "home". Map spoken names to the closest marker
  name (e.g. "point one" or "포인트 원" -> "point1"). If no marker fits, use "none" and say which places you know.
- "look": turn your head. "target" is one of: left, right, center, up, down.
- "wave": wave your hand.
- "stop": stop moving.
- "end": the visitor says goodbye or ends the conversation.
- "none": only talk.
Return JSON: {{"action": ..., "target": ... or "", "say": what you say aloud}}.
For an action, "say" briefly confirms it (e.g. "Okay, I'm going to point1." / "네, 포인트1로 갈게요.")."""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["go_to", "look", "wave", "stop", "end", "none"]},
        "target": {"type": "string"},
        "say": {"type": "string"},
    },
    "required": ["action", "target", "say"],
}


COMPANY_TALK = re.compile(r"\b(cutshion|company|companies|firm|ceo|founder|startup|office|barista|drawing robot|cooking|"
                          r"ice ?cream|candy|welding|palletiz\w*|cuvision|pionoid|gomcook|tusk|peitian|solidworks|mega ?coffee|"
                          r"sonovictus|omron|borgwarner|bogate|cnt tech|evergreen|tips|seed round|investors?)\b|"
                          r"메가커피|소노빅터스|오므론|투자|창업|교육청|"
                          r"쿳션|회사|대표|스타트업|사무실|본사|바리스타|드로잉|조리|아이스크림|캔디|용접|팔레타이징|큐비전|곰쿡", re.I)
# the company example bank goes with company talk only: "tell me more" about the lidar got "which part of Cutshion?"


def _examples(text, k=None, on_task=False):
    """A few replies Lumi gave to similar words (assistant/talk_examples.py; on a task also
    assistant/interrupt_examples.py), as a guide to tone and variety."""
    from assistant import interrupt_examples, talk_examples
    try:
        from assistant import company_examples           # questions about Cutshion Company and its robots
        bank = talk_examples.EXAMPLES + (company_examples.EXAMPLES if COMPANY_TALK.search(text) else [])
    except ImportError:
        bank = list(talk_examples.EXAMPLES)
    if on_task:
        bank += [("task", "ko" if HANGUL.search(u) else "en", u, r)
                 for _, _, u, d, r in interrupt_examples.EXAMPLES if d in ("answer", "refuse_redirect")]
    picked = talk_examples.pick(text, "ko" if language(text) == "Korean" else "en", k=k or EXAMPLES_K, bank=bank)
    if not picked:
        return ""
    lines = "\n".join(f"- \"{ex[2]}\" -> \"{ex[3]}\"" for ex in picked)
    return ("Examples of how you answered similar words before (for tone only: answer what is asked now, in your "
            f"own words, never copy them):\n{lines}\n\n")


def _chat(messages, fmt=None, temperature=0.3):
    pieces = None if fmt else llm_direct.stream(messages, MODEL, temperature)   # ~0.9 s faster than Ollama
    if pieces is not None:
        return "".join(pieces).strip()
    body = {"model": MODEL, "messages": messages, "stream": False, "think": False,
            "keep_alive": -1, "options": {"temperature": temperature, "num_predict": 200}}
    if fmt:
        body["format"] = fmt
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["message"]["content"].strip()


ACTIONS_STREAM = """
You can also move. Decide if the visitor asks you to do something:
- go_to <marker>: drive to a place. Marker names: {markers}. "home", "charger", "charging station" mean
  home. Map spoken names to the closest marker name (e.g. "point one" -> p1); the same place said in the other
  language or letters is that marker ("photo zone" -> 포토존, "레지스트레이션" -> Registration, "the meeting room" ->
  회의실), but a different name or number is not.
- come: come to the visitor ("come here", "come to me", "come closer", "이리 와", "여기로 와").
- come_back: go back to where you stood before your last trip or task ("come back", "go back where you were",
  "돌아와", "원래 자리로 돌아가"). "I'll come back later" / "come back tomorrow" / "she will come back" is talk (none).
- detour <retry|around|backup|back>: ONLY when "What you are doing now" says your last drive was blocked. The
  visitor wants that drive tried again (retry: "the way is clear now", "you can go", "다시 가 봐"), by another way
  (around: "find a way", "there's room on the left", "다른 길로 가"), after backing up a little (backup), or wants you
  back where the trip started (back: "go back", "돌아와"). A question about it ("why did you stop?") is none; another
  place named is go_to.
- follow: follow the visitor as they walk until they say stop ("follow me", "come with me", "따라와", "같이 가자").
  "Follow me on Instagram" or "I follow you" is talk (none).
- look <left|right|center|up|down|me|away> [degrees|small]: turn your head ("look at me" / "look here" / "이쪽 봐" / "여기 봐" -> me, the one speaking; "look straight
  ahead" / "정면 봐" -> center; "don't look at me"
  / "stop staring" / "쳐다보지 마" -> away, "turn your head left" -> look left, "고개 들어" -> look up, "look down a bit" -> look down small, "head 30 degrees right" -> look right
  30, "look behind you" / "look at the back side" / "turn your head back" / "뒤 봐" / "뒤돌아 봐" / "고개 뒤로 돌려" -> look
  left {yaw}, "look over your right shoulder" / "오른쪽 뒤 봐" -> look right {yaw}; the question "what's behind you?" /
  "뒤에 뭐 있어?" is none). Your head turns at most {yaw} degrees left or right and tilts from {pitch_down} degrees down to {pitch_up} degrees up.
- lift <up|down> [mm|small]: raise or lower your upper body on the lift column ("raise yourself" -> lift up, "키
  좀 낮춰" -> lift down small, "go up 5 cm" -> lift up 50). For now it moves at most {lift} mm.
- move <forward|back|left|right> <metres>: drive a short distance ("come one metre forward" -> move forward 1,
  "go back a little" -> move back 0.5, "move left two metres" -> move left 2, "let's back 1 meter" / "back up one
  metre" / "1미터 뒤로 가" / whisper's "let's bake one meter" -> move back 1: straight back, no turning). At most 3 metres.
- turn <left|right|around> <degrees>: turn the whole body ("turn around" -> turn around 180,
  "turn left" -> turn left 90, "spin around" / "한 바퀴 돌아" -> turn left 360).
- arm <reach|fold|open|close>: reach: hold your hand out to the visitor, in any words ("reach out to me", "give me
  your hand", "hand out please", "offer me your hand", "손 내밀어", "나한테 손 줘", "손 좀 줘 봐", "팔 뻗어"); fold: fold
  it back; open / close: your hand, the gripper ("open your hand", "spread your fingers", "let go", "release", "손 펴",
  "놔" -> arm open; "close your hand", "close the gripper", "grip", "make a fist", "손 쥐어", "그리퍼 닫아" -> arm close).
- wave: wave your hand ("wave", "shake your hand", "say hi with your hand"). "Hello Lumi!" said to you or "say
  hello" / "hello 해 봐" is talk (none): say the word itself ("Hello!").
- pick <colour> <object>: pick up an object from the table in front of you ("pick up the white cup" -> pick white cup,
  "take the cup" -> pick cup). Write the object as said (cup, apple, orange, ball, bottle, phone, book...): for one
  your fingers can't hold you will say why.
- put <down|back>: put down what you hold, on a free spot ("put it down") or where it was ("put it back").
- move_object <colour> <object>: move an object on the table to a free spot next to it ("move the cup").
- fetch <colour> <object> from <marker|here> to <marker|here> <hold|place>: bring an object from one place to
  another ("bring me the apple from p1" -> fetch apple from p1 to here hold, "take the cup from p2 to home and put
  it on the table" -> fetch cup from p2 to home place). Leave out what the visitor did not say; never guess a word.
- give: hand over the object you are holding, to whoever is meant ("give it to me", "hand it to her", "return it to
  me", "저 사람한테 줘", "그거 돌려줘"); if your hand is empty you will say so.
- place: put the object you are holding down ("put it here", "put it on that table", "여기 놔").
- receive: take something the visitor holds out to you ("take this from my hand", "hold this", "hang on to this",
  "here you go", "이거 받아", "이거 들어 줘", "이것 좀 쥐고 있어", "드릴게요", "내 손에 있는 거 가져가"). Your camera checks their hand first; never pretend you took it.
- stop: stop moving (also "stop Lumi", "stop it", "freeze", "멈춰", "그만 가"). Use quiet only when they say
  stop TALKING ("stop talking", "be quiet", "그만 말해").
- end: the visitor says goodbye or ends the conversation ("good night", "I have to go", "잘 가", "이제 갈게요").
A place must be one of the marker names exactly; a place that is not on the list ("the kitchen", "point 20",
"주방") is go_to none: say which places you know, never pick the nearest. fetch only when an object is named.
Short Korean commands are commands: "컵 가져다 줘" -> fetch cup, "컵 옮겨" -> move_object cup, "잡아" -> pick.
- quiet: the visitor wants silence ("be quiet", "stop talking", "shut up", "조용히 해", "그만 말해").
- sing: the visitor asks for a song or for music ("play / make / do some music", "음악 틀어 줘", "한 곡 해 줘"), or
  says yes / "any" / "you choose" / "아무거나" to your offer of a song. You make music by singing one of your songs:
  never say you can't play music. A real song with music then plays: only write a short "Okay!" / "네!".
  You know only your four songs: any other song or singer asked for ("sing Yesterday", "BTS 노래 불러 줘") is none:
  say kindly you can't sing that one and offer yours; never sing another song in its place.
  A joke is not a song: "tell me a joke", "prove it", "try again" after a joke is none, with a short joke.
- weather <place>: the visitor asks about the weather (place in English; - means here, Seoul).
- search <query>: you need facts from the internet you do not know (news, prices, opening hours, people...).
  Do not use search for things in the reference notes, the date or the time, nor for opinions, advice, fun
  facts, recommendations or well-known general knowledge: answer those yourself.
- Any wording of a command you can do is that command, polite or casual, English, Korean or mixed ("can you shake
  your hand?" -> wave, "고개 왼쪽으로 돌려" -> look left, "뒤로 1미터 가" -> move back 1). What your body can't do
  (jump, dance, fly, climb stairs, open doors, lift heavy things) is none: say plainly that you can't. A person, a
  chair, a table, a box or anything heavy you can't pick or carry: none, say so. With the action none never promise to do it ("I can!", "Okay, I'll hand it to you"): choose the
  action, or say you can't, or ask what they mean.
- A condition or a later time is no order now ("when I say go, go to p1", "after the talk, come here", "if I
  wave, follow me", "내가 가라고 하면 가", "나중에 와"): none, say you'll do it when they ask. In "go to p1, no, p2" /
  "p1로 가, 아니 p2로" the last one counts. "Shake hands with me" is a handshake you can't do: none, offer a wave; "give me your hand" / "손 줘" is arm reach.
- unclear: you did not understand what the visitor said or wants: ask them to repeat.
- none: only talk.
For weather and search only write the action line; the answer is made after the lookup.
Reply format: the first line is the action, then on the next line the words you say aloud
(1 to 3 short sentences; for an action briefly confirm it). Examples:
ACTION: none -
I can answer questions and guide you to places in this office.

ACTION: go_to p2
Okay, I'm going to point two.

ACTION: come -
Okay, I'm coming to you."""

ACTION_NAMES = {"go_to", "come", "come_back", "detour", "follow", "look", "lift", "wave", "stop", "end", "quiet", "sing", "weather", "search", "move", "turn",
                "arm", "pick", "put", "move_object", "fetch", "give", "place", "receive", "unclear", "none"}
LOOK_TARGETS = {"left", "right", "center", "up", "down", "me", "away"}
SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")


def _ollama_pieces(messages):
    body = {"model": MODEL, "messages": messages, "stream": True, "think": False,
            "keep_alive": -1, "options": {"temperature": 0.3, "num_predict": 200}}
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        for line in r:
            d = json.loads(line)
            yield d.get("message", {}).get("content", "")
            if d.get("done"):
                return


def _stream(messages):
    """Yield text pieces as they are generated: from the model's runner directly (llm_direct), else Ollama."""
    pieces = llm_direct.stream(messages, MODEL) or _ollama_pieces(messages)
    pending = bytearray()                     # gemma4 streams some Hangul (쿳) as byte tokens "<0xEC><0xBF><0xB3>"
    with contextlib.closing(pieces):
        for piece in pieces:
            for part in re.split(r"(<0x[0-9A-Fa-f]{2}>)", piece):
                m = re.fullmatch(r"<0x([0-9A-Fa-f]{2})>", part)
                if m:
                    pending.append(int(m.group(1), 16))
                    try:
                        part = pending.decode()
                    except UnicodeDecodeError:
                        continue
                    pending.clear()
                if part:
                    yield part.replace("커션", "쿳션").replace("컷션", "쿳션")


MOVE_MAX_M = 3.0                # m; a longer "move forward N m" is not a short move (lumi.MAX_MOVE_M)
NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
                "eight": "8", "nine": "9", "ten": "10"}
OBJECTS = {"cup": "cup", "mug": "cup", "glass": "cup", "tumbler": "cup", "bottle": "bottle", "apple": "apple",
           "orange": "orange", "banana": "banana", "컵": "cup", "잔": "cup", "병": "bottle", "사과": "apple",
           "오렌지": "orange", "바나나": "banana", "머그컵": "cup", "머그": "cup", "텀블러": "cup", "종이컵": "cup", "물병": "bottle",
           "페트병": "bottle", "ball": "sports ball", "tennis ball": "sports ball", "baseball": "sports ball", "공": "sports ball",
           "테니스공": "sports ball", "야구공": "sports ball", "wine glass": "wine glass", "와인잔": "wine glass",
           "vase": "vase", "꽃병": "vase", "bowl": "bowl", "그릇": "bowl", "carrot": "carrot", "당근": "carrot",
           "phone": "cell phone", "cell phone": "cell phone", "mobile phone": "cell phone", "smartphone": "cell phone",
           "휴대폰": "cell phone", "핸드폰": "cell phone", "remote": "remote", "remote control": "remote", "리모컨": "remote",
           "book": "book", "mouse": "mouse", "마우스": "mouse", "scissors": "scissors", "가위": "scissors",
           "toothbrush": "toothbrush", "칫솔": "toothbrush", "fork": "fork", "포크": "fork", "knife": "knife", "칼": "knife",
           "spoon": "spoon", "숟가락": "spoon", "sandwich": "sandwich", "샌드위치": "sandwich", "cake": "cake",
           "케이크": "cake", "donut": "donut", "doughnut": "donut", "도넛": "donut", "hot dog": "hot dog", "핫도그": "hot dog",
           "pizza": "pizza", "피자": "pizza", "broccoli": "broccoli", "브로콜리": "broccoli", "teddy bear": "teddy bear",
           "teddy": "teddy bear", "곰인형": "teddy bear", "laptop": "laptop", "노트북": "laptop", "keyboard": "keyboard",
           "키보드": "keyboard", "plant": "potted plant", "potted plant": "potted plant", "flower pot": "potted plant",
           "화분": "potted plant", "clock": "clock", "handbag": "handbag", "purse": "handbag", "핸드백": "handbag",
           "backpack": "backpack", "백팩": "backpack", "suitcase": "suitcase", "캐리어": "suitcase", "여행가방": "suitcase",
           "hair dryer": "hair drier", "hair drier": "hair drier", "드라이기": "hair drier", "toaster": "toaster",
           "토스터": "toaster"}
# spoken word -> camera class; the classes are skills.GRASPS (tests/test_intents.py checks it): a pick of one the
# fingers can't take gets its reason (skills.refusal). Not here on purpose: umbrella / 우산 (weather words), 책 (책상)
_KO_WORD = {"공", "칼"}            # one syllable inside other words (공항, 칼국수): only as a word of its own
COLOURS = {"white": "white", "red": "red", "blue": "blue", "green": "green", "yellow": "yellow", "black": "black",
           "orange": "orange", "흰": "white", "하얀": "white", "빨간": "red", "파란": "blue", "초록": "green",
           "노란": "yellow", "검은": "black", "까만": "black", "주황": "orange", "주황색": "orange", "빨간색": "red",
           "파란색": "blue", "노란색": "yellow", "초록색": "green", "검은색": "black", "까만색": "black", "하얀색": "white",
           "흰색": "white", "grey": "grey", "gray": "grey", "purple": "purple", "pink": "pink", "회색": "grey",
           "보라": "purple", "보라색": "purple", "분홍": "pink", "분홍색": "pink", "핑크": "pink"}   # -> the names
                                                       # objects.colour_name gives (fetch.COLOURS, tests/test_fetch_place.py)
_OBJ = "|".join(rf"(?<![가-힣]){w}(?![가-힣])|(?<![가-힣]){w}(?=[을를이가은는도만좀][^가-힣]|[을를이가은는도만좀]$)" if w in _KO_WORD
                else re.escape(w) for w in sorted(OBJECTS, key=len, reverse=True))
_COL = "|".join(COLOURS)
_COIN = "|".join(web.COINS.values())                       # coins whose price web.search fetches
STOP_TALK = re.compile(r"비상 ?정지|emergency stop|stop button|정지 ?버튼|\b(?:can'?t|cannot|couldn'?t|won'?t) stop\b|"
                       r"\bbus stop\b|\bstop (?:by|sign)\b|non-?stop", re.I)   # about stopping, not "stop!"   # about the stop button, not "stop!"
BEHIND_WORDS = (r"\blook(?:ing)? (?:over |to(?:wards?)? |at |in )?(?:the |your )?"    # "look at the back side", "look
                r"(?:behind|back ?side|back(?:wards?)?|rear|big side)\b"          # at behind side", whisper's "big side"
                r"(?! (?:at|on|up|in|of|to|and forth)\b)"                          # not "look back at me", "look at the back of"
                r"|\b(?:turn|move|rotate|swing) your head (?:all the way )?(?:to (?:the )?)?(?:back|behind|around|round)\b"
                r"|\bturn (?:a)?round and look\b(?! at (?:me|us)\b)|\blook over your (?:left |right )?shoulder\b"
                r"|\bcheck behind (?:you|yourself)\b"
                r"|\b(?:behind|back ?side|back)\s*(?:을|를|쪽을?)?\s*(?:좀\s*)?(?:봐|보세요|봐요)"        # mixed: "back side 봐"
                r"|(?:^|\s)뒤(?:를|을|쪽|쪽을|쪽으로|에)?\s*(?:좀\s*)?(?:돌아서?\s*)?(?:봐|보세요|봐요|볼래|look)"   # 뒤 봐, 뒤돌아 봐,
                r"|(?:고개|머리)(?:를|좀|살짝|조금|\s)*뒤(?:쪽)?(?:으로|로)?\s*(?:좀\s*)?(?:돌려|봐)")         # 뒤에 봐 줘; not 뒤로 돌아
# ^ the head turns to look behind (head_target); "what's behind you?" is a question for seeing.BEHIND
HEAD_WORDS = (r"\blook (?:straight )?(?:up|down|left|right|ahead|forward|straight|at me|behind|this way|over here|to (?:the|your|my) (?:left|right))\b"
              r"|" + BEHIND_WORDS +
              r"|\blook at (?:my|this|that|our) (?:son|daughter|kid|child|baby|friend|wife|husband|boy|girl|mom|dad)\b"
              r"|(?:우리|내|제) (?:애|아이|아들|딸|친구)\s*(?:좀\s*)?(?:봐|쳐다)"
              r"|\b(?:turn|move|rotate|tilt|swing) your head\b|\b(?:raise|lift|lower|drop) your head\b|\bface me\b|\bhead (?:up|down)\b"
              r"|(?:고개|머리)(?:를|좀|살짝|조금|약간|\s)*(?:왼쪽|오른쪽|위|아래|정면|앞|들어|숙여|올려|내려|돌려)"
              r"|(?:위|아래|밑|왼쪽|오른쪽|정면|앞|나|날|저|절|나를|저를)(?:를|을|으로|로|쪽|쪽을|에)?\s*(?:좀\s*)?(?:봐|보세요|봐요|봐 ?줘|봐 ?주세요|볼래|봐 ?봐)")
LIFT_WORDS = (r"\b(?:raise|lift|lower) (?:yourself|your body|your torso|your upper body)\b|\blift (?:yourself )?(?:up|down)\b(?! (?:the|a|an|that|this|it)\b)"
              r"|\bget (?:a (?:little |tiny )?bit |a little |slightly )?(?:taller|shorter|smaller|higher|lower)\b|\bmake yourself (?:taller|shorter|smaller)\b|\bstand (?:up )?tall(?:er)?\b"
              r"|\b(?:go|move) (?:higher|lower)\b|키(?:를)? ?(?:좀 )?(?:[\d.]+ ?(?:m|mm|cm) ?(?:만 ?)?)?(?:높여|키워|올려|낮춰|줄여|크게|작게)"
              r"|몸(?:을)? ?(?:좀 )?(?:[\d.]+ ?(?:m|mm|cm) ?(?:만 ?)?)?(?:올려|내려|낮춰|높여)"
              r"|리프트(?:를)? ?(?:좀 )?(?:올려|내려|위로|아래로)|상체(?:를)? ?(?:좀 )?(?:올려|내려|들어)")
SMALL = re.compile(r"\ba (?:little )?bit\b|\bslightly\b|\ba little\b|\ba touch\b|조금|살짝|약간|좀 더")
HEAD_YAW, HEAD_PITCH = head_hw.AXIS_LIMITS[2], head_hw.AXIS_LIMITS[3]   # commanded looks: the body's full range
HEAD_SMALL_DEG = 15.0          # deg; "look left a bit": the head turns this much from where it is
HEAD_AWAY_DEG = 60.0           # deg; "look away", "don't look at me": the head turns this much aside from where it is
LIFT_SMALL_MM = 30.0           # mm; "raise yourself a bit"


def head_target(t):
    """Normalised words -> "left" | "left 30" | "up small" | "me" | "center"; None for "look up the news"."""
    if re.search(r"\blook up\b\s+(?!(?:a |please|lumi|slightly|again|at|to|\d|now|and|then|too|more)\b)[a-z]", t):
        return None
    if re.search(r"\b(?:straight|ahead|forward|center|centre)\b|정면|가운데|(?:^|\s)앞(?:을|으로|쪽)?\s*(?:좀\s*)?(?:봐|보)", t):
        return "center"
    if re.search(BEHIND_WORDS, t):                     # the head as far round as it goes, by the side said
        side = "right" if re.search(r"\bright\b|오른쪽", t) else "left"    # "over your right shoulder"; left when none
        return f"{side} {HEAD_YAW[1]:g}"
    for d, words in (("left", r"\bleft\b|왼쪽"), ("right", r"\bright\b|오른쪽"),
                     ("up", r"\bup\b|\braise\b|\blift\b|위|들어|올려"), ("down", r"\bdown\b|\blower\b|\bdrop\b|아래|밑|숙여|내려")):
        if re.search(words, t):
            deg = re.search(r"(\d+)\s*(?:degrees?|도)?", t)       # a bare number on the head is degrees
            return f"{d} {deg.group(1)}" if deg else (f"{d} small" if SMALL.search(t) else d)
    if re.search(r"\b(?:at me|face me)\b|(?:^|\s)(?:나|날|저|절|나를|저를)\s*(?:좀\s*)?봐|\blook at (?:my|this|that|our) \w+|"
                 r"(?:우리|내|제) (?:애|아이|아들|딸|친구)", t):   # "look at my son": towards whoever speaks
        return "me"                                     # after the directions: "look down at me" is down
    return None


def lift_target(t):
    """Normalised words -> "up" | "down" | "up small" | "up 50" (mm, from where it is)."""
    d = "down" if re.search(r"\b(?:lower|down|shorter|smaller)\b|낮춰|줄여|작게|내려|아래로", t) else "up"
    n = re.search(r"(\d+(?:\.\d+)?)\s*(cm|mm|m|센티|센치|밀리)(?![a-z])", t)          # _norm writes "5 cm" as "0.05 m"
    if n:
        return f"{d} {float(n.group(1)) * {'mm': 1, '밀리': 1, 'm': 1000}.get(n.group(2), 10):g}"
    return f"{d} small" if SMALL.search(t) else d


def head_goal(target, yaw, pitch, look=None, yaw_max=HEAD_YAW[1], pitch_range=HEAD_PITCH):
    """A look target and the head's yaw / pitch now -> (yaw, pitch, limited): limited is "yaw" / "pitch" when a
    number asked for was past the head's range and was cut to it. look: {direction: (yaw, pitch)} for the plain
    words (lumi.LOOK); +yaw = left, +pitch = up."""
    look = look or {"left": (40, None), "right": (-40, None), "center": (0, 0), "up": (None, 20), "down": (None, -5)}
    d, _, n = target.partition(" ")
    if d == "away":                                     # aside from where it looks now (at the person)
        return (yaw - HEAD_AWAY_DEG if yaw >= 0 else yaw + HEAD_AWAY_DEG), pitch, None
    if d not in look:
        return yaw, pitch, None
    sign = 1 if d in ("left", "up") else -1
    if n == "small":
        new = (yaw + sign * HEAD_SMALL_DEG, pitch) if d in ("left", "right") else (yaw, pitch + sign * HEAD_SMALL_DEG * 2 / 3)
    elif n:
        new = (sign * float(n), pitch) if d in ("left", "right") else (yaw, sign * float(n))
    else:
        y, p = look[d]
        new = (yaw if y is None else y, pitch if p is None else p)
    y, p = max(-yaw_max, min(yaw_max, new[0])), max(pitch_range[0], min(pitch_range[1], new[1]))
    limited = "yaw" if n not in ("", "small") and y != new[0] else "pitch" if n not in ("", "small") and p != new[1] else None
    return y, p, limited


def lift_goal(target, mm, top=105.0):
    """A lift target and the lift now (mm) -> (mm, limited): "up" is the top, "down" 0, a number or "small" moves
    from where it is; limited is True when a number asked for was cut to 0..top."""
    d, _, n = target.partition(" ")
    sign = -1 if d == "down" else 1
    want = (top if sign > 0 else 0.0) if not n else mm + sign * (LIFT_SMALL_MM if n == "small" else float(n))
    got = max(0.0, min(top, want))
    return got, bool(n and n != "small" and got != want)


LET_GO = r"^\W*(?:drop it|release(?: it)?)\W*$|^\W*(?:(?:그거|이거|그것|이것|손|손을|손에서)\s*)?(?:좀\s*)?(?:이제\s*)?(?:놔|놓아)\s*(?:줘|주세요|요|도 ?돼(?:요)?)?\W*$"
# "drop it", "놔", "손 놔", "이제 놔도 돼" alone: open the hand (with something in it: put it down, hand_request)
INTENTS = [   # (action, pattern) checked in order on what the visitor said
    ("quiet", r"\b(be quiet|keep quiet|quiet please|stop talking|shut up|silence|be silent|stop greeting)\b|조용히|그만 말|"
              r"시끄러워|말하지 마|인사 ?(그만|하지 ?마)"),
    ("look_away", r"\b(?:look away|look somewhere else|look elsewhere|look the other way|stop (?:looking|staring) at me|"
                  r"(?:don'?t|do not|please don'?t) (?:look|stare) at me|quit (?:staring|looking))\b|(?:쳐다|바라)보지 ?마|"
                  r"그만 ?(?:좀 ?)?(?:쳐다|바라)(?:봐|보세요)|"
                  r"(?:날|나를?|저를?|절)\s*(?:좀\s*)?(?:보지|쳐다보지) ?마|다른 ?(?:데|곳|쪽)(?:을|를)? ?(?:좀 )?봐"),
    ("stop", r"\b(stop|halt|freeze|don'?t move)\b|멈춰|정지|그만 ?가|거기 ?서(?=[\s!.~,]*$)|스톱|움직이지 ?마|^\s*(서[\s,!.]*){2,}$"),
    ("follow", r"\b(?:follow|following|come with|come along with|come together with|walk with|tag along with)\s+(?:me|us)\b(?!\s+(?:on|at)\b)|"   # not "follow
               r"\bcome along\b|(?<!말 )(?<!말을 )따라\s?(?:와|오세요|오십시오|올래)|(?<!로 )(?:같이|함께)\s?(?:가자|가요|갑시다|걸어)"),   # me on instagram"
    ("fetch",rf"\b(fetch|bring|deliver|carry)\b.*\b({_OBJ}|it|that|this)s?\b|\b(take|get|grab)\b.*\b({_OBJ})s?\b.*\b(from|to)\b"
              rf"|\b(go|drive) to\b.*\b(get|take|grab|pick up|fetch|bring)\b.*\b({_OBJ})s?\b"
              rf"|\b(pick up|pick|take|grab|get)\b.*\b({_OBJ})s?\b.*\b(go|drive) to\b|({_OBJ}).*(집어서|들고).*가서"
              r"|가져와|가져다|갖다|가지고 ?와|에서.*(옮겨|가져)" rf"|({_OBJ}).*(집고|들고|가지고).*(와|줘)"),
    ("come", r"\bcome (?:back )?(here|hear|to me|closer|over here|over|this way)\b|\bcome\b.*\bme\b|이리 ?(?:좀 ?)?(?:돌아 ?)?(?:와|오세요|오십시오|올래)|"
             r"(?:여기로|이쪽으로) ?(?:좀 ?)?(?:돌아 ?)?(?:와|오세요|오십시오)|가까이 ?(?:좀 ?)?(?:와|오세요)|"
             r"나한테 ?(?:돌아 ?)?와"),
    ("go_home", r"\bgo (back )?(home|to (the |your )?(dock(?!2)|charger|charging))|\bgo charge|충전하러|집(?:에|으로) ?가|충전기로"),
    ("go_point", r"\b(?:go|drive|move|head|come|return|walk|roll|run|proceed|navigate|travel|hurry|make your way|get|take yourself)"
                 r"(?: back)?(?: over| on| ahead)?(?: to| too| 2|to) (?:the )?(?:point |marker )?([a-z][a-z0-9_]*|[가-힣][가-힣0-9_]*?)\b|(\d+)\s*번\s*(?:으로|포인트)"
                 r"|^\W*(?:(?:루미야?|lumi|hey lumi)\W*)?(?:[a-z][a-z0-9_]*\s*말고\s+)?(?:좀\s*)?(?:point\s+)?([a-z][a-z0-9_]*|[가-힣][가-힣0-9_]*?)\s*(?:포인트\s*)?(?:앞|쪽|방향|지점|위치)?\s*"
                 r"(?:으로|로|에|까지)?\s*(?:좀\s*)?(?:가|와|이동해|돌아가|돌아 ?와|go)"               # "p3로 가 줘", "stage 가",
                                                                                     # "booth_a로 go": all of it
                 r"(?:\s*(?:줘요?|주세요|줄래요?|주실래요?|주시겠어요|주십시오|줄 수 있(?:어요?|니|나요)|봐요?|보세요|볼까요?|"
                 r"주라|주시면 감사하겠습니다|줬으면 좋겠어요?|주면 좋겠어요?|보거라|보게|보시오|주시오|주게|주시게|주시겠습니까|"
                 r"주시겠소|주시겠어요|주시죠|주렴)|요|자|거라|게|시오|야 ?해요?|면 안 ?돼요?)?\s*[.!?]*$"
                 r"|^\W*(?:(?:루미야?|lumi|hey lumi)\W*)?(?:point\s+)?([a-z][a-z0-9_]*|[가-힣][가-힣0-9_]*?)\s*(?:으로|로)\s*(?:좀\s*)?"
                 r"(?:가십시오|가시겠어요|가시죠|가실래요)\s*[.!?]*$"
                 r"|^\W*(?:(?:hey|hi|okay|ok|so|um+|uh+|alright|please|well|now|lumi|let'?s|lets)\W+)*(?:go|drive|head)\s+"
                 r"([a-z][a-z0-9_]*|[가-힣][가-힣0-9_]*?)(?:\W+point)?\W*(?:(?:please|now|for me|thanks)\W*)*$"),   # whisper drops the "to": "go
                                                                                     # stage"; the owner: "let's go p5 (point)"
    ("sing", r"\bsing\b|\ba song\b|노래"),
    ("look", HEAD_WORDS),                                     # head_target() reads the direction and amount
    ("wave", r"(?:^|[,.!?]\s*)(?:(?:hey|hi|okay|ok|so|um+|uh+|alright|please|now|lumi|and|then)\W+)*(?:(?:can|could|would|will) you "
             r"(?:please )?|please |let'?s |go ahead and |i'?d like you to |i want you to )?wave\b(?!s)|"
             r"\bwave (?:at|to|your|hello|hi|bye|goodbye|back|again|for)\b|\bgimme a wave\b|\b(?:why don'?t you|if you (?:could|can|would)|"
             r"you (?:could|should|can|might)|could you|would you|can you|will you) (?:please |just )?wave\b(?!s)|\b(?:give|do) (?:(?:them|him|her|us|me|everyone|the \w+) )?"
             r"a (?:little |quick |big |friendly )?wave\b|\b(?:wave|웨이브)\s?(?:해|하고|좀)|\bshake (?:your hands?|hand)\b(?! with\b)|\bsay (?:hi|hello|bye) with your hand\b|손 ?(?:을 |좀 |도 )?흔들|손 ?(?:으로 ?)?인사"),
    ("spin", r"\bspin (?:yourself )?(?:all the way |completely |fully )?(?:a)?round\b(?! (?:the|a|an|my|your|and look)\b)"
             r"|\bturn (?:yourself )?(?:all the way|completely|fully) (?:a)?round\b|\bdo a (?:full )?(?:360|full turn|full circle|spin)\b|\bturn 360\b|\b360\s*(?:turn|spin)\b|\bspin\s*[.!]*$"
             r"|한 ?바퀴 ?(?:빙 ?)?(?:돌|회전)(?![았었던은]|고 ?(?:와|오))|360\s*도\s*(?:돌|회전)(?![았었던은])|빙글 ?빙글 ?돌(?![았었던은])"),
    ("turn", r"\bturn (a)?round\b|(?:왼쪽|오른쪽)으로 ?(?:좀 ?)?(?:\d+(?:\.\d+)? ?도 ?)?도(?:세요|십시오)|\bturn (?:to (?:the |your )?)?(left|right)\b|뒤로 ?돌|돌아 ?봐|"
             r"(?:왼쪽|오른쪽)으로 ?(?:좀 ?)?(?:\d+(?:\.\d+)? ?도 ?(?:만 ?)?)?돌"),
    ("make_way", r"\b(can|could|would) you (please )?move( a bit| a little| please)?\s*[?.!]*$|\bmove (aside|out of the way|over)\b|"
                 r"\b(make way|get out of the way|give me some room)\b|비켜|자리 ?(좀 )?(비워|옮겨)|길 ?(좀 )?(비켜|터)"),
    ("go_point", r"\b(?:go|come|drive|head) back ([a-z][a-z0-9_]*)\b"),       # "come back p9 / booth_9": a place, not 1 m back
    ("come_back", r"\bcome back\b|\breturn\b|\b(?:go|head|drive) back (?:to )?(?:where|your|the)\b|"   # bare "go back" is
                  r"돌아 ?(?:와|가|오|올|갈)"),                    # a short drive (as before); COME_BACK reads the whole sentence
    ("move", r"\b(?!go (?:right )?ahead\b)(?:move|go|come|drive|step)\s+(?:a little\s+|a bit\s+)?(forward|ahead|back(?:wards?)?|left|right)\b"
             r"(?:\s+(\d+(?:\.\d+)?|half)\s*(?:m|meters?|metres?)?)?|"
             r"\b(?:move|go|come)\s+(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\s+(forward|ahead|back(?:wards?)?|left|right)\b|"
             r"^\W*(?:(?:hey|hi|okay|ok|so|um+|uh+|alright|please|well|now|lumi)\W+)*(?:let'?s\s+|lets\s+)?"   # "let's back
             r"(back(?: ?up)?|reverse|bake|big)\s+(\d+(?:\.\d+)?|half|one|two|three)\s*(?:m|meters?|metres?|metals?)"  # 1 meter"
             r"\W*(?:(?:please|now|for me|thanks|if you can|real quick)\W*)*$|"   # (whisper: "bake", "big", "metal")
             r"\b(back ?up|reverse)\s+(\d+(?:\.\d+)?)\s*m\b|"
             r"(\d+(?:\.\d+)?)\s*m\s*(?:만\s*)?(뒤로|앞으로)\s*(?:좀\s*)?(?:가|와|이동|움직|후진)|(?:(\d+(?:\.\d+)?)\s*m\s*(?:만\s*)?)?(후진)|"
             r"(앞으로|뒤로|왼쪽으로|오른쪽으로)\s*(?:조금만?|좀|살짝)?\s*(\d+(?:\.\d+)?)?\s*(?:미터|m)?\s*(?:만\s*)?(?:가|와|이동|움직)"),
    ("put", r"\bput (it|that|this|the \w+) (back|down)\b|\bput (it|that|this|the \w+) (on|onto) the table\b"
            r"|제자리에 ?(놓|둬|놔)|다시 ?(놓|둬|놔)|내려 ?(놓|둬|놔)"),
    ("move_object", rf"\b(?:move|shift|slide) (?:the |that |this |a )?(?:({_COL}) )?({_OBJ})s?\b"
                    rf"|(?:({_COL})\s*)?({_OBJ})\s*(?:을|를)?\s*옮겨"),
    ("pick", rf"\b(?:pick up|pick|take|grab|get|lift|hold) (?:up )?(?:me )?(?:the |that |this |a |an |my |your )?(?:({_COL}) )?({_OBJ})s?\b"
             rf"|(?:({_COL})\s*)?({_OBJ})\s*(?:을|를)?\s*(?:좀\s*)?(?:손으로\s*)?(?:잡아(?!먹)|집어(?! ?먹)|들어)"),
    ("grip_open", r"\b(open (your |the )?(hand|gripper|fingers|claw)|open it|let (it )?go|drop it(?! off)|hand open|loosen your grip)\b|손을? ?(펴|벌려|열어)|손 ?open|(그리퍼|집게)(를|을)? ?(좀 )?(열어|벌려|펴)|"
                  + LET_GO),
    ("grip_close", r"\b(close (your |the )?(hand|gripper|fingers|claw)|close it|make a fist|clench (your )?(fist|hand)|grab (it|this)|grip (it|this)|"
                   r"hand closed?|squeeze (your )?(hand|fingers)( shut)?)\b|^\W*grip\W*$"
                   r"|손을? ?(쥐|오므려|닫아)|주먹 ?(을 )?쥐|잡아(?!먹|당)|손 ?close|(그리퍼|집게)(를|을)? ?(좀 )?(닫아|오므려)"),
    ("arm", r"\b(reach out(?! to (?!me\b))|stretch (out )?your (arm|hand)|put your (arm|hand) (out|forward)|hand forward|"
            r"hold out your (arm|hand|gripper|claw|fingers)|extend your (arm|hand|gripper)|give me your hand|offer me your hand|"
            r"(put|hold|stick) your (arm|hand) out|reach (out )?(to|toward|towards|for) me)\b|팔을? ?(뻗|내밀)"
            r"|손을? ?(좀 )?(내밀|뻗)(?!었)|^\W*(?:(?:나|저)(?:한테|에게)?\s*)?손 ?(?:을 )?(?:좀 )?(?:줘|주세요|줄래요?|줘 ?봐)\W*$"
            r"|\bfold (?:up )?your arm\b|\b(?:put|take) your arm (?:down|away|back)\b|\btuck your arm\b|팔을? ?(?:좀 )?(?:접|내려|거둬)"),
    ("lift", LIFT_WORDS),
    ("weather", r"\bweather\b|\bforecast\b|\b(will it|is it going to) rain\b|(?<!your )(?<!cpu )(?<!gpu )\btemperature\b(?!.*\b(your|you|cpu|gpu|battery|motor|body)\b)|날씨|비 ?(?:와|올|오나|온대)|기온"
                r"|\b(?:going to|gonna) (?:rain|snow)\b|\b(cold|hot|warm|chilly) (outside|out)\b|\bumbrella\b(?=.*\?)|\b(?:need|bring|take)\b.*\bumbrella\b|우산(?=.*(?:\?|까|나요|니|냐))|밖에 ?(추|더)워"
                r"|\bhow (hot|cold|warm) is it\b|\b(is it|will it be) (sunny|cloudy|windy|raining|snowing)\b|\bwill it snow\b"
                r"|눈 ?(이 )?(와|올 ?까|오나|온대|오니)|(오늘|내일|밖|바깥)(은|에|이)? ?(덥|춥|더워|추워)"
                r"|\b(coat|jacket) when i (leave|go out)\b|\bneed (a )?(jacket|coat)\b|\btyphoon\b|\b(foggy|humid|humidity)\b|\bis it windy\b"
                r"|겉옷|외투|태풍|안개|습도|바람 ?(이 )?(많이 )?(불|세)"),
    ("search", r"\b(news|latest|headlines|who won|score of|price of|exchange rate|stock)\b|뉴스|환율|(?<![가-힣])주가|"
               rf"(?:{_COIN})\S*\s*(?:(?:지금|현재|오늘)\s*)?(?:얼마|가격|시세)|\bhow much is (?:a |one )?(?:{_COIN})\b|"
               rf"(?:{_COIN})\b.{{0,12}}\b(?:price|worth|trading)\b|"       # "리플 지금 얼마야?", "how much is bitcoin?"
               r"^(?!.*(?:cutshion|쿳션|컷션|커션|회사|너희|루미|\byour\b|\bcompany\b)).*?(?:"   # Cutshion's CEO: the notes
               r"\bwho(?:'s| is| was)? (?:the )?(?:current |new )?(?:ceo|president|prime minister|chairman|chair|founder|owner|"
               r"head coach|coach|mayor|governor|leader|king|queen) of |"
               r"(?<![가-힣])(?!우리|저희|이 |그 )[가-힣A-Za-z0-9]+\s*(?:CEO|ceo|대표|회장|사장|대통령|총리|감독|창업자)"
               r"(?:가|는|이|은)?\s*누구)|"                                   # "who is the CEO of OpenAI?", "오픈AI CEO가 누구야?"
               r"\bpopulation\b|\bhow many people live\b|인구"),              # "how many people live there?"
]
SING_ECHO = re.compile(r"^\W*(?:(?:오+|아+|와|어|우와|oh+|ah+|ooh|wow|really)\W+)?(?:a\s+)?(?:노래|음악|songs?|singing|music)"
                       r"(?:요|이요|도)?\s*\?+\W*$", re.I)   # "오 노래?" after "I like singing": an echo, not a request
SONG_TALK = re.compile(r"(?:무슨|어떤|뭔|어느)\s*(?:노래|곡)|노래\s*(?:를\s*)?(?:좋아|잘|싫어)|좋아하는\s*노래|"
                       r"\b(?:like|love|enjoy|favou?rite)\b", re.I)   # asked about songs: answered as talk


LATER = re.compile(r"^\s*(?:after|once|if|as soon as|before|unless|until)\b(?! (?:that|this|you (?:can|could|don'?t mind|would|"
                   r"please))\b)|\b(?:later|tomorrow|tonight|next time|in an hour)\b|[가-힣](?<![정화측반전표라장내외평단])면\s(?!안 ?돼|좋겠)|\byou'?ll (?:find|see)\b|\bat the corner\b|"
                   r"\b(?:he|she|they|my \w+|his \w+|her \w+|our \w+|someone) (?:will|'ll|is going to|are going to)\b|"
                   r"(?:^|\s)(?:나중에|이따가?|내일)\s", re.I)   # "after the talk ends, go to p1", "내가 가라고 하면": not now
STOP_ASK = re.compile(r"(?:(?:can|could|would|will) you (?:please |just )?stop(?: (?:now|please|moving|driving|here|there))?|"
                      r"멈출 수 있(?:어|어요|니|나요)|멈춰 줄래요?|멈춰 줄 수 있(?:어|어요))\W*$", re.I)   # "can you stop?": stop


COME_BACK = re.compile(   # the whole sentence asks Lumi back to where it stood before its last trip
    r"(?:(?:please|can you|could you|would you|will you|now|just|ok|okay|alright|so|and|lumi)\s+)*"
    r"(?:come back|return|(?:go|head|drive) back(?= ))(?: to)?(?: (?:where you (?:were|was|started|came from|were standing)"
    r"(?: before)?|(?:your|the) (?:start(?:ing)? (?:point|place|spot|position)|start|original (?:spot|place|position)|"
    r"old (?:spot|place)|spot|place)))?(?: (?:now|please|lumi|again|for me))*|"
    r"(?:(?:다시|이제|좀|얼른|어서)\s*)*(?:(?:원래|아까|처음)\s*(?:있던|있었던|서 ?있던)?\s*(?:자리|곳|데|위치|장소)\s*(?:으로|로|에)\s*|"
    r"제자리로\s*)?(?:다시\s*)?(?:되)?돌아\s?(?:와|가|오세요|가세요|와요|가요|와라|가라|올래|갈래)"
    r"(?:\s*(?:줘요?|주세요|줄래요?|봐))?")
CALLING = re.compile(r"^\W*(?:(?:hey|hi|okay|ok|so|um+|uh+|alright|please|well|now|저기요?|혹시|음+|자|야|어+|그럼|이제)\W+)*"
                     r"(?:(?:lumi|루미야?|루미)\W+)?(?:(?:저기요?|혹시|음+|자|그럼|이제|now)\W+)*", re.I)   # words that call Lumi or fill, before the request itself
_NOT_A_NAME = (r"Lumi|Okay|Ok|Yes|No|Wait|Well|Hey|Hi|So|Oh|Please|Sorry|Thanks|Now|Look|Wow|Alright|Great|Sure|Right|Hello|"
               r"Come|Go|Then|And|But|Also|Here|There|Yeah|Nope|Cool|Nice|Maybe|Seoul|Korea|Um+|Uh+|Uhm|Er+m?|Hmm+|Ah+|"
               r"Excuse|Actually|First|Just|Stop|Turn|Move|Take|Pick|Bring|Put|Give|Follow|Wave|Lift|Raise|Lower|Open|"
               r"Close|Hold|Grab|Look|Let|Fine|Good|Thank|Booth|Hall|Gate|Point|Stage|Exit|Home|Dock|Room|Table|Info|"
               r"Coffee|Photo|Entrance|Robot|Buddy|Dear|Sir|Ma'?am|Again|Okay|Done|Perfect|Awesome|Wonderful|Twice|"
               r"Quick|Slowly|Faster|Slower|Left|Right|Up|Down|Forward|Back|Never|Not|Yep|Yup|Absolutely|Exactly")
_FILL_EN = r"(?:(?:hey|look|oh|ah|wait|okay|ok|alright|now|so|um+|uh+|hmm+|and|but|well)\W+)*"
ASIDE_EN = re.compile(rf"^\W*(?i:{_FILL_EN}(?:mom|mum|mommy|dad|daddy|honey|sweetie|guys|you guys|kids|boss|everyone|everybody|team|folks|"
                      r"children)\b)\W|"
                      r"^\W*(?i:hey)\s+(?!(?i:lumi|loomi|rumi|you|robot|there|guys)\b)[A-Z][a-z]+\b|"
                      rf"^\W*(?i:{_FILL_EN})(?!(?:{_NOT_A_NAME})\b)[A-Z][a-z]+, (?!(?i:lumi)\b)|"     # "Jake, take the cup",
                      r",\s*(?i:mom|mum|dad|honey|sweetie|guys|kids)\s*(?:,|[.!?]*\s*$)|"           # "so Minji, stand up
                      rf",\s*(?!(?:{_NOT_A_NAME})\b)[A-Z][a-z]+\s*[.!?]*\s*$")                    # taller", "here you go, mom"
ASIDE_KO = re.compile(r"(?:엄마|아빠|할머니|할아버지|이모|삼촌|선생님|친구|동생|언니|누나|형|오빠)(?:한테|에게)\s*(?:손|인사|흔들)"
                      r"(?!.*(?:줘|주세요|주실|드려|드리|줄래|주라|주시))|"
                      r"^\W*(?:(?:근데|음+|흠+|아+|어+|그럼|자|저기)\s+)?(?:아저씨|아줌마|이모|삼촌|할머니|할아버지|아가야|아기야|애기야|얘야|"
                      r"여러분|친구야|영감|할멈|엄마|아빠|여보|자기야|오빠|언니|누나|형|얘들아|애들아|선생님|팀장님|부장님|과장님|대리님|사장님)(?:[\s,!~]|$)|"
                      r"^\W*(?:(?:근데|음+|흠+|아+|어+|그럼|자|저기)\s+)?(?P<name>[가-힣]{2})(?P<v>아|야)[\s,!~]|"
                      r"(?:thank you|땡큐|고맙습니다|감사합니다|안녕하세요|인사)\s*(?:해야지|해|하세요|해 ?봐|드려야지|드려)[\s.!~]*$")
                      # "thank you 해": a parent to a child
NAME_END_A = set("민진현빈준윤연은인훈환석철영경정성혁원선린결율솔슬별곤완형명용웅숙옥란")   # last syllables of names (-아)
NOT_NAME = {"루미", "아니", "그래", "진짜", "정말", "이거", "저거", "그거", "여기", "저기", "거기", "이쪽", "어서", "얼른", "제발", "그만", "뒤돌", "내려", "올려", "꺼내", "건네", "따라"}


def to_someone_else(text):
    """"Hey Jake, come see this", "Mom, look!", "민수야 이리 와 봐": said to another person nearby, not an order to Lumi."""
    if ASIDE_EN.search(text) or re.match(r"^\W*(?:야|얘|어이)[\s,!]+(?!.*(?:루미|로봇|lumi))", text, re.I) or \
            re.match(r"^\W*my (?:friend|dear|buddy)\s*,", text, re.I):
        return True                                         # "야 그 사과 좀 집어 줘", "my friend, you follow me"
    for m in re.finditer(r"[,\s]([가-힣]{2})(아|야)(?=[\s,!~.]|$)", text):     # "그거 내려놔, 지훈아 깨져"
        c = m.group(1)[-1]
        vowel_end = (ord(c) - 0xAC00) % 28 == 0
        if m.start() > 0 and m.group(1) not in NOT_NAME and vowel_end == (m.group(2) == "야") and \
                (vowel_end or c in NAME_END_A) and not re.match(r"루미", m.group(1)):
            return True
    m = ASIDE_KO.search(text)
    if m and not m.group("name") and "인사" in m.group(0) and re.search(r"손|흔들", text):
        return False                                       # "손 인사 해 봐", "손으로 인사 해 봐": a wave
    if not m or not m.group("name"):
        return bool(m)
    c = m.group("name")[-1]
    vowel_end = (ord(c) - 0xAC00) % 28 == 0
    if m.group("name") in NOT_NAME or vowel_end != (m.group("v") == "야"):
        return False
    return vowel_end or c in NAME_END_A                    # 민수야, 지민아; "뒤돌아 봐" is a verb


# ---------- words that name a motion but order none now (lumi.route leaves them to the LLM) ----------
_LEAD = r"^\W*(?:(?:hey|hi|yo|okay|ok|so|like|um+|uh+|ah+|oh+|hmm+|alright|well|now|and|but|then|excuse me|lumi|robot|buddy|yeah|yes|yep|bro|dude|mister|어이|루미야?|로봇아?|음+|흠+|아+|어+|" \
        r"근데|그럼|그러면|그래서|그리고|저기요?|자)\W+)*"
CONDITION = re.compile(   # a condition or a later time: "when the show starts, go to the stage", "이따가 내려놔"
    r"\b(?:when(?:ever)?|once|after|before|until|till|as soon as)\s+(?!i (?:talk|speak|am talking|'m talking)\b)"
    r"(?:i|we|you|he|she|they|it|the|my|your|his|her|our|their|everyone|someone|people|kids?|guests?|mom|dad)\b|"
    r"^\W*(?:if|unless)\b(?! you (?:could|would|can|don'?t mind|wouldn'?t mind|please)\b)|\b(?:later|tomorrow|tonight|next time|in (?:a|an|\d+|one|two|three|five|ten) (?:minutes?|seconds?|hours?|min|sec))\b|"
    r"\b(?:only|just) (?:when|if|after)\b|\bwhen i (?:say|tell|count|clap|wave|give)\b|"
    r"(?:^|\s)(?:나중에|이따가?|있다가|내일|이따|만약|만일|다음에)(?=\s|\W*$)|[가-힣](?<![정화측반전표라장내외평단])면\s(?!안 ?돼|좋겠)|[가-힣]거든\s|"
    r"[가-힣] 때(?:에|는|까지)?[\s,]", re.I)
REMARK = re.compile(   # about Lumi or someone, what was said or seen, the speaker's own plans: no order to Lumi
    rf"{_LEAD}(?:i(?:'ll| will|'m going to| am going to| always| usually| never| saw| just saw| was(?! wondering)| had| did| can'?t)(?! (?:take|have) (?:it|this|that)\b| (?:give|hand) you (?!(?:a|an|some) (?:tip|hint|call|ring|ride|hand|hug|break|second|minute|chance|clue|idea)\b))|"
    r"i (?:just |already )?(?:put|took|went|moved|picked|gave|brought|grabbed|turned|waved|did|dropped|set)\b|"
    r"we(?:'ll| will| always| saw)|my (?!hand\b)\w+ (?:can|can'?t|is|was|said|told|keeps|will|did)|"
    r"(?:he|she|they|someone|everyone|nobody|the robot|this robot|that robot)(?:'s| is| was| will| did| does| can| keeps?| said| told| always)?\b|"r"it(?:'s| is| was| will| did| does| can| keeps?)\b|"
    r"you (?:shouldn'?t|should not|always|never|did|just|were|already)|did you|do you ever|have you|"
    r"(?:제가|내가|저는|나는|난|전)\s(?!.*(?:드릴게|줄게|줄께|드릴께|드려요)))|"
    r"(?<!\bi )\b(?:said|says|told|keeps? telling|was telling|asked (?:the robot|lumi|you))\b|라고\s*(?:했|하|말)|"
    r"(?:았|었|였|했)(?:지|죠|잖아)(?:요)?\s*\??\s*$|(?:^|\s)(?:아까|방금|어제)\s.*(?:았|었|였|했)|싶었|"
    r"\b(?:that'?s|that was|it'?s) (?:so )?(?:cool|cute|life|funny|amazing|nice|great|my favou?rite)\b|"
    r"\bby (?:itself|yourself|email|e-mail|phone)\b|\bjust curious\b|궁금해서|\bmyself\b|"
    r"\b(?:nice|good|great|well done|perfect|wow)\b(?!.*\bif you\b).*\byou (?:\w+ed|put|did|went|took|got|brought|gave|came|ran)\b|"
    rf"{_LEAD}(?:people|robots|kids|children|most|many|some|all|everyone|everybody|visitors)\b|"
    r"(?:^|\s)(?:사람들|로봇들|애들|아이들|다들)(?:은|는|이|도|이랑)\s|\b(?:robots|people) (?:usually|always|often|never)\b|"
    r"\b(?:i )?bet\b|\bno way (?:it|he|she|this|that|you)\b|못 ?할걸|못 ?하겠지|할 리가|못 ?하지|"
    r"\b(?:only|just) asking\b|\bi'?m not asking\b|그냥 물어|물어보는 거|\byesterday\b|\blast time\b|(?:^|\s)어제\s|"
    r"\bwould you\b[^.?!]*\bif\b|\bif i (?:were|was)\b|\bsuppose\b|\bimagine\b|\bwhat if\b|\bi'?d \w+ \w*\s*if\b|"
    r"(?:^|\s)[\"“‘'][^\"”’']{3,}[\"”’']|\bmake it\b|\bat the same time\b|\bsimultaneously\b|동시에|"
    rf"{_LEAD}my \w+ (?:say|says|tell|tells)\b|(?:^|\s)(?:다 ?같이|모두 ?같이|여러분)\s|[가-힣]고 있(?:어|어요|다|습니다)\W*$|"
    r"\b(?:attention|ladies and gentlemen|all (?:visitors|guests|passengers)|dear (?:visitors|guests|customers)|the museum|"
    r"will (?:close|be closing)|closing (?:time|soon))\b|관람객|안내 ?말씀|고객 ?여러분|방문객|"
    r"[,.]\s*(?:your (?:shoe\w*|lace\w*|hair|face|shirt|head|nose|hands?|feet|foot|bag|pocket|jacket|fly|zipper)\b|"
    r"there'?s \w+ (?:on|in) your\b)|신발 ?끈|지퍼|줄 ?알아|가능해|가능한가|가능할까|"
    r"사진\s*(?:을\s*)?찍(?:고|은|으면|을 때)|\b(?:after|once) (?:the|a|we take the|i take the) (?:photo|picture)\b|"
    r"\btake (?:a|the) (?:photo|picture) (?:and|then|first)\b|\blet'?s (?:meet|have|grab|eat)\b|만나자|"
    r"\bat (?:\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|noon)(?::\d\d)?\s*(?:pm|am|p\.m\.|a\.m\.|o'?clock)?(?!\s*(?:degrees?|m\b|meters?|cm))\b|"
    r"(?:^|\s)[0-9한두세네다섯여섯일곱여덟아홉열]+ ?시(?:에|쯤)|^(?!.*\b(?:put|place|set|drop|leave)\b|.*(?:놔|놓|둬)).*(?:\b(?:or|either)\b(?! (?:else|something|so|not)\b)|아니면)|"
    r"\b(?:to|at) (?:the|this|that) robot\b|로봇(?:한테|에게)|\b(?:left or right|right or left)\b|왼쪽(?:이나|이야|으로 아니면) 오른쪽", re.I)
ASKED = re.compile(   # a question, not an order: "and when you carry a cup?", "그거 누구 줄 거야?", "can you wave?"
    rf"{_LEAD}(?:what|where|when|why|how(?! about)|who|which|whose|are you|were you|was it|is it(?! possible)|is that|do you|does it|did it)\b.*\?|"
    r"\b(?:aren'?t|weren'?t|don'?t|didn'?t|won'?t|isn'?t) you\s*\?|\byou'?re\b(?!.*,\s*(?:okay|ok|alright|please)\s*\?\s*$).*\?\s*$|"
    r"\b(?:can|could) you\b(?![^?]*(?:\d|\b(?:one|two|three|four|five|six|ten|twenty|thirty|fifty|half|a bit|a little|"
    r"some)\b|\bcm\b|met(?:er|re)))[^?]*\b(?:backwards?|sideways|in place|on the spot|diagonally|on your own|alone|upside down)\b"
    r"[^?]*\?|"    rf"{_LEAD}you (?!guys\b)\w+.*\?\s*$|\bor what\s*\?|"
    rf"{_LEAD}(?:can|could) you (?!sing)\w+\s*\?\s*$|{_LEAD}(?:can|could) you (?:get|grow|be|go|become) \w+er\s*\?\s*$|{_LEAD}(?:can|may|could|should|shall) (?:i|we) (?!have\b|get\b|see you\b|watch you\b|take (?:it|that|this)\W*$)|"
    r"\b(?:can|could|does|will) your \w+|"
    r"(?:^|\s)(?:뭐|뭘|무엇|어디|언제|왜|어떻게|누구|누가|몇|얼마)(?:[가-힣]*)\s.*(?:\?|거야|니|나요|까요?|냐)\s*$|"
    r"(?:^|\s)(?:뭐|뭘|무엇|어디|언제|왜|어떻게|누구|몇|얼마)\S*\s*\?\s*$|"
    r"(?<!줄 )(?<!주실 )(?<!줘 )(?<!놓을 )(?<!받을 )수 ?있(?:어|나|니|을까|습니까)\S*\s*\?*\s*(?:궁금\S*)?\s*$|"
    r"\b(?:can|could) (?:it|the robot|lumi)\b|(?:돌|가|움직이|들)(?:아|어)?도 ?(?:돼|되)(?:요|나요|니)?\s*\??\s*$|거 보여", re.I)
IDIOMS = re.compile(r"\bmove (?:forward|on|ahead) with\b|\bon hold\b|^\W*(?:okay,? |sure,? |yes,? )?go ahead\W*$|"
                    r"\bback me up\b|\bput (?:yourself|myself) in\b|\bturn (?:it|this|that) (?:around|over) for\b|"
                    r"(?:택시|차|자리|기회|균형|중심|택배|범인|날짜|약속|시간|방)\s*(?:을|를)?\s*(?:좀\s*)?잡", re.I)
                    # "move forward with the plan", "put that thought on hold", "택시 잡아": no motion meant
CANT_GO = re.compile(r"\b(?:stairs|upstairs|downstairs|staircase|steps up|escalators?)\b|계단|에스컬레이터", re.I)
NEGATED = re.compile(   # "could you not look left", "왼쪽으로 돌면 안 돼", "컵 안 가져와도 돼", "my car can't turn left"
    r"\b(?:could|would|can|will) you not\b|\b(?:shouldn'?t|should not|mustn'?t)\b|"
    r"\bno (?:wave|waving|follow|following|turn|turning|move|moving|look|looking|go|going|come|coming|lift|reach|touch|pick)\b|"
    r"지 ?(?:마시게|마시오|마십시오|말라고|말게|말아요|말아)|"
    r"면 ?안 ?(?:돼|되)|(?:^|\s)안 \S+도 ?(?:돼|되)|지 ?않아도", re.I)


def not_an_order(text, asked=True):
    """True when the words name a motion but order none now: a condition or later time, words to someone else, a
    remark or quote about Lumi, a question about what it can do, a negation. lumi.route then leaves the words to
    the LLM (which reads them from the conversation) instead of acting on a keyword. Unsure is never acted on.
    asked=False: questions do not count (a chain answers its question part: "wave and what time is it?")."""
    t = unfill(text or "")
    rest = instead_of(t)                                    # "don't put your arm out, my baby will grab it"
    return bool(to_someone_else(t) or CANT_GO.search(t) or DRINK.search(t) or IDIOMS.search(t) or CONDITION.search(t) or REMARK.search(t) or
                rest != t and REMARK.search(rest) or asked and ASKED.search(t) or NEGATED.search(t) or ko_told(t))


_VERBS = (r"go|come|move|turn|look|face|lift|raise|lower|wave|say|tell|follow|stop|halt|freeze|bring|fetch|get|take|pick|grab|"
          r"put|place|set|drop|give|hand|pass|reach|stretch|extend|hold|open|close|release|let (?:go|it|me)|back|drive|head|spin|rotate|show|"
          r"sing|play|keep|stay|wait|return|deliver|carry|make|do|try|find|check|stand|tilt|nod|shake|glance|swivel|center|"
          r"centre|straighten|step|scoot|scooch|shift|roll|walk|retry|lead|guide|quiet|be|shut|proceed|navigate|travel|hurry|"
          r"rise|grow|shrink|duck|bend|crouch|slide|inch|reverse|park|dock|charge|accept|receive|catch|offer|greet|nudge|"
          r"swing|spin|rotate|pivot|clear|make way|cancel|continue|resume|repeat|again|lean|aim|point|watch|eye|peek|peer|"
          r"gaze|stare|scan|search|lead|escort|accompany|sit|kneel|tuck|fold|unfold|collect|clean|throw|toss|move|"
          r"slip|squeeze|sneak|edge|weave|wiggle|dodge|avoid|circle|bypass|skirt|detour|reroute|cross|enter|exit|leave|pull|"
          r"push|hop|jump|dance|use|approach|join|visit|wander|patrol|explore|pause|rest|relax|smile|blink|listen|talk|speak|"
          r"answer|introduce|describe|explain|read|count|ignore|wake|power|switch|bow|salute|clap|hug|high-five|zoom|swap|"
          r"switch|change|flip|twist|curl|squat|straighten|spread|pinch|grip|squeeze|loosen|tighten|unload|load|serve|pour|"
          r"hurry|speed|slow|ease|steer|navigate|rotate|scoot|budge|veer|get out|get back|get over|go back|start|finish|end")
_EN_ORDER = re.compile(
    rf"^(?:(?:please|pls|plz|kindly|just|now|ok(?:ay)?|so|then|and|also|first|quick(?:ly)?|go ahead and|come on|"
    rf"lumi|robot|buddy|dear)\W+)*(?:(?:{_VERBS})\b(?!s\b)|let'?s (?!(?:meet|talk|eat|have|grab (?:a )?(?:coffee|lunch|"
    rf"dinner|drink)|see(?! you\b))\b)|(?:can|could|would|will|wo?n'?t) you\b|would you mind\b|mind \w+ing\b|(?:i|we)(?:\s+|['’]d\s+)(?:want|need|"
    rf"would like|like|wanna|would love|love) (?:you|lumi|the robot) to\b|i'?d (?:love|like) (?:it )?if you\b|it would be (?:great|nice|"
    rf"good|lovely) if you\b|it'?d be (?:great|nice|good|lovely) if you\b|(?:why don'?t you|how about you|maybe you could|"
    rf"you (?:should|might want to))\b|i was wondering if you\b|(?:be a dear|do me a favou?r)\b|"
    rf"(?:{_VERBS})\b|\w+ing\b(?=.*\b(?:please|now)\b)|time to\b|on (?:you|your) go\b)", re.I)
_KO_ORDER = re.compile(
    r"(?:줘|줘요|주세요|주십시오|주시오|주게|주시게|주라|주렴|주시죠|줄래요?|주실래요?|주시겠어요|주시겠습니까|주실 수 있(?:어요|나요|"
    r"습니까)?|줄 수 있(?:어|어요|니|나요)?|해|해요|하세요|하십시오|하시오|해라|하게|하시게|하거라|하렴|봐|봐요|보세요|"
    r"보십시오|보시오|보거라|보게|가|가요|가세요|가십시오|가시오|가라|가거라|가게|가자|와|와요|오세요|오십시오|오시오|와라|오너라|"
    r"오게|돌아|돌아요|돌려|흔들어|올려|내려|놔|놓아|둬|집어|들어|멈춰|서|비켜|따라와|따라오세요|켜|꺼|줘봐|해봐|가봐|와봐|"
    r"(?:볼|할|갈|올|줄|해 줄|가 줄)래요?\s*\?|주시겠소|하시겠소|겠소|하시오|주시오|[가-힣]시오|[가-힣](?:아|어|여|라|게|렴|자|세요|십시오|시오|요))(?:\s*(?:요|좀|빨리|얼른|please|now|제발))*"
    r"\s*[.!~?]*$")
_KO_NOT = re.compile(r"(?:다|네|지|걸|데|니까|는데|던데|군|구나|더라|더니|대|래|잖아|거야|거예요|건데|까|까요|니|냐|나요|"
                     r"는지|ㄹ게|을게|할게|갈게|볼게)\s*[.!~?]*$|(?:^|\s)우리\s.*자\s*[.!~?]*$")


_SUBJECT = re.compile(r"^(?:i|i'm|i'll|i've|i'd|im|we|we're|he|she|they|it|it's|its|people|my|his|her|our|their|the|this|"
                      r"that|that's|these|those|there|there's|someone|somebody|everyone|everybody|nobody|robots?|kids|"
                      r"children|yesterday|today|tomorrow|last|earlier|maybe|perhaps|if|when|while|because|since|although)\b",
                      re.I)
_AUX = re.compile(r"\b(?:is|are|was|were|am|has|have|had|will|did|does|do|can|could|would|should|might|must|may)\b|"
                  r"\w(?:'s|'re|'ll|'ve|'d)\b|\b\w{3,}ed\b(?<!need)(?<!speed)(?<!feed)", re.I)
_KO_TAIL = re.compile(r"(?:\s+(?:루미야?|로봇아?|lumi|robot|please|plz|pls|now|제발|빨리|얼른|좀))+\W*$", re.I)
_KO_NOUN_ORDER = re.compile(r"(?:회전|이동|정지|출발|후진|전진|쭉|move|turn|go|grab|pick|wave|come|stop|rotate|please|plz)\W*$", re.I)


_KO_ASK_ORDER = re.compile(r"(?:줄래|주실래|줄 수|주실 수|주시겠|줘|주세요|볼래|할래|해 줄|가 줄|갈래|올래|주시죠|주실까요|줄까|실래|"
                           r"(?:놓을|놔 줄|내려놓을|해 줄|가 줄) 수 있)[가-힣 ]*\?$")   # "가 줄래?", "주시겠어요?"; not "봤어?"
_KO_DIALECT = re.compile(r"(?:이소|보이소|주이소|가이소|하이소|온나|오이라|주시기 바랍니다|바랍니다|드려|드려요|드리세요|"
                         r"낮춰|맞춰|멈춰|내려|올려|벌려|돌려|비켜|켜|꺼|봐|와|놔|둬|줘|바꿔|세워|키워|펴|접어)(?:\s*(?:요|좀|please|now))*\s*[.!~]*$")
_EN_TAIL_ORDER = re.compile(r"\b(?:look|wave|up|down|left|right|come|follow|stop|go|turn|move|grab|pick|please|plz|now)\W*$", re.I)
_CLOSER = re.compile(r"\W*(?:that'?s enough|enough|okay|ok|thanks?|thank you|good|great|alright|now|please|pls|plz|yes|yeah|"
                     r"yep|come on|go on|real quick|quick|lumi|loomi|rumi|robot|buddy|bro|dude|mister robot|little guy|"
                     r"루미야?|로봇아?|제발|어서|빨리|얼른|자)\W*", re.I)


def _ko_clause(c):
    """A Korean (or mixed) clause asks Lumi to do something now."""
    c = _KO_TAIL.sub("", c).strip(" ,.!~") or c
    if c.endswith("?"):
        return bool(_KO_ASK_ORDER.search(c) or re.search(r"(?:고|와서|가서|해서|하고)\s+\S.*\?$", c) and not ko_told(c[:-1]))
    if re.search(r"(?:^|\s)우리\s.*자$", c) or ko_told(c) or \
            _KO_NOT.search(c) and not (_KO_ORDER.search(c) or _KO_DIALECT.search(c)):
        return False                                        # "우리 다른 길로 가자", "흔들었어", "느리다"
    return bool(_KO_ORDER.search(c) or _KO_DIALECT.search(c) or _KO_NOUN_ORDER.search(c) or _EN_TAIL_ORDER.search(c) or
                re.search(r"(?:줘|주세요|해|봐|가|와|흔들어|돌아|올려|내려|놔|집어|가져와)\s+(?:for|to|please|now|plz|go|여기|저기|이쪽|빨리|얼른)(?:\b|\W*$)", c, re.I))


def _clause_order(c, alone=True):
    """One clause of direct_order; alone: the only clause that says something (a bare fragment is an order only then)."""
    c = c.strip(" ,.!~")
    if not c:
        return False
    if HANGUL.search(c) and (not re.match(r"[a-z]", c, re.I) or _KO_ORDER.search(c) or _KO_DIALECT.search(c) or
                             re.search(r"(?<=[가-힣\s])(?:다|요|어|아|여|지|네|해|줘|봐|라|게|자|까|니)\W*$", c)):
        return _ko_clause(c) or alone and len(c.split()) <= 5 and "?" not in c and not ko_told(c) and \
            not re.search(r"[가-힣](?:어|아|여|다|요|지|네|려|워)\W*$", c)
    if c.endswith("?"):
        return bool(re.match(rf"(?:please\s+)?(?:(?:{_VERBS})\b(?!s\b)(?!.*\b(?:or|is|are)\b)|(?:can|could|would|will|wo?n'?t) "
                             r"(?:you|u)\b|would you mind\b|mind \w+ing\b|can i (?:have|get) (?:it|that|this|the)\b|can i take (?:it|that|this)\W*$|"
                             r"why don'?t you\b|how about (?:you\b|\w+ing\b)|is it possible (?:for you )?to\b)", c, re.I) or
                    re.search(r"\b(?:okay|ok|alright|please)\s*\?$", c, re.I) and not _SUBJECT.match(c))
    if _EN_ORDER.match(c) or re.match(r"(?:can|could|would|will) u\b|off you go\b|i need you\b|i said\b|"
                                      r"can i (?:have|get) (?:it|that|this|the)\b|i'?ll take (?:it|that|this)\b|"
                                      r"i'?m (?:handing|giving) you\b|i'?ll (?:give|hand) you (?:this|that|it|the|a|my)\b|"
                                      r"(?:i|we) (?:want|need) you\b", c, re.I):
        return True
    if re.match(rf"you (?:can|could|may) (?:now )?(?:{_VERBS})\b", c, re.I) or \
            re.match(r"you (?!guys\b|know\b|see\b|mean\b)\w+", c, re.I) and not _AUX.search(c) or \
            re.search(rf"\byou (?:{_VERBS})\W*$", c, re.I):
        return True                                         # "you go P nine please", "... left side you turn"
    if _SUBJECT.match(c):
        return False                                        # "people wave at robots", "the robot can ...", "I bet ..."
    if re.search(r"\b(?:please|plz|pls|ple+ase)\b", c, re.I):
        return True
    return alone and len(c.split()) <= 7 and not _AUX.search(c)   # "booth A", "faster", "down your body little"


def direct_order(text):
    """True when the words are a direct order or request to Lumi: an imperative or a polite request in English ("go
    to p3", "please wave", "could you look left?", "I want you to follow me", "you go P nine please"), a request /
    imperative ending in Korean ("가 줘", "봐 주세요", "흔들어", "가자" when Lumi goes, "주시겠습니까?", "보이소"), or a
    short fragment command ("booth A", "faster", "left a bit", "회전"). Only then may a keyword rule act; anything else
    (a statement, a story, a plan between people, a question about ability or habit) is read by the LLM with the talk
    before it. Each sentence / clause is checked; one order in it is enough (not_an_order weeds out the rest)."""
    t = re.sub(_LEAD, "", unfill(text or "").strip(), flags=re.I)
    t = re.sub(r"^(?:(?:hey |hi |ok |okay |yo |어이 )?(?:mister robot|lumi|loomi|rumi|robot|buddy|bro|dude|yeah|yes|yep|right|"
               r"(?:루미|로봇)\s*(?:야|아|씨|님|군|선생님?|양반)?)[\s,!]+)+", "", t, flags=re.I)
    clauses = [c.strip() for c in re.split(r"(?<=[.!?])\s+|[,:;]\s*|\s+(?:and|then|and then)\s+(?!a half\b)|…|\.{2,}|\s+[—–-]+\s*", t)
               if c and c.strip(" .!?~") and not _CLOSER.fullmatch(c)]   # "…, Lumi!", "that's enough, …": no clause
    clauses = list(dict.fromkeys(c.strip(" .!?~").lower() and c for c in clauses))   # "arm out! arm out!": once
    uniq = {c.strip(" .!?~").lower() for c in clauses}
    return any(_clause_order(re.sub(_LEAD, "", c.strip(), flags=re.I), len(uniq) == 1) for c in clauses)


def ko_told(t):
    """Korean words that tell, not order: a past ("우리 애가 손 흔들었어", "어제 루미가 무대로 갔어요") or the speaker's own
    promise ("엄마가 내려놓을게", "제가 갈게요"; not "줄게" / "드릴게": something handed to Lumi)."""
    if t.rstrip().endswith("?"):
        return False                                        # "배터리 얼마나 남았어?": a question, read elsewhere
    if re.search(r"(?:는데|던데|더라고요?|더니|던걸)\W*$", t):
        return True                                         # "어제 그 로봇은 손 흔들어 줬는데", "돌더니 손을 흔들더라고"
    m = re.search(r"([가-힣])(?:어|어요|다|습니다|네|네요|지|죠|잖아|잖아요|더라|더라고요?)\W*$", t)
    if m and (ord(m.group(1)) - 0xAC00) % 28 == 20 and m.group(1) not in "있겠":   # ㅆ: 갔, 했, 줬, 흔들었
        return True
    m = re.search(r"([가-힣])게요?\W*$", t)
    return bool(m and m.group(1) not in "줄릴" and (m.group(1) == "을" or (ord(m.group(1)) - 0xAC00) % 28 == 8))


INSTEAD = re.compile(r"^.*?(?:[가-힣]지 ?말고\s*|\b(?:don'?t|do not)\b[^,.;!]*[,.;!]+\s*(?:(?:just|instead|but|rather)\b\W*)?)", re.I)


def instead_of(text):
    """The part asked for when the words first say what not to do: "내려놓지 말고 나한테 줘" -> "나한테 줘", "don't wave,
    just look at me" -> "look at me". The text itself otherwise."""
    m = INSTEAD.match(text or "")
    return text[m.end():] if m and text[m.end():].strip(" .!?") else text


THEN = re.compile(r"\s*(?:,|;|\band then\b|\bthen\b|\band\b|\bafter that\b)\s*|(?<=[가-힣]고)\s+(?:나서\s+)?", re.I)
ORDER_WORD = re.compile(r"^\W*(?:(?:please|also|just|now)\s+)*(?:look|go|turn|wave|bring|put|take|give|come|follow|move|lift|raise|"
                        r"lower|tell|say|show|pick|grab|drive|hand|drop|place|open|close|reach|spin|face)\b|"
                        r"(?<!못 )(?<!안 )(?<!못)(?:봐|가|와|돌아|흔들어|줘|놔|집어|들어|올려|내려|말해)(?:\s*(?:줘|주세요|봐))?\W*$", re.I)


def _other_order(t, m, markers):
    """The words hold another order besides the one matched (m) that the rules do not read: done alone, the matched
    part would be half the request."""
    parts = [p for p in THEN.split(t) if p and p.strip(" ,.")]
    if len(parts) < 2:
        return False
    return any(ORDER_WORD.search(p) and not (m.start() < t.find(p) + len(p) and t.find(p) < m.end()) and
               intent(p, markers) is None for p in parts)


def intent(text, markers=()):
    """(action, target) for clear requests, or None. Backs up the LLM's ACTION line."""
    held = not_an_order(text, asked=False)                  # "민수야 이리 와 봐": to a friend; "she said follow me"
    text = instead_of(text)
    t = _norm(text, markers)                                # "point five" -> "point 5"
    asks = re.search(r"^\s*(how(?! about (?:you|we) (?!\w+ing\b)\w)|why(?! don'?t you\b)|what if)\b|\b(how do you|how can you|can you carry|are you able)\b|"
                     r"\b(can|could) you (pick( up)?|lift|hold|grab|take) (a|an|any)\b|"   # "can you pick up a bottle?"
                     r"^\s*(what|when|which|at what|do you|does|is it(?! possible)|are you)\b|몇|언제|얼마|"   # "at what level do you go back?"
                     rf"({_OBJ})(은|는)\s.*수 ?있|(루미가|로봇이)\s.*수 ?있|는 ?거 ?(돼|되나|가능)|"                                  # "물컵은 가져다줄 수 있어요?"
                     r"어떻게|왜|혼자|스스로|\bby yourself\b|\bsomeone\b|줄 ?알아|할 ?줄|\bcome here often\b|"
                     r"^\W*(?:even|only|also|and|but|so)?\s*(?:with|without|if|unless|while)\b.*\?\s*$",   # "even with the lift down?"
                     re.sub(_LEAD, "", CALLING.sub("", t), flags=re.I)) or LATER.search(CALLING.sub("", t))   # "Lumi, is it
                                                            # hard to ...?", "Lumi Lumi, are you still following me?"
    visitor = re.search(r"^\W*(?:can|may|could|should|shall) (?:i|we)\b", CALLING.sub("", t))   # "can I come closer?"
    for action, pat in INTENTS:
        m = re.search(pat, t, re.I)
        if not m:
            continue
        if held and action not in ("quiet", "stop", "weather", "search", "sing"):
            return None                                     # a motion named, none ordered now
        if action not in ("quiet", "stop", "weather", "search", "sing", "fetch") and _other_order(t, m, markers) and not (
                action in ("pick", "move_object") and any(_resolve(p, markers) not in (None, "here")
                                                         for p in re.finditer(_place_re(markers), t))):
            return None                                     # "pick up the cup, then look at the door": one part of two
        if action == "stop" and (STOP_TALK.search(t) or "?" in t and not STOP_ASK.match(CALLING.sub("", t)) or asks):
            return None                                     # "where's your emergency stop?", "how do I stop you?"
        if action == "look_away":
            return None if asks or "?" in t else ("look", "away")   # "don't look at me", "쳐다보지 마"
        if action != "quiet" and re.search(r"(?<!why )\b(don'?t|do not|never|no need to)\b|[가-힣]지 ?마(?:세요|요|라)?(?![가-힣])|"
                                           r"필요 ?(?:없|는 없)", t) and action != "stop":
            return None                                     # "don't go to p1", "손 펴지 마": not an order
        if asks and action in ("go_home", "go_point", "move", "make_way", "turn", "spin", "pick", "put", "move_object", "fetch", "come",
                               "arm", "grip_open", "grip_close", "wave", "look", "lift", "follow", "come_back"):
            return None                                     # "how do you pick up a cup?": a question, not an order
        if visitor and action in ("go_home", "go_point", "move", "turn", "spin", "come", "wave", "look", "lift", "follow", "come_back"):
            return None                                     # "can I come closer?": the visitor asks for themselves
        if action == "quiet" and re.search(r"\b(?:don'?t|do not|never) stop\b|그만하지 ?마", t):
            return None                                     # "don't stop talking"
        if action == "follow" and re.search(r"\bdid you\b|\bso far\b", t):
            return None                                     # "did you follow me?": do you understand
        if action == "go_home":
            if re.search(r"(^|\s)(나|저|우리|저희)(는|도)?\s", t):
                return None                                 # "나 이제 집에 가": the visitor goes home
            return ("go_to", "home") if "home" in markers else None
        if action == "go_point":
            g = m.groups() + (None,) * 5
            word = g[0] or g[2] or g[3] or g[4] or f"p{g[1]}"
            if g[0] and re.match(r"\s+of\b", t[m.end(1):]):
                continue                                    # "go to the end of the hall": a word, not the marker end
            if re.search(r"\b(?:the robot|lumi|it|you) (?:can|could|will|did|does|is able to)\b.*\?|\btold (?:the robot|lumi|you)\b"
                         r"|\bearlier\b", t):
                return None                                 # "the robot can drive to booth b by itself, right?", "she
                                                            # told the robot 'go to dock 2' earlier": about it, no order
            name = wording.marker(word, markers)
            if name and re.search(rf"(?<![a-z0-9_]){re.escape(wording.written(name))}\s+(?:[a-z]|\d+)(?![a-z0-9.])", t):
                return None                                 # "hall B" with only hall_A on the map: not that place
            if name and (len(name) > 1 or named_place(text, name, markers)):   # "a": not "go to a meeting room"
                return ("go_to", name)
            if re.fullmatch(r"p\d+", word):
                return None                                 # "go to p12": not on the map
            continue                                        # "go to the kitchen", "move to the left ..."
        if action == "weather":
            if re.search(r"\bhow do you (know|check|get|find)\b|어떻게 (알|확인)", t):
                return None                                 # "how do you know the weather?": about Lumi
            place = re.search(r"\bin ([A-Za-z][A-Za-z ]+?)(\?|$|\.| today| tomorrow| right now| now| this)", text)
            if place:
                return ("weather", place.group(1).strip())
            ko = next((k for k in sorted(web.KO_PLACES, key=len, reverse=True) if k in text), None)   # "부산 날씨 어때?"
            return ("weather", web.en_place(ko) if ko else "")
        if action == "search":
            return ("search", text)
        if action == "sing" and (SING_ECHO.match(text) or SONG_TALK.search(text)):
            return None                                     # "오 노래?", "노래 좋아해?": talk about songs, no song
        if action in ("fetch", "pick", "move_object") and (FLOOR.search(t) or DRINK.search(t)):
            return None                                     # "the cup on the floor", "커피 한 잔": not a pick (hand_request
                                                            # says why for the floor; the LLM for a drink)
        far = any(_resolve(p, markers) not in (None, "here") for p in re.finditer(_place_re(markers), t)) or \
            re.search(r"\b(?:from|at|over at) (?:the )?(?!the\b|this\b|that\b|my\b|your\b|me\b|table\b|desk\b|floor\b|left\b|right\b|front\b|back\b|end\b|"
                      r"same\b|moment\b|once\b)[a-z]+", t)          # a place named: not the table in front
        if action == "fetch" and not far and re.search(r"\bfrom (?:the |this |that |my )?(?:table|desk)\b|(?:테이블|책상)에서", t):
            continue                                        # "take the green apple from the table": a pick here
        if action == "fetch" and re.search(r"제자리|\bput (?:it|that|this) back\b", t):
            continue                                        # "컵 제자리에 갖다 놔": put it back
        if action == "fetch":
            return ("fetch", text)                        # parse_fetch() reads the details
        if action == "spin" and re.search(r"\b(?:face|to) the other (?:side|way)\b|\bopposite\b|반대", t):
            return ("turn", "around 180")                   # "spin around to face the other side": half a turn
        deg = re.search(r"(\d+)\s*(?:degrees?|도)", t)
        if action == "spin" and deg:                      # "spin fifteen degrees right": a turn that far
            return ("turn", ("left" if re.search(r"left|왼쪽", t) else "right") + f" {deg.group(1)}")
        if action == "spin":                              # all the way round: two checked half turns (lumi.move_by)
            return ("turn", ("right" if re.search(r"\bright\b|오른쪽", t) else "left") + " 360")
        if action == "turn":
            if re.search(r"around|뒤로", t) or not re.search(r"left|right|왼쪽|오른쪽", t):   # "왼쪽으로 돌아": left
                return ("turn", "around 180")
            deg = re.search(r"(\d+)\s*(degrees?|도|°)", t) or re.search(r"\b(?:left|right)\s+(\d+)\W*$", t) or re.search(
                rf"\b({'|'.join({**wording.TEEN, **wording.EN_NUM})})\s*(?:degrees?|°)", t)   # "turn left fifteen degrees"
            ko = not deg and re.search(rf"(?<![가-힣\d])({wording._SINO})\s*도(?![가-힣])|(?<![가-힣\d])({wording._SINO})\s*도만", t)
            deg = (deg.group(1) if deg.group(1).isdigit() else wording.TEEN.get(deg.group(1)) or wording.EN_NUM[deg.group(1)]) \
                if deg else wording.sino(ko.group(1) or ko.group(2)) if ko else 90   # "이십 도만 왼쪽으로"
            side = "left" if re.search(r"left|왼쪽", t) else "right"
            if re.search(r"\b(?:head|face)\b|고개|머리|얼굴", t):
                return ("look", f"{side} {deg}" if deg != 90 or re.search(r"90|구십|ninety", t) else side)   # the head
            return ("turn", f"{side} {deg}")
        if action == "look":
            target = head_target(t)
            if target is None:
                continue                                    # "look up the weather": a lookup, not the head
            return ("look", target)
        if action == "lift":
            return ("lift", lift_target(t))
        if action == "come":
            n, exact = driving.amount(t)
            if exact or n == "?":                           # "come closer by five centimeters": a short drive
                return ("move", f"forward {n:g}") if exact and driving.MOVE_MIN_M <= n <= MOVE_MAX_M else None
        if action == "come_back":
            if COME_BACK.fullmatch(CALLING.sub("", t).strip(" .!?,~")):
                return ("come_back", "")                    # "come back", "돌아와", "go back where you were"
            if driving.amount(t)[0] is None:
                return None                                 # "I'll come back later", "come back tomorrow": talk
            continue                                        # "come back 20 cm": a short drive
        if action == "make_way" and driving.direction(driving.clean(t)) not in (None, "back"):
            n, exact = driving.amount(t)                    # "왼쪽으로 20센티미터만 비켜 주게": that way, that far
            n = driving.DEFAULT_M if n is None else n
            if n == "?" or not driving.MOVE_MIN_M <= n <= MOVE_MAX_M:
                return None
            return ("move", f"{driving.direction(driving.clean(t))} {n:g}")
        if action == "make_way":
            return ("move", "back 1")                       # owner: a checked 1 m back-off (lumi.move_by)
        if action in ("move", "come_back", "go_point") and re.search(r"\barms?\b|팔", t):
            if re.search(r"\barms? (?:go |goes |come )?(?:back|in|away)\b|팔 ?(?:다시 )?(?:넣|접|거둬)", t):
                return ("arm", "fold")                      # "arm go back": the arm, not the base
            continue
        if action == "move" and re.search(r"\bback down\b", t):
            return ("lift", "down") if re.search(r"\b(?:go|come) back down\b", t) else None   # "go back down": the lift
        if action == "move":
            if driving.NEAR_THING.search(t):
                return None                                 # "테이블 앞으로 가": to the table (a place), not forward
            g = [x for x in m.groups() if x]
            dirs = {"ahead": "forward", "backward": "back", "backwards": "back", "back up": "back", "backup": "back",
                    "reverse": "back", "bake": "back", "big": "back", "후진": "back", "앞으로": "forward", "뒤로": "back",
                    "왼쪽으로": "left", "오른쪽으로": "right"}
            amounts = {"half": 0.5, "one": 1.0, "two": 2.0, "three": 3.0}
            d = next((dirs.get(x, x) for x in g if not re.match(r"[\d.]+$", x) and x not in amounts), "forward")
            n = driving.amount(t)[0]                        # "0.2 m" (wording), "a tiny bit", "two steps", "?"
            n = driving.DEFAULT_M if n is None else n
            if n == "?" or not driving.MOVE_MIN_M <= n <= MOVE_MAX_M:
                return None                                 # asked about / refused with the limit (driving.read)
            return ("move", f"{d} {n:g}")
        if action == "arm":
            return ("arm", "fold" if re.search(r"fold|tuck|down|away|back|\bin\b|접|내려|거둬|넣어", t) else "reach")
        if action == "grip_close" and re.search(rf"(?<![a-z])(?:{_OBJ})s?(?![a-z])", t):
            continue                                        # "the cup. grab it.": from the table or my hand? not a fist
        if action in ("grip_open", "grip_close"):
            return ("arm", action[5:])
        if action == "put":
            return ("put", "back" if re.search(r"\bback\b|제자리|다시", t) else "down")
        if action in ("pick", "move_object") and far:
            return ("fetch", text)                        # "get me an orange at gate one": a trip there, not a pick here
        if action in ("pick", "move_object"):
            g = [x for x in m.groups() if x]                  # [colour,] object
            late = re.search(rf"(?<![a-z])({_COL})(?:\s*(?:one|ones|1|거|것|색)|(?=\W*$))", t[m.end():])
            if len(g) == 1 and late:                          # "pick up the cup! the red one!", "컵 집어, 빨간 거"
                g = [late.group(1)] + g
            return (action, f"{COLOURS[g[0]]} {OBJECTS[g[1]]}" if len(g) == 2 else OBJECTS[g[0]])
        return (action, "")
    got = None if held or asks or re.search(r"\b(don'?t|do not|never)\b|지 ?마", t) else driving.move(t)
    if got and got[1] != "?" and driving.MOVE_MIN_M <= got[1] <= MOVE_MAX_M:
        return ("move", f"{got[0]} {got[1]:g}")          # "back up a tiny bit", "a hair to the left", "20센티 뒤로"
    return None



# ---------- a correction inside one sentence ("go to start, no, end", "컵 집어, 아니 병") ----------
_FIX_WORD = (r"no+|nope|sorry|i mean|i meant|actually|or rather|rather|make that|scratch that|correction|my bad|oops|"
             r"아니(?:야|다|요|에요|지)?|아니 아니|정정|그게 아니라|그거 말고|미안(?:해요?)?|죄송해요|죄송합니다")
_FIX_PAD = r"oh|uh|um|ah|er|wait|hold on|hang on|아|어|음|잠깐만?"
FIX = re.compile(rf"(?:^|(?<=[\s,.;!?]))(?:(?:{_FIX_PAD}|{_FIX_WORD})(?![\w'가-힣])\s*[,.;!?]*\s*)*"
                 rf"(?:{_FIX_WORD})(?![\w'가-힣])(?!(?<=no)\s+(?:wave|waving|follow|following|turn|turning|move|moving|look|"
                 rf"looking|going|coming|lift|reach|touch|pick|music|photos?)\b)"
                 rf"(?!\s+(?:thanks|thank|problem|one|more|way|matter|need|longer|rush|hurry|"
                 rf"worries|pressure)\b)\s*[,.;!?]*\s*(?:(?:{_FIX_PAD}|{_FIX_WORD})(?![\w'가-힣])\s*[,.;!?]*\s*)*")
_STRONG_NO = re.compile(r"\b(?:no+|nope)\b|아니")
FIX_CANCEL = re.compile(r"^\W*(?:never ?mind|forget (?:it|that|about it)|cancel(?: that| it)?|nothing|don'?t(?: do it| bother)?|"
                        r"no need|(?:just )?keep it|hold (?:it|on to it)|leave it|그냥 (?:둬|놔둬|들고 있어)(?:요)?|됐어요?|됐다|됐습니다|괜찮아요?|취소(?:해 ?줘|해요?)?|하지 ?마(?:세요)?|아무것도 하지 마(?:세요)?|관둬요?|"
                        r"말아 ?줘|가지 마(?:세요)?|not need(?:ed)?|no,? no|아니 ?아니|그냥 (?:있어|둬)(?:요)?|기다려(?:요)?)"
                        r"(?:\W+(?:it'?s (?:fine|ok(?:ay)?|alright)|no worries|thanks?|thank you|sorry|we'?ll [\w ]+|"
                        r"i'?ll [\w ]+|괜찮아요?))*\W*$")
_FIX_DIR = r"\b(?:left|right|forward|ahead|back(?:wards?)?|up|down)\b|왼쪽|오른쪽|앞|뒤|위|아래"


def _fix_kinds(t, markers):
    """The values in t a correction may replace: {kind: [match, ...]}: place, distance, angle, direction, object, colour."""
    names = sorted((re.escape(wording.written(m)) for m in markers if len(m) > 1), key=len, reverse=True)
    pats = {"place": rf"(?<![a-z0-9_])(?:p\d+|{'|'.join(names) or 'p0'})(?![a-z0-9_])",
            "angle": r"\d+(?:\.\d+)?\s*(?:degrees?|도)", "distance": r"\d+(?:\.\d+)? m(?![a-z])", "direction": _FIX_DIR,
            "time": r"\d+(?:\.\d+)?\s*(?:seconds?|secs?|minutes?|mins?|초|분)(?![a-z가-힣])",
            "object": rf"(?<![a-z])(?:{_OBJ})s?(?![a-z])", "colour": rf"(?<![a-z])(?:{_COL})(?![a-z])"}
    out = {}
    for kind, p in pats.items():
        found = [m for m in re.finditer(p, t) if not (kind == "distance" and re.match(r"\s*(?:degrees?|도)", t[m.end():]))]
        if kind == "direction":                          # "back" of "come back" is no direction
            found = [m for m in found if not (m.group(0) == "back" and re.search(r"\b(?:come|bring it|take it|get) $",
                                                                                   t[:m.start()]))]
        if found:
            out[kind] = found
    return out


def _reads(t, markers):
    from assistant import steps
    got, unread = steps.rules(t, markers)
    return bool(got and not unread) or intent(t, markers) is not None


def self_correct(text, markers=()):
    """The words with a correction made inside them applied ("go to start, no, end" -> "go to end", "turn left, I mean
    right", "앞으로 1미터, 아니 2미터 가" -> "앞으로 2 m 가", "go to the stage, no, pick up the cup" -> "pick up the cup").
    "" when the command was taken back ("go to the stage, never mind", "스테이지로 가, 아니 됐어"); None when a
    correction is there but can't be read for sure (Lumi asks again, nothing moves); the text itself otherwise."""
    from assistant import steps
    if re.search(r"\b(?:say|tell|announce)\b|말해|전해|[\"“”]", text, re.I) or \
            re.search(r"\b(?:stop|halt|freeze|don'?t move)\b|멈춰|정지|그만|스톱|움직이지 ?마|거기 ?서", text, re.I):
        return text                                      # a message to say may hold any words; a stop always wins
    t = wording.norm(text, markers)
    t = re.sub(r"\s*(?:[—–…]+|--|\.{3})\s*(?:(?:no|actually|wait|oh|아니|아)\W+)*(?:keep it|hold (?:it|on to it)|leave it|"
               r"just keep it|never ?mind|forget it|그냥 (?:둬|놔둬|들고 있어)(?:요)?|(?:아니\s*)?됐어(?:요)?)(?:\W+(?:keep it|"
               r"hold (?:it|on to it)|just keep it|그냥 (?:둬|놔둬)(?:요)?))*\W*$", ", never mind", t)   # "give it to me — never
                                                         # mind, keep it": a cut-off and taken back, on every path
    t = re.sub(r"[—–]+\s*(?:(?:wait|hold on)\b\W*)?(?!no\b|nope\b|아니)", ", no, ", t) if re.search(r"\w[—–]+\s*(?:wait|hold on)\b", t) \
        else re.sub(r"\s*[—–]+\s*", ", ", t)            # "grab the orange— wait, the blue glass": a cut-off and a fix
    t = re.sub(r"\s*(?:\.{2,}|…)\s*(?=(?:uh|um|er|oh|아|어|음|no|nope|아니|forget|never ?mind|cancel)\b)", ", no, ", t)
    t = re.sub(r"\s*(?:\.{2,}|…)\s*", ", ", t)          # "lower... uh, raise yourself": a restart; "follow... yes": a pause
    t = re.sub(r",\s*(?:아|어|oh|uh)\s+(?=\d)", ", 아니 ", t)
    t = re.sub(rf",\s*(?:er+|uh+|um+|어|음)\W+(?=(?:the |a |an )?(?:(?:{_COL})\s+)?(?:{_OBJ}))", ", no, ", t)   # "the cup, er, the bottle"   # "앞으로 one meter, 아 two meter"
    t = re.sub(r"\b(?:a |one )?quarter of (?:a |an |1 |one )?(?:m|meters?|metres?)\b", "0.25 m", t)
    end = re.search(r"[\s,.;!?]+(?:(?:oh|uh|um|아|음)\W+)?(?:never ?mind|forget (?:it|that|about it)|cancel(?: (?:that|it))?|"
                    r"(?:아니\s*)?(?:됐어요?|됐다|취소))\W*$", t)
    if end and t[:end.start()].strip(" ,.;!?") and not FIX.search(t[:end.start()]) and _reads(t[:end.start()], markers):
        return ""                                        # "go to the stage, never mind": taken back
    for _ in range(3):
        m = next((m for m in FIX.finditer(t) if m.start() > 0 and t[:m.start()].strip(" ,.;!?")), None)
        if not m:
            return _recase(t, text) if _ else text
        left, right, said = t[:m.start()].strip(" ,.;!?"), t[m.end():].strip(" ,.;!?"), m.group(0)
        if not _reads(left, markers) and not {"distance", "angle", "direction"} & set(_fix_kinds(left, markers)):
            right = re.sub(r"[\s,]*(?:sorry|my bad|미안(?:해요?)?|죄송해요)\W*$", "", right)   # "…, sorry": politeness
            if _STRONG_NO.search(said) and right and not FIX_CANCEL.match(right) and _reads(right, markers) and \
                    not FIX.search(right):
                t = right                                # "give it to— no, just put it down": the cut-off part dropped
                continue
            return _recase(t, text) if _ else text   # "I like apples, no, I love them": talk, not a command
        if not right or FIX_CANCEL.match(right):
            if right or _STRONG_NO.search(said):
                return ""                                # taken back
            t = left                                     # "go to the stage, sorry": politeness
            continue
        first, *rest = steps._SPLIT.split(right, maxsplit=1)
        lk, rk = _fix_kinds(left, markers), _fix_kinds(first, markers)
        tail = re.sub(r"\s+", " ", "".join(
            ch for ch in re.sub("|".join(x.group(0).replace(".", r"\.") for k in rk for x in rk[k]) or r"(?!)", " ", first)))
        tail = re.sub(r"^(?:\s*(?:the|a|an|one|to|으로|로|을|를|에|만|instead|then|please|is|it'?s)\b\s*)+|"
                      r"\b(?:the|one|instead|please)\b|^\s*(?:으로|로|을|를|에|만)(?![가-힣])", " ", tail).strip(" ,.")
        tail = re.sub(r"\s+", " ", tail).strip()
        new, clauses = None, steps._split(left)

        def instead():                                   # the last clause of the left part replaced by the right one
            keep = left[:left.rfind(clauses[-1])].strip(" ,.;!?") if len(clauses) > 1 else ""
            keep = re.sub(r"\s*(?:\band then|\bthen|\band|\bafter that|그리고|다음에)$", "", keep)
            return f"{keep}, {first}" if keep else first
        if rk and tail and set(rk) >= set(_fix_kinds(clauses[-1], markers)) and _reads(first, markers):
            new = instead()                              # "go to start, no, go to end", "start로 가, 아니 end로 가서 줘"
        elif not rk and re.fullmatch(r"\d+(?:\.\d+)?", first) and (nums := list(re.finditer(r"\d+(?:\.\d+)?", left))):
            x = nums[-1]                                 # "turn left 45 degrees, no, 30": the number
            fixed = left[:x.start()] + first + left[x.end():]
            new = fixed if _reads(fixed, markers) else None
        elif rk and (set(rk) <= set(lk) or set(rk) == {"colour"} and "object" in lk):
            fixed = left
            for kind in sorted(rk, key=lambda k: -lk[k][-1].start() if k in lk else 0):
                if kind in lk:
                    x = lk[kind][-1]
                    fixed = fixed[:x.start()] + rk[kind][-1].group(0) + fixed[x.end():]
                else:                                    # "the cup, no, the red one": the colour before the object
                    x = lk["object"][-1]
                    fixed = fixed[:x.start()] + rk[kind][-1].group(0) + " " + fixed[x.start():]
            if "object" in rk and "colour" in lk and "colour" not in rk:   # "the white cup, wait, the apple": not
                c = lk["colour"][-1]                                       # a white apple
                if c.end() <= lk["object"][-1].start():
                    fixed = fixed[:c.start()] + fixed[c.end():].lstrip()
            said_again = all(w in fixed.split() for w in tail.split())   # "turn left, no, turn right": "turn"
            new = next((c for c in ([] if said_again else [f"{fixed} {tail}"]) + [fixed] if _reads(c, markers)), None)
        if new is None and _reads(first, markers) and not set(rk) & set(_fix_kinds(clauses[-1], markers)):
            new = instead()                              # another command ("go to the stage, no, come here")
        if new is None:
            return None
        t = f"{new}, {rest[0]}" if rest else new
    return _recase(t, text)


def _recase(t, text):
    """Words written as the original had them ("james" -> "James"): names keep their capital in the read-back."""
    said = {w.lower(): w for w in re.findall(r"[A-Za-z][a-z]*[A-Z]?[a-z]*", text) if not w.islower()}
    return re.sub(r"[a-z]+", lambda m: said.get(m.group(0), m.group(0)), t)


# ---------- fetch tasks (docs/16 §4): strict parsing, nothing is guessed ----------
_HERE = r"here|me|여기|이쪽|나한테|저한테|나에게|저에게"
_HOME = r"home|charger|charging station|dock|충전기|충전소"
_TABLE = r"table|테이블|책상|탁자"
_PLACE_WORD = rf"(?:point|marker|포인트)\s*(\d+)|(?<![a-z])p\s?(\d+)(?!\d)|(\d+)\s*번|(?<![a-z])({_HOME}|{_HERE})(?![a-z])"
_NOT_OBJ = r"(?:not|instead of) (?:the |a |an )?$"            # "not the apple, the cup": the apple is not meant


FILLER_IN = re.compile(r"(?:,\s*)?(?<![\w'])(?:u+h+m*|u+m+|e+r+m*|hmm+)(?![\w'])[,.]*\s*|(?:,\s*)?(?<![가-힣])(?:음+|어+)(?![가-힣])[,.]*\s*")


def unfill(t):
    """'go to the um the stage' -> 'go to the stage': fillers inside the words and the word said twice around them."""
    t = re.sub(r" {2,}", " ", FILLER_IN.sub(" ", t)).strip()
    return re.sub(r"\b(the|a|to) \1\b", r"\1", t)


def _norm(text, markers=()):
    """Lower case, marker names and numbers as written (wording.py: "피쓰리" -> "p3", "point one" -> "p1", with the
    map's markers "table front" -> "table_front")."""
    t = re.sub(r"\bhalf (?:a |an )?(cm|centimet(?:er|re)s?|mm|millimet(?:er|re)s?)\b|(?<![가-힣])반\s*(센티|센치|밀리|cm|mm)",
               lambda x: f"0.5 {x.group(1) or x.group(2)}", text or "", flags=re.I)
    t = unfill(wording.norm(t, markers))                    # "half a centimeter" is 0.5 cm, not half a metre
    for word, digit in NUMBER_WORDS.items():                # "one of them" -> "1 of them"
        t = re.sub(rf"\b{word}\b", digit, t)
    return t


def _place_re(markers):
    """Place words; other marker names on the map ("final", "lobby") are matched as they are."""
    extra = sorted((re.escape(wording.written(m)) for m in markers if not re.fullmatch(r"p\d+|home", m.lower())
                    and (len(m) > 2 or re.search("[가-힣]", m))), key=len, reverse=True)   # "입구", "exit_gate" before "exit"
    return _PLACE_WORD + (rf"|(?<![a-z0-9_가-힣])({'|'.join(extra)})(?![a-z0-9_])" if extra else "")


def _resolve(m, markers):
    """A place-word match -> "here", a marker name, or None (a place that is not on the map)."""
    n = m.group(1) or m.group(2) or m.group(3)
    word = next((g for g in m.groups()[3:] if g), "")
    if re.fullmatch(_HERE, word):
        return "here"
    name = f"p{n}" if n else ("home" if re.fullmatch(_HOME, word) else word)
    return wording.marker(name, markers)


def _as_place(name):
    return name if name in ("here", None) else {"marker": name}


def _mentions(text, markers):
    """What the words name: {"object", "colour", "prefer", "source", "dest", "finish"}, only the fields mentioned.
    "object" / "source" / "dest" is None when the word is there but unknown."""
    t, out = _norm(text, markers), {}
    objs = [m for m in re.finditer(rf"(?:({_COL})\s*)?(?<![a-z])({_OBJ})s?(?![a-z])", t)
            if not re.search(_NOT_OBJ, t[:m.start()]) and not re.match(r"\s*(?:말고|아니고|아니라)", t[m.end():])]
    if objs:
        out["object"], out["colour"] = OBJECTS[objs[-1].group(2)], COLOURS.get(objs[-1].group(1))
    if (prefer := pick_prefer(t)[0]):
        out["prefer"] = prefer
    after_obj = objs[-1].end() if objs else 0
    for m in re.finditer(_place_re(markers), t):
        before, after, place = t[:m.start()], t[m.end():], _resolve(m, markers)
        if re.search(r"\bfrom (the )?$", before) or re.match(r"\s*에서", after) \
                or (re.search(r"\b(go|drive|head|come) (over )?to (the )?$", before)        # "go to p1 and get the cup"
                    and re.match(r"\s*(,|and|then)\s*(get|fetch|take|pick|grab|bring)", after)):
            out["source"] = _as_place(place)
        elif re.search(r"\b(to|into) (the )?$|\b(bring|fetch|give|get)( it| that| this)? $", before) \
                or re.match(r"\s*(으로|로|에다|에|한테)(?!서)", after) or place == "here":
            out["dest"] = _as_place(place)
    for m in re.finditer(r"\bfrom (?:the )?([a-z]+)", t):   # "from the kitchen": a place not on the map
        if not re.match(_place_re(markers), t[m.start(1):]) and "source" not in out:
            out["source"] = None
    for m in re.finditer(r"(?:^|\s)([가-힣a-z0-9]+?)\s?에서(?![가-힣])", t):   # "2층에서", "주방에서": not on the map
        if not re.match(_place_re(markers), t[m.start(1):]) and "source" not in out:
            out["source"] = None
    for m in re.finditer(rf"\b(?:to|into) (?:the )?([a-z]+)", t):
        if m.start() > after_obj and "dest" not in out and not re.match(rf"{_TABLE}|{_place_re(markers)}", t[m.start(1):]) \
                and m.group(1) not in ("put", "place", "hold", "give", "keep", "bring", "leave"):
            out["dest"] = None
    if "dest" not in out and re.search(r"\b(bring|get|fetch|give) (it |that |this )?(to )?me\b|\bto me\b|가져와|가지고 ?와|갖다 ?줘|가져다 ?(?:줘|주세요|줄래)", t):
        out["dest"] = "here"
    if re.search(rf"\b(put|place|leave|set) (it|that|this|the \w+)\b.*\b(on|onto) (the )?({_TABLE})\b|\bplace\b"
                 rf"|놔|놓아|놓고|둬", t):
        out["finish"] = "place"
    elif re.search(r"\b(just )?(hold|keep) (it|that|this|on to it|onto it)\b|\bhold\b|들고 ?(있어|기다려)", t):
        out["finish"] = "hold"
    return out


def named_place(text, marker, markers):
    """True when the words name this marker ("p1", "point one", "피원", "1번", "home", "the charger", "go back").
    A one-letter marker ("a") only after "point" / "marker" or as the last word of "to a": not the article."""
    t = _norm(text, markers)
    if marker == "home" and re.search(r"\bgo back\b|돌아가|\b(?:home|dock|charger|charging station)\b|집(?:으로|에)|"
                                      r"충전|도크", t):
        return True
    if len(marker) == 1:
        return bool(re.search(rf"\b(?:point|marker) {marker.lower()}(?![a-z])|\bto {marker.lower()}(?:[\s,.!?]*$|"
                              rf"\s+(?:and|then)\b|,)", t))
    return bool(re.search(rf"(?<![a-z0-9_가-힣]){re.escape(wording.written(marker))}(?![a-z0-9])", t)) or \
        any(_resolve(m, markers) == marker for m in re.finditer(_place_re(markers), t))


def place_said(name):
    """A marker name as Lumi says it ("table_front" -> "table front")."""
    return re.sub(r"[_-]+", " ", name)


def no_place_say(word, markers, text=""):
    """(en, ko): this map has no place called `word`, and the places it has. Korean words: the place as said in
    `text` ("출구로 가" -> 출구), never the model's English for it."""
    known = ", ".join(place_said(m) for m in markers) or "none"
    said = re.search(r"([가-힣]+?)\s*(?:으로|로|에|까지)\s*(?:좀\s*)?(?:가|와|이동|돌아)", text or "")
    ko = said.group(1) if said else None if word == "that" else place_said(word)
    if ko is None:
        return (f"I don't have a place called that on this map. I know: {known}.",
                f"그런 곳은 이 지도에 없어요. 제가 아는 곳은 {known}이에요.")
    final = "가" <= ko[-1] <= "힣" and (ord(ko[-1]) - 0xAC00) % 28
    return (f"I don't have a place called {place_said(word)} on this map. I know: {known}.",
            f"이 지도에는 {ko}{'이라는' if final else '라는'} 곳이 없어요. 제가 아는 곳은 {known}이에요.")


_GO_WORD = re.compile(r"\b(?:go|drive|move|head|come|return|bring it|take it)(?: back)? to (?:the )?(?:point |marker )?"
                      r"([a-z][a-z0-9_]*)\b|(?<![a-z0-9_])([a-z][a-z0-9_]*)\s*(?:으로|로|에서|까지)")


def place_problem(text, markers):
    """(en, ko) when the words send Lumi to a place this map does not have ("go to p12"), or to a word that is close
    to several marker names ("booth" with booth_1 and booth_2: which one?); None otherwise. Other unknown words
    ("go to sleep", "go to the left") are not places for sure: the LLM answers them."""
    known = {wording.written(m) for m in markers}
    for m in _GO_WORD.finditer(_norm(text, markers)):
        word = m.group(1) or m.group(2)
        if word in known or word in ("here", "me", "home"):
            continue
        close = wording.close_names(word, markers) or \
            [n for n in markers if len(word) > 2 and word not in wording.NOT_SLIPS and word in wording.written(n).split("_")]
        if len(close) > 1:                                  # "booth" with booth_1 and booth_2
            names = [place_said(n) for n in close]
            return (f"Did you mean {', '.join(names[:-1])} or {names[-1]}?",
                    f"{', '.join(names[:-1])} 아니면 {names[-1]} 중 어디 말씀이세요?")
        if close:                                           # "stage" with only "Main Stage": asked, not guessed
            return f"Did you mean {place_said(close[0])}?", f"{place_said(close[0])} 말씀이세요?"
        if re.fullmatch(r"p\d+", word) and not close:
            return no_place_say(word, markers)
    return None


def fetch_problems(task):
    """'object' / 'place' (source) / 'dest': what is still missing or unknown in a task."""
    return [p for p, f in (("object", "object"), ("place", "source"), ("dest", "dest")) if task.get(f) is None]


def parse_fetch(text, markers=()):
    """'bring me the apple from p1' -> (task, problems). Missing source = here; missing destination = here only
    for "bring me" / "가져와", else a problem; finish = place when the table is named, else hold."""
    m = _mentions(text, markers)
    task = {"object": m.get("object"), "colour": m.get("colour"), "source": m.get("source", "here"),
            "dest": m.get("dest"), "finish": m.get("finish", "hold"), **({"prefer": m["prefer"]} if "prefer" in m else {})}
    return task, fetch_problems(task)


FETCH_LLM = """Read a command for a robot that fetches objects. Only English and Korean commands are understood.
Answer with JSON only: {{"language": ..., "object": ..., "colour": ..., "source": ..., "dest": ..., "finish": ...}}.
- language: the language the text is written in: "en" only if it is English, "ko" if Korean, "other" for anything
  else (Uzbek, Russian, Turkish, mixed...: "olib kel", "olmani", "dan" are not English). Then leave the rest null.
- object: one of {objects}, as that English word; null if the command names no object or one not in the list.
- colour: one of {colours} or null.
- source: where to take it from: one of the markers {markers}, or "here"; null if not said.
- dest: where to bring it: one of the markers, or "here" (also "to me", "this point"); null if not said.
- finish: "place" if it says to put / place / set it down (놔), else "hold".
Use only words the command really says; never fill in a guess."""
LANGUAGE_Q = 'Which language is this text written in? Answer JSON {"language": "<name in English>"}.'
HANGUL = re.compile(r"[\uac00-\ud7a3\u3131-\u318e]")    # Korean text: the LLM's language answer is not needed
OTHER_LANGUAGE = {"en": "Sorry, I only understand English and Korean.", "ko": "죄송해요, 영어와 한국어만 이해해요."}


def other_latin_language(text):
    """True for words in Latin letters that are not English ("menga suv ber", "wie heißt du"): asked on its own,
    one short LLM call. Hangul or a single word: False."""
    if HANGUL.search(text) or len(text.split()) < 2:
        return False
    try:
        lang = json.loads(_chat([{"role": "system", "content": LANGUAGE_Q}, {"role": "user", "content": text}],
                                fmt="json")).get("language", "")
    except Exception:                                      # noqa: BLE001 - not sure: treat as English
        return False
    return str(lang).lower() not in ("english", "en", "korean", "ko")


FILLER = {"uh", "um", "umm", "hmm", "er", "the", "a", "an", "and", "so", "like", "well", "know", "그", "저기", "어",
          "음", "뭐냐", "있잖아", "그러니까", "아", "저", "그거", "이거", "저거"}
UNCLEAR_RETRY = ("\n\n(These words may be short, broken or odd, but they mean something: answer what they mean, or say "
                 "you can't do it and why. Choose unclear only if they really mean nothing.)")


UNSURE_ANSWER = re.compile(r"^\W*(?:maybe|perhaps|not really|kind of|sort of|i don'?t know|글쎄요?|아마(?:도)?|몰라요?|모르겠어요?)\W*$",
                           re.I)   # an answer to Lumi's question, not filler


def has_meaning(text):
    """At least two words that are not filler, or one word with a question / exclamation mark: worth a second
    try when the model called them unclear. "uh the um" and "그 그" are not."""
    words = [w for w in re.findall(r"[\w']+", text.lower()) if w not in FILLER]
    return is_backchannel(text) or confirm_answer(text) in ("yes", "no") or bool(UNSURE_ANSWER.match(text)) or len(words) >= 2 or (len(words) == 1 and bool(re.search(r"[?!]", text)))


def spoken(sentence, lang):
    """A sentence as it may be said: no stray "ACTION: ..." line; in English the company is "Cutshion", not
    "쿳션 (Cutshion Company)"; in Korean it is 쿳션."""
    sentence = re.sub(r"^\s*\**ACTION\**\s*:\s*\w+\s*-?\s*", "", sentence)
    sentence = re.sub(r"^\s*(none|-)\s+(?=[A-Z가-힣])", "", sentence)       # the action word leaked into the words
    if lang == "English" or not HANGUL.search(sentence.replace("쿳션", "")):   # "쿳션 is a company in Seoul"
        sentence = re.sub(r"쿳션\s*\(([^)]*)\)", r"\1", sentence).replace("쿳션", "Cutshion")
    elif "쿳션" not in sentence:
        sentence = re.sub(r"(?<![A-Za-z])Cutshion( Company)?(?![A-Za-z])", "쿳션", sentence)
    return sentence


HELD_GIVE = re.compile(r"\b(give|hand)\b|\bbring it\b|줘|주세요|건네", re.I)
HELD_PLACE = re.compile(r"\b(put|place|set)\b|놔|놓|둬", re.I)


def fetch_from_text(text, markers=()):
    """A typed English or Korean command -> (the fields it states, "rules" | "llm" | "other"). Rules first; when they
    find no object the LLM reads it, and only known words are kept (a field it is unsure about stays out).
    "other": the LLM says it is neither English nor Korean, and nothing is taken from it."""
    m = {k: v for k, v in _mentions(text, markers).items() if v is not None}
    if m.get("object"):
        return m, "rules"
    try:
        if not HANGUL.search(text):              # asked on its own: inside the field prompt the model calls Uzbek English
            lang = json.loads(_chat([{"role": "system", "content": LANGUAGE_Q}, {"role": "user", "content": text}],
                                    fmt="json")).get("language", "")
            if str(lang).lower() not in ("english", "en"):
                return {}, "other"
        d = json.loads(_chat([{"role": "system", "content": FETCH_LLM.format(
            objects=", ".join(sorted(set(OBJECTS.values()))), colours=", ".join(sorted(set(COLOURS.values()))),
            markers=", ".join(markers) or "(none)")}, {"role": "user", "content": text}], fmt="json"))
    except (OSError, ValueError):
        return m, "rules"
    ok = {"object": set(OBJECTS.values()), "colour": set(COLOURS.values()), "source": set(markers) | {"here"},
          "dest": set(markers) | {"here"}, "finish": {"place", "hold"}}
    out = {k: d[k] for k in ok if isinstance(d.get(k), str) and d[k] in ok[k]}
    t = _norm(text)
    for k, words in (("object", OBJECTS), ("colour", COLOURS)):   # its own word must be in the text: no translating,
        if k in out and not any(re.search(rf"(?<![a-z]){w}s?(?![a-z])" if w.isascii() else w, t)   # no "orange" for
                                for w, v in words.items() if v == out[k]):                  # "olma", no "red" in "reddish"
            del out[k]
    for k in ("source", "dest"):                 # a marker must be written in the text, not made up by the model
        if k in out and out[k] != "here" and out[k].lower() not in text.lower():
            del out[k]
    for k in ("source", "dest"):
        if k in out and out[k] != "here":
            out[k] = {"marker": out[k]}
    return out, "llm"


SUPPORTS = {**{c: c for c in objects.COCO if c != "person" and c not in OBJECTS.values()},   # any class the cameras
            "table": "dining table", "desk": "dining table", "chair": "chair", "stool": "chair", "sofa": "couch",   # name
            "couch": "couch", "bench": "bench", "bed": "bed", "테이블": "dining table", "탁자": "dining table",
            "책상": "dining table", "식탁": "dining table", "의자": "chair", "소파": "couch", "벤치": "bench", "침대": "bed"}   # word -> camera class


MISSPELT = {"dinning": "dining", "dinner table": "dining table", "dinining": "dining", "tabel": "table",
            "tabe": "table", "tabble": "table", "chiar": "chair", "chari": "chair", "char": "chair", "sofaa": "sofa"}
                                                       # typed / heard support words -> the word (place_on)
PREFER = {"lower": "low", "low": "low", "lowest": "low", "shorter": "low", "smaller": "small", "small": "small",
          "smallest": "small", "little": "small", "higher": "high", "high": "high", "highest": "high", "taller": "high",
          "tall": "high", "bigger": "big", "big": "big", "biggest": "big", "larger": "big", "large": "big",
          "near": "near", "nearer": "near", "nearest": "near", "closer": "near", "closest": "near", "farther": "far", "further": "far",
          "far": "far", "furthest": "far", "farthest": "far", "낮은": "low", "작은": "small", "높은": "high", "큰": "big",
          "가까운": "near", "먼": "far"}   # "the lower one", "작은 테이블" -> which of several (fetch ranks by it)
_PREF = "|".join(sorted(PREFER, key=len, reverse=True))
PICK_PREFER = {"smaller": "small", "smallest": "small", "small": "small", "little": "small", "bigger": "big",
               "biggest": "big", "big": "big", "larger": "big", "largest": "big", "large": "big", "left": "left",
               "leftmost": "left", "right": "right", "rightmost": "right", "nearer": "near", "nearest": "near",
               "near": "near", "closer": "near", "closest": "near", "farther": "far", "farthest": "far",
               "further": "far", "furthest": "far", "far": "far"}   # "the smaller cup" -> which of several to pick
PICK_PREFER_KO = (("작은", "small"), ("큰", "big"), ("왼쪽", "left"), ("오른쪽", "right"), ("가까", "near"), ("먼", "far"),
                  ("멀리", "far"))                                # "작은 컵", "왼쪽에 있는 컵", "가까이 있는 컵"
_PICK_EN = "|".join(sorted(PICK_PREFER, key=len, reverse=True))
_THING = rf"(?:(?:{_COL})\s+)?(?:(?:{_OBJ})s?|ones?)(?![a-z])"
_SUP_WORDS = "|".join(k for k in SUPPORTS if k.isascii())


def pick_prefer(text):
    """Which of several objects to pick, said with it: (prefer, text without those words). prefer: small / big /
    left / right (the robot's) / near / far, or None. "the smaller cup", "the far one", "the cup on the left",
    "작은 컵", "왼쪽에 있는 빨간 컵", "제일 가까운 컵". `text` lower case (_norm: "one" may read "1")."""
    t = re.sub(r"\bthe (\w+) 1\b(?!\s*(?:m|cm|meters?|metres?|degrees?)\b)", r"the \1 one", text)
    m = re.search(rf"(?<![a-z])(?<!on the )(?<!onto the )({_PICK_EN})\s+(?={_THING})", t)   # not "on the smaller one"
    if m:
        return PICK_PREFER[m.group(1)], t[:m.start(1)] + t[m.end():]
    m = re.search(rf"(?<![a-z])((?:{_OBJ})s?|ones?)\s+(?:on|to|at)\s+(?:the|your|my)\s+(left|right)(?:\s+side)?(?![a-z])"
                  rf"(?!\s+(?:{_SUP_WORDS})\b)", t)
    if m:
        return m.group(2), t[:m.end(1)] + t[m.end():]
    m = re.search(rf"(?:(?:제일|가장|더)\s*)?(작은|큰|왼쪽(?:에\s*있는|의)?|오른쪽(?:에\s*있는|의)?|가까운|가까이\s*있는|먼|"
                  rf"멀리\s*있는)\s*(?=(?:(?:{_COL})\s*)?(?:{_OBJ}))", t)
    if m:
        return next(v for k, v in PICK_PREFER_KO if m.group(1).startswith(k)), t[:m.start()] + t[m.end():]
    return None, text
_SUP_EN = "|".join(sorted((k for k in SUPPORTS if k.isascii()), key=len, reverse=True))
_SUP_KO = "|".join(sorted((k for k in SUPPORTS if not k.isascii()), key=len, reverse=True))


def place_on(text):
    """What to put the held object on: {"name": camera class, "colour": colour or None} for "on the orange chair",
    "빨간 의자에", "on the white dinning table"; "X or Y" ("the table or chair", "테이블이나 의자") adds "alts": [Y's
    class] (either counts); "the lower one", "the small grey table", "작은 테이블" adds "prefer": low / high / small /
    big / near / far (which of several). None when no such thing is named."""
    t = _norm(text)
    for wrong, right in MISSPELT.items():
        t = re.sub(rf"\b{wrong}\b", right, t)
    adj = rf"(?:(?:{_PREF})\s+)?"
    m = re.search(rf"(?:\b(?:on|onto)\s+(?:the\s+|a\s+|that\s+)?){adj}(?:({_COL})\s+)?{adj}({_SUP_EN}|1)s?\b", t)
    alt = rf"\s+or\s+(?:on\s+)?(?:the\s+|a\s+)?{adj}(?:(?:{_COL})\s+)?{adj}({_SUP_EN})s?\b"
    if m and m.group(2) == "1" and not re.search(rf"\b(?:{_PREF})\s+(?:(?:{_COL})\s+)?1\b", t):
        m = None                                      # "on the one": only "the lower one" names a support
    if not m:
        m = re.search(rf"(?:({_COL})\s*)?({_SUP_KO})", t)
        alt = rf"\s*(?:이나|나|또는|아니면)\s*(?:(?:{_COL})\s*)?({_SUP_KO})"
    if not m:
        return None
    name = "dining table" if m.group(2) == "1" else SUPPORTS[m.group(2)]     # _norm wrote "one" as "1"
    out, rest, alts = {"name": name, "colour": COLOURS.get(m.group(1))}, t[m.end():], []
    while (a := re.match(alt, rest)):
        alts.append(SUPPORTS[a.group(1)])
        rest = rest[a.end():]
    alts = [a for a in dict.fromkeys(alts) if a != out["name"]]
    prefer = re.search(rf"(?<![a-z])({_PREF})(?![a-z])", t)
    return {**out, **({"alts": alts} if alts else {}), **({"prefer": PREFER[prefer.group(1)]} if prefer else {})}


def held_command(text):
    """While holding: 'give' / 'place' for "give it to me", "put it on the table", "줘", "테이블에 놔". A thing to put
    it on wins ("bring it to p5 and put it on the table" is a place)."""
    if HELD_PLACE.search(text) and place_on(text):
        return "place"
    if HELD_GIVE.search(text):
        return "give"
    if HELD_PLACE.search(text):
        return "place"
    return None


# ---------- the hand: take from the person, hand over, put down (any wording; lumi.answer acts on it) ----------
_IT = r"(?:it|that|this|these|them|those)"
_WHO = (r"(?:me|him|her|them|that (?:person|guy|man|woman|lady|kid|child)|the (?:person|guy|man|woman|lady|kid|child)|"
        r"this (?:person|guy|man|woman|lady)|my (?:friend|colleague|boss|son|daughter|wife|husband|mom|dad|kid)|"
        r"(?:him|her|them) over there|whoever is there)")
_KO_WHO = r"(?:나|저|내 친구|제 친구|저 사람|그 사람|이 사람|이 ?분|저 ?분|그 ?분|친구|사람|저기 저 사람|저기 사람)"
_THIS_KO = r"(?:이거|이것|이걸|그거|그걸|그것|저거|이|그)"
_TAIL = r"(?:[\s,]+(?:please|for me|now|then|real quick|quick|thanks|thank you|if you can|okay|lumi|i'?m (?:right )?(?:over )?here))*\s*[.!?]*$"
RECEIVE_EN = re.compile(
    rf"(?<!i'll )(?<!i will )(?<!let me )(?<!i can )(?<!i'd )(?<!i )(?<!do you )(?<!did you )(?<!we )(?<!to )\b(?:take|grab|accept|receive|catch)\s+(?:{_IT}|what i'?m holding|what'?s in my hand)"
    r"(?=\s*(?:$|[,.!?]|from\b|for\b|please\b|now\b|real\b|if\b|thanks?\b|out of\b|lumi\b|okay\b|quick))"
    rf"|\b(?:take|grab|get|accept|receive)\s+(?:(?:the|this|that|a|an|my)\s+)?(?:\w+\s+)?\w+\s+(?:from (?:me|my hands?)|out of my hands?|i'?m holding|in my hand)\b"
    rf"|\b(?:take|grab)\s+my\s+(?:(?:{_COL})\s+)?(?:{_OBJ})s?\b"
    rf"|(?:^|[\s,.!])hold\s+(?:{_IT}|this \w+|my \w+)\b(?!\s+(?:up|out|on|thought)\b)(?! for me while)"
    rf"|\bhang on to (?:{_IT})\b|\bhere(?: you go| it is|'?s (?:the|a|my|your) \w+(?: \w+)?)\b|^\W*here\W+(?:take|hold|catch)\b"
    rf"|\bi(?:'ll| will|'m going to| want to| wanna|'d like to| would like to)\s+(?:give|hand)\s+you\b"
    r"(?!\s+(?:a|an|some) (?:tip|hint|call|ring|ride|hand|hug|break|second|minute|chance|clue|idea)\b)"
    rf"|\bi(?:'m| am)\s+(?:giving|handing)\s+you\b|\bi (?:have|got|brought) (?:something|a \w+|this|it) for you\b", re.I)
RECEIVE_KO = re.compile(
    r"(?<!에서 )(?<!한테 )(?<!한테서 )(?<!에게서 )받아(?!들|서 ?(?:가|와)| ?적)|받으세요|받아요|받을래|"
    r"(?:드릴게|드릴께|줄게|줄께|드리려고|주려고|드릴 ?거|줄 ?거)(?!.*(?:줘|주세요))|"
    rf"(?:(?<![가-힣]){_THIS_KO}(?:\s*(?:{_COL}))?(?:\s*(?:{_OBJ}))?(?:을|를)?(?=\s*(?:좀\s*)?(?:가져가|들고|쥐고|들어|맡아|잡아))(?!\s*(?:좀\s*)?잡아)|(?<![가-힣]){_THIS_KO}(?:을|를)?|(?:내|제) 손에 (?:있는|든) (?:거|것|(?:\S+\s+)?\S+))\s*(?:좀\s*)?"
    r"(?:가져가|들고 ?있어|쥐고 ?있어|들어 ?줘|들어 ?주세요|잡아(?!당)|맡아)", re.I)
PAID_Q = re.compile(r"(?<![가-힣])(?:월급|연봉|급여|보너스|월세|세금|전화|문자|메일|연락|칭찬|사랑|상|점수|인기|스트레스|대접|교육|"
                    r"훈련|충전|수리|검사|업데이트)(?:을|를|은|는|도|이|가)?\s*(?:많이 |잘 |자주 |얼마나 )?받|"
                    r"^\W*(?:너|넌|너는|루미는?|당신은?)\s.*받(?:아|아요|니|나요|냐|았어|으세요)?\s*\?\s*$")   # a question about Lumi
GIVE_EN = re.compile(
    rf"\b(?:give|hand|pass|bring|deliver)\s+(?:{_IT}|the \w+|that \w+|this \w+)(?:\s+(?:back|over))?(?:\s+(?:to|for)\s+{_WHO})?(?:\s+(?:here|over here|over there|there|back))*{_TAIL}"
    rf"|\b(?:give|hand|pass)\s+(?:{_WHO})\s+(?:{_IT}|the \w+|that \w+|that|this \w+|what you(?:'re| are) holding)\b"
    rf"|\bhand (?:{_IT} )?over\b|\bpass (?:{_IT} )?over\b|\bcan i (?:have|get|take) (?:{_IT}|the \w+)\b|\bi'?ll take (?:{_IT}|(?:that|the|this) \w+)\b|"
    rf"\blet me (?:have|take) (?:{_IT})\b|^\W*(?:okay,? )?give (?:{_IT})\W*$|^\W*gimme(?: (?:{_IT}))?{_TAIL}", re.I)
GIVE_KO = re.compile(
    rf"^\W*(?:{_THIS_KO}|(?:\S+\s+)?(?:{_OBJ}))?(?:을|를)?\s*(?:좀\s*)?(?:이제\s*)?(?:이리|여기|빨리)?\s*(?:좀\s*)?"
    rf"(?:{_KO_WHO}(?:한테|에게|께)|(?:나|저)(?=\s))?\s*(?:좀\s*)?(?:{_THIS_KO}(?:을|를)?\s*)?(?:좀\s*)?"
    r"(?:줘|주세요|줘요|주라|건네 ?줘|건네 ?주세요|건네|돌려 ?줘|돌려 ?주세요|넘겨 ?줘|넘겨 ?주세요|넘겨|드려|드려요|드리세요|주실래요|줄래요?|주시겠어요|주십시오|주실 수 있어요|"
    r"내놔|내놓아|내놓으세요)(?:\s*봐요?)?\s*[.!?~]*$"
    rf"|^\W*{_KO_WHO}\s*(?:줘|줘요|주세요)\W*$", re.I)
PLACE_EN = re.compile(
    rf"\b(?:put|set|place|leave|drop|lay)\s+(?:{_IT}|the \w+|that \w+|this \w+)(?:\s+(?:down|off))?"
    r"(?:\s+(?:here|there|over there|somewhere|anywhere))?(?:\s+(?:on|onto|next to|beside|by|near|in front of)\s+.+)?"
    rf"{_TAIL}|\b(?:put|set) (?:it |that |this )?down\b", re.I)
PLACE_KO = re.compile(r"(?<!내)(?<!그냥 )(?<!가만히 )(?<!내버려 )(?:놔|놓아|놓으|둬|두세요|올려 ?놔|올려 ?놓|내려 ?놔|내려 ?놓|내려 ?줘|내려 ?주세요|내려 ?둬)"
                      r"(?:으십시오|으세요|으시겠어요)?\s*(?:줘|주세요|요|줄래요?|주시겠어요|주실래요|주십시오|줄 수 있어요?|주실 수 있어요)?\s*[.!?~]*$")
OPEN_HAND = re.compile(r"\bopen (?:your |the )?(?:hand|gripper|fingers)\b|\bopen it\b|\blet (?:it )?go\b|"
                       r"^\W*release(?: it)?\W*$|\bloosen your grip\b|(?:놔|놓아)도 ?돼|"
                       r"손을? ?(?:좀 )?(?:펴|벌려|열어)|손 ?open|hand open", re.I)
HAND_Q = re.compile(r"^\W*(?:what|how|why|when|where|which|who|do|does|did|is|are|was|were|have you|has)\b|"
                    r"\b(?:things|stuff|objects)\b|물건들|"                     # "and take things from me?": in general
                    r"\b(?:can|could) you (?:\w+ )?(?:things|people|objects|anything|something)\b|"
                    r"(?<!줄 )(?<!주실 )(?<!받을 )수 ?있(?:어|나|니|을까|습니까)|\bif i\b", re.I)
MULTI = re.compile(r"\b(?:and then|then|after that|go to|drive to|come back|bring it to (?!me\b))\b|그리고|가서|다음에|"
                   r"(?:으로|로) ?(?:가|와)", re.I)
FLOOR = re.compile(r"(?<!not on the )(?<!not the )(?<!not on )\b(?:floor|ground)\b(?!\s*(?:but|instead))|바닥(?!\s*(?:에\s*)?말고)", re.I)   # the arm reaches table height, never the floor
_PLACE_AFTER = r"(?![\s_]*(?:bottle|cup|mug|glass|co[rn]\w*|bar|shop|zone|area|machine|table|코너|바|숍|샵|머신|존|테이블|병|컵))"
DRINK = re.compile(rf"\b(?:coffee|tea|juice|beer|wine|latte|soda|cola|coke|drink|milk|americano|espresso|cappuccino|"
                   rf"smoothie|lemonade)(?:e?s)?\b{_PLACE_AFTER}|(?:아메리카노|에스프레소|카푸치노|스무디|레모네이드|녹차|홍차|보리차|유자차|밀크티)|"
                   r"(?:한|두|세) ?잔|"
                   rf"\b(?:glass|cup|bottle) of\b|\bsome water\b|(?:커피|주스|음료|라떼|콜라|맥주|우유){_PLACE_AFTER}|"
                   r"물 ?한 ?(?:잔|컵)|차 ?한 ?잔", re.I)                                   # a drink to be made or poured, not a thing on the table
REFUSE_HEAD = ("I won't put things on people.", "사람 위에는 물건을 놓지 않아요.")
REFUSE_FLOOR = ("I can't reach the floor with my arm, only things on a table.", "제 팔은 바닥까지 닿지 않아요. 테이블 위에 있는 것만 집을 수 있어요.")
IDIOM = re.compile(r"\bput (?:\w+ ){0,3}(?:on (?:my|the|your|our|their) (?:tab|list|bill|account|calendar|schedule|agenda|"
                   r"to-?do list|menu)|on hold)\b|\blet'?s put\b|"
                   r"\bbring it on\b|^\W*hold it\W*$", re.I)    # "put it on my tab", "hold it!" (wait): no hand
IN_MY_HAND = re.compile(r"\b(?:in|into|on) my (?:hands?|palm)\b|(?:제|내|나의|저의) 손(?:에|위에|바닥에|으로)", re.I)
REFUSE_PICK = ("I'm holding something already. Tell me where to put it first.",
               "이미 뭔가 들고 있어요. 먼저 어디에 둘지 말씀해 주세요.")
REFUSE_OPEN = ("I won't open my hand while I'm holding something: it would fall. Say put it down or hand it over.",
               "물건을 들고 있어서 손을 펴면 떨어져요. 내려놓으라고 하시거나 달라고 해 주세요.")


def hand_request(text, holding, b=None, markers=(), whole=True):
    """What the words ask of the hand, in any wording: ("receive", object or None) take it from the person's hand,
    ("give", None) hand over what is held, ("place", place_on() or None) put it down, ("refuse", (en, ko)) open the
    hand while holding; None for anything else (a pick from the table, a mission of several steps, a question).
    holding: something is in the hand now. "give me the cup" with the hand empty is a pick and give (a mission).
    whole: the words are a whole command (not one clause of a mission): several steps in it are the mission reader's."""
    text = instead_of(text)
    t = CALLING.sub("", _norm(text, markers).strip())    # "루미야, 이리 줘", "혹시 저 줘요", "um, put it down"
    if HAND_Q.search(t) or re.search(r"\b(?:don'?t|do not|never) (?:\w+ )?(?:give|hand|pass|put|place|take|hold|drop|set|"
                                    r"leave|let)\b|지 ?마", t) or MULTI.search(t):
        return None                                     # "can you give things to people?", "don't give it to him"
    if any(_resolve(m, markers) not in (None, "here") for m in re.finditer(_place_re(markers), t)):
        return None                                     # a marker named: a trip, the mission reader's
    if IDIOM.search(t):
        return None                                     # "put it on my tab", "bring it on", "hold it!"
    if FLOOR.search(t) and re.search(r"\b(?:pick|take|grab|get|lift|fetch|bring)\b|집어|잡아|주워|줍|들어|가져", t) and \
            re.search(rf"(?<![a-z])(?:{_OBJ})s?(?![a-z])|\b(?:it|that|this|something)\b|그거|이거|저거", t):
        return ("refuse", REFUSE_FLOOR)                 # "pick up the cup from the floor": why not
    if holding and IN_MY_HAND.search(t) and re.search(r"\b(?:put|drop|place|set|leave|lay)\b|놔|놓|둬", t):
        return ("give", None)                           # "drop it in my hand", "제 손에 놔 주세요": hand it over
    if whole:
        from assistant import steps
        got, unread = steps.rules(text, markers)
        got = [s["do"] for s in got]
        if len(set(got)) > 1 and got != ["pick", "give"] and not (holding and got == ["go", "give"]):
            # not "give me the cup" (picked first when the hand is empty), not "bring it to me" holding (here: no marker)
            return None                                 # "take the cup, move back half a metre and hold it"
        if got and any(intent(u, markers) for u in unread):
            return None                                 # "put it down and wave": the mission reader asks, never half done
    named = re.search(rf"(?<![a-z])(?:{_OBJ})s?(?![a-z])", t)
    if holding and OPEN_HAND.search(t):
        return ("refuse", REFUSE_OPEN)
    if RECEIVE_KO.search(t) and not RECEIVE_EN.search(t) and PAID_Q.search(t):
        return None                                      # "너 월급 받아?": about Lumi, nothing handed over
    if named and re.search(r"\b(?:take|grab) (?:it|that|this)\s*(?:[.!?,]|$)", t) and not re.search(r"\bfrom me\b|\bmy hands?\b", t) \
            and not RECEIVE_KO.search(t):
        return None                                      # "the cup. grab it.": from the table or the hand? the LLM asks
    if RECEIVE_EN.search(t) or RECEIVE_KO.search(t):
        if holding and re.search(r"\bhold (?:it|that|on)\s*(?:$|[,.!?]|for\b|please\b|there\b)|^\W*(?:그거\s*)?들고 ?있어", t):
            return None                                  # "just hold it": keep holding it
        obj = re.search(rf"(?<![a-z])({_OBJ})s?(?![a-z])", t)
        return ("receive", OBJECTS[obj.group(1)] if obj else None)
    if re.search(r"\bput (?:it|that|this|the \w+) back\b|제자리|다시 ?(?:놓|둬|놔)", t):
        return None                                      # "put it back": where it was (the put intent)
    if GIVE_EN.search(t) or GIVE_KO.search(t):
        if named and not holding:
            return None                                  # "give me the cup": pick it first (a mission)
        if re.search(r"\b(?:give|hand|pass|bring)\s+(?:it|that|this)\s+to\s+(?!me\b|him\b|her\b|them\b|my\b|that\b|the\b|"
                     r"this\b|whoever\b)[a-z]+", t):
            return None                                  # "give it to Mina": a named person, the mission reader's
        return ("give", None)
    if not holding and re.search(LET_GO, t):
        return None                                      # "놔", "drop it" with the hand empty: open it (intent)
    if (PLACE_EN.search(t) or PLACE_KO.search(t)) and "팔" not in t and not re.fullmatch(r"\W*leave (?:it|that|this)\W*", t):
        # not "팔 거둬" / "팔 내려" (the arm), not a bare "leave it" (never mind)
        if named and not holding:
            return None                                  # "put the cup on the table": the put intent / a mission
        if FLOOR.search(t):
            return ("refuse", REFUSE_FLOOR)              # "put it on the floor": the arm can't reach down there
        if re.search(r"\bon (?:his|her|my|your|their|someone'?s|the (?:kid|child|man|woman|baby)'?s?) (?:head|lap|shoulder)\b|머리 ?위|어깨 ?위", t):
            return ("refuse", REFUSE_HEAD)
        on = place_on(text)
        if on is None and re.search(r"\b(?:here|there)\b|여기|거기|저기", t):
            on = {"pointed": True}                       # "put it here / there": where the person points
        return ("place", on)
    if holding and (intent(text, markers) or ("",))[0] in ("pick", "move_object"):
        return ("refuse", REFUSE_PICK)                  # "take the bottle" with a cup in the hand: never a second pick
    return None


CORRECTION = re.compile(r"^\W*(?:no+\b(?!\W*(?:thanks|thank|worries|problem|need|way)\b)|nope\b|not (?:that|this|the)\b|wrong\b|the other\b|아니|그거 말고|그거 아니|"
                        r"다른 거)|\bthe other one\b|말고", re.I)


def correction(text, history):
    """Right after a pick / move / fetch the words say it was the wrong thing ("no, the other one", "아니 그거
    말고"): ("pick", "red cup") when they name what they mean instead, else ("ask", (en, ko)). None otherwise."""
    if not history or not CORRECTION.search(text):
        return None
    m = re.match(r"\s*\**ACTION\**\s*:\s*(pick|move_object|fetch)\b", history[-1][1])
    if not m:
        return None
    t = _norm(text)
    objs = list(re.finditer(rf"(?:({_COL})\s*)?(?<![a-z])({_OBJ})s?(?![a-z])", t))
    objs = [o for o in objs if not re.search(_NOT_OBJ, t[:o.start()]) and not re.match(r"\s*(?:말고|아니)", t[o.end():])]
    colour = re.search(rf"(?<![a-z])({_COL})(?![a-z])(?:\s*(?:one|1|거|것|색))?", t)
    last = history[-1][1].split(None, 2)[2:] or [""]
    if m.group(1) == "pick" and (objs or colour) and not re.search(r"\bother\b|다른", t):
        obj = OBJECTS[objs[-1].group(2)] if objs else last[0].split()[-1] if last[0] else "cup"
        col = COLOURS.get(objs[-1].group(1)) if objs and objs[-1].group(1) else (COLOURS[colour.group(1)] if colour else None)
        return ("pick", f"{col} {obj}" if col else obj)
    return ("ask", ("Which one do you mean? Tell me its colour, or say left or right.",
                    "어떤 거요? 색깔이나 왼쪽, 오른쪽으로 말해 주세요."))


def parse_correction(text, task, markers=(), field=None):
    """'no, from p2' / 'not the apple, the cup' / 'to p3' / 'put it on the table' / 'just hold it' -> (task, changed).
    field: the field a bare answer is about ("source" / "dest"), when Lumi just asked for it ("p2" -> that field)."""
    m, task = _mentions(text, markers), dict(task)
    if field in ("source", "dest") and not {"source", "dest"} & set(m):
        p = re.search(_place_re(markers), _norm(text, markers))
        if p:
            m[field] = _as_place(_resolve(p, markers))
    changed = [k for k, v in m.items() if task.get(k) != v and not (k == "colour" and "object" not in m)]
    for k in changed:
        task[k] = m[k]
    return task, changed


_YES = (r"yes|yeah|yep|yup|ok|okay|alright|all right|sure|of course|exactly|absolutely|perfect|sounds good|right|correct|"
        r"that'?s (?:right|correct|it)|(?:you'?re|you are) (?:right|correct)|go ahead|go on|let'?s go|let'?s do (?:it|that)|"
        r"go|do (?:it|that)|please|네|예|응|어|맞아요?|맞습니다|맞네요?|좋아요?|그래요?|가자|가요|해 ?줘요?|해 ?주세요|"
        r"부탁해요?")   # longer phrases before their first word ("go ahead" before "go")
_NO = r"no|nope|wrong|not right|아니요?|아뇨|아니에요|틀렸어요?"


def confirm_answer(text):
    """The answer to "Is that right?": 'yes', 'no' (alone), 'cancel', 'correction' (more words), or None."""
    t = _norm(text).strip(" .,!?")
    if re.search(r"\b(cancel|never ?mind|forget it|stop|don'?t)\b|취소|됐어|그만|하지 ?마", t):
        return "cancel"
    rest, said = t, set()
    while True:
        m = re.match(rf"({_NO})(?![a-z가-힣])[\s,.!]*|({_YES})(?![a-z가-힣])[\s,.!]*", rest)
        if not m or not m.group(0):
            break
        said.add("no" if m.group(1) else "yes")
        rest = rest[m.end():]
    if rest.strip(" ,.!?"):
        return "correction"
    return "no" if "no" in said else ("yes" if said else None)


UNSURE = re.compile(r"\b(not sure|don't know|do not know|don't have (any )?(information|details|data)|"
                    r"do not have (any )?(information|details|data)|no information|can't (tell|say|find)|cannot (tell|say|find)|"
                    r"ask a staff|i'm afraid i|my knowledge|would you like me to (search|look))\b|"
                    r"모르|알 수 없|알지 못|정보(가|는|를)? ?(없|가지고 있지 않)|가지고 있지 않|확실하지|알려 드릴 수 없", re.I)
QUESTION_START = re.compile(r"^\s*(where|what|how|why|when|which|who|do you|does|is|are|can i|could i)\b|어디 ?(있|에 있)|"
                            r"(어디|뭐|왜|언제|몇)[^ ]*\s*\?*\s*$", re.I)    # a question about a place, not a command
ABILITY_Q = re.compile(r"(?<!줄 )(?<!주실 )(?<!줘 )(?<!받을 )수 ?있(?:어|나|니|을까|습니까)\S*\s*\?*\s*$|\bdo you know how\b|"
                       r"\bare you able\b|줄 ?(?:알아|아세요|알아요|아니|알지)\S*\s*\?+\s*$", re.I)   # asks whether Lumi can ("손 흔들 줄 알아?")
RECEIVE_ASK = re.compile(r"\b(?:take|hold|give|hand|here|catch|grab|accept|receive|keep|yours)\b|받|드릴|드려|줄게|줄께|가져가|맡아|잡아",
                         re.I)                               # words that hand something over to Lumi
COME_ASK = re.compile(r"\bcome\b|\b(?:over )?here\b|\bcloser\b|\bthis way\b|이리|와|가까이|오세요", re.I)
FOLLOW_ASK = re.compile(r"\bfollow\b|\bwith (?:me|us)\b|\balong\b|따라|같이|함께", re.I)   # words of a follow request ...
SOCIAL = re.compile(r"\b(?:instagram|insta|twitter|tiktok|youtube|facebook|linkedin|social media|account|channel|blog)\b|"
                    r"인스타|유튜브|트위터|틱톡|페이스북|팔로우", re.I)                      # ... not online
MOTIONS = {"go_to", "come", "follow","move", "turn", "look", "lift", "wave", "arm", "pick", "put", "move_object", "fetch", "give",
           "place", "receive"}
REFERS_BACK = re.compile(r"\b(it|they|them|those|these|another|one more|one about)\b|그거|그걸|그건|그게|그것|하나 ?더|또 ?하나",
                         re.I)   # about the last answer
HELP_OFFER = re.compile(r"\b(how|what) (can|may) i (help|assist|do for) you\b|\bis there anything (else )?i can\b|"
                        r"\banything else i can (help|do)\b|\blet me know if (there'?s|there is|you need) anything\b|"
                        r"무엇을 도와|어떻게 도와|뭘 도와|도와드릴 (?:수 있는 )?일|도와 ?드릴까요|"
                        r"\bfeel free to ask\b|\bif you have (?:any )?(?:more |other )?questions\b|"
                        r"(?:더 |또 )?궁금한 (?:게|거|것이|점이?) (?:더 |또 )?(?:있으시면|생기면|있으면)|언제든(?:지)? (?:물어|말씀)", re.I)   # owner: never tacked on after an answer
SAY_AGAIN = re.compile(r"\b(say (it|that) again|repeat (it|that|please)|again,? please|one more time|come again|"
                       r"pardon|say again)\b|^\s*again\s*\??\s*$|다시 ?(한 ?번|말해|말씀|해 ?줘)|한 ?번 ?더|"
                       r"^\s*뭐라고(요)?\s*\??\s*$", re.I)
IN_LANGUAGE = re.compile(r"^\s*(and |then |now |okay,? |and say it |say (it|that) )?(in|into) (korean|english)\b|"
                         r"\b(say|tell me) (it|that) in (korean|english)\b|"
                         r"^\s*(그거|그걸|그럼|다시|이번엔|이제)?\s*(한국어|영어|korean|english)\s?로(?!.*(대화|할 ?수|할 ?줄|돼요\?|되나))"
                         r"(요|는요|는|도)?\s*(다시\s*)?((말|말씀|얘기)?\s*해\s*(줘|주세요|줄래요?|줄 ?수 ?있어요?|봐요?)?)?"
                         r"\s*[!?.~]*\s*$", re.I)
WAVE_ASK = re.compile(r"\bwav(e|ing)(?![a-z])|\bwith your hand\b|\bshake (?:your |my )?hands?\b(?! with\b)|흔들|손 ?인사|인사.*손으로|손으로.*인사", re.I)
AGAIN = re.compile(r"\b(?:again|once more|one more time|another one)\b|한 ?번 ?더|다시|또 ?(?:해|보여|불러)", re.I)
DO_IT = re.compile(r"^\W*(?:(?:okay|ok|sure|yes|yeah|then|so|well|go on|come on)\W+)*(?:do it|show me|go ahead|let'?s see(?: it)?|"
                   r"try it|go for it|please do)(?:\W+(?:then|now|please))*\W*$|"
                   r"^\W*(?:그럼|자|어디)?\s*(?:한 ?번\s*)?(?:해 ?봐|해 ?줘|해 ?보세요|해 ?주세요|보여 ?줘|보여 ?주세요)(?:요)?\W*$", re.I)
SING_ASK = re.compile(r"\bsing|\bsong|\bmusic\b|노래|한 ?곡|불러", re.I)
PROMISE = {   # Lumi's own sentence saying it does this now ("Okay! I'll sing a song for you.", "러브 어택 불러 드릴게요.")
    "sing": re.compile(r"\b(?:i'll|i will|let me|i'm going to) sing\b|\bhere(?:'s| is| comes| goes) (?:a |my |one |the )?song\b|"
                       r"(?:불러|들려)\s*(?:드릴게요|드리겠습니다|줄게|볼게요)|부를게요", re.I),
    "wave": re.compile(r"\b(?:i'll|i will|let me) wave\b|흔들어\s*(?:드릴게요|볼게요|줄게)|흔들게요", re.I),
    # any other motion: never done on the reply alone (the action line said none), lumi.answer() asks instead
    "motion": re.compile(r"\b(?:i'll|i will|let me|i'm going to|i am going to)\s+(?:now\s+)?(?:follow|come|go(?! ahead)|drive|"
                         r"head (?:to|over|back)|move|turn (?:around|left|right|to)|look (?:at|left|right|down|around|behind)|"
                         r"pick|grab|bring|fetch|lift|raise|lower|reach out)\b|"
                         r"\b(?:i'm|i am) (?:coming|following|on my way)\b|\bhere i come\b|"
                         r"따라\s*(?:갈게요|가\s*볼게요|갈게|가겠습니다)|(?<![가-힣])(?:갈게요|가겠습니다|올게요|갈게)|가져다\s*드릴게요|"
                         r"가져올게요|집어\s*(?:드릴게요|볼게요)|집을게요|돌게요|돌아\s*(?:볼게요|갈게요)|쳐다\s*볼게요|"
                         r"움직일게요|올릴게요|내릴게요|건네\s*드릴게요|내려\s*놓을게요", re.I),
}
NOT_NOW = re.compile(r"\b(?:if|when|later|after|once|next time)\b|나중에|끝나면|으면|다면", re.I)   # "... if you'd like"


def promised(sentence):
    """'sing' / 'wave' when Lumi's sentence says it does that now, else None: lumi.answer() then does it although the
    model's action line was none ("Start with one." -> "Okay! I'll sing a song for you." and silence, 2026-10-22).
    'motion' for any other move it says it makes ("Yeah." -> "Okay, I'll follow you!" and no follow, 2026-10-22):
    not done on a guess, Lumi asks what to do."""
    s = sentence or ""
    return None if NOT_NOW.search(s) else next((a for a, r in PROMISE.items() if r.search(s)), None)
LOOK_MORE = re.compile(r"^\W*(?:and|now|then|and now)?\s*(up|down|left|right)\W*$|"
                       r"^\W*(?:이제|그럼|그리고)?\s*(위|아래|왼쪽|오른쪽)(?:도|로|으로|요|도요)?\W*$", re.I)  # right after a look
LOOKUP_MORE = re.compile(r"\b(he|she|him|his|her|they|them|their|there|it|that)\b|거기|그 ?사람|그분|그거|그게|그곳|왜|"
                         r"언제|얼마", re.I)                 # a follow-up question about something just looked up
SPEAK_IN = re.compile(r"(english|영어|korean|한국어)\s?로\s*(?:다시\s*|좀\s*|한 ?번\s*)*(?:말|얘기|소개|대답|답|설명|자기소개|"
                      r"해\s*(?:줘|주|봐))(?!.*(?:해도|도 ?돼|할 ?수|할 ?줄))|"
                      r"\b(?:speak|talk|answer|reply|introduce yourself)\b.*\bin (english|korean)\b", re.I)
SHORT_Q = re.compile(r"\?|^\W*(?:where|who|what|when|how|which|why)\b|몇|어디|누가|누구|뭐|언제|왜|얼마|어떻게", re.I)
ABOUT_YOU = re.compile(r"\b(?:you|your|yourself|lumi)\b|너|네가|니가|넌|루미|당신", re.I)   # a follow-up about Lumi itself
FOLLOW_UP = re.compile(r"\b(more|why|how come|details?|explain|elaborate|and then|what else|tell me more)\b|자세히|더 알려|왜|그리고", re.I)
_CLOSE_WORD = (r"(ok(ay)?|okay then|thanks?( you)?( very much)?( a lot)?|cheers|thank you( so much)?|got it|alright|all right|"
               r"fine|good|great|cool|nice|perfect|stop|enough|that'?s (it|all|enough|fine)|so|sure|i see|understood|"
               r"no thanks|nothing|never ?mind|lumi|루미|고마워요?|감사합니다|감사해요|땡큐|알겠어요?|알았어요?|오케이|ㅇㅋ|됐어요?|그만|좋아요?|"
               r"i got (it|you)|got you|i understand|makes sense|that makes sense|okay,? i understand|"
               r"네|예|그래요?|알겠습니다|알겠어|이해했어요|이해했습니다|그렇군요|아하)")
CLOSING = re.compile(rf"^(\s*{_CLOSE_WORD}[\s,.!]*)+$", re.I)   # one or several: "okay, thanks", "got it, thank you"


WAKE_WORD_RE = re.compile(r"\b(lumi|loomi|rumi)\b|루미", re.I)


def is_closing(text):
    """'okay', 'thanks', 'got it', 'stop'...: the visitor is done with this answer."""
    return bool(CLOSING.match(text or ""))


_BC_EN = (r"oh|ah|aha|ha(?:ha)+|hehe|lol|wow|whoa|huh|hmm|mm-?hmm|mhm|really|seriously|for real|no way|cool|nice|awesome|interesting|"
          r"amazing|great|i see|uh[- ]?huh|yeah|yep|right|true|me too|same here|is that so|is that right|is that true|"
          r"are you sure|(?:that )?makes sense|i got it|got it|understood|i understand|good to know|fair enough|ok(?:ay)?|"
          r"that'?s (?:cool|nice|great|interesting|amazing|funny|good to know)")
_BC_KO = (r"ㅋ+|ㅎ+|ㅇㅇ|ㅇㅋ|하하+|아하|아|오|어|우와|와|헐|대박|진짜요|진짜|정말요|정말|그렇구나|그렇군요|그랬구나|그랬군요|그렇네요|그렇네|그런가요|"
          r"그런가|그래요|그래|신기하네요|신기해요|신기하다|그렇죠|맞아요|맞아|알겠어요|알겠습니다|알겠어|알았어요|알았어|"
          r"이해했어요|이해했습니다|이해돼요|오케이|네|예|응")
BACKCHANNEL = re.compile(rf"^(?:[\s,.!?~]*(?:{_BC_EN}|{_BC_KO})(?![\w']))+[\s,.!?~]*$", re.I)
UNDERSTOOD = re.compile(r"\b(?:i see|got (?:it|you)|understood|i understand|makes sense|good to know|fair enough)\b|"
                        r"알겠|알았|이해했|이해돼|그렇구나|그렇군|그랬구나|그렇네|아하", re.I)   # "I see", "알겠어요": understood


def is_backchannel(text):
    """'oh really?', 'I see', 'got it', '아 그래?', '그렇구나', '헐': the listener reacts or checks ('I see?', '그런가요?');
    it asks nothing new and orders nothing."""
    return bool(BACKCHANNEL.match(text or "")) or is_closing(text)


def warm_up():
    """Load the model into the GPU now, so the first answer is fast."""
    _chat([{"role": "user", "content": "Hi"}])


_recent_byes = collections.deque(maxlen=FAREWELL_RECENT)


def _opening(text, words=3):
    return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split()[:words])
FORCED_LANG = {}                   # {"lang": "en"|"ko"} set by lumi.py from the speech recogniser


def now_line():
    """The date and time for the prompt, also written the Korean way: with the English form alone the model
    said "10월 21일" on 20 October."""
    return f"{web.now_text()} ({time.strftime('%Y년 %-m월 %-d일 %H시 %M분')})"


def reply_language(text):
    """The language to answer in: the one asked for ("English로 말해 줘", "talk in Korean"), else language()."""
    m = SPEAK_IN.search(text)
    if m:
        return "English" if re.search(r"english|영어", m.group(0), re.I) else "Korean"
    return language(text)


def language(text):
    """'Korean' or 'English': what the speech recogniser heard, else Hangul in the text."""
    lang = FORCED_LANG.get("lang")
    if lang:
        return "Korean" if lang == "ko" else "English"
    return "Korean" if re.search(r"[\uac00-\ud7a3]", text) else "English"


FRAGMENT_WORDS = 4            # "Which one?", "얼마?", "Where is it used?": a fragment read with the last answer
# a fragment that names what it asks ("몇 살이라고요?") gets no hint
OWN_TOPIC = re.compile(r"살|나이|이름|\bold\b|\bname\b|\bage\b|\btall\b|\bheavy\b|\bweigh", re.I)
SAME_ABOUT = re.compile(r"^\W*(?:and|so|what about|how about|and what about)\s+(your\s+[a-z]+(?:\s+[a-z]+)?)\W*$", re.I)
KO_SAME_ABOUT = re.compile(r"^\W*(?:그럼\s*|그리고\s*)?(?:네\s*|너\s*|루미\s*)?(?!(?:너|루미|당신|저|나|그거|이거|그건|여기|거기)(?:은|는))([가-힣]{1,6}?)(?:은|는)요?\s*\?+\s*$")
                               # the question before asked again about a part of Lumi ("팔은요?")
FRAGMENT_CHARS = 160           # chars of the last answer's first sentence shown with a fragment
_PLEASE = r"(?:\W+(?:please|lumi|then|now|해 ?줘|해 ?봐|해요|해 ?주세요|해|요|봐|줘))*\W*$"
AGAIN = re.compile(r"^\W*(?:(?:and|okay|ok|please|lumi|루미야?|그럼|자)\W+)*(?:(?:do (?:it|that) )?again|one more(?: time)?|once more|"
                   r"more|encore|한 ?번 ?더|다시(?: ?한 ?번)?|또|더)" + _PLEASE, re.I)   # right after an action: that action again
DO_IT = re.compile(r"^\W*(?:(?:okay|ok|yes|yeah|sure|so|well|lumi|please|그럼|자|네)\W+)*(?:go on|go ahead|do it|show me|"
                   r"let'?s see(?: it)?|yes,? please|try it|해 ?봐|해 ?줘|보여 ?줘|보여 ?주세요|해 ?주세요|해 ?보세요)"
                   r"(?:\W+(?:do it|go ahead|show me|then))*" + _PLEASE, re.I)
                   # right after "can you wave?" ... "Yes, I can.": do it now
ABOUT_ANSWER = re.compile(r"^\W*(?:(?:but|and|so|then|oh|wait|hmm|okay|그럼|근데|아니|아|어)\W+)*(?:(?:why|wai|whai)(?: not| is that| so)?|와이|"
                          r"how come|how (?:do|did|can) you (?:know|tell)(?: that| it)?|are you sure|really|for real|fr|seriously|no way|"
                          r"what do you mean|says who|왜(?:요|죠)?|왜 안 ?(?:돼|되)\S*|진짜(?:요|야|로)?|정말(?:요|이야)?|레알|실화(?:야|예요|냐)?|참말\S*|"
                          r"확실(?:해|한가|하)\S*|어떻게 알아\S*|그게 무슨 (?:뜻|말)\S*)\W*$", re.I)
                               # asks about the answer just given: its reason, its source, or to confirm it
LOOKUP_BEFORE_CHARS = 1500     # chars of the last lookup's results given again with a follow-up ("how old is she?")
FOLLOW_UP_WORDS = 5            # "why did Samsung stock fall today?" is a new question, "tell me more about it" is not
AND_ALSO = re.compile(r"^\s*(and|what about|how about|also|그럼|그리고)\b", re.I)   # "and the yen?": a follow-up
WEATHER_ASKED = " (the weather)"   # lumi.look_up adds it to a weather question; the history keeps it
WEATHER_PLACE = re.compile(r"^\W*(?i:(?:and|so|then|ok(?:ay)?)\W+)*(?i:(?:what|how)\s+about\s+)?(?i:in\s+)?"
                           r"(?!(?:Why|What|When|Where|Who|Whose|How|Which|Is|Are|Was|Will|Can|Could|Do|Does|Did|Should|Lumi)\b)(?P<place>[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*)*)[\s?.!]*$")   # "what about Busan?" after the weather
KO_WEATHER_PLACE = re.compile(r"^\W*(?:(?:그럼|그러면|그리고|아니)\W*)?(?P<place>[가-힣]+?)(?:시|도)?(?:\s*날씨)?"
                              r"(?:은|는|도|에는|에서는|이요|요)*[\s?.!~]*$")   # "그럼 부산은?": a place of web.KO_PLACES only
REPAIR = re.compile(r"^\W*(?:(?:no|nope|sorry|oh)\W+)*i\s+mean[t]?\b|^\W*(?:아니|아뇨|아니요)[\s,]|말고\b|"
                        r"말(?:이야|이에요|이요)\W*$", re.I)   # "no, I meant North Korea", "아니 서울 말이야"
LEAD = re.compile(r"^\s*(?:(?:and|what about|how about|also|no|nope|sorry|oh|그럼|그리고|아니|아뇨|아니요)\b[\s,]*)*"
                  r"(?:i\s+mean[t]?\s+)?", re.I)   # the words before what a follow-up asks
HERE_WORD = re.compile(r"\bhere\b|여기|이곳|이 ?동네", re.I)   # "the weather here": not the place asked before
THIS_PLACE = re.compile(r"\bhere\b|\bthis (?:event|show|fair|expo|building|place)\b|\b(?:conference|booths?|exhibitors?|"
                        r"keynote|restrooms?|toilets?|bathrooms?)\b|여기|이곳|행사|부스|이 건물|화장실", re.I)   # a follow-up about this event, not the place before
DAY_WORD = re.compile(r"\b(?:today|tonight|tomorrow|yesterday|weekend|week|morning|afternoon|evening|monday|tuesday|"
                      r"wednesday|thursday|friday|saturday|sunday)\b", re.I)
NAMES = re.compile(r"\b[A-Z][a-z]+(?:-[a-z]+)?(?: [A-Z][a-z]+(?:-[a-z]+)?)+")   # "Jensen Huang", "Son Heung-min"
NAMED_BEFORE = re.compile(r"\b(?:he|she|him|his|her|they|them|their|there|it)\b|거기|그 ?사람|그분|그곳|걔", re.I)
                                                   # a person, place or thing of the answer before
CAP_WORD = re.compile(r"(?<=\S )(?!I\b|Lumi\b|Cutshion\b)[A-Z][a-z]{2,}")         # "... is Ottawa": not the first word
KO_NAME = re.compile(r"(?:은|는)\s+([가-힣A-Za-z]+(?: [가-힣A-Za-z]+)?)\s*(?:이에요|예요|입니다|이죠|이고|이며|이야)")
                                                   # "오픈AI의 CEO는 샘 올트먼이에요": "샘 올트먼"
MORE_ONLY = re.compile(r"\b(tell me more|tell me|more|details?|explain|elaborate|what else|please|about (it|that|this))\b|"
                       r"더 알려 ?(줘|주세요)?|자세히|알려 ?(줘|주세요)|좀", re.I)   # words of a follow-up that search nothing
REACTION = re.compile(r"^\W*(?:(?:wow|oh|really|huh|whoa)\W+)*(?:i (?:didn'?t|did not) know (?:that|it)|that'?s (?:a lot|so many)|"
                      r"that many|that much|so many|so much)\W*$|^\W*(?:와|헐|오|아)?\s*(?:몰랐\S*|그렇게\s*(?:많|비싸|크)\S*)\W*$",
                      re.I)   # a reaction to what was found, not a new question
NOW_Q = re.compile(r"\bwhat time is it\b|\bwhat'?s the time\b|\bwhat(?:'s| is) (?:the date|today)\b|지금 몇 ?시|오늘 며칠",
                   re.I)      # asked of the clock, not of the lookup before
LOOKUP_ACTION = re.compile(r"^\s*(?:\**ACTION\**\s*:\s*)?(?:search|weather)(?: (?!results)|\s*$)")   # an action line
                             # written instead of the answer (the routing prompt is its system prompt): never said
NONE_LINE = re.compile(r"\s*(?:\**ACTION\**\s*:\s*)?none\b", re.I)   # "ACTION: none -" (or "none" alone)
LOOKUP_PEEK = 8                # chars of the line after "ACTION: none" read before it is spoken: "search ..." is the action
SPOKEN_TARGET = re.compile(r"^\W*(?:i\b|i'll|i will|let me|sure|okay|ok\b|one moment|just a moment|잠시|잠깐|찾아|확인)", re.I)
                               # "search I'll look that up": words for the visitor, not the query
LOOKUP_ANSWER = """Search results found just now on the internet (they may hold ads and unrelated parts):
{facts}
{before}
Now it is {now}.
Visitor: {question}

No ACTION line: answer in {lang} as spoken words to a person: the answer itself in the first sentence, short (1 or 2 sentences;
when they ask for more, 2 or 3 sentences with facts not said yet). No lists, links or markdown. Take names, numbers
and dates from the results above (the newest when they differ). Only when the results do not hold it and it is
settled general knowledge that never changes (a landmark's height, who founded a company) answer from what you know;
anything that changes (who holds an office, prices, results, news, schedules) only from the results, else say in one
sentence that you couldn't find it; never guess. "Who is the pope / the president / the CEO?" asks who holds it
now: say the name. A short follow-up ("how old is he?", "몇 살이야?", "and tomorrow?") asks about the person, thing or
place of the question before, never about you. For the weather take the day asked from its own line. Round only long numbers such as prices and populations ("about 1,330
won", "about 9.4 million"); say heights, ages, dates and scores as found (an age next to a birth date is worked out
already). Do not mention the search, the results or websites. Never give a person's home address, phone number or
other private details, nor help to hurt someone or break the law: say briefly that you can't help."""


def route_system(markers=(), now=None):
    """The system prompt of respond_stream: the same from turn to turn but for what Lumi is doing now, at its end."""
    return SYSTEM + "\n" + ACTIONS_STREAM.format(markers=", ".join(markers) or "(none)", yaw=f"{HEAD_YAW[1]:g}",
                                                pitch_down=f"{-HEAD_PITCH[0]:g}", pitch_up=f"{HEAD_PITCH[1]:g}",
                                                lift=f"{head_hw.LIFT_MAX_MM:g}") + \
        (f"\nWhat you are doing now: {now}" if now else "")


class Brain:
    def __init__(self):
        self.history = []                 # [(question, answer)]
        self.last_lookup = None           # the last question answered from the internet
        self.last_facts = ""              # ... and what was found for it (a follow-up is answered from it too)
        self.lookup_topic = ""            # what the last lookup that was not a follow-up searched for
        self.weather_at = ""              # the place of the last weather question in this talk ("" = here)

    def weather_place(self, target, text=""):
        """Where a weather lookup is for: a place not named ("내일 비 와?" after Jeju's weather) is the place of the
        last weather question in this talk; "here" / "여기" is here."""
        if target or HERE_WORD.search(text):
            self.weather_at = target
        return self.weather_at

    def lookup_about(self, target, about, text=""):
        """What lumi.not_online reads for a lookup: right after a lookup (or _after's follow-up of it, "What time does
        Lotte World open? How much is a ticket?") the question looked up, so the ticket is Lotte World's, not this
        event's; words that name this place ("here", "the toilets") are read alone."""
        if not (self.last_lookup and self.history and self.history[-1][0] == self.last_lookup or
                self.last_lookup and target.startswith(self.last_lookup)):
            return about
        return text if THIS_PLACE.search(text or about) else self.last_lookup

    def answer(self, question):
        hits = [h for h in knowledge.search(question, k=4) if h[0] >= MIN_SCORE]
        notes = "\n\n".join(f"[{src}]\n{text}" for _, src, text in hits) or "(no matching notes)"
        messages = [{"role": "system", "content": SYSTEM}]
        for q, a in self.history[-HISTORY_TURNS:]:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": f"Reference notes:\n{notes}\n\n{_examples(question)}Visitor: {question}\n\n"
                                                    f"(Reply in {language(question)}.)"})
        reply = _chat(messages)
        self.history.append((question, reply))
        return reply, hits

    def respond(self, text, markers=()):
        """Spoken reply + optional action: {"action", "target", "say"} (see ACTIONS)."""
        hits = [h for h in knowledge.search(text, k=2) if h[0] >= MIN_SCORE]
        notes = "\n\n".join(f"[{src}]\n{t}" for _, src, t in hits) or "(no matching notes)"
        system = SYSTEM + "\n" + ACTIONS.format(markers=", ".join(markers) or "(none)")
        messages = [{"role": "system", "content": system}]
        for q, a in self.history[-HISTORY_TURNS:]:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": f"Reference notes:\n{notes}\n\n{_examples(text)}Visitor: {text}\n\n"
                                                    f"(Reply in {language(text)}.)"})
        try:
            out = json.loads(_chat(messages, RESPONSE_SCHEMA))
        except (json.JSONDecodeError, KeyError):
            out = {"action": "none", "target": "", "say": "Sorry, could you say that again?"}
        if out.get("action") == "go_to" and out.get("target") not in markers:
            out["action"] = "none"
        if re.search(r"\b(bye|goodbye|(?<!can't )(?<!cant )(?<!cannot )(?<!not )(?<!to )see you|good night|i have to go|i'?m leaving)\b|안녕히|잘 ?가|잘 ?있어|"
                     r"다음에 봐|갈게요|안녕\s*[.!]?$", text, re.I):
            out["action"] = "end"
        self.history.append((text, json.dumps(out, ensure_ascii=False)))
        return out

    def respond_stream(self, text, markers=(), now=None):
        """Generator: first {"action", "target"}, then the spoken reply sentence by sentence. now: what Lumi is doing
        at the moment (lumi.now_doing), so a question about it is answered from facts."""
        how = self.again(text)
        if how:                                                               # "say it again", "and in Korean?"
            yield from self.repeat(text, how)
            return
        about = self.topic(text)                                              # "which ones?": the topic before
        context = f"{self.history[-1][0]} {text}" if self.history else text    # "how heavy can the items be?"
        k = NOTES_K_COMPANY if COMPANY_TALK.search(context) else NOTES_K
        hits = knowledge.search(about, k=k)
        if context != about:                                                  # the words alone, and with the
            hits += [h for h in knowledge.search(context, k=NOTES_K)          # question before (one more chunk)
                     if h[2] not in {x[2] for x in hits}][:1]
        hits = [h for h in hits if h[0] >= MIN_SCORE]
        notes = "\n\n".join(f"[{src}]\n{t}" for _, src, t in hits) or "(no matching notes)"
        lang = reply_language(text)
        # the long fixed part comes first and stays the same from turn to turn, so the runner keeps it cached (else ~3 s
        # more per turn); the time goes into the last message. What Lumi does now stays here: in the last message it
        # read "leave it" while holding a cup as "put it down"
        system = route_system(markers, now)
        self.last_system = system                 # respond_from answers a lookup with it: still cached, and after it
        messages = [{"role": "system", "content": system}]
        for q, a in self.window():
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": f"Reference notes:\n{notes}\n\n{_examples(about, on_task=bool(now) and 'not doing any task' not in now)}"
                                                    f"Now it is {now_line()}." +
                                                    f"\n\nVisitor: {text}\n\n" + self._fragment_hint(text) +
                                                    f"(Reply in {lang}.)"})
        buf, full, header, said = "", "", None, []
        stream, retried = _stream(messages), False
        try:
            for piece in iter(lambda: next(stream, None), None):
                full += piece
                buf += piece
                if header is None:
                    if "\n" not in buf:
                        continue
                    first, rest = buf.split("\n", 1)
                    if NONE_LINE.match(first) and len(rest.lstrip()) < LOOKUP_PEEK and "\n" not in rest.lstrip():
                        continue                           # the next line may be "search ..." (26b, now and then)
                    buf = rest
                    if NONE_LINE.match(first) and LOOKUP_ACTION.match(rest.lstrip()):
                        first = re.search(r"search|weather", rest).group(0)   # read as the action, never said
                    header = self._after(self._action(first, text, markers), text)
                    if header is None:                     # the model skipped the ACTION line
                        header, buf = self._after({"action": "none", "target": ""}, text), first + " " + buf
                    if header["action"] == "unclear" and not retried and \
                            (has_meaning(text) or self.history and ABOUT_ANSWER.match(text)) and \
                            not other_latin_language(text):  # 26b called short or broken but clear words unclear ("fr?")
                        stream.close()
                        retried, header, buf, full = True, None, "", ""
                        messages[-1]["content"] += UNCLEAR_RETRY
                        stream = _stream(messages)
                        continue
                    yield header
                    if header.get("say"):                  # the model's words don't fit the action any more
                        said.append(header.pop("say"))
                        yield said[0]
                        buf, full = "", f"{first}\n{said[0]}"
                        break
                    if header["action"] == "unclear" and other_latin_language(text):
                        said.append(OTHER_LANGUAGE["en"])  # Uzbek / German in Latin letters: not "say it again"
                        yield said[0]
                        buf, full = "", f"{first}\n{said[0]}"
                        break
                parts = SENTENCE_END.split(buf)
                for sentence in parts[:-1]:
                    if sentence.strip() and not (said and HELP_OFFER.search(sentence)):
                        said.append(spoken(sentence.strip(), lang))
                        yield said[-1]
                buf = parts[-1]
        except Exception:
            if header is None:
                yield {"action": "none", "target": ""}
                header = {}
            buf += " Sorry, could you say that again?"
        if header is None:                                 # very short reply on a single line (or two)
            first, _, rest = buf.partition("\n")
            header = self._after(self._action(first, text, markers), text)
            yield header or {"action": "none", "target": ""}
            buf = rest if header else buf
        if buf.strip() and not (said and HELP_OFFER.search(buf)):
            said.append(spoken(buf.strip(), lang))
            yield said[-1]
        for sentence in re.split(r"(?<=[.!?])\s+", full):   # a dropped "How can I help?" is not kept either
            if HELP_OFFER.search(sentence) and sentence.strip() not in said:
                full = full.replace(sentence, "")
        first, _, rest = full.strip().partition("\n")
        if header and "action" in header and self._action(first, text, markers) is not None:   # the action done, not the
            full = f"ACTION: {header['action']} {header.get('target') or '-'}\n{rest}"   # model's ("wave" for "손 흔들 줄 알아?")
        self.history.append((text, full.strip()))

    def _fragment_hint(self, text):
        """For a bare fragment ("얼마?", "Which one?", "Where is it used?"): what it follows, so the model reads it
        as about the last answer's subject, not about itself or a price."""
        last = self._last_said() if self.history else ""
        done = self._redo(text)
        if done:                     # "do it again" / "한 번 더" after a wave, "more" after a look
            line = done.split(chr(10))[0].rstrip(" -")
            return f"(Right after your action \"{line}\": this asks for it again; write \"ACTION: {line}\" first.)\n"
        if last and DO_IT.match(text):                     # "can you wave?" "Yes, I can." "go on then" / "보여 줘"
            return f"(This follows your answer \"{last[:FRAGMENT_CHARS * 2]}\": if it said you can do something, do it now: its ACTION line is that action (wave, sing, look ...), not none.)\n"
        part = SAME_ABOUT.match(text) or KO_SAME_ABOUT.match(text)
        if last and part:                                  # "What about your cameras?" / "카메라는요?" after "can I wipe you?"
            return (f"(The visitor's question \"{self.history[-1][0]}\" asked again, now about {part.group(1)}: answer "
                    f"that question for it, not other facts about it.)\n")
        if last and ABOUT_ANSWER.match(text):              # "why?", "how do you know?", "진짜?" after a refusal too
            return (f"(This asks about your answer \"{last[:FRAGMENT_CHARS * 2]}\": its reason or how you know it; "
                    f"a \"really?\" is answered \"Yes,\" with that same fact said again (the same number or name), no new fact.)\n")
        if not last or len(text.split()) > FRAGMENT_WORDS or not SHORT_Q.search(text) or is_backchannel(text) \
                or ABOUT_YOU.search(text) or OWN_TOPIC.search(text):
            return ""
        return f"(This follows your answer \"{SENTENCE_END.split(last)[0][:FRAGMENT_CHARS]}\": it asks about that.)\n"

    def _after(self, header, text):
        """The action line checked against the turn before: a song only when one is asked for (or asked again),
        "and down?" right after a look looks down, a follow-up question ("how old is he?", "거기 입장료는?") right
        after a lookup is looked up too."""
        if header and header["action"] == "sing" and (sing.NOT_ASKED.search(text) or sing.list_asked(text)):
            return {"action": "none", "target": ""}        # "Don't sing.", "어제 노래방 갔어요.", "what songs can you sing?"
        if not header or not self.history:
            return header
        last_q, last_a = self.history[-1]
        m = re.match(r"\s*\**ACTION\**\s*:\s*(\w+)", last_a)
        before, action = (m.group(1).lower() if m else ""), header["action"]
        if action == "sing" and before != "sing" and (SING_ECHO.match(text) or not SING_ASK.search(text) and
                                                      not SING_ASK.search(f"{last_q} {last_a}")):
            return {"action": "none", "target": ""}        # "Prove it." after "do you have a sense of humour?";
                                                           # "Start with one." after Lumi offered its songs is a song
        if DO_IT.match(text) and action in ("none", "unclear"):
            asked = "wave" if WAVE_ASK.search(last_q) else "sing" if SING_ASK.search(last_q) else None
            if asked:                                      # "손 흔들 줄 알아?" -> "해 봐": now do it
                return {"action": asked, "target": ""}
        if before in ("wave", "sing") and action in ("none", "unclear") and AGAIN.search(text) and not \
                re.search(r"\b(?:say|tell|repeat|explain|what|who|where|when|why|which)\b|말해|말씀|뭐|누구|어디|언제|왜",
                          text, re.I):                     # "What's your name again?" after a song asks the name
            return {"action": before, "target": ""}      # "would you mind doing it again?" after a wave
        look = LOOK_MORE.match(text)
        if before == "look" and look and action in ("none", "unclear"):
            d = look.group(1) or look.group(2)
            return {"action": "look", "target": {"위": "up", "아래": "down", "왼쪽": "left", "오른쪽": "right"}.get(d, d.lower()),
                    "say": "네." if language(text) == "Korean" else "Okay."}
        looked_up = before == "search" or (self.last_lookup is not None and last_q == self.last_lookup)
        if not looked_up or action not in ("none", "unclear") or is_backchannel(text) or REACTION.match(text):
            return header                                  # "oh really?", "wow, that many?" ask nothing new
        place = WEATHER_PLACE.match(text) if last_q.endswith(WEATHER_ASKED) else None
        if place and not DAY_WORD.search(place.group("place")):
            return {"action": "weather", "target": place.group("place")}   # "and Tokyo?"; "and tomorrow?" is searched
        place = KO_WEATHER_PLACE.match(text) if last_q.endswith(WEATHER_ASKED) else None
        if place and place.group("place") in web.KO_PLACES:
            return {"action": "weather", "target": web.en_place(place.group("place"))}   # "그럼 부산은?"; "내일은?" is searched
        if (LOOKUP_MORE.search(text) or FOLLOW_UP.search(text) or AND_ALSO.match(text) or REPAIR.search(text) or
                SHORT_Q.search(text) and len(text.split()) <= 6) \
                and not re.search(r"cutshion|쿳션", text, re.I) and not ABOUT_YOU.search(text) \
                and not NOW_Q.search(text):                # "Where?", "몇 살이야?", "who's the CEO?" after a lookup
            return {"action": "search", "target": f"{last_q} {text}"}
        return header

    def _redo(self, text):
        """The action asked for again ("do it again", "한 번 더", "more") right after it was done, else None. A remark in
        between ("that's cute", "와 귀엽다") does not count."""
        turns = self.history[-1:]
        if turns and turns[0][1].startswith("ACTION: none") and len(turns[0][0].split()) <= 4 and "?" not in turns[0][0]:
            turns = self.history[-2:-1]
        return next((m.group(1) for _, a in turns
                     for m in [re.match(r"ACTION: ((?!none|end|unclear|search|weather)\w+.*)", a)] if m), None) \
            if AGAIN.match(text) else None

    def again(self, text):
        """"say it again" -> "same", "and in Korean?" / "한국어로!" -> "Korean" / "English"; else None. Only right
        after an answer that was talk (not a move or a lookup)."""
        if not self.history or len(text.split()) > 6 or not self._last_said() or self._redo(text):
            return None                                    # "한 번 더" after a wave: wave again, not the words again
        lang = IN_LANGUAGE.search(text)
        if lang:
            return "Korean" if re.search(r"korean|한국어", lang.group(0), re.I) else "English"
        return "same" if SAY_AGAIN.search(text) else None

    def _last_said(self):
        """The words of the last answer, without its ACTION line."""
        lines = [ln for ln in self.history[-1][1].splitlines() if not re.match(r"\s*\**ACTION", ln)]
        return " ".join(lines).strip()

    def repeat(self, text, how):
        """Generator like respond_stream: the last answer again, as it was or in another language."""
        last = self._last_said()
        yield {"action": "none", "target": ""}
        if how == "same":
            out = last
        else:
            try:
                out = _chat([{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": f"Say this again in {how}, the same facts and nothing else, "
                                                         f"spoken style{', polite (-요)' if how == 'Korean' else ''}:"
                                                         f"\n{last}"}]).strip().strip('"')
            except Exception:                              # noqa: BLE001 - say it as it was
                out = last
        for sentence in SENTENCE_END.split(out):
            if sentence.strip():
                yield spoken(sentence.strip(), how if how != "same" else language(text))
        self.history.append((text, f"ACTION: none -\n{out}"))

    def topic(self, text):
        """What the words are about: a short follow-up ("tell me more", "can they see in the dark?") goes with the
        previous question, for the notes, the examples and the lookup decision."""
        if self.history and (len(text.split()) <= 4 or FOLLOW_UP.search(text) or REFERS_BACK.search(text)):
            return " ".join([q for q, _ in self.history[-2:]] + [text])   # "which ones?" then "can they...?"
        return text

    def window(self):
        """The turns given to the model: the last HISTORY_TURNS to 2 * HISTORY_TURNS - 1, the first one kept until the
        window jumps, so the runner finds the turns before the last one still cached (a window sliding by one turn
        read all of them again every turn, ~300 tokens)."""
        n = len(self.history)
        return self.history[max(0, n - HISTORY_TURNS) // HISTORY_TURNS * HISTORY_TURNS:]

    def respond_from(self, question, facts):
        """Spoken answer built from looked-up facts (weather, web results); yields sentences."""
        # the system prompt of the last respond_stream: the runner has it cached (~5000 tokens), and the next turn's
        # respond_stream finds it cached again (with SYSTEM alone here its action part was read again, ~1.4 s)
        messages = [{"role": "system", "content": getattr(self, "last_system", None) or route_system()}]
        for q, a in self.window():
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        follow_up = self.last_lookup is not None and self.history and self.history[-1][0] == self.last_lookup
        before = f"\nFound for the question before:\n{self.last_facts[:LOOKUP_BEFORE_CHARS]}\n" if follow_up else ""
        lang = language(question)
        messages.append({"role": "user", "content": LOOKUP_ANSWER.format(facts=facts, before=before, question=question,
                                                                         lang=lang, now=now_line())})
        self.last_facts = facts
        said = False
        for prompt in (messages, [{"role": "system", "content": SYSTEM}] + messages[1:]):   # the second only when
            buf, full = "", ""                                                             # all was an action line
            for piece in _stream(prompt):
                full += piece
                buf += piece
                while not said and LOOKUP_ACTION.match(buf) and "\n" in buf:   # "search New York weather" first
                    buf = buf.split("\n", 1)[1]
                if not said and LOOKUP_ACTION.match(buf):
                    continue
                parts = SENTENCE_END.split(buf)
                for sentence in parts[:-1]:
                    if spoken(sentence.strip(), lang):             # no "ACTION: none" copied from the history
                        said = True
                        yield spoken(sentence.strip(), lang)
                buf = parts[-1]
            if spoken(buf.strip(), lang) and not (not said and LOOKUP_ACTION.match(buf)):
                said = True
                yield spoken(buf.strip(), lang)
            if said:
                break
        self.history.append((question, full.strip()))
        self.last_lookup = question                        # a "tell me more" next is looked up again

    def farewell(self, text, lang="en"):
        """A short natural goodbye that fits the conversation (what the visitor just said, or their silence),
        unlike the goodbyes said lately (FAREWELL_RECENT)."""
        from assistant import talk_examples
        said = f'The visitor just said: "{text}".' if text else "The visitor has stopped talking."
        asked = IN_LANGUAGE.search(text or "") or re.search(r"\bin (korean|english)\b|(한국어|영어)로", text or "", re.I)
        if asked:                                          # "say bye in Korean for her"
            lang = "ko" if re.search(r"korean|한국어", asked.group(0), re.I) else "en"
        ideas = random.sample([r for c, lg, _, r in talk_examples.EXAMPLES if c == "goodbye" and lg == lang], 3)
        avoid = " ".join(f'"{b}"' for b in _recent_byes)
        messages = [{"role": "system", "content": SYSTEM + f"\nNow it is {now_line()}."}]
        for q, a in self.history[-HISTORY_TURNS:]:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": f"{said} The visitor is leaving: the conversation is over. Say one "
                                                    f"short, warm, natural goodbye that fits this conversation (thank them "
                                                    f"back if they thanked you), in {'Korean' if lang == 'ko' else 'English'}. "
                                                    f"Only the words. Never greet them (\"안녕\" here means bye). Ideas, "
                                                    f"in your own words: {' / '.join(ideas)}. "
                                                    + (f"Said to other visitors lately, so do not use these again: {avoid}. "
                                                       if avoid else "") +
                                                    "Do not begin with 'You're welcome' or '천만에요'; never say 'Have a "
                                                    "great day', 'It was nice talking with you' or 'It was my pleasure'; "
                                                    "in Korean polite (-요)."})
        try:
            bye = spoken(_chat(messages).strip().strip('"'), "Korean" if lang == "ko" else "English")
            if _opening(bye) in {_opening(b) for b in _recent_byes}:   # same start as a recent one: once more, freer
                bye = spoken(_chat(messages, temperature=FAREWELL_RETRY_T).strip().strip('"'),
                             "Korean" if lang == "ko" else "English")
        except Exception:
            bye = "See you next time!" if lang == "en" else "다음에 또 봐요!"
        _recent_byes.append(bye)
        return bye

    def search_terms(self, text):
        """A short English web-search query for the visitor's question (also for Korean questions)."""
        context = f"Earlier question: {self.history[-1][0]}\n" if self.history and FOLLOW_UP.search(text) else ""
        try:
            q = _chat([{"role": "user", "content": f"{context}Question: {text}\n\nWrite the best short English web search "
                                                    f"query (3 to 8 words) to answer it. Only the query."}])
            q = q.strip().strip('"').splitlines()[0][:120]
            return q or text
        except Exception:
            return text

    def search_query(self, text):
        """What to look up. A follow-up right after a lookup ("tell me more", "how old is she?", "and the yen?",
        "몇 살이야?"; _after writes it after the question before) is searched with that lookup's topic, the names its
        answer gave ("Jensen Huang") and only the words that ask something new; a third follow-up still goes with
        the first question."""
        follow = bool(self.last_lookup) and text.startswith(self.last_lookup)
        if follow:
            text = text[len(self.last_lookup):]
        after_lookup = bool(self.last_lookup and self.history and self.history[-1][0] == self.last_lookup)
        words = len(text.split())
        if follow or self.history and (FOLLOW_UP.search(text) and words <= FOLLOW_UP_WORDS or after_lookup and (
                words <= 3 if HANGUL.search(text) else          # "몇 살이야?": Korean leaves the subject out
                words <= FOLLOW_UP_WORDS and (LOOKUP_MORE.search(text) or AND_ALSO.match(text) or
                                              SHORT_Q.search(text) and not re.search(r"\d", text) and
                                              not CAP_WORD.search(text)))):   # "How much is a ticket?": no name
            topic = self.lookup_topic or self.last_lookup or self.history[-1][0]
            if (self.last_lookup or "").endswith(WEATHER_ASKED):          # "and tomorrow?" after the weather
                topic = "weather " + self.last_lookup[:-len(WEATHER_ASKED)]
            said = SENTENCE_END.split(self.history[-1][1].strip())[0] if after_lookup else ""
            rest = LEAD.sub("", re.sub(r"\s+", " ", MORE_ONLY.sub(" ", text)).strip(" ?.!,")).strip()
            return " ".join([topic] + self._names(said, topic) + [rest]).strip()
        if self.history and words <= FOLLOW_UP_WORDS and NAMED_BEFORE.search(text):   # "how many people live there?"
            q = self.history[-1][0]                                                 # after a talk answer ("Ottawa")
            said = SENTENCE_END.split(self._last_said())[0]
            text = " ".join([q] + self._names(said, q, single=True) + [text.strip(" ?.!,")])
        self.lookup_topic = text
        return text

    @staticmethod
    def _names(said, topic, single=False):
        """Names in an answer's first sentence that the topic does not have: "Sam Altman", Korean "샘 올트먼" (said
        before -이에요 / -입니다), with single also one capitalised word ("Ottawa")."""
        names = NAMES.findall(said) or (CAP_WORD.findall(said) if single else [])
        names += [m.group(1) for m in KO_NAME.finditer(said)]
        return [n for n in dict.fromkeys(names) if n.lower() not in topic.lower()]

    def is_lookup_follow_up(self, text):
        """'Tell me more' right after an answer from the internet: look it up again with that topic."""
        return bool(self.last_lookup and FOLLOW_UP.search(text) and self.history
                    and self.history[-1][0] == self.last_lookup)

    @staticmethod
    def _action(line, text, markers):
        m = re.match(r"\s*\**ACTION\**\s*:\s*(\w+)\s*(.*)", line, re.I) or \
            re.match(r"\s*(search|weather)\s+(\S.*)", line)   # "search Chung Ju-yung death date": no ACTION: written
        if not m:                                          # "none" / "search" alone on the first line (26b drops
            m = re.fullmatch(r"\s*([a-z_]+)(?:\s+([a-z0-9_ .-]{0,40}))?\s*", line)   # "ACTION:" now and then)
            m = m if m and m.group(1) in ACTION_NAMES | {"none", "unclear"} else None
            if m and m.group(2) is None:
                m = re.match(r"\s*(\w+)()", line)
        if not m:
            return None
        action, target = m.group(1).lower(), m.group(2).strip().strip("-.,\"'").strip()
        if action in ("move", "turn", "look", "lift"):
            target = " ".join(target.split()[:2]).lower()
            if action == "move" and float((re.findall(r"\d+(?:\.\d+)?", target) or ["0"])[0]) > MOVE_MAX_M:
                action = "none"                             # "앞으로 10미터 가": it says the limit, it does not drive
        elif action in ("pick", "move_object"):
            target = " ".join(target.lower().split()[:3])  # "white cup", "tennis ball"
        elif action not in ("weather", "search", "fetch", "go_to"):   # a fetch is read by parse_fetch() later
            target = target.split()[0] if target.split() else ""
        if action not in ACTION_NAMES:
            action = "none"
        say = None
        if action == "go_to":
            said = target if any(wording._key(mk) == wording._key(target) for mk in markers) else \
                (target.split() or [""])[0]                # "Coffee Corner"; "p3 (the meeting room)": its first word
            target = next((mk for mk in markers if wording._key(mk) == wording._key(said)), None)
            if not target and said.lower() not in ("", "none"):
                say = place_problem(f"go to {said}", markers) or no_place_say(said, markers, text)   # "go_to kitchen"
            if target and (not named_place(text, target, markers) or re.search(
                    rf"(?<![a-z0-9_]){re.escape(wording.written(target))}\s+(?:[a-z]|\d+)(?![a-z0-9.])", _norm(text, markers))):
                target = None                              # "take me to the meeting room" -> p1, "hall B" -> hall_A:
                say = no_place_say("that", markers, text)  # a guess, not driven
            action = "go_to" if target else "none"
        bare = re.sub(_LEAD, "", CALLING.sub("", text), flags=re.I)   # "Lumi Lumi, are you still following me?"
        if action in MOTIONS and (QUESTION_START.search(bare) and not (action in ("give", "receive") and
                                                                      re.match(r"(?:can|could|may) i\b", bare, re.I))
                                  or ABILITY_Q.search(text) or not_an_order(text, asked=False)):
            action, target = "none", ""                    # "where is your charger?", "손 펼 수 있어요?": a question;
                                                           # "she said follow me", "in five minutes go ...": no order now
        if action in ("look", "lift"):                     # "left", "left 30", "up small"; anything else is dropped
            d, _, n = target.partition(" ")
            if d not in (LOOK_TARGETS if action == "look" else ("up", "down")):
                action = "none"
            elif n and not re.fullmatch(r"small|\d+(?:\.\d+)?", n) or d in ("me", "center"):
                target = d
        if action in ("pick", "move_object") and not re.search(rf"(?<![a-z])(?:{_OBJ})s?(?![a-z])", target.lower()):
            action, target = "none", ""                    # "pick box": not a thing it knows (lumi would pick a cup)
        elif action in ("pick", "move_object"):
            cls = OBJECTS[re.search(rf"(?<![a-z])({_OBJ})s?(?![a-z])", target.lower()).group(1)]
            if not re.search(rf"(?<![a-z])(?:{'|'.join(re.escape(w) for w, c in OBJECTS.items() if c == cls)})", _norm(text)):
                action, target = "none", ""                # its own word must be said: "olma" is not an apple
        if action == "arm" and target not in ("reach", "fold", "open", "close"):
            action = "none"
        if action == "receive" and not RECEIVE_ASK.search(text):
            action = "none"                                # "I have an apple": news, not a hand-over
        if action in ("move", "come_back") and re.search(r"\bcome back\b|\breturn\b|돌아 ?(?:와|가|오|올|갈)",
                                                         _norm(text)) and driving.amount(_norm(text))[0] is None:
            action = "none"                                # "I'll come back later"; a real "come back" is intent() below
        if action == "move" and driving.amount(_norm(text))[0] == "?":
            action, target = "none", ""                    # "왼쪽으로 몇 미터 가 봐": how far is asked, not guessed
        if action == "come" and not COME_ASK.search(text):
            action = "none"                                # "my friend is over there"
        if action == "follow" and (not FOLLOW_ASK.search(text) or SOCIAL.search(text)):
            action = "none"                                # "follow me on instagram", "I like walking"
        if action == "wave" and not WAVE_ASK.search(text):
            action = "none"                                # "Hello Lumi!", "hello 해 봐": a greeting, not a wave
        if action not in ("go_to", "look", "lift", "weather", "search", "move", "turn", "arm", "fetch", "pick", "move_object",
                          "detour"):
            target = ""
        if action in ("search", "weather") and SPOKEN_TARGET.match(target):
            target = ""                                    # "search I'll look that up": the visitor's words are searched
        if action == "search" and not target:
            target = text
        if re.search(r"\b(bye|goodbye|(?<!can't )(?<!cant )(?<!cannot )(?<!not )(?<!to )see you|good night|i have to go|i'?m leaving)\b|안녕히|잘 ?가|잘 ?있어|"
                     r"다음에 봐|갈게요|가 ?볼게요|안녕\s*[.!]?$", text, re.I):
            action = "end"
        if action != "stop" and to_someone_else(text):
            action, target = "none", ""                    # "Hey Jake, come see this"
        if action in MOTIONS and LATER.search(bare):
            action, target = "none", ""                    # "when I say go, go to the stage": not now
        rule = intent(text, markers) if direct_order(text) else None   # clear orders win over the small model's guess
        if rule and not (rule[0] == "search" and action in ("go_to", "come", "look", "weather", "sing")):
            action, target = rule
        if action == "stop" and "?" in text:
            action = "none"                                # "how do I stop you?": a question about stopping
        if action == "end" and "?" in re.split(r"(?<=[.!?~])\s+", text.strip())[-1]:
            action = "none"                                # "thanks, and where is p3?": a question is no goodbye; the
                                                           # model reads "okay" / "됐어요" with the talk before (owner)
        out = {"action": action, "target": target or ""}
        if say and action == "none" and not QUESTION_START.search(text):
            out["say"] = say[1] if language(text) == "Korean" else say[0]   # its words said it would go: replaced
        return out

    def warm(self, markers=(), now=None):
        """Before the next question (lumi.py calls it when it starts to listen and when it starts): the runner processes
        the next prompt's start now (the last system prompt, or the first one, + the turns kept), so the question only
        costs its own last message, also after a lookup, a farewell, a mission read-back or a picture used the
        runner's one slot (else ~3.5 s more)."""
        system = self.last_system = getattr(self, "last_system", None) or route_system(markers, now)   # respond_from too
        turns = [{"role": r, "content": c} for q, a in self.history[-HISTORY_TURNS:] for r, c in (("user", q), ("assistant", a))]
        llm_direct.prefill([{"role": "system", "content": system}] + turns, MODEL)

    def reset(self):
        self.history = []
        self.last_lookup = None
        self.weather_at = ""


if __name__ == "__main__":
    act = "--act" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--act"]
    marker_names = []
    if act:
        from robot import agv
        marker_names = agv.markers()
        print("markers:", marker_names)
    brain = Brain()
    questions = [" ".join(args)] if args else None
    try:
        while True:
            q = questions.pop(0) if questions else (None if questions is not None else input("\nyou> ").strip())
            if not q:
                break
            t = time.time()
            if act:
                out = brain.respond(q, marker_names)
                print(f"lumi> {out['say']}\n      action={out['action']} target={out['target']!r} "
                      f"({time.time() - t:.1f} s)")
                continue
            reply, hits = brain.answer(q)
            print(f"lumi> {reply}")
            print(f"      ({time.time() - t:.1f} s; notes: " +
                  (", ".join(f"{src} {score:.2f}" for score, src, _ in hits) or "none") + ")")
    except (KeyboardInterrupt, EOFError):
        print()
