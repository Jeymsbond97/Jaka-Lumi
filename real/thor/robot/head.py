"""Turn Lumi's head (body HTTP API on the arm/body controller).

    python robot/head.py               # print lift, waist, head yaw, head pitch
    python robot/head.py 10            # head yaw to +10 deg (slow), other joints unchanged
    python robot/head.py 10 5          # head yaw +10 deg, head pitch +5 deg
    python robot/head.py 30 --vel 60   # try another speed (speed ratio %, 1-100)
"""
import json
import sys
import threading
import time
import urllib.request

BODY = "http://192.168.10.90:5000/api/extaxis"
YAW_LIMIT = 60.0                 # deg; we keep the head well inside its +-180 range
STILL_S = 0.1                    # s between two position reads that must agree before a move is sent
TURN_TIMEOUT_S = 8.0             # s a head turn may take (estimate, to measure); a move the controller never reported
                                 # done held every other body move 30 s and Lumi stopped listening (2026-10-30)
PITCH_RANGE = (-5.0, 35.0)       # deg, hardware range
HEAD_REST_PITCH = PITCH_RANGE[0]  # deg; the head's rest: its lowest, looking down (+pitch = up), so sitting people
                                 # and near things are in view. Every "head back / ahead" uses it; yaw rests at 0
VEL = 40                         # speed ratio %, 1-100 (was 15: too slow to follow a visitor)
ACC = 40                         # acceleration ratio %, 1-100
ENABLE_TIMEOUT_S = 10.0          # s for reset / enable: the controller answers enable after more than 2 s (2026-11-13:
                                 # the app's BODY enable failed twice with a 2 s timeout right after a power cycle)
# Temporary: the head camera's cable is too short, any lift above the bottom pulls it out, so the lift stays at 0 and
# Lumi searches by driving and turning. Back to 250 mm (the body API allows 300) when the longer cable is in.
LIFT_MAX_MM = 0.0
# The controller's waist reading when the torso faces the base's front (the torso camera and the logo over the base's
# middle): owner by eye 2026-11-13; at the controller's 0 the torso stood about 20 deg to the left. Every waist angle
# outside this file is from the front (+ left), so 0 is the front everywhere; only _call's raw values are not.
WAIST_FRONT_DEG = -20.4
# [lift mm, waist, head yaw, head pitch] limits of the body API (docs/03: waist -140..140 on the controller), the lift
# held to LIFT_MAX_MM, the waist from the front. The controller drops a whole moveto when any value is outside, and its
# own encoders read a little past the ends (pitch -5.003 at the bottom stop).
AXIS_LIMITS = ((0.0, LIFT_MAX_MM), (-140.0 - WAIST_FRONT_DEG, 140.0 - WAIST_FRONT_DEG), (-180.0, 180.0), (-5.0, 35.0))

_one = threading.Lock()          # one moveto at a time: overlapping calls hang the body API
owners = ()                      # threads that own the body now (tasks/follow.py); empty: anyone may move it


def _call(path, body=None, timeout=2):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{BODY}/{path}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def moveto(pos, vel=VEL, acc=ACC, timeout=30):
    """Move all four body joints (the waist from the front); every value is clamped into AXIS_LIMITS. Blocks until the
    motion ends (and while another thread's moveto runs). None, nothing sent, when other threads own the body
    (`owners`)."""
    if owners and threading.current_thread() not in owners:
        return None                                        # ponytail: skipped silently, the owner turns it back
    pos = [max(lo, min(hi, float(p))) for p, (lo, hi) in zip(pos, AXIS_LIMITS)]
    with _one:
        end = time.time() + timeout
        joints = _call("status")
        while time.time() < end:                           # another process's move still runs: a moveto sent meanwhile
            time.sleep(STILL_S)                            # is dropped and its call never answers (checked 2026-10-30:
            before, joints = joints, _call("status")       # 20 s timeout, no motion). "vel" reads 0 while moving, so
            if all(abs(a["pos"] - b["pos"]) < 0.05 for a, b in zip(before, joints)):   # the positions tell
                break
        if not all(j["enable"] for j in joints):           # off after a controller power cycle; moveto needs them on
            _call("enable", {"enable": 1}, timeout=ENABLE_TIMEOUT_S)
        raw = [pos[0], pos[1] + WAIST_FRONT_DEG, pos[2], pos[3]]   # the controller counts the waist from its own 0
        return _call("moveto", {"pos": raw, "vel": vel, "acc": acc}, timeout=max(1.0, end - time.time()))


def joints():
    """The controller's status, one dict per joint (id, pos, vel, toq, enable, error, ecode), the waist's pos from the
    front (WAIST_FRONT_DEG)."""
    j = _call("status")
    j[1] = {**j[1], "pos": j[1]["pos"] - WAIST_FRONT_DEG}
    return j


def status():
    """[lift mm, waist deg, head yaw deg, head pitch deg]"""
    return [j["pos"] for j in joints()]


def enabled():
    """True when all four body joints are enabled."""
    return all(j["enable"] for j in joints())


def set_enabled(on, retries=5):
    """Enable (vendor pattern: reset, enable, check, repeat) or disable all four body joints. Returns enabled()."""
    with _one:                                             # never in the middle of a moveto
        if not on:
            _call("enable", {"enable": 0}, timeout=ENABLE_TIMEOUT_S)
            return enabled()
        for _ in range(retries):
            _call("reset", {}, timeout=ENABLE_TIMEOUT_S)
            _call("enable", {"enable": 1}, timeout=ENABLE_TIMEOUT_S)
            if enabled():
                return True
            time.sleep(0.3)
        return enabled()


def turn(yaw, pitch=None, vel=VEL, acc=ACC, limit=YAW_LIMIT):
    """Move the head, yaw within +-`limit`; blocks until the motion ends. Returns the controller's reply."""
    lift, waist, _, cur_pitch = status()
    yaw = max(-limit, min(limit, yaw))
    pitch = cur_pitch if pitch is None else max(PITCH_RANGE[0], min(PITCH_RANGE[1], pitch))
    return moveto([lift, waist, yaw, pitch], vel, acc, timeout=TURN_TIMEOUT_S)


if __name__ == "__main__":
    args = sys.argv[1:]
    vel = VEL
    if "--vel" in args:
        i = args.index("--vel")
        vel = float(args[i + 1])
        del args[i:i + 2]
    if not args:
        print(dict(zip(["lift_mm", "waist", "head_yaw", "head_pitch"], (round(p, 2) for p in status()))))
    else:
        print(turn(float(args[0]), float(args[1]) if len(args) > 1 else None, vel))
        print("now:", [round(p, 2) for p in status()])
