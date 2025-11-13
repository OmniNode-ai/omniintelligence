"""
Orphaned file in orphaned directory.

This file should be detected as orphaned since it's not imported
anywhere and doesn't import from the main project.
"""


def unused_function():
    """This function is never used."""
    return "I am completely unused"


class UnusedClass:
    """This class is never imported."""

    def __init__(self):
        self.status = "unused"
        self.purpose = None
