"""Request handling and formatting for LLM client."""

import json
from typing import Any, Dict, List, Optional


class RequestHandler:
    """Handles formatting and sending of requests to LLM API."""

    def __init__(
        self, logger: Any, config_manager: Any, token_manager: Any, openai_client: Any
    ):
        """Initialize request handler.

        Args:
            logger: Logger instance
            config_manager: Configuration manager
            token_manager: Token counting manager
            openai_client: OpenAI client instance
        """
        self.logger = logger
        self.config = config_manager
        self.token_manager = token_manager
        self.openai_client = openai_client

    def make_llm_request(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        message_validator: Any = None,
    ) -> Optional[Dict[str, Any]]:
        """Make a request to the LLM API.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tools
            stream: Whether to stream response
            message_validator: Optional message validator for role alternation fixes

        Returns:
            Response data or None if failed
        """
        # Validate messages if validator provided
        if message_validator:
            messages = message_validator.validate_and_fix_role_alternation(messages)
            # Log the final message sequence for debugging
            role_sequence = [msg.get("role", "unknown") for msg in messages]
            self.logger.debug(f"Message role sequence: {role_sequence}")

        # Prepare request parameters
        request_params = {
            "model": self.config.get("model", "local-model"),
            "stream": stream,
            "messages": messages,
        }

        # Add tools to payload according to OpenAI API and MCP specifications
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"
            # Debug: Log the tools being sent to the model
            self.logger.debug(
                f"Sending {len(tools)} tools to model "
                f"{self.config.get('model', 'local-model')}"
            )
            for i, tool in enumerate(tools[:3]):  # Log first 3 tools
                self.logger.debug(f"Tool {i}: {json.dumps(tool, indent=2)}")

        # Final token count verification for debugging
        model = self.config.get("model", "gpt-3.5-turbo")
        # Create a mock payload for token counting
        # (since OpenAI client handles the actual payload)
        mock_payload = {
            "model": request_params["model"],
            "stream": request_params["stream"],
            "messages": request_params["messages"],
        }
        if tools:
            mock_payload["tools"] = tools
            mock_payload["tool_choice"] = "auto"

        final_tokens = self.token_manager.count_tokens_for_payload(mock_payload, model)
        self.logger.debug(f"Final payload tokens: {final_tokens}")

        # Debug: Log the complete request structure (without full content for brevity)
        debug_request = {
            "model": request_params["model"],
            "stream": request_params["stream"],
            "messages": f"{len(request_params['messages'])} messages",
            "tools": (
                f"{len(request_params.get('tools', []))} tools" if tools else "no tools"
            ),
            "tool_choice": request_params.get("tool_choice", "not set"),
        }
        self.logger.debug(
            "Complete request structure: " f"{json.dumps(debug_request, indent=2)}"
        )

        try:
            response = self.openai_client.chat.completions.create(**request_params)

            self.logger.debug("LLM response received successfully")

            if stream:
                # Streaming responses are handled by streaming handler; return None
                return None
            else:
                # Convert OpenAI response to dict format for compatibility
                content = response.choices[0].message.content

                # Handle thinking content filtering if needed
                filtered_content = content
                if content and "<thinking>" in content:
                    # Basic filtering for thinking content
                    import re

                    filtered_content = re.sub(
                        r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL
                    )

                response_data = {
                    "choices": [
                        {
                            "message": {
                                "content": filtered_content,
                                "role": response.choices[0].message.role,
                                "tool_calls": (
                                    [
                                        {
                                            "id": tc.id,
                                            "type": tc.type,
                                            "function": {
                                                "name": tc.function.name,
                                                "arguments": tc.function.arguments,
                                            },
                                        }
                                        for tc in response.choices[0].message.tool_calls
                                    ]
                                    if response.choices[0].message.tool_calls
                                    else None
                                ),
                            }
                        }
                    ]
                }
                self.logger.debug(
                    f"LLM response data: {json.dumps(response_data, indent=2)[:500]}..."
                )
                return response_data

        except Exception as e:
            self.logger.error(f"LLM request failed: {e}")
            return None

    def make_llm_request_with_debug(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False,
        message_validator: Any = None,
    ) -> tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        """Make a request to the LLM API with debug information captured.

        Args:
            messages: List of message dictionaries
            tools: Optional list of tools
            stream: Whether to stream response
            message_validator: Optional message validator for role alternation fixes

        Returns:
            Tuple of (response data or None if failed, debug information dict)
        """
        # Validate messages if validator provided
        if message_validator:
            messages = message_validator.validate_and_fix_role_alternation(messages)
            # Log the final message sequence for debugging
            role_sequence = [msg.get("role", "unknown") for msg in messages]
            self.logger.debug(f"Message role sequence: {role_sequence}")

        # Prepare request parameters
        request_params = {
            "model": self.config.get("model", "local-model"),
            "stream": stream,
            "messages": messages,
        }

        # Add tools to payload according to OpenAI API and MCP specifications
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = "auto"

        # Capture debug information
        debug_info = {
            "request": {
                "model": request_params["model"],
                "stream": request_params["stream"],
                "messages": request_params["messages"],
                "tools": request_params.get("tools"),
                "tool_choice": request_params.get("tool_choice"),
            },
            "request_metadata": {
                "message_count": len(messages),
                "tool_count": len(tools) if tools else 0,
                "total_message_chars": sum(len(str(msg.get("content", ""))) for msg in messages),
            }
        }

        # Final token count verification for debugging
        model = self.config.get("model", "gpt-3.5-turbo")
        mock_payload = {
            "model": request_params["model"],
            "stream": request_params["stream"],
            "messages": request_params["messages"],
        }
        if tools:
            mock_payload["tools"] = tools
            mock_payload["tool_choice"] = "auto"

        final_tokens = self.token_manager.count_tokens_for_payload(mock_payload, model)
        debug_info["request_metadata"]["estimated_tokens"] = final_tokens

        try:
            response = self.openai_client.chat.completions.create(**request_params)

            self.logger.debug("LLM response received successfully")

            if stream:
                # Streaming responses are handled by streaming handler; return None
                debug_info["response"] = {"type": "stream", "note": "Streaming response not captured in debug"}
                return None, debug_info
            else:
                # Convert OpenAI response to dict format for compatibility
                content = response.choices[0].message.content
                
                # Capture raw response for debug
                raw_response = {
                    "id": response.id,
                    "object": response.object,
                    "created": response.created,
                    "model": response.model,
                    "choices": [
                        {
                            "index": choice.index,
                            "message": {
                                "role": choice.message.role,
                                "content": choice.message.content,
                                "tool_calls": (
                                    [
                                        {
                                            "id": tc.id,
                                            "type": tc.type,
                                            "function": {
                                                "name": tc.function.name,
                                                "arguments": tc.function.arguments,
                                            },
                                        }
                                        for tc in choice.message.tool_calls
                                    ]
                                    if choice.message.tool_calls
                                    else None
                                ),
                            },
                            "finish_reason": choice.finish_reason,
                        }
                        for choice in response.choices
                    ],
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                        "completion_tokens": response.usage.completion_tokens if response.usage else None,
                        "total_tokens": response.usage.total_tokens if response.usage else None,
                    } if response.usage else None,
                }

                debug_info["response"] = raw_response

                # Handle thinking content filtering if needed
                filtered_content = content
                if content and "<thinking>" in content:
                    # Basic filtering for thinking content
                    import re
                    filtered_content = re.sub(
                        r"<thinking>.*?</thinking>", "", content, flags=re.DOTALL
                    )

                response_data = {
                    "choices": [
                        {
                            "message": {
                                "content": filtered_content,
                                "role": response.choices[0].message.role,
                                "tool_calls": (
                                    [
                                        {
                                            "id": tc.id,
                                            "type": tc.type,
                                            "function": {
                                                "name": tc.function.name,
                                                "arguments": tc.function.arguments,
                                            },
                                        }
                                        for tc in response.choices[0].message.tool_calls
                                    ]
                                    if response.choices[0].message.tool_calls
                                    else None
                                ),
                            }
                        }
                    ]
                }
                
                return response_data, debug_info

        except Exception as e:
            debug_info["error"] = {
                "message": str(e),
                "type": type(e).__name__,
            }
            self.logger.error(f"LLM request failed: {e}")
            return None, debug_info
