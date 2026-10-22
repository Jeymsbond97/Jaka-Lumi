"""Follow-ups in a dialogue, written the way English and Korean speakers really continue a conversation: fragments
("and my shoes?", "그럼 내일은?"), anaphora ("how far is it?", "저거"), the question turned back ("and you?", "너는?"),
back-channels ("oh really?", "헐"), corrections ("no, I meant my jeans", "아니 그거 말고"), Korean endings (-지? -네
-잖아 -ㄹ까?) and English indirect requests ("would you mind...", "I wonder if..."), with negative cases where a
fragment must not be over-read. Checked by tests/test_followup.py.

CASES = [{"ctx": [turn, ...], "say", "route", "means", "ans", "must", "act", "lang", "fr"}]
- ctx: the turns before, as lumi.answer() handled them: T(said, reply) talk, S(said) a seeing answer (asked on the
  saved camera frames `fr`), L(said, reply) a web lookup, W(said, reply) a weather lookup, R(said, "go_to p3") a rule.
- route: what lumi.answer() must do with `say`, alternatives split by "|": seeing, search, weather, llm (the
  conversation model answers), closing (a closing word, waits), end, status, act:<action> <target>.
  talk = llm | closing. An action the rules leave to the model is written "act:go_to p3|llm".
- means: what the words mean here, resolved from the turn before (for the reader; the LLM run checks `must`).
- ans: regex the seeing answer / the lookup query / the weather place must match.
- must, act: for the short LLM run (tests/test_followup.py --llm): regexes the reply must match, the action line.
- fr: saved frames, "jacket" (white top, blue jeans, feet out of view) or "room" (plant, cup, laptop, chair, vase).
"""


def T(said, reply):
    return ("talk", said, reply)


def S(said):
    return ("seeing", said, None)


def L(said, reply):
    return ("search", said, reply)


def W(said, reply):
    return ("weather", said, reply)


def R(said, action):
    return ("rule", said, action)


def C(ctx, say, route, means, ans=None, must=(), act=None, fr="jacket"):
    return {"ctx": list(ctx), "say": say, "route": route, "means": means, "ans": ans, "must": list(must), "act": act,
            "fr": fr}


SHIRT = S("What is the color of my t-shirt?")
SHIRT_KO = S("내 티셔츠 무슨 색이야?")
PLANT = S("do you see a plant?")
PLANT_KO = S("화분 보여?")
PRES = L("who is the president of Korea?", "Lee Jae-myung is the president of South Korea.")
PRES_KO = L("한국 대통령이 누구야?", "한국 대통령은 이재명이에요.")
WX = W("what's the weather?", "It's sunny in Seoul, 18 degrees now, up to 21 today.")
WX_KO = W("오늘 날씨 어때?", "서울은 지금 맑고 18도예요. 낮 최고 21도예요.")
AGE_Q = T("how old are you?", "I'm two years old. How about you?")
NAME_Q = T("what's your name?", "Lumi. Easy to remember, I hope. And yours?")
HEAR = T("can you hear me?", "Yes, I can hear you.")
INTRO = T("who made you?", "Cutshion Company developed me, a robot company in Seoul.")
WELL = r"good|great|fine|well|doing|잘|좋"
AGE = r"\b2\b|two|두 ?살|2 ?살"

CASES = [
    # ---------- ellipsis after a clothes question (frames: white top, blue jeans, shoes out of view) ----------
    C([SHIRT], "What about my jeans?", "seeing", "what colour are my jeans", r"jeans look blue"),   # 2026-10-21 live
    C([SHIRT], "What about my shoes?", "seeing", "what colour are my shoes", r"can't see your shoes"),  # 2026-10-21 live
    C([SHIRT], "and my shoes?", "seeing", "what colour are my shoes", r"shoes"),
    C([SHIRT], "Jeans?", "seeing", "what colour are my jeans", r"jeans look blue"),
    C([SHIRT], "how about my trousers?", "seeing", "what colour are my trousers", r"trousers look blue"),
    C([SHIRT], "And my pants?", "seeing", "what colour are my pants", r"pants look blue"),
    C([SHIRT], "what about the jacket?", "seeing", "what colour is my jacket", r"jacket looks white"),
    C([SHIRT], "my shoes?", "seeing", "what colour are my shoes", r"shoes"),
    C([SHIRT], "Okay, and my sneakers?", "seeing", "what colour are my sneakers", r"sneakers"),
    C([SHIRT], "what about my blue jeans?", "seeing", "what colour are my jeans", r"jeans look blue"),
    C([S("what colour are my jeans?")], "and my shirt?", "seeing", "what colour is my shirt", r"shirt looks white"),
    C([S("what am I wearing?")], "what about my shoes?", "seeing", "what colour are my shoes", r"shoes"),
    C([SHIRT_KO], "그럼 바지는?", "seeing", "바지는 무슨 색이야", r"바지는 파란색"),
    C([SHIRT_KO], "신발은?", "seeing", "신발은 무슨 색이야", r"신발이 안 보여"),
    C([SHIRT_KO], "청바지는요?", "seeing", "청바지는 무슨 색이에요", r"청바지는 파란색"),
    C([SHIRT_KO], "바지도?", "seeing", "바지도 무슨 색인지", r"바지는 파란색"),
    C([SHIRT_KO], "내 신발은?", "seeing", "내 신발은 무슨 색이야", r"신발"),
    C([S("제 셔츠 무슨 색이에요?")], "바지는요?", "seeing", "제 바지는 무슨 색이에요", r"바지는 파란색"),
    C([S("What color is my shirt?")], "바지는?", "seeing", "mixed: and my trousers?", r"바지는 파란색"),
    C([SHIRT_KO], "and my jeans?", "seeing", "mixed: 청바지는?", r"jeans look blue"),
    C([SHIRT, T("nice!", "")], "and my jeans?", "seeing", "a back-channel between keeps the topic", r"jeans look blue"),
    C([SHIRT_KO, T("오 대박", "")], "바지는?", "seeing", "a back-channel between keeps the topic", r"파란색"),
    # corrections and repairs of a clothes question
    C([SHIRT], "no, I meant my jeans", "seeing", "what colour are my jeans", r"jeans look blue"),
    C([SHIRT], "I mean my trousers", "seeing", "what colour are my trousers", r"trousers look blue"),
    C([SHIRT], "Sorry, I meant my shoes.", "seeing", "what colour are my shoes", r"shoes"),
    C([SHIRT_KO], "아니 바지 말이야", "seeing", "바지 색 말이야", r"바지는 파란색"),
    C([SHIRT_KO], "아니, 그거 말고 신발", "seeing", "신발 색", r"신발"),
    C([SHIRT_KO], "아니요, 청바지요", "seeing", "청바지 색이요", r"청바지"),
    # not over-read: no clothes question just before
    C([], "What about my jeans?", "llm", "nothing to go with: the model asks or answers in general"),
    C([AGE_Q], "and my shoes?", "llm", "out of the blue after small talk: not the cameras"),
    C([SHIRT], "how about you?", "llm", "what is Lumi wearing / Lumi's colour: about Lumi"),
    C([SHIRT], "what about Japan?", "llm", "not a clothes word: not the cameras"),
    C([SHIRT, NAME_Q], "and my jeans?", "llm", "the clothes were two turns ago with a topic change between"),
    C([SHIRT], "and you?", "llm", "the question turned to Lumi"),
    C([SHIRT_KO], "그럼 너는?", "llm", "the question turned to Lumi"),

    # ---------- ellipsis and anaphora after "do you see ...?" (frames: plant, cup, laptop, chair, vase) ----------
    C([PLANT], "and the cup?", "seeing", "do you see a cup", r"Yes, I see a cup", fr="room"),
    C([PLANT], "what about a laptop?", "seeing", "do you see a laptop", r"laptop", fr="room"),
    C([PLANT], "Chair?", "seeing", "do you see a chair", r"chair", fr="room"),
    C([PLANT], "how far?", "seeing", "how far is the plant", r"metres from me", fr="room"),
    C([PLANT], "how far is it?", "seeing", "how far is the plant", r"metres from me", fr="room"),
    C([PLANT], "How far away is that?", "seeing", "how far is the plant", r"metres from me", fr="room"),
    C([PLANT], "and the apple?", "seeing", "do you see an apple", r"No, I don't see an apple", fr="room"),
    C([S("is there a cup?")], "how about a bottle?", "seeing", "is there a bottle", r"bottle", fr="room"),
    C([PLANT_KO], "그럼 컵은?", "seeing", "컵도 보여?", r"컵이 보여", fr="room"),
    C([PLANT_KO], "노트북도?", "seeing", "노트북도 보여?", r"노트북", fr="room"),
    C([PLANT_KO], "얼마나 멀어?", "seeing", "화분은 얼마나 멀어", r"떨어져", fr="room"),
    C([PLANT_KO], "그거 얼마나 멀어?", "seeing", "화분은 얼마나 멀어", r"떨어져", fr="room"),
    C([PLANT_KO], "저거 거리가 얼마나 돼?", "seeing", "화분은 얼마나 멀어", r"떨어져", fr="room"),
    C([S("how far is the plant?")], "and the laptop?", "seeing", "how far is the laptop", r"laptop is about", fr="room"),
    C([S("do you see a red cup?")], "no, I meant a white one", "seeing", "do you see a white cup", r"cup", fr="room"),
    C([S("do you see a red cup?")], "what about the blue one?", "seeing", "do you see a blue cup", r"cup", fr="room"),
    C([S("빨간 컵 보여?")], "아니 파란 거", "seeing", "파란 컵 보여?", r"컵", fr="room"),
    C([S("빨간 컵 보여?")], "흰색은?", "seeing", "흰 컵은 보여?", r"컵", fr="room"),
    C([S("do you see a cup?")], "and a vase?", "seeing", "do you see a vase", r"vase", fr="room"),
    C([S("do you see a laptop?")], "how far is that?", "seeing", "how far is the laptop", r"metres from me", fr="room"),
    C([S("컵 보여?")], "저거 얼마나 멀어?", "seeing", "컵은 얼마나 멀어", r"떨어져", fr="room"),
    # not over-read
    C([], "and the cup?", "llm", "nothing seen was asked about", fr="room"),
    C([T("do you like coffee?", "I don't drink it, but I like the smell.")], "and the cup?", "llm",
      "small talk, not the cameras", fr="room"),
    C([PLANT], "what about you?", "llm", "the question turned to Lumi", fr="room"),
    C([PLANT], "how far is Seoul?", "llm", "a city, not the cameras", fr="room"),
    C([], "how far?", "llm", "nothing to measure", fr="room"),
    C([PLANT], "and Busan?", "llm", "a city, not a thing in view", fr="room"),
    C([AGE_Q], "how far is it?", "llm", "'it' is not a thing seen", fr="room"),

    # ---------- after a web lookup ----------
    C([PRES], "what about Japan?", "search", "who is the prime minister / leader of Japan", r"Japan"),
    C([PRES], "and Japan?", "search", "the same question about Japan", r"Japan"),
    C([PRES], "Japan?", "search", "the same question about Japan", r"Japan"),
    C([PRES], "how about the US?", "search", "who is the president of the US", r"US"),
    C([PRES], "how old is he?", "search", "how old is Lee Jae-myung", r"Lee Jae-myung|old"),
    C([PRES], "When was he elected?", "search", "when was Lee Jae-myung elected", r"elected"),
    C([PRES], "그럼 일본은?", "search", "일본 총리는 누구야", r"일본"),
    C([PRES_KO], "일본은?", "search", "일본은 누가 총리야", r"일본"),
    C([PRES_KO], "그럼 미국은요?", "search", "미국 대통령은 누구예요", r"미국"),
    C([PRES_KO], "아까 그 사람 몇 살이야?", "search", "이재명은 몇 살이야", r"몇 살"),
    C([L("what's the population of Seoul?", "About 9.4 million people live in Seoul.")], "and Busan?", "search",
      "the population of Busan", r"population.*Busan"),
    C([L("what's the population of Seoul?", "About 9.4 million people live in Seoul.")], "what about Tokyo?",
      "search", "the population of Tokyo", r"Tokyo"),
    C([L("Samsung stock price?", "Samsung Electronics trades at about 61,000 won.")], "and Apple?", "search",
      "Apple's stock price", r"stock.*Apple"),
    C([L("Samsung stock price?", "Samsung Electronics trades at about 61,000 won.")], "and yesterday", "search",
      "Samsung's price yesterday", r"yesterday"),
    C([PRES], "why?", "search", "why is he president (more about it)"),
    C([PRES], "no, I meant North Korea", "search", "who leads North Korea", r"North Korea"),
    C([L("한국 인구는?", "한국 인구는 약 5,100만 명이에요.")], "아니 서울 말이야", "search", "서울 인구", r"서울"),
    C([L("who founded Samsung?", "Lee Byung-chul founded Samsung in 1938.")], "when did he die?", "search",
      "when did Lee Byung-chul die", r"die"),
    # back-channels and turn-taking after a lookup: not looked up again
    C([PRES], "oh really?", "talk", "surprise: react briefly"),
    C([PRES], "Really?", "talk", "surprise: react briefly"),
    C([PRES], "wow", "talk", "a reaction"),
    C([PRES], "I see", "llm", "understood: acknowledge, the talk goes on"),
    C([PRES], "interesting", "talk", "a reaction"),
    C([PRES], "That's interesting!", "talk", "a reaction"),
    C([PRES_KO], "헐", "talk", "놀람"),
    C([PRES_KO], "대박", "talk", "놀람"),
    C([PRES_KO], "아 그래?", "talk", "그렇구나"),
    C([PRES_KO], "진짜요?", "talk", "놀람"),
    C([PRES_KO], "그렇구나", "llm", "이해: 짧게 받고 대화는 이어짐"),
    C([PRES], "how about you?", "llm", "the question turned to Lumi (does Lumi follow politics)"),
    C([PRES_KO], "너는?", "llm", "the question turned to Lumi"),
    C([PRES], "thanks", "closing", "thanks for the answer: you're welcome, silence ends"),

    # ---------- after the weather ----------
    C([WX], "and tomorrow?", "search", "tomorrow's weather in Seoul", r"weather.*tomorrow"),
    C([WX], "Tomorrow?", "search", "tomorrow's weather in Seoul", r"weather.*Tomorrow"),
    C([WX], "what about tomorrow?", "search", "tomorrow's weather in Seoul", r"weather.*tomorrow"),
    C([WX], "and the weekend?", "search", "the weather this weekend", r"weather.*weekend"),
    C([WX], "and the day after tomorrow?", "search", "the weather the day after tomorrow", r"weather.*tomorrow"),
    C([WX], "sorry, I meant tomorrow", "search", "tomorrow's weather", r"weather.*tomorrow"),
    C([WX_KO], "그럼 내일은?", "search", "내일 날씨", r"weather.*내일"),
    C([WX_KO], "내일은?", "search", "내일 날씨", r"weather.*내일"),
    C([WX_KO], "주말은요?", "search", "주말 날씨", r"weather.*주말"),
    C([WX], "what about Busan?", "weather", "the weather in Busan", r"Busan"),
    C([WX], "and Tokyo?", "weather", "the weather in Tokyo", r"Tokyo"),
    C([WX], "How about in London?", "weather", "the weather in London", r"London"),
    C([W("what's the weather in Tokyo?", "Tokyo is cloudy, 16 degrees.")], "and Osaka?", "weather",
      "the weather in Osaka", r"Osaka"),
    C([WX_KO], "그럼 부산은?", "weather", "부산 날씨", r"^Busan$"),
    C([WX_KO], "제주도는요?", "weather", "제주 날씨", r"^Jeju City$"),
    C([WX_KO], "그럼 도쿄 날씨는?", "weather", "도쿄 날씨", r"^Tokyo$"),
    C([WX], "and Jeju?", "weather", "the weather in Jeju", r"^Jeju$"),
    C([WX_KO], "그럼 우산은?", "weather", "do I need an umbrella (here)", r"^$"),
    C([WX], "will it rain?", "weather", "will it rain (here, today)"),
    C([WX], "is it cold?", "search|llm", "is it cold today (from the weather just said)"),
    C([WX], "oh nice", "talk", "a reaction"),
    C([WX], "why?", "search", "why is it sunny / more about it"),
    C([WX], "how about you?", "llm", "does Lumi like this weather"),
    C([WX_KO], "너는?", "llm", "루미는 이런 날씨 좋아해?"),
    C([AGE_Q], "and tomorrow?", "llm", "no weather before: not a lookup"),
    C([], "what about tomorrow?", "llm", "nothing to go with"),

    # ---------- the question turned back to Lumi ----------
    C([T("hi Lumi", "Hi! How are you today?")], "I'm fine, and you?", "llm", "how is Lumi", must=[WELL]),
    C([AGE_Q], "I'm 30. And you?", "llm", "how old is Lumi (said again briefly)", must=[AGE]),
    C([T("do you like music?", "I do! Do you like music?")], "Yes, I love it. How about you?", "llm",
      "does Lumi like music"),
    C([T("where are you from?", "I was made by Cutshion Company in Seoul. Where are you from?")],
      "I'm from Tashkent, you?", "llm", "where is Lumi from", must=[r"Cutshion|Seoul|Korea"]),
    C([T("안녕 루미", "안녕하세요! 잘 지내셨어요?")], "네 잘 지냈어요. 루미는요?", "llm", "루미는 잘 지냈어?",
      must=[r"잘|좋"]),
    C([T("몇 살이야?", "저는 두 살이에요. 몇 살이세요?")], "저는 서른 살이에요. 너는?", "llm", "루미는 몇 살",
      must=[AGE]),
    C([T("I like coffee", "Coffee is a great way to start the day.")], "당신은요?", "llm", "does Lumi like coffee"),
    C([T("뭐 좋아해?", "저는 사람들 만나는 게 좋아요. 뭐 좋아하세요?")], "난 피자. 넌?", "llm", "루미는 뭐 좋아해"),
    C([NAME_Q], "I'm Sara. And yourself?", "llm", "Lumi's name again / about Lumi", must=[r"Lumi"]),
    C([T("I'm tired today", "Oh, I hope you can rest soon.")], "what about you, Lumi?", "llm", "is Lumi tired"),
    C([T("I like music", "Music is great!")], "Lumi, and you?", "llm", "does Lumi like music"),
    C([T("I like music", "Music is great!")], "How about you?", "llm", "does Lumi like music"),
    C([T("나 배고파", "배고프시군요. 근처에 식당이 있는지 직원에게 물어보세요.")], "너도?", "llm", "루미도 배고파?"),
    C([T("I'm from Uzbekistan", "Uzbekistan, how wonderful!")], "you?", "llm", "where is Lumi from"),
    C([T("I love pizza", "Pizza is a classic.")], "Me too", "talk", "agreement"),
    C([], "그럼 루미는?", "llm", "nothing before: the model asks what they mean"),
    # a suggestion, not the question turned back
    C([], "how about you go to p3?", "act:go_to p3", "a suggestion: go to p3"),
    C([], "why don't you go to p3?", "act:go_to p3", "a suggestion, not a negation: go to p3"),
    C([], "why don't you wave?", "act:wave", "a suggestion: wave"),
    C([], "how do you go to p3?", "llm", "asks how Lumi drives there, not an order"),
    C([], "how about we go to the kitchen?", "llm", "no such place on the map: say so"),

    # ---------- back-channels after Lumi's own words ----------
    C([INTRO], "oh really?", "talk", "a reaction"),
    C([INTRO], "I see", "llm", "understood: acknowledge, the talk goes on"),
    C([INTRO], "nice", "talk", "a reaction"),
    C([INTRO], "cool", "talk", "a reaction"),
    C([INTRO], "wow", "talk", "a reaction"),
    C([INTRO], "no way!", "talk", "a reaction"),
    C([INTRO], "uh-huh", "talk", "go on"),
    C([INTRO], "Oh, that's cool.", "talk", "a reaction"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "아 그래?", "talk", "그렇구나"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "그렇구나", "llm", "이해: 대화는 이어짐"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "대박", "talk", "놀람"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "헐", "talk", "놀람"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "와", "talk", "감탄"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "오 진짜?", "talk", "놀람"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "아하", "talk", "이해"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "그래요?", "talk", "그렇구나"),
    C([T("컵을 들 수 있어요", "네, 컵이나 병을 들 수 있어요.")], "신기하다", "talk", "감탄"),
    C([SHIRT], "oh wow", "talk", "a reaction to the colour, not a seeing question"),

    # ---------- corrections of talk and of orders ----------
    C([T("how heavy are you?", "About 96 kilograms.")], "no, I meant the arm", "llm", "how heavy is the arm",
      must=[r"9\.9"]),
    C([T("몇 킬로예요?", "약 96킬로그램이에요.")], "아니, 팔 말고 키요", "llm", "키가 얼마예요", must=[r"146|186"]),
    C([T("how much can you carry?", "About 1 kg in my hand.")], "I mean, how tall are you?", "llm",
      "how tall is Lumi", must=[r"146|1\.46|186"]),
    C([R("go to p3", "go_to p3")], "no, I meant p4", "act:go_to p4|llm", "go to p4 instead", act="go_to"),
    C([R("p5로 가", "go_to p5")], "아니 p5 말고 p4", "act:go_to p4|llm", "p4로 가", act="go_to"),

    # ---------- Korean: endings, dropped subjects, honorific and casual ----------
    C([], "너 두 살이지?", "llm", "-지: confirm that Lumi is two", must=[AGE + r"|네|맞"]),
    C([], "컵이 있네", "talk", "-네: noticing a cup, not an order"),
    C([], "같이 사진 찍을까?", "llm", "-ㄹ까: a suggestion (a photo together)"),
    C([], "너 컵 잡을 수 있잖아", "llm", "-잖아: a reminder, not an order to pick"),
    C([], "근데 날씨 어때?", "weather", "근데: a topic shift to the weather"),
    C([AGE_Q], "그래서 몇 살이라고?", "llm", "asks the age again", must=[AGE]),
    C([], "그럼 p3로 가 줘", "act:go_to p3|llm", "go to p3", act="go_to"),
    C([], "p3로 갈까?", "act:go_to p3|llm", "-ㄹ까: shall we go to p3 (go)", act="go_to"),
    C([], "왼쪽 좀 볼래?", "act:look left", "-ㄹ래: a soft request to look left"),
    C([], "몇 살이야?", "llm", "casual: how old are you", must=[AGE]),
    C([], "연세가 어떻게 되세요?", "llm", "honorific: how old are you", must=[AGE]),
    C([], "신발 무슨 색이에요?", "seeing", "polite: what colour are my shoes", r"신발"),
    C([], "제 바지 무슨 색인가요?", "seeing", "polite: what colour are my trousers", r"바지는 파란색"),
    C([], "날씨 좋네", "weather|llm", "-네: a remark on the weather (a lookup is fine too)"),

    # ---------- English indirect requests and rhetorical questions ----------
    C([], "I wonder if it'll rain tomorrow", "weather|search|llm", "will it rain tomorrow", act="weather"),
    C([], "do you happen to know the weather in Paris?", "weather", "the weather in Paris", r"Paris"),
    C([], "would you mind going to p3?", "act:go_to p3|llm", "go to p3", act="go_to"),
    C([], "would you mind waving?", "act:wave|llm", "wave", act="wave"),
    C([], "could you possibly look to the left?", "act:look left", "look left"),
    C([], "I was wondering if you could come here", "act:come", "come here"),
    C([], "it would be great if you could wave", "act:wave", "wave"),
    C([], "would you mind telling me your name?", "llm", "what is your name", must=[r"Lumi"]),
    C([], "isn't it a lovely day?", "llm", "a remark, not a weather lookup"),
    C([], "who doesn't love pizza?", "llm", "rhetorical: no lookup, no person to find"),
    C([], "can you believe it?", "llm", "a reaction"),
    C([], "mind if I take a photo?", "llm", "asking permission for a photo, not a pick"),
    C([], "let me ask you something", "llm", "a pre-sequence: wait for the question"),
    C([], "do you happen to know what time it is?", "llm", "what time is it"),
    # ---------- understanding, a check, an ambiguous "okay" / "thank you", a real closing (lumi.talk_fate) ----------
    # 2026-10-21 live: "Thank you." after "Yes, I can hear you." ended the talk at once; "I see" / "그렇구나" alone too
    C([HEAR], "Thank you.", "closing", "thanks for the answer, not goodbye: you're welcome, silence ends"),
    C([INTRO], "got it", "llm", "understood: acknowledge, go on"),
    C([INTRO], "okay I see", "llm", "understood"),
    C([INTRO], "Okay, I see.", "llm", "understood"),
    C([INTRO], "makes sense", "llm", "understood"),
    C([INTRO], "That makes sense.", "llm", "understood"),
    C([INTRO], "Uh huh.", "llm", "go on"),
    C([INTRO], "I see?", "llm", "a check: confirm the last point", must=[r"Cutshion|yes|right|that's"]),
    C([INTRO], "is that so?", "llm", "a check: confirm the last point", must=[r"Cutshion|yes|right|that's"]),
    C([INTRO], "Really? I see.", "llm", "surprise, then understood"),
    C([INTRO], "okay", "closing", "heard: wait, silence ends"),
    C([INTRO], "thank you", "closing", "thanks for the answer: you're welcome"),
    C([INTRO], "got it, thanks", "closing", "understood and thanks: you're welcome, silence ends"),
    C([INTRO], "okay, bye", "end", "a real closing"),
    C([INTRO], "thanks, that's all", "end", "a real closing"),
    C([INTRO], "that's it, thank you", "end", "a real closing"),
    C([INTRO], "see you", "end", "a real closing"),
    C([INTRO], "thank you for your time", "end", "a real closing"),
    C([INTRO], "okay, and how tall are you?", "llm", "goes on with a new question"),
    C([INTRO], "I see, who works there?", "llm|search", "goes on with a new question"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "아 그렇구나", "llm", "이해"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "알겠어요", "llm", "이해"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "그렇군요", "llm", "이해"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "아, 그랬구나", "llm", "이해"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "네 알겠습니다", "llm", "이해"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "그런가요?", "llm", "확인: 마지막 말을 짧게 다시",
      must=[r"쿳션|네|맞"]),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "정말?", "llm", "확인"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "그렇구나?", "llm", "확인"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "네", "closing", "들었음: 기다림, 침묵이면 끝"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "감사합니다", "closing", "답에 대한 감사: 천만에요"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "네 감사합니다", "closing", "답에 대한 감사"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "됐어요 고마워요", "end", "진짜 끝"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "안녕히 계세요", "end", "진짜 끝"),
    C([T("누가 만들었어?", "쿳션 컴퍼니에서 만들었어요.")], "알겠어요 근데 몇 살이에요?", "llm", "새 질문"),
    C([INTRO], "아 I see", "llm", "mixed: understood"),
    C([INTRO], "oh 그렇구나", "llm", "mixed: understood"),
    C([INTRO], "Okay, 알겠어요", "llm", "mixed: understood"),
    C([INTRO], "오케이 땡큐", "closing", "mixed: thanks"),
    C([INTRO], "okay 감사합니다", "closing", "mixed: thanks"),
    C([INTRO], "Thanks, Lumi.", "closing", "thanks for the answer"),
]

from tests.followup_cases_more import CASES_MORE  # noqa: E402 - written later (2026-10-21 night), uses the helpers above
CASES += CASES_MORE
