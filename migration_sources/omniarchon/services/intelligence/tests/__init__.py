"""
Intelligence Service Test Suite

This package contains all tests for the Intelligence Service:
- integration/: End-to-end integration tests for handlers and services
- unit/: Unit tests for individual components
- performance/: Performance benchmarks and tests
- pattern_learning/: Pattern learning system tests
- fixtures/: Shared test fixtures and data

Test Organization:
- All tests follow pytest conventions
- Async tests use @pytest.mark.asyncio
- Integration tests use @pytest.mark.integration
- Performance tests use @pytest.mark.performance

Running Tests:
    # All tests
    poetry run pytest tests/

    # Integration tests only
    poetry run pytest tests/integration/ -m integration

    # Specific handler tests
    poetry run pytest tests/integration/ -m analysis_handler

    # Performance benchmarks
    poetry run pytest tests/performance/ -m performance
"""
