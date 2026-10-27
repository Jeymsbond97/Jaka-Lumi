"""Scores the example bank (assistant/intent_bank.py) on case sets: how many requests the bank answers at once
(fast-lane hits), how many it gets wrong (a motion not asked for, or the wrong one: must stay 0) and how many it
leaves to the LLM. Nothing moves; only the embedding server is asked.

    .venv/bin/python tests/bank_check.py                 # the command, steps and song sets
    .venv/bin/python tests/bank_check.py --stress        # also every case the rules answer: the bank alone must not
                                                         # be wrong there either (its guards and margins, not the rules)
    .venv/bin/python tests/bank_check.py --blind         # tests/blind/train/*.py and tests/blind/r2/train/*.py too
    .venv/bin/python tests/bank_check.py -v              # print every hit too, not only the wrong ones
    .venv/bin/python tests/bank_check.py --blind --rounds r4,r6 --out bank_check_a3.md   # some rounds, own report
    .venv/bin/python tests/bank_check.py --blind --stress --fast --jobs 4 --rounds r6,r8,r9   # the bank alone, quick

A case reaches the bank when command_check's rules (lumi.route without the bank) leave it to the LLM.
-> logs/bank_check.md
"""
import collections
import importlib
import pathlib
import sys
import time

from assistant import brain, intent_bank
from tests import command_check
from tests.conversation_check import markers

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "logs" / "bank_check.md"
STEPS_SETS = ["steps_cases", "steps_cases2", "steps_cases3", "steps_cases4", "steps_cases5", "steps_cases6",
              "steps_cases7", "steps_cases8"]
CONF = ["home", "start", "end", "init", "final", "middle", "table_front", "stage", "booth_2", "dock2"]


def _from_steps(short):
    """A steps_cases answer as a command_check expect: a single go / move / turn / pick / arm step, "talk" for "?"
    (nothing may move), "chain" for several steps (the bank must never take one of those)."""
    if short.strip() == "?":
        return "skip"                               # the mission reader asks; a single quick rule may still read it
    parts = [p.strip() for p in short.split("|")]
    if len(parts) > 1:                              # go there, pick, come back: what a fetch does
        fetch = len(parts) == 3 and parts[0].startswith("go ") and parts[1].startswith("pick ") and parts[2] == "go here"
        return "chain | action:fetch" if fetch else "chain"
    w = parts[0].split()
    if w[0] == "go" and w[1] == "here":
        return "action:come | action:come_back"
    if w[0] == "go" and "," not in w[1]:
        return f"action:go_to {w[1]}"
    if w[0] == "move":
        return f"action:move {w[1]} {float(w[2]):g}"
    if w[0] == "turn":
        deg = float(w[1])
        return "action:turn around" if abs(deg) == 180 else f"action:turn {'left' if deg > 0 else 'right'} {abs(deg):g}"
    if w[0] == "pick":
        return "action:pick " + " ".join(w[1:])
    if w[0] == "arm":
        return f"action:arm {w[1]}"
    return "other"                                  # receive / place / give / wait / say: the hand or mission readers


def cases(blind):
    """[(set, text, expect, state, markers, before)]."""
    from tests.command_cases import CASES as C1
    from tests.command_cases2 import CASES as C2
    from tests.command_cases3 import CASES as C3
    from tests.song_cases_train import CASES as SONGS
    out = [("command", c["text"], c["expect"], c["state"], c.get("markers"), c["before"]) for c in C1 + C2 + C3]
    for name in STEPS_SETS:
        mod = importlib.import_module(f"tests.{name}")
        mk = CONF if hasattr(mod, "CONF") else None
        out += [(name, t, _from_steps(s), "idle", mk, None) for t, s in mod.CASES.items()]
    out += [("songs", t, "talk", "idle", None, None) for t, kind, ctx in SONGS if ctx is None]
    if blind:
        for f in sorted((ROOT / "tests" / "blind" / "train").glob("*.py")) + \
                sorted((ROOT / "tests" / "blind").glob("r*/train/*.py")):   # round 1, then r2, r3 ... (never held/)
            rnd = f.parent.parent.name if f.parent.parent.name != "blind" else ""
            if ROUNDS and (rnd or "r1") not in ROUNDS:
                continue
            mod = importlib.import_module(f"tests.blind.{rnd + '.' if rnd else ''}train.{f.stem}")
            tag = f"blind/{rnd + '/' if rnd else ''}{f.stem}"
            got = getattr(mod, "CASES", [])
            if isinstance(got, dict):                # missions: text -> {"steps", "markers"}
                out += [(tag, t, _from_steps(c["steps"]), "idle", c.get("markers"), None)
                        for t, c in got.items()]
                continue
            for c in got:
                if isinstance(c, dict) and "heard" in c:      # noise, others talking: nothing may move
                    if c["heard"].strip():
                        out.append((tag, c["heard"], "talk", "idle", None, None))
                elif isinstance(c, dict) and "expect" in c and "text" in c and c.get("state", "idle") in ("idle", "holding", "stuck"):
                    out.append((tag, c["text"], c["expect"], c.get("state", "idle"), c.get("markers"),
                                c.get("before"), c.get("stuck_goal")))
                elif isinstance(c, tuple) and c[2] is None:   # songs: no motion of the bank's may come of them
                    out.append((tag, c[0], "talk | sing", "idle", None, None))
    return out


def judge(expect, got):
    """'right' | 'wrong' for what the bank gave (got: 'action:<a> <target>')."""
    if expect == "skip":
        return "right"
    if expect in ("chain", "other"):
        return "wrong"                               # several steps or a hand request: never a single quick action
    return "right" if command_check.ok(expect.lower(), command_check.refused(got).lower()) == "right" else "wrong"


ROUNDS = []                                         # --rounds r1,r2: only these blind rounds (r1 = tests/blind/train)
KNOWN = {}
QUERIES = ROOT / "data" / "bank_check_queries.npz"   # the cases' embeddings, kept between runs (a re-run embeds only
                                                     # the words it has not seen: minutes instead of an hour)


def _cached_embed():
    """knowledge.embed with the case texts' vectors kept in QUERIES; returns the dict of known vectors."""
    import numpy as np
    from assistant import knowledge
    real, known = knowledge.embed, {}
    try:
        z = np.load(QUERIES)
        known = dict(zip(z["texts"].tolist(), z["vecs"]))
    except (OSError, ValueError, KeyError):
        pass

    def embed(texts):
        new = [t for t in dict.fromkeys(texts) if t not in known]
        if new:
            known.update(zip(new, real(new)))
        return np.array([known[t] for t in texts])
    knowledge.embed = embed
    return known


def _save_queries(known):
    import numpy as np
    tmp = QUERIES.with_suffix(".tmp.npz")
    np.savez(tmp, texts=np.array(list(known)), vecs=np.array(list(known.values())))
    tmp.replace(QUERIES)


def _run(job):
    """One share of the cases: (counts by set, wrong, hits, read times, missed, new query vectors)."""
    part, stress, fast, marks = job
    known = KNOWN                                  # the embed wrapper's own dict (in a forked job: its copy)
    n0 = set(known)
    from assistant import detour, steps
    steps._ollama = lambda *a: (_ for _ in ()).throw(command_check.NoLLM())
    real = intent_bank.read
    by = collections.defaultdict(collections.Counter)
    wrong, hits, times, missed = [], [], [], []
    for name, text, expect, state, mk, before, *goal in part:
        mk = mk or marks
        stuck = {"goal": goal[0]} if state == "stuck" and goal else None   # right after a blocked drive
        detour.recent = lambda: stuck
        b = brain.Brain()
        if before:
            b.history.append(tuple(before))
        brain.FORCED_LANG["lang"] = "ko" if brain.HANGUL.search(text) else "en"
        intent_bank.read = lambda *a, **k: None      # the rules alone first
        try:
            how = stuck and not fast and detour.read(text, mk, stuck["goal"])
            ruled = "llm?" if fast else f"detour {how}" if how else command_check.rules(text, state, mk, b)
        except command_check.NoLLM:
            ruled = "llm?"
        finally:
            intent_bank.read = real
        if ruled not in (None, "llm?") and not stress:
            by[name]["rules"] += 1
            continue
        t0 = time.time()
        got = intent_bank.read(text, mk, state == "holding")
        times.append(time.time() - t0)
        if not got:
            by[name]["llm" if ruled in (None, "llm?") else "rules"] += 1
            if ruled in (None, "llm?") and expect.startswith("action:"):
                missed.append(f"- [{name}/{state}] {text!r} (want {expect})")
            continue
        g = f"action:{got[0]} {got[1]}".strip()
        verdict = judge(expect, g)
        tag = "hit" if ruled in (None, "llm?") else "agree"
        if verdict == "wrong":
            by[name]["wrong"] += 1
            wrong.append(f"- [{name}/{state}] {text!r} -> {g} (want {expect}; rules: {ruled})")
        else:
            by[name][tag] += 1
            hits.append(f"- [{name}/{state}] {text!r} -> {g}")
    return by, wrong, hits, times, missed, {t: v for t, v in known.items() if t not in n0}


def main(args):
    """--fast: the rules are not run (0.8 s a case): wrong and llm are the same, hit and agree are counted together as
    hit. --jobs N: N processes (the embedding server is shared)."""
    global OUT
    if "--rounds" in args:
        ROUNDS[:] = args[args.index("--rounds") + 1].split(",")
    if "--out" in args:
        OUT = OUT.with_name(args[args.index("--out") + 1])
    marks = markers()
    global KNOWN
    known = KNOWN = _cached_embed()
    stress, verbose, fast = "--stress" in args, "-v" in args, "--fast" in args
    jobs = int(args[args.index("--jobs") + 1]) if "--jobs" in args else 1
    intent_bank._load(), intent_bank._codes()                # loaded once, shared by the forked jobs
    every = cases("--blind" in args)
    parts = [(every[i::jobs], stress, fast, marks) for i in range(jobs)]
    if jobs > 1:
        import multiprocessing
        with multiprocessing.get_context("fork").Pool(jobs) as pool:
            done = pool.map(_run, parts)
    else:
        done = [_run(parts[0])]
    by = collections.defaultdict(collections.Counter)
    wrong, hits, times, missed = [], [], [], []
    for b, w, h, t, m, v in done:
        for k, c in b.items():
            by[k].update(c)
        wrong += w
        hits += h
        times += t
        missed += m
        known.update(v)
    _save_queries(known)
    for c in by.values():
        c["cases"] = sum(c.values())
    total = sum(by.values(), collections.Counter())
    ms = sorted(times)
    lines = [f"# Bank check ({time.strftime('%Y-%m-%d %H:%M')}{', stress' if stress else ''}{', fast' if fast else ''})", "",
             f"bank: {len(intent_bank.examples())} wordings; read time median {1000 * ms[len(ms) // 2]:.0f} ms, "
             f"max {1000 * ms[-1]:.0f} ms over {len(ms)} reads" if ms else "", "",
             "hit: the rules left it to the LLM, the bank answered right; agree: the rules answered and the bank "
             "the same (--stress); wrong: the bank gave a motion not asked for (must be 0); llm: left to the LLM.", "",
             "| set | cases | rules | hit | agree | wrong | llm |", "|---|---|---|---|---|---|---|"]
    for k in sorted(by) + ["ALL"]:
        c = total if k == "ALL" else by[k]
        lines.append(f"| {k} | {c['cases']} | {c['rules']} | {c['hit']} | {c['agree']} | {c['wrong']} | {c['llm']} |")
    lines += ["", "## Wrong", ""] + wrong + ["", "## Hits", ""] + hits + \
        ["", "## Left to the LLM, a motion asked (the bank's room to grow)", ""] + missed
    OUT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:len(by) + 9]))
    print("\n".join(["", "Wrong:"] + wrong[:80]))
    if verbose:
        print("\n".join(["", "Hits:"] + hits))


if __name__ == "__main__":
    main(sys.argv[1:])
