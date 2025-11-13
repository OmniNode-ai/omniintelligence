"""
Perfect ONEX Compute Node Example

This fixture provides a fully compliant Compute node implementation
for testing validation logic.

ONEX Compliance:
- Naming: NodeDataTransformerCompute (suffix-based)
- File: node_data_transformer_compute.py
- Method: async def execute_compute(self, contract: ModelContractCompute)
- Contract: ModelContractCompute with proper structure
- Purpose: Pure transformation/algorithm (NO I/O)
"""

from typing import Any, Dict

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


class ModelContractCompute(ModelContractBase):
    """Contract for Compute nodes."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        algorithm_type: str,
        input_schema: Dict[str, Any],
        output_schema: Dict[str, Any],
    ):
        super().__init__(name, version, description, "compute")
        self.algorithm_type = algorithm_type
        self.input_schema = input_schema
        self.output_schema = output_schema


class ModelResult:
    """Standard result model."""

    def __init__(self, success: bool, data: Any = None, error: str = None):
        self.success = success
        self.data = data
        self.error = error


# ============================================================================
# Compliant Compute Node
# ============================================================================


class NodeDataTransformerCompute:
    """
    ONEX-Compliant Compute Node for pure data transformation.

    This node handles pure transformations with:
    - NO external I/O operations
    - NO side effects
    - Deterministic outputs
    - Proper naming convention (suffix: Compute)
    - Method signature (execute_compute)
    """

    def __init__(self):
        pass

    async def execute_compute(self, contract: ModelContractCompute) -> ModelResult:
        """
        Execute pure data transformation.

        Args:
            contract: Compute contract with transformation details

        Returns:
            ModelResult with transformed data
        """
        try:
            # Validate contract
            if not isinstance(contract, ModelContractCompute):
                return ModelResult(success=False, error="Invalid contract type")

            # Validate input schema
            if not contract.input_schema:
                return ModelResult(success=False, error="Missing input schema")

            # Perform pure transformation
            transformed_data = await self._transform_data(
                contract.input_schema, contract.algorithm_type
            )

            # Validate output against schema
            if not self._validate_output(transformed_data, contract.output_schema):
                return ModelResult(success=False, error="Output validation failed")

            return ModelResult(success=True, data=transformed_data)

        except Exception as e:
            return ModelResult(
                success=False, error=f"Compute execution failed: {str(e)}"
            )

    async def _transform_data(
        self, input_data: Dict[str, Any], algorithm: str
    ) -> Dict[str, Any]:
        """
        Pure transformation logic - NO I/O.

        Args:
            input_data: Input data structure
            algorithm: Transformation algorithm to apply

        Returns:
            Transformed data
        """
        # Pure transformation examples
        if algorithm == "normalize":
            return self._normalize_data(input_data)
        elif algorithm == "aggregate":
            return self._aggregate_data(input_data)
        elif algorithm == "filter":
            return self._filter_data(input_data)
        else:
            return input_data

    def _normalize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize data values."""
        return {k: self._normalize_value(v) for k, v in data.items()}

    def _normalize_value(self, value: Any) -> Any:
        """Normalize a single value."""
        if isinstance(value, (int, float)):
            return float(value) / 100.0
        return value

    def _aggregate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate data values."""
        numeric_values = [v for v in data.values() if isinstance(v, (int, float))]
        return {
            "count": len(numeric_values),
            "sum": sum(numeric_values),
            "avg": sum(numeric_values) / len(numeric_values) if numeric_values else 0,
        }

    def _filter_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter data values."""
        return {k: v for k, v in data.items() if v is not None}

    def _validate_output(self, data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
        """Validate output against schema."""
        # Simple schema validation
        if not schema:
            return True

        required_fields = schema.get("required", [])
        return all(field in data for field in required_fields)


# ============================================================================
# Test Fixture Code Strings
# ============================================================================

COMPLIANT_COMPUTE_NODE_CODE = '''
class NodeDataTransformerCompute:
    """ONEX-Compliant Compute Node for pure data transformation."""

    async def execute_compute(self, contract: ModelContractCompute) -> ModelResult:
        """Execute pure data transformation - NO I/O."""
        try:
            transformed_data = await self._transform_data(
                contract.input_schema, contract.algorithm_type
            )
            return ModelResult(success=True, data=transformed_data)
        except Exception as e:
            return ModelResult(success=False, error=str(e))

    async def _transform_data(self, input_data: dict, algorithm: str) -> dict:
        """Pure transformation logic - NO I/O."""
        if algorithm == "normalize":
            return {k: float(v) / 100.0 for k, v in input_data.items()}
        return input_data
'''

COMPLIANT_COMPUTE_CONTRACT_CODE = '''
class ModelContractCompute(ModelContractBase):
    """Contract for Compute nodes."""

    def __init__(
        self,
        name: str,
        version: str,
        description: str,
        algorithm_type: str,
        input_schema: dict,
        output_schema: dict,
    ):
        super().__init__(name, version, description, "compute")
        self.algorithm_type = algorithm_type
        self.input_schema = input_schema
        self.output_schema = output_schema
'''
