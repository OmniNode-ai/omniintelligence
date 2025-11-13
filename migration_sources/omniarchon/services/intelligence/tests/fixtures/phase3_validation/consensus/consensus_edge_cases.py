"""
Consensus Edge Cases for Multi-Model AI Quorum

These fixtures provide edge cases for testing consensus mechanisms:
- Split decisions (50/50)
- Model timeouts
- Model disagreements
- Confidence thresholds
- Tie-breaking scenarios
"""

# ============================================================================
# EDGE CASE 1: Perfect Split Decision
# ============================================================================

EDGE_CASE_SPLIT_DECISION = {
    "case_id": "split_001",
    "title": "Perfect 50/50 Split on Node Type",
    "description": "Models evenly split between Effect and Compute classification",
    "code_sample": '''
    class NodeDataEnricherEffect:
        """Enriches data by calling external API and transforming result."""

        async def execute_effect(self, contract: ModelContractEffect):
            # External API call (Effect behavior)
            external_data = await self.api_client.get(contract.endpoint)

            # Data transformation (Compute behavior)
            enriched = {
                "original": contract.data,
                "external": external_data,
                "combined": self._merge_data(contract.data, external_data),
                "score": self._calculate_score(enriched_data)
            }

            return enriched
    ''',
    "model_responses": [
        {
            "model": "gemini-flash",
            "weight": 1.0,
            "recommendation": "effect",
            "confidence": 0.85,
            "reasoning": "Primary purpose is external API call (I/O operation)",
        },
        {
            "model": "codestral",
            "weight": 1.5,
            "recommendation": "compute",
            "confidence": 0.80,
            "reasoning": "Significant transformation logic, API call is incidental",
        },
        {
            "model": "deepseek-lite",
            "weight": 2.0,
            "recommendation": "effect",
            "confidence": 0.75,
            "reasoning": "Effect node can have transformation, API call is primary",
        },
        {
            "model": "llama-3.1",
            "weight": 1.2,
            "recommendation": "compute",
            "confidence": 0.70,
            "reasoning": "Should separate: Compute for transform, Effect for API",
        },
        {
            "model": "deepseek-full",
            "weight": 1.8,
            "recommendation": "orchestrator",
            "confidence": 0.65,
            "reasoning": "Multiple concerns, should use Orchestrator pattern",
        },
    ],
    "weighted_scores": {
        "effect": 1.0 * 0.85 + 2.0 * 0.75,  # = 2.35
        "compute": 1.5 * 0.80 + 1.2 * 0.70,  # = 2.04
        "orchestrator": 1.8 * 0.65,  # = 1.17
    },
    "consensus_reached": False,
    "winning_option": "effect",
    "confidence_score": 0.43,  # 2.35 / (2.35 + 2.04 + 1.17) = 0.43
    "tie_breaking_needed": True,
    "recommended_action": "request_human_review",
}


# ============================================================================
# EDGE CASE 2: Model Timeout
# ============================================================================

EDGE_CASE_MODEL_TIMEOUT = {
    "case_id": "timeout_001",
    "title": "Model Timeout During Consensus",
    "description": "One or more models timeout during analysis",
    "code_sample": '''
    class NodeComplexProcessorCompute:
        """Complex data processor with multiple algorithms."""

        async def execute_compute(self, contract: ModelContractCompute):
            # Very complex code that takes time to analyze
            # ... 500 lines of code ...
            pass
    ''',
    "model_responses": [
        {
            "model": "gemini-flash",
            "weight": 1.0,
            "recommendation": "approve",
            "confidence": 0.90,
            "reasoning": "ONEX compliant Compute node",
            "response_time_ms": 1200,
        },
        {
            "model": "codestral",
            "weight": 1.5,
            "recommendation": None,  # TIMEOUT
            "confidence": 0.0,
            "reasoning": None,
            "response_time_ms": 30000,  # 30 second timeout
            "error": "Model timeout after 30 seconds",
        },
        {
            "model": "deepseek-lite",
            "weight": 2.0,
            "recommendation": "approve",
            "confidence": 0.85,
            "reasoning": "Compliant implementation",
            "response_time_ms": 2500,
        },
        {
            "model": "llama-3.1",
            "weight": 1.2,
            "recommendation": None,  # TIMEOUT
            "confidence": 0.0,
            "reasoning": None,
            "response_time_ms": 30000,
            "error": "Model timeout after 30 seconds",
        },
        {
            "model": "deepseek-full",
            "weight": 1.8,
            "recommendation": "reject",
            "confidence": 0.75,
            "reasoning": "Found complexity violation in algorithm",
            "response_time_ms": 5000,
        },
    ],
    "available_weight": 1.0 + 2.0 + 1.8,  # = 4.8 (excluding timeouts: 1.5 + 1.2)
    "total_weight": 7.5,
    "participation_rate": 0.64,  # 4.8 / 7.5
    "consensus_with_failures": {
        "approve": (1.0 * 0.90) + (2.0 * 0.85),  # = 2.60
        "reject": 1.8 * 0.75,  # = 1.35
    },
    "consensus_reached": True,  # Despite timeouts
    "winning_option": "approve",
    "confidence_score": 0.66,  # 2.60 / (2.60 + 1.35)
    "degraded_quorum": True,
    "recommended_action": "proceed_with_warning",
}


# ============================================================================
# EDGE CASE 3: Strong Disagreement
# ============================================================================

EDGE_CASE_STRONG_DISAGREEMENT = {
    "case_id": "disagreement_001",
    "title": "Strong Model Disagreement with High Confidence",
    "description": "Models strongly disagree, all with high confidence",
    "code_sample": '''
    class NodeUserAuthenticatorEffect:
        """User authentication with session management."""

        def __init__(self):
            self._session_cache = {}  # In-memory state

        async def execute_effect(self, contract: ModelContractEffect):
            # External auth service call (Effect)
            auth_result = await self.auth_service.authenticate(contract.credentials)

            # State management (Reducer?)
            self._session_cache[contract.user_id] = {
                "token": auth_result.token,
                "expires": auth_result.expires
            }

            return auth_result
    ''',
    "model_responses": [
        {
            "model": "gemini-flash",
            "weight": 1.0,
            "recommendation": "effect_correct",
            "confidence": 0.95,
            "reasoning": "Auth is I/O, caching is incidental, Effect is correct",
        },
        {
            "model": "codestral",
            "weight": 1.5,
            "recommendation": "split_to_reducer",
            "confidence": 0.90,
            "reasoning": "Session management is Reducer responsibility, MUST split",
        },
        {
            "model": "deepseek-lite",
            "weight": 2.0,
            "recommendation": "effect_correct",
            "confidence": 0.85,
            "reasoning": "Simple cache, Effect pattern is acceptable",
        },
        {
            "model": "llama-3.1",
            "weight": 1.2,
            "recommendation": "violation",
            "confidence": 0.92,
            "reasoning": "State mutation in Effect node violates ONEX principles",
        },
        {
            "model": "deepseek-full",
            "weight": 1.8,
            "recommendation": "split_to_reducer",
            "confidence": 0.88,
            "reasoning": "Reducer for session, Effect for auth, clear separation",
        },
    ],
    "high_confidence_threshold": 0.85,
    "all_above_threshold": True,
    "weighted_scores": {
        "effect_correct": (1.0 * 0.95) + (2.0 * 0.85),  # = 2.65
        "split_to_reducer": (1.5 * 0.90) + (1.8 * 0.88),  # = 2.934
        "violation": 1.2 * 0.92,  # = 1.104
    },
    "consensus_reached": False,  # Close scores despite high confidence
    "winning_option": "split_to_reducer",
    "confidence_score": 0.44,  # 2.934 / (2.65 + 2.934 + 1.104) = 0.44
    "requires_detailed_review": True,
    "recommended_action": "escalate_to_architecture_review",
}


# ============================================================================
# EDGE CASE 4: Low Confidence Across Board
# ============================================================================

EDGE_CASE_LOW_CONFIDENCE = {
    "case_id": "low_confidence_001",
    "title": "All Models Have Low Confidence",
    "description": "Ambiguous code, all models uncertain",
    "code_sample": '''
    class NodeDataProcessor:  # Missing type suffix!
        """Process data somehow."""  # Vague description

        async def process(self, data):  # Wrong method name!
            # Is this I/O or computation?
            result = await self.service.call(data)

            # Or is this transformation?
            transformed = self.transform(result)

            # Or is this aggregation?
            self.state.update(transformed)

            return transformed
    ''',
    "model_responses": [
        {
            "model": "gemini-flash",
            "weight": 1.0,
            "recommendation": "unclear",
            "confidence": 0.35,
            "reasoning": "Insufficient context, ambiguous implementation",
        },
        {
            "model": "codestral",
            "weight": 1.5,
            "recommendation": "effect_maybe",
            "confidence": 0.40,
            "reasoning": "Has I/O but also other concerns, unclear",
        },
        {
            "model": "deepseek-lite",
            "weight": 2.0,
            "recommendation": "violations_detected",
            "confidence": 0.50,
            "reasoning": "Multiple ONEX violations, hard to classify",
        },
        {
            "model": "llama-3.1",
            "weight": 1.2,
            "recommendation": "refactor_needed",
            "confidence": 0.45,
            "reasoning": "Code needs refactoring before classification",
        },
        {
            "model": "deepseek-full",
            "weight": 1.8,
            "recommendation": "orchestrator_maybe",
            "confidence": 0.38,
            "reasoning": "Multiple concerns suggest Orchestrator, uncertain",
        },
    ],
    "max_confidence": 0.50,
    "min_confidence_threshold": 0.70,
    "all_below_threshold": True,
    "consensus_reached": False,
    "recommended_action": "request_code_refactoring_and_retry",
    "blocking_issues": [
        "Missing ONEX naming convention",
        "Wrong method signature",
        "Unclear separation of concerns",
        "Insufficient documentation",
    ],
}


# ============================================================================
# EDGE CASE 5: Tie with Different Reasoning
# ============================================================================

EDGE_CASE_TIE_DIFFERENT_REASONING = {
    "case_id": "tie_reasoning_001",
    "title": "Tie Score But Different Reasoning Paths",
    "description": "Same recommendation, completely different reasoning",
    "code_sample": '''
    class NodeNotificationSenderEffect:
        """Send notifications via email, SMS, push."""

        async def execute_effect(self, contract: ModelContractEffect):
            if contract.channel == "email":
                return await self._send_email(contract)
            elif contract.channel == "sms":
                return await self._send_sms(contract)
            elif contract.channel == "push":
                return await self._send_push(contract)
    ''',
    "model_responses": [
        {
            "model": "gemini-flash",
            "weight": 1.0,
            "recommendation": "approve",
            "confidence": 0.85,
            "reasoning": "Simple Effect node, multiple channels is fine, common pattern",
        },
        {
            "model": "codestral",
            "weight": 1.5,
            "recommendation": "split_by_channel",
            "confidence": 0.80,
            "reasoning": "Should have separate Effect nodes per channel for SRP",
        },
        {
            "model": "deepseek-lite",
            "weight": 2.0,
            "recommendation": "approve",
            "confidence": 0.75,
            "reasoning": "Acceptable pragmatic approach, avoid over-engineering",
        },
        {
            "model": "llama-3.1",
            "weight": 1.2,
            "recommendation": "split_by_channel",
            "confidence": 0.82,
            "reasoning": "Better testability, clearer contracts per channel",
        },
    ],
    "weighted_scores": {
        "approve": (1.0 * 0.85) + (2.0 * 0.75),  # = 2.35
        "split_by_channel": (1.5 * 0.80) + (1.2 * 0.82),  # = 2.184
    },
    "score_difference": 0.166,  # Very close!
    "consensus_reached": True,  # But barely
    "winning_option": "approve",
    "confidence_score": 0.52,  # 2.35 / (2.35 + 2.184)
    "reasoning_diversity": "HIGH",  # Same conclusion, different paths
    "recommended_action": "approve_with_alternative_documented",
    "alternative_approaches": ["split_by_channel with reasoning preserved"],
}


# ============================================================================
# All Edge Cases
# ============================================================================

ALL_EDGE_CASES = [
    EDGE_CASE_SPLIT_DECISION,
    EDGE_CASE_MODEL_TIMEOUT,
    EDGE_CASE_STRONG_DISAGREEMENT,
    EDGE_CASE_LOW_CONFIDENCE,
    EDGE_CASE_TIE_DIFFERENT_REASONING,
]


# ============================================================================
# Consensus Resolution Strategies
# ============================================================================

RESOLUTION_STRATEGIES = {
    "split_decision": {
        "threshold": "< 0.60 confidence",
        "action": "request_human_review",
        "escalation": "architecture_team",
    },
    "model_timeout": {
        "min_participation": 0.60,  # Need 60% of weight available
        "action": "proceed_with_available" if "participation >= 0.60" else "retry",
        "degraded_mode": True,
    },
    "strong_disagreement": {
        "threshold": "all >= 0.85 confidence but no consensus",
        "action": "escalate_to_architecture_review",
        "require_documentation": True,
    },
    "low_confidence": {
        "threshold": "all < 0.70 confidence",
        "action": "request_code_refactoring",
        "blocking": True,
    },
    "close_tie": {
        "threshold": "score_difference < 0.20",
        "action": "approve_with_alternative_documented",
        "preserve_reasoning": True,
    },
}
