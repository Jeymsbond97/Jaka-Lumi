"""The training curves of a run as files to keep and show: every scalar TensorBoard logged as one CSV, and a figure of
the ones that tell the story (success, curriculum stage, reward, and each reward and penalty term on its own).

    IsaacLab/.venv/bin/python ~/Dev/lumi-wave/rl/sorting/tb_export.py logs/rsl_rl/lumi_sort/<run> [--tag it800]

Writes rl/sorting/media/<run>_<tag>_curves.png and <run>_<tag>_scalars.csv (not in git).
"""
import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator  # noqa: E402

TERMS = ("progress", "success", "drop", "close_empty", "action_rate", "joint_speed", "other_off_tray",
         "Episode_Steps/held", "Episode_Steps/lifted", "Episode_Steps/above_box")
MAIN = (("Metrics/success_rate", "Success rate (episodes ending in the box)"),
        ("Curriculum/stage", "Curriculum stage"),
        ("Train/mean_reward", "Mean episode reward"),
        ("Train/mean_episode_length", "Mean episode length (steps of 0.1 s)"))


def load(run):
    acc = EventAccumulator(str(run), size_guidance={"scalars": 0})
    acc.Reload()
    return {t: [(e.step, e.value) for e in acc.Scalars(t)] for t in acc.Tags()["scalars"]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("run")
    p.add_argument("--tag", default="latest")
    a = p.parse_args()
    run = Path(a.run).resolve()
    out = Path(__file__).resolve().parent / "media"
    out.mkdir(exist_ok=True)
    data = load(run)
    stem = f"{run.name}_{a.tag}"
    with open(out / f"{stem}_scalars.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tag", "iteration", "value"])
        for t, rows in sorted(data.items()):
            w.writerows([t, s, v] for s, v in rows)

    def find(name):
        for t in data:
            if t == name or t.endswith(name.split("/")[-1]) and name.split("/")[0] in t:
                return data[t]
        return []

    fig, axes = plt.subplots(4, 4, figsize=(18, 13))
    axes = axes.ravel()
    for ax, (tag, title) in zip(axes, MAIN):
        rows = find(tag)
        if rows:
            ax.plot(*zip(*rows), color="#c0392b" if "success" in tag else "#2c3e50", lw=1.6)
        ax.set_title(title, fontsize=11)
        ax.grid(alpha=0.3)
    for ax, term in zip(axes[4:], TERMS):
        rows = find(term if "/" in term else f"Episode_Reward/{term}")
        if rows:
            s, v = zip(*rows)
            ax.plot(s, v, color="#27ae60" if v[-1] >= 0 else "#8e44ad", lw=1.4)
        ax.set_title(f"Steps with the ball {term.split('/')[1].replace('_', ' ')}" if "/" in term
                     else f"Reward term: {term}", fontsize=11)
        ax.grid(alpha=0.3)
    for ax in axes[4 + len(TERMS):]:
        ax.axis("off")
    for ax in axes:
        ax.set_xlabel("iteration", fontsize=9)
    last = max((r[-1][0] for t, r in data.items() if r and not t.endswith("/time")), default=0)
    fig.suptitle(f"Lumi colour sorting, PPO in Isaac Lab (Newton / MuJoCo-Warp), run {run.name}, iteration {last}",
                 fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out / f"{stem}_curves.png", dpi=110)
    print(f"wrote {stem}_curves.png and {stem}_scalars.csv ({len(data)} curves, iteration {last})")


if __name__ == "__main__":
    main()
