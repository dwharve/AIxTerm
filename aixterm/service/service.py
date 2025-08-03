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

from ..config import AIxTermConfig

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

            mcp_client = MCPClient(self.config)
            self.llm_client = LLMClient(self.config, mcp_client)

            # Start components
            logger.debug("LLM client initialized")

            logger.debug("Loading plugins")
            await self.plugin_manager.load_plugins()

            logger.debug("Starting server")
            await self.server.start()

            logger.info(f"AIxTerm service started successfully (ID: {self.service_id})")

            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()

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

            logger.info("AIxTerm service stopped successfully")

        except Exception as e:
            logger.error(f"Error during service shutdown: {e}")
            raise

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
        # TODO: Get this from package metadata
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
