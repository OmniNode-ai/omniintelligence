"""Python Contract for KafkaEvent Effect Node"""
from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List

class KafkaEventEffectContract(ModelContractBase):
    """Contract for kafka_event effect node."""
    name: str = "kafka_event_effect"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "Publish and consume events via Kafka/Redpanda"
    node_type: EnumNodeType = EnumNodeType.EFFECT
    input_model: str = "ModelKafkaEventEffectInput"
    output_model: str = "ModelKafkaEventEffectOutput"
    config_model: str = "ModelKafkaEventEffectConfig"
    
    subcontracts: dict = Field(default={
        "input": "./subcontracts/input_subcontract.yaml",
        "output": "./subcontracts/output_subcontract.yaml",
        "config": "./subcontracts/config_subcontract.yaml",
    })
    
    capabilities: List[str] = Field(default=['Publish_Event', 'Consume_Event', 'Create_Topic', 'Delete_Topic'])
    performance_requirements: dict = Field(default={
        "max_latency_ms": 10000,
        "max_memory_mb": 1024,
        "min_throughput_per_second": 50,
    })
    
    def validate_node_specific_config(self) -> None:
        pass
