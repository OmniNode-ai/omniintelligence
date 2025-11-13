"""
Crawling Services Package

This package contains services for web crawling, document processing,
and related orchestration operations.
"""

# Make crawl4ai dependency optional for testing
try:
    from .code_extraction_service import CodeExtractionService
    from .crawling_service import (
        CrawlingService,
        CrawlOrchestrationService,
        get_active_orchestration,
        register_orchestration,
        unregister_orchestration,
    )
    from .document_storage_operations import DocumentStorageOperations
    from .helpers.site_config import SiteConfig

    # Export helpers
    from .helpers.url_handler import URLHandler
    from .progress_mapper import ProgressMapper

    # Export strategies
    from .strategies.batch import BatchCrawlStrategy
    from .strategies.recursive import RecursiveCrawlStrategy
    from .strategies.single_page import SinglePageCrawlStrategy
    from .strategies.sitemap import SitemapCrawlStrategy

    __all__ = [
        "CrawlingService",
        "CrawlOrchestrationService",
        "CodeExtractionService",
        "DocumentStorageOperations",
        "ProgressMapper",
        "BatchCrawlStrategy",
        "RecursiveCrawlStrategy",
        "SinglePageCrawlStrategy",
        "SitemapCrawlStrategy",
        "URLHandler",
        "SiteConfig",
        "get_active_orchestration",
        "register_orchestration",
        "unregister_orchestration",
    ]
except ImportError as e:
    # If crawl4ai is not available, provide stub classes for testing
    import logging

    logging.warning(f"Crawling functionality unavailable: {e}")

    # Create minimal stub classes
    class CrawlingService:
        """Stub for tests without crawl4ai."""

        pass

    class CrawlOrchestrationService:
        """Stub for tests without crawl4ai."""

        pass

    class CodeExtractionService:
        """Stub for tests without crawl4ai."""

        pass

    class DocumentStorageOperations:
        """Stub for tests without crawl4ai."""

        pass

    class ProgressMapper:
        """Stub for tests without crawl4ai."""

        pass

    class BatchCrawlStrategy:
        """Stub for tests without crawl4ai."""

        pass

    class RecursiveCrawlStrategy:
        """Stub for tests without crawl4ai."""

        pass

    class SinglePageCrawlStrategy:
        """Stub for tests without crawl4ai."""

        pass

    class SitemapCrawlStrategy:
        """Stub for tests without crawl4ai."""

        pass

    class URLHandler:
        """Stub for tests without crawl4ai."""

        pass

    class SiteConfig:
        """Stub for tests without crawl4ai."""

        pass

    def get_active_orchestration(session_id: str):
        """Stub for tests without crawl4ai."""
        return None

    def register_orchestration(session_id: str, service):
        """Stub for tests without crawl4ai."""
        pass

    def unregister_orchestration(session_id: str):
        """Stub for tests without crawl4ai."""
        pass

    __all__ = [
        "CrawlingService",
        "CrawlOrchestrationService",
        "CodeExtractionService",
        "DocumentStorageOperations",
        "ProgressMapper",
        "BatchCrawlStrategy",
        "RecursiveCrawlStrategy",
        "SinglePageCrawlStrategy",
        "SitemapCrawlStrategy",
        "URLHandler",
        "SiteConfig",
        "get_active_orchestration",
        "register_orchestration",
        "unregister_orchestration",
    ]
