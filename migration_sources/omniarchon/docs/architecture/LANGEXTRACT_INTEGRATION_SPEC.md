# Langextract Integration Specification

**Document Version**: 1.0
**Last Updated**: 2025-10-02
**Target Service**: langextract:8156
**Integration Phase**: Phase 2 - Hybrid Semantic Similarity

---

## Table of Contents

1. [Service Overview](#1-service-overview)
2. [API Endpoints](#2-api-endpoints)
3. [Data Models & Contracts](#3-data-models--contracts)
4. [Integration Patterns](#4-integration-patterns)
5. [Error Handling](#5-error-handling)
6. [Testing Strategy](#6-testing-strategy)
7. [Performance Specifications](#7-performance-specifications)

---

## 1. Service Overview

### 1.1 Service Configuration

```yaml
Service Name: langextract
Container: archon-langextract
Port: 8156
Protocol: HTTP/REST
Base URL: http://langextract:8156
Docker Network: archon-network

Health Check:
  Endpoint: GET /health
  Interval: 30s
  Timeout: 5s
  Retries: 3

Dependencies:
  - Memgraph (bolt://memgraph:7687) - Knowledge graph
  - Intelligence Service (http://archon-intelligence:8053) - AI analysis
  - Bridge Service (http://archon-bridge:8054) - Event coordination
```

### 1.2 Service Capabilities

```python
Available Features:
  ✅ Semantic pattern extraction (entities, relationships, concepts)
  ✅ Domain classification (6 domains: technology, business, science, etc.)
  ✅ Conceptual hierarchy mapping
  ✅ Sentiment analysis
  ✅ Theme and topic extraction
  ✅ Structural pattern detection (lists, definitions, etc.)
  ❌ Vector embeddings (use Ollama for this)
  ❌ Real-time streaming (batch only)
```

---

## 2. API Endpoints

### 2.1 Health Check

**Endpoint**: `GET /health`

**Purpose**: Check service health and component status

**Request**: None

**Response**: `HealthStatus`

```python
# Success Response (200 OK)
{
  "status": "healthy" | "degraded" | "unhealthy",
  "timestamp": "2025-10-02T12:00:00Z",
  "version": "1.0.0",
  "components": {
    "memgraph_adapter": "healthy" | "unhealthy",
    "intelligence_client": "healthy" | "unhealthy",
    "language_extractor": "healthy" | "unhealthy",
    "document_analyzer": "healthy" | "unhealthy",
    "event_subscriber": "healthy" | "unhealthy"
  },
  "uptime_seconds": 3600.5,
  "memory_usage_mb": 512.3,
  "cpu_usage_percent": 25.4
}
```

**Usage Example**:
```python
import httpx

async def check_langextract_health():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://langextract:8156/health")
        health_data = response.json()
        return health_data["status"] == "healthy"
```

**Error Responses**:
```python
# Service Unavailable (503)
{
  "status": "unhealthy",
  "timestamp": "2025-10-02T12:00:00Z",
  "error": "Memgraph connection failed",
  "version": "1.0.0"
}
```

---

### 2.2 Semantic Analysis (PRIMARY ENDPOINT FOR PHASE 2)

**Endpoint**: `POST /analyze/semantic`

**Purpose**: Extract semantic patterns, concepts, themes without full 6-stage pipeline

**Performance**: ~3-4s per request (uncached)

**Request Parameters**:

```python
Query Parameters:
  • content (str, required): Text content to analyze
  • context (str, optional): Context hint for analysis
  • language (str, optional): Language code (default: "en")

Example:
POST /analyze/semantic?content=<text>&context=<hint>&language=en
```

**Request Example**:
```python
import httpx

async def analyze_semantic_content(content: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            "http://langextract:8156/analyze/semantic",
            params={
                "content": content,
                "context": "pattern_matching",
                "language": "en"
            }
        )
        response.raise_for_status()
        return response.json()
```

**Response**: `SemanticAnalysisResult`

```python
# Success Response (200 OK)
{
  "semantic_patterns": [
    {
      "pattern_id": "pattern_0",
      "pattern_type": "THEME",
      "pattern_name": "theme_pattern_0",
      "description": "Semantic pattern of type THEME",
      "examples": ["machine learning enables..."],
      "frequency": 1,
      "confidence_score": 0.75,
      "significance_score": 0.60,
      "context": {"theme_keywords": ["machine", "learning", "enables"]},
      "properties": {},
      "related_entity_ids": []
    },
    {
      "pattern_id": "pattern_1",
      "pattern_type": "TOPIC",
      "pattern_name": "topic_pattern_1",
      "description": "Semantic pattern of type TOPIC",
      "examples": ["artificial intelligence"],
      "frequency": 2,
      "confidence_score": 0.85,
      "significance_score": 0.68,
      "context": {"topic_keywords": ["artificial", "intelligence", "AI"]},
      "properties": {},
      "related_entity_ids": []
    }
  ],

  "concepts": [
    "machine",
    "learning",
    "artificial",
    "intelligence",
    "data",
    "algorithm",
    "model",
    "training",
    "prediction",
    "neural",
    "network",
    "deep"
  ],

  "themes": [
    "machine learning",
    "artificial intelligence",
    "neural networks",
    "data science",
    "predictive modeling"
  ],

  "semantic_density": 0.45,
  "conceptual_coherence": 0.72,
  "thematic_consistency": 0.68,

  "semantic_context": {
    "analysis_language": "en",
    "content_length": 523,
    "analysis_context": "pattern_matching",
    "timestamp": "2025-10-02T12:00:00Z",
    "entity_count": 0,
    "provided_context": true
  },

  "domain_indicators": [
    "algorithm",
    "data",
    "model",
    "training",
    "neural",
    "network",
    "machine",
    "learning"
  ],

  "primary_topics": [
    "machine learning",
    "artificial intelligence",
    "neural networks",
    "data science",
    "algorithm"
  ],

  "topic_weights": {
    "machine learning": 0.85,
    "artificial intelligence": 0.78,
    "neural networks": 0.65,
    "data science": 0.52,
    "algorithm": 0.48
  }
}
```

**Error Responses**:

```python
# Bad Request (400)
{
  "detail": "Content parameter is required"
}

# Request Timeout (504)
{
  "detail": "Semantic analysis timeout after 10s"
}

# Internal Server Error (500)
{
  "detail": "Semantic analysis failed: <error message>"
}
```

---

### 2.3 Full Document Extraction (NOT RECOMMENDED FOR PHASE 2)

**Endpoint**: `POST /extract/document`

**Purpose**: Full 6-stage extraction pipeline (use only if you need entity/relationship data)

**Performance**: ~4-7s per request

**Request**: `DocumentExtractionRequest`

```python
{
  "document_path": "/path/to/document.txt",
  "extraction_options": {
    "mode": "comprehensive" | "standard" | "fast",
    "include_semantic_analysis": true,
    "include_relationship_extraction": true,
    "min_confidence_threshold": 0.3,
    "semantic_context": "pattern_matching"
  },
  "update_knowledge_graph": false,
  "emit_events": false
}
```

**Response**: `ExtractionResponse` (see Data Models section)

**Note**: For Phase 2 hybrid scoring, use `/analyze/semantic` instead for better performance.

---

### 2.4 Statistics (Optional)

**Endpoint**: `GET /statistics`

**Purpose**: Service performance metrics

**Response**:
```python
{
  "service_statistics": {
    "uptime": 3600.0,
    "total_extractions": 1523,
    "average_extraction_time": 4.2
  },
  "extraction_statistics": {
    "language_extractor": {...},
    "structured_extractor": {...},
    "semantic_extractor": {...}
  },
  "knowledge_graph_statistics": {...},
  "timestamp": "2025-10-02T12:00:00Z"
}
```

---

## 3. Data Models & Contracts

### 3.1 SemanticAnalysisResult (Primary Contract)

**Full Type Definition**:

```python
from typing import List, Dict, Any
from pydantic import BaseModel, Field

class SemanticPattern(BaseModel):
    """Individual semantic pattern detected in content"""

    pattern_id: str = Field(..., description="Unique pattern identifier")
    pattern_type: str = Field(..., description="THEME | TOPIC | NUMBERED_LIST | BULLET_LIST | etc.")
    pattern_name: str = Field(..., description="Human-readable pattern name")
    description: str = Field(..., description="Pattern description")
    examples: List[str] = Field(default_factory=list, description="Example instances")
    frequency: int = Field(default=1, ge=1, description="Occurrence count")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence")
    significance_score: float = Field(None, ge=0.0, le=1.0, description="Significance")
    context: Dict[str, Any] = Field(default_factory=dict, description="Context metadata")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional properties")
    related_entity_ids: List[str] = Field(default_factory=list, description="Related entities")


class SemanticAnalysisResult(BaseModel):
    """Primary output contract for semantic pattern extraction"""

    semantic_patterns: List[SemanticPattern] = Field(
        default_factory=list,
        description="List of detected semantic patterns"
    )

    concepts: List[str] = Field(
        default_factory=list,
        description="Extracted key concepts (15+ frequent meaningful words)"
    )

    themes: List[str] = Field(
        default_factory=list,
        description="Major themes identified in content"
    )

    # Semantic metrics (all 0.0-1.0 range)
    semantic_density: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How semantically dense the content is"
    )

    conceptual_coherence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How coherent the concepts are"
    )

    thematic_consistency: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Thematic consistency measure"
    )

    # Semantic context
    semantic_context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Analysis metadata (language, length, timestamp, etc.)"
    )

    domain_indicators: List[str] = Field(
        default_factory=list,
        description="Domain-specific terms found (technology, business, etc.)"
    )

    # Topic analysis
    primary_topics: List[str] = Field(
        default_factory=list,
        description="Top 5 topics by weight"
    )

    topic_weights: Dict[str, float] = Field(
        default_factory=dict,
        description="Weight for each topic (0.0-1.0)"
    )
```

**Validation Examples**:

```python
def validate_semantic_analysis_result(result: Dict[str, Any]) -> bool:
    """Validate SemanticAnalysisResult structure"""

    # Required fields
    required_fields = [
        "semantic_patterns",
        "concepts",
        "themes",
        "semantic_density",
        "conceptual_coherence",
        "thematic_consistency",
        "semantic_context",
        "domain_indicators",
        "primary_topics",
        "topic_weights"
    ]

    for field in required_fields:
        if field not in result:
            raise ValueError(f"Missing required field: {field}")

    # Type validation
    assert isinstance(result["semantic_patterns"], list)
    assert isinstance(result["concepts"], list)
    assert isinstance(result["themes"], list)
    assert isinstance(result["semantic_context"], dict)
    assert isinstance(result["domain_indicators"], list)
    assert isinstance(result["primary_topics"], list)
    assert isinstance(result["topic_weights"], dict)

    # Range validation for metrics
    assert 0.0 <= result["semantic_density"] <= 1.0
    assert 0.0 <= result["conceptual_coherence"] <= 1.0
    assert 0.0 <= result["thematic_consistency"] <= 1.0

    # Validate semantic_patterns structure
    for pattern in result["semantic_patterns"]:
        assert "pattern_id" in pattern
        assert "pattern_type" in pattern
        assert "confidence_score" in pattern
        assert 0.0 <= pattern["confidence_score"] <= 1.0

    return True
```

---

### 3.2 HealthStatus Contract

```python
class HealthStatus(BaseModel):
    """Service health check response"""

    status: str = Field(..., description="healthy | degraded | unhealthy")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="1.0.0")

    components: Dict[str, str] = Field(
        default_factory=dict,
        description="Component health status"
    )

    uptime_seconds: Optional[float] = Field(None, ge=0.0)
    memory_usage_mb: Optional[float] = Field(None, ge=0.0)
    cpu_usage_percent: Optional[float] = Field(None, ge=0.0, le=100.0)

    error: Optional[str] = Field(None, description="Error message if unhealthy")
    warnings: List[str] = Field(default_factory=list)
```

---

### 3.3 Error Response Contract

```python
class ErrorResponse(BaseModel):
    """Standard error response format"""

    detail: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

    # Optional debugging information
    error_type: Optional[str] = Field(None, description="Error class name")
    stack_trace: Optional[str] = Field(None, description="Stack trace (dev only)")
```

---

## 4. Integration Patterns

### 4.1 Recommended: Async HTTP Client with Caching

**Implementation**:

```python
import httpx
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

class LangextractClient:
    """Production-ready langextract HTTP client with caching"""

    def __init__(
        self,
        base_url: str = "http://langextract:8156",
        timeout: float = 10.0,
        max_retries: int = 3,
        enable_cache: bool = True,
        cache_ttl_seconds: int = 3600
    ):
        self.base_url = base_url
        self.timeout = httpx.Timeout(timeout, connect=5.0)
        self.max_retries = max_retries
        self.enable_cache = enable_cache
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)

        # HTTP client
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )

        # In-memory cache
        self._cache: Dict[str, Tuple[SemanticAnalysisResult, datetime]] = {}

    def _get_cache_key(self, content: str) -> str:
        """Generate cache key from content hash"""
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_from_cache(self, content: str) -> Optional[SemanticAnalysisResult]:
        """Get from cache if available and not expired"""
        if not self.enable_cache:
            return None

        cache_key = self._get_cache_key(content)
        if cache_key in self._cache:
            result, timestamp = self._cache[cache_key]
            if datetime.utcnow() - timestamp < self.cache_ttl:
                return result
            else:
                del self._cache[cache_key]  # Expired

        return None

    def _set_in_cache(self, content: str, result: SemanticAnalysisResult):
        """Cache the result"""
        if self.enable_cache:
            cache_key = self._get_cache_key(content)
            self._cache[cache_key] = (result, datetime.utcnow())

    async def analyze_semantic(
        self,
        content: str,
        context: Optional[str] = None,
        language: str = "en"
    ) -> SemanticAnalysisResult:
        """
        Analyze semantic content with caching and retries

        Args:
            content: Text to analyze
            context: Optional context hint
            language: Language code

        Returns:
            SemanticAnalysisResult

        Raises:
            LangextractError: On API errors
            LangextractTimeoutError: On timeout
            LangextractUnavailableError: On service unavailable
        """
        # Check cache first
        cached_result = self._get_from_cache(content)
        if cached_result:
            logger.debug(f"Cache hit for content hash: {self._get_cache_key(content)[:8]}")
            return cached_result

        # Make API request with retries
        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    f"{self.base_url}/analyze/semantic",
                    params={
                        "content": content,
                        "context": context,
                        "language": language
                    }
                )

                # Check status
                if response.status_code == 200:
                    data = response.json()
                    result = SemanticAnalysisResult(**data)

                    # Cache successful result
                    self._set_in_cache(content, result)

                    return result
                elif response.status_code == 503:
                    # Service unavailable - retry
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    raise LangextractUnavailableError("Service unavailable after retries")
                else:
                    # Other error - don't retry
                    raise LangextractError(
                        f"API error: {response.status_code} - {response.text}"
                    )

            except httpx.TimeoutException:
                if attempt < self.max_retries - 1:
                    continue
                raise LangextractTimeoutError(f"Request timeout after {self.timeout.read}s")
            except httpx.ConnectError:
                raise LangextractUnavailableError("Cannot connect to langextract service")

        raise LangextractError("Max retries exceeded")

    async def health_check(self) -> bool:
        """Check if service is healthy"""
        try:
            response = await self.client.get(
                f"{self.base_url}/health",
                timeout=5.0
            )
            data = response.json()
            return data.get("status") == "healthy"
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Custom exceptions
class LangextractError(Exception):
    """Base exception for langextract errors"""
    pass

class LangextractTimeoutError(LangextractError):
    """Request timeout"""
    pass

class LangextractUnavailableError(LangextractError):
    """Service unavailable"""
    pass
```

**Usage Example**:

```python
async def get_semantic_patterns(task_description: str):
    client = LangextractClient(
        timeout=10.0,
        enable_cache=True,
        cache_ttl_seconds=3600
    )

    try:
        result = await client.analyze_semantic(
            content=task_description,
            context="pattern_matching",
            language="en"
        )

        print(f"Found {len(result.semantic_patterns)} patterns")
        print(f"Concepts: {result.concepts[:5]}")
        print(f"Themes: {result.themes[:3]}")

        return result

    except LangextractTimeoutError:
        logger.error("Langextract timeout - falling back to vector-only scoring")
        return None
    except LangextractUnavailableError:
        logger.error("Langextract unavailable - falling back to vector-only scoring")
        return None
    finally:
        await client.close()
```

---

### 4.2 Circuit Breaker Pattern (Recommended for Production)

```python
from pybreaker import CircuitBreaker, CircuitBreakerError

# Configure circuit breaker
langextract_breaker = CircuitBreaker(
    fail_max=5,              # Open after 5 consecutive failures
    reset_timeout=60,        # Try again after 60s
    exclude=[LangextractTimeoutError]  # Don't count timeouts as failures
)

@langextract_breaker
async def analyze_with_circuit_breaker(client: LangextractClient, content: str):
    """Analyze with circuit breaker protection"""
    return await client.analyze_semantic(content)


# Usage
try:
    result = await analyze_with_circuit_breaker(client, task_description)
except CircuitBreakerError:
    logger.warning("Circuit breaker open - langextract unavailable")
    # Fallback to vector-only scoring
    result = None
```

---

## 5. Error Handling

### 5.1 Error Hierarchy

```python
Exception
├── LangextractError (base)
│   ├── LangextractTimeoutError (request timeout)
│   ├── LangextractUnavailableError (service down)
│   ├── LangextractValidationError (invalid response)
│   └── LangextractRateLimitError (rate limit exceeded)
```

### 5.2 Error Handling Strategy

```python
async def hybrid_scoring_with_fallback(
    task_description: str,
    vector_similarity_score: float
) -> float:
    """
    Calculate hybrid score with graceful fallback to vector-only

    Error Handling:
      1. Timeout → Use vector-only score (no pattern enrichment)
      2. Service unavailable → Use vector-only score
      3. Invalid response → Log error, use vector-only score
      4. Circuit breaker open → Use vector-only score
    """

    try:
        # Try to get semantic patterns
        semantic_result = await langextract_client.analyze_semantic(
            task_description,
            context="pattern_matching"
        )

        # Calculate pattern similarity
        pattern_similarity = calculate_pattern_similarity(
            task_semantic=semantic_result,
            pattern_semantic=historical_pattern_semantic
        )

        # Combine scores
        hybrid_score = (
            vector_similarity_score * 0.7 +
            pattern_similarity * 0.3
        )

        logger.info(f"Hybrid score: {hybrid_score:.3f} (vector: {vector_similarity_score:.3f}, pattern: {pattern_similarity:.3f})")
        return hybrid_score

    except LangextractTimeoutError:
        logger.warning("Langextract timeout - using vector-only score")
        metrics.langextract_fallback_total.inc(labels={"reason": "timeout"})
        return vector_similarity_score

    except LangextractUnavailableError:
        logger.warning("Langextract unavailable - using vector-only score")
        metrics.langextract_fallback_total.inc(labels={"reason": "unavailable"})
        return vector_similarity_score

    except LangextractValidationError as e:
        logger.error(f"Invalid langextract response: {e} - using vector-only score")
        metrics.langextract_fallback_total.inc(labels={"reason": "validation_error"})
        return vector_similarity_score

    except CircuitBreakerError:
        logger.warning("Circuit breaker open - using vector-only score")
        metrics.langextract_fallback_total.inc(labels={"reason": "circuit_breaker"})
        return vector_similarity_score

    except Exception as e:
        logger.error(f"Unexpected error in hybrid scoring: {e} - using vector-only score")
        metrics.langextract_fallback_total.inc(labels={"reason": "unknown"})
        return vector_similarity_score
```

---

## 6. Testing Strategy

### 6.1 Unit Tests

```python
# File: tests/unit/test_langextract_client.py

import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_analyze_semantic_success():
    """Test successful semantic analysis"""
    client = LangextractClient()

    # Mock successful response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "semantic_patterns": [],
        "concepts": ["machine", "learning"],
        "themes": ["AI"],
        "semantic_density": 0.5,
        "conceptual_coherence": 0.7,
        "thematic_consistency": 0.6,
        "semantic_context": {},
        "domain_indicators": ["algorithm"],
        "primary_topics": ["ML"],
        "topic_weights": {"ML": 0.8}
    }

    with patch.object(client.client, 'post', return_value=mock_response):
        result = await client.analyze_semantic("test content")

        assert isinstance(result, SemanticAnalysisResult)
        assert "machine" in result.concepts
        assert result.semantic_density == 0.5


@pytest.mark.asyncio
async def test_analyze_semantic_timeout():
    """Test timeout handling"""
    client = LangextractClient(timeout=1.0)

    with patch.object(client.client, 'post', side_effect=httpx.TimeoutException("timeout")):
        with pytest.raises(LangextractTimeoutError):
            await client.analyze_semantic("test content")


@pytest.mark.asyncio
async def test_analyze_semantic_cache_hit():
    """Test cache hit"""
    client = LangextractClient(enable_cache=True)

    # First call - should hit API
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "semantic_patterns": [],
        "concepts": ["test"],
        "themes": [],
        "semantic_density": 0.5,
        "conceptual_coherence": 0.7,
        "thematic_consistency": 0.6,
        "semantic_context": {},
        "domain_indicators": [],
        "primary_topics": [],
        "topic_weights": {}
    }

    with patch.object(client.client, 'post', return_value=mock_response) as mock_post:
        result1 = await client.analyze_semantic("test content")
        result2 = await client.analyze_semantic("test content")

        # Should only call API once (second is cached)
        assert mock_post.call_count == 1
        assert result1 == result2
```

### 6.2 Integration Tests

```python
# File: tests/integration/test_langextract_integration.py

@pytest.mark.integration
@pytest.mark.asyncio
async def test_langextract_service_available():
    """Test actual langextract service availability"""
    client = LangextractClient(base_url="http://localhost:8156")

    # Health check
    is_healthy = await client.health_check()
    assert is_healthy, "Langextract service not healthy"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_semantic_analysis_real_service():
    """Test semantic analysis against real service"""
    client = LangextractClient(base_url="http://localhost:8156")

    test_content = """
    Machine learning is a subset of artificial intelligence that enables
    computers to learn from data without being explicitly programmed.
    Neural networks are a key component of deep learning systems.
    """

    result = await client.analyze_semantic(test_content)

    # Validate response structure
    assert isinstance(result, SemanticAnalysisResult)
    assert len(result.concepts) > 0
    assert len(result.semantic_patterns) > 0

    # Validate expected concepts found
    concepts_lower = [c.lower() for c in result.concepts]
    assert "machine" in concepts_lower or "learning" in concepts_lower

    # Validate metrics in valid range
    assert 0.0 <= result.semantic_density <= 1.0
    assert 0.0 <= result.conceptual_coherence <= 1.0
```

---

## 7. Performance Specifications

### 7.1 Latency Targets

```yaml
Endpoint: POST /analyze/semantic

Uncached Request:
  Target: < 5s
  p50: 3-4s
  p95: 4-5s
  p99: 5-6s

Cached Request (via client-side cache):
  Target: < 100ms
  p50: 10-20ms
  p95: 50-80ms
  p99: 100-150ms

Overall Hybrid Scoring (with cache):
  Target: < 1s
  p50: 500-800ms
  p95: 1-2s
  p99: 2-3s
```

### 7.2 Throughput Targets

```yaml
Concurrent Requests:
  Target: 10 req/s sustained
  Max burst: 50 req/s for 30s

Cache Hit Rate:
  Target: > 80% after warmup
  Warmup period: 100 requests or 1 hour

Success Rate:
  Target: > 99.5% (with fallback to vector-only)
  Service uptime: > 99.0%
```

### 7.3 Resource Limits

```yaml
HTTP Client Configuration:
  Timeout (connect): 5s
  Timeout (read): 10s
  Max connections: 100
  Max keepalive connections: 20
  Retry attempts: 3
  Retry backoff: Exponential (2^attempt seconds)

Cache Configuration:
  Max size: 1000 entries
  TTL: 1 hour (3600s)
  Eviction policy: LRU
  Memory estimate: ~50-100MB (depending on content size)
```

---

## Appendix A: Complete Example Integration

```python
# File: services/intelligence/src/pattern_learning/hybrid_scorer_with_langextract.py

import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class HybridScoringResult:
    """Result of hybrid scoring operation"""
    hybrid_score: float
    vector_score: float
    pattern_score: Optional[float]
    used_patterns: bool
    latency_ms: float
    cache_hit: bool


class HybridScorerWithLangextract:
    """Production hybrid scorer with langextract integration"""

    def __init__(
        self,
        langextract_client: LangextractClient,
        vector_weight: float = 0.7,
        pattern_weight: float = 0.3
    ):
        self.langextract = langextract_client
        self.vector_weight = vector_weight
        self.pattern_weight = pattern_weight

    async def score_similarity(
        self,
        task_description: str,
        historical_pattern_text: str,
        vector_similarity: float
    ) -> HybridScoringResult:
        """
        Calculate hybrid similarity score

        Args:
            task_description: New task characteristics
            historical_pattern_text: Historical pattern description
            vector_similarity: Pre-computed vector similarity (from Qdrant)

        Returns:
            HybridScoringResult with scores and metadata
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Get semantic analysis for both texts
            task_semantic, pattern_semantic = await asyncio.gather(
                self.langextract.analyze_semantic(task_description),
                self.langextract.analyze_semantic(historical_pattern_text)
            )

            # Calculate pattern similarity
            pattern_similarity = self._calculate_pattern_similarity(
                task_semantic,
                pattern_semantic
            )

            # Combine scores
            hybrid_score = (
                vector_similarity * self.vector_weight +
                pattern_similarity * self.pattern_weight
            )

            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            return HybridScoringResult(
                hybrid_score=hybrid_score,
                vector_score=vector_similarity,
                pattern_score=pattern_similarity,
                used_patterns=True,
                latency_ms=latency_ms,
                cache_hit=False  # TODO: Track from client
            )

        except (LangextractTimeoutError, LangextractUnavailableError):
            # Fallback to vector-only
            latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            return HybridScoringResult(
                hybrid_score=vector_similarity,
                vector_score=vector_similarity,
                pattern_score=None,
                used_patterns=False,
                latency_ms=latency_ms,
                cache_hit=False
            )

    def _calculate_pattern_similarity(
        self,
        task_semantic: SemanticAnalysisResult,
        pattern_semantic: SemanticAnalysisResult
    ) -> float:
        """Calculate pattern-based similarity"""

        # Concept overlap (30%)
        task_concepts = set(c.lower() for c in task_semantic.concepts)
        pattern_concepts = set(c.lower() for c in pattern_semantic.concepts)
        concept_score = len(task_concepts & pattern_concepts) / \
                       len(task_concepts | pattern_concepts) if \
                       (task_concepts | pattern_concepts) else 0.0

        # Theme similarity (20%)
        task_themes = set(t.lower() for t in task_semantic.themes)
        pattern_themes = set(t.lower() for t in pattern_semantic.themes)
        theme_score = len(task_themes & pattern_themes) / \
                     len(task_themes | pattern_themes) if \
                     (task_themes | pattern_themes) else 0.0

        # Domain alignment (20%)
        task_domains = set(d.lower() for d in task_semantic.domain_indicators)
        pattern_domains = set(d.lower() for d in pattern_semantic.domain_indicators)
        domain_score = len(task_domains & pattern_domains) / \
                      len(task_domains | pattern_domains) if \
                      (task_domains | pattern_domains) else 0.0

        # Structural pattern match (15%)
        task_pattern_types = {p.pattern_type for p in task_semantic.semantic_patterns}
        pattern_pattern_types = {p.pattern_type for p in pattern_semantic.semantic_patterns}
        structure_score = len(task_pattern_types & pattern_pattern_types) / \
                         len(task_pattern_types | pattern_pattern_types) if \
                         (task_pattern_types | pattern_pattern_types) else 0.0

        # Relationship type match (15%) - not available in semantic-only endpoint
        relationship_score = 0.0

        # Weighted combination
        pattern_similarity = (
            concept_score * 0.30 +
            theme_score * 0.20 +
            domain_score * 0.20 +
            structure_score * 0.15 +
            relationship_score * 0.15
        )

        return pattern_similarity


# Usage example
async def main():
    # Initialize client
    client = LangextractClient(
        base_url="http://langextract:8156",
        timeout=10.0,
        enable_cache=True
    )

    # Initialize scorer
    scorer = HybridScorerWithLangextract(
        langextract_client=client,
        vector_weight=0.7,
        pattern_weight=0.3
    )

    # Score similarity
    result = await scorer.score_similarity(
        task_description="Implement OAuth2 authentication with JWT tokens",
        historical_pattern_text="Build user authentication using OAuth2 protocol",
        vector_similarity=0.85
    )

    print(f"Hybrid score: {result.hybrid_score:.3f}")
    print(f"Used patterns: {result.used_patterns}")
    print(f"Latency: {result.latency_ms:.1f}ms")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Appendix B: Monitoring & Metrics

```python
# Prometheus metrics for langextract integration

from prometheus_client import Counter, Histogram, Gauge

# Request metrics
langextract_requests_total = Counter(
    'langextract_requests_total',
    'Total langextract API requests',
    ['endpoint', 'status']
)

langextract_request_duration = Histogram(
    'langextract_request_duration_seconds',
    'Langextract request duration',
    ['endpoint']
)

# Cache metrics
langextract_cache_hits = Counter(
    'langextract_cache_hits_total',
    'Total cache hits'
)

langextract_cache_misses = Counter(
    'langextract_cache_misses_total',
    'Total cache misses'
)

langextract_cache_hit_rate = Gauge(
    'langextract_cache_hit_rate',
    'Current cache hit rate'
)

# Fallback metrics
langextract_fallback_total = Counter(
    'langextract_fallback_total',
    'Total fallbacks to vector-only scoring',
    ['reason']  # timeout, unavailable, validation_error, circuit_breaker
)

# Hybrid scoring metrics
hybrid_scoring_duration = Histogram(
    'hybrid_scoring_duration_seconds',
    'Hybrid scoring calculation duration'
)

pattern_similarity_score = Histogram(
    'pattern_similarity_score',
    'Pattern similarity scores distribution'
)
```

---

**Integration Specification Complete**: Ready for implementation
**Last Updated**: 2025-10-02
**See Also**:
- `LANGEXTRACT_HYBRID_INVESTIGATION.md` - Capabilities analysis
- `PHASE2_HYBRID_PLAN.md` - 8-agent implementation plan
