# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

from enum import Enum


class EnumEvalDomain(str, Enum):
    CONTRACT_CREATION = "contract_creation"
    AGENT_EXECUTION = "agent_execution"
    MEMORY_SYSTEM = "memory_system"
