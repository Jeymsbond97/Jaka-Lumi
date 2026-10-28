"""Self-check of follow-ups in a dialogue (tests/followup_cases.py) through lumi.answer()'s routing, no robot, no LLM:
the seeing answers on saved camera frames, the keyword rules, the lookup follow-ups (brain._after with the model
saying "none", brain.search_query). python tests/test_followup.py

    python tests/test_followup.py           # routing of every case; fails when one goes the wrong way
    python tests/test_followup.py --llm 30  # also the conversation model on up to 30 cases with `must` / `act`
                                            # (Ollama is shared with the live robot: keep it small)
"""
import re
import sys
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import brain, lumi, seeing, web
from tests.conversation_check import NOW, rules_route
from tests.followup_cases import CASES
from vision import scene

DATA = Path(__file__).resolve().parent / "data"
MARKS = ["home", "dock2", "p1", "p2", "p3", "p4", "p5"]       # fixed: the map is never asked
scene.ask_vlm = lambda q, lang="en", frames=None: "VLM"          # the slow model is not asked
scene.snapshot = None                                              # the live cameras are never read
FRAMES = {k: scene.load(str(DATA / f"scene_{v}")) for k, v in (("jacket", "carrying_jacket"), ("room", "empty_room"))}


def lang_of(text):
    return "ko" if re.search(r"[가-힣]", text) else "en"


def route(b, text, frames):
    """(route, detail) the way lumi.answer() sends the words: seeing first, the rules, then the model's turn
    (brain._after on an action line "none")."""
    lang = lang_of(text)
    brain.FORCED_LANG["lang"] = lang
    if lumi.NAME_ONLY.match(text) or lumi.stop_order(text, MARKS):
        return "rules", text
    seen = seeing.answer(text, lang, frames)
    if seen:
        b.history.append((text, f"ACTION: none -\n{seen}"))
        return "seeing", seen
    place = lumi.consent_place(text, b, MARKS)
    if place:
        return f"act:go_to {place}", ""
    if lumi.talk_fate(text) == "close":
        return "closing", ""                                         # the LLM reads it with the talk before
    r = rules_route(text, lang, MARKS)
    if r:
        name = {"chat": "closing", "action:end": "end"}.get(r[0], r[0].replace("action:", "act:"))
        if name in ("weather", "search"):
            rule = brain.intent(text, MARKS)
            return name, (b.weather_place(rule[1], text) if name == "weather" else b.search_query(rule[1]))
        return name, r[1]
    if b.is_lookup_follow_up(text):
        return "search", b.search_query(text)
    h = b._after({"action": "none", "target": ""}, text)
    if h["action"] == "search" and lumi.lookup_refused(b, h["target"], b.topic(text), text):
        return "refused", ""                                         # lumi.answer: Cutshion / this place, not online
    if h["action"] == "search":
        return "search", b.search_query(h["target"])
    if h["action"] != "none":
        if h["action"] == "weather":                                 # the place kept, the day in the words
            return "weather", h["target"] or f"weather {b.weather_place('', text)} {text}"
        return f"act:{h['action']} {h['target']}", h["target"]
    return "llm", ""


def replay(b, ctx, frames):
    """The turns before, with the history lumi.py keeps for each."""
    seeing._last.update(thing=None, name=None, kind=None)
    for kind, said, reply in ctx:
        lang = lang_of(said)
        brain.FORCED_LANG["lang"] = lang
        seen = seeing.answer(said, lang, frames)                  # lumi asks the cameras first, every turn
        if kind == "seeing":
            assert seen, f"context {said!r} is not a seeing question"
            b.history.append((said, f"ACTION: none -\n{seen}"))
        elif kind == "talk":
            if reply:
                b.history.append((said, f"ACTION: none -\n{reply}"))
        elif kind == "search":
            b.search_query(said)
            b.history.append((said, reply))
            b.last_lookup = said
        elif kind == "weather":
            asked = said + getattr(brain, "WEATHER_ASKED", " (the weather)")                  # lumi.look_up / brain.respond_from
            b.weather_place((brain.intent(said, MARKS) or ("", ""))[1], said)
            b.history.append((asked, reply))
            b.last_lookup = asked
        else:
            b.history.append((said, f"ACTION: {reply}"))


def check(case):
    """(ok, got route, detail)."""
    b = brain.Brain()
    frames = FRAMES[case["fr"]]
    replay(b, case["ctx"], frames)
    got, detail = route(b, case["say"], frames)
    want = case["route"].replace("talk", "llm|closing").split("|")
    ok = got in want or any(w.startswith("act:") and got.startswith(w) for w in want)
    if ok and case["ans"] and got in ("seeing", "search", "weather"):
        ok = bool(re.search(case["ans"], detail or "", re.I))
    return ok, got, detail


def llm_check(case):
    """The conversation model with the context: (ok, action, reply)."""
    b = brain.Brain()
    replay(b, case["ctx"], FRAMES[case["fr"]])
    brain.FORCED_LANG["lang"] = lang_of(case["say"])
    head, words = None, []
    for out in b.respond_stream(case["say"], MARKS, now=NOW):
        if isinstance(out, dict):
            head = out
        else:
            words.append(out)
    reply = " ".join(words)
    ok = all(re.search(m, reply, re.I) for m in case["must"])
    if case["act"]:
        ok = ok and head["action"] == case["act"]
    elif head["action"] not in ("none",):
        ok = False
    return ok, head["action"], reply


if __name__ == "__main__":
    bad = []
    for i, c in enumerate(CASES):
        ok, got, detail = check(c)
        if not ok:
            bad.append(i)
            print(f"FAIL {i:3} {c['say']!r} -> {got} {str(detail)[:70]!r}  (want {c['route']}: {c['means']})")
    print(f"follow-ups: {len(CASES) - len(bad)}/{len(CASES)} routed right")
    if "--llm" in sys.argv:
        n = int(sys.argv[sys.argv.index("--llm") + 1]) if len(sys.argv) > sys.argv.index("--llm") + 1 else 20
        picked = [c for c, (ok, got, _) in ((c, check(c)) for c in CASES) if (c["must"] or c["act"]) and got == "llm"][:n]
        good = 0
        for c in picked:
            ok, a, reply = llm_check(c)
            good += ok
            print(f"{'ok  ' if ok else 'FAIL'} {c['say']!r} -> {a}: {reply[:110]!r}")
        print(f"LLM: {good}/{len(picked)}")
    assert not bad, bad
    # "again" right after an action (a remark in between) is that action again, never "say it again"
    b = brain.Brain()
    b.history = [("let's see it", "ACTION: wave -\nOkay!"), ("와 귀엽다", "ACTION: none -\n고마워요!")]
    for t in ("do it again", "한 번 더", "one more time!", "또"):
        assert b._after({"action": "none", "target": ""}, t) == {"action": "wave", "target": ""} and not b.again(t), t
    assert b._after({"action": "none", "target": ""}, "what's that?")["action"] == "none"
    b.history = [("what's a lidar?", "ACTION: none -\nA laser scanner.")]
    assert b._after({"action": "quiet", "target": ""}, "에이, 거짓말하지 마")["action"] == "none"
    assert b.again("one more time") == "same" and b._after({"action": "none", "target": ""}, "again")["action"] == "none"
    from assistant import driving                       # "more" right after a look: the head a step further (live 2026-10-23)
    looked = driving.last_command([("Look at the left side.", "ACTION: look left")])
    for said in ("More again.", "Look at more.", "Look at the left side more.", "more", "a bit more", "again", "더", "조금 더",
                 "한 번 더", "좀 더 봐", "왼쪽으로 더", "look more to the left"):
        assert driving.read(driving.clean(brain._norm(said)), looked) == ("look", "left small"), said
    assert driving.read("look right", looked) is None and driving.read("i want more", looked, True) is None
    assert driving.read("오른쪽으로 더", looked) == ("look", "right small")
    # the weather asked, then the day moved (live 2026-10-23 15:37: "내일 어때요?" and "다음 주 월요일 어때요?" were
    # searched, "날씨 어때요?" then gave today's weather): the weather again, the day and place kept
    b = brain.Brain()
    b.history = [("오늘 부산 날씨 어때요? (the weather)", "흐려요.")]
    b.last_lookup, b.weather_at = b.history[0][0], "Busan"
    for t in ("내일 어때요?", "다음 주 월요일 어때요?", "And Friday?", "how about the day after?", "모레는요?"):
        for said in ("none", "search"):
            assert b._after({"action": said, "target": t}, t) == {"action": "weather", "target": ""}, (t, said)
    assert b._after({"action": "none", "target": ""}, "what about Daegu tomorrow?") == {"action": "weather", "target": "Daegu"}
    assert b._after({"action": "none", "target": ""}, "Thanks, see you tomorrow!")["action"] == "none"
    b.history = [("다음 주 월요일 어때요?", "다음 주 월요일은 10월 26일이에요.")]
    assert b.weather_on("날씨 어때요?") == web.asked_day("다음 주 월요일")
    # thanks / okay in context: a goodbye ends at once, a closing word is read with the talk (LLM), more words go on
    for t in ("Okay, I gotta run. Thanks!", "catch you later", "그만 물어볼게요. 잘 있어요.", "잘 있어, 담에 봐",
              "I'll let you go now", "고마워요, 또 뵐게요", "Thanks, I'm heading out."):
        assert lumi.talk_fate(t) == "end", t
    for t in ("Okay thanks.", "Thanks!", "고마워요.", "됐어요.", "Nah, I'm good.", "I'm all set, thanks.", "아뇨, 없어요.",
              "That's plenty, thank you.", "이제 충분해요.", "오케이 땡큐"):
        assert lumi.talk_fate(t) == "close", t
    for t in ("Thanks. Wait, one more thing.", "Thanks! And where is p3?", "고마워요. 근데 몇 살이에요?", "Oh I see.",
              "아 그렇구나.", "I'm good, how are you?", "하나만 더 물어볼게요", "물 없어요?", "Okay cool, thanks. Can you turn around?"):
        assert lumi.talk_fate(t) == "talk", t
    assert lumi.kept_goodbye("You're welcome! Have a great night.") and not lumi.kept_goodbye("You're welcome!")
    # the model's motion only for a direct order now: never for a remark, a plan, a report or a condition
    for t in ("우리 회의실 들렀다가 p3 가자", "Don't look up.", "점심 먹고 나서 p3로 가", "Let's go to the cafe after this.",
              "아까 뒤로 가더라", "엄마가 오른쪽으로 가래", "I should turn around and leave.", "Turn left and you'll see the toilet.",
              "Look, it's moving!", "Go on, tell me more.", "Go to gate one? nah, stay here", "give me a sec", "내 말 따라 해",
              "나 이제 무대 쪽으로 가려고.", "If I wave, follow me.", "회의 끝나면 여기로 와"):
        assert not brain.llm_ordered(t), t
    for t in ("look up", "come here please", "follow me", "따라와", "give me your hand", "손 줘", "lift up 3 cm if you don't mind",
              "왼쪽으로 돌아", "wave at me", "p1로 가 줘"):
        assert brain.llm_ordered(t), t
    # "ACTION: none -" then "ACTION: sing -" (or a sentence first): the second line is the action, never said aloud
    from unittest import mock
    from assistant import llm_direct
    for out in ("ACTION: none -\nACTION: sing -\nOkay!", "Okay!\nACTION: sing -\nHere it comes."):
        with mock.patch.object(llm_direct, "stream", lambda m, *a, o=out, **k: (o[i:i + 3] for i in range(0, len(o), 3))):
            b = brain.Brain()
            b.history = [("Can you sing?", "ACTION: none -\nYes! Shall I sing one for you?")]
            got = list(b.respond_stream("Sure, go ahead.", ["home"], now="You are not doing any task."))
        assert got[0]["action"] == "sing" and not any("ACTION" in s for s in got[1:]), (out, got)
    # a short follow-up gets follow-up examples; a new question does not
    h = [("How fast are you?", "ACTION: none -\nNormally 0.6 metres a second.")]
    for t in ("why?", "왜요?", "and then?", "진짜?", "그게 무슨 말이야?", "그럼 그건?", "언제?", "Who was he?"):
        assert brain._follow_examples(t, h), t
    for t in ("Where is p3?", "세종대왕이 누구예요?", "oh cool", "What's your name?", "Tell me about the Korean War."):
        assert not brain._follow_examples(t, h), t
    # a world subject keeps Lumi's notes out (also lower-case English and a part named after it); Lumi's own things keep them
    b = brain.Brain()
    for h, t, want in (([], "Why do whales sing?", ["whales"]), ([], "부엉이는 고개를 몇 도까지 돌려요?", ["부엉이"]),
                       ([("Why do whales sing?", "ACTION: none -\nTo find mates.")], "How far can the song go?", ["whales"]),
                       ([("문어는 다리가 몇 개고?", "ACTION: none -\n여덟 개예요.")], "심장은 몇 개고?", ["문어", "다리", "심장"]),
                       ([], "속도는 얼마예요?", []), ([], "How fast can you go?", []), ([], "Is the song yours?", []),
                       ([], "Can the arm lift 2 kg?", [])):
        b.history = list(h)
        assert b.world_talk(t) == want, (t, b.world_talk(t))
    # "really?" after a turn Lumi did not catch asks about the answer before it
    h = [("롯데월드타워 높이 몇 m예요?", "ACTION: none -\n555미터예요."),
         ("uh... what was it... 그...", "ACTION: unclear -\n죄송해요, 다시 말씀해 주시겠어요?")]
    assert brain.topic_turn(h)[0].startswith("롯데월드타워"), brain.topic_turn(h)
    # the model's "search" with its answer after it: said (none); a lookup promise or "don't know" keeps the search
    s = {"action": "search", "target": "x"}
    q = "윤초는 뭐예요?"
    for w in ("윤초는 지구 자전과 시계를 맞추는 1초예요.", "Mount Fuji is 3,776 metres high."):
        assert brain.Brain._settled(s, w, q)["action"] == "none", w
    for w in ("확인해 볼게요.", "Let me check.", "search whale song distance", "잘 모르겠어요.", "", "윤초는 뭐예요?",
              "윤초가 궁금하시군요. 잠시만요.", "What exactly do you mean?"):
        assert brain.Brain._settled(s, w, q) is s, w
    assert brain.CHANGES.search("지금 비트코인 얼마야?") and brain.CHANGES.search("Who won the game yesterday?")
    assert not brain.CHANGES.search("윤초는 뭐예요?") and not brain.CHANGES.search("How do bees dance?")
    print("followup ok")
