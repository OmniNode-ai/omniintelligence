"""Kafka emission status enum."""

from enum import StrEnum


class EnumKafkaEmissionStatus(StrEnum):
    """Status of Kafka event emission.

    Used in handler metadata to indicate the outcome of attempting
    to emit events to Kafka topics.
    """

    SUCCESS = "success"
    FAILED = "failed"
    NO_PRODUCER = "no_producer_available"
    NO_TOPIC = "no_topic_configured"


__all__ = ["EnumKafkaEmissionStatus"]
