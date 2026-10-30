"""The arm moves between named poses only by joint moves between taught poses, every joint move checked before
anything moves.

    give_pre - give - carry - look - wave_out - wave_start - wave       (EDGES: the moves run live first)
                               |
                             ready

`look` is where every arm action starts (picks and puts go out from it and come back to it, skills.py). With an empty
hand the arm goes from pose to pose by the route of least joint travel (each move its largest joint turn plus
STOP_DEG for the stop), any two poses one joint move apart when that move passes the checks below (all but NO_EDGES;
on equal travel the EDGES first): from wave_start straight to give, from give straight to look. With something in
the hand only the EDGES (fetch runs them as straight lines, the cup upright) and never a wave pose (WAVE_POSES). An
arm at no pose (after free
drive, after a stop half way) joins the graph by one checked joint move to a pose of it, the nearest first; when no
such move passes, first straight up by UP_MM (a joint move to the IK pose above, checked the same way), then the
join. Joins further than JOIN_DEG run at HOLD_SPEED. Only when nothing passes, nothing moves and Lumi asks for the
arm to be brought near `look` by hand. A task's own
way back from the table (`leaf`: it went out from `look` along a checked plan) goes straight to its target.

Each joint move is checked at PATH_POINTS points (kine_forward): joint limits, no joint turning further than
motion.MAX_TRAVEL, the gripper (flange -> grasp point -> finger tips) at least HEAD_CLEAR_MM from the head's turning
centre (vision/head_cam.py), every arm link (elbow, wrist; offline kinematics) at least LINK_HEAD_CLEAR_MM from it,
never more than skills.PATH_SAG_MM below both ends, and with something in the hand the
cup's lean at most skills.MAX_TILT_DEG. Refusals are RouteError with the reason in English and Korean.

A route runs one move at a time (motion.move_path): each to a full stop and SETTLE_S standing, then the next; SPEED
with an empty hand, HOLD_SPEED with something in it.

With an empty hand and `give_pre` taught, every way to `give` ends give_pre -> give: the route goes to `give_pre`
(never through `give`), stands there, and the last move into `give` runs at GIVE_SPEED. Without `give_pre` the route
to `give` is the plain cheapest one. With something in the hand `give_pre` is not used (fetch's straight moves).

Cobo π programs start only from `look` (start_program); hand_shaking.jks never (it hit the head, 2026-10-21).

    python manipulation/arm_route.py check [pose]    # the route from here to pose (default look), checked; moves nothing
    python manipulation/arm_route.py goto <pose>     # go there along the route (SPEED; the owner at the STOP)

Teach a pose (arm moved by hand in Cobo π first): python robot/motion.py teach give_pre (then teach give)
"""
import collections
import heapq
import sys
import time

import numpy as np

from manipulation import skills
from robot import arm, gripper, kinematics, motion
from vision import calib, head_cam

HOME = "look"                        # every arm action starts here
GIVE = "give"                        # the hand held out to a person
GIVE_PRE = "give_pre"                # one step before GIVE: an empty-hand way to GIVE always ends GIVE_PRE -> GIVE
GIVE_SPEED = "slow"                  # motion.JOINT_SPEED of the last move, GIVE_PRE -> GIVE (first live runs: slow)
EDGES = (("give_pre", "give"), ("give", "carry"), ("carry", "look"), ("look", "wave_out"), ("wave_out", "wave_start"),
         ("wave_start", "wave"), ("look", "ready"))   # the moves with something in the hand (both ways)
NO_EDGES = {frozenset(("look", "wave_start"))}        # never one joint move: passes 267 mm from the head (the wave
                                                      # goes up and down through wave_out, 309 mm)
WAVE_POSES = ("wave_out", "wave_start", "wave")       # never with something in the hand (the cup would tip)
STOP_DEG = 10.0                      # deg of joint travel one more stop on a route costs (SETTLE_S, slowing down and
                                     # starting again; an estimate, it only weighs routes against each other)
SPEED = "route"                      # motion.JOINT_SPEED of the moves along the graph, empty hand
HOLD_SPEED = "slow"                  # ... with something in the hand
AT_POSE_DEG = 3.0                    # deg; the arm is at a pose when every joint is this close (where, programs)
EXACT_DEG = 1.0                      # deg; further than this from the nearest pose a route first goes to it
JOIN_DEG = 20.0                      # deg; an arm at no pose this close to one (every joint) joins it at the route speed
UP_MM = (100.0, 200.0)               # mm straight up tried before a join when no direct join passes
PATH_POINTS = 21                     # points checked (kine_forward) on every joint move
HEAD_CLEAR_MM = 250.0                # mm the gripper keeps from the head's turning centre. Estimate: the head camera
                                     # is 102 mm from it, the head's size is not measured. `look` keeps 327 mm
LINK_HEAD_CLEAR_MM = 220.0           # mm every arm link keeps from the head's turning centre. Estimate below the taught
                                     # graph's least (267 mm at `wave`, live); the head's size is not measured
NEVER_RUN = ("hand_shaking.jks",)    # Cobo π programs not started any more

# Why the arm does not move, (English, Korean)
UNKNOWN = ("My arm is in a position I don't know, so I won't move it. Please bring it near its look pose by hand.",
           "팔이 모르는 자세라서 움직이지 않을게요. 손으로 팔을 기본 자세 가까이 옮겨 주세요.")
NOT_TAUGHT = ("I haven't learned that arm pose yet.", "그 팔 자세는 아직 배우지 못했어요.")
BLOCKED = ("I can't move my arm there safely.", "팔을 거기로 안전하게 움직일 수 없어요.")
NEAR_HEAD = ("That would bring my hand too close to my head, so I won't move my arm.",
             "손이 머리에 너무 가까워져서 팔을 움직이지 않을게요.")
SPILL = ("I can't move my arm there without spilling it.", "쏟지 않고는 팔을 거기로 움직일 수 없어요.")
UNSURE = ("I can't check my arm right now, so I won't move it.", "지금 팔 상태를 확인할 수 없어서 움직이지 않을게요.")
NOT_AT_LOOK = ("My arm has to be in its look pose first.", "먼저 팔이 기본 자세에 있어야 해요.")
OFF = ("Please enable my arm first.", "먼저 제 팔을 켜 주세요.")   # not powered / enabled in Cobo π (joints read 0)
RETIRED = ("I don't use that arm program any more.", "그 팔 프로그램은 이제 쓰지 않아요.")


class RouteError(skills.SkillError):
    """args: (English, Korean) reason. Nothing was sent to the arm."""


def log(*a):
    skills.log(*a)


def _r(j):
    return [round(v, 1) for v in j]


def _deg(now, pose):
    """Largest joint difference (deg) between `now` and `pose` as move_joints would reach it."""
    return max(abs(a - b) for a, b in zip(motion.nearest(pose, now), now))


def graph(holding=False, skip=()):
    """{pose: joints} of the graph's taught poses but `skip` (`holding`: without WAVE_POSES and GIVE_PRE)."""
    p = motion.poses()
    return {n: p[n] for e in EDGES for n in e
            if n in p and n not in skip and not (holding and n in WAVE_POSES + (GIVE_PRE,))}


def where(now=None):
    """The graph pose the arm is at (every joint within AT_POSE_DEG), else None."""
    now = skills._joints() if now is None else now
    d = {n: _deg(now, j) for n, j in graph().items()}
    best = min(d, key=lambda n: (d[n], n != HOME), default=None)
    return best if best is not None and d[best] <= AT_POSE_DEG else None


def _path(a, b, nodes):
    """Shortest list of poses a .. b along EDGES between `nodes`, None when there is none."""
    back, todo = {a: None}, collections.deque([a])
    while todo:
        n = todo.popleft()
        if n == b:
            out = []
            while n is not None:
                out.append(n)
                n = back[n]
            return out[::-1]
        for e in EDGES:
            for x, y in (e, e[::-1]):
                if x == n and y in nodes and y not in back:
                    back[y] = n
                    todo.append(y)
    return None


def _cheapest(a, b, nodes, ok):
    """Poses a .. b of least joint travel, one joint move between any two of `nodes` but NO_EDGES and the moves
    refused in `ok` ({frozenset pair: passed}); on equal travel fewer moves off EDGES. None when there is none."""
    listed = {frozenset(e) for e in EDGES}
    todo, done = [((0.0, 0), [a])], set()
    while todo:
        cost, path = heapq.heappop(todo)
        n = path[-1]
        if n == b:
            return path
        if n in done:
            continue
        done.add(n)
        for m in nodes:
            e = frozenset((n, m))
            if m not in done and e not in NO_EDGES and ok.get(e) is not False:
                heapq.heappush(todo, ((cost[0] + _deg(nodes[n], nodes[m]) + STOP_DEG, cost[1] + (e not in listed)),
                                      path + [m]))
    return None


def route(a, b, nodes, holding=False):
    """Poses a .. b. Holding: the fewest EDGES. Empty hand: _cheapest, each of its moves checked (check_moves) before
    it is taken, a refused one left out and the next cheapest tried. RouteError when there is no way: why the last
    move was refused, else NOT_TAUGHT."""
    if holding:
        path = _path(a, b, nodes)
        if path is None:
            log(f"arm route: no way from {a} to {b} among {', '.join(nodes)}")
            raise RouteError(*NOT_TAUGHT)
        return path
    ok, why = {}, NOT_TAUGHT
    while True:
        path = _cheapest(a, b, nodes, ok)
        if path is None:
            log(f"arm route: no checked way from {a} to {b}")
            raise RouteError(*why)
        for x, y in zip(path, path[1:]):
            e = frozenset((x, y))
            if e not in ok:
                try:
                    check_moves(nodes[x], [nodes[y]])
                    ok[e] = True
                except RouteError as err:
                    if err.args == UNSURE:
                        raise
                    ok[e], why = False, err.args
                    break
        else:
            return path


def hops(now, target, leaf=False, holding=False, skip=()):
    """The poses the arm goes through from the joints `now` to `target`, in order (not the one it is at). `leaf`: the
    arm is out on the task's own checked way from look (above a table): when it is at no pose, straight to target.
    `skip`: poses the way must not pass."""
    if holding and target in WAVE_POSES:
        raise RouteError(*SPILL)
    nodes = graph(holding, skip)
    if target not in nodes:
        log(f"arm route: {target} is not taught (robot/motion.py teach {target})")
        raise RouteError(*NOT_TAUGHT)
    d = {n: _deg(now, j) for n, j in nodes.items()}
    start = min(d, key=lambda n: (d[n], n != HOME))
    if d[start] > JOIN_DEG:
        if leaf:
            return [target]
        if not any(now):                                    # a switched-off arm reads all joints 0
            log("arm route: the arm reads all 0: switched off")
            raise RouteError(*OFF)
        log(f"arm route: arm at {_r(now)}, {d[start]:.0f} deg from {start}, the nearest pose (joins within "
            f"{JOIN_DEG:.0f})")
        raise RouteError(*UNKNOWN)
    path = route(start, target, nodes, holding)
    return path if d[start] > EXACT_DEG else path[1:]


def _seg_dist(c, a, b):
    """mm from point c to the segment a-b."""
    ab = b - a
    t = min(1.0, max(0.0, float((c - a) @ ab) / float(ab @ ab))) if ab @ ab else 0.0
    return float(np.linalg.norm(c - (a + t * ab)))


def _gripper(c):
    """Flange, grasp point, finger tips (mm) and the flange rotation of the flange pose c [x, y, z, rx, ry, rz]."""
    R, f = calib.rpy_matrix(*c[3:]), np.array(c[:3], float)
    g = f + R @ skills.GRASP_OFFSET
    return f, g, g + R @ (skills.TIP_MM * skills.FINGER_DIR), R


def links(j):
    """Joint origins (mm, arm base frame) from the shoulder to the flange at joints j (offline kinematics)."""
    return [f[:3, 3] for f in kinematics.chain(j)[2:]]


def link_clearance(j0, j1, centre):
    """Smallest distance (mm) from `centre` to the arm's links at PATH_POINTS points of the joint move j0 -> j1."""
    j0, j1 = np.array(j0, float), np.array(j1, float)
    out = np.inf
    for k in range(PATH_POINTS):
        pts = links(list(j0 + (j1 - j0) * k / (PATH_POINTS - 1)))
        out = min([out] + [_seg_dist(centre, a, b) for a, b in zip(pts, pts[1:])])
    return out


def flange_clearance(c, centre):
    """Smallest distance (mm) from `centre` to the gripper at the flange pose c."""
    f, g, tip, _ = _gripper(c)
    return min(_seg_dist(centre, f, g), _seg_dist(centre, g, tip))


def profile(j0, j1, centre):
    """(least gripper distance to `centre` mm, lowest z mm of the gripper at the ends, lowest z on the way, largest
    lean deg of a held cup's axis) at PATH_POINTS points of the joint move j0 -> j1 (all joints together, a straight
    line in joint space)."""
    j0, j1 = np.array(j0, float), np.array(j1, float)
    axis = calib.rpy_matrix(*skills.GRASP_RPY).T @ [0.0, 0.0, 1.0]     # a held cup's axis in the flange frame
    clear, low, tilt = [], [], 0.0
    for k in range(PATH_POINTS):
        c = skills._ask("kine_forward", jointPosition=[float(v) for v in j0 + (j1 - j0) * k / (PATH_POINTS - 1)])
        f, g, tip, R = _gripper(c["cartPosition"])
        clear.append(flange_clearance(c["cartPosition"], centre))
        low.append(float(min(f[2], g[2], tip[2])))
        tilt = max(tilt, float(np.degrees(np.arccos(np.clip((R @ axis)[2], -1.0, 1.0)))))
    return min(clear), min(low[0], low[-1]), min(low), tilt


def move_problem(j0, j1, centre, holding=False):
    """Why the joint move j0 -> j1 must not run as (reason, log text), None if it may."""
    clear, ends, low, tilt = profile(j0, j1, centre)
    if clear < HEAD_CLEAR_MM:
        return NEAR_HEAD, f"the gripper comes {clear:.0f} mm from the head (needs {HEAD_CLEAR_MM:.0f})"
    arm_clear = link_clearance(j0, j1, centre)
    if arm_clear < LINK_HEAD_CLEAR_MM:
        return NEAR_HEAD, f"the arm comes {arm_clear:.0f} mm from the head (needs {LINK_HEAD_CLEAR_MM:.0f})"
    if low < ends - skills.PATH_SAG_MM:
        return BLOCKED, f"the gripper dips to z {low:.0f} mm"
    if holding and tilt > skills.MAX_TILT_DEG:
        return SPILL, f"the held cup would lean {tilt:.0f} deg"
    return None


def check_moves(now, targets, holding=False):
    """Joint targets of the moves now -> targets[0] -> ..., as move_joints will turn them (J1 / J4 / J6 nearest),
    each checked. RouteError when one must not run."""
    centre = head_cam.head_centre()
    if centre is None:
        log("arm route: the head's place is not measured (vision/head_cam.py fit)")
        raise RouteError(*UNSURE)
    seq, prev, done = [], list(now), {}
    for t in targets:
        try:
            motion.check(t)
        except motion.MotionError as e:
            log(f"arm route: {e}")
            raise RouteError(*BLOCKED) from e
        t = motion.nearest(t, prev)
        if max(abs(a - b) for a, b in zip(t, prev)) > motion.MAX_TRAVEL:
            log(f"arm route: {_r(prev)} -> {_r(t)} turns a joint further than {motion.MAX_TRAVEL:.0f} deg")
            raise RouteError(*BLOCKED)
        key = frozenset((tuple(np.round(prev, 1)), tuple(np.round(t, 1))))
        if key not in done:                          # a move there and back (a wave's swings): checked once
            done[key] = move_problem(prev, t, centre, holding)
        if done[key]:
            log(f"arm route: {_r(prev)} -> {_r(t)} refused: {done[key][1]}")
            raise RouteError(*done[key][0])
        seq.append(t)
        prev = t
    return seq


def _up(now, mm):
    """Joints with the flange `mm` straight above where it is at `now` (same orientation), None without an IK answer."""
    c = skills._ask("kine_forward", jointPosition=[float(v) for v in now])["cartPosition"]
    r = skills._ask("kine_inverse", jointPosition=[float(v) for v in now], cartPosition=[c[0], c[1], c[2] + mm, *c[3:]])
    return r.get("jointPosition")


def join(now, target, holding=False, skip=()):
    """[(pose, joints)] of a checked way from an arm at no pose of the graph to `target`: one joint move to a graph
    pose (the nearest first), then along the graph; else first straight up by UP_MM. RouteError(UNKNOWN) when no way
    passes the checks; nothing moved."""
    nodes = graph(holding, skip)
    if target not in nodes:
        raise RouteError(*(SPILL if holding and target in WAVE_POSES else NOT_TAUGHT))
    order = sorted(nodes, key=lambda n: (_deg(now, nodes[n]), n != HOME))
    for mm in (None, *UP_MM):
        first = [] if mm is None else [("up", _up(now, mm))]
        if first and first[0][1] is None:
            continue
        for n in order:                              # the nearest pose first, then the way on from it
            try:
                way = first + [(x, nodes[x]) for x in route(n, target, nodes, holding)]
                return list(zip([x for x, _ in way], check_moves(now, [j for _, j in way], holding)))
            except RouteError as e:
                if e.args == UNSURE:
                    raise
    log(f"arm route: arm at {_r(now)}: no checked way to {target}")
    raise RouteError(*UNKNOWN)


def plan(target, holding=False, leaf=False, now=None):
    """[(pose, joints)] of the checked way from here to `target` ([] when it is there). RouteError to refuse.
    Empty hand to GIVE with GIVE_PRE taught: the way to GIVE_PRE (not through GIVE), then GIVE."""
    now = skills._joints() if now is None else now
    if target == GIVE and not holding and GIVE_PRE in graph() and where(now) != GIVE:
        seq = _plan(GIVE_PRE, False, leaf, now, skip=(GIVE,))
        return seq + [(GIVE, check_moves(seq[-1][1] if seq else now, [motion.poses()[GIVE]])[0])]
    return _plan(target, holding, leaf, now)


def _plan(target, holding, leaf, now, skip=()):
    try:
        names = hops(now, target, leaf, holding, skip)
    except RouteError as e:
        if e.args != UNKNOWN:
            raise
        seq = join(now, target, holding, skip)
        log(f"arm route: joining from {_r(now)} by {' -> '.join(n for n, _ in seq)}, checked")
        return seq
    p = motion.poses()
    return list(zip(names, check_moves(now, [p[n] for n in names], holding)))


def move(seq, speed=None, holding=False):
    """Run a plan() (made with the same `holding`) along its poses. motion.MotionError when stopped or failed on the
    way (the arm stays there)."""
    if not seq:
        return
    t0 = time.time()
    log(f"arm to {' -> '.join(n for n, _ in seq)}")
    s = HOLD_SPEED if holding else speed or SPEED
    last = GIVE_SPEED if not holding and GIVE_PRE in graph() else s     # GIVE_PRE -> GIVE (plan)
    motion.move_path([(j, last if n == GIVE else s) for n, j in seq])
    log(f"arm at {seq[-1][0]} after {time.time() - t0:.1f} s")


def goto(target, holding=False, leaf=False, speed=None):
    """Plan, check and go to pose `target` along the graph. Returns the poses passed."""
    now = skills._joints()
    seq = plan(target, holding, leaf, now)
    if not leaf and min(_deg(now, j) for j in graph().values()) > JOIN_DEG:
        speed = HOLD_SPEED                          # a join from far: slow
    if seq:
        log(f"arm route to {target}: {' -> '.join(n for n, _ in seq)}, checked")
    move(seq, speed, holding)
    return [n for n, _ in seq]


def start_program(name):
    """Start a Cobo π program, only from `look`. It ends wherever it was taught to end: the next move joins the graph
    from there (or is refused). RouteError to refuse."""
    if name.lower() in NEVER_RUN:
        raise RouteError(*RETIRED)
    if where() != HOME:
        log(f"program {name} refused: the arm is not at {HOME}")
        raise RouteError(*NOT_AT_LOOK)
    arm.start(name)


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if a[:1] == ["check"]:
            now = skills._joints()
            centre = head_cam.head_centre()
            print(f"at {where(now) or 'no pose'}: {_r(now)}")
            prev = now
            for n, j in plan(a[1] if len(a) > 1 else HOME, gripper.state()["holding"], now=now):
                clear, _, low, tilt = profile(prev, j, centre)
                print(f"  -> {n:10s} {_r(j)}  head {clear:.0f} mm, lowest z {low:.0f} mm, cup lean {tilt:.0f} deg")
                prev = j
            print("checked, nothing moved")
        elif a[:1] == ["goto"] and len(a) == 2:
            print(goto(a[1], gripper.state()["holding"]))
        else:
            sys.exit(__doc__)
    except RouteError as e:
        sys.exit(f"refused: {e.args[0]}")
    except motion.MotionError as e:
        sys.exit(f"stopped: {e}")
    except KeyboardInterrupt:
        print(motion.stop())
