"""Facts Lumi can look up while talking: date and time (always), weather and web search (needs internet).

The Thor has no internet on the robot network. When it gets some (a LAN cable on the Thor, internet on the
robot's router, or a proxy: set HTTPS_PROXY in proxy.txt next to this file), weather and search work at once.

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
    try:
        g = json.loads(_get("https://geocoding-api.open-meteo.com/v1/search?count=1&name=" + urllib.parse.quote(place)))
        if not g.get("results"):
            return f"I could not find a place called {place}."
        loc = g["results"][0]
        w = json.loads(_get(
            f"https://api.open-meteo.com/v1/forecast?latitude={loc['latitude']}&longitude={loc['longitude']}"
            "&current=temperature_2m,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max&timezone=auto&forecast_days=1"))
        c, d = w["current"], w["daily"]
        return (f"Weather in {loc['name']}: {WEATHER_CODES.get(c['weather_code'], 'unknown')}, "
                f"{c['temperature_2m']:.0f} degrees now, today {d['temperature_2m_min'][0]:.0f} to "
                f"{d['temperature_2m_max'][0]:.0f} degrees, chance of rain {d['precipitation_probability_max'][0]} percent, "
                f"wind {c['wind_speed_10m']:.0f} km/h.")
    except Exception:
        return None


def search(query, n=4):
    """A few web results (title + snippet) as text, or None without internet."""
    try:
        page = _get("https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query))
    except Exception:
        return None
    titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', page, re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page, re.S)
    clean = lambda t: html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
    out = [f"- {clean(t)}: {clean(s)}" for t, s in zip(titles, snippets)][:n]
    return "\n".join(out) if out else "No results."


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "weather":
        print(weather(" ".join(sys.argv[2:])))
    elif len(sys.argv) > 2 and sys.argv[1] == "search":
        print(search(" ".join(sys.argv[2:])))
    else:
        print(now_text(), "| internet:", online())
