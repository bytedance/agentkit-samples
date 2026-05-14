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
"""Example script: get video information from TOS using the Python SDK.

Reads configuration from environment variables and/or CLI arguments and calls the
`videoInfo` operation by issuing a `get_object` request with `process="video/info"`.

Environment variables:
  - TOS_ACCESS_KEY        Access key ID (AK) or STS AccessKeyId
  - TOS_SECRET_KEY        Secret access key (SK) or STS SecretAccessKey
  - TOS_SECURITY_TOKEN    (optional) STS session token
  - TOS_ENDPOINT          TOS endpoint, e.g. https://tos-cn-beijing.volces.com
  - TOS_REGION            TOS region, e.g. cn-beijing
  - TOS_BUCKET            Bucket name that stores the video
  - TOS_OBJECT_KEY        Object key of the video file in the bucket
"""

import argparse
import json
import os
import sys
from typing import Optional

import tos
from tos.exceptions import TosClientError, TosServerError


def get_env(name: str, required: bool = True, default: Optional[str] = None) -> str:
    """Read an environment variable or exit with an error if required and missing."""
    value = os.getenv(name, default)
    if required and not value:
        print(f"[ERROR] Environment variable {name} is required.", file=sys.stderr)
        sys.exit(1)
    return value  # type: ignore[return-value]


def create_client() -> tos.TosClientV2:
    """Initialize a TosClientV2 using AK/SK (and optional STS token)."""
    ak = get_env("TOS_ACCESS_KEY")
    sk = get_env("TOS_SECRET_KEY")
    endpoint = get_env("TOS_ENDPOINT")
    region = get_env("TOS_REGION")
    security_token = os.getenv("TOS_SECURITY_TOKEN")

    return tos.TosClientV2(
        ak=ak,
        sk=sk,
        endpoint=endpoint,
        region=region,
        security_token=security_token,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Get video info via TOS process=video/info")
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    args = parser.parse_args()

    client = create_client()
    bucket = args.bucket or get_env("TOS_BUCKET")
    key = args.key or get_env("TOS_OBJECT_KEY")

    if not args.json:
        print(f"[INFO] Requesting video info for {bucket}/{key} ...")

    try:
        output = client.get_object(bucket, key, process="video/info")
        raw = output.read()
    except TosServerError as e:
        print(
            f"[ERROR] TOS server error: code={e.code}, status={e.status_code}, "
            f"request_id={e.request_id}, message={e.message}",
            file=sys.stderr,
        )
        sys.exit(1)
    except TosClientError as e:
        print(f"[ERROR] TOS client error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        text = raw.decode("utf-8")
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        print("[ERROR] Failed to parse response as JSON:", file=sys.stderr)
        print(exc, file=sys.stderr)
        print(raw[:200], file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "operation": "video_info",
                    "bucket": bucket,
                    "key": key,
                    "process": "video/info",
                    "result": data,
                },
                ensure_ascii=False,
            )
        )
        return

    print("[OK] Video info:")
    print(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
