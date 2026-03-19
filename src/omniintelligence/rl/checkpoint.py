# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Checkpoint save/load for PPO policies."""

from __future__ import annotations

from pathlib import Path

import torch

from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.policy import PPOPolicy


def save_checkpoint(policy: PPOPolicy, path: str | Path) -> None:
    """Save policy state dict and configuration to disk.

    The checkpoint includes the model state dict plus metadata needed to
    reconstruct the policy (obs_dim, action_dim, config).

    Args:
        policy: The PPO policy to save.
        path: File path to write the checkpoint.
    """
    checkpoint = {
        "state_dict": policy.state_dict(),
        "obs_dim": policy.obs_dim,
        "action_dim": policy.action_dim,
        "config": policy.config.model_dump(),
    }
    torch.save(checkpoint, str(path))


def load_checkpoint(path: str | Path) -> PPOPolicy:
    """Load a PPO policy from a checkpoint file.

    Reconstructs the policy architecture from saved metadata and loads
    the state dict. The restored policy produces identical outputs for
    identical inputs.

    Args:
        path: File path to read the checkpoint from.

    Returns:
        A PPOPolicy with restored weights and configuration.

    Raises:
        FileNotFoundError: If the checkpoint file does not exist.
    """
    checkpoint = torch.load(str(path), weights_only=False)
    config = PPOConfig(**checkpoint["config"])
    policy = PPOPolicy(
        obs_dim=checkpoint["obs_dim"],
        action_dim=checkpoint["action_dim"],
        config=config,
    )
    policy.load_state_dict(checkpoint["state_dict"])
    policy.eval()
    return policy
