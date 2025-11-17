"""Input model for MemgraphGraph Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID, uuid4

class ModelMemgraphGraphEffectInput(BaseModel):
    """Input model for memgraph_graph operations."""
    operation: str
query: str
parameters: Dict[str, Any]
    correlation_id: UUID = Field(default_factory=uuid4, description="Correlation ID")
