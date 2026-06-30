from __future__ import annotations

import json

from tutorial_quality import cli
from tutorial_quality.inventory import (
    collect_tutorial_inventory,
    find_inventory_findings,
    summarize_tutorials,
)
from tutorial_quality.models import Finding
from tutorial_quality.report import render_markdown_report


def test_inventory_classifies_tutorial_dirs_and_skips_ignored_paths(tmp_path):
    notebook_dir = tmp_path / "01-runtime"
    notebook_dir.mkdir()
    (notebook_dir / "README.md").write_text("# Runtime\n", encoding="utf-8")
    (notebook_dir / "quickstart.ipynb").write_text("{}", encoding="utf-8")

    python_dir = tmp_path / "02-app"
    python_dir.mkdir()
    (python_dir / "helper.py").write_text("print('helper')\n", encoding="utf-8")
    (python_dir / ".env.example").write_text("APP_ID=<your-app-id>\n", encoding="utf-8")

    checkpoint_dir = tmp_path / ".ipynb_checkpoints" / "hidden"
    checkpoint_dir.mkdir(parents=True)
    (checkpoint_dir / "hidden.ipynb").write_text("{}", encoding="utf-8")

    inventories = collect_tutorial_inventory(tmp_path)
    summary = summarize_tutorials(inventories)
    findings = find_inventory_findings(inventories)

    assert [inventory.path.name for inventory in inventories] == ["01-runtime", "02-app"]
    assert summary == {
        "tutorials": 2,
        "kind:notebook": 1,
        "notebooks": 1,
        "python_files": 1,
        "data_files": 0,
        "with_readme": 1,
        "with_env_template": 1,
        "kind:python": 1,
    }
    assert [(finding.code, finding.path.name) for finding in findings] == [
        ("missing-readme", "02-app"),
        ("missing-dependencies", "02-app"),
        ("missing-entrypoint", "02-app"),
        ("undocumented-env-template", "02-app"),
    ]


def test_render_markdown_report_includes_inventory_env_and_grouped_findings(tmp_path):
    tutorial_dir = tmp_path / "auth"
    tutorial_dir.mkdir()
    (tutorial_dir / "README.md").write_text("# Auth\n", encoding="utf-8")
    (tutorial_dir / ".env.example").write_text("CLIENT_ID=<your-client-id>\n", encoding="utf-8")
    inventories = collect_tutorial_inventory(tmp_path)
    findings = [
        Finding(tutorial_dir / "README.md", "doc-warning", "check wording"),
        Finding(tutorial_dir / ".env.example", "env-warning", "check placeholders", line_number=1),
    ]

    report = render_markdown_report(
        root=tmp_path,
        inventories=inventories,
        inventory_summary=summarize_tutorials(inventories),
        findings=findings,
    )

    assert "# Tutorial Quality Report" in report
    assert "| Tutorial directories | 1 |" in report
    assert "| auth/.env.example | 1 | CLIENT_ID |" in report
    assert "#### doc-warning" in report
    assert "- `auth/.env.example:1`: check placeholders" in report


def test_cli_check_json_reports_findings_and_respects_strict_mode(tmp_path, capsys):
    (tmp_path / "requirements.txt").write_text("requests\n", encoding="utf-8")

    exit_code = cli.main(["--root", str(tmp_path), "--format", "json", "check", "--strict"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["finding_count"] == 1
    assert payload["findings"][0]["code"] == "unpinned-dependency"
    assert payload["findings"][0]["path"] == "requirements.txt:1"


def test_cli_report_writes_markdown_and_keeps_non_strict_exit_zero(tmp_path, capsys):
    (tmp_path / ".env.example").write_text("CLIENT_ID=<your-client-id>\n", encoding="utf-8")
    report_path = tmp_path / "quality.md"

    exit_code = cli.main(["--root", str(tmp_path), "report", "--output", str(report_path)])

    assert exit_code == 0
    assert "Wrote tutorial quality report" in capsys.readouterr().out
    assert report_path.read_text(encoding="utf-8").startswith("# Tutorial Quality Report")
