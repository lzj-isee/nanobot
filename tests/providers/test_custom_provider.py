"""Tests for CustomProvider with stream mode."""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock

from nanobot.providers.custom_provider import CustomProvider
from nanobot.providers.base import LLMResponse, ToolCallRequest


@pytest.fixture
def provider():
    """Create a CustomProvider instance."""
    return CustomProvider(
        api_key="test-key",
        api_base="https://test.example.com/v1",
        default_model="test-model",
    )


@pytest.fixture
def mock_stream_response():
    """Create a mock stream response."""
    def _create(chunks):
        async def _async_iter():
            for chunk in chunks:
                yield chunk
        return _async_iter()
    return _create


class TestCustomProviderBasic:
    """Basic functionality tests."""

    @pytest.mark.asyncio
    async def test_simple_chat(self, provider, mock_stream_response):
        """Test simple chat without tools."""
        # Mock chunks for a simple response
        chunks = [
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content="Hello", reasoning_content=None, tool_calls=None), finish_reason=None)],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content=" world", reasoning_content=None, tool_calls=None), finish_reason="stop")],
                usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello world"
        assert response.tool_calls == []
        assert response.finish_reason == "stop"
        assert response.usage["prompt_tokens"] == 10
        assert response.usage["completion_tokens"] == 5

    @pytest.mark.asyncio
    async def test_chat_with_reasoning(self, provider, mock_stream_response):
        """Test chat with reasoning content (thinking process)."""
        chunks = [
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content=None, reasoning_content="Let me think", tool_calls=None), finish_reason=None)],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content="Answer", reasoning_content=None, tool_calls=None), finish_reason="stop")],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(messages=[{"role": "user", "content": "Question"}])

        assert response.content == "Answer"
        assert response.reasoning_content == "Let me think"

    @pytest.mark.asyncio
    async def test_empty_content_handling(self, provider, mock_stream_response):
        """Test handling of empty content in response."""
        chunks = [
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content="", reasoning_content=None, tool_calls=None), finish_reason="stop")],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

        assert response.content is None  # Empty content becomes None


class TestCustomProviderToolCalls:
    """Tool call related tests."""

    @pytest.mark.asyncio
    async def test_single_tool_call(self, provider, mock_stream_response):
        """Test single tool call."""
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        }]

        # Tool call chunks come incrementally
        # Use a real object for function to avoid MagicMock issues with +=
        class MockFunction:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments

        chunks = [
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        content=None,
                        reasoning_content="I need weather",
                        tool_calls=[MagicMock(index=0, id="call_1", function=MockFunction("get_weather", '{"city": "'), finish_reason=None)],
                    ),
                    finish_reason=None,
                )],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        content=None,
                        reasoning_content=None,
                        tool_calls=[MagicMock(index=0, id=None, function=MockFunction(None, 'Beijing"}'), finish_reason=None)],
                    ),
                    finish_reason=None,
                )],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content=None, reasoning_content=None, tool_calls=None), finish_reason="tool_calls")],
                usage=MagicMock(prompt_tokens=20, completion_tokens=10, total_tokens=30),
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(
            messages=[{"role": "user", "content": "Weather in Beijing"}],
            tools=tools,
        )

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].id == "call_1"
        assert response.tool_calls[0].name == "get_weather"
        assert response.tool_calls[0].arguments == {"city": "Beijing"}
        assert response.finish_reason == "tool_calls"

    @pytest.mark.asyncio
    async def test_multiple_tool_calls(self, provider, mock_stream_response):
        """Test parallel tool calls."""
        tools = [{
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
            },
        }]

        chunks = [
            # First tool call
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        content=None,
                        tool_calls=[MagicMock(index=0, id="call_1", function=MagicMock(name="get_weather", arguments='{"city": "Beijing"}'))],
                    ),
                    finish_reason=None,
                )],
                usage=None,
            ),
            # Second tool call
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        content=None,
                        tool_calls=[MagicMock(index=1, id="call_2", function=MagicMock(name="get_weather", arguments='{"city": "Shanghai"}'))],
                    ),
                    finish_reason=None,
                )],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content=None, tool_calls=None), finish_reason="tool_calls")],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(
            messages=[{"role": "user", "content": "Weather in Beijing and Shanghai"}],
            tools=tools,
        )

        assert len(response.tool_calls) == 2
        assert response.tool_calls[0].arguments == {"city": "Beijing"}
        assert response.tool_calls[1].arguments == {"city": "Shanghai"}

    @pytest.mark.asyncio
    async def test_tool_call_with_partial_arguments(self, provider, mock_stream_response):
        """Test tool call where arguments come in multiple small chunks."""
        tools = [{
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        }]

        # Arguments split into many small pieces
        chunks = [
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        tool_calls=[MagicMock(index=0, id="call_1", function=MagicMock(name="search", arguments='{"qu'))],
                    ),
                    finish_reason=None,
                )],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        tool_calls=[MagicMock(index=0, id=None, function=MagicMock(name=None, arguments='ery": "'))],
                    ),
                    finish_reason=None,
                )],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        tool_calls=[MagicMock(index=0, id=None, function=MagicMock(name=None, arguments='hello wor'))],
                    ),
                    finish_reason=None,
                )],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        tool_calls=[MagicMock(index=0, id=None, function=MagicMock(name=None, arguments='ld"}'))],
                    ),
                    finish_reason=None,
                )],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(delta=MagicMock(tool_calls=None), finish_reason="tool_calls")],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(
            messages=[{"role": "user", "content": "Search"}],
            tools=tools,
        )

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].arguments == {"query": "hello world"}


class TestCustomProviderMultiTurn:
    """Multi-turn conversation tests."""

    @pytest.mark.asyncio
    async def test_conversation_with_tool_result(self, provider, mock_stream_response):
        """Test conversation where tool result is sent back."""
        # First turn: assistant requests tool call
        class MockFunction:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments

        chunks1 = [
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        content=None,
                        tool_calls=[MagicMock(index=0, id="call_1", function=MockFunction("get_time", '{}'))],
                    ),
                    finish_reason="tool_calls",
                )],
                usage=MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks1))

        response1 = await provider.chat(
            messages=[{"role": "user", "content": "What time is it?"}],
            tools=[{
                "type": "function",
                "function": {"name": "get_time", "description": "Get time", "parameters": {"type": "object", "properties": {}}},
            }],
        )

        assert response1.tool_calls[0].name == "get_time"

        # Second turn: assistant responds to tool result
        chunks2 = [
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(content="The current time is ", tool_calls=None),
                    finish_reason=None,
                )],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(content="14:30.", tool_calls=None),
                    finish_reason="stop",
                )],
                usage=MagicMock(prompt_tokens=25, completion_tokens=10, total_tokens=35),
            ),
        ]

        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks2))

        messages = [
            {"role": "user", "content": "What time is it?"},
            {"role": "assistant", "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "get_time", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "14:30"},
        ]

        response2 = await provider.chat(messages=messages)

        assert response2.content == "The current time is 14:30."
        assert response2.tool_calls == []


class TestCustomProviderErrorHandling:
    """Error handling tests."""

    @pytest.mark.asyncio
    async def test_api_error(self, provider):
        """Test handling of API errors."""
        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(side_effect=Exception("Connection error"))

        response = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

        assert response.content == "Error: Connection error"
        assert response.finish_reason == "error"
        assert response.tool_calls == []

    @pytest.mark.asyncio
    async def test_invalid_json_in_tool_args(self, provider, mock_stream_response):
        """Test handling of invalid JSON in tool arguments."""
        class MockFunction:
            def __init__(self, name, arguments):
                self.name = name
                self.arguments = arguments

        chunks = [
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        tool_calls=[MagicMock(index=0, id="call_1", function=MockFunction("test", 'invalid json'))],
                    ),
                    finish_reason="tool_calls",
                )],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(
            messages=[{"role": "user", "content": "Test"}],
            tools=[{
                "type": "function",
                "function": {"name": "test", "description": "Test", "parameters": {"type": "object", "properties": {}}},
            }],
        )

        # Should handle invalid JSON gracefully (json_repair should fix it or return empty dict)
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "test"


class TestCustomProviderParameters:
    """Parameter passing tests."""

    @pytest.mark.asyncio
    async def test_model_override(self, provider, mock_stream_response):
        """Test that model parameter overrides default."""
        chunks = [
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content="OK"), finish_reason="stop")],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        await provider.chat(
            messages=[{"role": "user", "content": "Hi"}],
            model="overridden-model",
        )

        # Verify the model was passed correctly
        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "overridden-model"

    @pytest.mark.asyncio
    async def test_temperature_and_max_tokens(self, provider, mock_stream_response):
        """Test temperature and max_tokens parameters."""
        chunks = [
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content="OK"), finish_reason="stop")],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        await provider.chat(
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.5,
            max_tokens=100,
        )

        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["temperature"] == 0.5
        assert call_kwargs["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_max_tokens_clamped(self, provider, mock_stream_response):
        """Test that max_tokens is clamped to at least 1."""
        chunks = [
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content="OK"), finish_reason="stop")],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        await provider.chat(
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=0,  # Invalid value
        )

        call_kwargs = provider._client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 1  # Should be clamped


class TestCustomProviderEdgeCases:
    """Edge case tests."""

    @pytest.mark.asyncio
    async def test_only_reasoning_no_content(self, provider, mock_stream_response):
        """Test response with only reasoning content and no regular content."""
        chunks = [
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(content=None, reasoning_content="Thinking...", tool_calls=None),
                    finish_reason="stop",
                )],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(messages=[{"role": "user", "content": "Think"}])

        assert response.content is None
        assert response.reasoning_content == "Thinking..."

    @pytest.mark.asyncio
    async def test_mixed_content_and_tool_calls(self, provider, mock_stream_response):
        """Test response with both content and tool calls."""
        chunks = [
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(content="Let me check ", tool_calls=None),
                    finish_reason=None,
                )],
                usage=None,
            ),
            MagicMock(
                choices=[MagicMock(
                    delta=MagicMock(
                        content="the weather",
                        tool_calls=[MagicMock(index=0, id="call_1", function=MagicMock(name="get_weather", arguments='{"city": "NYC"}'))],
                    ),
                    finish_reason="tool_calls",
                )],
                usage=None,
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(
            messages=[{"role": "user", "content": "Weather"}],
            tools=[{
                "type": "function",
                "function": {"name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}},
            }],
        )

        assert response.content == "Let me check the weather"
        assert len(response.tool_calls) == 1

    @pytest.mark.asyncio
    async def test_empty_stream(self, provider, mock_stream_response):
        """Test handling of empty stream."""
        chunks = []

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

        assert response.content is None
        assert response.tool_calls == []
        assert response.finish_reason == "stop"  # Default

    @pytest.mark.asyncio
    async def test_usage_in_multiple_chunks(self, provider, mock_stream_response):
        """Test that usage from any chunk is captured."""
        chunks = [
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content="Hello"), finish_reason=None)],
                usage=MagicMock(prompt_tokens=5, completion_tokens=0, total_tokens=5),
            ),
            MagicMock(
                choices=[MagicMock(delta=MagicMock(content=" world"), finish_reason="stop")],
                usage=MagicMock(prompt_tokens=5, completion_tokens=2, total_tokens=7),
            ),
        ]

        provider._client = MagicMock()
        provider._client.chat.completions.create = AsyncMock(return_value=mock_stream_response(chunks))

        response = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

        # Should use the last usage info
        assert response.usage["total_tokens"] == 7
