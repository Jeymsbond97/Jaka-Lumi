"""Self-check: assistant/memory.py with fakes (no robot, no LLM, no embedding server, a temp folder), EN + KO:
the body state line, seen things ("did you see an apple today?"), talks kept / recalled by meaning / confirmed /
forgotten, 48 h only, facts said earlier in a long talk.   python tests/test_memory.py"""
import json
import tempfile
import time
from pathlib import Path

import numpy as np

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
assert ask("what did we talk about yesterday?") == "Do you mean our talk about birds yesterday at about 4 pm?"
assert ask("yeah, that one") .startswith("Yes, I remember.")
assert ask("기억나? 어제 새 얘기 했던 거", "ko") == "어제 오후 4시쯤에 새에 대해 이야기한 거 말씀이세요?"
assert ask("네", "ko") == "네, 기억나요. 한국의 새에 대해 이야기했어요."
assert ask("우리 부산 날씨 얘기했던 거 기억나요?", "ko") == "오늘 오후 2시쯤에 부산 날씨에 대해 이야기한 거 말씀이세요?"
assert ask("아니", "ko") == "그건 기억이 안 나요."
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
assert ask("그저께 얘기한 거 기억나?", "ko") == "저는 최근 이틀 동안의 일만 기억해요."
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
          "Lumi, can you forget our conversation?", "잊어 주세요", "다 잊어버려", "delete my data"]:
    assert memory.FORGET.search(q), q
for q in ["forget it", "don't forget the cup", "잊지 마", "did you forget me?", "제 이름 잊어버렸어요?", "잊어버렸어?"]:
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
    assert memory.reply(q, "ko", NOW) == "팔은 앞에 접어 둔 기본 자세예요. 손은 펴져 있고 비어 있어요.", q
memory._state.update(arm="give", gripper="closed", holding="the red cup")
assert memory.reply("where is your hand?", "en", NOW) == "My hand is held out in front of me. I'm holding the red cup."
assert memory.reply("손에 뭐 있어요?", "ko", NOW) == "손을 앞으로 내밀고 있어요. 손에 빨간색 컵을 들고 있어요."
for q in ["open your hand", "손 펴", "손 펴 줘", "give me your hand", "close your hand", "hand me the cup", "손 줘"]:
    assert memory.reply(q, "en", NOW) is None, q
assert memory.reply("hand open or close?", "en", NOW).endswith("I'm holding the red cup.")
memory._state.update(place="p3", lift=0.0)
assert memory.reply("where are you?", "en", NOW) == "I'm at p3 right now."
assert memory.reply("지금 어디야?", "ko", NOW) == "지금 p3에 있어요."
assert memory.reply("where are you going?", "en", NOW) is None and memory.reply("where are you from?", "en", NOW) is None
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

# ---------- speed: a turn's lookups ----------
memory._state.update(body="Your body now: lift 75 mm.", at=time.time())
t = time.time()
for _ in range(100):
    memory.turn_lines(FakeBrain(hist), "what's my name?")
    memory.reply("tell me about Seoul", "en", NOW)
assert (time.time() - t) / 100 < 0.01, (time.time() - t) / 100
print("memory ok")
