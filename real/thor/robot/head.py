"""Turn Lumi's head (body HTTP API on the arm/body controller).

    python robot/head.py               # print lift, waist, head yaw, head pitch
    python robot/head.py 10            # head yaw to +10 deg (slow), other joints unchanged
    python robot/head.py 10 5          # head yaw +10 deg, head pitch +5 deg
    python robot/head.py 30 --vel 60   # try another speed (speed ratio %, 1-100)
"""
import json
import sys
import urllib.request

BODY = "http://192.168.10.90:5000/api/extaxis"
YAW_LIMIT = 60.0                 # deg; we keep the head well inside its +-180 range
PITCH_RANGE = (-5.0, 35.0)       # deg, hardware range
VEL = 40                         # speed ratio %, 1-100 (was 15: too slow to follow a visitor)
ACC = 40                         # acceleration ratio %, 1-100
# [lift mm, waist, head yaw, head pitch] limits of the body API (docs/03). The controller drops a whole moveto when
# any value is outside, and its own encoders read a little past the ends (pitch -5.003 at the bottom stop).
AXIS_LIMITS = ((0.0, 300.0), (-140.0, 140.0), (-180.0, 180.0), (-5.0, 35.0))


def _call(path, body=None, timeout=2):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{BODY}/{path}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def moveto(pos, vel=VEL, acc=ACC, timeout=30):
    """Move all four body joints; every value is clamped into AXIS_LIMITS. Blocks until the motion ends."""
    pos = [max(lo, min(hi, float(p))) for p, (lo, hi) in zip(pos, AXIS_LIMITS)]
    if not all(j["enable"] for j in _call("status")):      # off after a controller power cycle; moveto needs them on
        _call("enable", {"enable": 1})
    return _call("moveto", {"pos": pos, "vel": vel, "acc": acc}, timeout=timeout)


def status():
    """[lift mm, waist deg, head yaw deg, head pitch deg]"""
    return [j["pos"] for j in _call("status")]


def turn(yaw, pitch=None, vel=VEL, acc=ACC):
    """Move the head; blocks until the motion ends. Returns the controller's reply."""
    lift, waist, _, cur_pitch = status()
    yaw = max(-YAW_LIMIT, min(YAW_LIMIT, yaw))
    pitch = cur_pitch if pitch is None else max(PITCH_RANGE[0], min(PITCH_RANGE[1], pitch))
    return moveto([lift, waist, yaw, pitch], vel, acc)


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
