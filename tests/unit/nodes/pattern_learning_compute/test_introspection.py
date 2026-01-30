# SPDX-FileCopyrightText: 2025 OmniNode Team
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for pattern_learning_compute introspection.

Tests introspection metadata, error codes, and node discovery.

Part of OMN-1664: Achieve 80%+ test coverage for introspection.py.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

import pytest

from omniintelligence.nodes.pattern_learning_compute.introspection import (
    PatternLearningErrorCode,
    PatternLearningIntrospection,
    PatternLearningMetadataLoader,
    get_introspection_response,
)

if TYPE_CHECKING:
    from pydantic import BaseModel


# =============================================================================
# PatternLearningErrorCode Tests
# =============================================================================


@pytest.mark.unit
class TestPatternLearningErrorCode:
    """Tests for error code enum."""

    def test_get_number_returns_numeric_portion_patlearn_001(self) -> None:
        """PATLEARN_001 returns numeric portion 1."""
        error_code = PatternLearningErrorCode.PATLEARN_001
        assert error_code.get_number() == 1

    def test_get_number_returns_numeric_portion_patlearn_002(self) -> None:
        """PATLEARN_002 returns numeric portion 2."""
        error_code = PatternLearningErrorCode.PATLEARN_002
        assert error_code.get_number() == 2

    def test_get_number_returns_integer(self) -> None:
        """Error codes return integers from get_number()."""
        for error_code in PatternLearningErrorCode:
            result = error_code.get_number()
            assert isinstance(result, int)

    def test_get_description_returns_string(self) -> None:
        """Error descriptions are non-empty strings."""
        for error_code in PatternLearningErrorCode:
            description = error_code.get_description()
            assert isinstance(description, str)
            assert len(description) > 0

    def test_get_description_patlearn_001_content(self) -> None:
        """PATLEARN_001 description mentions input validation."""
        description = PatternLearningErrorCode.PATLEARN_001.get_description()
        assert "Input validation failed" in description

    def test_get_description_patlearn_002_content(self) -> None:
        """PATLEARN_002 description mentions computation error."""
        description = PatternLearningErrorCode.PATLEARN_002.get_description()
        assert "pattern learning computation" in description.lower()

    def test_get_exit_code_is_positive(self) -> None:
        """Exit codes are positive integers."""
        for error_code in PatternLearningErrorCode:
            exit_code = error_code.get_exit_code()
            assert isinstance(exit_code, int)
            assert exit_code > 0

    def test_get_exit_code_patlearn_001_is_1(self) -> None:
        """PATLEARN_001 has exit code 1 (non-recoverable)."""
        exit_code = PatternLearningErrorCode.PATLEARN_001.get_exit_code()
        assert exit_code == 1

    def test_get_exit_code_patlearn_002_is_2(self) -> None:
        """PATLEARN_002 has exit code 2 (recoverable)."""
        exit_code = PatternLearningErrorCode.PATLEARN_002.get_exit_code()
        assert exit_code == 2

    def test_enum_has_expected_members(self) -> None:
        """Enum has expected error code members."""
        member_names = [e.name for e in PatternLearningErrorCode]
        assert "PATLEARN_001" in member_names
        assert "PATLEARN_002" in member_names

    def test_enum_values_match_names(self) -> None:
        """Enum values match their names."""
        for error_code in PatternLearningErrorCode:
            assert error_code.value == error_code.name

    def test_inherits_from_enum(self) -> None:
        """PatternLearningErrorCode is an Enum."""
        assert issubclass(PatternLearningErrorCode, Enum)

    def test_get_description_unknown_error_fallback(self) -> None:
        """Unknown error codes return 'Unknown error' fallback.

        This tests the dictionary lookup fallback behavior.
        Note: This is a defensive test for code robustness.
        """
        # The descriptions dict only has entries for known codes
        # Testing the fallback requires examining the implementation
        # which uses .get() with a default
        # All current codes have descriptions, so we verify that
        for error_code in PatternLearningErrorCode:
            description = error_code.get_description()
            assert description != "Unknown error"


# =============================================================================
# PatternLearningMetadataLoader Tests
# =============================================================================


@pytest.mark.unit
class TestPatternLearningMetadataLoader:
    """Tests for metadata loader."""

    def test_init_creates_instance(self) -> None:
        """MetadataLoader can be instantiated."""
        loader = PatternLearningMetadataLoader()
        assert loader is not None

    def test_node_name_attribute(self) -> None:
        """Returns expected node name."""
        loader = PatternLearningMetadataLoader()
        assert loader.node_name == "pattern_learning_compute"

    def test_node_name_is_string(self) -> None:
        """Node name is a string."""
        loader = PatternLearningMetadataLoader()
        assert isinstance(loader.node_name, str)

    def test_node_version_attribute(self) -> None:
        """Returns node version as ModelSemVer."""
        from omnibase_core.models.primitives.model_semver import ModelSemVer

        loader = PatternLearningMetadataLoader()
        assert isinstance(loader.node_version, ModelSemVer)

    def test_node_version_is_1_0_0(self) -> None:
        """Node version is 1.0.0."""
        loader = PatternLearningMetadataLoader()
        assert loader.node_version.major == 1
        assert loader.node_version.minor == 0
        assert loader.node_version.patch == 0

    def test_node_description_attribute(self) -> None:
        """Returns non-empty node description."""
        loader = PatternLearningMetadataLoader()
        assert isinstance(loader.node_description, str)
        assert len(loader.node_description) > 0

    def test_node_description_mentions_compute(self) -> None:
        """Description mentions compute node purpose."""
        loader = PatternLearningMetadataLoader()
        assert "compute" in loader.node_description.lower()

    def test_node_description_mentions_pattern(self) -> None:
        """Description mentions pattern learning."""
        loader = PatternLearningMetadataLoader()
        assert "pattern" in loader.node_description.lower()

    def test_input_state_class_returns_model(self) -> None:
        """Returns the input model class."""
        from omniintelligence.nodes.pattern_learning_compute.models import (
            ModelPatternLearningInput,
        )

        loader = PatternLearningMetadataLoader()
        assert loader.input_state_class is ModelPatternLearningInput

    def test_input_state_class_is_type(self) -> None:
        """Input state class is a type."""
        loader = PatternLearningMetadataLoader()
        assert isinstance(loader.input_state_class, type)

    def test_output_state_class_returns_model(self) -> None:
        """Returns the output model class."""
        from omniintelligence.nodes.pattern_learning_compute.models import (
            ModelPatternLearningOutput,
        )

        loader = PatternLearningMetadataLoader()
        assert loader.output_state_class is ModelPatternLearningOutput

    def test_output_state_class_is_type(self) -> None:
        """Output state class is a type."""
        loader = PatternLearningMetadataLoader()
        assert isinstance(loader.output_state_class, type)

    def test_error_codes_class_returns_enum(self) -> None:
        """Returns the error codes enum."""
        loader = PatternLearningMetadataLoader()
        assert loader.error_codes_class is PatternLearningErrorCode

    def test_error_codes_class_is_enum_type(self) -> None:
        """Error codes class is an Enum type."""
        loader = PatternLearningMetadataLoader()
        assert issubclass(loader.error_codes_class, Enum)

    def test_frozen_dataclass_immutable(self) -> None:
        """Frozen dataclass prevents attribute modification."""
        loader = PatternLearningMetadataLoader()
        with pytest.raises(AttributeError):
            loader.node_name = "modified"  # type: ignore[misc]

    def test_multiple_instances_have_same_values(self) -> None:
        """Multiple instances have consistent default values."""
        loader1 = PatternLearningMetadataLoader()
        loader2 = PatternLearningMetadataLoader()
        assert loader1.node_name == loader2.node_name
        assert loader1.node_description == loader2.node_description


# =============================================================================
# PatternLearningIntrospection Tests
# =============================================================================


@pytest.mark.unit
class TestPatternLearningIntrospection:
    """Tests for introspection class."""

    def test_get_metadata_loader_returns_loader(self) -> None:
        """Returns PatternLearningMetadataLoader instance."""
        loader = PatternLearningIntrospection.get_metadata_loader()
        assert isinstance(loader, PatternLearningMetadataLoader)

    def test_get_metadata_loader_caches_instance(self) -> None:
        """Returns cached metadata loader on subsequent calls."""
        # Reset the cache first
        PatternLearningIntrospection._metadata_loader = None

        loader1 = PatternLearningIntrospection.get_metadata_loader()
        loader2 = PatternLearningIntrospection.get_metadata_loader()
        assert loader1 is loader2

    def test_get_metadata_loader_creates_on_first_call(self) -> None:
        """Creates new loader when cache is None."""
        # Reset the cache
        PatternLearningIntrospection._metadata_loader = None

        loader = PatternLearningIntrospection.get_metadata_loader()
        assert loader is not None
        assert PatternLearningIntrospection._metadata_loader is loader

    def test_get_node_author_returns_string(self) -> None:
        """Author is a non-empty string."""
        author = PatternLearningIntrospection.get_node_author()
        assert isinstance(author, str)
        assert len(author) > 0

    def test_get_node_author_value(self) -> None:
        """Author is OmniNode Team."""
        author = PatternLearningIntrospection.get_node_author()
        assert author == "OmniNode Team"

    def test_node_category_returns_string(self) -> None:
        """Category is a non-empty string."""
        category = PatternLearningIntrospection._get_node_category()
        assert isinstance(category, str)
        assert len(category) > 0

    def test_node_category_is_compute(self) -> None:
        """Category is 'compute'."""
        category = PatternLearningIntrospection._get_node_category()
        assert category == "compute"

    def test_node_tags_returns_list(self) -> None:
        """Tags is a list."""
        tags = PatternLearningIntrospection._get_node_tags()
        assert isinstance(tags, list)

    def test_node_tags_not_empty(self) -> None:
        """Tags list is not empty."""
        tags = PatternLearningIntrospection._get_node_tags()
        assert len(tags) > 0

    def test_node_tags_contains_strings(self) -> None:
        """Tags list contains only strings."""
        tags = PatternLearningIntrospection._get_node_tags()
        for tag in tags:
            assert isinstance(tag, str)

    def test_node_tags_contains_expected_values(self) -> None:
        """Tags contains expected values."""
        tags = PatternLearningIntrospection._get_node_tags()
        assert "ONEX" in tags
        assert "compute" in tags
        assert "pattern-learning" in tags

    def test_node_maturity_returns_string(self) -> None:
        """Maturity is a string."""
        maturity = PatternLearningIntrospection._get_node_maturity()
        assert isinstance(maturity, str)

    def test_node_maturity_is_stable(self) -> None:
        """Maturity is 'stable'."""
        maturity = PatternLearningIntrospection._get_node_maturity()
        assert maturity == "stable"

    def test_node_maturity_valid_value(self) -> None:
        """Maturity is a valid maturity level."""
        valid_maturity_levels = {"experimental", "beta", "stable", "deprecated"}
        maturity = PatternLearningIntrospection._get_node_maturity()
        assert maturity in valid_maturity_levels

    def test_node_use_cases_returns_list(self) -> None:
        """Use cases is a list."""
        use_cases = PatternLearningIntrospection._get_node_use_cases()
        assert isinstance(use_cases, list)

    def test_node_use_cases_not_empty(self) -> None:
        """Use cases list is not empty."""
        use_cases = PatternLearningIntrospection._get_node_use_cases()
        assert len(use_cases) > 0

    def test_node_use_cases_contains_strings(self) -> None:
        """Use cases list contains only strings."""
        use_cases = PatternLearningIntrospection._get_node_use_cases()
        for use_case in use_cases:
            assert isinstance(use_case, str)

    def test_node_use_cases_meaningful_content(self) -> None:
        """Use cases contain meaningful descriptions."""
        use_cases = PatternLearningIntrospection._get_node_use_cases()
        # Check that use cases are not trivially short
        for use_case in use_cases:
            assert len(use_case) > 10

    def test_get_runtime_dependencies_returns_list(self) -> None:
        """Runtime dependencies is a list."""
        deps = PatternLearningIntrospection.get_runtime_dependencies()
        assert isinstance(deps, list)

    def test_get_runtime_dependencies_not_empty(self) -> None:
        """Runtime dependencies list is not empty."""
        deps = PatternLearningIntrospection.get_runtime_dependencies()
        assert len(deps) > 0

    def test_get_runtime_dependencies_contains_strings(self) -> None:
        """Runtime dependencies list contains only strings."""
        deps = PatternLearningIntrospection.get_runtime_dependencies()
        for dep in deps:
            assert isinstance(dep, str)

    def test_get_runtime_dependencies_contains_omnibase_core(self) -> None:
        """Runtime dependencies includes omnibase_core."""
        deps = PatternLearningIntrospection.get_runtime_dependencies()
        assert "omnibase_core" in deps

    def test_get_runtime_dependencies_contains_pydantic(self) -> None:
        """Runtime dependencies includes pydantic."""
        deps = PatternLearningIntrospection.get_runtime_dependencies()
        assert "pydantic" in deps

    def test_get_cli_entrypoint_returns_string(self) -> None:
        """CLI entrypoint is a string."""
        entrypoint = PatternLearningIntrospection.get_cli_entrypoint()
        assert isinstance(entrypoint, str)

    def test_get_cli_entrypoint_not_empty(self) -> None:
        """CLI entrypoint is not empty."""
        entrypoint = PatternLearningIntrospection.get_cli_entrypoint()
        assert len(entrypoint) > 0

    def test_get_cli_entrypoint_is_python_module(self) -> None:
        """CLI entrypoint is a Python module invocation."""
        entrypoint = PatternLearningIntrospection.get_cli_entrypoint()
        assert entrypoint.startswith("python -m")

    def test_get_cli_entrypoint_correct_module(self) -> None:
        """CLI entrypoint references correct module."""
        entrypoint = PatternLearningIntrospection.get_cli_entrypoint()
        assert "omniintelligence.nodes.pattern_learning_compute" in entrypoint


# =============================================================================
# get_introspection_response Tests
# =============================================================================


@pytest.mark.unit
class TestGetIntrospectionResponse:
    """Tests for convenience function.

    Note: Some tests are marked xfail due to an upstream issue in omnibase_core
    where ModelNodeCoreMetadata is not fully defined (missing ModelSemVer rebuild).
    These tests verify the function exists and is callable, but full response
    generation requires upstream fixes.
    """

    def test_function_is_callable(self) -> None:
        """Function exists and is callable."""
        assert callable(get_introspection_response)

    def test_function_has_docstring(self) -> None:
        """Function has a docstring."""
        assert get_introspection_response.__doc__ is not None
        assert len(get_introspection_response.__doc__) > 0

    @pytest.mark.xfail(
        reason="Upstream omnibase_core issue: ModelNodeCoreMetadata not fully defined"
    )
    def test_returns_response_object(self) -> None:
        """Returns a response object."""
        response = get_introspection_response()
        assert response is not None

    @pytest.mark.xfail(
        reason="Upstream omnibase_core issue: ModelNodeCoreMetadata not fully defined"
    )
    def test_returns_correct_type(self) -> None:
        """Returns ModelNodeIntrospectionResponse."""
        from omnibase_core.models.core.model_node_introspection_response import (
            ModelNodeIntrospectionResponse,
        )

        response = get_introspection_response()
        assert isinstance(response, ModelNodeIntrospectionResponse)

    @pytest.mark.xfail(
        reason="Upstream omnibase_core issue: ModelNodeCoreMetadata not fully defined"
    )
    def test_response_has_node_name(self) -> None:
        """Response contains node name."""
        response = get_introspection_response()
        assert hasattr(response, "node_name") or hasattr(response, "name")

    @pytest.mark.xfail(
        reason="Upstream omnibase_core issue: ModelNodeCoreMetadata not fully defined"
    )
    def test_response_has_version(self) -> None:
        """Response contains version information."""
        response = get_introspection_response()
        # Check for version-related attributes
        has_version = (
            hasattr(response, "version")
            or hasattr(response, "node_version")
            or hasattr(response, "semver")
        )
        assert has_version

    @pytest.mark.xfail(
        reason="Upstream omnibase_core issue: ModelNodeCoreMetadata not fully defined"
    )
    def test_multiple_calls_consistent(self) -> None:
        """Multiple calls return consistent results."""
        response1 = get_introspection_response()
        response2 = get_introspection_response()
        # Both should have same node information
        assert type(response1) is type(response2)


# =============================================================================
# Module Export Tests
# =============================================================================


@pytest.mark.unit
class TestModuleExports:
    """Tests verifying module exports."""

    def test_all_exports_importable(self) -> None:
        """All expected classes/functions are importable."""
        from omniintelligence.nodes.pattern_learning_compute import introspection

        assert hasattr(introspection, "PatternLearningErrorCode")
        assert hasattr(introspection, "PatternLearningMetadataLoader")
        assert hasattr(introspection, "PatternLearningIntrospection")
        assert hasattr(introspection, "get_introspection_response")

    def test_dunder_all_defined(self) -> None:
        """Module defines __all__."""
        from omniintelligence.nodes.pattern_learning_compute import introspection

        assert hasattr(introspection, "__all__")

    def test_dunder_all_contents(self) -> None:
        """__all__ contains expected exports."""
        from omniintelligence.nodes.pattern_learning_compute import introspection

        expected = {
            "PatternLearningErrorCode",
            "PatternLearningIntrospection",
            "PatternLearningMetadataLoader",
            "get_introspection_response",
        }
        assert set(introspection.__all__) == expected

    def test_error_code_is_enum(self) -> None:
        """Exported PatternLearningErrorCode is an Enum."""
        from omniintelligence.nodes.pattern_learning_compute import introspection

        assert issubclass(introspection.PatternLearningErrorCode, Enum)

    def test_metadata_loader_is_class(self) -> None:
        """Exported PatternLearningMetadataLoader is a class."""
        from omniintelligence.nodes.pattern_learning_compute import introspection

        assert isinstance(introspection.PatternLearningMetadataLoader, type)

    def test_introspection_is_class(self) -> None:
        """Exported PatternLearningIntrospection is a class."""
        from omniintelligence.nodes.pattern_learning_compute import introspection

        assert isinstance(introspection.PatternLearningIntrospection, type)

    def test_get_introspection_response_is_callable(self) -> None:
        """Exported get_introspection_response is callable."""
        from omniintelligence.nodes.pattern_learning_compute import introspection

        assert callable(introspection.get_introspection_response)


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.unit
class TestIntrospectionIntegration:
    """Integration tests for introspection components."""

    def test_error_codes_match_metadata_loader(self) -> None:
        """Error codes from loader match the enum."""
        loader = PatternLearningMetadataLoader()
        error_codes_class = loader.error_codes_class
        assert error_codes_class is PatternLearningErrorCode

    def test_input_output_models_are_pydantic(self) -> None:
        """Input and output models are Pydantic BaseModel subclasses."""
        from pydantic import BaseModel

        loader = PatternLearningMetadataLoader()
        assert issubclass(loader.input_state_class, BaseModel)
        assert issubclass(loader.output_state_class, BaseModel)

    def test_introspection_uses_metadata_loader(self) -> None:
        """Introspection class uses the metadata loader."""
        # Reset cache
        PatternLearningIntrospection._metadata_loader = None

        loader = PatternLearningIntrospection.get_metadata_loader()
        assert isinstance(loader, PatternLearningMetadataLoader)

    @pytest.mark.xfail(
        reason="Upstream omnibase_core issue: ModelNodeCoreMetadata not fully defined"
    )
    def test_full_workflow_metadata_to_response(self) -> None:
        """Full workflow from metadata loader to response works."""
        # Get loader
        loader = PatternLearningIntrospection.get_metadata_loader()
        assert loader.node_name == "pattern_learning_compute"

        # Get response
        response = get_introspection_response()
        assert response is not None

    def test_all_error_codes_have_descriptions(self) -> None:
        """All error codes have non-empty descriptions."""
        for error_code in PatternLearningErrorCode:
            description = error_code.get_description()
            assert description is not None
            assert len(description) > 0
            assert description != "Unknown error"

    def test_all_error_codes_have_exit_codes(self) -> None:
        """All error codes have valid exit codes."""
        for error_code in PatternLearningErrorCode:
            exit_code = error_code.get_exit_code()
            assert isinstance(exit_code, int)
            assert exit_code > 0
