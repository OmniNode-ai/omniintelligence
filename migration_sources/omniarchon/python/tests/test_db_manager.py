#!/usr/bin/env python3
"""
Test Database Manager

Simple script to manage the test database container for Archon integration tests.

Usage:
    python test_db_manager.py start    # Start the test database
    python test_db_manager.py stop     # Stop the test database
    python test_db_manager.py status   # Check database status
    python test_db_manager.py logs     # View database logs
    python test_db_manager.py reset    # Reset database (stop, remove, start fresh)
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


class TestDBManager:
    """Manager for Archon test database container"""

    def __init__(self):
        self.project_root = Path(__file__).parent

    def run_docker_compose(self, command: list, capture_output: bool = False) -> bool:
        """Run docker compose command"""
        full_cmd = [
            "docker",
            "compose",
            "-f",
            "docker-compose.test.yml",
            "--env-file",
            ".env.test",
        ] + command

        try:
            if capture_output:
                result = subprocess.run(
                    full_cmd, cwd=self.project_root, capture_output=True, text=True
                )
                print(result.stdout)
                if result.stderr:
                    print(result.stderr)
                return result.returncode == 0
            else:
                result = subprocess.run(full_cmd, cwd=self.project_root)
                return result.returncode == 0
        except Exception as e:
            print(f"❌ Error running docker compose: {e}")
            return False

    def start(self) -> bool:
        """Start the test Supabase stack"""
        print("🚀 Starting test Supabase stack...")

        if not self.run_docker_compose(["up", "-d"]):
            print("❌ Failed to start test Supabase")
            return False

        print("⏳ Waiting for Supabase to be ready...")

        # Wait for Supabase to be healthy
        max_attempts = 60  # 60 seconds max (Supabase takes longer to start)
        for attempt in range(max_attempts):
            if self.check_health():
                print("✅ Test Supabase is ready!")
                return True
            time.sleep(1)
            if attempt % 5 == 0:  # Print every 5 seconds
                print(
                    f"   Waiting for Supabase services... ({attempt + 1}/{max_attempts})"
                )

        print("❌ Supabase did not become ready in time")
        return False

    def stop(self) -> bool:
        """Stop the test Supabase stack"""
        print("🛑 Stopping test Supabase...")
        return self.run_docker_compose(["stop"])

    def status(self) -> bool:
        """Check status of test Supabase"""
        print("🔍 Checking test Supabase status...")
        return self.run_docker_compose(["ps"], capture_output=True)

    def logs(self) -> bool:
        """Show Supabase logs"""
        print("📋 Test Supabase logs:")
        return self.run_docker_compose(["logs", "-f"])

    def reset(self) -> bool:
        """Reset the Supabase stack (stop, remove, start fresh)"""
        print("♻️  Resetting test Supabase...")

        # Stop and remove containers and volumes
        self.run_docker_compose(["down", "-v"])

        # Start fresh
        return self.start()

    def check_health(self) -> bool:
        """Check if Supabase is healthy by testing the API endpoint"""
        try:
            import urllib.request

            # Test the health endpoint
            with urllib.request.urlopen(
                "http://localhost:54321/rest/v1/", timeout=3
            ) as response:
                return response.status == 200
        except Exception:
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Manage Archon test database")
    parser.add_argument(
        "action",
        choices=["start", "stop", "status", "logs", "reset"],
        help="Action to perform",
    )

    args = parser.parse_args()
    manager = TestDBManager()

    # Check if .env.test exists
    env_file = Path(".env.test")
    if not env_file.exists():
        print("❌ .env.test file not found")
        print("   Please make sure you're running this from the project root")
        sys.exit(1)

    success = False

    if args.action == "start":
        success = manager.start()
    elif args.action == "stop":
        success = manager.stop()
    elif args.action == "status":
        success = manager.status()
    elif args.action == "logs":
        success = manager.logs()
    elif args.action == "reset":
        success = manager.reset()

    if (
        not success and args.action != "logs"
    ):  # logs command often "fails" when user exits
        sys.exit(1)


if __name__ == "__main__":
    main()
