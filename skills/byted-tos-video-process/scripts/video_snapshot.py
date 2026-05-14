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
"""Example script: take a single snapshot from a TOS video using the Python SDK.

Reads configuration from environment variables and optional CLI args,
constructs a `process="video/snapshot,..."` rule string, and either:
  - saves the returned image locally (default), or
  - if `--saveas-bucket`/`--saveas-object` is provided, lets TOS persist
    the snapshot to the specified object and prints the JSON result.
"""

import argparse
import base64
import json
import os
import sys
from typing import Any, Optional

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


def build_process_rule(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.time is not None:
        parts.append(f"t_{args.time}")
    if args.width is not None:
        parts.append(f"w_{args.width}")
    if args.height is not None:
        parts.append(f"h_{args.height}")
    if args.mode:
        parts.append(f"m_{args.mode}")
    if args.output_format:
        parts.append(f"f_{args.output_format}")
    if args.auto_rotate:
        parts.append(f"ar_{args.auto_rotate}")
    if parts:
        return "video/snapshot," + ",".join(parts)
    return "video/snapshot"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Take a single video snapshot using the TOS Python SDK",
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument("--time", type=int, help="Snapshot time in milliseconds")
    parser.add_argument("--width", type=int, help="Snapshot width in pixels")
    parser.add_argument("--height", type=int, help="Snapshot height in pixels")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["fast"],
        help="Snapshot mode: fast or precise (default precise)",
    )
    parser.add_argument(
        "--output-format",
        dest="output_format",
        choices=["jpg", "png"],
        help="Output image format",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Local output file (default: snapshot_<time>ms.<fmt>)",
    )
    parser.add_argument(
        "--saveas-bucket",
        type=str,
        help="If set, persist snapshot to this bucket instead of saving locally",
    )
    parser.add_argument(
        "--saveas-object",
        type=str,
        help="If set, persist snapshot as this object key instead of saving locally",
    )
    parser.add_argument(
        "--auto-rotate",
        dest="auto_rotate",
        choices=["auto", "w", "h"],
        help="Auto rotate mode",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved request and exit")
    args = parser.parse_args()

    bucket = args.bucket or get_env("TOS_BUCKET")
    key = args.key or get_env("TOS_OBJECT_KEY")
    process_value = build_process_rule(args)

    saveas_bucket = args.saveas_bucket or os.getenv("TOS_SAVEAS_BUCKET")
    saveas_object = args.saveas_object or os.getenv("TOS_SAVEAS_OBJECT")
    persist_to_tos = bool(saveas_bucket or saveas_object)

    time_part: Any = args.time if args.time is not None else "0"
    fmt = args.output_format or "jpg"

    if persist_to_tos:
        resolved_bucket = saveas_bucket or bucket
        resolved_object = saveas_object or f"snapshot_{time_part}ms.{fmt}"
        resolved_output = None
    else:
        resolved_bucket = None
        resolved_object = None
        resolved_output = args.output or f"snapshot_{time_part}ms.{fmt}"

    if args.dry_run:
        payload = {
            "ok": True,
            "operation": "video_snapshot",
            "bucket": bucket,
            "key": key,
            "process": process_value,
            "mode": "save_to_tos" if persist_to_tos else "save_local",
            "output_path": resolved_output,
            "saveas_bucket": resolved_bucket,
            "saveas_object": resolved_object,
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    client = create_client()

    if persist_to_tos:
        if not args.json:
            print(
                f"[INFO] Requesting snapshot for {bucket}/{key} -> {resolved_bucket}/{resolved_object}",
            )
            print(f"[INFO] process = {process_value}")

        try:
            encoded_bucket = base64.urlsafe_b64encode(resolved_bucket.encode()).decode()
            encoded_object = base64.urlsafe_b64encode(resolved_object.encode()).decode()
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
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] Unexpected error: {exc}", file=sys.stderr)
            sys.exit(1)

        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print(
                "[ERROR] Failed to parse snapshot save result as JSON:", file=sys.stderr
            )
            print(exc, file=sys.stderr)
            print(raw[:200], file=sys.stderr)
            sys.exit(1)

        if args.json:
            print(
                json.dumps(
                    {
                        "ok": True,
                        "operation": "video_snapshot",
                        "bucket": bucket,
                        "key": key,
                        "process": process_value,
                        "mode": "save_to_tos",
                        "saveas_bucket": resolved_bucket,
                        "saveas_object": resolved_object,
                        "result": data,
                    },
                    ensure_ascii=False,
                )
            )
            return

        print("[OK] Snapshot saved to TOS:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    if not args.json:
        print(f"[INFO] Requesting snapshot for {bucket}/{key} -> {resolved_output}")
        print(f"[INFO] process = {process_value}")

    try:
        client.get_object_to_file(
            bucket=bucket,
            key=key,
            file_path=resolved_output,
            process=process_value,
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
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        size = os.path.getsize(resolved_output)
    except OSError:
        size = -1

    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "operation": "video_snapshot",
                    "bucket": bucket,
                    "key": key,
                    "process": process_value,
                    "mode": "save_local",
                    "output_path": resolved_output,
                    "size": size,
                },
                ensure_ascii=False,
            )
        )
        return

    print(f"[OK] Snapshot saved to {resolved_output} ({size} bytes)")


if __name__ == "__main__":
    main()
