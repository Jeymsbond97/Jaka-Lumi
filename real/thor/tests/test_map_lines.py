"""Self-check of the no-go lines the Lumi app draws (2026-11-17): save one on this floor, delete one, refuse bad input,
and a base that refuses. Fake base and rosbridge, no robot: python tests/test_map_lines.py"""
import json

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from fastapi import HTTPException

from api import server

calls = []
reply = {"success": True, "message": ""}
server.agv.request = lambda cmd, timeout=3.0: {"results": {"map_name": "office", "floor": 2}}
server.rosbridge.call_service = lambda service, args, timeout=3.0: (calls.append((service, args["cmd"],
                                                                                  json.loads(args["message"]))), reply)[1]


def refused(fn, *a, code):
    try:
        fn(*a)
    except HTTPException as e:
        return e.status_code == code
    return False


r = server.line_save(server.NoGoLineBody(name="door_1", points=[[0, 1.23456], [2, 1]]))
assert calls == [("/forbidden_manager/action_service", "add_lines", {"data": [
    {"name": "door_1", "type": "forbidden", "floor": 2, "points": [[0, 1.235], [2, 1]], "comment": "",
     "properties": "{}"}]})], calls
calls.clear()
server.line_delete(server.MarkerName(name="door_1"))
assert calls == [("/forbidden_manager/action_service", "delete_lines", {"names": ["door_1"]})], calls
calls.clear()

assert refused(server.line_save, server.NoGoLineBody(name="a b", points=[[0, 0], [1, 1]]), code=422)
assert refused(server.line_save, server.NoGoLineBody(name="x", points=[[0, 0], [1]]), code=422)
try:
    server.NoGoLineBody(name="x", points=[[0, 0]])                  # one point is not a line
    raise AssertionError("one point accepted")
except ValueError:
    pass
assert calls == [], calls

reply = {"success": False, "message": "busy"}
assert refused(server.line_save, server.NoGoLineBody(name="x", points=[[0, 0], [1, 1]]), code=502)
print("ok: map lines")
