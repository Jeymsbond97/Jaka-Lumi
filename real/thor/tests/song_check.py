"""Song wordings (tests/song_cases_train.py, song_cases_held.py, written blind) through Lumi's route, to what Lumi
does: sings a song (which one), says it can't sing the one asked (sing.unknown_reply), names its songs
(sing.list_reply), or only talks.

    .venv/bin/python tests/song_check.py train            # rules only; cases the rules leave are "llm?"
    .venv/bin/python tests/song_check.py held --llm       # those go to the real LLM, LLM_GAP_S apart, at most LLM_MAX
                                                          # new ones a run (answers saved by earlier runs are kept;
                                                          # delete logs/song_check_<set>.json after a prompt change)
    .venv/bin/python tests/song_check.py held --cached    # the LLM's answers saved by the last --llm run
    .venv/bin/python tests/song_check.py held --cached --bank   # the song bank (sing.bank_read) before the LLM

-> logs/song_check_<set>.md / .json. Verdicts: right; wrong_song (a song not asked for, or not the one asked);
missed (no song where one was asked); odd (no song, but the wrong kind of answer). Nothing moves.
"""
import collections
import json
import pathlib
import sys
import time

from assistant import abilities, brain, voice_words
from audio import sing
from tests import command_check
from tests.conversation_check import NOW, markers
from tests.song_contexts import SANG, SANG_SONG

ROOT = pathlib.Path(__file__).resolve().parents[1]
LLM_GAP_S = 6.0                 # s between two LLM calls (the robot's own LLM is in use)
LLM_MAX = 40                    # LLM calls per run (--llm); the next run goes on from the saved ones
TITLES = [n for s in sing.songs().values() for n in (s["title"].lower(), s["title_ko"])]


def sung(text, lang, before, whole=False):
    song = sing.choose(text, lang, SANG_SONG if before == SANG else None, whole)
    return "unknown" if song is None else "sing:" + song


def by_rules(text, lang, before, marks, b):
    """What lumi.answer() does before the LLM, or None."""
    last = before[1] if before else ""
    if voice_words.read(text, last):
        return "talk"
    if last.startswith("ACTION: sing") and sing.AFTER_SONG.search(text) and sing.asked(text, last):
        return sung(text, lang, before)
    if sing.list_asked(text):
        return "list"
    if abilities.answer(text, lang, last):
        return "talk"
    try:
        r = command_check.rules(text, "idle", marks, b)
    except command_check.NoLLM:
        return None
    if r == "sing" or r == "talk" and sing.asked(text, last):   # "talk": a song we don't have (command_check)
        return sung(text, lang, before)
    return r if r is None or r == "stop" or r.startswith("action:") else "talk"


def from_llm(raw, first, text, lang, before, marks):
    head = brain.Brain._action("ACTION: " + raw, text, marks) or {"action": "none", "target": ""}
    if head["action"] == "none" and brain.promised(first) == "sing":
        head = {"action": "sing"}
    if head["action"] == "sing":
        return sung(text, lang, before)
    if head["action"] in ("none", "end", "unclear", "search", "weather", "quiet"):
        low = first.lower()
        return "talk_titles" if sum(t in low for t in TITLES) >= 2 else "talk"
    return "stop" if head["action"] == "stop" else "action:" + head["action"]


def verdict(expect, got, before):
    kind = got.split(":")[0]
    for alt in expect.split(" | "):
        if alt == got or alt == "sing" and kind == "sing" or \
                alt == "sing_other" and kind == "sing" and got != "sing:" + SANG_SONG or \
                alt == "list" and got in ("list", "talk_titles") or \
                alt == "unknown" and got in ("talk", "talk_titles") or \
                alt in ("no", "stop") and got in ("talk", "talk_titles", "stop", "list"):
            return "right"
    if kind == "sing" or kind == "action":
        return "wrong_song"
    return "missed" if expect.split(" | ")[0].startswith("sing") else "odd"


def main(args):
    name = args[0]
    cases = __import__(f"tests.song_cases_{name}", fromlist=["CASES"]).CASES
    out = ROOT / "logs" / f"song_check_{name}"
    use_llm, cached, use_bank = "--llm" in args, "--cached" in args, "--bank" in args
    old = {}
    if out.with_suffix(".json").exists():
        old = {(r["text"], str(r["before"])): r for r in json.loads(out.with_suffix(".json").read_text()) if r.get("raw")}
    if not use_llm:
        from assistant import steps
        steps._ollama = lambda *a: (_ for _ in ()).throw(command_check.NoLLM())
    marks, rows, t0, bank_s, asked = markers(), [], time.time(), [], 0
    for text, expect, before in cases:
        lang = "ko" if brain.HANGUL.search(text) else "en"
        brain.FORCED_LANG["lang"] = lang
        b = brain.Brain()
        if before:
            b.history.append(tuple(before))
        got, by, raw, first = by_rules(text, lang, before, marks, b), "rules", "", ""
        if got is None and use_bank:
            t = time.time()
            label = sing.bank_read(text, before[1] if before else "")
            bank_s.append(time.time() - t)
            if label:
                got, by = (sung(text, lang, before) if label == "sing" else "list"), "bank"
        key = (text, str(before))
        if got is None and (cached or use_llm) and key in old:
            raw, first = old[key]["raw"], old[key]["first"]
        elif got is None and use_llm and asked < LLM_MAX:
            asked += 1
            gen = b.respond_stream(text, marks, now=NOW)
            head = next(gen)
            first = next(gen, "") or ""
            gen.close()
            raw = f"{head['action']} {head['target']}".strip()
            time.sleep(LLM_GAP_S)
        if got is None:
            got, by = (from_llm(raw, first, text, lang, before, marks), "llm") if raw else ("llm?", "-")
        v = verdict(expect, got, before) if got != "llm?" else "llm?"
        rows.append({"text": text, "expect": expect, "before": before, "got": got, "by": by, "raw": raw,
                     "first": first, "verdict": v})
        if v not in ("right", "llm?"):
            print(f"{v:10} {text!r} -> {got} (want {expect}) [{by}] {first[:60]!r}", flush=True)
    out.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    report(rows, out, time.time() - t0, bank_s)


def report(rows, out, secs, bank_s):
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        group = r["expect"].split(" | ")[0].split(":")[0]
        by[group][r["verdict"]] += 1
        by["ALL"][r["verdict"]] += 1
    lines = [f"# Song check {out.name} ({time.strftime('%Y-%m-%d %H:%M')}, {secs:.0f} s)", "",
             "| expect | cases | right | wrong_song | missed | odd | llm? |", "|---|---|---|---|---|---|---|"]
    for k in sorted(by, key=lambda k: (k == "ALL", k)):
        c = by[k]
        lines.append(f"| {k} | {sum(c.values())} | {c['right']} | {c['wrong_song']} | {c['missed']} | {c['odd']} | "
                     f"{c['llm?']} |")
    route = collections.Counter((r["by"], r["verdict"]) for r in rows)
    lines += ["", "By route: " + ", ".join(f"{k[0]} {k[1]} {n}" for k, n in sorted(route.items()))]
    if bank_s:
        lines.append(f"Bank: {len(bank_s)} looked up, {1000 * sum(bank_s) / len(bank_s):.0f} ms mean, "
                     f"{1000 * max(bank_s):.0f} ms max")
    lines += ["", "## Not right", ""] + [f"- {r['verdict']}: {r['text']!r} -> {r['got']} (want {r['expect']}) [{r['by']}] "
                                         f"{r['first'][:80]!r}" for r in rows if r["verdict"] not in ("right", "llm?")]
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:len(by) + 6]))


if __name__ == "__main__":
    main(sys.argv[1:])
