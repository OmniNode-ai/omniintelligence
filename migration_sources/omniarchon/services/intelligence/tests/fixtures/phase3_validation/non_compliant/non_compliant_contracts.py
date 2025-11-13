"""
Non-Compliant ONEX Contract Examples

These fixtures provide examples of INCORRECT contract implementations
to test validation detection logic.

Violations:
- Missing required fields
- Incorrect base class
- Missing validation
- Wrong contract type for node type
- Missing contract entirely
"""

from typing import Any, Dict

# ============================================================================
# VIOLATION: Missing Required Fields
# ============================================================================


class ModelContractEffect:
    """VIOLATION: Missing required base fields."""

    def __init__(self, target_system: str):
        # VIOLATION: Missing name, version, description, node_type
        self.target_system = target_system


NON_COMPLIANT_MISSING_FIELDS_CODE = '''
class ModelContractEffect:
    """VIOLATION: Missing name, version, description, node_type."""

    def __init__(self, target_system: str):
        self.target_system = target_system
'''


# ============================================================================
# VIOLATION: No Base Class Inheritance
# ============================================================================


class ModelContractCompute:  # VIOLATION: Not inheriting from ModelContractBase
    """Should inherit from ModelContractBase."""

    def __init__(self, name: str, algorithm_type: str):
        self.name = name
        self.algorithm_type = algorithm_type
        # VIOLATION: Missing version, description, node_type


NON_COMPLIANT_NO_BASE_CLASS_CODE = '''
class ModelContractCompute:  # VIOLATION: No base class
    """Should inherit from ModelContractBase."""

    def __init__(self, name: str, algorithm_type: str):
        self.name = name
        self.algorithm_type = algorithm_type
'''


# ============================================================================
# VIOLATION: Wrong Contract Type for Node Type
# ============================================================================


class ModelContractBase:
    """Base contract."""

    def __init__(self, name: str, version: str, description: str, node_type: str):
        self.name = name
        self.version = version
        self.description = description
        self.node_type = node_type


class ModelContractCompute(ModelContractBase):
    """Correct Compute contract."""

    def __init__(self, name: str, version: str, description: str):
        super().__init__(name, version, description, "compute")


# Node using wrong contract type
class NodeDatabaseWriterEffect:
    """VIOLATION: Effect node using Compute contract."""

    async def execute_effect(self, contract: ModelContractCompute) -> Any:
        # VIOLATION: Effect node should use ModelContractEffect
        return {"success": True}


NON_COMPLIANT_WRONG_CONTRACT_TYPE_CODE = '''
class NodeDatabaseWriterEffect:
    """VIOLATION: Effect node using Compute contract."""

    async def execute_effect(self, contract: ModelContractCompute):
        # Should be ModelContractEffect
        return {"success": True}
'''


# ============================================================================
# VIOLATION: Missing Contract Type Hints
# ============================================================================


class NodeDataTransformerCompute:
    """VIOLATION: No type hints for contract parameter."""

    async def execute_compute(self, contract) -> Any:  # VIOLATION: No type hint
        return contract.data


NON_COMPLIANT_NO_TYPE_HINTS_CODE = '''
class NodeDataTransformerCompute:
    """VIOLATION: No type hints for contract."""

    async def execute_compute(self, contract):  # Should be contract: ModelContractCompute
        return contract.data
'''


# ============================================================================
# VIOLATION: Incomplete Contract Specialization
# ============================================================================


class ModelContractEffect(ModelContractBase):
    """VIOLATION: Effect contract missing required specialized fields."""

    def __init__(self, name: str, version: str, description: str):
        super().__init__(name, version, description, "effect")
        # VIOLATION: Missing target_system, operation_type, timeout_seconds


NON_COMPLIANT_INCOMPLETE_SPECIALIZATION_CODE = '''
class ModelContractEffect(ModelContractBase):
    """VIOLATION: Missing target_system, operation_type, timeout."""

    def __init__(self, name: str, version: str, description: str):
        super().__init__(name, version, description, "effect")
        # Missing required Effect-specific fields
'''


# ============================================================================
# VIOLATION: Wrong Node Type in Contract
# ============================================================================


class ModelContractEffect(ModelContractBase):
    """VIOLATION: Effect contract with wrong node_type."""

    def __init__(self, name: str, version: str, description: str, target_system: str):
        super().__init__(
            name, version, description, "compute"  # VIOLATION: Should be "effect"
        )
        self.target_system = target_system


NON_COMPLIANT_WRONG_NODE_TYPE_CODE = '''
class ModelContractEffect(ModelContractBase):
    """VIOLATION: node_type mismatch."""

    def __init__(self, name: str, version: str, description: str, target_system: str):
        super().__init__(name, version, description, "compute")  # WRONG
        self.target_system = target_system
'''


# ============================================================================
# VIOLATION: Missing Contract Validation
# ============================================================================


class ModelContractReducer(ModelContractBase):
    """VIOLATION: No validation method."""

    def __init__(self, name: str, version: str, description: str, state_key: str):
        super().__init__(name, version, description, "reducer")
        self.state_key = state_key

    # VIOLATION: Missing validate() method


NON_COMPLIANT_NO_VALIDATION_CODE = '''
class ModelContractReducer(ModelContractBase):
    """VIOLATION: No validate() method."""

    def __init__(self, name: str, version: str, description: str, state_key: str):
        super().__init__(name, version, description, "reducer")
        self.state_key = state_key
        # Missing validation
'''


# ============================================================================
# VIOLATION: Using Plain Dict Instead of Contract
# ============================================================================


class NodeDatabaseWriterEffect:
    """VIOLATION: Using plain dict instead of contract object."""

    async def execute_effect(self, contract: Dict[str, Any]) -> Any:
        # VIOLATION: Should use ModelContractEffect, not dict
        contract.get("target_system")
        return {"success": True}


NON_COMPLIANT_DICT_CONTRACT_CODE = '''
class NodeDatabaseWriterEffect:
    """VIOLATION: Using dict instead of proper contract."""

    async def execute_effect(self, contract: dict):  # WRONG
        # Should be contract: ModelContractEffect
        target = contract.get("target_system")
        return {"success": True}
'''


# ============================================================================
# VIOLATION: Missing Contract Entirely
# ============================================================================


class NodeDataProcessorCompute:
    """VIOLATION: No contract parameter at all."""

    async def execute_compute(self, data: Any) -> Any:
        # VIOLATION: Should accept contract: ModelContractCompute
        return {"processed": data}


NON_COMPLIANT_NO_CONTRACT_CODE = '''
class NodeDataProcessorCompute:
    """VIOLATION: No contract parameter."""

    async def execute_compute(self, data):  # WRONG
        # Should be execute_compute(self, contract: ModelContractCompute)
        return {"processed": data}
'''


# ============================================================================
# VIOLATION: Contract with Invalid node_type
# ============================================================================


class ModelContractCustom(ModelContractBase):
    """VIOLATION: Invalid node_type value."""

    def __init__(self, name: str, version: str, description: str):
        super().__init__(
            name,
            version,
            description,
            "custom",  # VIOLATION: Must be effect/compute/reducer/orchestrator
        )


NON_COMPLIANT_INVALID_NODE_TYPE_CODE = '''
class ModelContractCustom(ModelContractBase):
    """VIOLATION: Invalid node_type 'custom'."""

    def __init__(self, name: str, version: str, description: str):
        super().__init__(name, version, description, "custom")  # INVALID
'''


# ============================================================================
# VIOLATION: Mutable Contract Fields
# ============================================================================


class ModelContractCompute(ModelContractBase):
    """VIOLATION: Contracts should be immutable."""

    def __init__(self, name: str, version: str, description: str):
        super().__init__(name, version, description, "compute")
        self.cache = {}  # VIOLATION: Mutable field

    def add_to_cache(self, key: str, value: Any):
        # VIOLATION: Contracts should not have methods that mutate state
        self.cache[key] = value


NON_COMPLIANT_MUTABLE_CONTRACT_CODE = '''
class ModelContractCompute(ModelContractBase):
    """VIOLATION: Mutable contract with state."""

    def __init__(self, name: str, version: str, description: str):
        super().__init__(name, version, description, "compute")
        self.cache = {}  # VIOLATION

    def add_to_cache(self, key, value):  # VIOLATION
        self.cache[key] = value
'''


# ============================================================================
# Summary of Contract Violations
# ============================================================================

CONTRACT_VIOLATIONS = {
    "missing_fields": {
        "description": "Contract missing required base fields",
        "severity": "critical",
        "examples": ["name", "version", "description", "node_type"],
    },
    "no_base_class": {
        "description": "Contract not inheriting from ModelContractBase",
        "severity": "critical",
        "examples": ["class ModelContractEffect: (no inheritance)"],
    },
    "wrong_contract_type": {
        "description": "Node using wrong contract type",
        "severity": "critical",
        "examples": ["Effect node with Compute contract"],
    },
    "no_type_hints": {
        "description": "Missing type hints for contract parameter",
        "severity": "medium",
        "examples": ["execute_effect(self, contract) without type"],
    },
    "incomplete_specialization": {
        "description": "Specialized contract missing required fields",
        "severity": "high",
        "examples": ["Effect contract without target_system"],
    },
    "wrong_node_type": {
        "description": "Contract with incorrect node_type value",
        "severity": "critical",
        "examples": ["Effect contract with node_type='compute'"],
    },
    "no_validation": {
        "description": "Contract missing validation method",
        "severity": "medium",
        "examples": ["No validate() method"],
    },
    "dict_instead_of_contract": {
        "description": "Using dict instead of proper contract class",
        "severity": "high",
        "examples": ["contract: dict instead of contract: ModelContractEffect"],
    },
    "no_contract": {
        "description": "Node method without contract parameter",
        "severity": "critical",
        "examples": [
            "execute_effect(self, data) instead of execute_effect(self, contract)"
        ],
    },
    "invalid_node_type": {
        "description": "Contract with invalid node_type value",
        "severity": "critical",
        "examples": [
            "node_type='custom' (must be effect/compute/reducer/orchestrator)"
        ],
    },
    "mutable_contract": {
        "description": "Contract with mutable state or methods",
        "severity": "high",
        "examples": ["Contracts should be immutable data structures"],
    },
}
