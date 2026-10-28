"""The blind seeing dialogues (tests/blind/train/seeing_dialogues.py, scenes that change between turns) through
lumi.route with seeing.answer, on fake cameras that show each turn's scene; no robot, no LLM. A turn passes when it
goes the way it should (seeing / not seeing) and a seeing reply matches every `must` and no `must_not`. Turns the
conversation model answers are only checked for their route.

    python tests/test_seeing_dialogues.py            # score, the failures to logs/seeing_dialogues.log
    python tests/test_seeing_dialogues.py --min 0.9  # fails below this part of the turns right
    python tests/test_seeing_dialogues.py --set r2   # round 2's train set (r1 default); --set mixed: the scene turns
                                                     # of r2/train/dialogues_mixed.py (other turns: must not be seeing)
Only train sets: the held-out halves are scored by the lead, never from here.
"""
import importlib
import re
import sys
import time
from pathlib import Path

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from assistant import brain, lumi, seeing
from vision import scene

SETS = {"r1": "tests.blind.train.seeing_dialogues", "r2": "tests.blind.r2.train.seeing_dialogues",
        "mixed": "tests.blind.r2.train.dialogues_mixed"}

MARKS = ["home", "dock2", "p1", "p2", "p3", "p4", "p5"]
LOGS = Path(__file__).resolve().parents[1] / "logs"
BEARING = {"front": 0.0, "left": 30.0, "right": -30.0}
now = {"scene": {"people": [], "objects": []}}


def _where(side):
    return scene.where(BEARING.get(side, 0.0))


def snapshot(cameras=scene.CAMERAS, since=None):
    assert since is not None and since <= time.time()
    return [{"camera": "head", "scene": now["scene"]}]


def _scene(frames):
    return frames[0]["scene"]


def _front(frames):
    near = [p for p in _scene(frames)["people"] if (p.get("dist_m") or 0) <= scene.FRONT_M]
    return min(near, key=lambda p: scene.speaker_key(p.get("dist_m"), BEARING.get(p.get("side"), 0.0))) if near else None


def _thing(name, colour):
    """A held thing as the detector gives it, None for one it has no class for (a watch: COCO has none)."""
    name = seeing._name(name) or None
    return name and {"name": name, "colour": colour, "position_mm": None, "distance_m": None, "width_mm": None}


def person_in_front(frames=None):
    return _person(_front(frames))


def _person(p):
    if p is None:
        return None
    seen = p.get("hands_visible", True)
    hands = {s: ({"position_mm": None, "distance_m": 0.8, "object": _thing(*p[f"{s}_hand"]) if isinstance(p.get(f"{s}_hand"), (list, tuple))
                  else (_thing(p[f"{s}_hand"], None) if p.get(f"{s}_hand") else None)} if seen else None)
             for s in ("left", "right")}
    for s, h in hands.items():                     # the palm check: something without a class shows as a colour
        raw = p.get(f"{s}_hand")
        if h is not None:
            h["something"] = None if h["object"] else {"colour": (raw[1] if isinstance(raw, (list, tuple)) else None) or
                                                       "grey", "share": 0.5} if raw else {"colour": None, "share": 0.0}
    return {"distance_m": p.get("dist_m"), "bearing_deg": BEARING.get(p.get("side"), 0.0), "where": _where(p.get("side")),
            "position_mm": None, "camera": "head", "facing": True, "gesture": None,
            "raised": [p["raised"]] if p.get("raised") else [], "pointing": None, "hands": hands,
            "clothes": {"upper": p.get("top"), "lower": p.get("bottom"), "feet": p.get("feet")}}


def other_person(frames=None):
    me = _front(frames)
    rest = sorted((p for p in _scene(frames)["people"] if p is not me), key=lambda p: p.get("dist_m") or 99)
    if me is None or not rest:
        return None
    return _person(rest[0])


def object_in_hand(frames=None):
    p = person_in_front(frames)
    for s in ("right", "left"):
        h = p and p["hands"][s]
        if h and h["object"]:
            return {**h["object"], "hand": s}
    return None


def person_holds(obj=None, frames=None):
    p = person_in_front(frames)
    if p is None or not any(p["hands"].values()):
        return None
    return object_in_hand(frames) is not None


def things(frames=None):
    out = [{"name": seeing._name(o["name"]) or o["name"], "colour": o.get("colour"), "distance_m": o.get("dist_m"),
            "bearing_deg": BEARING.get(o.get("side"), 0.0), "where": _where(o.get("side")), "camera": "head",
            "position_mm": None, "score": 0.9, "box": (0, 0, 1, 1)} for o in _scene(frames)["objects"]]
    return sorted(out, key=lambda t: t["distance_m"] or 99)


scene.snapshot = snapshot
scene.person_in_front = person_in_front
scene.other_person = other_person
scene.object_in_hand = object_in_hand
scene.person_holds = person_holds
scene.things = things
scene.people = lambda frames=None: [{"distance_m": p.get("dist_m"), "bearing_deg": BEARING.get(p.get("side"), 0.0),
                                     "camera": "head"} for p in _scene(frames)["people"]]
scene.pointing_target = lambda frames=None: None
scene.ask_vlm = lambda q, lang="en", frames=None: None


def ask_vlm_hand(evidence, lang="en", frames=None, side=None):
    """The close look names a thing the detector has no class for (a watch), as gemma4 does on the hand picture."""
    p = _front(frames)
    for s in ((side,) if side else ("right", "left")):
        raw = p and p.get(f"{s}_hand")
        name = raw and (raw[0] if isinstance(raw, (list, tuple)) else raw)
        if name and not _thing(name, None):
            k = {"watch": "시계"}.get(name, name)
            return f"You're holding a {name} in your {s} hand." if lang == "en" else \
                f"{seeing.KO_SIDE[s]}손에 {seeing._j(k, '을', '를')} 들고 계세요."
    return None


scene.ask_vlm_hand = ask_vlm_hand


def lang_of(text):
    return "ko" if re.search(r"[가-힣]", text) else "en"


def run(dialogues):
    ok, bad, asked = 0, [], 0
    for n, d in enumerate(dialogues):
        seeing._last.update(thing=None, name=None, kind=None, asked=None, parts=[], held=None, unsure=0.0, at=0.0)
        b = brain.Brain()
        marks = d.get("markers") or MARKS
        for i, turn in enumerate(d["turns"]):
            now["scene"] = turn.get("scene") or {"people": [], "objects": []}
            text, lang = turn["say"], lang_of(turn["say"])
            brain.FORCED_LANG["lang"] = lang
            if "reply" in turn:                            # a setup turn of the mixed set: Lumi's line, not scored
                b.history.append((text, turn["reply"]))
                seeing.answer(text, lang)                  # what the router would do with it before the LLM
                continue
            kind, data = lumi.route(text, marks, b, seen=lambda x: seeing.answer(x, lang))
            got = data if kind == "seeing" else None
            if got:
                b.history.append((text, f"ACTION: none -\n{got}"))
            want = turn.get("route")
            asked += want == "seeing"
            if want == "seeing":
                good = bool(got) and all(re.search(m, got, re.I) for m in turn["must"]) and \
                    not any(re.search(m, got, re.I) for m in turn["must_not"])
            else:
                good = not got
            ok += good
            if not good:
                bad.append(f"[{n} {d['topic']} #{i}] {text!r} -> {kind}: {got!r}\n    want {want} {turn['must']} "
                           f"not {turn['must_not']}  ({turn['check']})")
    return ok, bad, asked


if __name__ == "__main__":
    name = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "r1"
    ok, bad, asked = run(importlib.import_module(SETS[name]).DIALOGUES)
    n = ok + len(bad)
    missed = sum("\n    want seeing " in b for b in bad)
    log = LOGS / f"seeing_dialogues{'' if name == 'r1' else '_' + name}.log"
    line = f"{ok}/{n} turns right (camera questions {asked - missed}/{asked}, other turns left alone {n - asked - len(bad) + missed}/{n - asked})"
    log.write_text(f"seeing dialogues ({name} train) {time.strftime('%Y-%m-%d %H:%M')}: {line}\n\n" + "\n".join(bad))
    print(f"seeing dialogues ({name}): {line} ({log})")
    if "--min" in sys.argv:
        assert ok >= float(sys.argv[sys.argv.index("--min") + 1]) * n
