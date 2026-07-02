#!/usr/bin/env python3
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

"""
poll_execution.py — resume polling a snapshot job by RunId

Usage:
  uv run python scripts/poll_execution.py <RunId> [space_name]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vod_client import get_client, get_space_name, out, bail
from snapshot import poll_snapshot


def main():
    if len(sys.argv) < 2:
        bail("Usage: uv run python scripts/poll_execution.py <RunId> [space_name]")

    run_id = sys.argv[1].strip()
    if not run_id:
        bail("RunId must not be empty")

    space_name = get_space_name(argv_pos=2)
    client = get_client()
    out(poll_snapshot(client, run_id, space_name))


if __name__ == "__main__":
    main()

