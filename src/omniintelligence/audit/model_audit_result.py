"""ModelAuditResult - result of an audit run."""

from __future__ import annotations

from dataclasses import dataclass

from omniintelligence.audit.model_audit_metrics import ModelAuditMetrics
from omniintelligence.audit.model_io_audit_violation import ModelIOAuditViolation


@dataclass
class ModelAuditResult:
    """Result of an audit run.

    Attributes:
        violations: List of violations found (after whitelisting).
        files_scanned: Number of files scanned.
        is_clean: True if no violations were found.
        metrics: Optional detailed metrics about the audit run.
    """

    violations: list[ModelIOAuditViolation]
    files_scanned: int
    metrics: ModelAuditMetrics | None = None

    @property
    def is_clean(self) -> bool:
        """Return True if no violations found."""
        return len(self.violations) == 0
