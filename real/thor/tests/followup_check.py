"""Long dialogues of follow-up questions about Lumi's own answers and of questions Lumi has no fact for
(tests/dialogues_followup_en.py, _ko.py), through the same turn as tests/dialogue_check.py, keeping the context.

    .venv/bin/python tests/followup_check.py            # every dialogue -> logs/followup_check.md / .json
    .venv/bin/python tests/followup_check.py ko         # only dialogues whose persona or topic contains this
    .venv/bin/python tests/followup_check.py 3,17       # only these dialogues
    .venv/bin/python tests/followup_check.py --failed   # only the dialogues that failed in the saved .json
    .venv/bin/python tests/followup_check.py --blind 4  # the writer's blind train set (tests/blind/train/
                                                         # followup_dialogues.py), every 4th dialogue -> logs/followup_blind.*
    .venv/bin/python tests/followup_check.py --unknowns 2   # tests/blind/train/unknowns.py, every 2nd case
    .venv/bin/python tests/followup_check.py --blind 6 --r2 # the same from round 2 (tests/blind/r2/train/)

A turn made with S(say, said) is answered by code in lumi.py (a refusal, a seeing answer, a fixed line): its line
goes into the talk through lumi.keep_said, the way Lumi.talk_turn keeps it, and the next turn ("why?", "really?",
"왜요?") must go on from it. Every other turn is dialogue_check.run_turn (rules, then the model) and is checked with
dialogue_check.problems and its judge.
"""
import importlib
import json
import re
import sys

from assistant import brain, lumi
from tests import dialogue_check as dc
from tests.conversation_check import markers
from tests.dialogues_followup_en import DIALOGUES_FOLLOWUP_EN
from tests.dialogues_followup_ko import DIALOGUES_FOLLOWUP_KO

DIALOGUES = DIALOGUES_FOLLOWUP_EN + DIALOGUES_FOLLOWUP_KO
ROUND = "r2." if "--r2" in sys.argv else ""       # --r2: round 2's train sets (tests/blind/r2/train/)
dc.OUT_JSON, dc.OUT_MD = dc.ROOT / "logs" / "followup_check.json", dc.ROOT / "logs" / "followup_check.md"


def blind(step):
    """The blind train set in this file's format: a setup turn (its "reply") is said by code, an unscored turn is
    answered but not checked (expect_action "-")."""
    B = importlib.import_module(f"tests.blind.{ROUND}train.followup_dialogues").DIALOGUES
    out = []
    for d in B[::step]:
        turns = []
        for t in d["turns"]:
            if "reply" in t:
                turns.append({"say": t["say"], "said": t["reply"], "expect_action": "none"})
            else:
                turns.append({"say": t["say"], "expect_action": t.get("expect_action", "none") if t.get("scored") else "-",
                              "must": t.get("must", []) if t.get("scored") else [],
                              "must_not": t.get("must_not", []) if t.get("scored") else [], "check": t.get("check")})
        out.append({"who": d["who"], "topic": d["topic"], "lang": d["lang"], "turns": turns})
    return out


def unknowns(step):
    """tests/blind/train/unknowns.py as one-question dialogues after their context; the people in view are never the
    answer about the company."""
    CASES = importlib.import_module(f"tests.blind.{ROUND}train.unknowns").CASES
    out = []
    for c in CASES[::step]:
        no = list(c["must_not"])
        if c["kind"] == "unknown" and c.get("people_in_view"):
            no.append(rf"(?<![\d.]){c['people_in_view']}\s*(?:people|persons?|명|분)")
        turns = [{"say": v, "said": a, "expect_action": "none"} for v, a in c["ctx"]]
        turns.append({"say": c["text"], "expect_action": "none", "must": c["must"], "must_not": no,
                      "check": "says plainly it does not have that fact, nothing made up" if c["kind"] == "unknown"
                      else "answers the fact"})
        out.append({"who": c["kind"], "topic": c["kind"], "lang": c["lang"], "turns": turns})
    return out


def main(only=None, failed=False):
    marks = markers()
    saved = json.loads(dc.OUT_JSON.read_text()) if failed and dc.OUT_JSON.exists() else []
    if failed:
        ids = sorted({r["dialogue"] for r in saved if r["problems"]})
    elif only and re.fullmatch(r"[\d,]+", only):
        ids = [int(x) for x in only.split(",") if x]
    elif only:
        ids = [i for i, d in enumerate(DIALOGUES, 1) if only in d["who"] or only in d["topic"] or only == d["lang"]]
    else:
        ids = list(range(1, len(DIALOGUES) + 1))
    rows = []
    for n, i in enumerate(ids, 1):
        d, b = DIALOGUES[i - 1], brain.Brain()
        for j, turn in enumerate(d["turns"]):
            lang = dc.turn_lang(turn)
            before = list(b.history)
            if "said" in turn:                                   # answered by code: kept in the talk, not checked
                lumi.keep_said(b, turn["say"], turn["said"])
                r, reply, first = "code", turn["said"], None
            else:
                try:
                    r, reply, first, _ = dc.run_turn(b, turn["say"], lang, marks)
                except Exception as e:                           # noqa: BLE001 - a crash fails that turn
                    r, reply, first = "error", repr(e), None
            scored = r != "code" and turn.get("expect_action") != "-"
            probs = dc.problems(turn, lang, r, reply, first is not None) if scored else []
            if scored and first is not None and r not in ("action:end", "unclear"):
                ok, why = dc.judge(before, turn["say"], reply, turn.get("check"))
                if not ok:
                    probs.append(f"ignores the question ({why})")
            if scored and r == "unclear" and turn.get("expect_action", "none") != "unclear":
                probs.append("asked to say it again")
            rows.append({"dialogue": i, "turn": j + 1, "who": d["who"], "topic": d["topic"], "lang": lang,
                         "say": turn["say"], "expect": turn.get("expect_action", "none"), "check": turn.get("check"),
                         "got": r, "reply": reply, "llm": first is not None, "first_s": first, "total_s": 0.0,
                         "problems": probs})
            if r != "code":
                print(f"{i} ({n}/{len(ids)}).{j + 1} {'ok ' if not probs else 'BAD'} [{r}] {turn['say'][:40]!r} -> "
                      f"{reply[:90]!r} {probs}", flush=True)
        dc.OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    dc.report([r for r in rows if r["got"] != "code"])


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for flag, make in (("--blind", blind), ("--unknowns", unknowns)):
        if flag in sys.argv:
            DIALOGUES = make(int(args.pop(0)) if args else 1)
            name = ("followup_blind" if flag == "--blind" else "unknowns_check") + ("_r2" if ROUND else "")
            dc.OUT_JSON, dc.OUT_MD = dc.ROOT / "logs" / f"{name}.json", dc.ROOT / "logs" / f"{name}.md"
    main(args[0] if args else None, failed="--failed" in sys.argv)
