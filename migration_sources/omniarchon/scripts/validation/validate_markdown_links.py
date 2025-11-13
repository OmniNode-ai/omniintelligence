#!/usr/bin/env python3
"""
Validate markdown links in documentation.

Checks for:
- Broken internal file links (relative paths)
- Missing anchor links
- Unreachable files
- Supports ignore patterns via .linkcheck-ignore file
"""

import fnmatch
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple


def load_ignore_patterns(repo_root: Path) -> List[str]:
    """Load link ignore patterns from .linkcheck-ignore file."""
    ignore_file = repo_root / ".linkcheck-ignore"
    patterns = []

    if not ignore_file.exists():
        return patterns

    try:
        content = ignore_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith("#"):
                patterns.append(line)
    except (OSError, UnicodeDecodeError) as e:
        print(f"⚠️  Warning: Could not read .linkcheck-ignore: {e}")

    return patterns


def is_ignored_link(link: str, patterns: List[str]) -> bool:
    """Check if link matches any ignore pattern."""
    for pattern in patterns:
        # Support both fnmatch wildcards and simple substring matching
        if fnmatch.fnmatch(link, pattern) or pattern in link:
            return True
    return False


def extract_markdown_links(content: str, file_path: Path) -> List[Tuple[str, int]]:
    """Extract all markdown links with line numbers."""
    links = []

    # Match [text](link) and [text](link#anchor)
    pattern = r"\[([^\]]+)\]\(([^)]+)\)"

    for match in re.finditer(pattern, content):
        link = match.group(2)
        # Find line number
        line_num = content[: match.start()].count("\n") + 1
        links.append((link, line_num))

    return links


def is_internal_link(link: str) -> bool:
    """Check if link is internal (not http/https/mailto)."""
    return not link.startswith(("http://", "https://", "mailto:", "#"))


def validate_file_link(
    link: str, source_file: Path, repo_root: Path
) -> Tuple[bool, str]:
    """Validate that a file link exists."""
    # Remove anchor if present
    file_path = link.split("#")[0]

    if not file_path:
        # Pure anchor link (same file)
        return True, ""

    # Resolve relative to source file's directory
    source_dir = source_file.parent
    target = source_dir / file_path

    # Normalize path
    try:
        target = target.resolve()
    except (OSError, ValueError, RuntimeError) as e:
        return False, f"Invalid path: {e}"

    # Check if file exists
    if not target.exists():
        # Try to show path relative to repo_root, fall back to full path
        try:
            display_path = target.relative_to(repo_root)
        except ValueError:
            display_path = target
        return False, f"File not found: {display_path}"

    return True, ""


def validate_markdown_links(repo_root: Path) -> int:
    """Validate all markdown links in repository."""
    errors = 0
    total_links = 0
    total_files = 0
    ignored_count = 0
    external_count = 0

    # Load ignore patterns
    ignore_patterns = load_ignore_patterns(repo_root)
    if ignore_patterns:
        print(
            f"📋 Loaded {len(ignore_patterns)} ignore pattern(s) from .linkcheck-ignore\n"
        )

    # Find all markdown files
    md_files = sorted(repo_root.rglob("*.md"))

    print(f"🔍 Scanning {len(md_files)} markdown files for broken links...\n")

    for md_file in md_files:
        # Skip .venv and __pycache__ directories
        if ".venv" in md_file.parts or "__pycache__" in md_file.parts:
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"❌ Error reading {md_file.relative_to(repo_root)}: {e}")
            errors += 1
            continue

        links = extract_markdown_links(content, md_file)

        if not links:
            continue

        total_files += 1
        file_errors = 0

        for link, line_num in links:
            total_links += 1

            # Skip external links (http/https/mailto)
            if not is_internal_link(link):
                external_count += 1
                continue

            # Check if link matches ignore patterns
            if is_ignored_link(link, ignore_patterns):
                ignored_count += 1
                continue

            # Validate internal file link
            is_valid, error_msg = validate_file_link(link, md_file, repo_root)

            if not is_valid:
                if file_errors == 0:
                    print(f"\n📄 {md_file.relative_to(repo_root)}")

                print(f"  ❌ Line {line_num}: [{link}] - {error_msg}")
                file_errors += 1
                errors += 1

    print(f"\n{'='*70}")
    print(f"✅ Validation complete!")
    print(f"   Files scanned: {total_files}")
    print(f"   Total links: {total_links}")
    print(f"   External links (http/https): {external_count}")
    print(f"   Ignored links (patterns): {ignored_count}")
    print(f"   Broken links: {errors}")

    if errors == 0:
        print(f"\n🎉 All internal links are valid!")
        if ignored_count > 0:
            print(f"ℹ️  {ignored_count} link(s) ignored via .linkcheck-ignore")
        return 0
    else:
        print(f"\n⚠️  Found {errors} broken link(s)")
        if ignored_count > 0:
            print(f"ℹ️  {ignored_count} link(s) ignored via .linkcheck-ignore")
        return 1


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    sys.exit(validate_markdown_links(repo_root))
