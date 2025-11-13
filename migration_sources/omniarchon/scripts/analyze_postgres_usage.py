#!/usr/bin/env python3
"""
PostgreSQL Database Usage Analysis Script

Analyzes table usage, row counts, sizes, and relationships in Archon PostgreSQL database.
Generates comprehensive reports for database health monitoring.

Usage:
    python analyze_postgres_usage.py [options]

Options:
    --format {json,markdown,console}  Output format (default: console)
    --output-file PATH                Save report to file
    --schema SCHEMA                   Analyze specific schema only
    --include-indexes                 Include index analysis
    --compare-file PATH               Compare with previous report
    --verbose                         Enable verbose logging

Examples:
    # Quick console report
    python analyze_postgres_usage.py

    # Generate markdown report
    python analyze_postgres_usage.py --format markdown --output-file report.md

    # Analyze specific schema with indexes
    python analyze_postgres_usage.py --schema pattern_traceability --include-indexes

    # Generate JSON for programmatic access
    python analyze_postgres_usage.py --format json --output-file stats.json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

# ============================================================================
# CONFIGURATION
# ============================================================================

# Environment variable priority for database connection
DB_ENV_VARS = [
    "DATABASE_URL",
    "POSTGRES_URL",
    "ARCHON_DATABASE_URL",
]

# Default connection parameters (fallback)
DEFAULT_DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "archon_db",
    "user": "postgres",
    "password": "postgres",
}

# Schemas to exclude from analysis
EXCLUDED_SCHEMAS = ["pg_catalog", "information_schema", "pg_toast"]

# Known critical tables that should have data
CRITICAL_TABLES = {
    "public": ["users", "projects", "tasks"],
    "pattern_traceability": ["pattern_lineage", "pattern_events"],
}

# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class TableStats:
    """Statistics for a single table"""

    schema_name: str
    table_name: str
    row_count: int
    total_size_bytes: int
    table_size_bytes: int
    indexes_size_bytes: int
    has_data: bool
    primary_key: Optional[str] = None
    foreign_keys: List[Dict[str, str]] = None
    indexes: List[Dict[str, Any]] = None
    last_modified: Optional[str] = None

    def __post_init__(self):
        if self.foreign_keys is None:
            self.foreign_keys = []
        if self.indexes is None:
            self.indexes = []

    @property
    def size_pretty(self) -> str:
        """Human-readable total size"""
        return _format_bytes(self.total_size_bytes)

    @property
    def table_size_pretty(self) -> str:
        """Human-readable table size"""
        return _format_bytes(self.table_size_bytes)

    @property
    def indexes_size_pretty(self) -> str:
        """Human-readable indexes size"""
        return _format_bytes(self.indexes_size_bytes)


@dataclass
class SchemaStats:
    """Statistics for a database schema"""

    schema_name: str
    total_tables: int
    tables_with_data: int
    empty_tables: int
    total_rows: int
    total_size_bytes: int
    tables: List[TableStats]

    @property
    def size_pretty(self) -> str:
        """Human-readable total size"""
        return _format_bytes(self.total_size_bytes)

    @property
    def data_percentage(self) -> float:
        """Percentage of tables with data"""
        return (
            (self.tables_with_data / self.total_tables * 100)
            if self.total_tables > 0
            else 0.0
        )


@dataclass
class DatabaseReport:
    """Complete database analysis report"""

    timestamp: str
    database_name: str
    host: str
    port: int
    total_schemas: int
    total_tables: int
    tables_with_data: int
    empty_tables: int
    total_rows: int
    total_size_bytes: int
    schemas: List[SchemaStats]
    recommendations: List[str]

    @property
    def size_pretty(self) -> str:
        """Human-readable total size"""
        return _format_bytes(self.total_size_bytes)

    @property
    def data_percentage(self) -> float:
        """Percentage of tables with data"""
        return (
            (self.tables_with_data / self.total_tables * 100)
            if self.total_tables > 0
            else 0.0
        )


# ============================================================================
# DATABASE CONNECTION
# ============================================================================


def _parse_database_url(url: str) -> Dict[str, Any]:
    """Parse PostgreSQL connection URL"""
    # Format: postgresql://user:password@host:port/database
    try:
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            url = url.replace("postgresql://", "").replace("postgres://", "")

            # Extract user:password
            if "@" in url:
                auth, rest = url.split("@", 1)
                if ":" in auth:
                    user, password = auth.split(":", 1)
                else:
                    user = auth
                    password = None
            else:
                user = "postgres"
                password = None
                rest = url

            # Extract host:port/database
            if "/" in rest:
                host_port, database = rest.split("/", 1)
            else:
                host_port = rest
                database = "postgres"

            if ":" in host_port:
                host, port = host_port.split(":", 1)
                port = int(port)
            else:
                host = host_port
                port = 5432

            return {
                "host": host,
                "port": port,
                "database": database,
                "user": user,
                "password": password,
            }
    except Exception as e:
        logging.warning(f"Failed to parse DATABASE_URL: {e}")

    return DEFAULT_DB_CONFIG


async def _get_database_connection() -> asyncpg.Connection:
    """Establish PostgreSQL database connection"""
    # Try environment variables first
    for env_var in DB_ENV_VARS:
        url = os.getenv(env_var)
        if url:
            logging.info(f"Using database connection from {env_var}")
            config = _parse_database_url(url)
            try:
                conn = await asyncpg.connect(
                    **{k: v for k, v in config.items() if v is not None}
                )
                logging.info(
                    f"Connected to {config['host']}:{config['port']}/{config['database']}"
                )
                return conn
            except Exception as e:
                logging.warning(f"Failed to connect using {env_var}: {e}")

    # Fallback to default config
    logging.info("Using default database configuration")
    try:
        conn = await asyncpg.connect(**DEFAULT_DB_CONFIG)
        logging.info(
            f"Connected to {DEFAULT_DB_CONFIG['host']}:{DEFAULT_DB_CONFIG['port']}/{DEFAULT_DB_CONFIG['database']}"
        )
        return conn
    except Exception as e:
        logging.error(f"Failed to connect to database: {e}")
        raise


# ============================================================================
# DATABASE ANALYSIS
# ============================================================================


async def _get_schemas(
    conn: asyncpg.Connection, target_schema: Optional[str] = None
) -> List[str]:
    """Get list of schemas to analyze"""
    if target_schema:
        # Verify schema exists
        result = await conn.fetchval(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = $1",
            target_schema,
        )
        if not result:
            raise ValueError(f"Schema '{target_schema}' not found")
        return [target_schema]

    # Get all schemas except excluded ones
    query = """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ({})
        ORDER BY schema_name
    """.format(
        ",".join(f"'{s}'" for s in EXCLUDED_SCHEMAS)
    )

    rows = await conn.fetch(query)
    return [row["schema_name"] for row in rows]


async def _get_table_row_count(
    conn: asyncpg.Connection, schema: str, table: str
) -> int:
    """Get row count for a specific table"""
    try:
        # Use COUNT(*) for accurate count
        query = f'SELECT COUNT(*) FROM "{schema}"."{table}"'
        count = await conn.fetchval(query)
        return count
    except Exception as e:
        logging.warning(f"Failed to get row count for {schema}.{table}: {e}")
        return 0


async def _get_table_size(
    conn: asyncpg.Connection, schema: str, table: str
) -> Tuple[int, int, int]:
    """Get table size information (total, table, indexes)"""
    try:
        query = """
            SELECT
                pg_total_relation_size($1) as total_size,
                pg_relation_size($1) as table_size,
                pg_indexes_size($1) as indexes_size
        """
        full_name = f'"{schema}"."{table}"'
        row = await conn.fetchrow(query, full_name)
        return (
            row["total_size"] or 0,
            row["table_size"] or 0,
            row["indexes_size"] or 0,
        )
    except Exception as e:
        logging.warning(f"Failed to get size for {schema}.{table}: {e}")
        return (0, 0, 0)


async def _get_table_foreign_keys(
    conn: asyncpg.Connection, schema: str, table: str
) -> List[Dict[str, str]]:
    """Get foreign key relationships for a table"""
    try:
        query = """
            SELECT
                kcu.column_name,
                ccu.table_schema AS foreign_schema,
                ccu.table_name AS foreign_table,
                ccu.column_name AS foreign_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_schema = $1
                AND tc.table_name = $2
        """
        rows = await conn.fetch(query, schema, table)
        return [
            {
                "column": row["column_name"],
                "foreign_table": f"{row['foreign_schema']}.{row['foreign_table']}",
                "foreign_column": row["foreign_column"],
            }
            for row in rows
        ]
    except Exception as e:
        logging.warning(f"Failed to get foreign keys for {schema}.{table}: {e}")
        return []


async def _get_table_indexes(
    conn: asyncpg.Connection, schema: str, table: str
) -> List[Dict[str, Any]]:
    """Get index information for a table"""
    try:
        query = """
            SELECT
                indexname,
                indexdef,
                pg_size_pretty(pg_relation_size(schemaname||'.'||indexname)) as size
            FROM pg_indexes
            WHERE schemaname = $1 AND tablename = $2
        """
        rows = await conn.fetch(query, schema, table)
        return [
            {
                "name": row["indexname"],
                "definition": row["indexdef"],
                "size": row["size"],
            }
            for row in rows
        ]
    except Exception as e:
        logging.warning(f"Failed to get indexes for {schema}.{table}: {e}")
        return []


async def _get_table_primary_key(
    conn: asyncpg.Connection, schema: str, table: str
) -> Optional[str]:
    """Get primary key column(s) for a table"""
    try:
        query = """
            SELECT string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) as pk_columns
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
                AND tc.table_schema = $1
                AND tc.table_name = $2
            GROUP BY tc.constraint_name
        """
        result = await conn.fetchval(query, schema, table)
        return result
    except Exception as e:
        logging.warning(f"Failed to get primary key for {schema}.{table}: {e}")
        return None


async def _analyze_table(
    conn: asyncpg.Connection, schema: str, table: str, include_indexes: bool = False
) -> TableStats:
    """Analyze a single table"""
    logging.debug(f"Analyzing table {schema}.{table}")

    # Get basic stats in parallel
    row_count, (total_size, table_size, indexes_size), foreign_keys, primary_key = (
        await asyncio.gather(
            _get_table_row_count(conn, schema, table),
            _get_table_size(conn, schema, table),
            _get_table_foreign_keys(conn, schema, table),
            _get_table_primary_key(conn, schema, table),
        )
    )

    # Get indexes if requested
    indexes = []
    if include_indexes:
        indexes = await _get_table_indexes(conn, schema, table)

    return TableStats(
        schema_name=schema,
        table_name=table,
        row_count=row_count,
        total_size_bytes=total_size,
        table_size_bytes=table_size,
        indexes_size_bytes=indexes_size,
        has_data=row_count > 0,
        primary_key=primary_key,
        foreign_keys=foreign_keys,
        indexes=indexes,
    )


async def _analyze_schema(
    conn: asyncpg.Connection, schema: str, include_indexes: bool = False
) -> SchemaStats:
    """Analyze all tables in a schema"""
    logging.info(f"Analyzing schema: {schema}")

    # Get all tables in schema
    query = """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = $1
        ORDER BY tablename
    """
    rows = await conn.fetch(query, schema)
    table_names = [row["tablename"] for row in rows]

    if not table_names:
        logging.warning(f"No tables found in schema {schema}")
        return SchemaStats(
            schema_name=schema,
            total_tables=0,
            tables_with_data=0,
            empty_tables=0,
            total_rows=0,
            total_size_bytes=0,
            tables=[],
        )

    # Analyze all tables
    tables = await asyncio.gather(
        *[_analyze_table(conn, schema, table, include_indexes) for table in table_names]
    )

    # Calculate schema statistics
    tables_with_data = sum(1 for t in tables if t.has_data)
    total_rows = sum(t.row_count for t in tables)
    total_size = sum(t.total_size_bytes for t in tables)

    return SchemaStats(
        schema_name=schema,
        total_tables=len(tables),
        tables_with_data=tables_with_data,
        empty_tables=len(tables) - tables_with_data,
        total_rows=total_rows,
        total_size_bytes=total_size,
        tables=tables,
    )


async def _generate_recommendations(schemas: List[SchemaStats]) -> List[str]:
    """Generate actionable recommendations based on analysis"""
    recommendations = []

    # Check for empty critical tables
    for schema_stats in schemas:
        if schema_stats.schema_name in CRITICAL_TABLES:
            critical_tables = CRITICAL_TABLES[schema_stats.schema_name]
            for table_stats in schema_stats.tables:
                if (
                    table_stats.table_name in critical_tables
                    and not table_stats.has_data
                ):
                    recommendations.append(
                        f"⚠️  Critical table '{schema_stats.schema_name}.{table_stats.table_name}' is empty. "
                        f"This may block key functionality."
                    )

    # Check for schemas with high empty table ratio
    for schema_stats in schemas:
        if schema_stats.total_tables > 0:
            empty_ratio = schema_stats.empty_tables / schema_stats.total_tables
            if empty_ratio > 0.75:
                recommendations.append(
                    f"📊 Schema '{schema_stats.schema_name}' has {schema_stats.empty_tables}/{schema_stats.total_tables} "
                    f"({empty_ratio*100:.1f}%) empty tables. Consider reviewing schema design or initialization."
                )

    # Check for tables with foreign keys but no data
    for schema_stats in schemas:
        for table_stats in schema_stats.tables:
            if not table_stats.has_data and table_stats.foreign_keys:
                recommendations.append(
                    f"🔗 Table '{schema_stats.schema_name}.{table_stats.table_name}' has foreign keys but no data. "
                    f"May need seed data or initialization."
                )

    # Check for large empty tables (indexes without data)
    for schema_stats in schemas:
        for table_stats in schema_stats.tables:
            if (
                not table_stats.has_data
                and table_stats.indexes_size_bytes > 1024 * 1024
            ):  # > 1MB
                recommendations.append(
                    f"💾 Table '{schema_stats.schema_name}.{table_stats.table_name}' is empty but has "
                    f"{table_stats.indexes_size_pretty} of indexes. Consider dropping unused indexes."
                )

    if not recommendations:
        recommendations.append(
            "✅ Database appears healthy. All critical tables have data."
        )

    return recommendations


async def analyze_database(
    target_schema: Optional[str] = None, include_indexes: bool = False
) -> DatabaseReport:
    """Perform complete database analysis"""
    logging.info("Starting database analysis")

    conn = await _get_database_connection()
    try:
        # Get database info
        db_name = await conn.fetchval("SELECT current_database()")
        conn.get_server_pid()  # Just to verify connection

        # Get schemas to analyze
        schemas_to_analyze = await _get_schemas(conn, target_schema)
        logging.info(
            f"Found {len(schemas_to_analyze)} schemas to analyze: {', '.join(schemas_to_analyze)}"
        )

        # Analyze all schemas
        schema_stats = await asyncio.gather(
            *[
                _analyze_schema(conn, schema, include_indexes)
                for schema in schemas_to_analyze
            ]
        )

        # Calculate totals
        total_tables = sum(s.total_tables for s in schema_stats)
        tables_with_data = sum(s.tables_with_data for s in schema_stats)
        empty_tables = sum(s.empty_tables for s in schema_stats)
        total_rows = sum(s.total_rows for s in schema_stats)
        total_size = sum(s.total_size_bytes for s in schema_stats)

        # Generate recommendations
        recommendations = await _generate_recommendations(schema_stats)

        # Build report
        report = DatabaseReport(
            timestamp=datetime.utcnow().isoformat() + "Z",
            database_name=db_name,
            host=DEFAULT_DB_CONFIG[
                "host"
            ],  # Using config since we can't easily get from connection
            port=DEFAULT_DB_CONFIG["port"],
            total_schemas=len(schema_stats),
            total_tables=total_tables,
            tables_with_data=tables_with_data,
            empty_tables=empty_tables,
            total_rows=total_rows,
            total_size_bytes=total_size,
            schemas=schema_stats,
            recommendations=recommendations,
        )

        logging.info("Database analysis complete")
        return report

    finally:
        await conn.close()


# ============================================================================
# REPORT GENERATION
# ============================================================================


def _format_bytes(bytes_value: int) -> str:
    """Format bytes to human-readable string"""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f} PB"


def _generate_console_report(
    report: DatabaseReport, include_indexes: bool = False
) -> str:
    """Generate console-formatted report"""
    lines = []

    # Header
    lines.append("=" * 80)
    lines.append("PostgreSQL Database Usage Report")
    lines.append("=" * 80)
    lines.append(f"Generated: {report.timestamp}")
    lines.append(f"Database:  {report.database_name} ({report.host}:{report.port})")
    lines.append("")

    # Executive Summary
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 80)
    lines.append(f"Total Schemas:      {report.total_schemas}")
    lines.append(f"Total Tables:       {report.total_tables}")
    lines.append(
        f"Tables with Data:   {report.tables_with_data} ({report.data_percentage:.1f}%)"
    )
    lines.append(
        f"Empty Tables:       {report.empty_tables} ({100-report.data_percentage:.1f}%)"
    )
    lines.append(f"Total Rows:         {report.total_rows:,}")
    lines.append(f"Total Data Size:    {report.size_pretty}")
    lines.append("")

    # Schema Details
    for schema in report.schemas:
        lines.append("=" * 80)
        lines.append(f"SCHEMA: {schema.schema_name}")
        lines.append("=" * 80)
        lines.append(
            f"Tables: {schema.total_tables} | "
            f"With Data: {schema.tables_with_data} ({schema.data_percentage:.1f}%) | "
            f"Empty: {schema.empty_tables} | "
            f"Size: {schema.size_pretty}"
        )
        lines.append("")

        # Tables with data
        if schema.tables_with_data > 0:
            lines.append("Tables with Data:")
            lines.append("-" * 80)
            lines.append(f"{'Table':<30} {'Rows':>12} {'Size':>12} {'PK':<20}")
            lines.append("-" * 80)

            for table in sorted(schema.tables, key=lambda t: t.row_count, reverse=True):
                if table.has_data:
                    pk = (
                        table.primary_key[:18] + ".."
                        if table.primary_key and len(table.primary_key) > 20
                        else (table.primary_key or "-")
                    )
                    lines.append(
                        f"{table.table_name:<30} {table.row_count:>12,} {table.size_pretty:>12} {pk:<20}"
                    )
            lines.append("")

        # Empty tables
        if schema.empty_tables > 0:
            lines.append("Empty Tables:")
            lines.append("-" * 80)
            lines.append(f"{'Table':<30} {'Foreign Keys':<20} {'Indexes Size':<15}")
            lines.append("-" * 80)

            for table in sorted(schema.tables, key=lambda t: t.table_name):
                if not table.has_data:
                    fk_count = len(table.foreign_keys)
                    fk_str = f"{fk_count} FK(s)" if fk_count > 0 else "-"
                    idx_size = (
                        table.indexes_size_pretty
                        if table.indexes_size_bytes > 0
                        else "-"
                    )
                    lines.append(f"{table.table_name:<30} {fk_str:<20} {idx_size:<15}")
            lines.append("")

        # Index details if requested
        if include_indexes:
            tables_with_indexes = [t for t in schema.tables if t.indexes]
            if tables_with_indexes:
                lines.append("Index Summary:")
                lines.append("-" * 80)
                for table in tables_with_indexes:
                    if table.indexes:
                        lines.append(
                            f"\n{table.table_name} ({len(table.indexes)} indexes):"
                        )
                        for idx in table.indexes:
                            lines.append(f"  - {idx['name']}: {idx['size']}")
                lines.append("")

    # Recommendations
    lines.append("=" * 80)
    lines.append("RECOMMENDATIONS")
    lines.append("=" * 80)
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"{i}. {rec}")
    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


def _generate_markdown_report(
    report: DatabaseReport, include_indexes: bool = False
) -> str:
    """Generate Markdown-formatted report"""
    lines = []

    # Header
    lines.append("# PostgreSQL Database Usage Report")
    lines.append("")
    lines.append(f"**Generated:** {report.timestamp}  ")
    lines.append(
        f"**Database:** {report.database_name} (`{report.host}:{report.port}`)"
    )
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"- **Total Schemas:** {report.total_schemas}")
    lines.append(f"- **Total Tables:** {report.total_tables}")
    lines.append(
        f"- **Tables with Data:** {report.tables_with_data} ({report.data_percentage:.1f}%)"
    )
    lines.append(
        f"- **Empty Tables:** {report.empty_tables} ({100-report.data_percentage:.1f}%)"
    )
    lines.append(f"- **Total Rows:** {report.total_rows:,}")
    lines.append(f"- **Total Data Size:** {report.size_pretty}")
    lines.append("")

    # Schema Details
    for schema in report.schemas:
        lines.append(f"## Schema: `{schema.schema_name}`")
        lines.append("")
        lines.append(
            f"**Statistics:** {schema.total_tables} tables | "
            f"{schema.tables_with_data} with data ({schema.data_percentage:.1f}%) | "
            f"{schema.empty_tables} empty | "
            f"Size: {schema.size_pretty}"
        )
        lines.append("")

        # Tables with data
        if schema.tables_with_data > 0:
            lines.append("### Tables with Data")
            lines.append("")
            lines.append("| Table | Rows | Size | Primary Key | Foreign Keys |")
            lines.append("|-------|------|------|-------------|--------------|")

            for table in sorted(schema.tables, key=lambda t: t.row_count, reverse=True):
                if table.has_data:
                    fk_count = len(table.foreign_keys)
                    fk_str = f"{fk_count}" if fk_count > 0 else "-"
                    pk = table.primary_key or "-"
                    lines.append(
                        f"| `{table.table_name}` | {table.row_count:,} | {table.size_pretty} | `{pk}` | {fk_str} |"
                    )
            lines.append("")

        # Empty tables
        if schema.empty_tables > 0:
            lines.append("### Empty Tables")
            lines.append("")
            lines.append("| Table | Foreign Keys | Indexes Size | Primary Key |")
            lines.append("|-------|--------------|--------------|-------------|")

            for table in sorted(schema.tables, key=lambda t: t.table_name):
                if not table.has_data:
                    fk_count = len(table.foreign_keys)
                    fk_str = f"{fk_count} FK(s)" if fk_count > 0 else "-"
                    idx_size = (
                        table.indexes_size_pretty
                        if table.indexes_size_bytes > 0
                        else "-"
                    )
                    pk = table.primary_key or "-"
                    lines.append(
                        f"| `{table.table_name}` | {fk_str} | {idx_size} | `{pk}` |"
                    )
            lines.append("")

            # Empty table details
            empty_with_fk = [
                t for t in schema.tables if not t.has_data and t.foreign_keys
            ]
            if empty_with_fk:
                lines.append("#### Empty Tables with Foreign Keys")
                lines.append("")
                for table in empty_with_fk:
                    lines.append(f"**`{table.table_name}`:**")
                    for fk in table.foreign_keys:
                        lines.append(
                            f"- `{fk['column']}` → `{fk['foreign_table']}.{fk['foreign_column']}`"
                        )
                    lines.append("")

        # Index details if requested
        if include_indexes:
            tables_with_indexes = [t for t in schema.tables if t.indexes]
            if tables_with_indexes:
                lines.append("### Indexes")
                lines.append("")
                for table in tables_with_indexes:
                    if table.indexes:
                        lines.append(
                            f"#### `{table.table_name}` ({len(table.indexes)} indexes)"
                        )
                        lines.append("")
                        lines.append("| Index Name | Size |")
                        lines.append("|------------|------|")
                        for idx in table.indexes:
                            lines.append(f"| `{idx['name']}` | {idx['size']} |")
                        lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"{i}. {rec}")
    lines.append("")

    return "\n".join(lines)


def _generate_json_report(report: DatabaseReport) -> str:
    """Generate JSON-formatted report"""
    # Convert dataclasses to dicts
    report_dict = asdict(report)
    return json.dumps(report_dict, indent=2, default=str)


# ============================================================================
# CLI INTERFACE
# ============================================================================


def _setup_logging(verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Analyze PostgreSQL database table usage and generate reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick console report
  python analyze_postgres_usage.py

  # Generate markdown report
  python analyze_postgres_usage.py --format markdown --output-file report.md

  # Analyze specific schema with indexes
  python analyze_postgres_usage.py --schema pattern_traceability --include-indexes

  # Generate JSON for programmatic access
  python analyze_postgres_usage.py --format json --output-file stats.json
        """,
    )

    parser.add_argument(
        "--format",
        choices=["console", "markdown", "json"],
        default="console",
        help="Output format (default: console)",
    )

    parser.add_argument(
        "--output-file", type=str, help="Save report to file (stdout if not specified)"
    )

    parser.add_argument("--schema", type=str, help="Analyze specific schema only")

    parser.add_argument(
        "--include-indexes", action="store_true", help="Include detailed index analysis"
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


async def main():
    """Main execution"""
    args = _parse_args()
    _setup_logging(args.verbose)

    try:
        # Run analysis
        report = await analyze_database(
            target_schema=args.schema, include_indexes=args.include_indexes
        )

        # Generate report in requested format
        if args.format == "console":
            output = _generate_console_report(report, args.include_indexes)
        elif args.format == "markdown":
            output = _generate_markdown_report(report, args.include_indexes)
        elif args.format == "json":
            output = _generate_json_report(report)
        else:
            raise ValueError(f"Unsupported format: {args.format}")

        # Output report
        if args.output_file:
            output_path = Path(args.output_file)
            output_path.write_text(output)
            logging.info(f"Report saved to: {output_path.absolute()}")
        else:
            print(output)

        # Exit with status code based on recommendations
        critical_issues = sum(1 for rec in report.recommendations if "⚠️" in rec)
        if critical_issues > 0:
            logging.warning(f"Found {critical_issues} critical issues")
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        logging.error(f"Analysis failed: {e}", exc_info=args.verbose)
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
