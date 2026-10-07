"""Read-only network check of the real Lumi. Nothing moves.

Run on the robot Wi-Fi (no internet needed):
    python3 tools/robot_check.py
The report is printed and saved to docs/private/robot_check_<time>.txt (git-ignored).
"""
import datetime
import json
import pathlib
import socket
import ssl
import subprocess
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

CONTROLLER = "192.168.10.90"   # arm (Cobo π, SDK) + body API
AGV = "192.168.10.10"
ROUTER = "192.168.10.79"
PORTS = {
    CONTROLLER: [443, 80, 5000, 10000, 10001],
    AGV: [31001, 9001, 8809, 8808],
    ROUTER: [80],
}

lines = []


def out(text=""):
    print(text)
    lines.append(text)


def port_open(host, port, timeout=1.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_get(url, timeout=3.0):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(url, timeout=timeout, context=ctx) as r:
            return r.read().decode(errors="replace")
    except Exception as e:
        return f"ERROR {e}"


def agv(command, timeout=5.0):
    """Send one TCP command to the AGV, return its response message."""
    tag = uuid.uuid4().hex
    command += ("&" if "?" in command else "?") + f"uuid={tag}"
    buf, dec = "", json.JSONDecoder()
    try:
        with socket.create_connection((AGV, 31001), timeout=timeout) as sock:
            sock.sendall(command.encode())
            while True:
                buf += sock.recv(65536).decode()
                while buf.strip():
                    try:
                        msg, end = dec.raw_decode(buf.lstrip())
                    except json.JSONDecodeError:
                        break
                    buf = buf.lstrip()[end:]
                    if msg.get("type") == "response" and msg.get("uuid") == tag:
                        return msg
    except Exception as e:
        return f"ERROR {e}"


def my_addresses():
    try:
        return subprocess.run(["ifconfig"], capture_output=True, text=True).stdout
    except Exception as e:
        return f"ERROR {e}"


def scan_subnet():
    """Find hosts on 192.168.10.0/24 with SSH (22) open: the onboard computer / Thor."""
    hosts = [f"192.168.10.{i}" for i in range(1, 255)]
    with ThreadPoolExecutor(64) as pool:
        ssh = [h for h, ok in zip(hosts, pool.map(lambda h: port_open(h, 22, 0.5), hosts)) if ok]
        web = [h for h, ok in zip(hosts, pool.map(lambda h: port_open(h, 80, 0.5), hosts)) if ok]
    return ssh, web


def main():
    out(f"Lumi read-only check  {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    out("=" * 60)

    out("\n[1] This computer's IPv4 addresses")
    for line in my_addresses().splitlines():
        if "inet " in line and "127.0.0.1" not in line:
            out("   " + line.strip())

    out("\n[2] Ports")
    for host, ports in PORTS.items():
        for p in ports:
            out(f"   {host}:{p:<6} {'OPEN' if port_open(host, p) else 'closed'}")

    out("\n[3] Body API (read only)")
    for ep in ("sysinfo", "status"):
        out(f"   /api/extaxis/{ep}: {http_get(f'http://{CONTROLLER}:5000/api/extaxis/{ep}')[:800]}")

    out("\n[4] AGV (read only)")
    for cmd in ("/api/robot_status", "/api/software/get_version", "/api/get_power_status",
                "/api/map/get_current_map", "/api/markers/query_brief"):
        reply = agv(cmd)
        out(f"   {cmd}: {json.dumps(reply, ensure_ascii=False)[:1500] if isinstance(reply, dict) else reply}")

    out("\n[5] Cobo π page title")
    page = http_get(f"https://{CONTROLLER}")
    out("   " + (page[page.find("<title>"):page.find("</title>") + 8] if "<title>" in page else page[:200]))

    out("\n[6] Devices on 192.168.10.x (looking for the Thor)")
    ssh, web = scan_subnet()
    out(f"   SSH (22) open: {ssh or 'none'}")
    out(f"   HTTP (80) open: {web or 'none'}")

    path = pathlib.Path(__file__).resolve().parent.parent / "docs" / "private" / \
        f"robot_check_{datetime.datetime.now():%Y%m%d_%H%M%S}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
