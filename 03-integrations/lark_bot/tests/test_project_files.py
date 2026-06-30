from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_env_example_documents_required_lark_and_volcengine_keys():
    env_example = PROJECT_ROOT / ".env.example"
    keys = {
        line.split("=", 1)[0]
        for line in env_example.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }

    assert keys == {
        "VOLCENGINE_ACCESS_KEY",
        "VOLCENGINE_SECRET_KEY",
        "LARK_APP_ID",
        "LARK_APP_SECRET",
    }


def test_start_script_invokes_lark_bot_entrypoint():
    start_script = (PROJECT_ROOT / "start.sh").read_text(encoding="utf-8")

    assert ("main.py" in start_script) or ("-m main" in start_script)
    assert "python" in start_script


def test_lark_bot_has_separate_agent_package_entrypoint():
    assert (PROJECT_ROOT / "agent.py").exists()
    assert (PROJECT_ROOT / "agent" / "agent.py").exists()
    assert (PROJECT_ROOT / "agent" / "__init__.py").exists()
