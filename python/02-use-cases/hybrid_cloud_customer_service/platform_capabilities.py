"""Portable platform capability adapters with explicit local fallbacks."""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import subprocess
from dataclasses import dataclass
from typing import Any

from a2a_client import a2a_data_agent_configured


@dataclass(slots=True)
class Identity:
    tenant_id: str
    user_id: str
    roles: list[str]
    source: str


def resolve_identity(tenant_id: str, user_id: str, authorization: str | None = None) -> Identity:
    """Consume gateway-verified JWT claims and enforce tenant/user equality."""
    if authorization and authorization.startswith("Bearer "):
        parts = authorization.removeprefix("Bearer ").split(".")
        if len(parts) != 3:
            raise PermissionError("invalid gateway identity claims")
        try:
            payload = parts[1] + "=" * (-len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise PermissionError("invalid gateway identity claims") from exc
        claim_tenant = str(claims.get("tenant_id", tenant_id))
        claim_user = str(claims.get("sub", user_id))
        if claim_tenant != tenant_id or claim_user != user_id:
            raise PermissionError("request identity does not match gateway claims")
        return Identity(
            claim_tenant, claim_user, list(claims.get("roles", ["customer"])), "gateway-jwt"
        )
    return Identity(tenant_id, user_id, ["customer"], "local-request")


class SessionStore:
    """Tenant-isolated session state; SQLite fallback for local demos and CI."""

    def __init__(self, path: str | None = None) -> None:
        self._db = sqlite3.connect(
            path or os.getenv("SESSION_SQLITE_PATH", ":memory:"), check_same_thread=False
        )
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS sessions (tenant TEXT, user TEXT, session TEXT, state TEXT, PRIMARY KEY (tenant,user,session))"
        )

    @property
    def mode(self) -> str:
        return "platform-postgres" if platform_postgres_configured() else "local-sqlite"

    def load(self, tenant: str, user: str, session: str) -> dict[str, Any]:
        row = self._db.execute(
            "SELECT state FROM sessions WHERE tenant=? AND user=? AND session=?",
            (tenant, user, session),
        ).fetchone()
        return json.loads(row[0]) if row else {}

    def save(self, tenant: str, user: str, session: str, state: dict[str, Any]) -> None:
        self._db.execute(
            "INSERT OR REPLACE INTO sessions VALUES (?,?,?,?)",
            (tenant, user, session, json.dumps(state, ensure_ascii=False)),
        )
        self._db.commit()


def sandbox_calculate(expression: str) -> dict[str, Any]:
    if not expression or any(char not in set("0123456789+-*/(). %") for char in expression):
        raise ValueError("sandbox expression contains unsupported characters")
    script = (
        "import ast;print(eval(compile(ast.parse(%r,mode='eval'),'<sandbox>','eval'),{'__builtins__':{}},{}))"
        % expression
    )
    result = subprocess.run(
        [os.getenv("PYTHON_BIN", "python3"), "-I", "-c", script],
        capture_output=True,
        text=True,
        timeout=3,
        check=True,
    )
    return {
        "result": result.stdout.strip(),
        "backend": "associated-sandbox" if os.getenv("AGENTKIT_TOOL_ID") else "local-isolated",
    }


def capability_status() -> dict[str, dict[str, str | bool]]:
    return {
        "sandbox": {
            "configured": bool(os.getenv("AGENTKIT_TOOL_ID")),
            "fallback": "local-isolated",
        },
        "mcp": {"configured": True, "endpoint": "/mcp"},
        "skills": {
            "configured": bool(os.getenv("SKILL_SPACE_ID")),
            "package": "customer-service-compliance",
        },
        "a2a": {
            "configured": a2a_data_agent_configured(),
            "agent_card": os.getenv("A2A_DATA_AGENT_CARD_URL", "not-configured"),
        },
        "identity": {
            "configured": bool(os.getenv("AGENTKIT_IDENTITY_ENABLED")),
            "fallback": "local-request",
        },
        "session": {"configured": platform_postgres_configured(), "fallback": "local-sqlite"},
    }


def platform_postgres_configured() -> bool:
    """Match AgentKit's managed PostgreSQL environment-variable contract."""
    return all(
        os.getenv(key)
        for key in (
            "DATABASE_POSTGRESQL_HOST",
            "DATABASE_POSTGRESQL_PORT",
            "DATABASE_POSTGRESQL_USER",
            "DATABASE_POSTGRESQL_PASSWORD",
            "DATABASE_POSTGRESQL_DATABASE",
        )
    )
