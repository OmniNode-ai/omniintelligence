"""Pre-commit fast-path runner for the Code Intelligence Review Bot.

Reuses RunnerPrReview core logic but skips slow rules for fast feedback
at commit time. Exits non-zero on BLOCKER findings in BLOCK mode.

OMN-2496: Implement PR Gatekeeper CI integration.
"""

from __future__ import annotations

import subprocess
import sys

from omniintelligence.review_bot.runner.runner_pr_review import (
    PrReviewResult,
    RunnerPrReview,
)


class RunnerPrecommit:
    """Pre-commit hook runner that reuses the core review logic.

    Skips slow rules (``slow: true`` in policy) for fast pre-commit feedback.
    Exits non-zero on BLOCKER findings when in BLOCK enforcement mode.

    Usage (from pre-commit hook)::

        runner = RunnerPrecommit()
        exit_code = runner.run(policy_path="review_policy.yaml")
        sys.exit(exit_code)
    """

    def run(
        self,
        policy_path: str = "review_policy.yaml",
    ) -> int:
        """Run the pre-commit review.

        Captures the staged diff and runs fast rules against it.

        Args:
            policy_path: Path to the policy YAML file.

        Returns:
            Exit code: 0 for pass, 1 for block (BLOCKER findings in BLOCK mode).
        """
        # Load policy
        core_runner = RunnerPrReview()
        policy = core_runner.load_policy(policy_path)

        if policy is None:
            print(
                f"WARNING: No valid policy at {policy_path!r}. Skipping review.",
                file=sys.stderr,
            )
            return 0

        # Get staged diff
        diff_content = self._get_staged_diff()
        if not diff_content.strip():
            print("No staged changes to review.", file=sys.stderr)
            return 0

        # Run fast rules only (slow=False)
        result = core_runner.run(diff_content=diff_content, policy=policy, slow=False)
        return self._handle_result(result)

    def run_with_diff(
        self,
        diff_content: str,
        policy_path: str = "review_policy.yaml",
    ) -> int:
        """Run the pre-commit review against a provided diff.

        Useful for testing and scenarios where the diff is already available.

        Args:
            diff_content: Git unified diff content to review.
            policy_path: Path to the policy YAML file.

        Returns:
            Exit code: 0 for pass, 1 for block.
        """
        core_runner = RunnerPrReview()
        policy = core_runner.load_policy(policy_path)

        if policy is None:
            print(
                f"WARNING: No valid policy at {policy_path!r}. Skipping review.",
                file=sys.stderr,
            )
            return 0

        result = core_runner.run(diff_content=diff_content, policy=policy, slow=False)
        return self._handle_result(result)

    def _get_staged_diff(self) -> str:
        """Get the git staged diff.

        Returns:
            Unified diff string of staged changes, or empty string on error.
        """
        try:
            proc = subprocess.run(
                ["git", "diff", "--cached", "--unified=0"],
                capture_output=True,
                text=True,
                check=False,
            )
            return proc.stdout
        except OSError:
            return ""

    def _handle_result(self, result: PrReviewResult) -> int:
        """Print summary and determine exit code.

        Args:
            result: PrReviewResult from core runner.

        Returns:
            0 for pass, 1 for block.
        """
        print(result.summary, file=sys.stderr)

        if not result.ci_passed:
            print(
                "\nPre-commit check FAILED: BLOCKER findings detected. "
                "Fix the issues above before committing.",
                file=sys.stderr,
            )
            return 1

        return 0


__all__ = ["RunnerPrecommit"]
