"""Runtime role selection matching agentkit-cli MR 136, using signed IAM HTTP."""

from __future__ import annotations

import json
import re
import secrets
import string
import time
from typing import Any

import requests

from _http_client import (
    AgentKitHttpError,
    DEFAULT_TIMEOUT_SECONDS,
    _canonical_query,
    _env,
    _positive_int_env,
    direct_base_url,
    resolve_credentials,
    resolve_endpoint,
    resolve_provider,
    response_json,
    sign_headers,
)

RUNTIME_POLICY = "AgentKitDefaultRuntimeAccess"
ROLE_PREFIX = "AgentKit_Runtime_Default_ServiceRole_"


class IamHttpClient:
    """IAM Actions use GET query parameters, service iam, version 2018-01-01."""

    def __init__(self, region: str | None = None) -> None:
        self.endpoint = resolve_endpoint("volcengine")
        self.region = _env("VOLCENGINE_IAM_REGION") or region or self.endpoint.region
        self.host = _env("VOLCENGINE_IAM_HOST") or "open.volcengineapi.com"
        self.scheme = _env("VOLCENGINE_IAM_SCHEME") or "https"
        self.credentials = resolve_credentials("volcengine")
        self.timeout = _positive_int_env(
            "AGENTKIT_HTTP_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS
        )

    def call(self, action: str, params: dict[str, str]) -> dict[str, Any]:
        query = {"Action": action, "Version": "2018-01-01", **params}
        headers = sign_headers(
            "GET",
            self.host,
            query,
            b"",
            access_key=self.credentials.access_key,
            secret_key=self.credentials.secret_key,
            session_token=self.credentials.session_token,
            service="iam",
            region=self.region,
        )
        try:
            # Do not blindly replay IAM writes: CreateRole has no client_token.
            response = requests.get(
                f"{self.scheme}://{self.host}/?{_canonical_query(query)}",
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise RuntimeError(
                f"IAM {action}: network error; inspect IAM before retrying. "
                "CreateEnvironmentResource has not been submitted."
            ) from None
        result = response_json(action, response)
        value = result.get("Result") if "Result" in result else result
        if not isinstance(value, dict):
            raise RuntimeError(f"IAM {action}: expected a JSON object result")
        return value


def _get_role(api: IamHttpClient, role_name: str) -> dict[str, Any] | None:
    try:
        result = api.call("GetRole", {"RoleName": role_name})
    except AgentKitHttpError as exc:
        if re.search(r"RoleNotExist|NotFound", exc.code, re.I):
            return None
        raise
    role = result.get("Role")
    if not isinstance(role, dict) or role.get("RoleName") != role_name:
        raise RuntimeError("IAM GetRole returned an invalid or mismatched RoleName")
    return role


def _list_items(
    api: IamHttpClient,
    action: str,
    field: str,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen = set()
    while True:
        result = api.call(action, {**params, "Limit": "100", "Offset": str(len(items))})
        page = result.get(field)
        if page is None and action == "ListRoles":
            page = result.get("Roles")
        if page is None and result.get("Total") == 0:
            page = []
        if not isinstance(page, list) or not all(isinstance(row, dict) for row in page):
            raise RuntimeError(f"IAM {action}: missing or invalid {field}[]")
        signature = json.dumps(page, sort_keys=True)
        if page and signature in seen:
            raise RuntimeError(
                f"IAM {action}: repeated page; refusing partial selection"
            )
        seen.add(signature)
        items.extend(page)
        total = result.get("Total")
        if total is not None:
            try:
                total = int(total)
            except (ValueError, TypeError):
                raise RuntimeError(f"IAM {action}: invalid Total") from None
            if total < 0 or (not page and len(items) < total):
                raise RuntimeError(f"IAM {action}: incomplete pagination")
        # Match MR 136: IAM may return the complete list without Total and
        # ignore Offset. Only an explicit Total can require another page.
        if total is None or not page or len(items) >= total:
            return items


def _has_runtime_policy(api: IamHttpClient, role_name: str) -> bool:
    policies = _list_items(
        api,
        "ListAttachedRolePolicies",
        "AttachedPolicyMetadata",
        {"RoleName": role_name},
    )
    for policy in policies:
        if (
            not isinstance(policy.get("PolicyName"), str)
            or not policy["PolicyName"].strip()
        ):
            raise RuntimeError(
                "IAM ListAttachedRolePolicies returned an invalid PolicyName"
            )
    return any(
        policy["PolicyName"].strip().lower() == RUNTIME_POLICY.lower()
        and policy.get("PolicyType", "System") == "System"
        for policy in policies
    )


def _trust_policy(service: str) -> str:
    return json.dumps(
        {
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["sts:AssumeRole"],
                    "Principal": {
                        "Service": [
                            "vefaas_dev" if "stg" in service.lower() else "vefaas"
                        ]
                    },
                }
            ]
        },
        separators=(",", ":"),
    )


def select_runtime_role(api: IamHttpClient, role_name: str | None = None) -> str:
    """Validate an explicit role, or reuse/create a role with the Runtime policy."""
    if role_name:
        if _get_role(api, role_name) is None:
            raise RuntimeError(f"Configured Runtime role {role_name} does not exist")
        # Explicit customer roles retain their existing trust and policies.
        return role_name

    roles = _list_items(api, "ListRoles", "RoleMetadata", {})
    names = []
    for role in roles:
        name = role.get("RoleName")
        if not isinstance(name, str) or not name.strip():
            raise RuntimeError("IAM ListRoles returned an invalid RoleName")
        names.append(name.strip())
    for name in names:
        if _has_runtime_policy(api, name):
            return name

    for _ in range(10):
        name = ROLE_PREFIX + "".join(
            secrets.choice(string.ascii_lowercase + string.digits) for _ in range(7)
        )
        if name in names or _get_role(api, name) is not None:
            continue
        role = api.call(
            "CreateRole",
            {
                "RoleName": name,
                "DisplayName": name,
                "TrustPolicyDocument": _trust_policy(api.endpoint.service),
            },
        ).get("Role")
        if not isinstance(role, dict) or role.get("RoleName") != name:
            raise RuntimeError(f"IAM CreateRole returned no matching role for {name}")
        try:
            api.call(
                "AttachRolePolicy",
                {
                    "RoleName": name,
                    "PolicyName": RUNTIME_POLICY,
                    "PolicyType": "System",
                },
            )
        except AgentKitHttpError as exc:
            if re.search(r"\bConflict\b", exc.code, re.I):
                for delay in (0, 0.1, 0.3, 0.9):
                    if delay:
                        time.sleep(delay)
                    if _has_runtime_policy(api, name):
                        return name
            raise RuntimeError(
                f"Runtime role {name} was created but policy attachment failed: {exc}. "
                "Inspect this role before retrying; CreateEnvironmentResource was not submitted."
            ) from exc
        return name
    raise RuntimeError("Unable to generate a unique AgentKit Runtime role name")


def prepare_runtime_role(
    role_name: str | None, *, dry_run: bool, region: str | None = None
) -> str | None:
    """Only Volcengine TOP can select IAM in the same authenticated account."""
    if direct_base_url() or resolve_provider() != "volcengine":
        return role_name
    if dry_run:
        return role_name or "<auto-selected-runtime-role>"
    return select_runtime_role(IamHttpClient(region), role_name)
