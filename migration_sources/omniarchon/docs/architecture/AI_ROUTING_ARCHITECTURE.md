# AI Routing Architecture - Complete System Design

**Version**: 1.0.0
**Date**: October 1, 2025
**Status**: Design Complete
**Type**: Architecture Documentation

---

## Executive Summary

AI-powered routing system that enhances Phase 1 filesystem routing by leveraging multi-GPU AI lab infrastructure for semantic agent selection. Achieves 90%+ routing accuracy while maintaining <2s response time through intelligent path selection, multi-model consensus, and aggressive caching.

### Key Architecture Decisions

1. **Hybrid Routing**: Fast path (Phase 1) for simple queries, AI path for complex queries
2. **Multi-Model Consensus**: AI Quorum with 5 models (local + cloud) for robust decisions
3. **Progressive Fallback**: 4-tier cascade from AI Quorum → Phase 1 guarantee
4. **Learning-Enabled**: Supabase storage for continuous accuracy improvement
5. **Zero Breaking Changes**: Transparent enhancement of existing Phase 1 router

---

## System Architecture

### High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      User Request                               │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│              AIRoutingIntelligence (Main Coordinator)           │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. Complexity Analyzer                                   │  │
│  │    - Explicit agent detection                            │  │
│  │    - Query complexity scoring                            │  │
│  │    - Path selection (Fast vs AI)                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 2. Result Cache (Phase 1 + AI)                          │  │
│  │    - Unified caching layer                               │  │
│  │    - 1-hour TTL                                          │  │
│  │    - Context-aware keys                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────┬───────────┘
                 │ Simple/Explicit                    │ Complex/Ambiguous
                 │                                    │
                 ↓                                    ↓
┌────────────────────────────────┐  ┌────────────────────────────────┐
│   Phase 1 Fast Path            │  │   AI Quorum Path               │
│   (EnhancedAgentRouter)        │  │   (AIQuorumRouter)             │
│                                │  │                                │
│  • Fuzzy trigger matching      │  │  • Parallel model queries      │
│  • 4-component confidence      │  │  • Multi-model consensus       │
│  • Capability indexing         │  │  • Weighted aggregation        │
│  • 50-100ms response           │  │  • 1-2s response               │
└────────────────────────────────┘  └────────────────┬───────────────┘
                 │                                    │
                 │                                    ↓
                 │                   ┌────────────────────────────────┐
                 │                   │  AI Quorum Infrastructure      │
                 │                   │                                │
                 │                   │  Primary (3.2 weight):         │
                 │                   │  • 5090 DeepSeek-Lite (2.0)   │
                 │                   │  • 4090 Llama 3.1 (1.2)       │
                 │                   │                                │
                 │                   │  Secondary (3.3 weight):       │
                 │                   │  • Mac Studio Codestral (1.5) │
                 │                   │  • Mac Mini DeepSeek (1.8)    │
                 │                   │                                │
                 │                   │  Tertiary (1.0 weight):        │
                 │                   │  • Gemini Flash (cloud)        │
                 │                   └────────────────────────────────┘
                 │                                    │
                 ↓                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Consensus Builder                            │
│  • Aggregate model responses                                    │
│  • Weight by model confidence                                   │
│  • Calculate consensus score                                    │
│  • Generate unified reasoning                                   │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Learning System (Supabase)                     │
│  • Log routing decisions                                        │
│  • Track agent success metrics                                 │
│  • Calculate historical scores                                  │
│  • Feed back into confidence scoring                            │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ↓
┌─────────────────────────────────────────────────────────────────┐
│              Ranked Agent Recommendations                       │
│  • Top 1-3 agents with confidence scores                       │
│  • Detailed reasoning and capability matches                    │
│  • Workflow suggestions for multi-step tasks                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Routing Decision Flow

### Detailed Decision Tree

```
User Query
    │
    ↓
┌───────────────────────────────────────────────────┐
│ Explicit Agent Pattern Match?                    │
│ • "use agent-X"                                   │
│ • "@agent-X"                                      │
│ • "^agent-X"                                      │
└───────────────┬───────────────────────────────────┘
                │
        ┌───────┴───────┐
        │               │
       YES             NO
        │               │
        ↓               ↓
    ┌───────┐   ┌──────────────────────────────┐
    │ Phase │   │ Run Phase 1 Quick Analysis   │
    │   1   │   │ (EnhancedAgentRouter)        │
    │ Fast  │   │                              │
    │ Path  │   │ • Trigger matching           │
    │       │   │ • Confidence scoring         │
    │ 50ms  │   │ • Top 3 candidates           │
    └───────┘   └──────────────┬───────────────┘
        │                      │
        │                      ↓
        │       ┌──────────────────────────────────┐
        │       │ Single High-Confidence Match?    │
        │       │ (confidence > 0.9)               │
        │       └──────────────┬───────────────────┘
        │                      │
        │              ┌───────┴────────┐
        │              │                │
        │             YES              NO
        │              │                │
        │              ↓                ↓
        │       ┌──────────┐   ┌───────────────────┐
        │       │  Phase   │   │ Multiple Similar  │
        │       │    1     │   │ Options?          │
        │       │  Fast    │   │ (3+ with >0.7)    │
        │       │  Path    │   └─────────┬─────────┘
        │       │          │             │
        │       │  80ms    │     ┌───────┴────────┐
        │       └──────────┘     │                │
        │              │        YES              NO
        │              │         │                │
        │              │         ↓                ↓
        │              │  ┌──────────┐   ┌────────────┐
        │              │  │    AI    │   │  Low       │
        │              │  │  Quorum  │   │  Confidence│
        │              │  │   Path   │   │  (<0.7)?   │
        │              │  │          │   └──────┬─────┘
        │              │  │ Disambig │          │
        │              │  │  1-2s    │  ┌───────┴────┐
        │              │  └──────────┘  │            │
        │              │         │     YES          NO
        │              │         │      │            │
        │              │         │      ↓            ↓
        │              │         │  ┌────────┐  ┌────────┐
        │              │         │  │   AI   │  │ Phase  │
        │              │         │  │ Quorum │  │   1    │
        │              │         │  │  Path  │  │ Result │
        │              │         │  │        │  │        │
        │              │         │  │ Semantic│  │ Medium │
        │              │         │  │  1-2s  │  │  Conf  │
        │              │         │  └────────┘  └────────┘
        │              │         │      │            │
        └──────────────┴─────────┴──────┴────────────┘
                       │
                       ↓
              ┌────────────────┐
              │ Check Cache    │
              │ (both paths)   │
              └────────┬───────┘
                       │
               ┌───────┴────────┐
               │                │
            HIT (5ms)         MISS
               │                │
               ↓                ↓
         ┌─────────┐    ┌──────────────┐
         │ Return  │    │ Execute Path │
         │ Cached  │    │ (AI or P1)   │
         │ Result  │    └──────┬───────┘
         └─────────┘           │
               │               ↓
               │        ┌─────────────┐
               │        │ Cache Result│
               │        │ Log Decision│
               │        └──────┬──────┘
               │               │
               └───────────────┘
                       │
                       ↓
              ┌────────────────┐
              │ Return Ranked  │
              │ Recommendations│
              └────────────────┘
```

### Path Selection Criteria

#### Phase 1 Fast Path (50-100ms)

**Use When:**
- ✅ Explicit agent mention detected
- ✅ Single high-confidence match (>0.9)
- ✅ Simple keyword-based query
- ✅ Historical success rate >95% for this query pattern
- ✅ User preference for speed over accuracy
- ✅ Fast path explicitly requested in context

**Characteristics:**
- Fuzzy trigger matching
- 4-component confidence scoring
- Capability index lookups
- Result caching (1-hour TTL)
- 80% estimated accuracy

#### AI Quorum Path (1-2s)

**Use When:**
- ✅ Complex multi-part query
- ✅ Ambiguous intent or unclear domain
- ✅ Multiple similar Phase 1 candidates (3+ with >0.7 confidence)
- ✅ Low Phase 1 confidence (<0.7)
- ✅ Novel query pattern (no cache hit)
- ✅ Query contains uncertainty indicators: "not sure", "help choose", "best for"
- ✅ Cross-domain query requiring semantic understanding

**Characteristics:**
- Multi-model semantic analysis
- Weighted consensus building
- Deep capability reasoning
- Workflow planning for complex tasks
- 90%+ target accuracy

---

## AI Quorum Infrastructure

### Model Configuration

```python
AI_QUORUM_CONFIG = {
    "models": [
        {
            "name": "deepseek-r1",
            "endpoint": "http://192.168.86.200:11434/api/generate",
            "model_id": "deepseek-r1:14b-distill-qwen-q8_0",
            "weight": 2.0,
            "timeout_seconds": 5,
            "priority": "primary",
            "hardware": "RTX 5090",
            "strengths": ["semantic_understanding", "complex_reasoning", "intent_analysis"],
            "use_cases": ["ambiguous_queries", "multi_domain", "workflow_planning"]
        },
        {
            "name": "llama3.1",
            "endpoint": "http://192.168.86.200:11434/api/generate",
            "model_id": "llama3.1:70b-instruct-q4_K_M",
            "weight": 1.2,
            "timeout_seconds": 5,
            "priority": "primary",
            "hardware": "RTX 4090",
            "strengths": ["general_reasoning", "pattern_recognition", "consistency"],
            "use_cases": ["validation", "consensus_building", "uncertainty_reduction"]
        },
        {
            "name": "codestral",
            "endpoint": "http://192.168.86.200:11434/api/generate",
            "model_id": "codestral:22b-v0.1-q4_K_M",
            "weight": 1.5,
            "timeout_seconds": 5,
            "priority": "secondary",
            "hardware": "Mac Studio",
            "strengths": ["code_understanding", "technical_queries", "framework_knowledge"],
            "use_cases": ["code_focused_queries", "technical_decisions", "framework_selection"]
        },
        {
            "name": "deepseek-coder",
            "endpoint": "http://192.168.86.200:11434/api/generate",
            "model_id": "deepseek-coder:33b-instruct-q4_K_M",
            "weight": 1.8,
            "timeout_seconds": 5,
            "priority": "secondary",
            "hardware": "Mac Mini",
            "strengths": ["architectural_analysis", "system_design", "code_patterns"],
            "use_cases": ["architecture_queries", "system_design", "pattern_matching"]
        },
        {
            "name": "gemini-flash",
            "endpoint": "google_ai_api",
            "model_id": "gemini-2.5-flash",
            "weight": 1.0,
            "timeout_seconds": 5,
            "priority": "tertiary",
            "hardware": "Google Cloud",
            "strengths": ["reliability", "availability", "general_knowledge"],
            "use_cases": ["fallback", "cloud_backup", "high_availability"]
        }
    ],
    "consensus": {
        "minimum_models": 2,  # Need at least 2 models for consensus
        "auto_apply_threshold": 0.80,  # ≥80% consensus → auto-select
        "suggest_threshold": 0.60,  # ≥60% consensus → suggest with review
        "review_threshold": 0.40,  # ≥40% consensus → present options
        "fallback_threshold": 0.00,  # <40% consensus → fallback to Phase 1
    },
    "performance": {
        "parallel_requests": True,
        "max_concurrent": 5,
        "total_timeout_seconds": 10,
        "retry_on_timeout": False,
        "cache_responses": True,
        "cache_ttl_seconds": 3600
    }
}
```

### Consensus Algorithm

```python
def build_consensus(
    responses: List[ModelResponse],
    agent_registry: dict,
    max_recommendations: int = 3
) -> ConsensusResult:
    """
    Build consensus from multiple AI model responses.

    Algorithm:
    1. Parse each model's recommendations
    2. Weight by model weight (5090=2.0, 4090=1.2, etc.)
    3. Aggregate scores per agent
    4. Calculate consensus strength
    5. Synthesize unified reasoning
    6. Rank by weighted consensus
    7. Return top N recommendations

    Consensus Score Calculation:
    - For each agent mentioned by models:
      - Sum: (model_confidence * model_weight) for all mentions
      - Divide by: sum(model_weights) for responding models
      - Result: 0.0-1.0 consensus score

    Example:
    Agent X recommended by:
    - 5090 (weight=2.0, confidence=0.9) → 1.8
    - 4090 (weight=1.2, confidence=0.85) → 1.02
    - Mac Studio (weight=1.5, confidence=0.75) → 1.125
    Total: 3.945
    Total weights: 4.7
    Consensus: 3.945 / 4.7 = 0.84 (84% consensus)
    """

    agent_votes = defaultdict(lambda: {
        "weighted_confidence": 0.0,
        "vote_count": 0,
        "reasoning_texts": [],
        "capabilities": set(),
        "model_names": [],
        "individual_confidences": []
    })

    total_weight = sum(r.model_weight for r in responses if r.success)

    # Aggregate votes
    for response in responses:
        if not response.success:
            continue

        for recommendation in response.recommendations:
            agent_id = recommendation["agent_name"]
            confidence = recommendation["confidence"]
            weighted = confidence * response.model_weight

            agent_votes[agent_id]["weighted_confidence"] += weighted
            agent_votes[agent_id]["vote_count"] += 1
            agent_votes[agent_id]["reasoning_texts"].append(recommendation["reasoning"])
            agent_votes[agent_id]["capabilities"].update(recommendation.get("capabilities_match", []))
            agent_votes[agent_id]["model_names"].append(response.model_name)
            agent_votes[agent_id]["individual_confidences"].append({
                "model": response.model_name,
                "confidence": confidence,
                "weight": response.model_weight
            })

    # Calculate consensus scores
    consensus_recommendations = []
    for agent_id, vote_data in agent_votes.items():
        consensus_score = vote_data["weighted_confidence"] / total_weight

        # Synthesize reasoning from multiple models
        synthesized_reasoning = synthesize_reasoning(vote_data["reasoning_texts"])

        # Get agent metadata
        agent_meta = agent_registry["agents"][agent_id]

        consensus_recommendations.append(ConsensusRecommendation(
            agent_name=agent_id,
            agent_title=agent_meta["title"],
            consensus_score=consensus_score,
            vote_count=vote_data["vote_count"],
            reasoning=synthesized_reasoning,
            capabilities_match=list(vote_data["capabilities"]),
            model_agreement=vote_data["model_names"],
            confidence_breakdown=vote_data["individual_confidences"],
            definition_path=agent_meta["definition_path"]
        ))

    # Sort by consensus score
    consensus_recommendations.sort(key=lambda x: x.consensus_score, reverse=True)

    # Calculate overall consensus strength
    if consensus_recommendations:
        consensus_strength = consensus_recommendations[0].consensus_score
    else:
        consensus_strength = 0.0

    return ConsensusResult(
        recommendations=consensus_recommendations[:max_recommendations],
        consensus_strength=consensus_strength,
        models_consulted=len([r for r in responses if r.success]),
        total_models=len(responses),
        processing_time_ms=sum(r.processing_time_ms for r in responses if r.success)
    )


def synthesize_reasoning(reasoning_texts: List[str]) -> str:
    """
    Synthesize unified reasoning from multiple model explanations.

    Strategy:
    1. Extract common themes/keywords
    2. Identify primary justification (most frequent)
    3. Combine complementary explanations
    4. Remove redundancy
    5. Generate coherent 2-3 sentence summary
    """

    if len(reasoning_texts) == 1:
        return reasoning_texts[0]

    # Extract common phrases (3+ words)
    common_phrases = extract_common_phrases(reasoning_texts, min_length=3)

    # Build synthesis
    primary_justification = reasoning_texts[0]  # Highest weighted model

    # Add complementary insights from other models
    complementary = []
    for text in reasoning_texts[1:]:
        # Extract unique insights not in primary
        unique_insights = extract_unique_insights(text, primary_justification)
        if unique_insights:
            complementary.append(unique_insights)

    # Combine into coherent summary
    synthesis = primary_justification
    if complementary:
        synthesis += " " + " ".join(complementary[:2])  # Max 2 complementary insights

    return synthesis
```

---

## Caching Strategy

### Unified Cache Architecture

```python
class UnifiedRoutingCache:
    """
    Unified cache for both Phase 1 and AI Quorum routing results.

    Key Design:
    - Hash: SHA-256(query + context)
    - Value: RoutingResult with metadata
    - TTL: 1 hour (configurable)
    - Storage: In-memory dict with timestamp tracking
    """

    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, CacheEntry] = {}
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def generate_key(self, query: str, context: dict) -> str:
        """
        Generate cache key from query and context.

        Includes:
        - Query text (lowercase, stripped)
        - Domain context
        - Previous agent (workflow continuity)
        - Current file extension (language context)

        Excludes:
        - Timestamps
        - User IDs
        - Session IDs
        """
        key_components = {
            "query": query.lower().strip(),
            "domain": context.get("domain", "general"),
            "previous_agent": context.get("previous_agent"),
            "file_extension": self._extract_extension(context.get("current_file"))
        }

        key_string = json.dumps(key_components, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    def get(self, key: str) -> Optional[RoutingResult]:
        """
        Get cached result if not expired.
        """
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        # Check expiration
        if time.time() - entry.timestamp > self.ttl_seconds:
            del self.cache[key]
            self.evictions += 1
            self.misses += 1
            return None

        self.hits += 1
        return entry.result

    def set(self, key: str, result: RoutingResult):
        """
        Store routing result with timestamp.
        """
        self.cache[key] = CacheEntry(
            result=result,
            timestamp=time.time()
        )

    def get_stats(self) -> dict:
        """
        Get cache performance statistics.
        """
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0.0

        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_requests": total_requests,
            "hit_rate": hit_rate,
            "current_size": len(self.cache),
            "ttl_seconds": self.ttl_seconds
        }

    def invalidate_pattern(self, pattern: str):
        """
        Invalidate cache entries matching pattern.
        """
        keys_to_delete = [
            key for key, entry in self.cache.items()
            if pattern.lower() in entry.result.query.lower()
        ]
        for key in keys_to_delete:
            del self.cache[key]

    def clear(self):
        """
        Clear entire cache.
        """
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
```

### Cache Warming Strategy

```python
def warm_cache(router: AIRoutingIntelligence, common_queries: List[str]):
    """
    Pre-populate cache with common query patterns.

    Strategy:
    1. Load 100 most common queries from analytics
    2. Route through AI Quorum
    3. Cache results
    4. Reduces cold start latency for new sessions
    """

    print("Warming routing cache...")

    for i, query in enumerate(common_queries):
        try:
            # Route and cache
            router.route(query, context={"domain": "general"})
            print(f"[{i+1}/{len(common_queries)}] Cached: {query[:50]}...")
        except Exception as e:
            print(f"Failed to cache: {query[:50]}... - {e}")

    stats = router.cache.get_stats()
    print(f"\nCache warmed: {stats['current_size']} entries")


# Example: Load common queries from analytics
common_queries = [
    "debug production error",
    "optimize API performance",
    "create semantic commit message",
    "review code quality",
    "setup CI/CD pipeline",
    "write unit tests",
    "design REST API",
    "monitor production systems",
    "analyze security vulnerabilities",
    "refactor code for maintainability"
]

warm_cache(routing_intelligence, common_queries)
```

---

## Fallback & Error Handling

### Fallback Cascade

```
Primary: AI Quorum (DeepSeek-R1 + Llama 3.1)
  ↓ (timeout or error)
Secondary: Mac Studio (Codestral) + Mac Mini (DeepSeek-Coder)
  ↓ (timeout or error)
Tertiary: Gemini Flash (cloud)
  ↓ (timeout or error)
Quaternary: Phase 1 Filesystem Routing
  ↓ (guaranteed success)
Return: Best available result
```

### Error Handling Strategy

```python
class AIRoutingError(Exception):
    """Base exception for AI routing errors."""
    pass

class ModelTimeoutError(AIRoutingError):
    """Model did not respond within timeout."""
    pass

class ModelResponseError(AIRoutingError):
    """Model returned invalid or unparseable response."""
    pass

class AllModelsFailedError(AIRoutingError):
    """All AI models failed, must fallback to Phase 1."""
    pass


async def route_with_fallback(query: str, context: dict) -> RoutingResult:
    """
    Route with comprehensive fallback cascade.
    """

    try:
        # Try AI Quorum (primary + secondary models)
        return await route_with_ai_quorum(query, context)

    except ModelTimeoutError as e:
        logger.warning(f"AI Quorum timeout: {e}, trying tertiary models")

        try:
            # Try Gemini Flash (tertiary)
            return await route_with_gemini(query, context)

        except Exception as e2:
            logger.error(f"Tertiary models failed: {e2}, falling back to Phase 1")

    except AllModelsFailedError as e:
        logger.error(f"All AI models failed: {e}, falling back to Phase 1")

    # Ultimate fallback: Phase 1 guaranteed success
    return route_with_phase1(query, context)


async def route_with_ai_quorum(query: str, context: dict) -> RoutingResult:
    """
    Route using AI Quorum with progressive fallback.
    """

    # Try primary models (5090 + 4090)
    primary_responses = await asyncio.gather(
        query_model(AI_QUORUM_CONFIG["models"][0], query, context),  # 5090
        query_model(AI_QUORUM_CONFIG["models"][1], query, context),  # 4090
        return_exceptions=True
    )

    # Filter successful responses
    successful_primary = [r for r in primary_responses if not isinstance(r, Exception)]

    if len(successful_primary) >= 2:
        # Both primary models responded - build consensus
        return build_consensus(successful_primary, agent_registry)

    # Try secondary models (Mac Studio + Mac Mini)
    secondary_responses = await asyncio.gather(
        query_model(AI_QUORUM_CONFIG["models"][2], query, context),  # Codestral
        query_model(AI_QUORUM_CONFIG["models"][3], query, context),  # DeepSeek-Coder
        return_exceptions=True
    )

    successful_secondary = [r for r in secondary_responses if not isinstance(r, Exception)]

    # Combine all successful responses
    all_successful = successful_primary + successful_secondary

    if len(all_successful) >= 2:
        # Have enough models for consensus
        return build_consensus(all_successful, agent_registry)

    if len(all_successful) == 1:
        # Only one model responded - use its recommendation
        logger.warning("Only 1 AI model responded, using single model result")
        return convert_single_response(all_successful[0])

    # All models failed
    raise AllModelsFailedError(f"All AI models failed for query: {query[:50]}")
```

---

## Learning & Analytics System

### Supabase Schema

```sql
-- Routing decisions table
CREATE TABLE routing_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Query data
    user_query TEXT NOT NULL,
    query_hash TEXT NOT NULL,  -- SHA-256 for deduplication
    query_complexity VARCHAR(20),  -- 'simple' | 'moderate' | 'high'
    context JSONB,

    -- Routing data
    routing_path TEXT NOT NULL,  -- 'phase1_fast_path' | 'ai_quorum' | 'ai_cache_hit' | 'ai_fallback'
    recommendations JSONB NOT NULL,  -- Array of recommendations with scores
    selected_agent TEXT,  -- Which agent user actually selected
    selection_rank INTEGER,  -- Was it 1st, 2nd, 3rd recommendation?

    -- Performance data
    processing_time_ms INTEGER,
    cache_hit BOOLEAN,
    consensus_score FLOAT,

    -- AI Quorum data (if applicable)
    ai_models_used TEXT[],
    ai_model_count INTEGER,
    ai_responses JSONB,

    -- User feedback (collected asynchronously)
    user_feedback TEXT,  -- 'helpful' | 'somewhat_helpful' | 'not_helpful'
    task_success BOOLEAN,  -- Did the agent successfully complete the task?
    task_duration_seconds INTEGER,
    user_notes TEXT
);

-- Indexes for performance
CREATE INDEX idx_routing_decisions_query_hash ON routing_decisions(query_hash);
CREATE INDEX idx_routing_decisions_selected_agent ON routing_decisions(selected_agent);
CREATE INDEX idx_routing_decisions_routing_path ON routing_decisions(routing_path);
CREATE INDEX idx_routing_decisions_created_at ON routing_decisions(created_at DESC);
CREATE INDEX idx_routing_decisions_consensus_score ON routing_decisions(consensus_score DESC);

-- Agent success metrics table
CREATE TABLE agent_success_metrics (
    agent_name TEXT PRIMARY KEY,
    agent_title TEXT NOT NULL,
    category TEXT NOT NULL,

    -- Recommendation stats
    total_recommendations INTEGER DEFAULT 0,
    total_selections INTEGER DEFAULT 0,
    selection_rate FLOAT DEFAULT 0.0,  -- selections / recommendations

    -- Rank stats (where in recommendation list was it selected?)
    rank_1_selections INTEGER DEFAULT 0,  -- Selected when it was #1 recommendation
    rank_2_selections INTEGER DEFAULT 0,
    rank_3_selections INTEGER DEFAULT 0,

    -- Success metrics
    successful_tasks INTEGER DEFAULT 0,
    failed_tasks INTEGER DEFAULT 0,
    success_rate FLOAT DEFAULT 0.0,

    -- Performance metrics
    avg_task_duration_seconds INTEGER,
    avg_consensus_score FLOAT,

    -- User feedback
    helpful_count INTEGER DEFAULT 0,
    somewhat_helpful_count INTEGER DEFAULT 0,
    not_helpful_count INTEGER DEFAULT 0,
    avg_helpfulness FLOAT DEFAULT 0.0,

    -- Temporal tracking
    last_selected_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_agent_metrics_selection_rate ON agent_success_metrics(selection_rate DESC);
CREATE INDEX idx_agent_metrics_success_rate ON agent_success_metrics(success_rate DESC);
CREATE INDEX idx_agent_metrics_category ON agent_success_metrics(category);

-- Query complexity patterns table
CREATE TABLE query_complexity_patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Pattern data
    pattern_type VARCHAR(50) NOT NULL,  -- 'explicit_agent' | 'simple_keyword' | 'multi_domain' | 'ambiguous'
    pattern_regex TEXT,
    example_queries TEXT[],

    -- Performance data
    count INTEGER DEFAULT 0,
    phase1_success_rate FLOAT,
    ai_routing_success_rate FLOAT,
    recommended_path VARCHAR(20)  -- 'phase1' | 'ai_quorum'
);

-- Routing path performance table
CREATE TABLE routing_path_performance (
    date DATE PRIMARY KEY,

    -- Volume stats
    total_queries INTEGER DEFAULT 0,
    phase1_fast_path_count INTEGER DEFAULT 0,
    ai_quorum_count INTEGER DEFAULT 0,
    ai_cache_hit_count INTEGER DEFAULT 0,
    ai_fallback_count INTEGER DEFAULT 0,

    -- Accuracy stats
    phase1_accuracy FLOAT,
    ai_quorum_accuracy FLOAT,
    overall_accuracy FLOAT,

    -- Performance stats
    avg_phase1_latency_ms INTEGER,
    avg_ai_quorum_latency_ms INTEGER,
    cache_hit_rate FLOAT,

    -- Cost stats (future)
    local_model_calls INTEGER,
    cloud_model_calls INTEGER,
    estimated_cost_usd FLOAT
);
```

### Analytics Queries

```sql
-- Daily routing performance summary
SELECT
    date,
    total_queries,
    phase1_fast_path_count,
    ai_quorum_count,
    ai_cache_hit_count,
    ROUND(phase1_accuracy, 3) as phase1_acc,
    ROUND(ai_quorum_accuracy, 3) as ai_acc,
    ROUND(overall_accuracy, 3) as overall_acc,
    ROUND(cache_hit_rate, 3) as cache_rate,
    avg_phase1_latency_ms,
    avg_ai_quorum_latency_ms
FROM routing_path_performance
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY date DESC;

-- Top performing agents
SELECT
    agent_name,
    agent_title,
    category,
    total_selections,
    ROUND(selection_rate, 3) as sel_rate,
    ROUND(success_rate, 3) as success_rate,
    ROUND(avg_helpfulness, 2) as helpfulness,
    rank_1_selections,
    last_selected_at
FROM agent_success_metrics
WHERE total_recommendations >= 10  -- Minimum sample size
ORDER BY success_rate DESC, selection_rate DESC
LIMIT 20;

-- Underperforming agents (candidates for improvement)
SELECT
    agent_name,
    agent_title,
    total_recommendations,
    total_selections,
    ROUND(selection_rate, 3) as sel_rate,
    ROUND(success_rate, 3) as success_rate,
    ROUND(avg_helpfulness, 2) as helpfulness
FROM agent_success_metrics
WHERE
    total_recommendations >= 20  -- Sufficient sample size
    AND (selection_rate < 0.5 OR success_rate < 0.7)
ORDER BY selection_rate ASC, success_rate ASC
LIMIT 10;

-- AI Quorum model performance
SELECT
    UNNEST(ai_models_used) as model_name,
    COUNT(*) as queries_handled,
    ROUND(AVG(consensus_score), 3) as avg_consensus,
    ROUND(AVG(processing_time_ms), 0) as avg_latency_ms,
    COUNT(*) FILTER (WHERE selection_rank = 1) as top_pick_count
FROM routing_decisions
WHERE routing_path = 'ai_quorum'
    AND created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY model_name
ORDER BY queries_handled DESC;

-- Query complexity distribution
SELECT
    query_complexity,
    COUNT(*) as count,
    ROUND(AVG(processing_time_ms), 0) as avg_latency,
    ROUND(AVG(consensus_score), 3) as avg_consensus,
    COUNT(*) FILTER (WHERE routing_path = 'phase1_fast_path') as phase1_count,
    COUNT(*) FILTER (WHERE routing_path = 'ai_quorum') as ai_count
FROM routing_decisions
WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY query_complexity
ORDER BY count DESC;

-- Cache effectiveness analysis
SELECT
    DATE(created_at) as date,
    COUNT(*) as total_queries,
    COUNT(*) FILTER (WHERE cache_hit = true) as cache_hits,
    ROUND(COUNT(*) FILTER (WHERE cache_hit = true)::FLOAT / COUNT(*), 3) as hit_rate,
    ROUND(AVG(processing_time_ms) FILTER (WHERE cache_hit = true), 0) as avg_hit_latency,
    ROUND(AVG(processing_time_ms) FILTER (WHERE cache_hit = false), 0) as avg_miss_latency
FROM routing_decisions
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

---

## Performance Optimization

### Parallel Request Optimization

```python
async def parallel_ai_quorum_request(query: str, context: dict) -> List[ModelResponse]:
    """
    Optimize parallel AI model requests for minimal latency.

    Optimizations:
    1. Fire all requests simultaneously
    2. Return as soon as minimum models respond (2+)
    3. Cancel remaining requests after threshold
    4. Use asyncio.gather with return_exceptions=True
    """

    # Fire all model requests in parallel
    tasks = [
        asyncio.create_task(query_model(model_config, query, context))
        for model_config in AI_QUORUM_CONFIG["models"]
    ]

    responses = []
    min_models = AI_QUORUM_CONFIG["consensus"]["minimum_models"]

    # Use asyncio.wait with FIRST_COMPLETED to return early
    done, pending = await asyncio.wait(
        tasks,
        timeout=AI_QUORUM_CONFIG["performance"]["total_timeout_seconds"],
        return_when=asyncio.FIRST_COMPLETED  # Return as soon as first completes
    )

    # Collect responses as they complete
    while done:
        for task in done:
            try:
                response = await task
                if response.success:
                    responses.append(response)
            except Exception as e:
                logger.warning(f"Model query failed: {e}")

        # Check if we have enough responses
        if len(responses) >= min_models and pending:
            # Have enough models, cancel remaining
            for task in pending:
                task.cancel()
            break

        # Wait for more to complete
        if pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED
            )
        else:
            break

    return responses
```

### Caching Optimization

```python
class OptimizedCache:
    """
    Memory-efficient cache with LRU eviction.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache = OrderedDict()  # LRU ordering
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[RoutingResult]:
        """
        Get with LRU update.
        """
        if key not in self.cache:
            self.misses += 1
            return None

        entry = self.cache[key]

        # Check expiration
        if time.time() - entry.timestamp > self.ttl_seconds:
            del self.cache[key]
            self.misses += 1
            return None

        # Move to end (most recently used)
        self.cache.move_to_end(key)
        self.hits += 1
        return entry.result

    def set(self, key: str, result: RoutingResult):
        """
        Set with LRU eviction.
        """
        # Evict if at capacity
        if len(self.cache) >= self.max_size:
            # Remove oldest (first) item
            self.cache.popitem(last=False)

        # Add new entry (at end)
        self.cache[key] = CacheEntry(
            result=result,
            timestamp=time.time()
        )

    def cleanup_expired(self):
        """
        Periodic cleanup of expired entries.
        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items()
            if current_time - entry.timestamp > self.ttl_seconds
        ]
        for key in expired_keys:
            del self.cache[key]
```

---

## Monitoring & Observability

### Key Metrics to Track

```python
METRICS = {
    # Volume metrics
    "routing.queries.total": Counter("Total routing queries"),
    "routing.path.phase1": Counter("Phase 1 fast path queries"),
    "routing.path.ai_quorum": Counter("AI Quorum path queries"),
    "routing.cache.hits": Counter("Cache hits"),
    "routing.cache.misses": Counter("Cache misses"),

    # Latency metrics (histograms)
    "routing.latency.phase1": Histogram("Phase 1 latency (ms)", buckets=[10, 50, 100, 200, 500]),
    "routing.latency.ai_quorum": Histogram("AI Quorum latency (ms)", buckets=[500, 1000, 2000, 5000, 10000]),
    "routing.latency.cache_hit": Histogram("Cache hit latency (ms)", buckets=[1, 5, 10, 20, 50]),

    # Accuracy metrics (gauges)
    "routing.accuracy.overall": Gauge("Overall routing accuracy"),
    "routing.accuracy.phase1": Gauge("Phase 1 routing accuracy"),
    "routing.accuracy.ai_quorum": Gauge("AI Quorum routing accuracy"),

    # Model health metrics
    "ai_quorum.model.response_rate": Gauge("Model response rate", labels=["model_name"]),
    "ai_quorum.model.latency": Histogram("Model latency (ms)", labels=["model_name"]),
    "ai_quorum.model.errors": Counter("Model errors", labels=["model_name", "error_type"]),

    # Consensus metrics
    "ai_quorum.consensus.score": Histogram("Consensus score", buckets=[0.0, 0.4, 0.6, 0.8, 0.9, 1.0]),
    "ai_quorum.consensus.models": Histogram("Models in consensus", buckets=[1, 2, 3, 4, 5]),

    # Cache metrics
    "cache.hit_rate": Gauge("Cache hit rate"),
    "cache.size": Gauge("Cache size (entries)"),
    "cache.evictions": Counter("Cache evictions"),

    # Agent metrics
    "agent.selections": Counter("Agent selections", labels=["agent_name"]),
    "agent.success_rate": Gauge("Agent task success rate", labels=["agent_name"]),
}
```

### Health Check Endpoints

```python
@app.get("/health/routing")
async def routing_health():
    """
    Comprehensive routing system health check.
    """
    return {
        "status": "healthy",
        "phase1": {
            "status": "healthy",
            "avg_latency_ms": 67,
            "cache_hit_rate": 0.643
        },
        "ai_quorum": {
            "status": "healthy",
            "models": [
                {"name": "deepseek-r1", "status": "healthy", "response_rate": 0.97},
                {"name": "llama3.1", "status": "healthy", "response_rate": 0.94},
                {"name": "codestral", "status": "healthy", "response_rate": 0.91},
                {"name": "deepseek-coder", "status": "degraded", "response_rate": 0.76},
                {"name": "gemini-flash", "status": "healthy", "response_rate": 0.99}
            ],
            "avg_latency_ms": 1342,
            "avg_consensus_score": 0.86
        },
        "cache": {
            "hit_rate": 0.687,
            "size": 432,
            "max_size": 1000
        },
        "accuracy": {
            "overall": 0.88,
            "phase1": 0.81,
            "ai_quorum": 0.92
        }
    }
```

---

## Security & Privacy

### Data Privacy

```python
def anonymize_routing_data(routing_decision: dict) -> dict:
    """
    Anonymize routing decision before storage.

    Remove:
    - User IDs
    - Session IDs
    - File paths (keep only extensions)
    - Project names
    - Any PII in query text
    """
    anonymized = routing_decision.copy()

    # Remove user identifiers
    anonymized.pop("user_id", None)
    anonymized.pop("session_id", None)

    # Anonymize file paths
    if "context" in anonymized and "current_file" in anonymized["context"]:
        file_path = anonymized["context"]["current_file"]
        extension = os.path.splitext(file_path)[1]
        anonymized["context"]["current_file"] = f"**/*{extension}"

    # Remove project names
    anonymized.get("context", {}).pop("project_name", None)

    return anonymized
```

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/route")
@limiter.limit("100/minute")  # Max 100 routing requests per minute per IP
async def route_request(request: RoutingRequest):
    """
    Rate-limited routing endpoint.
    """
    return await routing_intelligence.route(
        request.query,
        request.context,
        request.max_recommendations
    )
```

---

## Deployment Architecture

### Container Setup

```yaml
# docker-compose.yml
services:
  archon-routing:
    build: ./services/routing
    ports:
      - "8060:8060"
    environment:
      - OLLAMA_BASE_URL=http://192.168.86.200:11434
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_KEY=${SUPABASE_KEY}
      - CACHE_TTL_SECONDS=3600
      - LOG_LEVEL=INFO
    volumes:
      - /Users/jonah/.claude/agent-definitions:/app/agent-definitions:ro
      - routing-cache:/app/cache
    depends_on:
      - supabase
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8060/health/routing"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  routing-cache:
```

### Production Configuration

```python
# config/production.py
PRODUCTION_CONFIG = {
    "routing": {
        "default_path": "ai_quorum",  # Default to AI routing in production
        "fallback_to_phase1": True,
        "cache_ttl_seconds": 7200,  # 2 hours in production
        "max_cache_size": 5000
    },
    "ai_quorum": {
        "timeout_seconds": 10,  # More generous timeout
        "parallel_requests": True,
        "retry_on_timeout": False,
        "minimum_models": 2
    },
    "monitoring": {
        "enable_metrics": True,
        "enable_tracing": True,
        "log_level": "INFO",
        "alert_on_accuracy_drop": 0.80  # Alert if accuracy drops below 80%
    },
    "learning": {
        "enable_logging": True,
        "batch_size": 100,  # Batch insert to Supabase
        "log_interval_seconds": 60
    }
}
```

---

## Testing Strategy

See agent-routing-intelligence.md for comprehensive testing documentation.

---

## Future Enhancements

### Phase 6: Advanced Routing Intelligence

1. **Multi-Agent Workflow Planning**
   - Automatic workflow decomposition
   - Agent sequencing and coordination
   - Dependency management

2. **Fine-Tuned Local Model**
   - Train on collected routing decisions
   - <100ms latency
   - 95%+ accuracy

3. **Natural Language Feedback**
   - Real-time learning from corrections
   - Query refinement suggestions
   - Intent clarification

4. **Context-Aware Memory**
   - Session continuity
   - Workflow awareness
   - Previous interaction recall

---

**Document Status**: Complete
**Last Updated**: October 1, 2025
**Next Review**: After Phase 1 Implementation
**Maintainer**: Agent Workflow Coordinator
