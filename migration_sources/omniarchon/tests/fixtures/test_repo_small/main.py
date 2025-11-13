"""
Main module for test repository.

This file imports from utils.py and serves as the entry point.
"""

from utils import helper_function, HelperClass


def main():
    """Main function that uses helper utilities."""
    result = helper_function()
    helper = HelperClass()
    helper.do_something()
    return result


if __name__ == "__main__":
    main()
