"""
ModelIntelligenceOutput Usage Examples.

Demonstrates common usage patterns for the Intelligence Adapter Effect Node
output model across different intelligence operations.

This file serves as both documentation and runnable examples for developers
implementing intelligence adapters or consuming intelligence service APIs.
"""

from uuid import UUID, uuid4

from model_intelligence_output import (
    ModelIntelligenceMetrics,
    ModelIntelligenceOutput,
    ModelPatternDetection,
)


def example_quality_assessment_success() -> ModelIntelligenceOutput:
    """
    Example: Successful code quality assessment with ONEX compliance.

    Typical response from assess_code_quality operation when analyzing
    Python code for quality metrics, complexity, and ONEX compliance.
    """
    return ModelIntelligenceOutput(
        success=True,
        operation_type="assess_code_quality",
        correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        processing_time_ms=1234,
        quality_score=0.87,
        onex_compliance=0.92,
        complexity_score=0.65,
        issues=[
            "Missing docstring in function 'process_data'",
            "Function 'calculate' exceeds complexity threshold (15 > 10)",
            "No type hints for function parameters in 'transform'",
        ],
        recommendations=[
            "Add comprehensive docstrings to all public functions",
            "Consider extracting complex logic into smaller functions",
            "Add type hints to improve IDE support and maintainability",
            "Use ONEX patterns for better architectural compliance",
        ],
        patterns=[
            ModelPatternDetection(
                pattern_type="architectural",
                pattern_name="ONEX_EFFECT_NODE",
                confidence=0.95,
                description="Proper Effect node implementation with execute_effect method",
                location="src/nodes/effect/node_api_effect.py:42",
                severity="info",
            ),
            ModelPatternDetection(
                pattern_type="quality",
                pattern_name="ANTI_PATTERN_GOD_CLASS",
                confidence=0.78,
                description="Class has too many responsibilities (12 methods)",
                location="src/service/orchestrator.py:15",
                severity="warning",
                recommendation="Consider splitting into smaller, focused classes",
            ),
        ],
        result_data={
            "lines_of_code": 250,
            "functions_analyzed": 18,
            "classes_analyzed": 3,
            "imports_count": 12,
            "test_coverage": 0.78,
        },
        metrics=ModelIntelligenceMetrics(
            rag_service_ms=300,
            vector_service_ms=250,
            knowledge_service_ms=450,
            cache_hit=False,
            cache_key="quality:assess:abc123",
            services_invoked=["intelligence", "search", "qdrant"],
            total_api_calls=3,
        ),
        metadata={
            "language": "python",
            "file_path": "src/api/endpoints.py",
            "onex_version": "1.0.0",
            "analyzer_version": "2.1.0",
        },
    )


def example_rag_query_cached() -> ModelIntelligenceOutput:
    """
    Example: RAG query served from cache.

    Shows response structure when intelligence gathering hits distributed
    cache (Valkey) and returns cached results without invoking backend services.
    """
    return ModelIntelligenceOutput(
        success=True,
        operation_type="perform_rag_query",
        correlation_id=UUID("550e8400-e29b-41d4-a716-446655440002"),
        processing_time_ms=45,  # Fast response from cache
        recommendations=[
            "Consider using vector search for better semantic matching",
            "Related patterns found in 3 other projects",
            "See similar implementations in omninode_bridge repository",
        ],
        result_data={
            "query": "ONEX Effect node implementation patterns",
            "total_results": 42,
            "top_confidence": 0.94,
            "sources": ["cache"],  # Served from cache, no backend calls
            "results": [
                {
                    "title": "ONEX Effect Node Guide",
                    "confidence": 0.94,
                    "source": "docs/onex/ONEX_GUIDE.md",
                },
                {
                    "title": "Effect Node Implementation Example",
                    "confidence": 0.89,
                    "source": "docs/onex/examples/nodes/effect/",
                },
            ],
        },
        metrics=ModelIntelligenceMetrics(
            cache_hit=True,  # Served from cache
            cache_key="research:rag:onex_effect_patterns",
            services_invoked=["cache"],  # Only cache accessed
            total_api_calls=1,
        ),
        metadata={
            "cache_ttl_seconds": 300,
            "warm_cache": True,
            "cache_age_seconds": 45,
        },
    )


def example_optimization_opportunities() -> ModelIntelligenceOutput:
    """
    Example: Performance optimization opportunities identified.

    Response from identify_optimization_opportunities operation showing
    ROI-ranked performance improvement suggestions.
    """
    return ModelIntelligenceOutput(
        success=True,
        operation_type="identify_optimization_opportunities",
        correlation_id=uuid4(),
        processing_time_ms=2100,
        recommendations=[
            "Add database index on 'user_id' column (50% query time reduction)",
            "Implement connection pooling (30% latency reduction)",
            "Cache frequently accessed user profiles (40% cache hit rate expected)",
            "Optimize N+1 query pattern in user_orders endpoint",
        ],
        result_data={
            "opportunities": [
                {
                    "type": "database_index",
                    "description": "Missing index on frequently queried column",
                    "impact": "high",
                    "effort": "low",
                    "roi_score": 0.95,
                    "estimated_improvement": "50% query time reduction",
                },
                {
                    "type": "caching",
                    "description": "User profile data accessed frequently",
                    "impact": "medium",
                    "effort": "medium",
                    "roi_score": 0.78,
                    "estimated_improvement": "40% cache hit rate",
                },
            ],
            "baseline_metrics": {
                "avg_response_time_ms": 450,
                "p95_response_time_ms": 1200,
                "p99_response_time_ms": 2500,
            },
        },
        metrics=ModelIntelligenceMetrics(
            rag_service_ms=800,
            vector_service_ms=600,
            knowledge_service_ms=700,
            cache_hit=False,
            services_invoked=["intelligence", "search", "qdrant", "memgraph"],
            total_api_calls=4,
        ),
    )


def example_service_timeout_error() -> ModelIntelligenceOutput:
    """
    Example: Service timeout with retry capability.

    Shows error response when intelligence service times out but operation
    can be safely retried.
    """
    return ModelIntelligenceOutput.create_error(
        operation_type="assess_code_quality",
        correlation_id=UUID("550e8400-e29b-41d4-a716-446655440001"),
        processing_time_ms=10150,  # Exceeded 10s timeout
        error_code="INTELLIGENCE_SERVICE_TIMEOUT",
        error_message="Intelligence service did not respond within 10s timeout",
        retry_allowed=True,
        metadata={
            "service": "intelligence",
            "timeout_ms": 10000,
            "attempt": 1,
            "max_retries": 3,
        },
    )


def example_invalid_input_error() -> ModelIntelligenceOutput:
    """
    Example: Invalid input that cannot be retried.

    Shows error response when input is malformed or invalid, making
    retry pointless without correcting the input.
    """
    return ModelIntelligenceOutput.create_error(
        operation_type="assess_code_quality",
        correlation_id=uuid4(),
        processing_time_ms=12,
        error_code="INVALID_INPUT_SYNTAX",
        error_message="Code content contains invalid syntax: unexpected EOF while parsing",
        retry_allowed=False,  # Cannot retry without fixing input
        metadata={
            "validation_errors": [
                "Line 42: SyntaxError: unexpected EOF while parsing",
                "Unable to parse Python AST",
            ],
            "language": "python",
        },
    )


def example_from_api_response() -> ModelIntelligenceOutput:
    """
    Example: Creating output from raw API response.

    Demonstrates parsing Intelligence Service API responses into
    strongly-typed output models.
    """
    # Simulate raw API response from intelligence service
    api_response = {
        "quality_score": 0.87,
        "onex_compliance": 0.92,
        "complexity_score": 0.65,
        "issues": ["Missing docstrings"],
        "recommendations": ["Add type hints"],
        "patterns": [
            {
                "pattern_type": "architectural",
                "pattern_name": "ONEX_EFFECT_NODE",
                "confidence": 0.95,
                "description": "Proper Effect node detected",
                "severity": "info",
            }
        ],
        "result_data": {"lines_of_code": 250},
        "metrics": {
            "rag_service_ms": 300,
            "cache_hit": False,
            "services_invoked": ["intelligence"],
            "total_api_calls": 1,
        },
    }

    return ModelIntelligenceOutput.from_api_response(
        api_response=api_response,
        operation_type="assess_code_quality",
        correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        processing_time_ms=1234,
    )


def example_serialization() -> dict:
    """
    Example: Serializing output to dictionary.

    Shows how to convert strongly-typed output models to JSON-serializable
    dictionaries for API responses, event payloads, or logging.
    """
    output = ModelIntelligenceOutput(
        success=True,
        operation_type="assess_code_quality",
        correlation_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        processing_time_ms=1234,
        quality_score=0.87,
    )

    # Convert to dictionary (UUIDs → strings, datetime → ISO 8601)
    result_dict = output.to_dict()

    # Can now be JSON serialized
    import json

    json_str = json.dumps(result_dict, indent=2)
    print(json_str)

    return result_dict


def main():
    """Run all examples and print results."""
    print("=" * 80)
    print("ModelIntelligenceOutput Usage Examples")
    print("=" * 80)

    print("\n1. Quality Assessment Success")
    print("-" * 80)
    success = example_quality_assessment_success()
    print(f"Success: {success.success}")
    print(f"Quality Score: {success.quality_score}")
    print(f"ONEX Compliance: {success.onex_compliance}")
    print(f"Issues: {len(success.issues)}")
    print(f"Patterns: {len(success.patterns) if success.patterns else 0}")

    print("\n2. RAG Query (Cached)")
    print("-" * 80)
    cached = example_rag_query_cached()
    print(f"Processing Time: {cached.processing_time_ms}ms")
    print(f"Cache Hit: {cached.metrics.cache_hit}")
    print(f"Results: {cached.result_data['total_results']}")

    print("\n3. Optimization Opportunities")
    print("-" * 80)
    optimize = example_optimization_opportunities()
    print(f"Recommendations: {len(optimize.recommendations)}")
    print(f"Services Invoked: {optimize.metrics.services_invoked}")

    print("\n4. Service Timeout Error")
    print("-" * 80)
    timeout = example_service_timeout_error()
    print(f"Success: {timeout.success}")
    print(f"Error Code: {timeout.error_code}")
    print(f"Retry Allowed: {timeout.retry_allowed}")

    print("\n5. Invalid Input Error")
    print("-" * 80)
    invalid = example_invalid_input_error()
    print(f"Success: {invalid.success}")
    print(f"Error Code: {invalid.error_code}")
    print(f"Retry Allowed: {invalid.retry_allowed}")

    print("\n6. From API Response")
    print("-" * 80)
    from_api = example_from_api_response()
    print(f"Parsed Quality Score: {from_api.quality_score}")
    print(f"Parsed ONEX Compliance: {from_api.onex_compliance}")

    print("\n7. Serialization to Dict")
    print("-" * 80)
    serialized = example_serialization()

    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
