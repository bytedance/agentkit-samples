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


JOB_TYPE = "Concat"
JOB_CATEGORY = "media_jobs"


def build_concat_detail(
    first_object: str,
    fragments: list,
    output_bucket: str,
    output_object: str,
    region: str,
    container_format: str = "mp4",
    video_codec: str = "h264",
    audio_codec: str = "aac",
) -> dict:
    concat_fragments = [{"Object": f} for f in fragments]

    return {
        "Input": {"Object": first_object},
        "ConcatConfig": {
            "ConcatFragments": concat_fragments,
            "Container": {"Format": container_format},
            "Video": {"Codec": video_codec},
            "Audio": {"Codec": audio_codec},
        },
        "Output": {
            "Region": region,
            "Bucket": output_bucket,
            "Object": output_object,
        },
    }


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
        description="Concatenate video clips via TOS media_jobs API"
    )
    parser.add_argument("--key", help="First video fragment object key (required)")
    parser.add_argument("--bucket", help="TOS bucket name (default: TOS_BUCKET env)")
    parser.add_argument(
        "--fragments", help="Subsequent video fragment object keys, comma-separated"
    )
    parser.add_argument(
        "--output-key", dest="output_key", help="Deprecated alias of --saveas-object"
    )
    parser.add_argument(
        "--output-bucket",
        dest="output_bucket",
        help="Deprecated alias of --saveas-bucket",
    )
    parser.add_argument(
        "--saveas-object", help="Output object key (default: <key>_concat.mp4)"
    )
    parser.add_argument(
        "--saveas-bucket", help="Output bucket (default: same as source)"
    )
    parser.add_argument(
        "--format", default="mp4", help="Output container format (default: mp4)"
    )
    parser.add_argument(
        "--video-codec", default="h264", help="Video codec (default: h264)"
    )
    parser.add_argument(
        "--audio-codec", default="aac", help="Audio codec (default: aac)"
    )
    parser.add_argument("--wait", action="store_true", help="Wait for job completion")
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Max wait time in seconds (default: 600)",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=5,
        help="Poll interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--job-id", help="Query an existing job instead of creating a new one"
    )
    parser.add_argument(
        "--validate", action="store_true", help="Validate arguments and payload only"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print resolved payload and exit"
    )
    parser.add_argument(
        "--json", action="store_true", help="Print machine-readable JSON only"
    )
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
                "operation": "video_concat_query",
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

    fragments = []
    if args.fragments:
        fragments = [f.strip() for f in args.fragments.split(",") if f.strip()]

    output_bucket = args.saveas_bucket or args.output_bucket or bucket
    output_key = (
        args.saveas_object
        or args.output_key
        or key.rsplit(".", 1)[0] + "_concat." + args.format
    )

    detail = build_concat_detail(
        first_object=key,
        fragments=fragments,
        output_bucket=output_bucket,
        output_object=output_key,
        region=region,
        container_format=args.format,
        video_codec=args.video_codec,
        audio_codec=args.audio_codec,
    )

    plan = {
        "ok": True,
        "operation": "video_concat",
        "bucket": bucket,
        "key": key,
        "fragments": fragments,
        "saveas_bucket": output_bucket,
        "saveas_object": output_key,
        "job_type": JOB_TYPE,
        "job_category": JOB_CATEGORY,
        "detail": detail,
    }

    if args.validate or args.dry_run:
        emit(plan, args.json, "[OK] Resolved request:")
        return

    if not args.json:
        all_clips = [key] + fragments
        print(
            f"[INFO] Creating Concat job: {' + '.join(all_clips)} -> {output_bucket}/{output_key}"
        )
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
        emit(result_payload, args.json, "[OK] Video concatenation result:")
        if result_payload["state"] != "Success":
            sys.exit(1)
        return

    emit(result_payload, args.json, "[OK] Job created:")


if __name__ == "__main__":
    main()
