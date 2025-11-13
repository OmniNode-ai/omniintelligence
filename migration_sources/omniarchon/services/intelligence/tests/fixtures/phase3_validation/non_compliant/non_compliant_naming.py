"""
Non-Compliant ONEX Naming Convention Examples

These fixtures provide examples of INCORRECT naming conventions
to test validation detection logic.

Violations:
- Wrong suffix usage
- Missing suffix
- Wrong case
- Wrong method names
- Wrong file naming patterns
"""

from typing import Any

# ============================================================================
# VIOLATION: Missing Suffix
# ============================================================================


class NodeDatabaseWriter:  # WRONG: Missing "Effect" suffix
    """This should be NodeDatabaseWriterEffect."""

    async def execute_effect(self, contract) -> Any:
        pass


NON_COMPLIANT_MISSING_SUFFIX_CODE = '''
class NodeDatabaseWriter:  # WRONG: Missing "Effect" suffix
    """This should be NodeDatabaseWriterEffect."""

    async def execute_effect(self, contract):
        pass
'''


# ============================================================================
# VIOLATION: Wrong Suffix
# ============================================================================


class NodeDataTransformerEffect:  # WRONG: Should be "Compute" not "Effect"
    """This should be NodeDataTransformerCompute (pure transformation)."""

    async def execute_compute(self, contract) -> Any:
        # Pure computation but wrong suffix
        pass


NON_COMPLIANT_WRONG_SUFFIX_CODE = '''
class NodeDataTransformerEffect:  # WRONG: Should be "Compute"
    """Pure transformation but labeled as Effect."""

    async def execute_compute(self, contract):
        return {"transformed": True}
'''


# ============================================================================
# VIOLATION: Wrong Case
# ============================================================================


class nodeDatabaseWriterEffect:  # WRONG: Should start with capital "N"
    """Wrong case - should be NodeDatabaseWriterEffect."""

    async def execute_effect(self, contract) -> Any:
        pass


class Node_database_writer_effect:  # WRONG: Snake_case instead of PascalCase
    """Wrong case - should be NodeDatabaseWriterEffect."""

    async def execute_effect(self, contract) -> Any:
        pass


NON_COMPLIANT_WRONG_CASE_CODE = """
class nodeDatabaseWriterEffect:  # WRONG: lowercase first letter
    async def execute_effect(self, contract):
        pass

class Node_database_writer_effect:  # WRONG: snake_case
    async def execute_effect(self, contract):
        pass
"""


# ============================================================================
# VIOLATION: Wrong Prefix
# ============================================================================


class DatabaseWriterEffect:  # WRONG: Missing "Node" prefix
    """Should be NodeDatabaseWriterEffect."""

    async def execute_effect(self, contract) -> Any:
        pass


class EffectNodeDatabaseWriter:  # WRONG: Suffix should be at end, prefix "Node" first
    """Should be NodeDatabaseWriterEffect."""

    async def execute_effect(self, contract) -> Any:
        pass


NON_COMPLIANT_WRONG_PREFIX_CODE = """
class DatabaseWriterEffect:  # WRONG: Missing "Node" prefix
    async def execute_effect(self, contract):
        pass

class EffectNodeDatabaseWriter:  # WRONG: Wrong order
    async def execute_effect(self, contract):
        pass
"""


# ============================================================================
# VIOLATION: Wrong Method Names
# ============================================================================


class NodeDatabaseWriterEffect:
    """Correct class name but wrong method signature."""

    async def execute(self, contract) -> Any:  # WRONG: Should be execute_effect
        pass


class NodeDataTransformerCompute:
    """Correct class name but wrong method signature."""

    async def transform(self, contract) -> Any:  # WRONG: Should be execute_compute
        pass


class NodeEventAggregatorReducer:
    """Correct class name but wrong method signature."""

    async def reduce(self, contract) -> Any:  # WRONG: Should be execute_reduction
        pass


class NodeWorkflowCoordinatorOrchestrator:
    """Correct class name but wrong method signature."""

    async def coordinate(
        self, contract
    ) -> Any:  # WRONG: Should be execute_orchestration
        pass


NON_COMPLIANT_WRONG_METHOD_CODE = """
class NodeDatabaseWriterEffect:
    async def execute(self, contract):  # WRONG: Should be execute_effect
        pass

class NodeDataTransformerCompute:
    async def transform(self, contract):  # WRONG: Should be execute_compute
        pass

class NodeEventAggregatorReducer:
    async def reduce(self, contract):  # WRONG: Should be execute_reduction
        pass

class NodeWorkflowCoordinatorOrchestrator:
    async def coordinate(self, contract):  # WRONG: Should be execute_orchestration
        pass
"""


# ============================================================================
# VIOLATION: Wrong File Naming (represented as strings)
# ============================================================================

WRONG_FILE_NAMES = {
    "database_writer_effect.py": "WRONG: Missing 'node_' prefix",
    "NodeDatabaseWriterEffect.py": "WRONG: PascalCase file name (should be snake_case)",
    "node-database-writer-effect.py": "WRONG: Kebab-case (should be snake_case)",
    "node_database_writer.py": "WRONG: Missing '_effect' suffix",
    "effect_node_database_writer.py": "WRONG: Wrong order (should be node_*_effect.py)",
}

CORRECT_FILE_NAMES = {
    "node_database_writer_effect.py": "CORRECT: node_*_effect.py pattern",
    "node_data_transformer_compute.py": "CORRECT: node_*_compute.py pattern",
    "node_event_aggregator_reducer.py": "CORRECT: node_*_reducer.py pattern",
    "node_workflow_coordinator_orchestrator.py": "CORRECT: node_*_orchestrator.py pattern",
}


# ============================================================================
# VIOLATION: Contract Naming
# ============================================================================


class ContractEffect:  # WRONG: Missing "Model" prefix
    """Should be ModelContractEffect."""

    pass


class EffectContract:  # WRONG: Wrong order
    """Should be ModelContractEffect."""

    pass


class ModelEffectContract:  # WRONG: Wrong order
    """Should be ModelContractEffect."""

    pass


NON_COMPLIANT_CONTRACT_NAMING_CODE = """
class ContractEffect:  # WRONG: Missing "Model" prefix
    pass

class EffectContract:  # WRONG: Wrong order
    pass

class ModelEffectContract:  # WRONG: "Effect" should come after "Contract"
    pass
"""


# ============================================================================
# Summary of Naming Violations
# ============================================================================

NAMING_VIOLATIONS = {
    "missing_suffix": {
        "example": "NodeDatabaseWriter",
        "should_be": "NodeDatabaseWriterEffect",
        "severity": "critical",
    },
    "wrong_suffix": {
        "example": "NodeDataTransformerEffect (for pure computation)",
        "should_be": "NodeDataTransformerCompute",
        "severity": "critical",
    },
    "wrong_case": {
        "example": "nodeDatabaseWriterEffect or Node_database_writer_effect",
        "should_be": "NodeDatabaseWriterEffect",
        "severity": "high",
    },
    "wrong_prefix": {
        "example": "DatabaseWriterEffect or EffectNodeDatabaseWriter",
        "should_be": "NodeDatabaseWriterEffect",
        "severity": "critical",
    },
    "wrong_method": {
        "example": "execute(), transform(), reduce(), coordinate()",
        "should_be": "execute_effect(), execute_compute(), execute_reduction(), execute_orchestration()",
        "severity": "critical",
    },
    "wrong_file_name": {
        "example": "database_writer_effect.py or NodeDatabaseWriterEffect.py",
        "should_be": "node_database_writer_effect.py",
        "severity": "medium",
    },
}
