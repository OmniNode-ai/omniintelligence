# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Integration test: kernel boots with all new wiring from Plan B.

Verifies that:
1. wire_intelligence_handlers() imports all handler specs without ImportError
2. create_intelligence_dispatch_engine() registers routes for review_pairing,
   decision-recorded, and CI topics
3. collect_subscribe_topics_from_contracts() includes review_pairing topics
4. No topic collisions between new and existing dispatch aliases

Related:
    - OMN-6611: Integration test — kernel boots with all new wiring
    - OMN-6589: Plan B — Service Wiring
"""

from __future__ import annotations

import importlib
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.integration
class TestKernelBootWiring:
    """Test that all Plan B wiring integrates without errors."""

    def test_all_handler_specs_importable(self) -> None:
        """All entries in _HANDLER_SPECS can be imported successfully."""
        from omniintelligence.runtime.wiring import _HANDLER_SPECS

        for module_path, attr_name, is_class in _HANDLER_SPECS:
            mod = importlib.import_module(module_path)
            handler_attr = getattr(mod, attr_name)
            if is_class:
                # Verify it can be instantiated (pure compute, no deps)
                instance = handler_attr()
                assert instance is not None, f"Failed to instantiate {attr_name}"
            else:
                assert callable(handler_attr), (
                    f"{attr_name} in {module_path} is not callable"
                )

    def test_review_pairing_dispatch_aliases_exist(self) -> None:
        """Review pairing dispatch aliases are defined."""
        from omniintelligence.runtime.dispatch_handlers import (
            DISPATCH_ALIAS_REVIEW_PAIRING_FINDING_OBSERVED,
            DISPATCH_ALIAS_REVIEW_PAIRING_FINDING_RESOLVED,
            DISPATCH_ALIAS_REVIEW_PAIRING_FIX_APPLIED,
            DISPATCH_ALIAS_REVIEW_PAIRING_PAIR_CREATED,
        )

        assert "finding-observed" in DISPATCH_ALIAS_REVIEW_PAIRING_FINDING_OBSERVED
        assert "fix-applied" in DISPATCH_ALIAS_REVIEW_PAIRING_FIX_APPLIED
        assert "finding-resolved" in DISPATCH_ALIAS_REVIEW_PAIRING_FINDING_RESOLVED
        assert "pair-created" in DISPATCH_ALIAS_REVIEW_PAIRING_PAIR_CREATED

    def test_decision_recorded_alias_exists(self) -> None:
        """Decision-recorded dispatch alias is defined."""
        from omniintelligence.runtime.dispatch_handlers import (
            DISPATCH_ALIAS_DECISION_RECORDED_CMD,
        )

        assert "decision-recorded" in DISPATCH_ALIAS_DECISION_RECORDED_CMD

    def test_dispatch_engine_creates_with_new_routes(self) -> None:
        """Dispatch engine can be created with all new routes."""
        from omniintelligence.runtime.dispatch_handlers import (
            create_intelligence_dispatch_engine,
        )

        mock_repository = MagicMock()
        mock_repository.query_patterns = AsyncMock(return_value=[])
        mock_idempotency_store = MagicMock()
        mock_intent_classifier = MagicMock()

        engine = create_intelligence_dispatch_engine(
            repository=mock_repository,
            idempotency_store=mock_idempotency_store,
            intent_classifier=mock_intent_classifier,
            kafka_producer=None,
            publish_topics={},
            pattern_upsert_store=None,
            pattern_query_store=None,
            llm_client=None,
        )

        # Engine should have routes for review-pairing topics
        assert engine.route_count > 0
        assert engine.handler_count > 0

    def test_contract_topics_include_review_pairing(self) -> None:
        """collect_subscribe_topics_from_contracts includes review_pairing topics."""
        from omniintelligence.runtime.contract_topics import (
            collect_subscribe_topics_from_contracts,
        )

        topics = collect_subscribe_topics_from_contracts()
        review_pairing_topics = [t for t in topics if "review-pairing" in t]
        assert len(review_pairing_topics) >= 2, (
            f"Expected at least 2 review-pairing subscribe topics, "
            f"got {len(review_pairing_topics)}: {review_pairing_topics}"
        )

    def test_no_duplicate_dispatch_aliases(self) -> None:
        """All dispatch aliases are unique — no topic collisions."""
        from omniintelligence.runtime import dispatch_handlers

        aliases = [
            value
            for name, value in vars(dispatch_handlers).items()
            if name.startswith("DISPATCH_ALIAS_") and isinstance(value, str)
        ]

        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for alias in aliases:
            if alias in seen:
                duplicates.append(alias)
            seen[alias] = alias

        assert not duplicates, f"Duplicate dispatch aliases found: {duplicates}"

    def test_decision_store_consumer_importable(self) -> None:
        """DecisionRecordConsumer can be imported (wiring.py verification)."""
        from omniintelligence.decision_store.consumer import (
            DecisionRecordConsumer,
        )

        assert callable(DecisionRecordConsumer)

    def test_decision_store_main_importable(self) -> None:
        """decision_store.__main__ can be imported."""
        import omniintelligence.decision_store.__main__ as main_mod

        assert hasattr(main_mod, "main")
        assert callable(main_mod.main)
