"""Python Contract for IntelligenceApi Effect Node"""
from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List

class IntelligenceApiEffectContract(ModelContractBase):
    """Contract for intelligence_api effect node."""
    name: str = "intelligence_api_effect"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "HTTP API gateway for intelligence services"
    node_type: EnumNodeType = EnumNodeType.EFFECT
    input_model: str = "ModelIntelligenceApiEffectInput"
    output_model: str = "ModelIntelligenceApiEffectOutput"
    config_model: str = "ModelIntelligenceApiEffectConfig"
    
    subcontracts: dict = Field(default={
        "input": "./subcontracts/input_subcontract.yaml",
        "output": "./subcontracts/output_subcontract.yaml",
        "config": "./subcontracts/config_subcontract.yaml",
    })
    
    capabilities: List[str] = Field(default=['Get_Request', 'Post_Request', 'Put_Request', 'Delete_Request'])
    performance_requirements: dict = Field(default={
        "max_latency_ms": 10000,
        "max_memory_mb": 1024,
        "min_throughput_per_second": 50,
    })
    
    def validate_node_specific_config(self) -> None:
        pass
