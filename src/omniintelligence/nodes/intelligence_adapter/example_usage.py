"""
Example Usage of NodeIntelligenceAdapterEffect

Demonstrates how to use the Intelligence Adapter Effect Node for code
quality assessment, performance analysis, and pattern detection.

This example shows the basic workflow:
1. Initialize the node with a container
2. Call initialize() to connect to the Intelligence Service
3. Create ModelIntelligenceInput with operation details
4. Call analyze_code() to execute the operation
5. Process the ModelIntelligenceOutput results
6. Get statistics for monitoring

Usage:
    python example_usage.py

Requirements:
    - Intelligence Service running at http://localhost:8053
    - omnibase_core installed
    - All dependencies from pyproject.toml

Created: 2025-10-21
"""

import asyncio
import logging
from uuid import uuid4

from omniintelligence.nodes import NodeIntelligenceAdapterEffect
from omnibase_core.models.container.model_onex_container import ModelONEXContainer

# Import models from the canonical location
from omniintelligence._legacy.models import ModelIntelligenceInput
from omniintelligence._legacy.models.model_intelligence_output import ModelIntelligenceOutput


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def example_code_quality_assessment() -> ModelIntelligenceOutput:
    """
    Example: Code quality assessment with ONEX compliance.

    Demonstrates basic usage of the Intelligence Adapter for analyzing
    code quality, detecting issues, and getting recommendations.
    """
    logger.info("=" * 80)
    logger.info("Example 1: Code Quality Assessment")
    logger.info("=" * 80)

    # Sample code to analyze
    code_content = '''
async def calculate_user_score(user_id: int, db: Session) -> float:
    """Calculate user score based on activity metrics."""
    user = await db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")

    activity_score = user.activity_count / 100.0
    engagement_score = user.engagement_rate

    return min((activity_score + engagement_score) / 2.0, 1.0)
'''

    # Initialize container and adapter
    container = ModelONEXContainer()
    adapter = NodeIntelligenceAdapterEffect(container)

    try:
        # Initialize the adapter (connects to Intelligence Service)
        logger.info("Initializing Intelligence Adapter...")
        await adapter.initialize()
        logger.info("✓ Adapter initialized successfully")

        # Create intelligence input for code quality assessment
        input_data = ModelIntelligenceInput(
            operation_type="assess_code_quality",
            correlation_id=uuid4(),
            content=code_content,
            source_path="src/services/user_service.py",
            language="python",
            options={"include_recommendations": True, "min_quality_threshold": 0.7},
        )

        logger.info(f"\nAnalyzing code: {input_data.source_path}")

        # Execute analysis
        result = await adapter.analyze_code(input_data)

        # Display results
        logger.info("\n" + "=" * 60)
        logger.info("Analysis Results")
        logger.info("=" * 60)
        logger.info(f"Operation: {result.operation_type}")
        logger.info(f"Success: {result.success}")
        logger.info(f"Processing Time: {result.processing_time_ms}ms")

        if result.quality_score is not None:
            logger.info(f"\nQuality Score: {result.quality_score:.2f}")
        if result.onex_compliance is not None:
            logger.info(f"ONEX Compliance: {result.onex_compliance:.2f}")
        if result.complexity_score is not None:
            logger.info(f"Complexity Score: {result.complexity_score:.2f}")

        if result.issues:
            logger.info(f"\nIssues Detected ({len(result.issues)}):")
            for issue in result.issues:
                logger.info(f"  - {issue}")

        if result.recommendations:
            logger.info(f"\nRecommendations ({len(result.recommendations)}):")
            for rec in result.recommendations:
                logger.info(f"  - {rec}")

        # Get statistics
        stats = adapter.get_analysis_stats()
        logger.info("\n" + "=" * 60)
        logger.info("Adapter Statistics")
        logger.info("=" * 60)
        logger.info(f"Total Analyses: {stats['total_analyses']}")
        logger.info(f"Successful: {stats['successful_analyses']}")
        logger.info(f"Failed: {stats['failed_analyses']}")
        logger.info(f"Success Rate: {stats['success_rate']:.2%}")
        logger.info(f"Avg Quality Score: {stats['avg_quality_score']:.2f}")
        logger.info(f"Circuit Breaker State: {stats['circuit_breaker_state']}")

        return result

    except (ConnectionError, TimeoutError, OSError) as e:
        # Network-related errors during initialization or analysis
        logger.error(f"Network error during code analysis: {e}", exc_info=True)
        raise
    except ValueError as e:
        # Configuration or validation errors
        logger.error(f"Validation error during code analysis: {e}", exc_info=True)
        raise
    except Exception as e:
        # Intentionally broad: example script catch-all to ensure errors are logged
        # before re-raising. In production code, use more specific exception handlers.
        logger.error(f"Unexpected error during code analysis: {e}", exc_info=True)
        raise

    finally:
        # Cleanup
        await adapter._cleanup_node_resources()
        logger.info("\n✓ Cleanup complete")


async def example_performance_analysis() -> ModelIntelligenceOutput:
    """
    Example: Performance analysis and optimization opportunities.

    Demonstrates how to use the adapter for identifying performance
    bottlenecks and getting optimization recommendations.
    """
    logger.info("\n" + "=" * 80)
    logger.info("Example 2: Performance Analysis")
    logger.info("=" * 80)

    code_content = '''
async def fetch_user_dashboard_data(user_id: int, db: Session) -> dict[str, Any]:
    """Fetch all data for user dashboard."""
    user = await db.query(User).filter(User.id == user_id).first()
    posts = await db.query(Post).filter(Post.author_id == user_id).all()
    comments = await db.query(Comment).filter(Comment.author_id == user_id).all()
    notifications = await db.query(Notification).filter(Notification.user_id == user_id).all()

    return {
        "user": user,
        "posts": posts,
        "comments": comments,
        "notifications": notifications
    }
'''

    container = ModelONEXContainer()
    adapter = NodeIntelligenceAdapterEffect(container)

    try:
        await adapter.initialize()

        input_data = ModelIntelligenceInput(
            operation_type="identify_optimization_opportunities",
            correlation_id=uuid4(),
            content=code_content,
            language="python",
            options={
                "operation_name": "user_dashboard_fetch",
                "target_percentile": 95,
                "include_opportunities": True,
                "context": {
                    "execution_type": "async",
                    "io_type": "database",
                    "expected_frequency": "high",
                    "current_latency_p95": 500,
                },
            },
        )

        # Access options safely (we know it's set above)
        operation_name = (
            input_data.options["operation_name"] if input_data.options else "unknown"
        )
        logger.info(f"Analyzing performance for: {operation_name}")

        result = await adapter.analyze_code(input_data)

        logger.info("\n" + "=" * 60)
        logger.info("Performance Analysis Results")
        logger.info("=" * 60)
        logger.info(f"Success: {result.success}")
        logger.info(f"Processing Time: {result.processing_time_ms}ms")

        if result.recommendations:
            logger.info(
                f"\nOptimization Opportunities ({len(result.recommendations)}):"
            )
            for rec in result.recommendations:
                logger.info(f"  - {rec}")

        if result.result_data:
            logger.info("\nAdditional Data:")
            for key, value in result.result_data.items():
                logger.info(f"  {key}: {value}")

        return result

    except (ConnectionError, TimeoutError, OSError) as e:
        # Network-related errors during initialization or analysis
        logger.error(f"Network error during performance analysis: {e}", exc_info=True)
        raise
    except ValueError as e:
        # Configuration or validation errors
        logger.error(f"Validation error during performance analysis: {e}", exc_info=True)
        raise
    except Exception as e:
        # Intentionally broad: example script catch-all to ensure errors are logged
        # before re-raising. In production code, use more specific exception handlers.
        logger.error(f"Unexpected error during performance analysis: {e}", exc_info=True)
        raise

    finally:
        await adapter._cleanup_node_resources()


async def main() -> None:
    """Run all examples."""
    logger.info("Intelligence Adapter Effect Node - Usage Examples")
    logger.info("=" * 80)

    try:
        # Example 1: Code Quality Assessment
        await example_code_quality_assessment()

        # Example 2: Performance Analysis
        # Uncomment to run performance analysis example
        # await example_performance_analysis()

        logger.info("\n" + "=" * 80)
        logger.info("All examples completed successfully!")
        logger.info("=" * 80)

    except Exception as e:
        # Intentionally broad: top-level example script catch-all to ensure any
        # unexpected error is logged with full traceback before propagating.
        logger.error(f"Example execution failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
