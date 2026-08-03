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

import argparse
import logging
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from common import (
    call_agentkit_api,
    call_sts_api,
    get_agentkit_config,
    get_volcengine_credentials,
    load_skill_env,
    parse_skill_space_ids,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("register_skill")

try:
    import frontmatter
except ImportError:
    logger.error(
        "python-frontmatter is required. Please install it with 'pip install python-frontmatter'"
    )
    sys.exit(1)

try:
    from veadk.integrations.ve_tos.ve_tos import VeTOS
except ImportError:
    logger.error(
        "veadk package not found. Please ensure veadk-python is in your PYTHONPATH or installed."
    )
    sys.exit(1)


def _resolve_skill_path(skill_local_path: str) -> Path:
    working_dir = Path.cwd()
    raw = Path(skill_local_path).expanduser()
    if not raw.is_absolute():
        return (working_dir / raw).resolve()
    return raw.resolve()


def _read_skill_name(skill_path: Path) -> str:
    skill_readme = skill_path / "SKILL.md"
    try:
        skill = frontmatter.load(str(skill_readme))
        return skill.get("name", "") or skill_path.name
    except Exception as exc:
        raise ValueError(f"Failed to get skill name from {skill_readme}: {exc}") from exc


def _zip_skill(skill_path: Path, skill_name: str, zip_file_path: Path) -> None:
    logger.info("Zipping skill '%s' from '%s' to '%s'...", skill_name, skill_path, zip_file_path)
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _dirs, files in os.walk(skill_path):
            for file in files:
                file_path = Path(root) / file
                if file_path.resolve() == zip_file_path.resolve():
                    continue
                if any(part.startswith(".") for part in file_path.relative_to(skill_path).parts):
                    continue

                arcname = Path(skill_name) / file_path.relative_to(skill_path)
                zipf.write(file_path, arcname)


def register_skills_tool(skill_local_path: str, space_id: str | None = None) -> str:
    """Register a skill to remote skill spaces by uploading its zip package to TOS."""
    skill_path = _resolve_skill_path(skill_local_path)

    if not skill_path.exists() or not skill_path.is_dir():
        msg = f"Skill path '{skill_path}' does not exist or is not a directory."
        logger.error(msg)
        return msg

    skill_readme = skill_path / "SKILL.md"
    if not skill_readme.exists():
        msg = f"Skill path '{skill_path}' has no SKILL.md file."
        logger.error(msg)
        return msg

    try:
        load_skill_env()
        skill_space_ids = parse_skill_space_ids(space_id)
    except Exception as exc:
        msg = str(exc)
        logger.error(msg)
        return msg

    try:
        skill_name = _read_skill_name(skill_path)
    except ValueError as exc:
        msg = str(exc)
        logger.error(msg)
        return msg

    working_dir = Path.cwd()
    output_dir = working_dir / "outputs"
    output_dir.mkdir(exist_ok=True)
    zip_file_path = output_dir / f"{skill_name}.zip"

    try:
        _zip_skill(skill_path, skill_name, zip_file_path)

        config = get_agentkit_config()
        credentials = get_volcengine_credentials()

        res = call_sts_api("GetCallerIdentity", {}, credentials, config.region)
        try:
            account_id = res["Result"]["AccountId"]
        except (KeyError, TypeError) as exc:
            logger.error("Error occurred while getting account id: %s, response is %s", exc, res)
            return f"Error: Failed to get account id when registering skill '{skill_name}'."

        tos_bucket = f"agentkit-platform-{config.region}-{account_id}-skill"

        tos_client = VeTOS(
            ak=credentials.access_key,
            sk=credentials.secret_key,
            session_token=credentials.session_token,
            bucket_name=tos_bucket,
            region=config.region,
        )

        object_key = f"uploads/{datetime.now().strftime('%Y%m%d_%H%M%S')}/{skill_name}.zip"

        logger.info("Uploading zip to TOS bucket '%s' key '%s'...", tos_bucket, object_key)
        tos_client.upload_file(
            file_path=zip_file_path, bucket_name=tos_bucket, object_key=object_key
        )
        tos_url = tos_client.build_tos_url(bucket_name=tos_bucket, object_key=object_key)

        request_body = {"TosUrl": tos_url, "SkillSpaces": skill_space_ids}
        logger.debug("CreateSkill request body: %s", request_body)

        logger.info("Calling CreateSkill API...")
        response = call_agentkit_api("CreateSkill", request_body, credentials, config)

        logger.debug("CreateSkill response: %s", response)

        if "ResponseMetadata" in response and "Error" in response["ResponseMetadata"]:
            error_details = response["ResponseMetadata"]["Error"]
            msg = f"Failed to register skill '{skill_name}': {error_details}"
            logger.error(msg)
            return msg

        msg = f"Successfully registered skill '{skill_name}' to skill space {skill_space_ids}."
        logger.info(msg)
        return msg

    except Exception as exc:
        msg = f"Failed to register skill '{skill_name}': {exc}"
        logger.error(msg)
        return msg


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register a skill to AgentKit skill spaces.")
    parser.add_argument("skill_path", help="Path to the skill directory containing SKILL.md")
    parser.add_argument(
        "--space-id",
        help="Optional comma-separated skill space IDs. Defaults to SKILL_SPACE_ID.",
    )
    args = parser.parse_args()

    result = register_skills_tool(args.skill_path, args.space_id)
    print(result)
