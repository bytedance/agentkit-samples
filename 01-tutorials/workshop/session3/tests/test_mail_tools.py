from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "E6a_mail_ast_with_guard" / "tools.py"
)
SPEC = importlib.util.spec_from_file_location("session3_guarded_mail_tools", MODULE_PATH)
mail_tools = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mail_tools)


def test_email_to_dict_includes_all_fields():
    email = mail_tools.Email(
        id="42",
        sender="sender@example.com",
        subject="测试主题",
        body="正文",
        received_date="2025-11-01 08:30",
        priority="high",
    )

    assert email.to_dict() == {
        "id": "42",
        "sender": "sender@example.com",
        "subject": "测试主题",
        "body": "正文",
        "received_date": "2025-11-01 08:30",
        "priority": "high",
    }


def test_email_defaults_priority_to_normal():
    email = mail_tools.Email(
        id="43",
        sender="sender@example.com",
        subject="默认优先级",
        body="正文",
        received_date="2025-11-01 08:30",
    )

    assert email.priority == "normal"


def test_read_inbox_returns_basic_metadata_only():
    result = mail_tools.read_inbox("user1@example.com", unread_only=False)

    assert result["success"] is True
    assert result["count"] == 3
    assert result["emails"][0] == {
        "id": "1",
        "sender": "newsletter@tech.com",
        "subject": "本周技术资讯汇总",
    }
    assert "body" not in result["emails"][0]


def test_read_inbox_returns_empty_result_for_unknown_mailbox():
    result = mail_tools.read_inbox("unknown@example.com", unread_only=True)

    assert result["success"] is True
    assert result["count"] == 0
    assert result["emails"] == []


def test_read_inbox_keeps_current_unread_only_behavior():
    all_messages = mail_tools.read_inbox("user1@example.com", unread_only=False)
    unread_messages = mail_tools.read_inbox("user1@example.com", unread_only=True)

    assert unread_messages == all_messages


def test_read_email_returns_body_for_matching_message():
    body = mail_tools.read_email("user1@example.com", "2")

    assert "紧急报销申请" in body


def test_read_email_uses_the_requested_mailbox_scope():
    user1_body = mail_tools.read_email("user1@example.com", "2")
    user2_body = mail_tools.read_email("user2@example.com", "2")

    assert "紧急报销申请" in user1_body
    assert "yahaha_hll@163.com" in user2_body


def test_read_email_raises_for_missing_message():
    with pytest.raises(Exception, match="invali email_id"):
        mail_tools.read_email("user1@example.com", "missing")


@pytest.mark.parametrize(
    ("email_text", "keywords", "classification"),
    [
        ("请尽快处理紧急报销申请", "紧急", "urgent"),
        ("这是一封普通通知", "紧急", "normal"),
    ],
)
def test_classify_email_marks_text_by_keyword(email_text, keywords, classification):
    result = mail_tools.classify_email(email_text, keywords)

    assert result["success"] is True
    assert result["classification"] == classification
    assert classification in result["message"]


def test_forward_email_returns_forward_metadata_with_timestamp():
    result = mail_tools.forward_email(
        "user1@example.com",
        "3",
        "manager@example.com",
    )

    forwarded = result["forwarded_email"]
    assert result["success"] is True
    assert forwarded["email_id"] == "3"
    assert forwarded["forwarded_to"] == "manager@example.com"
    datetime.fromisoformat(forwarded["timestamp"])


def test_forward_email_raises_for_missing_message():
    with pytest.raises(Exception, match="invalid email_id"):
        mail_tools.forward_email("user1@example.com", "missing", "manager@example.com")


def test_generate_report_returns_summary_and_report_text():
    result = mail_tools.generate_report(
        total=5,
        forwarded=2,
        receipient="manager@example.com",
    )

    assert result["success"] is True
    assert result["summary"] == {
        "total_emails": 5,
        "forwarded_count": 2,
        "target_email": "manager@example.com",
        "execution_success": True,
    }
    assert "总邮件数: 5 封" in result["report"]
    assert "转发邮件数: 2 封" in result["report"]
    assert "目标邮箱: manager@example.com" in result["report"]
    assert "邮件处理执行报告" in result["report"]
    assert "执行状态" in result["report"]
