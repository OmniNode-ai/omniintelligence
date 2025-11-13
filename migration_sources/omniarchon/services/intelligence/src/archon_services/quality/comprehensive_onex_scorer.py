"""
Comprehensive ONEX Quality Scorer

Integrates official omnibase_core validation checkers with custom quality scoring.
Uses the actual validation logic from omnibase_core to ensure consistency.

Migrated from: omnibase_3/src/omnibase/tools/intelligence/.../onex_quality_scorer.py
Enhanced with: omnibase_core.validation checkers
Migration Date: 2025-10-14
Purpose: Production-grade code quality and ONEX compliance scoring
"""

import ast
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# Import official ONEX validators with fallback
try:
    from omnibase_core.validation.checker_generic_pattern import GenericPatternChecker
    from omnibase_core.validation.checker_naming_convention import (
        NamingConventionChecker,
    )
    from omnibase_core.validation.checker_pydantic_pattern import PydanticPatternChecker
except ImportError:
    # Fallback checker classes when omnibase_core is not available
    logger.warning(
        "omnibase_core not available - using no-op checkers. "
        "ONEX validation will be skipped. Quality scores may be misleading."
    )

    class FallbackChecker(ast.NodeVisitor):
        """Fallback checker that marks validation as skipped when omnibase_core is not available"""

        def __init__(self, file_path: str):
            self.file_path = file_path
            self.issues: List[str] = [
                "ONEX_VALIDATION_SKIPPED: omnibase_core unavailable - quality scores are unreliable"
            ]

    GenericPatternChecker = FallbackChecker
    NamingConventionChecker = FallbackChecker
    PydanticPatternChecker = FallbackChecker


class ComprehensiveONEXScorer:
    """
    Comprehensive ONEX quality scorer using official omnibase_core validators.

    Combines:
    1. Official omnibase_core validation checkers
    2. Custom quality scoring logic
    3. Temporal relevance analysis
    4. Architectural era detection
    """

    def __init__(self):
        # Critical legacy patterns (auto-reject: score = 0.0)
        self.critical_legacy_patterns = [
            r"from\s+typing\s+import\s+.*\bAny\b",  # Any types usage from typing
            r":\s*Any\b",  # Any type annotations
            r"class\s+[a-z]\w*\([^)]*BaseModel[^)]*\):",  # Non-CamelCase Pydantic models
            r"\b(Database|Connection|Client)\(\)",  # Direct instantiation of services
            # Pydantic v1 legacy patterns (CRITICAL)
            r"\.dict\s*\(",  # .dict() -> .model_dump()
            r"\.json\s*\(",  # .json() -> .model_dump_json()
            r"\.copy\s*\(",  # .copy() -> .model_copy()
            r"\.schema\s*\(",  # .schema() -> .model_json_schema()
        ]

        # Moderate legacy patterns (score = 0.3-0.6)
        self.moderate_legacy_patterns = [
            r"class\s+[a-z]\w*:",  # Non-CamelCase class names
            r"def\s+\w+\([^)]*\)\s*:\s*\n\s*\w+\s*=\s*\w+\(",  # Direct instantiation in functions
            r"import\s+os",  # Direct OS imports (should use container)
            r"from\s+\.\.+\w+\s+import",  # Multi-level relative imports (.. or ...)
            r"@validator\s*\(",  # Legacy @validator decorator
            r"@root_validator\s*\(",  # Legacy @root_validator decorator
        ]

        # Modern ONEX patterns (score = 0.8-1.0)
        self.modern_onex_patterns = [
            r"def\s+__init__\(self,\s*registry:\s*\w+Registry\)",  # Registry injection
            r"class\s+Model[A-Z]\w*\(BaseModel\)",  # CamelCase Pydantic models
            r"from\s+omnibase\.protocols",  # Protocol usage
            r"@standard_error_handling",  # Proper error handling
            r"NodeBase",  # NodeBase integration
            r"OnexError",  # Proper exception handling
            r"contract_path\s*=\s*Path",  # Contract-driven patterns
            r"emit_log_event",  # ONEX logging
            r"ModelONEXContainer",  # Correct container class
            r"CoreErrorCode",  # Error code enum
            r"Node(Effect|Compute|Transform|Input|Output)",  # Node types
            r"\.model_dump\s*\(",  # Pydantic v2 .model_dump()
            r"\.model_dump_json\s*\(",  # Pydantic v2 .model_dump_json()
            r"\.model_copy\s*\(",  # Pydantic v2 .model_copy()
            r"@field_validator\s*\(",  # Pydantic v2 @field_validator
            r"@model_validator\s*\(",  # Pydantic v2 @model_validator
        ]

        # Architectural era indicators
        self.architectural_eras = {
            "pre_nodebase": [
                r"class\s+\w+Tool:",
                r"def\s+main\(\):\s*parser",
                r"argparse",
            ],
            "early_nodebase": [
                r"NodeBase\(",
                r"class\s+\w+\(NodeBase\)",
                r"__main__.*NodeBase",
            ],
            "contract_driven": [
                r"contract\.yaml",
                r"from_contract",
                r"CONTRACT_FILENAME",
            ],
            "modern_onex": [
                r"registry:\s*BaseOnexRegistry",
                r"container:\s*ModelONEXContainer",
                r"@standard_error_handling",
                r"ProtocolToolBase",
                r"emit_log_event",
                r"Model[A-Z]\w+",
                r"\.model_dump\(",  # Pydantic v2
            ],
        }

    def analyze_content(
        self,
        content: str,
        file_path: Optional[str] = None,
        file_last_modified: Optional[datetime] = None,
        git_commit_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Analyze content and return comprehensive quality metrics.

        Uses official omnibase_core validators plus custom quality scoring.
        """

        # Run official omnibase_core validators
        omnibase_violations = self._run_omnibase_validators(
            content, file_path or "temp.py"
        )

        # Calculate ONEX compliance score (with validator input)
        onex_compliance_score = self._calculate_onex_compliance(
            content, omnibase_violations
        )

        # Calculate temporal relevance score
        relevance_score = self._calculate_temporal_relevance(
            file_last_modified, git_commit_date
        )

        # Detect architectural era
        architectural_era = self._detect_architectural_era(content)

        # Detect legacy indicators
        legacy_indicators = self._detect_legacy_indicators(content)

        # Check if validation was skipped
        validation_skipped = any(
            "ONEX_VALIDATION_SKIPPED" in v for v in omnibase_violations
        )

        # Add omnibase violations to legacy indicators
        if omnibase_violations:
            legacy_indicators.extend(
                [f"ONEX Validator: {v}" for v in omnibase_violations[:5]]
            )

        # Calculate overall quality score
        quality_score = self._calculate_overall_quality(
            onex_compliance_score, relevance_score, architectural_era, legacy_indicators
        )

        return {
            "quality_score": quality_score,
            "relevance_score": relevance_score,
            "onex_compliance_score": onex_compliance_score,
            "architectural_era": architectural_era,
            "legacy_indicators": legacy_indicators,
            "omnibase_violations": omnibase_violations,
            "validation_skipped": validation_skipped,
            "file_last_modified": file_last_modified,
            "git_commit_date": git_commit_date,
        }

    def _run_omnibase_validators(self, content: str, file_path: str) -> List[str]:
        """Run official omnibase_core validation checkers."""
        violations = []

        try:
            tree = ast.parse(content, filename=file_path)

            # Run Pydantic pattern checker
            pydantic_checker = PydanticPatternChecker(file_path)
            pydantic_checker.visit(tree)
            violations.extend(pydantic_checker.issues)

            # Run naming convention checker
            naming_checker = NamingConventionChecker(file_path)
            naming_checker.visit(tree)
            violations.extend(naming_checker.issues)

            # Run generic pattern checker
            generic_checker = GenericPatternChecker(file_path)
            generic_checker.visit(tree)
            violations.extend(generic_checker.issues)

        except SyntaxError:
            violations.append("Syntax error in code")
        except Exception as e:
            violations.append(f"Validation error: {str(e)}")

        return violations

    def _calculate_onex_compliance(
        self, content: str, omnibase_violations: List[str]
    ) -> float:
        """Calculate ONEX architectural compliance score (0.0-1.0)."""
        # Check for critical legacy patterns first (auto-fail regardless of validation status)
        for pattern in self.critical_legacy_patterns:
            if re.search(pattern, content, re.MULTILINE):
                return 0.0  # Critical failure

        # Check if validation was skipped (omnibase_core unavailable)
        validation_skipped = any(
            "ONEX_VALIDATION_SKIPPED" in v for v in omnibase_violations
        )

        if validation_skipped:
            # Return low score (0.3) to indicate unreliable validation
            # Not 0.0 since we don't know if code is actually bad
            # Not 0.5 since we want to signal uncertainty/untrustworthiness
            return 0.3

        score = 0.5  # Start with neutral score

        # Deduct for moderate legacy patterns
        legacy_penalty = 0.0
        for pattern in self.moderate_legacy_patterns:
            matches = len(re.findall(pattern, content, re.MULTILINE))
            legacy_penalty += matches * 0.1  # 0.1 penalty per match

        # Add points for modern ONEX patterns
        modern_bonus = 0.0
        for pattern in self.modern_onex_patterns:
            matches = len(re.findall(pattern, content, re.MULTILINE))
            modern_bonus += matches * 0.1  # 0.1 bonus per match

        # Penalty for omnibase validator violations
        validator_penalty = (
            len(omnibase_violations) * 0.05
        )  # 0.05 penalty per violation

        # Calculate final score
        final_score = score - legacy_penalty + modern_bonus - validator_penalty
        return max(0.0, min(1.0, final_score))

    def _calculate_temporal_relevance(
        self,
        file_last_modified: Optional[datetime],
        git_commit_date: Optional[datetime],
    ) -> float:
        """Calculate temporal relevance score (0.0-1.0) based on recency."""
        now = datetime.now(timezone.utc)

        # Use the most recent timestamp available
        reference_date = None
        if git_commit_date:
            reference_date = git_commit_date
        elif file_last_modified:
            reference_date = file_last_modified
        else:
            return 0.5  # Neutral score if no temporal data

        # Ensure timezone awareness
        if reference_date.tzinfo is None:
            reference_date = reference_date.replace(tzinfo=timezone.utc)

        # Calculate days since last modification
        days_old = (now - reference_date).days

        # Scoring function: exponential decay
        if days_old <= 30:
            return 1.0
        elif days_old <= 90:
            return 0.9
        elif days_old <= 180:
            return 0.7
        elif days_old <= 365:
            return 0.5
        else:
            return 0.3

    def _detect_architectural_era(self, content: str) -> str:
        """Detect which ONEX architectural era the content belongs to."""
        era_scores = {}

        for era, patterns in self.architectural_eras.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, content, re.MULTILINE))
                score += matches
            era_scores[era] = score

        # Return era with highest score, default to modern if no clear match
        if not any(era_scores.values()):
            return "modern_onex"

        return max(era_scores.items(), key=lambda x: x[1])[0]

    def _detect_legacy_indicators(self, content: str) -> List[str]:
        """Detect specific legacy patterns in the content."""
        indicators = []

        # Map patterns to human-readable descriptions
        pattern_descriptions = {
            r"from\s+typing\s+import\s+.*\bAny\b": "Uses Any types (forbidden in ONEX)",
            r":\s*Any\b": "Uses Any type annotations (forbidden in ONEX)",
            r"class\s+[a-z]\w*\([^)]*BaseModel[^)]*\):": "Non-CamelCase Pydantic models (should be Model* prefix)",
            r"\b(Database|Connection|Client)\(\)": "Direct instantiation without container",
            r"class\s+[a-z]\w*:": "Non-CamelCase class names",
            r"import\s+os": "Direct OS imports (should use container)",
            r"\.dict\s*\(": "Legacy Pydantic v1 .dict() method (use .model_dump())",
            r"\.json\s*\(": "Legacy Pydantic v1 .json() method (use .model_dump_json())",
            r"\.copy\s*\(": "Legacy Pydantic v1 .copy() method (use .model_copy())",
            r"@validator\s*\(": "Legacy @validator decorator (use @field_validator)",
            r"@root_validator\s*\(": "Legacy @root_validator decorator (use @model_validator)",
            r"from\s+\.\.+\w+\s+import": "Multi-level relative imports (use absolute imports)",
        }

        for pattern, description in pattern_descriptions.items():
            if re.search(pattern, content, re.MULTILINE):
                indicators.append(description)

        return indicators

    def _calculate_overall_quality(
        self,
        onex_compliance_score: float,
        relevance_score: float,
        architectural_era: str,
        legacy_indicators: List[str],
    ) -> float:
        """Calculate weighted overall quality score."""

        # Weighted average: compliance (60%), relevance (30%), era bonus (10%)
        base_score = (onex_compliance_score * 0.6) + (relevance_score * 0.3)

        # Architectural era bonus/penalty
        era_modifiers = {
            "pre_nodebase": -0.2,
            "early_nodebase": -0.1,
            "contract_driven": 0.05,
            "modern_onex": 0.1,
        }

        era_modifier = era_modifiers.get(architectural_era, 0)
        final_score = base_score + (era_modifier * 0.1)

        # Heavy penalty for critical legacy indicators
        if any("forbidden" in indicator.lower() for indicator in legacy_indicators):
            final_score *= 0.1  # 90% penalty for forbidden patterns

        return max(0.0, min(1.0, final_score))
