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
"""Example script: apply image watermark using TOS image processing.

Builds `process="image/watermark,..."` and either:
  - saves the processed image locally via `get_object_to_file` (default), or
  - saves it back to TOS via `get_object(..., save_bucket=..., save_object=...)`.

This implementation follows the official TOS watermark model:
  - text watermark: text/type/color/size/shadow/rotate/fill
  - image watermark: image plus optional base placement params
  - mixed watermark: specify both text and image, then use order/align/interval
  - base params: t/g/x/y/voffset

For advanced scenarios, repeated `--kv key=value` is still supported and will be
appended verbatim after the modeled parameters.

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
import re
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


FONT_TO_B64 = {
    "wqy-zenhei": "d3F5LXplbmhlaQ",
    "wqy-microhei": "d3F5LW1pY3JvaGVp",
    "fangzhengshusong": "ZmFuZ3poZW5nc2h1c29uZw",
    "fangzhengkaiti": "ZmFuZ3poZW5na2FpdGk",
    "fangzhengheiti": "ZmFuZ3poZW5naGVpdGk",
    "fangzhengfangsong": "ZmFuZ3poZW5nZmFuZ3Nvbmc",
    "droidsansfallback": "ZHJvaWRzYW5zZmFsbGJhY2s",
}

GRAVITY_CHOICES = ["nw", "north", "ne", "west", "center", "east", "sw", "south", "se"]


def urlsafe_b64_no_padding(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def normalize_hex_color(value: str) -> str:
    color = value.strip().lstrip("#").upper()
    if not re.fullmatch(r"[0-9A-F]{6}", color):
        raise ValueError(
            f"Invalid color '{value}', expected 6-digit hex RGB like FF0000"
        )
    return color


def encoded_or_raw(
    raw_value: Optional[str], encoded_value: Optional[str]
) -> Optional[str]:
    if encoded_value:
        return encoded_value.strip()
    if raw_value:
        return urlsafe_b64_no_padding(raw_value)
    return None


def build_modeled_pairs(args: argparse.Namespace) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []

    image_value = encoded_or_raw(args.image, args.image_b64)
    text_value = encoded_or_raw(args.text, args.text_b64)
    font_value = args.font_b64.strip() if args.font_b64 else None
    if args.font:
        font_value = FONT_TO_B64[args.font]

    if image_value:
        pairs.append(("image", image_value))
    if text_value:
        pairs.append(("text", text_value))
    if font_value:
        pairs.append(("type", font_value))
    if args.color:
        pairs.append(("color", normalize_hex_color(args.color)))
    if args.size is not None:
        pairs.append(("size", str(args.size)))
    if args.shadow is not None:
        pairs.append(("shadow", str(args.shadow)))
    if args.rotate is not None:
        pairs.append(("rotate", str(args.rotate)))
    if args.fill is not None:
        pairs.append(("fill", str(args.fill)))

    if args.opacity is not None:
        pairs.append(("t", str(args.opacity)))
    if args.gravity:
        pairs.append(("g", args.gravity))
    if args.x is not None:
        pairs.append(("x", str(args.x)))
    if args.y is not None:
        pairs.append(("y", str(args.y)))
    if args.voffset is not None:
        pairs.append(("voffset", str(args.voffset)))

    if args.order is not None:
        pairs.append(("order", str(args.order)))
    if args.align is not None:
        pairs.append(("align", str(args.align)))
    if args.interval is not None:
        pairs.append(("interval", str(args.interval)))

    return pairs


def build_process(op: str, pairs: list[tuple[str, str]]) -> str:
    base = f"image/{op}"
    if not pairs:
        return base
    return base + "," + ",".join([f"{k}_{v}" for k, v in pairs])


def default_output_path(key: str) -> str:
    base = os.path.basename(key)
    if not base:
        return "watermarked_output"
    return f"watermarked_{base}"


def emit(payload: dict, json_only: bool, heading=None) -> None:
    if json_only:
        print(json.dumps(payload, ensure_ascii=False))
        return
    if heading:
        print(heading)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply watermark via TOS process=image/watermark"
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Raw text watermark content; the script converts it to URL-safe Base64.",
    )
    parser.add_argument(
        "--text-b64",
        type=str,
        default=None,
        help="Pre-encoded URL-safe Base64 watermark text.",
    )
    parser.add_argument(
        "--font",
        choices=sorted(FONT_TO_B64.keys()),
        default=None,
        help="Font name for text watermark. Encoded automatically using the official mapping.",
    )
    parser.add_argument(
        "--font-b64",
        type=str,
        default=None,
        help="Pre-encoded URL-safe Base64 font identifier for the type parameter.",
    )
    parser.add_argument(
        "--color",
        type=str,
        default=None,
        help="Text color as RRGGBB or #RRGGBB.",
    )
    parser.add_argument("--size", type=int, default=None, help="Text size in px.")
    parser.add_argument(
        "--shadow", type=int, default=None, help="Text shadow opacity [0,100]."
    )
    parser.add_argument(
        "--rotate", type=int, default=None, help="Clockwise rotation angle [0,360]."
    )
    parser.add_argument(
        "--fill",
        type=int,
        choices=[0, 1],
        default=None,
        help="Whether to tile text watermark across the source image: 0 or 1.",
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help=(
            "Raw watermark image reference string. Must point to an object in the same bucket. "
            "For image preprocessing, pass the full reference including '?x-tos-process=...'; "
            "the script converts it to URL-safe Base64."
        ),
    )
    parser.add_argument(
        "--image-b64",
        type=str,
        default=None,
        help="Pre-encoded URL-safe Base64 watermark image reference string.",
    )
    parser.add_argument(
        "--opacity", type=int, default=None, help="Watermark opacity `t` in [0,100]."
    )
    parser.add_argument(
        "--gravity",
        choices=GRAVITY_CHOICES,
        default=None,
        help="Watermark placement `g`: nw, north, ne, west, center, east, sw, south, se.",
    )
    parser.add_argument(
        "--x", type=int, default=None, help="Horizontal margin `x` in px."
    )
    parser.add_argument(
        "--y", type=int, default=None, help="Vertical margin `y` in px."
    )
    parser.add_argument(
        "--voffset",
        type=int,
        default=None,
        help="Vertical offset from center line in px.",
    )
    parser.add_argument(
        "--order",
        type=int,
        choices=[0, 1],
        default=None,
        help="Mixed watermark order: 0 means image first, 1 means text first.",
    )
    parser.add_argument(
        "--align",
        type=int,
        choices=[0, 1, 2],
        default=None,
        help="Mixed watermark alignment: 0 top, 1 middle, 2 bottom.",
    )
    parser.add_argument(
        "--interval", type=int, default=None, help="Mixed watermark spacing in px."
    )
    parser.add_argument(
        "--kv",
        action="append",
        default=[],
        help="Advanced watermark option appended verbatim as key=value -> key_value.",
    )
    parser.add_argument("--output", type=str, default=None, help="Local output file")
    parser.add_argument(
        "--saveas-bucket", type=str, default=None, help="Save result to this bucket"
    )
    parser.add_argument(
        "--saveas-object", type=str, default=None, help="Save result as this object key"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the generated process string and exit without calling TOS.",
    )
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON only"
    )
    args = parser.parse_args()

    if args.text and args.text_b64:
        print("[ERROR] Use only one of --text or --text-b64.", file=sys.stderr)
        sys.exit(1)
    if args.font and args.font_b64:
        print("[ERROR] Use only one of --font or --font-b64.", file=sys.stderr)
        sys.exit(1)
    if args.image and args.image_b64:
        print("[ERROR] Use only one of --image or --image-b64.", file=sys.stderr)
        sys.exit(1)

    client = create_client()
    bucket = args.bucket or get_env("TOS_BUCKET")
    key = args.key or get_env("TOS_OBJECT_KEY")

    try:
        pairs = build_modeled_pairs(args)
        pairs.extend(parse_kv_list(args.kv))
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    has_modeled_source = bool(
        args.text or args.text_b64 or args.image or args.image_b64
    )
    has_advanced_source = any(k in {"text", "image"} for k, _ in pairs)
    if not has_modeled_source and not has_advanced_source:
        print(
            "[ERROR] Specify a watermark source with --text/--text-b64/--image/--image-b64, "
            "or provide advanced --kv text=... / --kv image=... parameters.",
            file=sys.stderr,
        )
        sys.exit(1)

    process_value = build_process("watermark", pairs)
    plan = {
        "ok": True,
        "operation": "image_watermark",
        "bucket": bucket,
        "key": key,
        "process": process_value,
        "saveas_bucket": args.saveas_bucket or bucket
        if (args.saveas_bucket or args.saveas_object)
        else None,
        "saveas_object": args.saveas_object,
    }
    if args.dry_run:
        emit(plan, args.json, "[OK] Resolved request:")
        return

    save_bucket = args.saveas_bucket
    save_object = args.saveas_object
    persist_to_tos = bool(save_bucket or save_object)

    if persist_to_tos:
        save_bucket = save_bucket or bucket
        if not save_object:
            save_object = f"watermarked_{os.path.basename(key)}"

        if not args.json:
            print(f"[INFO] Watermarking {bucket}/{key} -> {save_bucket}/{save_object}")
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

        emit(
            {
                **plan,
                "saveas_bucket": save_bucket,
                "saveas_object": save_object,
                "result": data,
            },
            args.json,
            "[OK] Image saved to TOS:",
        )
        return

    output_path = args.output or default_output_path(key)
    if not args.json:
        print(f"[INFO] Watermarking {bucket}/{key} -> {output_path}")
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
        {**plan, "output_path": output_path, "size": size},
        args.json,
        f"[OK] Image saved to {output_path} ({size} bytes)",
    )


if __name__ == "__main__":
    main()
