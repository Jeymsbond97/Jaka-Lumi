"""Self-check of fetch's ways to a thing (tasks/fetch.py), no robot: python tests/test_fetch_ways.py

A fake room: a table (a rectangle on the map), a cup on it, the base that drives and turns on the map and stands still
when its front comes too near the table (its own safety stop, live 2026-10-26), navigation that "arrives" without
moving when its goal is inside the table's margin, a torso camera that sees the cup where it is from the base pose now
and the table top only from a near limit on. The live positions of 2026-10-26: (-117, 960), (-104, 694), (-141, 869),
(262, 774), (260, 722), (300, 621), (-99, 738); the place at 18:53 ("no table in view", the table seen further away,
the base never nearer) and at 18:55 (a table's box centre (22, 623), then (-349, 647))."""
import json
import math
import tempfile
from pathlib import Path

import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from manipulation import skills
from tasks import fetch
from vision import head_cam

tmp = Path(tempfile.mkdtemp())
fetch.STATE_FILE = tmp / "lumi_task.json"           # never the real /dev/shm file
fetch.CALIB_FILE = tmp / "fetch_calib.json"
fetch.KNOWN_FILE = tmp / "known_things.json"
fetch.DRIVE_POLL_S, fetch.DRIVE_START_S = 0.0, 0.05
fetch.ASK_EVERY_S, fetch.ASK_WAIT_S = 0.0, 0.0
fetch.LOG_LINES = 1000
fetch.AXIS_SPEED, fetch.COAST_S = 100.0, 0.0
CALIB = {"arm_yaw_in_base_deg": -95.5, "arm_xy_in_base_m": [0.111, -0.109], "waist_deg": -20.31}   # live values
WAIST0 = CALIB["waist_deg"]
REACH_MM = 800.0            # the fake arm reaches this far from the column (R1's map: nothing past ~850) ...
TRUSTED_REACH_MM = 740.0    # ... with a grasp turned at most skills.TRUSTED_YAW_DEG this far
STOP_GAP_M = 0.10           # the base stands still when its front would come this near the table
VIEW_Y = 650.0              # mm, arm frame: the torso camera sees a table top from here on (lift 0, table -328)
HELD_X, HELD_W, HELD_Y = -130.0, 110.0, 760.0   # the held cup hides the table here from the camera (x +- W, y < Y)
FLOOR_Z = -1060.0

skills.arm.cmd = lambda *a, **kw: (_ for _ in ()).throw(AssertionError(f"real arm command in a test: {a}"))
head_cam.head_centre = lambda: np.array([-92.97, -19.87, 356.12])      # measured (data on the Thor), fixed here
C = head_cam.head_centre()[:2]
col = lambda x, y: math.hypot(x - C[0], y - C[1])

# ---------- the room ----------
room = {"table": (0.355, 1.255, -0.6, 0.6), "chairs": [], "z": -328.0, "cups": [], "holding": None}
base = {"pose": (0.0, 0.0, 0.0), "polls": 0}
body = {"lift": 0.0, "waist": WAIST0, "yaw": 0.0, "pitch": fetch.head.HEAD_REST_PITCH}
log = []                                            # what the fake robot did


def to_box(x, y, box):
    x0, x1, y0, y1 = box
    if x0 <= x <= x1 and y0 <= y <= y1:
        return min(x - x0, x1 - x, y - y0, y1 - y)
    return math.hypot(max(x0 - x, 0.0, x - x1), max(y0 - y, 0.0, y - y1))


def to_table(x, y):
    """Distance (m) from a map point to the outline of the table or a chair (0 on it; inside: to the nearest edge, as
    the probe)."""
    return min(to_box(x, y, b) for b in [room["table"]] + room["chairs"])


def inside(x, y):
    x0, x1, y0, y1 = room["table"]
    return x0 <= x <= x1 and y0 <= y <= y1


def base_free(x, y):
    """The base may stand here: its outline (a circle of BASE_HALF_M) STOP_GAP_M from the table."""
    return not inside(x, y) and not any(to_box(x, y, b) == 0 or b[0] <= x <= b[1] and b[2] <= y <= b[3]
                                        for b in room["chairs"]) and to_table(x, y) >= fetch.BASE_HALF_M + STOP_GAP_M


def go_point(x, y, th):
    px, py, _ = base["pose"]
    if math.hypot(x - px, y - py) < 1e-6:                       # a turn on the spot
        log.append(("turn", round(math.degrees(th), 1)))
        base["pose"] = (px, py, th)
    elif base_free(x, y):
        log.append(("nav", round(x, 2), round(y, 2)))
        base["pose"] = (x, y, th)
    else:                                                       # inside the table's margin: "succeeded", not moved
        log.append(("nav still", round(x, 2), round(y, 2)))
    return True, "OK"


real_straight = fetch._straight


def straight(d, speed=None, stop=True):
    got = real_straight(d, speed, stop)
    x, y, th = base["pose"]
    went = 0.0
    while went + 0.01 <= got + 1e-9 and base_free(x + math.copysign(went + 0.01, d) * math.cos(th),
                                                   y + math.copysign(went + 0.01, d) * math.sin(th)):
        went += 0.01
    log.append(("straight", round(math.copysign(got, d), 2), round(math.copysign(went, d), 2)))
    base["pose"] = (x + math.copysign(went, d) * math.cos(th), y + math.copysign(went, d) * math.sin(th), th)
    return got


fetch._straight = straight
fetch.agv.pose = lambda: base["pose"]
fetch.agv.go_point = go_point
fetch.agv.status = lambda: {"move_status": "succeeded", "charge_state": False}
fetch.agv.cancel = lambda: None
fetch.agv.request = lambda cmd, **kw: {}
fetch.agv.clearance = lambda x, y: to_table(x, y)
fetch.agv.probe = lambda x, y: (float("inf"), float("inf"))
fetch.agv.markers = lambda: []
fetch.depth_hits = lambda deg, camera="torso", T=None: None
fetch.head.status = lambda: [body["lift"], body["waist"], body["yaw"], body["pitch"]]
fetch.head.moveto = lambda pos, **kw: body.update(lift=pos[0], waist=pos[1], yaw=pos[2], pitch=pos[3])
fetch.head_cam.base_from_head = lambda yaw, pitch: None            # the head camera: not used here
fetch.objects.latest = lambda camera="torso": {"age_s": None, "objects": [], "head_pose": None}
fetch.camview.want = lambda name: None
fetch.objects.base_from_camera = lambda: np.array([[1, 0, 0, -60.0], [0, 0, 0.9, 120.0], [0, -1, -0.44, 200.0],
                                                   [0, 0, 0, 1]])  # looks along arm +y, down
skills.FRESH_WAIT_S = 0.0
arm = {"j": [0.0] * 6}
fetch.motion.poses = lambda: {"ready": [0] * 6, "carry": [3] * 6, "look": [0] * 6, "give": [7] * 6}
fetch.motion.go = lambda name, *a, **k: arm.update(j=list(fetch.motion.poses()[name]))
fetch.motion.stop = lambda: None
fetch.arm_route.move = lambda seq, *a, **k: [fetch.motion.go(n) for n, _ in seq]
fetch.motion.tcp = lambda: [0.0] * 3 + list(skills.GRASP_RPY)
fetch.motion.move_linear = lambda target=None, **kw: None
skills._joints = lambda: arm["j"]
skills.home_joints = lambda: [0.0] * 6
skills._ask = lambda name, **a: {"errorCode": "0", "cartPosition": [0, 0, 0] + list(skills.GRASP_RPY)}
fetch.gripper.state = lambda: {"holding": room["holding"] is not None, "closed": room["holding"] is not None,
                               "ai": [3500 if room["holding"] else 160], "di": [0]}
fetch.gripper.open_ = lambda: (room.update(holding=None), fetch.gripper.state())[-1]
skills.hand_sees = lambda: "unknown"


# ---------- the fake cameras: the cup and the table seen from the base pose now ----------
def arm_xy_of(w):
    return [float(v) for v in fetch.arm_frame(w)]


def visible(x, y):
    """The torso camera sees the arm-frame point (x, y): ahead within its view, not behind the held cup."""
    hidden = room["holding"] is not None and abs(x - HELD_X) < HELD_W and y < HELD_Y
    return 300.0 <= y <= 2500.0 and abs(math.degrees(math.atan2(x, y))) <= 40.0 and not hidden


def low_view(x, y, z):
    """The torso camera looks level: at y 580 it sees down to z -375, further out lower (real extrinsics, lift 0)."""
    return z >= -375.0 - 0.7 * (y - 580.0)


fetch.in_view = low_view


def cups():
    out = []
    for c in room["cups"]:
        x, y = arm_xy_of(c["map"])
        if visible(x, y) and low_view(x, y, room["z"] + 145.0 / 2):
            out.append({"name": "cup", "colour": "white", "x": x, "y": y, "top_mm": room["z"] + 145.0,
                        "height_mm": 145.0, "width_mm": 80.0, "seen": 8, "spread": 1.0, "id": c["id"]})
    return out


def find(name="cup", colour=None, seen=None):
    got = sorted(cups(), key=lambda o: math.hypot(o["x"], o["y"]))
    if not got:
        raise skills.SkillError("I can't see a thing.")
    return got[0]


def flat(pts, guess_z=-400.0, camera="torso", T=None):
    out = []
    for x, y, *_ in pts:
        if not visible(x, y) or y < VIEW_Y:
            out.append(None)
            continue
        w = fetch.map_xy({"x": x, "y": y})
        out.append((x, y, room["z"] if inside(*w) else FLOOR_Z))
    return out


skills.find = find
skills.look = lambda frames=None, ignore=(), **kw: cups()
skills.flat_points = flat
skills.surface_heights = lambda pts, guess_z=-400.0: [None if q is None else q[2] for q in flat(pts)]
skills.surface_points = lambda pts, guess_z=-400.0, **kw: flat(pts)
skills.table_near = lambda obj: room["z"]
skills.locate = lambda xy, top, table, width, radius=None: ("unseen", None)


# ---------- the fake arm: reaches REACH_MM from the column; what it picked and where ----------
def reachable(obj, start=None, accept=None, max_yaw=None):
    """No-turn / small-turn grasps reach TRUSTED_REACH_MM from the column, every turn REACH_MM."""
    if col(obj["x"], obj["y"]) > (REACH_MM if max_yaw is None else TRUSTED_REACH_MM):
        skills.log(f"plan refused: no grasp turn reaches ({obj['x']:.0f}, {obj['y']:.0f})")
        return None
    turned["any"] = col(obj["x"], obj["y"]) > TRUSTED_REACH_MM
    return skills.plan_pick(obj), [0.0] * 6


turned = {"any": False}


def do_pick(obj, wp, ja):
    log.append(("pick", round(obj["x"]), round(obj["y"]), round(col(obj["x"], obj["y"])), turned["any"]))
    held = next(c for c in room["cups"] if c["id"] == obj["id"])
    true = arm_xy_of(held["map"])                         # a plan from where it is now, never from before a move
    assert math.hypot(true[0] - obj["x"], true[1] - obj["y"]) < 5.0, (true, obj)
    room["cups"].remove(held)
    room["holding"] = held
    skills._held.update(top_mm=obj["top_mm"], x=obj["x"], y=obj["y"], table=room["z"])


def chain(wp, j):
    """IK rows: a straight line to a place spot further than REACH_MM from the column fails."""
    out = []
    for n, p in wp:
        far = n.startswith("to (") and col(*map(float, n[4:].split(")")[0].split(", "))) > REACH_MM
        out.append([n, p, [0] * 6, "no IK solution" if far else None])
    return out


def do_place(wp):
    x, y = (float(v) for v in placed["at"])
    log.append(("place", round(x), round(y)))
    room["holding"] = None
    skills._held.clear()


placed = {"at": None}
real_place_at = fetch._place_at


def place_at(tries, top):
    for p in tries:
        if col(*p) <= REACH_MM:
            placed["at"] = p
            break
    return real_place_at(tries, top)


skills.reachable_pick = reachable
skills._do_pick = do_pick
skills._do_place = do_place
skills.ik_chain = chain
skills.place_options = lambda *a: iter(())
skills._line = lambda name, pose: None
fetch._place_at = place_at


def setup(cup_arm=None, table=(0.355, 1.255, -0.6, 0.6), pose=(0.0, 0.0, 0.0)):
    """A new scene: the base at `pose`, the table, a cup seen at `cup_arm` (mm, arm frame from that pose)."""
    fetch.CALIB_FILE.write_text(json.dumps(CALIB))
    fetch._state.update(status="idle", holding=False, step="", log=[])
    base["pose"], room["table"], room["cups"], room["holding"], room["chairs"] = pose, table, [], None, []
    body.update(lift=0.0, waist=WAIST0, yaw=0.0)
    log.clear()
    skills._held.clear()
    if cup_arm:
        room["cups"].append({"id": 1, "map": fetch.map_xy({"x": cup_arm[0], "y": cup_arm[1]})})


def run(fn, *a):
    fn(*a)
    fetch._thread.join(10)
    assert not fetch._thread.is_alive()
    return fetch.state()


TASK = {"object": "cup", "colour": None, "source": "here", "dest": "here", "finish": "hold"}


def repeats():
    """Base moves made twice from the same pose the same way (a move that did nothing tried again)."""
    seen, out = set(), []
    for line in fetch.state()["log"]:
        if "to bring it to" in line:
            key = line.split(" ", 1)[1]
            out += [key] if key in seen else []
            seen.add(key)
    return out


# ---------- (a) 17:57: the cup at (-117, 960); the base stops at the table with it at (-104, 694) ----------
# The table's near edge where the base's front stops with the cup ~0.71 m from the column: it is taken from there
# (the base can't bring it nearer), every way in tried once, nothing repeated, nobody asked.
setup((-117.0, 960.0), table=(0.6, 1.4, -0.6, 0.6))
st = run(fetch.start, TASK)
picks = [l for l in log if l[0] == "pick"]
assert st["status"] == "holding" and len(picks) == 1, (st["log"], log)
assert not any("asking" in l for l in st["log"]) and not repeats(), st["log"]
assert any("edge of my reach" in l for l in st["log"]), st["log"]
print("17:57 picked at", picks[0][1:], "column", picks[0][3])

# ---------- (b) 18:13: (-141, 869) across the table, the base already at it: round to another side ----------
setup((-141.0, 869.0), table=(0.355, 1.255, -0.6, 0.6))
st = run(fetch.start, TASK)
picks = [l for l in log if l[0] == "pick"]
assert st["status"] == "holding" and len(picks) == 1 and not fetch.at_edge(dict(zip("xy", picks[0][1:3]))), (st["log"], log)
assert any(l[0] == "nav" for l in log) and not repeats(), (st["log"], log)
assert not any(l[0] == "straight" and l[2] == 0 and l[1] != 0 for l in log[1:] if l in log[:log.index(l)]), log
print("18:13 picked at", picks[0][1:], "after", sum(l[0] == "nav" for l in log), "drive(s) round")

# ---------- (a) the far-edge and side cups in a free room: the base brings each to the comfortable zone first ------
for cup in ((262.0, 774.0), (260.0, 722.0), (300.0, 621.0), (-99.0, 738.0), (-104.0, 694.0)):
    setup(cup, table=(5.0, 6.0, 5.0, 6.0))                   # the table far away: the floor is free
    room["z"] = -328.0
    st = run(fetch.start, TASK)
    picks = [l for l in log if l[0] == "pick"]
    assert st["status"] == "holding" and len(picks) == 1, (cup, st["log"])
    assert not fetch.at_edge(dict(zip("xy", picks[0][1:3]))), (cup, picks, st["log"])
    print(cup, "picked at", picks[0][1:3], "column", picks[0][3])

# ... the same cups with the table in front blocking every way: taken from where it stands (reachable), not asked
for cup in ((-99.0, 738.0), (300.0, 621.0), (-104.0, 694.0)):
    setup(cup, table=(0.355, 1.6, -1.5, 1.5))
    st = run(fetch.start, TASK)
    picks = [l for l in log if l[0] == "pick"]
    assert st["status"] == "holding" and len(picks) == 1 and not repeats(), (cup, st["log"])
    assert picks[0][4] == (picks[0][3] > TRUSTED_REACH_MM), picks          # a large turn only when nothing else reaches
    print(cup, "blocked: picked from where it stands, column", picks[0][3], "any turn" if picks[0][4] else "")

# ---------- (c) kept: after a base move the cup it went for is taken, not another one nearer the camera ----------
setup((262.0, 774.0), table=(5.0, 6.0, 5.0, 6.0))
first = room["cups"][0]["map"]
room["cups"].append({"id": 2, "map": fetch.map_xy({"x": -250.0, "y": 450.0})})     # another cup, nearer after the move
skills.find = lambda name="cup", colour=None, seen=None: next(o for o in cups() if o["id"] == 1)   # the one chosen
real_see = fetch._see
fetch._see = lambda task, say=None: (setattr(skills, "find", find), real_see(task, say))[1]       # then any
obj = next(o for o in cups() if o["id"] == 1)
got = fetch._reach({"object": "cup", "colour": None}, obj, None)
fetch._see, skills.find = real_see, find
assert got[0]["id"] == 1 and any("where I kept it" in l for l in fetch.state()["log"]), fetch.state()["log"]

# ---------- (g) 18:53 place: holding at lift 0, the table in front hidden by the held cup near, seen further away,
# the base can't get nearer: put down on the part of it the arm reaches, no base move repeated ----------
setup(None, table=(0.355, 1.6, -1.0, 1.0))
room["holding"] = {"id": 9, "map": None}
fetch._set(holding=True, status="holding", held_object={"object": "cup", "colour": "white"})
skills._held.update(top_mm=-183.0, x=-73.0, y=588.0, table=-329.0, base=(9.0, 9.0, 0.0), what={"object": "cup"})
assert fetch.table_ahead() is None                       # live: "no table in view"
st = run(fetch.place)
done = [l for l in log if l[0] == "place"]
assert st["status"] == "done" and done and col(*done[0][1:]) <= REACH_MM, (st["log"], log)
assert not any(l[0] == "straight" for l in log), (st["log"], log)
print("18:53 put down at", done[0][1:])

# ---------- (h) 18:55: "the white table": its box centre at (22, 623), then (-349, 647) after a turn ----------
setup(None, table=(0.355, 1.6, -1.0, 1.0))
room["holding"] = {"id": 9, "map": None}
fetch._set(holding=True, status="holding", held_object={"object": "cup", "colour": "white"})
skills._held.update(top_mm=-183.0, x=-73.0, y=588.0, table=-329.0, base=(9.0, 9.0, 0.0), what={"object": "cup"})
box = {"at": (22.0, 623.0)}
real_turn, real_head_seen = fetch._turn, fetch._head_seen
fetch._head_seen = lambda match: {"x": box["at"][0], "y": box["at"][1], "head": True}   # seen by the head camera
fetch._turn = lambda deg, *a, **k: (box.update(at=(-349.0, 647.0)), real_turn(deg, *a, **k))[1]
st = run(fetch.place, None, {"name": "dining table", "colour": "white"})
fetch._turn, fetch._head_seen = real_turn, real_head_seen
done = [l for l in log if l[0] == "place"]
assert st["status"] == "done" and done and not any(l[0] == "turn" for l in log), (st["log"], log)
print("18:55 put down at", done[0][1:], "without turning")
# ---------- X1 round 2: a chair in front of the table: the side with room to stand is driven to first ----------
setup((-100.0, 1000.0), table=(0.8, 1.4, -0.3, 0.3))
room["chairs"] = [(0.35, 0.75, -0.3, 0.3)]
st = run(fetch.start, TASK)
picks = [l for l in log if l[0] == "pick"]
assert st["status"] == "holding" and picks and sum(l[0] == "nav" for l in log) == 1, (st["log"], log)
print("chair in front: picked at", picks[0][1:3], "after one drive round")

# ---------- X1: a cup on a low table drops out of the torso camera at the pick zone (lift 0): the goal moves out ----
room["z"] = -480.0
setup((-100.0, 1000.0), table=(5.0, 6.0, 5.0, 6.0))
room["z"] = -480.0
st = run(fetch.start, TASK)
picks = [l for l in log if l[0] == "pick"]
assert st["status"] == "holding" and picks and picks[0][2] > 600, (st["log"], log)
print("low table picked at", picks[0][1:3])
setup((-100.0, 1000.0), table=(5.0, 6.0, 5.0, 6.0))       # lower still: nowhere both seen and reached: said at once
room["z"] = -560.0
st = run(fetch.start, TASK)
assert st["status"] == "failed" and "too low" in st["log"][-1] and not any(l[0] == "straight" for l in log), st["log"]
room["z"] = -328.0

# ---------- X1: a cup too near to be seen (the table right at the base): back off and look before the search -------
setup((-100.0, 380.0), table=(0.37, 1.0, -0.6, 0.6))
room["cups"][0]["map"] = np.array([0.40, 0.10])          # on the table's near edge, under the cameras' view
assert not cups()
st = run(fetch.start, TASK)
assert any("backing off" in l for l in st["log"]) and st["status"] == "holding", st["log"]
assert not any("look around" in l.lower() for l in st["log"]), st["log"]
# ---------- X1 round 5: a cup beside Lumi on a table at its side, below both cameras: after the whole search, back
# off, turn to what is near and look ----------
for edge, cup in ((0.42, (0.15, 0.6)), (0.7, (0.15, 0.85))):
    setup(None, table=(-0.4, 0.5, edge, edge + 0.8))
    room["cups"].append({"id": 1, "map": np.array(cup)})
    assert not cups()
    st = run(fetch.start, TASK)
    assert st["status"] == "holding", st["log"]
    print("beside, table", edge, "m:", [l.split(" ", 1)[1] for l in st["log"] if "near me" in l or "front of me" in l])
real_around = fetch._look_around                         # the whole search sees nothing (waist turns refused)
fetch._look_around = lambda *a, **k: None
setup(None, table=(-0.4, 0.5, 0.7, 1.5))
room["cups"].append({"id": 1, "map": np.array([0.15, 0.85])})
st = run(fetch.start, TASK)
fetch._look_around = real_around
assert st["status"] == "holding" and any("near me at +90 deg" in l for l in st["log"]), st["log"]
print("fetch ways ok")
