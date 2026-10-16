"""Mobile base (AGV) over its TCP API (192.168.10.10:31001).

    python robot/agv.py                 # status + markers
    python robot/agv.py go point1       # drive to a marker (returns at once)
    python robot/agv.py cancel
"""
import json
import socket
import sys
import uuid

AGV = ("192.168.10.10", 31001)
DOCK_FALLBACK = "충전위치로"      # dock marker name on the old map; on any map the type-11 marker is used


def request(command, timeout=3.0):
    tag = uuid.uuid4().hex
    command += ("&" if "?" in command else "?") + f"uuid={tag}"
    buf, dec = "", json.JSONDecoder()
    with socket.create_connection(AGV, timeout=timeout) as s:
        s.sendall(command.encode())
        while True:
            chunk = s.recv(65536)
            if not chunk:                            # the base closed the connection: never loop forever
                raise ConnectionError(f"AGV closed the connection ({command.split('?')[0]})")
            buf += chunk.decode()
            while buf.strip():
                try:
                    msg, end = dec.raw_decode(buf.lstrip())
                except json.JSONDecodeError:
                    break
                buf = buf.lstrip()[end:]
                if msg.get("uuid") == tag:
                    return msg


def status():
    return request("/api/robot_status").get("results", {})


def dock_marker():
    """Name of the main charging-dock marker on the current map ("home"): of the type-11 markers the one with the
    lowest dock number (num); None when there is none. Further docks keep their own names (dock2, ...)."""
    docks = [(m.get("num", 1), name) for name, m in (request("/api/markers/query_list").get("results") or {}).items()
             if m.get("key") == 11]
    return min(docks)[1] if docks else None


def markers():
    """Marker names on the current map; the dock marker is called "home"."""
    names = list((request("/api/markers/query_brief").get("results") or {}).keys())
    dock = dock_marker()
    return ["home" if n == dock else n for n in names]


def go(marker):
    """Start driving to a marker. Returns (ok, message)."""
    marker = (dock_marker() or DOCK_FALLBACK) if marker == "home" else marker
    if status().get("move_status") == "running":
        request("/api/move/cancel")
    r = request(f"/api/move?marker={marker}")
    return r.get("status") == "OK", r.get("error_message") or r.get("status")


def go_point(x, y, theta):
    """Start driving to a map point (m, rad). Returns (ok, message)."""
    if status().get("move_status") == "running":
        request("/api/move/cancel")
    r = request(f"/api/move?location={x:.3f},{y:.3f},{theta:.3f}")
    return r.get("status") == "OK", r.get("error_message") or r.get("status")


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
