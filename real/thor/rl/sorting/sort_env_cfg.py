"""Isaac Lab configuration of the sorting task (docs/sorting/02-04): Lumi's arm, the Zimmer with the straight
fingers, the 75 cm table, the tray, the red and yellow boxes and up to MAX_BALLS foam balls, all read from the MuJoCo
scene so both simulators are the same. Physics: Newton with the MuJoCo-Warp solver, on the GPU.

Frame: the arm controller's base frame (m, z up, y forward) is each environment's origin.
"""
from __future__ import annotations

from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg, NewtonCollisionPipelineCfg

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets import ArticulationCfg, AssetBaseCfg, RigidObjectCfg
from isaaclab.envs import DirectRLEnvCfg
from isaaclab.envs import mdp
from isaaclab.managers import EventTermCfg, SceneEntityCfg
from isaaclab.scene import InteractiveScene, InteractiveSceneCfg
from isaaclab.sim import RigidBodyMaterialCfg, SimulationCfg
from isaaclab.utils import configclass
from isaaclab.visualizers import VisualizerCfg

from . import scene_from_mjcf as mj

MAX_BALLS = 6                     # the owner's balls: 3 red and 3 yellow; an episode puts 1 to 6 of them on the tray
ARM_JOINTS = ["j1", "j2", "j3", "j4", "j5", "j6"]
JAW_JOINTS = ["jaw_l", "jaw_r"]
# the hand above the tray's centre, fingers as straight down as the arm allows there (sim/sorting/scripted_demo.py)
START_Q = [-1.2348, 2.0271, -0.9701, -4.6218, -1.79, 2.3861]
JAW_OPEN = 0.013                  # m per jaw: pads 61 mm apart (docs/sorting/01)
TCP_IN_GRIPPER = (0.1305, 0.0, 0.155)   # the grasp point between the pad centres, in the gripper body frame (build.py)

FLOOR_Z = -1.008
BALLS = mj.balls()
BALL_R = BALLS[0][2]
BALL_MASS = BALLS[0][3]
RED = (0.86, 0.12, 0.12)
YELLOW = (0.97, 0.80, 0.10)


def _static_parts():
    """The table, its legs, the tray and the two boxes as fixed cuboids, from the MuJoCo scene."""
    parts = {}
    for name, centre, half, rgba, collides in mj.static_boxes():
        parts[name] = AssetBaseCfg(
            prim_path="{ENV_REGEX_NS}/" + name,
            spawn=sim_utils.CuboidCfg(
                size=tuple(2 * h for h in half),
                collision_props=sim_utils.UsdPhysicsCollisionCfg() if collides else None,
                physics_material=RigidBodyMaterialCfg(static_friction=0.8, dynamic_friction=0.7),
                visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=tuple(rgba[:3])),
            ),
            init_state=AssetBaseCfg.InitialStateCfg(pos=tuple(centre)),
        )
    return parts


def _ball(i):
    """Ball i: red for even i, yellow for odd i (3 of each, as the real balls); the box it goes to follows its colour."""
    return RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/" + f"ball_{i}",
        spawn=sim_utils.SphereCfg(
            radius=BALL_R,
            rigid_props=sim_utils.UsdPhysicsRigidBodyCfg(),
            mass_props=sim_utils.MassCfg(mass=BALL_MASS),
            collision_props=sim_utils.UsdPhysicsCollisionCfg(),
            physics_material=RigidBodyMaterialCfg(static_friction=1.0, dynamic_friction=0.9, restitution=0.2),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=RED if i % 2 == 0 else YELLOW),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(-0.6 + 0.06 * i, -0.5, FLOOR_Z + BALL_R)),   # off the tray: waiting
    )


ROBOT_CFG = ArticulationCfg(
    prim_path="{ENV_REGEX_NS}/Robot",
    spawn=sim_utils.UsdFileCfg(usd_path=str(mj.robot_usd())),     # made from the MuJoCo scene (scene_from_mjcf.py)
    init_state=ArticulationCfg.InitialStateCfg(
        joint_pos={**dict(zip(ARM_JOINTS, START_Q)), "jaw_l": JAW_OPEN, "jaw_r": JAW_OPEN},
    ),
    actuators={
        # the controller holds its joint targets stiffly (MuJoCo scene: kp 1500 / 400 with critical damping)
        "arm_big": ImplicitActuatorCfg(joint_names_expr=["j[1-3]"], stiffness=1500.0, damping=80.0, effort_limit_sim=60.0),
        "arm_small": ImplicitActuatorCfg(joint_names_expr=["j[4-6]"], stiffness=400.0, damping=20.0, effort_limit_sim=20.0),
        # the Zimmer squeezes ~90 N at switch level 1; capped at 20 N here so the contacts on the 8 g ball stay stable
        # (docs/sorting/03 §2: a held ball must still survive a shake)
        "jaws": ImplicitActuatorCfg(joint_names_expr=["jaw_.*"], stiffness=2000.0, damping=40.0, effort_limit_sim=20.0),
    },
)


class SortSceneCfg(InteractiveSceneCfg):          # made a configclass below, once the parts are added
    class_type: type = InteractiveScene      # named here: this config lives outside Isaac Lab's packages
    robot: ArticulationCfg = ROBOT_CFG
    floor = AssetBaseCfg(prim_path="/World/floor", spawn=sim_utils.GroundPlaneCfg(),
                         init_state=AssetBaseCfg.InitialStateCfg(pos=(0.0, 0.0, FLOOR_Z)))
    light = AssetBaseCfg(prim_path="/World/light", spawn=sim_utils.DomeLightCfg(intensity=2500.0))


for _name, _cfg in _static_parts().items():
    setattr(SortSceneCfg, _name, _cfg)
    SortSceneCfg.__annotations__[_name] = AssetBaseCfg
for _i in range(MAX_BALLS):
    setattr(SortSceneCfg, f"ball_{_i}", _ball(_i))
    SortSceneCfg.__annotations__[f"ball_{_i}"] = RigidObjectCfg
SortSceneCfg = configclass(SortSceneCfg)


class SortEventCfg:                               # made a configclass below, one term per ball
    pass


for _i in range(MAX_BALLS):
    # every reset: each ball's friction and bounce drawn anew (docs/sorting/04 §7; foam balls differ and age)
    setattr(SortEventCfg, f"ball_{_i}_material", EventTermCfg(
        func=mdp.randomize_rigid_body_material, mode="reset",
        params={"asset_cfg": SceneEntityCfg(f"ball_{_i}"), "static_friction_range": (0.6, 1.2),
                "dynamic_friction_range": (0.6, 1.2), "restitution_range": (0.1, 0.5), "num_buckets": 64}))
    SortEventCfg.__annotations__ = {**getattr(SortEventCfg, "__annotations__", {}), f"ball_{_i}_material": EventTermCfg}
SortEventCfg = configclass(SortEventCfg)


@configclass
class SortEnvCfg(DirectRLEnvCfg):
    # control: the policy runs at 10 Hz (mode A of docs/sorting/04 §3), the physics at 200 Hz
    decimation = 20
    episode_length_s = 15.0
    action_space = 4                  # dx, dy, dz of the grasp point, gripper (> 0 close, < 0 open)
    observation_space = 40
    state_space = 0

    sim: SimulationCfg = SimulationCfg(
        dt=1 / 200,
        render_interval=decimation,
        physics=NewtonCfg(
            solver_cfg=MJWarpSolverCfg(
                solver="newton", integrator="implicitfast", njmax=400, nconmax=200, impratio=10.0,
                cone="elliptic", iterations=50, ls_iterations=25, use_mujoco_contacts=False,
            ),
            collision_cfg=NewtonCollisionPipelineCfg(rigid_contact_max=2_000_000),
            num_substeps=1,
            debug_mode=False,
        ),
    )
    scene: SortSceneCfg = SortSceneCfg(num_envs=1024, env_spacing=2.5, replicate_physics=True)

    # action
    step_m = 0.012                    # the grasp point moves at most this far per policy step
    jaw_speed = JAW_OPEN / 0.5        # a full stroke takes 0.5 s and cannot be stopped half way (binary Zimmer)
    workspace_lo = (-0.42, 0.30, -0.243)   # the grasp point stays in this box (table top + 15 mm ... + 300 mm)
    workspace_hi = (0.45, 0.66, 0.042)
    tilt_weight = 0.05                # IK: how much the fingers' direction counts against the grasp point's place
    carry_tilt_weight = 0.02          # ... and with the ball in the hand (it may be dropped with the hand any way)
    ik_damping = 0.05
    ik_gain = 0.1                     # share of the IK step taken each physics step (smooth, no overshoot)

    # scene numbers (MuJoCo scene, build.py)
    tray_centre = (0.03, 0.47)
    tray_inner_half = (0.135, 0.090)
    tray_floor_z = -0.254
    boxes = {"red": (-0.25, 0.47), "yellow": (0.31, 0.47)}
    box_inner_half = (0.0885, 0.1285)
    box_rim_z = -0.1795
    table_z = -0.258

    events: SortEventCfg = SortEventCfg()

    # the student (docs/sorting/04 §8): off for the teacher's PPO training
    student_obs = False
    student_observation_space = 39
    cam_period_steps = 5              # the camera's ball positions come every 0.5 s (the skills' depth rate)
    cam_delay_steps = (1, 3)          # ... 0.1 to 0.3 s late
    cam_bias_m = 0.010                # a fixed error per episode, up to this on each axis
    cam_noise_m = (0.003, 0.005)      # and noise on every reading, its size drawn per episode
    cam_dropout = 0.05                # readings lost
    cam_hide_xy_m = 0.05              # no reading of a ball while the hand is above it within this, or holding it
    ball_mass_range = (0.8, 1.2)      # stage 4: each ball's mass times this, drawn at every reset

    # curriculum (docs/sorting/04 §6): starts at `stage`, moves on when the success rate passes `stage_up`
    stage = 1
    stage_up = 0.8

    # reward (docs/sorting/04 §4): progress shaping (the change of a progress potential, which no policy can farm by
    # staying put), the success bonus, and penalties. Runs 1 and 2 paid per step for holding and for lifting and
    # learned to hold the ball instead of finishing
    gamma = 0.99                      # the same discount as PPO's, for the shaping
    rew_progress = 10.0
    rew_success = 100.0
    rew_drop = -20.0
    rew_close_empty = -1.0
    rew_action_rate = -0.005
    rew_joint_speed = -0.0005
    rew_other_off_tray = -5.0

    def __post_init__(self):
        # the browser view shows nine of the scenes (all of them would slow the training)
        self.sim.default_visualizer_cfg = VisualizerCfg(eye=(4.2, 6.0, 1.6), lookat=(0.0, 1.0, -0.3),
                                                        max_visible_envs=9, visible_env_indices=list(range(9)),
                                                        randomly_sample_visible_envs=False)


@configclass
class SortDistillEnvCfg(SortEnvCfg):
    """The student's training: every layout and full randomisation from the start, the camera model on."""
    student_obs = True
    stage = 4
    stage_up = 2.0                    # stays at stage 4

