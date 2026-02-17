"""Pattern Compliance Compute Handlers.

Provides handler functions for evaluating code against applicable patterns
using an LLM (Coder-14B). Handlers implement the computation logic following
the ONEX thin shell pattern where nodes delegate to handler functions.

Handler Pattern:
    The compute handler orchestrates the compliance evaluation workflow:
    - Builds a structured prompt from code + patterns
    - Delegates LLM inference to an injected ProtocolLlmClient
    - Parses the JSON response into typed violations
    - Returns a structured ModelComplianceResult
    - Routes failures to DLQ when kafka_producer is available (optional)

The pure handler functions (build_compliance_prompt, parse_llm_response)
contain no I/O and can be tested independently.

Ticket: OMN-2256
"""

from omniintelligence.nodes.node_pattern_compliance_effect.handlers.exceptions import (
    ComplianceValidationError,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.handler_compliance import (
    COMPLIANCE_PROMPT_VERSION,
    build_compliance_prompt,
    parse_llm_response,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.handler_compute import (
    DEFAULT_MODEL,
    DLQ_TOPIC,
    handle_evaluate_compliance,
)
from omniintelligence.nodes.node_pattern_compliance_effect.handlers.protocols import (
    ComplianceLlmResponseDict,
    ComplianceViolationDict,
    ProtocolLlmClient,
)
from omniintelligence.protocols import ProtocolKafkaPublisher

__all__ = [
    "COMPLIANCE_PROMPT_VERSION",
    "DEFAULT_MODEL",
    "DLQ_TOPIC",
    "ComplianceLlmResponseDict",
    "ComplianceValidationError",
    "ComplianceViolationDict",
    "ProtocolKafkaPublisher",
    "ProtocolLlmClient",
    "build_compliance_prompt",
    "handle_evaluate_compliance",
    "parse_llm_response",
]
