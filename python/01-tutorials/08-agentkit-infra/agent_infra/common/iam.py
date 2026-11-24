"""为 AgentKit Runtime 查询或创建固定名称的 IAM 角色。"""

from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.parse import urlencode

import requests

from .clients import (
    ControlConfig,
    HarnessInfraError,
    _decode_json,
    sign_headers,
)
from .config import DEFAULT_RUNTIME_ROLE_NAME

IAM_VERSION = "2018-01-01"
RUNTIME_POLICY = "AgentKitDefaultRuntimeAccess"
SANDBOX_POLICY_NAME = "AgentKitSelfHostSandboxAccess"
SANDBOX_POLICY_DOCUMENT = json.dumps(
    {
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["agentkit:SetSessionTtl", "agentkit:DeleteSession"],
                "Resource": ["*"],
            }
        ]
    },
    separators=(",", ":"),
)


class IamClient:
    """复用账号 AK/SK，通过 IAM TOP 的 GET Action 管理 Runtime Role。"""

    def __init__(self, control: ControlConfig) -> None:
        self.config = ControlConfig(
            access_key=control.access_key,
            secret_key=control.secret_key,
            session_token=control.session_token,
            region=os.getenv("HARNESS_INFRA_IAM_REGION", control.region).strip(),
            service="iam",
            host=os.getenv("HARNESS_INFRA_IAM_HOST", "open.volcengineapi.com").strip(),
            scheme=os.getenv("HARNESS_INFRA_IAM_SCHEME", "https").strip(),
            api_version=IAM_VERSION,
        )
        if self.config.scheme not in {"http", "https"}:
            raise RuntimeError("IAM scheme must be http or https")
        self.timeout = int(os.getenv("HARNESS_INFRA_HTTP_TIMEOUT_SECONDS", "60"))

    def call(self, action: str, params: dict[str, str]) -> dict[str, Any]:
        """发送 IAM Action；写操作不自动重放，避免创建不确定性。"""

        query = {"Action": action, "Version": IAM_VERSION, **params}
        headers = sign_headers(
            "GET",
            self.config.host,
            query,
            b"",
            config=self.config,
        )
        url = f"{self.config.scheme}://{self.config.host}/?{urlencode(query)}"
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=False,
            )
        except requests.RequestException:
            raise RuntimeError(f"IAM {action}: network error") from None
        return _decode_json(
            f"IAM {action}", response, top_envelope=True, allow_empty_result=True
        )


def _get_role(client: IamClient, role_name: str) -> dict[str, Any] | None:
    try:
        result = client.call("GetRole", {"RoleName": role_name})
    except HarnessInfraError as exc:
        if exc.status_code == 404 or re.search(
            r"RoleNotExist|NotFound", exc.code, re.IGNORECASE
        ):
            return None
        raise
    role = result.get("Role")
    if not isinstance(role, dict) or role.get("RoleName") != role_name:
        raise RuntimeError("IAM GetRole returned an invalid Role")
    return role


def _trust_policy(service_code: str) -> str:
    runtime_service = "vefaas_dev" if "stg" in service_code.lower() else "vefaas"
    return json.dumps(
        {
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["sts:AssumeRole"],
                    "Principal": {"Service": [runtime_service]},
                }
            ]
        },
        separators=(",", ":"),
    )


def ensure_runtime_role(
    control: ControlConfig,
    role_name: str = DEFAULT_RUNTIME_ROLE_NAME,
) -> tuple[str, bool]:
    """按固定名称复用角色；不存在时创建并附加 Runtime 系统策略。"""

    client = IamClient(control)
    if _get_role(client, role_name) is not None:
        return role_name, True

    result = client.call(
        "CreateRole",
        {
            "RoleName": role_name,
            "DisplayName": role_name,
            "TrustPolicyDocument": _trust_policy(control.service),
        },
    )
    role = result.get("Role")
    if not isinstance(role, dict) or role.get("RoleName") != role_name:
        raise RuntimeError("IAM CreateRole returned an invalid Role")
    try:
        client.call(
            "AttachRolePolicy",
            {
                "RoleName": role_name,
                "PolicyName": RUNTIME_POLICY,
                "PolicyType": "System",
            },
        )
    except HarnessInfraError as exc:
        if exc.status_code != 409 or exc.code != "PolicyAttachConflict":
            raise RuntimeError(
                f"Runtime role {role_name} was created, but policy attachment failed; "
                "inspect the role before retrying"
            ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"Runtime role {role_name} was created, but policy attachment failed; "
            "inspect the role before retrying"
        ) from exc
    return role_name, False


def ensure_sandbox_role_policy(
    control: ControlConfig,
    role_name: str = DEFAULT_RUNTIME_ROLE_NAME,
) -> None:
    """补充 Dispatcher 续租和回收 Sandbox Session 所需的内联权限。

    系统策略 AgentKitDefaultRuntimeAccess 不包含 SetSessionTtl/DeleteSession，
    缺少时会话复用失败（403 AccessDenied）。
    """

    client = IamClient(control)
    try:
        client.call(
            "CreatePolicy",
            {
                "PolicyName": SANDBOX_POLICY_NAME,
                "PolicyDocument": SANDBOX_POLICY_DOCUMENT,
                "Description": "AgentKit self-host dispatcher session TTL/reclaim access",
            },
        )
    except HarnessInfraError as exc:
        if exc.status_code != 409:
            raise
    try:
        client.call(
            "AttachRolePolicy",
            {
                "RoleName": role_name,
                "PolicyName": SANDBOX_POLICY_NAME,
                "PolicyType": "Custom",
            },
        )
    except HarnessInfraError as exc:
        if exc.status_code != 409:
            raise
