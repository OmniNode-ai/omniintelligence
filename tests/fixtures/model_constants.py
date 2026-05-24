# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Shared model ID constants for omniintelligence tests.

Use these in assertions and model_id field values — not in fixture
wiring dicts (registry constructors, conftest side-table builds).
"""

MODEL_QWEN3_CODER_30B: str = "qwen3-coder-30b"
MODEL_QWEN3_CODER_30B_A3B: str = "qwen3-coder-30b-a3b"
MODEL_QWEN3_14B: str = "qwen3-14b"
MODEL_DEEPSEEK_R1: str = "deepseek-r1"
MODEL_GEMINI_FLASH: str = "gemini-flash"
MODEL_GLM_4: str = "glm-4"
MODEL_CLAUDE_SONNET_4: str = "claude-sonnet-4"
MODEL_CLAUDE_OPUS_4: str = "claude-opus-4"
MODEL_GPT_4_1: str = "gpt-4.1"

__all__ = [
    "MODEL_CLAUDE_OPUS_4",
    "MODEL_CLAUDE_SONNET_4",
    "MODEL_DEEPSEEK_R1",
    "MODEL_GEMINI_FLASH",
    "MODEL_GLM_4",
    "MODEL_GPT_4_1",
    "MODEL_QWEN3_14B",
    "MODEL_QWEN3_CODER_30B",
    "MODEL_QWEN3_CODER_30B_A3B",
]
