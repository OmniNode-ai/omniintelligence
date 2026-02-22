"""Unit tests for auto-remediation pipeline.

Tests cover OMN-2498 acceptance criteria:
- R1: Only safe refactors are auto-applied
- R2: Bot PR is isolated from source PR
- R3: Remediation outcome is recorded
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from omniintelligence.review_bot.models.model_review_finding import ModelReviewFinding
from omniintelligence.review_bot.models.model_review_severity import ReviewSeverity
from omniintelligence.review_bot.remediation.patch_applicator import (
    SAFE_REFACTOR_ALLOWLIST,
    PatchApplicator,
    PatchResult,
    SafeRefactorType,
)
from omniintelligence.review_bot.remediation.pipeline_remediation import (
    RemediationPipeline,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def make_finding(
    rule_id: str = "formatter",
    patch: str | None = "diff patch",
    confidence: float = 0.8,
) -> ModelReviewFinding:
    return ModelReviewFinding(
        finding_id=uuid.uuid4(),
        rule_id=rule_id,
        severity=ReviewSeverity.WARNING,
        confidence=confidence,
        rationale="Test",
        suggested_fix="Test fix",
        file_path="src/test.py",
        line_number=1,
        patch=patch,
    )


def make_mock_applicator(success: bool = True) -> MagicMock:
    applicator = MagicMock(spec=PatchApplicator)
    applicator.apply_patch.return_value = PatchResult(
        success=success,
        patch_content="diff patch",
        error=None if success else "Patch failed",
    )
    applicator.is_safe_refactor_type.side_effect = lambda t: (
        t in SAFE_REFACTOR_ALLOWLIST
    )
    return applicator


# ---------------------------------------------------------------------------
# R1: Only safe refactors are auto-applied
# ---------------------------------------------------------------------------


class TestSafeRefactorAllowlist:
    def test_all_safe_types_in_allowlist(self) -> None:
        """R1: Allowlist contains all four safe refactor types."""
        expected = {"type_completer", "formatter", "import_sort", "trivial_rename"}
        assert expected == SAFE_REFACTOR_ALLOWLIST

    def test_safe_types_as_enum_values(self) -> None:
        for t in SafeRefactorType:
            assert t.value in SAFE_REFACTOR_ALLOWLIST

    def test_is_safe_type_formatter(self) -> None:
        applicator = PatchApplicator()
        assert applicator.is_safe_refactor_type("formatter") is True

    def test_is_safe_type_type_completer(self) -> None:
        applicator = PatchApplicator()
        assert applicator.is_safe_refactor_type("type_completer") is True

    def test_is_safe_type_import_sort(self) -> None:
        applicator = PatchApplicator()
        assert applicator.is_safe_refactor_type("import_sort") is True

    def test_is_safe_type_trivial_rename(self) -> None:
        applicator = PatchApplicator()
        assert applicator.is_safe_refactor_type("trivial_rename") is True

    def test_unsafe_type_rejected(self) -> None:
        applicator = PatchApplicator()
        assert applicator.is_safe_refactor_type("semantic_change") is False

    def test_none_type_rejected(self) -> None:
        applicator = PatchApplicator()
        assert applicator.is_safe_refactor_type(None) is False

    def test_finding_without_patch_skipped(self) -> None:
        applicator = make_mock_applicator()
        pipeline = RemediationPipeline(patch_applicator=applicator)

        finding = make_finding(patch=None)
        result = pipeline.run(
            findings=[finding],
            source_pr_number=1,
            source_pr_title="Test PR",
            base_branch="main",
        )

        assert finding in result.skipped_findings
        assert finding not in result.eligible_findings

    def test_finding_with_unsafe_type_skipped(self) -> None:
        applicator = make_mock_applicator()
        pipeline = RemediationPipeline(patch_applicator=applicator)

        # Rule ID "semantic_change" is not in safe allowlist
        finding = make_finding(rule_id="semantic_change", patch="some patch")
        result = pipeline.run(
            findings=[finding],
            source_pr_number=1,
            source_pr_title="Test PR",
            base_branch="main",
        )

        assert finding in result.skipped_findings

    def test_safe_findings_go_to_eligible(self) -> None:
        applicator = make_mock_applicator()
        pipeline = RemediationPipeline(patch_applicator=applicator)

        finding = make_finding(
            rule_id="formatter", patch="--- a\n+++ b\n@@ -1 +1 @@\n-x\n+x\n"
        )
        result = pipeline.run(
            findings=[finding],
            source_pr_number=1,
            source_pr_title="Test PR",
            base_branch="main",
        )

        assert finding in result.eligible_findings

    def test_mixed_findings_split_correctly(self) -> None:
        applicator = make_mock_applicator()
        pipeline = RemediationPipeline(patch_applicator=applicator)

        safe = make_finding(rule_id="formatter", patch="patch")
        unsafe_no_patch = make_finding(rule_id="formatter", patch=None)
        unsafe_type = make_finding(rule_id="dangerous_refactor", patch="patch")

        result = pipeline.run(
            findings=[safe, unsafe_no_patch, unsafe_type],
            source_pr_number=1,
            source_pr_title="Test PR",
            base_branch="main",
        )

        assert safe in result.eligible_findings
        assert unsafe_no_patch in result.skipped_findings
        assert unsafe_type in result.skipped_findings


class TestPipelineAppliesPatches:
    def test_successful_patch_applied(self) -> None:
        applicator = make_mock_applicator(success=True)
        pipeline = RemediationPipeline(patch_applicator=applicator)

        finding = make_finding(rule_id="formatter", patch="patch")
        result = pipeline.run(
            findings=[finding],
            source_pr_number=1,
            source_pr_title="Test PR",
            base_branch="main",
        )

        assert finding in result.applied_findings
        applicator.apply_patch.assert_called_once_with("patch")

    def test_failed_patch_not_in_applied(self) -> None:
        applicator = make_mock_applicator(success=False)
        pipeline = RemediationPipeline(patch_applicator=applicator)

        finding = make_finding(rule_id="formatter", patch="bad patch")
        result = pipeline.run(
            findings=[finding],
            source_pr_number=1,
            source_pr_title="Test PR",
            base_branch="main",
        )

        assert finding not in result.applied_findings

    def test_empty_findings_returns_empty_result(self) -> None:
        applicator = make_mock_applicator()
        pipeline = RemediationPipeline(patch_applicator=applicator)

        result = pipeline.run(
            findings=[],
            source_pr_number=1,
            source_pr_title="Test PR",
            base_branch="main",
        )

        assert result.eligible_findings == []
        assert result.applied_findings == []
        assert result.skipped_findings == []
        applicator.apply_patch.assert_not_called()


class TestRefactorTypeOverride:
    def test_explicit_refactor_type_mapping_used(self) -> None:
        """Explicit refactor_types mapping overrides rule_id lookup."""
        applicator = make_mock_applicator()
        pipeline = RemediationPipeline(patch_applicator=applicator)

        finding = make_finding(rule_id="some_rule", patch="patch")
        fid = str(finding.finding_id)

        result = pipeline.run(
            findings=[finding],
            source_pr_number=1,
            source_pr_title="Test PR",
            base_branch="main",
            refactor_types={fid: "formatter"},  # Override: formatter is safe
        )

        assert finding in result.eligible_findings

    def test_explicit_unsafe_mapping_skips(self) -> None:
        applicator = make_mock_applicator()
        pipeline = RemediationPipeline(patch_applicator=applicator)

        finding = make_finding(rule_id="formatter", patch="patch")
        fid = str(finding.finding_id)

        result = pipeline.run(
            findings=[finding],
            source_pr_number=1,
            source_pr_title="Test PR",
            base_branch="main",
            refactor_types={fid: "semantic_change"},  # Override: unsafe type
        )

        assert finding in result.skipped_findings


# ---------------------------------------------------------------------------
# R2: Bot PR is isolated from source PR
# ---------------------------------------------------------------------------


class TestBotPrCreation:
    def test_bot_pr_title_format(self) -> None:
        from omniintelligence.review_bot.remediation.bot_pr_creator import (
            BotPrCreator,
            BotPrSpec,
        )

        client = MagicMock()
        client._repo = "owner/repo"
        client._post.return_value = {
            "html_url": "https://github.com/owner/repo/pull/99"
        }

        creator = BotPrCreator(client=client)
        spec = BotPrSpec(
            source_pr_number=42,
            source_pr_title="Add auth",
            base_branch="main",
            head_branch="bot/fix-42",
            applied_findings=[make_finding()],
        )

        url = creator.create_bot_pr(spec)

        # Verify title format
        call_kwargs = client._post.call_args
        body_sent = call_kwargs.args[1]
        assert "[omni-review-bot]" in body_sent["title"]
        assert "Add auth" in body_sent["title"]

    def test_bot_pr_targets_base_branch_not_source(self) -> None:
        from omniintelligence.review_bot.remediation.bot_pr_creator import (
            BotPrCreator,
            BotPrSpec,
        )

        client = MagicMock()
        client._repo = "owner/repo"
        client._post.return_value = {
            "html_url": "https://github.com/owner/repo/pull/99"
        }

        creator = BotPrCreator(client=client)
        spec = BotPrSpec(
            source_pr_number=42,
            source_pr_title="Add auth",
            base_branch="main",  # Targets base, not feature branch
            head_branch="bot/fix-42",
            applied_findings=[],
        )

        creator.create_bot_pr(spec)

        call_kwargs = client._post.call_args
        body_sent = call_kwargs.args[1]
        assert body_sent["base"] == "main"
        assert body_sent["head"] == "bot/fix-42"

    def test_bot_pr_body_links_source_pr(self) -> None:
        from omniintelligence.review_bot.remediation.bot_pr_creator import (
            BotPrCreator,
            BotPrSpec,
        )

        client = MagicMock()
        client._repo = "owner/repo"
        creator = BotPrCreator(client=client)

        spec = BotPrSpec(
            source_pr_number=42,
            source_pr_title="Add auth",
            base_branch="main",
            head_branch="bot/fix",
            applied_findings=[make_finding()],
        )

        body = creator._build_pr_body(spec)
        assert "#42" in body

    def test_bot_pr_body_lists_applied_findings(self) -> None:
        from omniintelligence.review_bot.remediation.bot_pr_creator import (
            BotPrCreator,
            BotPrSpec,
        )

        client = MagicMock()
        client._repo = "owner/repo"
        creator = BotPrCreator(client=client)

        finding = make_finding(rule_id="formatter")
        spec = BotPrSpec(
            source_pr_number=1,
            source_pr_title="Test",
            base_branch="main",
            head_branch="bot/fix",
            applied_findings=[finding],
        )

        body = creator._build_pr_body(spec)
        assert "formatter" in body

    def test_bot_pr_creation_failure_returns_none(self) -> None:
        from omniintelligence.review_bot.remediation.bot_pr_creator import (
            BotPrCreator,
            BotPrSpec,
        )

        client = MagicMock()
        client._repo = "owner/repo"
        client._post.return_value = None  # API failure

        creator = BotPrCreator(client=client)
        spec = BotPrSpec(
            source_pr_number=1,
            source_pr_title="Test",
            base_branch="main",
            head_branch="bot/fix",
            applied_findings=[],
        )

        result = creator.create_bot_pr(spec)
        assert result is None


# ---------------------------------------------------------------------------
# R3: Remediation outcome signals
# ---------------------------------------------------------------------------


class TestRemediationSignals:
    def test_accepted_signal_type(self) -> None:
        pipeline = RemediationPipeline()
        finding = make_finding(confidence=0.9)

        signal = pipeline.emit_accepted_signal(finding)

        assert signal.signal_type == "remediation_accepted"

    def test_rejected_signal_type(self) -> None:
        pipeline = RemediationPipeline()
        finding = make_finding(confidence=0.7)

        signal = pipeline.emit_rejected_signal(finding)

        assert signal.signal_type == "remediation_rejected"

    def test_signal_includes_finding_id(self) -> None:
        pipeline = RemediationPipeline()
        finding = make_finding()

        signal = pipeline.emit_accepted_signal(finding)

        assert signal.finding_id == str(finding.finding_id)

    def test_signal_includes_rule_id(self) -> None:
        pipeline = RemediationPipeline()
        finding = make_finding(rule_id="formatter")

        signal = pipeline.emit_accepted_signal(finding)

        assert signal.rule_id == "formatter"

    def test_signal_includes_confidence(self) -> None:
        pipeline = RemediationPipeline()
        finding = make_finding(confidence=0.85)

        signal = pipeline.emit_accepted_signal(finding)

        assert signal.confidence == 0.85
