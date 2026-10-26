"""Marker names and numbers as people say them (English, Korean, mixed, and as whisper writes them) -> the written
form the readers use. brain (keyword rules, fetch, named_place) and steps (missions, the LLM check) both read
through norm(), so a place or a number is read the same way everywhere.

    "피쓰리로 가 줘", "피 삼으로", "포인트 쓰리", "삼 번 포인트", "point three", "P.3", "피3"  -> "p3"
    "파이널로" -> "final로"     "도크 투", "dock two" -> "dock2"     "엑시트" -> "exit"     "홈으로" -> "home으로"
    "일 미터 반", "1미터 50센치", "one and a half meters" -> "1.5 m"     "오십 센치", "half a meter" -> "0.5 m"
Only clear forms are changed: "피로 가" (no number), "PE로", "피자", "이번에" stay as they are, and Lumi asks.
With the map's marker names (norm(text, names)) any name is read as said: "table front" / "테이블 프론트" ->
"table_front", "booth two" / "부스 투" -> "booth_2", "스타트로" -> "start로", and a word after "to" / "from" one
letter off one name only ("go to the stagee") -> that name.

    python assistant/wording.py "피쓰리로 가서 일 미터 앞으로 가"
"""
import difflib
import re
import sys

EN_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
          "ten": 10, "eleven": 11, "twelve": 12}
KO_EN_NUM = {"원": 1, "투": 2, "쓰리": 3, "스리": 3, "뜨리": 3, "트리": 3, "포": 4, "파이브": 5, "화이브": 5,
             "식스": 6, "씩스": 6, "세븐": 7, "쎄븐": 7, "에잇": 8, "에이트": 8, "나인": 9, "텐": 10, "일레븐": 11,
             "트웰브": 12}                                 # English numbers said in Korean ("피쓰리", "포인트 원")
NATIVE = {"한": 1, "두": 2, "세": 3, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
SINO = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "륙": 6, "칠": 7, "팔": 8, "구": 9}
_D = "[일이삼사오육륙칠팔구]"
_SINO = rf"(?:{_D}?천(?:{_D}?백)?(?:{_D}?십)?{_D}?|(?:{_D}?백)(?:{_D}?십)?{_D}?|{_D}?십{_D}?|{_D})"   # 일 … 구천구백구십구
NATIVE_TENS = {"열": 10, "스물": 20, "스무": 20, "서른": 30, "마흔": 40, "쉰": 50, "예순": 60, "일흔": 70, "여든": 80, "아흔": 90}
NATIVE_ONES = {"하나": 1, "한": 1, "둘": 2, "두": 2, "셋": 3, "세": 3, "넷": 4, "네": 4, "다섯": 5, "여섯": 6, "일곱": 7,
               "여덟": 8, "아홉": 9}
_NATIVE_NUM = (rf"(?:({'|'.join(NATIVE_TENS)})\s?({'|'.join(NATIVE_ONES)})?|(다섯|여섯|일곱|여덟|아홉))")   # 한 / 두 / 세 /
                                                    # 네 alone: NUM_WORDS (before a unit only; "한 도" is no angle)
_ABOUT = r"(?:만|쯤|정도|가량|씩)?"                  # "45도만", "30도쯤": still that amount
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
NUM_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
             "nine": "9", "ten": "10", "a": "1", "an": "1", "한": "1", "두": "2", "세": "3", "네": "4"}
UNIT = (r"(?:m|meters?|metres?|metals?|cm|centimet(?:er|re)s?|mm|millimet(?:er|re)s?|km|kilomet(?:er|re)s?|miles?|"
        r"미터|센티(?:미터)?|센치(?:미터)?|밀리(?:미터)?|킬로(?:미터)?(?!그램)|마일)")   # whisper writes "metal" for meter
_CM = r"(?:cm|centimet(?:er|re)s?|센티(?:미터)?|센치(?:미터)?)"
# what may follow a number said in Korean words for it to be a marker: a particle, a place word, or no more Hangul
# ("피삼으로", "피파이브 앞에", "피일에서"; not "피투성이", "피오나")
_KO_END = (r"(?=(?:(?:으로|로|에서|에게|에다|에|까지|부터|중에서|중에|중|또는|번|이|가|은|는|도|랑|이랑|하고|의|한테)(?![가-힣])"
           r"|(?:으로|로|에)(?=가|와|돌아|이동|갔)|(?:이나|나)(?=\s|$)|(?:앞|뒤|옆|위|쪽|근처))|(?![가-힣]))")
_P = r"(?:(?<![가-힣])피|\bp|포인트|마커|\bpoint|\bmarker)"     # what is said before a marker's number
NAMED = [   # other markers on the map, as said / as whisper writes them -> the name
    (r"(?:파이[널날]|화이[널날])(?:\s*포인트)?|파이너(?=로|에)", "final"),
    (r"\bdo(?:ck|c|k)\s*-?\s*(?:2|two)(?![a-z0-9])|\bdock(?:y|u|ie)\s?2\b|(?:도크|독|닥)\s*(?:2|투|트)" + _KO_END, "dock2"),
    (r"(?:엑시트|엑싯|엑짓|엑지트|에그짓|이그짓)", "exit"),
    (r"(?<![가-힣])피트(?=으로|로|에서|까지|\s*앞)", "p2"),         # whisper writes 피투 as 피트 ("피트로 가서")
    (r"\b(?:p\.?\s?o\.?|pio)(?=\s*(?:으로|로|에서|에|까지))", "p5"),   # 피오 as letters ("PO에서", "P.O.로")
    (r"\bp[\s.-]?init(?![a-z])|피\s?이?닛|피\s?이?니트", "pinit"),
    (r"\bw[\s.-]p\b|더블[유류]\s?피" + _KO_END, "wp"),
    (r"(?<![가-힣])홈" + _KO_END, "home"),
    (r"(?:포인트|마커)\s*(?:에이|a)(?![a-z])" + _KO_END, "point a"), (r"(?:포인트|마커)\s*(?:비|b)(?![a-z])" + _KO_END, "point b"),
    (r"(?<![가-힣])(?:에이|a)\s*지점", "point a"), (r"(?<![가-힣])(?:비|b)\s*지점", "point b"),   # "에이 지점으로 가"
]

# English words of marker names as people say them in Korean: plain transliterations only, never a translation
KO_SPOKEN = {"start": ["스타트"], "end": ["엔드"], "final": ["파이널", "화이널"], "middle": ["미들"], "home": ["홈"],
             "stage": ["스테이지"], "booth": ["부스"], "table": ["테이블"], "front": ["프론트", "프런트"],
             "init": ["이닛", "이니트"], "exit": ["엑시트", "엑싯"], "dock": ["도크"], "point": ["포인트"],
             "coffee": ["커피"], "corner": ["코너"], "info": ["인포"], "desk": ["데스크"], "gate": ["게이트"],
             "hall": ["홀"], "zone": ["존"], "photo": ["포토"], "lounge": ["라운지"], "lobby": ["로비"], "room": ["룸"],
             "demo": ["데모"], "bar": ["바"], "main": ["메인"], "cafe": ["카페"], "area": ["에어리어"], "center": ["센터"],
             "entrance": ["엔트런스"], "finish": ["피니시", "피니쉬"], "lab": ["랩"], "office": ["오피스"],
             "a": ["에이"], "b": ["비"], "c": ["씨"], "d": ["디"]}   # letters only inside a longer name ("부스 에이")
KO_NOT_ALONE = {"table", "point", "a", "b", "c", "d"}   # "테이블에 놔" is the table, "포인트" a p-number, "비" rain:
                                                    # the Korean form only inside a longer name
NOT_SLIPS = {"point", "marker", "here", "there", "me", "home", "table", "left", "right", "back", "front", "it", "them"}
CLOSE = 0.8                           # difflib ratio for a whisper slip of a marker name ("stagee" -> stage)


def sino(word):
    """'사십오' -> 45, '백팔십' -> 180, '십' -> 10."""
    n, part = 0, 0
    for ch in word:
        if ch in SINO:
            part = SINO[ch]
        else:
            n += (part or 1) * {"십": 10, "백": 100, "천": 1000}[ch]
            part = 0
    return n + part


def _num(word):
    return EN_NUM.get(word) or KO_EN_NUM.get(word) or (int(word) if word.isdigit() else sino(word))


def markers(t):
    """Marker names in lower-case text -> "p3", "final", "dock2", "exit", "pinit", "wp", "home", "point a"."""
    ko = "|".join(sorted(KO_EN_NUM, key=len, reverse=True))
    t = re.sub(rf"(?<![\w.])({_SINO}|\d+|{'|'.join(NATIVE)})\s*번\s*(?:포인트|마커|point|marker)",  # "3번 포인트",
               lambda m: f"p{NATIVE.get(m.group(1)) or _num(m.group(1))}", t)                  # "삼 번", "세 번 포인트"
    t = re.sub(rf"(?:포인트|마커|point|marker)\s*({_SINO}|\d+)\s*번", lambda m: f"p{_num(m.group(1))}", t)
    t = re.sub(rf"(?<![가-힣])({_SINO})\s*번(?=\s*(?:으로|로|에서|에|까지))",             # "삼 번으로" -> "3번으로"
               lambda m: m.group(0) if m.group(0) == "이번" and t[m.end():m.end() + 1] == "에"   # "이번에": this time
               else f"{sino(m.group(1))}번", t)
    for name_re, name in NAMED:
        t = re.sub(name_re, name, t)
    t = re.sub(rf"{_P}\s*[.-]?\s*(\d+)(?!\d|\.\d)", lambda m: f"p{m.group(1)}", t)       # "P.3", "p 3", "피3", "포인트 3"
    t = re.sub(r"(?<![\w.])(\d+)\s?(?:p(?:\s+(?:point|포인트))?|point|포인트)(?![a-z\d])(?!\s*\d)",   # "10p point",
               lambda m: f"p{m.group(1)}", t)                                            # "10p", "10 point"
    t = re.sub(rf"(?<!\d )(?<![a-z] point ){_P}\s*[.-]?\s*({'|'.join(EN_NUM)})(?![a-z])(?!\s*{UNIT}\b)",
               lambda m: f"p{EN_NUM[m.group(1)]}", t)                                    # "point three", "p two"
    t = re.sub(rf"{_P}\s*({ko}|{_SINO}){_KO_END}", lambda m: f"p{_num(m.group(1))}", t)  # "피쓰리", "포인트 삼"
    t = re.sub(rf"\b(to|from|at|go) (the )?(?:piece|peace|pee|pea|pit|pi|pe) ?(\d+|{'|'.join(EN_NUM)})\b",  # whisper's
               lambda m: f"{m.group(1)} {m.group(2) or ''}p{_num(m.group(3))}", t)                    # "go to piece six"
    t = re.sub(r"\b(p\d+)\s+(?:point|포인트)(?![a-z])(?!\s*(?:a|b|\d)(?![a-z]))", r"\1", t)   # "p10 point"
    return t


def numbers(t):
    """Distances and angles in lower-case text -> digits and metres: "half a meter" -> "0.5 m", "오십 센치" -> "0.5 m",
    "일 미터 반" -> "1.5 m", "구십 도" -> "90도"."""
    t = re.sub(r"\bone and a half\b", "1.5", t)
    t = re.sub(rf"\b({'|'.join(TENS)})(?:[ -]({'|'.join(list(EN_NUM)[:9])}))?\b",
               lambda m: str(TENS[m.group(1)] + EN_NUM.get(m.group(2), 0)), t)
    t = re.sub(rf"\b(?:a|one|1) thousand\b|\b(\d+|{'|'.join(EN_NUM)}) thousand\b",
               lambda m: str(1000 * _num(m.group(1)) if m.group(1) else 1000), t)     # "a thousand", "five thousand"
    t = re.sub(rf"\b([2-9]|{'|'.join(list(EN_NUM)[1:9])}) hundred(?: and)?(?: (\d+))?\b",
               lambda m: str(100 * _num(m.group(1)) + int(m.group(2) or 0)), t)       # "two hundred and fifty"
    t = re.sub(rf"\b({'|'.join(TEEN)}|eleven|twelve)\b(?=\s*{UNIT}(?![a-z]))",
               lambda m: str(TEEN.get(m.group(1)) or EN_NUM[m.group(1)]), t)          # "fifteen centimetres"
    t = re.sub(r"\b(?:a|one) hundred(?: and)? (\d+)\b", lambda m: str(100 + int(m.group(1))), t)
    t = re.sub(r"\b(?:a|one) hundred\b", "100", t)
    t = re.sub(rf"(?<![\w.])(\d|{'|'.join(list(EN_NUM)[:9])}) point (\d|{'|'.join(list(EN_NUM)[:9])})\s*(?={UNIT}\b)",
               lambda m: f"{_num(m.group(1))}.{_num(m.group(2))} ", t)                   # "one point five meters"
    t = re.sub(rf"\b(?:zero |oh )?point ({'|'.join(list(EN_NUM)[:9])}|\d)\s*(?={UNIT}\b)",
               lambda m: f"0.{_num(m.group(1))} ", t)                                    # "point five meters"
    t = re.sub(rf"(?<![가-힣\d])({_SINO}(?:\s{_SINO})+)(?=\s*(?:{UNIT}|도|걸음|점))",       # "사 십오 도", "삼백 육십 도":
               lambda m: m.group(1).replace(" ", "") if re.fullmatch(_SINO, m.group(1).replace(" ", "")) else m.group(1),
               t)                                                                        # one number said apart
    t = re.sub(rf"(?<![가-힣]){_NATIVE_NUM}\s*(?={UNIT}|걸음|발짝|발자국|뼘|도{_ABOUT}(?![가-힣]))",   # "마흔다섯 도", "스무 센티"
               lambda m: f"{NATIVE_TENS.get(m.group(1), 0) + NATIVE_ONES.get(m.group(2) or m.group(3), 0)} ", t)
    t = re.sub(rf"(?<![가-힣\d])({_SINO})\s*도(?={_ABOUT}(?![가-힣]))",                         # "사십오 도만", "백팔십 도"
               lambda m: f"{sino(m.group(1))}도" if len(m.group(1)) > 1 or m.group(1) in "십백" else m.group(0), t)
    t = re.sub(rf"(?<![가-힣])(?:({_SINO})|[영공])\s*점\s*({_D})\s*(?={UNIT})",
               lambda m: f"{sino(m.group(1)) if m.group(1) else 0}.{SINO[m.group(2)]} ", t)  # "영점오 미터", "일 점 오"
    t = re.sub(rf"(?<![가-힣\d])({_SINO})\s*(?={UNIT}(?![a-z]))", lambda m: f"{sino(m.group(1))} ", t)   # "오십 센치"
    t = re.sub(rf"(?:(?<=으로)|(?<=로))\s*({_SINO})\s*도(?![가-힣])", lambda m: f" {sino(m.group(1))}도", t)
    t = re.sub(rf"(?<![가-힣\d])({_SINO})\s*도(?=\s+(?:왼쪽|오른쪽|뒤로|돌))", lambda m: f"{sino(m.group(1))}도", t)
    t = re.sub(r"(\d+)\s*degrees?(?=\s*[가-힣])", r"\1도", t)                 # "왼쪽으로 45 degrees 돌아"
    t = re.sub(rf"\bhalf (?:a |an )?{UNIT}", "0.5 m", t)
    t = re.sub(rf"반\s*{UNIT}", "0.5 m", t)
    for w, d in NUM_WORDS.items():
        if w.isascii():
            t = re.sub(rf"\b{w}\b(?=\s*(?:{UNIT}(?![a-z])|degrees?|and a (?:half|0\.5)))", d, t)   # "one meter", "a meter"
        else:
            t = re.sub(rf"(?<![가-힣]){w}\s*(?={UNIT})", d + " ", t)
    t = re.sub(rf"(?<![\d.])0(\d)\s*(?={UNIT}(?![a-z]))", r"0.\1 ", t)      # whisper's "05 meters": 0.5 m
    t = re.sub(rf"(\d+(?:\.\d+)?)\s*{_CM}(?![a-z])", lambda m: f"{float(m.group(1)) / 100:g} m", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:mm|millimet(?:er|re)s?|밀리(?:미터)?)(?![a-z])",
               lambda m: f"{float(m.group(1)) / 1000:g} m", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:km|kilomet(?:er|re)s?|킬로(?:미터)?(?!그램))(?![a-z])",
               lambda m: f"{float(m.group(1)) * 1000:g} m", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:miles?|마일)(?![a-z])", lambda m: f"{float(m.group(1)) * 1609.344:g} m", t)
    t = re.sub(r"(\d+(?:\.\d+)?)\s*(?:meters?|metres?|metals?|미터)", r"\1 m", t)
    t = re.sub(r"(?<![\d.])(\d+) ?m (0\.\d+) m", lambda m: f"{int(m.group(1)) + float(m.group(2)):g} m", t)  # "1미터 50센치",
                                                                      # whisper's "1m 50cm"
    t = re.sub(r"(?<![\d.])(\d+)(?: m)? and (?:a )?(?:half|0\.5)(?: m)?", lambda m: f"{int(m.group(1)) + 0.5:g} m", t)
    t = re.sub(r"(?<![\d.])(\d+) ?m 반", lambda m: f"{int(m.group(1)) + 0.5:g} m", t)
    t = re.sub(r"\ba 0\.5 m", "0.5 m", t)
    return re.sub(r"(\d)\s*m(?![a-z])", r"\1 m", t)


TEEN = {"thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_SEC = r"(?:seconds?|secs?|s)(?![a-z])"
_MIN = r"(?:minutes?|mins?)(?![a-z])"
_HOUR = r"(?:hours?|hrs?)(?![a-z])"
# what may follow a Korean time: not a particle that makes "이 분" / "두 분" people ("이 분한테 줘", "두 분께")
_KO_TIME_END = r"(?!\s*(?:께|한테|에게|들|이랑|하고|의(?![가-힣])|은(?![가-힣])|는(?![가-힣])|이(?![가-힣])|에(?![가-힣])))"


def durations(t):
    """Times in lower-case normalised text -> seconds written "<n> s": "2 minutes" -> "120 s", "half an hour" ->
    "1800 s", "1분 30초" -> "90 s", "오 분" -> "300 s", "한 시간" -> "3600 s". Vague ones ("a few minutes", "몇 분")
    stay as they are. Used by the mission reader only (brain keeps the words)."""
    words = {**EN_NUM, **TEEN, "a": 1, "an": 1}
    en = rf"(\d+(?:\.\d+)?|{'|'.join(sorted(words, key=len, reverse=True))})"
    val = lambda w: float(w) if w[0].isdigit() else words[w]
    t = re.sub(r"\bhalf (?:an|a) hour\b", "1800 s", t)
    t = re.sub(r"\b(?:a )?quarter (?:of an )?hour\b", "900 s", t)
    t = re.sub(r"\bhalf a minute\b", "30 s", t)
    t = re.sub(rf"\b{en} and a half {_MIN}|\b{en} {_MIN} and a half\b",
               lambda m: f"{(val(m.group(1) or m.group(2)) + 0.5) * 60:g} s", t)
    t = re.sub(rf"\b{en} {_HOUR}", lambda m: f"{val(m.group(1)) * 3600:g} s", t)
    t = re.sub(rf"\b{en} ?{_MIN}(?:,? (?:and )?(\d+) ?{_SEC})?",
               lambda m: f"{val(m.group(1)) * 60 + float(m.group(2) or 0):g} s", t)
    sec = en.replace("|an|a)", ")")                       # "a second" is a short wait, not 1 s (steps.WAIT_SHORT_S)
    t = re.sub(rf"(?<![\w.]){sec} ?{_SEC}", lambda m: f"{val(m.group(1)):g} s", t)
    # Korean: 초 / 분 with digits or sino numbers, 시간 with native numbers or digits; "1분 30초", "1분 반"
    ko = rf"(\d+(?:\.\d+)?|{_SINO})"
    kval = lambda w: float(w) if w[0].isdigit() else sino(w)
    t = re.sub(rf"(?<![가-힣\d.])(\d+|{'|'.join(NATIVE)}|{_SINO})\s*시간(?:\s*(반))?{_KO_TIME_END}",
               lambda m: f"{((NATIVE.get(m.group(1)) or kval(m.group(1))) + (0.5 if m.group(2) else 0)) * 3600:g} s", t)
    t = re.sub(rf"(?<![가-힣\d.]){ko}\s*분(?:\s*(?:{ko}\s*초|(반)))?{_KO_TIME_END}",
               lambda m: f"{kval(m.group(1)) * 60 + (kval(m.group(2)) if m.group(2) else 30 if m.group(3) else 0):g} s",
               t)
    t = re.sub(rf"(?<![가-힣\d.]){ko}\s*초(?![가-힣])|(?<![가-힣\d.]){ko}\s*초(?=동안|정도|만|쯤|간|후|뒤)",
               lambda m: f"{kval(m.group(1) or m.group(2)):g} s", t)
    return t


def _key(name):
    return re.sub(r"[\s_.-]", "", name.lower())


def close_names(word, names):
    """Marker names a spoken word may be when it is none of them exactly (a whisper slip): one letter or so off, the
    same digits ("booth3" is not booth_2, "p12" not p1). Several back: ask which one."""
    if len(_key(word)) < 3 or word in NOT_SLIPS:
        return []
    by = {_key(n): n for n in names if re.findall(r"\d+", n) == re.findall(r"\d+", word)
          and _key(n)[:1] == _key(word)[:1] and abs(len(_key(n)) - len(_key(word))) <= 1}
                                                         # whisper keeps the first sound and the length: "send" is no
                                                         # slip of "end", "stage" none of "storage"
    return [by[k] for k in difflib.get_close_matches(_key(word), by, n=3, cutoff=CLOSE)]


def _spoken(name):
    """A regex for a marker name as said: its words / numbers with spaces, "_", "-" or nothing between them, a number
    also as a word ("two", "투"), an English word also in Hangul (KO_SPOKEN)."""
    toks = re.findall(r"[a-z]+|\d+|[가-힣]+", name.lower())
    parts = []
    for tok in toks:
        alts = [tok] + (KO_SPOKEN.get(tok, []) if len(toks) > 1 or tok not in KO_NOT_ALONE else [])
        if tok.isdigit():
            alts += [w for w, n in {**EN_NUM, **KO_EN_NUM, **(SINO if len(toks) > 1 else {})}.items() if n == int(tok)]
                                                         # "부스 삼"; a lone "이" / "오" is a word, not 2 / 5
        alts = sorted(map(re.escape, alts), key=len, reverse=True)
        if re.fullmatch(r"[가-힣]{3,}", tok):
            alts.insert(0, r"\s?".join(tok))           # Korean words said or written apart: "커피 코너" for 커피코너
        parts.append("(?:" + "|".join(alts) + ")")
    return rf"(?<![a-z0-9_가-힣])" + r"[\s_.-]*".join(parts) + rf"(?![a-z0-9_])(?:(?<=[a-z0-9])|{_KO_END})"


def written(name):
    """A marker name as norm() writes it: one word, lower case ("Coffee Corner" -> "coffee_corner")."""
    return re.sub(r"\s+", "_", name.strip().lower())


def marker(word, names):
    """The marker of the map written as `word` in normalised text ("coffee_corner" -> "Coffee Corner"), or None."""
    return next((n for n in names if written(n) == word), None)


def map_names(t, names):
    """Marker names of this map in normalised text written as the names (written()), then one-name slips after a
    place word ("to the stagee")."""
    names = [n for n in names if not re.fullmatch(r"p\d+", n.lower())]       # p-numbers: markers() above
    for n in sorted(names, key=len, reverse=True):
        t = re.sub(_spoken(n), written(n), t)
    known = {written(n) for n in names}

    def slip(m):
        for w in (m.group(2).split()[0], m.group(2)):          # one word, then two ("table fronts")
            if w in known:
                break
            close = close_names(w, names)
            if len(close) == 1:
                return m.group(1) + written(close[0]) + m.group(2)[len(w):]
        return m.group(0)
    return re.sub(r"(\b(?:to|from|at|toward|towards) (?:the )?)([a-z][a-z0-9_]*(?: [a-z0-9]+)?)", slip, t)


ASR_SLIPS = [   # how whisper writes Korean commands (tests/asr_check.py, 2026-10-21) -> as said
    (r"([a-z0-9])\.?\s+(으로|로)\s*(?=가|와|이동|돌아)", r"\1\2 "),   # "P3. 로가줘", "final point. 로 가": one word
    (r"(?<=로)\s*가죠(?![가-힣])", " 가 줘"),                        # "p3로 가 줘" written "p3로 가죠"
    (r"\blook (?:last|lest|less)(?=[\s.!,]*$)", "look left"), (r"\bdoc t\b", "dock 2"),     # said at the end
    (r"고게(?=\s*(?:들|숙))", "고개"), (r"찝어", "집어"), (r"파이나(?=\s*(?:갔|가|로))", "파이널"),
    # the owner's English as whisper wrote it live (logs/lumi.log 2026-10-21 / 22)
    (r"\bcount to(?= p\s?\d)", "come to"),                       # "Let's count to p5."
    (r"\b(?:go )?(?:copy|pick) (\d+|one|two|three|four|five|six|seven|eight|nine|ten) point\b", r"go to p\1"),
    (r"\bfall(?:ow)? (?:lonely|of him)\b", "follow me"),         # "Let's fall lonely.", "Let's fall of Him."
    # hearing round 2 (tests/asr_check.py blind r3 / set 5, 2026-10-22 night)
    (r"(\d)\s*센트(?=\s*(?:앞|뒤|가|와|이동|옆|만|[.!]|$))", r"\1센티"),   # "왼쪽으로 30센트 가죠"
    (r"\bboot(?:h)?(?: number)? (?=\d|(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b)",
     "booth "),                                                    # "Go to boot number 12.", "Go to boot three."
    (r"\b(go|move|turn) write\b", r"\1 right"), (r"\bturn rate\b", "turn right"),   # "Go write one meter."
    (r"\bto \.(\d+)\b", r"to point \1"),                         # "Please drive to .8."
    (r"\bmean stage\b", "main stage"),
]


_NO = r"(?<![가-힣a-z])"
KONGLISH = [   # English direction words said in Korean -> the Korean word ("레프트로 반 미터 가 줘요", "라이트 턴 해")
    (_NO + r"레프트\s*(?:쪽으로|으로|로|쪽)?", "왼쪽으로 "),
    (_NO + r"라이트\s*(?:쪽으로|으로|로|쪽)(?![가-힣])|" + _NO + r"라이트(?=\s*(?:턴|turn|무브|move|\d|반\s*미터))",
     "오른쪽으로 "),                                     # "라이트 켜" is a light
    (_NO + r"포워드\s*(?:쪽으로|으로|로|쪽)?", "앞으로 "),
    (_NO + r"백\s*(?:쪽으로|으로|쪽)(?![가-힣])|" + _NO + r"백(?=\s+(?:\d|반\s*미터|무브|move|고(?![가-힣])|해(?![가-힣])))",
     "뒤로 "),                                           # "백 미터", "백팔십" stay numbers
    (r"(?:" + _NO + r"턴|(?<=으로 )turn\b)(?:\s*(?:해|해요|해라|하세요|하십시오|해\s*줘|해\s*주세요|해\s*줄래요?))?(?![가-힣])",
     "돌아"),                                            # "왼쪽으로 턴 해", "왼쪽으로 turn 해"
    (r"(?:" + _NO + r"무브|(?:(?<=미터 )|(?<=센티 )|(?<=센치 )|(?<=cm )|(?<=\dm )|(?<=으로 ))고|" + _NO + r"고\s*고)(?:\s*(?:해|해요|하세요|해\s*줘|해\s*주세요))?(?![가-힣])",
     "이동해"),                                          # "고" alone is a particle / a place's "go": after a way only
    (r"(고개|머리|헤드|얼굴)\s*(?:를|을)?\s*업(?![가-힣])", r"\1 들어"),
    (r"(고개|머리|헤드|얼굴)\s*(?:를|을)?\s*다운(?![가-힣])", r"\1 숙여"),
    (_NO + r"헤드(?=\s)", "고개"),
]


_DIR = r"(?:forward|backwards?|back|left|right|앞으로|뒤로|왼쪽|오른쪽|옆으로)"
_AMOUNT = r"(?:(?:\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|and|a|half)\s+)+"
# whisper's slips of amounts in a move (tests/asr_check.py set 5, blind train hearing; 2026-10-23). Each needs a move
# direction in the text (MOVE_SAID); none guesses a lost digit: "1.m" (1.5미터 with the 5 dropped) becomes "1점 몇 m",
# which is asked ("how far?") instead of driving 1 m.
NUMBER_SLIPS = [
    (r"(?<![\d.])(\d+)\.\s?m(?![a-z\d])", r"\1점 몇 m"),                           # "앞으로 1.m가"
    (r"(?<![\d.])(\d+)\s?미가(?![가-힣])", r"\1미터 가"),                          # "1미가"
    (r"(?<![\d.])(\d+)\s?m\s?(\d+)\s?cm\b", r"\1 m \2 cm"),                      # "1m50cm 뒤로 가"
    (r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:센트|센터|세트|세기|cent(?:uries|ury|s|i)?(?: letters?)?)(?![a-z])",
     r"\1 cm"),                                                                  # "30 centuries", "40센터만", "60세기"
    (r"\b(forward|backward|left|right)\.\s+(\d+(?:\.\d+)?)\s*(?=cm|m\b|meters?|미터|센티|도|degrees?)", r"\1 \2 "),
                                                     # a clause cut at the language change: "Left. 30cm가." (a period
                                                     # only: commas mark self-corrections, "forward, sorry, right, 150 cm")
    (r"\b((?:go|move|drive|step) " + _DIR + " " + _AMOUNT + r")(?:years?|later)\b", r"\1meters"),   # "go back two years"
    (r"\b(forward|backward|left|right)[,.]? to me(?=\W*$)", r"\1 2 meters"),     # "Go forward. Forward to me." (not back:
                                                                                 # "go back to me" may be meant)
    (r"(\bto [\w.-]+)[,.]? weight[,.]? (?=\S)", r"\1, wait, "),                  # "Move to P3 weight P8"
]
MOVE_SAID = re.compile(rf"\b(?:go|move|drive|step|come|turn)\b|{_DIR}|가|와|이동|돌아")
NOT_MOVE = re.compile(r"\b(?:come|look|turn|wave|give|bring|hand|show)\b[^.!?]*\bto me\W*$")


def number_slips(t):
    """Whisper's slips of a distance in a move command (NUMBER_SLIPS); text without a move is left as it is."""
    if not MOVE_SAID.search(t):
        return t
    for slip, said in NUMBER_SLIPS:
        if "to me" in slip and NOT_MOVE.search(t):
            continue
        t = re.sub(slip, said, t)
    return t


def norm(text, names=()):
    """Lower case, whisper's slips (ASR_SLIPS), Konglish directions (KONGLISH), numbers first ("point five meters" is
    a distance), then marker names (names: the map's)."""
    t = " " + (text or "").lower().replace("’", "'") + " "
    for slip, said in ASR_SLIPS + KONGLISH:
        t = re.sub(slip, said, t)
    t = number_slips(t)
    return re.sub(r"\s+", " ", markers(map_names(numbers(t), names))).strip()   # the map's names first: "booth 3 point"
                                                                                # is booth_3, not "booth p3"


if __name__ == "__main__":
    print(norm(" ".join(sys.argv[1:])))
