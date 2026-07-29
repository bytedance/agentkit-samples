"""Portable business core shared by local tests and the AgentKit wrapper."""

from __future__ import annotations

import uuid

from platform_capabilities import SessionStore, sandbox_calculate
from tools import (
    CRMTool,
    KnowledgeTool,
    MemoryTool,
    complaint_trend,
    detect_attack,
    transaction_summary,
)
from utils.models import AgentResponse, CapabilityEvent


class HybridCustomerService:
    def __init__(self, mode: str = "demo") -> None:
        self.mode = mode
        self.knowledge = KnowledgeTool()
        self.memory = MemoryTool()
        self.crm = CRMTool()
        self.sessions = SessionStore()

    def chat(
        self,
        message: str,
        *,
        tenant_id: str = "demo-bank",
        user_id: str = "user-001",
        session_id: str = "session-001",
        identity_source: str = "local-request",
    ) -> AgentResponse:
        trace_id = f"trace-{uuid.uuid4().hex[:12]}"
        events: list[CapabilityEvent] = []
        events.append(
            CapabilityEvent("identity.resolve", mode=self.mode, detail={"source": identity_source})
        )
        state = self.sessions.load(tenant_id, user_id, session_id)
        events.append(
            CapabilityEvent("session.load", mode=self.mode, detail={"backend": self.sessions.mode})
        )

        matches = detect_attack(message)
        if matches:
            events.append(
                CapabilityEvent(
                    "security.prompt_injection",
                    status="blocked",
                    mode=self.mode,
                    detail={"risk_level": "critical", "rule_count": len(matches)},
                )
            )
            return AgentResponse(
                "该请求包含越权或敏感操作指令，已被安全策略拦截。",
                session_id,
                trace_id,
                self.mode,
                events=events,
            )

        if "sandbox" in message.lower() or "隔离计算" in message:
            result = sandbox_calculate("1284650 / 237")
            events.extend(
                [
                    CapabilityEvent("sandbox.exec", mode=self.mode, detail=result),
                    CapabilityEvent(
                        "mcp.tool_call",
                        mode=self.mode,
                        detail={"tool": "calculate_transaction_summary"},
                    ),
                ]
            )
            return AgentResponse(
                f"Sandbox 隔离计算完成：单笔平均收益约 ¥{float(result['result']):,.2f}。",
                session_id,
                trace_id,
                self.mode,
                events=events,
            )

        if "合规" in message or "skill" in message.lower():
            events.extend(
                [
                    CapabilityEvent(
                        "skill.discover",
                        mode=self.mode,
                        detail={"skill": "customer-service-compliance"},
                    ),
                    CapabilityEvent(
                        "skill.execute",
                        mode=self.mode,
                        detail={"decision": "manual-confirmation-required"},
                    ),
                ]
            )
            return AgentResponse(
                "合规 Skill 检查完成：退款执行前必须展示金额、渠道和预计到账时间，并由用户确认。",
                session_id,
                trace_id,
                self.mode,
                events=events,
            )

        if "偏好" in message or "快速到账" in message:
            self.memory.remember(tenant_id, user_id, "快速到账")
            state["refund_preference"] = "快速到账"
            self.sessions.save(tenant_id, user_id, session_id, state)
            events.append(CapabilityEvent("memory.write", mode=self.mode))
            events.append(
                CapabilityEvent(
                    "session.save", mode=self.mode, detail={"backend": self.sessions.mode}
                )
            )
            return AgentResponse(
                "已记住您偏好快速到账；执行退款前仍会请您确认具体到账渠道。",
                session_id,
                trace_id,
                self.mode,
                events=events,
            )

        if "提交" in message and ("退" in message or "工单" in message):
            preference = self.memory.recall(tenant_id, user_id)
            channel = "alipay" if preference == "快速到账" else "bank_account"
            order = self.crm.create_work_order(
                user_id=user_id,
                channel=channel,
                idempotency_key=f"{session_id}:refund",
            )
            events.extend(
                [
                    CapabilityEvent("memory.read", mode=self.mode),
                    CapabilityEvent(
                        "tool.work_order.create",
                        mode=self.mode,
                        detail={"order_id": order.order_id, "idempotent": True},
                    ),
                ]
            )
            return AgentResponse(
                f"已创建退款工单 {order.order_id}，建议渠道为 {channel}。请确认后进入正式处理。",
                session_id,
                trace_id,
                self.mode,
                events=events,
            )

        if "237" in message or "交易" in message or "总收益" in message:
            summary = transaction_summary()
            events.append(
                CapabilityEvent(
                    "tool.transaction_analysis", mode=self.mode, detail={"rows": summary["count"]}
                )
            )
            return AgentResponse(
                f"已分析 {summary['count']} 笔合成交易，总收益 ¥{summary['total_profit']:,}。"
                "按产品分类：稳健理财 ¥528,300、债券增强 ¥411,250、现金管理 ¥345,100。",
                session_id,
                trace_id,
                self.mode,
                events=events,
            )

        if "投诉" in message or "趋势" in message or "预测" in message:
            result = complaint_trend()
            events.extend(
                [
                    CapabilityEvent("a2a.discover", mode=self.mode),
                    CapabilityEvent(
                        "a2a.delegate.data_agent",
                        mode=self.mode,
                        detail={"fallback": self.mode != "live"},
                    ),
                ]
            )
            return AgentResponse(
                "数据 Agent 分析完成：Q1 234 件、Q2 142 件、Q3 89 件、Q4 118 件；"
                f"下季度预计 {result['next_quarter_forecast']} 件，重点关注到账延迟和费率透明度。",
                session_id,
                trace_id,
                self.mode,
                events=events,
            )

        hits = self.knowledge.search(message)
        if hits:
            hit = hits[0]
            events.append(
                CapabilityEvent(
                    "knowledge.search", mode=self.mode, detail={"hits": len(hits), "selected": 1}
                )
            )
            return AgentResponse(
                f"根据《{hit.title}》，{hit.text}",
                session_id,
                trace_id,
                self.mode,
                citations=[{"title": hit.title, "chunk_id": hit.chunk_id}],
                events=events,
            )

        return AgentResponse(
            "我可以协助查询退换规则、记住到账偏好、创建退款工单、分析交易或投诉趋势。",
            session_id,
            trace_id,
            self.mode,
            events=[*events, CapabilityEvent("router.fallback", mode=self.mode)],
        )
