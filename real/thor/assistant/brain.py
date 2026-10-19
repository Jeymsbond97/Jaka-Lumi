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
import json
import random
import re
import sys
import time
import urllib.request

from assistant import knowledge
from assistant import wording
from assistant import web

OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "gemma4:26b"
MIN_SCORE = 0.42               # chunks below this similarity are not given to the LLM (fewer = faster)
NOTES_K = 2                    # note chunks given with each question
NOTES_K_COMPANY = 4            # ... about Cutshion: its facts are spread over many short chunks
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
- If the visitor's words are unclear, cut off or do not make sense, do NOT guess what they meant: choose the
  action "unclear" and politely ask them to say it again (e.g. "Sorry, I didn't catch that. Could you say it again?").
- If you do not know a fact about the world (people, places, events, products, prices, definitions, sports,
  anything after your training), do not guess: choose the action "search" so it is looked up on the internet.
- For facts about yourself and Cutshion Company use ONLY the reference notes. Only if the notes do not contain the
  answer, say you are not sure. Never say you were made or developed by any other company.
- The company's Korean name is 쿳션 (주식회사 쿳션); never write 컷션 or 커션.
- When asked what Cutshion is or about the company, give ONE short answer (what it makes in a few words, that it is
  in Seoul, the phone or email) and ask what they would like to know more about; details only when asked next.
- Questions about Cutshion (its robots, prices, people, jobs, hours, delivery, warranty, the CEO) are never looked
  up on the internet: if the notes do not say it, answer "I don't have that information" ("그 정보는 없어요").
- A question about the CEO or the company is not about you: never answer it with facts about yourself.
- Never mention "the reference notes" or "the notes" to the visitor.
- Facts about you: your name is Lumi. You understand speech with Whisper and answer with the language model Gemma 4,
  both running on your own NVIDIA Jetson AGX Thor (Gemma is made by Google, Whisper by OpenAI); you do not use
  ChatGPT or the cloud. You have a lidar, three depth
  cameras, six microphones and one arm with a two-finger gripper. A fact about yourself that is not here or in the
  notes (your price, charging time, battery level now): say you don't know and that a staff member can tell them.
- Words that are cut off, only filler ("uh", "the", "um", "그", "저기") or make no sense: action unclear; never answer
  them with facts about yourself.
- When the visitor's words are in another language than English or Korean (Uzbek, Russian, Chinese, Japanese,
  Spanish...): action unclear, do nothing they ask, say "Sorry, I only understand English and Korean." A question in
  English or Korean about a language ("can you speak Chinese?") is answered normally.
- A short follow-up ("and normally?", "which ones?", "why?", "tell me more", "몇 개?", "어디어디요?") is about the topic
  of your previous answer: answer that. "Say it again" / "다시 한 번만요" means repeat your previous answer; "and in
  Korean?" / "영어로는요?" means your previous answer in that language. Never answer a follow-up with a list of what
  you can do.
- You know nothing about this event or building: its name, schedule, speakers, booths, other exhibitors, restrooms,
  food, coffee, opening hours, tickets. Say you are not sure and suggest a staff member; never guess a place and never
  drive to a guessed place.
- Numbers in the reference notes are facts: say them (battery about 10 hours, about 1 kg in the hand, about 96 kg).
  Say you are not sure only when the notes do not have it.
- When the visitor thanks you or is done ("thank you for your time", "고마워요", "수고하세요", "잘 있어요"), choose the
  action end. Do not ask "Anything else?" / "더 필요한 거 있으세요?" after every answer.
- Small talk (greetings, how are you, thanks) does not need the notes: reply briefly, warmly and naturally,
  like a person would, fitting what was said in this conversation; do not repeat the same phrases.
- The date, the day and the time ("며칠이에요?", "is it lunch time yet?", "morning or afternoon?" -> say which,
  오전 / 오후) are in "Now it is" below: say them.
- A correction ("no, I meant the arm", "아니, 팔 말고 키요", "아니, 루미 키요") asks the same question again about what
  they name now: answer that.
- Never invent numbers, prices or dates.

What you can do (say this when asked what you can do): talk in English and Korean and answer questions;
tell the date and time; check the weather and look things up on the internet when it is connected; drive to the
places on your map (and back to your charging dock); come to the person who calls you; look left, right, up or
down; wave; sing a short song; stop and stay quiet when asked; pick up cups, bottles and fruit, put them down, bring
them to a place or a person, hand them over and take them from a person; do a task of several steps said in one
command ("take the cup, go to p3 and give it to Mina"). You greet people who come close and you wake up when
someone says "Hi Lumi"."""


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
    body = {"model": MODEL, "messages": messages, "stream": False, "think": False,
            "keep_alive": -1, "options": {"temperature": temperature, "num_predict": 200}}
    if fmt:
        body["format"] = fmt
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["message"]["content"].strip()


ACTIONS_STREAM = """
You can also move. Decide if the visitor asks you to do something:
- go_to <marker>: drive to a place. Marker names: {markers}. "home", "charger", "charging station" and
  "go back" mean home. Map spoken names to the closest marker name (e.g. "point one" -> p1).
- come: come to the visitor ("come here", "come to me", "come closer", "이리 와", "여기로 와").
- look <left|right|center|up|down|me>: turn your head ("look at me" -> me).
- move <forward|back|left|right> <metres>: drive a short distance ("come one metre forward" -> move forward 1,
  "go back a little" -> move back 0.5, "move left two metres" -> move left 2). At most 3 metres.
- turn <left|right|around> <degrees>: turn the whole body ("turn around" -> turn around 180,
  "turn left" -> turn left 90).
- arm <reach|fold|open|close>: stretch your arm forward ("reach out your hand"), fold it back, or open / close
  your hand (the gripper: "open your hand", "grab it", "let go").
- wave: wave your hand ("wave", "shake your hand", "say hi with your hand").
- pick <colour> <object>: pick up an object from the table in front of you ("pick up the white cup" -> pick white cup,
  "take the cup" -> pick cup). Objects: cup, bottle, apple, orange, banana.
- put <down|back>: put down what you hold, on a free spot ("put it down") or where it was ("put it back").
- move_object <colour> <object>: move an object on the table to a free spot next to it ("move the cup").
- fetch <colour> <object> from <marker|here> to <marker|here> <hold|place>: bring an object from one place to
  another ("bring me the apple from p1" -> fetch apple from p1 to here hold, "take the cup from p2 to home and put
  it on the table" -> fetch cup from p2 to home place). Leave out what the visitor did not say; never guess a word.
- give: hand over the object you are holding ("give it to me").
- place: put the object you are holding on the table ("put it on the table").
- stop: stop moving (also "stop Lumi", "stop it", "freeze", "멈춰", "그만 가"). Use quiet only when they say
  stop TALKING ("stop talking", "be quiet", "그만 말해").
- end: the visitor says goodbye or ends the conversation ("good night", "I have to go", "잘 가", "이제 갈게요").
A place must be one of the marker names exactly; a place that is not on the list ("the kitchen", "point 20",
"주방") is go_to none: say which places you know, never pick the nearest. fetch only when an object is named.
Short Korean commands are commands: "컵 가져다 줘" -> fetch cup, "컵 옮겨" -> move_object cup, "잡아" -> pick.
- quiet: the visitor wants silence ("be quiet", "stop talking", "shut up", "조용히 해", "그만 말해").
- sing: the visitor asks for a song. Then your words ARE the song: 4 to 8 short, cheerful, original lines.
- weather <place>: the visitor asks about the weather (place in English; - means here, Seoul).
- search <query>: you need facts from the internet you do not know (news, prices, opening hours, people...).
  Do not use search for things in the reference notes, the date or the time.
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

ACTION_NAMES = {"go_to", "come", "look", "wave", "stop", "end", "quiet", "sing", "weather", "search", "move", "turn",
                "arm", "pick", "put", "move_object", "fetch", "give", "place", "unclear", "none"}
LOOK_TARGETS = {"left", "right", "center", "up", "down", "me"}
SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")


def _stream(messages):
    """Yield text pieces from Ollama as they are generated."""
    body = {"model": MODEL, "messages": messages, "stream": True, "think": False,
            "keep_alive": -1, "options": {"temperature": 0.3, "num_predict": 200}}
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    pending = bytearray()                     # gemma4 streams some Hangul (쿳) as byte tokens "<0xEC><0xBF><0xB3>"
    with urllib.request.urlopen(req, timeout=120) as r:
        for line in r:
            d = json.loads(line)
            piece = d.get("message", {}).get("content", "")
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
            if d.get("done"):
                return


MOVE_MAX_M = 3.0                # m; a longer "move forward N m" is not a short move (lumi.MAX_MOVE_M)
NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
                "eight": "8", "nine": "9", "ten": "10"}
OBJECTS = {"cup": "cup", "mug": "cup", "glass": "cup", "tumbler": "cup", "bottle": "bottle", "apple": "apple",
           "orange": "orange", "banana": "banana", "컵": "cup", "잔": "cup", "병": "bottle", "사과": "apple",
           "오렌지": "orange", "바나나": "banana"}       # spoken word -> camera class (skills.py)
COLOURS = {"white": "white", "red": "red", "blue": "blue", "green": "green", "yellow": "yellow", "black": "black",
           "orange": "orange", "흰": "white", "하얀": "white", "빨간": "red", "파란": "blue", "초록": "green",
           "노란": "yellow", "검은": "black", "까만": "black", "주황": "orange", "주황색": "orange", "빨간색": "red",
           "파란색": "blue", "노란색": "yellow", "초록색": "green", "검은색": "black", "까만색": "black", "하얀색": "white",
           "흰색": "white"}
_OBJ = "|".join(OBJECTS)
_COL = "|".join(COLOURS)
STOP_TALK = re.compile(r"비상 ?정지|emergency stop|stop button|정지 ?버튼", re.I)   # about the stop button, not "stop!"
INTENTS = [   # (action, pattern) checked in order on what the visitor said
    ("quiet", r"\b(be quiet|keep quiet|quiet please|stop talking|shut up|silence|be silent|stop greeting)\b|조용히|그만 말|"
              r"시끄러워|말하지 마|인사 ?(그만|하지 ?마)"),
    ("stop", r"\b(stop|halt|freeze|don'?t move)\b|멈춰|정지|그만 ?가|거기 ?서|스톱|움직이지 ?마"),
    ("fetch", rf"\b(fetch|bring|deliver|carry)\b.*\b({_OBJ}|it|that|this)s?\b|\b(take|get|grab)\b.*\b({_OBJ})s?\b.*\b(from|to)\b"
              rf"|\b(go|drive) to\b.*\b(get|take|grab|pick up|fetch|bring)\b.*\b({_OBJ})s?\b"
              rf"|\b(pick up|pick|take|grab|get)\b.*\b({_OBJ})s?\b.*\b(go|drive) to\b|({_OBJ}).*(집어서|들고).*가서"
              r"|가져와|가져다|갖다|가지고 ?와|에서.*(옮겨|가져)" rf"|({_OBJ}).*(집고|들고|가지고).*(와|줘)"),
    ("come", r"\bcome (here|to me|closer|over here|over)\b|\bcome\b.*\bme\b|이리 ?와|여기로 ?와|가까이 ?와|나한테 ?와"),
    ("go_home", r"\bgo (back )?(home|to (the |your )?(dock(?!2)|charger|charging))|\bgo charge|충전하러|집(?:에|으로) ?가|충전기로"),
    ("go_point", r"\b(?:go|drive|move|head)(?: back)? to (?:the )?(?:point |marker )?([a-z]+\d*)\b|(\d+)\s*번\s*(?:으로|포인트)"   # after _norm:
                 r"|^\W*(?:(?:루미야?|lumi|hey lumi)\W*)?(?:좀\s*)?([a-z]+\d*)\s*(?:으로|로|에)\s*(?:좀\s*)?"   # "p3로 가 줘":
                 r"(?:가|와|이동해|돌아가)"                                                               # all of it
                 r"(?:\s*줘요?|\s*주세요|요|자|줄래)?\s*[.!?]*$"),
    ("sing", r"\bsing\b|\ba song\b|노래"),
    ("turn", r"\bturn (a)?round\b|\bturn (left|right)\b|뒤로 ?돌|돌아 ?봐|왼쪽으로 ?돌|오른쪽으로 ?돌"),
    ("move", r"\b(?!go ahead\b)(?:move|go|come|drive|step)\s+(?:a little\s+|a bit\s+)?(forward|ahead|back(?:ward)?|left|right)\b"
             r"(?:\s+(\d+(?:\.\d+)?|half)\s*(?:m|meters?|metres?)?)?|"
             r"\b(?:move|go|come)\s+(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\s+(forward|ahead|back(?:ward)?|left|right)\b|"
             r"(앞으로|뒤로|왼쪽으로|오른쪽으로)\s*(\d+(?:\.\d+)?)?\s*(?:미터|m)?\s*(?:가|와|이동|움직)"),
    ("put", r"\bput (it|that|this|the \w+) (back|down)\b|\bput (it|that|this|the \w+) (on|onto) the table\b"
            r"|제자리에 ?(놓|둬|놔)|다시 ?(놓|둬|놔)|내려 ?(놓|둬|놔)"),
    ("move_object", rf"\b(?:move|shift|slide) (?:the |that |this |a )?(?:({_COL}) )?({_OBJ})s?\b"
                    rf"|(?:({_COL})\s*)?({_OBJ})\s*(?:을|를)?\s*옮겨"),
    ("pick", rf"\b(?:pick up|pick|take|grab|get|lift|hold) (?:up )?(?:me )?(?:the |that |this |a |an )?(?:({_COL}) )?({_OBJ})s?\b"
             rf"|(?:({_COL})\s*)?({_OBJ})\s*(?:을|를)?\s*(?:좀\s*)?(?:잡아|집어|들어)"),
    ("grip_open", r"\b(open (your )?(hand|gripper|fingers)|let (it )?go|drop it)\b|손을? ?(펴|벌려|열어)|놓아"),
    ("grip_close", r"\b(close (your )?(hand|gripper|fingers)|grab (it|this)|grip (it|this))\b"
                   r"|손을? ?(쥐|오므려|닫아)|잡아"),
    ("arm", r"\b(reach out|stretch (out )?your (arm|hand)|put your (arm|hand) (out|forward)|hand forward)\b|팔을? ?(뻗|내밀)"),
    ("weather", r"\bweather\b|\bforecast\b|\b(will it|is it going to) rain\b|\btemperature (outside|today)\b|날씨|비 ?와|기온"
                r"|\b(cold|hot|warm|chilly) (outside|out)\b|\bumbrella\b|우산|밖에 ?(추|더)워"
                r"|\bhow (hot|cold|warm) is it\b|\b(is it|will it be) (sunny|cloudy|windy|raining|snowing)\b|\bwill it snow\b"
                r"|눈 ?(이 )?(와|올 ?까|오나|온대|오니)|(오늘|내일|밖|바깥)(은|에|이)? ?(덥|춥|더워|추워)"),
    ("search", r"\b(news|latest|headlines|who won|score of|price of|exchange rate|stock)\b|뉴스|환율|(?<![가-힣])주가"),
]


def intent(text, markers=()):
    """(action, target) for clear requests, or None. Backs up the LLM's ACTION line."""
    t = _norm(text)                                         # "point five" -> "point 5"
    asks = re.search(r"^\s*(how|why|what if)\b|\b(how do you|how can you|can you carry|are you able)\b|"
                     r"\b(can|could) you (pick( up)?|lift|hold|grab|take) (a|an|any)\b|"   # "can you pick up a bottle?"
                     r"^\s*(what|when|which|at what|do you|does|is it|are you)\b|몇|언제|얼마|"   # "at what level do you go back?"
                     rf"({_OBJ})(은|는)\s.*수 ?있|(루미가|로봇이)\s.*수 ?있|는 ?거 ?(돼|되나|가능)|"                                  # "물컵은 가져다줄 수 있어요?"
                     r"어떻게|왜|혼자|스스로|\bby yourself\b|\bsomeone\b", t)
    for action, pat in INTENTS:
        m = re.search(pat, t, re.I)
        if not m:
            continue
        if action == "stop" and STOP_TALK.search(t):
            return None                                     # "where's your emergency stop?": a question
        if action != "quiet" and re.search(r"\b(don'?t|do not|never)\b|(하|펴|가|잡|놓|열)지 ?마", t) and action != "stop":
            return None                                     # "don't go to p1", "손 펴지 마": not an order
        if asks and action in ("go_home", "go_point", "move", "turn", "pick", "put", "move_object", "fetch", "come",
                               "arm", "grip_open", "grip_close"):
            return None                                     # "how do you pick up a cup?": a question, not an order
        if action == "go_home":
            if re.search(r"(^|\s)(나|저|우리|저희)(는|도)?\s", t):
                return None                                 # "나 이제 집에 가": the visitor goes home
            return ("go_to", "home") if "home" in markers else None
        if action == "go_point":
            word = m.group(1) or m.group(3) or f"p{m.group(2)}"
            name = next((mk for mk in markers if mk.lower() == word), None)
            if name and (len(name) > 1 or named_place(text, name, markers)):   # "a": not "go to a meeting room"
                return ("go_to", name)
            if re.fullmatch(r"p\d+", word):
                return None                                 # "go to p12": not on the map
            continue                                        # "go to the kitchen", "move to the left ..."
        if action == "weather":
            if re.search(r"\bhow do you (know|check|get|find)\b|어떻게 (알|확인)", t):
                return None                                 # "how do you know the weather?": about Lumi
            place = re.search(r"\bin ([A-Za-z][A-Za-z ]+?)(\?|$|\.| today| tomorrow| right now| now| this)", text)
            return ("weather", place.group(1).strip() if place else "")
        if action == "search":
            return ("search", text)
        if action == "fetch":
            return ("fetch", text)                        # parse_fetch() reads the details
        if action == "turn":
            if re.search(r"around|뒤로", t) or not re.search(r"left|right|왼쪽|오른쪽", t):   # "왼쪽으로 돌아": left
                return ("turn", "around 180")
            deg = re.search(r"(\d+)\s*(degrees?|도)", t)                # "turn left 45 degrees"
            return ("turn", ("left" if re.search(r"left|왼쪽", t) else "right") + f" {deg.group(1) if deg else 90}")
        if action == "move":
            g = [x for x in m.groups() if x]
            dirs = {"ahead": "forward", "backward": "back", "앞으로": "forward", "뒤로": "back", "왼쪽으로": "left",
                    "오른쪽으로": "right"}
            d = next((dirs.get(x, x) for x in g if not re.match(r"[\d.]+$|half$", x)), "forward")
            n = next((0.5 if x == "half" else float(x) for x in g if re.match(r"[\d.]+$|half$", x)), 1.0)
            if re.search(r"a little|a bit|조금", t):
                n = min(n, 0.5)
            if n > MOVE_MAX_M:
                return None                                 # "move forward ten metres": the LLM says the limit
            return ("move", f"{d} {n:g}")
        if action == "arm":
            return ("arm", "reach")
        if action in ("grip_open", "grip_close"):
            return ("arm", action[5:])
        if action == "put":
            return ("put", "back" if re.search(r"\bback\b|제자리|다시", t) else "down")
        if action in ("pick", "move_object"):
            g = [x for x in m.groups() if x]                  # [colour,] object
            return (action, f"{COLOURS[g[0]]} {OBJECTS[g[1]]}" if len(g) == 2 else OBJECTS[g[0]])
        return (action, "")
    return None


# ---------- fetch tasks (docs/16 §4): strict parsing, nothing is guessed ----------
_HERE = r"here|me|여기|이쪽|나한테|저한테|나에게|저에게"
_HOME = r"home|charger|charging station|dock|충전기|충전소"
_TABLE = r"table|테이블|책상|탁자"
_PLACE_WORD = rf"(?:point|marker|포인트)\s*(\d+)|(?<![a-z])p\s?(\d+)(?!\d)|(\d+)\s*번|(?<![a-z])({_HOME}|{_HERE})(?![a-z])"
_NOT_OBJ = r"(?:not|instead of) (?:the |a |an )?$"            # "not the apple, the cup": the apple is not meant


def _norm(text):
    """Lower case, marker names and numbers as written (wording.py: "피쓰리" -> "p3", "point one" -> "p1")."""
    t = wording.norm(text)
    for word, digit in NUMBER_WORDS.items():                # "one of them" -> "1 of them"
        t = re.sub(rf"\b{word}\b", digit, t)
    return t


def _place_re(markers):
    """Place words; other marker names on the map ("final", "lobby") are matched as they are."""
    extra = [re.escape(m.lower()) for m in markers if not re.fullmatch(r"p\d+|home", m.lower()) and len(m) > 2]
    return _PLACE_WORD + (rf"|(?<![a-z])({'|'.join(extra)})(?![a-z])" if extra else "")


def _resolve(m, markers):
    """A place-word match -> "here", a marker name, or None (a place that is not on the map)."""
    n = m.group(1) or m.group(2) or m.group(3)
    word = next((g for g in m.groups()[3:] if g), "")
    if re.fullmatch(_HERE, word):
        return "here"
    name = f"p{n}" if n else ("home" if re.fullmatch(_HOME, word) else word)
    return next((mk for mk in markers if mk.lower() == name), None)


def _as_place(name):
    return name if name in ("here", None) else {"marker": name}


def _mentions(text, markers):
    """What the words name: {"object", "colour", "source", "dest", "finish"}, only the fields mentioned.
    "object" / "source" / "dest" is None when the word is there but unknown."""
    t, out = _norm(text), {}
    objs = [m for m in re.finditer(rf"(?:({_COL})\s*)?(?<![a-z])({_OBJ})s?(?![a-z])", t)
            if not re.search(_NOT_OBJ, t[:m.start()]) and not re.match(r"\s*(?:말고|아니고|아니라)", t[m.end():])]
    if objs:
        out["object"], out["colour"] = OBJECTS[objs[-1].group(2)], COLOURS.get(objs[-1].group(1))
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
    for m in re.finditer(rf"\b(?:to|into) (?:the )?([a-z]+)", t):
        if m.start() > after_obj and "dest" not in out and not re.match(rf"{_TABLE}|{_place_re(markers)}", t[m.start(1):]) \
                and m.group(1) not in ("put", "place", "hold", "give", "keep", "bring", "leave"):
            out["dest"] = None
    if "dest" not in out and re.search(r"\b(bring|get|fetch|give) (it |that |this )?(to )?me\b|\bto me\b|가져와|가지고 ?와|갖다 ?줘", t):
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
    t = _norm(text)
    if marker == "home" and re.search(r"\bgo back\b|돌아가|\b(?:home|dock|charger|charging station)\b|집(?:으로|에)|"
                                      r"충전|도크", t):
        return True
    if len(marker) == 1:
        return bool(re.search(rf"\b(?:point|marker) {marker.lower()}(?![a-z])|\bto {marker.lower()}(?:[\s,.!?]*$|"
                              rf"\s+(?:and|then)\b|,)", t))
    return bool(re.search(rf"(?<![a-z]){re.escape(marker.lower())}(?![a-z0-9])", t)) or \
        any(_resolve(m, markers) == marker for m in re.finditer(_place_re(markers), t))


def fetch_problems(task):
    """'object' / 'place' (source) / 'dest': what is still missing or unknown in a task."""
    return [p for p, f in (("object", "object"), ("place", "source"), ("dest", "dest")) if task.get(f) is None]


def parse_fetch(text, markers=()):
    """'bring me the apple from p1' -> (task, problems). Missing source = here; missing destination = here only
    for "bring me" / "가져와", else a problem; finish = place when the table is named, else hold."""
    m = _mentions(text, markers)
    task = {"object": m.get("object"), "colour": m.get("colour"), "source": m.get("source", "here"),
            "dest": m.get("dest"), "finish": m.get("finish", "hold")}
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


def spoken(sentence, lang):
    """A sentence as it may be said: in English the company is "Cutshion", not "쿳션 (Cutshion Company)"."""
    if lang == "English":
        sentence = re.sub(r"쿳션\s*\(([^)]*)\)", r"\1", sentence).replace("쿳션", "Cutshion")
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


SUPPORTS = {"table": "dining table", "desk": "dining table", "chair": "chair", "stool": "chair", "sofa": "couch",
            "couch": "couch", "bench": "bench", "bed": "bed", "테이블": "dining table", "탁자": "dining table",
            "책상": "dining table", "식탁": "dining table", "의자": "chair", "소파": "couch", "벤치": "bench", "침대": "bed"}   # word -> camera class


def place_on(text):
    """What to put the held object on: {"name": camera class, "colour": colour or None} for "on the orange chair",
    "빨간 의자에"; None when no such thing is named."""
    t = _norm(text)
    m = re.search(rf"(?:\b(?:on|onto)\s+(?:the\s+|a\s+|that\s+)?)(?:({_COL})\s+)?({'|'.join(k for k in SUPPORTS if k.isascii())})s?\b", t) \
        or re.search(rf"(?:({_COL})\s*)?({'|'.join(k for k in SUPPORTS if not k.isascii())})", t)
    return {"name": SUPPORTS[m.group(2)], "colour": COLOURS.get(m.group(1))} if m else None


def held_command(text):
    """While holding: 'give' / 'place' for "give it to me", "put it on the table", "줘", "테이블에 놔". A table named
    wins ("bring it to p5 and put it on the table" is a place)."""
    if HELD_PLACE.search(text) and re.search(r"\btables?\b|테이블|탁자|책상", text, re.I):
        return "place"
    if HELD_GIVE.search(text):
        return "give"
    if HELD_PLACE.search(text):
        return "place"
    return None


def parse_correction(text, task, markers=(), field=None):
    """'no, from p2' / 'not the apple, the cup' / 'to p3' / 'put it on the table' / 'just hold it' -> (task, changed).
    field: the field a bare answer is about ("source" / "dest"), when Lumi just asked for it ("p2" -> that field)."""
    m, task = _mentions(text, markers), dict(task)
    if field in ("source", "dest") and not {"source", "dest"} & set(m):
        p = re.search(_place_re(markers), _norm(text))
        if p:
            m[field] = _as_place(_resolve(p, markers))
    changed = [k for k, v in m.items() if task.get(k) != v and not (k == "colour" and "object" not in m)]
    for k in changed:
        task[k] = m[k]
    return task, changed


_YES = r"yes|yeah|yep|yup|ok|okay|sure|right|correct|that'?s right|go ahead|do it|please|네|예|응|어|맞아요?|맞습니다|좋아요?|그래요?"
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
REFERS_BACK = re.compile(r"\b(it|they|them|those|these|another|one more|one about)\b|그거|그걸|그건|그게|그것|하나 ?더|또 ?하나",
                         re.I)   # about the last answer
HELP_OFFER = re.compile(r"\b(how|what) (can|may) i (help|assist|do for) you\b|\bis there anything (else )?i can\b|"
                        r"\banything else i can (help|do)\b|\blet me know if (there'?s|there is|you need) anything\b|"
                        r"무엇을 도와|어떻게 도와|뭘 도와|도와드릴 일", re.I)   # owner: never tacked on after an answer
FOLLOW_UP = re.compile(r"\b(more|why|how come|details?|explain|elaborate|and then|what else|tell me more)\b|자세히|더 알려|왜|그리고", re.I)
_CLOSE_WORD = (r"(ok(ay)?|okay then|thanks?( you)?( very much)?( a lot)?|thank you( so much)?|got it|alright|all right|"
               r"fine|good|great|cool|nice|perfect|stop|enough|that'?s (it|all|enough|fine)|so|sure|i see|understood|"
               r"no thanks|nothing|never ?mind|lumi|루미|고마워요?|감사합니다|감사해요|알겠어요?|알았어요?|오케이|됐어요?|그만|좋아요?|"
               r"i got (it|you)|got you|i understand|makes sense|that makes sense|okay,? i understand|"
               r"네|예|그래요?|알겠습니다|알겠어|이해했어요|이해했습니다|그렇군요|아하)")
CLOSING = re.compile(rf"^(\s*{_CLOSE_WORD}[\s,.!]*)+$", re.I)   # one or several: "okay, thanks", "got it, thank you"


WAKE_WORD_RE = re.compile(r"\b(lumi|loomi|rumi)\b|루미", re.I)


def is_closing(text):
    """'okay', 'thanks', 'got it', 'stop'...: the visitor is done with this answer."""
    return bool(CLOSING.match(text or ""))


def warm_up():
    """Load the model into the GPU now, so the first answer is fast."""
    _chat([{"role": "user", "content": "Hi"}])


_recent_byes = collections.deque(maxlen=FAREWELL_RECENT)


def _opening(text, words=3):
    return " ".join(re.sub(r"[^\w\s]", "", text.lower()).split()[:words])
FORCED_LANG = {}                   # {"lang": "en"|"ko"} set by lumi.py from the speech recogniser


def language(text):
    """'Korean' or 'English': what the speech recogniser heard, else Hangul in the text."""
    lang = FORCED_LANG.get("lang")
    if lang:
        return "Korean" if lang == "ko" else "English"
    return "Korean" if re.search(r"[\uac00-\ud7a3]", text) else "English"


class Brain:
    def __init__(self):
        self.history = []                 # [(question, answer)]
        self.last_lookup = None           # the last question answered from the internet

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
        if re.search(r"\b(bye|goodbye|see you|good night|i have to go|i'?m leaving)\b|안녕히|잘 ?가|잘 ?있어|"
                     r"다음에 봐|갈게요|안녕\s*[.!]?$", text, re.I):
            out["action"] = "end"
        self.history.append((text, json.dumps(out, ensure_ascii=False)))
        return out

    def respond_stream(self, text, markers=(), now=None):
        """Generator: first {"action", "target"}, then the spoken reply sentence by sentence. now: what Lumi is doing
        at the moment (lumi.now_doing), so a question about it is answered from facts."""
        about = self.topic(text)                                              # "which ones?": the topic before
        context = f"{self.history[-1][0]} {text}" if self.history else text    # "how heavy can the items be?"
        k = NOTES_K_COMPANY if COMPANY_TALK.search(context) else NOTES_K
        hits = knowledge.search(about, k=k)
        if context != about:                                                  # the words alone, and with the
            hits += [h for h in knowledge.search(context, k=NOTES_K)          # question before (one more chunk)
                     if h[2] not in {x[2] for x in hits}][:1]
        hits = [h for h in hits if h[0] >= MIN_SCORE]
        notes = "\n\n".join(f"[{src}]\n{t}" for _, src, t in hits) or "(no matching notes)"
        system = SYSTEM + f"\nNow it is {web.now_text()}." + (f"\nWhat you are doing now: {now}" if now else "") + \
            "\n" + ACTIONS_STREAM.format(markers=", ".join(markers) or "(none)")
        messages = [{"role": "system", "content": system}]
        for q, a in self.history[-HISTORY_TURNS:]:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": f"Reference notes:\n{notes}\n\n{_examples(about, on_task=bool(now) and 'not doing any task' not in now)}Visitor: {text}\n\n"
                                                    f"(Reply in {language(text)}.)"})
        buf, full, header, said = "", "", None, []
        try:
            for piece in _stream(messages):
                full += piece
                buf += piece
                if header is None:
                    if "\n" not in buf:
                        continue
                    first, buf = buf.split("\n", 1)
                    header = self._action(first, text, markers)
                    if header is None:                     # the model skipped the ACTION line
                        header, buf = {"action": "none", "target": ""}, first + " " + buf
                    yield header
                    if header["action"] == "unclear" and other_latin_language(text):
                        said.append(OTHER_LANGUAGE["en"])  # Uzbek / German in Latin letters: not "say it again"
                        yield said[0]
                        buf, full = "", f"{first}\n{said[0]}"
                        break
                parts = SENTENCE_END.split(buf)
                for sentence in parts[:-1]:
                    if sentence.strip() and not (said and HELP_OFFER.search(sentence)):
                        said.append(spoken(sentence.strip(), language(text)))
                        yield said[-1]
                buf = parts[-1]
        except Exception:
            if header is None:
                yield {"action": "none", "target": ""}
                header = {}
            buf += " Sorry, could you say that again?"
        if header is None:                                 # very short reply on a single line
            header = self._action(buf, text, markers)
            yield header or {"action": "none", "target": ""}
            buf = "" if header else buf
        if buf.strip() and not (said and HELP_OFFER.search(buf)):
            said.append(spoken(buf.strip(), language(text)))
            yield said[-1]
        for sentence in re.split(r"(?<=[.!?])\s+", full):   # a dropped "How can I help?" is not kept either
            if HELP_OFFER.search(sentence) and sentence.strip() not in said:
                full = full.replace(sentence, "")
        self.history.append((text, full.strip()))

    def topic(self, text):
        """What the words are about: a short follow-up ("tell me more", "can they see in the dark?") goes with the
        previous question, for the notes, the examples and the lookup decision."""
        if self.history and (len(text.split()) <= 4 or FOLLOW_UP.search(text) or REFERS_BACK.search(text)):
            return " ".join([q for q, _ in self.history[-2:]] + [text])   # "which ones?" then "can they...?"
        return text

    def respond_from(self, question, facts):
        """Spoken answer built from looked-up facts (weather, web results); yields sentences."""
        messages = [{"role": "system", "content": SYSTEM + f"\nNow it is {web.now_text()}."}]
        for q, a in self.history[-HISTORY_TURNS:]:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": f"Facts found just now on the internet:\n{facts}\n\nVisitor: {question}\n\n"
                                                    f"Answer the visitor directly in {language(question)}: short and exact, "
                                                    f"1 or 2 spoken sentences (more only if they asked for more), no lists, "
                                                    f"no links. Use the facts, and your own general knowledge where the facts "
                                                    f"are incomplete. Do not talk about the facts or the search themselves."})
        buf, full = "", ""
        for piece in _stream(messages):
            full += piece
            buf += piece
            parts = SENTENCE_END.split(buf)
            for sentence in parts[:-1]:
                if sentence.strip():
                    yield sentence.strip()
            buf = parts[-1]
        if buf.strip():
            yield buf.strip()
        self.history.append((question, full.strip()))
        self.last_lookup = question                        # a "tell me more" next is looked up again

    def farewell(self, text, lang="en"):
        """A short natural goodbye that fits the conversation (what the visitor just said, or their silence),
        unlike the goodbyes said lately (FAREWELL_RECENT)."""
        from assistant import talk_examples
        said = f'The visitor just said: "{text}".' if text else "The visitor has stopped talking."
        ideas = random.sample([r for c, lg, _, r in talk_examples.EXAMPLES if c == "goodbye" and lg == lang], 3)
        avoid = " ".join(f'"{b}"' for b in _recent_byes)
        messages = [{"role": "system", "content": SYSTEM + f"\nNow it is {web.now_text()}."}]
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
            bye = _chat(messages).strip().strip('"')
            if _opening(bye) in {_opening(b) for b in _recent_byes}:   # same start as a recent one: once more, freer
                bye = _chat(messages, temperature=FAREWELL_RETRY_T).strip().strip('"')
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
        """What to look up: a follow-up ("tell me more") is about the previous question."""
        if FOLLOW_UP.search(text) and self.history:
            return f"{self.last_lookup or self.history[-1][0]} {text}"
        return text

    def is_lookup_follow_up(self, text):
        """'Tell me more' right after an answer from the internet: look it up again with that topic."""
        return bool(self.last_lookup and FOLLOW_UP.search(text) and self.history
                    and self.history[-1][0] == self.last_lookup)

    @staticmethod
    def _action(line, text, markers):
        m = re.match(r"\s*\**ACTION\**\s*:\s*(\w+)\s*(.*)", line, re.I)
        if not m:
            return None
        action, target = m.group(1).lower(), m.group(2).strip().strip("-.,\"'").strip()
        if action in ("move", "turn"):
            target = " ".join(target.split()[:2])
        elif action not in ("weather", "search", "fetch"):     # a fetch is read by parse_fetch() later
            target = target.split()[0] if target.split() else ""
        if action not in ACTION_NAMES:
            action = "none"
        if action == "go_to":
            target = next((mk for mk in markers if mk.lower() == target.lower()), None)
            if target and not named_place(text, target, markers):
                target = None                              # "take me to the meeting room" -> p1: a guess, not driven
            action = "go_to" if target else "none"
        if action == "look" and target not in LOOK_TARGETS:
            action = "none"
        if action == "arm" and target not in ("reach", "fold", "open", "close"):
            action = "none"
        if action not in ("go_to", "look", "weather", "search", "move", "turn", "arm", "fetch"):
            target = ""
        if action == "search" and not target:
            target = text
        if re.search(r"\b(bye|goodbye|see you|good night|i have to go|i'?m leaving)\b|안녕히|잘 ?가|잘 ?있어|"
                     r"다음에 봐|갈게요|안녕\s*[.!]?$", text, re.I):
            action = "end"
        rule = intent(text, markers)                       # clear wordings win over the small model's guess
        if rule and not (rule[0] == "search" and action in ("go_to", "come", "look", "weather", "sing")):
            action, target = rule
        return {"action": action, "target": target or ""}

    def reset(self):
        self.history = []
        self.last_lookup = None


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
