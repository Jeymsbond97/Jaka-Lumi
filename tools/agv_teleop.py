"""Drive the Lumi base from the keyboard in a terminal (AGV /api/joy_control).

    python3 tools/agv_teleop.py

Hold a key to move; release it and the base stops (each command lasts 0.5 s).
  w / s   forward / back          a / d   turn left / right
  space   stop + cancel any navigation goal
  m       save the current pose as a marker wp_01, wp_02, ... (for tools/agv_route.py)
  + / -   speed up / down          q       quit (sends stop)
Speed is capped at 0.3 m/s and 0.6 rad/s; it starts at 0.1 m/s and 0.3 rad/s.
"""
import curses
import json
import socket
import time
import uuid

AGV = ("192.168.10.10", 31001)
MAX_V, MAX_W = 0.3, 0.6          # m/s, rad/s (API limit is 0.5 / 1.0)
KEY_HOLD = 0.6                   # s without a key repeat before we treat the key as released (covers the OS repeat delay)


class Agv:
    def __init__(self):
        self.sock = socket.create_connection(AGV, timeout=3)
        self.sock.setblocking(False)

    def send(self, command):
        command += ("&" if "?" in command else "?") + f"uuid={uuid.uuid4().hex}"
        self.sock.sendall(command.encode())
        try:                     # drop replies; we do not wait for them
            while self.sock.recv(65536):
                pass
        except BlockingIOError:
            pass

    def drive(self, v, w):
        self.send(f"/api/joy_control?angular_velocity={w:.3f}&linear_velocity={v:.3f}")

    def stop(self):
        self.drive(0.0, 0.0)


def request(command):
    """Send one command on a separate connection and return its response."""
    tag = uuid.uuid4().hex
    command += ("&" if "?" in command else "?") + f"uuid={tag}"
    buf, dec = "", json.JSONDecoder()
    with socket.create_connection(AGV, timeout=2) as s:
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


def save_marker():
    """Insert a marker at the current pose, named after the existing wp_NN markers."""
    names = request("/api/markers/query_brief").get("results", {}) or {}
    nums = [int(n[3:]) for n in names if n.startswith("wp_") and n[3:].isdigit()]
    name = f"wp_{max(nums, default=0) + 1:02d}"
    reply = request(f"/api/markers/insert?name={name}")
    return f"{name}: {reply.get('status')} {reply.get('error_message', '')}"


def main(scr):
    curses.curs_set(0)
    scr.nodelay(True)
    agv = Agv()
    v_set, w_set = 0.1, 0.3
    last_key, cmd = 0.0, (0.0, 0.0)
    last_send, last_status, info, note = 0.0, 0.0, {}, ""

    while True:
        key = scr.getch()
        now = time.time()
        if key != -1:
            ch = chr(key) if 0 <= key < 256 else ""
            if ch == "q":
                break
            if ch == " ":
                agv.stop()
                agv.send("/api/move/cancel")
                cmd = (0.0, 0.0)
            elif ch == "m":
                agv.stop()
                cmd = (0.0, 0.0)
                try:
                    note = "marker " + save_marker()
                except OSError as e:
                    note = f"marker failed: {e}"
            elif ch in "+=":
                v_set, w_set = min(v_set + 0.05, MAX_V), min(w_set + 0.1, MAX_W)
            elif ch == "-":
                v_set, w_set = max(v_set - 0.05, 0.05), max(w_set - 0.1, 0.1)
            elif ch in "wsad":
                cmd = {"w": (v_set, 0.0), "s": (-v_set, 0.0),
                       "a": (0.0, w_set), "d": (0.0, -w_set)}[ch]
                last_key = now
        if now - last_key > KEY_HOLD:
            cmd = (0.0, 0.0)

        if now - last_send >= 0.1:                    # 10 Hz
            if cmd != (0.0, 0.0):
                agv.drive(*cmd)
            last_send = now
        if now - last_status >= 1.0:
            try:
                info = status()
            except OSError:
                info = {}
            last_status = now

        pose = info.get("current_pose", {})
        scr.erase()
        scr.addstr(0, 0, "Lumi base teleop   w/s forward/back   a/d turn   space stop   m marker   +/- speed   q quit")
        scr.addstr(2, 0, f"speed setting: {v_set:.2f} m/s  {w_set:.2f} rad/s")
        scr.addstr(3, 0, f"command now:   v={cmd[0]:+.2f} m/s  w={cmd[1]:+.2f} rad/s")
        scr.addstr(5, 0, f"pose: x={pose.get('x', 0):+.3f} m  y={pose.get('y', 0):+.3f} m  "
                         f"theta={pose.get('theta', 0):+.3f} rad")
        scr.addstr(6, 0, f"move: {info.get('move_status')}  soft E-stop: {info.get('soft_estop_state')}  "
                         f"hard E-stop: {info.get('hard_estop_state')}  battery: {info.get('power_percent')} %")
        scr.addstr(8, 0, note)
        scr.refresh()
        time.sleep(0.02)

    agv.stop()


if __name__ == "__main__":
    curses.wrapper(main)
