from enum import Enum


class EnumEvalDomain(str, Enum):
    CONTRACT_CREATION = "contract_creation"
    AGENT_EXECUTION = "agent_execution"
    MEMORY_SYSTEM = "memory_system"
