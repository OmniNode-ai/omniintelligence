#!/usr/bin/env python3
"""
Fix Wave 6 Integration Tests
Applies systematic fixes to all failing Wave 6 tests:
1. Fix publish call_args access (KeyError: 'event')
2. Add MagicMock imports where missing
"""

import os
import re

test_dir = "tests/integration/wave6"


def fix_publish_call_args(content):
    """Fix publish call_args access pattern."""
    # Pattern 1: publish_call[1]["event"] -> publish_call[0][1]
    content = re.sub(
        r'published_event = publish_call\[1\]\["event"\]',
        "published_event = publish_call[0][1]  # 2nd positional argument is the event",
        content,
    )
    return content


def fix_magic_mock_import(content):
    """Add MagicMock to imports if using it but not imported."""
    # Check if MagicMock is used but not imported
    if "MagicMock" in content and "from unittest.mock import" in content:
        # Check if MagicMock is already in the import
        if "import MagicMock" not in content:
            # Add MagicMock to the import line
            content = re.sub(
                r"from unittest.mock import (AsyncMock, patch)",
                r"from unittest.mock import AsyncMock, MagicMock, patch",
                content,
            )
    return content


def process_file(filepath):
    """Process a single test file."""
    with open(filepath, "r") as f:
        content = f.read()

    original = content
    content = fix_publish_call_args(content)
    content = fix_magic_mock_import(content)

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        print(f"Fixed: {filepath}")
        return True
    else:
        print(f"No changes: {filepath}")
        return False


def main():
    """Process all Wave 6 test files."""
    fixed_count = 0
    for filename in os.listdir(test_dir):
        if filename.startswith("test_") and filename.endswith(".py"):
            filepath = os.path.join(test_dir, filename)
            if process_file(filepath):
                fixed_count += 1

    print(f"\nFixed {fixed_count} files")


if __name__ == "__main__":
    main()
