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

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from workflow_utils import check_project_yaml


class CheckProjectYamlTest(unittest.TestCase):
    def test_only_changed_projects_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "python" / "sample" / "project.yaml"
            project.parent.mkdir(parents=True)
            project.write_text("name: ''\n", encoding="utf-8")
            script = root / "workflow_utils" / "check_project_yaml.py"

            # Git reports forward slashes for both staged and unstaged changes.
            for staged in (False, True, None):
                with self.subTest(staged=staged):
                    diffs = ["", "python/sample/project.yaml\n"]
                    if staged is None:
                        diffs = ["", ""]
                    elif not staged:
                        diffs.reverse()
                    results = [
                        subprocess.CompletedProcess([], 0, stdout=diff)
                        for diff in diffs
                    ]
                    error = io.StringIO()
                    with (
                        patch.object(check_project_yaml, "__file__", str(script)),
                        patch.object(
                            check_project_yaml.subprocess, "run", side_effect=results
                        ),
                        redirect_stderr(error),
                    ):
                        result = check_project_yaml.main([str(project)])

                    if staged is None:
                        self.assertEqual(result, 0)
                        self.assertEqual(error.getvalue(), "")
                    else:
                        self.assertEqual(result, 1)
                        self.assertIn("name is required", error.getvalue())


if __name__ == "__main__":
    unittest.main()
