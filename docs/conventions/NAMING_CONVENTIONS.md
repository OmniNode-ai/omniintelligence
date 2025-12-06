# ONEX Naming Conventions

**Purpose**: Standard naming conventions for omniintelligence code artifacts
**Audience**: Contributors, AI agents, technical writers
**Last Updated**: 2025-12-05

---

## Quick Reference

| Artifact | Pattern | Example |
|----------|---------|---------|
| Model files | `model_{name}.py` | `model_routing_decision.py` |
| Model classes | `Model{Name}` | `ModelRoutingDecision` |
| Enum files | `enum_{name}.py` | `enum_confidence_level.py` |
| Enum classes | `Enum{Name}` | `EnumConfidenceLevel` |
| Protocol files | `protocol_{name}.py` | `protocol_router.py` |
| Protocol classes | `Protocol{Name}` | `ProtocolRouter` |
| Service files | `service_{name}.py` | `service_agent_registry.py` |
| Service classes | `Service{Name}` | `ServiceAgentRegistry` |
| Node files | `node_{name}.py` | `node_intelligence_reducer.py` |
| Node classes | `Node{Name}{Type}` | `NodeIntelligenceReducer` |

---

## File Naming Prefixes

All Python source files must use the appropriate prefix based on their type:

| Prefix | Description | Location |
|--------|-------------|----------|
| `model_*` | Pydantic domain models | `shared/models/` |
| `enum_*` | Enumeration types | `shared/enums/` |
| `protocol_*` | Protocol interfaces (ABCs) | `contracts/` |
| `service_*` | Service implementations | `services/` |
| `node_*` | ONEX nodes | `nodes/` |
| `handler_*` | Protocol handlers | `handlers/` |
| `client_*` | External service clients | `integration/` |
| `test_*` | Test files | `tests/` |

---

## Field Naming Patterns

### Identifiers

Use `{entity}_id` pattern for all identifier fields:

```python
# ✅ Correct
task_id: UUID
correlation_id: UUID
request_id: UUID
batch_id: UUID
decision_id: UUID

# ❌ Wrong
id: UUID           # Too generic
task: UUID         # Missing _id suffix
taskId: UUID       # Wrong case (camelCase)
```

### Type Discriminators

Use `{entity}_type` pattern for type fields:

```python
# ✅ Correct
event_type: str
action_type: EnumActionType
operation_type: str
routing_strategy: EnumRoutingStrategy  # _strategy also acceptable

# ❌ Wrong
type: str          # Too generic
eventType: str     # Wrong case
```

### Names and Labels

Use `{entity}_name` pattern for name fields:

```python
# ✅ Correct
agent_name: str
stream_name: str
target_name: str

# ❌ Wrong
name: str          # Too generic at entity level
agentName: str     # Wrong case
```

### Timestamps

Use `*_at` suffix for datetime fields:

```python
# ✅ Correct
created_at: datetime
updated_at: datetime
started_at: datetime
completed_at: datetime

# ❌ Wrong
timestamp: datetime    # Use created_at instead
creation_time: datetime # Use _at suffix
createdAt: datetime    # Wrong case
```

### Durations

Use `*_ms` suffix for duration fields (always in milliseconds):

```python
# ✅ Correct
timeout_ms: int
latency_ms: float
processing_time_ms: float
duration_ms: int

# ❌ Wrong
timeout_seconds: int   # Use _ms, convert at API boundary
timeout: int           # Missing unit suffix
timeoutMs: int         # Wrong case
```

**Rationale**: Milliseconds provide sufficient precision for most operations while avoiding floating-point issues with sub-second values.

### Counts

Use `*_count` suffix for count fields:

```python
# ✅ Correct
retry_count: int
match_count: int
completed_count: int
failed_count: int

# ❌ Wrong
completed_tasks: int   # Sounds like a list, not a count
retries: int           # Missing _count suffix
num_retries: int       # Use _count, not num_
```

### Scores

Use `*_score` suffix for score fields (0.0 to 1.0 range):

```python
# ✅ Correct
confidence_score: float = Field(ge=0.0, le=1.0)
quality_score: float
final_score: float

# ❌ Wrong
confidence: float      # Missing _score suffix (unless it's a level)
score: float           # Too generic
```

### Boolean Fields

Use appropriate pattern based on semantics:

```python
# Feature flags: {feature}_enabled
cache_enabled: bool
parallel_enabled: bool
archon_mcp_enabled: bool
correlation_tracking_enabled: bool

# State checks: is_{condition}
is_success: bool
is_complete: bool
is_valid: bool
is_terminal: bool

# Presence checks: has_{thing}
has_dependencies: bool
has_alternatives: bool
has_correlation_id: bool

# Capability flags: {capability}_capable
parallel_capable: bool
```

### Limits and Thresholds

Use `max_*` and `*_threshold` patterns:

```python
# ✅ Correct
max_retries: int
max_alternatives: int
confidence_threshold: float

# ❌ Wrong
retry_limit: int       # Use max_retries
threshold: float       # Too generic
```

---

## Collection Fields

When naming collection fields (lists, dicts):

```python
# Lists: Use plural of contained type
dependencies: list[UUID]       # List of dependency IDs
alternatives: list[dict]       # List of alternative options
triggers: list[str]            # List of trigger patterns

# Dicts: Use {entity}_{contents} or descriptive name
task_results: dict[str, Any]   # Results keyed by task
component_scores: dict[str, float]  # Scores by component
metadata: dict[str, Any]       # Generic metadata (exception)
```

---

## Entity-Prefixed Fields

When a field is too generic at the model level, prefix with the entity:

```python
class ModelParallelResult(BaseModel):
    # ✅ Correct - prefixed with entity context
    batch_id: UUID
    batch_status: BatchStatus
    task_results: dict[str, Any]

    # ❌ Wrong - too generic
    id: UUID
    status: BatchStatus
    results: dict[str, Any]
```

---

## Computed Properties

Computed fields should follow the same naming conventions:

```python
@computed_field
@property
def total_duration_ms(self) -> float | None:
    """Duration uses _ms suffix."""
    ...

@computed_field
@property
def success_rate(self) -> float:
    """Rate uses _rate suffix."""
    ...

@computed_field
@property
def is_complete(self) -> bool:
    """Boolean state check uses is_ prefix."""
    ...
```

---

## Validation

### Pre-commit Checks

Field naming is validated through code review. Future automation may include:

```bash
# Check for non-compliant field names (future)
poetry run ruff check --select=ONEX-NAMING
```

### Manual Review Checklist

When reviewing models, verify:

- [ ] All `*_id` fields use UUID type
- [ ] All datetime fields use `*_at` suffix
- [ ] All duration fields use `*_ms` suffix
- [ ] All count fields use `*_count` suffix
- [ ] All boolean flags use `*_enabled`, `is_*`, or `has_*`
- [ ] No generic field names (`id`, `type`, `status`, `results`)
- [ ] Collection fields use appropriate pluralization

---

## Cross-Repository Consistency

These conventions are aligned with:

- **omnibase_core**: `ModelIntent`, `ModelAction`, `ModelComputeInput/Output`
- **omnibase_infra**: `ModelEventHeaders`, `ModelInfraErrorContext`
- **omniagent**: `ModelRoutingDecision`, `ModelParallelResult`

See also:
- `omnibase_core/docs/conventions/TERMINOLOGY_GUIDE.md`
- `omnibase_core/docs/reference/api/models.md`

---

**Version**: 1.0
**Maintained By**: OmniIntelligence team
