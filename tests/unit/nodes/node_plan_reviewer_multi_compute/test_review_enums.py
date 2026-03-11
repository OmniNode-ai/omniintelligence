# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Unit tests for EnumReviewStrategy and EnumReviewModel.

Verifies that enum values are stable — no accidental renames or reorderings.
Any change to these values requires a DB migration update (migration 020).

Ticket: OMN-3284
"""

from __future__ import annotations

import pytest

from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_model import (
    EnumReviewModel,
)
from omniintelligence.nodes.node_plan_reviewer_multi_compute.models.enum_review_strategy import (
    EnumReviewStrategy,
)

# =========================================================================
# Constants: Frozen expected values (must match migration 020)
# =========================================================================

EXPECTED_STRATEGY_VALUES = frozenset(
    {
        "panel_vote",
        "specialist_split",
        "sequential_critique",
        "independent_merge",
    }
)

EXPECTED_MODEL_VALUES = frozenset(
    {
        "qwen3-coder",
        "deepseek-r1",
        "gemini-flash",
        "glm-4",
    }
)

EXPECTED_STRATEGY_COUNT = 4
EXPECTED_MODEL_COUNT = 4


# =========================================================================
# Tests: EnumReviewStrategy
# =========================================================================


@pytest.mark.unit
class TestEnumReviewStrategyStability:
    """Verify EnumReviewStrategy values are stable and match migration 020."""

    def test_strategy_count(self) -> None:
        """Enum has exactly 4 strategies (S1-S4)."""
        assert len(EnumReviewStrategy) == EXPECTED_STRATEGY_COUNT, (
            f"EnumReviewStrategy has {len(EnumReviewStrategy)} values; "
            f"expected {EXPECTED_STRATEGY_COUNT}. "
            "Changing this requires a DB migration update."
        )

    def test_all_strategy_values_are_expected(self) -> None:
        """Every enum value exists in the frozen expected set."""
        for strategy in EnumReviewStrategy:
            assert strategy.value in EXPECTED_STRATEGY_VALUES, (
                f"Unexpected strategy value '{strategy.value}'. "
                f"Valid values: {sorted(EXPECTED_STRATEGY_VALUES)}"
            )

    def test_all_expected_values_in_enum(self) -> None:
        """Every expected value has a corresponding enum member."""
        enum_values = {s.value for s in EnumReviewStrategy}
        for expected in EXPECTED_STRATEGY_VALUES:
            assert expected in enum_values, (
                f"Expected strategy '{expected}' not in EnumReviewStrategy. "
                "Add the missing member."
            )

    def test_exact_bidirectional_match(self) -> None:
        """Exact bidirectional match between enum and expected set."""
        enum_values = {s.value for s in EnumReviewStrategy}
        assert enum_values == EXPECTED_STRATEGY_VALUES, (
            f"Enum values {sorted(enum_values)} != "
            f"expected {sorted(EXPECTED_STRATEGY_VALUES)}"
        )

    @pytest.mark.parametrize("value", sorted(EXPECTED_STRATEGY_VALUES))
    def test_individual_strategy_constructible(self, value: str) -> None:
        """Each strategy value can be used to construct the enum."""
        strategy = EnumReviewStrategy(value)
        assert strategy.value == value

    def test_s1_panel_vote(self) -> None:
        """S1_PANEL_VOTE has value 'panel_vote'."""
        assert EnumReviewStrategy.S1_PANEL_VOTE.value == "panel_vote"

    def test_s2_specialist_split(self) -> None:
        """S2_SPECIALIST_SPLIT has value 'specialist_split'."""
        assert EnumReviewStrategy.S2_SPECIALIST_SPLIT.value == "specialist_split"

    def test_s3_sequential_critique(self) -> None:
        """S3_SEQUENTIAL_CRITIQUE has value 'sequential_critique'."""
        assert EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE.value == "sequential_critique"

    def test_s4_independent_merge(self) -> None:
        """S4_INDEPENDENT_MERGE has value 'independent_merge'."""
        assert EnumReviewStrategy.S4_INDEPENDENT_MERGE.value == "independent_merge"


@pytest.mark.unit
class TestEnumReviewStrategyProperties:
    """Test EnumReviewStrategy type and string behavior."""

    def test_is_str_subclass(self) -> None:
        """EnumReviewStrategy inherits from str."""
        assert issubclass(EnumReviewStrategy, str)

    def test_values_are_strings(self) -> None:
        """All enum values are strings."""
        for strategy in EnumReviewStrategy:
            assert isinstance(strategy.value, str)

    def test_names_are_uppercase(self) -> None:
        """All enum names are SCREAMING_SNAKE_CASE."""
        for strategy in EnumReviewStrategy:
            assert strategy.name == strategy.name.upper(), (
                f"Enum name '{strategy.name}' should be SCREAMING_SNAKE_CASE"
            )

    def test_comparison_with_string(self) -> None:
        """Enum members compare equal to their string values."""
        assert EnumReviewStrategy.S1_PANEL_VOTE == "panel_vote"
        assert EnumReviewStrategy.S2_SPECIALIST_SPLIT == "specialist_split"
        assert EnumReviewStrategy.S3_SEQUENTIAL_CRITIQUE == "sequential_critique"
        assert EnumReviewStrategy.S4_INDEPENDENT_MERGE == "independent_merge"

    def test_importable_from_models_package(self) -> None:
        """EnumReviewStrategy is exported from the models package."""
        from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
            EnumReviewStrategy as Exported,
        )

        assert Exported is EnumReviewStrategy


# =========================================================================
# Tests: EnumReviewModel
# =========================================================================


@pytest.mark.unit
class TestEnumReviewModelStability:
    """Verify EnumReviewModel values are stable and match migration 020 seed data."""

    def test_model_count(self) -> None:
        """Enum has exactly 4 model IDs."""
        assert len(EnumReviewModel) == EXPECTED_MODEL_COUNT, (
            f"EnumReviewModel has {len(EnumReviewModel)} values; "
            f"expected {EXPECTED_MODEL_COUNT}. "
            "Adding a model requires a DB migration INSERT."
        )

    def test_all_model_values_are_expected(self) -> None:
        """Every enum value exists in the frozen expected set."""
        for model in EnumReviewModel:
            assert model.value in EXPECTED_MODEL_VALUES, (
                f"Unexpected model value '{model.value}'. "
                f"Valid values: {sorted(EXPECTED_MODEL_VALUES)}"
            )

    def test_all_expected_values_in_enum(self) -> None:
        """Every expected value has a corresponding enum member."""
        enum_values = {m.value for m in EnumReviewModel}
        for expected in EXPECTED_MODEL_VALUES:
            assert expected in enum_values, (
                f"Expected model '{expected}' not in EnumReviewModel. "
                "Add the missing member."
            )

    def test_exact_bidirectional_match(self) -> None:
        """Exact bidirectional match between enum and expected set."""
        enum_values = {m.value for m in EnumReviewModel}
        assert enum_values == EXPECTED_MODEL_VALUES, (
            f"Enum values {sorted(enum_values)} != "
            f"expected {sorted(EXPECTED_MODEL_VALUES)}"
        )

    @pytest.mark.parametrize("value", sorted(EXPECTED_MODEL_VALUES))
    def test_individual_model_constructible(self, value: str) -> None:
        """Each model value can be used to construct the enum."""
        model = EnumReviewModel(value)
        assert model.value == value

    def test_qwen3_coder(self) -> None:
        """QWEN3_CODER has value 'qwen3-coder'."""
        assert EnumReviewModel.QWEN3_CODER.value == "qwen3-coder"

    def test_deepseek_r1(self) -> None:
        """DEEPSEEK_R1 has value 'deepseek-r1'."""
        assert EnumReviewModel.DEEPSEEK_R1.value == "deepseek-r1"

    def test_gemini_flash(self) -> None:
        """GEMINI_FLASH has value 'gemini-flash'."""
        assert EnumReviewModel.GEMINI_FLASH.value == "gemini-flash"

    def test_glm_4(self) -> None:
        """GLM_4 has value 'glm-4'."""
        assert EnumReviewModel.GLM_4.value == "glm-4"


@pytest.mark.unit
class TestEnumReviewModelProperties:
    """Test EnumReviewModel type and string behavior."""

    def test_is_str_subclass(self) -> None:
        """EnumReviewModel inherits from str."""
        assert issubclass(EnumReviewModel, str)

    def test_values_are_strings(self) -> None:
        """All enum values are strings."""
        for model in EnumReviewModel:
            assert isinstance(model.value, str)

    def test_names_are_uppercase(self) -> None:
        """All enum names are SCREAMING_SNAKE_CASE."""
        for model in EnumReviewModel:
            assert model.name == model.name.upper(), (
                f"Enum name '{model.name}' should be SCREAMING_SNAKE_CASE"
            )

    def test_comparison_with_string(self) -> None:
        """Enum members compare equal to their string values."""
        assert EnumReviewModel.QWEN3_CODER == "qwen3-coder"
        assert EnumReviewModel.DEEPSEEK_R1 == "deepseek-r1"
        assert EnumReviewModel.GEMINI_FLASH == "gemini-flash"
        assert EnumReviewModel.GLM_4 == "glm-4"

    def test_importable_from_models_package(self) -> None:
        """EnumReviewModel is exported from the models package."""
        from omniintelligence.nodes.node_plan_reviewer_multi_compute.models import (
            EnumReviewModel as Exported,
        )

        assert Exported is EnumReviewModel
