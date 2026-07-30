"""Request-scoped credentials used by platform component adapters.

AgentKit authenticates a public ``/invoke`` request with an ``Authorization``
header.  The Knowledge service accepts the same bearer credential, but VeADK
tools run after the HTTP handler has handed the request to the agent runner.
Keeping the value in a :class:`contextvars.ContextVar` makes it available to a
tool call without storing a per-user credential on the Agent or in an
environment variable.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Callable


_request_authorization: ContextVar[str] = ContextVar("agentkit_request_authorization", default="")


def request_authorization() -> str:
    """Return the current request Authorization header, never logging it."""
    return _request_authorization.get()


class RequestAuthorizationMiddleware:
    """Expose the inbound bearer token to adapters for this request only."""

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        authorization = ""
        for key, value in scope.get("headers", []):
            if key.decode("latin-1").lower() == "authorization":
                authorization = value.decode("latin-1")
                break

        token = _request_authorization.set(authorization)
        try:
            await self.app(scope, receive, send)
        finally:
            _request_authorization.reset(token)
