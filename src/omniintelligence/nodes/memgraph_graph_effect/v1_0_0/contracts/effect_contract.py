"""Python Contract for MemgraphGraph Effect Node"""
from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List

class MemgraphGraphEffectContract(ModelContractBase):
    """Contract for memgraph_graph effect node."""
    name: str = "memgraph_graph_effect"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "Store and query knowledge graph in Memgraph"
    node_type: EnumNodeType = EnumNodeType.EFFECT
    input_model: str = "ModelMemgraphGraphEffectInput"
    output_model: str = "ModelMemgraphGraphEffectOutput"
    config_model: str = "ModelMemgraphGraphEffectConfig"
    
    subcontracts: dict = Field(default={
        "input": "./subcontracts/input_subcontract.yaml",
        "output": "./subcontracts/output_subcontract.yaml",
        "config": "./subcontracts/config_subcontract.yaml",
    })
    
    capabilities: List[str] = Field(default=['Create_Node', 'Create_Relationship', 'Query_Graph', 'Delete_Node'])
    performance_requirements: dict = Field(default={
        "max_latency_ms": 10000,
        "max_memory_mb": 1024,
        "min_throughput_per_second": 50,
    })
    
    def validate_node_specific_config(self) -> None:
        pass
