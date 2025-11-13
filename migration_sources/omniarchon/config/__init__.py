"""Configuration module for Archon services."""

from .settings import Settings, get_settings, settings
from .timeout_config import (
    AsyncOperationTimeoutConfig,
    BackgroundTaskTimeoutConfig,
    CacheTimeoutConfig,
    DatabaseTimeoutConfig,
    HTTPTimeoutConfig,
    RetryConfig,
    ServiceRestartTimeoutConfig,
    TestTimeoutConfig,
    TimeoutConfig,
    get_async_timeout,
    get_cache_timeout,
    get_db_timeout,
    get_http_timeout,
    get_retry_config,
    timeout_config,
)

__all__ = [
    # Settings module
    "Settings",
    "get_settings",
    "settings",
    # Timeout config
    "TimeoutConfig",
    "HTTPTimeoutConfig",
    "DatabaseTimeoutConfig",
    "CacheTimeoutConfig",
    "AsyncOperationTimeoutConfig",
    "BackgroundTaskTimeoutConfig",
    "TestTimeoutConfig",
    "ServiceRestartTimeoutConfig",
    "RetryConfig",
    "timeout_config",
    "get_http_timeout",
    "get_db_timeout",
    "get_cache_timeout",
    "get_async_timeout",
    "get_retry_config",
]
