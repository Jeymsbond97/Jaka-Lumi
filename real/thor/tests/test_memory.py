"""Self-check: assistant/memory.py with fakes (no robot, no LLM, no embedding server, a temp folder), EN + KO:
the body state line, seen things ("did you see an apple today?"), talks kept / recalled by meaning / confirmed /
forgotten, 48 h only, facts said earlier in a long talk.   python tests/test_memory.py"""
import json
import tempfile
import time
from pathlib import Path

import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import memory

memory.DIR = Path(tempfile.mkdtemp())
memory.on = True
NOW = time.mktime((2026, 10, 23, 17, 0, 0, 0, 0, -1))      # Friday 17:00 local
HOUR = 3600
memory.clock = lambda: NOW

# ---------- self state ----------
st = {"arm": "look", "gripper": "open", "head": (30.0, -5.0), "look_held": True, "lift": 75.2, "waist": -20.3,
      "place": "dock2", "battery": 64, "charging": True}
lines = memory.state_line(st)
assert lines["arm"] == "Your arm is in its look pose. Your gripper (hand) is open and empty.", lines
assert lines["body"] == ("Your body now: head turned 30° to your left, tilted 5° down, holding a look you were told, "
                         "lift 75 mm, waist -20°, at dock2, battery 64 %, charging."), lines
lines = memory.state_line({"arm": "give", "holding": "the red cup", "head": (0, 0)})
assert lines["arm"] == "Your arm is in its give pose (held out to the visitor). Your gripper is closed, holding the red cup."
assert lines["body"] == "Your body now: head turned ahead, tilted level."
assert memory.state_line({}) == {"arm": "", "body": ""}
assert len(memory.state_line(st)["arm"].split() + memory.state_line(st)["body"].split()) < 45   # ~40 tokens

# ---------- time words ----------
assert memory.when(NOW - 2 * HOUR + 10, "en", NOW) == "today at about 3 pm"
assert memory.when(NOW - 2 * HOUR + 20 * 60, "ko", NOW) == "오늘 오후 3시 20분쯤"
assert memory.when(NOW - 25 * HOUR, "en", NOW) == "yesterday at about 4 pm"
assert memory.when(NOW - 25 * HOUR, "ko", NOW) == "어제 오후 4시쯤"

# ---------- seen things ----------
memory.saw([{"name": "apple", "colour": "red"}, {"name": "cup", "colour": "white"}], "p3", now=NOW - 100 * 60)
memory.saw([{"name": "apple", "colour": "red"}], "p3", now=NOW - 98 * 60)            # the same again: one entry
memory.saw([{"name": "banana", "colour": "yellow"}], "", now=NOW - 26 * HOUR)
memory.saw([{"name": "dog", "colour": None}], "", now=NOW - 50 * HOUR)             # past 48 h: gone
seen = json.loads((memory.DIR / "seen.json").read_text())
assert [e["name"] for e in seen] == ["apple", "cup", "banana"], seen

SEEN = {
    "did you see an apple today?": "Yes, I saw a red apple today at about 3:20 pm, near p3.",
    "Have you seen any apples today?": "Yes, I saw a red apple today at about 3:20 pm, near p3.",
    "did you see a mug?": "Yes, I saw a white cup today at about 3:20 pm, near p3.",
    "did you see a banana today?": "I haven't seen one today. I saw one yesterday at about 3 pm.",
    "did you see a banana yesterday?": "Yes, I saw a yellow banana yesterday at about 3 pm.",
    "did you see a dog?": "I haven't seen one in the last two days.",
    "have you seen a laptop last week?": "I only remember the last two days.",
    "오늘 사과 봤어?": "네, 오늘 오후 3시 20분쯤 p3 근처에서 빨간색 사과를 봤어요.",
    "오늘 사과 보셨어요?": "네, 오늘 오후 3시 20분쯤 p3 근처에서 빨간색 사과를 봤어요.",
    "아까 컵 봤어요?": "네, 오늘 오후 3시 20분쯤 p3 근처에서 흰색 컵을 봤어요.",
    "오늘 바나나 봤어?": "오늘은 바나나를 못 봤어요. 어제 오후 3시쯤에 본 적은 있어요.",
    "어제 바나나 봤어?": "네, 어제 오후 3시쯤 노란색 바나나를 봤어요.",
    "강아지 봤어?": "최근 이틀 동안 개를 못 봤어요.",
    "지난주에 노트북 봤어?": "저는 최근 이틀 동안의 일만 기억해요.",
    "오늘 apple 봤어?": "네, 오늘 오후 3시 20분쯤 p3 근처에서 빨간색 사과를 봤어요.",
    "did you see 사과 today?": "Yes, I saw a red apple today at about 3:20 pm, near p3.",
    "you see apple today?": "Yes, I saw a red apple today at about 3:20 pm, near p3.",
    "사과 see 했어, 오늘?": "네, 오늘 오후 3시 20분쯤 p3 근처에서 빨간색 사과를 봤어요.",
    "last week에 laptop 봤어?": "저는 최근 이틀 동안의 일만 기억해요.",
}
for q, want in SEEN.items():
    got = memory.reply(q, "ko" if any("가" <= c <= "힣" for c in q) and not q.startswith("did") else "en", NOW)
    assert got == want, (q, got)
for q in ["do you see an apple?", "사과 보여?", "have you ever seen an elephant?", "사과 먹어 봤어?", "코끼리 본 적 있어?", "can you see a cup now?", "what do you see?", "did you eat today?",
          "I saw a dog today", "how are you?"]:
    assert memory.reply(q, "en", NOW) is None, q
assert "a red apple today at about 3:20 pm, near p3" in memory.seen_list(NOW)

# ---------- talks ----------
TOPICS = [("bird", "새", "parrot", "앵무"), ("weather", "날씨", "busan", "부산", "rain", "비"), ("battery", "배터리", "charge", "충전")]


def fake_embed(texts):
    """One axis per topic: the words of a topic (EN or KO) point the same way."""
    out = []
    for t in texts:
        t = t.lower()
        v = np.array([sum(t.count(w) for w in ws) for ws in TOPICS] + [0.3], dtype=np.float32)
        out.append(v / np.linalg.norm(v))
    return np.array(out)


def fake_chat(title, summary, facts=(), title_ko="", summary_ko=""):
    return lambda messages, fmt=None: json.dumps({"title": title, "summary": summary, "facts": list(facts),
                                                  "title_ko": title_ko, "summary_ko": summary_ko})


birds = [("what birds live in Korea?", "ACTION: none -\nMagpies are very common here."), ("and parrots?", "ACTION: none -\nOnly as pets.")]
memory.keep_talk(birds, "p1", NOW - 25 * HOUR, fake_chat("Birds", "The visitor asked about birds in Korea.",
                                                                  ["Magpies are common."], "새", "한국의 새에 대해 이야기했어요."),
                 fake_embed, name="james")
memory.keep_talk([("weather in Busan?", "ACTION: weather Busan\nSunny.")] * 2, "t4", NOW - 3 * HOUR,
                 fake_chat("Weather in Busan", "The visitor asked about the weather in Busan; it was sunny.", [],
                           "부산 날씨", "부산 날씨를 물어보셨어요."), fake_embed)
memory.keep_talk([("battery?", "ACTION: none -\n64 %")] * 2, "t5", NOW - 60 * HOUR,
                 fake_chat("Battery", "Old talk.", []), fake_embed)                # past 48 h: never found
talks = json.loads((memory.DIR / "talks.json").read_text())
assert [s["title"] for s in talks] == ["Birds", "Weather in Busan"] and len(talks[0]["vec"]) == 4
assert "vec" in talks[0] and "audio" not in json.dumps(talks)


def ask(q, lang="en"):
    return memory.recall(q, lang, NOW, embed=fake_embed)


assert ask("Do you remember we talked about birds yesterday?") == "Do you mean our talk about birds yesterday at about 4 pm?"
assert ask("yes") == "Yes, I remember. The visitor asked about birds in Korea. Magpies are common."
assert memory._recall["talk"]["title"] == "Birds"
assert ask("remember our chat about the weather?") == "Do you mean our talk about weather in Busan today at about 2 pm?"
assert ask("no") == "I can't remember that."                            # nothing else near: never another talk
assert ask("remember we talked about weather and birds?") == "Do you mean our talk about birds yesterday at about 4 pm?"
assert ask("no") == "Or was it our talk about weather in Busan today at about 2 pm?"
assert ask("no") == "I can't remember that."
assert ask("remember what we said about battery?") == "I can't remember that."     # only past 48 h
assert ask("do you remember our talk last week?") == "I only remember the last two days."
assert ask("what did we talk about yesterday?") == "Yesterday we talked about birds at about 4 pm. Would you like to hear more?"
assert ask("yeah, that one") .startswith("Yes, I remember.")
assert ask("기억나? 어제 새 얘기 했던 거", "ko") == "어제 오후 4시쯤에 새에 대해 이야기한 거 말씀이세요?"
assert ask("네", "ko") == "네, 기억나요. 한국의 새에 대해 이야기했어요."
assert ask("우리 부산 날씨 얘기했던 거 기억나요?", "ko") == "오늘 오후 2시쯤에 부산 날씨에 대해 이야기한 거 말씀이세요?"
assert ask("아니", "ko") == "그건 기억이 안 나요."
assert ask("우리 서울 날씨 얘기했잖아, 기억해?", "ko") == "그건 기억이 안 나요."        # a name said must be the talk's own
assert ask("didn't we talk about the weather in Seoul?") == "I can't remember that."
assert ask("Didn't we have a chat about birds yesterday?").startswith("Do you mean our talk about birds")
memory._recall.update(offered=[], left=[])
assert ask("부산 날씨랑 새 얘기했던 거 기억나요?", "ko") == "오늘 오후 2시쯤에 부산 날씨에 대해 이야기한 거 말씀이세요?"
assert ask("아니", "ko") == "아니면 어제 오후 4시쯤에 새에 대해 이야기한 거 말씀이세요?"
assert ask("아니요", "ko") == "그건 기억이 안 나요."
assert ask("remember the 날씨 talk?") == "Do you mean our talk about weather in Busan today at about 2 pm?"
assert ask("cancel") is None
assert ask("remember our talk about birds?").startswith("Do you mean")
assert ask("remind me what you said") == "I told you that magpies are common."   # in place of a yes
memory._recall.update(offered=[], talk=None)

# the talks of a day listed; a command agreed then read back and asked, never done here
memory.keep_talk(birds, "t6", NOW - 26 * HOUR,
                 lambda m, fmt=None: json.dumps({"title": "Stage show", "summary": "When the show starts.", "facts": [],
                                                 "commands": ["go to the stage at 3 pm"], "title_ko": "무대 공연",
                                                 "summary_ko": ""}), fake_embed)
assert ask("what did we talk about yesterday?") == \
    "Yesterday I talked about Stage show and Birds. Would you like to hear more about one of them?"
assert [s["title"] for s in memory._recall["listed"]] == ["Stage show", "Birds"]
assert ask("어제 우리 무슨 얘기 했지?", "ko") == "어제는 무대 공연, 새에 대해 이야기했어요. 더 듣고 싶은 이야기가 있으세요?"
assert ask("Do what we said yesterday.") == 'Yesterday at about 3 pm we agreed: "go to the stage at 3 pm". Shall I do that now?'
assert "Commands agreed then: go to the stage at 3 pm. Before doing one, read it back and ask." in \
    memory.turn_lines(type("B", (), {"history": [], "window": lambda self: []})(), "yes")
assert ask("어제 말한 거 해 줘.", "ko") == '어제 오후 3시쯤에 이렇게 하기로 했어요: "go to the stage at 3 pm". 지금 할까요?'
assert ask("오늘 하기로 한 거 해.", "ko").startswith("어제 오후 3시쯤에 이렇게 하기로 했어요")   # the one agreed
assert ask("time to do what we planned") .startswith("Yesterday at about 3 pm we agreed")
assert "agreed" not in (ask("don't do what we said") or "")
memory._recall.update(offered=[], talk=None, listed=[])
assert ask("그저께 얘기한 거 기억나?", "ko") == "그건 기억이 안 나요."          # none that day (within 48 h)
for q in ["remember to bring the cup", "I don't remember", "please remember my name", "기억해 줘", "how are you?",
          "what is the weather?", "I remember when I was a kid", "last time I was here it was cold", "do you remember me?",
          "지난번에 왔을 때 추웠어요"]:
    assert ask(q) is None, q

# a named visitor is not told another named visitor's talk
memory.heard("anna")
assert ask("do you remember we talked about birds?") == "I can't remember that."
memory._talk["name"] = None

# forget this: the person's talks go, the talk now is not kept
memory.heard("james")
for q in ["forget this conversation", "please forget what I said", "Don't remember any of this, okay?", "잊어 줘", "대화 기록 지워 주세요", "forget me",
          "Lumi, can you forget our conversation?", "잊어 주세요", "다 잊어버려", "delete my data", "You forget what I say please.",
          "아까 그 토크 포겟해 줘", "내 데이터 딜리트해 주세요", "다 지워 주이소.", "Wipe what we talked about.", "우리 얘기 기억에서 지워 줘."]:
    assert memory.FORGET.search(q), q
for q in ["forget it", "don't forget the cup", "잊지 마", "포겟하지 마", "did you forget me?", "제 이름 잊어버렸어요?", "잊어버렸어?"]:
    assert memory.reply(q, "en", NOW) != memory.FORGOT["en"], q
assert memory.reply("forget our conversation", "en", NOW) == "Okay, I've forgotten our conversation."
assert [s["title"] for s in json.loads((memory.DIR / "talks.json").read_text())] == ["Weather in Busan", "Stage show"]
memory.talk_over(birds)                               # "forget" was said in it: not kept, and nothing runs
assert memory._talk == {"name": None, "track": None, "skip": False}
assert memory.reply("잊어 줘", "ko", NOW) == "네, 우리 대화는 잊을게요."

# talk_over keeps nothing for checks (memory.on False) and for a one-turn talk
memory.on = False
memory.talk_over(birds)
memory.on = True
memory.talk_over(birds[:1])
assert len(json.loads((memory.DIR / "talks.json").read_text())) == 2

# the transcript the LLM sums up has no ACTION lines
tr = memory._transcript(birds + [("wave", "ACTION: wave -")])
assert "ACTION" not in tr and "Lumi: Magpies are very common here." in tr and "Lumi: (did: wave -)" in tr


# ---------- facts said earlier in a long talk ----------
class FakeBrain:
    def __init__(self, history):
        self.history = history

    def window(self):
        return self.history[-4:]


hist = [("Hi, my name is Anvar.", "Nice to meet you."), ("I have 3 kids.", "Lovely."), ("what is a robot?", "..."),
        ("tell me a joke", "..."), ("why?", "..."), ("and then?", "..."), ("ok", "..."), ("cool", "...")]
lines = memory.turn_lines(FakeBrain(hist), "what's my name?")
assert 'Said earlier in this talk by the visitor: "Hi, my name is Anvar." / "I have 3 kids."' in lines, lines
assert 'Earlier in this talk (asked -> you answered): "Hi, my name is Anvar." -> "Nice to meet you."' in lines, lines
assert '"what is a robot?" -> "..."' in lines and "and then" not in lines   # only turns out of the window
assert memory.earlier_facts(hist[:4], 4) == ""                          # all still in the window
hist_ko = [("제 이름은 민준이에요.", "반가워요."), ("저는 부산에서 왔어요.", "멀리서 오셨네요.")] + hist[2:]
assert "민준" in memory.turn_lines(FakeBrain(hist_ko), "내 이름 뭐야?") and "부산" in memory.turn_lines(FakeBrain(hist_ko), "x")
memory._state.update(body="Your body now: lift 75 mm.", at=time.time())
assert memory.turn_lines(FakeBrain([]), "hello").startswith("Your body now: lift 75 mm.")
memory._state.update(line="Your arm is in its look pose.")
assert memory.arm_line() == " Your arm is in its look pose."
memory._state["at"] = 0.0                                                # stale: not given
assert memory.turn_lines(FakeBrain([]), "hello") == "" and memory.arm_line() == ""
assert "a red apple" in memory.turn_lines(FakeBrain([]), "what did you see earlier?")

# ---------- the hand asked about, from the state read lately ----------
memory._state.update(arm="look", gripper="open", holding=None, at=time.time())
for q in ["where is your hand?", "is your hand open?", "Is your gripper closed?", "are you holding anything?",
          "what's in your hand?"]:
    assert memory.reply(q, "en", NOW) == "My arm is in its resting pose, folded in front of me. My hand is open and empty.", q
for q in ["손 어디 있어?", "손 펴져 있어?", "손에 뭐 있어?", "그리퍼 닫혀 있어요?", "팔은 지금 어떤 상태야?"]:
    assert memory.reply(q, "ko", NOW) == "팔은 앞에 접어 둔 기본 자세예요. 손은 펴져 있고, 아무것도 안 들고 있어요.", q
memory._state.update(arm="give", gripper="closed", holding="the red cup")
assert memory.reply("where is your hand?", "en", NOW) == "My hand is held out in front of me. I'm holding the red cup."
assert memory.reply("손에 뭐 있어요?", "ko", NOW) == "손을 앞으로 내밀고 있어요. 손에 빨간색 컵을 들고 있어요."
for q in ["open your hand", "손 펴", "손 펴 줘", "give me your hand", "close your hand", "hand me the cup", "손 줘"]:
    assert memory.reply(q, "en", NOW) is None, q
for q in ["hand open or close?", "what u holding?", "Is anything in your hand?"]:
    assert memory.reply(q, "en", NOW).endswith("I'm holding the red cup."), q
memory._state.update(place="p3", lift=0.0)
assert memory.reply("where are you?", "en", NOW) == "I'm at p3 right now."
assert memory.reply("지금 어디야?", "ko", NOW) == "지금 p3 근처에 있어요."
assert memory.reply("where are you going?", "en", NOW) is None and memory.reply("where are you from?", "en", NOW) is None
for q in ["Um, where are you right now?", "you are where now?", "Which place on the map are you at?", "where you are?",
          "너 지금 어디임?", "지금 있는 곳 어딘가?", "너 지금 어디입니까?", "지금 어디에 계십니까?", "지금 어느 위치에 계세요?",
          "현재 위치가 어디예요?", "너 지금 어디유?", "지금 있는 곳 어데고?", "map에서 어디예요?", "너 지금 어디에 있는지 여쭤봐도 될까요?",
          "so where you at now?", "tell me where you are now", "What's your location right now?", "지금 위치 좀 알려 줘.", "지금 어딨어?",
          "지금 어디 있노?"]:
    assert (memory.reply(q, "en", NOW) or "").startswith(("I'm at p3", "지금 p3")), q
for q in ["Where are you looking?", "where are you taking me?", "지금 어디 보고 있어?", "어디 가?", "지금 어디로 가?",
          "어디서 왔어?", "너 어디 출신이야?", "화장실 어디야?", "입구는 어디예요?"]:
    assert memory.reply(q, "en", NOW) is None, q
assert memory.reply("지금 몸 얼마나 올라가 있어?", "ko", NOW) == "리프트는 맨 아래에 있어요. 몸을 올리지 않은 상태예요."
memory._state.update(lift=75.0)
assert memory.reply("how high is your lift?", "en", NOW) == "My lift is raised 75 millimetres."
memory._state.update(place=None, lift=None)
memory._state["at"] = 0.0
assert memory.reply("where is your hand?", "en", NOW) is None             # not read lately: the LLM, never a guess
memory._state.update(arm=None, gripper=None, holding=None)

# ---------- topic words, names, a topic of this talk, the day before yesterday ----------
assert memory.topic("Do you remember we talked about birds yesterday?") == "birds"
assert memory.topic("what did we talk about yesterday?") == ""
assert memory.topic("고양이 얘기 기억나세요? 어제 했던 거요.") == "고양이"
assert memory.topic("루미야, 어제 나랑 야구 얘기한 거 기억하니?") == "야구"
assert memory.topic("Remember 오늘 아침 노래 얘기?") == "노래"
memory.keep_talk(birds, "p1", NOW - 5 * HOUR, fake_chat("Owls", "Owls hunt at night."), fake_embed, name="james")
memory._talk.update(name=None, track="p1")
assert memory.reply("Do you remember my name?", "en", NOW) == "Yes, you're James."
assert memory.reply("제 이름 기억나요?", "ko", NOW) == "네, James님이시죠."
memory._talk.update(track="p9")
assert memory.reply("Do you remember my name?", "en", NOW) == memory.NO_NAME["en"]
memory._talk.update(track=None)
assert memory.reply("please remember my name", "en", NOW) is None
talk_now = [("tell me about birds", "Many birds migrate south."), ("and the moon?", "It is far.")]
assert memory.recall("what were we saying about birds, remember?", "en", NOW, embed=fake_embed, history=talk_now + [("x", "")]) is None
memory.keep_talk(birds, "t7", NOW - 44 * HOUR, fake_chat("Parrots", "Parrots can talk."), fake_embed)
assert ask("그저께 앵무 얘기 기억나?", "ko") == "그저께 오후 9시쯤에 'Parrots'에 대해 이야기한 거 말씀이세요?"
assert ask("the day before yesterday we talked about the weather, remember?") == "I can't remember that."
memory._recall.update(offered=[], talk=None, listed=[])

# ---------- Korean at every speech level, Konglish, slips (the same meaning, the same answer) ----------
memory.DIR = Path(tempfile.mkdtemp())
memory._talk.update(name=None, track="p2", skip=False)
TOPICS.append(("hangul", "한글", "sejong", "세종"))
TOPICS.append(("cutshion", "쿳션"))


def kept(title, summary, facts, title_ko, summary_ko, facts_ko, hours, commands=()):
    memory.keep_talk(birds, "p2", NOW - hours * HOUR, lambda m, fmt=None: json.dumps(
        {"title": title, "summary": summary, "facts": facts, "commands": list(commands), "title_ko": title_ko,
         "summary_ko": summary_ko, "facts_ko": facts_ko}), fake_embed)


kept("Birds", "Why birds fly south.", ["Many birds migrate south for food in winter."], "새들",
     "새들이 왜 남쪽으로 가는지에 대한 이야기예요.", ["많은 새들이 겨울에 먹이를 찾아 남쪽으로 이동해요."], 25)
kept("Hangul", "Who made Hangul.", ["King Sejong made it in the 15th century."], "한글", "한글을 누가 만들었는지에 대한 이야기예요.",
     ["15세기에 세종대왕이 만들었어요."], 26)
kept("Cutshion", "When Cutshion was founded.", [], "Cutshion", "Cutshion이 언제 세워졌는지에 대한 이야기예요.", [], 27,
     ["go to p3 and wave"])
memory._recall.update(offered=[], talk=None, listed=[], left=[])
BIRDS_KO = "어제 오후 4시쯤에 새들에 대해 이야기한 거 말씀이세요?"
for q in ["어제 새 얘기 했던 거 기억나?", "어제 새 얘기 했던 거 기억나요?", "어제 새에 대해 이야기했던 것을 기억하십니까?",
          "어제 새 얘기한 거 기억하시나요?", "어제 새 얘기 한 거 기억나니?", "어제 새 얘기했던 거 기억하세요?",   # 반말 / 해요체 / 하십시오체 / honorific
          "어제 새 얘기 했던 거 기억나나?", "어제 새 얘기 했던 거 기억 나냐?", "어제 새 얘기 했던 거 기억나노?",       # friendly, dialect
          "어제 새 얘기했던 거 생각나요?", "어제 새 얘기 했잖아, 기억 안 나?", "어제 저랑 새 얘기 나누셨던 거 기억나세요?",
          "루미야 어제 새 얘기한 거 remember 해?", "Remember 어제 새 얘기?", "음 그 어제 새 얘기 기억나?",           # Konglish, fillers
          "잠깐, 시청자분들 위해서 어제 새 얘기 한 거 기억나요?",
          "어제 새 얘기 기억허냐?", "어제 새 얘기 하지 않았어?", "어제 새 얘기 안 했어?"]:            # dialect, negative questions
    memory._recall.update(offered=[], talk=None, listed=[], left=[])
    assert memory.recall(q, "ko", NOW, embed=fake_embed) == BIRDS_KO, (q, memory.recall(q, "ko", NOW, embed=fake_embed))
for q in ["응", "네", "맞아요", "그렇습니다", "어 맞아", "맞제", "ㅇㅇ", "응 그거"]:              # yes at any level
    memory.recall("어제 새 얘기 했던 거 기억나?", "ko", NOW, embed=fake_embed)
    assert (memory.recall(q, "ko", NOW, embed=fake_embed) or "").startswith("네, 기억나요. 새들이 왜 남쪽으로"), (q, memory.recall(q, "ko", NOW, embed=fake_embed))
for q in ["그래서 결론이 뭐였어요?", "그때 뭐라고 했었지?", "그때 뭐라고 하셨죠?", "뭐라고 했는지 다시 말해 줄래?", "그때 point가 뭐였어요?",
          "다시 remind 해 줘, 뭐라고 했어?", "뭐라고 말씀하셨었죠?", "핵심이 뭐였어요?", "그 얘기 좀 자세히 해 줘."]:   # the detail is the facts, in Korean
    assert memory.recall(q, "ko", NOW, embed=fake_embed) == "많은 새들이 겨울에 먹이를 찾아 남쪽으로 이동해요.", q
for q in ["아닙니다", "아냐", "ㄴㄴ", "아뇨, 그거 말고요"]:                                  # no at any level
    memory.recall("어제 새 얘기 했던 거 기억나?", "ko", NOW, embed=fake_embed)
    assert memory.recall(q, "ko", NOW, embed=fake_embed) == "그건 기억이 안 나요.", q
for q in ["Nah.", "No, a different one.", "not really"]:
    memory.recall("Remember we talked about birds yesterday?", "en", NOW, embed=fake_embed)
    assert memory.recall(q, "en", NOW, embed=fake_embed) == "I can't remember that.", q
memory._recall.update(offered=[], talk=None, listed=[], left=[])
for q in ["Do you happen to recall our bird chat?", "We were chatting about birds yesterday, weren't we?", "Any memory of us discussing birds?",
          "yo lumi u remember bird talk yday?", "Birds. Yesterday. Ring any bells?", "Did we not talk about birds yesterday?",
          "Didn't we talk about birds?", "you and me talk birds, remember or no?"]:
    memory._recall.update(offered=[], talk=None, listed=[], left=[])
    assert memory.recall(memory._clean(q), "en", NOW, embed=fake_embed) == "Do you mean our talk about birds yesterday at about 4 pm?", q
memory._recall.update(offered=[], talk=None, listed=[], left=[])
for q in ["나 그런 얘기 안 했어.", "I never said that."]:
    assert memory.recall(q, "ko", NOW, embed=fake_embed) is None, q
assert memory.recall("한글 얘기 기억나세요? 어제 했던 거요.", "ko", NOW, embed=fake_embed) == "어제 오후 3시쯤에 한글에 대해 이야기한 거 말씀이세요?"
assert memory.recall("Remember 어제 쿳션 얘기?", "ko", NOW, embed=fake_embed).endswith("Cutshion에 대해 이야기한 거 말씀이세요?")
assert memory.recall("Going back to chess: what was that again?", "en", NOW, embed=fake_embed) is None   # not the talk recalled
for q in ["Quick one: what did you tell me about it?", "Lumi-san ano... what did you tell me about it?",   # a filler is no topic
          "Okay, and please, robot what did you tell me about that?", "and answer was what?", "what was the answer?"]:
    memory._recall.update(offered=[], talk=None, listed=[], left=[])
    memory.recall("Remember we talked about birds yesterday?", "en", NOW, embed=fake_embed)
    assert memory.recall(q, "en", NOW, embed=fake_embed) == "I told you that many birds migrate south for food in winter.", q
for q, lang in [("Right, did we talk about sharks?", "en"), ("yesterday we talk sharks, you remember?", "en"),   # a new question
                ("Exactly what did we talk about last week?", "en"), ("맞다, 어제 상어 얘기도 했었나?", "ko"),        # is no "yes"
                ("그래, 지난주에 우리 무슨 얘기 했지?", "ko")]:
    memory._recall.update(offered=[], talk=None, listed=[], left=[])
    memory.recall("Remember we talked about birds yesterday?", "en", NOW, embed=fake_embed)
    out = memory.recall(q, lang, NOW, embed=fake_embed)
    assert out in memory.CANT_REMEMBER.values() or out in memory.ONLY_TWO_DAYS.values(), (q, out)
memory._talk.update(skip=True, track=None)             # "forget this" said in this talk (no person known): nothing recalled
for q, lang in [("So what did we say about birds?", "en"), ("어제 새 얘기 했던 거 기억나요?", "ko"), ("Do what we said yesterday.", "en")]:
    assert memory.recall(q, lang, NOW, embed=fake_embed) in memory.CANT_REMEMBER.values(), q
memory._talk.update(skip=False, track="p2")
assert memory.recall("어제 문어 얘기 했던 거 기억나?", "ko", NOW, embed=fake_embed) == "그건 기억이 안 나요."
assert memory.recall("우리 무슨 주제로 얘기했었지?", "ko", NOW, embed=fake_embed).startswith("최근 이틀 동안")   # "주제" is no topic
for q in ["지난주에 우리 무슨 얘기 했지?", "저번 주 월요일에 우리 뭐 얘기했어?", "last weekend 얘기 기억나?", "사흘 전에 내가 뭐라고 했는지 기억나?",
          "what did we talk about last weekend?", "Remember what I told you three days ago?"]:
    assert memory.recall(q, "ko", NOW, embed=fake_embed) in memory.ONLY_TWO_DAYS.values(), q
assert memory.recall("그저께 얘기한 거 기억나?", "ko", NOW, embed=fake_embed) == "그건 기억이 안 나요."   # none that day
talk_now = [("배터리 얼마나 가?", "약 10시간 가요."), ("고마워", "천만에요.")]
assert memory.recall("아까 배터리에 대해 뭐라고 하셨습니까?", "ko", NOW, embed=fake_embed, history=talk_now) is None   # this talk: the LLM
for q in ["어제 말한 거 해 줘", "어제 얘기한 대로 해 주세요", "어제 하기로 한 거 해", "어제 말씀드린 거 진행해 주십시오", "Do what we said yesterday."]:
    out = memory.recall(q, "ko" if "어" in q else "en", NOW, embed=fake_embed)
    assert "go to p3 and wave" in out and ("할까요" in out or "Shall I" in out), (q, out)   # read back, asked, never done
for q in ["내 얘기 delete 해 줘", "그 대화 delete 좀 해 주세요", "I'd rather you didn't keep that", "Erase our talk, please.",
          "다 잊어 주세요", "잊어 줘", "잊어버려", "제 이야기는 기억에서 지워 주십시오", "기억하지 마세요", "Please 잊어 주세요"]:
    assert memory.FORGET.search(memory._clean(q)), q
# seen things: Korean levels, a colour asked, an elliptic follow-up, the hand state asked in Konglish
memory.saw([{"name": "bottle", "colour": "white"}], "", now=NOW - HOUR)
memory.saw([{"name": "cup", "colour": "red"}], "", now=NOW - 2 * HOUR)
for q in ["오늘 흰 병 봤어?", "오늘 흰 병 봤어요?", "오늘 흰 병 보셨습니까?", "오늘 흰 병 보셨어요?", "오늘 흰 병 봤나?", "오늘 white bottle 봤어?"]:
    assert memory.reply(q, "ko", NOW).startswith("네, 오늘 오후 4시쯤"), q
assert memory.reply("그럼 빨간 컵은?", "ko", NOW).startswith("네, 오늘 오후 3시쯤")
assert memory.reply("음 그럼 초록 컵은?", "ko", NOW).startswith("오늘은 초록색 컵은 못 봤어요.")
assert memory.reply("did you see a green cup today?", "en", NOW).startswith("I haven't seen a green cup today. I saw a red cup")
memory._state.update(arm="look", gripper="open", holding=None, at=time.time())
for q in ["hand에 뭐 있어?", "너 hand에 뭐 있어?", "손에 뭐 있어요?", "손에 뭐 들고 계세요?", "그리퍼 열려 있어요?"]:
    out = memory.reply(q, "ko", NOW)
    assert out and "아무것도" in out, (q, out)
memory._state["at"] = 0.0
# privacy: only text, nothing of audio; a forget deletes only this person's talks; past 48 h gone
assert "audio" not in json.dumps(json.loads((memory.DIR / "talks.json").read_text()))
memory.keep_talk(birds, "p8", NOW - HOUR, fake_chat("Moon", "The moon."), fake_embed)
memory._talk.update(track="p2")
assert memory.reply("다 잊어 줘", "ko", NOW) == memory.FORGOT["ko"]
assert [s["title"] for s in memory._load("talks")] == ["Moon"]
memory.clock = lambda: NOW + 49 * HOUR
assert memory._load("talks") == [] and memory._load("seen") == []
memory.clock = lambda: NOW
memory._talk.update(name=None, track=None, skip=False)

# ---------- speed: a turn's lookups ----------
memory._state.update(body="Your body now: lift 75 mm.", at=time.time())
t = time.time()
for _ in range(100):
    memory.turn_lines(FakeBrain(hist), "what's my name?")
    memory.reply("tell me about Seoul", "en", NOW)
assert (time.time() - t) / 100 < 0.01, (time.time() - t) / 100
print("memory ok")
