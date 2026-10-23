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

from assistant import brain, lumi, seeing
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
        return f"act:{h['action']} {h['target']}" if h["action"] != "weather" else "weather", h["target"]
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
    print("followup ok")
