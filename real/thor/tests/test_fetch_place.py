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


FLAT_REAL = skills.flat_points


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

# ---------- the table's height from a real depth frame (2026-10-20, lift 63 mm, the round white table in front, white
# chairs, a person and a second table further back): every sight line's median read it 60-110 mm too low, the level
# top alone reads it right ----------
import json
import numpy as np
from vision import camview
REC = np.load(Path(__file__).parent / "data" / "depth_torso_2026-10-20.npz")
real_depth, real_intr, real_T = camview.depth, camview.intrinsics, objects.base_from_camera
camview.depth, camview.intrinsics = lambda name, max_age=None: REC["depth"], lambda name: json.loads(str(REC["intr"]))
objects.base_from_camera = lambda: REC["T"]
fetch.head.status = lambda: [63.0, -20.3, 0.0, 0.0]
TABLE_LIVE = -386.0                                                             # its level top, checked by eye
skills.flat_points = FLAT_REAL
assert abs(fetch.table_ahead() - TABLE_LIVE) < 10.0, fetch.table_ahead()
far = fetch.far_table()
assert far and abs(far["table"] - TABLE_LIVE) < 10.0, far
band = fetch.surface_band()
grid = [(r * math.cos(math.radians(90 + b)), r * math.sin(math.radians(90 + b))) for r in fetch.FAR_R_MM
        for b in range(-45, 46, 3)]
zs = [q[2] for q in skills.surface_points(grid, fetch.TABLE_PROVEN_Z) if q is not None and band[0] <= q[2] <= band[1]]
assert abs(np.median(zs) - TABLE_LIVE) > 60.0, np.median(zs)                    # the old way: chairs pull it down
camview.depth, camview.intrinsics, objects.base_from_camera = real_depth, real_intr, real_T
skills.flat_points = flat

# ---------- a table seen further away (the live case: its near edge ~1 m ahead, lift 0, chairs before it): go to it,
# the place grid then lies on its top ----------
fetch.head.status = lambda: [0.0, -20.3, 0.0, 0.0]
ROUND.update(c=(-160.0, 1350.0), r=400.0)
TABLE_Z = -390.0
chairs = lambda x, y: math.hypot(x + 450.0, y - 900.0) < 200.0                 # level nowhere: its back, the seat edge
skills.flat_points = lambda pts, guess_z=-400.0, camera="torso", T=None: \
    [None if chairs(x, y) or z is None else (x, y, z) for (x, y), z in zip(pts, depth(pts))]
assert fetch.table_ahead() is None                                              # nothing to put it on in reach
far = fetch.far_table()
assert far and abs(far["table"] - TABLE_Z) < 1.0, far
shift = np.subtract((far["x"], far["y"]), fetch.PLACE_GOAL)                      # what the base move brings closer
on_top = [(x + shift[0], y + shift[1]) for y in fetch.PLACE_GRID_Y for x in fetch.PLACE_GRID_X]
assert all(math.hypot(x - ROUND["c"][0], y - ROUND["c"][1]) <= ROUND["r"] for x, y in on_top), (far, shift)
assert shift[1] > 200.0, shift                                                  # forward, towards it: not away
skills.flat_points = flat

# ---------- named things: the cameras' labels flip, the colour and the level top decide ----------
fetch.CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": -95.5}))
fetch.agv.pose = lambda: (0.0, 0.0, 0.0)
fetch.KNOWN_FILE = tmp / "known_things.json"
white_chair = {"name": "chair", "colour": "white", "x": -160.0, "y": 760.0, "top_mm": -380.0}
on = brain.place_on("put the cup on the white dinning table or chair")
assert on == {"name": "dining table", "colour": "white", "alts": ["chair"]}, on
assert not fetch._matches(white_chair, {"name": "dining table", "colour": "white"})        # not exactly what was said ...
assert fetch._matches(white_chair, {"name": "dining table", "colour": "white"}, exact=False)  # ... but the same kind
assert fetch._matches({**white_chair, "names": ["chair", "dining table"]}, {"name": "dining table", "colour": "white"})
assert fetch._matches({**white_chair, "name": "sink"}, {"name": "sink", "colour": "grey"})  # white = grey (light)
assert not fetch._matches({**white_chair, "colour": "red"}, on)
assert not fetch._matches({**white_chair, "name": "cup"}, on)
ROUND.update(c=(-160.0, 900.0), r=400.0)
TABLE_Z = -400.0
got = fetch._support(on, [white_chair])                     # "or chair": it; its top is level and the arm can work at it
assert got["y"] == 760.0 and abs(got["top_mm"] - TABLE_Z) < 1.0, got
low = {**white_chair, "y": 700.0}
skills.flat_points = lambda pts, guess_z=-400.0, camera="torso", T=None: [(x, y, -720.0) for x, y in pts]
heights = []
assert fetch._support({"name": "chair", "colour": "white"}, [low], heights) is None and heights == [-720.0]
skills.flat_points = flat
# only the head camera sees it: that counts too, it shows where to go
fetch.head_cam.base_from_head = lambda yaw, pitch: np.eye(4)
fetch.objects.latest = lambda camera="torso": {"age_s": 0.1, "head_pose": None, "objects": [
    {"name": "dining table", "colour": "white", "position_mm": [400.0, 2600.0, -500.0]}] if camera == "head" else []}
got = fetch._support({"name": "dining table", "colour": "white"}, [])
assert got and got.get("head") and got["y"] == 2600.0, got
fetch.head_cam.base_from_head = lambda yaw, pitch: None

# ---------- two tables, a high white one and a low grey one: exactly what was said first ----------
white_t = {"name": "dining table", "colour": "white", "x": -160.0, "y": 760.0, "top_mm": -330.0, "width_mm": 600.0}
grey_t = {"name": "dining table", "colour": "grey", "x": 300.0, "y": 900.0, "top_mm": -430.0, "width_mm": 400.0}
LEVEL = ((white_t, -350.0), (grey_t, -450.0))
skills.flat_points = lambda pts, guess_z=-400.0, camera="torso", T=None: [
    next(((x, y, z) for t, z in LEVEL if math.hypot(x - t["x"], y - t["y"]) <= 150.0), None) for x, y in pts]
grey_t["colour"] = "black"                     # (white and grey count as one light colour; this one reads darker)
fetch.objects.latest = lambda camera="torso": {"age_s": None, "objects": [], "head_pose": None}
two = [white_t, grey_t]
pick = lambda text: fetch._support(brain.place_on(text), two)["x"]
assert pick("put it on the lower one") == grey_t["x"]
assert pick("put it on the black table") == grey_t["x"] and pick("put it on the white table") == white_t["x"]
assert pick("put it on the higher table") == white_t["x"] and pick("put it on the smaller table") == grey_t["x"]
assert pick("put it on the table") == white_t["x"]                            # nothing said: the nearest
assert pick("낮은 테이블에 놔") == grey_t["x"]
# the labels flip: the black table read "chair" in most frames, "dining table" in some -> still exactly it
flip = [white_t, {**grey_t, "name": "chair", "names": ["chair", "dining table"]}]
assert fetch._support(brain.place_on("put it on the black table"), flip)["x"] == grey_t["x"]
# ... "chair" in every frame: not exactly it; after the whole search it is the closest to what was said (its colour
# and kind) of everything seen, the white table only the same kind: there, and Lumi says so
only_chair = [white_t, {**grey_t, "name": "chair", "names": ["chair"]}]
assert fetch._support(brain.place_on("put it on the black table"), only_chair) is None
usable, went, said = [], [], []
fetch._usable(usable, only_chair)
real_go_to, real_near = fetch._go_to, fetch._place_near
fetch._go_to = lambda thing, goal, tried, holding=False: went.append((round(thing["x"]), round(thing["y"])))
fetch._place_near = lambda top0, tried: True
fetch._state.update(holding=True, held_object={"object": "cup", "colour": "grey"})
fetch._put_instead(-260.0, brain.place_on("put it on the black table"), "black table", usable, set(),
                   lambda en, ko: said.append(en))
assert went == [(300, 900)], went
assert said == ["I couldn't find the black table, so I put the grey cup on the black chair here."], said
went.clear(); said.clear()
fetch._put_instead(-260.0, brain.place_on("put it on the lower red sofa"), "red sofa", usable, set(),
                   lambda en, ko: said.append(en))
assert went == [(300, 900)] and "on the black chair here" in said[0], (went, said)   # same kind, the lower one
fetch._go_to, fetch._place_near = real_go_to, real_near
fetch._state.update(holding=False, held_object=None)
skills.flat_points = flat

# ---------- several cups: the said colour / size / place first; that colour nowhere: the closest, said ----------
cups = [{"name": "cup", "colour": c, "x": x, "y": y, "top_mm": -260.0, "width_mm": w, "seen": 8, "spread": 2.0}
        for c, x, y, w in (("white", -150.0, 600.0, 80.0), ("red", 100.0, 700.0, 70.0), ("white", -300.0, 900.0, 64.0))]
find = lambda **t: fetch._find({"object": "cup", "colour": None, **t}, cups)
assert find() == cups[0] and find(colour="red") == cups[1]                   # the nearest; the red one
assert find(prefer="small") == cups[2] and find(prefer="far") == cups[2] and find(colour="white", prefer="big") == cups[0]
skills.look = lambda frames=None, **kw: cups
close = []
assert fetch._find_any({"object": "cup", "colour": "blue"}, close) is None and len(close) == 3
real_around, real_look_at, real_fitted = fetch._look_around, fetch._look_at, fetch._fitted
fetch._look_around = lambda attempt, holding=False, say=None: attempt()      # the whole search: nothing blue
fetch._look_at = lambda view, attempt: attempt()
fetch._fitted = lambda task, obj: obj
fetch._go_to = lambda thing, goal, tried, holding=False: None
said.clear()
got = fetch._see({"object": "cup", "colour": "blue"}, lambda en, ko: said.append(en))
assert got["colour"] == "white" and said[-1] == "I couldn't see a blue cup, so I'm taking the white one.", (got, said)
fetch._look_around, fetch._look_at, fetch._fitted, fetch._go_to = real_around, real_look_at, real_fitted, real_go_to

# ---------- the dialog's sentence says what was understood ----------
fetch.check_hand = lambda: True
fetch._state.update(holding=True, held_object={"object": "cup", "colour": "grey"})
for text, said in (("put the cup on the white dinning table or chair", "Put the grey cup on the white dining table or chair."),
                   ("put it on the white tabel", "Put the grey cup on the white table."),
                   ("put it on the grey table", "Put the grey cup on the grey table."),
                   ("put it on the lower one", "Put the grey cup on the lower table.")):
    r = server.task_parse(server.ParseBody(text=text))
    assert r["action"] == "place" and r["sentence"] == said, (text, r)
fetch._state.update(holding=False, held_object=None)

# ---------- "take the smaller cup": typed, the sentence says it, the task carries it; fetch takes the smaller one ----
fetch.check_hand = lambda: False
for text, said, prefer in (("take the smaller cup to p1", "Take the smaller cup from here, bring it to p1 and hold it.",
                            "small"),
                           ("bring me the cup on the left", "Take the cup on the left from here, bring it here and "
                            "hold it.", "left"),
                           ("작은 컵 가져와", "Take the smaller cup from here, bring it here and hold it.", "small")):
    r = server.task_parse(server.ParseBody(text=text))
    assert r["action"] == "fetch" and r["sentence"] == said and r["task"]["prefer"] == prefer, (text, r)
    assert server.TaskBody(**r["task"]).model_dump()["prefer"] == prefer        # /tasks/fetch keeps it
# a correction inside the typed command is read as by voice (brain.self_correct)
r = server.task_parse(server.ParseBody(text="bring me the cup from p1, no, from p8"))
assert r["action"] == "fetch" and r["task"]["source"] == {"marker": "p8"}, r
assert server.task_parse(server.ParseBody(text="go to p1, never mind"))["problems"] == ["Taken back: nothing to do."]
# two places in a row is a mission by the rules (live 2026-10-22: it was read as a fetch of nothing by the LLM)
r = server.task_parse(server.ParseBody(text="let's go p1 point and go p8 point"))
assert r["action"] == "steps" and r["steps"] == [{"do": "go", "to": "p1"}, {"do": "go", "to": "p8"}], r
r = server.task_parse(server.ParseBody(text="go from p1 to p8 and dance"))
assert r["action"] != "fetch" and r.get("task") is None and r["read_by"] == "rules", r   # no object named: never a fetch
two = [{**cups[0], "x": -100.0, "y": 600.0, "width_mm": 80.0}, {**cups[0], "x": 120.0, "y": 650.0, "width_mm": 66.0}]
find = lambda **t: fetch._find({"object": "cup", "colour": None, **t}, two)
assert find() == two[0] and find(prefer="small") == two[1] and find(prefer="big") == two[0]
assert find(prefer="left") == two[0] and find(prefer="right") == two[1]           # arm +x is the robot's right

# ---------- the live case 2026-10-20 17:59: the table measured right (-385 mm, lift 63), every place spot failed IK
# with the held grasp turn (0 deg); the pick's table was not stored (the cup's bottom out of view) ----------
from vision import calib
READY = [-284.35, -75.43, -52.45, -136.99, 26.46, -278.46]
skills.motion.poses = lambda: {"ready": READY, "look": READY}
skills._joints = lambda: list(READY)
fetch.motion.tcp = lambda: skills.flange_for(-100.0, 450.0, -150.0)
TILT = {"flipped": 0.0}


def ik(name, **a):          # IK only with the wrist flipped (J5 < 0) and the grasp turned 45 deg or more
    if name == "kine_forward":
        tilt = TILT["flipped"] if a["jointPosition"][4] < 0 else 0.0
        return {"errorCode": "0", "cartPosition": [0.0, 0.0, 0.0] + skills.rpy_of(
            calib.rpy_matrix(tilt, 0.0, 0.0) @ calib.rpy_matrix(*skills.GRASP_RPY))}
    if a["jointPosition"][4] < 0 and abs(skills.yaw_of(a["cartPosition"])) >= 44:
        return {"errorCode": "0", "jointPosition": list(a["jointPosition"])}
    return {"errorCode": "1"}


skills._ask = ik
placed = []
real_turned, real_pose = skills.place_turned, fetch._pose
skills.place_turned = lambda way, ja: placed.append((way, ja))
fetch._pose = lambda name, speed=None: None
fetch.head.status = lambda: [63.0, -20.3, 0.0, 0.0]
skills._held.clear()
skills._held.update(top_mm=-259.5, x=-95.5, y=598.5, yaw=0.0, table=None, tips=False, base=None, lift=75.0)
assert abs(fetch._top_on(-259.5, -385.0) - (-247.5)) < 1e-6           # not measured: moved by the lift (75 -> 63)
skills._held["table"] = -395.0                                          # stored at the pick now (skills.table_near)
top = fetch._top_on(-259.5, -385.0)
assert abs(top - (-249.5)) < 1e-6
tries = [(-180.0, 660.0), (-180.0, 680.0), (-220.0, 640.0)]
lines.clear()
assert fetch._place_at(tries, top) is True, lines
assert any("straight move to (-180, 660) refused" in l for l in lines), lines       # the held turn: refused, as live
way, ja = placed[0]
R = calib.rpy_matrix(*way[1][1][3:])
assert ja[4] < 0 and abs(round(skills.yaw_of(way[1][1]))) == 45, (ja, way)        # another turn, the other wrist
assert np.allclose(np.array(way[1][1][:3]) + R @ skills.GRASP_OFFSET,
                   [-180.0, 660.0, top - skills.BELOW_RIM_MM + skills.PLACE_EXTRA_MM])   # the nearest spot, its height
assert np.allclose(R @ calib.rpy_matrix(*skills.GRASP_RPY).T @ [0, 0, 1], [0, 0, 1])     # the cup upright
TILT["flipped"] = 30.0                                                  # that way would tip the cup: no spot
placed.clear()
assert fetch._place_at(tries, top) is None and not placed
skills.place_turned, fetch._pose = real_turned, real_pose
skills._held.clear()
print("fetch place ok")
