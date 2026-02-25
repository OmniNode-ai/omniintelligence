"""Typed intent class enum for the 8-class classification system."""

from __future__ import annotations

from enum import Enum


class EnumIntentClass(str, Enum):
    """8-class typed intent classification system.

    Each class drives downstream behavior: model selection, temperature,
    validator set, permission scope, and sandbox enforcement.

    Attributes:
        REFACTOR: Code refactoring, quality improvement, restructuring.
        BUGFIX: Bug fixing, error resolution, crash recovery.
        FEATURE: New feature development, capability addition.
        ANALYSIS: Code review, investigation, evaluation — read-only.
        CONFIGURATION: Config changes, schema updates, settings management.
        DOCUMENTATION: Writing docs, README, docstrings, guides.
        MIGRATION: DB migrations, data transformations, schema migrations.
        SECURITY: Security audits, auth, encryption, permission changes.
    """

    REFACTOR = "REFACTOR"
    BUGFIX = "BUGFIX"
    FEATURE = "FEATURE"
    ANALYSIS = "ANALYSIS"
    CONFIGURATION = "CONFIGURATION"
    DOCUMENTATION = "DOCUMENTATION"
    MIGRATION = "MIGRATION"
    SECURITY = "SECURITY"


__all__ = ["EnumIntentClass"]
