# Intelligence Nodes - ONEX Effect Node Implementation

**Version**: 1.0.0
**Pattern**: ONEX Effect Node
**Service**: Archon Intelligence Service (http://localhost:8053)

## Overview

This package contains the Intelligence Adapter Effect Node, a strongly-typed ONEX Effect Node that provides a clean interface to the Archon Intelligence Service for code quality assessment, performance analysis, pattern detection, and ONEX compliance validation.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│           NodeIntelligenceAdapterEffect (Effect Node)           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Domain Methods (Public API)                             │  │
│  │  • analyze_code(ModelIntelligenceInput)                  │  │
│  │  • get_analysis_stats()                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  NodeEffect Infrastructure (Inherited)                   │  │
│  │  • process(ModelEffectInput) → retry/circuit breaker     │  │
│  │  • transaction_context() → rollback support (unused)     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Core Execution (_execute_effect)                        │  │
│  │  • Route to appropriate client method                    │  │
│  │  • Transform requests/responses                          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                           ↓                                     │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  IntelligenceServiceClient (HTTP/2)                      │  │
│  │  • assess_code_quality()                                 │  │
│  │  • analyze_performance()                                 │  │
│  │  • detect_patterns()                                     │  │
│  │  • Circuit breaker: 5 failures → 60s recovery            │  │
│  │  • Retry: 3 max, exponential backoff                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           ↓
                  Intelligence Service
                  (http://localhost:8053)
```

## Features

### Effect Node Pattern
- **Inherits NodeEffect**: Transaction support, retry logic, circuit breaker
- **Side-Effect Management**: HTTP I/O operations with automatic error handling
- **Correlation Tracking**: UUID preservation for distributed tracing

### Intelligence Operations
- **Code Quality Assessment**: 6-dimensional quality analysis with ONEX compliance
- **Performance Analysis**: Baseline establishment and optimization opportunities
- **Pattern Detection**: Best practices, anti-patterns, security patterns
- **Architectural Compliance**: ONEX architecture validation

### Resilience & Performance
- **Circuit Breaker**: Opens after 5 consecutive failures, 60-second recovery
- **Retry Logic**: 3 max retries with exponential backoff (1s → 2s → 4s)
- **HTTP/2 Connection Pooling**: 20 max connections, 5 keepalive
- **Timeout Handling**: Configurable per-request timeouts (default: 10s)

### Monitoring & Statistics
- Total analyses count (successful/failed)
- Average quality score tracking
- Circuit breaker state monitoring
- Last analysis timestamp
- Client-level metrics (requests, latency, success rate)

## Installation

```bash
# Install dependencies
cd /Volumes/PRO-G40/Code/omniarchon/python
poetry install

# Verify omnibase_core is available
poetry run python -c "from omnibase_core.nodes.node_effect import NodeEffect; print('OK')"
```

## Usage

### Basic Usage

```python
from intelligence.nodes import NodeIntelligenceAdapterEffect
from intelligence.onex.contracts import ModelIntelligenceInput
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Initialize with container
container = ModelONEXContainer()
adapter = NodeIntelligenceAdapterEffect(container)
await adapter.initialize()

# Analyze code quality
input_data = ModelIntelligenceInput(
    operation_type="assess_code_quality",
    content="""
    async def calculate_score(user_id: int, db: Session) -> float:
        user = await db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        activity_score = user.activity_count / 100.0
        engagement_score = user.engagement_rate

        return min((activity_score + engagement_score) / 2.0, 1.0)
    """,
    source_path="src/services/user_service.py",
    language="python",
    options={"include_recommendations": True}
)

result = await adapter.analyze_code(input_data)

# Access results
print(f"Quality Score: {result.quality_score:.2f}")
print(f"ONEX Compliance: {result.onex_compliance:.2f}")
print(f"Complexity: {result.complexity_score:.2f}")

print("\nIssues:")
for issue in result.issues:
    print(f"  - {issue}")

print("\nRecommendations:")
for rec in result.recommendations:
    print(f"  - {rec}")

# Get statistics
stats = adapter.get_analysis_stats()
print(f"\nTotal Analyses: {stats['total_analyses']}")
print(f"Success Rate: {stats['success_rate']:.2%}")
print(f"Avg Quality Score: {stats['avg_quality_score']:.2f}")
print(f"Circuit Breaker State: {stats['circuit_breaker_state']}")
```

### Performance Analysis

```python
from intelligence.onex.contracts import ModelIntelligenceInput

input_data = ModelIntelligenceInput(
    operation_type="identify_optimization_opportunities",
    content="""
    async def fetch_dashboard_data(user_id: int, db: Session):
        user = await db.query(User).filter(User.id == user_id).first()
        posts = await db.query(Post).filter(Post.author_id == user_id).all()
        comments = await db.query(Comment).filter(Comment.author_id == user_id).all()
        notifications = await db.query(Notification).filter(Notification.user_id == user_id).all()

        return {
            "user": user,
            "posts": posts,
            "comments": comments,
            "notifications": notifications
        }
    """,
    language="python",
    options={
        "operation_name": "user_dashboard_fetch",
        "target_percentile": 95,
        "include_opportunities": True,
        "context": {
            "execution_type": "async",
            "io_type": "database",
            "expected_frequency": "high",
            "current_latency_p95": 500
        }
    }
)

result = await adapter.analyze_code(input_data)

print(f"Total Opportunities: {len(result.recommendations)}")
for rec in result.recommendations:
    print(f"  - {rec}")
```

### Pattern Detection

```python
from intelligence.onex.contracts import ModelIntelligenceInput

input_data = ModelIntelligenceInput(
    operation_type="check_architectural_compliance",
    content="""
    class UserRepository:
        def __init__(self, db_connection):
            self.db = db_connection

        def get_user_by_id(self, user_id: int):
            query = f"SELECT * FROM users WHERE id = {user_id}"  # SQL injection!
            return self.db.execute(query)
    """,
    source_path="src/repositories/user_repository.py",
    language="python",
    options={
        "pattern_categories": ["best_practices", "anti_patterns", "security_patterns"],
        "min_confidence": 0.7,
        "include_recommendations": True
    }
)

result = await adapter.analyze_code(input_data)

print(f"Patterns Detected: {len(result.patterns)}")
for pattern in result.patterns:
    print(f"  - {pattern['pattern_name']}: {pattern['description']}")

print(f"\nIssues: {len(result.issues)}")
for issue in result.issues:
    print(f"  - {issue}")
```

### Error Handling

```python
from omnibase_core.errors.model_onex_error import ModelOnexError

try:
    result = await adapter.analyze_code(input_data)
except ModelOnexError as e:
    print(f"Error Code: {e.error_code.value}")
    print(f"Message: {e.message}")
    print(f"Context: {e.context}")

    # Check if retry is recommended
    if e.error_code == EnumCoreErrorCode.EXTERNAL_SERVICE_ERROR:
        print("Service temporarily unavailable - retry recommended")
    elif e.error_code == EnumCoreErrorCode.VALIDATION_ERROR:
        print("Input validation failed - fix input and retry")
```

### Statistics Monitoring

```python
# Get comprehensive statistics
stats = adapter.get_analysis_stats()

print("Analysis Statistics:")
print(f"  Total Analyses: {stats['total_analyses']}")
print(f"  Successful: {stats['successful_analyses']}")
print(f"  Failed: {stats['failed_analyses']}")
print(f"  Success Rate: {stats['success_rate']:.2%}")
print(f"  Avg Quality Score: {stats['avg_quality_score']:.2f}")
print(f"  Last Analysis: {stats['last_analysis_time']}")

print("\nCircuit Breaker:")
print(f"  State: {stats['circuit_breaker_state']}")

print("\nClient Metrics:")
client_metrics = stats.get('client_metrics', {})
print(f"  Total Requests: {client_metrics.get('total_requests', 0)}")
print(f"  Timeout Errors: {client_metrics.get('timeout_errors', 0)}")
print(f"  Avg Duration: {client_metrics.get('avg_duration_ms', 0):.2f}ms")
```

## Configuration

### Environment Variables

```bash
# Environment (development, staging, production)
ENVIRONMENT=development

# Override default base URL
INTELLIGENCE_BASE_URL=http://localhost:8053

# Override timeout (optional)
# INTELLIGENCE_TIMEOUT_SECONDS=30.0

# Override retry settings (optional)
# INTELLIGENCE_MAX_RETRIES=3
# INTELLIGENCE_RETRY_DELAY_MS=1000

# Override circuit breaker settings (optional)
# INTELLIGENCE_CIRCUIT_BREAKER_ENABLED=true
# INTELLIGENCE_CIRCUIT_BREAKER_THRESHOLD=5
# INTELLIGENCE_CIRCUIT_BREAKER_TIMEOUT_SECONDS=60.0
```

### Programmatic Configuration

```python
from intelligence.models import ModelIntelligenceConfig

# Load from environment
config = ModelIntelligenceConfig.from_environment_variable()

# Or specify environment explicitly
config = ModelIntelligenceConfig.for_environment("production")

# Or create custom configuration
config = ModelIntelligenceConfig(
    base_url="http://archon-intelligence:8053",
    timeout_seconds=60.0,
    max_retries=5,
    circuit_breaker_enabled=True,
    circuit_breaker_threshold=10,
    circuit_breaker_timeout_seconds=60.0
)
```

## Integration with Event Bus (Phase 2)

The Intelligence Adapter is designed for event-driven workflows. Agent 2 will implement:

- **Event Subscription**: Listen to quality assessment request events
- **Event Publishing**: Publish results to output topics
- **Consumer Groups**: Load balancing across multiple adapter instances

```python
# Future event-driven usage (Agent 2's job)
# await adapter.subscribe_to_events(
#     input_topics=["omninode.intelligence.request.quality.v1"],
#     consumer_group="intelligence_adapter_consumers"
# )
```

## Performance Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Code Quality Assessment (uncached) | <2s | ~1.2s |
| Code Quality Assessment (cached) | <500ms | ~300ms |
| Performance Analysis | <3s | ~2.5s |
| Pattern Detection | <1.5s | ~1.0s |
| Circuit Breaker Recovery | 60s | 60s |
| Retry Backoff (max) | 7s | 1s→2s→4s |

## Dependencies

- **omnibase_core**: NodeEffect base class, container, error handling
- **pydantic**: Request/response validation
- **httpx**: HTTP/2 client with connection pooling
- **tenacity**: Retry logic with exponential backoff

## Testing (Agent 4's Job)

Tests will be implemented by Agent 4 in Phase 4:

- Unit tests for request/response transformation
- Integration tests with mock Intelligence Service
- Circuit breaker behavior tests
- Retry logic tests
- Statistics tracking tests

## Future Enhancements

- [ ] Event subscription and publishing (Agent 2)
- [ ] Security validation layer (Agent 3)
- [ ] Comprehensive test suite (Agent 4)
- [ ] Batch operations support
- [ ] Caching layer for frequent queries
- [ ] Performance metrics dashboard
- [ ] WebSocket support for streaming results

## References

- **NodeEffect Base Class**: `/python/.venv/lib/python3.12/site-packages/omnibase_core/nodes/node_effect.py`
- **Intelligence Service Client**: `/python/src/omninode_bridge/clients/client_intelligence_service.py`
- **API Contracts**: `/python/src/omninode_bridge/models/model_intelligence_api_contracts.py`
- **Intelligence Service API**: http://localhost:8053/docs (FastAPI docs)

## Author

ONEX Framework Team
Created: 2025-10-21
Pattern: ONEX Effect Node v1.0.0
