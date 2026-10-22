"""Wave the hand when someone asks for it. A greeting never moves the arm.

The arm waves only from a known start pose (START_POSES: `look`, where the robot stands). It goes through the taught
poses ROUTE (first the hand away from the head, then up), swings one wrist joint about the last of them and comes back
the same way. Before anything moves, every joint move of that sequence is checked: joint limits, no joint turning
further than motion.MAX_TRAVEL, and at PATH_POINTS points along it (kine_forward) the gripper (flange -> grasp point ->
finger tips) stays HEAD_CLEAR_MM from the head's turning centre (vision/head_cam.py). Refused, with the reason in
English and Korean: the arm off or busy, the base driving, a task running, something in the hand, the arm anywhere
else (after free drive, in carry or give), a pose not taught, a move too near the head.

The Cobo π program hand_shaking.jks is not used: it ran from wherever the arm was and hit the head from `look`
(2026-10-21).

    python manipulation/wave.py check      # plan and check from where the arm is now; moves nothing
    python manipulation/wave.py run        # wave (slow; the owner at the STOP)

Teach the route first, arm moved by hand in Cobo π: python robot/motion.py teach wave_start / teach wave
"""
import sys

import numpy as np

from manipulation import skills
from robot import agv, arm, gripper, motion
from vision import calib, head_cam

START_POSES = ("look",)              # the wave starts and ends only at one of these (motion.poses())
ROUTE = ("wave_start", "wave")       # taught poses from the start: the hand away from the head, then raised
AT_POSE_DEG = 3.0                    # deg; the arm is at a pose when every joint is this close
WAVE_JOINT = 4                       # joint index swung at the raised pose (4 = J5); check on the first slow run
WAVE_DEG = 15.0                      # deg each way from the raised pose
WAVE_SWINGS = 2                      # times there and back
WAVE_SPEED = "slow"                  # motion.JOINT_SPEED; the route and the swings
PATH_POINTS = 21                     # points checked (kine_forward) on every joint move
HEAD_CLEAR_MM = 250.0                # mm the gripper keeps from the head's turning centre. Estimate: the head camera
                                     # is 102 mm from it, the head's size is not measured. `look` keeps 327 mm, tuck 266

# Why Lumi does not wave, (English, Korean)
OFF = ("My arm is switched off, so I can't wave.", "팔이 꺼져 있어서 손을 흔들 수 없어요.")
BUSY = ("I'm busy with my arm right now.", "지금 팔로 하는 일이 있어요.")
DRIVING = ("I can't wave while I'm moving.", "움직이는 동안에는 손을 흔들 수 없어요.")
HOLDING = ("I'm holding something, so I won't wave.", "손에 물건을 들고 있어서 손을 흔들지 않을게요.")
UNKNOWN_POSE = ("My arm isn't in its usual place, so I won't wave. Please put it back first.",
                "팔이 평소 자세가 아니어서 손을 흔들지 않을게요. 먼저 팔을 제자리로 해 주세요.")
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


def _seg_dist(c, a, b):
    """mm from point c to the segment a-b."""
    ab = b - a
    t = min(1.0, max(0.0, float((c - a) @ ab) / float(ab @ ab))) if ab @ ab else 0.0
    return float(np.linalg.norm(c - (a + t * ab)))


def gripper_clearance(j, centre):
    """Smallest distance (mm) from `centre` to the gripper (flange -> grasp point -> finger tips) at joints j."""
    c = skills._ask("kine_forward", jointPosition=[float(v) for v in j])["cartPosition"]
    R, f = calib.rpy_matrix(*c[3:]), np.array(c[:3], float)
    g = f + R @ skills.GRASP_OFFSET
    tip = g + R @ (skills.TIP_MM * skills.FINGER_DIR)
    return min(_seg_dist(centre, f, g), _seg_dist(centre, g, tip))


def move_clearance(j0, j1, centre):
    """Smallest gripper distance (mm) to `centre` at PATH_POINTS points of the joint move j0 -> j1 (the controller
    moves all joints together, in a straight line in joint space)."""
    j0, j1 = np.array(j0, float), np.array(j1, float)
    return min(gripper_clearance(j0 + (j1 - j0) * k / (PATH_POINTS - 1), centre) for k in range(PATH_POINTS))


def _at(now, pose):
    return max(abs(a - b) for a, b in zip(motion.nearest(pose, now), now)) <= AT_POSE_DEG


def plan():
    """Joint targets of the whole wave from here, each move checked. Raises WaveError to refuse."""
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
    now, poses = motion.joints(), motion.poses()
    start = next((n for n in START_POSES if n in poses and _at(now, poses[n])), None)
    if start is None:
        log(f"wave refused: arm at {[round(v, 1) for v in now]}, not at {', '.join(START_POSES)}")
        raise WaveError(*UNKNOWN_POSE)
    if any(n not in poses for n in ROUTE):
        log(f"wave refused: teach {', '.join(n for n in ROUTE if n not in poses)} first (robot/motion.py teach)")
        raise WaveError(*NOT_TAUGHT)
    route = [list(poses[n]) for n in ROUTE]
    top, i = route[-1], WAVE_JOINT
    swings = [top[:i] + [top[i] + s * WAVE_DEG] + top[i + 1:] for _ in range(WAVE_SWINGS) for s in (1, -1)]
    seq, prev = [], now
    for t in route + swings + [top] + route[-2::-1] + [poses[start]]:
        motion.check(t)
        t = motion.nearest(t, prev)                  # as move_joints will turn it
        if max(abs(a - b) for a, b in zip(t, prev)) > motion.MAX_TRAVEL:
            log(f"wave refused: {[round(v, 1) for v in prev]} -> {[round(v, 1) for v in t]} turns a joint too far")
            raise WaveError(*NOT_TAUGHT)
        seq.append(t)
        prev = t
    centre = head_cam.head_centre()
    if centre is None:
        raise WaveError(*UNSURE)
    done = set()
    for a, b in zip([now] + seq, seq):
        key = frozenset((tuple(np.round(a, 1)), tuple(np.round(b, 1))))
        if key in done:                              # the way back and the repeated swings: checked once
            continue
        done.add(key)
        d = move_clearance(a, b, centre)
        if d < HEAD_CLEAR_MM:
            log(f"wave refused: {[round(v, 1) for v in a]} -> {[round(v, 1) for v in b]} brings the gripper "
                f"{d:.0f} mm from the head (needs {HEAD_CLEAR_MM:.0f})")
            raise WaveError(*NEAR_HEAD)
    return seq


def wave(on_start=None):
    """Plan, check and wave; back at the start pose at the end. `on_start()` is called once the plan is checked.
    Raises WaveError (refused) or motion.MotionError (stopped / failed while moving: the arm stays where it stopped)."""
    try:
        seq = plan()
    except (motion.MotionError, skills.SkillError, ConnectionError, OSError, KeyError, ValueError) as e:
        log(f"wave refused: {e}")
        raise WaveError(*UNSURE) from e
    log(f"wave: {len(seq)} joint moves, checked")
    if on_start:
        on_start()
    for t in seq:
        motion.move_joints(t, WAVE_SPEED)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "check"
    try:
        if what == "check":
            print([[round(v, 1) for v in t] for t in plan()])
        elif what == "run":
            wave()
            print("done")
        else:
            sys.exit(__doc__)
    except WaveError as e:
        sys.exit(f"refused: {e.args[0]}")
    except KeyboardInterrupt:
        print(motion.stop())
