# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""
Stub implementations for external dependencies.

This module provides stub implementations for modules that are expected
to exist in external packages but are not yet available. These stubs
allow the code to function while the actual implementations are being
developed or migrated.
"""

from omniintelligence.tools.stubs.contract_validator import (
    ProtocolContractValidator,
    ProtocolContractValidatorResult,
)

__all__ = [
    "ProtocolContractValidator",
    "ProtocolContractValidatorResult",
]
