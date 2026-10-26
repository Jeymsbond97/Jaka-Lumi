"""The blind test sets (tests/blind/README.md) scored with the existing checkers' functions.

    .venv/bin/python tests/blind_check.py train                    # every set; the LLM where the rules leave a case
    .venv/bin/python tests/blind_check.py train commands_go unknowns   # only these sets ("commands" = every commands_*)
    .venv/bin/python tests/blind_check.py train --cached           # LLM / whisper outputs of the last run where the
                                                                   # case is the same (fast, after a rule change)
    .venv/bin/python tests/blind_check.py train --rules            # no LLM: what the rules leave is "llm?"
    .venv/bin/python tests/blind_check.py train --limit 20         # the first 20 cases (dialogues) of each set
    .venv/bin/python tests/blind_check.py held --round r6 --sample 100   # 100 cases per file, seeded (the same each run)
    .venv/bin/python tests/blind_check.py held                     # held-out: only scored, never read to fix from
    .venv/bin/python tests/blind_check.py train --round r2         # round 2 (tests/blind/r2/train) -> blind_r2_train.*
    .venv/bin/python tests/blind_check.py train --rules --tag a3   # -> blind_train_a3.* (the shared files untouched)

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

from assistant import battery, brain, chain, detour, lumi, seeing, steps, voice_words
from audio import ears, sing
from tests import command_check, company_check, conversation_check, dialogue_check, song_check
from tests.blind.maps import MAPS
from robot import head as robot_head
from vision import pointing, scene

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MARKERS = MAPS["office"]       # cases that name no place
SHORT_WORDS = 20                       # silence_noise "no_action": the one line allowed is at most this many words
MOTION = re.compile(r"^(?:action:(?!(?:end|none|stop|quiet|unclear|sing|weather|search)\b)|receive|give\b|place\b|"
                    r"mission|chain)")
SETS = ["commands_go", "commands_move", "commands_turn", "commands_look", "commands_lift", "commands_wave",
        "commands_reach", "commands_give", "commands_take", "commands_put", "commands_bring", "commands_follow",
        "commands_stop", "commands_status", "commands_chain", "commands_detour", "speed_short", "commands_sing",
        "commands_missions", "seeing_dialogues", "followup_dialogues", "dialogues_mixed", "unknowns", "silence_noise",
        "hearing", "questions_world", "memory_dialogues", "commands_come", "commands_hand", "commands_point",
        "commands_voice", "commands_waist", "commands_more", "closing_context", "lookup_dialogues"]
                                        # commands_chain, commands_detour, speed_short, dialogues_mixed: round r2 on;
                                        # questions_world, memory_dialogues: r6 on. Any other file in a round's folder
                                        # is scored too, by the set its name grows ("commands_go_b" as commands_go)


def base(name):
    """The set a file's name belongs to: "commands_go_b" / "seeing_dialogues_2" -> "commands_go" / "seeing_dialogues"."""
    m = re.fullmatch(r"(.+?)_(?:[a-z]|\d+)", name)
    return m.group(1) if m and m.group(1) in SETS else name


def ordered(names):
    """Set names in SETS order, then the rest (growth files next to their set)."""
    return sorted(names, key=lambda n: (SETS.index(base(n)) if base(n) in SETS else len(SETS), n))


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
            "hands": {"left": hand("left"), "right": hand("right")}, "seen": 17, "where": scene.where(b),
            "posture": p.get("posture"), "_scene": p,     # _scene: the r6 fields (hair, glasses ...) for the fake VLM
            "looks": seeing.scene_looks(_looks_fields(p))}   # what seeing reads instead of asking the VLM (A6)


def _looks_fields(p):
    """The r6 person fields in the names seeing.scene_looks reads (hat / bag as "black cap", the pattern, the bottoms)."""
    said = lambda x: f"{x.get('colour') or ''} {x['kind']}".strip() if isinstance(x, dict) else x
    return dict(p, pattern=p.get("top_pattern"), bottom_type=p.get("bottom_kind"), hat=said(p.get("hat")),
                bag=said(p.get("bag")))


def _persons(frames=None):
    """Every person described, the speaker "A" first (the README's speaker; the real code takes the nearest), then
    the nearest: scene._front, person_in_front, object_in_hand, other_person work on these."""
    ps = sorted((SCENE["now"] or {}).get("people", []), key=lambda p: (p["id"] != "A", p["dist_m"] or 99))
    return [_person(p) for p in ps]


scene.snapshot = lambda cameras=None, since=None: [SCENE["now"]] if SCENE["now"] is not None else []
scene.things, scene.people, scene._persons = _things, _people, _persons
scene.speaker_key = lambda d, b: 0     # scene._front's stable sort keeps _persons' order: the speaker A first (A6)
VLM_ASKED = [("glasses", r"glass|안경|선글"), ("hat", r"\bhat|\bcap\b|beanie|모자|캡"), ("hair", r"hair|머리"),
             ("bag", r"bag|backpack|가방|배낭"), ("top_pattern", r"pattern|stripe|check|dot|print|무늬|줄무늬|체크|땡땡이"),
             ("bottom_kind", r"jeans|trousers|pants|skirt|shorts|바지|청바지|치마|반바지"),
             ("posture", r"sit|stand|crouch|squat|앉|서 ?있|쪼그"), ("action", r"doing|하고 있|뭐 해|뭐해")]


def _vlm_said(p, field, lang):
    """One fact of the r6 scene person as the picture model would say it, or None when the scene leaves it open."""
    ko = lang == "ko"
    v = p.get(field)
    if field == "glasses":
        return None if v is None else ("선글라스를 쓰고 있어요." if ko else "You are wearing sunglasses.") if v == "sunglasses" \
            else ("안경을 쓰고 있어요." if ko else "You are wearing glasses.") if v else \
            ("안경은 안 쓰고 있어요." if ko else "You are not wearing glasses.")
    if field in ("hat", "bag"):
        if field not in p:
            return None
        if not v:
            return {"hat": ("모자는 안 쓰고 있어요.", "You are not wearing a hat."),
                    "bag": ("가방은 없어요.", "You have no bag.")}[field][0 if ko else 1]
        return f"{v.get('colour') or ''} {v['kind']}을(를) {'쓰고' if field == 'hat' else '메고'} 있어요." if ko else \
            f"You have a {v.get('colour') or ''} {v['kind']}.".replace("  ", " ")
    if field == "hair":
        return None if not v else (f"머리는 {v.get('colour') or ''} {v.get('length') or ''}이에요." if ko else
                                   f"You have {v.get('length') or ''} {v.get('colour') or ''} hair.".replace("  ", " "))
    if v is None:
        return None
    return {"top_pattern": f"The top is {v}.", "bottom_kind": f"You are wearing {v}.", "posture": f"You are {v}.",
            "action": f"You are {v}."}[field]


def _fake_vlm(question, lang="en", frames=None):
    """vision.scene.ask_vlm on the r6 scenes: what the picture model would say of the person in front (the speaker A),
    from the scene's fields; the fields the question names, else all of them; None when nobody is in view."""
    ps = _persons()
    if not ps:
        return None
    p = ps[0].get("_scene") or {}
    fields = [f for f, rx in VLM_ASKED if re.search(rx, question or "", re.I)] or [f for f, _ in VLM_ASKED]
    said = [x for x in (_vlm_said(p, f, lang) for f in fields) if x]
    return " ".join(said) or None


scene.ask_vlm = _fake_vlm             # "am I wearing glasses?" asks the picture model: answered from the scene


def fresh_seeing():
    seeing._last.update(thing=None, name=None, kind=None, asked=None, parts=[], at=0.0)


STUCK = {"now": None}                  # the blocked drive "try again" means (commands_detour), never the live file
detour.recent = lambda: STUCK["now"]


def turn_route(b, say, lang, mk, state="idle", use_llm=True):
    """One turn the way lumi.answer() goes: command_check.rules (drive words, then lumi.route) with seeing.answer on
    the fake scene; what the rules leave through dialogue_check.run_turn with the cameras' facts (and the hand) in
    the prompt. (route in dialogue_check's notation, reply, by). A rule's fixed line is "" (not judged)."""
    if lang not in ("en", "ko"):                           # r9 "mix" turns: Lumi answers in Korean or English
        lang = "ko" if brain.HANGUL.search(say) else "en"
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
        elif r in ("weather", "search"):                   # lumi.look_up keeps the question (+ WEATHER_ASKED)
            b.last_lookup = say + brain.WEATHER_ASKED if r == "weather" else say
            b.history.append((b.last_lookup, ""))
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
    if got != "stop" and pointing.asked(text) == "there":
        got = "point"                                      # lumi.pointed_drive, right after a stop
    got = at_limit(got, c.get("at_limit"))
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


LIMIT_AT = {"head_left": (brain.HEAD_YAW[1], None, None), "head_right": (-brain.HEAD_YAW[1], None, None),
            "head_up": (None, brain.HEAD_PITCH[1], None), "head_down": (None, brain.HEAD_PITCH[0], None),
            "lift_top": (None, None, robot_head.LIFT_MAX_MM), "lift_bottom": (None, None, 0.0)}


def at_limit(got, where):
    """commands_more (r6) "at_limit": the head or the lift already at that end; lumi.look / lumi.lift then move
    nothing and say so (LIMIT_SAY): "limit"."""
    if not where or not re.match(r"action:(?:look|lift) ", got):
        return got
    yaw, pitch, mm = LIMIT_AT[where]
    a, target = got.removeprefix("action:").split(" ", 1)
    if a == "look":
        y0, p0 = 0.0 if yaw is None else yaw, robot_head.HEAD_REST_PITCH if pitch is None else pitch
        y1, p1, limited = brain.head_goal(target, y0, p0, lumi.LOOK)
        still = abs(y1 - y0) < 1 and abs(p1 - p0) < 1        # a number past the range, cut to where it is
        return "limit" if limited in ("left", "right", "up", "down") or limited and still else got
    limited = brain.lift_goal(target, 50.0 if mm is None else mm, robot_head.LIFT_MAX_MM)[1]
    return "limit" if limited in ("up", "down") else got


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


def same_steps(want, got):
    """The steps as written, or more exact where the notation has no word for it: a bare "place" read with the table
    said ("put it on the table"), a "receive ... wait" read as the receive (it waits for the hand-over anyway)."""
    if got == want:
        return True
    if not got or len(got) != len(want):
        return False
    for w, g in zip(want, got):
        w, g = dict(w), dict(g)
        if w.get("do") == "place" and w.get("on") is None:
            w.pop("on", None), g.pop("on", None)
        if w.get("do") == "receive":
            w.pop("wait_s", None), g.pop("wait_s", None)
        if w != g:
            return False
    return True


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
    elif not unread and same_steps([short(s.strip()) for s in want.split(" | ")], got):
        v = "right"
    elif unread and not use_llm and by == "rules" and len(steps._split(steps._norm(steps._cut_says(text)[0], mk))) >= 2:
        v = "llm?"                                         # the LLM pass would read it
    else:
        v = "wrong" if unread or refused else "motion"
    return row(text, v, by, f"{text!r}\n  want {want}\n  got  {got} unread {unread} [{by}]",
               got=json.loads(json.dumps(got)), unread=unread)


LOOKUP = {"lookup:weather": "weather", "lookup:news": "search", "lookup:web": "search"}   # lookup_dialogues (r9)
FORGOT = set(__import__("assistant.memory", fromlist=["FORGOT"]).FORGOT.values())


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
                if turn.get("closing"):
                    rows[-1]["closing"] = turn["closing"]
                b.history.append((turn["say"], ""))
                continue
            if r.startswith("action:give") or r.startswith("action:place"):
                state = "idle"                             # handed over / put down: the hand is empty now
            if r == "none" and reply in FORGOT:
                r = "forget"                               # memory_dialogues: the talks deleted and said so
            if not scored:
                rows.append(row(key, "-", by, "", route=r, reply=reply))
                continue
            want = dict(turn, expect_action=" | ".join(LOOKUP.get(a.strip(), a.strip()).removeprefix("action:")
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
        if turn.get("closing"):
            rows[-1]["closing"] = turn["closing"]          # closing_context: "end" / "continue", counted apart
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


def score_questions(c, old, use_llm):
    """questions_world (r6): the way lumi.answer() goes: abilities / battery (fixed_answer), lumi.route (weather, search,
    seeing, status ...), quick_answers, then the LLM. expect quick: answered without the LLM (the LLM's answer is wrong
    even when right: not at once); knowledge / unknown: must / must_not on whatever answered, a lookup is wrong;
    lookup:weather: the weather lookup; lookup:news / lookup:web: the web search."""
    from assistant import abilities, quick_answers
    text, mk = c["text"], DEFAULT_MARKERS
    lang = c["lang"] if c["lang"] in ("en", "ko") else "ko" if brain.HANGUL.search(text) else "en"
    brain.FORCED_LANG["lang"] = lang
    SCENE["now"] = None
    fresh_seeing()
    b, key = brain.Brain(), text
    got = abilities.answer(text, lang, "") or (("battery", battery.answer(text, lang)) if battery.asked(text) else None)
    if got:
        r, reply, by = "quick", got[1], "rules"
    elif old and old["by"] == "llm":
        r, reply, by = old["out"]["route"], old["out"]["reply"], "llm"
    else:
        r, reply, by = turn_route(b, text, lang, mk, "idle", use_llm=False)
        if r == "llm?":
            say = quick_answers.answer(text, lang, ())
            if say:
                r, reply, by = "quick", say, "rules"
            elif use_llm:
                r, reply, by = turn_route(b, text, lang, mk, "idle", use_llm=True)
    want = c["expect"]
    looked = r in ("weather", "search", "search(unsure)")
    if r == "llm?":
        v, probs = ("wrong", ["left to the LLM, not at once"]) if want == "quick" else ("llm?", [])
    elif want.startswith("lookup:"):
        ok = r == "weather" if want == "lookup:weather" else r in ("search", "search(unsure)")
        probs = [] if ok else [f"want {want}"]
        v = "right" if ok else "motion" if MOTION.match(r) else "wrong"
    else:
        probs = company_check.problems(c, lang, reply) if not looked else [f"looked up ({r})"]
        if want == "quick" and by == "llm":
            probs.append("by the LLM, not at once")
        v = "right" if not probs else "motion" if MOTION.match(r) else "wrong"
    return row(key, v, by, f"[{c['q']}, {want}] {text!r} -> [{r}] {reply[:140]!r} {probs}", route=r, reply=reply)


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
        "silence_noise": lambda c: f"{c['heard']}|{json.dumps(c['ctx'], sort_keys=True)}",
        "questions_world": lambda c: c["text"]}
SCORERS = {"commands_sing": score_sing, "commands_missions": score_missions, "seeing_dialogues": score_dialogue,
           "followup_dialogues": lambda d, old, use_llm: score_dialogue(d, old, use_llm, judge=True),
           "dialogues_mixed": score_dialogue, "unknowns": score_unknowns, "silence_noise": score_silence,
           "questions_world": score_questions,
           "memory_dialogues": lambda d, old, use_llm: importlib.import_module("tests.memory_check").score_memory(d, old, use_llm)}


def load(split, name):
    """split: "train" / "held", or "r2.train" for a round's folder."""
    mod = importlib.import_module(f"tests.blind.{split}.{name}")
    cases = getattr(mod, "CASES", None) or getattr(mod, "DIALOGUES")
    return list(cases.items()) if isinstance(cases, dict) else cases


def run_set(split, name, old_rows, use_llm, cached, limit, sample=None):
    cases = load(split, name)
    if sample and len(cases) > sample:                     # the same N cases every run (seeded by the set's name)
        import random
        cases = random.Random(name).sample(cases, sample)
    cases = cases[:limit]
    old_rows = old_rows if cached else []
    name = base(name)
    if name == "hearing":
        return score_hearing(cases, old_rows, use_llm)
    dialogue = "dialogues" in name or bool(cases) and isinstance(cases[0], dict) and "turns" in cases[0]
    fn = SCORERS.get(name, score_dialogue if dialogue else score_commands)   # closing_context: a dialogue set
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
            r["lang"] = lang_of(c, r)
            r["level"] = level_of(c, r)
            if r["verdict"] in ("wrong", "motion", "error") and "-v" in sys.argv:
                print(f"  {r['verdict'].upper():6} {r['show'][:200]}", flush=True)
    return rows


KINDS = ["right", "wrong", "motion", "llm?", "error"]


def lang_of(c, r):
    """en / ko / mix of a case (its "lang"), of a dialogue turn (dialogue_check.turn_lang), or by its letters."""
    if isinstance(c, dict) and "turns" in c:
        j = int(r["key"].split("|", 1)[0]) - 1 if r["key"][:1].isdigit() else -1
        return dialogue_check.turn_lang(c["turns"][j]) if 0 <= j < len(c["turns"]) else c.get("lang", "?")
    case = c if isinstance(c, dict) else c[1] if len(c) > 1 and isinstance(c[1], dict) else {}
    text = case.get("text") or case.get("heard") or (c[0] if isinstance(c, (list, tuple)) else "")
    if case.get("lang"):
        return case["lang"]
    ko, en = bool(brain.HANGUL.search(text or "")), bool(re.search(r"[A-Za-z]{3,}", text or ""))
    return "mix" if ko and en else "ko" if ko else "en"


LEVEL_NAME = {"banmal": "ko_banmal", "haeyo": "ko_haeyo", "hapsyo": "ko_hasipsio", "friendly": "ko_friendly",
              "honorific": "ko_honorific", "dialect": "ko_dialect"}      # W2's names (r6 _i files) -> r9's
LEVEL_GUESS = [("ko_dialect", r"(?:주이소|하이소|하입시더|하이소|데이|카이|라예|랑께|허자잉|줘유|해유|줍서|헙서|마씸|아이가|머꼬|와이라|"
                              r"하모|맞제|그라제|했노|하노|하나\?|가\?)[.?!~]*$|잉[.?!~]*$|(?:주소|해 ?도)[.?!]*$"),
               ("ko_hage", r"(?:하게|주게|하네|하세|보게|오게|가게나|하시게)[.?!~]*$|자네"),
               ("ko_honorific", r"(?:시[어겠었]|으시|하시|주시|가시|보시|께서|드리|드릴|드려|여쭤|여쭙|계세|계십|잡수|주무|말씀)"),
               ("ko_hasipsio", r"(?:습니다|습니까|[가-힣]니다|[가-힣]니까|십시오|시오|하십시다)[.?!~]*$"),
               ("ko_friendly", r"ㅋ|ㅎㅎ|~|임\?|ㄱㄱ|ㅇㅇ|ㄹㅇ|당[.?!]*$|용[.?!]*$|쥬[.?!]*$"),
               ("ko_haeyo", r"요[.?!~,]*(?:\s|$)")]


def level_of(c, r):
    """The speech level of a case or a scored turn: its "level" field (r9; W2's names in r6 _i files read as r9's),
    else guessed from the Korean endings (marked "*"); English "en*", mixed "mixed*"."""
    turn = {}
    if isinstance(c, dict) and "turns" in c and r["key"][:1].isdigit():
        j = int(r["key"].split("|", 1)[0]) - 1
        turn = c["turns"][j] if 0 <= j < len(c["turns"]) else {}
    case = c if isinstance(c, dict) else c[1] if isinstance(c, (list, tuple)) and len(c) > 1 and \
        isinstance(c[1], dict) else {}
    lv = turn.get("level") or (case.get("level") if not turn or "turns" not in case else None)
    if lv:
        return LEVEL_NAME.get(lv, lv)
    if r.get("lang") == "en":
        return "en*"
    if r.get("lang") == "mix":
        return "mixed*"
    text = turn.get("say") or case.get("text") or case.get("heard") or (c[0] if isinstance(c, (list, tuple)) else "")
    text = (text or "").strip()
    return next((name + "*" for name, rx in LEVEL_GUESS if re.search(rx, text)), "ko_banmal*")


def by_level(saved):
    """right / cases per speech level over every set (r9 / r6 _i: as labelled; "*": guessed from the endings), and the
    closing turns (closing_context) by kind."""
    lv, cl = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for name in ordered(saved):
        for r in saved[name]["rows"]:
            if r["verdict"] != "-":
                lv[r.get("level", "?")][r["verdict"]] += 1
                if r.get("closing"):
                    cl[r["closing"]][r["verdict"]] += 1
    lines = ["", "By speech level (right / cases, motions in brackets; * = guessed from the endings):", "",
             "| level | right | wrong | motion | llm? |", "|---|---|---|---|---|"]
    lines += [f"| {k} | {cell(lv[k])} | {lv[k]['wrong']} | {lv[k]['motion']} | {lv[k]['llm?']} |" for k in sorted(lv)]
    if cl:
        lines += ["", "Closing turns: " + ", ".join(f"{k} {cell(cl[k])}" for k in sorted(cl))]
    return lines


def cell(k):
    n = sum(k.values())
    return f"{k['right']}/{n} ({100 * k['right'] // max(1, n)} %)" + (f" [{k['motion']}]" if k["motion"] else "") if n else "-"


def by_lang(saved):
    """Lines of a table: right / cases per language, per set and in all."""
    lines = ["", "By language (right / cases, motions in brackets):", "", "| set | en | ko | mix |", "|---|---|---|---|"]
    tot = collections.defaultdict(collections.Counter)
    for name in ordered(saved):
        c = collections.defaultdict(collections.Counter)
        for r in saved[name]["rows"]:
            if r["verdict"] != "-":
                for x in (c[r.get("lang", "?")], tot[r.get("lang", "?")]):
                    x[r["verdict"]] += 1
        lines.append(f"| {name} | {cell(c['en'])} | {cell(c['ko'])} | {cell(c['mix'])} |")
    lines.append(f"| ALL | {cell(tot['en'])} | {cell(tot['ko'])} | {cell(tot['mix'])} |")
    return lines


def report(split, saved, secs):
    lines = [f"# Blind sets, {split} ({time.strftime('%Y-%m-%d %H:%M')}, model {brain.MODEL}, this run {secs:.0f} s)", "",
             "right / wrong / motion (a motion not asked for: the worst) / llm? (left to the LLM, --rules run) / error. "
             "Dialogue sets count scored turns. by LLM: answered by the LLM.", "",
             "| set | run | cases | right | % | wrong | motion | llm? | error | by LLM |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    tot = collections.Counter()
    for name in ordered(saved):
        rows = [r for r in saved[name]["rows"] if r["verdict"] != "-"]
        c = collections.Counter(r["verdict"] for r in rows)
        tot.update(c)
        n, llm_n = len(rows), sum(r["by"] == "llm" for r in rows)
        lines.append(f"| {name} | {saved[name]['when']} | {n} | {c['right']} | {100 * c['right'] // max(1, n)} | "
                     f"{c['wrong']} | {c['motion']} | {c['llm?']} | {c['error']} | {llm_n} |")
    n = sum(tot.values())
    lines.append(f"| ALL | | {n} | {tot['right']} | {100 * tot['right'] // max(1, n)} | {tot['wrong']} | "
                 f"{tot['motion']} | {tot['llm?']} | {tot['error']} | |")
    lines += by_lang(saved) + by_level(saved)
    for name in ordered(saved):
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
    print("\n".join(lines[:len(saved) + 7] + by_lang(saved) + by_level(saved)))


def main(args):
    if not args or args[0] not in ("train", "held") or {"-h", "--help"} & set(args):
        print(__doc__.split("\n\n")[1])
        return
    split = args[0]
    use_llm, cached = "--rules" not in args, "--cached" in args
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    sample = int(args[args.index("--sample") + 1]) if "--sample" in args else None
    rnd = args[args.index("--round") + 1] if "--round" in args else ""
    own = args[args.index("--tag") + 1] if "--tag" in args else None
    names = [a for a in args[1:] if not a.startswith("-") and not a.isdigit() and a not in (rnd, own)]
    folder, tag = (f"{rnd}.{split}", f"{rnd}_{split}") if rnd else (split, split)
    if "--tag" in args:                                    # own report files (logs/blind_<tag>.*): a --rules run
        tag += "_" + args[args.index("--tag") + 1]         # leaves the shared ones' LLM rows for --cached alone
    files = [f.stem for f in (ROOT / "tests" / "blind" / folder.replace(".", "/")).glob("*.py") if f.stem != "__init__"]
    todo = [n for n in ordered(files) if not names or any(n == a or n.startswith(a) or base(n) == a for a in names)]
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
        rows = run_set(folder, name, saved.get(name, {}).get("rows", []), use_llm, cached, limit, sample)
        saved[name] = {"when": time.strftime("%m-%d %H:%M") + (" rules" if not use_llm else "") +
                       (f" first {limit}" if limit else "") + (f" sample {sample}" if sample else ""), "rows": rows}
        c = collections.Counter(r["verdict"] for r in rows if r["verdict"] != "-")
        print(f"{name}: " + ", ".join(f"{k} {c[k]}" for k in KINDS if c[k]) + f" ({time.time() - t1:.0f} s)", flush=True)
        path.write_text(json.dumps(saved, ensure_ascii=False, indent=0))
    report(tag, saved, time.time() - t0)


if __name__ == "__main__":
    main(sys.argv[1:])
