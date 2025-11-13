#!/usr/bin/env python3
"""
Quality Gates Configuration Validator

Validates quality_gates.yaml configuration files against the JSON schema
and performs additional semantic validation.

Usage:
    python validate_config.py                     # Validate main config
    python validate_config.py --env development   # Validate dev config
    python validate_config.py --all               # Validate all configs
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml
except ImportError:
    print("❌ PyYAML not installed. Install with: pip install pyyaml")
    sys.exit(1)

try:
    from jsonschema import SchemaError, ValidationError, validate
except ImportError:
    print("❌ jsonschema not installed. Install with: pip install jsonschema")
    sys.exit(1)


class Colors:
    """Terminal colors for output"""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


class ConfigValidator:
    """Validates quality gates configuration files"""

    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path(__file__).parent
        self.schema_path = self.config_dir / "quality_gates.schema.json"
        self.main_config_path = self.config_dir / "quality_gates.yaml"
        self.env_configs = {
            "development": self.config_dir / "environments" / "development.yaml",
            "staging": self.config_dir / "environments" / "staging.yaml",
            "production": self.config_dir / "environments" / "production.yaml",
        }

    def load_yaml(self, path: Path) -> Dict[str, Any]:
        """Load and parse YAML file"""
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parsing error: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {path}")

    def load_schema(self) -> Dict[str, Any]:
        """Load JSON schema"""
        try:
            with open(self.schema_path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON schema parsing error: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Schema file not found: {self.schema_path}")

    def validate_against_schema(
        self, config: Dict[str, Any], schema: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate configuration against JSON schema"""
        errors = []
        try:
            validate(instance=config, schema=schema)
            return True, []
        except ValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
            if e.path:
                path_str = ".".join(str(p) for p in e.path)
                errors.append(f"  Location: {path_str}")
            return False, errors
        except SchemaError as e:
            errors.append(f"Invalid schema: {e.message}")
            return False, errors

    def validate_thresholds(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate threshold values are reasonable"""
        warnings = []

        # Check ONEX compliance threshold
        onex_threshold = (
            config.get("quality_gates", {}).get("onex_compliance", {}).get("threshold")
        )
        if onex_threshold and onex_threshold < 0.7:
            warnings.append(
                f"⚠️  ONEX compliance threshold {onex_threshold} is quite low (recommended: ≥0.75)"
            )

        # Check test coverage threshold
        coverage_threshold = (
            config.get("quality_gates", {}).get("test_coverage", {}).get("threshold")
        )
        if coverage_threshold and coverage_threshold < 0.7:
            warnings.append(
                f"⚠️  Test coverage threshold {coverage_threshold} is quite low (recommended: ≥0.80)"
            )

        # Check code quality threshold
        quality_threshold = (
            config.get("quality_gates", {}).get("code_quality", {}).get("threshold")
        )
        if quality_threshold and quality_threshold < 0.5:
            warnings.append(
                f"⚠️  Code quality threshold {quality_threshold} is very low (recommended: ≥0.60)"
            )

        return len(warnings) == 0, warnings

    def validate_consensus_models(
        self, config: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate multi-model consensus configuration"""
        errors = []

        consensus = config.get("quality_gates", {}).get("multi_model_consensus", {})
        if not consensus.get("enabled"):
            return True, []

        models = consensus.get("models", [])
        if len(models) < 2:
            errors.append("❌ Multi-model consensus requires at least 2 models")

        # Calculate total weight
        total_weight = sum(
            model.get("weight", 0) for model in models if model.get("enabled")
        )
        if total_weight == 0:
            errors.append(
                "❌ Total model weight is 0 - at least one model must be enabled"
            )

        # Check consensus threshold is achievable
        threshold = consensus.get("consensus_threshold", 0.67)
        if threshold > 1.0 or threshold < 0:
            errors.append(f"❌ Consensus threshold {threshold} must be between 0 and 1")

        return len(errors) == 0, errors

    def validate_environment_overrides(
        self, main_config: Dict[str, Any], env_config: Dict[str, Any], env_name: str
    ) -> Tuple[bool, List[str]]:
        """Validate environment configuration is more relaxed or equal to main config"""
        warnings = []

        # Development should be more relaxed than production
        if env_name == "development":
            main_gates = main_config.get("quality_gates", {})
            env_gates = env_config.get("quality_gates", {})

            # Check ONEX threshold
            main_onex = main_gates.get("onex_compliance", {}).get("threshold", 0.95)
            env_onex = env_gates.get("onex_compliance", {}).get("threshold", 0.95)
            if env_onex > main_onex:
                warnings.append(
                    f"⚠️  Development ONEX threshold ({env_onex}) is stricter than main ({main_onex})"
                )

            # Check test coverage
            main_coverage = main_gates.get("test_coverage", {}).get("threshold", 0.90)
            env_coverage = env_gates.get("test_coverage", {}).get("threshold", 0.90)
            if env_coverage > main_coverage:
                warnings.append(
                    f"⚠️  Development coverage threshold ({env_coverage}) is stricter than main ({main_coverage})"
                )

        return len(warnings) == 0, warnings

    def validate_file(
        self, path: Path, env_name: str = None
    ) -> Tuple[bool, List[str], List[str]]:
        """Validate a single configuration file"""
        errors = []
        warnings = []

        # Load configuration
        try:
            config = self.load_yaml(path)
        except Exception as e:
            errors.append(f"❌ Failed to load configuration: {e}")
            return False, errors, warnings

        # Load schema
        try:
            schema = self.load_schema()
        except Exception as e:
            errors.append(f"❌ Failed to load schema: {e}")
            return False, errors, warnings

        # Validate against schema
        schema_valid, schema_errors = self.validate_against_schema(config, schema)
        if not schema_valid:
            errors.extend(schema_errors)

        # Validate thresholds
        thresholds_valid, threshold_warnings = self.validate_thresholds(config)
        warnings.extend(threshold_warnings)

        # Validate consensus models
        consensus_valid, consensus_errors = self.validate_consensus_models(config)
        if not consensus_valid:
            errors.extend(consensus_errors)

        # Validate environment overrides
        if env_name and env_name == "development":
            try:
                main_config = self.load_yaml(self.main_config_path)
                env_valid, env_warnings = self.validate_environment_overrides(
                    main_config, config, env_name
                )
                warnings.extend(env_warnings)
            except Exception as e:
                warnings.append(f"⚠️  Could not validate environment overrides: {e}")

        return len(errors) == 0, errors, warnings

    def print_results(
        self, path: Path, valid: bool, errors: List[str], warnings: List[str]
    ):
        """Print validation results"""
        status = (
            f"{Colors.GREEN}✅ VALID{Colors.END}"
            if valid
            else f"{Colors.RED}❌ INVALID{Colors.END}"
        )
        print(f"\n{Colors.BOLD}{path.name}{Colors.END}: {status}")

        if errors:
            print(f"\n{Colors.RED}Errors:{Colors.END}")
            for error in errors:
                print(f"  {error}")

        if warnings:
            print(f"\n{Colors.YELLOW}Warnings:{Colors.END}")
            for warning in warnings:
                print(f"  {warning}")

        if valid and not warnings:
            print(
                f"  {Colors.GREEN}Configuration is valid with no warnings{Colors.END}"
            )

    def validate_main(self) -> bool:
        """Validate main configuration"""
        print(f"{Colors.BOLD}Validating Main Configuration{Colors.END}")
        print(f"{'=' * 60}")

        valid, errors, warnings = self.validate_file(self.main_config_path)
        self.print_results(self.main_config_path, valid, errors, warnings)
        return valid

    def validate_environment(self, env_name: str) -> bool:
        """Validate environment-specific configuration"""
        print(f"\n{Colors.BOLD}Validating {env_name.title()} Environment{Colors.END}")
        print(f"{'=' * 60}")

        env_path = self.env_configs.get(env_name)
        if not env_path or not env_path.exists():
            print(f"{Colors.RED}❌ Configuration not found: {env_path}{Colors.END}")
            return False

        valid, errors, warnings = self.validate_file(env_path, env_name)
        self.print_results(env_path, valid, errors, warnings)
        return valid

    def validate_all(self) -> bool:
        """Validate all configurations"""
        print(
            f"\n{Colors.BLUE}{Colors.BOLD}Quality Gates Configuration Validation{Colors.END}"
        )
        print(f"{'=' * 60}")

        all_valid = True

        # Validate main config
        all_valid &= self.validate_main()

        # Validate all environment configs
        for env_name in ["development", "staging", "production"]:
            all_valid &= self.validate_environment(env_name)

        # Print summary
        print(f"\n{Colors.BOLD}Summary{Colors.END}")
        print(f"{'=' * 60}")
        if all_valid:
            print(f"{Colors.GREEN}✅ All configurations are valid{Colors.END}")
        else:
            print(f"{Colors.RED}❌ Some configurations have errors{Colors.END}")

        return all_valid


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Validate quality gates configuration files"
    )
    parser.add_argument(
        "--env",
        choices=["development", "staging", "production"],
        help="Validate specific environment configuration",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all configurations (main + all environments)",
    )

    args = parser.parse_args()

    validator = ConfigValidator()

    if args.all:
        success = validator.validate_all()
    elif args.env:
        success = validator.validate_environment(args.env)
    else:
        success = validator.validate_main()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
