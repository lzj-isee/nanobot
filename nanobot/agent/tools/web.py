"""Web tools: web_search and web_fetch."""

import html
import json
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from nanobot.agent.tools.base import Tool

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional, so we don't require it
    pass

# Shared constants
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_2) AppleWebKit/537.36"
MAX_REDIRECTS = 5  # Limit redirects to prevent DoS attacks


def _strip_tags(text: str) -> str:
    """Remove HTML tags and decode entities."""
    text = re.sub(r'<script[\s\S]*?</script>', '', text, flags=re.I)
    text = re.sub(r'<style[\s\S]*?</style>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    return html.unescape(text).strip()


def _normalize(text: str) -> str:
    """Normalize whitespace."""
    text = re.sub(r'[ \t]+', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _validate_url(url: str) -> tuple[bool, str]:
    """Validate URL: must be http(s) with valid domain."""
    try:
        p = urlparse(url)
        if p.scheme not in ('http', 'https'):
            return False, f"Only http/https allowed, got '{p.scheme or 'none'}'"
        if not p.netloc:
            return False, "Missing domain"
        return True, ""
    except Exception as e:
        return False, str(e)


class WebSearchTool(Tool):
    """Search the web using DashScope WebSearch API via MCP protocol."""

    name = "web_search"
    description = "Search the web. Returns titles, URLs, and snippets."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "count": {"type": "integer", "description": "Results (1-10)", "minimum": 1, "maximum": 10}
        },
        "required": ["query"]
    }

    def __init__(self, api_key: str | None = None, max_results: int = 10):
        self._init_api_key = api_key
        self.max_results = max_results
        self.base_url = "https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp"
        
        # Initialize the MCP connection and discover available tools
        self._session_initialized = False
        self._available_tools = {}
        self._search_tool_name = None
        self._input_schema = {}

    @property
    def api_key(self) -> str:
        """Resolve API key at call time so env/config changes are picked up."""
        return self._init_api_key or os.environ.get("DASHSCOPE_API_KEY", "")

    async def _ensure_session_initialized(self):
        """Initialize the MCP session and discover available tools if not already done."""
        if self._session_initialized:
            return

        if not self.api_key:
            raise ValueError("DashScope API key not configured. Set DASHSCOPE_API_KEY in your environment variables.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            # Initialize MCP session
            init_payload = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "nanobot-web-search",
                        "version": "1.0.0"
                    }
                },
                "id": 1
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Send initialization
                init_response = await client.post(self.base_url, json=init_payload, headers=headers)
                init_response.raise_for_status()
                
                # Send initialized notification
                notify_payload = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {}
                }
                await client.post(self.base_url, json=notify_payload, headers=headers)

                # Get list of available tools
                tools_payload = {
                    "jsonrpc": "2.0",
                    "method": "tools/list",
                    "id": 2
                }
                
                tools_response = await client.post(self.base_url, json=tools_payload, headers=headers)
                tools_response.raise_for_status()
                
                # Parse the tools
                tools_data = tools_response.json()
                tools_list = tools_data.get("result", {}).get("tools", [])
                
                # Store the tools for later use
                for tool in tools_list:
                    name = tool.get("name")
                    self._available_tools[name] = tool
                    
                    # Look for a web search tool
                    if "search" in name.lower() or "web" in name.lower():
                        self._search_tool_name = name
                
                # If we didn't find a search tool by keyword, use the first one
                if not self._search_tool_name and self._available_tools:
                    self._search_tool_name = next(iter(self._available_tools.keys()))
                
                if not self._search_tool_name:
                    raise ValueError("No web search tool found in the available tools")
                
                # Store the input schema for the selected tool
                selected_tool = self._available_tools[self._search_tool_name]
                self._input_schema = selected_tool.get("inputSchema", {})
                
                self._session_initialized = True

        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"HTTP error {e.response.status_code}: Failed to initialize MCP session")
        except httpx.RequestError as e:
            raise RuntimeError(f"Request error during initialization: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error initializing MCP session: {str(e)}")

    def _build_arguments(self, query: str, count: int | None = None) -> dict:
        """Dynamically build arguments based on the tool's input schema."""
        # Get the input schema properties
        schema_props = self._input_schema.get("properties", {})
        
        arguments = {}
        
        # Map the query parameter - find the actual parameter name for query (might be different)
        query_param_found = False
        for param_name in schema_props.keys():
            if param_name.lower() == "query" or "query" in param_name.lower():
                arguments[param_name] = query
                query_param_found = True
                break
        
        # If no query-like parameter found in properties, try required fields
        if not query_param_found:
            required_fields = self._input_schema.get("required", [])
            for field in required_fields:
                if field.lower() == "query" or "query" in field.lower():
                    arguments[field] = query
                    query_param_found = True
                    break
        
        # If still no query parameter found, add it with default name
        if not query_param_found:
            arguments["query"] = query
        
        # Map the count parameter - find the actual parameter name for count (might be different)
        count_param_found = False
        for param_name in schema_props.keys():
            param_lower = param_name.lower()
            # Check if the parameter name contains any of the keywords we're looking for
            if any(keyword in param_lower for keyword in ["count", "num", "limit", "size"]):
                count_arg_value = min(max(count or self.max_results, 1), 10)
                arguments[param_name] = count_arg_value
                count_param_found = True
                break
        
        # If no count-like parameter found in properties, try required fields
        if not count_param_found:
            required_fields = self._input_schema.get("required", [])
            for field in required_fields:
                field_lower = field.lower()
                # Check if the required field contains any of the keywords we're looking for
                if any(keyword in field_lower for keyword in ["count", "num", "limit", "size"]):
                    count_arg_value = min(max(count or self.max_results, 1), 10)
                    arguments[field] = count_arg_value
                    count_param_found = True
                    break
        
        return arguments

    async def execute(self, query: str, count: int | None = None, **kwargs: Any) -> str:
        if not self.api_key:
            return (
                "Error: DashScope API key not configured. "
                "Set DASHSCOPE_API_KEY in your environment variables."
            )

        try:
            # Ensure session is initialized
            await self._ensure_session_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # Build arguments dynamically based on the tool's schema
            arguments = self._build_arguments(query, count)

            # Call the discovered web search tool
            search_payload = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": self._search_tool_name,  # Dynamically discovered tool name
                    "arguments": arguments
                },
                "id": 3
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                search_response = await client.post(self.base_url, json=search_payload, headers=headers)
                search_response.raise_for_status()

            # Parse the search results
            result_data = search_response.json()
            
            # Extract content from the response
            content_blocks = result_data.get("result", {}).get("content", [])
            
            # Find the text content block
            text_content = None
            for block in content_blocks:
                if block.get("type") == "text":
                    text_content = block.get("text")
                    break
            
            if not text_content:
                return f"No search results found for query: {query}"
            
            # Parse the text content as JSON (which contains the actual search results)
            try:
                search_results = json.loads(text_content)
                pages = search_results.get("pages", [])
                
                if not pages:
                    return f"No search results found for query: {query}"
                
                # Format the results
                lines = [f"Results for: {query}\n"]
                for i, item in enumerate(pages, 1):  # Show all results returned, up to what was requested
                    title = item.get("title", "No Title")
                    url = item.get("url", "")
                    snippet = item.get("snippet", "")
                    
                    lines.append(f"{i}. {title}")
                    lines.append(f"   URL: {url}")
                    lines.append(f"   Snippet: {snippet}")
                    lines.append("")  # Empty line for readability
                
                return "\n".join(lines).strip()
            except json.JSONDecodeError:
                return f"Error parsing search results: Could not decode JSON response\nRaw response: {text_content}"

        except httpx.HTTPStatusError as e:
            return f"HTTP error {e.response.status_code}: Failed to search the web"
        except httpx.RequestError as e:
            return f"Request error: {str(e)}"
        except Exception as e:
            return f"Error: {str(e)}"


class WebFetchTool(Tool):
    """Fetch and extract content from a URL using Readability."""
    
    name = "web_fetch"
    description = "Fetch URL and extract readable content (HTML → markdown/text)."
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "extractMode": {"type": "string", "enum": ["markdown", "text"], "default": "markdown"},
            "maxChars": {"type": "integer", "minimum": 100}
        },
        "required": ["url"]
    }
    
    def __init__(self, max_chars: int = 50000):
        self.max_chars = max_chars
    
    async def execute(self, url: str, extractMode: str = "markdown", maxChars: int | None = None, **kwargs: Any) -> str:
        from readability import Document

        max_chars = maxChars or self.max_chars

        # Validate URL before fetching
        is_valid, error_msg = _validate_url(url)
        if not is_valid:
            return json.dumps({"error": f"URL validation failed: {error_msg}", "url": url}, ensure_ascii=False)

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                max_redirects=MAX_REDIRECTS,
                timeout=30.0
            ) as client:
                r = await client.get(url, headers={"User-Agent": USER_AGENT})
                r.raise_for_status()
            
            ctype = r.headers.get("content-type", "")
            
            # JSON
            if "application/json" in ctype:
                text, extractor = json.dumps(r.json(), indent=2, ensure_ascii=False), "json"
            # HTML
            elif "text/html" in ctype or r.text[:256].lower().startswith(("<!doctype", "<html")):
                doc = Document(r.text)
                content = self._to_markdown(doc.summary()) if extractMode == "markdown" else _strip_tags(doc.summary())
                text = f"# {doc.title()}\n\n{content}" if doc.title() else content
                extractor = "readability"
            else:
                text, extractor = r.text, "raw"
            
            truncated = len(text) > max_chars
            if truncated:
                text = text[:max_chars]
            
            return json.dumps({"url": url, "finalUrl": str(r.url), "status": r.status_code,
                              "extractor": extractor, "truncated": truncated, "length": len(text), "text": text}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e), "url": url}, ensure_ascii=False)
    
    def _to_markdown(self, html: str) -> str:
        """Convert HTML to markdown."""
        # Convert links, headings, lists before stripping tags
        text = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',
                      lambda m: f'[{_strip_tags(m[2])}]({m[1]})', html, flags=re.I)
        text = re.sub(r'<h([1-6])[^>]*>([\s\S]*?)</h\1>',
                      lambda m: f'\n{"#" * int(m[1])} {_strip_tags(m[2])}\n', text, flags=re.I)
        text = re.sub(r'<li[^>]*>([\s\S]*?)</li>', lambda m: f'\n- {_strip_tags(m[1])}', text, flags=re.I)
        text = re.sub(r'</(p|div|section|article)>', '\n\n', text, flags=re.I)
        text = re.sub(r'<(br|hr)\s*/?>', '\n', text, flags=re.I)
        return _normalize(_strip_tags(text))
