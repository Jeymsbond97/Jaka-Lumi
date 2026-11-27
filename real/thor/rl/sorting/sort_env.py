"""The sorting task in Isaac Lab (docs/sorting/04): one episode takes one ball, the easiest on the tray, and drops it
into the box of its colour.

The policy moves the grasp point (between the finger pads) by up to `step_m` per step and opens or closes the Zimmer.
The hand's turn is chosen by code at the episode's start, where the fingers have room beside the ball (the same rule
as manipulation/sort.py); the fingers are kept as straight down as the arm allows by the IK. This is the teacher
version: it sees the simulator's true ball positions and speed.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import torch

from isaaclab.envs import DirectRLEnv
from isaaclab.utils.math import matrix_from_quat

from . import layouts
from .sort_env_cfg import (ARM_JOINTS, BALL_MASS, BALL_R, FLOOR_Z, JAW_JOINTS, JAW_OPEN, MAX_BALLS, START_Q, TCP_IN_GRIPPER,
                           SortEnvCfg)

FINGER_OUT = 0.0305 + 0.0075 / 2      # the open fingers' middles this far either side of the grasp point (sort.py)
FINGER_R = 0.0085
CLEAR = 0.003
ONTO = 0.012
YAW0 = math.radians(59.0)             # the jaws' direction at START_Q, seen from above
# the jaws are symmetric, so six turns 30° apart cover every direction; each is taken on the side nearer the start
# (149° and -31° grip the same: -31° twists the wrist less)
YAWS = torch.tensor([YAW0 + math.radians(30 * k) for k in (0, 1, -1, 2, -2, -3)])


class SortEnv(DirectRLEnv):
    cfg: SortEnvCfg

    def __init__(self, cfg: SortEnvCfg, render_mode: str | None = None, **kwargs):
        super().__init__(cfg, render_mode, **kwargs)
        self.robot = self.scene["robot"]
        self.balls = [self.scene[f"ball_{i}"] for i in range(MAX_BALLS)]
        self.arm_ids = self.robot.find_joints(ARM_JOINTS, preserve_order=True)[0]
        self.jaw_ids = self.robot.find_joints(JAW_JOINTS, preserve_order=True)[0]
        self.grip_body = self.robot.find_bodies("gripper")[0][0]
        self.jac_idx = self.grip_body - 1 if self.robot.is_fixed_base else self.grip_body
        self.jac_cols = [j + self.robot.num_base_dofs for j in self.arm_ids]
        n, d = self.num_envs, self.device
        self.tcp_off = torch.tensor(TCP_IN_GRIPPER, device=d)
        self.start_q = torch.tensor(START_Q, device=d)
        self.lo = torch.tensor(cfg.workspace_lo, device=d)
        self.hi = torch.tensor(cfg.workspace_hi, device=d)
        self.tray_c = torch.tensor(cfg.tray_centre, device=d)
        self.tray_h = torch.tensor(cfg.tray_inner_half, device=d)
        self.box_xy = torch.tensor([cfg.boxes["red"], cfg.boxes["yellow"]], device=d)    # (2, 2)
        self.box_h = torch.tensor(cfg.box_inner_half, device=d)
        self.yaws = YAWS.to(d)
        self.is_red = (torch.arange(MAX_BALLS, device=d) % 2 == 0)

        self.target = torch.zeros(n, 3, device=d)            # where the policy wants the grasp point
        self.R_des = torch.eye(3, device=d).repeat(n, 1, 1)  # the hand's wanted orientation this episode
        self.yaw = torch.zeros(n, device=d)
        self.jaw_goal = torch.full((n,), JAW_OPEN, device=d)  # the Zimmer's stroke goal: open or shut
        self.jaw_cmd = torch.full((n,), JAW_OPEN, device=d)   # where the stroke is now
        self.close_cmd = torch.zeros(n, dtype=torch.bool, device=d)
        self.actions = torch.zeros(n, 4, device=d)
        self.prev_actions = torch.zeros(n, 4, device=d)
        self.active = torch.zeros(n, MAX_BALLS, dtype=torch.bool, device=d)
        self.ball_id = torch.zeros(n, dtype=torch.long, device=d)       # the episode's ball
        self.box_id = torch.zeros(n, dtype=torch.long, device=d)        # 0 red, 1 yellow
        self.start_z = torch.zeros(n, device=d)
        self.off_tray = torch.zeros(n, MAX_BALLS, dtype=torch.bool, device=d)
        self.stage = cfg.stage
        self.success_rate = 0.0
        self.success_now = torch.zeros(n, dtype=torch.bool, device=d)
        self.dropped_now = torch.zeros(n, dtype=torch.bool, device=d)
        self.close_empty_now = torch.zeros(n, dtype=torch.bool, device=d)
        self.reward_now = torch.zeros(n, device=d)
        self.held_flag = torch.zeros(n, dtype=torch.bool, device=d)
        self.arm_goal = self.start_q.repeat(n, 1)
        self.inertia0 = [b.data.body_inertia.torch.clone() for b in self.balls]   # (N, 1, 9) each
        self.bad_now = torch.zeros(n, dtype=torch.bool, device=d)
        # the camera model for the student: the last reading of each ball and how old it is
        self.read_pos = torch.zeros(n, MAX_BALLS, 3, device=d)
        self.read_age = torch.zeros(n, MAX_BALLS, device=d)
        self.pend_pos = torch.zeros(n, MAX_BALLS, 3, device=d)
        self.pend_ok = torch.zeros(n, MAX_BALLS, dtype=torch.bool, device=d)
        self.pend_due = torch.full((n,), -1, dtype=torch.long, device=d)
        self.cam_phase = torch.zeros(n, dtype=torch.long, device=d)
        self.cam_bias = torch.zeros(n, 1, 3, device=d)
        self.cam_noise = torch.zeros(n, 1, 1, device=d)
        self.finished = 0                                               # episodes ended, for the success rate
        self.sums = {k: torch.zeros(n, device=d) for k in
                     ("progress", "success", "drop", "close_empty", "action_rate", "joint_speed", "other_off_tray")}
        self.steps_in = {k: torch.zeros(n, device=d) for k in ("held", "lifted", "above_box")}
        self.phi_prev = torch.zeros(n, device=d)
        self.fresh = torch.ones(n, dtype=torch.bool, device=d)     # first step of an episode: no shaping yet

    # ---------- state ----------
    def _poses(self):
        """Grasp point (N, 3), gripper rotation (N, 3, 3), gripper origin (N, 3), env-local."""
        pose = self.robot.data.body_pose_w.torch[:, self.grip_body]
        R = matrix_from_quat(pose[:, 3:7])
        g = pose[:, :3] - self.scene.env_origins
        return g + (R @ self.tcp_off), R, g

    def _ball_state(self):
        """All balls: positions (N, B, 3) env-local, speeds (N, B, 3)."""
        p = torch.stack([b.data.root_pos_w.torch for b in self.balls], 1) - self.scene.env_origins[:, None]
        v = torch.stack([b.data.root_lin_vel_w.torch for b in self.balls], 1)
        return p, v

    def _target_ball(self, p, v):
        i = torch.arange(self.num_envs, device=self.device)
        return p[i, self.ball_id], v[i, self.ball_id]

    def _held(self, ball, R, g):
        """The episode's ball between the pads (in the gripper frame) with the Zimmer shut on it."""
        local = (R.transpose(1, 2) @ (ball - g)[..., None])[..., 0]
        between = ((local[:, 0] - self.tcp_off[0]).abs() < 0.02) & (local[:, 1].abs() < 0.03) & \
                  ((local[:, 2] - self.tcp_off[2]).abs() < 0.035)
        return between, between & self.close_cmd

    def _on_tray(self, xy):
        return ((xy - self.tray_c).abs() <= self.tray_h + 0.01).all(-1)

    def _in_box(self, xy, box):
        return ((xy - self.box_xy[box]).abs() <= self.box_h).all(-1)

    # ---------- acting ----------
    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        self.prev_actions[:] = self.actions
        self.actions = actions.clamp(-1.0, 1.0)
        tcp, _, _ = self._poses()               # the step is taken from where the grasp point is, as on the robot
        self.target = torch.max(torch.min(tcp + self.actions[:, :3] * self.cfg.step_m, self.hi), self.lo)
        # the Zimmer takes a new command only when the last stroke has ended
        idle = (self.jaw_cmd - self.jaw_goal).abs() < 1e-6
        want_close = self.actions[:, 3] > 0.0
        start = idle & (want_close != self.close_cmd)
        self.close_empty_now = start & want_close
        self.close_cmd = torch.where(start, want_close, self.close_cmd)
        self.jaw_goal = torch.where(self.close_cmd, torch.zeros_like(self.jaw_goal), torch.full_like(self.jaw_goal, JAW_OPEN))

    def _ik(self):
        """One damped least squares step: the grasp point to its target first, the hand's orientation as far as the
        arm allows (weighted by tilt_weight)."""
        tcp, R, _ = self._poses()
        J = self.robot.data.body_link_jacobian_w.torch[:, self.jac_idx][:, :, self.jac_cols]   # (N, 6, 6)
        r = R @ self.tcp_off
        skew = torch.zeros(self.num_envs, 3, 3, device=self.device)
        skew[:, 0, 1], skew[:, 0, 2], skew[:, 1, 2] = -r[:, 2], r[:, 1], -r[:, 0]
        skew = skew - skew.transpose(1, 2)
        Jp = J[:, :3] - skew @ J[:, 3:]
        # fingers down at the ball; with the ball in the hand the hand may turn any way (the drop over a box)
        w = torch.where(self.held_flag, self.cfg.carry_tilt_weight, self.cfg.tilt_weight)[:, None]
        e_p = self.target - tcp
        e_r = 0.5 * sum(torch.cross(R[:, :, k], self.R_des[:, :, k], dim=-1) for k in range(3))
        Jw = torch.cat([Jp, w[..., None] * J[:, 3:]], 1)
        e = torch.cat([e_p, w * e_r], 1)
        A = Jw @ Jw.transpose(1, 2) + (self.cfg.ik_damping ** 2) * torch.eye(6, device=self.device)
        dq = (Jw.transpose(1, 2) @ torch.linalg.solve(A, e[..., None]))[..., 0]
        dq = dq.clamp(-0.02, 0.02)              # per physics step (200 Hz): at most ~4 rad/s
        # added to the joint goal, not to the measured joints: the arm's sag under its own weight is taken up, as the
        # real controller's gravity compensation does; the goal stays near the arm (no wind-up)
        q = self.robot.data.joint_pos.torch[:, self.arm_ids]
        self.arm_goal = torch.max(torch.min(self.arm_goal + self.cfg.ik_gain * dq, q + 0.1), q - 0.1)

    def _apply_action(self) -> None:
        self._ik()                              # every physics step, towards the policy's target
        step = self.cfg.jaw_speed * self.physics_dt
        self.jaw_cmd = self.jaw_cmd + (self.jaw_goal - self.jaw_cmd).clamp(-step, step)
        self.robot.set_joint_position_target_index(target=self.arm_goal, joint_ids=self.arm_ids)
        self.robot.set_joint_position_target_index(target=self.jaw_cmd[:, None].repeat(1, 2), joint_ids=self.jaw_ids)

    # ---------- the camera, for the student ----------
    def _camera(self, p, tcp):
        """One policy step of the camera model: a frame every cam_period_steps, its ball positions (true + this
        episode's bias + noise) delivered cam_delay_steps later; no reading of a ball under the hand or in it, and
        some readings lost. Between readings the last one is held and ages."""
        c, n, d = self.cfg, self.num_envs, self.device
        self.read_age += self.step_dt
        due = self.pend_due == 0
        if due.any():
            upd = due[:, None] & self.pend_ok
            self.read_pos = torch.where(upd[..., None], self.pend_pos, self.read_pos)
            delay = torch.full_like(self.read_age, 0.0)
            self.read_age = torch.where(upd, (self.pend_age_at_delivery[:, None] + delay), self.read_age)
        self.pend_due = torch.where(self.pend_due >= 0, self.pend_due - 1, self.pend_due)
        frame = (self.episode_length_buf + self.cam_phase) % c.cam_period_steps == 0
        if frame.any():
            meas = p + self.cam_bias + self.cam_noise * torch.randn_like(p)
            under = (torch.linalg.norm(p[..., :2] - tcp[:, None, :2], dim=-1) < c.cam_hide_xy_m) &                     (tcp[:, None, 2] > p[..., 2])
            lost = torch.rand(n, MAX_BALLS, device=d) < c.cam_dropout
            ok = ~under & ~lost
            lo, hi = c.cam_delay_steps
            delay = torch.randint(lo, hi + 1, (n,), device=d)
            self.pend_pos = torch.where(frame[:, None, None], meas, self.pend_pos)
            self.pend_ok = torch.where(frame[:, None], ok, self.pend_ok)
            self.pend_due = torch.where(frame, delay, self.pend_due)
            self.pend_age_at_delivery = torch.where(frame, delay.float() * self.step_dt,
                                                    getattr(self, "pend_age_at_delivery", torch.zeros(n, device=d)))

    def _camera_reset(self, env_ids, p):
        """The camera saw the tray before the episode began: a reading of every ball, fresh."""
        c, m, d = self.cfg, len(env_ids), self.device
        self.cam_bias[env_ids] = (torch.rand(m, 1, 3, device=d) * 2 - 1) * c.cam_bias_m
        lo, hi = c.cam_noise_m
        self.cam_noise[env_ids] = lo + (hi - lo) * torch.rand(m, 1, 1, device=d)
        self.read_pos[env_ids] = p + self.cam_bias[env_ids] + self.cam_noise[env_ids] * torch.randn_like(p)
        self.read_age[env_ids] = 0.0
        self.pend_due[env_ids] = -1
        self.cam_phase[env_ids] = torch.randint(0, c.cam_period_steps, (m,), device=d)

    def _student_obs(self, tcp, box, q, qd, jaw):
        i = torch.arange(self.num_envs, device=self.device)
        rp = self.read_pos
        ball = rp[i, self.ball_id]
        age = self.read_age[i, self.ball_id]
        rel = rp - ball[:, None]
        dist = torch.linalg.norm(rel[..., :2], dim=-1)
        others = self.active & self._on_tray(rp[..., :2])
        others[i, self.ball_id] = False
        dist = torch.where(others, dist, torch.full_like(dist, 9.0))
        near = dist.argsort(-1)[:, :2]
        nrel = torch.gather(rel, 1, near[..., None].expand(-1, -1, 3))
        nmask = torch.gather(dist, 1, near) < 1.0
        nrel = nrel * nmask[..., None]
        tray3 = torch.cat([self.tray_c, torch.tensor([self.cfg.tray_floor_z], device=self.device)])
        obs = torch.cat([
            q - self.start_q, 0.1 * qd,                       # 12
            tcp - tray3,                                      # 3
            ball - tcp,                                       # 3 the ball as last read
            box - tcp,                                        # 3 the box is known exactly
            self.close_cmd.float()[:, None], (jaw / JAW_OPEN)[:, None],   # 2
            age.clamp(0.0, 2.0)[:, None], (age < 0.6).float()[:, None],   # 2 how old the reading is
            nrel.reshape(self.num_envs, 6), nmask.float(),    # 8
            torch.sin(self.yaw)[:, None], torch.cos(self.yaw)[:, None],   # 2
            self.actions,                                     # 4
        ], -1)
        return torch.nan_to_num(obs).clamp(-10.0, 10.0)

    # ---------- what the policy sees ----------
    def _get_observations(self) -> dict:
        tcp, R, g = self._poses()
        p, v = self._ball_state()
        ball, bvel = self._target_ball(p, v)
        box = torch.cat([self.box_xy[self.box_id], torch.full((self.num_envs, 1), self.cfg.box_rim_z + 0.045,
                                                                 device=self.device)], -1)
        # the two nearest other balls on the tray, relative to the episode's ball
        rel = p - ball[:, None]
        dist = torch.linalg.norm(rel[..., :2], dim=-1)
        others = self.active & self._on_tray(p[..., :2])
        others[torch.arange(self.num_envs, device=self.device), self.ball_id] = False
        dist = torch.where(others, dist, torch.full_like(dist, 9.0))
        near = dist.argsort(-1)[:, :2]
        nrel = torch.gather(rel, 1, near[..., None].expand(-1, -1, 3))
        nmask = torch.gather(dist, 1, near) < 1.0
        nrel = nrel * nmask[..., None]
        q = self.robot.data.joint_pos.torch[:, self.arm_ids]
        qd = self.robot.data.joint_vel.torch[:, self.arm_ids]
        jaw = self.robot.data.joint_pos.torch[:, self.jaw_ids[0]]
        tray3 = torch.cat([self.tray_c, torch.tensor([self.cfg.tray_floor_z], device=self.device)])
        obs = torch.cat([
            q - self.start_q, 0.1 * qd,                       # 12
            tcp - tray3,                                      # 3
            ball - tcp,                                       # 3
            box - ball,                                       # 3
            self.close_cmd.float()[:, None], (jaw / JAW_OPEN)[:, None],   # 2
            bvel,                                             # 3 (teacher only)
            nrel.reshape(self.num_envs, 6), nmask.float(),    # 8
            torch.sin(self.yaw)[:, None], torch.cos(self.yaw)[:, None],   # 2
            self.actions,                                     # 4
        ], -1)
        out = {"policy": torch.nan_to_num(obs).clamp(-10.0, 10.0)}
        if self.cfg.student_obs:
            self._camera(p, tcp)
            out["student"] = self._student_obs(tcp, box, q, qd, jaw)
        return out

    # ---------- reward and end (Isaac Lab asks for the end first, then the reward, after the same physics) ----------
    def _evaluate(self):
        c = self.cfg
        tcp, R, g = self._poses()
        p, v = self._ball_state()
        ball, bvel = self._target_ball(p, v)
        between, held = self._held(ball, R, g)
        lifted = held & (ball[:, 2] > self.start_z + 0.03)
        box_d = torch.linalg.norm(ball[:, :2] - self.box_xy[self.box_id], dim=-1)
        in_target = self._in_box(ball[:, :2], self.box_id)
        in_other = self._in_box(ball[:, :2], 1 - self.box_id)
        above_box = held & in_target & (ball[:, 2] > c.box_rim_z)
        settled = bvel.norm(dim=-1) < 0.2
        if self.stage == 1:
            success = lifted
        else:
            success = in_target & (ball[:, 2] < c.box_rim_z) & ~held & settled
        low = ball[:, 2] < c.tray_floor_z + 0.06
        dropped = ~held & low & ((~self._on_tray(ball[:, :2]) & ~in_target) | in_other)
        dropped |= ball[:, 2] < c.table_z - 0.05
        # other balls pushed off the tray (each counted once)
        now_off = self.active & ~self._on_tray(p[..., :2])
        now_off[torch.arange(self.num_envs, device=self.device), self.ball_id] = False
        new_off = (now_off & ~self.off_tray).sum(-1).float()
        self.off_tray |= now_off

        # progress potential: how far along the task the state is (reach, hold, lift, carry, over the box). The
        # shaping reward is its change, gamma * phi(now) - phi(before) (Ng et al. 1999): only progress pays, staying
        # anywhere pays nothing, so holding or hovering can never beat finishing (runs 1 and 2 learned to hold)
        lift_frac = held.float() * ((ball[:, 2] - self.start_z) / 0.03).clamp(0.0, 1.0)
        reach_phi = 0.5 * (1 - torch.tanh(torch.linalg.norm(tcp - ball, dim=-1) / 0.1))
        hold_phi = 1.0 + lift_frac + 2.0 * lift_frac * (1 - torch.tanh(box_d / 0.15)) + above_box.float()
        # a ball let go over its box keeps the top value while it falls in: letting go there is not a loss
        phi = torch.where(held, hold_phi, torch.where(in_target,
                                                      torch.full_like(hold_phi, 4.5), reach_phi))
        shaping = torch.where(self.fresh, torch.zeros_like(phi), c.gamma * phi - self.phi_prev)
        self.phi_prev = phi
        self.fresh[:] = False
        terms = {
            "progress": c.rew_progress * shaping,
            "success": c.rew_success * success.float(),
            "drop": c.rew_drop * dropped.float(),
            "close_empty": c.rew_close_empty * (self.close_empty_now & ~between).float(),
            "action_rate": c.rew_action_rate * (self.actions - self.prev_actions).square().sum(-1),
            "joint_speed": c.rew_joint_speed * self.robot.data.joint_vel.torch[:, self.arm_ids].square().sum(-1),
            "other_off_tray": c.rew_other_off_tray * new_off,
        }
        # what the hand did this episode, in steps (not rewards): for the curves
        for k, v in (("held", held), ("lifted", lifted), ("above_box", above_box)):
            self.steps_in[k] += v.float()
        self.success_now, self.dropped_now, self.held_flag = success, dropped, held
        total = torch.zeros(self.num_envs, device=self.device)
        for k, t in terms.items():
            self.sums[k] += t
            total += t
        # a scene whose physics gave non-numbers is ended and restarted, with no reward, not the whole run
        q_all = self.robot.data.joint_pos.torch
        self.bad_now = ~(torch.isfinite(total) & torch.isfinite(p).all(-1).all(-1) & torch.isfinite(q_all).all(-1)
                         & torch.isfinite(tcp).all(-1))
        self.reward_now = torch.where(self.bad_now, torch.zeros_like(total), total)
        self.success_now &= ~self.bad_now
        self.dropped_now &= ~self.bad_now

    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        self._evaluate()
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        return self.success_now | self.dropped_now | self.bad_now, time_out

    def _get_rewards(self) -> torch.Tensor:
        return self.reward_now

    # ---------- reset ----------
    def _reset_idx(self, env_ids: Sequence[int] | None):
        if env_ids is None:
            env_ids = self.robot._ALL_INDICES
        env_ids = torch.as_tensor(env_ids, device=self.device)
        if self.common_step_counter > 0:
            done = self.success_now[env_ids].float()
            rate = float(done.mean()) if len(env_ids) else 0.0
            self.success_rate = 0.97 * self.success_rate + 0.03 * rate
            log = self.extras.setdefault("log", {})
            log["Metrics/success_rate"] = self.success_rate
            log["Metrics/dropped"] = float(self.dropped_now[env_ids].float().mean())
            log["Metrics/physics_restarts"] = float(self.bad_now[env_ids].float().sum())
            log["Curriculum/stage"] = float(self.stage)
            for k, s in self.sums.items():
                log[f"Episode_Reward/{k}"] = float(s[env_ids].mean())
            for k, s in self.steps_in.items():
                log[f"Episode_Steps/{k}"] = float(s[env_ids].mean())
            if self.success_rate > self.cfg.stage_up and self.stage < 4:
                self.stage += 1
                self.success_rate = 0.0
        for s in list(self.sums.values()) + list(self.steps_in.values()):
            s[env_ids] = 0.0
        self.fresh[env_ids] = True
        super()._reset_idx(env_ids)
        m, d = len(env_ids), self.device

        # the arm above the tray, open
        q = self.robot.data.default_joint_pos.torch[env_ids].clone()
        q[:, self.arm_ids] = self.start_q + (torch.rand(m, 6, device=d) - 0.5) * 0.04
        q[:, self.jaw_ids] = JAW_OPEN
        self.robot.write_joint_position_to_sim_index(position=q, env_ids=env_ids)
        self.robot.write_joint_velocity_to_sim_index(velocity=torch.zeros_like(q), env_ids=env_ids)
        self.robot.set_joint_position_target_index(target=q[:, self.arm_ids], joint_ids=self.arm_ids, env_ids=env_ids)
        self.arm_goal[env_ids] = q[:, self.arm_ids]
        self.jaw_goal[env_ids] = JAW_OPEN
        self.jaw_cmd[env_ids] = JAW_OPEN
        self.close_cmd[env_ids] = False
        self.held_flag[env_ids] = False
        self.actions[env_ids] = 0.0
        self.prev_actions[env_ids] = 0.0
        self.target[env_ids] = torch.tensor([0.03, 0.47, -0.1427], device=d) + (torch.rand(m, 3, device=d) - 0.5) * 0.04

        # the balls: how many and how they lie depends on the stage
        one = torch.ones(m, dtype=torch.long, device=d)
        if self.stage <= 2:                     # one ball: near the tray's centre (stage 1) or anywhere on it (stage 2)
            kind = torch.full((m,), layouts.SPREAD, device=d)
            n = one
            half = (0.03 + BALL_R + 0.002,) * 2 if self.stage == 1 else tuple(self.cfg.tray_inner_half)
        else:                                   # 1 to 6 balls in every layout
            kind = torch.randint(0, 5, (m,), device=d)
            n = torch.randint(1, MAX_BALLS + 1, (m,), device=d)
            half = tuple(self.cfg.tray_inner_half)
        xy, act = layouts.make(kind, n, self.cfg.tray_centre, half, BALL_R, MAX_BALLS, d)
        # which of the six balls (three red, three yellow) lie there: a random choice each episode
        perm = torch.rand(m, MAX_BALLS, device=d).argsort(-1)
        xy_b = torch.zeros_like(xy)
        act_b = torch.zeros_like(act)
        xy_b.scatter_(1, perm[..., None].expand(-1, -1, 2), xy)
        act_b.scatter_(1, perm, act)
        rest = self.cfg.tray_floor_z + BALL_R + 0.0005
        z = torch.full((m, MAX_BALLS), rest, device=d)
        z += torch.where((kind == layouts.SCATTERED)[:, None], 0.05 + 0.10 * torch.rand(m, MAX_BALLS, device=d),
                         torch.zeros_like(z))
        for i, b in enumerate(self.balls):
            pos = torch.stack([xy_b[:, i, 0], xy_b[:, i, 1], z[:, i]], -1)
            parked = torch.tensor([-0.6 + 0.06 * i, -0.5, FLOOR_Z + BALL_R], device=d).expand(m, 3)
            pos = torch.where(act_b[:, i, None], pos, parked)
            pose = torch.cat([pos + self.scene.env_origins[env_ids], torch.tensor([0.0, 0.0, 0.0, 1.0], device=d).expand(m, 4)], -1)
            b.write_root_pose_to_sim_index(root_pose=pose, env_ids=env_ids)
            b.write_root_velocity_to_sim_index(root_velocity=torch.zeros(m, 6, device=d), env_ids=env_ids)
        if self.stage >= 4:                     # full randomisation: the balls' masses too, inertia scaled with them
            lo, hi = self.cfg.ball_mass_range
            for b, inertia in zip(self.balls, self.inertia0):
                k = lo + (hi - lo) * torch.rand(m, 1, device=d)
                b.set_masses_index(masses=BALL_MASS * k, env_ids=env_ids)
                b.set_inertias_index(inertias=inertia[env_ids] * k[..., None], env_ids=env_ids)
        self.active[env_ids] = act_b
        if self.cfg.student_obs:
            start = torch.stack([torch.stack([xy_b[:, i, 0], xy_b[:, i, 1], z[:, i]], -1) for i in range(MAX_BALLS)], 1)
            self._camera_reset(env_ids, start)
        self.off_tray[env_ids] = False

        # the episode's ball: the easiest, as manipulation/sort.py picks it; the hand turned where there is room
        ball_id, yaw = self._easiest(xy_b, act_b)
        self.ball_id[env_ids] = ball_id
        self.yaw[env_ids] = yaw
        self.box_id[env_ids] = (~self.is_red[ball_id]).long()
        self.start_z[env_ids] = rest
        cy, sy = torch.cos(yaw), torch.sin(yaw)
        y_ax = torch.stack([cy, sy, torch.zeros_like(cy)], -1)
        z_ax = torch.tensor([0.0, 0.0, -1.0], device=d).expand(m, 3)
        x_ax = torch.cross(y_ax, z_ax, dim=-1)
        self.R_des[env_ids] = torch.stack([x_ax, y_ax, z_ax], -1)

    def _easiest(self, xy, act):
        """(ball index, hand turn) per env: free balls nearest the arm first, else the most room; a turn that puts a
        finger onto another ball is never taken (manipulation/sort.py room/clearance)."""
        m, B = act.shape
        yaws = self.yaws
        u = FINGER_OUT * torch.stack([torch.cos(yaws), torch.sin(yaws)], -1)      # (Y, 2)
        fingers = xy[:, :, None, None] + torch.stack([u, -u], 0)[None, None]       # (m, B, 2 fingers, Y, 2)
        d = torch.linalg.norm(fingers[:, :, None] - xy[:, None, :, None, None], dim=-1)   # (m, B, B, 2, Y)
        other = act[:, None, :] & ~torch.eye(B, dtype=torch.bool, device=self.device)[None]
        d = torch.where(other[..., None, None], d, torch.full_like(d, 9.0))
        onto = (d < ONTO).any(2).any(2)                                            # (m, B, Y)
        clear = (d - BALL_R - FINGER_R).amin(2).amin(2)                            # (m, B, Y)
        clear = torch.where(onto, torch.full_like(clear, -9.0), clear)
        room, best = clear.max(-1)                                                 # (m, B)
        dist = torch.linalg.norm(xy, dim=-1)
        score = torch.where(room >= CLEAR, 10.0 - dist, room)
        score = torch.where(act & (room > -9.0), score, torch.full_like(score, -99.0))
        ball = score.argmax(-1)
        i = torch.arange(m, device=self.device)
        return ball, yaws[best[i, ball]]
