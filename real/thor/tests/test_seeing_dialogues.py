"""The blind seeing dialogues (tests/blind/train/seeing_dialogues.py, scenes that change between turns) through
lumi.route with seeing.answer, on fake cameras that show each turn's scene; no robot, no LLM. A turn passes when it
goes the way it should (seeing / not seeing) and a seeing reply matches every `must` and no `must_not`. Turns the
conversation model answers are only checked for their route.

    python tests/test_seeing_dialogues.py            # score, the failures to logs/seeing_dialogues.log
    python tests/test_seeing_dialogues.py --min 0.9  # fails below this part of the turns right
"""
import re
import sys
import time
from pathlib import Path

from assistant import brain, lumi, seeing
from tests.blind.train.seeing_dialogues import DIALOGUES
from vision import scene

MARKS = ["home", "dock2", "p1", "p2", "p3", "p4", "p5"]
LOG = Path(__file__).resolve().parents[1] / "logs" / "seeing_dialogues.log"
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
    return min(near, key=lambda p: p.get("dist_m") or 99) if near else None


def _thing(name, colour):
    """A held thing as the detector gives it, None for one it has no class for (a watch: COCO has none)."""
    name = seeing._name(name) or None
    return name and {"name": name, "colour": colour, "position_mm": None, "distance_m": None, "width_mm": None}


def person_in_front(frames=None):
    p = _front(frames)
    if p is None:
        return None
    seen = p.get("hands_visible", True)
    hands = {s: ({"position_mm": None, "object": _thing(*p[f"{s}_hand"]) if isinstance(p.get(f"{s}_hand"), (list, tuple))
                  else (_thing(p[f"{s}_hand"], None) if p.get(f"{s}_hand") else None)} if seen else None)
             for s in ("left", "right")}
    return {"distance_m": p.get("dist_m"), "bearing_deg": BEARING.get(p.get("side"), 0.0), "where": _where(p.get("side")),
            "position_mm": None, "camera": "head", "facing": True, "gesture": None,
            "raised": [p["raised"]] if p.get("raised") else [], "pointing": None, "hands": hands,
            "clothes": {"upper": p.get("top"), "lower": p.get("bottom"), "feet": p.get("feet")}}


def other_person(frames=None):
    me = _front(frames)
    rest = sorted((p for p in _scene(frames)["people"] if p is not me), key=lambda p: p.get("dist_m") or 99)
    if me is None or not rest:
        return None
    return person_in_front([{"scene": {"people": [rest[0]], "objects": []}}])


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
    out = [{"name": o["name"], "colour": o.get("colour"), "distance_m": o.get("dist_m"),
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


def lang_of(text):
    return "ko" if re.search(r"[가-힣]", text) else "en"


def run():
    ok, bad = 0, []
    for n, d in enumerate(DIALOGUES):
        seeing._last.update(thing=None, name=None, kind=None, asked=None, parts=[], at=0.0)
        b = brain.Brain()
        for i, turn in enumerate(d["turns"]):
            now["scene"] = turn["scene"]
            text, lang = turn["say"], lang_of(turn["say"])
            brain.FORCED_LANG["lang"] = lang
            kind, data = lumi.route(text, MARKS, b, seen=lambda x: seeing.answer(x, lang))
            got = data if kind == "seeing" else None
            if got:
                b.history.append((text, f"ACTION: none -\n{got}"))
            want = turn["route"]
            if want == "seeing":
                good = bool(got) and all(re.search(m, got, re.I) for m in turn["must"]) and \
                    not any(re.search(m, got, re.I) for m in turn["must_not"])
            else:
                good = not got
            ok += good
            if not good:
                bad.append(f"[{n} {d['topic']} #{i}] {text!r} -> {kind}: {got!r}\n    want {want} {turn['must']} "
                           f"not {turn['must_not']}  ({turn['check']})")
    return ok, bad


if __name__ == "__main__":
    ok, bad = run()
    n = ok + len(bad)
    LOG.write_text(f"seeing dialogues (train) {time.strftime('%Y-%m-%d %H:%M')}: {ok}/{n} turns right\n\n" + "\n".join(bad))
    print(f"seeing dialogues: {ok}/{n} turns right ({LOG})")
    if "--min" in sys.argv:
        assert ok >= float(sys.argv[sys.argv.index("--min") + 1]) * n
