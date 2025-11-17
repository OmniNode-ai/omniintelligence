"""Operation types for KafkaEvent Effect Node"""
from enum import Enum

class EnumKafkaEventOperationType(str, Enum):
    """Operation types supported by kafka_event effect node."""
    PUBLISH_EVENT = "PUBLISH_EVENT"
    CONSUME_EVENT = "CONSUME_EVENT"
    CREATE_TOPIC = "CREATE_TOPIC"
    DELETE_TOPIC = "DELETE_TOPIC"
    HEALTH_CHECK = "HEALTH_CHECK"

    def is_system(self) -> bool:
        return self == EnumKafkaEventOperationType.HEALTH_CHECK
