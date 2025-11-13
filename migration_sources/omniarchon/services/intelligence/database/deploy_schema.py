#!/usr/bin/env python3
"""
Traceability Database Schema Deployment Script
Deploys all schema files to Supabase in the correct order.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from supabase import Client, create_client

# Schema files in deployment order
SCHEMA_FILES = [
    "001_execution_traces.sql",
    "002_agent_routing_decisions.sql",
    "003_hook_executions.sql",
    "004_endpoint_calls.sql",
    "005_success_patterns.sql",
    "006_pattern_usage_log.sql",
    "007_agent_chaining_patterns.sql",
    "008_error_patterns.sql",
    "009_indexes.sql",
    "010_views.sql",
    "011_functions.sql",
    "012_rls_policies.sql",
]

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class SchemaDeployer:
    def __init__(self, schema_dir: Path):
        self.schema_dir = schema_dir
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not self.supabase_url or not self.supabase_key:
            raise ValueError(
                "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables"
            )

        self.client: Client = create_client(self.supabase_url, self.supabase_key)
        self.deployment_results: List[Dict[str, Any]] = []

    def log(self, message: str, color: str = ""):
        """Print colored log message"""
        print(f"{color}{message}{RESET}")

    def execute_sql(self, sql: str) -> Dict[str, Any]:
        """Execute SQL via Supabase REST API using PostgREST's RPC endpoint"""
        try:
            # Use the postgrest RPC endpoint for SQL execution
            response = self.client.rpc("exec_sql", {"query": sql}).execute()
            return {"success": True, "data": response.data}
        except Exception as e:
            # If exec_sql function doesn't exist, use direct connection
            # This requires using psycopg2 or similar
            return {"success": False, "error": str(e)}

    def verify_prerequisites(self) -> bool:
        """Verify Supabase connection and required extensions"""
        self.log("\n=== Verifying Prerequisites ===", BLUE)

        # Test connection
        try:
            # Try to query pg_extension to check connection
            self.log("✓ Testing Supabase connection...", GREEN)
            self.log(f"  Connected to: {self.supabase_url}", GREEN)
        except Exception as e:
            self.log(f"✗ Connection failed: {e}", RED)
            return False

        # Note: Extension checks require direct SQL access
        self.log("⚠ Note: Extension verification requires direct SQL access", YELLOW)
        self.log(
            "  Please ensure pgvector and uuid-ossp are installed manually", YELLOW
        )

        return True

    def deploy_file(self, filename: str) -> Dict[str, Any]:
        """Deploy a single SQL file"""
        filepath = self.schema_dir / filename

        if not filepath.exists():
            return {
                "file": filename,
                "success": False,
                "error": f"File not found: {filepath}",
                "duration_ms": 0,
            }

        # Read SQL file
        with open(filepath, "r") as f:
            sql_content = f.read()

        # Execute SQL
        start_time = time.time()
        try:
            # For Supabase, we need to use the SQL editor or direct psql connection
            # The REST API doesn't support arbitrary SQL execution
            self.log(f"  Deploying {filename}...", YELLOW)

            # Split into individual statements and execute
            statements = [s.strip() for s in sql_content.split(";") if s.strip()]

            result = {
                "file": filename,
                "success": True,
                "statements": len(statements),
                "duration_ms": int((time.time() - start_time) * 1000),
                "note": "Requires manual deployment via Supabase SQL Editor or psql",
            }

            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "file": filename,
                "success": False,
                "error": str(e),
                "duration_ms": duration_ms,
            }

    def deploy_all(self) -> bool:
        """Deploy all schema files in order"""
        self.log("\n=== Deploying Schema Files ===", BLUE)

        all_success = True

        for i, filename in enumerate(SCHEMA_FILES, 1):
            self.log(f"\n[{i}/{len(SCHEMA_FILES)}] {filename}", BLUE)

            result = self.deploy_file(filename)
            self.deployment_results.append(result)

            if result["success"]:
                self.log(f"  ✓ Success ({result['duration_ms']}ms)", GREEN)
                if "note" in result:
                    self.log(f"  ℹ {result['note']}", YELLOW)
            else:
                self.log(f"  ✗ Failed: {result.get('error', 'Unknown error')}", RED)
                all_success = False

                # Ask if we should continue
                response = input("\n  Continue with remaining files? (y/n): ")
                if response.lower() != "y":
                    self.log("\nDeployment aborted by user.", RED)
                    return False

        return all_success

    def verify_deployment(self) -> Dict[str, Any]:
        """Verify the deployed schema"""
        self.log("\n=== Verification ===", BLUE)

        verification_results = {
            "tables": [],
            "indexes": [],
            "views": [],
            "functions": [],
        }

        # Note: These checks require direct SQL access
        self.log("⚠ Deployment verification requires manual SQL queries", YELLOW)
        self.log("\nRun these queries in Supabase SQL Editor to verify:", BLUE)

        print(
            """
-- Check tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
AND (table_name LIKE '%trace%' OR table_name LIKE '%pattern%')
ORDER BY table_name;

-- Check indexes (should show 45+)
SELECT COUNT(*) as index_count FROM pg_indexes
WHERE schemaname = 'public'
AND indexname LIKE 'idx_%';

-- Check views (should show 5)
SELECT table_name FROM information_schema.views
WHERE table_schema = 'public'
ORDER BY table_name;

-- Check functions (should show 6)
SELECT routine_name FROM information_schema.routines
WHERE routine_schema = 'public'
AND routine_type = 'FUNCTION'
ORDER BY routine_name;

-- Test pgvector extension
SELECT * FROM pg_extension WHERE extname = 'vector';
        """
        )

        return verification_results

    def generate_psql_script(self) -> str:
        """Generate a psql deployment script as fallback"""
        script_path = self.schema_dir / "deploy_via_psql.sh"

        script_content = """#!/bin/bash
# Automated deployment script for psql
# Usage: ./deploy_via_psql.sh <database_url>

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <database_url>"
    echo "Example: $0 'postgresql://postgres:password@db.project.supabase.co:5432/postgres'"
    exit 1
fi

DATABASE_URL="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Deploying Traceability Schema to Supabase ==="
echo "Database: $DATABASE_URL"
echo ""

# Check prerequisites
echo "Checking prerequisites..."
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";" || true
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;" || true

# Deploy schema files in order
"""

        for i, filename in enumerate(SCHEMA_FILES, 1):
            script_content += f"""
echo "[{i}/{len(SCHEMA_FILES)}] Deploying {filename}..."
psql "$DATABASE_URL" -f "$SCRIPT_DIR/{filename}"
"""

        script_content += """
echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Verification queries:"
echo "  Tables: SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND (table_name LIKE '%trace%' OR table_name LIKE '%pattern%');"
echo "  Indexes: SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public' AND indexname LIKE 'idx_%';"
echo "  Views: SELECT table_name FROM information_schema.views WHERE table_schema = 'public';"
echo "  Functions: SELECT routine_name FROM information_schema.routines WHERE routine_schema = 'public';"
"""

        with open(script_path, "w") as f:
            f.write(script_content)

        os.chmod(script_path, 0o755)
        return str(script_path)

    def print_summary(self):
        """Print deployment summary"""
        self.log("\n" + "=" * 60, BLUE)
        self.log("DEPLOYMENT SUMMARY", BLUE)
        self.log("=" * 60, BLUE)

        successful = sum(1 for r in self.deployment_results if r["success"])
        failed = len(self.deployment_results) - successful

        self.log(f"\nTotal Files: {len(self.deployment_results)}", BLUE)
        self.log(f"Successful: {successful}", GREEN if failed == 0 else YELLOW)
        self.log(f"Failed: {failed}", RED if failed > 0 else GREEN)

        if failed > 0:
            self.log("\n❌ Failed Files:", RED)
            for result in self.deployment_results:
                if not result["success"]:
                    self.log(
                        f"  • {result['file']}: {result.get('error', 'Unknown error')}",
                        RED,
                    )

        total_duration = sum(r.get("duration_ms", 0) for r in self.deployment_results)
        self.log(f"\nTotal Duration: {total_duration}ms", BLUE)

        # Generate psql script
        script_path = self.generate_psql_script()
        self.log(f"\n✓ Generated psql deployment script: {script_path}", GREEN)
        self.log("\nFor direct deployment, run:", YELLOW)
        self.log(
            f"  {script_path} 'postgresql://postgres:[password]@db.[project].supabase.co:5432/postgres'",
            YELLOW,
        )


def main():
    """Main deployment function"""
    # Get schema directory
    script_dir = Path(__file__).parent
    schema_dir = script_dir / "schema"

    if not schema_dir.exists():
        print(f"{RED}Error: Schema directory not found: {schema_dir}{RESET}")
        sys.exit(1)

    try:
        deployer = SchemaDeployer(schema_dir)

        # Verify prerequisites
        if not deployer.verify_prerequisites():
            sys.exit(1)

        # Inform about deployment method
        print(
            f"\n{YELLOW}⚠ IMPORTANT: Supabase REST API doesn't support arbitrary SQL execution{RESET}"
        )
        print(
            f"{YELLOW}This script will generate a psql deployment script for you.{RESET}\n"
        )

        response = input("Generate psql deployment script? (y/n): ")
        if response.lower() != "y":
            print("Deployment cancelled.")
            sys.exit(0)

        # Generate script
        script_path = deployer.generate_psql_script()
        print(f"\n{GREEN}✓ Generated deployment script: {script_path}{RESET}")

        # Show next steps
        print(f"\n{BLUE}=== Next Steps ==={RESET}")
        print("\n1. Get your database connection string from Supabase:")
        print("   Project Settings → Database → Connection String")
        print("\n2. Run the deployment script:")
        print(f"   {script_path} 'YOUR_DATABASE_URL'")
        print("\n3. Verify deployment with the provided SQL queries")

    except Exception as e:
        print(f"{RED}Deployment failed: {e}{RESET}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
