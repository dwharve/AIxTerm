"""Configuration management for AIxTerm."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class AIxTermConfig:
    """Manages AIxTerm configuration with validation and MCP server support."""

    DEFAULT_CONFIG_PATH = Path.home() / ".aixterm"

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_path: Custom path to configuration file
        """
        if config_path:
            self.config_path: Path = config_path
        else:
            self.config_path = self.DEFAULT_CONFIG_PATH
        self._config = self._load_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "model": "local-model",
            "system_prompt": (
                "You are a terminal AI assistant that can utilize tool calls to "
                "collaborate with and assist the user in achieving their stated "
                "goals. Responses should be short and concise. If the user asks a "
                "question, attempt to answer it directly. If the user asks you to "
                "perform a task, use tool calls to execute commands and perform "
                "actions. The context that is given is used to inform your "
                "responses, but you should not repeat it verbatim or discuss it "
                "unless specifically asked or relevant."
            ),
            "planning_system_prompt": (
                "You are a strategic planning AI assistant. When given a task or "
                "problem, break it down into clear, actionable steps. Create "
                "detailed plans that consider dependencies, potential issues, and "
                "alternative approaches. Use tool calls to execute commands and "
                "perform actions. Always think through the complete workflow "
                "before starting and explain your reasoning. Provide step-by-step "
                "guidance and check for understanding before proceeding."
            ),
            "api_url": "http://localhost/v1/chat/completions",
            "api_key": "",
            "context_size": 4000,  # Total context window size available
            "response_buffer_size": 1000,  # Space reserved for LLM response
            "mcp_servers": [],
            "cleanup": {
                "enabled": True,
                "max_log_age_days": 30,
                "max_log_files": 10,
                "cleanup_interval_hours": 24,
            },
            "tool_management": {
                "reserve_tokens_for_tools": 2000,  # Reserve tokens for tool definitions
            },
            "server_mode": {
                "enabled": False,  # Run as server instead of exiting immediately
                "host": "localhost",  # Server host address
                "port": 8081,  # Server port number
                "transport": "http",  # Transport protocol (http, websocket)
                "keep_alive": True,  # Keep server running after requests
            },
            "logging": {
                "level": "INFO",
                "file": None,
            },  # None means no file logging
        }

    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix configuration values.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary
        """
        defaults = self._get_default_config()

        # Ensure required keys exist
        for key in defaults:
            if key not in config:
                config[key] = defaults[key]

        # Validate specific values

        # Validate context_size
        try:
            config["context_size"] = max(
                1000, min(32000, int(config.get("context_size", 4000)))
            )
        except (ValueError, TypeError):
            config["context_size"] = defaults.get("context_size", 4000)

        # Validate response_buffer_size
        try:
            config["response_buffer_size"] = max(
                100, min(4000, int(config.get("response_buffer_size", 1000)))
            )
        except (ValueError, TypeError):
            config["response_buffer_size"] = defaults.get("response_buffer_size", 1000)

        # Ensure response buffer doesn't exceed total context size
        if config["response_buffer_size"] >= config["context_size"]:
            config["response_buffer_size"] = min(1000, config["context_size"] // 2)

        # Validate api_url - convert to string if not string
        if not isinstance(config.get("api_url"), str) or not config.get("api_url"):
            config["api_url"] = defaults["api_url"]

        # Validate MCP servers configuration
        if not isinstance(config.get("mcp_servers"), list):
            config["mcp_servers"] = []

        # Validate each MCP server configuration
        validated_servers = []
        for server in config["mcp_servers"]:
            if isinstance(server, dict) and "name" in server and "command" in server:
                # Only include servers with valid non-empty names
                if server.get("name", "").strip():
                    validated_servers.append(self._validate_mcp_server(server))
        config["mcp_servers"] = validated_servers

        # Validate cleanup configuration
        if not isinstance(config.get("cleanup"), dict):
            config["cleanup"] = defaults["cleanup"]
        else:
            cleanup = config["cleanup"]

            # Keep only valid keys
            valid_keys = {
                "enabled",
                "max_log_age_days",
                "max_log_files",
                "cleanup_interval_hours",
            }
            cleanup = {k: v for k, v in cleanup.items() if k in valid_keys}

            # Set defaults for missing keys
            cleanup.setdefault("enabled", True)
            cleanup.setdefault("max_log_age_days", 30)
            cleanup.setdefault("max_log_files", 10)
            cleanup.setdefault("cleanup_interval_hours", 24)

            # Convert string booleans to actual booleans
            if isinstance(cleanup.get("enabled"), str):
                cleanup["enabled"] = cleanup["enabled"].lower() in (
                    "true",
                    "yes",
                    "1",
                )

            # Convert string numbers to integers
            for key in [
                "max_log_age_days",
                "max_log_files",
                "cleanup_interval_hours",
            ]:
                try:
                    cleanup[key] = int(cleanup[key])
                except (ValueError, TypeError):
                    cleanup[key] = defaults["cleanup"][key]

            config["cleanup"] = cleanup

        # Validate tool management configuration
        if not isinstance(config.get("tool_management"), dict):
            config["tool_management"] = defaults["tool_management"]
        else:
            tool_mgmt = config["tool_management"]
            defaults_tool_mgmt = defaults["tool_management"]

            # Validate reserve_tokens_for_tools
            try:
                tool_mgmt["reserve_tokens_for_tools"] = max(
                    500,
                    min(
                        8000,
                        int(tool_mgmt.get("reserve_tokens_for_tools", 2000)),
                    ),
                )
            except (ValueError, TypeError):
                tool_mgmt["reserve_tokens_for_tools"] = defaults_tool_mgmt[
                    "reserve_tokens_for_tools"
                ]

        # Validate server mode configuration
        if not isinstance(config.get("server_mode"), dict):
            config["server_mode"] = defaults["server_mode"]
        else:
            server_mode = config["server_mode"]
            defaults_server_mode = defaults["server_mode"]

            # Validate enabled
            if not isinstance(server_mode.get("enabled"), bool):
                server_mode["enabled"] = defaults_server_mode["enabled"]

            # Validate host
            if not isinstance(server_mode.get("host"), str):
                server_mode["host"] = defaults_server_mode["host"]

            # Validate port
            try:
                server_mode["port"] = max(
                    1, min(65535, int(server_mode.get("port", 8081)))
                )
            except (ValueError, TypeError):
                server_mode["port"] = defaults_server_mode["port"]

            # Validate transport
            if server_mode.get("transport") not in ["http", "websocket"]:
                server_mode["transport"] = defaults_server_mode["transport"]

            # Validate keep_alive
            if not isinstance(server_mode.get("keep_alive"), bool):
                server_mode["keep_alive"] = defaults_server_mode["keep_alive"]

        return config

    def _validate_mcp_server(self, server: Dict[str, Any]) -> Dict[str, Any]:
        """Validate MCP server configuration.

        Args:
            server: MCP server configuration

        Returns:
            Validated MCP server configuration
        """
        validated = {
            "name": str(server.get("name", "")),
            "command": server.get("command", []),
            "args": server.get("args", []),
            "env": server.get("env", {}),
            "enabled": server.get("enabled", True),
            "timeout": max(5, min(300, int(server.get("timeout", 30)))),
            "auto_start": server.get("auto_start", True),
        }

        # Ensure command is a list
        if isinstance(validated["command"], str):
            validated["command"] = [validated["command"]]

        # Convert string booleans to actual booleans
        if isinstance(validated.get("enabled"), str):
            validated["enabled"] = validated["enabled"].lower() in (
                "true",
                "yes",
                "1",
            )

        return validated

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or return defaults.

        Returns:
            Configuration dictionary
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                return self._validate_config(config)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Error loading config file: {e}. Using defaults.")
                return self._get_default_config()
        else:
            return self._get_default_config()

    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            print(f"Error saving config file: {e}")

    def save(self) -> bool:
        """Save current configuration to file.

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            self.save_config()
            return True
        except Exception:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key (supports dot notation like 'cleanup.enabled')
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split(".")
        value = self._config

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key (supports dot notation)
            value: Value to set
        """
        keys = key.split(".")
        config = self._config

        # Navigate to parent
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        # Set value
        config[keys[-1]] = value

    def get_mcp_servers(self) -> List[Dict[str, Any]]:
        """Get list of enabled MCP servers.

        Returns:
            List of MCP server configurations
        """
        return [
            server
            for server in self._config.get("mcp_servers", [])
            if server.get("enabled", True)
        ]

    def add_mcp_server(self, name: str, command: List[str], **kwargs: Any) -> None:
        """Add MCP server to configuration.

        Args:
            name: Server name
            command: Command to start server
            **kwargs: Additional server configuration
        """
        server_config = {"name": name, "command": command, **kwargs}

        validated_server = self._validate_mcp_server(server_config)

        # Remove existing server with same name
        servers = self._config.get("mcp_servers", [])
        servers = [s for s in servers if s.get("name") != name]
        servers.append(validated_server)

        self._config["mcp_servers"] = servers

    def remove_mcp_server(self, name: str) -> bool:
        """Remove MCP server from configuration.

        Args:
            name: Server name to remove

        Returns:
            True if server was removed, False if not found
        """
        servers = self._config.get("mcp_servers", [])
        original_count = len(servers)

        self._config["mcp_servers"] = [s for s in servers if s.get("name") != name]

        return len(self._config["mcp_servers"]) < original_count

    def get_tool_management_config(self) -> Dict[str, Any]:
        """Get tool management configuration.

        Returns:
            Tool management configuration dictionary
        """
        tool_config: Dict[str, Any] = self._config.get("tool_management", {})
        return tool_config

    def get_tool_tokens_reserve(self) -> int:
        """Get number of tokens to reserve for tool definitions.

        Returns:
            Number of tokens to reserve for tools
        """
        reserve_tokens: int = self.get_tool_management_config().get(
            "reserve_tokens_for_tools", 2000
        )
        return reserve_tokens

    def get_server_mode_config(self) -> Dict[str, Any]:
        """Get server mode configuration.

        Returns:
            Server mode configuration dictionary
        """
        server_config: Dict[str, Any] = self._config.get("server_mode", {})
        return server_config

    def is_server_mode_enabled(self) -> bool:
        """Check if server mode is enabled.

        Returns:
            True if server mode is enabled
        """
        enabled: bool = self.get_server_mode_config().get("enabled", False)
        return enabled

    def get_server_host(self) -> str:
        """Get server host address.

        Returns:
            Server host address
        """
        host: str = self.get_server_mode_config().get("host", "localhost")
        return host

    def get_server_port(self) -> int:
        """Get server port number.

        Returns:
            Server port number
        """
        port: int = self.get_server_mode_config().get("port", 8081)
        return port

    def get_server_transport(self) -> str:
        """Get server transport protocol.

        Returns:
            Server transport protocol
        """
        transport: str = self.get_server_mode_config().get("transport", "http")
        return transport

    def is_server_keep_alive_enabled(self) -> bool:
        """Check if server keep alive is enabled.

        Returns:
            True if server should keep running after requests
        """
        keep_alive: bool = self.get_server_mode_config().get("keep_alive", True)
        return keep_alive

    def create_default_config(self, overwrite: bool = False) -> bool:
        """Create a default configuration file.

        Args:
            overwrite: Whether to overwrite existing config file

        Returns:
            True if config was created, False if file exists and overwrite=False
        """
        if self.config_path.exists() and not overwrite:
            return False

        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create default config with comments
        default_config = self._get_default_config()

        # Write the config file with comments for better user experience
        config_content = {
            "_comment": (
                "AIxTerm Configuration File - Edit this file to customize "
                "your AI assistant"
            ),
            "model": default_config["model"],
            "system_prompt": default_config["system_prompt"],
            "api_url": default_config["api_url"],
            "api_key": default_config["api_key"],
            "context_size": default_config["context_size"],
            "response_buffer_size": default_config["response_buffer_size"],
            "mcp_servers": default_config["mcp_servers"],
            "cleanup": default_config["cleanup"],
            "logging": default_config["logging"],
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_content, f, indent=2, ensure_ascii=False)

        # Reload the config
        self._config = self._load_config()

        return True

    @property
    def config(self) -> Dict[str, Any]:
        """Get full configuration dictionary."""
        return self._config.copy()

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access."""
        return self.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style setting."""
        self.set(key, value)

    def get_total_context_size(self) -> int:
        """Get the total context window size.

        This is the complete context window available for the LLM, including
        both input context and response space.

        Returns:
            Total context size in tokens
        """
        return int(self.get("context_size", 4000))

    def get_response_buffer_size(self) -> int:
        """Get the response buffer size.

        This is the amount of space reserved for the LLM's response within
        the total context window. The actual available context for input is
        total_context_size - response_buffer_size.

        Returns:
            Response buffer size in tokens
        """
        return int(self.get("response_buffer_size", 1000))

    def get_available_context_size(self) -> int:
        """Get the available context size for input after reserving response buffer.

        This is the maximum amount of context that can be used for system prompts,
        user queries, file contents, terminal history, and tool results before
        the LLM generates its response.

        Returns:
            Available context size in tokens
        """
        return self.get_total_context_size() - self.get_response_buffer_size()
