"""Self-check of robot/arm.py retries, no robot: python tests/test_arm.py"""
import no_robot                                     # noqa: F401  any connection to the robot fails the test
from robot import arm

sent = []


def flaky(name, args):
    """The controller closes the first connection without a reply."""
    sent.append(name)
    if len(sent) == 1:
        raise ConnectionError("closed")
    return {"errorCode": "0"}


arm._send = flaky
arm.time.sleep = lambda s: None
assert arm.cmd("moveL", relFlag=0, cartPosition=[0] * 6) == {"errorCode": "0"} and sent == ["moveL", "moveL"]
sent.clear()
assert arm.cmd("set_digital_output", type=1, index=1, value=1) == {"errorCode": "0"} and sent == ["set_digital_output"] * 2
sent.clear()
arm._send = flaky
try:
    arm.cmd("joint_move", relFlag=1, jointPosition=[0] * 6)
    raise AssertionError("relative move sent again")
except ConnectionError:
    assert sent == ["joint_move"]

# the gripper asks again when get_data comes without the tool I/O
from robot import gripper
answers = [{}, {"joint_actual_position": [0] * 6}, {"tio_ain": [2300.0, 0.0], "tio_din": [0, 0], "tio_dout": [1, 0]}]
arm.cmd = lambda name, **a: answers.pop(0)
gripper.time.sleep = lambda s: None
assert gripper.state()["holding"] and not answers
arm.cmd = lambda name, **a: {}
try:
    gripper.state()
    raise AssertionError("no tool I/O accepted")
except ConnectionError:
    pass

# a reply to another command (get_data to get_joint_pos) is asked again
from robot import motion
answers = [{"cmdName": "get_data", "tio_ain": [0, 0]}, {"cmdName": "get_joint_pos", "joint_pos": [1.0] * 6}]
arm.cmd = lambda name, **a: answers.pop(0)
assert motion.joints() == [1.0] * 6 and not answers
print("arm ok")
