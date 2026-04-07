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

import argparse
import json
import time
from typing import Any, Dict, Optional

from sdk_client import UniversalClient, error_envelope


def as_non_empty_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _as_optional_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, int):
        return v
    try:
        s = str(v).strip()
        if not s:
            return None
        return int(s)
    except Exception:
        return None


def _extract_task_status(resp: Any) -> Optional[int]:
    if not isinstance(resp, dict):
        return None
    payload: Any = resp.get("Result") if isinstance(resp.get("Result"), dict) else resp
    if isinstance(payload, dict):
        if "Status" in payload:
            return _as_optional_int(payload.get("Status"))
        items = payload.get("Items") or payload.get("items")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict) and "Status" in first:
                return _as_optional_int(first.get("Status"))
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--access-key", required=True)
    ap.add_argument("--secret-key", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--thread-id", default=None)
    ap.add_argument("--wait", type=int, default=10, help="Poll duration in seconds. Default 10.")
    ap.add_argument("--interval", type=int, default=2, help="Poll interval in seconds. Default 2.")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        run_id = as_non_empty_str(args.run_id)
        if not run_id:
            raise ValueError("RunId is required (--run-id)")

        client = UniversalClient(access_key=args.access_key, secret_key=args.secret_key)
        body: Dict[str, Any] = {"RunId": run_id}
        thread_id = as_non_empty_str(args.thread_id)
        if thread_id:
            body["ThreadId"] = thread_id

        terminal_statuses = {3, 5, 6, 7}
        raw: Dict[str, Any] = {}
        status: Optional[int] = None
        deadline = time.time() + max(0, int(args.wait))

        while True:
            raw = client.call(method="GET", action="ListAgentRunCurrentStep", body=body)
            status = _extract_task_status(raw)
            if status in terminal_statuses:
                break
            if time.time() >= deadline:
                break
            time.sleep(max(1, int(args.interval)))

        out: Dict[str, Any] = {
            "ok": True,
            "run_id": run_id,
            "thread_id": thread_id or "",
            "status": status,
            "raw_response": raw,
        }
        if args.pretty:
            print(json.dumps(out, ensure_ascii=False, indent=2) + "\n", end="")
        else:
            print(json.dumps(out, ensure_ascii=False) + "\n", end="")
        return 0
    except Exception as e:
        out = error_envelope(err=e)
        print(json.dumps(out, ensure_ascii=False, indent=2) + "\n", end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
