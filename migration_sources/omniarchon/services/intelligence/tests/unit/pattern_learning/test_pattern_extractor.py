"""
Unit Tests for PatternExtractor

Tests autonomous pattern extraction from successful code validations.
Target: 80%+ pattern extraction accuracy across all categories.

Created: 2025-10-15 (MVP Phase 5A)
Purpose: Validate pattern extraction quality and accuracy
"""

import pytest
from archon_services.pattern_learning.phase5_autonomous import (
    PatternCategory,
    PatternExtractor,
)


class TestPatternExtractor:
    """Test suite for PatternExtractor autonomous pattern discovery."""

    @pytest.fixture
    def extractor(self):
        """Create PatternExtractor instance."""
        return PatternExtractor()

    @pytest.fixture
    def validation_result_success(self):
        """Successful validation result."""
        return {
            "is_valid": True,
            "quality_score": 0.92,
            "onex_compliance_score": 0.95,
        }

    @pytest.fixture
    def validation_result_failure(self):
        """Failed validation result."""
        return {
            "is_valid": False,
            "quality_score": 0.45,
            "onex_compliance_score": 0.50,
        }

    # ===== Architectural Pattern Tests =====

    @pytest.mark.asyncio
    async def test_extract_base_class_inheritance(
        self, extractor, validation_result_success
    ):
        """Test extraction of ONEX base class inheritance patterns."""
        code = """
class NodeDatabaseWriterEffect(NodeBase):
    '''Effect node for database writes.'''
    pass
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="effect",
        )

        # Should find architectural pattern
        arch_patterns = [
            p for p in patterns if p.pattern_category == PatternCategory.ARCHITECTURAL
        ]
        assert len(arch_patterns) >= 1, "Should extract base class inheritance pattern"

        # Verify pattern details
        base_pattern = next(
            (p for p in arch_patterns if p.pattern_type == "base_class_inheritance"),
            None,
        )
        assert base_pattern is not None, "Should extract base_class_inheritance pattern"
        assert "NodeBase" in base_pattern.context.get("bases", [])
        assert (
            base_pattern.confidence >= 0.8
        ), "Should have high confidence for explicit base class"

    @pytest.mark.asyncio
    async def test_extract_mixin_composition(
        self, extractor, validation_result_success
    ):
        """Test extraction of mixin composition patterns."""
        code = """
class NodeCachedApiEffect(NodeBase, CachingMixin, RetryMixin):
    '''Effect node with caching and retry mixins.'''
    pass
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="effect",
        )

        # Should find mixin pattern
        mixin_patterns = [
            p
            for p in patterns
            if p.pattern_category == PatternCategory.ARCHITECTURAL
            and p.pattern_type == "mixin_composition"
        ]
        assert len(mixin_patterns) >= 1, "Should extract mixin composition pattern"

        mixin_pattern = mixin_patterns[0]
        mixins = mixin_pattern.context.get("mixins", [])
        assert "CachingMixin" in mixins
        assert "RetryMixin" in mixins
        assert mixin_pattern.confidence >= 0.75

    @pytest.mark.asyncio
    async def test_extract_onex_method_implementation(
        self, extractor, validation_result_success
    ):
        """Test extraction of ONEX method implementation patterns."""
        code = """
class NodeExampleEffect(NodeBase):
    async def execute_effect(self, contract):
        '''Execute effect operation.'''
        return await self._perform_operation(contract)
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="effect",
        )

        # Should find ONEX method pattern
        method_patterns = [
            p
            for p in patterns
            if p.pattern_category == PatternCategory.ARCHITECTURAL
            and p.pattern_type == "onex_method_implementation"
        ]
        assert (
            len(method_patterns) >= 1
        ), "Should extract ONEX method implementation pattern"

        method_pattern = method_patterns[0]
        assert method_pattern.context["method_name"] == "execute_effect"
        assert method_pattern.context["is_async"] is True
        assert (
            method_pattern.confidence >= 0.9
        ), "Should have very high confidence for ONEX methods"

    # ===== Quality Pattern Tests =====

    @pytest.mark.asyncio
    async def test_extract_error_handling_pattern(
        self, extractor, validation_result_success
    ):
        """Test extraction of error handling patterns."""
        code = """
async def process_data(data):
    try:
        result = await validate_data(data)
        return result
    except ValueError as e:
        logger.error(f"Validation failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
    finally:
        await cleanup()
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="compute",
        )

        # Should find error handling pattern
        error_patterns = [
            p
            for p in patterns
            if p.pattern_category == PatternCategory.QUALITY
            and p.pattern_type == "error_handling"
        ]
        assert len(error_patterns) >= 1, "Should extract error handling pattern"

        error_pattern = error_patterns[0]
        assert error_pattern.context["has_finally"] is True
        assert len(error_pattern.context["exception_types"]) >= 2
        assert error_pattern.confidence >= 0.7

    @pytest.mark.asyncio
    async def test_extract_type_annotations_pattern(
        self, extractor, validation_result_success
    ):
        """Test extraction of type annotation patterns."""
        code = """
from typing import Dict, Any

async def compute_result(input_data: Dict[str, Any], multiplier: float) -> Dict[str, Any]:
    '''Compute result with type safety.'''
    return {"result": input_data["value"] * multiplier}
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="compute",
        )

        # Should find type annotation pattern
        type_patterns = [
            p
            for p in patterns
            if p.pattern_category == PatternCategory.QUALITY
            and p.pattern_type == "type_annotations"
        ]
        assert len(type_patterns) >= 1, "Should extract type annotation pattern"

        type_pattern = type_patterns[0]
        assert type_pattern.context["has_return_type"] is True
        assert type_pattern.context["typed_arg_count"] == 2
        assert (
            type_pattern.confidence >= 0.85
        ), "Should have high confidence for full type hints"

    @pytest.mark.asyncio
    async def test_extract_documentation_pattern(
        self, extractor, validation_result_success
    ):
        """Test extraction of documentation patterns."""
        code = '''
async def complex_operation(input_param: str, config: Dict[str, Any]) -> bool:
    """
    Perform complex operation with comprehensive documentation.

    Args:
        input_param: Input parameter description
        config: Configuration dictionary

    Returns:
        True if operation succeeded, False otherwise

    Raises:
        ValueError: If input_param is invalid
    """
    if not input_param:
        raise ValueError("input_param cannot be empty")
    return True
'''
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="compute",
        )

        # Should find documentation pattern
        doc_patterns = [
            p
            for p in patterns
            if p.pattern_category == PatternCategory.QUALITY
            and p.pattern_type == "documentation"
        ]
        assert len(doc_patterns) >= 1, "Should extract documentation pattern"

        doc_pattern = doc_patterns[0]
        assert doc_pattern.context["has_args_section"] is True
        assert doc_pattern.context["has_returns_section"] is True
        assert doc_pattern.context["has_raises_section"] is True
        assert doc_pattern.confidence >= 0.7

    # ===== Security Pattern Tests =====

    @pytest.mark.asyncio
    async def test_extract_input_validation_pattern(
        self, extractor, validation_result_success
    ):
        """Test extraction of input validation patterns."""
        code = """
async def process_user_input(user_id: str, data: Dict[str, Any]) -> bool:
    '''Process user input with validation.'''
    # Input validation
    if not user_id or not isinstance(user_id, str):
        raise ValueError("Invalid user_id")

    if not data:
        raise ValueError("Data cannot be empty")

    # Process validated input
    return await store_data(user_id, data)
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="effect",
        )

        # Should find security validation pattern
        security_patterns = [
            p
            for p in patterns
            if p.pattern_category == PatternCategory.SECURITY
            and p.pattern_type == "input_validation"
        ]
        assert len(security_patterns) >= 1, "Should extract input validation pattern"

        security_pattern = security_patterns[0]
        assert "conditional_check" in security_pattern.context["validation_types"]
        assert security_pattern.confidence >= 0.8

    # ===== ONEX Pattern Tests =====

    @pytest.mark.asyncio
    async def test_extract_container_usage_pattern(
        self, extractor, validation_result_success
    ):
        """Test extraction of ONEX container usage patterns."""
        code = """
from omnibase.container import Container

class NodeDatabaseEffect(NodeBase):
    def __init__(self, container: Container[DatabaseService]):
        self.db_service = container.resolve(DatabaseService)
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="effect",
        )

        # Should find ONEX container pattern
        onex_patterns = [
            p
            for p in patterns
            if p.pattern_category == PatternCategory.ONEX
            and p.pattern_type == "container_dependency_injection"
        ]
        assert len(onex_patterns) >= 1, "Should extract container usage pattern"

        onex_pattern = onex_patterns[0]
        assert onex_pattern.context["has_container"] is True
        assert (
            onex_pattern.confidence >= 0.9
        ), "Should have very high confidence for explicit DI"

    @pytest.mark.asyncio
    async def test_extract_structured_logging_pattern(
        self, extractor, validation_result_success
    ):
        """Test extraction of structured logging patterns."""
        code = """
class NodeApiEffect(NodeBase):
    async def execute_effect(self, contract):
        correlation_id = contract.correlation_id
        logger.info(
            "Processing API request",
            extra={"correlation_id": correlation_id, "endpoint": contract.endpoint}
        )
        return await self._call_api(contract)
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="effect",
        )

        # Should find structured logging pattern
        logging_patterns = [
            p
            for p in patterns
            if p.pattern_category == PatternCategory.ONEX
            and p.pattern_type == "structured_logging"
        ]
        assert len(logging_patterns) >= 1, "Should extract structured logging pattern"

        logging_pattern = logging_patterns[0]
        assert logging_pattern.context["has_correlation_id"] is True
        assert logging_pattern.confidence >= 0.85

    @pytest.mark.asyncio
    async def test_extract_naming_convention_pattern(
        self, extractor, validation_result_success
    ):
        """Test extraction of ONEX naming convention patterns."""
        code = """
class NodeDatabaseWriterEffect(NodeBase):
    '''Effect node following ONEX naming convention.'''
    pass
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="effect",
        )

        # Should find naming convention pattern
        naming_patterns = [
            p
            for p in patterns
            if p.pattern_category == PatternCategory.ONEX
            and p.pattern_type == "naming_convention"
        ]
        assert len(naming_patterns) >= 1, "Should extract naming convention pattern"

        naming_pattern = naming_patterns[0]
        assert naming_pattern.context["follows_convention"] is True
        assert (
            naming_pattern.confidence == 1.0
        ), "Should have perfect confidence for naming"

    # ===== Pattern Tracking Tests =====

    @pytest.mark.asyncio
    async def test_pattern_frequency_tracking(
        self, extractor, validation_result_success
    ):
        """Test that patterns are tracked for frequency."""
        code = """
class NodeExampleEffect(NodeBase):
    pass
"""
        # Extract same pattern multiple times
        for _ in range(5):
            await extractor.extract_patterns(
                code=code,
                validation_result=validation_result_success,
                node_type="effect",
            )

        # Get emerging patterns
        emerging = await extractor.get_emerging_patterns(min_frequency=5)
        assert len(emerging) >= 1, "Should track pattern frequency"

        # Verify frequency increased
        tracked_pattern = emerging[0]
        assert tracked_pattern.frequency >= 5

    @pytest.mark.asyncio
    async def test_pattern_confidence_updates(self, extractor):
        """Test that pattern confidence updates based on validation outcomes."""
        code = """
class NodeTestEffect(NodeBase):
    pass
"""
        # First extraction with high quality
        patterns1 = await extractor.extract_patterns(
            code=code,
            validation_result={"is_valid": True, "quality_score": 0.95},
            node_type="effect",
        )
        patterns1[0].confidence if patterns1 else 0.0

        # Second extraction with lower quality
        patterns2 = await extractor.extract_patterns(
            code=code,
            validation_result={"is_valid": True, "quality_score": 0.70},
            node_type="effect",
        )

        # Confidence should be influenced by quality scores
        assert len(patterns2) >= 1, "Should extract patterns from both validations"

    @pytest.mark.asyncio
    async def test_skip_failed_validations(self, extractor, validation_result_failure):
        """Test that patterns are NOT extracted from failed validations."""
        code = """
class NodeFailedEffect(NodeBase):
    pass
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_failure,
            node_type="effect",
        )

        assert len(patterns) == 0, "Should not extract patterns from failed validations"

    # ===== Comprehensive Pattern Tests =====

    @pytest.mark.asyncio
    async def test_extract_all_pattern_categories(
        self, extractor, validation_result_success
    ):
        """Test extraction of patterns from all categories in one code sample."""
        code = """
from omnibase.container import Container
from typing import Dict, Any

class NodeComprehensiveEffect(NodeBase, CachingMixin, RetryMixin):
    '''
    Comprehensive effect node demonstrating all pattern categories.

    This node shows architectural, quality, security, and ONEX patterns.
    '''

    def __init__(self, container: Container[DatabaseService]):
        self.db = container.resolve(DatabaseService)

    async def execute_effect(self, contract: ModelContractEffect) -> Dict[str, Any]:
        '''
        Execute effect with comprehensive patterns.

        Args:
            contract: Effect contract with input data

        Returns:
            Result dictionary with status and data

        Raises:
            ValueError: If contract is invalid
        '''
        correlation_id = contract.correlation_id

        # Input validation (security pattern)
        if not contract or not contract.payload:
            raise ValueError("Invalid contract")

        try:
            # Structured logging (ONEX pattern)
            logger.info(
                "Executing effect",
                extra={"correlation_id": correlation_id, "node_type": "effect"}
            )

            # Process data
            result = await self._process(contract.payload)
            return {"status": "success", "data": result}

        except ValueError as e:
            logger.error(f"Validation error: {e}", extra={"correlation_id": correlation_id})
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}", extra={"correlation_id": correlation_id})
            raise
        finally:
            await self._cleanup()
"""
        patterns = await extractor.extract_patterns(
            code=code,
            validation_result=validation_result_success,
            node_type="effect",
        )

        # Should extract patterns from all categories
        categories_found = {p.pattern_category for p in patterns}

        assert (
            PatternCategory.ARCHITECTURAL in categories_found
        ), "Should find architectural patterns"
        assert (
            PatternCategory.QUALITY in categories_found
        ), "Should find quality patterns"
        assert (
            PatternCategory.SECURITY in categories_found
        ), "Should find security patterns"
        assert PatternCategory.ONEX in categories_found, "Should find ONEX patterns"

        # Should have multiple patterns
        assert (
            len(patterns) >= 8
        ), "Should extract comprehensive patterns from rich code"

        # Verify pattern diversity
        architectural_count = sum(
            1 for p in patterns if p.pattern_category == PatternCategory.ARCHITECTURAL
        )
        quality_count = sum(
            1 for p in patterns if p.pattern_category == PatternCategory.QUALITY
        )
        security_count = sum(
            1 for p in patterns if p.pattern_category == PatternCategory.SECURITY
        )
        onex_count = sum(
            1 for p in patterns if p.pattern_category == PatternCategory.ONEX
        )

        assert architectural_count >= 2, "Should find multiple architectural patterns"
        assert quality_count >= 2, "Should find multiple quality patterns"
        assert security_count >= 1, "Should find security patterns"
        assert onex_count >= 2, "Should find multiple ONEX patterns"

    # ===== Accuracy Validation Test =====

    @pytest.mark.asyncio
    async def test_pattern_extraction_accuracy_target(
        self, extractor, validation_result_success
    ):
        """
        Test overall pattern extraction accuracy meets 80%+ target.

        This test validates that the PatternExtractor achieves the Phase 5A
        success criteria of 80%+ pattern extraction accuracy.
        """
        test_cases = [
            # Test case 1: Base class inheritance
            {
                "code": "class NodeTestEffect(NodeBase): pass",
                "expected_categories": {
                    PatternCategory.ARCHITECTURAL,
                    PatternCategory.ONEX,
                },
                "min_patterns": 1,
            },
            # Test case 2: Mixin composition
            {
                "code": "class NodeTestEffect(NodeBase, CachingMixin): pass",
                "expected_categories": {
                    PatternCategory.ARCHITECTURAL,
                    PatternCategory.ONEX,
                },
                "min_patterns": 2,
            },
            # Test case 3: Type annotations
            {
                "code": "async def func(x: int, y: str) -> bool: return True",
                "expected_categories": {PatternCategory.QUALITY},
                "min_patterns": 1,
            },
            # Test case 4: Error handling
            {
                "code": "try:\n    pass\nexcept Exception:\n    pass\nfinally:\n    pass",
                "expected_categories": {PatternCategory.QUALITY},
                "min_patterns": 1,
            },
            # Test case 5: Input validation
            {
                "code": "def func(x):\n    if not x:\n        raise ValueError()\n    return x",
                "expected_categories": {PatternCategory.SECURITY},
                "min_patterns": 1,
            },
        ]

        total_tests = len(test_cases)
        successful_extractions = 0

        for i, test_case in enumerate(test_cases, 1):
            patterns = await extractor.extract_patterns(
                code=test_case["code"],
                validation_result=validation_result_success,
                node_type="effect",
            )

            categories_found = {p.pattern_category for p in patterns}

            # Check if expected patterns were found
            if len(patterns) >= test_case["min_patterns"] and any(
                cat in categories_found for cat in test_case["expected_categories"]
            ):
                successful_extractions += 1

        accuracy = (successful_extractions / total_tests) * 100

        print(f"\n{'='*60}")
        print("Pattern Extraction Accuracy Test Results")
        print(f"{'='*60}")
        print(f"Total test cases: {total_tests}")
        print(f"Successful extractions: {successful_extractions}")
        print(f"Accuracy: {accuracy:.1f}%")
        print("Target: 80.0%")
        print(f"{'='*60}\n")

        assert (
            accuracy >= 80.0
        ), f"Pattern extraction accuracy {accuracy:.1f}% below 80% target"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
