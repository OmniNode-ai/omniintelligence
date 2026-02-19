"""ModelAuditMetrics - metrics about an audit run."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ModelAuditMetrics:
    """Metrics about an audit run.

    Attributes:
        duration_ms: Time taken for the audit in milliseconds.
        violations_total: Total violations found before whitelisting.
        whitelisted_yaml_count: Violations whitelisted by YAML rules.
        whitelisted_pragma_count: Violations whitelisted by inline pragmas.
        violations_by_rule: Breakdown of total violations by rule type.
    """

    duration_ms: int = 0
    violations_total: int = 0
    whitelisted_yaml_count: int = 0
    whitelisted_pragma_count: int = 0
    violations_by_rule: dict[str, int] = field(default_factory=dict)
