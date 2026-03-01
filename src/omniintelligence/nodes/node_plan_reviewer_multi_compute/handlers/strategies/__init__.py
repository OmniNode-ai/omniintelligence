# SPDX-FileCopyrightText: 2026 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Strategy handlers for node_plan_reviewer_multi_compute.

Four independently-invocable review strategy handlers:
- S1: panel_vote      — majority vote across all 4 models (handler_panel_vote)
- S2: specialist_split — domain-assigned models, no vote (handler_specialist_split)
- S3: sequential_critique — drafter + critic pipeline (handler_sequential_critique)
- S4: independent_merge — union merge with deduplication (handler_independent_merge)

Ticket: OMN-3288
"""
