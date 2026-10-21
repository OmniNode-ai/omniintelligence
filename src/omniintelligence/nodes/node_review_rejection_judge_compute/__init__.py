# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The review bot's judgement of a rejected Hostile Reviewer finding (OMN-17427).

COMPUTE node: ``handle(ModelRejectionJudgeRequest) -> ModelRejectionJudgePlan``
chooses a judge that is none of the voters (by the quorum's reviewer identity)
and writes its prompt; ``read_judgement(answer)`` reads the judge's answer as
an accept or refuse verdict with one sentence. Pure: the model call, the
overlays and GitHub are the caller's (``cli_review judge-rejections``).
"""
