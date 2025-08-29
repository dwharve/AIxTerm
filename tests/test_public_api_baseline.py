"""
Test suite for Public API Baseline - Phase 2 Batch 9

This test suite ensures that the intended public API surface remains stable
and prevents accidental removal or renaming of critical public symbols.
"""

import pytest
import importlib
import sys
from pathlib import Path

# Core public API modules that must remain accessible
CORE_API_MODULES = [
    "aixterm",
    "aixterm.config", 
    "aixterm.mcp_client",
    "aixterm.cleanup",
    "aixterm.utils",
    "aixterm.context",
    "aixterm.display",
    "aixterm.llm",
]

# Critical public symbols that must be available from main module
MAIN_MODULE_EXPORTS = [
    "AIxTermConfig",
    "TerminalContext", 
    "DisplayManager",
    "create_display_manager",
    "LLMClient",
    "MCPClient",
    "CleanupManager",
]

# Critical classes that must remain available
CRITICAL_CLASSES = {
    "aixterm.config": ["AIxTermConfig"],
    "aixterm.mcp_client": ["MCPClient", "MCPServer", "MCPError", "ProgressParams", "ProgressCallback"],
    "aixterm.cleanup": ["CleanupManager"],
}

# Critical functions that must remain available  
CRITICAL_FUNCTIONS = {
    "aixterm.config": ["save_config", "create_default_config"],
    "aixterm.mcp_client": ["initialize", "get_available_tools", "call_tool", "shutdown"],
    "aixterm.cleanup": ["run_cleanup", "get_cleanup_status"],
    "aixterm.utils": ["get_logger", "get_current_shell", "format_file_size"],
}


class TestPublicAPIBaseline:
    """Test suite for public API baseline stability."""

    def test_core_modules_importable(self):
        """Test that all core API modules can be imported."""
        failed_imports = []
        
        for module_name in CORE_API_MODULES:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                # Skip modules that require external dependencies not available in test
                if any(dep in str(e) for dep in ["mcp", "openai", "tqdm"]):
                    pytest.skip(f"Skipping {module_name} due to missing test dependency: {e}")
                failed_imports.append((module_name, str(e)))
        
        if failed_imports:
            failures = "\n".join([f"  {mod}: {err}" for mod, err in failed_imports])
            pytest.fail(f"Failed to import core API modules:\n{failures}")

    def test_main_module_exports(self):
        """Test that main module exports critical symbols."""
        try:
            import aixterm
        except ImportError as e:
            if any(dep in str(e) for dep in ["mcp", "openai", "tqdm"]):
                pytest.skip(f"Skipping main module test due to missing dependency: {e}")
            raise

        missing_exports = []
        
        for export_name in MAIN_MODULE_EXPORTS:
            if not hasattr(aixterm, export_name):
                missing_exports.append(export_name)
        
        if missing_exports:
            pytest.fail(f"Main module missing critical exports: {missing_exports}")

    def test_critical_classes_available(self):
        """Test that critical classes remain available."""
        missing_classes = []
        
        for module_name, class_names in CRITICAL_CLASSES.items():
            try:
                module = importlib.import_module(module_name)
            except ImportError as e:
                if any(dep in str(e) for dep in ["mcp", "openai", "tqdm"]):
                    continue  # Skip modules with test dependencies
                missing_classes.append(f"{module_name}: import failed - {e}")
                continue
                
            for class_name in class_names:
                if not hasattr(module, class_name):
                    missing_classes.append(f"{module_name}.{class_name}")
        
        if missing_classes:
            pytest.fail(f"Missing critical classes: {missing_classes}")

    def test_critical_functions_available(self):
        """Test that critical functions remain available."""
        missing_functions = []
        
        for module_name, function_names in CRITICAL_FUNCTIONS.items():
            try:
                module = importlib.import_module(module_name)
            except ImportError as e:
                if any(dep in str(e) for dep in ["mcp", "openai", "tqdm"]):
                    continue  # Skip modules with test dependencies
                missing_functions.append(f"{module_name}: import failed - {e}")
                continue
                
            for function_name in function_names:
                if not hasattr(module, function_name):
                    missing_functions.append(f"{module_name}.{function_name}")
        
        if missing_functions:
            pytest.fail(f"Missing critical functions: {missing_functions}")

    def test_public_api_baseline_file_exists(self):
        """Test that the public API baseline documentation exists."""
        baseline_file = Path("docs/internal/public_api_phase2_baseline.txt")
        assert baseline_file.exists(), "Public API baseline file must exist"
        
        content = baseline_file.read_text()
        assert len(content) > 1000, "Baseline file should contain substantial documentation"
        assert "Phase 2 Public API Baseline" in content, "File should have proper header"

    def test_no_accidental_underscore_exports(self):
        """Test that we don't accidentally export private symbols."""
        try:
            import aixterm
        except ImportError as e:
            if any(dep in str(e) for dep in ["mcp", "openai", "tqdm"]):
                pytest.skip(f"Skipping private symbol test due to missing dependency: {e}")
            raise
            
        if hasattr(aixterm, '__all__'):
            all_exports = aixterm.__all__
            private_exports = [name for name in all_exports if name.startswith('_')]
            
            if private_exports:
                pytest.fail(f"Main module accidentally exports private symbols: {private_exports}")

    def test_api_stability_marker(self):
        """Test for API stability markers in key modules."""
        # This test ensures we maintain version compatibility
        try:
            import aixterm
            assert hasattr(aixterm, '__version__'), "Main module should have version info"
        except ImportError as e:
            if any(dep in str(e) for dep in ["mcp", "openai", "tqdm"]):
                pytest.skip(f"Skipping version test due to missing dependency: {e}")
            raise