"""
Headless check of the Lumi simulation: body, base, pick-and-place, waving at a person.
Prints what happened and saves camera pictures to media/.

    python demo.py             # no window, just the checks
    mjpython demo.py --viewer  # watch it in the MuJoCo window (macOS needs mjpython)
"""
import sys
from pathlib import Path

import cv2
import numpy as np

from lumi_api import ARM_HOME, LumiSim

MEDIA = Path(__file__).parent / "media"


def save(robot, name, camera="head_cam"):
    MEDIA.mkdir(exist_ok=True)
    cv2.imwrite(str(MEDIA / name), cv2.cvtColor(robot.get_image(camera), cv2.COLOR_RGB2BGR))


def main():
    robot = LumiSim(viewer="--viewer" in sys.argv)

    print("1) body: lift 150 mm, head pitch 30 deg (look down at the table)")
    robot.body_moveto([150, 0, 0, 30])
    print("   status:", np.round(robot.body_status(), 1))
    save(robot, "head_table.png")
    robot.body_moveto([0, 0, 0, 30])

    print("2) pick the red cube and put it down 12 cm to the right")
    cube = robot.object_position("red_cube")
    robot.pick(cube)
    print("   cube height after pick: %.3f m (table top is 0.750)" % robot.object_position("red_cube")[2])
    goal = cube + [0, -0.12, 0]
    robot.place(goal)
    robot.arm_joint_move(ARM_HOME)
    robot.body_moveto([0, 0, 0, 30])
    print("   cube is %.3f m from the goal" % np.linalg.norm(robot.object_position("red_cube") - goal))
    save(robot, "after_place.png")

    print("3) base: back up 0.4 m, turn left 90 deg")
    robot.drive(-0.2, 0, 2.0)
    robot.drive(0, np.pi / 4, 2.0)
    print("   base pose (x, y, heading deg):", np.round(robot.base_pose(), 2))

    print("4) a person walks up, the robot looks up and waves")
    x, y, heading = robot.base_pose()
    robot.set_person(x + 1.5 * np.cos(np.deg2rad(heading)), y + 1.5 * np.sin(np.deg2rad(heading)))
    robot.body_moveto([0, 0, 0, -5])
    save(robot, "person.png")
    robot.wave()
    print("   done")

    if robot.viewer is not None:
        while robot.viewer.is_running():
            robot.step(0.02)


if __name__ == "__main__":
    main()
