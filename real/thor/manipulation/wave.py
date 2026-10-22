"""Wave the hand when someone asked for it. A greeting never moves the arm.

The arm goes up along the pose graph (manipulation/arm_route.py: from `look` to `wave_out`, the hand away from the
head, then `wave_start`, the hand above the head), swings between the taught poses `wave_start` and `wave` (J3 −14.7°)
SWINGS times and STAYS at `wave_start`: the next arm task takes it back down the same way (wave_start -> wave_out
-> look). The way up goes like arm_route.goto, each move to a stop, the last one (into wave_start) at ARRIVE_SPEED;
the swings run back to back. Before anything moves, every joint move is checked (arm_route.check_moves: limits,
travel, the gripper clear of the head, no dip). Refused, with the reason in English and Korean: the arm off or busy, the base driving, a task
running, something in the hand, the arm at no known pose (after free drive), a pose not taught, a move too near the
head.

    python manipulation/wave.py check      # plan and check from where the arm is now; moves nothing
    python manipulation/wave.py run        # wave (slow; the owner at the STOP)

Teach the poses first, arm moved by hand in Cobo π: python robot/motion.py teach wave_out / wave_start / wave
"""
import sys
import time

from manipulation import arm_route, skills
from robot import agv, arm, gripper, motion

START = "wave_start"                 # hand above the head; the wave starts and ends here
SWING = "wave"                       # START with J3 −14.7°
SWINGS = 2                           # times START -> SWING -> START
SWING_SPEED = "normal"               # motion.JOINT_SPEED of the swings; the way up is arm_route.SPEED ...
ARRIVE_SPEED = "normal"              # ... but its last move, into START: at route speed it stopped there hard (J1 60°)

# Why Lumi does not wave, (English, Korean)
OFF = ("Please enable my arm first.", "먼저 제 팔을 켜 주세요.")
BUSY = ("I'm busy with my arm right now.", "지금 팔로 하는 일이 있어요.")
DRIVING = ("I can't wave while I'm moving.", "움직이는 동안에는 손을 흔들 수 없어요.")
HOLDING = ("I'm holding something, so I won't wave.", "손에 물건을 들고 있어서 손을 흔들지 않을게요.")
UNKNOWN_POSE = arm_route.UNKNOWN
NOT_TAUGHT = ("I haven't learned how to wave safely yet.", "아직 안전하게 손 흔드는 법을 배우지 못했어요.")
NEAR_HEAD = ("Waving would bring my hand too close to my head, so I won't.",
             "손이 머리에 너무 가까워져서 손을 흔들지 않을게요.")
UNSURE = ("I can't check my arm right now, so I won't wave.", "지금 팔 상태를 확인할 수 없어서 손을 흔들지 않을게요.")


class WaveError(RuntimeError):
    """args: (English, Korean) reason."""


def log(*a):
    print(*a, flush=True)


def _holding():
    """Is something in the hand? The fetch rule (fetch._in_hand): the task state first, then the torso camera, the
    gripper's AI_1 when the camera can't tell. Only reads: fetch's own functions write its state file."""
    from tasks import fetch
    st = fetch.state()
    if st.get("holding") or st.get("held_object"):
        return True
    try:
        seen = skills.hand_sees()
    except (skills.SkillError, ConnectionError, OSError, KeyError):
        seen = "unknown"
    return seen == "object" if seen != "unknown" else bool(gripper.state()["holding"])


def plan():
    """(the way up: arm_route.plan to START, the swings' joint targets) from here, each move checked. Raises
    WaveError to refuse."""
    from tasks import fetch
    st = arm.cmd("get_robot_state")
    if not (st.get("power") and st.get("enable")):
        raise WaveError(*OFF)
    if arm.program_state() != "idle" or fetch.state().get("status") in ("running", "waiting"):
        raise WaveError(*BUSY)
    if (agv.status() or {}).get("move_status") == "running":
        raise WaveError(*DRIVING)
    if _holding():
        raise WaveError(*HOLDING)
    now = motion.joints()
    try:
        route = arm_route.plan(START, now=now)        # up along the graph ([] when it is there already)
        p = motion.poses()
        if SWING not in p:
            raise arm_route.RouteError(*arm_route.NOT_TAUGHT)
        swings = arm_route.check_moves(route[-1][1] if route else now, [p[SWING], p[START]] * SWINGS)
    except arm_route.RouteError as e:
        raise WaveError(*{arm_route.UNKNOWN: UNKNOWN_POSE, arm_route.NOT_TAUGHT: NOT_TAUGHT,
                          arm_route.BLOCKED: NOT_TAUGHT, arm_route.NEAR_HEAD: NEAR_HEAD}.get(e.args, UNSURE)) from e
    return route, swings


def wave(on_start=None):
    """Plan, check and wave; the arm stays at START. `on_start()` is called once the plan is checked.
    Raises WaveError (refused) or motion.MotionError (stopped / failed while moving: the arm stays where it stopped)."""
    try:
        route, swings = plan()
    except (motion.MotionError, skills.SkillError, ConnectionError, OSError, KeyError, ValueError) as e:
        log(f"wave refused: {e}")
        raise WaveError(*UNSURE) from e
    log(f"wave: {len(route) + len(swings)} joint moves, checked")
    if on_start:
        on_start()
    if route:                                         # up as arm_route.goto, a stop at each pose; softer into START
        t0 = time.time()
        log(f"arm to {' -> '.join(n for n, _ in route)}")
        motion.move_path([(j, arm_route.SPEED) for _, j in route[:-1]] + [(route[-1][1], ARRIVE_SPEED)])
        log(f"arm at {START} after {time.time() - t0:.1f} s")
    if route and motion._stopped.wait(motion.SETTLE_S):   # stand at START first, as between any two moves
        raise motion.MotionError("stopped")
    t0 = time.time()
    motion.move_path([(t, SWING_SPEED) for t in swings], queued=True)   # back to back, no stop between swings
    log(f"wave: {SWINGS} swings after {time.time() - t0:.1f} s")


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "check"
    try:
        if what == "check":
            route, swings = plan()
            print([n for n, _ in route], [[round(v, 1) for v in t] for t in swings])
        elif what == "run":
            wave()
            print("done")
        else:
            sys.exit(__doc__)
    except WaveError as e:
        sys.exit(f"refused: {e.args[0]}")
    except KeyboardInterrupt:
        print(motion.stop())
