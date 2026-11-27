"""Checks the sorting environment before any training: a hand-written "oracle" drives it through the observations
(above the ball, down, shut, up, over the box, open) and the episodes are counted. If the oracle cannot sort, the
scene, the IK, the gripper or the success test is wrong, not the learning.

Run on the Thor:  cd ~/isaaclab-spike && . ./env.sh && IsaacLab/.venv/bin/python ~/Dev/lumi-wave/rl/sorting/check.py \
                  --num_envs 16 --stage 3 --viz viser       (open http://<thor>:8080 to watch; --viz none: no view)
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from isaaclab.app import add_launcher_args, launch_simulation

parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
parser.add_argument("--num_envs", type=int, default=16)
parser.add_argument("--stage", type=int, default=3)
parser.add_argument("--record", type=float, default=0.0, help="write an mp4 of this many seconds (Newton view)")
parser.add_argument("--shot", choices=("close", "grid"), default="close",
                    help="close: one table from the MuJoCo overview angle; grid: all the environments")
parser.add_argument("--out", default="media", help="folder for the mp4 (relative to rl/sorting/)")
parser.add_argument("--trace", action="store_true", help="print environment 0 every few steps")
parser.add_argument("--episodes", type=int, default=64, help="stop after this many finished episodes (0: run on)")
add_launcher_args(parser)
args, _ = parser.parse_known_args()

import torch

from rl.sorting.sort_env import SortEnv
from rl.sorting.sort_env_cfg import SortEnvCfg


STEP = 0.012


def oracle(obs, phase):
    """Scripted actions from the teacher's observations; `phase` (N,) moves 0 above, 1 down, 2 shut, 3 up, 4 over the
    box, 5 open."""
    o = obs["policy"]
    to_ball, ball_to_box, shut = o[:, 15:18], o[:, 18:21], o[:, 21] > 0.5
    a = torch.zeros(o.shape[0], 4, device=o.device)
    a[:, 3] = -1.0
    above = to_ball + torch.tensor([0.0, 0.0, 0.09], device=o.device)
    go = lambda v: (v / STEP).clamp(-1, 1)
    p0, p1, p2, p3, p4, p5 = (phase == k for k in range(6))
    a[p0, :3] = go(above[p0])
    phase[p0 & (above.norm(dim=-1) < 0.008)] = 1
    a[p1, :3] = go(to_ball[p1])
    # the finger tips stand 25 mm below the grasp point: on the tray floor it stops a few mm over the ball's centre
    phase[p1 & (to_ball[:, :2].norm(dim=-1) < 0.006) & (to_ball[:, 2] > -0.012)] = 2
    a[p2, 3] = 1.0
    phase[p2 & shut] = 3
    a[p3, 3] = 1.0
    a[p3, 2] = 1.0                                   # straight up to the carrying height over the box rim
    phase[p3 & (ball_to_box[:, 2] < 0.01)] = 4
    a[p4, :3] = go(ball_to_box[p4])
    a[p4, 3] = 1.0
    phase[p4 & (ball_to_box[:, :2].norm(dim=-1) < 0.01)] = 5
    a[p5, 3] = -1.0
    return a


def main():
    cfg = SortEnvCfg()
    cfg.scene.num_envs = args.num_envs
    cfg.stage = args.stage
    if args.record:
        from isaaclab.envs.utils.video_recorder_cfg import VideoRecorderCfg
        from isaaclab_visualizers.newton import NewtonGLVisualizerCfg
        if args.shot == "close":                     # env 0 sits at the origin when there is one env
            eye, look = (0.38, 0.98, -0.02), (0.02, 0.45, -0.20)
        else:
            eye, look = (5.5, 7.5, 2.6), (0.0, 0.5, -0.4)
        cfg.sim.visualizer_cfgs = [NewtonGLVisualizerCfg(headless=True, eye=eye, lookat=look, window_width=1280,
                                                         window_height=720)]
        global STEP
        cfg.decimation, cfg.step_m = 10, cfg.step_m / 2      # 20 frames a second for a smooth clip, same speeds
        STEP = cfg.step_m
        cfg.sim.render_interval = cfg.decimation
        fps = round(1 / (cfg.sim.dt * cfg.decimation))
        cfg.video_recorders = [VideoRecorderCfg(source="visualizer:newton",
                                                output_dir=str(Path(__file__).resolve().parent / args.out),
                                                output_filename_prefix=f"isaac_{args.shot}_stage{args.stage}",
                                                video_length=int(args.record * fps), fps=fps)]
    with launch_simulation(cfg, args):
        env = SortEnv(cfg)
        obs, _ = env.reset()
        phase = torch.zeros(env.num_envs, dtype=torch.long, device=env.device)
        done_n, ok_n, drop_n, steps = 0, 0, 0, 0
        while env.sim.is_running():
            with torch.inference_mode():
                obs, rew, term, trunc, _ = env.step(oracle(obs, phase))
            ended = term | trunc
            ok_n += int((ended & env.success_now).sum())
            drop_n += int((ended & env.dropped_now).sum())
            done_n += int(ended.sum())
            phase[ended] = 0
            steps += 1
            if args.trace and steps % 3 == 0:
                tcp, R, g = env._poses()
                p, v = env._ball_state()
                ball, _ = env._target_ball(p, v)
                between, held = env._held(ball, R, g)
                jaw = env.robot.data.joint_pos.torch[0, env.jaw_ids]
                print(f"  {steps:4d} phase {int(phase[0])} tcp {[round(float(x), 3) for x in tcp[0]]} "
                      f"target {[round(float(x), 3) for x in env.target[0]]} ball {[round(float(x), 3) for x in ball[0]]} "
                      f"jaw {[round(float(x), 4) for x in jaw]} between {bool(between[0])} held {bool(held[0])} "
                      f"fingers_z {float(R[0, 2, 2]):.2f}", flush=True)
            if steps % 50 == 0:
                print(f"step {steps}: episodes {done_n}, sorted {ok_n}, dropped {drop_n}, "
                      f"reward {float(rew.mean()):.2f}", flush=True)
            if args.episodes and done_n >= args.episodes:
                break
            if args.record and steps >= int(args.record / (cfg.sim.dt * cfg.decimation)) + 5:
                break
        print(f"oracle: {ok_n} of {done_n} episodes sorted ({100 * ok_n / max(done_n, 1):.0f} %), {drop_n} dropped",
              flush=True)
        env.close()


if __name__ == "__main__":
    main()
