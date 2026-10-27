"""Blind set llm_reasoning (round r13 on, tests/blind/README.md "## r13"): requests and questions no fixed rule
covers, scored through the real route and the real model. Each case goes the way lumi.answer() sends it: the voice
settings, then the rules (tests/command_check.rules: drive words, lumi.route, chains, stop), then the model
(Brain.respond_stream with the state line, the reply read through to its end). The outcome is scored like a command
case (any listed outcome is right; a motion not listed is "motion", the worst) and a model reply also against the
case's must / must_not. A rule's fixed line is not checked against must (it is not the model's).

    .venv/bin/python tests/reasoning_check.py                    # r13 train, every case (long: ~2400 model turns)
    .venv/bin/python tests/reasoning_check.py --sample 120        # 120 cases, seeded (the same each run)
    .venv/bin/python tests/reasoning_check.py --kind cant,riddle --sample 60 --tag t1a
    .venv/bin/python tests/reasoning_check.py --rules             # no model: what the rules leave is "llm?"
    .venv/bin/python tests/reasoning_check.py --failed --tag t1a  # only the cases not right in that tag's last run

-> logs/reasoning_<round>_<tag>.md / .json. Only train sets: held-out sets are never read here.
"""
import collections
import importlib
import json
import pathlib
import random
import re
import sys
import time

from assistant import brain, voice_words
from tests import blind_check as bc
from tests import command_check

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED = 131
VOICE = {("volume", 1): "louder", ("volume", -1): "quieter", ("speed", 1): "faster", ("speed", -1): "slower"}


def model_turn(b, text, state, mk):
    """(route, action line, the whole reply) from the model, acted on like lumi.answer() (command_check.llm, with
    every sentence of the reply)."""
    brain.FORCED_LANG["lang"] = "ko" if brain.HANGUL.search(text) else "en"
    text = brain.self_correct(text, mk) or text
    gen = b.respond_stream(text, mk, now=command_check.HOLDING_NOW if state == "holding" else command_check.NOW)
    head, words = next(gen), list(gen)
    first = words[0] if words else ""
    if head["action"] == "none" and brain.promised(first) in ("sing", "wave") and \
            not (brain.not_an_order(text, asked=False) and brain.promised(first) == "wave"):
        head = {"action": brain.promised(first), "target": ""}
    target = (brain._mentions(text, mk).get("object") or "") if head["action"] == "receive" else head["target"]
    return command_check.act(head["action"], target, first, state), f"{head['action']} {target}".strip(), " ".join(words)


def score(c, use_llm):
    b = brain.Brain()
    for visitor, said in c["ctx"]:
        b.history.append((visitor, said))
    if c["before"]:
        b.history.append(tuple(c["before"]))
    mk, text, state = bc.marks_of(c), c["text"], c["state"]
    brain.FORCED_LANG["lang"] = c["lang"] if c["lang"] in ("en", "ko") else "ko" if brain.HANGUL.search(text) else "en"
    raw = reply = ""
    by = "rules"
    voice = voice_words.read(text, c["before"][1] if c["before"] else "")
    try:
        got = "voice " + VOICE[voice] if voice else command_check.rules(text, state, mk, b)
    except command_check.NoLLM:
        got = None
    if got is None:
        if not use_llm:
            return {"verdict": "llm?", "by": "-", "got": "llm?", "raw": "", "reply": "", "probs": []}
        got, raw, reply = model_turn(b, text, state, mk)
        by = "llm"
    got = command_check.refused(got)
    v = command_check.ok(c["expect"], got)
    v = "right" if v == "right" else "motion" if v == "wrong" and bc.MOTION.match(got) else "wrong"
    probs = []
    if by == "llm":
        probs = [f"missing /{p}/" for p in c["must"] if not re.search(p, reply, re.I)] + \
            [f"has /{p}/" for p in c["must_not"] if re.search(p, reply, re.I)]
        if probs and v == "right":
            v = "wrong"
    return {"verdict": v, "by": by, "got": got, "raw": raw, "reply": reply, "probs": probs}


def key(c):
    return f"{c['text']}|{c['state']}|{c['before']}|{c['ctx']}"


def report(rows, out, title, secs):
    def table(field):
        t = collections.defaultdict(collections.Counter)
        for r in rows:
            t[r[field]][r["verdict"]] += 1
            t[r[field]]["n"] += 1
        lines = [f"| {field} | right | wrong | motion | llm? |", "|---|---|---|---|---|"]
        for k in sorted(t):
            n = t[k]["n"]
            lines.append(f"| {k} | {t[k]['right']}/{n} ({100 * t[k]['right'] // n} %) | {t[k]['wrong']} | "
                         f"{t[k]['motion']} | {t[k]['llm?']} |")
        return "\n".join(lines)
    n = len(rows)
    right = sum(r["verdict"] == "right" for r in rows)
    md = [f"# {title} ({time.strftime('%Y-%m-%d %H:%M')}, model {brain.MODEL}, {secs:.0f} s)", "",
          f"right {right}/{n} ({100 * right // max(n, 1)} %), motions {sum(r['verdict'] == 'motion' for r in rows)}, "
          f"by the model {sum(r['by'] == 'llm' for r in rows)}", "", table("kind"), "", table("lang"), "",
          table("level"), "", "## Not right", ""]
    for r in rows:
        if r["verdict"] != "right":
            md.append(f"- {r['verdict'].upper()}: [{r['kind']}:{r['meaning']}, {r['level']}, {r['state']}] "
                      f"{r['text']!r} -> {r['got']} (want {r['expect']}) {r['reply'][:150]!r} {r['probs']}")
    out.with_suffix(".md").write_text("\n".join(md) + "\n")
    out.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print("\n".join(md[:4]))


def main(args):
    def opt(name, default=None):
        return args[args.index(name) + 1] if name in args else default
    rnd, tag = opt("--round", "r13"), opt("--tag", "")
    cases = importlib.import_module(f"tests.blind.{rnd}.train.llm_reasoning").CASES
    kinds = opt("--kind")
    if kinds:
        cases = [c for c in cases if c["kind"] in kinds.split(",")]
    out = ROOT / "logs" / (f"reasoning_{rnd}_{tag}" if tag else f"reasoning_{rnd}")
    if "--failed" in args:
        bad = {r["key"] for r in json.loads(out.with_suffix(".json").read_text()) if r["verdict"] != "right"}
        cases = [c for c in cases if key(c) in bad]
    if opt("--sample"):
        cases = random.Random(SEED).sample(cases, min(int(opt("--sample")), len(cases)))
    if opt("--limit"):
        cases = cases[:int(opt("--limit"))]
    bc.SCENE["now"] = None                         # no camera picture: seeing answers "can't see" where it looks
    t0, rows = time.time(), []
    for i, c in enumerate(cases, 1):
        try:
            r = score(c, "--rules" not in args)
        except Exception as e:                     # noqa: BLE001 - a crash fails that case
            r = {"verdict": "wrong", "by": "-", "got": "error", "raw": "", "reply": repr(e), "probs": []}
        rows.append({"key": key(c), **{k: c[k] for k in ("text", "lang", "level", "kind", "meaning", "state", "expect")},
                     **r})
        print(f"{i}/{len(cases)} {r['verdict']:6} [{c['kind']}] {c['text'][:60]!r} -> {r['got']} "
              f"{r['reply'][:80]!r} {r['probs']}", flush=True)
    report(rows, out, f"llm_reasoning {rnd} train{' ' + tag if tag else ''}", time.time() - t0)


if __name__ == "__main__":
    main(sys.argv[1:])
