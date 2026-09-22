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
#
# Ported from https://github.com/windrichie/byteplus-agentkit-samples
# (use-cases/harness_code_coach/scripts/publish_skill.py) by Windrichie.

"""Publish a local skill directory to the AgentKit Skill Hub.

Mirrors what the Skills Center console does: zip the skill directory, upload it
to the platform TOS bucket, then call the AgentKit `CreateSkill` OpenAPI with
the target skill space(s). Prints the skill ref to pass to
`agentkit harness set --skills ...`.

Usage:
    uv run python scripts/publish_skill.py --space ss-xxxxxxxxxxxx
    uv run python scripts/publish_skill.py --space ss-aaa --space ss-bbb --dir skill/code-coach
    uv run python scripts/publish_skill.py            # --space defaults to $SKILL_SPACE_ID

Configuration comes from the project's `.env` (loaded automatically, see
load_env_file) or the shell environment:
    BYTEPLUS_ACCESS_KEY / BYTEPLUS_SECRET_KEY   (or VOLCENGINE_ACCESS_KEY / ...)
    BYTEPLUS_REGION                             (default: ap-southeast-1)
    SKILL_SPACE_ID                              (default for --space)
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import requests
from dotenv import dotenv_values

logger = logging.getLogger(__name__)

# Which cloud this copy of the sample targets; CLOUD_PROVIDER in the
# environment overrides it.
DEFAULT_CLOUD_PROVIDER = "byteplus"
DEFAULT_REGIONS = {"byteplus": "ap-southeast-1", "volcengine": "cn-beijing"}

API_VERSION = "2025-10-30"  # AgentKit OpenAPI version used by veadk's register tool

# Directories searched for a `.env` file, highest priority first. The current
# working directory is always searched last.
_PROJECT_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE_DIRS = [_PROJECT_DIR]


def load_env_file() -> list[Path]:
    """Load environment variables from `.env` files (optional).

    Same precedence as the other examples in this repository: values in a
    `.env` file win over variables already exported in the shell; anything not
    present in any `.env` file falls back to the shell environment. Files are
    searched in the project directory and then the current working directory;
    when several exist, the project-side file wins for keys they share.
    Missing files are ignored.

    Returns the list of `.env` files that were loaded.
    """
    loaded: list[Path] = []
    seen: set[Path] = set()
    for directory in [*_ENV_FILE_DIRS, Path.cwd()]:
        env_file = (directory / ".env").resolve()
        if env_file in seen or not env_file.is_file():
            continue
        seen.add(env_file)
        loaded.append(env_file)

    merged: dict[str, str] = {}
    # Apply lowest-priority (CWD) first so higher-priority files override it.
    for env_file in reversed(loaded):
        merged.update(
            {k: v for k, v in dotenv_values(env_file).items() if v is not None}
        )
    os.environ.update(merged)

    for env_file in loaded:
        logger.info(f"[publish_skill] Loaded environment variables from {env_file}")
    return loaded


def skill_name_from_frontmatter(skill_dir: Path) -> str:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---"):
        sys.exit("SKILL.md has no frontmatter block")
    for line in text[3:].splitlines():
        if line.strip() == "---":
            break
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    sys.exit("SKILL.md frontmatter has no 'name:' field")


def zip_skill(skill_dir: Path, skill_name: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zipf:
        for path in sorted(skill_dir.rglob("*")):
            if path.is_file():
                # archive layout: <skill_name>/<relative path> (hub expects this)
                zipf.write(path, Path(skill_name) / path.relative_to(skill_dir))
    return buf.getvalue()


def _split_csv(value: str | None) -> list[str]:
    return [s.strip() for s in (value or "").split(",") if s.strip()]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_env_file()

    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--dir",
        default=str(_PROJECT_DIR / "skill" / "code-coach"),
        help="skill directory containing SKILL.md (default: skill/code-coach)",
    )
    ap.add_argument(
        "--space",
        action="append",
        help="skill space id (ss-...); repeat for several spaces. "
        "Defaults to SKILL_SPACE_ID from .env / the environment.",
    )
    args = ap.parse_args()
    spaces = args.space or _split_csv(os.getenv("SKILL_SPACE_ID"))
    if not spaces:
        sys.exit(
            "Pass --space ss-... or set SKILL_SPACE_ID (run `agentkit skill spaces` to list them)"
        )

    provider = (os.getenv("CLOUD_PROVIDER") or DEFAULT_CLOUD_PROVIDER).lower()
    if provider not in DEFAULT_REGIONS:
        sys.exit(
            f"Unsupported CLOUD_PROVIDER '{provider}' (expected byteplus or volcengine)"
        )
    os.environ["CLOUD_PROVIDER"] = provider  # VeTOS picks its TOS endpoint from this

    if provider == "byteplus":
        ak = os.getenv("BYTEPLUS_ACCESS_KEY") or os.getenv("VOLCENGINE_ACCESS_KEY")
        sk = os.getenv("BYTEPLUS_SECRET_KEY") or os.getenv("VOLCENGINE_SECRET_KEY")
        cred_hint = "BYTEPLUS_ACCESS_KEY / BYTEPLUS_SECRET_KEY"
        region = (
            os.getenv("AGENTKIT_TOOL_REGION")
            or os.getenv("BYTEPLUS_REGION")
            or DEFAULT_REGIONS[provider]
        )
        sts_host = "open.byteplusapi.com"
        sld = "byteplusapi"
    else:
        ak = os.getenv("VOLCENGINE_ACCESS_KEY")
        sk = os.getenv("VOLCENGINE_SECRET_KEY")
        cred_hint = "VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY"
        region = (
            os.getenv("AGENTKIT_TOOL_REGION")
            or os.getenv("VOLCENGINE_REGION")
            or DEFAULT_REGIONS[provider]
        )
        sts_host = "sts.volcengineapi.com"
        sld = "volcengineapi"
    if not (ak and sk):
        sys.exit(f"Set {cred_hint} in .env or the environment")

    # veadk is imported only now: it snapshots CLOUD_PROVIDER and credentials
    # at import time, so the environment must be fully populated first.
    from veadk.integrations.ve_tos.ve_tos import VeTOS
    from veadk.utils.volcengine_sign import ve_request

    skill_dir = Path(args.dir)
    if not (skill_dir / "SKILL.md").is_file():
        sys.exit(f"{skill_dir}/SKILL.md not found")
    skill_name = skill_name_from_frontmatter(skill_dir)

    # 1. who am I (needed for the platform bucket name)
    ident = ve_request(
        request_body={},
        action="GetCallerIdentity",
        ak=ak,
        sk=sk,
        service="sts",
        version="2018-01-01",
        region=region,
        host=sts_host,
    )
    if isinstance(ident, str):
        ident = json.loads(ident)
    account_id = ident["Result"]["AccountId"]

    # 2. upload the zip to the platform skill bucket
    bucket = f"agentkit-platform-{region}-{account_id}-skill"
    object_key = f"uploads/{datetime.now().strftime('%Y%m%d_%H%M%S')}/{skill_name}.zip"
    tos = VeTOS(ak=ak, sk=sk, session_token="", bucket_name=bucket, region=region)
    if not tos.bucket_exists(bucket) and not tos.create_bucket(bucket):
        sys.exit(
            f"Cannot access or create TOS bucket {bucket} — is TOS enabled on this account?"
        )
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir) / f"{skill_name}.zip"
        tmp.write_bytes(zip_skill(skill_dir, skill_name))
        tos.upload_file(file_path=str(tmp), bucket_name=bucket, object_key=object_key)
    tos_url = tos.build_tos_url(bucket_name=bucket, object_key=object_key)
    # upload_file() only logs on failure — prove the object landed with a signed
    # GET (the signed URL is method-scoped to GET; a HEAD would 403)
    probe = requests.get(
        tos.build_tos_signed_url(object_key=object_key, bucket_name=bucket),
        headers={"Range": "bytes=0-0"},
        timeout=15,
    )
    if probe.status_code not in (200, 206):
        sys.exit(f"Upload verification failed (HTTP {probe.status_code}) for {tos_url}")
    print(f"uploaded {skill_name}.zip -> {tos_url}")

    # 3. create the skill in the hub, attached to the requested space(s)
    resp = ve_request(
        request_body={"TosUrl": tos_url, "SkillSpaces": spaces},
        action="CreateSkill",
        ak=ak,
        sk=sk,
        service=os.getenv("AGENTKIT_TOOL_SERVICE_CODE", "agentkit"),
        version=API_VERSION,
        region=region,
        host=f"agentkit.{region}.{sld}.com",
    )
    if isinstance(resp, str):
        resp = json.loads(resp)
    err = resp.get("ResponseMetadata", {}).get("Error")
    if err:
        sys.exit(f"CreateSkill failed: {err}")
    result = resp.get("Result", resp)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    skill_id = result.get("Id", "<s-...>") if isinstance(result, dict) else "<s-...>"
    print(f"\nNext: agentkit skill show {skill_id}      # wait until status is running")
    print(
        f"Then: agentkit harness set --skills {spaces[0]}:{skill_id}   # just this skill"
    )
    print(
        f"  or: agentkit harness set --skills {spaces[0]}               # whole space"
    )


if __name__ == "__main__":
    main()
