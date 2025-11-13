"""Archon Source Package - Intelligence Provider for AI Coding Assistants.

This package contains the core implementation of Archon, an intelligence platform
for AI coding assistants via Model Context Protocol (MCP). Provides code quality
analysis, performance optimization, RAG intelligence, pattern learning, and ONEX
compliance validation.

Main Components:
    - server/: Business logic, services, and ML models
        - mcp/: MCP server implementation
        - intelligence/: Intelligence services (quality, performance, learning)
        - search/: RAG and vector search services
        - bridge/: Bridge service for metadata stamping
        - langextract/: Language extraction and ML features

    - tools/: MCP tool implementations
    - models/: Pydantic data models
    - config/: Configuration management
    - utils/: Shared utilities

Architecture:
    Archon follows a microservices architecture:

    MCP Server (port 8051)
        ↓
    Intelligence Service (port 8053)
        ↓
    Backend Services:
        - Qdrant (vector DB)
        - Memgraph (knowledge graph)
        - Supabase (PostgreSQL)
        - Valkey (distributed cache)

Key Features:
    1. Code Quality Assessment:
        - ONEX architectural compliance scoring
        - 6-dimension quality analysis
        - Pattern and anti-pattern detection

    2. Performance Optimization:
        - Baseline establishment
        - Optimization opportunity identification
        - Trend monitoring and predictions

    3. RAG Intelligence:
        - Multi-source research orchestration
        - Context-aware recommendations
        - Cross-project insights

    4. Pattern Learning:
        - Hybrid pattern matching
        - Semantic analysis
        - Usage analytics and feedback loops

    5. Document Freshness:
        - Freshness analysis and tracking
        - Stale document identification
        - Automated refresh workflows

MCP Integration:
    Archon exposes 168+ operations via a unified gateway:
    - 68 internal operations (intelligence services)
    - 100+ external operations (zen, context7, codanna, serena)

Usage:
    Import core components:
    >>> from python.src.server.intelligence import QualityAssessmentService
    >>> from python.src.server.search import SearchService
    >>> from python.src.tools import archon_menu

    MCP tool usage:
    >>> result = archon_menu(
    ...     operation="assess_code_quality",
    ...     params={"content": code, "source_path": "file.py", "language": "python"}
    ... )

Environment Setup:
    Required environment variables:
    - ARCHON_MCP_PORT: MCP server port (default: 8051)
    - INTELLIGENCE_SERVICE_PORT: Intelligence service port (default: 8053)
    - SUPABASE_URL, SUPABASE_SERVICE_KEY: Database connection
    - QDRANT_URL: Vector database URL
    - MEMGRAPH_URI: Knowledge graph connection
    - VALKEY_URL: Cache connection

Package Structure:
    python/src/
        __init__.py                         # This file - package initialization
        server/                             # Core business logic
        tools/                              # MCP tool implementations
        models/                             # Data models
        config/                             # Configuration
        utils/                              # Utilities

See Also:
    - CLAUDE.md: Complete project documentation
    - docs/mcp_proxy/: MCP integration guides
    - python/README.md: Python package documentation
"""
