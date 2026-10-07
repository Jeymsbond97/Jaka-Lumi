"""Turn Lumi's head (body HTTP API on the arm/body controller).

    python head.py               # print lift, waist, head yaw, head pitch
    python head.py 10            # head yaw to +10 deg (slow), other joints unchanged
    python head.py 10 5          # head yaw +10 deg, head pitch +5 deg
"""
import json
import sys
import urllib.request

BODY = "http://192.168.10.90:5000/api/extaxis"
YAW_LIMIT = 60.0                 # deg; we keep the head well inside its +-180 range
PITCH_RANGE = (-5.0, 35.0)       # deg, hardware range
VEL = 15                         # speed ratio %, slow


def _call(path, body=None, timeout=2):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(f"{BODY}/{path}", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def status():
    """[lift mm, waist deg, head yaw deg, head pitch deg]"""
    return [j["pos"] for j in _call("status")]


def turn(yaw, pitch=None, vel=VEL):
    """Move the head; blocks until the motion ends. Returns the controller's reply."""
    lift, waist, _, cur_pitch = status()
    yaw = max(-YAW_LIMIT, min(YAW_LIMIT, yaw))
    pitch = cur_pitch if pitch is None else max(PITCH_RANGE[0], min(PITCH_RANGE[1], pitch))
    return _call("moveto", {"pos": [lift, waist, yaw, pitch], "vel": vel, "acc": 20}, timeout=30)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print(dict(zip(["lift_mm", "waist", "head_yaw", "head_pitch"], (round(p, 2) for p in status()))))
    else:
        print(turn(float(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else None))
        print("now:", [round(p, 2) for p in status()])
