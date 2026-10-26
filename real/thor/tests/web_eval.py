"""Rules-only routing of weather / news questions and weather follow-ups. python web_eval.py"""
import sys
sys.path.insert(0, __file__.rsplit("/tests/", 1)[0])
from assistant import brain, web

WEATHER = {  # text -> place expected ("" = here)
 "what's the weather like": "", "how's the weather today": "", "weather?": "", "weather today": "",
 "is it going to rain today": "", "will it rain tomorrow": "", "do i need an umbrella": "", "is it cold outside": "",
 "what's the temperature outside": "", "what's the forecast for tomorrow": "", "what's the weather this weekend": "",
 "how hot will it be tomorrow": "", "will it snow tomorrow": "", "is it sunny outside": "", "what's the weather in Busan": "Busan",
 "how's the weather in Tokyo today": "Tokyo", "weather in New York": "New York", "what's the weather like in Jeju tomorrow": "Jeju",
 "is it raining in London": "London", "how cold is it in Seoul": "Seoul", "what will the weather be on Saturday": "",
 "weather forecast for next week": "", "should i bring a jacket": "", "is it humid today": "", "is it windy outside": "",
 "날씨 어때": "", "오늘 날씨 어때요": "", "내일 날씨 어때": "", "내일 비 와": "", "내일 비 와요?": "", "비 올까요?": "", "우산 가져가야 돼?": "",
 "밖에 추워?": "", "오늘 기온 몇 도야": "", "주말 날씨 어때요": "", "이번 주 날씨 알려 줘": "", "부산 날씨 어때": "Busan",
 "제주도 날씨 알려 주세요": "Jeju City", "도쿄 날씨는 어때요": "Tokyo", "서울 내일 날씨": "Seoul", "모레 날씨 어떻습니까": "",
 "눈 와?": "", "오늘 더워요?": "", "날씨 좀 알려 줘": "", "오늘 날씨 how": "", "weather 어때": "", "부산 weather 어때": "Busan",
 "today weather 알려 줘": "", "내일 rain 와?": "", "지금 몇 도야": "", "오늘 몇 도예요": "", "밖에 날씨 어때": "",
 "오늘 미세먼지 어때": "", "how many degrees is it": "", "what's it like outside": "", "is it nice out today": "",
 "대구는 오늘 더워요?": "Daegu", "광주 날씨": "Gwangju", "오사카 날씨 어때": "Osaka", "what's the weather in Paris this weekend": "Paris",
 "오늘 날씨 좋아?": "", "is it going to be cold tonight": "", "내일 아침 추워요?": "",
}
WEATHER.update({   # every Korean level, new this night
 "오늘 날씨 어떻습니까": "", "오늘 날씨 어떠세요": "", "날씨가 어떻게 되나요": "", "오늘 날씨 어떻노": "", "날씨 우째 되노": "", "날씨 어뗘": "",
 "내일 날씨 좀 알려 주시겠어요": "", "내일 날씨 알려 주십시오": "", "날씨 좀 알려 줄래": "", "내일 비 옵니까": "", "내일 비 오나요": "",
 "내일 비 오노": "", "비 올 것 같아요": "", "주말에 비 와요": "", "토요일 날씨 어때": "", "모레 날씨 어떠세요": "", "다음 주 날씨는요": "",
 "부산 날씨 어떻습니까": "Busan", "부산 날씨 우째 되노": "Busan", "제주 날씨 알려 주세요": "Jeju", "대구 오늘 더워요": "Daegu",
 "서울 날씨 어떠세요": "Seoul", "내일 서울 비 와": "Seoul", "오늘 춥나요": "", "밖에 춥습니까": "", "오늘 많이 추워요": "",
 "내일 아침 쌀쌀해요": "", "미세먼지 심해요": "", "미세먼지 어떻습니까": "", "황사 와요": "", "우산 챙겨야 돼요": "", "우산 가져가야 됩니까": "",
 "눈 올까요": "", "내일 눈 와": "", "weather 어떻습니까": "", "내일 weather 알려 줘": "", "forecast 좀 알려 주세요": "",
 "what's the weather gonna be like tomorrow": "", "any rain today": "", "is it going to snow this weekend": "",
 "how's the weather looking for saturday": "", "do we need umbrellas today": "", "what's the temperature in Seoul": "Seoul",
 "how cold will it be tonight": "", "is it raining outside": "", "weather for Busan tomorrow": "Busan",
})
NEWS = ["latest news", "what's the latest news", "any news today", "tell me the news", "news please", "what's in the news",
        "today's headlines", "AI news", "any AI news", "sports news", "latest sports news", "tech news", "world news",
        "what happened today", "what's happening in the world", "오늘 뉴스", "오늘 뉴스 알려 줘", "최신 뉴스", "뉴스 알려 주세요",
        "AI 뉴스", "스포츠 뉴스 알려 줘", "요즘 무슨 일 있어", "오늘 무슨 일 있었어", "경제 뉴스", "뉴스 좀 들려줘", "news 알려 줘",
        "오늘 headline 뭐야", "최근 소식 알려 줘", "what's new in tech", "IT 뉴스", "연예 뉴스", "세계 뉴스 알려 줘",
        "who won the game last night", "어제 야구 누가 이겼어", "bitcoin price", "달러 환율 얼마야", "삼성전자 주가 얼마야",
        "who is the president of the US", "미국 대통령이 누구야"]
NEWS += ["뉴스 좀 알려 주시겠어요", "오늘 뉴스 알려 주십시오", "최신 뉴스 있습니까", "요즘 뉴스 뭐 있노", "뉴스 들려줘", "스포츠 소식 알려 줘",
         "경제 뉴스 좀 알려 주세요", "IT 뉴스 있어요", "오늘 헤드라인이 뭐예요", "주요 뉴스 알려 줘", "환율 얼마예요", "달러 환율 어떻게 돼요",
         "비트코인 지금 얼마예요", "코스피 어때요", "any news about AI", "what are today's headlines", "give me the latest news",
         "sports news please", "what's the dollar rate today", "how's the stock market today"]
NOT = ["do you like rainy weather", "what's your favourite weather", "is it hot in here", "you're cool", "날씨 좋아해?",
       "how do you know the weather", "the news is boring", "what's your temperature",
       "어떤 날씨 좋아해", "우산 어디 있어요?", "우산 잃어버렸어요", "where is my umbrella", "실내 너무 더워요", "i like the news", "are you cold", "추워?", "너 더워?"]
FOLLOW = [  # (first question, follow-up, expected place or None for "not a weather follow-up")
 ("what's the weather today", "and tomorrow?", ""), ("what's the weather today", "what about Busan?", "Busan"),
 ("what's the weather today", "and the weekend?", ""), ("what's the weather today", "what about the weekend?", ""),
 ("what's the weather today", "how about Friday?", ""), ("what's the weather today", "and in Tokyo?", "Tokyo"),
 ("what's the weather today", "tomorrow?", ""), ("what's the weather today", "and next week?", ""),
 ("what's the weather today", "the day after?", ""), ("what's the weather today", "what about tonight?", ""),
 ("what's the weather today", "and New York tomorrow?", "New York"), ("what's the weather today", "is it going to rain?", ""),
 ("what's the weather today", "do I need an umbrella then?", ""),
 ("오늘 날씨 어때", "내일은?", ""), ("오늘 날씨 어때", "부산은?", "Busan"), ("오늘 날씨 어때", "주말은요?", ""),
 ("오늘 날씨 어때", "그럼 내일은요?", ""), ("오늘 날씨 어때", "모레는?", ""), ("오늘 날씨 어때", "제주도는요?", "Jeju City"),
 ("오늘 날씨 어때", "부산 내일은?", "Busan"), ("오늘 날씨 어때", "다음 주는?", ""), ("오늘 날씨 어때", "금요일은 어때요?", ""),
 ("오늘 날씨 어때", "그럼 도쿄는?", "Tokyo"), ("오늘 날씨 어때", "비는 와?", ""), ("오늘 날씨 어때", "내일 비 와?", ""),
 ("오늘 날씨 어때", "tomorrow는?", ""), ("what's the weather today", "내일은?", ""), ("오늘 날씨 어때", "what about Busan?", "Busan"),
 ("오늘 날씨 어때", "저녁에는?", ""), ("오늘 날씨 어때", "이번 주말은 어때요?", ""),
 # every Korean level and English, new this night
 ("오늘 날씨 어때", "내일은요?", ""), ("오늘 날씨 어때", "내일은 어떻습니까?", ""), ("오늘 날씨 어때", "내일은 어떠세요?", ""),
 ("오늘 날씨 어때", "내일은 우째 되노?", ""), ("오늘 날씨 어때", "내일은 어뗘?", ""), ("오늘 날씨 어때", "주말엔 어때요?", ""),
 ("오늘 날씨 어때", "주말에는 어떻습니까?", ""), ("오늘 날씨 어때", "주말엔?", ""), ("오늘 날씨 어때", "부산은 어떻노?", "Busan"),
 ("오늘 날씨 어때", "부산은요?", "Busan"), ("오늘 날씨 어때", "그럼 부산은 어떻습니까?", "Busan"), ("오늘 날씨 어때", "대구는 어때?", "Daegu"),
 ("오늘 날씨 어때", "모레는 어떻게 돼요?", ""), ("오늘 날씨 어때", "토요일은요?", ""), ("오늘 날씨 어때", "내일 아침은?", ""),
 ("오늘 날씨 어때", "우산 챙겨야 돼?", ""), ("오늘 날씨 어때", "비 와요?", ""), ("오늘 날씨 어때", "눈은 와?", ""),
 ("오늘 날씨 어때", "추워요?", None), ("오늘 날씨 어때", "미세먼지는요?", ""), ("오늘 날씨 어때", "내일 부산은요?", "Busan"),
 ("오늘 날씨 어때", "다음 주 월요일은?", ""), ("오늘 날씨 어때", "그 다음 날은?", ""), ("부산 날씨 어때", "내일은?", ""),
 ("what's the weather today", "and then?", ""), ("what's the weather today", "what about tomorrow?", ""),
 ("what's the weather today", "how's Saturday looking?", ""), ("what's the weather today", "and the day after tomorrow?", ""),
 ("what's the weather today", "what about Jeju?", "Jeju"), ("what's the weather today", "is it cold?", None),
 ("what's the weather today", "will it snow?", ""), ("what's the weather today", "and this evening?", ""),
 ("what's the weather today", "what about next Monday?", ""), ("what's the weather today", "how about in Seoul?", "Seoul"),
 ("what's the weather today", "should I bring a jacket?", ""), ("what's the weather in Busan", "and tomorrow?", ""),
 ("what's the weather today", "thanks", None), ("오늘 날씨 어때", "좋네", None), ("what's the weather today", "cool", None),
 ("오늘 날씨 어때", "알겠어요", None), ("what's the weather today", "what's your name?", None), ("오늘 날씨 어때", "고마워", None), ("what's the weather today", "okay", None),
]

def run():
    bad = []
    n = ok = 0
    for t, place in WEATHER.items():
        n += 1
        got = brain.intent(t)
        if got and got[0] == "weather" and (not place or place.lower() in (got[1] or "").lower()):
            ok += 1
        else:
            bad.append(f"weather {t!r} -> {got} (want {place!r})")
    for t in NEWS:
        n += 1
        got = brain.intent(t)
        if got and got[0] == "search":
            ok += 1
        else:
            bad.append(f"search  {t!r} -> {got}")
    wrong = 0
    for t in NOT:
        got = brain.intent(t)
        if got and got[0] in ("weather", "search"):
            wrong += 1; bad.append(f"WRONG   {t!r} -> {got}")
    fok = 0
    for first, follow, place in FOLLOW:
        b = brain.Brain()
        b.history = [(first + brain.WEATHER_ASKED, "ACTION: weather -\nIt is clear, 15 degrees.")]
        b.last_lookup = first + brain.WEATHER_ASKED
        rule = brain.intent(follow)                     # the live path: the rules first, the turn before second
        head = {"action": rule[0], "target": rule[1]} if rule and rule[0] in ("weather", "search") else {"action": "none", "target": ""}
        h = b._after(head, follow)
        got = h and h["action"] == "weather" and h["target"]
        if place is None:
            good = not (h and h["action"] == "weather")
        else:
            good = h and h["action"] == "weather" and (h["target"] or "").lower() == place.lower()
        if good: fok += 1
        else: bad.append(f"follow  {first!r} -> {follow!r}: {h} (want {place!r})")
    print("\n".join(bad))
    print(f"first questions {ok}/{n}, wrong on NOT {wrong}/{len(NOT)}, follow-ups {fok}/{len(FOLLOW)}")
run()
