"""
Services package for intelligence service.

This package provides core intelligence services for code generation,
quality assessment, pattern learning, and semantic analysis.
"""

from uuid import UUID, uuid4

# Semantic analysis services
from src.archon_services.langextract import CodegenLangExtractService

# Pattern learning services
from src.archon_services.pattern_learning import CodegenPatternService

# Quality assessment services
from src.archon_services.quality import (
    CodegenQualityService,
    ComprehensiveONEXScorer,
    ONEXQualityScorer,
)

__all__ = [
    # Quality services
    "CodegenQualityService",
    "ComprehensiveONEXScorer",
    "ONEXQualityScorer",
    # Semantic analysis
    "CodegenLangExtractService",
    # Pattern learning
    "CodegenPatternService",
]
