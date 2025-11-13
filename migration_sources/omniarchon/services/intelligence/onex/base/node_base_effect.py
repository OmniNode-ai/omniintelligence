"""
Base Effect Node for ONEX Architecture

Provides foundation for all Effect nodes with transaction management,
logging, and performance monitoring.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict

from .transaction_manager import LightweightTransactionManager

logger = logging.getLogger(__name__)


class NodeBaseEffect(ABC):
    """
    Base class for all ONEX Effect nodes.

    Effect nodes handle side effects including:
    - External I/O operations
    - Database operations
    - API calls
    - Event emissions
    - Vector database operations
    """

    def __init__(self):
        """Initialize base effect node with transaction manager."""
        self.transaction_manager = LightweightTransactionManager()
        self._metrics: Dict[str, Any] = {}

    @abstractmethod
    async def execute_effect(self, contract: Any) -> Any:
        """
        Execute the effect operation.

        Args:
            contract: Contract model defining the operation parameters

        Returns:
            Result model with operation outcome

        Raises:
            Exception: On effect execution failure
        """
        pass

    def _record_metric(self, key: str, value: Any) -> None:
        """Record a performance metric."""
        self._metrics[key] = {
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics."""
        return self._metrics.copy()

    def clear_metrics(self) -> None:
        """Clear collected metrics."""
        self._metrics.clear()
