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

"""Zoom an image by chaining resize and crop operations.

This script is designed for agent-friendly "zoom" usage where the final result
is typically produced by:

1. Resize the source image.
2. Crop a target region from the resized image.

The generated process string looks like:
  image/resize,.../crop,...
"""

import argparse
import base64
import json
import os
import re
import sys
import warnings
from typing import Optional

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")

import tos
from tos.exceptions import TosClientError, TosServerError

COLOR_RE = re.compile(r"^[0-9A-Fa-f]{6}$")
VALID_GRAVITIES = {
    "northwest",
    "north",
    "northeast",
    "west",
    "center",
    "east",
    "southwest",
    "south",
    "southeast",
}


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


def maybe_print_json(raw: bytes) -> bool:
    try:
        text = raw.decode("utf-8")
        data = json.loads(text)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return True
    except Exception:
        return False


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


def build_process_value(args: argparse.Namespace) -> str:
    resize_parts = []
    if args.resize_w is not None:
        resize_parts.append(f"w_{args.resize_w}")
    if args.resize_h is not None:
        resize_parts.append(f"h_{args.resize_h}")
    if args.resize_l is not None:
        resize_parts.append(f"l_{args.resize_l}")
    if args.resize_s is not None:
        resize_parts.append(f"s_{args.resize_s}")
    if args.resize_wp is not None:
        resize_parts.append(f"wp_{args.resize_wp}")
    if args.resize_hp is not None:
        resize_parts.append(f"hp_{args.resize_hp}")
    if args.resize_p is not None:
        resize_parts.append(f"p_{args.resize_p}")
    if args.resize_area is not None:
        resize_parts.append(f"area_{args.resize_area}")
    if args.resize_mode:
        resize_parts.append(f"m_{args.resize_mode}")
    if args.resize_color:
        resize_parts.append(f"color_{args.resize_color.upper()}")

    crop_parts = []
    if args.crop_w is not None:
        crop_parts.append(f"w_{args.crop_w}")
    if args.crop_h is not None:
        crop_parts.append(f"h_{args.crop_h}")
    if args.crop_l is not None:
        crop_parts.append(f"l_{args.crop_l}")
    if args.crop_s is not None:
        crop_parts.append(f"s_{args.crop_s}")
    if args.x is not None:
        crop_parts.append(f"x_{args.x}")
    if args.y is not None:
        crop_parts.append(f"y_{args.y}")
    if args.gravity:
        crop_parts.append(f"g_{args.gravity}")

    process = "image/resize," + ",".join(resize_parts)
    if crop_parts:
        process += "/crop," + ",".join(crop_parts)
    return process


def main() -> None:
    parser = argparse.ArgumentParser(description="Zoom image by resize + crop")
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument("--resize-w", type=int, default=None, help="Resize width")
    parser.add_argument("--resize-h", type=int, default=None, help="Resize height")
    parser.add_argument("--resize-l", type=int, default=None, help="Resize long side")
    parser.add_argument("--resize-s", type=int, default=None, help="Resize short side")
    parser.add_argument(
        "--resize-wp", type=int, default=None, help="Resize width percentage"
    )
    parser.add_argument(
        "--resize-hp", type=int, default=None, help="Resize height percentage"
    )
    parser.add_argument("--resize-p", type=int, default=None, help="Resize percentage")
    parser.add_argument(
        "--resize-area", type=int, default=None, help="Resize area in pixels"
    )
    parser.add_argument(
        "--resize-mode",
        type=str,
        default="fill",
        help="Resize mode, e.g. fill, pad, lfit, mfit",
    )
    parser.add_argument(
        "--resize-color",
        type=str,
        default=None,
        help="Optional resize background color for pad-like modes, e.g. FFFFFF",
    )
    parser.add_argument("--crop-w", type=int, default=None, help="Crop width")
    parser.add_argument("--crop-h", type=int, default=None, help="Crop height")
    parser.add_argument("--crop-l", type=int, default=None, help="Crop long side")
    parser.add_argument("--crop-s", type=int, default=None, help="Crop short side")
    parser.add_argument("--x", type=int, default=None, help="Crop x offset")
    parser.add_argument("--y", type=int, default=None, help="Crop y offset")
    parser.add_argument(
        "--gravity",
        type=str,
        default="center",
        help="Crop gravity: northwest/north/northeast/west/center/east/southwest/south/southeast",
    )
    parser.add_argument(
        "--output", type=str, default=None, help="Local output file path"
    )
    parser.add_argument(
        "--saveas-bucket", type=str, default=None, help="Save result to this bucket"
    )
    parser.add_argument(
        "--saveas-object", type=str, default=None, help="Save result as this object key"
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved request and exit")
    args = parser.parse_args()

    if not any(
        value is not None
        for value in (
            args.resize_w,
            args.resize_h,
            args.resize_l,
            args.resize_s,
            args.resize_wp,
            args.resize_hp,
            args.resize_p,
            args.resize_area,
        )
    ):
        print("[ERROR] At least one resize argument must be provided.", file=sys.stderr)
        sys.exit(1)

    if args.resize_color and not COLOR_RE.match(args.resize_color):
        print(
            "[ERROR] --resize-color must be a 6-digit RGB hex string.", file=sys.stderr
        )
        sys.exit(1)

    if args.gravity not in VALID_GRAVITIES:
        print(
            f"[ERROR] --gravity must be one of: {', '.join(sorted(VALID_GRAVITIES))}",
            file=sys.stderr,
        )
        sys.exit(1)

    bucket = args.bucket or os.getenv("TOS_BUCKET") or (
        "<TOS_BUCKET>" if args.dry_run else get_env("TOS_BUCKET")
    )
    key = args.key or os.getenv("TOS_OBJECT_KEY") or (
        "<TOS_OBJECT_KEY>" if args.dry_run else get_env("TOS_OBJECT_KEY")
    )
    process_value = build_process_value(args)
    default_save_object = f"zoom_{os.path.basename(key)}"
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
    output_path = None if persist_to_tos else args.output or default_save_object

    plan = {
        "ok": True,
        "operation": "image_zoom",
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

    if not args.json:
        print(f"[INFO] process = {process_value}")

    if persist_to_tos:
        encoded_bucket = base64.urlsafe_b64encode(resolved_save_bucket.encode()).decode()
        encoded_object = base64.urlsafe_b64encode(resolved_save_object.encode()).decode()
        if not args.json:
            print(
                f"[INFO] Processing {bucket}/{key} -> {resolved_save_bucket}/{resolved_save_object}"
            )
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
        except Exception:
            data = {"raw": raw.decode("utf-8", errors="replace")}
        emit({**plan, "result": data}, args.json, "[OK] Save result:")
        return

    if not args.json:
        print(f"[INFO] Processing {bucket}/{key} -> {output_path}")
    try:
        client.get_object_to_file(
            bucket=bucket,
            key=key,
            file_path=output_path,
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

    size = os.path.getsize(output_path)
    emit(
        {**plan, "size": size},
        args.json,
        f"[OK] Output saved to {output_path} ({size} bytes)",
    )


if __name__ == "__main__":
    main()
