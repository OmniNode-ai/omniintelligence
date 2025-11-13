# OmniNode Bridge - Intelligence Service Integration

Comprehensive API contracts and HTTP client for Archon Intelligence Service integration.

## Overview

This package provides ONEX-compliant API contracts and HTTP client wrapper for communicating with the Archon Intelligence Service (http://localhost:8053). It follows ONEX Effect Node patterns for external HTTP I/O with robust error handling, retry logic, and circuit breaker patterns.

## Architecture

```
omninode_bridge/
├── models/
│   └── model_intelligence_api_contracts.py  # API request/response models
├── clients/
│   └── client_intelligence_service.py       # HTTP client wrapper
├── examples/
│   └── intelligence_service_usage.py        # Usage examples
└── README.md                                 # This file
```

## Features

### API Contracts (Pydantic Models)

**3 Core API Contract Pairs:**

1. **Code Quality Assessment** (`POST /assess/code`)
   - Request: `ModelQualityAssessmentRequest`
   - Response: `ModelQualityAssessmentResponse`
   - 6-dimensional quality analysis (complexity, maintainability, documentation, temporal relevance, patterns, architecture)

2. **Performance Analysis** (`POST /performance/baseline`)
   - Request: `ModelPerformanceAnalysisRequest`
   - Response: `ModelPerformanceAnalysisResponse`
   - Performance baseline establishment and ROI-ranked optimization opportunities

3. **Pattern Detection** (`POST /patterns/extract`)
   - Request: `ModelPatternDetectionRequest`
   - Response: `ModelPatternDetectionResponse`
   - Best practices, anti-patterns, security patterns, ONEX compliance

### HTTP Client Features

- **Circuit Breaker Pattern**: Opens after 5 failures, resets after 60s
- **Retry Logic**: Exponential backoff with max 3 retries
- **HTTP/2 Connection Pooling**: 20 max connections, 5 keepalive
- **Timeout Handling**: Configurable per request (default 10s)
- **Health Checks**: Periodic background checks every 30s
- **Error Handling**: HTTP errors → OnexError hierarchy
- **Metrics Tracking**: Success rate, latency, circuit breaker state
- **Async Context Manager**: Automatic connection management

## Installation

```python
# Import API contracts
from omninode_bridge.models import (
    ModelQualityAssessmentRequest,
    ModelQualityAssessmentResponse,
    ModelPerformanceAnalysisRequest,
    ModelPatternDetectionRequest,
)

# Import HTTP client
from omninode_bridge.clients import IntelligenceServiceClient
```

## Quick Start

### Example 1: Code Quality Assessment

```python
import asyncio
from omninode_bridge.models import ModelQualityAssessmentRequest
from omninode_bridge.clients import IntelligenceServiceClient

async def assess_code():
    async with IntelligenceServiceClient() as client:
        # Create request
        request = ModelQualityAssessmentRequest(
            content="def hello(): pass",
            source_path="src/api.py",
            language="python",
            include_recommendations=True,
            min_quality_threshold=0.7,
        )

        # Execute assessment
        response = await client.assess_code_quality(request)

        # Access results
        print(f"Quality Score: {response.quality_score:.2f}")
        print(f"ONEX Compliance: {response.onex_compliance.score:.2f}")
        print(f"Maintainability: {response.maintainability.complexity_score:.2f}")

        # Check recommendations
        for rec in response.onex_compliance.recommendations:
            print(f"  - {rec}")

asyncio.run(assess_code())
```

### Example 2: Performance Analysis

```python
async def analyze_performance():
    async with IntelligenceServiceClient() as client:
        # Create request
        request = ModelPerformanceAnalysisRequest(
            operation_name="database_query",
            code_content="async def query_users(db): return db.query(User).all()",
            context={"execution_type": "async", "io_type": "database"},
            include_opportunities=True,
            target_percentile=95,
        )

        # Execute analysis
        response = await client.analyze_performance(request)

        # View optimization opportunities
        for opp in response.optimization_opportunities:
            print(f"{opp.title} (ROI: {opp.roi_score:.2f})")
            print(f"  Improvement: {opp.estimated_improvement}")
            print(f"  Effort: {opp.effort_estimate}")
```

### Example 3: Pattern Detection

```python
from omninode_bridge.models import ModelPatternDetectionRequest, PatternCategory

async def detect_patterns():
    async with IntelligenceServiceClient() as client:
        # Create request
        request = ModelPatternDetectionRequest(
            content="class UserService:\n    pass",
            source_path="src/services/user_service.py",
            pattern_categories=[
                PatternCategory.BEST_PRACTICES,
                PatternCategory.ANTI_PATTERNS,
                PatternCategory.SECURITY_PATTERNS,
            ],
            min_confidence=0.7,
        )

        # Execute detection
        response = await client.detect_patterns(request)

        # View detected patterns
        for pattern in response.detected_patterns:
            print(f"{pattern.pattern_type} ({pattern.confidence:.2f})")
            print(f"  Category: {pattern.category.value}")
            print(f"  Description: {pattern.description}")
```

## Error Handling

The client uses OnexError hierarchy for comprehensive error handling:

```python
from omninode_bridge.clients import (
    IntelligenceServiceUnavailable,
    IntelligenceServiceTimeout,
    IntelligenceServiceValidation,
    IntelligenceServiceRateLimit,
)

async def handle_errors():
    async with IntelligenceServiceClient() as client:
        try:
            response = await client.assess_code_quality(request)
        except IntelligenceServiceValidation as e:
            # Handle validation errors (422)
            print(f"Validation failed: {e.details['validation_errors']}")
        except IntelligenceServiceTimeout as e:
            # Handle timeout errors (504)
            print(f"Request timed out after {e.details['timeout_seconds']}s")
        except IntelligenceServiceUnavailable as e:
            # Handle service unavailable (503) or circuit breaker open
            print(f"Service unavailable: {e.message}")
        except IntelligenceServiceRateLimit as e:
            # Handle rate limits (429)
            retry_after = e.details.get('retry_after')
            print(f"Rate limited. Retry after {retry_after}s")
```

## Configuration

### Client Configuration

```python
client = IntelligenceServiceClient(
    base_url="http://localhost:8053",  # Service URL
    timeout_seconds=10.0,               # Request timeout
    max_retries=3,                      # Retry attempts
    circuit_breaker_enabled=True,       # Enable circuit breaker
)
```

### Environment Variables

```bash
# Intelligence Service URL (optional, default: http://localhost:8053)
INTELLIGENCE_SERVICE_URL=http://localhost:8053

# Service authentication token (if required)
INTELLIGENCE_SERVICE_AUTH_TOKEN=<token>
```

## Metrics and Monitoring

### Get Client Metrics

```python
async with IntelligenceServiceClient() as client:
    # ... perform requests ...

    # Get metrics
    metrics = client.get_metrics()

    print(f"Total Requests: {metrics['total_requests']}")
    print(f"Success Rate: {metrics['success_rate']:.2%}")
    print(f"Avg Duration: {metrics['avg_duration_ms']:.2f}ms")
    print(f"Circuit Breaker State: {metrics['circuit_breaker_state']}")
    print(f"Is Healthy: {metrics['is_healthy']}")
```

### Health Checks

```python
async with IntelligenceServiceClient() as client:
    # Manual health check
    health = await client.check_health()

    print(f"Status: {health.status}")
    print(f"Memgraph Connected: {health.memgraph_connected}")
    print(f"Ollama Connected: {health.ollama_connected}")
    print(f"Version: {health.service_version}")
```

## Performance Targets

| Operation | Target | Typical |
|-----------|--------|---------|
| Quality Assessment | <2s (uncached) | ~1.5s |
| Quality Assessment | <500ms (cached) | ~300ms |
| Performance Analysis | <3s | ~2s |
| Pattern Detection | <1.5s | ~1s |
| Health Check | <2s | ~100ms |

## ONEX Compliance

### Request/Response Models

All models follow ONEX patterns:
- Pydantic BaseModel for validation
- Field() descriptions for documentation
- Validation rules (ge, le, min_length)
- JSON schema examples in Config
- Type hints throughout

### Error Handling

All HTTP errors mapped to OnexError hierarchy:
- 422 → IntelligenceServiceValidation
- 429 → IntelligenceServiceRateLimit
- 503 → IntelligenceServiceUnavailable
- 504 → IntelligenceServiceTimeout
- 5xx → IntelligenceServiceError

### Effect Node Pattern

Client follows ONEX Effect Node pattern:
- External HTTP I/O operations
- Async execution with context manager
- Circuit breaker for resilience
- Retry logic for transient failures
- Comprehensive error handling
- Metrics tracking and monitoring

## Testing

Run the comprehensive examples:

```bash
python -m omninode_bridge.examples.intelligence_service_usage
```

This will execute all 6 examples:
1. Code Quality Assessment
2. Performance Analysis
3. Pattern Detection
4. Health Checks
5. Error Handling
6. Metrics Tracking

## API Reference

### Request Models

**ModelQualityAssessmentRequest**
- `content: str` - Source code content
- `source_path: str` - File path
- `language: Optional[str]` - Programming language
- `include_recommendations: bool` - Include recommendations
- `min_quality_threshold: float` - Minimum quality threshold

**ModelPerformanceAnalysisRequest**
- `operation_name: str` - Operation identifier
- `code_content: str` - Code to analyze
- `context: Optional[Dict]` - Execution context
- `include_opportunities: bool` - Include opportunities
- `target_percentile: int` - Target percentile (50, 90, 95, 99)

**ModelPatternDetectionRequest**
- `content: str` - Source code content
- `source_path: str` - File path
- `pattern_categories: Optional[List[PatternCategory]]` - Categories to detect
- `min_confidence: float` - Minimum confidence threshold
- `include_recommendations: bool` - Include recommendations

### Response Models

**ModelQualityAssessmentResponse**
- `quality_score: float` - Overall quality score (0.0-1.0)
- `architectural_compliance: ArchitecturalCompliance` - Compliance details
- `maintainability: MaintainabilityMetrics` - Maintainability breakdown
- `onex_compliance: OnexComplianceDetails` - ONEX compliance
- `architectural_era: str` - Era classification
- `temporal_relevance: float` - Temporal relevance score
- `timestamp: datetime` - Analysis timestamp

**ModelPerformanceAnalysisResponse**
- `baseline_metrics: BaselineMetrics` - Performance baseline
- `optimization_opportunities: List[OptimizationOpportunity]` - Ranked opportunities
- `total_opportunities: int` - Total count
- `estimated_total_improvement: Optional[str]` - Cumulative improvement
- `timestamp: datetime` - Analysis timestamp

**ModelPatternDetectionResponse**
- `detected_patterns: List[DetectedPattern]` - All patterns
- `anti_patterns: List[DetectedPattern]` - Anti-patterns subset
- `architectural_compliance: Optional[ArchitecturalComplianceDetails]` - Compliance
- `analysis_summary: Dict` - Summary statistics
- `confidence_scores: Dict` - Confidence by category
- `recommendations: List[str]` - Recommendations
- `timestamp: datetime` - Analysis timestamp

## Contributing

When adding new API contracts:

1. Define request/response models in `model_intelligence_api_contracts.py`
2. Add client method in `client_intelligence_service.py`
3. Include usage example in `examples/intelligence_service_usage.py`
4. Update `__init__.py` exports
5. Update this README with new examples

## License

Part of the Archon Intelligence Platform.
