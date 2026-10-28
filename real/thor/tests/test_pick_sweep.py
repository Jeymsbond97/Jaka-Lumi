"""Self-check of the pick / place sweep's hardest fixed scenes (tests/pick_sweep.py simulator, no robot):
python tests/test_pick_sweep.py

The live positions of 2026-10-26 (WORK_PLAN "Big night test 5", faults (a), (b), (e), (f)) and the hardest sweep
scenes, run through the real fetch._pick_here: each must end holding the cup with the fingers on it, or refuse for
a physical reason (no stand reaches it), never crash, never repeat a base move that went nowhere. Scenes still open
(OPEN) are run and printed, not asserted: they are the next work."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests import pick_sweep as ps

ps.install()
at = ps.pick_at
MUST = {                                                     # name: (scene, camera error)
    "picked live 15:39": (at(-96, 598, -260), 0.0),
    "17:57 carry line refused": (at(-104, 694, -186), 0.0),
    "18:13 across the table": (at(-141, 869, -186), 0.0),
    "18:13, base stops 0.25 m early": (at(-141, 869, -186, stall_gap=0.25), 0.0),
    "18:30 far edge, turned -45": (at(262, 774, -189), 0.0),
    "18:40 turned -30": (at(260, 722, -186), 0.0),
    "18:40 turned -30, nearer": (at(300, 621, -191), 0.0),
    "18:45 straight ahead": (at(-99, 738, -181), 0.0),
    "far edge on a low table (-450)": (at(262, 774, -330, height=120), 0.0),
    "sweep 54: low table -432": (ps.make_pick(54, 1), 1.0),
    "sweep 189: low table -440": (ps.make_pick(189, 1), 1.0),
}
PHYSICAL = {"18:13 behind a chair": (at(-141, 869, -186, stall_gap=0.25, chair=0.3), 0.0),
            "sweep 534: behind a chair, low table": (ps.make_pick(534, 1), 1.0)}   # was picked turned -30 once
OPEN = {}

bad = []
for group, scenes in (("must", MUST), ("physical", PHYSICAL), ("open", OPEN)):
    for name, (sc, cam) in scenes.items():
        for t in sc["tables"] + sc["boxes"]:
            t["half"] = [float(v) for v in t["half"]]
        r = ps.run_scene(sc, cam)
        t, j5 = ps.parse_grasp(r.get("grasp"))
        print(f"{group:8s} {name:36s} {r['result']:8s} turn {t} J5 {j5} waist {r['waist_end']:+.0f} landing "
              f"{(r.get('landings') or [None])[-1]} moves {[m[:3] for m in r['moves']]} {r.get('why') or ''}")
        if group == "open":
            continue
        if r["result"] in ("exception", "timeout") or r["repeats"]:
            bad.append((name, r["result"], r.get("why"), r["repeats"]))
        elif group == "must" and (r["result"] != "ok" or not r["landings"][-1][2]):
            bad.append((name, r["result"], r.get("why"), r.get("landings")))
        elif group == "physical" and (r["result"] == "ok" or ps.way_exists(sc) is not None):
            bad.append((name, "no longer physical", r["result"]))
assert not bad, bad

# ---------- places, the live run of 2026-10-27 (named white table, a higher grey one, a chair seat at -549) ----------
P = lambda deg, m: [m * ps.math.cos(ps.math.radians(deg)), m * ps.math.sin(ps.math.radians(deg))]
WHITE = {"name": "dining table", "colour": "white"}
SEAT = {"c": P(-55, 1.3), "half": [0.22, 0.22], "ang": 10.0, "z": -549.0}
PLACES = {   # name: (scene, must end on table 0)
    "10:55 the white table by name, far right": (ps.place_at(
        [{"c": P(-70, 1.9), "r": 0.5, "z": -330.0},
         {"c": P(-120, 1.6), "half": [0.3, 0.4], "ang": -120.0, "z": -267.0, "colour": "black"}], [SEAT], WHITE), True),
    "10:55 the same, the base stops 0.1 m early": (ps.place_at(
        [{"c": P(-70, 1.9), "r": 0.5, "z": -330.0},
         {"c": P(-120, 1.6), "half": [0.3, 0.4], "ang": -120.0, "z": -267.0, "colour": "black"}], [SEAT], WHITE,
        stall_gap=0.1), True),
    "10:59 a chair seat, no table": (ps.place_at([], [{**SEAT, "c": P(-20, 1.1)}]), False),
    "10:59 a chair seat ahead": (ps.place_at([], [{**SEAT, "c": P(0, 1.1)}]), False),
    "11:13 the round table ahead, flush": (ps.place_at([{"c": P(0, 0.95), "r": 0.5, "z": -330.0}]), True),
}
for name, (sc, must) in PLACES.items():
    r = ps.run_scene(sc, 1.0)
    navs = sum(m[0] == "nav" for m in r["moves"])
    drives = sum(m[0] == "nav" or m[0] == "straight" and m[1] > 0 for m in r["moves"])   # towards something
    print(f"place    {name:44s} {r['result']:8s} moves {[m[:3] for m in r['moves']]} {r.get('why') or ''}")
    if must and r["result"] != "ok" or not must and (r.get("released") or drives) or navs > ps.fetch.PLACE_NAV_MAX \
            or r["result"] in ("exception", "timeout"):
        bad.append((name, r["result"], r.get("why"), r["moves"]))
assert not bad, bad
print("pick sweep scenes ok")
