"""Tests for WebSearchTool."""

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from nanobot.agent.tools.web import WebSearchTool


@pytest.fixture
def mock_dashscope_api_key():
    """Fixture to set a mock DASHSCOPE_API_KEY for testing."""
    original_key = os.environ.get("DASHSCOPE_API_KEY")
    os.environ["DASHSCOPE_API_KEY"] = "mock-api-key-for-testing"
    yield
    if original_key is not None:
        os.environ["DASHSCOPE_API_KEY"] = original_key
    else:
        os.environ.pop("DASHSCOPE_API_KEY", None)


@pytest.mark.asyncio
async def test_web_search_tool_initialization(mock_dashscope_api_key):
    """Test WebSearchTool initialization."""
    tool = WebSearchTool()
    
    assert tool.name == "web_search"
    assert tool.description == "Search the web. Returns titles, URLs, and snippets."
    assert tool.api_key == "mock-api-key-for-testing"


@pytest.mark.asyncio
async def test_web_search_tool_api_key_from_constructor(mock_dashscope_api_key):
    """Test that WebSearchTool uses API key passed to constructor."""
    custom_api_key = "custom-api-key"
    tool = WebSearchTool(api_key=custom_api_key)
    
    assert tool.api_key == custom_api_key


@pytest.mark.asyncio
async def test_web_search_tool_api_key_fallback_to_env(mock_dashscope_api_key):
    """Test that WebSearchTool falls back to environment variable for API key."""
    tool = WebSearchTool()
    
    assert tool.api_key == "mock-api-key-for-testing"


@pytest.mark.asyncio
async def test_web_search_tool_execute_without_api_key():
    """Test that WebSearchTool returns error when no API key is provided."""
    # Temporarily remove the API key
    original_key = os.environ.get("DASHSCOPE_API_KEY")
    if "DASHSCOPE_API_KEY" in os.environ:
        del os.environ["DASHSCOPE_API_KEY"]
    
    try:
        tool = WebSearchTool()
        result = await tool.execute(query="test query")
        
        assert "Error: DashScope API key not configured" in result
        assert "Set DASHSCOPE_API_KEY in your environment variables" in result
    finally:
        # Restore original key if it existed
        if original_key is not None:
            os.environ["DASHSCOPE_API_KEY"] = original_key




@pytest.mark.asyncio
async def test_build_arguments_method(mock_dashscope_api_key):
    """Test the _build_arguments method with different schemas."""
    tool = WebSearchTool()
    
    # Simulate a schema with standard query and count fields
    tool._input_schema = {
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Number of results"}
        },
        "required": ["query"]
    }
    
    arguments = tool._build_arguments("test query", 5)
    
    assert arguments["query"] == "test query"
    assert arguments["count"] == 5


@pytest.mark.asyncio
async def test_build_arguments_with_different_field_names(mock_dashscope_api_key):
    """Test the _build_arguments method with different field names."""
    tool = WebSearchTool()
    
    # Simulate a schema with different field names
    tool._input_schema = {
        "properties": {
            "search_query": {"type": "string", "description": "Search query"},
            "result_count": {"type": "integer", "description": "Number of results"}
        },
        "required": ["search_query"]
    }
    
    arguments = tool._build_arguments("test query", 3)
    
    assert arguments["search_query"] == "test query"
    assert arguments["result_count"] == 3


@pytest.mark.asyncio
async def test_build_arguments_fallback_to_required_fields(mock_dashscope_api_key):
    """Test the _build_arguments method fallback to required fields."""
    tool = WebSearchTool()
    
    # Simulate a schema with unusual field names that match the required fields
    tool._input_schema = {
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "num_results": {"type": "integer", "description": "Number of results"}
        },
        "required": ["query", "num_results"]
    }
    
    arguments = tool._build_arguments("test query", 4)
    
    assert arguments["query"] == "test query"
    assert arguments["num_results"] == 4


@pytest.mark.asyncio
async def test_build_arguments_defaults_to_query_if_not_found(mock_dashscope_api_key):
    """Test that _build_arguments defaults to 'query' field if no match found."""
    tool = WebSearchTool()
    
    # Simulate a schema with no recognizable field names
    tool._input_schema = {
        "properties": {
            "unknown_field": {"type": "string", "description": "Some unknown field"},
            "another_field": {"type": "integer", "description": "Another field"}
        },
        "required": ["unknown_field"]
    }
    
    arguments = tool._build_arguments("test query", 2)
    
    # Should include the query even if field names don't match known patterns
    assert arguments["query"] == "test query"
    # Count should not be added if no matching field was found
    assert "count" not in arguments or "another_field" in arguments