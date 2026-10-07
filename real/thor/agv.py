"""Mobile base (AGV) over its TCP API (192.168.10.10:31001).

    python agv.py                 # status + markers
    python agv.py go point1       # drive to a marker (returns at once)
    python agv.py cancel
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
            buf += s.recv(65536).decode()
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
    """Name of the charging-dock marker (type 11) on the current map, or None."""
    for name, m in (request("/api/markers/query_list").get("results") or {}).items():
        if m.get("key") == 11:
            return name
    return None


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
