"""Python Contract for RelationshipDetection Compute Node"""
from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List

class RelationshipDetectionComputeContract(ModelContractBase):
    """Contract for relationship_detection compute node."""
    name: str = "relationship_detection_compute"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "Detect relationships between code entities"
    node_type: EnumNodeType = EnumNodeType.COMPUTE
    input_model: str = "ModelRelationshipDetectionComputeInput"
    output_model: str = "ModelRelationshipDetectionComputeOutput"
    config_model: str = "ModelRelationshipDetectionComputeConfig"
    
    subcontracts: dict = Field(default={
        "input": "./subcontracts/input_subcontract.yaml",
        "output": "./subcontracts/output_subcontract.yaml",
        "config": "./subcontracts/config_subcontract.yaml",
    })
    
    capabilities: List[str] = Field(default=['Detect_Relationships', 'Analyze_Dependencies', 'Build_Graph'])
    performance_requirements: dict = Field(default={
        "max_latency_ms": 5000,
        "max_memory_mb": 512,
        "min_throughput_per_second": 20,
    })
    
    def validate_node_specific_config(self) -> None:
        pass
