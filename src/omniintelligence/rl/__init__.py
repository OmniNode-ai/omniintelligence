# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Reinforcement learning module for learned decision optimization.

This package provides PPO training, reward shaping, calibration analysis,
and related utilities for training RL-based routing policies.
"""

from omniintelligence.rl.calibration import (
    CalibrationThresholds,
    ChannelSensitivityResult,
    RewardCalibrationReport,
    RewardCalibrator,
)
from omniintelligence.rl.checkpoint import load_checkpoint, save_checkpoint
from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.policy import PPOPolicy
from omniintelligence.rl.rewards import (
    RewardConfig,
    RewardShaper,
    RewardSignal,
)
from omniintelligence.rl.trainer import PPOTrainer

__all__ = [
    "CalibrationThresholds",
    "ChannelSensitivityResult",
    "PPOConfig",
    "PPOPolicy",
    "PPOTrainer",
    "RewardCalibrationReport",
    "RewardCalibrator",
    "RewardConfig",
    "RewardShaper",
    "RewardSignal",
    "load_checkpoint",
    "save_checkpoint",
]
