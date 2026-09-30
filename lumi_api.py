"""
LumiSim: the JAKA Lumi in MuJoCo, behind the same kind of interface the real robot has.

The real Lumi is driven through three channels (see "Lumi SDK" in the JAKA_Lumi repo):
  - body (lift, waist, head): HTTP POST /api/extaxis/moveto {"pos": [mm, deg, deg, deg]}
  - arm: JAKA SDK (jkrc), joint moves and Cartesian moves
  - AGV base: TCP string commands

The methods here keep the same units (mm and degrees for the body, degrees for arm joints),
so code written against LumiSim (including LLM tool calls) can later run on a LumiReal class
that has the same methods and talks to the hardware instead.

Robot frame (used by every Cartesian method): origin on the floor under the wheel axle,
x = forward, y = left, z = up, in meters.
"""
from pathlib import Path

import mujoco
import mujoco.viewer
import numpy as np

SCENE = Path(__file__).parent / "scene.xml"

WHEEL_RADIUS = 0.084        # m (from wheel_l.STL)
WHEEL_TRACK = 0.3586        # m, distance between the two wheels (from the URDF)
AXLE_HEIGHT = 0.0840        # m, wheel axle above the floor

ARM_JOINTS = ["l_a1", "l_a2", "l_a3", "l_a4", "l_a5", "l_a6"]
ARM_ACTUATORS = ["a1", "a2", "a3", "a4", "a5", "a6"]
BODY_ACTUATORS = ["lift", "waist", "head_yaw", "head_pitch"]

GRIPPER_OPEN = 0
GRIPPER_CLOSED = 255

# Arm poses in degrees (found with solve_ik, then rounded)
ARM_HOME = [3, 43, 128, -60, 94, -54]          # gripper in front of the chest, pointing forward and down
ARM_WAVE = [136, -123, 99, -134, 73, -47]      # gripper raised to head height, pointing up

BODY_SPEED = [100.0, 60.0, 90.0, 60.0]   # mm/s, deg/s, deg/s, deg/s at vel=100
ARM_SPEED = 90.0                          # deg/s at vel=100


class LumiSim:
    def __init__(self, scene=SCENE, viewer=False):
        """viewer=True opens the interactive window (on macOS run the script with mjpython)."""
        self.model = mujoco.MjModel.from_xml_path(str(scene))
        self.data = mujoco.MjData(self.model)
        self._ik_data = mujoco.MjData(self.model)
        self._renderers = {}

        self._arm_qpos = [self.model.joint(j).qposadr[0] for j in ARM_JOINTS]
        self._arm_dof = [self.model.joint(j).dofadr[0] for j in ARM_JOINTS]
        self._arm_range = np.array([self.model.joint(j).range for j in ARM_JOINTS])
        self._pinch = self.model.site("g_pinch").id
        # IK works on the waist plus the six arm joints
        self._ik_qpos = [self.model.joint("l_2").qposadr[0]] + self._arm_qpos
        self._ik_dof = [self.model.joint("l_2").dofadr[0]] + self._arm_dof
        self._ik_range = np.vstack([self.model.joint("l_2").range, self._arm_range])
        # every body from the waist up (arm and gripper included), for the IK collision check
        waist = self.model.body("link_2").id
        self._upper_bodies = [b for b in range(self.model.nbody) if self._has_ancestor(b, waist)]
        base = self.model.body("base_link").id
        self._loose_bodies = [self.model.jnt_bodyid[j] for j in range(self.model.njnt)
                              if self.model.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE
                              and self.model.jnt_bodyid[j] != base]

        self.data.ctrl[[self.model.actuator(a).id for a in ARM_ACTUATORS]] = np.deg2rad(ARM_HOME)
        self.data.qpos[self._arm_qpos] = np.deg2rad(ARM_HOME)
        mujoco.mj_forward(self.model, self.data)

        self.viewer = None
        if viewer:
            self.viewer = mujoco.viewer.launch_passive(self.model, self.data)
        self.step(0.5)

    def _has_ancestor(self, body, ancestor):
        while body != 0:
            if body == ancestor:
                return True
            body = self.model.body_parentid[body]
        return False

    # ------------------------------------------------------------------ simulation

    def step(self, seconds):
        """Advance the simulation. Every blocking move below is built on this."""
        for i in range(int(round(seconds / self.model.opt.timestep))):
            mujoco.mj_step(self.model, self.data)
            if self.viewer is not None and i % 8 == 0:
                self.viewer.sync()

    def _ramp(self, actuators, target, speed, settle=0.4):
        """Move the actuator setpoints to `target` at a constant `speed` (units per second),
        then wait for the joints to settle. This is what makes a move look like a real robot's."""
        ids = [self.model.actuator(a).id for a in actuators]
        start = self.data.ctrl[ids].copy()
        target = np.asarray(target, dtype=float)
        duration = max(np.max(np.abs(target - start) / speed), 0.05)
        steps = max(int(duration / 0.02), 1)
        for i in range(1, steps + 1):
            self.data.ctrl[ids] = start + (target - start) * i / steps
            self.step(0.02)
        self.step(settle)

    # ------------------------------------------------------------------ body: lift, waist, head

    def body_moveto(self, pos, vel=100):
        """Same arguments as the real /api/extaxis/moveto.
        pos = [lift mm (0..300), waist deg (-140..140), head yaw deg (-180..180), head pitch deg (-5..35)].
        Positive head pitch looks down. Out-of-range targets raise, as the real robot reports an error."""
        target = np.array([pos[0] / 1000.0, *np.deg2rad(pos[1:4])])
        for name, value in zip(BODY_ACTUATORS, target):
            low, high = self.model.actuator(name).ctrlrange
            if not low - 1e-3 <= value <= high + 1e-3:
                raise ValueError(f"{name} target out of range: {pos}")
        speed = np.array([BODY_SPEED[0] / 1000.0, *np.deg2rad(BODY_SPEED[1:])]) * np.clip(vel, 0.1, 100) / 100
        self._ramp(BODY_ACTUATORS, target, speed)

    def body_status(self):
        """[lift mm, waist deg, head yaw deg, head pitch deg], like the 'pos' fields of /status."""
        q = [self.data.joint(j).qpos[0] for j in ("l_1", "l_2", "l_3", "l_4")]
        return [q[0] * 1000.0, *np.rad2deg(q[1:])]

    # ------------------------------------------------------------------ arm

    def arm_joint_move(self, joints_deg, vel=100):
        """Move the six arm joints to the given angles (degrees). Blocking."""
        target = np.deg2rad(joints_deg)
        if np.any(target < self._arm_range[:, 0]) or np.any(target > self._arm_range[:, 1]):
            raise ValueError(f"arm joint target out of range: {joints_deg}")
        self._ramp(ARM_ACTUATORS, target, np.deg2rad(ARM_SPEED) * np.clip(vel, 1, 100) / 100)

    def arm_joints(self):
        """Current arm joint angles in degrees."""
        return np.rad2deg(self.data.qpos[self._arm_qpos])

    def tcp_position(self):
        """Point between the gripper fingers, in the robot frame (m)."""
        return self.world_to_robot(self.data.site_xpos[self._pinch])

    def solve_ik(self, xyz, approach=(0, 0, -1), use_waist=True, restarts=40):
        """Waist angle and arm joint angles (degrees) that put the fingertip point at `xyz` (robot frame, m)
        with the gripper pointing along `approach` (robot frame; default straight down). Rotation around
        the approach axis is left free. The arm is short and mounted on the robot's right side, so most
        points in front are only reachable after turning the waist; use_waist=False keeps the waist still.

        Damped least squares on a scratch copy of the state (the simulation is not disturbed), started
        from the current pose and then from random poses. Solutions where the robot would be in collision
        are rejected. Raises ValueError if nothing is found."""
        target = self.robot_to_world(xyz)
        axis = self._base_rotation() @ (np.asarray(approach, dtype=float) / np.linalg.norm(approach))
        qpos = self._ik_qpos if use_waist else self._ik_qpos[1:]
        dof = self._ik_dof if use_waist else self._ik_dof[1:]
        limits = self._ik_range if use_waist else self._ik_range[1:]
        d = self._ik_data
        jacp = np.zeros((3, self.model.nv))
        jacr = np.zeros((3, self.model.nv))
        rng = np.random.default_rng(0)
        for attempt in range(restarts):
            d.qpos[:] = self.data.qpos
            if attempt > 0:
                d.qpos[qpos] = rng.uniform(np.maximum(limits[:, 0], -np.pi), np.minimum(limits[:, 1], np.pi))
            for _ in range(200):
                mujoco.mj_kinematics(self.model, d)
                mujoco.mj_comPos(self.model, d)
                pos_error = target - d.site_xpos[self._pinch]
                current_axis = d.site_xmat[self._pinch].reshape(3, 3)[:, 2]
                rot_error = np.cross(current_axis, axis)
                if np.dot(current_axis, axis) < 0:                 # pointing the wrong way: keep turning
                    rot_error /= np.linalg.norm(rot_error) + 1e-9
                elif np.linalg.norm(pos_error) < 1e-3 and np.linalg.norm(rot_error) < 1e-2:
                    break
                mujoco.mj_jacSite(self.model, d, jacp, jacr, self._pinch)
                jac = np.vstack([jacp[:, dof], jacr[:, dof]])
                error = np.concatenate([pos_error, rot_error])
                dq = jac.T @ np.linalg.solve(jac @ jac.T + 1e-3 * np.eye(6), error)
                d.qpos[qpos] = np.clip(d.qpos[qpos] + np.clip(dq, -0.2, 0.2), limits[:, 0], limits[:, 1])
            else:
                continue                                           # did not converge from this start
            # a1, a4, a6 can turn +-360: take the turn nearest to where the joint is now
            for adr in (self._arm_qpos[0], self._arm_qpos[3], self._arm_qpos[5]):
                d.qpos[adr] = self.data.qpos[adr] + (d.qpos[adr] - self.data.qpos[adr] + np.pi) % (2 * np.pi) - np.pi
            if not self._in_collision(d):
                return np.rad2deg(d.qpos[self._ik_qpos[0]]), np.rad2deg(d.qpos[self._arm_qpos])
        raise ValueError(f"no IK solution for {np.round(xyz, 3)} (out of reach?)")

    def _in_collision(self, d):
        """True if, in state `d`, any robot part above the base touches the robot or the fixed world.
        Loose objects are ignored: touching them is the point of a grasp."""
        mujoco.mj_fwdPosition(self.model, d)
        for contact in d.contact[:d.ncon]:
            bodies = self.model.geom_bodyid[[contact.geom1, contact.geom2]]
            if np.any(np.isin(bodies, self._loose_bodies)):
                continue
            if contact.dist < -0.002 and np.any(np.isin(bodies, self._upper_bodies)):
                return True
        return False

    def arm_move_to(self, xyz, approach=(0, 0, -1), use_waist=True, vel=100):
        """Put the fingertip point at `xyz` (robot frame, m), gripper pointing along `approach`.
        If the waist has to turn, the head turns back by the same angle so it keeps looking the same way."""
        waist, joints = self.solve_ik(xyz, approach, use_waist)
        if use_waist:
            # start from the commanded targets, not the measured pose (which can sit a hair past a limit)
            ctrl = [self.data.actuator(a).ctrl[0] for a in BODY_ACTUATORS]
            lift, old_waist, head_yaw, head_pitch = [ctrl[0] * 1000.0, *np.rad2deg(ctrl[1:])]
            head_yaw = np.clip(head_yaw - (waist - old_waist), -180, 180)
            self.body_moveto([lift, waist, head_yaw, head_pitch], vel)
        self.arm_joint_move(joints, vel)

    # ------------------------------------------------------------------ gripper

    def gripper(self, closed):
        """closed=True closes the Robotiq 2F-85, False opens it."""
        self.data.actuator("g_fingers_actuator").ctrl = GRIPPER_CLOSED if closed else GRIPPER_OPEN
        self.step(0.8)

    def arm_move_line(self, xyz, approach=(0, 0, -1), vel=40):
        """Like arm_move_to, but the fingertip travels in a straight line (2 cm steps, waist kept still).
        Use it for the last stretch down to an object and back up."""
        start = self.tcp_position()
        xyz = np.asarray(xyz, dtype=float)
        steps = max(int(np.ceil(np.linalg.norm(xyz - start) / 0.02)), 1)
        speed = np.deg2rad(ARM_SPEED) * np.clip(vel, 1, 100) / 100
        for i in range(1, steps + 1):
            _, joints = self.solve_ik(start + (xyz - start) * i / steps, approach, use_waist=False, restarts=1)
            self._ramp(ARM_ACTUATORS, np.deg2rad(joints), speed, settle=0)
        self.step(0.4)

    def pick(self, xyz, clearance=0.10):
        """Grasp from above: open, go above `xyz` (robot frame, m), descend, close, lift back up."""
        above = np.asarray(xyz, dtype=float) + [0, 0, clearance]
        self.gripper(closed=False)
        self.arm_move_to(above)
        self.arm_move_line(xyz)
        self.gripper(closed=True)
        self.arm_move_line(above)

    def place(self, xyz, clearance=0.10):
        """Put the held object down at `xyz` (robot frame, m) and retreat upward."""
        above = np.asarray(xyz, dtype=float) + [0, 0, clearance]
        self.arm_move_to(above)
        self.arm_move_line(xyz)
        self.gripper(closed=False)
        self.arm_move_line(above)

    # ------------------------------------------------------------------ AGV base

    def drive(self, linear, angular, seconds):
        """Drive for `seconds` at `linear` m/s forward and `angular` rad/s (positive = turn left), then stop."""
        left = (linear - angular * WHEEL_TRACK / 2) / WHEEL_RADIUS
        right = (linear + angular * WHEEL_TRACK / 2) / WHEEL_RADIUS
        self.data.actuator("wheel_l").ctrl = left
        self.data.actuator("wheel_r").ctrl = right
        self.step(seconds)
        self.data.actuator("wheel_l").ctrl = 0
        self.data.actuator("wheel_r").ctrl = 0
        self.step(0.5)

    def base_pose(self):
        """(x, y, heading in degrees) of the robot in the world."""
        origin = self.robot_to_world([0, 0, 0])
        forward = self._base_rotation()[:, 0]
        return origin[0], origin[1], np.rad2deg(np.arctan2(forward[1], forward[0]))

    # ------------------------------------------------------------------ cameras

    def get_image(self, camera="head_cam", width=640, height=480, depth=False):
        """RGB image (H, W, 3 uint8) from 'head_cam' or 'torso_cam'. depth=True returns meters (H, W) instead."""
        key = (width, height)
        if key not in self._renderers:
            self._renderers[key] = mujoco.Renderer(self.model, height, width)
        renderer = self._renderers[key]
        if depth:
            renderer.enable_depth_rendering()
        renderer.update_scene(self.data, camera)
        image = renderer.render().copy()
        if depth:
            renderer.disable_depth_rendering()
        return image

    # ------------------------------------------------------------------ gestures and the world

    def wave(self, times=3):
        """Raise the arm and wave hello, then return to the home pose."""
        self.arm_joint_move(ARM_WAVE)
        left, right = list(ARM_WAVE), list(ARM_WAVE)
        left[4] += 25                                  # a5 (wrist) swings the hand sideways
        right[4] -= 25
        for _ in range(times):
            self.arm_joint_move(left)
            self.arm_joint_move(right)
        self.arm_joint_move(ARM_HOME)

    def set_person(self, x, y):
        """Simulation only: put the mannequin at world (x, y). Far away (the default 4, 3) = nobody there."""
        self.data.mocap_pos[self.model.body("person").mocapid[0]] = [x, y, 0]
        self.step(0.02)

    def object_position(self, name):
        """Simulation only (ground truth for checking results): an object's position in the robot frame."""
        return self.world_to_robot(self.data.body(name).xpos)

    # ------------------------------------------------------------------ frames

    def _base_rotation(self):
        """Columns = robot frame axes (forward, left, up) in world coordinates.
        In base_link the front is -y and the left side is +x."""
        base = self.data.body("base_link").xmat.reshape(3, 3)
        return base @ np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]], dtype=float)

    def _base_origin(self):
        axle = self.data.site("base_center").xpos
        return np.array([axle[0], axle[1], axle[2] - AXLE_HEIGHT])

    def robot_to_world(self, xyz):
        return self._base_origin() + self._base_rotation() @ np.asarray(xyz, dtype=float)

    def world_to_robot(self, xyz):
        return self._base_rotation().T @ (np.asarray(xyz, dtype=float) - self._base_origin())
