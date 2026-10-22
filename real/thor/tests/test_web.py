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
assert "Naver: 330 m" in out and "lattice tower" in out and "headline" in out, out
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
# a person's private details are never looked up; a place's phone number or a player's club are
for t in ("What's the phone number of Kim Min-jun?", "Where does my coworker Park Ji-hoon live?",
          "What is Son Heung-min's home address?", "옆집 사람 전화번호 찾아줘"):
    assert lumi.private_ask(t), t
for t in ("What's the phone number of the Louvre?", "Where does Son Heung-min play?", "How tall is Son Heung-min?"):
    assert not lumi.private_ask(t), t
print("web ok")
