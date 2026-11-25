"""A scripted (not learned) sorting run in the sorting scene: inverse kinematics and fixed waypoints, nothing more.
It shows the scene can be solved with this arm, gripper and layout before any learning, and gives a baseline.

For each ball, nearest to the tray's front edge first: above it, straight down until the grasp point (between the
pad centres) is at the ball's centre, close (a full 1 s stroke, as the Zimmer does), lift, over the box of its
colour, open, back up. The hand points its fingers straight down; the jaws close along x, the way the balls are
spaced widest.

    .venv-sim/bin/python sim/sorting/scripted_demo.py           # result in the terminal
    .venv-sim/bin/python sim/sorting/scripted_demo.py --video   # also media/sorting_scripted.mp4
"""
import math
import sys
from pathlib import Path

import mujoco
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402  (scene numbers: table, tray, boxes, stroke)

ABOVE = 0.09            # m above the ball's centre before going down
CARRY_Z = build.TABLE_Z + build.BOX_OUT[2] + 0.045  # grasp point height while carrying: the ball clears the rim by ~2 cm
SPEED = 0.15            # m/s of the grasp point on straight moves
STROKE_S = 1.0          # the Zimmer's full stroke
FPS = 30
JOINT_RAD_S = math.radians(50)   # the robot's normal joint speed (robot/motion.py JOINT_SPEED)


class Sim:
    def __init__(self, video):
        self.m = mujoco.MjModel.from_xml_path(str(HERE / "sorting.xml"))
        self.d = mujoco.MjData(self.m)
        self.ik = mujoco.MjData(self.m)
        self.qadr = [self.m.jnt_qposadr[self.m.joint(f"j{i}").id] for i in range(1, 7)]
        self.dadr = [self.m.jnt_dofadr[self.m.joint(f"j{i}").id] for i in range(1, 7)]
        self.lim = np.array([self.m.jnt_range[self.m.joint(f"j{i}").id] for i in range(1, 7)])
        self.tcp = self.m.site("tcp").id
        self.grip = self.m.actuator("gripper").id
        self.frames, self.video = [], video
        if video:
            self.r = mujoco.Renderer(self.m, 720, 960)
            self.opt = mujoco.MjvOption()
            self.opt.geomgroup[3] = 0
        self.next_frame = 0.0

    # ---------- inverse kinematics on the grasp point ----------
    def _err(self, q, target, Rd):
        d = self.ik
        d.qpos[self.qadr] = q
        mujoco.mj_kinematics(self.m, d)
        R = d.site_xmat[self.tcp].reshape(3, 3)
        er = 0.5 * sum(np.cross(R[:, k], Rd[:, k]) for k in range(3))
        return np.concatenate([target - d.site_xpos[self.tcp], 0.1 * er])    # 0.1 m per radian

    def _solve(self, target, seed, psi):
        m, d = self.m, self.ik
        x = np.array([0, 0, -1.0])
        y = np.array([math.cos(psi), math.sin(psi), 0.0])
        Rd = np.column_stack([x, y, np.cross(x, y)])
        q = np.array(seed, float)
        e = self._err(q, target, Rd)
        for _ in range(300):
            if np.linalg.norm(e[:3]) < 2e-4 and np.linalg.norm(e[3:]) < 2e-4:
                return q
            mujoco.mj_comPos(m, d)
            jp, jr = np.zeros((3, m.nv)), np.zeros((3, m.nv))
            mujoco.mj_jacSite(m, d, jp, jr, self.tcp)
            J = np.vstack([jp[:, self.dadr], 0.1 * jr[:, self.dadr]])
            dq = J.T @ np.linalg.solve(J @ J.T + 1e-6 * np.eye(6), e)
            step = 1.0
            while step > 1e-3:                                   # take the step only if it helps
                qn = np.clip(q + step * np.clip(dq, -0.3, 0.3), self.lim[:, 0], self.lim[:, 1])
                en = self._err(qn, target, Rd)
                if np.linalg.norm(en) < np.linalg.norm(e):
                    q, e = qn, en
                    break
                step /= 2
            else:
                return None
            self._err(q, target, Rd)
        return None

    def solve(self, target, seed, psi=None, restarts=True):
        """(joint angles, hand turn) putting the grasp point at `target` with the fingers straight down. `psi`: the
        jaws' direction about the vertical; None tries every 15 deg from the hand's present turn outwards."""
        d = self.ik
        d.qpos[self.qadr] = seed
        mujoco.mj_kinematics(self.m, d)
        y = d.site_xmat[self.tcp].reshape(3, 3)[:, 1]
        now = math.atan2(y[1], y[0])
        tries = [psi] if psi is not None else [now + math.radians(k * s) for k in range(0, 181, 15) for s in (1, -1)][1:]
        rng = np.random.default_rng(0)
        seeds = [np.array(seed)] + ([rng.uniform(self.lim[:, 0] / 2, self.lim[:, 1] / 2) for _ in range(6)] if restarts else [])
        for s in seeds:                       # the nearest solution first; other arm postures only when it has none
            for p in tries:
                q = self._solve(target, s, p)
                if q is not None:
                    return q, p
        raise RuntimeError(f"no IK solution for {np.round(target * 1000)} mm")

    def approach(self, b, seed):
        """(grasp, above, turn): one hand turn that reaches both the ball and the point ABOVE it, nearest the seed."""
        self.ik.qpos[self.qadr] = seed
        mujoco.mj_kinematics(self.m, self.ik)
        y = self.ik.site_xmat[self.tcp].reshape(3, 3)[:, 1]
        now = math.atan2(y[1], y[0])
        rng = np.random.default_rng(1)
        for s in [np.array(seed)] + [rng.uniform(self.lim[:, 0] / 2, self.lim[:, 1] / 2) for _ in range(6)]:
            for k in range(0, 181, 15):
                for sign in (1, -1):
                    p = now + sign * math.radians(k)
                    qg = self._solve(b, s, p)
                    qa = self._solve(b + [0, 0, ABOVE], qg, p) if qg is not None else None
                    if qa is not None:
                        return qg, qa, p
        raise RuntimeError(f"cannot reach the ball at {np.round(b * 1000)} mm with the fingers down")

    # ---------- moving ----------
    def step(self, n=1):
        for _ in range(n):
            mujoco.mj_step(self.m, self.d)
            if self.video and self.d.time >= self.next_frame:
                self.r.update_scene(self.d, camera="overview", scene_option=self.opt)
                self.frames.append(self.r.render().copy())
                self.next_frame += 1.0 / FPS

    def arm_q(self):
        return self.d.qpos[self.qadr].copy()

    def drive(self, q_to, seconds, settle=True):
        q0 = np.array(self.d.ctrl[:6])
        n = max(1, int(seconds / self.m.opt.timestep))
        for k in range(n):
            s = (k + 1) / n
            s = s * s * (3 - 2 * s)                      # smooth start and stop
            self.d.ctrl[:6] = q0 + (q_to - q0) * s
            self.step()
        if settle:
            self.step(int(0.15 / self.m.opt.timestep))

    def line(self, target, q_seed, psi):
        """Straight move of the grasp point (down to a ball, up from it), solved every 5 mm, the hand's turn kept."""
        start = self.d.site_xpos[self.tcp].copy()
        n = max(1, int(np.linalg.norm(target - start) / 0.005))
        q = q_seed
        for k in range(1, n + 1):
            q, _ = self.solve(start + (target - start) * k / n, q, psi, restarts=False)
            self.drive(q, 0.005 / SPEED, settle=False)
        self.step(int(0.15 / self.m.opt.timestep))
        return q

    def joint_move(self, target, q_seed):
        """To a pose by a joint move (the controller's joint_move), as fast as JOINT_RAD_S allows."""
        q, psi = self.solve(target, q_seed)
        self.drive(q, max(0.3, np.abs(q - q_seed).max() / JOINT_RAD_S))
        return q, psi

    def gripper(self, open_):
        a0 = self.d.ctrl[self.grip]
        a1 = build.JAW_STROKE if open_ else 0.0
        n = int(STROKE_S / self.m.opt.timestep)
        for k in range(n):
            self.d.ctrl[self.grip] = a0 + (a1 - a0) * (k + 1) / n
            self.step()
        self.step(int(0.2 / self.m.opt.timestep))


def ball_colour(m, i):
    rgba = m.geom(f"ball_{i}").rgba
    return "red" if rgba[1] < 0.5 else "yellow"            # red 0.86 0.12 0.12, yellow 0.97 0.80 0.10


def box_centre(colour):
    side = build.BOXES[colour]
    return np.array([build.TRAY_C[0] + side * (build.TRAY_OUT[0] / 2 + build.BOX_GAP + build.BOX_OUT[0] / 2),
                     build.TRAY_C[1], build.TABLE_Z])


def in_box(pos, colour):
    c = box_centre(colour)
    return (abs(pos[0] - c[0]) < build.BOX_OUT[0] / 2 and abs(pos[1] - c[1]) < build.BOX_OUT[1] / 2
            and pos[2] < build.TABLE_Z + build.BOX_OUT[2])


def in_tray(pos):
    return (abs(pos[0] - build.TRAY_C[0]) < build.TRAY_OUT[0] / 2 and abs(pos[1] - build.TRAY_C[1]) < build.TRAY_OUT[1] / 2
            and pos[2] < build.TABLE_Z + build.TRAY_OUT[2] + build.BALL_R)


def main():
    video = "--video" in sys.argv
    sim = Sim(video)
    m, d = sim.m, sim.d
    # start: open, the hand above the tray
    d.qpos[m.jnt_qposadr[m.joint("jaw_l").id]] = d.qpos[m.jnt_qposadr[m.joint("jaw_r").id]] = build.JAW_STROKE
    d.ctrl[sim.grip] = build.JAW_STROKE
    # the owner's taught grasp (data/grasp_teach.json): fingers down at a cup on this table
    seed = np.radians([-297.606897, -78.356094, -28.782753, -143.133593, 40.177249, -277.868113])
    home = np.array([*build.TRAY_C, CARRY_Z])
    q, _ = sim.solve(home, seed)
    d.qpos[sim.qadr] = q
    d.ctrl[:6] = q
    mujoco.mj_forward(m, d)
    sim.step(int(0.5 / m.opt.timestep))

    balls = sorted(range(6), key=lambda i: d.xpos[m.body(f"ball_{i}").id][1])
    results = []
    try:
        run(sim, balls, results, q, home)
    finally:
        finish(sim, results, video)


def run(sim, balls, results, q, home):
    m, d = sim.m, sim.d
    home_q = q.copy()
    for i in balls:
        colour = ball_colour(m, i)
        b = d.xpos[m.body(f"ball_{i}").id].copy()
        if not in_tray(b):
            results.append(False)
            print(f"ball {i} ({colour}): KNOCKED out of the tray, at ({b[0] * 1000:.0f}, {b[1] * 1000:.0f}, {b[2] * 1000:.0f}) mm")
            continue
        # the hand's turn is chosen at the grasp (the tightest place to reach), then kept on the way down and up
        q_grasp, q_above, psi = sim.approach(b, home_q)
        sim.drive(q_above, max(0.3, np.abs(q_above - q).max() / JOINT_RAD_S))
        q = sim.line(b, q_above, psi)
        sim.gripper(open_=False)
        q = sim.line(np.array([b[0], b[1], CARRY_Z]), q, psi)
        c = box_centre(colour)
        q_box, _ = sim.solve(np.array([c[0], c[1], CARRY_Z]), q, restarts=False)
        sim.drive(q_box, max(0.3, np.abs(q_box - q).max() / JOINT_RAD_S))
        q = q_box
        sim.gripper(open_=True)
        sim.step(int(0.6 / m.opt.timestep))
        p = d.xpos[m.body(f"ball_{i}").id]
        ok = in_box(p, colour)
        results.append(ok)
        print(f"ball {i} ({colour}): {'in its box' if ok else 'MISSED'} at ({p[0] * 1000:.0f}, {p[1] * 1000:.0f}, "
              f"{p[2] * 1000:.0f}) mm, t={d.time:.1f} s")
        sim.drive(home_q, max(0.3, np.abs(home_q - q).max() / JOINT_RAD_S))
        q = home_q


def finish(sim, results, video):
    print(f"sorted {sum(results)} of {len(results)} in {sim.d.time:.0f} s of robot time")
    if video:
        import cv2
        out = HERE / "media" / "sorting_scripted.mp4"
        w = cv2.VideoWriter(str(out), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (960, 720))
        for f in sim.frames:
            w.write(f[:, :, ::-1])
        w.release()
        print(f"video: {out.relative_to(build.REPO)}")


if __name__ == "__main__":
    main()
