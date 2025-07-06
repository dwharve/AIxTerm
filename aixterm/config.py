"""Configuration management for AIxTerm."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import get_logger


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
        self.logger = get_logger(__name__)
        self._timing_initialized: bool = False
        self._config = self._load_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "model": "local-model",
            "system_prompt": (
                "You are a terminal-based AI assistant. Respond to user input "
                "with short, concise answers. Do not repeat the user's instructions "
                "or restate the context unless specifically asked or contextually "
                "necessary. Prioritize tool use for efficiency. When information "
                "is required that may be inaccurate or unknown, search the web "
                "rather than guessing. Use available tools when they are "
                "appropriate to the user's request. Only include relevant output "
                "in your responses. If web sources are used, cite them properly."
                "Citations should be located at the end of the response and in the "
                "format:\n1. <title>\n<url>\n<snippet>\n\n2. ..."
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
            "context_size": 4096,  # Total context window size available
            "response_buffer_size": 1024,  # Space reserved for LLM response
            "mcp_servers": [],
            "cleanup": {
                "enabled": True,
                "max_log_age_days": 30,
                "max_log_files": 10,
                "cleanup_interval_hours": 24,
            },
            "tool_management": {
                "reserve_tokens_for_tools": 1024,  # Reserve tokens for tool definitions
                "max_tool_iterations": 5,  # Max iterations for tool execution loops
                "response_timing": {
                    "average_response_time": 10.0,  # Average API response time
                    "max_progress_time": 30.0,  # Max time to show progress before hung
                    "progress_update_interval": 0.5,  # Progress update freq in seconds
                },
                "tool_priorities": {
                    # Essential execution tools (priority: 1000+)
                    "execute_command": 1000,
                    # Tool introspection and discovery (priority: 900+)
                    "search_tools": 950,
                    "describe_tool": 900,
                    # File operations (priority: 800+)
                    "read_file": 850,
                    "write_file": 840,
                    "find_files": 820,
                    "search_files": 810,
                    "delete_file": 800,
                    # Web and network tools (priority: 600+)
                    "web_search": 650,
                    "http_client": 600,
                },
            },
            "server_mode": {
                "enabled": False,  # Run as server instead of exiting immediately
                "host": "localhost",  # Server host address
                "port": 8081,  # Server port number
                "transport": "http",  # Transport protocol (http, websocket)
                "keep_alive": True,  # Keep server running after requests
            },
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
                1000,
                min(32000, int(config.get("context_size", defaults["context_size"]))),
            )
        except (ValueError, TypeError):
            config["context_size"] = defaults["context_size"]

        # Validate response_buffer_size
        try:
            config["response_buffer_size"] = max(
                100,
                min(
                    4000,
                    int(
                        config.get(
                            "response_buffer_size", defaults["response_buffer_size"]
                        )
                    ),
                ),
            )
        except (ValueError, TypeError):
            config["response_buffer_size"] = defaults["response_buffer_size"]

        # Ensure response buffer doesn't exceed total context size
        if config["response_buffer_size"] >= config["context_size"]:
            config["response_buffer_size"] = min(1024, config["context_size"] // 2)

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

            # Validate max_tool_iterations
            try:
                tool_mgmt["max_tool_iterations"] = max(
                    1,
                    min(
                        20,
                        int(tool_mgmt.get("max_tool_iterations", 5)),
                    ),
                )
            except (ValueError, TypeError):
                tool_mgmt["max_tool_iterations"] = defaults_tool_mgmt[
                    "max_tool_iterations"
                ]

            # Validate response_timing
            if not isinstance(tool_mgmt.get("response_timing"), dict):
                tool_mgmt["response_timing"] = defaults_tool_mgmt["response_timing"]
            else:
                timing = tool_mgmt["response_timing"]
                defaults_timing = defaults_tool_mgmt["response_timing"]

                # Validate average_response_time
                try:
                    timing["average_response_time"] = max(
                        1.0,
                        min(120.0, float(timing.get("average_response_time", 10.0))),
                    )
                except (ValueError, TypeError):
                    timing["average_response_time"] = defaults_timing[
                        "average_response_time"
                    ]

                # Validate max_progress_time
                try:
                    timing["max_progress_time"] = max(
                        5.0, min(300.0, float(timing.get("max_progress_time", 30.0)))
                    )
                except (ValueError, TypeError):
                    timing["max_progress_time"] = defaults_timing["max_progress_time"]

                # Validate progress_update_interval
                try:
                    timing["progress_update_interval"] = max(
                        0.1,
                        min(5.0, float(timing.get("progress_update_interval", 0.5))),
                    )
                except (ValueError, TypeError):
                    timing["progress_update_interval"] = defaults_timing[
                        "progress_update_interval"
                    ]

            # Validate tool_priorities
            if not isinstance(tool_mgmt.get("tool_priorities"), dict):
                tool_mgmt["tool_priorities"] = defaults_tool_mgmt["tool_priorities"]
            else:
                # Validate each priority value is an integer
                priorities = tool_mgmt["tool_priorities"]
                validated_priorities = {}
                for tool_name, priority in priorities.items():
                    try:
                        validated_priorities[tool_name] = int(priority)
                    except (ValueError, TypeError):
                        print(
                            f"Warning: Invalid priority for tool '{tool_name}': "
                            f"{priority}. Using default priority."
                        )
                        # Don't include invalid priorities
                tool_mgmt["tool_priorities"] = validated_priorities

            config["tool_management"] = tool_mgmt

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
            "model": default_config["model"],
            "system_prompt": default_config["system_prompt"],
            "api_url": default_config["api_url"],
            "api_key": default_config["api_key"],
            "context_size": default_config["context_size"],
            "response_buffer_size": default_config["response_buffer_size"],
            "mcp_servers": default_config["mcp_servers"],
            "cleanup": default_config["cleanup"],
            "tool_management": default_config["tool_management"],
            "server_mode": default_config["server_mode"],
        }

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config_content, f, indent=2, ensure_ascii=False)

        # Reload the config
        self._config = self._load_config()

        return True

    def update_response_timing(self, actual_response_time: float) -> None:
        """Update running average of response times for adaptive progress.

        Args:
            actual_response_time: Actual time taken for the AI response in seconds
        """
        try:
            timing_config = self.get("tool_management.response_timing", {})
            current_avg = timing_config.get("average_response_time", 10.0)

            # Clamp input to reasonable bounds first (0.5-120 seconds)
            clamped_time = max(0.5, min(120.0, actual_response_time))

            # Check if this is the first update (current_avg is still initial config)
            # If so, use the actual time as starting point instead of averaging
            if not hasattr(self, "_timing_initialized") or not self._timing_initialized:
                # First update - use actual time as baseline
                new_avg = clamped_time
                self._timing_initialized = True
                self.logger.debug(
                    f"Initializing adaptive timing with first measurement: "
                    f"{new_avg:.2f}s"
                )
            else:
                # Subsequent updates - use exponential moving average with alpha=0.3
                alpha = 0.3
                new_avg = alpha * clamped_time + (1 - alpha) * current_avg
                self.logger.debug(
                    f"Updated average response time: {current_avg:.2f}s -> "
                    f"{new_avg:.2f}s (actual: {actual_response_time:.2f}s)"
                )

            # Clamp result to reasonable bounds for progress display (1-60 seconds)
            new_avg = max(1.0, min(60.0, new_avg))

            # Update the config
            self.set("tool_management.response_timing.average_response_time", new_avg)

        except Exception as e:
            self.logger.debug(f"Error updating response timing: {e}")

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
        return int(self.get("context_size", 4096))

    def get_response_buffer_size(self) -> int:
        """Get the response buffer size.

        This is the amount of space reserved for the LLM's response within
        the total context window. The actual available context for input is
        total_context_size - response_buffer_size.

        Returns:
            Response buffer size in tokens
        """
        return int(self.get("response_buffer_size", 1024))

    def get_available_context_size(self) -> int:
        """Get the available context size for input after reserving response buffer.

        This is the maximum amount of context that can be used for system prompts,
        user queries, file contents, terminal history, and tool results before
        the LLM generates its response.

        Returns:
            Available context size in tokens
        """
        return self.get_total_context_size() - self.get_response_buffer_size()
