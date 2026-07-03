# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
OmniIntelligence validators package.

Provides contract validators and linting tools for ONEX node development.

Note: Some validators require omnibase_core to be installed. If not available,
those validators will not be exported from this module.
"""

__all__: list[str] = []

# Contract linter requires omnibase_core - make import optional
try:
    from omniintelligence.validators.contract_linter import (  # noqa: F401
        ContractLinter,
        main,
        validate_contract,
        validate_contracts_batch,
    )
    from omniintelligence.validators.enum_contract_error_type import (  # noqa: F401
        EnumContractErrorType,
    )
    from omniintelligence.validators.model_contract_validation_error import (  # noqa: F401
        ModelContractValidationError,
    )
    from omniintelligence.validators.model_contract_validation_result import (  # noqa: F401
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
