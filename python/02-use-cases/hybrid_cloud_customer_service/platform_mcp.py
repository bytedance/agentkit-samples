"""AgentKit MCP toolset integration through VeADK's platform router.

The platform lifecycle is MCP service -> MCP toolset -> Runtime association.
After the Runtime is published, AgentKit injects ``TOOL_MCP_ROUTER_URL`` and
``TOOL_MCP_ROUTER_API_KEY`` for the associated toolset.  VeADK's
``mcp_router`` consumes those values and hides MCP discovery/routing details
from business code.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import urlsplit, urlunsplit

logger = logging.getLogger(__name__)


def normalize_mcp_router_url(url: str) -> str:
    """Return the Streamable HTTP endpoint expected by VeADK.

    AgentKit currently injects the MCP toolset public *base* URL in some
    hybrid-cloud environments, while VeADK 0.5.40 passes that value to the
    MCP client verbatim.  The actual Streamable HTTP endpoint is ``/mcp``.
    Keep an already complete endpoint unchanged so this compatibility shim
    remains safe after the platform starts injecting the full URL.
    """
    value = url.strip()
    parsed = urlsplit(value)
    path = parsed.path.rstrip("/")
    if not path.endswith("/mcp"):
        path = f"{path}/mcp"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))


def platform_mcp_configured() -> bool:
    """Whether AgentKit injected a complete associated-toolset connection."""
    return bool(os.getenv("TOOL_MCP_ROUTER_URL") and os.getenv("TOOL_MCP_ROUTER_API_KEY"))


def build_platform_mcp_router():
    """Return VeADK's MCP router when a platform toolset is associated.

    The import is deliberately lazy because VeADK reads both required values
    at module import time.  This keeps local/demo mode usable without MCP and
    avoids duplicating the platform's authentication or routing logic.
    """
    url = os.getenv("TOOL_MCP_ROUTER_URL", "").strip()
    api_key = os.getenv("TOOL_MCP_ROUTER_API_KEY", "").strip()
    if not url and not api_key:
        return None
    if not url or not api_key:
        logger.warning(
            "AgentKit MCP disabled: TOOL_MCP_ROUTER_URL and "
            "TOOL_MCP_ROUTER_API_KEY must both be injected."
        )
        return None
    if not url.startswith(("http://", "https://")):
        logger.warning("AgentKit MCP disabled: toolset router URL must be HTTP(S).")
        return None

    normalized_url = normalize_mcp_router_url(url)
    if normalized_url != url:
        # Do not log the URL or API key: both are Runtime connection details.
        logger.info("AgentKit MCP router base URL detected; appended Streamable HTTP path /mcp.")
        # VeADK 0.5.40 reads the value while importing its built-in singleton.
        os.environ["TOOL_MCP_ROUTER_URL"] = normalized_url

    from veadk.tools.builtin_tools.mcp_router import mcp_router

    logger.info("AgentKit MCP toolset router enabled from Runtime association.")
    return mcp_router
