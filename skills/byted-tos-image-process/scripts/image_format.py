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
"""Example script: convert image format using TOS image processing.

Builds `process="image/format,..."` and either:
  - saves the processed image locally via `get_object_to_file` (default), or
  - saves it back to TOS via `get_object(..., save_bucket=..., save_object=...)`.

Common parameters:
  - f: output format (jpg/png/webp)
  - q: output quality (integer, range subject to official documentation)

The current service behavior used by this script expects the target format as a
plain segment, for example `image/format,webp,q_80`.

For any additional parameters, pass `--kv key=value` and the script will append it
as `key_value` in the process string.

Environment variables:
  - TOS_ACCESS_KEY, TOS_SECRET_KEY, TOS_SECURITY_TOKEN(optional)
  - TOS_ENDPOINT, TOS_REGION
  - TOS_BUCKET, TOS_OBJECT_KEY
Note: Parameter semantics are subject to the official TOS documentation.
"""

import argparse
import base64
import json
import os
import sys
from typing import Optional

import tos
from tos.exceptions import TosClientError, TosServerError


def get_env(name: str, required: bool = True, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if required and not value:
        print(f"[ERROR] Environment variable {name} is required.", file=sys.stderr)
        sys.exit(1)
    return value  # type: ignore[return-value]


def create_client() -> tos.TosClientV2:
    ak = get_env("TOS_ACCESS_KEY")
    sk = get_env("TOS_SECRET_KEY")
    endpoint = get_env("TOS_ENDPOINT")
    region = get_env("TOS_REGION")
    security_token = os.getenv("TOS_SECURITY_TOKEN")

    print(
        f"[INFO] Initializing TOS client for endpoint={endpoint}, region={region} ..."
    )
    return tos.TosClientV2(
        ak=ak,
        sk=sk,
        endpoint=endpoint,
        region=region,
        security_token=security_token,
    )


def parse_kv_list(items: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --kv '{item}', expected key=value")
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            raise ValueError(f"Invalid --kv '{item}', key is empty")
        pairs.append((k, v))
    return pairs


def build_process(op: str, pairs: list[tuple[str, str]]) -> str:
    base = f"image/{op}"
    if not pairs:
        return base
    if op == "format":
        rendered: list[str] = []
        for k, v in pairs:
            if k == "f":
                # The current service accepts the target format as a plain segment:
                # image/format,png
                rendered.append(v)
            else:
                rendered.append(f"{k}_{v}")
        return base + "," + ",".join(rendered)
    return base + "," + ",".join([f"{k}_{v}" for k, v in pairs])


def default_output_path(key: str, fmt: str) -> str:
    base = os.path.basename(key)
    name, _dot, _ext = base.partition(".")
    if not name:
        name = "output"
    return f"{name}.{fmt}"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert image format via TOS process=image/format"
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--f",
        dest="fmt",
        choices=["jpg", "png", "webp"],
        required=True,
        help="Target format",
    )
    parser.add_argument(
        "--q", dest="quality", type=int, default=None, help="Output quality"
    )
    parser.add_argument(
        "--kv", action="append", default=[], help="Extra process option: key=value"
    )
    parser.add_argument("--output", type=str, default=None, help="Local output file")
    parser.add_argument(
        "--saveas-bucket", type=str, default=None, help="Save result to this bucket"
    )
    parser.add_argument(
        "--saveas-object", type=str, default=None, help="Save result as this object key"
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved request and exit")
    args = parser.parse_args()

    client = create_client()
    bucket = args.bucket or get_env("TOS_BUCKET")
    key = args.key or get_env("TOS_OBJECT_KEY")

    pairs: list[tuple[str, str]] = [("f", args.fmt)]
    if args.quality is not None:
        pairs.append(("q", str(args.quality)))

    try:
        pairs.extend(parse_kv_list(args.kv))
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    process_value = build_process("format", pairs)

    save_bucket = args.saveas_bucket
    save_object = args.saveas_object
    persist_to_tos = bool(save_bucket or save_object)

    if persist_to_tos:
        save_bucket = save_bucket or bucket
        if not save_object:
            save_object = f"format_{os.path.basename(key)}.{args.fmt}"

        print(f"[INFO] Converting {bucket}/{key} -> {save_bucket}/{save_object}")
        print(f"[INFO] process = {process_value}")

        encoded_bucket = base64.urlsafe_b64encode(save_bucket.encode()).decode()
        encoded_object = base64.urlsafe_b64encode(save_object.encode()).decode()

        try:
            output = client.get_object(
                bucket=bucket,
                key=key,
                process=process_value,
                save_bucket=encoded_bucket,
                save_object=encoded_object,
            )
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

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print("[ERROR] Failed to parse save result as JSON:", file=sys.stderr)
            print(exc, file=sys.stderr)
            print(raw[:200], file=sys.stderr)
            sys.exit(1)

        print("[OK] Image saved to TOS:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    output_path = args.output or default_output_path(key, args.fmt)
    print(f"[INFO] Converting {bucket}/{key} -> {output_path}")
    print(f"[INFO] process = {process_value}")

    try:
        client.get_object_to_file(
            bucket=bucket, key=key, file_path=output_path, process=process_value
        )
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

    size = os.path.getsize(output_path)
    print(f"[OK] Image saved to {output_path} ({size} bytes)")


if __name__ == "__main__":
    main()
