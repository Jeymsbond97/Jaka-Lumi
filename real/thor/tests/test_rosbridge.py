"""Self-check of reading the base's lidar for the Lumi app's position correction: the rosbridge WebSocket frames
(robot/rosbridge.py) and the scan as points around the base's centre (api/server.py /map/scan). Fake socket, no robot:
python tests/test_rosbridge.py"""
import json
import math
import struct

import no_robot                                     # noqa: F401  any connection to the robot fails the test

from robot import rosbridge
from api import server

# a client frame is masked and carries the JSON; a server frame (unmasked, maybe split over reads) is read back
f = rosbridge.client_frame(b'{"op":"x"}')
assert f[0] == 0x81 and f[1] & 0x80 and len(f) == 2 + 4 + 10, f
mask, body = f[2:6], f[6:]
assert bytes(b ^ mask[i % 4] for i, b in enumerate(body)) == b'{"op":"x"}'
big = json.dumps({"msg": {"ranges": [1.0] * 300}}).encode()
server_frame = bytes([0x81, 126]) + struct.pack(">H", len(big)) + big


class Sock:
    def __init__(self, data, step=50):
        self.data, self.step = data, step

    def recv(self, n):
        out, self.data = self.data[:self.step], self.data[self.step:]
        return out


msg, rest = rosbridge.read_message(Sock(server_frame + b"\x81\x02{}"), b"")
assert msg["msg"]["ranges"][0] == 1.0 and len(msg["msg"]["ranges"]) == 300, msg
assert rest == b"\x81\x02{}" or rest == b"", rest

# the scan as points (x ahead, y left, m) around the base's centre: the lidar sits LASER_X ahead of it
scan = {"angle_min": -math.pi / 2, "angle_increment": math.pi / 2, "range_min": 0.05, "range_max": 30.0,
        "ranges": [1.0, 2.0, 1.0, None, 0.01, 50.0]}
pts = server.scan_points(scan, every=1)
assert len(pts) == 3, pts                            # None, too near and too far left out
assert pts[0] == [round(server.LASER_X, 3), -1.0], pts[0]          # right of the lidar
assert pts[1] == [round(server.LASER_X + 2.0, 3), 0.0], pts[1]     # ahead
assert pts[2] == [round(server.LASER_X, 3), 1.0], pts[2]           # left
assert len(server.scan_points({**scan, "ranges": [1.0] * 6}, every=2)) == 3   # every 2nd

# /map/scan reads one message of the base's /scan
server.rosbridge.read_once = lambda topic, timeout=3.0: {"msg": scan} if topic == "/scan" else None
r = server.map_scan()
assert r["points"] == server.scan_points(scan) and r["frame"] == "base", r   # every 2nd ray by default

print("ok: rosbridge and scan")
