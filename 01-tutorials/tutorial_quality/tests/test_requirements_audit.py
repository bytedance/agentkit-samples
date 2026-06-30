from __future__ import annotations

from tutorial_quality.requirements_audit import (
    audit_requirements,
    meaningful_requirement_lines,
    split_requirement,
    strip_inline_comment,
)


def test_strip_inline_comment_preserves_hash_inside_quotes():
    assert strip_inline_comment("demo==1.0 # normal comment") == "demo==1.0"
    assert strip_inline_comment("demo=='1.0#local' # normal comment") == "demo=='1.0#local'"
    assert strip_inline_comment('demo=="1.0#local"') == 'demo=="1.0#local"'


def test_split_requirement_normalizes_editable_and_external_sources():
    assert split_requirement("requests>=2.32.0") == ("requests", ">=2.32.0")
    assert split_requirement("-e git+https://example.com/repo.git#egg=demo") == (
        "git+https://example.com/repo.git#egg=demo",
        "",
    )
    assert split_requirement("https://example.com/pkg.whl") == (
        "https://example.com/pkg.whl",
        "",
    )


def test_audit_requirements_flags_unpinned_external_and_duplicate_dependencies(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "\n".join(
            [
                "--index-url https://example.com/simple",
                "-r base.txt",
                "requests>=2.32.0",
                "Requests==2.32.3",
                "pandas",
                "git+https://example.com/private/pkg.git",
            ]
        ),
        encoding="utf-8",
    )

    findings = audit_requirements(requirements)

    assert [(finding.code, finding.line_number) for finding in findings] == [
        ("unpinned-dependency", 5),
        ("external-dependency", 6),
        ("duplicate-dependency", 4),
    ]
    assert meaningful_requirement_lines(requirements) == [
        (3, "requests>=2.32.0"),
        (4, "Requests==2.32.3"),
        (5, "pandas"),
        (6, "git+https://example.com/private/pkg.git"),
    ]
