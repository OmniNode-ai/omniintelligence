"""
Pattern Ingestion Pipeline
===========================

This module provides a comprehensive pipeline for ingesting code patterns from
repositories and extracting pattern intelligence from PR reviews.

Main Components:
- IngestionPipeline: Main pipeline for pattern extraction and storage
- PRIntelligenceExtractor: Extracts pattern insights from PR reviews using langextract
- BatchProcessor: Parallel processing of multiple repositories

Usage:
    from pattern_ingestion import IngestionPipeline, PRIntelligenceExtractor

    pipeline = IngestionPipeline(db_config)
    await pipeline.ingest_directory('/path/to/code')

    pr_extractor = PRIntelligenceExtractor(db_config)
    await pr_extractor.analyze_pr(repo='owner/repo', pr_number=123)
"""

from pattern_ingestion.batch_processor import BatchProcessor
from pattern_ingestion.ingestion_pipeline import IngestionPipeline
from pattern_ingestion.pr_intelligence import PRIntelligenceExtractor

__all__ = [
    "IngestionPipeline",
    "PRIntelligenceExtractor",
    "BatchProcessor",
]
