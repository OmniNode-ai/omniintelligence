# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
OmniIntelligence tools package.

Provides CLI tools for ONEX node development and validation.

Note: Some tools require omnibase_core to be installed. If not available,
those tools will not be exported from this module.
"""

__all__: list[str] = []

# Contract linter requires omnibase_core - make import optional
try:
    from omniintelligence.tools.contract_linter import (
        ContractLinter,
        main,
        validate_contract,
        validate_contracts_batch,
    )
    from omniintelligence.tools.enum_contract_error_type import EnumContractErrorType
    from omniintelligence.tools.model_contract_validation_error import (
        ModelContractValidationError,
    )
    from omniintelligence.tools.model_contract_validation_result import (
        ModelContractValidationResult,
    )

    __all__.extend(
        [
            "ContractLinter",
            "EnumContractErrorType",
            "ModelContractValidationError",
            "ModelContractValidationResult",
            "main",
            "validate_contract",
            "validate_contracts_batch",
        ]
    )
except ImportError:
    # omnibase_core not available - contract linter tools will not be exported
    pass
