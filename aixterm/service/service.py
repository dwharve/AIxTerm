"""
AIxTerm Service Implementation

This module provides the core service implementation for AIxTerm, enabling
it to run as a background daemon/service that clients can connect to.
"""

import asyncio
import datetime
import logging
import platform
import signal
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
import os

from ..config import AIxTermConfig
from ..config_env.env_vars import get_pytest_current_test, get_test_idle_grace, get_test_idle_limit

logger = logging.getLogger(__name__)


class AIxTermService:
    """
    Main AIxTerm service class.

    This class manages the lifecycle of the AIxTerm service, including:
    - Service startup and shutdown
    - Plugin management
    - Client connection handling
    - Context and state management
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the AIxTerm service.

        Args:
            config_path: Optional path to a configuration file.
        """
        # Load configuration
        self.config = AIxTermConfig(Path(config_path) if config_path else None)

        # Import types for proper type annotations
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from ..llm import LLMClient
            from .context import ContextManager
            from .plugin_manager import PluginManager
            from .server import ServiceServer

        # Initialize components (these will be initialized properly in start())
        self.plugin_manager: Optional["PluginManager"] = None
        self.server: Optional["ServiceServer"] = None
        self.context_manager: Optional["ContextManager"] = None
        self.llm_client: Optional["LLMClient"] = None
        # Persist MCP client across queries so MCP-managed servers (e.g. pythonium)
        # are not torn down after a single request like in ephemeral CLI mode.
        # Forward-declared; actual import at start() so annotation as Any to avoid name error
        self.mcp_client: Optional[Any] = None

        # Service state
        self._running: bool = False
        self._start_time: Optional[datetime.datetime] = None
        self.service_id = str(uuid.uuid4())

        # Setup logging
        self._configure_logging()

    def _configure_logging(self):
        """Configure logging based on service configuration."""
        log_config = self.config.get("logging", {})
        log_level = log_config.get("level", "INFO")
        # log_format = log_config.get("format", "structured")  # Not used currently

        # Set log level
        numeric_level = getattr(logging, log_level.upper(), None)
        if not isinstance(numeric_level, int):
            numeric_level = logging.INFO

        # Configure root logger
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        logger.debug(f"Logging configured with level {log_level}")

    async def start(self):
        """
        Start the AIxTerm service and all its components.

        This method initializes all service components and starts listening for client connections.
        """
        if self._running:
            logger.warning("Service is already running")
            return

        logger.info("Starting AIxTerm service")
        self._start_time = datetime.datetime.now()
        self._running = True

        try:
            # Initialize components
            from ..llm import LLMClient
            from .context import ContextManager
            from .plugin_manager import PluginManager
            from .server import ServiceServer

            # Create component instances
            self.plugin_manager = PluginManager(self)
            self.server = ServiceServer(self)
            self.context_manager = ContextManager(self)
            # For LLM client, we'll need MCP client too
            from ..mcp_client import MCPClient

            self.mcp_client = MCPClient(self.config)
            self.llm_client = LLMClient(self.config, self.mcp_client)

            # Initialize MCP servers immediately in service mode so they persist
            # for subsequent client requests. This avoids stdio server teardown
            # that happens when the short-lived CLI process exits.
            try:
                if self.config.get("mcp_servers", []):
                    self.mcp_client.initialize()
                    logger.debug("Initialized MCP servers at service startup")
            except Exception as e:
                logger.error(f"Failed to initialize MCP servers at startup: {e}")

            # Start components
            logger.debug("LLM client initialized")

            logger.debug("Loading plugins")
            await self.plugin_manager.load_plugins()

            logger.debug("Starting server")
            await self.server.start()
            # Reset last_activity post-start to avoid counting initialization time
            try:
                import asyncio as _asyncio
                if self.server:
                    self.server.last_activity = _asyncio.get_event_loop().time()
            except Exception:
                pass

            logger.info(f"AIxTerm service started successfully (ID: {self.service_id})")

            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()

            # In test/ephemeral environments (detected via PYTEST_CURRENT_TEST or temp runtime dir), add idle shutdown
            if get_pytest_current_test():
                asyncio.create_task(self._idle_shutdown_monitor())

        except Exception as e:
            logger.error(f"Failed to start AIxTerm service: {e}")
            self._running = False
            raise

    async def stop(self):
        """
        Stop the AIxTerm service gracefully.

        This method shuts down all service components and releases resources.
        """
        if not self._running:
            logger.warning("Service is not running")
            return

        logger.info("Stopping AIxTerm service")
        self._running = False

        try:
            # Stop components in reverse order
            if self.server:
                logger.debug("Stopping server")
                await self.server.stop()

            if self.plugin_manager:
                logger.debug("Unloading plugins")
                await self.plugin_manager.unload_plugins()

            if self.llm_client:
                logger.debug("Shutting down LLM client")
                # LLMClient has no async shutdown method

            # Ensure MCP client and any managed MCP servers are shut down cleanly
            if self.mcp_client:
                try:
                    logger.debug("Shutting down MCP client and servers")
                    self.mcp_client.shutdown()
                except Exception as e:
                    logger.debug(f"Error during MCP client shutdown: {e}")

            logger.info("AIxTerm service stopped successfully")

        except Exception as e:
            logger.error(f"Error during service shutdown: {e}")
            raise

    async def _idle_shutdown_monitor(self):
        """Background task to auto-shutdown the service after a short idle period during tests.

        This prevents orphaned processes when the pytest session finishes before
        auto-started background services exit. Only active in test mode.
        """
        try:
            # Allow override of idle window for tests via env var (bounded 0.05s..10s)
            try:
                idle_limit_env = get_test_idle_limit()
            except ValueError:
                idle_limit_env = 2.0
            idle_limit = max(0.05, min(idle_limit_env, 10.0))
            # Startup grace window to ensure the service has time to finish initialization
            # before the idle monitor can trigger. This prevents very small idle limits
            # (e.g. 0.2s) from shutting down the service before the client connects.
            try:
                grace_env = get_test_idle_grace()
            except ValueError:
                grace_env = 0.4
            grace_period = max(0.1, min(grace_env, 5.0))
            # Check interval scales with idle limit for responsiveness while avoiding busy loop
            check_interval = min(idle_limit / 2.0, 0.5)
            from .server import ServiceServer  # local import to avoid cycle at module load
            loop = asyncio.get_event_loop()
            start_time = loop.time()
            while self._running and get_pytest_current_test():
                await asyncio.sleep(check_interval)
                # If server exists and last activity is older than idle_limit, shutdown
                server = self.server
                if not server or not isinstance(server, ServiceServer):
                    continue
                last = getattr(server, "last_activity", None)
                if last is None:
                    continue
                now = loop.time()
                # Enforce startup grace period
                if (now - start_time) < grace_period:
                    continue
                if (now - last) > idle_limit:
                    logger.info("Idle shutdown monitor: no activity for %.2fs, stopping service", idle_limit)
                    await self.stop()
                    break
        except Exception as e:
            logger.debug(f"Idle shutdown monitor terminated: {e}")

    def status(self) -> Dict[str, Any]:
        """
        Get the current status of the service.

        Returns:
            A dictionary containing service status information.
        """
        status_info = {
            "service_id": self.service_id,
            "running": self._running,
            "uptime": self.get_uptime(),
            "version": self.get_version(),
            "platform": platform.system(),
            "python_version": platform.python_version(),
        }

        # Add component status if available
        if self.plugin_manager:
            status_info["plugins"] = self.plugin_manager.get_status()

        if self.server:
            status_info["server"] = self.server.get_status()

        # Add MCP server status if MCP client initialized
        if self.mcp_client:
            try:
                status_info["mcp_servers"] = self.mcp_client.get_server_status()
            except Exception as e:
                # Don't fail overall status due to MCP introspection problems
                logger.debug(f"Unable to collect MCP server status: {e}")

        return status_info

    def get_uptime(self) -> Optional[float]:
        """
        Get the service uptime in seconds.

        Returns:
            The number of seconds the service has been running, or None if not running.
        """
        if not self._running or not self._start_time:
            return None

        delta = datetime.datetime.now() - self._start_time
        return delta.total_seconds()

    @staticmethod
    def get_version() -> str:
        """
        Get the AIxTerm version.

        Returns:
            The version string.
        """
        return "0.2.0"

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        if platform.system() != "Windows":
            # SIGTERM handler
            def handle_sigterm(sig, frame):
                logger.info("Received SIGTERM signal, initiating shutdown")
                asyncio.create_task(self.stop())

            # SIGINT handler
            def handle_sigint(sig, frame):
                logger.info("Received SIGINT signal, initiating shutdown")
                asyncio.create_task(self.stop())

            signal.signal(signal.SIGTERM, handle_sigterm)
            signal.signal(signal.SIGINT, handle_sigint)
        else:
            # Windows doesn't support the same signals, but we can handle Ctrl+C
            def handle_interrupt(sig, frame):
                logger.info("Received interrupt signal, initiating shutdown")
                asyncio.create_task(self.stop())

            signal.signal(signal.SIGINT, handle_interrupt)


async def run_service(config_path: Optional[str] = None):
    """
    Run the AIxTerm service with the given configuration.

    Args:
        config_path: Optional path to a configuration file.
    """
    service = AIxTermService(config_path)

    try:
        await service.start()

        # Keep the service running
        while service._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    finally:
        await service.stop()


def main():
    """
    Main entry point for running the AIxTerm service directly.
    """
    import argparse

    parser = argparse.ArgumentParser(description="AIxTerm Service")
    parser.add_argument("--config", help="Path to configuration file")
    args = parser.parse_args()

    # Run the service
    asyncio.run(run_service(args.config))


if __name__ == "__main__":
    main()
