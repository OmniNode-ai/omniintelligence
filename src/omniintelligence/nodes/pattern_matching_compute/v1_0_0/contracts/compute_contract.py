"""Python Contract for PatternMatching Compute Node"""
from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List

class PatternMatchingComputeContract(ModelContractBase):
    """Contract for pattern_matching compute node."""
    name: str = "pattern_matching_compute"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "Match and detect code patterns"
    node_type: EnumNodeType = EnumNodeType.COMPUTE
    input_model: str = "ModelPatternMatchingComputeInput"
    output_model: str = "ModelPatternMatchingComputeOutput"
    config_model: str = "ModelPatternMatchingComputeConfig"
    
    subcontracts: dict = Field(default={
        "input": "./subcontracts/input_subcontract.yaml",
        "output": "./subcontracts/output_subcontract.yaml",
        "config": "./subcontracts/config_subcontract.yaml",
    })
    
    capabilities: List[str] = Field(default=['Match_Pattern', 'Detect_Pattern', 'Analyze_Similarity'])
    performance_requirements: dict = Field(default={
        "max_latency_ms": 5000,
        "max_memory_mb": 512,
        "min_throughput_per_second": 20,
    })
    
    def validate_node_specific_config(self) -> None:
        pass
