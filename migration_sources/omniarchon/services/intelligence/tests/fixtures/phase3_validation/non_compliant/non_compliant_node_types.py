"""
Non-Compliant ONEX Node Type Implementations

These fixtures provide examples of INCORRECT node type implementations
to test validation detection logic.

Violations:
- I/O operations in Compute nodes (should be pure)
- Pure computations in Effect nodes (should have I/O)
- Missing transaction management in Effect nodes
- State mutations in Compute nodes
- Wrong node type for operation purpose
"""

from typing import Any

# ============================================================================
# VIOLATION: I/O in Compute Node
# ============================================================================


class NodeDataTransformerCompute:
    """
    VIOLATION: Compute node performing I/O operations.

    Compute nodes should be PURE - no external I/O, no side effects.
    This node violates that by accessing database and making HTTP calls.
    """

    def __init__(self, db_pool, http_client):
        self.db_pool = db_pool
        self.http_client = http_client

    async def execute_compute(self, contract) -> Any:
        """WRONG: Compute node with I/O operations."""
        # VIOLATION: Database I/O in Compute node
        async with self.db_pool.acquire() as conn:
            data = await conn.fetchrow("SELECT * FROM users")

        # VIOLATION: HTTP call in Compute node
        response = await self.http_client.get("https://api.example.com/data")

        # VIOLATION: File I/O in Compute node
        with open("/tmp/cache.txt", "r") as f:
            cached_data = f.read()

        # Pure transformation (this part is correct)
        return {"transformed": data, "cached": cached_data, "response": response}


NON_COMPLIANT_IO_IN_COMPUTE_CODE = '''
class NodeDataTransformerCompute:
    """VIOLATION: I/O in Compute node."""

    async def execute_compute(self, contract):
        # VIOLATION: Database query in Compute node
        async with self.db_pool.acquire() as conn:
            data = await conn.fetchrow("SELECT * FROM users")

        # VIOLATION: HTTP call in Compute node
        response = await self.http_client.get("https://api.example.com/data")

        # VIOLATION: File I/O in Compute node
        with open("/tmp/cache.txt", "r") as f:
            cached = f.read()

        return {"data": data, "cached": cached}
'''


# ============================================================================
# VIOLATION: State Mutation in Compute Node
# ============================================================================


class NodeCalculatorCompute:
    """
    VIOLATION: Compute node with state mutations.

    Compute nodes should be stateless and deterministic.
    """

    def __init__(self):
        self._cache = {}  # Mutable state
        self._counter = 0  # Mutable state

    async def execute_compute(self, contract) -> Any:
        """WRONG: Stateful compute operation."""
        # VIOLATION: Mutating internal state
        self._counter += 1

        # VIOLATION: Side effect (caching)
        self._cache[contract.name] = contract.data

        # Pure computation (this part is correct)
        result = contract.data * 2

        return {"result": result, "call_count": self._counter}


NON_COMPLIANT_STATE_IN_COMPUTE_CODE = '''
class NodeCalculatorCompute:
    """VIOLATION: Stateful Compute node."""

    def __init__(self):
        self._cache = {}  # VIOLATION: Mutable state

    async def execute_compute(self, contract):
        # VIOLATION: State mutation
        self._cache[contract.name] = contract.data

        return {"result": contract.data * 2}
'''


# ============================================================================
# VIOLATION: Pure Computation in Effect Node
# ============================================================================


class NodeDataNormalizerEffect:
    """
    VIOLATION: Effect node performing only pure computation.

    Effect nodes should perform external I/O operations.
    If there's no I/O, it should be a Compute node.
    """

    async def execute_effect(self, contract) -> Any:
        """WRONG: Effect node with no I/O operations."""
        # VIOLATION: Only pure computation, no I/O
        normalized = contract.data / 100.0
        squared = normalized**2
        result = {"normalized": normalized, "squared": squared}

        # No database write, no API call, no file I/O
        # This should be a Compute node instead
        return result


NON_COMPLIANT_PURE_IN_EFFECT_CODE = '''
class NodeDataNormalizerEffect:
    """VIOLATION: Effect node with only pure computation."""

    async def execute_effect(self, contract):
        # VIOLATION: No I/O operations, only computation
        normalized = contract.data / 100.0
        return {"normalized": normalized}
'''


# ============================================================================
# VIOLATION: Missing Transaction Management in Effect Node
# ============================================================================


class NodeDatabaseWriterEffect:
    """
    VIOLATION: Effect node without transaction management.

    Effect nodes should use transaction management for safety.
    """

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def execute_effect(self, contract) -> Any:
        """WRONG: No transaction management."""
        # VIOLATION: Direct database write without transaction
        async with self.db_pool.acquire() as conn:
            # No transaction context!
            await conn.execute("INSERT INTO users (name) VALUES ($1)", contract.name)
            await conn.execute("INSERT INTO audit (action) VALUES ($1)", "user_created")

        return {"success": True}


NON_COMPLIANT_NO_TRANSACTION_CODE = '''
class NodeDatabaseWriterEffect:
    """VIOLATION: Effect node without transactions."""

    async def execute_effect(self, contract):
        # VIOLATION: No transaction management
        async with self.db_pool.acquire() as conn:
            await conn.execute("INSERT INTO users (name) VALUES ($1)", contract.name)
            await conn.execute("INSERT INTO audit (action) VALUES ($1)", "created")

        return {"success": True}
'''


# ============================================================================
# VIOLATION: Wrong Node Type for Purpose
# ============================================================================


class NodeAPIClientEffect:
    """
    VIOLATION: Using Effect for orchestration.

    This node coordinates multiple API calls - should be Orchestrator.
    """

    async def execute_effect(self, contract) -> Any:
        """WRONG: Orchestration logic in Effect node."""
        # VIOLATION: This is orchestration, not a simple effect
        user_data = await self._get_user(contract.user_id)
        orders = await self._get_orders(contract.user_id)
        preferences = await self._get_preferences(contract.user_id)

        # Combining results - this is orchestration
        return {
            "user": user_data,
            "orders": orders,
            "preferences": preferences,
        }

    async def _get_user(self, user_id):
        return {"id": user_id}

    async def _get_orders(self, user_id):
        return []

    async def _get_preferences(self, user_id):
        return {}


class NodeEventCounterEffect:
    """
    VIOLATION: Using Effect for aggregation.

    This node aggregates events - should be Reducer.
    """

    def __init__(self):
        self._event_count = 0

    async def execute_effect(self, contract) -> Any:
        """WRONG: Aggregation logic in Effect node."""
        # VIOLATION: This is aggregation, not an effect
        self._event_count += 1
        return {"total_events": self._event_count}


NON_COMPLIANT_WRONG_TYPE_CODE = '''
class NodeAPIClientEffect:
    """VIOLATION: Orchestration in Effect node."""

    async def execute_effect(self, contract):
        # VIOLATION: Multiple coordinated calls = Orchestrator
        user = await self._get_user(contract.user_id)
        orders = await self._get_orders(contract.user_id)
        return {"user": user, "orders": orders}

class NodeEventCounterEffect:
    """VIOLATION: Aggregation in Effect node."""

    async def execute_effect(self, contract):
        # VIOLATION: State aggregation = Reducer
        self._count += 1
        return {"count": self._count}
'''


# ============================================================================
# VIOLATION: Reducer Without State Management
# ============================================================================


class NodeEventAggregatorReducer:
    """
    VIOLATION: Reducer node without proper state management.

    Reducers should manage state properly with persistence.
    """

    async def execute_reduction(self, contract) -> Any:
        """WRONG: No state management."""
        # VIOLATION: No state loading
        # VIOLATION: No state persistence
        # Just returning new data without aggregating with existing state

        return {"events": [contract.event]}


NON_COMPLIANT_NO_STATE_MANAGEMENT_CODE = '''
class NodeEventAggregatorReducer:
    """VIOLATION: Reducer without state management."""

    async def execute_reduction(self, contract):
        # VIOLATION: No state loading or persistence
        return {"events": [contract.event]}
'''


# ============================================================================
# Summary of Node Type Violations
# ============================================================================

NODE_TYPE_VIOLATIONS = {
    "io_in_compute": {
        "description": "Compute node performing I/O operations",
        "severity": "critical",
        "examples": ["Database queries", "HTTP calls", "File I/O"],
    },
    "state_in_compute": {
        "description": "Compute node with mutable state",
        "severity": "critical",
        "examples": ["Instance variables", "Caching", "Counters"],
    },
    "pure_in_effect": {
        "description": "Effect node with only pure computation",
        "severity": "high",
        "examples": ["Mathematical operations only", "No I/O operations"],
    },
    "no_transactions": {
        "description": "Effect node without transaction management",
        "severity": "high",
        "examples": ["Direct database writes", "No rollback capability"],
    },
    "wrong_type": {
        "description": "Using wrong node type for the operation",
        "severity": "critical",
        "examples": [
            "Orchestration in Effect",
            "Aggregation in Effect",
            "I/O in Compute",
        ],
    },
    "no_state_management": {
        "description": "Reducer without proper state management",
        "severity": "high",
        "examples": ["No state loading", "No persistence"],
    },
}
