#!/usr/bin/env python3
"""
Intelligence Hook Validation Script

Validates intelligence hook configuration across multiple repositories to prevent
the issues encountered with missing scripts and broken git hooks.

This script:
1. Discovers repositories that use intelligence hooks
2. Validates hook configuration and script presence
3. Provides automated fixes for common issues
4. Generates validation reports

Usage:
    python3 validate_intelligence_hooks.py --scan /Volumes/PRO-G40/Code
    python3 validate_intelligence_hooks.py --repo /path/to/repo --fix
    python3 validate_intelligence_hooks.py --validate-all --auto-fix
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("intelligence_hook_validator")


class IntelligenceHookValidator:
    """Validates intelligence hook configuration across repositories."""

    def __init__(self, base_path: str = "/Volumes/PRO-G40/Code"):
        self.base_path = Path(base_path)
        self.archon_path = self.base_path / "Archon"
        self.validation_results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repositories": [],
            "summary": {
                "total_repos": 0,
                "valid_repos": 0,
                "invalid_repos": 0,
                "fixed_repos": 0,
                "issues_found": [],
            },
        }

        # Reference files from Archon
        self.reference_files = {
            "intelligence_hook.py": self.archon_path
            / "scripts"
            / "intelligence_hook.py",
            "intelligence_hook_poetry.py": self.archon_path
            / "scripts"
            / "intelligence_hook_poetry.py",
            "pre-push": self.archon_path / ".git" / "hooks" / "pre-push",
        }

    def print_status(self, message: str, level: str = "info"):
        """Print status message with appropriate emoji."""
        emojis = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "fix": "🔧",
            "search": "🔍",
        }
        emoji = emojis.get(level, "ℹ️")
        print(f"{emoji} {message}")

        if level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)
        else:
            logger.info(message)

    def discover_repositories(self, scan_path: Optional[str] = None) -> List[Path]:
        """Discover git repositories that might use intelligence hooks."""
        scan_path = Path(scan_path) if scan_path else self.base_path
        repositories = []

        self.print_status(f"Scanning for git repositories in: {scan_path}", "search")

        for item in scan_path.iterdir():
            if not item.is_dir() or item.name.startswith("."):
                continue

            git_dir = item / ".git"
            if git_dir.exists():
                # Check if repository has hooks or references intelligence hooks
                if self.has_intelligence_hook_references(item):
                    repositories.append(item)
                    self.print_status(
                        f"Found repository with intelligence hooks: {item.name}"
                    )

        return repositories

    def has_intelligence_hook_references(self, repo_path: Path) -> bool:
        """Check if repository has intelligence hook references."""
        indicators = [
            # Git hooks
            repo_path / ".git" / "hooks" / "pre-push",
            repo_path / ".git" / "hooks" / "intelligence_hook.py",
            repo_path / ".git" / "hooks" / "intelligence_hook_poetry.py",
            # Script references
            repo_path / "scripts" / "intelligence_hook.py",
            # Pre-commit configs that might reference intelligence
        ]

        for indicator in indicators:
            if indicator.exists():
                if "intelligence" in indicator.read_text(errors="ignore").lower():
                    return True

        # Check for pre-push hook content
        pre_push = repo_path / ".git" / "hooks" / "pre-push"
        if pre_push.exists():
            content = pre_push.read_text(errors="ignore")
            if "intelligence" in content.lower():
                return True

        return False

    def validate_repository(self, repo_path: Path) -> Dict[str, Any]:
        """Validate intelligence hook configuration for a single repository."""
        repo_name = repo_path.name
        validation_result = {
            "name": repo_name,
            "path": str(repo_path),
            "valid": True,
            "issues": [],
            "warnings": [],
            "fixes_applied": [],
            "components": {
                "pre_push_hook": {"exists": False, "valid": False, "path": ""},
                "intelligence_hook_script": {
                    "exists": False,
                    "valid": False,
                    "path": "",
                },
                "poetry_wrapper": {"exists": False, "valid": False, "path": ""},
                "scripts_directory": {"exists": False, "valid": False, "path": ""},
            },
        }

        self.print_status(f"Validating repository: {repo_name}")

        # 1. Check pre-push hook
        self._validate_pre_push_hook(repo_path, validation_result)

        # 2. Check intelligence hook script in scripts/
        self._validate_intelligence_script(repo_path, validation_result)

        # 3. Check poetry wrapper in git hooks
        self._validate_poetry_wrapper(repo_path, validation_result)

        # 4. Check scripts directory structure
        self._validate_scripts_directory(repo_path, validation_result)

        # 5. Validate hook execution chain
        self._validate_hook_execution_chain(repo_path, validation_result)

        # Determine overall validity
        critical_components = ["pre_push_hook", "intelligence_hook_script"]
        validation_result["valid"] = all(
            validation_result["components"][comp]["valid"]
            for comp in critical_components
        )

        if not validation_result["valid"]:
            self.validation_results["summary"]["invalid_repos"] += 1
        else:
            self.validation_results["summary"]["valid_repos"] += 1

        return validation_result

    def _validate_pre_push_hook(self, repo_path: Path, result: Dict[str, Any]):
        """Validate pre-push hook configuration."""
        pre_push_path = repo_path / ".git" / "hooks" / "pre-push"
        component = result["components"]["pre_push_hook"]

        component["path"] = str(pre_push_path)
        component["exists"] = pre_push_path.exists()

        if not component["exists"]:
            result["issues"].append("Pre-push hook not found")
            return

        # Check if executable
        if not os.access(pre_push_path, os.X_OK):
            result["issues"].append("Pre-push hook is not executable")
            component["valid"] = False
            return

        # Check content
        try:
            content = pre_push_path.read_text()
            if "intelligence" not in content.lower():
                result["warnings"].append(
                    "Pre-push hook does not reference intelligence"
                )
                component["valid"] = False
                return

            # Check for proper script path references
            if "intelligence_hook_poetry.py" in content:
                component["valid"] = True
            else:
                result["issues"].append(
                    "Pre-push hook does not reference poetry wrapper correctly"
                )
                component["valid"] = False

        except Exception as e:
            result["issues"].append(f"Error reading pre-push hook: {e}")
            component["valid"] = False

    def _validate_intelligence_script(self, repo_path: Path, result: Dict[str, Any]):
        """Validate intelligence hook script in scripts directory."""
        script_path = repo_path / "scripts" / "intelligence_hook.py"
        component = result["components"]["intelligence_hook_script"]

        component["path"] = str(script_path)
        component["exists"] = script_path.exists()

        if not component["exists"]:
            result["issues"].append("Intelligence hook script not found in scripts/")
            return

        # Check if executable
        if not os.access(script_path, os.X_OK):
            result["issues"].append("Intelligence hook script is not executable")

        # Check script content validity
        try:
            content = script_path.read_text()

            # Basic validation checks
            if "IntelligenceHookConfig" in content or "intelligence" in content.lower():
                component["valid"] = True
            else:
                result["warnings"].append(
                    "Intelligence script may be invalid or outdated"
                )

        except Exception as e:
            result["issues"].append(f"Error reading intelligence script: {e}")

    def _validate_poetry_wrapper(self, repo_path: Path, result: Dict[str, Any]):
        """Validate poetry wrapper in git hooks."""
        wrapper_path = repo_path / ".git" / "hooks" / "intelligence_hook_poetry.py"
        component = result["components"]["poetry_wrapper"]

        component["path"] = str(wrapper_path)
        component["exists"] = wrapper_path.exists()

        if not component["exists"]:
            result["warnings"].append("Poetry wrapper not found in git hooks")
            return

        # Check if executable
        if not os.access(wrapper_path, os.X_OK):
            result["issues"].append("Poetry wrapper is not executable")

        # Check wrapper functionality
        try:
            content = wrapper_path.read_text()
            if "find_archon_root" in content and "poetry run" in content:
                component["valid"] = True
            else:
                result["issues"].append("Poetry wrapper appears invalid or outdated")

        except Exception as e:
            result["issues"].append(f"Error reading poetry wrapper: {e}")

    def _validate_scripts_directory(self, repo_path: Path, result: Dict[str, Any]):
        """Validate scripts directory structure."""
        scripts_path = repo_path / "scripts"
        component = result["components"]["scripts_directory"]

        component["path"] = str(scripts_path)
        component["exists"] = scripts_path.exists()

        if not component["exists"]:
            result["issues"].append("Scripts directory does not exist")
            return

        component["valid"] = scripts_path.is_dir()
        if not component["valid"]:
            result["issues"].append("Scripts path exists but is not a directory")

    def _validate_hook_execution_chain(self, repo_path: Path, result: Dict[str, Any]):
        """Validate the complete hook execution chain."""
        # Test if the hook chain would work
        try:
            # Simulate hook execution without actually running it
            pre_push = repo_path / ".git" / "hooks" / "pre-push"
            if pre_push.exists():
                content = pre_push.read_text()

                # Check for common path issues
                if (
                    "/Volumes/PRO-G40/Code/omniagent/scripts/intelligence_hook.py"
                    in content
                ):
                    result["issues"].append(
                        "Pre-push hook has hardcoded omniagent path"
                    )

        except Exception as e:
            result["warnings"].append(f"Could not validate execution chain: {e}")

    def fix_repository(
        self, repo_path: Path, validation_result: Dict[str, Any]
    ) -> bool:
        """Attempt to fix issues in a repository."""
        fixes_applied = []
        repo_name = repo_path.name

        self.print_status(f"Applying fixes to repository: {repo_name}", "fix")

        try:
            # Fix 1: Copy missing intelligence hook script
            if not validation_result["components"]["intelligence_hook_script"][
                "exists"
            ]:
                self._fix_missing_intelligence_script(repo_path, fixes_applied)

            # Fix 2: Copy missing poetry wrapper
            if not validation_result["components"]["poetry_wrapper"]["exists"]:
                self._fix_missing_poetry_wrapper(repo_path, fixes_applied)

            # Fix 3: Fix pre-push hook
            if not validation_result["components"]["pre_push_hook"]["valid"]:
                self._fix_pre_push_hook(repo_path, fixes_applied)

            # Fix 4: Create scripts directory if missing
            if not validation_result["components"]["scripts_directory"]["exists"]:
                self._fix_missing_scripts_directory(repo_path, fixes_applied)

            # Fix 5: Set proper permissions
            self._fix_permissions(repo_path, fixes_applied)

            validation_result["fixes_applied"] = fixes_applied

            if fixes_applied:
                self.validation_results["summary"]["fixed_repos"] += 1
                self.print_status(
                    f"Applied {len(fixes_applied)} fixes to {repo_name}", "success"
                )
                return True
            else:
                self.print_status(f"No fixes needed for {repo_name}")
                return False

        except Exception as e:
            self.print_status(f"Error applying fixes to {repo_name}: {e}", "error")
            return False

    def _fix_missing_intelligence_script(
        self, repo_path: Path, fixes_applied: List[str]
    ):
        """Copy intelligence hook script from Archon."""
        source = self.reference_files["intelligence_hook.py"]
        dest = repo_path / "scripts" / "intelligence_hook.py"

        if source.exists():
            dest.parent.mkdir(exist_ok=True)
            shutil.copy2(source, dest)
            os.chmod(dest, 0o755)  # Make executable
            fixes_applied.append(f"Copied intelligence_hook.py to {dest}")
        else:
            raise FileNotFoundError(
                f"Reference intelligence script not found: {source}"
            )

    def _fix_missing_poetry_wrapper(self, repo_path: Path, fixes_applied: List[str]):
        """Copy poetry wrapper from Archon."""
        source = self.reference_files["intelligence_hook_poetry.py"]
        dest = repo_path / ".git" / "hooks" / "intelligence_hook_poetry.py"

        if source.exists():
            shutil.copy2(source, dest)
            os.chmod(dest, 0o755)  # Make executable
            fixes_applied.append(f"Copied intelligence_hook_poetry.py to {dest}")
        else:
            raise FileNotFoundError(f"Reference poetry wrapper not found: {source}")

    def _fix_pre_push_hook(self, repo_path: Path, fixes_applied: List[str]):
        """Fix or create pre-push hook."""
        source = self.reference_files["pre-push"]
        dest = repo_path / ".git" / "hooks" / "pre-push"

        if source.exists():
            shutil.copy2(source, dest)
            os.chmod(dest, 0o755)  # Make executable
            fixes_applied.append(f"Fixed pre-push hook at {dest}")
        else:
            # Create a basic pre-push hook
            hook_content = """#!/bin/bash
#
# Intelligence Pre-Push Hook (Python Version)
#
# Calls the Python intelligence hook via Poetry wrapper
# This ensures all dependencies are properly loaded
#

set -e

# Find the intelligence hook poetry wrapper
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTELLIGENCE_HOOK="$SCRIPT_DIR/intelligence_hook_poetry.py"

# Check if the Python wrapper exists
if [ ! -f "$INTELLIGENCE_HOOK" ]; then
    echo "⚠️  Intelligence hook not found: $INTELLIGENCE_HOOK"
    echo "ℹ️  Skipping intelligence analysis"
    exit 0
fi

# Run the intelligence hook
echo "🧠 Running intelligence analysis..."
python3 "$INTELLIGENCE_HOOK" "$@"

echo "✅ Intelligence analysis complete"
"""
            dest.write_text(hook_content)
            os.chmod(dest, 0o755)
            fixes_applied.append(f"Created pre-push hook at {dest}")

    def _fix_missing_scripts_directory(self, repo_path: Path, fixes_applied: List[str]):
        """Create scripts directory if missing."""
        scripts_dir = repo_path / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        fixes_applied.append(f"Created scripts directory at {scripts_dir}")

    def _fix_permissions(self, repo_path: Path, fixes_applied: List[str]):
        """Fix file permissions for hook files."""
        files_to_fix = [
            repo_path / "scripts" / "intelligence_hook.py",
            repo_path / ".git" / "hooks" / "intelligence_hook_poetry.py",
            repo_path / ".git" / "hooks" / "pre-push",
        ]

        for file_path in files_to_fix:
            if file_path.exists() and not os.access(file_path, os.X_OK):
                os.chmod(file_path, 0o755)
                fixes_applied.append(f"Fixed permissions for {file_path.name}")

    def validate_all_repositories(
        self, scan_path: Optional[str] = None, auto_fix: bool = False
    ) -> Dict[str, Any]:
        """Validate all repositories in the scan path."""
        repositories = self.discover_repositories(scan_path)
        self.validation_results["summary"]["total_repos"] = len(repositories)

        self.print_status(f"Validating {len(repositories)} repositories")

        for repo_path in repositories:
            try:
                result = self.validate_repository(repo_path)

                if auto_fix and not result["valid"]:
                    self.fix_repository(repo_path, result)
                    # Re-validate after fixes
                    result = self.validate_repository(repo_path)

                self.validation_results["repositories"].append(result)

            except Exception as e:
                error_result = {
                    "name": repo_path.name,
                    "path": str(repo_path),
                    "valid": False,
                    "issues": [f"Validation error: {e}"],
                    "warnings": [],
                    "fixes_applied": [],
                }
                self.validation_results["repositories"].append(error_result)
                self.print_status(f"Error validating {repo_path.name}: {e}", "error")

        return self.validation_results

    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate a comprehensive validation report."""
        report_content = [
            "# Intelligence Hook Validation Report",
            f"Generated: {self.validation_results['timestamp']}",
            "",
            "## Summary",
            f"- Total Repositories: {self.validation_results['summary']['total_repos']}",
            f"- Valid Repositories: {self.validation_results['summary']['valid_repos']}",
            f"- Invalid Repositories: {self.validation_results['summary']['invalid_repos']}",
            f"- Fixed Repositories: {self.validation_results['summary']['fixed_repos']}",
            "",
            "## Repository Details",
            "",
        ]

        for repo in self.validation_results["repositories"]:
            status = "✅ VALID" if repo["valid"] else "❌ INVALID"
            report_content.append(f"### {repo['name']} - {status}")
            report_content.append(f"Path: `{repo['path']}`")

            if repo["issues"]:
                report_content.append("**Issues:**")
                for issue in repo["issues"]:
                    report_content.append(f"- ❌ {issue}")

            if repo["warnings"]:
                report_content.append("**Warnings:**")
                for warning in repo["warnings"]:
                    report_content.append(f"- ⚠️ {warning}")

            if repo["fixes_applied"]:
                report_content.append("**Fixes Applied:**")
                for fix in repo["fixes_applied"]:
                    report_content.append(f"- 🔧 {fix}")

            report_content.append("")

        report_text = "\n".join(report_content)

        if output_file:
            Path(output_file).write_text(report_text)
            self.print_status(f"Report saved to: {output_file}")

        return report_text

    def test_hook_execution(self, repo_path: Path) -> Dict[str, Any]:
        """Test intelligence hook execution without actually running git push."""
        test_result = {
            "repo_name": repo_path.name,
            "executable": False,
            "dependencies_available": False,
            "config_valid": False,
            "test_output": "",
            "errors": [],
        }

        try:
            # Test if the poetry wrapper can find required components
            wrapper = repo_path / ".git" / "hooks" / "intelligence_hook_poetry.py"
            if wrapper.exists():
                # Simulate wrapper execution
                result = subprocess.run(
                    ["python3", str(wrapper), "--test-mode"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                test_result["executable"] = result.returncode == 0
                test_result["test_output"] = result.stdout + result.stderr

                if result.returncode != 0:
                    test_result["errors"].append(
                        f"Hook execution failed: {result.stderr}"
                    )
            else:
                test_result["errors"].append("Poetry wrapper not found")

        except subprocess.TimeoutExpired:
            test_result["errors"].append("Hook execution timed out")
        except Exception as e:
            test_result["errors"].append(f"Test execution error: {e}")

        return test_result


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate intelligence hook configuration across repositories",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --scan /Volumes/PRO-G40/Code                    # Scan all repos
  %(prog)s --repo /path/to/repo --validate                 # Validate single repo
  %(prog)s --repo /path/to/repo --fix                      # Fix single repo
  %(prog)s --validate-all --auto-fix                       # Validate all and fix
  %(prog)s --validate-all --report validation_report.md   # Generate report
        """,
    )

    parser.add_argument("--scan", help="Base path to scan for repositories")
    parser.add_argument("--repo", help="Single repository path to validate/fix")
    parser.add_argument("--validate", action="store_true", help="Validate repository")
    parser.add_argument("--fix", action="store_true", help="Fix repository issues")
    parser.add_argument(
        "--validate-all",
        action="store_true",
        help="Validate all discovered repositories",
    )
    parser.add_argument(
        "--auto-fix", action="store_true", help="Automatically fix issues"
    )
    parser.add_argument("--report", help="Output report file path")
    parser.add_argument(
        "--test-execution", action="store_true", help="Test hook execution"
    )
    parser.add_argument("--json-output", help="Output results as JSON to file")

    args = parser.parse_args()

    # Initialize validator
    validator = IntelligenceHookValidator()

    try:
        if args.repo:
            # Single repository operation
            repo_path = Path(args.repo)
            if not repo_path.exists():
                validator.print_status(f"Repository not found: {repo_path}", "error")
                sys.exit(1)

            result = validator.validate_repository(repo_path)

            if args.fix and not result["valid"]:
                validator.fix_repository(repo_path, result)
                # Re-validate after fixes
                result = validator.validate_repository(repo_path)

            if args.test_execution:
                test_result = validator.test_hook_execution(repo_path)
                print(f"\nExecution Test Results for {repo_path.name}:")
                print(f"Executable: {test_result['executable']}")
                if test_result["errors"]:
                    print("Errors:")
                    for error in test_result["errors"]:
                        print(f"  - {error}")

            # Print summary
            status = "VALID" if result["valid"] else "INVALID"
            validator.print_status(f"Repository {repo_path.name}: {status}")

        elif args.validate_all or args.scan:
            # Multiple repository operation
            results = validator.validate_all_repositories(args.scan, args.auto_fix)

            # Generate report
            if args.report:
                validator.generate_report(args.report)
            else:
                print(validator.generate_report())

            # Output JSON if requested
            if args.json_output:
                with open(args.json_output, "w") as f:
                    json.dump(results, f, indent=2)
                validator.print_status(f"JSON results saved to: {args.json_output}")

        else:
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        validator.print_status("Validation interrupted by user", "warning")
        sys.exit(1)
    except Exception as e:
        validator.print_status(f"Validation failed: {e}", "error")
        sys.exit(1)


if __name__ == "__main__":
    main()
