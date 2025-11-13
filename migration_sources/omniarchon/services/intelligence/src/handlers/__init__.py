"""Event handlers for intelligence services."""

from uuid import UUID, uuid4

from src.handlers.base_response_publisher import BaseResponsePublisher

# Import handlers lazily to avoid circular dependencies and missing dependencies
__all__ = [
    "BaseResponsePublisher",
    "CodegenValidationHandler",
    "CodegenAnalysisHandler",
    "CodegenPatternHandler",
    "CodegenMixinHandler",
    "PatternTraceabilityHandler",
    "AutonomousLearningHandler",
]


# NOTE: correlation_id support enabled for tracing
def __getattr__(name):
    """Lazy import handlers to avoid dependency issues."""
    if name == "CodegenValidationHandler":
        from .codegen_validation_handler import CodegenValidationHandler

        return CodegenValidationHandler
    elif name == "CodegenAnalysisHandler":
        from .codegen_analysis_handler import CodegenAnalysisHandler

        return CodegenAnalysisHandler
    elif name == "CodegenPatternHandler":
        from .codegen_pattern_handler import CodegenPatternHandler

        return CodegenPatternHandler
    elif name == "CodegenMixinHandler":
        from .codegen_mixin_handler import CodegenMixinHandler

        return CodegenMixinHandler
    elif name == "PatternTraceabilityHandler":
        from .pattern_traceability_handler import PatternTraceabilityHandler

        return PatternTraceabilityHandler
    elif name == "AutonomousLearningHandler":
        from .autonomous_learning_handler import AutonomousLearningHandler

        return AutonomousLearningHandler
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
