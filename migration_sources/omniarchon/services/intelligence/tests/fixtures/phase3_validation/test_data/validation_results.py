"""
Expected Validation Results

This fixture provides expected validation outputs for testing
validation logic correctness.

Results include:
- ONEX compliance validation results
- Quality gate validation results
- Consensus validation results
"""

from uuid import uuid4

# ============================================================================
# Expected ONEX Validation Results
# ============================================================================

EXPECTED_ONEX_VALIDATION_COMPLIANT = {
    "validation_id": str(uuid4()),
    "timestamp": "2025-10-02T00:00:00Z",
    "code_sample": "NodeDatabaseWriterEffect",
    "validation_type": "onex_compliance",
    "result": {
        "compliant": True,
        "compliance_score": 1.0,
        "violations": [],
        "warnings": [],
        "checks": {
            "naming_convention": {
                "passed": True,
                "details": {
                    "class_name": "NodeDatabaseWriterEffect",
                    "expected_pattern": "Node*Effect",
                    "suffix": "Effect",
                    "prefix": "Node",
                },
            },
            "method_signature": {
                "passed": True,
                "details": {
                    "method_name": "execute_effect",
                    "expected": "execute_effect",
                    "parameters": ["self", "contract"],
                    "return_type": "ModelResult",
                },
            },
            "contract_type": {
                "passed": True,
                "details": {
                    "contract_type": "ModelContractEffect",
                    "expected": "ModelContractEffect",
                    "node_type": "effect",
                },
            },
            "node_type_behavior": {
                "passed": True,
                "details": {
                    "node_type": "effect",
                    "has_io": True,
                    "has_transaction": True,
                    "pure_computation": False,
                },
            },
        },
    },
    "metadata": {
        "validator_version": "1.0.0",
        "execution_time_ms": 45,
    },
}

EXPECTED_ONEX_VALIDATION_NON_COMPLIANT = {
    "validation_id": str(uuid4()),
    "timestamp": "2025-10-02T00:00:00Z",
    "code_sample": "NodeDataTransformerEffect",  # Wrong suffix for pure computation
    "validation_type": "onex_compliance",
    "result": {
        "compliant": False,
        "compliance_score": 0.4,
        "violations": [
            {
                "type": "naming_convention",
                "severity": "critical",
                "message": "Effect node performing pure computation should be Compute node",
                "line": 1,
                "column": 0,
                "suggestion": "Rename to NodeDataTransformerCompute",
            },
            {
                "type": "contract_mismatch",
                "severity": "high",
                "message": "Using ModelContractEffect for pure computation",
                "line": 5,
                "column": 4,
                "suggestion": "Use ModelContractCompute instead",
            },
        ],
        "warnings": [
            {
                "type": "method_complexity",
                "severity": "medium",
                "message": "Method complexity is high (12), consider refactoring",
                "line": 10,
                "column": 4,
            }
        ],
        "checks": {
            "naming_convention": {
                "passed": False,
                "details": {
                    "class_name": "NodeDataTransformerEffect",
                    "expected_pattern": "Node*Compute",
                    "suffix": "Effect",
                    "correct_suffix": "Compute",
                },
            },
            "node_type_behavior": {
                "passed": False,
                "details": {
                    "node_type": "effect",
                    "expected_type": "compute",
                    "has_io": False,  # No I/O operations found
                    "pure_computation": True,  # Only pure computation
                },
            },
        },
    },
    "metadata": {
        "validator_version": "1.0.0",
        "execution_time_ms": 52,
    },
}


# ============================================================================
# Expected Quality Gate Results
# ============================================================================

EXPECTED_QUALITY_GATE_PASS = {
    "gate_id": str(uuid4()),
    "timestamp": "2025-10-02T00:00:00Z",
    "gate_type": "quality_assessment",
    "result": {
        "passed": True,
        "overall_score": 0.92,
        "gates": {
            "test_coverage": {
                "passed": True,
                "score": 0.95,
                "threshold": 0.90,
                "metrics": {
                    "line_coverage": 0.96,
                    "branch_coverage": 0.94,
                    "function_coverage": 1.0,
                },
            },
            "code_quality": {
                "passed": True,
                "score": 0.90,
                "threshold": 0.80,
                "metrics": {
                    "complexity": 8.2,  # avg cyclomatic complexity
                    "duplication": 0.02,  # 2% duplication
                    "maintainability_index": 85,
                },
            },
            "performance": {
                "passed": True,
                "score": 0.91,
                "threshold": 0.85,
                "metrics": {
                    "response_time_p95_ms": 45,
                    "memory_usage_mb": 128,
                    "sla_violations": 0,
                },
            },
        },
    },
    "metadata": {
        "gate_version": "1.0.0",
        "execution_time_ms": 1250,
    },
}

EXPECTED_QUALITY_GATE_FAIL = {
    "gate_id": str(uuid4()),
    "timestamp": "2025-10-02T00:00:00Z",
    "gate_type": "quality_assessment",
    "result": {
        "passed": False,
        "overall_score": 0.62,
        "gates": {
            "test_coverage": {
                "passed": False,
                "score": 0.50,
                "threshold": 0.90,
                "metrics": {
                    "line_coverage": 0.52,
                    "branch_coverage": 0.35,
                    "function_coverage": 0.65,
                },
                "failures": [
                    "Line coverage 52% below threshold 90%",
                    "Branch coverage 35% below threshold 90%",
                ],
            },
            "code_quality": {
                "passed": False,
                "score": 0.65,
                "threshold": 0.80,
                "metrics": {
                    "complexity": 15.8,  # High complexity
                    "duplication": 0.25,  # 25% duplication
                    "maintainability_index": 45,
                },
                "failures": [
                    "Average complexity 15.8 exceeds threshold 10",
                    "Code duplication 25% exceeds threshold 5%",
                ],
            },
            "performance": {
                "passed": True,
                "score": 0.88,
                "threshold": 0.85,
                "metrics": {
                    "response_time_p95_ms": 75,
                    "memory_usage_mb": 256,
                    "sla_violations": 0,
                },
            },
        },
        "blocking_issues": [
            "Test coverage below minimum threshold",
            "Code quality issues require remediation",
        ],
    },
    "metadata": {
        "gate_version": "1.0.0",
        "execution_time_ms": 1580,
    },
}


# ============================================================================
# Expected Consensus Results
# ============================================================================

EXPECTED_CONSENSUS_RESULT_ACHIEVED = {
    "consensus_id": str(uuid4()),
    "timestamp": "2025-10-02T00:00:00Z",
    "consensus_type": "architectural_decision",
    "result": {
        "consensus_reached": True,
        "confidence_score": 0.85,
        "recommendation": "split_to_multiple_nodes",
        "model_responses": [
            {
                "model": "gemini-flash",
                "weight": 1.0,
                "recommendation": "split_to_multiple_nodes",
                "confidence": 0.90,
            },
            {
                "model": "codestral",
                "weight": 1.5,
                "recommendation": "split_to_multiple_nodes",
                "confidence": 0.88,
            },
            {
                "model": "deepseek-lite",
                "weight": 2.0,
                "recommendation": "split_to_multiple_nodes",
                "confidence": 0.85,
            },
            {
                "model": "llama-3.1",
                "weight": 1.2,
                "recommendation": "split_to_multiple_nodes",
                "confidence": 0.82,
            },
            {
                "model": "deepseek-full",
                "weight": 1.8,
                "recommendation": "keep_single_node",
                "confidence": 0.70,
            },
        ],
        "weighted_scores": {
            "split_to_multiple_nodes": 5.64,  # Sum of weights * confidence
            "keep_single_node": 1.26,
        },
        "total_weight": 7.5,
        "participation_rate": 1.0,
    },
    "metadata": {
        "consensus_version": "1.0.0",
        "execution_time_ms": 3450,
        "models_queried": 5,
        "models_responded": 5,
    },
}

EXPECTED_CONSENSUS_RESULT_FAILED = {
    "consensus_id": str(uuid4()),
    "timestamp": "2025-10-02T00:00:00Z",
    "consensus_type": "architectural_decision",
    "result": {
        "consensus_reached": False,
        "confidence_score": 0.52,
        "recommendation": "option_a",  # Barely winning
        "model_responses": [
            {
                "model": "gemini-flash",
                "weight": 1.0,
                "recommendation": "option_a",
                "confidence": 0.75,
            },
            {
                "model": "codestral",
                "weight": 1.5,
                "recommendation": "option_b",
                "confidence": 0.80,
            },
            {
                "model": "deepseek-lite",
                "weight": 2.0,
                "recommendation": "option_a",
                "confidence": 0.70,
            },
            {
                "model": "llama-3.1",
                "weight": 1.2,
                "recommendation": "option_b",
                "confidence": 0.75,
            },
            {
                "model": "deepseek-full",
                "weight": 1.8,
                "recommendation": "option_c",
                "confidence": 0.65,
            },
        ],
        "weighted_scores": {
            "option_a": 2.15,  # (1.0 * 0.75) + (2.0 * 0.70)
            "option_b": 2.10,  # (1.5 * 0.80) + (1.2 * 0.75)
            "option_c": 1.17,  # (1.8 * 0.65)
        },
        "threshold": 0.70,
        "reason": "Confidence score 0.52 below threshold 0.70",
        "recommended_action": "request_human_review",
    },
    "metadata": {
        "consensus_version": "1.0.0",
        "execution_time_ms": 3850,
        "models_queried": 5,
        "models_responded": 5,
    },
}


# ============================================================================
# Expected Multi-Phase Validation Results
# ============================================================================

EXPECTED_MULTI_PHASE_VALIDATION = {
    "validation_id": str(uuid4()),
    "timestamp": "2025-10-02T00:00:00Z",
    "validation_type": "multi_phase",
    "result": {
        "overall_passed": True,
        "phases": {
            "phase_1_onex_compliance": {
                "passed": True,
                "score": 0.95,
                "execution_time_ms": 45,
            },
            "phase_2_quality_gates": {
                "passed": True,
                "score": 0.92,
                "execution_time_ms": 1250,
            },
            "phase_3_consensus": {
                "passed": True,
                "score": 0.85,
                "execution_time_ms": 3450,
            },
        },
        "total_execution_time_ms": 4745,
        "recommendation": "approve",
    },
}


# ============================================================================
# All Expected Results
# ============================================================================

ALL_EXPECTED_RESULTS = {
    "onex_compliant": EXPECTED_ONEX_VALIDATION_COMPLIANT,
    "onex_non_compliant": EXPECTED_ONEX_VALIDATION_NON_COMPLIANT,
    "quality_gate_pass": EXPECTED_QUALITY_GATE_PASS,
    "quality_gate_fail": EXPECTED_QUALITY_GATE_FAIL,
    "consensus_achieved": EXPECTED_CONSENSUS_RESULT_ACHIEVED,
    "consensus_failed": EXPECTED_CONSENSUS_RESULT_FAILED,
    "multi_phase": EXPECTED_MULTI_PHASE_VALIDATION,
}
