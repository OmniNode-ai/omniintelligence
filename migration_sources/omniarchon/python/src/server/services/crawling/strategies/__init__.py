"""
Crawling Strategies

This module contains different crawling strategies for various URL types.
"""

from server.services.crawling.strategies.batch import BatchCrawlStrategy
from server.services.crawling.strategies.recursive import RecursiveCrawlStrategy
from server.services.crawling.strategies.single_page import SinglePageCrawlStrategy
from server.services.crawling.strategies.sitemap import SitemapCrawlStrategy

__all__ = [
    "BatchCrawlStrategy",
    "RecursiveCrawlStrategy",
    "SinglePageCrawlStrategy",
    "SitemapCrawlStrategy",
]
