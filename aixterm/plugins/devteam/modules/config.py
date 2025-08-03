"""
Configuration management for the DevTeam plugin.

This module handles configuration loading, validation, and access for the DevTeam plugin.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from .types import AgentRole

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration for the DevTeam plugin."""

    def __init__(self, user_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the configuration manager.

        Args:
            user_config: Optional user-provided configuration to override defaults.
        """
        self._config = self._get_default_config()

        # Update with user config if provided
        if user_config:
            self.update_config(user_config)

    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get the default configuration.

        Returns:
            Default configuration dictionary.
        """
        return {
            "max_concurrent_tasks": 5,
            "default_timeout_hours": 24,
            "agent_timeout_minutes": 30,
            "data_directory": str(Path.home() / ".aixterm" / "plugins" / "devteam"),
            "metrics_filename": "prompt_metrics.json",
            "agents": {
                AgentRole.PROJECT_MANAGER.value: {"enabled": True, "max_tasks": 10},
                AgentRole.ARCHITECT.value: {"enabled": True, "max_tasks": 3},
                AgentRole.DEVELOPER.value: {
                    "enabled": True,
                    "instances": 2,
                    "max_tasks": 5,
                },
                AgentRole.REVIEWER.value: {"enabled": True, "max_tasks": 8},
                AgentRole.QA.value: {"enabled": True, "max_tasks": 5},
                AgentRole.DOCUMENTATION.value: {"enabled": True, "max_tasks": 3},
            },
            "workflow": {
                "require_architecture_review": True,
                "require_code_review": True,
                "require_testing": True,
                "require_documentation": True,
                "parallel_development": True,
            },
            "adaptive_learning": {
                "enabled": True,
                "save_interval_seconds": 3600,
                "min_samples_for_optimization": 10,
                "max_experiments_per_day": 5,
            },
            "logging": {
                "level": "INFO",
                "file_logging": False,
                "log_directory": "",
            },
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key (nested keys can use dots, e.g., 'agents.developer.max_tasks')
            default: Default value to return if key not found

        Returns:
            Configuration value or default if not found.
        """
        if "." in key:
            # Handle nested keys
            parts = key.split(".")
            current = self._config

            for part in parts:
                if isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    return default

            return current

        return self._config.get(key, default)

    def get_state_directory(self) -> Path:
        """
        Get the state directory for the plugin.

        Returns:
            Path to the state directory.
        """
        state_dir = Path(self.get("data_directory")) / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir

    def update_config(self, config_updates: Dict[str, Any]) -> None:
        """
        Update configuration with new values.

        Args:
            config_updates: Dictionary with configuration updates
        """
        self._deep_update(self._config, config_updates)
        logger.debug("Configuration updated")

    def _deep_update(self, target: Dict[str, Any], updates: Dict[str, Any]) -> None:
        """
        Deep update a nested dictionary.

        Args:
            target: Target dictionary to update
            updates: Updates to apply
        """
        for key, value in updates.items():
            if (
                key in target
                and isinstance(target[key], dict)
                and isinstance(value, dict)
            ):
                self._deep_update(target[key], value)
            else:
                target[key] = value

    def validate(self) -> bool:
        """
        Validate the configuration for consistency and required values.

        Returns:
            True if configuration is valid, False otherwise.
        """
        try:
            # Check required sections
            required_sections = ["agents", "workflow", "adaptive_learning"]
            for section in required_sections:
                if section not in self._config:
                    logger.error(f"Missing required configuration section: {section}")
                    return False

            # Check agent configuration
            for agent_role in AgentRole:
                role_value = agent_role.value
                if role_value not in self._config["agents"]:
                    logger.warning(
                        f"Missing configuration for agent role: {role_value}"
                    )
                    # Add default configuration for this role
                    self._config["agents"][role_value] = {
                        "enabled": True,
                        "max_tasks": 5,
                    }

            # Ensure data directory exists
            data_dir = Path(self._config["data_directory"])
            if not data_dir.exists():
                os.makedirs(data_dir, exist_ok=True)
                logger.debug(f"Created data directory: {data_dir}")

            return True

        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

    def save_to_file(self, file_path: Optional[str] = None) -> bool:
        """
        Save the current configuration to a file.

        Args:
            file_path: Path to save the configuration file. If not provided,
                       uses the data directory from config.

        Returns:
            True if saved successfully, False otherwise.
        """
        try:
            if not file_path:
                data_dir = Path(self._config["data_directory"])
                file_path = str(data_dir / "config.json")

            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # Save configuration
            with open(file_path, "w") as f:
                json.dump(self._config, f, indent=2)

            logger.debug(f"Configuration saved to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            return False

    def load_from_file(self, file_path: str) -> bool:
        """
        Load configuration from a file.

        Args:
            file_path: Path to the configuration file

        Returns:
            True if loaded successfully, False otherwise.
        """
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Configuration file not found: {file_path}")
                return False

            with open(file_path, "r") as f:
                config_data = json.load(f)

            # Update configuration
            self.update_config(config_data)
            logger.debug(f"Configuration loaded from {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            return False
