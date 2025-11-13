# Hybrid Score Endpoint

**Endpoint**: `POST /api/pattern-learning/hybrid/score`
**Status**: ✅ Implemented (2025-11-03)
**Performance**: <1ms average processing time (target: <50ms)

## Overview

Calculates a hybrid score for pattern matching by combining multiple scoring dimensions:
1. **Keyword matching**: Jaccard similarity between pattern and context keywords
2. **Semantic similarity**: Pattern relevance to user prompt (from vector search)
3. **Quality score**: Pattern quality from metadata
4. **Success rate**: Historical pattern success rate from metadata

## Request Format

```json
{
  "pattern": {
    "keywords": ["fastapi", "async", "api", "rest"],
    "metadata": {
      "quality_score": 0.85,        // Optional, defaults to 0.5
      "success_rate": 0.90,          // Optional, defaults to 0.5
      "confidence_score": 0.88,      // Optional, defaults to 0.5
      "semantic_score": 0.82         // Optional, uses confidence_score or 0.5
    }
  },
  "context": {
    "keywords": ["fastapi", "rest", "endpoint"],
    "task_type": "api_development",    // Optional
    "complexity": "moderate"            // Optional
  },
  "weights": {                         // Optional, defaults below
    "keyword": 0.25,
    "semantic": 0.35,
    "quality": 0.20,
    "success_rate": 0.20
  }
}
```

## Response Format

```json
{
  "status": "success",
  "data": {
    "hybrid_score": 0.7370,
    "breakdown": {
      "keyword_score": 0.4000,
      "semantic_score": 0.8200,
      "quality_score": 0.8500,
      "success_rate_score": 0.9000
    },
    "confidence": 0.7129,
    "metadata": {
      "processing_time_ms": 0.39,
      "weights_used": {
        "keyword": 0.25,
        "semantic": 0.35,
        "quality": 0.2,
        "success_rate": 0.2
      },
      "keyword_matches": 2,
      "pattern_keywords_count": 4,
      "context_keywords_count": 3
    }
  },
  "timestamp": "2025-11-03T14:43:18.937055Z",
  "metadata": {
    "processing_time_ms": 0.3
  }
}
```

## Scoring Dimensions

### 1. Keyword Score (Jaccard Similarity)

Measures keyword overlap between pattern and context:

```
keyword_score = |pattern_keywords ∩ context_keywords| / |pattern_keywords ∪ context_keywords|
```

- Range: 0.0 (no overlap) to 1.0 (perfect match)
- Example: ["fastapi", "rest"] vs ["fastapi", "endpoint"] → 0.33

### 2. Semantic Score

Uses vector similarity from pattern metadata:
- Source: `pattern.metadata.semantic_score` (from vector search)
- Fallback: `pattern.metadata.confidence_score`
- Default: 0.5 if not provided

### 3. Quality Score

Pattern quality assessment from metadata:
- Source: `pattern.metadata.quality_score`
- Default: 0.5 if not provided
- Should reflect ONEX compliance, documentation quality, etc.

### 4. Success Rate Score

Historical pattern success rate:
- Source: `pattern.metadata.success_rate`
- Default: 0.5 if not provided
- Should reflect actual usage success metrics

## Weight Configuration

### Default Weights

```python
{
    "keyword": 0.25,      # 25% - Keyword matching
    "semantic": 0.35,     # 35% - Semantic similarity (highest weight)
    "quality": 0.20,      # 20% - Pattern quality
    "success_rate": 0.20  # 20% - Historical success
}
```

### Custom Weights

- Weights are automatically normalized to sum to 1.0
- Example: `{keyword: 1.0, semantic: 2.0, quality: 1.0, success_rate: 1.0}`
  → Normalized to `{keyword: 0.2, semantic: 0.4, quality: 0.2, success_rate: 0.2}`

## Confidence Calculation

Confidence measures score agreement and overall quality:

```python
avg_score = mean([keyword_score, semantic_score, quality_score, success_rate])
variance = variance([keyword_score, semantic_score, quality_score, success_rate])
confidence = avg_score * (1.0 - min(variance, 1.0))
```

- High confidence: Scores agree (low variance) and average is high
- Low confidence: Scores diverge or average is low

## Use Cases

### 1. OmniClaude Pattern Selection

Use hybrid scoring to rank patterns for agent selection:

```python
import requests

def score_pattern_for_task(pattern, user_prompt, keywords):
    response = requests.post(
        "http://localhost:8053/api/pattern-learning/hybrid/score",
        json={
            "pattern": pattern,
            "context": {
                "keywords": keywords,
                "user_prompt": user_prompt
            }
        }
    )
    return response.json()["data"]["hybrid_score"]
```

### 2. Pattern Quality Assessment

Evaluate pattern quality with custom weights emphasizing quality:

```python
response = requests.post(
    "http://localhost:8053/api/pattern-learning/hybrid/score",
    json={
        "pattern": pattern,
        "context": context,
        "weights": {
            "keyword": 0.15,
            "semantic": 0.25,
            "quality": 0.40,      # Emphasize quality
            "success_rate": 0.20
        }
    }
)
```

### 3. Keyword-Heavy Matching

For exact keyword matching scenarios:

```python
response = requests.post(
    "http://localhost:8053/api/pattern-learning/hybrid/score",
    json={
        "pattern": pattern,
        "context": context,
        "weights": {
            "keyword": 0.60,      # High keyword weight
            "semantic": 0.20,
            "quality": 0.10,
            "success_rate": 0.10
        }
    }
)
```

## Performance

- **Target**: <50ms per request
- **Actual**: ~0.1-0.5ms processing time
- **Bottlenecks**: None (pure computation, no I/O)
- **Scalability**: Can handle 1000+ requests/second

## Error Handling

### 400 Bad Request

Invalid input (non-numeric scores, malformed JSON):

```json
{
  "detail": "Invalid input: quality_score must be a float"
}
```

### 500 Internal Server Error

Unexpected server error:

```json
{
  "detail": "Hybrid scoring failed: <error message>"
}
```

## Testing

Run the test suite:

```bash
python3 scripts/test_hybrid_score_api.py
```

Or test manually:

```bash
curl -X POST http://localhost:8053/api/pattern-learning/hybrid/score \
  -H "Content-Type: application/json" \
  -d '{
    "pattern": {
      "keywords": ["fastapi", "async"],
      "metadata": {
        "quality_score": 0.85,
        "success_rate": 0.90
      }
    },
    "context": {
      "keywords": ["fastapi", "endpoint"]
    }
  }'
```

## Implementation Details

- **File**: `services/intelligence/src/api/pattern_learning/routes.py`
- **Function**: `calculate_hybrid_score()`
- **Algorithm**: Weighted linear combination with Jaccard similarity for keywords
- **Dependencies**: None (pure Python, no external services)

## Future Enhancements

1. **Adaptive Weighting**: Use NodeHybridScorerCompute for complexity-based weight adjustment
2. **Semantic Search Integration**: Call Qdrant for real semantic scoring instead of using metadata
3. **Caching**: Cache frequent pattern/context combinations
4. **Batch API**: Support scoring multiple patterns in one request
5. **Analytics**: Track scoring performance and adjustment patterns

## Related APIs

- `POST /api/pattern-learning/pattern/match` - Pattern similarity matching
- `POST /api/pattern-learning/semantic/analyze` - Semantic analysis via Langextract
- `GET /api/pattern-learning/metrics` - Pattern learning metrics

## Changelog

- **2025-11-03**: Initial implementation
  - Basic hybrid scoring with 4 dimensions
  - Jaccard similarity for keyword matching
  - Confidence calculation based on score agreement
  - Weight normalization and validation
  - Performance: <1ms average processing time
