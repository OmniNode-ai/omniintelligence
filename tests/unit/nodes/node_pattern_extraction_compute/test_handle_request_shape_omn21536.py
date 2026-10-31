# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""handle(request) shape of the pattern extraction handlers (OMN-21536).

Every handler module of ``node_pattern_extraction_compute`` holds a handler class whose
``handle`` takes one typed request. Each class returns what the pure function it
delegates to returns, and the node's contract binds the five extractor classes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
import yaml
from omnibase_core.models.contracts.subcontracts.model_validator_subcontract import (
    ModelValidatorSubcontract,
)
from omnibase_core.models.intelligence.model_pattern_extraction_input import (
    ModelPatternExtractionInput as CoreInput,
)
from omnibase_core.validation.checker_handler_shape import check_handler_shape
from omnibase_core.validation.validator_handler_shape import module_facts
from pydantic import BaseModel, ValidationError

from omniintelligence.nodes.node_pattern_extraction_compute.handlers import (
    extract_architecture_patterns,
    extract_error_patterns,
    extract_file_access_patterns,
    extract_tool_patterns,
    insight_identity_key,
    merge_insights,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_architecture_patterns import (
    HandlerArchitecturePatterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_converters import (
    HandlerConverters,
    ModelPatternConversionRequest,
    convert_file_patterns,
    convert_tool_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_core_models import (
    HandlerPatternExtractionCore,
    handle_pattern_extraction_core,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_error_patterns import (
    HandlerErrorPatterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_extract_all_patterns import (
    HandlerExtractAllPatterns,
    extract_all_patterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_file_patterns import (
    HandlerFilePatterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_group_node_families import (
    ModelNodeFamily,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_identity import (
    HandlerInsightIdentity,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_match_pattern import (
    HandlerMatchPattern,
    match_pattern_role,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_merge import (
    HandlerMergeInsights,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_scan_role_occurrences import (
    RoleOccurrence,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_store_node_families import (
    HandlerStoreNodeFamilies,
    node_family_to_pattern_row,
)
from omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_tool_patterns import (
    HandlerToolPatterns,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models import (
    ModelCodebaseInsight,
    ModelPatternExtractionInput,
    ModelPatternRole,
    ModelSessionSnapshot,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_core_extraction_request import (
    ModelCoreExtractionRequest,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_file_pattern_request import (
    ModelFilePatternRequest,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_match_pattern_request import (
    ModelMatchPatternRequest,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_merge_insights_request import (
    ModelMergeInsightsRequest,
)
from omniintelligence.nodes.node_pattern_extraction_compute.models.model_session_pattern_request import (
    ModelSessionPatternRequest,
)

pytestmark = pytest.mark.unit


_VOLATILE = frozenset({"pattern_id", "insight_id"})


def _masked(value: Any) -> Any:
    """The value with the ids a run generates (random UUIDs) removed, for comparison."""
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _masked(v) for k, v in value.items() if k not in _VOLATILE}
    if isinstance(value, (list, tuple)):
        return [_masked(v) for v in value]
    return value


_NODE_DIR = Path(__file__).resolve().parents[4] / (
    "src/omniintelligence/nodes/node_pattern_extraction_compute"
)
_HANDLER_MODULES = (
    "handler_architecture_patterns",
    "handler_converters",
    "handler_core_models",
    "handler_error_patterns",
    "handler_extract_all_patterns",
    "handler_file_patterns",
    "handler_identity",
    "handler_match_pattern",
    "handler_merge",
    "handler_store_node_families",
    "handler_tool_patterns",
)
_BOUND_CLASSES = {
    "extract_patterns": "HandlerExtractAllPatterns",
    "extract_file_patterns": "HandlerFilePatterns",
    "extract_error_patterns": "HandlerErrorPatterns",
    "extract_architecture_patterns": "HandlerArchitecturePatterns",
    "extract_tool_patterns": "HandlerToolPatterns",
    "extract_core_patterns": "HandlerPatternExtractionCore",
}


def _handler_shape_issues(path: Path) -> tuple[str, ...]:
    """The handler_shape validator's issues for one module, from its own contract."""
    contract_text = (
        resources.files("omnibase_core.validation")
        .joinpath("contracts/handler_shape.validation.yaml")
        .read_text(encoding="utf-8")
    )
    contract = ModelValidatorSubcontract.model_validate(
        yaml.safe_load(contract_text)["validation"]
    )
    facts = module_facts(path.as_posix(), path.read_text(encoding="utf-8"))
    return tuple(
        f"{issue.code}: {issue.message}"
        for issue in check_handler_shape(facts, contract.rules)
    )


class TestHandlerShapeValidator:
    @pytest.mark.parametrize("module", _HANDLER_MODULES)
    def test_module_has_no_handler_shape_issue(self, module: str) -> None:
        path = _NODE_DIR / "handlers" / f"{module}.py"
        assert _handler_shape_issues(path) == ()

    def test_validator_reports_a_bare_function_module(self, tmp_path: Path) -> None:
        """Positive control: the same check flags a module of bare functions."""
        bare = tmp_path / "handler_bare.py"
        bare.write_text("def do_it(a, b):\n    return a\n", encoding="utf-8")
        issues = _handler_shape_issues(bare)
        assert len(issues) == 1
        assert issues[0].startswith("module_function_handler")

    def test_contract_binds_the_extractor_classes(self) -> None:
        contract = yaml.safe_load((_NODE_DIR / "contract.yaml").read_text("utf-8"))
        bound = {
            h["operation"]: h["handler"]["class"]
            for h in contract["handler_routing"]["handlers"]
        }
        assert bound == _BOUND_CLASSES
        for entry in contract["handler_routing"]["handlers"]:
            assert entry["handler"]["module"].startswith(
                "omniintelligence.nodes.node_pattern_extraction_compute.handlers.handler_"
            )
            assert "function" not in entry["handler"]


class TestSessionExtractors:
    def test_architecture(
        self,
        sessions_with_architecture_patterns: tuple[ModelSessionSnapshot, ...],
    ) -> None:
        sessions = sessions_with_architecture_patterns
        request = ModelSessionPatternRequest(
            sessions=sessions, min_occurrences=1, min_confidence=0.1
        )
        assert _masked(HandlerArchitecturePatterns().handle(request)) == _masked(
            extract_architecture_patterns(
                sessions, min_occurrences=1, min_confidence=0.1
            )
        )

    def test_error(
        self, sessions_with_errors: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        request = ModelSessionPatternRequest(
            sessions=sessions_with_errors, min_occurrences=1, min_confidence=0.1
        )
        assert _masked(HandlerErrorPatterns().handle(request)) == _masked(
            extract_error_patterns(
                sessions_with_errors, min_occurrences=1, min_confidence=0.1
            )
        )

    def test_tool(
        self, sessions_with_diverse_tools: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        request = ModelSessionPatternRequest(
            sessions=sessions_with_diverse_tools, min_occurrences=1, min_confidence=0.1
        )
        assert _masked(HandlerToolPatterns().handle(request)) == _masked(
            extract_tool_patterns(
                sessions_with_diverse_tools, min_occurrences=1, min_confidence=0.1
            )
        )

    def test_file_with_explicit_thresholds(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        request = ModelFilePatternRequest(
            sessions=multiple_sessions, min_occurrences=2, min_confidence=0.3
        )
        expected = extract_file_access_patterns(
            multiple_sessions, min_occurrences=2, min_confidence=0.3
        )
        assert expected
        assert _masked(HandlerFilePatterns().handle(request)) == _masked(expected)

    def test_file_request_keeps_the_function_default_threshold(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        request = ModelFilePatternRequest(sessions=multiple_sessions)
        assert request.min_occurrences == 5
        assert _masked(HandlerFilePatterns().handle(request)) == _masked(
            extract_file_access_patterns(multiple_sessions)
        )

    def test_session_request_defaults(self) -> None:
        request = ModelSessionPatternRequest(sessions=())
        assert request.min_occurrences == 2
        assert request.min_confidence == 0.6
        assert request.min_distinct_sessions == 2
        assert request.max_results_per_type == 20

    def test_request_is_frozen_and_rejects_unknown_fields(self) -> None:
        request = ModelSessionPatternRequest(sessions=())
        with pytest.raises(ValidationError):
            request.min_occurrences = 9
        with pytest.raises(ValidationError):
            ModelSessionPatternRequest.model_validate({"sessions": (), "unknown": 1})


class TestExtractAll:
    def test_matches_the_function(
        self, multiple_sessions: tuple[ModelSessionSnapshot, ...]
    ) -> None:
        request = ModelPatternExtractionInput(session_snapshots=multiple_sessions)
        handled = HandlerExtractAllPatterns().handle(request)
        direct = extract_all_patterns(request)
        assert _masked(handled.new_insights) == _masked(direct.new_insights)
        assert handled.success == direct.success


class TestConverters:
    def test_converts_each_kind(
        self,
        multiple_sessions: tuple[ModelSessionSnapshot, ...],
        sessions_with_diverse_tools: tuple[ModelSessionSnapshot, ...],
    ) -> None:
        reference_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)
        files = extract_file_access_patterns(
            multiple_sessions, min_occurrences=2, min_confidence=0.3
        )
        tools = extract_tool_patterns(
            sessions_with_diverse_tools, min_occurrences=1, min_confidence=0.1
        )
        request = ModelPatternConversionRequest(
            file_patterns=files, tool_patterns=tools, reference_time=reference_time
        )
        response = HandlerConverters().handle(request)
        assert list(response.file_insights) == convert_file_patterns(
            files, reference_time
        )
        assert list(response.tool_insights) == convert_tool_patterns(
            tools, reference_time
        )
        assert response.error_insights == ()
        assert response.architecture_insights == ()


class TestInsightHandlers:
    def test_identity(
        self, existing_insights: tuple[ModelCodebaseInsight, ...]
    ) -> None:
        insight = existing_insights[0]
        assert HandlerInsightIdentity().handle(insight) == insight_identity_key(insight)

    def test_merge(self, existing_insights: tuple[ModelCodebaseInsight, ...]) -> None:
        insight = existing_insights[0]
        request = ModelMergeInsightsRequest(new=insight, existing=insight)
        assert HandlerMergeInsights().handle(request) == merge_insights(
            insight, insight
        )


class TestMatchPattern:
    def test_matches_the_function(self) -> None:
        role = ModelPatternRole(
            role_name="compute",
            base_class="NodeCompute",
            distinguishing_mixin="MixinHandlerRouting",
            required=True,
            description="Pure computation",
        )
        request = ModelMatchPatternRequest(role=role, entities=())
        assert HandlerMatchPattern().handle(request) == match_pattern_role(role, [])


class TestStoreNodeFamilies:
    def test_row_matches_the_function(self) -> None:
        occurrence = RoleOccurrence(
            pattern_name="onex-four-node",
            matched_role="effect",
            entity_name="NodePatternStorageEffect",
            qualified_name="omniintelligence.nodes.node_pattern_storage_effect.node.NodePatternStorageEffect",
            file_path="src/omniintelligence/nodes/node_pattern_storage_effect/node.py",
            source_repo="omniintelligence",
            bases=["NodeEffect"],
        )
        family = ModelNodeFamily(
            directory_name="node_pattern_storage_effect",
            directory_path="src/omniintelligence/nodes/node_pattern_storage_effect",
            source_repo="omniintelligence",
            roles=frozenset({"effect"}),
            occurrences=(occurrence,),
        )
        handled = HandlerStoreNodeFamilies().handle(family)
        direct = node_family_to_pattern_row(family)
        assert handled["pattern_signature"] == direct["pattern_signature"]
        assert handled["confidence"] == direct["confidence"]


class TestCoreModels:
    def test_matches_the_function(self) -> None:
        core_input = CoreInput(
            session_ids=["session-1"],
            raw_events=[],
            min_occurrences=1,
            min_confidence=0.1,
        )
        request = ModelCoreExtractionRequest(input_data=core_input)
        assert request.extraction_config is None
        handled = HandlerPatternExtractionCore().handle(request)
        direct = handle_pattern_extraction_core(core_input)
        assert handled.success == direct.success
        assert handled.patterns_by_kind == direct.patterns_by_kind
