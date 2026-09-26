# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

import pytest

from scripts.validate_ci_precommit_alignment import (
    _check_precommit_full_codebase_mode,
    validate_alignment,
)

pytestmark = pytest.mark.unit


def _config(*hooks: dict[str, object]) -> dict[str, object]:
    return {
        "default_stages": ["pre-commit"],
        "repos": [{"repo": "local", "hooks": list(hooks)}],
    }


def _staged_hook(hook_id: str) -> dict[str, object]:
    return {
        "id": hook_id,
        "entry": f"uv run {hook_id}",
        "language": "system",
        "pass_filenames": True,
        "types": ["python"],
        "files": r"^(src|tests)/",
        "stages": ["pre-commit"],
    }


def test_real_repository_configuration_is_aligned() -> None:
    result = validate_alignment()

    assert result.is_aligned is True
    assert result.errors == []


def test_dev_style_always_run_ruff_hooks_are_full_codebase() -> None:
    config = _config(
        {
            "id": "ruff-format",
            "entry": "uv run ruff format --check src/ tests/",
            "always_run": True,
            "pass_filenames": False,
            "types": ["python"],
        },
        {
            "id": "ruff-check",
            "entry": "uv run ruff check src/ tests/",
            "always_run": True,
            "pass_filenames": False,
            "types": ["python"],
        },
    )

    assert _check_precommit_full_codebase_mode(config) is True


def test_staged_scope_ruff_hooks_are_full_codebase() -> None:
    config = _config(_staged_hook("ruff-format"), _staged_hook("ruff-check"))

    assert _check_precommit_full_codebase_mode(config) is True


@pytest.mark.parametrize(
    "config",
    [
        _config(
            {
                **_staged_hook("ruff-check"),
                "files": r"^src/omniintelligence/(tools|utils)/",
            }
        ),
        _config(
            _staged_hook("ruff-format"),
            {
                **_staged_hook("ruff-check"),
                "files": r"^src/omniintelligence/(tools|utils)/",
            },
        ),
    ],
)
def test_narrowed_ruff_hook_is_not_full_codebase(config: dict[str, object]) -> None:
    assert _check_precommit_full_codebase_mode(config) is False


def test_excluding_tests_is_not_full_codebase() -> None:
    hook = _staged_hook("ruff-check")
    hook["exclude"] = r"^tests/"

    assert _check_precommit_full_codebase_mode(_config(hook)) is False


@pytest.mark.parametrize(
    ("type_field", "values"),
    [("types", ["yaml"]), ("types_or", ["yaml"])],
)
def test_non_python_ruff_hook_is_not_full_codebase(
    type_field: str, values: list[str]
) -> None:
    hook = _staged_hook("ruff-check")
    hook[type_field] = values

    assert _check_precommit_full_codebase_mode(_config(hook)) is False
