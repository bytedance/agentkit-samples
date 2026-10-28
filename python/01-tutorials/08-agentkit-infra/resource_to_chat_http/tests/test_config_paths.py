"""共享配置路径选择和写回的离线验证。"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _config


class ConfigPathTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.shared = self.root / "config.yaml"
        self.legacy = self.root / "resource_to_chat_http" / "config.yaml"
        self.console = self.root / "harness_console" / "config.yaml"
        self.legacy.parent.mkdir()
        self.console.parent.mkdir()
        self.enterContext(patch.dict(os.environ, {"HARNESS_INFRA_CONFIG": ""}))
        self.enterContext(patch.object(_config, "DEFAULT_CONFIG_PATH", self.shared))
        self.enterContext(patch.object(_config, "LEGACY_CONFIG_PATH", self.legacy))
        self.enterContext(
            patch.object(
                _config, "EXAMPLE_CONFIG_PATH", self.root / "config.yaml.example"
            )
        )

    def test_shared_config_precedes_legacy_locations(self):
        self.legacy.touch()
        self.assertEqual(_config.config_path(), self.legacy.resolve())
        self.console.touch()
        self.assertEqual(_config.config_path(self.console), self.console.resolve())
        self.shared.touch()
        self.assertEqual(_config.config_path(), self.shared.resolve())
        self.assertEqual(_config.config_path(self.console), self.shared.resolve())

    def test_explicit_missing_config_is_not_silently_replaced(self):
        self.shared.touch()
        selected = self.root / "explicit.yaml"
        with patch.dict(os.environ, {"HARNESS_INFRA_CONFIG": str(selected)}):
            self.assertEqual(_config.config_path(self.console), selected.resolve())
            with self.assertRaisesRegex(RuntimeError, "explicit.yaml"):
                _config._read_yaml()

    def test_missing_default_points_to_shared_template(self):
        self.assertEqual(_config.config_path(), self.shared.resolve())
        with self.assertRaises(RuntimeError) as error:
            _config._read_yaml()
        self.assertIn(str(self.root / "config.yaml.example"), str(error.exception))
        self.assertFalse(self.shared.exists())

    def test_runtime_writeback_updates_only_selected_config(self):
        data = {"version": 1, "session": {"id": ""}}
        self.shared.write_text(yaml.safe_dump(data))
        self.legacy.write_text("legacy contents must not change")
        _config.persist_session("session-new", "new", "https://example.com")
        self.assertEqual(
            yaml.safe_load(self.shared.read_text())["session"]["id"], "session-new"
        )
        self.assertEqual(self.legacy.read_text(), "legacy contents must not change")
        self.assertEqual(self.shared.stat().st_mode & 0o777, 0o600)

    def test_session_store_network_defaults_and_private_validation(self):
        default = _config._session_store_config({})
        self.assertEqual(default.project_name, "default")
        self.assertEqual(default.vpc_id, "")
        self.assertEqual(default.subnet_ids, [])

        with self.assertRaisesRegex(RuntimeError, "exactly one subnet_id"):
            _config._session_store_config(
                {
                    "session_store": {
                        "network": {
                            "use_private_network": True,
                            "vpc_id": "vpc-test",
                            "subnet_ids": [],
                        }
                    }
                }
            )

        private = _config._session_store_config(
            {
                "session_store": {
                    "project_name": "project-test",
                    "network": {
                        "use_private_network": True,
                        "vpc_id": "vpc-test",
                        "subnet_ids": ["subnet-test"],
                    },
                }
            }
        )
        self.assertEqual(private.project_name, "project-test")
        self.assertEqual(private.vpc_id, "vpc-test")
        self.assertEqual(private.subnet_ids, ["subnet-test"])
