"""Python Contract for SemanticAnalysis Compute Node"""
from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List

class SemanticAnalysisComputeContract(ModelContractBase):
    """Contract for semantic_analysis compute node."""
    name: str = "semantic_analysis_compute"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "Analyze semantic features of code"
    node_type: EnumNodeType = EnumNodeType.COMPUTE
    input_model: str = "ModelSemanticAnalysisComputeInput"
    output_model: str = "ModelSemanticAnalysisComputeOutput"
    config_model: str = "ModelSemanticAnalysisComputeConfig"
    
    subcontracts: dict = Field(default={
        "input": "./subcontracts/input_subcontract.yaml",
        "output": "./subcontracts/output_subcontract.yaml",
        "config": "./subcontracts/config_subcontract.yaml",
    })
    
    capabilities: List[str] = Field(default=['Analyze_Semantics', 'Extract_Features', 'Compute_Complexity'])
    performance_requirements: dict = Field(default={
        "max_latency_ms": 5000,
        "max_memory_mb": 512,
        "min_throughput_per_second": 20,
    })
    
    def validate_node_specific_config(self) -> None:
        pass
