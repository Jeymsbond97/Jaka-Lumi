"""Offline pick / place sweep: seeded scenes all around Lumi (cups and tables left, ahead, right, beside it, near, far,
out of reach, table edges, a chair on the way), run through the real tasks/fetch.py and manipulation/skills.py code
(_pick_here, _put_down) with fakes at the hardware edge only. No robot, no network, no services.

    .venv/bin/python tests/pick_sweep.py --round 1 [--picks 1500] [--places 600] [--seed 1] [--jobs 12] [--cam 1]

Writes logs/pick_sweep_<round>.jsonl (one record per scene) and logs/pick_sweep_<round>.md (the report).

The fakes (a small simulator):
- arm: robot/kinematics.py answers kine_inverse / kine_forward; joint and straight moves set the joints at once.
  Any other controller command raises.
- base: a map pose; navigation arrives (+-2 cm, +-1 deg) unless the goal is within NAV_MARGIN_M of an obstacle, then
  it reports "succeeded" without moving (CLAUDE.md); joy_control drives straight on a virtual clock and stalls when
  driving forward would bring the base centre nearer an obstacle than BASE_HALF_M + the scene's stall gap (the base's
  own safety stop, live 2026-10-26 18:13). Obstacles: the table top and a chair as rectangles (clearance, probe).
- body: lift 0 (held there), waist and head as commanded. The waist turns the arm frame about the column
  (COLUMN_BASE_M, the head's turning centre); fetch's own model turns it about the base centre (finding, X1.md).
- torso camera: detections of the cup with a per-scene extrinsic error (rotation, depth scale) and frame noise;
  depth frames ray-cast from the true camera pose (table tops, the floor, the chair, the cup), read through the real
  skills.surface_points / flat_points / on_table / locate. The head camera is off.
- gripper: close() checks where the fingers came down on the true cup (along the fingers / across them, see LANDING)
  and knocks it over when a finger lands on it; open_() releases a held cup where the hand is.
The grasp offset carries the camera's error at the taught cup (grasp_teach.json was taught from a seen cup), so a
straight pick near the taught spot lands right and a turned one carries that error turned (fault (e)).
"""
import argparse
import collections
import json
import math
import multiprocessing as mp
import os
import random
import signal
import sys
import tempfile
import time as _time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ---------- fixed values (embedded so the sweep runs without the Thor-only calibration files) ----------
T_CAL = np.array([[0.999523, -0.014152, 0.027436, -257.663352],      # data/camera_extrinsics.json T_base_cam
                  [-0.02739, 0.003442, 0.999619, 13.72052],          # (2026-10-13, in use)
                  [-0.014242, -0.999894, 0.003053, -41.359237],
                  [0.0, 0.0, 0.0, 1.0]])
INTR = {"width": 1280, "height": 720, "fx": 608.3, "fy": 608.4, "cx": 636.9, "cy": 363.2, "dist": [0.0] * 5}
HEAD_CENTRE = np.array([-92.969, -19.868, 356.124])   # head_cam.head_centre() (mm, arm frame), 2026-10-19 fit
CALIB = {"arm_yaw_in_base_deg": -95.5, "waist_deg": -20.31, "arm_xy_in_base_m": [0.111, -0.109]}  # data/fetch_calib.json
WAIST_REF = CALIB["waist_deg"]
FLOOR_Z = -985.0              # mm, arm frame at lift 0 (the floor read -1060 at lift 75)
TABLE_THICK_MM = 30.0         # table top slab
LEG_IN_M, LEG_R_M = 0.05, 0.025   # table legs: this far in from the corners, this thick (radius)
HEAD_FOV_DEG = (35.0, 25.0)  # head camera: half field of view, horizontal / vertical (estimate)
HEAD_NOISE_MM = 8.0          # its detections' noise (calibrated 6 mm median)
NAV_MARGIN_M = 0.35           # navigation goal this near an obstacle: "succeeded" without moving (estimate)
DEPTH_RANGE_MM = (200.0, 4000.0)
DET_RANGE_MM = 3000.0         # the cup is detected up to this far from the camera
EDGE_PX = 10                  # ... with its centre this far inside the image
TEACH_CUP = np.array([-128.0, 628.0, -261.0 - 20.0])   # grasp_teach.json cup (centre at mid height ~ top - 20)
# finger landing (docs/10_GRIPPER.md §1, docs/gripper: open gaps belly 96, neck 73, tips 88 mm; neck and tips ~25 mm
# either side of the belly centre along the fingers): see fits(). The cup's diameter there = its grip width.
TIPS_GAP_MM = 88.0
BELLY_GAP_MM = 96.0
HOOK_LINES = ((-30.0, 73.0), (25.0, 88.0))   # (mm along the fingers from the belly centre, open gap): neck, tips.
# The neck at -30 (tape says ~25 +-5): at -25 most picks of the 85 mm tumbler (grip 81-89) would knock, live it was
# picked 10+ times without a turn.
CAM_ROT_SD_DEG = 0.4          # per-scene torso extrinsic rotation error, each axis (estimate from 3.3 mm at ~0.35 m)
CAM_SCALE_SD = 0.008          # per-scene depth scale error
CAM_NOISE_MM = 2.0            # per-frame noise of a detection's centre
ARM_XY_ERR_M = 0.03           # true arm base origin off the calibrated one by up to this (samples spread 6-19 cm in x)
ARM_YAW_ERR_DEG = 1.0
STALL_GAPS = (0.10, 0.25)     # m in front of the base where its own safety stop holds it (per scene)

EVENTS = ("no box for it", "the base went", "an obstacle", "plan refused", "straight move to carry",
          "turning my waist", "too near me", "asking to move it closer", "not turning", "driving round", "no way there",
          "not where it should be", "can't turn back", "going closer", "no table in view")   # log phrases counted
SECTORS = ("beside L", "left", "ahead", "right", "beside R")
RANGES = ((0, 450, "too near"), (450, 720, "comfortable"), (720, 900, "far edge"), (900, 99999, "out of reach"))


def sector(bearing):
    return "beside L" if bearing > 65 else "left" if bearing > 20 else "ahead" if bearing >= -20 else \
        "right" if bearing >= -65 else "beside R"


def dist_class(d):
    return next(n for lo, hi, n in RANGES if lo <= d < hi)


def rot2(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


COLUMN_BASE_M = np.asarray(CALIB["arm_xy_in_base_m"]) + rot2(CALIB["arm_yaw_in_base_deg"]) @ (HEAD_CENTRE[:2] / 1000)
# the waist's axis in the base frame (m): the head's turning centre (the waist and the head share the column, URDF)


def rpy(r, p, y):
    r, p, y = (math.radians(v) for v in (r, p, y))
    Rx = np.array([[1, 0, 0], [0, math.cos(r), -math.sin(r)], [0, math.sin(r), math.cos(r)]])
    Ry = np.array([[math.cos(p), 0, math.sin(p)], [0, 1, 0], [-math.sin(p), 0, math.cos(p)]])
    Rz = np.array([[math.cos(y), -math.sin(y), 0], [math.sin(y), math.cos(y), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


class Clock:
    """Virtual time for fetch / skills: time() moves on a little at every read, sleep() moves it on."""
    def __init__(self):
        self.t = 1.8e9

    def time(self):
        self.t += 0.001
        return self.t

    def sleep(self, s):
        self.t += max(0.0, s)

    def __getattr__(self, k):
        return getattr(_time, k)


CLOCK = Clock()
W = {}                         # the world of the scene running in this process
fetch = skills = kin = motion = None


# ---------- world geometry ----------
def arm_true():
    """(yaw deg, origin m) of the true arm base frame in the base frame at the waist now."""
    w = W["body"][1] - WAIST_REF
    col = W["col"]
    return W["yaw0"] + w, col + rot2(w) @ (W["xy0"] - col)


def world_to_arm(p):
    x, y, th = W["base"]
    yaw, org = arm_true()
    b = rot2(-math.degrees(th)) @ (np.asarray(p, float) - [x, y])
    return rot2(-yaw) @ (b - org) * 1000.0


def arm_to_world(a):
    x, y, th = W["base"]
    yaw, org = arm_true()
    return rot2(math.degrees(th)) @ (rot2(yaw) @ (np.asarray(a, float)[:2] / 1000.0) + org) + [x, y]


def rect_dist(p, r):
    """Distance (m) from map point p to rectangle r {c, half, ang} (0 inside)."""
    q = rot2(-r["ang"]) @ (np.asarray(p, float) - r["c"])
    d = np.maximum(np.abs(q) - r["half"], 0.0)
    return float(np.hypot(*d))


def legs(t):
    """Map points (m) of a table's four legs (LEG_IN_M in from its corners)."""
    hx, hy = t["half"][0] - LEG_IN_M, t["half"][1] - LEG_IN_M
    return [t["c"] + rot2(t["ang"]) @ [sx * hx, sy * hy] for sx in (-1, 1) for sy in (-1, 1)]


def clearance(x, y):
    """What the base's sensors and map give (agv.clearance): a table by its legs (the lidar sees under its top), a
    chair as a whole."""
    p = np.array([x, y])
    return min([float(np.linalg.norm(p - l)) - LEG_R_M for t in W["tables"] for l in legs(t)] +
               [rect_dist(p, b) for b in W["boxes"]] + [5.0])


def solid(x, y):
    """Distance (m) to the nearest table top or chair: what the base's own front camera stops at and navigation keeps
    its margin from."""
    return min([rect_dist((x, y), r) for r in W["tables"] + W["boxes"]] + [5.0])


# ---------- torso camera ----------
def cam_true():
    """True camera -> arm transform: the calibrated one with this scene's rotation error about the camera."""
    T = T_CAL.copy()
    T[:3, :3] = T_CAL[:3, :3] @ W["cam_err"]
    return T


def _pix_dirs(u, v):
    return np.stack([(u - INTR["cx"]) / INTR["fx"], (v - INTR["cy"]) / INTR["fy"], np.ones_like(u, float)], -1)


def render(u, v):
    """Depth (mm) at pixels (u, v) as the depth camera reports it: the first surface along each ray from the true
    camera pose, times the scene's depth scale; 0 where nothing is hit in range."""
    u, v = np.asarray(u, float), np.asarray(v, float)
    shape = u.shape
    d = _pix_dirs(u.ravel(), v.ravel())
    T = cam_true()
    o, D = T[:3, 3], d @ T[:3, :3].T                      # rays in the arm frame; parameter t = depth (cam z)
    best = np.full(len(D), np.inf)

    def take(t, ok):
        np.minimum(best, np.where(ok & (t > 0), t, np.inf), out=best)

    with np.errstate(divide="ignore", invalid="ignore"):
        t = (FLOOR_Z - o[2]) / D[:, 2]
        take(t, D[:, 2] < 0)
        for box in W["arm_boxes"]:                          # oriented boxes (table slabs, a chair) in the arm frame
            c, ax, half, z0, z1 = box
            rel_o = np.array([(o[:2] - c) @ ax[0], (o[:2] - c) @ ax[1], o[2]])
            rel_d = np.stack([D[:, :2] @ ax[0], D[:, :2] @ ax[1], D[:, 2]], -1)
            lo, hi = np.array([-half[0], -half[1], z0]), np.array([half[0], half[1], z1])
            t1, t2 = (lo - rel_o) / rel_d, (hi - rel_o) / rel_d
            tn, tf = np.nanmax(np.minimum(t1, t2), 1), np.nanmin(np.maximum(t1, t2), 1)
            take(tn, tn <= tf)
        cup = W.get("arm_cup")
        if cup is not None:
            (cx, cy), r, z0, z1 = cup
            px, py = o[0] - cx, o[1] - cy
            a = D[:, 0] ** 2 + D[:, 1] ** 2
            b = 2 * (px * D[:, 0] + py * D[:, 1])
            disc = b * b - 4 * a * (px * px + py * py - r * r)
            ts = (-b - np.sqrt(np.maximum(disc, 0))) / (2 * a)
            z = o[2] + ts * D[:, 2]
            take(ts, (disc >= 0) & (z >= z0) & (z <= z1))
            tt = (z1 - o[2]) / D[:, 2]
            hx, hy = o[0] + tt * D[:, 0] - cx, o[1] + tt * D[:, 1] - cy
            take(tt, hx * hx + hy * hy <= r * r)
    best = best * (1.0 + W["scale"])
    best[(best < DEPTH_RANGE_MM[0]) | (best > DEPTH_RANGE_MM[1])] = 0.0
    return best.reshape(shape)


class Depth:
    """A depth frame that is ray-cast only where the code reads it."""
    shape = (INTR["height"], INTR["width"])

    def __getitem__(self, key):
        if not isinstance(key, tuple):
            return np.zeros((0, self.shape[1]))
        a, b = key
        if isinstance(a, slice):
            vv, uu = np.meshgrid(np.arange(self.shape[0])[a], np.arange(self.shape[1])[b], indexing="ij")
        else:
            vv, uu = np.broadcast_arrays(np.asarray(a), np.asarray(b))
        return render(uu, vv)


def measured(p):
    """Where the camera code puts a true arm-frame point: through the true camera, depth scaled, back through T_CAL."""
    T = cam_true()
    pc = np.linalg.inv(T) @ np.append(p, 1.0)
    pc[:3] *= 1.0 + W["scale"]
    return (T_CAL @ pc)[:3]


def detections():
    cup = W.get("cup")
    if cup is None or W["in_hand"]:
        return []
    c = np.append(world_to_arm(cup["xy"]), (cup["top"] + cup["table"]) / 2)
    T = cam_true()
    pc = np.linalg.inv(T) @ np.append(c, 1.0)
    if pc[2] <= 0 or np.linalg.norm(pc[:3]) > DET_RANGE_MM:
        return []
    u, v = INTR["fx"] * pc[0] / pc[2] + INTR["cx"], INTR["fy"] * pc[1] / pc[2] + INTR["cy"]
    if not (EDGE_PX <= u < INTR["width"] - EDGE_PX and EDGE_PX <= v < INTR["height"] - EDGE_PX):
        return []
    m = measured(c) + np.append(W["rng"].normal(0, CAM_NOISE_MM, 2), 0.0)
    top = measured(np.array([c[0], c[1], cup["top"]]))[2]
    return [{"name": "cup", "colour": "white", "score": 0.9, "box": [0, 0, 1, 1],
             "position_mm": [float(m[0]), float(m[1]), float(m[2])], "top_mm": float(top),
             "width_mm": cup["grip"] - 8.0 + float(W["rng"].normal(0, 1.0)),
             "height_mm": cup["top"] - cup["table"] + float(W["rng"].normal(0, 2.0))}]


def head_T(yaw, pitch):
    """Head camera -> arm transform at head (yaw, pitch): at the head's centre, looking ahead (arm +y) turned by yaw
    (+ left) and tilted by pitch (+ up). Its depth frames are not simulated (camview.depth gives None)."""
    a, b = math.radians(yaw), math.radians(pitch)
    z = np.array([-math.sin(a) * math.cos(b), math.cos(a) * math.cos(b), math.sin(b)])   # optical axis
    x = np.array([math.cos(a), math.sin(a), 0.0])                                         # image right
    T = np.eye(4)
    T[:3, :3] = np.stack([x, np.cross(z, x), z], 1)
    T[:3, 3] = HEAD_CENTRE
    return T


def head_detections():
    """The cup as the head camera sees it (positions in the arm frame, HEAD_NOISE_MM), inside its field of view."""
    cup = W.get("cup")
    if cup is None or W["in_hand"]:
        return []
    c = np.append(world_to_arm(cup["xy"]), (cup["top"] + cup["table"]) / 2)
    pc = np.linalg.inv(head_T(*W["body"][2:])) @ np.append(c, 1.0)
    if pc[2] <= 0 or np.linalg.norm(pc[:3]) > DET_RANGE_MM or \
            abs(math.degrees(math.atan2(pc[0], pc[2]))) > HEAD_FOV_DEG[0] or \
            abs(math.degrees(math.atan2(pc[1], pc[2]))) > HEAD_FOV_DEG[1]:
        return []
    m = c + np.append(W["rng"].normal(0, HEAD_NOISE_MM, 2), 0.0)
    return [{"name": "cup", "colour": "white", "score": 0.9, "position_mm": [float(v) for v in m],
             "top_mm": float(cup["top"]), "width_mm": cup["grip"] - 8.0}]


def refresh():
    """The world in the arm frame now (after any base / waist change)."""
    yaw, org = arm_true()
    x, y, th = W["base"]
    boxes = []
    for r, z0, z1 in [(t, t["z"] - TABLE_THICK_MM, t["z"]) for t in W["tables"]] + \
                     [(b, FLOOR_Z, b["z"]) for b in W["boxes"]]:
        c = world_to_arm(r["c"])
        a = math.radians(r["ang"] - math.degrees(th) - yaw)
        ax = np.array([[math.cos(a), math.sin(a)], [-math.sin(a), math.cos(a)]])
        boxes.append((c, ax, np.array(r["half"]) * 1000.0, z0, z1))
    W["arm_boxes"] = boxes
    cup = W.get("cup")
    W["arm_cup"] = None if cup is None or W["in_hand"] else \
        (world_to_arm(cup["xy"]), cup["grip"] / 2.0, cup["table"], cup["top"])


# ---------- arm, gripper, landing ----------
def offset_true():
    """The grasp point's true offset in the flange frame: skills.GRASP_OFFSET was computed from a cup the camera saw,
    so it holds the camera's error at the taught cup."""
    R0 = rpy(*skills.GRASP_RPY)
    b_teach = measured(TEACH_CUP) - TEACH_CUP
    return skills.GRASP_OFFSET - R0.T @ b_teach


def hand_now():
    """(true grasp point mm, along-finger unit, across unit) of the hand at the joints now."""
    c = kin.pose(W["J"])
    R = rpy(*c[3:])
    g = np.array(c[:3]) + R @ W["off_true"]
    u = (R @ [0.0, 0.0, 1.0])[:2]
    u /= np.linalg.norm(u)
    return g, u, np.array([-u[1], u[0]])


def landing():
    """(along, across, ok) mm of the true cup axis from the true grasp point, in the fingers' directions."""
    g, u, a = hand_now()
    cup = W["cup"]
    d = world_to_arm(cup["xy"]) - g[:2]
    along, across = float(d @ u), float(d @ a)
    return along, across, fits(cup["grip"], along, across), float(g[2] - (cup["top"] - 40.0))


def fits(D, a, c):
    """A cup of diameter D (mm), its axis `a` along the fingers (+ to the tips) and `c` across from the belly centre,
    passes down between the open hooks: the belly (BELLY_GAP_MM) round it, and its chord at the neck and the tips lines
    (HOOK_LINES: mm along, gap) inside the gap there (P2's window, docs/gripper tape +-5 mm)."""
    r = D / 2.0
    if abs(c) > (BELLY_GAP_MM - D) / 2.0:
        return False
    return all(abs(l - a) >= r or 2.0 * math.sqrt(r * r - (l - a) ** 2) <= gap - 2.0 * abs(c) for l, gap in HOOK_LINES)


def f_close(wait=True):
    rec = W["rec"]
    if W.get("cup") is not None and not W["hand"]["holding"]:
        along, across, ok, dz = landing()
        rec.setdefault("landings", []).append([round(along, 1), round(across, 1), ok, round(dz, 1)])
        if ok:
            W["hand"].update(holding=True)
            W["in_hand"] = True
            W["held"] = {"h": W["cup"]["top"] - W["cup"]["table"], "below": skills.BELOW_RIM_MM}
        else:
            W["cup"] = None                        # a finger came down on it: knocked over
            rec["knocked"] = True
    W["hand"]["closed"] = True
    refresh()
    return g_state()


def f_open(wait=True):
    if W["hand"]["holding"]:
        g, _, _ = hand_now()
        held = W["held"]
        bottom = g[2] + held["below"] - held["h"]          # grasp point is `below` under its top
        xy = arm_to_world(g)
        on = [t for t in W["tables"] if rect_dist(xy, t) == 0.0]
        W["rec"]["released"] = {"xy": [round(float(v), 3) for v in xy],
                                "edge_m": round(min((-max(np.abs(rot2(-t["ang"]) @ (xy - t["c"])) - t["half"])
                                                     for t in on), default=-1.0), 3),
                                "above_table_mm": round(float(bottom - on[0]["z"]), 1) if on else None}
    W["hand"].update(holding=False, closed=False)
    refresh()
    return g_state()


def g_state():
    h = W["hand"]
    ai = 3500 if h["holding"] else 4150 if h["closed"] else 160
    return {"closed": h["closed"], "holding": h["holding"], "object_in_front": False, "ai": [ai], "di": [0],
            "do": [0, 0], "gap_mm": 80}


def f_move_path(moves, wait=True, queued=False):
    for t, _ in moves:
        motion.check(t)
        W["J"] = motion.nearest(list(t), W["J"])
    return list(W["J"])


def f_move_linear(target=None, delta=None, speed="slow", wait=True, path_checked=False):
    if target is None:
        p = kin.pose(W["J"])
        target = [p[i] + (delta[i] if i < len(delta) else 0.0) for i in range(3)] + p[3:]
    j = kin.ik(list(target), W["J"])
    if j is None:
        raise motion.MotionError(f"no IK solution for {[round(v, 1) for v in target]}")
    W["J"] = motion.nearest(j, W["J"])
    motion.check(W["J"])
    return list(target)


def f_arm_cmd(name, **a):
    if name in ("kine_inverse", "kine_forward"):
        return kin.ask(name, **a)
    raise AssertionError(f"real arm command in the sweep: {name}")


# ---------- base ----------
def f_pose():
    return tuple(float(v) for v in W["base"])


def _moved(kind, want, before):
    after = W["base"]
    W["rec"]["moves"].append([kind, round(float(want), 3),
                              round(float(math.hypot(after[0] - before[0], after[1] - before[1])), 3),
                              round(math.degrees((after[2] - before[2] + math.pi) % (2 * math.pi) - math.pi), 1)])


def f_go_point(x, y, th):
    before = W["base"].copy()
    target = np.array([x, y, th], float)
    ok = solid(x, y) >= NAV_MARGIN_M
    turn_only = math.hypot(x - before[0], y - before[1]) < 0.02
    if ok or turn_only:
        rng = W["rng"]
        err = np.array([rng.normal(0, 0.01), rng.normal(0, 0.01), rng.normal(0, math.radians(0.5))])
        W["base"] = target + (err if not turn_only else [0, 0, err[2]])
    W["nav"] = {"polls": 0}
    _moved("turn" if turn_only else "nav", math.degrees((th - before[2] + math.pi) % (2 * math.pi) - math.pi)
           if turn_only else math.hypot(x - before[0], y - before[1]), before)
    refresh()
    return True, "OK"


def f_status():
    nav = W.get("nav")
    if nav is not None:
        nav["polls"] += 1
        st = "running" if nav["polls"] == 1 else "succeeded"
        if st == "succeeded":
            W["nav"] = None
    else:
        st = "succeeded"
    x, y, th = W["base"]
    return {"move_status": st, "charge_state": False, "current_pose": {"x": x, "y": y, "theta": th}}


def f_request(cmd, timeout=3.0):
    if "joy_control" not in cmd:
        return {}
    v = float(cmd.split("linear_velocity=")[1].split("&")[0])
    now = CLOCK.t
    joy = W["joy"]
    if joy["v"]:                                    # the last command drove until now (at most JOY_HOLD_S)
        dist = joy["v"] * min(now - joy["t"], fetch.JOY_HOLD_S)
        x, y, th = W["base"]
        step = math.copysign(0.005, dist)
        n = int(abs(dist) / 0.005)
        for _ in range(n):
            nx, ny = x + step * math.cos(th), y + step * math.sin(th)
            if step > 0 and solid(nx, ny) < fetch.BASE_HALF_M + W["stall_gap"]:
                break                               # the base's own safety stop
            x, y = nx, ny
        W["base"] = np.array([x, y, th])
        joy["want"] += dist
        refresh()
    if v == 0.0 and joy["v"]:
        _moved("straight", joy["want"], joy["start"])
        joy.update(want=0.0)
    if v != 0.0 and not joy["v"]:
        joy["start"] = W["base"].copy()
    joy.update(v=v, t=now)
    return {}


# ---------- install the fakes (once per process) ----------
def install():
    global fetch, skills, kin, motion
    from robot import agv, arm, gripper, head, kinematics, motion as mo
    from vision import camview, head_cam, objects
    from manipulation import arm_route, skills as sk
    from tasks import fetch as fe
    fetch, skills, kin, motion = fe, sk, kinematics, mo
    forbid = lambda *a, **k: (_ for _ in ()).throw(AssertionError(f"hardware call in the sweep: {a}"))
    agv._ask = head._call = gripper._out = forbid
    arm.cmd = f_arm_cmd
    tmp = Path(tempfile.mkdtemp(prefix="pick_sweep_"))
    fe.STATE_FILE, fe.KNOWN_FILE, fe.CALIB_FILE = tmp / "task.json", tmp / "known.json", tmp / "calib.json"
    fe._write = lambda: None
    fe.time = sk.time = CLOCK
    fe.DRIVE_POLL_S = fe.GIVE_POLL_S = 0.0
    fe.ASK_EVERY_S = 0.0
    sk.FRESH_WAIT_S = 0.0                       # look() keeps its frame gaps: on the virtual clock
    sk.fresh = lambda path, camera, after=0.0: CLOCK.time()
    lines = []
    W["lines"] = lines
    fe.log = sk.log = arm_route.log = lambda *a: lines.append(" ".join(str(x) for x in a))
    sk._ask = kinematics.ask
    agv.pose, agv.status, agv.go_point, agv.request = f_pose, f_status, f_go_point, f_request
    agv.turn_by = lambda a: f_go_point(W["base"][0], W["base"][1], (W["base"][2] + a + math.pi) % (2 * math.pi) - math.pi)
    agv.cancel = lambda: W.update(nav=None)
    agv.clearance = clearance
    agv.probe = lambda x, y: (clearance(x, y), float("inf"))
    agv.markers = lambda: []
    agv.go = forbid
    head.status = lambda: list(W["body"])
    head.moveto = lambda pos, **k: (W["body"].__setitem__(slice(None), [max(0.0, min(head.LIFT_MAX_MM, pos[0])),
                                                                         *pos[1:]]), refresh(), {})[-1]
    gripper.state, gripper.close, gripper.open_ = g_state, f_close, f_open
    mo.joints = lambda: list(W["J"])
    mo.tcp = lambda: kinematics.pose(W["J"])
    mo.move_path, mo.move_linear = f_move_path, f_move_linear
    mo.stop = lambda: {}
    camview.want = lambda name: None
    camview.depth = lambda name, max_age=None: Depth() if name == "torso" else None
    camview.intrinsics = lambda name: dict(INTR) if name == "torso" else None
    objects.base_from_camera = lambda: T_CAL
    objects.latest = lambda camera="torso": {"age_s": 0.0, "objects": detections(), "head_pose": None} \
        if camera == "torso" else {"age_s": 0.0, "objects": head_detections(), "head_pose": list(W["body"])}
    head_cam.head_centre = lambda: HEAD_CENTRE.copy()
    head_cam.base_from_head = head_T


# ---------- scenes ----------
def _table_round(cup_xy, n, rng, depth, width, gap, along):
    """Rectangle with its near edge (facing the robot along n) `gap` m before the cup, the cup `along` m sideways."""
    c = cup_xy + n * (depth / 2 - gap) + np.array([-n[1], n[0]]) * along
    return {"c": c, "half": (depth / 2, width / 2), "ang": math.degrees(math.atan2(n[1], n[0]))}


def make_pick(i, seed):
    rng = random.Random(seed * 100003 + i)
    col = COLUMN_BASE_M
    for _ in range(200):
        bearing = rng.uniform(-110, 110)
        dist = rng.uniform(300, 1600)
        n = np.array([math.cos(math.radians(bearing)), math.sin(math.radians(bearing))])
        cup = col + n * dist / 1000.0
        kind = rng.choices(("table", "stand", "table+chair"), (0.6, 0.2, 0.2))[0]
        if kind == "stand":
            depth = width = 0.35
            gap, along = rng.uniform(0.08, 0.17), rng.uniform(-0.08, 0.08)
        else:
            depth, width = rng.uniform(0.5, 0.9), rng.uniform(0.6, 1.4)
            gap, along = rng.uniform(0.04, 0.30), rng.uniform(-width / 2 + 0.1, width / 2 - 0.1)
        nn = cup / max(np.linalg.norm(cup), 1e-6)            # the table faces the base centre
        table = _table_round(cup, nn, rng, depth, width, gap, along)
        top = rng.uniform(-330, -180)
        h = rng.uniform(90, 130)
        table["z"] = top - h
        table["half"] = tuple(table["half"])
        boxes = []
        if kind == "table+chair":
            edge = cup - nn * gap
            ch = edge - nn * rng.uniform(0.25, 0.45) + np.array([-nn[1], nn[0]]) * rng.uniform(-0.15, 0.15)
            boxes.append({"c": ch, "half": (0.22, 0.22), "ang": rng.uniform(0, 90), "z": table["z"] - 260})
        W["tables"], W["boxes"] = [table], boxes
        if solid(0, 0) >= 0.29:
            break
    return {"kind": "pick", "i": i, "seed": seed, "variant": kind, "bearing": round(bearing, 1),
            "dist_mm": round(dist), "cup": {"xy": [float(v) for v in cup], "top": round(top, 1),
                                           "table": round(top - h, 1), "grip": round(rng.uniform(61, 92), 1)},
            "tables": [{**table, "c": [float(v) for v in table["c"]]}],
            "boxes": [{**b, "c": [float(v) for v in b["c"]]} for b in boxes],
            "stall_gap": rng.choice(STALL_GAPS), "err_seed": rng.randrange(1 << 30)}


def pick_at(x, y, top, grip=80.0, gap=0.10, height=110.0, variant="table", stall_gap=0.10, err_seed=0, chair=None):
    """A fixed pick scene: the cup seen at (x, y) mm in the arm frame (waist at the front, calibrated arm base) with its
    top at `top`, on a 0.7 x 1.0 m table whose near edge faces the base centre `gap` m before the cup."""
    yaw, org = CALIB["arm_yaw_in_base_deg"], np.asarray(CALIB["arm_xy_in_base_m"])
    cup = rot2(yaw) @ (np.array([x, y]) / 1000.0) + org
    nn = cup / np.linalg.norm(cup)
    table = _table_round(cup, nn, None, 0.7, 1.0, gap, 0.0)
    table.update(z=top - height, half=[0.35, 0.5], c=[float(v) for v in table["c"]])
    rel = cup - COLUMN_BASE_M
    boxes = [] if chair is None else [{"c": [float(v) for v in cup - nn * (gap + chair)], "half": [0.22, 0.22],
                                       "ang": 0.0, "z": table["z"] - 260}]
    return {"kind": "pick", "i": 0, "seed": 0, "variant": variant,
            "bearing": round(math.degrees(math.atan2(rel[1], rel[0])), 1), "dist_mm": round(1000 * np.linalg.norm(rel)),
            "cup": {"xy": [float(v) for v in cup], "top": top, "table": top - height, "grip": grip},
            "tables": [table], "boxes": boxes, "stall_gap": stall_gap, "err_seed": err_seed}


def make_place(i, seed):
    rng = random.Random(seed * 200003 + i)
    for _ in range(200):
        bearing = rng.uniform(-180, 180)
        near = rng.uniform(0.32, 2.4)                        # m from the base centre to the table's near edge
        n = np.array([math.cos(math.radians(bearing)), math.sin(math.radians(bearing))])
        depth, width = rng.uniform(0.5, 0.9), rng.uniform(0.6, 1.4)
        along = rng.uniform(-width / 2 + 0.2, width / 2 - 0.2)
        table = {"c": n * (near + depth / 2) + np.array([-n[1], n[0]]) * along, "half": (depth / 2, width / 2),
                 "ang": bearing, "z": rng.uniform(-460, -300)}
        W["tables"], W["boxes"] = [table], []
        if solid(0, 0) >= 0.29:
            break
    h = rng.uniform(90, 130)
    other = None
    if rng.random() < 0.25:                                  # another cup already on it, near its front edge
        other = [float(v) for v in table["c"] - n * (depth / 2 - 0.12)]
    return {"kind": "place", "i": i, "seed": seed, "bearing": round(bearing, 1), "dist_mm": round(near * 1000),
            "variant": "table" + ("+cup" if other else ""),
            "held": {"grip": round(rng.uniform(72, 92), 1), "h": round(h, 1), "table0": -403.0 + 75.0},
            "tables": [{**table, "c": [float(v) for v in table["c"]]}], "boxes": [], "other": other,
            "stall_gap": rng.choice(STALL_GAPS), "err_seed": rng.randrange(1 << 30)}


def setup(sc, cam=1.0):
    nr = np.random.default_rng(sc["err_seed"])
    lines = W.get("lines", [])
    lines.clear()
    W.update(lines=lines, in_hand=False, base=np.zeros(3), body=[0.0, WAIST_REF, 0.0, -5.0], nav=None,
             joy={"v": 0.0, "t": 0.0, "want": 0.0, "start": np.zeros(3)},
             J=list(motion.poses()["look"]), hand={"holding": False, "closed": False}, rng=nr,
             tables=[{**t, "c": np.array(t["c"]), "half": np.array(t["half"])} for t in sc["tables"]],
             boxes=[{**b, "c": np.array(b["c"]), "half": np.array(b["half"])} for b in sc["boxes"]],
             stall_gap=sc["stall_gap"], col=COLUMN_BASE_M, rec={"moves": []})
    e = nr.normal(0, CAM_ROT_SD_DEG * cam, 3)
    W.update(cam_err=rpy(*e), scale=float(nr.normal(0, CAM_SCALE_SD * cam)),
             yaw0=CALIB["arm_yaw_in_base_deg"] + (float(nr.uniform(-1, 1)) * ARM_YAW_ERR_DEG if cam else 0.0),
             xy0=np.asarray(CALIB["arm_xy_in_base_m"]) + (nr.uniform(-1, 1, 2) * ARM_XY_ERR_M if cam else 0.0))
    W["off_true"] = offset_true()
    fetch.CALIB_FILE.write_text(json.dumps(CALIB))
    fetch._stop.clear()
    fetch._pause.clear()
    fetch.stay_put = False
    fetch._state.update(status="running", holding=False, held_object=None, log=[])
    fetch._rolling.update(v=0.0, t=0.0, sent=0.0)
    skills._held.clear()
    if sc["kind"] == "pick":
        c = sc["cup"]
        W["cup"] = {"xy": np.array(c["xy"]), "top": c["top"], "table": c["table"], "grip": c["grip"]}
    else:
        hd = sc["held"]
        W["cup"] = None
        W["held"] = {"h": hd["h"], "below": skills.BELOW_RIM_MM}
        W["hand"].update(holding=True, closed=True)
        top0 = hd["table0"] + hd["h"]
        skills._held.update(top_mm=top0, x=-100.0, y=600.0, yaw=0.0, table=hd["table0"], tips=False,
                            below=skills.BELOW_RIM_MM, base=(5.0, 5.0, 0.0), waist=0.0, lift=0.0,
                            what={"object": "cup", "colour": "white"})
        fetch._state.update(holding=True, held_object={"object": "cup", "colour": "white"})
        if sc.get("other"):                                   # a standing cup the camera sees on the table
            W["cup"] = {"xy": np.array(sc["other"]), "top": sc["tables"][0]["z"] + 100.0,
                        "table": sc["tables"][0]["z"], "grip": 80.0}
    refresh()


WAIST_TRIES = (0, 15, -15, 30, -30, 45, -45, 60, -60)   # deg, waist turns the physical check allows
GOALS = ((-100, 580), (-100, 640), (-100, 700), (0, 600), (-200, 620), (100, 600), (-160, 520))   # mm, arm frame


def way_exists(sc):
    """A stand for the base from which the arm reaches the cup (grasp turns up to skills.TRUSTED_YAW_DEG, from look,
    the waist turned by one of WAIST_TRIES), the cup's middle in the torso camera's view there: one of GOALS
    where skills plans a pick at the cup's height, with the base centre BASE_HALF_M + the stall gap clear of every
    table top and chair, facing any way (5 deg steps). The physical check behind "out of reach after every way"."""
    c = sc["cup"]
    setup(sc, 0.0)
    W["cup"] = None
    refresh()
    cup = np.array(c["xy"])
    for g in GOALS:
        obj = {"name": "cup", "colour": "white", "x": float(g[0]), "y": float(g[1]), "top_mm": c["top"],
               "width_mm": max(c["grip"], 72.0) - 8.0, "height_mm": c["top"] - c["table"], "seen": 8, "spread": 1.0}
        pc = np.linalg.inv(T_CAL) @ [g[0], g[1], (c["top"] + c["table"]) / 2, 1.0]   # seen there by the torso camera?
        u, v = INTR["fx"] * pc[0] / pc[2] + INTR["cx"], INTR["fy"] * pc[1] / pc[2] + INTR["cy"]
        if not (EDGE_PX <= u < INTR["width"] - EDGE_PX and EDGE_PX <= v < INTR["height"] - EDGE_PX):
            continue
        kw = {"max_yaw": skills.TRUSTED_YAW_DEG} if hasattr(skills, "TRUSTED_YAW_DEG") else {}
        try:
            if not skills.reachable_pick(obj, start=list(motion.poses()["look"]), **kw):
                continue
        except skills.SkillError:
            continue
        xy0 = np.asarray(CALIB["arm_xy_in_base_m"])
        for w in WAIST_TRIES:                               # the waist turned w: the arm frame about the column
            v = rot2(CALIB["arm_yaw_in_base_deg"] + w) @ (np.array(g) / 1000.0) + \
                COLUMN_BASE_M + rot2(w) @ (xy0 - COLUMN_BASE_M)
            for phi in range(0, 360, 5):
                p = cup - rot2(phi) @ v
                if solid(*p) >= 0.255 + sc["stall_gap"]:
                    return [g[0], g[1], phi, w]
    return None


def _alarm(*a):
    raise TimeoutError("scene took too long")


def run_scene(sc, cam=1.0):
    """One scene through fetch; the record of what happened."""
    setup(sc, cam)
    rec = W["rec"]
    t0 = _time.time()
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(600)
    try:
        if sc["kind"] == "pick":
            fetch._pick_here({"object": "cup", "colour": None}, None)
            rec["result"] = "ok" if W["hand"]["holding"] else "not holding"
        else:
            fetch._put_down(None)
            rel = rec.get("released")
            rec["result"] = "ok" if rel and rel["edge_m"] >= 0.0 else "released off a table" if rel else "not released"
    except fetch.Stopped:
        rec["result"] = "stopped"
    except (fetch.FetchError, skills.SkillError) as e:
        rec["result"] = "refused"
        rec["why"] = str(e.args[0]) if e.args else type(e).__name__
    except TimeoutError:
        rec["result"] = "timeout"
    except Exception as e:                                     # a bug in the code under test (or in the sim)
        tb = traceback.extract_tb(e.__traceback__)[-1]
        rec["result"] = "exception"
        rec["why"] = f"{type(e).__name__}: {e} at {Path(tb.filename).name}:{tb.lineno}"
    finally:
        signal.alarm(0)
    lines = W["lines"]
    grasp = [l for l in lines if l.startswith("grasp ")]
    rec["grasp"] = grasp[-1] if grasp else None
    rec["waist_end"] = round(W["body"][1] - WAIST_REF, 1)
    rec["log_tail"] = lines[-12:]
    rec["events"] = {k: n for k in EVENTS if (n := sum(k in l for l in lines))}
    rec["n_ik_refusals"] = sum("plan refused" in l for l in lines)
    rec["secs"] = round(_time.time() - t0, 1)
    if sc["kind"] == "pick" and rec["result"] == "ok":
        rec["held_at"] = [round(v, 3) for v in arm_to_world(hand_now()[0])]
    mv = [m for m in rec["moves"]]
    rec["base_moves"] = len(mv)
    rec["still"] = sum(1 for m in mv if m[2] < 0.02 and abs(m[3]) < 2.0)
    rec["repeats"] = sum(1 for a, b in zip(mv, mv[1:]) if a[0] == b[0] and abs(a[1] - b[1]) < 0.02
                         and a[2] < 0.02 and abs(a[3]) < 2.0)
    if sc["kind"] == "pick" and rec["result"] != "ok" and sc["cup"]["grip"] >= 72.0:
        lines_kept = list(W["lines"])
        try:
            rec["way"] = way_exists(sc)
        except Exception as e:
            rec["way"] = f"oracle failed: {e}"
        W["lines"][:] = lines_kept
    out = {k: v for k, v in sc.items() if k not in ("tables", "boxes")}
    out["tables"], out["boxes"] = sc["tables"], sc["boxes"]
    return {**out, **rec}


def _work(args):
    sc, cam = args
    return run_scene(sc, cam)


def _init():
    install()
    signal.signal(signal.SIGINT, signal.SIG_IGN)


# ---------- report ----------
def parse_grasp(g):
    """(turn deg, J5) from skills' "grasp in the hooks, turned -30 deg, wrist J5 +24" line."""
    if not g:
        return None, None
    turn = int(g.split("turned ")[1].split(" ")[0]) if "turned" in g else 0
    j5 = int(g.split("J5 ")[1])
    return turn, j5


def why_class(r):
    c = _why_class(r)
    if "way" in r and "physical" not in c and "wider" not in c:
        c += " [no stand sees and reaches it (turn <= 15, lift 0): physical]" if r["way"] is None else " [a stand exists]"
    return c


def _why_class(r):
    if r["result"] == "ok":
        return "ok"
    if r["kind"] == "pick" and r["cup"]["grip"] < 72.0:
        return "cup too small (physical)" + ("" if "too small" in (r.get("why") or "") else ", but tried")
    if r.get("knocked"):
        if r["cup"]["grip"] > TIPS_GAP_MM:
            return "knocked over: cup wider than ~88 mm (its chord does not pass the hooks' neck)"
        return "knocked over (finger landed on the cup)"
    w = r.get("why") or r["result"]
    for key, name in (("too small", "cup too small (physical)"), ("too big", "cup too big (physical)"),
                      ("too thin", "cup too thin (physical)"), ("can't see", "not seen"),
                      ("looked all around", "not seen"), ("still can't reach", "out of reach after every way"),
                      ("way to get close", "no way to get close"), ("not answering", "controller not answering"),
                      ("free place", "no free place found"), ("safely", "arm move refused (not safe)"),
                      ("too close to me", "too near, can't back off"), ("spilling", "arm move refused (spill)")):
        if key in w:
            return name
    return f"{r['result']}: {w[:70]}"


def report(rows, path, title, mtimes):
    picks = [r for r in rows if r["kind"] == "pick"]
    places = [r for r in rows if r["kind"] == "place"]
    out = [f"# {title}", "", f"Written {_time.strftime('%Y-%m-%d %H:%M')}. Code under test (mtime): " +
           ", ".join(f"{k} {v}" for k, v in mtimes.items()), ""]

    def table(rs, rows_key, cols, label):
        out.append(f"| {label} | " + " | ".join(cols) + " | all |")
        out.append("|---" * (len(cols) + 2) + "|")
        for rk in rows_key:
            cells = []
            for c in cols + ["all"]:
                sel = [r for r in rs if r["_s"] == rk and (c == "all" or r["_d"] == c)]
                cells.append(f"{100 * sum(r['result'] == 'ok' for r in sel) / len(sel):.0f}% ({len(sel)})" if sel else "-")
            out.append(f"| {rk} | " + " | ".join(cells) + " |")
        sel = rs
        out.append("| all | " + " | ".join(
            (lambda s: f"{100 * sum(r['result'] == 'ok' for r in s) / len(s):.0f}% ({len(s)})" if s else "-")
            ([r for r in sel if c == "all" or r["_d"] == c]) for c in cols + ["all"]) + " |")
        out.append("")

    for r in picks:
        r["_s"], r["_d"] = sector(r["bearing"]), dist_class(r["dist_mm"])
    for r in places:
        b = r["bearing"]
        r["_s"] = "behind" if abs(b) > 110 else sector(b)
        r["_d"] = "in reach" if r["dist_mm"] < 450 else "near (< 1 m)" if r["dist_mm"] < 1000 else "far"
    if picks:
        ok = sum(r["result"] == "ok" for r in picks)
        out += [f"## Picks: {ok}/{len(picks)} ok ({100 * ok / len(picks):.1f} %)", "",
                "Success by sector (bearing of the cup from the column, + left) and distance from the column (mm):", ""]
        table(picks, SECTORS, [n for _, _, n in RANGES], "sector")
        sized = [r for r in picks if r["cup"]["grip"] >= 72]
        if sized:
            out.append("Cups 72-92 mm only (thinner ones are refused: MIN_WIDTH):")
            out.append("")
            table(sized, SECTORS, [n for _, _, n in RANGES], "sector")
        ok_rows = [r for r in picks if r["result"] == "ok" or r.get("landings")]
        turns = collections.defaultdict(list)
        for r in ok_rows:
            t, j5 = parse_grasp(r.get("grasp"))
            if t is None:
                continue
            land = (r.get("landings") or [[None]])[-1]
            turns[("no turn" if t == 0 else f"turn {abs(t)}" + (" L" if t > 0 else " R"))].append((r, land))
        out += ["## Grasps (pick plans that reached the cup)", "",
                "| grasp | n | waist turned | finger landings off (along / across, mm, median of abs) | knocked |",
                "|---|---|---|---|---|"]
        for k in sorted(turns, key=lambda k: (k != "no turn", k)):
            v = turns[k]
            lands = [l for _, l in v if l and l[0] is not None]
            med = (f"{np.median([abs(l[0]) for l in lands]):.1f} / {np.median([abs(l[1]) for l in lands]):.1f}"
                   if lands else "-")
            out.append(f"| {k} | {len(v)} | {sum(abs(r['waist_end']) >= 3 for r, _ in v)} | {med} | "
                       f"{sum(1 for l in lands if not l[2])} |")
        out.append("")
        mv = [r for r in picks]
        out += ["## Base behaviour (picks)", "",
                f"- scenes with a base move: {sum(r['base_moves'] > 0 for r in mv)}; moves in all: "
                f"{sum(r['base_moves'] for r in mv)}",
                f"- moves that went nowhere (< 2 cm, < 2 deg): {sum(r['still'] for r in mv)} in "
                f"{sum(r['still'] > 0 for r in mv)} scenes",
                f"- the same move repeated after one that went nowhere: {sum(r['repeats'] for r in mv)} in "
                f"{sum(r['repeats'] > 0 for r in mv)} scenes", ""]
    if places:
        ok = sum(r["result"] == "ok" for r in places)
        out += [f"## Places: {ok}/{len(places)} ok ({100 * ok / len(places):.1f} %)", "",
                "By the table's bearing and the distance of its near edge from the base centre:", ""]
        table(places, ("beside L", "left", "ahead", "right", "beside R", "behind"),
              ["in reach", "near (< 1 m)", "far"], "sector")
        out += [f"- moves that went nowhere: {sum(r['still'] for r in places)} in "
                f"{sum(r['still'] > 0 for r in places)} scenes; repeated: {sum(r['repeats'] for r in places)}", ""]
        rel = [r["released"] for r in places if r.get("released") and r["released"]["above_table_mm"] is not None]
        if rel:
            hz = [x["above_table_mm"] for x in rel]
            out += [f"- put down: cup bottom above the table median {np.median(hz):.0f} mm (min {min(hz):.0f}, "
                    f"max {max(hz):.0f}); centre from the table edge median {1000 * np.median([x['edge_m'] for x in rel]):.0f} mm",
                    ""]
    out += ["## By table height (mm, arm frame at lift 0)", "", "| table top | picks ok (72-92 mm cups) | places ok |",
            "|---|---|---|"]
    for lo, hi in ((-480, -420), (-420, -380), (-380, -340), (-340, -260)):
        pk = [r for r in picks if lo <= r["cup"]["table"] < hi and r["cup"]["grip"] >= 72]
        pl = [r for r in places if lo <= r["tables"][0]["z"] < hi]
        pct = lambda rs: f"{100 * sum(r['result'] == 'ok' for r in rs) / len(rs):.0f}% ({len(rs)})" if rs else "-"
        out.append(f"| {lo} .. {hi} | {pct(pk)} | {pct(pl)} |")
    out += ["", "## Failure classes", ""]
    for kind, rs in (("pick", picks), ("place", places)):
        cls = collections.defaultdict(list)
        for r in rs:
            c = why_class(r)
            if c != "ok":
                cls[c].append(r)
        for c, v in sorted(cls.items(), key=lambda kv: -len(kv[1])):
            out.append(f"### {kind}: {c} — {len(v)}")
            for r in v[:3]:
                cup = r.get("cup") or r.get("held")
                out.append(f"- scene {r['i']} (seed {r['seed']}, {r['variant']}): bearing {r['bearing']:+.0f}, "
                           f"{r['dist_mm']} mm, {json.dumps(cup)}, stall gap {r['stall_gap']}, moves "
                           f"{r['moves']}, grasp {r.get('grasp')}, landings {r.get('landings')}")
                out.append(f"  - log: {' | '.join(r['log_tail'][-5:])}")
            out.append("")
    Path(path).write_text("\n".join(out) + "\n")


def mtimes():
    return {f: _time.strftime("%H:%M", _time.localtime((ROOT / f).stat().st_mtime))
            for f in ("tasks/fetch.py", "manipulation/skills.py", "manipulation/arm_route.py", "robot/kinematics.py")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="1")
    ap.add_argument("--picks", type=int, default=1500)
    ap.add_argument("--places", type=int, default=600)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--cam", type=float, default=1.0, help="camera error times this (0: none)")
    ap.add_argument("--only", default=None, help="comma list of pick:i / place:i to run (debug)")
    ap.add_argument("--report", action="store_true", help="only write the .md again from the round's .jsonl")
    a = ap.parse_args()
    if a.report:
        jl = ROOT / "logs" / f"pick_sweep_{a.round}.jsonl"
        rows = sorted((json.loads(l) for l in open(jl)), key=lambda r: (r["kind"], r["i"]))
        report(rows, jl.with_suffix(".md"), f"Pick / place sweep, round {a.round} (seed {a.seed})", mtimes())
        return
    scenes = [make_pick(i, a.seed) for i in range(a.picks)] + [make_place(i, a.seed) for i in range(a.places)]
    if a.only:
        want = {tuple(s.split(":")) for s in a.only.split(",")}
        scenes = [s for s in scenes if (s["kind"], str(s["i"])) in want]
    for s in scenes:                                       # numpy -> plain values for the records
        for t in s["tables"] + s["boxes"]:
            t["half"] = [float(v) for v in t["half"]]
    logs = ROOT / "logs"
    jl, md = logs / f"pick_sweep_{a.round}.jsonl", logs / f"pick_sweep_{a.round}.md"
    stamp = mtimes()
    rows = []
    t0 = _time.time()
    with mp.get_context("fork").Pool(a.jobs, initializer=_init) as pool, open(jl, "w") as f:
        for k, r in enumerate(pool.imap_unordered(_work, [(s, a.cam) for s in scenes], chunksize=2)):
            rows.append(r)
            f.write(json.dumps(r, default=float) + "\n")
            if (k + 1) % 100 == 0:
                print(f"{k + 1}/{len(scenes)} {(_time.time() - t0) / 60:.1f} min", flush=True)
    rows.sort(key=lambda r: (r["kind"], r["i"]))
    report(rows, md, f"Pick / place sweep, round {a.round} (seed {a.seed}, camera error x{a.cam:g})",
           stamp)
    print(md)


if __name__ == "__main__":
    main()
