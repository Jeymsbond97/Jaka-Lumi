"""The base's own settings the Lumi app's Map SETTINGS shows and changes: four of the base page's "configuration"
(:9001 robot-user-configuration.html), saved the way that page saves them: POST :9001/api/update_user_parameters
(kept by the base over a restart), then the ROS parameter itself (used at once).

Max speed is the base's ceiling. Lumi's own drives send their speed before every move (robot/agv.py max_speed,
tasks/fetch.py NAV_SPEED_MPS, tasks/follow.py): it is cut to that ceiling here, so a lower one holds for them too.
Their turn speed is left as they send it (follow turns at up to 1.0 rad/s, above the base's 0.7 of 2026-11-18).

    python robot/base_settings.py       # print them
"""
import json
import threading
import time
import urllib.request

from robot import rosbridge

BASE_PAGE = "http://192.168.10.10:9001"
# name: (ROS parameter, min, max, step, the base page's default); ranges as the base page allows them
SETTINGS = {
    "max_speed_linear": ("api_params/max_speed_linear", 0.1, 0.7, 0.1, 0.7),        # m/s; by robot type, see below
    "max_speed_angular": ("api_params/max_speed_angular", 0.1, 3.5, 0.1, 3.5),      # rad/s
    "pose_tolerance": ("move_base/DWAPlannerROS/xy_goal_tolerance", 0.05, 0.5, 0.01, 0.3),   # m
    "theta_tolerance": ("move_base/DWAPlannerROS/yaw_goal_tolerance", 0.05, 1.0, 0.01, 0.2),  # rad
}
# max speed's top (and default) by the base's robot type (/robot_global robot_type), as the base page sets it; ours is
# "WT" (1.2 m/s); other types keep 0.7
SPEED_TOP = {"WT": 1.2, "OCEAN": 0.9}
_type = {"name": None}
CAP_FRESH_S = 60.0          # the speed ceiling is read again after this long
_cap = {"t": 0.0, "linear": None}
_lock = threading.Lock()


def _get(param):
    v = rosbridge.call_service("/rosapi/get_param", {"name": "/" + param}).get("value")
    try:
        return float(json.loads(v)) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _robot_type():
    if _type["name"] is None:
        v = rosbridge.call_service("/rosapi/get_param", {"name": "/robot_global"}).get("value")
        _type["name"] = (json.loads(v) or {}).get("robot_type", "") if v else ""
    return _type["name"]


def ranges():
    """SETTINGS with max speed's top and default for this robot's type (asks the base once)."""
    out = dict(SETTINGS)
    top = SPEED_TOP.get(_robot_type())
    if top:
        param, lo, _, step, _ = SETTINGS["max_speed_linear"]
        out["max_speed_linear"] = (param, lo, top, step, top)
    return out


def read():
    """{name: value or None} as the base has them now; raises OSError when the base does not answer."""
    return {name: _get(s[0]) for name, s in SETTINGS.items()}


def write(name, value):
    """Save one setting (cut to its range and step); returns the value saved. Raises KeyError for an unknown name,
    OSError / RuntimeError when the base does not take it."""
    param, lo, hi, step, _ = ranges()[name]
    value = round(round(min(hi, max(lo, float(value))) / step) * step, 3)
    req = urllib.request.Request(f"{BASE_PAGE}/api/update_user_parameters", data=json.dumps({param: value}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=4) as r:
        reply = json.loads(r.read().decode() or "{}")
    if reply.get("status") != "OK":
        raise RuntimeError(f"base refused {name}: {reply.get('error_message') or reply}")
    rosbridge.call_service("/rosapi/set_param", {"name": "/" + param, "value": json.dumps(value)})
    with _lock:
        _cap["t"] = 0.0                     # read the ceiling again at the next drive
    return value


def ceiling():
    """The max speed ceiling (m/s), None when unknown; read at most every CAP_FRESH_S, never raises."""
    with _lock:
        if time.monotonic() - _cap["t"] > CAP_FRESH_S:
            try:
                _cap["linear"] = _get(SETTINGS["max_speed_linear"][0])
            except (OSError, RuntimeError):
                _cap["linear"] = None
            _cap["t"] = time.monotonic()
        return _cap["linear"]


def capped(linear, angular):
    """Lumi's own drive speed with its forward speed cut to the base's ceiling; the turn speed as it is."""
    cl = ceiling()
    return (min(linear, cl) if cl else linear), angular


if __name__ == "__main__":
    print(read())
