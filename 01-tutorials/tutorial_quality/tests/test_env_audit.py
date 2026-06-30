from __future__ import annotations

from tutorial_quality.env_audit import (
    audit_env_template,
    collect_env_templates,
    split_env_assignment,
    summarize_env_templates,
)


def finding_codes(findings):
    return {finding.code for finding in findings}


def test_split_env_assignment_supports_export_quotes_and_comments():
    assert split_env_assignment("export CLIENT_ID='abc-123'") == ("CLIENT_ID", "abc-123")
    assert split_env_assignment('TOKEN="secret-token"') == ("TOKEN", "secret-token")
    assert split_env_assignment("  # TOKEN=ignored") is None
    assert split_env_assignment("MISSING_VALUE") == ("MISSING_VALUE", "")


def test_audit_env_template_flags_real_quality_risks(tmp_path):
    env_file = tmp_path / ".env.example"
    env_file.write_text(
        "\n".join(
            [
                "VOLC_ACCESS_KEY=<your-access-key>",
                "VOLC_ACCESS_KEY=actual-access-key",
                "INVALID-KEY=value",
                "SECRET_TOKEN=actual-secret-value",
                "CLIENT_SECRET= ${CLIENT_SECRET} ",
            ]
        ),
        encoding="utf-8",
    )

    findings = audit_env_template(env_file)

    assert finding_codes(findings) == {
        "duplicate-env-key",
        "invalid-env-key",
        "secret-like-env-value",
        "env-value-whitespace",
    }
    assert [finding.line_number for finding in findings if finding.code == "duplicate-env-key"] == [2]
    assert [finding.severity for finding in findings if finding.code == "secret-like-env-value"] == [
        "error",
        "error",
    ]


def test_collect_and_summarize_env_templates_only_use_template_names(tmp_path):
    nested = tmp_path / "tutorial" / "auth"
    nested.mkdir(parents=True)
    (nested / ".env.example").write_text("CLIENT_ID=<your-client-id>\n", encoding="utf-8")
    (nested / ".env.template").write_text(
        "CLIENT_ID=<your-client-id>\nCLIENT_SECRET=<your-client-secret>\n",
        encoding="utf-8",
    )
    (nested / ".env").write_text("CLIENT_SECRET=real-value\n", encoding="utf-8")

    templates = collect_env_templates(tmp_path)
    summary = summarize_env_templates(tmp_path)

    assert [path.name for path in templates] == [".env.example", ".env.template"]
    assert summary["template_count"] == 2
    assert summary["shared_keys"] == {
        "CLIENT_ID": [
            "tutorial/auth/.env.example",
            "tutorial/auth/.env.template",
        ]
    }
