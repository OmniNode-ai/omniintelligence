#!/usr/bin/env python3
"""
Poetry-enabled Intelligence Hook Wrapper

This wrapper ensures the intelligence hook runs in the proper Poetry environment
with all dependencies available.
"""

import os
import subprocess
import sys
from pathlib import Path


def find_archon_root():
    """Find the Archon project root directory."""
    current = Path(__file__).resolve()

    # Look for pyproject.toml or .git directory
    for parent in current.parents:
        if (parent / "python" / "pyproject.toml").exists():
            return parent
        if (parent / "pyproject.toml").exists():
            return parent
        if (parent / ".git").exists() and parent.name == "Archon":
            return parent

    # Fallback to parent directory of scripts
    return current.parent.parent


def main():
    """Run the intelligence hook using Poetry if available."""
    # Find Archon root
    archon_root = find_archon_root()
    python_dir = archon_root / "python"

    # Check if we should use Poetry
    use_poetry = False
    if python_dir.exists() and (python_dir / "pyproject.toml").exists():
        # Check if poetry is available
        try:
            subprocess.run(
                ["poetry", "--version"], capture_output=True, check=True, cwd=python_dir
            )
            use_poetry = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(
                "⚠️  Poetry not available, falling back to direct Python execution",
                file=sys.stderr,
            )

    # Prepare the intelligence hook script path
    hook_script = archon_root / "scripts" / "intelligence_hook.py"

    if not hook_script.exists():
        print(f"❌ Intelligence hook script not found: {hook_script}", file=sys.stderr)
        sys.exit(1)

    # Prepare command
    if use_poetry:
        print(
            f"🎯 Running intelligence hook via Poetry from {python_dir}",
            file=sys.stderr,
        )
        cmd = ["poetry", "run", "python", str(hook_script)] + sys.argv[1:]
        subprocess.run(cmd, cwd=python_dir)
    else:
        print("🐍 Running intelligence hook via direct Python", file=sys.stderr)
        # Add the project root to Python path
        env = os.environ.copy()
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{archon_root / 'python' / 'src'}:{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = str(archon_root / "python" / "src")

        cmd = ["python3", str(hook_script)] + sys.argv[1:]
        subprocess.run(cmd, env=env)


if __name__ == "__main__":
    main()
