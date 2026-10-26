"""Short drives and the drive speed as people say them, in English, Korean and mixed, with whisper's slips.

    which way and how far: "come back 20 cm", "move back 5 centimeters", "20센티 뒤로", "앞으로 반 미터",
        "back up a tiny bit", "a hair to the left", "살짝 뒤로", "한 뼘 앞으로", "two steps back", "반 걸음 뒤로"
    faster / slower: "a little faster", "can you pick up the pace", "not so fast", "ease off", "slow it down a notch",
        "way too slow", "너무 빨라", "좀 천천히 가 줄래요", "속도 줄여"
    after one of them: "more", "again", "a bit more", "same again", "조금 더", "한 번 더", "just a few centimetres more"

Reads text normalised by brain._norm (wording.norm: "20 cm" -> "0.2 m", "이십 센티" -> "0.2 m", "two" -> "2").
Nothing is guessed: a number said without a unit that is read is asked about, a drive past MOVE_MAX_M is refused
with the limit, "more" with nothing before it is asked about.

    python assistant/driving.py "back up a tiny bit"
"""
import re
import sys

MOVE_MAX_M = 3.0             # m; the longest short drive (lumi.MAX_MOVE_M); longer is refused with this limit
MOVE_MIN_M = 0.01            # m; a shorter drive is refused
DEFAULT_M = 1.0              # m; "move back" with no amount (as before)
LITTLE_M = 0.5               # m; "a little", "a bit", "조금", "좀" (as before)
TINY_M = 0.05                # m; "a tiny bit", "a hair", "a few centimetres", "살짝"; estimate
SPAN_M = 0.2                 # m; "한 뼘", one hand span; estimate
STEP_M = 0.5                 # m; one step ("two steps", "한 걸음", "반 걸음"); estimate of a person's step
TURN_MORE_DEG = 15.0         # deg; "a bit more" right after a turn: this much further the same way

DIRS = (("back", r"\bback(?:wards?)?\b(?! down\b)|\bbackward\b|\breverse\b|^(?:let'?s )?(?:bake|big)\b(?= \d| half| a )|뒤로|뒤쪽|후진|"
                 r"물러"),                                    # whisper's "let's bake / big one meter"
        ("forward", r"\bforwards?\b|\bahead\b|앞으로|앞쪽|전진"),
        ("left", r"\b(?:to the |to your )?left\b|왼쪽|좌측"),
        ("right", r"(?<!all )\b(?:to the |to your )?right\b(?! now| away| here| there| back)|오른쪽|우측"))
VERB = re.compile(r"\b(?:move|go|come|drive|step|scoot|scooch|shift|inch|roll|back (?:up|off)|reverse|get)\b|"
                  r"가|와|이동|움직|물러|빠져|후진|전진|비켜")
NEAR_THING = re.compile(r"(?:테이블|책상|탁자|의자|소파|문|벽|창문)\s*(?:앞|옆|뒤)|"
                        r"(?<![가-힣])(?!(?:루미야?|조금만?|살짝|다시|그냥|이제|저기요?|여기|거기|약간|천천히|빨리|얼른|어서|그럼|근데|"
                        r"그리고|좀|더|한|두|세|반|쭉|바로|똑바로|계속|한번|한 번|일단|먼저|자|아주|많이|쪼끔|쬐끔|요만큼|뼘|걸음|발짝|발자국|미터|센티|센치|밀리)만?(?:\s|$))(?:[가-힣][가-힣_]{0,9}|(?<![a-z0-9_.])(?!(?:m|cm|mm|lumi|loomi|rumi|hey|ok|okay|please)\b)[a-z][a-z0-9_]*)\s*"
                        r"(?:앞|옆|뒤)(?:으?로|쪽|에)")   # "테이블 앞으로", "무대 앞으로 가": to that thing or place, not forward
OTHER = re.compile(r"\b(?:look|head|turn|spin|rotate|face|arm|hand|lift|raise|lower|it|this|that|them|those|these|here|there|"
                   r"home|me|us)\b|\bthe (?!left\b|right\b)|\bgo (?:right )?ahead\b|\bback to (?![\d.])|\b[a-z]+\d+\b|\b[a-z]+(?:_[a-z0-9]+)+\b|고개|머리|팔|손|돌아|돌려|봐|보(?:세요|십시오|시오|실래요|자|라|아|여)|볼래|쳐다|들어|올려|내려|"
                   r"여기|저기|이리|집|\S(?:을|를)(?=\s)|도십시오|도세요|회전|\d+(?:\.\d+)? ?도(?:만|쯤|정도|가량)?(?=\s|$)|" + NEAR_THING.pattern)
                                                    # the head, an object, a place
                                                    # (p3, dock2, booth_9: a marker as written): not a short drive
SAYER = re.compile(r"\b(?:i|i'm|im|i'll|i've|we|we're|he|she|they|there|it's|it is|my|our|his|her|their|was|were|"
                   r"if|when)\b|(?:^|\s)(?:나|저|우리|저희)(?:는|도|가)\s")   # "I live a few metres to the left"
_NATIVE = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
           "a": 1, "an": 1, "half": 0.5, "반": 0.5}
_COUNT = rf"(\d+(?:\.\d+)?|{'|'.join(_NATIVE)})\s*(?:a\s+)?"
STEPS = re.compile(rf"(?:(?<![\w.]){_COUNT}\s*)?(?:steps?|paces?|걸음|발짝|발자국)(?![a-z])")
SPANS = re.compile(rf"(?:(?<![\w.]){_COUNT}\s*)?뼘")
TINY = re.compile(r"\b(?:tiny|teeny|wee|hair|hairs?breadth|smidge|smidgen|tad|touch|nudge|slightly|little tiny)\b|"
                  r"\bfew (?:centimet(?:er|re)s|cm)\b|\binch (?:forward|back|left|right|ahead)|"
                  r"살짝|아주 조금|쪼끔|쬐끔|약간|요만큼|조금만 살짝")
LITTLE = re.compile(r"\b(?:a little|a bit|little bit|bit)\b|조금|쪼금")   # "좀" is "please" as often as "a bit"
VAGUE = re.compile(r"\b(?:more|less|longer|further|farther|bit more|bit less) than\b|(?:^|\s)몇\s*(?:미터|센티|m\b|걸음)|\bsome (?:meters?|metres?)\b|\bto (?:m|meters?|metres?)\b|"
                   r"\b(?:some|like|uh|um)\s*$|(?<![가-힣])[이삼사오육칠팔구]?[십백][일이삼사오육칠팔구]?\s*(?:만\s*)?"
                   r"(?:가|와|이동|움직|후진|전진)")   # an amount half said: asked, never a guess
NUM_WORD = re.compile(r"\b(?:eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
                      r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|dozen|couple|several|few|half)\b")
KO_NUM_WORD = re.compile(r"(?<![가-힣])(?:하나|둘|셋|넷|다섯|여섯|일곱|여덟|아홉|열|스물|서른|마흔|쉰)(?:만|쯤|정도)?(?![가-힣])")
                                                    # "앞으로 다섯만 가": a count with no unit, asked
KO_COUNT = re.compile(KO_NUM_WORD.pattern + r"|(?<![가-힣])[이삼사오육칠팔구]?[십백][일이삼사오육칠팔구]?(?:만|쯤|정도)?(?![가-힣])|"
                      r"(?<![\w.])\d+(?:\.\d+)?(?![\d.])(?!\s?(?:m|도|degrees?|°)(?![a-z]))")   # a number with no unit
WRONG_UNIT = (re.compile(r"(?<![\w.])\d+(?:\.\d+)? ?(?:도|degrees?)(?:만|쯤|정도|가량)?(?![가-힣a-z])"),       # degrees for a drive
              re.compile(r"(?<![\w.])\d+(?:\.\d+)? m(?![a-z])"))                        # metres for a turn
TURN_WORD = re.compile(r"\b(?:turn|spin|rotate|pivot)\b|돌아|돌려|돌(?:까|래|면)|회전|도세요|도십시오")
NOT_BASE = re.compile(r"\b(?:look|head|face|lift|arm)\b|고개|머리|얼굴|봐|보세요|리프트|팔|손")

FASTER = re.compile(r"\b(?:faster|quicker|speed (?:it )?up|pick up (?:the )?(?:pace|speed)|step on it|hurry(?: up)?|"
                    r"get a move on|more speed|full speed|go quick(?:ly)?|too slow(?:ly)?|so slow(?:ly)?|"
                    r"not fast enough|move it)\b|빨리|빠르게|(?:속도|speed)\s*(?:를|좀)?\s*(?:좀\s*)?(?:높|올)\S*|느려|느리다|서둘러")
SLOWER = re.compile(r"\b(?:slower|slow (?:it )?down|slow|ease (?:off|up)|not so fast|too fast|"
                    r"so fast|less speed|gently|more slowly|slowly)\b|"
                    r"천천히|느리게|(?:속도|speed)\s*(?:를|좀)?\s*(?:좀\s*)?(?:줄|낮|늦)\S*|빨라|빠르다|살살")
_FILLER = (r"please|pls|lumi|hey|hi|okay|ok|so|um+|uh+|well|now|then|just|can|could|would|will|you|you're|youre|"
           r"are|is|going|moving|driving|go|drive|move|"
           r"keep|going|get|it|the|a|an|bit|little|tiny|notch|touch|tad|lot|much|way|even|bit|slightly|somewhat|"
           r"more|than|that|this|let's|lets|try|be|bit\.|maybe|yeah|yes|alright|right|bro|man|too|really|"
           r"루미야|루미|좀|조금|조금만|더|약간|살짝|이제|그냥|너무|가|가줘|가 ?줘|가요|가세요|줘|주세요|줄래|줄래요|"
           r"줄래\?|주실래요|주시겠어요|해|해줘|해요|해 ?줘|움직여|요|좀더|조금더|자|볼래|봐|볼까|좀만|해봐")
FILL = re.compile(rf"(?:^|\s)(?:{_FILLER})(?=\s|$)")
AGAIN = re.compile(r"^(?:(?:just|a|an|bit|little|tiny|some|even|one|1|once|the|same|do|it|that|go|please|lumi|ok|"
                   r"okay|yeah|yes|and|then|now)\s+)*(?:more|again|once more|one more time|same again|"
                   r"the same again|more please|again please|1 more time)(?:\s+(?:please|lumi|then))?$|"
                   r"^(?:루미야\s+)?(?:조금만?|좀|살짝|약간|한 ?번|1 ?번|아까처럼|똑같이)?\s*더"
                   r"(?:\s*(?:가|해|가 ?줘|해 ?줘|가요|해요|가 ?주세요|해 ?주세요))?$|^한 ?번 ?더|^똑같이(?: 해| 한 ?번)?")
LESS = re.compile(r"^(?:(?:a|bit|little|just|a little|a bit)\s+)*less(?: please)?$|^(?:좀|조금)?\s*덜$")
JOINED = re.compile(r"\b(?:and|then|after that|and then)\b|그리고|하고|해서|가서|다음에|집어|가져")


def clean(t):
    return re.sub(r"\s+", " ", re.sub(r"[,!?~…]+|(?<!\d)\.|\.(?!\d)", " ", (t or "").lower())).strip()


def direction(t):
    """The way said; "not left. right." is right (a direction said with "not" is not meant)."""
    t = re.sub(r"\bnot (?:to the |to your )?(?:left|right|forward|back(?:wards?)?)\b|(?:왼쪽|오른쪽|앞|뒤)(?:으로|쪽)? ?말고", " ", t)
    found = [(m.start(), d) for d, rx in DIRS for m in [re.search(rx, t)] if m]
    return min(found)[1] if found else None


def amount(t):
    """(metres, exact) said in normalised text: exact for a number with a unit ("0.2 m"), else the estimate a vague
    word stands for; (None, False) when no amount is said; ("?", False) for a number without a unit that is read."""
    if re.search(r"\bquarter of (?:a |an |1 |one )?(?:m|meters?|metres?)\b", t):
        return 0.25, True                                    # "a quarter of a meter"
    if VAGUE.search(t):
        return "?", False                                    # "more than a meter", "to meters" (two?), "move back some"
    m = re.search(r"(?<![\w.])(\d+(?:\.\d+)?) m(?![a-z])", t)
    if m:
        return float(m.group(1)), True
    if TINY.search(t):
        return TINY_M, False
    for rx, unit in ((STEPS, STEP_M), (SPANS, SPAN_M)):
        m = rx.search(t)
        if m and not re.search(r"\b(?:few|couple|several|some)\b", t):
            n = m.group(1)
            return (float(n) if n and n[0].isdigit() else _NATIVE.get(n, 1)) * unit, False
    if re.search(r"(?<![\w.])\d", t) or NUM_WORD.search(t) or KO_NUM_WORD.search(t):
        return "?", False                                    # "move back 20", "two feet", "a couple of metres"
    if LITTLE.search(t):
        return LITTLE_M, False
    return None, False


def move(t, verb_needed=True):
    """(direction, metres | "?", exact) for one short drive in normalised text, or None. Without a drive verb an
    amount must be said ("a hair to the left", "살짝 뒤로"); a sentence about someone else is not a drive."""
    t = clean(t)
    d = direction(t)
    if d is None or JOINED.search(t) or SAYER.search(t) or OTHER.search(t):
        return None
    n, exact = amount(t)
    if verb_needed and n is None and not VERB.search(t):
        return None
    if n is None:
        n = DEFAULT_M
    return d, n, exact


def speed(t):
    """+1 (faster) / -1 (slower) when the whole sentence asks for a speed change, else 0."""
    t = clean(t)
    too = re.search(r"\b(?:too|so|way too) (fast|slow)\b|(?:너무|넘) ?(빨라|느려)", t)
    if too:
        sign = -1 if too.group(1) == "fast" or too.group(2) == "빨라" else 1
    else:
        fast, slow = FASTER.search(t), SLOWER.search(t)
        if bool(fast) == bool(slow):
            return 0
        sign = 1 if fast else -1
    rest = FILL.sub(" ", FILL.sub(" ", SLOWER.sub(" ", FASTER.sub(" ", t))))
    rest = re.sub(r"\b(?:too|so|way|fast|slow|the pace|pace|speed|down|it)\b|(?:^|\s)(?:속도|를)(?=\s|$)", " ", rest)
    return sign if not rest.strip() else 0


def read(t, last=None, talking=False):
    """What a sentence asks of the base, or None (not about driving):
    ("move", "back 0.2", exact) | ("turn", "left 90") | ("speed", +1 | -1) | ("refuse", "back 5") | ("ask", "back" | "")
    | ("look" / "lift", "left small"): "one more" after a look or a lift.
    `last` is the move / speed just before (last_command(history)): "more" / "again" repeat it. With none and
    `talking` (the turn before was conversation) "more" is left to the conversation, else it is asked about."""
    asked = "?" in (t or "") and not re.search(r"\b(?:can|could|would|will) you\b|\bplease\b|줄래|주세요|줘", t or "")
    t = clean(t)
    s = 0 if asked else speed(t)                             # "really? that slow?": a reaction, not an order
    if s:
        return ("speed", s)
    if AGAIN.search(t) or LESS.search(t):
        if last is None:
            return None if talking else ("ask", "")          # "more" of what?
        if LESS.search(t):
            return ("speed", -1) if last[0] == "speed" else None
        if last[0] == "turn" and re.search(r"\b(?:more|bit|little)\b|조금|좀|살짝|약간", t) and \
                not re.search(r"\bagain\b|한 ?번|똑같이|아까처럼|(?:one|1) more time|once more", t):
            side = last[1].split()[0]                        # "a bit more" after "turn left": a little further
            return ("turn", f"{side} {TURN_MORE_DEG:g}") if side in ("left", "right") else ("ask", "")
        return last
    if last and last[0] == "lift":                           # "too high, go back down", "now back up": the lift
        m = re.search(r"\bback (up|down)\b|^(?:(?:now|and|then|ok|okay) )*(up|down)(?: (?:again|please))?$", t)
        if m:
            return ("lift", m.group(1) or m.group(2))
    if last and last[0] == "move" and re.search(r"\bmore\b|더", t) and direction(t) is None and not JOINED.search(t):
        n, exact = amount(t)                                 # "just a few centimetres more", "10센티 더"
        if n is not None:
            return _checked(last[1].split()[0], n, exact)
    d = direction(t)
    if d and not (JOINED.search(t) or SAYER.search(t) or NOT_BASE.search(t)):
        if WRONG_UNIT[0].search(t) and VERB.search(t) and not TURN_WORD.search(t):
            return ("ask", d)                                # "앞으로 30도 가": degrees for a drive
        if WRONG_UNIT[1].search(t) and TURN_WORD.search(t) and d in ("left", "right") and not VERB.search(TURN_WORD.sub(" ", t)):
            return ("ask", f"turn {d}")                      # "왼쪽으로 1미터 돌아": metres for a turn
        if TURN_WORD.search(t) and d in ("left", "right") and re.search(r"[가-힣]", t) and \
                not WRONG_UNIT[0].search(t) and KO_COUNT.search(t):
            return ("ask", f"turn {d}")                      # "왼쪽으로 서른만 돌아", "왼쪽으로 30 돌아": degrees?
    got = move(t)
    return _checked(*got) if got else None


def _checked(d, n, exact):
    if n == "?":
        return ("ask", d)
    if n > MOVE_MAX_M or n < MOVE_MIN_M:
        return ("refuse", f"{d} {n:g}")
    return ("move", f"{d} {n:g}", exact)


def last_command(history):
    """The move, turn, speed change, look or lift of the turn just before, from brain history ("ACTION: move back
    0.2", "ACTION: look left" -> ("look", "left small")), else None."""
    if not history:
        return None
    m = re.match(r"ACTION: (look|lift) (left|right|up|down)\b", history[-1][1] or "")
    if m:                                                    # "look left" then "one more": a little further that way
        return (m.group(1), f"{m.group(2)} small")
    m = re.match(r"ACTION: (move|speed|turn) (\S+)(?: (\S+))?", history[-1][1] or "")
    if not m:
        return None
    if m.group(1) == "turn":                                 # "turn left" then "again": the same turn
        return ("turn", "around 180" if m.group(2) == "around" else f"{m.group(2)} {m.group(3) or 90}")
    if m.group(1) == "speed":
        return ("speed", {"faster": 1, "slower": -1}.get(m.group(2)) or int(m.group(2)))
    return ("move", f"{m.group(2)} {m.group(3)}", True) if m.group(3) else None


def talking(history):
    """The turn before was conversation (not a command): a bare "more" belongs to it."""
    return bool(history) and bool(re.match(r"ACTION: none\b|(?!ACTION:)", history[-1][1] or ""))


def spoken(m, lang="en"):
    """0.2 -> "20 centimetres" / "20센티", 1.5 -> "1.5 metres" / "1.5미터"."""
    if m >= 1:
        return f"{m:g} metre{'' if m == 1 else 's'}" if lang == "en" else f"{m:g}미터"
    if m >= 0.01:
        cm = round(m * 100, 1)
        return f"{cm:g} centimetre{'' if cm == 1 else 's'}" if lang == "en" else f"{cm:g}센티"
    return f"{m * 1000:g} millimetres" if lang == "en" else f"{m * 1000:g}밀리"


KO_DIR = {"forward": "앞으로", "back": "뒤로", "left": "왼쪽으로", "right": "오른쪽으로"}


def say_move(d, m, exact, lang="en"):
    """The read-back of a drive; "about" when the amount was not said exactly."""
    if lang == "en":
        return f"Okay, moving {d} {'' if exact else 'about '}{spoken(m)}."
    return f"네, {KO_DIR.get(d, '')} {'' if exact else '약 '}{spoken(m, 'ko')} 갈게요."


def say_refused(d, n, lang="en"):
    if n < MOVE_MIN_M:
        return ("Sorry, that's too short for me to drive." if lang == "en" else "죄송해요, 너무 짧아서 갈 수 없어요.")
    return (f"Sorry, I can only drive up to {spoken(MOVE_MAX_M)} at a time." if lang == "en"
            else f"죄송해요, 한 번에 {spoken(MOVE_MAX_M, 'ko')}까지만 갈 수 있어요.")


def say_ask(d, lang="en"):
    if d.startswith("turn "):
        d = d.split()[1]
        return (f"How far should I turn {d}? Please say it in degrees, like 30 degrees." if lang == "en"
                else f"{KO_DIR.get(d, '')} 몇 도 돌까요? 30도처럼 말씀해 주세요.")
    if not d:
        return ("More of what? Please tell me what to do." if lang == "en" else "무엇을 더 할까요? 다시 말씀해 주세요.")
    return (f"How far should I go {d}? Please say it with a unit, like 20 centimetres." if lang == "en"
            else f"{KO_DIR.get(d, '')} 얼마나 갈까요? 20센티처럼 단위와 함께 말씀해 주세요.")


def say_speed(sign, factor, changed, lang="en"):
    """The answer to a speed change: the new speed in plain words."""
    pct = round(factor * 100)
    if not changed:
        return (("I'm already at my top speed." if sign > 0 else "I'm already at my slowest.") if lang == "en"
                else ("이미 가장 빠른 속도예요." if sign > 0 else "이미 가장 느린 속도예요."))
    if pct == 100:
        return "Okay, back to my normal speed." if lang == "en" else "네, 보통 속도로 갈게요."
    if lang == "en":
        return f"Okay, a bit {'faster' if sign > 0 else 'slower'}: {pct} percent of my normal speed."
    return f"네, 조금 더 {'빨리' if sign > 0 else '천천히'} 갈게요. 보통 속도의 {pct}퍼센트예요."


if __name__ == "__main__":
    from assistant import brain
    print(read(brain._norm(" ".join(sys.argv[1:]))))
