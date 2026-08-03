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
import shutil
import sys
import zipfile
from pathlib import Path

from common import (
    get_agentkit_config,
    get_volcengine_credentials,
    list_skills_by_space_id,
    load_skill_env,
    parse_skill_space_ids,
    validate_zip_member,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("skills_download")

try:
    from veadk.integrations.ve_tos.ve_tos import VeTOS
except ImportError:
    logger.error(
        "veadk package not found. Please ensure veadk-python is in your PYTHONPATH or installed."
    )
    sys.exit(1)


def _safe_extract(zip_file: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_file, "r") as zipf:
        for member in zipf.infolist():
            validate_zip_member(destination, member.filename)
        zipf.extractall(path=str(destination))


def download_skills(download_path: str, skill_names: list[str] | None = None) -> str:
    """
    Download skills from skill spaces to local path.

    Args:
        download_path: Local path to save downloaded skills.
        skill_names: Optional list of specific skill names to download. If None, download all skills.

    Returns:
        Success or error message.
    """
    try:
        load_skill_env()
        skill_space_ids = parse_skill_space_ids()
        logger.info("Downloading skills from skill spaces: %s", skill_space_ids)

        config = get_agentkit_config()
        credentials = get_volcengine_credentials()

        download_dir = Path(download_path).resolve()
        download_dir.mkdir(parents=True, exist_ok=True)

        tos_client = VeTOS(
            ak=credentials.access_key,
            sk=credentials.secret_key,
            session_token=credentials.session_token,
            region=config.region,
        )

        all_downloaded_skills: list[str] = []

        for skill_space_id in skill_space_ids:
            try:
                items = list_skills_by_space_id(skill_space_id, credentials, config)

                if not items:
                    logger.warning("No skills found in skill space: %s", skill_space_id)
                    continue

                skills_to_download = []
                for item in items:
                    skill_name = item.get("Name")
                    tos_bucket = item.get("BucketName")
                    tos_path = item.get("TosPath")

                    if not skill_name or not tos_bucket or not tos_path:
                        continue

                    if skill_names is None or skill_name in skill_names:
                        skills_to_download.append(
                            {"name": skill_name, "bucket": tos_bucket, "path": tos_path}
                        )

                if not skills_to_download:
                    logger.warning(
                        "No matching skills found in skill space: %s", skill_space_id
                    )
                    continue

                for skill in skills_to_download:
                    skill_name = skill["name"]
                    tos_bucket = skill["bucket"]
                    tos_path = skill["path"]

                    logger.info(
                        "Downloading skill '%s' from tos://%s/%s",
                        skill_name,
                        tos_bucket,
                        tos_path,
                    )

                    zip_path = download_dir / f"{skill_name}.zip"
                    success = tos_client.download(
                        bucket_name=tos_bucket,
                        object_key=tos_path,
                        save_path=str(zip_path),
                    )

                    if not success:
                        logger.warning("Failed to download skill '%s'", skill_name)
                        continue

                    skill_extract_dir = download_dir / skill_name
                    try:
                        if skill_extract_dir.exists():
                            shutil.rmtree(skill_extract_dir)

                        _safe_extract(zip_path, download_dir)

                        logger.info(
                            "Successfully extracted skill '%s' to %s",
                            skill_name,
                            skill_extract_dir,
                        )
                        all_downloaded_skills.append(skill_name)

                    except zipfile.BadZipFile:
                        logger.error("Downloaded file for '%s' is not a valid zip", skill_name)
                    except Exception as exc:
                        logger.error("Failed to extract skill '%s': %s", skill_name, exc)
                    finally:
                        if zip_path.exists():
                            zip_path.unlink()
                            logger.debug("Deleted zip file: %s", zip_path)

            except Exception as exc:
                logger.error("Failed to process skill space %s: %s", skill_space_id, exc)
                continue

        if all_downloaded_skills:
            return (
                f"Successfully downloaded {len(all_downloaded_skills)} skill(s): "
                f"{', '.join(all_downloaded_skills)} to {download_path}"
            )
        return "Failed to download any skills"

    except Exception as exc:
        logger.error("Error when downloading skills: %s", exc)
        return f"Error when downloading skills: {str(exc)}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download skills from AgentKit skill spaces.")
    parser.add_argument("download_path", help="Local directory path to save downloaded skills.")
    parser.add_argument(
        "--skills", nargs="*", help="Optional list of specific skill names to download."
    )

    args = parser.parse_args()

    result = download_skills(args.download_path, args.skills)
    print(result)
