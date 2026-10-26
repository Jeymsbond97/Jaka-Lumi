"""Facts Lumi can look up while talking: date and time (always), weather and web search (needs internet).

The robot network has no internet; the Thor reaches it through its own Wi-Fi. A proxy can be set instead
(one line such as http://192.168.10.200:8888 in proxy.txt next to this file, or HTTPS_PROXY).

    python assistant/web.py                  # date/time + is the internet reachable?
    python assistant/web.py weather Seoul
    python assistant/web.py search "Jetson Thor"
"""
import html
import datetime
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]      # the project folder
PROXY_FILE = ROOT / "data" / "proxy.txt"          # e.g. http://192.168.10.200:8888 (one line), optional
DEFAULT_PLACE = "Seoul"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux aarch64) LumiRobot/1.0"}
_online = {"time": 0.0, "ok": False}
PLACES = {"seoul": {"name": "Seoul", "latitude": 37.57, "longitude": 126.98},     # known places: no geocoding request
          "incheon airport": {"name": "Incheon Airport", "latitude": 37.46, "longitude": 126.44},   # the geocoder has
          "gimpo airport": {"name": "Gimpo Airport", "latitude": 37.56, "longitude": 126.79}}       # towns, no airports
FIXED = list(PLACES.values())
# Korean names -> the English name the geocoder knows (it finds 부산 as a village "Pusan", 제주 not at all, "Jeju" in Ethiopia)
KO_PLACES = {
    "서울": "Seoul", "부산": "Busan", "인천": "Incheon", "대구": "Daegu", "대전": "Daejeon", "광주": "Gwangju",
    "울산": "Ulsan", "세종": "Sejong", "수원": "Suwon", "성남": "Seongnam-si", "고양": "Goyang", "용인": "Yongin-si",
    "창원": "Changwon", "청주": "Cheongju", "전주": "Jeonju", "천안": "Cheonan", "포항": "Pohang", "김해": "Gimhae",
    "제주": "Jeju City", "제주도": "Jeju City", "서귀포": "Seogwipo", "강릉": "Gangneung", "춘천": "Chuncheon", "원주": "Wonju",
    "속초": "Sokcho", "경주": "Gyeongju", "여수": "Yeosu", "목포": "Mokpo", "안동": "Andong", "평창": "Pyeongchang",
    "도쿄": "Tokyo", "오사카": "Osaka", "교토": "Kyoto", "후쿠오카": "Fukuoka", "삿포로": "Sapporo",
    "베이징": "Beijing", "상하이": "Shanghai", "홍콩": "Hong Kong", "타이베이": "Taipei", "방콕": "Bangkok",
    "싱가포르": "Singapore", "하노이": "Hanoi", "다낭": "Da Nang", "뉴욕": "New York", "런던": "London",
    "파리": "Paris", "타슈켄트": "Tashkent", "사마르칸트": "Samarkand",
    "인천공항": "Incheon Airport", "인천국제공항": "Incheon Airport", "김포공항": "Gimpo Airport",
    "jeju": "Jeju City", "seongnam": "Seongnam-si", "yongin": "Yongin-si",   # the plain English name is found elsewhere
}


def en_place(place):
    """'부산', '부산시', '제주도', 'Jeju' -> 'Busan', 'Busan', 'Jeju City', 'Jeju City'; anything else unchanged."""
    p = place.strip()
    return KO_PLACES.get(p.lower()) or (KO_PLACES.get(p[:-1]) if p.endswith(("시", "도")) else None) or p
WEATHER_TTL = 600                        # s a weather answer is reused (each web request takes ~2 s on the Wi-Fi)
_weather = {}                            # place -> (time, text)


def _opener():
    proxy = PROXY_FILE.read_text().strip() if PROXY_FILE.exists() else os.environ.get("HTTPS_PROXY", "")
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else []
    return urllib.request.build_opener(*handlers)


def _get(url, timeout=6, headers=UA):
    req = urllib.request.Request(url, headers=headers)
    with _opener().open(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def online():
    """Is the internet reachable? (checked at most every 60 s)"""
    now = time.time()
    if now - _online["time"] > 60:
        _online["time"] = now
        try:
            _get("https://api.open-meteo.com/v1/forecast?latitude=37.57&longitude=126.98&current=temperature_2m", 4)
            _online["ok"] = True
        except Exception:
            _online["ok"] = False
    return _online["ok"]


def now_text():
    """Local date and time in words, e.g. 'Monday, 12 October 2026, 15:07'."""
    return time.strftime("%A, %d %B %Y, %H:%M")


WEATHER_CODES = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog",
                 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
                 61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
                 71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "rain showers",
                 81: "rain showers", 82: "violent rain showers", 85: "snow showers", 86: "snow showers",
                 95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"}
WEATHER_DAYS = 7                         # days of forecast given ("tomorrow", "모레", "this weekend")


def weather(place=DEFAULT_PLACE):
    """Weather now and the days ahead as a short English text, or None without internet."""
    place = en_place(place or DEFAULT_PLACE) or DEFAULT_PLACE
    key = place.lower()
    if key in _weather and time.time() - _weather[key][0] < WEATHER_TTL:
        return _weather[key][1]
    try:
        loc = _place(place)
        if not loc:
            return f"I could not find a place called {place}."
        w = json.loads(_get(
            f"https://api.open-meteo.com/v1/forecast?latitude={loc['latitude']}&longitude={loc['longitude']}"
            "&current=temperature_2m,weather_code,wind_speed_10m&daily=weather_code,temperature_2m_max,"
            f"temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days={WEATHER_DAYS}"))
        c, d = w["current"], w["daily"]
        days = []
        for i, day in enumerate(d["time"]):
            name = datetime.date.fromisoformat(day).strftime("%A %d %B")
            name = f"Today ({name})" if i == 0 else f"Tomorrow ({name})" if i == 1 else name
            days.append(f"{name}: {WEATHER_CODES.get(d['weather_code'][i], 'unknown')}, {d['temperature_2m_min'][i]:.0f} "
                        f"to {d['temperature_2m_max'][i]:.0f} degrees, chance of rain "
                        f"{d['precipitation_probability_max'][i]} percent.")
        text = (f"Weather in {loc['name']} now: {WEATHER_CODES.get(c['weather_code'], 'unknown')}, "
                f"{c['temperature_2m']:.0f} degrees, wind {c['wind_speed_10m']:.0f} km/h.\n" + "\n".join(days))
        _weather[key] = (time.time(), text)
        return text
    except Exception:
        return None


WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
            "월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "이틀": 2, "사흘": 3, "나흘": 4}
DAY_AFTER = re.compile(r"\bthe (?:day after|next day|following day)\b(?! tomorrow)|그 ?다음 ?날|다음 ?날|그 ?담 ?날|"
                       r"^\W*(?:and then|then|after that|and after that|그 ?다음(?:은|에는?)?|그 ?담(?:엔|은)?|그리고(?:는)?)\W*(?:요)?\W*$", re.I)
                       # a bare "and then?" / "그 다음은?" after a day's weather: the day after it
DAY_BEFORE = re.compile(r"\bthe day before\b(?! yesterday)|그 ?전 ?날", re.I)
FIXED_DAY = re.compile(r"\bday after tomorrow\b|\bday before yesterday\b|내일 ?모레|글피|그저께|그제|모레|"
                       r"(?<![a-z])(?:today|tonight)(?![a-z])|\b(?:this |in the )?(?:morning|afternoon|evening)(?![a-z])|"
                       r"\bright now\b|\bnow\b|오늘|지금|(?<![a-z])tomorrow(?![a-z])|내일|(?<![a-z])yesterday(?![a-z])|어제|"
                       r"아침|오전|오후|저녁|(?<![가-힣])밤(?:에는|에|은|엔|이)?(?![가-힣])|(?<![가-힣])낼(?=[은는도]|\s|\W|$)", re.I)   # "tomorrow는?", "저녁에는?": English
                       # words next to Korean ones have no \b; a part of the day alone is today's
FIXED_OFFSET = {"day after tomorrow": 2, "day before yesterday": -2, "내일모레": 2, "내일 모레": 2, "글피": 3,
                "그저께": -2, "그제": -2, "모레": 2, "tomorrow": 1, "내일": 1, "낼": 1, "yesterday": -1, "어제": -1}
IN_DAYS = re.compile(r"\bin (\d+|one|two|three|four|five|six|seven) days?\b|(\d+|이틀|사흘|나흘) ?(?:일)? ?(?:후|뒤)", re.I)
WEEKDAY = re.compile(r"(?<![a-z])(monday|tuesday|wednesday|thursday|friday|saturday|sunday)s?(?![a-z])|([월화수목금토일])요일", re.I)
WEEKEND = re.compile(r"(?<![a-z])weekend(?![a-z])|주말", re.I)
NEXT_WEEK = re.compile(r"\bnext\b|다음 ?주|담 ?주", re.I)        # "next Monday", "다음 주 월요일", "next weekend"
WEEK = re.compile(r"\b(?:this|next) week\b|이번 ?주|다음 ?주|담 ?주", re.I)
DAY_PHRASE = re.compile(r"(?:이번|다음|담|this|next|coming) ?(?:주말|weekend)|" +     # before "이번 주", "다음 주"
                        "|".join(r.pattern for r in (DAY_AFTER, DAY_BEFORE, IN_DAYS, WEEKDAY, WEEKEND, WEEK, NEXT_WEEK, FIXED_DAY)) +
                        r"|\b(?:this|coming|on)\b", re.I)          # all the words that name a day, for lumi's follow-ups


def asked_day(text, before=None, today=None):
    """The days a question asks about, as days from today: [0] today, [1] tomorrow, [2] 모레, a weekday its next
    one (today's own name is today), "next Monday" / "다음 주 월요일" the Monday of next week, "this weekend" / "주말"
    Saturday and Sunday, "next week" its seven days; negative for days past. "The day after" / "다음 날" is the day
    after `before` (the days asked the turn before). None when no day is named."""
    t = text or ""
    wd = (today or datetime.date.today()).weekday()
    before = before or [0]
    if DAY_AFTER.search(t):
        return [before[-1] + 1]
    if DAY_BEFORE.search(t):
        return [before[0] - 1]
    m = IN_DAYS.search(t)
    if m:
        n = m.group(1) or m.group(2)
        return [int(n) if n.isdigit() else NUMBER_WORDS[n.lower()]]
    week = 7 if NEXT_WEEK.search(t) else 0
    m = WEEKDAY.search(t)
    if m:
        day = WEEKDAYS[(m.group(1) or m.group(2)).lower()]
        return [7 - wd + day] if week else [(day - wd) % 7]
    if WEEKEND.search(t):
        return [d for d in (week + (5 - wd) % 7, week + (6 - wd) % 7) if wd != 6 or week or d == 0]   # Sunday: today
    if WEEK.search(t):
        return list(range(7 - wd, 14 - wd)) if week else list(range(0, 7 - wd))
    m = FIXED_DAY.search(t)
    if m:
        return [FIXED_OFFSET.get(m.group(0).lower(), 0)]
    return None


def weather_on(forecast, days, today=None):
    """Of weather()'s text only what the days asked need: the line of each day (the weather now with today), and a
    plain line for a day past or beyond the forecast, so the answer can't take another day's line."""
    lines = (forecast or "").split("\n")
    if days is None or len(lines) < 2:
        return forecast
    today = today or datetime.date.today()
    place = re.match(r"Weather in (.+?) now:", lines[0])
    out = [lines[0]] if 0 in days else [f"Forecast for {place.group(1) if place else 'here'}:"]
    last = (today + datetime.timedelta(days=len(lines) - 2)).strftime("%A %d %B")
    for d in days:
        name = (today + datetime.timedelta(days=d)).strftime("%A %d %B")
        out.append(lines[d + 1] if 0 <= d < len(lines) - 1 else
                   f"{name}: already past, there is no forecast for a day gone by." if d < 0 else
                   f"{name}: too far ahead, the forecast reaches only to {last}.")
    return "\n".join(out)


def _place(place):
    """{name, latitude, longitude} of a place (English or a Korean name of KO_PLACES), or None; geocoded once."""
    place = en_place(place)
    key = place.lower()
    if key not in PLACES:
        if re.search(r"[가-힣]", place):            # the geocoder finds Korean names wrong (강릉: a village in the North)
            return None
        g = json.loads(_get("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(place), 3))
        if not g.get("results"):
            return None
        PLACES[key] = g["results"][0]
    return PLACES[key]


TOWN = 50000                 # people; a smaller place of the geocoder's is not taken for a distance (often a namesake)
HOW_FAR = re.compile(r"\bhow far\b|\bdistance\b|거리", re.I)
BETWEEN = (re.compile(r"\b(?:from|between)\s+(?:the\s+)?(.+?)\s+(?:to|and)\s+(?:the\s+)?(.+?)(?:\s+by \w+)?[?.!\s]*$", re.I),
           re.compile(r"\bhow far (?:away )?is (?:the\s+)?(.+?) from (?:the\s+)?(.+?)(?:\s+by \w+)?[?.!\s]*$", re.I),
           re.compile(r"([가-힣A-Za-z]+(?: [A-Za-z]+)*)에서 ([가-힣A-Za-z]+(?: [A-Za-z]+)*)까지"),
           re.compile(r"\bdistance (?:of )?(?:the\s+)?(.+?) (?:to|and) (?:the\s+)?(.+?)[?.!\s]*$", re.I),   # the LLM's
           re.compile(r"^(?:distance |how far )?([A-Za-z가-힣]+) ([A-Za-z가-힣]+) (?:거리|distance)", re.I),   # queries
           re.compile(r"^(?:the )?(.+?) distance (?:from|to) (?:the )?(.+?)[?.!\s]*$", re.I),
           re.compile(r"\bhow far (?:away )?is (?:the\s+)?(.+?)[?.!\s]*$", re.I), re.compile(r"([가-힣]+)까지"))
                             # the two places of "how far": the last two forms are from here (Seoul)


def _distance(query):
    """The straight-line distance between the two places a "how far" question names (one: from Seoul), or ''."""
    if not HOW_FAR.search(query):
        return ""
    for form in BETWEEN:                         # the first form whose two places are both found
        m = form.search(query)
        if not m:
            continue
        names = m.groups() if len(m.groups()) == 2 else (DEFAULT_PLACE, m.group(1))
        a, b = (_place(DEFAULT_PLACE if re.fullmatch(r"here|this place|you|여기", n.strip(), re.I) else n.strip())
                for n in names)
        if a and b and not any(p.get("population", 0) < TOWN and p not in FIXED for p in (a, b)):   # "the moon":
            break                                                                              # a French village
    else:
        return ""
    la1, lo1, la2, lo2 = map(math.radians, (a["latitude"], a["longitude"], b["latitude"], b["longitude"]))
    km = 2 * 6371 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 +
                                        math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))
    return (f"Straight-line distance from {a['name']} to {b['name']}: about {km:,.0f} km ({km / 1.609:,.0f} miles); "
            f"by road or rail it is longer.")


def keep_weather_fresh(place=DEFAULT_PLACE):
    """Background thread: refresh the weather before the cache runs out, so a question gets it at once."""
    import threading

    def loop():
        while True:
            _weather.pop(place.lower(), None)
            weather(place)
            time.sleep(WEATHER_TTL - 60)
    threading.Thread(target=loop, daemon=True).start()


STOP = {"the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or", "is", "are", "was", "how", "what", "who",
        "when", "where", "which", "height", "tall", "meters", "metres", "current", "latest", "now", "today", "name",
        "date", "year", "founded", "founding", "company", "age", "old", "big", "size", "long", "length", "far",
        "distance", "population", "price", "cost", "number", "many", "much", "there"}
BROWSER = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 "
                         "Safari/537.36", "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"}
WIKI_UA = {"User-Agent": "LumiRobot/1.0 (https://cutshion.com; cutshion@cutshion.com)"}   # Wikimedia answers 429
                             # (too many requests) to a browser or bare robot name; a name with a contact it serves
SEARCH_WAIT_S = 2.0          # s all sources get together; a slower one is left out (Naver and Wikipedia ~0.7 s,
                             # Google News 0.4-1.6 s; the fetch runs while "Let me check." is said)
PAGE_CHARS = 1500            # chars of the search page given to the LLM (it reads ~1300 tokens a second; Korean
                             # is ~1 token a char); 1200 lost answers further down (Apple's founding year)
BLOCK_CHARS = 600            # ... at most this much from one part of the page (an answer box, the news, one site)
WIKI_CHARS = 500             # chars of the Wikipedia summary
NEWS_ITEMS = 3               # headlines given, only for questions about what changes (NEWSY)
SEARCH_TTL = 600             # s a search result is reused (visitors ask the same things; follow-ups search again)
SKIP_BLOCKS = re.compile(r'ad_section|data-meta-ssuid="(influencer|clip|image|qra|shortents|ex_csa|shopping)"|'
                         r"가격비교|플러스 스토어|브라우저를 업데이트하세요|함께 가볼만한 장소")   # Naver page parts that never answer a question
JUNK = re.compile(r"새 창 열림|새 창으로 열기|Keep에 (저장|바로가기)|Keep 바로가기|문서 저장하기|AI 출처 정보.*?자세히 보기|"
                  r"이 (광고|정보)가 표시된 이유|정보확인 레이어 닫기|레이어 닫기|이전으로 이동|다음으로 이동|이전 다음|"
                  r"동영상 바로재생( 버튼)?|펼치기|접기|공유하기|차트를 불러오는 중입니다\.|"
                  r"환율을 (계산할|변환하는) 국가를 선택( [가-힣]+)+|환율우대 \d+%|환율우대없음|"
                  r"이 키워드를 선택한 인원 [\d,]+|길찾기|거리뷰|펼쳐보기|더보기|알림받기|네이버 고객센터|관련도순 최신순|"
                  r"최신 콘텐츠 채널\(계정\).*?자동으로 구성됩니다\.|(정보확인 내용 열고 닫기|본인참여 관리) .*")   # disclaimers at a box's end
NEWSY = re.compile(r"news|latest|recent|lately|today|tonight|yesterday|\bnow\b|current|this (week|month|year|season)|"
                   r"\blast\b|\bnext\b|\bnew(est)?\b|upcoming|\bwon\b|\bwin|champion|score|result|standing|leading|"
                   r"president|prime minister|minister|\bceo\b|coach|mayor|\bpope\b|chairman|governor|secretary|"
                   r"\bwho('s| is| are) the\b|price|stock|cost|\brates?\b|election|event|"
                   r"release|happening|going on|뉴스|소식|최근|최신|요즘|오늘|어제|지금|현재|올해|이번|작년|지난|다음|우승|"
                   r"결과|순위|경기|대통령|총리|장관|대표|감독|시장|교황|회장|총장|총재|가격|주가|시세|얼마|선거|발표|출시|요금|"
                   r"어느 팀|소속", re.I)
                   # questions about what changes: they get the news headlines (who holds an office, who won lately)
ASKED_AS = ((r"\bhow (tall|high)\b", "height"), (r"\bhow long\b", "length"), (r"\bhow old\b", "age"),
            (r"\bhow far\b", "distance"), (r"\bhow deep\b", "depth"), (r"\bhow (big|large)\b", "size"),
            (r"\bhow many people\b", "population"), (r"\bhow much\b", "price"), (r"\bwhat time\b", "hours"),
            (r"\bwho won\b", "winner"), (r"\bwhere is\b", "location"))   # English question -> what a search engine wants
KO_ASK = ((r"\bhow old\b|\bage\b|\bbirthday\b|\bwhen was \w+( \w+)? born\b", "나이"),
          (r"\bhow tall\b|\bheight\b", "키"), (r"\bstocks?( price)?\b|\bshares?( price)?\b", "주가"),
          (r"\bindex\b|(?=\b(nasdaq|dow jones|kospi|kosdaq|s&p 500)\b)", "지수"),
          (r"\bstandings?\b|\bfirst place\b|\bin first\b|\branking\b", "순위"),
          (r"\bscore\b|\bresult\b|\blast (game|match)\b|\bhow did\b", "경기 결과"))
                             # not opening hours: "Louvre 영업시간" brings Korean shops named Louvre
                             # English question -> the Korean word for Naver's answer box (ko_box_query)
ASK_WORDS = re.compile(r"\b(what'?s|what|who'?s|who|whom|which|where|when|why|how|is|are|was|were|the|a|an|do|does|did|"
                       r"can|could|you|tell me|please|lumi|right now|i|me|my|and|he|she|his|her|it|its|they|their)\b|"
                       r"[?,.!]", re.I)
CURRENCIES = {"USD": ("US dollar", r"dollars?|usd|달러"), "EUR": ("euro", r"euros?|eur\b|유로"),
              "JPY": ("Japanese yen", r"\byen\b|jpy|엔화|(?<=[\d만] )엔|(?<=[\d만])엔"), "CNY": ("Chinese yuan", r"yuan|renminbi|cny|위안"),
              "GBP": ("British pound", r"pounds? sterling|british pounds?|gbp|파운드"),
              "VND": ("Vietnamese dong", r"vietnamese dong|vnd|동화"), "THB": ("Thai baht", r"baht|thb|바트"),
              "KRW": ("Korean won", r"\bwons?\b|krw|원화")}
COINS = {"bitcoin": r"bitcoin|btc|비트 ?코인|빗코인", "ethereum": r"ethereum|\beth\b|이더리움", "ripple": r"\bxrp\b|ripple|리플",
         "solana": r"solana|솔라나", "dogecoin": r"doge|도지"}
RATE_WORDS = re.compile(r"exchange|\brates?\b|convert|환율|환전|in (korean )?wons?\b|\bto (krw|wons?|usd|dollars?)\b|"
                        r"\bkrw\b|원으로|얼마", re.I)
_searched = {}                               # query -> (time, text)
_pool = ThreadPoolExecutor(6)


def _text(page):
    """Visible text of an HTML fragment on one line."""
    page = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page))).strip()


def keywords(query):
    """An English question as search words: "How tall is Son Heung-min?" -> "height Son Heung-min". Naver finds
    English blogs about grammar for a whole English question, the right pages for the words. Korean stays as it is."""
    if re.search(r"[가-힣]", query):
        return query
    q = query
    for asked, word in ASKED_AS:
        q = re.sub(asked, f" {word} ", q, flags=re.I)
    return re.sub(r"\s+", " ", ASK_WORDS.sub(" ", q)).strip() or query


def _naver(query, boxes_only=False):
    """The Naver results page as text: answer boxes (exchange rates, stocks, people, sports), web pages, news, blogs;
    ads, shopping and image strips left out. '' when nothing is found. Naver answers scripts like a browser and
    has live answer boxes; it reads English questions too. boxes_only: the answer boxes alone (the web results
    and news have a data-meta-area)."""
    page = _get("https://search.naver.com/search.naver?query=" + urllib.parse.quote(query), 4, BROWSER)
    parts = []
    for block in re.split(r'(?=<div class="_scrollLog")', page)[1:]:
        if SKIP_BLOCKS.search(block[:3000]) or boxes_only and 'data-meta-area="' in block[:1500]:
            continue
        text = re.sub(r"\s+", " ", JUNK.sub(" ", _text(block))).strip()
        if len(text) > 20 and not text.startswith("함께 가볼만한"):      # places nearby
            parts.append(text[:BLOCK_CHARS])
    return "\n".join(parts)[:BLOCK_CHARS if boxes_only else PAGE_CHARS]


def ko_box_query(query):
    """An English question about a person, a share, an index or a team as its names and the Korean word
    that brings Naver's answer box ("How old is Taylor Swift?" -> "Taylor Swift 나이": birth date and age; the
    English words give only web pages), or None."""
    if re.search(r"[가-힣]", query):
        return None
    for asked, word in KO_ASK:
        if re.search(asked, query, re.I):
            names = re.sub(asked, " ", query, flags=re.I)
            names = re.sub(r"'s\b|'|\b(today|now|currently|doing|in|at|of|for|right|this|last|latest|current|much|"
                           r"open|close|first|price|their|team)\b", " ", names, flags=re.I)
            names = re.sub(r"\s+", " ", ASK_WORDS.sub(" ", names)).strip()
            return f"{names} {word}" if names else None
    return None


def _duckduckgo(query):
    """Titles and snippets from DuckDuckGo, or ''; only when Naver fails (DuckDuckGo often asks scripts to solve a
    picture puzzle)."""
    page = _get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query), 2.5, BROWSER)
    hits = re.findall(r'class="result__a"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</a>', page, re.S)
    return "\n".join(f"{_text(t)}: {_text(s)}" for t, s in hits[:6])[:PAGE_CHARS]


def _wikipedia(query, lang):
    """Intro of the Wikipedia article that fits the query best (one request), or ''."""
    words = [w for w in re.findall(r"\w+", query.lower()) if w not in STOP]
    for q in (" ".join(words), query):                   # the names alone first: "height in metres" misleads search
        if not q:
            continue
        found = json.loads(_get(f"https://{lang}.wikipedia.org/w/api.php?action=query&format=json&generator=search"
                                f"&gsrlimit=3&prop=extracts&exintro=1&explaintext=1&exlimit=3&redirects=1"
                                f"&exchars={WIKI_CHARS}&gsrsearch=" + urllib.parse.quote(q), 3, WIKI_UA))   # full-text search
        pages = sorted(found.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 9))
        if pages:
            break
    else:
        return ""
    best = max(pages, key=lambda p: len(set(words) & set(re.findall(r"\w+", p["title"].lower()))))   # title that fits
    return f"{best['title']}: {best.get('extract', '')}"


def _news(query, lang, n=4):
    """Latest headlines from Google News for the query, or ''."""
    hl = "ko" if lang == "ko" else "en-US"
    gl = "KR" if lang == "ko" else "US"
    rss = _get(f"https://news.google.com/rss/search?hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}&q="
               + urllib.parse.quote(query), 3)
    items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<pubDate>(.*?)</pubDate>", rss, re.S)[:n]
    return "\n".join(f"- {html.unescape(t)} ({d[:16]})" for t, d in items)


def _money(query):
    """Exchange rates to the Korean won (open.er-api.com, updated daily) and coin prices (CoinGecko, live) for the
    currencies and coins the query names, or ''. Naver shows its rate box only for some wordings."""
    lines = []
    named = [c for c, (_, words) in CURRENCIES.items() if re.search(words, query, re.I)]
    if named and RATE_WORDS.search(query):
        r = json.loads(_get("https://open.er-api.com/v6/latest/USD", 3))
        rates = r["rates"]
        for c in [c for c in named if c != "KRW"] or ["USD"]:
            won = rates["KRW"] / rates[c]
            lines.append(f"1 {CURRENCIES[c][0]} = {won:,.2f} Korean won" + (f" (100 yen = {won * 100:,.0f} won)" if
                         c == "JPY" else "") + (f" = {1 / rates[c]:,.4f} US dollars" if c != "USD" else ""))
            m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(만)?\s*(?:" + CURRENCIES[c][1] + ")", query, re.I)
            if m:                                                # "100 dollars", "1만 엔": the sum worked out
                amount = float(m.group(1).replace(",", "")) * (10000 if m.group(2) else 1)
                lines.append(f"{amount:,.0f} {CURRENCIES[c][0]} = {won * amount:,.0f} Korean won")
        lines.append(f"(exchange rates of {r['time_last_update_utc'][:16]})")
    coins = [c for c, words in COINS.items() if re.search(words, query, re.I)]
    if coins:
        price = json.loads(_get("https://api.coingecko.com/api/v3/simple/price?vs_currencies=usd,krw&ids="
                                + ",".join(coins), 3))
        lines += [f"1 {c} = {p['usd']:,} US dollars = {p['krw']:,} Korean won (now)" for c, p in price.items()]
    return "\n".join(lines)


BIRTH = (re.compile(r"\bborn(?: on)? ([A-Z][a-z]+ \d{1,2}, \d{4}|\d{1,2} [A-Z][a-z]+ \d{4})"),
         re.compile(r"(?:출생|생년월일) ?:? ?(\d{4})\. ?(\d{1,2})\. ?(\d{1,2})"),
         re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일 ?(?:~|생|출생)"))


BIRTH_YEAR = re.compile(r"\bborn (?:in )?(\d{4})\b|(\d{4})년생")     # the year only: the age is one of two


def _born(m):
    """The date a BIRTH match names, or None."""
    if len(m.groups()) == 3:
        return datetime.date(*map(int, m.groups()))
    for form in ("%B %d, %Y", "%d %B %Y"):
        try:
            return datetime.datetime.strptime(m.group(1), form).date()
        except ValueError:
            pass
    return None


def with_ages(text, today=None):
    """Each birth date in the text followed by the age it makes today ("born May 7, 1996 (30 years old today)"):
    the LLM gets ages a year wrong."""
    today = today or datetime.date.today()

    def age(m):
        try:
            born = _born(m)
        except ValueError:                       # "1992.13.40"
            born = None
        if not born:
            return m.group(0)
        years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return f"{m.group(0)} ({years} years old today)"
    for pattern in BIRTH:
        text = pattern.sub(age, text)
    def either(m):
        years = today.year - int(m.group(1) or m.group(2))
        return f"{m.group(0)} ({years - 1} or {years} years old today)"
    return BIRTH_YEAR.sub(either, text)


def search(query, n=NEWS_ITEMS):
    """Text to answer a question from, fetched at the same time: exchange rates and coin prices when asked, the
    Naver results page (DuckDuckGo when Naver fails), a Wikipedia summary and Google News headlines. "No results." when nothing is found,
    None without internet. (Bing returns unrelated pages to scripts.)"""
    query = re.sub(r"[<>]", " ", query).strip()                  # the LLM wrote "search <flight time Seoul NY>"
    lang = "ko" if re.search(r"[가-힣]", query) else "en"
    q = re.sub(r"\b(what|who|whom|is|are|was|were|the|a|an|about|tell me|more|please|latest|news|today'?s?|any|how|"
               r"do|does|did|you|know|can|could|of|lumi)\b|[?,.!]", " ", query, flags=re.I)
    q = re.sub(r"\s+", " ", q).strip() or query
    key = query.strip().lower()
    if key in _searched and time.time() - _searched[key][0] < SEARCH_TTL:
        return _searched[key][1]
    jobs = {"Rates and prices": _pool.submit(_money, query)} if RATE_WORDS.search(query) or \
        any(re.search(w, query, re.I) for w in COINS.values()) else {}
    if HOW_FAR.search(query):
        jobs["Distance"] = _pool.submit(_distance, query)
    box = ko_box_query(query)
    if box:                                                      # "Taylor Swift 나이": Naver's people box
        jobs["Answer box"] = _pool.submit(_naver, box, True)
    jobs |= {"Search results": _pool.submit(_naver, keywords(query)), "Wikipedia": _pool.submit(_wikipedia, q, lang)}
    if NEWSY.search(query):                                      # "how old is Musk?" got "80-year-old Musk's father"
        jobs["News headlines"] = _pool.submit(_news, q, lang, n)
    wait(jobs.values(), timeout=SEARCH_WAIT_S)
    found = {}
    for name, job in jobs.items():
        try:
            found[name] = job.result(timeout=0) if job.done() else ""
        except Exception:
            found[name] = ""
    if not found["Search results"]:
        try:
            found["Search results"] = _duckduckgo(keywords(query))
        except Exception:
            pass
    order = sorted(found, key=lambda name: name not in ("Rates and prices", "Distance", "Answer box", "News headlines"))
    text = with_ages("\n\n".join(f"{name}:\n{found[name]}" for name in order if found[name]))   # the news before
                                                         # old pages: "지금 대통령" got the president of 2024
    if not text:
        return None if not online() else "No results."
    _searched[key] = (time.time(), text)
    return text


OPENAI_KEY = Path.home() / ".config" / "lumi" / "openai_key"    # the owner's key, on this Thor only (never copied)
OPENAI_MODEL = "gpt-5.4-mini"    # with web_search: right on live facts, 2-6 s (2026-10-21); ~1.5 cents a question
OPENAI_WAIT_S = 12.0             # s; slower than this: the free search below answers instead
OPENAI_HISTORY = 4               # earlier turns given along, for "and his age?"
OPENAI_SAY = ("You are Lumi, a friendly service robot speaking aloud. Answer the question from a web search in 1-2 short "
              "spoken sentences, in the question's language (English or Korean), the answer first. On 'tell me more' "
              "give 2-3 new facts. Round long numbers; say heights, ages and scores exactly. Now it is {today} in Seoul, Korea (where Lumi is). Never "
              "give a private person's address or phone number. No links, sources, lists or markdown.")
CITATION = re.compile(r"\s*\(\[[^\]]*\]\([^)]*\)\)|\[([^\]]*)\]\([^)]*\)|https?://\S+|[*#`]")


def openai_ready():
    return OPENAI_KEY.exists()


def openai_answer(question, history=()):
    """A short spoken answer to a web question from OpenAI's web search, or None (no key, no internet, too slow).
    history: earlier (heard, said) pairs of the conversation."""
    if not openai_ready():
        return None
    turns = [{"role": r, "content": c} for h, a in list(history)[-OPENAI_HISTORY:] for r, c in (("user", h), ("assistant", a))
             if c and not c.startswith("ACTION:")]
    body = {"model": OPENAI_MODEL, "reasoning": {"effort": "low"}, "tools": [{"type": "web_search"}],
            "instructions": OPENAI_SAY.format(today=datetime.datetime.now().strftime("%A %Y-%m-%d %H:%M")),
            "input": turns + [{"role": "user", "content": question}]}
    req = urllib.request.Request("https://api.openai.com/v1/responses", json.dumps(body).encode(),
                                 {"Authorization": f"Bearer {OPENAI_KEY.read_text().strip()}",
                                  "Content-Type": "application/json"})
    try:
        with _opener().open(req, timeout=OPENAI_WAIT_S) as r:
            out = json.loads(r.read())
    except (OSError, ValueError) as e:
        print(f"openai: {e}", file=sys.stderr)
        return None
    text = " ".join(c.get("text", "") for o in out.get("output", []) if o.get("type") == "message"
                    for c in o.get("content", []))
    text = re.sub(r"\s+", " ", CITATION.sub(lambda m: m.group(1) or "", text)).strip()
    return text or None


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "weather":
        print(weather(" ".join(sys.argv[2:])))
    elif len(sys.argv) > 2 and sys.argv[1] == "search":
        print(search(" ".join(sys.argv[2:])))
    else:
        print(now_text(), "| internet:", online())
