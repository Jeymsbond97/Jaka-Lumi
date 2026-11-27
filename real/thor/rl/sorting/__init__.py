"""The colour sorting task for Isaac Lab (docs/sorting/04). Importing this registers `Lumi-Sort-v0`.

Needs the Isaac Lab environment (~/isaaclab-spike on the Thor), not the robot's .venv.
"""
import gymnasium as gym

gym.register(
    id="Lumi-Sort-v0",
    entry_point=f"{__name__}.sort_env:SortEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.sort_env_cfg:SortEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.agents.rsl_rl_ppo_cfg:SortPPORunnerCfg",
        "default_agent": "rsl_rl",
    },
)

gym.register(
    id="Lumi-Sort-Distill-v0",
    entry_point=f"{__name__}.sort_env:SortEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.sort_env_cfg:SortDistillEnvCfg",
        "rsl_rl_cfg_entry_point": f"{__name__}.agents.rsl_rl_distillation_cfg:SortDistillationRunnerCfg",
        "default_agent": "rsl_rl",
    },
)
