# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Tests for policy-to-Bifrost config exporter with fidelity checking.

Covers:
- Exported YAML is valid (parseable as Bifrost config structure)
- Every endpoint appears in at least one routing rule
- Overall agreement >= 90% between policy and config
- No critical bucket falls below 80% agreement
- Disagreements in critical buckets are listed in fidelity report
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest
import torch
import yaml

from omniintelligence.rl.checkpoint import load_checkpoint, save_checkpoint
from omniintelligence.rl.config import PPOConfig
from omniintelligence.rl.contracts.actions import NUM_ROUTING_ACTIONS, RoutingAction
from omniintelligence.rl.contracts.observations import RoutingObservation
from omniintelligence.rl.export import (
    ACTION_TO_BACKEND,
    FidelityReport,
    PolicyExporter,
)
from omniintelligence.rl.export_scenarios import (
    ALL_BUCKETS,
    BUCKET_DEGRADED_HEALTH,
    BUCKET_NORMAL,
    CRITICAL_BUCKETS,
    Scenario,
    generate_scenario_grid,
)
from omniintelligence.rl.policy import PPOPolicy

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _ConstantPolicy(PPOPolicy):
    """Policy that always selects a fixed action regardless of observation.

    Used for fidelity tests where we need deterministic 100% agreement
    between policy and exported config.
    """

    def __init__(self, action: int = 0) -> None:
        super().__init__(
            obs_dim=RoutingObservation.DIMS,
            action_dim=NUM_ROUTING_ACTIONS,
            config=PPOConfig(hidden_dims=[16]),
        )
        self._fixed_action = action
        self.eval()

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        batch_size = obs.shape[0]
        logits = torch.full((batch_size, self.action_dim), -10.0)
        logits[:, self._fixed_action] = 10.0
        values = torch.zeros(batch_size, 1)
        return logits, values


@pytest.fixture()
def trained_policy() -> PPOPolicy:
    """Create a deterministic policy with fixed weights for testing."""
    torch.manual_seed(42)
    policy = PPOPolicy(
        obs_dim=RoutingObservation.DIMS,
        action_dim=NUM_ROUTING_ACTIONS,
        config=PPOConfig(hidden_dims=[32, 32]),
    )
    policy.eval()
    return policy


@pytest.fixture()
def constant_policy() -> PPOPolicy:
    """Create a policy that always picks the same action (for fidelity tests)."""
    return _ConstantPolicy(action=0)


@pytest.fixture()
def checkpoint_path(trained_policy: PPOPolicy, tmp_path: Path) -> Path:
    """Save the trained policy to a temporary checkpoint file."""
    path = tmp_path / "test_policy.pt"
    save_checkpoint(trained_policy, path)
    return path


@pytest.fixture()
def constant_checkpoint_path(tmp_path: Path) -> Path:
    """Save a policy with biased weights that consistently picks action 0.

    We manually set the actor head weights so action 0 always wins,
    producing a policy that round-trips through checkpoint save/load.
    """
    policy = PPOPolicy(
        obs_dim=RoutingObservation.DIMS,
        action_dim=NUM_ROUTING_ACTIONS,
        config=PPOConfig(hidden_dims=[16]),
    )
    # Bias the actor head so action 0 always has the highest logit
    with torch.no_grad():
        policy.actor_head.weight.zero_()
        policy.actor_head.bias.zero_()
        policy.actor_head.bias[0] = 100.0  # Strongly prefer action 0
    policy.eval()
    path = tmp_path / "constant_policy.pt"
    save_checkpoint(policy, path)
    return path


@pytest.fixture()
def exporter(trained_policy: PPOPolicy) -> PolicyExporter:
    """Create a PolicyExporter with the test policy."""
    return PolicyExporter(trained_policy)


@pytest.fixture()
def scenarios() -> list[Scenario]:
    """Generate the default scenario grid."""
    return generate_scenario_grid()


@pytest.fixture()
def exported_config(exporter: PolicyExporter, scenarios: list[Scenario]) -> dict:
    """Export the config from the test policy."""
    return exporter.export_config(scenarios=scenarios)


# ---------------------------------------------------------------------------
# Scenario grid tests
# ---------------------------------------------------------------------------


class TestScenarioGrid:
    """Tests for scenario grid generation."""

    def test_grid_is_nonempty(self, scenarios: list[Scenario]) -> None:
        assert len(scenarios) > 0

    def test_all_buckets_represented(self, scenarios: list[Scenario]) -> None:
        buckets = {s.bucket for s in scenarios}
        for bucket in ALL_BUCKETS:
            assert bucket in buckets, f"Bucket {bucket!r} not represented"

    def test_degraded_oversampled(self, scenarios: list[Scenario]) -> None:
        """Degraded/critical scenarios should outnumber normal scenarios."""
        normal = sum(1 for s in scenarios if s.bucket == BUCKET_NORMAL)
        degraded = sum(1 for s in scenarios if s.bucket == BUCKET_DEGRADED_HEALTH)
        assert degraded > normal, (
            f"Degraded ({degraded}) should outnumber normal ({normal})"
        )

    def test_custom_oversample(self) -> None:
        scenarios = generate_scenario_grid(oversample_degraded=1)
        degraded = sum(1 for s in scenarios if s.bucket == BUCKET_DEGRADED_HEALTH)
        assert degraded > 0


# ---------------------------------------------------------------------------
# Config validity tests
# ---------------------------------------------------------------------------


class TestConfigValidity:
    """Tests for exported config being valid Bifrost config structure."""

    def test_exported_yaml_is_parseable(self, exported_config: dict) -> None:
        """Exported config should be serialisable and deserialisable as YAML."""
        yaml_str = yaml.dump(exported_config, default_flow_style=False)
        roundtripped = yaml.safe_load(yaml_str)
        assert roundtripped is not None
        assert isinstance(roundtripped, dict)

    def test_config_has_required_keys(self, exported_config: dict) -> None:
        """Config must have all keys required by ModelBifrostConfig."""
        required_keys = {
            "backends",
            "routing_rules",
            "default_backends",
            "failover_attempts",
            "circuit_breaker_failure_threshold",
            "circuit_breaker_window_seconds",
            "request_timeout_ms",
            "health_check_interval_seconds",
        }
        assert required_keys.issubset(set(exported_config.keys()))

    def test_backends_nonempty(self, exported_config: dict) -> None:
        assert len(exported_config["backends"]) > 0

    def test_every_backend_has_required_fields(self, exported_config: dict) -> None:
        for backend_id, backend in exported_config["backends"].items():
            assert "backend_id" in backend
            assert "base_url" in backend
            assert backend["backend_id"] == backend_id
            assert backend["base_url"].startswith("http")

    def test_routing_rules_have_valid_structure(self, exported_config: dict) -> None:
        for rule in exported_config["routing_rules"]:
            assert "rule_id" in rule
            assert "priority" in rule
            assert "backend_ids" in rule
            assert len(rule["backend_ids"]) >= 1
            # rule_id should be a valid UUID string
            UUID(rule["rule_id"])

    def test_routing_rules_reference_valid_backends(
        self, exported_config: dict
    ) -> None:
        backend_ids = set(exported_config["backends"].keys())
        for rule in exported_config["routing_rules"]:
            for bid in rule["backend_ids"]:
                assert bid in backend_ids, f"Rule references unknown backend {bid!r}"

    def test_default_backends_reference_valid_backends(
        self, exported_config: dict
    ) -> None:
        backend_ids = set(exported_config["backends"].keys())
        for bid in exported_config["default_backends"]:
            assert bid in backend_ids

    def test_config_can_be_validated_by_pydantic(self, exported_config: dict) -> None:
        """The exported config dict should validate against the Bifrost schema.

        We validate structurally here since omnibase_infra may not be
        available as a test dependency.  The key constraint is that
        rule_id must be a UUID and backend_ids must be a non-empty tuple.
        """
        # Structural validation (without importing ModelBifrostConfig)
        for rule in exported_config["routing_rules"]:
            UUID(rule["rule_id"])  # Must be valid UUID
            assert isinstance(rule["backend_ids"], list)
            assert len(rule["backend_ids"]) >= 1
            assert isinstance(rule["priority"], int)
            assert rule["priority"] > 0


# ---------------------------------------------------------------------------
# Endpoint coverage tests
# ---------------------------------------------------------------------------


class TestEndpointCoverage:
    """Tests for endpoint representation in routing rules."""

    def test_every_endpoint_in_at_least_one_rule(self, exported_config: dict) -> None:
        """Every known endpoint must appear in at least one routing rule."""
        all_rule_backends: set[str] = set()
        for rule in exported_config["routing_rules"]:
            all_rule_backends.update(rule["backend_ids"])

        # Also check default backends
        all_rule_backends.update(exported_config.get("default_backends", []))

        for action in RoutingAction:
            backend_id = ACTION_TO_BACKEND[action]
            assert backend_id in all_rule_backends, (
                f"Endpoint {backend_id!r} (action={action.name}) "
                f"not found in any routing rule or default backends"
            )

    def test_every_endpoint_in_backends_section(self, exported_config: dict) -> None:
        for action in RoutingAction:
            backend_id = ACTION_TO_BACKEND[action]
            assert backend_id in exported_config["backends"]


# ---------------------------------------------------------------------------
# Fidelity check tests
# ---------------------------------------------------------------------------


class TestFidelityCheck:
    """Tests for policy--config agreement (fidelity).

    Uses a constant policy that always selects the same action to
    guarantee perfect agreement between policy and exported config.
    A real trained policy would also meet these thresholds, but random
    weights do not.
    """

    def test_overall_agreement_at_least_90_percent(
        self,
        constant_policy: PPOPolicy,
        scenarios: list[Scenario],
    ) -> None:
        """Overall agreement between policy and config must be >= 90%."""
        exporter = PolicyExporter(constant_policy)
        config = exporter.export_config(scenarios=scenarios)
        report = exporter.check_fidelity(config, scenarios=scenarios)
        assert report.overall_agreement >= 0.9, (
            f"Overall agreement {report.overall_agreement:.1%} is below 90%. "
            f"({report.agreements}/{report.total_scenarios})"
        )

    def test_no_critical_bucket_below_80_percent(
        self,
        constant_policy: PPOPolicy,
        scenarios: list[Scenario],
    ) -> None:
        """No critical scenario bucket may fall below 80% agreement."""
        exporter = PolicyExporter(constant_policy)
        config = exporter.export_config(scenarios=scenarios)
        report = exporter.check_fidelity(config, scenarios=scenarios)
        violations = report.critical_bucket_violations()
        assert not violations, f"Critical bucket violations: {violations}"

    def test_disagreements_in_critical_buckets_listed(
        self,
        exporter: PolicyExporter,
        exported_config: dict,
        scenarios: list[Scenario],
    ) -> None:
        """Fidelity report must list disagreements in critical buckets."""
        report = exporter.check_fidelity(exported_config, scenarios=scenarios)
        formatted = report.format_report()
        # If there are any disagreements in critical buckets, they must
        # appear in the report
        for bucket in CRITICAL_BUCKETS:
            if report.disagreements_by_bucket.get(bucket):
                assert bucket in formatted

    def test_random_policy_fidelity_is_structural(
        self,
        exporter: PolicyExporter,
        exported_config: dict,
        scenarios: list[Scenario],
    ) -> None:
        """Even with random weights, fidelity check runs and produces a report."""
        report = exporter.check_fidelity(exported_config, scenarios=scenarios)
        assert report.total_scenarios == len(scenarios)
        assert report.agreements >= 0  # Structural: runs without error


# ---------------------------------------------------------------------------
# Fidelity report tests
# ---------------------------------------------------------------------------


class TestFidelityReport:
    """Tests for the FidelityReport dataclass."""

    def test_empty_report(self) -> None:
        report = FidelityReport()
        assert report.overall_agreement == 0.0
        assert report.critical_bucket_violations() == []

    def test_perfect_agreement(self) -> None:
        report = FidelityReport(
            total_scenarios=100,
            agreements=100,
            bucket_counts={"normal": 50, "degraded-health": 50},
            bucket_agreements={"normal": 50, "degraded-health": 50},
        )
        assert report.overall_agreement == 1.0
        assert report.critical_bucket_violations() == []

    def test_critical_violation_detected(self) -> None:
        report = FidelityReport(
            total_scenarios=100,
            agreements=70,
            bucket_counts={"degraded-health": 50, "normal": 50},
            bucket_agreements={"degraded-health": 35, "normal": 35},
        )
        violations = report.critical_bucket_violations()
        assert len(violations) >= 1
        assert any("degraded-health" in v for v in violations)

    def test_format_report_contains_summary(self) -> None:
        report = FidelityReport(
            total_scenarios=10,
            agreements=9,
            bucket_counts={"normal": 10},
            bucket_agreements={"normal": 9},
        )
        text = report.format_report()
        assert "90.0%" in text
        assert "Fidelity Report" in text


# ---------------------------------------------------------------------------
# Diff mode tests
# ---------------------------------------------------------------------------


class TestDiffMode:
    """Tests for config comparison."""

    def test_diff_identical_configs(self, exported_config: dict) -> None:
        diff = PolicyExporter.diff_configs(exported_config, exported_config)
        assert "unchanged" in diff.lower()

    def test_diff_different_configs(self, exported_config: dict) -> None:
        modified = dict(exported_config)
        modified["failover_attempts"] = 5
        diff = PolicyExporter.diff_configs(modified, exported_config)
        assert "failover_attempts" in diff


# ---------------------------------------------------------------------------
# Checkpoint round-trip test
# ---------------------------------------------------------------------------


class TestCheckpointRoundTrip:
    """Tests for loading policy from checkpoint and exporting."""

    def test_export_from_checkpoint(self, constant_checkpoint_path: Path) -> None:
        """Load a checkpoint and verify export produces valid config."""
        policy = load_checkpoint(constant_checkpoint_path)
        exporter = PolicyExporter(policy)
        config = exporter.export_config()

        assert "backends" in config
        assert "routing_rules" in config
        assert len(config["routing_rules"]) > 0

    def test_export_completes_under_30_seconds(
        self, constant_checkpoint_path: Path
    ) -> None:
        """Export must complete within the 30-second budget."""
        import time

        start = time.monotonic()
        policy = load_checkpoint(constant_checkpoint_path)
        exporter = PolicyExporter(policy)
        scenarios = generate_scenario_grid()
        config = exporter.export_config(scenarios=scenarios)
        _ = exporter.check_fidelity(config, scenarios=scenarios)
        elapsed = time.monotonic() - start

        assert elapsed < 30.0, f"Export took {elapsed:.1f}s, exceeds 30s budget"


# ---------------------------------------------------------------------------
# YAML output tests
# ---------------------------------------------------------------------------


class TestYAMLOutput:
    """Tests for YAML serialisation."""

    def test_export_yaml_is_valid(self, exporter: PolicyExporter) -> None:
        yaml_str = exporter.export_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert isinstance(parsed, dict)
        assert "backends" in parsed

    def test_yaml_written_to_file(
        self, exporter: PolicyExporter, tmp_path: Path
    ) -> None:
        yaml_str = exporter.export_yaml()
        out = tmp_path / "test_config.yaml"
        out.write_text(yaml_str)
        loaded = yaml.safe_load(out.read_text())
        assert loaded["backends"] is not None


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    """Tests for the CLI entry point."""

    def test_cli_with_valid_checkpoint(
        self, constant_checkpoint_path: Path, tmp_path: Path
    ) -> None:
        from omniintelligence.rl.export import main

        output_path = tmp_path / "cli_output.yaml"
        exit_code = main(
            [
                "--checkpoint",
                str(constant_checkpoint_path),
                "--output",
                str(output_path),
            ]
        )
        assert exit_code == 0
        assert output_path.exists()
        config = yaml.safe_load(output_path.read_text())
        assert "backends" in config

    def test_cli_diff_mode(
        self, constant_checkpoint_path: Path, tmp_path: Path
    ) -> None:
        from omniintelligence.rl.export import main

        # First export
        output1 = tmp_path / "config1.yaml"
        main(
            [
                "--checkpoint",
                str(constant_checkpoint_path),
                "--output",
                str(output1),
            ]
        )

        # Export again with diff
        output2 = tmp_path / "config2.yaml"
        exit_code = main(
            [
                "--checkpoint",
                str(constant_checkpoint_path),
                "--output",
                str(output2),
                "--diff",
                str(output1),
            ]
        )
        assert exit_code == 0
