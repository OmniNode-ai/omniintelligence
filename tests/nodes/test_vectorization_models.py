"""Unit tests for Vectorization Compute models.

Tests the consistent output structure for both single and batch modes.
"""

import pytest
from pydantic import ValidationError

# Import directly to avoid package-level imports that may have dependency issues
import sys
sys.path.insert(0, "src")

from omniintelligence.nodes.vectorization_compute.models.model_vectorization_input import (
    ModelVectorizationInput,
)
from omniintelligence.nodes.vectorization_compute.models.model_vectorization_output import (
    ModelVectorizationOutput,
)


class TestModelVectorizationInput:
    """Test ModelVectorizationInput validation."""

    def test_valid_input(self):
        """Test valid input creation."""
        input_model = ModelVectorizationInput(
            content="Hello world",
            metadata={"source": "test"},
            model_name="text-embedding-3-small",
            batch_mode=False,
        )
        assert input_model.content == "Hello world"
        assert input_model.metadata == {"source": "test"}
        assert input_model.model_name == "text-embedding-3-small"
        assert input_model.batch_mode is False

    def test_default_values(self):
        """Test default field values."""
        input_model = ModelVectorizationInput(content="test content")
        assert input_model.metadata == {}
        assert input_model.model_name == "text-embedding-3-small"
        assert input_model.batch_mode is False

    def test_empty_content_rejected(self):
        """Test that empty content is rejected."""
        with pytest.raises(ValidationError):
            ModelVectorizationInput(content="")

    def test_batch_mode_flag(self):
        """Test batch_mode flag."""
        input_batch = ModelVectorizationInput(
            content="item1\nitem2\nitem3",
            batch_mode=True,
        )
        assert input_batch.batch_mode is True


class TestModelVectorizationOutput:
    """Test ModelVectorizationOutput validation.

    Verifies the consistent output structure for both single and batch modes.
    """

    # =========================================================================
    # Single Mode Tests
    # =========================================================================

    def test_single_mode_success(self):
        """Test successful single mode output."""
        output = ModelVectorizationOutput(
            success=True,
            embeddings=[[0.1, 0.2, 0.3, 0.4, 0.5]],
            model_used="text-embedding-3-small",
            batch_count=1,
            embedding_dimension=5,
        )
        assert output.success is True
        assert len(output.embeddings) == 1
        assert len(output.embeddings[0]) == 5
        assert output.batch_count == 1
        assert output.embedding_dimension == 5

    def test_single_mode_with_metadata(self):
        """Test single mode output with metadata."""
        output = ModelVectorizationOutput(
            success=True,
            embeddings=[[0.1, 0.2, 0.3]],
            model_used="text-embedding-3-small",
            batch_count=1,
            embedding_dimension=3,
            metadata={"content_length": 100, "source": "test"},
        )
        assert output.metadata["content_length"] == 100
        assert output.metadata["source"] == "test"

    # =========================================================================
    # Batch Mode Tests
    # =========================================================================

    def test_batch_mode_success(self):
        """Test successful batch mode output."""
        output = ModelVectorizationOutput(
            success=True,
            embeddings=[
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
                [0.7, 0.8, 0.9],
            ],
            model_used="text-embedding-3-small",
            batch_count=3,
            embedding_dimension=3,
        )
        assert output.success is True
        assert len(output.embeddings) == 3
        assert output.batch_count == 3
        assert output.embedding_dimension == 3

    def test_batch_mode_consistent_access(self):
        """Test that batch mode embeddings can be accessed consistently."""
        output = ModelVectorizationOutput(
            success=True,
            embeddings=[
                [1.0, 2.0],
                [3.0, 4.0],
            ],
            model_used="test-model",
            batch_count=2,
            embedding_dimension=2,
        )
        # Same access pattern works for both modes
        for i, emb in enumerate(output.embeddings):
            assert len(emb) == output.embedding_dimension
            if i == 0:
                assert emb == [1.0, 2.0]
            else:
                assert emb == [3.0, 4.0]

    # =========================================================================
    # Failed Operation Tests
    # =========================================================================

    def test_failed_operation(self):
        """Test failed operation output."""
        output = ModelVectorizationOutput(
            success=False,
            embeddings=[],
            model_used="none",
            batch_count=0,
            embedding_dimension=0,
            metadata={"error": "Content was empty"},
        )
        assert output.success is False
        assert len(output.embeddings) == 0
        assert output.batch_count == 0
        assert output.embedding_dimension == 0
        assert output.metadata["error"] == "Content was empty"

    def test_failed_with_non_empty_embeddings_rejected(self):
        """Test that failed operations with non-empty embeddings are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ModelVectorizationOutput(
                success=False,
                embeddings=[[0.1, 0.2]],  # Should be empty on failure
                model_used="none",
                batch_count=0,
                embedding_dimension=0,
            )
        assert "Failed vectorization should have empty embeddings" in str(
            exc_info.value
        )

    def test_failed_with_nonzero_batch_count_rejected(self):
        """Test that failed operations with non-zero batch_count are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ModelVectorizationOutput(
                success=False,
                embeddings=[],
                model_used="none",
                batch_count=1,  # Should be 0 on failure
                embedding_dimension=0,
            )
        assert "Failed vectorization should have batch_count=0" in str(exc_info.value)

    # =========================================================================
    # Consistency Validation Tests
    # =========================================================================

    def test_batch_count_must_match_embeddings_length(self):
        """Test that batch_count must match number of embeddings."""
        with pytest.raises(ValidationError) as exc_info:
            ModelVectorizationOutput(
                success=True,
                embeddings=[[0.1, 0.2, 0.3]],
                model_used="test-model",
                batch_count=2,  # Wrong! Only 1 embedding
                embedding_dimension=3,
            )
        assert "batch_count (2) must match number of embeddings (1)" in str(
            exc_info.value
        )

    def test_embedding_dimension_must_match_vector_length(self):
        """Test that embedding_dimension must match actual vector length."""
        with pytest.raises(ValidationError) as exc_info:
            ModelVectorizationOutput(
                success=True,
                embeddings=[[0.1, 0.2, 0.3]],
                model_used="test-model",
                batch_count=1,
                embedding_dimension=5,  # Wrong! Vector has length 3
            )
        assert "embedding_dimension (5) must match actual vector dimension (3)" in str(
            exc_info.value
        )

    def test_all_embeddings_must_have_same_dimension(self):
        """Test that all embedding vectors must have the same dimension."""
        with pytest.raises(ValidationError) as exc_info:
            ModelVectorizationOutput(
                success=True,
                embeddings=[
                    [0.1, 0.2, 0.3],
                    [0.4, 0.5],  # Wrong! Different dimension
                ],
                model_used="test-model",
                batch_count=2,
                embedding_dimension=3,
            )
        assert "Embedding 1 has dimension 2, expected 3" in str(exc_info.value)

    def test_successful_must_have_at_least_one_embedding(self):
        """Test that successful operations must have at least one embedding."""
        with pytest.raises(ValidationError) as exc_info:
            ModelVectorizationOutput(
                success=True,
                embeddings=[],  # Empty! But success=True
                model_used="test-model",
                batch_count=0,
                embedding_dimension=0,
            )
        assert "Successful vectorization must have at least one embedding" in str(
            exc_info.value
        )

    # =========================================================================
    # Model Config Tests
    # =========================================================================

    def test_frozen_model(self):
        """Test that model is frozen (immutable)."""
        output = ModelVectorizationOutput(
            success=True,
            embeddings=[[0.1, 0.2, 0.3]],
            model_used="test-model",
            batch_count=1,
            embedding_dimension=3,
        )
        with pytest.raises(ValidationError):
            output.success = False  # type: ignore

    def test_extra_fields_forbidden(self):
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError):
            ModelVectorizationOutput(
                success=True,
                embeddings=[[0.1, 0.2, 0.3]],
                model_used="test-model",
                batch_count=1,
                embedding_dimension=3,
                extra_field="not allowed",  # type: ignore
            )

    # =========================================================================
    # Serialization Tests
    # =========================================================================

    def test_model_dump(self):
        """Test model serialization to dict."""
        output = ModelVectorizationOutput(
            success=True,
            embeddings=[[0.1, 0.2]],
            model_used="test-model",
            batch_count=1,
            embedding_dimension=2,
        )
        data = output.model_dump()
        assert data["success"] is True
        assert data["embeddings"] == [[0.1, 0.2]]
        assert data["model_used"] == "test-model"
        assert data["batch_count"] == 1
        assert data["embedding_dimension"] == 2

    def test_model_dump_json(self):
        """Test model serialization to JSON."""
        output = ModelVectorizationOutput(
            success=True,
            embeddings=[[0.1, 0.2]],
            model_used="test-model",
            batch_count=1,
            embedding_dimension=2,
        )
        json_str = output.model_dump_json()
        assert '"success":true' in json_str.lower().replace(" ", "")
        assert '"embeddings":[[0.1,0.2]]' in json_str.lower().replace(" ", "")


class TestOutputConsistency:
    """Test that single and batch modes have consistent output structure."""

    def test_same_access_pattern(self):
        """Test that the same access pattern works for both modes."""
        # Single mode
        single_output = ModelVectorizationOutput(
            success=True,
            embeddings=[[1.0, 2.0, 3.0]],
            model_used="test-model",
            batch_count=1,
            embedding_dimension=3,
        )

        # Batch mode
        batch_output = ModelVectorizationOutput(
            success=True,
            embeddings=[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
            model_used="test-model",
            batch_count=2,
            embedding_dimension=3,
        )

        # Same iteration pattern works for both
        single_embeddings = list(single_output.embeddings)
        batch_embeddings = list(batch_output.embeddings)

        assert len(single_embeddings) == 1
        assert len(batch_embeddings) == 2

        # Each embedding has same structure (list of floats)
        for emb in single_embeddings + batch_embeddings:
            assert isinstance(emb, list)
            assert all(isinstance(x, float) for x in emb)
            assert len(emb) == 3

    def test_consistent_field_types(self):
        """Test that field types are consistent between modes."""
        single_output = ModelVectorizationOutput(
            success=True,
            embeddings=[[0.1]],
            model_used="m",
            batch_count=1,
            embedding_dimension=1,
        )

        batch_output = ModelVectorizationOutput(
            success=True,
            embeddings=[[0.1], [0.2]],
            model_used="m",
            batch_count=2,
            embedding_dimension=1,
        )

        # Same field types
        assert type(single_output.embeddings) is type(batch_output.embeddings)  # list
        assert type(single_output.batch_count) is type(batch_output.batch_count)  # int
        assert type(single_output.embedding_dimension) is type(
            batch_output.embedding_dimension
        )  # int
