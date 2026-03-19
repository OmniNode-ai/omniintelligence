# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Export trained PPO routing policy as Bifrost-compatible YAML config.

The exporter:

1. Loads a trained ``PPOPolicy`` checkpoint.
2. Generates a scenario grid covering all observation combinations.
3. Runs policy inference on each scenario.
4. Maps policy decisions to Bifrost routing rules.
5. Exports as YAML parseable by ``ModelBifrostConfig``.

CLI usage::

    uv run python -m omniintelligence.rl.export \\
        --checkpoint checkpoints/routing_latest.pt \\
        --output bifrost_config.yaml

    # Diff against existing static config
    uv run python -m omniintelligence.rl.export \\
        --checkpoint checkpoints/routing_latest.pt \\
        --output bifrost_config.yaml \\
        --diff existing_bifrost.yaml
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import torch
import yaml

from omniintelligence.rl.checkpoint import load_checkpoint
from omniintelligence.rl.contracts.actions import NUM_ROUTING_ACTIONS, RoutingAction
from omniintelligence.rl.contracts.observations import _TASK_TYPES, RoutingObservation
from omniintelligence.rl.export_scenarios import (
    CRITICAL_BUCKETS,
    Scenario,
    generate_scenario_grid,
)
from omniintelligence.rl.policy import PPOPolicy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants: action-to-backend mapping
# ---------------------------------------------------------------------------

#: Maps RoutingAction enum values to Bifrost backend_id slugs.
ACTION_TO_BACKEND: dict[RoutingAction, str] = {
    RoutingAction.QWEN3_30B: "qwen3-30b",
    RoutingAction.QWEN3_14B: "qwen3-14b",
    RoutingAction.DEEPSEEK_R1: "deepseek-r1",
    RoutingAction.EMBEDDING: "embedding",
}

#: Default backend URLs (match the LLM topology from CLAUDE.md).
BACKEND_URLS: dict[str, str] = {
    "qwen3-30b": "http://192.168.86.201:8000",
    "qwen3-14b": "http://192.168.86.201:8001",
    "deepseek-r1": "http://192.168.86.200:8101",
    "embedding": "http://192.168.86.200:8100",
}

#: Model names for each backend.
BACKEND_MODELS: dict[str, str] = {
    "qwen3-30b": "qwen3-coder-30b-a3b-awq",
    "qwen3-14b": "qwen3-14b-awq",
    "deepseek-r1": "deepseek-r1-distill-qwen-32b",
    "embedding": "qwen3-embedding-8b",
}

#: Namespace UUID for deterministic rule_id generation.
_RULE_NAMESPACE = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


# ---------------------------------------------------------------------------
# Fidelity report
# ---------------------------------------------------------------------------


@dataclass
class FidelityReport:
    """Result of comparing policy decisions against exported config rules.

    Attributes:
        total_scenarios: Number of scenarios evaluated.
        agreements: Total number of scenarios where policy and config agree.
        disagreements_by_bucket: Mapping of bucket name to list of
            disagreement descriptions.
        bucket_counts: Total scenarios per bucket.
        bucket_agreements: Agreements per bucket.
    """

    total_scenarios: int = 0
    agreements: int = 0
    disagreements_by_bucket: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list)
    )
    bucket_counts: dict[str, int] = field(default_factory=lambda: Counter())
    bucket_agreements: dict[str, int] = field(default_factory=lambda: Counter())

    @property
    def overall_agreement(self) -> float:
        """Overall agreement ratio [0.0, 1.0]."""
        if self.total_scenarios == 0:
            return 0.0
        return self.agreements / self.total_scenarios

    def bucket_agreement_rate(self, bucket: str) -> float:
        """Agreement rate for a specific bucket.

        Returns 1.0 for empty buckets (no data = no violation).
        """
        count = self.bucket_counts.get(bucket, 0)
        if count == 0:
            return 1.0
        return self.bucket_agreements.get(bucket, 0) / count

    def critical_bucket_violations(self) -> list[str]:
        """Return critical buckets that fall below 80% agreement."""
        violations: list[str] = []
        for bucket in CRITICAL_BUCKETS:
            rate = self.bucket_agreement_rate(bucket)
            if rate < 0.8:
                violations.append(
                    f"{bucket}: {rate:.1%} agreement "
                    f"({self.bucket_agreements.get(bucket, 0)}/{self.bucket_counts.get(bucket, 0)})"
                )
        return violations

    def format_report(self) -> str:
        """Format a human-readable fidelity report."""
        lines: list[str] = [
            "=" * 60,
            "  Policy-to-Bifrost Fidelity Report",
            "=" * 60,
            "",
            f"Overall agreement: {self.overall_agreement:.1%} "
            f"({self.agreements}/{self.total_scenarios})",
            "",
            "Per-bucket breakdown:",
        ]
        for bucket in sorted(self.bucket_counts.keys()):
            rate = self.bucket_agreement_rate(bucket)
            marker = " [CRITICAL]" if bucket in CRITICAL_BUCKETS else ""
            warning = (
                " *** BELOW 80% ***"
                if bucket in CRITICAL_BUCKETS and rate < 0.8
                else ""
            )
            lines.append(
                f"  {bucket}{marker}: {rate:.1%} "
                f"({self.bucket_agreements.get(bucket, 0)}/{self.bucket_counts[bucket]})"
                f"{warning}"
            )

        violations = self.critical_bucket_violations()
        if violations:
            lines.extend(["", "CRITICAL BUCKET VIOLATIONS:"])
            for v in violations:
                lines.append(f"  - {v}")

        # List disagreements in critical buckets
        critical_disagreements = {
            b: d
            for b, d in self.disagreements_by_bucket.items()
            if b in CRITICAL_BUCKETS and d
        }
        if critical_disagreements:
            lines.extend(["", "Disagreements in critical buckets:"])
            for bucket, descs in sorted(critical_disagreements.items()):
                lines.append(f"  [{bucket}] ({len(descs)} disagreements):")
                for desc in descs[:10]:  # Cap at 10 per bucket
                    lines.append(f"    - {desc}")
                if len(descs) > 10:
                    lines.append(f"    ... and {len(descs) - 10} more")

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# PolicyExporter
# ---------------------------------------------------------------------------


class PolicyExporter:
    """Export a trained PPO routing policy as Bifrost-compatible YAML config.

    Args:
        policy: A trained PPOPolicy instance.
        backend_urls: Optional override for backend base URLs.
        backend_models: Optional override for backend model names.
    """

    def __init__(
        self,
        policy: PPOPolicy,
        *,
        backend_urls: dict[str, str] | None = None,
        backend_models: dict[str, str] | None = None,
    ) -> None:
        self._policy = policy
        self._backend_urls = backend_urls or BACKEND_URLS
        self._backend_models = backend_models or BACKEND_MODELS

    # ── Core export ──────────────────────────────────────────────────────

    def export_config(
        self,
        scenarios: list[Scenario] | None = None,
    ) -> dict[str, Any]:
        """Generate Bifrost config dict from policy inference.

        Runs the policy on the scenario grid, aggregates decisions by
        task type, and builds routing rules with backend priority
        ordering based on policy preference.

        Args:
            scenarios: Override scenario grid (defaults to full grid).

        Returns:
            Dictionary matching the ``ModelBifrostConfig`` schema.
        """
        if scenarios is None:
            scenarios = generate_scenario_grid()

        # Collect action distributions per task type
        task_action_counts: dict[str, Counter[int]] = defaultdict(Counter)
        for scenario in scenarios:
            action = self._infer_action(scenario.observation)
            # Determine task type from one-hot
            task_idx = scenario.observation.task_type_onehot.index(
                max(scenario.observation.task_type_onehot)
            )
            task_type = _TASK_TYPES[task_idx]
            task_action_counts[task_type][action] += 1

        # Build config
        backends = self._build_backends()
        routing_rules = self._build_routing_rules(task_action_counts)
        default_backends = self._build_default_backends(task_action_counts)

        return {
            "backends": backends,
            "routing_rules": routing_rules,
            "default_backends": list(default_backends),
            "failover_attempts": 3,
            "failover_backoff_base_ms": 500,
            "circuit_breaker_failure_threshold": 5,
            "circuit_breaker_window_seconds": 30,
            "request_timeout_ms": 10_000,
            "health_check_interval_seconds": 10,
        }

    def export_yaml(
        self,
        scenarios: list[Scenario] | None = None,
    ) -> str:
        """Export config as a YAML string.

        Args:
            scenarios: Override scenario grid.

        Returns:
            YAML string parseable by ``ModelBifrostConfig``.
        """
        config = self.export_config(scenarios=scenarios)
        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    # ── Fidelity check ───────────────────────────────────────────────────

    def check_fidelity(
        self,
        config: dict[str, Any],
        scenarios: list[Scenario] | None = None,
    ) -> FidelityReport:
        """Validate agreement between policy and exported config.

        For each scenario, compares the policy's top action against the
        first backend in the matching routing rule.

        Args:
            config: Bifrost config dict (as returned by ``export_config``).
            scenarios: Override scenario grid.

        Returns:
            ``FidelityReport`` with per-bucket agreement statistics.
        """
        if scenarios is None:
            scenarios = generate_scenario_grid()

        # Build reverse mapping: backend_id -> RoutingAction
        backend_to_action = {v: k for k, v in ACTION_TO_BACKEND.items()}

        # Index routing rules by operation type
        rules_by_op: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rule in config.get("routing_rules", []):
            for op in rule.get("match_operation_types", []):
                rules_by_op[op].append(rule)

        report = FidelityReport()

        for scenario in scenarios:
            report.total_scenarios += 1
            report.bucket_counts[scenario.bucket] += 1

            # Get policy action
            policy_action = self._infer_action(scenario.observation)
            policy_backend = ACTION_TO_BACKEND[RoutingAction(policy_action)]

            # Get config action: find matching rule
            task_idx = scenario.observation.task_type_onehot.index(
                max(scenario.observation.task_type_onehot)
            )
            task_type = _TASK_TYPES[task_idx]

            config_backends = self._resolve_config_backends(
                config, task_type, rules_by_op
            )

            if config_backends and config_backends[0] == policy_backend:
                report.agreements += 1
                report.bucket_agreements[scenario.bucket] += 1
            else:
                config_top = config_backends[0] if config_backends else "<none>"
                report.disagreements_by_bucket[scenario.bucket].append(
                    f"{scenario.description}: policy={policy_backend}, config={config_top}"
                )

        return report

    # ── Diff mode ────────────────────────────────────────────────────────

    @staticmethod
    def diff_configs(
        new_config: dict[str, Any],
        existing_config: dict[str, Any],
    ) -> str:
        """Generate human-readable diff between two Bifrost configs.

        Args:
            new_config: The newly exported config.
            existing_config: The existing static config.

        Returns:
            Human-readable diff string.
        """
        lines: list[str] = [
            "=" * 60,
            "  Bifrost Config Diff (new vs existing)",
            "=" * 60,
            "",
        ]

        # Compare backends
        new_backends = set(new_config.get("backends", {}).keys())
        old_backends = set(existing_config.get("backends", {}).keys())

        added = new_backends - old_backends
        removed = old_backends - new_backends
        common = new_backends & old_backends

        if added:
            lines.append(f"Backends added: {', '.join(sorted(added))}")
        if removed:
            lines.append(f"Backends removed: {', '.join(sorted(removed))}")
        if not added and not removed:
            lines.append(f"Backends unchanged: {', '.join(sorted(common))}")

        # Compare routing rules
        new_rules = new_config.get("routing_rules", [])
        old_rules = existing_config.get("routing_rules", [])

        lines.append("")
        lines.append(
            f"Routing rules: {len(old_rules)} existing -> {len(new_rules)} new"
        )
        lines.append("")

        # Map rules by operation type for comparison
        new_by_op: dict[str, list[str]] = {}
        for rule in new_rules:
            for op in rule.get("match_operation_types", []):
                backends = rule.get("backend_ids", [])
                new_by_op[op] = backends

        old_by_op: dict[str, list[str]] = {}
        for rule in old_rules:
            for op in rule.get("match_operation_types", []):
                backends = rule.get("backend_ids", [])
                old_by_op[op] = backends

        all_ops = sorted(set(list(new_by_op.keys()) + list(old_by_op.keys())))
        for op in all_ops:
            new_b = new_by_op.get(op, [])
            old_b = old_by_op.get(op, [])
            if new_b == old_b:
                lines.append(f"  {op}: unchanged ({' -> '.join(new_b)})")
            else:
                lines.append(f"  {op}:")
                lines.append(
                    f"    existing: {' -> '.join(old_b) if old_b else '<none>'}"
                )
                lines.append(
                    f"    new:      {' -> '.join(new_b) if new_b else '<none>'}"
                )

        # Compare gateway settings
        gateway_keys = [
            "failover_attempts",
            "circuit_breaker_failure_threshold",
            "circuit_breaker_window_seconds",
            "request_timeout_ms",
            "health_check_interval_seconds",
        ]
        settings_diffs: list[str] = []
        for key in gateway_keys:
            new_val = new_config.get(key)
            old_val = existing_config.get(key)
            if new_val != old_val:
                settings_diffs.append(f"  {key}: {old_val} -> {new_val}")

        if settings_diffs:
            lines.extend(["", "Gateway settings changed:"])
            lines.extend(settings_diffs)

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)

    # ── Internals ────────────────────────────────────────────────────────

    def _infer_action(self, obs: RoutingObservation) -> int:
        """Run policy inference and return the argmax action index."""
        with torch.no_grad():
            tensor = obs.to_tensor().unsqueeze(0)
            logits, _ = self._policy(tensor)
            return int(torch.argmax(logits, dim=-1).item())

    def _build_backends(self) -> dict[str, dict[str, Any]]:
        """Build the backends section of the config."""
        backends: dict[str, dict[str, Any]] = {}
        for action in RoutingAction:
            backend_id = ACTION_TO_BACKEND[action]
            url = self._backend_urls.get(
                backend_id, f"http://localhost:800{action.value}"
            )
            model = self._backend_models.get(backend_id)
            backend: dict[str, Any] = {
                "backend_id": backend_id,
                "base_url": url,
                "weight": 1,
            }
            if model:
                backend["model_name"] = model
            backends[backend_id] = backend
        return backends

    def _build_routing_rules(
        self,
        task_action_counts: dict[str, Counter[int]],
    ) -> list[dict[str, Any]]:
        """Build routing rules sorted by policy preference per task type.

        Each rule includes ALL backends ordered by policy preference
        (most-selected first, then remaining backends as failover).
        This guarantees every endpoint appears in every routing rule.
        """
        all_actions = list(range(NUM_ROUTING_ACTIONS))
        rules: list[dict[str, Any]] = []
        for priority, task_type in enumerate(_TASK_TYPES):
            counts = task_action_counts.get(task_type, Counter())
            if not counts:
                continue

            # Sort actions by frequency (most preferred first)
            ranked_actions = sorted(
                counts.keys(), key=lambda a: counts[a], reverse=True
            )
            # Append any actions not seen in scenarios (ensures full coverage)
            remaining = [a for a in all_actions if a not in ranked_actions]
            ranked_actions.extend(remaining)

            backend_ids = [ACTION_TO_BACKEND[RoutingAction(a)] for a in ranked_actions]

            # Generate deterministic UUID from task type
            rule_id = str(uuid5(_RULE_NAMESPACE, task_type))

            rules.append(
                {
                    "rule_id": rule_id,
                    "priority": (priority + 1) * 10,
                    "match_operation_types": [task_type],
                    "match_capabilities": [],
                    "match_cost_tiers": [],
                    "match_max_latency_ms_lte": None,
                    "backend_ids": backend_ids,
                }
            )
        return rules

    def _build_default_backends(
        self,
        task_action_counts: dict[str, Counter[int]],
    ) -> list[str]:
        """Build the default_backends fallback from overall action frequency.

        Includes all backends in preference order, ensuring full coverage.
        """
        overall: Counter[int] = Counter()
        for counts in task_action_counts.values():
            overall.update(counts)
        if not overall:
            return [ACTION_TO_BACKEND[a] for a in RoutingAction]
        ranked = sorted(overall.keys(), key=lambda a: overall[a], reverse=True)
        # Ensure all actions are included
        remaining = [a for a in range(NUM_ROUTING_ACTIONS) if a not in ranked]
        ranked.extend(remaining)
        return [ACTION_TO_BACKEND[RoutingAction(a)] for a in ranked]

    @staticmethod
    def _resolve_config_backends(
        config: dict[str, Any],
        task_type: str,
        rules_by_op: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        """Find the backend ordering for a task type in the config."""
        matching_rules = rules_by_op.get(task_type, [])
        if matching_rules:
            # Use highest-priority (lowest number) rule
            best = min(matching_rules, key=lambda r: r.get("priority", 100))
            return best.get("backend_ids", [])
        return list(config.get("default_backends", []))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export trained PPO routing policy as Bifrost YAML config"
    )
    parser.add_argument(
        "--checkpoint",
        required=True,
        help="Path to PPO policy checkpoint file",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output YAML file path",
    )
    parser.add_argument(
        "--diff",
        default=None,
        help="Path to existing Bifrost config YAML for comparison",
    )
    parser.add_argument(
        "--oversample-degraded",
        type=int,
        default=3,
        help="Oversampling factor for degraded scenarios (default: 3)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the policy exporter.

    Returns:
        Exit code: 0 on success, 1 on fidelity failure.
    """
    args = _parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    start = time.monotonic()

    # Load policy
    logger.info("Loading checkpoint from %s", args.checkpoint)
    policy = load_checkpoint(args.checkpoint)

    # Generate scenarios
    logger.info(
        "Generating scenario grid (oversample_degraded=%d)", args.oversample_degraded
    )
    scenarios = generate_scenario_grid(oversample_degraded=args.oversample_degraded)
    logger.info("Generated %d scenarios", len(scenarios))

    # Export
    exporter = PolicyExporter(policy)
    config = exporter.export_config(scenarios=scenarios)
    yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml_str)
    logger.info("Wrote Bifrost config to %s", output_path)

    # Fidelity check
    report = exporter.check_fidelity(config, scenarios=scenarios)
    print(report.format_report())  # noqa: T201

    # Diff mode
    if args.diff:
        diff_path = Path(args.diff)
        existing = yaml.safe_load(diff_path.read_text())
        diff_output = PolicyExporter.diff_configs(config, existing)
        print(diff_output)  # noqa: T201

    elapsed = time.monotonic() - start
    logger.info("Export completed in %.1f seconds", elapsed)

    # Check fidelity thresholds
    if report.overall_agreement < 0.9:
        logger.error(
            "Overall agreement %.1f%% is below 90%% threshold",
            report.overall_agreement * 100,
        )
        return 1

    violations = report.critical_bucket_violations()
    if violations:
        logger.error("Critical bucket violations: %s", violations)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__: list[str] = [
    "ACTION_TO_BACKEND",
    "BACKEND_MODELS",
    "BACKEND_URLS",
    "FidelityReport",
    "PolicyExporter",
    "main",
]
