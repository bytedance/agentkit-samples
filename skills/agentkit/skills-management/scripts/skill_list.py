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
import json
import logging
from typing import Any

from common import (
    get_agentkit_config,
    get_volcengine_credentials,
    list_skills_by_space_id,
    load_skill_env,
    parse_skill_space_ids,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("skill_list")


def _display_text(value: Any, max_len: int = 48) -> str:
    if value is None:
        return ""
    text = str(value).replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def list_skills(space_id: str | None = None) -> list[dict[str, Any]]:
    load_skill_env()
    skill_space_ids = parse_skill_space_ids(space_id)
    config = get_agentkit_config()
    credentials = get_volcengine_credentials()

    result: list[dict[str, Any]] = []
    for skill_space_id in skill_space_ids:
        items = list_skills_by_space_id(skill_space_id, credentials, config)
        result.append({"SkillSpaceId": skill_space_id, "Items": items})
    return result


def print_table(result: list[dict[str, Any]]) -> None:
    for space in result:
        sid = space["SkillSpaceId"]
        items = space["Items"]
        print(f"\nSkill Space: {sid}")
        print(f"{'Name':<25} {'Description':<50} {'SkillId':<24}")
        print("-" * 104)
        for item in items:
            name = _display_text(item.get("Name", "?"), 24)
            desc = _display_text(item.get("Description") or item.get("InnerDescription"), 49)
            skill_id = _display_text(item.get("SkillId") or item.get("Id"), 23)
            print(f"{name:<25} {desc:<50} {skill_id:<24}")


def main() -> None:
    parser = argparse.ArgumentParser(description="List skills in AgentKit skill spaces.")
    parser.add_argument(
        "--space-id",
        help="Optional comma-separated skill space IDs. Defaults to SKILL_SPACE_ID.",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    try:
        result = list_skills(args.space_id)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_table(result)
    except Exception as exc:
        logger.error("Failed to list skills: %s", exc)
        raise


if __name__ == "__main__":
    main()
