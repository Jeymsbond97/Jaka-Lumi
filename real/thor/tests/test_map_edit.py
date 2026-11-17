"""Self-check of the map edits for the Lumi app (2026-11-16): save a marker where Lumi stands or at a tapped pose,
delete one (a charger's too), save a charger's marker, set Lumi's position on the map. Fake base, no robot: python tests/test_map_edit.py"""
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from fastapi import HTTPException

from api import server
import tempfile, pathlib
server.MARKER_TIMES = pathlib.Path(tempfile.mkdtemp()) / "marker_times.json"   # not the real file
server._map_dates = lambda: {}
dated = []
server._mark_time = lambda name, when: dated.append((name, when is not None))   # the date book is test_map_info's

sent = []
server.agv.request = lambda cmd, timeout=3.0: sent.append(cmd) or {"status": "OK", "results": {}}
server.agv.dock_marker = lambda: "Home"
server.agv.known_markers = lambda fresh=False: sent.append("refresh") if fresh else None
server.robot_free = lambda manual=False: None


def refused(fn, *a, code=409):
    try:
        fn(*a)
    except HTTPException as e:
        return e.status_code == code
    return False


# where Lumi stands, and at a tapped pose (an existing name is moved there)
server.marker_save(server.MarkerBody(name="door_1"))
assert sent == ["/api/markers/insert?name=door_1&type=0&num=1", "refresh"], sent
assert dated == [("door_1", True)], dated                        # dated, so the app lists it first
sent.clear()
server.marker_save(server.MarkerBody(name="p11", x=1.5, y=-2.25, theta=0.5))
assert sent == ["/api/markers/insert_by_pose?name=p11&x=1.5&y=-2.25&theta=0.5&type=0", "refresh"], sent
sent.clear()
for bad in ("", "a b", "x/y", "로비", "a" * 51):     # the base takes letters, digits, _ and - only
    assert refused(server.marker_save, server.MarkerBody(name=bad), code=422), bad
assert sent == [], sent

# delete, the main dock too (the owner moves the charger; the app warns that Lumi then cannot dock)
server.marker_delete(server.MarkerName(name="door_1"))
assert sent == ["/api/markers/delete?name=door_1", "refresh"], sent
sent.clear()
server.marker_delete(server.MarkerName(name="Home"))
assert sent == ["/api/markers/delete?name=Home", "refresh"], sent
sent.clear()

# a charger's marker (type 11): its own dock number when it is one, else the next free one
marks = {"Home": {"key": 11, "num": 1}, "p1": {"key": 0}}
server.agv.request = lambda cmd, timeout=3.0: (sent.append(cmd) or {"status": "OK", "results": marks if "query_list" in cmd else {}})
server.marker_save(server.MarkerBody(name="Home", charger=True))
assert sent[-2] == "/api/markers/insert?name=Home&type=11&num=1", sent
server.marker_save(server.MarkerBody(name="dock_b", x=1, y=2, theta=0, charger=True))
assert sent[-2] == "/api/markers/insert_by_pose?name=dock_b&x=1.0&y=2.0&theta=0.0&type=11&num=2", sent
server.agv.request = lambda cmd, timeout=3.0: sent.append(cmd) or {"status": "OK", "results": {}}
sent.clear()

# Lumi's position on the map (relocalise), only while nothing runs
server.map_position(server.PointBody(x=-1.2, y=0.05, theta=-0.04))
assert sent == ["/api/position_adjust_by_pose?x=-1.2&y=0.05&theta=-0.04"], sent
sent.clear()
server.robot_free = lambda manual=False: (_ for _ in ()).throw(HTTPException(409, server.BUSY_MSG))
assert refused(server.map_position, server.PointBody(x=0, y=0))
assert sent == []


# the map picture in the app's dark look: unknown almost black, free space dark, walls light (same size). The base's
# clean ui_map.png (three colours, BGR) when it has one; else its raw grid map.png (205 unknown, 255 free, 0 walls)
import cv2                                           # noqa: E402
import numpy as np                                   # noqa: E402
ui = np.full((4, 6, 3), 250, np.uint8)               # unknown
ui[1, 1:5] = (253, 241, 234)                         # free
ui[2, 2] = (194, 177, 161)                           # outline
grid = np.full((4, 6), 205, np.uint8)
grid[1, 1:5] = 255
grid[2, 2] = 0
pngs = {"ui_map.png": cv2.imencode(".png", ui)[1].tobytes(), "map.png": cv2.imencode(".png", grid)[1].tobytes()}


def fake_open(url, timeout=10):
    name = url.rsplit("/", 1)[1]
    if name not in pngs:
        raise OSError("404")
    return type("R", (), {"read": lambda s: pngs[name], "__enter__": lambda s: s, "__exit__": lambda s, *a: False})()


server.agv.request = lambda cmd, timeout=3.0: {"results": {"map_name": "m", "floor": 1}}
server.urllib.request.urlopen = fake_open
for _ in range(2):                                   # with ui_map.png, then without it
    out = cv2.imdecode(np.frombuffer(server.map_image(dark=True).body, np.uint8), cv2.IMREAD_COLOR)
    assert out.shape == (4, 6, 3), out.shape
    assert tuple(out[0, 0]) == server.DARK_UNKNOWN[::-1] and tuple(out[1, 1]) == server.DARK_FREE[::-1], (out[0, 0], out[1, 1])
    assert tuple(out[2, 2]) == server.DARK_WALL[::-1], out[2, 2]
    pngs.pop("ui_map.png", None)
assert server.map_image().body == pngs["map.png"]       # as the base draws it, unless asked
# Lumi stands at a marker: the base takes its pose from it (after a map switch, the quickest way)
sent.clear()
server.agv.request = lambda cmd, timeout=3.0: sent.append(cmd) or {"status": "OK", "results": {}}
server.robot_free = lambda manual=False: None
server.map_position_marker(server.MarkerName(name="Home"))
assert sent == ["/api/position_adjust?marker=Home"], sent
assert refused(server.map_position_marker, server.MarkerName(name="a b"), code=422)

print("ok: map edits")
