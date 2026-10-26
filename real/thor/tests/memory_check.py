"""The memory dialogues (tests/blind/<round>/<split>/memory_dialogues.py) scored the way lumi.answer() goes: each
dialogue's memory (talks, things seen, the self state) loaded into assistant/memory.py (a temp folder, the
dialogue's clock), then every turn memory.reply first (as lumi._answer), else blind_check.turn_route (rules, then
the LLM with memory.turn_lines in its prompt). A forget turn must also delete the forget_person's talks.

    .venv/bin/python tests/memory_check.py                    # r6 train, the LLM where the rules leave a turn
    .venv/bin/python tests/memory_check.py --rules            # no LLM: those turns are "llm?"
    .venv/bin/python tests/memory_check.py --limit 20 -v      # the first 20 dialogues, wrong turns printed
    .venv/bin/python tests/memory_check.py --round r8 --files memory_dialogues_b   # every memory_dialogues* by default

-> logs/memory_check_<round>_<split>.md / .json. blind_check can score the set with score_memory (SCORERS).
"""
import collections
import datetime
import json
import pathlib
import sys
import tempfile
import time
import types
from unittest import mock

from assistant import battery, memory
from tests import blind_check, conversation_check

ROOT = pathlib.Path(__file__).resolve().parents[1]
_vecs = {}                      # title + summary -> vector (the embedding server once per text)
DOING = {"idle": ("I'm not doing any task right now.", "하고 있는 일은 없어요."),
         "talking": ("I'm talking with you; no task.", "지금은 이야기하고 있어요."),
         "waiting at the marker": ("I'm waiting at {place}.", "{place}에서 기다리고 있어요.")}


def epoch(iso):
    return datetime.datetime.fromisoformat(iso).timestamp()


def _vec(text):
    if text not in _vecs:
        from assistant import knowledge
        _vecs[text] = [round(float(x), 4) for x in knowledge.embed([text])[0]]
    return _vecs[text]


KO_CACHE = ROOT / "logs" / "memory_check_ko.json"   # title -> Korean title / summary (local: made from the sets)
_ko = {}


def _korean(title, summary, facts=()):
    """The Korean title, summary and facts a live talk carries (memory.summarise asks the LLM for them): made once per
    talk by the LLM and kept in KO_CACHE, so the rules-only runs need no LLM after the first."""
    key = f"{title}|{summary}"
    if not _ko and KO_CACHE.exists():
        _ko.update(json.loads(KO_CACHE.read_text()))
    if key not in _ko or facts and "facts_ko" not in _ko[key]:
        from assistant import brain
        out = json.loads(brain._chat([{"role": "system", "content": "Translate this robot's memory of a talk into Korean "
                                       "as JSON: {\"title_ko\": \"<the title, 1-4 Korean words>\", \"summary_ko\": \"<the "
                                       "summary in polite Korean (-요)>\", \"facts_ko\": [\"<each fact in polite Korean (-요)>\"]}. "
                                       "Names of people, robots and companies as they are said in Korean (JAKA = 자카)."},
                                      {"role": "user", "content": f"title: {title}\nsummary: {summary}\nfacts: {json.dumps(list(facts))}"}],
                                     {"type": "object", "properties": {"title_ko": {"type": "string"}, "summary_ko": {"type": "string"},
                                                                       "facts_ko": {"type": "array", "items": {"type": "string"}}},
                                      "required": ["title_ko", "summary_ko", "facts_ko"]}))
        old = _ko.get(key, {})                         # a title already made stays (the embeddings are cached by it)
        _ko[key] = {"title_ko": old.get("title_ko") or out["title_ko"].strip(),
                    "summary_ko": old.get("summary_ko") or out["summary_ko"].strip(),
                    "facts_ko": [f.strip() for f in out["facts_ko"]][:len(facts)]}
        KO_CACHE.write_text(json.dumps(_ko, ensure_ascii=False, indent=0))
    return _ko[key]


def _talk(t):
    ko = _korean(t["title"], t["summary"], t.get("facts", []))
    return {"t": epoch(t["when"]), "title": t["title"], "summary": t["summary"], "facts": t.get("facts", []),
            "commands": t.get("commands", []), "person": t.get("person"), **ko,
            "vec": _vec(f"{t['title']}. {t['summary']}"), "vec_ko": _vec(f"{ko['title_ko']}. {ko['summary_ko']}")}


def load(d):
    """The dialogue's memory into assistant/memory.py: a new temp folder, its clock, its self state."""
    mem, now = d["memory"], epoch(d["now"])
    memory.DIR = pathlib.Path(tempfile.mkdtemp(prefix="lumi_memory_"))
    memory.clock = lambda: now
    memory._recall.update(offered=[], left=[], talk=None, listed=[], at=0.0)
    memory._talk.update(name=None, track=mem.get("forget_person"), skip=False)   # who talks now (the forget's person)
    memory._save("talks", [_talk(t) for t in mem.get("talks", [])])
    memory._save("seen", [{"t": epoch(s["when"]), "name": memory._object(s["object"]) or s["object"],
                           "colour": s.get("colour"), "where": s.get("where")} for s in mem.get("seen", [])])
    st = mem.get("self") or {}
    held = st.get("holding")
    lines = memory.state_line({"arm": st.get("arm"), "gripper": "closed" if st.get("gripper") == "holding" else st.get("gripper"),
                               "holding": f"the {held}" if held else None})
    body = ", ".join(x for x in [f"head {st['head']}" if st.get("head") else "",
                                 f"lift {st['lift_mm']} mm" if st.get("lift_mm") is not None else "",
                                 f"at {st['place']}" if st.get("place") else "",
                                 f"battery {st['battery']} %" if st.get("battery") is not None else ""] if x)
    memory._state.update(arm=st.get("arm"), gripper="closed" if held else st.get("gripper"),
                         holding=f"the {held}" if held else None, place=st.get("place"), lift=st.get("lift_mm"), line=lines["arm"],
                         body=f"Your body now: {body}." if body else "", at=time.time())
    en, ko = DOING.get(st.get("doing"), ("", ""))
    hand = f" I'm holding the {held}." if held else ""
    battery.agv = types.SimpleNamespace(status=lambda: {"power_percent": st.get("battery"), "charge_state": False})
    conversation_check.NOW = en.format(place=st.get("place") or "the marker") + hand + memory.arm_line()
    conversation_check.NOW_KO = ko.format(place=st.get("place") or "마커") + memory.arm_line()


def _route(orig, d):
    """blind_check.turn_route with memory.reply first, as lumi._answer asks it."""
    def turn_route(b, say, lang, mk, state="idle", use_llm=True):
        memory._state["at"] = time.time()
        said = memory.reply(say, lang, history=b.history + [(say, "")])
        if said is None:
            return orig(b, say, lang, mk, state, use_llm)
        b.history.append((say, f"ACTION: none -\n{said}"))
        gone = d["memory"].get("forget_person")
        if said in memory.FORGOT.values() and gone and any(s.get("person") == gone for s in memory._load("talks")):
            return "action:forget_kept", said, "rules"     # confirmed, but the talks are still there
        return "none", said, "rules"
    return turn_route


def score_memory(d, old, use_llm):
    """One memory dialogue -> blind_check rows (the dialogue scorer with the memory loaded and asked first)."""
    load(d)
    with mock.patch.object(blind_check, "turn_route", _route(blind_check.turn_route, d)):
        rows = blind_check.score_dialogue(d, old, use_llm)
    for r in rows:      # "what's my name?" wanting the name from a talk with another person: the check can't say who
        if r["verdict"] == "wrong" and "(told in the talk about" in r["show"] and \
                any(n[:20] in r["show"] for n in memory.NO_NAME.values()):
            r["verdict"] = "who?"                          # the visitor is not known (re-id): not scored
    return rows


def main(args):
    rnd = args[args.index("--round") + 1] if "--round" in args else "r6"
    split = args[args.index("--split") + 1] if "--split" in args else "train"
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    use_llm = "--rules" not in args
    files = sorted(f.stem for f in (ROOT / "tests" / "blind" / rnd / split).glob("memory_dialogues*.py"))
    if "--files" in args:                              # e.g. --files memory_dialogues_b,memory_dialogues_c
        files = args[args.index("--files") + 1].split(",")
    cases = [d for f in files for d in blind_check.load(f"{rnd}.{split}", f)][:limit]
    rows, t0 = [], time.time()
    for i, d in enumerate(cases):
        for r in score_memory(d, None, use_llm):
            r["dialogue"], r["topic"], r["lang"] = i + 1, d["topic"], d["lang"]
            rows.append(r)
            if r["verdict"] in ("wrong", "motion", "error") and "-v" in args:
                print(f"  {r['verdict'].upper():6} d{i + 1} {r['show'][:300]}", flush=True)
    scored = [r for r in rows if r["verdict"] != "-"]
    kinds = collections.Counter(r["verdict"] for r in scored)
    by_tag = collections.defaultdict(collections.Counter)
    for r in scored:
        for tag in r["topic"].split(":", 1)[-1].split("/"):
            by_tag[tag][r["verdict"]] += 1
    lines = [f"# memory_dialogues {rnd} {split} ({'LLM' if use_llm else 'rules only'}, {time.time() - t0:.0f} s)", "",
             f"right {kinds['right']} / {len(scored)}; wrong {kinds['wrong']}, motion {kinds['motion']}, "
             f"llm? {kinds['llm?']}, error {kinds['error']}, who? {kinds['who?']} (the visitor's name from a talk the "
             f"check can't tie to them)", "", "| case kind | right | wrong | llm? |", "|---|---|---|---|"]
    lines += [f"| {t} | {c['right']} | {c['wrong'] + c['motion'] + c['error']} | {c['llm?']} |" for t, c in sorted(by_tag.items())]
    lines += ["", "## Wrong", ""] + [f"- d{r['dialogue']} {r['show'][:400]}" for r in scored
                                     if r["verdict"] in ("wrong", "motion", "error")]
    out = ROOT / "logs" / f"memory_check_{rnd}_{split}"
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    out.with_suffix(".json").write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    print("\n".join(lines[:4]))
    print(f"-> {out}.md")


if __name__ == "__main__":
    main(sys.argv[1:])
