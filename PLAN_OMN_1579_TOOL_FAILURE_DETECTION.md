# Plan: OMN-1579 - Implement tool_failure pattern detection

## Overview

Add tool failure pattern detection to the existing `pattern_extraction_compute` node. This implements the `tool_failure` pattern type that was already reserved in `ErrorPatternResult`.

## Key Discovery

The codebase **already anticipated this feature**:
- `protocols.py:201-210` defines `ErrorPatternResult` with `pattern_type: Literal["error_prone_file", "tool_failure", "error_sequence"]`
- Line 205-206 comments: `tool_failure: [PLANNED - see OMN-1579]`
- The existing `convert_error_patterns` converter handles `ErrorPatternResult` → `ModelCodebaseInsight`

**This means**: No new TypedDict needed. Use existing `ErrorPatternResult` with `pattern_type="tool_failure"`.

## Architecture Decision

**Approach**: Extend existing `pattern_extraction_compute` using established patterns.

**What we reuse**:
- `ErrorPatternResult` TypedDict (already has `tool_failure` variant)
- `convert_error_patterns` converter
- `EnumInsightType.ERROR_PATTERN` insight type
- `_EXTRACTORS` registry pattern

**What we add**:
- `ModelToolExecution` model for structured tool execution data
- `tool_executions` field on `ModelSessionSnapshot`
- `extract_tool_failure_patterns` config flag
- `handler_tool_failure_patterns.py` with detection logic

## Critical Design Decisions

### 1. Determinism Requirements

All pattern extraction MUST be deterministic:
- **Stable pattern IDs**: Computed from content hash, NOT `uuid4()`
- **Deterministic ordering**: Results sorted by (pattern_type, tool_name, error_type, confidence desc)
- **Index-based sequence ordering**: Primary ordering = index in `tool_executions` tuple, time is secondary guard only

### 2. Runtime vs Contract Architecture

- `_EXTRACTORS` is the **runtime registry** that controls extraction
- `contract.yaml` **documents capabilities** but does not control runtime routing
- Config-driven toggles come from `ModelExtractionConfig` flags

### 3. Noise Suppression

Every pattern family requires **distinct-session support**:
- Patterns must appear in ≥ `min_distinct_sessions` (default: 2) to be emitted
- Prevents one weird session from dominating results
- Top-K by confidence per pattern type (max 20 per batch)

## Dependencies

### Internal (omniintelligence2)
- `ErrorPatternResult` from `handlers/protocols.py`
- `convert_error_patterns` from `handlers/handler_converters.py`
- `ModelSessionSnapshot` from `models/model_input.py`

### External
- `JsonType` from omnibase_core (for typed JSON instead of `dict[str, Any]`)

### Input Data (from omniclaude)
- Kafka topic suffix: `onex.evt.omniclaude.tool-executed.v1`
- Full topic: `{env}.onex.evt.omniclaude.tool-executed.v1` (composed at runtime)
- Fields: `tool_name`, `success`, `error_message`, `error_type`, `duration_ms`, `tool_parameters`

## Implementation Plan

### Phase 1: Model Updates

#### 1.1 Add ModelToolExecution to `models/model_input.py`

```python
from omnibase_core.types import JsonType  # NOT dict[str, Any]

# TEMP_BOOTSTRAP: Should move to core intelligence input models
# Follow-up ticket: OMN-XXXX
class ModelToolExecution(BaseModel):
    """Single tool execution record for pattern analysis."""

    tool_name: str = Field(..., description="Tool name (Read, Write, Edit, Bash, etc.)")
    success: bool = Field(..., description="Whether the tool execution succeeded")
    error_message: str | None = Field(default=None, description="Error message if failed")
    error_type: str | None = Field(default=None, description="Exception type if failed")
    duration_ms: int | None = Field(default=None, ge=0, description="Execution duration")
    # IMPORTANT: Use JsonType, NOT dict[str, Any]. Default is None, not {}.
    tool_parameters: JsonType | None = Field(default=None, description="Tool input parameters (opaque JSON)")
    timestamp: datetime = Field(..., description="When the tool was executed")

    model_config = {"frozen": True, "extra": "forbid"}
```

#### 1.2 Update ModelSessionSnapshot

```python
class ModelSessionSnapshot(BaseModel):
    # ... existing fields ...
    tool_executions: tuple[ModelToolExecution, ...] = Field(
        default=(),
        description="Structured tool execution records including success/failure. "
                    "ORDER IS AUTHORITATIVE for sequence detection."
    )
```

#### 1.3 Add config flags to ModelExtractionConfig

```python
class ModelExtractionConfig(BaseModel):
    # ... existing flags ...
    extract_tool_failure_patterns: bool = Field(
        default=True,
        description="Extract tool failure patterns from tool_executions"
    )
    min_distinct_sessions: int = Field(
        default=2,
        ge=1,
        description="Minimum distinct sessions a pattern must appear in"
    )
```

### Phase 2: Handler Implementation

#### 2.1 Create `handlers/handler_tool_failure_patterns.py`

```python
"""Tool failure pattern extraction from session data.

Extracts failure patterns from structured tool execution records.
Returns ErrorPatternResult with pattern_type="tool_failure".

Pattern Types Detected:
1. recurring_failure: Same tool + error_type across sessions
2. failure_sequence: Tool A failure followed by Tool B failure
3. context_failure: Failures correlated with file types/paths
4. recovery_pattern: Failure → retry → success/failure
5. failure_hotspot: Directories with high failure rates

CRITICAL DESIGN DECISIONS:
- Pattern IDs are DETERMINISTIC (content hash, NOT uuid4())
- Ordering is INDEX-BASED (tool_executions order is authoritative)
- Time-based checks are SECONDARY guards only
- All patterns require min_distinct_sessions to avoid single-session noise

Ticket: OMN-1579
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Sequence

from omniintelligence.nodes.pattern_extraction_compute.handlers.protocols import (
    ErrorPatternResult,
)
from omniintelligence.nodes.pattern_extraction_compute.models import (
    ModelSessionSnapshot,
)

# Detection bounds (prevents noisy garbage)
SEQUENCE_MAX_TOOL_GAP = 5       # A→B must be within 5 tool calls (index-based)
SEQUENCE_MAX_TIME_GAP_SEC = 60  # Secondary guard: A→B within 60 seconds
RETRY_MAX_TOOL_GAP = 3          # Retry must be within 3 tool calls
MAX_RESULTS_PER_TYPE = 20       # Cap per pattern type to prevent noise

# Hotspot granularity: tool_name + directory (not full file path)
HOTSPOT_GRANULARITY = "tool_directory"  # Options: "directory", "tool_directory"

# Path key normalization (aliases → canonical)
PATH_KEY_ALIASES = {"file_path", "path", "filename", "file"}
CANONICAL_PATH_KEY = "file_path"


def extract_tool_failure_patterns(
    sessions: Sequence[ModelSessionSnapshot],
    min_occurrences: int = 2,
    min_confidence: float = 0.6,
    min_distinct_sessions: int = 2,
) -> list[ErrorPatternResult]:
    """Extract failure patterns from tool executions.

    Returns ErrorPatternResult with pattern_type="tool_failure".
    Results are DETERMINISTICALLY ordered by (pattern_subtype, tool_name, confidence desc).
    """
    results: list[ErrorPatternResult] = []

    # Collect all failures across sessions
    failures = _collect_failures(sessions)

    if not failures:
        return results

    # 1. Recurring failures (same tool + error_type)
    results.extend(_detect_recurring_failures(
        failures, sessions, min_occurrences, min_confidence, min_distinct_sessions
    ))

    # 2. Failure sequences (A fails → B fails within bounds)
    results.extend(_detect_failure_sequences(
        sessions, min_occurrences, min_confidence, min_distinct_sessions
    ))

    # 3. Context-sensitive failures (file type/path correlations)
    results.extend(_detect_context_failures(
        failures, min_occurrences, min_confidence, min_distinct_sessions
    ))

    # 4. Recovery patterns (failure → retry → outcome)
    results.extend(_detect_recovery_patterns(
        sessions, min_occurrences, min_confidence, min_distinct_sessions
    ))

    # 5. Failure hotspots (tool_name + directory level)
    results.extend(_detect_failure_hotspots(
        failures, min_occurrences, min_confidence, min_distinct_sessions
    ))

    # DETERMINISTIC ORDERING: sort by (pattern_subtype, tool_name, confidence desc)
    results.sort(key=lambda r: (
        _get_pattern_subtype(r),
        _get_primary_tool(r),
        -r["confidence"],
    ))

    return results


def _generate_stable_pattern_id(pattern_type: str, *key_components: str) -> str:
    """Generate deterministic pattern ID from content hash.

    NEVER use uuid4() - that breaks determinism.
    """
    content = "|".join([pattern_type, *key_components])
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

#### 2.2 Detection Logic Details

**Recurring Failures** (confidence = explainable math):
```python
def _detect_recurring_failures(...):
    # Group by (tool_name, error_type)
    # confidence = occurrences / total_failures_for_that_tool
    #
    # Store raw components in error_summary for explainability:
    # error_summary = f"{tool_name}:{error_type} - {occurrences}/{tool_total_failures} failures ({prevalence:.0%} of calls)"
    #
    # Pattern ID: hash of (tool_name, error_type)
    pattern_id = _generate_stable_pattern_id("recurring", tool_name, error_type or "unknown")
```

**Failure Sequences** (index-based ordering):
```python
def _detect_failure_sequences(...):
    # CRITICAL: Use index in tool_executions as PRIMARY ordering
    # Time is SECONDARY guard only (handles missing/same timestamps)
    #
    # Single pass per session (O(n)):
    for i, exec in enumerate(session.tool_executions):
        if not exec.success:
            # Look ahead within SEQUENCE_MAX_TOOL_GAP
            for j in range(i + 1, min(i + SEQUENCE_MAX_TOOL_GAP + 1, len(executions))):
                next_exec = executions[j]
                if not next_exec.success:
                    # Secondary time check (if timestamps available)
                    if _within_time_bound(exec, next_exec, SEQUENCE_MAX_TIME_GAP_SEC):
                        record_transition(exec.tool_name, next_exec.tool_name, session.session_id)
```

**Context Features** (stable, normalized):
```python
def _extract_context_features(tool_parameters: JsonType | None) -> dict:
    """Extract STABLE context features. Values in tool_parameters don't affect features."""
    if not tool_parameters or not isinstance(tool_parameters, dict):
        return {"extension": None, "top_level_dir": None, "has_lockfile": False, "param_shape": ""}

    # Normalize path key aliases
    path_value = None
    for key in PATH_KEY_ALIASES:
        if key in tool_parameters:
            path_value = tool_parameters[key]
            break

    # Extract features from path (if found)
    extension = _extract_extension(path_value)  # lowercased, posix-normalized
    top_level_dir = _extract_top_level_dir(path_value)  # first path component
    has_lockfile = _is_lockfile_path(path_value)  # package-lock.json, yarn.lock, etc.

    # param_shape = sorted top-level keys only, capped at 10, no values
    param_keys = sorted(set(tool_parameters.keys()))[:10]
    param_shape = "|".join(param_keys)

    return {"extension": extension, "top_level_dir": top_level_dir,
            "has_lockfile": has_lockfile, "param_shape": param_shape}
```

**Hotspots** (directory-level granularity):
```python
def _detect_failure_hotspots(...):
    # Granularity: tool_name + directory (NOT full file path)
    # This is actionable: "Read fails 80% in /node_modules/"
    #
    # Key = (tool_name, directory_path)  # NOT (tool_name, file_path)
    # directory_path = parent directory of the file, normalized
    hotspot_key = (exec.tool_name, _extract_directory(path_value))
```

**Recovery Patterns** (strict retry definition):
```python
def _detect_recovery_patterns(...):
    # Retry = same tool + same primary param (normalized) + within RETRY_MAX_TOOL_GAP
    #
    # Primary param = first path-like value found in tool_parameters
    # Normalized = lowercase, posix separators
    #
    # Track outcomes:
    # - failure → retry → success = "recovered"
    # - failure → retry → failure = "persistent"
```

### Phase 3: Handler Registration

#### 3.1 Update `handlers/handler_extract_all_patterns.py`

```python
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
    extract_tool_failure_patterns,
)

_EXTRACTORS: list[tuple[str, str, str, _ExtractorFunc, _ConverterFunc]] = [
    # ... existing extractors ...
    (
        "PATTERN-005",
        "extract_tool_failure_patterns",    # Config flag (matches naming convention)
        "tool_failure_patterns_count",      # Metrics field (avoids ambiguity)
        extract_tool_failure_patterns,      # NEW extractor
        convert_error_patterns,             # REUSE existing converter
    ),
]
```

#### 3.2 Update `handlers/__init__.py`

```python
from omniintelligence.nodes.pattern_extraction_compute.handlers.handler_tool_failure_patterns import (
    extract_tool_failure_patterns,
)

__all__ = [
    # ... existing exports ...
    "extract_tool_failure_patterns",
]
```

### Phase 4: Testing

#### 4.1 Add fixtures to `tests/nodes/pattern_extraction_compute/conftest.py`

```python
@pytest.fixture
def tool_execution_success(base_time: datetime) -> ModelToolExecution:
    """Successful tool execution."""
    return ModelToolExecution(
        tool_name="Read",
        success=True,
        duration_ms=45,
        timestamp=base_time,
    )

@pytest.fixture
def tool_execution_failure(base_time: datetime) -> ModelToolExecution:
    """Failed tool execution."""
    return ModelToolExecution(
        tool_name="Read",
        success=False,
        error_message="File not found: /path/to/file",
        error_type="FileNotFoundError",
        duration_ms=12,
        tool_parameters={"file_path": "/path/to/file"},
        timestamp=base_time,
    )

@pytest.fixture
def sessions_with_recurring_failures(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions with same tool+error across multiple sessions."""
    # Create 3+ sessions each with Read + FileNotFoundError
    ...

@pytest.fixture
def sessions_with_failure_sequence(base_time: datetime) -> tuple[ModelSessionSnapshot, ...]:
    """Sessions where Read failure is followed by Edit failure."""
    ...
```

#### 4.2 Add test class to `tests/nodes/pattern_extraction_compute/test_handlers.py`

```python
class TestExtractToolFailurePatterns:
    """Tests for tool failure pattern extraction handler."""

    # Detection tests
    def test_detects_recurring_failures(self, sessions_with_recurring_failures): ...
    def test_detects_failure_sequences(self, sessions_with_failure_sequence): ...
    def test_detects_context_failures(self, sessions_with_extension_failures): ...
    def test_detects_recovery_patterns(self, sessions_with_retries): ...
    def test_detects_failure_hotspots(self, sessions_with_directory_failures): ...

    # Threshold tests
    def test_respects_min_occurrences(self, sessions_with_single_failure): ...
    def test_respects_min_confidence(self, sessions_with_low_confidence): ...
    def test_respects_min_distinct_sessions(self, sessions_single_session_failures): ...

    # Edge cases
    def test_empty_tool_executions_returns_empty(self): ...
    def test_no_failures_returns_empty(self, sessions_all_success): ...
    def test_single_failure_not_pattern(self, single_failure_session): ...

    # === CRITICAL DETERMINISM TESTS (must pass) ===

    def test_stable_pattern_ids(self, sessions_with_failures):
        """Same input produces IDENTICAL pattern_id values."""
        result1 = extract_tool_failure_patterns(sessions, 2, 0.6)
        result2 = extract_tool_failure_patterns(sessions, 2, 0.6)

        ids1 = [r["pattern_id"] for r in result1]
        ids2 = [r["pattern_id"] for r in result2]
        assert ids1 == ids2, "Pattern IDs must be deterministic (no uuid4())"

    def test_deterministic_ordering(self, sessions_with_failures):
        """Results are strictly ordered by (pattern_subtype, tool_name, confidence desc)."""
        result1 = extract_tool_failure_patterns(sessions, 2, 0.6)
        result2 = extract_tool_failure_patterns(sessions, 2, 0.6)

        assert result1 == result2, "Full result list must be identical"

        # Verify ordering invariant
        for i in range(len(result1) - 1):
            curr, next_ = result1[i], result1[i + 1]
            curr_key = (_get_pattern_subtype(curr), _get_primary_tool(curr), -curr["confidence"])
            next_key = (_get_pattern_subtype(next_), _get_primary_tool(next_), -next_["confidence"])
            assert curr_key <= next_key, f"Ordering violated at index {i}"

    def test_param_shape_ignores_values(self, sessions_with_varying_param_values):
        """param_shape feature is based on KEYS only, not values."""
        # Two sessions with same keys but different values should produce same context
        result = extract_tool_failure_patterns(sessions, 2, 0.6)
        # Verify all patterns with same tool+error have same context features
        ...

    # Metadata stability test
    def test_metadata_json_serializable(self, sessions_with_failures):
        """All metadata values are JSON-serializable."""
        import json
        results = extract_tool_failure_patterns(sessions, 2, 0.6)
        for r in results:
            # error_summary should be serializable string
            json.dumps(r["error_summary"])
            # No datetime/UUID objects sneaking in
            for file in r["affected_files"]:
                assert isinstance(file, str)
            for sid in r["evidence_session_ids"]:
                assert isinstance(sid, str)
```

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `models/model_input.py` | MODIFY | Add `ModelToolExecution`, update `ModelSessionSnapshot`, add config flags |
| `handlers/handler_tool_failure_patterns.py` | CREATE | New handler returning `list[ErrorPatternResult]` |
| `handlers/handler_extract_all_patterns.py` | MODIFY | Add to `_EXTRACTORS` registry |
| `handlers/__init__.py` | MODIFY | Export `extract_tool_failure_patterns` |
| `tests/.../conftest.py` | MODIFY | Add failure-related fixtures |
| `tests/.../test_handlers.py` | MODIFY | Add `TestExtractToolFailurePatterns` class |

**Files NOT changed** (reusing existing infrastructure):
- `handlers/protocols.py` - already has `tool_failure` in `ErrorPatternResult`
- `handlers/handler_converters.py` - reuse `convert_error_patterns`
- `models/enum_insight_type.py` - `ERROR_PATTERN` covers this
- `contract.yaml` - documents capabilities, runtime uses `_EXTRACTORS`

## Success Criteria

### Must Pass (blocking)
- [ ] **Stable pattern IDs**: Same input → same `pattern_id` values (no `uuid4()`)
- [ ] **Deterministic ordering**: Results sorted by (pattern_subtype, tool_name, confidence desc)
- [ ] **Index-based sequences**: Uses `tool_executions` order, time is secondary guard
- [ ] Uses existing `ErrorPatternResult` (no new TypedDict)
- [ ] Uses `JsonType | None` for tool_parameters (not `dict[str, Any]`)

### Should Pass (important)
- [ ] All 5 failure pattern types detected correctly
- [ ] Distinct-session requirement enforced (min_distinct_sessions)
- [ ] Hotspots at directory level (not full file path)
- [ ] Context features stable (keys only, normalized paths)
- [ ] Metadata JSON-serializable (no datetime/UUID objects)
- [ ] Existing pattern extraction tests still pass
- [ ] Performance: <100ms for 1000 tool executions

## Follow-up Tickets

- **OMN-XXXX**: Move `ModelToolExecution` to core intelligence input models (remove TEMP_BOOTSTRAP)
- **OMN-XXXX**: Add `EnumPatternKind.TOOL_FAILURE` to SPI if semantic separation needed

## Estimated Scope

- **New code**: ~350 lines (handler + tests)
- **Modified code**: ~60 lines (models, config, registry)
- **Test coverage**: 15-18 new test cases (including 3 critical determinism tests)

## Naming Conventions (for consistency)

| Component | Name | Rationale |
|-----------|------|-----------|
| Handler file | `handler_tool_failure_patterns.py` | Matches pattern type |
| Handler function | `extract_tool_failure_patterns()` | Matches config flag |
| Config flag | `extract_tool_failure_patterns` | Consistent with other `extract_*` flags |
| Metrics field | `tool_failure_patterns_count` | Avoids ambiguity with future non-tool failures |
| Test class | `TestExtractToolFailurePatterns` | Matches handler function |
