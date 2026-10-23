"""The reading tests on other maps: every case that names an office marker (p1 ... p10, final, exit, dock2) or a
conference marker (start, table_front, booth_2 ...) is said again with another map's names and must be read the same
way, so nothing depends on the office's p-numbers. No robot, no LLM:

    .venv/bin/python tests/fake_maps.py             # every map, failures printed, numbers per map
    .venv/bin/python tests/fake_maps.py korean -v   # one map, every substituted case shown

Cases (the existing sets): tests/test_steps.py (steps_cases*.py), the go-to rules of tests/test_places.py, the place
cases of tests/command_check.py (rules only), and tests/blind/train/commands_*.py when they name a map
(tests/blind/maps.py). A case whose place is said in a form only one map has ("피쓰리" for p3) is skipped.
"""
import contextlib
import importlib
import io
import pathlib
import re
import sys

from assistant import brain, steps, wording

OFFICE = ["home", "PInit", "Wp", "a", "b", "dock2", "exit", "final"] + [f"p{i}" for i in range(1, 11)]
OFFICE_SRC = [f"p{i}" for i in range(1, 11)] + ["final", "exit", "dock2"]
CONF_SRC = ["start", "end", "init", "final", "middle", "table_front", "stage", "booth_2", "dock2"]
WORDY = {"final", "exit", "start", "end", "init", "middle", "stage"}   # also plain words: swapped only when a place
# Each map: (marker, said in English, said in Korean) in the order of the source names above; "home" is on every map.
MAPS = {
    "office": [(n, n, n) for n in OFFICE_SRC],
    "expo": [("booth_A", "booth A", "부스 A"), ("booth_B", "booth B", "부스 B"), ("booth_3", "booth 3", "부스 3"),
             ("entrance", "entrance", "entrance"), ("stage", "stage", "스테이지"),
             ("coffee_corner", "coffee corner", "coffee corner"), ("info_desk", "info desk", "info desk"),
             ("registration", "registration", "registration"), ("demo_zone", "demo zone", "demo zone"),
             ("main_hall", "main hall", "main hall"), ("finish", "finish", "finish"),
             ("exit_gate", "exit gate", "exit gate"), ("lounge", "lounge", "lounge")],
    "korean": [("커피코너", "커피 코너", "커피 코너"), ("부스3", "부스 3", "부스 3"), ("입구", "입구", "입구"),
               ("무대", "무대", "무대"), ("안내데스크", "안내데스크", "안내데스크"), ("휴게실", "휴게실", "휴게실"),
               ("회의실", "회의실", "회의실"), ("전시장", "전시장", "전시장"), ("로비", "로비", "로비"),
               ("창고", "창고", "창고"), ("사무실", "사무실", "사무실"), ("출구", "출구", "출구"),
               ("주차장", "주차장", "주차장")],
    "booths": [(f"booth_{i}", f"booth {i}", f"부스 {i}") for i in range(1, 11)] +
              [("gate_1", "gate 1", "gate 1"), ("gate_2", "gate 2", "gate 2"), ("photo_zone", "photo zone", "photo zone")],
    "mixed": [("hall_A", "hall A", "hall A"), ("gate_1", "gate 1", "gate 1"), ("gate_2", "gate 2", "gate 2"),
              ("table_front", "table front", "테이블 프론트"), ("photo_zone", "photo zone", "photo zone"),
              ("start", "start", "스타트"), ("end", "end", "엔드"), ("middle", "middle", "미들"),
              ("카페", "카페", "카페"), ("VIP_room", "VIP room", "VIP room"), ("final", "final", "파이널"),
              ("exit", "exit", "exit"), ("dock2", "dock 2", "도크 2")],
    "spaces": [("Coffee Corner", "coffee corner", "coffee corner"), ("Booth A", "booth A", "booth A"),
               ("Main Stage", "main stage", "main stage"), ("Info Desk", "info desk", "info desk"),
               ("Hall 2", "hall 2", "hall 2"), ("Demo Area", "demo area", "demo area"),
               ("North Gate", "north gate", "north gate"), ("Rest Area", "rest area", "rest area"),
               ("Lab", "lab", "lab"), ("Workshop", "workshop", "workshop"), ("Lobby", "lobby", "lobby"),
               ("Back Door", "back door", "back door"), ("Storage", "storage", "storage")],
}
EXTRA = {"mixed": ["a", "b"]}                     # one-letter names that are also words ("go a bit forward")
HANGUL = re.compile(r"[가-힣]")
NBSP = "\x03"                                       # a space inside a marker name in the short notation


def names(m):
    return ["home"] + [n for n, _, _ in MAPS[m]] + EXTRA.get(m, [])


def table(m, src):
    """source marker -> (marker, said en, said ko) on map m."""
    return dict(zip(src, MAPS[m]))


def _particle(said):
    """'로' / '으로' after a Korean word as it is said: 입구로, 주차장으로 (ㄹ takes 로: 출구로, 휴게실로)."""
    if not HANGUL.match(said[-1]):
        return None
    jong = (ord(said[-1]) - 0xAC00) % 28
    return "으로" if jong and jong != 8 else "로"


def swap(text, sub, keep=()):
    """The text with each source marker said as the map's name; (text, sources found). Word-like sources ("final",
    "start") are swapped only when in keep (the case names them as a place)."""
    said_in = 2 if HANGUL.search(text) else 1
    found, said = set(), []
    for src in sorted(sub, key=len, reverse=True):
        if src in WORDY and src not in keep:
            continue
        said.append(sub[src][said_in])
        p, ref = _particle(said[-1]), f"\x01{len(said) - 1}\x02"   # filled in at the end: never matched again
        text, n = re.subn(wording._spoken(src) + r"(으로|로)?",
                          lambda m: ref + ((p or m.group(1)) if m.group(1) else ""), text, flags=re.I)
        if n:
            found.add(src)
    return re.sub("\x01(\\d+)\x02", lambda m: said[int(m.group(1))], text), found


def _own_place(orig, marks, sub, found):
    """True when the words name a place of the new map by themselves ("go to the lobby" on a map with a lobby): a
    case that wants Lumi to ask is then no longer one."""
    t = wording.norm(orig, marks)
    images = {wording.written(sub[s][0]) for s in found}
    return any(re.search(rf"(?<![a-z0-9_가-힣]){re.escape(wording.written(m))}(?![a-z0-9_])", t)
               for m in marks if m != "home" and wording.written(m) not in images)


def _go(part, sub):
    w = part.split(None, 1)
    if w[0] == "go":
        return "go " + ",".join(sub[t][0].replace(" ", NBSP) if t in sub else t for t in w[1].split(","))
    if w[0] == "say" and len(w) > 1:
        return "say " + swap(w[1], sub, set(sub))[0]
    return part


def steps_want(want, sub):
    """Places named in a steps want ("go p3 | say hi | go p5,p7") and the want on the new map."""
    if want == "?":
        return set(), "?"
    named = {t for p in want.split(" | ") if p.split()[0] == "go" for t in p.split()[1].split(",")}
    return named, " | ".join(_go(p.strip(), sub) for p in want.split(" | "))


def _quiet_import(name):
    with contextlib.redirect_stdout(io.StringIO()):
        return importlib.import_module(name)


def steps_cases():
    """(text, want, source map) from tests/test_steps.py and steps_cases7 / 8 (the conference map)."""
    ts = _quiet_import("tests.test_steps")
    from tests import steps_cases7 as c7, steps_cases8 as c8
    out = [(t, w, "office") for t, w in ts.CASES.items()]
    out += [(t, w, "conf") for t, w in c7.CASES.items()]
    out += [(brain.self_correct(t, c7.CONF), w, "conf") for t, w in list(c7.FIXED.items()) + list(c8.CASES.items())]
    return ts.short, out


def run_steps(m, short, cases, verbose):
    ok = bad = skip = 0
    marks = names(m)
    for text, want, srcmap in cases:
        src = OFFICE_SRC if srcmap == "office" else CONF_SRC
        sub = table(m, src)
        named, new_want = steps_want(want, sub)
        if not text or named - set(src) - {"home", "here"} or srcmap == "conf" and re.search(r"\bp\d+", text, re.I):
            skip += 1                                   # a p-number on the conference map: not a place there
            continue
        new_text, found = swap(text, sub, named)
        if named - {"home", "here"} - found:
            skip += 1                                   # said in a form only that map has
            continue
        if new_want == "?" and _own_place(text, marks, sub, found):
            skip += 1
            continue
        got, unread = steps.rules(new_text, marks)
        if new_want == "?":
            right = bool(unread) or bool(steps.check(got, False, marks))
        else:
            want_steps = [short(x.strip()) for x in new_want.split(" | ")]
            for x in want_steps:
                if x["do"] == "go":
                    x["to"] = [t.replace(NBSP, " ") for t in x["to"]] if isinstance(x["to"], list) else \
                        x["to"].replace(NBSP, " ")
            right = not unread and got == want_steps
        ok, bad = ok + right, bad + (not right)
        if not right or verbose:
            print(f"{'ok  ' if right else 'FAIL'} [{m} steps] {new_text!r}\n  want {new_want}\n  got  {got}"
                  f"{'  unread ' + str(unread) if unread else ''}")
    return ok, bad, skip


def intent_cases():
    tp = _quiet_import("tests.test_places")
    return tp.INTENTS


def run_intents(m, cases, verbose):
    ok = bad = skip = 0
    marks = names(m)
    sub = table(m, OFFICE_SRC)
    for text, want in cases.items():
        named = {want[1]} if want and want[0] == "go_to" else set()
        if named - set(OFFICE_SRC) - {"home"}:
            skip += 1
            continue
        new_text, found = swap(text, sub, named)
        if named - {"home"} - found:
            skip += 1
            continue
        if not want and _own_place(text, marks, sub, found):
            skip += 1
            continue
        new_want = ("go_to", sub[want[1]][0]) if named - {"home"} else \
            (want[0], swap(want[1], sub, named)[0]) if want and want[0] == "fetch" else want
        got = brain.intent(new_text, marks)
        right = got == new_want
        ok, bad = ok + right, bad + (not right)
        if not right or verbose:
            print(f"{'ok  ' if right else 'FAIL'} [{m} intent] {new_text!r}: want {new_want}, got {got}")
    return ok, bad, skip


PLACE_TOKEN = re.compile(r"(?<![a-z0-9_])(p\d+|dock2|final|exit|start|end|init|middle|stage|table_front|booth_2)"
                         r"(?![a-z0-9_])")


def command_cases():
    from tests.command_cases import CASES as c1
    from tests.command_cases2 import CASES as c2
    from tests.command_cases3 import CASES as c3
    return [c for c in c1 + c2 + c3 if re.search(r"action:(?:go_to|come_back) " + PLACE_TOKEN.pattern, c["expect"]) or
            re.search(r"(?<![a-z0-9_])(p\d+|dock2|booth_2|table_front)(?![a-z0-9_])", c["text"], re.I)]


def run_commands(m, cases, verbose):
    from assistant import lumi
    from tests import command_check as cc
    lumi.LOG_FILE = "/dev/null"
    steps._ollama = lambda *a: (_ for _ in ()).throw(cc.NoLLM())
    ok = bad = skip = 0
    marks = names(m)
    for c in cases:
        conf = c.get("markers") and "start" in c["markers"]
        src = CONF_SRC if conf else OFFICE_SRC
        sub = table(m, src)
        named = set()
        for alt in c["expect"].split(" | "):
            w = alt.split()
            if w[0] in ("action:go_to", "action:come_back") and len(w) > 1:
                named.add(w[1])
        if named - set(src) - {"home"} or conf and re.search(r"\bp\d+", c["text"], re.I):
            skip += 1
            continue
        text, found = swap(c["text"], sub, named)
        if named - {"home"} - found:
            skip += 1
            continue
        if not named and _own_place(c["text"], marks, sub, found):
            skip += 1
            continue
        expect = " | ".join(" ".join(sub[x][0].lower() if x in sub and x in named else x for x in alt.split())
                            for alt in c["expect"].split(" | "))
        b = brain.Brain()
        if c["before"]:
            b.history.append((swap(c["before"][0], sub, set(sub))[0], c["before"][1]))
        brain.FORCED_LANG["lang"] = c["lang"] if c["lang"] in ("en", "ko") else "ko"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                got = cc.rules(text, c["state"], marks, b)
        except cc.NoLLM:
            got = "llm?"
        if got is None or got == "llm?":
            skip += 1                                   # the LLM's case: not judged here
            continue
        verdict = cc.ok(expect, cc.refused(got))
        right = verdict == "right" or verdict == "missed" and c["expect"].split()[0] in ("talk", "ask")
        ok, bad = ok + right, bad + (not right)
        if not right or verbose:
            print(f"{'ok  ' if right else 'FAIL'} [{m} command {c['intent']}] {text!r} -> {got} (want {expect})")
    return ok, bad, skip


TRAIN = ["blind/train", "blind/r2/train"]          # never the held-out sets (blind/held, blind/r2/held)


def _train_modules():
    for d in TRAIN:
        for f in sorted((pathlib.Path(__file__).parent / d).glob("*.py")):
            if f.stem != "__init__":
                yield importlib.import_module("tests." + d.replace("/", ".") + "." + f.stem)


def blind_cases():
    """Blind train cases that name a map (tests/blind/maps.py), already on their map, and are about a place:
    commands (one route each), the place turns of the mixed dialogues (said with nothing before), and missions
    ({text: {"steps", "map"}}, read by steps.rules) -> (commands, missions)."""
    cmds, missions = [], []
    for mod in _train_modules():
        cases = getattr(mod, "CASES", [])
        if isinstance(cases, dict):
            missions += [(t, c) for t, c in cases.items() if isinstance(c, dict) and c.get("map") and "steps" in c]
            continue
        cmds += [c for c in cases if isinstance(c, dict) and c.get("map") and "expect" in c and "text" in c and
                 c.get("state", "idle") in ("idle", "holding") and _about_place(c)]
        for d in getattr(mod, "DIALOGUES", []) if "dialogues_mixed" in mod.__name__ else []:
            cmds += [{"intent": "dialogue:" + d["topic"].split(":")[0], "text": t["say"], "lang": d["lang"],
                      "state": d["state"], "before": None, "expect": t["expect_action"].replace("none", "talk"),
                      "map": d["map"], "markers": d["markers"]}
                     for t in d["turns"][:1] if t.get("scored") and "go_to" in t.get("expect_action", "")]
    return cmds, missions


def run_missions(cases, short, verbose):
    per = {}
    for text, c in cases:
        marks = c["markers"]
        fixed = brain.self_correct(text, marks)          # lumi.answer does it first: "go to p3, no, p5"
        got, unread = steps.rules(fixed, marks) if fixed else ([], [text])
        if c["steps"] == "?":
            right = bool(unread) or bool(steps.check(got, False, marks))
        else:
            right = not unread and got == [short(x.strip()) for x in c["steps"].split(" | ")]
        n = per.setdefault(c["map"], [0, 0])
        n[0 if right else 1] += 1
        if not right or verbose:
            print(f"{'ok  ' if right else 'FAIL'} [blind mission {c['map']}] {text!r}\n  want {c['steps']}\n  got  {got}"
                  f"{'  unread ' + str(unread) if unread else ''}")
    return per


def _about_place(c):
    """A blind case that names a place of its map or expects a drive (the rest is the other checks' work)."""
    from tests.blind.maps import MAPS as BLIND_MAPS
    marks = c.get("markers") or BLIND_MAPS[c["map"]]
    t = wording.norm(c["text"], marks)
    return re.search(r"go_to|come_back|mission", c["expect"]) or \
        any(re.search(rf"(?<![a-z0-9_가-힣]){re.escape(wording.written(m))}(?![a-z0-9_])", t) for m in marks if m != "home")


def run_blind(cases, verbose):
    from tests.blind.maps import MAPS as BLIND_MAPS
    from tests import command_check as cc
    from assistant import lumi
    lumi.LOG_FILE = "/dev/null"
    steps._ollama = lambda *a: (_ for _ in ()).throw(cc.NoLLM())
    per = {}
    for c in cases:
        marks = c.get("markers") or BLIND_MAPS[c["map"]]
        b = brain.Brain()
        if c.get("before"):
            b.history.append(tuple(c["before"]))
        brain.FORCED_LANG["lang"] = c.get("lang") if c.get("lang") in ("en", "ko") else "ko"
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                got = cc.rules(c["text"], c.get("state", "idle"), marks, b)
        except cc.NoLLM:
            got = "llm?"
        n = per.setdefault(c.get("map", "?"), [0, 0, 0])
        if got is None or got == "llm?":
            n[2] += 1
            continue
        verdict = cc.ok(c["expect"].lower(), cc.refused(got))           # marker names in any case: booth_A
        right = verdict == "right" or verdict == "missed" and c["expect"].split()[0] in ("talk", "ask")
        n[0 if right else 1] += 1
        if not right or verbose:
            print(f"{'ok  ' if right else 'FAIL'} [blind {c.get('map')} {c.get('intent')}] {c['text']!r} -> {got} "
                  f"(want {c['expect']})")
    return per


def main(args):
    verbose = "-v" in args
    only = [a for a in args if not a.startswith("-")] or list(MAPS)
    short, sc = steps_cases()
    ic, cc_ = intent_cases(), command_cases()
    total_bad, rows = 0, []
    for m in only:
        r = [run_steps(m, short, sc, verbose), run_intents(m, ic, verbose), run_commands(m, cc_, verbose)]
        total_bad += sum(x[1] for x in r)
        rows.append(f"{m:8} " + "   ".join(f"{k} {o}/{o + b} (skipped {s})" for k, (o, b, s) in
                                             zip(("steps", "intents", "commands"), r)))
    blind, missions = blind_cases()
    for mp, (o, b, s) in run_blind(blind, verbose).items():
        total_bad += b
        rows.append(f"blind {mp}: commands {o}/{o + b} right (LLM's, not judged: {s})")
    for mp, (o, b) in run_missions(missions, short, verbose).items():
        total_bad += b
        rows.append(f"blind {mp}: missions {o}/{o + b} right")
    print("\n".join(rows))
    return total_bad


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1:]) else 0)
