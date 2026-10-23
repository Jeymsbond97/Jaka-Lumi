"""Generated commands (tests/command_cases.py) through Lumi's routing, per intent: right, missed (no motion) or wrong.

    .venv/bin/python tests/command_check.py              # rules only; cases the rules leave are "llm?" (not judged)
    .venv/bin/python tests/command_check.py --llm        # those go to the real LLM (action line + first sentence)
    .venv/bin/python tests/command_check.py --cached     # the LLM's answers from the last --llm run where the text is
                                                         # the same (fast, after a rule change)
    .venv/bin/python tests/command_check.py receive      # only this intent
    .venv/bin/python tests/command_check.py --new        # only the second set (tests/command_cases2.py); --old the first
    .venv/bin/python tests/command_check.py --songs      # only the song set (tests/song_cases.py) -> logs/song_check.*

-> logs/command_check.md / .json (rules only: logs/command_check_rules.*). The order is lumi.answer()'s with nothing running and the hand empty ("idle") or
holding something ("holding"): stop, what the cameras see (seeing.answer), status, the hand (brain.hand_request), mission, goodbye / closing words, song,
keyword rules, then the LLM's action line acted on as lumi.answer() does. Nothing moves; the LLM is only asked.
"""
import collections
import json
import pathlib
import re
import sys
import time

from assistant import brain, driving, lumi, seeing
from audio import sing
from tests.command_cases import CASES as CASES1
from tests.command_cases2 import CASES as CASES2   # 2026-10-21 night: new wordings, the conference map
from tests.command_cases3 import CASES as CASES3   # the same night, written blind from docs/14 and docs/17
from tests.song_cases import CASES as SONGS        # 2026-10-22: song requests and near misses, written blind
from tests.conversation_check import NOW, markers

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "command_check"
HOLDING_NOW = "I'm holding a cup and waiting for what to do with it."
NO_MOTION = {"seeing", "talk", "unclear", "status", "empty_hand", "refuse", "search", "weather", "llm?", "ask", "speed"}


class NoLLM(Exception):
    """A rules-only run reached the mission reader's LLM pass."""


def seen(text):
    """assistant/seeing.answer() takes these words (its own test: tests/test_seeing.py). No frames: it answers "no
    camera" where it would look, None where it leaves the words to the rest ("how far is the stage?")."""
    seeing._last.update(thing=None, name=None, kind=None)
    return seeing.answer(text.strip(), frames=[]) is not None


def rules(text, state, marks, b):
    """The route lumi.answer() takes before the LLM, or None."""
    holding = state == "holding"
    if lumi.FOREIGN_SCRIPT.search(text):
        return "unclear"
    fixed = brain.self_correct(text, marks)              # "go to start, no, end"
    if not fixed:
        return "ask" if fixed is None else "talk"
    text = fixed
    t = brain._norm(text)                                # lumi.drive_words: speed, "again", how far?, too far
    drive = driving.read(t, driving.last_command(b.history), driving.talking(b.history))
    if drive and (drive[0] != "move" or drive != driving.read(t, None, True)):
        return {"speed": lambda d: f"speed {'faster' if d[1] > 0 else 'slower'}", "move": lambda d: f"action:move {d[1]}",
                "turn": lambda d: f"action:turn {d[1]}", "look": lambda d: f"action:look {d[1]}",
                "lift": lambda d: f"action:lift {d[1]}",
                "refuse": lambda d: "refuse", "ask": lambda d: "ask"}[drive[0]](drive)
    if lumi.NAME_ONLY.match(text):
        return "talk"
    kind, data = lumi.route(text, marks, b, holding, seen=lambda x: "seen" if seen(x) else None,
                            last=b.history[-1][1] if b.history else "")   # the voice's and the Command box's way
    if kind in ("stop", "seeing", "status", "end"):
        return kind
    if kind == "chain":                                  # lumi.chain_request: every part in the order said
        return "chain:" + "+".join(k if k != "quick" else "_".join(filter(None, w)).replace(" ", "_")
                                   for k, _, w in data)
    if kind == "correction":
        return "talk" if data[0] == "ask" else f"action:{data[0]} {data[1]}"
    if kind == "hand":
        (hand, held) = data
        return {"receive": lambda h: "receive " + (h[1] or "") if not held else "refuse",
                "give": lambda h: "give" if held else "empty_hand",
                "place": lambda h: "place " + ((h[1] or {}).get("name") or "") if held else "empty_hand",
                "refuse": lambda h: "refuse", "ask": lambda h: "talk"}[hand[0]](hand).strip()
    if kind == "mission":
        from assistant import steps                      # lumi.mission_request: refused before anything moves
        return "talk" if data[1] else "refuse" if steps.check(data[0], holding, marks) else "mission"
    if kind == "sing":
        return "sing" if sing.choose(text) else "talk"     # a song we don't have: said so (sing.unknown_reply)
    if kind == "quick":
        return data[0] if data[0] in ("weather", "search") else f"action:{data[0]} {data[1]}".strip()
    return None


def llm(text, state, marks, b):
    """(route, action line, first sentence) from the real model, acted on like lumi.answer()."""
    brain.FORCED_LANG["lang"] = "ko" if brain.HANGUL.search(text) else "en"
    text = brain.self_correct(text, marks) or text
    gen = b.respond_stream(text, marks, now=HOLDING_NOW if state == "holding" else NOW)
    head = next(gen)
    first = next(gen, "") or ""
    gen.close()
    if head["action"] == "none" and brain.promised(first) in ("sing", "wave"):   # lumi.answer() does what the reply
        head = {"action": brain.promised(first), "target": ""}                    # promises (a move: it asks)
    target = (brain._mentions(text, marks).get("object") or "") if head["action"] == "receive" else head["target"]
    return act(head["action"], target, first, state), f"{head['action']} {target}".strip(), first


def refused(route):
    """A pick / receive / fetch of a thing the fingers can't take is answered with the reason (skills.refusal)."""
    from manipulation import skills
    from tasks import fetch
    words = route.split(None, 1)
    if words[0] in ("action:pick", "action:move_object", "receive") and len(words) > 1 and \
            any(skills.refusal(c) for c in set(brain.OBJECTS.values()) if words[1].endswith(c)):
        return "refuse"
    if words[0] == "action:fetch":
        obj = brain.fetch_from_text(words[1])[0].get("object") if len(words) > 1 else None
        if obj and skills.refusal(obj):
            return "refuse"
    return route


def act(a, target, first, state):
    if a in ("none", "end"):
        return "talk"
    if a in ("give", "place", "receive"):
        if a == "receive":
            return f"receive {target}".strip() if state == "idle" else "refuse"
        return a if state == "holding" else "empty_hand"
    if a in ("unclear", "search", "weather", "sing", "stop"):
        return a
    return f"action:{a} {target}".strip()


def ok(expect, got):
    """'right' | 'missed' | 'wrong'."""
    g = got.lower().split()
    for alt in expect.split(" | "):
        want = refused(alt).split()                             # "pick bottle": the reason why not is right
        if want[0] in ("talk", "ask") and g[0] in ("talk", "ask", "refuse"):     # a reason why not is an answer
            return "right"
        if want[0] == "chain" and g[0].startswith("chain:"):
            return "right"                                      # several parts, each done in turn (lumi.chain_run)
        if want[0] == "action:fetch" and g[0] == "action:fetch":
            return "right"                                      # parse_fetch reads the words later
        if want[0] == g[0] and all(w in g[1:] for w in want[1:]):
            return "right"
    return "missed" if g[0] in NO_MOTION else "wrong"


def main(args):
    global OUT
    marks = markers()
    use_llm, cached = "--llm" in args, "--cached" in args
    if "--songs" in args:
        OUT = OUT.with_name("song_check")
    cases = SONGS if "--songs" in args else CASES2 if "--new" in args else CASES3 if "--blind" in args else CASES1 if "--old" in args else \
        CASES1 + CASES2 + CASES3
    only = [a for a in args if not a.startswith("-")]
    old = {}
    if cached and OUT.with_suffix(".json").exists():
        old = {(r["text"], r["state"], str(r["before"])): r for r in json.loads(OUT.with_suffix(".json").read_text())
               if r.get("raw")}
    if not use_llm and not cached:
        OUT = OUT.with_name("command_check_rules")       # a rules-only run keeps the last LLM run's report
    if not use_llm:                                      # a mission's LLM pass (lumi.read_mission) only with --llm
        from assistant import steps
        steps._ollama = lambda *a: (_ for _ in ()).throw(NoLLM())
    rows, t0 = [], time.time()
    for i, c in enumerate(c for c in cases if not only or c["intent"] in only):
        b = brain.Brain()
        if c["before"]:
            b.history.append(tuple(c["before"]))
        brain.FORCED_LANG["lang"] = c["lang"] if c["lang"] in ("en", "ko") else "ko"
        mk = c.get("markers") or marks
        try:
            got, raw, first = rules(c["text"], c["state"], mk, b), "", ""
        except NoLLM:
            got, raw, first = "llm?", "", ""
        if got is None:
            key = (c["text"], c["state"], str(c["before"]))
            if key in old:                               # the saved action line checked again by today's Brain._action
                raw, first = old[key]["raw"], old[key]["first"]
                head = brain.Brain._action("ACTION: " + raw, brain.self_correct(c["text"], mk) or c["text"], mk) or \
                    {"action": "none", "target": ""}
                a, tgt = head["action"], head["target"] if head["action"] != "receive" else raw.partition(" ")[2]
                got = act(a, tgt, first, c["state"])
            elif use_llm:
                try:
                    got, raw, first = llm(c["text"], c["state"], mk, b)
                except Exception as e:                          # noqa: BLE001 - a crash is a failure of that case
                    got, raw = "error", repr(e)
            else:
                got = "llm?"
        got = refused(got) if got not in ("llm?", "error") else got
        verdict = ok(c["expect"], got) if got != "llm?" else "llm?"
        rows.append({**c, "got": got, "raw": raw, "first": first, "verdict": verdict, "by": "llm" if raw else "rules"})
        if verdict == "wrong" or verdict == "missed" and "-v" in sys.argv:
            print(f"{i} {verdict.upper():6} [{c['intent']}/{c['state']}] {c['text']!r} -> {got} (want {c['expect']}) "
                  f"{first[:60]!r}", flush=True)
    OUT.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    report(rows, time.time() - t0)


def report(rows, secs):
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[r["intent"]][r["verdict"]] += 1
        by["ALL"][r["verdict"]] += 1
    lines = [f"# Command check ({time.strftime('%Y-%m-%d %H:%M')}, model {brain.MODEL}, {secs:.0f} s)", "",
             f"{len(rows)} cases. right / missed (no motion) / wrong (a motion not asked for) / not run (LLM).", "",
             "| intent | cases | right | missed | wrong | llm? | by LLM |", "|---|---|---|---|---|---|---|"]
    llm_n = collections.Counter(r["intent"] for r in rows if r["by"] == "llm")
    for k in sorted(by, key=lambda k: (k == "ALL", k)):
        c = by[k]
        n = sum(c.values())
        lines.append(f"| {k} | {n} | {c['right']} | {c['missed']} | {c['wrong']} | {c['llm?']} | "
                     f"{llm_n[k] if k != 'ALL' else sum(llm_n.values())} |")
    lines += ["", "## Wrong", ""] + [f"- [{r['intent']}/{r['state']}] {r['text']!r} -> {r['got']} (want {r['expect']}) "
                                     f"{r['first'][:80]!r}" for r in rows if r["verdict"] == "wrong"]
    lines += ["", "## Missed", ""] + [f"- [{r['intent']}/{r['state']}] {r['text']!r} -> {r['got']} (want {r['expect']}) "
                                      f"{r['first'][:80]!r}" for r in rows if r["verdict"] == "missed"]
    OUT.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:len(by) + 6]))


if __name__ == "__main__":
    main(sys.argv[1:])
