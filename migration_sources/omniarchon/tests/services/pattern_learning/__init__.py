"""
Pattern Learning Test Suite
AI-Generated with agent-testing methodology
Coverage Target: 95%+

Test categories:
- Unit tests: PostgreSQL storage, Qdrant indexing
- Integration tests: End-to-end pattern flow
- Performance tests: <100ms search, indexing throughput
- Edge cases: 20+ malformed inputs, connection failures

Run all tests:
    pytest tests/services/pattern_learning/

Run specific category:
    pytest tests/services/pattern_learning/unit/
    pytest tests/services/pattern_learning/integration/
    pytest tests/services/pattern_learning/performance/
    pytest tests/services/pattern_learning/edge_cases/

Run with coverage:
    pytest tests/services/pattern_learning/ --cov --cov-report=html

Performance benchmarks:
    pytest tests/services/pattern_learning/performance/ -m performance
"""

__version__ = "1.0.0"
__author__ = "AI Agent (agent-testing)"
__coverage_target__ = "95%"
