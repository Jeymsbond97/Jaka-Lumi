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
    if re.search(r"\b(?:turn|rotat\w*|spin|swivel|pivot|degrees?)\b|돌|회전", t):     # "turn left one eighty": 180
        t = re.sub(r"\b(one|two|three) ([2-9]0)\b(?!\s*(?:m|cm|mm|meters?|metres?|centimet\w*)\b)",
                   lambda m: str(100 * _num(m.group(1)) + int(m.group(2))), t)
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
    t = re.sub(rf"(?<![\d.])(\d+) ?m ?({_SINO}|\d{{2}})(?![\d.가-힣]|\s*(?:m|도|°|degrees?|cm|센|초|분|seconds?|minutes?)\b)",
               lambda m: f"{int(m.group(1)) + (int(m.group(2)) if m.group(2).isdigit() else sino(m.group(2))) / 100:g} m"
               if 10 <= (int(m.group(2)) if m.group(2).isdigit() else sino(m.group(2)) or 0) < 100 else m.group(0), t)
    # "1미터50", "one meter fifty", "일 미터 오십": the centimetres after the metres
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
    # the head up / down, said or heard loosely (2026-10-23 15:08-15:16: "Look at the bellow.", "Look it up.")
    (r"\blook (?:at |to(?:wards?)? )?(?:the )?(?:upwards?|above)\b|\blook (?:at |to(?:wards?)? )(?:the )?up\b", "look up"),
    (r"\blook (?:at |to(?:wards?)? )?(?:the )?(?:downwards?|below|bellow)\b|\blook (?:at |to(?:wards?)? )(?:the )?down\b",
     "look down"),
    (r"^\W*look it up\W*$", " look up "),       # alone it is the head; "look it up for me" / "look up the news" stay a search
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
    (_NO + r"업\s*(?=(?:좀\s*)?(?:봐|보세요|봐요))", "위 "),     # "업 봐"
    (_NO + r"다운\s*(?=(?:좀\s*)?(?:봐|보세요|봐요))", "아래 "),  # "다운 봐"
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


NOT_LATER = re.compile(r"[\s,;]*\b(?:and |but |so )?(?:not|no) (?:later(?! than)|tomorrow|tonight|afterwards?|next time|"
                       r"in a (?:bit|while|minute|moment|sec(?:ond)?))\b[\s.!]*|"
                       r"[\s,]*(?:나중에?|이따가?|있다가|다음에) ?(?:말고|아니고)(?![가-힣])", re.I)
    # "go to the stage, right now, not later", "지금 가, 나중 말고": said to mean now; the later-time guards must not see it


def now_not_later(t):
    """The words without "not later" / "나중 말고" (NOT_LATER)."""
    return re.sub(r"\s{2,}", " ", NOT_LATER.sub(" ", t or "")).strip() or (t or "")


def _jamo(c):
    n = ord(c) - 0xAC00
    return (n // 588, n // 28 % 21, n % 28) if 0 <= n < 11172 else None


def _syl(l, v, t=0):
    return chr(0xAC00 + (l * 21 + v) * 28 + t)


def aform(stem):
    """The 아/어 form of a Korean verb stem, the form a plain request ends in: 가 -> 가, 오 -> 와, 따라오 -> 따라와,
    주 -> 줘, 기다리 -> 기다려, 하 -> 해, 집 -> 집어, 잡 -> 잡아, 놓 -> 놔, 누르 -> 눌러, 끄 -> 꺼."""
    if not stem or not _jamo(stem[-1]):
        return stem
    if stem.endswith("하"):
        return stem[:-1] + "해"
    if stem.endswith("놓"):
        return stem[:-1] + "놔"
    l, v, t = _jamo(stem[-1])
    if t:
        return stem + ("아" if v in (0, 8) else "어")
    if stem[-1] == "르" and len(stem) > 1 and _jamo(stem[-2]) and not _jamo(stem[-2])[2]:
        pl, pv, _ = _jamo(stem[-2])
        return stem[:-2] + _syl(pl, pv, 8) + ("라" if pv in (0, 8) else "러")
    v = {8: 9, 13: 14, 20: 6, 18: 4, 11: 10}.get(v, v)          # 오 -> 와, 주 -> 줘, 리 -> 려, 끄 -> 꺼, 되 -> 돼
    return stem[:-1] + _syl(l, v) + ("어" if v == 16 else "")


KO_SOCIAL = {"안녕하", "수고하", "고생하", "감사하", "축하하", "조심하", "계", "드", "주무", "잡수", "들어가", "쉬", "반갑", "알",
             "맞", "아니", "뭐", "그", "이", "누구", "어디", "왜", "마", "말"}   # "안녕하세요", "들어가세요", "뭐라고?": kept as said
KO_SOCIAL_BEFORE = re.compile(r"(?:안녕히|조심히|살펴|잘|편히|어서)\s*$")   # "안녕히 가세요", "어서 오세요": greetings
KO_L_DROP = {"도": "돌", "흔드": "흔들", "여": "열", "내미": "내밀", "미": "밀", "도시": "돌"}   # 도세요 is 돌다's
_END = r"(?=(?:\s+(?:빨리|얼른|어서|좀|제발|당장|지금|please|now|루미야?|로봇아?))*\s*(?:[,.!?~…]|$))"   # a clause's end
_END_NOT_ASKED = r"(?=(?:\s+(?:빨리|얼른|어서|좀|제발|당장|지금|please|now|루미야?|로봇아?))*\s*(?:[,.!~…]|$))"
_HON = r"(?:세요|세용|세여|십시오|시오|셔요|시죠|실래요|실래|시겠어요|시겠습니까|시겠어|시게|이소(?:마|예)?|거라|너라|렴|라고요?|랑께요?|래이|이라|쇼|시라|시지요|실래예|씨요|세예)"
_LOOK_AT = r"(왼쪽|오른쪽|위|위쪽|아래|아래쪽|뒤|뒤쪽|앞|하늘|천장|바닥|여기|이쪽|저쪽|나|날|저|정면|좌측|우측)"
KO_PLAIN = [
    (re.compile(r"(?<=아니 )(\S+?)(?:이요|요)(?=\s*(?:[,.!?~…]|$))"), r"\1"),          # "아 아니 정면이요": the noun
    (re.compile(r"오른쭉|오른족"), "오른쪽"), (re.compile(r"(?<![가-힣])외쪽"), "왼쪽"), (re.compile(r"고게(?= )"), "고개"),
    (re.compile(r"(루미야|루미씨|루미 씨)(?=[가-힣])"), r"\1 "),                       # "루미야오른쪽 봐"
    (re.compile(r"(?<![가-힣])쫌(?![가-힣])"), "좀"), (re.compile(r"(?<![가-힣])놉여"), "높여"),
    (re.compile(r"(?<= )주드라(?:고|구)|(?<= )주드랑께"), "줘"),                       # 전라: "와 주드라고"
    (re.compile(r"(?<![가-힣])(\S*(?:돌아오|따라오|다가오|가져오|이리 오|일로 오))게" + _END), lambda m: aform(m.group(1))),
                                                                                   # 하게체: "돌아오게", "이리 오게"
    (re.compile(r"(\S+) ?주셨으면 (?:해요|합니다|좋겠(?:어요|습니다|네요))" + _END), r"\1 줘"),   # "내려가 주셨으면 해요"
    (re.compile(r"(?<= )조(?:잉)?(?=\s*(?:[,.!?~…]|$))"), "줘"),                       # "흔들어 조잉", "손 한번 조"
    (re.compile(r"악수 ?(?:한 ?번)? ?(?:할까요?|하실래요?|합시다|하십시다|하자잉|허자잉?|하입시더)"), "악수하자"),   # shake hands = wave
    (re.compile(r"(?<=[가-힣](?:라|자)) 마(?=\s*(?:[,.!?~…]|$))"), ""),                 # 경상: "팔 접어 봐라 마"
    (re.compile(_LOOK_AT + r" ?(?:한번 )?(?:바|보게)(?= 주|\s*(?:[,.!?~]|$))"), r"\1 봐"),   # whisper "왼쪽바", 하게체 "하늘보게"
    (re.compile(r"(\S+) ?주면 안 (?:돼|될까|되나|되겠니|되겠어|되겠습니까)(?:요)?\s*\??" + r"(?=\s*(?:[,.!~…]|$))"), r"\1 줘?"),
                                                                                   # "봐 주면 안 돼?": please look
    (re.compile(r"(?<=\S) 주게(?=\s*(?:[,.!?~…]|$))"), " 줘"),                        # 하게체: "봐 주게"
    (re.compile(r"(?<![가-힣])볼래(?:요)?\s*\?*(?=\s*(?:[,.!~…]|$))"), "봐 줘?"),      # "나 볼래요?", "천장 봐 볼래요?"
    (re.compile(r"(?<![가-힣])(\S*(?:려|어|아|와|봐|해|줘)) 도(?=\s*(?:[,.!?~…]|$))"), r"\1 줘"),   # 경상: "돌려 도"
    (re.compile(r"(?<![가-힣])아프로(?=\s|$)"), "앞으로"),                            # "아프로 가": 앞으로 as said
    (re.compile(r"(?<=[\d일이삼사오육칠팔구십 ])(?:메타|미타|메다)(?![가-힣])"), "미터"),   # "삼메타"
    (re.compile(r"(\S+) ?줬으면 (?:좋겠(?:어요?|습니다|다|네요)|해요?|싶어요?)" + _END), r"\1 줘"),   # "가 줬으면 좋겠어"
    (re.compile(r"(?<=[가-힣]) ?줘 ?봐(?:요)?" + _END), " 줘"),                      # "출발해 줘 봐"
    (re.compile(r"(?<![가-힣])(\S*(?:가|와|봐|해|어|아|려|워))조" + _END), r"\1 줘"),   # whisper: "가조", "따라와조"
    (re.compile(r"(?<![가-힣])(\S*(?:가|와|해|어|아|려|워|봐)) 볼래(?:요)?" + _END), r"\1 봐"),   # "나와 볼래?"
    (re.compile(r"(?<![가-힣])(\S*하)게" + _END), lambda m: aform(m.group(1))),   # 하게체: "이동하게" -> 이동해
    (re.compile(r"(\S+) ?주(?:시|)면 (?:돼요?|됩니다|돼|좋겠(?:어요?|습니다|다|네요)|고맙겠(?:어요?|습니다)|감사하겠(?:어요?|습니다)|"
                r"감사(?:하겠습니다|드리겠습니다|해요)?)" + _END), r"\1 줘"),          # "가 주면 돼", "주시면 감사하겠습니다"
    (re.compile(r"(?<![가-힣])(\S*?[가-힣])(?:으)?면 (?:돼요?|됩니다)" + _END_NOT_ASKED), "STEM"),   # "날 따라오면 돼"
    (re.compile(r"(?<![가-힣])(\S*[가-힣])\s?(?:줄래요?|줄 수 (?:있어요?|있니|있나요|있습니까)|주실 수 (?:있어요|있나요|있습니까|있으세요)|"
                r"주시겠어요|주시겠습니까|주실래요)" + _END), r"\1 줘"),
    (re.compile(r"(?<![가-힣])(\S*?[가-힣])(?:으)?" + _HON + _END), "STEM"),          # 가세요, 따라오십시오, 보이소, 집으세요
    (re.compile(r"(?<![가-힣])(\S*[가-힣])(?: 수 (?:있을까요?|있겠(?:어요|니|습니까)|있으실까요|있으시겠어요))\s*\??" + _END),
     "CAN_L"),                                                                       # "갈 수 있을까요?": please go
    (re.compile(r"(?<![가-힣])(\S*[가-힣]) 거 (?:돼요|되나요|될까요|가능해요|가능할까요|가능합니까|가능하세요)\s*\??" + _END),
     "CAN_N"),                                                                       # "가는 거 돼요?"
    (re.compile(r"(?<![가-힣])(\S*(?:해|가|와|봐|줘|돌아|어|아|려|워|쳐|져|켜|꺼|둬|놔|펴|서|내))(?:요|라|유|부러|불어|뿌러|뿌라|삐라|잉|용)" + _END),
     r"\1"),                                                                      # 해요, 가라, 해유, 해부러, 줘잉
    (re.compile(r"(?<![가-힣])혀" + _END), "해"),                                   # 전라: "빨리 혀"
    (re.compile(r"(?<![가-힣])가 ?온나" + _END), "가져와"),                           # 경상: "컵 가온나" is 가져와
    (re.compile(r"(\S*)온나" + _END), r"\1와"),                                     # 경상: "따라온나", "이리 온나"
    (re.compile(r"((?:고개|머리|얼굴|손|팔)\s?(?:좀\s)?)드(?:세요|십시오|시오|이소|셔요)" + _END), r"\1들어"),   # "고개 드세요": 들다
    (re.compile(r"((?:그거|이거|저거|그것|이것|저것|그 컵|이 컵|좀|빨리|퍼뜩|언능|얼른) )도" + _END), r"\1줘"),   # 경상: "그거 도"
]


def _stem_l(word):
    """The verb stem of a 관형형 before 수: 갈 -> 가, 숙일 -> 숙이, 집을 -> 집, 들 -> 들, 돌 -> 돌; None when it is none."""
    if word.endswith("을") and len(word) > 1:
        return word[:-1]
    j = _jamo(word[-1])
    if not j or j[2] != 8:
        return None
    stem = word[:-1] + _syl(j[0], j[1])
    return {"드": "들", "도": "돌", "여": "열", "미": "밀", "내미": "내밀", "흔드": "흔들"}.get(stem, stem)


def _can_you(m, kind):
    """"홈으로 갈 수 있을까요?", "고개 숙일 수 있겠어요?", "가는 거 돼요?": a polite request -> "가 줘?"."""
    w = m.group(1)
    if w in ("그럴", "이럴", "저럴", "알", "될", "있을", "없을", "믿을", "잘", "그렇게", "어떻게", "그러는", "이러는"):
        return m.group(0)                                  # "그럴 수 있을까요?", "알 수 있을까요?": no request
    stem = _stem_l(w) if kind == "CAN_L" else (w[:-1] if w.endswith("는") and len(w) > 1 else None)
    if kind != "CAN_L" and stem:
        stem = {"도": "돌", "드": "들", "여": "열", "흔드": "흔들", "내미": "내밀"}.get(stem, stem)
    if not stem or stem in KO_SOCIAL:
        return m.group(0)
    return aform(stem) + " 줘?"


def _stem_aform(word):
    """'따라오' -> '따라와', with KO_SOCIAL kept as they are and 도 -> 돌아 (KO_L_DROP); None when kept."""
    if word in KO_SOCIAL or word.split()[-1] in KO_SOCIAL:
        return None
    return aform(KO_L_DROP.get(word, word))


def ko_plain(t):
    """Korean request endings of every speech level and dialect as one plain form, so the readers see one wording:
    "가세요" / "가십시오" / "가요" / "가라" / "가이소" -> "가"; "따라오세요" / "따라온나" / "따라오라고" -> "따라와";
    "가 주세요" / "가 주실래요?" / "가 주시겠습니까?" / "가 주면 돼" / "가 주시면 감사하겠습니다" -> "가 줘"; "도세요" -> "돌아";
    "흔드세요" -> "흔들어"; "해부러" / "혀" -> "해". Greetings ("안녕하세요", "들어가세요") stay; questions keep their "?"."""
    if not t or not re.search(r"[가-힣]", t):
        return t
    for rx, to in KO_PLAIN:
        if to in ("CAN_L", "CAN_N"):
            t = rx.sub(lambda m: _can_you(m, to), t)
        elif to == "STEM":
            def stem(m):
                w = m.group(1)
                if KO_SOCIAL_BEFORE.search(m.string[:m.start()]):
                    return m.group(0)
                got = _stem_aform(w[:-1] if w.endswith("으") and len(w) > 1 and _jamo(w[-2]) and _jamo(w[-2])[2] else w)
                return got if got else m.group(0)
            t = rx.sub(stem, t)
        else:
            t = rx.sub(to, t)
    return t


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
    t = re.sub(r"(\S+)[—–-]+\s*(?=\1)", "", t)                              # a stutter: "육십 센— 센티", "go ah— ahead"
    t = re.sub(r"(?<=[가-힣])(?=\d+(?:\.\d+)?\s*(?:미터|센티|센치|cm|m\b|도))", " ", t)   # "오른쪽으로80센티미터"
    for slip, said in ASR_SLIPS + KONGLISH:
        t = re.sub(slip, said, t)
    t = number_slips(t)
    return re.sub(r"\s+", " ", markers(map_names(numbers(t), names))).strip()   # the map's names first: "booth 3 point"
                                                                                # is booth_3, not "booth p3"


if __name__ == "__main__":
    print(norm(" ".join(sys.argv[1:])))
