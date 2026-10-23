"""Multi-turn conversations (tests/dialogues.py) through Lumi's real routing and LLM, keeping the context.

    .venv/bin/python tests/dialogue_check.py              # 80 of them, every persona and topic (subset())
    .venv/bin/python tests/dialogue_check.py --all        # all dialogues -> logs/dialogue_check.md / .json
    .venv/bin/python tests/dialogue_check.py kid          # only dialogues whose persona or topic contains this
    .venv/bin/python tests/dialogue_check.py 9,21,309     # only these dialogues (numbers as in the report)
    .venv/bin/python tests/dialogue_check.py --resume     # go on after a stop: dialogues in the .json are kept
    .venv/bin/python tests/dialogue_check.py --rescore    # judge the saved replies again (no LLM for the replies)
    .venv/bin/python tests/dialogue_check.py --failed     # only the dialogues that failed in the saved .json
    .venv/bin/python tests/dialogue_check.py --commands   # body commands in any wording (tests/dialogues_commands.py)
    .venv/bin/python tests/dialogue_check.py --pragmatics # context reading (tests/dialogues_prag_en.py, _ko.py)

Each turn goes the way lumi.answer() sends it (tests/conversation_check.rules_route: stop, status, mission,
closing words, keyword rules; else brain.Brain().respond_stream). One Brain per dialogue keeps its history the
way lumi.py does: respond_stream adds the turn itself, a keyword-rule command adds "ACTION: <a> <target>", a
goodbye says brain.farewell() and resets the Brain. Lookups (weather, search, "not sure") are not made: the
route is checked, the reply is what was said before the lookup.

When assistant/talk_examples.py exists and brain.py does not use it yet, its pick() examples are added to the
system prompt per turn, the way the brain is meant to use them (EXAMPLES_IN_HARNESS below says so in the report).

Checks per turn: expect_action, must, must_not, the language of the reply, a few phrases the owner never wants,
and a judge (the same local model) that says whether the reply answers what was asked. Across all replies: the
same opening or the same sentence in more than REPEAT_SHARE of the replies. No audio, no robot (markers are
read once, read-only).
"""
import collections
import json
import pathlib
import re
import sys
import time

from assistant import brain, lumi
from tests.conversation_check import NOW, fill, llm_route, markers, refused, rules_route
from tests.dialogues import DIALOGUES

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "logs" / "dialogue_check.json"
OUT_MD = ROOT / "logs" / "dialogue_check.md"
REPEAT_SHARE = 0.03          # an opening / sentence in more than this share of all replies is flagged
OPENING_WORDS = 3            # words that make an "opening"
NEVER = [r"\bJAKA\b", r"자카", r"컷션|커션", r"how (can|may) i (help|assist)", r"무엇을 도와|어떻게 도와|도와드릴 일",
         r"nice to meet you.*how can", r"[一-鿿]"]   # owner: never said, whatever was asked

try:
    from assistant import talk_examples
except ImportError:
    talk_examples = None
BASE_SYSTEM = brain.SYSTEM
EXAMPLES_IN_HARNESS = talk_examples is not None and "talk_examples" not in (ROOT / "assistant/brain.py").read_text()

JUDGE = """You check a talking robot's reply. Robot facts: Lumi, a mobile robot by Cutshion Company, 2 years old.
Given the conversation so far, the visitor's last words and the robot's reply, decide: does the reply respond to
what the visitor just said (answers the question, or says it does not know, or does / refuses the request, or
asks them to repeat when the words make no sense)? A reply that changes the subject, answers an earlier question,
only greets (when the visitor did more than greet) or only offers help counts as false. {check}
Answer JSON {{"answers": true or false, "why": "a few words"}}."""


def turn_lang(turn):
    return turn.get("lang") or ("ko" if re.search(r"[가-힣]", turn["say"]) else "en")


def set_examples(text, lang):
    """The talk-example bank in the system prompt, as style examples (not answers)."""
    if not EXAMPLES_IN_HARNESS:
        return
    ex = talk_examples.pick(text, lang)
    brain.SYSTEM = BASE_SYSTEM + ("\nExamples of how you talk (style only: vary your words, never copy them, "
                                  "use only facts you really have):\n" +
                                  "\n".join(f"Visitor: {e[2]} -> Lumi: {e[3]}" for e in ex) if ex else "")


def run_turn(b, text, lang, marks):
    """(route, reply, first-sentence seconds or None, total seconds). Same order and history as lumi.answer()."""
    t0 = time.time()
    brain.FORCED_LANG["lang"] = lang
    place = lumi.consent_place(text, b, marks)                      # "그럼 가 보세요" after "p3로 갈 수 있어요?"
    if place:
        b.history.append((text, f"ACTION: go_to {place}"))
        return f"action:go_to {place}", "", None, time.time() - t0
    by_rule = rules_route(text, lang, marks)
    if by_rule:
        r = by_rule[0]
        if r == "action:end":                                       # lumi.end_conversation
            bye = b.farewell(text, lang)
            b.reset()
            return r, bye, time.time() - t0, time.time() - t0
        if r.startswith("action:") or r in ("weather", "search"):     # quick_command keeps it in the history
            a = r.split(":", 1)[-1].split(" ", 1)
            b.history.append((text, f"ACTION: {a[0]} {a[1] if len(a) > 1 else '-'}"))
        return r, by_rule[1], None, time.time() - t0
    set_examples(text, lang)
    about, repeating = b.topic(text), b.again(text)                 # before the turn is added to the history
    first, head, words = None, None, []
    for out in b.respond_stream(text, marks, now=NOW):
        if isinstance(out, dict):
            head = out
        else:
            words.append(out)
            first = first or time.time() - t0
    a, tgt = head["action"], head["target"]
    r, reply = llm_route(a, tgt, words, text, about, lang, repeating)          # lumi.py looks an unsure answer up instead
    if a == "end":
        b.reset()
    return r, reply, first, time.time() - t0


def action_ok(expect, got):
    """expect: 'none', 'search', 'go_to p3', 'end', ... alternatives split by ' | '."""
    for alt in expect.split(" | "):
        alt = alt.strip()
        if got == "none" and refused(alt):
            return True                                             # the reason the fingers can't take it
        if alt == "none" and got in ("none", "chat", "status"):
            return True
        if alt == "end" and got == "chat":
            return True                                             # "Thanks." alone: lumi ends after the silence
        if alt == "mission" and got.startswith("action:fetch"):
            return True                                             # the plain fetch does it (steps.is_mission is False)
        if got == "empty_hand" and alt in ("none", "give", "place", "fetch"):
            return True                                             # nothing is held in these checks
        if alt == "search" and got in ("search", "search(unsure)"):
            return True
        if alt in ("weather", "unclear", "status", "mission", "search(unsure)") and got == alt:
            return True
        if got.startswith("action:"):
            want, have = alt.lower().split(), got[7:].lower().split()
            if want and have and want[0] == have[0] and all(w in have[1:] for w in want[1:]):
                return True
    return False


def judge(history, text, reply, check):
    if not reply:
        return True, "no reply to judge"
    convo = "\n".join(f"Visitor: {q}\nRobot: {a}" for q, a in history[-3:])
    try:
        d = json.loads(brain._chat([
            {"role": "system", "content": JUDGE.format(check=f"A right reply here: {check}." if check else "")},
            {"role": "user", "content": f"Conversation so far:\n{convo or '(start)'}\n\nVisitor now: {text}\n"
                                        f"Robot reply: {reply}"}], fmt="json"))
        return bool(d.get("answers", True)), str(d.get("why", ""))[:100]
    except Exception as e:                                          # noqa: BLE001 - the judge is advisory
        return True, f"judge failed {e!r}"[:100]


def problems(turn, lang, route, reply, by_llm):
    out = []
    if not action_ok(turn.get("expect_action", "none"), route):
        out.append(f"action {route}, want {turn.get('expect_action', 'none')}")
    if not reply or not by_llm and route != "action:end":
        return out                                                  # fixed phrases of lumi.py: not checked here
    for m in turn.get("must", []):
        if not re.search(fill(m), reply, re.I):
            out.append(f"missing /{m}/")
    for m in turn.get("must_not", []) + NEVER:
        if re.search(fill(m), reply, re.I):
            out.append(f"says /{m}/")
    hangul = bool(re.search(r"[가-힣]", reply))
    lang = turn.get("reply_lang", lang)                             # "and in Korean?" asked in English
    if lang == "ko" and not hangul:
        out.append("English reply to Korean")
    if lang == "en" and hangul:
        out.append("Korean reply to English")
    return out


def norm(s):
    return re.sub(r"[^\w\s]", "", s.lower()).strip()


def repetition(rows):
    """Openings and sentences used in more than REPEAT_SHARE of the LLM replies: [(kind, text, count)]."""
    replies = [r["reply"] for r in rows if r["reply"] and r["llm"]]
    limit = max(2, REPEAT_SHARE * len(replies))
    opens = collections.Counter(" ".join(norm(r).split()[:OPENING_WORDS]) for r in replies)
    sents = collections.Counter(norm(s) for r in replies for s in set(re.split(r"(?<=[.!?])\s+", r)) if norm(s))
    out = [("opening", k, n) for k, n in opens.most_common() if n > limit]
    out += [("sentence", k, n) for k, n in sents.most_common() if n > limit]
    return out, len(replies)


SUBSET_SIZE = 80                                                  # dialogues in a default run (--all: every one)
SUBSET_TOPICS = ("follow_up", "correction", "switch", "repeat")   # kept first: they test the context
SUBSET_KO = 0.4                                                   # share of Korean dialogues aimed at


def subset(chosen=()):
    """Dialogue numbers (1-based) for a quick run: every persona and topic at least once, the context topics
    first, about SUBSET_KO Korean. chosen: numbers already in (a resumed run's), kept."""
    ids = set(chosen)
    while len(ids) < SUBSET_SIZE:
        who = {DIALOGUES[i - 1]["who"] for i in ids}
        topics = collections.Counter(DIALOGUES[i - 1]["topic"] for i in ids)
        ko = sum(DIALOGUES[i - 1]["lang"] == "ko" for i in ids) / max(1, len(ids))

        def gain(i):
            d = DIALOGUES[i - 1]
            return (2 * (d["who"] not in who) + 2 * (d["topic"] not in topics) +
                    (d["topic"] in SUBSET_TOPICS and topics[d["topic"]] < 3) + (d["lang"] == "ko" and ko < SUBSET_KO)
                    - topics[d["topic"]] / 10)
        rest = [i for i in range(1, len(DIALOGUES) + 1) if i not in ids]
        if not rest:
            break
        ids.add(max(rest, key=lambda i: (gain(i), -i)))
    return sorted(ids)


def main(only=None, everything=False, resume=False, failed=False):
    marks = markers()
    import numpy as np                                            # read the whole index now: a rebuild during the
    from assistant import knowledge                               # run would break np.load's lazy file reads
    with np.load(knowledge.INDEX, allow_pickle=True) as z:
        knowledge._index = {k: z[k] for k in z.files}
    saved = json.loads(OUT_JSON.read_text()) if (resume or failed) and OUT_JSON.exists() else []
    rows = saved if resume else []
    done = {r["dialogue"] for r in rows}
    if failed:
        ids = sorted({r["dialogue"] for r in saved if r["problems"]})
    elif only and re.fullmatch(r"[\d,]+", only):
        ids = [int(x) for x in only.split(",") if x]
    elif only:
        ids = [i for i, d in enumerate(DIALOGUES, 1) if only in d["who"] or only in d.get("topic", "")]
    else:
        ids = list(range(1, len(DIALOGUES) + 1)) if everything else subset(done)
    todo = [i for i in ids if i not in done]
    for n, i in enumerate(todo, 1):
        d, b = DIALOGUES[i - 1], brain.Brain()
        for j, turn in enumerate(d["turns"]):
            lang = turn_lang(turn)
            before = list(b.history)
            try:
                r, reply, first, total = run_turn(b, turn["say"], lang, marks)
            except Exception as e:                                  # noqa: BLE001 - a crash fails that turn
                r, reply, first, total = "error", repr(e), None, 0.0
            by_llm = first is not None
            probs = problems(turn, lang, r, reply, by_llm)
            if by_llm and r not in ("action:end", "unclear") and not lumi.HELLO_ONLY.match(turn["say"]):
                ok_j, why = judge(before, turn["say"], reply, turn.get("check"))
                if not ok_j:
                    probs.append(f"ignores the question ({why})")
            rows.append({"dialogue": i, "turn": j + 1, "who": d["who"], "topic": d.get("topic", "-"), "lang": lang,
                         "say": turn["say"], "expect": turn.get("expect_action", "none"), "check": turn.get("check"),
                         "got": r, "reply": reply, "llm": by_llm, "first_s": first, "total_s": total, "problems": probs})
            print(f"{i} ({n}/{len(todo)}).{j + 1} {'ok ' if not probs else 'BAD'} [{r}] {turn['say'][:40]!r} -> "
                  f"{reply[:90]!r} {probs}", flush=True)
        OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=1))   # after each: --resume goes on from here
    report(rows)


def _table(rows, key):
    groups = collections.defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    out = ["| group | turns | ok | % | dialogues all ok | first sentence median s |", "|---|---|---|---|---|---|"]
    for k in sorted(groups):
        g = groups[k]
        ok = sum(not r["problems"] for r in g)
        dl = collections.defaultdict(list)
        for r in g:
            dl[r["dialogue"]].append(not r["problems"])
        firsts = sorted(r["first_s"] for r in g if r["first_s"])
        med = f"{firsts[len(firsts) // 2]:.2f}" if firsts else "-"
        out.append(f"| {k} | {len(g)} | {ok} | {100 * ok // len(g)} | {sum(all(v) for v in dl.values())}/{len(dl)} | {med} |")
    return out


def cause(p):
    return re.sub(r"\(.*|/.*", "", p).strip() if not p.startswith("action") else "wrong action"


def report(rows):
    reps, n_llm = repetition(rows)
    firsts = sorted(r["first_s"] for r in rows if r["first_s"])
    n_dlg = len({r["dialogue"] for r in rows})
    dlg_ok = sum(all(not x["problems"] for x in rows if x["dialogue"] == d) for d in {r["dialogue"] for r in rows})
    causes = collections.Counter(cause(p) for r in rows for p in r["problems"])
    lines = [f"# Dialogue check ({time.strftime('%Y-%m-%d %H:%M')}, model {brain.MODEL})", "",
             f"{n_dlg} dialogues, {len(rows)} turns: {sum(not r['problems'] for r in rows)} turns right, "
             f"{dlg_ok} dialogues right in every turn. LLM replies: {n_llm}."
             + (f" First sentence median {firsts[len(firsts) // 2]:.2f} s, 90 % {firsts[int(len(firsts) * 0.9)]:.2f} s, "
                f"max {firsts[-1]:.2f} s." if firsts else ""),
             f"Talk examples in the prompt: {'yes (added by this harness)' if EXAMPLES_IN_HARNESS else 'as brain.py does'}.",
             "", "## Failure causes", "", "| cause | turns |", "|---|---|"]
    lines += [f"| {k} | {n} |" for k, n in causes.most_common()]
    lines += ["", f"## Repetition (more than {REPEAT_SHARE:.0%} of {n_llm} LLM replies)", ""]
    lines += [f"- {k} ×{n}: \"{t}\"" for k, t, n in reps] or ["- none"]
    lines += ["", "## By persona", ""] + _table(rows, lambda r: r["who"])
    lines += ["", "## By topic", ""] + _table(rows, lambda r: r["topic"])
    lines += ["", "## By language", ""] + _table(rows, lambda r: r["lang"])
    lines += ["", "## Failures", "", "| # | who | turn | said | want | got | problems | reply |", "|---|---|---|---|---|---|---|---|"]
    cell = lambda s: str(s).replace("|", "/").replace("\n", " ")[:220]
    for r in rows:
        if r["problems"]:
            lines.append(f"| {r['dialogue']} | {cell(r['who'])} | {r['turn']} | {cell(r['say'])} | {cell(r['expect'])} | "
                         f"{cell(r['got'])} | {cell('; '.join(r['problems']))} | {cell(r['reply'])} |")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:12]))


def rescore():
    """Saved routes and replies judged again by today's dialogues (must / must_not / action / repetition)."""
    old = {(r["dialogue"], r["turn"]): r for r in json.loads(OUT_JSON.read_text())}
    rows = []
    for i, d in enumerate(DIALOGUES, 1):
        for j, turn in enumerate(d["turns"]):
            r = old.get((i, j + 1))
            if r is None or r["say"] != turn["say"]:
                continue
            judged = [p for p in r["problems"] if p.startswith("ignores")]
            probs = problems(turn, r["lang"], r["got"], r["reply"], r["llm"]) + judged
            if r.get("reply_cut") and len(r["reply"]) >= 90:          # taken from a log line: the reply is cut
                probs = [p for p in probs if not p.startswith("missing") or p in r["problems"]]
            rows.append({**r, "who": d["who"], "topic": d.get("topic", "-"), "expect": turn.get("expect_action", "none"),
                         "problems": probs})
    report(rows)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--commands" in sys.argv:                          # its own set and report, the subset stays as it is
        from tests.dialogues_commands import DIALOGUES_COMMANDS
        DIALOGUES = DIALOGUES_COMMANDS
        OUT_JSON, OUT_MD = ROOT / "logs" / "dialogue_commands.json", ROOT / "logs" / "dialogue_commands.md"
        sys.argv.append("--all")
    if "--pragmatics" in sys.argv:                        # context reading: ellipsis, turned-back questions, endings
        from tests.dialogues_prag_en import DIALOGUES_PRAG_EN
        from tests.dialogues_prag_ko import DIALOGUES_PRAG_KO
        DIALOGUES = DIALOGUES_PRAG_EN + DIALOGUES_PRAG_KO
        OUT_JSON, OUT_MD = ROOT / "logs" / "dialogue_prag.json", ROOT / "logs" / "dialogue_prag.md"
        if not args:
            sys.argv.append("--all")
    if {"-h", "--help"} & set(sys.argv):
        print(__doc__.split("\n\n")[1])                      # the usage lines; never starts a run
    elif "--rescore" in sys.argv:
        rescore()
    else:
        main(args[0] if args else None, everything="--all" in sys.argv, resume="--resume" in sys.argv,
             failed="--failed" in sys.argv)
