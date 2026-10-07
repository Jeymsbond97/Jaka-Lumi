"""Drive the Lumi base through a list of markers, one after another (AGV /api/move).

    python3 tools/agv_route.py --list                 # show the markers on the current map
    python3 tools/agv_route.py wp_01 wp_02 wp_03      # visit them once, in order
    python3 tools/agv_route.py wp_01 wp_02 --loop 3   # repeat the route 3 times (0 = forever)
    python3 tools/agv_route.py --home                 # go back to the dock and charge
    python3 tools/agv_route.py new_table_01 home      # "home" = the dock marker, anywhere in a route
    python3 tools/agv_route.py --speed 0.3 0.5        # navigation speed limit m/s, rad/s (reset at AGV restart)

The base plans its own path and avoids obstacles. Ctrl+C cancels the move and stops.
Markers are made with the `m` key in tools/agv_teleop.py or "add marker" in the web panel.
"""
import argparse
import json
import socket
import time
import uuid

AGV = ("192.168.10.10", 31001)
DOCK_FALLBACK = "충전위치로"      # dock marker on the old map; on any map the type-11 marker is used


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
    """The charging-dock marker (type 11) of the current map; going there docks and charges."""
    for name, m in (request("/api/markers/query_list").get("results") or {}).items():
        if m.get("key") == 11:
            return name
    return DOCK_FALLBACK


def go(marker):
    """Send one move and wait for it to end. Returns the final move_status."""
    reply = request(f"/api/move?marker={marker}")
    if reply.get("status") != "OK":
        print(f"  {marker}: refused: {reply.get('status')} {reply.get('error_message')}")
        return "refused"
    print(f"  -> {marker}", end="", flush=True)
    time.sleep(0.5)
    while True:
        st = status()
        if st.get("move_status") in ("succeeded", "failed", "canceled"):
            p = st.get("current_pose", {})
            print(f"  {st['move_status']}  (x={p.get('x', 0):+.2f}, y={p.get('y', 0):+.2f}, "
                  f"theta={p.get('theta', 0):+.2f})")
            return st["move_status"]
        if st.get("soft_estop_state") or st.get("hard_estop_state"):
            print("  [E-stop on, waiting]", end="", flush=True)
        time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("markers", nargs="*")
    ap.add_argument("--loop", type=int, default=1, help="times to run the route, 0 = forever")
    ap.add_argument("--list", action="store_true", help="list markers on the current map")
    ap.add_argument("--home", action="store_true", help="go to the charging dock marker")
    ap.add_argument("--speed", nargs=2, type=float, metavar=("V", "W"),
                    help="set max navigation speed: m/s (0.1-1.0) and rad/s (0.5-3.5)")
    a = ap.parse_args()

    if a.speed:
        v, w = min(max(a.speed[0], 0.1), 1.0), min(max(a.speed[1], 0.5), 3.5)
        request(f"/api/set_params?max_speed_linear={v}&max_speed_angular={w}")
        print("Speed limits now:", request("/api/get_params").get("results"))
        if not (a.markers or a.home or a.list):
            return

    if a.list:
        dock = dock_marker()
        for name, floor_type in (request("/api/markers/query_brief").get("results") or {}).items():
            print(f"  {name}   (type-floor {floor_type}){'   = home' if name == dock else ''}")
        return
    dock = dock_marker()
    route = [dock] if a.home else [dock if m == "home" else m for m in a.markers]
    if not route:
        ap.error("give marker names, --list or --home")

    st = status()
    if st.get("move_status") == "running":
        print("A move is already running; cancel it first (space in agv_teleop.py or Cancel in the panel).")
        return
    print(f"Battery {st.get('power_percent')} %, route: {' -> '.join(route)}")

    try:
        lap = 0
        while a.loop == 0 or lap < a.loop:
            lap += 1
            print(f"Lap {lap}")
            for m in route:
                if go(m) in ("canceled", "refused"):
                    return
    except KeyboardInterrupt:
        print("\nCancelling...")
    finally:
        if status().get("move_status") == "running":
            request("/api/move/cancel")
            print("Move cancelled, base stopped.")


if __name__ == "__main__":
    main()
