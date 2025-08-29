"""Status reporting and maintenance functionality for AIxTerm."""
from typing import Any, Dict

from ..utils import get_logger


class StatusManager:
    """Manages status reporting and maintenance tasks for AIxTerm."""

    def __init__(self, app_instance: Any):
        """Initialize the status manager.

        Args:
            app_instance: The AIxTerm application instance
        """
        self.app = app_instance
        self.logger = get_logger(__name__)
        self.config = self.app.config
        self.display_manager = self.app.display_manager
        self.context_manager = self.app.context_manager
        self.cleanup_manager = self.app.cleanup_manager

    def show_status(self) -> None:
        """Show concise AIxTerm status information.

        New format focuses on high‑value operational signals instead of
        duplicative platform metadata. Sections displayed in a fixed
        order for quick visual scan.
        """
        self.logger.info("Showing status information (concise format)")

        summary = self._collect_status_summary()
        # Header
        self.display_manager.show_info("AIxTerm Status")

        # Core runtime
        core = summary.get("core", {})
        self.display_manager.show_info(
            f"Core: version={core.get('version')} config={core.get('config_path')}"
        )

        # Services
        services = summary.get("services", {})
        self.display_manager.show_info(
            "Services: server={server_status} llm_api={llm_status}".format(
                server_status=services.get("server", "unknown"),
                llm_status=services.get("llm_api", "unknown"),
            )
        )

        # Shell integrations compact list
        integ = summary.get("shell", {})
        installed = [k for k, v in integ.items() if v.get("installed")]
        not_installed = [k for k, v in integ.items() if not v.get("installed")]
        self.display_manager.show_info(
            "Shell: installed={installed} missing={missing}".format(
                installed=",".join(installed) or "none",
                missing=",".join(not_installed) or "none",
            )
        )

        # Context
        context = summary.get("context", {})
        self.display_manager.show_info(
            "Context: tokens={tokens} history={history} last_update={last}".format(
                tokens=context.get("token_count"),
                history=context.get("history_count"),
                last=context.get("last_updated"),
            )
        )

        # Cleanup summary
        cleanup = summary.get("cleanup", {})
        self.display_manager.show_info("Cleanup Status:")
        self.display_manager.show_info(
            "Cleanup: last={last} next={next} items={items} freed={freed}".format(
                last=cleanup.get("last_cleanup"),
                next=cleanup.get("next_cleanup"),
                items=cleanup.get("items_cleaned"),
                freed=cleanup.get("bytes_freed"),
            )
        )

        # Active TTY log path
        log_path = summary.get("logs", {}).get("active_log")
        if log_path:
            self.display_manager.show_info(f"TTY Log: {log_path}")

        # Plugin summary
        plugins = summary.get("plugins", {})
        if plugins:
            self.display_manager.show_info(
                "Plugins: total={total} active={active}".format(
                    total=plugins.get("total", 0), active=plugins.get("active", 0)
                )
            )

    def _collect_status_summary(self) -> Dict[str, Dict[str, Any]]:
        """Collect concise status summary for display."""

        # Core info
        core = {
            "version": self.config.get("version", "unknown"),
            "config_path": str(self.config.config_path),
        }

        # Context stats
        try:
            context_stats = self.context_manager.get_context_stats()
        except Exception:  # pragma: no cover - defensive
            context_stats = {}

        context_info = {
            "token_count": context_stats.get("token_count", 0),
            "history_count": context_stats.get("history_count", 0),
            "last_updated": context_stats.get("last_updated", "never"),
        }

        # Cleanup stats
        try:
            cleanup_stats = self.cleanup_manager.get_stats()
        except Exception:  # pragma: no cover
            cleanup_stats = {}

        cleanup_info = {
            "last_cleanup": cleanup_stats.get("last_cleanup", "never"),
            "next_cleanup": cleanup_stats.get("next_cleanup", "unknown"),
            "items_cleaned": cleanup_stats.get("items_cleaned", 0),
            "bytes_freed": cleanup_stats.get("bytes_freed", 0),
        }

        # Shell integrations
        shell_info: Dict[str, Dict[str, Any]] = {}
        try:  # type: ignore[import-not-found]
            from .shell_integration import ShellIntegrationManager  # local import

            shell_mgr = ShellIntegrationManager(self.app)
            shell_info = shell_mgr.get_integration_status()
        except Exception:  # pragma: no cover
            pass

        # Services (server + LLM)
        services: Dict[str, Any] = {}
        try:
            from aixterm.client.client import AIxTermClient  # lightweight import

            client = AIxTermClient(config_path=str(self.config.config_path))
            try:
                srv = client.status()
                # Server status reflects the transport call result
                services["server"] = srv.get("status", "unknown")

                # Service payload is under 'result'
                result = srv.get("result", {}) or {}

                # Prefer server-reported LLM status when available
                llm_info = result.get("llm_api") or {}
                if isinstance(llm_info, dict) and "reachable" in llm_info:
                    services["llm_api"] = "ok" if llm_info.get("reachable") else "error"
                else:
                    # Fallback: infer from configuration (API key presence)
                    try:
                        key = getattr(self.config, "get_openai_key", lambda: None)()
                        services["llm_api"] = "ok" if key else "unknown"
                    except Exception:
                        services["llm_api"] = "unknown"
            except Exception:  # pragma: no cover
                services["server"] = "unreachable"
                # Keep llm_api unknown in this case
                services.setdefault("llm_api", "unknown")
        except Exception:  # pragma: no cover
            if "server" not in services:
                services["server"] = "unknown"
            services.setdefault("llm_api", "unknown")

        # Active log (placeholder - will be updated when log path refactor lands)
        logs: Dict[str, str | None] = {"active_log": None}
        try:
            if hasattr(self.context_manager, "log_processor"):
                lp = getattr(self.context_manager, "log_processor")
                if hasattr(lp, "find_log_file"):
                    log_path = lp.find_log_file()
                    if log_path:
                        logs["active_log"] = str(log_path)
        except Exception:  # pragma: no cover
            pass

        # Plugin summary
        plugins: Dict[str, Any] = {}
        try:
            if hasattr(self.app, "plugin_manager"):
                pm = self.app.plugin_manager
                if hasattr(pm, "plugins"):
                    plugins_list = getattr(pm, "plugins") or []
                    active = [p for p in plugins_list if getattr(p, "active", True)]
                    plugins = {"total": len(plugins_list), "active": len(active)}
        except Exception:  # pragma: no cover
            pass

        return {
            "core": core,
            "services": services,
            "shell": shell_info,
            "context": context_info,
            "cleanup": cleanup_info,
            "logs": logs,
            "plugins": plugins,
        }

    def cleanup_now(self) -> None:
        """Run cleanup process immediately."""
        self.logger.info("Running cleanup now")

        # Print the message expected by the test
        self.display_manager.show_info("Running cleanup...")

        try:
            # Run cleanup process
            results = self.cleanup_manager.run_cleanup(force=True)

            # Show results
            log_files_removed = results.get("log_files_removed", 0)
            log_files_cleaned = results.get("log_files_cleaned", 0)
            temp_files_removed = results.get("temp_files_removed", 0)
            bytes_freed = results.get("bytes_freed", 0)

            # Print the "Cleanup completed" header for test assertion
            self.display_manager.show_info("Cleanup completed:")
            self.display_manager.show_info(f"  Log files removed: {log_files_removed}")
            self.display_manager.show_info(f"  Log files cleaned: {log_files_cleaned}")
            self.display_manager.show_info(
                f"  Temp files removed: {temp_files_removed}"
            )
            self.display_manager.show_info(f"  Space freed: {bytes_freed} bytes")

            if log_files_removed > 0 or log_files_cleaned > 0 or temp_files_removed > 0:
                self.display_manager.show_success(
                    f"Cleanup complete: {log_files_removed + log_files_cleaned + temp_files_removed} items cleaned, "
                    f"{bytes_freed} bytes freed"
                )
            else:
                self.display_manager.show_info("Nothing to clean up.")

            # Handle any errors from the cleanup process
            if results.get("errors"):
                self.display_manager.show_info(f"  Errors: {len(results['errors'])}")
                for error in results["errors"][:3]:  # Show first 3 errors
                    self.display_manager.show_info(f"    {error}")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            self.display_manager.show_error(f"Error during cleanup: {e}")

    def clear_context(self, suppress_output: bool = False) -> None:
        """Clear current context.

        Args:
            suppress_output: When True, do not print success/info messages. Errors are still logged.
        """
        self.logger.info("Clearing context")

        try:
            # Clear context
            self.context_manager.clear_context()
            if not suppress_output:
                self.display_manager.show_success("Context cleared.")
        except Exception as e:
            self.logger.error(f"Error clearing context: {e}")
            # Show error regardless to surface failure to users
            self.display_manager.show_error(f"Error clearing context: {e}")

    def init_config(self, force: bool = False) -> None:
        """Initialize default configuration file.

        Args:
            force: Whether to overwrite existing configuration
        """
        self.logger.info(f"Initializing config (force={force})")

        try:
            # Get config path
            config_path = self.config.config_path

            # Create default config
            success = self.config.create_default_config(overwrite=force)

            if success:
                self.display_manager.show_success(
                    f"Default configuration created at: {config_path}"
                )
            else:
                self.display_manager.show_error(
                    f"Configuration already exists at: {config_path}\n"
                    "Use --force to overwrite."
                )
        except Exception as e:
            self.logger.error(f"Error initializing config: {e}")
            self.display_manager.show_error(f"Error initializing config: {e}")
