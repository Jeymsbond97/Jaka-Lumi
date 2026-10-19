"""Pick and place with the torso camera, the arm and the gripper: find an object, plan every pose, check it with
the controller's IK, then move. Nothing moves unless the whole plan (pick and place) passes.

The grasp is the one taught in grasp_teach.json: the flange orientation with the fingers around a cup, and the
point between the fingers where the cup's axis sits 4 cm below the rim. Down from 10 cm above, close, lift.

    python manipulation/skills.py plan [cup] [--to X Y]     # dry run: object, place spot, every waypoint with IK joints
    python manipulation/skills.py pick cup                  # pick it up and hold it 3 cm above the table
    python manipulation/skills.py move cup [--to X Y]       # pick it up and put it down at X Y (mm, base frame) or a free spot

Ctrl+C, cancel() (STOP in the API, "stop" by voice) or any motion error stops the arm; the gripper keeps its state.
The API and the assistant call pick(), put_down(), move_object() and cancel() in their own process.
"""
import collections
import json
import math
import statistics
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from robot import arm
from vision import calib
from vision import camview
from robot import gripper
from robot import motion
from vision import objects

ROOT = Path(__file__).resolve().parents[1]      # the project folder
TEACH = json.loads((ROOT / "data" / "grasp_teach.json").read_text())
GRASP_RPY = TEACH["flange"][3:]                  # deg, flange orientation with the fingers around a cup
GRASP_OFFSET = np.array(TEACH["tcp_offset_flange"])   # mm, cup axis 4 cm below the rim, in the flange frame
GRASP_YAWS = (0, *(s * a for a in range(15, 180, 15) for s in (-1, 1)), 180)   # deg; the taught grasp turned about
                                                 # the vertical, every 15 deg all the way round, nearest the taught one
                                                 # first (the cup stays upright at every one)
EMPTY_SPEED = "normal"                           # arm speed with nothing in the hand (motion.JOINT_SPEED / LINEAR_SPEED:
                                                 # "normal" = 25 deg/s, 50 mm/s)
HOLDING_SPEED = "slow"                           # with an object in the hand, and the last 10 cm down onto one or
                                                 # away from it ("slow" = 10 deg/s, 20 mm/s)
HOME_POSE = "look"                               # empty hand: picks start here and the arm comes back here
                                                 # (high, out of the torso camera's view; ready if not taught)
PATH_POINTS = 11                                 # points checked (kine_forward) on a joint move
PATH_SAG_MM = 20.0                               # a joint move may take the gripper at most this much below both ends
TIP_MM = 60.0                                    # finger tips this far beyond the grasp point along the tool axis
BELOW_RIM_MM = 40.0                              # grasp this far below the object's top
ABOVE_MM = 100.0                                 # approach / retreat height over the grasp pose
LIFT_MM = 30.0                                   # first lift after closing, then check the grip again
PLACE_EXTRA_MM = 3.0                             # put down this much higher than it was picked (same table)
MIN_WIDTH, MAX_WIDTH = 45.0, 84.0                # mm; fingertip entry is 88 mm, the fingers close to ~62
FRAMES = 8                                       # camera frames looked at by find()
FRAME_GAP_S = 0.2                                # s between them
MIN_SEEN = 5                                     # an object must be in this many frames, at the same place
CLUSTER_MM = 40.0                                # detections closer than this (x, y) are the same object
SPREAD_MM = 20.0                                 # a detection further than this from the median -> unstable
IGNORE = {"dining table"}                        # classes that are never objects to pick or avoid
FREE_MM = 110.0                                  # a place spot keeps this distance from other objects' centres
PLACE_X = (-240.0, -100.0)                       # mm; place spots stay in this zone (picks proven to work there)
PLACE_Y = (560.0, 630.0)
SPOT_DX = (-60, -90, -120, 60, 90, 120)          # mm; candidate offsets from the pick point, tried in this order
SPOT_DY = (0, -20, -40, 20)
TABLE_RING_MM = 50.0                             # a place spot is checked at its centre and 8 points this far around
TABLE_TOL_MM = 25.0                              # ... each must be table: depth within this of the table height
LOCATE_MM = 90.0                                 # locate(): looked for this far around where an object was last seen,
LOCATE_STEP_MM = 15.0                            # ... on a grid this fine
LOCATE_MIN_HITS = 4                              # ... with at least this many depth points above half its height
HAND_PROBE_MM = (30.0, 50.0, 70.0)               # hand_sees(): points this far below the grasp point, on the cup's axis
HAND_NEAR_MM = 60.0                              # ... depth no further than this behind one = something in the hand
HAND_FAR_MM = 250.0                              # ... depth further than this behind one = nothing there (the room)
NEAR_FRACTION = 0.7                              # depth nearer than this part of the expected one: something in front
                                                 # of the sight line (the gripper, the held cup), not the surface
RETRIES = 4                                      # the controller now and then answers with nothing: ask again
RETRY_S = 0.2
OPEN_AI = gripper.CLOSED_AI                      # AI_1 below this after opening = released

_held = {}                                       # what pick() holds: {"top_mm", "x", "y"} for place() / put_down()
_cancel = threading.Event()                      # set by cancel(): the running skill makes no further move
LOG = collections.deque(maxlen=40)               # last log lines, shown by the API


class SkillError(RuntimeError):
    """A plain spoken-style reason why the skill cannot go on."""


def log(*a):
    line = " ".join(str(x) for x in (time.strftime("%H:%M:%S"),) + a)
    LOG.append(line)
    print(line, flush=True)


def cancel():
    """Stop the running skill: the arm stops now and no further move or grip starts."""
    _cancel.set()
    return motion.stop()


def _go_on():
    if _cancel.is_set():
        raise SkillError("Stopped.")


# ---------- seeing ----------
def look(frames=FRAMES):
    """Detections over several frames, grouped by position: [{name, colour, x, y, top_mm, width_mm, height_mm, seen,
    spread}]
    with medians of the detections that agree with the majority name. Raises when the camera is not live."""
    camview.want(objects.CAMERA)
    groups, live = [], 0
    for i in range(frames):
        d = objects.latest()
        if d["age_s"] is not None and d["age_s"] < objects.STALE_S:
            live += 1
            for o in d["objects"]:
                if o["name"] in IGNORE or not o.get("position_mm"):
                    continue
                x, y = o["position_mm"][:2]
                g = next((g for g in groups if np.hypot(x - g[0]["x"], y - g[0]["y"]) < CLUSTER_MM), None)
                row = {"name": o["name"], "colour": o.get("colour"), "x": x, "y": y, "top_mm": o.get("top_mm"),
                       "width_mm": o.get("width_mm"), "height_mm": o.get("height_mm")}
                if g:
                    g.append(row)
                else:
                    groups.append([row])
        if i < frames - 1:
            time.sleep(FRAME_GAP_S)
    if live < frames // 2:
        raise SkillError("My camera isn't working right now.")
    out = []
    for g in groups:
        name = statistics.mode(r["name"] for r in g)
        rows = [r for r in g if r["name"] == name]
        med = {k: statistics.median(r[k] for r in rows if r[k] is not None) if any(r[k] is not None for r in rows)
               else None for k in ("x", "y", "top_mm", "width_mm", "height_mm")}
        spread = max(np.hypot(r["x"] - med["x"], r["y"] - med["y"]) for r in rows)
        out.append({"name": name, "colour": statistics.mode(r["colour"] for r in rows), **med, "seen": len(rows),
                    "spread": round(float(spread), 1)})
    return sorted(out, key=lambda o: np.hypot(o["x"], o["y"]))


def find(name="cup", colour=None, seen=None):
    """The nearest stable `name` (of `colour`) the torso camera sees, from look() (or `seen`, its result)."""
    seen = look() if seen is None else seen
    what = f"{colour + ' ' if colour else ''}{name}"
    hits = [o for o in seen if o["name"] == name and (colour is None or o["colour"] == colour)]
    if not hits:
        raise SkillError(f"I can't see a {what}.")
    steady = [o for o in hits if o["seen"] >= MIN_SEEN and o["spread"] <= SPREAD_MM and o["top_mm"] is not None]
    if not steady:
        raise SkillError(f"I'm not sure where the {what} is, it keeps changing.")
    return steady[0]


# ---------- geometry ----------
def _rz(deg):
    a = math.radians(deg)
    return np.array([[math.cos(a), -math.sin(a), 0.0], [math.sin(a), math.cos(a), 0.0], [0.0, 0.0, 1.0]])


def rpy_of(R):
    """Inverse of calib.rpy_matrix (R = Rz Ry Rx), deg."""
    return [math.degrees(math.atan2(R[2, 1], R[2, 2])), math.degrees(math.asin(-R[2, 0])),
            math.degrees(math.atan2(R[1, 0], R[0, 0]))]


def flange_for(x, y, z, yaw=0.0):
    """Flange pose that puts the taught grasp point at (x, y, z) mm, the taught orientation turned by `yaw` deg
    about the vertical."""
    if not yaw:
        R, rpy = calib.rpy_matrix(*GRASP_RPY), list(GRASP_RPY)
    else:
        R = _rz(yaw) @ calib.rpy_matrix(*GRASP_RPY)
        rpy = rpy_of(R)
    f = np.array([x, y, z]) - R @ GRASP_OFFSET
    return [float(v) for v in f] + rpy


def yaw_of(pose):
    """How far (deg) a flange pose is turned about the vertical from the taught grasp."""
    D = calib.rpy_matrix(*pose[3:]) @ calib.rpy_matrix(*GRASP_RPY).T
    return math.degrees(math.atan2(D[1, 0], D[0, 0]))


def up(pose, dz):
    return [pose[0], pose[1], pose[2] + dz] + list(pose[3:])


def plan_pick(obj, yaw=0.0):
    """Waypoints [(name, flange pose)] to pick `obj` (a find() result). Refuses objects of the wrong width."""
    w = obj.get("width_mm")
    if w is None or w > MAX_WIDTH:
        raise SkillError(f"The {obj['name']} is too big for my hand.")
    if w < MIN_WIDTH:
        raise SkillError(f"The {obj['name']} is too small for me to hold.")
    grasp = flange_for(obj["x"], obj["y"], obj["top_mm"] - BELOW_RIM_MM, yaw)
    return [("above", up(grasp, ABOVE_MM)), ("grasp", grasp), ("lift", up(grasp, LIFT_MM))]


def plan_place(x, y, top_mm, start=None, yaw=0.0):
    """Waypoints to put down what was picked with its top at `top_mm`, centred at (x, y), the grasp turned by `yaw`.
    `start`: the flange pose it is held at now (adds the lift to carry height there)."""
    down = up(flange_for(x, y, top_mm - BELOW_RIM_MM, yaw), PLACE_EXTRA_MM)
    steps = [("carry", [start[0], start[1], down[2] - PLACE_EXTRA_MM + ABOVE_MM] + list(start[3:]))] if start else []
    return steps + [("above place", up(down, ABOVE_MM)), ("place", down), ("release up", up(down, ABOVE_MM))]


def spots(pick_xy, others):
    """Candidate place spots (x, y) near the pick point, inside the place zone, FREE_MM from every other object."""
    out = []
    for dx in SPOT_DX:
        for dy in SPOT_DY:
            x, y = pick_xy[0] + dx, pick_xy[1] + dy
            if not (PLACE_X[0] <= x <= PLACE_X[1] and PLACE_Y[0] <= y <= PLACE_Y[1]):
                continue
            if all(np.hypot(x - o["x"], y - o["y"]) >= FREE_MM for o in others):
                out.append((x, y))
    return out


def table_z(obj):
    """Height (mm) of the table an object stands on, from its top and height, or None."""
    return obj["top_mm"] - obj["height_mm"] if obj.get("top_mm") is not None and obj.get("height_mm") else None


def surface_heights(points_xy, guess_z=-400.0):
    """z (mm, arm base frame) of the surface the torso depth camera sees on its line of sight to each
    (x, y, guess_z); None where the point is out of view or has no depth. A table at another height is still
    measured right (the sight line meets it a little nearer or further)."""
    return [None if q is None else q[2] for q in surface_points(points_xy, guess_z)]


def surface_points(points_xy, guess_z=-400.0, camera=objects.CAMERA, T=None):
    """(x, y, z) mm, arm base frame, where the torso depth camera's line of sight to each (x, y, guess_z) (or to each
    (x, y, z) given whole) meets a surface; None where the point is out of view or has no depth. Another camera:
    its name and its camera -> arm base transform T."""
    d, intr = camview.depth(camera), camview.intrinsics(camera)
    T = objects.base_from_camera() if T is None else T
    if d is None or intr is None or T is None:
        log("no depth frame: I can't measure the table")
        return [None] * len(points_xy)
    K = np.array([[intr["fx"], 0, intr["cx"]], [0, intr["fy"], intr["cy"]], [0, 0, 1]])
    dist, Ti = np.array(intr["dist"]), np.linalg.inv(T)
    P = np.array([[p[0], p[1], p[2] if len(p) > 2 else guess_z] for p in points_xy], float)
    cam = (Ti[:3, :3] @ P.T + Ti[:3, 3:4]).T
    uv = cv2.projectPoints(cam, np.zeros(3), np.zeros(3), K, dist)[0].reshape(-1, 2)
    out = []
    for (u, v), expected in zip(np.round(uv).astype(int), cam[:, 2]):
        win = d[max(v - 2, 0):v + 3, max(u - 2, 0):u + 3] if 0 <= u < d.shape[1] and 0 <= v < d.shape[0] else d[:0]
        win = win[win > 0]
        if win.size == 0:
            out.append(None)
            continue
        depth_mm = float(np.median(win))
        if depth_mm < NEAR_FRACTION * expected:
            out.append(None)
            continue
        n = cv2.undistortPoints(np.array([[[u, v]]], np.float64), K, dist).reshape(2)
        out.append(tuple(float(v) for v in T[:3, :3] @ [n[0] * depth_mm, n[1] * depth_mm, depth_mm] + T[:3, 3]))
    return out


def locate(xy, top_mm, table_mm, width_mm, radius=LOCATE_MM):
    """An object last seen at `xy` (mm) with its top at `top_mm` on a table at `table_mm`, looked for with depth only
    (YOLO may miss it): ("here", obj) with its centre and top from what stands above half its height within
    `radius`; ("gone", None) when the camera sees only table there; ("unseen", None) when it can't see the place."""
    pts = [(xy[0] + dx, xy[1] + dy) for dx in np.arange(-radius, radius + 1, LOCATE_STEP_MM)
           for dy in np.arange(-radius, radius + 1, LOCATE_STEP_MM)]
    hits = [q for q in surface_points(pts, top_mm - 20.0) if q is not None]
    if len(hits) < len(pts) / 3:
        return "unseen", None
    tall = np.array([q for q in hits if q[2] > table_mm + (top_mm - table_mm) / 2])
    if len(tall) < LOCATE_MIN_HITS:
        return "gone", None
    c = tall[:, :2].mean(axis=0)
    cam = objects.base_from_camera()[:2, 3]
    away = (c - cam) / max(np.linalg.norm(c - cam), 1e-6)       # the camera sees the front half of the cup: its
    c = c + away * (2 / math.pi) * width_mm / 2                 # mean lies 0.64 r nearer than the axis
    return "here", {"x": float(c[0]), "y": float(c[1]), "top_mm": float(tall[:, 2].max()), "width_mm": width_mm}


def hand_sees():
    """What the torso depth camera sees where a held object would be (on the cup's axis just below the grasp point,
    from the arm's joints now): "object", "empty", or "unknown" (out of view, no depth, the fingers in the way).
    In look the place is in view (2026-10-16: pixel (558, 259), 264 mm away): an empty hand reads "empty" (the room
    behind); a cup held there gave no depth at all ("unknown", too near for the camera), so a held object is left to
    AI_1. The gripper's AI_1 alone can be wrong: a cup pulled out of the closed fingers left it at 162 ("open")."""
    c = _ask("kine_forward", jointPosition=[float(v) for v in _joints()])["cartPosition"]
    R, f = calib.rpy_matrix(*c[3:]), np.array(c[:3])
    g = f + R @ GRASP_OFFSET
    pts = [g - [0.0, 0.0, dz] for dz in HAND_PROBE_MM]
    T = objects.base_from_camera()
    if T is None:
        return "unknown"
    cam = T[:3, 3]
    near = far = 0
    for p, hit in zip(pts, surface_points(pts)):
        if hit is None:
            continue
        behind = np.linalg.norm(np.subtract(hit, cam)) - np.linalg.norm(p - cam)
        near += behind <= HAND_NEAR_MM
        far += behind > HAND_FAR_MM
    return "object" if near >= 2 else "empty" if far >= 2 and not near else "unknown"


def table_near(obj):
    """Height (mm) of the table around a found object: median depth surface on rings 80 and 110 mm around its centre,
    lower than its top; None when too little of it is in view."""
    guess = (table_z(obj) or obj["top_mm"] - 100.0)
    pts = [(obj["x"] + r * math.cos(a), obj["y"] + r * math.sin(a))
           for r in (80.0, 110.0) for a in np.linspace(0, 2 * math.pi, 12, endpoint=False)]
    zs = [z for z in surface_heights(pts, guess) if z is not None and z < obj["top_mm"] - 30.0]
    return statistics.median(zs) if len(zs) >= 6 else None


def on_table(spots_xy, table_mm=None):
    """The (x, y) spots where the torso depth camera sees table: the centre and TABLE_RING_MM around it, each within
    TABLE_TOL_MM of `table_mm` (None: of each other). Points the camera can't see count as not table."""
    ring = [(0.0, 0.0)] + [(TABLE_RING_MM * math.cos(a), TABLE_RING_MM * math.sin(a))
                           for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
    guess = table_mm if table_mm is not None else -400.0     # only to find the pixels; the depth decides
    out = []
    for x, y in spots_xy:
        zs = surface_heights([(x + dx, y + dy) for dx, dy in ring], guess)
        if None in zs:
            continue
        ref = table_mm if table_mm is not None else statistics.median(zs)
        if max(abs(z - ref) for z in zs) <= TABLE_TOL_MM:
            out.append((x, y))
    return out


# ---------- checking with the controller ----------
def _ask(name, **args):
    """arm.cmd with retries for empty answers / dropped connections."""
    for _ in range(RETRIES):
        try:
            r = arm.cmd(name, **args)
        except (ConnectionError, OSError):
            r = {}
        empty = r.get("errorCode") == "0" and ((name == "kine_inverse" and "jointPosition" not in r)
                                              or (name == "kine_forward" and "cartPosition" not in r))
        if "jointPosition" in r:
            r["jointPosition"] = r["jointPosition"][:6]       # some answers carry a 7th (external axis) value
        if "errorCode" in r and not empty:
            return r                     # ("0" without the answer happens too: ask again)
        time.sleep(RETRY_S)
    raise SkillError("The arm controller is not answering.")


def _joints():
    for _ in range(RETRIES):
        try:
            return motion.joints()
        except (motion.MotionError, ConnectionError, OSError):
            time.sleep(RETRY_S)
    raise SkillError("The arm controller is not answering.")


def ik_chain(waypoints, start_joints):
    """IK for each waypoint, each from the previous answer. Rows [name, pose, joints, error]; stops at the first
    error (error None = passed)."""
    rows, ref = [], list(start_joints)
    for name, pose in waypoints:
        r = _ask("kine_inverse", jointPosition=ref, cartPosition=list(pose))
        if r["errorCode"] != "0":
            rows.append([name, pose, None, "no IK solution"])
            return rows
        j = r["jointPosition"]
        err = None
        try:
            motion.check(j)
        except motion.MotionError as e:
            err = str(e)
        flips = [f"J{i + 1} turns {j[i] - ref[i]:+.0f} deg" for i in motion.FULL_TURN if abs(j[i] - ref[i]) > motion.MAX_FLIP]
        err = err or (flips[0] if flips else None)
        rows.append([name, pose, j, err])
        if err:
            return rows
        ref = j
    return rows


def home():
    return HOME_POSE if HOME_POSE in motion.poses() else "ready"


def home_joints():
    """The home pose as move_joints will reach it from here (J1 / J4 / J6 nearest the current angles)."""
    return motion.nearest(motion.poses()[home()], _joints())


def wrist_flip(j):
    """Seed for the other wrist solution of the same flange pose."""
    return [j[0], j[1], j[2], j[3] + 180.0, -j[4], j[5] + 180.0]


def above_joints(pose, start=None):
    """Joint solutions for the approach pose `pose`: from `ready`'s arm configuration (where the picks were proven)
    and from it with the wrist flipped. Each is within the joint limits and a joint move from `start` (default: here)
    that move_joints accepts (no joint further than motion.MAX_TRAVEL); no duplicates."""
    start = _joints() if start is None else start
    ready = motion.nearest(motion.poses()["ready"], start)
    out = []
    for seed in (ready, wrist_flip(ready)):
        r = _ask("kine_inverse", jointPosition=[float(v) for v in seed], cartPosition=list(pose))
        if r["errorCode"] != "0":
            continue
        j = r["jointPosition"]
        try:
            motion.check(j)
        except motion.MotionError:
            continue
        near = motion.nearest(j, start)
        if max(abs(a - b) for a, b in zip(near, start)) > motion.MAX_TRAVEL:
            continue
        if all(max(abs(a - b) for a, b in zip(motion.nearest(o, j), j)) > 1.0 for o in out):
            out.append(j)
    return out


def path_heights(j0, j1):
    """Lowest z (mm) of flange, grasp point and finger tips at PATH_POINTS points of the joint move j0 -> j1."""
    j0, j1, out = np.array(j0), np.array(motion.nearest(j1, list(j0))), []
    for k in range(PATH_POINTS):
        c = _ask("kine_forward", jointPosition=[float(v) for v in j0 + (j1 - j0) * k / (PATH_POINTS - 1)])["cartPosition"]
        R, f = calib.rpy_matrix(*c[3:]), np.array(c[:3])
        g = f + R @ GRASP_OFFSET
        out.append(float(min(f[2], g[2], (g + R @ [0.0, 0.0, TIP_MM])[2])))
    return out


def joint_move_ok(j0, j1):
    """The joint move j0 -> j1 never takes the gripper more than PATH_SAG_MM below its start and its end."""
    z = path_heights(j0, j1)
    return min(z) >= min(z[0], z[-1]) - PATH_SAG_MM


def checked(waypoints, start_joints):
    rows = ik_chain(waypoints, start_joints)
    if rows[-1][3]:
        log(f"plan refused at {rows[-1][0]}: {rows[-1][3]}")
        raise SkillError("I can't reach it safely.")
    return rows


def pick_options(obj, start):
    """(waypoints, joints above) of every grasp turn (GRASP_YAWS) and wrist solution reachable from `start`: a joint
    move down to above that stays above it, then straight down and up. Objects of the wrong width raise."""
    plan_pick(obj)
    for yaw in GRASP_YAWS:
        waypoints = plan_pick(obj, yaw)
        for ja in above_joints(waypoints[0][1], start):
            if not ik_chain(waypoints[1:], ja)[-1][3] and joint_move_ok(start, ja):
                yield waypoints, ja


def reachable_pick(obj, start=None, accept=lambda waypoints, ja: True):
    """(waypoints, joints above) of the first pick option from `start` (home) that `accept` also takes, else None."""
    for waypoints, ja in pick_options(obj, home_joints() if start is None else start):
        if accept(waypoints, ja):
            yaw = round(yaw_of(waypoints[1][1]))
            log(f"grasp turned {yaw:+d} deg, wrist J5 {ja[4]:+.0f}" if yaw else f"grasp, wrist J5 {ja[4]:+.0f}")
            return waypoints, ja
    log(f"plan refused: no grasp turn reaches ({obj['x']:.0f}, {obj['y']:.0f})")
    return None


def plan_move(obj, to=None, seen=()):
    """Full pick + place plan from home: (place (x, y), IK rows). `to` None = first free spot that passes IK."""
    start = home_joints()
    if to is not None:
        tries = [tuple(to)]
    else:
        others = [o for o in seen if np.hypot(o["x"] - obj["x"], o["y"] - obj["y"]) >= CLUSTER_MM]
        tries = spots((obj["x"], obj["y"]), others)
        if not tries:
            raise SkillError("I can't find a free place to put it.")
    for pick, ja in pick_options(obj, start):      # the cup is put down turned as it was picked
        yaw = yaw_of(pick[1][1])
        for xy in tries:
            rows = ik_chain(pick[1:] + plan_place(*xy, obj["top_mm"], start=pick[-1][1], yaw=yaw), ja)
            if not rows[-1][3]:
                return xy, [["above", pick[0][1], ja, None]] + rows
            log(f"spot ({xy[0]:.0f}, {xy[1]:.0f}) grasp {yaw:+.0f} deg refused at {rows[-1][0]}: {rows[-1][3]}")
    if to is not None:
        raise SkillError("I can't reach that place safely.")
    raise SkillError("I can't find a free place I can reach.")


# ---------- moving ----------
def _prepare():
    _go_on()
    if gripper.state()["ai"][0] > OPEN_AI:
        log("opening the gripper")
        gripper.open_()
    if max(abs(a - b) for a, b in zip(_joints(), home_joints())) > 1.0:
        log(f"going to {home()}")
        motion.go(home(), EMPTY_SPEED)


def _back_home():
    """Joint move to the home pose; refused when it would take the gripper lower than where it is now."""
    _go_on()
    if not joint_move_ok(_joints(), home_joints()):
        raise SkillError("I can't get my arm back up safely from here.")
    log(f"going to {home()}")
    motion.go(home(), EMPTY_SPEED)


def _line(name, pose):
    _go_on()                             # move_linear clears motion's own stop flag, so check ours before each move
    log(f"{name}: to ({pose[0]:.0f}, {pose[1]:.0f}, {pose[2]:.0f})")
    motion.move_linear(target=pose, speed=HOLDING_SPEED)


def _give_up(reason):
    """Open, back up 100 mm, home, raise. Only used while the object is at (or just above) the table."""
    log(f"{reason}: opening, backing up")
    gripper.open_()
    motion.move_linear(delta=[0, 0, ABOVE_MM], speed=HOLDING_SPEED)
    _back_home()
    raise SkillError(reason)


def _do_pick(obj, waypoints, ja):
    """Pick with the planned joints `ja` above the object (pick_options)."""
    above, grasp, lift = (p for _, p in waypoints)
    _prepare()
    _go_on()
    log(f"above: joint move to ({above[0]:.0f}, {above[1]:.0f}, {above[2]:.0f})")
    motion.move_joints(ja, EMPTY_SPEED)
    _line("grasp", grasp)
    _go_on()
    log("closing")
    s = gripper.close()
    log(f"AI_1 {s['ai'][0]:.0f} holding {s['holding']} finger sensor {s['object_in_front']}")
    if not s["holding"]:
        _give_up("I missed it.")
    _line("lift", lift)
    s = gripper.state()
    log(f"AI_1 {s['ai'][0]:.0f} holding {s['holding']}")
    if not s["holding"]:
        _line("slipped, back down", grasp)
        _give_up("It slipped out of my hand.")
    _held.update(top_mm=obj["top_mm"], x=obj["x"], y=obj["y"], yaw=yaw_of(grasp), table=table_z(obj))


def _do_place(waypoints):
    for name, pose in waypoints[:-1]:
        _line(name, pose)
    _go_on()
    log("opening")
    s = gripper.open_()
    log(f"AI_1 {s['ai'][0]:.0f}")
    if s["ai"][0] > OPEN_AI:
        raise SkillError("My hand did not open.")           # stay put: lifting now would drag the object
    _held.clear()
    _line(*waypoints[-1])
    _back_home()


def _guarded(fn, *a):
    """Run a motion sequence; on a motion error or Ctrl+C stop the arm and re-raise."""
    try:
        return fn(*a)
    except (motion.MotionError, KeyboardInterrupt, ConnectionError, OSError):
        motion.stop()
        log("stopped")
        raise


def pick(name="cup", colour=None):
    """Find, plan, pick up and hold `name` 3 cm above the table."""
    _cancel.clear()
    obj = find(name, colour)
    log(f"found {obj['colour']} {obj['name']} at ({obj['x']:.0f}, {obj['y']:.0f}) top {obj['top_mm']:.0f} "
        f"width {obj['width_mm']:.0f}")
    plan = reachable_pick(obj)
    if plan is None:
        raise SkillError("I can't reach it safely.")
    _guarded(_do_pick, obj, *plan)
    log("holding it")
    return obj


def place(x, y):
    """Put down what pick() holds at (x, y), then go home."""
    return _place_first([(x, y)], "I can't reach that place safely.")


def put_down(back=False):
    """Put down what pick() holds: where it was picked (`back`) or at a free spot near there."""
    if "top_mm" not in _held:
        raise SkillError("I'm not holding anything I picked.")
    xy = (_held["x"], _held["y"])
    if back:
        return _place_first([xy], "I can't reach that place safely.")
    others = [o for o in look() if np.hypot(o["x"] - xy[0], o["y"] - xy[1]) >= CLUSTER_MM]   # not the held one
    tries = spots(xy, others)
    if not tries:
        raise SkillError("I can't find a free place to put it.")
    return _place_first(tries, "I can't find a free place I can reach.")


def _place_first(tries, refusal):
    """Place at the first (x, y) of `tries` whose whole path passes IK; the rest of place() / put_down()."""
    _cancel.clear()
    if "top_mm" not in _held:
        raise SkillError("I'm not holding anything I picked.")
    start, joints = motion.tcp(), _joints()
    for xy in tries:
        rows = ik_chain(plan_place(*xy, _held["top_mm"], start=start, yaw=_held.get("yaw", 0.0)), joints)
        if not rows[-1][3]:
            _guarded(_do_place, [(r[0], r[1]) for r in rows])
            log("done")
            return xy
        log(f"spot ({xy[0]:.0f}, {xy[1]:.0f}) refused at {rows[-1][0]}: {rows[-1][3]}")
    raise SkillError(refusal)


def move_object(name="cup", colour=None, to=None):
    """Pick `name` up and put it at `to` (x, y) or at a free spot. Everything is planned before anything moves."""
    _cancel.clear()
    seen = look()
    obj = find(name, colour, seen)
    log(f"found {obj['colour']} {obj['name']} at ({obj['x']:.0f}, {obj['y']:.0f}) top {obj['top_mm']:.0f}")
    xy, rows = plan_move(obj, to, seen)
    log(f"placing at ({xy[0]:.0f}, {xy[1]:.0f}); plan of {len(rows)} waypoints passed")
    waypoints = [(r[0], r[1]) for r in rows]
    _guarded(_do_pick, obj, waypoints[:3], rows[0][2])
    _guarded(_do_place, waypoints[3:])
    log("done")
    return xy


def _dry_run(name, to):
    seen = look()
    for o in seen:
        log(f"seen {o['colour']} {o['name']} at ({o['x']:.0f}, {o['y']:.0f}) top {o['top_mm']} "
            f"width {o['width_mm']} in {o['seen']}/{FRAMES} frames, spread {o['spread']} mm")
    obj = find(name, None, seen)
    log(f"picking {obj['colour']} {obj['name']} at ({obj['x']:.0f}, {obj['y']:.0f}) top {obj['top_mm']:.0f}")
    try:
        xy, rows = plan_move(obj, to, seen)
        log(f"place spot ({xy[0]:.0f}, {xy[1]:.0f})")
    except SkillError as e:
        log(f"no plan: {e}")
        return
    for n, pose, j, err in rows:
        print(f"  {n:12s} flange {[round(v, 1) for v in pose[:3]]}  joints {[round(v, 1) for v in j]}  "
              f"{'FAIL ' + err if err else 'ok'}")


if __name__ == "__main__":
    a = sys.argv[1:]
    to = None
    if "--to" in a:
        i = a.index("--to")
        to, a = (float(a[i + 1]), float(a[i + 2])), a[:i] + a[i + 3:]
    try:
        if a[:1] == ["plan"]:
            _dry_run(a[1] if len(a) > 1 else "cup", to)
        elif a[:1] == ["pick"]:
            pick(a[1] if len(a) > 1 else "cup")
        elif a[:1] == ["move"]:
            move_object(a[1] if len(a) > 1 else "cup", to=to)
        else:
            sys.exit(__doc__)
    except SkillError as e:
        sys.exit(f"refused: {e}")
    except motion.MotionError as e:
        sys.exit(f"motion failed: {e}")
    except KeyboardInterrupt:
        sys.exit("stopped")
