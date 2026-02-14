"""Tests for generate_node_report.py script.

This module tests the stub detection logic and report generation functions.
The stub detection uses AST parsing to avoid false positives that regex
would produce (e.g., matching commented code or strings).

Reference: OMN-1140 PR #11 review feedback about stub detection regex.

Stub Detection Rules:
---------------------
A node is considered a "stub" if and only if:
1. It contains a class definition
2. That class has an annotated assignment: is_stub: ClassVar[bool] = True
3. The assignment is a direct ClassVar[bool] annotation with value True

NOT considered stubs (false positive prevention):
- Commented out is_stub declarations
- is_stub mentioned in docstrings or strings
- is_stub = True without ClassVar annotation
- is_stub: ClassVar[bool] = False (explicitly not a stub)
- Abstract methods that raise NotImplementedError (legitimate pattern)
- Empty methods with pass (may be intentional)
- Type stubs using ellipsis (separate from is_stub ClassVar)
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Module-level marker: all tests in this file are unit tests
pytestmark = pytest.mark.unit

# Import the function under test
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
from generate_node_report import check_is_stub, get_node_type

# =========================================================================
# Test Fixtures
# =========================================================================


@pytest.fixture
def valid_stub_code() -> str:
    """Standard stub node with is_stub: ClassVar[bool] = True."""
    return '''"""Stub node example."""
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute


class NodeExampleCompute(NodeCompute):
    """STUB: Example compute node."""

    is_stub: ClassVar[bool] = True

    def compute(self, input_data):
        """Compute method (stub implementation)."""
        return {"result": "stub"}
'''


@pytest.fixture
def non_stub_code() -> str:
    """Standard non-stub node without is_stub marker."""
    return '''"""Non-stub node example."""
from omnibase_core.nodes.node_compute import NodeCompute


class NodeExampleCompute(NodeCompute):
    """Example compute node - fully implemented."""

    def __init__(self):
        super().__init__()
'''


@pytest.fixture
def commented_stub_code() -> str:
    """Code with is_stub commented out (should NOT be detected as stub)."""
    return '''"""Node with commented stub marker."""
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute


class NodeExampleCompute(NodeCompute):
    """Example compute node."""

    # is_stub: ClassVar[bool] = True  # Commented out, not a stub
    # TODO: Remove stub marker when implemented

    def compute(self, input_data):
        return input_data
'''


@pytest.fixture
def string_stub_code() -> str:
    """Code with is_stub in a string (should NOT be detected as stub)."""
    return '''"""Node with is_stub in docstring."""
from omnibase_core.nodes.node_compute import NodeCompute


class NodeExampleCompute(NodeCompute):
    """Example node.

    Note: This node uses is_stub: ClassVar[bool] = True for stub detection.
    But since this is in a docstring, it should not trigger detection.
    """

    def compute(self, input_data):
        return input_data
'''


@pytest.fixture
def explicit_non_stub_code() -> str:
    """Code with is_stub: ClassVar[bool] = False (explicitly NOT a stub)."""
    return '''"""Node explicitly marked as not a stub."""
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute


class NodeExampleCompute(NodeCompute):
    """Example compute node."""

    is_stub: ClassVar[bool] = False  # Explicitly not a stub

    def compute(self, input_data):
        return input_data * 2
'''


@pytest.fixture
def untyped_stub_code() -> str:
    """Code with is_stub = True without ClassVar annotation (should NOT match)."""
    return '''"""Node with untyped is_stub."""
from omnibase_core.nodes.node_compute import NodeCompute


class NodeExampleCompute(NodeCompute):
    """Example compute node."""

    # This is not the proper ONEX stub pattern
    is_stub = True  # No ClassVar annotation

    def compute(self, input_data):
        return input_data
'''


@pytest.fixture
def abstract_method_code() -> str:
    """Code with abstract methods using NotImplementedError (NOT a stub marker)."""
    return '''"""Node with abstract methods."""
from abc import ABC, abstractmethod

from omnibase_core.nodes.node_compute import NodeCompute


class NodeAbstractCompute(NodeCompute, ABC):
    """Abstract compute node base class."""

    @abstractmethod
    def compute(self, input_data):
        """Abstract method - must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement compute()")
'''


@pytest.fixture
def multiple_classes_code() -> str:
    """Code with multiple classes, only one is stub."""
    return '''"""Module with multiple classes."""
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute


class HelperClass:
    """Helper class - not a node."""
    pass


class NodeMainCompute(NodeCompute):
    """Main compute node - not a stub."""

    def compute(self, input_data):
        return input_data


class NodeStubCompute(NodeCompute):
    """STUB: Secondary stub node."""

    is_stub: ClassVar[bool] = True
'''


@pytest.fixture
def nested_class_stub_code() -> str:
    """Code with is_stub in a nested class."""
    return '''"""Module with nested class."""
from typing import ClassVar

from omnibase_core.nodes.node_compute import NodeCompute


class NodeOuterCompute(NodeCompute):
    """Outer node - not a stub itself."""

    class InnerConfig:
        """Inner config class with stub marker."""
        is_stub: ClassVar[bool] = True

    def compute(self, input_data):
        return input_data
'''


@pytest.fixture
def ellipsis_body_code() -> str:
    """Code with ellipsis method body (type stub pattern, NOT is_stub marker)."""
    return '''"""Node with ellipsis method body."""
from omnibase_core.nodes.node_compute import NodeCompute


class NodeExampleCompute(NodeCompute):
    """Example compute node with type stub methods."""

    def compute(self, input_data) -> dict:
        ...  # Ellipsis placeholder, NOT same as is_stub marker
'''


# =========================================================================
# Test Cases: check_is_stub Function
# =========================================================================


class TestCheckIsStub:
    """Test the check_is_stub function for accurate stub detection."""

    def test_detects_standard_stub(self, tmp_path: Path, valid_stub_code: str) -> None:
        """Should detect standard is_stub: ClassVar[bool] = True pattern."""
        file_path = tmp_path / "node.py"
        file_path.write_text(valid_stub_code)

        assert check_is_stub(file_path) is True

    def test_non_stub_returns_false(self, tmp_path: Path, non_stub_code: str) -> None:
        """Should return False for nodes without is_stub marker."""
        file_path = tmp_path / "node.py"
        file_path.write_text(non_stub_code)

        assert check_is_stub(file_path) is False

    def test_ignores_commented_stub(
        self, tmp_path: Path, commented_stub_code: str
    ) -> None:
        """Should NOT detect is_stub when commented out (false positive prevention)."""
        file_path = tmp_path / "node.py"
        file_path.write_text(commented_stub_code)

        assert check_is_stub(file_path) is False

    def test_ignores_string_stub(self, tmp_path: Path, string_stub_code: str) -> None:
        """Should NOT detect is_stub when in a string/docstring (false positive prevention)."""
        file_path = tmp_path / "node.py"
        file_path.write_text(string_stub_code)

        assert check_is_stub(file_path) is False

    def test_explicit_false_not_stub(
        self, tmp_path: Path, explicit_non_stub_code: str
    ) -> None:
        """Should NOT detect as stub when is_stub: ClassVar[bool] = False."""
        file_path = tmp_path / "node.py"
        file_path.write_text(explicit_non_stub_code)

        assert check_is_stub(file_path) is False

    def test_untyped_assignment_not_stub(
        self, tmp_path: Path, untyped_stub_code: str
    ) -> None:
        """Should NOT detect is_stub = True without ClassVar annotation.

        The ONEX pattern requires is_stub: ClassVar[bool] = True for proper
        type checking and IDE support. Plain assignment is not sufficient.
        """
        file_path = tmp_path / "node.py"
        file_path.write_text(untyped_stub_code)

        # This is an intentional design decision: only annotated assignments count
        assert check_is_stub(file_path) is False

    def test_abstract_methods_not_stub(
        self, tmp_path: Path, abstract_method_code: str
    ) -> None:
        """Abstract methods with NotImplementedError are NOT stubs.

        NotImplementedError in abstract methods is a legitimate Python pattern
        and should not be confused with the is_stub ClassVar marker.
        """
        file_path = tmp_path / "node.py"
        file_path.write_text(abstract_method_code)

        assert check_is_stub(file_path) is False

    def test_multiple_classes_finds_stub(
        self, tmp_path: Path, multiple_classes_code: str
    ) -> None:
        """Should detect stub when ANY class in the file has is_stub = True."""
        file_path = tmp_path / "node.py"
        file_path.write_text(multiple_classes_code)

        assert check_is_stub(file_path) is True

    def test_nested_class_stub(
        self, tmp_path: Path, nested_class_stub_code: str
    ) -> None:
        """Should detect is_stub in nested classes (ast.walk traverses all).

        Note: This behavior matches the current implementation. If this is
        not desired, the implementation should be changed to only check
        top-level classes.
        """
        file_path = tmp_path / "node.py"
        file_path.write_text(nested_class_stub_code)

        # Current implementation finds nested class stubs
        assert check_is_stub(file_path) is True

    def test_ellipsis_body_not_stub(
        self, tmp_path: Path, ellipsis_body_code: str
    ) -> None:
        """Ellipsis in method body is NOT the same as is_stub marker.

        Type stubs often use ... (ellipsis) in method bodies, but this
        is distinct from the is_stub: ClassVar[bool] = True marker.
        """
        file_path = tmp_path / "node.py"
        file_path.write_text(ellipsis_body_code)

        assert check_is_stub(file_path) is False

    def test_nonexistent_file_returns_false(self, tmp_path: Path) -> None:
        """Should return False for nonexistent files without raising."""
        file_path = tmp_path / "does_not_exist.py"

        assert check_is_stub(file_path) is False

    def test_syntax_error_returns_false(self, tmp_path: Path) -> None:
        """Should return False for files with syntax errors without raising."""
        file_path = tmp_path / "node.py"
        file_path.write_text("def broken(:\n    pass")  # Syntax error

        assert check_is_stub(file_path) is False

    def test_empty_file_returns_false(self, tmp_path: Path) -> None:
        """Should return False for empty files."""
        file_path = tmp_path / "node.py"
        file_path.write_text("")

        assert check_is_stub(file_path) is False


# =========================================================================
# Test Cases: get_node_type Function
# =========================================================================


class TestGetNodeType:
    """Test the get_node_type function."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("quality_scoring_compute", "compute"),
            ("pattern_learning_compute", "compute"),
            ("intelligence_orchestrator", "orchestrator"),
            ("intelligence_reducer", "reducer"),
            ("unknown_node", "unknown"),
            ("intelligence_adapter", "effect"),  # Special case: adapters are effects
        ],
    )
    def test_node_type_detection(self, name: str, expected: str) -> None:
        """Should correctly detect node type from directory name."""
        assert get_node_type(name) == expected


# =========================================================================
# Integration Test with Real Node Files
# =========================================================================


@pytest.mark.integration
class TestRealNodeStubDetection:
    """Integration tests against real node files in the codebase."""

    @pytest.fixture
    def nodes_directory(self) -> Path:
        """Get the path to the nodes directory."""
        test_dir = Path(__file__).parent
        nodes_dir = test_dir.parent.parent.parent / "src" / "omniintelligence" / "nodes"
        if not nodes_dir.exists():
            pytest.skip(f"Nodes directory not found: {nodes_dir}")
        return nodes_dir

    def test_known_stub_nodes_detected(self, nodes_directory: Path) -> None:
        """Known stub nodes should be detected as stubs."""
        # Note: 9 nodes were removed in PR #12 (vectorization_compute, ingestion_effect,
        # qdrant_vector_effect, memgraph_graph_effect, postgres_pattern_effect,
        # intelligence_api_effect, entity_extraction_compute,
        # context_keyword_extractor_compute, relationship_detection_compute)
        # Note: quality_scoring_compute was implemented in PR #16
        # Note: semantic_analysis_compute was implemented in OMN-1422
        # Note: node_intent_classifier_compute was refactored to thin shell in declarative refactor
        # Note: pattern_learning_compute was implemented
        # Note: pattern_matching_compute was implemented in OMN-1424
        # Note: success_criteria_matcher_compute was implemented in OMN-1426
        # Note: execution_trace_parser_compute was implemented in OMN-1427
        # Note: pattern_assembler_orchestrator was implemented in OMN-1428
        known_stubs: list[str] = []

        if not known_stubs:
            # No known stubs remain -- test is a placeholder for future stubs.
            pytest.skip("No known stub nodes to test - all have been implemented")

        for node_name in known_stubs:
            node_path = nodes_directory / node_name / "node.py"
            if node_path.exists():
                assert (
                    check_is_stub(node_path) is True
                ), f"{node_name} should be detected as stub"

    def test_known_non_stub_nodes_not_detected(self, nodes_directory: Path) -> None:
        """Known non-stub nodes should NOT be detected as stubs."""
        # Note: vectorization_compute was removed in PR #12
        # Note: quality_scoring_compute was implemented in PR #16
        # Note: semantic_analysis_compute was implemented in OMN-1422
        # Note: Folder renames in declarative refactor (node_* prefix)
        # Note: pattern_learning_compute was implemented
        # Note: pattern_matching_compute was implemented in OMN-1424
        # Note: success_criteria_matcher_compute was implemented in OMN-1426
        # Note: execution_trace_parser_compute was implemented in OMN-1427
        # Note: pattern_assembler_orchestrator was implemented in OMN-1428
        known_non_stubs = [
            "intelligence_orchestrator",
            "intelligence_reducer",
            "pattern_learning_compute",
            "node_quality_scoring_compute",
            "node_semantic_analysis_compute",
            "node_intent_classifier_compute",
            "node_pattern_matching_compute",
            "node_success_criteria_matcher_compute",
            "node_execution_trace_parser_compute",
            "node_pattern_assembler_orchestrator",
        ]

        for node_name in known_non_stubs:
            node_path = nodes_directory / node_name / "node.py"
            if node_path.exists():
                assert (
                    check_is_stub(node_path) is False
                ), f"{node_name} should NOT be detected as stub"
