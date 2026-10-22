"""Every conversation case through Lumi's real routing, without the robot and without speaking.

    .venv/bin/python tests/conversation_check.py                 # all cases -> logs/conversation_check.md / .json
    .venv/bin/python tests/conversation_check.py about_self      # only cases whose expected route contains this
    .venv/bin/python tests/conversation_check.py --rescore       # judge the saved replies again with today's cases

The order is lumi.answer()'s with no task running and nothing held, through the same functions: other script
(lumi.FOREIGN_SCRIPT), name only, stop (lumi.stop_order), status question (lumi.status_question), mission
(lumi.read_mission), goodbye (lumi.says_goodbye), closing words, keyword rules (brain.intent, the ones quick_command
acts on), then the LLM (brain.Brain().respond_stream with the real model, knowledge search and prompts). A search
lumi.not_online() refuses is route "none" with lumi's fixed reply; a first sentence lumi.look_up_unsure() sends to
the internet is reported as route "search(unsure)".
Also scores STATUS_Q on tests/status_cases.py. Reads the map's marker names once (read-only); nothing moves.
"""
import collections
import json
import pathlib
import re
import sys
import time

from assistant import brain
from assistant import steps
from assistant import lumi
from audio import sing
from assistant.lumi import STATUS_Q
from tests.conversation_cases import CASES
from tests.status_cases import NOT_STATUS, STATUS

ROOT = pathlib.Path(__file__).resolve().parents[1]
NOW = "I'm talking with you. I'm not doing any task right now, and my hand is empty."
NOW_KO = "지금은 이야기하고 있어요. 하고 있는 일은 없고, 손도 비어 있어요."     # lumi.now_doing() with nothing running
QUICK = {"go_to", "come", "quiet", "weather", "search", "move", "turn", "arm", "pick", "put", "move_object", "fetch",
         "look", "lift", "wave"}   # lumi.quick_command
TALK = {"about_self", "date_time", "chat", "action:none"}      # the LLM only talks: action none
WD_KO = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]


def markers():
    try:
        from robot import agv
        return agv.markers()
    except Exception:                                            # noqa: BLE001 - base off: the map of 2026-10-16
        return ['home', 'PInit', 'Wp', 'a', 'b', 'dock2', 'exit', 'final', 'p1', 'p10', 'p2', 'p3', 'p4', 'p5', 'p6',
                'p7', 'p8', 'p9']


HOUR_SLACK_S = 300           # s; a reply's hour may be the one before the check runs


def fill(pattern):
    t, p = time.localtime(), time.localtime(time.time() - HOUR_SLACK_S)   # "It is 10:59." checked at 11:00
    for k, v in {"{wd}": time.strftime("%A", t), "{wdk}": WD_KO[t.tm_wday], "{d}": str(t.tm_mday),
                 "{mon}": time.strftime("%B", t), "{h24}": f"{t.tm_hour}|{t.tm_hour:02d}|{p.tm_hour}|{p.tm_hour:02d}",
                 "{h12}": f"{t.tm_hour % 12 or 12}|{p.tm_hour % 12 or 12}",
                 "{y}": str(t.tm_year)}.items():
        pattern = pattern.replace(k, v)
    return pattern


def rules_route(text, lang, marks):
    """The routes lumi.answer() takes before the LLM: (route, reply, None, "") or None."""
    if lumi.FOREIGN_SCRIPT.search(text):
        return "unclear", "Sorry, I only understand English and Korean.", None, ""
    if lumi.NAME_ONLY.match(text):
        return "chat", "", None, ""
    if lumi.stop_order(text, marks):
        return "action:stop", "", None, ""
    if lumi.status_question(text):
        return "status", NOW if lang == "en" else NOW_KO, None, ""
    hand = brain.hand_request(text, False, None, marks)          # lumi.hand_command, nothing held
    if hand:
        if hand[0] == "receive":
            from manipulation import skills
            no = hand[1] and skills.refusal(hand[1])
            return ("none", no[0 if lang == "en" else 1], None, "") if no else ("action:receive", "", None, "")
        return ("empty_hand", lumi.EMPTY_HAND_SAY[lang], None, "") if hand[0] in ("give", "place") else ("none", "", None, "")
    read = lumi.read_mission(text, marks)
    if read and read[1]:
        return "mission_unread", f"unread: {read[1]}", None, ""
    if read:
        return "mission", steps.describe(read[0]), None, ""
    if lumi.empty_hand_request(text):                            # nothing is held in these checks
        return "empty_hand", lumi.EMPTY_HAND_SAY[lang], None, ""
    fate = lumi.talk_fate(text)
    if fate != "talk":
        return ("action:end" if fate == "end" else "chat"), "", None, ""
    if sing.asked(text):                                         # lumi.sing_song: a real song plays
        return "action:sing", "", None, ""
    rule = brain.intent(text, marks)
    if rule and rule[0] in QUICK:
        a, tgt = rule
        if a in ("pick", "move_object"):                         # lumi.object_task: the reason the fingers can't
            from manipulation import skills
            no = skills.refusal(next((c for c in set(brain.OBJECTS.values()) if tgt.endswith(c)), ""))
            if no:
                return "none", no[0 if lang == "en" else 1], None, ""
        if a == "search" and lumi.not_online(text):              # lumi.quick_command refuses it
            return "none", lumi.not_known(lang), None, ""
        return (a if a in ("weather", "search") else f"action:{a} {tgt}".strip()), "", None, ""
    return None


def llm_route(action, target, words, text, about, lang, repeating=False):
    """(route, reply) for the LLM's action line and first sentence, the way lumi.answer() acts on them."""
    if action == "search" and lumi.not_online(about):
        return "none", lumi.not_known(lang)
    if action in ("weather", "search"):
        return action, ""                                   # lumi.answer() closes the stream and looks it up
    if action == "unclear":
        return action, " ".join(words)
    if action in ("none", "sing") and not repeating and lumi.look_up_unsure(about, words[0] if words else "", text):
        return "search(unsure)", " ".join(words)
    return ("none" if action == "none" else f"action:{action} {target}".strip()), " ".join(words)


def route(text, lang, marks):
    """(route, reply, seconds to the first sentence or None, raw LLM header)."""
    by_rule = rules_route(text, lang, marks)
    if by_rule:
        return by_rule
    brain.FORCED_LANG["lang"] = lang
    t0, first, head, words, b = time.time(), None, None, [], brain.Brain()
    for out in b.respond_stream(text, marks, now=NOW):
        if isinstance(out, dict):
            head = out
        else:
            words.append(out)
            first = first or time.time() - t0
    a, tgt = head["action"], head["target"]
    r, reply = llm_route(a, tgt, words, text, text, lang)
    return "talk" if r == "none" else r, reply, first, f"{a} {tgt}".strip()


def refused(alt):
    """True for an expected pick / move of a thing the fingers can't take: lumi answers with the reason instead."""
    from manipulation import skills
    w = re.sub(r"^action:", "", alt).split(None, 1)
    return len(w) == 2 and w[0] in ("pick", "move_object") and \
        any(skills.refusal(c) for c in set(brain.OBJECTS.values()) if w[1].endswith(c))


def route_ok(expect, got):
    for alt in expect.split(" | "):
        if got == "none" and refused(alt):
            return True
        if alt in TALK or alt == "other_language":
            if got in ("talk", "none") or (alt == "other_language" and got == "unclear"):
                return True
            continue
        if alt.startswith("action:") and got.startswith("action:"):
            want, have = alt[7:].split(), got[7:].lower().split()
            if want[0] != (have or [""])[0]:
                continue
            if want[0] == "fetch" or all(w in have[1:] for w in want[1:]):
                return True
            continue
        if alt == "mission" and got.startswith("action:fetch"):
            return True                                          # the plain fetch does it (steps.is_mission is False)
        if got == "empty_hand" and re.match(r"chat$|action:(give|place|put|fetch)", alt):
            return True                                          # nothing is held in these checks
        if alt == got or (alt == "search" and got == "search(unsure)"):   # looked up after "not sure": still found
            return True
    return False


def content_problems(case, reply, spoken_by_llm):
    out = []
    for m in case["must"]:
        if not re.search(fill(m), reply, re.I):
            out.append(f"missing /{m}/")
    for m in case["must_not"]:
        if re.search(fill(m), reply, re.I):
            out.append(f"says /{m}/")
    if spoken_by_llm and reply:
        if re.search(r"[一-鿿]", reply):
            out.append("Chinese")
        hangul = bool(re.search(r"[가-힣]", reply))
        if case["lang"] == "ko" and not hangul:
            out.append("English reply to Korean")
        if case["lang"] == "en" and hangul and case["expect"] != "other_language":
            out.append("Korean reply to English")
    return out


def main(only=None):
    marks = markers()
    cases = [c for c in CASES if not only or only in c["expect"]]
    rows = []
    for i, c in enumerate(cases, 1):
        try:
            r, reply, first, raw = route(c["text"], c["lang"], marks)
        except Exception as e:                                   # noqa: BLE001 - a crash is a failure of that case
            r, reply, first, raw = "error", repr(e), None, ""
        ok_r = route_ok(c["expect"], r)
        probs = content_problems(c, reply, first is not None) if ok_r else []
        rows.append({**c, "got": r, "raw": raw, "reply": reply, "first_s": first, "route_ok": ok_r,
                     "problems": probs, "ok": ok_r and not probs})
        print(f"{i}/{len(cases)} {'ok ' if rows[-1]['ok'] else 'BAD'} [{r}] {c['text'][:50]!r} -> {reply[:80]!r} {probs}",
              flush=True)
    status_miss = [s for s in STATUS if not STATUS_Q.search(s)]
    status_false = [s for s in NOT_STATUS if STATUS_Q.search(s)]
    (ROOT / "logs" / "conversation_check.json").write_text(json.dumps(
        {"rows": rows, "status_miss": status_miss, "status_false": status_false}, ensure_ascii=False, indent=1))
    report(rows, status_miss, status_false)


def _table(rows, key):
    groups = collections.defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    out = ["| group | cases | route ok | all ok | first sentence median s |", "|---|---|---|---|---|"]
    for k in sorted(groups):
        g = groups[k]
        firsts = sorted(r["first_s"] for r in g if r["first_s"])
        med = f"{firsts[len(firsts) // 2]:.2f}" if firsts else "-"
        out.append(f"| {k} | {len(g)} | {sum(r['route_ok'] for r in g)} | {sum(r['ok'] for r in g)} | {med} |")
    return out


def report(rows, status_miss, status_false):
    firsts = sorted(r["first_s"] for r in rows if r["first_s"])
    lines = [f"# Conversation check ({time.strftime('%Y-%m-%d %H:%M')}, model {brain.MODEL})", "",
             f"{len(rows)} cases: route right {sum(r['route_ok'] for r in rows)}, all right {sum(r['ok'] for r in rows)}. "
             f"First sentence (LLM answers): median {firsts[len(firsts) // 2]:.2f} s, "
             f"90 % {firsts[int(len(firsts) * 0.9)]:.2f} s, max {firsts[-1]:.2f} s." if firsts else "", "",
             f"STATUS_Q: {len(STATUS) - len(status_miss)} / {len(STATUS)} status questions caught, "
             f"{len(status_false)} / {len(NOT_STATUS)} near misses wrongly caught.", "",
             "## By route", ""] + _table(rows, lambda r: r["expect"].split(" ")[0].split(":")[0] + f" ({r['lang']})") + \
            ["", "## By who", ""] + _table(rows, lambda r: r["who"]) + ["", "## Failures", "",
             "| expect | lang | text | got | raw header | problems | reply |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        if not r["ok"]:
            cell = lambda s: str(s).replace("|", "/").replace("\n", " ")[:160]
            lines.append(f"| {cell(r['expect'])} | {r['lang']} | {cell(r['text'])} | {cell(r['got'])} | {cell(r['raw'])} | "
                         f"{cell('; '.join(r['problems']))} | {cell(r['reply'])} |")
    lines += ["", "## STATUS_Q misses", ""] + [f"- {s}" for s in status_miss] + \
             ["", "## STATUS_Q false hits", ""] + [f"- {s}" for s in status_false]
    (ROOT / "logs" / "conversation_check.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:6]))


def rescore():
    """Route and reply from the last run, judged again by the current cases (same text and language)."""
    old = json.loads((ROOT / "logs" / "conversation_check.json").read_text())
    saved = {(r["text"], r["lang"]): r for r in old["rows"]}
    rows, marks = [], markers()
    for c in CASES:
        r = saved.get((c["text"], c["lang"]))
        if r is None:
            continue
        by_rule = rules_route(c["text"], c["lang"], marks)       # the rules may have changed since: no LLM needed
        if by_rule:
            r = {**r, "got": by_rule[0], "reply": by_rule[1], "first_s": None, "raw": ""}
        elif r["first_s"] is None and not r["raw"]:
            r = {**r, "got": "rerun needed"}                     # went by a rule then, to the LLM now
        ok_r = route_ok(c["expect"], r["got"])
        probs = content_problems(c, r["reply"], r["first_s"] is not None) if ok_r else []
        rows.append({**r, **c, "route_ok": ok_r, "problems": probs, "ok": ok_r and not probs})
    status_miss = [s for s in STATUS if not STATUS_Q.search(s)]
    status_false = [s for s in NOT_STATUS if STATUS_Q.search(s)]
    report(rows, status_miss, status_false)


if __name__ == "__main__":
    if sys.argv[1:] == ["--rescore"]:
        rescore()
    else:
        main(sys.argv[1] if len(sys.argv) > 1 else None)
