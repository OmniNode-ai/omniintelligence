# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT
"""Unit tests for change-aware test path detection (OMN-10765)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci.detect_test_paths import compute_selection, resolve_test_paths
from scripts.ci.test_selection_models import EnumFullSuiteReason

ADJACENCY_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "scripts/ci/test_selection_adjacency.yaml"
)


@pytest.mark.unit
class TestResolveTestPaths:
    def test_src_change_maps_to_unit_dir(self) -> None:
        paths = resolve_test_paths(
            ["src/omniintelligence/tools/some_tool.py"],
            ADJACENCY_PATH,
        )
        assert "tests/unit/tools/" in paths

    def test_unit_test_change_included_directly(self) -> None:
        paths = resolve_test_paths(
            ["tests/unit/handlers/test_foo.py"],
            ADJACENCY_PATH,
        )
        assert "tests/unit/handlers/" in paths

    def test_integration_change_ignored(self) -> None:
        paths = resolve_test_paths(
            ["tests/integration/test_db.py"],
            ADJACENCY_PATH,
        )
        assert paths == []

    def test_reverse_deps_expanded(self) -> None:
        # models is in shared_modules so it escalates to full suite in compute_selection,
        # but resolve_test_paths itself just expands reverse deps.
        paths = resolve_test_paths(
            ["src/omniintelligence/handlers/handler_foo.py"],
            ADJACENCY_PATH,
        )
        # handlers -> reverse_deps: [nodes]
        assert "tests/unit/handlers/" in paths
        assert "tests/unit/nodes/" in paths

    def test_unknown_src_module_ignored(self) -> None:
        paths = resolve_test_paths(
            ["src/omniintelligence/nonexistent_module/foo.py"],
            ADJACENCY_PATH,
        )
        assert paths == []


@pytest.mark.unit
class TestComputeSelection:
    def test_feature_flag_off_returns_full_suite(self) -> None:
        sel = compute_selection(
            changed_files=["src/omniintelligence/tools/foo.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="jonah/feature",
            feature_flag_enabled=False,
        )
        assert sel.is_full_suite is True
        assert sel.full_suite_reason == EnumFullSuiteReason.FEATURE_FLAG_OFF

    def test_main_branch_returns_full_suite(self) -> None:
        sel = compute_selection(
            changed_files=["src/omniintelligence/tools/foo.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="main",
        )
        assert sel.is_full_suite is True
        assert sel.full_suite_reason == EnumFullSuiteReason.MAIN_BRANCH

    def test_merge_group_event_returns_full_suite(self) -> None:
        sel = compute_selection(
            changed_files=["src/omniintelligence/tools/foo.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="jonah/feature",
            event_name="merge_group",
        )
        assert sel.is_full_suite is True
        assert sel.full_suite_reason == EnumFullSuiteReason.MERGE_GROUP

    def test_shared_module_change_returns_full_suite(self) -> None:
        sel = compute_selection(
            changed_files=["src/omniintelligence/models/some_model.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="jonah/feature",
        )
        assert sel.is_full_suite is True
        assert sel.full_suite_reason == EnumFullSuiteReason.SHARED_MODULE

    def test_test_infrastructure_change_returns_full_suite(self) -> None:
        sel = compute_selection(
            changed_files=["tests/conftest.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="jonah/feature",
        )
        assert sel.is_full_suite is True
        assert sel.full_suite_reason == EnumFullSuiteReason.TEST_INFRASTRUCTURE

    def test_small_change_returns_smart_selection(self) -> None:
        sel = compute_selection(
            changed_files=["src/omniintelligence/tools/foo.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="jonah/feature",
        )
        assert sel.is_full_suite is False
        assert sel.full_suite_reason is None
        assert "tests/unit/tools/" in sel.selected_paths
        assert sel.split_count >= 1
        assert len(sel.matrix) == sel.split_count

    def test_no_matching_files_falls_back_to_unit_root(self) -> None:
        sel = compute_selection(
            changed_files=["docs/README.md"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="jonah/feature",
        )
        assert sel.is_full_suite is False
        assert sel.selected_paths == ["tests/unit/"]

    def test_matrix_length_matches_split_count(self) -> None:
        sel = compute_selection(
            changed_files=["src/omniintelligence/tools/foo.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="jonah/feature",
        )
        assert len(sel.matrix) == sel.split_count
        assert sel.matrix == list(range(1, sel.split_count + 1))

    def test_output_is_json_serializable(self) -> None:
        sel = compute_selection(
            changed_files=["src/omniintelligence/tools/foo.py"],
            adjacency_path=ADJACENCY_PATH,
            ref_name="jonah/feature",
        )
        data = json.loads(sel.model_dump_json())
        assert "selected_paths" in data
        assert "split_count" in data
        assert "is_full_suite" in data
        assert "matrix" in data


@pytest.mark.unit
class TestAdjacencyMapLoads:
    def test_adjacency_yaml_loads_without_error(self) -> None:
        from scripts.ci.test_selection_loader import load_adjacency_map

        adj = load_adjacency_map(ADJACENCY_PATH)
        assert adj.schema_version == 1
        assert len(adj.adjacency) > 0
        assert len(adj.shared_modules) > 0

    def test_all_shared_modules_in_adjacency(self) -> None:
        from scripts.ci.test_selection_loader import load_adjacency_map

        adj = load_adjacency_map(ADJACENCY_PATH)
        for sm in adj.shared_modules:
            assert sm in adj.adjacency, f"shared_module '{sm}' missing from adjacency"

    def test_all_reverse_deps_reference_known_modules(self) -> None:
        from scripts.ci.test_selection_loader import load_adjacency_map

        adj = load_adjacency_map(ADJACENCY_PATH)
        all_modules = set(adj.adjacency.keys())
        for module, entry in adj.adjacency.items():
            for dep in entry.reverse_deps:
                assert dep in all_modules, (
                    f"adjacency['{module}'].reverse_deps references unknown module '{dep}'"
                )
