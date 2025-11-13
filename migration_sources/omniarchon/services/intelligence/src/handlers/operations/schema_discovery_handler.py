"""
Schema Discovery Handler

Handles SCHEMA_DISCOVERY operation requests by querying PostgreSQL information_schema
to provide database schema and table definitions.

Created: 2025-10-26
Purpose: Provide schema discovery information to omniclaude manifest_injector
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

import asyncpg
from src.events.models.intelligence_adapter_events import ModelSchemaDiscoveryPayload

# Centralized configuration
from config import settings

logger = logging.getLogger(__name__)


class SchemaDiscoveryHandler:
    """
    Handle SCHEMA_DISCOVERY operations.

    Query PostgreSQL information_schema for table and column definitions.

    Performance Target: <1500ms query timeout
    """

    TIMEOUT_MS = 1500  # Per spec: 1500ms query timeout

    def __init__(
        self,
        postgres_url: Optional[str] = None,
    ):
        """
        Initialize Schema Discovery handler.

        Args:
            postgres_url: PostgreSQL connection URL
        """
        self.postgres_url = postgres_url or os.getenv(
            "DATABASE_URL",
            settings.get_postgres_dsn(async_driver=True),
        )

    async def execute(
        self,
        source_path: str,
        options: Dict[str, Any],
    ) -> ModelSchemaDiscoveryPayload:
        """
        Execute SCHEMA_DISCOVERY operation.

        Args:
            source_path: Not used (always "database_schemas")
            options: Operation options (include_tables, include_columns, etc.)

        Returns:
            ModelSchemaDiscoveryPayload with schema information

        Raises:
            Exception: If discovery fails or times out
        """
        start_time = time.perf_counter()

        try:
            # Extract options
            include_tables = options.get("include_tables", True)
            include_columns = options.get("include_columns", True)
            include_indexes = options.get("include_indexes", False)
            schema_name = options.get("schema_name", "public")

            logger.info(
                f"Executing SCHEMA_DISCOVERY | schema={schema_name} | options={options}"
            )

            # Query PostgreSQL schema
            conn = await asyncpg.connect(self.postgres_url, timeout=1.5)
            try:
                tables = await self._get_tables(
                    conn, schema_name, include_columns, include_indexes
                )

                query_time_ms = (time.perf_counter() - start_time) * 1000

                logger.info(
                    f"SCHEMA_DISCOVERY completed | tables_found={len(tables)} | "
                    f"query_time_ms={query_time_ms:.2f}"
                )

                return ModelSchemaDiscoveryPayload(
                    tables=tables,
                    total_tables=len(tables),
                    query_time_ms=query_time_ms,
                )
            finally:
                await conn.close()

        except Exception as e:
            query_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"SCHEMA_DISCOVERY failed | error={e} | query_time_ms={query_time_ms:.2f}",
                exc_info=True,
            )
            raise

    async def _get_tables(
        self,
        conn: asyncpg.Connection,
        schema_name: str,
        include_columns: bool,
        include_indexes: bool,
    ) -> List[Dict[str, Any]]:
        """Get tables from information_schema."""
        try:
            # Get table list
            tables_query = f"""
                SELECT
                    table_schema,
                    table_name,
                    pg_total_relation_size(table_schema||'.'||table_name)::bigint / 1024 / 1024 as size_mb
                FROM information_schema.tables
                WHERE table_schema = $1
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """
            tables_raw = await conn.fetch(tables_query, schema_name)

            tables = []
            for row in tables_raw:
                table_name = row["table_name"]
                table_schema = row["table_schema"]
                size_mb = float(row["size_mb"])

                # Get row count
                count_query = f"SELECT COUNT(*) FROM {table_schema}.{table_name}"
                row_count = await conn.fetchval(count_query)

                table_info = {
                    "name": table_name,
                    "schema": table_schema,
                    "row_count": row_count,
                    "size_mb": size_mb,
                }

                # Get columns if requested
                if include_columns:
                    columns = await self._get_columns(conn, table_schema, table_name)
                    table_info["columns"] = columns

                # Get indexes if requested
                if include_indexes:
                    indexes = await self._get_indexes(conn, table_schema, table_name)
                    table_info["indexes"] = indexes

                tables.append(table_info)

            return tables

        except Exception as e:
            logger.error(f"Failed to get tables: {e}")
            raise

    async def _get_columns(
        self,
        conn: asyncpg.Connection,
        schema_name: str,
        table_name: str,
    ) -> List[Dict[str, Any]]:
        """Get columns for a table."""
        try:
            columns_query = """
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    character_maximum_length,
                    numeric_precision,
                    numeric_scale
                FROM information_schema.columns
                WHERE table_schema = $1
                  AND table_name = $2
                ORDER BY ordinal_position
            """
            columns_raw = await conn.fetch(columns_query, schema_name, table_name)

            # Get primary key columns
            pk_query = """
                SELECT a.attname
                FROM pg_index i
                JOIN pg_attribute a ON a.attrelid = i.indrelid
                    AND a.attnum = ANY(i.indkey)
                WHERE i.indrelid = $1::regclass
                  AND i.indisprimary
            """
            pk_columns_raw = await conn.fetch(pk_query, f"{schema_name}.{table_name}")
            pk_columns = {row["attname"] for row in pk_columns_raw}

            columns = []
            for row in columns_raw:
                column_name = row["column_name"]
                data_type = row["data_type"]

                # Add length/precision info to type
                if row["character_maximum_length"]:
                    data_type = f"{data_type}({row['character_maximum_length']})"
                elif row["numeric_precision"]:
                    if row["numeric_scale"]:
                        data_type = f"{data_type}({row['numeric_precision']},{row['numeric_scale']})"
                    else:
                        data_type = f"{data_type}({row['numeric_precision']})"

                columns.append(
                    {
                        "name": column_name,
                        "type": data_type.upper(),
                        "nullable": row["is_nullable"] == "YES",
                        "primary_key": column_name in pk_columns,
                        "default": row["column_default"],
                    }
                )

            return columns

        except Exception as e:
            logger.error(f"Failed to get columns: {e}")
            return []

    async def _get_indexes(
        self,
        conn: asyncpg.Connection,
        schema_name: str,
        table_name: str,
    ) -> List[Dict[str, Any]]:
        """Get indexes for a table."""
        try:
            indexes_query = """
                SELECT
                    i.relname as index_name,
                    a.attname as column_name,
                    ix.indisunique as is_unique,
                    ix.indisprimary as is_primary
                FROM pg_class t
                JOIN pg_index ix ON t.oid = ix.indrelid
                JOIN pg_class i ON i.oid = ix.indexrelid
                JOIN pg_attribute a ON a.attrelid = t.oid
                    AND a.attnum = ANY(ix.indkey)
                WHERE t.relname = $1
                  AND t.relnamespace = $2::regnamespace
                ORDER BY i.relname, a.attnum
            """
            indexes_raw = await conn.fetch(indexes_query, table_name, schema_name)

            # Group by index name
            indexes_dict = {}
            for row in indexes_raw:
                index_name = row["index_name"]
                if index_name not in indexes_dict:
                    indexes_dict[index_name] = {
                        "name": index_name,
                        "columns": [],
                        "is_unique": row["is_unique"],
                        "is_primary": row["is_primary"],
                    }
                indexes_dict[index_name]["columns"].append(row["column_name"])

            return list(indexes_dict.values())

        except Exception as e:
            logger.error(f"Failed to get indexes: {e}")
            return []
