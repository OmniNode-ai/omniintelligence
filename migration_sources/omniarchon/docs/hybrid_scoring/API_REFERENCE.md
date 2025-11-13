# Hybrid Scoring API Reference

**Version**: 1.0.0
**Last Updated**: 2025-10-02
**Track**: Phase 2 - Pattern Learning Enhancement

---

## Table of Contents

1. [Overview](#overview)
2. [Core Components](#core-components)
3. [Client APIs](#client-apis)
4. [Cache APIs](#cache-apis)
5. [Scoring APIs](#scoring-apis)
6. [Error Handling](#error-handling)
7. [Code Examples](#code-examples)
8. [Performance Characteristics](#performance-characteristics)

---

## Overview

The Hybrid Scoring system combines vector-based similarity (Ollama + Qdrant) with semantic pattern analysis (langextract) to provide comprehensive pattern matching for the Pattern Learning Engine.

### Key Features

- **Dual Scoring**: 70% vector similarity + 30% pattern similarity
- **Intelligent Caching**: Multi-tier LRU + TTL cache with >80% hit rate
- **Graceful Degradation**: Falls back to vector-only if langextract unavailable
- **Adaptive Weights**: Adjusts scoring weights based on task characteristics
- **Production Ready**: Circuit breaker, retry logic, comprehensive monitoring

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│              Hybrid Scoring Pipeline                      │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  Task Description                                         │
│       ↓                                                   │
│  ┌─────────────────────┬─────────────────────┐          │
│  │                     │                     │          │
│  │  Vector Similarity  │  Semantic Patterns  │          │
│  │  (Ollama+Qdrant)    │  (Langextract)      │          │
│  │  ~150-300ms         │  ~500ms-5s          │          │
│  │  Score: 0.0-1.0     │  Score: 0.0-1.0     │          │
│  │                     │  (cached: <100ms)   │          │
│  └─────────────────────┴─────────────────────┘          │
│                     ↓                                     │
│             Hybrid Combiner                               │
│         (70% vector + 30% pattern)                        │
│                     ↓                                     │
│           Final Score: 0.0-1.0                            │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

---

## Core Components

### Component Hierarchy

```python
hybrid_scoring/
├── langextract_client.py    # HTTP client for langextract service
├── semantic_cache.py         # Multi-tier caching layer
├── pattern_similarity.py     # Pattern similarity scoring
├── hybrid_scorer.py          # Hybrid score combination
├── cache_optimizer.py        # Cache performance optimization
└── metrics.py                # Prometheus metrics instrumentation
```

---

## Client APIs

### LangextractClient

**Module**: `services.intelligence.src.pattern_learning.langextract_client`

#### Class Definition

```python
class LangextractClient:
    """
    Async HTTP client for langextract semantic analysis service

    Features:
      • Circuit breaker pattern for fault tolerance
      • Automatic retry with exponential backoff
      • Configurable timeout (default: 5s)
      • Health checking with periodic polling
      • Comprehensive error logging
    """
```

#### Constructor

```python
def __init__(
    self,
    base_url: str = "http://langextract:8156",
    timeout: float = 5.0,
    max_retries: int = 3,
    circuit_breaker_threshold: int = 5,
    circuit_breaker_timeout: int = 60
)
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `base_url` | `str` | `http://langextract:8156` | Langextract service URL |
| `timeout` | `float` | `5.0` | Request timeout in seconds |
| `max_retries` | `int` | `3` | Maximum retry attempts |
| `circuit_breaker_threshold` | `int` | `5` | Failures before circuit opens |
| `circuit_breaker_timeout` | `int` | `60` | Seconds before retry after open |

**Example**:

```python
client = LangextractClient(
    base_url="http://langextract:8156",
    timeout=10.0,
    max_retries=3
)
```

#### Methods

##### analyze_semantic()

```python
async def analyze_semantic(
    self,
    content: str,
    context: Optional[str] = None,
    language: str = "en"
) -> SemanticAnalysisResult
```

**Purpose**: Extract semantic patterns, concepts, and themes from text content.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | `str` | Yes | Text content to analyze |
| `context` | `Optional[str]` | No | Context hint (e.g., "pattern_matching") |
| `language` | `str` | No | Language code (default: "en") |

**Returns**: `SemanticAnalysisResult` containing:
- `semantic_patterns`: List of detected semantic patterns
- `concepts`: Extracted key concepts (15+ terms)
- `themes`: Major themes identified
- `semantic_density`: Semantic density score (0.0-1.0)
- `conceptual_coherence`: Concept coherence score (0.0-1.0)
- `thematic_consistency`: Theme consistency score (0.0-1.0)
- `domain_indicators`: Domain-specific terms
- `primary_topics`: Top 5 topics
- `topic_weights`: Weight for each topic

**Raises**:
- `LangextractTimeoutError`: Request timeout (>5s)
- `LangextractUnavailableError`: Service unavailable
- `LangextractError`: Other API errors
- `CircuitBreakerError`: Circuit breaker open

**Example**:

```python
try:
    result = await client.analyze_semantic(
        content="Implement OAuth2 authentication with JWT tokens",
        context="pattern_matching",
        language="en"
    )

    print(f"Found {len(result.semantic_patterns)} patterns")
    print(f"Concepts: {result.concepts[:5]}")
    print(f"Themes: {result.themes}")
    print(f"Semantic density: {result.semantic_density:.2f}")

except LangextractTimeoutError:
    print("Request timeout - langextract took too long")
except LangextractUnavailableError:
    print("Service unavailable - falling back to vector-only")
except CircuitBreakerError:
    print("Circuit breaker open - too many failures")
```

**Performance**:
- Uncached: 3-5s (p95)
- Cached (via SemanticCache): <100ms (p95)
- Timeout: 5s default

##### health_check()

```python
async def health_check(self) -> bool
```

**Purpose**: Check if langextract service is healthy and reachable.

**Returns**: `bool` - True if service is healthy, False otherwise

**Example**:

```python
is_healthy = await client.health_check()
if not is_healthy:
    logger.warning("Langextract service is unhealthy")
```

**Performance**: <1s typical response time

##### close()

```python
async def close(self) -> None
```

**Purpose**: Close HTTP client and release resources.

**Example**:

```python
await client.close()
```

---

## Cache APIs

### SemanticCache

**Module**: `services.intelligence.src.pattern_learning.semantic_cache`

#### Class Definition

```python
class SemanticCache:
    """
    TTL-based LRU cache for semantic analysis results

    Features:
      • Content-based cache keys (SHA256 hash)
      • TTL expiration (default: 1 hour)
      • Hit/miss metrics tracking
      • Optional Redis backend for distributed caching
      • Cache warming from historical data
    """
```

#### Constructor

```python
def __init__(
    self,
    max_size: int = 1000,
    ttl_seconds: int = 3600,
    redis_client: Optional[redis.Redis] = None
)
```

**Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_size` | `int` | `1000` | Maximum cache entries |
| `ttl_seconds` | `int` | `3600` | Time-to-live in seconds (1 hour) |
| `redis_client` | `Optional[redis.Redis]` | `None` | Optional Redis for persistence |

**Example**:

```python
# In-memory cache only
cache = SemanticCache(max_size=1000, ttl_seconds=3600)

# With Redis backend
import redis
redis_client = redis.Redis(host='localhost', port=6379, db=0)
cache = SemanticCache(
    max_size=1000,
    ttl_seconds=3600,
    redis_client=redis_client
)
```

#### Methods

##### get()

```python
async def get(self, content: str) -> Optional[SemanticAnalysisResult]
```

**Purpose**: Get cached semantic analysis result.

**Parameters**:
- `content` (str): Text content (used for cache key generation)

**Returns**: `SemanticAnalysisResult` if cached and not expired, `None` otherwise

**Example**:

```python
cached_result = await cache.get(task_description)
if cached_result:
    print(f"Cache hit! Found {len(cached_result.concepts)} concepts")
else:
    print("Cache miss - need to fetch from langextract")
```

##### set()

```python
async def set(
    self,
    content: str,
    result: SemanticAnalysisResult
) -> None
```

**Purpose**: Cache semantic analysis result with TTL.

**Parameters**:
- `content` (str): Text content (for cache key)
- `result` (SemanticAnalysisResult): Result to cache

**Example**:

```python
result = await client.analyze_semantic(task_description)
await cache.set(task_description, result)
```

##### warm_cache()

```python
async def warm_cache(
    self,
    content_samples: List[str],
    langextract_client: LangextractClient
) -> int
```

**Purpose**: Pre-populate cache with semantic analyses for common patterns.

**Parameters**:
- `content_samples` (List[str]): List of content samples to analyze and cache
- `langextract_client` (LangextractClient): Client for fetching analyses

**Returns**: `int` - Number of samples successfully cached

**Example**:

```python
# Warm cache with historical task descriptions
historical_tasks = [
    "Implement user authentication",
    "Create REST API endpoint",
    "Write unit tests"
]

warmed_count = await cache.warm_cache(historical_tasks, client)
print(f"Warmed cache with {warmed_count} entries")
```

##### get_metrics()

```python
def get_metrics(self) -> Dict[str, Any]
```

**Purpose**: Get cache performance metrics.

**Returns**: Dictionary with metrics:

```python
{
    "hit_rate": 0.85,           # Cache hit rate (0.0-1.0)
    "hits": 850,                # Total cache hits
    "misses": 150,              # Total cache misses
    "evictions": 25,            # Total LRU evictions
    "total_requests": 1000,     # Total requests
    "current_size": 975,        # Current entries in cache
    "max_size": 1000,           # Maximum cache size
    "ttl_seconds": 3600         # TTL configuration
}
```

**Example**:

```python
metrics = cache.get_metrics()
print(f"Cache hit rate: {metrics['hit_rate']:.1%}")
print(f"Current size: {metrics['current_size']}/{metrics['max_size']}")
```

---

## Scoring APIs

### PatternSimilarityScorer

**Module**: `services.intelligence.src.pattern_learning.pattern_similarity`

#### Class Definition

```python
class PatternSimilarityScorer:
    """
    Calculate pattern-based similarity between task and historical patterns

    Components:
      1. Concept Overlap (30%): Jaccard similarity of concepts
      2. Theme Similarity (20%): Jaccard similarity of themes
      3. Domain Alignment (20%): Domain indicator overlap
      4. Structural Pattern Match (15%): Pattern type overlap
      5. Relationship Type Match (15%): Relationship type overlap

    Performance: <100ms per comparison
    """
```

#### Constructor

```python
def __init__(self, config: Optional[PatternSimilarityConfig] = None)
```

**Parameters**:
- `config` (Optional[PatternSimilarityConfig]): Custom configuration for component weights

**Example**:

```python
# Default weights (30/20/20/15/15)
scorer = PatternSimilarityScorer()

# Custom weights
from dataclasses import dataclass

@dataclass
class CustomConfig:
    concept_weight: float = 0.40
    theme_weight: float = 0.30
    domain_weight: float = 0.15
    structure_weight: float = 0.10
    relationship_weight: float = 0.05

scorer = PatternSimilarityScorer(config=CustomConfig())
```

#### Methods

##### calculate_similarity()

```python
def calculate_similarity(
    self,
    task_semantic: SemanticAnalysisResult,
    pattern_semantic: SemanticAnalysisResult
) -> Dict[str, float]
```

**Purpose**: Calculate comprehensive pattern similarity.

**Parameters**:
- `task_semantic` (SemanticAnalysisResult): Semantic analysis of task
- `pattern_semantic` (SemanticAnalysisResult): Semantic analysis of historical pattern

**Returns**: Dictionary with component scores and final similarity:

```python
{
    "concept_score": 0.75,      # Concept overlap score
    "theme_score": 0.60,        # Theme similarity score
    "domain_score": 0.85,       # Domain alignment score
    "structure_score": 0.50,    # Structural pattern match
    "relationship_score": 0.0,  # Relationship type match
    "final_similarity": 0.68    # Weighted combination
}
```

**Example**:

```python
# Get semantic analyses
task_semantic = await client.analyze_semantic(task_description)
pattern_semantic = await client.analyze_semantic(historical_pattern_text)

# Calculate similarity
similarity = scorer.calculate_similarity(task_semantic, pattern_semantic)

print(f"Final similarity: {similarity['final_similarity']:.2f}")
print(f"Concept overlap: {similarity['concept_score']:.2f}")
print(f"Theme similarity: {similarity['theme_score']:.2f}")
print(f"Domain alignment: {similarity['domain_score']:.2f}")
```

**Performance**: <100ms typical execution time

---

### HybridScorer

**Module**: `services.intelligence.src.pattern_learning.hybrid_scorer`

#### Class Definition

```python
class HybridScorer:
    """
    Combine vector similarity and pattern similarity into hybrid score

    Features:
      • Configurable weights (default: 70% vector, 30% pattern)
      • Adaptive weight adjustment based on task characteristics
      • Score normalization to [0, 1]
      • Confidence calculation based on component agreement
    """
```

#### Constructor

```python
def __init__(self, config: Optional[HybridScoringConfig] = None)
```

**Parameters**:
- `config` (Optional[HybridScoringConfig]): Custom configuration for weights and adaptive tuning

**Example**:

```python
# Default configuration (70/30 weights, adaptive enabled)
scorer = HybridScorer()

# Custom configuration
from dataclasses import dataclass

@dataclass
class CustomConfig:
    default_vector_weight: float = 0.8
    default_pattern_weight: float = 0.2
    enable_adaptive_weights: bool = False

scorer = HybridScorer(config=CustomConfig())
```

#### Methods

##### calculate_hybrid_score()

```python
def calculate_hybrid_score(
    self,
    vector_similarity: float,
    pattern_similarity: float,
    task_characteristics: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

**Purpose**: Calculate hybrid similarity score from vector and pattern components.

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `vector_similarity` | `float` | Yes | Vector similarity (0.0-1.0) from Qdrant |
| `pattern_similarity` | `float` | Yes | Pattern similarity (0.0-1.0) |
| `task_characteristics` | `Optional[Dict]` | No | Metadata for adaptive weight tuning |

**Returns**: Dictionary with hybrid score and metadata:

```python
{
    "hybrid_score": 0.75,       # Final hybrid score (0.0-1.0)
    "vector_score": 0.80,       # Input vector score
    "pattern_score": 0.60,      # Input pattern score
    "vector_weight": 0.7,       # Applied vector weight
    "pattern_weight": 0.3,      # Applied pattern weight
    "weights_adjusted": False,  # Whether weights were adapted
    "confidence": 0.85          # Confidence in prediction (0.0-1.0)
}
```

**Example**:

```python
# Basic hybrid scoring
result = scorer.calculate_hybrid_score(
    vector_similarity=0.85,
    pattern_similarity=0.72
)
print(f"Hybrid score: {result['hybrid_score']:.2f}")

# With adaptive weights
task_metadata = {
    "complexity_level": "high",
    "domain": "technology"
}

result = scorer.calculate_hybrid_score(
    vector_similarity=0.85,
    pattern_similarity=0.72,
    task_characteristics=task_metadata
)

print(f"Hybrid score: {result['hybrid_score']:.2f}")
print(f"Weights adjusted: {result['weights_adjusted']}")
print(f"Vector weight: {result['vector_weight']:.1%}")
print(f"Pattern weight: {result['pattern_weight']:.1%}")
print(f"Confidence: {result['confidence']:.2f}")
```

**Adaptive Weight Rules**:

| Task Characteristic | Vector Weight | Pattern Weight | Rationale |
|---------------------|---------------|----------------|-----------|
| High complexity | 60% | 40% | Need deeper structural analysis |
| Low complexity | 80% | 20% | Simple semantic matching sufficient |
| Domain-specific | 60% | 40% | Leverage domain classification |
| General | 70% | 30% | Default balanced approach |

**Performance**: <10ms typical execution time

---

## Error Handling

### Exception Hierarchy

```python
Exception
├── LangextractError (base)
│   ├── LangextractTimeoutError      # Request timeout (>5s)
│   ├── LangextractUnavailableError  # Service down/unreachable
│   ├── LangextractValidationError   # Invalid response format
│   └── LangextractRateLimitError    # Rate limit exceeded
```

### Error Response Format

All API errors include structured error information:

```python
{
    "detail": "Error message",
    "status_code": 500,
    "timestamp": "2025-10-02T12:00:00Z",
    "error_type": "LangextractTimeoutError",
    "stack_trace": "..." # Development only
}
```

### Error Handling Best Practices

#### 1. Graceful Degradation

```python
async def hybrid_scoring_with_fallback(
    task_description: str,
    vector_similarity: float
) -> float:
    """
    Calculate hybrid score with fallback to vector-only
    """
    try:
        # Try hybrid scoring
        task_semantic = await langextract_client.analyze_semantic(
            task_description
        )
        pattern_semantic = await langextract_client.analyze_semantic(
            historical_pattern_text
        )

        pattern_similarity = pattern_scorer.calculate_similarity(
            task_semantic, pattern_semantic
        )["final_similarity"]

        result = hybrid_scorer.calculate_hybrid_score(
            vector_similarity, pattern_similarity
        )

        return result["hybrid_score"]

    except (LangextractTimeoutError, LangextractUnavailableError):
        # Fallback to vector-only
        logger.warning("Langextract unavailable - using vector-only score")
        return vector_similarity
```

#### 2. Circuit Breaker Pattern

```python
from pybreaker import CircuitBreaker, CircuitBreakerError

langextract_breaker = CircuitBreaker(
    fail_max=5,              # Open after 5 failures
    reset_timeout=60,        # Retry after 60s
    exclude=[LangextractTimeoutError]  # Don't count timeouts
)

@langextract_breaker
async def analyze_with_protection(content: str):
    return await langextract_client.analyze_semantic(content)

try:
    result = await analyze_with_protection(task_description)
except CircuitBreakerError:
    # Circuit open - service unavailable
    logger.warning("Circuit breaker open - falling back")
    return None
```

#### 3. Retry Logic

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
async def analyze_with_retry(content: str):
    return await langextract_client.analyze_semantic(content)

try:
    result = await analyze_with_retry(task_description)
except LangextractError as e:
    logger.error(f"All retries failed: {e}")
```

---

## Code Examples

### Example 1: Basic Hybrid Scoring

```python
import asyncio
from langextract_client import LangextractClient
from semantic_cache import SemanticCache
from pattern_similarity import PatternSimilarityScorer
from hybrid_scorer import HybridScorer

async def basic_hybrid_scoring_example():
    """Complete hybrid scoring workflow"""

    # 1. Initialize components
    client = LangextractClient(timeout=10.0)
    cache = SemanticCache(max_size=1000, ttl_seconds=3600)
    pattern_scorer = PatternSimilarityScorer()
    hybrid_scorer = HybridScorer()

    try:
        # 2. Task and historical pattern
        task_description = "Implement OAuth2 authentication with JWT tokens"
        historical_pattern_text = "Build user authentication using OAuth2 protocol"
        vector_similarity = 0.85  # From Phase 1 Qdrant search

        # 3. Get semantic analyses (with caching)
        task_semantic = await cache.get(task_description)
        if not task_semantic:
            task_semantic = await client.analyze_semantic(task_description)
            await cache.set(task_description, task_semantic)

        pattern_semantic = await cache.get(historical_pattern_text)
        if not pattern_semantic:
            pattern_semantic = await client.analyze_semantic(historical_pattern_text)
            await cache.set(historical_pattern_text, pattern_semantic)

        # 4. Calculate pattern similarity
        similarity = pattern_scorer.calculate_similarity(
            task_semantic, pattern_semantic
        )
        pattern_similarity = similarity["final_similarity"]

        # 5. Calculate hybrid score
        result = hybrid_scorer.calculate_hybrid_score(
            vector_similarity=vector_similarity,
            pattern_similarity=pattern_similarity
        )

        # 6. Display results
        print(f"=== Hybrid Scoring Results ===")
        print(f"Vector similarity: {result['vector_score']:.2f}")
        print(f"Pattern similarity: {result['pattern_score']:.2f}")
        print(f"Hybrid score: {result['hybrid_score']:.2f}")
        print(f"Confidence: {result['confidence']:.2f}")

        return result

    finally:
        await client.close()

# Run example
if __name__ == "__main__":
    asyncio.run(basic_hybrid_scoring_example())
```

**Output**:
```
=== Hybrid Scoring Results ===
Vector similarity: 0.85
Pattern similarity: 0.72
Hybrid score: 0.81
Confidence: 0.88
```

### Example 2: Batch Processing with Cache Warming

```python
async def batch_hybrid_scoring_example():
    """Process multiple patterns with cache warming"""

    client = LangextractClient()
    cache = SemanticCache(max_size=1000)
    pattern_scorer = PatternSimilarityScorer()
    hybrid_scorer = HybridScorer()

    # Historical patterns
    historical_patterns = [
        "Implement user authentication",
        "Create REST API endpoint",
        "Write unit tests for service",
        "Deploy to production environment"
    ]

    # Warm cache
    print("Warming cache...")
    warmed_count = await cache.warm_cache(historical_patterns, client)
    print(f"Warmed cache with {warmed_count} patterns")

    # New tasks to score
    new_tasks = [
        "Add OAuth2 authentication",
        "Build GraphQL API",
        "Create integration tests"
    ]

    # Process batch
    for task in new_tasks:
        # Get semantic analysis (cached)
        task_semantic = await cache.get(task)
        if not task_semantic:
            task_semantic = await client.analyze_semantic(task)
            await cache.set(task, task_semantic)

        # Score against all patterns
        best_match = None
        best_score = 0.0

        for pattern_text in historical_patterns:
            pattern_semantic = await cache.get(pattern_text)  # Cache hit!

            pattern_sim = pattern_scorer.calculate_similarity(
                task_semantic, pattern_semantic
            )["final_similarity"]

            hybrid_result = hybrid_scorer.calculate_hybrid_score(
                vector_similarity=0.8,  # Placeholder
                pattern_similarity=pattern_sim
            )

            if hybrid_result["hybrid_score"] > best_score:
                best_score = hybrid_result["hybrid_score"]
                best_match = pattern_text

        print(f"\nTask: {task}")
        print(f"Best match: {best_match}")
        print(f"Score: {best_score:.2f}")

    # Check cache metrics
    metrics = cache.get_metrics()
    print(f"\n=== Cache Metrics ===")
    print(f"Hit rate: {metrics['hit_rate']:.1%}")
    print(f"Hits: {metrics['hits']}, Misses: {metrics['misses']}")

    await client.close()

asyncio.run(batch_hybrid_scoring_example())
```

### Example 3: Production Integration with Error Handling

```python
from typing import Optional
import logging

logger = logging.getLogger(__name__)

class ProductionHybridScorer:
    """Production-ready hybrid scorer with comprehensive error handling"""

    def __init__(self):
        self.client = LangextractClient(timeout=10.0, max_retries=3)
        self.cache = SemanticCache(max_size=1000, ttl_seconds=3600)
        self.pattern_scorer = PatternSimilarityScorer()
        self.hybrid_scorer = HybridScorer()

    async def score_similarity(
        self,
        task_description: str,
        historical_pattern_text: str,
        vector_similarity: float
    ) -> Dict[str, Any]:
        """
        Calculate hybrid similarity with full error handling

        Returns:
            Dict with score and metadata, always succeeds (graceful degradation)
        """
        start_time = asyncio.get_event_loop().time()

        try:
            # Get semantic analyses (with caching)
            task_semantic = await self._get_semantic_cached(task_description)
            pattern_semantic = await self._get_semantic_cached(historical_pattern_text)

            if task_semantic is None or pattern_semantic is None:
                # Langextract unavailable - fallback to vector-only
                return {
                    "hybrid_score": vector_similarity,
                    "vector_score": vector_similarity,
                    "pattern_score": None,
                    "used_patterns": False,
                    "latency_ms": self._get_latency_ms(start_time),
                    "fallback_reason": "langextract_unavailable"
                }

            # Calculate pattern similarity
            similarity = self.pattern_scorer.calculate_similarity(
                task_semantic, pattern_semantic
            )
            pattern_similarity = similarity["final_similarity"]

            # Calculate hybrid score
            result = self.hybrid_scorer.calculate_hybrid_score(
                vector_similarity=vector_similarity,
                pattern_similarity=pattern_similarity
            )

            return {
                "hybrid_score": result["hybrid_score"],
                "vector_score": result["vector_score"],
                "pattern_score": result["pattern_score"],
                "used_patterns": True,
                "latency_ms": self._get_latency_ms(start_time),
                "confidence": result["confidence"],
                "component_scores": similarity
            }

        except Exception as e:
            logger.error(f"Unexpected error in hybrid scoring: {e}", exc_info=True)

            # Ultimate fallback - return vector score
            return {
                "hybrid_score": vector_similarity,
                "vector_score": vector_similarity,
                "pattern_score": None,
                "used_patterns": False,
                "latency_ms": self._get_latency_ms(start_time),
                "fallback_reason": f"error: {type(e).__name__}"
            }

    async def _get_semantic_cached(
        self,
        content: str
    ) -> Optional[SemanticAnalysisResult]:
        """Get semantic analysis with caching and error handling"""
        try:
            # Check cache first
            cached = await self.cache.get(content)
            if cached:
                return cached

            # Fetch from langextract
            result = await self.client.analyze_semantic(content)
            await self.cache.set(content, result)
            return result

        except (LangextractTimeoutError, LangextractUnavailableError) as e:
            logger.warning(f"Langextract error: {e}")
            return None
        except CircuitBreakerError:
            logger.warning("Circuit breaker open - langextract unavailable")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching semantic analysis: {e}")
            return None

    def _get_latency_ms(self, start_time: float) -> float:
        """Calculate latency in milliseconds"""
        return (asyncio.get_event_loop().time() - start_time) * 1000

    async def close(self):
        """Cleanup resources"""
        await self.client.close()


# Usage
async def production_example():
    scorer = ProductionHybridScorer()

    try:
        result = await scorer.score_similarity(
            task_description="Implement OAuth2 authentication",
            historical_pattern_text="Build user authentication",
            vector_similarity=0.85
        )

        print(f"Hybrid score: {result['hybrid_score']:.2f}")
        print(f"Used patterns: {result['used_patterns']}")
        print(f"Latency: {result['latency_ms']:.1f}ms")

        if 'fallback_reason' in result:
            print(f"Fallback reason: {result['fallback_reason']}")

    finally:
        await scorer.close()

asyncio.run(production_example())
```

---

## Performance Characteristics

### Latency Benchmarks

| Operation | Target | Typical (p50) | p95 | p99 |
|-----------|--------|---------------|-----|-----|
| **Langextract uncached** | <5s | 3-4s | 4-5s | 5-6s |
| **Langextract cached** | <100ms | 10-20ms | 50-80ms | 100-150ms |
| **Pattern similarity calculation** | <100ms | 30-50ms | 80-90ms | 100-120ms |
| **Hybrid score combination** | <10ms | 2-5ms | 8-9ms | 10-12ms |
| **Overall hybrid scoring (cached)** | <1s | 500-800ms | 1-2s | 2-3s |

### Throughput

| Metric | Target | Typical |
|--------|--------|---------|
| **Concurrent requests** | 10 req/s sustained | 8-12 req/s |
| **Burst capacity** | 50 req/s for 30s | 40-60 req/s |
| **Cache hit rate (after warmup)** | >80% | 82-88% |
| **Success rate (with fallback)** | >99.5% | 99.7-99.9% |

### Resource Usage

```yaml
HTTP Client:
  Max connections: 100
  Keepalive connections: 20
  Memory per connection: ~50KB

Cache (in-memory):
  Max size: 1000 entries
  Memory usage: 50-100MB
  TTL: 3600s (1 hour)
  Eviction policy: LRU

Redis (optional):
  Memory per entry: ~2-5KB
  Total for 1000 entries: ~2-5MB
```

### Optimization Tips

1. **Cache Warming**: Pre-populate cache with common patterns during startup
2. **TTL Tuning**: Adjust TTL based on access patterns (longer for stable patterns)
3. **Batch Processing**: Process multiple patterns in parallel
4. **Circuit Breaker**: Prevent cascading failures with circuit breaker
5. **Monitoring**: Track cache hit rate and adjust max_size if needed

---

## Return Types

### SemanticAnalysisResult

```python
class SemanticAnalysisResult(BaseModel):
    semantic_patterns: List[SemanticPattern]
    concepts: List[str]
    themes: List[str]
    semantic_density: float  # 0.0-1.0
    conceptual_coherence: float  # 0.0-1.0
    thematic_consistency: float  # 0.0-1.0
    semantic_context: Dict[str, Any]
    domain_indicators: List[str]
    primary_topics: List[str]
    topic_weights: Dict[str, float]
```

### SemanticPattern

```python
class SemanticPattern(BaseModel):
    pattern_id: str
    pattern_type: str  # THEME, TOPIC, NUMBERED_LIST, etc.
    pattern_name: str
    description: str
    examples: List[str]
    frequency: int
    confidence_score: float  # 0.0-1.0
    significance_score: float  # 0.0-1.0
    context: Dict[str, Any]
    properties: Dict[str, Any]
    related_entity_ids: List[str]
```

---

**API Reference Complete**
**Version**: 1.0.0
**Last Updated**: 2025-10-02
**Next**: See [Integration Guide](INTEGRATION_GUIDE.md) for implementation guidance
