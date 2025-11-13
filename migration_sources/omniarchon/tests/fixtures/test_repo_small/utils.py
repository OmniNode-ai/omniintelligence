"""
Utility module with no dependencies.

This file is imported by main.py but doesn't import anything else.
"""


def helper_function():
    """Helper function for main module."""
    return "Helper function executed"


class HelperClass:
    """Helper class for main module."""

    def __init__(self):
        self.name = "HelperClass"

    def do_something(self):
        """Perform some action."""
        return f"{self.name} did something"
