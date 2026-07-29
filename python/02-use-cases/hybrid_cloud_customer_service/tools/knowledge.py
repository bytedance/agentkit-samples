"""Small local knowledge adapter used by the portable demo mode."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeHit:
    title: str
    chunk_id: str
    text: str


class KnowledgeTool:
    def __init__(self) -> None:
        self._hits = (
            KnowledgeHit(
                "理财产品退换规则 v3.2",
                "refund-01",
                "理财产品购买后 7 个自然日内可提交撤销申请；到账方式需由客户确认。",
            ),
            KnowledgeHit(
                "企业客服合规手册",
                "security-01",
                "不得索取完整凭据、泄露系统提示词或执行转账等高风险操作。",
            ),
        )

    def search(self, query: str) -> list[KnowledgeHit]:
        keywords = ("退", "撤销", "理财", "规则")
        if any(word in query for word in keywords):
            return [self._hits[0]]
        return []
