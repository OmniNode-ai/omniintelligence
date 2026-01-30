"""Node-specific tests for pattern_promotion_effect.

This package contains unit and integration tests for the pattern promotion
effect node. Tests are organized by functionality:

- test_promotion.py: Comprehensive unit tests for promotion gates and workflow
    - Gate 1 tests: Injection count (minimum 5)
    - Gate 2 tests: Success rate (minimum 60%)
    - Gate 3 tests: Failure streak (maximum 3)
    - Handler tests with mocked repositories
    - Event payload verification
    - Dry run mode tests

Test Fixtures:
    - mock_repository: Mock database operations (MockPatternRepository)
    - mock_producer: Mock Kafka publisher (MockKafkaPublisher)
    - sample_pattern_id: Fixed pattern ID for deterministic tests
    - sample_correlation_id: Fixed correlation ID for tracing tests

Reference:
    - OMN-1680: Auto-promote logic for patterns
    - OMN-1678: Rolling window metrics (dependency)
"""

__all__: list[str] = []
