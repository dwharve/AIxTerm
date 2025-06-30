"""Integration tests for AIxTerm."""

import json
import sys
from io import StringIO
from unittest.mock import Mock, patch

import pytest

from aixterm.main import AIxTerm, main


class TestAIxTermIntegration:
    """Integration test cases for AIxTerm application."""

    def test_aixterm_initialization(self, mock_config):
        """Test AIxTerm application initialization."""
        app = AIxTerm()

        assert app.config is not None
        assert app.context_manager is not None
        assert app.llm_client is not None
        assert app.mcp_client is not None
        assert app.cleanup_manager is not None

    def test_run_with_simple_query(self, mock_config, mock_requests_post):
        """Test running AIxTerm with a simple query."""
        app = AIxTerm()

        with patch.object(
            app.context_manager,
            "get_optimized_context",
            return_value="test context",
        ):
            with patch.object(app.context_manager, "create_log_entry") as mock_log:
                with patch("builtins.print"):
                    app.run("list files")

                    # Should have logged the interaction
                    mock_log.assert_called()

    def test_run_with_empty_response(self, mock_config):
        """Test running AIxTerm when LLM returns empty response."""
        app = AIxTerm()

        with patch.object(app.llm_client, "ask_with_context", return_value=""):
            with patch.object(
                app.context_manager,
                "get_optimized_context",
                return_value="test context",
            ):
                with patch("builtins.print") as mock_print:
                    app.run("test query")

                    # Should print message about no response
                    mock_print.assert_any_call("No response received from AI.")

    def test_run_with_mcp_servers(self, mock_config):
        """Test running AIxTerm with MCP servers configured."""
        mock_config._config["mcp_servers"] = [
            {
                "name": "test-server",
                "command": ["python", "server.py"],
                "enabled": True,
            }
        ]

        app = AIxTerm()

        with patch.object(app.mcp_client, "initialize") as mock_init:
            with patch.object(app.mcp_client, "get_available_tools", return_value=[]):
                with patch.object(
                    app.llm_client,
                    "ask_with_context",
                    return_value="test response",
                ):
                    with patch.object(
                        app.context_manager,
                        "get_terminal_context",
                        return_value="test context",
                    ):
                        with patch("builtins.print"):
                            app.run("test query")

                            # Should have initialized MCP client
                            mock_init.assert_called_once()

    def test_run_with_cleanup_needed(self, mock_config):
        """Test running AIxTerm when cleanup is needed."""
        app = AIxTerm()

        with patch.object(app.cleanup_manager, "should_run_cleanup", return_value=True):
            with patch.object(app.cleanup_manager, "run_cleanup") as mock_cleanup:
                mock_cleanup.return_value = {"log_files_removed": 2}

                with patch.object(
                    app.llm_client,
                    "ask_with_context",
                    return_value="test response",
                ):
                    with patch.object(
                        app.context_manager,
                        "get_terminal_context",
                        return_value="test context",
                    ):
                        with patch("builtins.print"):
                            app.run("test query")

                            # Should have run cleanup
                            mock_cleanup.assert_called_once()

    def test_list_tools_no_servers(self, mock_config):
        """Test listing tools when no MCP servers are configured."""
        app = AIxTerm()

        with patch("builtins.print") as mock_print:
            app.list_tools()

            mock_print.assert_any_call("No MCP servers configured.")

    def test_list_tools_with_servers(self, mock_config):
        """Test listing tools with MCP servers configured."""
        mock_config._config["mcp_servers"] = [
            {
                "name": "test-server",
                "command": ["python", "server.py"],
                "enabled": True,
            }
        ]

        app = AIxTerm()

        mock_tools = [
            {
                "server": "test-server",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                },
            }
        ]

        with patch.object(app.mcp_client, "initialize"):
            with patch.object(
                app.mcp_client, "get_available_tools", return_value=mock_tools
            ):
                with patch("builtins.print") as mock_print:
                    app.list_tools()

                    # Should print tool information
                    mock_print.assert_any_call("\nAvailable MCP Tools:")
                    mock_print.assert_any_call("\nServer: test-server")
                    mock_print.assert_any_call("  test_tool: A test tool")

    def test_status_command(self, mock_config):
        """Test status command output."""
        app = AIxTerm()

        with patch.object(app.mcp_client, "initialize"):
            with patch.object(app.mcp_client, "get_server_status", return_value={}):
                with patch.object(
                    app.cleanup_manager, "get_cleanup_status"
                ) as mock_status:
                    mock_status.return_value = {
                        "cleanup_enabled": True,
                        "log_files_count": 5,
                        "total_log_size": "1.2 MB",
                        "last_cleanup": "2024-01-01T12:00:00",
                        "next_cleanup_due": "2024-01-02T12:00:00",
                    }

                    with patch("builtins.print") as mock_print:
                        app.status()

                        # Should print status information
                        mock_print.assert_any_call("AIxTerm Status")
                        mock_print.assert_any_call("\nCleanup Status:")

    def test_cleanup_now_command(self, mock_config):
        """Test cleanup now command."""
        app = AIxTerm()

        mock_results = {
            "log_files_removed": 3,
            "log_files_cleaned": 1,
            "temp_files_removed": 2,
            "bytes_freed": 1024,
            "errors": [],
        }

        with patch.object(
            app.cleanup_manager, "force_cleanup_now", return_value=mock_results
        ):
            with patch("builtins.print") as mock_print:
                app.cleanup_now()

                # Should print cleanup results
                mock_print.assert_any_call("Running cleanup...")
                mock_print.assert_any_call("Cleanup completed:")
                mock_print.assert_any_call("  Log files removed: 3")

    def test_shutdown(self, mock_config):
        """Test application shutdown."""
        app = AIxTerm()

        with patch.object(app.mcp_client, "shutdown") as mock_shutdown:
            app.shutdown()

            mock_shutdown.assert_called_once()

    def test_signal_handling(self, mock_config):
        """Test signal handling for graceful shutdown."""
        app = AIxTerm()

        with patch.object(app, "shutdown") as mock_shutdown:
            with patch("sys.exit") as mock_exit:
                # Simulate SIGINT
                app._signal_handler(2, None)

                mock_shutdown.assert_called_once()
                mock_exit.assert_called_once_with(0)


class TestMainFunction:
    """Test cases for the main CLI function."""

    def test_main_no_arguments(self):
        """Test main function with no arguments."""
        with patch.object(sys, "argv", ["aixterm"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as excinfo:
                    main()

                # Check that help was printed (argparse format)
                output = mock_stdout.getvalue()
                assert "AIxTerm - AI-powered command line assistant" in output
                assert excinfo.value.code == 1

    def test_main_help_command(self):
        """Test main function with help command."""
        with patch.object(sys, "argv", ["aixterm", "--help"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as excinfo:
                    main()

                # Check that help was printed (argparse format)
                output = mock_stdout.getvalue()
                assert "AIxTerm - AI-powered command line assistant" in output
                assert excinfo.value.code == 0

    def test_main_status_command(self, mock_config):
        """Test main function with status command."""
        with patch.object(sys, "argv", ["aixterm", "--status"]):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                mock_app.status.assert_called_once()
                mock_app.shutdown.assert_called_once()

    def test_main_tools_command(self, mock_config):
        """Test main function with tools command."""
        with patch.object(sys, "argv", ["aixterm", "--tools"]):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                mock_app.list_tools.assert_called_once()
                mock_app.shutdown.assert_called_once()

    def test_main_cleanup_command(self, mock_config):
        """Test main function with cleanup command."""
        with patch.object(sys, "argv", ["aixterm", "--cleanup"]):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                mock_app.cleanup_now.assert_called_once()
                mock_app.shutdown.assert_called_once()

    def test_main_regular_query(self, mock_config):
        """Test main function with regular query."""
        with patch.object(sys, "argv", ["aixterm", "list", "files"]):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                mock_app.config.is_server_mode_enabled.return_value = False
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                mock_app.run_cli_mode.assert_called_once_with(
                    "list files", [], use_planning=False
                )

    def test_main_exception_handling(self, mock_config):
        """Test main function exception handling."""
        with patch.object(sys, "argv", ["aixterm", "test"]):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                mock_app.run_cli_mode.side_effect = Exception("Test error")
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                with patch("builtins.print") as mock_print:
                    with pytest.raises(SystemExit) as excinfo:
                        main()

                    # Should print error and exit with code 1
                    mock_print.assert_any_call("Error: Test error")
                    assert excinfo.value.code == 1

    def test_end_to_end_workflow(
        self, mock_config, mock_requests_post, sample_log_file
    ):
        """Test complete end-to-end workflow without command execution."""
        with patch.object(sys, "argv", ["aixterm", "list", "processes"]):
            with patch("aixterm.main.AIxTerm.shutdown"):  # Prevent actual shutdown
                with patch("builtins.print"):
                    # This should go through the workflow:
                    # 1. Parse command line
                    # 2. Initialize AIxTerm
                    # 3. Get context
                    # 4. Call LLM
                    # 5. Log interaction
                    main()

                    # Verify that the request was made to the LLM
                    mock_requests_post.assert_called()


class TestMainFunctionWithFiles:
    """Test cases for main function with file arguments."""

    def test_main_with_file_arguments(self, mock_config, tmp_path):
        """Test main function with --file arguments."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('test')")

        with patch.object(
            sys,
            "argv",
            ["aixterm", "--file", str(test_file), "what", "does", "this", "do"],
        ):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Should call run with the query and file list
                mock_app.run_cli_mode.assert_called_once_with(
                    "what does this do", [str(test_file)], use_planning=False
                )
                mock_app.shutdown.assert_called_once()

    def test_main_with_multiple_files(self, mock_config, tmp_path):
        """Test main function with multiple --file arguments."""
        file1 = tmp_path / "file1.py"
        file2 = tmp_path / "file2.py"
        file1.write_text("code1")
        file2.write_text("code2")

        with patch.object(
            sys,
            "argv",
            [
                "aixterm",
                "--file",
                str(file1),
                "--file",
                str(file2),
                "analyze",
                "code",
            ],
        ):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Should call run with both files
                mock_app.run_cli_mode.assert_called_once_with(
                    "analyze code",
                    [str(file1), str(file2)],
                    use_planning=False,
                )

    def test_main_without_files(self, mock_config):
        """Test main function without file arguments."""
        with patch.object(sys, "argv", ["aixterm", "simple", "query"]):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Should call run with empty file list
                mock_app.run_cli_mode.assert_called_once_with(
                    "simple query", [], use_planning=False
                )

    def test_main_with_api_overrides(self, mock_config, tmp_path):
        """Test main function with API URL and key overrides."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('test')")

        with patch.object(
            sys,
            "argv",
            [
                "aixterm",
                "--api_url",
                "http://example.com/api",
                "--api_key",
                "test-key",
                "simple",
                "query",
            ],
        ):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Should call run with the query and empty file list
                mock_app.run_cli_mode.assert_called_once_with(
                    "simple query", [], use_planning=False
                )
                # Should set the API overrides
                mock_app.config.set.assert_any_call("api_url", "http://example.com/api")
                mock_app.config.set.assert_any_call("api_key", "test-key")
                mock_app.shutdown.assert_called_once()

    def test_main_with_api_url_override_only(self, mock_config):
        """Test main function with only API URL override."""
        with patch.object(
            sys,
            "argv",
            [
                "aixterm",
                "--api_url",
                "http://localhost:8080/v1",
                "test",
                "query",
            ],
        ):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Should only set the API URL
                mock_app.config.set.assert_called_once_with(
                    "api_url", "http://localhost:8080/v1"
                )
                mock_app.run_cli_mode.assert_called_once_with(
                    "test query", [], use_planning=False
                )

    def test_main_with_file_and_api_overrides(self, mock_config, tmp_path):
        """Test main function with both file context and API overrides."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        with patch.object(
            sys,
            "argv",
            [
                "aixterm",
                "--api_url",
                "http://custom.api/v1",
                "--file",
                str(test_file),
                "analyze",
                "this",
                "code",
            ],
        ):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Should set the API URL and include the file
                mock_app.config.set.assert_called_once_with(
                    "api_url", "http://custom.api/v1"
                )
                mock_app.run_cli_mode.assert_called_once_with(
                    "analyze this code", [str(test_file)], use_planning=False
                )


class TestPlanningModeIntegration:
    """Test planning mode functionality."""

    def test_planning_flag_short_form(self, mock_config):
        """Test -p flag for planning mode."""
        with patch.object(
            sys, "argv", ["aixterm", "-p", "create", "deployment", "strategy"]
        ):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Verify run was called with planning=True
                mock_app.run_cli_mode.assert_called_once_with(
                    "create deployment strategy", [], use_planning=True
                )

    def test_planning_flag_long_form(self, mock_config):
        """Test --plan flag for planning mode."""
        with patch.object(
            sys, "argv", ["aixterm", "--plan", "setup", "CI/CD", "pipeline"]
        ):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                mock_app.config.is_server_mode_enabled.return_value = False
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Verify run_cli_mode was called with planning=True
                mock_app.run_cli_mode.assert_called_once_with(
                    "setup CI/CD pipeline", [], use_planning=True
                )

    def test_planning_with_files_and_api_overrides(self, mock_config, tmp_path):
        """Test planning mode with files and API overrides."""
        test_file = tmp_path / "project.py"
        test_file.write_text("# Project code")

        with patch.object(
            sys,
            "argv",
            [
                "aixterm",
                "--plan",
                "--file",
                str(test_file),
                "--api_url",
                "http://custom:8080/v1",
                "refactor",
                "this",
                "code",
            ],
        ):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Verify planning mode, files, and API overrides
                mock_app.run_cli_mode.assert_called_once_with(
                    "refactor this code", [str(test_file)], use_planning=True
                )
                mock_app.config.set.assert_called_once_with(
                    "api_url", "http://custom:8080/v1"
                )

    def test_planning_mode_integration_with_llm(self, mock_config, mock_requests_post):
        """Test planning mode integration with LLM."""
        app = AIxTerm()

        # Mock planning response
        mock_requests_post.return_value.status_code = 200
        mock_requests_post.return_value.iter_lines.return_value = [
            (
                b'data: {"choices": [{"delta": {"content": "## Plan\\n1. First '
                b'step\\n2. Second step"}}]}'
            ),
            b"data: [DONE]",
        ]

        with patch.object(
            app.context_manager,
            "get_optimized_context",
            return_value="test context",
        ):
            with patch.object(app.context_manager, "create_log_entry") as mock_log:
                with patch("builtins.print"):
                    app.run("Deploy a web application", use_planning=True)

                    # Verify planning mode was used
                    call_args = mock_requests_post.call_args
                    request_data = call_args[1][
                        "json"
                    ]  # Already a dict, no need to parse JSON
                    system_message = request_data["messages"][0]["content"]
                    assert "strategic planning" in system_message.lower()
                    mock_log.assert_called()


class TestAdvancedIntegration:
    """Advanced integration test cases."""

    def test_file_context_integration(self, mock_config, mock_requests_post, tmp_path):
        """Test file context integration with multiple files."""
        app = AIxTerm()

        # Create test files
        file1 = tmp_path / "test1.py"
        file1.write_text("def hello(): print('Hello')")
        file2 = tmp_path / "test2.py"
        file2.write_text("def world(): print('World')")

        with patch.object(app.context_manager, "get_optimized_context") as mock_context:
            with patch.object(app.context_manager, "create_log_entry"):
                with patch("builtins.print"):
                    app.run("analyze these files", [str(file1), str(file2)])

                    # Should have called get_optimized_context with file paths
                    mock_context.assert_called()

    def test_error_handling_integration(self, mock_config):
        """Test error handling during integration."""
        app = AIxTerm()

        with patch.object(
            app.llm_client,
            "ask_with_context",
            side_effect=Exception("Test error"),
        ):
            with patch("builtins.print") as mock_print:
                with patch("sys.exit") as mock_exit:
                    app.run("test query")

                    # Should handle the error gracefully
                    mock_print.assert_any_call("Unexpected error: Test error")
                    mock_exit.assert_called_once_with(1)

    def test_mcp_integration_error_handling(self, mock_config):
        """Test MCP integration with error handling."""
        app = AIxTerm()

        with patch.object(
            app.mcp_client,
            "get_available_tools",
            side_effect=Exception("MCP error"),
        ):
            with patch("builtins.print"):
                # Should not crash when MCP has errors - but should still
                # raise for direct calls
                with pytest.raises(Exception, match="MCP error"):
                    app.mcp_client.get_available_tools()

    def test_signal_handling_integration(self, mock_config):
        """Test signal handling integration."""
        app = AIxTerm()

        with patch.object(app, "shutdown") as mock_shutdown:
            with patch("sys.exit") as mock_exit:
                # Simulate SIGINT
                app._signal_handler(2, None)  # SIGINT = 2
                mock_shutdown.assert_called_once()
                mock_exit.assert_called_once_with(0)

    def test_configuration_override_integration(self, tmp_path):
        """Test configuration override integration."""
        # Create custom config without the mock
        custom_config = tmp_path / ".aixterm"
        config_data = {
            "model": "custom-model",
            "api_url": "http://custom.url",
            "context_size": 3000,
        }
        custom_config.write_text(json.dumps(config_data))

        # Create app without config mock
        app = AIxTerm(str(custom_config))

        assert app.config.get("model") == "custom-model"
        assert app.config.get("api_url") == "http://custom.url"
        assert app.config.get("context_size") == 3000


class TestCommandLineEdgeCases:
    """Test edge cases in command line argument handling."""

    def test_empty_query_with_flags(self, mock_config):
        """Test behavior with flags but no actual query."""
        with patch.object(sys, "argv", ["aixterm", "--plan"]):
            with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
                with pytest.raises(SystemExit) as excinfo:
                    main()
                # Should print help when no query is provided
                output = mock_stdout.getvalue()
                assert "AIxTerm - AI-powered command line assistant" in output
                assert excinfo.value.code == 1

    def test_multiple_api_overrides(self, mock_config):
        """Test multiple API parameter overrides."""
        with patch.object(
            sys,
            "argv",
            [
                "aixterm",
                "--api_url",
                "http://test:8080/v1",
                "--api_key",
                "test-key-123",
                "test",
                "query",
            ],
        ):
            with patch("aixterm.main.AIxTerm") as MockAIxTerm:
                mock_app = Mock()
                MockAIxTerm.return_value = mock_app
                mock_app.config.is_server_mode_enabled.return_value = False

                main()

                # Verify both overrides were applied
                expected_calls = [
                    ("api_url", "http://test:8080/v1"),
                    ("api_key", "test-key-123"),
                ]
                actual_calls = [call[0] for call in mock_app.config.set.call_args_list]
                assert actual_calls == expected_calls

    def test_init_config_force_flag(self, tmp_path):
        """Test --init-config with --force flag."""
        config_file = tmp_path / ".aixterm"
        config_file.write_text('{"existing": "config"}')

        with patch.object(sys, "argv", ["aixterm", "--init-config", "--force"]):
            with patch("aixterm.config.AIxTermConfig") as MockConfig:
                mock_config_instance = Mock()
                mock_config_instance.config_path = config_file
                mock_config_instance.create_default_config.return_value = True
                MockConfig.return_value = mock_config_instance

                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 0
                mock_config_instance.create_default_config.assert_called_once_with(
                    overwrite=True
                )
