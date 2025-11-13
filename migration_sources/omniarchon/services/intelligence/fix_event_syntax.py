#!/usr/bin/env python3
"""
Fix all event model files to use omnibase_core imports instead of custom _event_base.

Changes:
1. Remove import from ._event_base
2. Add import from omnibase_core.models.events.model_event_envelope
3. Fix create_event_envelope() calls to use ModelEventEnvelope() constructor
"""

import re
from pathlib import Path

# Event files to fix
EVENT_FILES = [
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

BASE_DIR = Path(__file__).parent / "src" / "events" / "models"


def fix_imports(content: str) -> str:
    """Fix imports to use omnibase_core instead of custom _event_base."""
    # Remove the custom import line
    content = re.sub(
        r"^from \._event_base import ModelEventEnvelope(?:, ModelEventSource)?\n",
        "",
        content,
        flags=re.MULTILINE,
    )

    # Remove any standalone comment about local event base
    content = re.sub(
        r"^# Import from local event base to avoid circular imports\n",
        "",
        content,
        flags=re.MULTILINE,
    )

    # Add omnibase_core import after the pydantic import
    if (
        "from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope"
        not in content
    ):
        # Find the pydantic import line
        pydantic_import_pattern = r"(from pydantic import[^\n]+\n)"
        match = re.search(pydantic_import_pattern, content)
        if match:
            # Insert after pydantic import
            insert_pos = match.end()
            content = (
                content[:insert_pos]
                + "\n# Import ModelEventEnvelope from omnibase_core\n"
                + "from omnibase_core.models.events.model_event_envelope import ModelEventEnvelope\n"
                + content[insert_pos:]
            )

    return content


def fix_create_event_envelope(content: str) -> str:
    """Fix create_event_envelope() calls to use ModelEventEnvelope() constructor."""

    # Pattern to match the create_event_envelope() call
    # Looking for the pattern with ModelEventSource
    pattern = r'envelope = create_event_envelope\(\s*event_type=f"omninode\.{([^}]+)}\.{([^}]+)}\.{([^}]+)}\.{event_type}\.{([^}]+)}",\s*payload=payload if isinstance\(payload, dict\) else payload\.model_dump\(\),\s*correlation_id=correlation_id,\s*causation_id=causation_id,\s*source=ModelEventSource\(\s*service=([^,]+),\s*instance_id=([^,]+),\s*hostname=None,\s*\),\s*\)'

    # Replacement using ModelEventEnvelope constructor
    def replace_func(match):
        domain = match.group(1)
        pattern = match.group(2)
        event_pattern = match.group(3)
        version = match.group(4)
        service = match.group(5)
        instance_id = match.group(6)

        return f"""envelope = ModelEventEnvelope(
            payload=payload if isinstance(payload, dict) else payload.model_dump(),
            correlation_id=correlation_id,
            source_tool="omninode-intelligence",
            metadata={{
                "event_type": f"omninode.{{{domain}}}.{{{pattern}}}.{{event_type}}.{{{version}}}",
                "service": {service},
                "instance_id": {instance_id},
                "causation_id": str(causation_id) if causation_id else None,
            }}
        )"""

    content = re.sub(pattern, replace_func, content, flags=re.DOTALL)

    return content


def process_file(filepath: Path) -> bool:
    """Process a single event file."""
    try:
        print(f"Processing {filepath.name}...")

        # Read file
        content = filepath.read_text()

        # Apply fixes
        original_content = content
        content = fix_imports(content)
        content = fix_create_event_envelope(content)

        # Check if anything changed
        if content == original_content:
            print(f"  ⚠️  No changes needed for {filepath.name}")
        else:
            # Write back
            filepath.write_text(content)
            print(f"  ✅ Fixed {filepath.name}")

        return True
    except Exception as e:
        print(f"  ❌ Error fixing {filepath.name}: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Fix all event files."""
    print("=" * 60)
    print("Fixing event model files to use omnibase_core")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for filename in EVENT_FILES:
        filepath = BASE_DIR / filename
        if filepath.exists():
            if process_file(filepath):
                success_count += 1
            else:
                fail_count += 1
        else:
            print(f"  ⚠️  File not found: {filename}")
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"Summary: {success_count} fixed, {fail_count} failed")
    print("=" * 60)

    if fail_count == 0:
        print("\n✅ All files processed!")
        print("\nNext step: Delete custom _event_base.py file")
    else:
        print("\n⚠️  Some files had errors. Please review.")


if __name__ == "__main__":
    main()
