"""Self-check of placing (2026-10-20 live test), no robot: the place sentences, the colour lists, and finding a
place on a round table lower than the proven one with a fake torso depth camera: python tests/test_fetch_place.py"""
import math
import tempfile
from pathlib import Path

from assistant import brain
from manipulation import skills
from tasks import fetch
from vision import objects

tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"           # never the real /dev/shm file
fetch.CALIB_FILE = tmp / "fetch_calib.json"
skills.arm.cmd = lambda *a, **kw: (_ for _ in ()).throw(AssertionError(f"real arm command in a test: {a}"))
fetch.head.moveto = lambda *a, **kw: (_ for _ in ()).throw(AssertionError("real lift move in a test"))

# ---------- the colours a command may name are the ones the cameras give ----------
assert set(brain.COLOURS.values()) == set(fetch.COLOURS), set(brain.COLOURS.values()) ^ set(fetch.COLOURS)
assert {n for _, n in objects.HUES} | {"white", "black", "grey"} == set(fetch.COLOURS)

# ---------- what to put it on: any class the cameras name, tables by any word ----------
ON = {"put on the grey table": ("dining table", "grey"), "put it on the gray table": ("dining table", "grey"),
      "put it on the white chair": ("chair", "white"), "put it on the white sink": ("sink", "white"),
      "put it on the table": ("dining table", None), "put it on the pink couch": ("couch", "pink"),
      "회색 테이블에 놔": ("dining table", "grey"), "보라색 의자에 놔": ("chair", "purple"), "흰 탁자에 놔": ("dining table", "white")}
for text, (name, colour) in ON.items():
    assert brain.place_on(text) == {"name": name, "colour": colour}, (text, brain.place_on(text))
    assert brain.held_command(text) == "place", text
assert brain.place_on("put it on the person") is None and brain.place_on("put it on the cup") is None
assert brain.held_command("bring it to p5 and put it on the white chair") == "place"

# ---------- /tasks/parse: the sentence names the held object and the thing; an empty hand is never offered placing --
from api import server
server.agv.markers = lambda: ["p1", "p8", "home"]
for holding in (True, False):
    fetch.check_hand = lambda: holding
    fetch._state.update(holding=holding, held_object={"object": "cup", "colour": "white"} if holding else None)
    for text, said in (("put it on the grey table", "Put the white cup on the grey table."),
                       ("put on the gray table", "Put the white cup on the grey table."),
                       ("put it on the white chair", "Put the white cup on the white chair."),
                       ("put it on the table", "Put the white cup on the table."),
                       ("put it down", "Put the white cup on the table near me.")):
        r = server.task_parse(server.ParseBody(text=text))
        if holding:
            assert r["action"] == "place" and r["sentence"] == said and not r["problems"], (text, r)
        elif brain.place_on(text):
            assert r["action"] is None and r["problems"] == ["My hand is empty, I'm not holding anything."], (text, r)
fetch._state.update(holding=False, held_object=None)

# ---------- the live case: a round table 1 cm lower than the proven one, the lift at its bottom ----------
# Torso camera (data/camera_extrinsics.json): a table at -414 mm is in view from y ~655 on; nearer is below the
# image. The approach brought the table's near edge to y 620. YOLO calls the table a white "sink" (flat).
TABLE_Z, EDGE_Y, VIEW_Y = -414.0, 620.0, 655.0
ROUND = {"c": (-160.0, 1020.0), "r": 400.0}           # the round table, arm frame mm


def depth(pts, guess_z=-400.0):
    out = []
    for x, y in pts:
        on = math.hypot(x - ROUND["c"][0], y - ROUND["c"][1]) <= ROUND["r"]
        out.append(None if y < VIEW_Y else TABLE_Z if on else -1000.0)      # the floor beyond the table
    return out


def flat(pts, guess_z=-400.0, camera="torso", T=None):
    return [None if z is None else (x, y, z) for (x, y), z in zip(pts, depth(pts))]


skills.surface_heights, skills.flat_points = depth, flat
skills.FRESH_WAIT_S = 0.0
fetch.head_cam.base_from_head = lambda yaw, pitch: None                     # the torso camera only (head: below)
fetch.head.status = lambda: [0.0, -20.0, 0.0, 0.0]          # lift 0 (its bottom), as in the log
lines = []
fetch.log = lambda *a: lines.append(" ".join(str(x) for x in a))

assert abs(fetch.table_ahead() - TABLE_Z) < 1.0
sink = {"name": "sink", "colour": "white", "x": -160.0, "y": 700.0, "top_mm": -405.0, "height_mm": 21.0}
held = {"top_mm": -263.0, "x": 61.0, "y": 677.0, "table": -409.0, "base": [1.38, 8.44, -3.13], "waist": -60.0}
spots = fetch.place_spots(held, (0.5, 7.4, 0.0), [sink], TABLE_Z)
assert spots and all(y >= 680 for _, y in spots), spots      # was []: the near ring below the view, the sink in the way
for x, y in spots:                                            # every spot on the table, its near side 25 mm too
    assert math.hypot(x - ROUND["c"][0], y - skills.TABLE_NEAR_RING_MM - ROUND["c"][1]) <= ROUND["r"], (x, y)
cup = {**sink, "name": "cup", "top_mm": -300.0, "x": -140.0, "y": 700.0}
assert all(math.hypot(x - cup["x"], y - cup["y"]) >= skills.FREE_MM for x, y in fetch.place_spots(held, (0.5, 7.4, 0.0),
                                                                                                  [cup], TABLE_Z))

# the same table further away (the base stopped 0.15 m short): the free spot is found off its curved edge
ROUND["c"] = (-160.0, 1170.0)
far = fetch.far_table()
assert far and abs(far["table"] - TABLE_Z) < 1.0 and far["camera"] == "torso", far
x, y = far["x"], far["y"]
assert all(math.hypot(x + dx - ROUND["c"][0], y + dy - ROUND["c"][1]) <= ROUND["r"]
           for dx, dy in ((0, 0), (50, 0), (-50, 0), (0, 50), (0, -50))), far

# the lift message says plainly whether it is right or at its end
lines.clear()
assert fetch._fit_lift(TABLE_Z) is False and lines[-1] == "table at -414 mm: the lift stays at 0 mm", lines
assert fetch._fit_lift(-457.0) is False and lines[-1] == "table at -457 mm: the lift stays at 0 mm (its end)", lines
# a table's top is measured with the sight lines aimed at its box top too: aimed 15 cm lower they ran past its edge
# to the floor (live 2026-10-20: top -330 mm, box top -320)
fetch.skills.flat_points = lambda pts, guess=-400.0, camera="torso", T=None: \
    [(x, y, -1004.0 if guess < -420 else -330.0) for x, y in pts]
assert abs(fetch._top_of({"x": -190.0, "y": 665.0, "top_mm": -320.0}) - (-330.0)) < 1.0
fetch.skills.flat_points = flat
print("fetch place ok")
