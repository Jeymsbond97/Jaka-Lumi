"""Writes every drive of the base to the log, whoever started it (dashboard, fetch, assistant): the start, where it
is on the way and how far it still has to go, standing still, the end (arrived / failed / cancelled), E-stop and
error codes. The base's own status is read once a second. api/server.py runs it; the lines show in the dashboard's
Settings -> Logs.

    python robot/drive_log.py      # watch and print here (Ctrl+C)
"""
import math
import time

from robot import agv

POLL_S = 1.0           # s between base status reads
PROGRESS_S = 5.0       # s between "on the way" lines
STILL_M = 0.05         # m; moving less than this ...
STILL_S = 5.0          # ... for this long while driving -> "standing still" (again every STILL_S)
STUCK_S = 15.0         # standing still this long -> "seems stuck" (shown among the errors)
OK_CODE = "00000000"   # robot_status error_code when there is no error


class DriveLog:
    """Turns base status reads into log lines (update() returns the new ones)."""

    def __init__(self, marker_xy):
        self.marker_xy = marker_xy                 # f(name) -> (x, y) or None
        self.drive = None                          # target, start time, start pose of the drive in progress
        self.last_line = self.anchor = None        # time of the last progress line; (x, y, t) of the last real move
        self.flags = {}                            # error_code / estop / paused as last logged

    def _where(self, p, target):
        xy = self.marker_xy(target)
        left = f", {math.hypot(xy[0] - p['x'], xy[1] - p['y']):.2f} m to go" if xy else ""
        return f"at ({p['x']:.2f}, {p['y']:.2f}){left}"

    def update(self, st, now):
        out = []
        for key, bad, on, off in (("error_code", lambda v: v not in (None, OK_CODE), "base error code {v}",
                                   "base error code cleared"),
                                  ("estop_state", bool, "base E-stop pressed", "base E-stop released"),
                                  ("is_paused", bool, "base paused", "base running again")):
            v = st.get(key)
            if bad(v) != self.flags.get(key, False):
                self.flags[key] = bad(v)
                out.append(on.format(v=v) if bad(v) else off)
        status, target, p = st.get("move_status"), st.get("move_target"), st.get("current_pose")
        if p is None:
            return out
        running = status == "running"
        if running and (self.drive is None or self.drive["target"] != target):
            self.drive = {"target": target, "t0": now}
            self.last_line, self.anchor = now, (p["x"], p["y"], now)
            out.append(f"drive to {target}: started {self._where(p, target)}")
        elif running:
            moved = math.hypot(p["x"] - self.anchor[0], p["y"] - self.anchor[1])
            if moved >= STILL_M:
                self.anchor = (p["x"], p["y"], now)
            still = now - self.anchor[2]
            if still >= STILL_S and now - self.last_line >= STILL_S:
                word = "seems stuck" if still >= STUCK_S else "standing still"
                out.append(f"drive to {target}: {word} for {still:.0f} s {self._where(p, target)}")
                self.last_line = now
            elif still < STILL_S and now - self.last_line >= PROGRESS_S:
                out.append(f"drive to {target}: on the way {self._where(p, target)}")
                self.last_line = now
        elif self.drive is not None:
            took = now - self.drive["t0"]
            word = {"succeeded": "arrived", "failed": "failed", "canceled": "cancelled"}.get(status, status)
            out.append(f"drive to {self.drive['target']}: {word} after {took:.0f} s {self._where(p, self.drive['target'])}")
            self.drive = None
        return out


def marker_positions():
    """f(name) -> (x, y) of a marker on the current map; re-read when a name is not known yet."""
    cache = {}

    def xy(name):
        if name not in cache:
            try:
                for n, m in (agv.request("/api/markers/query_list").get("results") or {}).items():
                    cache[n] = (m["pose"]["position"]["x"], m["pose"]["position"]["y"])
            except (ConnectionError, OSError, KeyError):
                pass
            cache.setdefault(name, None)           # a map point's generated name: no marker
        return cache[name]
    return xy


def watch(log=print):
    d, down = DriveLog(marker_positions()), False
    while True:
        try:
            st = agv.status()
        except (ConnectionError, OSError):
            if not down:
                log("base not answering")
            down = True
            time.sleep(POLL_S)
            continue
        if down:
            log("base answering again")
            down = False
        for line in d.update(st, time.time()):
            log(line)
        time.sleep(POLL_S)


if __name__ == "__main__":
    try:
        watch(lambda line: print(time.strftime("%H:%M:%S"), line, flush=True))
    except KeyboardInterrupt:
        pass
