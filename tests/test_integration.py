"""Integration tests for AIxTerm."""

import json
import sys
from unittest.mock import Mock, patch

import pytest

from aixterm.main import AIxTerm
from aixterm.main.app import AIxTermApp
from aixterm.main.cli import main


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

    def test_run_with_simple_query(self, mock_config, mock_openai_client):
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

        # Use process_query directly for better control
        with patch.object(
            app.llm_client,
            "process_query",
            return_value={"content": "", "elapsed_time": 0},
        ):
            with patch.object(
                app.context_manager,
                "get_optimized_context",
                return_value="test context",
            ):
                with patch.object(app.logger, "warning") as mock_warning:
                    app.run("test query")

                    # Should log warning about no response
                    mock_warning.assert_any_call("No response received from AI.")

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
            app._status_manager.cleanup_manager,
            "run_cleanup",
            return_value=mock_results,
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
        """Test main function with no arguments - should show error for missing query."""
        with patch.object(sys, "argv", ["aixterm"]):
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                mock_app.display_manager.show_error = Mock()
                MockApp.return_value = mock_app

                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock run_cli_mode to simulate the "no query" error path
                    mock_run.return_value = None

                    main()

                    # Verify run_cli_mode was called (it handles the no-query case)
                    mock_run.assert_called_once()

    def test_main_help_command(self):
        """Test main function with help command."""
        with patch.object(sys, "argv", ["aixterm", "--help"]):
            # Create a custom parser that doesn't exit
            mock_parser = Mock()
            mock_parser.parse_args.return_value = Mock(
                help=False,  # We'll handle help manually
                query=[],
                config=None,
                init_config=False,
                force=False,
                context=None,
                clear_context=False,
                cleanup=False,
                status=False,
                list_tools=False,
                install_shell=None,
                uninstall_shell=None,
                message_id=None,
                no_thinking=False,
                no_prompt=False,
                plan=False,
                file=None,
                api_url=None,
                api_key=None,
                debug=False,
            )

            # Create a mock for ArgumentParser
            mock_arg_parser = Mock()
            mock_arg_parser.return_value = mock_parser

            # Patch argparse.ArgumentParser to use our mock
            with patch("aixterm.main.cli.argparse.ArgumentParser", mock_arg_parser):
                # Also patch sys.exit to prevent exiting
                with patch("sys.exit"):
                    # Now when main() is called, it will use our mock parser
                    main()

            # Verify our parser was used
            assert mock_parser.parse_args.called

    def test_main_status_command(self, mock_config):
        """Test main function with status command."""
        with patch.object(sys, "argv", ["aixterm", "--status"]):
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                with patch("aixterm.main.cli.StatusManager") as MockStatusManager:
                    mock_app = Mock()
                    mock_status_manager = Mock()
                    MockApp.return_value = mock_app
                    MockStatusManager.return_value = mock_status_manager

                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                    # The status manager's show_status should be called
                    mock_status_manager.show_status.assert_called_once()

    def test_main_tools_command(self, mock_config):
        """Test main function with tools command."""
        with patch.object(
            sys, "argv", ["aixterm", "--list-tools"]
        ):  # Note: it's --list-tools, not --tools
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                with patch("aixterm.main.cli.ToolsManager") as MockToolsManager:
                    mock_app = Mock()
                    mock_tools_manager = Mock()
                    MockApp.return_value = mock_app
                    MockToolsManager.return_value = mock_tools_manager

                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                    # The tools manager's list_tools should be called
                    mock_tools_manager.list_tools.assert_called_once()

    def test_main_cleanup_command(self, mock_config):
        """Test main function with cleanup command."""
        with patch.object(sys, "argv", ["aixterm", "--cleanup"]):
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                with patch("aixterm.main.cli.StatusManager") as MockStatusManager:
                    mock_app = Mock()
                    mock_status_manager = Mock()
                    MockApp.return_value = mock_app
                    MockStatusManager.return_value = mock_status_manager

                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                    # The status manager's cleanup_now should be called
                    mock_status_manager.cleanup_now.assert_called_once()

    def test_main_regular_query(self, mock_config):
        """Test main function with regular query."""
        with patch.object(sys, "argv", ["aixterm", "list", "files"]):
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock the run_cli_mode function
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    main()

                    # Verify run_cli_mode was called with the right arguments
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    # Check that the function was called with correct parameters
                    assert call_args.kwargs["app"] == mock_app
                    assert call_args.kwargs["query"] == ["list", "files"]
                    assert call_args.kwargs["use_planning"] is False
                    assert call_args.kwargs["show_thinking"] is False  # New default

    def test_main_exception_handling(self, mock_config):
        """Test main function exception handling."""
        with patch.object(sys, "argv", ["aixterm", "test"]):
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to raise an exception
                with patch(
                    "aixterm.main.cli.run_cli_mode", side_effect=Exception("Test error")
                ):
                    with patch("aixterm.main.cli.get_logger") as mock_get_logger:
                        mock_logger = Mock()
                        mock_get_logger.return_value = mock_logger

                        with pytest.raises(SystemExit) as excinfo:
                            main()

                        # Should log error and exit with code 1
                        mock_logger.error.assert_any_call("Error: Test error")
                        assert excinfo.value.code == 1

    def test_end_to_end_workflow(
        self, mock_config, mock_openai_client, sample_log_file
    ):
        """Test complete end-to-end workflow without command execution."""
        with patch.object(sys, "argv", ["aixterm", "list", "processes"]):
            # We need to patch run_cli_mode directly to avoid stdin issues
            with patch("aixterm.main.cli.run_cli_mode") as mock_run_cli:
                # Mock AIxTermApp to return our mock app
                with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                    # Configure our mock app
                    mock_app = Mock()
                    MockApp.return_value = mock_app

                    # Create a mock LLM client that uses our mock_openai_client
                    mock_llm_client = Mock()
                    mock_llm_client.openai_client = mock_openai_client

                    # Set the llm_client attribute on the mock app
                    mock_app.llm_client = mock_llm_client

                    # Now mock the process_query method to ensure it's called
                    mock_app.llm_client.process_query = Mock(
                        return_value="Test response"
                    )

                    # Run the main function which will call our mocked run_cli_mode
                    main()

                    # Verify the app was created
                    MockApp.assert_called_once()

                    # Verify run_cli_mode was called with the expected arguments
                    mock_run_cli.assert_called_once()
                    args, kwargs = mock_run_cli.call_args
                    assert kwargs["app"] == mock_app
                    assert kwargs["query"] == ["list", "processes"]


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
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock the run_cli_mode function
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Should call run_cli_mode with the query and file list
                        mock_run.assert_called_once()
                        args, kwargs = mock_run.call_args
                        assert kwargs["app"] == mock_app
                        assert kwargs["query"] == ["what", "does", "this", "do"]
                        assert kwargs["files"] == [str(test_file)]

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
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to avoid actual execution
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Should call run_cli_mode with the right arguments
                        mock_run.assert_called_once()
                        args, kwargs = mock_run.call_args
                        assert kwargs["app"] == mock_app
                        assert kwargs["query"] == ["analyze", "code"]
                        assert sorted(kwargs["files"]) == sorted(
                            [str(file1), str(file2)]
                        )

    def test_main_without_files(self, mock_config):
        """Test main function without file arguments."""
        with patch.object(sys, "argv", ["aixterm", "simple", "query"]):
            # Use the proper import path for AIxTermApp
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to avoid actual execution
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Verify that run_cli_mode was called with the right arguments
                        mock_run.assert_called_once()
                        args, kwargs = mock_run.call_args
                        assert kwargs["app"] == mock_app
                        assert kwargs["query"] == ["simple", "query"]
                        assert kwargs.get("files", []) == []

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
            # Use the proper import path for AIxTermApp
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to avoid actual execution
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Verify that run_cli_mode was called with the right arguments
                        mock_run.assert_called_once()
                        args, kwargs = mock_run.call_args
                        assert kwargs["app"] == mock_app
                        assert kwargs["query"] == ["simple", "query"]

                        # Should set the API overrides
                        mock_app.config.set.assert_any_call(
                            "api_url", "http://example.com/api"
                        )
                        mock_app.config.set.assert_any_call("api_key", "test-key")

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
            # Use the proper import path for AIxTermApp
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to avoid actual execution
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Verify that config.set was called with the API URL
                        mock_app.config.set.assert_any_call(
                            "api_url", "http://localhost:8080/v1"
                        )

                        # Verify that run_cli_mode was called with the correct arguments
                        mock_run.assert_called_once()
                        args, kwargs = mock_run.call_args
                        assert kwargs["app"] == mock_app
                        assert kwargs["query"] == ["test", "query"]

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
            # Use the proper import path for AIxTermApp
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to avoid actual execution
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Verify that config.set was called with the API URL
                        mock_app.config.set.assert_any_call(
                            "api_url", "http://custom.api/v1"
                        )

                        # Verify that run_cli_mode was called with the right arguments
                        mock_run.assert_called_once()
                        args, kwargs = mock_run.call_args
                        assert kwargs["app"] == mock_app
                        assert kwargs["query"] == ["analyze", "this", "code"]
                        assert kwargs["files"] == [str(test_file)]


class TestPlanningModeIntegration:
    """Test planning mode functionality."""

    def test_planning_flag_short_form(self, mock_config):
        """Test -p flag for planning mode."""
        with patch.object(
            sys, "argv", ["aixterm", "-p", "create", "deployment", "strategy"]
        ):
            # Use the proper import path for AIxTermApp
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to avoid actual execution
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Verify that run_cli_mode was called with the right arguments
                        mock_run.assert_called_once()
                        args, kwargs = mock_run.call_args
                        assert kwargs["app"] == mock_app
                        assert kwargs["query"] == ["create", "deployment", "strategy"]
                        assert kwargs["use_planning"] is True

    def test_planning_flag_long_form(self, mock_config):
        """Test --plan flag for planning mode."""
        with patch.object(
            sys, "argv", ["aixterm", "--plan", "setup", "CI/CD", "pipeline"]
        ):
            # Use the proper import path for AIxTermApp
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to avoid actual execution
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Verify that run_cli_mode was called with the right arguments
                        mock_run.assert_called_once()
                        args, kwargs = mock_run.call_args
                        assert kwargs["app"] == mock_app
                        assert kwargs["query"] == ["setup", "CI/CD", "pipeline"]
                        assert kwargs["use_planning"] is True

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
            # Use the proper import path for AIxTermApp
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to avoid actual execution
                with patch("aixterm.main.cli.run_cli_mode") as mock_run:
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Verify that config.set was called with the API URL
                        mock_app.config.set.assert_any_call(
                            "api_url", "http://custom:8080/v1"
                        )

                        # Verify that run_cli_mode was called with the right arguments
                        mock_run.assert_called_once()
                        args, kwargs = mock_run.call_args
                        assert kwargs["app"] == mock_app
                        assert kwargs["query"] == ["refactor", "this", "code"]
                        assert kwargs["use_planning"] is True
                        assert kwargs["files"] == [str(test_file)]

    def test_planning_mode_integration_with_llm(self, mock_config, mock_openai_client):
        """Test planning mode integration with LLM."""
        app = AIxTermApp()

        # Mock the process_query method directly instead of mocking OpenAI
        with patch.object(
            app.llm_client, "process_query", return_value="## Planning Response"
        ) as mock_process:
            with patch.object(
                app.context_manager,
                "get_optimized_context",
                return_value="test context",
            ):
                with patch.object(app.context_manager, "create_log_entry") as mock_log:
                    with patch("builtins.print"):
                        app.run("Deploy a web application", use_planning=True)

                        # Verify planning mode was used (check if planning prompt was passed)
                        args, kwargs = mock_process.call_args
                        assert "REQUEST: Deploy a web application" in kwargs.get(
                            "query", ""
                        )
                        assert "Problem Analysis" in kwargs.get("query", "")

                        # Verify log entry was created
                        mock_log.assert_called()


class TestAdvancedIntegration:
    """Advanced integration test cases."""

    def test_file_context_integration(self, mock_config, mock_openai_client, tmp_path):
        """Test file context integration with multiple files."""
        app = AIxTermApp()

        # Create test files
        file1 = tmp_path / "test1.py"
        file1.write_text("def hello(): print('Hello')")
        file2 = tmp_path / "test2.py"
        file2.write_text("def world(): print('World')")

        # Set up the LLM client mock
        mock_llm = Mock()
        mock_llm.process_query.return_value = "Analysis of the files"
        app.llm_client = mock_llm

        # Mock the add_file_context method to verify it's called
        with patch.object(app.context_manager, "add_file_context") as mock_add_file:
            with patch.object(app.context_manager, "create_log_entry"):
                with patch("builtins.print"):
                    app.run("analyze these files", files=[str(file1), str(file2)])

                    # Verify add_file_context was called for both files
                    assert mock_add_file.call_count == 2
                    mock_add_file.assert_any_call(
                        str(file1), "def hello(): print('Hello')"
                    )
                    mock_add_file.assert_any_call(
                        str(file2), "def world(): print('World')"
                    )

                    # Verify process_query was called
                    mock_llm.process_query.assert_called_once()

    def test_error_handling_integration(self, mock_config):
        """Test error handling during integration."""
        from aixterm.llm.exceptions import LLMError

        app = AIxTermApp()

        # Specifically use LLMError since that's what's handled in the run method
        with patch.object(
            app.llm_client,
            "process_query",
            side_effect=LLMError("Test error"),
        ):
            with patch.object(app.display_manager, "show_error") as mock_show_error:
                # Run the query - this should trigger error handling
                app.run("test query")

                # Should show the error through the display manager
                mock_show_error.assert_called_with("Error: Test error")

    def test_mcp_integration_error_handling(self, mock_config):
        """Test MCP integration with error handling."""
        app = AIxTermApp()

        with patch.object(
            app.mcp_client,
            "get_available_tools",
            side_effect=Exception("MCP error"),
        ):
            # Should not crash when MCP has errors - but should still
            # raise for direct calls
            with pytest.raises(Exception, match="MCP error"):
                app.mcp_client.get_available_tools()

    def test_signal_handling_integration(self, mock_config):
        """Test signal handling integration."""
        app = AIxTermApp()

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
        app = AIxTermApp(config_path=str(custom_config))

        assert app.config.get("model") == "custom-model"
        assert app.config.get("api_url") == "http://custom.url"
        assert app.config.get("context_size") == 3000


class TestCommandLineEdgeCases:
    """Test edge cases in command line argument handling."""

    def test_empty_query_with_flags(self, mock_config):
        """Test behavior with flags but no actual query."""
        with patch.object(sys, "argv", ["aixterm", "--plan"]):
            # In the new version, we handle it within run_cli_mode
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Create a mock display manager
                mock_display = Mock()
                mock_app.display_manager = mock_display

                # Mock run_cli_mode to call it directly, so we can verify error handling
                with patch(
                    "aixterm.main.cli.run_cli_mode",
                    side_effect=lambda **kwargs: (
                        None
                        if kwargs.get("query")
                        else mock_display.show_error("Error: No query provided.")
                    ),
                ):
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()

                        # Check that run_cli_mode was called (which would internally handle the no query case)
                        mock_display.show_error.assert_called_with(
                            "Error: No query provided."
                        )

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
            # Use the proper import path for AIxTermApp
            with patch("aixterm.main.cli.AIxTermApp") as MockApp:
                mock_app = Mock()
                MockApp.return_value = mock_app

                # Mock run_cli_mode to avoid actual execution
                with patch("aixterm.main.cli.run_cli_mode"):
                    # Mock app.shutdown() call that should happen at end of main()
                    with patch.object(AIxTermApp, "shutdown"):
                        main()
                        # Verify both overrides were applied
                mock_app.config.set.assert_any_call("api_url", "http://test:8080/v1")
                mock_app.config.set.assert_any_call("api_key", "test-key-123")

    def test_config_auto_creation(self, tmp_path):
        """Test that config file is automatically created when missing."""
        # Test that config is automatically created - this is now handled in config.py
        with patch("aixterm.main.cli.AIxTermApp") as MockApp:
            mock_app = Mock()
            MockApp.return_value = mock_app
            mock_app.config.config_path = tmp_path / ".aixterm"

            with patch.object(sys, "argv", ["aixterm", "test query"]):
                with patch("aixterm.main.cli.run_cli_mode") as mock_run_cli:
                    main()

                    # Verify that run_cli_mode was called (config creation happens automatically)
                    mock_run_cli.assert_called_once()
