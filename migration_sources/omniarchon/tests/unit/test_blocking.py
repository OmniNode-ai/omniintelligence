"""This file should be BLOCKED from being written."""


class BadClassName:  # This violates snake_case for functions
    def camelCaseMethod(self):  # Should be snake_case
        return "blocked"


def anotherBadName():  # Should be snake_case
    return "test"
