"""Fetch tasks: drive to a place, find an object with the torso camera, pick it up, bring it somewhere and hold
it or put it on the table there (docs/16_FETCH_TASKS.md). One runner per process, in a background thread; the
state is shared through /dev/shm/lumi_task.json so the API, the assistant and the dashboard all see it.

    python tasks/fetch.py describe '{"object": "apple", "source": {"marker": "p1"}, "dest": {"marker": "home"}, "finish": "hold"}'
    python tasks/fetch.py state
    python tasks/fetch.py measure-axis [cup]    # MOVES THE BASE 10 cm forward and back: arm at ready, a cup in reach

The task: {"object", "colour" (or null), "source": "here" | {"marker"} | {"x", "y", "theta"},
"dest": the same forms, "finish": "hold" | "place"}. Map points are metres / radians in the map frame.
"""
import json
import math
import os
import random
import statistics
import sys
import threading
import time
from pathlib import Path

import numpy as np

from manipulation import skills
from robot import agv
from robot import gripper
from robot import head
from robot import motion
from vision import calib
from vision import camview
from vision import head_cam
from vision import objects

ROOT = Path(__file__).resolve().parents[1]      # the project folder
STATE_FILE = Path("/dev/shm/lumi_task.json")   # the task state, readable by every process
CALIB_FILE = ROOT / "data" / "fetch_calib.json"
KNOWN_FILE = ROOT / "data" / "known_things.json"    # things taught by name and colour, kept by their place on the map  # {"arm_yaw_in_base_deg": ...} from measure-axis
OBJECTS = {"cup": "컵", "bottle": "병", "apple": "사과", "orange": "오렌지", "banana": "바나나"}   # camera classes
COLOURS = {"red": "빨간", "orange": "주황색", "yellow": "노란", "green": "초록색", "blue": "파란", "purple": "보라색",
           "pink": "분홍색", "white": "흰", "black": "검은", "grey": "회색"}   # the names objects.colour_name gives
FINISH = ("hold", "place")
LOOK_POSE = "look"           # drives, turns, looks and waits here, also with an object (the cup leans 5.9 deg); high,
                             # out of the torso camera's view (ready if not taught). carry is only passed through after a
                             # pick: in carry the hand is ~0.3 m before the base's front, where its 3D camera seems to see
                             # it as an obstacle (every drive in carry stalled; the same drives in look went, 2026-10-16)
MAX_TILT_DEG = 15.0          # deg; the held cup's axis may lean this far from vertical on ready <-> carry
TILT_POINTS = 11             # points checked along a joint move (kine_forward)
LINE_POINTS = 20             # points IK- and tilt-checked on a straight move with an object in the hand ...
LINE_STEP_DEG = 25.0         # ... no joint may turn more than this between two of them (one IK branch all the way;
                             # near J5 = 0 J4 and J6 turn ~15 deg a step against each other, the cup hardly turns)
# ponytail: fixed table height (top ~ -400 mm in the arm base frame, the 142 mm tumbler's top ~ -258);
# use the measured table top instead when tables of other heights come in.
MIN_POSE_Z = -220.0          # mm; a move between named poses must keep the grasp point above this (or above its start)
PICK_ZONE_CENTRE = (-100.0, 580.0)   # mm, arm base frame: where the base brings an object out of reach. Next to the
                                     # successful picks (x -126..-178, y 579..613) and inside the reach at table height
                                     # (IK map 2026-10-16, top -330: grasps for x -200..100 at y <= 650, none further)
PLACE_GRID_X = range(-260, -59, 40)  # mm; place spots tried after the pick spot. At table height the torso camera
PLACE_GRID_Y = (640, 660, 680, 700)  # sees only y >= ~640, nearer spots can't be checked for table (skills.on_table)
PLACE_GOAL = (-160.0, 670.0)         # mm; a table spot seen further away is brought here by the base (middle of the grid)
FAR_GRID_X = range(-700, 501, 50)    # mm; where a table further away is looked for in the depth image
FAR_GRID_Y = range(720, 1601, 40)
KNOWN_M = 0.5                        # m; a thing seen this near where it was taught is that thing
SUPPORT_DISC_MM = 100.0              # mm; the top of a named thing (a chair's seat) is measured on a disc this wide
FAR_TRIES = 15                       # nearest table points checked for a whole free spot (ring) there
TABLE_PROVEN_Z = -403.0      # mm, arm base frame: the table top of every proven pick and place (lift 75 mm)
SURFACE_Z = (-560.0, -30.0)  # mm, arm frame, after the lift: table tops the arm can pick from / put on at all (IK of
                             # the grasp, 2026-10-16: -578 4 of 9 spots, -528 7 of 9, -28 9 of 9). Lower: a floor or a
                             # seat ~30 cm under a table, which no grasp reaches even at lift 0
LIFT_TOL_MM = 20.0           # closer than this: the lift stays
LIFT_RANGE = (0.0, 250.0)    # mm; the body API allows 0-300, kept to what the colleagues' code uses (lumi_voice_app)
LIFT_DRIVE_MM = 75.0         # every drive, every task's end and a look that found nothing again at this lift
                             # (higher, the near part of the table is below the torso camera's view)
LIFT_VEL = 20                # % of the lift's speed
SEARCH_TURN_DEG = 30.0       # search: look, turn on the spot by this much, look again ...
SEARCH_TURNS = 11            # ... this many times (all the way round) at the lift it has; never while charging
LIFT_TRIES = (0.0, 250.0)    # mm; nothing found: the same whole turn again at these lifts (down first, then up)
SAME_BASE_M = 0.02                   # m / rad; the base is still where it picked: the pick spot is still table
SAME_BASE_RAD = 0.035
APPROACH_TRIES = 5           # base moves to bring an object out of reach to PICK_ZONE_CENTRE before asking the person
STRAIGHT_MAX_M = 0.6         # m; a straight drive (after a turn on the spot) at most this long, else navigation
STANDOFF_M = 0.4             # m; navigation goes to this far back from the pick pose, then straight in
APPROACH_SIDES = (0, 45, -45, 90, -90, 135, -135, 180)   # deg; ways in to the object tried by navigation, the
                                                       # direct one first (a table side may be blocked)
BASE_HALF_M = 0.255          # m; half the base's 510 mm (docs/01) ...
CLEAR_M = 0.05               # ... plus this: a straight drive stops where the base would get closer to an obstacle
PROBE_STEP_M = 0.05          # m between the points checked along a straight drive
TURN_MIN_DEG = 3.0           # smaller turns are left out
FURNITURE_ANGLES = (45, 90, 135)     # deg left / right of the heading ...
FURNITURE_RANGES = (0.6, 1.0, 1.4)   # ... and m from the base centre where the first search turn looks for things
FURNITURE_HIT_M = 0.3                # ... the lidar sees now (closer than this) and the map does not have (nothing
FURNITURE_MAP_M = 0.5                # on the map this near): tables, chairs, boxes, where an object most likely stands
LOST_BACK_M = 0.15           # an object lost after a base move: back off this much (the camera sees more) ...
LOST_TURN_DEG = 20.0         # ... and turn this much each way, looking again (YOLO, then depth where it should be)
ARM_CLEAR_M = 0.10           # m; flange, grasp point and finger tips kept this far from anything the lidar or the map
SWEEP_STEP_DEG = 10.0        # shows while the base turns on the spot, checked every this many degrees (turn_hits)
SELF_MM = 120.0              # depth this near the arm's own flange / grasp point / tips is the arm itself (depth_hits)
HEAD_SIDE_DEG = 60.0         # head yaw (+ left) towards the side of a turn, to check the arm's sweep (head_hits)
HEAD_LOW_PITCH = -5.0        # head pitch for those checks and the search: its lowest, where the camera is calibrated
HEAD_SETTLE_S = 1.2          # s after a head move: frames at rest (depth is written every 0.5 s)
HEAD_SCAN_STEP_DEG = 60.0    # search with the head: ahead, then every this many degrees to one side up to ...
HEAD_SCAN_MAX_DEG = 180.0    # ... this head yaw (its end), then the same to the other side (the colour view is 94 deg wide)
BASE_HALF_STEPS = 3          # then the base turns half round in this many checked turns and the head looks again
HEAD_READS = 4               # detection reads per head yaw ...
HEAD_SAME_MM = 120.0         # ... an object counts when seen at least twice within this distance
HEAD_DRIVE_MAX_M = 3.0       # m; at most this far straight towards a thing the head camera found
OFFSET_TURN_DEG = 15.0       # a move that turned the base at least this much tells where the arm base is (arm_offset)
WIDTH_NEAR_MM = 250.0        # mm from PICK_ZONE_CENTRE; a width measured further away is not trusted (the same tumbler:
                             # 85-88 mm at 1.14 m, 76-81 up close, 2026-10-16; the gripper takes up to 84)
OFFSET_SAMPLES = 9           # ... the median of the last this many such measurements is used (one can be off)
ASK_WAIT_S = 30.0            # s; after "please move it closer" look again for this long ...
ASK_EVERY_S = 2.0            # ... this often
DRIVE_POLL_S = 0.5           # s between base status reads while driving
DRIVE_START_S = 3.0          # s to see the base report "running" after a go; after that its status is believed
STUCK_S = 30.0               # s "running" without getting STUCK_M anywhere (turning on the spot does not count) ...
STUCK_M = 0.10               # ... -> the drive is cancelled: no way through
HOLD_CHECK_S = 1.0           # s between gripper reads while driving with an object
SAME_PLACE_M = 0.05          # m; closer than this to the target point (and SAME_ANGLE) -> no drive
SAME_ANGLE_RAD = 0.05
AXIS_STEP_M = 0.10           # m the base drives forward (and back) in measure-axis
AXIS_SPEED = 0.05            # m/s; straight with joy_control (navigation may turn in place, the arm is over the table)
COAST_S = 1.0                # s; the base coasts a little after a joy_control stop
GIVE_WAIT_S = 30.0           # s; no release by then: keep holding it and go back to carry (never drop it)
# Opening needs a word from the person ("thank you", or Release in the dashboard): AI_1 can't feel a pull. Measured
# 2026-10-15 with the cup in the closed gripper: its median stayed 2780-2870 during gentle pulls (only its noise
# grew, sd 20 -> 50-75), while the fingers settling after the move changed it by 192.
GIVE_POLL_S = 0.2
MOVE_SPEED = 0.10            # m/s; a mission's move (straight with joy_control); estimate, tune live (docs/17)
RECEIVE_WAIT_S = 30.0        # s; receive: nothing put in the hand by then -> the mission fails, hand open
RECEIVE_DI_S = 0.5           # s; DI_1 (finger sensor) sees something this long -> Lumi asks the person to let go;
                             # the hand closes only on their "okay" / Release (never on fingers still in it)
MOVE_SEGMENT_M = 0.25        # m; a mission move is driven in pieces this long, the way (base and arm) checked before each
WAIT_POLL_S = 0.2            # s between looks at stop / go on / an instruction while a mission waits (a wait step)
LOG_LINES = 40

_lock = threading.RLock()                   # _finish sets the state while it holds it
_stop = threading.Event()                    # set by stop(): every step and every wait gives up
_release = threading.Event()                 # set by release_now() ("thank you" / Release while giving)
_proceed = threading.Event()                 # set by proceed() ("go on" while a mission waits): the wait ends
_order = {"steps": None}                     # steps given by instruct() to a wait for an instruction
_rest = []                                   # the running mission's steps still to come (instruct() checks them too)
_pause = threading.Event()                   # set by pause() (someone talks to Lumi on the way): drives halt, the run
                                             # waits at the next step; resume() goes on where it was
_thread = None
_task = {"start_pose": None}                 # map pose (x, y, theta) where the current task was given
_state = {"status": "idle", "step": "", "task": None, "holding": False, "log": [], "since": time.time()}


class FetchError(RuntimeError):
    """A plain spoken-style reason why the task cannot start or go on."""


class Stopped(Exception):
    pass


# ---------- state ----------
def _write():
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps({**_state, "held": dict(skills._held)}))
    os.replace(tmp, STATE_FILE)


def _adopt():
    """Holding something that another process picked (the API ran the task, now the assistant gives it):
    take over its holding state and what skills needs to put it down."""
    s = state()
    if not _busy() and s.get("holding") and not _state["holding"]:
        _state.update(holding=True, task=s.get("task"), status="holding", step="holding")
        skills._held.update(s.get("held") or {})


def _set(**kw):
    with _lock:
        if "status" in kw and kw["status"] != _state["status"]:
            kw["since"] = time.time()
        _state.update(kw)
        _write()


def log(*a):
    line = " ".join(str(x) for x in (time.strftime("%H:%M:%S"),) + a)
    print(line, flush=True)
    with _lock:
        _state["log"] = (_state["log"] + [line])[-LOG_LINES:]
        _write()


def state():
    """{"status", "step", "task", "holding", "log", "since"} as the runner (in any process) wrote it last."""
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return {"status": "idle", "step": "", "task": None, "holding": False, "log": [], "since": None}


# ---------- the task in words ----------
def _place_ok(p, markers):
    if p == "here":
        return True
    if isinstance(p, dict) and "marker" in p:
        return p["marker"] in markers
    return isinstance(p, dict) and all(isinstance(p.get(k), (int, float)) for k in ("x", "y", "theta"))


def validate(task, markers):
    """Problems with `task` in plain words; empty when it can run. `markers`: marker names on the map."""
    out = []
    if task.get("object") not in OBJECTS:
        out.append("Which object? I know cup, bottle, apple, orange and banana.")
    if task.get("colour") is not None and task["colour"] not in COLOURS:
        out.append(f"I don't know the colour {task['colour']}.")
    for key, what in (("source", "Where should I take it from?"), ("dest", "Where should I bring it?")):
        p = task.get(key, "here" if key == "source" else None)
        if p is None:
            out.append(what)
        elif not _place_ok(p, markers):
            known = isinstance(p, dict) and "marker" in p
            out.append(f"I don't know the place {p['marker']}." if known else what)
    if task.get("finish") not in FINISH:
        out.append("Should I hold it or put it on the table?")
    return out


def _object_particle(word):
    """을 / 를 after a Korean word (final consonant or not)."""
    c = word[-1]
    return "을" if "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 else "를"


def describe(task, lang="en"):
    """The read-back sentence, e.g. "Take the apple from p1, bring it to home and hold it."."""
    obj, colour = task.get("object") or "?", task.get("colour")
    src, dst = task.get("source", "here"), task.get("dest")
    mark = {k: p["marker"] for k, p in (("src", src), ("dst", dst)) if isinstance(p, dict) and "marker" in p}
    place = task.get("finish") == "place"
    if lang == "ko":
        thing = (COLOURS.get(colour, colour) + " " if colour else "") + OBJECTS.get(obj, obj)
        frm = "여기에서" if src == "here" else f"{mark['src']} 위치에서" if "src" in mark else "알려 주신 위치에서"
        to = "여기로" if dst == "here" else f"{mark['dst']} 위치로" if "dst" in mark else \
            "알려 주신 위치로" if dst else "어딘가로"
        end = "테이블에 내려놓을게요" if place else "들고 있을게요"
        carry = "가져와서" if dst == "here" else "가져가서"
        return f"{frm} {thing}{_object_particle(thing)} 가져와서 {to} {carry} {end}."
    thing = (colour + " " if colour else "") + obj
    frm = "from here" if src == "here" else f"from {mark['src']}" if "src" in mark else "from the point I was shown"
    to = "here" if dst == "here" else f"to {mark['dst']}" if "dst" in mark else \
        "to the point I was shown" if dst else "somewhere"
    end = "put it on the table" if place else "hold it"
    return f"Take the {thing} {frm}, bring it {to} and {end}."


# ---------- helpers ----------
def _go_on():
    """Between parts of a run: STOP ends it; a pause waits here until resume()."""
    if _stop.is_set():
        raise Stopped()
    if _pause.is_set():
        log("paused")
        while _pause.is_set():
            if _stop.wait(0.1):
                raise Stopped()
        log("going on")


def _step(name, say=None, en=None, ko=None):
    _go_on()
    _set(step=name)
    log(name)
    if en:
        _say(say, en, ko)


def _say(say, en, ko=None):
    if say:
        try:
            say(en, ko)
        except Exception as e:           # a speaking problem must not stop the robot halfway
            log(f"say failed: {e}")


def _pose(name, speed=skills.EMPTY_SPEED):
    """Joint move to pose `name`, refused when it would take the gripper down to the table. Empty hand: faster."""
    _go_on()
    start, low = lowest_along(name)
    if low < min(MIN_POSE_Z, start - 10.0):
        log(f"refused: on the way to {name} the gripper would go down to z {low:.0f} mm")
        raise FetchError("My arm would go too close to the table, I stopped.", "팔이 테이블에 너무 가까워져서 멈췄어요.")
    log(f"arm to {name}")
    motion.go(name, speed)
    _go_on()


def _path(name):
    """Flange poses (rotation, position) at TILT_POINTS points on the joint move from here to pose `name`."""
    j0 = np.array(skills._joints())
    j1 = np.array(motion.nearest(motion.poses()[name], list(j0)))
    for k in range(TILT_POINTS):
        c = skills._ask("kine_forward", jointPosition=[float(v) for v in j0 + (j1 - j0) * k / (TILT_POINTS - 1)])
        c = c["cartPosition"]
        yield calib.rpy_matrix(*c[3:]), np.array(c[:3])


def lowest_along(name):
    """(start z, lowest z) in mm of the grasp point on the joint move from here to pose `name`."""
    z = [float((t + R @ skills.GRASP_OFFSET)[2]) for R, t in _path(name)]
    return z[0], min(z)


def tilt_along(name):
    """Largest lean (deg) of the held cup's axis from vertical on the joint move from here to pose `name`."""
    axis = calib.rpy_matrix(*skills.GRASP_RPY).T @ [0.0, 0.0, 1.0]      # cup axis in the flange frame
    worst = 0.0
    for R, _ in _path(name):
        v = R @ axis
        worst = max(worst, math.degrees(math.acos(float(np.clip(v[2], -1.0, 1.0)))))
    return worst


def _line_rows(target, label, start=None):
    """IK rows of the straight move from here (or `start`: (flange pose, joints)) to the flange pose `target`.
    FetchError when IK fails on the way or the held cup would lean more than MAX_TILT_DEG (the arm stays where it is)."""
    c0, j0 = (np.array(motion.tcp()), skills._joints()) if start is None else (np.array(start[0], float), list(start[1]))
    d = np.array(target, float) - c0
    d[3:] = (d[3:] + 180) % 360 - 180
    rows = skills.ik_chain([(f"{label} {k}", [float(v) for v in c0 + d * k / LINE_POINTS])
                            for k in range(1, LINE_POINTS + 1)], j0)
    if rows[-1][3]:
        log(f"straight move {label} refused at {rows[-1][0]}: {rows[-1][3]}")
        raise FetchError("I can't move my arm there safely.")
    js = [j0] + [r[2] for r in rows]
    jump = max(abs(b - a) for p, q in zip(js, js[1:]) for a, b in zip(p, q))
    if jump > LINE_STEP_DEG:
        log(f"straight move {label}: a joint jumps {jump:.0f} deg between two points")
        raise FetchError("I can't move my arm there safely.")
    axis = calib.rpy_matrix(*skills.GRASP_RPY).T @ [0.0, 0.0, 1.0]
    tilt = max(math.degrees(math.acos(float(np.clip((calib.rpy_matrix(*r[1][3:]) @ axis)[2], -1.0, 1.0))))
               for r in rows)
    if tilt > MAX_TILT_DEG:
        log(f"straight move {label}: the cup would lean {tilt:.1f} deg")
        raise FetchError("I can't move my arm there without spilling it.")
    return rows


def _line_holding(name):
    """With the object in the hand: straight to pose `name` (IK and tilt checked), then its exact joints."""
    _go_on()
    target = skills._ask("kine_forward", jointPosition=[float(v) for v in motion.poses()[name]])["cartPosition"]
    _line_rows(target, f"to {name}")
    log(f"arm to {name} (straight)")
    motion.move_linear(target=target, speed=skills.HOLDING_SPEED, path_checked=True)
    _go_on()
    j = skills._joints()
    if max(abs(a - b) for a, b in zip(j, motion.nearest(motion.poses()[name], j))) > 1.0:
        _pose_holding(name)


def _look():
    return LOOK_POSE if LOOK_POSE in motion.poses() else "ready"


def _pose_holding(name):
    """Joint move with an object in the hand: refused when the cup would lean more than MAX_TILT_DEG."""
    tilt = tilt_along(name)
    log(f"tilt on the way to {name}: {tilt:.1f} deg")
    if tilt > MAX_TILT_DEG:
        raise FetchError("I can't move my arm there without spilling it.")
    _pose(name, skills.HOLDING_SPEED)


def _wait_drive(watch_holding=False, again=None):
    """Wait until the base stops. Raises FetchError unless it arrived ("succeeded"). A pause cancels the drive, waits
    for resume() and then calls again() to send the base on (the rest of a turn, the same goal)."""
    t0 = last_hold = time.time()
    seen_running = False
    anchor = None                            # (x, y, time) of the last real progress
    while True:
        if _stop.wait(DRIVE_POLL_S):
            raise Stopped()
        if _pause.is_set():
            agv.cancel()
            _go_on()                             # waits until resume() (or STOP)
            if again is None:
                raise FetchError("I was stopped on the way.", "가는 중에 멈췄어요.")
            ok, msg = again()
            if ok is None:                       # nothing left to do (a turn already finished)
                return
            if not ok:
                raise FetchError(f"I couldn't go on ({msg}).")
            t0, seen_running, anchor = time.time(), False, None
            continue
        try:
            full = agv.status()
        except (ConnectionError, OSError):
            continue
        st = full.get("move_status")
        seen_running = seen_running or st == "running"
        pose = full.get("current_pose")
        if st == "running" and pose:
            if anchor is None or math.hypot(pose["x"] - anchor[0], pose["y"] - anchor[1]) > STUCK_M:
                anchor = (pose["x"], pose["y"], time.time())
            elif time.time() - anchor[2] > STUCK_S:
                agv.cancel()
                log(f"the base has not got anywhere for {STUCK_S:.0f} s at ({pose['x']:.2f}, {pose['y']:.2f}): cancelled")
                raise FetchError("I can't find a way there.", "그곳으로 가는 길을 못 찾겠어요.")
        if watch_holding and time.time() - last_hold >= HOLD_CHECK_S:
            last_hold = time.time()
            try:
                held = gripper.state()["holding"]
            except (ConnectionError, OSError, KeyError):
                held = True                  # one missed read: look again next second
            if not held:
                agv.cancel()
                _set(holding=False)
                skills._held.clear()
                raise FetchError("I dropped it.")
        if st != "running" and (seen_running or time.time() - t0 > DRIVE_START_S):
            if st != "succeeded":
                raise FetchError(f"I couldn't get there (base: {st}).")
            return


def _lift_to(mm):
    """Move the lift (slowly), the waist and head stay. The body's own stop does not stop a moveto: it runs to the end."""
    lift, waist, yaw, pitch = head.status()
    mm = max(LIFT_RANGE[0], min(LIFT_RANGE[1], mm))
    if abs(mm - lift) < 1.0:
        return
    _go_on()
    log(f"lift {lift:.0f} -> {mm:.0f} mm")
    head.moveto([mm, waist, yaw, pitch], vel=LIFT_VEL, acc=20, timeout=90)
    _go_on()


def _charging():
    try:
        return bool(agv.status().get("charge_state"))
    except (ConnectionError, OSError):
        return True                          # unknown: better not drive off


def arm_points_3d():
    """(x, y, z) mm in the arm base frame of the flange, the grasp point and the finger tips, from the joints now."""
    c = skills._ask("kine_forward", jointPosition=[float(v) for v in skills._joints()])["cartPosition"]
    R, f = calib.rpy_matrix(*c[3:]), np.array(c[:3])
    g = f + R @ skills.GRASP_OFFSET
    return [f, g, g + R @ [0.0, 0.0, skills.TIP_MM]]


def arm_points():
    """(x, y) m in the base frame of the flange, the grasp point and the finger tips: the parts of the arm that reach
    out past the base (in look the flange is ~0.4 m ahead of the base centre)."""
    return [to_base(p[:2], arm_yaw(), arm_xy()) for p in arm_points_3d()]


def depth_hits(deg, camera="torso", T=None):
    """Like turn_hits, with the torso depth camera: the arm's points along the turn at their real height (a table top's
    edge, a shelf: the lidar at the base's height does not see them), (x, y, z) mm in the arm frame now of the first
    one the camera sees something at or in front of; None when clear. Points out of its view are left to the lidar;
    depth on the arm's own parts (in view, within SELF_MM of them) does not count. Another camera: its name and its
    camera -> arm base transform T."""
    yaw = arm_yaw()
    T = skills.objects.base_from_camera() if T is None else T
    if yaw is None or T is None:
        return None
    pts, t, cam = arm_points_3d(), arm_xy(), T[:3, 3]
    n = max(1, math.ceil(abs(deg) / SWEEP_STEP_DEG))
    cand = []
    for k in range(1, n + 1):
        R = _rot(deg * k / n)
        for p in pts:
            xy = _rot(-yaw) @ (R @ to_base(p[:2], yaw, t) - t) * 1000.0
            cand.append(np.array([xy[0], xy[1], p[2]]))
    for c, h in zip(cand, skills.surface_points([tuple(c) for c in cand], camera=camera, T=T)):
        if h is None or min(np.linalg.norm(np.subtract(h, q)) for q in pts) < SELF_MM:
            continue
        if np.linalg.norm(np.subtract(h, cam)) <= np.linalg.norm(c - cam) + ARM_CLEAR_M * 1000.0:
            return c
    return None


def _head_to(yaw, pitch):
    """Turn the head (lift and waist stay) and wait until its frames are at rest."""
    lift, waist, _, _ = head.status()
    head.moveto([lift, waist, yaw, pitch])
    camview.want("head")
    time.sleep(HEAD_SETTLE_S)


def head_hits(deg):
    """depth_hits with the head camera turned towards the side of the turn: the torso camera sees only ahead, the arm
    sweeps to the side. None when clear, or when the head camera is not calibrated (then the other checks decide)."""
    side = math.copysign(HEAD_SIDE_DEG, deg)
    T = head_cam.base_from_head(side, HEAD_LOW_PITCH)
    if T is None:
        return None
    _, _, yaw0, pitch0 = head.status()
    try:
        _head_to(side, HEAD_LOW_PITCH)
        return depth_hits(deg, "head", T)
    finally:
        _head_to(yaw0, pitch0)


def turn_hits(deg):
    """The map point (x, y) where the arm would come closer than ARM_CLEAR_M to something the lidar or the map shows
    while the base turns by `deg`, checked every SWEEP_STEP_DEG along the way; None when the way is clear. The base
    itself turns in its own footprint; navigation does not know about the arm sticking out."""
    if arm_yaw() is None:
        return None
    pts, (x, y, th) = arm_points(), agv.pose()
    n = max(1, math.ceil(abs(deg) / SWEEP_STEP_DEG))
    for k in range(1, n + 1):
        R = _rot(math.degrees(th) + deg * k / n)
        for p in pts:
            w = np.array([x, y]) + R @ p
            if agv.clearance(*w) < ARM_CLEAR_M:
                return w
    return None


def _turn(deg, holding=False, why="to look further"):
    """Turn the base on the spot by `deg` (+ = left), arm in look (holding: it is there already), the lift where it
    is. False when it must not: charging, or the arm would hit something on the way (turn_hits)."""
    if _charging():
        log("on the charger: I don't turn")
        return False
    if not holding:
        _pose(_look())
    hit = turn_hits(deg)
    if hit is not None:
        log(f"not turning {deg:+.0f} deg: my arm would hit something at ({hit[0]:.2f}, {hit[1]:.2f})")
        return False
    seen = depth_hits(deg)
    if seen is not None:
        log(f"not turning {deg:+.0f} deg: the camera sees something in my arm's way at ({seen[0]:.0f}, {seen[1]:.0f}, "
            f"{seen[2]:.0f}) mm")
        return False
    seen = head_hits(deg)
    if seen is not None:
        log(f"not turning {deg:+.0f} deg: the head camera sees something in my arm's way at ({seen[0]:.0f}, "
            f"{seen[1]:.0f}, {seen[2]:.0f}) mm")
        return False
    log(f"turning {deg:+.0f} deg {why}")
    target = agv.pose()[2] + math.radians(deg)

    def rest():                                  # after a pause: only what is left of the turn
        left = (target - agv.pose()[2] + math.pi) % (2 * math.pi) - math.pi
        return (None, "done") if abs(left) < math.radians(TURN_MIN_DEG) else agv.turn_by(left)
    ok, msg = agv.turn_by(math.radians(deg))
    if not ok:
        raise FetchError(f"I couldn't turn ({msg}).")
    _wait_drive(watch_holding=holding, again=rest)
    return True


def _search(attempt, holding=False, say=None):
    """Run attempt() until it returns something: a whole turn on the spot (SEARCH_TURNS turns) at the lift it has,
    then the same at each of LIFT_TRIES; on the charger only the lifts. None when nothing was found."""
    here, step = head.status()[0], None
    for n, lift in enumerate([None] + [m for m in LIFT_TRIES if abs(m - here) >= 5.0]):
        if lift is not None:
            _lift_to(lift)
        for i in range(SEARCH_TURNS + 1):
            if i and step is None and not _charging():
                step = SEARCH_TURN_DEG * first_side()
            if i and not _turn(step or SEARCH_TURN_DEG, holding):
                break
            if n == 0 and i == 1:
                _say(say, "Let me look around.", "주변을 둘러볼게요.")
            got = attempt()
            if got is not None:
                return got
    return None


def first_side():
    """+1 (left) or -1 (right): the side where the lidar sees more things the map does not have (FURNITURE_*), the
    first way to turn when searching. ponytail: base-height lidar only (a table counts by its legs)."""
    x, y, th = agv.pose()
    seen = {}
    for side in (1, -1):
        seen[side] = 0
        for a in FURNITURE_ANGLES:
            for r in FURNITURE_RANGES:
                h = th + side * math.radians(a)
                live, mapped = agv.probe(x + r * math.cos(h), y + r * math.sin(h))
                seen[side] += live < FURNITURE_HIT_M and mapped > FURNITURE_MAP_M
    side = 1 if seen[1] >= seen[-1] else -1
    log(f"things around me: {seen[1]} on the left, {seen[-1]} on the right: turning {'left' if side > 0 else 'right'}")
    return side


def _find_any(task):
    try:
        return _find(task)
    except FetchError:
        return None


def surface_band(lift=None):
    """(low, high) mm, arm frame at the lift it has now: surfaces some lift in LIFT_RANGE brings into SURFACE_Z."""
    lift = head.status()[0] if lift is None else lift
    return SURFACE_Z[0] - lift + LIFT_RANGE[0], SURFACE_Z[1] - lift + LIFT_RANGE[1]


def lift_for(z):
    """The lift (mm) for working on a surface at `z` (arm frame now): the one bringing it nearest TABLE_PROVEN_Z,
    where every proven pick and place was; None when no lift brings it into SURFACE_Z."""
    lift = head.status()[0]
    target = max(LIFT_RANGE[0], min(LIFT_RANGE[1], lift + z - TABLE_PROVEN_Z))   # higher surface -> lift up
    return target if SURFACE_Z[0] <= z - (target - lift) <= SURFACE_Z[1] else None


def _fit_lift(table):
    """Set the lift for a table at `table` mm (arm frame; lift_for). True when the lift moved (look again)."""
    if table is None:
        log("table height not measured: the lift stays")
        return False
    target, lift = lift_for(table), head.status()[0]
    if target is None:
        log(f"surface at {table:.0f} mm is not one my arm can work at: the lift stays")
        return False
    if abs(target - lift) < LIFT_TOL_MM:
        log(f"table at {table:.0f} mm, but the lift is at its end ({lift:.0f} mm)")
        return False
    _lift_to(target)
    return True


def _drive_to(place, say, watch_holding=False):
    """Drive to "here" (where the task was given), {"marker"} or {"x", "y", "theta"} and wait."""
    _go_on()
    if place == "here":
        x, y, th = _task["start_pose"]
        px, py, pth = agv.pose()
        if math.hypot(x - px, y - py) < SAME_PLACE_M and \
                abs((th - pth + math.pi) % (2 * math.pi) - math.pi) < SAME_ANGLE_RAD:
            return
        place = {"x": x, "y": y, "theta": th}
    _lift_to(LIFT_DRIVE_MM)
    if "marker" in place:
        _say(say, f"Going to {place['marker']}.", f"{place['marker']} 위치로 갈게요.")
        go = lambda: agv.go(place["marker"])
    else:
        _say(say, "On my way.", "가는 중이에요.")
        go = lambda: agv.go_point(place["x"], place["y"], place["theta"])
    ok, msg = go()
    if not ok:
        raise FetchError(f"I couldn't start driving ({msg}).")
    _wait_drive(watch_holding, again=go)


# ---------- base shift ----------
def _waist_turn():
    """How far (deg) the waist is turned from where measure-axis was run (0 when that was not recorded). The arm and
    both cameras sit on the waist: they turn with it about the base centre. ponytail: waist axis taken at the base
    centre (the lift column, URDF); measure-axis again if the base shift misses after a waist turn."""
    try:
        ref = json.loads(CALIB_FILE.read_text()).get("waist_deg")
    except (FileNotFoundError, ValueError):
        return 0.0
    return 0.0 if ref is None else head.status()[1] - ref


def arm_yaw():
    """Angle (deg) of the arm base frame in the base frame, from measure-axis; None until it is measured."""
    try:
        return float(json.loads(CALIB_FILE.read_text())["arm_yaw_in_base_deg"]) + _waist_turn()
    except (FileNotFoundError, ValueError, KeyError):
        return None


def _rot(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


def arm_xy():
    """Arm base origin (m) in the base frame, as last learned by arm_offset() (0, 0 until then: approach() corrects
    the error by looking again after every move)."""
    try:
        return _rot(_waist_turn()) @ np.array(json.loads(CALIB_FILE.read_text())["arm_xy_in_base_m"], float)
    except (FileNotFoundError, ValueError, KeyError):
        return np.zeros(2)


def to_base(obj_xy, yaw_deg, t):
    """A point (mm, arm base frame) in the base frame (m)."""
    return _rot(yaw_deg) @ (np.asarray(obj_xy, float) / 1000.0) + t


def approach_move(obj_xy, yaw_deg, t, goal=PICK_ZONE_CENTRE):
    """(turn deg, then straight m) of the base that bring the object at `obj_xy` (mm, arm frame) to `goal`. The turn
    puts the object on the circle the goal reaches by a straight drive. None when the object is nearer the turning
    centre than the goal is from the drive line (back off first)."""
    o, d = to_base(obj_xy, yaw_deg, t), to_base(goal, yaw_deg, t)
    r2 = float(o @ o - d[1] ** 2)
    if r2 < 0:
        return None
    s = math.sqrt(r2) - d[0]
    turn = math.atan2(o[1], o[0]) - math.atan2(d[1], d[0] + s)
    return math.degrees((turn + math.pi) % (2 * math.pi) - math.pi), s


def side_pose(obj_world, heading, yaw_deg, t, back=STANDOFF_M, goal=PICK_ZONE_CENTRE):
    """Map pose (x, y, heading) from which a straight drive of `back` m brings the object at `obj_world` (map, m)
    to `goal`."""
    g = np.asarray(obj_world) - _rot(math.degrees(heading)) @ to_base(goal, yaw_deg, t)
    return g[0] - back * math.cos(heading), g[1] - back * math.sin(heading), heading


def arm_offset(seen1, seen2, yaw_deg):
    """Arm base origin (m) in the base frame from one object seen from two base poses that differ by a turn.
    seen = ((x, y, theta) map pose, (x, y) mm arm frame); the object stays put in the map."""
    (p1, a1), (p2, a2) = seen1, seen2
    R1, R2 = _rot(math.degrees(p1[2])), _rot(math.degrees(p2[2]))
    b = R2 @ to_base(a2, yaw_deg, 0) - R1 @ to_base(a1, yaw_deg, 0) + np.subtract(p2[:2], p1[:2])
    return np.linalg.solve(R1 - R2, b)


def yaw_from_shift(before_xy, after_xy, base_move):
    """Arm-frame yaw (deg) in the base frame: the base moved by `base_move` (m, base frame) and the object seemed
    to move from `before_xy` to `after_xy` (mm, arm frame), i.e. by -base_move in the base frame."""
    seen = np.subtract(after_xy, before_xy)
    a = math.atan2(-base_move[1], -base_move[0]) - math.atan2(seen[1], seen[0])
    return math.degrees((a + math.pi) % (2 * math.pi) - math.pi)


# ---------- steps ----------
def _find(task):
    try:
        return skills.find(task["object"], task.get("colour"))
    except skills.SkillError:
        thing = OBJECTS[task["object"]]
        raise FetchError(f"I can't see the {task['object']}.", f"{thing}{'이' if _object_particle(thing) == '을' else '가'} 안 보여요.")


def _carry_ok(waypoints, ja):
    """After the pick the arm goes straight up to above, then straight to carry with the cup: check that line now."""
    target = skills._ask("kine_forward", jointPosition=[float(v) for v in motion.poses()["carry"]])["cartPosition"]
    try:
        _line_rows(target, "to carry", start=(waypoints[0][1], ja))
        return True
    except FetchError:
        return False


def _reachable(obj):
    """(waypoints, joints above) of a pick from look (any grasp turn, either wrist) after which the cup can go
    straight to carry, else None. Wrong-size objects raise, but only when measured near: from further away the width
    is not trusted, the base goes closer and it is measured again."""
    try:
        return skills.reachable_pick(obj, accept=_carry_ok)
    except skills.SkillError:
        if math.hypot(obj["x"] - PICK_ZONE_CENTRE[0], obj["y"] - PICK_ZONE_CENTRE[1]) <= WIDTH_NEAR_MM:
            raise
        log(f"width {obj.get('width_mm')} mm measured from further away: I'll measure it again up close")
        return None


def _head_seen(task):
    """The task's object as the head camera sees it now ({"x", "y"} mm, arm frame), seen at least twice in
    HEAD_READS reads at about the same place; None when not."""
    hits = []
    for _ in range(HEAD_READS):
        for o in objects.latest("head")["objects"]:
            if o["name"] == task["object"] and task.get("colour") in (None, o.get("colour")) and o.get("position_mm"):
                hits.append(np.array(o["position_mm"][:2], float))
        time.sleep(0.3)
    for h in hits:
        near = [g for g in hits if np.linalg.norm(g - h) <= HEAD_SAME_MM]
        if len(near) >= 2:
            x, y = np.mean(near, axis=0)
            return {"x": float(x), "y": float(y)}
    return None


def _head_yaws(side):
    """Head yaws of one search: ahead, then up to HEAD_SCAN_MAX_DEG towards `side` (+1 left), then the other side."""
    n = int(HEAD_SCAN_MAX_DEG // HEAD_SCAN_STEP_DEG)
    steps = [k * HEAD_SCAN_STEP_DEG for k in range(1, n + 1)]
    return [0.0] + [side * a for a in steps] + [-side * a for a in steps]


def _head_search(task, side, say=None):
    """Look for the object with the head camera (_head_yaws): it sees further and to the sides than the torso camera.
    When found, turn the base to face it and drive straight towards it (checked moves), then find it with the torso
    camera. None when the head camera did not see it or the torso camera still can't."""
    _, _, yaw0, pitch0 = head.status()
    found = None
    try:
        for yaw in _head_yaws(side):
            _head_to(yaw, HEAD_LOW_PITCH)
            found = _head_seen(task)
            if found:
                log(f"the head camera sees the {task['object']} at ({found['x']:.0f}, {found['y']:.0f}) mm "
                    f"(head turned {yaw:+.0f} deg)")
                break
    finally:
        _head_to(yaw0, pitch0)
    if found is None:
        return None
    _say(say, "I see it. Going there.", "찾았어요. 그쪽으로 갈게요.")
    move = approach_move((found["x"], found["y"]), arm_yaw(), arm_xy())
    if move is None:
        return _find_any(task)
    turn, dist = move
    if abs(turn) >= TURN_MIN_DEG and not _turn(turn, why="to face it"):
        return None
    if dist > PROBE_STEP_M:
        _straight_clear(min(dist, HEAD_DRIVE_MAX_M))
    return _find_any(task)


def _look_around(task, say=None):
    """Search with the head before the base moves: the head looks to the side with more things (first_side) as far
    as it turns, then to the other side; then the base turns half round (checked turns) and the head looks again.
    Not found: the lift goes to its other end (down when it is up, up when it is down) and all of it again. Without
    a calibrated head camera: the base-turning search (_search)."""
    if head_cam.base_from_head(0.0, HEAD_LOW_PITCH) is None or arm_yaw() is None:
        return _search(lambda: _find_any(task), say=say)
    here = head.status()[0]
    other = LIFT_TRIES[1] if here < sum(LIFT_TRIES) / 2 else LIFT_TRIES[0]
    side = None
    for n, lift in enumerate((None, other)):
        if lift is not None:
            _lift_to(lift)
            got = _find_any(task)
            if got is not None:
                return got
        for half in range(2):
            if half and not _charging():
                if not all(_turn(side * 180.0 / BASE_HALF_STEPS) for _ in range(BASE_HALF_STEPS)):
                    break                          # a turn was refused: the rest of that half is not looked at
            elif half:
                break                              # on the charger: the head and the lifts only
            if side is None:
                side = first_side()
                _say(say, "Let me look around.", "주변을 둘러볼게요.")
            got = _head_search(task, side, say)
            if got is not None:
                return got
    return None


def _see(task, say=None):
    """Find the object here (else look with the head camera, else search by turning), fit the lift to its table and
    look once more."""
    obj = _find_any(task) or _look_around(task, say)
    if obj is None:
        _lift_to(LIFT_DRIVE_MM)
        thing = OBJECTS[task["object"]]
        raise FetchError(f"I looked all around, but I can't see the {task['object']}.",
                         f"주변을 다 봤는데 {thing}{'이' if _object_particle(thing) == '을' else '가'} 안 보여요.")
    return _fitted(task, obj)


def _fitted(task, obj):
    """Fit the lift to the table `obj` stands on; look once more when the lift moved."""
    table = skills.table_near(obj) or skills.table_z(obj)
    log(f"table at {table:.0f} mm" if table is not None else "table height not measured")
    if _fit_lift(table):
        obj = _find(task)
    log(f"found {obj['colour']} {obj['name']} at ({obj['x']:.0f}, {obj['y']:.0f}) top {obj['top_mm']:.0f}")
    return obj


def _straight_clear(dist, speed=None):
    """Drive straight by `dist` m (+ forward), only as far as the base keeps BASE_HALF_M + CLEAR_M from every obstacle
    the sensors and the map show (checked every PROBE_STEP_M before it starts; getting further from one is fine).
    Returns the distance driven (m)."""
    x, y, th = agv.pose()
    sign = 1.0 if dist > 0 else -1.0
    free, last = 0.0, agv.clearance(x, y)
    for k in range(1, int(abs(dist) / PROBE_STEP_M + 1e-9) + 1):
        c = agv.clearance(x + sign * k * PROBE_STEP_M * math.cos(th), y + sign * k * PROBE_STEP_M * math.sin(th))
        if c < BASE_HALF_M + CLEAR_M and c < last:
            log(f"an obstacle {c:.2f} m from the way after {free:.2f} m")
            break
        free, last = k * PROBE_STEP_M, c
    if free >= PROBE_STEP_M:
        log(f"straight {sign * free:+.2f} m")
        free = _straight(sign * free, speed or AXIS_SPEED)
    return free


def _approach(obj, yaw, tried, goal=PICK_ZONE_CENTRE, holding=False):
    """One base move that should bring `obj` (x, y in the arm frame) to `goal`: turn on the spot and drive straight
    when the way is short and free; else navigation (around obstacles) to a stand-off point on a side of it not in
    `tried`, facing it. FetchError when no side can be reached."""
    t = arm_xy()
    move = approach_move((obj["x"], obj["y"]), yaw, t, goal)
    if move is None:
        log("it is too near me: backing off")
        if _straight_clear(-STANDOFF_M) < PROBE_STEP_M:
            raise FetchError("It is too close to me and I can't back off.")
        return
    turn, s = move
    log(f"to bring it to ({goal[0]:.0f}, {goal[1]:.0f}): turn {turn:+.0f} deg, straight {s:+.2f} m")
    if abs(s) <= STRAIGHT_MAX_M:
        turned = abs(turn) < TURN_MIN_DEG or _turn(turn, holding, why="to face it")
        if turned:
            turn = 0.0
        if turned and (abs(s) < PROBE_STEP_M or _straight_clear(s) >= PROBE_STEP_M):
            return                                    # else the turn or the straight way is blocked: go round
    x, y, th = agv.pose()
    world = np.array([x, y]) + _rot(math.degrees(th)) @ to_base((obj["x"], obj["y"]), yaw, t)
    facing = th + math.radians(turn)
    _lift_to(LIFT_DRIVE_MM)
    for side in APPROACH_SIDES:
        if side in tried:
            continue
        tried.add(side)
        sx, sy, sth = side_pose(world, facing + math.radians(side), yaw, t, goal=goal)
        log(f"driving round to ({sx:.2f}, {sy:.2f}) to come in from {side:+d} deg")
        go = lambda: agv.go_point(sx, sy, (sth + math.pi) % (2 * math.pi) - math.pi)
        ok, msg = go()
        if not ok:
            log(f"no way there: {msg}")
            continue
        try:
            _wait_drive(watch_holding=holding, again=go)
            return
        except FetchError as e:
            log(f"no way there: {e}")
    raise FetchError("I can't find a way to get close to it.", "가까이 갈 길을 못 찾겠어요.")


def _learn_offset(before, after, yaw):
    """After a move with a turn: the arm base origin in the base frame from the object seen before and after; kept
    in CALIB_FILE when it is plausible (inside the base)."""
    if abs(math.degrees((after[0][2] - before[0][2] + math.pi) % (2 * math.pi) - math.pi)) < OFFSET_TURN_DEG:
        return
    t = arm_offset(before, after, yaw)
    if np.linalg.norm(t) > BASE_HALF_M * math.sqrt(2):
        log(f"arm offset {t.round(3)} m does not fit the base: not kept")
        return
    try:
        data = json.loads(CALIB_FILE.read_text())
    except (FileNotFoundError, ValueError):
        data = {}
    t = _rot(-_waist_turn()) @ t                  # kept as at the waist of measure-axis
    samples = (data.get("arm_xy_samples", []) + [[round(float(v), 3) for v in t]])[-OFFSET_SAMPLES:]
    mid = [round(float(v), 3) for v in np.median(samples, axis=0)]
    log(f"arm base measured at ({t[0]:.3f}, {t[1]:.3f}) m; median of {len(samples)}: ({mid[0]:.3f}, {mid[1]:.3f})")
    data.update(arm_xy_samples=samples, arm_xy_in_base_m=mid, arm_xy_measured=time.strftime("%Y-%m-%d %H:%M"))
    CALIB_FILE.write_text(json.dumps(data))


def remember(obj, yaw):
    """Where `obj` (arm frame) is on the map, to find it again after the base moved."""
    x, y, th = agv.pose()
    table = skills.table_z(obj)
    return {"world": np.array([x, y]) + _rot(math.degrees(th)) @ to_base((obj["x"], obj["y"]), yaw, arm_xy()),
            "top": obj["top_mm"], "table": table if table is not None else obj["top_mm"] - 100.0,
            "lift": head.status()[0], "obj": obj}


def expected(mem, yaw):
    """((x, y) arm frame mm, top mm, table mm) where a remembered object should be seen from here."""
    x, y, th = agv.pose()
    b = _rot(-math.degrees(th)) @ (mem["world"] - [x, y])
    xy = _rot(-yaw) @ (b - arm_xy()) * 1000.0
    down = head.status()[0] - mem["lift"]                 # the lift went up: the object is lower in the arm frame
    return (float(xy[0]), float(xy[1])), mem["top"] - down, mem["table"] - down


def _see_again(task, mem, yaw, say):
    """After a base move: the object by YOLO (its box measured with depth: what a pick may use). Not found: depth
    where it should be now (`mem`) says whether it is still there; back off a little, turn a little each way and
    look again. Depth sees only table where it was: someone took it, the whole search. Depth sees it but YOLO never
    does: ask the person. A pick never uses the depth-only position: it was 45 mm off once and the gripper knocked
    the cup over (2026-10-16)."""
    there = False
    for move in (None, -LOST_BACK_M, LOST_TURN_DEG, -2 * LOST_TURN_DEG):
        if move is not None and abs(move) < 1:
            _straight_clear(move)
        elif move is not None:
            _turn(move, why="to find it again")
        obj = _find_any(task)
        if obj is not None:
            return _fitted(task, obj)
        xy, top, table = expected(mem, yaw)
        how, got = skills.locate(xy, top, table, mem["obj"]["width_mm"])
        log(f"no box for it; depth where it should be ({xy[0]:.0f}, {xy[1]:.0f}): {how}")
        if how == "gone":
            _say(say, "It is not where I saw it. Let me look around.", "아까 본 자리에 없어요. 주변을 볼게요.")
            return _see(task, say)
        there = there or how == "here"
    if there:
        raise FetchError(f"Something is still where I saw the {task['object']}, but I can't see it well enough to "
                         "take it. Please move it a little.", "물건이 보이긴 하는데 잡을 만큼 잘 안 보여요. 조금 옮겨 주세요.")
    return _see(task, say)


def _reach(task, obj, say):
    """Step 5: (obj, waypoints, joints above) of a pick that passes IK. Out of reach: move the base (_approach) and look
    again, up to APPROACH_TRIES times (never on the charger); then ask the person to move it."""
    yaw, tried = arm_yaw(), set()
    for i in range(APPROACH_TRIES + 1):
        plan = _reachable(obj)
        if plan:
            return (obj, *plan)
        if yaw is None or i == APPROACH_TRIES or _charging():
            break
        _step(f"moving to reach it ({i + 1}/{APPROACH_TRIES})", say,
              *(("Let me get closer to it.", "가까이 가 볼게요.") if i == 0 else ()))
        before, mem = (agv.pose(), (obj["x"], obj["y"])), remember(obj, yaw)
        _pose(_look())
        _approach(obj, yaw, tried)
        obj = _see_again(task, mem, yaw, say)
        _learn_offset(before, (agv.pose(), (obj["x"], obj["y"])), yaw)
    _step("asking to move it closer", say, "I can't reach it, please move it closer to me.",
          "손이 닿지 않아요. 저에게 조금 더 가까이 놓아 주세요.")
    deadline = time.time() + ASK_WAIT_S
    while time.time() < deadline:
        if _stop.wait(ASK_EVERY_S):
            raise Stopped()
        try:
            obj = _find(task)
        except FetchError:
            continue
        plan = _reachable(obj)
        if plan:
            return (obj, *plan)
    raise FetchError("I still can't reach it.", "아직 손이 닿지 않아요.")


def table_ahead():
    """Height (mm) of the table in front: median depth surface over the place grid, only values near
    the arm can work at (surface_band) count; None when too little table is in view."""
    band = surface_band()
    zs = [z for z in skills.surface_heights([(x, y) for y in PLACE_GRID_Y for x in PLACE_GRID_X])
          if z is not None and band[0] <= z <= band[1]]
    return statistics.median(zs) if len(zs) >= 4 else None


def place_spots(held, base_now, seen, table=None):
    """Where the held object may go: the pick spot when the base has not moved since the pick, then free grid spots
    the depth camera sees as table at `table` mm (default: the pick table's height), nearest the pick zone centre
    first."""
    b0 = held.get("base")
    same = b0 is not None and math.hypot(base_now[0] - b0[0], base_now[1] - b0[1]) < SAME_BASE_M \
        and abs((base_now[2] - b0[2] + math.pi) % (2 * math.pi) - math.pi) < SAME_BASE_RAD
    tries = [(held["x"], held["y"])] if same else []
    others = [o for o in seen if not (same and math.hypot(o["x"] - held["x"], o["y"] - held["y"]) < skills.CLUSTER_MM)]
    table = held.get("table") if table is None else table
    if table is None:                    # the held one's bottom was out of view: another object on the table
        zs = [skills.table_z(o) for o in seen if skills.table_z(o) is not None]
        table = statistics.median(zs) if zs else None
    grid = sorted(((x, y) for y in PLACE_GRID_Y for x in PLACE_GRID_X
                   if all(math.hypot(x - o["x"], y - o["y"]) >= skills.FREE_MM for o in others)),
                  key=lambda p: math.hypot(p[0] - PICK_ZONE_CENTRE[0], p[1] - PICK_ZONE_CENTRE[1]))
    return tries + skills.on_table(grid, table)


def _place_here(top0):
    """One look for a place from where the arm is (look, the held object out of the view): measure the table, fit the
    lift, try the spots. True when the object was put down."""
    table = table_ahead()
    if _fit_lift(table):
        table = table_ahead()
    top, held_table = top0, skills._held.get("table")
    if table is not None and held_table is not None:
        top += table - held_table                     # the same object on a table this much higher / lower
    log(f"table here at {table:.0f} mm" if table is not None else "no table in view")
    if table is None:                    # never put it down on a table not measured right now
        return _to_far_table(top0)
    tries = place_spots(skills._held, agv.pose(), skills.look(), table)
    if not tries:
        return _to_far_table(top0)
    return _place_at(tries, top)


def _place_at(tries, top):
    """Put the held object down at the first of `tries` (x, y) whose way down passes IK. True when it is down."""
    log(f"place spots: {', '.join(f'({x:.0f}, {y:.0f})' for x, y in tries[:6])}")
    for x, y in tries:
        way = skills.plan_place(x, y, top, yaw=skills._held.get("yaw", 0.0))      # above place, place, release up
        try:
            over = _line_rows(way[0][1], f"to ({x:.0f}, {y:.0f})")
        except FetchError:
            continue
        rows = over[-1:] + skills.ik_chain(way[1:], over[-1][2])
        rows[0][0] = way[0][0]
        if not rows[-1][3]:
            _go_on()
            log(f"putting it down at ({x:.0f}, {y:.0f})")
            skills._guarded(lambda: motion.move_linear(target=way[0][1], speed=skills.HOLDING_SPEED,
                                                       path_checked=True))  # checked
            skills._guarded(skills._do_place, [(r[0], r[1]) for r in rows])   # ends at home (look), hand open
            _set(holding=False)
            _pose(_look())
            return True
        log(f"spot ({x:.0f}, {y:.0f}) refused at {rows[-1][0]}: {rows[-1][3]}")
    return None


def far_table():
    """(x, y) mm of a free table spot the torso depth camera sees beyond the place grid (the nearest whole one, its
    ring all table) and the table's height, or None. Surfaces no lift brings into SURFACE_Z are not
    tables (floor, low seats)."""
    pts = [(x, y) for y in FAR_GRID_Y for x in FAR_GRID_X]
    band = surface_band()
    hits = [(p, z) for p, z in zip(pts, skills.surface_heights(pts, TABLE_PROVEN_Z))
            if z is not None and band[0] <= z <= band[1]]
    if len(hits) < 4:
        return None
    table = statistics.median(z for _, z in hits)
    near = sorted((p for p, z in hits if abs(z - table) <= skills.TABLE_TOL_MM),
                  key=lambda p: math.hypot(p[0] - PLACE_GOAL[0], p[1] - PLACE_GOAL[1]))[:FAR_TRIES]
    spots = skills.on_table(near, table)
    return (spots[0], table) if spots else None


def _to_far_table(top0):
    """No place in reach but a table further away: bring the base to it (as for a pick) and look for a place
    again, up to APPROACH_TRIES times. None when there is no table in view or it can't be reached."""
    yaw, tried = arm_yaw(), set()
    for i in range(APPROACH_TRIES):
        far = far_table()
        if far is None or yaw is None or _charging():
            return None
        (x, y), table = far
        log(f"a table at {table:.0f} mm further away, free at ({x:.0f}, {y:.0f}): going closer ({i + 1}/{APPROACH_TRIES})")
        try:
            _approach({"x": x, "y": y}, yaw, tried, goal=PLACE_GOAL, holding=True)
        except FetchError as e:
            log(f"{e}")
            return None
        table = table_ahead()
        if _fit_lift(table):
            table = table_ahead()
        top, held_table = top0, skills._held.get("table")
        if table is not None and held_table is not None:
            top += table - held_table
        if table is None:
            continue
        tries = place_spots(skills._held, agv.pose(), skills.look(), table)
        if tries and _place_at(tries, top):
            return True
    return None


def known_things():
    """[{"name", "colour", "map": [x, y]}] taught with teach_thing()."""
    try:
        return json.loads(KNOWN_FILE.read_text())
    except (FileNotFoundError, ValueError):
        return []


def map_xy(obj):
    """Map position (m) of an object seen now (arm frame), or None until the arm's yaw is measured."""
    yaw = arm_yaw()
    if yaw is None:
        return None
    x, y, th = agv.pose()
    return np.array([x, y]) + _rot(math.degrees(th)) @ to_base((obj["x"], obj["y"]), yaw, arm_xy())


def colour_of(obj):
    """The taught colour of a thing seen within KNOWN_M of where it was taught, else the camera's: the colour read
    from a box changes with the view (a chair read grey, blue, orange and yellow while the robot moved, 2026-10-16)."""
    w = map_xy(obj)
    for k in known_things():
        if w is not None and k["name"] == obj["name"] and math.hypot(w[0] - k["map"][0], w[1] - k["map"][1]) < KNOWN_M:
            return k["colour"]
    return obj.get("colour")


def teach_thing(name, colour):
    """Remember the nearest `name` seen now as a `colour` one, by its place on the map. Returns it and its map place."""
    seen = [o for o in skills.look() if o["name"] == name]
    if not seen:
        raise FetchError(f"I can't see a {name} now.")
    o = min(seen, key=lambda o: math.hypot(o["x"], o["y"]))
    w = map_xy(o)
    if w is None:
        raise FetchError("I don't know where my arm is on the base yet.")
    things = [k for k in known_things() if not (k["name"] == name and math.hypot(w[0] - k["map"][0], w[1] - k["map"][1]) < KNOWN_M)]
    things.append({"name": name, "colour": colour, "map": [round(float(w[0]), 3), round(float(w[1]), 3)],
                   "taught": time.strftime("%Y-%m-%d %H:%M")})
    KNOWN_FILE.write_text(json.dumps(things, indent=1))
    return o, w


def _support(on):
    """The nearest thing of the class (and colour: the taught one first, colour_of) `on` names, or None."""
    seen = [o for o in skills.look() if o["name"] == on["name"] and (not on.get("colour") or colour_of(o) == on["colour"])]
    return min(seen, key=lambda o: math.hypot(o["x"], o["y"])) if seen else None


def _top_of(thing):
    """Height (mm) of the flat top of `thing` (a chair's seat, not its back): the median depth surface on a disc of
    SUPPORT_DISC_MM around its centre, below its highest point; None when too little of it is seen."""
    pts = [(thing["x"] + r * math.cos(a), thing["y"] + r * math.sin(a))
           for r in (0.0, SUPPORT_DISC_MM / 2, SUPPORT_DISC_MM) for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)]
    top = thing.get("top_mm") or TABLE_PROVEN_Z
    zs = [z for z in skills.surface_heights(pts, top - 150.0) if z is not None and z < top - 30.0]
    return statistics.median(zs) if len(zs) >= 6 else None


def _put_on(top0, on, say):
    """Put the held object on a named thing that is not a table (a chair, a couch...): find it (searching like for an
    object), measure its flat top, fit the lift and put it there when the arm can reach that height; else say why.
    A chair seat is ~30 cm lower than a table: the arm reaches no place there even at lift 0 (IK, 2026-10-16)."""
    label = " ".join(w for w in (on.get("colour"), on["name"]) if w)
    yaw, tried = arm_yaw(), set()
    for i in range(APPROACH_TRIES + 1):
        thing = _search(lambda: _support(on), holding=True, say=say)
        if thing is None:
            raise FetchError(f"I can't see the {label} around me.", "그 물건이 안 보여요.")
        surface = _top_of(thing)
        if surface is None:
            raise FetchError(f"I can't see the top of the {label} well enough.", "윗면이 잘 안 보여요.")
        off = surface - TABLE_PROVEN_Z
        log(f"{label} at ({thing['x']:.0f}, {thing['y']:.0f}), its top at {surface:.0f} mm")
        if lift_for(surface) is None:
            raise FetchError(f"The top of the {label} is {abs(off) / 10:.0f} cm {'lower' if off < 0 else 'higher'} "
                             "than a table: my arm can't put things there.", "높이가 맞지 않아서 거기에는 놓을 수 없어요.")
        if _fit_lift(surface):
            continue                                  # look again from the new height
        held_table = skills._held.get("table")
        top = top0 + (surface - held_table if held_table is not None else 0.0)
        spots = skills.on_table([(thing["x"] + dx, thing["y"] + dy) for dx in (0, -50, 50) for dy in (0, -50, 50)],
                                surface)
        if spots and _place_at(spots, top):
            return True
        if yaw is None or i == APPROACH_TRIES or _charging():
            break
        _approach({"x": thing["x"], "y": thing["y"]}, yaw, tried, goal=PLACE_GOAL, holding=True)
    raise FetchError(f"I couldn't reach a free spot on the {label}.", "놓을 자리에 손이 닿지 않아요.")


def _put_down(say=None, on=None):
    """Straight to look with the object (carry hides the table from the torso camera), then search for a free
    table spot: here, a table further away (the base goes closer), at other lifts, turning on the spot; put it
    down, back to look. `on` (brain.place_on): put it on that named thing instead (a table: as above)."""
    top = skills._held.get("top_mm")
    if top is None:
        raise FetchError("I'm not holding anything I picked.")
    _step("placing")
    _line_holding(LOOK_POSE)
    if on and (on.get("name") != "dining table" or on.get("colour")):
        _put_on(top, on, say)                       # a chair, or "the white table": that thing, by colour
        return
    if _search(lambda: _place_here(top), holding=True, say=say) is None:
        _lift_to(LIFT_DRIVE_MM)
        raise FetchError("I can't find a free place on a table around me.", "주변에 내려놓을 빈 자리를 못 찾았어요.")


def _give(say):
    """Look -> give (straight), open on "thank you" / Release, then look. No release within GIVE_WAIT_S:
    back to look, still holding it; returns "kept"."""
    _line_holding("give")
    _release.clear()
    _step("giving", say, "Here you go. Hold it and say thank you.", "여기 있어요. 잡고 고맙다고 말해 주세요.")
    t0 = time.time()
    while time.time() - t0 < GIVE_WAIT_S and not _release.is_set():
        if _stop.wait(GIVE_POLL_S):
            raise Stopped()
    if not _release.is_set():
        _say(say, "Nobody took it, I'll keep holding it.", "아무도 안 받아서 계속 들고 있을게요.")
        _line_holding(LOOK_POSE)
        return "kept"
    _go_on()
    log("opening")
    gripper.open_()
    skills._held.clear()
    _set(holding=False)
    _pose(_look())


def _run(task, say):
    try:
        _step("preparing")
        if gripper.open_()["closed"]:          # always open: AI_1 may say open while the fingers are shut
            raise FetchError("My hand does not open.", "손이 안 열려요.")
        _pose(_look())
        _step("driving to the source")
        _drive_to(task.get("source", "here"), say)
        _pick_here(task, say)
        _step("driving to the destination")
        _drive_to(task["dest"], say, watch_holding=True)
        _say(say, "I'm here.", "도착했어요.")
        if task["finish"] == "place":
            _put_down(say)
            _lift_to(LIFT_DRIVE_MM)
            _set(status="done", step="")
        else:
            _set(status="holding", step="")
        log(_state["status"])
    except Exception as e:
        _fail(e, say)


def _pick_here(task, say):
    """Find task["object"] (colour) here, reach it (base moves if needed), pick it and bring it to look."""
    _step("looking")
    obj = _see(task, say)
    _step("reaching")
    obj, waypoints, ja = _reach(task, obj, say)
    _step("picking")
    skills._guarded(skills._do_pick, obj, waypoints, ja)   # ends 3 cm above the table, holding
    skills._held["base"] = agv.pose()                       # place_spots: put back here if the base stays
    _set(holding=True)
    _say(say, "I've got it.", "잡았어요.")
    _step("carry")
    skills._guarded(skills._line, "up", waypoints[0][1])   # straight up to the approach height first
    _line_holding("carry")                                   # straight: the cup stays upright (a turned grasp
    _line_holding(LOOK_POSE)                                 # can't go straight to look), then look to drive


def _fail(e, say):
    """End of a run that did not finish: stopped (STOP pressed) or failed with a spoken reason."""
    if _stop.is_set() or isinstance(e, Stopped):
        _set(status="stopped")
        log("stopped")
        return
    en = e.args[0] if e.args else str(e)
    ko = e.args[1] if isinstance(e, FetchError) and len(e.args) > 1 else "문제가 생겨서 멈췄어요."
    if not isinstance(e, (FetchError, skills.SkillError)):
        log(f"error: {type(e).__name__}: {e}")
        en = "Something went wrong, I stopped."
        try:
            motion.stop()
        except Exception:
            pass
    _set(status="failed")
    log(f"failed: {en}")
    _say(say, en, ko)


def _clear():
    """Before a run: a stop() from now on stays set for the whole run (skills.pick() would clear it itself)."""
    _stop.clear()
    _pause.clear()
    skills._cancel.clear()


def _launch(fn, *a):
    global _thread
    _thread = threading.Thread(target=fn, args=a, daemon=True)
    _thread.start()


def _busy():
    return _thread is not None and _thread.is_alive()


# ---------- public ----------
def _in_hand():
    """Is something in the hand, whatever the state file says? The torso depth camera first (skills.hand_sees: it
    sees the place between the fingers); when it can't tell, the gripper's AI_1. AI_1 alone was wrong once: a cup
    pulled out of the closed fingers left it reading "open" (2026-10-16)."""
    try:
        seen = skills.hand_sees()
    except (skills.SkillError, ConnectionError, OSError, KeyError):
        seen = "unknown"
    try:
        ai = bool(gripper.state()["holding"])
    except (ConnectionError, OSError, KeyError):
        ai = None
    if seen == "unknown":
        return bool(ai)
    if ai is not None and ai != (seen == "object"):
        log(f"hand: the camera sees it {seen}, AI_1 says {'holding' if ai else 'empty'}: the camera is believed")
    return seen == "object"


def check_hand():
    """Bring the state in line with the hand (_in_hand) while no task runs: forget a held object that is gone, take
    over one that is there. Returns whether something is held. The dashboard's command dialog asks this."""
    _adopt()                                     # what the state file says (another process, or before a restart)
    with _lock:
        if _busy():
            return bool(_state["holding"])
        held = _in_hand()
        if _state["holding"] and not held:
            _forget_held()
        elif held and not _state["holding"]:
            _set(holding=True)
        return held


def _forget_held():
    log("the state says holding, but the hand is empty: nothing is held")
    _set(holding=False, **({"status": "idle", "step": ""} if _state["status"] == "holding" else {}))
    skills._held.clear()


def start(task, say=None):
    """Start `task` in the background. FetchError when busy, holding something or the task is invalid."""
    _adopt()
    with _lock:
        if _busy():
            raise FetchError("I'm busy with another task.")
        held = _in_hand()
        if _state["holding"] and not held:              # taken out of the hand since: forget it
            _forget_held()
        if held:
            _set(holding=True)
            raise FetchError("I'm holding something, where should I put it first?")
    problems = validate(task, agv.markers() if _needs_markers(task) else [])
    if problems:
        raise FetchError(" ".join(problems))
    _task["start_pose"] = agv.pose()
    _clear()
    _set(status="running", step="", task=task, log=[])
    log(f"task: {describe(task)}")
    _launch(_run, task, say)


def _needs_markers(task):
    return any(isinstance(task.get(k), dict) and "marker" in task[k] for k in ("source", "dest"))


def _finish(fn, say):
    _adopt()
    with _lock:
        if _busy():
            raise FetchError("I'm busy with another task.")
        held = _in_hand()
        if not held:
            if _state["holding"]:
                _forget_held()
            raise FetchError("My hand is empty, I'm not holding anything.", "손에 아무것도 없어요.")
        if not _state["holding"]:
            _set(holding=True)                    # the state was lost; give still works, place needs skills._held
    _clear()
    _set(status="running")

    def run():
        try:
            if fn(say) == "kept":
                _set(status="holding", step="holding")
                return
            _lift_to(LIFT_DRIVE_MM)
            _set(status="done", step="")
            _say(say, "Done.", "다 했어요.")
            log("done")
        except Exception as e:
            _fail(e, say)
    _launch(run)


def give(say=None):
    """Hand the held object to the person in front."""
    if "give" not in motion.poses():
        raise FetchError("I haven't learned how to hand things over yet.")
    _finish(_give, say)


def place(say=None, on=None):
    """Put the held object on the table in front, or on the thing `on` names (brain.place_on)."""
    _finish(lambda s: _put_down(s, on), say)


THEN = (None, "place", "give")       # after carry_to: keep holding it, put it on a table there, hand it over


def carry_to(dest, then=None, say=None, on=None):
    """Bring the held object to `dest` (marker / map point) in look, then keep holding it, put it on a table there
    ("place") or hand it over ("give")."""
    if not _place_ok(dest, agv.markers() if isinstance(dest, dict) and "marker" in dest else []):
        raise FetchError("I don't know that place.")
    if then not in THEN:
        raise FetchError(f"After driving I can only {', '.join(t for t in THEN if t)} or keep holding it.")
    if then == "give" and "give" not in motion.poses():
        raise FetchError("I haven't learned how to hand things over yet.")
    _finish(lambda s: _carry_to(dest, s, then, on), say)


def _carry_to(dest, say, then=None, on=None):
    _line_holding(LOOK_POSE)
    _step("driving to the destination")
    _drive_to(dest, say, watch_holding=True)
    _say(say, "I'm here.", "도착했어요.")
    if then == "place":
        return _put_down(say, on)
    if then == "give":
        return _give(say)
    return "kept"


# ---------- missions (docs/17): a list of steps ----------
def run_steps(steps, say=None, sender=None):
    """Start a mission (assistant/steps.py) in the background. FetchError when busy or when the steps don't fit the
    hand or the map (steps.check)."""
    from assistant import steps as steps_mod
    _adopt()
    with _lock:
        if _busy():
            raise FetchError("I'm busy with another task.")
        held = _in_hand()
        if _state["holding"] and not held:
            _forget_held()
        if held and not _state["holding"]:
            _set(holding=True)
    problems = steps_mod.check(steps, held, agv.markers())
    if problems:
        raise FetchError(" ".join(problems))
    steps = [dict(s, to=random.choice(s["to"])) if s["do"] == "go" and isinstance(s["to"], list) else s
             for s in steps]                     # "one of p3, p5, p7": chosen now, said when it starts
    _task["start_pose"] = agv.pose()
    _clear()
    _proceed.clear()
    _order["steps"] = None
    _set(status="running", step="", task={"steps": steps, "sender": sender}, log=[], waiting=None)
    log(f"mission: {steps_mod.describe(steps)}")
    _launch(_run_steps, steps, say)


def _run_steps(steps, say):
    global _rest
    try:
        todo, done, at, stay = list(steps), [], None, False
        while todo:
            s = todo.pop(0)
            _rest = todo
            _go_on()
            log(f"step {len(done) + 1}/{len(done) + 1 + len(todo)}: {s}")
            if s == {"do": "wait", "s": None} and not todo:
                stay = True                          # "go to p3 and stay there": the mission ends there, waiting
            elif s["do"] == "wait":
                new = _wait(s, at, say)
                if new:                              # an instruction from the person here: done now, then the rest
                    todo[:0] = new
                    _set(task={**(_state.get("task") or {}), "steps": done + [s] + todo})
            elif s["do"] == "receive":
                _receive(s.get("object"), say, s.get("wait_s"), at)
            else:
                _do_step(s, say)
            done.append(s)
            at = s["to"] if s["do"] == "go" else None if s["do"] in ("move", "turn") else at
        if stay:
            _lift_to(LIFT_DRIVE_MM)
            _set(status="holding" if _state["holding"] else "waiting", step=f"waiting {_where(at)}",
                 waiting={"at": at, "for": "stay", "end": None})
            _say(say, "I'll wait here.", "여기서 기다릴게요.")
        elif _state["holding"]:
            _set(status="holding", step="holding")
        else:
            _lift_to(LIFT_DRIVE_MM)
            _set(status="done", step="")
            _say(say, "Done.", "다 했어요.")
        log(_state["status"])
    except Exception as e:
        _fail(e, say)


def _do_step(s, say):
    d, holding = s["do"], _state["holding"]
    if d == "go":
        if holding:
            _line_holding(LOOK_POSE)
        else:
            _pose(_look())
        _step(f"driving to {s['to']}")
        _drive_to("here" if s["to"] == "here" else {"marker": s["to"]}, say, watch_holding=holding)
        _say(say, "I'm here.", "도착했어요.")
    elif d == "move":
        _move(s["dir"], s["m"], holding)
    elif d == "turn":
        _step(f"turning {s['deg']:+.0f} deg")
        if not _turn(s["deg"], holding, why="as asked"):
            raise FetchError("I can't turn here: my arm would hit something, or I'm on the charger.",
                             "여기서는 돌 수 없어요.")
    elif d == "pick":
        if gripper.open_()["closed"]:
            raise FetchError("My hand does not open.", "손이 안 열려요.")
        _pose(_look())
        _pick_here({"object": s["object"], "colour": s.get("colour")}, say)
        _set(task={**(_state.get("task") or {}), "object": s["object"], "colour": s.get("colour")})   # held_name
    elif d == "receive":
        _receive(s.get("object"), say)
    elif d == "say":
        _step("speaking")
        _say(say, s["text"], s["text"])
    elif d == "place":
        on = s.get("on")
        if on and on.get("side"):                    # "the table on your left": turn to that side first
            _line_holding(LOOK_POSE)
            _step(f"turning {on['side']}")
            if not _turn(90.0 if on["side"] == "left" else -90.0, True, why=f"to the {on['side']}"):
                raise FetchError(f"I can't turn {on['side']} here: my arm would hit something, or I'm on the charger.",
                                 "여기서는 돌 수 없어요.")
        _put_down(say, on)
        if _state["holding"]:
            raise FetchError("I couldn't put it down.", "내려놓지 못했어요.")
    elif d == "give":
        if "give" not in motion.poses():
            raise FetchError("I haven't learned how to hand things over yet.")
        if _give(say) == "kept":
            raise FetchError("Nobody took it, I'm still holding it.", "아무도 안 받아서 계속 들고 있어요.")
    elif d == "arm":
        _arm(s["pose"])
    # "hold": nothing to do, the mission ends holding


def _where(at):
    return f"at {at}" if at and at != "here" else "here"


def _wait(s, at, say):
    """A wait step: s["s"] seconds (time paused for someone talking does not count), or until "go on" (proceed())
    when None; with "until": "instruction" until the person here gives one (instruct()), at most s["s"]. "Go on" ends
    any wait. Returns the instruction's steps, or []. No instruction in time: said, and the mission goes on."""
    from assistant import steps as steps_mod
    kind = "instruction" if s.get("until") else "time" if s["s"] is not None else "go on"
    _proceed.clear()
    _order["steps"] = None
    en, ko = {"instruction": ("I'll wait here. Tell me what I should do.", "여기서 기다릴게요. 무엇을 할지 말씀해 주세요."),
              "time": (f"I'll wait {steps_mod._dur(s['s'] or 0)}.", f"{steps_mod._dur(s['s'] or 0, True)} 기다릴게요."),
              "go on": ("I'll wait here until you tell me to go on.", "가도 된다고 하실 때까지 여기서 기다릴게요.")}[kind]
    end = None if s["s"] is None else time.time() + s["s"]
    _step(f"waiting {_where(at)}", say, en, ko)
    _set(waiting={"at": at, "for": kind, "end": end})
    try:
        while end is None or time.time() < end:
            if _pause.is_set():
                t0 = time.time()
                _go_on()
                if end is not None:
                    end += time.time() - t0
                    _set(waiting={"at": at, "for": kind, "end": end})
            if _stop.wait(WAIT_POLL_S):
                raise Stopped()
            if _proceed.is_set():
                log("told to go on")
                return []
            if _order["steps"]:
                got, _order["steps"] = _order["steps"], None
                log(f"instruction: {got}")
                return got
        if kind == "instruction":
            _say(say, "Nobody told me what to do, I'll go on.", "아무도 일을 시키지 않아서 계속할게요.")
        return []
    finally:
        _set(waiting=None)


def proceed():
    """"Go on" while a mission waits (a wait step): the rest of the mission now."""
    _proceed.set()


def instruct(new_steps):
    """The person at the place gives the instruction a wait step waits for ("go to p6 and do what they tell you"):
    `new_steps` are done there, then the rest of the mission. "here" in them is that place. FetchError when no such
    wait runs, when they ask for another such wait, or when they don't fit the hand / the map (steps.check)."""
    from assistant import steps as steps_mod
    w = _state.get("waiting") or {}
    if not _busy() or w.get("for") != "instruction":
        raise FetchError("I'm not waiting for an instruction.", "지금은 지시를 기다리고 있지 않아요.")
    if any(isinstance(s, dict) and s.get("do") == "wait" and s.get("until") for s in new_steps or []):
        raise FetchError("I can take one instruction here, not wait for another one.", "여기서는 한 번만 지시를 받을 수 있어요.")
    problems = steps_mod.check(list(new_steps or []) + list(_rest), _state["holding"], agv.markers())
    if problems:
        raise FetchError(" ".join(problems))
    here = w.get("at") if w.get("at") not in (None, "here") else "here"
    _order["steps"] = [dict(s, to=here if s["to"] == "here" else random.choice(s["to"]) if isinstance(s["to"], list)
                            else s["to"]) if s["do"] == "go" else s for s in new_steps]


def line_hits(dist):
    """Like turn_hits for a straight drive of `dist` m (+ forward): the map point where the arm would come closer than
    ARM_CLEAR_M to something the lidar or the map shows, checked every PROBE_STEP_M; None when clear."""
    if arm_yaw() is None:
        return None
    pts, (x, y, th) = arm_points(), agv.pose()
    R, u = _rot(math.degrees(th)), np.array([math.cos(th), math.sin(th)])
    n = max(1, math.ceil(abs(dist) / PROBE_STEP_M))
    for k in range(1, n + 1):
        for p in pts:
            w = np.array([x, y]) + R @ p + u * dist * k / n
            if agv.clearance(*w) < ARM_CLEAR_M:
                return w
    return None


def _move(direction, m, holding):
    """Drive `m` metres forward / back, or turn 90 deg left / right (arm sweep checked) and drive forward. Straight
    with joy_control in MOVE_SEGMENT_M pieces; before each the base's way (_straight_clear) and the arm's (line_hits)
    are checked again with the live lidar, and a held object is checked after it. Stopped short -> FetchError."""
    if holding:
        _line_holding(LOOK_POSE)
    else:
        _pose(_look())
    if direction in ("left", "right"):
        _step(f"turning {direction}")
        if not _turn(90.0 if direction == "left" else -90.0, holding, why=f"to drive {direction}"):
            raise FetchError(f"I can't turn {direction} here: my arm would hit something, or I'm on the charger.",
                             "여기서는 돌 수 없어요.")
    elif direction == "back" and _charging():
        raise FetchError("I'm on the charger: I won't drive back into it.", "충전 중이라 뒤로 갈 수 없어요.")
    _lift_to(LIFT_DRIVE_MM)
    sign = -1.0 if direction == "back" else 1.0
    _step(f"driving {m:g} m {'back' if direction == 'back' else 'forward'}")
    done = 0.0
    while m - done >= PROBE_STEP_M - 1e-9:
        _go_on()
        piece = min(MOVE_SEGMENT_M, m - done)
        hit = line_hits(sign * piece)
        if hit is not None:
            raise FetchError(f"My arm would hit something: I stopped after {done:.2f} m of {m:g}.",
                             f"팔이 부딪힐 것 같아서 {done:.2f}미터에서 멈췄어요.")
        cut = _pause.is_set
        got = _straight_clear(sign * piece, MOVE_SPEED)
        done += got
        if cut():                                # someone stopped me: wait, then the rest of the way, checked again
            _go_on()
            continue
        if holding and not gripper.state()["holding"]:
            skills._held.clear()
            _set(holding=False)
            raise FetchError("I dropped it.", "떨어뜨렸어요.")
        if got < piece - PROBE_STEP_M + 1e-9:
            raise FetchError(f"Something is in my way: I stopped after {done:.2f} m of {m:g}.",
                             f"앞에 뭔가 있어서 {done:.2f}미터에서 멈췄어요.")


def _receive(name, say, wait_s=None, at=None):
    """Hold the open hand out (give pose), ask for the object, close when the finger sensor (DI_1) has seen something
    for RECEIVE_DI_S, check the hand holds it. Nothing within RECEIVE_WAIT_S (wait_s: "wait until someone gives you
    the cup"): hand open, FetchError, the mission ends there."""
    if "give" not in motion.poses():
        raise FetchError("I haven't learned how to hold my hand out yet.")
    if gripper.open_()["closed"]:
        raise FetchError("My hand does not open.", "손이 안 열려요.")
    _pose("give")
    thing, ko = name or "it", OBJECTS.get(name, "물건")
    _step("receiving", say, f"Please put the {thing} in my hand." if name else "Please put it in my hand.",
          f"제 손에 {ko}{_object_particle(ko)} 넣어 주세요.")
    t0, seen_since = time.time(), None
    if wait_s:
        _set(waiting={"at": at, "for": "person", "object": name, "end": t0 + wait_s})
    while time.time() - t0 < (wait_s or RECEIVE_WAIT_S):
        if _stop.wait(GIVE_POLL_S):
            raise Stopped()
        try:
            front = gripper.state()["object_in_front"]
        except (ConnectionError, OSError, KeyError):
            continue
        seen_since = (seen_since or time.time()) if front else None
        if seen_since and time.time() - seen_since >= RECEIVE_DI_S:
            break
    else:
        _set(waiting=None)
        _pose(_look())
        raise FetchError(f"Nobody gave me the {thing}.", "아무도 주지 않았어요.")
    _set(waiting=None)
    _release.clear()                             # their fingers may still be in my hand: close only on their word
    _step("receiving: waiting for okay", say, "Let go of it, then say okay.", "손을 놓고 됐다고 말해 주세요.")
    t0 = time.time()
    while not _release.is_set():
        if _stop.wait(GIVE_POLL_S):
            raise Stopped()
        if time.time() - t0 > RECEIVE_WAIT_S:
            _pose(_look())
            raise FetchError("Nobody said okay, I didn't close my hand.", "확인이 없어서 손을 닫지 않았어요.")
    if not gripper.state()["object_in_front"]:
        _pose(_look())
        raise FetchError(f"The {thing} is not in my hand any more.", "손에 아무것도 없어요.")
    log("something in the hand and okay: closing")
    st = gripper.close()
    if not st.get("holding"):
        gripper.open_()
        _pose(_look())
        raise FetchError("I couldn't hold it, my hand closed on nothing.", "잡지 못했어요.")
    skills._held.clear()                         # nothing measured: where it sits in the hand is not known
    skills._held["received"] = True
    _set(holding=True, task={**(_state.get("task") or {}), "object": name})
    _say(say, "Thank you, I've got it.", "고마워요, 받았어요.")
    _line_holding(LOOK_POSE)


def _arm(pose):
    if pose in ("open", "close"):
        st = gripper.open_() if pose == "open" else gripper.close()
        if pose == "open":
            skills._held.clear()
            _set(holding=False)
        log(f"gripper {pose}: {st}")
    elif pose == "fold":
        _pose("tuck")
    elif pose == "reach":                        # the hand held out, as for a hand-over
        if "give" not in motion.poses():
            raise FetchError("I haven't learned how to reach out yet.")
        _pose("give")


def held_name():
    """"the white cup" / "the cup": what the last fetch took, for "I'm holding the cup"."""
    t = _state.get("task") or state().get("task") or {}
    return " ".join(["the"] + [w for w in (t.get("colour"), t.get("object")) if w]) if t.get("object") else "something"


def carry_sentence(dest, then=None):
    m = dest.get("marker") if isinstance(dest, dict) else None
    where = m or "the point I was shown"
    rest = {"place": "put it on the table there", "give": "hand it to you"}.get(then, "keep holding it")
    return f"Bring it to {where} and {rest}."


def release_now():
    """The person said "thank you" while Lumi is giving: open now."""
    _release.set()


def replace(steps, say=None):
    """The person a mission is for takes it here or changes it: end the rest of this run, start `steps`."""
    sender = ((_state.get("task") or {}).get("sender"))
    stop()
    if _thread is not None:
        _thread.join(30)
    run_steps(steps, say, sender)


def pause():
    """Someone talks to Lumi on the way: halt the base now (an arm move in progress ends first), the run waits at its
    next step until resume(). False when no run is going."""
    if not _busy() or _pause.is_set():
        return False
    _pause.set()
    try:
        agv.cancel()
    except Exception as e:
        log(f"pause: base cancel failed: {e}")
    _set(paused=True)
    return True


def resume():
    """Go on after pause(): the drive or turn goes on where it was."""
    if _pause.is_set():
        _pause.clear()
        _set(paused=False)


def paused():
    return _pause.is_set()


def stop():
    """Stop the base, the arm and any waiting at once; the gripper keeps its state."""
    _stop.set()
    for fn in (skills.cancel, agv.cancel):
        try:
            fn()
        except Exception as e:           # try every stop even when one of them fails
            log(f"stop: {fn.__module__}.{fn.__name__} failed: {e}")
    if _state["status"] in ("running", "holding", "waiting"):
        _set(status="stopped")
        log("stopped")


# ---------- measuring the arm's yaw on the base ----------
def _straight(dist_m, speed=None):
    """Drive straight by dist_m (+ forward) at `speed` (AXIS_SPEED) with joy_control (no turning), then stop.
    Stopped() on STOP; a pause stops it early. Returns the distance driven (m, by time)."""
    speed = speed or AXIS_SPEED
    t0 = time.time()
    t_end = t0 + abs(dist_m) / speed
    v = speed if dist_m > 0 else -speed
    try:
        while time.time() < t_end and not _stop.is_set() and not _pause.is_set():
            agv.request(f"/api/joy_control?linear_velocity={v:.3f}&angular_velocity=0")
            time.sleep(0.1)
    finally:
        agv.request("/api/joy_control?linear_velocity=0&angular_velocity=0")
    if _stop.is_set():
        raise Stopped()
    time.sleep(COAST_S)
    return abs(dist_m) if time.time() >= t_end else min(abs(dist_m), (time.time() - t0) * speed)


def yaw_from_motion(pairs, move, dtheta):
    """Arm-frame yaw (deg) in the base frame from objects seen before / after a base move.
    pairs: [((x, y) before, (x, y) after)] mm in the arm frame; move: (dx, dy) m in the base frame; dtheta: rad the
    base turned on the way. A point fixed in the room ends at rot(-dtheta) (p - move) in the base frame (the arm base's
    own offset from the turning centre is left out: a few mm for the small turns here). Best yaw by a 0.1 deg search."""
    def err(yaw):
        R = _rot(yaw)
        total = 0.0
        for before, after in pairs:
            pb = R @ np.asarray(before, float)
            want = _rot(-math.degrees(dtheta)) @ (pb - np.asarray(move, float) * 1000.0) - pb
            total += float(np.sum((R @ np.subtract(after, before) - want) ** 2))
        return total
    return float(min(np.arange(-180.0, 180.0, 0.1), key=err))


def _pairs(before, after):
    """Objects of the same class seen in both looks, matched nearest first (they moved by about the base move); each
    object of the second look is matched once (two cups seen before and one after gave one wrong pair)."""
    cand = sorted((np.hypot(a["x"] - b["x"], a["y"] - b["y"]), i, k) for i, b in enumerate(before)
                  for k, a in enumerate(after) if a["name"] == b["name"])
    out, used_b, used_a = [], set(), set()
    for _, i, k in cand:
        if i not in used_b and k not in used_a:
            used_b.add(i)
            used_a.add(k)
            b, a = before[i], after[k]
            out.append(((b["x"], b["y"]), (a["x"], a["y"]), b["name"]))
    return out


def measure_axis(name=None):
    """Arm at ready, a few objects in view: drive AXIS_STEP_M straight forward and back, fit the yaw from every object
    seen both times (or only `name`), write CALIB_FILE. The base always drives back, also after an error."""
    _stop.clear()
    j = skills._joints()
    if all(max(abs(a - b) for a, b in zip(j, motion.nearest(motion.poses()[n], j))) > 1.0 for n in {_look(), "ready"}):
        sys.exit(f"put the arm in {_look()} first: python robot/motion.py go {_look()}")
    steady = lambda seen: [o for o in seen if o["seen"] >= skills.MIN_SEEN and o["spread"] <= skills.SPREAD_MM
                           and (name is None or o["name"] == name)]
    before = steady(skills.look())
    if not before:
        sys.exit("nothing steady in view")
    p0 = agv.pose()
    print(f"before: base {p0}; " + ", ".join(f"{o['name']} ({o['x']:.0f}, {o['y']:.0f})" for o in before))
    x, y, th = p0
    moved = False
    try:
        moved = True
        _straight(AXIS_STEP_M)
        time.sleep(1.0)                              # let the camera service see the new view
        after = steady(skills.look())
        p1 = agv.pose()
    finally:
        if moved:
            p_now = agv.pose()
            _straight(-(_rot(-math.degrees(th)) @ [p_now[0] - x, p_now[1] - y])[0])
    move = _rot(-math.degrees(th)) @ [p1[0] - x, p1[1] - y]           # the move as made, in the base frame
    dth = (p1[2] - th + math.pi) % (2 * math.pi) - math.pi
    pairs = _pairs(before, after)
    print(f"base moved {move.round(3)} m, turned {math.degrees(dth):.2f} deg; seen both times: "
          + ", ".join(f"{n} {b} -> {a}" for b, a, n in pairs))
    if not pairs:
        sys.exit("no object was seen both times: nothing written")
    yaw = yaw_from_motion([(b, a) for b, a, _ in pairs], move, dth)
    CALIB_FILE.write_text(json.dumps({"arm_yaw_in_base_deg": round(yaw, 1), "objects": [n for *_, n in pairs],
                                      "waist_deg": round(head.status()[1], 2),
                                      "measured": time.strftime("%Y-%m-%d %H:%M")}))
    print(f"arm yaw in the base frame {yaw:.1f} deg -> {CALIB_FILE}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["describe"] and len(a) > 1:
        t = json.loads(a[1])
        print(describe(t))
        print(describe(t, "ko"))
        for p in validate(t, agv.markers()):
            print("problem:", p)
    elif a[:1] == ["state"]:
        print(json.dumps(state(), indent=1, ensure_ascii=False))
    elif a[:1] == ["measure-axis"]:
        try:
            measure_axis(a[1] if len(a) > 1 else None)
        except KeyboardInterrupt:
            agv.cancel()
            sys.exit("stopped")
    else:
        sys.exit(__doc__)
