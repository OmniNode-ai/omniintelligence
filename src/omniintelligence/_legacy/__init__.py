"""Legacy code from omniarchon migration.

This module contains code migrated from the omniarchon project that is
pending refactoring. It is excluded from linting and validation.

DO NOT add new code here. All new development should go in:
- nodes/ - ONEX node implementations
- tools/ - CLI tools and utilities

This code will be incrementally replaced as part of the migration phases.
"""

import warnings

# To suppress this warning during active migration, add to your code:
#   import warnings
#   warnings.filterwarnings(
#       'ignore',
#       category=DeprecationWarning,
#       module='omniintelligence._legacy'
#   )

warnings.warn(
    "omniintelligence._legacy is deprecated. "
    "Code here is pending refactoring and should not be used directly.",
    DeprecationWarning,
    stacklevel=2,
)
