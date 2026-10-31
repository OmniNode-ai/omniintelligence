# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Canonical dispatch parity with preserved business functions (OMN-21536)."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import BaseModel

from omniintelligence.nodes.node_pattern_compliance_effect.handlers import (
    DEFAULT_MODEL,
    ProtocolLlmClient,
    build_compliance_prompt,
    handle_evaluate_compliance,
    handler_compute,
    parse_llm_response,
)
from omniintelligence.nodes.node_pattern_compliance_effect.models import (
    ModelApplicablePattern,
    ModelComplianceRequest,
)
from tests.unit.nodes.node_pattern_compliance_effect.test_handler_compute import (
    MockKafkaPublisher,
    MockLlmClient,
    MockLlmClientError,
)

pytestmark = pytest.mark.unit

_CORRELATION_ID = UUID("12345678-1234-5678-1234-567812345678")
_OVERRIDE_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
_PATTERN = ModelApplicablePattern(
    pattern_id="P001",
    pattern_signature="Use frozen Pydantic models",
    domain_id="onex",
    confidence=0.9,
)
_INPUT = ModelComplianceRequest(
    correlation_id=_CORRELATION_ID,
    source_path="test.py",
    content="class Foo: pass",
    language="python",
    applicable_patterns=[_PATTERN],
)
_COMPLIANT_RESPONSE = '{"compliant": true, "confidence": 0.9, "violations": []}'
_VIOLATION_RESPONSE = (
    '{"compliant": true, "confidence": 0.8, "violations": '
    '[{"pattern_id": "P001", "description": "Not frozen", "severity": "minor"}]}'
)


def _build_parse_request(
    raw_text: str, patterns: list[ModelApplicablePattern] | None = None
) -> BaseModel:
    from omniintelligence.nodes.node_pattern_compliance_effect.models import (
        ModelComplianceParseRequest,
    )

    if patterns is None:
        return ModelComplianceParseRequest(raw_text=raw_text)
    return ModelComplianceParseRequest(raw_text=raw_text, patterns=patterns)


def _build_evaluate_request(correlation_id: UUID | None = None) -> BaseModel:
    from omniintelligence.nodes.node_pattern_compliance_effect.models import (
        ModelEvaluateComplianceRequest,
    )

    if correlation_id is None:
        return ModelEvaluateComplianceRequest(input_data=_INPUT)
    return ModelEvaluateComplianceRequest(
        input_data=_INPUT, correlation_id=correlation_id
    )


PARITY_CASES: list[tuple[str, Callable[[], BaseModel]]] = [
    (
        "parse_compliant",
        partial(
            _build_parse_request, raw_text=_COMPLIANT_RESPONSE, patterns=[_PATTERN]
        ),
    ),
    (
        "parse_fenced_violation",
        partial(
            _build_parse_request,
            raw_text=(
                '```json\n{"confidence": 2, "violations": '
                '[{"pattern_id": "P001", "severity": "MINOR", '
                '"line_reference": 3}]}\n```'
            ),
            patterns=[_PATTERN],
        ),
    ),
    (
        "parse_empty_fields",
        partial(
            _build_parse_request,
            raw_text='{"violations": [{"pattern_id": "", "description": ""}]}',
        ),
    ),
    ("parse_invalid_json", partial(_build_parse_request, raw_text="not json")),
    ("parse_nonobject", partial(_build_parse_request, raw_text="[]")),
    ("evaluate_compliant", _build_evaluate_request),
    ("evaluate_violation", _build_evaluate_request),
    ("evaluate_parse_error", _build_evaluate_request),
    ("evaluate_llm_error", _build_evaluate_request),
    ("evaluate_no_client", _build_evaluate_request),
    (
        "evaluate_correlation_override",
        partial(_build_evaluate_request, correlation_id=_OVERRIDE_ID),
    ),
]


def _make_client(case_id: str) -> ProtocolLlmClient | None:
    """Create fresh dependencies for each dispatch path, matching sibling fakes."""
    if case_id == "evaluate_no_client":
        return None
    if case_id == "evaluate_llm_error":
        return MockLlmClientError()
    response = {
        "evaluate_violation": _VIOLATION_RESPONSE,
        "evaluate_parse_error": "not json",
    }.get(case_id, _COMPLIANT_RESPONSE)
    return MockLlmClient(response)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "build_request"),
    PARITY_CASES,
    ids=[case_id for case_id, _ in PARITY_CASES],
)
async def test_canonical_dispatch_matches_preserved_core(
    case_id: str,
    build_request: Callable[[], BaseModel],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Typed dispatch preserves outputs, tracing, LLM requests, and DLQ effects."""
    is_parse_case = case_id.startswith("parse_")
    module_name = "omniintelligence.nodes.node_pattern_compliance_effect.handlers." + (
        "handler_compliance" if is_parse_case else "handler_compute"
    )
    class_name = (
        "HandlerComplianceParsing" if is_parse_case else "HandlerEvaluateCompliance"
    )
    module = importlib.import_module(module_name)
    handler_cls = getattr(module, class_name, None)
    assert handler_cls is not None, f"{class_name} is missing from {module_name}"

    from omniintelligence.nodes.node_pattern_compliance_effect.models import (
        ModelComplianceParseRequest,
        ModelEvaluateComplianceRequest,
    )

    parity_request = build_request()
    if isinstance(parity_request, ModelComplianceParseRequest):
        class_request = parity_request.model_copy(deep=True)
        function_request = parity_request.model_copy(deep=True)
        result = handler_cls().handle(class_request)
        expected = parse_llm_response(
            raw_text=function_request.raw_text, patterns=function_request.patterns
        )
        assert result.model_dump() == expected
        return

    assert isinstance(parity_request, ModelEvaluateComplianceRequest)
    monkeypatch.setattr(handler_compute.time, "perf_counter", lambda: 1.0)
    fixed_datetime = Mock(wraps=datetime)
    fixed_datetime.now.return_value = datetime(2025, 1, 1, tzinfo=UTC)
    monkeypatch.setattr(handler_compute, "datetime", fixed_datetime)
    class_request = parity_request.model_copy(deep=True)
    function_request = parity_request.model_copy(deep=True)
    class_client = _make_client(case_id)
    function_client = _make_client(case_id)
    class_producer = MockKafkaPublisher()
    function_producer = MockKafkaPublisher()

    result = await handler_cls(class_client, DEFAULT_MODEL, class_producer).handle(
        class_request
    )
    expected = await handle_evaluate_compliance(
        function_request.input_data,
        llm_client=function_client,
        model=DEFAULT_MODEL,
        correlation_id=function_request.correlation_id,
        kafka_producer=function_producer,
    )

    assert result.model_dump() == expected.model_dump()
    assert result.metadata is not None
    assert result.metadata.correlation_id == (
        parity_request.correlation_id or _CORRELATION_ID
    )
    expected_status = {
        "evaluate_parse_error": "parse_error",
        "evaluate_llm_error": "llm_error",
        "evaluate_no_client": "llm_error",
    }.get(case_id, "completed")
    assert result.metadata.status == expected_status
    assert result.compliant is (
        case_id in {"evaluate_compliant", "evaluate_correlation_override"}
    )
    assert class_producer.published == function_producer.published
    assert len(class_producer.published) == (0 if expected_status == "completed" else 1)
    assert class_request == function_request == parity_request
    if isinstance(class_client, MockLlmClient):
        assert isinstance(function_client, MockLlmClient)
        assert class_client.call_count == function_client.call_count == 1
        assert class_client.last_messages == function_client.last_messages
        assert class_client.last_model == function_client.last_model == DEFAULT_MODEL


@pytest.mark.parametrize("patterns", [[], [_PATTERN]], ids=["empty", "with_pattern"])
def test_build_prompt_matches_preserved_function(
    patterns: list[ModelApplicablePattern],
) -> None:
    """The stateless prompt wrapper preserves empty and populated pattern lists."""
    from omniintelligence.nodes.node_pattern_compliance_effect.handlers import (
        HandlerComplianceParsing,
    )
    from omniintelligence.nodes.node_pattern_compliance_effect.models import (
        ModelCompliancePromptRequest,
    )

    request = ModelCompliancePromptRequest(
        content=_INPUT.content, language=_INPUT.language, patterns=patterns
    )
    assert HandlerComplianceParsing().build_prompt(request) == build_compliance_prompt(
        content=request.content, language=request.language, patterns=request.patterns
    )
