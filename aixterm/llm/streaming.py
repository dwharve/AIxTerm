"""Streaming response handling for LLM requests."""

import json
from typing import Any, Dict, List, Optional, Tuple

import requests


class StreamingHandler:
    """Handles streaming responses from LLM APIs."""

    def __init__(self, config_manager: Any, logger: Any):
        """Initialize streaming handler.

        Args:
            config_manager: Configuration manager instance
            logger: Logger instance
        """
        self.config = config_manager
        self.logger = logger

    def handle_streaming_response(self, response: requests.Response) -> str:
        """Handle streaming response from LLM.

        Args:
            response: Streaming response object

        Returns:
            Complete response text
        """
        full_response = ""
        # print("\n--- AI Response ---")

        try:
            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8").strip()

                    # Skip empty lines and completion marker
                    if not line_str or line_str == "data: [DONE]":
                        continue

                    if line_str.startswith("data: "):
                        line_str = line_str[6:]  # Remove "data: " prefix

                    try:
                        data = json.loads(line_str)

                        # Handle tool calls
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})

                        if "tool_calls" in delta:
                            # Handle tool calls in streaming mode
                            tool_calls = delta["tool_calls"]
                            for tool_call in tool_calls:
                                function_name = tool_call.get("function", {}).get(
                                    "name", "unknown"
                                )
                                print(f"[Tool Call: {function_name}]")
                                self.handle_tool_call(tool_call)

                        content = delta.get("content", "")
                        if content:
                            print(content, end="", flush=True)
                            full_response += content

                    except json.JSONDecodeError:
                        # Some lines might not be JSON
                        continue

        except Exception as e:
            self.logger.error(f"Error processing streaming response: {e}")

        print()  # New line after streaming
        return full_response

    def handle_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """Handle tool call from LLM.

        Args:
            tool_call: Tool call information
        """
        # For now, just log tool calls
        # In a full implementation, this would execute the tool
        function_name = tool_call.get("function", {}).get("name", "unknown")
        self.logger.info(f"LLM requested tool call: {function_name}")
        print(f"\n⚡ Executing tool: {function_name}")  # Enhanced display

    def handle_streaming_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        """Handle streaming response that may include tool calls.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tools

        Returns:
            Tuple of (response_text, tool_calls)
        """
        # Make streaming request
        headers = {
            "Content-Type": "application/json",
        }

        api_key = self.config.get("api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "model": self.config.get("model", "local-model"),
            "stream": True,
            "messages": messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            response = requests.post(
                self.config.get("api_url", "http://localhost/v1/chat/completions"),
                headers=headers,
                json=payload,
                stream=True,
                timeout=30,
            )
            response.raise_for_status()

            return self.parse_streaming_response_with_tools(response)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Streaming LLM request failed: {e}")
            return "", None

    def parse_streaming_response_with_tools(
        self, response: requests.Response
    ) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        """Parse streaming response and extract content and tool calls.

        Args:
            response: Streaming response object

        Returns:
            Tuple of (response_text, tool_calls)
        """
        full_response = ""
        tool_calls: List[Dict[str, Any]] = []
        current_tool_calls: Dict[int, Dict[str, Any]] = {}

        try:
            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8").strip()

                    # Skip empty lines and completion marker
                    if not line_str or line_str == "data: [DONE]":
                        continue

                    if line_str.startswith("data: "):
                        line_str = line_str[6:]  # Remove "data: " prefix

                    try:
                        data = json.loads(line_str)
                        choice = data.get("choices", [{}])[0]
                        delta = choice.get("delta", {})

                        # Handle content
                        content = delta.get("content", "")
                        if content:
                            print(content, end="", flush=True)
                            full_response += content

                        # Handle tool calls
                        if "tool_calls" in delta:
                            delta_tool_calls = delta["tool_calls"]
                            for delta_tool_call in delta_tool_calls:
                                index = delta_tool_call.get("index", 0)

                                if index not in current_tool_calls:
                                    current_tool_calls[index] = {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }

                                tool_call = current_tool_calls[index]

                                # Update tool call ID
                                if "id" in delta_tool_call:
                                    tool_call["id"] = delta_tool_call["id"]

                                # Update function details
                                if "function" in delta_tool_call:
                                    func = delta_tool_call["function"]
                                    if "name" in func:
                                        tool_call["function"]["name"] += func["name"]
                                    if "arguments" in func:
                                        tool_call["function"]["arguments"] += func[
                                            "arguments"
                                        ]

                    except json.JSONDecodeError:
                        # Some lines might not be JSON
                        continue

        except Exception as e:
            self.logger.error(f"Error parsing streaming response: {e}")

        # Convert tool calls dict to list
        if current_tool_calls:
            tool_calls = list(current_tool_calls.values())
            # Filter out incomplete tool calls
            tool_calls = [
                tc
                for tc in tool_calls
                if tc.get("id") and tc.get("function", {}).get("name")
            ]

        # Only add newline if we actually streamed content
        if full_response:
            print()  # New line after streaming

        return full_response, tool_calls if tool_calls else None
