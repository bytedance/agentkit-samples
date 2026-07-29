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
"""Image understanding entrypoint for TOS image processing.

Uses the image/understanding sync operation to invoke a VLM (Vision Language Model)
for intelligent image comprehension.

Environment variables:
  - TOS_ACCESS_KEY, TOS_SECRET_KEY, TOS_SECURITY_TOKEN(optional)
  - TOS_ENDPOINT, TOS_REGION
  - TOS_BUCKET
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
        socket_timeout=120,
    )


def b64url_encode(data: str) -> str:
    return base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")


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
        description="TOS image understanding (VLM) entrypoint"
    )
    parser.add_argument("--key", type=str, required=True, help="Image object key")
    parser.add_argument(
        "--bucket", type=str, default=None, help="TOS bucket (default: TOS_BUCKET env)"
    )
    parser.add_argument("--prompt", type=str, required=True, help="Prompt for VLM")
    parser.add_argument(
        "--model", type=str, default="doubao-seed-1.6-vision", help="VLM model name"
    )
    parser.add_argument(
        "--detail",
        type=str,
        default=None,
        choices=["auto", "low", "high"],
        help="Detail level",
    )
    parser.add_argument(
        "--saveas-bucket", type=str, default=None, help="Save result to this bucket"
    )
    parser.add_argument(
        "--saveas-object", type=str, default=None, help="Save result as this object key"
    )
    parser.add_argument("--output", type=str, default=None, help="Local output file")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved request and exit")
    args = parser.parse_args()

    bucket = args.bucket or os.getenv("TOS_BUCKET") or (
        "<TOS_BUCKET>" if args.dry_run else get_env("TOS_BUCKET")
    )
    key = args.key

    encoded_model = b64url_encode(args.model)
    encoded_prompt = b64url_encode(args.prompt)
    process = f"image/understanding,m_{encoded_model},p_{encoded_prompt}"
    if args.detail:
        process += f",d_{args.detail}"

    default_save_object = f"understanding_{os.path.basename(key)}.json"
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
    output_path = None if persist_to_tos else args.output

    plan = {
        "ok": True,
        "operation": "image_understanding",
        "bucket": bucket,
        "key": key,
        "process": process,
        "mode": "save_to_tos" if persist_to_tos else "save_local" if output_path else "read",
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
                f"[INFO] Understanding {bucket}/{key} -> {resolved_save_bucket}/{resolved_save_object}"
            )
            print(f"[INFO] process = {process}")

        encoded_bucket = base64.urlsafe_b64encode(resolved_save_bucket.encode()).decode()
        encoded_object = base64.urlsafe_b64encode(resolved_save_object.encode()).decode()

        try:
            output = client.get_object(
                bucket=bucket,
                key=key,
                process=process,
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
        except Exception:
            data = {"raw": raw.decode("utf-8", errors="replace")}
        emit({**plan, "result": data}, args.json, "[OK] Save result:")
        return

    if not args.json:
        print(f"[INFO] Understanding {bucket}/{key}")
        print(f"[INFO] process = {process}")

    try:
        output = client.get_object(
            bucket=bucket,
            key=key,
            process=process,
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

    text = raw.decode("utf-8", errors="replace")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            data = json.loads(text)
        except Exception:
            data = {"raw": text}
        emit({**plan, "result": data}, args.json, f"[OK] Output saved to {args.output}")
    else:
        try:
            data = json.loads(text)
        except Exception:
            data = {"raw": text}
        emit({**plan, "result": data}, args.json)


if __name__ == "__main__":
    main()
