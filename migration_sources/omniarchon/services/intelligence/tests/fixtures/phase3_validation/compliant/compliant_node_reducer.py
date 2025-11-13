"""
Perfect ONEX Reducer Node Example

This fixture provides a fully compliant Reducer node implementation
for testing validation logic.

ONEX Compliance:
- Naming: NodeEventAggregatorReducer (suffix-based)
- File: node_event_aggregator_reducer.py
- Method: async def execute_reduction(self, contract: ModelContractReducer)
- Contract: ModelContractReducer with proper structure
- Purpose: Aggregation, persistence, state management
"""

from typing import Any, Dict
from uuid import uuid4

# ============================================================================
# Compliant Contract
# ============================================================================


class ModelContractBase:
    """Base contract for ONEX nodes."""

    def __init__(self, name: str, version: str, description: str, node_type: str):
        self.name = name
        self.version = version
        self.description = description
        self.node_type = node_type


class ModelContractReducer(ModelContractBase):
    """Contract for Reducer nodes."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        aggregation_strategy: str,
        state_key: str,
        persistence_required: bool = True,
    ):
        super().__init__(name, version, description, "reducer")
        self.aggregation_strategy = aggregation_strategy
        self.state_key = state_key
        self.persistence_required = persistence_required


class ModelResult:
    """Standard result model."""

    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error


# ============================================================================
# Compliant Reducer Node
# ============================================================================


class NodeEventAggregatorReducer:
    """
    ONEX-Compliant Reducer Node for event aggregation and state management.

    This node handles:
    - Event aggregation
    - State persistence
    - Data reduction
    - Proper naming convention (suffix: Reducer)
    - Method signature (execute_reduction)
    """

    def __init__(self, state_manager=None, persistence_layer=None):
        self.state_manager = state_manager
        self.persistence_layer = persistence_layer
        self._internal_state: Dict[str, Any] = {}

    async def execute_reduction(self, contract: ModelContractReducer) -> ModelResult:
        """
        Execute event aggregation and state reduction.

        Args:
            contract: Reducer contract with aggregation details

        Returns:
            ModelResult with aggregated state
        """
        try:
            # Validate contract
            if not isinstance(contract, ModelContractReducer):
                return ModelResult(success=False, error="Invalid contract type")

            if not contract.state_key:
                return ModelResult(success=False, error="Missing state key")

            # Get current state
            current_state = await self._load_state(contract.state_key)

            # Apply aggregation strategy
            aggregated_state = await self._aggregate_events(
                current_state, contract.aggregation_strategy
            )

            # Persist if required
            if contract.persistence_required:
                await self._persist_state(contract.state_key, aggregated_state)

            return ModelResult(
                success=True,
                data={
                    "state_key": contract.state_key,
                    "aggregated_state": aggregated_state,
                    "event_count": aggregated_state.get("event_count", 0),
                },
            )

        except Exception as e:
            return ModelResult(
                success=False, error=f"Reduction execution failed: {str(e)}"
            )

    async def _load_state(self, state_key: str) -> Dict[str, Any]:
        """Load current state from storage."""
        # Check internal state first
        if state_key in self._internal_state:
            return self._internal_state[state_key]

        # Load from persistence layer
        if self.state_manager:
            return await self.state_manager.load(state_key)

        # Return empty state if not found
        return {"event_count": 0, "events": [], "metadata": {}}

    async def _aggregate_events(
        self, current_state: Dict[str, Any], strategy: str
    ) -> Dict[str, Any]:
        """
        Apply aggregation strategy to events.

        Args:
            current_state: Current aggregated state
            strategy: Aggregation strategy to apply

        Returns:
            Updated aggregated state
        """
        if strategy == "count":
            return self._count_aggregation(current_state)
        elif strategy == "sum":
            return self._sum_aggregation(current_state)
        elif strategy == "average":
            return self._average_aggregation(current_state)
        elif strategy == "merge":
            return self._merge_aggregation(current_state)
        else:
            return current_state

    def _count_aggregation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Count aggregation strategy."""
        state["event_count"] = state.get("event_count", 0) + 1
        return state

    def _sum_aggregation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Sum aggregation strategy."""
        events = state.get("events", [])
        total = sum(e.get("value", 0) for e in events)
        state["total"] = total
        return state

    def _average_aggregation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Average aggregation strategy."""
        events = state.get("events", [])
        if events:
            total = sum(e.get("value", 0) for e in events)
            state["average"] = total / len(events)
        return state

    def _merge_aggregation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Merge aggregation strategy."""
        state["merged_at"] = str(uuid4())
        return state

    async def _persist_state(self, state_key: str, state: Dict[str, Any]) -> None:
        """Persist aggregated state."""
        # Update internal state
        self._internal_state[state_key] = state

        # Persist to storage layer
        if self.persistence_layer:
            await self.persistence_layer.save(state_key, state)


# ============================================================================
# Test Fixture Code Strings
# ============================================================================

COMPLIANT_REDUCER_NODE_CODE = '''
class NodeEventAggregatorReducer:
    """ONEX-Compliant Reducer Node for event aggregation."""

    async def execute_reduction(self, contract: ModelContractReducer) -> ModelResult:
        """Execute event aggregation and state reduction."""
        try:
            current_state = await self._load_state(contract.state_key)
            aggregated_state = await self._aggregate_events(
                current_state, contract.aggregation_strategy
            )
            if contract.persistence_required:
                await self._persist_state(contract.state_key, aggregated_state)
            return ModelResult(success=True, data=aggregated_state)
        except Exception as e:
            return ModelResult(success=False, error=str(e))
'''

COMPLIANT_REDUCER_CONTRACT_CODE = '''
class ModelContractReducer(ModelContractBase):
    """Contract for Reducer nodes."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        aggregation_strategy: str,
        state_key: str,
        persistence_required: bool = True,
    ):
        super().__init__(name, version, description, "reducer")
        self.aggregation_strategy = aggregation_strategy
        self.state_key = state_key
        self.persistence_required = persistence_required
'''
