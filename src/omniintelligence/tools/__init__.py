# SPDX-License-Identifier: Apache-2.0
"""
OmniIntelligence tools package.

Provides CLI tools for ONEX node development and validation.

Note: Some tools require omnibase_core to be installed. If not available,
those tools will not be exported from this module.
"""

__all__: list[str] = []

# Contract linter requires omnibase_core - make import optional
try:
    from omniintelligence.tools.contract_linter import (  # noqa: F401
        ContractLinter,
        ModelContractValidationError,
        ModelContractValidationResult,
        main,
        validate_contract,
        validate_contracts_batch,
    )

    __all__.extend(
        [
            "ContractLinter",
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
