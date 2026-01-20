"""Model Type Safety Audit Tests.

This module verifies that all models comply with ONEX type safety standards:
- No `Any` types in contract-facing models
- No `dict[str, Any]` in input/output models
- All validators fire correctly including edge cases
- Documentation matches actual enum values
- Proper range validation for score fields
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path
from typing import Any, get_type_hints

import pytest


# Model files to audit
MODEL_FILES = [
    "src/omniintelligence/nodes/context_keyword_extractor_compute/models/model_keyword_extraction_output.py",
    "src/omniintelligence/nodes/intelligence_reducer/models/model_reducer_input.py",
    "src/omniintelligence/nodes/intent_classifier_compute/models/model_intent_classification_input.py",
    "src/omniintelligence/nodes/pattern_matching_compute/models/model_pattern_matching_input.py",
    "src/omniintelligence/nodes/relationship_detection_compute/models/model_relationship_detection_output.py",
    "src/omniintelligence/nodes/entity_extraction_compute/models/model_entity_extraction_output.py",
    "src/omniintelligence/models/model_intelligence_input.py",
    "src/omniintelligence/models/model_intelligence_output.py",
    "src/omniintelligence/models/model_search_result.py",
]


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


class TestNoAnyTypesInModels:
    """Verify models don't use Any type in field annotations."""

    @pytest.mark.parametrize("model_file", MODEL_FILES)
    def test_no_any_in_field_annotations(self, model_file: str) -> None:
        """Verify no `Any` type in field annotations."""
        project_root = get_project_root()
        file_path = project_root / model_file

        if not file_path.exists():
            pytest.skip(f"File not found: {file_path}")

        content = file_path.read_text()

        # Parse AST to find class field annotations
        tree = ast.parse(content)

        any_usages = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign):
                        annotation_str = ast.unparse(item.annotation)
                        # Check for raw Any usage (not dict[str, Any] which is checked separately)
                        if re.match(r"^Any$", annotation_str.strip()):
                            any_usages.append(
                                f"Class {node.name}, field {ast.unparse(item.target) if item.target else 'unknown'}: {annotation_str}"
                            )

        assert not any_usages, (
            f"Found raw `Any` type in {model_file}:\n" + "\n".join(any_usages)
        )

    @pytest.mark.parametrize("model_file", MODEL_FILES)
    def test_no_dict_str_any_in_field_annotations(self, model_file: str) -> None:
        """Verify no `dict[str, Any]` type in field annotations."""
        project_root = get_project_root()
        file_path = project_root / model_file

        if not file_path.exists():
            pytest.skip(f"File not found: {file_path}")

        content = file_path.read_text()

        # Parse AST to find class field annotations
        tree = ast.parse(content)

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.AnnAssign):
                        annotation_str = ast.unparse(item.annotation)
                        # Check for dict[str, Any] pattern
                        if re.search(r"dict\s*\[\s*str\s*,\s*Any\s*\]", annotation_str):
                            field_name = (
                                ast.unparse(item.target)
                                if item.target
                                else "unknown"
                            )
                            violations.append(
                                f"Class {node.name}, field {field_name}: {annotation_str}"
                            )

        assert not violations, (
            f"Found `dict[str, Any]` type in {model_file}:\n" + "\n".join(violations)
        )


class TestValidatorBehavior:
    """Verify model validators work correctly."""

    def test_relationship_detection_output_empty_list_validator(self) -> None:
        """Verify relationship_count is computed for empty list."""
        from omniintelligence.nodes.relationship_detection_compute.models.model_relationship_detection_output import (
            ModelRelationshipDetectionOutput,
        )

        output = ModelRelationshipDetectionOutput(
            success=True,
            relationships=[],
        )

        assert output.relationship_count == 0, (
            "Validator should compute count even for empty list"
        )

    def test_relationship_detection_output_with_relationships(self) -> None:
        """Verify relationship_count is computed correctly for non-empty list."""
        from omniintelligence.enums import EnumRelationshipType
        from omniintelligence.models.model_entity import ModelRelationship
        from omniintelligence.nodes.relationship_detection_compute.models.model_relationship_detection_output import (
            ModelRelationshipDetectionOutput,
        )

        output = ModelRelationshipDetectionOutput(
            success=True,
            relationships=[
                ModelRelationship(
                    source_id="ent_1",
                    target_id="ent_2",
                    relationship_type=EnumRelationshipType.CALLS,
                ),
                ModelRelationship(
                    source_id="ent_2",
                    target_id="ent_3",
                    relationship_type=EnumRelationshipType.IMPORTS,
                ),
            ],
        )

        assert output.relationship_count == 2, (
            "Validator should compute count from actual list length"
        )

    def test_entity_extraction_output_empty_list_validator(self) -> None:
        """Verify entity_count is computed for empty list."""
        from omniintelligence.nodes.entity_extraction_compute.models.model_entity_extraction_output import (
            ModelEntityExtractionOutput,
        )

        output = ModelEntityExtractionOutput(
            success=True,
            entities=[],
        )

        assert output.entity_count == 0, (
            "Validator should compute count even for empty list"
        )

    def test_entity_extraction_output_with_entities(self) -> None:
        """Verify entity_count is computed correctly for non-empty list."""
        from omniintelligence.enums import EnumEntityType
        from omniintelligence.models.model_entity import ModelEntity
        from omniintelligence.nodes.entity_extraction_compute.models.model_entity_extraction_output import (
            ModelEntityExtractionOutput,
        )

        output = ModelEntityExtractionOutput(
            success=True,
            entities=[
                ModelEntity(
                    entity_id="ent_1",
                    entity_type=EnumEntityType.CLASS,
                    name="MyClass",
                ),
                ModelEntity(
                    entity_id="ent_2",
                    entity_type=EnumEntityType.FUNCTION,
                    name="my_function",
                ),
            ],
        )

        assert output.entity_count == 2, (
            "Validator should compute count from actual list length"
        )


class TestTypedDictUsage:
    """Verify models use TypedDict instead of dict[str, Any]."""

    def test_keyword_extraction_uses_typeddict_for_metadata(self) -> None:
        """Verify metadata uses typed dict structure."""
        from omniintelligence.nodes.context_keyword_extractor_compute.models.model_keyword_extraction_output import (
            ExtractionMetadataDict,
            KeywordContextEntry,
            ModelKeywordExtractionOutput,
        )

        # Verify TypedDict classes exist and are used
        assert ExtractionMetadataDict is not None
        assert KeywordContextEntry is not None

        # Create instance with typed metadata
        output = ModelKeywordExtractionOutput(
            success=True,
            keywords=["test"],
            keyword_contexts={"test": KeywordContextEntry(frequency=1, positions=[0])},
            metadata=ExtractionMetadataDict(
                extraction_duration_ms=100,
                algorithm_version="1.0.0",
            ),
        )

        assert output.success is True
        assert output.metadata is not None
        assert output.metadata.get("extraction_duration_ms") == 100

    def test_intent_classification_uses_typeddict_for_context(self) -> None:
        """Verify context uses typed dict structure."""
        from omniintelligence.nodes.intent_classifier_compute.models.model_intent_classification_input import (
            IntentContextDict,
            ModelIntentClassificationInput,
        )

        # Verify TypedDict class exists
        assert IntentContextDict is not None

        # Create instance with typed context
        input_model = ModelIntentClassificationInput(
            content="test content",
            context=IntentContextDict(
                user_id="user1",
                session_id="session1",
                language="en",
            ),
        )

        assert input_model.content == "test content"
        assert input_model.context.get("user_id") == "user1"


class TestDiscriminatedUnions:
    """Verify reducer input uses discriminated unions."""

    def test_reducer_input_ingestion(self) -> None:
        """Verify INGESTION FSM type uses typed payload."""
        from uuid import uuid4

        from omniintelligence.nodes.intelligence_reducer.models.model_reducer_input import (
            ModelIngestionPayload,
            ModelReducerInputIngestion,
        )

        input_model = ModelReducerInputIngestion(
            fsm_type="INGESTION",
            entity_id="test-entity",
            action="process",
            correlation_id=uuid4(),
            payload=ModelIngestionPayload(
                content="test content",
                document_id="doc_123",
            ),
        )

        assert input_model.fsm_type == "INGESTION"
        assert input_model.payload.content == "test content"

    def test_reducer_input_pattern_learning(self) -> None:
        """Verify PATTERN_LEARNING FSM type uses typed payload."""
        from uuid import uuid4

        from omniintelligence.nodes.intelligence_reducer.models.model_reducer_input import (
            ModelPatternLearningPayload,
            ModelReducerInputPatternLearning,
        )

        input_model = ModelReducerInputPatternLearning(
            fsm_type="PATTERN_LEARNING",
            entity_id="test-entity",
            action="learn",
            correlation_id=uuid4(),
            payload=ModelPatternLearningPayload(
                pattern_id="pat_123",
                confidence_threshold=0.8,
            ),
        )

        assert input_model.fsm_type == "PATTERN_LEARNING"
        assert input_model.payload.confidence_threshold == 0.8


class TestPatternContextModel:
    """Verify pattern matching uses proper context model."""

    def test_pattern_context_is_pydantic_model(self) -> None:
        """Verify context uses Pydantic model instead of dict."""
        from pydantic import BaseModel

        from omniintelligence.nodes.pattern_matching_compute.models.model_pattern_matching_input import (
            ModelPatternContext,
            ModelPatternMatchingInput,
        )

        # Verify ModelPatternContext is a Pydantic model
        assert issubclass(ModelPatternContext, BaseModel)

        # Create instance with typed context
        input_model = ModelPatternMatchingInput(
            code_snippet="def foo(): pass",
            context=ModelPatternContext(
                language="python",
                min_confidence=0.8,
                max_results=10,
                include_similar=True,
            ),
        )

        assert input_model.context.language == "python"
        assert input_model.context.min_confidence == 0.8


class TestEnumDocumentation:
    """Verify documentation matches actual enum values."""

    def test_intelligence_input_operation_type_docs(self) -> None:
        """Verify operation_type field docs match actual enum."""
        from omniintelligence.enums import EnumIntelligenceOperationType
        from omniintelligence.models.model_intelligence_input import (
            ModelIntelligenceInput,
        )

        # Get all enum values
        enum_values = set(e.name for e in EnumIntelligenceOperationType)

        # Get field description
        field_info = ModelIntelligenceInput.model_fields["operation_type"]
        description = field_info.description or ""

        # Key operation types that should be documented
        key_operations = [
            "ASSESS_CODE_QUALITY",
            "PATTERN_MATCH",
            "ESTABLISH_PERFORMANCE_BASELINE",
            "ADVANCED_VECTOR_SEARCH",
            "INGEST_PATTERNS",
        ]

        for op in key_operations:
            assert op in enum_values, f"Operation {op} not in enum"
            assert op in description, (
                f"Operation {op} not documented in field description"
            )


class TestScoreFieldValidation:
    """Verify score fields have proper range validation."""

    def test_match_score_validation(self) -> None:
        """Verify match_score fields validate 0.0-1.0 range."""
        from pydantic import ValidationError

        from omniintelligence.models.model_search_result import ModelPatternMatch

        # Valid score
        match = ModelPatternMatch(
            pattern_name="TEST",
            match_score=0.85,
        )
        assert match.match_score == 0.85

        # Score too high
        with pytest.raises(ValidationError):
            ModelPatternMatch(
                pattern_name="TEST",
                match_score=1.5,
            )

        # Score too low
        with pytest.raises(ValidationError):
            ModelPatternMatch(
                pattern_name="TEST",
                match_score=-0.1,
            )

    def test_search_result_score_validation(self) -> None:
        """Verify search result score validates 0.0-1.0 range."""
        from pydantic import ValidationError

        from omniintelligence.models.model_search_result import ModelSearchResult

        # Valid score
        result = ModelSearchResult(
            id="test_1",
            score=0.95,
        )
        assert result.score == 0.95

        # Score too high
        with pytest.raises(ValidationError):
            ModelSearchResult(
                id="test_1",
                score=1.5,
            )

    def test_success_criteria_match_score_validation(self) -> None:
        """Verify success criteria match_score validates 0.0-1.0 range."""
        from pydantic import ValidationError

        from omniintelligence.nodes.success_criteria_matcher_compute.models.model_success_criteria_output import (
            ModelSuccessCriteriaOutput,
        )

        # Valid score
        output = ModelSuccessCriteriaOutput(
            success=True,
            match_score=0.75,
        )
        assert output.match_score == 0.75

        # Score too high
        with pytest.raises(ValidationError):
            ModelSuccessCriteriaOutput(
                success=True,
                match_score=1.5,
            )


class TestCorrelationIdValidation:
    """Verify correlation_id fields have proper validation."""

    def test_intelligence_input_correlation_id_uuid_pattern(self) -> None:
        """Verify correlation_id accepts valid UUID format."""
        from omniintelligence.enums import EnumIntelligenceOperationType
        from omniintelligence.models.model_intelligence_input import (
            ModelIntelligenceInput,
        )

        # Valid UUID
        input_model = ModelIntelligenceInput(
            operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
            content="def foo(): pass",
            correlation_id="550e8400-e29b-41d4-a716-446655440000",
        )
        assert input_model.correlation_id == "550e8400-e29b-41d4-a716-446655440000"

    def test_intelligence_input_correlation_id_invalid_pattern(self) -> None:
        """Verify correlation_id rejects invalid UUID format."""
        from pydantic import ValidationError

        from omniintelligence.enums import EnumIntelligenceOperationType
        from omniintelligence.models.model_intelligence_input import (
            ModelIntelligenceInput,
        )

        # Invalid format
        with pytest.raises(ValidationError):
            ModelIntelligenceInput(
                operation_type=EnumIntelligenceOperationType.ASSESS_CODE_QUALITY,
                content="def foo(): pass",
                correlation_id="not-a-uuid",
            )

    def test_reducer_input_uses_uuid_type(self) -> None:
        """Verify reducer input correlation_id uses UUID type."""
        from uuid import UUID, uuid4

        from omniintelligence.nodes.intelligence_reducer.models.model_reducer_input import (
            ModelReducerInputIngestion,
        )

        correlation_id = uuid4()
        input_model = ModelReducerInputIngestion(
            fsm_type="INGESTION",
            entity_id="test",
            action="process",
            correlation_id=correlation_id,
        )

        assert input_model.correlation_id == correlation_id
        assert isinstance(input_model.correlation_id, UUID)
