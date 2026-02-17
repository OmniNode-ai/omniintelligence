"""Handler for pattern compliance compute node orchestration.

This module bridges the node's typed input/output models and the pure
compliance evaluation functions. It manages timing, error handling,
and LLM client interaction.

The handler:
    - Accepts ModelComplianceRequest (Pydantic model)
    - Calls ProtocolLlmClient for LLM inference
    - Parses the response via handler_compliance functions
    - Returns ModelComplianceResult (Pydantic model)
    - Handles all error cases gracefully (returns structured output)

Ticket: OMN-2256
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Final

from omniintelligence.nodes.node_pattern_compliance_compute.handlers.exceptions import (
    ComplianceLlmError,
    ComplianceParseError,
    ComplianceValidationError,
)
from omniintelligence.nodes.node_pattern_compliance_compute.handlers.handler_compliance import (
    COMPLIANCE_PROMPT_VERSION,
    build_compliance_prompt,
    parse_llm_response,
)
from omniintelligence.nodes.node_pattern_compliance_compute.handlers.protocols import (
    ProtocolLlmClient,
)
from omniintelligence.nodes.node_pattern_compliance_compute.models.model_compliance_request import (
    ModelComplianceRequest,
)
from omniintelligence.nodes.node_pattern_compliance_compute.models.model_compliance_result import (
    ModelComplianceMetadata,
    ModelComplianceResult,
    ModelComplianceViolation,
)

logger = logging.getLogger(__name__)

# Default model identifier for Coder-14B.
DEFAULT_MODEL: Final[str] = "Qwen/Qwen2.5-Coder-14B-Instruct"

# Status constants for metadata.
STATUS_COMPLETED: Final[str] = "completed"
STATUS_VALIDATION_ERROR: Final[str] = "validation_error"
STATUS_LLM_ERROR: Final[str] = "llm_error"
STATUS_PARSE_ERROR: Final[str] = "parse_error"
STATUS_UNKNOWN_ERROR: Final[str] = "unknown_error"

# System prompt for the LLM.
_SYSTEM_PROMPT: Final[str] = (
    "You are a code compliance evaluator. You analyze source code against "
    "a set of patterns and report violations. You respond ONLY with valid JSON, "
    "no markdown fences, no commentary."
)


async def handle_pattern_compliance_compute(
    input_data: ModelComplianceRequest,
    *,
    llm_client: ProtocolLlmClient,
    model: str = DEFAULT_MODEL,
) -> ModelComplianceResult:
    """Handle pattern compliance compute operation.

    Orchestrates the compliance evaluation workflow:
    1. Validates input
    2. Builds the compliance prompt
    3. Calls the LLM via ProtocolLlmClient
    4. Parses the response into violations
    5. Constructs the output model with metadata

    Error Handling:
        - ComplianceValidationError: Returns output with validation_error status
        - ComplianceLlmError: Returns output with llm_error status
        - ComplianceParseError: Returns output with parse_error status
        - All errors are caught and returned as structured output (no exceptions raised)

    Args:
        input_data: Typed input model with code and patterns.
        llm_client: LLM client for inference calls.
        model: Model identifier for LLM (default: Coder-14B).

    Returns:
        ModelComplianceResult with compliance status, violations, and metadata.
        Always returns a valid output, even on errors.
    """
    start_time = time.perf_counter()
    patterns_count = len(input_data.applicable_patterns)

    try:
        return await _execute_compliance(
            input_data, llm_client=llm_client, model=model, start_time=start_time
        )

    except ComplianceValidationError as e:
        processing_time = _safe_elapsed_ms(start_time)
        return _create_error_output(
            status=STATUS_VALIDATION_ERROR,
            message=str(e),
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        )

    except ComplianceLlmError as e:
        processing_time = _safe_elapsed_ms(start_time)
        return _create_error_output(
            status=STATUS_LLM_ERROR,
            message=str(e),
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        )

    except ComplianceParseError as e:
        processing_time = _safe_elapsed_ms(start_time)
        return _create_error_output(
            status=STATUS_PARSE_ERROR,
            message=str(e),
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        )

    except Exception as e:
        processing_time = _safe_elapsed_ms(start_time)

        try:
            logger.exception(
                "Unhandled exception in pattern compliance compute. "
                "file_path=%s, language=%s, processing_time_ms=%.2f",
                getattr(input_data, "file_path", "<unknown>"),
                getattr(input_data, "language", "<unknown>"),
                processing_time,
            )
        except Exception:
            with contextlib.suppress(Exception):
                logger.error("Pattern compliance compute failed: %s", e)

        return _create_error_output(
            status=STATUS_UNKNOWN_ERROR,
            message=f"Unhandled error: {e}",
            processing_time_ms=processing_time,
            patterns_checked=patterns_count,
        )


async def _execute_compliance(
    input_data: ModelComplianceRequest,
    *,
    llm_client: ProtocolLlmClient,
    model: str,
    start_time: float,
) -> ModelComplianceResult:
    """Execute the compliance evaluation logic.

    Args:
        input_data: Typed input model with code and patterns.
        llm_client: LLM client for inference calls.
        model: Model identifier for LLM.
        start_time: Performance counter start time for timing.

    Returns:
        ModelComplianceResult with evaluation results.

    Raises:
        ComplianceValidationError: If input validation fails.
        ComplianceLlmError: If the LLM call fails.
        ComplianceParseError: If the LLM response cannot be parsed.
    """
    # 1. Build prompt
    prompt = build_compliance_prompt(
        content=input_data.content,
        language=input_data.language,
        patterns=list(input_data.applicable_patterns),
    )

    # 2. Call LLM
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]

    try:
        raw_response = await llm_client.chat_completion(
            messages=messages,
            model=model,
            temperature=0.0,
            max_tokens=2048,
        )
    except Exception as e:
        raise ComplianceLlmError(f"LLM inference failed: {e}")

    # 3. Parse response
    parsed = parse_llm_response(
        raw_text=raw_response,
        patterns=list(input_data.applicable_patterns),
    )

    processing_time = (time.perf_counter() - start_time) * 1000

    # 4. Build violations list
    violations = [
        ModelComplianceViolation(
            pattern_id=v["pattern_id"],
            pattern_signature=v["pattern_signature"],
            description=v["description"],
            severity=v["severity"],
            line_reference=v["line_reference"],
        )
        for v in parsed["violations"]
    ]

    return ModelComplianceResult(
        success=True,
        violations=violations,
        compliant=parsed["compliant"],
        confidence=parsed["confidence"],
        metadata=ModelComplianceMetadata(
            status=STATUS_COMPLETED,
            compliance_prompt_version=COMPLIANCE_PROMPT_VERSION,
            model_used=model,
            processing_time_ms=processing_time,
            patterns_checked=len(input_data.applicable_patterns),
        ),
    )


def _create_error_output(
    *,
    status: str,
    message: str,
    processing_time_ms: float,
    patterns_checked: int,
) -> ModelComplianceResult:
    """Create error output with consistent structure.

    Args:
        status: Error status code.
        message: Error message.
        processing_time_ms: Elapsed time in milliseconds.
        patterns_checked: Number of patterns that were to be checked.

    Returns:
        ModelComplianceResult indicating failure.
    """
    return ModelComplianceResult(
        success=False,
        violations=[],
        compliant=False,
        confidence=0.0,
        metadata=ModelComplianceMetadata(
            status=status,
            message=message,
            compliance_prompt_version=COMPLIANCE_PROMPT_VERSION,
            processing_time_ms=processing_time_ms,
            patterns_checked=patterns_checked,
        ),
    )


def _safe_elapsed_ms(start_time: float) -> float:
    """Safely calculate elapsed time in milliseconds.

    Never raises -- returns 0.0 if calculation fails.

    Args:
        start_time: Performance counter start time.

    Returns:
        Elapsed time in milliseconds, or 0.0 on any error.
    """
    try:
        return (time.perf_counter() - start_time) * 1000
    except Exception:
        return 0.0


__all__ = ["handle_pattern_compliance_compute"]
