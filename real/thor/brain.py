"""Lumi's answers: knowledge search (RAG) + local LLM (Ollama, gemma4). English and Korean.

    python brain.py                       # type questions, empty line or Ctrl+C to quit
    python brain.py "What can you do?"    # one question
    python brain.py --act                 # also decide robot actions (go_to / look / wave / stop / end)

The answer comes back in the language of the question and is kept short, because Lumi speaks it aloud.
respond_stream() streams the reply: the first line names the action, then the spoken sentences come one by
one while the LLM is still writing, so Lumi can start talking after the first sentence (about 1 s).
The model is kept loaded (keep_alive -1): a cold start costs ~6 s.
"""
import json
import re
import sys
import time
import urllib.request

import knowledge
import tools

OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "gemma4:e4b"
MIN_SCORE = 0.42               # chunks below this similarity are not given to the LLM (fewer = faster)
HISTORY_TURNS = 4              # previous question/answer pairs kept for follow-up questions

SYSTEM = """You are Lumi, a friendly mobile robot assistant made by JAKA Robotics, standing in front of a visitor.
Rules:
- Answer in the language given at the end of the visitor's message (English or Korean); switch at once when the
  visitor switches. Never answer in Chinese.
- Answer exactly what was asked, nothing else: short and exact, usually 1 or 2 sentences, no lists, no markdown,
  no emojis. Do not introduce yourself or list what you can do unless you are asked. Only when the visitor asks
  for more ("tell me more", "why", "details", "자세히") give more about that same topic.
- If the visitor's words are unclear, cut off or do not make sense, do NOT guess what they meant: choose the
  action "unclear" and politely ask them to say it again (e.g. "Sorry, I didn't catch that. Could you say it again?").
- If you do not know a fact about the world (people, places, events, products, prices, definitions, sports,
  anything after your training), do not guess: choose the action "search" so it is looked up on the internet.
- For facts about yourself, JAKA or its products use ONLY the reference notes. They may be written in Chinese;
  translate what you need. Only if the notes do not contain the answer, say you are not sure.
- Small talk (greetings, how are you, thanks) does not need the notes: reply briefly, warmly and naturally,
  like a person would, fitting what was said in this conversation; do not repeat the same phrases.
- Never invent numbers, prices or dates.

What you can do (say this when asked what you can do): talk in English and Korean and answer questions;
tell the date and time; check the weather and look things up on the internet when it is connected; drive to the
places on your map (and back to your charging dock); come to the person who calls you; look left, right, up or
down; wave; sing a short song; stop and stay quiet when asked. You greet people who come close and you wake up
when someone says "Hi Lumi"."""


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


def _chat(messages, fmt=None):
    body = {"model": MODEL, "messages": messages, "stream": False, "think": False,
            "keep_alive": -1, "options": {"temperature": 0.3, "num_predict": 200}}
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
- arm <reach|fold>: stretch your arm forward ("reach out your hand") or fold it back.
- wave: wave your hand ("wave", "shake your hand", "say hi with your hand").
- stop: stop moving.
- end: the visitor says goodbye or ends the conversation.
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
                "arm", "unclear", "none"}
LOOK_TARGETS = {"left", "right", "center", "up", "down", "me"}
SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")


def _stream(messages):
    """Yield text pieces from Ollama as they are generated."""
    body = {"model": MODEL, "messages": messages, "stream": True, "think": False,
            "keep_alive": -1, "options": {"temperature": 0.3, "num_predict": 200}}
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        for line in r:
            d = json.loads(line)
            piece = d.get("message", {}).get("content", "")
            if piece:
                yield piece
            if d.get("done"):
                return


NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
                "eight": "8", "nine": "9", "ten": "10", "일": "1", "이": "2", "삼": "3", "사": "4", "오": "5"}
INTENTS = [   # (action, pattern) checked in order on what the visitor said
    ("quiet", r"\b(be quiet|keep quiet|quiet please|stop talking|shut up|silence|be silent)\b|조용히|그만 말|시끄러워|말하지 마"),
    ("come", r"\bcome (here|to me|closer|over here|over)\b|\bcome\b.*\bme\b|이리 ?와|여기로 ?와|가까이 ?와|나한테 ?와"),
    ("go_home", r"\bgo (back )?(home|to (the |your )?(dock|charger|charging))|\bgo charge|충전하러|집에 ?가|충전기로"),
    ("go_point", r"\b(?:go|drive|move) to (?:the )?(point|marker|p)\s*(\d+)|포인트\s*(\d+)|(\d+)\s*번\s*(?:으로|포인트)"),
    ("sing", r"\bsing\b|\ba song\b|노래"),
    ("turn", r"\bturn (a)?round\b|\bturn (left|right)\b|뒤로 ?돌|돌아 ?봐|왼쪽으로 ?돌|오른쪽으로 ?돌"),
    ("move", r"\b(?:move|go|come|drive|step)\s+(?:a little\s+|a bit\s+)?(forward|ahead|back(?:ward)?|left|right)\b"
             r"(?:\s+(\d+(?:\.\d+)?|half)\s*(?:m|meters?|metres?)?)?|"
             r"\b(?:move|go|come)\s+(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\s+(forward|ahead|back(?:ward)?|left|right)\b|"
             r"(앞으로|뒤로|왼쪽으로|오른쪽으로)\s*(\d+(?:\.\d+)?)?\s*(?:미터|m)?\s*(?:가|와|이동|움직)"),
    ("arm", r"\b(reach out|stretch (out )?your (arm|hand)|put your (arm|hand) (out|forward)|hand forward)\b|팔을? ?(뻗|내밀)"),
    ("weather", r"\bweather\b|\bforecast\b|\b(will it|is it going to) rain\b|\btemperature (outside|today)\b|날씨|비 ?와|기온"),
    ("search", r"\b(news|latest|headlines|who won|score of|price of|exchange rate|stock)\b|뉴스|환율|주가"),
]


def intent(text, markers=()):
    """(action, target) for clear requests, or None. Backs up the LLM's ACTION line."""
    t = text.lower()
    for word, digit in NUMBER_WORDS.items():                # "point five" -> "point 5"
        t = re.sub(rf"\b{word}\b", digit, t)
    for action, pat in INTENTS:
        m = re.search(pat, t, re.I)
        if not m:
            continue
        if action == "go_home":
            return ("go_to", "home") if "home" in markers else None
        if action == "go_point":
            n = next(g for g in m.groups()[1:] if g)
            name = next((mk for mk in markers if mk.lower() == f"p{n}"), None)
            return ("go_to", name) if name else None
        if action == "weather":
            place = re.search(r"\bin ([A-Za-z][A-Za-z ]+?)(\?|$|\.| today| tomorrow)", text)
            return ("weather", place.group(1).strip() if place else "")
        if action == "search":
            return ("search", text)
        if action == "turn":
            if re.search(r"around|뒤로|돌아", t):
                return ("turn", "around 180")
            return ("turn", ("left" if re.search(r"left|왼쪽", t) else "right") + " 90")
        if action == "move":
            g = [x for x in m.groups() if x]
            dirs = {"ahead": "forward", "backward": "back", "앞으로": "forward", "뒤로": "back", "왼쪽으로": "left",
                    "오른쪽으로": "right"}
            d = next((dirs.get(x, x) for x in g if not re.match(r"[\d.]+$|half$", x)), "forward")
            n = next((0.5 if x == "half" else float(x) for x in g if re.match(r"[\d.]+$|half$", x)), 1.0)
            if re.search(r"a little|a bit|조금", t):
                n = min(n, 0.5)
            return ("move", f"{d} {min(n, 3.0):g}")
        if action == "arm":
            return ("arm", "reach")
        return (action, "")
    return None


UNSURE = re.compile(r"\b(not sure|don't know|do not know|don't have (any )?(information|details|data)|"
                    r"do not have (any )?(information|details|data)|no information|can't (tell|say|find)|cannot (tell|say|find)|"
                    r"unable to|ask a staff|i'm afraid i|my knowledge|would you like me to (search|look))\b|"
                    r"모르|알 수 없|알지 못|정보(가|는|를)? ?(없|가지고 있지 않)|가지고 있지 않|확실하지|드릴 수 없", re.I)
FOLLOW_UP = re.compile(r"\b(more|why|how come|details?|explain|elaborate|and then|what else|tell me more)\b|자세히|더 알려|왜|그리고", re.I)
_CLOSE_WORD = (r"(ok(ay)?|okay then|thanks?( you)?( very much)?( a lot)?|thank you( so much)?|got it|alright|all right|"
               r"fine|good|great|cool|nice|perfect|stop|enough|that'?s (it|all|enough|fine)|so|sure|i see|understood|"
               r"no thanks|nothing|never ?mind|lumi|루미|고마워요?|감사합니다|감사해요|알겠어요?|알았어요?|오케이|됐어요?|그만|좋아요?)")
CLOSING = re.compile(rf"^(\s*{_CLOSE_WORD}[\s,.!]*)+$", re.I)   # one or several: "okay, thanks", "got it, thank you"


WAKE_WORD_RE = re.compile(r"\b(lumi|loomi|rumi)\b|루미", re.I)


def is_closing(text):
    """'okay', 'thanks', 'got it', 'stop'...: the visitor is done with this answer."""
    return bool(CLOSING.match(text or ""))


def warm_up():
    """Load the model into the GPU now, so the first answer is fast."""
    _chat([{"role": "user", "content": "Hi"}])


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
        messages.append({"role": "user", "content": f"Reference notes:\n{notes}\n\nVisitor: {question}\n\n"
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
        messages.append({"role": "user", "content": f"Reference notes:\n{notes}\n\nVisitor: {text}\n\n"
                                                    f"(Reply in {language(text)}.)"})
        try:
            out = json.loads(_chat(messages, RESPONSE_SCHEMA))
        except (json.JSONDecodeError, KeyError):
            out = {"action": "none", "target": "", "say": "Sorry, could you say that again?"}
        if out.get("action") == "go_to" and out.get("target") not in markers:
            out["action"] = "none"
        if re.search(r"\b(bye|goodbye|see you)\b|안녕히|잘 ?가|다음에 봐", text, re.I):
            out["action"] = "end"
        self.history.append((text, json.dumps(out, ensure_ascii=False)))
        return out

    def respond_stream(self, text, markers=()):
        """Generator: first {"action", "target"}, then the spoken reply sentence by sentence."""
        hits = [h for h in knowledge.search(text, k=2) if h[0] >= MIN_SCORE]
        notes = "\n\n".join(f"[{src}]\n{t}" for _, src, t in hits) or "(no matching notes)"
        system = SYSTEM + f"\nNow it is {tools.now_text()}." + "\n" + ACTIONS_STREAM.format(markers=", ".join(markers) or "(none)")
        messages = [{"role": "system", "content": system}]
        for q, a in self.history[-HISTORY_TURNS:]:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": f"Reference notes:\n{notes}\n\nVisitor: {text}\n\n"
                                                    f"(Reply in {language(text)}.)"})
        buf, full, header = "", "", None
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
                parts = SENTENCE_END.split(buf)
                for sentence in parts[:-1]:
                    if sentence.strip():
                        yield sentence.strip()
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
        if buf.strip():
            yield buf.strip()
        self.history.append((text, full.strip()))

    def respond_from(self, question, facts):
        """Spoken answer built from looked-up facts (weather, web results); yields sentences."""
        messages = [{"role": "system", "content": SYSTEM + f"\nNow it is {tools.now_text()}."}]
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
        """A short natural goodbye that fits the conversation (what the visitor just said, or their silence)."""
        said = f'The visitor just said: "{text}".' if text else "The visitor has stopped talking."
        messages = [{"role": "system", "content": SYSTEM + f"\nNow it is {tools.now_text()}."}]
        for q, a in self.history[-HISTORY_TURNS:]:
            messages += [{"role": "user", "content": q}, {"role": "assistant", "content": a}]
        messages.append({"role": "user", "content": f"{said} The conversation is over. Say one short, warm, natural "
                                                    f"goodbye that fits this conversation (thank them back if they thanked "
                                                    f"you), in {'Korean' if lang == 'ko' else 'English'}. Only the words."})
        try:
            return _chat(messages).strip().strip('"')
        except Exception:
            return "See you next time!" if lang == "en" else "다음에 또 봐요!"

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
        elif action not in ("weather", "search"):
            target = target.split()[0] if target.split() else ""
        if action not in ACTION_NAMES:
            action = "none"
        if action == "go_to":
            target = next((mk for mk in markers if mk.lower() == target.lower()), None)
            action = "go_to" if target else "none"
        if action == "look" and target not in LOOK_TARGETS:
            action = "none"
        if action == "arm" and target not in ("reach", "fold"):
            action = "none"
        if action not in ("go_to", "look", "weather", "search", "move", "turn", "arm"):
            target = ""
        if action == "search" and not target:
            target = text
        if re.search(r"\b(bye|goodbye|see you)\b|안녕히|잘 ?가|다음에 봐", text, re.I):
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
        import agv
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
