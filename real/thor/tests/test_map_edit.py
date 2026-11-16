"""Self-check of the map edits for the Lumi app (2026-11-16): save a marker where Lumi stands or at a tapped pose,
delete one (never the main dock), set Lumi's position on the map. Fake base, no robot: python tests/test_map_edit.py"""
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from fastapi import HTTPException

from api import server

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
sent.clear()
server.marker_save(server.MarkerBody(name="p11", x=1.5, y=-2.25, theta=0.5))
assert sent == ["/api/markers/insert_by_pose?name=p11&x=1.5&y=-2.25&theta=0.5&type=0", "refresh"], sent
sent.clear()
for bad in ("", "a b", "x/y", "로비", "a" * 51):     # the base takes letters, digits, _ and - only
    assert refused(server.marker_save, server.MarkerBody(name=bad), code=422), bad
assert sent == [], sent

# delete; never the main dock (docking needs it)
server.marker_delete(server.MarkerName(name="door_1"))
assert sent == ["/api/markers/delete?name=door_1", "refresh"], sent
sent.clear()
assert refused(server.marker_delete, server.MarkerName(name="Home"))
assert sent == [], sent

# Lumi's position on the map (relocalise), only while nothing runs
server.map_position(server.PointBody(x=-1.2, y=0.05, theta=-0.04))
assert sent == ["/api/position_adjust_by_pose?x=-1.2&y=0.05&theta=-0.04"], sent
sent.clear()
server.robot_free = lambda manual=False: (_ for _ in ()).throw(HTTPException(409, server.BUSY_MSG))
assert refused(server.map_position, server.PointBody(x=0, y=0))
assert sent == []


# the map picture in the app's dark look: unknown almost black, free space dark, walls light (same size)
import cv2                                           # noqa: E402
import numpy as np                                   # noqa: E402
pic = np.full((4, 6), 205, np.uint8)                 # unknown
pic[1, 1:5] = 255                                    # free
pic[2, 2] = 0                                        # a wall
png = cv2.imencode(".png", pic)[1].tobytes()
server.agv.request = lambda cmd, timeout=3.0: {"results": {"map_name": "m", "floor": 1}}
server.urllib.request.urlopen = lambda url, timeout=10: type("R", (), {"read": lambda s: png, "__enter__": lambda s: s,
                                                                    "__exit__": lambda s, *a: False})()
out = cv2.imdecode(np.frombuffer(server.map_image(dark=True).body, np.uint8), cv2.IMREAD_COLOR)
assert out.shape == (4, 6, 3), out.shape
assert tuple(out[0, 0]) == server.DARK_UNKNOWN[::-1] and tuple(out[1, 1]) == server.DARK_FREE[::-1], (out[0, 0], out[1, 1])
assert tuple(out[2, 2]) == server.DARK_WALL[::-1], out[2, 2]
assert server.map_image().body == png                # as the base draws it, unless asked


# Lumi stands at a marker: the base takes its pose from it (after a map switch, the quickest way)
sent.clear()
server.agv.request = lambda cmd, timeout=3.0: sent.append(cmd) or {"status": "OK", "results": {}}
server.robot_free = lambda manual=False: None
server.map_position_marker(server.MarkerName(name="Home"))
assert sent == ["/api/position_adjust?marker=Home"], sent
assert refused(server.map_position_marker, server.MarkerName(name="a b"), code=422)

print("ok: map edits")
