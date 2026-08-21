# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd. and/or its affiliates.
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

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SANDBOX_SKILLS = {
    "docx",
    "pdf",
    "pptx",
    "skill-creator",
    "tos-file-access",
    "xlsx",
}


class RemoteSkillsProxySampleTest(unittest.TestCase):
    def test_manifest_contains_only_remote_skill_metadata(self) -> None:
        manifest = json.loads((ROOT / "remote_skills.json").read_text(encoding="utf-8"))
        skills = manifest["remote_skills"]

        self.assertGreaterEqual(len(skills), 1)
        for skill in skills:
            self.assertIsInstance(skill["name"], str)
            self.assertIsInstance(skill["description"], str)
            self.assertIsInstance(skill["input_schema"], dict)
            self.assertNotIn("implementation", skill)
            self.assertNotIn("script", skill)
            self.assertNotIn("skill_dir", skill)

    def test_manifest_matches_builtin_agentkit_skill_sandbox_skills(self) -> None:
        manifest = json.loads((ROOT / "remote_skills.json").read_text(encoding="utf-8"))
        skill_names = {skill["name"] for skill in manifest["remote_skills"]}

        self.assertEqual(EXPECTED_SANDBOX_SKILLS, skill_names)

    def test_agent_uses_remote_skills_wrapper(self) -> None:
        source = (ROOT / "agent.py").read_text(encoding="utf-8")

        self.assertIn("load_remote_skill_definitions", source)
        self.assertIn("build_remote_skill_tools", source)
        self.assertIn("tools=remote_skill_tools", source)
        self.assertNotIn("execute_skills(", source)


if __name__ == "__main__":
    unittest.main()
