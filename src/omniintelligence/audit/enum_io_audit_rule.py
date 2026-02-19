"""EnumIOAuditRule - I/O audit rule identifiers."""

from __future__ import annotations

from enum import Enum


class EnumIOAuditRule(Enum):
    """I/O audit rule identifiers.

    These are the canonical rule IDs used in error messages and pragmas.
    """

    NET_CLIENT = "net-client"
    ENV_ACCESS = "env-access"
    FILE_IO = "file-io"
