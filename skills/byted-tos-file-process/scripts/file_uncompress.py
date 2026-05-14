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
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from tos_jobs_client import create_client_from_env


JOB_TYPE = "FileUncompress"
JOB_CATEGORY = "file_jobs"


def build_file_uncompress_detail(
    src_object: str,
    output_bucket: str,
    region: str,
    prefix: str = "",
    prefix_replaced: int = 0,
) -> dict:
    detail = {
        "Input": {
            "Object": src_object,
        },
        "FileUncompressConfig": {
            "Prefix": prefix,
            "PrefixReplaced": prefix_replaced,
        },
        "Output": {
            "Region": region,
            "Bucket": output_bucket,
        },
    }
    return detail


def fail(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)
    sys.exit(1)


def emit(payload: dict, json_only: bool, heading=None) -> None:
    if json_only:
        print(json.dumps(payload, ensure_ascii=False))
        return
    if heading:
        print(heading)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Uncompress a TOS archive via TOS file_jobs API"
    )
    parser.add_argument("--key", help="Source archive object key in TOS")
    parser.add_argument("--bucket", help="TOS bucket name (default: TOS_BUCKET env)")
    parser.add_argument("--output-bucket", dest="output_bucket", help="Deprecated alias of --saveas-bucket")
    parser.add_argument("--saveas-bucket", help="Output bucket (default: same as source)")
    parser.add_argument(
        "--prefix",
        default="",
        help="Target prefix for uncompressed files (default: empty)",
    )
    parser.add_argument(
        "--prefix-replaced",
        type=int,
        default=0,
        choices=[0, 1],
        help="0=keep original directory, 1=replace with prefix (default: 0)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Max wait time in seconds (default: 300)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Poll interval in seconds (default: 5)",
    )
    parser.add_argument("--wait", action="store_true", help="Wait for job completion")
    parser.add_argument("--job-id", help="Query an existing job instead of creating a new one")
    parser.add_argument("--validate", action="store_true", help="Validate arguments and payload only")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved payload and exit")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only")
    return parser.parse_args()


def main():
    args = parse_args()

    bucket = args.bucket or os.environ.get("TOS_BUCKET", "")
    if not bucket:
        fail("--bucket or TOS_BUCKET env is required")

    region = os.environ.get("TOS_REGION", "")
    if not region:
        fail("TOS_REGION env is required")

    client = create_client_from_env()
    client.bucket = bucket
    client.region = region

    if args.job_id:
        result = client.get_job(JOB_TYPE, args.job_id, job_category=JOB_CATEGORY)
        emit(
            {
                "ok": True,
                "operation": "file_uncompress_query",
                "bucket": bucket,
                "job_id": args.job_id,
                "job_type": JOB_TYPE,
                "job_category": JOB_CATEGORY,
                "result": result,
            },
            args.json,
            "[OK] Job query result:",
        )
        return

    key = args.key
    if not key:
        fail("--key is required")

    output_bucket = args.saveas_bucket or args.output_bucket or bucket

    detail = build_file_uncompress_detail(
        src_object=key,
        output_bucket=output_bucket,
        region=region,
        prefix=args.prefix,
        prefix_replaced=args.prefix_replaced,
    )

    plan = {
        "ok": True,
        "operation": "file_uncompress",
        "bucket": bucket,
        "key": key,
        "saveas_bucket": output_bucket,
        "prefix": args.prefix,
        "prefix_replaced": args.prefix_replaced,
        "job_type": JOB_TYPE,
        "job_category": JOB_CATEGORY,
        "detail": detail,
    }

    if args.validate or args.dry_run:
        emit(plan, args.json, "[OK] Resolved request:")
        return

    if not args.json:
        print(f"[INFO] Creating FileUncompress job: {key} -> {output_bucket}/{args.prefix}")
    resp = client.create_job(JOB_CATEGORY, JOB_TYPE, detail)

    job_id = resp.get("JobId", "")
    if not job_id:
        fail(f"No JobId in response: {resp}")

    result_payload = {
        **plan,
        "job_id": job_id,
        "create_response": resp,
    }

    if args.wait:
        if not args.json:
            print(f"[INFO] Waiting for job completion (timeout={args.timeout}s)...")
        result = client.wait_for_job(
            JOB_TYPE,
            job_id,
            timeout=args.timeout,
            interval=args.poll_interval,
            job_category=JOB_CATEGORY,
        )
        result_payload["final_result"] = result
        result_payload["state"] = result.get("State", "Unknown")
        emit(result_payload, args.json, "[OK] File uncompression result:")
        if result_payload["state"] != "Success":
            sys.exit(1)
        return

    emit(result_payload, args.json, "[OK] Job created:")


if __name__ == "__main__":
    main()
