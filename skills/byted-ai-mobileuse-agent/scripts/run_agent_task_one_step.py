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
import uuid
from typing import Any, Dict, Optional

from sdk_client import UniversalClient, error_envelope, extract_result_payload


def as_non_empty_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def build_request(
    *,
    product_id: str,
    pod_id: str,
    prompt: str,
    thread_id: str,
    max_step: Optional[int],
    timeout: Optional[int],
) -> Dict[str, Any]:
    resolved_product_id = as_non_empty_str(product_id)
    resolved_pod_id = as_non_empty_str(pod_id)
    resolved_prompt = as_non_empty_str(prompt)
    resolved_thread_id = as_non_empty_str(thread_id)

    if not resolved_product_id:
        raise ValueError("ProductId is required (--product-id)")
    if not resolved_pod_id:
        raise ValueError("PodId is required (--pod-id)")
    if not resolved_prompt:
        raise ValueError("UserPrompt is required (--prompt)")
    if not resolved_thread_id:
        raise ValueError("ThreadId is required (--thread-id)")

    req: Dict[str, Any] = {
        "RunName": "mobile-use execution",
        "PodId": resolved_pod_id,
        "ProductId": resolved_product_id,
        "UserPrompt": resolved_prompt,
        "ThreadId": resolved_thread_id,
    }

    if max_step is not None:
        req["MaxStep"] = int(max_step)
    if timeout is not None:
        req["Timeout"] = int(timeout)

    return req


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


def _emit(event: Dict[str, Any]) -> None:
    print(json.dumps(event, ensure_ascii=False) + "\n", end="", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--access-key", required=True)
    ap.add_argument("--secret-key", required=True)
    ap.add_argument("--product-id", required=True)
    ap.add_argument("--pod-id", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--thread-id", required=True)
    ap.add_argument("--max-step", type=int, default=None, help="Optional. Max agent steps (1~500).")
    ap.add_argument("--timeout", type=int, default=None, help="Optional. Timeout in seconds (1~86400).")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        req = build_request(
            product_id=args.product_id,
            pod_id=args.pod_id,
            prompt=args.prompt,
            thread_id=args.thread_id,
            max_step=args.max_step,
            timeout=args.timeout,
        )
        client = UniversalClient(access_key=args.access_key, secret_key=args.secret_key)
        raw_start = client.call(method="POST", action="RunAgentTaskOneStep", body=req)
        started = extract_result_payload(raw_start)
        run_id = as_non_empty_str(started.get("RunId")) or ""
        thread_id = as_non_empty_str(args.thread_id) or ""

        _emit(
            {
                "type": "started",
                "run_id": run_id,
                "run_name": as_non_empty_str(started.get("RunName")) or "",
                "thread_id": as_non_empty_str(started.get("ThreadId")) or thread_id,
                "raw_response": raw_start,
            }
        )

        terminal_statuses = {3, 5, 6, 7}
        last_step_raw: Optional[Dict[str, Any]] = None
        status: Optional[int] = None

        local_wait_seconds = int(args.timeout) if args.timeout is not None else 300
        deadline = time.time() + max(1, local_wait_seconds)

        if run_id:
            while time.time() < deadline:
                step_body: Dict[str, Any] = {"RunId": run_id}
                if thread_id:
                    step_body["ThreadId"] = thread_id
                last_step_raw = client.call(method="GET", action="ListAgentRunCurrentStep", body=step_body)
                status = _extract_task_status(last_step_raw)
                _emit(
                    {
                        "type": "progress",
                        "run_id": run_id,
                        "thread_id": thread_id,
                        "status": status,
                        "raw_response": last_step_raw,
                    }
                )
                if status in terminal_statuses:
                    break
                time.sleep(2)

        agent_result_raw: Optional[Dict[str, Any]] = None
        if run_id and status in terminal_statuses:
            agent_result_raw = client.call(method="GET", action="GetAgentResult", body={"RunId": run_id, "IsDetail": True})

        out = {
            "type": "result",
            "ok": True,
            "run_id": run_id,
            "run_name": as_non_empty_str(started.get("RunName")) or "",
            "thread_id": as_non_empty_str(started.get("ThreadId")) or as_non_empty_str(args.thread_id) or "",
            "raw_response": raw_start,
            "current_step_status": status,
            "current_step_raw": last_step_raw,
            "agent_result_raw": agent_result_raw,
        }
        _emit(out)
        return 0
    except Exception as e:
        out = error_envelope(err=e)
        _emit({"type": "error", **out})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
