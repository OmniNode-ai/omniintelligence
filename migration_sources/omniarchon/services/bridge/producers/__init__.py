"""
Kafka producers for bridge service.

This module provides Kafka producers for publishing events to the async
intelligence enrichment pipeline.
"""

from .kafka_producer_manager import KafkaProducerManager

__all__ = ["KafkaProducerManager"]
