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

"""
Get VolcEngine AK/SK credentials for comic-drama-master skill.

Priority order:
  1. Tool-specific env vars: TOOL_COMIC_DRAMA_ACCESS_KEY / TOOL_COMIC_DRAMA_SECRET_KEY
  2. Generic env vars: VOLCENGINE_ACCESS_KEY / VOLCENGINE_SECRET_KEY
  3. VeFaaS IAM credential (automatic when running inside VeFaaS)

Usage:
    python scripts/get_aksk.py
"""

import json
import logging
import os
import sys

logger = logging.getLogger(__name__)


def get_aksk() -> dict:
    """Get VolcEngine AK/SK/SessionToken credentials.

    Returns:
        A dict with keys: access_key, secret_key, session_token.

    Raises:
        RuntimeError: If AK/SK cannot be retrieved from any source.
    """
    ak = None
    sk = None
    session_token = ""

    # Priority 1: tool-specific environment variables
    ak = os.getenv("TOOL_COMIC_DRAMA_ACCESS_KEY")
    sk = os.getenv("TOOL_COMIC_DRAMA_SECRET_KEY")
    if ak and sk:
        logger.debug("Successfully got tool-specific AK/SK.")

    # Priority 2: generic VolcEngine environment variables
    if not (ak and sk):
        ak = os.getenv("VOLCENGINE_ACCESS_KEY")
        sk = os.getenv("VOLCENGINE_SECRET_KEY")
        if ak and sk:
            logger.debug(
                "Successfully got AK/SK from VOLCENGINE_ACCESS_KEY/SECRET_KEY."
            )

    # Priority 3: VeFaaS IAM (runs automatically inside VeFaaS runtime)
    if not (ak and sk):
        logger.debug("Get AK/SK from environment variables failed, trying VeFaaS IAM.")
        try:
            from veadk.auth.veauth.utils import get_credential_from_vefaas_iam

            credential = get_credential_from_vefaas_iam()
            ak = credential.access_key_id
            sk = credential.secret_access_key
            session_token = credential.session_token
            logger.debug("Successfully got AK/SK from VeFaaS IAM.")
        except Exception as e:
            logger.error(f"Failed to get credential from VeFaaS IAM: {e}")

    if not ak or not sk:
        raise RuntimeError(
            "AK/SK is empty. Please set VOLCENGINE_ACCESS_KEY and VOLCENGINE_SECRET_KEY "
            "environment variables, or run inside a VeFaaS environment."
        )

    return {
        "access_key": ak,
        "secret_key": sk,
        "session_token": session_token,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    try:
        cred = get_aksk()
        # Only print non-sensitive summary to stdout
        print(
            json.dumps(
                {
                    "access_key": cred["access_key"][:6] + "****",
                    "secret_key": "****",
                    "session_token": "(present)"
                    if cred["session_token"]
                    else "(empty)",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
