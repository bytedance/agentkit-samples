# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from efs_workspace import (  # noqa: E402
    _extract_marker_json,
    _isolation_command,
    _reader_command,
    _workspace_command,
    build_create_session_body,
)


class EFSWorkspaceTest(unittest.TestCase):
    def test_build_create_session_body_includes_efs_mount_configs(self) -> None:
        body = build_create_session_body(
            tool_id="t-demo",
            filespace_name="agentkit-demo",
            mount_path="/mnt/efs/",
            ttl_seconds=60,
            user_session_id="user-session-1",
        )

        self.assertEqual(body["ToolId"], "t-demo")
        self.assertEqual(body["Ttl"], 60)
        self.assertEqual(body["UserSessionId"], "user-session-1")
        self.assertEqual(
            body["EfsMountConfigs"],
            [
                {
                    "FilespaceName": "agentkit-demo",
                    "LocalMountPath": "/mnt/efs/",
                    "ReadOnly": False,
                }
            ],
        )

    def test_build_create_session_body_keeps_required_mount_path_slash(self) -> None:
        body = build_create_session_body(
            tool_id="t-demo",
            filespace_name="agentkit-demo",
            mount_path="/mnt/efs",
            ttl_seconds=60,
            user_session_id="user-session-1",
        )

        self.assertEqual(
            body["EfsMountConfigs"][0]["LocalMountPath"],
            "/mnt/efs/",
        )

    def test_extract_marker_json_reads_last_matching_line(self) -> None:
        output = "\n".join(
            [
                'EFS_DEMO_RESULT={"old": true}',
                "noise",
                'shell-prefix EFS_DEMO_RESULT={"workspace": "/mnt/efs/a"}',
            ]
        )

        self.assertEqual(
            _extract_marker_json(output, "EFS_DEMO_RESULT"),
            {"workspace": "/mnt/efs/a"},
        )

    def test_workspace_commands_do_not_inline_plain_task(self) -> None:
        task_text = "review repo and summarize build notes"
        workspace = "efs-demo-workspace"
        writer_script = _workspace_command(task_text, workspace)
        reader_script = _reader_command(workspace, "abc123")
        isolation_script = _isolation_command(workspace)

        self.assertNotIn(task_text, writer_script)
        self.assertIn("EFS_DEMO_RESULT=", writer_script)
        self.assertIn("read_workspace.py", writer_script)
        self.assertIn("subprocess.run", reader_script)
        self.assertIn("read_workspace.py", reader_script)
        self.assertIn("EFS_ISOLATION_RESULT", isolation_script)

    def test_marker_json_is_valid(self) -> None:
        value = {"workspace": "/mnt/efs/demo"}
        output = "EFS_SHARED_RUN_RESULT=" + json.dumps(value)

        self.assertEqual(_extract_marker_json(output, "EFS_SHARED_RUN_RESULT"), value)


if __name__ == "__main__":
    unittest.main()
