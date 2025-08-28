"""
Environment Variable Centralization for AIxTerm

This module provides typed accessors for all AIxTerm environment variables,
centralizing environment variable access to prevent drift and provide
a single point of truth.
"""

import os
from typing import Optional


class EnvironmentVariables:
    """Central access point for all AIxTerm environment variables."""

    @staticmethod
    def get_log_level() -> str:
        """
        Get the logging level for AIxTerm.
        
        Returns:
            Log level string (defaults to "WARNING")
        """
        return os.environ.get("AIXTERM_LOG_LEVEL", "WARNING")

    @staticmethod
    def get_runtime_home() -> Optional[str]:
        """
        Get the runtime home directory override.
        
        Returns:
            Runtime home path if set, None otherwise
        """
        return os.environ.get("AIXTERM_RUNTIME_HOME")

    @staticmethod
    def get_show_timing() -> bool:
        """
        Get whether to show timing information.
        
        Returns:
            True if timing should be shown, False otherwise
        """
        return os.environ.get("AIXTERM_SHOW_TIMING", "").lower() in ("1", "true", "yes")

    @staticmethod
    def get_test_idle_grace() -> float:
        """
        Get the idle grace period for tests.
        
        Returns:
            Grace period in seconds (defaults to 0.4)
        """
        return float(os.environ.get("AIXTERM_TEST_IDLE_GRACE", "0.4"))

    @staticmethod
    def get_test_idle_limit() -> float:
        """
        Get the idle limit for tests.
        
        Returns:
            Idle limit in seconds (defaults to 2.0)
        """
        return float(os.environ.get("AIXTERM_TEST_IDLE_LIMIT", "2.0"))

    @staticmethod
    def get_pytest_current_test() -> Optional[str]:
        """
        Get the current pytest test name.
        
        Returns:
            Test name if running under pytest, None otherwise
        """
        return os.environ.get("PYTEST_CURRENT_TEST")

    @staticmethod
    def get_shell() -> str:
        """
        Get the current shell path.
        
        Returns:
            Shell path (defaults to empty string)
        """
        return os.environ.get("SHELL", "")

    @staticmethod
    def get_aixterm_log_file() -> Optional[str]:
        """
        Get the active AIxTerm log file path.
        
        Returns:
            Log file path if set, None otherwise
        """
        return os.environ.get("_AIXTERM_LOG_FILE")

    @staticmethod
    def set_log_level(level: str) -> None:
        """
        Set the logging level for AIxTerm.
        
        Args:
            level: Log level to set
        """
        os.environ["AIXTERM_LOG_LEVEL"] = level


# Convenience functions for direct import
def get_log_level() -> str:
    """Get the logging level for AIxTerm."""
    return EnvironmentVariables.get_log_level()


def get_runtime_home() -> Optional[str]:
    """Get the runtime home directory override."""
    return EnvironmentVariables.get_runtime_home()


def get_show_timing() -> bool:
    """Get whether to show timing information."""
    return EnvironmentVariables.get_show_timing()


def get_test_idle_grace() -> float:
    """Get the idle grace period for tests."""
    return EnvironmentVariables.get_test_idle_grace()


def get_test_idle_limit() -> float:
    """Get the idle limit for tests."""
    return EnvironmentVariables.get_test_idle_limit()


def get_pytest_current_test() -> Optional[str]:
    """Get the current pytest test name."""
    return EnvironmentVariables.get_pytest_current_test()


def get_shell() -> str:
    """Get the current shell path."""
    return EnvironmentVariables.get_shell()


def get_aixterm_log_file() -> Optional[str]:
    """Get the active AIxTerm log file path."""
    return EnvironmentVariables.get_aixterm_log_file()


def set_log_level(level: str) -> None:
    """Set the logging level for AIxTerm."""
    EnvironmentVariables.set_log_level(level)