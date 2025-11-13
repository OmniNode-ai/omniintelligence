# Add these imports after tree_integration imports (line ~60):

# Pattern analytics and enrichment
from src.api.pattern_analytics.service import PatternAnalyticsService
from src.api.pattern_learning.metadata_enrichment import MetadataEnrichmentService

# Add these global variables after other globals (line ~140):

_analytics_service: Optional[PatternAnalyticsService] = None
_enrichment_service: Optional[MetadataEnrichmentService] = None


# Add these getter functions after get_langextract_client (line ~170):


def get_analytics_service() -> PatternAnalyticsService:
    """Get or create analytics service instance"""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = PatternAnalyticsService()
    return _analytics_service


def get_enrichment_service() -> MetadataEnrichmentService:
    """Get or create metadata enrichment service instance"""
    global _enrichment_service
    if _enrichment_service is None:
        analytics_service = get_analytics_service()
        _enrichment_service = MetadataEnrichmentService(
            analytics_service=analytics_service
        )
    return _enrichment_service


# Add this new endpoint class (with other request models ~line 90):


class PatternEnrichmentRequest(BaseModel):
    """Request for pattern metadata enrichment"""

    pattern_id: str = Field(..., description="Pattern ID to enrich")
    pattern_data: Dict[str, Any] = Field(
        default_factory=dict, description="Base pattern data"
    )


# Add this new endpoint (before health check endpoint):


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
            },
        )

    except Exception as e:
        logger.error(
            f"Pattern enrichment failed | pattern_id={request.pattern_id} | error={str(e)}",
            exc_info=True,
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
                "avg_time_per_pattern_ms": (
                    processing_time_ms / len(patterns) if patterns else 0
                ),
            },
        )

    except Exception as e:
        logger.error(
            f"Batch enrichment failed | count={len(patterns)} | error={str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail=f"Batch enrichment failed: {str(e)}"
        )
