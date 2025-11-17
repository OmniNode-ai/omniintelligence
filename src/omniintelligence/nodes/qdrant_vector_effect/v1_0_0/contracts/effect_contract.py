"""Python Contract for QdrantVector Effect Node"""
from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List

class QdrantVectorEffectContract(ModelContractBase):
    """Contract for qdrant_vector effect node."""
    name: str = "qdrant_vector_effect"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "Store and search vectors in Qdrant"
    node_type: EnumNodeType = EnumNodeType.EFFECT
    input_model: str = "ModelQdrantVectorEffectInput"
    output_model: str = "ModelQdrantVectorEffectOutput"
    config_model: str = "ModelQdrantVectorEffectConfig"
    
    subcontracts: dict = Field(default={
        "input": "./subcontracts/input_subcontract.yaml",
        "output": "./subcontracts/output_subcontract.yaml",
        "config": "./subcontracts/config_subcontract.yaml",
    })
    
    capabilities: List[str] = Field(default=['Index_Vector', 'Search_Vectors', 'Update_Vector', 'Delete_Vector'])
    performance_requirements: dict = Field(default={
        "max_latency_ms": 10000,
        "max_memory_mb": 1024,
        "min_throughput_per_second": 50,
    })
    
    def validate_node_specific_config(self) -> None:
        pass
