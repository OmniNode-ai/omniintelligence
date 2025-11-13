"""
ONEX Base Class: Compute Node

Purpose: Base class for all ONEX Compute nodes
Pattern: ONEX 4-Node Architecture - Compute
File: node_base_compute.py
Class: NodeBaseCompute

ONEX Compliant: Base class for pure computation nodes
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

from src.archon_services.pattern_learning.phase1_foundation.quality.model_contract_pattern_quality import (
    ModelContractPatternQuality,
    ModelResult,
)

logger = logging.getLogger(__name__)


class NodeBaseCompute(ABC):
    """
    Base class for ONEX Compute nodes.

    Compute nodes implement pure computation logic with no side effects:
    - No database I/O
    - No external API calls
    - No file system operations
    - Deterministic outputs for same inputs
    - Stateless operations

    Subclasses must implement:
    - execute_compute(self, contract) -> ModelResult

    Example:
        >>> class NodeMyComputeNode(NodeBaseCompute):
        ...     async def execute_compute(self, contract):
        ...         result = self._transform_data(contract.data)
        ...         return ModelResult(success=True, data=result)
    """

    def __init__(self):
        """Initialize base compute node."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._metrics: Dict[str, Any] = {}

    @abstractmethod
    async def execute_compute(
        self, contract: ModelContractPatternQuality
    ) -> ModelResult:
        """
        Execute computation operation.

        This method must be implemented by subclasses.

        Args:
            contract: Contract with input data and parameters

        Returns:
            ModelResult with computation results

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclass must implement execute_compute()")

    def _record_metric(self, metric_name: str, value: Any) -> None:
        """
        Record a performance metric.

        Args:
            metric_name: Metric name
            value: Metric value
        """
        self._metrics[metric_name] = {
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get recorded metrics.

        Returns:
            Dictionary of metrics
        """
        return self._metrics.copy()

    def reset_metrics(self) -> None:
        """Reset recorded metrics."""
        self._metrics.clear()
