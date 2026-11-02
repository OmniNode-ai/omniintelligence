# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""NodeRetrievalEvalCompute binds the retrieval eval harness (OMN-21945)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from omniintelligence.nodes.node_retrieval_eval_compute import (
    NodeRetrievalEvalCompute,
)
from omniintelligence.nodes.node_retrieval_eval_compute.baselines import (
    BASELINE_SCORECARD_PATH,
)
from omniintelligence.nodes.node_retrieval_eval_compute.handlers.handler_retrieval_eval import (
    handle_retrieval_eval,
)
from omniintelligence.nodes.node_retrieval_eval_compute.models import (
    ModelRetrievalEvalInput,
)


@pytest.mark.unit
async def test_handler_reproduces_committed_baseline() -> None:
    correlation_id = uuid4()

    output = await handle_retrieval_eval(
        ModelRetrievalEvalInput(correlation_id=correlation_id)
    )

    assert output.correlation_id == correlation_id
    assert output.error is None
    assert output.passed is True
    assert output.result is not None
    assert (
        output.result.scorecard.to_canonical_bytes()
        == BASELINE_SCORECARD_PATH.read_bytes()
    )


@pytest.mark.unit
async def test_handler_returns_structured_error_for_missing_fixtures(
    tmp_path: Path,
) -> None:
    output = await handle_retrieval_eval(
        ModelRetrievalEvalInput(fixture_root=tmp_path / "absent")
    )

    assert output.passed is False
    assert output.result is None
    assert output.error is not None


@pytest.mark.unit
def test_contract_binds_the_handler() -> None:
    import yaml

    contract_path = (
        Path(__file__).resolve().parents[4]
        / "src/omniintelligence/nodes/node_retrieval_eval_compute/contract.yaml"
    )
    contract = yaml.safe_load(contract_path.read_text())
    default = contract["handler_routing"]["default_handler"]

    assert default["function"] == handle_retrieval_eval.__name__
    assert default["module"] == handle_retrieval_eval.__module__
    assert NodeRetrievalEvalCompute.__name__ == "NodeRetrievalEvalCompute"
