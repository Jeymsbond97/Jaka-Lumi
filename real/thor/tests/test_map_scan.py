"""Self-check of making a new map from the Lumi app (2026-11-17, api/server.py /map/scan/*): start under a new name
(refused while busy, for a bad or taken name, or while a scan runs), the state with the pose and progress, the
growing picture matched to its geometry, save, and cancel (saved then deleted, only a map started here). Fake base,
map builder and rosbridge, no robot: python tests/test_map_scan.py"""
import base64
import json
import tempfile
from pathlib import Path

import cv2
import numpy as np

import no_robot                                     # noqa: F401  any connection to the robot fails the test
from fastapi import HTTPException

from api import server

server.SCAN_FILE = Path(tempfile.mkdtemp()) / "lumi_mapping.json"     # never the real /dev/shm file
gets, calls = [], []
builder = {"mapbuilding": False, "hotelid": "", "floor": ""}
picture = cv2.imencode(".png", np.full((4, 6), 255, np.uint8))[1].tobytes()     # 6 x 4 pixels, all free


def build_get(path, timeout=5.0):
    gets.append(path)
    if path.startswith("map-build-api/get_info"):
        return json.dumps({"success": True, **builder}).encode()
    if path.startswith("map-build-api/start"):
        builder.update(mapbuilding=True, hotelid=path.split("hotelid=")[1].split("&")[0], floor="1", map_type="v2")
        return b'{"success": true}'
    if path == "map-build-api/stop":
        builder.update(mapbuilding=False)
        return b'{"success": true}'
    if path.startswith("maps/"):
        return picture
    raise AssertionError(path)


current = {"map_name": "office", "floor": 1}
server._build_get = build_get
server.agv.request = lambda cmd, timeout=3.0: {"results": {"office": [1], "lab": [1]} if cmd == "/api/map/list"
                                               else dict(current)}
delete_reply = {"success": True, "message": ""}


def call_service(service, args, timeout=3.0):
    calls.append((service, args))
    if service == "/rosapi/get_param":
        return {"value": '"[0.02,0.03,0.05]"'}
    return delete_reply


meta = {"width": 6, "height": 4, "resolution": 0.05, "origin": {"position": {"x": -1.0, "y": -2.0, "z": 0}}}
server.rosbridge.call_service = call_service
server.rosbridge.read_once = lambda topic, timeout=3.0: {"op": "publish", "topic": topic, "msg": meta}
server.rosbridge.read_many = lambda topics, timeout=1.5: {
    "/robot_pose": {"position": {"x": 1.0, "y": 2.0, "z": 0},
                    "orientation": {"x": 0, "y": 0, "z": 0.7071068, "w": 0.7071068}},
    "/map_metadata": meta, "/optimizing_progress": {"data": 1.4}}
busy = {"assistant": False, "task": False}


def robot_free(manual=False):
    if (manual and busy["task"]) or (not manual and busy["assistant"]):
        raise HTTPException(409, "busy")


server.robot_free = robot_free


def refused(fn, *a, code=409):
    try:
        fn(*a)
    except HTTPException as e:
        return e.status_code == code
    return False


# nothing runs: the state says so, nothing to see or save
assert server.scan_state() == {"mapping": False, "name": "", "floor": 1, "map_type": "", "pose": None,
                               "progress": None, "map": None}
assert refused(server.scan_picture) and refused(server.scan_save) and refused(server.scan_cancel)

# refused: a bad name, a size it does not know, a map that exists, while busy (nothing is started)
for bad in ("", "a b", "a-b", "로비", "a" * 37):
    assert refused(server.scan_start, server.NewMapBody(name=bad), code=422), bad
assert refused(server.scan_start, server.NewMapBody(name="hall", size="huge"), code=422)
assert refused(server.scan_start, server.NewMapBody(name="lab"))
for what in ("assistant", "task"):
    busy[what] = True
    assert refused(server.scan_start, server.NewMapBody(name="hall")), what
    busy[what] = False
assert not any(g.startswith("map-build-api/start") for g in gets), gets

# start: small map (the base's first delta), v2, floor 1; remembered with the maps there were
r = server.scan_start(server.NewMapBody(name="hall_2"))
assert r["ok"] and r["delta"] == 0.02, r
assert "map-build-api/start?hotelid=hall_2&floor=1&delta=0.02&map_type=v2" in gets, gets
assert json.loads(server.SCAN_FILE.read_text())["maps"] == ["lab", "office"]
assert refused(server.scan_start, server.NewMapBody(name="other"))           # one at a time
assert refused(server.map_switch, server.MapBody(map_name="lab"))             # no other map while scanning
assert refused(server.map_position, server.PointBody(x=0, y=0))

# the state: pose (90° here), progress kept within 0..1, the map's geometry
s = server.scan_state()
assert s["mapping"] and s["name"] == "hall_2" and s["progress"] == 1.0, s
assert abs(s["pose"]["theta"] - 1.5708) < 1e-3 and s["pose"]["x"] == 1.0, s
assert s["map"] == {"width": 6, "height": 4, "resolution": 0.05, "origin_x": -1.0, "origin_y": -2.0}, s

# the picture: the growing map (map-temp.png) in the app's look, matched to its geometry by size
p = server.scan_picture()
assert any(g.startswith("maps/hall_2/1/map-temp.png") for g in gets), gets
assert p["exact"] and p["width"] == 6 and p["height"] == 4 and p["origin_x"] == -1.0, p
img = cv2.imdecode(np.frombuffer(base64.b64decode(p["png"]), np.uint8), cv2.IMREAD_COLOR)
assert img.shape == (4, 6, 3) and tuple(img[0, 0]) == server.DARK_FREE[::-1], img[0, 0]
picture = cv2.imencode(".png", np.full((5, 7), 255, np.uint8))[1].tobytes()    # grew; its geometry not seen yet
p = server.scan_picture()
assert not p["exact"] and (p["width"], p["height"]) == (7, 5), p

# save: the base's stop, then nothing runs
assert server.scan_save()["name"] == "hall_2"
assert "map-build-api/stop" in gets and not server.SCAN_FILE.exists()
assert refused(server.scan_save)

# cancel: saved, then deleted (a new name started here, not the map in use)
server.scan_start(server.NewMapBody(name="hall_3"))
calls.clear()
r = server.scan_cancel()
assert r["deleted"] is True, r
assert calls == [("/water_map_manager/map_service",
                  {"cmd": "delete_map", "message": json.dumps({"mapName": "hall_3", "floors": [1]})})], calls

# cancel of a scan not started here (the base's own page), or of the map in use: it stays
builder.update(mapbuilding=True, hotelid="office", floor="1")
calls.clear()
r = server.scan_cancel()
assert r["deleted"] is False and calls == [], (r, calls)
server.scan_start(server.NewMapBody(name="hall_4"))
current["map_name"] = "hall_4"
calls.clear()
r = server.scan_cancel()
assert r["deleted"] is False and calls == [], (r, calls)
current["map_name"] = "office"

# a base that refuses the delete: the map stays, said so
server.scan_start(server.NewMapBody(name="hall_5"))
delete_reply = {"success": False, "message": "no"}
r = server.scan_cancel()
assert r["deleted"] is False and "no" in r["note"], r

# a scan saved from the base's page: switching maps works again
server.SCAN_FILE.write_text(json.dumps({"name": "hall_6"}))
server.agv.request = lambda cmd, timeout=3.0: {"results": {}}
server.map_switch(server.MapBody(map_name="lab"))
assert not server.SCAN_FILE.exists()
print("ok: map scan")
