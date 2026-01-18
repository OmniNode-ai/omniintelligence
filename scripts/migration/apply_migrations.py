#!/usr/bin/env python3
"""
Apply database migrations for omniintelligence.

This script applies SQL migrations in order to set up the database schema.
"""

import asyncio
import sys
from pathlib import Path
import asyncpg


class MigrationRunner:
    """Database migration runner."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.migrations_dir = Path(__file__).parent.parent.parent / "deployment" / "database" / "migrations"

    async def get_connection(self) -> asyncpg.Connection:
        """Get database connection."""
        return await asyncpg.connect(self.database_url)

    async def create_migrations_table(self, conn: asyncpg.Connection):
        """Create migrations tracking table if it doesn't exist."""
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id SERIAL PRIMARY KEY,
                migration_name VARCHAR(255) NOT NULL UNIQUE,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                checksum VARCHAR(64)
            )
        """)

    async def get_applied_migrations(self, conn: asyncpg.Connection) -> list[str]:
        """Get list of applied migrations."""
        rows = await conn.fetch(
            "SELECT migration_name FROM schema_migrations ORDER BY migration_name"
        )
        return [row["migration_name"] for row in rows]

    def get_pending_migrations(self, applied: list[str]) -> list[Path]:
        """Get list of pending migration files."""
        all_migrations = sorted(self.migrations_dir.glob("*.sql"))
        return [
            mig for mig in all_migrations
            if mig.stem not in applied
        ]

    async def apply_migration(
        self,
        conn: asyncpg.Connection,
        migration_file: Path,
    ) -> bool:
        """
        Apply a single migration.

        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"Applying migration: {migration_file.name}")

            # Read migration SQL
            sql = migration_file.read_text()

            # Execute migration
            async with conn.transaction():
                await conn.execute(sql)

                # Record migration
                await conn.execute(
                    """
                    INSERT INTO schema_migrations (migration_name)
                    VALUES ($1)
                    """,
                    migration_file.stem,
                )

            print(f"✓ Applied: {migration_file.name}")
            return True

        except Exception as e:
            print(f"✗ Failed: {migration_file.name}")
            print(f"  Error: {e}")
            return False

    async def run_migrations(self, stop_on_error: bool = True) -> int:
        """
        Run all pending migrations.

        Args:
            stop_on_error: Stop on first error

        Returns:
            Number of migrations applied
        """
        conn = await self.get_connection()
        try:
            # Create migrations table
            await self.create_migrations_table(conn)

            # Get applied and pending migrations
            applied = await self.get_applied_migrations(conn)
            pending = self.get_pending_migrations(applied)

            if not pending:
                print("No pending migrations.")
                return 0

            print(f"Found {len(pending)} pending migration(s)")

            applied_count = 0
            for migration_file in pending:
                success = await self.apply_migration(conn, migration_file)
                if success:
                    applied_count += 1
                elif stop_on_error:
                    print("Stopping due to error.")
                    break

            print(f"\nApplied {applied_count} migration(s)")
            return applied_count

        finally:
            await conn.close()

    async def show_status(self):
        """Show migration status."""
        conn = await self.get_connection()
        try:
            await self.create_migrations_table(conn)

            applied = await self.get_applied_migrations(conn)
            pending = self.get_pending_migrations(applied)

            print("Migration Status")
            print("=" * 60)
            print(f"Applied migrations: {len(applied)}")
            for name in applied:
                print(f"  ✓ {name}")

            print(f"\nPending migrations: {len(pending)}")
            for mig_file in pending:
                print(f"  - {mig_file.name}")

        finally:
            await conn.close()


async def main():
    """Main entry point."""
    import os
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Apply database migrations")
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL"),
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue applying migrations even if one fails",
    )

    args = parser.parse_args()

    if not args.database_url:
        print("Error: DATABASE_URL not set")
        sys.exit(1)

    runner = MigrationRunner(args.database_url)

    try:
        if args.status:
            await runner.show_status()
        else:
            await runner.run_migrations(stop_on_error=not args.continue_on_error)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
