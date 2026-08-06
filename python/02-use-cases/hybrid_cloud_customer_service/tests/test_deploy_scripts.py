from __future__ import annotations

import importlib.util
import logging
import os
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def test_verbose_docker_logger_only_streams_docker_debug_lines(capsys) -> None:
    module_path = PROJECT_ROOT / "scripts" / "agentkit_cli_poc.py"
    spec = importlib.util.spec_from_file_location("agentkit_cli_poc_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    logger = logging.getLogger("agentkit.toolkit.docker.container")
    previous_level = logger.level
    os.environ["AGENTKIT_VERBOSE_DOCKER_LOGS"] = "1"
    handler = module._enable_verbose_docker_logs()
    assert handler is not None
    try:
        logger.debug("Step 1/4 : COPY requirements.lock ./")
        logger.info("normal AgentKit line")
    finally:
        logger.removeHandler(handler)
        logger.setLevel(previous_level)
        os.environ.pop("AGENTKIT_VERBOSE_DOCKER_LOGS", None)

    captured = capsys.readouterr()
    assert "[docker] Step 1/4 : COPY requirements.lock ./" in captured.err
    assert "normal AgentKit line" not in captured.err


def test_invalid_control_plane_credentials_stop_before_image_build(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    scripts = project / "scripts"
    fake_bin = tmp_path / "bin"
    venv_bin = project / ".venv" / "bin"
    scripts.mkdir(parents=True)
    fake_bin.mkdir()
    venv_bin.mkdir(parents=True)

    for relative_path in (
        "scripts/deploy_hybrid.sh",
        "scripts/configure_agentkit_cli.sh.example",
        "agentkit.yaml.example",
    ):
        source = PROJECT_ROOT / relative_path
        target = project / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    docker_marker = tmp_path / "docker-was-called"
    _write_executable(fake_bin / "uv", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "docker",
        f"#!/usr/bin/env bash\ntouch {docker_marker!s}\nexit 0\n",
    )
    _write_executable(fake_bin / "curl", "#!/usr/bin/env bash\nprintf '{\"pong\":true}'\n")
    _write_executable(
        venv_bin / "agentkit",
        """#!/usr/bin/env bash
if [[ "$1" == "runtime" && "$2" == "list" ]]; then
  echo '{"ResponseMetadata":{"RequestId":"req-control-plane-test","Action":"ListRuntimes","Version":"2025-10-30","Service":"agentkit","Region":"cn-beijing","Error":{"Code":"InvalidSignature","Message":"The request signature does not match. AccessKeyId=AKLT_SHOULD_NOT_LEAK&Signature=SIGNATURE_SHOULD_NOT_LEAK"}}}'
  echo 'AgentKit request failed' >&2
  exit 7
fi
exit 0
""",
    )

    access_key = "qa-invalid-access-key-marker"
    secret_key = "qa-invalid-secret-key-marker"
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "AGENTKIT_DEPLOY_MODE": "demo",
            "AGENTKIT_MODEL_REQUIRED": "0",
            "AGENTKIT_POST_DEPLOY_INVOKE": "0",
            "AGENTKIT_OPENAPI_SCHEME": "http",
            "AGENTKIT_OPENAPI_HOST": "openapi.example.com",
            "VOLCENGINE_ACCESS_KEY": access_key,
            "VOLCENGINE_SECRET_KEY": secret_key,
            "VOLCENGINE_REGION": "cn-beijing",
        }
    )

    result = subprocess.run(
        ["bash", str(scripts / "deploy_hybrid.sh")],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "控制面 AK/SK 鉴权失败" in output
    assert "未进入镜像构建或 Runtime 创建阶段" not in output
    assert "TOP 详细错误（凭证与签名值已脱敏）" in output
    assert "RequestId: req-control-plane-test" in output
    assert "Action: ListRuntimes" in output
    assert "Region: cn-beijing" in output
    assert "Code: InvalidSignature" in output
    assert "The request signature does not match" in output
    assert access_key not in output
    assert secret_key not in output
    assert "AKLT_SHOULD_NOT_LEAK" not in output
    assert "SIGNATURE_SHOULD_NOT_LEAK" not in output
    assert "AgentKit request failed" not in output
    assert not docker_marker.exists()


def test_stale_runtime_binding_stops_before_image_build(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    scripts = project / "scripts"
    fake_bin = tmp_path / "bin"
    venv_bin = project / ".venv" / "bin"
    fake_home = tmp_path / "home"
    scripts.mkdir(parents=True)
    fake_bin.mkdir()
    venv_bin.mkdir(parents=True)
    (fake_home / ".agentkit").mkdir(parents=True)

    shutil.copy2(PROJECT_ROOT / "scripts/deploy_hybrid.sh", scripts / "deploy_hybrid.sh")
    (project / "agentkit.yaml").write_text(
        """common: {}
launch_types:
  hybrid:
    region: cn-sh
    runtime_name: stale-runtime-demo
    runtime_id: r-stale-runtime-id
"""
    )
    (fake_home / ".agentkit" / "config.yaml").write_text(
        """region: cn-sh
services:
  agentkit:
    scheme: http
    host: openapi.example.com
"""
    )

    docker_marker = tmp_path / "docker-was-called"
    _write_executable(fake_bin / "uv", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(
        fake_bin / "docker",
        f"#!/usr/bin/env bash\ntouch {docker_marker!s}\nexit 0\n",
    )
    _write_executable(fake_bin / "curl", "#!/usr/bin/env bash\nprintf '{\"pong\":true}'\n")
    _write_executable(
        venv_bin / "agentkit",
        """#!/usr/bin/env bash
if [[ "$1" == "runtime" && "$2" == "get" ]]; then
  echo 'Runtime not found: r-stale-runtime-id' >&2
  exit 1
fi
exit 0
""",
    )

    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:{environment['PATH']}",
            "HOME": str(fake_home),
            "AGENTKIT_DEPLOY_MODE": "demo",
            "AGENTKIT_MODEL_REQUIRED": "0",
            "AGENTKIT_POST_DEPLOY_INVOKE": "0",
            "VOLCENGINE_REGION": "cn-sh",
        }
    )

    result = subprocess.run(
        ["bash", str(scripts / "deploy_hybrid.sh")],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "项目绑定的 Runtime ID 在当前 Region 中不存在" in output
    assert "r-stale-runtime-id (cn-sh)" in output
    assert "镜像尚未构建或推送" in output
    assert not docker_marker.exists()
