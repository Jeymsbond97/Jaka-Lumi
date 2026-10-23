"""The blind test sets (tests/blind/README.md) scored with the existing checkers' functions.

    .venv/bin/python tests/blind_check.py train                    # every set; the LLM where the rules leave a case
    .venv/bin/python tests/blind_check.py train commands_go unknowns   # only these sets ("commands" = every commands_*)
    .venv/bin/python tests/blind_check.py train --cached           # LLM / whisper outputs of the last run where the
                                                                   # case is the same (fast, after a rule change)
    .venv/bin/python tests/blind_check.py train --rules            # no LLM: what the rules leave is "llm?"
    .venv/bin/python tests/blind_check.py train --limit 20         # the first 20 cases (dialogues) of each set
    .venv/bin/python tests/blind_check.py held                     # held-out: only scored, never read to fix from
    .venv/bin/python tests/blind_check.py train --round r2         # round 2 (tests/blind/r2/train) -> blind_r2_train.*

-> logs/blind_<split>.md / .json (blind_r2_<split>.* with --round r2; a run of some sets keeps the others' saved
rows). Verdicts per case (per scored turn in the dialogue sets): right; wrong; motion (a motion not asked for, the worst wrong); llm? (left to the LLM in
a --rules run); error (the case crashed). "by LLM": how many went to the LLM (or the mission reader's LLM pass).

How each set is scored (the checker whose functions are used):
- commands_<cap>: tests/command_check (rules, llm, act, refused, ok) with the case's markers.
  Lumi.voice_setting is asked first ("voice louder"); state "stuck" fakes detour.recent() with stuck_goal and a
  detour.read reading is "detour retry / around / back / return" (detour.py's backup = back, back = return).
- commands_chain (r2): as commands, and a chain must have the "parts" in the order said (chain.plan's parts: the
  command, look / lift: the way, go_to: the place; questions as "ask"). One part done alone is wrong, not a motion.
- speed_short (r2): as commands; a "fast" case answered right by the LLM is wrong (it had to be read at once).
- commands_sing: tests/song_check (by_rules, the song bank as lumi.answer() asks it, from_llm, verdict).
- commands_missions: steps.read (rules, then the LLM pass) against tests/test_steps.short(); "?" right when words
  stay unread or steps.check refuses. A wrong reading that would run is a motion.
- seeing_dialogues: a fake scene per turn in place of vision.scene (snapshot, things, people, _persons, ask_vlm), then
  command_check.rules (drive words, lumi.route) with seeing.answer on it; what the rules leave goes through
  tests/dialogue_check.run_turn with seeing.facts_for in the prompt, as lumi.answer() does. dialogue_check.problems (must / must_not / action / language) on every reply.
- dialogues_mixed (r2): the dialogue's markers and hand state, scenes where given, like the seeing turns; expect
  "action:x" read as dialogue_check's "x"; a weather / search lookup counts as talk where talk is expected. No judge.
  A turn's "route" that differs is noted in the report, not counted.
- followup_dialogues: setup turns put into the history as said; back-channels answered, not judged; scored turns
  through dialogue_check.run_turn, problems and the judge.
- unknowns: the visitor / Lumi context in the history, people_in_view people in the fake scene, then like the seeing
  turns; tests/company_check.problems.
- silence_noise: the heard text through the real ears.transcribe filters (whisper faked to have written the text,
  the VAD to have found speech_s), then the wake-word path (session none / just_ended) or the talk path (open: own
  echo, noise words, "say it again", command_check.rules, the LLM). nothing: no words at all; no_action: at most one
  short line (SHORT_WORDS), no motion, the talk not ended.
- hearing: tests/asr_check (synth, room, judge) in both rooms with the case's markers; also wrong when a "not" text
  is heard. A slip that routes to another motion is a motion.
Nothing moves; no task API is called.
"""
import ast
import collections
import contextlib
import importlib
import json
import pathlib
import re
import sys
import time
from unittest import mock

import numpy as np

from assistant import brain, chain, detour, lumi, seeing, steps, voice_words
from audio import ears, sing
from tests import command_check, company_check, conversation_check, dialogue_check, song_check
from tests.blind.maps import MAPS
from vision import scene

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MARKERS = MAPS["office"]       # cases that name no place
SHORT_WORDS = 20                       # silence_noise "no_action": the one line allowed is at most this many words
MOTION = re.compile(r"^(?:action:(?!(?:end|none|stop|quiet|unclear|sing|weather|search)\b)|receive|give\b|place\b|"
                    r"mission|chain)")
SETS = ["commands_go", "commands_move", "commands_turn", "commands_look", "commands_lift", "commands_wave",
        "commands_reach", "commands_give", "commands_take", "commands_put", "commands_bring", "commands_follow",
        "commands_stop", "commands_status", "commands_chain", "commands_detour", "speed_short", "commands_sing",
        "commands_missions", "seeing_dialogues", "followup_dialogues", "dialogues_mixed", "unknowns", "silence_noise",
        "hearing"]                      # commands_chain, commands_detour, speed_short, dialogues_mixed: round r2 only


def marks_of(c):
    return c.get("markers") or DEFAULT_MARKERS


def row(key, verdict, by, show, **out):
    return {"key": key, "verdict": verdict, "by": by, "show": show, "out": out}


# ---------- tests/test_steps.py: its short() without running the module (it runs its checks on import) ----------
def _short():
    src = (ROOT / "tests" / "test_steps.py").read_text()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "short")
    ns = {"steps": steps}
    exec(compile(ast.Module([fn], []), "test_steps.py", "exec"), ns)
    return ns["short"]


short = _short()


# ---------- a fake scene for seeing.py (vision.scene stand-ins) ----------
SCENE = {"now": None}                  # the turn's scene (tests/blind/README.md), None: no camera picture
BEARING = {"left": 30.0, "front": 0.0, "right": -30.0}   # deg; scene.where() turns these into the side said


def _things(frames=None):
    out = []
    for o in (SCENE["now"] or {}).get("objects", []):
        b = BEARING[o["side"]]
        out.append({"name": seeing.SYNONYMS.get(o["name"], o["name"]), "colour": o.get("colour"),
                    "distance_m": o.get("dist_m"), "bearing_deg": b, "camera": "torso", "position_mm": None,
                    "score": 0.9, "box": [0, 0, 1, 1], "where": scene.where(b)})
    return sorted(out, key=lambda t: t["distance_m"] or 99)


def _people(frames=None):
    return sorted(({"distance_m": p["dist_m"], "bearing_deg": BEARING[p["side"]], "camera": "head"}
                   for p in (SCENE["now"] or {}).get("people", [])), key=lambda p: p["distance_m"] or 99)


def _person(p):
    def hand(side):
        if not p.get("hands_visible", True):
            return None
        held = p.get(f"{side}_hand")
        obj = {"name": seeing.SYNONYMS.get(held, held), "colour": None, "position_mm": None,
               "distance_m": p["dist_m"], "width_mm": None} if held else None
        return {"object": obj, "distance_m": p["dist_m"]}
    raised = {None: [], "both": ["left", "right"]}.get(p.get("raised"), [p.get("raised")])
    b = BEARING[p["side"]]
    return {"camera": "head", "box": [0, 0, 1, 1], "distance_m": p["dist_m"], "bearing_deg": b, "position_mm": None,
            "facing": True, "raised": raised, "pointing": None, "gesture": "hand_raised" if raised else None,
            "clothes": {"upper": p.get("top"), "lower": p.get("bottom"), "feet": None},
            "hands": {"left": hand("left"), "right": hand("right")}, "seen": 17, "where": scene.where(b)}


def _persons(frames=None):
    """Every person described, the speaker "A" first (the README's speaker; the real code takes the nearest), then
    the nearest: scene._front, person_in_front, object_in_hand, other_person work on these."""
    ps = sorted((SCENE["now"] or {}).get("people", []), key=lambda p: (p["id"] != "A", p["dist_m"] or 99))
    return [_person(p) for p in ps]


scene.snapshot = lambda cameras=None, since=None: [SCENE["now"]] if SCENE["now"] is not None else []
scene.things, scene.people, scene._persons = _things, _people, _persons
scene.ask_vlm = lambda *a, **k: None   # "what am I wearing?" asks the picture model: no picture here


def fresh_seeing():
    seeing._last.update(thing=None, name=None, kind=None, asked=None, parts=[], at=0.0)


STUCK = {"now": None}                  # the blocked drive "try again" means (commands_detour), never the live file
detour.recent = lambda: STUCK["now"]


def turn_route(b, say, lang, mk, state="idle", use_llm=True):
    """One turn the way lumi.answer() goes: command_check.rules (drive words, then lumi.route) with seeing.answer on
    the fake scene; what the rules leave through dialogue_check.run_turn with the cameras' facts (and the hand) in
    the prompt. (route in dialogue_check's notation, reply, by). A rule's fixed line is "" (not judged)."""
    brain.FORCED_LANG["lang"] = lang
    said = {}

    def seen(text):
        said["a"] = seeing.answer(text.strip(), lang)
        return said["a"] is not None
    with mock.patch.object(command_check, "seen", seen):
        try:
            got = command_check.rules(say, state, mk, b)
        except command_check.NoLLM:
            got = "llm?"
    if got == "seeing":
        b.history.append((say, f"ACTION: none -\n{said['a']}"))
        return "seeing", said["a"], "rules"
    if got == "status":                                    # lumi.now_doing's fixed line: kept, not judged
        b.history.append((say, command_check.HOLDING_NOW if state == "holding" else
                          conversation_check.NOW if lang == "en" else conversation_check.NOW_KO))
        return "status", "", "rules"
    if got == "search" and lumi.not_online(say):           # lumi.quick_command refuses it with this line
        reply = lumi.not_known(lang)
        b.history.append((say, reply))
        return "none", reply, "rules"
    if got == "end":
        reply = b.farewell(say, lang)
        b.reset()
        return "action:end", reply, "rules"
    if got is not None:
        got = command_check.refused(got)                   # a pick the fingers can't do is answered with the reason
        r = {"talk": "none", "ask": "none", "refuse": "none", "stop": "action:stop", "unclear": "unclear", "weather": "weather",
             "search": "search", "empty_hand": "empty_hand", "llm?": "llm?"}.get(got) or \
            ("mission" if got == "mission" else "action:chain" if got.startswith("chain:") else
             got if got.startswith("action:") else "action:" + got)
        if r.startswith("action:") or r == "mission":
            b.history.append((say, f"ACTION: {r.split(':', 1)[1] if ':' in r else r}"))
        return r, "", "rules"
    if not use_llm:
        return "llm?", "", "-"
    dialogue_check.NOW = (command_check.HOLDING_NOW if state == "holding" else conversation_check.NOW) + \
        seeing.facts_for(say)
    r, reply, first, _ = dialogue_check.run_turn(b, say, lang, mk)
    return r, reply, "llm" if first is not None else "rules"


def turn_verdict(probs, route):
    if not probs:
        return "right"
    return "motion" if any(p.startswith("action") for p in probs) and MOTION.match(route) else "wrong"


def said_route(r):
    """The kind of route a turn took, in the sets' "route" words."""
    return "seeing" if r == "seeing" else "status" if r == "status" else "end" if r == "action:end" else \
        "act" if MOTION.match(r) or r == "action:stop" else "talk"


def chain_tokens(plan):
    """chain.plan's parts as the sets' "parts" notation, one token per command: "look left", "put", "ask"."""
    out = []
    for kind, words, what in plan:
        if kind == "talk":
            out.append("ask")
        elif kind == "quick":
            out.append(f"{what[0]} {what[1]}".strip())
        else:
            for s in what:
                d = s["do"]
                out.append({"place": "put", "go": f"go_to {s.get('to')}", "pick": f"pick {s.get('object')}",
                            "receive": "take"}.get(d, d))
    return out


def chain_ok(want, plan):
    """The parts in the order said: the same commands (look / lift: the same way; go_to: the same place)."""
    got = chain_tokens(plan)
    if len(got) != len(want):
        return False
    for w, g in zip(want, got):
        w = "ask" if w.startswith("ask:") else w
        ww, gw = w.split(), g.split()
        if ww[0] != gw[0] or ww[0] in ("look", "lift", "go_to", "pick") and len(ww) > 1 and ww[1] not in gw[1:]:
            return False
    return True


DETOUR = {"retry": "retry", "backup": "back", "around": "around", "back": "return"}   # detour.read -> the sets' words
VOICE = {("volume", 1): "louder", ("volume", -1): "quieter", ("speed", 1): "faster", ("speed", -1): "slower"}


# ---------- the sets ----------
def score_commands(c, old, use_llm):
    b = brain.Brain()
    if c["before"]:
        b.history.append(tuple(c["before"]))
    brain.FORCED_LANG["lang"] = c["lang"] if c["lang"] in ("en", "ko") else "ko"
    mk, key, text = marks_of(c), KEYS["commands"](c), c["text"]
    state = "idle" if c["state"] == "stuck" else c["state"]
    STUCK["now"] = {"goal": c["stuck_goal"], "rest": [{"do": "go", "to": c["stuck_goal"]}], "start": None,
                    "tries": 0, "time": time.time()} if c["state"] == "stuck" else None
    raw = first = ""
    voice = voice_words.read(text, c["before"][1] if c["before"] else "")    # Lumi.voice_setting comes first
    try:
        got = "voice " + VOICE[voice] if voice else command_check.rules(text, state, mk, b)
    except command_check.NoLLM:
        got = "llm?"
    if got is None and STUCK["now"]:                       # lumi.route's "detour" kind (command_check has none)
        how = detour.read(text, mk, c["stuck_goal"])
        got = f"detour {DETOUR.get(how, how)}" if how else None
    if got is None:
        if old and old["out"].get("raw"):                  # as command_check --cached: today's Brain._action on it
            raw, first = old["out"]["raw"], old["out"]["first"]
            head = brain.Brain._action("ACTION: " + raw, brain.self_correct(text, mk) or text, mk) or \
                {"action": "none", "target": ""}
            tgt = head["target"] if head["action"] != "receive" else raw.partition(" ")[2]
            got = command_check.act(head["action"], tgt, first, state)
        elif use_llm:
            got, raw, first = command_check.llm(text, state, mk, b)
        else:
            got = "llm?"
    STUCK["now"] = None
    if got == "llm?":
        v = "llm?"
    else:
        got = command_check.refused(got)
        v = command_check.ok(c["expect"], got)
        v = "right" if v == "right" else "motion" if v == "wrong" and (MOTION.match(got) or got.startswith("detour")) \
            else "wrong"
        part_words = {p.split()[0].replace("put", "place") for p in c.get("parts") or ()}
        if v == "motion" and (got.split()[0].removeprefix("action:").replace("put", "place") in part_words or
                              got == "mission"):
            v = "wrong"                                    # one part of the chain (or its steps) done, the rest not
        if v == "right" and c.get("parts") and got.startswith("chain:"):   # commands_chain: the parts in order
            plan = chain.plan(brain.self_correct(text, mk) or text, mk, lumi.NOT_A_STEP) or []
            if not chain_ok(c["parts"], plan):
                v, got = "wrong", f"{got} {chain_tokens(plan)}"
        if v == "right" and c.get("fast") and raw:        # speed_short: must be read without the LLM
            v, got = "wrong", got + " (by the LLM, not at once)"
    return row(key, v, "llm" if raw else "rules", f"[{c['state']}] {text!r} -> {got} (want {c['expect']}"
               + (f", parts {c['parts']}" if c.get("parts") else "") + f") {first[:70]!r}", raw=raw, first=first)


def score_sing(c, old, use_llm):
    text, expect, before = c
    lang = "ko" if brain.HANGUL.search(text) else "en"
    brain.FORCED_LANG["lang"] = lang
    b = brain.Brain()
    if before:
        b.history.append(tuple(before))
    before = tuple(before) if before else None
    got, by, raw, first = song_check.by_rules(text, lang, before, DEFAULT_MARKERS, b), "rules", "", ""
    if got is None:                                        # lumi.answer(): the song bank before the LLM
        label = sing.bank_read(text, before[1] if before else "")
        if label:
            got, by = (song_check.sung(text, lang, before) if label == "sing" else "list"), "bank"
    if got is None:
        if old and old["out"].get("raw"):
            raw, first = old["out"]["raw"], old["out"]["first"]
        elif use_llm:
            gen = b.respond_stream(text, DEFAULT_MARKERS, now=conversation_check.NOW)
            head = next(gen)
            first = next(gen, "") or ""
            gen.close()
            raw = f"{head['action']} {head['target']}".strip()
        got, by = (song_check.from_llm(raw, first, text, lang, before, DEFAULT_MARKERS), "llm") if raw else ("llm?", "-")
    v = song_check.verdict(expect, got, before) if got != "llm?" else "llm?"
    v = {"right": "right", "llm?": "llm?", "wrong_song": "motion" if got.startswith("action:") else "wrong"}.get(v, "wrong")
    return row(KEYS["commands_sing"](c), v, by, f"{text!r} -> {got} (want {expect}) [{by}] {first[:70]!r}", raw=raw, first=first)


def score_missions(c, old, use_llm):
    text, case = c
    mk, want = marks_of(case), case["steps"]
    if old and old["by"] == "llm":
        got, unread, by = old["out"]["got"], old["out"]["unread"], "llm"
    else:
        got, unread, by = steps.read(text, mk, llm=use_llm)
    refused = bool(steps.check(got, False, mk)) if got and not unread else True
    if want.strip() == "?":
        v = "right" if unread or refused else "motion"
    elif not unread and got == [short(s.strip()) for s in want.split(" | ")]:
        v = "right"
    elif unread and not use_llm and by == "rules" and len(steps._split(steps._norm(steps._cut_says(text)[0], mk))) >= 2:
        v = "llm?"                                         # the LLM pass would read it
    else:
        v = "wrong" if unread or refused else "motion"
    return row(text, v, by, f"{text!r}\n  want {want}\n  got  {got} unread {unread} [{by}]",
               got=json.loads(json.dumps(got)), unread=unread)


def score_dialogue(d, old, use_llm, judge=False):
    """seeing_dialogues, followup_dialogues, dialogues_mixed: one Brain for the dialogue; setup turns put into the
    history as said; back-channels (scored False) answered, not judged; a turn's scene (if any) is what the cameras
    see then. judge: dialogue_check.judge on the LLM's replies too (followup_dialogues)."""
    b, rows = brain.Brain(), []
    mk, state = d.get("markers") or DEFAULT_MARKERS, d.get("state", "idle")
    fresh_seeing()
    SCENE["now"] = None
    for j, turn in enumerate(d["turns"]):
        key = f"{j + 1}|{turn['say']}"
        if turn.get("reply") is not None and not turn.get("scored", True):   # a setup: Lumi said this
            b.history.append((turn["say"], turn["reply"]))
            continue
        if "scene" in turn:
            SCENE["now"] = turn["scene"]
        lang = dialogue_check.turn_lang(turn)
        scored = turn.get("scored", True)
        o = (old or {}).get(key)
        before = list(b.history)
        judged = None
        try:
            if o and o["by"] == "llm":                     # --cached: the saved LLM turn into the history as said
                r, reply, by, judged = o["out"]["route"], o["out"]["reply"], "llm", o["out"].get("judged")
                b.history.append((turn["say"], reply))
            else:
                r, reply, by = turn_route(b, turn["say"], lang, mk, state, use_llm)
            if r == "llm?":
                rows.append(row(key, "llm?" if scored else "-", "-", "", route="", reply=""))
                b.history.append((turn["say"], ""))
                continue
            if r.startswith("action:give") or r.startswith("action:place"):
                state = "idle"                             # handed over / put down: the hand is empty now
            if not scored:
                rows.append(row(key, "-", by, "", route=r, reply=reply))
                continue
            want = dict(turn, expect_action=" | ".join(a.strip().removeprefix("action:")
                                                       for a in turn.get("expect_action", "none").split(" | ")))
            looked_up = r in ("weather", "search", "search(unsure)") and \
                not dialogue_check.action_ok(want["expect_action"], r)   # a lookup's answer is talk (not checked)
            probs = dialogue_check.problems(want, lang, "none" if r == "seeing" or looked_up else r, reply,
                                            bool(reply)) + \
                (["no reply"] if not reply and turn.get("must") and by == "llm" else [])
            if judge and by == "llm" and reply:
                if judged is None:
                    judged = list(dialogue_check.judge(before, turn["say"], reply, turn.get("check")))
                if not judged[0]:
                    probs.append(f"ignores the question ({judged[1]})")
            way = turn.get("route")
            note = f" (route {said_route(r)}, want {way})" if way and {way, said_route(r)} - {"llm", "talk"} and \
                way != said_route(r) else ""
            v = turn_verdict(probs, r)
        except Exception as e:                             # noqa: BLE001 - a crash fails that turn
            r, reply, by, probs, note, v = "error", repr(e), "-", [repr(e)], "", "error"
        rows.append(row(key, v, by, f"{d['topic']} t{j + 1} {turn['say']!r} -> [{r}] {reply[:120]!r} {probs}{note} "
                                    f"(check: {turn.get('check')})", route=r, reply=reply, judged=judged))
    return rows


def score_unknowns(c, old, use_llm):
    mk, lang = DEFAULT_MARKERS, c["lang"]
    SCENE["now"] = {"people": [{"id": chr(65 + i), "dist_m": round(1.2 + 0.5 * i, 1), "side": "front", "top": None,
                                "bottom": None, "left_hand": None, "right_hand": None, "hands_visible": False,
                                "raised": None} for i in range(c["people_in_view"])], "objects": []}
    fresh_seeing()
    b = brain.Brain()
    for visitor, said in c["ctx"]:
        b.history.append((visitor, said))
    key = KEYS["unknowns"](c)
    if old and old["by"] == "llm":
        r, reply, by = old["out"]["route"], old["out"]["reply"], "llm"
    else:
        r, reply, by = turn_route(b, c["text"], lang, mk, "idle", use_llm)
        if r == "llm?":
            return row(key, "llm?", "-", "", route="", reply="")
    probs = company_check.problems(c, lang, reply)
    v = "right" if not probs else "motion" if MOTION.match(r) else "wrong"
    return row(key, v, by, f"[{c.get('topic', c['kind'])}, {c['kind']}, {c['people_in_view']} in view] {c['text']!r} "
                           f"-> [{r}] {reply[:140]!r} {probs}", route=r, reply=reply)


@contextlib.contextmanager
def heard_as(text, speech_s):
    """ears.transcribe on a stand-in: whisper wrote `text` (sure of it), the VAD found speech_s s of speech."""
    lang = "korean" if re.search(r"[가-힣]", text) else "english"
    with mock.patch.object(ears, "_infer", lambda wav, prompt, language=None: (text, language and
                           {"en": "english", "ko": "korean"}.get(language, language) or lang, 0.9, -0.3)), \
            mock.patch.object(ears, "speech_seconds", lambda audio: speech_s), \
            mock.patch.object(ears, "ensure_stt_server", lambda: None), \
            mock.patch.object(ears, "HEARD_DIR", ROOT / "logs" / "blind_heard"):
        yield


def score_silence(c, old, use_llm):
    """What Lumi does with this sound: (outcome, words said). Outcomes: silent, greet, again (say it again), talk,
    end, motion, llm?."""
    x, heard = c["ctx"], c["heard"]
    key = KEYS["silence_noise"](c)
    with heard_as(heard, x["speech_s"]):
        text = ears.transcribe(np.zeros(int(max(1.0, x["speech_s"] + 0.5) * ears.RATE), np.int16))
    raw = first = ""
    if x["session"] in ("none", "just_ended"):             # idle: Lumi.check_wake
        m = lumi.WAKE.search(text or "") or lumi.HELLO_ONLY.match(text or "")
        if x["from_lumi_speaker"] or not m:
            outcome, said = "silent", ""
        else:
            rest = text[m.end():].strip(" ,.!?")
            outcome, said, text = ("greet", lumi.WAKE_REPLY["en"], "") if len(rest) <= 2 else ("talk", "", rest)
    else:
        outcome, said = "talk", ""
        with mock.patch.object(lumi.mouth, "recent_speech", lambda s=30.0: x["lumi_said"] or ""):
            echo = text and lumi.Lumi.own_echo(text)
        if not text or echo and x["from_lumi_speaker"] or lumi.NOISE_WORDS.fullmatch(text.strip()):
            outcome = "silent"
    if outcome == "talk":                                  # Lumi._answer
        last = x["lumi_said"] or ""
        if not ears.understood() and not (ears.heard_clearly() and lumi.own_command(text, last)):
            outcome, said = "again", "Sorry, I didn't catch that. Could you say it again?"
        else:
            b = brain.Brain()
            if x["lumi_said"]:
                b.history.append(("", x["lumi_said"]))
            brain.FORCED_LANG["lang"] = ears.heard_lang("en")
            try:
                got = command_check.rules(text, "idle", DEFAULT_MARKERS, b)
            except command_check.NoLLM:
                got = "llm?"
            if got is None:
                if old and old["out"].get("raw"):
                    raw, first = old["out"]["raw"], old["out"]["first"]
                    got = command_check.act(raw.split(" ", 1)[0], raw.partition(" ")[2], first, "idle")
                elif use_llm:
                    got, raw, first = command_check.llm(text, "idle", DEFAULT_MARKERS, b)
                else:
                    got = "llm?"
            said = first or got
            outcome = "llm?" if got == "llm?" else "motion" if MOTION.match(got) else \
                "end" if got in ("action:end", "end") or raw.startswith("end") else "talk"
            if outcome == "talk" and got == "talk" and not first:
                said = "(a fixed line)"
    if outcome == "llm?":
        v = "llm?"
    elif outcome == "motion":
        v = "motion"
    elif c["expect"] == "nothing":
        v = "right" if outcome == "silent" else "wrong"
    else:                                                  # no_action: one short line at most, the talk goes on
        v = "right" if outcome == "silent" or outcome == "talk" and len(said.split()) <= SHORT_WORDS else "wrong"
    return row(key, v, "llm" if raw else "rules", f"[{c['kind']}, {x['session']}, want {c['expect']}] {heard!r} -> "
                                                  f"{outcome}: {said[:100]!r} (text {text!r})", raw=raw, first=first)


def score_hearing(cases, old_rows, use_llm, rooms=("near", "far")):
    from tests import asr_check
    asr_check.OUT.mkdir(parents=True, exist_ok=True)
    old = {r["key"]: r for r in old_rows or []}
    rng, rows, started = np.random.default_rng(5), [], False
    for i, c in enumerate(cases):
        voice, speed = asr_check.VOICES[i % 10], [0.85, 0.95, 1.05, 1.15][(i // 10) % 4]
        marks = marks_of(c)
        for rname in rooms:
            key = f"{c['text']}|{rname}"
            try:
                o = old.get(key)
                if o:
                    heard, stt = o["out"]["heard"], o["out"]["stt"]
                    ears.last_stt.clear()
                    ears.last_stt.update(stt)
                else:
                    if not started:
                        asr_check.start_server()
                        started = True
                    x = asr_check.synth(c["say"], voice, speed)
                    others = [asr_check.synth(cases[(i * 7 + k * 13) % len(cases)]["say"], asr_check.VOICES[(i + k + 3) % 10],
                                              1.0) * 0.5 for k in range(3)] if asr_check.ROOMS[rname]["babble"] and c["say"] else ()
                    audio = asr_check.room(x, asr_check.ROOMS[rname], rng, others)
                    ears.set_names(marks)
                    heard = ears.transcribe(audio)
                    stt = dict(ears.last_stt)
                verdict, why = asr_check.judge(c, heard, stt)
                bad = [n for n in c.get("not", []) if heard and re.search(rf"(?<!\w){re.escape(n)}(?!\w)", heard, re.I)]
                if bad and verdict == "right":
                    verdict, why = "slip", f"heard as {bad}"
                got = asr_check.route(heard, brain.Brain(), marks) if heard else "llm"
                want = asr_check.route(c["text"], brain.Brain(), marks) if c["kind"] != "noise" else "llm"
                v = "right" if verdict == "right" else "motion" if MOTION.match(got) and got != want else "wrong"
            except Exception as e:                         # noqa: BLE001
                heard, stt, verdict, why, v = "", {}, "error", repr(e), "error"
            rows.append(row(key, v, "whisper", f"[{c['kind']}/{c['lang']}/{rname}] {c['text']!r} -> {heard!r} "
                                               f"{verdict}: {why}", heard=heard, stt=stt))
    return rows


KEYS = {"commands": lambda c: f"{c['text']}|{c['state']}|{c['before']}",
        "commands_sing": lambda c: f"{c[0]}|{tuple(c[2]) if c[2] else None}",
        "commands_missions": lambda c: c[0],
        "unknowns": lambda c: f"{c['text']}|{c['ctx']}|{c['people_in_view']}",
        "silence_noise": lambda c: f"{c['heard']}|{json.dumps(c['ctx'], sort_keys=True)}"}
SCORERS = {"commands_sing": score_sing, "commands_missions": score_missions, "seeing_dialogues": score_dialogue,
           "followup_dialogues": lambda d, old, use_llm: score_dialogue(d, old, use_llm, judge=True),
           "dialogues_mixed": score_dialogue, "unknowns": score_unknowns, "silence_noise": score_silence}


def load(split, name):
    """split: "train" / "held", or "r2.train" for a round's folder."""
    mod = importlib.import_module(f"tests.blind.{split}.{name}")
    cases = getattr(mod, "CASES", None) or getattr(mod, "DIALOGUES")
    return list(cases.items()) if isinstance(cases, dict) else cases


def run_set(split, name, old_rows, use_llm, cached, limit):
    cases = load(split, name)[:limit]
    old_rows = old_rows if cached else []
    if name == "hearing":
        return score_hearing(cases, old_rows, use_llm)
    fn = SCORERS.get(name, score_commands)
    dialogue = "dialogues" in name
    if dialogue:                                           # saved rows of each dialogue, in order
        old = collections.defaultdict(dict)
        for r in old_rows:
            old[r["dialogue"]][r["key"]] = r
    else:
        old = {r["key"]: r for r in old_rows}
    rows = []
    for i, c in enumerate(cases):
        n = len(rows)
        try:
            if dialogue:
                got = fn(c, old.get(i + 1), use_llm)
                for r in got:
                    r["dialogue"] = i + 1
                rows += got
            else:
                rows.append(fn(c, old.get(KEYS.get(name, KEYS["commands"])(c)), use_llm))
        except Exception as e:                             # noqa: BLE001 - a crash fails that case
            rows.append(row(str(c)[:200], "error", "-", f"{str(c)[:150]} -> {e!r}"))
        for r in rows[n:]:
            if r["verdict"] in ("wrong", "motion", "error") and "-v" in sys.argv:
                print(f"  {r['verdict'].upper():6} {r['show'][:200]}", flush=True)
    return rows


KINDS = ["right", "wrong", "motion", "llm?", "error"]


def report(split, saved, secs):
    lines = [f"# Blind sets, {split} ({time.strftime('%Y-%m-%d %H:%M')}, model {brain.MODEL}, this run {secs:.0f} s)", "",
             "right / wrong / motion (a motion not asked for: the worst) / llm? (left to the LLM, --rules run) / error. "
             "Dialogue sets count scored turns. by LLM: answered by the LLM.", "",
             "| set | run | cases | right | % | wrong | motion | llm? | error | by LLM |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    tot = collections.Counter()
    for name in [n for n in SETS if n in saved]:
        rows = [r for r in saved[name]["rows"] if r["verdict"] != "-"]
        c = collections.Counter(r["verdict"] for r in rows)
        tot.update(c)
        n, llm_n = len(rows), sum(r["by"] == "llm" for r in rows)
        lines.append(f"| {name} | {saved[name]['when']} | {n} | {c['right']} | {100 * c['right'] // max(1, n)} | "
                     f"{c['wrong']} | {c['motion']} | {c['llm?']} | {c['error']} | {llm_n} |")
    n = sum(tot.values())
    lines.append(f"| ALL | | {n} | {tot['right']} | {100 * tot['right'] // max(1, n)} | {tot['wrong']} | "
                 f"{tot['motion']} | {tot['llm?']} | {tot['error']} | |")
    for name in [n for n in SETS if n in saved]:
        rows = saved[name]["rows"]
        dl = {}
        for r in rows:
            if "dialogue" in r and r["verdict"] != "-":
                dl[r["dialogue"]] = dl.get(r["dialogue"], True) and r["verdict"] == "right"
        bad = [r for v in ("motion", "error", "wrong") for r in rows if r["verdict"] == v]
        lines += ["", f"## {name}" + (f" (dialogues right in every turn: {sum(dl.values())}/{len(dl)})" if dl else ""), ""]
        lines += [f"- {r['verdict'].upper()}: " + (f"d{r['dialogue']} " if "dialogue" in r else "") +
                  r["show"].replace("\n", "\n  ") for r in bad] or ["- none"]
    out = ROOT / "logs" / f"blind_{split}.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:len(saved) + 7]))


def main(args):
    if not args or args[0] not in ("train", "held") or {"-h", "--help"} & set(args):
        print(__doc__.split("\n\n")[1])
        return
    split = args[0]
    use_llm, cached = "--rules" not in args, "--cached" in args
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    rnd = args[args.index("--round") + 1] if "--round" in args else ""
    names = [a for a in args[1:] if not a.startswith("-") and not a.isdigit() and a != rnd]
    folder, tag = (f"{rnd}.{split}", f"{rnd}_{split}") if rnd else (split, split)
    todo = [n for n in SETS if (not names or any(n == a or n.startswith(a) for a in names)) and
            (ROOT / "tests" / "blind" / folder.replace(".", "/") / f"{n}.py").exists()]
    if not use_llm:                                        # the mission reader's LLM pass only with the LLM
        steps._ollama = lambda *a: (_ for _ in ()).throw(command_check.NoLLM())
    from assistant import knowledge                        # the whole index read now (dialogue_check does so too)
    with np.load(knowledge.INDEX, allow_pickle=True) as z:
        knowledge._index = {k: z[k] for k in z.files}
    path = ROOT / "logs" / f"blind_{tag}.json"
    saved = json.loads(path.read_text()) if path.exists() else {}
    t0 = time.time()
    for name in todo:
        t1 = time.time()
        print(f"{name} ...", flush=True)
        rows = run_set(folder, name, saved.get(name, {}).get("rows", []), use_llm, cached, limit)
        saved[name] = {"when": time.strftime("%m-%d %H:%M") + (" rules" if not use_llm else "") +
                       (f" first {limit}" if limit else ""), "rows": rows}
        c = collections.Counter(r["verdict"] for r in rows if r["verdict"] != "-")
        print(f"{name}: " + ", ".join(f"{k} {c[k]}" for k in KINDS if c[k]) + f" ({time.time() - t1:.0f} s)", flush=True)
        path.write_text(json.dumps(saved, ensure_ascii=False, indent=0))
    report(tag, saved, time.time() - t0)


if __name__ == "__main__":
    main(sys.argv[1:])
