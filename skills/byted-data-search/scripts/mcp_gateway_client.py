import json
import os
from typing import Any, Dict, Optional, Tuple

import requests

DEFAULT_MCP_GATEWAY_URL = (
    "https://sd6k08f59gqcea6qe13vg.apigateway-cn-beijing.volceapi.com/mcp"
)


def load_credentials(
    access_key: Optional[str] = None, secret_key: Optional[str] = None
) -> Tuple[str, str]:
    """Load Volcengine credentials from parameters or environment variables.
    
    Supports both VOLCENGINE_ACCESS_KEY and VOLC_ACCESS_KEY naming conventions.
    """
    ak = (
        access_key
        or os.getenv("VOLCENGINE_ACCESS_KEY")
        or os.getenv("VOLC_ACCESS_KEY")
        or ""
    )
    sk = (
        secret_key
        or os.getenv("VOLCENGINE_SECRET_KEY")
        or os.getenv("VOLC_SECRET_KEY")
        or ""
    )

    if not ak or not sk:
        raise ValueError(
            "Missing credentials. Please set environment variables:\n"
            "  export VOLCENGINE_ACCESS_KEY='your-access-key'\n"
            "  export VOLCENGINE_SECRET_KEY='your-secret-key'\n"
            "Get your AK/SK from: https://www.volcengine.com/docs/6291/65568"
        )

    return ak, sk


def call_mcp_tool(
    *,
    url: str,
    access_key: str,
    secret_key: str,
    tool_name: str,
    arguments: Dict[str, Any],
    request_id: int = 1,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    """Call an MCP tool via the Volcengine MCP Gateway.
    
    Args:
        url: MCP Gateway endpoint URL
        access_key: Volcengine Access Key
        secret_key: Volcengine Secret Key
        tool_name: Name of the MCP tool to invoke
        arguments: Tool arguments dict
        request_id: JSON-RPC request ID
        timeout_seconds: Request timeout in seconds
    
    Returns:
        JSON-RPC response dict
    
    Raises:
        requests.HTTPError: If the HTTP request fails
        requests.Timeout: If the request times out
    """
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Volc-Access-Key": access_key,
        "Volc-Secret-Key": secret_key,
    }

    response = requests.post(
        url,
        headers=headers,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def extract_tool_text(mcp_response: Dict[str, Any]) -> Optional[str]:
    """Extract text content from MCP tool response.
    
    Args:
        mcp_response: Raw JSON-RPC response from MCP Gateway
    
    Returns:
        Concatenated text content, or None if error or no text found
    """
    if "error" in mcp_response and mcp_response["error"]:
        return None

    result = mcp_response.get("result")
    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, list):
            texts = []
            for item in content:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "text"
                    and isinstance(item.get("text"), str)
                ):
                    texts.append(item["text"])
            if texts:
                return "\n".join(texts)

    if isinstance(result, str):
        return result

    return None


def pretty_print_mcp_result(mcp_response: Dict[str, Any]) -> None:
    """Pretty-print an MCP tool response.
    
    For text results, attempts JSON parsing for formatted output.
    Falls back to raw JSON-RPC dump on error or non-text responses.
    """
    if "error" in mcp_response and mcp_response["error"]:
        print(json.dumps(mcp_response, ensure_ascii=False, indent=2))
        return

    tool_text = extract_tool_text(mcp_response)
    if tool_text is None:
        print(json.dumps(mcp_response, ensure_ascii=False, indent=2))
        return

    try:
        parsed = json.loads(tool_text)
        print(json.dumps(parsed, ensure_ascii=False, indent=2))
    except Exception:
        print(tool_text)
