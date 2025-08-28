"""Backward-compatible alias test for MCP persistence.

Historically validated MCP server uptime persistence. The core lifecycle
behavior is now covered by ``test_service_autostarts_and_persists``. This file
retains the old test name to avoid breaking downstream references. Remove once
external consumers migrate.
"""

from .test_service_autostart_persistence import (  # noqa: F401
	test_service_autostarts_and_persists as test_service_mcp_persistence,
)










