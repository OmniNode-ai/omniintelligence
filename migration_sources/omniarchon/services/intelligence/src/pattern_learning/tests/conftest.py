"""
Pytest configuration and fixture discovery for Pattern Learning tests.

This file ensures pytest can discover and use all fixtures from fixtures.py.
Track: Track 3-1.5 - Comprehensive Test Suite Generation
"""

# Import all fixtures to make them available to pytest
from pattern_learning.tests.fixtures import (  # Database fixtures; Effect node fixtures; Sample data fixtures
    analytics_node,
    asyncpg_pool,
    db_manager,
    db_url,
    initialized_db,
    inserted_pattern,
    inserted_patterns,
    pattern_with_usage,
    query_node,
    sample_pattern_data,
    sample_relationship_data,
    sample_usage_data,
    storage_node,
    update_node,
)

# Make fixtures available
__all__ = [
    "db_url",
    "asyncpg_pool",
    "db_manager",
    "initialized_db",
    "storage_node",
    "query_node",
    "update_node",
    "analytics_node",
    "sample_pattern_data",
    "inserted_pattern",
    "inserted_patterns",
    "pattern_with_usage",
    "sample_usage_data",
    "sample_relationship_data",
]
