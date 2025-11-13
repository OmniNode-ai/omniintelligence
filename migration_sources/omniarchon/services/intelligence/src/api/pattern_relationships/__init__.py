"""
Pattern Relationships API

Provides REST endpoints for pattern relationship queries and graph operations.
Part of Pattern Relationship Detection and Graph Engine.

Features:
- Get pattern relationships grouped by type
- Build pattern dependency graph with configurable depth
- Find dependency chains between patterns
- Detect circular dependencies
- Create relationships manually
- Auto-detect relationships from source code

Endpoints:
- GET /api/patterns/{pattern_id}/relationships - Get all relationships
- GET /api/patterns/graph - Build dependency graph
- GET /api/patterns/dependency-chain - Find dependency chain
- GET /api/patterns/{pattern_id}/circular-dependencies - Detect cycles
- POST /api/patterns/relationships - Create relationship
- POST /api/patterns/{pattern_id}/detect-relationships - Auto-detect relationships
"""

from src.api.pattern_relationships.routes import router

__all__ = ["router"]
