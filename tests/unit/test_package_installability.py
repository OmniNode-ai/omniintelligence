# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Package installability validation tests.

Ensures omniintelligence installs cleanly and all handler modules are
importable from a fresh Python environment. This catches:

- Missing __init__.py files at any level of the package hierarchy
- Broken re-exports in handler __init__.py files
- Import-time errors in handler modules (circular imports, missing deps)
- Package metadata issues in pyproject.toml

These tests run without infrastructure (no Kafka, no PostgreSQL) and
validate only that Python can resolve all handler module paths.

Ticket: OMN-1977
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

# =========================================================================
# Constants
# =========================================================================

# Relative to project root; resolved via project_root fixture in tests.
NODES_DIR = Path("src/omniintelligence/nodes")

# All node directories that MUST be importable for HandlerPluginLoader.
# This list is authoritative: if a new node is added, it MUST be listed here.
EXPECTED_NODE_DIRS = [
    "node_claude_hook_event_effect",
    "node_compliance_evaluate_effect",
    "node_context_item_writer_effect",
    "node_crawl_scheduler_effect",
    "node_doc_promotion_reducer",
    "node_doc_staleness_detector_effect",
    "node_document_fetch_effect",
    "node_document_parser_compute",
    "node_enforcement_feedback_effect",
    "node_execution_trace_parser_compute",
    "node_git_repo_crawler_effect",
    "node_intelligence_orchestrator",
    "node_intelligence_reducer",
    "node_intent_classifier_compute",
    "node_intent_drift_detect_compute",
    "node_linear_crawler_effect",
    "node_pattern_assembler_orchestrator",
    "node_pattern_compliance_effect",
    "node_pattern_demotion_effect",
    "node_pattern_extraction_compute",
    "node_pattern_feedback_effect",
    "node_pattern_learning_compute",
    "node_pattern_learning_effect",
    "node_pattern_lifecycle_effect",
    "node_pattern_matching_compute",
    "node_pattern_projection_effect",
    "node_pattern_promotion_effect",
    "node_pattern_storage_effect",
    "node_quality_scoring_compute",
    "node_routing_feedback_effect",
    "node_semantic_analysis_compute",
    "node_success_criteria_matcher_compute",
    "node_watchdog_effect",
]

# Handler functions/classes that HandlerPluginLoader resolves dynamically.
# Each entry: (module_path, attribute_name).
# node_intelligence_orchestrator is excluded (uses workflow_coordination, no handlers/).
HANDLER_ENTRY_POINTS = [
    # --- Compute nodes ---
    (
        "omniintelligence.nodes.node_quality_scoring_compute.handlers",
        "handle_quality_scoring_compute",
    ),
    (
        "omniintelligence.nodes.node_intent_classifier_compute.handlers",
        "handle_intent_classification",
    ),
    (
        "omniintelligence.nodes.node_pattern_extraction_compute.handlers",
        "extract_all_patterns",
    ),
    (
        "omniintelligence.nodes.node_pattern_learning_compute.handlers",
        "HandlerPatternLearning",
    ),
    (
        "omniintelligence.nodes.node_pattern_matching_compute.handlers",
        "handle_pattern_matching_compute",
    ),
    (
        "omniintelligence.nodes.node_semantic_analysis_compute.handlers",
        "handle_semantic_analysis_compute",
    ),
    (
        "omniintelligence.nodes.node_execution_trace_parser_compute.handlers",
        "handle_trace_parsing_compute",
    ),
    (
        "omniintelligence.nodes.node_success_criteria_matcher_compute.handlers",
        "handle_success_criteria_compute",
    ),
    # --- Effect nodes ---
    (
        "omniintelligence.nodes.node_claude_hook_event_effect.handlers",
        "HandlerClaudeHookEvent",
    ),
    (
        "omniintelligence.nodes.node_compliance_evaluate_effect.handlers",
        "handle_compliance_evaluate_command",
    ),
    (
        "omniintelligence.nodes.node_pattern_compliance_effect.handlers",
        "handle_evaluate_compliance",
    ),
    (
        "omniintelligence.nodes.node_pattern_storage_effect.handlers",
        "route_storage_operation",
    ),
    (
        "omniintelligence.nodes.node_pattern_promotion_effect.handlers",
        "check_and_promote_patterns",
    ),
    (
        "omniintelligence.nodes.node_pattern_demotion_effect.handlers",
        "check_and_demote_patterns",
    ),
    (
        "omniintelligence.nodes.node_pattern_feedback_effect.handlers",
        "record_session_outcome",
    ),
    (
        "omniintelligence.nodes.node_pattern_lifecycle_effect.handlers",
        "apply_transition",
    ),
    (
        "omniintelligence.nodes.node_enforcement_feedback_effect.handlers",
        "process_enforcement_feedback",
    ),
    # --- Reducer ---
    (
        "omniintelligence.nodes.node_intelligence_reducer.handlers",
        "handle_pattern_lifecycle_transition",
    ),
    # --- Orchestrator (with handler routing) ---
    (
        "omniintelligence.nodes.node_pattern_assembler_orchestrator.handlers",
        "handle_pattern_assembly_orchestrate",
    ),
    # --- Effect nodes (continued) ---
    (
        "omniintelligence.nodes.node_watchdog_effect.handlers",
        "start_watching",
    ),
    (
        "omniintelligence.nodes.node_watchdog_effect.handlers",
        "stop_watching",
    ),
]


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


@pytest.fixture
def nodes_dir(project_root: Path) -> Path:
    """Get the nodes directory."""
    return project_root / NODES_DIR


# =========================================================================
# Tests
# =========================================================================


@pytest.mark.unit
class TestPackageInstallability:
    """Validate that omniintelligence is installable and importable."""

    def test_top_level_import(self) -> None:
        """Verify 'import omniintelligence' succeeds."""
        mod = importlib.import_module("omniintelligence")
        assert hasattr(mod, "__name__")

    def test_nodes_package_import(self) -> None:
        """Verify 'import omniintelligence.nodes' succeeds."""
        mod = importlib.import_module("omniintelligence.nodes")
        assert hasattr(mod, "__name__")

    @pytest.mark.parametrize("node_dir", EXPECTED_NODE_DIRS)
    def test_node_package_importable(self, node_dir: str) -> None:
        """Verify each node directory is importable as a Python package."""
        module_path = f"omniintelligence.nodes.{node_dir}"
        mod = importlib.import_module(module_path)
        assert hasattr(mod, "__name__")

    @pytest.mark.parametrize("node_dir", EXPECTED_NODE_DIRS)
    def test_node_handlers_importable(self, node_dir: str, nodes_dir: Path) -> None:
        """Verify each node's handlers subpackage is importable.

        Orchestrators that use workflow_coordination instead of handler_routing
        may not have a handlers/ subpackage - these are skipped.
        """
        handlers_dir = nodes_dir / node_dir / "handlers"
        if not handlers_dir.exists():
            pytest.skip(f"{node_dir} has no handlers/ subpackage (likely orchestrator)")

        module_path = f"omniintelligence.nodes.{node_dir}.handlers"
        mod = importlib.import_module(module_path)
        assert hasattr(mod, "__name__")

    @pytest.mark.parametrize("module_path,attr_name", HANDLER_ENTRY_POINTS)
    def test_handler_entry_point_resolvable(
        self, module_path: str, attr_name: str
    ) -> None:
        """Verify HandlerPluginLoader can resolve each handler entry point."""
        mod = importlib.import_module(module_path)
        assert hasattr(mod, attr_name), (
            f"Handler '{attr_name}' not found in '{module_path}'. "
            f"Available: {[a for a in dir(mod) if not a.startswith('_')]}"
        )

    def test_no_legacy_node_directories(self, nodes_dir: Path) -> None:
        """Ensure no legacy (non-node_*) directories pollute the namespace.

        Legacy directories without the 'node_' prefix were removed in OMN-1977.
        This test prevents regression.
        """
        if not nodes_dir.exists():
            pytest.skip(f"Nodes directory not found: {nodes_dir}")

        legacy_dirs = []
        for child in sorted(nodes_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("node_") or child.name == "__pycache__":
                continue
            legacy_dirs.append(child.name)

        if legacy_dirs:
            pytest.fail(
                f"Legacy node directories found (must use 'node_' prefix): "
                f"{legacy_dirs}"
            )

    def test_all_node_dirs_accounted_for(self, nodes_dir: Path) -> None:
        """Ensure EXPECTED_NODE_DIRS matches the actual node directories on disk.

        Catches newly added nodes that haven't been registered in this test.
        """
        if not nodes_dir.exists():
            pytest.skip(f"Nodes directory not found: {nodes_dir}")

        actual_dirs = sorted(
            child.name
            for child in nodes_dir.iterdir()
            if child.is_dir() and child.name.startswith("node_")
        )
        expected = sorted(EXPECTED_NODE_DIRS)

        missing_from_test = set(actual_dirs) - set(expected)
        extra_in_test = set(expected) - set(actual_dirs)

        errors = []
        if missing_from_test:
            errors.append(
                f"Node dirs on disk but not in EXPECTED_NODE_DIRS: {missing_from_test}"
            )
        if extra_in_test:
            errors.append(
                f"Node dirs in EXPECTED_NODE_DIRS but not on disk: {extra_in_test}"
            )

        if errors:
            pytest.fail("\n".join(errors))
