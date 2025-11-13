"""Test file to trigger naming violations in Archon repo.

This file should NOT trigger Omninode conventions since Archon is excluded.
But it should still validate Python code quality.
"""


# This is just a test file to see hook warnings
class TestClass:
    def testMethod(self):  # camelCase - should be snake_case
        return "test"


def myFunction():  # camelCase - should be snake_case
    return "hello"


MY_CONSTANT = 123  # This is fine - UPPER_SNAKE_CASE
