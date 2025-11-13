"""Enum for canary impure tool actions."""

from enum import Enum


class EnumCanaryImpureAction(str, Enum):
    """
    Enumeration of canary impure tool actions.

    Defines the specific types of impure operations (with side effects)
    that can be performed by the canary tool.
    """

    WRITE_FILE = "write_file"
    APPEND_LOG = "append_log"
    SEND_NOTIFICATION = "send_notification"
    MODIFY_STATE = "modify_state"
