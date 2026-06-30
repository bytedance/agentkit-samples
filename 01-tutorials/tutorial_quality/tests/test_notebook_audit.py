from __future__ import annotations

import json

from tutorial_quality.notebook_audit import (
    audit_notebook,
    collect_notebook_findings,
    output_text,
)


def write_notebook(path, cells):
    path.write_text(
        json.dumps(
            {
                "cells": cells,
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        ),
        encoding="utf-8",
    )


def code_cell(source, outputs=None):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": outputs or [],
        "source": source,
    }


def test_output_text_collects_plain_error_and_rich_display_data():
    output = {
        "text": ["line one\n", "line two\n"],
        "ename": "ValueError",
        "evalue": "bad input",
        "data": {
            "text/plain": ["rich text"],
            "application/json": {"ignored": "non-string"},
        },
    }

    assert output_text(output) == (
        "line one\nline two\nValueErrorbad inputrich text{'ignored': 'non-string'}"
    )


def test_audit_notebook_detects_paths_secrets_large_outputs_and_empty_files(tmp_path):
    notebook = tmp_path / "tutorial.ipynb"
    write_notebook(
        notebook,
        [
            code_cell("open('/Users/alice/private/config.json')"),
            code_cell("client = make_client(api_key='actual-access-key')"),
            code_cell(
                "print('ok')",
                outputs=[
                    {"output_type": "stream", "name": "stdout", "text": "x" * 11},
                    {"output_type": "execute_result", "data": {"text/plain": "token=abc123456789"}},
                ],
            ),
        ],
    )
    empty = tmp_path / "empty.ipynb"
    write_notebook(empty, [])

    findings = audit_notebook(notebook, max_output_chars=10)
    empty_findings = audit_notebook(empty)

    assert [finding.code for finding in findings] == [
        "absolute-path",
        "secret-like-source",
        "large-output",
        "secret-like-output",
    ]
    assert [finding.code for finding in empty_findings] == ["empty-notebook"]


def test_collect_notebook_findings_skips_checkpoint_directories(tmp_path):
    write_notebook(tmp_path / "visible.ipynb", [code_cell("print('ok')")])
    checkpoint_dir = tmp_path / ".ipynb_checkpoints"
    checkpoint_dir.mkdir()
    write_notebook(checkpoint_dir / "hidden.ipynb", [])

    assert collect_notebook_findings(tmp_path) == []
