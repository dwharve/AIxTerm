# Changelog

All notable changes to AIxTerm will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Completed fully modular log processor implementation
  - New specialized modules: processor.py, parsing.py, tokenization.py, tty_utils.py, summary.py
  - Improved TTY detection across all platforms
  - Advanced intelligent summarization of terminal history
  - Enhanced command extraction and token management
  - Fully compatible API with existing integration points

### Changed
- Updated documentation to reflect modular context architecture
- Improved terminal_context.py documentation and class structure
- Enhanced code quality with proper type hints and docstrings

### Fixed
- Resolved backward compatibility issues in the context module
- Fixed error handling in TTY validation logic
- Improved token counting accuracy in log processing

## [0.2.1] - 2025-08-26

### Added
- Test-mode automatic idle shutdown for background service to prevent orphaned processes during pytest runs
- Environment variable controls:
  - `AIXTERM_TEST_IDLE_LIMIT` (seconds, bounded) to configure idle timeout window
  - `AIXTERM_TEST_IDLE_GRACE` startup grace period to avoid premature shutdown before first client request
  - `AIXTERM_RUNTIME_HOME` to isolate runtime directory (socket, lock, logs) across subprocess boundary in tests
- Idle shutdown validation test (`test_service_idle_shutdown.py`) ensuring autostart → activity → idle termination → re-autostart sequence

### Changed
- Client autostart now propagates the above test environment variables to the service subprocess
- Runtime path resolution honors `AIXTERM_RUNTIME_HOME` before falling back to user home directory

### Fixed
- Eliminated lingering background service processes after test suite completion by enforcing deterministic idle exit in test environments
- Race conditions around early idle shutdown mitigated via explicit grace period and `last_activity` reset post-start

### Internal
- Added granular environment forwarding loop in client for test-focused variables
- Stabilized test isolation for service lifecycle bringing total passing tests to 291/291

## [0.2.0] - 2025-08-26

### Changed
- Adopted new canonical TTY log layout: `~/.aixterm/tty/{pts-N.log,default.log}` with deterministic discovery
- Updated log resolution precedence: `_AIXTERM_LOG_FILE` (scoped to current home) > active TTY log > `default.log` > newest log fallback
- Refactored `LogProcessor` for clearer separation of listing vs. filtered TTY views
- Documentation (README, ARCHITECTURE) updated to remove legacy examples

### Removed
- All legacy `.aixterm_log.*` filename pattern handling and dual-write compatibility code
- Legacy sed-based filename normalization in shell integration scripts (bash/zsh/fish)

### Fixed
- Eliminated cross-session log leakage by restricting `_AIXTERM_LOG_FILE` to the active (possibly monkeypatched) home directory
- Stabilized test isolation for TTY-specific selection across 290-test suite

### Internal
- Deterministic sorting of log files for reproducible selection in tests
- Triple verification runs: 290/290 tests passing post-refactor

## [0.1.4] - 2025-07-05

### Changed
- Full shell logging is now the default behavior (no longer experimental)
- Improved shell integration with automatic command output capture
- Streamlined logging functions for better performance

### Removed
- Experimental flags and warnings for full output logging
- Separate "full logging" functions - now integrated into default behavior

## [0.1.3] - 2025-06-30

### Changed
- Updated project metadata and author information
- Minor version bump for consistency

## [0.1.2] - 2025-06-30

### Changed
- Updated project documentation and README accuracy
- Improved project structure documentation
- Enhanced installation instructions with command aliases
- Version bump for documentation improvements

### Fixed
- Corrected test count documentation (145 tests vs previously claimed 160)
- Updated project structure to reflect actual codebase

## [0.1.1] - 2025-06-30

### Added
- Initial stable release
- MCP server integration
- Terminal context management
- HTTP server mode
- Comprehensive test suite (145 tests)

### Features
- Natural language command interface
- Cross-platform support
- Configuration management
- Automatic cleanup functionality
