"""Python Contract for EntityExtraction Compute Node"""
from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List

class EntityExtractionComputeContract(ModelContractBase):
    """Contract for entity_extraction compute node."""
    name: str = "entity_extraction_compute"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "Extract code entities from source code"
    node_type: EnumNodeType = EnumNodeType.COMPUTE
    input_model: str = "ModelEntityExtractionComputeInput"
    output_model: str = "ModelEntityExtractionComputeOutput"
    config_model: str = "ModelEntityExtractionComputeConfig"
    
    subcontracts: dict = Field(default={
        "input": "./subcontracts/input_subcontract.yaml",
        "output": "./subcontracts/output_subcontract.yaml",
        "config": "./subcontracts/config_subcontract.yaml",
    })
    
    capabilities: List[str] = Field(default=['Extract_Entities', 'Parse_Code', 'Analyze_Ast'])
    performance_requirements: dict = Field(default={
        "max_latency_ms": 5000,
        "max_memory_mb": 512,
        "min_throughput_per_second": 20,
    })
    
    def validate_node_specific_config(self) -> None:
        pass
