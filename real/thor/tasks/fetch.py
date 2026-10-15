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

ROOT = Path(__file__).resolve().parents[1]      # the project folder
STATE_FILE = Path("/dev/shm/lumi_task.json")   # the task state, readable by every process
CALIB_FILE = ROOT / "data" / "fetch_calib.json"  # {"arm_yaw_in_base_deg": ...} from measure-axis
OBJECTS = {"cup": "컵", "bottle": "병", "apple": "사과", "orange": "오렌지", "banana": "바나나"}   # camera classes
COLOURS = {"red": "빨간", "orange": "주황색", "yellow": "노란", "green": "초록색", "blue": "파란", "purple": "보라색",
           "pink": "분홍색", "white": "흰", "black": "검은", "grey": "회색"}   # the names objects.colour_name gives
FINISH = ("hold", "place")
LOOK_POSE = "look"           # empty hand: drives, looks and picks from here; high, inside the base outline, out of the
                             # torso camera's view (ready if not taught). With an object: carry
MAX_TILT_DEG = 15.0          # deg; the held cup's axis may lean this far from vertical on ready <-> carry
TILT_POINTS = 11             # points checked along a joint move (kine_forward)
LINE_POINTS = 20             # points IK- and tilt-checked on a straight move with an object in the hand ...
LINE_STEP_DEG = 25.0         # ... no joint may turn more than this between two of them (one IK branch all the way;
                             # near J5 = 0 J4 and J6 turn ~15 deg a step against each other, the cup hardly turns)
# ponytail: fixed table height (top ~ -400 mm in the arm base frame, the 142 mm tumbler's top ~ -258);
# use the measured table top instead when tables of other heights come in.
MIN_POSE_Z = -220.0          # mm; a move between named poses must keep the grasp point above this (or above its start)
PICK_ZONE_CENTRE = (-160.0, 600.0)   # mm, arm base frame: middle of the successful picks (x -126..-178, y 579..613)
PLACE_GRID_X = range(-260, -59, 40)  # mm; place spots tried after the pick spot. At table height the torso camera
PLACE_GRID_Y = (640, 660, 680, 700)  # sees only y >= ~640, nearer spots can't be checked for table (skills.on_table)
TABLE_PROVEN_Z = -403.0      # mm, arm base frame: the table top of every proven pick and place (lift 75 mm)
TABLE_FIT_MM = 150.0         # a measured surface further than this from it is not a table to fit (floor, a wall)
LIFT_TOL_MM = 20.0           # closer than this: the lift stays
LIFT_RANGE = (0.0, 250.0)    # mm; the body API allows 0-300, kept to what the colleagues' code uses (lumi_voice_app)
LIFT_DRIVE_MM = 75.0         # every drive, every task's end and a look that found nothing again at this lift
                             # (higher, the near part of the table is below the torso camera's view)
LIFT_VEL = 20                # % of the lift's speed
LIFT_TRIES = (75.0, 250.0, 0.0)   # mm; where else to look when nothing is found at this lift (usual, top, bottom)
SEARCH_TURN_DEG = 30.0       # then turn on the spot by this much and look again ...
SEARCH_TURNS = 11            # ... this many times (all the way round); never while charging
SAME_BASE_M = 0.02                   # m / rad; the base is still where it picked: the pick spot is still table
SAME_BASE_RAD = 0.035
MAX_SHIFT_M = 0.30           # m; at most this far per base shift
SHIFT_TRIES = 3              # base shifts before asking the person to move the object
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
GIVE_WAIT_S = 30.0           # s; no release by then: keep holding it and go back to carry (never drop it)
# Opening needs a word from the person ("thank you", or Release in the dashboard): AI_1 can't feel a pull. Measured
# 2026-10-15 with the cup in the closed gripper: its median stayed 2780-2870 during gentle pulls (only its noise
# grew, sd 20 -> 50-75), while the fingers settling after the move changed it by 192.
GIVE_POLL_S = 0.2
LOG_LINES = 40

_lock = threading.Lock()
_stop = threading.Event()                    # set by stop(): every step and every wait gives up
_release = threading.Event()                 # set by release_now() ("thank you" / Release while giving)
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
        frm = "여기에서" if src == "here" else f"{mark['src']} 위치에서" if "src" in mark else "알려준 위치에서"
        to = "여기로" if dst == "here" else f"{mark['dst']} 위치로" if "dst" in mark else \
            "알려준 위치로" if dst else "어딘가로"
        end = "테이블에 내려놓을게요" if place else "들고 있을게요"
        return f"{frm} {thing}{_object_particle(thing)} 가져와서 {to} 가져가 {end}."
    thing = (colour + " " if colour else "") + obj
    frm = "from here" if src == "here" else f"from {mark['src']}" if "src" in mark else "from the point I was shown"
    to = "here" if dst == "here" else f"to {mark['dst']}" if "dst" in mark else \
        "to the point I was shown" if dst else "somewhere"
    end = "put it on the table" if place else "hold it"
    return f"Take the {thing} {frm}, bring it {to} and {end}."


# ---------- helpers ----------
def _go_on():
    if _stop.is_set():
        raise Stopped()


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


def _pose(name):
    _go_on()
    start, low = lowest_along(name)
    if low < min(MIN_POSE_Z, start - 10.0):
        log(f"refused: on the way to {name} the gripper would go down to z {low:.0f} mm")
        raise FetchError("My arm would go too close to the table, I stopped.", "팔이 테이블에 너무 가까워져서 멈췄어요.")
    log(f"arm to {name}")
    motion.go(name)
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


def _line_rows(target, label):
    """IK rows of the straight move from here to the flange pose `target`. FetchError when IK fails on the way or the
    held cup would lean more than MAX_TILT_DEG (the arm stays where it is)."""
    c0, j0 = np.array(motion.tcp()), skills._joints()
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
    motion.move_linear(target=target, speed="slow", path_checked=True)
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
    _pose(name)


def _wait_drive(watch_holding=False):
    """Wait until the base stops. Raises FetchError unless it arrived ("succeeded")."""
    t0 = last_hold = time.time()
    seen_running = False
    anchor = None                            # (x, y, time) of the last real progress
    while True:
        if _stop.wait(DRIVE_POLL_S):
            raise Stopped()
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


def _turn(deg, holding=False):
    """Turn the base on the spot by `deg` (+ = left), arm in look (empty) or carry (holding), lift at 75 mm.
    False when it must not (charging)."""
    if _charging():
        log("on the charger: I don't turn")
        return False
    if holding:
        _line_holding("carry")
    else:
        _pose(_look())
    _lift_to(LIFT_DRIVE_MM)
    log(f"turning {deg:+.0f} deg to look further")
    ok, msg = agv.turn_by(math.radians(deg))
    if not ok:
        raise FetchError(f"I couldn't turn ({msg}).")
    _wait_drive(watch_holding=holding)
    if holding:
        _line_holding(LOOK_POSE)
    return True


def _search(attempt, holding=False, say=None):
    """Run attempt() until it returns something: here at this lift, at LIFT_TRIES, then turning on the spot
    (each new heading at the usual and the top lift). None when the whole search found nothing."""
    for i in range(SEARCH_TURNS + 1):
        if i and not _turn(SEARCH_TURN_DEG, holding):
            return None
        if i == 1:
            _say(say, "Let me look around.", "주변을 둘러볼게요.")
        here = head.status()[0]
        lifts = [None] + [m for m in LIFT_TRIES if abs(m - here) >= 5.0] if i == 0 else [None, LIFT_TRIES[1]]
        for lift in lifts:
            if lift is not None:
                _lift_to(lift)
            got = attempt()
            if got is not None:
                return got
    return None


def _find_any(task):
    try:
        return _find(task)
    except FetchError:
        return None


def _fit_lift(table):
    """Bring a table at `table` mm (arm frame) to TABLE_PROVEN_Z with the lift. True when the lift moved (look again)."""
    if table is None:
        log("table height not measured: the lift stays")
        return False
    delta = table - TABLE_PROVEN_Z                    # table higher (less negative) -> lift up by as much
    if abs(delta) > TABLE_FIT_MM:
        log(f"surface at {table:.0f} mm is not a table I can work at: the lift stays")
        return False
    if abs(delta) < LIFT_TOL_MM:
        return False
    lift = head.status()[0]
    target = max(LIFT_RANGE[0], min(LIFT_RANGE[1], lift + delta))
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
        ok, msg = agv.go(place["marker"])
    else:
        _say(say, "On my way.", "가는 중이에요.")
        ok, msg = agv.go_point(place["x"], place["y"], place["theta"])
    if not ok:
        raise FetchError(f"I couldn't start driving ({msg}).")
    _wait_drive(watch_holding)


# ---------- base shift ----------
def arm_yaw():
    """Angle (deg) of the arm base frame in the base frame, from measure-axis; None until it is measured."""
    try:
        return float(json.loads(CALIB_FILE.read_text())["arm_yaw_in_base_deg"])
    except (FileNotFoundError, ValueError, KeyError):
        return None


def _rot(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


def shift_target(obj_xy, base_pose, yaw_deg):
    """Map pose (x, y, theta) the base drives to so the object at `obj_xy` (mm, arm base frame) comes to the
    pick zone centre. The base moves by the object's offset from the centre, turned into the base frame, so the
    object then appears that much nearer; at most MAX_SHIFT_M."""
    move = _rot(yaw_deg) @ (np.subtract(obj_xy, PICK_ZONE_CENTRE) / 1000.0)
    n = np.linalg.norm(move)
    if n > MAX_SHIFT_M:
        move *= MAX_SHIFT_M / n
    x, y, th = base_pose
    dx, dy = _rot(math.degrees(th)) @ move
    return x + dx, y + dy, th


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


def _reachable(obj):
    """The pick waypoints when their IK passes from look (any grasp turn), else None. Wrong-size objects raise."""
    return skills.reachable_pick(obj)


def _reach(task, obj, say):
    """Step 5: (obj, waypoints) of a pick that passes IK, shifting the base or asking the person when needed."""
    yaw = arm_yaw()
    for i in range(SHIFT_TRIES + 1):
        waypoints = _reachable(obj)
        if waypoints:
            return obj, waypoints
        if yaw is None or i == SHIFT_TRIES:
            break
        target = shift_target((obj["x"], obj["y"]), agv.pose(), yaw)
        _step(f"shifting the base ({i + 1}/{SHIFT_TRIES})", say, "Let me move a little closer.", "조금 가까이 갈게요.")
        _pose(_look())
        ok, msg = agv.go_point(*target)
        if not ok:
            raise FetchError(f"I couldn't move the base ({msg}).")
        _wait_drive()
        _pose(_look())
        obj = _find(task)
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
        waypoints = _reachable(obj)
        if waypoints:
            return obj, waypoints
    raise FetchError("I still can't reach it.", "아직 손이 닿지 않아요.")


def table_ahead():
    """Height (mm) of the table in front: median depth surface over the place grid, only values near
    TABLE_PROVEN_Z (TABLE_FIT_MM) count; None when too little table is in view."""
    zs = [z for z in skills.surface_heights([(x, y) for y in PLACE_GRID_Y for x in PLACE_GRID_X])
          if z is not None and abs(z - TABLE_PROVEN_Z) <= TABLE_FIT_MM]
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
    tries = place_spots(skills._held, agv.pose(), skills.look(), table)
    if not tries:
        return None
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
            skills._guarded(lambda: motion.move_linear(target=way[0][1], speed="slow", path_checked=True))  # checked
            skills._guarded(skills._do_place, [(r[0], r[1]) for r in rows])   # ends at home (look), hand open
            _set(holding=False)
            _pose(_look())
            return True
        log(f"spot ({x:.0f}, {y:.0f}) refused at {rows[-1][0]}: {rows[-1][3]}")
    return None


def _put_down(say=None):
    """Straight to look with the object (carry hides the table from the torso camera), then search for a free
    table spot: here, at other lifts, turning on the spot; put it down, back to look."""
    top = skills._held.get("top_mm")
    if top is None:
        raise FetchError("I'm not holding anything I picked.")
    _step("placing")
    _line_holding(LOOK_POSE)
    if _search(lambda: _place_here(top), holding=True, say=say) is None:
        _line_holding("carry")
        _lift_to(LIFT_DRIVE_MM)
        raise FetchError("I can't find a free place on a table around me.", "주변에 내려놓을 빈 자리를 못 찾았어요.")


def _give(say):
    """Carry -> give (straight), open on "thank you" / Release, then look. No release within GIVE_WAIT_S:
    back to carry, still holding it; returns "kept"."""
    _line_holding("give")
    _release.clear()
    _step("giving", say, "Here you go. Hold it and say thank you.", "여기 있어요. 잡고 고맙다고 말해 주세요.")
    t0 = time.time()
    while time.time() - t0 < GIVE_WAIT_S and not _release.is_set():
        if _stop.wait(GIVE_POLL_S):
            raise Stopped()
    if not _release.is_set():
        _say(say, "Nobody took it, I'll keep holding it.", "아무도 안 받아서 계속 들고 있을게요.")
        _line_holding("carry")
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
        s = gripper.state()
        if s["holding"]:
            raise FetchError("I'm holding something, where should I put it first?",
                             "뭔가 들고 있어요. 먼저 어디에 놓을까요?")
        if s["closed"]:
            gripper.open_()
        _pose(_look())
        _step("driving to the source")
        _drive_to(task.get("source", "here"), say)
        _step("looking")
        obj = _search(lambda: _find_any(task), say=say)
        if obj is None:
            _lift_to(LIFT_DRIVE_MM)
            thing = OBJECTS[task["object"]]
            raise FetchError(f"I looked all around, but I can't see the {task['object']}.",
                             f"주변을 다 봤는데 {thing}{'이' if _object_particle(thing) == '을' else '가'} 안 보여요.")
        table = skills.table_near(obj) or skills.table_z(obj)
        log(f"table at {table:.0f} mm" if table is not None else "table height not measured")
        if _fit_lift(table):
            obj = _find(task)
        log(f"found {obj['colour']} {obj['name']} at ({obj['x']:.0f}, {obj['y']:.0f}) top {obj['top_mm']:.0f}")
        _step("reaching")
        obj, waypoints = _reach(task, obj, say)
        _step("picking")
        skills._guarded(skills._do_pick, obj, waypoints)       # ends 3 cm above the table, holding
        skills._held["base"] = agv.pose()                       # place_spots: put back here if the base stays
        _set(holding=True)
        _say(say, "I've got it.", "잡았어요.")
        _step("carry")
        skills._guarded(skills._line, "up", waypoints[0][1])   # straight up to the approach height first
        _line_holding("carry")                                   # straight: the cup stays upright
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
    skills._cancel.clear()


def _launch(fn, *a):
    global _thread
    _thread = threading.Thread(target=fn, args=a, daemon=True)
    _thread.start()


def _busy():
    return _thread is not None and _thread.is_alive()


# ---------- public ----------
def _hand_holds():
    """The gripper's own word (closed on something), whatever the state file says."""
    try:
        return bool(gripper.state()["holding"])
    except (ConnectionError, OSError, KeyError):
        return False


def start(task, say=None):
    """Start `task` in the background. FetchError when busy, holding something or the task is invalid."""
    _adopt()
    with _lock:
        if _busy():
            raise FetchError("I'm busy with another task.")
        if _state["holding"] or _hand_holds():
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
        if not _state["holding"]:
            if not _hand_holds():
                raise FetchError("I'm not holding anything.")
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


def place(say=None):
    """Put the held object on the table in front."""
    _finish(_put_down, say)


def carry_to(dest, say=None):
    """Bring the held object to `dest` (marker / map point) in carry and keep holding it."""
    if not _place_ok(dest, agv.markers() if isinstance(dest, dict) and "marker" in dest else []):
        raise FetchError("I don't know that place.")
    _finish(lambda s: _carry_to(dest, s), say)


def _carry_to(dest, say):
    _line_holding("carry")
    _step("driving to the destination")
    _drive_to(dest, say, watch_holding=True)
    _say(say, "I'm here.", "도착했어요.")
    return "kept"


def carry_sentence(dest):
    m = dest.get("marker") if isinstance(dest, dict) else None
    return f"Bring it to {m} and keep holding it." if m else "Bring it to the point I was shown and keep holding it."


def release_now():
    """The person said "thank you" while Lumi is giving: open now."""
    _release.set()


def stop():
    """Stop the base, the arm and any waiting at once; the gripper keeps its state."""
    _stop.set()
    for fn in (skills.cancel, agv.cancel):
        try:
            fn()
        except Exception as e:           # try every stop even when one of them fails
            log(f"stop: {fn.__module__}.{fn.__name__} failed: {e}")
    if _state["status"] in ("running", "holding"):
        _set(status="stopped")
        log("stopped")


# ---------- measuring the arm's yaw on the base ----------
def _straight(dist_m):
    """Drive straight by dist_m (+ forward) at AXIS_SPEED with joy_control (no turning), then stop."""
    t_end = time.time() + abs(dist_m) / AXIS_SPEED
    v = AXIS_SPEED if dist_m > 0 else -AXIS_SPEED
    try:
        while time.time() < t_end:
            agv.request(f"/api/joy_control?linear_velocity={v:.3f}&angular_velocity=0")
            time.sleep(0.1)
    finally:
        agv.request("/api/joy_control?linear_velocity=0&angular_velocity=0")
    time.sleep(1.0)                                  # the base coasts a little


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
    """Objects of the same class seen in both looks, matched nearest first (they moved by about the base move)."""
    out = []
    for b in before:
        same = [a for a in after if a["name"] == b["name"]]
        if same:
            a = min(same, key=lambda o: np.hypot(o["x"] - b["x"], o["y"] - b["y"]))
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
