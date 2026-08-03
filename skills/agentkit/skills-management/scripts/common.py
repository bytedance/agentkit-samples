#!/usr/bin/env python3
# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from veadk.utils.volcengine_sign import ve_request
except ImportError:
    logging.getLogger(__name__).error(
        "veadk package not found. Please ensure veadk-python is in your PYTHONPATH or installed."
    )
    sys.exit(1)

logger = logging.getLogger("agentkit_skills")

AGENTKIT_API_VERSION = "2025-10-30"


@dataclass(frozen=True)
class AgentKitConfig:
    service: str
    region: str
    host: str


@dataclass(frozen=True)
class VolcengineCredentials:
    access_key: str
    secret_key: str
    session_token: str = ""


def load_skill_env() -> None:
    """Load sandbox skill environment variables when python-dotenv is available."""
    skills_env = Path("/root/.skills_env")
    if skills_env.exists() and load_dotenv:
        load_dotenv(skills_env)


def parse_skill_space_ids(value: str | None = None) -> list[str]:
    raw = value if value is not None else os.getenv("SKILL_SPACE_ID", "")
    skill_space_ids = [x.strip() for x in raw.split(",") if x.strip()]
    if not skill_space_ids:
        raise ValueError("SKILL_SPACE_ID environment variable is not set")
    return skill_space_ids


def get_agentkit_config() -> AgentKitConfig:
    return AgentKitConfig(
        service=os.getenv("AGENTKIT_TOOL_SERVICE_CODE", "agentkit"),
        region=os.getenv("AGENTKIT_TOOL_REGION", "cn-beijing"),
        host=os.getenv("AGENTKIT_SKILL_HOST", "open.volcengineapi.com"),
    )


def get_volcengine_credentials() -> VolcengineCredentials:
    access_key = os.getenv("VOLCENGINE_ACCESS_KEY")
    secret_key = os.getenv("VOLCENGINE_SECRET_KEY")
    session_token = os.getenv("VOLCENGINE_SESSION_TOKEN", "")

    if access_key and secret_key:
        return VolcengineCredentials(access_key, secret_key, session_token)

    try:
        from veadk.auth.veauth.utils import get_credential_from_vefaas_iam
    except ImportError:
        get_credential_from_vefaas_iam = None

    if get_credential_from_vefaas_iam:
        try:
            cred = get_credential_from_vefaas_iam()
            return VolcengineCredentials(
                cred.access_key_id,
                cred.secret_access_key,
                cred.session_token or "",
            )
        except Exception as exc:
            logger.warning("Failed to get credential from vefaas iam: %s", exc)

    raise PermissionError(
        "VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY are not set in environment variables."
    )


def security_token_header(credentials: VolcengineCredentials) -> dict[str, str]:
    if credentials.session_token:
        return {"X-Security-Token": credentials.session_token}
    return {}


def call_agentkit_api(
    action: str,
    request_body: dict[str, Any],
    credentials: VolcengineCredentials,
    config: AgentKitConfig,
) -> dict[str, Any]:
    response = ve_request(
        request_body=request_body,
        action=action,
        ak=credentials.access_key,
        sk=credentials.secret_key,
        service=config.service,
        version=AGENTKIT_API_VERSION,
        region=config.region,
        host=config.host,
        header=security_token_header(credentials),
    )
    if isinstance(response, str):
        return json.loads(response)
    return response


def call_sts_api(
    action: str,
    request_body: dict[str, Any],
    credentials: VolcengineCredentials,
    region: str,
) -> dict[str, Any]:
    response = ve_request(
        request_body=request_body,
        action=action,
        ak=credentials.access_key,
        sk=credentials.secret_key,
        service="sts",
        version="2018-01-01",
        region=region,
        host="sts.volcengineapi.com",
        header=security_token_header(credentials),
    )
    if isinstance(response, str):
        return json.loads(response)
    return response


def list_skills_by_space_id(
    skill_space_id: str,
    credentials: VolcengineCredentials,
    config: AgentKitConfig,
) -> list[dict[str, Any]]:
    body = {"SkillSpaceId": skill_space_id, "InnerTags": {"source": "sandbox"}}
    logger.info("ListSkillsBySpaceId request body: %s", body)
    response = call_agentkit_api("ListSkillsBySpaceId", body, credentials, config)
    result = response.get("Result")
    if not result:
        logger.warning("No result found for space %s. Response: %s", skill_space_id, response)
        return []
    items = result.get("Items", [])
    if not isinstance(items, list):
        logger.warning("Unexpected Items value for space %s: %s", skill_space_id, items)
        return []
    return [item for item in items if isinstance(item, dict)]


def validate_zip_member(destination: Path, member_name: str) -> Path:
    target = (destination / member_name).resolve()
    destination_resolved = destination.resolve()
    if destination_resolved != target and destination_resolved not in target.parents:
        raise ValueError(f"Unsafe zip member path: {member_name}")
    return target
