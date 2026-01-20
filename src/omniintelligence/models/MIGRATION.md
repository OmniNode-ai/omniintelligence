# Model Migration Guide: Legacy to Canonical

This document describes the intentional differences between the canonical OmniIntelligence models and the legacy omniarchon models, providing migration guidance for users transitioning from the legacy system.

## Overview

The canonical models in OmniIntelligence represent a **simplified, event-focused** design optimized for Kafka-based communication. The legacy models from omniarchon were comprehensive but designed for direct API responses. The canonical models prioritize:

1. **Simplicity**: Fewer fields, focused on essential data
2. **Event compatibility**: Optimized for Kafka message serialization
3. **Flexibility**: Generic field types that work across operation types
4. **Immutability**: All models use `frozen=True` configuration

## Model Comparison

### ModelIntelligenceOutput

| Field | Legacy Type | Canonical Type | Change Reason |
|-------|-------------|----------------|---------------|
| `success` | `bool` (required) | `bool` (required) | **No change** |
| `operation_type` | `str` (required) | `str` (required) | **No change** |
| `correlation_id` | `UUID` (required) | `Optional[str]` | Simplified to string for JSON serialization; made optional for flexibility |
| `processing_time_ms` | `int` (required) | *Removed* | Moved to event envelope metadata |
| `quality_score` | `Optional[float]` | `Optional[float]` | **No change** |
| `onex_compliance` | `Optional[float]` | `Optional[bool]` (`onex_compliant`) | Simplified from score to boolean compliance flag |
| `complexity_score` | `Optional[float]` | *Removed* | Available in `analysis_results` if needed |
| `issues` | `list[str]` | *Removed* | Merged into `recommendations` |
| `recommendations` | `list[str]` | `list[str]` | **No change** |
| `patterns` | `list[ModelPatternDetection]` | `list[str]` (`patterns_detected`) | Simplified to pattern names only |
| `result_data` | `Optional[dict]` | `dict` (`analysis_results`) | Renamed for clarity; now has default factory |
| `metrics` | `Optional[ModelIntelligenceMetrics]` | *Removed* | Moved to observability layer |
| `error_code` | `Optional[str]` | *Removed* | Use `error_message` for error context |
| `error_message` | `Optional[str]` | `Optional[str]` | **No change** |
| `retry_allowed` | `bool` | *Removed* | Handled by DLQ routing logic |
| `timestamp` | `datetime` | *Removed* | Moved to event envelope |
| `metadata` | `dict` | `dict` | **No change** |

### ModelIntelligenceInput (New in Canonical)

The canonical design introduces a **unified input model** that replaces multiple operation-specific request models from the legacy system.

| Field | Type | Description |
|-------|------|-------------|
| `operation_type` | `str` (required) | Type of intelligence operation |
| `content` | `str` (required) | Content to analyze (source code, document, etc.) |
| `source_path` | `Optional[str]` | Path to source file being analyzed |
| `language` | `str` (default: "python") | Programming language of content |
| `project_name` | `Optional[str]` | Project name for context |
| `options` | `dict` | Operation-specific parameters |
| `correlation_id` | `Optional[str]` | Correlation ID for tracing |
| `metadata` | `dict` | Additional request metadata |

**Legacy Equivalent**: In omniarchon, different operations used different request models:
- `ModelQualityAssessmentRequest`
- `ModelPerformanceAnalysisRequest`
- `ModelPatternDetectionRequest`

The canonical `ModelIntelligenceInput` unifies these into a single model with `operation_type` routing and `options` for operation-specific parameters.

## Intentional Simplifications

### 1. correlation_id: UUID to Optional[str]

**Legacy:**
```python
correlation_id: UUID = Field(..., description="Request correlation ID")
```

**Canonical:**
```python
correlation_id: Optional[str] = Field(default=None, description="Correlation ID for distributed tracing")
```

**Rationale:**
- String format is more portable across systems
- Optional allows events without explicit correlation (e.g., system-generated events)
- JSON serialization is simpler without UUID parsing
- Event envelope typically contains primary correlation ID

**Migration:**
```python
# Legacy
output = ModelIntelligenceOutput(
    correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    ...
)

# Canonical
output = ModelIntelligenceOutput(
    correlation_id="550e8400-e29b-41d4-a716-446655440000",
    ...
)
```

### 2. onex_compliance: Float Score to Boolean Flag

**Legacy:**
```python
onex_compliance: Optional[float] = Field(None, ge=0.0, le=1.0, description="ONEX compliance score")
```

**Canonical:**
```python
onex_compliant: Optional[bool] = Field(default=None, description="Whether the analyzed code is ONEX compliant")
```

**Rationale:**
- Most consumers only need to know "compliant or not"
- Detailed compliance scoring available in `analysis_results` if needed
- Reduces cognitive load for event consumers
- Aligns with binary quality gates in CI/CD pipelines

**Migration:**
```python
# Legacy - convert score to boolean
legacy_output.onex_compliance  # 0.92

# Canonical - use threshold-based conversion
canonical_output.onex_compliant  # True (assuming threshold >= 0.9)

# If score needed, include in analysis_results:
canonical_output = ModelIntelligenceOutput(
    onex_compliant=True,
    analysis_results={"onex_compliance_score": 0.92, ...},
    ...
)
```

### 3. patterns: Rich Objects to String List

**Legacy:**
```python
patterns: Optional[list[ModelPatternDetection]] = Field(None, description="Detected patterns")

class ModelPatternDetection(BaseModel):
    pattern_type: str
    pattern_name: str
    confidence: float
    description: str
    location: Optional[str]
    severity: Literal["info", "warning", "error", "critical"]
    recommendation: Optional[str]
```

**Canonical:**
```python
patterns_detected: list[str] = Field(default_factory=list, description="List of detected patterns")
```

**Rationale:**
- Simplifies event payload size
- Pattern names are sufficient for most routing/filtering use cases
- Detailed pattern information available in `analysis_results` if needed
- Reduces coupling between event consumers and pattern model structure

**Migration:**
```python
# Legacy
legacy_output.patterns = [
    ModelPatternDetection(
        pattern_type="architectural",
        pattern_name="ONEX_EFFECT_NODE",
        confidence=0.95,
        description="Proper Effect node implementation detected",
        severity="info"
    )
]

# Canonical - extract pattern names
canonical_output.patterns_detected = ["ONEX_EFFECT_NODE"]

# If full details needed, include in analysis_results:
canonical_output = ModelIntelligenceOutput(
    patterns_detected=["ONEX_EFFECT_NODE"],
    analysis_results={
        "pattern_details": [
            {
                "pattern_type": "architectural",
                "pattern_name": "ONEX_EFFECT_NODE",
                "confidence": 0.95,
                "description": "Proper Effect node implementation detected",
                "severity": "info"
            }
        ]
    },
    ...
)
```

### 4. Removed Fields

The following fields were intentionally removed from the canonical output model:

| Field | Legacy Purpose | Where Data Lives Now |
|-------|----------------|----------------------|
| `processing_time_ms` | Track operation duration | Event envelope `timestamp` or observability metrics |
| `complexity_score` | Code complexity measure | `analysis_results["complexity_score"]` if needed |
| `issues` | List of detected issues | Merged into `recommendations` or `analysis_results["issues"]` |
| `metrics` | Service execution metrics | Observability layer (Kafka headers, logging, tracing) |
| `error_code` | Machine-readable error identifier | `metadata["error_code"]` or `analysis_results["error_code"]` |
| `retry_allowed` | Retry eligibility flag | DLQ routing configuration / event envelope |
| `timestamp` | Operation completion time | Event envelope metadata |

#### Retry Configuration Scope

The `retry_allowed` field was removed because retry behavior is now handled at the infrastructure level:

- **Effect Nodes**: Retry logic is configured in the Effect node's `contract.yaml` under the `error_handling` section. This applies to all operations processed by that Effect node.
- **Dead Letter Queue (DLQ)**: Failed messages are automatically routed to DLQ topics (e.g., `*.dlq`) based on the Effect node's configuration. DLQ routing criteria include:
  - Number of retry attempts exceeded
  - Non-retryable error codes (e.g., validation errors, malformed payloads)
  - Timeout thresholds
- **Event Envelope**: For individual event-level retry overrides, use the event envelope's `metadata.retry_policy` field (optional).

Example Effect node retry configuration in `contract.yaml`:
```yaml
error_handling:
  retry:
    enabled: true
    max_attempts: 3
    backoff_multiplier: 2.0
    initial_delay_ms: 1000
  dlq:
    enabled: true
    topic_suffix: ".dlq"
```

### 5. Renamed Fields

| Legacy Name | Canonical Name | Rationale |
|-------------|----------------|-----------|
| `result_data` | `analysis_results` | More descriptive name for the field's purpose |
| `onex_compliance` | `onex_compliant` | Changed from score (float) to flag (bool) |
| `patterns` | `patterns_detected` | More descriptive, indicates list of detected pattern names |

## Models Not Migrated

The following legacy models are **intentionally not present** in the canonical package. They may be migrated in future versions or remain as operation-specific models in their respective nodes:

### API Contract Models (from model_intelligence_api_contracts.py)

- `ModelQualityAssessmentRequest/Response` - Use `ModelIntelligenceInput` with `operation_type="assess_code_quality"`
- `ModelPerformanceAnalysisRequest/Response` - Use `ModelIntelligenceInput` with `operation_type="analyze_performance"`
- `ModelPatternDetectionRequest/Response` - Use `ModelIntelligenceInput` with `operation_type="detect_patterns"`
- `ModelHealthCheckResponse` - Handled by node introspection
- `ModelErrorResponse` - Use `ModelIntelligenceOutput` with `success=False`

### Supporting Models

- `ModelPatternDetection` - Pattern details in `analysis_results` dictionary
- `ModelIntelligenceMetrics` - Moved to observability layer
- `ArchitecturalCompliance` - Simplified to boolean in output
- `MaintainabilityMetrics` - Available in `analysis_results` if needed
- `OnexComplianceDetails` - Simplified; details in `analysis_results`

### Configuration Model

- `ModelIntelligenceConfig` - Configuration handled by node-specific contracts (YAML) and environment variables

## Migration Examples

### Example 1: Quality Assessment

**Legacy Request:**
```python
from omniarchon.models import ModelQualityAssessmentRequest

request = ModelQualityAssessmentRequest(
    content="def hello(): pass",
    source_path="src/main.py",
    language="python",
    include_recommendations=True,
    min_quality_threshold=0.7
)
```

**Canonical Request:**
```python
from omniintelligence.models import ModelIntelligenceInput

request = ModelIntelligenceInput(
    operation_type="assess_code_quality",
    content="def hello(): pass",
    source_path="src/main.py",
    language="python",
    options={
        "include_recommendations": True,
        "min_quality_threshold": 0.7
    }
)
```

### Example 2: Processing Output

**Legacy:**
```python
from omniarchon.models import ModelIntelligenceOutput, ModelPatternDetection
from uuid import UUID

output = ModelIntelligenceOutput(
    success=True,
    operation_type="assess_code_quality",
    correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    processing_time_ms=1234,
    quality_score=0.87,
    onex_compliance=0.92,
    complexity_score=0.65,
    issues=["Missing docstring"],
    recommendations=["Add type hints"],
    patterns=[
        ModelPatternDetection(
            pattern_type="quality",
            pattern_name="MISSING_DOCSTRING",
            confidence=0.9,
            description="Function lacks docstring",
            severity="warning"
        )
    ],
    error_code=None,
    error_message=None,
    retry_allowed=False,
)

# Access pattern details
for pattern in output.patterns:
    print(f"{pattern.pattern_name}: {pattern.description}")
```

**Canonical:**
```python
from omniintelligence.models import ModelIntelligenceOutput

output = ModelIntelligenceOutput(
    success=True,
    operation_type="assess_code_quality",
    quality_score=0.87,
    onex_compliant=True,  # Boolean instead of score
    patterns_detected=["MISSING_DOCSTRING"],
    recommendations=["Missing docstring", "Add type hints"],  # issues merged here
    analysis_results={
        "onex_compliance_score": 0.92,
        "complexity_score": 0.65,
        "pattern_details": [
            {
                "pattern_type": "quality",
                "pattern_name": "MISSING_DOCSTRING",
                "confidence": 0.9,
                "description": "Function lacks docstring",
                "severity": "warning"
            }
        ]
    },
    correlation_id="550e8400-e29b-41d4-a716-446655440000",
    metadata={"processing_time_ms": 1234}  # Timing in metadata if needed
)

# Access pattern details from analysis_results
for pattern in output.analysis_results.get("pattern_details", []):
    print(f"{pattern['pattern_name']}: {pattern['description']}")
```

### Example 3: Error Handling

**Legacy:**
```python
error_output = ModelIntelligenceOutput.create_error(
    operation_type="assess_code_quality",
    correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
    processing_time_ms=150,
    error_code="INTELLIGENCE_SERVICE_TIMEOUT",
    error_message="Service did not respond within 10s",
    retry_allowed=True,
)
```

**Canonical:**
```python
error_output = ModelIntelligenceOutput(
    success=False,
    operation_type="assess_code_quality",
    correlation_id="550e8400-e29b-41d4-a716-446655440000",
    error_message="Service did not respond within 10s",
    metadata={
        "error_code": "INTELLIGENCE_SERVICE_TIMEOUT",
        "retry_allowed": True,
        "processing_time_ms": 150
    }
)
```

## Compatibility Notes

### Pydantic Configuration

Both legacy and canonical models use Pydantic, but with different configurations:

**Legacy:**
```python
class Config:
    arbitrary_types_allowed = True
    json_schema_extra = {...}
```

**Canonical:**
```python
model_config = {"frozen": True, "extra": "forbid"}
```

Key differences:
- Canonical models are **immutable** (`frozen=True`)
- Canonical models **reject unknown fields** (`extra="forbid"`)
- This ensures data integrity in event-driven systems

### JSON Serialization

**Legacy** used a custom `to_dict()` method for serialization.

**Canonical** relies on Pydantic's built-in serialization:
```python
# Serialize to dict
output.model_dump()

# Serialize to JSON string
output.model_dump_json()
```

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-01-18 | Initial canonical models with simplified design |

## Questions?

If you encounter migration issues or need additional legacy fields, please:

1. Check if the data can be placed in `analysis_results` or `metadata`
2. Open an issue in the omniintelligence repository
3. Consult the CLAUDE.md file for additional context
