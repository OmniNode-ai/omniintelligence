"""
Quality Gate Configuration Fixtures

This fixture provides various quality gate configurations
for testing different validation scenarios.

Configurations include:
- Strict quality gates (production)
- Lenient quality gates (development)
- Custom quality gates (project-specific)
- Performance-focused gates
- Security-focused gates
"""

from typing import Any, Dict

# ============================================================================
# Default Quality Gate Configuration
# ============================================================================

DEFAULT_QUALITY_GATE_CONFIG = {
    "config_id": "default",
    "name": "Default Quality Gates",
    "version": "1.0.0",
    "description": "Standard quality gates for ONEX projects",
    "gates": {
        "test_coverage": {
            "enabled": True,
            "thresholds": {
                "line_coverage": 0.90,  # 90% minimum
                "branch_coverage": 0.90,
                "function_coverage": 0.90,
            },
            "weight": 0.30,  # 30% of overall score
            "blocking": True,  # Blocks if fails
        },
        "code_quality": {
            "enabled": True,
            "thresholds": {
                "cyclomatic_complexity_avg": 10,
                "cyclomatic_complexity_max": 15,
                "code_duplication_percent": 5.0,
                "maintainability_index_min": 70,
                "method_length_max": 50,
                "nesting_depth_max": 3,
            },
            "weight": 0.30,
            "blocking": True,
        },
        "performance": {
            "enabled": True,
            "thresholds": {
                "response_time_p95_ms": 100,
                "response_time_p99_ms": 500,
                "memory_usage_max_mb": 512,
                "sla_violations_max": 0,
            },
            "weight": 0.20,
            "blocking": False,  # Warning only
        },
        "security": {
            "enabled": True,
            "thresholds": {
                "critical_vulnerabilities": 0,
                "high_vulnerabilities": 0,
                "medium_vulnerabilities": 5,
            },
            "weight": 0.20,
            "blocking": True,
        },
    },
    "overall_threshold": 0.80,  # Must achieve 80% overall
    "require_all_gates": False,  # Can pass overall even if some gates fail
}


# ============================================================================
# Strict Quality Gate Configuration (Production)
# ============================================================================

STRICT_QUALITY_GATE_CONFIG = {
    "config_id": "strict",
    "name": "Strict Production Quality Gates",
    "version": "1.0.0",
    "description": "Strict quality gates for production deployments",
    "gates": {
        "test_coverage": {
            "enabled": True,
            "thresholds": {
                "line_coverage": 0.95,  # 95% minimum
                "branch_coverage": 0.95,
                "function_coverage": 0.95,
                "mutation_score": 0.80,  # Mutation testing
            },
            "weight": 0.35,
            "blocking": True,
        },
        "code_quality": {
            "enabled": True,
            "thresholds": {
                "cyclomatic_complexity_avg": 8,  # Stricter
                "cyclomatic_complexity_max": 12,
                "code_duplication_percent": 3.0,
                "maintainability_index_min": 80,
                "method_length_max": 40,
                "nesting_depth_max": 3,
                "cognitive_complexity_max": 10,
            },
            "weight": 0.35,
            "blocking": True,
        },
        "performance": {
            "enabled": True,
            "thresholds": {
                "response_time_p50_ms": 20,
                "response_time_p95_ms": 50,
                "response_time_p99_ms": 100,
                "memory_usage_max_mb": 256,
                "sla_violations_max": 0,
                "throughput_min_rps": 1000,
            },
            "weight": 0.15,
            "blocking": True,  # Strict performance
        },
        "security": {
            "enabled": True,
            "thresholds": {
                "critical_vulnerabilities": 0,
                "high_vulnerabilities": 0,
                "medium_vulnerabilities": 0,  # Zero tolerance
                "low_vulnerabilities": 10,
            },
            "weight": 0.15,
            "blocking": True,
        },
    },
    "overall_threshold": 0.90,  # 90% minimum
    "require_all_gates": True,  # All gates must pass
}


# ============================================================================
# Lenient Quality Gate Configuration (Development)
# ============================================================================

LENIENT_QUALITY_GATE_CONFIG = {
    "config_id": "lenient",
    "name": "Lenient Development Quality Gates",
    "version": "1.0.0",
    "description": "Lenient quality gates for rapid development",
    "gates": {
        "test_coverage": {
            "enabled": True,
            "thresholds": {
                "line_coverage": 0.70,  # More lenient
                "branch_coverage": 0.70,
                "function_coverage": 0.80,
            },
            "weight": 0.25,
            "blocking": False,  # Warning only
        },
        "code_quality": {
            "enabled": True,
            "thresholds": {
                "cyclomatic_complexity_avg": 15,
                "cyclomatic_complexity_max": 20,
                "code_duplication_percent": 10.0,
                "maintainability_index_min": 50,
                "method_length_max": 80,
                "nesting_depth_max": 4,
            },
            "weight": 0.25,
            "blocking": False,
        },
        "performance": {
            "enabled": False,  # Disabled for dev
        },
        "security": {
            "enabled": True,
            "thresholds": {
                "critical_vulnerabilities": 0,
                "high_vulnerabilities": 5,  # More lenient
                "medium_vulnerabilities": 20,
            },
            "weight": 0.50,  # Higher weight on security
            "blocking": True,  # Still block on security
        },
    },
    "overall_threshold": 0.60,  # 60% minimum
    "require_all_gates": False,
}


# ============================================================================
# Performance-Focused Quality Gate Configuration
# ============================================================================

PERFORMANCE_FOCUSED_GATE_CONFIG = {
    "config_id": "performance",
    "name": "Performance-Focused Quality Gates",
    "version": "1.0.0",
    "description": "Quality gates focused on performance optimization",
    "gates": {
        "test_coverage": {
            "enabled": True,
            "thresholds": {
                "line_coverage": 0.85,
                "branch_coverage": 0.85,
            },
            "weight": 0.15,
            "blocking": False,
        },
        "code_quality": {
            "enabled": True,
            "thresholds": {
                "cyclomatic_complexity_avg": 10,
                "code_duplication_percent": 5.0,
            },
            "weight": 0.15,
            "blocking": False,
        },
        "performance": {
            "enabled": True,
            "thresholds": {
                "response_time_p50_ms": 10,  # Very strict
                "response_time_p95_ms": 25,
                "response_time_p99_ms": 50,
                "memory_usage_max_mb": 128,  # Low memory
                "cpu_usage_max_percent": 50,
                "throughput_min_rps": 5000,  # High throughput
                "cache_hit_rate_min": 0.90,
                "db_query_time_max_ms": 10,
            },
            "weight": 0.60,  # 60% weight on performance
            "blocking": True,
            "performance_sla": {
                "p95_response_time_ms": 25,
                "p99_response_time_ms": 50,
                "availability_percent": 99.9,
            },
        },
        "scalability": {
            "enabled": True,
            "thresholds": {
                "horizontal_scaling_factor": 10,  # Can scale to 10x
                "memory_leak_rate_mb_per_hour": 0,
                "connection_pool_efficiency": 0.95,
            },
            "weight": 0.10,
            "blocking": False,
        },
    },
    "overall_threshold": 0.85,
    "require_all_gates": False,
}


# ============================================================================
# Security-Focused Quality Gate Configuration
# ============================================================================

SECURITY_FOCUSED_GATE_CONFIG = {
    "config_id": "security",
    "name": "Security-Focused Quality Gates",
    "version": "1.0.0",
    "description": "Quality gates focused on security and compliance",
    "gates": {
        "security": {
            "enabled": True,
            "thresholds": {
                "critical_vulnerabilities": 0,
                "high_vulnerabilities": 0,
                "medium_vulnerabilities": 0,
                "low_vulnerabilities": 5,
                "dependency_vulnerabilities": 0,
                "code_injection_risks": 0,
                "authentication_issues": 0,
                "authorization_issues": 0,
                "data_exposure_risks": 0,
            },
            "weight": 0.60,
            "blocking": True,
        },
        "code_quality": {
            "enabled": True,
            "thresholds": {
                "security_hotspots": 0,
                "input_validation_coverage": 1.0,
                "error_handling_coverage": 1.0,
                "sensitive_data_logging": 0,
            },
            "weight": 0.20,
            "blocking": True,
        },
        "compliance": {
            "enabled": True,
            "thresholds": {
                "license_compliance": True,
                "gdpr_compliance": True,
                "pci_compliance": True,
                "api_security_score": 0.95,
            },
            "weight": 0.20,
            "blocking": True,
        },
    },
    "overall_threshold": 0.95,
    "require_all_gates": True,
}


# ============================================================================
# ONEX-Specific Quality Gate Configuration
# ============================================================================

ONEX_QUALITY_GATE_CONFIG = {
    "config_id": "onex",
    "name": "ONEX Architecture Quality Gates",
    "version": "1.0.0",
    "description": "Quality gates specific to ONEX architecture compliance",
    "gates": {
        "onex_compliance": {
            "enabled": True,
            "thresholds": {
                "naming_convention_compliance": 1.0,
                "contract_compliance": 1.0,
                "node_type_correctness": 1.0,
                "method_signature_compliance": 1.0,
                "io_purity_compliance": 1.0,  # Compute nodes must be pure
            },
            "weight": 0.40,
            "blocking": True,
        },
        "architectural_patterns": {
            "enabled": True,
            "thresholds": {
                "effect_has_io": 1.0,  # Effect nodes must have I/O
                "compute_is_pure": 1.0,  # Compute must be pure
                "reducer_manages_state": 1.0,
                "orchestrator_coordinates": 1.0,
                "transaction_management": 1.0,
            },
            "weight": 0.30,
            "blocking": True,
        },
        "test_coverage": {
            "enabled": True,
            "thresholds": {
                "line_coverage": 0.90,
                "branch_coverage": 0.90,
                "contract_validation_tests": 1.0,
            },
            "weight": 0.20,
            "blocking": True,
        },
        "documentation": {
            "enabled": True,
            "thresholds": {
                "docstring_coverage": 1.0,
                "contract_documentation": 1.0,
                "node_purpose_clarity": 0.90,
            },
            "weight": 0.10,
            "blocking": False,
        },
    },
    "overall_threshold": 0.95,
    "require_all_gates": True,
    "onex_specific": {
        "enforce_suffix_naming": True,
        "enforce_contract_types": True,
        "enforce_method_signatures": True,
        "check_io_purity": True,
    },
}


# ============================================================================
# All Configurations
# ============================================================================

ALL_QUALITY_GATE_CONFIGS = {
    "default": DEFAULT_QUALITY_GATE_CONFIG,
    "strict": STRICT_QUALITY_GATE_CONFIG,
    "lenient": LENIENT_QUALITY_GATE_CONFIG,
    "performance": PERFORMANCE_FOCUSED_GATE_CONFIG,
    "security": SECURITY_FOCUSED_GATE_CONFIG,
    "onex": ONEX_QUALITY_GATE_CONFIG,
}


# ============================================================================
# Helper Functions
# ============================================================================


def get_gate_config(config_id: str = "default") -> Dict[str, Any]:
    """Get quality gate configuration by ID."""
    return ALL_QUALITY_GATE_CONFIGS.get(config_id, DEFAULT_QUALITY_GATE_CONFIG)


def merge_gate_configs(
    base_config_id: str, overrides: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge a base configuration with custom overrides."""
    base_config = get_gate_config(base_config_id).copy()

    # Deep merge overrides
    for key, value in overrides.items():
        if (
            key in base_config
            and isinstance(base_config[key], dict)
            and isinstance(value, dict)
        ):
            base_config[key].update(value)
        else:
            base_config[key] = value

    return base_config
