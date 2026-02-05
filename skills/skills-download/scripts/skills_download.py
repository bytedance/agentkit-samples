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

#!/usr/bin/env python3
import json
import os
import zipfile
import sys
import argparse
import shutil
import logging
from pathlib import Path
from typing import Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("skills_download")

try:
    from veadk.integrations.ve_tos.ve_tos import VeTOS
    from veadk.utils.volcengine_sign import ve_request
except ImportError:
    logger.error(
        "veadk package not found. Please ensure veadk-python is in your PYTHONPATH or installed."
    )
    sys.exit(1)


def download_skills(download_path: str, skill_names: Optional[list[str]] = None) -> str:
    """
    Download skills from skill spaces to local path.

    Args:
        download_path: Local path to save downloaded skills
        skill_names: Optional list of specific skill names to download. If None, download all skills.

    Returns:
        Success or error message
    """
    try:
        # Check for veadk auth imports
        try:
            from veadk.auth.veauth.utils import get_credential_from_vefaas_iam
        except ImportError:
            get_credential_from_vefaas_iam = None

        # Get skill space IDs from environment variable
        skill_space_ids = os.getenv("SKILL_SPACE_ID", "")
        skill_space_ids_list = [
            x.strip() for x in skill_space_ids.split(",") if x.strip()
        ]
        if not skill_space_ids_list:
            return "Error: SKILL_SPACE_ID environment variable is not set"

        logger.info(f"Downloading skills from skill spaces: {skill_space_ids_list}")

        # Get credentials
        access_key = os.getenv("VOLCENGINE_ACCESS_KEY")
        secret_key = os.getenv("VOLCENGINE_SECRET_KEY")
        session_token = ""

        if not (access_key and secret_key) and get_credential_from_vefaas_iam:
            try:
                cred = get_credential_from_vefaas_iam()
                access_key = cred.access_key_id
                secret_key = cred.secret_access_key
                session_token = cred.session_token
            except Exception as e:
                logger.warning(f"Failed to get credential from vefaas iam: {e}")

        if not (access_key and secret_key):
            return "Error: VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY not set and could not retrieve from IAM."

        # Get service configuration
        service = os.getenv("AGENTKIT_TOOL_SERVICE_CODE", "agentkit")
        region = os.getenv("AGENTKIT_TOOL_REGION", "cn-beijing")
        host = os.getenv("AGENTKIT_SKILL_HOST", "open.volcengineapi.com")

        # Ensure download path exists
        download_dir = Path(download_path).resolve()
        download_dir.mkdir(parents=True, exist_ok=True)

        # Initialize VeTOS client
        tos_client = VeTOS(
            ak=access_key,
            sk=secret_key,
            session_token=session_token,
            region=region,
        )

        all_downloaded_skills = []

        # Iterate through each skill space
        for skill_space_id in skill_space_ids_list:
            try:
                # Call ListSkillsBySpaceId API
                request_body = {
                    "SkillSpaceId": skill_space_id,
                    "InnerTags": {"source": "sandbox"},
                }
                logger.info(f"ListSkillsBySpaceId request body: {request_body}")

                response = ve_request(
                    request_body=request_body,
                    action="ListSkillsBySpaceId",
                    ak=access_key,
                    sk=secret_key,
                    service=service,
                    version="2025-10-30",
                    region=region,
                    host=host,
                    header={"X-Security-Token": session_token} if session_token else {},
                )

                if isinstance(response, str):
                    response = json.loads(response)

                list_skills_result = response.get("Result")
                if not list_skills_result:
                    logger.warning(
                        f"No result found for space {skill_space_id}. Response: {response}"
                    )
                    continue

                items = list_skills_result.get("Items", [])

                if not items:
                    logger.warning(f"No skills found in skill space: {skill_space_id}")
                    continue

                # Filter skills if skill_names is provided
                skills_to_download = []
                for item in items:
                    if not isinstance(item, dict):
                        continue

                    skill_name = item.get("Name")
                    tos_bucket = item.get("BucketName")
                    tos_path = item.get("TosPath")

                    if not skill_name or not tos_bucket or not tos_path:
                        continue

                    # If skill_names specified, only include matching skills
                    if skill_names is None or skill_name in skill_names:
                        skills_to_download.append(
                            {"name": skill_name, "bucket": tos_bucket, "path": tos_path}
                        )

                if not skills_to_download:
                    logger.warning(
                        f"No matching skills found in skill space: {skill_space_id}"
                    )
                    continue

                # Download each skill
                for skill in skills_to_download:
                    skill_name = skill["name"]
                    tos_bucket = skill["bucket"]
                    tos_path = skill["path"]

                    logger.info(
                        f"Downloading skill '{skill_name}' from tos://{tos_bucket}/{tos_path}"
                    )

                    # Download zip file
                    zip_path = download_dir / f"{skill_name}.zip"
                    success = tos_client.download(
                        bucket_name=tos_bucket,
                        object_key=tos_path,
                        save_path=str(zip_path),
                    )

                    if not success:
                        logger.warning(f"Failed to download skill '{skill_name}'")
                        continue

                    # Extract zip file
                    skill_extract_dir = download_dir / skill_name
                    try:
                        # Remove existing directory if exists
                        if skill_extract_dir.exists():
                            shutil.rmtree(skill_extract_dir)

                        with zipfile.ZipFile(zip_path, "r") as z:
                            z.extractall(path=str(download_dir))

                        logger.info(
                            f"Successfully extracted skill '{skill_name}' to {skill_extract_dir}"
                        )
                        all_downloaded_skills.append(skill_name)

                    except zipfile.BadZipFile:
                        logger.error(
                            f"Downloaded file for '{skill_name}' is not a valid zip"
                        )
                    except Exception as e:
                        logger.error(f"Failed to extract skill '{skill_name}': {e}")
                    finally:
                        # Delete zip file
                        if zip_path.exists():
                            zip_path.unlink()
                            logger.debug(f"Deleted zip file: {zip_path}")

            except Exception as e:
                logger.error(f"Failed to process skill space {skill_space_id}: {e}")
                continue

        if all_downloaded_skills:
            return f"Successfully downloaded {len(all_downloaded_skills)} skill(s): {', '.join(all_downloaded_skills)} to {download_path}"
        else:
            return "Failed to download any skills"

    except Exception as e:
        logger.error(f"Error when downloading skills: {e}")
        return f"Error when downloading skills: {str(e)}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download skills from VeADK skill space."
    )
    parser.add_argument(
        "download_path", help="Local directory path to save downloaded skills."
    )
    parser.add_argument(
        "--skills", nargs="*", help="Optional list of specific skill names to download."
    )

    args = parser.parse_args()

    result = download_skills(args.download_path, args.skills)
    print(result)
