#!/usr/bin/env python3
"""
Analyze markdown file naming conventions in the repository.
Categorize files by their naming pattern and generate rename recommendations.
"""

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


def categorize_filename(filename: str) -> str:
    """Categorize a filename by its naming pattern."""
    # Skip special files that should not be renamed
    if filename in ["README.md", "CLAUDE.md", "INITIAL.md"]:
        return "KEEP_AS_IS"

    # ALL_CAPS_WITH_UNDERSCORES (e.g., EVENT_BUS_ARCHITECTURE.md)
    if re.match(r"^[A-Z][A-Z0-9_]*\.md$", filename):
        return "ALL_CAPS_UNDERSCORES"

    # kebab-case (e.g., agent-api-architect.md, pr-workflow-guide.md)
    if re.match(r"^[a-z][a-z0-9-]*\.md$", filename):
        return "KEBAB_CASE"

    # PascalCase or Mixed (e.g., OmniNode_Orchestrator.md)
    if re.match(r"^[A-Z]", filename) and "_" in filename:
        return "MIXED_PASCAL_UNDERSCORES"

    # camelCase starting with lowercase
    if re.match(r"^[a-z][a-zA-Z0-9]*\.md$", filename):
        return "CAMEL_CASE"

    # Numbers at start (e.g., 2025-10-01_final_design.md)
    if re.match(r"^\d", filename):
        return "STARTS_WITH_NUMBER"

    return "OTHER"


def convert_to_all_caps_underscores(filename: str) -> str:
    """Convert filename to ALL_CAPS_WITH_UNDERSCORES format."""
    # Special files keep their name
    if filename in ["README.md", "CLAUDE.md", "INITIAL.md"]:
        return filename

    # Remove .md extension
    name = filename[:-3] if filename.endswith(".md") else filename

    # Handle different patterns
    # If already ALL_CAPS_WITH_UNDERSCORES, return as-is
    if re.match(r"^[A-Z][A-Z0-9_]*$", name):
        return filename

    # Convert kebab-case to UNDERSCORES: agent-api-architect -> AGENT_API_ARCHITECT
    if "-" in name:
        name = name.replace("-", "_")

    # Convert spaces to underscores
    name = name.replace(" ", "_")

    # Convert camelCase/PascalCase to UNDERSCORES
    # Insert underscore before capitals that follow lowercase
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)

    # Convert to uppercase
    name = name.upper()

    # Clean up multiple underscores
    name = re.sub(r"_+", "_", name)

    # Remove leading/trailing underscores
    name = name.strip("_")

    return f"{name}.md"


def scan_markdown_files(root_dir: str) -> Dict[str, List[Tuple[str, str, str]]]:
    """
    Scan all git-tracked markdown files and categorize them.
    Returns dict: {category: [(filepath, filename, proposed_name), ...]}
    """
    import subprocess

    categories = defaultdict(list)

    # Get list of git-tracked markdown files
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.md"],
            cwd=root_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        tracked_files = result.stdout.strip().split("\n")
    except subprocess.CalledProcessError:
        print("Error: Could not get git-tracked files. Is this a git repository?")
        return categories

    for relative_path in tracked_files:
        if not relative_path:  # Skip empty lines
            continue

        file = os.path.basename(relative_path)
        category = categorize_filename(file)
        proposed_name = convert_to_all_caps_underscores(file)

        categories[category].append((relative_path, file, proposed_name))

    return categories


def generate_report(categories: Dict[str, List[Tuple[str, str, str]]]) -> str:
    """Generate a markdown report of the analysis."""
    report = []
    report.append("# Markdown File Naming Convention Analysis\n")
    report.append(
        f"**Total files analyzed**: {sum(len(files) for files in categories.values())}\n"
    )

    # Summary by category
    report.append("## Summary by Category\n")
    for category in sorted(categories.keys()):
        count = len(categories[category])
        percentage = (count / sum(len(files) for files in categories.values())) * 100
        report.append(f"- **{category}**: {count} files ({percentage:.1f}%)")

    report.append("\n## Recommendations\n")
    report.append(
        "**Standard**: ALL_CAPS_WITH_UNDERSCORES.md (based on existing pattern)\n"
    )
    report.append("**Exceptions**: README.md, CLAUDE.md, INITIAL.md (keep as-is)\n")

    # Detailed breakdown
    report.append("\n## Files Requiring Rename\n")

    for category in sorted(categories.keys()):
        if category == "KEEP_AS_IS" or category == "ALL_CAPS_UNDERSCORES":
            continue

        files = categories[category]
        if not files:
            continue

        report.append(f"\n### {category} ({len(files)} files)\n")
        report.append("| Current Path | Current Name | Proposed Name |")
        report.append("|--------------|--------------|---------------|")

        for filepath, filename, proposed in sorted(files):
            # Only show if rename is needed
            if filename != proposed:
                # Truncate long paths for readability
                display_path = (
                    filepath if len(filepath) < 50 else "..." + filepath[-47:]
                )
                report.append(f"| {display_path} | {filename} | {proposed} |")

    # Files that are already compliant
    report.append("\n## Files Already Compliant\n")
    compliant = categories.get("ALL_CAPS_UNDERSCORES", []) + categories.get(
        "KEEP_AS_IS", []
    )
    report.append(f"**Total**: {len(compliant)} files\n")

    return "\n".join(report)


def generate_rename_script(
    categories: Dict[str, List[Tuple[str, str, str]]], root_dir: str
) -> str:
    """Generate a bash script with git mv commands."""
    script = []
    script.append("#!/bin/bash")
    script.append(
        "# Generated script to rename markdown files to ALL_CAPS_WITH_UNDERSCORES"
    )
    script.append("# Run from repository root: /Volumes/PRO-G40/Code/omniarchon")
    script.append("")
    script.append("set -e  # Exit on error")
    script.append("")

    rename_count = 0

    for category in sorted(categories.keys()):
        if category in ["KEEP_AS_IS", "ALL_CAPS_UNDERSCORES"]:
            continue

        files = categories[category]
        if not files:
            continue

        script.append(f"# {category} ({len(files)} files)")

        for filepath, filename, proposed in sorted(files):
            if filename == proposed:
                continue

            # Get directory
            dir_path = os.path.dirname(filepath)
            new_filepath = os.path.join(dir_path, proposed) if dir_path else proposed

            script.append(f'git mv "{filepath}" "{new_filepath}"')
            rename_count += 1

        script.append("")

    script.append(f"echo 'Renamed {rename_count} files'")

    return "\n".join(script)


if __name__ == "__main__":
    root_dir = "/Volumes/PRO-G40/Code/omniarchon"

    print("Scanning markdown files...")
    categories = scan_markdown_files(root_dir)

    print("\nGenerating report...")
    report = generate_report(categories)

    # Write report
    report_path = os.path.join(root_dir, "MARKDOWN_NAMING_ANALYSIS_REPORT.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Report written to: {report_path}")

    # Generate rename script
    script = generate_rename_script(categories, root_dir)
    script_path = os.path.join(root_dir, "rename_markdown_files.sh")
    with open(script_path, "w") as f:
        f.write(script)
    os.chmod(script_path, 0o755)  # Make executable
    print(f"Rename script written to: {script_path}")

    print("\nSummary:")
    for category in sorted(categories.keys()):
        print(f"  {category}: {len(categories[category])} files")
