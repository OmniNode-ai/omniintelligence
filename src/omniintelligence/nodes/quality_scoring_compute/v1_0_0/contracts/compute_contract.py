"""Python Contract for QualityScoring Compute Node"""
from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List

class QualityScoringComputeContract(ModelContractBase):
    """Contract for quality_scoring compute node."""
    name: str = "quality_scoring_compute"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "Compute quality scores and compliance metrics"
    node_type: EnumNodeType = EnumNodeType.COMPUTE
    input_model: str = "ModelQualityScoringComputeInput"
    output_model: str = "ModelQualityScoringComputeOutput"
    config_model: str = "ModelQualityScoringComputeConfig"
    
    subcontracts: dict = Field(default={
        "input": "./subcontracts/input_subcontract.yaml",
        "output": "./subcontracts/output_subcontract.yaml",
        "config": "./subcontracts/config_subcontract.yaml",
    })
    
    capabilities: List[str] = Field(default=['Compute_Score', 'Check_Compliance', 'Calculate_Metrics'])
    performance_requirements: dict = Field(default={
        "max_latency_ms": 5000,
        "max_memory_mb": 512,
        "min_throughput_per_second": 20,
    })
    
    def validate_node_specific_config(self) -> None:
        pass
