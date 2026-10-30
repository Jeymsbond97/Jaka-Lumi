"""Pick and place with the torso camera, the arm and the gripper: find an object, plan every pose, check it with
the controller's IK, then move. Nothing moves unless the whole plan (pick and place) passes.

The grasp is the one taught in grasp_teach.json: the flange orientation with the fingers around a cup, and the
point between the fingers where the cup's axis sits 4 cm below the rim. Down from 10 cm above, close, lift.

    python manipulation/skills.py plan [cup] [--to X Y]     # dry run: object, place spot, every waypoint with IK joints
    python manipulation/skills.py pick cup                  # pick it up and hold it 3 cm above the table
    python manipulation/skills.py move cup [--to X Y]       # pick it up and put it down at X Y (mm, base frame) or a free spot
    python manipulation/skills.py hover cup [TURN]          # live check: the open hooks 6 cm over the cup's rim, grasp
                                                            # turned TURN deg; Enter goes back
    python manipulation/skills.py offset T1 DX1 DY1 T2 DX2 DY2 [...]   # hover readings -> the grasp point's error

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
from robot import kinematics
from robot import motion
from vision import objects

ROOT = Path(__file__).resolve().parents[1]      # the project folder
TEACH = json.loads((ROOT / "data" / "grasp_teach.json").read_text())
GRASP_RPY = TEACH["flange"][3:]                  # deg, flange orientation with the fingers around a cup
GRASP_OFFSET = np.array(TEACH["tcp_offset_flange"])   # mm, cup axis 4 cm below the rim, in the flange frame
FINGER_DIR = calib.rpy_matrix(*GRASP_RPY).T @ [0.0, 0.0, -1.0]   # straight down in the taught grasp, flange frame:
                                                 # the hand's lowest part is checked TIP_MM along it
TIPS_TEACH = json.loads((ROOT / "data" / "grasp_tips_teach.json").read_text())
TIPS_OFFSET = np.array(TIPS_TEACH["tips_offset_flange"])   # mm, flange frame: a thing held between the finger tips
                                                 # has its axis this far from the grasp point (the hooks' belly
                                                 # centre), almost along the flange z axis: the fingers lie level, the
                                                 # hook ring goes down over the thing (taught on a 66 mm can 2026-10-22)
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
TIP_MM = 60.0                                    # the hand's lowest part this far below the grasp point (estimate, kept
                                                 # as a margin: the fingers lie level; the taught tips grasp had the
                                                 # grasp point 113 mm above the table, owner's tape: finger plane 135)
BELOW_RIM_MM = 40.0                              # grasp this far below the object's top
ABOVE_MM = 100.0                                 # approach / retreat height over the grasp pose
LIFT_MM = 30.0                                   # first lift after closing, then check the grip again
MAX_TILT_DEG = 15.0                              # deg; a held cup's axis may lean this far from vertical on a joint
                                                 # move with it (place_options; tasks/fetch.py uses the same)
PLACE_EXTRA_MM = 3.0                             # put down this much higher than it was picked (same table)
MIN_WIDTH, MAX_WIDTH = 70.0, 97.0                # mm: the cup's top goes through the open hooks' ring (tips 100 open,
                                                 # owner's measure) and the belly closes round it. MAX_WIDTH: the
                                                 # owner's margin 3; wider tops are taken from the side (side()). The
                                                 # tips grasp (61-72) missed twice live on a
                                                 # 66 mm can (2026-10-22): off by the owner until it is checked; 61
                                                 # brings it back
SEEN_UNDER_MM = 8.0                              # the camera's width is this much under the width the fingers meet
                                                 # (2026-10-19: 73 seen / 85 by tape, 81 seen / 85 by AI_1); the
                                                 # limits here are the fingers', compared with grip_width()
BELLY_MIN_MM = 70.0                              # thinner is held between the finger tips: the belly closes only to 68
                                                 # (a 70 mm steel cup was missed there and knocked over, 2026-10-19)
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
TABLE_XY_MM = 20.0                               # ... and the sight line aimed at that height meets it this near the
                                                 # point (X1's sweep: a spot 17 mm off the near edge passed, it fell)
TABLE_NEAR_RING_MM = 25.0                        # a ring point on the near side the camera can't see (below its view
                                                 # at table height) is checked this far from the centre instead
LOCATE_MM = 90.0                                 # locate(): looked for this far around where an object was last seen,
LOCATE_STEP_MM = 15.0                            # ... on a grid this fine
LOCATE_MIN_HITS = 4                              # ... with at least this many depth points above half its height
HAND_PROBE_MM = (30.0, 50.0, 70.0)               # hand_sees(): points this far below the grasp point, on the cup's axis
HAND_NEAR_MM = 60.0                              # ... depth no further than this behind one = something in the hand
HAND_FAR_MM = 250.0                              # ... depth further than this behind one = nothing there (the room)
NEAR_FRACTION = 0.7                              # depth nearer than this part of the expected one: something in front
                                                 # of the sight line (the gripper, the held cup), not the surface
FLAT_DEG = 12.0                                  # flat_points(): the depth around a sight line's pixel must lie on a
FLAT_PATCH = (3, 3)                              # plane leaning less than this (a table top, a seat, the floor; not a
                                                 # chair's back, a table's edge, a person); the patch: 7 x 7 pixels 3 px
                                                 # apart (px step, half width). Live 2026-10-20: of 2850 sight lines
                                                 # 283 were level, the table among them as one clear height
FLAT_MIN_FRACTION = 0.7                          # ... at least this part of the patch must have depth
TABLE_MIN_POINTS = 6                             # a table height needs this many level points within TABLE_TOL_MM
FRAME_LAG_S = 0.15                               # s; a frame written this long after a move ended was taken after it
FRESH_WAIT_S = 2.0                               # s; at most this long waiting for such a frame (depth: every 0.5 s)
FRESH_POLL_S = 0.02
TIP_CLEAR_MM = 10.0                              # round things: the finger tips (TIP_MM below the grasp point, an
                                                 # unmeasured estimate) stop at least this far above what it stands on
ROUND_BITE_MM = 10.0                             # ... and the grasp point must stay at least this far below its top
                                                 # (estimate; neither tried live)
BELOW_SHOULDER_MM = 80.0                         # bottles: grasp this far below where the body begins (objects.body):
                                                 # the owner's taught tips grasp of a spray can, at its middle (2026-10-22,
                                                 # grasp_tips_teach.json); the hand's lowest part (TIP_MM below) must
                                                 # stay TIP_CLEAR_MM above the table (else its lowest point seen)
SIDE_MAX_WIDTH = 97.0                            # mm; side grasp (a cup whose top is wider than MAX_WIDTH): the width the
                                                 # fingers meet (seen + SIDE_SEEN_MM) where the hooks go in from the
                                                 # side, under the open tips' 100 mm (owner's measure) with a margin 3
SIDE_SEEN_MM = 0.0                               # ... the camera's width of a cup's lower part is not under like its rim:
                                                 # an 84 mm rim cup read 73-77 where the tape gave 71 (45 mm up) and
                                                 # AI_1 74 (60 mm up, 2026-10-29)
SIDE_AT = 0.42                                   # ... grasp this share of the cup's height above the table, or the
                                                 # nearest height that fits (owner's free-drive side grasps of a 142 mm
                                                 # cup: 54-67 mm up; picked live at 60)
SIDE_TOP_MM = 5.0                                # ... the hooks' top this far under the rim at least
SIDE_BAND_MM = 12.0                              # ... that width holds from this far below to this far above the grasp
                                                 # point (the hooks are ~16 mm thick: owner's photos, about +-5 mm)
HOOK_BELOW_MM = 8.0                              # ... the hand's lowest part this far below the grasp point when it
                                                 # comes in from the side (half the hooks' thickness; estimate from the
                                                 # photos), kept TIP_CLEAR_MM above the table
SIDE_CLEAR_MM = 40.0                             # ... the hand comes down this far from the cup's top edge (before the
                                                 # tips), then goes in straight along the tips' direction
UPRIGHT, ROUND, BODY = "upright", "round", "body"   # how the cup fingers take a thing (GRASPS)
# Why a thing can't be picked, (English, Korean); {en} / {ko} = its name, {topic} = 은 / 는
FRAGILE = ("I won't take the {en}: my hand closes too hard and it could break.", "{ko}{topic} 깨질 수 있어서 잡지 않을게요.")
THIN = ("The {en} is too thin or flat for my fingers: they hold round things 6 to 9 cm wide.",
        "{ko}{topic} 너무 얇거나 납작해서 제 손가락으로 잡을 수 없어요.")
SHALLOW = ("The {en} is too wide and shallow for my fingers.", "{ko}{topic} 너무 넓고 얕아서 잡을 수 없어요.")
SOFT = ("The {en} is too soft: my hand would squeeze it flat.", "{ko}{topic} 너무 물렁해서 제 손이 눌러 버려요.")
BIG = ("The {en} is too big for my hand.", "{ko}{topic} 제 손에 너무 커요.")
SMALL = ("The {en} is too small for me to hold.", "{ko}{topic} 너무 작아서 잡을 수 없어요.")
NO_BODY = ("I can't see the {en}'s body well enough to hold it.", "{ko}의 몸통이 잘 보이지 않아서 잡을 수 없어요.")
WIDE = ("The {en} is too wide for my hand, also lower down.", "{ko}{topic} 아래쪽도 제 손에 너무 커요.")
SHORT_BODY = ("The {en}'s body is too short for my fingers: they would hit the table.",
              "{ko}{topic} 몸통이 짧아서 제 손가락이 테이블에 닿아요.")
GRASPS = {                                       # COCO class -> (Korean name, UPRIGHT / ROUND / why not) (docs/15 §10)
    "cup": ("컵", UPRIGHT),                      # the taught grasp 40 mm below the top; proven on cups 84-85 mm
    "apple": ("사과", ROUND), "orange": ("오렌지", ROUND), "sports ball": ("공", ROUND),   # at the equator: not live yet
    "bottle": ("병", BODY),                      # by the body below the neck (objects.body): not live yet
    "wine glass": ("와인잔", FRAGILE), "vase": ("꽃병", FRAGILE),    # level 1 is still ~90 N (docs/10)
    "bowl": ("그릇", SHALLOW),                   # a steel bowl was missed / knocked over (2026-10-19)
    "banana": ("바나나", THIN), "carrot": ("당근", THIN), "cell phone": ("휴대폰", THIN), "remote": ("리모컨", THIN),
    "book": ("책", THIN), "mouse": ("마우스", THIN), "scissors": ("가위", THIN), "toothbrush": ("칫솔", THIN),
    "fork": ("포크", THIN), "knife": ("칼", THIN), "spoon": ("숟가락", THIN),   # under the tips' closed 59 mm, or
                                                 # lower than the tips reach below the grasp point
    "sandwich": ("샌드위치", SOFT), "cake": ("케이크", SOFT), "donut": ("도넛", SOFT), "hot dog": ("핫도그", SOFT),
    "pizza": ("피자", SOFT), "broccoli": ("브로콜리", SOFT), "teddy bear": ("곰인형", SOFT),   # paper cups: crushed
    "laptop": ("노트북", BIG), "keyboard": ("키보드", BIG), "potted plant": ("화분", BIG), "clock": ("시계", BIG),
    "handbag": ("핸드백", BIG), "backpack": ("가방", BIG), "umbrella": ("우산", BIG), "suitcase": ("여행가방", BIG),
    "hair drier": ("드라이기", BIG), "toaster": ("토스터", BIG),   # over the tips' open 88 mm, or over the payload
}
IK_SEEDS = ("ready", "look", "carry", "give")   # taught poses whose arm configurations (and wrist flips) seed the
                                                 # pick / place IK: the controller answers the solution nearest the
                                                 # seed, so one seed alone misses cups another configuration reaches
WRIST_MIN_DEG = 10.0                             # deg; |J5| at least this at above, grasp and lift (estimate: the
                                                 # proven picks had J5 +20; near 0 J4 / J6 swing round)
TRUSTED_YAW_DEG = 15.0                           # deg; grasp turns from -this to 0 picked live (-10, -15: 3 of 3); -30
                                                 # and -45 missed 4 of 4 (2026-10-26, a finger end on the rim); +15
                                                 # missed 2 of 2 (2026-10-27, a finger on the cup, DI_1 set; never hover-
                                                 # checked). The taught grasp point's horizontal error turns with the
                                                 # grasp: a waist turn or a base move comes before another turn
COMFORT_R_MM = 710.0                             # mm, cup's horizontal distance from the arm base origin: picks proven
                                                 # up to here (furthest live success (-68, 703)); further, the base moves
                                                 # in first when it can (tasks/fetch.py). Estimate until measured live
CARRY_UP_MM = (100.0, 200.0)                     # holding the cup: when the straight line to carry is refused (a joint
                                                 # jumps: carry has the elbow almost straight), straight up this much
                                                 # first, then one checked joint move to carry (carry_up)
HOVER_MM = 60.0                                  # hover(): the grasp point this far over the top (the fingers lie level
                                                 # near its height, owner's tape on the tips grasp; TIP_MM is a margin)
LINE_STEPS = 10                                  # ... that straight up is checked at this many points (line_joints)
LINE_POINTS = 20                                 # points checked on a longer straight line with the cup (line_joints)
LINE_STEP_DEG = 25.0                             # ... no joint turning more than this between two of them
OFFLINE_KINE = True                              # kine_forward / kine_inverse answered by robot/kinematics.py (fitted
                                                 # to the controller, < 0.5 mm): a plan asks hundreds, and the controller
                                                 # drops its connection under such bursts (2026-10-26 18:46). The
                                                 # controller confirms only the chosen plan (confirm)
CONFIRM_MM = 2.0                                 # mm; the controller's forward kinematics of planned joints within this
CONFIRM_DEG = 2.0                                # deg; its inverse kinematics within this of the offline answer
RETRIES = 4                                      # the controller now and then answers with nothing: ask again,
RETRY_S = 0.2                                    # waiting this long, twice as long each time (it drops connections)
OPEN_AI = gripper.CLOSED_AI                      # AI_1 below this after opening = released
BACK_OUT_NEAR_MM = 30.0                          # back_out: the hand this near the stopped pick's way in is still in it

_held = {}                                       # what pick() holds: {"top_mm", "x", "y"} for place() / put_down()
_pick_way = {}                                   # the pick's waypoints {name: pose} from the move to above until the
                                                 # hand holds or has backed out (back_out after a stop)
_cancel = threading.Event()                      # set by cancel(): the running skill makes no further move
LOG = collections.deque(maxlen=40)               # last log lines, shown by the API
moved_at = {}                                    # camera -> time its last move (lift, waist, base, head) ended:
                                                 # frames written before that are not used (moved())


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
def moved(*cameras, after=0.0):
    """A move of `cameras` (default: both; the lift, the waist and the base carry both) ended now (+ `after` s, e.g. the
    base coasting): depth and detections are read from frames taken after it (fresh)."""
    for c in cameras or ("torso", "head"):
        moved_at[c] = time.time() + after


def fresh(path, camera, after=0.0):
    """Wait until the camera service has written `path` (a detection or depth file of `camera`) FRAME_LAG_S after the
    camera's last move and after `after`, at most FRESH_WAIT_S. The file's time, or None when there is none."""
    t = max(moved_at.get(camera, 0.0) + FRAME_LAG_S, after)
    end = time.time() + FRESH_WAIT_S
    while True:
        try:
            m = path.stat().st_mtime
        except OSError:
            m = None
        if (m is not None and m >= t) or time.time() >= end:
            return m
        time.sleep(FRESH_POLL_S)


def look(frames=FRAMES, ignore=IGNORE):
    """Detections over several frames, grouped by position: [{name, colour, x, y, top_mm, width_mm, height_mm, seen,
    spread, names}] (names: every class any frame gave the thing there; the cameras' labels flip)
    with medians of the detections that agree with the majority name; classes in `ignore` left out. Raises when the
    camera is not live."""
    camview.want(objects.CAMERA)
    fresh(camview.det_path(objects.CAMERA), objects.CAMERA)
    groups, live = [], 0
    intr, T = camview.intrinsics(objects.CAMERA), objects.base_from_camera()
    for i in range(frames):
        d = objects.latest()
        depth = camview.depth(objects.CAMERA) if any(GRASPS.get(o["name"], (None, None))[1] in (BODY, UPRIGHT)
                                                     for o in d["objects"]) else None
        if d["age_s"] is not None and d["age_s"] < objects.STALE_S:
            live += 1
            for o in d["objects"]:
                if o["name"] in ignore or not o.get("position_mm"):
                    continue
                x, y = o["position_mm"][:2]
                g = next((g for g in groups if np.hypot(x - g[0]["x"], y - g[0]["y"]) < CLUSTER_MM), None)
                row = {"name": o["name"], "colour": o.get("colour"), "x": x, "y": y, "top_mm": o.get("top_mm"),
                       "width_mm": o.get("width_mm"), "height_mm": o.get("height_mm")}
                if GRASPS.get(o["name"], (None, None))[1] == BODY and depth is not None:
                    row.update(objects.body(depth, o["box"], intr, T) or {})
                if GRASPS.get(o["name"], (None, None))[1] == UPRIGHT and depth is not None:
                    row["profile"] = objects.profile(depth, o["box"], intr, T)
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
        med = {k: statistics.median(r[k] for r in rows if r.get(k) is not None)
               if any(r.get(k) is not None for r in rows) else None
               for k in ("x", "y", "top_mm", "width_mm", "height_mm", "shoulder_mm", "body_mm", "low_mm")}
        spread = max(np.hypot(r["x"] - med["x"], r["y"] - med["y"]) for r in rows)
        out.append({"name": name, "colour": statistics.mode(r["colour"] for r in rows), **med, "seen": len(rows),
                    "spread": round(float(spread), 1), "names": sorted({r["name"] for r in g})})   # every label there
        profiles = [r["profile"] for r in rows if r.get("profile")]
        if profiles:                                  # an upright thing's widths down its height (side_height)
            n = min(len(p[0]) for p in profiles)
            out[-1]["profile"] = [(statistics.median(p[0][i][0] for p in profiles),
                                   statistics.median(p[0][i][1] for p in profiles)) for i in range(n)]
            out[-1]["low_mm"] = statistics.median(p[1] for p in profiles)
        if med["shoulder_mm"] is not None:            # a bottle: the table under it (its bottom is often out of view)
            out[-1]["table_mm"] = table_near(out[-1])
    return sorted(out, key=lambda o: np.hypot(o["x"], o["y"]))


def find(name="cup", colour=None, seen=None):
    """The nearest stable `name` (of `colour`) the torso camera sees, from look() (or `seen`, its result)."""
    seen = look() if seen is None else seen
    what = f"{colour + ' ' if colour else ''}{name}"
    hits = [o for o in seen if o["name"] == name and objects.same_colour(colour, o["colour"])]
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


def flange_for(x, y, z, yaw=0.0, tips=False):
    """Flange pose that puts the taught grasp point (`tips`: the point between the finger tips, TIPS_OFFSET from it)
    at (x, y, z) mm, the taught orientation turned by `yaw` deg about the vertical."""
    if not yaw:
        R, rpy = calib.rpy_matrix(*GRASP_RPY), list(GRASP_RPY)
    else:
        R = _rz(yaw) @ calib.rpy_matrix(*GRASP_RPY)
        rpy = rpy_of(R)
    f = np.array([x, y, z]) - R @ (GRASP_OFFSET + (TIPS_OFFSET if tips else 0.0))
    return [float(v) for v in f] + rpy


def yaw_of(pose):
    """How far (deg) a flange pose is turned about the vertical from the taught grasp."""
    D = calib.rpy_matrix(*pose[3:]) @ calib.rpy_matrix(*GRASP_RPY).T
    return math.degrees(math.atan2(D[1, 0], D[0, 0]))


def up(pose, dz):
    return [pose[0], pose[1], pose[2] + dz] + list(pose[3:])


def grip_width(obj):
    """mm the fingers will meet: the camera's width (a bottle's: its body's) plus SEEN_UNDER_MM (None when not
    measured). A 66 mm spray can's body read 58-60 (2026-10-22)."""
    w = obj.get("body_mm") if obj.get("body_mm") is not None else obj.get("width_mm")
    return None if w is None else w + SEEN_UNDER_MM


def reason(why, name):
    """(English, Korean) of a reason (NO_BODY, BIG, ...) about a `name`."""
    ko = GRASPS.get(name, ("그건", None))[0]
    topic = "은" if "가" <= ko[-1] <= "힣" and (ord(ko[-1]) - 0xAC00) % 28 else "는"
    return why[0].format(en=name), why[1].format(ko=ko, topic=topic)


def refusal(name):
    """(English, Korean) reason why the cup fingers can't pick a `name` (GRASPS), None when they can."""
    how = GRASPS.get(name, (None, None))[1]
    if how in (UPRIGHT, ROUND, BODY):
        return None
    return reason(how or ("I can't pick up a {en}.", "{ko} 잡을 수 없어요."), name)


def grasp_height(obj):
    """z (mm) of the grasp point for `obj`: BELOW_RIM_MM under the top of an upright thing (the proven cup grasp); the
    equator of a round one (a ball is as tall as it is wide), raised until the finger tips stay TIP_CLEAR_MM above
    what it stands on. SkillError when that leaves less than ROUND_BITE_MM of it above the grasp point. A bottle:
    BELOW_SHOULDER_MM under where its body begins, refused when the hand's lowest part (TIP_MM below) would come
    nearer than TIP_CLEAR_MM to the table under it (table_mm), or when that was not measured, to its lowest point
    seen."""
    how = GRASPS.get(obj["name"], (None, UPRIGHT))[1]
    if how == BODY:
        if obj.get("shoulder_mm") is None or obj.get("low_mm") is None:
            raise SkillError(*reason(NO_BODY, obj["name"]))
        z = obj["shoulder_mm"] - BELOW_SHOULDER_MM
        floor = obj["low_mm"] if obj.get("table_mm") is None else obj["table_mm"]
        if z - TIP_MM < floor + TIP_CLEAR_MM:
            raise SkillError(*reason(SHORT_BODY, obj["name"]))
        return z
    if how != ROUND:
        if how == UPRIGHT and side(obj):
            z = side_height(obj)
            if z is None:
                raise SkillError(*reason(WIDE, obj["name"]))
            return z
        return obj["top_mm"] - BELOW_RIM_MM
    tall = obj.get("height_mm") or grip_width(obj)
    bottom = obj["top_mm"] - tall
    z = max(bottom + tall / 2, bottom + TIP_MM + TIP_CLEAR_MM)
    if z > obj["top_mm"] - ROUND_BITE_MM:
        raise SkillError(f"The {obj['name']} is too low for my fingers: they would hit the table.")
    return z


def side(obj):
    """True when an upright `obj` is too wide at the top for the hooks to come down over it: the side grasp."""
    w = grip_width(obj)
    return w is not None and w > MAX_WIDTH and GRASPS.get(obj["name"], (None, None))[1] == UPRIGHT


def side_height(obj):
    """z (mm) of the grasp point for a side grasp: the height nearest SIDE_AT of the cup's height where the width the
    fingers meet (profile + SIDE_SEEN_MM) is within MIN_WIDTH..SIDE_MAX_WIDTH from SIDE_BAND_MM below to SIDE_BAND_MM
    above it, the hand's lowest part (HOOK_BELOW_MM under it) stays TIP_CLEAR_MM above what it stands on and the
    hooks' top SIDE_TOP_MM under the rim. None when no height fits."""
    slices = obj.get("profile") or []
    floor = obj.get("table_mm") if obj.get("table_mm") is not None else table_z(obj)
    if floor is None:
        floor = obj.get("low_mm")
    if not slices or floor is None:
        return None
    lo, hi = floor + TIP_CLEAR_MM + HOOK_BELOW_MM, obj["top_mm"] - SIDE_TOP_MM - HOOK_BELOW_MM
    want = floor + SIDE_AT * (obj["top_mm"] - floor)
    mids = [(t - objects.SLICE_MM / 2, w + SIDE_SEEN_MM) for t, w in slices]
    fits = [z for z, _ in mids if lo <= z <= hi and
            all(MIN_WIDTH <= w <= SIDE_MAX_WIDTH for m, w in mids if abs(m - z) <= SIDE_BAND_MM)]
    return min(fits, key=lambda z: abs(z - want)) if fits else None


def tips_dir(yaw=0.0):
    """Unit (x, y) in the arm frame the finger tips point to (away from the gripper body), the grasp turned `yaw`."""
    d = (_rz(yaw) @ calib.rpy_matrix(*GRASP_RPY) @ TIPS_OFFSET)[:2]
    return d / np.linalg.norm(d)


def side_back(obj):
    """mm the hand comes down this far from the grasp, against the tips' direction, for a side grasp of `obj`."""
    return grip_width(obj) / 2 + float(np.linalg.norm(TIPS_OFFSET)) + SIDE_CLEAR_MM


def back_off(pose, mm):
    """Flange pose moved `mm` horizontally against the finger tips' direction (out of a side grasp)."""
    d = tips_dir(yaw_of(pose)) * mm
    return [pose[0] - d[0], pose[1] - d[1]] + list(pose[2:])


def plan_pick(obj, yaw=0.0):
    """Waypoints [(name, flange pose)] to pick `obj` (a find() result): above, grasp, lift; a side grasp (side()) has
    "side" before the grasp, the hand at the grasp height beside the cup, and comes down there. Refuses things the
    fingers can't take (refusal) and objects of the wrong width or height."""
    no = refusal(obj["name"])
    if no:
        raise SkillError(*no)
    w = grip_width(obj)
    if w is None or (w > MAX_WIDTH and not side(obj)):
        raise SkillError(*reason(BIG, obj["name"]))
    if w < MIN_WIDTH:
        raise SkillError(*reason(SMALL, obj["name"]))
    z = grasp_height(obj)
    grasp = flange_for(obj["x"], obj["y"], z, yaw, tips=w < BELLY_MIN_MM)
    if side(obj):
        start = back_off(grasp, side_back(obj))
        return [("above", up(start, clear_above(obj["top_mm"] - z))), ("side", start), ("grasp", grasp),
                ("lift", up(grasp, LIFT_MM))]
    return [("above", up(grasp, clear_above(obj["top_mm"] - z))), ("grasp", grasp), ("lift", up(grasp, LIFT_MM))]


def clear_above(below):
    """How far above the grasp pose the hand comes down from and goes back up to, the object's top `below` mm over
    the grasp point: ABOVE_MM, more when the finger tips would still be beside it (a bottle's neck)."""
    return max(ABOVE_MM, below + TIP_MM)


def plan_place(x, y, top_mm, start=None, yaw=0.0, tips=None, below=None, back=None):
    """Waypoints to put down what was picked with its top at `top_mm`, centred at (x, y), the grasp turned by `yaw`.
    `start`: the flange pose it is held at now (adds the lift to carry height there). `tips`: held between the tips,
    `below`: the grasp point this far under its top, `back`: held from the side, the open hand backs out this far
    before it goes up (default: as pick() holds it)."""
    tips = _held.get("tips", False) if tips is None else tips
    below = _held.get("below", BELOW_RIM_MM) if below is None else below
    back = _held.get("back", 0.0) if back is None else back
    down = up(flange_for(x, y, top_mm - below, yaw, tips), PLACE_EXTRA_MM)
    steps = [("carry", [start[0], start[1], down[2] - PLACE_EXTRA_MM + ABOVE_MM] + list(start[3:]))] if start else []
    out = back_off(down, back) if back else down
    return steps + [("above place", up(down, ABOVE_MM)), ("place", down)] + \
        ([("release back", out)] if back else []) + [("release up", up(out, clear_above(below)))]


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
    fresh(camview.depth_path(camera), camera)
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


def flat_points(points_xy, guess_z=-400.0, camera=objects.CAMERA, T=None):
    """Like surface_points (also (x, y, z) given whole), but only where the camera sees a level surface (a table top, a seat, the floor): the depth
    pixels around the sight line's pixel (FLAT_PATCH) lie on a plane leaning less than FLAT_DEG. (x, y, z) mm, arm base
    frame, is the middle of that patch; None where it is not level (a chair's back, a table's edge, a person), out of
    view or without depth."""
    fresh(camview.depth_path(camera), camera)
    d, intr = camview.depth(camera), camview.intrinsics(camera)
    T = objects.base_from_camera() if T is None else T
    if d is None or intr is None or T is None or not len(points_xy):
        return [None] * len(points_xy)
    K = np.array([[intr["fx"], 0, intr["cx"]], [0, intr["fy"], intr["cy"]], [0, 0, 1]])
    dist, Ti = np.array(intr["dist"]), np.linalg.inv(T)
    P = np.array([[p[0], p[1], p[2] if len(p) > 2 else guess_z] for p in points_xy], float)
    cam = (Ti[:3, :3] @ P.T + Ti[:3, 3:4]).T
    uv = np.round(cv2.projectPoints(cam, np.zeros(3), np.zeros(3), K, dist)[0].reshape(-1, 2)).astype(int)
    step, half = FLAT_PATCH
    off = np.array([(a, b) for a in range(-half, half + 1) for b in range(-half, half + 1)]) * step
    px = uv[:, None, :] + off[None]
    inside = (px[..., 0] >= 0) & (px[..., 0] < d.shape[1]) & (px[..., 1] >= 0) & (px[..., 1] < d.shape[0])
    px = np.clip(px, 0, [d.shape[1] - 1, d.shape[0] - 1])
    z = np.where(inside, d[px[..., 1], px[..., 0]], 0).astype(float)
    n = cv2.undistortPoints(px.reshape(-1, 1, 2).astype(np.float64), K, dist).reshape(px.shape)
    Q = np.stack([n[..., 0] * z, n[..., 1] * z, z], axis=-1) @ T[:3, :3].T + T[:3, 3]
    level, out = math.cos(math.radians(FLAT_DEG)), []
    for q, zz, ahead in zip(Q, z, cam[:, 2]):
        q = q[zz > 0]
        if ahead <= 0 or len(q) < FLAT_MIN_FRACTION * len(off):       # behind the camera, or too little depth
            out.append(None)
            continue
        c = q.mean(axis=0)
        normal = np.linalg.svd(q - c)[2][2]
        out.append(tuple(float(v) for v in c) if abs(normal[2]) >= level else None)
    return out


def flat_top(points_xy, band, guess_z=-400.0, camera=objects.CAMERA, T=None):
    """(height mm, [(x, y, z)]) of the level surface most of `points_xy`'s sight lines meet within `band` (low, high):
    the largest group of flat_points within TABLE_TOL_MM of one height (as many: the higher), the median of it; None
    when fewer than TABLE_MIN_POINTS agree. A chair's back or seat next to the table, its edge, the floor and the held
    cup don't pull it off (live 2026-10-20 the median of every sight line read one table at -324 ... -555 mm)."""
    hits = [q for q in flat_points(points_xy, guess_z, camera, T) if q is not None and band[0] <= q[2] <= band[1]]
    if len(hits) < TABLE_MIN_POINTS:
        return None
    zs = np.array([q[2] for q in hits])
    agree = np.abs(zs[:, None] - zs[None, :]) <= TABLE_TOL_MM
    best = agree[int(np.argmax(agree.sum(axis=1) + zs * 1e-6))]
    if best.sum() < TABLE_MIN_POINTS:
        return None
    group = [q for q, a in zip(hits, best) if a]
    return float(np.median([q[2] for q in group])), group


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
    In the look taught 2026-10-20 the place is above the camera's view ("unknown": AI_1 decides); in the look before it
    (pixel (558, 259), 264 mm away) an empty hand read "empty" and a held cup gave no depth ("unknown"). The gripper's AI_1 alone can be wrong: a cup pulled out of the closed fingers left it at 162 ("open")."""
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
    """The (x, y) spots where the torso depth camera sees level table (flat_points): the centre and TABLE_RING_MM
    around it, each within TABLE_TOL_MM of `table_mm` (None: of each other). Points the camera can't see count as not table, but one on the
    near side (y below the centre's) is checked again at TABLE_NEAR_RING_MM: the camera sees a table only from
    y ~640 on, where the arm hardly reaches past y 700."""
    angles = np.linspace(0, 2 * math.pi, 8, endpoint=False)
    ring = [(0.0, 0.0)] + [(TABLE_RING_MM * math.cos(a), TABLE_RING_MM * math.sin(a)) for a in angles]
    inner = [(0.0, 0.0)] + [(TABLE_NEAR_RING_MM * math.cos(a), TABLE_NEAR_RING_MM * math.sin(a)) for a in angles]
    guess = table_mm if table_mm is not None else -400.0     # only to find the pixels; the depth decides

    def heights(pts):                     # z of the level surface at each point: the sight line aimed again at the
        first = flat_points(pts, guess)      # height it met must meet it at the point itself (a line just past the
        aim = [(p[0], p[1], q[2]) for p, q in zip(pts, first) if q is not None]   # near edge meets the top further
        second = dict(zip([a[:2] for a in aim], flat_points(aim) if aim else []))   # on, or the edge's face)
        out = []
        for p, q in zip(pts, first):
            r = None if q is None else second[(p[0], p[1])]
            out.append(None if r is None or math.hypot(r[0] - p[0], r[1] - p[1]) > TABLE_XY_MM else r[2])
        return out

    out = []
    for x, y in spots_xy:
        zs = heights([(x + dx, y + dy) for dx, dy in ring])
        again = [i for i, z in enumerate(zs) if z is None and ring[i][1] < -1e-6]
        if again:
            for i, z in zip(again, heights([(x + inner[i][0], y + inner[i][1]) for i in again])):
                zs[i] = z
        if None in zs:
            continue
        ref = table_mm if table_mm is not None else statistics.median(zs)
        if max(abs(z - ref) for z in zs) <= TABLE_TOL_MM:
            out.append((x, y))
    return out


# ---------- checking with the controller ----------
def _offline():
    """Plans use the offline kinematics: OFFLINE_KINE and the real controller behind arm.cmd (a test's stand-in arm
    answers its own kinematics)."""
    return OFFLINE_KINE and arm.cmd is _ARM_CMD


def _ask(name, controller=False, **args):
    """arm.cmd with retries for empty answers / dropped connections; kine_forward / kine_inverse offline (_offline)
    unless `controller`."""
    if not controller and name in ("kine_forward", "kine_inverse") and _offline():
        return kinematics.ask(name, **args)
    for i in range(RETRIES):
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
        time.sleep(RETRY_S * 2 ** i)
    raise SkillError("The arm controller is not answering.")


def confirm(waypoints, ja):
    """The controller agrees with an offline plan (waypoints from `ja`, the joints at the first one): its forward
    kinematics of `ja` is the first pose (CONFIRM_MM) and its inverse kinematics of the next one from `ja` is the
    offline answer (CONFIRM_DEG: the same arm configuration). Two asks. True without asking for a plan made by a
    stand-in (a test's _ask or arm)."""
    if not _offline() or _ask is not _ASK:
        return True
    c = _ask("kine_forward", controller=True, jointPosition=[float(v) for v in ja])["cartPosition"]
    if np.linalg.norm(np.subtract(c[:3], waypoints[0][1][:3])) > CONFIRM_MM:
        log(f"the controller puts {[round(v) for v in c[:3]]} for the plan's {[round(v) for v in waypoints[0][1][:3]]}")
        return False
    r = _ask("kine_inverse", controller=True, jointPosition=[float(v) for v in ja], cartPosition=list(waypoints[1][1]))
    mine = _ask("kine_inverse", jointPosition=[float(v) for v in ja], cartPosition=list(waypoints[1][1]))
    if r["errorCode"] != "0" or mine["errorCode"] != "0" or \
            max(abs(a - b) for a, b in zip(motion.nearest(r["jointPosition"], mine["jointPosition"]),
                                           mine["jointPosition"])) > CONFIRM_DEG:
        log(f"the controller's IK of {waypoints[1][0]} differs from the plan's")
        return False
    return True


_ASK, _ARM_CMD = _ask, arm.cmd


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
        j = motion.nearest(r["jointPosition"], ref)    # J1 / J4 / J6 +-360: the same pose, nearest the last one
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


def above_joints(pose, start=None, seeds=IK_SEEDS):
    """Joint solutions for the approach pose `pose`: from the arm configuration of each `seeds` pose (`ready` first,
    where the picks were proven) and from it with the wrist flipped. Each is within the joint limits and a joint move
    from `start` (default: here) that move_joints accepts (no joint further than motion.MAX_TRAVEL); no duplicates."""
    start = _joints() if start is None else start
    taught = motion.poses()
    out = []
    for name in seeds:
        if name not in taught:
            continue
        seed = motion.nearest(taught[name], start)
        for s in (seed, wrist_flip(seed)):
            j = _solve(pose, s, start)
            if j is not None and all(max(abs(a - b) for a, b in zip(o, j)) > 1.0 for o in out):
                out.append(j)
    return out


def _solve(pose, seed, start):
    """IK of `pose` from `seed`, J1 / J4 / J6 nearest `start`; None when there is none, it is out of the joint limits
    or the joint move from `start` turns a joint further than motion.MAX_TRAVEL."""
    r = _ask("kine_inverse", jointPosition=[float(v) for v in seed], cartPosition=list(pose))
    if r["errorCode"] != "0":
        return None
    j = motion.nearest(r["jointPosition"], start)
    try:
        motion.check(j)
    except motion.MotionError:
        return None
    return j if max(abs(a - b) for a, b in zip(j, start)) <= motion.MAX_TRAVEL else None


def path_heights(j0, j1):
    """Lowest z (mm) of flange, grasp point and finger tips at PATH_POINTS points of the joint move j0 -> j1."""
    j0, j1, out = np.array(j0), np.array(motion.nearest(j1, list(j0))), []
    for k in range(PATH_POINTS):
        c = _ask("kine_forward", jointPosition=[float(v) for v in j0 + (j1 - j0) * k / (PATH_POINTS - 1)])["cartPosition"]
        R, f = calib.rpy_matrix(*c[3:]), np.array(c[:3])
        g = f + R @ GRASP_OFFSET
        out.append(float(min(f[2], g[2], (g + R @ (TIP_MM * FINGER_DIR))[2])))
    return out


def joint_move_ok(j0, j1):
    """The joint move j0 -> j1 never takes the gripper more than PATH_SAG_MM below its start and its end."""
    z = path_heights(j0, j1)
    return min(z) >= min(z[0], z[-1]) - PATH_SAG_MM


def move_ok(j0, j1):
    """The joint move j0 -> j1 out to a table keeps the gripper HEAD_CLEAR_MM from the head and does not dip
    (arm_route.move_problem, the check of every pose-graph move); False when the head's place is not measured."""
    from manipulation import arm_route
    centre = arm_route.head_cam.head_centre()
    return centre is not None and arm_route.move_problem(j0, j1, centre) is None


def checked(waypoints, start_joints):
    rows = ik_chain(waypoints, start_joints)
    if rows[-1][3]:
        log(f"plan refused at {rows[-1][0]}: {rows[-1][3]}")
        raise SkillError("I can't reach it safely.")
    return rows


def pick_options(obj, start, max_yaw=None):
    """(waypoints, joints above) of every grasp turn (GRASP_YAWS; from -`max_yaw` to 0 deg when given: the turns picked
    live, TRUSTED_YAW_DEG) and wrist solution
    reachable from `start`: a joint move down to above that stays above it, then straight down and up; the controller
    confirms each one given. Every pick that worked live had J5 > 0: those come first. Objects of the wrong width
    raise."""
    plan_pick(obj)
    tried = []
    for wrist, seeds in ((1, IK_SEEDS[:1]), (1, IK_SEEDS[1:]), (-1, IK_SEEDS[:1]), (-1, IK_SEEDS[1:])):
        for yaw in GRASP_YAWS:                         # the proven wrist (J5 > 0) and `ready` configuration first
            if max_yaw is not None and not -max_yaw <= yaw <= 0:
                continue
            waypoints = plan_pick(obj, yaw)
            for ja in above_joints(waypoints[0][1], start, seeds):
                if ja[4] * wrist < 0 or any(y == yaw and max(abs(a - b) for a, b in zip(t, ja)) <= 1.0
                                            for y, t in tried):
                    continue                           # another seed found the same solution
                tried.append((yaw, ja))
                rows = ik_chain(waypoints[1:], ja)
                if not rows[-1][3] and wrist_ok([ja] + [r[2] for r in rows]) and move_ok(start, ja) and \
                        confirm(waypoints, ja):
                    yield waypoints, ja


def wrist_ok(joints):
    """J5 stays WRIST_MIN_DEG from 0 at every pose of a straight move down and up: near J5 = 0 a straight move may
    turn J4 and J6 far round in small steps (motion.move_linear refuses it there, half way through the pick)."""
    return all(abs(j[4]) >= WRIST_MIN_DEG for j in joints)


def tilt_on(j0, j1):
    """Largest lean (deg) of the held cup's axis from vertical at PATH_POINTS points of the joint move j0 -> j1."""
    axis = calib.rpy_matrix(*GRASP_RPY).T @ [0.0, 0.0, 1.0]           # cup axis in the flange frame
    j0, j1, worst = np.array(j0), np.array(motion.nearest(j1, list(j0))), 0.0
    for k in range(PATH_POINTS):
        c = _ask("kine_forward", jointPosition=[float(v) for v in j0 + (j1 - j0) * k / (PATH_POINTS - 1)])["cartPosition"]
        v = calib.rpy_matrix(*c[3:]) @ axis
        worst = max(worst, math.degrees(math.acos(float(np.clip(v[2], -1.0, 1.0)))))
    return worst


def place_options(x, y, top_mm, start):
    """(waypoints, joints above) of every grasp turn (GRASP_YAWS, the held turn first) and wrist solution that puts
    the held object down at (x, y) with its top at `top_mm`: a joint move from the joints `start` to above the spot
    that stays above it and keeps the cup upright (MAX_TILT_DEG), then straight down and up; after all of those, a
    straight line from where the hand is to above the spot (first waypoint "above place (straight)": line_joints).
    An upright cup turned about its own axis stands the same: any turn will do, as for the pick."""
    held = _held.get("yaw", 0.0)
    yaws = sorted(GRASP_YAWS, key=lambda a: abs((a - held + 180.0) % 360.0 - 180.0))
    for yaw in yaws:
        way = plan_place(x, y, top_mm, yaw=yaw)
        for ja in above_joints(way[0][1], start):
            rows = ik_chain(way[1:], ja)
            if not rows[-1][3] and wrist_ok([ja] + [r[2] for r in rows]) and move_ok(start, ja) and \
                    tilt_on(start, ja) <= MAX_TILT_DEG and confirm(way, ja):
                yield way, ja
    c0 = _ask("kine_forward", jointPosition=[float(v) for v in start])["cartPosition"]
    for yaw in yaws:                              # a joint move from look leans the cup where a line keeps it upright
        way = plan_place(x, y, top_mm, yaw=yaw)
        way[0] = ("above place (straight)", way[0][1])
        ja = line_joints(c0, start, way[0][1])
        if ja is None:
            continue
        rows = ik_chain(way[1:], ja)
        if not rows[-1][3] and wrist_ok([ja] + [r[2] for r in rows]) and confirm(way, ja):
            yield way, ja


def line_joints(c0, j0, target, steps=LINE_POINTS):
    """Joints at the end of the straight move with the held cup from the flange pose `c0` (joints `j0`) to `target`:
    IK at `steps` points, no joint turning more than LINE_STEP_DEG between two, J5 off 0, the cup leaning at most
    MAX_TILT_DEG, the gripper HEAD_CLEAR_MM from the head (its place measured); None when not."""
    from manipulation import arm_route
    centre = arm_route.head_cam.head_centre()
    c0 = np.array(c0, float)
    d = np.array(target, float) - c0
    d[3:] = (d[3:] + 180.0) % 360.0 - 180.0
    rows = ik_chain([(f"line {k}", [float(v) for v in c0 + d * k / steps]) for k in range(1, steps + 1)], j0)
    if centre is None or rows[-1][3]:
        return None
    js = [list(j0)] + [r[2] for r in rows]
    axis = calib.rpy_matrix(*GRASP_RPY).T @ [0.0, 0.0, 1.0]           # cup axis in the flange frame
    if max(abs(b - a) for p, q in zip(js, js[1:]) for a, b in zip(p, q)) > LINE_STEP_DEG or not wrist_ok(js[1:]) or \
            any((calib.rpy_matrix(*r[1][3:]) @ axis)[2] < math.cos(math.radians(MAX_TILT_DEG)) for r in rows) or \
            min(arm_route.flange_clearance(r[1], centre) for r in rows) < arm_route.HEAD_CLEAR_MM:
        return None
    return js[-1]


def place_turned(way, ja):
    """Put down along a place_options() option: to above the spot (a joint move, or the straight line it was planned
    with), then down, open, up and home."""
    _go_on()
    log(f"{way[0][0]}: grasp turned {yaw_of(way[0][1]):+.0f} deg, wrist J5 {ja[4]:+.0f}")
    if way[0][0].endswith("(straight)"):
        motion.move_linear(target=way[0][1], speed=HOLDING_SPEED, path_checked=True)
    else:
        motion.move_joints(ja, HOLDING_SPEED)
    _do_place(way)


def carry_up(above, ja):
    """Another way to carry for a held cup whose straight line from above the pick spot (flange pose `above`, joints
    `ja`) to carry is refused: straight up CARRY_UP_MM (line_joints at LINE_STEPS points), then one joint move to
    carry, the cup upright, clear of the head, no dip (arm_route.check_moves). (pose up there, carry joints) or None."""
    from manipulation import arm_route
    for dz in CARRY_UP_MM:
        j = line_joints(above, ja, up(above, dz), LINE_STEPS)
        if j is None:
            continue
        try:
            return up(above, dz), arm_route.check_moves(j, [motion.poses()["carry"]], holding=True)[0]
        except arm_route.RouteError:
            continue
    return None


def carry_by_joints(plan):
    """Run a carry_up() plan from above the pick spot: straight up, then the joint move to carry."""
    _line("up to carry", plan[0])
    _go_on()
    log("carry: joint move")
    motion.move_joints(plan[1], HOLDING_SPEED)


def reachable_pick(obj, start=None, accept=lambda waypoints, ja: True, max_yaw=None):
    """(waypoints, joints above) of the first pick option from `start` (home), grasp turned -`max_yaw`..0 deg
    (e.g. TRUSTED_YAW_DEG; None: any), that `accept` also takes, else None."""
    for waypoints, ja in pick_options(obj, home_joints() if start is None else start, max_yaw):
        if accept(waypoints, ja):
            yaw = round(yaw_of(waypoints[1][1]))
            how = "between the tips" if grip_width(obj) < BELLY_MIN_MM else "in the hooks"
            log(f"grasp {how}, turned {yaw:+d} deg, wrist J5 {ja[4]:+.0f}" if yaw else
                f"grasp {how}, wrist J5 {ja[4]:+.0f}")
            return waypoints, ja
    log(f"plan refused: no grasp turn{'' if max_yaw is None else f' from -{max_yaw:.0f} to 0 deg'} reaches "
        f"({obj['x']:.0f}, {obj['y']:.0f})")
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
            rows = ik_chain(pick[1:] + plan_place(*xy, obj["top_mm"], start=pick[-1][1], yaw=yaw,
                                                  tips=grip_width(obj) < BELLY_MIN_MM,
                                                  below=obj["top_mm"] - grasp_height(obj),
                                                  back=side_back(obj) if side(obj) else 0.0), ja)
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
    back_out()
    if max(abs(a - b) for a, b in zip(_joints(), home_joints())) > 1.0:
        from manipulation import arm_route
        arm_route.goto(home())


def _back_home():
    """From the table (out from home along the checked plan) straight back to the home pose: one joint move, checked
    (arm_route: never lower than where it is now, clear of the head)."""
    _go_on()
    from manipulation import arm_route
    arm_route.goto(home(), leaf=True)


def _line(name, pose):
    _go_on()                             # move_linear clears motion's own stop flag, so check ours before each move
    log(f"{name}: to ({pose[0]:.0f}, {pose[1]:.0f}, {pose[2]:.0f})")
    motion.move_linear(target=pose, speed=HOLDING_SPEED)


def _give_up(reason, back=0.0):
    """Open, back up 100 mm (from a side grasp first `back` mm out sideways: the rim is wider than the hooks), home,
    raise. Only used while the object is at (or just above) the table."""
    log(f"{reason}: opening, backing up")
    _held.clear()
    gripper.open_()
    if back:
        _line("out sideways", back_off(motion.tcp(), back))
    motion.move_linear(delta=[0, 0, ABOVE_MM], speed=HOLDING_SPEED)
    _back_home()
    _pick_way.clear()
    raise SkillError(reason)


def back_out():
    """A pick stopped on its way in (_pick_way: the open hand beside the object or down around it): out the way it
    came before anything else moves, a side grasp straight out against the tips' direction to its "side" point, then
    straight up to its "above" height. Nothing when no pick was stopped there or the hand is no longer near its way."""
    if not _pick_way:
        return
    now, way = motion.tcp(), _pick_way
    above, grasp = way["above"], way["grasp"]
    start = way.get("side", grasp)
    near = np.hypot(start[0] - grasp[0], start[1] - grasp[1]) + BACK_OUT_NEAR_MM
    if now[2] >= above[2] - 1.0 or now[2] < grasp[2] - BACK_OUT_NEAR_MM or \
            np.hypot(now[0] - grasp[0], now[1] - grasp[1]) > near:
        _pick_way.clear()                        # already up there, or moved away since: nothing to back out of
        return
    log("a pick was stopped here: backing out the way it came in")
    if "side" in way:
        d = float(np.dot(np.subtract(now[:2], start[:2]), tips_dir(yaw_of(now))))
        if d > 1.0:
            now = back_off(now, d)
            _line("out sideways", now)
    _line("up", [now[0], now[1], above[2]] + list(now[3:]))
    _pick_way.clear()


def _do_pick(obj, waypoints, ja):
    """Pick with the planned joints `ja` above the object (pick_options); a side grasp goes down beside it first."""
    way = dict(waypoints)
    above, grasp, lift = way["above"], way["grasp"], way["lift"]
    back = side_back(obj) if "side" in way else 0.0
    table = obj.get("table_mm")                                      # a bottle's: look() measured it
    if table is None:
        table = table_z(obj) if table_z(obj) is not None else table_near(obj)   # what put down needs: the object's height
    log(f"it stands on a table at {table:.0f} mm" if table is not None else "the table under it is not in view")
    _held.clear()                                                    # nothing held until the fingers close on it
    _prepare()
    _go_on()
    _pick_way.clear()
    _pick_way.update(way)
    log(f"above: joint move to ({above[0]:.0f}, {above[1]:.0f}, {above[2]:.0f})")
    motion.move_joints(ja, EMPTY_SPEED)
    if back:
        _line("side", way["side"])
    _line("grasp", grasp)
    _go_on()
    log("closing")
    s = gripper.close()
    log(f"AI_1 {s['ai'][0]:.0f} holding {s['holding']} finger sensor {s['object_in_front']}")
    if not s["holding"]:
        _give_up("I missed it.", back)
    # held from here on: a stop in the lift leaves it ready to put down
    _held.update(top_mm=obj["top_mm"], x=obj["x"], y=obj["y"], yaw=yaw_of(grasp), table=table,
                 tips=grip_width(obj) < BELLY_MIN_MM, below=obj["top_mm"] - grasp_height(obj), back=back)
    _pick_way.clear()
    _line("lift", lift)
    s = gripper.state()
    log(f"AI_1 {s['ai'][0]:.0f} holding {s['holding']}")
    if not s["holding"]:
        _held.clear()
        _line("slipped, back down", grasp)
        _give_up("It slipped out of my hand.", back)


def _do_place(waypoints):
    """Down to "place", open, then the rest (out sideways after a side grasp, up) and home."""
    n = [name for name, _ in waypoints].index("place") + 1
    for name, pose in waypoints[:n]:
        _line(name, pose)
    _go_on()
    log("opening")
    s = gripper.open_()
    log(f"AI_1 {s['ai'][0]:.0f}")
    if s["ai"][0] > OPEN_AI:
        raise SkillError("My hand did not open.")           # stay put: lifting now would drag the object
    _held.clear()
    for name, pose in waypoints[n:]:
        _line(name, pose)
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
    plan = reachable_pick(obj, max_yaw=TRUSTED_YAW_DEG)              # no base here to bring it round (fetch can)
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
    carry = ik_chain([("carry", up(start, ABOVE_MM))], joints)         # other turns start from up here, clear of
    for xy in tries:                                                   # the table
        rows = ik_chain(plan_place(*xy, _held["top_mm"], start=start, yaw=_held.get("yaw", 0.0)), joints)
        if not rows[-1][3]:
            _guarded(_do_place, [(r[0], r[1]) for r in rows])
            log("done")
            return xy
        log(f"spot ({xy[0]:.0f}, {xy[1]:.0f}) refused at {rows[-1][0]}: {rows[-1][3]}")
        opt = None if carry[-1][3] else next(place_options(*xy, _held["top_mm"], carry[-1][2]), None)
        if opt:
            _guarded(_line, "carry", carry[-1][1])
            _guarded(place_turned, *opt)
            log("done")
            return xy
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
    n = 4 if side(obj) else 3                       # above, (side,) grasp, lift
    _guarded(_do_pick, obj, waypoints[:n], rows[0][2])
    _guarded(_do_place, waypoints[n:])
    log("done")
    return xy


def hover(name="cup", yaw=0.0):
    """Live check of the grasp point: the pick of `name` planned with the grasp turned `yaw` deg,
    slow, down to the grasp point HOVER_MM above its top (the hooks' ring over the rim, nothing touches, the gripper
    stays open); Enter: back up and home. The owner reads how far the ring's centre is from the rim's centre."""
    _cancel.clear()
    obj = find(name)
    log(f"found {obj['colour']} {obj['name']} at ({obj['x']:.0f}, {obj['y']:.0f}) top {obj['top_mm']:.0f}")
    way, ja = next(((w, j) for w, j in pick_options(obj, home_joints()) if round(yaw_of(w[1][1])) == round(yaw)),
                   (None, None))
    if way is None:
        raise SkillError(f"No grasp turned {yaw:+.0f} deg reaches it.")
    _prepare()
    _go_on()
    log(f"above: joint move, grasp turned {yaw:+.0f} deg, wrist J5 {ja[4]:+.0f}")
    motion.move_joints(ja, HOLDING_SPEED)
    _line("hover", up(dict(way)["grasp"], obj["top_mm"] - grasp_height(obj) + HOVER_MM))
    input(f"hooks {HOVER_MM:.0f} mm over the rim, cup seen at ({obj['x']:.0f}, {obj['y']:.0f}): read the offset, "
          f"then Enter ")
    _line("up", way[0][1])
    _back_home()


def offset_fix(reports):
    """From hover() readings [(grasp turn deg, ring centre minus rim centre (dx, dy) mm, arm frame)] at one cup spot,
    with at least two turns: (u, e, new tcp_offset_flange). u: the taught grasp point's horizontal error (it turns
    with the grasp), e: the camera's error at that spot (it does not). Reading = e - Rz(turn) u, least squares."""
    A, b = [], []
    for yaw, d in reports:
        A += list(np.hstack([np.eye(2), -_rz(yaw)[:2, :2]]))
        b += list(d)
    e_u = np.linalg.lstsq(np.array(A), np.array(b, float), rcond=None)[0]
    u = np.array([*e_u[2:], 0.0])
    return u[:2], e_u[:2], GRASP_OFFSET - calib.rpy_matrix(*GRASP_RPY).T @ u


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
        elif a[:1] == ["hover"]:
            hover(a[1] if len(a) > 1 else "cup", float(a[2]) if len(a) > 2 else 0.0)
        elif a[:1] == ["offset"] and len(a) >= 7 and len(a) % 3 == 1:
            v = [float(x) for x in a[1:]]
            u, e, new = offset_fix([(v[i], v[i + 1:i + 3]) for i in range(0, len(v), 3)])
            print(f"grasp point error {u.round(1)} mm, camera error {e.round(1)} mm; "
                  f"tcp_offset_flange {[round(float(x), 1) for x in new]} (was {GRASP_OFFSET.tolist()})")
        else:
            sys.exit(__doc__)
    except SkillError as e:
        sys.exit(f"refused: {e}")
    except motion.MotionError as e:
        sys.exit(f"motion failed: {e}")
    except KeyboardInterrupt:
        sys.exit("stopped")
