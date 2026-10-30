"""Self-check of the skills.py geometry, no robot: python tests/test_skills.py"""
import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from vision import calib, head_cam
from manipulation import skills

head_cam.head_centre = lambda: np.array([-92.97, -19.87, 356.12])   # the head's turning centre (head_cam fit 2026-10-19;
                                                                     # its file stays on the Thor)

cup = {"name": "cup", "colour": "white", "x": -126.5, "y": 613.0, "top_mm": -261.0, "width_mm": 72.0}
R = calib.rpy_matrix(*skills.GRASP_RPY)
g = np.array([cup["x"], cup["y"], cup["top_mm"] - 40])

(n1, above), (n2, grasp), (n3, lift) = skills.plan_pick(cup)
assert np.allclose(grasp[:3], g - R @ skills.GRASP_OFFSET) and grasp[3:] == list(skills.GRASP_RPY)
assert np.allclose(np.array(grasp[:3]) + R @ skills.GRASP_OFFSET, g)       # the fingers' point is on the cup axis
assert np.allclose(np.subtract(above[:3], grasp[:3]), [0, 0, 100])
assert np.allclose(np.subtract(lift[:3], grasp[:3]), [0, 0, 30])

steps = dict(skills.plan_place(-200, 600, cup["top_mm"], start=lift))
assert np.isclose(steps["place"][2], grasp[2] + 3)                         # same table, 3 mm higher
assert np.isclose(steps["carry"][2], above[2]) and steps["carry"][:2] == lift[:2]
assert np.allclose(np.array(steps["place"][:3]) + R @ skills.GRASP_OFFSET, [-200, 600, g[2] + 3])

for yaw in (-30, 45):                                                      # a turned grasp: same point, cup upright
    t = skills.plan_pick(cup, yaw)[1][1]
    Rt = calib.rpy_matrix(*t[3:])
    assert np.allclose(np.array(t[:3]) + Rt @ skills.GRASP_OFFSET, g)
    assert np.allclose(Rt @ R.T @ [0, 0, 1], [0, 0, 1]) and np.isclose(skills.yaw_of(t), yaw)
    p = dict(skills.plan_place(-200, 600, cup["top_mm"], yaw=yaw))["place"]
    assert np.allclose(np.array(p[:3]) + calib.rpy_matrix(*p[3:]) @ skills.GRASP_OFFSET, [-200, 600, g[2] + 3])

for bad in (95, 30, 50):                      # seen widths: +SEEN_UNDER_MM over 97, under 61
    try:
        skills.plan_pick({**cup, "width_mm": bad})
        raise AssertionError(f"width {bad} accepted")
    except skills.SkillError:
        pass

# ---------- the object table: what the cup fingers take, and why not ----------
for name in ("cup", "apple", "orange", "sports ball"):
    assert skills.refusal(name) is None, name
for name, word in (("wine glass", "break"), ("banana", "thin"), ("cell phone", "thin"),
                   ("book", "flat"), ("bowl", "shallow"), ("sandwich", "soft"), ("laptop", "big")):
    en, ko = skills.refusal(name)
    assert word in en and name in en and ko, (name, en, ko)
assert skills.refusal("vase")[1] == "꽃병은 깨질 수 있어서 잡지 않을게요."                       # 은 after a final consonant
assert skills.refusal("banana")[1].startswith("바나나는 ")
assert "giraffe" in skills.refusal("giraffe")[0]                                       # not in the table at all
assert all(n in skills.objects.COCO for n in skills.GRASPS), [n for n in skills.GRASPS if n not in skills.objects.COCO]
try:                                                                                   # refused before any geometry
    skills.plan_pick({**cup, "name": "wine glass"})
    raise AssertionError("a wine glass planned")
except skills.SkillError as e:
    assert e.args == skills.refusal("wine glass")
# a cup: the proven grasp, 40 mm below its top, whatever its height
assert skills.grasp_height(cup) == cup["top_mm"] - skills.BELOW_RIM_MM
assert skills.grasp_height({**cup, "height_mm": 80.0}) == cup["top_mm"] - skills.BELOW_RIM_MM
# a round thing: at its equator when the tips clear the table there, else raised until they do
ball = {"name": "orange", "colour": "orange", "x": -126.5, "y": 613.0, "top_mm": -250.0, "width_mm": 150.0 - 8,
        "height_mm": 150.0}                                                 # (too wide for the hand, geometry only)
assert skills.grasp_height(ball) == -325.0                                 # equator 75 mm up, tips 65 mm up
apple = {**ball, "name": "apple", "width_mm": 72.0, "height_mm": 80.0}
z = skills.grasp_height(apple)
bottom = apple["top_mm"] - 80.0
assert z - skills.TIP_MM >= bottom + skills.TIP_CLEAR_MM - 1e-9 and z > bottom + 40.0, z     # raised over the equator
assert np.isclose(skills.grasp_height({**apple, "height_mm": None}), skills.grasp_height({**apple, "height_mm": 80.0}))
try:                                                                        # too low: the tips would hit the table
    skills.grasp_height({**apple, "height_mm": 60.0})
    raise AssertionError("a 60 mm high apple planned")
except skills.SkillError as e:
    assert "too low" in e.args[0]
(_, a_above), (_, a_grasp), _ = skills.plan_pick(apple)
assert np.allclose(np.array(a_grasp[:3]) + R @ skills.GRASP_OFFSET, [apple["x"], apple["y"], z])
# put down where it was held: the grasp point as far under its top as at the pick (below), not the cup's 40 mm
p = dict(skills.plan_place(-200, 600, apple["top_mm"], below=apple["top_mm"] - z))["place"]
assert np.allclose(np.array(p[:3]) + R @ skills.GRASP_OFFSET, [-200, 600, z + 3])
skills._held.update(below=apple["top_mm"] - z)
assert np.allclose(dict(skills.plan_place(-200, 600, apple["top_mm"]))["place"], p)
skills._held.clear()
assert np.allclose(dict(skills.plan_place(-200, 600, cup["top_mm"]))["place"][:3], np.array(grasp[:3]) + [-200 - cup["x"], 600 - cup["y"], 3])


free = skills.spots((cup["x"], cup["y"]), [])
assert free and all(np.hypot(x - cup["x"], y - cup["y"]) >= 60 for x, y in free)
near = {"x": free[0][0], "y": free[0][1]}                                  # something standing on the first spot
assert free[0] not in skills.spots((cup["x"], cup["y"]), [near])

moved = []                                                                 # after cancel() no move may start
skills.motion.stop = lambda: None
skills.motion.move_linear = lambda **kw: moved.append(kw)
skills.cancel()
try:
    skills._line("grasp", grasp)
    raise AssertionError("moved after cancel")
except skills.SkillError:
    assert not moved
try:
    skills.put_down()
    raise AssertionError("put down without holding anything")
except skills.SkillError:
    pass
sag = lambda name, **a: {"errorCode": "0",                                # z dips 250 mm in the middle of J1 0 -> 10
                         "cartPosition": [0, 0, -10 * a["jointPosition"][0] * (10 - a["jointPosition"][0])] + list(skills.GRASP_RPY)}
skills._ask = sag
assert not skills.joint_move_ok([0] * 6, [10, 0, 0, 0, 0, 0])
assert skills.joint_move_ok([5, 0, 0, 0, 0, 0], [10, 0, 0, 0, 0, 0])              # rising from the low point is fine
assert skills.joint_move_ok([0] * 6, [0] * 6)

# grasp options: only the flipped wrist reaches (seed J5 < 0), and only at turns of 45 deg or more; `accept` can refuse
READY = [-284.35, -75.43, -52.45, -136.99, 26.46, -278.46]
skills.motion.poses = lambda: {"ready": READY}
def ik(name, **a):
    if name == "kine_forward":
        return {"errorCode": "0", "cartPosition": [0, 0, 0] + list(skills.GRASP_RPY)}
    flipped, turn = a["jointPosition"][4] < 0, abs(skills.yaw_of(a["cartPosition"]))
    if flipped and turn >= 44:
        return {"errorCode": "0", "jointPosition": list(a["jointPosition"])}
    return {"errorCode": "1"}
skills._ask = ik
start = READY
plan = skills.reachable_pick(cup, start)
assert plan and plan[1][4] < 0 and abs(round(skills.yaw_of(plan[0][1][1]))) == 45, plan       # nearest turn first
plan = skills.reachable_pick(cup, start, accept=lambda wp, ja: abs(skills.yaw_of(wp[1][1])) > 100)
assert plan and abs(round(skills.yaw_of(plan[0][1][1]))) == 105, plan
assert skills.reachable_pick(cup, start, accept=lambda wp, ja: False) is None
# trusted turns are the ones picked live, -15..0: +15 missed 2 of 2 (a finger on the cup); the voice pick keeps to them
def ik_at(turns):
    def ask(name, **a):
        if name == "kine_forward":
            return {"errorCode": "0", "cartPosition": [0, 0, 0] + list(skills.GRASP_RPY)}
        ok = round(skills.yaw_of(a["cartPosition"])) in turns
        return {"errorCode": "0", "jointPosition": list(a["jointPosition"])} if ok else {"errorCode": "1"}
    return ask
skills._ask = ik_at({15, -15})
plan = skills.reachable_pick(cup, start, max_yaw=skills.TRUSTED_YAW_DEG)
assert plan and round(skills.yaw_of(plan[0][1][1])) == -15, plan
skills._ask = ik_at({15, 30})
assert skills.reachable_pick(cup, start, max_yaw=skills.TRUSTED_YAW_DEG) is None
real_find, real_guarded, real_home = skills.find, skills._guarded, skills.home_joints
skills.home_joints = lambda: start
skills.find = lambda name, colour=None, seen=None: dict(cup, colour="grey", width_mm=72)
skills._guarded = lambda *a: (_ for _ in ()).throw(AssertionError("picked at an untrusted turn"))
try:
    skills.pick("cup")
    raise AssertionError("picked")
except skills.SkillError as e:
    assert e.args[0] == "I can't reach it safely.", e
skills.find, skills._guarded, skills.home_joints = real_find, real_guarded, real_home
# hand_sees: depth right at the cup's axis = object, far behind it = empty, nothing seen = unknown
skills.objects.base_from_camera = lambda: np.eye(4)                      # camera at the arm base origin
skills._ask = lambda name, **a: {"errorCode": "0", "cartPosition": [0.0, 500.0, 0.0] + list(skills.GRASP_RPY)}
skills._joints = lambda: [0.0] * 6
for depth_extra, want in ((0.0, "object"), (2000.0, "empty")):
    skills.surface_points = lambda pts, guess_z=-400.0, e=depth_extra: [tuple(np.array(p) * (1 + e / np.linalg.norm(p)))
                                                                        for p in pts]
    assert skills.hand_sees() == want, want
skills.surface_points = lambda pts, guess_z=-400.0: [None] * len(pts)
assert skills.hand_sees() == "unknown"
assert len(skills.GRASP_YAWS) == 24 and set(skills.GRASP_YAWS) == set(range(-165, 181, 15))
print("skills ok")

# ---------- FINGER_DIR is straight down in the grasp (the hand's lowest part: TIP_MM along it, below the grasp point)
assert abs(np.linalg.norm(skills.FINGER_DIR) - 1.0) < 1e-9 and \
    (calib.rpy_matrix(*skills.GRASP_RPY) @ skills.FINGER_DIR)[2] < -0.99
# the tips grasp is off (MIN_WIDTH 72, 2026-10-22): a 66 mm cup is refused; the checks below turn it back on
try:
    skills.plan_pick({**cup, "width_mm": 58.0})
    raise AssertionError("66 mm cup planned with the tips grasp off")
except skills.SkillError as e:
    assert "too small" in e.args[0]
skills.MIN_WIDTH = 61.0
# a cup thinner than the belly closes to is held between the tips: its axis at the tips (TIPS_OFFSET from the
# belly's centre, level, almost along the flange z axis), at every grasp turn
thin = {**cup, "width_mm": 58.0}                                            # 66 mm at the fingers
for yaw in (0, -45, 90):
    g_belly, g_tips = skills.plan_pick(cup, yaw)[1][1], skills.plan_pick(thin, yaw)[1][1]
    Ry = calib.rpy_matrix(*g_tips[3:])
    assert np.allclose(np.array(g_tips[:3]) + Ry @ (skills.GRASP_OFFSET + skills.TIPS_OFFSET), g, atol=1e-6)
    shift = np.subtract(g_belly[:3], g_tips[:3])
    assert 25 < np.hypot(*shift[:2]) < 32 and abs(shift[2]) < 3, (yaw, shift)            # 28 mm, level
skills._held.update(tips=True)
d = skills.plan_place(-200, 600, thin["top_mm"])[1][1]                         # put down held the same way
assert np.allclose(np.array(d[:3]) + R @ (skills.GRASP_OFFSET + skills.TIPS_OFFSET), [-200, 600, g[2] + 3])
skills._held.clear()

# ---------- frames after a move: wait for one written after it ended, never longer than FRESH_WAIT_S ----------
import tempfile
import time
from pathlib import Path
f = Path(tempfile.mkdtemp()) / "lumi_depth_torso.npy"
f.write_bytes(b"x")
skills.moved_at.clear()
t0 = time.time()
assert skills.fresh(f, "torso") is not None and time.time() - t0 < 0.05        # no move since: at once
skills.FRESH_WAIT_S = 0.3
skills.moved("torso")
t0 = time.time()
skills.fresh(f, "torso")                                                         # older than the move: waits, gives up
assert 0.25 < time.time() - t0 < 0.5
import threading
threading.Timer(0.2, lambda: f.write_bytes(b"y")).start()                        # a new frame comes: taken at once
skills.moved("torso")
skills.FRESH_WAIT_S = 2.0
t0 = time.time()
skills.fresh(f, "torso")
assert 0.15 < time.time() - t0 < 0.6, time.time() - t0
skills.moved_at.clear()

# ---------- the table's height: the biggest group of level points, not the median of everything ----------
real_flat = skills.flat_points
table = [(x, 700.0, -400.0 + (x % 7)) for x in range(0, 300, 20)]              # 15 level points of a table
seat = [(x, 900.0, -600.0) for x in range(0, 200, 20)]                          # 10 of a chair seat
skills.flat_points = lambda pts, guess_z=-400.0, camera="torso", T=None: (table + seat + [None] * 30)[:len(pts)]
z, group = skills.flat_top([(0, 0)] * 55, (-700.0, 0.0))
assert abs(z + 397) < 4 and len(group) == 15, (z, len(group))
assert skills.flat_top([(0, 0)] * 55, (-700.0, -500.0))[0] == -600.0           # the band leaves only the seat
assert skills.flat_top([(0, 0)] * 3, (-700.0, 0.0)) is None                      # too few points
skills.flat_points = real_flat
print("skills fresh / flat ok")

# ---------- a pick stores what put down needs: the table under the object, also when its bottom was not in view ------
real_prepare, skills._prepare = skills._prepare, lambda: None
skills._cancel.clear()                                                          # cancel() above
skills.motion.move_joints = lambda j, speed=None: None
skills.gripper.close = lambda: {"ai": [3500.0], "holding": True, "object_in_front": False}
skills.gripper.state = lambda: {"ai": [3500.0], "holding": True}
skills.table_near = lambda obj: -395.0                                          # the ring of table around it
skills._held.clear()
skills._do_pick(cup, skills.plan_pick(cup), READY)                              # no height_mm (live 2026-10-20 15:39)
assert skills._held["table"] == -395.0 and skills._held["top_mm"] == cup["top_mm"], skills._held
skills._do_pick({**cup, "height_mm": 120.0}, skills.plan_pick(cup), READY)      # its own bottom seen: that one
assert skills._held["table"] == cup["top_mm"] - 120.0 and skills._held["below"] == skills.BELOW_RIM_MM
skills._do_pick(apple, skills.plan_pick(apple), READY)                          # a round one: held higher up on it
assert np.isclose(skills._held["below"], apple["top_mm"] - skills.grasp_height(apple)) and skills._held["table"] == apple["top_mm"] - 80.0
# put down (voice "put it down"): the held turn reaches no spot -> up to carry height, then another turn and wrist
def ik_place(name, **a):
    if name == "kine_forward":
        return {"errorCode": "0", "cartPosition": [0.0, 0.0, 0.0] + list(skills.GRASP_RPY)}
    p = a["cartPosition"]
    if p[2] > -100.0 or a["jointPosition"][4] < 0 and abs(skills.yaw_of(p)) >= 44:   # up high, or turned and flipped
        return {"errorCode": "0", "jointPosition": list(a["jointPosition"])}
    return {"errorCode": "1"}


skills._ask, skills._joints = ik_place, lambda: list(READY)
skills.motion.tcp = lambda: skills.flange_for(cup["x"], cup["y"], cup["top_mm"] - 10.0)
lines_, turned = [], []
skills._line = lambda name, pose: lines_.append(name)
skills.place_turned = lambda way, ja: turned.append((way, ja))
assert skills.place(-200.0, 600.0) == (-200.0, 600.0)
assert lines_ == ["carry"] and turned[0][1][4] < 0 and abs(round(skills.yaw_of(turned[0][0][1][1]))) == 45, turned
skills._held.clear()
print("skills pick stores ok")

# ---------- a bottle: held by its body, under where the neck widens (objects.body on a depth profile) ----------
H_CAM, D_CAM = -100.0, 600.0                     # camera 300 mm above a table at z -400, the bottle's axis 600 mm ahead
T_CAM = np.eye(4)
T_CAM[:3, :3], T_CAM[:3, 3] = [[1, 0, 0], [0, 0, 1], [0, -1, 0]], [0.0, 0.0, H_CAM]   # looking along y, level
INTR = {"fx": 600.0, "fy": 600.0, "cx": 320.0, "cy": 100.0, "dist": [0.0] * 5}
BOX = (250, 120, 390, 420)


def depth_of(radius):
    """A level depth camera's frame of an upright round thing on a table at z -400: radius(z) mm, 0 = nothing."""
    d = np.zeros((480, 640), np.uint16)
    u, v = np.meshgrid(np.arange(BOX[0], BOX[2]), np.arange(BOX[1], BOX[3]))
    xn, yn = (u - INTR["cx"]) / INTR["fx"], (v - INTR["cy"]) / INTR["fy"]
    for t in np.arange(D_CAM - 60.0, D_CAM, 0.5)[::-1]:            # far to near: the nearest surface stays
        z = H_CAM - t * yn
        r = np.vectorize(radius)(z)
        hit = (t * xn) ** 2 + (t - D_CAM) ** 2 <= r ** 2
        d[v[hit], u[hit]] = round(t)
    return d


def bottle_r(body, shoulder=-230.0, neck=14.0, top=-150.0):
    """A bottle: body radius up to `shoulder`, a 30 mm shoulder narrowing to the neck, the neck up to `top`."""
    return lambda z: 0.0 if z < -400 or z > top else body if z <= shoulder else \
        neck if z >= shoulder + 30 else body + (neck - body) * (z - shoulder) / 30


from vision import objects
prof = objects.body(depth_of(bottle_r(33.0)), BOX, INTR, T_CAM)                 # 66 mm body, 28 mm neck
assert -232 <= prof["shoulder_mm"] <= -212 and 60 <= prof["body_mm"] <= 67 and prof["low_mm"] < -390, prof
cup_prof = objects.body(depth_of(lambda z: 0.0 if z < -400 or z > -305 else 40.0 - (-305 - z) * 0.05), BOX, INTR, T_CAM)
assert cup_prof["shoulder_mm"] >= -320, cup_prof                               # a cup: widest at its top, no neck

skills._held.clear()
bottle = {"name": "bottle", "colour": "blue", "x": -195.0, "y": 600.0, "top_mm": -150.0, "width_mm": 63.0,
          "height_mm": None, "shoulder_mm": -203.0, "body_mm": 58.0, "low_mm": -365.0}      # the spray can 2026-10-22
assert skills.refusal("bottle") is None and skills.grip_width(bottle) == 66.0             # its body, not the mid band
z = skills.grasp_height(bottle)
assert z == -203.0 - skills.BELOW_SHOULDER_MM and z - skills.TIP_MM >= bottle["low_mm"] + skills.TIP_CLEAR_MM
(_, b_above), (_, b_grasp), (_, b_lift) = skills.plan_pick(bottle)
assert np.allclose(np.array(b_grasp[:3]) + R @ (skills.GRASP_OFFSET + skills.TIPS_OFFSET), [bottle["x"], bottle["y"], z])
assert np.isclose(b_above[2] - b_grasp[2], bottle["top_mm"] - z + skills.TIP_MM)   # tips come down from over its top
assert np.isclose(b_lift[2] - b_grasp[2], skills.LIFT_MM)
assert skills.grip_width(bottle) < skills.BELLY_MIN_MM < skills.grip_width({**bottle, "body_mm": 70.0})   # tips / belly
way = dict(skills.plan_place(-130, 600, bottle["top_mm"], below=bottle["top_mm"] - z))
assert np.isclose(way["release up"][2] - way["place"][2], bottle["top_mm"] - z + skills.TIP_MM)   # up over its top
assert np.isclose(way["above place"][2] - way["place"][2], skills.ABOVE_MM)
cup_way = dict(skills.plan_place(-130, 600, cup["top_mm"], below=skills.BELOW_RIM_MM))          # a cup: as before
assert np.isclose(cup_way["release up"][2] - cup_way["place"][2], skills.ABOVE_MM)
assert skills.grasp_height({**bottle, "low_mm": -300.0, "table_mm": -396.0}) == z    # bottom out of view: the table
for bad, words in (({"body_mm": 50.0}, ("too small", "작아서")),
                   ({"low_mm": -300.0}, ("hit the table", "테이블에 닿아요")),    # ... not measured: its lowest point                  # a too narrow body: 58 at the fingers
                   ({"body_mm": 90.0}, ("too big", "너무 커요")),
                   ({"shoulder_mm": -280.0}, ("hit the table", "테이블에 닿아요")),   # the tips would reach the table
                   ({"shoulder_mm": None}, ("body well enough", "몸통이 잘"))):
    try:
        skills.plan_pick({**bottle, **bad})
        raise AssertionError(f"bottle {bad} planned")
    except skills.SkillError as e:
        assert words[0] in e.args[0] and words[1] in e.args[1] and e.args[1].startswith("병"), (bad, e.args)

# look(): the profile of each frame's bottle box, medians of them; nothing for a cup
frames_ = [{"age_s": 0.1, "objects": [{"name": "bottle", "box": BOX, "colour": "blue", "position_mm": [-195, 600, -280],
                                       "top_mm": -150, "width_mm": 63, "height_mm": 250},
                                      {"name": "cup", "box": BOX, "colour": "white", "position_mm": [0, 600, -350],
                                       "top_mm": -310, "width_mm": 72, "height_mm": 90}]}] * 2
skills.camview.want = lambda name: None
skills.fresh = lambda path, camera, after=0.0: None
skills.objects.latest = lambda camera=objects.CAMERA: frames_[0]
skills.camview.depth = lambda name, max_age=1.0: depth_of(bottle_r(33.0))
skills.camview.intrinsics = lambda name: INTR
skills.objects.base_from_camera = lambda: T_CAM
skills.FRAME_GAP_S = 0.0
got = {o["name"]: o for o in skills.look(frames=2)}
assert got["bottle"]["shoulder_mm"] == prof["shoulder_mm"] and got["bottle"]["body_mm"] == prof["body_mm"], got
assert got["cup"]["shoulder_mm"] is None and got["cup"]["body_mm"] is None
print("skills bottle ok")

# offset_fix: hover readings at one spot (ring centre - rim centre) = e - Rz(turn) u; the error u of the taught grasp
# point turns with the grasp, the camera's e does not
u, e = np.array([12.0, -7.0]), np.array([3.0, 2.0])
reads = [(t, e - skills._rz(t)[:2, :2] @ u) for t in (0.0, -30.0, -45.0)]
got_u, got_e, new = skills.offset_fix(reads)
assert np.allclose(got_u, u) and np.allclose(got_e, e)
fixed = skills.flange_for(-100.0, 600.0, -300.0, -30.0)       # with the new offset the ring lands on the cup at any turn
Rt = calib.rpy_matrix(*fixed[3:])
assert np.allclose((np.array(fixed[:3]) + Rt @ new)[:2], np.array([-100.0, 600.0]) - skills._rz(-30.0)[:2, :2] @ u)
print("skills offset ok")

# on_table: a spot whose near ring point is just off the table's near edge is not table, though that sight line, aimed
# a little too high, meets the top a bit further on at table height, or the top's edge face (not level) (X1's sweep:
# cups put down 3-10 mm inside the edge)
CAM, EDGE_Y, TOP = np.array([-258.0, 14.0, -41.0]), 600.0, -420.0
def cast(pts, guess_z=-400.0):                               # flat_points' answer: level top / floor, None on the face
    out = []
    for p in pts:
        p = np.array([p[0], p[1], p[2] if len(p) > 2 else guess_z])
        d = (p - CAM) / np.linalg.norm(p - CAM)
        q = CAM + d * (TOP - CAM[2]) / d[2]                    # where the line meets the table's plane
        face = CAM + d * (EDGE_Y - CAM[1]) / d[1]              # ... and the plane of its near face
        out.append(tuple(q) if q[1] >= EDGE_Y else None if TOP - 30.0 <= face[2] <= TOP
                   else tuple(CAM + d * (-900.0 - CAM[2]) / d[2]))
    return out
skills.flat_points = cast
assert skills.on_table([(-100.0, 700.0)], -400.0) == [(-100.0, 700.0)]       # well on it, table read 20 mm high
assert skills.on_table([(-100.0, 620.0)], -400.0) == []                      # its near ring point 5 mm off the edge
assert skills.on_table([(-100.0, 700.0)]) == [(-100.0, 700.0)]               # table height not given
print("skills on_table ok")

# ---------- side grasp: a cup too wide at the top for the hooks to come down over it, narrower lower down ----------
top = cup["top_mm"]
wide = {**cup, "width_mm": 92.0, "height_mm": 120.0,                       # 100 the fingers would meet: over MAX_WIDTH
        "profile": [(top - 10.0 * i, 100.0 if i < 4 else 72.0) for i in range(12)]}  # 100 at the rim, 72 from 40 mm down
assert skills.side(wide) and not skills.side(cup)
d = skills.tips_dir()
assert np.isclose(np.linalg.norm(d), 1.0) and d[1] > 0.5                     # the tips point away from the robot
z = skills.side_height(wide)
assert z == top - 65.0, z               # nearest SIDE_AT of its 120 mm (50 mm up, top - 70) where the band is all 72
short = {**wide, "top_mm": top - 50.0, "height_mm": 70.0,                   # a 70 mm cup on the same table
         "profile": [(top - 50.0 - 10.0 * i, 100.0 if i < 2 else 74.0) for i in range(7)]}
assert skills.side_height(short) == top - 50.0 - 45.0                         # 25 mm up: the hooks' bottom 17 over it
way = skills.plan_pick(wide)
assert [n for n, _ in way] == ["above", "side", "grasp", "lift"], way
p = dict(way)
assert np.isclose(p["side"][2], p["grasp"][2]) and p["side"][3:] == p["grasp"][3:]          # in level at the grasp height
back = skills.side_back(wide)
assert np.isclose(back, 100.0 / 2 + np.linalg.norm(skills.TIPS_OFFSET) + skills.SIDE_CLEAR_MM)
assert np.allclose(np.subtract(p["grasp"][:2], p["side"][:2]), d * back)  # it goes in along the tips' direction
assert np.allclose(np.subtract(p["above"][:3], p["side"][:3]), [0, 0, skills.clear_above(top - z)])
g = np.array(p["grasp"][:3]) + calib.rpy_matrix(*p["grasp"][3:]) @ skills.GRASP_OFFSET
assert np.allclose(g, [wide["x"], wide["y"], z])                            # the hooks' point on the cup axis
assert [n for n, _ in skills.plan_pick(cup)] == ["above", "grasp", "lift"]  # a cup whose top fits: from above, as before
for bad in ([(top - 10.0 * i, 100.0) for i in range(12)],                    # wide all the way down
            [(top - 10.0 * i, 100.0 if i < 10 else 72.0) for i in range(12)],   # narrow only where the hooks hit the table
            None):                                                         # its widths down its height not measured
    try:
        skills.plan_pick({**wide, "profile": bad})
        raise AssertionError(f"side grasp planned for {bad}")
    except skills.SkillError as e:
        assert e.args == skills.reason(skills.WIDE, "cup"), e.args
# picked from the side: the open hand backs out sideways before it goes up, also after a miss
lines_, opened = [], []
skills._line = lambda name, pose: lines_.append((name, pose))
skills.gripper.open_ = lambda: (opened.append(len(lines_)), {"ai": [150.0]})[1]
skills.gripper.close = lambda: {"ai": [3500.0], "holding": True, "object_in_front": False}
skills.gripper.state = lambda: {"ai": [3500.0], "holding": True}
skills._back_home = lambda: None
skills._held.clear()
skills._do_pick(wide, way, READY)
assert [n for n, _ in lines_] == ["side", "grasp", "lift"] and np.isclose(skills._held["back"], back)
assert np.isclose(skills._held["below"], top - z)
put = skills.plan_place(-200, 600, top)
assert [n for n, _ in put] == ["above place", "place", "release back", "release up"], put
q = dict(put)
assert np.isclose(q["release back"][2], q["place"][2])
assert np.allclose(np.subtract(q["place"][:2], q["release back"][:2]), d * back)
assert np.allclose(np.subtract(q["release up"][:3], q["release back"][:3]), [0, 0, skills.clear_above(top - z)])
lines_.clear()
skills._do_place(put)
assert [n for n, _ in lines_] == ["above place", "place", "release back", "release up"] and opened[-1] == 2
assert [n for n, _ in skills.plan_place(-200, 600, top, back=0.0)][-2:] == ["place", "release up"]   # from above: as before
lines_.clear()
skills.gripper.close = lambda: {"ai": [4150.0], "holding": False, "object_in_front": False}
skills.motion.tcp = lambda: p["grasp"]
skills.motion.move_linear = lambda **k: lines_.append(("up", k.get("delta")))
try:
    skills._do_pick(wide, way, READY)
    raise AssertionError("a miss went on")
except skills.SkillError:
    pass
assert [n for n, _ in lines_] == ["side", "grasp", "out sideways", "up"], lines_
assert np.allclose(np.subtract(p["grasp"][:2], lines_[2][1][:2]), d * back)
skills._held.clear()
print("skills side grasp ok")

# ---------- a pick stopped on its way in (the open hand beside / around the cup): the next pick backs out the way it
# came first, never a diagonal move from there; a stop once the fingers hold it leaves it ready to put down ----------
def stop_at(where, at):                              # STOP while moving to waypoint `where`: the hand ends at `at`
    def line(name, pose):
        lines_.append((name, pose))
        if name == where:
            skills.motion.tcp = lambda: list(at)
            raise skills.SkillError("Stopped.")
        skills.motion.tcp = lambda: list(pose)
    return line
skills.gripper.close = lambda: {"ai": [3500.0], "holding": True, "object_in_front": False}
skills.gripper.state = lambda: {"ai": [150.0], "holding": False}       # open: the stop came before the close
skills._joints = skills.home_joints = lambda: [0.0] * 6                # back at home after backing out: no route
mid = list(np.add(p["side"], p["grasp"]) / 2)                          # half way in, beside the cup
for way_, where, at, want in ((way, "grasp", mid, ["out sideways", "up"]),                  # side grasp, half way in
                              (way, "grasp", p["grasp"], ["out sideways", "up"]),           # ... around it
                              (way, "side", p["side"], ["up"]),                             # ... still coming down
                              (skills.plan_pick(cup), "grasp", grasp, ["up"])):             # down around it from above
    w = dict(way_)
    skills._held.update(top_mm=-1.0, x=0.0, y=0.0)                                         # from an earlier pick
    lines_.clear()
    skills._line = stop_at(where, at)
    try:
        skills._do_pick(wide if "side" in w else cup, way_, READY)
        raise AssertionError("not stopped")
    except skills.SkillError:
        pass
    try:                                                         # "put it down": nothing is held, nothing moves
        skills.put_down()
        raise AssertionError("put down with an open hand")
    except skills.SkillError as e:
        assert e.args[0] == "I'm not holding anything I picked.", e.args
    lines_.clear()
    real_prepare()                                               # "take the cup" again
    assert [n for n, _ in lines_] == want, (where, lines_)
    out, top_ = lines_[-2][1] if len(lines_) > 1 else at, lines_[-1][1]
    start_ = w.get("side", w["grasp"])
    assert np.allclose(out[:3], [start_[0], start_[1], at[2]], atol=1e-6), (out, start_)   # out along the way in
    assert np.allclose(top_[:3], [start_[0], start_[1], w["above"][2]], atol=1e-6)        # then straight up to above
    lines_.clear()
    real_prepare()                                               # backed out once: nothing more
    assert not lines_, lines_
skills.motion.tcp = lambda: [0.0, 300.0, 0.0] + list(skills.GRASP_RPY)   # moved away since (another task): no lines
skills._line = stop_at("grasp", grasp)
try:
    skills._do_pick(cup, skills.plan_pick(cup), READY)
except skills.SkillError:
    pass
skills.motion.tcp = lambda: [0.0, 300.0, 0.0] + list(skills.GRASP_RPY)
lines_.clear()
real_prepare()
assert not lines_ and not skills._pick_way, lines_
# STOP in the lift, the fingers holding it: put down knows it (as at the end of a pick), the next pick backs out nothing
for way_, obj_ in ((way, wide), (skills.plan_pick(cup), cup)):
    skills._held.clear()
    skills._line = stop_at("lift", dict(way_)["grasp"])
    try:
        skills._do_pick(obj_, way_, READY)
        raise AssertionError("not stopped")
    except skills.SkillError:
        pass
    assert skills._held["top_mm"] == obj_["top_mm"] and np.isclose(skills._held["back"], back if obj_ is wide else 0.0)
    assert np.isclose(skills._held["below"], obj_["top_mm"] - skills.grasp_height(obj_)) and not skills._pick_way
    placed = []
    real_place_first, skills._place_first = skills._place_first, lambda tries, refusal: placed.append(tries[0])
    skills.put_down(back=True)
    skills._place_first = real_place_first
    assert placed == [(obj_["x"], obj_["y"])], placed
skills._held.clear()
print("skills stopped pick ok")
