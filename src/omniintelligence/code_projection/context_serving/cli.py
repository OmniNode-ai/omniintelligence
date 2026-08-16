# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Explicit operator CLI for tenant-authorized code-context packs."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

from omniintelligence.code_projection._canonical import sha256_hex
from omniintelligence.code_projection.artifacts import CodeProjectionArtifactStore
from omniintelligence.code_projection.context_serving.codec import (
    parse_authorization_profile,
    parse_code_context_request,
)
from omniintelligence.code_projection.context_serving.exceptions import (
    CodeContextAuthorizationError,
    CodeContextError,
    CodeContextSearchError,
)
from omniintelligence.code_projection.context_serving.live import (
    live_code_context_search,
)
from omniintelligence.code_projection.context_serving.resolver import (
    CodeProjectionContextArtifactResolver,
    authorize_code_context_request,
)
from omniintelligence.code_projection.context_serving.service import (
    CodeContextProcessor,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m omniintelligence.code_projection.context_serving",
        description=(
            "Search one explicit tenant/repository and emit a bounded, "
            "authorization-verified code context pack."
        ),
        epilog=(
            "Requires CODE_CONTEXT_AUTHORIZATION_FILE and its independently "
            "trusted CODE_CONTEXT_AUTHORIZATION_SHA256 pin."
        ),
    )
    parser.add_argument("--request-file", required=True)
    parser.add_argument("--artifact-root", required=True)
    return parser


def _trusted_authorization_payload() -> bytes:
    authorization_file = os.environ.get("CODE_CONTEXT_AUTHORIZATION_FILE", "").strip()
    expected_sha256 = os.environ.get(
        "CODE_CONTEXT_AUTHORIZATION_SHA256",
        "",
    ).strip()
    if not authorization_file or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise CodeContextAuthorizationError(
            "trusted code-context authorization path and digest are not bound"
        )
    payload = Path(authorization_file).read_bytes()
    if sha256_hex(payload) != expected_sha256:
        raise CodeContextAuthorizationError(
            "trusted code-context authorization digest does not match"
        )
    return payload


async def _run(args: argparse.Namespace) -> bytes:
    request_payload = Path(str(args.request_file)).read_bytes()
    authorization_payload = _trusted_authorization_payload()
    profile = parse_authorization_profile(authorization_payload)
    request = parse_code_context_request(request_payload)
    authorize_code_context_request(
        authorization_profile=profile,
        request=request,
    )
    artifact_store = CodeProjectionArtifactStore(Path(str(args.artifact_root)))
    resolver = CodeProjectionContextArtifactResolver(
        artifact_store=artifact_store,
        authorization_profile=profile,
    )
    try:
        async with live_code_context_search(artifact_store) as search:
            processor = CodeContextProcessor(
                search=search,
                artifact_resolver=resolver,
            )
            return await processor.process(request_payload)
    except CodeContextError:
        raise
    except Exception as exc:
        raise CodeContextSearchError(
            "live code-context search dependency failed to initialize"
        ) from exc


def main(argv: Sequence[str] | None = None) -> int:
    """Run one exact request without logging query text or resolved content."""

    args = _parser().parse_args(argv)
    try:
        response = asyncio.run(_run(args))
    except CodeContextError as exc:
        error = {
            "error": type(exc).__name__,
            "message": str(exc),
            "status": "failed",
        }
        sys.stderr.write(json.dumps(error, sort_keys=True) + "\n")
        return 1
    except OSError:
        error = {
            "error": "CodeContextInputError",
            "message": "context-serving input could not be read",
            "status": "failed",
        }
        sys.stderr.write(json.dumps(error, sort_keys=True) + "\n")
        return 1
    sys.stdout.buffer.write(response + b"\n")
    return 0


__all__ = ["main"]
