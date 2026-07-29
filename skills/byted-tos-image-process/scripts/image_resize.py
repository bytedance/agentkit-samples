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
"""Example script: resize image using TOS image processing.

Builds `process="image/resize,..."` and either:
  - saves the processed image locally via `get_object_to_file` (default), or
  - saves it back to TOS via `get_object(..., save_bucket=..., save_object=...)`.

Common parameters:
  - w: target width
  - h: target height
  - m: resize mode (string; exact options are subject to official documentation)

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
import warnings
from typing import Optional

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

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
    return base + "," + ",".join([f"{k}_{v}" for k, v in pairs])


def default_output_path(key: str) -> str:
    base = os.path.basename(key)
    if not base:
        return "resized_output"
    return f"resized_{base}"


def prefixed_object(prefix: Optional[str], default_name: str) -> Optional[str]:
    if not prefix:
        return None
    return f"{prefix.rstrip('/')}/{default_name}"


def emit(payload: dict, json_only: bool, heading: Optional[str] = None) -> None:
    if json_only:
        print(json.dumps(payload, ensure_ascii=False))
        return
    if heading:
        print(heading)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resize image via TOS process=image/resize"
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--w", "--width", dest="width", type=int, default=None, help="Target width"
    )
    parser.add_argument(
        "--h", "--height", dest="height", type=int, default=None, help="Target height"
    )
    parser.add_argument(
        "--m", "--mode", dest="mode", type=str, default=None, help="Resize mode"
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

    bucket = args.bucket or os.getenv("TOS_BUCKET") or (
        "<TOS_BUCKET>" if args.dry_run else get_env("TOS_BUCKET")
    )
    key = args.key or os.getenv("TOS_OBJECT_KEY") or (
        "<TOS_OBJECT_KEY>" if args.dry_run else get_env("TOS_OBJECT_KEY")
    )

    pairs: list[tuple[str, str]] = []
    if args.width is not None:
        pairs.append(("w", str(args.width)))
    if args.height is not None:
        pairs.append(("h", str(args.height)))
    if args.mode:
        pairs.append(("m", args.mode))

    try:
        pairs.extend(parse_kv_list(args.kv))
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    process_value = build_process("resize", pairs)

    default_save_object = f"resized_{os.path.basename(key)}"
    save_bucket = args.saveas_bucket or os.getenv("TOS_SAVEAS_BUCKET")
    save_object = args.saveas_object or prefixed_object(
        os.getenv("TOS_SAVEAS_OBJECT_PREFIX"), default_save_object
    )
    explicit_saveas = bool(args.saveas_bucket or args.saveas_object)
    if explicit_saveas:
        persist_to_tos = True
    elif args.output:
        persist_to_tos = False
        save_bucket = None
        save_object = None
    else:
        persist_to_tos = bool(save_bucket or save_object)
    resolved_save_bucket = save_bucket or bucket if persist_to_tos else None
    resolved_save_object = save_object or default_save_object if persist_to_tos else None
    output_path = None if persist_to_tos else args.output or default_output_path(key)

    plan = {
        "ok": True,
        "operation": "image_resize",
        "bucket": bucket,
        "key": key,
        "process": process_value,
        "mode": "save_to_tos" if persist_to_tos else "save_local",
        "output_path": output_path,
        "saveas_bucket": resolved_save_bucket,
        "saveas_object": resolved_save_object,
    }
    if args.dry_run:
        emit(plan, args.json)
        return

    client = create_client()

    if persist_to_tos:
        if not args.json:
            print(
                f"[INFO] Resizing {bucket}/{key} -> {resolved_save_bucket}/{resolved_save_object}"
            )
            print(f"[INFO] process = {process_value}")

        encoded_bucket = base64.urlsafe_b64encode(resolved_save_bucket.encode()).decode()
        encoded_object = base64.urlsafe_b64encode(resolved_save_object.encode()).decode()

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

        emit(
            {
                **plan,
                "result": data,
            },
            args.json,
            "[OK] Image saved to TOS:",
        )
        return

    if not args.json:
        print(f"[INFO] Resizing {bucket}/{key} -> {output_path}")
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
    emit(
        {**plan, "size": size},
        args.json,
        f"[OK] Image saved to {output_path} ({size} bytes)",
    )


if __name__ == "__main__":
    main()
