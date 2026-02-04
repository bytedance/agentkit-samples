#!/usr/bin/env python3
import json
import os
import zipfile
import sys
import argparse
from pathlib import Path
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("register_skill")

# Try to import veadk dependencies
# Assuming the script is run from a location where veadk is importable or in veadk-python directory
try:
    import frontmatter
except ImportError:
    logger.error(
        "python-frontmatter is required. Please install it with 'pip install python-frontmatter'"
    )
    sys.exit(1)

try:
    from veadk.integrations.ve_tos.ve_tos import VeTOS
    from veadk.utils.volcengine_sign import ve_request
except ImportError:
    logger.error(
        "veadk package not found. Please ensure veadk-python is in your PYTHONPATH or installed."
    )
    sys.exit(1)


def register_skills_tool(skill_local_path: str) -> str:
    """Register a skill to the remote skill space by uploading its zip package to TOS and calling the CreateSkill API.

    Args:
        skill_local_path (str): The local path of the skill directory.

    Returns:
        str: Result message indicating success or failure.
    """
    # Use current working directory as base
    working_dir = Path.cwd()

    raw = Path(skill_local_path).expanduser()
    if not raw.is_absolute():
        skill_path = (working_dir / raw).resolve()
    else:
        skill_path = raw.resolve()

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
        skill = frontmatter.load(str(skill_readme))
        skill_name = skill.get("name", "")
        if not skill_name:
            # Fallback to directory name if name not in frontmatter
            skill_name = skill_path.name
    except Exception as e:
        msg = f"Failed to get skill name from {skill_readme}: {e}"
        logger.error(msg)
        return msg

    # Create outputs directory if it doesn't exist to store the zip
    output_dir = working_dir / "outputs"
    output_dir.mkdir(exist_ok=True)

    zip_file_path = output_dir / f"{skill_name}.zip"

    logger.info(
        f"Zipping skill '{skill_name}' from '{skill_path}' to '{zip_file_path}'..."
    )
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(skill_path):
            for file in files:
                file_path = Path(root) / file
                # Ensure we don't zip the zip file itself
                if file_path.resolve() == zip_file_path.resolve():
                    continue
                # Skip hidden files/dirs (optional, but good practice)
                if any(
                    part.startswith(".")
                    for part in file_path.relative_to(skill_path).parts
                ):
                    continue

                arcname = Path(skill_name) / file_path.relative_to(skill_path)
                zipf.write(file_path, arcname)

    try:
        # Check for veadk auth imports
        try:
            from veadk.auth.veauth.utils import get_credential_from_vefaas_iam
        except ImportError:
            get_credential_from_vefaas_iam = None

        agentkit_tool_service = os.getenv("AGENTKIT_TOOL_SERVICE_CODE", "agentkit")
        agentkit_skill_host = os.getenv("AGENTKIT_SKILL_HOST", "open.volcengineapi.com")
        region = os.getenv("AGENTKIT_TOOL_REGION", "cn-beijing")

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

        # Get Account ID
        res = ve_request(
            request_body={},
            action="GetCallerIdentity",
            ak=access_key,
            sk=secret_key,
            service="sts",
            version="2018-01-01",
            region=region,
            host="sts.volcengineapi.com",
            header={"X-Security-Token": session_token} if session_token else {},
        )
        try:
            if isinstance(res, str):
                res = json.loads(res)
            account_id = res["Result"]["AccountId"]
        except (KeyError, TypeError) as e:
            logger.error(
                f"Error occurred while getting account id: {e}, response is {res}"
            )
            return f"Error: Failed to get account id when registering skill '{skill_name}'."

        tos_bucket = f"agentkit-platform-{region}-{account_id}-skill"

        tos_client = VeTOS(
            ak=access_key,
            sk=secret_key,
            session_token=session_token,
            bucket_name=tos_bucket,
            region=region,
        )

        object_key = (
            f"uploads/{datetime.now().strftime('%Y%m%d_%H%M%S')}/{skill_name}.zip"
        )

        logger.info(f"Uploading zip to TOS bucket '{tos_bucket}' key '{object_key}'...")
        tos_client.upload_file(
            file_path=zip_file_path, bucket_name=tos_bucket, object_key=object_key
        )
        tos_url = tos_client.build_tos_url(
            bucket_name=tos_bucket, object_key=object_key
        )

        skill_space_ids = os.getenv("SKILL_SPACE_ID", "")
        skill_space_ids_list = [
            x.strip() for x in skill_space_ids.split(",") if x.strip()
        ]

        request_body = {
            "TosUrl": tos_url,
            "SkillSpaces": skill_space_ids_list,
        }
        logger.debug(f"CreateSkill request body: {request_body}")

        logger.info("Calling CreateSkill API...")
        response = ve_request(
            request_body=request_body,
            action="CreateSkill",
            ak=access_key,
            sk=secret_key,
            service=agentkit_tool_service,
            version="2025-10-30",
            region=region,
            host=agentkit_skill_host,
            header={"X-Security-Token": session_token} if session_token else {},
        )

        if isinstance(response, str):
            response = json.loads(response)

        logger.debug(f"CreateSkill response: {response}")

        if "ResponseMetadata" in response and "Error" in response["ResponseMetadata"]:
            error_details = response["ResponseMetadata"]["Error"]
            msg = f"Failed to register skill '{skill_name}': {error_details}"
            logger.error(msg)
            return msg

        msg = f"Successfully registered skill '{skill_name}' to skill space {skill_space_ids_list}."
        logger.info(msg)
        return msg

    except Exception as e:
        msg = f"Failed to register skill '{skill_name}': {e}"
        logger.error(msg)
        return msg


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Register a skill to AgentKit skill space."
    )
    parser.add_argument(
        "skill_path", help="Path to the skill directory containing SKILL.md"
    )
    args = parser.parse_args()

    result = register_skills_tool(args.skill_path)
    print(result)
