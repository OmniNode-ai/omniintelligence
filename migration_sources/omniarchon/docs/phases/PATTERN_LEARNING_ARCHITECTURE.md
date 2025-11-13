# Phase 2-3 Architecture Guide

**Date**: 2025-10-02
**Status**: Production Architecture
**Version**: 1.0.0

## Executive Summary

This guide provides comprehensive architectural documentation for Phase 2 (Hybrid Pattern Matching) and Phase 3 (Quality Gate Orchestration) of the Archon Pattern Learning Engine. The architecture follows ONEX principles with clear separation of concerns, pure compute nodes, and robust error handling.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Phase 2 Architecture](#phase-2-architecture)
3. [Phase 3 Architecture](#phase-3-architecture)
4. [Data Flow Patterns](#data-flow-patterns)
5. [Integration Architecture](#integration-architecture)
6. [Performance Architecture](#performance-architecture)
7. [Monitoring & Observability](#monitoring--observability)
8. [Security Architecture](#security-architecture)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Pattern Learning Engine                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────┐         ┌──────────────────────┐        │
│  │   Phase 2: Hybrid    │         │  Phase 3: Quality    │        │
│  │  Pattern Matching    │────────▶│  Gate Orchestration  │        │
│  │                      │         │                      │        │
│  │  • Pattern Scoring   │         │  • ONEX Validation   │        │
│  │  • Vector Matching   │         │  • Coverage Gates    │        │
│  │  • Semantic Cache    │         │  • Quality Gates     │        │
│  │  • Langextract       │         │  • Security Gates    │        │
│  └──────────────────────┘         └──────────────────────┘        │
│           │                                   │                     │
│           ▼                                   ▼                     │
│  ┌─────────────────────────────────────────────────────┐          │
│  │          Intelligence Service (Port 8053)           │          │
│  └─────────────────────────────────────────────────────┘          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### ONEX Node Type Distribution

```
Node Types Used:
├── Compute (Pure Functions)
│   ├── NodePatternSimilarityCompute      # 5-component scoring
│   ├── NodeHybridScorerCompute           # Vector + Pattern fusion
│   ├── OptimizerCacheTuning              # Cache optimization
│   └── NodeOnexValidatorCompute          # ONEX compliance
│
├── Effect (I/O Operations)
│   ├── ClientLangextractHttp             # HTTP client
│   ├── NodeComplianceReporterEffect      # Report generation
│   └── NodeReportStorageEffect           # Persistence
│
├── Reducer (State Management)
│   └── ReducerSemanticCache              # Cache management
│
└── Orchestrator (Workflow Coordination)
    ├── NodeQualityGateOrchestrator       # Gate orchestration
    └── NodeConsensusValidatorOrchestrator # Multi-model consensus
```

---

## Phase 2 Architecture

### Component Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Phase 2: Hybrid Pattern Matching                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  1. Task Input                                               │   │
│  │     • User query/description                                 │   │
│  │     • Context metadata                                       │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  2. Langextract Integration (Effect Node)                   │   │
│  │     ┌─────────────────────────────────────────────────┐    │   │
│  │     │  ClientLangextractHttp                          │    │   │
│  │     │  • Circuit breaker (5 failures → open)          │    │   │
│  │     │  • Exponential backoff (1s, 2s, 4s)            │    │   │
│  │     │  • Connection pooling                           │    │   │
│  │     │  • Request/response validation                  │    │   │
│  │     └─────────────────────────────────────────────────┘    │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  3. Semantic Cache (Reducer Node)                          │   │
│  │     ┌─────────────────────────────────────────────────┐    │   │
│  │     │  ReducerSemanticCache                           │    │   │
│  │     │  • Memory cache (24μs retrieval)                │    │   │
│  │     │  • Redis backup (5ms fallback)                  │    │   │
│  │     │  • LRU eviction                                 │    │   │
│  │     │  • TTL management (1 hour default)             │    │   │
│  │     └─────────────────────────────────────────────────┘    │   │
│  │              Cache Hit ─┐      Cache Miss                  │   │
│  └────────────────────────┼────────────┬────────────────────────┘   │
│                            │            │                             │
│           ┌────────────────┘            └──────────────┐            │
│           ▼                                            ▼            │
│  ┌──────────────────┐                    ┌────────────────────┐   │
│  │  Return Cached   │                    │  Fetch from        │   │
│  │  Semantic Data   │                    │  Langextract       │   │
│  └────────┬─────────┘                    └──────┬─────────────┘   │
│           │                                      │                  │
│           └──────────────┬───────────────────────┘                  │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  4. Pattern Similarity Scoring (Compute Node)               │   │
│  │     ┌─────────────────────────────────────────────────┐    │   │
│  │     │  NodePatternSimilarityCompute                   │    │   │
│  │     │  • Concept overlap (30%)                        │    │   │
│  │     │  • Theme similarity (20%)                       │    │   │
│  │     │  • Domain alignment (20%)                       │    │   │
│  │     │  • Structural patterns (15%)                    │    │   │
│  │     │  • Relationship matching (15%)                  │    │   │
│  │     │  Performance: ~0.03ms per comparison            │    │   │
│  │     └─────────────────────────────────────────────────┘    │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  5. Hybrid Scoring (Compute Node)                          │   │
│  │     ┌─────────────────────────────────────────────────┐    │   │
│  │     │  NodeHybridScorerCompute                        │    │   │
│  │     │  • Combines vector (70%) + pattern (30%)        │    │   │
│  │     │  • Adaptive weight adjustment                   │    │   │
│  │     │  • Score normalization (0.0-1.0)               │    │   │
│  │     │  Performance: ~10ms total                       │    │   │
│  │     └─────────────────────────────────────────────────┘    │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  6. Results Output                                          │   │
│  │     • Hybrid similarity score (0.0-1.0)                     │   │
│  │     • Component breakdown (vector/pattern)                  │   │
│  │     • Performance metadata                                  │   │
│  │     • Correlation ID for tracing                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘

         Parallel Components (Performance Optimization)

┌──────────────────────────────────────────────────────────────────────┐
│                                                                       │
│  ┌────────────────────────────┐    ┌────────────────────────────┐  │
│  │  Cache Optimizer           │    │  Monitoring & Metrics      │  │
│  │  (Background Process)      │    │  (Real-time Collection)    │  │
│  │                            │    │                            │  │
│  │  • Hit rate analysis       │    │  • 25+ Prometheus metrics  │  │
│  │  • TTL tuning              │    │  • Context managers        │  │
│  │  • Size optimization       │    │  • Decorators              │  │
│  │  • Cache warming           │    │  • Structured logging      │  │
│  └────────────────────────────┘    └────────────────────────────┘  │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Phase 2 Data Flow

#### Primary Path (Cache Hit)

```
User Query
    │
    ▼
Semantic Analysis Request
    │
    ▼
┌─────────────────────┐
│ Semantic Cache      │
│ CHECK               │──────────────────┐
└─────────────────────┘                  │
    │ (Cache Hit - 24μs)                 │ (Cache Miss)
    ▼                                    ▼
┌─────────────────────┐        ┌─────────────────────┐
│ Return Cached       │        │ Langextract HTTP    │
│ Semantic Result     │        │ Request             │
└─────────────────────┘        │ • Circuit breaker   │
    │                          │ • Retry logic       │
    ▼                          └─────────────────────┘
Pattern Similarity                       │
    │                                    ▼
    ▼                          ┌─────────────────────┐
Hybrid Scoring                 │ Cache STORE         │
    │                          └─────────────────────┘
    ▼                                    │
Final Score                              │
                                        ▼
                            Pattern Similarity
                                        │
                                        ▼
                            Hybrid Scoring
                                        │
                                        ▼
                            Final Score
```

#### Performance Characteristics

```
Operation Timing Breakdown:

Total Path (Cache Hit):    ~10.03ms
├── Cache Lookup:           0.024ms  (0.2%)
├── Pattern Scoring:        0.030ms  (0.3%)
└── Hybrid Calculation:     10.000ms (99.5%)

Total Path (Cache Miss):   ~210.03ms
├── Langextract Request:    200.00ms (95.2%)
├── Cache Store:            0.010ms  (0.0%)
├── Pattern Scoring:        0.030ms  (0.0%)
└── Hybrid Calculation:     10.000ms (4.8%)

Cache Hit Savings: ~200ms (95% faster)
```

### Circuit Breaker State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                Circuit Breaker States                        │
└─────────────────────────────────────────────────────────────┘

        ┌────────────┐
        │   CLOSED   │◀──────────────────┐
        │ (Normal)   │                   │
        └──────┬─────┘                   │
               │                         │
         Failure Count                   │
         Reaches 5                 Success Count
               │                   Reaches 3
               ▼                         │
        ┌────────────┐            ┌──────┴──────┐
        │    OPEN    │───────────▶│  HALF-OPEN  │
        │ (Blocking) │   After 60s│  (Testing)  │
        └────────────┘            └─────────────┘
               │                         │
               │                   Failure
         All Requests              (Any)
         Rejected                        │
               │                         │
               └─────────────────────────┘
                   Immediate Fail

Configuration:
• Failure Threshold: 5 failures
• Recovery Time: 60 seconds
• Half-Open Test: 3 successes required
• Failure Types: HTTP errors, timeouts, validation
```

---

## Phase 3 Architecture

### Quality Gate Orchestration Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│              Phase 3: Quality Gate Orchestration                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Input: ModelQualityGateInput                               │   │
│  │  • code_path: str                                           │   │
│  │  • gate_configs: List[ModelGateConfig]                      │   │
│  │  • parallel_execution: bool                                 │   │
│  │  • fail_fast: bool                                          │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  NodeQualityGateOrchestrator                                │   │
│  │  (Orchestrator Node - 930 lines)                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│           │                                                           │
│           │ Parallel Mode                 Sequential Mode            │
│           ▼                                     ▼                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  Gate Execution                             │   │
│  │                                                              │   │
│  │  Parallel:                      Sequential:                 │   │
│  │  ┌──────────┐                   ┌──────────┐               │   │
│  │  │  Gate 1  │                   │  Gate 1  │               │   │
│  │  │  Gate 2  │ ──All Run──▶      │    ↓     │ ──Ordered──▶ │   │
│  │  │  Gate 3  │  Together         │  Gate 2  │    Chain      │   │
│  │  │  Gate 4  │                   │    ↓     │               │   │
│  │  │  Gate 5  │                   │  Gate 3  │               │   │
│  │  └──────────┘                   │    ↓     │               │   │
│  │   ~18s total                    │  Gate 4  │               │   │
│  │                                  │    ↓     │               │   │
│  │                                  │  Gate 5  │               │   │
│  │                                  └──────────┘               │   │
│  │                                   ~45s total                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                            ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Output: ModelQualityGateResult                             │   │
│  │  • overall_passed: bool                                     │   │
│  │  • gate_results: List[GateResult]                           │   │
│  │  • blocking_failures: List[str]                             │   │
│  │  • total_duration_ms: float                                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Individual Quality Gates

```
┌──────────────────────────────────────────────────────────────────────┐
│                        5 Quality Gates                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  1. ONEX Compliance Gate                                            │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  NodeOnexValidatorCompute (540 lines)                      │   │
│  │                                                              │   │
│  │  Validation Checks:                                         │   │
│  │  ├── File naming:  node_*_<type>.py ✓                     │   │
│  │  ├── Class naming: Node<Name><Type> ✓                     │   │
│  │  ├── Methods:      execute_<type>() ✓                     │   │
│  │  ├── Contracts:    ModelContract* ✓                       │   │
│  │  └── Structure:    ONEX compliance ✓                      │   │
│  │                                                              │   │
│  │  Scoring: Start 1.0, deduct by severity                    │   │
│  │  • CRITICAL: -0.20                                         │   │
│  │  • HIGH:     -0.10                                         │   │
│  │  • MEDIUM:   -0.05                                         │   │
│  │  • LOW:      -0.02                                         │   │
│  │                                                              │   │
│  │  Performance: ~2s                                           │   │
│  │  Coverage: 89% (25/25 tests passing)                       │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  2. Test Coverage Gate                                              │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Integration: pytest-cov                                    │   │
│  │                                                              │   │
│  │  • Runs pytest with coverage analysis                      │   │
│  │  • Checks statement coverage percentage                    │   │
│  │  • Validates test execution                                │   │
│  │  • Default threshold: 90%                                  │   │
│  │                                                              │   │
│  │  Performance: ~5s (depends on test suite)                  │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  3. Code Quality Gate                                               │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Integration: pylint (optional)                             │   │
│  │                                                              │   │
│  │  • Static code analysis                                     │   │
│  │  • Style violations                                         │   │
│  │  • Potential bugs                                           │   │
│  │  • Complexity metrics                                       │   │
│  │                                                              │   │
│  │  Performance: ~3s                                           │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  4. Performance Gate                                                │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Anti-Pattern Detection                                     │   │
│  │                                                              │   │
│  │  Detects:                                                    │   │
│  │  • range(len()) usage                                       │   │
│  │  • List append in loops                                     │   │
│  │  • Inefficient algorithms                                   │   │
│  │                                                              │   │
│  │  Performance: <1s                                           │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  5. Security Gate                                                   │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Vulnerability Scanning                                     │   │
│  │                                                              │   │
│  │  Detects:                                                    │   │
│  │  • Hardcoded secrets                                        │   │
│  │  • SQL injection patterns                                   │   │
│  │  • eval() usage                                             │   │
│  │  • Unsafe input handling                                    │   │
│  │                                                              │   │
│  │  Scoring:                                                    │   │
│  │  • CRITICAL: -0.30 (auto-fail)                             │   │
│  │  • HIGH:     -0.20                                         │   │
│  │                                                              │   │
│  │  Performance: ~2s                                           │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Multi-Model Consensus Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│           Consensus Validator Orchestrator (680 lines)               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Architectural Decision Input                                        │
│         │                                                             │
│         ▼                                                             │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Parallel Model Consultation                               │   │
│  │                                                              │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │   │
│  │  │  Gemini 2.0 │  │ Codestral   │  │  DeepSeek   │       │   │
│  │  │   Flash     │  │    22B      │  │    Lite     │       │   │
│  │  │             │  │             │  │             │       │   │
│  │  │  Fast       │  │  Code       │  │  Deep       │       │   │
│  │  │  Responses  │  │  Expert     │  │  Reasoning  │       │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │   │
│  │         │                │                │               │   │
│  │         ▼                ▼                ▼               │   │
│  │  ┌──────────────────────────────────────────────────┐    │   │
│  │  │          Response Collection                     │    │   │
│  │  │  • Recommendation                                │    │   │
│  │  │  • Confidence score (0.0-1.0)                   │    │   │
│  │  │  • Reasoning                                     │    │   │
│  │  │  • Alternatives                                  │    │   │
│  │  └──────────────────────────────────────────────────┘    │   │
│  └─────────────────────────┬────────────────────────────────┘   │
│                             ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Consensus Calculation                                     │   │
│  │                                                              │   │
│  │  Weighted Voting:                                           │   │
│  │  • Model confidence weights                                │   │
│  │  • Agreement scoring                                        │   │
│  │  • Conflict resolution                                      │   │
│  │                                                              │   │
│  │  Consensus Levels:                                          │   │
│  │  • STRONG:    >0.80 agreement                              │   │
│  │  • MODERATE:  0.60-0.80 agreement                          │   │
│  │  • WEAK:      0.40-0.60 agreement                          │   │
│  │  • CONFLICT:  <0.40 agreement                              │   │
│  └─────────────────────────┬────────────────────────────────┘   │
│                             ▼                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Output: ModelConsensusResult                              │   │
│  │  • recommendation: str                                      │   │
│  │  • confidence: float                                        │   │
│  │  • model_responses: List[Response]                         │   │
│  │  • reasoning: str                                           │   │
│  │  • alternatives: List[Alternative]                         │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Patterns

### End-to-End Flow: Task to Pattern Match

```
1. User submits coding task
        │
        ▼
2. Task characteristics extraction
        │
        ├─── Task description text
        ├─── Context metadata
        └─── Priority/urgency
        │
        ▼
3. Semantic analysis (Phase 2)
        │
        ├─── Check semantic cache (24μs if hit)
        │    └─── Cache miss? Call langextract (200ms)
        │
        ▼
4. Pattern database query
        │
        ├─── Qdrant vector search (70% weight)
        └─── Get candidate patterns (100 results)
        │
        ▼
5. Pattern similarity scoring (Phase 2)
        │
        ├─── For each candidate pattern:
        │    ├─── Concept overlap (30%)
        │    ├─── Theme similarity (20%)
        │    ├─── Domain alignment (20%)
        │    ├─── Structure match (15%)
        │    └─── Relationship match (15%)
        │    │
        │    └─── ~0.03ms per pattern
        │
        ▼
6. Hybrid scoring (Phase 2)
        │
        ├─── Combine vector score (70%)
        ├─── Combine pattern score (30%)
        └─── Normalize to 0.0-1.0
        │
        ▼
7. Rank and return top matches
        │
        └─── Sorted by hybrid score
             ├─── Top 10 patterns
             ├─── Confidence scores
             └─── Metadata
        │
        ▼
8. [Optional] Code quality validation (Phase 3)
        │
        ├─── Generate code from pattern
        ├─── Run through quality gates
        │    ├─── ONEX compliance
        │    ├─── Test coverage
        │    ├─── Code quality
        │    ├─── Performance
        │    └─── Security
        │
        └─── Return validated code + report
```

### Caching Strategy Flow

```
Request Flow with Multi-Level Caching:

┌─────────────────────────────────────────────────────────┐
│  Semantic Analysis Request                              │
│  • Content hash: SHA-256                                │
│  • TTL: 1 hour                                          │
└────────────────────┬────────────────────────────────────┘
                     ▼
            ┌────────────────┐
            │  L1: Memory    │
            │  Cache         │
            │  (Dict-based)  │
            └───────┬────────┘
                    │
              ┌─────┴─────┐
              │           │
         [HIT: 24μs]  [MISS]
              │           │
              │           ▼
              │    ┌──────────────┐
              │    │  L2: Redis   │
              │    │  Cache       │
              │    │  (Optional)  │
              │    └──────┬───────┘
              │           │
              │     ┌─────┴─────┐
              │     │           │
              │  [HIT: 5ms]  [MISS]
              │     │           │
              ▼     ▼           ▼
         ┌──────────────────────────┐
         │  Return                  │
         │  Cached                  │◀──────┐
         │  Result                  │       │
         └──────────────────────────┘       │
                                             │
                                    ┌────────┴────────┐
                                    │  Langextract    │
                                    │  HTTP Request   │
                                    │  (200ms)        │
                                    └────────┬────────┘
                                             │
                                    ┌────────┴────────┐
                                    │  Store in L2    │
                                    │  (if Redis)     │
                                    └────────┬────────┘
                                             │
                                    ┌────────┴────────┐
                                    │  Store in L1    │
                                    │  (Always)       │
                                    └─────────────────┘

Cache Hit Rate Progression:
• First hour:    ~30% (cold cache)
• After 1 day:   ~60% (warming)
• Steady state:  ~80% (mature)

Performance Impact:
• Cache hit:     ~200ms saved (95% faster)
• Memory cost:   ~50KB per entry
• Redis cost:    ~100KB per entry
```

---

## Integration Architecture

### External Service Integration

```
┌──────────────────────────────────────────────────────────────────────┐
│               Intelligence Service Integration                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Intelligence Service (FastAPI - Port 8053)                │   │
│  │                                                              │   │
│  │  Endpoints:                                                 │   │
│  │  • POST /pattern/match       → Hybrid scoring              │   │
│  │  • POST /quality/validate    → Quality gates               │   │
│  │  • GET  /metrics             → Prometheus metrics          │   │
│  │  • GET  /health              → Health check                │   │
│  └────────────────────────────────────────────────────────────┘   │
│           │                    │                    │                │
│           ▼                    ▼                    ▼                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  │ Langextract  │    │   Qdrant     │    │   Supabase   │         │
│  │   Service    │    │   Vector     │    │  PostgreSQL  │         │
│  │              │    │   Database   │    │              │         │
│  │ Port 8000    │    │  Port 6333   │    │ Port 5432    │         │
│  │              │    │              │    │              │         │
│  │ • Pattern    │    │ • Vector     │    │ • Patterns   │         │
│  │   extraction │    │   search     │    │ • Reports    │         │
│  │ • Semantic   │    │ • Similarity │    │ • Metadata   │         │
│  │   analysis   │    │   scoring    │    │              │         │
│  └──────────────┘    └──────────────┘    └──────────────┘         │
│           │                    │                    │                │
│           └────────────────────┴────────────────────┘                │
│                                │                                      │
│                                ▼                                      │
│           ┌────────────────────────────────────────┐                │
│           │  Redis Cache (Optional - Port 6379)    │                │
│           │  • Semantic analysis cache             │                │
│           │  • Pattern match cache                 │                │
│           └────────────────────────────────────────┘                │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘

Service Communication Patterns:

1. Synchronous HTTP (Phase 2)
   Intelligence ──HTTP──▶ Langextract
                ◀──JSON──

2. Async Vector Search
   Intelligence ──gRPC──▶ Qdrant
                ◀──Results──

3. Database Persistence
   Intelligence ──SQL──▶ Supabase
                ◀──ACK──

4. Cache Layer
   Intelligence ──Redis Protocol──▶ Redis
                ◀──Cached Data──

Error Handling:
• Circuit breaker for Langextract
• Retry logic for transient failures
• Graceful degradation (cache-only mode)
• Health check monitoring
```

### Monitoring Integration

```
┌──────────────────────────────────────────────────────────────────────┐
│                 Monitoring & Observability Stack                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Intelligence Service                                       │   │
│  │  • Prometheus metrics endpoint (/metrics)                  │   │
│  │  • Structured logging (JSON)                               │   │
│  │  • Correlation ID tracking                                 │   │
│  └───────────────────┬────────────────────────────────────────┘   │
│                      │                                              │
│           ┌──────────┴──────────┐                                  │
│           ▼                     ▼                                  │
│  ┌──────────────────┐  ┌──────────────────┐                      │
│  │   Prometheus     │  │  Logging         │                      │
│  │   (Port 9090)    │  │  Aggregation     │                      │
│  │                  │  │  (Logfire)       │                      │
│  │ • Metrics scrape │  │                  │                      │
│  │   (15s interval) │  │ • Log ingestion  │                      │
│  │ • Alert rules    │  │ • Search/filter  │                      │
│  │ • Time-series DB │  │ • Correlation    │                      │
│  └────────┬─────────┘  └──────────────────┘                      │
│           │                                                         │
│           ▼                                                         │
│  ┌──────────────────┐                                             │
│  │   Grafana        │                                             │
│  │   (Port 3000)    │                                             │
│  │                  │                                             │
│  │ • Dashboards     │                                             │
│  │ • Visualizations │                                             │
│  │ • Alerts         │                                             │
│  └────────┬─────────┘                                             │
│           │                                                         │
│           ▼                                                         │
│  ┌──────────────────┐                                             │
│  │  Alertmanager    │                                             │
│  │  (Port 9093)     │                                             │
│  │                  │                                             │
│  │ • Alert routing  │                                             │
│  │ • Deduplication  │                                             │
│  │ • Notifications  │                                             │
│  └────────┬─────────┘                                             │
│           │                                                         │
│           ▼                                                         │
│  ┌──────────────────────────────────────┐                         │
│  │  Notification Channels               │                         │
│  │  • Email                             │                         │
│  │  • Slack                             │                         │
│  │  • PagerDuty                         │                         │
│  └──────────────────────────────────────┘                         │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘

Metrics Collection Flow:
1. Intelligence service exposes /metrics endpoint
2. Prometheus scrapes every 15 seconds
3. Metrics stored in time-series database
4. Grafana visualizes in real-time
5. Alert rules evaluate on metrics
6. Alertmanager routes notifications
```

---

## Performance Architecture

### Performance Optimization Layers

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Performance Optimization                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Layer 1: Algorithm Optimization                                    │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • O(n+m) Jaccard similarity (set operations)              │   │
│  │  • Pre-computed embeddings (avoid re-encoding)             │   │
│  │  • Batch processing (100 patterns at once)                 │   │
│  │  • Early termination (skip low-quality matches)            │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Layer 2: Caching Strategy                                          │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • L1 Memory cache (24μs retrieval)                        │   │
│  │  • L2 Redis cache (5ms fallback)                           │   │
│  │  • LRU eviction (keep hot data)                            │   │
│  │  • TTL management (1 hour default)                         │   │
│  │  • Cache warming (proactive loading)                       │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Layer 3: I/O Optimization                                          │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • Connection pooling (HTTP clients)                       │   │
│  │  • Async I/O (non-blocking operations)                     │   │
│  │  • Batch database queries                                  │   │
│  │  • Vector index optimization (Qdrant HNSW)                 │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Layer 4: Parallel Execution                                        │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • Quality gates (parallel execution ~18s vs 45s)          │   │
│  │  • Pattern scoring (batch parallelization)                 │   │
│  │  • Multi-model consensus (parallel consultation)           │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Layer 5: Resource Management                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • Memory limits (cache max size: 1000 entries)            │   │
│  │  • CPU affinity (process pinning)                          │   │
│  │  • Thread pool sizing (optimal workers)                    │   │
│  │  • Garbage collection tuning                               │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘

Performance Monitoring:
• Real-time latency tracking (P50, P95, P99)
• Throughput metrics (requests/second)
• Resource utilization (CPU, memory, I/O)
• Cache hit rates (target: 80%)
• Error rates (target: <1%)
```

---

## Security Architecture

### Security Layers

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Security Architecture                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Input Validation Layer                                             │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • Pydantic model validation                               │   │
│  │  • Request schema enforcement                              │   │
│  │  • Type checking (mypy compatible)                         │   │
│  │  • Size limits (max request: 10MB)                         │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Authentication & Authorization                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • Service-to-service auth tokens                          │   │
│  │  • API key validation                                      │   │
│  │  • Role-based access control                              │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Network Security                                                   │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • TLS/SSL encryption (in-transit)                         │   │
│  │  • VPC isolation (service communication)                   │   │
│  │  • Rate limiting (100 req/minute)                          │   │
│  │  • DDoS protection                                         │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Data Security                                                      │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  • Encryption at rest (database)                           │   │
│  │  • Secret management (environment variables)               │   │
│  │  • No hardcoded credentials                                │   │
│  │  • Audit logging (all access)                              │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Code Security (Phase 3 Security Gate)                             │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Vulnerability Scanning:                                    │   │
│  │  • Hardcoded secrets detection                             │   │
│  │  • SQL injection patterns                                  │   │
│  │  • eval() usage                                            │   │
│  │  • Unsafe input handling                                   │   │
│  │  • Dependency vulnerabilities                              │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘

Security Monitoring:
• Failed authentication attempts
• Suspicious request patterns
• Vulnerability scan results
• Security gate failures
• Access audit trail
```

---

## Deployment Architecture

### Container Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                 Docker Container Architecture                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  archon-intelligence (Port 8053)                           │   │
│  │                                                              │   │
│  │  Base: python:3.12-slim                                    │   │
│  │  Dependencies: pyproject.toml                              │   │
│  │  Volumes:                                                   │   │
│  │  • /app/src (source code)                                  │   │
│  │  • /app/tests (test suite)                                 │   │
│  │  • /app/config (configuration)                             │   │
│  │                                                              │   │
│  │  Environment:                                               │   │
│  │  • LANGEXTRACT_URL=http://langextract:8000                │   │
│  │  • QDRANT_URL=http://qdrant:6333                          │   │
│  │  • REDIS_URL=redis://redis:6379                           │   │
│  │  • SUPABASE_URL=...                                        │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                       │
│  Linked Services:                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ langextract  │  │   qdrant     │  │    redis     │            │
│  │ Port 8000    │  │ Port 6333    │  │  Port 6379   │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                       │
│  Monitoring Stack:                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ prometheus   │  │   grafana    │  │ alertmanager │            │
│  │ Port 9090    │  │  Port 3000   │  │  Port 9093   │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘

Health Checks:
• Startup probe: /health (initial)
• Liveness probe: /health (every 30s)
• Readiness probe: /ready (every 10s)

Resource Limits:
• Memory: 2GB limit, 1GB request
• CPU: 2 cores limit, 1 core request
• Restart policy: on-failure
```

---

## Conclusion

This architecture guide provides a comprehensive understanding of how Phase 2 and Phase 3 components work together to provide intelligent pattern matching and quality validation for the Archon Pattern Learning Engine.

### Key Architectural Principles

1. **ONEX Compliance**: Strict adherence to node type patterns
2. **Separation of Concerns**: Clear boundaries between components
3. **Performance First**: Multi-level caching and optimization
4. **Resilience**: Circuit breakers, retries, graceful degradation
5. **Observability**: Comprehensive metrics and monitoring
6. **Security**: Multi-layer security controls and validation

### Architecture Highlights

- **4,355 lines** of Phase 2 code (hybrid scoring, caching, monitoring)
- **5,528 lines** of Phase 3 code (quality gates, validation, consensus)
- **100% ONEX compliant** node implementations
- **~200ms** performance improvement with caching (95% faster)
- **5 quality gates** with parallel execution (<30s total)
- **25+ Prometheus metrics** for real-time monitoring
- **3-model consensus** for architectural decisions

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-02
**Version**: 1.0.0
**Maintained By**: Archon Architecture Team
