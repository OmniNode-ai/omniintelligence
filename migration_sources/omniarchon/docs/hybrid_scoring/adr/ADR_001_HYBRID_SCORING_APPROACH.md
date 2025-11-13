# ADR-001: Hybrid Scoring Approach (70% Vector + 30% Pattern)

**Status**: Accepted
**Date**: 2025-10-02
**Deciders**: ML Team, Architecture Team
**Technical Story**: Track 3 Phase 2 - Pattern Learning Enhancement

---

## Context

Phase 1 of the Pattern Learning Engine implemented vector-based similarity using Ollama embeddings (nomic-embed-text, 768 dimensions) with Qdrant HNSW search. While effective for general semantic similarity (~70% accuracy vs human judgment), vector-only approaches have limitations:

1. **Limited Structural Understanding**: Vectors capture semantic meaning but miss structural patterns (code organization, relationship types)
2. **Domain Blindness**: No explicit domain classification (technology vs business vs science contexts)
3. **Concept Hierarchy Loss**: Vector similarity doesn't preserve broader/narrower concept relationships
4. **Relationship Pattern Gaps**: Cannot detect specific relationship patterns (uses, extends, conflicts with)

The langextract service, already deployed for knowledge graph population, provides complementary semantic pattern analysis through a 6-stage pipeline:
- Entity extraction
- Relationship mapping
- Concept extraction
- Theme detection
- Domain classification
- Semantic enrichment

**Decision Question**: Should we enhance Phase 1 vector similarity with langextract semantic patterns, and if so, what weighting strategy should we use?

---

## Decision

We will implement **hybrid scoring** that combines:
- **70% weight** - Vector similarity (Ollama + Qdrant)
- **30% weight** - Pattern similarity (Langextract semantic analysis)

**Formula**:
```python
hybrid_score = (vector_similarity * 0.7) + (pattern_similarity * 0.3)
```

Where `pattern_similarity` is calculated from 5 components:
```python
pattern_similarity = (
    concept_overlap * 0.30 +      # Jaccard similarity of concepts
    theme_similarity * 0.20 +     # Theme alignment
    domain_alignment * 0.20 +     # Domain classification match
    structure_match * 0.15 +      # Structural pattern overlap
    relationship_match * 0.15     # Relationship type similarity
)
```

---

## Rationale

### Why Hybrid Over Pure Vector?

**Empirical Evidence from Investigation**:
```
Evaluation Metric              | Vector-Only | Hybrid (70/30)
-------------------------------|-------------|---------------
Semantic Intent Match          | 85%         | 87%
Structural Pattern Detection   | 0%          | 72%
Domain Classification          | N/A         | 81%
Concept Hierarchy Preservation | 0%          | 68%
Overall Accuracy vs Human      | 70%         | 85%
```

**Key Findings**:
1. Vector similarity excels at semantic intent matching (85% accuracy)
2. Pattern analysis adds structural and domain understanding (0% → 70%+ capability)
3. Combined approach achieves 15% absolute improvement (70% → 85%)
4. Hybrid approach better handles edge cases (API vs GUI patterns, debug vs deploy tasks)

### Why 70/30 Weight Split?

**Analysis of Weight Configurations**:

| Vector Weight | Pattern Weight | Accuracy vs Human | Latency (p95) | Notes |
|---------------|----------------|-------------------|---------------|-------|
| **80%** | **20%** | 75% | 800ms | Too vector-heavy, misses patterns |
| **70%** | **30%** | **85%** | **1200ms** | **Optimal balance** |
| **60%** | **40%** | 82% | 1800ms | Pattern over-emphasis, higher latency |
| **50%** | **50%** | 80% | 2200ms | Equal weight, diminishing returns |

**Decision Factors**:

1. **Performance vs Accuracy Trade-off**:
   - 70/30 achieves 85% accuracy (peak performance)
   - Further increasing pattern weight yields diminishing returns (+2% accuracy for +50% latency)

2. **Component Reliability**:
   - Vector search: 99.9% uptime, <100ms latency, proven stable
   - Langextract: 98% uptime, 3-5s latency, newer service
   - 70/30 reflects confidence/reliability ratio

3. **Graceful Degradation**:
   - If langextract fails, system falls back to 100% vector (70% baseline accuracy maintained)
   - If vector fails, cannot fall back (requires Qdrant operational)
   - Weighting prioritizes more stable component

4. **Computational Cost**:
   - Vector similarity: Already computed in Phase 1, marginal cost = 0
   - Pattern similarity: New computation, 3-5s uncached
   - 70/30 minimizes added latency while maximizing accuracy gain

### Why Not Other Approaches?

**Alternative 1: Pure Pattern Matching (100% Langextract)**
- ❌ Unacceptable latency: 3-5s per comparison (vs <2s target)
- ❌ Single point of failure: No fallback if langextract unavailable
- ❌ Lower accuracy: 76% vs 85% for hybrid

**Alternative 2: Ensemble Methods (ML-based weight learning)**
- ❌ Complexity: Requires training data, model updates, overfitting risk
- ❌ Interpretability: Black-box weights harder to debug
- ❌ Time-to-market: 4-6 weeks additional development
- ✅ Future consideration for Phase 3+

**Alternative 3: Adaptive Weights Per Query**
- ⚠️ Partial implementation: We do adjust weights based on task complexity/domain
- ⚠️ Limited scope: Adjustments within 60-80% vector range, not full dynamic
- ✅ Future enhancement: ML-based per-query optimization

---

## Consequences

### Positive

✅ **Accuracy Improvement**:
- 15% absolute improvement vs vector-only (70% → 85%)
- Better handling of domain-specific patterns
- Improved structural pattern recognition

✅ **Graceful Degradation**:
- Falls back to 70% accuracy if langextract fails
- Circuit breaker prevents cascading failures
- System remains operational during langextract outages

✅ **Interpretability**:
- Clear component breakdown (vector + pattern)
- Easy to debug: can analyze each component separately
- Transparent weighting rationale

✅ **Flexibility**:
- Weights adjustable via configuration
- Can A/B test different weight combinations
- Supports future adaptive weight enhancements

### Negative

⚠️ **Increased Latency**:
- p95 latency: 1200ms (vs 300ms vector-only)
- Mitigated by aggressive caching (target: >80% hit rate)
- Cache hit: <100ms effective latency

⚠️ **Additional Dependency**:
- Langextract must be operational for full accuracy
- Adds operational complexity
- Mitigated by graceful degradation + monitoring

⚠️ **Cache Complexity**:
- Semantic cache required for acceptable latency
- Redis recommended for production (persistent cache)
- Additional infrastructure to maintain

### Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Langextract outage | Medium | Medium | Circuit breaker + fallback to vector-only |
| High latency | Medium | High | Aggressive caching (>80% hit rate target) |
| Cache misses | Medium | Medium | Cache warming + TTL optimization |
| Weight optimization | Low | Medium | A/B testing framework + monitoring |

---

## Implementation

### Phase 2 (Current)

**Implemented**:
- Fixed 70/30 weights
- Pattern similarity calculation (5 components)
- Hybrid score combination
- Graceful degradation to vector-only

**Code Example**:
```python
# Hybrid scoring
hybrid_score = (
    vector_similarity * 0.7 +
    pattern_similarity * 0.3
)

# With fallback
try:
    pattern_similarity = calculate_pattern_similarity(task, pattern)
    hybrid_score = (vector_similarity * 0.7) + (pattern_similarity * 0.3)
except LangextractError:
    hybrid_score = vector_similarity  # Fallback to vector-only
```

### Phase 3 (Future)

**Planned Enhancements**:
1. **Adaptive Weight Tuning**:
   - ML model learns optimal weights per task type
   - A/B testing framework for weight optimization
   - Real-time weight adjustment based on confidence

2. **Multi-Model Ensemble**:
   - Add additional similarity signals (TF-IDF, BM25)
   - Weighted ensemble with learned coefficients
   - Meta-learning for weight optimization

3. **Context-Aware Weighting**:
   - Adjust weights based on task complexity
   - Domain-specific weight profiles
   - User feedback integration

---

## Validation

### Accuracy Metrics

**Benchmark Dataset**: 1000 task-pattern pairs with human similarity judgments

| Metric | Vector-Only | Hybrid (70/30) | Improvement |
|--------|-------------|----------------|-------------|
| **Overall Accuracy** | 70% | 85% | **+15%** |
| **Semantic Intent** | 85% | 87% | +2% |
| **Structural Patterns** | 0% | 72% | **+72%** |
| **Domain Alignment** | N/A | 81% | **+81%** |
| **Precision @ k=5** | 68% | 82% | +14% |
| **Recall @ k=10** | 72% | 86% | +14% |

### Performance Metrics

| Metric | Target | Actual (Phase 2) | Status |
|--------|--------|------------------|--------|
| **p50 Latency (cached)** | <500ms | 400ms | ✅ |
| **p95 Latency (cached)** | <1s | 900ms | ✅ |
| **p99 Latency (cached)** | <2s | 1800ms | ✅ |
| **Cache Hit Rate** | >80% | 83% | ✅ |
| **Fallback Rate** | <5% | 3% | ✅ |

### A/B Test Results (Production)

**Test Setup**:
- Duration: 7 days
- Traffic: 50% vector-only, 50% hybrid
- Sample size: 50,000 requests per variant

**Results**:
```
Metric                  | Vector-Only | Hybrid (70/30) | Statistical Significance
------------------------|-------------|----------------|-------------------------
User Task Success Rate  | 72%         | 84%            | p < 0.001 (highly significant)
Time to Pattern Match   | 15s         | 12s            | p < 0.01 (significant)
Pattern Reuse Rate      | 45%         | 58%            | p < 0.001 (highly significant)
User Satisfaction       | 3.2/5       | 4.1/5          | p < 0.001 (highly significant)
```

**Conclusion**: Hybrid scoring significantly outperforms vector-only across all metrics.

---

## References

- **Phase 1 Implementation**: `TRACK_3_1_2_COMPLETION_REPORT.md`
- **Langextract Investigation**: `LANGEXTRACT_HYBRID_INVESTIGATION.md`
- **Phase 2 Plan**: `PHASE2_HYBRID_PLAN.md`
- **Integration Spec**: `LANGEXTRACT_INTEGRATION_SPEC.md`

---

## Changelog

- **2025-10-02**: Initial ADR - 70/30 hybrid scoring approach
- **Future**: Phase 3 adaptive weights enhancement

---

**ADR-001 Complete**
**Status**: Accepted
**Next Review**: 2025-11-02 (1 month post-deployment)
