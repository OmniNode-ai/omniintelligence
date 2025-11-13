"""
Codegen Quality Service

Event-driven wrapper for ONEX quality scoring and code validation.
Integrates with CodegenValidationHandler for event processing.

Created: 2025-10-14
Updated: 2025-10-14 - Integrated ComprehensiveONEXScorer with omnibase_core validators
Purpose: Quality validation for autonomous code generation
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from src.archon_services.quality.comprehensive_onex_scorer import (
    ComprehensiveONEXScorer,
)
from src.archon_services.quality.suggestion_generator import QualitySuggestionGenerator

logger = logging.getLogger(__name__)


class CodegenQualityService:
    """
    Event-driven wrapper for ONEX quality scoring and validation.

    Now uses ComprehensiveONEXScorer with official omnibase_core validators.
    """

    def __init__(
        self,
        quality_scorer: Optional[ComprehensiveONEXScorer] = None,
        suggestion_generator: Optional[QualitySuggestionGenerator] = None,
    ):
        """
        Initialize Codegen Quality Service.

        Args:
            quality_scorer: Optional ComprehensiveONEXScorer instance (creates new if None)
                          Can also accept ONEXQualityScorer for backward compatibility
            suggestion_generator: Optional QualitySuggestionGenerator instance
        """
        self.quality_scorer = quality_scorer or ComprehensiveONEXScorer()
        self.suggestion_generator = suggestion_generator or QualitySuggestionGenerator()

    async def validate_generated_code(
        self,
        code_content: str,
        node_type: str,
        file_path: Optional[str] = None,
        contracts: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Validate generated code for quality and ONEX compliance.

        This is the main entry point called by CodegenValidationHandler.

        Args:
            code_content: Generated code content to validate
            node_type: Type of node (effect, compute, reducer, orchestrator)
            file_path: Optional file path for context
            contracts: Optional contract definitions for validation

        Returns:
            Validation result dictionary with:
            {
                "quality_score": float (0.0-1.0),
                "onex_compliance_score": float (0.0-1.0),
                "violations": List[str],
                "warnings": List[str],
                "suggestions": List[str],
                "is_valid": bool,
                "architectural_era": str,
                "details": Dict[str, Any]
            }
        """
        try:
            # Run ONEX quality analysis
            analysis_result = self.quality_scorer.analyze_content(
                content=code_content,
                file_path=file_path,
                file_last_modified=datetime.now(
                    timezone.utc
                ),  # Current timestamp for generated code
            )

            # Extract scores and indicators
            quality_score = analysis_result["quality_score"]
            onex_compliance_score = analysis_result["onex_compliance_score"]
            legacy_indicators = analysis_result["legacy_indicators"]
            architectural_era = analysis_result["architectural_era"]
            omnibase_violations = analysis_result.get("omnibase_violations", [])

            # Classify issues by severity
            violations = self._extract_violations(
                legacy_indicators, omnibase_violations
            )
            warnings = self._extract_warnings(legacy_indicators, architectural_era)

            # Generate intelligent suggestions using QualitySuggestionGenerator
            suggestions = await self._generate_intelligent_suggestions(
                code_content=code_content,
                node_type=node_type,
                quality_score=quality_score,
                onex_compliance_score=onex_compliance_score,
                violations=violations,
                warnings=warnings,
            )

            # Determine if code is valid (meets minimum thresholds)
            is_valid = self._determine_validity(
                quality_score, onex_compliance_score, violations
            )

            return {
                "quality_score": quality_score,
                "onex_compliance_score": onex_compliance_score,
                "violations": violations,
                "warnings": warnings,
                "suggestions": suggestions,
                "is_valid": is_valid,
                "architectural_era": architectural_era,
                "details": {
                    "relevance_score": analysis_result["relevance_score"],
                    "legacy_indicators": legacy_indicators,
                    "omnibase_violations": omnibase_violations,
                    "node_type": node_type,
                    "validation_timestamp": datetime.now(timezone.utc).isoformat(),
                    "validator_source": "ComprehensiveONEXScorer + omnibase_core",
                },
            }

        except Exception as e:
            logger.error(f"Code validation failed: {e}", exc_info=True)
            return {
                "quality_score": 0.0,
                "onex_compliance_score": 0.0,
                "violations": [f"Validation error: {str(e)}"],
                "warnings": [],
                "suggestions": [],
                "is_valid": False,
                "architectural_era": "unknown",
                "details": {"error": str(e)},
            }

    def _extract_violations(
        self, legacy_indicators: List[str], omnibase_violations: List[str]
    ) -> List[str]:
        """
        Extract critical violations from legacy indicators and omnibase validators.

        Violations are blocking issues that should fail validation.
        """
        violations = []

        # Critical patterns that are forbidden
        forbidden_keywords = ["forbidden", "should not", "must not"]

        for indicator in legacy_indicators:
            if any(keyword in indicator.lower() for keyword in forbidden_keywords):
                violations.append(f"CRITICAL: {indicator}")

        # Add omnibase validator violations (from official omnibase_core)
        for violation in omnibase_violations:
            violations.append(f"ONEX VALIDATOR: {violation}")

        return violations

    def _extract_warnings(
        self, legacy_indicators: List[str], architectural_era: str
    ) -> List[str]:
        """
        Extract non-blocking warnings from analysis.

        Warnings are issues that should be addressed but don't block validation.
        """
        warnings = []

        # Legacy indicators that aren't critical violations
        for indicator in legacy_indicators:
            if not any(
                keyword in indicator.lower()
                for keyword in ["forbidden", "should not", "must not"]
            ):
                warnings.append(indicator)

        # Era-based warnings
        if architectural_era in ["pre_nodebase", "early_nodebase"]:
            warnings.append(
                f"Code uses outdated architectural patterns ({architectural_era})"
            )

        return warnings

    async def _generate_intelligent_suggestions(
        self,
        code_content: str,
        node_type: str,
        quality_score: float,
        onex_compliance_score: float,
        violations: List[str],
        warnings: List[str],
    ) -> List[str]:
        """
        Generate intelligent, actionable suggestions using QualitySuggestionGenerator.

        Returns list of formatted suggestion strings for backward compatibility.
        """
        # Create validation result dict for generator
        validation_result = {
            "quality_score": quality_score,
            "onex_compliance_score": onex_compliance_score,
            "violations": violations,
            "warnings": warnings,
        }

        # Generate sophisticated suggestions
        suggestion_objects = await self.suggestion_generator.generate_suggestions(
            validation_result=validation_result,
            code=code_content,
            node_type=node_type,
        )

        # Format suggestions as strings for backward compatibility
        formatted_suggestions = []
        for suggestion in suggestion_objects[:10]:  # Limit to top 10 suggestions
            # Format: [PRIORITY:X] [TYPE] Title - Description
            suggestion_text = (
                f"[PRIORITY:{suggestion['priority']}] "
                f"[{suggestion['type'].upper()}] "
                f"{suggestion['title']}"
            )

            # Add code example if available
            if suggestion.get("code_example"):
                suggestion_text += f"\n{suggestion['description']}\n\nExample:\n{suggestion['code_example']}"
            else:
                suggestion_text += f" - {suggestion['description']}"

            formatted_suggestions.append(suggestion_text)

        return formatted_suggestions

    def _determine_validity(
        self, quality_score: float, onex_compliance_score: float, violations: List[str]
    ) -> bool:
        """
        Determine if generated code is valid.

        Validation criteria:
        - No critical violations
        - Quality score >= 0.7 (acceptable threshold)
        - ONEX compliance score >= 0.6 (minimum compliance)
        """
        # Critical violations always fail validation
        if violations:
            return False

        # Check score thresholds
        if quality_score < 0.7:
            return False

        if onex_compliance_score < 0.6:
            return False

        return True

    async def get_validation_report(
        self, validation_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate aggregate validation report from multiple validation results.

        Args:
            validation_results: List of validation result dictionaries

        Returns:
            Aggregate report with statistics and recommendations
        """
        if not validation_results:
            return {
                "total_validations": 0,
                "success_rate": 0.0,
                "average_quality_score": 0.0,
                "average_compliance_score": 0.0,
                "total_violations": 0,
                "total_warnings": 0,
            }

        total = len(validation_results)
        valid_count = sum(1 for r in validation_results if r.get("is_valid", False))

        avg_quality = (
            sum(r.get("quality_score", 0.0) for r in validation_results) / total
        )
        avg_compliance = (
            sum(r.get("onex_compliance_score", 0.0) for r in validation_results) / total
        )

        total_violations = sum(len(r.get("violations", [])) for r in validation_results)
        total_warnings = sum(len(r.get("warnings", [])) for r in validation_results)

        return {
            "total_validations": total,
            "success_rate": valid_count / total if total > 0 else 0.0,
            "average_quality_score": avg_quality,
            "average_compliance_score": avg_compliance,
            "total_violations": total_violations,
            "total_warnings": total_warnings,
            "report_timestamp": datetime.now(timezone.utc).isoformat(),
        }
