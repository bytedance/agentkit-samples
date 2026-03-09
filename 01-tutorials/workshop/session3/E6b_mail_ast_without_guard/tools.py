from datetime import datetime
import json
import os


# Mock数据结构
class Email:
    def __init__(
        self,
        id: str,
        sender: str,
        subject: str,
        body: str,
        received_date: str,
        priority: str = "normal",
    ):
        self.id = id
        self.sender = sender
        self.subject = subject
        self.body = body
        self.received_date = received_date
        self.priority = priority

    def to_dict(self):
        return {
            "id": self.id,
            "sender": self.sender,
            "subject": self.subject,
            "body": self.body,
            "received_date": self.received_date,
            "priority": self.priority,
        }


# 从JSON文件加载邮件数据
# 获取当前文件的目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 构建emails.json的绝对路径
email_file_path = os.path.join(current_dir, "emails.json")

with open(email_file_path, "r", encoding="utf-8") as f:
    email_data = json.load(f)


def read_inbox(mailbox: str, unread_only: bool):
    """
    读取用户收件箱中的邮件列表，仅返回ID、发件人和标题
    Args:
        mailbox (str): 要读取的邮箱的地址
        unread_only (bool): 是否仅读取未读邮件
    """
    # 根据mailbox过滤邮件
    owner_emails = [Email(**email) for email in email_data.get(mailbox, [])]

    emails = [
        {"id": email.id, "sender": email.sender, "subject": email.subject}
        for email in owner_emails
    ]

    result = {
        "success": True,
        "count": len(emails),
        "emails": emails,
        "message": f"成功读取 {len(emails)} 封邮件基本信息",
    }

    return result


def read_email(mailbox: str, email_id: str):
    """
    读取邮件内容，仅返回邮件正文
    Args:
        mailbox (str): 要读取的邮箱的地址
        email_id (str): 邮件ID
    """
    # 根据mailbox过滤邮件
    owner_emails = [Email(**email) for email in email_data.get(mailbox, [])]

    email = next((e for e in owner_emails if e.id == email_id), None)

    if email:
        # 只返回邮件正文内容
        result = email.body
        return result
    else:
        raise Exception("invali email_id")


def classify_email(email_text: str, keywords: str):
    """
    根据指定的关键对单封邮件进行分类
    Args:
        email_text (str): 邮件正文文本
    """
    classification = "urgent" if keywords in email_text else "normal"

    result = {
        "success": True,
        "classification": classification,
        "message": f"成功分类邮件为 {classification} 优先级",
    }

    return result


def forward_email(mailbox: str, email_id: str, recipient: str):
    """
    将指定的单封邮件转发到目标邮箱
    Args:
        mailbox (str): 要读取的邮箱的地址
        email_id (str): 邮件ID
        receipient (str): 转发目标收件人邮箱
    """
    # 根据mailbox过滤邮件
    owner_emails = [Email(**email) for email in email_data.get(mailbox, [])]

    email = next((e for e in owner_emails if e.id == email_id), None)
    if not email:
        raise Exception("invalid email_id")

    result = {
        "success": True,
        "forwarded_email": {
            "email_id": email_id,
            "forwarded_to": recipient,
            "timestamp": datetime.now().isoformat(),
        },
        "message": f"成功转发邮件 {email_id} 到 {recipient}",
    }
    return result


def generate_report(total: int, forwarded: int, receipient: str):
    """
    生成任务执行总结报告
    Args:
        total (int): 处理的邮件总数
        forwarded (int): 转发的邮件总数
        receipient (str): 转发目标收件人邮箱
    """

    success = True

    # 生成报告
    report = f"""
===== 邮件处理执行报告 =====
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

📊 处理统计:
  - 总邮件数: {total} 封
  - 转发邮件数: {forwarded} 封
  - 目标邮箱: {receipient}
  - 执行状态: {"✅ 成功" if success else "❌ 失败"}
"""

    result = {
        "success": True,
        "report": report,
        "summary": {
            "total_emails": total,
            "forwarded_count": forwarded,
            "target_email": receipient,
            "execution_success": success,
        },
    }

    return result


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
