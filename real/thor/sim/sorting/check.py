"""Checks of the sorting scene against the real robot, and pictures of it.

1. Arm: the simulated flange against the controller's own flange pose in every calibration sample
   (data/calib_samples*/: joint angles + the flange pose kine_forward reported).
2. Pictures: the scene from the side, from above and through the torso camera, with the arm in its `look` pose and
   over the tray (media/sorting_*.png).

    .venv-sim/bin/python sim/sorting/check.py
"""
import glob
import json
import math
from pathlib import Path

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA = REPO / "data"
MEDIA = HERE / "media"


def set_arm(m, d, joints_deg):
    for i, a in enumerate(joints_deg):
        d.qpos[m.jnt_qposadr[m.joint(f"j{i + 1}").id]] = math.radians(a)
        d.ctrl[m.actuator(f"j{i + 1}").id] = math.radians(a)


def flange_errors(m, d):
    errs, angs = [], []
    for f in sorted(glob.glob(str(DATA / "calib_samples*/*.json"))):
        s = json.loads(Path(f).read_text())
        set_arm(m, d, s["joints"])
        mujoco.mj_kinematics(m, d)
        sid = m.site("flange").id
        F = np.array(s["flange"])
        errs.append(np.linalg.norm(d.site_xpos[sid] * 1000 - F[:3, 3]))
        R = d.site_xmat[sid].reshape(3, 3) @ F[:3, :3].T
        angs.append(math.degrees(math.acos(max(-1.0, min(1.0, (np.trace(R) - 1) / 2)))))
    return np.array(errs), np.array(angs)


def render(m, d, camera, name, w=960, h=720):
    r = mujoco.Renderer(m, h, w)
    opt = mujoco.MjvOption()
    opt.geomgroup[3] = 0                     # collision shapes hidden
    r.update_scene(d, camera=camera, scene_option=opt)
    img = r.render()
    MEDIA.mkdir(exist_ok=True)
    path = MEDIA / f"sorting_{name}.png"
    import cv2
    cv2.imwrite(str(path), img[:, :, ::-1])
    r.close()
    return path


def main():
    m = mujoco.MjModel.from_xml_path(str(HERE / "sorting.xml"))
    d = mujoco.MjData(m)
    e, a = flange_errors(m, d)
    print(f"flange vs controller over {len(e)} samples: median {np.median(e):.2f} mm, max {e.max():.2f} mm; "
          f"turn median {np.median(a):.3f}, max {a.max():.3f} deg")

    poses = json.loads((DATA / "arm_poses.json").read_text())
    teach = json.loads((DATA / "grasp_teach.json").read_text())
    for label, joints in (("look", poses["look"]), ("grasp", teach["joints"])):
        mujoco.mj_resetData(m, d)
        set_arm(m, d, joints)
        d.ctrl[m.actuator("gripper").id] = 0.013          # open
        d.qpos[m.jnt_qposadr[m.joint("jaw_l").id]] = 0.013
        d.qpos[m.jnt_qposadr[m.joint("jaw_r").id]] = 0.013
        mujoco.mj_forward(m, d)
        for _ in range(300):                               # let the balls settle
            mujoco.mj_step(m, d)
        tcp = d.site_xpos[m.site("tcp").id] * 1000
        print(f"{label}: tcp at ({tcp[0]:.0f}, {tcp[1]:.0f}, {tcp[2]:.0f}) mm")
        for cam in ("overview", "top", "torso_cam"):
            print("  ", render(m, d, cam, f"{label}_{cam}").relative_to(REPO))


if __name__ == "__main__":
    main()
