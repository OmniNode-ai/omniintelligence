# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Topic models: reading event-bus topics from node contracts (OMN-21623)."""

from omniintelligence.models.topics.model_contract_topic_reader import (
    ModelContractTopicReader,
)

read_contract_topic = ModelContractTopicReader().read

__all__ = ["ModelContractTopicReader", "read_contract_topic"]
