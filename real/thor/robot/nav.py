"""Where to drive to reach a person: a free spot about STOP_DIST in front of them that the base can get to.

The base's own /api/map/accessible_point_query answers every point unchanged, so the check is done here
on the map picture: free cells (white) that are at least ROBOT_RADIUS from any wall or unknown area, and
connected to where the robot stands now. Among those, the spot nearest to "STOP_DIST before the person on
the line from the robot" wins; the robot then faces the person.

    python robot/nav.py 1.0 2.0        # best spot to reach a person at map x=1.0, y=2.0 from where the robot is
"""
import math
import sys
import urllib.request

import cv2
import numpy as np

from robot import agv

AGV_WEB = "http://192.168.10.10:9001"
STOP_DIST = 1.0                  # m between the robot centre and the person
RING = (0.9, 1.6)                # m, distances from the person that are tried
ROBOT_RADIUS = 0.35              # m of clearance needed (base 0.54 m wide + the arm)
CLOSE_ENOUGH = 1.3               # m; nearer than this the robot does not move

_map = {}


def load_map():
    """Current map: dict(name, res, ox, oy, h, clear (bool mask), comp (component ids))."""
    cur = agv.request("/api/map/get_current_map")["results"]
    key = (cur["map_name"], cur["floor"])
    if _map.get("key") != key:
        url = f"{AGV_WEB}/maps/{urllib.request.quote(cur['map_name'])}/{cur['floor']}/map.png"
        img = cv2.imdecode(np.frombuffer(urllib.request.urlopen(url, timeout=10).read(), np.uint8),
                           cv2.IMREAD_GRAYSCALE)
        info = cur["info"]
        res = info["resolution"]
        free = (img > 240).astype(np.uint8)
        clearance = cv2.distanceTransform(free, cv2.DIST_L2, 5) * res
        clear = clearance >= ROBOT_RADIUS
        _, comp = cv2.connectedComponents(clear.astype(np.uint8), connectivity=8)
        _map.update(key=key, res=res, ox=info["origin_x"], oy=info["origin_y"], h=img.shape[0], w=img.shape[1],
                    clear=clear, comp=comp, free=free.astype(bool))
    return _map


def _cell(m, x, y):
    return int((x - m["ox"]) / m["res"]), int(m["h"] - (y - m["oy"]) / m["res"])


def _robot_component(m, x, y):
    """Component id of the robot's place (or of the nearest clear cell within 0.6 m: it may stand near a wall)."""
    cx, cy = _cell(m, x, y)
    r = int(0.6 / m["res"])
    best = None
    for dy in range(-r, r + 1, 2):
        for dx in range(-r, r + 1, 2):
            px, py = cx + dx, cy + dy
            if 0 <= px < m["w"] and 0 <= py < m["h"] and m["clear"][py, px]:
                d = dx * dx + dy * dy
                if best is None or d < best[0]:
                    best = (d, m["comp"][py, px])
    return None if best is None else best[1]


def approach(person_x, person_y, robot=None):
    """(x, y, theta) to drive to, "close" if already near enough, or None if no reachable spot."""
    rx, ry, _ = robot or agv.pose()
    if math.hypot(person_x - rx, person_y - ry) <= CLOSE_ENOUGH:
        return "close"
    m = load_map()
    comp = _robot_component(m, rx, ry)
    if comp is None:
        return None
    toward = math.atan2(ry - person_y, rx - person_x)          # from the person back to the robot
    ideal = (person_x + STOP_DIST * math.cos(toward), person_y + STOP_DIST * math.sin(toward))
    best = None
    for dist in np.arange(RING[0], RING[1] + 1e-6, 0.1):
        for a in np.radians(np.arange(0, 360, 10)):
            gx, gy = person_x + dist * math.cos(a), person_y + dist * math.sin(a)
            px, py = _cell(m, gx, gy)
            if not (0 <= px < m["w"] and 0 <= py < m["h"]) or not m["clear"][py, px] or m["comp"][py, px] != comp:
                continue
            score = math.hypot(gx - ideal[0], gy - ideal[1])
            if best is None or score < best[0]:
                best = (score, gx, gy)
    if best is None:
        return None
    _, gx, gy = best
    return gx, gy, math.atan2(person_y - gy, person_x - gx)


def reachable(x, y, robot=None):
    """True when the base can stand at map (x, y): a free cell, next to (0.6 m) the open area the robot is in.
    Near walls and furniture is allowed: that is where it stands to reach a table."""
    m = load_map()
    px, py = _cell(m, x, y)
    if not (0 <= px < m["w"] and 0 <= py < m["h"]) or not m["free"][py, px]:
        return False
    rx, ry, _ = robot or agv.pose()
    here = _robot_component(m, x, y)
    return here is not None and here == _robot_component(m, rx, ry)


def person_on_map(distance_m, angle_deg, waist_deg=0.0, robot=None):
    """Map position of a person seen at distance / angle (deg, + left, waist frame) from the robot."""
    rx, ry, th = robot or agv.pose()
    a = th + math.radians(angle_deg + waist_deg)
    return rx + distance_m * math.cos(a), ry + distance_m * math.sin(a)


if __name__ == "__main__":
    x, y = float(sys.argv[1]), float(sys.argv[2])
    print("robot", agv.pose())
    print("drive to", approach(x, y))
