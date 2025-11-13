#!/usr/bin/env python3
"""
Fix Circular Import in Event Model Files

Replaces direct imports from omnibase_core with local imports to avoid circular dependency.

OLD (causes circular import):
    from omnibase_core.models.events.model_event_envelope import (
        ModelEventEnvelope,
        ModelEventSource,
    )

NEW (uses local definitions):
    from typing import TYPE_CHECKING
    from events.models._event_base import ModelEventSource, create_event_envelope

    if TYPE_CHECKING:
        from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope

Also replaces:
    ModelEventEnvelope(...) -> create_event_envelope(...)
"""

import re
from pathlib import Path

# Event model files to fix
EVENT_MODEL_FILES = [
    "autonomous_learning_events.py",
    "bridge_intelligence_events.py",
    "custom_quality_rules_events.py",
    "document_indexing_events.py",
    "document_processing_events.py",
    "entity_extraction_events.py",
    "freshness_database_events.py",
    "freshness_events.py",
    "intelligence_adapter_events.py",
    "pattern_analytics_events.py",
    "pattern_learning_events.py",
    "pattern_traceability_events.py",
    "performance_analytics_events.py",
    "performance_events.py",
    "quality_assessment_events.py",
    "quality_trends_events.py",
    "repository_crawler_events.py",
    "search_events.py",
    "system_utilities_events.py",
]

# Base path
BASE_PATH = Path(__file__).parent / "src" / "events" / "models"

# Old import pattern (multi-line)
OLD_IMPORT_PATTERN = r"from omnibase_core\.models\.events\.model_event_envelope import \(\s*ModelEventEnvelope,\s*ModelEventSource,\s*\)"

# New import block
NEW_IMPORT_BLOCK = """from typing import TYPE_CHECKING

# Import from local event base to avoid circular imports
from ._event_base import ModelEventSource, create_event_envelope

# Type-only import for type hints
if TYPE_CHECKING:
    from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope"""


# Pattern to find ModelEventEnvelope( calls and replace with create_event_envelope(
# This is more complex because we need to reorder parameters
def replace_envelope_calls(content: str) -> str:
    """Replace ModelEventEnvelope(...) with create_event_envelope(...) and reorder params."""

    # Find all ModelEventEnvelope( instances
    pattern = r"ModelEventEnvelope\("

    # Simple replacement - just change the function name
    # The parameter order in create_event_envelope matches ModelEventEnvelope
    content = re.sub(pattern, "create_event_envelope(", content)

    return content


def fix_file(file_path: Path) -> bool:
    """
    Fix circular imports in a single event model file.

    Returns:
        True if file was modified, False otherwise
    """
    print(f"Processing: {file_path.name}")

    # Read file
    try:
        content = file_path.read_text()
    except Exception as e:
        print(f"  ERROR reading file: {e}")
        return False

    original_content = content

    # Replace import block
    content = re.sub(
        OLD_IMPORT_PATTERN, NEW_IMPORT_BLOCK, content, flags=re.MULTILINE | re.DOTALL
    )

    # Also need to add TYPE_CHECKING to existing typing imports if not present
    if "from typing import" in content and "TYPE_CHECKING" not in content:
        # Find the typing import line and add TYPE_CHECKING
        content = re.sub(
            r"from typing import ([^(\n]+)",
            r"from typing import TYPE_CHECKING, \1",
            content,
        )

    # Replace ModelEventEnvelope calls
    content = replace_envelope_calls(content)

    if content == original_content:
        print(f"  No changes needed")
        return False

    # Write file back
    try:
        file_path.write_text(content)
        print(f"  ✅ Fixed")
        return True
    except Exception as e:
        print(f"  ERROR writing file: {e}")
        return False


def main():
    """Fix all event model files."""
    print(f"Fixing circular imports in {len(EVENT_MODEL_FILES)} event model files...")
    print(f"Base path: {BASE_PATH}\n")

    fixed_count = 0
    error_count = 0

    for filename in EVENT_MODEL_FILES:
        file_path = BASE_PATH / filename

        if not file_path.exists():
            print(f"WARNING: {filename} not found")
            error_count += 1
            continue

        try:
            if fix_file(file_path):
                fixed_count += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Total files: {len(EVENT_MODEL_FILES)}")
    print(f"  Fixed: {fixed_count}")
    print(f"  Unchanged: {len(EVENT_MODEL_FILES) - fixed_count - error_count}")
    print(f"  Errors: {error_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
