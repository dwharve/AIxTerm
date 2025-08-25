"""Configuration management for AIxTerm.

Unified Unix domain socket architecture only; legacy HTTP code paths have
been removed per project rules forbidding retention of dead code.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import get_logger


class AIxTermConfig:
    """Manages AIxTerm configuration with validation and MCP server support.

    Runtime configuration lives at the fixed home directory path
    '~/.aixterm/config'.
    """

    # Legacy default (home) retained only for migration; not used when None passed
    LEGACY_HOME_PATH = Path.home() / ".aixterm"

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_path: Custom path to configuration file
        """
        from .runtime_paths import ensure_runtime_layout, get_config_file

        if config_path:
            if config_path.is_dir():
                self.config_path = config_path / "config"
            else:
                self.config_path = config_path
        else:
            # Home directory default (~/.aixterm/config)
            ensure_runtime_layout()
            self.config_path = get_config_file()
        self.logger = get_logger(__name__)
        self._timing_initialized: bool = False
        self._config = self._load_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration.

        Only currently supported keys are provided here; any extraneous keys
        present in an on-disk config will be stripped during validation.
        """
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
                "in your responses. If web sources are used, cite them properly. "
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
            "context_size": 4096,
            "response_buffer_size": 1024,
            "mcp_servers": [
                {
                    "name": "pythonium",
                    "command": "python -m pythonium",
                    "args": ["serve"],
                    "env": {},
                    "description": "Python code execution and analysis MCP server",
                }
            ],
            "cleanup": {
                "enabled": True,
                "max_log_age_days": 30,
                "max_log_files": 10,
                "cleanup_interval_hours": 24,
            },
            "tool_management": {
                "reserve_tokens_for_tools": 1024,
                "max_tool_iterations": 5,
                "response_timing": {
                    "average_response_time": 10.0,
                    "max_progress_time": 30.0,
                    "progress_update_interval": 0.5,
                },
                "tool_priorities": {
                    "execute_command": 1000,
                    "search_tools": 950,
                    "describe_tool": 900,
                    "read_file": 850,
                    "write_file": 840,
                    "find_files": 820,
                    "search_files": 810,
                    "delete_file": 800,
                    "web_search": 650,
                    "http_client": 600,
                },
            },
        }

    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize configuration dictionary.

        Missing keys are populated with defaults, invalid values corrected, and
        any extraneous top-level keys removed for a clean, forward-only config.
        """
        defaults = self._get_default_config()

        # Ensure required keys exist
        for key, value in defaults.items():
            if key not in config:
                config[key] = value

        # context_size
        try:
            config["context_size"] = max(
                1000,
                min(32000, int(config.get("context_size", defaults["context_size"]))),
            )
        except (ValueError, TypeError):
            config["context_size"] = defaults["context_size"]

        # response_buffer_size
        try:
            config["response_buffer_size"] = max(
                100,
                min(
                    4000,
                    int(config.get("response_buffer_size", defaults["response_buffer_size"])),
                ),
            )
        except (ValueError, TypeError):
            config["response_buffer_size"] = defaults["response_buffer_size"]

        if config["response_buffer_size"] >= config["context_size"]:
            config["response_buffer_size"] = min(1024, config["context_size"] // 2)

        # api_url
        if not isinstance(config.get("api_url"), str) or not config.get("api_url"):
            config["api_url"] = defaults["api_url"]

        # mcp_servers
        if not isinstance(config.get("mcp_servers"), list):
            config["mcp_servers"] = []
        validated_servers: List[Dict[str, Any]] = []
        for server in config["mcp_servers"]:
            if (
                isinstance(server, dict)
                and server.get("name", "").strip()
                and server.get("command")
            ):
                validated_servers.append(self._validate_mcp_server(server))
        config["mcp_servers"] = validated_servers

        # cleanup
        if not isinstance(config.get("cleanup"), dict):
            config["cleanup"] = defaults["cleanup"]
        else:
            cleanup = {
                k: v for k, v in config["cleanup"].items() if k in defaults["cleanup"]
            }
            for k, v in defaults["cleanup"].items():
                cleanup.setdefault(k, v)
            # normalize types
            if isinstance(cleanup.get("enabled"), str):
                cleanup["enabled"] = cleanup["enabled"].lower() in {"true", "yes", "1"}
            for num_key in ("max_log_age_days", "max_log_files", "cleanup_interval_hours"):
                try:
                    cleanup[num_key] = int(cleanup[num_key])
                except (ValueError, TypeError):
                    cleanup[num_key] = defaults["cleanup"][num_key]
            config["cleanup"] = cleanup

        # tool_management
        if not isinstance(config.get("tool_management"), dict):
            config["tool_management"] = defaults["tool_management"]
        else:
            tm_defaults = defaults["tool_management"]
            tm = {
                k: v for k, v in config["tool_management"].items() if k in tm_defaults
            }
            for k, v in tm_defaults.items():
                tm.setdefault(k, v)
            # reserve_tokens_for_tools
            try:
                tm["reserve_tokens_for_tools"] = max(
                    500,
                    min(
                        8000,
                        int(
                            tm.get(
                                "reserve_tokens_for_tools",
                                tm_defaults["reserve_tokens_for_tools"],
                            )
                        ),
                    ),
                )
            except (ValueError, TypeError):
                tm["reserve_tokens_for_tools"] = tm_defaults["reserve_tokens_for_tools"]
            # max_tool_iterations
            try:
                tm["max_tool_iterations"] = max(
                    1,
                    min(
                        20,
                        int(
                            tm.get(
                                "max_tool_iterations", tm_defaults["max_tool_iterations"]
                            )
                        ),
                    ),
                )
            except (ValueError, TypeError):
                tm["max_tool_iterations"] = tm_defaults["max_tool_iterations"]
            # response_timing
            if not isinstance(tm.get("response_timing"), dict):
                tm["response_timing"] = tm_defaults["response_timing"]
            else:
                rt_defaults = tm_defaults["response_timing"]
                rt = {
                    k: v for k, v in tm["response_timing"].items() if k in rt_defaults
                }
                for k, v in rt_defaults.items():
                    rt.setdefault(k, v)
                try:
                    rt["average_response_time"] = max(
                        1.0,
                        min(
                            120.0,
                            float(
                                rt.get(
                                    "average_response_time",
                                    rt_defaults["average_response_time"],
                                )
                            ),
                        ),
                    )
                except (ValueError, TypeError):
                    rt["average_response_time"] = rt_defaults["average_response_time"]
                try:
                    rt["max_progress_time"] = max(
                        5.0,
                        min(
                            300.0,
                            float(
                                rt.get(
                                    "max_progress_time", rt_defaults["max_progress_time"]
                                )
                            ),
                        ),
                    )
                except (ValueError, TypeError):
                    rt["max_progress_time"] = rt_defaults["max_progress_time"]
                try:
                    rt["progress_update_interval"] = max(
                        0.1,
                        min(
                            5.0,
                            float(
                                rt.get(
                                    "progress_update_interval",
                                    rt_defaults["progress_update_interval"],
                                )
                            ),
                        ),
                    )
                except (ValueError, TypeError):
                    rt["progress_update_interval"] = rt_defaults["progress_update_interval"]
                tm["response_timing"] = rt
            # tool_priorities
            if not isinstance(tm.get("tool_priorities"), dict):
                tm["tool_priorities"] = tm_defaults["tool_priorities"]
            else:
                priorities: Dict[str, int] = {}
                for tool_name, priority in tm["tool_priorities"].items():
                    try:
                        priorities[tool_name] = int(priority)
                    except (ValueError, TypeError):
                        self.logger.debug(
                            f"Invalid priority for tool '{tool_name}': {priority} (discarded)"
                        )
                tm["tool_priorities"] = priorities
            config["tool_management"] = tm

        # Remove extraneous top-level keys
        allowed = set(defaults.keys())
        for k in list(config.keys()):
            if k not in allowed:
                config.pop(k, None)

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

        If config file doesn't exist, automatically create it with defaults.

        Returns:
            Configuration dictionary
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                return self._validate_config(config)
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(
                    f"Error loading config file: {e}. Using defaults."
                )
                return self._get_default_config()
        else:
            # Config file doesn't exist, create it with defaults
            config = self._get_default_config()
            try:
                # Ensure parent directory exists
                self.config_path.parent.mkdir(parents=True, exist_ok=True)

                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                self.logger.info(
                    f"Created default configuration file at {self.config_path}"
                )
            except IOError as e:
                self.logger.warning(f"Could not create config file: {e}")

            return config

    def save_config(self) -> None:
        """Save current configuration to file."""
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
        except IOError as e:
            self.logger.error(f"Error saving config file: {e}")

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

    # Legacy network accessor methods removed.

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
                    "Initializing adaptive timing with first measurement: "
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

    def get_openai_key(self) -> str:
        """Get OpenAI API key from config.

        Returns:
            API key or dummy key if not configured
        """
        api_key = str(self.get("api_key", ""))
        if not api_key:
            api_key = "dummy_key"
        return api_key

    def get_openai_base_url(self) -> Optional[str]:
        """Get OpenAI base URL from config.

        Returns:
            Base URL for non-OpenAI endpoints or None for default OpenAI
        """
        api_url = str(self.get("api_url", ""))
        if api_url and "openai.com" not in api_url.lower():
            return api_url
        return None
