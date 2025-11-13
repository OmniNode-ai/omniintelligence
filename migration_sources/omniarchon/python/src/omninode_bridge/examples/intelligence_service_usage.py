"""
Intelligence Service Client Usage Examples

Demonstrates how to use the Intelligence Service HTTP client with
comprehensive API contracts for code quality assessment, performance
analysis, and pattern detection.

ONEX Pattern: Effect Node (External HTTP I/O)
Service: Archon Intelligence Service
Base URL: http://localhost:8053

Examples:
1. Code Quality Assessment - Comprehensive 6-dimensional quality analysis
2. Performance Analysis - Baseline establishment and optimization opportunities
3. Pattern Detection - Best practices, anti-patterns, and security patterns
4. Health Checks - Service availability monitoring
5. Error Handling - OnexError integration and retry logic
6. Metrics Tracking - Client performance monitoring
"""

import asyncio
import logging
from typing import List

# Import HTTP client
from omninode_bridge.clients.client_intelligence_service import (
    IntelligenceServiceClient,
)

# Import API contracts
from omninode_bridge.models.model_intelligence_api_contracts import (
    ModelPatternDetectionRequest,
    ModelPerformanceAnalysisRequest,
    ModelQualityAssessmentRequest,
    PatternCategory,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Example 1: Code Quality Assessment
# ============================================================================


async def example_quality_assessment():
    """
    Example: Assess code quality with comprehensive analysis.

    Demonstrates:
    - Request model creation with validation
    - Quality assessment execution
    - Response parsing with Pydantic models
    - Quality score interpretation (6-dimensional)
    - ONEX compliance validation
    """
    logger.info("=" * 80)
    logger.info("Example 1: Code Quality Assessment")
    logger.info("=" * 80)

    # Sample code to analyze
    code_content = '''
async def calculate_user_score(user_id: int, db: Session) -> float:
    """
    Calculate user score based on activity metrics.

    Args:
        user_id: User ID to calculate score for
        db: Database session

    Returns:
        User score (0.0-1.0)
    """
    user = await db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")

    # Calculate score from metrics
    activity_score = user.activity_count / 100.0
    engagement_score = user.engagement_rate

    return min((activity_score + engagement_score) / 2.0, 1.0)
'''

    async with IntelligenceServiceClient() as client:
        # Create quality assessment request
        request = ModelQualityAssessmentRequest(
            content=code_content,
            source_path="src/services/user_service.py",
            language="python",
            include_recommendations=True,
            min_quality_threshold=0.7,
        )

        logger.info(f"Assessing code quality for: {request.source_path}")

        try:
            # Execute quality assessment
            response = await client.assess_code_quality(request)

            # Parse and display results
            logger.info(f"\n{'=' * 60}")
            logger.info("Quality Assessment Results")
            logger.info(f"{'=' * 60}")
            logger.info(f"Overall Quality Score: {response.quality_score:.2f}")
            logger.info(f"ONEX Compliance Score: {response.onex_compliance.score:.2f}")
            logger.info(f"Architectural Era: {response.architectural_era}")
            logger.info(f"Temporal Relevance: {response.temporal_relevance:.2f}")

            logger.info(f"\nMaintainability Metrics:")
            logger.info(
                f"  Complexity Score: {response.maintainability.complexity_score:.2f}"
            )
            logger.info(
                f"  Readability Score: {response.maintainability.readability_score:.2f}"
            )
            logger.info(
                f"  Testability Score: {response.maintainability.testability_score:.2f}"
            )

            logger.info(f"\nArchitectural Compliance:")
            logger.info(f"  Score: {response.architectural_compliance.score:.2f}")
            logger.info(f"  Reasoning: {response.architectural_compliance.reasoning}")

            if response.onex_compliance.violations:
                logger.warning(f"\nONEX Compliance Violations:")
                for violation in response.onex_compliance.violations:
                    logger.warning(f"  - {violation}")

            if response.onex_compliance.recommendations:
                logger.info(f"\nRecommendations:")
                for rec in response.onex_compliance.recommendations:
                    logger.info(f"  - {rec}")

            logger.info(f"\nTimestamp: {response.timestamp}")

            return response

        except Exception as e:
            logger.error(f"Quality assessment failed: {e}", exc_info=True)
            raise


# ============================================================================
# Example 2: Performance Analysis
# ============================================================================


async def example_performance_analysis():
    """
    Example: Analyze performance and identify optimization opportunities.

    Demonstrates:
    - Performance baseline establishment
    - Optimization opportunity detection
    - ROI scoring and ranking
    - Implementation guidance
    """
    logger.info("\n" + "=" * 80)
    logger.info("Example 2: Performance Analysis")
    logger.info("=" * 80)

    # Sample code for performance analysis
    code_content = '''
async def fetch_user_dashboard_data(user_id: int, db: Session) -> Dict[str, Any]:
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

    async with IntelligenceServiceClient() as client:
        # Create performance analysis request
        request = ModelPerformanceAnalysisRequest(
            operation_name="user_dashboard_fetch",
            code_content=code_content,
            context={
                "execution_type": "async",
                "io_type": "database",
                "expected_frequency": "high",
                "current_latency_p95": 500,  # 500ms current P95
            },
            include_opportunities=True,
            target_percentile=95,
        )

        logger.info(f"Analyzing performance for: {request.operation_name}")

        try:
            # Execute performance analysis
            response = await client.analyze_performance(request)

            # Parse and display results
            logger.info(f"\n{'=' * 60}")
            logger.info("Performance Analysis Results")
            logger.info(f"{'=' * 60}")

            logger.info(f"\nBaseline Metrics:")
            logger.info(f"  Operation: {response.baseline_metrics.operation_name}")
            logger.info(
                f"  Baseline Latency: {response.baseline_metrics.baseline_latency_ms or 'N/A'}ms"
            )
            logger.info(
                f"  Target Latency (P{request.target_percentile}): {response.baseline_metrics.target_latency_ms or 'N/A'}ms"
            )
            logger.info(
                f"  Complexity Estimate: {response.baseline_metrics.complexity_estimate}"
            )

            logger.info(
                f"\nOptimization Opportunities Found: {response.total_opportunities}"
            )

            if response.optimization_opportunities:
                logger.info(f"\nTop Opportunities (Ranked by ROI):")
                for i, opp in enumerate(response.optimization_opportunities, 1):
                    logger.info(f"\n{i}. {opp.title} (ROI: {opp.roi_score:.2f})")
                    logger.info(f"   Category: {opp.category}")
                    logger.info(
                        f"   Estimated Improvement: {opp.estimated_improvement}"
                    )
                    logger.info(f"   Effort: {opp.effort_estimate}")
                    logger.info(f"   Description: {opp.description}")

                    if opp.implementation_steps:
                        logger.info(f"   Implementation Steps:")
                        for step in opp.implementation_steps:
                            logger.info(f"     - {step}")

            if response.estimated_total_improvement:
                logger.info(
                    f"\nEstimated Total Improvement: {response.estimated_total_improvement}"
                )

            logger.info(f"\nTimestamp: {response.timestamp}")

            return response

        except Exception as e:
            logger.error(f"Performance analysis failed: {e}", exc_info=True)
            raise


# ============================================================================
# Example 3: Pattern Detection
# ============================================================================


async def example_pattern_detection():
    """
    Example: Detect code patterns across multiple categories.

    Demonstrates:
    - Pattern detection with category filtering
    - Best practices identification
    - Anti-pattern detection
    - ONEX compliance validation
    - Pattern-based recommendations
    """
    logger.info("\n" + "=" * 80)
    logger.info("Example 3: Pattern Detection")
    logger.info("=" * 80)

    # Sample code for pattern detection
    code_content = '''
class UserRepository:
    """Repository for user data access."""

    def __init__(self, db_connection):
        self.db = db_connection

    def get_user_by_id(self, user_id: int) -> User:
        """Fetch user by ID."""
        query = f"SELECT * FROM users WHERE id = {user_id}"  # SQL injection risk!
        return self.db.execute(query)

    def create_user(self, username: str, email: str, password: str) -> User:
        """Create new user."""
        # No password hashing - security issue!
        user = User(username=username, email=email, password=password)
        self.db.add(user)
        self.db.commit()
        return user
'''

    async with IntelligenceServiceClient() as client:
        # Create pattern detection request
        request = ModelPatternDetectionRequest(
            content=code_content,
            source_path="src/repositories/user_repository.py",
            pattern_categories=[
                PatternCategory.BEST_PRACTICES,
                PatternCategory.ANTI_PATTERNS,
                PatternCategory.SECURITY_PATTERNS,
            ],
            min_confidence=0.7,
            include_recommendations=True,
        )

        logger.info(f"Detecting patterns in: {request.source_path}")
        logger.info(f"Categories: {[cat.value for cat in request.pattern_categories]}")

        try:
            # Execute pattern detection
            response = await client.detect_patterns(request)

            # Parse and display results
            logger.info(f"\n{'=' * 60}")
            logger.info("Pattern Detection Results")
            logger.info(f"{'=' * 60}")

            logger.info(f"\nAnalysis Summary:")
            for key, value in response.analysis_summary.items():
                logger.info(f"  {key}: {value}")

            logger.info(f"\nConfidence Scores:")
            for key, value in response.confidence_scores.items():
                logger.info(f"  {key}: {value:.2f}")

            if response.detected_patterns:
                logger.info(f"\nDetected Patterns ({len(response.detected_patterns)}):")
                for pattern in response.detected_patterns:
                    logger.info(f"\n  Pattern: {pattern.pattern_type}")
                    logger.info(f"  Category: {pattern.category.value}")
                    logger.info(f"  Confidence: {pattern.confidence:.2f}")
                    logger.info(f"  Description: {pattern.description}")

                    if pattern.location:
                        logger.info(f"  Location: {pattern.location}")

                    if pattern.severity:
                        logger.info(f"  Severity: {pattern.severity}")

                    if pattern.suggested_fix:
                        logger.info(f"  Suggested Fix: {pattern.suggested_fix}")

            if response.anti_patterns:
                logger.warning(
                    f"\nAnti-Patterns Detected ({len(response.anti_patterns)}):"
                )
                for anti_pattern in response.anti_patterns:
                    logger.warning(
                        f"  - {anti_pattern.pattern_type}: {anti_pattern.description}"
                    )
                    if anti_pattern.suggested_fix:
                        logger.info(f"    Fix: {anti_pattern.suggested_fix}")

            if response.architectural_compliance:
                logger.info(f"\nArchitectural Compliance:")
                logger.info(
                    f"  ONEX Compliant: {response.architectural_compliance.onex_compliance}"
                )
                if response.architectural_compliance.node_type_detected:
                    logger.info(
                        f"  Node Type: {response.architectural_compliance.node_type_detected}"
                    )
                if response.architectural_compliance.violations:
                    logger.warning(f"  Violations:")
                    for violation in response.architectural_compliance.violations:
                        logger.warning(f"    - {violation}")

            if response.recommendations:
                logger.info(f"\nRecommendations:")
                for rec in response.recommendations:
                    logger.info(f"  - {rec}")

            logger.info(f"\nTimestamp: {response.timestamp}")

            return response

        except Exception as e:
            logger.error(f"Pattern detection failed: {e}", exc_info=True)
            raise


# ============================================================================
# Example 4: Health Checks
# ============================================================================


async def example_health_check():
    """
    Example: Monitor service health.

    Demonstrates:
    - Health check execution
    - Service status interpretation
    - Dependency availability checking
    """
    logger.info("\n" + "=" * 80)
    logger.info("Example 4: Health Check")
    logger.info("=" * 80)

    async with IntelligenceServiceClient() as client:
        try:
            # Execute health check
            health = await client.check_health()

            # Display health status
            logger.info(f"\n{'=' * 60}")
            logger.info("Service Health Status")
            logger.info(f"{'=' * 60}")
            logger.info(f"Status: {health.status}")
            logger.info(f"Version: {health.service_version}")
            logger.info(f"Uptime: {health.uptime_seconds or 'N/A'} seconds")

            logger.info(f"\nDependency Status:")
            logger.info(f"  Memgraph: {'✓' if health.memgraph_connected else '✗'}")
            logger.info(f"  Ollama: {'✓' if health.ollama_connected else '✗'}")
            logger.info(
                f"  Freshness DB: {'✓' if health.freshness_database_connected else '✗'}"
            )

            if health.error:
                logger.warning(f"\nError: {health.error}")

            logger.info(f"\nLast Check: {health.last_check}")

            return health

        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            raise


# ============================================================================
# Example 5: Error Handling
# ============================================================================


async def example_error_handling():
    """
    Example: Demonstrate comprehensive error handling.

    Demonstrates:
    - OnexError integration
    - Retry logic with exponential backoff
    - Circuit breaker pattern
    - Validation error handling
    - Timeout handling
    """
    logger.info("\n" + "=" * 80)
    logger.info("Example 5: Error Handling")
    logger.info("=" * 80)

    async with IntelligenceServiceClient(
        base_url="http://localhost:8053",
        timeout_seconds=5.0,
        max_retries=2,
        circuit_breaker_enabled=True,
    ) as client:
        # Example 5.1: Validation Error
        logger.info("\n5.1: Testing validation error handling...")
        try:
            invalid_request = ModelQualityAssessmentRequest(
                content="",  # Invalid: empty content
                source_path="test.py",
            )
            await client.assess_code_quality(invalid_request)
        except Exception as e:
            logger.info(f"✓ Validation error caught: {type(e).__name__}: {e}")

        # Example 5.2: Timeout Handling
        logger.info("\n5.2: Testing timeout handling...")
        try:
            request = ModelQualityAssessmentRequest(
                content="def test(): pass", source_path="test.py"
            )
            # Use extremely short timeout to trigger timeout
            await client.assess_code_quality(request, timeout_override=0.001)
        except Exception as e:
            logger.info(f"✓ Timeout error caught: {type(e).__name__}: {e}")

        # Example 5.3: Circuit Breaker
        logger.info("\n5.3: Circuit breaker state...")
        metrics = client.get_metrics()
        logger.info(f"Circuit Breaker State: {metrics['circuit_breaker_state']}")
        logger.info(f"Total Requests: {metrics['total_requests']}")
        logger.info(f"Success Rate: {metrics['success_rate']:.2%}")


# ============================================================================
# Example 6: Metrics Tracking
# ============================================================================


async def example_metrics_tracking():
    """
    Example: Monitor client performance metrics.

    Demonstrates:
    - Metrics collection
    - Performance monitoring
    - Success rate tracking
    - Average latency calculation
    """
    logger.info("\n" + "=" * 80)
    logger.info("Example 6: Metrics Tracking")
    logger.info("=" * 80)

    async with IntelligenceServiceClient() as client:
        # Execute several requests
        logger.info("Executing sample requests for metrics...")

        for i in range(5):
            try:
                request = ModelQualityAssessmentRequest(
                    content=f"def function_{i}(): pass", source_path=f"test_{i}.py"
                )
                await client.assess_code_quality(request)
                logger.info(f"  Request {i + 1}/5 completed")
            except Exception:
                pass

        # Get and display metrics
        metrics = client.get_metrics()

        logger.info(f"\n{'=' * 60}")
        logger.info("Client Performance Metrics")
        logger.info(f"{'=' * 60}")
        logger.info(f"Total Requests: {metrics['total_requests']}")
        logger.info(f"Successful Requests: {metrics['successful_requests']}")
        logger.info(f"Failed Requests: {metrics['failed_requests']}")
        logger.info(f"Success Rate: {metrics['success_rate']:.2%}")
        logger.info(f"Average Duration: {metrics['avg_duration_ms']:.2f}ms")
        logger.info(f"Timeout Errors: {metrics['timeout_errors']}")
        logger.info(f"Retries Attempted: {metrics['retries_attempted']}")
        logger.info(f"Circuit Breaker Opens: {metrics['circuit_breaker_opens']}")
        logger.info(f"Circuit Breaker State: {metrics['circuit_breaker_state']}")
        logger.info(f"Is Healthy: {metrics['is_healthy']}")
        logger.info(f"Last Health Check: {metrics['last_health_check']}")


# ============================================================================
# Main Execution
# ============================================================================


async def run_all_examples():
    """Run all examples sequentially."""
    logger.info("\n" + "=" * 80)
    logger.info("Intelligence Service Client Usage Examples")
    logger.info("=" * 80)

    try:
        await example_quality_assessment()
        await example_performance_analysis()
        await example_pattern_detection()
        await example_health_check()
        await example_error_handling()
        await example_metrics_tracking()

        logger.info("\n" + "=" * 80)
        logger.info("All examples completed successfully!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Example execution failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Run all examples
    asyncio.run(run_all_examples())
