"""Debug test to check Python path"""

import os
import sys


def test_python_path():
    """Print Python path for debugging"""
    print("\n=== PYTHON PATH DEBUG ===")
    print("CWD:", os.getcwd())
    print("\nsys.path:")
    for i, path in enumerate(sys.path):
        print(f"  [{i}] {path}")

    # Check if src is in path
    src_path = os.path.join(os.getcwd(), "src")
    print(f"\nLooking for: {src_path}")
    print(f"Is src in sys.path? {src_path in sys.path}")

    # Try to import services
    try:
        import services

        print(f"\n✓ Successfully imported 'services' from: {services.__file__}")
    except ImportError as e:
        print(f"\n✗ Failed to import 'services': {e}")

    # Try to import archon_services.pattern_learning
    try:
        from archon_services.pattern_learning.phase2_matching.models import (
            model_hybrid_score,
        )

        print(
            f"✓ Successfully imported model_hybrid_score from: {model_hybrid_score.__file__}"
        )
    except ImportError as e:
        print(f"✗ Failed to import from archon_services.pattern_learning: {e}")

    assert True
