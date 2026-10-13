"""Facts Lumi can look up while talking: date and time (always), weather and web search (needs internet).

The robot network has no internet; the Thor reaches it through its own Wi-Fi. A proxy can be set instead
(one line such as http://192.168.10.200:8888 in proxy.txt next to this file, or HTTPS_PROXY).

    python tools.py                  # date/time + is the internet reachable?
    python tools.py weather Seoul
    python tools.py search "JAKA robotics"
"""
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROXY_FILE = HERE / "proxy.txt"          # e.g. http://192.168.10.200:8888 (one line), optional
DEFAULT_PLACE = "Seoul"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux aarch64) LumiRobot/1.0"}
_online = {"time": 0.0, "ok": False}
PLACES = {"seoul": {"name": "Seoul", "latitude": 37.57, "longitude": 126.98}}   # known places: no geocoding request
WEATHER_TTL = 600                        # s a weather answer is reused (each web request takes ~2 s on the Wi-Fi)
_weather = {}                            # place -> (time, text)


def _opener():
    proxy = PROXY_FILE.read_text().strip() if PROXY_FILE.exists() else os.environ.get("HTTPS_PROXY", "")
    handlers = [urllib.request.ProxyHandler({"http": proxy, "https": proxy})] if proxy else []
    return urllib.request.build_opener(*handlers)


def _get(url, timeout=6):
    req = urllib.request.Request(url, headers=UA)
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
                 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 61: "light rain", 63: "rain",
                 65: "heavy rain", 71: "light snow", 73: "snow", 75: "heavy snow", 80: "rain showers",
                 81: "rain showers", 82: "violent rain showers", 95: "thunderstorm", 96: "thunderstorm with hail"}


def weather(place=DEFAULT_PLACE):
    """Current weather and today's range as a short English text, or None without internet."""
    place = (place or DEFAULT_PLACE).strip() or DEFAULT_PLACE
    key = place.lower()
    if key in _weather and time.time() - _weather[key][0] < WEATHER_TTL:
        return _weather[key][1]
    try:
        loc = PLACES.get(key)
        if not loc:
            g = json.loads(_get("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(place)))
            if not g.get("results"):
                return f"I could not find a place called {place}."
            loc = PLACES[key] = g["results"][0]
        w = json.loads(_get(
            f"https://api.open-meteo.com/v1/forecast?latitude={loc['latitude']}&longitude={loc['longitude']}"
            "&current=temperature_2m,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max&timezone=auto&forecast_days=1"))
        c, d = w["current"], w["daily"]
        text = (f"Weather in {loc['name']}: {WEATHER_CODES.get(c['weather_code'], 'unknown')}, "
                f"{c['temperature_2m']:.0f} degrees now, today {d['temperature_2m_min'][0]:.0f} to "
                f"{d['temperature_2m_max'][0]:.0f} degrees, chance of rain {d['precipitation_probability_max'][0]} percent, "
                f"wind {c['wind_speed_10m']:.0f} km/h.")
        _weather[key] = (time.time(), text)
        return text
    except Exception:
        return None


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


def _wikipedia(query, lang):
    """Best-matching Wikipedia article summary + the matching snippets of the top results, or ''."""
    api = f"https://{lang}.wikipedia.org"
    words = [w for w in re.findall(r"\w+", query.lower()) if w not in STOP]
    if "jaka" in words and "robotics" not in words:     # our own maker, not the people called Jaka
        words.append("robotics")
    hits = []
    for q in (" ".join(words), query):                   # the names alone first: "height in metres" misleads search
        if not q:
            continue
        found = json.loads(_get(f"{api}/w/api.php?action=query&list=search&srlimit=3&srprop=snippet&format=json&srsearch="
                                + urllib.parse.quote(q)))   # full-text search, not just title prefixes
        hits = found.get("query", {}).get("search", [])
        if hits:
            break
    if not hits:
        return ""
    words = set(words)
    best = max(hits, key=lambda h: len(words & set(re.findall(r"\w+", h["title"].lower()))))   # title that fits the question
    page = json.loads(_get(f"{api}/api/rest_v1/page/summary/" + urllib.parse.quote(best["title"].replace(" ", "_"))))
    clean = lambda t: html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
    snippets = "; ".join(f"{h['title']}: {clean(h['snippet'])}" for h in hits)
    return f"Wikipedia, {page.get('title', '')}: {page.get('extract', '')[:700]}\nMatching text: {snippets}"


def _news(query, lang, n=4):
    """Latest headlines from Google News for the query, or ''."""
    hl = "ko" if lang == "ko" else "en-US"
    gl = "KR" if lang == "ko" else "US"
    rss = _get(f"https://news.google.com/rss/search?hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}&q="
               + urllib.parse.quote(query))
    items = re.findall(r"<item>.*?<title>(.*?)</title>.*?<pubDate>(.*?)</pubDate>", rss, re.S)[:n]
    return "\n".join(f"- {html.unescape(t)} ({d[:16]})" for t, d in items)


def search(query, n=4):
    """Facts for a question: a Wikipedia summary + the latest news headlines, or None without internet.
    (DuckDuckGo answers the robot with a bot check; Bing returns unrelated pages to scripts.)"""
    lang = "ko" if re.search(r"[가-힣]", query) else "en"
    q = re.sub(r"\b(what|who|whom|is|are|was|were|the|a|an|about|tell me|more|please|latest|news|today'?s?|any|how|"
               r"do|does|did|you|know|can|could|of|lumi)\b|[?,.!]", " ", query, flags=re.I)
    q = re.sub(r"\s+", " ", q).strip() or query
    parts = []
    for fn in (lambda: _wikipedia(q, lang), lambda: _news(q, lang, n)):
        try:
            text = fn()
        except Exception:
            text = None
        if text is None:
            continue
        if text:
            parts.append(text)
    if not parts and not online():
        return None
    return "\n".join(parts) if parts else "No results."


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "weather":
        print(weather(" ".join(sys.argv[2:])))
    elif len(sys.argv) > 2 and sys.argv[1] == "search":
        print(search(" ".join(sys.argv[2:])))
    else:
        print(now_text(), "| internet:", online())
