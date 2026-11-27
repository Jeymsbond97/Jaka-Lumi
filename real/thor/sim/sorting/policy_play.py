"""Sim-to-sim check: the sorting policy trained in Isaac Lab (Newton physics) run in this MuJoCo scene, a different
physics engine. It is given exactly the observations it had in training and its actions are used the same way (the
grasp point moved by the IK, the binary Zimmer), all read from the policy's JSON (rl/sorting/export_policy.py).
Episodes are counted the same way: one ball, the easiest on the tray, into the box of its colour.

    .venv-sim/bin/python sim/sorting/policy_play.py rl/sorting/policies/<run>_it<it>.onnx --episodes 100 --layouts all
    .venv-sim/bin/python sim/sorting/policy_play.py <policy.onnx> --sort-all --video     # every ball, then a clip

On the Thor pictures need MUJOCO_GL=egl.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import mujoco
import numpy as np
import onnxruntime as ort

HERE = Path(__file__).resolve().parent
BALLS = 6
FLOOR_Z = -1.008


class Player:
    def __init__(self, onnx_path, seed=0, video=False):
        self.meta = json.loads(Path(onnx_path).with_suffix(".json").read_text())
        mt = self.meta
        self.pol = ort.InferenceSession(str(onnx_path))
        self.inp = self.pol.get_inputs()[0].name
        self.student = bool(mt.get("student"))
        self.h = None                                   # the student's memory (GRU state), cleared each episode
        self.m = mujoco.MjModel.from_xml_path(str(HERE / "sorting.xml"))
        self.d = mujoco.MjData(self.m)
        m = self.m
        self.qadr = [m.jnt_qposadr[m.joint(f"j{i}").id] for i in range(1, 7)]
        self.dadr = [m.jnt_dofadr[m.joint(f"j{i}").id] for i in range(1, 7)]
        self.jaw_adr = m.jnt_qposadr[m.joint("jaw_l").id]
        self.jaw_r_adr = m.jnt_qposadr[m.joint("jaw_r").id]
        self.tcp = m.site("tcp").id
        self.grip = m.actuator("gripper").id
        self.ball_q = [m.jnt_qposadr[m.body(f"ball_{i}").jntadr[0]] for i in range(BALLS)]
        self.ball_v = [m.jnt_dofadr[m.body(f"ball_{i}").jntadr[0]] for i in range(BALLS)]
        self.is_red = np.arange(BALLS) % 2 == 0
        self.box_xy = np.array([mt["boxes"]["red"], mt["boxes"]["yellow"]])
        self.tray_c, self.tray_h = np.array(mt["tray_centre"]), np.array(mt["tray_inner_half"])
        self.r = mt["ball_r"]
        self.sub = int(round(mt["policy_dt"] / m.opt.timestep))
        self.ik_gain = mt["ik_rate_per_s"] * m.opt.timestep
        self.rng = np.random.default_rng(seed)
        self.frames, self.video = [], video
        self.use_oracle, self.phase = False, 0
        if video:
            self.renderer = mujoco.Renderer(m, 720, 1280)
            self.cam = m.camera("overview").id

    # ---------- state ----------
    def tcp_pose(self):
        return self.d.site_xpos[self.tcp].copy(), self.d.site_xmat[self.tcp].reshape(3, 3).copy()

    def balls(self):
        p = np.array([self.d.qpos[a:a + 3] for a in self.ball_q])
        v = np.array([self.d.qvel[a:a + 3] for a in self.ball_v])
        return p, v

    def on_tray(self, xy):
        return np.all(np.abs(xy - self.tray_c) <= self.tray_h + 0.01, axis=-1)

    def in_box(self, xy, box):
        return np.all(np.abs(xy - self.box_xy[box]) <= np.array(self.meta["box_inner_half"]), axis=-1)

    # ---------- the start of an episode ----------
    def layout(self, kind, n):
        """Ball centres (n, 2) for one of the layouts of rl/sorting/layouts.py; fewer if they do not fit."""
        half = self.tray_h - self.r - 0.002
        c, r = self.tray_c, self.r
        s = 2 * r + 0.0005
        if kind in ("scattered", "spread"):
            gap = 0.001 if kind == "scattered" else 0.02
            pts = []
            for _ in range(200):
                p = c + self.rng.uniform(-half, half)
                if all(np.linalg.norm(p - q) >= 2 * r + gap for q in pts):
                    pts.append(p)
                if len(pts) == n:
                    break
        elif kind == "row":
            a = self.rng.uniform(0, math.pi)
            pts = [c + self.rng.uniform(-half, half)]
            for _ in range(n - 1):
                a += self.rng.uniform(-0.2, 0.2)
                pts.append(pts[-1] + s * np.array([math.cos(a), math.sin(a)]))
        elif kind == "heap":
            ring = [(0, 0)] + [(s * math.cos(k * math.pi / 3), s * math.sin(k * math.pi / 3)) for k in range(6)]
            rot = self.rng.uniform(0, 2 * math.pi)
            R = np.array([[math.cos(rot), -math.sin(rot)], [math.sin(rot), math.cos(rot)]])
            cc = c + self.rng.uniform(-half * 0.5, half * 0.5)
            pts = [cc + R @ np.array(q) for q in ring[:n]]
        else:                                                       # pairs
            pts = []
            for _ in range(200):
                p = c + self.rng.uniform(-half, half)
                if all(np.linalg.norm(p - q) >= 4 * r + 0.01 for q in pts[::2]):
                    a = self.rng.uniform(0, 2 * math.pi)
                    pts += [p, p + s * np.array([math.cos(a), math.sin(a)])]
                if len(pts) >= n:
                    break
            pts = pts[:n]
        pts = [p for p in pts if np.all(np.abs(p - c) <= half + 1e-4)]
        keep = []
        for p in pts:
            if all(np.linalg.norm(p - q) >= 2 * r - 0.001 for q in keep):
                keep.append(p)
        return np.array(keep) if keep else np.array([c])

    def easiest(self, xy, active):
        """(ball, hand turn): the rule of manipulation/sort.py and rl/sorting/sort_env.py."""
        mt = self.meta
        yaws = np.radians(mt["yaws_deg"])
        best = (-99.0, 0, yaws[0])
        for i in np.flatnonzero(active):
            others = [xy[j] for j in np.flatnonzero(active) if j != i]
            room, turn = -9.0, yaws[0]
            for yw in yaws:
                u = mt["finger_out"] * np.array([math.cos(yw), math.sin(yw)])
                clear, onto = 9.0, False
                for f in (xy[i] + u, xy[i] - u):
                    for q in others:
                        dd = np.linalg.norm(f - q)
                        onto |= dd < mt["onto"]
                        clear = min(clear, dd - self.r - mt["finger_r"])
                if not onto and clear > room:
                    room, turn = clear, yw
            if room <= -9.0:
                continue
            score = 10.0 - np.linalg.norm(xy[i]) if room >= mt["clear"] else room
            if score > best[0]:
                best = (score, i, turn)
        return best[1], best[2]

    def reset(self, kind="spread", n=1, place=None):
        mt, m, d = self.meta, self.m, self.d
        mujoco.mj_resetData(m, d)
        q0 = np.array(mt["start_q"])
        d.qpos[self.qadr] = q0
        d.qpos[self.jaw_adr] = d.qpos[self.jaw_r_adr] = mt["jaw_open"]
        xy = self.layout(kind, n) if place is None else np.array(place)
        ids = self.rng.permutation(BALLS)[:len(xy)]
        self.active = np.zeros(BALLS, bool)
        self.active[ids] = True
        rest = mt["tray_floor_z"] + self.r + 0.0005
        for i in range(BALLS):
            a = self.ball_q[i]
            if self.active[i]:
                k = list(ids).index(i)
                z = rest + (self.rng.uniform(0.05, 0.15) if kind == "scattered" else 0.0)
                d.qpos[a:a + 3] = [xy[k][0], xy[k][1], z]
            else:
                d.qpos[a:a + 3] = [-0.6 + 0.06 * i, -0.5, FLOOR_Z + self.r]
            d.qpos[a + 3:a + 7] = [1, 0, 0, 0]
        mujoco.mj_forward(m, d)
        self.arm_goal = q0.copy()
        d.ctrl[:6] = q0
        self.jaw_goal = self.jaw_cmd = mt["jaw_open"]
        d.ctrl[self.grip] = self.jaw_cmd
        self.close_cmd = False
        self.actions = np.zeros(4)
        bxy = np.array([d.qpos[self.ball_q[i]:self.ball_q[i] + 2] for i in range(BALLS)])
        self.ball, self.yaw = self.easiest(bxy, self.active)
        self.box = 0 if self.is_red[self.ball] else 1
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        y, z = np.array([cy, sy, 0.0]), np.array([0.0, 0.0, -1.0])
        self.R_des = np.column_stack([np.cross(y, z), y, z])
        self.start_z = rest
        self.held = False
        if self.student:
            self.camera_reset()

    def next_ball(self):
        """After a ball, as on the robot: the arm back at the start pose, open; the balls and the clock go on. Returns
        False when no ball is left on the tray."""
        mt, m, d = self.meta, self.m, self.d
        p, _ = self.balls()
        self.active = self.active & self.on_tray(p[:, :2])
        if not self.active.any():
            return False
        q0 = np.array(mt["start_q"])
        d.qpos[self.qadr] = q0
        d.qvel[self.dadr] = 0.0
        d.qpos[self.jaw_adr] = d.qpos[self.jaw_r_adr] = mt["jaw_open"]
        mujoco.mj_forward(m, d)
        self.arm_goal = q0.copy()
        d.ctrl[:6] = q0
        self.jaw_goal = self.jaw_cmd = mt["jaw_open"]
        d.ctrl[self.grip] = self.jaw_cmd
        self.close_cmd, self.held = False, False
        self.actions = np.zeros(4)
        self.ball, self.yaw = self.easiest(p[:, :2], self.active)
        self.box = 0 if self.is_red[self.ball] else 1
        y, z = np.array([math.cos(self.yaw), math.sin(self.yaw), 0.0]), np.array([0.0, 0.0, -1.0])
        self.R_des = np.column_stack([np.cross(y, z), y, z])
        if self.student:
            self.camera_reset()
        return True

    # ---------- the camera, for the student (as rl/sorting/sort_env.py _camera) ----------
    def camera_reset(self):
        cam = self.meta["camera"]
        p, _ = self.balls()
        self.cam_bias = self.rng.uniform(-1, 1, 3) * cam["bias_m"]
        self.cam_noise = self.rng.uniform(*cam["noise_m"])
        self.read_pos = p + self.cam_bias + self.cam_noise * self.rng.standard_normal(p.shape)
        self.read_age = np.zeros(BALLS)
        self.pend_due, self.cam_step = -1, int(self.rng.integers(0, cam["period_steps"]))
        self.h = np.zeros((1, 1, 128), np.float32)

    def camera_step(self):
        cam, dt = self.meta["camera"], self.meta["policy_dt"]
        self.read_age += dt
        if self.pend_due == 0:
            self.read_pos = np.where(self.pend_ok[:, None], self.pend_pos, self.read_pos)
            self.read_age = np.where(self.pend_ok, self.pend_delay * dt, self.read_age)
        if self.pend_due >= 0:
            self.pend_due -= 1
        self.cam_step += 1
        if self.cam_step % cam["period_steps"] == 0:
            p, _ = self.balls()
            tcp, _ = self.tcp_pose()
            under = (np.linalg.norm(p[:, :2] - tcp[:2], axis=1) < cam["hide_xy_m"]) & (tcp[2] > p[:, 2])
            lost = self.rng.random(BALLS) < cam["dropout"]
            self.pend_pos = p + self.cam_bias + self.cam_noise * self.rng.standard_normal(p.shape)
            self.pend_ok = ~under & ~lost
            self.pend_delay = int(self.rng.integers(cam["delay_steps"][0], cam["delay_steps"][1] + 1))
            self.pend_due = self.pend_delay

    def student_obs(self):
        mt, d = self.meta, self.d
        self.camera_step()
        tcp, _ = self.tcp_pose()
        rp = self.read_pos
        ball, age = rp[self.ball], self.read_age[self.ball]
        box = np.array([*self.box_xy[self.box], mt["box_rim_z"] + 0.045])
        rel = rp - ball
        dist = np.linalg.norm(rel[:, :2], axis=-1)
        others = self.active & self.on_tray(rp[:, :2])
        others[self.ball] = False
        dist = np.where(others, dist, 9.0)
        near = np.argsort(dist, kind="stable")[:2]
        mask = dist[near] < 1.0
        nrel = rel[near] * mask[:, None]
        tray3 = np.array([*self.tray_c, mt["tray_floor_z"]])
        o = np.concatenate([d.qpos[self.qadr] - np.array(mt["start_q"]), 0.1 * d.qvel[self.dadr], tcp - tray3,
                            ball - tcp, box - tcp, [float(self.close_cmd), d.qpos[self.jaw_adr] / mt["jaw_open"]],
                            [min(max(age, 0.0), 2.0), float(age < 0.6)], nrel.ravel(), mask.astype(float),
                            [math.sin(self.yaw), math.cos(self.yaw)], self.actions])
        return np.clip(np.nan_to_num(o), -10, 10).astype(np.float32)

    # ---------- the policy's view ----------
    def obs(self):
        mt, d = self.meta, self.d
        tcp, R = self.tcp_pose()
        p, v = self.balls()
        ball, bvel = p[self.ball], v[self.ball]
        box = np.array([*self.box_xy[self.box], mt["box_rim_z"] + 0.045])
        rel = p - ball
        dist = np.linalg.norm(rel[:, :2], axis=-1)
        others = self.active & self.on_tray(p[:, :2])
        others[self.ball] = False
        dist = np.where(others, dist, 9.0)
        near = np.argsort(dist, kind="stable")[:2]
        mask = dist[near] < 1.0
        nrel = rel[near] * mask[:, None]
        q = d.qpos[self.qadr]
        qd = d.qvel[self.dadr]
        tray3 = np.array([*self.tray_c, mt["tray_floor_z"]])
        o = np.concatenate([q - np.array(mt["start_q"]), 0.1 * qd, tcp - tray3, ball - tcp, box - ball,
                            [float(self.close_cmd), d.qpos[self.jaw_adr] / mt["jaw_open"]], bvel,
                            nrel.ravel(), mask.astype(float), [math.sin(self.yaw), math.cos(self.yaw)],
                            self.actions])
        return np.clip(np.nan_to_num(o), -10, 10).astype(np.float32)

    # ---------- one policy step ----------
    def step(self):
        mt, m, d = self.meta, self.m, self.d
        if self.student:
            o = self.student_obs()
            out = self.pol.run(None, {self.inp: o[None], "h_in": self.h})
            a, self.h = np.clip(out[0][0], -1, 1), out[1]
        else:
            o = self.obs()
            a = np.clip(self.oracle(o) if self.use_oracle else self.pol.run(None, {self.inp: o[None]})[0][0], -1, 1)
        self.actions = a
        tcp, _ = self.tcp_pose()
        target = np.clip(tcp + a[:3] * mt["step_m"], mt["workspace_lo"], mt["workspace_hi"])
        idle = abs(self.jaw_cmd - self.jaw_goal) < 1e-9
        want = a[3] > 0
        if idle and want != self.close_cmd:
            self.close_cmd = want
        self.jaw_goal = 0.0 if self.close_cmd else mt["jaw_open"]
        w = mt["carry_tilt_weight"] if self.held else mt["tilt_weight"]
        jstep = mt["jaw_open"] / mt["jaw_stroke_s"] * m.opt.timestep
        for _ in range(self.sub):
            tcp, R = self.tcp_pose()
            jp, jr = np.zeros((3, m.nv)), np.zeros((3, m.nv))
            mujoco.mj_jacSite(m, d, jp, jr, self.tcp)
            J = np.vstack([jp[:, self.dadr], w * jr[:, self.dadr]])
            er = 0.5 * sum(np.cross(R[:, k], self.R_des[:, k]) for k in range(3))
            e = np.concatenate([target - tcp, w * er])
            dq = J.T @ np.linalg.solve(J @ J.T + mt["ik_damping"] ** 2 * np.eye(6), e)
            dq = np.clip(dq, -0.02, 0.02)
            q = d.qpos[self.qadr]
            self.arm_goal = np.clip(self.arm_goal + self.ik_gain * dq, q - 0.1, q + 0.1)
            d.ctrl[:6] = self.arm_goal
            self.jaw_cmd += np.clip(self.jaw_goal - self.jaw_cmd, -jstep, jstep)
            d.ctrl[self.grip] = self.jaw_cmd
            mujoco.mj_step(m, d)
            if self.video and d.time >= len(self.frames) / 30.0:
                self.renderer.update_scene(d, camera=self.cam)
                self.frames.append(self.renderer.render())
        return self.judge()

    def oracle(self, o):
        """The scripted controller of rl/sorting/check.py on the same observations (checks this MuJoCo side)."""
        step = self.meta["step_m"]
        to_ball, to_box, shut = o[15:18], o[18:21], o[21] > 0.5
        go = lambda v: np.clip(v / step, -1, 1)
        a = np.array([0, 0, 0, -1.0])
        above = to_ball + [0, 0, 0.09]
        if self.phase == 0:
            a[:3] = go(above)
            self.phase = 1 if np.linalg.norm(above) < 0.008 else 0
        elif self.phase == 1:
            a[:3] = go(to_ball)
            # the finger tips stand 25 mm below the grasp point: on the tray floor it stops a few mm over the centre
            self.phase = 2 if np.linalg.norm(to_ball[:2]) < 0.006 and to_ball[2] > -0.012 else 1
        elif self.phase == 2:
            a[3] = 1.0
            self.phase = 3 if shut else 2
        elif self.phase == 3:
            a[2], a[3] = 1.0, 1.0
            self.phase = 4 if to_box[2] < 0.01 else 3
        elif self.phase == 4:
            a[:3], a[3] = go(to_box), 1.0
            self.phase = 5 if np.linalg.norm(to_box[:2]) < 0.01 else 4
        return a

    def judge(self):
        """'success', 'drop' or None, as in the Isaac Lab task (sort_env.py)."""
        mt = self.meta
        tcp, R = self.tcp_pose()
        p, v = self.balls()
        ball = p[self.ball]
        local = R.T @ (ball - tcp)
        between = abs(local[0]) < 0.02 and abs(local[1]) < 0.03 and abs(local[2]) < 0.035
        self.held = between and self.close_cmd
        in_target = self.in_box(ball[:2], self.box)
        in_other = self.in_box(ball[:2], 1 - self.box)
        if in_target and ball[2] < mt["box_rim_z"] and not self.held and np.linalg.norm(v[self.ball]) < 0.2:
            return "success"
        low = ball[2] < mt["tray_floor_z"] + 0.06
        if (not self.held and low and ((not self.on_tray(ball[:2]) and not in_target) or in_other)) or \
                ball[2] < mt["table_z"] - 0.05:
            return "drop"
        return None

    def episode(self, max_steps=150):
        self.phase = 0
        for k in range(max_steps):
            r = self.step()
            if r:
                return r, k + 1
        return "timeout", max_steps


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("onnx")
    ap.add_argument("--episodes", type=int, default=100)
    ap.add_argument("--layouts", default="spread", help="spread | all (scattered, row, heap, pairs, spread)")
    ap.add_argument("--max-balls", type=int, default=1)
    ap.add_argument("--sort-all", action="store_true", help="six balls, episodes until the tray is empty (a demo)")
    ap.add_argument("--video", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--oracle", action="store_true", help="the scripted controller instead of the policy")
    a = ap.parse_args()
    pl = Player(a.onnx, a.seed, a.video)
    pl.use_oracle = a.oracle
    kinds = ("scattered", "row", "heap", "pairs", "spread") if a.layouts == "all" else (a.layouts,)
    results, t0 = [], time.time()
    if a.sort_all:
        pl.reset("spread", 6)
        while len(results) < 12:
            res, steps = pl.episode()
            results.append(res)
            print(f"ball {len(results)}: {res} in {steps * pl.meta['policy_dt']:.1f} s", flush=True)
            if not pl.next_ball():
                break
    else:
        per_kind = {}
        for e in range(a.episodes):
            kind = kinds[e % len(kinds)]
            nb = int(pl.rng.integers(1, a.max_balls + 1))
            pl.reset(kind, nb)
            res, steps = pl.episode()
            results.append(res)
            per_kind.setdefault(kind, []).append(res)
            per_kind.setdefault(f"{int(pl.active.sum())} balls", []).append(res)
        for k in sorted(per_kind):
            r = per_kind[k]
            print(f"  {k:10s} {r.count('success'):3d}/{len(r):3d} sorted, {r.count('drop')} dropped, "
                  f"{r.count('timeout')} timed out")
    n, ok = len(results), results.count("success")
    lo, hi = wilson(ok, n)
    print(f"MuJoCo: {ok} of {n} sorted = {100 * ok / max(n, 1):.0f} % (95 % interval {100 * lo:.0f}–{100 * hi:.0f} %), "
          f"dropped {results.count('drop')}, timed out {results.count('timeout')}; {time.time() - t0:.0f} s", flush=True)
    if a.video and pl.frames:
        import imageio.v2 as imageio
        out = HERE / "media" / f"mujoco_{Path(a.onnx).stem}{'_sort_all' if a.sort_all else ''}.mp4"
        out.parent.mkdir(exist_ok=True)
        imageio.mimwrite(out, pl.frames, fps=30, codec="libx264", quality=8, macro_block_size=8)
        print(f"wrote {out}")


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), min(1.0, c + h)


if __name__ == "__main__":
    sys.exit(main())
