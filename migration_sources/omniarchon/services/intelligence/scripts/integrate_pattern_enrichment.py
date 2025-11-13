#!/usr/bin/env python3
"""
Script to integrate pattern enrichment into routes.py

This script modifies the routes.py file to add:
1. Imports for PatternAnalyticsService and MetadataEnrichmentService
2. Global service instances
3. Service getter functions
4. New enrichment endpoints

Usage:
    python3 scripts/integrate_pattern_enrichment.py
"""

import re
import sys
from pathlib import Path


def main():
    # Path to routes.py
    routes_path = Path("services/intelligence/src/api/pattern_learning/routes.py")

    if not routes_path.exists():
        print(f"Error: {routes_path} not found")
        sys.exit(1)

    # Read current content
    with open(routes_path, "r") as f:
        content = f.read()

    # Check if already integrated
    if "PatternAnalyticsService" in content:
        print("✓ Pattern analytics already integrated")
        return

    print("Integrating pattern enrichment into routes.py...")

    # 1. Add imports after tree_integration imports
    imports_addition = """
# Pattern analytics and enrichment
from src.api.pattern_analytics.service import PatternAnalyticsService
from src.api.pattern_learning.metadata_enrichment import MetadataEnrichmentService
"""

    content = content.replace(
        "from src.api.pattern_learning.tree_integration import (\n    clear_tree_cache,\n    get_tree_cache_metrics,\n    get_tree_info_for_pattern,\n)",
        "from src.api.pattern_learning.tree_integration import (\n    clear_tree_cache,\n    get_tree_cache_metrics,\n    get_tree_info_for_pattern,\n)"
        + imports_addition,
    )

    # 2. Add global variables
    globals_addition = """_analytics_service: Optional[PatternAnalyticsService] = None
_enrichment_service: Optional[MetadataEnrichmentService] = None
"""

    content = content.replace(
        "_langextract_client: Optional[ClientLangextractHttp] = None",
        "_langextract_client: Optional[ClientLangextractHttp] = None\n"
        + globals_addition,
    )

    # 3. Add getter functions
    getters_addition = """

def get_analytics_service() -> PatternAnalyticsService:
    \"\"\"Get or create analytics service instance\"\"\"
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = PatternAnalyticsService()
    return _analytics_service


def get_enrichment_service() -> MetadataEnrichmentService:
    \"\"\"Get or create metadata enrichment service instance\"\"\"
    global _enrichment_service
    if _enrichment_service is None:
        analytics_service = get_analytics_service()
        _enrichment_service = MetadataEnrichmentService(
            analytics_service=analytics_service
        )
    return _enrichment_service
"""

    # Find the get_langextract_client function and add after it
    pattern = r"(def get_langextract_client\(\) -> ClientLangextractHttp:.*?return _langextract_client\n)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        content = content.replace(match.group(0), match.group(0) + getters_addition)

    # 4. Add request model
    request_model_addition = """

class PatternEnrichmentRequest(BaseModel):
    \"\"\"Request for pattern metadata enrichment\"\"\"

    pattern_id: str = Field(..., description="Pattern ID to enrich")
    pattern_data: Dict[str, Any] = Field(
        default_factory=dict, description="Base pattern data"
    )
"""

    # Add after PatternMetricsResponse
    content = content.replace(
        "class PatternMetricsResponse(BaseModel):",
        request_model_addition + "\n\nclass PatternMetricsResponse(BaseModel):",
    )

    # 5. Add enrichment endpoints before health check
    enrichment_endpoints = '''

@router.post("/pattern/enrich", response_model=Dict[str, Any])
async def enrich_pattern_metadata(
    request: PatternEnrichmentRequest, correlation_id: Optional[UUID] = None
):
    """
    Enrich pattern with analytics metadata

    Adds success_rate, usage_count, avg_quality_score, and confidence_score
    to pattern data based on historical feedback.

    Performance: <20ms target
    """
    start_time = time.time()
    logger.info(
        f"POST /api/pattern-learning/pattern/enrich | "
        f"pattern_id={request.pattern_id} | correlation_id={correlation_id}"
    )

    try:
        enrichment_service = get_enrichment_service()

        # Enrich pattern with analytics metadata
        enriched_pattern = await enrichment_service.enrich_pattern_with_analytics(
            pattern_id=request.pattern_id,
            pattern_data=request.pattern_data,
        )

        # Get enrichment stats
        stats = enrichment_service.get_statistics()

        processing_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Pattern enriched | pattern_id={request.pattern_id} | "
            f"enriched={enriched_pattern.get('enriched', False)} | "
            f"time_ms={processing_time_ms:.2f}"
        )

        return success_response(
            enriched_pattern,
            metadata={
                **processing_time_metadata(start_time),
                "enrichment_stats": stats,
            }
        )

    except Exception as e:
        logger.error(
            f"Pattern enrichment failed | pattern_id={request.pattern_id} | error={str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Pattern enrichment failed: {str(e)}"
        )


@router.post("/pattern/enrich/batch", response_model=Dict[str, Any])
async def enrich_patterns_batch(
    patterns: list[Dict[str, Any]], correlation_id: Optional[UUID] = None
):
    """
    Enrich multiple patterns with analytics metadata

    Each pattern dict must have 'pattern_id' field.

    Performance: <20ms per pattern target
    """
    start_time = time.time()
    logger.info(
        f"POST /api/pattern-learning/pattern/enrich/batch | "
        f"count={len(patterns)} | correlation_id={correlation_id}"
    )

    try:
        enrichment_service = get_enrichment_service()

        # Enrich all patterns
        enriched_patterns = await enrichment_service.enrich_multiple_patterns(patterns)

        # Get enrichment stats
        stats = enrichment_service.get_statistics()

        processing_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Batch enrichment complete | count={len(enriched_patterns)} | "
            f"time_ms={processing_time_ms:.2f} | "
            f"avg_per_pattern_ms={processing_time_ms / len(patterns) if patterns else 0:.2f}"
        )

        return success_response(
            {
                "enriched_patterns": enriched_patterns,
                "total_count": len(enriched_patterns),
            },
            metadata={
                **processing_time_metadata(start_time),
                "enrichment_stats": stats,
                "avg_time_per_pattern_ms": processing_time_ms / len(patterns) if patterns else 0,
            }
        )

    except Exception as e:
        logger.error(
            f"Batch enrichment failed | count={len(patterns)} | error={str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500, detail=f"Batch enrichment failed: {str(e)}"
        )


'''

    # Insert before health check endpoint
    content = content.replace(
        '@router.get("/health")\nasync def health_check(',
        enrichment_endpoints + '@router.get("/health")\nasync def health_check(',
    )

    # Write updated content
    with open(routes_path, "w") as f:
        f.write(content)

    print("✓ Pattern enrichment integration complete!")
    print("\nNew endpoints added:")
    print("  - POST /api/pattern-learning/pattern/enrich")
    print("  - POST /api/pattern-learning/pattern/enrich/batch")
    print("\nServices added:")
    print("  - get_analytics_service()")
    print("  - get_enrichment_service()")


if __name__ == "__main__":
    main()
