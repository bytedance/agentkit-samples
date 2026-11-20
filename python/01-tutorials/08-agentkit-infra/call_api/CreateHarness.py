#!/usr/bin/env python3
"""Call Harness Infra CreateHarness with Volcengine AK/SK signing.

Example:
    export VOLCENGINE_ACCESS_KEY="..."
    export VOLCENGINE_SECRET_KEY="..."
    export VOLCENGINE_REGION="cn-beijing"
    export AGENTKIT_WORKSPACE_ID="ws-xxxxxxxxxxxxxxxxxxxx"

    python CreateHarness.py \
      --name "api-demo-harness" \
      --model-id "doubao-seed-evolving" \
      --model-base-url "https://ark.cn-beijing.volces.com/api/v3" \
      --runtime-id "r-xxxxxxxxxxxxxxxxxxxx" \
      --environment-id "env_xxxxxxxxxxxxxxxxxxxx"

Optional JSON fields accept raw JSON strings:
    --tools-json '[{"Type":"agent_toolset_20260401","Configs":[]}]'
    --skills-json '[{"type":"external_skill_package","source":"public_url","url":"https://api.skillhub.cn/api/v1/download?slug=%40ake%2Fdev-god"}]'
    --mcp-servers-json '[]'

Or put the full CreateHarness request body in a JSON file:
    python CreateHarness.py --body-json-file CreateHarnessPayload.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import quote, urlencode

API_VERSION = "2025-10-30"
DEFAULT_HOST = "open.volcengineapi.com"
DEFAULT_REGION = "cn-beijing"
DEFAULT_SERVICE = "agentkit"
DEFAULT_MODEL_ID = "doubao-seed-evolving"
DEFAULT_MODEL_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_EXTERNAL_SKILL_PACKAGE_URL = (
    "https://api.skillhub.cn/api/v1/download?slug=%40ake%2Fdev-god"
)
RETRYABLE_STATUS_CODES = {429, 503}


@dataclass(frozen=True)
class ControlConfig:
    access_key: str
    secret_key: str
    region: str
    service: str
    host: str
    scheme: str = "https"
    session_token: str = ""
    forward_env: str = ""
    api_version: str = API_VERSION
    workspace_id: str = ""
    timeout_seconds: int = 60
    retries: int = 2


class HarnessInfraError(RuntimeError):
    def __init__(
        self,
        operation: str,
        code: str,
        message: str,
        *,
        status_code: int,
        request_id: str = "",
    ) -> None:
        details = [f"HTTP {status_code}", code, message]
        if request_id:
            details.append(f"RequestId={request_id}")
        super().__init__(
            f"{operation} failed: " + ": ".join(item for item in details if item)
        )


@dataclass(frozen=True)
class TopResponse:
    status_code: int
    headers: dict[str, str]
    body: bytes

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def int_env(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return value


def json_arg(value: str, field_name: str) -> Any:
    try:
        return json.loads(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{field_name} must be valid JSON") from exc


def json_object_arg(value: str, field_name: str) -> dict[str, Any]:
    parsed = json_arg(value, field_name)
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError(f"{field_name} must be a JSON object")
    return parsed


def json_list_arg(value: str, field_name: str) -> list[Any]:
    parsed = json_arg(value, field_name)
    if not isinstance(parsed, list):
        raise argparse.ArgumentTypeError(f"{field_name} must be a JSON list")
    return parsed


def json_file_arg(value: str, field_name: str) -> dict[str, Any]:
    path = Path(value)
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise argparse.ArgumentTypeError(f"{field_name} cannot be read: {exc}") from exc
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{field_name} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError(f"{field_name} must be a JSON object")
    return parsed


def hmac_sha256(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def canonical_query(query: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in sorted(query.items()):
        values = value if isinstance(value, list) else [value]
        for item in values:
            parts.append(
                f"{quote(str(key), safe='-_.~')}={quote(str(item), safe='-_.~')}"
            )
    return "&".join(parts)


def sign_headers(
    method: str,
    host: str,
    query: dict[str, Any],
    body: bytes,
    *,
    config: ControlConfig,
    path: str = "/",
) -> dict[str, str]:
    now = dt.datetime.now(dt.UTC)
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    date = timestamp[:8]
    payload_hash = hashlib.sha256(body).hexdigest()
    signed = {
        "content-type": "application/json",
        "host": host,
        "x-content-sha256": payload_hash,
        "x-date": timestamp,
    }
    if config.session_token:
        signed["x-security-token"] = config.session_token
    if config.forward_env:
        signed["x-forward-env"] = config.forward_env
    signed_names = ";".join(sorted(signed))
    canonical_headers = "".join(f"{name}:{signed[name]}\n" for name in sorted(signed))
    canonical_request = "\n".join(
        [
            method.upper(),
            path,
            canonical_query(query),
            canonical_headers,
            signed_names,
            payload_hash,
        ]
    )
    scope = f"{date}/{config.region}/{config.service}/request"
    string_to_sign = "\n".join(
        [
            "HMAC-SHA256",
            timestamp,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = hmac_sha256(
        hmac_sha256(
            hmac_sha256(
                hmac_sha256(config.secret_key.encode("utf-8"), date),
                config.region,
            ),
            config.service,
        ),
        "request",
    )
    signature = hmac.new(
        signing_key, string_to_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Host": host,
        "X-Date": timestamp,
        "X-Content-Sha256": payload_hash,
        "Authorization": (
            f"HMAC-SHA256 Credential={config.access_key}/{scope}, "
            f"SignedHeaders={signed_names}, Signature={signature}"
        ),
    }
    if config.session_token:
        headers["X-Security-Token"] = config.session_token
    if config.forward_env:
        headers["X-Forward-Env"] = config.forward_env
    return headers


def decode_top_result(
    operation: str,
    response: TopResponse,
) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        request_id = response.headers.get("request-id", "")
        raise HarnessInfraError(
            operation,
            "InvalidResponse",
            "non-JSON response",
            status_code=response.status_code,
            request_id=request_id,
        ) from None
    if not isinstance(payload, dict):
        raise HarnessInfraError(
            operation,
            "InvalidResponse",
            "response must be a JSON object",
            status_code=response.status_code,
        )
    metadata = payload.get("ResponseMetadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    error = metadata.get("Error")
    error = error if isinstance(error, dict) else {}
    request_id = str(
        metadata.get("RequestId") or response.headers.get("request-id") or ""
    )
    if error or not 200 <= response.status_code < 300:
        code = str(error.get("Code") or payload.get("code") or "HTTPError")
        message = str(error.get("Message") or payload.get("message") or "")
        raise HarnessInfraError(
            operation,
            code,
            message,
            status_code=response.status_code,
            request_id=request_id,
        )
    result = payload.get("Result")
    if not isinstance(result, dict):
        raise HarnessInfraError(
            operation,
            "InvalidResponse",
            "TOP response is missing object Result",
            status_code=response.status_code,
            request_id=request_id,
        )
    return result


def top_call(
    action: str,
    body: dict[str, Any],
    *,
    config: ControlConfig,
) -> dict[str, Any]:
    query = {"Action": action, "Version": config.api_version}
    url = f"{config.scheme}://{config.host}/?{urlencode(query)}"
    payload = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )
    for attempt in range(config.retries + 1):
        headers = sign_headers(
            "POST",
            config.host,
            query,
            payload,
            config=config,
        )
        try:
            request = urlrequest.Request(
                url,
                headers=headers,
                data=payload,
                method="POST",
            )
            with urlrequest.urlopen(
                request,
                timeout=config.timeout_seconds,
            ) as raw_response:
                response = TopResponse(
                    status_code=raw_response.status,
                    headers={
                        key.lower(): value
                        for key, value in raw_response.headers.items()
                    },
                    body=raw_response.read(),
                )
        except urlerror.HTTPError as exc:
            response = TopResponse(
                status_code=exc.code,
                headers={key.lower(): value for key, value in exc.headers.items()},
                body=exc.read(),
            )
        except urlerror.URLError:
            if attempt < config.retries:
                time.sleep(min(8.0, 0.5 * (2**attempt)))
                continue
            raise RuntimeError(
                f"{action}: network error; retry with the same token and body"
            ) from None
        if response.status_code in RETRYABLE_STATUS_CODES and attempt < config.retries:
            time.sleep(min(8.0, 0.5 * (2**attempt)))
            continue
        return decode_top_result(action, response)
    raise AssertionError("unreachable")


def control_config_from_args(args: argparse.Namespace) -> ControlConfig:
    access_key = args.access_key or env(
        "HARNESS_INFRA_ACCESS_KEY",
        "VOLCENGINE_AGENTKIT_ACCESS_KEY",
        "VOLCENGINE_ACCESS_KEY",
    )
    secret_key = args.secret_key or env(
        "HARNESS_INFRA_SECRET_KEY",
        "VOLCENGINE_AGENTKIT_SECRET_KEY",
        "VOLCENGINE_SECRET_KEY",
    )
    if not access_key or not secret_key:
        raise RuntimeError(
            "set VOLCENGINE_ACCESS_KEY/VOLCENGINE_SECRET_KEY, or pass "
            "--access-key/--secret-key"
        )
    return ControlConfig(
        access_key=access_key,
        secret_key=secret_key,
        session_token=args.session_token
        or env(
            "HARNESS_INFRA_SESSION_TOKEN",
            "VOLCENGINE_AGENTKIT_SESSION_TOKEN",
            "VOLCENGINE_SESSION_TOKEN",
        ),
        forward_env=args.forward_env
        or env("HARNESS_INFRA_FORWARD_ENV", "VOLCENGINE_AGENTKIT_FORWARD_ENV"),
        region=args.region
        or env(
            "HARNESS_INFRA_REGION",
            "VOLCENGINE_AGENTKIT_REGION",
            "VOLCENGINE_REGION",
            default=DEFAULT_REGION,
        ),
        service=args.service
        or env(
            "HARNESS_INFRA_SERVICE",
            "VOLCENGINE_AGENTKIT_SERVICE",
            default=DEFAULT_SERVICE,
        ),
        host=args.host
        or env(
            "HARNESS_INFRA_CONTROL_HOST",
            "VOLCENGINE_AGENTKIT_HOST",
            default=DEFAULT_HOST,
        ),
        scheme=args.scheme
        or env(
            "HARNESS_INFRA_CONTROL_SCHEME",
            "VOLCENGINE_AGENTKIT_SCHEME",
            default="https",
        ),
        api_version=args.api_version
        or env(
            "HARNESS_INFRA_API_VERSION",
            "VOLCENGINE_AGENTKIT_API_VERSION",
            default=API_VERSION,
        ),
        workspace_id=args.workspace_id
        or env("HARNESS_INFRA_WORKSPACE_ID", "AGENTKIT_WORKSPACE_ID"),
        timeout_seconds=args.timeout_seconds,
        retries=args.retries,
    )


def create_harness_body(
    args: argparse.Namespace, config: ControlConfig
) -> dict[str, Any]:
    if args.body is not None:
        body = dict(args.body)
        if "ClientToken" not in body:
            body["ClientToken"] = args.client_token
        if config.workspace_id and "WorkspaceId" not in body:
            body["WorkspaceId"] = config.workspace_id
        return body

    payload = args.payload
    if payload is None:
        payload = {
            "model": args.model_id,
            "modelBaseUrl": args.model_base_url,
            "apiKey": "",
            "apiKeyName": "",
            "system": args.system,
            "skills": args.skills,
            "mcp": args.mcp_servers,
            "knowledge": [],
            "tools": args.tools,
            "webSearch": args.web_search,
        }
    body: dict[str, Any] = {
        "Name": args.name,
        "Description": args.description,
        "Model": {
            "Id": args.model_id,
            "BaseUrl": args.model_base_url,
        },
        "AgentLoop": args.agent_loop,
        "System": args.system,
        "Tools": args.tools,
        "McpServers": args.mcp_servers,
        "Skills": args.skills,
        "KnowledgeContexts": args.knowledge_contexts,
        "Payload": payload,
        "Metadata": args.metadata,
        "ClientToken": args.client_token,
    }
    if args.runtime_id:
        body["RuntimeId"] = args.runtime_id
    if args.environment_id:
        body["EnvironmentId"] = args.environment_id
    if config.workspace_id:
        body["WorkspaceId"] = config.workspace_id
    return body


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a Harness through Harness Infra TOP API."
    )
    parser.add_argument("--access-key", default="", help="Volcengine Access Key.")
    parser.add_argument("--secret-key", default="", help="Volcengine Secret Key.")
    parser.add_argument("--session-token", default="", help="Optional STS token.")
    parser.add_argument(
        "--forward-env",
        default="",
        help="Optional X-Forward-Env value, for example nice.",
    )
    parser.add_argument("--region", default="", help=f"Default: {DEFAULT_REGION}.")
    parser.add_argument("--service", default="", help=f"Default: {DEFAULT_SERVICE}.")
    parser.add_argument("--host", default="", help=f"Default: {DEFAULT_HOST}.")
    parser.add_argument("--scheme", choices=["http", "https"], default="")
    parser.add_argument("--api-version", default="", help=f"Default: {API_VERSION}.")
    parser.add_argument("--workspace-id", default="", help="Optional WorkspaceId.")
    parser.add_argument(
        "--body-json-file",
        dest="body",
        type=lambda value: json_file_arg(value, "body-json-file"),
        default=None,
        help=(
            "Path to a full CreateHarness request body JSON file. "
            "When set, body fields such as Name, Model, Skills, and Payload are "
            "read from the file; auth and TOP routing flags still come from CLI/env."
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=60)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument(
        "--name",
        default=f"api-demo-harness-{uuid.uuid4().hex[:8]}",
        help="Harness name.",
    )
    parser.add_argument(
        "--description",
        default="Created by call_api/CreateHarness.py",
        help="Harness description.",
    )
    parser.add_argument(
        "--model-id",
        default=env("HARNESS_MODEL_ID", "MODEL_ID", default=DEFAULT_MODEL_ID),
        help=f"Model id. Default: {DEFAULT_MODEL_ID}.",
    )
    parser.add_argument(
        "--model-base-url",
        default=env(
            "HARNESS_MODEL_BASE_URL",
            "MODEL_BASE_URL",
            default=DEFAULT_MODEL_BASE_URL,
        ),
        help=f"Model API base URL. Default: {DEFAULT_MODEL_BASE_URL}.",
    )
    parser.add_argument(
        "--agent-loop",
        choices=["adk", "codex", "piagent"],
        default=env("HARNESS_AGENT_LOOP", default="adk"),
    )
    parser.add_argument(
        "--system",
        default=env(
            "HARNESS_SYSTEM_PROMPT",
            default="你是一个通用任务执行智能体。请分析用户目标，按步骤完成任务并清晰说明结果。",
        ),
        help="Harness system prompt.",
    )
    parser.add_argument(
        "--runtime-id",
        default=env("HARNESS_RUNTIME_ID", "AGENTKIT_RUNTIME_ID"),
        help="Optional RuntimeId to bind the Harness.",
    )
    parser.add_argument(
        "--environment-id",
        default=env("HARNESS_ENVIRONMENT_ID", "AGENTKIT_ENVIRONMENT_ID"),
        help="Optional EnvironmentId to bind the Harness.",
    )
    parser.add_argument(
        "--tools-json",
        dest="tools",
        type=lambda value: json_list_arg(value, "tools-json"),
        default=[],
        help="CreateHarness Tools JSON list.",
    )
    parser.add_argument(
        "--skills-json",
        dest="skills",
        type=lambda value: json_list_arg(value, "skills-json"),
        default=[
            {
                "type": "external_skill_package",
                "source": "public_url",
                "url": DEFAULT_EXTERNAL_SKILL_PACKAGE_URL,
            }
        ],
        help="CreateHarness Skills JSON list. Defaults to the public dev-god zip package.",
    )
    parser.add_argument(
        "--mcp-servers-json",
        dest="mcp_servers",
        type=lambda value: json_list_arg(value, "mcp-servers-json"),
        default=[],
        help="CreateHarness McpServers JSON list.",
    )
    parser.add_argument(
        "--knowledge-contexts-json",
        dest="knowledge_contexts",
        type=lambda value: json_list_arg(value, "knowledge-contexts-json"),
        default=[],
        help="CreateHarness KnowledgeContexts JSON list.",
    )
    parser.add_argument(
        "--payload-json",
        dest="payload",
        type=lambda value: json_object_arg(value, "payload-json"),
        default=None,
        help="CreateHarness Payload JSON object. Defaults to a console-compatible payload.",
    )
    parser.add_argument(
        "--metadata-json",
        dest="metadata",
        type=lambda value: json_object_arg(value, "metadata-json"),
        default={
            "source": "call_api/CreateHarness.py",
            "agentkit.console.ark_key_name": "",
        },
        help="CreateHarness Metadata JSON object.",
    )
    parser.add_argument(
        "--disable-web-search",
        dest="web_search",
        action="store_false",
        default=True,
        help="Set generated Payload.webSearch to false.",
    )
    parser.add_argument(
        "--client-token",
        default=f"create-harness-{uuid.uuid4().hex}",
        help="Idempotency token. Reuse the same token only for an identical retry.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the CreateHarness body without sending the request.",
    )
    return parser


def main() -> None:
    args = parser().parse_args()
    if args.timeout_seconds < 1:
        raise RuntimeError("--timeout-seconds must be at least 1")
    if args.retries < 0:
        raise RuntimeError("--retries must be at least 0")
    config = control_config_from_args(args)
    body = create_harness_body(args, config)
    if args.dry_run:
        print(
            json.dumps(
                {"Action": "CreateHarness", "Body": body}, ensure_ascii=False, indent=2
            )
        )
        return
    result = top_call("CreateHarness", body, config=config)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
