"""
Intelligence consumer service for asynchronous document enrichment.

Consumes enrichment events from Kafka, processes them through the
intelligence service, and publishes completion events.
"""

__version__ = "1.0.0"

from .main import IntelligenceConsumerService, run

__all__ = ["IntelligenceConsumerService", "run"]
