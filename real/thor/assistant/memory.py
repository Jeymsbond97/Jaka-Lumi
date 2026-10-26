"""What Lumi remembers for 48 hours: what it saw, what was talked about, and its own body state now.

- Self state: one short line of facts about the body (arm pose, gripper, head, lift, waist, place, battery), read in
  the background every STATE_S (watch()), so a turn only reads a string: "where is your hand?" from facts.
- Seen things: every seeing answer / camera summary (object, colour, place, time) is kept KEEP_S (note_seen()).
  "Did you see an apple today?" -> "Yes, I saw a red apple at about 3:20 pm, near p3." / "I haven't seen one today."
- Talks: each finished talk is summed up by the LLM after it ends, in the background (title, summary, key facts,
  person), kept KEEP_S, and found again by meaning (knowledge.embed): "do you remember we talked about birds?" ->
  "Do you mean our talk about birds yesterday at about 4 pm?" -> yes / the next closest / "I can't remember that."
  "Forget this" / "잊어 줘" deletes the person's talks. No audio is kept, only text.

Data in data/memory/ (git-ignored: visitors' words). Nothing is saved unless start() was called (lumi.py does), so
the checks and tests never write here; tests point DIR at a temp folder.

    python assistant/memory.py                     # what is remembered now
    python assistant/memory.py "did you see a cup today?"
"""
import json
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "memory"
KEEP_S = 48 * 3600              # s everything is kept
STATE_S = 3.0                   # s between reads of the body state (the dashboard polls the same, read-only)
POSE_DEG = 3.0                  # deg; the arm is "at" a taught pose when every joint is this close
PLACE_M = 1.5                   # m; within this of a marker Lumi is "at" it
SEEN_SAME_S = 600               # s; the same thing at the same place again within this only updates the time
SEEN_SCORE = 0.3                # detections weaker than this are not kept (seeing.DESCRIBE_SCORE)
MIN_TURNS = 2                   # a talk of fewer turns is not saved
RECALL_MIN = 0.62               # cosine of the question's topic words to a talk (English or Korean title + summary)
                                # when none of its words was said; unrelated short topics score 0.3-0.5, meant 0.5-0.8
RECALL_PART = 0.50              # the cosine needed when only some of the topic words are the talk's own
RECENT_TURNS = 3                # a recalled talk is "it" / "what you said" for this many turns after
RECALL_OFFER = 3                # at most this many talks offered one after another
IDLE_WAIT_S = 900               # s a summary waits for Lumi to be idle (no talk) before it is made anyway
EARLIER_N = 5                   # visitor lines with facts kept from turns that left the LLM's window
EARLIER_CHARS = 140

on = False                      # start() sets it: only the live assistant saves
clock = time.time               # the time of memories (the checks set a dialogue's clock)
_state = {"line": "", "body": "", "at": 0.0}
_talk = {"name": None, "track": None, "skip": False}   # the talk now: who with, "forget this" said
_recall = {"offered": [], "left": [], "at": 0.0, "talk": None, "listed": []}   # talks offered / told / listed
_lock = threading.Lock()


# ---------- files ----------
def _load(name):
    try:
        items = json.loads((DIR / f"{name}.json").read_text())
    except (FileNotFoundError, ValueError):
        return []
    return [x for x in items if clock() - x.get("t", 0) < KEEP_S]


def _save(name, items):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = DIR / f"{name}.tmp"
    tmp.write_text(json.dumps([x for x in items if clock() - x.get("t", 0) < KEEP_S], ensure_ascii=False))
    tmp.replace(DIR / f"{name}.json")


# ---------- time words ----------
def _clock(t, lang):
    """"3:20 pm" / "오후 3시 20분", rounded to 10 minutes (it is "about")."""
    lt = time.localtime(round(t / 600) * 600)
    h, m = lt.tm_hour, lt.tm_min
    if lang == "ko":
        return f"{'오전' if h < 12 else '오후'} {h % 12 or 12}시" + (f" {m}분" if m else "")
    return f"{h % 12 or 12}{f':{m:02d}' if m else ''} {'am' if h < 12 else 'pm'}"


def _day(t, now=None):
    """0 today, 1 yesterday, 2 the day before."""
    now = clock() if now is None else now
    a, b = time.localtime(t), time.localtime(now)
    return int((time.mktime((b.tm_year, b.tm_mon, b.tm_mday, 0, 0, 0, 0, 0, -1)) -
                time.mktime((a.tm_year, a.tm_mon, a.tm_mday, 0, 0, 0, 0, 0, -1)) + 43200) // 86400)


def when(t, lang="en", now=None):
    """"today at about 3:20 pm" / "어제 오후 4시쯤"."""
    d = _day(t, now)
    if lang == "ko":
        return f"{('오늘', '어제', '그저께')[min(d, 2)]} {_clock(t, 'ko')}쯤"
    return f"{('today', 'yesterday', 'the day before yesterday')[min(d, 2)]} at about {_clock(t, 'en')}"


TODAY = re.compile(r"\btoday(?![a-z])|\bthis (?:morning|afternoon|evening)(?![a-z])|\btonight(?![a-z])|오늘|아침에|오전에|오후에|아까|방금", re.I)
YESTERDAY = re.compile(r"\byesterday(?![a-z])|\blast night(?![a-z])|어제|어젯밤", re.I)
TOO_OLD = re.compile(r"\b(?:last|past|previous) (?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?![a-z])|"
                     r"\b(?:a|one|two|three|several|few|\d+) (?:weeks?|months?|years?) ago\b|\b(?:three|four|five|\d+|few|several) days ago\b|"
                     r"\blong (?:time )?ago\b|\b(?:last|past|previous) weekend\b|\b(?:a|one|last) week (?:ago|back)\b|"
                     r"지난 ?(?:주|달|해|번 ?주)|저번 ?(?:주|달)|며칠 ?전|(?:사흘|나흘|닷새|엿새|열흘|보름) ?(?:전|前)|"
                     r"(?:[3-9]|세|네|다섯|여러) ?일 ?전|(?:[2-9]|두|세|네|다섯|여러) ?(?:주|달|개월|년) ?전|일주일 ?전|한 ?달 ?전|작년|옛날", re.I)
DAY_BEFORE = re.compile(r"\bday before yesterday(?![a-z])|\btwo days ago(?![a-z])|그저께|그제(?![가-힣])|이틀 ?전", re.I)
ONLY_TWO_DAYS = {"en": "I only remember the last two days.", "ko": "저는 최근 이틀 동안의 일만 기억해요."}


def _asked_days(text):
    """{0}, {1} or None (any day within KEEP_S); "too old" for a day past it."""
    if TOO_OLD.search(text):
        return "too old"
    if DAY_BEFORE.search(text):
        return {2}
    if YESTERDAY.search(text):
        return {1}
    if TODAY.search(text):
        return {0}
    return None


# ---------- self state ----------
def state_line(st):
    """The body facts for the LLM from a state dict (read_state); "" when nothing is known. Two parts: `arm` (slow to
    change: goes with what Lumi is doing, in the system prompt) and `body` (head, lift, waist, place, battery: in the
    turn's own message, so a head turn does not cost the cached prompt)."""
    arm = []
    if st.get("arm"):
        arm.append({"off": "Your arm is switched off.", "between": "Your arm is between taught poses."}.get(
            st["arm"], f"Your arm is in its {st['arm']} pose" + (" (held out to the visitor)." if st["arm"] == "give" else ".")))
    if st.get("holding"):
        arm.append(f"Your gripper is closed, holding {st['holding']}.")
    elif st.get("gripper"):
        arm.append(f"Your gripper (hand) is {st['gripper']} and empty.")
    body = []
    if st.get("head"):
        yaw, pitch = st["head"]
        side = "ahead" if abs(yaw) < 5 else f"{abs(yaw):.0f}° to your {'left' if yaw > 0 else 'right'}"
        tilt = "level" if abs(pitch) < 3 else f"{abs(pitch):.0f}° {'down' if pitch < 0 else 'up'}"
        body.append(f"head turned {side}, tilted {tilt}" + (", holding a look you were told" if st.get("look_held") else ""))
    if st.get("lift") is not None:
        body.append(f"lift {st['lift']:.0f} mm")
    if st.get("waist") is not None:
        body.append(f"waist {st['waist']:.0f}°")
    if st.get("place"):
        body.append(f"at {st['place']}")
    if st.get("battery") is not None:
        body.append(f"battery {st['battery']:.0f} %" + (", charging" if st.get("charging") else ""))
    return {"arm": " ".join(arm), "body": ("Your body now: " + ", ".join(body) + ".") if body else ""}


def read_state(arm_ok=True, look_held=False):
    """The body state from the robot (read-only calls). arm_ok False while the arm moves: its joints are not asked
    then (the controller mixes up replies to commands sent at once)."""
    from robot import agv, head
    st = {"look_held": look_held}
    try:
        lift, waist, yaw, pitch = head.status()
        st.update(lift=lift, waist=waist, head=(yaw, pitch))
    except Exception:
        pass
    try:
        b = agv.status()
        st.update(battery=b.get("power_percent"), charging=bool(b.get("charge_state")))
        st["place"] = _place((b.get("current_pose") or {}))
    except Exception:
        pass
    try:
        from tasks import fetch
        f = fetch.state()
        if f.get("holding"):
            st["holding"] = fetch.held_name()
    except Exception:
        pass
    if arm_ok:
        try:
            from robot import arm, gripper, motion
            d = arm.cmd("get_data")
            j = d.get("joint_actual_position")
            if j and not any(j):
                st["arm"] = "off"
            elif j:
                near = [n for n, p in motion.poses().items() if not n.startswith("wave")
                        and max(abs(a - b) for a, b in zip(motion.nearest(p, j), j)) <= POSE_DEG]
                st["arm"] = near[0] if near else "between"
            ai = (d.get("tio_ain") or [None])[0]
            if ai is not None:
                st["gripper"] = "closed" if ai > gripper.CLOSED_AI else "open"
        except Exception:
            pass
    else:
        st.update(arm=_state.get("arm"), gripper=_state.get("gripper"))
    return st


_markers = {"at": 0.0, "xy": {}}


def _place(pose):
    """The marker Lumi stands within PLACE_M of, else ""."""
    if "x" not in pose:
        return ""
    if time.time() - _markers["at"] > 60:
        from robot import agv
        res = (agv.request("/api/markers/query_list").get("results") or {})
        dock = agv.dock_marker()
        _markers["xy"] = {("home" if n == dock else n): (m["pose"]["position"]["x"], m["pose"]["position"]["y"])
                          for n, m in res.items() if (m.get("pose") or {}).get("position")}
        _markers["at"] = time.time()
    d, name = min(((((x - pose["x"]) ** 2 + (y - pose["y"]) ** 2) ** 0.5, n) for n, (x, y) in _markers["xy"].items()),
                  default=(99, ""))
    return name if d <= PLACE_M else ""


def watch(arm_ok=lambda: True, look_held=lambda: False):
    """Read the body state every STATE_S in the background (lumi.py starts it)."""
    def run():
        while True:
            try:
                st = read_state(arm_ok(), look_held())
                lines = state_line(st)
                _state.update(st, line=lines["arm"], body=lines["body"], at=time.time())
            except Exception as e:
                print(f"memory: state not read ({e})", flush=True)
            time.sleep(STATE_S)
    threading.Thread(target=run, daemon=True, name="memory-state").start()


def arm_line():
    """" Your arm is in its look pose. Your gripper (hand) is open and empty." (for lumi's `now`), or ""."""
    return " " + _state["line"] if _state["line"] and time.time() - _state["at"] < 10 * STATE_S else ""


HAND_Q = re.compile(   # questions about the hand / arm now (not orders: "open your hand" is a command)
    r"\b(?:where|how) (?:is|'s) your (?:hand|arm|gripper)\b|\bwhere(?:'s| is) your (?:hand|arm|gripper)\b|"
    r"\bis your (?:hand|gripper|arm) (?:open|opened|closed|shut|empty|free|full|out|up|down|folded|stretched)\b|"
    r"\b(?:your )?(?:hand|gripper) (?:is )?(?:open|opened|close|closed)(?: or (?:open|opened|close|closed))?\s*\?|"
    r"\b(?:are|do) you (?:holding|have|carrying) (?:anything|something)(?: in your (?:hand|gripper))?\b|"
    r"\bwhat(?:'s| is) (?:in|on) your (?:hand|gripper)\b|\bstate of your (?:hand|arm|gripper)\b|"
    r"(?:손|팔|그리퍼|arm|hand|gripper)(?:은|는|이|가)?\s*(?:지금\s*)?(?:어디|어떻게|(?:무슨|어떤)\s*상태|상태)|"
    r"(?:손|그리퍼)(?:은|는|이|가)?\s*(?:지금\s*)?(?:펴져|펼쳐져|벌어져|열려|닫혀|오므려져|쥐어져|비어|비었|펴졌|열렸|닫혔|오므려졌|쥐어졌)\s*(?:있)?(?:어|니|나|나요|어요|습니까|있어|있니|있나요|있어요|냐|노|나요)?\s*\?|"
    r"(?:팔|arm)(?:은|는|이|가)?\s*(?:지금\s*)?(?:어떤|무슨)\s*자세|"
    r"(?:손|hand|gripper|그리퍼)에\s*(?:뭐|뭔가|무엇|뭘|아무것도|든 거|있는 거)(?:을|를|이|가)?\s*(?:있|들|쥐|잡|가지)", re.I)
ARM_WHERE = {"look": ("My arm is in its resting pose, folded in front of me.", "팔은 앞에 접어 둔 기본 자세예요."),
             "ready": ("My arm is in its ready pose.", "팔은 준비 자세예요."),
             "carry": ("My arm is in its carry pose, close to my body.", "팔은 물건을 나르는 자세로 몸 가까이 있어요."),
             "give": ("My hand is held out in front of me.", "손을 앞으로 내밀고 있어요."),
             "between": ("My arm is between my usual poses.", "팔은 평소 자세들 사이에 있어요."),
             "off": ("My arm is switched off right now.", "지금은 팔 전원이 꺼져 있어요."),
             **{w: ("My arm is raised, as for a wave.", "팔을 흔들려고 들어 올린 자세예요.") for w in ("wave_start", "wave_out", "wave")}}


def _j(word, after_consonant, after_vowel):
    from assistant import seeing
    return seeing._j(word, after_consonant, after_vowel)


def _held_ko(name):
    """"the red apple" -> "빨간색 사과" (seeing's Korean words), "something" -> "물건"."""
    from assistant import seeing
    words = name.removeprefix("the ").split()
    colour = next((seeing.COLOUR_KO[w] for w in words[:1] if w in seeing.COLOUR_KO), "")
    thing = " ".join(words[1:] if colour else words)
    return (colour + " " if colour else "") + (seeing.KO.get(thing) or ("물건" if thing in ("something", "") else thing))


PLACE_Q = re.compile(r"^\W*(?:(?:lumi|hey|so|and|okay)\W+)*(?:where are you(?: now| right now| standing)?|where you are|where are you at)\W*$|"
                     r"\bwhich (?:marker|point|place) are you (?:at|near)\b|(?:너|루미|루미야)?\s*지금\s*어디(?:야|에 있어|에 있어요|예요|에요|입니까|에 계세요)\W*$|"
                     r"^\W*(?:너|루미야?)?\s*어디(?:에)? 있(?:어|어요|니|습니까)\W*$", re.I)
LIFT_Q = re.compile(r"\bhow (?:high|tall) (?:is your (?:lift|body|torso)|are you raised|is your body raised)\b|\bis your (?:lift|body) (?:up|down|raised)\b|"
                    r"\b(?:lift|body) (?:height|position)\b|(?:몸|리프트|허리)(?:이|가|은|는)?\s*(?:지금\s*)?(?:얼마나|몇)\s*(?:올라|높|내려)|"
                    r"리프트\s*(?:높이|위치)", re.I)


def self_answer(text, lang="en"):
    """"Where is your hand?", "is your hand open?", "손 펴져 있어?", "where are you?", "how high is your lift?" from the
    body state read lately, else None."""
    if time.time() - _state["at"] > 10 * STATE_S:
        return None
    ko = lang == "ko"
    if PLACE_Q.search(text):
        return None if not _state.get("place") else \
            ("지금 홈에 있어요." if _state["place"] == "home" else f"지금 {_state['place']} 근처에 있어요.") if ko \
            else f"I'm at {_state['place']} right now."
    if LIFT_Q.search(text):
        mm = _state.get("lift")
        if mm is None:
            return None
        if mm < 5:
            return "리프트는 맨 아래에 있어요. 몸을 올리지 않은 상태예요." if ko else "My lift is all the way down; my body isn't raised."
        return f"리프트는 {mm:.0f}밀리미터 올라가 있어요." if ko else f"My lift is raised {mm:.0f} millimetres."
    if not HAND_Q.search(text):
        return None
    parts = [ARM_WHERE[_state["arm"]][ko]] if _state.get("arm") in ARM_WHERE else []
    if _state.get("holding"):
        parts.append(f"I'm holding {_state['holding']}." if not ko else f"손에 {_j(_held_ko(_state['holding']), '을', '를')} 들고 있어요.")
    elif _state.get("gripper"):
        parts.append({"open": ("My hand is open and empty.", "손은 펴져 있고, 아무것도 안 들고 있어요."),
                      "closed": ("My hand is closed, with nothing in it.", "손은 닫혀 있고, 아무것도 안 들고 있어요.")}[_state["gripper"]][ko])
    return " ".join(parts) or None


# ---------- seen things ----------
def saw(things, place="", now=None):
    """Keep things seen: [{"name", "colour"}] (scene.things), at place (a marker name or "")."""
    if not on and now is None:
        return
    now = clock() if now is None else now
    with _lock:
        seen = _load("seen")
        for th in things:
            same = next((s for s in reversed(seen) if s["name"] == th["name"] and s.get("colour") == th.get("colour")
                         and s.get("place") == place and now - s["t"] < SEEN_SAME_S), None)
            if same:
                same["t"] = now
            else:
                seen.append({"t": now, "name": th["name"], "colour": th.get("colour"), "place": place})
        _save("seen", seen)


def note_seen():
    """In the background: what the cameras see now (after a seeing answer or a camera summary) is kept."""
    if not on:
        return

    def run():
        try:
            from vision import scene
            frames = scene.snapshot()
            things = [t for t in scene.things(frames) if (t["score"] or 0) >= SEEN_SCORE]
            n = len(scene.people(frames))
            saw(things + ([{"name": "person", "colour": None}] if n else []), _state.get("place") or "")
        except Exception as e:
            print(f"memory: seen not kept ({e})", flush=True)
    threading.Thread(target=run, daemon=True).start()


SEEN_Q = re.compile(
    r"\b(?:did|have|had) (?:you|u) (?:\w+ )?(?:see|seen|spot|spotted|notice|noticed|come across|run into)\b|"
    r"\b(?:you|u) (?:saw|spotted|noticed)\b|\bhave you got (?:eyes on|a look at)\b|\bwas there (?:a|an|any)\b|"
    r"^\W*(?:\w+\W+)?(?:you|u) see\b.*\b(?:today|earlier|yesterday|this morning|before)(?![a-z])|see\s*했|"
    r"(?:봤|봤어|봤니|봤나|봤냐|봤어요|봤나요|보셨|보았|본 ?적|봤던|봤는지|봤지|봤죠|본 거|목격)", re.I)
NOW_Q = re.compile(r"\b(?:do|can) you see\b(?!.*\b(?:today|earlier|yesterday|this morning)\b)|\bsee (?:it|one) now\b|보여|보이니|보이나|보입니까|보이세요|보이는지|"
                   r"\bever\b|본 ?적|[가-힣][어아여] ?봤|해 ?봤", re.I)   # "have you ever seen snow?", "먹어 봤어?": the LLM


KO_MORE = {"강아지": "dog", "멍멍이": "dog", "냥이": "cat", "핸드폰": "cell phone", "스마트폰": "cell phone", "텀블러": "cup",
           "머그컵": "cup", "종이컵": "cup", "물컵": "cup", "페트병": "bottle", "생수": "bottle", "곰인형": "teddy bear"}
KO_ONE = {"컵", "병", "잔", "책", "새", "공"}       # one-syllable names taken alone ("개" in "몇 개" is no dog)


def _object(text):
    """The COCO name of the thing asked about, else None."""
    from assistant import seeing
    from vision import objects
    words = {**{c: c for c in objects.COCO}, **seeing.SYNONYMS, **seeing.KO_WORDS, **KO_MORE}
    t = text.lower()
    for w in sorted(words, key=len, reverse=True):
        if w.isascii():
            hit = re.search(rf"(?<![a-z]){re.escape(w)}(?:s|es)?(?![a-z])", t)
        else:                                          # a Korean word alone or with a particle; one syllable only
            hit = (len(w) > 1 or w in KO_ONE) and re.search(rf"(?<![가-힣]){w}(?![가-힣])|(?<![가-힣]){w}[을를이가은는도만](?![가-힣])", t)
        if hit:
            return words[w]
    return None


def _colour(text, name):
    """The colour said with the thing ("a green apple", "초록 사과"), else None ("orange" the fruit is no colour)."""
    from assistant import seeing
    t = text.lower()
    for w in sorted(seeing.COLOURS, key=len, reverse=True):
        if w == name or w == "하늘" or not re.search(rf"(?<![a-z가-힣]){w}(?![a-z])", t):
            continue
        return seeing.COLOURS[w]
    return None


def _thing_words(e, lang):
    from assistant import seeing
    if lang == "ko":
        return (seeing.COLOUR_KO.get(e.get("colour"), "") + " " if e.get("colour") else "") + seeing.KO.get(e["name"], e["name"])
    return seeing._a(e["name"], e.get("colour"))


def seen_answer(text, lang="en", now=None, days="ask"):
    """The answer to "did you see an apple today?" from what was kept, else None (not such a question). days: a
    follow-up ("and a green apple?") asks the days of the question before."""
    if days == "ask":
        if not SEEN_Q.search(text) or NOW_Q.search(text) and _asked_days(text) is None:   # "오늘 사과 본 적 있어요?"
            return None
        days = _asked_days(text)
    if days == "too old":
        return ONLY_TWO_DAYS[lang]
    name = _object(text)
    if name is None:
        return None                                    # a thing the cameras can't name: the LLM, with the seen list
    now = clock() if now is None else now
    _recall["seen"] = (now, days)
    from assistant import seeing
    seen = [e for e in _load("seen") if e["name"] == name]
    hits = [e for e in seen if days is None or _day(e["t"], now) in days]
    word_ko = seeing.KO.get(name, name)
    span_en = {None: "in the last two days", 0: "today", 1: "yesterday", 2: "the day before yesterday"}[next(iter(days)) if days else None]
    span_ko = {None: "최근 이틀 동안", 0: "오늘은", 1: "어제는", 2: "그저께는"}[next(iter(days)) if days else None]
    if not hits:
        other = seen[-1] if seen else None              # "not today, but yesterday at about 4 pm"
        if lang == "ko":
            return f"{span_ko} {seeing._j(word_ko, '을', '를')} 못 봤어요." + \
                (f" {when(other['t'], 'ko', now)}에 본 적은 있어요." if other else "")
        return f"I haven't seen {'anyone' if name == 'person' else 'one'} {span_en}." + \
            (f" I saw one {when(other['t'], 'en', now)}." if other else "")
    colour = _colour(text, name)
    if colour and not any(e.get("colour") == colour for e in hits):   # "a green apple?" when only a red one was seen
        e = hits[-1]
        if lang == "ko":
            return f"{span_ko} {seeing._j(seeing.COLOUR_KO.get(colour, colour) + ' ' + word_ko, '은', '는')} 못 봤어요. " \
                   f"{when(e['t'], 'ko', now)}{_where(e, 'ko')} {seeing._j(_thing_words(e, 'ko'), '은', '는')} 봤어요."
        return f"I haven't seen {seeing._a(name, colour)} {span_en}. I saw {_thing_words(e, 'en')} {when(e['t'], 'en', now)}{_where(e, 'en')}."
    e = next((e for e in reversed(hits) if e.get("colour") == colour), hits[-1])
    if lang == "ko":
        return f"네, {when(e['t'], 'ko', now)}{_where(e, 'ko')} {seeing._j(_thing_words(e, 'ko'), '을', '를')} 봤어요."
    return f"Yes, I saw {_thing_words(e, 'en')} {when(e['t'], 'en', now)}{_where(e, 'en')}."


def _where(e, lang):
    """", near p3" / " p3 근처에서": where it was seen (a marker; a where text in the checks), or ""."""
    w = e.get("where") or ""
    if lang == "ko":
        return f" {w}에서" if re.search(r"[가-힣]", w) else f" {e['place']} 근처에서" if e.get("place") else ""
    return f", {w}" if w else f", near {e['place']}" if e.get("place") else ""


def seen_list(now=None, n=8):
    """"Things you saw lately: a red cup today at about 3:20 pm near p3; ..." for the LLM, or ""."""
    seen = _load("seen")[-n:]
    if not seen:
        return ""
    return "Things you saw lately (nothing else): " + "; ".join(
        f"{_thing_words(e, 'en')} {when(e['t'], 'en', now)}{_where(e, 'en')}" for e in reversed(seen)) + "."


# ---------- talks ----------
def heard(name=None, track=None):
    """Who this talk is with: a name said ("I'm James", sticky for the talk), else the re-id person / track."""
    if name:
        _talk["name"] = name
    if track is not None:
        _talk["track"] = f"p{id(track.person)}" if getattr(track, "person", None) is not None else f"t{track.id}"


def _person():
    return _talk["track"] or (f"name:{_talk['name']}" if _talk["name"] else None)


SUMMARY_PROMPT = """Here is a conversation between a visitor and Lumi, a robot. Sum it up for Lumi's memory as JSON:
{"title": "<2-4 words naming the topic, e.g. Battery life, Birds, Weather in Busan>",
 "summary": "<2-3 short sentences: what was asked and answered, in English>",
 "facts": ["<each name, place, number or plan the visitor gave, in English>"],
 "commands": ["<each command for Lumi agreed in the talk, e.g. go to p3 and wave>"],
 "title_ko": "<the title in Korean>", "summary_ko": "<the summary in polite Korean (-요)>",
 "facts_ko": ["<each fact in polite Korean (-요)>"]}
Only what is in the conversation; nothing else."""
SUMMARY_SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}, "summary": {"type": "string"},
                                                   "facts": {"type": "array", "items": {"type": "string"}},
                                                   "commands": {"type": "array", "items": {"type": "string"}},
                                                   "title_ko": {"type": "string"}, "summary_ko": {"type": "string"},
                                                   "facts_ko": {"type": "array", "items": {"type": "string"}}},
                  "required": ["title", "summary", "facts", "commands", "title_ko", "summary_ko", "facts_ko"]}


def _transcript(history):
    lines = []
    for q, a in history:
        a = "\n".join(ln for ln in a.splitlines() if not re.match(r"\s*\**ACTION", ln)).strip() or \
            re.sub(r"\s*\**ACTION\**\s*:\s*", "(did: ", a.strip()) + ")"
        lines += [f"Visitor: {q}", f"Lumi: {a}"]
    return "\n".join(lines)


def summarise(history, chat=None):
    """{"title", "summary", "facts"} by the LLM (chat(messages, fmt) -> JSON text; brain._chat when None)."""
    if chat is None:
        from assistant import brain
        chat = brain._chat
    out = json.loads(chat([{"role": "system", "content": SUMMARY_PROMPT},
                           {"role": "user", "content": _transcript(history)}], SUMMARY_SCHEMA))
    return {"title": str(out.get("title", "")).strip()[:60], "summary": str(out.get("summary", "")).strip()[:600],
            "facts": [str(f)[:160] for f in out.get("facts", [])][:10],
            "commands": [str(f)[:160] for f in out.get("commands", [])][:5],
            "title_ko": str(out.get("title_ko", "")).strip()[:60], "summary_ko": str(out.get("summary_ko", "")).strip()[:600],
            "facts_ko": [str(f)[:160] for f in out.get("facts_ko", [])][:10]}


def keep_talk(history, person=None, t=None, chat=None, embed=None, name=None):
    """Sum up a finished talk and save it (blocking; talk_over runs it in the background)."""
    if embed is None:
        from assistant import knowledge
        embed = knowledge.embed
    s = summarise(history, chat)
    if not s["title"] and not s["summary"]:
        return None
    en, ko = embed([f"{s['title']}. {s['summary']}", f"{s['title_ko']}. {s['summary_ko']}"])
    s.update(t=clock() if t is None else t, person=person, name=name, vec=[round(float(x), 4) for x in en],
             vec_ko=[round(float(x), 4) for x in ko])     # a Korean question is matched to the Korean words too
    with _lock:
        talks = _load("talks")
        talks.append(s)
        _save("talks", talks)
    return s


_hooks = {"idle": lambda: True, "after": None}


def talk_over(history):
    """A talk ended (Brain.reset): keep it unless "forget this" was said in it; summed up once Lumi is idle (the LLM
    then is free), after(): what to do next (lumi warms the LLM again)."""
    skip, person, name = _talk["skip"], _person(), _talk["name"]
    _talk.update(name=None, track=None, skip=False)
    _recall.update(offered=[], left=[], talk=None, listed=[])
    if not on or skip or len(history) < MIN_TURNS:
        return
    history, ended = list(history), clock()
    idle, after = _hooks["idle"], _hooks["after"]

    def run():
        end = time.time() + IDLE_WAIT_S
        while not idle() and time.time() < end:
            time.sleep(2.0)
        try:
            s = keep_talk(history, person, ended, name=name)
            print(f"memory: talk kept: {s and s['title']}", flush=True)
        except Exception as e:
            print(f"memory: talk not kept ({e})", flush=True)
        if after:
            after()
    threading.Thread(target=run, daemon=True, name="memory-talk").start()


RECALL_Q = re.compile(   # a question about an earlier talk; "I remember when ..." / "last time I was here" are not
    r"\b(?:do|did|can|could|don'?t|didn'?t|you) (?:you )?(?:still |even )?(?:remember|recall)\b|^\W*(?:\w+\W+)?(?:remember|recall)\b|"
    r"\bwe (?:talked|spoke|chatted|discussed|were talking)\b|\bour (?:talk|chat|conversation)\b|"
    r"\b(?:what|which) did (?:we|i) (?:talk|speak|chat|say|tell|ask)\b|\bwhat did you (?:tell|say to) me about\b|"
    r"\bwhat (?:did )?we (?:talk|talked|discuss|discussed|chat|chatted)\b|\bdid (?:we|i) (?:talk|speak|chat|tell you|ask you|mention)\b|"
    r"\bearlier (?:i|we) (?:said|told|asked|talked)\b|\bremember(?: (?:that|this|it))?\W*$|\bring a bell\b|\bremind me\b|\bwe had (?:a|our|that) (?:talk|chat|conversation)\b|"
    r"\bdid we have (?:a|any) (?:talk|chat|conversation)\b|\bdid i (?:tell|give) you\b|\bwhat (?:we|you) (?:said|told me|talked about)\b|"
    r"(?:말해|알려|얘기해|이야기해) ?(?:줬|주었|드렸)(?:던|었|지|잖|죠)|(?:했던|나눴던|한) (?:얘기|이야기|대화)|"
    r"(?:얘기|이야기|대화)\s*(?:\S+\s+)?(?:했잖|했었|했던|나눴)|무슨\s*(?:topic|주제)(?:였|이었)|"
    r"기억\s*(?:이\s*)?(?:나|해|하|날)|생각\s*(?:이\s*)?나|"
    r"(?:얘기|이야기|대화|말)(?:를|을)?\s*(?:했던|했었|나눴|나누었|나누셨|하셨|한 거|했지|했잖|했는|했죠|했어|했노|했나|했니|했냐|했더라|했습니까|했을까)|"
    r"\b(?:remember|recall)\s*(?:해|하|나|돼|되)|\b(?:talk|chat|conversation)\s*(?:했던|했었|한 거|나눴)",   # Konglish: "remember 해?"
    re.I)
NOT_RECALL = re.compile(r"\bremember (?:to|that you|my|me)\b(?! (?:asking|telling|saying|talking|ask|tell|say|talk))|\bremember me\?$|\b(?:i|we) (?:don'?t |do not )?remember\b|"
                        r"\b(?:can|could|will|would) you remember\b(?! (?:what|when|our|that we|we))|기억력|기억해\s*(?:줘|주세요|둬|놔)", re.I)
GENERIC = re.compile(r"\b(?:what|which) did (?:we|i) (?:talk|speak|chat|say)(?: about)?\W*(?:today|yesterday|earlier|last time|before)?\W*$|"
                     r"무슨 ?(?:얘기|이야기|대화|말)|뭐(?:라고)? ?(?:얘기|이야기|말)", re.I)
FORGET = re.compile(   # an order to forget: "did you forget me?", "제 이름 잊어버렸어요?", "I forget what we said" are not
    r"(?<!\bdid you )(?<!\bdo you )(?<!\bhave you )(?<!\bwill you )(?<!\bi )(?<!\bwe )(?<!n't )(?<!\bnot )(?<!\bnever )\b"
    r"(?:forget (?:this|me|everything|all (?:of )?(?:this|that|it)|what (?:i|we) (?:said|told|talked|discussed|chatted)|"
    r"(?:our|this|that|the|my) (?:talk|chat|conversation|data|info)|about (?:me|this|our talk)|my name|i was here)\b|"
    r"(?:delete|erase|clear|remove|wipe) (?:out )?(?:this|our|my|the|that) (?:conversation|talk|chat|data|memory|memories|record|records|history)\b|"
    r"(?:wipe|erase|delete|clear|remove) (?:out )?(?:what (?:we|i) (?:said|talked about|told you|discussed)|it all|everything|"
    r"all (?:of )?(?:it|that|this)|my (?:data|info|information|details))\b)|"
    r"\bdon'?t (?:remember|keep|save|store) (?:this|me|that|our|anything|what|any(?:thing)? of (?:this|it|that))\b|"
    r"\b(?:you )?(?:didn'?t|did not|wouldn'?t) (?:keep|save|store|record|remember) (?:that|this|it|any of (?:this|that|it)|our)\b|"
    r"(?:얘기|이야기|말|대화|기록|내용|정보|데이터|메모리|history|record|data)(?:을|를|은|는|도)?\s*(?:다\s*|전부\s*|모두\s*|싹\s*|좀\s*)?"
    r"(?:지워|지우|지아|삭제|잊어|잊어버|없애|delete|erase|forget|remove|clear|wipe)|"
    r"잊어\s*(?:줘|주세요|주라|주십시오|주시겠|주시기|주실래|주시면|줄래|줄 수|버려|버리|삐|뿌|도\s*돼|도 됩|달라)|잊어버려(?:요)?(?![가-힣])|"
    r"잊으세요|잊으십시오|잊어라|잊어 ?도(?![가-힣])|기억(?:에서)?\s*(?:지워|삭제|없애)|기억하지\s*(?:마|말아|마세요|마십시오|말아 ?주)|"
    r"(?:대화|기록)\s*(?:지워|삭제)|^\W*(?:다\s*)?지워\s*(?:줘|주세요|주십시오|주실래요|줄래)\W*$|(?:delete|forget|erase|remove)\s*(?:해|하|시켜)\s*(?:줘|주|줄|라|요|봐)", re.I)
FORGOT = {"en": "Okay, I've forgotten our conversation.", "ko": "네, 우리 대화는 잊을게요."}
CANT_REMEMBER = {"en": "I can't remember that.", "ko": "그건 기억이 안 나요."}
OFFER_WAIT_S = 60               # s a "do you mean ...?" waits for yes / no


DETAIL = re.compile(r"\bremind me\b|\b(?:your|the) answer\b|\bwhat was your (?:point|answer)\b|\bwhat you (?:told|said)\b|\bmain point\b|\bthe point\b|\bconclusion\b|\bwhat was (?:it|that)(?: again)?\b|결론|요점|포인트|point|\bwhat (?:did|was it) you (?:say|tell|said|told)|\bwhat was (?:it|that|the \w+)\b|"
                    r"\btell me (?:more|again|what)\b|\bwhat did you (?:say|tell me)\b|\bwhat (?:you|we) said\b|\bthe details?\b|"
                    r"무슨 (?:얘기|이야기|말)(?:였|이었)|뭐라고 (?:했|하셨|말했)|다시 (?:말해|알려)|자세히|뭐였", re.I)


def forget(person=None):
    """Delete the talks of this person (the talk now is not kept either)."""
    _talk["skip"] = True
    _recall.update(offered=[], left=[], talk=None, listed=[])
    person = person or _person()
    if not person:
        return 0
    with _lock:
        talks = _load("talks")
        keep = [s for s in talks if s.get("person") != person and not (_talk["name"] and s.get("name") == _talk["name"])]
        _save("talks", keep)
    return len(talks) - len(keep)


def _offer(s, lang, first=True, now=None):
    if lang == "ko":
        return f"{'' if first else '아니면 '}{when(s['t'], 'ko', now)}에 {_title_ko(s)}에 대해 " \
               f"이야기한 거 말씀이세요?"
    return f"{'Do you mean' if first else 'Or was it'} our talk about {_lower(s['title'])} " \
           f"{when(s['t'], 'en', now)}?"


def _lower(title):
    return title[:1].lower() + title[1:] if title[1:2].islower() else title     # not "TV", "NASA"


def _title_ko(s):
    return s.get("title_ko") or f"'{s['title']}'"


def _told(s, lang, detail=False, turn=-99):
    """The answer once a talk is confirmed (or its details asked): its summary and facts; None in Korean when the
    talk has no Korean summary (the LLM then says it from the talk in its prompt)."""
    _recall.update(talk=s, offered=[], left=[], turn=turn)
    facts = " ".join(f if f.endswith(".") else f + "." for f in s.get("facts", [])[:3])
    if lang == "ko":                                   # a detail is the facts (the summary only names the topic)
        facts_ko = " ".join(f if f.endswith(".") else f + "." for f in s.get("facts_ko", [])[:3])
        if detail:
            return facts_ko or (None if s.get("facts") else s.get("summary_ko")) or None
        ko = s.get("summary_ko")
        return f"네, 기억나요. {ko}" + (f" {facts_ko}" if facts_ko and facts_ko not in ko else "") if ko else None
    if detail:
        return f"I told you that {facts[:1].lower() + facts[1:]}" if facts else f"We talked about this: {s['summary']}"
    return f"Yes, I remember. {s['summary']}" + (f" {facts}" if facts and facts not in s["summary"] else "")


_STOP_EN = set("""remember recall remind do does did you we i me my your our us lumi hey please talk talked talking spoke speak
spoken chat chatted chatting discuss discussed conversation conversations say said tell told mention mentioned about the a an
that this it its was were is are had have has yesterday today tonight earlier morning afternoon evening last time before ago
day days two right again what which so and oh going back to in on at of with still can could would will any something thing
things then there when where how much go ahead just okay ok well there's what's we've i've you've anything that's again,
tell, remember, now yes yeah no topic topics subject subjects um uh hmm oh wait right pls bro hey talk? chatted?
by way anyway also too stuff answer point main back asking asked ask didn't don't ring bell""".split())
_STOP_KO = re.compile(r"^(?:기억|얘기|이야기|대화|말씀|말했|말한|했|어제|오늘|아까|그저께|그제|이틀|우리|제가|내가|나랑|저랑|저와|나와|"
                      r"루미|그때|그거|그것|무슨|나눴|나누|혹시|있잖|맞|좀|다시|알려|아침|오전|오후|저녁|지난|전에|"
                      r"그래서|결론|요점|그러니까|어떤|무엇|어디|언제|이었|였|이에|예요|입니|이야|주제|remember|recall|talk|yesterday|today|"
                      r"(?:그리고|그럼|그러면|그런데|근데|잠깐|궁금한|궁금해|참|저기|음|어|아|자|얘|야|위해서|위해|대해|대해서|관해|관해서|대한|관한)$|"
                      # one-syllable stems only alone or with a verb ending ("한 거", "해 줘"; not "한글", "해변", "주말")
                      r"(?:말|한|하|거|것|요|주|줘|줄|알|있|없|해|할|뭔|뭐|저)(?:[요어아지죠고던는신셨세시자게니냐나까서면기여였잖든다며라래려줘봐야해했할줄][가-힣]?)?$|"
                      r"(?:가|이|은|는|을|를|도|에|의|로|으로|에서)$)")   # a particle left alone ("point가")
_KO_TAIL = re.compile(r"(?:에\s*대해서?|에\s*관해서?|이랑|랑|하고|얘기|이야기|은|는|을|를|도|에|의|요)+$")


FOCUS = re.compile(r"\babout\b(.+)|\b(?:remember|recall)\b(.+)|((?:[가-힣A-Za-z0-9']+\s+){0,2}[가-힣A-Za-z0-9']+)\s*"
                   r"(?:에\s*대해서?|에\s*관해서?|에\s*대한|얘기|이야기)", re.I)


def topic(text):
    """The words of a recall question that name its topic ("remember we talked about birds yesterday?" -> "birds");
    "" when it names none ("what did we talk about?"). The words after "about" / "remember" or before "얘기" first,
    so a filler ("Class, listen: ...", "Jason, look") is not taken for a topic."""
    m = FOCUS.search(text)
    part = next((g for g in m.groups() if g), text) if m else text
    if m and m.group(3):                               # "시청자분들 위해서 어제 한글 얘기": what follows the time word
        part = re.split(r"(?:어제|오늘|아까|그저께|그제|이틀 ?전|지난번|저번에|우리|오늘 ?아침)\s*", part)[-1] or part
    return (_words(part) if m else "") or _words(text)


def _words(text):
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z'.-]*|[가-힣]+|\d+", text):
        if re.match(r"[A-Za-z]", w):
            if w.lower().strip(".'") not in _STOP_EN and len(w) > 1:
                out.append(w.lower().strip(".'"))
        else:
            w = re.sub(r"^(?:우리|저랑|나랑|제가|내가)(?=[가-힣]{1,})", "", w)    # "우리달 얘기" (no space)
            if _STOP_KO.match(w):
                continue
            w = _KO_TAIL.sub("", w)
            if w and not _STOP_KO.match(w):
                out.append(w)
    return " ".join(out)


NAMES_KO = {"cutshion": "쿳션 컷션 커션", "jaka": "자카", "lumi": "루미", "hangul": "한글", "chuseok": "추석", "kimchi": "김치",
            "seoul": "서울", "busan": "부산", "jeju": "제주", "everest": "에베레스트"}   # names a title may keep in English


def _hits(words, s):
    """The share of the topic words found in a talk's own words (English and Korean title, summary, facts); a
    one-syllable Korean word only alone or with a particle ("달" is not in "달해요")."""
    text = " ".join([s["title"], s["summary"], s.get("title_ko", ""), s.get("summary_ko", "")] + s.get("facts", [])).lower()
    text += "".join(f" {ko}" for en, ko in NAMES_KO.items() if en in text)   # "쿳션 얘기" for the talk "Cutshion"
    n = 0
    for w in words:
        if w.isascii():
            n += w in text or len(w) > 3 and w.rstrip("s") in text
        elif len(w) > 1:
            n += w in text
        else:
            n += bool(re.search(rf"(?<![가-힣]){w}(?:들)?(?:[은는이가을를도의]|에서|에)?(?![가-힣])", text))
    return n / len(words) if words else 0.0


def _rank(about, talks, embed):
    """The talks that may be the one meant, best first. The words decide first (the embedding of one or two words
    is weak: unrelated short topics score 0.3-0.5); a talk none of whose words were said needs a close meaning."""
    import numpy as np
    q = embed([about])[0]
    words = [w for w in about.split() if len(w) > 2 or not w.isascii()]
    out = []
    for s in talks:
        cos = max(float(np.dot(q, s["vec"])), float(np.dot(q, s["vec_ko"])) if s.get("vec_ko") else 0.0)
        hit = max(_hits(words, s), _title_said(about, s))
        if hit >= 0.99 or hit and cos >= RECALL_PART or cos >= RECALL_MIN:
            out.append((hit, cos, s))
    return [s for _, _, s in sorted(out, key=lambda x: (-x[0], -x[1]))]


def _title_said(about, s):
    """1.0 when every word of the talk's title (English or Korean) was said: "부산 날씨랑 새 얘기" names both the talk
    "부산 날씨" and the talk "새"."""
    said = set(about.lower().split())
    for title in (s["title"], s.get("title_ko") or ""):
        ws = [w for w in _words(title).split() if len(w) > 2 or not w.isascii()]
        if ws and all(w in said or len(w) > 3 and w.rstrip("s") in {x.rstrip("s") for x in said} for w in ws):
            return 1.0
    return 0.0


PRONOUN = re.compile(r"\b(?:it|that|this|then|that time)\b|그거|그것|그때|그 ?얘기|그 ?이야기|거기", re.I)


def recall(text, lang="en", now=None, embed=None, history=()):
    """The answer to "do you remember we talked about birds?" and to the yes / no after it, else None. history: the
    talk now (a topic of this talk: "what were we saying about the moon?" is the LLM's, not a memory)."""
    from assistant import brain
    now = clock() if now is None else now
    past = list(history[:-1] if history and history[-1][0] == text else history)
    about = topic(text)
    other_q = HAND_Q.search(text) or SEEN_Q.search(text) or PLACE_Q.search(text) or LIFT_Q.search(text)
    if _recall["offered"] and now - _recall["at"] < OFFER_WAIT_S and not other_q:
        yes = brain.confirm_answer(text)
        if yes == "yes" or yes == "correction" and re.match(r"\W*(?:yes|yeah|yep|right|exactly|네|예|응|맞아|맞습니다|맞아요|그래|그렇|그거)", text, re.I):
            return _told(_recall["offered"][-1], lang, turn=len(past))
        if yes in ("no", "cancel") or yes == "correction" and re.match(r"\W*(?:no|nope|not that|아니|아뇨)\b", text, re.I):
            if yes == "cancel":
                _recall.update(offered=[], left=[])
                return None
            if _recall["left"]:
                s = _recall["left"].pop(0)
                _recall["offered"].append(s)
                _recall.update(at=now, talk=s, turn=len(past))
                return _offer(s, lang, first=False, now=now)
            _recall.update(offered=[], left=[], talk=None)
            return CANT_REMEMBER[lang]
    if DO_SAID.search(text) and not NOT_DO.search(text):
        out = do_said(text, lang, now)
        _recall["turn"] = len(past)
        return out
    recent = _recall.get("talk") and len(past) - _recall.get("turn", -99) <= RECENT_TURNS
    if recent and DETAIL.search(text) and (not about or _hits(about.split(), _recall["talk"]) >= 0.5):   # not "back to chess: what was that?"
        return _told(_recall["talk"], lang, detail=True, turn=len(past))   # "remind me what you said", "결론이 뭐였어요?"
    if NAME_Q.search(text):
        return name_answer(lang)
    if not (RECALL_Q.search(text) or SAID_THEN.search(text) and _asked_days(text) is not None) or NOT_RECALL.search(text):
        return None
    days = _asked_days(text)
    words = [w for w in about.split() if len(w) > 2 or len(w) > 1 and not w.isascii()]
    if words and days in (None, {0}) and any(w in f"{q} {a}".lower() for q, a in past if not RECALL_Q.search(q) for w in words):
        return None                                    # a topic of this talk ("아까 배터리에 대해 뭐라고 하셨죠?"): the LLM has it
    if days == "too old":
        return ONLY_TWO_DAYS[lang]
    talks = [s for s in _load("talks") if (days is None or _day(s["t"], now) in days) and _mine(s)]
    if not talks:
        return CANT_REMEMBER[lang]
    if not about:                                      # "what did we talk about yesterday?": the talks of then
        return _listed(sorted(talks, key=lambda s: s["t"])[-RECALL_OFFER:], days, lang, now, len(past))
    else:
        if embed is None:
            from assistant import knowledge
            embed = knowledge.embed
        ranked = _rank(about, talks, embed)
    if not ranked:
        return CANT_REMEMBER[lang]
    ranked = ranked[:RECALL_OFFER]
    _recall.update(offered=[ranked[0]], left=ranked[1:], at=now, talk=ranked[0], listed=[], turn=len(past))
    return _offer(ranked[0], lang, now=now)


SAID_THEN = re.compile(r"\bwhat did you (?:say|tell me)\b|뭐라고\s*(?:하셨|했|말했|말씀하셨)|무슨 말(?:을|씀을)?\s*(?:했|하셨)", re.I)
NAME_Q = re.compile(r"\b(?:you (?:still )?(?:remember|know|recall)|what(?:'s| is)) my name\b|\bremember my name\?|\bdid i (?:tell|give) you my name\b|\bwho (?:am|was) i\b|"
                    r"(?:제|내|my) ?(?:이름|name)\s*(?:을|를|은|는|이|가)?\s*(?:기억|알아|아세요|아십니까|아시|뭐|무엇|말했|말씀)", re.I)
NO_NAME = {"en": "I don't remember you telling me your name. What is it?", "ko": "성함은 기억에 없어요. 성함이 어떻게 되세요?"}


def name_answer(lang):
    """"Do you remember my name?": a name given in this talk, or in a kept talk with this person (re-id); never one
    made up."""
    name = _talk["name"] or next((s.get("name") for s in reversed(_load("talks"))
                                  if s.get("name") and _talk["track"] and s.get("person") == _talk["track"]), None)
    if not name:
        return NO_NAME[lang]
    name = name.title() if name.isascii() else name
    return f"Yes, you're {name}." if lang == "en" else f"네, {name}님이시죠."


DO_SAID = re.compile(   # "do what we said yesterday", "어제 말한 거 해 줘": a command from an earlier talk
    r"\b(?:do|go ahead with|carry out|start) (?:it|what|the (?:thing|task|plan)s?) (?:that )?(?:we|i|you) (?:said|agreed|planned|talked|asked|"
    r"told|decided|discussed)|\bdo what (?:we|i) (?:said|agreed|planned|talked|asked|told|decided)|"
    r"\b(?:what|the thing) (?:i|we) (?:told|asked) you to do\b.*\bdo it\b|\btime to do what\b|\bdo the thing we\b|"
    r"(?:말한|말씀드린|말씀한|얘기한|이야기한|부탁한|부탁드린|하기로 한|정한|약속한|plan ?한|계획한)\s*(?:거|것|대로|일)(?:을|를)?\s*"
    r"(?:지금\s*)?(?:해|do|하|진행|실행|시작)", re.I)
NOT_DO = re.compile(r"\b(?:don'?t|do not|never|why did)\b|하지 ?마|왜 ", re.I)
NOTHING_AGREED = {"en": "I don't remember agreeing on anything for me to do. What would you like me to do?",
                  "ko": "제가 하기로 한 일은 기억나지 않아요. 무엇을 해 드릴까요?"}


def do_said(text, lang="en", now=None):
    """Read back the command agreed in the latest talk that had one (of the day said) and ask first; never done
    here. None agreed: ask what to do."""
    days = _asked_days(text)
    if days == "too old":
        return ONLY_TWO_DAYS[lang]
    talks = [s for s in _load("talks") if s.get("commands") and _mine(s)]
    talks = [s for s in talks if days is None or _day(s["t"], now) in days] or talks   # "yesterday" for this morning's
    if not talks:
        return NOTHING_AGREED[lang]
    s = max(talks, key=lambda s: s["t"])
    _recall.update(offered=[], left=[], talk=s, listed=[])
    cmd = "; ".join(s["commands"])
    if lang == "ko":
        return f"{when(s['t'], 'ko', now)}에 이렇게 하기로 했어요: \"{cmd}\". 지금 할까요?"
    return f"{when(s['t'], 'en', now)[:1].upper() + when(s['t'], 'en', now)[1:]} we agreed: \"{cmd}\". Shall I do that now?"


def _listed(talks, days, lang, now=0.0, turn=-99):
    """"Yesterday I talked about bibimbap, dinosaurs and Lumi's cameras." (the next turn's prompt has them all). One
    talk: "Yesterday we talked about birds. Would you like to hear more?", and a yes tells it."""
    _recall.update(offered=[], left=[], talk=None, listed=talks)
    d = next(iter(days)) if days else None
    if len(talks) == 1:
        s = talks[0]
        _recall.update(offered=[s], talk=s, listed=[], at=now, turn=turn)
        if lang == "ko":
            return f"{ {None: '최근 이틀 동안', 0: '오늘은', 1: '어제는', 2: '그저께는'}[d]} {_title_ko(s)}에 대해 이야기했어요. 더 들어 보실래요?"
        return f"{ {None: 'In the last two days', 0: 'Today', 1: 'Yesterday', 2: 'The day before yesterday'}[d]} we talked " \
               f"about {_lower(s['title'])} at about {_clock(s['t'], 'en')}. Would you like to hear more?"
    if lang == "ko":
        names = ", ".join(_title_ko(s) for s in talks)
        return f"{ {None: '최근 이틀 동안', 0: '오늘은', 1: '어제는', 2: '그저께는'}[d]} {names}에 대해 이야기했어요. 더 듣고 싶은 이야기가 있으세요?"
    names = [s["title"] for s in talks]
    return f"{ {None: 'In the last two days', 0: 'Today', 1: 'Yesterday', 2: 'The day before yesterday'}[d]} I talked about " + \
        (", ".join(names[:-1]) + " and " + names[-1]) + ". Would you like to hear more about one of them?"


def _mine(s):
    """A talk with someone else who gave a name is not told to a named visitor (privacy)."""
    return not (s.get("name") and _talk["name"] and s["name"] != _talk["name"])


CHAT_EN = {"ur": "your", "u": "you", "pls": "please", "plz": "please", "da": "the", "dat": "that", "wat": "what", "r": "are"}


def _clean(text):
    """Whisper slips and chat spelling out: "w— what we talked" -> "what we talked", "is ur hand open" -> "is your
    hand open"."""
    text = re.sub(r"(?<![\w])(\w{1,3})\s*[—–-]+\s+(?=\1)", "", text)
    return re.sub(r"(?<![\w'])(?:ur|u|pls|plz|da|dat|wat|r)(?![\w'])", lambda m: CHAT_EN[m.group(0).lower()], text, flags=re.I)


SEEN_MORE = re.compile(r"\W*(?:(?:and|what about|how about|or|then|so|also|um|uh|oh|okay|ok|well|lumi|그럼|그러면|그리고|아니면|또|혹시|"
                       r"음|어|아|자|잠깐|저기|근데|그런데|루미야?)\W+)*(?:the |an? |any )?"
                       r"(?:[\w가-힣]+\s+)?([\w가-힣]+?)(?:은요|는요|이요|은|는|도|이나|나)?(?: either| too| then)?\W*", re.I)


def _seen_more(text):
    """"And a green apple?", "그럼 빨간 컵은?": a short follow-up naming only a thing (a colour or one word before it),
    after a "did you see ...?" answer; "do you see an apple?", "그럼 빨간 컵 가져와" are not."""
    text = re.split(r"[:,;]\s*", text.strip())[-1]                 # "Right, use case: and a green apple?"
    m = SEEN_MORE.fullmatch(text)
    return bool(m and _object(m.group(1)) and (re.search(r"[?？]|[은는도]\W*요?\W*$|^\W*(?:and|what about|how about|or)\b", text, re.I)))


def reply(text, lang="en", now=None, history=()):
    """What to say at once for a memory question ("forget this", "do you remember ...?", "did you see a cup today?"),
    else None. lumi.py asks it before the other routes."""
    text = _clean(text)
    if FORGET.search(text) and not re.search(r"\b(?:don'?t|never) forget\b|잊지\s*마", text, re.I):
        forget()
        return FORGOT[lang]
    now = clock() if now is None else now
    seen = _recall.get("seen")
    if seen and now - seen[0] < OFFER_WAIT_S and not SEEN_Q.search(text) and _seen_more(text):
        return seen_answer(text, lang, now, days=_asked_days(text) or seen[1] if _asked_days(text) != "too old" else seen[1])   # "흰 병 봤어?" -> "그럼 빨간 컵은?"
    return recall(text, lang, now, history=history) or seen_answer(text, lang, now) or self_answer(text, lang)


# ---------- the LLM's turn ----------
FACT = re.compile(r"\d|\bmy name\b|\bi'?m [A-Z]|\bi am [A-Z]|\bcall me\b|\bi (?:live|work|study|come|came)\b|\bi'?m from\b|"
                  r"\bmy (?:wife|husband|son|daughter|kid|kids|friend|boss|mom|dad|mother|father|brother|sister|birthday|car|dog|cat|"
                  r"phone|email|job|favou?rite)\b|\bi (?:like|love|hate|have|need|want)\b|이름|저는|제가|나는|내가|살아|살고|왔어|왔어요|"
                  r"다녀|일해|좋아해|좋아하|싫어|있어요|생일|우리 ?(?:아들|딸|엄마|아빠|회사|집)")


def earlier_facts(history, shown):
    """The turns of this talk the LLM no longer sees (history[:-shown]): visitor lines with names, numbers, places,
    plans (last EARLIER_N), and the topics talked about with the first sentence of each answer (last EARLIER_N), so
    "what's my name?" or "back to the moon: what was it?" late in a long talk is still known."""
    gone = history[:len(history) - shown] if shown else history
    lines = [q.strip()[:EARLIER_CHARS] for q, _ in gone if FACT.search(q)][-EARLIER_N:]
    said = []
    for q, a in gone:
        a = " ".join(ln for ln in a.splitlines() if not re.match(r"\s*\**ACTION", ln)).strip()
        first = re.split(r"(?<=[.!?。])\s+", a)[0][:EARLIER_CHARS] if a else ""
        if first and len(q.split()) > 1:
            said.append(f'"{q.strip()[:80]}" -> "{first}"')
    out = ("Said earlier in this talk by the visitor: " + " / ".join(f'"{x}"' for x in lines) + ".") if lines else ""
    if said:
        out += ("\n" if out else "") + "Earlier in this talk (asked -> you answered): " + " / ".join(said[-EARLIER_N:]) + "."
    return out


ABOUT_MEMORY = re.compile(r"\bremember\b|\bsaw\b|\bseen\b|\bearlier\b|\byesterday\b|\blast time\b|기억|봤|아까|어제|지난번", re.I)


def turn_lines(brain, text):
    """Memory lines for the LLM's turn message (brain.respond_stream): the body now, facts said earlier in this talk,
    a talk recalled; "" when none. Reads only what is in memory (no robot, no files) but for a memory question."""
    parts = []
    if _state["body"] and time.time() - _state["at"] < 10 * STATE_S:
        parts.append(_state["body"])
    early = earlier_facts(brain.history, len(brain.window()))
    if early:
        parts.append(early)
    for s in ([_recall["talk"]] if _recall.get("talk") else []) + _recall.get("listed", []):
        parts.append(f"A talk you remember ({when(s['t'])}): {s['title']}. {s['summary']} " +
                     " ".join(s.get("facts", [])[:5]) +
                     (f" Commands agreed then: {'; '.join(s['commands'])}. Before doing one, read it back and ask."
                      if s.get("commands") else " No command was agreed then."))
    if ABOUT_MEMORY.search(text):
        seen = seen_list()
        parts.append(seen or "You have seen nothing to remember in the last two days.")
        parts.append("You remember only the last two days; never invent a memory.")
    return ("\n".join(parts) + "\n\n") if parts else ""


def start(idle=lambda: True, after=None):
    """The live assistant keeps memories from now on. idle(): nobody is talking (a summary waits for it); after():
    run once a summary is made (lumi warms the LLM again: the summary took the runner's one slot)."""
    global on
    on = True
    _hooks.update(idle=idle, after=after)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        q = " ".join(sys.argv[1:])
        print(reply(q, "ko" if re.search(r"[가-힣]", q) else "en"))
    else:
        for s in _load("talks"):
            print(when(s["t"]), s.get("person"), s["title"], "-", s["summary"])
        print(seen_list() or "nothing seen kept")
