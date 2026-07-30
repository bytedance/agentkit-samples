from __future__ import annotations

import sys

import platform_mcp


def clear_mcp_env(monkeypatch) -> None:
    for key in (
        "TOOL_MCP_ROUTER_URL",
        "TOOL_MCP_ROUTER_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    sys.modules.pop("veadk.tools.builtin_tools.mcp_router", None)


def test_platform_mcp_is_disabled_without_complete_configuration(monkeypatch) -> None:
    clear_mcp_env(monkeypatch)
    assert platform_mcp.platform_mcp_configured() is False
    assert platform_mcp.build_platform_mcp_router() is None

    monkeypatch.setenv("TOOL_MCP_ROUTER_URL", "https://mcp.example/mcp")
    assert platform_mcp.platform_mcp_configured() is False
    assert platform_mcp.build_platform_mcp_router() is None


def test_platform_mcp_uses_injected_toolset_router(monkeypatch) -> None:
    clear_mcp_env(monkeypatch)
    # Hybrid-cloud AgentKit currently injects the toolset base URL.
    monkeypatch.setenv("TOOL_MCP_ROUTER_URL", "https://mcp.example/router-id/")
    monkeypatch.setenv("TOOL_MCP_ROUTER_API_KEY", "secret-test-key")

    toolset = platform_mcp.build_platform_mcp_router()

    assert platform_mcp.platform_mcp_configured() is True
    assert toolset._connection_params.url == "https://mcp.example/router-id/mcp"
    assert toolset._connection_params.headers == {"Authorization": "Bearer secret-test-key"}


def test_normalize_mcp_router_url_appends_streamable_http_path() -> None:
    assert (
        platform_mcp.normalize_mcp_router_url("https://mcp.example/router-id/")
        == "https://mcp.example/router-id/mcp"
    )


def test_normalize_mcp_router_url_preserves_complete_endpoint() -> None:
    assert (
        platform_mcp.normalize_mcp_router_url("https://mcp.example/router-id/mcp")
        == "https://mcp.example/router-id/mcp"
    )
