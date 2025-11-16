"""
Python Contract for Vectorization Compute Node

This is the main contract defining the node's interface, capabilities, and requirements.
"""

from omnibase_core.models.contracts import ModelContractBase
from omnibase_core.models.versioning import ModelSemVer
from omnibase_core.enums import EnumNodeType
from pydantic import Field
from typing import List, Optional


class VectorizationComputeContract(ModelContractBase):
    """Contract for vectorization compute node."""

    # Core identification
    name: str = "vectorization_compute"
    version: ModelSemVer = ModelSemVer(major=1, minor=0, patch=0)
    description: str = "Compute node for generating embeddings from code and documents"
    node_type: EnumNodeType = EnumNodeType.COMPUTE

    # Model specifications
    input_model: str = "ModelVectorizationComputeInput"
    output_model: str = "ModelVectorizationComputeOutput"
    config_model: str = "ModelVectorizationComputeConfig"

    # Subcontract references
    subcontracts: dict = Field(
        default={
            "input": "./subcontracts/input_subcontract.yaml",
            "output": "./subcontracts/output_subcontract.yaml",
            "config": "./subcontracts/config_subcontract.yaml",
        }
    )

    # Node capabilities
    capabilities: List[str] = Field(
        default=[
            "EMBEDDING_GENERATION",
            "BATCH_VECTORIZATION",
            "MODEL_VALIDATION",
            "CACHING",
        ]
    )

    # Performance requirements
    performance_requirements: dict = Field(
        default={
            "max_latency_ms": 5000,
            "max_memory_mb": 512,
            "min_throughput_per_second": 20,
        }
    )

    # Dependencies
    dependencies: List[str] = Field(
        default=[
            "openai>=1.71.0",
            "sentence-transformers>=4.1.0",
        ]
    )

    # External services
    external_services: List[str] = Field(
        default=["openai_api"]
    )

    def validate_node_specific_config(self) -> None:
        """Validate node-specific configuration."""
        # Compute nodes should have low latency
        if self.performance_requirements.get("max_latency_ms", 0) > 10000:
            raise ValueError("Compute nodes should have max latency < 10s")
