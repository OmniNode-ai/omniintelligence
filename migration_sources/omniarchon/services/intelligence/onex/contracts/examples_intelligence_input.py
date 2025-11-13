#!/usr/bin/env python3
"""
Usage Examples for ModelIntelligenceInput and EnumIntelligenceOperationType.

This file demonstrates comprehensive usage patterns for the Intelligence
Adapter Effect Node input contracts across all operation categories.

Run this file to validate contract behavior:
    python examples_intelligence_input.py

ONEX v2.0 Compliance:
- Demonstrates all operation categories
- Shows validation behavior
- Provides security examples
- Illustrates hybrid content/path patterns
"""

from datetime import datetime, timezone
from uuid import uuid4

from .enum_intelligence_operation_type import EnumIntelligenceOperationType
from .model_intelligence_input import ModelIntelligenceInput


def example_code_quality_assessment():
    """
    Example: Code quality assessment with ONEX compliance checking.
    """
    print("\n=== Example 1: Code Quality Assessment ===")

    python_code = """
class NodeCalculatorCompute(NodeCompute):
    '''Compute node for arithmetic calculations.'''

    async def execute_compute(self, contract: ModelContractCompute):
        result = await self._calculate(contract.data)
        return ModelResult(success=True, data=result)

    async def _calculate(self, data: dict) -> float:
        return sum(data.get('values', []))
"""

    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
        correlation_id=uuid4(),
        source_path="src/onex/compute/node_calculator_compute.py",
        content=python_code,
        language="python",
        options={
            "include_recommendations": True,
            "onex_compliance_check": True,
            "max_recommendations": 10,
        },
        metadata={
            "project_id": "omniarchon",
            "namespace": "production",
            "tags": ["onex", "compute-node"],
        },
    )

    print(f"Operation: {input_data.operation_type}")
    print(f"Correlation ID: {input_data.correlation_id}")
    print(f"Source Path: {input_data.source_path}")
    print(f"Language: {input_data.language}")
    print(f"Category: {input_data.get_operation_category()}")
    print(f"Read-only: {input_data.is_read_only_operation()}")
    print(f"Content Preview: {input_data.get_content_or_placeholder()}")


def example_performance_baseline():
    """
    Example: Establish performance baseline for operation tracking.
    """
    print("\n=== Example 2: Performance Baseline ===")

    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE,
        correlation_id=uuid4(),
        options={
            "operation_name": "api_endpoint_latency",
            "target_percentile": 95,
            "measurement_window_hours": 24,
            "baseline_samples": 1000,
        },
        metadata={
            "service": "archon-intelligence",
            "endpoint": "/assess/code",
        },
    )

    print(f"Operation: {input_data.operation_type}")
    print(f"Correlation ID: {input_data.correlation_id}")
    print(f"Options: {input_data.options}")
    print(f"Category: {input_data.get_operation_category()}")
    print(f"Read-only: {input_data.is_read_only_operation()}")


def example_document_freshness():
    """
    Example: Analyze document freshness for staleness detection.
    """
    print("\n=== Example 3: Document Freshness Analysis ===")

    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.ANALYZE_DOCUMENT_FRESHNESS,
        correlation_id=uuid4(),
        source_path="docs/architecture/ONEX_ARCHITECTURE.md",
        options={
            "staleness_threshold_days": 30,
            "include_refresh_recommendations": True,
            "check_external_references": True,
        },
        metadata={
            "project_id": "omniarchon",
            "document_type": "architecture",
        },
    )

    print(f"Operation: {input_data.operation_type}")
    print(f"Source Path: {input_data.source_path}")
    print(f"Category: {input_data.get_operation_category()}")
    print(f"Read-only: {input_data.is_read_only_operation()}")


def example_vector_search():
    """
    Example: Quality-weighted vector search for ONEX-compliant code.
    """
    print("\n=== Example 4: Quality-Weighted Vector Search ===")

    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.QUALITY_WEIGHTED_SEARCH,
        correlation_id=uuid4(),
        content="ONEX effect node patterns for database operations",
        options={
            "quality_weight": 0.3,
            "min_quality_score": 0.7,
            "limit": 10,
            "filters": {"language": "python", "node_type": "effect"},
        },
    )

    print(f"Operation: {input_data.operation_type}")
    print(f"Query: {input_data.content}")
    print(f"Category: {input_data.get_operation_category()}")
    print(f"Options: {input_data.options}")


def example_pattern_matching():
    """
    Example: Pattern matching for code analysis.
    """
    print("\n=== Example 5: Pattern Matching ===")

    rust_code = """
impl NodeEffect for NodeDatabaseWriterEffect {
    async fn execute_effect(&self, contract: ModelContractEffect) -> Result<ModelResult> {
        let result = self.write_to_database(contract.data).await?;
        Ok(ModelResult {
            success: true,
            data: result,
        })
    }
}
"""

    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.PATTERN_MATCH,
        correlation_id=uuid4(),
        content=rust_code,
        language="rust",
        options={
            "pattern_confidence_threshold": 0.8,
            "include_similar_patterns": True,
            "max_patterns": 5,
        },
    )

    print(f"Operation: {input_data.operation_type}")
    print(f"Language: {input_data.language}")
    print(f"Category: {input_data.get_operation_category()}")
    print(f"Content Preview: {input_data.get_content_or_placeholder()}")


def example_autonomous_prediction():
    """
    Example: Predict optimal agent for task execution.
    """
    print("\n=== Example 6: Autonomous Agent Prediction ===")

    task_description = """
Refactor the database adapter to use connection pooling and implement
retry logic with exponential backoff. Ensure ONEX compliance and add
comprehensive error handling.
"""

    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.PREDICT_AGENT,
        correlation_id=uuid4(),
        content=task_description,
        options={
            "prediction_confidence_threshold": 0.7,
            "include_alternatives": True,
            "max_alternatives": 3,
        },
        metadata={
            "task_type": "refactoring",
            "complexity": "medium",
        },
    )

    print(f"Operation: {input_data.operation_type}")
    print(f"Task: {input_data.content[:100]}...")
    print(f"Category: {input_data.get_operation_category()}")


def example_optimization_opportunities():
    """
    Example: Identify performance optimization opportunities.
    """
    print("\n=== Example 7: Optimization Opportunities ===")

    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.IDENTIFY_OPTIMIZATION_OPPORTUNITIES,
        correlation_id=uuid4(),
        options={
            "operation_name": "qdrant_vector_search",
            "time_window_hours": 168,  # Last week
            "min_roi_threshold": 0.2,  # 20% improvement minimum
        },
    )

    print(f"Operation: {input_data.operation_type}")
    print(f"Options: {input_data.options}")
    print(f"Category: {input_data.get_operation_category()}")


def example_validation_errors():
    """
    Example: Demonstrating validation errors and requirements.
    """
    print("\n=== Example 8: Validation Behavior ===")

    # Example 8a: Missing required content for quality operation
    print("\n8a. Missing content for quality operation (should fail):")
    try:
        ModelIntelligenceInput(
            operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
            correlation_id=uuid4(),
            # Missing: content and source_path
            language="python",
        )
        print("❌ Validation should have failed!")
    except ValueError as e:
        print(f"✅ Validation failed as expected: {e}")

    # Example 8b: Missing language for quality operation with content
    print("\n8b. Missing language for quality operation (should fail):")
    try:
        ModelIntelligenceInput(
            operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
            correlation_id=uuid4(),
            content="def hello(): pass",
            # Missing: language
        )
        print("❌ Validation should have failed!")
    except ValueError as e:
        print(f"✅ Validation failed as expected: {e}")

    # Example 8c: Path traversal attack (should fail)
    print("\n8c. Path traversal attack prevention (should fail):")
    try:
        ModelIntelligenceInput(
            operation_type=EnumIntelligenceOperationType.ANALYZE_DOCUMENT_FRESHNESS,
            correlation_id=uuid4(),
            source_path="../../../etc/passwd",  # Path traversal attempt
        )
        print("❌ Security validation should have failed!")
    except ValueError as e:
        print(f"✅ Security validation passed: {e}")

    # Example 8d: Invalid operation type (should fail)
    print("\n8d. Invalid operation type (should fail):")
    try:
        ModelIntelligenceInput(
            operation_type="invalid_operation",
            correlation_id=uuid4(),
        )
        print("❌ Validation should have failed!")
    except ValueError as e:
        print(f"✅ Validation failed as expected: {str(e)[:100]}...")


def example_enum_utilities():
    """
    Example: Using EnumIntelligenceOperationType utility methods.
    """
    print("\n=== Example 9: Enum Utility Methods ===")

    op = EnumIntelligenceOperationType.ASSESS_CODE_QUALITY

    print(f"\nOperation: {op.value}")
    print(f"Is Quality Operation: {op.is_quality_operation()}")
    print(f"Is Performance Operation: {op.is_performance_operation()}")
    print(f"Is Pattern Operation: {op.is_pattern_operation()}")
    print(f"Requires Content: {op.requires_content()}")
    print(f"Requires Source Path: {op.requires_source_path()}")
    print(f"Is Read-only: {op.is_read_only()}")

    # Demonstrate multiple operation types
    operations = [
        EnumIntelligenceOperationType.ESTABLISH_PERFORMANCE_BASELINE,
        EnumIntelligenceOperationType.QUALITY_WEIGHTED_SEARCH,
        EnumIntelligenceOperationType.BATCH_INDEX_DOCUMENTS,
    ]

    print("\nOperation Categories:")
    for op in operations:
        categories = []
        if op.is_quality_operation():
            categories.append("quality")
        if op.is_performance_operation():
            categories.append("performance")
        if op.is_vector_operation():
            categories.append("vector")
        if op.is_read_only():
            categories.append("read-only")
        else:
            categories.append("write")

        print(f"  {op.value}: {', '.join(categories)}")


def example_hybrid_content_path():
    """
    Example: Hybrid operation with both content and source_path.
    """
    print("\n=== Example 10: Hybrid Content + Path ===")

    # Provide both for maximum context
    input_data = ModelIntelligenceInput(
        operation_type=EnumIntelligenceOperationType.CHECK_ARCHITECTURAL_COMPLIANCE,
        correlation_id=uuid4(),
        source_path="src/onex/effects/node_database_adapter_effect.py",
        content="""
class NodeDatabaseAdapterEffect(NodeEffect):
    async def execute_effect(self, contract: ModelContractEffect):
        # Implementation
        pass
""",
        language="python",
        options={
            "strict_compliance": True,
            "include_suggestions": True,
        },
    )

    print(f"Operation: {input_data.operation_type}")
    print(f"Has Content: {input_data.content is not None}")
    print(f"Has Source Path: {input_data.source_path is not None}")
    print(f"Content Preview: {input_data.get_content_or_placeholder()}")


def main():
    """
    Run all examples to demonstrate usage patterns.
    """
    print("=" * 80)
    print("ModelIntelligenceInput Usage Examples")
    print("ONEX v2.0 Compliance Demonstration")
    print("=" * 80)

    example_code_quality_assessment()
    example_performance_baseline()
    example_document_freshness()
    example_vector_search()
    example_pattern_matching()
    example_autonomous_prediction()
    example_optimization_opportunities()
    example_validation_errors()
    example_enum_utilities()
    example_hybrid_content_path()

    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80)


if __name__ == "__main__":
    main()
