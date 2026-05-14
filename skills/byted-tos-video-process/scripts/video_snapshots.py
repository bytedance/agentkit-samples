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
"""Example script: take multiple snapshots from a TOS video using the Python SDK.

Two modes are supported:
- Explicit timestamps:   --timestamps 1000 5000 10000
- Interval-based:        --interval-ms 5000 --duration-ms 60000 [--max-snapshots N]

Snapshots can be saved locally or directly to TOS using save-as parameters.
"""

import argparse
import base64
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

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


def build_timestamps(args: argparse.Namespace) -> List[int]:
    if args.timestamps:
        return [int(t) for t in args.timestamps]

    if args.interval_ms and args.duration_ms:
        interval = int(args.interval_ms)
        duration = int(args.duration_ms)
        if interval <= 0 or duration <= 0:
            print(
                "[ERROR] interval-ms and duration-ms must be positive.", file=sys.stderr
            )
            sys.exit(1)
        max_snaps = int(args.max_snapshots) if args.max_snapshots else None
        timestamps: List[int] = []
        current = interval
        while current < duration:
            timestamps.append(current)
            if max_snaps is not None and len(timestamps) >= max_snaps:
                break
            current += interval
        return timestamps

    print(
        "[ERROR] Either --timestamps or (--interval-ms and --duration-ms) must be provided.",
        file=sys.stderr,
    )
    sys.exit(1)


def build_process_value(
    ts: int, width: Optional[int], height: Optional[int], fmt: Optional[str]
) -> str:
    parts = [f"t_{ts}"]
    if width is not None:
        parts.append(f"w_{width}")
    if height is not None:
        parts.append(f"h_{height}")
    if fmt:
        parts.append(f"f_{fmt}")
    return "video/snapshot," + ",".join(parts)


def do_snapshot(
    ts: int,
    client: tos.TosClientV2,
    bucket: str,
    key: str,
    width: Optional[int],
    height: Optional[int],
    fmt: Optional[str],
    save_to_tos: bool,
    saveas_bucket: Optional[str],
    saveas_prefix: Optional[str],
    output_dir: str,
) -> dict:
    process_value = build_process_value(ts, width, height, fmt)

    if save_to_tos:
        save_bucket = saveas_bucket or bucket
        prefix = (saveas_prefix or "snapshots/").rstrip("/")
        save_object = f"{prefix}/frame_{ts}ms.{fmt or 'jpg'}"
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
            data = json.loads(raw.decode("utf-8"))
            return {
                "ok": True,
                "timestamp_ms": ts,
                "process": process_value,
                "mode": "save_to_tos",
                "saveas_bucket": save_bucket,
                "saveas_object": save_object,
                "result": data,
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "timestamp_ms": ts,
                "process": process_value,
                "mode": "save_to_tos",
                "error": str(exc),
            }

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"snapshot_{ts}ms.{fmt or 'jpg'}")

    try:
        client.get_object_to_file(
            bucket=bucket,
            key=key,
            file_path=output_path,
            process=process_value,
        )
        try:
            size = os.path.getsize(output_path)
        except OSError:
            size = -1
        return {
            "ok": True,
            "timestamp_ms": ts,
            "process": process_value,
            "mode": "save_local",
            "output_path": output_path,
            "size": size,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "timestamp_ms": ts,
            "process": process_value,
            "mode": "save_local",
            "output_path": output_path,
            "error": str(exc),
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Take multiple video snapshots using the TOS Python SDK",
    )
    parser.add_argument("--bucket", type=str, default=None, help="Override TOS_BUCKET")
    parser.add_argument("--key", type=str, default=None, help="Override TOS_OBJECT_KEY")
    parser.add_argument(
        "--timestamps",
        nargs="*",
        help="Explicit timestamps in ms, e.g. 1000 5000 10000",
    )
    parser.add_argument(
        "--interval-ms", type=int, help="Interval in ms between snapshots"
    )
    parser.add_argument(
        "--duration-ms", type=int, help="Total video duration in ms for interval mode"
    )
    parser.add_argument(
        "--max-snapshots", type=int, help="Maximum number of snapshots in interval mode"
    )
    parser.add_argument("--width", type=int, help="Snapshot width in pixels")
    parser.add_argument("--height", type=int, help="Snapshot height in pixels")
    parser.add_argument(
        "--format",
        choices=["jpg", "png"],
        default="jpg",
        help="Snapshot image format",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        default="snapshots",
        help="Deprecated alias of --output",
    )
    parser.add_argument(
        "--output",
        dest="output",
        default=None,
        help="Local directory to store snapshots",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Number of concurrent requests",
    )
    parser.add_argument("--save-to-tos", action="store_true", help="Deprecated flag; use --saveas-bucket/--saveas-object")
    parser.add_argument("--saveas-bucket", type=str, default=None, help="Save snapshots directly to this TOS bucket")
    parser.add_argument("--saveas-object", type=str, default=None, help="Save snapshots directly to this TOS key prefix")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved request and exit")
    args = parser.parse_args()

    timestamps = build_timestamps(args)
    bucket = args.bucket or get_env("TOS_BUCKET")
    key = args.key or get_env("TOS_OBJECT_KEY")
    output_dir = args.output or args.output_dir
    saveas_bucket = args.saveas_bucket or os.getenv("TOS_SAVEAS_BUCKET")
    saveas_prefix = args.saveas_object or os.getenv("TOS_SAVEAS_OBJECT_PREFIX")
    save_to_tos = args.save_to_tos or bool(saveas_bucket or saveas_prefix)

    plan = {
        "ok": True,
        "operation": "video_snapshots",
        "bucket": bucket,
        "key": key,
        "timestamps": timestamps,
        "format": args.format,
        "concurrency": args.concurrency,
        "mode": "save_to_tos" if save_to_tos else "save_local",
        "output": None if save_to_tos else output_dir,
        "saveas_bucket": saveas_bucket if save_to_tos else None,
        "saveas_object": saveas_prefix if save_to_tos else None,
    }

    if args.dry_run:
        if args.json:
            print(json.dumps(plan, ensure_ascii=False))
        else:
            print(json.dumps(plan, indent=2, ensure_ascii=False))
        return

    client = create_client()

    if not args.json:
        print(f"[INFO] Planning snapshots at timestamps (ms): {timestamps}")
        print(f"[INFO] Concurrency: {args.concurrency}, save_to_tos={save_to_tos}")

    results = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(
                do_snapshot,
                ts,
                client,
                bucket,
                key,
                args.width,
                args.height,
                args.format,
                save_to_tos,
                saveas_bucket,
                saveas_prefix,
                output_dir,
            )
            for ts in timestamps
        ]

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if not args.json:
                if result.get("ok"):
                    if result["mode"] == "save_to_tos":
                        print(f"[OK] ts={result['timestamp_ms']}ms saved to TOS: {result['saveas_bucket']}/{result['saveas_object']}")
                    else:
                        print(f"[OK] ts={result['timestamp_ms']}ms saved locally to {result['output_path']} ({result['size']} bytes)")
                else:
                    print(f"[ERROR] ts={result['timestamp_ms']}ms failed: {result['error']}")

    if args.json:
        print(
            json.dumps(
                {
                    **plan,
                    "results": sorted(results, key=lambda item: item["timestamp_ms"]),
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
