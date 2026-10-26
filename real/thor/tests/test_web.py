"""Self-check of the web lookup without the internet or the LLM: python tests/test_web.py

The search words made from a question, the parts of a Naver page that are kept, the sources put together (and
DuckDuckGo when Naver gives nothing), and what a follow-up of a lookup searches for. Live answers: tests/web_check.py."""
import datetime

from assistant import brain, lumi, web

# English questions become search words; Korean stays as it is
for q, words in {"How tall is Son Heung-min?": "height Son Heung-min", "How long is the Han River?": "length Han River",
                 "Who won the Nobel Prize in Literature in 2024?": "winner Nobel Prize in Literature in 2024",
                 "What time does the Louvre open?": "hours Louvre open", "Who is Faker?": "Faker",
                 "오늘 달러 환율 얼마야?": "오늘 달러 환율 얼마야?"}.items():
    assert web.keywords(q) == words, (q, web.keywords(q))

# English questions about a person, a share, an index or a team also ask Naver with the Korean word of its box
for q, box in {"How old is Taylor Swift?": "Taylor Swift 나이", "What is Nvidia's stock price today?": "Nvidia 주가",
               "What's the Nasdaq doing today?": "Nasdaq 지수", "How did LAFC do in their last match?": "LAFC 경기 결과",
               "What time does the Louvre open?": None, "Who is the pope?": None,
               "손흥민 나이": None}.items():
    assert web.ko_box_query(q) == box, (q, web.ko_box_query(q))

# a Naver page: answer box and web result kept, ad / influencer blocks and the page furniture left out
PAGE = ('<html><div class="_scrollLog"><section class="sc_new cs_nexchangerate"><b>미국 USD</b> 1,328.40 원 '
        '새 창 열림 전일대비 상승 5.10</section></div>'
        '<div class="_scrollLog"><div class="sc_new ad_section">달러환율 관련 광고 쿠팡 7,000 원</div></div>'
        '<div class="_scrollLog" data-meta-ssuid="influencer">네이버 메이트 지식인 858만 인용 영어 문법</div>'
        '<div class="_scrollLog" data-meta-ssuid="web"><a>Eiffel Tower</a> is 330 m tall to the tip. '
        '<script>var x = 1;</script>Keep에 저장</div></html>')
calls = []
web._get = lambda url, timeout=6, headers=web.UA: calls.append(url) or PAGE
text = web._naver("달러 환율")
assert [web.en_place(p) for p in ("부산", "부산시", "제주도", "Jeju", "Tokyo", "우산")] == \
    ["Busan", "Busan", "Jeju City", "Jeju City", "Tokyo", "우산"]   # the geocoder finds 부산 / "Jeju" wrong
assert "1,328.40 원" in text and "330 m tall" in text, text
assert not any(w in text for w in ("광고", "쿠팡", "인용", "새 창", "var x", "Keep")), text

# search(): the sources together; Naver empty -> DuckDuckGo; nothing anywhere -> "No results." (online)
web._naver = lambda q: "Naver: 330 m"
web._wikipedia = lambda q, lang: "Eiffel Tower: a lattice tower in Paris"
web._news = lambda q, lang, n=4: "- headline"
web._duckduckgo = lambda q: "DDG: 330 m"
web.online = lambda: True
out = web.search("How tall is the Eiffel Tower?")
assert "Naver: 330 m" in out and "lattice tower" in out and "headline" not in out, out   # news only for what changes
assert "headline" in web.search("Who is the president of France now?")
web._naver = lambda q: ""
assert "DDG: 330 m" in web.search("height of the Lotte World Tower")
web._naver = web._wikipedia = web._duckduckgo = web._news = lambda *a: ""
assert web.search("something nobody wrote about") == "No results."
web.online = lambda: False
assert web.search("something else nobody wrote about") is None
web._naver = lambda q: (_ for _ in ()).throw(TimeoutError())       # a source that fails is left out
web._wikipedia = lambda q, lang: "Wiki text"
web.online = lambda: True
assert web.search("a failing source") == "Wikipedia:\nWiki text"

# follow-ups of a lookup go with the topic of that lookup and the names its answer gave, without the words that only
# ask for more; a new question is searched as it is
b = brain.Brain()
assert b.search_query("Who is the CEO of Nvidia?") == "Who is the CEO of Nvidia?"
b.history, b.last_lookup = [("Who is the CEO of Nvidia?", "It is Jensen Huang. He co-founded it.")], "Who is the CEO of Nvidia?"
assert b.search_query("Who is the CEO of Nvidia? And his age?") == "Who is the CEO of Nvidia? Jensen Huang his age"
assert b.search_query("Where was he born?") == "Who is the CEO of Nvidia? Jensen Huang Where was he born"   # LLM's query
b.history.append(("And his age?", "He is 63.")); b.last_lookup = "And his age?"
assert b.search_query("And his age? Where was he born?") == "Who is the CEO of Nvidia? Where was he born"
assert b.search_query("And the yen?") == "Who is the CEO of Nvidia? the yen"
assert b.search_query("Tell me more.") == "Who is the CEO of Nvidia?"
assert b.search_query("더 알려줘") == "Who is the CEO of Nvidia?"
assert b.search_query("Why did Samsung stock fall so much today?") == "Why did Samsung stock fall so much today?"
b = brain.Brain()
b.search_query("손흥민 지금 어느 팀이야?")
b.history, b.last_lookup = [("손흥민 지금 어느 팀이야?", "LAFC 소속이에요.")], "손흥민 지금 어느 팀이야?"
assert b.search_query("몇 살이야?") == "손흥민 지금 어느 팀이야? 몇 살이야"
assert b.search_query("에펠탑 높이는 얼마나 되나요 정확하게?") == "에펠탑 높이는 얼마나 되나요 정확하게?"

# the weather: now and the days ahead, today and tomorrow named
web._get = lambda url, timeout=6, headers=web.UA: (
    '{"current": {"temperature_2m": 10.4, "weather_code": 0, "wind_speed_10m": 9.8}, "daily": {"time": ["2026-10-21", '
    '"2026-10-22", "2026-10-23"], "weather_code": [61, 0, 3], "temperature_2m_max": [15.2, 14.4, 17.8], '
    '"temperature_2m_min": [7.6, 4.5, 7.0], "precipitation_probability_max": [92, 0, 2]}}')
w = web.weather("Seoul")
assert w.startswith("Weather in Seoul now: clear sky, 10 degrees, wind 10 km/h.") and \
    "Tomorrow (Thursday 22 October): clear sky, 4 to 14 degrees, chance of rain 0 percent." in w and \
    "\nFriday 23 October: overcast" in w, w

# "how far": the straight-line distance of the two places (one named: from Seoul); a small namesake is not taken
import re
web.PLACES["busan"] = {"name": "Busan", "latitude": 35.18, "longitude": 129.08, "population": 3400000}
assert re.search(r"Seoul to Busan: about 3\d\d km", web._distance("부산까지 거리가 얼마나 돼?"))
assert re.search(r"Busan to Seoul: about 3\d\d km", web._distance("How far is Busan from Seoul by car?"))
web._get = lambda url, timeout=6, headers=web.UA: '{"results": [{"name": "Moon-sur-Elle", "latitude": 49.2, ' \
    '"longitude": -1.0, "population": 700}]}'
assert web._distance("How far away is the moon?") == "" and web._distance("How tall is the Eiffel Tower?") == ""

assert "Busan to Seoul" in web._distance("Busan distance from Seoul")
assert "Incheon Airport to Seoul" in web._distance("Incheon Airport distance from Seoul")   # not "Incheon" "Airport"

# respond_from: an action line the model writes instead of the answer is never said; all of it: asked once more
outs = iter([["search New York", " weather"], ["It is 15 degrees", " in New York."]])
real_stream, brain._stream = brain._stream, lambda m: iter(next(outs))
assert list(brain.Brain().respond_from("What's the weather in New York?", "15 degrees")) == ["It is 15 degrees in New York."]
outs = iter([["search NY weather\n", "It is 15 degrees. Clear."]])
assert list(brain.Brain().respond_from("Weather?", "x")) == ["It is 15 degrees.", "Clear."]
outs = iter([["Search results say 330 m."]])
assert list(brain.Brain().respond_from("Eiffel?", "x")) == ["Search results say 330 m."]
# "Let me check." is said by lumi before the lookup: never again inside the answer
outs = iter([["Let me check. It is 15 degrees. 확인해 볼게요."]])
assert list(brain.Brain().respond_from("Weather?", "x")) == ["It is 15 degrees."]

# the days a weather question asks (today: Friday 23 October 2026), and only their lines of the forecast
fri = datetime.date(2026, 10, 23)
for q, days in {"오늘 날씨": [0], "and tomorrow?": [1], "모레는요?": [2], "내일모레": [2], "next Monday?": [3],
                "다음 주 월요일 어때요?": [3], "this weekend": [1, 2], "이번 주말": [1, 2], "and Friday?": [0],
                "next Friday": [7], "yesterday": [-1], "어제": [-1], "in 2 days": [2], "사흘 뒤": [3], "what about Busan?": None,
                "the day after": [2], "tomorrow는?": [1], "weekend는?": [1, 2], "다음 주말은?": [8, 9], "저녁에는?": [0],
                "in the evening?": [0], "밤에는?": [0]}.items():
    assert web.asked_day(q, [1], fri) == days, (q, web.asked_day(q, [1], fri))
week = "Weather in Seoul now: clear sky, 15 degrees.\n" + "\n".join(
    f"{(fri + datetime.timedelta(days=i)).strftime('%A %d %B')}: rain." for i in range(7))
assert web.weather_on(week, [3], fri) == "Forecast for Seoul:\nMonday 26 October: rain."
assert web.weather_on(week, [0], fri).startswith("Weather in Seoul now") and web.weather_on(week, None, fri) == week
assert "too far ahead, the forecast reaches only to Thursday 29 October" in web.weather_on(week, [9], fri)
assert "already past" in web.weather_on(week, [-1], fri)
from tests import dialogues_weather                          # 30+ weather talks, EN / KO / mixed
dialogues_weather.check()
# respond_stream: "search ..." under "ACTION: none" or without "ACTION:" is the lookup, never said; its words are not
# the query
outs = iter([["ACTION: none -\n", "search Lotte World", " ticket price"]])
brain._stream = lambda m: iter(next(outs))
real_search, brain.knowledge.search = brain.knowledge.search, lambda *a, **k: []      # no embedding server asked
assert next(brain.Brain().respond_stream("How much is a ticket for Lotte World?", ["p1"])) == \
    {"action": "search", "target": "How much is a ticket for Lotte World?"}
outs = iter([["search I'll look", " that up.\n"]])
assert next(brain.Brain().respond_stream("Who is the CEO of Nvidia now?", ["p1"]))["target"] == "Who is the CEO of Nvidia now?"
outs = iter([["ACTION: none -\n", "Hi!"]])
assert list(brain.Brain().respond_stream("Hello Lumi", ["p1"])) == [{"action": "none", "target": ""}, "Hi!"]
outs = iter([["ACTION: none -\n", "I'm Lumi, nice to meet you."]])
assert list(brain.Brain().respond_stream("Who are you?", ["p1"]))[1:] == ["I'm Lumi, nice to meet you."]
brain._stream, brain.knowledge.search = real_stream, real_search

# the names of a Korean answer go with a follow-up; "there" after a talk answer goes with its place
b = brain.Brain()
b.search_query("오픈AI CEO가 누구야?")
b.history, b.last_lookup = [("오픈AI CEO가 누구야?", "오픈AI의 CEO는 샘 올트먼이에요.")], "오픈AI CEO가 누구야?"
assert b.search_query("몇 살이야?") == "오픈AI CEO가 누구야? 샘 올트먼 몇 살이야"
b = brain.Brain()
b.history = [("What is the capital of Canada?", "ACTION: none -\nThe capital of Canada is Ottawa.")]
assert b.search_query("How many people live there?") == "What is the capital of Canada? Ottawa How many people live there"
b = brain.Brain()
b.search_query("What time does Lotte World open?")
b.history, b.last_lookup = [("What time does Lotte World open?", "At 10.")], "What time does Lotte World open?"
assert b.search_query("How much is a ticket?") == "What time does Lotte World open? How much is a ticket"
assert b.search_query("Who won the 2025 World Series?") == "Who won the 2025 World Series?"
# a weather question without a place: the place of the weather before in this talk; "here" is here
b = brain.Brain()
assert b.weather_place("Jeju", "제주 날씨 알려줘") == "Jeju" and b.weather_place("", "내일 비 와?") == "Jeju"
assert b.weather_place("", "what about the weather here?") == "" and b.weather_place("", "and tomorrow?") == ""
b.weather_place("Busan"); b.reset()
assert b.weather_place("", "내일 비 와?") == ""

# ages worked out from birth dates in the results; money questions get rates, others do not
assert web.with_ages("Han Kang (born 27 November 1970)", datetime.date(2026, 10, 20)) == \
    "Han Kang (born 27 November 1970 (55 years old today))"
assert "(34 years old today)" in web.with_ages("출생 1992.07.08. 신체 183cm", datetime.date(2026, 10, 20))
assert web.with_ages("출생 1992.13.40", datetime.date(2026, 10, 20)) == "출생 1992.13.40"
assert web.with_ages("Han Kang (born 1970)", datetime.date(2026, 10, 20)) == "Han Kang (born 1970 (55 or 56 years old today))"
assert "(29 or 30 years old today)" in web.with_ages("1996년생 선수", datetime.date(2026, 10, 20))
web._get = lambda url, timeout=6, headers=web.UA: \
    '{"rates": {"USD": 1, "KRW": 1330.0, "JPY": 150.0}, "time_last_update_utc": "Tue, 20 Oct 2026 00:02"}'
assert "1 Japanese yen = 8.87 Korean won (100 yen = 887 won)" in web._money("엔화 환율 알려줘")
assert "1 US dollar = 1,330.00 Korean won" in web._money("What's the dollar to won exchange rate?")
assert web._money("How tall is the Eiffel Tower?") == ""
assert "100 US dollar = 133,000 Korean won" in web._money("How much is 100 dollars in Korean won?")
assert "10,000 Japanese yen = 88,667 Korean won" in web._money("1만 엔은 한국 돈으로 얼마야?")
# a person's private details are never looked up; a place's phone number or a player's club are
for t in ("What's the phone number of Kim Min-jun?", "Where does my coworker Park Ji-hoon live?",
          "What is Son Heung-min's home address?", "옆집 사람 전화번호 찾아줘",
          "What's my coworker Lee Seo-yeon's salary?", "옆자리 김지훈 씨 연봉 얼마야?"):
    assert lumi.private_ask(t), t
for t in ("What's the phone number of the Louvre?", "손흥민 연봉 얼마야?", "Where does Son Heung-min play?", "How tall is Son Heung-min?"):
    assert not lumi.private_ask(t), t
# lumi.look_up on the free search: "Let me check." first, the answer made while it plays (never OpenAI, no speaker)
import threading
import time
from audio import mouth
lumi.log = lambda msg: None
web.openai_ready = lambda: False
events = []


def fake_say_stream(pieces, lang=None, abort=None):
    """Like mouth.say_stream: a thread pulls the pieces while the ones before play (0.3 s each)."""
    import queue
    q, said = queue.Queue(), []

    def pull():
        for p in pieces:
            events.append(("say", p, time.time()))
            q.put(p)
        q.put(None)
    threading.Thread(target=pull, daemon=True).start()
    while (p := q.get()) is not None:
        said.append(p)
        threading.Event().wait(0.3)
    return " ".join(said)


class FakeBrain:
    weather_place, weather_on = brain.Brain.weather_place, brain.Brain.weather_on
    weather_at, weather_days, history = "", None, []

    def respond_from(self, asked, facts):
        events.append(("llm", asked, time.time()))
        yield "It is 330 metres tall, with the antennas on top."


mouth.say_stream = fake_say_stream
mouth.say = lambda *a, **k: (_ for _ in ()).throw(AssertionError("say() on the free path"))
web.search = lambda target: "Eiffel Tower: 330 m"
L = object.__new__(lumi.Lumi)
L.lang, L.brain, L.speak_abort, L.current = "en", FakeBrain(), lambda: False, None
L.look_up("How tall is the Eiffel Tower?", "search", "Eiffel Tower height")
assert [e[1] for e in events] == ["Let me check.", "How tall is the Eiffel Tower?", "It is 330 metres tall,",
                                  "with the antennas on top."], events
assert events[1][2] - events[0][2] < 0.1, events          # the answer is asked for while "Let me check." plays
web.weather, events[:] = (lambda target: "Weather in Seoul now: clear sky"), []
L.look_up("내일 비 와?", "weather", "")
assert events[1][1] == "내일 비 와? (the weather)", events
web.search, events[:] = (lambda target: None), []
L.look_up("Who won?", "search", "winner")
assert [e[1] for e in events][1].startswith("Sorry, I'm not connected"), events
# the weather follow-up after a weather question: the day or the place moves
for q, place in {"이번 주말은 어때요?": "", "tomorrow는?": "", "부산은?": None, "and Tokyo tomorrow?": "Tokyo"}.items():
    assert brain.weather_follow(q) == place, (q, brain.weather_follow(q))
print("web ok")
