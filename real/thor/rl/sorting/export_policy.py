"""Export a trained sorting policy for use outside Isaac Lab: the actor (with its observation normaliser) as ONNX, and
next to it a JSON with everything needed to build its observations and use its actions the same way (control rate,
step size, IK weights, start pose, scene numbers, the observation layout). The MuJoCo check (sim/sorting/policy_play.py)
and later the robot read these two files only.

    cd ~/isaaclab-spike && . ./env.sh && IsaacLab/.venv/bin/python ~/Dev/lumi-wave/rl/sorting/export_policy.py \
        --checkpoint logs/rsl_rl/lumi_sort/<run>/model_<it>.pt --viz none

Writes rl/sorting/policies/<run>_it<it>.onnx and .json (not in git).
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--task", default="Lumi-Sort-v0", help="Lumi-Sort-Distill-v0 for a student checkpoint")
add_launcher_args(parser)
args, _ = parser.parse_known_args()

from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, create_rsl_rl_runner, handle_deprecated_rsl_rl_cfg  # noqa: E402
from isaaclab_rl.rsl_rl.utils import check_rsl_rl_version  # noqa: E402

from rl.sorting import sort_env as se  # noqa: E402
from rl.sorting import sort_env_cfg as sc  # noqa: E402
from rl.sorting.agents.rsl_rl_distillation_cfg import SortDistillationRunnerCfg  # noqa: E402
from rl.sorting.agents.rsl_rl_ppo_cfg import SortPPORunnerCfg  # noqa: E402

OBS_LAYOUT = [("q_minus_start", 6), ("0.1_qd", 6), ("tcp_minus_tray_floor_centre", 3), ("ball_minus_tcp", 3),
              ("box_drop_point_minus_ball", 3), ("gripper_closing", 1), ("jaw_over_open", 1), ("ball_velocity", 3),
              ("two_nearest_other_balls_minus_ball", 6), ("their_mask", 2), ("sin_cos_hand_turn", 2),
              ("previous_action", 4)]
STUDENT_LAYOUT = [("q_minus_start", 6), ("0.1_qd", 6), ("tcp_minus_tray_floor_centre", 3),
                  ("ball_reading_minus_tcp", 3), ("box_drop_point_minus_tcp", 3), ("gripper_closing", 1),
                  ("jaw_over_open", 1), ("reading_age_s_clipped_2", 1), ("reading_fresh_under_0.6_s", 1),
                  ("two_nearest_other_readings_minus_reading", 6), ("their_mask", 2), ("sin_cos_hand_turn", 2),
                  ("previous_action", 4)]


def main():
    ckpt = Path(args.checkpoint).resolve()
    it = re.search(r"model_(\d+)\.pt", ckpt.name).group(1)
    out = Path(__file__).resolve().parent / "policies"
    out.mkdir(exist_ok=True)
    name = f"{ckpt.parent.name}_it{it}"
    student = args.task == "Lumi-Sort-Distill-v0"
    cfg = sc.SortDistillEnvCfg() if student else sc.SortEnvCfg()
    cfg.scene.num_envs = 1
    with launch_simulation(cfg, args):
        env = se.SortEnv(cfg)
        agent = handle_deprecated_rsl_rl_cfg(SortDistillationRunnerCfg() if student else SortPPORunnerCfg(),
                                             check_rsl_rl_version())
        agent.device = env.device
        runner = create_rsl_rl_runner(RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions), agent)
        runner.load(str(ckpt))
        runner.export_policy_to_onnx(path=str(out), filename=f"{name}.onnx")
        meta = {
            "checkpoint": str(ckpt), "student": student,
            "observation_layout": STUDENT_LAYOUT if student else OBS_LAYOUT, "observation_clip": 10.0,
            "camera": {"period_steps": cfg.cam_period_steps, "delay_steps": cfg.cam_delay_steps,
                       "bias_m": cfg.cam_bias_m, "noise_m": cfg.cam_noise_m, "dropout": cfg.cam_dropout,
                       "hide_xy_m": cfg.cam_hide_xy_m},
            "action": ["dx", "dy", "dz", "gripper (> 0 close)"], "action_clip": 1.0,
            "policy_dt": cfg.sim.dt * cfg.decimation, "step_m": cfg.step_m, "jaw_open": sc.JAW_OPEN,
            "jaw_stroke_s": sc.JAW_OPEN / cfg.jaw_speed, "workspace_lo": cfg.workspace_lo,
            "workspace_hi": cfg.workspace_hi, "tilt_weight": cfg.tilt_weight,
            "carry_tilt_weight": cfg.carry_tilt_weight, "ik_damping": cfg.ik_damping,
            "ik_rate_per_s": cfg.ik_gain / cfg.sim.dt, "start_q": sc.START_Q, "tcp_in_gripper": sc.TCP_IN_GRIPPER,
            "tray_centre": cfg.tray_centre, "tray_inner_half": cfg.tray_inner_half, "tray_floor_z": cfg.tray_floor_z,
            "boxes": cfg.boxes, "box_inner_half": cfg.box_inner_half, "box_rim_z": cfg.box_rim_z,
            "table_z": cfg.table_z, "ball_r": sc.BALL_R, "yaws_deg": [float(v) * 180 / 3.141592653589793 for v in se.YAWS],
            "finger_out": se.FINGER_OUT, "finger_r": se.FINGER_R, "clear": se.CLEAR, "onto": se.ONTO,
        }
        (out / f"{name}.json").write_text(json.dumps(meta, indent=1))
        print(f"exported {out / name}.onnx and .json")
        env.close()


if __name__ == "__main__":
    main()
