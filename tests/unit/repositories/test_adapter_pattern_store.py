"""Unit tests for AdapterPatternStore._build_positional_args error paths.

Tests cover:
1. Unknown operation name raises ValueError
2. Missing required parameter with no default raises ValueError
"""

from unittest.mock import MagicMock

import pytest

from omnibase_core.enums.enum_parameter_type import EnumParameterType
from omnibase_core.models.common.model_schema_value import ModelSchemaValue
from omnibase_core.models.contracts.model_db_operation import ModelDbOperation
from omnibase_core.models.contracts.model_db_param import ModelDbParam
from omnibase_core.models.contracts.model_db_repository_contract import (
    ModelDbRepositoryContract,
)
from omnibase_core.models.contracts.model_db_return import ModelDbReturn

from omniintelligence.repositories.adapter_pattern_store import AdapterPatternStore


def _create_test_contract() -> ModelDbRepositoryContract:
    """Create a minimal test contract with one operation for testing.

    The operation has:
    - One required param with no default ('required_param')
    - One optional param with a default ('optional_with_default')
    - One optional param with no default ('optional_no_default')
    """
    return ModelDbRepositoryContract(
        name="test_contract",
        engine="postgres",
        database_ref="test_db",
        tables=["test_table"],
        models={
            "TestResult": "test.models:TestResult",
        },
        ops={
            "test_operation": ModelDbOperation(
                mode="read",
                sql="SELECT * FROM test_table WHERE id = :required_param",
                params={
                    "required_param": ModelDbParam(
                        name="required_param",
                        param_type=EnumParameterType.STRING,
                        required=True,
                        default=None,
                        description="A required parameter with no default",
                    ),
                    "optional_with_default": ModelDbParam(
                        name="optional_with_default",
                        param_type=EnumParameterType.INTEGER,
                        required=False,
                        default=ModelSchemaValue.create_number(10),
                        description="An optional parameter with a default value",
                    ),
                    "optional_no_default": ModelDbParam(
                        name="optional_no_default",
                        param_type=EnumParameterType.STRING,
                        required=False,
                        default=None,
                        description="An optional parameter with no default",
                    ),
                },
                returns=ModelDbReturn(
                    model_ref="TestResult",
                    many=False,
                ),
            ),
        },
    )


def _create_adapter_with_mock_runtime(
    contract: ModelDbRepositoryContract,
) -> AdapterPatternStore:
    """Create an adapter with a mocked runtime containing the given contract."""
    mock_runtime = MagicMock()
    mock_runtime.contract = contract
    return AdapterPatternStore(runtime=mock_runtime)


class TestBuildPositionalArgsErrorPaths:
    """Tests for _build_positional_args error handling."""

    @pytest.mark.unit
    def test_build_positional_args_unknown_operation_raises(self) -> None:
        """_build_positional_args raises ValueError for unknown operation."""
        # Arrange
        contract = _create_test_contract()
        adapter = _create_adapter_with_mock_runtime(contract)
        unknown_op_name = "nonexistent_operation"
        provided_params = {"some_param": "some_value"}

        # Act & Assert
        with pytest.raises(ValueError, match=f"Unknown operation: {unknown_op_name}"):
            adapter._build_positional_args(unknown_op_name, provided_params)

    @pytest.mark.unit
    def test_build_positional_args_missing_required_param_raises(self) -> None:
        """_build_positional_args raises ValueError when required param missing."""
        # Arrange
        contract = _create_test_contract()
        adapter = _create_adapter_with_mock_runtime(contract)
        op_name = "test_operation"
        # Intentionally omit 'required_param' which is required and has no default
        provided_params = {"optional_with_default": 42}

        # Act & Assert
        with pytest.raises(
            ValueError,
            match=r"Required param 'required_param' not provided for operation 'test_operation'",
        ):
            adapter._build_positional_args(op_name, provided_params)

    @pytest.mark.unit
    def test_build_positional_args_success_with_all_required(self) -> None:
        """_build_positional_args succeeds when all required params provided."""
        # Arrange
        contract = _create_test_contract()
        adapter = _create_adapter_with_mock_runtime(contract)
        op_name = "test_operation"
        provided_params = {"required_param": "test_value"}

        # Act
        result = adapter._build_positional_args(op_name, provided_params)

        # Assert - should return tuple with:
        # - provided required_param
        # - default for optional_with_default (10)
        # - None for optional_no_default (optional with no default)
        assert result == ("test_value", 10, None)

    @pytest.mark.unit
    def test_build_positional_args_uses_contract_defaults(self) -> None:
        """_build_positional_args applies contract defaults for optional params."""
        # Arrange
        contract = _create_test_contract()
        adapter = _create_adapter_with_mock_runtime(contract)
        op_name = "test_operation"
        provided_params = {"required_param": "test_value"}

        # Act
        result = adapter._build_positional_args(op_name, provided_params)

        # Assert - second param should be the default value (10)
        assert result[1] == 10

    @pytest.mark.unit
    def test_build_positional_args_provided_overrides_default(self) -> None:
        """_build_positional_args uses provided value over contract default."""
        # Arrange
        contract = _create_test_contract()
        adapter = _create_adapter_with_mock_runtime(contract)
        op_name = "test_operation"
        provided_params = {
            "required_param": "test_value",
            "optional_with_default": 999,  # Override the default of 10
        }

        # Act
        result = adapter._build_positional_args(op_name, provided_params)

        # Assert - second param should be the provided value, not default
        assert result[1] == 999
