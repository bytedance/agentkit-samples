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
from typing import Any, Dict, Optional

from sdk_client import UniversalClient, error_envelope


def as_non_empty_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--access-key", required=True)
    ap.add_argument("--secret-key", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--thread-id", default=None)
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    try:
        run_id = as_non_empty_str(args.run_id)
        if not run_id:
            raise ValueError("RunId is required (--run-id)")

        client = UniversalClient(access_key=args.access_key, secret_key=args.secret_key)
        raw = client.call(method="GET", action="GetAgentResult", body={"RunId": run_id, "IsDetail": True})
        thread_id = as_non_empty_str(args.thread_id) or ""
        out: Dict[str, Any] = {"ok": True, "run_id": run_id, "thread_id": thread_id, "raw_response": raw}
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
