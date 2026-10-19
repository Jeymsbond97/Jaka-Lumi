"""Missions (docs/17): one command of several steps -> a list of steps, read by rules (and the LLM for what the
rules leave), checked against the hand and the map, read back in English or Korean.

    python assistant/steps.py "take the cup, go left 1 m and put it on the table"

A step is a dict, "do" says which:
    {"do": "go", "to": "p1" | "here" | ["p3", "p5"] (one of them, at random)}
    {"do": "move", "dir": "forward" | "back" | "left" | "right", "m": metres}
    {"do": "turn", "deg": + left}
    {"do": "pick", "object", "colour"}         {"do": "receive", "object"}      {"do": "say", "text"}
    {"do": "place", "on": None | {"name": camera class, "colour", "side": "left" | "right" | None}}
    {"do": "give"}   {"do": "hold"}   {"do": "arm", "pose": "reach" | "fold" | "open" | "close"}
    {"do": "wait", "s": seconds | None (until told to go on; at the end: stay there), "until": "instruction" (optional)}
    {"do": "receive", "object", "wait_s": seconds}     ("wait until someone gives you the cup": the hand held out this long)
Nothing is guessed: a clause the rules can't read stays unread and the whole command is asked again."""
import re
import sys

from assistant import brain, wording

MOVE_MAX_M = 3.0             # m; a mission's single move is at most this long
TURN_DEG = 90.0              # "turn left" without a number
SIDE_DEG = {"left": 90.0, "right": -90.0}
DO = ("go", "move", "turn", "pick", "receive", "say", "place", "give", "hold", "arm", "wait")
MISSION_ONLY = {"move", "turn", "receive", "say", "arm", "wait"}   # steps the plain fetch / carry can't do
WAIT_SHORT_S = 10.0          # s; "wait a moment", "잠깐 기다렸다가": a short wait
WAIT_MAX_S = 1800.0          # s; a longer wait is refused (check)
WAIT_GIVE_S = 300.0          # s; "wait until someone gives you the cup": the hand is held out this long, then the
                             # mission fails there (hand open, nothing driven)
WAIT_ORDER_S = 300.0         # s; "wait there and do what they tell you": no instruction by then -> the rest of the mission

OBJ, COL = brain._OBJ, brain._COL
_SUP = "|".join(k for k in brain.SUPPORTS if k.isascii())
_SUP_KO = "|".join(k for k in brain.SUPPORTS if not k.isascii())
_NUM = r"(\d+(?:\.\d+)?)"
_DIR = r"(forward|ahead|straight|back(?:wards?)?|left|right)"
_DIR_KO = r"(앞으로|뒤로|왼쪽으로|오른쪽으로)"
_FILL = (r"(?:please|hey lumi|hi lumi|hey|hi|lumi|loomi|rumi|okay|ok|instead|um+|uh+|er|hmm|thank you|thanks|now|then|and|also|first|next|"
         r"finally|after that|there|for me|again|carefully|slowly|could you|can you|would you|will you|lumi야|루미야|루미|음|응|어|야 로봇|로봇아|로봇야|"
         r"감사합니다|고마워요|고마워|고맙습니다|좀)")
_PEOPLE = r"(?:them|him|her|someone|somebody|the person(?: there)?|people|the people|everyone|everybody|the guests?)"
# where one step ends and the next starts
_SPLIT = re.compile(r"\s*(?:,|;|\.(?=\s|$)|\band then\b|\bthen\b|\band\b|\bafter that\b|그리고|그 다음에?|다음에)\s*")
_SPLIT_KO = re.compile(r"(?<=[가-힣](?:고|서))(?<!라고)(?<!다고)(?<!자고)(?<!냐고)(?<!에서)(?<!말고)\s+(?!있)|(?<=다가)\s+")   # "들고 ", "가서 ": a verb
                                                                                        # joining two steps, not a quote

def _norm(text):
    """Lower case, marker names and numbers as written (assistant/wording.py: "피쓰리로" -> "p3로", "half a meter" ->
    "0.5 m", "오십 센치" -> "0.5 m"), titles without their dot ("Mr. Park")."""
    t = re.sub(r"\b(mr|mrs|ms|dr|prof)\. ", r"\1 ", wording.durations(wording.norm(text)) + " ")
    return re.sub(r"\b(?:take|pick up|pick|grab)\s?(?:해서|하고)", "집어서", t).strip()   # "컵 take해서": mixed


# ---------- one clause -> one step ----------
def _place(word, markers):
    """A place word in a go clause -> marker name, "here", or None (not on the map)."""
    word = re.sub(r"(?<=\S) (?:point|marker)$|\s*(?:앞|옆|근처|쪽)$", "", word.strip())   # "the final point", "p5 앞"
    w = re.sub(r"^(?:either |the |your |my |point |marker |포인트 ?)", "", word)
    exact = next((mk for mk in markers if mk.lower() == w or mk.lower() == w.replace(" ", "")), None)
    if exact:
        return exact
    m = re.fullmatch(brain._place_re(markers), word.strip())
    if m:
        return brain._resolve(m, markers)
    if w in ("집", "홈", "도크", "충전기", "충전소", "dock", "charger", "home", "charging station"):
        return "home" if "home" in markers else None
    return None


def _places(t, markers):
    """'p3, p5 or p7' / 'p3' / 'here' -> list of names, or None when one of them is not a place on the map."""
    t = re.sub(r"^either\s+", "", t.strip())
    words = [w for w in re.split(r"\s*(?:,\s*(?:or|and)\b|,|\bor\b|\band\b|또는|(?<=[a-z\d])이나(?=\s)|(?<=[a-z\d])나(?=\s))\s*",
                                 t) if w.strip()]
    names = [_place(w, markers) for w in words]
    return names if names and None not in names else None


def _side(t):
    m = re.search(r"\b(?:on|to) (?:your|the|my) (left|right)\b|\bon the (left|right)\b|(왼쪽|오른쪽)", t)
    if not m:
        return None
    return {"왼쪽": "left", "오른쪽": "right"}.get(m.group(3), m.group(1) or m.group(2))


def _support(t):
    """'the white table' / '흰 테이블' -> {"name", "colour", "side"} or None."""
    on = brain.place_on(t) or brain.place_on("on " + re.sub(r"^.*?\b(?:for|find) ", "", t))
    return dict(on, side=_side(t)) if on else None


def _go(c, markers):
    m = re.fullmatch(r"(?:(?:go|drive|head|come|move|return|get)(?: back)?(?: over)?|(?:bring|take|carry) it(?: back)?)"
                     r" to (?:the )?(?:(?:a )?random (?:one )?of |one of |any of )?(?:the )?(.+?)(?: point| marker)?", c)
    if m:
        to = _places(m.group(1), markers)
        return to and {"do": "go", "to": to if len(to) > 1 else to[0]}
    m = re.fullmatch(r"(?:go|drive|head) (?:the )?(p\d+|final|dock2|exit)", c)          # whisper drops the "to"
    if m:
        to = _places(m.group(1), markers)
        return to and {"do": "go", "to": to[0]}
    if re.fullmatch(r"go (?:home )?(?:to )?charge(?: yourself)?|충전하러 (?:집으로 )?가", c):
        return {"do": "go", "to": "home"} if "home" in markers else None
    m = re.fullmatch(r"(?:go|drive|head|come|return)(?: back)? (home|here)|come back", c)
    if m:
        to = m.group(1) or "here"
        return {"do": "go", "to": to} if to == "here" or "home" in markers else None
    m = re.fullmatch(r"(?:bring|take|carry) it (?:back )?here", c)
    if m:
        return {"do": "go", "to": "here"}
    m = re.fullmatch(r"(?:(?:이거|이것|그거)\s+)?(.+?)\s*(?:중에서?|중)?\s*(?:아무 ?데나|아무 ?곳에나|하나|한 ?곳)?\s*"
                     r"(?:으로|로|에|까지)?\s*(?:가져가|가져와|가져다 ?줘|가져다|갖다 ?줘|갖다|가|와|가 ?줘|돌아가|돌아와|갔다가)"
                     r"(?:서|고|세요|줘|요)?|(\S+?)(?:으로|로)", c)
    if m:
        to = _places(re.sub(r"\s*(?:중에서?|중)\s*(?:아무 ?데나|아무 ?곳에나|하나|한 ?곳)?$", "", m.group(1) or m.group(2)),
                     markers)
        return to and {"do": "go", "to": to if len(to) > 1 else to[0]}
    m = re.fullmatch(r"(.+?)\s*중에?\s*(?:아무 ?데나|아무 ?곳에나|하나|한 ?곳(?:으로)?)\s*(?:가져가|가)(?:서|고|세요|줘)?", c)
    if m:
        to = _places(m.group(1), markers)
        return to and {"do": "go", "to": to if len(to) > 1 else to[0]}
    return None


def _move(c):
    dirs = {"ahead": "forward", "straight": "forward", "앞으로": "forward", "뒤로": "back", "왼쪽으로": "left",
            "오른쪽으로": "right"}
    pats = (rf"(?:(?:go|move|drive|step|walk|come|back up|head)\s+)?(?:to (?:the |your )?)?{_DIR}\s+(?:by\s+)?{_NUM} m",
            rf"(?:(?:go|move|drive|step|walk|come|back up|head)\s+)?{_NUM} m\s+(?:to (?:the |your )?)?{_DIR}",
            rf"(?:go|move|drive|step|walk|head)\s+{_NUM} m()",
            rf"{_DIR_KO}\s*{_NUM} m\s*(?:가|가고|가서|이동|이동해|움직여|와)(?:세요|줘)?")
    for p in pats:
        m = re.fullmatch(p, c)
        if m:
            d = next((g for g in m.groups() if g is not None and not re.fullmatch(r"[\d.]+", g)), "") or "forward"
            n = float(next(g for g in m.groups() if g and re.fullmatch(r"[\d.]+", g)))
            d = dirs.get(d, "back" if d.startswith("back") else d)
            return {"do": "move", "dir": d, "m": n}
    return None


def _turn(c):
    if re.fullmatch(r"turn(?: around)? 180(?: degrees?)?|(?:180\s*도|뒤로)\s*(?:돌아|돌고|돌아서)", c):
        return {"do": "turn", "deg": 180.0}
    m = re.fullmatch(r"turn (?:to the |to your )?(left|right|around)(?: by)?(?: {0}(?: degrees?)?)?".format(_NUM), c)
    if m:
        if m.group(1) == "around":
            return {"do": "turn", "deg": 180.0}
        n = float(m.group(2)) if m.group(2) else TURN_DEG
        return {"do": "turn", "deg": n if m.group(1) == "left" else -n}
    m = re.fullmatch(rf"(왼쪽으로|오른쪽으로|뒤로)\s*(?:{_NUM}\s*도\s*)?(?:돌고|돌아서|돌아|돌아줘|돌아요)", c)
    if m:
        if m.group(1) == "뒤로":
            return {"do": "turn", "deg": 180.0}
        n = float(m.group(2)) if m.group(2) else TURN_DEG
        return {"do": "turn", "deg": n if m.group(1) == "왼쪽으로" else -n}
    return None


def _thing(m_col, m_obj):
    return brain.OBJECTS[m_obj], brain.COLOURS.get(m_col) if m_col else None


def _pick_receive(c, markers):
    """pick / receive, and 'take the bottle from p2' -> [go p2, pick bottle]; a list of steps or None."""
    m = re.fullmatch(rf"(?:take|get|receive|accept|collect|grab) (?:the |a |an )?(?:({COL}) )?({OBJ})s? from {_PEOPLE}"
                     rf" (?:at|in|by) (.+)", c)
    if m:
        to = _places(m.group(3), markers)
        obj, col = _thing(m.group(1), m.group(2))
        return to and len(to) == 1 and [{"do": "go", "to": to[0]}, {"do": "receive", "object": obj}]
    m = re.fullmatch(rf"(?:take|get|receive|accept|collect|grab) (?:the |a |an )?(?:({COL}) )?({OBJ})s? from {_PEOPLE}"
                     rf"|ask {_PEOPLE} (?:for|from|to (?:give|hand) (?:you|me|it)?) ?(?:the |a |an )?(?:({COL}) )?({OBJ})s?"
                     rf"|ask {_PEOPLE} to (?:give|hand) (?:you|me) (?:the |a |an )?(?:({COL}) )?({OBJ})s?"
                     rf"|wait for {_PEOPLE} to (?:give|hand) (?:you|me) (?:the |a |an )?(?:({COL}) )?({OBJ})s?"
                     rf"|receive (?:the |a |an )?(?:({COL}) )?({OBJ})s?"
                     rf"|ask for (?:the |a |an )?(?:({COL}) )?({OBJ})s?", c)
    if m:
        g = m.groups()
        i = next(k for k in range(1, len(g), 2) if g[k])
        obj, col = _thing(g[i - 1], g[i])
        return [{"do": "receive", "object": obj}]
    m = re.fullmatch(rf"(?:(?:그 )?(?:사람|손님|분)(?:한테|에게|께)(?:서)?\s*)?(?:({COL})\s*)?({OBJ})\s*(?:을|를)?\s*"
                     rf"(?:받아|받고|받아서|받아줘|달라고 해)( ?와)?", c)
    if m:
        return [{"do": "receive", "object": brain.OBJECTS[m.group(2)]}] + ([{"do": "go", "to": "here"}] if m.group(3) else [])
    m = re.fullmatch(rf"(?:take|bring|carry|move|get) (?:the |a |an )?(?:({COL}) )?({OBJ})s? from (?:the )?(.+?) to (.+)", c)
    if m:
        src, to = _places(m.group(3), markers), _places(m.group(4), markers)
        obj, col = _thing(m.group(1), m.group(2))
        return src and to and len(src) == 1 and [{"do": "go", "to": src[0]}, {"do": "pick", "object": obj, "colour": col},
                                                 {"do": "go", "to": to if len(to) > 1 else to[0]}] or None
    m = re.fullmatch(rf"(?:pick up|pick|take|grab|get|lift)(?: up)? (?:the |a |an |that |this )?(?:({COL}) )?({OBJ})s?"
                     rf"(?: up)?(?: from (?:the )?(.+?))?", c)
    if m:
        obj, col = _thing(m.group(1), m.group(2))
        out = [{"do": "pick", "object": obj, "colour": col}]
        if m.group(3):
            src = _places(m.group(3), markers)
            if not src or len(src) > 1:
                return None
            out.insert(0, {"do": "go", "to": src[0]})
        return out
    m = re.fullmatch(rf"(?:pick up|pick|take|grab|get) (?:the |a |an )?(?:({COL}) )?({OBJ})s? (?:to|over to) (.+)", c)
    if m:
        to = _places(m.group(3), markers)
        obj, col = _thing(m.group(1), m.group(2))
        return to and [{"do": "pick", "object": obj, "colour": col}, {"do": "go", "to": to if len(to) > 1 else to[0]}]
    m = re.fullmatch(rf"(.+?)에서\s*(?:({COL})\s*)?({OBJ})\s*(?:을|를)?\s*(가져와서|가져와|가져오고|집어서|집고|잡고|"
                     rf"집어|들고)", c)
    if m:
        src = _places(m.group(1), markers)
        obj, col = _thing(m.group(2), m.group(3))
        back = [{"do": "go", "to": "here", "implied": True}] if m.group(4).startswith("가져") else []   # "bring"
        return src and len(src) == 1 and [{"do": "go", "to": src[0]}, {"do": "pick", "object": obj, "colour": col}] + back
    m = re.fullmatch(rf"(?:({COL})\s*)?({OBJ})\s*(?:을|를)?\s*(?:들고|잡고|집고|들어|잡아|집어|챙겨|집어줘|잡아줘|들어줘)(?:서)?", c)
    if m:
        obj, col = _thing(m.group(1), m.group(2))
        return [{"do": "pick", "object": obj, "colour": col}]
    return None


def _say(c):
    m = re.fullmatch(r"(.+?)(?:이?라고|고)\s*(?:말해|전해|얘기해|말해줘|전해줘|알려줘|말해 줘|전해 줘|말하고|전하고)"
                     r"(?:요|주세요)?", c)
    return m and {"do": "say", "text": m.group(1).strip().strip("'\"‘’“”").strip()}


def _give(c):
    if re.fullmatch(rf"(?:give|hand) (?:it|that|this|the (?:(?:{COL}) )?(?:{OBJ})s?)?(?: over)?"
                    rf"(?: to (?:me|you|{_PEOPLE}|the person there|whoever is there))?(?: there)?"
                    r"|hand it over|(?:give|hand) it", c) or \
            re.fullmatch(rf"(?:그거|그것을?|(?:(?:{COL})\s*)?(?:{OBJ})(?:을|를)?)?\s*(?:줘|주고|주세요|건네 ?줘|건네주고|"
                         rf"건네 ?주세요|건네)", c):
        return {"do": "give"}
    if re.fullmatch(r"(?:거기 있는\s*)?(?:나한테|저한테|나에게|저에게|그 사람한테|사람한테|그분께|분께|분한테)\s*"
                    r"(?:줘|주고|주세요|건네|건네줘|건네주고|건네주세요|건네 ?줘|건네 ?주세요|드려|드리고|갖다 ?줘|갖다 ?주세요)", c) or \
            re.fullmatch(r"(?:이|그|저|두|세|네) ?분(?:께|한테|에게)\s*(?:줘|주고|드려|드리고|건네|건네 ?줘|건네 ?드려)", c):
        return {"do": "give"}
    m = re.fullmatch(rf"(?:give|hand) (?:me|them|him|her) (?:the |it|that)(?:(?:({COL}) )?(?:{OBJ})s?)?", c)
    return {"do": "give"} if m else None


def _place_step(c):
    c = re.sub(r"\b(on|onto) (?:his|her|their|[a-z]+'s) ", r"\1 the ", c)
    if re.fullmatch(rf"(?:look for|find|search for) (?:a |the )?(?:({COL}) )?(?:{_SUP})s?(?: on (?:your|the|my) (?:left|right))?", c):
        return {"do": "place", "on": _support(c)}
    m = re.fullmatch(rf"(?:put|place|set|leave|drop) (?:it|that|this|the (?:(?:{COL}) )?(?:{OBJ})s?)(?: down)?(?: there| here)?"
                     rf"( (?:on|onto) .+)?", c)
    if m:
        on = _support(c)
        return {"do": "place", "on": on} if on or not m.group(1) else None     # "on the shelf": not a thing I know
    if re.fullmatch(rf"(?:(?:{COL})\s*)?(?:{_SUP_KO})\s*(?:을|를)?\s*(?:찾아서|찾고|찾아)", c):
        return {"do": "place", "on": _support(c)}
    _KO_PUT = r"(?:놔|놓아|놓고|내려놔|내려 ?놓고|내려 ?놓아|내려 놔|둬|두고|올려놔|올려 ?놓고|올려 놔|올려)"
    if re.search(rf"{_KO_PUT}(?:줘|주세요|요)?$", c):
        rest = re.sub(rf"\s*(?:에|위에)?\s*{_KO_PUT}(?:줘|주세요|요)?$", "", c)
        on = _support(rest) if rest else None
        if rest and not on and not re.fullmatch(r"(?:거기|여기|그거|그것을?|컵을?|거기에|여기에)", rest):
            return None
        return {"do": "place", "on": on}
    return None


def _hold(c):
    return {"do": "hold"} if re.fullmatch(r"(?:just )?(?:hold|keep) (?:it|on to it|holding(?: it)?)(?: there)?"
                                          r"|wait (?:there )?holding it|들고 있어(?:요|줘)?", c) else None


def _arm(c):
    for pose, p in (("reach", r"(?:reach out|stretch out|stretch|extend|put out|hold out) (?:your |my )?(?:arm|hand)|"
                              r"reach out|팔을? ?(?:뻗어|뻗고|내밀어|내밀고)(?:줘|요)?"),
                    ("fold", r"(?:fold|bend|tuck) (?:in )?(?:your |my )?arm(?: in)?|팔을? ?(?:접어|접고|굽혀|굽히고)(?:줘|요)?"),
                    ("open", r"open (?:your |my )?(?:hand|gripper|fingers)|let (?:it )?go|open it|"
                             r"(?:다시 )?손을? ?(?:펴|펴고|벌려|벌리고|열어|열고)(?:줘|요)?"),
                    ("close", r"close (?:your |my )?(?:hand|gripper|fingers)|close it|"
                              r"(?:다시 )?(?:손을? ?)?(?:쥐어|쥐고|오므려|닫아|닫고)(?:줘|요)?")):
        if re.fullmatch(p, c):
            return {"do": "arm", "pose": pose}
    return None


# ---------- waiting ("stay there", "wait 30 seconds", "wait until someone gives you a cup", "do what they tell you") ----
_DUR = r"(?:(\d+(?:\.\d+)?) s|(a (?:moment|second|sec|bit|little(?: bit| while)?|short (?:time|while))|"\
       r"one (?:moment|second|sec)|briefly|just a (?:moment|second|sec)))"         # wording.durations wrote "<n> s"
_DUR_KO = r"(?:(\d+(?:\.\d+)?) s|(잠깐만|잠시만|조금만|잠깐|잠시|조금))"
_STAY_EN = r"(?:wait|stay|remain|pause|hang on|hold on|stand by|stay put|sit tight|wait around|stand there|stay there)"
_THERE = r"(?: (?:right )?(?:there|here)| for me)*"
_GIVER = (r"(?:someone|somebody|anyone|anybody|a person|the person(?: there)?|they|people|a guest|the guests?|"
          r"someone there|he|she|them|him|her|a visitor|[a-z][a-z'-]+)")
_THING = rf"(?:(?:the|a|an|some|one|your) )?(?:({COL}) )?({OBJ}|something|anything|it|one|a thing|that)s?"
_WHO = (r"(?:they|the person(?: there)?|someone|somebody|people|he|she|the people(?: there)?|the guests?|"
        r"whoever is (?:there|at .+?)|anyone|anybody|the staff|them|him|her|the person you meet)")
_ORDERS = r"(?:(?:an?|their|new|the|further|more|your|next|any) )?(?:instructions?|orders?|commands?|tasks?|directions?)"
_ORDER_EN = (rf"do (?:what(?:ever)?|anything|as) {_WHO} (?:tells?|asks?|says?|wants?|needs?|orders?)(?: (?:of )?you)?"
             r"(?: to(?: do)?)?(?: there)?|do (?:what(?:ever)?|as) (?:you'?re|you are) (?:told|asked)(?: there)?"
             rf"|(?:take|get|follow|accept) {_ORDERS}(?: (?:there|from {_WHO}))?|listen to {_WHO}(?: there)?")
_KO_WAIT = (r"(?:기다려|기다려요|기다리고|기다려서|기다렸다가|기다리다가|기다린|기다리고 있어|기다리고 있다가|대기해|대기하고|"
            r"대기했다가|대기|있다가|있다 ?가|있어|있어요|있고|계세요|계십시오|있으세요|머물러|머물다가|머물고|쉬었다가|쉬고|"
            r"서 있다가|서 있어|가만히 있어|가 있어|가 있다가|가 있고)")
_KO_BARE = r"(?:기다려|기다려요|기다리고|기다려서|기다렸다가|기다리다가|기다리고 있어|대기해|대기하고|대기했다가|있다가|머물러|계세요)"
_KO_GIVER = (r"(?:누가|누군가|사람이|손님이|누가 와서|사람들이|그 사람이|그분이|거기 있는 사람이|거기 사람이|누구든|"
             r"[가-힣]{2,4}(?:이|가))")
_KO_ORDER = (r"(?:(?:거기|여기)\s*)?(?:(?:있는|계신)\s*)?(?:(?:사람|분|손님|사람들|그 사람|그분|누구|누가)(?:이|들이|가)?\s*)?"
             r"(?:시키는|하라는|말하는|부탁하는|원하는)\s*(?:거|것|일|대로|걸)\s*(?:을|를)?\s*(?:다\s*)?"
             r"(?:해|하고|해 줘|해줘|해 주고|들어|들어 줘|들어주고|하세요|하십시오|해요|해 주세요)"
             r"|(?:(?:거기|여기)(?:서|에서)?\s*)?(?:(?:새|다음|새로운)\s*)?(?:지시|명령|지시사항)\s*(?:을|를)?\s*"
             r"(?:기다려|기다리고|기다려요|받아|받아서|받고|따라|따르고)"
             r"|(?:누가|누군가|사람이)\s*(?:뭐|뭔가|무언가|일을|뭘)?\s*시키면\s*(?:그거\s*)?(?:해|하고|해 줘|들어 줘|해요)")


def _secs(num, short):
    return float(num) if num else WAIT_SHORT_S if short else None


def _at_place(word, markers):
    to = _places(word, markers) if word else None
    return to[0] if to and len(to) == 1 else None


def _wait(c, markers, after):
    """A clause about waiting -> list of steps, or None. `after`: the step before it (a bare "wait" / "기다려" is a
    step only after another one: alone it is "wait!" or a question)."""
    if re.fullmatch(rf"{_ORDER_EN}|(?:wait|stay){_THERE}(?: (?:for )?{_DUR})?(?: and)? (?:for|wait for) {_ORDERS}"
                    rf"(?: (?:there|from {_WHO}))?(?: for {_DUR})?|(?:{_DUR_KO}\s*(?:동안|정도|만)?\s*)?(?:{_KO_ORDER})", c):
        n = re.findall(r"(\d+(?:\.\d+)?) s", c)
        return [{"do": "wait", "s": float(n[0]) if n else WAIT_ORDER_S, "until": "instruction"}]
    m = re.fullmatch(rf"(?:{_STAY_EN}{_THERE} )?(?:(?:for )?(?:up to )?{_DUR} )?(?:until|till|til) "
                     rf"(?:{_GIVER} (?:gives?|hands?|brings?|passes?)(?: (?:you|me))? {_THING}(?: to (?:you|me))?|"
                     rf"you (?:get|are given|'re given|receive) {_THING})(?: for (?:up to )?{_DUR})?"
                     rf"|{_STAY_EN}{_THERE}(?: (?:for )?(?:up to )?{_DUR})? for {_GIVER} to (?:give|hand|bring|pass) (?:you|me) "
                     rf"{_THING}(?: for (?:up to )?{_DUR})?"
                     rf"|{_GIVER} will (?:give|hand|bring|pass) (?:you|me) {_THING}", c)
    if m:
        g = m.groups()
        obj = next((x for x in g if x in brain.OBJECTS), None)
        num = next((x for x in g if x and re.fullmatch(r"[\d.]+", x)), None)
        return [{"do": "receive", "object": brain.OBJECTS[obj] if obj else None, "wait_s": float(num) if num else WAIT_GIVE_S}]
    m = re.fullmatch(rf"(?:(.+?)에서\s*)?(?:(\d+(?:\.\d+)?) s\s*(?:동안|정도|만)?\s*)?{_KO_GIVER}\s*(?:({COL})\s*)?({OBJ}|물건|뭔가|무언가|그거|뭐|무엇을|뭘|이거)?\s*"
                     r"(?:을|를)?\s*(?:주면|건네주면|건네면|갖다주면|가져다주면|가져다 주면|줄 때까지|건네줄 때까지|줄 거야|"
                     r"줄 거예요|가져올 거야)\s*(?:기다렸다가|기다려서|기다리고|기다려|기다려요)?\s*"
                     r"(받아서|받아|받고|받아와|받아 와|받아요)?", c)
    if m and (m.group(1) is None or _at_place(m.group(1), markers)):
        obj = brain.OBJECTS.get(m.group(4) or "")
        return ([{"do": "go", "to": _at_place(m.group(1), markers)}] if m.group(1) else []) + \
            [{"do": "receive", "object": obj, "wait_s": float(m.group(2)) if m.group(2) else WAIT_GIVE_S}] + \
            ([{"do": "go", "to": "here"}] if m.group(5) in ("받아 와", "받아와") else [])
    if after and re.fullmatch(r"(?:거기|여기)(?:서|에서)", c):
        return []                                    # "p3로 가서 | 거기서 | 기다려": the place of the next step
    if after and after["do"] == "receive" and after.get("wait_s") and re.fullmatch(r"받아서|받아|받고|받아 와|받아와|받아요", c):
        return []                                    # "누가 컵 줄 때까지 기다렸다가 | 받아서": the same step
    # a time
    m = re.fullmatch(rf"{_STAY_EN}{_THERE} (?:for )?(?:(?:about|around|exactly|just) )?{_DUR}{_THERE}"
                     rf"|(?:after|in|wait) {_DUR}|{_DUR} later", c)
    if m:
        return [{"do": "wait", "s": _secs(*m.groups()[:2]) or _secs(*m.groups()[2:4]) or _secs(*m.groups()[4:6])}]
    m = re.fullmatch(rf"(?:after|in) {_DUR},? (.+)|{_DUR} later,? (.+)", c)
    if m:
        g = m.groups()
        rest = _clause(g[2] or g[5], markers)
        return rest and [{"do": "wait", "s": _secs(*g[:2]) or _secs(*g[3:5])}] + rest
    m = re.fullmatch(rf"(?:(.+?)에서\s*)?{_DUR_KO}\s*(?:만|동안|정도|쯤|간)?\s*{_KO_WAIT}(?:\s*줘)?", c)
    if m and (m.group(1) is None or _at_place(m.group(1), markers)):
        return ([{"do": "go", "to": _at_place(m.group(1), markers)}] if m.group(1) else []) + \
            [{"do": "wait", "s": _secs(m.group(2), m.group(3))}]
    m = re.fullmatch(rf"(?:(.+?)에서\s*)?{_DUR_KO}\s*(?:만)?\s*(?:뒤에?|후에?|있다가|지나서|지나고|지나면|기다렸다가|"
                     r"기다린 ?다음에?|기다린 ?후에?|기다린 ?뒤에?)\s+(.+)", c)
    if m and (m.group(1) is None or _at_place(m.group(1), markers)):
        rest = _clause(m.group(4), markers)
        return rest and ([{"do": "go", "to": _at_place(m.group(1), markers)}] if m.group(1) else []) + \
            [{"do": "wait", "s": _secs(m.group(2), m.group(3))}] + rest
    # at a place, no time limit (with a time: "wait at p3 for 30 seconds")
    m = re.fullmatch(rf"(?:go (?:and )?)?(?:wait|stay|remain)(?: for me)? (?:at|by|in|near) (?:the )?(.+?)(?: for {_DUR})?(?: for me)?", c)
    if m and _at_place(m.group(1), markers):
        return [{"do": "go", "to": _at_place(m.group(1), markers)}, {"do": "wait", "s": _secs(m.group(2), m.group(3))}]
    m = re.fullmatch(rf"(.+?)(?:에서|에)\s*(?:가\s*)?{_KO_WAIT}(?:\s*줘)?", c)
    if m and _at_place(m.group(1), markers):
        return [{"do": "go", "to": _at_place(m.group(1), markers)}, {"do": "wait", "s": None}]
    if re.fullmatch(rf"{_STAY_EN}(?: (?:right )?(?:there|here)| for me| until (?:i|we) (?:come back|call you|tell you"
                    r"(?: to go(?: on)?)?|say so)| until further notice| until (?:someone|somebody|they) tells? you to go(?: on)?)+"
                    r"|(?:거기|여기|그 ?자리)(?:서|에서|에)?\s*" + _KO_WAIT + r"(?:\s*줘)?|가만히 있어", c):
        return [{"do": "wait", "s": None}]
    if after and re.fullmatch(rf"(?:wait|stay|remain|stand by|stay put|wait around)|{_KO_BARE}(?:\s*줘)?", c):
        return [{"do": "wait", "s": None}]
    m = re.fullmatch(r"((?:go|drive|head|come|bring it|take it) .+?) ((?:wait|stay|remain) .+)", c)   # no comma between
    if m:
        first = _clause(m.group(1), markers)
        second = first and _wait(m.group(2), markers, first[-1])
        return first + second if first and second else None
    return None


_POLITE = re.compile(r"(?<=[가-힣])\s*(?:주십시오|주시겠어요|주시겠습니까|주실 수 있나요|주실 수 있습니까|주실 수 있어요|"
                     r"줄 수 있어요|줄 수 있어|주실래요|줄래요?|줘 ?봐요?|줘요?|주세요|죠)\??$")   # every speech level
_HONORIFIC = [(r"(가|와|놔|돌아|집어|잡어|잡아|들어|줘)봐요?$", r"\1"),                    # "가봐", "놔봐": try / do it
              (r"가(?:십시오|세요|시죠|요)$", "가"), (r"오(?:십시오|세요|시죠)$", "와"), (r"도(?:십시오|세요)$", "돌아"),
              (r"드리(?:십시오|세요)$", "드려"), (r"(?:주|드리)십시오$", "줘"), (r"물러나(?:세요|십시오|요)?$", "가"),
              (r"회전(?:해|하세요|하십시오|해요)$", "돌아"), (r"말씀(?:해|하세요|하십시오|해요|해 주세요)$", "말해"),
              (r"놓으(?:십시오|세요)$", "놔"), (r"기다리(?:십시오|세요|시죠|셔요)$", "기다려"),
              (r"대기하(?:십시오|세요|시죠)$", "대기해"),
              (r"(시키는|하라는|말하는) (거|것|대로|일|걸)\s*(?:을|를)?\s*하(?:십시오|세요|시죠)$", r"\1 \2 해")]


# ---------- a named person to give it to ("bring it to James at p6", "p6에 있는 제임스한테 갖다줘") ----------
_NAME = r"((?:mr|mrs|ms|dr|prof) [a-z]+|[a-z][a-z'-]+)"
_NOT_NAME = {"me", "him", "her", "them", "us", "you", "it", "someone", "somebody", "people", "everyone", "everybody",
             "whoever", "the", "a", "an", "my", "his", "their", "your", "boss", "here", "there", "this", "that", "home",
             "one", "random", "any", "either", "point", "marker", "he", "she", "they", "it's", "who"}
_KNAME = r"([가-힣]{1,4}(?: [가-힣]{1,4})?)"
_NOT_KNAME = {"이거", "이것", "그거", "사람", "그 사람", "분", "손님", "나", "저", "여기", "거기", "사장님", "사장", "누구",
              "이 분", "그 분", "저 분", "두 분", "세 분", "네 분",
              "왼쪽", "오른쪽", "앞", "뒤", "옆"}
_SEND = rf"(?:bring|take|carry|deliver|give|hand|send)"
_HELD = r"(?: it| this| that| this (?:{0})s?| that (?:{0})s?)?(?: over)?".format(OBJ)
_GIVE_KO = r"(?:갖다 ?주고|가져다 ?주고|갖다 ?줘|갖다 ?드려|가져다 ?줘|가져다 ?드려|전해 ?줘|전해|줘|드려|건네 ?줘|건네|주고|드리고)(?:요|주세요)?"


def _is_name(n, markers):
    n = n.strip()
    return bool(n) and n not in _NOT_NAME and n.split()[-1] not in _NOT_NAME and n not in brain.OBJECTS and \
        n not in brain.COLOURS and not any(n == m.lower() for m in markers) and not re.fullmatch(r"p\d+", n)


def _ko_name(n):
    """'민수 씨' -> '민수', '수진이' -> '수진'; titles with 님 stay ('김 부장님')."""
    n = re.sub(r"\s*씨$", "", n.strip())
    return n[:-1] if len(n) >= 3 and n.endswith("이") and " " not in n else n


def _person(c, markers):
    """Steps for a clause about a named person, or None. A give to a person whose place is not said yet is
    {"do": "give", "person", "where": None}; "he is at p6" is {"do": "_at", "person" or None, "to"}: rules() puts
    them together (or leaves the give unread)."""
    if re.fullmatch(rf"(?:{_NAME} (?:asks|asked|wants|wanted|would like) (?:you|me) to .*)", c):
        return None                                           # handled by stripping the sender first (_sender)
    if re.fullmatch(rf"(?:i'?m|i am) (?:{_NAME}|at .+)", c):
        return []                                             # the sender says who / where they are
    if re.fullmatch(rf"{_NAME} sends? (?:it|this|that)", c) and _is_name(c.split()[0], markers):
        return []
    m = re.fullmatch(rf"(?:put|place|set|leave) (?:it|this|that|the (?:(?:{COL}) )?(?:{OBJ})s?) (?:on|onto) "
                     rf"(?:my|his|her|their|the|[a-z]+'s) (?:({COL}) )?({_SUP})s? (?:at|in|by) (.+)", c)
    if m:
        to = _places(m.group(3), markers)
        return to and len(to) == 1 and [{"do": "go", "to": to[0]}, {"do": "place", "on": {
            "name": brain.SUPPORTS[m.group(2)], "colour": brain.COLOURS.get(m.group(1)), "side": None}}] or None
    if re.fullmatch(r"(?:[a-z]+ (?:isn'?t|is not|'s not)(?: .*)?|i'?m not (?:there|here|in|at).*|"
                    r"i'?m (?:going|coming|heading) (?:there|here|to .+)|is (?:that|it|this) from [a-z]+)", c):
        return []
    if re.fullmatch(r"(?:it'?s |this is )?from (?:[a-z][a-z'-]+)|on behalf of [a-z][a-z'-]+(?: .*)?", c) and \
            not re.search(r"\b(?:bring|take|give|hand|carry|send)\b", c):
        return []
    m = re.fullmatch(r"bring back the (?:({0}) )?({1})s? from (?:him|her|them) to me".format(COL, OBJ), c)
    if m:
        obj, col = _thing(m.group(1), m.group(2))
        return [{"do": "receive", "object": obj}, {"do": "go", "to": "here"}, {"do": "give"}]
    m = re.fullmatch(rf"{_SEND}(?: (?:the|a|an) (?:({COL}) )?({OBJ})s?(?: you'?re holding)?|{_HELD}) to {_NAME}"
                     rf"(?:,? (?:who is|(?:he|she|they)(?:'s| is| are)(?: waiting| standing)?|is) (?:at|in|by) (.+)|"
                     rf" (?:at|in|by) (.+)| (?:right )?(here))?", c)
    if m and m.group(3) in ("him", "her", "them") and not any(m.group(i) for i in (4, 5, 6)):
        return [{"do": "give", "person": "_them", "where": False}]        # "... take it to her": who from "_at"
    if m and _is_name(m.group(3), markers):
        out = []
        if m.group(2) and not re.search(r"you'?re holding", c):
            obj, col = _thing(m.group(1), m.group(2))
            out.append({"do": "pick", "object": obj, "colour": col})
        where = m.group(4) or m.group(5) or m.group(6)
        if where:
            to = _places(where, markers)
            if not to or len(to) > 1:
                return None
            out.append({"do": "go", "to": to[0]})
        return out + [{"do": "give", "person": m.group(3), "where": bool(where)}]
    m = re.fullmatch(rf"(?:{_NAME}(?: is| 's)|(?:he|she|they)(?:'s| is| are)) (?:(?:waiting|standing|sitting) )?"
                     rf"(?:(?:at|in|by) (.+)|(?:right )?(here))", c)
    if m and (m.group(1) is None or _is_name(m.group(1), markers) or m.group(1) in ("he", "she", "they")):
        to = _places(m.group(2) or m.group(3), markers)
        name = m.group(1) if m.group(1) and _is_name(m.group(1), markers) else None
        return to and len(to) == 1 and [{"do": "_at", "person": name, "to": to[0]}] or None
    m = re.fullmatch(rf"(?:get|take|receive) the (?:({COL}) )?({OBJ})s? from {_NAME}(?: (?:at|in|by) (.+))?|"
                     rf"ask {_NAME} for the (?:({COL}) )?({OBJ})s?", c)
    if m:
        g = m.groups()
        name, obj = (g[2], g[1]) if g[1] else (g[4], g[6])
        if _is_name(name, markers) and not _places(name, markers):
            out = [{"do": "receive", "object": brain.OBJECTS[obj]}]
            if g[3]:
                to = _places(g[3], markers)
                if not to or len(to) > 1:
                    return None
                out.insert(0, {"do": "go", "to": to[0]})
            return out
    # Korean
    m = re.fullmatch(rf"(?:이거|이것(?:을)?|이 (?:{OBJ})(?:을|를)?|(?:({COL})\s*)?({OBJ})(?:을|를)?)?\s*(?:들고|집어서|잡고)?\s*"
                     rf"(.+?)에 (?:있는|계신) {_KNAME}\s*(?:씨)?(?:한테|에게|께)\s*(?:(?:({COL})\s*)?({OBJ})(?:을|를)?\s*)?"
                     rf"{_GIVE_KO}", c)
    if m and m.group(6):                                       # "p6에 있는 제임스한테 컵 갖다줘": the object after the name
        return _person(f"{m.group(5) or ''} {m.group(6)} {m.group(3)}에 있는 {m.group(4)}한테 줘".strip(), markers)
    if m and _ko_name(m.group(4)) not in _NOT_KNAME:
        to = _places(m.group(3), markers)
        if not to or len(to) > 1:
            return None
        out = [{"do": "pick", "object": brain.OBJECTS[m.group(2)], "colour": brain.COLOURS.get(m.group(1))}] \
            if m.group(2) else []
        return out + [{"do": "go", "to": to[0]}, {"do": "give", "person": _ko_name(m.group(4)), "where": True}]
    m = re.fullmatch(rf"(?:이거 |이것 )?여기 있는 {_KNAME}(?:한테|에게|께)\s*{_GIVE_KO}", c)
    if m and _ko_name(m.group(1)) not in _NOT_KNAME:
        return [{"do": "go", "to": "here"}, {"do": "give", "person": _ko_name(m.group(1)), "where": True}]
    m = re.fullmatch(rf"{_KNAME}(?:이|가) (.+?)에(?:서)? (?:있어|있어요|있대|기다려|기다려요|기다리고 있어)(?:,? (?:이거 )?{_GIVE_KO})?", c)
    if m and _ko_name(m.group(1)) not in _NOT_KNAME:
        to = _places(m.group(2), markers)
        if not to or len(to) > 1:
            return None
        if re.search(_GIVE_KO + "$", c):
            return [{"do": "go", "to": to[0]}, {"do": "give", "person": _ko_name(m.group(1)), "where": True}]
        return [{"do": "_at", "person": _ko_name(m.group(1)), "to": to[0]}]
    m = re.fullmatch(rf"{_KNAME}\s*(?:씨)?(?:한테|에게|께)\s*{_GIVE_KO}", c)
    if m and _ko_name(m.group(1)) not in _NOT_KNAME:
        return [{"do": "give", "person": _ko_name(m.group(1)), "where": False}]
    m = re.fullmatch(rf"(.+?)에 있는 {_KNAME}(?:한테|에게|께)\s*(?:({COL})\s*)?({OBJ})(?:을|를)?\s*받(?:아|아서|고)", c)
    if m and _ko_name(m.group(2)) not in _NOT_KNAME:
        to = _places(m.group(1), markers)
        return to and len(to) == 1 and [{"do": "go", "to": to[0]}, {"do": "receive", "object": brain.OBJECTS[m.group(4)]}] \
            or None
    m = re.fullmatch(rf"{_KNAME}(?:한테|에게|께)\s*(?:({COL})\s*)?({OBJ})(?:을|를)?\s*받(?:아|아서|고)", c)
    if m and _ko_name(m.group(1)) not in _NOT_KNAME:
        return [{"do": "receive", "object": brain.OBJECTS[m.group(3)]}]
    m = re.fullmatch(rf"(.+?)에 있는 (?:({COL})\s*)?({_SUP_KO})(?: 위)?에 (?:놔|놓아|올려놔)", c)
    if m and _places(m.group(1), markers) and len(_places(m.group(1), markers)) == 1:
        return [{"do": "go", "to": _places(m.group(1), markers)[0]}, {"do": "place", "on": {
            "name": brain.SUPPORTS[m.group(3)], "colour": brain.COLOURS.get(m.group(2)), "side": None}}]
    m = re.fullmatch(r"(p\d+|final|dock2|exit|home) (?:테이블|책상|식탁)(?: 위)?에 (?:놔|놓아|올려놔)", c)
    if m:
        return [{"do": "go", "to": m.group(1)}, {"do": "place", "on": {"name": "dining table", "colour": None,
                                                                       "side": None}}]
    if re.fullmatch(r"\S+ (?:없으니까|없어서|없대|없네)|거기로 갈게|내가 거기로 갈게|거기 있을게", c):
        return []
    m = re.fullmatch(rf"(?:이거 )?(.+?)에 있는 {_KNAME} (?:책상|테이블)에 (?:놔|놓아|올려놔)", c)
    if m and m.group(2) not in _NOT_KNAME and m.group(2) not in brain.COLOURS:
        to = _places(m.group(1), markers) if m.group(1) else None
        if m.group(1) and (not to or len(to) > 1):
            return None
        return ([{"do": "go", "to": to[0]}] if to else []) + [{"do": "place", "on": {"name": "dining table",
                                                                                     "colour": None, "side": None}}]
    return None


_SENDER = [rf"^{_NAME} (?:asks|asked|wants|wanted|would like) (?:you|me) to ",
           rf"^{_NAME} sends? (?=the |this |it )", r"^(?:this is |it'?s )?from [a-z][a-z'-]+:? ",
           r"^on behalf of [a-z][a-z'-]+,? ",
           rf"^{_KNAME}(?:이|가) (?:보내는|보낸|보내신|부탁한|준) (?:거야|건데|거예요),?\s*",
           rf"^{_KNAME}(?:이|가) 보내는 (?=\S)", rf"^{_KNAME} 씨 심부름이야,?\s*", rf"^이거 {_KNAME}(?:이|가) 준 건데\s*",
           rf"^나 (?:.+?)에 있는 {_KNAME}인데,?\s*"]


def sender(text):
    """Who sends a mission ("Anvar asks you to bring ...", "I'm Anvar, ...", "안바르가 보내는 거야") or None."""
    t = _norm(_cut_says(text)[0])
    for p in [rf"(?:^|, |\. ){_NAME} (?:asks|asked|wants|wanted|would like) (?:you|me) to ", rf"(?:^|, ){_NAME} sends? ",
              rf"\bfrom {_NAME}\b", rf"\bon behalf of {_NAME}\b", rf"^(?:i'?m|i am) {_NAME}\b",
              rf"{_KNAME}(?:이|가) (?:보내는|보낸|보내신|부탁한|준)", rf"{_KNAME} 씨 심부름", rf"나 (?:.+?)에 있는 {_KNAME}인데"]:
        m = re.search(p, t)
        if m:
            n = m.group(1)
            return _orig(n, text) if n.isascii() else _ko_name(n)
    return None


def _sender(c):
    """A clause without who sends it ("Anvar asks you to bring ..." -> "bring ..."); the sender is not a step."""
    for p in _SENDER:
        c2 = re.sub(p, "", c)
        if c2 != c:
            if p.startswith("^이거"):
                c2 = "이거 " + c2
            if "sends" in p or " send" in p:
                c2 = "bring " + c2 if c2.startswith(("this ", "it ")) else c2
            return c2.strip()
    return c


def _clause(c, markers, after=None):
    """One clause -> list of steps, or None when it is not understood. `after`: the step before it."""
    c = re.sub(rf"^(?:{_FILL}[\s,]+)+|(?:[\s,]+{_FILL})+$", "", c.strip(" .!?")).strip(" .!?,")
    if re.search(r"[가-힣]", c):
        c = re.sub(r"\s+", " ", c)
        c = re.sub(r"\s좀\s", " ", c)
        c = re.sub(r"^(?:야\s+)?로봇(?:아|야)?[,\s]+", "", c)       # "야 로봇", "로봇아": calling it
        c = c.replace("그리퍼를", "손을").replace("물러나", "뒤로 물러나") if "뒤로" not in c else c.replace("그리퍼를", "손을")
        c = re.sub(r"(\d m)만", r"\1", c)                            # "1미터만"
        bare = _POLITE.sub("", c).strip()
        if bare != c and re.search(r"(?:건네|갖다|가져다|건네다)$", bare):
            c = bare + "줘"                       # "건네주십시오" -> "건네줘": 줘 is the verb itself
        elif bare != c and re.search(r"(?:[아어여해가와놔둬펴려봐]|물러나)$", bare):
            c = bare                              # "가 주세요" -> "가"; "나한테 줘" keeps its 줘 (the verb itself)
        for pat, rep in _HONORIFIC:
            c = re.sub(pat, rep, c)
        c = re.sub(r"뒤로 뒤로", "뒤로", c)
        c = re.sub(r"^계속\s+", "", c)
    if not c or re.fullmatch(_FILL, c):
        return []
    c = re.sub(r"^\S+ 말고\s+", "", c)                     # "미나 말고 사라한테": not Mina, Sara
    c = re.sub(r"^\S+ (?:없으니까|없어서|없대서)\s+", "", c)   # "현우 없으니까 ...": the reason, not a step
    c = re.sub(r"\s+(?:거기로|내가) 갈게$", "", c)
    c = re.sub(r"(?<=[a-z0-9]) (?:하고|해서|하고서|하고 나서|한 다음에?)$", "", c)     # "turn left 하고 p2로 가"
    raw, c = c, _sender(c)
    if not c:
        return []
    if re.fullmatch(r"(?:(?:it'?s |this is )?from|on behalf of) [a-z][a-z'-]+|[가-힣 ]+(?:이|가) (?:보내는|보낸) (?:거야|건데)", c):
        return []
    who = _person(c, markers)
    if who is not None:
        return who
    c = re.sub(r"^back ?up\b", "move back", c)
    c = re.sub(r"^(go|move|drive) write\b", r"\1 right", c)          # whisper's "go write 1 meter"
    c = re.sub(r"\bstraight ahead\b", "forward", c)
    c = re.sub(r"\bthe gripper\b", "your hand", c)
    c = c.replace("그리퍼", "손")
    m = re.fullmatch(r"(.+?)에 있는 (?:사람|분|손님)(?:한테|에게|께)\s*(?:갖다|가져다|건네) ?(?:줘|주고|주세요)?", c)
    if m:
        to = _places(m.group(1), markers)
        return to and len(to) == 1 and [{"do": "go", "to": to[0]}, {"do": "give"}] or None
    m = re.fullmatch(rf"(?:the|a) (?:({COL}) )?({OBJ})s?", c)            # "Kim sends the bottle": that one, picked here
    if m and c != raw:
        obj, col = _thing(m.group(1), m.group(2))
        return [{"do": "pick", "object": obj, "colour": col}]
    if c in ("bring it back to me", "bring it to me", "bring it back") or \
            re.fullmatch(r"(?:나한테|저한테|나에게|저에게)\s*(?:가져와|가져다 ?줘|가져와서|가져다 ?주고|가져다|갖다 ?줘|갖다)"
                         r"(?:요| ?주세요)?", c):
        return [{"do": "go", "to": "here"}, {"do": "give"}]
    if re.fullmatch(r"(?:여기로\s*)?(?:돌아와|돌아오고|돌아와서|와)(?:요|줘)?|(?:여기로|이리) 와(?:서|요|줘)?"
                    r"|이리와|come (?:back )?here|come back", c):
        return [{"do": "go", "to": "here"}]
    s = _wait(c, markers, after)
    if s is not None:
        return s
    for f in (_go, _move, _turn, _give, _hold, _arm):
        s = f(c, markers) if f is _go else f(c)
        if s:
            return [s]
    s = _pick_receive(c, markers)
    if s:
        return s
    s = _place_step(c) or _say(c)
    return [s] if s else None


# ---------- whole commands ----------
_STEP_VERB = (r"(?:go|come|drive|head|return|give|hand|put|place|set|leave|take|pick|grab|get|bring|carry|turn|move|"
              r"wait|hold|keep|open|close|reach|fold|receive|ask|find|look for)\b")
_SAY_EN = re.compile(rf"\b(?:(?:say|announce)\b|tell {_PEOPLE}(?: that)?)\s*[:.,]?\s*(?:[\"“‘']([^\"”’]+?)[\"”’']"
                     rf"|(.+?)(?=\s*(?:[,.]?\s*(?:and\s+|then\s+|and then\s+)+{_STEP_VERB}|[,.]\s*then\b|"
                     r"[,.]\s*(?:wait|stay) (?:for |there|here|until|\d|a |an |one |two |three |five |ten |half )|"
                     rf"(?<!\bmr)(?<!\bms)(?<!\bdr)(?<!\bmrs)(?<!\bprof)\.\s+[a-z]|$)))", re.I)


def _cut_says(text):
    text = re.sub(r"\bsay (hi|hello) with your hand\b", "wave", text, flags=re.I)   # a wave, not a message
    """The words to say are taken from the text as written (case, numbers) before anything else reads it:
    (text with each message replaced by '§N§', [messages])."""
    says = []

    def keep(m):
        says.append((m.group(1) or m.group(2)).strip().rstrip(".!?,").strip("\"“”'"))
        return f" §{len(says) - 1}§ "
    return _SAY_EN.sub(keep, text), says


def _split(t):
    out = []
    for part in _SPLIT.split(t):
        out += [p for p in _SPLIT_KO.split(part) if p.strip()]
    return out


def _protect_lists(t, markers):
    """'p3, p5 or p7' (one of them) must not be split as clauses: joined with '|'. Only a list that says "or",
    "one of", "random", "중": "go to p1 and p2" is two drives, not a choice."""
    place = rf"(?:{brain._place_re(markers)})"
    sep = r"\s*(?:,\s*(?:or|and)\b|,|\bor\b|\band\b|또는|(?<=\d)나)\s*"

    def join(m):
        before, after = t[:m.start()], t[m.end():]
        if re.search(r"\bor\b|또는|(?<=\d)나", m.group(0)) or re.match(r"\s*중", after) or \
                re.search(r"\b(?:(?:one|any) of|random(?: one)? of)(?: the)?\s*$", before):
            return re.sub(sep, "|", m.group(0))
        return m.group(0)
    return re.sub(rf"{place}(?:{sep}{place})+", join, t)


# "wait, go to p2" / "hold on, ...": a word to get attention, not a step (not "wait a minute, then ...")
_INTERJECTION = re.compile(r"^(?:(?:(?:oh|ah|um|uh) )?(?:wait(?: wait)*|hold on|hang on|one (?:moment|second)|"
                           r"wait a (?:sec|second|moment)|wait 60 s|(?:아|어) 잠깐(?:만)?(?:요)?|잠깐(?:만)?(?:요)?|잠시만(?:요)?)"
                           r"\s*[,.!]+\s*)+(?!then\b|and\b|after\b)(?=\S)")


def rules(text, markers=()):
    """(steps, unread clauses). Steps are merged where two clauses mean one ("look for the table" + "put it there")."""
    cut, says = _cut_says(text)
    t = _protect_lists(_norm(cut), markers)
    t = _INTERJECTION.sub("", t)
    steps, unread = [], []
    for c in _split(t):
        c = c.replace("|", ", ")
        m = re.fullmatch(r"§(\d+)§", c.strip())
        got = [{"do": "say", "text": says[int(m.group(1))]}] if m else _clause(c, markers, steps[-1] if steps else None)
        if got is None and steps and steps[-1] == {"do": "go", "to": "home"} and re.fullmatch(r"charge(?: yourself)?|충전해", c):
            continue
        if got is None and steps and steps[-1]["do"] == "go":
            to = _places(re.sub(r"^(?:(?:and )?then )?(?:to )?(?:the )?", "", c.strip()), markers)
            got = to and [{"do": "go", "to": to if len(to) > 1 else to[0]}]
        if got is None or (not m and "§" in c):
            unread.append(re.sub(r"§(\d+)§", lambda x: says[int(x.group(1))], c))
            continue
        for s in got:
            if s["do"] == "place" and steps and steps[-1]["do"] == "place":
                steps[-1]["on"] = steps[-1]["on"] or s["on"]
            elif s == {"do": "wait", "s": None} and steps and steps[-1]["do"] == "wait":
                continue                                 # "기다리고 | 계세요": one wait
            elif s["do"] == "go" and steps and steps[-1] == s:
                continue                                 # "go to p3 and wait at p3": one drive
            elif steps and steps[-1] == {"do": "wait", "s": None} and (s.get("until") or s.get("wait_s")):
                steps[-1] = s                            # "wait there and do what they tell you": one wait
            else:
                steps.append(s)
    steps = [s for i, s in enumerate(steps)                 # "bring it" then a place to go: no trip back first
             if not (s.pop("implied", False) and i + 1 < len(steps) and steps[i + 1]["do"] == "go")]
    steps, unread = _people(steps, unread, text)
    if steps and not unread and all(s["do"] == "wait" for s in steps):
        return [], [text.strip()]                # "hold on a second", "wait here": talk to me, not a task
    return steps, unread


def _orig(name, text):
    """A name as the command writes it ("Mr. Park", "peter"), found again in the text."""
    m = re.search(r"(?<!\w)" + r"\.?\s+".join(map(re.escape, name.split())) + r"(?!\w)", text, re.I)
    return m.group(0) if m and m.group(0).isascii() else name


def _people(steps, unread, text):
    """Put a give to a named person together with where they are ("bring it to James, he is at p6"): a drive there
    before it. A named person nobody says where: unread (Lumi asks), unless Lumi drives somewhere first. A give
    followed by a put-down there ("... and put it on his desk"): the put-down is what is meant."""
    ats, out = [s for s in steps if s["do"] == "_at"], []
    for s in steps:
        if s["do"] == "_at":
            continue
        if s["do"] == "give" and "where" in s:
            where = s.pop("where")
            if not where:
                at = next((a for a in ats if a["person"] is None or s["person"] == "_them" or
                           a["person"].lower() == s["person"].lower()), None)
                if at:
                    ats.remove(at)
                    out.append({"do": "go", "to": at["to"]})
                    if s["person"] == "_them" and at["person"]:
                        s["person"] = at["person"]
                elif s["person"] != "_them" and not any(x["do"] in ("go", "move", "turn") for x in out):
                    unread.append(f"where is {s['person']}?")
                    continue
            if s["person"] == "_them":                       # "give it to them": whoever is there
                out.append({"do": "give"})
                continue
            s["person"] = _orig(s["person"], text)
        out.append(s)
    unread += [f"who is at {a['to']}?" for a in ats]
    out = [s for i, s in enumerate(out) if not (s["do"] == "give" and s.get("person") and i + 1 < len(out)
                                                and out[i + 1]["do"] == "place")
           and not (s == {"do": "give"} and i and out[i - 1]["do"] == "give")]      # "to Tom at p9, give it"
    return out, unread


def read(text, markers=(), llm=True):
    """(steps, unread, "rules" | "llm" | "other"). Rules first; when they leave a clause of a command of several
    clauses unread, the LLM reads the whole command and its answer is kept only if every value in it is written in
    the command (_checked). "other": the LLM says it is not English or Korean, nothing is taken."""
    s, u = rules(text, markers)
    if not u or not llm or len(_split(_norm(_cut_says(text)[0]))) < 2:
        return s, u, "rules"
    got = _llm(text, markers)
    if got == "other":
        return [], [text], "other"
    if got and not _in_order(s, got):            # what the rules did read must be there, in the same order
        got = None
    return (got, [], "llm") if got else (s, u, "rules")


def _in_order(part, whole):
    it = iter(whole)
    return all(any(x == y for y in it) for x in part)


# ---------- the LLM pass ----------
LLM_PROMPT = """You turn a command for a mobile robot with one arm into a list of steps. Only English and Korean.
Step types ("do"):
- go: drive to a place. "to": list of marker names, one name normally; several only for "one of p3, p5 or p7".
  "here" = back where the command was given ("come back", "bring it back here"). Markers: {markers}.
- move: drive a distance. "dir": forward | back | left | right, "m": metres as said (50 cm = 0.5).
- turn: turn on the spot. "deg": + left, - right, 180 around.
- pick: take an object from a table. "object": one of {objects}; "colour": one of {colours} or null.
- receive: take an object a person hands over ("ask them for the cup", "take the cup from the person"). "object".
- say: speak words. "text": the words exactly as written in the command.
- place: put the held object down. "on": null, or {{"name": one of {supports}, "colour", "side": left | right | null}}.
- give: hand the held object to a person.   - hold: keep holding it (only when said).
- arm: "pose": reach | fold | open | close.
- wait: wait where it is. "s": seconds as said (2 minutes = 120), null = no time said (until told to go on);
  "until": "instruction" when it is to wait for the person there to say what to do ("do what they tell you").
- unknown: a part that is none of these (dance, follow me, a place not in the list, an object not in the list).
Rules: only what the command says, in its order; never add a step or a value that is not said; never translate
or guess a word ("olma" is not "orange"); a part you can't read exactly is an "unknown" step.
Answer JSON: {{"steps": [ ... ]}}."""
LLM_SCHEMA = {"type": "object", "required": ["steps"], "properties": {"steps": {"type": "array", "items": {
    "type": "object", "required": ["do"], "properties": {
        "do": {"enum": list(DO) + ["unknown"]}, "to": {"type": "array", "items": {"type": "string"}},
        "dir": {"enum": ["forward", "back", "left", "right"]}, "m": {"type": "number"}, "deg": {"type": "number"},
        "object": {"type": ["string", "null"]}, "colour": {"type": ["string", "null"]}, "text": {"type": "string"},
        "on": {"type": ["object", "null"], "properties": {"name": {"type": "string"}, "colour": {"type": ["string", "null"]},
                                                          "side": {"type": ["string", "null"]}}},
        "pose": {"enum": ["reach", "fold", "open", "close"]}, "s": {"type": ["number", "null"]},
        "until": {"type": ["string", "null"]}}}}}}
LLM_NUM_PREDICT = 700        # tokens; a 7-step answer is ~400
NEGATION = re.compile(r"\b(?:not|don'?t|do not|never|instead|except|without|no)\b|말고|대신|하지 ?마|지 ?마|빼고")
VERBS = {"give": r"\b(?:give|hand|pass)\b|줘|주고|주세요|건네|드려|드리", "hold": r"\b(?:hold|keep)\b|들고 있",
         "place": r"\b(?:put|place|set|leave|drop)\b|놔|놓|둬|내려",
         "receive": r"\b(?:ask|receive|accept|from (?:them|him|her|the person|someone|somebody|people))\b|받|달라"}


def _ollama(messages, fmt):
    import json
    import urllib.request
    body = {"model": brain.MODEL, "messages": messages, "stream": False, "think": False, "format": fmt,
            "keep_alive": -1, "options": {"temperature": 0.0, "num_predict": LLM_NUM_PREDICT}}
    req = urllib.request.Request(brain.OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(json.loads(r.read())["message"]["content"])


def _llm(text, markers):
    """The LLM's steps for `text` when every one passes _checked; None when one doesn't (or the LLM fails);
    "other" when the text is not English or Korean."""
    import json
    if NEGATION.search(_norm(text)):             # "don't take the cup", "p3 말고": the rules alone, never the LLM
        return None
    try:
        if not brain.HANGUL.search(text):        # asked on its own: inside a longer prompt the model calls Uzbek English
            lang = str(_ollama([{"role": "system", "content": brain.LANGUAGE_Q}, {"role": "user", "content": text}],
                               "json").get("language", "")).lower()
            if lang not in ("english", "en"):
                return "other"
        d = _ollama([{"role": "system", "content": LLM_PROMPT.format(
            markers=", ".join(markers) or "(none)", objects=", ".join(sorted(set(brain.OBJECTS.values()))),
            colours=", ".join(sorted(set(brain.COLOURS.values()))), supports=", ".join(sorted(set(brain.SUPPORTS.values()))))},
            {"role": "user", "content": text}], LLM_SCHEMA)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    out = []
    for raw in d.get("steps") or []:
        s = _checked(raw, text, markers) if isinstance(raw, dict) else None
        if s is None:
            return None
        out.append(s)
    t = _norm(text)
    for s in out:                                # a number used more often than it is said: a step made up twice
        n = s.get("m") if s["do"] == "move" else abs(s["deg"]) if s["do"] == "turn" and abs(s["deg"]) not in (90, 180) \
            else None
        if n is not None and sum(1 for x in out if x.get("m") == n or abs(x.get("deg") or 0) == n) > \
                len(re.findall(rf"(?<![\w.]){n:g}(?![\d.])", t)):
            return None
    return out or None


def _said(word_map, value, t):
    """Is a word for `value` (an English class / colour) written in t?"""
    return any(re.search(rf"(?<![a-z]){re.escape(w)}s?(?![a-z])" if w.isascii() else re.escape(w), t)
               for w, v in word_map.items() if v == value)


def _checked(raw, text, markers):
    """One LLM step in the reader's form, only when every value in it is written in the command; else None."""
    t, flat = _norm(text), re.sub(r"\s+", " ", text.lower())
    num = lambda x: re.search(rf"(?<![\w.]){float(x):g}(?![\d.])", t)
    d = raw.get("do")
    if d == "go":
        to = [x for x in raw.get("to") or [] if isinstance(x, str)]
        names = []
        for x in to:
            if x == "here" and re.search(r"\b(?:here|back|me)\b|여기|돌아|나한테|저한테", t):
                names.append("here")
                continue
            mk = next((m for m in markers if m.lower() == x.lower()), None)
            if mk is None or not brain.named_place(text, mk, markers):
                return None
            names.append(mk)
        return {"do": "go", "to": names if len(names) > 1 else names[0]} if names else None
    if d == "move":
        if raw.get("dir") not in ("forward", "back", "left", "right") or not isinstance(raw.get("m"), (int, float)):
            return None
        word = {"forward": r"\b(?:forward|ahead|straight)\b|앞으로", "back": r"\bback|뒤로", "left": r"\bleft\b|왼쪽",
                "right": r"\bright\b|오른쪽"}[raw["dir"]]
        if not num(raw["m"]) or not re.search(word, t):
            return None
        return {"do": "move", "dir": raw["dir"], "m": float(raw["m"])}
    if d == "turn":
        deg = raw.get("deg")
        if not isinstance(deg, (int, float)) or not re.search(r"\bturn|돌", t):
            return None
        said = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*(?:degrees?|도)", t)]
        if said and abs(deg) not in said or not said and abs(deg) not in (90, 180):
            return None
        if abs(deg) == 180 and not said:
            if not re.search(r"\baround\b|뒤로 ?돌", t):
                return None
        elif not re.search(r"turn (?:to the |to your )?{0}\b|{1}으로\s*(?:[\d.]+\s*도\s*)?돌".format(
                *(("left", "왼쪽") if deg > 0 else ("right", "오른쪽"))), t):
            return None
        return {"do": "turn", "deg": float(deg)}
    if d in ("pick", "receive"):
        obj, col = raw.get("object"), raw.get("colour")
        if obj not in brain.OBJECTS.values() or not _said(brain.OBJECTS, obj, t):
            return None
        if d == "receive":
            return {"do": "receive", "object": obj} if re.search(VERBS["receive"], t) else None
        if col is not None and (col not in brain.COLOURS.values() or not _said(brain.COLOURS, col, t)):
            return None
        return {"do": "pick", "object": obj, "colour": col}
    if d == "say":
        words = re.sub(r"\s+", " ", str(raw.get("text") or "")).strip().strip("\"'“”").rstrip(".!?,")
        return {"do": "say", "text": words} if words and words.lower() in flat else None
    if d == "place":
        on = raw.get("on")
        if not re.search(VERBS["place"], t):
            return None
        if not on:
            return {"do": "place", "on": None}
        name, col, side = on.get("name"), on.get("colour"), on.get("side")
        if name not in brain.SUPPORTS.values() or not _said(brain.SUPPORTS, name, t):
            return None
        if col is not None and (col not in brain.COLOURS.values() or not _said(brain.COLOURS, col, t)):
            return None
        if side is not None and side != _side(t):
            return None
        return {"do": "place", "on": {"name": name, "colour": col, "side": side}}
    if d in ("give", "hold"):
        return {"do": d} if re.search(VERBS[d], t) else None
    if d == "wait":
        secs, until = raw.get("s"), raw.get("until")
        said = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?) s\b", t)]           # wording.durations wrote them
        if until not in (None, "instruction") or secs is not None and not isinstance(secs, (int, float)):
            return None
        if until:
            if not re.search(r"\b(?:instructions?|orders?|commands?|tells?|says?|asks?)\b|시키|지시|명령", t):
                return None
            if secs is None or secs == WAIT_ORDER_S and float(WAIT_ORDER_S) not in said:
                return {"do": "wait", "s": WAIT_ORDER_S, "until": "instruction"}
            return {"do": "wait", "s": float(secs), "until": "instruction"} if float(secs) in said else None
        if secs is None:
            return {"do": "wait", "s": None} if re.search(r"\b(?:wait|stay|remain)\b|기다|대기|계세요", t) else None
        if float(secs) in said or secs == WAIT_SHORT_S and re.search(rf"{_DUR}|잠깐|잠시|조금", t):
            return {"do": "wait", "s": float(secs)}
        return None
    if d == "arm":
        pat = {"reach": r"reach|stretch|뻗|내밀", "fold": r"fold|bend|tuck|접|굽", "open": r"\bopen|펴|벌려|열",
               "close": r"\bclose|쥐|오므|닫"}.get(raw.get("pose"))
        return {"do": "arm", "pose": raw["pose"]} if pat and re.search(pat, t) else None
    return None


def is_mission(steps):
    """True when the plain fetch (go? pick go? place|hold?) or carry (go? place|give|hold?) can't do it."""
    kinds = [s["do"] for s in steps]
    if steps and set(kinds) == {"wait"}:
        return False                             # "wait here", "wait 30 seconds" alone: nothing to do as a task
    if not steps or MISSION_ONLY & set(kinds):
        return bool(steps)
    if any(s["do"] == "go" and isinstance(s["to"], list) for s in steps):
        return True
    if any(s["do"] == "place" and (s["on"] or {}).get("side") for s in steps) or any(s.get("person") for s in steps):
        return True
    shape = "".join({"go": "g", "pick": "p", "place": "e", "hold": "e", "give": "v"}.get(k, "?") for k in kinds)
    return not re.fullmatch(r"g?pg?e?|g?[ev]?", shape)


MOVE_MIN_M = 0.1             # m; a shorter move is not driven (the clearance check works in 5 cm steps)
TURN_MAX_DEG = 360.0


def _bad_fields(s):
    """Why a step dict (it may come from the dashboard's JSON) is not one this reader makes, or None."""
    if not isinstance(s, dict) or s.get("do") not in DO:
        return "a step I don't know"
    d, num = s["do"], lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    to = s.get("to")
    if d == "go" and not (isinstance(to, str) and to or isinstance(to, list) and to and all(isinstance(x, str) for x in to)):
        return "a drive without a place"
    if d == "move" and (s.get("dir") not in ("forward", "back", "left", "right") or not num(s.get("m"))):
        return "a move without a direction or distance"
    if d == "turn" and not num(s.get("deg")):
        return "a turn without an angle"
    if d in ("pick", "receive") and s.get("object") not in set(brain.OBJECTS.values()) | ({None} if d == "receive" else set()):
        return "an object I don't know"
    if d == "pick" and s.get("colour") not in set(brain.COLOURS.values()) | {None}:
        return "a colour I don't know"
    if d == "say" and not (isinstance(s.get("text"), str) and s["text"].strip()):
        return "nothing to say"
    on = s.get("on")
    if d == "place" and on is not None and not (isinstance(on, dict) and on.get("name") in set(brain.SUPPORTS.values())
                                                and on.get("colour") in set(brain.COLOURS.values()) | {None}
                                                and on.get("side") in ("left", "right", None)):
        return "a place I don't know"
    if d == "give" and not isinstance(s.get("person", ""), str):
        return "a person without a name"
    if d == "arm" and s.get("pose") not in ("reach", "fold", "open", "close"):
        return "an arm movement I don't know"
    if d == "wait" and (not (s.get("s") is None or num(s["s"])) or s.get("until") not in (None, "instruction")
                        or s.get("until") and s.get("s") is None):
        return "a wait I don't know"
    if d == "receive" and "wait_s" in s and not num(s["wait_s"]):
        return "a wait I don't know"
    return None


def check(steps, holding, markers=()):
    """What is wrong with running `steps` from now (the hand full or not): a list of sentences, empty when fine."""
    out, received = [], False
    if not isinstance(steps, list) or not steps:
        return ["There is nothing to do."]
    for i, s in enumerate(steps, 1):
        bad = _bad_fields(s)
        if bad:
            out.append(f"Step {i}: {bad}.")
            continue
        d = s["do"]
        if d == "go":
            bad = [p for p in (s["to"] if isinstance(s["to"], list) else [s["to"]]) if p != "here" and p not in markers]
            if bad:
                out.append(f"I don't know the place {', '.join(bad)}.")
        elif d == "move" and not MOVE_MIN_M <= s["m"] <= MOVE_MAX_M:
            out.append(f"I drive {MOVE_MIN_M:g} to {MOVE_MAX_M:g} m in one go.")
        elif d == "turn" and not 0 < abs(s["deg"]) <= TURN_MAX_DEG:
            out.append(f"I turn at most {TURN_MAX_DEG:g} degrees at a time.")
        elif d == "wait" and s["s"] is not None and not 0 < s["s"] <= WAIT_MAX_S or \
                d == "receive" and "wait_s" in s and not 0 < s["wait_s"] <= WAIT_MAX_S:
            out.append(f"Step {i}: I wait at most {WAIT_MAX_S / 60:g} minutes.")
        elif d in ("pick", "receive"):
            if holding:
                out.append(f"Step {i}: my hand is full already.")
            holding, received = True, d == "receive"
        elif d in ("place", "give"):
            if d == "place" and received:
                out.append(f"Step {i}: I can't put down something handed to me yet: I don't know where it sits in my "
                           "hand. I can hand it over or hold it.")
            if not holding:
                out.append(f"Step {i}: I have nothing in my hand to {'put down' if d == 'place' else 'hand over'}.")
            holding = False
        elif d == "arm" and s["pose"] in ("reach", "fold") and holding:
            out.append(f"Step {i}: I can't move my arm like that while holding something.")
        elif d == "arm" and s["pose"] == "open" and holding:
            out.append(f"Step {i}: I won't open my hand while holding something: it would fall. "
                       "Say put it down or hand it over.")
    return out


# ---------- read-back ----------
def _on_words(on, ko=False):
    if not on:
        return "테이블" if ko else "a table"
    name = {"dining table": "테이블" if ko else "table", "couch": "소파" if ko else "sofa", "chair": "의자" if ko else "chair",
            "bench": "벤치" if ko else "bench", "bed": "침대" if ko else "bed"}.get(on["name"], on["name"])
    col = on.get("colour")
    if ko:
        side = {"left": "왼쪽 ", "right": "오른쪽 "}.get(on.get("side"), "")
        return f"{side}{(brain_ko(col) + ' ') if col else ''}{name}"
    side = f" on my {on['side']}" if on.get("side") else ""
    return f"the {col + ' ' if col else ''}{name}{side}"


def brain_ko(colour):
    from tasks.fetch import COLOURS as KO
    return KO.get(colour, colour)


def _dur(sec, ko=False):
    """120 -> "2 minutes" / "2분", 90 -> "1 minute 30 seconds" / "1분 30초"."""
    m, x = divmod(int(round(sec)), 60)
    if ko:
        return " ".join(([f"{m}분"] if m else []) + ([f"{x}초"] if x else [])) or "0초"
    return " ".join(([f"{m} minute{'s' * (m != 1)}"] if m else []) + ([f"{x} second{'s' * (x != 1)}"] if x else []))


def _en(s, last=False):
    d = s["do"]
    if d == "wait":
        if s.get("until"):
            return f"wait there for an instruction (up to {_dur(s['s'])})"
        if s["s"] is None:
            return "stay there" if last else "wait there until I'm told to go on"
        return f"wait {_dur(s['s'])}"
    if d == "go":
        to = s["to"]
        if isinstance(to, list):
            return f"go to one of {', '.join(to[:-1])} or {to[-1]}"
        return "come back here" if to == "here" else "go to my dock" if to == "home" else f"go to {to}"
    if d == "move":
        if s["dir"] in ("left", "right"):
            return f"turn {s['dir']} and drive {s['m']:g} m"
        return f"drive {s['m']:g} m {s['dir']}"
    if d == "turn":
        if abs(s["deg"]) == 180:
            return "turn around"
        side = "left" if s["deg"] > 0 else "right"
        return f"turn {side}" + ("" if abs(s["deg"]) == TURN_DEG else f" {abs(s['deg']):g} degrees")
    if d == "pick":
        return f"take the {s['colour'] + ' ' if s['colour'] else ''}{s['object']}"
    if d == "receive" and s.get("wait_s"):
        return f"wait for someone to give me the {s['object'] or 'thing'} (up to {_dur(s['wait_s'])})"
    if d == "receive":
        return f"take the {s['object'] or 'thing'} from a person"
    if d == "say":
        return f'say "{s["text"]}"'
    if d == "place":
        return "put it down" if not s["on"] else f"put it on {_on_words(s['on'])}"
    if d == "give":
        return f"hand it to {s['person']}" if s.get("person") else "hand it over"
    if d == "hold":
        return "hold it"
    return {"reach": "reach out my arm", "fold": "fold my arm", "open": "open my hand", "close": "close my hand"}[s["pose"]]


def _ko(s, last=False):
    d = s["do"]
    if d == "wait":
        if s.get("until"):
            return f"최대 {_dur(s['s'], True)} 동안 거기서 지시를 기다리고"
        if s["s"] is None:
            return "거기서 기다리고" if last else "가도 된다고 할 때까지 거기서 기다리고"
        return f"{_dur(s['s'], True)} 기다리고"
    if d == "go":
        to = s["to"]
        if isinstance(to, list):
            return f"{', '.join(to)} 중 한 곳으로 가고"
        return "여기로 돌아오고" if to == "here" else "충전소로 가고" if to == "home" else f"{to} 위치로 가고"
    if d == "move":
        side = {"forward": "앞으로", "back": "뒤로", "left": "왼쪽으로", "right": "오른쪽으로"}[s["dir"]]
        return f"{side} {s['m']:g}미터 가고"
    if d == "turn":
        return "뒤로 돌고" if abs(s["deg"]) == 180 else ("왼쪽" if s["deg"] > 0 else "오른쪽") + "으로 돌고"
    if d == "pick":
        from tasks.fetch import OBJECTS as KO
        return f"{(brain_ko(s['colour']) + ' ') if s['colour'] else ''}{KO.get(s['object'], s['object'])}을 집고"
    if d == "receive" and s.get("wait_s"):
        from tasks.fetch import OBJECTS as KO
        return f"최대 {_dur(s['wait_s'], True)} 동안 누가 {KO.get(s['object'], '물건')}을 줄 때까지 기다렸다가 받고"
    if d == "receive":
        from tasks.fetch import OBJECTS as KO
        return f"사람에게서 {KO.get(s['object'], '물건')}을 받고"
    if d == "say":
        return f'"{s["text"]}"라고 말하고'
    if d == "place":
        return f"{_on_words(s['on'], True)}에 놓고"
    if d == "give":
        if s.get("person"):
            return f"{s['person']}께 건네드리고" if s["person"].endswith("님") else f"{s['person']}에게 건네주고"
        return "건네주고"
    if d == "hold":
        return "들고 있고"
    return {"reach": "팔을 뻗고", "fold": "팔을 접고", "open": "손을 펴고", "close": "손을 쥐고"}[s["pose"]]


def _will(stem):
    """Korean '-ㄹ게요' on a verb stem: 가 -> 갈게요, 집 -> 집을게요, 돌 -> 돌게요."""
    code = ord(stem[-1]) - 0xAC00
    if not 0 <= code < 11172:
        return stem + "게요"
    final = code % 28
    if final == 0:
        return stem[:-1] + chr(ord(stem[-1]) + 8) + "게요"     # + ㄹ
    return stem + ("게요" if final == 8 else "을게요")


def describe(steps, lang="en"):
    """'Take the cup, drive 0.5 m forward, turn right and drive 1 m, then put it on the table.'"""
    if not steps:
        return ""
    if lang == "ko":
        parts = [_ko(s, i == len(steps) - 1) for i, s in enumerate(steps)]
        return " ".join(parts[:-1] + [_will(parts[-1][:-1]) + "."])
    parts = [_en(s, i == len(steps) - 1) for i, s in enumerate(steps)]
    text = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + ", then " + parts[-1]
    return text[0].upper() + text[1:] + "."


if __name__ == "__main__":
    from robot import agv
    s, u, by = read(" ".join(sys.argv[1:]), agv.markers())
    print(s, "\nunread:", u, "\n", describe(s), "\n", describe(s, "ko"), "\n", check(s, False, agv.markers()))
