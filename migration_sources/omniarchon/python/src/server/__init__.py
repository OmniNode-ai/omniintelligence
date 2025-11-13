"""Archon Server Package - Core Business Logic and Intelligence Services.

This package contains all business logic, services, and ML models for the Archon
intelligence platform. Implements microservices architecture with specialized
services for quality assessment, performance optimization, RAG intelligence,
pattern learning, and more.

Main Service Categories:
    1. Intelligence Services (port 8053):
        - Quality Assessment: ONEX compliance, code quality scoring
        - Performance Analytics: Baseline tracking, optimization identification
        - Document Freshness: Staleness detection, refresh workflows
        - Pattern Learning: Hybrid matching, semantic analysis
        - Pattern Traceability: Lineage tracking, usage analytics
        - Autonomous Learning: Success prediction, safety calculations
        - Quality Trends: Historical tracking, regression detection

    2. Search Services (port 8055):
        - RAG Search: Multi-source intelligence gathering
        - Vector Search: Semantic similarity with quality weighting
        - Enhanced Search: Hybrid search across RAG + Qdrant + Memgraph
        - Code Examples: Implementation pattern discovery

    3. Bridge Service (port 8054):
        - Metadata Stamping: BLAKE3 hashing, ONEX compliance
        - Kafka Event Publishing: Change stream integration
        - Intelligence Generation: OmniNode metadata

    4. Language Extraction (port 8156):
        - ML Feature Extraction: AST analysis, semantic features
        - Code Classification: Language detection, pattern recognition
        - Entity Extraction: Symbol and relationship identification

    5. MCP Server (port 8051):
        - Unified Gateway: 168+ operation routing
        - Protocol Implementation: SSE-based MCP protocol
        - External Gateway: Integration with zen, context7, codanna, serena

Service Architecture:
    ```
    MCP Server (8051)
        ↓
    Intelligence Service (8053)
        ↓
    Specialized Services:
        - Search (8055)
        - Bridge (8054)
        - LangExtract (8156)
        ↓
    Data Layer:
        - Qdrant (6333): Vector DB
        - Memgraph (7687): Knowledge Graph
        - Supabase: PostgreSQL
        - Valkey (6379): Distributed Cache
    ```

Package Structure:
    server/
        __init__.py                         # This file
        intelligence/                       # Intelligence services
            quality_assessment/             # Code quality analysis
            performance_analytics/          # Performance optimization
            document_freshness/             # Freshness tracking
            pattern_learning/               # Pattern matching & learning
            pattern_traceability/           # Lineage & analytics
            autonomous_learning/            # Predictive intelligence
            quality_trends/                 # Historical quality tracking
        search/                             # Search and RAG services
        bridge/                             # Bridge integration service
        langextract/                        # Language extraction service
        mcp/                                # MCP server implementation
        models/                             # Shared data models
        utils/                              # Service utilities

API Endpoints:
    Intelligence Service (http://localhost:8053):
        - POST /assess/code: Quality assessment
        - POST /performance/baseline: Performance baseline
        - POST /freshness/analyze: Document freshness analysis
        - POST /api/pattern-learning/pattern/match: Pattern matching
        - POST /api/pattern-traceability/lineage/track: Pattern tracking
        - POST /api/autonomous/predict/agent: Agent prediction
        - GET /api/quality-trends/project/{id}/trend: Quality trends
        ... (78 total endpoints)

    Search Service (http://localhost:8055):
        - POST /search/rag: RAG intelligence queries
        - POST /search/vector: Vector similarity search
        - POST /search/enhanced: Multi-source hybrid search
        - POST /search/code-examples: Code pattern search

Performance Targets:
    - Code Quality Assessment: <500ms per file
    - Vector Search: <100ms per query
    - RAG Query: <1200ms with orchestration
    - Pattern Matching: <50ms per pattern
    - Cache Hit Latency: <100ms

Service Health:
    All services expose health endpoints:
    >>> import requests
    >>> response = requests.get("http://localhost:8053/health")
    >>> assert response.json()["status"] == "healthy"

Usage:
    Import services:
    >>> from python.src.server.intelligence import (
    ...     QualityAssessmentService,
    ...     PerformanceAnalyticsService
    ... )
    >>> from python.src.server.search import SearchService

    Initialize service:
    >>> quality_service = QualityAssessmentService()
    >>> result = await quality_service.assess_code_quality(
    ...     content=code,
    ...     source_path="file.py",
    ...     language="python"
    ... )

Configuration:
    Services configured via environment variables:
    - INTELLIGENCE_SERVICE_PORT=8053
    - SEARCH_SERVICE_PORT=8055
    - BRIDGE_SERVICE_PORT=8054
    - LANGEXTRACT_SERVICE_PORT=8156
    - QDRANT_URL=http://qdrant:6333
    - MEMGRAPH_URI=bolt://memgraph:7687
    - VALKEY_URL=redis://archon-valkey:6379/0

See Also:
    - CLAUDE.md: Complete service documentation
    - docs/intelligence/: Intelligence service architecture
    - python/src/tools/: MCP tool implementations
"""
