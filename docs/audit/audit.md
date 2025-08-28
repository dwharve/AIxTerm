# AIxTerm Repository Audit Report

**Generated:** 2025-08-28 05:56:40  
**Commit:** 8baba208c5e6d6c3f4e57ee4f51466887afcede0  
**Branch:** copilot/fix-eb88a388-ff9b-49c0-b846-3e031df24a76  
**Script:** scripts/generate_audit.py  

<!-- AUDIT_CONTENT_START -->

## Repository Structure

```
.
├── aixterm
│   ├── client
│   ├── context
│   │   └── log_processor
│   ├── display
│   ├── integration
│   ├── llm
│   │   └── client
│   ├── main
│   ├── plugins
│   │   └── devteam
│   │       ├── agents
│   │       ├── modules
│   │       └── plugin
│   └── service
│       └── installer
├── docs
│   ├── audit
│   └── plugins
│       └── devteam
├── scripts
└── tests
    └── llm

24 directories

```

## Language & File Metrics

### Code Statistics (cloc)

```
cloc not available - install with: apt-get install cloc
```

### File Distribution

- **Total Files:** 182
- **Total Size:** 1.4 MB

#### By File Type
- .py: 129 files
- .md: 38 files
- no_extension: 6 files
- .txt: 2 files
- .json: 2 files
- .toml: 1 files
- .ini: 1 files
- .cfg: 1 files
- .in: 1 files
- .typed: 1 files

#### Largest Files
- scripts/generate_audit.py: 44.4 KB
- tests/test_integration.py: 38.8 KB
- aixterm/plugins/devteam/modules/workflow_engine_original.py: 31.0 KB
- aixterm/README.md: 29.7 KB
- tests/test_mcp_progress_notifications.py: 28.6 KB
- ARCHITECTURE.md: 27.6 KB
- aixterm/mcp_client.py: 26.3 KB
- docs/audit/audit.md: 24.3 KB
- aixterm/config.py: 23.6 KB
- tests/test_task_manager_characterization.py: 23.3 KB

## Dependency Inventory

### requirements.txt
- aiohttp
- requests
- tiktoken

### requirements-dev.txt
- bandit
- black
- build
- flake8
- isort
- keyring
- mypy
- pre-commit
- pytest
- pytest-asyncio
- pytest-cov
- pytest-mock
- requests
- tiktoken
- twine
- types-requests

### pyproject.toml
- bandit
- black
- flake8
- isort
- mcp
- mypy
- openai
- pre-commit
- pytest
- pytest-asyncio
- pytest-cov
- pytest-mock
- requests
- tiktoken
- tqdm
- types-requests

### setup.py
- black
- flake8
- mypy
- pytest
- pytest-asyncio
- pytest-cov
- pytest-mock

## Tooling & Automation Inventory

### Makefile Targets
- all
- audit-baseline
- build
- build-sdist
- build-wheel
- check-package
- ci
- clean
- deb
- deb-native
- deb-python
- deb-windows
- fix
- format
- format-check
- help
- import-check
- import-sort
- info
- install

### CI/CD Workflows
No GitHub workflows found.

## Configuration Discovery

### Env Vars
- aixterm/__main__.py (1 occurrences)
- aixterm/client/client.py (7 occurrences)
- aixterm/config.py (3 occurrences)
- aixterm/context/log_processor/processor.py (2 occurrences)
- aixterm/display/status.py (2 occurrences)
- aixterm/integration/zsh.py (1 occurrences)
- aixterm/main/cli.py (1 occurrences)
- aixterm/mcp_client.py (8 occurrences)
- aixterm/runtime_paths.py (1 occurrences)
- aixterm/service/service.py (5 occurrences)

### Config Files
- aixterm/__init__.py (1 occurrences)
- aixterm/cleanup.py (15 occurrences)
- aixterm/client/client.py (2 occurrences)
- aixterm/context/directory_handler.py (9 occurrences)
- aixterm/context/log_processor/processor.py (3 occurrences)
- aixterm/context/terminal_context.py (11 occurrences)
- aixterm/context/token_manager.py (11 occurrences)
- aixterm/context/tool_optimizer.py (5 occurrences)
- aixterm/integration/fish.py (11 occurrences)
- aixterm/llm/client/__init__.py (15 occurrences)

### Settings
- aixterm/__init__.py (1 occurrences)
- aixterm/cleanup.py (16 occurrences)
- aixterm/client/client.py (3 occurrences)
- aixterm/config.py (89 occurrences)
- aixterm/context/directory_handler.py (3 occurrences)
- aixterm/context/log_processor/processor.py (4 occurrences)
- aixterm/context/terminal_context.py (12 occurrences)
- aixterm/context/token_manager.py (15 occurrences)
- aixterm/context/tool_optimizer.py (6 occurrences)
- aixterm/display/status.py (1 occurrences)

### Environment Variable Names

| Env Var | Files | Occurrence Count |
|---------|-------|------------------|
| AIXTERM_LOG_LEVEL | aixterm/utils.py, aixterm/main/cli.py | 3 |
| AIXTERM_RUNTIME_HOME | aixterm/runtime_paths.py | 2 |
| AIXTERM_SHOW_TIMING | aixterm/display/status.py | 1 |
| AIXTERM_TEST_IDLE_GRACE | aixterm/service/service.py | 1 |
| AIXTERM_TEST_IDLE_LIMIT | aixterm/service/service.py | 1 |
| PYTEST_CURRENT_TEST | aixterm/service/service.py | 2 |
| SHELL | aixterm/utils.py | 2 |
| X | scripts/generate_audit.py | 5 |
| _AIXTERM_LOG_FILE | aixterm/context/log_processor/processor.py | 2 |

## Logging Patterns

### Custom Loggers
- aixterm/cleanup.py (1 occurrences)
- aixterm/client/client.py (1 occurrences)
- aixterm/config.py (1 occurrences)
- aixterm/context/terminal_context.py (1 occurrences)
- aixterm/display/content.py (1 occurrences)
- aixterm/display/manager.py (1 occurrences)
- aixterm/display/progress.py (1 occurrences)
- aixterm/display/status.py (1 occurrences)
- aixterm/display/terminal.py (1 occurrences)
- aixterm/integration/base.py (1 occurrences)

### Logger Instances
- aixterm/client/client.py (1 occurrences)
- aixterm/main/cli.py (2 occurrences)
- aixterm/plugins/base.py (2 occurrences)
- aixterm/plugins/cli.py (1 occurrences)
- aixterm/plugins/devteam/adaptive.py (1 occurrences)
- aixterm/plugins/devteam/agents/__init__.py (3 occurrences)
- aixterm/plugins/devteam/agents/code_analyst.py (1 occurrences)
- aixterm/plugins/devteam/agents/developer.py (1 occurrences)
- aixterm/plugins/devteam/agents/qa_tester.py (1 occurrences)
- aixterm/plugins/devteam/cli.py (1 occurrences)

### Python Logging
- aixterm/cleanup.py (19 occurrences)
- aixterm/client/client.py (8 occurrences)
- aixterm/config.py (8 occurrences)
- aixterm/context/directory_handler.py (11 occurrences)
- aixterm/context/log_processor/processor.py (10 occurrences)
- aixterm/context/terminal_context.py (18 occurrences)
- aixterm/context/token_manager.py (3 occurrences)
- aixterm/context/tool_optimizer.py (11 occurrences)
- aixterm/display/content.py (3 occurrences)
- aixterm/display/manager.py (7 occurrences)

### Print Statements
- aixterm/client/client.py (2 occurrences)
- aixterm/display/content.py (10 occurrences)
- aixterm/display/manager.py (1 occurrences)
- aixterm/display/status.py (2 occurrences)
- aixterm/integration/base.py (17 occurrences)
- aixterm/llm/client/__init__.py (4 occurrences)
- aixterm/main/cli.py (41 occurrences)
- aixterm/plugins/cli.py (29 occurrences)
- aixterm/plugins/devteam/agents/developer.py (1 occurrences)
- aixterm/plugins/devteam/cli.py (75 occurrences)

### Module Loggers
- scripts/generate_audit.py (1 occurrences)

## Error Handling Patterns

### Try Except
- aixterm/cleanup.py (8 occurrences)
- aixterm/client/client.py (17 occurrences)
- aixterm/config.py (15 occurrences)
- aixterm/context/directory_handler.py (6 occurrences)
- aixterm/context/log_processor/processor.py (7 occurrences)
- aixterm/context/log_processor/tokenization.py (4 occurrences)
- aixterm/context/log_processor/tty_utils.py (5 occurrences)
- aixterm/context/terminal_context.py (11 occurrences)
- aixterm/context/token_manager.py (6 occurrences)
- aixterm/context/tool_optimizer.py (2 occurrences)

### Result Wrappers
- aixterm/cleanup.py (2 occurrences)
- aixterm/client/client.py (4 occurrences)
- aixterm/config.py (2 occurrences)
- aixterm/context/log_processor/processor.py (13 occurrences)
- aixterm/context/log_processor/tokenization.py (5 occurrences)
- aixterm/context/log_processor/tty_utils.py (2 occurrences)
- aixterm/context/terminal_context.py (2 occurrences)
- aixterm/context/token_manager.py (3 occurrences)
- aixterm/context/tool_optimizer.py (2 occurrences)
- aixterm/display/content.py (1 occurrences)

### Raise Statements
- aixterm/client/client.py (1 occurrences)
- aixterm/context/token_manager.py (1 occurrences)
- aixterm/llm/client/__init__.py (4 occurrences)
- aixterm/llm/client/streaming.py (2 occurrences)
- aixterm/llm/tools.py (3 occurrences)
- aixterm/mcp_client.py (14 occurrences)
- aixterm/plugins/base.py (3 occurrences)
- aixterm/plugins/devteam/modules/events.py (2 occurrences)
- aixterm/plugins/devteam/modules/workflow_engine_modules/models.py (1 occurrences)
- aixterm/plugins/devteam/modules/workflow_engine_modules/step_types.py (1 occurrences)

### Error Classes
- aixterm/client/client.py (1 occurrences)
- aixterm/context/token_manager.py (1 occurrences)
- aixterm/llm/client/__init__.py (4 occurrences)
- aixterm/llm/client/streaming.py (2 occurrences)
- aixterm/llm/exceptions.py (1 occurrences)
- aixterm/mcp_client.py (13 occurrences)
- aixterm/plugins/base.py (3 occurrences)
- aixterm/plugins/devteam/modules/events.py (2 occurrences)
- aixterm/plugins/devteam/modules/workflow_engine_modules/step_types.py (1 occurrences)
- aixterm/plugins/devteam/modules/workflow_engine_original.py (1 occurrences)

## Async/Concurrency Patterns

### Multiprocessing
- aixterm/plugins/devteam/agents/developer.py (1 occurrences)
- aixterm/utils.py (1 occurrences)
- tests/test_mcp_progress_notifications.py (2 occurrences)

### Async Functions
- aixterm/llm/client/__init__.py (1 occurrences)
- aixterm/mcp_client.py (6 occurrences)
- aixterm/plugins/devteam/adaptive.py (9 occurrences)
- aixterm/plugins/devteam/agents/__init__.py (1 occurrences)
- aixterm/plugins/devteam/agents/code_analyst.py (3 occurrences)
- aixterm/plugins/devteam/agents/developer.py (5 occurrences)
- aixterm/plugins/devteam/agents/project_manager.py (1 occurrences)
- aixterm/plugins/devteam/agents/qa_tester.py (5 occurrences)
- aixterm/plugins/devteam/modules/events.py (1 occurrences)
- aixterm/plugins/devteam/modules/workflow_engine_modules/executor.py (2 occurrences)

### Await Calls
- aixterm/llm/client/__init__.py (1 occurrences)
- aixterm/mcp_client.py (10 occurrences)
- aixterm/plugins/devteam/adaptive.py (4 occurrences)
- aixterm/plugins/devteam/agents/code_analyst.py (2 occurrences)
- aixterm/plugins/devteam/agents/developer.py (4 occurrences)
- aixterm/plugins/devteam/agents/qa_tester.py (4 occurrences)
- aixterm/plugins/devteam/modules/events.py (2 occurrences)
- aixterm/plugins/devteam/modules/workflow_engine_modules/executor.py (2 occurrences)
- aixterm/plugins/devteam/modules/workflow_engine_modules/models.py (1 occurrences)
- aixterm/plugins/devteam/modules/workflow_engine_modules/step_types.py (1 occurrences)

### Callbacks
- aixterm/llm/client/__init__.py (19 occurrences)
- aixterm/llm/client/base.py (5 occurrences)
- aixterm/llm/tools.py (14 occurrences)
- aixterm/main/app.py (8 occurrences)
- aixterm/mcp_client.py (66 occurrences)
- aixterm/plugins/devteam/plugin/core.py (2 occurrences)
- aixterm/service/server.py (4 occurrences)
- scripts/generate_audit.py (2 occurrences)
- tests/test_llm.py (2 occurrences)
- tests/test_mcp_progress_notifications.py (116 occurrences)

### Threading
- aixterm/display/manager.py (1 occurrences)
- aixterm/display/progress.py (1 occurrences)
- aixterm/llm/client/progress.py (2 occurrences)
- aixterm/llm/streaming.py (2 occurrences)
- aixterm/mcp_client.py (4 occurrences)
- tests/test_runtime_paths_autostart.py (4 occurrences)

## Code Annotations

| File | Line | Type | Description |
|------|------|------|-------------|
| aixterm/plugins/devteam/plugin/core.py | 317 | DEPRECATED | when no loop running. |
| scripts/generate_audit.py | 717 | DEPRECATED | ', 'LEGACY'] else "Inconsistency", |
| aixterm/plugins/devteam/README.md | 15 | LEGACY | ) |
| README.md | 85 | NOTE | **: AIxTerm provides two command aliases after installation: |
| aixterm/context/terminal_context.py | 318 | NOTE | This is a fallback when shell integration is not available. |
| aixterm/llm/client/requests.py | 230 | NOTE | ": "Streaming response not captured in debug"} |
| aixterm/main/cli.py | 384 | NOTE | ", "Streaming response")) |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 95 | NOTE | Optional[str] = None |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 103 | NOTE | Optional note to add |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 115 | NOTE |  |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 116 | NOTE | , "system") |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 263 | NOTE | str, author: str = "system" |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 266 | NOTE | to a task. |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 270 | NOTE | Note content |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 271 | NOTE | (default: "system") |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 280 | NOTE | , author) |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 282 | NOTE | added event |
| aixterm/plugins/devteam/modules/task_manager_modules/manager.py | 288 | NOTE | , "author": author}, |
| aixterm/plugins/devteam/modules/task_manager_modules/models.py | 194 | NOTE | str, author: str = "system") -> None: |
| aixterm/plugins/devteam/modules/task_manager_modules/models.py | 196 | NOTE | to the task. |
| aixterm/plugins/devteam/modules/task_manager_modules/models.py | 199 | NOTE | Note content |
| aixterm/plugins/devteam/modules/task_manager_modules/models.py | 200 | NOTE | (default: "system") |
| aixterm/plugins/devteam/modules/task_manager_modules/models.py | 203 | NOTE | , "author": author, "timestamp": datetime.now().isoformat()} |
| aixterm/plugins/devteam/modules/task_manager_original.py | 204 | NOTE | str, author: str = "system") -> None: |
| aixterm/plugins/devteam/modules/task_manager_original.py | 206 | NOTE | to the task. |
| aixterm/plugins/devteam/modules/task_manager_original.py | 209 | NOTE | Note content |
| aixterm/plugins/devteam/modules/task_manager_original.py | 210 | NOTE | (default: "system") |
| aixterm/plugins/devteam/modules/task_manager_original.py | 213 | NOTE | , "author": author, "timestamp": datetime.now().isoformat()} |
| aixterm/plugins/devteam/modules/task_manager_original.py | 307 | NOTE | Optional[str] = None |
| aixterm/plugins/devteam/modules/task_manager_original.py | 315 | NOTE | Optional note to add to the task |

## Commented-Out Code Blocks

No large commented-out code blocks detected.

## Potential Duplication Candidates

**Summary:** 159 distinct function duplication candidates, 1 distinct dunder method patterns.

### Function Duplication Table

*Showing top 20 of 159 total candidates*

| Function Name | File Count | File Paths |
|---------------|------------|------------|
| name | 10 | aixterm/plugins/devteam/agents/__init__.py, tests/test_plugin_service.py, aixterm/plugins/devteam/agents/developer.py, aixterm/plugins/devteam/agents/project_manager.py, aixterm/plugins/base.py, aixterm/plugins/devteam/plugin/core.py, tests/test_plugins.py, aixterm/plugins/devteam/agents/code_analyst.py ... (2 more) |
| shutdown | 9 | aixterm/llm/client/base.py, aixterm/plugins/devteam/agents/__init__.py, aixterm/display/manager.py, aixterm/main/__init__.py, aixterm/context/terminal_context.py, aixterm/plugins/base.py, aixterm/mcp_client.py, aixterm/cleanup.py ... (1 more) |
| status | 8 | aixterm/service/installer/common.py, aixterm/service/installer/linux.py, aixterm/service/service.py, aixterm/service/installer/macos.py, aixterm/main/__init__.py, aixterm/plugins/base.py, aixterm/service/installer/windows.py, aixterm/client/client.py |
| to_dict | 8 | aixterm/plugins/devteam/workflow.py, aixterm/plugins/devteam/modules/events.py, aixterm/plugins/devteam/modules/workflow_engine_modules/models.py, aixterm/plugins/devteam/modules/workflow_engine_modules/step_types.py, aixterm/plugins/devteam/modules/workflow_engine_original.py, aixterm/plugins/devteam/modules/task_manager_original.py, aixterm/plugins/devteam/modules/task_manager_modules/models.py, aixterm/plugins/devteam/adaptive.py |
| description | 7 | aixterm/plugins/devteam/agents/__init__.py, aixterm/plugins/devteam/agents/developer.py, aixterm/plugins/devteam/agents/project_manager.py, aixterm/plugins/base.py, aixterm/plugins/devteam/plugin/core.py, aixterm/plugins/devteam/agents/code_analyst.py, aixterm/plugins/devteam/agents/qa_tester.py |
| install | 6 | aixterm/service/installer/common.py, aixterm/service/installer/linux.py, aixterm/service/installer/macos.py, aixterm/integration/fish.py, aixterm/service/installer/windows.py, aixterm/integration/base.py |
| agent_type | 6 | aixterm/plugins/devteam/agents/__init__.py, aixterm/plugins/devteam/agents/developer.py, aixterm/plugins/devteam/agents/project_manager.py, aixterm/plugins/devteam/agents/code_analyst.py, aixterm/plugins/devteam/agents/qa_tester.py, tests/test_devteam_agents.py |
| process_task | 6 | aixterm/plugins/devteam/agents/__init__.py, aixterm/plugins/devteam/agents/developer.py, aixterm/plugins/devteam/agents/project_manager.py, aixterm/plugins/devteam/agents/code_analyst.py, aixterm/plugins/devteam/agents/qa_tester.py, tests/test_devteam_agents.py |
| from_dict | 6 | aixterm/plugins/devteam/modules/events.py, aixterm/plugins/devteam/modules/workflow_engine_modules/models.py, aixterm/plugins/devteam/modules/workflow_engine_modules/step_types.py, aixterm/plugins/devteam/modules/workflow_engine_original.py, aixterm/plugins/devteam/modules/task_manager_original.py, aixterm/plugins/devteam/modules/task_manager_modules/models.py |
| initialize | 5 | aixterm/plugins/devteam/agents/__init__.py, aixterm/plugins/devteam/plugin/core.py, aixterm/plugins/base.py, aixterm/mcp_client.py, aixterm/plugins/devteam/adaptive.py |
| debug | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |
| info | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |
| warning | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |
| error | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |
| shell_name | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |
| config_files | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |
| generate_integration_code | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |
| is_available | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |
| validate_integration_environment | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |
| get_installation_notes | 5 | aixterm/integration/fish.py, tests/test_shell_integration.py, aixterm/integration/zsh.py, aixterm/integration/bash.py, aixterm/integration/base.py |

### Dunder Methods Summary

| Method Name | File Count | File Paths |
|-------------|------------|------------|
| __init__ | 62 | tests/test_devteam_workflow.py, aixterm/plugins/devteam/workflow.py, aixterm/plugins/devteam/agents/__init__.py, aixterm/main/__init__.py, aixterm/plugins/devteam/modules/workflow_engine_modules/step_types.py ... (57 more) |


## Test Coverage Surface Mapping

### Test Files (32)
- aixterm/plugins/devteam/agents/qa_tester.py
- pytest.ini
- tests/__init__.py
- tests/conftest.py
- tests/llm/__init__.py
- tests/llm/test_context_module.py
- tests/test_adaptive_learning.py
- tests/test_cleanup.py
- tests/test_config.py
- tests/test_context.py
- tests/test_context_modular.py
- tests/test_devteam_agents.py
- tests/test_devteam_plugin.py
- tests/test_devteam_workflow.py
- tests/test_display_modular.py

### Source Directories (2)
- aixterm/
- scripts/

### Test to Source Mapping
- tests/llm/test_context_module.py -> context_module
- tests/test_adaptive_learning.py -> adaptive_learning
- tests/test_cleanup.py -> cleanup
- tests/test_config.py -> config
- tests/test_context.py -> context
- tests/test_context_modular.py -> context_modular
- tests/test_devteam_agents.py -> devteam_agents
- tests/test_devteam_plugin.py -> devteam_plugin
- tests/test_devteam_workflow.py -> devteam_workflow
- tests/test_display_modular.py -> display_modular

## Build & CI Quality Gates

- quality-check (format-check, lint, type-check, import-check, security-check)
- test (pytest)
- ci (test + quality-check)

## Risk & Maintenance Hotspots

- Large file: scripts/generate_audit.py (45466 bytes)
- Large file: tests/test_integration.py (39715 bytes)
- Large file: aixterm/plugins/devteam/modules/workflow_engine_original.py (31696 bytes)
- Large file: aixterm/README.md (30441 bytes)
- Large file: tests/test_mcp_progress_notifications.py (29244 bytes)
- Large file: ARCHITECTURE.md (28247 bytes)
- Large file: aixterm/mcp_client.py (26963 bytes)
- Large file: docs/audit/audit.md (24850 bytes)
- Large file: aixterm/config.py (24157 bytes)
- Large file: tests/test_task_manager_characterization.py (23810 bytes)
- High annotation count: aixterm/plugins/devteam/modules/task_manager_original.py (15 TODOs/FIXMEs)
- High annotation count: aixterm/plugins/devteam/modules/task_manager_modules/manager.py (11 TODOs/FIXMEs)
- High annotation count: tests/test_task_manager_characterization.py (9 TODOs/FIXMEs)
- High annotation count: aixterm/plugins/devteam/modules/task_manager_modules/models.py (5 TODOs/FIXMEs)
- High annotation count: scripts/generate_audit.py (5 TODOs/FIXMEs)
- Complex module: aixterm/config.py (650 lines, 1 classes, 24 functions)
- Complex module: aixterm/mcp_client.py (751 lines, 5 classes, 27 functions)
- Complex module: aixterm/plugins/devteam/modules/task_manager_original.py (649 lines, 2 classes, 28 functions)
- Complex module: aixterm/plugins/devteam/modules/workflow_engine_original.py (943 lines, 6 classes, 21 functions)
- Complex module: scripts/generate_audit.py (1112 lines, 1 classes, 23 functions)
- Complex module: tests/test_task_manager_characterization.py (629 lines, 1 classes, 21 functions)
- Complex module: tests/test_integration.py (953 lines, 6 classes, 38 functions)
- Complex module: tests/test_context.py (513 lines, 5 classes, 33 functions)
- Complex module: tests/test_mcp_progress_notifications.py (831 lines, 5 classes, 54 functions)

## Phase 1 Findings

| ID | Category | Evidence | Impact | Effort | Recommended Action |
|----|----------|----------|--------|--------|-----------------|
| F001 | Inconsistency | 55 NOTE annotations across codebase | Med | M | Review and address NOTE annotations systematically |
| F002 | Duplication | 20 potentially duplicated function names | Med | L | Review and consolidate duplicate functions |

## Methodology

This audit was generated using the following commands and techniques:

### Data Collection
- `git rev-parse HEAD` - Get current commit hash
- `git rev-parse --abbrev-ref HEAD` - Get current branch
- `tree -d -L 4` or `find . -type d` - Repository structure
- `cloc . --exclude-dir=...` - Code metrics (if available)
- `os.walk()` - File system traversal and analysis
- `re.findall()` - Pattern matching for code analysis

### Analysis Patterns
- **Code Annotations:** `\b(TODO|FIXME|HACK|DEPRECATED|LEGACY|XXX|NOTE)\b`
- **Function Definitions:** `def\s+(\w+)\s*\(`, `function\s+(\w+)\s*\(`
- **Logging:** `console\.(log|error|warn)`, `log(?:ger)?\.(debug|info|warn)`
- **Error Handling:** `\btry\s*:.*?except\b`, `\braise\b`
- **Async Patterns:** `\basync\s+def\b`, `\bawait\b`
- **Configuration:** `\b(?:os\.environ|getenv|ENV)\b`

### File Analysis
- Extensions analyzed: {', '.join(sorted(self.code_extensions))}
- Directories excluded: {', '.join(sorted(self.exclude_dirs))}
- Encoding: UTF-8 with error handling
- Large file threshold: >20KB or >500 lines
- Comment block threshold: >5 consecutive lines

### Limitations
- Static analysis only (no runtime instrumentation)
- Pattern-based detection (may have false positives/negatives)
- Limited to text-based analysis
- Heuristic-based duplication detection
- Manual review recommended for all findings

<!-- AUDIT_CONTENT_END -->
