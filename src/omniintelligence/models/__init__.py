"""Top-level models for OmniIntelligence.

These models are shared across multiple nodes and provide common
data structures for intelligence operations.
"""
from omniintelligence.models.model_intelligence_input import ModelIntelligenceInput
from omniintelligence.models.model_intelligence_output import ModelIntelligenceOutput

__all__ = ["ModelIntelligenceInput", "ModelIntelligenceOutput"]
