"""Typed = voice, English = Korean: every command case of the blind train sets read both ways, offline.

    .venv/bin/python tests/parity_check.py                          # rules: r6 r8 r9 r10 (and r12 when it is there)
    .venv/bin/python tests/parity_check.py --round r9 commands_go   # one round, these sets ("commands" = every commands_*)
    .venv/bin/python tests/parity_check.py --sample 50              # 50 cases per file, seeded (the same each run)
    .venv/bin/python tests/parity_check.py --llm --sample 20        # what the rules leave goes to the LLM (voice asks it
                                                                    # once; the box acts on the same action line)
    .venv/bin/python tests/parity_check.py --cached                 # the LLM lines of the last --llm run (same tag)
    .venv/bin/python tests/parity_check.py --tag final              # -> logs/parity_final.md / .json

Voice: tests/blind_check.score_commands (command_check.rules = lumi.answer's order on lumi.route, then the LLM).
Typed: api/server.task_parse, the dashboard's Command box, with the hand as the case says (fetch.check_hand faked) and
the case's map; a "command" it hands to the assistant is heard by voice, so that one is voice's by construction. The box
has no talk history: cases with "before" that differ are counted apart ("context"). Missions: lumi.route's steps on
both sides against the case's steps (tests/test_steps.py notation).
Report: typed != voice (same words, other plan), right / wrong / motion per channel and speech level, and per meaning
(same set, intent, expect, state, before, map) English against Korean: a meaning right in one language and not in the
other. Nothing moves; no service is called (the bank's embeddings are read as by every check).
"""
import collections
import json
import pathlib
import random
import re
re._MAXCACHE = 50000                                    # ponytail: the readers build many patterns per map; the
                                                        # default 512 recompiles them every case (20x slower)
import sys
import time

from tests import blind_check as bc
from tests import command_check
from assistant import brain, intent_bank, lumi
from tasks import fetch
from api import server

ROOT = pathlib.Path(__file__).resolve().parents[1]
ROUNDS = ["r6", "r8", "r9", "r10", "r11", "r12"]               # train sets only; held folders are never opened
SKIP = {"commands_sing"}                                # songs: the box hands every song to the assistant (voice)
EN_LEVELS = {"en_native", "en_nonnative", "en", "en*"}
ARM = re.compile(r"^(?:wave|reach|hand|arm|give|take|put|waist)")   # intents of the arm wordings (H1)

# ---------- fakes: nothing moves, nothing is written ----------
HAND = {"held": False}
fetch.check_hand = lambda: HAND["held"]
fetch.held_name = lambda lang="en": "the cup" if lang == "en" else "컵"
fetch.state = lambda: {"holding": HAND["held"]}
fetch.log = lumi.log = lambda *a, **k: None
MAP = {"now": bc.DEFAULT_MARKERS}
server.agv.markers = lambda: MAP["now"]

SEEN = {"route": None, "bank": None}                    # what lumi.route and the bank answered last
_route, _bank = lumi.route, intent_bank.read


def route(*a, **k):
    SEEN["bank"] = None
    SEEN["route"] = _route(*a, **k)
    return SEEN["route"]


def bank(*a, **k):
    SEEN["bank"] = _bank(*a, **k)
    return SEEN["bank"]


lumi.route, intent_bank.read = route, bank

SEEN_V = {"route": None}                            # voice's route of the case
LLM_LINE = {"head": None, "first": ""}                  # voice's action line, given to the box's LLM pass


def box_llm(self, *a, **k):
    yield LLM_LINE["head"] or {"action": "none", "target": ""}
    yield LLM_LINE["first"]


# ---------- one notation for both ----------
def num(x):
    return f"{float(x):g}"


def step_word(s):
    d = s.get("do")
    if d == "go":
        return f"go {s.get('to') if isinstance(s.get('to'), str) else (s.get('to') or {}).get('name', s.get('to'))}"
    if d == "move":
        return f"move {s.get('dir')} {num(s.get('m', 1))}"
    if d == "turn":
        return f"turn {num(abs(s.get('deg', 0)) if abs(s.get('deg', 0)) == 180 else s.get('deg', 0))}"   # half: either way
    if d in ("pick", "receive"):
        return " ".join(str(w) for w in (d, s.get("colour"), s.get("object")) if w)
    if d == "arm":
        return f"arm {s.get('pose')}"
    if d == "place":
        return "place " + str((s.get("on") or {}).get("name") or "")
    return d


def canon_steps(st):
    return " ; ".join(step_word(s) for s in st or [])


def canon(got, plan=None, st=None):
    """A route as one comparable string: motions by what they do, every no-motion answer as "none"."""
    w = got.split()
    if not w:
        return "none"
    if w[0] in command_check.NO_MOTION or w[0] in ("empty_hand", "refuse", "seeing", "status", "end", "sing", "point"):
        return "none" if w[0] != "point" else "point"
    if got == "mission":
        return "steps " + canon_steps(st)
    if got.startswith("chain:"):
        return "chain " + " + ".join(bc.chain_tokens(plan or []))
    if got.startswith("action:"):
        a, _, t = got[7:].partition(" ")
        if a == "fetch":
            return "fetch"
        if a == "put":                                  # "put it down" while holding: the place
            return "place"
        rs = server._rule_steps((a, t))
        return "steps " + canon_steps(rs) if rs else f"{a} {t}".strip()
    if w[0] == "receive":
        return "steps " + " ".join(w)
    if w[0] == "place":
        return "place"
    return got


def turn_said(deg):
    return "around" if abs(deg) == 180 else f"{'left' if deg > 0 else 'right'} {num(abs(deg))}"


def typed_got(r):
    """/tasks/parse's result in the checkers' notation (judged by command_check.ok), or None: handed to the assistant
    (heard as by voice)."""
    a = r.get("action")
    if a in ("steps", "carry") and r.get("problems"):
        return "refuse", None                           # shown with the reason, Start not offered (a fetch's
                                                        # problems are the dialog's questions: "Where should I bring it?")
    if a == "steps":
        st = r["steps"]
        if len(st) == 1:
            s = st[0]
            d = s.get("do")
            one = {"go": lambda: f"action:go_to {s.get('to')}", "move": lambda: f"action:move {s['dir']} {num(s['m'])}",
                   "turn": lambda: f"action:turn {turn_said(s['deg'])}", "arm": lambda: f"action:arm {s['pose']}",
                   "pick": lambda: "action:pick " + " ".join(x for x in (s.get("colour"), s.get("object")) if x),
                   "receive": lambda: f"receive {s.get('object') or ''}".strip(),
                   "place": lambda: "place " + str((s.get("on") or {}).get("name") or "")}.get(d)
            if one and isinstance(s.get("to", ""), str):
                return one(), st
        return "mission", st
    if a == "fetch":
        return f"action:fetch {(r.get('task') or {}).get('object') or ''}".strip(), None
    if a in ("give", "place"):
        return (a if a == "give" else "place " + str(((r.get("task") or {}).get("on") or {}).get("name") or "")), None
    if a == "carry":
        d = (r.get("task") or {}).get("dest")
        return f"action:go_to {d.get('marker') or d.get('name') if isinstance(d, dict) else d}", None
    if a == "command":                                  # Start sends the words to the assistant (/tasks/command):
        return None, None                               # heard and done as by voice
    return ("refuse" if r.get("talk") == "refuse" else "talk"), None


# ---------- both ways ----------
def voice(c, old, use_llm):
    SEEN["route"] = None
    r = bc.score_commands(c, old, use_llm)
    got = re.search(r"\] .*? -> (.*?) \(want ", r["show"], re.S)
    got = got.group(1) if got else "?"
    kind, data = SEEN["route"] or (None, None)
    src = r["by"] if r["by"] == "llm" else "bank" if kind == "quick" and SEEN["bank"] and tuple(SEEN["bank"]) == \
        tuple(data) else "rules"
    plan = data if kind == "chain" else None
    st = data[0] if kind == "mission" else None
    return r, got, src, plan, st


def typed(c, voice_row, use_llm):
    HAND["held"] = c["state"] == "holding"
    MAP["now"] = bc.marks_of(c)
    bc.STUCK["now"] = {"goal": c["stuck_goal"], "rest": [{"do": "go", "to": c["stuck_goal"]}], "start": None,
                       "tries": 0, "time": time.time()} if c["state"] == "stuck" else None
    raw = voice_row["out"].get("raw") or ""
    a, _, t = raw.partition(" ")
    LLM_LINE.update(head={"action": a, "target": t} if raw else None, first=voice_row["out"].get("first") or "")
    SEEN["route"] = None
    real, brain.Brain.respond_stream = brain.Brain.respond_stream, box_llm
    try:
        r = server.task_parse(server.ParseBody(text=c["text"], llm=bool(raw)))
    except command_check.NoLLM:                         # the mission reader's LLM pass, as on the voice side
        return "llm?", None, None
    except Exception as e:                              # noqa: BLE001 - a crash is a failure of that case
        return f"error {e!r}"[:120], None, None
    finally:
        bc.STUCK["now"] = None
        brain.Brain.respond_stream = real
    got, st = typed_got(r)
    got = command_check.refused(got) if got else got  # a thing the fingers can't take: the box says why too
    kind, data = SEEN["route"] or (None, None)
    return got, st, data if kind == "chain" else None


def verdict(c, got):
    if got == "llm?":
        return "llm?"
    got = command_check.refused(got)
    v = command_check.ok(c["expect"], got)
    return "right" if v == "right" else "motion" if bc.MOTION.match(got) or got.startswith("detour") else "wrong"


def mission_case(text, case):
    """A commands_missions case as a command case: lumi.route's steps judged against the written ones."""
    return {"text": text, "lang": case.get("lang") or bc.lang_of((text, case), {}), "state": "idle", "before": None,
            "expect": "mission", "steps": case["steps"], "markers": case.get("markers"), "map": case.get("map"),
            "level": case.get("level"), "intent": case.get("intent") or "missions"}


CHAIN_VERB = {"go_to": "go", "come_back": "go", "come": "go", "put": "place", "take": "receive"}


def mission_verdict(c, got, st, plan=None):
    want = c["steps"].strip()
    if want == "?":
        return "right" if not bc.MOTION.match(got) else "motion"
    if got == "mission" or st and got.startswith(("action:", "receive", "place")):
        return "right" if bc.same_steps([bc.short(s.strip()) for s in want.split(" | ")], st or []) else "motion"
    if got.startswith("chain:"):                        # the parts one by one (chain_run): the same commands in turn
        verbs = [CHAIN_VERB.get(t.split()[0], t.split()[0]) for t in bc.chain_tokens(plan or [])]
        return "right" if verbs == [w.split()[0] for w in want.split(" | ")] else "motion"
    return "llm?" if got == "llm?" else "wrong"


def run_case(rnd, name, c, old, use_llm):
    mission = "steps" in c
    vrow, vgot, src, vplan, vst = voice(c, old, use_llm) if not mission else voice({**c, "expect": "mission"}, old, use_llm)
    if mission and vgot == "mission" and SEEN["route"] and SEEN["route"][0] == "mission":
        vst = SEEN["route"][1][0]
    SEEN_V["route"] = SEEN["route"]
    tgot, tst, tplan = typed(c, vrow, use_llm)
    handed = tgot is None
    if handed:                                          # the assistant hears it: voice's way
        tgot, tst, tplan = vgot, vst, vplan
    if mission:
        vv, tv = mission_verdict(c, vgot, vst, vplan), mission_verdict(c, tgot, tst, tplan)
    else:
        vv, tv = (vrow["verdict"] if vrow["verdict"] in ("right", "wrong", "motion", "llm?") else verdict(c, vgot)), \
            verdict(c, tgot)
    fetch_asks = vgot == "ask" and (SEEN_V["route"] or (None,))[0] == "quick" and SEEN_V["route"][1][0] == "fetch"
    vc, tc = canon("action:fetch" if fetch_asks else vgot, vplan, vst), canon(tgot, tplan, tst)   # the dialog asks too
    lv = c.get("level") or bc.level_of(c, {"lang": c.get("lang")})
    return {"round": rnd, "set": name, "text": c["text"], "state": c["state"], "before": c.get("before"),
            "expect": c["expect"] if not mission else c["steps"], "intent": c.get("intent", ""), "map": c.get("map"),
            "level": bc.LEVEL_NAME.get(lv, lv), "lang": c.get("lang"), "channel": c.get("channel") or "-", "voice": vgot, "typed": tgot, "handed": handed,
            "v_canon": vc, "t_canon": tc, "v": vv, "t": tv, "src": src, "same": vc == tc,
            "raw": vrow["out"].get("raw", ""), "first": vrow["out"].get("first", "")}


def cases_of(rnd, name, sample):
    """sample: about this many cases, whole meanings (every level of a meaning kept, so EN / KO stay comparable)."""
    cases = bc.load(f"{rnd}.train", name)
    if bc.base(name) == "commands_missions":
        cases = [mission_case(t, k) for t, k in cases]
    cases = [c for c in cases if isinstance(c, dict) and "text" in c and "expect" in c and not bc.split_decimal(c)]
    if sample and len(cases) > sample:
        groups = collections.defaultdict(list)
        for c in cases:
            groups[(c.get("intent"), c["expect"], c["state"], str(c.get("before")), c.get("map"))].append(c)
        keys = sorted(groups, key=str)
        random.Random(name).shuffle(keys)
        picked = []
        for k in keys:
            if len(picked) >= sample:
                break
            picked += groups[k]
        cases = picked
    return cases


def sets_of(rnd, only):
    folder = ROOT / "tests" / "blind" / rnd / "train"
    if not folder.is_dir():
        return []
    names = sorted(p.stem for p in folder.glob("*.py") if p.stem != "__init__")
    names = [n for n in names if (n.startswith("commands_") or bc.base(n) == "speed_short") and bc.base(n) not in SKIP]
    if only:
        names = [n for n in names if bc.base(n) in only or n in only or "commands" in only and n.startswith("commands_")]
    return names


# ---------- report ----------
def meaning(r):
    return (r["round"], bc.base(r["set"]), r["intent"], r["expect"], r["state"], str(r["before"]), r["map"])


def owner(r, kind):
    """Which agent's reader a fault belongs to: L1 the Command box and the brain's rules, B2 the bank, H1 the arm's
    wordings, T1 the LLM's reading."""
    if kind == "typed":
        return "L1"
    if r["src"] == "llm":
        return "T1"
    if r["src"] == "bank":
        return "B2"
    return "H1" if ARM.match(r["intent"]) else "L1"


def report(rows, tag, secs, args):
    out = [f"# Parity check {tag} ({time.strftime('%Y-%m-%d %H:%M')}, {secs:.0f} s, {' '.join(args) or 'rules'})", "",
           f"{len(rows)} command cases (blind train sets). right / wrong / motion (a motion not asked for) / llm? per "
           "channel; typed = the dashboard's Command box (/tasks/parse), voice = lumi.answer's way.", ""]
    diff = [r for r in rows if not r["same"]]
    ctx = [r for r in diff if r["before"]]
    out += [f"**typed != voice: {len(diff) - len(ctx)}** (+ {len(ctx)} with a talk before, which the box has not)", "",
            "| round | cases | voice right | typed right | voice motion | typed motion | voice llm? | typed≠voice |",
            "|---|---|---|---|---|---|---|---|"]
    for rnd in sorted({r["round"] for r in rows}, key=ROUNDS.index) + ["ALL"]:
        rr = [r for r in rows if rnd in ("ALL", r["round"])]
        c = lambda k, v: sum(r[k] == v for r in rr)
        out.append(f"| {rnd} | {len(rr)} | {c('v', 'right')} | {c('t', 'right')} | {c('v', 'motion')} | "
                   f"{c('t', 'motion')} | {c('v', 'llm?')} | {sum(not r['same'] and not r['before'] for r in rr)} |")
    out += ["", "By speech level (right / judged; motions):", "", "| level | voice | typed | voice motion | typed motion |",
            "|---|---|---|---|---|"]
    for lv in sorted({r["level"] for r in rows}):
        rr = [r for r in rows if r["level"] == lv]
        jv, jt = [r for r in rr if r["v"] != "llm?"], [r for r in rr if r["t"] != "llm?"]
        pct = lambda j, k: f"{sum(r[k] == 'right' for r in j)}/{len(j)} ({100 * sum(r[k] == 'right' for r in j) / max(1, len(j)):.1f} %)"
        out.append(f"| {lv} | {pct(jv, 'v')} | {pct(jt, 't')} | {sum(r['v'] == 'motion' for r in rr)} | "
                   f"{sum(r['t'] == 'motion' for r in rr)} |")
    chans = sorted({r.get("channel", "-") for r in rows} - {"-"})
    if chans:                                           # r12 / r13: the words as typed or as whisper wrote them
        out += ["", "By speech level and written channel (voice path right / judged; typed≠voice):", "",
                "| level | " + " | ".join(chans) + " |", "|---|" + "---|" * len(chans)]
        for lv in sorted({r["level"] for r in rows if r.get("channel", "-") != "-"}) + ["ALL"]:
            cells = []
            for ch in chans:
                rr = [r for r in rows if r.get("channel") == ch and lv in ("ALL", r["level"]) and r["v"] != "llm?"]
                ok = sum(r["v"] == "right" for r in rr)
                cells.append(f"{ok}/{len(rr)} ({100 * ok / max(1, len(rr)):.1f} %); "
                             f"{sum(not r['same'] and not r['before'] for r in rr)}")
            out.append(f"| {lv} | " + " | ".join(cells) + " |")
    groups = collections.defaultdict(list)
    for r in rows:
        groups[meaning(r)].append(r)
    gap = []                                            # a meaning right in one language, not in the other
    for k, rr in groups.items():
        en = [r for r in rr if r["level"] in EN_LEVELS and r["v"] != "llm?"]
        ko = [r for r in rr if r["level"] not in EN_LEVELS and r["v"] != "llm?"]
        if en and ko:
            er, kr = any(r["v"] == "right" for r in en), any(r["v"] == "right" for r in ko)
            bad_ko = [r for r in ko if r["v"] != "right"]
            bad_en = [r for r in en if r["v"] != "right"]
            if er and bad_ko:
                gap.append(("KO behind", k, bad_ko))
            if kr and bad_en:
                gap.append(("EN behind", k, bad_en))
    both = sum(1 for rr in groups.values() if any(r["level"] in EN_LEVELS for r in rr) and
               any(r["level"] not in EN_LEVELS for r in rr))
    lvgap = collections.Counter(r["level"] for _, _, bad in gap for r in bad)
    out += ["", f"**EN != KO**: {sum(g[0] == 'KO behind' for g in gap)} meanings where English is right and a Korean "
            f"level is not, {sum(g[0] == 'EN behind' for g in gap)} the other way, of {both} meanings said in both. "
            "Cases behind, per level: " + ", ".join(f"{k} {v}" for k, v in lvgap.most_common()), ""]
    # classes for the owners
    cls = collections.defaultdict(list)
    for r in rows:
        if not r["same"] and not r["before"]:
            cls[("L1", f"typed != voice: voice {r['v_canon'].split()[0]}, typed {r['t_canon'].split()[0]}")].append(r)
        if r["v"] in ("wrong", "motion"):
            cls[(owner(r, "voice"), f"{r['v']} ({r['src']}): {bc.base(r['set'])}")].append(r)
        elif r["t"] in ("wrong", "motion") and r["same"] is False and not r["handed"]:
            cls[("L1", f"typed {r['t']}: {bc.base(r['set'])}")].append(r)
    for who in ("L1", "B2", "H1", "T1"):
        mine = sorted(((k[1], v) for k, v in cls.items() if k[0] == who), key=lambda x: -len(x[1]))
        out += ["", f"## For {who} ({sum(len(v) for _, v in mine)} cases)", ""]
        for name, rr in mine:
            out.append(f"- **{name}**: {len(rr)}")
            for r in rr[:3]:
                out.append(f"  - [{r['round']} {r['set']} {r['level']}/{r['state']}] {r['text']!r} -> voice {r['voice']}, "
                           f"typed {r['typed']} (want {r['expect']})")
    out += ["", "## EN != KO examples (per meaning, 3 per kind and set)", ""]
    shown = collections.Counter()
    for kind, k, bad in gap:
        if shown[(kind, k[1])] < 3:
            shown[(kind, k[1])] += 1
            out.append(f"- {kind} [{k[0]} {k[1]} {k[2]} / {k[4]}] want {k[3]}: " +
                       "; ".join(f"{r['level']} {r['text']!r} -> {r['voice']}" for r in bad[:2]))
    return "\n".join(out) + "\n"


def main(args):
    use_llm, cached = "--llm" in args, "--cached" in args
    tag = args[args.index("--tag") + 1] if "--tag" in args else ("llm" if use_llm else "rules")
    sample = int(args[args.index("--sample") + 1]) if "--sample" in args else None
    rounds = [args[args.index("--round") + 1]] if "--round" in args else ROUNDS
    skip = {args[i + 1] for i, a in enumerate(args) if a in ("--tag", "--sample", "--round", "--merge")}
    only = [a for a in args if not a.startswith("-") and a not in skip]
    out = ROOT / "logs" / f"parity_{tag}"
    if "--merge" in args:                               # the reports of runs made side by side, as one
        rows = [r for t in args[args.index("--merge") + 1].split(",")
                for r in json.loads((ROOT / "logs" / f"parity_{t}.json").read_text())]
        out.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
        out.with_suffix(".md").write_text(report(rows, tag, 0, args))
        print(out.with_suffix(".md").read_text()[:3000])
        return
    old = {}
    if cached and out.with_suffix(".json").exists():
        old = {(r["round"], r["set"], r["text"], r["state"], str(r["before"])): r
               for r in json.loads(out.with_suffix(".json").read_text()) if r.get("raw")}
    if not use_llm:                                     # a mission's LLM pass only with --llm
        from assistant import steps
        steps._ollama = lambda *a: (_ for _ in ()).throw(command_check.NoLLM())
    rows, t0 = [], time.time()
    for rnd in rounds:
        for name in sets_of(rnd, only):
            for c in cases_of(rnd, name, sample):
                key = (rnd, name, c["text"], c["state"], str(c.get("before")))
                o = old.get(key)
                o = {"out": {"raw": o["raw"], "first": o["first"]}} if o else None
                try:
                    r = run_case(rnd, name, c, o, use_llm)
                except Exception as e:                      # noqa: BLE001
                    r = {"round": rnd, "set": name, "text": c["text"], "state": c["state"], "before": c.get("before"),
                         "expect": c.get("expect"), "intent": c.get("intent", ""), "map": c.get("map"),
                         "level": c.get("level") or "?", "lang": c.get("lang"), "voice": f"error {e!r}"[:120],
                         "typed": "-", "handed": False, "v_canon": "error", "t_canon": "error", "v": "wrong",
                         "t": "wrong", "src": "rules", "same": False, "raw": "", "first": ""}
                rows.append(r)
            print(f"{rnd} {name}: {len(rows)} ({time.time() - t0:.0f} s)", flush=True)
    out.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    text = report(rows, tag, time.time() - t0, args)
    out.with_suffix(".md").write_text(text)
    print(text[:3000])


if __name__ == "__main__":
    main(sys.argv[1:])
