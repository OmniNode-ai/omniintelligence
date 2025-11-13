"""
Perfect ONEX Effect Node Example

This fixture provides a fully compliant Effect node implementation
for testing validation logic.

ONEX Compliance:
- Naming: NodeDatabaseWriterEffect (suffix-based)
- File: node_database_writer_effect.py
- Method: async def execute_effect(self, contract: ModelContractEffect)
- Contract: ModelContractEffect with proper structure
- Purpose: External I/O (database write operation)
"""

from typing import Any
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


class ModelContractEffect(ModelContractBase):
    """Contract for Effect nodes."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        target_system: str,
        operation_type: str,
        timeout_seconds: int = 30,
    ):
        super().__init__(name, version, description, "effect")
        self.target_system = target_system
        self.operation_type = operation_type
        self.timeout_seconds = timeout_seconds


class ModelResult:
    """Standard result model."""

    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error


# ============================================================================
# Compliant Effect Node
# ============================================================================


class NodeDatabaseWriterEffect:
    """
    ONEX-Compliant Effect Node for database write operations.

    This node handles external I/O operations with proper:
    - Naming convention (suffix: Effect)
    - Method signature (execute_effect)
    - Contract validation
    - Transaction management
    - Error handling
    """

    def __init__(self, db_pool=None, transaction_manager=None):
        self.db_pool = db_pool
        self.transaction_manager = transaction_manager

    async def execute_effect(self, contract: ModelContractEffect) -> ModelResult:
        """
        Execute database write operation.

        Args:
            contract: Effect contract with operation details

        Returns:
            ModelResult with operation outcome
        """
        try:
            # Validate contract
            if not isinstance(contract, ModelContractEffect):
                return ModelResult(success=False, error="Invalid contract type")

            if contract.target_system != "database":
                return ModelResult(
                    success=False, error=f"Unsupported target: {contract.target_system}"
                )

            # Execute within transaction context
            async with self.transaction_manager.begin():
                result = await self._perform_database_write(contract)

                return ModelResult(
                    success=True,
                    data={"operation_id": str(uuid4()), "rows_affected": result},
                )

        except Exception as e:
            return ModelResult(
                success=False, error=f"Effect execution failed: {str(e)}"
            )

    async def _perform_database_write(self, contract: ModelContractEffect) -> int:
        """Perform the actual database write operation."""
        # Simulated database write
        return 1


# ============================================================================
# Test Fixture Code Strings
# ============================================================================

COMPLIANT_EFFECT_NODE_CODE = '''
class NodeDatabaseWriterEffect:
    """ONEX-Compliant Effect Node for database write operations."""

    async def execute_effect(self, contract: ModelContractEffect) -> ModelResult:
        """Execute database write operation."""
        try:
            async with self.transaction_manager.begin():
                result = await self._perform_database_write(contract)
                return ModelResult(success=True, data=result)
        except Exception as e:
            return ModelResult(success=False, error=str(e))
'''

COMPLIANT_EFFECT_CONTRACT_CODE = '''
class ModelContractEffect(ModelContractBase):
    """Contract for Effect nodes."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        target_system: str,
        operation_type: str,
        timeout_seconds: int = 30,
    ):
        super().__init__(name, version, description, "effect")
        self.target_system = target_system
        self.operation_type = operation_type
        self.timeout_seconds = timeout_seconds
'''
