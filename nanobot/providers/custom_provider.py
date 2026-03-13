"""Direct OpenAI-compatible provider — bypasses LiteLLM."""

from __future__ import annotations

from typing import Any

import json_repair
from openai import AsyncOpenAI

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class CustomProvider(LLMProvider):

    def __init__(self, api_key: str = "no-key", api_base: str = "http://localhost:8000/v1", default_model: str = "default"):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        self._client = AsyncOpenAI(api_key=api_key, base_url=api_base)

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None,
                   model: str | None = None, max_tokens: int = 4096, temperature: float = 0.7) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": self._sanitize_empty_content(messages),
            "max_tokens": max(1, max_tokens),
            "temperature": temperature,
            "extra_body": {"enable_thinking": True},
            "stream": True,  # Use stream mode to avoid non-stream issues
        }
        if tools:
            kwargs.update(tools=tools, tool_choice="auto")

        try:
            stream = await self._client.chat.completions.create(**kwargs)
            return await self._parse_stream(stream)
        except Exception as e:
            return LLMResponse(content=f"Error: {e}", finish_reason="error")

    async def _parse_stream(self, stream) -> LLMResponse:
        """Parse SSE stream chunks and assemble complete response."""
        content = ""
        reasoning_content = ""
        tool_calls: dict[int, dict[str, Any]] = {}  # index -> {id, name, arguments}
        finish_reason = "stop"
        usage = {}

        async for chunk in stream:
            # Handle usage info (usually in last chunk)
            if chunk.usage:
                usage = {
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                    "total_tokens": chunk.usage.total_tokens,
                }

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta
            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason

            # Collect reasoning content (thinking process)
            if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                reasoning_content += delta.reasoning_content

            # Collect content
            if delta.content:
                content += delta.content

            # Collect tool calls (incremental, index-based)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {"id": "", "name": "", "arguments": ""}

                    if tc.id:
                        tool_calls[idx]["id"] += tc.id
                    if tc.function and tc.function.name:
                        tool_calls[idx]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls[idx]["arguments"] += tc.function.arguments

        # Assemble tool calls into ToolCallRequest objects
        assembled_tool_calls = []
        for idx in sorted(tool_calls.keys()):
            tc = tool_calls[idx]
            try:
                args = json_repair.loads(tc["arguments"]) if tc["arguments"] else {}
            except Exception:
                args = {}
            assembled_tool_calls.append(ToolCallRequest(
                id=tc["id"],
                name=tc["name"],
                arguments=args,
            ))

        return LLMResponse(
            content=content if content else None,
            tool_calls=assembled_tool_calls,
            finish_reason=finish_reason or "stop",
            usage=usage,
            reasoning_content=reasoning_content if reasoning_content else None,
        )

    def get_default_model(self) -> str:
        return self.default_model
