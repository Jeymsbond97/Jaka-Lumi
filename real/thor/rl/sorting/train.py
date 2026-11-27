"""Train the sorting policy with PPO (rsl_rl) in Isaac Lab, on the Thor's GPU.

    cd ~/isaaclab-spike && . ./env.sh && IsaacLab/.venv/bin/python ~/Dev/lumi-wave/rl/sorting/train.py \
        --num_envs 1024 --viz viser          # nine of the scenes in the browser at http://<thor>:8080
    IsaacLab/.venv/bin/tensorboard --logdir logs/rsl_rl/lumi_sort --host 0.0.0.0 --port 6006   # the curves

Every other flag is Isaac Lab's own (`--max_iterations`, `--seed`, `--resume`, `--video` ...). Runs are written to
logs/rsl_rl/lumi_sort/<date_time>/ under the folder it is started from (checkpoints model_<iteration>.pt, the
TensorBoard events, the configs used).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import rl.sorting  # noqa: E402,F401  registers Lumi-Sort-v0

from isaaclab_rl.entrypoints import run_train_cli  # noqa: E402

if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--task" not in argv:
        argv = ["--task", "Lumi-Sort-v0", *argv]
    if "--rl_library" not in argv:
        argv = ["--rl_library", "rsl_rl", *argv]
    sys.exit(run_train_cli(argv))
