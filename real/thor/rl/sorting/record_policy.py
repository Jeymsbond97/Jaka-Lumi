"""Record what a trained sorting policy does: loads a checkpoint (model_<iteration>.pt) and writes an mp4 from Isaac
Lab's Newton view, either one table close up (the MuJoCo overview angle) or a grid of scenes. Also counts the
episodes it sorts. Used for the learning-progress clips (the same layout at several iterations).

    cd ~/isaaclab-spike && . ./env.sh && IsaacLab/.venv/bin/python ~/Dev/lumi-wave/rl/sorting/record_policy.py \
        --checkpoint logs/rsl_rl/lumi_sort/<run>/model_300.pt --stage 2 --shot close --seconds 20 --viz newton

Clips go to rl/sorting/media/ (not in git): <run>_it<iteration>_<shot>_stage<stage>_0000.mp4
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("--checkpoint", required=True)
parser.add_argument("--stage", type=int, default=2)
parser.add_argument("--shot", choices=("close", "grid"), default="close")
parser.add_argument("--seconds", type=float, default=20.0)
parser.add_argument("--seed", type=int, default=7, help="the same seed gives the same ball layouts at every iteration")
parser.add_argument("--out", default="media")
parser.add_argument("--evaluate", type=int, default=0,
                    help="no clip: run this many episodes on --num_envs scenes and print the success with its 95 %% interval")
parser.add_argument("--num_envs", type=int, default=256)
parser.add_argument("--task", default="Lumi-Sort-v0", help="Lumi-Sort-Distill-v0 for a student checkpoint")
parser.add_argument("--cam-bias", type=float, default=None, help="student: the camera's fixed error per axis (m)")
parser.add_argument("--cam-noise", type=float, default=None, help="student: the camera's noise per reading (m)")
add_launcher_args(parser)
args, _ = parser.parse_known_args()

import torch

from isaaclab.envs.utils.video_recorder_cfg import VideoRecorderCfg
from isaaclab.utils.seed import configure_seed
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, create_rsl_rl_runner, handle_deprecated_rsl_rl_cfg
from isaaclab_rl.rsl_rl.utils import check_rsl_rl_version
from isaaclab_visualizers.newton import NewtonGLVisualizerCfg

from rl.sorting.agents.rsl_rl_distillation_cfg import SortDistillationRunnerCfg
from rl.sorting.agents.rsl_rl_ppo_cfg import SortPPORunnerCfg
from rl.sorting.sort_env import SortEnv
from rl.sorting.sort_env_cfg import SortDistillEnvCfg, SortEnvCfg


def main():
    ckpt = Path(args.checkpoint).resolve()
    it = re.search(r"model_(\d+)\.pt", ckpt.name).group(1)
    student = args.task == "Lumi-Sort-Distill-v0"
    cfg = SortDistillEnvCfg() if student else SortEnvCfg()
    cfg.stage = args.stage
    if args.cam_bias is not None:
        cfg.cam_bias_m = args.cam_bias
    if args.cam_noise is not None:
        cfg.cam_noise_m = (args.cam_noise, args.cam_noise)
    cfg.stage_up = 2.0                                   # the stage stays as asked while recording
    cfg.seed = args.seed
    if args.evaluate:
        cfg.scene.num_envs = args.num_envs
    elif args.shot == "close":
        cfg.scene.num_envs = 1                           # the one scene sits at the origin
        eye, look = (0.38, 0.98, -0.02), (0.02, 0.45, -0.20)
    else:
        cfg.scene.num_envs = 16
        eye, look = (4.6, 6.2, 1.9), (0.2, 1.4, -0.5)
    if not args.evaluate:
        cfg.sim.visualizer_cfgs = [NewtonGLVisualizerCfg(headless=True, eye=eye, lookat=look, window_width=1280,
                                                         window_height=720, max_visible_envs=cfg.scene.num_envs,
                                                         visible_env_indices=list(range(cfg.scene.num_envs)),
                                                         randomly_sample_visible_envs=False)]
    fps = round(1 / (cfg.sim.dt * cfg.decimation))
    steps = int(args.seconds * fps)
    if not args.evaluate:
        cfg.video_recorders = [VideoRecorderCfg(
            source="visualizer:newton", output_dir=str(Path(__file__).resolve().parent / args.out),
            output_filename_prefix=f"{ckpt.parent.name}_it{it}_{args.shot}_stage{args.stage}", video_length=steps,
            fps=fps)]
    configure_seed(args.seed)
    with launch_simulation(cfg, args):
        env = SortEnv(cfg)
        agent = handle_deprecated_rsl_rl_cfg(SortDistillationRunnerCfg() if student else SortPPORunnerCfg(),
                                             check_rsl_rl_version())
        agent.device = env.device
        wenv = RslRlVecEnvWrapper(env, clip_actions=agent.clip_actions)
        runner = create_rsl_rl_runner(wenv, agent)
        runner.load(str(ckpt))
        policy = runner.get_inference_policy(device=env.device)
        obs = wenv.get_observations()
        ended = ok = dropped = 0
        n = 0
        # the same number of episodes from every scene, so quick endings (success or drop) are not over-counted
        per_env = -(-args.evaluate // env.num_envs) if args.evaluate else 10 ** 9
        counted = torch.zeros(env.num_envs, dtype=torch.long, device=env.device)
        while (n < steps + 5) if not args.evaluate else bool((counted < per_env).any()):
            with torch.inference_mode():
                obs, _, dones, _ = wenv.step(policy(obs))
                policy.reset(dones)
            take = dones.bool() & (counted < per_env)
            counted += take.long()
            ended += int(take.sum())
            ok += int((take & env.success_now).sum())
            dropped += int((take & env.dropped_now).sum())
            n += 1
        if args.evaluate:
            import math
            p, z = ok / ended, 1.96
            c = (p + z * z / (2 * ended)) / (1 + z * z / ended)
            h = z * math.sqrt(p * (1 - p) / ended + z * z / (4 * ended * ended)) / (1 + z * z / ended)
            print(f"evaluated iteration {it}, stage {args.stage}: {ok} of {ended} sorted = {100 * p:.1f} % "
                  f"(95 % interval {100 * (c - h):.1f}-{100 * (c + h):.1f} %), dropped {dropped}", flush=True)
        else:
            print(f"recorded iteration {it}, stage {args.stage}, {args.shot}: {ok} of {ended} episodes sorted",
                  flush=True)
        env.close()


if __name__ == "__main__":
    main()
