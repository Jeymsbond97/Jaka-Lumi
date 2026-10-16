"""Self-check of robot/drive_log.py with made-up base status reads, no robot: python tests/test_drive_log.py"""
from robot import drive_log

MARKERS = {"p10": (3.0, 0.0)}
d = drive_log.DriveLog(MARKERS.get)


def read(status, x, t, target="p10", **kw):
    return d.update({"move_status": status, "move_target": target, "current_pose": {"x": x, "y": 0.0, "theta": 0.0},
                     "error_code": "00000000", "estop_state": False, "is_paused": False, **kw}, t)


assert read("succeeded", 0.0, 0) == []                                          # idle: nothing
assert read("running", 0.0, 1) == ["drive to p10: started at (0.00, 0.00), 3.00 m to go"]
assert read("running", 0.5, 3) == []
assert read("running", 1.0, 6) == ["drive to p10: on the way at (1.00, 0.00), 2.00 m to go"]
assert read("running", 2.7, 9) == []
lines = [l for t in range(10, 30) for l in read("running", 2.7, t)]            # stands still near the target
assert any(l.startswith("drive to p10: standing still for") and l.endswith("at (2.70, 0.00), 0.30 m to go")
           for l in lines), lines
assert any("seems stuck for" in l for l in lines), lines
assert read("running", 2.7, 30, estop_state=True) == ["base E-stop pressed"]
assert read("succeeded", 3.0, 35) == ["base E-stop released", "drive to p10: arrived after 34 s at (3.00, 0.00), 0.00 m to go"]
assert read("running", 3.0, 40, target="1Fn4d") == ["drive to 1Fn4d: started at (3.00, 0.00)"]   # a map point
assert read("canceled", 3.0, 41, target="1Fn4d") == ["drive to 1Fn4d: cancelled after 1 s at (3.00, 0.00)"]
assert read("succeeded", 3.0, 42, error_code="00000201") == ["base error code 00000201"]
assert read("succeeded", 3.0, 43) == ["base error code cleared"]
print("drive log ok")
