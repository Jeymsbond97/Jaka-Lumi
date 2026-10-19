"""Questions about Cutshion (tests/company_cases.py) through brain.Brain().respond_stream with the real model; a
search lumi.not_online() refuses gets lumi's fixed reply, as on the robot.

    .venv/bin/python tests/company_check.py          # -> logs/company_check.md

Each single case gets a fresh Brain; each dialogue one Brain for all its turns (history kept), so follow-ups and
topic switches are judged. Reads the map's marker names once (read-only); nothing moves.
"""
import pathlib
import re
import sys
import time

from assistant import brain, lumi
from tests.company_cases import CASES, DIALOGUES
from tests.conversation_check import NOW, markers

ROOT = pathlib.Path(__file__).resolve().parents[1]


def ask(b, text, lang, marks):
    """(action header, reply)."""
    brain.FORCED_LANG["lang"] = lang
    about, head, words = b.topic(text), None, []
    for out in b.respond_stream(text, marks, now=NOW):
        if isinstance(out, dict):
            head = out
        else:
            words.append(out)
    if head["action"] == "search" and lumi.not_online(about):      # lumi.answer() refuses it and says this
        return "none (search refused)", lumi.NOT_KNOWN[lang]
    return f"{head['action']} {head['target']}".strip(), " ".join(words)


def problems(case, lang, reply):
    out = [f"missing /{m}/" for m in case["must"] if not re.search(m, reply, re.I)]
    out += [f"says /{m}/" for m in case["must_not"] if re.search(m, reply, re.I)]
    if lang == "ko" and not re.search(r"[가-힣]", reply):
        out.append("English reply to Korean")
    if re.search(r"컷션|커션|컷시온|커치션", reply):
        out.append("Korean name not 쿳션")
    return out


def main():
    marks = markers()
    single, dial = [], []
    for i, c in enumerate(CASES, 1):
        action, reply = ask(brain.Brain(), c["text"], c["lang"], marks)
        p = problems(c, c["lang"], reply)
        single.append((c["text"], action, reply, p))
        print(f"{i}/{len(CASES)} {'FAIL' if p else 'ok  '} {c['text']} -> [{action}] {reply}", flush=True)
    for i, d in enumerate(DIALOGUES, 1):
        b, turns = brain.Brain(), []
        for t in d["turns"]:
            action, reply = ask(b, t["text"], d["lang"], marks)
            turns.append((t["text"], action, reply, problems(t, d["lang"], reply)))
        dial.append(turns)
        print(f"dialogue {i}/{len(DIALOGUES)} {'FAIL' if any(t[3] for t in turns) else 'ok'}", flush=True)
    ok1 = sum(not r[3] for r in single)
    ok2 = sum(not any(t[3] for t in turns) for turns in dial)
    lines = [f"# Company questions ({time.strftime('%Y-%m-%d %H:%M')}, {brain.MODEL})", "",
             f"Single questions: **{ok1}/{len(single)}**. Dialogues (every turn right): **{ok2}/{len(dial)}**.", "",
             "## Failed questions", ""]
    lines += [f"- `{q}` [{a}] {r!r}: {'; '.join(p)}" for q, a, r, p in single if p]
    lines += ["", "## Dialogues", ""]
    for n, turns in enumerate(dial, 1):
        lines.append(f"{n}. {'FAIL' if any(t[3] for t in turns) else 'ok'}")
        lines += [f"   - `{q}` [{a}] {r!r}" + (f" -> {'; '.join(p)}" if p else "") for q, a, r, p in turns]
    lines += ["", "## All questions", ""]
    lines += [f"- {'FAIL' if p else 'ok'} `{q}` [{a}] {r}" for q, a, r, p in single]
    (ROOT / "logs" / "company_check.md").write_text("\n".join(lines) + "\n")
    print(f"{ok1}/{len(single)} questions, {ok2}/{len(dial)} dialogues")
    return len(single) - ok1 + len(dial) - ok2


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
