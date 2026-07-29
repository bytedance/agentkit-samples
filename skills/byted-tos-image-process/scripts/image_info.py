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
"""Example script: get image information from TOS using the Python SDK.

Calls TOS image processing with `process="image/info"` and prints metadata.
If the service returns JSON, the script prints that JSON. If the service returns
raw image bytes instead, the script falls back to local parsing for basic info.

Environment variables:
  - TOS_ACCESS_KEY        Access key ID (AK) or STS AccessKeyId
  - TOS_SECRET_KEY        Secret access key (SK) or STS SecretAccessKey
  - TOS_SECURITY_TOKEN    (optional) STS session token
  - TOS_ENDPOINT          TOS endpoint, e.g. https://tos-cn-beijing.volces.com
  - TOS_REGION            TOS region, e.g. cn-beijing
  - TOS_BUCKET            Bucket name that stores the image
  - TOS_OBJECT_KEY        Object key of the image file in the bucket

This script supports:
  - local save: saves the response body locally when `--output` is provided
  - save back to TOS: via `get_object(..., save_bucket=..., save_object=...)`

Note: The exact response schema is subject to the official TOS documentation.
"""

import argparse
import base64
import json
import os
import sys
import warnings
from pathlib import Path
from typing import Any
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


def load_json_file(path: str) -> object:
    with open(path, "rb") as f:
        raw = f.read()
    return json.loads(raw.decode("utf-8"))


def _is_likely_json(raw: bytes) -> bool:
    s = raw.lstrip()
    return s.startswith(b"{") or s.startswith(b"[")


def _sniff_image_kind(raw: bytes) -> Optional[str]:
    if raw.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if raw.startswith(b"GIF87a") or raw.startswith(b"GIF89a"):
        return "gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "webp"
    return None


def _parse_dimensions(raw: bytes) -> tuple[Optional[int], Optional[int]]:
    kind = _sniff_image_kind(raw)
    if kind == "png" and len(raw) >= 24:
        # IHDR chunk: width/height big-endian at offset 16.
        w = int.from_bytes(raw[16:20], "big")
        h = int.from_bytes(raw[20:24], "big")
        return w, h
    if kind == "gif" and len(raw) >= 10:
        # Logical Screen Width/Height little-endian at offset 6.
        w = int.from_bytes(raw[6:8], "little")
        h = int.from_bytes(raw[8:10], "little")
        return w, h
    if kind == "jpeg":
        # Scan for SOF marker (baseline/progressive) to read width/height.
        i = 2
        n = len(raw)
        while i + 1 < n:
            if raw[i] != 0xFF:
                i += 1
                continue
            # Skip padding FFs.
            while i < n and raw[i] == 0xFF:
                i += 1
            if i >= n:
                break
            marker = raw[i]
            i += 1
            # Standalone markers.
            if marker in (0xD8, 0xD9):
                continue
            if i + 1 >= n:
                break
            seg_len = int.from_bytes(raw[i : i + 2], "big")
            if seg_len < 2 or i + seg_len > n:
                break
            # SOF0/1/2/3/5/6/7/9/A/B/C/D/E/F
            if marker in (
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            ):
                # segment layout: [len(2)] [precision(1)] [height(2)] [width(2)] ...
                if i + 7 <= n:
                    h = int.from_bytes(raw[i + 3 : i + 5], "big")
                    w = int.from_bytes(raw[i + 5 : i + 7], "big")
                    return w, h
                break
            i += seg_len
        return None, None
    # WebP parsing is chunk-type dependent; keep it unknown for now.
    return None, None


def _fallback_local_info(raw: bytes) -> dict[str, Any]:
    kind = _sniff_image_kind(raw) or "unknown"
    w, h = _parse_dimensions(raw)
    return {
        "source": "fallback-local-parse",
        "format": kind,
        "bytes": len(raw),
        "width": w,
        "height": h,
        "note": "TOS image/info did not return JSON; computed basic info from response bytes.",
    }


def prefixed_object(prefix: Optional[str], default_name: str) -> Optional[str]:
    if not prefix:
        return None
    return f"{prefix.rstrip('/')}/{default_name}"


def emit(payload: dict[str, Any], json_only: bool, heading: Optional[str] = None) -> None:
    if json_only:
        print(json.dumps(payload, ensure_ascii=False))
        return
    if heading:
        print(heading)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Get image info via TOS process=image/info"
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="If set, save the response body locally using get_object_to_file",
    )
    parser.add_argument(
        "--saveas-bucket", type=str, default=None, help="Persist result to this bucket"
    )
    parser.add_argument(
        "--saveas-object",
        type=str,
        default=None,
        help="Persist result as this object key",
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

    default_save_object = f"image_info_{os.path.basename(key).replace('/', '_')}.json"
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

    plan: dict[str, Any] = {
        "ok": True,
        "operation": "image_info",
        "bucket": bucket,
        "key": key,
        "process": "image/info",
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
                f"[INFO] Requesting image info for {bucket}/{key} -> {resolved_save_bucket}/{resolved_save_object}"
            )
            print("[INFO] process = image/info")

        encoded_bucket = base64.urlsafe_b64encode(resolved_save_bucket.encode()).decode()
        encoded_object = base64.urlsafe_b64encode(resolved_save_object.encode()).decode()

        try:
            output = client.get_object(
                bucket=bucket,
                key=key,
                process="image/info",
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
            print("[ERROR] Failed to parse response as JSON:", file=sys.stderr)
            print(exc, file=sys.stderr)
            print(raw[:200], file=sys.stderr)
            sys.exit(1)

        emit({**plan, "result": data}, args.json, "[OK] Image info saved to TOS:")
        return

    if args.output:
        output_path = args.output
        if not args.json:
            print(f"[INFO] Requesting image info for {bucket}/{key} -> {output_path}")
            print("[INFO] process = image/info")

        try:
            client.get_object_to_file(
                bucket=bucket, key=key, file_path=output_path, process="image/info"
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

        raw = Path(output_path).read_bytes()
        if _is_likely_json(raw):
            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                print("[ERROR] Failed to parse local file as JSON:", file=sys.stderr)
                print(exc, file=sys.stderr)
                sys.exit(1)
        else:
            data = _fallback_local_info(raw)

        emit({**plan, "result": data}, args.json, "[OK] Image info:")
        return

    if not args.json:
        print(f"[INFO] Requesting image info for {bucket}/{key} ...")
        print("[INFO] process = image/info")

    try:
        output = client.get_object(bucket=bucket, key=key, process="image/info")
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

    if _is_likely_json(raw):
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            print("[ERROR] Failed to parse response as JSON:", file=sys.stderr)
            print(exc, file=sys.stderr)
            print(raw[:200], file=sys.stderr)
            sys.exit(1)
    else:
        data = _fallback_local_info(raw)

    emit({**plan, "result": data}, args.json, "[OK] Image info:")


if __name__ == "__main__":
    main()
