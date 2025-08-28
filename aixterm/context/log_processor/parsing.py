"""Log parsing utilities for extracting commands and conversations."""

from typing import Any, Dict, List, Tuple


def extract_commands_from_log(
    log_content: str,
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Extract commands and their outputs from log content.

    Args:
        log_content: Raw log content string

    Returns:
        Tuple of (list of (command, output) tuples, list of error messages)
    """
    lines = log_content.split("\n")
    commands = []
    errors = []
    current_command = None
    current_output: list[str] = []

    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue

        # Handle both traditional format ($ command) and
        # script format (└──╼ $command)
        command_match = None
        if clean_line.startswith("$ "):
            command_match = clean_line[2:]  # Remove '$ '
        elif "└──╼ $" in clean_line:
            # Extract command from script format: └──╼ $command
            dollar_pos = clean_line.find("└──╼ $")
            if dollar_pos != -1:
                command_match = clean_line[dollar_pos + 6 :]  # Remove '└──╼ $'

        if command_match:
            # Save previous command and output
            if current_command and current_output:
                commands.append((current_command, "\n".join(current_output)))

            current_command = command_match
            current_output = []
        else:
            if "error" in line.lower() or "failed" in line.lower():
                errors.append(line)
            current_output.append(line)

    # Save last command
    if current_command and current_output:
        commands.append((current_command, "\n".join(current_output)))

    return commands, errors


def extract_conversation_from_log(log_content: str) -> List[Dict[str, Any]]:
    """Extract conversation messages from log content.

    Args:
        log_content: Raw log content string

    Returns:
        List of conversation messages in ChatCompletion format
    """
    lines = log_content.split("\n")
    messages = []

    current_ai_response: list[str] = []
    collecting_response = False

    for line in lines:
        clean_line = line.strip()
        if not clean_line:
            continue

        # Detect AI assistant queries (ai or aixterm commands)
        # Handle both traditional format ($ command) and
        # script format (└──╼ $command)
        ai_command_match = None
        if clean_line.startswith("$ ai ") or clean_line.startswith("$ aixterm "):
            ai_command_match = clean_line
        elif "└──╼ $ai " in clean_line or "└──╼ $aixterm " in clean_line:
            # Extract command from script format
            dollar_pos = clean_line.find("└──╼ $")
            if dollar_pos != -1:
                ai_command_match = (
                    "$" + clean_line[dollar_pos + 6 :]
                )  # Convert to standard format

        # Also support fallback logging format used by TerminalContext:
        # "$ User: <query>" followed later by "$ Assistant: <response>"
        if clean_line.startswith("$ User:"):
            # Save any ongoing AI response first
            if current_ai_response and collecting_response:
                ai_content = "\n".join(current_ai_response).strip()
                if ai_content:
                    messages.append({"role": "assistant", "content": ai_content})
                current_ai_response = []
                collecting_response = False

            # Extract the user query after the colon
            query_part = clean_line.split(":", 1)[1].strip()
            if query_part:
                messages.append({"role": "user", "content": query_part})
                collecting_response = True
            continue

        if clean_line.startswith("$ Assistant:"):
            # Assistant response in single line (fallback format)
            resp_part = clean_line.split(":", 1)[1].strip()
            if resp_part:
                messages.append({"role": "assistant", "content": resp_part})
                current_ai_response = []
                collecting_response = False
            continue

        if ai_command_match:
            # Save any ongoing AI response first
            if current_ai_response and collecting_response:
                ai_content = "\n".join(current_ai_response).strip()
                if ai_content:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": ai_content,
                        }
                    )
                current_ai_response = []
                collecting_response = False

            # Extract and save the user query
            if ai_command_match.startswith("$ ai "):
                query_part = ai_command_match[5:].strip()  # Remove "$ ai "
            elif ai_command_match.startswith("$ aixterm "):
                query_part = ai_command_match[9:].strip()  # Remove "$ aixterm "
            else:
                # Handle script format
                if "$ai " in ai_command_match:
                    query_part = ai_command_match.split("$ai ", 1)[1].strip()
                else:
                    query_part = ai_command_match.split("$aixterm ", 1)[1].strip()

            # Add user message
            if query_part:
                # Remove quotes that might have been added by shell
                if (
                    (query_part.startswith("'") and query_part.endswith("'"))
                    or (query_part.startswith('"') and query_part.endswith('"'))
                ) and len(query_part) > 2:
                    query_part = query_part[1:-1]

                messages.append(
                    {
                        "role": "user",
                        "content": query_part,
                    }
                )
                collecting_response = True

        elif collecting_response:
            # Skip lines that are likely prompt markers
            if clean_line in (
                "Thinking...",
                "Working on it...",
                "Thinking about your query...",
            ):
                continue

            # Skip this type of marker but consider it the start of an AI response
            if clean_line.startswith("[1;36m") or clean_line.startswith("\x1b[1;36m"):
                continue

            # This is a continuation of the AI's response
            current_ai_response.append(line)

    # Save the final AI response if there is one
    if current_ai_response and collecting_response:
        ai_content = "\n".join(current_ai_response).strip()
        if ai_content:
            messages.append(
                {
                    "role": "assistant",
                    "content": ai_content,
                }
            )

    return messages
