"""Closing words read in context (tests/closing_cases.py) the way lumi.answer() takes them: the clear-goodbye rule
(lumi.talk_fate "end"), else the conversation model with the turns before (its action end ends the talk; on a
closing word it does not end, Lumi waits and silence ends the talk). Uses the LLM, never the robot.

    .venv/bin/python tests/closing_check.py          # every case -> a table, how many right, LLM wait per turn
    .venv/bin/python tests/closing_check.py holdout  # the second set (written after the change)

Right: want "end" -> end; want "on" -> no goodbye (an answer, or a wait); "either" -> anything. "late": an end the
rule left to the silence (a wait), counted wrong for "end".
"""
import statistics
import sys
import time

from assistant import brain, lumi
from tests.closing_cases import CASES, HOLDOUT
from tests.conversation_check import NOW

MARKS = ["home", "dock2", "p1", "p2", "p3"]


def route(lang, ctx, said):
    """(outcome, LLM seconds or None, reply): outcome end / wait / on."""
    brain.FORCED_LANG["lang"] = lang
    b = brain.Brain()
    b.history = [(q, f"ACTION: none -\n{a}") for q, a in ctx]
    fate = lumi.talk_fate(said)
    if fate == "end":
        return "end", None, "(goodbye by rule)"
    if fate == "wait":
        return "wait", None, "(waits by rule)"
    t = time.time()
    gen = b.respond_stream(said, MARKS, now=NOW)
    head = next(gen)
    first = next(gen, "")
    secs = time.time() - t
    reply = " ".join([first] + list(gen))
    if head["action"] == "end":
        return "end", secs, reply
    return ("wait" if fate == "close" else "on"), secs, reply


def main(cases=CASES):
    rows, llm_s = [], []
    for lang, ctx, said, want in cases:
        got, secs, reply = route(lang, ctx, said)
        ok = want == "either" or (got == "end") == (want == "end")
        rows.append(ok)
        if secs is not None:
            llm_s.append(secs)
        print(f"{'ok ' if ok else 'BAD'} want {want:<6} got {got:<4} {secs or 0:4.1f}s  {said!r} -> {reply[:90]!r}", flush=True)
    print(f"\n{sum(rows)}/{len(rows)} right; LLM asked for {len(llm_s)} of them" +
          (f", first sentence median {statistics.median(llm_s):.1f} s" if llm_s else ""))
    return sum(rows), len(rows)


if __name__ == "__main__":
    main(HOLDOUT if "holdout" in sys.argv else CASES)
