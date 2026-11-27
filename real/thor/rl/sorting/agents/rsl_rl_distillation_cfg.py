"""Teacher to student (docs/sorting/04 §8): the student, which sees only what the robot can measure (the camera's
late, noisy, sometimes missing ball positions), learns to act as the teacher does (DAgger-style distillation in
rsl_rl). The teacher is the PPO policy, loaded from its checkpoint (--checkpoint); the student has a memory (GRU) to
carry the ball's place through the moments the camera does not see it."""
from isaaclab.utils import configclass

from isaaclab_rl.rsl_rl import (RslRlDistillationAlgorithmCfg, RslRlDistillationRunnerCfg, RslRlMLPModelCfg,
                                RslRlRNNModelCfg)


@configclass
class SortDistillationRunnerCfg(RslRlDistillationRunnerCfg):
    num_steps_per_env = 48
    max_iterations = 1500
    save_interval = 100
    experiment_name = "lumi_sort_student"
    obs_groups = {"student": ["student"], "teacher": ["policy"]}
    student = RslRlRNNModelCfg(
        hidden_dims=[256, 128, 64],
        activation="elu",
        obs_normalization=True,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=0.1),
        rnn_type="gru",
        rnn_hidden_dim=128,
        rnn_num_layers=1,
    )
    teacher = RslRlMLPModelCfg(                 # as the PPO actor (agents/rsl_rl_ppo_cfg.py), so it loads
        hidden_dims=[256, 128, 64],
        activation="elu",
        obs_normalization=True,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    algorithm = RslRlDistillationAlgorithmCfg(num_learning_epochs=2, learning_rate=1.0e-3, gradient_length=16,
                                              max_grad_norm=1.0)
