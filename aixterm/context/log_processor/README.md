# Log Processor Module

This directory contains the fully modularized components of the log processor. The original monolithic implementation has been refactored into specialized modules with clearly defined responsibilities.

## Module Structure

The log processor is divided into these modules:

### 1. `processor.py`

The main LogProcessor class that handles:
- Finding appropriate log files based on TTY identification
- Managing TTY-specific logs with proper isolation
- Reading and processing log content with intelligent summarization
- Generating context from logs with token optimization
- Validating log files and TTY matching
- Managing log file sizes and cleanup

### 2. `tty_utils.py`

TTY utilities for log file management:
- TTY detection
- Active TTY identification
- Extracting TTY information from log paths

### 3. `parsing.py`

Log content parsing functions:
- Extracting commands and outputs from logs
- Identifying error messages
- Extracting conversation history

### 4. `tokenization.py`

Text tokenization and truncation:
- Tokenizing text content
- Managing token limits
- Reading and truncating log files

### 5. `summary.py`

Building useful summaries from command history:
- Generating tiered summaries based on recency
- Abbreviating command outputs
- Organizing context into sections

## Usage

The system is designed to be used through the main LogProcessor class, which integrates all the specialized modules:

```python
# Import from the new modular structure
from aixterm.context.log_processor.processor import LogProcessor
from aixterm.context.log_processor.parsing import extract_commands_from_log

# Create log processor
log_processor = LogProcessor(config, logger)

# Get session context
context = log_processor.get_session_context()

# Get conversation history
messages = log_processor.get_conversation_history(max_tokens=1000)

# Process log content with intelligent summarization
log_content = log_processor.read_and_process_log(log_path, max_tokens=2000, smart_summarize=True)
```

For importing from the package level:

```python
from aixterm.context import LogProcessor
from aixterm.context import extract_commands_from_log, extract_conversation_from_log
```

The backward compatibility layer has been completely removed, and all references have been updated to use the new modular implementation directly.
