# SPDX-FileCopyrightText: 2025 OmniNode.ai Inc.
# SPDX-License-Identifier: MIT

"""Adapter bridging PostgresRepositoryRuntime to ProtocolCodeEntityStore.

Follows the same pattern as AdapterPatternStore: implements the protocol
by delegating to contract-driven PostgresRepositoryRuntime operations.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from omnibase_core.models.contracts import ModelDbRepositoryContract
from omnibase_infra.runtime.db import PostgresRepositoryRuntime

from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_entity import (
    ModelCodeEntity,
)
from omniintelligence.nodes.node_ast_extraction_compute.models.model_code_relationship import (
    ModelCodeRelationship,
)

if TYPE_CHECKING:
    from asyncpg import Pool

CONTRACT_PATH = Path(__file__).parent / "code_entities.repository.yaml"


class AdapterCodeEntityStore:
    """Adapter implementing ProtocolCodeEntityStore via contract runtime.

    Each method call is an independent transaction (same semantics as
    AdapterPatternStore). The conn parameter is not used.
    """

    def __init__(self, runtime: PostgresRepositoryRuntime) -> None:
        self._runtime = runtime

    def _build_positional_args(
        self,
        op_name: str,
        provided: dict[str, Any],
    ) -> tuple[Any, ...]:
        contract = self._runtime.contract
        operation = contract.ops.get(op_name)
        if operation is None:
            msg = f"Unknown operation: {op_name}"
            raise ValueError(msg)

        args = []
        for param_name, param_spec in operation.params.items():
            if param_name in provided:
                args.append(provided[param_name])
            elif param_spec.default is not None:
                args.append(param_spec.default.to_value())
            elif not param_spec.required:
                args.append(None)
            else:
                msg = f"Required param '{param_name}' not provided for operation '{op_name}'"
                raise ValueError(msg)

        return tuple(args)

    async def upsert_entity(self, entity: ModelCodeEntity) -> str:
        """Upsert a code entity via the contract runtime."""
        args = self._build_positional_args(
            "upsert_entity",
            {
                "id": entity.id,
                "entity_type": entity.entity_type,
                "name": entity.entity_name,
                "file_path": entity.source_path,
                "file_hash": entity.file_hash,
                "source_repo": entity.source_repo,
                "line_start": entity.line_number,
                "line_end": entity.line_number,
                "bases": json.dumps(entity.bases),
                "methods": json.dumps(entity.methods),
                "decorators": json.dumps(entity.decorators),
                "docstring": entity.docstring,
                "source_code": entity.signature,
                "confidence": entity.confidence,
            },
        )
        result = await self._runtime.call("upsert_entity", *args)
        if result and isinstance(result, dict) and "id" in result:
            return str(result["id"])
        return entity.id

    async def upsert_relationship(self, relationship: ModelCodeRelationship) -> str:
        """Upsert a code relationship via the contract runtime."""
        args = self._build_positional_args(
            "upsert_relationship",
            {
                "id": relationship.id,
                "source_entity_id": relationship.source_entity,
                "target_entity_id": relationship.target_entity,
                "relationship_type": relationship.relationship_type,
                "confidence": relationship.confidence,
                "trust_tier": relationship.trust_tier,
                "metadata": json.dumps(relationship.evidence),
            },
        )
        result = await self._runtime.call("upsert_relationship", *args)
        if result and isinstance(result, dict) and "id" in result:
            return str(result["id"])
        return relationship.id

    async def delete_entities_by_file(self, source_repo: str, file_path: str) -> int:
        """Delete all entities for a file. Returns count deleted."""
        args = self._build_positional_args(
            "delete_entities_by_file",
            {
                "source_repo": source_repo,
                "file_path": file_path,
            },
        )
        result = await self._runtime.call("delete_entities_by_file", *args)
        if isinstance(result, list):
            return len(result)
        return 0

    async def get_entities_by_repo(
        self, source_repo: str, *, limit: int = 1000
    ) -> list[ModelCodeEntity]:
        """Get entities by repository."""
        args = self._build_positional_args(
            "get_entities_by_repo",
            {
                "source_repo": source_repo,
                "limit": limit,
            },
        )
        result = await self._runtime.call("get_entities_by_repo", *args)
        if isinstance(result, list):
            return result
        return []

    async def get_entities_by_file(
        self, source_repo: str, file_path: str
    ) -> list[ModelCodeEntity]:
        """Get entities by file."""
        args = self._build_positional_args(
            "get_entities_by_file",
            {
                "source_repo": source_repo,
                "file_path": file_path,
            },
        )
        result = await self._runtime.call("get_entities_by_file", *args)
        if isinstance(result, list):
            return result
        return []


def _convert_defaults_to_schema_value(
    contract_dict: dict[str, Any],
) -> dict[str, Any]:
    """Convert plain default values to ModelSchemaValue format."""
    from omnibase_core.models.common.model_schema_value import ModelSchemaValue

    result = copy.deepcopy(contract_dict)
    ops = result.get("ops", {})
    for _op_name, op in ops.items():
        params = op.get("params", {})
        for _param_name, param in params.items():
            if "default" in param:
                schema_value = ModelSchemaValue.from_value(param["default"])
                param["default"] = schema_value.model_dump(mode="json")
    return result


def load_code_entities_contract() -> ModelDbRepositoryContract:
    """Load the code_entities repository contract."""
    if not CONTRACT_PATH.exists():
        msg = f"Contract file not found: {CONTRACT_PATH}"
        raise FileNotFoundError(msg)

    with open(CONTRACT_PATH) as f:
        raw = yaml.safe_load(f)

    contract_dict = raw.get("db_repository")
    if not contract_dict:
        msg = "Contract YAML missing 'db_repository' key"
        raise ValueError(msg)

    contract_dict = _convert_defaults_to_schema_value(contract_dict)
    return ModelDbRepositoryContract.model_validate(contract_dict)


async def create_code_entity_store_adapter(pool: Pool) -> AdapterCodeEntityStore:
    """Factory function to create a code entity store adapter."""
    contract = load_code_entities_contract()
    runtime = PostgresRepositoryRuntime(pool=pool, contract=contract)
    return AdapterCodeEntityStore(runtime)


__all__ = [
    "AdapterCodeEntityStore",
    "create_code_entity_store_adapter",
    "load_code_entities_contract",
]
