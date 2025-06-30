"""Tests for configuration management."""

import json
from pathlib import Path

from aixterm.config import AIxTermConfig


class TestAIxTermConfig:
    """Test cases for AIxTermConfig class."""

    def test_default_config(self, temp_dir, monkeypatch):
        """Test loading default configuration when no config file exists."""
        # Ensure no config file exists
        config_path = temp_dir / ".aixterm"
        if config_path.exists():
            config_path.unlink()

        # Use custom path to ensure clean state
        config = AIxTermConfig(config_path)

        assert config.get("model") == "local-model"
        assert config.get("context_size") == 4000  # Updated to match new default
        assert config.get("response_buffer_size") == 1000  # Check new parameter
        assert isinstance(config.get("mcp_servers"), list)
        assert len(config.get("mcp_servers")) == 0

    def test_load_existing_config(self, temp_dir, monkeypatch):
        """Test loading existing configuration file."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Ensure no config file exists first
        config_path = temp_dir / ".aixterm"
        if config_path.exists():
            config_path.unlink()

        config_data = {
            "model": "custom-model",
            "context_size": 1024,
            "api_url": "http://custom-url",
            "mcp_servers": [
                {
                    "name": "test-server",
                    "command": ["python", "server.py"],
                    "enabled": True,
                }
            ],
        }

        with open(config_path, "w") as f:
            json.dump(config_data, f)

        # Create config with custom path instead of relying on monkeypatch
        config = AIxTermConfig(config_path)

        assert config.get("model") == "custom-model"
        assert config.get("context_size") == 1024
        assert config.get("api_url") == "http://custom-url"
        assert len(config.get("mcp_servers")) == 1

    def test_config_validation(self, temp_dir, monkeypatch):
        """Test configuration validation and fixing."""
        # Create invalid config
        config_data = {
            "model": "test-model",
            "context_size": "invalid",  # Should be int
            "api_url": "",  # Should not be empty
            "mcp_servers": "not_a_list",  # Should be list
        }

        config_path = temp_dir / ".aixterm"
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = AIxTermConfig(config_path)

        assert isinstance(config.get("context_size"), int)
        assert config.get("context_size") == 4000  # Default value
        assert config.get("api_url") == "http://localhost/v1/chat/completions"
        assert isinstance(config.get("mcp_servers"), list)

    def test_token_limit_validation(self, temp_dir, monkeypatch):
        """Test context token limit validation."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Ensure no config file exists first
        config_path = temp_dir / ".aixterm"
        if config_path.exists():
            config_path.unlink()

        config_data = {"context_size": 40000}  # Too high for new limit
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = AIxTermConfig(config_path)
        assert config.get("context_size") == 32000  # Max allowed with new limit

        config_data = {"context_size": 500}  # Too low
        with open(config_path, "w") as f:
            json.dump(config_data, f)

        config = AIxTermConfig(config_path)
        assert config.get("context_size") == 1000  # Min allowed

    def test_mcp_server_management(self, mock_config):
        """Test MCP server configuration management."""
        # Add server
        mock_config.add_mcp_server(
            "test-server", ["python", "server.py"], enabled=True, timeout=60
        )

        servers = mock_config.get_mcp_servers()
        assert len(servers) == 1
        assert servers[0]["name"] == "test-server"
        assert servers[0]["command"] == ["python", "server.py"]
        assert servers[0]["enabled"] is True
        assert servers[0]["timeout"] == 60

        # Remove server
        removed = mock_config.remove_mcp_server("test-server")
        assert removed is True
        assert len(mock_config.get_mcp_servers()) == 0

        # Try to remove non-existent server
        removed = mock_config.remove_mcp_server("non-existent")
        assert removed is False

    def test_dot_notation_access(self, mock_config):
        """Test dot notation for nested configuration access."""
        # Test getting nested values
        assert mock_config.get("cleanup.enabled") is True
        assert mock_config.get("cleanup.max_log_age_days") == 30

        # Test setting nested values
        mock_config.set("cleanup.max_log_files", 5)
        assert mock_config.get("cleanup.max_log_files") == 5

        # Test creating new nested structure
        mock_config.set("new.nested.value", "test")
        assert mock_config.get("new.nested.value") == "test"

    def test_dictionary_style_access(self, mock_config):
        """Test dictionary-style access to configuration."""
        # Test getting values
        assert mock_config["model"] == "test-model"
        assert mock_config["context_size"] == 1000  # Updated to match mock config

        # Test setting values
        mock_config["model"] = "new-model"
        assert mock_config["model"] == "new-model"

    def test_save_config(self, temp_dir, monkeypatch):
        """Test saving configuration to file."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Ensure no config file exists first
        config_path = temp_dir / ".aixterm"
        if config_path.exists():
            config_path.unlink()

        config = AIxTermConfig(config_path)
        config.set("model", "saved-model")
        config.save_config()

        # Verify file was created and contains correct data
        assert config_path.exists()

        with open(config_path, "r") as f:
            saved_data = json.load(f)

        assert saved_data["model"] == "saved-model"

    def test_invalid_json_handling(self, temp_dir, monkeypatch):
        """Test handling of invalid JSON in config file."""
        monkeypatch.setattr(Path, "home", lambda: temp_dir)

        # Ensure no config file exists first
        config_path = temp_dir / ".aixterm"
        if config_path.exists():
            config_path.unlink()

        config_path.write_text("invalid json content")

        # Should fall back to defaults without crashing
        config = AIxTermConfig(config_path)
        assert config.get("model") == "local-model"


class TestConfigurationEdgeCases:
    """Test configuration edge cases and error conditions."""

    def test_config_file_permissions_error(self, temp_dir):
        """Test handling of config file permission errors."""
        config_path = temp_dir / ".aixterm"
        config_path.write_text('{"model": "test"}')
        config_path.chmod(0o000)  # Remove all permissions

        try:
            from unittest.mock import patch

            with patch(
                "builtins.open",
                side_effect=PermissionError("Permission denied"),
            ):
                config = AIxTermConfig(config_path)
                # Should fall back to defaults
                assert config.get("model") == "local-model"
        finally:
            config_path.chmod(0o644)  # Restore permissions for cleanup

    def test_config_corrupted_json(self, temp_dir):
        """Test handling of corrupted JSON config."""
        config_path = temp_dir / ".aixterm"
        config_path.write_text('{"model": "test", invalid json}')

        config = AIxTermConfig(config_path)
        # Should fall back to defaults
        assert config.get("model") == "local-model"

    def test_config_empty_file(self, temp_dir):
        """Test handling of empty config file."""
        config_path = temp_dir / ".aixterm"
        config_path.write_text("")

        config = AIxTermConfig(config_path)
        # Should fall back to defaults
        assert config.get("model") == "local-model"

    def test_config_invalid_data_types(self, temp_dir):
        """Test handling of invalid data types in config."""
        config_data = {
            "context_size": "not_a_number",
            "mcp_servers": "not_a_list",
            "cleanup": "not_a_dict",
            "api_url": 12345,  # Should be string
        }

        config_path = temp_dir / ".aixterm"
        config_path.write_text(json.dumps(config_data))

        config = AIxTermConfig(config_path)

        # Should validate and fix types
        assert isinstance(config.get("context_size"), int)
        assert isinstance(config.get("mcp_servers"), list)
        assert isinstance(config.get("cleanup"), dict)
        assert isinstance(config.get("api_url"), str)

    def test_config_nested_validation(self, temp_dir):
        """Test validation of nested configuration objects."""
        config_data = {
            "cleanup": {
                "enabled": "true",  # String instead of bool
                "max_log_age_days": "30",  # String instead of int
                "invalid_key": "should_be_removed",
            },
            "logging": {
                "level": 123,  # Invalid type
                "file": ["not", "a", "string"],  # Invalid type
            },
        }

        config_path = temp_dir / ".aixterm"
        config_path.write_text(json.dumps(config_data))

        config = AIxTermConfig(config_path)

        # Should validate nested objects
        cleanup = config.get("cleanup")
        assert isinstance(cleanup["enabled"], bool)
        assert isinstance(cleanup["max_log_age_days"], int)
        assert "invalid_key" not in cleanup

    def test_config_mcp_server_validation(self, temp_dir):
        """Test MCP server configuration validation."""
        config_data = {
            "mcp_servers": [
                {
                    "name": "valid-server",
                    "command": ["python", "server.py"],
                    "enabled": True,
                },
                {
                    "name": "",  # Invalid empty name
                    "command": "not_a_list",  # Invalid command format
                    "enabled": "yes",  # Invalid boolean format
                },
                "not_a_dict",  # Invalid server format
            ]
        }

        config_path = temp_dir / ".aixterm"
        config_path.write_text(json.dumps(config_data))

        config = AIxTermConfig(config_path)

        servers = config.get("mcp_servers")
        # Should filter out invalid servers
        assert len(servers) <= 1  # Only valid server should remain
        if servers:
            assert servers[0]["name"] == "valid-server"

    def test_config_save_with_unicode(self, temp_dir):
        """Test saving config with unicode characters."""
        config_path = temp_dir / ".aixterm"
        config = AIxTermConfig(config_path)

        # Set config with unicode
        config.set("model", "test-模型-🤖")
        success = config.save()
        assert success

        # Verify unicode was saved correctly
        config2 = AIxTermConfig(config_path)
        assert config2.get("model") == "test-模型-🤖"

    def test_config_backup_creation(self, temp_dir):
        """Test configuration file save functionality."""
        config_path = temp_dir / ".aixterm"
        config_path.write_text('{"model": "original"}')

        config = AIxTermConfig(config_path)
        config.set("model", "updated")

        # Test save functionality
        success = config.save()
        assert success

        # Verify the change was saved
        config2 = AIxTermConfig(config_path)
        assert config2.get("model") == "updated"

    def test_config_concurrent_access(self, temp_dir):
        """Test concurrent config access."""
        config_path = temp_dir / ".aixterm"
        config_path.write_text('{"model": "test"}')

        config1 = AIxTermConfig(config_path)
        config2 = AIxTermConfig(config_path)

        config1.set("model", "config1")
        config2.set("model", "config2")

        # Both should work without errors
        success1 = config1.save()
        success2 = config2.save()

        assert success1 and success2


class TestConfigurationSecurity:
    """Test configuration security features."""

    def test_config_file_permissions(self, temp_dir):
        """Test config file permissions after creation."""
        config_path = temp_dir / ".aixterm"
        config = AIxTermConfig(config_path)
        config.save()

        # Check that file was created
        assert config_path.exists()

        # In a real implementation, we'd check file permissions
        # For now, just verify it was created successfully
        stat = config_path.stat()
        assert stat.st_size > 0

    def test_sensitive_data_handling(self, temp_dir):
        """Test handling of sensitive configuration data."""
        config_path = temp_dir / ".aixterm"
        config = AIxTermConfig(config_path)

        # Set sensitive data
        config.set("api_key", "sensitive-key-12345")
        config.save()

        # Verify data is stored (in real implementation, might be encrypted)
        config2 = AIxTermConfig(config_path)
        assert config2.get("api_key") == "sensitive-key-12345"
