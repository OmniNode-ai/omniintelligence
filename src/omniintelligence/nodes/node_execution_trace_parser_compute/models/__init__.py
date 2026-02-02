"""Models for Execution Trace Parser Compute Node.

All models use strong typing with Pydantic BaseModel for type safety.
"""

from omniintelligence.nodes.node_execution_trace_parser_compute.models.model_trace_parsing_input import (
    ModelTraceData,
    ModelTraceLog,
    ModelTraceParsingInput,
)
from omniintelligence.nodes.node_execution_trace_parser_compute.models.model_trace_parsing_output import (
    ModelErrorEvent,
    ModelParsedEvent,
    ModelTimingData,
    ModelTraceMetadata,
    ModelTraceParsingOutput,
)

__all__ = [
    "ModelErrorEvent",
    "ModelParsedEvent",
    "ModelTimingData",
    "ModelTraceData",
    "ModelTraceLog",
    "ModelTraceMetadata",
    "ModelTraceParsingInput",
    "ModelTraceParsingOutput",
]
