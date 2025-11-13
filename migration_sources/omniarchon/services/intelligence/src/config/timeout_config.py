"""
Timeout configuration bridge.

Re-exports timeout configuration from parent config directory
to avoid import conflicts when services/intelligence/src is in sys.path.
"""

# Import directly from the parent config file to avoid circular import
import sys
from pathlib import Path

# Get the parent config file path
parent_config_file = (
    Path(__file__).parent.parent.parent / "config" / "timeout_config.py"
)

# Load the module directly from file
import importlib.util

spec = importlib.util.spec_from_file_location(
    "timeout_config_parent", parent_config_file
)
parent_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent_module)

# Re-export all public names from parent module
for name in dir(parent_module):
    if not name.startswith("_"):
        globals()[name] = getattr(parent_module, name)
