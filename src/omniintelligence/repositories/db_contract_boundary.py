# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""The one place that crosses the two ModelDbRepositoryContract families.

There are two of these models on the fleet and they are not the same model:

* ``omnibase_core.models.contracts.ModelDbRepositoryContract`` -- the rich one.
  Its ``ModelDbParam`` carries ``required``, ``nullable``, ``default`` and a
  typed ``EnumParameterType``. Every ``*.repository.yaml`` in this repo is
  written against it and uses those fields heavily (178 ``required:`` /
  ``default:`` keys across the three contracts), and the arg-binding in each
  adapter reads them to decide what to pass for an omitted parameter.
* ``omnibase_infra.runtime.db.models.ModelDbRepositoryContract`` -- a leaner
  copy, local to omnibase_infra "since 0.3.2" per its own package docstring.
  Its ``ModelDbParam`` has ``name`` and ``param_type`` and nothing else, and it
  is ``extra="forbid"``, so this repo's contracts cannot validate against it.

``PostgresRepositoryRuntime`` annotates its ``contract`` parameter and its
``.contract`` attribute as the LEAN one. It is a plain class with ``__slots__``
that stores the object and reads it structurally, so the rich contract works
there and always has -- but the annotation says otherwise, so as of
omnibase-infra 0.38.22 a type checker disagrees with the code at every adapter.

This module is that disagreement, stated once, instead of a cast scattered
across four call sites with four different comments. It performs NO conversion:
both functions return the object they were given. Converting would be wrong,
because the lean model cannot hold what the rich one carries -- a real
conversion would silently drop every ``required`` and ``default`` in the
contracts and change which arguments get bound.

The durable fix belongs upstream: one of the two families should be the only
one, or ``PostgresRepositoryRuntime`` should accept the rich contract it
already tolerates. Tracked as OMN-18634's follow-up; until then this boundary
keeps the type-level claim honest and confined to one file.
"""

from __future__ import annotations

from typing import cast

from omnibase_core.models.contracts import ModelDbRepositoryContract
from omnibase_infra.runtime.db import PostgresRepositoryRuntime
from omnibase_infra.runtime.db.models import (
    ModelDbRepositoryContract as RuntimeDbRepositoryContract,
)

__all__ = ["as_runtime_contract", "contract_of"]


def as_runtime_contract(
    contract: ModelDbRepositoryContract,
) -> RuntimeDbRepositoryContract:
    """Hand a rich contract to ``PostgresRepositoryRuntime``, unchanged."""
    return cast(RuntimeDbRepositoryContract, contract)


def contract_of(runtime: PostgresRepositoryRuntime) -> ModelDbRepositoryContract:
    """Read back the rich contract a runtime was constructed with, unchanged.

    Only sound for a runtime built through :func:`as_runtime_contract`; every
    construction site in this repo is.
    """
    return cast(ModelDbRepositoryContract, runtime.contract)
