# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for generate_node_report.py script.

Tests for node scanning, report generation, and CLI behavior.
Covers main function logic, node discovery, report generation,
error handling, and edge cases.

Reference: OMN-1140
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import the module under test
# We need to add scripts to path since it's not a package
SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from generate_node_report import (
    NodeInfo,
    check_is_stub,
    count_lines,
    find_node_file,
    generate_report,
    get_node_type,
    main,
    scan_all_nodes,
    scan_node,
)


# =============================================================================
# Test Class: get_node_type
# =============================================================================


@pytest.mark.unit
class TestGetNodeType:
    """Tests for get_node_type function."""

    def test_compute_type(self):
        """Test detection of compute node type."""
        assert get_node_type("vectorization_compute") == "compute"
        assert get_node_type("quality_scoring_compute") == "compute"
        assert get_node_type("pattern_learning_compute") == "compute"

    def test_effect_type(self):
        """Test detection of effect node type."""
        assert get_node_type("ingestion_effect") == "effect"
        assert get_node_type("intelligence_api_effect") == "effect"

    def test_orchestrator_type(self):
        """Test detection of orchestrator node type."""
        assert get_node_type("intelligence_orchestrator") == "orchestrator"
        assert get_node_type("workflow_orchestrator") == "orchestrator"

    def test_reducer_type(self):
        """Test detection of reducer node type."""
        assert get_node_type("intelligence_reducer") == "reducer"
        assert get_node_type("state_reducer") == "reducer"

    def test_adapter_is_effect(self):
        """Test that adapter nodes are classified as effect type."""
        assert get_node_type("intelligence_adapter") == "effect"
        assert get_node_type("kafka_adapter") == "effect"

    def test_unknown_type(self):
        """Test detection of unknown node type."""
        assert get_node_type("some_node") == "unknown"
        assert get_node_type("helper_module") == "unknown"
        assert get_node_type("utils") == "unknown"


# =============================================================================
# Test Class: check_is_stub
# =============================================================================


@pytest.mark.unit
class TestCheckIsStub:
    """Tests for check_is_stub function."""

    def test_stub_node_detected(self, tmp_path: Path):
        """Test detection of stub node with ClassVar marker."""
        node_file = tmp_path / "node.py"
        node_file.write_text('''
from typing import ClassVar

class NodeTestCompute:
    """Test compute node."""

    is_stub: ClassVar[bool] = True

    def execute(self):
        pass
''')
        assert check_is_stub(node_file) is True

    def test_non_stub_node(self, tmp_path: Path):
        """Test non-stub node without is_stub marker."""
        node_file = tmp_path / "node.py"
        node_file.write_text('''
from typing import ClassVar

class NodeTestCompute:
    """Test compute node."""

    def execute(self):
        return "result"
''')
        assert check_is_stub(node_file) is False

    def test_stub_marker_false(self, tmp_path: Path):
        """Test node with is_stub = False is not detected as stub."""
        node_file = tmp_path / "node.py"
        node_file.write_text('''
from typing import ClassVar

class NodeTestCompute:
    """Test compute node."""

    is_stub: ClassVar[bool] = False

    def execute(self):
        return "result"
''')
        assert check_is_stub(node_file) is False

    def test_malformed_python_returns_false(self, tmp_path: Path):
        """Test that malformed Python returns False instead of raising."""
        node_file = tmp_path / "node.py"
        node_file.write_text('''
this is not valid python
def broken(:
''')
        assert check_is_stub(node_file) is False

    def test_nonexistent_file_returns_false(self, tmp_path: Path):
        """Test that nonexistent file returns False."""
        node_file = tmp_path / "nonexistent.py"
        assert check_is_stub(node_file) is False


# =============================================================================
# Test Class: count_lines
# =============================================================================


@pytest.mark.unit
class TestCountLines:
    """Tests for count_lines function."""

    def test_count_lines_basic(self, tmp_path: Path):
        """Test basic line counting."""
        file_path = tmp_path / "test.py"
        file_path.write_text("line1\nline2\nline3\n")
        assert count_lines(file_path) == 3  # splitlines() doesn't count trailing newline

    def test_count_lines_empty_file(self, tmp_path: Path):
        """Test counting lines in empty file."""
        file_path = tmp_path / "empty.py"
        file_path.write_text("")
        assert count_lines(file_path) == 0

    def test_count_lines_single_line(self, tmp_path: Path):
        """Test counting single line file."""
        file_path = tmp_path / "single.py"
        file_path.write_text("single line")
        assert count_lines(file_path) == 1

    def test_count_lines_nonexistent_file(self, tmp_path: Path):
        """Test counting lines in nonexistent file returns 0."""
        file_path = tmp_path / "nonexistent.py"
        assert count_lines(file_path) == 0


# =============================================================================
# Test Class: find_node_file
# =============================================================================


@pytest.mark.unit
class TestFindNodeFile:
    """Tests for find_node_file function."""

    def test_find_node_py(self, tmp_path: Path):
        """Test finding node.py file."""
        node_dir = tmp_path / "test_compute"
        node_dir.mkdir()
        node_file = node_dir / "node.py"
        node_file.write_text("# node content")

        result = find_node_file(node_dir)
        assert result == node_file

    def test_find_node_pattern_file(self, tmp_path: Path):
        """Test finding node_*.py pattern file when node.py doesn't exist."""
        node_dir = tmp_path / "test_compute"
        node_dir.mkdir()
        # Use a name that doesn't start with "node_test" since those are filtered out
        node_file = node_dir / "node_compute_impl.py"
        node_file.write_text("# node content")

        result = find_node_file(node_dir)
        assert result == node_file

    def test_node_py_takes_precedence(self, tmp_path: Path):
        """Test that node.py takes precedence over node_*.py."""
        node_dir = tmp_path / "test_compute"
        node_dir.mkdir()
        node_py = node_dir / "node.py"
        node_py.write_text("# main node")
        node_pattern = node_dir / "node_test_compute.py"
        node_pattern.write_text("# pattern node")

        result = find_node_file(node_dir)
        assert result == node_py

    def test_ignores_node_test_files(self, tmp_path: Path):
        """Test that node_test*.py files are ignored."""
        node_dir = tmp_path / "test_compute"
        node_dir.mkdir()
        test_file = node_dir / "node_test_compute.py"
        test_file.write_text("# test file")

        # Only node_test* file exists, should find it since it doesn't START with node_test
        # but contains "node_" prefix. Let's verify the actual behavior.
        result = find_node_file(node_dir)
        # The file node_test_compute.py starts with "node_test", so it should be ignored
        assert result is None

    def test_no_node_file_found(self, tmp_path: Path):
        """Test when no node file exists."""
        node_dir = tmp_path / "test_compute"
        node_dir.mkdir()
        (node_dir / "models.py").write_text("# models")
        (node_dir / "__init__.py").write_text("")

        result = find_node_file(node_dir)
        assert result is None


# =============================================================================
# Test Class: scan_node
# =============================================================================


@pytest.mark.unit
class TestScanNode:
    """Tests for scan_node function."""

    def test_scan_pure_shell_node(self, tmp_path: Path):
        """Test scanning a pure shell node (< 100 lines)."""
        node_dir = tmp_path / "test_compute"
        node_dir.mkdir()

        # Create a small node file
        node_file = node_dir / "node.py"
        node_file.write_text("# Small node\nclass Node:\n    pass\n")

        # Create contract
        (node_dir / "contract.yaml").write_text("name: test")

        # Create models directory
        (node_dir / "models").mkdir()

        result = scan_node(node_dir)

        assert result.name == "test_compute"
        assert result.node_type == "compute"
        assert result.line_count == 3  # splitlines() doesn't count trailing newline
        assert result.is_stub is False
        assert result.has_contract is True
        assert result.has_models is True
        assert result.has_handlers is False
        assert result.status == "Pure Shell"

    def test_scan_stub_node(self, tmp_path: Path):
        """Test scanning a stub node."""
        node_dir = tmp_path / "test_effect"
        node_dir.mkdir()

        node_file = node_dir / "node.py"
        node_file.write_text('''
from typing import ClassVar

class NodeTestEffect:
    is_stub: ClassVar[bool] = True
''')

        result = scan_node(node_dir)

        assert result.name == "test_effect"
        assert result.node_type == "effect"
        assert result.is_stub is True
        assert result.status == "Stub"

    def test_scan_large_node_needs_extraction(self, tmp_path: Path):
        """Test scanning a large node that needs handler extraction."""
        node_dir = tmp_path / "large_orchestrator"
        node_dir.mkdir()

        # Create a large node file (> 100 lines)
        lines = ["# Line " + str(i) for i in range(150)]
        node_file = node_dir / "node.py"
        node_file.write_text("\n".join(lines))

        result = scan_node(node_dir)

        assert result.name == "large_orchestrator"
        assert result.node_type == "orchestrator"
        assert result.line_count == 150
        assert result.is_stub is False
        assert result.status == "Needs Handler Extraction"

    def test_scan_node_with_handlers(self, tmp_path: Path):
        """Test scanning a node with handlers directory."""
        node_dir = tmp_path / "test_compute"
        node_dir.mkdir()
        (node_dir / "handlers").mkdir()
        (node_dir / "node.py").write_text("# node")

        result = scan_node(node_dir)

        assert result.has_handlers is True

    def test_scan_node_with_models_py(self, tmp_path: Path):
        """Test scanning a node with models.py file."""
        node_dir = tmp_path / "test_reducer"
        node_dir.mkdir()
        (node_dir / "models.py").write_text("# models")
        (node_dir / "node.py").write_text("# node")

        result = scan_node(node_dir)

        assert result.has_models is True
        assert result.node_type == "reducer"

    def test_scan_node_missing_node_file(self, tmp_path: Path):
        """Test scanning a node directory without node file."""
        node_dir = tmp_path / "empty_compute"
        node_dir.mkdir()
        (node_dir / "__init__.py").write_text("")

        result = scan_node(node_dir)

        assert result.name == "empty_compute"
        assert result.node_type == "compute"
        assert result.line_count == 0
        assert result.is_stub is False
        assert result.node_file_path is None
        assert result.status == "Missing Node File"


# =============================================================================
# Test Class: scan_all_nodes
# =============================================================================


@pytest.mark.unit
class TestScanAllNodes:
    """Tests for scan_all_nodes function."""

    def test_scan_multiple_nodes(self, tmp_path: Path):
        """Test scanning multiple node directories."""
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create multiple node directories
        for name in ["alpha_compute", "beta_effect", "gamma_reducer"]:
            node_dir = nodes_dir / name
            node_dir.mkdir()
            (node_dir / "node.py").write_text("# node")

        results = scan_all_nodes(nodes_dir)

        assert len(results) == 3
        names = [r.name for r in results]
        assert "alpha_compute" in names
        assert "beta_effect" in names
        assert "gamma_reducer" in names

    def test_scan_skips_underscore_directories(self, tmp_path: Path):
        """Test that directories starting with underscore are skipped."""
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create node directories
        (nodes_dir / "valid_compute").mkdir()
        (nodes_dir / "valid_compute" / "node.py").write_text("# node")
        (nodes_dir / "_private").mkdir()
        (nodes_dir / "__pycache__").mkdir()

        results = scan_all_nodes(nodes_dir)

        assert len(results) == 1
        assert results[0].name == "valid_compute"

    def test_scan_empty_directory(self, tmp_path: Path):
        """Test scanning empty nodes directory."""
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        results = scan_all_nodes(nodes_dir)

        assert len(results) == 0

    def test_scan_skips_files(self, tmp_path: Path):
        """Test that regular files are skipped."""
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create a node directory and a regular file
        (nodes_dir / "valid_compute").mkdir()
        (nodes_dir / "valid_compute" / "node.py").write_text("# node")
        (nodes_dir / "README.md").write_text("# readme")

        results = scan_all_nodes(nodes_dir)

        assert len(results) == 1

    def test_scan_returns_sorted_results(self, tmp_path: Path):
        """Test that results are sorted by name."""
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create directories in non-alphabetical order
        for name in ["zebra_compute", "alpha_effect", "middle_reducer"]:
            node_dir = nodes_dir / name
            node_dir.mkdir()
            (node_dir / "node.py").write_text("# node")

        results = scan_all_nodes(nodes_dir)

        names = [r.name for r in results]
        assert names == ["alpha_effect", "middle_reducer", "zebra_compute"]


# =============================================================================
# Test Class: generate_report
# =============================================================================


@pytest.mark.unit
class TestGenerateReport:
    """Tests for generate_report function."""

    def test_generate_report_basic(self):
        """Test basic report generation."""
        nodes = [
            NodeInfo(
                name="test_compute",
                node_type="compute",
                line_count=50,
                is_stub=False,
                has_handlers=False,
                has_contract=True,
                has_models=True,
                node_file_path="nodes/test_compute/node.py",
                status="Pure Shell",
            )
        ]

        report = generate_report(nodes)

        assert "# Node Status Report" in report
        assert "## Summary" in report
        assert "test_compute" in report
        assert "Pure Shell" in report
        assert "Compute" in report  # Type is title-cased

    def test_generate_report_with_violations(self):
        """Test report generation with purity violations."""
        nodes = [
            NodeInfo(
                name="large_compute",
                node_type="compute",
                line_count=200,
                is_stub=False,
                has_handlers=False,
                has_contract=True,
                has_models=True,
                node_file_path="nodes/large_compute/node.py",
                status="Needs Handler Extraction",
            )
        ]

        report = generate_report(nodes)

        assert "## Purity Violations" in report
        assert "large_compute" in report
        assert "200" in report
        assert "**NEEDS EXTRACTION**" in report
        assert "handler extraction" in report.lower()

    def test_generate_report_no_violations(self):
        """Test report generation with no violations shows success message."""
        nodes = [
            NodeInfo(
                name="test_compute",
                node_type="compute",
                line_count=50,
                is_stub=False,
                has_handlers=True,
                has_contract=True,
                has_models=True,
                node_file_path="nodes/test_compute/node.py",
                status="Pure Shell",
            )
        ]

        report = generate_report(nodes)

        assert "No purity violations detected" in report

    def test_generate_report_with_stubs(self):
        """Test report generation with stub nodes."""
        nodes = [
            NodeInfo(
                name="stub_effect",
                node_type="effect",
                line_count=30,
                is_stub=True,
                has_handlers=False,
                has_contract=True,
                has_models=False,
                node_file_path="nodes/stub_effect/node.py",
                status="Stub",
            )
        ]

        report = generate_report(nodes)

        assert "Stub" in report
        assert "Effect" in report

    def test_generate_report_missing_node_file(self):
        """Test report generation for node with missing file."""
        nodes = [
            NodeInfo(
                name="empty_reducer",
                node_type="reducer",
                line_count=0,
                is_stub=False,
                has_handlers=False,
                has_contract=False,
                has_models=False,
                node_file_path=None,
                status="Missing Node File",
            )
        ]

        report = generate_report(nodes)

        assert "## Missing Node Files" in report
        assert "empty_reducer" in report
        assert "*Missing*" in report

    def test_generate_report_type_distribution(self):
        """Test report includes type distribution."""
        nodes = [
            NodeInfo(
                name="node1",
                node_type="compute",
                line_count=50,
                is_stub=False,
                has_handlers=False,
                has_contract=True,
                has_models=True,
                node_file_path="nodes/node1/node.py",
                status="Pure Shell",
            ),
            NodeInfo(
                name="node2",
                node_type="compute",
                line_count=50,
                is_stub=False,
                has_handlers=False,
                has_contract=True,
                has_models=True,
                node_file_path="nodes/node2/node.py",
                status="Pure Shell",
            ),
            NodeInfo(
                name="node3",
                node_type="effect",
                line_count=50,
                is_stub=False,
                has_handlers=False,
                has_contract=True,
                has_models=True,
                node_file_path="nodes/node3/node.py",
                status="Pure Shell",
            ),
        ]

        report = generate_report(nodes)

        assert "### Node Type Distribution" in report
        assert "| Compute | 2 |" in report
        assert "| Effect | 1 |" in report

    def test_generate_report_recommendations(self):
        """Test report includes recommendations."""
        nodes = [
            NodeInfo(
                name="no_contract_node",
                node_type="compute",
                line_count=50,
                is_stub=False,
                has_handlers=False,
                has_contract=False,  # Missing contract
                has_models=True,
                node_file_path="nodes/no_contract_node/node.py",
                status="Pure Shell",
            )
        ]

        report = generate_report(nodes)

        assert "## Recommendations" in report
        assert "missing contracts" in report.lower()

    def test_generate_report_empty_nodes(self):
        """Test report generation with empty node list."""
        nodes = []

        report = generate_report(nodes)

        assert "# Node Status Report" in report
        assert "**Total** | **0**" in report
        assert "No purity violations detected" in report

    def test_generate_report_legend(self):
        """Test report includes legend."""
        nodes = []

        report = generate_report(nodes)

        assert "## Legend" in report
        assert "Pure Shell" in report
        assert "Stub" in report
        assert "Needs Handler Extraction" in report


# =============================================================================
# Test Class: main function
# =============================================================================


@pytest.mark.unit
class TestMain:
    """Tests for main entry point."""

    def test_main_success(self, tmp_path: Path):
        """Test main function with valid nodes directory."""
        # Create nodes directory structure
        nodes_dir = tmp_path / "src" / "omniintelligence" / "nodes"
        nodes_dir.mkdir(parents=True)

        # Create a node
        node_dir = nodes_dir / "test_compute"
        node_dir.mkdir()
        (node_dir / "node.py").write_text("# node")

        # Create output directory
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()

        # Create a mock script directory
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()

        with patch("generate_node_report.Path") as mock_path_class:
            # Mock __file__ to point to our temp structure
            mock_file = MagicMock()
            mock_file.parent = script_dir
            mock_path_class.__file__ = str(script_dir / "generate_node_report.py")

            # Use real Path for actual operations
            mock_path_class.side_effect = Path
            mock_path_class.return_value = Path()

            with patch("sys.argv", ["generate_node_report.py",
                                    "--nodes-dir", str(nodes_dir),
                                    "--output", str(docs_dir / "report.md")]):
                # Patch __file__ in the module
                with patch("generate_node_report.__file__", str(script_dir / "generate_node_report.py")):
                    exit_code = main()

        assert exit_code == 0

    def test_main_nodes_directory_not_found(self, tmp_path: Path, capsys):
        """Test main function when nodes directory doesn't exist."""
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()

        nonexistent = tmp_path / "nonexistent" / "nodes"

        with patch("sys.argv", ["generate_node_report.py",
                                "--nodes-dir", str(nonexistent)]):
            with patch("generate_node_report.__file__", str(script_dir / "generate_node_report.py")):
                exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out or "not found" in captured.out.lower()

    def test_main_creates_output_directory(self, tmp_path: Path):
        """Test that main creates output directory if it doesn't exist."""
        # Create nodes directory
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()
        node_dir = nodes_dir / "test_compute"
        node_dir.mkdir()
        (node_dir / "node.py").write_text("# node")

        script_dir = tmp_path / "scripts"
        script_dir.mkdir()

        # Output directory doesn't exist
        output_file = tmp_path / "new_docs" / "report.md"

        with patch("sys.argv", ["generate_node_report.py",
                                "--nodes-dir", str(nodes_dir),
                                "--output", str(output_file)]):
            with patch("generate_node_report.__file__", str(script_dir / "generate_node_report.py")):
                exit_code = main()

        assert exit_code == 0
        assert output_file.exists()
        assert output_file.parent.exists()

    def test_main_default_arguments(self, tmp_path: Path):
        """Test main function with default arguments structure."""
        # This tests that argparse is set up correctly
        with patch("sys.argv", ["generate_node_report.py", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        # --help exits with code 0
        assert exc_info.value.code == 0


# =============================================================================
# Test Class: NodeInfo Dataclass
# =============================================================================


@pytest.mark.unit
class TestNodeInfo:
    """Tests for NodeInfo dataclass."""

    def test_node_info_creation(self):
        """Test NodeInfo dataclass creation."""
        node = NodeInfo(
            name="test_compute",
            node_type="compute",
            line_count=100,
            is_stub=False,
            has_handlers=True,
            has_contract=True,
            has_models=True,
            node_file_path="nodes/test_compute/node.py",
            status="Pure Shell",
        )

        assert node.name == "test_compute"
        assert node.node_type == "compute"
        assert node.line_count == 100
        assert node.is_stub is False
        assert node.has_handlers is True
        assert node.has_contract is True
        assert node.has_models is True
        assert node.node_file_path == "nodes/test_compute/node.py"
        assert node.status == "Pure Shell"

    def test_node_info_with_none_path(self):
        """Test NodeInfo with None node_file_path."""
        node = NodeInfo(
            name="empty_node",
            node_type="unknown",
            line_count=0,
            is_stub=False,
            has_handlers=False,
            has_contract=False,
            has_models=False,
            node_file_path=None,
            status="Missing Node File",
        )

        assert node.node_file_path is None
        assert node.status == "Missing Node File"


# =============================================================================
# Test Class: Edge Cases
# =============================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_scan_node_with_deeply_nested_structure(self, tmp_path: Path):
        """Test scanning node with deeply nested directory structure."""
        # Create a deeply nested structure
        base = tmp_path / "nodes"
        base.mkdir()
        node_dir = base / "nested_compute"
        node_dir.mkdir()

        # Create nested handlers
        handlers = node_dir / "handlers" / "sub" / "deep"
        handlers.mkdir(parents=True)
        (handlers / "handler.py").write_text("# handler")

        # Create node file
        (node_dir / "node.py").write_text("# node")

        result = scan_node(node_dir)

        assert result.has_handlers is True

    def test_scan_node_unicode_content(self, tmp_path: Path):
        """Test scanning node with unicode content."""
        node_dir = tmp_path / "unicode_compute"
        node_dir.mkdir()

        node_file = node_dir / "node.py"
        node_file.write_text('# Unicode: \u4e2d\u6587 \u0440\u0443\u0441\u0441\u043a\u0438\u0439\nclass Node:\n    pass\n')

        result = scan_node(node_dir)

        assert result.line_count == 3  # splitlines() doesn't count trailing newline
        assert result.name == "unicode_compute"

    def test_scan_node_symlinks(self, tmp_path: Path):
        """Test scanning node directories that are symlinks."""
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create actual node directory
        actual_dir = tmp_path / "actual_compute"
        actual_dir.mkdir()
        (actual_dir / "node.py").write_text("# node")

        # Create symlink in nodes directory
        link_dir = nodes_dir / "link_compute"
        try:
            link_dir.symlink_to(actual_dir)
        except OSError:
            pytest.skip("Symlinks not supported on this platform")

        results = scan_all_nodes(nodes_dir)

        # Symlink should be followed and scanned
        assert len(results) == 1
        assert results[0].name == "link_compute"

    def test_report_with_all_status_types(self):
        """Test report generation with all possible status types."""
        nodes = [
            NodeInfo(
                name="pure_shell",
                node_type="compute",
                line_count=50,
                is_stub=False,
                has_handlers=False,
                has_contract=True,
                has_models=True,
                node_file_path="nodes/pure_shell/node.py",
                status="Pure Shell",
            ),
            NodeInfo(
                name="stub_node",
                node_type="effect",
                line_count=30,
                is_stub=True,
                has_handlers=False,
                has_contract=True,
                has_models=False,
                node_file_path="nodes/stub_node/node.py",
                status="Stub",
            ),
            NodeInfo(
                name="needs_extraction",
                node_type="orchestrator",
                line_count=200,
                is_stub=False,
                has_handlers=False,
                has_contract=True,
                has_models=True,
                node_file_path="nodes/needs_extraction/node.py",
                status="Needs Handler Extraction",
            ),
            NodeInfo(
                name="missing_file",
                node_type="reducer",
                line_count=0,
                is_stub=False,
                has_handlers=False,
                has_contract=False,
                has_models=False,
                node_file_path=None,
                status="Missing Node File",
            ),
        ]

        report = generate_report(nodes)

        # All statuses should be represented in summary table (uses plural forms)
        assert "Pure Shells | 1" in report
        assert "Stubs | 1" in report
        assert "Needs Handler Extraction | 1" in report
        assert "Missing Node File | 1" in report
        assert "**Total** | **4**" in report

    def test_large_line_count_formatting(self):
        """Test that large line counts are formatted with commas."""
        nodes = [
            NodeInfo(
                name="huge_node",
                node_type="compute",
                line_count=12345,
                is_stub=False,
                has_handlers=False,
                has_contract=True,
                has_models=True,
                node_file_path="nodes/huge_node/node.py",
                status="Needs Handler Extraction",
            )
        ]

        report = generate_report(nodes)

        # Line count should be formatted with comma
        assert "12,345 lines" in report

    def test_boundary_line_counts(self, tmp_path: Path):
        """Test nodes at exactly 100 lines boundary."""
        node_dir = tmp_path / "boundary_compute"
        node_dir.mkdir()

        # Exactly 100 lines (should be Pure Shell, <= 100)
        lines = ["# line"] * 100
        node_file = node_dir / "node.py"
        node_file.write_text("\n".join(lines))

        result = scan_node(node_dir)

        assert result.line_count == 100
        assert result.status == "Pure Shell"

    def test_boundary_101_lines(self, tmp_path: Path):
        """Test node with 101 lines (should need extraction)."""
        node_dir = tmp_path / "over_boundary_compute"
        node_dir.mkdir()

        # 101 lines (should be Needs Handler Extraction, > 100)
        lines = ["# line"] * 101
        node_file = node_dir / "node.py"
        node_file.write_text("\n".join(lines))

        result = scan_node(node_dir)

        assert result.line_count == 101
        assert result.status == "Needs Handler Extraction"


# =============================================================================
# Test Class: Integration-style Unit Tests
# =============================================================================


@pytest.mark.unit
class TestIntegrationStyle:
    """Integration-style tests that test multiple components together."""

    def test_full_scan_to_report_flow(self, tmp_path: Path):
        """Test full flow from scanning nodes to generating report."""
        # Create a realistic nodes directory structure
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        # Create various node types
        for node_name, content, has_contract, has_handlers in [
            ("quality_scoring_compute", "# small\nclass Node: pass\n", True, False),
            ("ingestion_effect", "from typing import ClassVar\nclass Node:\n    is_stub: ClassVar[bool] = True\n", True, False),
            ("intelligence_orchestrator", "\n".join(["# line"] * 150), False, True),
            ("state_reducer", "", True, True),  # Empty = missing node file scenario
        ]:
            node_dir = nodes_dir / node_name
            node_dir.mkdir()

            if content:
                (node_dir / "node.py").write_text(content)

            if has_contract:
                (node_dir / "contract.yaml").write_text("name: test")

            if has_handlers:
                (node_dir / "handlers").mkdir()

        # Scan all nodes
        results = scan_all_nodes(nodes_dir)

        # Generate report
        report = generate_report(results)

        # Verify report content
        assert len(results) == 4
        assert "quality_scoring_compute" in report
        assert "ingestion_effect" in report
        assert "intelligence_orchestrator" in report
        assert "state_reducer" in report

        # Check summary statistics
        assert "Pure Shell" in report
        assert "Stub" in report
        assert "Needs Handler Extraction" in report

    def test_round_trip_through_main(self, tmp_path: Path, capsys):
        """Test complete round trip through main function."""
        # Setup directory structure
        nodes_dir = tmp_path / "nodes"
        nodes_dir.mkdir()

        node_dir = nodes_dir / "test_compute"
        node_dir.mkdir()
        (node_dir / "node.py").write_text("# test node\nclass Node:\n    pass\n")
        (node_dir / "contract.yaml").write_text("name: test")

        output_file = tmp_path / "output" / "report.md"
        script_dir = tmp_path / "scripts"
        script_dir.mkdir()

        with patch("sys.argv", ["generate_node_report.py",
                                "--nodes-dir", str(nodes_dir),
                                "--output", str(output_file)]):
            with patch("generate_node_report.__file__", str(script_dir / "generate_node_report.py")):
                exit_code = main()

        assert exit_code == 0
        assert output_file.exists()

        # Verify report content
        report_content = output_file.read_text()
        assert "test_compute" in report_content
        assert "# Node Status Report" in report_content

        # Verify console output
        captured = capsys.readouterr()
        assert "Found 1 nodes" in captured.out
        assert "Pure Shells: 1" in captured.out
