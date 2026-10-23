"""Mobile base (AGV) over its TCP API (192.168.10.10:31001).

    python robot/agv.py                 # status + markers
    python robot/agv.py go point1       # drive to a marker (returns at once)
    python robot/agv.py cancel
"""
import json
import socket
import sys
import threading
import time
import uuid

AGV = ("192.168.10.10", 31001)
DOCK_FALLBACK = "충전위치로"      # dock marker name on the old map; on any map the type-11 marker is used
MARKERS_FRESH_S = 5.0            # known_markers() reads the list again after this long: a new map is seen within it
_known = {"t": 0.0, "names": []}
# One connection kept open per process: the base answers the first command on a new connection only after ~100 ms
# (often 200-300), on an open one in 1-2 ms (robot_status) / 5-15 ms (distance_probe), measured 2026-10-22; an idle
# connection still answered after 90 s.
_conn = {"sock": None, "buf": ""}
_conn_lock = threading.Lock()
# robot/nav_guard.py's state of the navigation move this process sent: gen counts go / go_point / cancel (a guard
# whose gen is old stops); held: the guard cancelled it until the way is clear; reason: (en, ko) why it ended it.
_guard = {"gen": 0, "held": False, "reason": None}


def _ask(command, tag, timeout):
    s = _conn["sock"]
    s.settimeout(timeout)
    s.sendall(command.encode())
    dec = json.JSONDecoder()
    while True:
        buf = _conn["buf"]
        while buf.strip():                           # replies to earlier timed-out commands are skipped by uuid
            try:
                msg, end = dec.raw_decode(buf.lstrip())
            except json.JSONDecodeError:
                break
            buf = _conn["buf"] = buf.lstrip()[end:]
            if msg.get("uuid") == tag:
                return msg
        chunk = s.recv(65536)
        if not chunk:                                # the base closed the connection: never loop forever
            raise ConnectionError(f"AGV closed the connection ({command.split('?')[0]})")
        _conn["buf"] += chunk.decode()


def request(command, timeout=3.0):
    tag = uuid.uuid4().hex
    command += ("&" if "?" in command else "?") + f"uuid={tag}"
    with _conn_lock:
        for again in (True, False):
            reused = _conn["sock"] is not None
            try:
                if not reused:
                    _conn["sock"] = socket.create_connection(AGV, timeout=timeout)
                    _conn["sock"].setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                return _ask(command, tag, timeout)
            except OSError as e:
                try:
                    _conn["sock"].close()
                except (OSError, AttributeError):
                    pass
                _conn.update(sock=None, buf="")
                if not (again and reused) or isinstance(e, TimeoutError):   # an old connection died: once more
                    raise


def status():
    """robot_status. A move nav_guard holds reads "running", one it ended "failed" with "guard": (en, ko)."""
    st = request("/api/robot_status").get("results", {})
    if st.get("move_status") in ("canceled", "idle"):
        if _guard["held"]:
            return {**st, "move_status": "running", "guard": "held"}
        if _guard["reason"]:
            return {**st, "move_status": "failed", "guard": _guard["reason"]}
    return st


def _move(command):
    """Send a navigation move (cancelling one that runs) and guard the arm along it (robot/nav_guard.py)."""
    if status().get("move_status") == "running":
        cancel()
    r = request(command)
    ok = r.get("status") == "OK"
    _guard.update(gen=_guard["gen"] + 1, held=False, reason=None)
    if ok:
        from robot import nav_guard           # imported here: it needs the arm (tasks.fetch), which imports this
        nav_guard.watch(command, _guard["gen"])
    return ok, r.get("error_message") or r.get("status")


def dock_marker():
    """Name of the main charging-dock marker on the current map ("home"): of the type-11 markers the one with the
    lowest dock number (num); None when there is none. Further docks keep their own names (dock2, ...)."""
    docks = [(m.get("num", 1), name) for name, m in (request("/api/markers/query_list").get("results") or {}).items()
             if m.get("key") == 11]
    return min(docks)[1] if docks else None


def marker_xy(name):
    """(x, y) of a marker on the map ("home" = the dock marker), None when there is no such marker."""
    name = (dock_marker() or DOCK_FALLBACK) if name == "home" else name
    m = (request("/api/markers/query_list").get("results") or {}).get(name) or {}
    p = (m.get("pose") or {}).get("position")
    return (p["x"], p["y"]) if p else None


def markers():
    """Marker names on the current map; the dock marker is called "home"."""
    names = list((request("/api/markers/query_brief").get("results") or {}).keys())
    dock = dock_marker()
    return ["home" if n == dock else n for n in names]


def known_markers(fresh=False):
    """markers(), read again when older than MARKERS_FRESH_S or when fresh (a name was not on the list); the last
    list while the base does not answer."""
    if fresh or time.time() - _known["t"] > MARKERS_FRESH_S:
        try:
            _known.update(names=markers(), t=time.time())
        except OSError:                          # ConnectionError and socket.timeout are OSErrors
            pass
    return _known["names"]


def go(marker):
    """Start driving to a marker. Returns (ok, message)."""
    marker = (dock_marker() or DOCK_FALLBACK) if marker == "home" else marker
    return _move(f"/api/move?marker={marker}")


def go_point(x, y, theta):
    """Start driving to a map point (m, rad). Returns (ok, message)."""
    return _move(f"/api/move?location={x:.3f},{y:.3f},{theta:.3f}")


def pose():
    """(x, y, theta) of the base on the map."""
    p = status()["current_pose"]
    return p["x"], p["y"], p["theta"]


def turn_by(angle_rad):
    """Turn in place by angle_rad (+ = left); the base plans it like a normal move."""
    x, y, th = pose()
    return go_point(x, y, (th + angle_rad + 3.14159265) % 6.2831853 - 3.14159265)


def probe(x, y):
    """(live, map): distance (m) from the map point (x, y) to the nearest obstacle the sensors see now and to the
    nearest one on the map; inf when there is none in range."""
    d = request(f"/api/map/distance_probe?x={x:.3f}&y={y:.3f}").get("results", {}).get("env_dist", {})
    return tuple(v if v is not None and v >= 0 else float("inf") for v in (d.get("obstacle"), d.get("static")))


def clearance(x, y):
    """Distance (m) from the map point (x, y) to the nearest obstacle the sensors see now or the map holds."""
    return min(probe(x, y))


def cancel():
    _guard.update(gen=_guard["gen"] + 1, held=False, reason=None)
    return request("/api/move/cancel").get("status")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "go":
        print(go(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == "cancel":
        print(cancel())
    else:
        st = status()
        print({k: st.get(k) for k in ("move_status", "move_target", "charge_state", "power_percent", "current_pose")})
        print("markers:", markers())
