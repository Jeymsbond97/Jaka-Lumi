"""Weather talks of several turns (English, Korean, mixed): a follow-up keeps the topic and the place and moves the
day ("and tomorrow?", "모레는요?", "next Monday?", "what about Busan?", "the weather then?" after a date answer); a
day past or beyond the 7-day forecast is said plainly. Checked without the internet or the LLM, on a fake forecast
with today fixed (Friday 23 October 2026): the route lumi.answer() takes (keyword rule, else brain._after on the
model's "none" or "search"), the place, the days (web.asked_day: 0 today, 1 Saturday ... 6 Thursday) and the forecast
lines the answer is made from. python tests/dialogues_weather.py (also run by tests/test_web.py)

W(text, place, days): a weather lookup at `place` ("" = here, Seoul) for `days` (None = the whole forecast).
S(text, said): a turn answered by talk (the model's own answer, e.g. a date). N(text): not a weather lookup.
"""
import datetime

from assistant import brain, web

TODAY = datetime.date(2026, 10, 23)     # a Friday
MARKS = ["home", "dock2", "p1", "p2"]


def W(text, place, days, llm="none"):
    return {"text": text, "place": place, "days": days, "llm": llm}


def S(text, said):
    return {"text": text, "said": said}


def N(text):
    return {"text": text, "place": None}


FAR, PAST = "too far ahead", "already past"
DIALOGUES = [
    # the owner's talk of 2026-10-23 15:37 (logs/lumi.log), Korean and English
    [W("오늘 날씨 어때요?", "", [0]), W("내일 어때요?", "", [1], "search"), W("다음 주 월요일 어때요?", "", [3], "search"),
     W("날씨 어때요?", "", [3])],
    [W("How is the weather today?", "", [0]), W("And tomorrow?", "", [1]), W("What about next week Monday?", "", [3]),
     W("And the weather?", "", [3])],
    # a date answered first, then "the weather then?"
    [S("What date is next Monday?", "Next Monday is the 26th of October."), W("And the weather then?", "", [3])],
    [S("다음 주 월요일이 며칠이에요?", "다음 주 월요일은 10월 26일이에요."), W("그날 날씨는요?", "", [3])],
    [S("What day is it tomorrow?", "Tomorrow is Saturday."), W("How's the weather?", "", [1])],
    # the day moves, the place stays
    [W("What's the weather in Busan?", "Busan", None), W("And tomorrow?", "Busan", [1]), W("And Sunday?", "Busan", [2])],
    [W("부산 날씨 어때요?", "Busan", None), W("내일은요?", "Busan", [1]), W("모레는요?", "Busan", [2])],
    [W("제주 날씨 알려줘", "Jeju City", None), W("그럼 토요일은 비 와요?", "Jeju City", [1])],
    [W("Weather in Tokyo tomorrow?", "Tokyo", [1]), W("How about the day after?", "Tokyo", [2]),
     W("And the day after that?", "Tokyo", [3])],
    [W("내일 날씨 어때?", "", [1]), W("그 다음 날은?", "", [2]), W("다음날은요?", "", [3])],
    # the place moves, the day stays
    [W("Will it rain tomorrow?", "", [1]), W("What about Busan?", "Busan", [1]), W("And Daegu?", "Daegu", [1])],
    [W("내일 비 와요?", "", [1]), W("그럼 부산은?", "Busan", [1])],
    [W("What's the weather on Saturday?", "", [1]), W("What about Busan on Sunday?", "Busan", [2])],
    [W("오늘 서울 날씨 어때요?", "Seoul", [0]), W("부산은 내일 어때요?", "Busan", [1])],
    # weekends and weeks
    [W("What's the weather this weekend?", "", [1, 2]), W("And next weekend?", "", [8, 9])],
    [W("이번 주말 날씨 어때요?", "", [1, 2]), W("다음 주 수요일은요?", "", [5])],
    [W("주말에 비 와요?", "", [1, 2]), W("일요일은?", "", [2])],
    [W("How's the weather next week?", "", [3, 4, 5, 6, 7, 8, 9])],
    [W("Will it rain this week?", "", [0, 1, 2])],
    # beyond the forecast, in the past
    [W("What's the weather next Friday?", "", [7]), W("And Thursday?", "", [6])],
    [W("다음 주 토요일 날씨 어때요?", "", [8]), W("그럼 화요일은?", "", [4])],
    [W("Weather in 10 days?", "", [10])],
    [W("어제 날씨 어땠어요?", "", [-1]), W("오늘은요?", "", [0])],
    [W("What was the weather yesterday?", "", [-1]), W("And tomorrow?", "", [1])],
    # mixed English and Korean
    [W("내일 weather 어때?", "", [1]), W("And Busan 내일은?", "Busan", [1])],
    [W("What's the weather in Seoul?", "Seoul", None), W("모레는?", "Seoul", [2])],
    [W("오늘 날씨?", "", [0]), W("And Monday?", "", [3])],
    # in three days, today's own weekday
    [W("What will the weather be in three days?", "", [3]), W("And Friday?", "", [0])],
    [W("3일 후 날씨 어때요?", "", [3]), W("글피는요?", "", [3])],
    # the day moves through a long talk, a remark in between ends the follow-up
    [W("Weather today?", "", [0]), W("Tomorrow?", "", [1]), W("And Sunday?", "", [2]), W("What about Monday?", "", [3]),
     W("And Tuesday?", "", [4])],
    [W("오늘 날씨 어때요?", "", [0]), N("고마워요"), W("날씨 어때요?", "", None)],
    [W("What's the weather like tomorrow?", "", [1]), N("Thanks, see you tomorrow!")],
    [W("내일 기온 몇 도예요?", "", [1]), W("다음 주 월요일은요?", "", [3]), W("부산은요?", "Busan", [3])],
]


class _Date(datetime.date):
    @classmethod
    def today(cls):
        return TODAY


def forecast(place):
    days = [(TODAY + datetime.timedelta(days=i)).strftime("%A %d %B") for i in range(web.WEATHER_DAYS)]
    lines = [f"Today ({days[0]})" if i == 0 else f"Tomorrow ({days[1]})" if i == 1 else d for i, d in enumerate(days)]
    return f"Weather in {place or 'Seoul'} now: clear sky, 15 degrees, wind 3 km/h.\n" + \
        "\n".join(f"{n}: partly cloudy, {8 + i} to {18 + i} degrees, chance of rain {10 * i} percent." for i, n in enumerate(lines))


def check():
    saved = web.datetime
    web.datetime = type("dt", (), {"date": _Date, "timedelta": datetime.timedelta})
    try:
        for n, talk in enumerate(DIALOGUES):
            b = brain.Brain()
            for turn in talk:
                text, where = turn["text"], f"dialogue {n}: {turn['text']!r}"
                if "said" in turn:
                    b.history.append((text, f"ACTION: none -\n{turn['said']}"))
                    continue
                rule = brain.intent(text, MARKS)
                if rule and rule[0] == "weather":
                    target = rule[1]
                else:
                    h = b._after({"action": turn.get("llm", "none"), "target": text}, text)
                    target = h["target"] if h["action"] == "weather" else None
                if turn["place"] is None:
                    assert target is None, (where, "not weather", target)
                    b.history.append((text, "ACTION: none -\nYou're welcome."))
                    continue
                assert target is not None, (where, "not routed to the weather", rule)
                place = b.weather_place(target, text)
                days = b.weather_on(text)
                assert (place, days) == (turn["place"], turn["days"]), (where, place, days)
                facts = web.weather_on(forecast(place), days, TODAY)
                for d in days or []:
                    name = (TODAY + datetime.timedelta(days=d)).strftime("%A %d %B")
                    line = next((l for l in facts.split("\n") if name in l), "")
                    assert line and ((FAR in line) == (d >= web.WEATHER_DAYS)) and ((PAST in line) == (d < 0)), (where, facts)
                if days:
                    assert len(facts.split("\n")) == len(days) + 1, (where, facts)   # no other day's line
                asked = text + brain.WEATHER_ASKED
                b.history.append((asked, "It will be partly cloudy."))
                b.last_lookup = asked
    finally:
        web.datetime = saved
    return len(DIALOGUES)


if __name__ == "__main__":
    print(f"weather dialogues ok: {check()}")
