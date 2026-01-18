# SPDX-License-Identifier: Apache-2.0
"""
Basic import tests for the tools module.

These tests verify that the tools module can be imported without errors,
regardless of whether optional dependencies (like omnibase_core) are available.
"""

import pytest


@pytest.mark.unit
class TestToolsModuleImport:
    """Tests for tools module importability."""

    def test_tools_module_imports(self) -> None:
        """Test that the tools module can be imported.

        This test ensures that the tools module has graceful handling
        of optional dependencies and can be imported even when
        omnibase_core is not available.
        """
        # This import should always succeed, even without omnibase_core
        import omniintelligence.tools  # noqa: F401

        # Verify the module exists
        assert omniintelligence.tools is not None

    def test_tools_all_attribute_exists(self) -> None:
        """Test that __all__ is defined on the tools module."""
        import omniintelligence.tools

        assert hasattr(omniintelligence.tools, "__all__")
        # __all__ should be a list (possibly empty if dependencies missing)
        assert isinstance(omniintelligence.tools.__all__, list)
