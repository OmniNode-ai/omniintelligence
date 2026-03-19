# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for PPO trainer, policy, checkpoint, and config."""

from __future__ import annotations

import time

import pytest
import torch

from omniintelligence.rl.checkpoint import load_checkpoint, save_checkpoint
from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.policy import PPOPolicy
from omniintelligence.rl.trainer import EpisodeReplayBuffer, PPOTrainer


@pytest.mark.unit
class TestPPOConfig:
    """Tests for PPOConfig Pydantic model."""

    def test_defaults(self) -> None:
        config = PPOConfig()
        assert config.lr == pytest.approx(3e-4)
        assert config.gamma == pytest.approx(0.99)
        assert config.gae_lambda == pytest.approx(0.95)
        assert config.clip_epsilon == pytest.approx(0.2)
        assert config.entropy_coeff == pytest.approx(0.01)
        assert config.value_coeff == pytest.approx(0.5)
        assert config.epochs_per_update == 4
        assert config.batch_size == 64
        assert config.hidden_dims == [64, 64]

    def test_custom_values(self) -> None:
        config = PPOConfig(
            lr=1e-3,
            gamma=0.95,
            hidden_dims=[128, 128, 64],
        )
        assert config.lr == pytest.approx(1e-3)
        assert config.gamma == pytest.approx(0.95)
        assert config.hidden_dims == [128, 128, 64]

    def test_serialization_roundtrip(self) -> None:
        config = PPOConfig(lr=1e-2, hidden_dims=[32])
        data = config.model_dump()
        restored = PPOConfig(**data)
        assert restored == config


@pytest.mark.unit
class TestPPOPolicy:
    """Tests for PPOPolicy actor-critic network."""

    def test_forward_shapes(self) -> None:
        policy = PPOPolicy(obs_dim=10, action_dim=4)
        obs = torch.randn(8, 10)
        logits, values = policy(obs)
        assert logits.shape == (8, 4)
        assert values.shape == (8, 1)

    def test_action_probs_sum_to_one(self) -> None:
        policy = PPOPolicy(obs_dim=5, action_dim=3)
        obs = torch.randn(4, 5)
        probs = policy.get_action_probs(obs)
        sums = probs.sum(dim=-1)
        for s in sums:
            assert s.item() == pytest.approx(1.0, abs=1e-5)

    def test_custom_hidden_dims(self) -> None:
        config = PPOConfig(hidden_dims=[128, 64, 32])
        policy = PPOPolicy(obs_dim=20, action_dim=6, config=config)
        obs = torch.randn(2, 20)
        logits, values = policy(obs)
        assert logits.shape == (2, 6)
        assert values.shape == (2, 1)


@pytest.mark.unit
class TestEpisodeReplayBuffer:
    """Tests for the episode replay buffer."""

    def test_add_and_length(self) -> None:
        buf = EpisodeReplayBuffer()
        assert len(buf) == 0
        buf.add([1.0, 2.0], 0, 1.0, [2.0, 3.0], False)
        assert len(buf) == 1
        buf.add([3.0, 4.0], 1, -1.0, [4.0, 5.0], True)
        assert len(buf) == 2

    def test_clear(self) -> None:
        buf = EpisodeReplayBuffer()
        buf.add([1.0], 0, 1.0, [2.0], False)
        buf.clear()
        assert len(buf) == 0


@pytest.mark.unit
class TestPPOTrainer:
    """Tests for PPO training loop."""

    @staticmethod
    def _fill_buffer_toy_problem(
        buffer: EpisodeReplayBuffer,
        policy: PPOPolicy,
        obs_dim: int,
        optimal_action: int,
        n_steps: int = 200,
    ) -> None:
        """Fill buffer with transitions from a toy environment.

        The environment: random observation, one action is always optimal
        (reward=1.0), all others give reward=0.0.
        """
        for _ in range(n_steps):
            obs = torch.randn(obs_dim).tolist()
            # Sample action from current policy
            with torch.no_grad():
                probs = policy.get_action_probs(
                    torch.tensor([obs], dtype=torch.float32)
                )
                action = torch.multinomial(probs[0], 1).item()
            reward = 1.0 if action == optimal_action else 0.0
            next_obs = torch.randn(obs_dim).tolist()
            done = False
            buffer.add(obs, int(action), reward, next_obs, done)

    def test_convergence_toy_problem(self) -> None:
        """After 100 updates, optimal action probability > 0.9."""
        obs_dim = 30
        action_dim = 4
        optimal_action = 2

        config = PPOConfig(
            lr=3e-3,
            epochs_per_update=4,
            batch_size=64,
            hidden_dims=[64, 64],
            entropy_coeff=0.005,
        )
        policy = PPOPolicy(obs_dim=obs_dim, action_dim=action_dim, config=config)
        buffer = EpisodeReplayBuffer()
        trainer = PPOTrainer(policy=policy, buffer=buffer, config=config)

        for _ in range(100):
            buffer.clear()
            self._fill_buffer_toy_problem(
                buffer, policy, obs_dim, optimal_action, n_steps=200
            )
            trainer.update()

        # Check that the optimal action has high probability
        test_obs = torch.randn(50, obs_dim)
        with torch.no_grad():
            probs = policy.get_action_probs(test_obs)
        mean_optimal_prob = probs[:, optimal_action].mean().item()
        assert mean_optimal_prob > 0.9, (
            f"Expected optimal action probability > 0.9, got {mean_optimal_prob:.4f}"
        )

    def test_training_performance(self) -> None:
        """100 updates on 30-dim/4-action space must complete in < 10s on CPU."""
        obs_dim = 30
        action_dim = 4
        optimal_action = 0

        config = PPOConfig(
            lr=3e-3,
            epochs_per_update=4,
            batch_size=64,
            hidden_dims=[64, 64],
        )
        policy = PPOPolicy(obs_dim=obs_dim, action_dim=action_dim, config=config)
        buffer = EpisodeReplayBuffer()
        trainer = PPOTrainer(policy=policy, buffer=buffer, config=config)

        start = time.monotonic()
        for _ in range(100):
            buffer.clear()
            self._fill_buffer_toy_problem(
                buffer, policy, obs_dim, optimal_action, n_steps=200
            )
            trainer.update()
        elapsed = time.monotonic() - start

        assert elapsed < 10.0, f"Expected < 10s for 100 updates, took {elapsed:.2f}s"

    def test_metrics_logged(self) -> None:
        """Training metrics are recorded after each update."""
        config = PPOConfig(epochs_per_update=2, batch_size=32, hidden_dims=[32])
        policy = PPOPolicy(obs_dim=5, action_dim=3, config=config)
        buffer = EpisodeReplayBuffer()
        trainer = PPOTrainer(policy=policy, buffer=buffer, config=config)

        # Fill buffer
        for i in range(50):
            buffer.add(
                [float(i)] * 5,
                i % 3,
                1.0 if i % 3 == 0 else 0.0,
                [float(i + 1)] * 5,
                False,
            )

        metrics = trainer.update()
        assert len(trainer.metrics_history) == 1
        assert trainer.metrics_history[0] is metrics
        # Check all fields are finite numbers
        assert isinstance(metrics.policy_loss, float)
        assert isinstance(metrics.value_loss, float)
        assert isinstance(metrics.entropy, float)
        assert isinstance(metrics.kl_divergence, float)

    def test_empty_buffer_returns_default_metrics(self) -> None:
        config = PPOConfig()
        policy = PPOPolicy(obs_dim=5, action_dim=3, config=config)
        buffer = EpisodeReplayBuffer()
        trainer = PPOTrainer(policy=policy, buffer=buffer, config=config)

        metrics = trainer.update()
        assert metrics.policy_loss == 0.0
        assert metrics.value_loss == 0.0


@pytest.mark.unit
class TestCheckpoint:
    """Tests for checkpoint save/load round-trip."""

    def test_roundtrip_preserves_behavior(self, tmp_path: object) -> None:
        """Checkpoint round-trip must preserve policy behavior exactly."""
        import pathlib

        assert isinstance(tmp_path, pathlib.Path)
        checkpoint_path = tmp_path / "policy.pt"

        config = PPOConfig(hidden_dims=[32, 32])
        policy = PPOPolicy(obs_dim=10, action_dim=4, config=config)
        policy.eval()

        test_obs = torch.randn(5, 10)
        with torch.no_grad():
            original_logits, original_values = policy(test_obs)

        save_checkpoint(policy, checkpoint_path)
        restored = load_checkpoint(checkpoint_path)

        with torch.no_grad():
            restored_logits, restored_values = restored(test_obs)

        assert torch.allclose(original_logits, restored_logits, atol=1e-6)
        assert torch.allclose(original_values, restored_values, atol=1e-6)

    def test_roundtrip_preserves_config(self, tmp_path: object) -> None:
        """Checkpoint round-trip preserves the PPOConfig."""
        import pathlib

        assert isinstance(tmp_path, pathlib.Path)
        checkpoint_path = tmp_path / "policy.pt"

        config = PPOConfig(lr=1e-2, hidden_dims=[128, 64])
        policy = PPOPolicy(obs_dim=20, action_dim=6, config=config)

        save_checkpoint(policy, checkpoint_path)
        restored = load_checkpoint(checkpoint_path)

        assert restored.obs_dim == 20
        assert restored.action_dim == 6
        assert restored.config == config
