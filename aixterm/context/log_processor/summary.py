"""Building summaries from command history."""

from typing import List, Tuple


def build_tiered_summary(
    commands: List[Tuple[str, str]], errors: List[str]
) -> List[str]:
    """Build tiered summary with different detail levels based on recency.

    Args:
        commands: List of (command, output) tuples
        errors: List of error messages

    Returns:
        List of summary parts
    """
    summary_parts = []
    total_commands = len(commands)

    if total_commands == 0:
        return ["No commands executed in this session."]

    # Calculate tier boundaries
    recent_count = max(1, int(total_commands * 0.2))  # Last 20% (min 1)
    middle_count = max(1, int(total_commands * 0.3))  # Next 30% (min 1)

    # Split commands into tiers
    recent_commands = commands[-recent_count:]
    middle_commands = commands[-(recent_count + middle_count) : -recent_count]
    older_commands = commands[: -(recent_count + middle_count)]

    # Process recent commands (full detail)
    if recent_commands:
        summary_parts.append(f"\n--- Most Recent Commands ({len(recent_commands)}) ---")
        for cmd, output in recent_commands:
            # Limit output to a reasonable size
            abbreviated_output = abbreviate_output(output)
            summary_parts.append(f"$ {cmd}")
            summary_parts.append(abbreviated_output)
            summary_parts.append("")  # Empty line for separation

    # Process middle commands (command only)
    if middle_commands:
        summary_parts.append(f"\n--- Previous Commands ({len(middle_commands)}) ---")
        for cmd, _ in middle_commands:
            summary_parts.append(f"$ {cmd}")

    # Process older commands (just count them)
    if older_commands:
        summary_parts.append(
            f"\n--- Older Session History: {len(older_commands)} earlier commands ---"
        )

    # Add error summary if any errors
    if errors:
        summary_parts.append("\n--- Errors Detected ---")
        for error in errors[:5]:  # Limit to 5 errors
            summary_parts.append(error)
        if len(errors) > 5:
            summary_parts.append(f"... and {len(errors) - 5} more errors")

    return summary_parts


def abbreviate_output(output: str, max_lines: int = 10, max_length: int = 500) -> str:
    """Abbreviate command output to keep summary concise.

    Args:
        output: Command output
        max_lines: Maximum number of lines to include
        max_length: Maximum overall length

    Returns:
        Abbreviated output
    """
    lines = output.split("\n")
    if len(lines) <= max_lines and len(output) <= max_length:
        return output

    # Truncate lines
    if len(lines) > max_lines:
        half = max(1, max_lines // 2)
        selected_lines = lines[:half] + ["..."] + lines[-half:]
        output = "\n".join(selected_lines)

    # Truncate length
    if len(output) > max_length:
        half = max(50, max_length // 2)
        output = output[:half] + "..." + output[-half:]

    return output
