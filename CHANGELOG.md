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
