"""Self-check: a marker added on the base after the API started is in /map/info, /agv/markers and the assistant's
list at once (api/server.py, robot/agv.py), with a fake base, no robot: python tests/test_map_info.py"""
import time

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from api import server
from robot import agv

MARKS = {"home_dock": {"key": 11, "num": 1, "floor": 1, "pose": {"position": {"x": 0, "y": 0},
                                                                 "orientation": {"z": 0, "w": 1}}}}


def fake(cmd, timeout=3.0):
    path = cmd.split("?")[0]
    if path == "/api/map/get_current_map":
        return {"results": {"map_name": "office", "floor": 1, "info": {"resolution": 0.05}}}
    if path in ("/api/markers/query_list", "/api/markers/query_brief"):
        return {"results": {n: dict(m) for n, m in MARKS.items()}}
    if path == "/api/map/list":
        return {"results": {"office": [1]}}
    raise AssertionError(cmd)


agv.request = server.agv.request = fake
names = lambda d: [m["name"] for m in d["markers"]]
assert names(server.map_info()) == ["home_dock"]
assert server.markers()["markers"] == ["home"] and agv.known_markers() == ["home"]

MARKS["p13"] = {"key": 0, "floor": 1, "pose": {"position": {"x": 1.0, "y": 2.0}, "orientation": {"z": 0, "w": 1}}}
assert names(server.map_info()) == ["home_dock", "p13"]             # the next page load sees it
assert server.markers()["markers"] == ["home", "p13"]
assert agv.known_markers(fresh=True) == ["home", "p13"]             # a name not on the list: read again
agv._known["t"] = time.time() - agv.MARKERS_FRESH_S - 1
del MARKS["p13"]
assert agv.known_markers() == ["home"]                              # and within MARKERS_FRESH_S anyway
print("map info ok")
