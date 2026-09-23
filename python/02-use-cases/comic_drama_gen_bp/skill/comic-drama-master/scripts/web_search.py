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
Web search tool for comic-drama-master skill.

The document of this tool see: https://www.volcengine.com/docs/85508/1650263

Usage:
    python scripts/web_search.py <query>
"""

import json
import os
import sys

from veadk.utils.logger import get_logger
from veadk.utils.volcengine_sign import ve_request

logger = get_logger(__name__)


def web_search(query: str) -> list[str]:
    """Search a query in websites.

    Args:
        query: The query to search.

    Returns:
        A list of result documents.
    """
    if not query:
        logger.error("Query is empty.")
        return []

    # Import get_aksk from the same scripts directory
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from get_aksk import get_aksk

    try:
        cred = get_aksk()
    except RuntimeError as e:
        logger.error(f"Failed to get AK/SK: {e}")
        return []

    ak = cred["access_key"]
    sk = cred["secret_key"]
    session_token = cred["session_token"]

    response = ve_request(
        request_body={
            "Query": query,
            "SearchType": "web",
            "Count": 5,
            "NeedSummary": True,
        },
        action="WebSearch",
        ak=ak,
        sk=sk,
        service="volc_torchlight_api",
        version="2025-01-01",
        region="cn-beijing",
        host="mercury.volcengineapi.com",
        header={"X-Security-Token": session_token},
    )

    try:
        results: list = response["Result"]["WebResults"]
        final_results = []
        for result in results:
            final_results.append(result["Summary"].strip())
        return final_results
    except Exception as e:
        logger.error(f"Web search failed {e}, response body: {response}")
        return [response]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: python web_search.py <query>")
        sys.exit(1)

    query = sys.argv[1]
    results = web_search(query)
    print(json.dumps(results, ensure_ascii=False, indent=2))
