"""Output model for MemgraphGraph Effect Node"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from uuid import UUID

class ModelMemgraphGraphEffectOutput(BaseModel):
    """Output model for memgraph_graph operations."""
    success: bool
results: List[Dict[str, Any]]
    correlation_id: UUID = Field(..., description="Correlation ID")
    processing_time_ms: float = Field(..., description="Processing time in ms", ge=0.0)
