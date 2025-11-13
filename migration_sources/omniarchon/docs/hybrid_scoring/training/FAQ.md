# Hybrid Scoring FAQ

**Version**: 1.0.0
**Last Updated**: 2025-10-02

---

## General Questions

### Q: What is hybrid scoring?

**A**: Hybrid scoring combines vector-based similarity (70%) with semantic pattern analysis (30%) to achieve more accurate pattern matching. It improves accuracy from 70% to 85% compared to vector-only approaches.

### Q: When should I use hybrid scoring?

**A**: Use hybrid scoring when:
- You need >80% accuracy in pattern matching
- Structural patterns matter (code organization, architecture)
- Domain classification is important (technology vs business)
- You can tolerate slightly higher latency (p95: 1-2s vs 300ms)

### Q: What's the difference from Phase 1?

**A**: Phase 1 uses only vector embeddings (Ollama + Qdrant). Phase 2 adds semantic pattern analysis from langextract, combining both for better accuracy.

---

## Integration Questions

### Q: Do I need to change my Phase 1 code?

**A**: Minimal changes required. You add hybrid scoring alongside Phase 1:

```python
# Phase 1 (keep this)
vector_score = await qdrant_search(task_embedding)

# Phase 2 (add this)
hybrid_score = await hybrid_scorer.score(task, pattern, vector_score)

# Use hybrid_score instead of vector_score
```

### Q: Can I use hybrid scoring without Redis?

**A**: Yes. Redis is optional but recommended for production. Without Redis:
- Cache is per-instance only (not shared)
- Hit rate ~75% instead of ~83%
- No persistence across restarts

### Q: What if langextract is unavailable?

**A**: The system automatically falls back to vector-only scoring (Phase 1 behavior). Circuit breaker opens after 5 failures, and all requests use vector similarity until langextract recovers.

---

## Performance Questions

### Q: What's the expected latency?

**A**:
- **Uncached**: 3-5s (langextract call)
- **Cached**: <100ms (90% of requests)
- **Circuit open**: <1ms (fail fast to vector-only)
- **Target p95**: <2s

### Q: How can I improve cache hit rate?

**A**:
1. Increase cache size: `SEMANTIC_CACHE_MAX_SIZE=2000`
2. Increase TTL: `SEMANTIC_CACHE_TTL_SECONDS=7200` (2 hours)
3. Implement cache warming at startup
4. Enable Redis for shared cache

### Q: Why is hybrid scoring slower than Phase 1?

**A**: Langextract semantic analysis takes 3-5s uncached. However, aggressive caching (>80% hit rate) makes cached requests <100ms, comparable to Phase 1.

---

## Operational Questions

### Q: How do I monitor hybrid scoring?

**A**: Key metrics to watch:
```yaml
semantic_cache_hit_rate       # Target: >80%
langextract_request_duration  # p95: <5s
langextract_circuit_breaker_state  # Should be 0 (closed)
hybrid_scoring_duration       # p95: <2s
langextract_fallback_total    # Target: <5%
```

### Q: What does "circuit breaker open" mean?

**A**: Circuit breaker opens after 5 consecutive langextract failures. When open:
- All requests fail fast (<1ms)
- System uses vector-only scoring
- Automatically tests recovery after 60s
- Returns to hybrid scoring when langextract recovers

### Q: How do I manually reset the circuit breaker?

**A**: Emergency reset (use sparingly):
```python
from langextract_client import langextract_breaker
langextract_breaker.reset()  # Reset to closed state
```

---

## Configuration Questions

### Q: Can I change the 70/30 weight ratio?

**A**: Yes, via configuration:
```python
config = HybridScoringConfig(
    default_vector_weight=0.8,
    default_pattern_weight=0.2
)
scorer = HybridScorer(config=config)
```

**Recommendation**: Keep 70/30 default unless A/B testing shows improvement.

### Q: What is adaptive weight adjustment?

**A**: Adaptive weights adjust the 70/30 ratio based on task characteristics:
- High complexity → 60% vector, 40% pattern
- Low complexity → 80% vector, 20% pattern
- Technology domain → 65% vector, 35% pattern

Enable with: `HYBRID_ENABLE_ADAPTIVE_WEIGHTS=true`

### Q: Should I use adaptive weights?

**A**: Start with fixed 70/30. Enable adaptive weights if:
- You have high-complexity tasks (architecture, design)
- Domain classification is important
- A/B testing shows improvement

---

## Troubleshooting Questions

### Q: Cache hit rate is only 40%. What's wrong?

**A**: Common causes:
1. **Cache size too small**: Increase `SEMANTIC_CACHE_MAX_SIZE`
2. **TTL too short**: Increase `SEMANTIC_CACHE_TTL_SECONDS`
3. **High pattern diversity**: Normal for unique patterns
4. **No cache warming**: Implement startup cache warming

### Q: Circuit breaker keeps opening. Help!

**A**: Investigate in order:
1. Check langextract health: `curl http://localhost:8156/health`
2. Check langextract logs: `docker logs archon-langextract`
3. Verify network connectivity
4. Check Memgraph dependency (langextract needs it)
5. Consider increasing threshold if false positives

### Q: Hybrid scoring is slower than expected

**A**: Debug latency:
```python
import time

# Measure langextract
start = time.time()
result = await client.analyze_semantic(task)
langextract_ms = (time.time() - start) * 1000

# Measure pattern similarity
start = time.time()
pattern_sim = scorer.calculate_similarity(task_sem, pattern_sem)
pattern_ms = (time.time() - start) * 1000

print(f"Langextract: {langextract_ms:.1f}ms")
print(f"Pattern calc: {pattern_ms:.1f}ms")
```

Check:
1. Cache hit rate (should be >80%)
2. Langextract service health
3. Redis connectivity (if enabled)

---

## Architecture Questions

### Q: Why 70% vector and 30% pattern?

**A**: Empirical testing showed:
- 80/20 → 75% accuracy (too vector-heavy)
- 70/30 → 85% accuracy (optimal)
- 60/40 → 82% accuracy (diminishing returns, higher latency)

See ADR-001 for detailed analysis.

### Q: Why LRU eviction for cache?

**A**: Pattern matching workloads show temporal locality (recent patterns accessed repeatedly). LRU captures this pattern better than LFU or FIFO. See ADR-002.

### Q: Why 1 hour TTL?

**A**: Balance between:
- **Hit rate**: 1 hour → 83%, 4 hours → 85% (+2%)
- **Memory**: 1 hour → ~100MB, 4 hours → ~200MB
- **Staleness**: Patterns rarely change within 1 hour

See ADR-002 for TTL analysis.

### Q: Why circuit breaker instead of just retries?

**A**: Circuit breaker provides:
- **Fail fast**: <1ms vs 5-10s timeout
- **Resource protection**: Prevents thread pool exhaustion
- **Auto recovery**: Tests health automatically

See ADR-004 for detailed rationale.

---

## Best Practices Questions

### Q: What's the recommended deployment strategy?

**A**: Gradual rollout:
1. **Week 1**: Deploy to staging, test thoroughly
2. **Week 2**: 10% production traffic (feature flag)
3. **Week 3**: 50% production traffic
4. **Week 4**: 100% production traffic

Monitor cache hit rate, latency, accuracy at each stage.

### Q: How should I handle errors?

**A**: Always implement fallback:
```python
try:
    hybrid_score = await hybrid_scorer.score(task, pattern, vector_score)
except (CircuitBreakerError, LangextractError):
    hybrid_score = vector_score  # Fallback to vector-only
```

Never let hybrid scoring failures block user requests.

### Q: Should I warm the cache at startup?

**A**: Yes, recommended for production:
```python
# Load top 100 most-used patterns
patterns = await load_top_patterns(limit=100)

# Warm cache
count = await cache.warm_cache(patterns, client)
logger.info(f"Warmed cache with {count} patterns")
```

Reduces cold start latency from 4s to <100ms.

---

## Cost & Resources Questions

### Q: What infrastructure is required?

**A**:
- **Langextract**: 1 container (2 CPU, 4GB RAM)
- **Redis** (optional): 1 container (1 CPU, 2GB RAM)
- **Intelligence service**: Existing + ~500MB for cache

**Total incremental**: ~3 CPU, ~6GB RAM

### Q: What's the cost of hybrid scoring?

**A**: Incremental costs:
- **Compute**: ~$50-100/month (langextract + Redis)
- **Memory**: ~$10-20/month (cache storage)
- **Network**: Minimal (internal traffic)

**Total**: ~$60-120/month additional

### Q: Can I reduce costs?

**A**: Yes:
1. Disable Redis (use in-memory only)
2. Reduce cache size
3. Use lighter langextract configuration
4. Share langextract across services

---

## Migration Questions

### Q: Can I migrate from Phase 1 gradually?

**A**: Yes, recommended approach:
```python
# Feature flag
USE_HYBRID = os.getenv("USE_HYBRID_SCORING", "false") == "true"

if USE_HYBRID:
    score = await hybrid_scorer.score(task, pattern, vector_score)
else:
    score = vector_score  # Phase 1 behavior
```

Gradually increase traffic to hybrid scoring.

### Q: Is Phase 1 still required?

**A**: Yes. Phase 2 depends on Phase 1:
- Vector similarity is 70% of hybrid score
- Fallback to vector-only when langextract fails
- Phase 1 infrastructure (Ollama, Qdrant) remains critical

### Q: Can I skip Phase 1 and use only Phase 2?

**A**: No. Hybrid scoring requires:
- Vector similarity from Phase 1 (70% of score)
- Pattern similarity from Phase 2 (30% of score)

Both components are required for hybrid scoring.

---

## Support Questions

### Q: Who do I contact for support?

**A**:
- **Technical issues**: #hybrid-scoring-support on Slack
- **Bugs**: File issue in GitHub repo
- **Emergency**: ml-oncall@company.com (24/7 on-call)

### Q: Where can I find more documentation?

**A**:
- **API Reference**: `/docs/hybrid_scoring/API_REFERENCE.md`
- **Integration Guide**: `/docs/hybrid_scoring/INTEGRATION_GUIDE.md`
- **Operational Runbook**: `/docs/hybrid_scoring/OPERATIONAL_RUNBOOK.md`
- **ADRs**: `/docs/hybrid_scoring/adr/`

### Q: Is there training available?

**A**: Yes:
- **Self-paced**: Training guide in `/docs/hybrid_scoring/training/`
- **Live sessions**: Bi-weekly training (sign up via Slack)
- **Office hours**: Tuesday 2-3 PM PT, Thursday 10-11 AM PT

---

**Have a question not answered here?**

Submit via:
- Slack: #hybrid-scoring-support
- Email: ml-team@company.com
- GitHub: Open a discussion in the repository

We'll update this FAQ with new questions regularly.

---

**FAQ Version**: 1.0.0
**Last Updated**: 2025-10-02
**Maintained by**: ML Team
