"""
Pattern Metadata Enrichment

Enriches pattern data with analytics metadata from PatternAnalyticsService.
Provides success rates, usage statistics, and quality metrics for pattern scoring.

This module bridges PatternAnalyticsService with pattern matching/scoring to enable
data-driven pattern selection based on historical performance.

Performance Target: <20ms enrichment overhead
"""

import logging
import time
from typing import Any, Dict, Optional
from uuid import UUID

from src.api.pattern_analytics.service import PatternAnalyticsService

logger = logging.getLogger(__name__)


class MetadataEnrichmentService:
    """
    Service for enriching pattern metadata with analytics data.

    Queries PatternAnalyticsService to add:
    - success_rate: Historical success rate (0.0-1.0)
    - usage_count: Number of times pattern has been used
    - avg_quality_score: Average quality score (0.0-1.0)
    - confidence_score: Confidence based on sample size and success (0.0-1.0)
    """

    # Default values when no analytics data exists
    DEFAULT_SUCCESS_RATE = 0.5  # Neutral assumption
    DEFAULT_USAGE_COUNT = 0
    DEFAULT_QUALITY_SCORE = 0.5  # Neutral assumption
    DEFAULT_CONFIDENCE = 0.5  # Neutral assumption

    def __init__(
        self,
        analytics_service: Optional[PatternAnalyticsService] = None,
    ):
        """
        Initialize metadata enrichment service.

        Args:
            analytics_service: PatternAnalyticsService instance (optional, will create if not provided)
        """
        self.analytics_service = analytics_service or PatternAnalyticsService()
        self.logger = logging.getLogger("MetadataEnrichmentService")

        # Statistics tracking
        self._enrichment_count = 0
        self._fallback_count = 0
        self._total_enrichment_time = 0.0

    async def enrich_pattern_with_analytics(
        self,
        pattern_id: str,
        pattern_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Enrich pattern with analytics metadata.

        Queries PatternAnalyticsService for historical performance data and adds
        enriched fields to pattern_data.

        Args:
            pattern_id: Pattern identifier (UUID string)
            pattern_data: Base pattern data dictionary

        Returns:
            Enriched pattern data with added fields:
            - success_rate: 0.0-1.0 (historical success rate)
            - usage_count: integer (number of uses)
            - avg_quality_score: 0.0-1.0 (average quality)
            - confidence_score: 0.0-1.0 (confidence in metrics)
            - enriched: boolean (True if real data, False if fallback)
            - enrichment_time_ms: float (time taken to enrich)

        Performance: <20ms target
        """
        start_time = time.time()

        try:
            # Query pattern feedback history from analytics service
            feedback_result = await self.analytics_service.get_pattern_feedback_history(
                pattern_id=pattern_id
            )

            summary = feedback_result.get("summary", {})
            total_feedback = summary.get("total_feedback", 0)

            # Check if we have enough data
            if total_feedback == 0:
                # No data available, use fallback values
                enriched_data = self._apply_fallback_values(
                    pattern_data=pattern_data,
                    reason="no_feedback_data",
                )
                self._fallback_count += 1
            else:
                # Use real analytics data
                success_rate = summary.get("success_rate", self.DEFAULT_SUCCESS_RATE)
                avg_quality_score = summary.get(
                    "avg_quality_score", self.DEFAULT_QUALITY_SCORE
                )

                # Calculate confidence based on sample size
                # Full confidence at 30+ samples, scales linearly below that
                sample_factor = min(total_feedback / 30.0, 1.0)
                confidence_score = success_rate * sample_factor

                enriched_data = {
                    **pattern_data,
                    "success_rate": success_rate,
                    "usage_count": total_feedback,
                    "avg_quality_score": avg_quality_score,
                    "confidence_score": confidence_score,
                    "enriched": True,
                    "enrichment_source": "analytics_service",
                }

                self.logger.debug(
                    f"Pattern enriched with analytics | "
                    f"pattern_id={pattern_id} | "
                    f"success_rate={success_rate:.3f} | "
                    f"usage_count={total_feedback} | "
                    f"confidence={confidence_score:.3f}"
                )

        except Exception as e:
            # Error occurred, use fallback values
            self.logger.warning(
                f"Failed to enrich pattern metadata | "
                f"pattern_id={pattern_id} | "
                f"error={str(e)} | "
                f"using_fallback=True"
            )
            enriched_data = self._apply_fallback_values(
                pattern_data=pattern_data,
                reason=f"error: {str(e)}",
            )
            self._fallback_count += 1

        # Add timing metadata
        enrichment_time_ms = (time.time() - start_time) * 1000
        enriched_data["enrichment_time_ms"] = enrichment_time_ms

        # Track statistics
        self._enrichment_count += 1
        self._total_enrichment_time += enrichment_time_ms

        # Log warning if enrichment is slow
        if enrichment_time_ms > 20.0:
            self.logger.warning(
                f"Slow enrichment detected | "
                f"pattern_id={pattern_id} | "
                f"time_ms={enrichment_time_ms:.2f} | "
                f"target=20ms"
            )

        return enriched_data

    async def enrich_multiple_patterns(
        self,
        patterns: list[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        """
        Enrich multiple patterns with analytics metadata.

        Args:
            patterns: List of pattern dictionaries, each must have 'pattern_id' field

        Returns:
            List of enriched pattern dictionaries

        Performance: <20ms per pattern target
        """
        enriched_patterns = []

        for pattern in patterns:
            pattern_id = pattern.get("pattern_id")
            if not pattern_id:
                self.logger.warning(
                    "Pattern missing pattern_id, skipping enrichment | "
                    f"pattern={pattern}"
                )
                enriched_patterns.append(pattern)
                continue

            enriched_pattern = await self.enrich_pattern_with_analytics(
                pattern_id=str(pattern_id),
                pattern_data=pattern,
            )
            enriched_patterns.append(enriched_pattern)

        return enriched_patterns

    def _apply_fallback_values(
        self,
        pattern_data: Dict[str, Any],
        reason: str,
    ) -> Dict[str, Any]:
        """
        Apply fallback values when analytics data is unavailable.

        Args:
            pattern_data: Base pattern data
            reason: Reason for fallback

        Returns:
            Pattern data with fallback values
        """
        self.logger.info(
            f"Applying fallback values | reason={reason} | "
            f"success_rate={self.DEFAULT_SUCCESS_RATE} | "
            f"usage_count={self.DEFAULT_USAGE_COUNT} | "
            f"confidence={self.DEFAULT_CONFIDENCE}"
        )

        return {
            **pattern_data,
            "success_rate": self.DEFAULT_SUCCESS_RATE,
            "usage_count": self.DEFAULT_USAGE_COUNT,
            "avg_quality_score": self.DEFAULT_QUALITY_SCORE,
            "confidence_score": self.DEFAULT_CONFIDENCE,
            "enriched": False,
            "enrichment_source": "fallback",
            "fallback_reason": reason,
        }

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get enrichment statistics.

        Returns:
            Dictionary with enrichment statistics:
            - enrichment_count: Total enrichments performed
            - fallback_count: Number of times fallback was used
            - fallback_rate: Percentage of enrichments using fallback
            - avg_enrichment_time_ms: Average enrichment time
        """
        if self._enrichment_count == 0:
            return {
                "enrichment_count": 0,
                "fallback_count": 0,
                "fallback_rate": 0.0,
                "avg_enrichment_time_ms": 0.0,
            }

        return {
            "enrichment_count": self._enrichment_count,
            "fallback_count": self._fallback_count,
            "fallback_rate": (
                self._fallback_count / self._enrichment_count
                if self._enrichment_count > 0
                else 0.0
            ),
            "avg_enrichment_time_ms": (
                self._total_enrichment_time / self._enrichment_count
                if self._enrichment_count > 0
                else 0.0
            ),
            "total_enrichment_time_ms": self._total_enrichment_time,
        }

    def reset_statistics(self) -> None:
        """Reset statistics counters."""
        self._enrichment_count = 0
        self._fallback_count = 0
        self._total_enrichment_time = 0.0


# ============================================================================
# Convenience Function for Direct Usage
# ============================================================================


async def enrich_pattern_with_analytics(
    pattern_id: str,
    pattern_data: Dict[str, Any],
    analytics_service: Optional[PatternAnalyticsService] = None,
) -> Dict[str, Any]:
    """
    Convenience function for enriching a single pattern.

    Args:
        pattern_id: Pattern identifier
        pattern_data: Base pattern data
        analytics_service: Optional PatternAnalyticsService instance

    Returns:
        Enriched pattern data
    """
    enrichment_service = MetadataEnrichmentService(analytics_service=analytics_service)
    return await enrichment_service.enrich_pattern_with_analytics(
        pattern_id=pattern_id,
        pattern_data=pattern_data,
    )
