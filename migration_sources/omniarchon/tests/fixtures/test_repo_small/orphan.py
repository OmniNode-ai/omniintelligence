"""
Orphaned file with no imports or references.

This file should be detected as an orphan since nothing imports it
and it doesn't import anything from the project.
"""


def orphaned_function():
    """This function is never called from the project."""
    return "I am orphaned and alone"


class OrphanedClass:
    """This class is never imported or used."""

    def __init__(self):
        self.status = "orphaned"
